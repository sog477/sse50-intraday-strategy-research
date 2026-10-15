"""Targeted offline evidence checks; no investor identity labels or strategy fitting."""
import json
from decimal import Decimal, ROUND_CEILING
from pathlib import Path
import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
DATA = ROOT / 'sse50_20260923'

def millis(t):
    return (int(t)//10000000*3600+int(t)//100000%100*60+int(t)//1000%100)*1000+int(t)%1000

def clock(t):
    return f'{t//3600000:02d}:{t//60000%60:02d}:{t//1000%60:02d}.{t%1000:03d}'

def raw_stock(symbol):
    orders = pq.read_table(DATA/'ord_20260923.parquet', filters=[('Symbol','=',symbol)]).to_pandas()
    trades = pq.read_table(DATA/'exe_20260923.parquet', filters=[('Symbol','=',symbol)]).to_pandas()
    return orders, trades

def describe(row, orders, trades):
    linked = orders[(orders.Channel == row.Channel) & (orders.OrderOriNo == row.OrderOriNo)]
    cancels = linked[linked.OrderKind == 68]
    fills = trades[(trades.Channel == row.Channel) & ((trades.BidOrder == row.OrderOriNo) | (trades.AskOrder == row.OrderOriNo))]
    return dict(channel=int(row.Channel), order_id=int(row.OrderOriNo), side=chr(int(row.FunctionCode)),
                time=clock(millis(row.Time)), time_ms=millis(row.Time), price=round(float(row.Price),2), qty=int(row.Volume),
                cancel_times=[clock(millis(t)) for t in cancels.Time],
                cancel_ms=[millis(t) for t in cancels.Time], cancelled=int(cancels.Volume.sum()),
                trade_rows=len(fills), unique_adds=int((linked.OrderKind==65).sum()))

periodic = pd.read_csv(OUT/'periodic_examples.csv')
result = {'method':'post-hoc targeted offline checks; sampled patterns, not identities or independently validated strategies'}

orders,trades=raw_stock(688981)
adds=orders[(orders.OrderKind==65)&(orders.Time>=110504360)&(orders.Time<=110525360)&(orders.Volume==1100)]
records=[describe(r,orders,trades) for r in adds.itertuples()]
pairs=[]
for stamp in sorted(set(r['time_ms'] for r in records)):
    same=[r for r in records if r['time_ms']==stamp]
    for b in same:
        for s in same:
            if b['side']=='B' and s['side']=='S' and b['channel']==s['channel'] and abs(b['order_id']-s['order_id'])==1:
                pairs.append({'time':b['time'], 'buy':b, 'sell':s})
result['synchronized_two_sided_688981']={'pairs':pairs, 'all_selected_orders':records}

orders,trades=raw_stock(600050)
chosen=periodic[periodic.case_id=='600050-1']
batch=[]
for r in chosen.itertuples():
    row=orders[(orders.Channel==r.channel)&(orders.OrderOriNo==r.original_order_id)&(orders.OrderKind==65)].iloc[0]
    batch.append(describe(row,orders,trades))
c=[v for r in batch for v in r['cancel_ms']]
result['batch_cancel_600050']={'orders':batch,'cancel_spread_ms':max(c)-min(c),
                              'cancel_start':clock(min(c)), 'cancel_end':clock(max(c))}

cash=[]
for symbol,target in [(688008,100000),(688012,200000),(688041,100000),(688111,100000),(688256,300000)]:
    x=periodic[(periodic.symbol==symbol)&(periodic.side=='B')].copy()
    x['target_qty']=[int((Decimal(target)/Decimal(str(p))).to_integral_value(rounding=ROUND_CEILING)) for p in x.price]
    exact=x[x.original_qty==x.target_qty]
    cash.append({'symbol':symbol,'target_yuan':target,'periodic_selected_buy_orders':len(x),
                 'exact_ceil_target_over_price':len(exact),'fraction':len(exact)/len(x),
                 'examples':exact[['time','price','original_qty','original_order_id']].drop_duplicates(['price','original_qty']).head(6).to_dict('records')})
result['cash_formula_selected_buys']=cash
(OUT/'additional_clues.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'paired_timestamps':[p['time'] for p in pairs], 'batch_cancel':{k:v for k,v in result['batch_cancel_600050'].items() if k!='orders'}, 'cash_formula':cash},ensure_ascii=False,indent=2))
