"""Static figures from completed whole-day paired execution experiment."""
from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from plot_fonts import research_font

OUT=Path(__file__).resolve().parent/'reports'/'execution_day'
s=json.loads((OUT/'summary.json').read_text(encoding='utf-8'))
font=research_font()
plt.rcParams.update({'font.family':font.get_name(),'axes.unicode_minus':False,'font.size':11,
 'axes.spines.top':False,'axes.spines.right':False,'savefig.facecolor':'white'})
names={'immediate':'立即主动','passive':'被动等待','imbalance':'信号切换'}
colors={'immediate':'#a3afb3','passive':'#d09558','imbalance':'#287e8e'}
policies=['immediate','passive','imbalance']
g={r['policy']:r for r in s['groups'] if r['model']=='with_residual' and r['delay_ms']==0}
fig,axs=plt.subplots(2,2,figsize=(14,10));fig.subplots_adjust(top=.86,bottom=.17,hspace=.64,wspace=.34)
fig.suptitle('盘口信号执行策略：50只股票全天对照',fontsize=22,fontweight='bold',y=.97)
fig.text(.5,.915,'2026-09-23文件标签 · 每30秒一组任务 · 每种模型/延迟47,200个买卖任务 · 未调阈值',ha='center',color='#555')

def style(ax,title,y):
 ax.set_title(title,loc='left',fontweight='bold',fontsize=13,pad=15);ax.set_ylabel(y);ax.grid(axis='y',alpha=.17);ax.set_axisbelow(True)
def bars(ax,values):
 ax.bar([names[p] for p in policies],values,color=[colors[p] for p in policies],width=.58)
 lo=min(0,min(values));hi=max(0,max(values));pad=max((hi-lo)*.06,.05)
 for i,v in enumerate(values):ax.text(i,v+(pad if v>=0 else -pad),f'{v:+.2f}',ha='center',va='bottom' if v>=0 else 'top',fontsize=12)
 ax.set_ylim(lo-pad*4,hi+pad*4);ax.axhline(0,color='#777',lw=.8)

ax=axs[0,0];bars(ax,[g[p]['task_cost_bp'] for p in policies]);style(ax,'① 全部任务的含费执行成本','股票等权成本（bp，越低越好）')
ax.text(.01,-.27,'主口径：真实成交＋新反向残量，动作延迟0ms\n未完成量按截止中间价计机会成本，不假定成交',transform=ax.transAxes,color='#666',fontsize=10)
ax=axs[0,1]
for p in policies:
 rows=sorted([r for r in s['groups'] if r['model']=='with_residual' and r['policy']==p],key=lambda x:x['delay_ms'])
 ax.plot([r['delay_ms'] for r in rows],[r['complete_pct'] for r in rows],'o-',color=colors[p],label=names[p])
style(ax,'② 保护价下，是否能完成任务？','任务全部完成率（%）');ax.set_xlabel('决策到动作生效延迟（ms）');ax.legend(frameon=False,fontsize=10,loc='center right',bbox_to_anchor=(1,.35));ax.set_xticks([0,100,500])
ax.text(.01,-.38,'保护价固定为起点对手价外2分；成交数量不足\n不会被删除，延迟为简化的整体撤换动作延迟',transform=ax.transAxes,color='#666',fontsize=10)
ax=axs[1,0];positions=[];vals=[];lows=[];highs=[];labels=[]
for i,model in enumerate(['with_residual','tape_only']):
 for j,base in enumerate(['immediate','passive']):
  r=next(r for r in s['paired_comparisons'] if r['model']==model and r['delay_ms']==0 and r['baseline']==base)
  v=r['equal_stock_saving_bp'];lo,hi=r['within_day_95_interval'];positions.append(i*3+j);vals.append(v);lows.append(v-lo);highs.append(hi-v)
  labels.append(('成交＋残量' if i==0 else '仅成交流')+'\n对比'+names[base])
ax.errorbar(positions,vals,yerr=[lows,highs],fmt='o',capsize=6,color='#287e8e',markersize=7);ax.axhline(0,color='#777',ls='--');ax.set_xticks(positions,labels)
style(ax,'③ 信号策略究竟省了多少？','基准成本−信号成本（bp，正数表示节省）')
ax.text(.01,-.30,'相同股票/时刻/方向/数量逐任务配对；全部任务\n区间来自股票与共同10分钟时段重抽样，仅限当日',transform=ax.transAxes,color='#666',fontsize=10)
ax=axs[1,1]
r=next(r for r in s['paired_comparisons'] if r['model']=='with_residual' and r['delay_ms']==0 and r['baseline']=='passive')
values=[r['gross_saving_bp'],r['extra_fee_bp'],r['equal_stock_saving_bp']]
ax.bar(['毛成本节省','额外实际费用','净成本节省'],values,color=['#287e8e','#d09558','#a3afb3'],width=.58)
for i,v in enumerate(values):ax.text(i,v+(.025 if v>=0 else -.025),f'{v:+.3f}',ha='center',va='bottom' if v>=0 else 'top')
ax.set_ylim(-.28,.46);ax.axhline(0,color='#777',lw=.8)
style(ax,'④ 相对被动等待：费用差异很关键','股票等权差异（bp）')
ax.text(.01,-.30,'净节省＝毛节省−额外费用；更多任务成交也会\n增加费用，不应把差异全部归因于撤单重报',transform=ax.transAxes,color='#666',fontsize=10)
fig.text(.02,.025,'主板100股、科创板200股；买卖为独立实验，非同一资金/持仓账户。固定历史路径、零市场冲击；单日结果不是样本外验证。',fontsize=10,color='#666')
fig.savefig(OUT/'overview.png',dpi=180);plt.close(fig)
print('Saved overview.png')
