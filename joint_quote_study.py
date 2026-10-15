"""Offline joint quotation study. Rules fixed before this run, no trader labels.

Entry features use only ADD and earlier messages. Cancellation/fill outcomes
never select patterns. Cash targets were discovered on this same day earlier;
an afternoon check here is a stability check, not independent validation.
"""
from __future__ import annotations
from bisect import bisect_left
from collections import defaultdict
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from order_patterns import reconstruct, ms, session, clock
from orderbook import OrderBook, apply_market_event

ROOT=Path(__file__).resolve().parent
DATA=ROOT/'sse50_20260923'
OUT=ROOT/'reports'/'joint_quotes'
CASH={688008:100000,688012:200000,688041:100000,688111:100000,688256:300000}


def entry_features(symbol, add, orders, trades):
    """Exact historical book before each ADD, no quote-label alignment search."""
    events=[(int(r['Time']),int(r['Channel']),int(r['BizIndex']),'ord',r) for r in orders.to_dict('records')]
    events += [(int(r['Time']),int(r['Channel']),int(r['BizIndex']),'exe',r) for r in trades.to_dict('records')]
    if len({e[1] for e in events})!=1:raise ValueError('multi-channel mapping required')
    events.sort(key=lambda e:e[2])
    if len({e[2] for e in events})!=len(events):raise ValueError('duplicate business sequence')
    if any(b[0]<a[0] for a,b in zip(events,events[1:])):raise ValueError('timestamp reverses business sequence')
    book=OrderBook(int(symbol),retain_trades=False)
    stats=defaultdict(int)
    keys={(int(r.Channel),int(r.OrderOriNo)):i for i,r in enumerate(add.itertuples())}
    features=np.full((len(add),5),np.nan)
    for event in events:
        time,ch,seq,kind,row=event
        if kind=='ord' and row['OrderKind']==65:
            i=keys.get((ch,int(row['OrderOriNo'])))
            if i is not None:
                side=chr(row['FunctionCode']); p=int(round(float(row['Price'])*100))
                bid=book._best('B'); ask=book._best('S'); own=bid if side=='B' else ask
                prices=book.prices[side]
                insertion=bisect_left(prices,p)
                rank=(len(prices)-insertion if p in book.levels[side] else len(prices)-insertion+1) if side=='B' else insertion+1
                distance=(bid-p if side=='B' else p-ask) if own is not None else np.nan
                features[i]=[bid if bid is not None else np.nan,ask if ask is not None else np.nan,
                             distance,rank,book.levels[side].get(p,0)]
        apply_market_event(book,event,stats)
    return pd.DataFrame(features,columns=['entry_bid','entry_ask','distance_ticks','rank','ahead_qty'])


def early_outcomes(add, orders, trades):
    keys=['Channel','OrderOriNo']
    lookup=add[keys+['BizIndex','t']].rename(columns={'BizIndex':'add_seq','t':'add_t'})
    legs=[]
    for col in ['BidOrder','AskOrder']:
        legs.append(trades[['Channel',col,'BizIndex','Time','Volume']].rename(columns={col:'OrderOriNo'}))
    fill=pd.concat(legs,ignore_index=True).merge(lookup,on=keys)
    fill['elapsed']=ms(fill.Time)-fill.add_t
    fill=fill[(fill.BizIndex>fill.add_seq)&(fill.elapsed>=0)]
    cancel=orders[orders.OrderKind==68][keys+['BizIndex','Time','Volume']].merge(lookup,on=keys)
    cancel['elapsed']=ms(cancel.Time)-cancel.add_t
    if (cancel.elapsed<0).any() or (cancel.BizIndex<=cancel.add_seq).any():
        raise ValueError('cancellation precedes ADD')
    for horizon in [1000,3000,10000]:
        for label,events in [('fill',fill),('cancel',cancel)]:
            quantities=events[events.elapsed<=horizon].groupby(keys).Volume.sum()
            add=add.join(quantities.rename(f'{label}{horizon}'),on=keys)
            add[f'{label}{horizon}']=add[f'{label}{horizon}'].fillna(0).astype('int64')
        if ((add[f'fill{horizon}']+add[f'cancel{horizon}'])>add.Volume).any():
            raise ValueError('early reduction exceeds observable ADD')
    return add


def pair_candidates(add):
    """Exact-time/channel, adjacent original IDs, opposite sides, greedy disjoint.

    Adjacency is a candidate mechanism signature, not common-account evidence.
    No same-quantity, lifetime, or fill filter in initial candidate selection.
    """
    x=add[['Channel','OrderOriNo','Time','side','BizIndex','original_qty','price_cents','t']].copy()
    x['idx']=np.arange(len(x)); y=x.copy(); y['OrderOriNo']-=1
    joined=x.merge(y,on=['Channel','OrderOriNo','Time'],suffixes=('_a','_b'))
    joined=joined[joined.side_a!=joined.side_b].sort_values(['Time','BizIndex_a'])
    used=set(); rows=[]
    for r in joined.itertuples():
        if r.idx_a in used or r.idx_b in used:continue
        used.update([r.idx_a,r.idx_b])
        b=int(r.idx_a if r.side_a=='B' else r.idx_b); s=int(r.idx_a if r.side_a=='S' else r.idx_b)
        rb,rs=add.iloc[b],add.iloc[s]
        rows.append(dict(b=b,s=s,t=int(rb.t),channel=int(rb.Channel),buy_oid=int(rb.OrderOriNo),sell_oid=int(rs.OrderOriNo),
                         buy_qty=int(rb.original_qty),sell_qty=int(rs.original_qty),buy_price=int(rb.price_cents),sell_price=int(rs.price_cents),
                         width=int(rs.price_cents-rb.price_cents),block=int(rb.t)//1800000))
    p=pd.DataFrame(rows)
    if p.empty:return p
    p['linked']=False;p['price_moved']=False;p['gap_ms']=np.nan
    for _,g in p.groupby(['channel','buy_qty','sell_qty','block'],sort=False):
        ids=g.sort_values('t',kind='stable').index.to_numpy();times=p.loc[ids,'t'].to_numpy()
        for k in range(3,len(ids)):
            selected=ids[k-3:k+1]; gaps=np.diff(times[k-3:k+1]);mean=gaps.mean()
            width=p.loc[selected,'width'].to_numpy()
            linked=(p.loc[ids[k],'buy_qty']==p.loc[ids[k],'sell_qty'] and gaps.min()>0 and
                    500<=mean<=60000 and gaps.std()/mean<=.03 and width.max()-width.min()<=1 and width.min()>0)
            p.loc[ids[k],'linked']=linked
            p.loc[ids[k],'price_moved']=p.loc[selected,'buy_price'].nunique()>1
            p.loc[ids[k],'gap_ms']=gaps[-1]
    return p


def enrich_pairs(p,add,symbol):
    if p.empty:return p
    target=CASH.get(int(symbol))
    p['symbol']=int(symbol);p['cash_scope']=target is not None
    # integer fen exact ceiling, prior fills are known by current ADD publication
    p['cash']=False if target is None else p.buy_qty.eq((target*100+p.buy_price-1)//p.buy_price)
    p['joint']=p.linked&p.cash
    p['half']=np.where(p.t<43200000,'morning','afternoon')
    p['clock']=p.t.map(clock)
    for side in ['b','s']:
        frame=add.iloc[p[side].to_numpy()].reset_index(drop=True)
        for col in ['Volume','pre_add_filled','rank','distance_ticks','ahead_qty','last_cancel_t','post_add_filled','cancelled','final_remaining']:
            p[f'{side}_{col}']=frame[col].to_numpy()
        for h in [1000,3000,10000]:
            for kind in ['fill','cancel']:
                p[f'{side}_{kind}{h}']=frame[f'{kind}{h}'].to_numpy()
    p['both_full_cancel_no_fill']=(p.b_cancelled.eq(p.b_Volume)&p.s_cancelled.eq(p.s_Volume)&p.b_post_add_filled.eq(0)&p.s_post_add_filled.eq(0))
    p['cancel_time_diff_ms']=(p.b_last_cancel_t-p.s_last_cancel_t).abs()
    for h in [1000,3000,10000]:
        p[f'both_cancel{h}']=p.both_full_cancel_no_fill&((p.b_last_cancel_t-p.t)<=h)&((p.s_last_cancel_t-p.t)<=h)
        p[f'common_cancel{h}']=p[f'both_cancel{h}']&(p.cancel_time_diff_ms<=20)
    p['either_top10']=(p.b_rank<=10)|(p.s_rank<=10)
    p['both_top10']=(p.b_rank<=10)&(p.s_rank<=10)
    return p


def describe(p):
    p=p[((p.t<41400000)&(p.t<=41390000))|((p.t>=46800000)&(p.t<=53810000))]
    if p.empty:return {'pairs':0}
    denominator=p.b_Volume+p.s_Volume
    out={'pairs':len(p),'stocks':int(p.symbol.nunique()),'same_qty_fraction':float(p.buy_qty.eq(p.sell_qty).mean()),
         'both_top10_fraction':float(p.both_top10.mean()),'either_top10_fraction':float(p.either_top10.mean()),
         'median_buy_rank':float(p.b_rank.median()),'median_sell_rank':float(p.s_rank.median()),
         'median_buy_distance_ticks':float(p.b_distance_ticks.median()),'median_sell_distance_ticks':float(p.s_distance_ticks.median()),
         'price_moved_fraction':float(p.price_moved.mean()),'both_full_cancel_no_postfill_fraction':float(p.both_full_cancel_no_fill.mean())}
    for h in [1000,3000,10000]:
        out[str(h)]={'mean_fill_fraction':float(((p[f'b_fill{h}']+p[f's_fill{h}'])/denominator).mean()),
                     'mean_cancel_fraction':float(((p[f'b_cancel{h}']+p[f's_cancel{h}'])/denominator).mean()),
                     'any_fill_probability':float(((p[f'b_fill{h}']+p[f's_fill{h}'])>0).mean()),
                     'both_full_cancel_probability':float(p[f'both_cancel{h}'].mean()),
                     'common_cancel_probability':float(p[f'common_cancel{h}'].mean())}
    return out


def match_controls(all_add, exact_distance=False, exact_size=False):
    """ATT descriptive reweighting, stock/side/clock/depth/spread/size strata.

    Compare joint pair legs with other ADDs in the five cash-target stocks.
    Outcomes are observable ADD remainder reductions, not pre-ADD executions.
    """
    x=all_add[all_add.symbol.isin(CASH)].copy()
    x=x[((x.t<41400000)&(x.t<=41390000))|((x.t>=46800000)&(x.t<=53810000))]
    x['rank_bin']=np.select([x['rank']<=1,x['rank']<=5,x['rank']<=10,x['rank']<=20],[1,2,3,4],default=5)
    spread=x.entry_ask-x.entry_bid
    x['spread_bin']=np.select([spread==1,spread==2,spread.between(3,5),spread>=6],[1,2,3,4],default=0)
    x['size_bin']=np.floor(np.log2(x.Volume)).astype(int)
    x['block5']=x.t//300000
    x['half']=np.where(x.t<43200000,'morning','afternoon')
    cols=['symbol','side','block5','rank_bin','spread_bin','size_bin']
    if exact_distance:
        x=x[x.distance_ticks.notna()].copy()
        x['exact_distance']=x.distance_ticks.astype(int)
        cols=['symbol','side','block5','exact_distance','spread_bin','size_bin']
    if exact_size:
        cols=[c for c in cols if c!='size_bin']+['Volume']
    metrics=[]
    for h in [1000,3000,10000]:
        x[f'fill_frac{h}']=x[f'fill{h}']/x.Volume
        x[f'cancel_frac{h}']=x[f'cancel{h}']/x.Volume
        x[f'any_fill{h}']=(x[f'fill{h}']>0).astype(float)
        metrics += [f'fill_frac{h}',f'cancel_frac{h}',f'any_fill{h}']
    output={}
    for name,subset in [('all',x),('morning',x[x.half=='morning']),('afternoon',x[x.half=='afternoon'])]:
        treat=subset[subset.joint];control=subset[~subset.is_pair]
        t=treat.groupby(cols)[metrics].agg(['mean','size'])
        c=control.groupby(cols)[metrics].agg(['mean','size'])
        common=t.index.intersection(c.index);t=t.loc[common];c=c.loc[common]
        mask=c[(metrics[0],'size')]>=5;t=t[mask];c=c[mask]
        weight=t[(metrics[0],'size')]
        result={'eligible_treatment_legs':len(treat),'matched_treatment_legs':int(weight.sum()),'strata':len(t),
                'distinct_control_legs':int(c[(metrics[0],'size')].sum()),'metrics':{},'stock_differences':[]}
        for metric in metrics:
            if len(t):
                a=float(np.average(t[(metric,'mean')],weights=weight));b=float(np.average(c[(metric,'mean')],weights=weight))
                result['metrics'][metric]={'joint':a,'control_reweighted':b,'difference':a-b}
        for symbol in sorted(set(t.index.get_level_values('symbol'))):
            a=t.xs(symbol);b=c.xs(symbol);w=a[(metrics[0],'size')]
            result['stock_differences'].append({'symbol':int(symbol),'matched_legs':int(w.sum()),
                'cancel3_difference':float(np.average(a[('cancel_frac3000','mean')]-b[('cancel_frac3000','mean')],weights=w)),
                'fill3_difference':float(np.average(a[('fill_frac3000','mean')]-b[('fill_frac3000','mean')],weights=w))})
        output[name]=result
    return output


def renewal_description(p):
    """Descriptive past-pair cancellation vs new pair timestamp; no selection."""
    x=p.sort_values(['symbol','channel','buy_qty','sell_qty','block','t']).copy()
    grouped=x.groupby(['symbol','channel','buy_qty','sell_qty','block'])
    for col in ['b_last_cancel_t','s_last_cancel_t','both_full_cancel_no_fill','t']:
        x['previous_'+col]=grouped[col].shift(1)
    x=x[x.joint & (((x.t<41400000)&(x.t<=41390000))|((x.t>=46800000)&(x.t<=53810000)))]
    previous=x.previous_both_full_cancel_no_fill.eq(True)
    out={'joint_pairs':len(x),'previous_candidate_in_group':int(x.previous_t.notna().sum()),'by_tolerance_ms':{}}
    for tol in [0,20,100]:
        a=previous&((x.t-x.previous_b_last_cancel_t).abs()<=tol)&((x.t-x.previous_s_last_cancel_t).abs()<=tol)
        out['by_tolerance_ms'][str(tol)]={'pairs':int(a.sum()),'fraction_all_joint':float(a.mean())}
    out['post_add_reduction_within_1sec_legs']=int(((x.b_fill1000+x.b_cancel1000)>0).sum()+((x.s_fill1000+x.s_cancel1000)>0).sum())
    return out


def run(refresh=False):
    OUT.mkdir(parents=True,exist_ok=True)
    symbols=pd.read_csv(ROOT/'reports/order_patterns/stocks.csv').symbol.tolist()
    pairs=[];frames=[];stock_rows=[]
    for symbol in symbols:
        checkpoint=OUT/f'checkpoint_{symbol}.json'
        if checkpoint.exists() and not refresh:
            stock_rows.append(json.loads(checkpoint.read_text(encoding='utf-8')))
            saved=OUT/f'pairs_{symbol}.parquet'
            if saved.exists():pairs.append(pd.read_parquet(saved))
            saved=OUT/f'controls_{symbol}.parquet'
            if saved.exists():frames.append(pd.read_parquet(saved))
            print('reused '+str(symbol),flush=True)
            continue
        od=pq.read_table(DATA/'ord_20260923.parquet',filters=[('Symbol','=',int(symbol))],columns=['Symbol','Time','BizIndex','Channel','OrderOriNo','FunctionCode','OrderKind','Price','Volume']).to_pandas()
        ex=pq.read_table(DATA/'exe_20260923.parquet',filters=[('Symbol','=',int(symbol))],columns=['Symbol','Time','BizIndex','Channel','BidOrder','AskOrder','BSFlag','Price','Volume']).to_pandas()
        ex=ex[ex.Time<=150000000]
        add=reconstruct(od,ex);add=add[session(add.t)].sort_values(['t','BizIndex'],kind='stable').reset_index(drop=True)
        add=early_outcomes(add,od,ex)
        entry=entry_features(symbol,add,od,ex);add=pd.concat([add.reset_index(drop=True),entry],axis=1)
        p=enrich_pairs(pair_candidates(add),add,symbol)
        add['symbol']=int(symbol);add['joint']=False;add['is_pair']=False
        if len(p):
            add.loc[np.r_[p.b.to_numpy(),p.s.to_numpy()],'is_pair']=True
            joint=p[p.joint];add.loc[np.r_[joint.b.to_numpy(),joint.s.to_numpy()],'joint']=True
            pairs.append(p)
        cols=['symbol','side','Channel','OrderOriNo','t','Volume','rank','entry_bid','entry_ask','distance_ticks','joint','is_pair']
        cols += [f'{k}{h}' for h in [1000,3000,10000] for k in ['fill','cancel']]
        if symbol in CASH:
            frames.append(add[cols]);add[cols].to_parquet(OUT/f'controls_{symbol}.parquet',index=False)
        stock_rows.append({'symbol':int(symbol),'adds':len(add),'pairs':len(p),'linked':int(p.linked.sum()) if len(p) else 0,
                           'joint':int(p.joint.sum()) if len(p) else 0})
        if len(p):p.to_parquet(OUT/f'pairs_{symbol}.parquet',index=False)
        checkpoint.write_text(json.dumps(stock_rows[-1]),encoding='utf-8')
        print(json.dumps(stock_rows[-1]),flush=True)
    p=pd.concat(pairs,ignore_index=True)
    all_add=pd.concat(frames,ignore_index=True)
    groups={'all_candidates':p,'linked':p[p.linked], 'cash_scope_candidates':p[p.cash_scope],
            'cash_only':p[p.cash_scope&p.cash&~p.linked], 'linked_without_cash':p[p.cash_scope&p.linked&~p.cash],
            'joint':p[p.joint], 'joint_morning':p[p.joint&(p.half=='morning')], 'joint_afternoon':p[p.joint&(p.half=='afternoon')]}
    summary={'date':'2026-09-23','rules':{'candidate':'same channel, exact timestamp, adjacent original IDs, opposite sides; greedy disjoint',
             'linked':'same qty on both sides; current plus previous three candidates within same 30min and qty group; three gaps 0.5-60s, CV<=3%, width range<=1cent and positive',
             'cash':'known original buy quantity equals exact ceil(previously chosen cash target/buy price)',
             'outcomes':'ADD remainder only, 1/3/10s after publication; last 10s before session ends excluded',
             'common_cancel':'both entire ADD remainders cancelled without post-ADD fill, cancellation timestamps differ <=20ms',
             'control':'other non-pair ADDs, same stock/side/5min/depth/spread/size strata, >=5 control legs per stratum',
             'warning':'same-day exploratory targets and serial dependent observations, not participant identity or causal evidence'},
             'stock_results':stock_rows,'groups':{k:describe(g) for k,g in groups.items()},
             'cash_targets_yuan':CASH,'matched':match_controls(all_add),'matched_exact_distance':match_controls(all_add,True),
             'matched_exact_distance_size':match_controls(all_add,True,True),'renewal':renewal_description(p)}
    summary['joint_by_stock']=[{'symbol':int(s),**describe(g)} for s,g in p[p.joint].groupby('symbol')]
    eligible=p[p.joint & (((p.t<41400000)&(p.t<=41390000))|((p.t>=46800000)&(p.t<=53810000)))]
    summary['common_cancel_sensitivity']={str(t):float((eligible.both_cancel10000&(eligible.cancel_time_diff_ms<=t)).mean()) for t in [0,20,100]}
    summary['common_cancel_horizon_sensitivity']={str(h):float((eligible.both_full_cancel_no_fill &
        ((eligible.b_last_cancel_t-eligible.t)<=h)&((eligible.s_last_cancel_t-eligible.t)<=h)&
        (eligible.cancel_time_diff_ms<=20)).mean()) for h in [3000,3010,3100,10000]}
    p.to_csv(OUT/'pairs.csv',index=False)
    pd.DataFrame(stock_rows).to_csv(OUT/'stocks.csv',index=False)
    # Every pair index maps to stock-local continuous ADD row; raw identity fields are also saved.
    p[p.joint].to_csv(OUT/'joint_pairs.csv',index=False)
    (OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps(summary['groups']['joint'],indent=2),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--refresh',action='store_true',help='rebuild stage checkpoints after changing rules or input')
    run(parser.parse_args().refresh)
