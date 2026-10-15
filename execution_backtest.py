"""Whole-day, fixed-clock paired execution experiment; no parameter fitting.

Every historical message is applied once per stock. Concurrent independent shadow
sessions read the same immutable historical book, with private capacity ledgers.
Latency is an action delay (atomic cancel/replace), not a full network/ACK model.
"""
from __future__ import annotations
from collections import defaultdict
from pathlib import Path
import argparse, json, time
from concurrent.futures import ProcessPoolExecutor, as_completed
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from execution_strategy import quote, valid_child_quantity, compare_execution, POLICIES
from simulator import HistoricalSession, clock, stamp_ms, ms_stamp
from orderbook import apply_market_event, price_str, dataset_date

ROOT=Path(__file__).resolve().parent
DATA=ROOT/'sse50_20260923'
OUT=ROOT/'reports'/'execution_day'
VERSION=1
PLAN={'version':VERSION,'date':'2026-09-23','stocks':50,'task_clock_seconds':30,
 'sessions_ms':[[34200000,41400000],[46800000,53820000]],'horizon_ms':30000,
 'quantity':'100 mainboard / 200 STAR shares; BUY and SELL independently; sell assumes sufficient initial sellable inventory per task',
 'policies':[p for p,_ in POLICIES],'obi_threshold':.6,'decision_ms':1000,
 'models':['tape_only','with_residual'],'action_delays_ms':[0,100,500],
 'protection':'fixed initial opposite best +/-2 cents, minimum1 cent',
 'latency':'signal observation at clock t; entire cancel/replace or submit action effective at t+delay; prior order may fill meanwhile; size recomputed at effectiveness; final action pre-scheduled to become effective at deadline. Idealized atomic replace, no extra ACK/return latency or market-data lag.',
 'evaluation':'all tasks with actual fills/fees plus separately marked unfilled opportunity cost at deadline midpoint; paired all-completed subset secondary; no portfolio/roundtrip profit claim',
 'selection':'all stocks/all regular30-second origins with full30-second window strictly inside same session; no outcome selection, no retuning; single previously studied day, not out of sample'}

class Node:
 def __init__(self, source, side, qty, policy, model, delay, initial, start):
  self.s=HistoricalSession(source.symbol,[],fees=source.fees,allow_residual_fills=model=='with_residual')
  self.s.book=source.book;self.s.time=source.time
  self.side,self.qty,self.policy,self.model,self.delay=side,qty,policy,model,delay
  self.initial,self.start=initial,start;self.urgent=policy=='immediate'
  self.cap=initial['ask']+2 if side=='B' else max(1,initial['bid']-2)
  self.pending=None;self.deadline_qty=0;self.deadline_notional=0;self.deadline_fees=0
  self.invalid_reposts=0;self.trigger_ms=None
 def filled(self):return sum(o.quantity-o.remaining for o in self.s.orders)
 def remaining(self):return self.qty-self.filled()
 def fees(self):return sum(o.fees_cents for o in self.s.orders)
 def notional(self):return sum(o.notional_cents for o in self.s.orders)
 def decide(self,now,q):
  if self.remaining()==0:return
  signed=(1 if self.side=='B' else -1)*q['obi'] if q else None
  if self.policy=='imbalance' and signed is not None and signed>=.6:
   if not self.urgent:self.trigger_ms=now-self.start
   self.urgent=True
  if self.urgent:self.pending=(now+self.delay,'active',None)
  elif now==self.start:
   own=q['bid'] if self.side=='B' else q['ask']
   p=min(own,self.cap) if self.side=='B' else max(own,self.cap)
   self.pending=(now+self.delay,'passive',p)
 def execute(self,now,final=False):
  if final:kind,p='active',None
  elif self.pending and self.pending[0]==now:_,kind,p=self.pending;self.pending=None
  else:return
  remaining=self.remaining()
  if not remaining:return
  before_q,before_n,before_f=self.filled(),self.notional(),self.fees()
  legal=valid_child_quantity(self.s.symbol,self.side,remaining)
  if final and self.s.active:self.s.cancel()
  if kind=='active' and legal:
   if self.s.active:self.s.cancel()
   self.s.submit(self.side,'FIVE_CANCEL',remaining,protection=price_str(self.cap))
  elif kind=='passive':self.s.submit(self.side,'LIMIT',remaining,price=price_str(p))
  elif not legal:self.invalid_reposts+=1
  if final:
   self.deadline_qty=self.filled()-before_q;self.deadline_notional=self.notional()-before_n;self.deadline_fees=self.fees()-before_f
 def row(self,end):
  filled=self.filled();remaining=self.qty-filled;sign=1 if self.side=='B' else -1
  n,f=self.notional(),self.fees();den=self.qty*self.initial['mid']
  gross=sign*(n-filled*self.initial['mid'])
  opportunity=sign*remaining*(end['mid']-self.initial['mid']) if end else None
  cost=gross+f+opportunity if opportunity is not None else (gross+f if not remaining else None)
  last=stamp_ms(int(self.s.fills[-1]['time'].replace(':','').replace('.',''))) if self.s.fills else None
  first=stamp_ms(int(self.s.fills[0]['time'].replace(':','').replace('.',''))) if self.s.fills else None
  opp=self.initial['ask'] if self.side=='B' else self.initial['bid']
  return {'symbol':self.s.symbol,'t':self.start,'side':self.side,'quantity':self.qty,'policy':self.policy,
   'model':self.model,'delay_ms':self.delay,'initial_mid_cents':self.initial['mid'],'initial_obi':self.initial['obi'],
   'protection_cents':self.cap,'terminal_mid_cents':end['mid'] if end else None,
   'filled':filled,'remaining':remaining,'complete':not remaining,'completion_fraction':filled/self.qty,
   'completion_ms':last-self.start if not remaining else None,'first_fill_ms':first-self.start if first is not None else None,
   'notional_cents':n,'fees_cents':f,'children':len(self.s.orders),'filled_children':sum(o.notional_cents>0 for o in self.s.orders),
   'gross_filled_cost_cents':gross,'opportunity_cost_cents':opportunity,'task_cost_cents':cost,
   'task_cost_bp':cost/den*10000 if cost is not None else None,'gross_task_cost_bp':(cost-f)/den*10000 if cost is not None else None,
   'fee_bp':f/den*10000,'filled_cost_bp':(gross+f)/(filled*self.initial['mid'])*10000 if filled else None,
   'deadline_fill_qty':self.deadline_qty,'deadline_fees_cents':self.deadline_fees,
   'deadline_chase_cents':sign*(self.deadline_notional-self.deadline_qty*opp),
   'invalid_repost_attempts':self.invalid_reposts,'trigger_ms':self.trigger_ms}

def advance_shared(source,target,nodes):
 raw=ms_stamp(target)
 while source.cursor<len(source.events) and source.events[source.cursor][0]<=raw:
  event=source.events[source.cursor];tm,ch,seq,kind,r=event;source.time=tm
  live=[n for n in nodes if n.remaining()>0 and (n.s.active is not None or n.s.used)]
  for n in live:n.s.time=tm;n.s._before_event(event)
  apply_market_event(source.book,event,source.stats)
  ids=[f"{ch}:{r['BidOrder']}",f"{ch}:{r['AskOrder']}"] if kind=='exe' else [f"{ch}:{r['OrderOriNo']}"]
  for n in live:
   for oid in ids:
    if oid not in source.book.orders or not n.s.used.get(oid,0):n.s.used.pop(oid,None)
    elif n.s.used[oid]>source.book.orders[oid].remaining:n.s.used[oid]=source.book.orders[oid].remaining
  source.cursor+=1
 source.time=raw
 for n in nodes:n.s.time=raw

def run_stock(symbol,verify=False):
 tic=time.perf_counter();source=HistoricalSession.from_data(DATA,symbol)
 rows=[];skipped=[];checks=[];windows=0
 for start,end in PLAN['sessions_ms']:
  for t in range(start,end-30000,30000):
   advance_shared(source,t,[]);initial=quote(source)
   if initial is None:skipped.append(t);continue
   qty=200 if str(symbol).startswith('688') else 100
   reference={}
   if verify and t==36000000:
    for model in PLAN['models']:
     for side in ['B','S']:
      reference[(model,side)]=compare_execution(source,side,qty,sellable=qty,fill_model=model)
   nodes=[Node(source,side,qty,policy,model,delay,initial,t) for side in ['B','S']
          for model in PLAN['models'] for delay in PLAN['action_delays_ms'] for policy,_ in POLICIES]
   offsets=sorted({0,30000}|{k+d for k in range(0,30000,1000) for d in PLAN['action_delays_ms'] if k+d<30000})
   for offset in offsets:
    now=t+offset;advance_shared(source,now,nodes)
    if offset==30000:
     for n in nodes:n.execute(now,final=True)
    else:
     # All historical messages at this timestamp precede effective commands.
     for n in nodes:n.execute(now)
     if offset%1000==0:
      q=quote(source)
      for n in nodes:
       n.decide(now,q)
       if n.delay==0:n.execute(now)
   terminal=quote(source);out=[n.row(terminal) for n in nodes]
   for r in out:
    if r['filled']<0 or r['filled']>qty:raise ValueError('task fill invariant')
   if reference:
    for r in out:
     if r['delay_ms']!=0:continue
     ref=next(z for z in reference[(r['model'],r['side'])]['results'] if z['policy']==r['policy'])
     diffs={key:(r[key],ref[other]) for key,other in [('filled','filled'),('remaining','remaining'),('completion_ms','completion_time_ms')]
            if r[key]!=ref[other]}
     if r['fees_cents']!=round(ref['fees_yuan']*100):diffs['fees']=(r['fees_cents'],ref['fees_yuan'])
     if abs(r['task_cost_bp']-ref['task_marked_cost_bp'])>1e-7:diffs['cost']=(r['task_cost_bp'],ref['task_marked_cost_bp'])
     if diffs:raise ValueError(f'UI engine mismatch {symbol} {r["policy"]}: {diffs}')
     checks.append({'symbol':symbol,'t':t,'model':r['model'],'side':r['side'],'policy':r['policy'],'matches_ui':True})
   rows.extend(out);windows+=1
 advance_shared(source,54000000,[])
 frame=pd.DataFrame(rows);frame.to_parquet(OUT/f'tasks_{symbol}.parquet',index=False)
 info={'symbol':symbol,'windows':windows,'task_origins_per_configuration':windows*2,'rows':len(frame),
       'events':source.cursor,'skipped_invalid_initial_quote':skipped,'ui_cross_checks':checks,
       'seconds':round(time.perf_counter()-tic,3),'version':VERSION}
 (OUT/f'stock_{symbol}.json').write_text(json.dumps(info,indent=2),encoding='utf-8')
 print(json.dumps(info),flush=True)

def main():
 p=argparse.ArgumentParser();p.add_argument('--symbols',nargs='*',type=int);p.add_argument('--refresh',action='store_true');p.add_argument('--workers',type=int,default=4);args=p.parse_args()
 OUT.mkdir(parents=True,exist_ok=True);(OUT/'PLAN.json').write_text(json.dumps(PLAN,indent=2),encoding='utf-8')
 symbols=args.symbols or sorted(pq.read_table(DATA/f'ord_{dataset_date(DATA)}.parquet',columns=['Symbol']).column('Symbol').unique().to_pylist())
 pending=[symbol for symbol in symbols if args.refresh or not (OUT/f'stock_{symbol}.json').exists()]
 if args.workers<1 or args.workers>4:raise ValueError('workers must be1..4')
 if args.workers==1:
  for symbol in pending:run_stock(symbol,verify=symbol in [600028,601688,688256])
 else:
  with ProcessPoolExecutor(max_workers=args.workers) as pool:
   futures=[pool.submit(run_stock,symbol,symbol in [600028,601688,688256]) for symbol in pending]
   for future in as_completed(futures):future.result()

if __name__=='__main__':main()
