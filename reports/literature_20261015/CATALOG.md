# 38条定向文献目录：逐笔订单、队列、撤换与流动性

核验日期：2026-10-15。37条核对了至少一手摘要或原稿相关内容；P35仅确认书目存在，未作为结论来源。没有声称逐篇通读或复现。

核验层级：F＝已打开全文并核相关段落，非逐页通读；A＝一手摘要/正文片段已核，未作全文核对；M＝仅核书目。适配：A＝现有字段可做当日分析；B＝可做有边界的改写；C＝关键识别条件缺失，不能直接复现。适配A也不代表一天足以验证普遍规律。

## 阅读方式

先看[研究选题与阅读导图](READING_GUIDE.md)。以下“论文切口”是原文的简短概括；“本地问题”是我们的改写提案，不是作者做过上证50或本数据的声明。工作论文、预印本与期刊版本明确区分。同一论文不同版本只计一次。

## 优先读

### P01 · The Market Maker's Dilemma: Navigating the Fill Probability vs. Post-Fill Returns Trade-Off

Jakob Albers; Mihai Cucuringu; Sam Howison; Alexander Y. Shestopaloff。**2025；arXiv v2**。核验 **F**；适配 **B**。

- 论文切口：实盘小额挂单实验揭示成交概率与成交后收益的冲突。
- 本地问题：在同样盘口下，买单越容易成交，成交后1/5/30秒中间价是否越不利？
- 边界：币安永续与A股制度不同；历史虚拟成交不能替代原文实盘实验。
- 来源：[原始页面/原稿](https://arxiv.org/abs/2502.18625)

### P02 · What really causes large price changes?

J. Doyne Farmer; Laszlo Gillemot; Fabrizio Lillo; Szabolcs Mike; Anindya Sen。**2003预印本；2004修订**。核验 **F**；适配 **A**。

- 论文切口：伦敦订单簿研究把大幅跳价与空价档、流动性波动联系起来。
- 本地问题：小成交遇到大断层，是否比大成交遇到密集盘口产生更大跳价？
- 边界：区分机械价格变化归因与真正向前预测；不把外国经验视为本地结论。
- 来源：[原始页面/原稿](https://arxiv.org/abs/cond-mat/0312703)

### P03 · The determinants of limit order cancellations

Petter Dahlström; Björn Hagströmer; Lars L. Nordén。**2023在线；2024卷期；Financial Review**。核验 **F**；适配 **B**。

- 论文切口：区分成交机会与成交时利润两种撤单动机，拆分订单前后队列深度。
- 本地问题：同价队前与队后挂量分别减少时，撤单倾向是否不同？队后新增能否延长存续？
- 边界：原文含交易公司及库存字段；我们只能复现匿名队列部分。
- 来源：[原始页面/原稿](https://onlinelibrary.wiley.com/doi/10.1111/fire.12363)

### P04 · Technology and liquidity provision: The blurring of traditional definitions

Joel Hasbrouck; Gideon Saar。**2009；Journal of Financial Markets；链接为作者原稿**。核验 **F**；适配 **B**。

- 论文切口：短命限价单可以表现为追价和寻找潜在流动性，而非传统耐心挂单。
- 本地问题：撤单后是追价、原价补回、移到远档，还是退出？
- 边界：无法确认同一交易者；更换原始ID后的连接属于推断。
- 来源：[原始页面/原稿](https://pages.stern.nyu.edu/~jhasbrou/Research/Working%20Papers/HS6.pdf)

### P05 · Low-latency trading

Joel Hasbrouck; Gideon Saar。**2013；Journal of Financial Markets**。核验 **F**；适配 **B**。

- 论文切口：用提交—撤销—重挂消息链度量低延迟活动，并讨论错误链接。
- 本地问题：把我们的周期案例扩展成匿名报撤链，比较链最终成交或转主动的比例。
- 边界：没有参与者标识；时间精度及全成交无ADD会限制连接，不照抄毫秒阈值。
- 来源：[原始页面/原稿](https://pages.stern.nyu.edu/~jhasbrou/Research/lowLatencyTrading/lowLatencyTradingHasbrouckSaarJFM.pdf)

### P06 · A Model for Queue Position Valuation in a Limit Order Book

Ciamac C. Moallemi; Kai Yuan。**2016初稿；2017修订；工作论文**。核验 **F**；适配 **B**。

- 论文切口：队列位置兼有成交时收益与未来优先权的价值。
- 本地问题：同价前排与后排，成交率和成交后价格漂移各差多少？撤单重排代价多大？
- 边界：模拟订单受固定历史路径和排队假设限制；不把工作论文写成已核定的期刊文章。
- 来源：[原始页面/原稿](https://moallemi.com/ciamac/papers/queue-value-2016.pdf)

### P07 · Queuing Uncertainty of Limit Orders

Bart Zhou Yueshen。**2025在线首发；Crossref登记2026年6月卷期；Management Science**。核验 **F**；适配 **B**。

- 论文切口：理论上排队位置不确定可导致过度挂量及随后修订。
- 本地问题：短时间密集入场后，后排是否更快撤销？汇总深度是否短暂超调？
- 边界：看不到交易者当时的队列认知与延迟；只能检验可观测含义。
- 来源：[原始页面/原稿](https://pubsonline.informs.org/doi/10.1287/mnsc.2023.03371)

### P08 · The "Neutrinos" of the Order Book: Pervasive, Weakly Interacting Order Flow and its Consequences

Jakob Albers; Mihai Cucuringu; Sam Howison; Alexander Y. Shestopaloff。**2026；SSRN工作论文；登记号7162966，较早版本6250738**。核验 **A**；适配 **C**。

- 论文切口：Hyperliquid完整消息研究包含公开簿外的拒单，并讨论预先在途的补价。
- 本地问题：可借鉴补价事件形态研究，不能判断补单究竟在冲击前已发送还是冲击后响应。
- 边界：缺拒单、发送时间、接收确认与post-only标志；摘要经登记页检索及作者主页交叉核对，全文未取得。
- 来源：[原始页面/原稿](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7162966)；[书目交叉核对](https://math.ucla.edu/~mihai/index.html)

## 中国直接相关

### P09 · Limit-order book resiliency after effective market orders: Spread, depth and intensity

Hai-Chuan Xu; Wei Chen; Xiong Xiong; Wei Zhang; Wei-Xing Zhou; H. Eugene Stanley。**2016预印本；2017修订**。核验 **F**；适配 **A**。

- 论文切口：中国股票研究区分不同激进程度成交后的价差、深度和报单强度恢复。
- 本地问题：吃穿一档后，成交冲击和撤单冲击的补回速度是否不同？
- 边界：历史申报类型缺失；用可观察的成交与盘口变化分类，不伪造原始市价类型。
- 来源：[原始页面/原稿](https://arxiv.org/abs/1602.00731)

### P10 · Empirical regularities of opening call auction in Chinese stock market

Gao-Feng Gu; Fei Ren; Xiao-Hui Ni; Wei Chen; Wei-Xing Zhou。**2009预印本；2010期刊版本**。核验 **F**；适配 **A**。

- 论文切口：2003年深圳22股开盘集合研究数量聚集、相对昨收报价和剩余簿形状。
- 本地问题：集合成交价确定后，各报价距离、整角偏好与留下的挂量是什么关系？
- 边界：历史盲式集合制度不同于现行；一天仅50次开盘，不作一般制度因果结论。
- 来源：[原始页面/原稿](https://arxiv.org/abs/0905.0582)

### P11 · Empirical regularities of order placement in the Chinese stock market

Gao-Feng Gu; Wei Chen; Wei-Xing Zhou。**2007预印本；2008期刊版本**。核验 **A**；适配 **A**。

- 论文切口：深圳23股研究集合、冷静期及连续竞价的相对报价差异。
- 本地问题：固定金额循环报价与其他单子的相对最优价距离分布是否不同？
- 边界：连续竞价ADD是剩余单，不能代表所有原始申报，尤其不含全即时成交主动单。
- 来源：[原始页面/原稿](https://arxiv.org/abs/0712.0912)

### P12 · Empirical properties of inter-cancellation durations in the Chinese stock market

Gao-Feng Gu; Xiong Xiong; Wei Zhang; Yong-Jie Zhang; Wei-Xing Zhou。**2014；arXiv预印本**。核验 **A**；适配 **A**。

- 论文切口：研究深圳18股撤单之间的事件时间间隔。
- 本地问题：3秒、45秒周期，在按事件数而非钟表秒数计时后是否仍突出？
- 边界：一天可描述周期，不能可靠确立长期记忆、幂律或跨日稳定性。
- 来源：[原始页面/原稿](https://arxiv.org/abs/1403.3478)

### P13 · Quantifying bid-ask spreads in the Chinese stock market using limit-order book data: Intraday pattern, probability distribution, long memory, and multifractal nature

Gao-Feng Gu; Wei Chen; Wei-Xing Zhou。**2006年底预印本；2007期刊版本**。核验 **A**；适配 **A**。

- 论文切口：比较成交前、最优价更新时与固定时钟采样下的价差。
- 本地问题：同一只股票按秒平均与按成交平均，得到的价差是否不同？
- 边界：一天的时间曲线只是当日图景；不重复做单日长记忆显著性。
- 来源：[原始页面/原稿](https://arxiv.org/abs/physics/0701017)

### P14 · Linear and nonlinear correlations in order aggressiveness of Chinese stocks

Peng Yue; Hai-Chuan Xu; Wei Chen; Xiong Xiong; Wei-Xing Zhou。**2017；arXiv预印本**。核验 **A**；适配 **B**。

- 论文切口：中国43股研究申报激进程度的序列相关。
- 本地问题：相同方向、相似距离的连续订单，是同价补回还是逐步追价？
- 边界：无法完整恢复无ADD主动单的限价；只分析可观察的剩余挂单激进程度。
- 来源：[原始页面/原稿](https://arxiv.org/abs/1707.05604)

### P15 · An empirical analysis of the Shanghai and Shenzhen limit order books

Huimin Chung; Cheng Gao; Jie Lu; Bruce Mizrach。**2013；Economic Modelling 34, 37–41**。核验 **A**；适配 **B**。

- 论文切口：直接研究沪深订单簿信息与交易冲击。
- 本地问题：不同价格、交易强度和盘口形状的股票，其成交冲击有何差异？
- 边界：正式版四作者；2009三作者工作稿不是另一篇。旧文制度叙述不能直接用于2026。
- 来源：[原始页面/原稿](https://doi.org/10.1016/j.econmod.2012.11.055)；[书目交叉核对](https://econweb.rutgers.edu/mizrach/cv.pdf)

### P16 · An analysis of impact of cancellation activity on market quality: Evidence from China

Gang Chu; Yongjie Zhang; Xiaotao Zhang。**2021；Economic Modelling 102, 105560**。核验 **A**；适配 **B**。

- 论文切口：以五档与逐笔成交构造撤单代理并研究市场质量。
- 本地问题：我们有真实D消息：代理估计与真实撤单差多少？哪些补单会混淆代理？
- 边界：不能把相关性解释成撤单改善市场的因果证据；作者及年份另核Crossref注册。
- 来源：[原始页面/原稿](https://doi.org/10.1016/j.econmod.2021.105560)；[书目交叉核对](https://api.crossref.org/works/10.1016/j.econmod.2021.105560)

### P17 · Call Auction Transparency and Market Liquidity: Evidence from China

Dionigi Gerace; Qigui Liu; Gary Gang Tian; Willa Zheng。**2015；International Review of Finance**。核验 **A**；适配 **C**。

- 论文切口：研究中国集合竞价透明度变化与市场流动性。
- 本地问题：可启发集合后剩余簿与开盘连续竞价的接续研究。
- 边界：我们没有透明度改革前后样本；无法复制制度冲击识别。
- 来源：[原始页面/原稿](https://doi.org/10.1111/irfi.12047)

### P18 · An empirical behavioral order-driven model with price limit rules

Gao-Feng Gu; Xiong Xiong; Hai-Chuan Xu; Wei Zhang; Yongjie Zhang; Wei Chen; Wei-Xing Zhou。**2021；Financial Innovation 7, 70**。核验 **F**；适配 **B**。

- 论文切口：以中国订单行为规律建立含价格限制的报单及撤单模拟。
- 本地问题：用真实报单、撤单与补回规律校准模拟行情，而不只复刻价格波动。
- 边界：参数不能靠一天得到稳健估计；机制实验不是历史路径回放的事实结果。
- 来源：[原始页面/原稿](https://doi.org/10.1186/s40854-021-00288-4)

## 机制与基线

### P19 · The Price Impact of Order Book Events

Rama Cont; Arseniy Kukanov; Sasha Stoikov。**2010预印本；2014 Journal of Financial Econometrics**。核验 **A**；适配 **A**。

- 论文切口：供需失衡同时纳入限价单、成交和撤单，比单看成交量更完整。
- 本地问题：将OFI拆成成交、撤单和补单部分，哪种变化与随后跳价相关？
- 边界：同期解释不等于未来预测；作为基线，不包装成新发现。
- 来源：[原始页面/原稿](https://arxiv.org/abs/1011.6402)

### P20 · Queue Imbalance as a One-Tick-Ahead Price Predictor in a Limit Order Book

Martin D. Gould; Julius Bonart。**2015；arXiv预印本**。核验 **A**；适配 **A**。

- 论文切口：下一次中间价方向与队列失衡的关系随tick环境而不同。
- 本地问题：同样失衡，来自长存续队列还是反复撤换队列，预测力是否不同？
- 边界：next-tick标签与30秒标签不同；重叠标签及同股依赖须处理。
- 来源：[原始页面/原稿](https://arxiv.org/abs/1512.03492)

### P21 · Tick Size Reduction and Price Clustering in a FX Order Book

Mehdi Lallouache; Frédéric Abergel。**2013预印本；2014修订**。核验 **A**；适配 **B**。

- 论文切口：外汇tick细化后旧价位聚集，并讨论领先聚集价一tick的订单。
- 本地问题：整角队列是否更长寿？改善一分钱的订单是否真正获得更好成交？
- 边界：我们此前没有支持普遍抢整角前一分；不能用价尾判定人工身份。
- 来源：[原始页面/原稿](https://arxiv.org/abs/1307.5440)

### P22 · Order Flows and Limit Order Book Resiliency on the Meso-Scale

Kyle Bechler; Michael Ludkovski。**2017；arXiv预印本**。核验 **A**；适配 **A**。

- 论文切口：按成交量分桶研究新增、撤销和深层盘口形状。
- 本地问题：固定时间与固定成交量窗口，对撤换周期及补回的判断是否一致？
- 边界：同一数据换时钟不增加独立样本；桶阈值仅用此前信息确定。
- 来源：[原始页面/原稿](https://arxiv.org/abs/1708.02715)

### P23 · The information content of an open limit-order book

Charles Cao; Oliver Hansch; Xiaoxin Wang。**2009；Journal of Futures Markets**。核验 **A**；适配 **A**。

- 论文切口：澳大利亚市场研究最优档以外的增量信息。
- 本地问题：远档现金约束报价，是价格信息还是纯粹报价维护？控制近档后还剩多少？
- 边界：深档与股价共动本身不证明深档预测价格；特征冻结后再向前检验。
- 来源：[原始页面/原稿](https://doi.org/10.1002/fut.20334)

### P24 · Resiliency of the limit order book

Danny K. Lo; Anthony D. Hall。**2015；Journal of Economic Dynamics and Control**。核验 **A**；适配 **A**。

- 论文切口：区分交易及撤单流动性冲击后的恢复过程。
- 本地问题：同样减少一万股，成交减少与撤单减少是否引来不同补回？
- 边界：冲击前的距离、价差和可见挂量需要匹配；尚无市场因果实验。
- 来源：[原始页面/原稿](https://doi.org/10.1016/j.jedc.2015.09.012)

### P25 · Why is order flow so persistent?

Bence Tóth; Imon Palit; Fabrizio Lillo; J. Doyne Farmer。**2011；arXiv预印本**。核验 **A**；适配 **C**。

- 论文切口：利用会员标识区分拆单与不同参与者同向交易。
- 本地问题：我们的同量同向序列可作行为线索，不能完成拆单与羊群的身份分解。
- 边界：缺会员/账户ID；连续同向不等于发现同一母单。
- 来源：[原始页面/原稿](https://arxiv.org/abs/1108.1632)

### P26 · Cross-Impact of Order Flow Imbalance in Equity Markets

Rama Cont; Mihai Cucuringu; Chao Zhang。**2021预印本；2023 Quantitative Finance**。核验 **A**；适配 **B**。

- 论文切口：区分多层OFI、同期跨股解释与滞后跨股预测。
- 本地问题：某股的深度撤换，是否在剔除市场共同波动后仍领先另一股？
- 边界：一天50股两两筛选极易过拟合；须约束配对和严格处理时间标签、市场因子。
- 来源：[原始页面/原稿](https://arxiv.org/abs/2112.13213)

### P27 · Queuing and inventories in limit order markets

Corey Garriott; Vincent van Kervel; Marius Zoican。**2025；Journal of Financial Markets**。核验 **A**；适配 **C**。

- 论文切口：队列与库存管理存在冲突，靠后做市商可被挤出流动性供给。
- 本地问题：可借鉴队列依赖的撤单形态，不能声称识别库存冲击。
- 边界：缺真实交易商库存与身份；双边数量不对称不能直接当库存。
- 来源：[原始页面/原稿](https://mariuszoican.com/publication/tmx_hft/)

## 重要但数据受限

### P28 · Cross-Venue Liquidity Provision: High Frequency Trading and Ghost Liquidity

Hans Degryse; Rudy De Winne; Carole Gresse; Richard Payne。**2020；ESMA Working Paper No.4**。核验 **F**；适配 **C**。

- 论文切口：跨场所同一供给者重复挂单会使简单相加的可见容量高估可执行总量。
- 本地问题：提示区分撤换、跨场所重复容量与真正可同时执行的容量。
- 边界：仅一交易所且无跨场所统一身份，不能把我们的重挂称为该文ghost liquidity。
- 来源：[原始页面/原稿](https://www.esma.europa.eu/sites/default/files/library/esma_wp_4_2020_hft_and_ghost_liquidity.pdf)

### P29 · Competition for Order Flow with Fast and Slow Traders

Vincent van Kervel。**2015；Review of Financial Studies**。核验 **A**；适配 **C**。

- 论文切口：跨市场成交可伴随另一市场撤单，模型解释快慢交易者竞争。
- 本地问题：启发先查公共行情驱动，再讨论跨股或跨市场同步撤单。
- 边界：没有同一证券其他场所的订单簿，不能复现跨场所结论。
- 来源：[原始页面/原稿](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2021988)

### P30 · CME Iceberg Order Detection and Prediction

Dmitry Zotikov; Anton Antonov。**2019；arXiv预印本**。核验 **A**；适配 **B**。

- 论文切口：利用CME消息语义及成交后刷新，识别原生/合成冰山并估计隐含量。
- 本地问题：只借鉴成交触发的同价补单与撤单触发补单之间的区分。
- 边界：SSE消息不是CME冰山协议；不能凭同价重挂认定冰山或恢复隐藏总量。
- 来源：[原始页面/原稿](https://arxiv.org/abs/1909.09495)

### P31 · Discrete Prices, Discrete Quantities, and the Optimal Price of a Stock

Sida Li; Mao Ye。**2023稿；SSRN修订至2026；工作论文**。核验 **A**；适配 **B**。

- 论文切口：研究价格tick和股数lot两种离散约束的共同作用。
- 本地问题：同样金额约束下，主板整百与科创板非整百报量造成何种金额超调？
- 边界：美国背景和最优股价结论不能直接搬用；单日也不能研究拆股因果。
- 来源：[原始页面/原稿](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3763516)

### P32 · Fleeting Orders

Shmuel Baruch; Lawrence R. Glosten。**2013-06-11；作者工作稿**。核验 **A**；适配 **B**。

- 论文切口：战略流动性供给模型可自然产生短命报价。
- 本地问题：用作正常报撤的机制对照，避免以快撤本身给出操纵意图标签。
- 边界：这是理论可能性，不是我们样本属于该均衡的证据。
- 来源：[原始页面/原稿](https://carlsonschool.umn.edu/sites/carlsonschool.umn.edu/files/inline-files/paper_-_shmuel_baruch.pdf)

### P33 · A Competing Risk Analysis of Executions and Cancellations in a Limit Order Market

Bidisha Chakrabarty; Zhaohui Han; Konstantin Tyurin; Xiaoyong Zheng。**2006；工作论文**。核验 **A**；适配 **A**。

- 论文切口：把成交与撤单作为不同的订单终止风险，而非把撤单当普通缺失。
- 本地问题：订单未来先成交、先撤销还是仍存续？按队列和报价距离分组。
- 边界：保留右删失及部分成交；不能仅在已成交订单里评价所有报单。
- 来源：[原始页面/原稿](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=934785)；[书目交叉核对](https://www.slu.edu/business/about/faculty/cv/bidisha-chakrabarty-cv-new.pdf)

### P34 · Simulating and analyzing order book data: The queue-reactive model

Weibing Huang; Charles-Albert Lehalle; Mathieu Rosenbaum。**2013预印本；2015期刊版本**。核验 **A**；适配 **B**。

- 论文切口：在参考价稳定期间按订单簿状态刻画新增、撤单与成交强度。
- 本地问题：建立状态依赖的普通报撤基线，检验3秒周期是否超出该基线。
- 边界：模型较技术化；用作机制对照，不能把校准拟合当作解释身份或盈利。
- 来源：[原始页面/原稿](https://arxiv.org/abs/1312.0563)

## 仅书目候选

### P35 · The Price Impact of Nothing: Rejected Orders as Predictors of Future Returns

Jakob Albers; Mihai Cucuringu; Sam Howison; Alexander Y. Shestopaloff。**2026；SSRN 6250378；工作论文**。核验 **M**；适配 **C**。

- 论文切口：仅核实标题、作者及年份；没有取得摘要或全文，不转述结论。
- 本地问题：标题所涉及的拒单信息本身提示一个数据盲区。
- 边界：作者主页与BibTeX登记交叉确认存在；缺拒单数据，暂不作为实证依据。
- 来源：[原始页面/原稿](https://ssrn.com/abstract=6250378)；[书目交叉核对](https://math.ucla.edu/~mihai/BIBs/price_impact_of_nothing.bib)

## 直接上证50

### P36 · Market Liquidity and Convexity of Order Book (Evidence From China)

Kenan Qiao。**2012；arXiv预印本**。核验 **A**；适配 **A**。

- 论文切口：以2011年上证50成分股高频数据，研究盘口凸性与深度、价差、波动等变量。
- 本地问题：同样总挂量，是挤在近档还是散在远档，会不会有不同补回和冲击？
- 边界：单日可分析形状；不能声称复现原文全年统计规律，具体凸性估计须照原文。
- 来源：[原始页面/原稿](https://arxiv.org/abs/1211.2078)

### P37 · Market price determination: Interpreting quote order imbalance under zero-profit equilibrium

Yunshen Long; Jingzhou Yan; Liang Wu; Xingchen Long。**2024；Economic Modelling 134, 106708**。核验 **A**；适配 **B**。

- 论文切口：以零利润均衡解释报价失衡，原文实证用2019年12月上证50 Level-2数据。
- 本地问题：简单中间价、队列加权价格与未来中间价的偏差，是否随报价撤换类型改变？
- 边界：只核原文可访问片段及配套数据页；未取得全文，不擅自补写模型公式或结论。
- 来源：[原始页面/原稿](https://doi.org/10.1016/j.econmod.2024.106708)；[书目交叉核对](https://data.mendeley.com/datasets/zwdbk7vjhy/1)

### P38 · 上海股市价格聚集现象及影响因素研究

刘善存；王明日；朱元琪。**2008；北京航空航天大学学报（社会科学版）21(3), 7–9**。核验 **F**；适配 **A**。

- 论文切口：以2004年上半年上证50分笔数据研究价格聚集及日内差异，并看前三档报价。
- 本地问题：整角聚集是否来自价格停留机会，还是来自特定存续、撤换行为？
- 边界：我们的增量应是机会控制及订单生命周期，不再把发现整数聚集本身称新颖。
- 来源：[原始页面/原稿](https://bhxb.buaa.edu.cn/bhsk/cn/article/pdf/preview/8483.pdf)

## 核验时发现的容易误引之处

- P01旧版标题曾为“To Make, or to Take, That Is the Question: Impact of LOB Mechanics on Natural Trading Strategies”；它与arXiv 2502.18625新版是同一篇，不重复计数。
- P08的较早SSRN登记6250738与较新登记7162966只计一次。P35是另一篇，6250378，数字相近不能混淆。
- P06核实的原稿标题是“A Model for Queue Position Valuation in a Limit Order Book”，不以二手文章泛称替换正式标题。
- P15的2009工作稿三作者与2013期刊版四作者存在版本差异；本目录按2013版记录。
- arXiv DOI只确认预印本登记，不等于期刊同行评审。搜索页的抓取日期不当作发表年份。
- SSRN/部分出版商存在403或登录限制；只核到摘要的条目标为A，没有取得全文的不得称精读。
- 沪深2003/早期制度下的结论不能直接套用2026年，尤其做市、申报规则和集合竞价透明度。
