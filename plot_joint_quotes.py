"""Render the descriptive joint quotation study with standard matplotlib."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from plot_fonts import research_font

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'reports'/'joint_quotes'
summary=json.loads((OUT/'summary.json').read_text(encoding='utf-8'))
p=pd.read_csv(OUT/'pairs.csv')
p=p[((p.t<41400000)&(p.t<=41390000))|((p.t>=46800000)&(p.t<=53810000))]
font=research_font()
plt.rcParams.update({'font.family':font.get_name(),'axes.unicode_minus':False,'font.size':11,'figure.facecolor':'#f5f3e4','axes.facecolor':'#fffef5','axes.spines.top':False,'axes.spines.right':False})
fig,axs=plt.subplots(2,2,figsize=(13,9.5))
colors=['#236579','#95b7a2','#c8995d','#a3a8a4']
scope=p[p.cash_scope]
labels=['双边规律＋金额公式','仅金额公式','仅双边规律','两者均无']
counts=[int((scope.linked&scope.cash).sum()),int((~scope.linked&scope.cash).sum()),int((scope.linked&~scope.cash).sum()),int((~scope.linked&~scope.cash).sum())]
ax=axs[0,0];ax.barh(labels[::-1],counts[::-1],color=colors[::-1]);ax.set_title('五只预先指定金额股票：特征是否重合？',loc='left',pad=14)
for i,c in enumerate(counts[::-1]):ax.text(c+max(counts)*.01,i,f'{c:,}',va='center')
ax.set_xlim(0,max(counts)*1.2);ax.set_xlabel('候选双边订单对数；不使用后续撤单筛选')
ax=axs[0,1];metrics=summary['matched']['all']['metrics']
if metrics:
    for i,(label,key) in enumerate([('联合特征','joint'),('匹配普通ADD','control_reweighted')]):
        values=[metrics['fill_frac10000'][key],metrics['cancel_frac10000'][key]]
        values.append(max(0,1-sum(values)));left=0
        for j,(value,name) in enumerate(zip(values,['成交扣减','撤单扣减','仍然挂着'])):
            ax.barh(i,value*100,left=left*100,color=colors[j],label=name if i==0 else None)
            if value>.06:ax.text((left+value/2)*100,i,f'{value*100:.1f}%',ha='center',va='center',color='white' if j==0 else '#263b3a')
            left+=value
    ax.set_yticks([0,1],['联合特征','匹配普通ADD']);ax.set_xlim(0,100);ax.set_xlabel('入场剩余量在未来10秒的去向（逐订单平均，%）')
ax.set_title('粗档位匹配：精确距离对照覆盖率不足\n蓝：成交　绿：撤单　棕：仍在簿上',loc='left',pad=14)
ax=axs[1,0]
for label,data,color,offset in [('联合特征',scope[scope.joint],colors[0],-.18),('其他候选对',scope[~scope.joint],colors[2],.18)]:
    ranks=np.r_[data.b_rank,data.s_rank];bins=[(ranks<=1).mean(),((ranks>=2)&(ranks<=5)).mean(),((ranks>=6)&(ranks<=10)).mean(),((ranks>=11)&(ranks<=20)).mean(),(ranks>20).mean()]
    ax.bar(np.arange(5)+offset,np.array(bins)*100,width=.36,label=label,color=color)
ax.set_xticks(range(5),['第1档','2–5档','6–10档','11–20档','20档外']);ax.set_ylabel('订单比例（%）');ax.set_title('准确重建簿：入场价位的位置',loc='left',pad=14);ax.legend(frameon=False)
ax=axs[1,1];x=scope[(scope.symbol==688256)&scope.joint]
if len(x):
    ax.scatter(x.buy_price/100,x.buy_qty,s=10,alpha=.2,color=colors[0],label='联合特征中的买单')
    price=np.linspace(x.buy_price.min()/100,x.buy_price.max()/100,500)
    ax.plot(price,np.ceil(300000/price),color=colors[2],lw=1.6,label='ceil(30万元／报价)')
ax.set_title('688256：数量随价格变化的现金约束',loc='left',pad=14);ax.set_xlabel('买单报价（元）');ax.set_ylabel('股数');ax.legend(frameon=False)
fig.suptitle('双边联动 × 固定金额 × 共同撤换\n2026-09-23 · 50股扫描 · 事后机制研究',fontsize=18,x=.06,ha='left',y=.99)
fig.text(.06,.015,'识别只用当前及过去消息；后续撤单是结果。金额假设来自此前同日探索，上午／下午不是独立验证。\n粗匹配556/664笔；精确距离仅12/664笔，无法排除位置混杂。档位以每笔ADD前的逐笔历史簿计算。',fontsize=9,color='#5c6865')
fig.tight_layout(rect=(.02,.07,.99,.91),h_pad=3,w_pad=2)
fig.savefig(OUT/'overview.png',dpi=170)
print(OUT/'overview.png')
