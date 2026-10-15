"""Paired all-origin comparisons; include unfilled opportunity cost, report marks separately."""
from pathlib import Path
import json
import hashlib
import numpy as np
import pandas as pd
from execution_backtest import OUT, PLAN
from simulator import Fees
from decimal import Decimal, ROUND_HALF_UP

def interval(frame,column):
 symbols=sorted(frame.symbol.unique());blocks=sorted(frame.block.unique())
 si={v:i for i,v in enumerate(symbols)};bi={v:i for i,v in enumerate(blocks)}
 cube=np.zeros((2,len(symbols),len(blocks)))
 for r in frame.groupby(['symbol','block'])[column].agg(['sum','count']).reset_index().itertuples(index=False):
  cube[:,si[r.symbol],bi[r.block]]=[r.sum,r.count]
 rng=np.random.default_rng(20260923);boot=[]
 for _ in range(1000):
  sw=rng.multinomial(len(symbols),np.ones(len(symbols))/len(symbols));bw=rng.multinomial(len(blocks),np.ones(len(blocks))/len(blocks))
  x=cube@bw;valid=(x[1]>0)&(sw>0)
  if valid.any():boot.append(float(np.average(x[0,valid]/x[1,valid],weights=sw[valid])))
 return np.quantile(boot,[.025,.975]).tolist()

def main():
 stocks=[json.loads(p.read_text()) for p in sorted(OUT.glob('stock_*.json'))]
 if len(stocks)!=50:raise ValueError(f'require50 completed stocks, got{len(stocks)}')
 frame=pd.concat([pd.read_parquet(OUT/f'tasks_{r["symbol"]}.parquet') for r in stocks],ignore_index=True)
 keys=['symbol','t','side','model','delay_ms','policy']
 if frame.duplicated(keys).any():raise ValueError('duplicate task-policy rows')
 expected=472*2*2*3*3*50
 if len(frame)!=expected:raise ValueError(f'incomplete grid {len(frame)} !={expected}')
 if frame.task_cost_bp.isna().any():raise ValueError('missing endpoint costs')
 frame['block']=frame.t//600000
 sign=np.where(frame.side.eq('B'),1,-1)
 den=frame.quantity*frame.initial_mid_cents
 frame['gross_end_mark_cents']=sign*(frame.filled*frame.terminal_mid_cents-frame.notional_cents)
 frame['net_end_mark_cents']=frame.gross_end_mark_cents-frame.fees_cents
 frame['gross_end_mark_bp']=frame.gross_end_mark_cents/den*10000
 frame['net_end_mark_bp']=frame.net_end_mark_cents/den*10000
 # Exploratory valuation sensitivity, not simulated extra fills: future fees on
 # unfinished quantities if a single later child could complete at deadline mid.
 fee_model=Fees();extra=np.zeros(len(frame))
 for r in frame[frame.remaining>0].itertuples():
  hypothetical=int((Decimal(r.remaining)*Decimal(str(r.terminal_mid_cents))).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
  extra[r.Index]=fee_model.total(hypothetical,r.side)['total']
 frame['residual_fee_sensitivity_bp']=frame.task_cost_bp+extra/den*10000
 identity_error=(frame.task_cost_cents+frame.net_end_mark_cents-sign*frame.quantity*(frame.terminal_mid_cents-frame.initial_mid_cents)).abs().max()
 if identity_error>1e-7:raise ValueError('execution cost / terminal mark accounting identity failed')
 if not (frame.filled+frame.remaining).eq(frame.quantity).all():raise ValueError('task quantity conservation failed')
 frame['deadline_chase_bp']=frame.deadline_chase_cents/den*10000
 frame['complete_pct']=frame.complete*100
 frame['fill_pct']=frame.completion_fraction*100
 frame['deadline_fill_pct']=frame.deadline_fill_qty/frame.quantity*100
 metrics=['task_cost_bp','gross_task_cost_bp','fee_bp','complete_pct','fill_pct','gross_end_mark_bp','net_end_mark_bp','deadline_chase_bp','deadline_fill_pct','children','filled_children']
 perstock=frame.groupby(['model','delay_ms','policy','symbol'])[metrics].mean().reset_index()
 perstock.to_csv(OUT/'stock_metrics.csv',index=False)
 groups=[]
 for (model,delay,policy),g in frame.groupby(['model','delay_ms','policy']):
  es=perstock[(perstock.model==model)&(perstock.delay_ms==delay)&(perstock.policy==policy)]
  z={'model':model,'delay_ms':int(delay),'policy':policy,'n':len(g),'stocks':int(g.symbol.nunique())}
  z.update({m:float(es[m].mean()) for m in metrics})
  z.update({'remaining_shares':int(g.remaining.sum()),'deadline_filled_shares':int(g.deadline_fill_qty.sum()),
   'fees_yuan':float(g.fees_cents.sum()/100),'arithmetic_task_cost_yuan':float(g.task_cost_cents.sum()/100),
   'arithmetic_end_mark_yuan':float(g.net_end_mark_cents.sum()/100),
   'median_completion_ms_if_complete':float(g.loc[g.complete,'completion_ms'].median()),
   'median_first_fill_ms_if_filled':float(g.loc[g.filled>0,'first_fill_ms'].median()),
   'no_fill_pct':float((g.filled==0).mean()*100),'deadline_attempt_fill_cases':int((g.deadline_fill_qty>0).sum()),
   'invalid_repost_cases':int((g.invalid_repost_attempts>0).sum())})
  groups.append(z)
 pd.DataFrame(groups).to_csv(OUT/'configuration_metrics.csv',index=False)
 paired=[];effects=[]
 for (model,delay),g in frame.groupby(['model','delay_ms']):
  idx=['symbol','t','side','block']
  a=g[g.policy=='imbalance'].set_index(idx)
  for baseline in ['immediate','passive']:
   b=g[g.policy==baseline].set_index(idx).reindex(a.index)
   p=a.reset_index()[idx].copy();p['model']=model;p['delay_ms']=int(delay);p['baseline']=baseline
   p['saving_bp']=(b.task_cost_bp-a.task_cost_bp).to_numpy()
   p['gross_saving_bp']=(b.gross_task_cost_bp-a.gross_task_cost_bp).to_numpy()
   p['extra_fee_bp']=(a.fee_bp-b.fee_bp).to_numpy()
   p['residual_fee_sensitivity_saving_bp']=(b.residual_fee_sensitivity_bp-a.residual_fee_sensitivity_bp).to_numpy()
   p['saving_yuan']=((b.task_cost_cents-a.task_cost_cents)/100).to_numpy()
   p['both_complete']=(a.complete&b.complete).to_numpy();p['strategy_complete']=a.complete.to_numpy();p['baseline_complete']=b.complete.to_numpy()
   p['win']=p.saving_bp>1e-8;p['loss']=p.saving_bp<-1e-8;p['tie']=~(p.win|p.loss)
   e=p.groupby('symbol').agg(saving_bp=('saving_bp','mean'),gross_saving_bp=('gross_saving_bp','mean'),extra_fee_bp=('extra_fee_bp','mean'),win_pct=('win','mean'),n=('saving_bp','size')).reset_index()
   e['model']=model;e['delay_ms']=int(delay);e['baseline']=baseline;effects.append(e)
   z={'model':model,'delay_ms':int(delay),'baseline':baseline,'n':len(p),'stocks':int(p.symbol.nunique()),
      'equal_stock_saving_bp':float(e.saving_bp.mean()),'within_day_95_interval':interval(p,'saving_bp'),
      'gross_saving_bp':float(e.gross_saving_bp.mean()),'extra_fee_bp':float(e.extra_fee_bp.mean()),
      'residual_fee_sensitivity_saving_bp':float(p.groupby('symbol').residual_fee_sensitivity_saving_bp.mean().mean()),
      'residual_fee_sensitivity_interval':interval(p,'residual_fee_sensitivity_saving_bp'),
      'positive_stocks':int((e.saving_bp>1e-8).sum()),'win_pct':float(p.win.mean()*100),'tie_pct':float(p.tie.mean()*100),
      'loss_pct':float(p.loss.mean()*100),'arithmetic_saving_yuan':float(p.saving_yuan.sum()),
      'strategy_complete_pct':float(p.strategy_complete.mean()*100),'baseline_complete_pct':float(p.baseline_complete.mean()*100)}
   full=p[p.both_complete];z['both_complete_n']=len(full)
   z['both_complete_saving_bp']=float(full.groupby('symbol').saving_bp.mean().mean()) if len(full) else None
   z['sides']={side:{'saving_bp':float(h.groupby('symbol').saving_bp.mean().mean()),'n':len(h)} for side,h in p.groupby('side')}
   z['periods']={label:{'saving_bp':float(h.groupby('symbol').saving_bp.mean().mean()),'n':len(h)}
     for label,h in [('morning',p[p.t<43200000]),('afternoon',p[p.t>=43200000])]}
   paired.append(z)
 pd.concat(effects,ignore_index=True).to_csv(OUT/'paired_stock_savings.csv',index=False)
 # Every input execution is checked against its protection and task budget during replay.
 tail=json.loads((OUT/'postclose_status_verification.json').read_text(encoding='utf-8'))
 result={'plan':PLAN,'stocks':len(stocks),'events_replayed':sum(r['events'] for r in stocks),
  'postclose_status_records_verified_separately':tail['count'],
  'competition_records_covered':sum(r['events'] for r in stocks)+tail['count'],
  'windows_per_stock':sorted({r['windows'] for r in stocks}),'task_origins_per_configuration':47200,'policy_rows':len(frame),
  'skipped_invalid_quotes':sum(len(r['skipped_invalid_initial_quote']) for r in stocks),
  'ui_engine_cross_checks':sum(len(r['ui_cross_checks']) for r in stocks),
  'maximum_accounting_identity_error_cents':float(identity_error),
  'code_sha256':{name:hashlib.sha256((Path(__file__).resolve().parent/name).read_bytes()).hexdigest()
                 for name in ['execution_backtest.py','execution_strategy.py','simulator.py','orderbook.py','summarize_execution_day.py']},
  'groups':groups,'paired_comparisons':paired,
  'uncertainty':'1000 crossed stock/10-minute common-clock-block bootstrap; within-day only, no new-day validation',
  'money_note':'Arithmetic savings/marks across independent task scenarios; not one funded portfolio, not daily realized profit. End marks use deadline midpoint without hypothetical liquidation/exit fees.',
  'exploratory_valuation_sensitivity':'Added after inspecting primary results: assign remaining quantity one additional child fee at deadline midpoint. Not extra fills, not actual completion, and no spread/impact or protection constraints modeled for that hypothetical completion.',
  'stock_run_stats':stocks}
 def clean(x):
  if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
  if isinstance(x,list):return [clean(v) for v in x]
  if isinstance(x,float) and not np.isfinite(x):return None
  return x
 (OUT/'summary.json').write_text(json.dumps(clean(result),ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
 print(json.dumps({'stocks':50,'events':result['events_replayed'],'rows':len(frame),'primary_groups':[r for r in groups if r['model']=='with_residual' and r['delay_ms']==0],
   'primary_comparisons':[r for r in paired if r['model']=='with_residual' and r['delay_ms']==0]},ensure_ascii=True),flush=True)

if __name__=='__main__':main()
