"""Descriptive summaries and within-day matched comparisons, no strategy fitting."""
from pathlib import Path
import argparse,json
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'reports'/'four_studies'

def compare(frame,group,a,b,metrics,keys,mincell=3):
 x=frame[frame[group].isin([a,b])].copy();x['block']=x.t//1800000
 aa=x[x[group]==a].groupby(keys)[metrics].agg(['mean','count']);bb=x[x[group]==b].groupby(keys)[metrics].agg(['mean','count'])
 common=aa.index.intersection(bb.index);aa=aa.loc[common];bb=bb.loc[common]
 result={'groups':[a,b],'entry_n_a':int((x[group]==a).sum()),'entry_n_b':int((x[group]==b).sum()),'keys':keys,'minimum_per_cell':mincell,'metrics':{}}
 for metric in metrics:
  good=(aa[(metric,'count')]>=mincell)&(bb[(metric,'count')]>=mincell);left=aa[good];right=bb[good]
  if left.empty:result['metrics'][metric]={'stocks':0,'strata':0};continue
  w=np.minimum(left[(metric,'count')],right[(metric,'count')]);p=pd.DataFrame({k:left.index.get_level_values(k) for k in keys})
  p['w']=w.to_numpy();p['sa']=p.w*left[(metric,'mean')].to_numpy();p['sb']=p.w*right[(metric,'mean')].to_numpy()
  bystock=p.groupby('symbol')[['w','sa','sb']].sum();eligible=bystock.w>=5;bystock=bystock[eligible];p=p[p.symbol.isin(bystock.index)]
  if bystock.empty:result['metrics'][metric]={'stocks':0,'strata':len(left)};continue
  means=bystock[['sa','sb']].div(bystock.w,axis=0);diff=means.sa-means.sb
  symbols=sorted(p.symbol.unique());blocks=sorted(p.block.unique());si={v:i for i,v in enumerate(symbols)};bi={v:i for i,v in enumerate(blocks)}
  cube=np.zeros((3,len(symbols),len(blocks)))
  for r in p.groupby(['symbol','block'])[['w','sa','sb']].sum().reset_index().itertuples():cube[:,si[r.symbol],bi[r.block]]=[r.w,r.sa,r.sb]
  rng=np.random.default_rng(20260923);boot=[]
  for _ in range(1000):
   sw=rng.multinomial(len(symbols),np.ones(len(symbols))/len(symbols));bw=rng.multinomial(len(blocks),np.ones(len(blocks))/len(blocks));sums=cube@bw
   valid=(sums[0]>0)&(sw>0)
   if valid.any():boot.append(float(np.average((sums[1,valid]-sums[2,valid])/sums[0,valid],weights=sw[valid])))
  keep=left.index.get_level_values('symbol').isin(bystock.index)
  counts_a=int(left.loc[keep,(metric,'count')].sum());counts_b=int(right.loc[keep,(metric,'count')].sum())
  result['metrics'][metric]={'stocks':len(bystock),'strata':len(p),'matched_n_a':counts_a,'matched_n_b':counts_b,
    'equal_stock_a':float(means.sa.mean()),'equal_stock_b':float(means.sb.mean()),'difference_a_minus_b':float(diff.mean()),
    'within_day_95_interval':np.quantile(boot,[.025,.975]).tolist(),'positive_stocks':int((diff>0).sum()),
    'stock_effects':[{'symbol':int(s),'weight':float(bystock.loc[s,'w']),'a':float(means.loc[s,'sa']),'b':float(means.loc[s,'sb']),'difference':float(diff.loc[s])} for s in bystock.index]}
 return result

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--partial',action='store_true');args=parser.parse_args()
 stocks=[json.loads(p.read_text()) for p in sorted(OUT.glob('stock_*.json'))]
 if len(stocks)!=50 and not args.partial:raise ValueError(f'need50 stocks, got{len(stocks)}')
 symbols=[s['symbol'] for s in stocks]
 load=lambda name:pd.concat([pd.read_parquet(OUT/f'{name}_{s}.parquet') for s in symbols],ignore_index=True)
 result={'stocks':len(stocks),'events':sum(s['events'] for s in stocks),'stock_results':stocks,'bootstrap':'1000 crossed stock and 30-minute clock-block resamples; within-day uncertainty, not new-day validation'}
 q=load('queue');q['block']=q.t//1800000
 q['exposure']=np.select([(q.fc>0)&q.bc.eq(0),(q.bc>0)&q.fc.eq(0),(q.fc>0)&(q.bc>0)],['front_only','back_only','mixed'],default='none')
 q['position']=q.front/q.level;q['pos_bin']=np.minimum(3,(q.position*4).astype(int));q['pos_decile']=np.minimum(9,(q.position*10).astype(int))
 q['cancel_ratio']=(q.fc+q.bc)/q.level;q['cancel_bin']=np.searchsorted([.01,.05,.2],q.cancel_ratio)
 q['age_bin']=np.searchsorted([1000,5000,30000,300000],q.age+1000);q['spread_bin']=np.minimum(q.spread,3)
 q['trade_present']=((q.ft+q.bt)>0).astype(int);q['depth_bin']=np.floor(np.log2(q.level)).astype(int);q['size_bin']=np.floor(np.log2(q.qty)).astype(int)
 qm=[f'{k}{h}' for h in [1000,3000,10000] for k in ['cancel','fill']]
 qt=q.groupby('exposure').agg(n=('oid','size'),stocks=('symbol','nunique'),unique_orders=('oid','nunique'),cancel3=('cancel3000','mean'),fill3=('fill3000','mean'),median_position=('position','median'),median_cancel_fraction=('cancel_ratio','median')).reset_index()
 qt.to_csv(OUT/'queue_groups.csv',index=False)
 qkeys=['symbol','side','block','spread_bin','pos_bin','cancel_bin','age_bin','trade_present']
 result['queue']={'samples':len(q),'groups':qt.to_dict('records'),
  'matched':compare(q,'exposure','back_only','front_only',qm,qkeys),
  'strict':compare(q,'exposure','back_only','front_only',qm,['symbol','side','block','spread_bin','pos_decile','cancel_bin','age_bin','trade_present','depth_bin','size_bin']),
  'no_trade':compare(q[q.trade_present==0],'exposure','back_only','front_only',qm,qkeys)}
 q.to_parquet(OUT/'queue_samples.parquet',index=False)

 p=load('maker');p['block']=p.t//1800000;p['fill_any']=(p.filled>0).astype(float);p['fill_fraction']=p.filled/p.quantity;p['spread_bin']=np.minimum(p.spread,3)
 for name in ['future30_ticks','markout1000','markout5000','markout30000','drift1000','drift5000','drift30000','markout30_after_entry_fee_ticks']:
  p[name+'_bp']=p[name]/p.entry_mid*10000
 rows=[]
 for (model,signal),g in p.groupby(['model','signal']):
  record={'model':model,'signal':signal,'n':len(g),'stocks':int(g.symbol.nunique()),'fills':int(g.fill_any.sum()),'fill_probability':float(g.fill_any.mean()),'fill_fraction':float(g.fill_fraction.mean()),'median_wait_ms':float(g.wait_ms.median()),'future30_ticks':float(g.future30_ticks.mean()),'future30_bp':float(g.future30_ticks_bp.mean()),'after_entry_fee_markout30_bp':float(g.markout30_after_entry_fee_ticks_bp.mean())}
  for h in [1000,5000,30000]:
   record[f'markout{h}_bp']=float(g[f'markout{h}_bp'].mean());record[f'drift{h}_bp']=float(g[f'drift{h}_bp'].mean())
  rows.append(record)
 pd.DataFrame(rows).to_csv(OUT/'maker_groups.csv',index=False)
 pm=['fill_any','fill_fraction','future30_ticks_bp'];cm=['markout1000_bp','markout5000_bp','markout30000_bp','drift1000_bp','drift5000_bp','drift30000_bp']
 result['maker']={'trials':len(p),'groups':rows,'models':{}}
 for model,g in p.groupby('model'):
  result['maker']['models'][model]={'entry_comparison':compare(g,'signal','against','with',pm,['symbol','side','block','spread_bin']),
   'filled_comparison':compare(g[g.fill_any==1],'signal','against','with',cm,['symbol','side','block','spread_bin'],mincell=2),
   'filled_equal_stock':compare(g[g.fill_any==1],'signal','against','with',cm,['symbol','block'],mincell=2)}
 wide=p.pivot(index=['symbol','side','t'],columns='model',values='filled')
 result['maker']['model_disagreement_fraction']=float((wide.tape_only!=wide.with_residual).mean())
 p.to_parquet(OUT/'maker_trials.parquet',index=False)

 s=load('shocks');s['block']=s.end_t//1800000;s['spread_bin']=np.minimum(s.spread,3)
 s['rel_bin']=np.searchsorted([.25,.5,1,2],s.relative_volume)
 s['impact_bp']=s.impact/s.pre_mid*10000;s['impact_at_1sec']=s.impact+s.drift1000
 s['large_move_at_1sec']=(s.impact_at_1sec>=2).astype(int)
 st=s.groupby(['size','gap_group']).agg(n=('quantity','size'),stocks=('symbol','nunique'),median_quantity=('quantity','median'),median_relative_volume=('relative_volume','median'),mean_impact_ticks=('impact','mean'),mean_impact_bp=('impact_bp','mean'),large_jump_probability=('large_move','mean'),depletion_probability=('depleted','mean'),impact_after1sec=('impact_at_1sec','mean'),drift30=('drift30000','mean')).reset_index()
 st.to_csv(OUT/'shock_cells.csv',index=False)
 sm=['impact','large_move','depleted','impact_at_1sec','large_move_at_1sec','drift1000','drift5000','drift30000']
 result['shocks']={'sampled_groups':len(s),'cells':st.to_dict('records'),
  'matched':compare(s,'gap_group','gap>=2','gap=1',sm,['symbol','side','block','size','rel_bin','spread_bin']),
  'depleted_only':compare(s[s.depleted],'gap_group','gap>=2','gap=1',sm,['symbol','side','block','size','rel_bin','spread_bin'])}
 s['cross_cell']=np.select([s['size'].eq('small')&s.gap_group.eq('gap>=2'),s['size'].eq('large')&s.gap_group.eq('gap=1')],['small_gap','large_dense'],default='other')
 result['shocks']['small_vs_large']=compare(s,'cross_cell','small_gap','large_dense',['impact','large_move','impact_at_1sec'],['symbol','side','block','spread_bin'],mincell=5)
 examples=pd.concat([s[(s['size']=='small')&(s.gap>=2)&(s.impact>=2)].sort_values('impact',ascending=False).head(10),s[(s['size']=='large')&(s.gap==1)&(s.impact==0)].sort_values('quantity',ascending=False).head(10)])
 examples.to_csv(OUT/'shock_examples.csv',index=False);s.to_parquet(OUT/'shock_samples.parquet',index=False)

 summaries=[];checks=[];examples=[];quantity_tables=[]
 links=['same_price','chase','retreat','active_no_ADD']
 for symbol in symbols:
  r=pd.read_parquet(OUT/f'replacements_{symbol}.parquet');r['any_fill']=(r.filled30_fraction>0).astype(float)
  agg=r.groupby(['symbol','shift','window','symmetric','classification']).agg(n=('oid','size'),any_fill=('any_fill','sum'),sum_fill_fraction=('filled30_fraction','sum'),median_lag=('lag','median')).reset_index();summaries.append(agg)
  for shift in [60000,300000]:
   raw=r[(r['shift']==0)&((r.t+shift+31000)<np.where(r.t<43200000,41400000,53820000))];null=r[r['shift']==shift]
   for w in [20,100,1000]:
    for sym in [False,True]:
     a=raw[(raw.window==w)&raw.symmetric.eq(sym)];b=null[(null.window==w)&null.symmetric.eq(sym)]
     if len(a)!=len(b):raise ValueError('shift common population mismatch')
     checks.append({'symbol':symbol,'shift':shift,'window':w,'symmetric':sym,'n':len(a),'raw_unique':int(a.classification.isin(links).sum()),'null_unique':int(b.classification.isin(links).sum()),'raw_chase_active':int(a.classification.isin(['chase','active_no_ADD']).sum()),'null_chase_active':int(b.classification.isin(['chase','active_no_ADD']).sum())})
  primary=r[(r['shift']==0)&(r.window==100)&~r.symmetric].copy();primary['size_group']=np.select([primary.quantity==100,primary.quantity%100!=0,primary.quantity>=10000],['100shares','non100multiple','>=10000'],default='other_round')
  quantity_tables.append(primary.groupby(['symbol','size_group','classification']).size().rename('n').reset_index())
  for typ in links:
   examples.append(primary[primary.classification==typ].sort_values(['quantity','lag'],ascending=[False,True]).head(2))
 agg=pd.concat(summaries,ignore_index=True);agg.to_csv(OUT/'replacement_by_stock.csv',index=False)
 pooled=agg.groupby(['shift','window','symmetric','classification']).agg(n=('n','sum'),any_fill=('any_fill','sum'),sum_fill_fraction=('sum_fill_fraction','sum')).reset_index();pooled['any_fill_probability']=pooled.any_fill/pooled.n;pooled['mean_fill_fraction']=pooled.sum_fill_fraction/pooled.n
 pooled.to_csv(OUT/'replacement_groups.csv',index=False)
 checks=pd.DataFrame(checks);checks.to_csv(OUT/'replacement_shift_diagnostics.csv',index=False)
 effect=[]
 for key,g in checks.groupby(['shift','window','symmetric']):
  d=(g.raw_unique-g.null_unique)/g.n
  effect.append({'shift':int(key[0]),'window':int(key[1]),'symmetric':bool(key[2]),'same_population_n':int(g.n.sum()),'raw_unique_fraction':float(g.raw_unique.sum()/g.n.sum()),'null_unique_fraction':float(g.null_unique.sum()/g.n.sum()),'equal_stock_difference':float(d.mean()),'positive_stocks':int((d>0).sum())})
 pd.concat(quantity_tables).to_csv(OUT/'replacement_quantity_groups.csv',index=False)
 pd.concat(examples).to_csv(OUT/'replacement_examples.csv',index=False)
 result['replacement']={'groups':pooled.to_dict('records'),'shift_diagnostics':effect,'note':'anonymous mutually unique links; no candidate is not evidence of exit; completion is offline within30s from first observed new order message, including fills preceding residualADD'}
 # Python's NaN is not JSON: recursively replace undefined statistics with null.
 def clean(x):
  if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
  if isinstance(x,list):return [clean(v) for v in x]
  if isinstance(x,(np.integer,)):return int(x)
  if isinstance(x,(np.floating,float)):return float(x) if np.isfinite(x) else None
  return x
 name='preview_summary.json' if args.partial else 'summary.json'
 (OUT/name).write_text(json.dumps(clean(result),ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
 print(name,'stocks',len(stocks),'queue',len(q),'maker',len(p),'shocks',len(s),flush=True)

if __name__=='__main__':main()
