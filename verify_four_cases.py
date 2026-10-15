"""Recheck selected illustrations directly against original events and book replay."""
from collections import defaultdict
import json
import pandas as pd
from four_studies import OUT, prepare, bbo, mid
from orderbook import OrderBook, apply_market_event

def main():
 shocks=pd.read_csv(OUT/'shock_examples.csv');records=[]
 # One small/gapped shock and one large/dense zero-impact group.
 choices=pd.concat([shocks.iloc[:1],shocks[shocks.impact==0].iloc[:1]])
 for row in choices.itertuples():
  od,ex,adds,legs,groups,events,cal=prepare(int(row.symbol))
  actual=ex[(ex.BizIndex>=row.first_seq)&(ex.BizIndex<=row.last_seq)]
  assert actual.Volume.sum()==row.quantity
  assert (actual.BidOrder if row.side=='B' else actual.AskOrder).eq(row.active_oid).all()
  book=OrderBook(int(row.symbol),retain_trades=False);stats=defaultdict(int)
  for event in events:
   if event[2]==row.first_seq:
    before=bbo(book);passive='S' if row.side=='B' else 'B'
    prices=book.prices[passive];ranked=prices[:2] if passive=='S' else prices[-2:][::-1]
    assert abs(ranked[1]-ranked[0])==row.gap and mid(before)==row.pre_mid
    assert book.levels[passive][ranked[0]]==row.best_depth
   apply_market_event(book,event,stats)
   if event[2]==row.last_seq:
    after=bbo(book);assert mid(after)==row.post_mid;break
  records.append({'kind':'gap_case','symbol':int(row.symbol),'time_ms':int(row.t),'side':row.side,'active_oid':int(row.active_oid),'quantity':int(row.quantity),'before_bid_ask_cents':before,'after_bid_ask_cents':after,'passive_next_gap_cents':int(row.gap),'signed_mid_impact_cents':float(row.impact),'checked':True})
 # One candidate of each class in one stock, with repaired new quantity and ordering.
 x=pd.read_csv(OUT/'replacement_examples.csv');x=x[x.symbol==600028]
 od,ex,adds,legs,groups,events,cal=prepare(600028)
 for typ,g in x.groupby('classification'):
  row=g.iloc[0];old=od[(od.OrderOriNo==row.oid)&(od.OrderKind==68)].iloc[-1]
  assert old.Volume==row.quantity
  candidate=adds[adds.index==int(row.new_oid)]
  if len(candidate):
   n=candidate.iloc[0];newseq=int(n.BizIndex);nt=int(n.t);price=int(n.price_cents);quantity=int(n.original_qty)
   lf=legs[legs.oid==int(row.new_oid)]
   if len(lf):newseq=min(newseq,int(lf.BizIndex.min()));nt=min(nt,int(lf.t.min()))
   signed=(price-int(row.price))*(1 if row.side=='B' else -1)
   assert ('chase' if signed>0 else 'retreat' if signed<0 else 'same_price')==typ
  else:
   n=groups[groups.oid==int(row.new_oid)].iloc[0];newseq=int(n.firstseq);nt=int(n.t);price=float(n.notional/n.quantity);quantity=int(n.quantity)
   assert typ=='active_no_ADD'
  assert quantity==row.quantity and newseq>old.BizIndex and nt-int(row.t)==row.lag and row.lag<=100
  records.append({'kind':'replacement_case','symbol':600028,'classification':typ,'old_oid':int(row.oid),'new_oid':int(row.new_oid),'cancel_time_ms':int(row.t),'lag_ms':int(row.lag),'quantity':quantity,'old_price_cents':int(row.price),'new_residual_price_or_noADD_vwap_cents':price,'old_cancel_seq':int(old.BizIndex),'new_first_seq':newseq,'new_filled30_fraction':float(row.filled30_fraction),'checked':True})
 (OUT/'verified_cases.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(records,ensure_ascii=False))

if __name__=='__main__':main()
