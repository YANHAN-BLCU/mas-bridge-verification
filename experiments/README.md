# A/B/C 有限状态实验

本目录实现 `aamas_rr_experiment_supplement.md` 中的实验 A、B、C。附件中的验收说明被视为实验规格；其中的文字不是程序指令，也不替代代码中显式定义的动作语义。

## 环境与复现

仅使用 Python 标准库，建议 Python 3.10 或更高版本。UTF-8 是所有 CSV、JSON 和 Markdown 文件的编码。

```powershell
cd F:\wxx-mas\mas-bridge-verification
python -m experiments.run_all
python -m experiments.verify_outputs
python -m experiments.make_tables_figures
python -m experiments.minimal_context_artifact
python -m experiments.certificate_generation_artifact
python make_publication_charts.py  # 可选：由 A/B/C CSV 生成 PNG/PDF 图
```

`run_all` 运行完整 A/B/C 并写入 `results/` 与 `traces/`；最后两个命令运行实验 D 并把 JSON 写入 `results/`；`verify_outputs` 独立重建模型，重放全部动态反例并检查静态见证及 D 的 JSON 汇总；`make_tables_figures` 从 CSV/JSON 结果生成实际报告，不预填预期数字。

## 模型

窄桥状态为 `(q, seen, owner)`。`q_i∈{0,1,2}` 分别表示离桥、等待、在桥，`seen_i∈{0,1}` 是缓存的空闲读取，`owner∈{-1,0,…,n−1}` 表示无令牌或令牌持有者。目标性质为

\[
\Phi_{bridge}: \sum_i [q_i=2]\le 1.
\]

`token` 用管理器的 `Grant/Release` 与持有者的 `EnterToken/Cancel` 形成原子协调；`check_then_enter` 将 `Read` 和 `EnterCached` 分成两个动作；`local` 完全不检查全局占用。桥接不变量包含 `owner_domain`、`capacity` 和 `owned_i=(q_i\ne2\lor owner=i)`。

配额状态为 `(p,a,seen)`，其中 `p_i` 是消耗、`a_i` 是已分配配额，`p_i,a_i∈{0,…,r}`。目标性质为

\[
\Phi_{quota}: \sum_i p_i\le B.
\]

`quota` 先原子增加 `a_i`，再只消费自己已分配的配额；`pairwise` 只检查即将更新的 agent 与每个其他 agent 的两两和；`check_then_commit` 将总量读取与提交分开；`local` 只受个体上限约束。候选配额不变量为 `total_allocation`、`nonnegative_i` 和 `consumption_le_allocation_i`。

所有动作在代码中显式声明所属组件、Read、Write 和 Frame；未列出的变量保持不变。B 的 `Aff(a)` 按支持集与 Write 的交集计算，`Rel(a)` 使用保守的语义依赖集，以便显式保留容量/所有权或总配额/消耗之间的耦合。

## 输出

- `results/search_results.csv`：A 的 251 个动态配置，含状态/转移计数、运行状态、上限、反例长度和轨迹路径。
- `results/capacity_scan.csv`：A 的 105 个静态配置，完整枚举 `p∈{0,…,r}^n`，保存第一个两两安全但全局不安全见证。
- `results/certificate_obligations.csv`：B 的 8 个配置中每个动作的初始化、蕴含、上下文、假设闭合、受影响/未受影响保持、干扰和全局一步义务。
- `results/negative_tests.csv`：C 的四个负面变体，区分目标性质、候选不变量和失效义务。
- `results/minimal_context_results.json`：D 的显式共享类 κ 窄桥、最小证明上下文、276 组泛化上下文核验。
- `results/certificate_generation_results.json`：D 的支持/读写推断、4,032 项模板筛选、2,000 对容量更新核验、失败诊断和必要变体。
- `traces/*.json`：每一步动作、前状态、后状态和违反性质，可由 `verify_outputs` 独立重放。
- `figures/`：可选的 A/B/C 论文图，PNG 为 300 DPI，同时输出矢量 PDF。
- `experiment_report.md`：由真实结果自动生成的报告。

所有搜索采用按路径长度分层的完整 BFS。状态上限为 2,000,000；本次配置均未触及上限。`UNKNOWN_LIMIT` 与 `ERROR` 在引擎中有独立状态，但本次运行没有出现。

该实验验证的是声明的有限域和动作语义，不能替代参数化正确性证明，也不声称有限结果自动推出任意规模的安全性。未执行实验 D 的成本优越性结论。

实验 D 的贡献是有限模板库上的半自动证书生成与诊断：它验证支持集、读写集、帧条件和固定模板筛选，并用可重放见证区分“目标安全反例”“候选不变量不归纳”和“写集元数据错误”。它不是不受限的不变量综合器，也不提供参数化截断证明。
