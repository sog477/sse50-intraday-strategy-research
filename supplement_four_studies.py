"""Additional descriptive checks, explicitly exploratory after main results."""
import json
import numpy as np
import pandas as pd
from summarize_four_studies import OUT, compare

def main():
 p=pd.read_parquet(OUT/'maker_trials.parquet');p=p[p.model=='tape_only'].copy()
 p['fill_status']=np.where(p.fill_any>0,'filled','unfilled')
 selection=p.groupby(['signal','fill_status']).agg(n=('t','size'),future30_bp=('future30_ticks_bp','mean')).reset_index()
 selection.to_csv(OUT/'maker_selection.csv',index=False)
 result={'exploratory_after_main_results':True,'maker_selection_raw':selection.to_dict('records'),'maker_selection_matched':{}}
 for signal,g in p.groupby('signal'):
  result['maker_selection_matched'][signal]=compare(g,'fill_status','filled','unfilled',['future30_ticks_bp'],['symbol','side','block','spread_bin'])
 s=pd.read_parquet(OUT/'shock_samples.parquet')
 s['impact_at_1sec_bp']=s.impact_at_1sec/s.pre_mid*10000
 result['gap_normalized']=compare(s,'gap_group','gap>=2','gap=1',['impact_bp','impact_at_1sec_bp'],['symbol','side','block','size','rel_bin','spread_bin'])
 result['gap_mainboard']=compare(s[s.symbol<688000],'gap_group','gap>=2','gap=1',['impact','large_move','impact_at_1sec'],['symbol','side','block','size','rel_bin','spread_bin'])
 result['small_vs_large_mainboard']=compare(s[s.symbol<688000],'cross_cell','small_gap','large_dense',['impact','large_move'],['symbol','side','block','spread_bin'],mincell=5)
 d=pd.read_csv(OUT/'replacement_shift_diagnostics.csv');d=d[(d.window==100)&~d.symmetric]
 checks=[]
 for shift,g in d.groupby('shift'):
  x=(g.raw_unique-g.null_unique)/g.n;rng=np.random.default_rng(20260923)
  boot=np.mean(rng.choice(x.to_numpy(),(10000,len(x)),replace=True),axis=1)
  checks.append({'shift':int(shift),'equal_stock_difference':float(x.mean()),'stock_bootstrap_within_day_interval':np.quantile(boot,[.025,.975]).tolist()})
 result['replacement_stock_bootstrap']=checks
 (OUT/'supplement.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
 print(json.dumps({k:v for k,v in result.items() if k in ['maker_selection_raw','replacement_stock_bootstrap']},ensure_ascii=False))

if __name__=='__main__':main()
