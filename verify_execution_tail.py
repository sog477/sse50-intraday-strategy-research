"""Verify the post-15:00 competition messages omitted by the trading clock.

All are status-only in this dataset; no strategy window extends to these records.
Keep the original replay count and report the verified tail separately.
"""
import json
import pyarrow.parquet as pq
from execution_backtest import DATA,OUT
from orderbook import dataset_date

def main():
 table=pq.read_table(DATA/f'ord_{dataset_date(DATA)}.parquet',filters=[('Time','>',150000000)])
 rows=table.to_pylist()
 if any(r['OrderKind']!=83 or r['Volume']!=0 for r in rows):raise ValueError('non-status postclose records need full replay')
 info={'count':len(rows),'all_zero_volume_status':True,'records':rows,
       'note':'verified separately after main replay through15:00; status branch only increments statistics, no book changes; outside all trading tasks'}
 (OUT/'postclose_status_verification.json').write_text(json.dumps(info,indent=2),encoding='utf-8')
 print(len(rows),'postclose status records, no book/strategy effect')

if __name__=='__main__':main()
