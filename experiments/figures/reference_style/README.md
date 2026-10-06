# 实验论文图

共 8 张图，覆盖实验 A–D。采用白底、灰网格、鲜明红蓝绿橙紫青配色及 Comic Sans MS 字体；线型、点形、文字与颜色共同编码。图中文字采用英文，便于投稿；下列提供中英文图注。

PDF 为论文插图首选；SVG 保留可编辑文字；PNG 为 600 DPI。画布宽度统一为 182.9 mm，按双栏宽度排版；如缩为单栏，需要重新设置画布与字号。没有添加误差棒或显著性标记，实验为确定性有限域检查，没有随机重复。

建议优先选择图 03（群体缺口）、05（协调反例）、06（证明前提）；图 01、02、04、07、08 可用于实验补充材料。当前只交付图，不自动插入六页正文。

复现命令：`python -m experiments.plot_reference_style`。依赖：Matplotlib、NumPy、Pillow；字体需要 Comic Sans MS。数据来自 `experiments/results` 和实验 C 的原始轨迹。各图对应的数值在 `source_data`，输入哈希与样式参数在 `manifest.json`。

## fig01_A_bridge_scaling

中文图注：实验 A 的窄桥规模扫描。左图为 BFS 已发现状态数（对数轴）；反例配置在首个反例处停止，安全配置穷尽搜索。右图只绘制存在反例的配置，令牌协议的安全结果不记作零步反例。共 27 个配置。

English caption: Bridge size sweep in Experiment A (27 configurations). Discovered states use a log axis; unsafe searches stop at the first counterexample and safe searches are exhaustive. Counterexample length is defined only for unsafe configurations.

## fig02_A_quota_outcome_map

中文图注：实验 A 配额模型全部 224 个配置的结果。行对应单体上限 r，列对应容量 B；每个子图展示四类协议与智能体数 n。方块表示穷尽安全，叉号表示可达反例。

English caption: Outcomes for all 224 quota configurations in Experiment A. Panel rows vary the local bound r and columns vary capacity B. Squares denote exhaustive safety; crosses denote reachable counterexamples.

## fig03_A_static_capacity_gaps

中文图注：实验 A 静态容量扫描（105 个配置）。66 个配置存在满足全部个体及两两约束、却违反群体容量的见证。红色单元中的整数是已保存见证的超额量 Σp_i−B，不是最大超额；蓝色横线表示穷尽扫描未发现缺口。

English caption: Static capacity scan over 105 configurations. A gap exists in 66 configurations. Red-cell values are the overload of the saved witness, sum(p_i)-B, rather than maximal overload; cyan cells mark configurations with no gap after exhaustive scanning.

## fig04_B_certificate_coverage

中文图注：实验 B 的动作级证书覆盖。左图统计各有限域配置的动作记录数；右图每个单元显示通过该项检查的动作记录数。各列重复检查同一组 140 条记录，不能相加视作独立样本。Decl. 为读写声明，Aff./Frame 为受影响及未受影响保持，Interf. 为组件干扰，Global 为全局一步保持。

English caption: Action-level certificate coverage in Experiment B. The left panel counts action records for eight finite configurations; cells on the right count records passing each check. Columns evaluate the same 140 records and are not independent samples.

## fig05_C_coordination_failure_traces

中文图注：实验 C 四种协调失效的独立重放轨迹。窄桥负载为在桥智能体数（容量 1）；配额负载为总消耗（容量 2）。纵轴为负载/容量，虚线是安全边界。红叉仅标注最终违规状态；反例长度分别为 6、7、6、7 步。

English caption: Independently replayed traces for four coordination failures in Experiment C. Bridge load counts agents on the bridge (capacity 1); quota load is total consumption (capacity 2). The dashed line is the safety boundary, with final violations marked by crosses.

## fig06_D_minimum_context_scaling

中文图注：实验 D 显式共享类窄桥的证明前提计数。全部前提、仅受影响前提与基数最小前提在同一批动作–目标对上比较；最小前提出现次数为 6、18、36，相对全部前提减少 90.0%、93.3%、95.5%。指标只度量逐目标前提的重复表示，不代表运行时间、通信或状态空间收益。

English caption: Proof-premise occurrences for the explicit shared-class bridge in Experiment D. All methods use the same action-target pairs. Minimum-context occurrences are 6, 18 and 36, a reduction of 90.0%, 93.3% and 95.5%. This metric describes premise representation, not runtime or communication speedup.

## fig07_D_action_target_contexts

中文图注：实验 D 在 n=4 时的逐动作、逐目标最小前提矩阵。20 个动作对应 10 个不变式子句，共 80 个受影响动作–目标对；44 个取空上下文，36 个仅需一个前提。灰格为未受影响目标，由帧条件保持。tok-i 对应所有权子句，share-ij 对应共享类一致性子句；数值不统计动作守卫或环境假设。

English caption: Minimum premise cardinalities for n=4 in Experiment D. Of 80 affected action-target pairs, 44 require no premise and 36 require one. Gray cells are unaffected targets preserved by frame conditions. tok-i denotes ownership and share-ij shared-class consistency; guards and environment assumptions are excluded.

## fig08_D_certificate_diagnosis

中文图注：实验 D 九个故障及元数据变体的证书诊断。证书状态、BFS 目标安全、保留/提供模板数与可达反例长度分别记录。共有 5 个变体出现目标反例、4 个目标安全；缺失模板可能使证书无法证明而协议仍安全，写集元数据错误则阻断证书。拆分刷新删除一致性模板后仍证明目标安全。另有 6 个正确实例均已证明且安全。

English caption: Certificate diagnostics for nine mutations in Experiment D. Certificate status, BFS target safety, retained/supplied templates and reachable trace lengths are reported separately. Five mutations are unsafe and four are safe. Missing templates can prevent proof without causing unsafety; incorrect write metadata blocks certification. All six correct instances are proved and safe.
