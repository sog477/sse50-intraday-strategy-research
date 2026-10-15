"""Optional plotting for order_patterns.py results; needs matplotlib/pandas."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

out=Path('reports/order_patterns')
plt.rcParams.update({'font.sans-serif':['Microsoft YaHei','SimHei','DejaVu Sans'],
                     'axes.unicode_minus':False,'font.size':11})
tails=pd.read_csv(out/'price_tails.csv')
tails['fraction']=tails.orders/tails.groupby(['symbol','side']).orders.transform('sum')
tails=tails.groupby(['side','tail']).fraction.mean().unstack(0)*100
controls=pd.read_csv(out/'exposure_controls.csv')
controls=controls[(controls.symbol!=601166)&(controls.lag_ms==1000)]
examples=pd.read_csv(out/'periodic_examples.csv')
rapid=pd.read_csv(out/'rapid_cancel_examples.csv')
fig,axes=plt.subplots(2,2,figsize=(15,10),facecolor='#f8f5dd')
for ax in axes.flat:
    ax.set_facecolor('#fffcec'); ax.spines[['top','right']].set_visible(False)
x=np.arange(10);ax=axes[0,0]
ax.bar(x-.2,tails.B,.38,label='买单',color='#bf5650')
ax.bar(x+.2,tails.S,.38,label='卖单',color='#448976')
ax.set(xticks=x,xlabel='价格分位末位（0 = 整角）',ylabel='每股等权订单占比 (%)',title='整数价有聚集；末位数字不能识别交易者')
ax.axhline(10,color='#999',ls=':',lw=1);ax.legend(frameon=False)
ax=axes[0,1]
vals=[controls.observed_round.mean(),controls.expected_round.mean(),
      controls.observed_priority.mean(),controls.expected_priority.mean()]
ax.bar(np.arange(4),np.array(vals)*100,color=['#bf5650','#b7b4a0','#448976','#b7b4a0'])
ax.set(xticks=np.arange(4),xticklabels=['整角：实际','整角：机会基准','买1 / 卖9：实际','买1 / 卖9：基准'],
       ylabel='控制后每股等权占比 (%)',title='控制同股、方向、时间、价格与报价距离后')
for i,v in enumerate(vals):ax.text(i,v*100+.25,f'{v*100:.2f}%',ha='center')
ax.text(.5,.02,'49 股；报价先于订单 1 秒；非因果识别',transform=ax.transAxes,ha='center',fontsize=9)
ax=axes[1,0]
g=examples[examples.case_id=='601668-14']
seconds=(g.raw_time//10000000*3600+g.raw_time//100000%100*60+g.raw_time//1000%100+g.raw_time%1000/1000)
seconds=seconds-seconds.iloc[0]
for sec in seconds:
    ax.plot([sec,sec+33],[71500,71500],color='#bf5650',lw=6)
    ax.scatter(sec,71500,color='#bf5650',marker='o',s=45)
    ax.scatter(sec+33,71500,color='#163949',marker='x',s=55)
ax.set(xlabel='从 14:40:09.350 开始经过的秒数',ylabel='同价卖单股数',ylim=(0,85000),
       title='601668：每 45 秒报 71,500 股，约 33 秒全撤')
ax.text(.5,.1,'8 笔全部零成交；周期挂量不等于执行卖压',transform=ax.transAxes,ha='center')
ax=axes[1,1]
g=rapid[rapid.cluster=='601328:B:750:400:0']
times=pd.to_timedelta(g.time).dt.total_seconds();times=times-times.iloc[0]
ax.vlines(times,0,g.lifetime_ms,color='#448976',lw=3)
ax.scatter(times,g.lifetime_ms,color='#448976')
ax.set(xlabel='从 09:35:34.420 开始经过的秒数',ylabel='存续时间 (毫秒)',ylim=(0,140),
       title='601328：7.50 元 / 400 股反复报单，90–100ms 全撤')
ax.text(.5,.06,'整角价、整数数量也会出现自动撤换式行为',transform=ax.transAxes,ha='center')
fig.suptitle('2026-09-23 上证50：从报价行为找市场机制，不用尾数判身份',fontsize=17,y=.98)
fig.text(.5,.015,'公开逐笔流无账户/参与者标识；周期案例来自全市场预设扫描；行情时间精度和快照滞后影响解释。',ha='center',fontsize=9)
fig.tight_layout(rect=(0,.04,1,.95))
fig.savefig(out/'overview.png',dpi=140)
plt.close(fig)
