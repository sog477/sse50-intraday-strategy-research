"""Static research figures; reads saved summaries only (matplotlib runtime)."""
from pathlib import Path
import csv,json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from plot_fonts import research_font

OUT=Path(__file__).resolve().parent/'reports'/'four_studies'
font=research_font()
plt.rcParams.update({'font.family':font.get_name(),'axes.unicode_minus':False,'font.size':11,'axes.spines.top':False,'axes.spines.right':False,'savefig.facecolor':'white'})
s=json.loads((OUT/'summary.json').read_text(encoding='utf-8'))

def labels(ax,title,y):
 ax.set_title(title,loc='left',fontsize=13,fontweight='bold',pad=15)
 ax.set_ylabel(y);ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True)

def bars(ax,vals,names,colors,fmt='{:.2f}'):
 ax.bar(names,vals,color=colors,width=.55)
 lo=min(0,min(vals));hi=max(vals);pad=max((hi-lo)*.075,.05)
 for i,v in enumerate(vals):ax.text(i,v+(pad if v>=0 else -pad),fmt.format(v),ha='center',va='bottom' if v>=0 else 'top',fontsize=12)
 ax.set_ylim(lo-pad*3,hi+pad*5)

fig,axs=plt.subplots(2,2,figsize=(14,10));fig.subplots_adjust(top=.87,bottom=.17,hspace=.70,wspace=.32)
fig.suptitle('单日逐笔研究：四个问题的证据强弱',fontsize=22,fontweight='bold',y=.97)
fig.text(.5,.915,'2026-09-23（文件标签） · 50只股票 · 10,066,831条竞价消息 · 所有价格来自逐笔重建簿',ha='center',color='#555555')
ax=axs[0,0];r=s['queue']['matched']['metrics']['cancel3000'];d=r['difference_a_minus_b']*100;low,high=np.array(r['within_day_95_interval'])*100
ax.errorbar([d],[0],xerr=[[d-low],[high-d]],fmt='o',color='#816484',capsize=8,markersize=10)
ax.axvline(0,color='#777777',ls='--');ax.set_yticks([]);ax.set_ylim(-1,1);ax.set_xlim(-1.3,2.8)
ax.set_xlabel('自己3秒内先撤单的概率差（百分点）');ax.set_title('① 队后撤 vs 队前撤：证据不足',loc='left',fontsize=13,fontweight='bold',pad=15)
ax.text(.03,.82,f'差值 +{d:.2f}；区间 [{low:.2f}, {high:.2f}]',transform=ax.transAxes)
ax.text(.03,.12,'可比样本仅11只股票、1,106次观察\n更细控制后无可比层，不能下定论',transform=ax.transAxes,color='#666666')
ax=axs[0,1];r=s['maker']['models']['tape_only']['entry_comparison']['metrics']['fill_any']
bars(ax,[r['equal_stock_b']*100,r['equal_stock_a']*100],['顺盘口方向','逆盘口方向'],['#277e8c','#d28b50'],fmt='{:.1f}%')
labels(ax,'② 信号方向较好，挂单却更难成交','30秒内至少部分成交（%）')
ax.text(.02,-.26,'控制股票、方向、半小时时段与价差；50只股票\n两种成交假设下结果接近，属于独立虚拟挂单',transform=ax.transAxes,color='#666666',fontsize=10)
ax=axs[1,0];r=s['shocks']['matched']['metrics']['large_move']
bars(ax,[r['equal_stock_b']*100,r['equal_stock_a']*100],['相邻档差1分','相邻档差≥2分'],['#277e8c','#d28b50'],fmt='{:.2f}%')
labels(ax,'③ 跳价与盘口断层的关系更直接','即时中间价顺成交方向跳≥2分（%）')
ax.text(.02,-.26,'27只股票有可比层；已控制成交量/最优档深度等\n这是冲击描述，不能直接解释为事前可交易收益',transform=ax.transAxes,color='#666666',fontsize=10)
ax=axs[1,1];rs=[r for r in s['replacement']['shift_diagnostics'] if r['window']==100 and not r['symmetric']]
bars(ax,[rs[0]['raw_unique_fraction']*100,rs[0]['null_unique_fraction']*100,rs[1]['raw_unique_fraction']*100,rs[1]['null_unique_fraction']*100],['真实\n60秒对照','错移\n60秒','真实\n300秒对照','错移\n300秒'],['#277e8c','#b4bcc0','#277e8c','#b4bcc0'],fmt='{:.2f}%')
labels(ax,'④ 同量撤旧报新，多于错时巧合','100毫秒内双向唯一候选占比（%）')
ax.text(.02,-.37,'真实/错移按相同起点总体比较；两列错移总体略不同\n均为匿名候选关联，不能据此认定同一账户',transform=ax.transAxes,color='#666666',fontsize=10)
fig.text(.02,.025,'区间为当日股票与半小时时段重抽样；非跨日验证。指标定义、共同支撑样本与限制详见 REPORT.md。',color='#666666',fontsize=10)
fig.savefig(OUT/'overview.png',dpi=180);plt.close(fig)

fig,axs=plt.subplots(1,2,figsize=(13,5.6));fig.subplots_adjust(top=.80,bottom=.22,wspace=.35)
fig.suptitle('看对方向 ≠ 限价单能拿到这段涨幅',fontsize=21,fontweight='bold',y=.96)
fig.text(.5,.875,'顺盘口信号：同侧最优档挂量至少为对侧4倍；主板100股、科创板200股，固定价格等待30秒',ha='center',color='#555555',fontsize=11)
rows=list(csv.DictReader((OUT/'maker_selection.csv').open(encoding='utf-8')));x={r['fill_status']:r for r in rows if r['signal']=='with'}
overall=next(r for r in s['maker']['groups'] if r['model']=='tape_only' and r['signal']=='with')
bars(axs[0],[overall['future30_bp'],float(x['filled']['future30_bp']),float(x['unfilled']['future30_bp'])],['全部5,065单','成交1,854单','未成交3,211单'],['#80979a','#bd705a','#277e8c'],fmt='{:+.2f}')
labels(axs[0],'同一个进场时钟起算：未来30秒','有利方向中间价变化（bp）');axs[0].axhline(0,color='#777777',lw=.8)
axs[0].text(.02,-.30,'原始观察均值；成交/未成交是事后分组\n控制股票、方向、时段和价差后，差值仍为负',transform=axs[0].transAxes,color='#666666',fontsize=10)
r=s['maker']['models']['tape_only']['filled_comparison']['metrics']['markout30000_bp']
bars(axs[1],[r['equal_stock_b'],r['equal_stock_a']],['顺盘口后成交','逆盘口后成交'],['#277e8c','#d28b50'],fmt='{:+.2f}')
labels(axs[1],'成交价到成交后30秒的中间价','成交后有利方向价差（bp，毛值）');axs[1].axhline(0,color='#777777',lw=.8)
axs[1].text(.02,-.30,'成交样本中匹配后38只股票；这项结果与简单的\n“越易成交越差”排序相反，不能硬套原论文结论',transform=axs[1].transAxes,color='#666666',fontsize=10)
fig.savefig(OUT/'maker_selection.png',dpi=180);plt.close(fig)
print('Saved overview.png and maker_selection.png')
