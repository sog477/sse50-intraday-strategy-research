"""Four fixed-definition single-day microstructure studies. Anonymous, zero impact.

All identification features use present/past events; future fields are outcomes.
Replacement links are offline candidate matches, never participant identities.
"""
from __future__ import annotations
import argparse, json
from bisect import bisect_left
from collections import defaultdict
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from orderbook import OrderBook, apply_market_event
from order_patterns import ms, reconstruct
from simulator import Fees

ROOT=Path(__file__).resolve().parent
DATA=ROOT/'sse50_20260923'
OUT=ROOT/'reports'/'four_studies'
SESSIONS=[(34200000,41400000),(46800000,53820000)]
VERSION=1
PLAN={
 'version':VERSION,'data_date':'2026-09-23',
 'queue':'Uniform live BBO order per side every5s; observe other reductions for1s; retain unchanged own order and continuously unchanged same-side best; first own cancellation/execution over1/3/10s; full10s window',
 'maker':'Independent min-lot BBO-tail probes each60s both sides, fixed limit for30s; tape-only and tape+new-crossing-residual scenarios; fill and1/5/30s post-fill markouts; complete60s window',
 'gaps':'Every fifth contiguous aggressor execution group; train per-stock volume Q25/Q75 in09:30-10:00, evaluate>=10:00; before-gap and exact pre/post BBO; immediate attribution separate from future drift',
 'replacement':'Full cancellation to new observable same-side/same-quantity candidate; include ADD-backed quantity repaired from pre-ADD fills and no-ADD aggressor trades; unique both ways; windows20/100/1000ms, after-only and symmetric; +60s/+300s time-shift diagnostics',
 'limitations':'Single day, repeated observations, no trader identity/receive/send/reject timestamps; hypothetical fills not live experiments; no strategy profit claim',
}

def end_of(t):return 41400000 if t<43200000 else 53820000
def in_session(t):return any(a<=t<b for a,b in SESSIONS)
def bbo(book):return book._best('B'),book._best('S')
def mid(quote):return (quote[0]+quote[1])/2 if None not in quote and quote[1]>quote[0] else np.nan
def raw_stamp(t):
 h,r=divmod(int(t),3600000);m,r=divmod(r,60000);s,u=divmod(r,1000)
 return h*10000000+m*100000+s*1000+u
def age_bin(x):return int(np.searchsorted([1000,5000,30000,300000],x,side='right'))

def prepare(symbol):
 od=pq.read_table(DATA/'ord_20260923.parquet',filters=[('Symbol','=',symbol)]).to_pandas()
 ex=pq.read_table(DATA/'exe_20260923.parquet',filters=[('Symbol','=',symbol)]).to_pandas();ex=ex[ex.Time<=150000000].copy()
 od['t']=ms(od.Time);ex['t']=ms(ex.Time)
 add=reconstruct(od,ex)
 adds=add.set_index('OrderOriNo')
 if not adds.index.is_unique:raise ValueError('duplicate original order ID')
 tradelegs=pd.concat([ex[['BidOrder','BizIndex','t','Volume']].rename(columns={'BidOrder':'oid'}),ex[['AskOrder','BizIndex','t','Volume']].rename(columns={'AskOrder':'oid'})],ignore_index=True)
 active=ex[ex.BSFlag.isin([66,83])].sort_values('BizIndex').copy()
 active['oid']=np.where(active.BSFlag.eq(66),active.BidOrder,active.AskOrder)
 active['side']=np.where(active.BSFlag.eq(66),'B','S');active['pos']=np.arange(len(active))
 active['notional']=np.rint(active.Price.astype(float)*100).astype('int64')*active.Volume
 groups=active.groupby(['oid','side'],sort=False).agg(firstseq=('BizIndex','min'),lastseq=('BizIndex','max'),t=('t','min'),last_t=('t','max'),quantity=('Volume','sum'),notional=('notional','sum'),n=('pos','size'),firstpos=('pos','min'),lastpos=('pos','max')).reset_index()
 groups=groups.sort_values('firstseq').reset_index(drop=True);groups['contiguous']=groups.n.eq(groups.lastpos-groups.firstpos+1)
 train=groups[(groups.t>=34200000)&(groups.last_t<36000000)]
 q25,q75=train.quantity.quantile([.25,.75]).tolist()
 cols_o=['Time','Channel','BizIndex','OrderOriNo','FunctionCode','OrderKind','Price','Volume']
 cols_e=['Time','Channel','BizIndex','BidOrder','AskOrder','BSFlag','Price','Volume']
 events=[(int(r['Time']),int(r['Channel']),int(r['BizIndex']),'ord',r) for r in od[cols_o].to_dict('records')]
 events += [(int(r['Time']),int(r['Channel']),int(r['BizIndex']),'exe',r) for r in ex[cols_e].to_dict('records')]
 events.sort(key=lambda r:r[2])
 if len({e[1] for e in events})!=1 or len({e[2] for e in events})!=len(events):raise ValueError('channel/sequence invalid')
 if any(b[0]<a[0] for a,b in zip(events,events[1:])):raise ValueError('time reversal')
 return od,ex,adds,tradelegs,groups,events,(q25,q75,len(train))


def run_stock(symbol):
 od,ex,adds,tradelegs,groups,events,cal=prepare(symbol)
 event_t=ms(np.array([e[0] for e in events]));event_seq=np.array([e[2] for e in events])
 entered={str(int(r.Index)):int(r.BizIndex) for r in adds.itertuples()}
 channel=events[0][1];entered={f'{channel}:{k}':v for k,v in entered.items()}
 rng=np.random.default_rng(20260923+symbol)
 book=OrderBook(symbol,retain_trades=False);stats=defaultdict(int)
 active_q={};active_probes=[];qrows=[];prows=[];fillrows=[];cancelrows=[];shocks=[]
 mt=[];mv=[];changes=defaultdict(lambda:[0,0.]);lastquote=(None,None)
 schedule=[]
 for start,end in SESSIONS:
  for t in range(start+5000,end-11000+1,5000):schedule.extend([(t,'qstart'),(t+1000,'qend')])
  for t in range(start,end-60000,60000):schedule.extend([(t,'pstart'),(t+30000,'pend')])
 schedule.sort();si=0;lastseq=-1
 selected=groups[(groups.index%5==0)&groups.contiguous&(groups.last_t-groups.t<=1000)&(groups.t>=36000000)&(groups.last_t+30000<np.where(groups.t<43200000,41400000,53820000))]
 shock_start={int(r.firstseq):r for r in selected.itertuples()};shock_end={int(r.lastseq):int(r.firstseq) for r in selected.itertuples()};pending={}

 def action(t,kind):
  nonlocal active_probes
  quote=bbo(book);m=mid(quote)
  if kind=='pend':active_probes=[p for p in active_probes if p['t']+30000>t];return
  if not np.isfinite(m):
   if kind=='qend':active_q.clear()
   return
  if kind=='qstart':
   for side,p in zip(['B','S'],quote):
    ids=[oid for oid in book.queues[side][p] if oid in book.orders]
    if not ids:continue
    i=int(rng.integers(len(ids)));oid=ids[i];o=book.orders[oid]
    front=sum(book.orders[k].remaining for k in ids[:i]);back=sum(book.orders[k].remaining for k in ids[i+1:])
    active_q[side]=dict(symbol=symbol,side=side,oid=oid,price=p,start=t,start_mid=m,qty=o.remaining,entered_seq=entered[oid],age=t-int(ms(np.array([o.entered_at]))[0]),front=front,back=back,level=front+back+o.remaining,
                        fc=0,bc=0,ft=0,bt=0,ba=0,own=False,off=False)
  elif kind=='qend':
   for side,q in active_q.items():
    o=book.orders.get(q['oid'])
    if not q['own'] and not q['off'] and o and o.remaining==q['qty'] and book._best(side)==q['price']:
     if book.levels[side][q['price']]!=q['level']-q['fc']-q['bc']-q['ft']-q['bt']+q['ba']:raise ValueError('queue exposure conservation')
     row={**q,'t':t,'decision_seq':lastseq,'spread':quote[1]-quote[0],'mid':m,'ret1':(m-q['start_mid'])/q['start_mid']*10000,'other_depth':book.levels['S' if side=='B' else 'B'][quote[1] if side=='B' else quote[0]]}
     qrows.append(row)
   active_q.clear()
  elif kind=='pstart':
   for side,p in zip(['B','S'],quote):
    bv,av=book.levels['B'][quote[0]],book.levels['S'][quote[1]]
    for model in ['tape_only','with_residual']:
     row=dict(symbol=symbol,side=side,model=model,t=t,price=p,quantity=200 if str(symbol).startswith('688') else 100,entry_mid=m,spread=quote[1]-quote[0],obi=(bv-av)/(bv+av),ahead=bv if side=='B' else av,cutoff=lastseq,filled=0,notional=0,fill_records=[])
     active_probes.append(row);prows.append(row)

 def reduce_watch(oid,quantity,cause):
  o=book.orders.get(oid)
  if o is None:return
  q=active_q.get(o.side)
  if q and q['price']==o.price:
   if oid==q['oid']:q['own']=True
   else:q[('f' if entered[oid]<q['entered_seq'] else 'b')+('c' if cause=='cancel' else 't')]+=quantity
  for p in active_probes:
   if o.side==p['side'] and o.price==p['price'] and entered[oid]<=p['cutoff']:
    p['ahead']-=quantity
    if p['ahead']<0:raise ValueError('negative virtual ahead')

 def probe_fill(p,t,seq,volume,source):
  n=min(volume,p['quantity']-p['filled'])
  if n<=0:return
  p['filled']+=n;p['notional']+=n*p['price']
  r=dict(t=t,seq=seq,qty=n,price=p['price'],side=p['side'],source=source)
  p['fill_records'].append(len(fillrows));fillrows.append(r)

 for j,event in enumerate(events):
  raw,ch,seq,kind,r=event;t=int(event_t[j])
  while si<len(schedule) and schedule[si][0]<t:
   action(*schedule[si]);si+=1
  quote=bbo(book);m=mid(quote);cont=in_session(t)
  if seq in shock_start and np.isfinite(m):
   g=shock_start[seq];side=g.side;passive='S' if side=='B' else 'B';prices=book.prices[passive];ranked=prices[:2] if passive=='S' else prices[-2:][::-1]
   if len(ranked)==2:
    pending[seq]=dict(symbol=symbol,t=t,end_t=int(g.last_t),side=side,first_seq=seq,last_seq=int(g.lastseq),active_oid=int(g.oid),quantity=int(g.quantity),gap=abs(ranked[1]-ranked[0]),best_depth=book.levels[passive][ranked[0]],pre_best=ranked[0],pre_mid=m,spread=quote[1]-quote[0],q25=cal[0],q75=cal[1])
  if kind=='exe':
   flag=r['BSFlag'];passive='S' if flag==66 else 'B' if flag==83 else None
   if cont and passive:
    passive_oid=f"{ch}:{r['AskOrder'] if passive=='S' else r['BidOrder']}";price=int(round(float(r['Price'])*100));qty=int(r['Volume'])
    for p in active_probes:
     if p['filled']>=p['quantity'] or p['side']!=passive:continue
     through=price<p['price'] if passive=='B' else price>p['price']
     old=book.orders.get(passive_oid)
     behind=(old is not None and old.price==p['price'] and entered[passive_oid]>p['cutoff'])
     if through or (price==p['price'] and p['ahead']==0 and behind):probe_fill(p,t,seq,qty,'tape')
   for oid in [f"{ch}:{r['BidOrder']}",f"{ch}:{r['AskOrder']}"]:reduce_watch(oid,int(r['Volume']),'trade')
  else:
   oid=f"{ch}:{r['OrderOriNo']}"
   if r['OrderKind']==68:
    o=book.orders.get(oid)
    if cont and o is not None and np.isfinite(m) and o.remaining==r['Volume']:
     prices=book.prices[o.side];ix=bisect_left(prices,o.price);rank=len(prices)-ix if o.side=='B' else ix+1
     cancelrows.append(dict(symbol=symbol,oid=int(r['OrderOriNo']),seq=seq,t=t,side=o.side,quantity=int(r['Volume']),price=o.price,rank=rank,distance=(quote[0]-o.price if o.side=='B' else o.price-quote[1])))
    reduce_watch(oid,int(r['Volume']),'cancel')
   elif r['OrderKind']==65:
    side=chr(r['FunctionCode']);price=int(round(float(r['Price'])*100));qty=int(r['Volume'])
    q=active_q.get(side)
    if q and price==q['price']:q['ba']+=qty
    if cont:
     for p in active_probes:
      crosses=price<=p['price'] if p['side']=='B' else price>=p['price']
      if p['model']=='with_residual' and side!=p['side'] and crosses:probe_fill(p,t,seq,qty,'new_residual')
  previous_fills=len(fillrows)
  apply_market_event(book,event,stats);after=bbo(book);am=mid(after)
  # Fill records generated in this event have no marked post-event mid yet.
  for fr in reversed(fillrows):
   if fr['seq']!=seq:break
   fr['mid_after']=am
  if after!=lastquote and np.isfinite(am):mt.append(t);mv.append(am);lastquote=after
  if cont and np.isfinite(m) and np.isfinite(am) and am!=m:
   typ='trade' if kind=='exe' else 'cancel' if r['OrderKind']==68 else 'add'
   key=f'{typ}_'+('large' if abs(am-m)>=2 else 'small');changes[key][0]+=1;changes[key][1]+=abs(am-m)
  for side,q in active_q.items():
   if book._best(side)!=q['price']:q['off']=True
  if seq in shock_end:
   initial=shock_end[seq];g=pending.pop(initial,None)
   if g is not None and np.isfinite(am):
    passive='S' if g['side']=='B' else 'B';post=book._best(passive)
    g.update(post_mid=am,impact=(am-g['pre_mid'])*(1 if g['side']=='B' else -1),depleted=(post is None or (post>g['pre_best'] if passive=='S' else post<g['pre_best'])))
    shocks.append(g)
  lastseq=seq
  if j+1==len(events) or event_t[j+1]>t:
   while si<len(schedule) and schedule[si][0]==t:action(*schedule[si]);si+=1
 while si<len(schedule):action(*schedule[si]);si+=1
 mt=np.asarray(mt);mv=np.asarray(mv)
 def future(target):
  ix=np.searchsorted(mt,target,side='right')-1
  if (ix<0).any():raise ValueError('midpoint lookup before history')
  return mv[ix]
 qframe=pd.DataFrame(qrows)
 if len(qframe):
  wanted={int(s.split(':')[1]) for s in qframe.oid}
  red=tradelegs[tradelegs.oid.isin(wanted)].copy();red['cause']='fill'
  cc=od[(od.OrderKind==68)&od.OrderOriNo.isin(wanted)][['OrderOriNo','BizIndex','t','Volume']].rename(columns={'OrderOriNo':'oid'});cc['cause']='cancel'
  red=pd.concat([red,cc]).sort_values('BizIndex');life={int(k):g for k,g in red.groupby('oid',sort=False)}
  results=[]
  for r in qframe.itertuples():
   events_o=life.get(int(r.oid.split(':')[1]));first=None
   if events_o is not None:
    pos=np.searchsorted(events_o.BizIndex.to_numpy(),r.decision_seq,side='right')
    if pos<len(events_o):first=events_o.iloc[pos]
   row={}
   for h in [1000,3000,10000]:
    row[f'cancel{h}']=int(first is not None and first.t<=r.t+h and first.cause=='cancel')
    row[f'fill{h}']=int(first is not None and first.t<=r.t+h and first.cause=='fill')
   results.append(row)
  qframe=pd.concat([qframe.reset_index(drop=True),pd.DataFrame(results)],axis=1)
 pframe=pd.DataFrame(prows)
 if len(pframe):
  pframe['signed_obi']=np.where(pframe.side.eq('B'),1,-1)*pframe.obi
  pframe['signal']=np.select([pframe.signed_obi>=.6,pframe.signed_obi<=-.6],['with','against'],default='middle')
  pframe['future30_ticks']=np.where(pframe.side.eq('B'),1,-1)*(future(pframe.t.to_numpy()+30000)-pframe.entry_mid)
  for h in [1000,5000,30000]:
   marks=[];drifts=[]
   for r in pframe.itertuples():
    fs=[fillrows[i] for i in r.fill_records]
    if not fs:marks.append(np.nan);drifts.append(np.nan);continue
    targets=np.array([f['t']+h for f in fs]);fut=future(targets);weight=np.array([f['qty'] for f in fs]);sgn=1 if r.side=='B' else -1
    marks.append(float(np.average(sgn*(fut-r.price),weights=weight)))
    drifts.append(float(np.average(sgn*(fut-np.array([f['mid_after'] for f in fs])),weights=weight)))
   pframe[f'markout{h}']=marks;pframe[f'drift{h}']=drifts
  fees=Fees();pframe['fees_cents']=[fees.total(int(r.notional),r.side)['total'] for r in pframe.itertuples()]
  pframe['entry_fee_ticks']=np.divide(pframe.fees_cents,pframe.filled,out=np.full(len(pframe),np.nan),where=pframe.filled.to_numpy()>0)
  pframe['markout30_after_entry_fee_ticks']=pframe.markout30000-pframe.entry_fee_ticks
  pframe['wait_ms']=[fillrows[r.fill_records[0]]['t']-r.t if r.fill_records else np.nan for r in pframe.itertuples()]
  pframe['fill_sources']=[','.join(sorted({fillrows[i]['source'] for i in r.fill_records})) for r in pframe.itertuples()]
  pframe=pframe.drop(columns='fill_records')
 sframe=pd.DataFrame(shocks)
 if len(sframe):
  sframe['relative_volume']=sframe.quantity/sframe.best_depth
  sframe['size']=np.select([sframe.quantity<=sframe.q25,(sframe.quantity>=sframe.q75)&(sframe.quantity>sframe.q25)],['small','large'],default='middle')
  sframe['gap_group']=np.where(sframe.gap>=2,'gap>=2','gap=1')
  for h in [1000,5000,30000]:sframe[f'drift{h}']=np.where(sframe.side.eq('B'),1,-1)*(future(sframe.end_t.to_numpy()+h)-sframe.post_mid)
  sframe['large_move']=(sframe.impact>=2).astype(int)
 replacement,new=replacements(pd.DataFrame(cancelrows),adds,tradelegs,groups,event_t,event_seq)
 for name,frame in [('queue',qframe),('maker',pframe),('shocks',sframe),('replacements',replacement)]:frame.to_parquet(OUT/f'{name}_{symbol}.parquet',index=False)
 summary={'symbol':symbol,'events':len(events),'queue_samples':len(qframe),'maker_trials':len(pframe),'sampled_shocks':len(sframe),'full_cancellations':len(cancelrows),'replacement_rows':len(replacement),'active_groups':len(groups),'noncontiguous_groups':int((~groups.contiguous).sum()),'volume_calibration':cal,'mid_changes':dict(changes)}
 (OUT/f'stock_{symbol}.json').write_text(json.dumps(summary,allow_nan=False),encoding='utf-8')
 print(json.dumps(summary),flush=True)


def replacements(c,adds,legs,groups,event_t,event_seq):
 """Mutually unique same-size anonymous links; reconstruct first observable message offline."""
 a=adds.reset_index().rename(columns={'OrderOriNo':'oid','original_qty':'quantity','price_cents':'price'})
 first=legs[legs.oid.isin(a.oid)].groupby('oid').agg(firstseq=('BizIndex','min'),first_t=('t','min'))
 a=a.join(first,on='oid');a['seq']=np.fmin(a.BizIndex,a.firstseq.fillna(np.inf)).astype('int64');a['t']=np.fmin(a.t,a.first_t.fillna(np.inf)).astype('int64');a['family']='ADD'
 noadd=groups[~groups.oid.isin(a.oid)].copy();noadd['seq']=noadd.firstseq;noadd['price']=noadd.notional/noadd.quantity;noadd['family']='active_no_ADD'
 cols=['oid','side','t','seq','quantity','price','family']
 new=pd.concat([a[cols],noadd[cols]],ignore_index=True).sort_values('seq').reset_index(drop=True)
 new=new[new.t.map(in_session)].copy()
 linked=legs.merge(new[['oid','t']].rename(columns={'t':'birth'}),on='oid');linked=linked[(linked.t>=linked.birth)&(linked.t<=linked.birth+30000)]
 fill=linked.groupby('oid').Volume.sum();new=new.join(fill.rename('filled30'),on='oid');new.filled30=new.filled30.fillna(0)
 if (new.filled30>new.quantity).any():raise ValueError('new candidate execution exceeds observable quantity')
 c=c[c.t+31000<c.t.map(end_of)].copy();c=c.sort_values('seq').reset_index(drop=True)
 results=[]
 new=new.reset_index(drop=True)
 new_groups=new.groupby(['side','quantity'],sort=False).indices
 new_arrays={k:new[k].to_numpy() for k in ['oid','t','seq','price','family','filled30','quantity']}
 for shift in [0,60000,300000]:
  common=c[c.t+shift+31000<c.t.map(end_of)].copy();common['anchor']=common.t+shift
  if shift:
   ix=np.searchsorted(event_t,common.anchor.to_numpy(),side='left');common['anchor_seq']=event_seq[np.minimum(ix,len(event_seq)-1)]-.5
  else:common['anchor_seq']=common.seq
  common=common.reset_index(drop=True);old_groups=common.groupby(['side','quantity'],sort=False).indices
  oa={k:common[k].to_numpy() for k in ['anchor','anchor_seq','oid','price']}
  for w in [20,100,1000]:
   for sym in [False,True]:
    labels=np.full(len(common),'no_candidate',dtype=object);lags=np.full(len(common),np.nan);newids=lags.copy();fractions=lags.copy()
    for (side,qty),ids in old_groups.items():
     fresh_ids=new_groups.get((side,qty))
     if fresh_ids is None:continue
     ot=oa['anchor'][ids];os=oa['anchor_seq'][ids];oi=oa['oid'][ids]
     nt=new_arrays['t'][fresh_ids];ns=new_arrays['seq'][fresh_ids];ni=new_arrays['oid'][fresh_ids]
     own_new=np.full(len(ids),-1);own_old=np.full(len(fresh_ids),-1)
     if sym:
      sn={int(v):i for i,v in enumerate(ni)};so={int(v):i for i,v in enumerate(oi)}
      own_new=np.array([sn.get(int(v),-1) for v in oi]);own_old=np.array([so.get(int(v),-1) for v in ni])
     lo=np.searchsorted(nt,ot-w,side='left') if sym else np.searchsorted(ns,os,side='right')
     hi=np.searchsorted(nt,ot+w,side='right');has_self=(own_new>=lo)&(own_new<hi)&(own_new>=0)
     count=hi-lo-has_self
     pick=lo+((own_new==lo)&has_self);safe=np.clip(pick,0,len(fresh_ids)-1)
     reverse_lo=np.searchsorted(ot,nt-w,side='left')
     reverse_hi=np.searchsorted(ot,nt+w,side='right') if sym else np.searchsorted(os,ns,side='left')
     reverse_self=(own_old>=reverse_lo)&(own_old<reverse_hi)&(own_old>=0)
     reverse_n=reverse_hi-reverse_lo-reverse_self
     unique=(count==1)&(reverse_n[safe]==1)
     labels[ids]=np.where(count==0,'no_candidate','ambiguous')
     partners=fresh_ids[safe];delta=(new_arrays['price'][partners]-oa['price'][ids])*(1 if side=='B' else -1)
     label=np.where(new_arrays['family'][partners]=='active_no_ADD','active_no_ADD',np.where(delta>0,'chase',np.where(delta<0,'retreat','same_price')))
     chosen=ids[unique];nidx=partners[unique];labels[chosen]=label[unique]
     lags[chosen]=new_arrays['t'][nidx]-ot[unique];newids[chosen]=new_arrays['oid'][nidx]
     fractions[chosen]=new_arrays['filled30'][nidx]/new_arrays['quantity'][nidx]
    z=common[['symbol','oid','t','side','quantity','price','rank','distance']].copy();z['shift']=shift;z['window']=w;z['symmetric']=sym
    z['classification']=labels;z['lag']=lags;z['new_oid']=newids;z['filled30_fraction']=fractions;results.append(z)
 return pd.concat(results,ignore_index=True),new


def main():
 parser=argparse.ArgumentParser();parser.add_argument('--symbols',nargs='*',type=int);parser.add_argument('--refresh',action='store_true');args=parser.parse_args()
 OUT.mkdir(parents=True,exist_ok=True)
 (OUT/'PLAN.json').write_text(json.dumps(PLAN,ensure_ascii=False,indent=2),encoding='utf-8')
 symbols=args.symbols or pd.read_csv(ROOT/'reports/order_patterns/stocks.csv').symbol.tolist()
 for symbol in symbols:
  if not args.refresh and (OUT/f'stock_{symbol}.json').exists():print(f'reused {symbol}',flush=True);continue
  run_stock(int(symbol))

if __name__=='__main__':main()
