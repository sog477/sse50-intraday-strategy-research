"""Single-day order-behaviour evidence, never investor identity classification.

Run with pandas/numpy/pyarrow. Plotting is optional in a separate runtime.
All scans/thresholds are explicit; permutations are selection-bias diagnostics.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow.parquet as pq


def ms(raw):
    x = np.asarray(raw, dtype=np.int64)
    return (x // 10000000 * 3600 + x // 100000 % 100 * 60 + x // 1000 % 100) * 1000 + x % 1000


def clock(t):
    t = int(t)
    return f'{t//3600000:02d}:{t//60000%60:02d}:{t//1000%60:02d}.{t%1000:03d}'


def session(t):
    return ((t >= 34200000) & (t < 41400000)) | ((t >= 46800000) & (t < 53820000))


def reconstruct(orders, trades):
    """For ADD-backed orders only: original size = ADD remainder + pre-ADD fills.

    Fully executed aggressors with no ADD have no observable original limit.
    Those orders are intentionally outside priced-ADD studies.
    """
    add = orders[orders.OrderKind == 65].copy()
    if add.duplicated(['Channel', 'OrderOriNo']).any():
        raise ValueError('duplicate ADD identity')
    add['t'] = ms(add.Time)
    add['price_cents'] = np.rint(add.Price.astype(float) * 100).astype(int)
    add['side'] = add.FunctionCode.map({66: 'B', 83: 'S'})
    key = ['Channel', 'OrderOriNo']
    legs = []
    for col, side in [('BidOrder', 'B'), ('AskOrder', 'S')]:
        x = trades[['Channel', col, 'BizIndex', 'Time', 'Volume']].rename(columns={col:'OrderOriNo'}).copy()
        x['side'] = side
        legs.append(x)
    legs = pd.concat(legs, ignore_index=True)
    linked = legs.merge(add[key + ['BizIndex', 'side']].rename(columns={'BizIndex':'add_seq', 'side':'add_side'}), on=key)
    if (linked.side != linked.add_side).any():
        raise ValueError('order side mismatch')
    pre = linked[linked.BizIndex < linked.add_seq].groupby(key).Volume.sum().rename('pre_add_filled')
    post = linked[linked.BizIndex > linked.add_seq].groupby(key).Volume.sum().rename('post_add_filled')
    cancels = orders[orders.OrderKind == 68].copy()
    cancels['cancel_t'] = ms(cancels.Time)
    cancel = cancels.groupby(key).agg(cancelled=('Volume','sum'), last_cancel_t=('cancel_t','max'))
    add = add.join(pre,on=key).join(post,on=key).join(cancel,on=key)
    for col in ['pre_add_filled','post_add_filled','cancelled']:
        add[col] = add[col].fillna(0).astype(np.int64)
    add['original_qty'] = add.Volume + add.pre_add_filled
    add['final_remaining'] = add.Volume - add.post_add_filled - add.cancelled
    if (add.final_remaining < 0).any():
        raise ValueError('quantity exceeded ADD remainder')
    add['cancel_lifetime_ms'] = add.last_cancel_t - add.t
    add['quick_cancel'] = (add.cancelled == add.Volume) & (add.post_add_filled == 0) & (add.pre_add_filled == 0) & (add.cancel_lifetime_ms <= 1000)
    return add


def periodic_windows(t, qty, side, block, retain=False):
    """Eight consecutive equal-size same-side ADDs in a 30-min block.

    Seven gaps: mean 0.5--60 seconds, CV <= 3%. Price can move.
    This detects public stream motifs, not same-trader child orders.
    """
    frame = pd.DataFrame({'t':t,'qty':qty,'side':side,'block':block,'row':np.arange(len(t))})
    result, count = [], 0
    for (s,b,q), g in frame.groupby(['side','block','qty'], sort=False):
        if len(g)<8:
            continue
        ids = g.sort_values('t',kind='stable').row.to_numpy()
        times = np.asarray(t)[ids]
        gaps = np.diff(times).astype(float)
        w = np.lib.stride_tricks.sliding_window_view(gaps,7)
        means = w.mean(axis=1)
        cvs = w.std(axis=1) / np.maximum(means,1)
        hits = np.flatnonzero((means >= 500) & (means <= 60000) & (cvs <= .03) & (w.min(axis=1)>0))
        count += len(hits)
        if retain:
            last = -8
            for h in hits:
                if h < last + 8:
                    continue
                result.append({'indices':ids[h:h+8].tolist(),'quantity':int(q),'side':s,'block':int(b),
                               'start':int(times[h]),'mean_gap_ms':float(means[h]),'gap_cv':float(cvs[h])})
                last = h
    return count,result


def quote_match(add, snap, lag):
    valid = snap[session(snap.t) & (snap.BidPrice1 > 0) & (snap.AskPrice1 > snap.BidPrice1)].sort_values('t')
    times = valid.t.to_numpy()
    idx = np.searchsorted(times, add.t.to_numpy()-lag, side='right')-1
    okay = idx >= 0
    ix = np.maximum(idx,0)
    okay &= add.t.to_numpy()-lag-times[ix] <= 4000
    out = add[okay].copy()
    refs = valid.iloc[ix[okay]]
    b = np.rint(refs.BidPrice1.to_numpy()*100).astype(int)
    a = np.rint(refs.AskPrice1.to_numpy()*100).astype(int)
    out['best_same'] = np.where(out.side=='B',b,a)
    out['distance_ticks'] = np.where(out.side=='B',out.best_same-out.price_cents,out.price_cents-out.best_same)
    out['clock5'] = out.t // 300000
    out['yuan_bin'] = out.price_cents // 100
    out = out[out.distance_ticks.between(0,20)]
    return out, valid


def exposure_control(add,snap):
    """Reweight available tick endings by observed order-distance/time distribution.

    Same symbol, side, 5-min block, exact quote distance (0--20 ticks), and
    integer-yuan bin. Need >=5 snapshots and >=2 available tail values.
    Not a causal identity test; stale quote/tick exposure is a limitation.
    """
    keys = ['side','clock5','distance_ticks','yuan_bin']
    obs = add.groupby(keys).agg(n=('price_cents','size'), observed_round=('tail0','mean'),
                                observed_priority=('priority_tail','mean'))
    opportunities = []
    for side,col,sign,prior in [('B','BidPrice1',-1,1),('S','AskPrice1',1,9)]:
        best = np.rint(snap[col].to_numpy()*100).astype(int)
        for d in range(21):
            p = best+sign*d
            opportunities.append(pd.DataFrame({'side':side,'clock5':snap.t.to_numpy()//300000,
                'distance_ticks':d,'yuan_bin':p//100,'round':p%10==0,'priority':p%10==prior,'tail':p%10}))
    opp = pd.concat(opportunities,ignore_index=True).groupby(keys).agg(exposure_n=('round','size'),
        expected_round=('round','mean'),expected_priority=('priority','mean'), tail_variety=('tail','nunique'))
    paired = obs.join(opp,how='inner')
    paired = paired[(paired.exposure_n>=5)&(paired.tail_variety>=2)]
    if paired.empty:
        return paired,{}
    result = {'eligible_orders':int(paired.n.sum()),'strata':len(paired)}
    for name in ['round','priority']:
        for typ in ['observed','expected']:
            result[f'{typ}_{name}'] = float(np.average(paired[f'{typ}_{name}'],weights=paired.n))
        result[f'excess_{name}_pp'] = 100*(result[f'observed_{name}']-result[f'expected_{name}'])
    return paired,result


def verify_displayed_cases(data:Path,out:Path,date:str):
    """Independent raw-row check of displayed examples, selected post scan.

    These examples are explanatory, not held-out statistical discoveries.
    """
    cases=pd.read_csv(out/'periodic_examples.csv')
    rapid=pd.read_csv(out/'rapid_cancel_examples.csv')
    selections=[(601668,cases[cases.case_id=='601668-14'].original_order_id.tolist(),'601668-14'),
                (688981,cases[cases.case_id=='688981-102'].original_order_id.tolist(),'688981-102'),
                (601328,rapid[rapid.cluster=='601328:B:750:400:0'].original_order_id.tolist(),'601328-fast')]
    records=[]
    for symbol,ids,label in selections:
        orders=pq.read_table(data/f'ord_{date}.parquet',filters=[('Symbol','=',symbol)]).to_pandas()
        trades=pq.read_table(data/f'exe_{date}.parquet',filters=[('Symbol','=',symbol)]).to_pandas()
        for oid in ids:
            rows=orders[orders.OrderOriNo==oid];adds=rows[rows.OrderKind==65];cancels=rows[rows.OrderKind==68]
            if len(adds)!=1:raise ValueError('displayed case not unique')
            channel=int(adds.Channel.iloc[0])
            legs=trades[(trades.Channel==channel)&((trades.BidOrder==oid)|(trades.AskOrder==oid))]
            if len(legs) or int(cancels.Volume.sum())!=int(adds.Volume.iloc[0]):
                raise ValueError('displayed fully cancelled case has execution/quantity inconsistency')
            records.append({'case':label,'symbol':symbol,'channel':channel,'original_order_id':int(oid),
                'add_seq':int(adds.BizIndex.iloc[0]),'add_time':int(adds.Time.iloc[0]),
                'cancel_seq':int(cancels.BizIndex.max()),'cancel_time':int(cancels.Time.max()),
                'add_remaining':int(adds.Volume.iloc[0]),'cancelled':int(cancels.Volume.sum()),'linked_trade_rows':len(legs)})
    result={'verification':'direct raw parquet extraction, displayed orders: unique ADD, full cancel, no bid or ask execution links',
            'selection':'post-scan explanatory examples, not independent identity labels','orders':records}
    (out/'selected_case_verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')


def run(data:Path,out:Path,null_runs:int):
    out.mkdir(parents=True,exist_ok=True)
    date = next(data.glob('ord_*.parquet')).stem.split('_')[1]
    od = pq.read_table(data/f'ord_{date}.parquet').to_pandas()
    ex = pq.read_table(data/f'exe_{date}.parquet',columns=['Symbol','Time','Channel','BizIndex','BidOrder','AskOrder','Volume']).to_pandas()
    ex = ex[ex.Time<=150000000]
    sn = pq.read_table(data/f'snp_{date}.parquet',columns=['Symbol','Time','BidPrice1','AskPrice1']).to_pandas()
    sn['t'] = ms(sn.Time)
    rng = np.random.default_rng(20260923)
    stocks, tails, controls, periodic, details, rapid, lifecycle, size_rows, strata_rows = [],[],[],[],[],[],[],[],[]
    for symbol in sorted(od.Symbol.unique()):
        raw = od[od.Symbol==symbol]
        add = reconstruct(raw,ex[ex.Symbol==symbol])
        stocks.append({'symbol':int(symbol),'adds':len(add),'pre_add_qty_changed':int((add.pre_add_filled>0).sum()),
                       'full_cancel_without_postfill':int(((add.cancelled==add.Volume)&(add.post_add_filled==0)).sum()),
                       'negative_remaining':int((add.final_remaining<0).sum())})
        add = add[session(add.t)].sort_values(['t','BizIndex'],kind='stable').reset_index(drop=True)
        add['tail0'] = add.price_cents%10==0
        add['priority_tail'] = np.where(add.side=='B',add.price_cents%10==1,add.price_cents%10==9)
        for (side,tail),g in add.groupby(['side',add.price_cents%10]):
            tails.append({'symbol':int(symbol),'side':side,'tail':int(tail),'orders':len(g),'shares':int(g.original_qty.sum())})
        for name,mask in [('size100',add.original_qty==100),('multiple100',add.original_qty%100==0),
                          ('multiple1000',add.original_qty%1000==0),('multiple10000',add.original_qty%10000==0),
                          ('not_multiple100',add.original_qty%100!=0)]:
            size_rows.append({'symbol':int(symbol),'feature':name,'n':int(mask.sum()),'total':len(add)})
        for label,mask in [('tail0',add.tail0),('priority_tail',add.priority_tail),('other',~add.tail0&~add.priority_tail)]:
            g=add[mask]
            lifecycle.append({'symbol':int(symbol),'group':label,'n':len(g),'quick_cancel_fraction':float(g.quick_cancel.mean()),
                              'preadd_filled_fraction':float((g.pre_add_filled>0).mean()),'size100_fraction':float((g.original_qty==100).mean()),
                              'integer_yuan_fraction':float((g.price_cents%100==0).mean())})
        sp = sn[sn.Symbol==symbol]
        for lag in [0,1000,2000]:
            matched,quotes=quote_match(add,sp,lag)
            p,res = exposure_control(matched,quotes)
            controls.append({'symbol':int(symbol),'lag_ms':lag,**res})
            if lag==1000 and not p.empty:
                p=p.reset_index();p['symbol']=int(symbol);strata_rows.append(p)
        block=add.t.to_numpy()//1800000
        qty=add.original_qty.to_numpy(); side=add.side.to_numpy(); time=add.t.to_numpy()
        n,cases=periodic_windows(time,qty,side,block,retain=True)
        null=[]
        groups=add.groupby(['side',add.t//1800000],sort=False).indices.values()
        for _ in range(null_runs):
            shuffled=qty.copy()
            for ids in groups:
                shuffled[ids]=rng.permutation(shuffled[ids])
            null.append(periodic_windows(time,shuffled,side,block)[0])
        periodic.append({'symbol':int(symbol),'windows':n,'nonoverlap_examples':len(cases),
                         'null_mean':float(np.mean(null)),'null_max':int(max(null)),'null_runs':null_runs})
        # Keep every non-overlapping qualifying case; high counts are not hidden.
        for ci,case in enumerate(cases):
            ids=case.pop('indices');caseid=f'{symbol}-{ci+1}'
            for j,idx in enumerate(ids):
                row=add.iloc[idx]
                details.append({'case_id':caseid,'symbol':int(symbol),'position':j+1,'time':clock(row.t),
                    'raw_time':int(row.Time),'channel':int(row.Channel),'original_order_id':int(row.OrderOriNo),
                    'biz_index':int(row.BizIndex),'side':row.side,'price':round(row.price_cents/100,2),
                    'original_qty':int(row.original_qty),'add_remaining':int(row.Volume),
                    'pre_add_filled':int(row.pre_add_filled),'gap_ms':0 if j==0 else int(row.t-add.iloc[ids[j-1]].t),
                    'mean_gap_ms':case['mean_gap_ms'],'gap_cv':case['gap_cv'],'quick_cancel':bool(row.quick_cancel),
                    'cancel_lifetime_ms':None if pd.isna(row.cancel_lifetime_ms) else int(row.cancel_lifetime_ms),
                    'cancelled':int(row.cancelled),'post_add_filled':int(row.post_add_filled)})
        # Clusters of >=8 fully cancelled ADDs, same price/side/size, <=30s span.
        q=add[add.quick_cancel]
        for (s,p,quantity),g in q.groupby(['side','price_cents','original_qty']):
            if len(g)<8: continue
            g=g.sort_values('t'); arr=g.t.to_numpy(); ids=g.index.to_numpy(); last=-8
            for j in np.flatnonzero(arr[7:]-arr[:-7]<=30000):
                if j<last+8 or len(np.unique(arr[j:j+8]))<8:continue
                last=j
                for k,idx in enumerate(ids[j:j+8]):
                    row=add.loc[idx]
                    rapid.append({'symbol':int(symbol),'cluster':f'{symbol}:{s}:{p}:{quantity}:{j}',
                        'position':k+1,'time':clock(row.t),'raw_time':int(row.Time),'channel':int(row.Channel),
                        'original_order_id':int(row.OrderOriNo),'biz_index':int(row.BizIndex),'side':s,'price':p/100,
                        'original_qty':int(quantity),'lifetime_ms':int(row.cancel_lifetime_ms),'pre_add_filled':int(row.pre_add_filled)})
        print(f'{symbol}: {len(add):,} continuous ADDs, periodic windows {n}, null mean {np.mean(null):.1f}',flush=True)
    outputs={'stocks':stocks,'price_tails':tails,'exposure_controls':controls,'periodic_counts':periodic,
             'periodic_examples':details,'rapid_cancel_examples':rapid,'lifecycle_descriptive':lifecycle,'size_features':size_rows}
    for name,rows in outputs.items():pd.DataFrame(rows).to_csv(out/f'{name}.csv',index=False)
    if strata_rows:pd.concat(strata_rows).to_csv(out/'matched_strata.csv',index=False)
    detail_frame=pd.DataFrame(details)
    if not detail_frame.empty:
        detail_frame['notional_yuan']=detail_frame.original_qty*detail_frame.price
        notionals=detail_frame[detail_frame.symbol>=688000].groupby(['symbol','side']).agg(
            observations=('original_qty','size'),median_qty=('original_qty','median'),
            median_notional=('notional_yuan','median'),min_notional=('notional_yuan','min'),max_notional=('notional_yuan','max'))
        notionals.to_csv(out/'periodic_quote_notionals.csv')
    cd=pd.DataFrame(controls); valid=cd[(cd.symbol!=601166)&(cd.eligible_orders>0)]
    summary={'date':date,'stocks':len(stocks),'continuous_adds':sum(x['total'] for x in size_rows if x['feature']=='size100'),
        'pre_add_qty_changed':sum(x['pre_add_qty_changed'] for x in stocks),
        'periodic_window_total':sum(x['windows'] for x in periodic),
        'periodic_null_total_mean':sum(x['null_mean'] for x in periodic),
        'periodic_nonoverlap_cases':len(set(x['case_id'] for x in details)),
        'rapid_cancel_clusters':len(set(x['cluster'] for x in rapid)),
        'identity_identifiable':False,'quote_control_excluded_stock':601166,
        'periodic_null_runs':null_runs,'seed':20260923,'matched_controls':{}}
    if not detail_frame.empty:
        cases=detail_frame.groupby('case_id').first()
        summary['periodic_behaviour']={
            'orders_in_cases':len(detail_frame),
            'no_fills_fraction':float((detail_frame.pre_add_filled.eq(0)&detail_frame.post_add_filled.eq(0)).mean()),
            'fully_cancelled_without_fills_fraction':float((detail_frame.cancelled.eq(detail_frame.add_remaining)&
                detail_frame.pre_add_filled.eq(0)&detail_frame.post_add_filled.eq(0)).mean()),
            'mean_period_3sec_cases_fraction':float(cases.mean_gap_ms.between(2990,3010).mean()),
            'mainboard_cases':int((cases.symbol<688000).sum()),
            'morning_cases':int((cases.raw_time<120000000).sum()),'afternoon_cases':int((cases.raw_time>120000000).sum())}
    for lag,g in valid.groupby('lag_ms'):
        summary['matched_controls'][str(lag)]={'stocks':len(g),'orders':int(g.eligible_orders.sum()),
            **{c:float(g[c].mean()) for c in ['observed_round','expected_round','excess_round_pp','observed_priority','expected_priority','excess_priority_pp']},
            'round_positive_stocks':int((g.excess_round_pp>0).sum()),'priority_positive_stocks':int((g.excess_priority_pp>0).sum())}
    summary['size_equal_stock_fractions']={name:float(np.mean([x['n']/x['total'] for x in size_rows if x['feature']==name]))
        for name in sorted(set(x['feature'] for x in size_rows))}
    (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    verify_displayed_cases(data,out,date)
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--data',type=Path,default=Path('sse50_20260923'))
    p.add_argument('--out',type=Path,default=Path('reports/order_patterns'));p.add_argument('--null-runs',type=int,default=10)
    a=p.parse_args();run(a.data,a.out,a.null_runs)
