"""Independent pass: count invalid two-sided quotes inside continuous sessions."""
from collections import defaultdict
import json
from orderbook import OrderBook, apply_market_event, load_stock_events
from four_studies import OUT, DATA, in_session, ms

def main():
 results=[]
 for f in sorted(OUT.glob('stock_*.json')):
  symbol=json.loads(f.read_text())['symbol'];events,_=load_stock_events(DATA,symbol)
  book=OrderBook(symbol,retain_trades=False);stats=defaultdict(int)
  bad=bad_clocks=clocks=0;first=[]
  for i,event in enumerate(events):
   apply_market_event(book,event,stats);t=int(ms([event[0]])[0])
   if not in_session(t):continue
   bid,ask=book._best('B'),book._best('S');valid=bid is not None and ask is not None and bid<ask
   if not valid:
    bad+=1
    if len(first)<3:first.append({'time':event[0],'seq':event[2],'bid':bid,'ask':ask})
   if i+1==len(events) or events[i+1][0]!=event[0]:
    clocks+=1;bad_clocks+=not valid
  r={'symbol':symbol,'continuous_distinct_timestamps':clocks,'invalid_post_message_states':bad,'invalid_end_of_timestamp_states':bad_clocks,'first_invalid':first}
  results.append(r);print(json.dumps(r),flush=True)
 (OUT/'quote_validity_audit.json').write_text(json.dumps({'stocks':len(results),'invalid_post_message_states':sum(r['invalid_post_message_states'] for r in results),'invalid_end_of_timestamp_states':sum(r['invalid_end_of_timestamp_states'] for r in results),'results':results},indent=2),encoding='utf-8')

if __name__=='__main__':main()
