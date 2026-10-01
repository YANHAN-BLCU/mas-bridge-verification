# 实验 A/B/C 报告：从安全反例到桥接不变量

> 本报告由 `python -m experiments.make_tables_figures` 根据当前 CSV/JSON 自动生成。

## 1. 复现范围

实验 A 包含窄桥 `n=2…10` 的 27 个配置、配额 `n=2…8,B=1…4,r∈{1,2}` 的 224 个配置，以及 105 个静态容量配置。实验 B 检查窄桥 token `n=2…5` 和配额 `B=2,r=1,n=2…5`，共 8 个完整有限域配置。实验 C 检查四个一次只改变一个协调条件的负面变体。

## 2. 实验 A：可达性与静态容量

动态搜索结果：共 **251** 个配置，其中 `COUNTEREXAMPLE` 165 个（65.7%），`SAFE_EXHAUSTIVE` 86 个（34.3%），`UNKNOWN_LIMIT` 0 个，`ERROR` 0 个。

| 模型 | 协议 | 配置数 | 反例 | 穷尽安全 | 最大已发现状态 | 最大最短反例步数 |
|---|---:|---:|---:|---:|---:|---:|
| bridge | check_then_enter | 9 | 9 | 0 | 7474 | 6 |
| bridge | local | 9 | 9 | 0 | 891 | 4 |
| bridge | token | 9 | 0 | 9 | 16384 | 0 |
| quota | check_then_commit | 56 | 49 | 7 | 33490 | 10 |
| quota | local | 56 | 49 | 7 | 1604 | 5 |
| quota | pairwise | 56 | 49 | 7 | 1604 | 6 |
| quota | quota | 56 | 0 | 56 | 4325 | 0 |

静态容量扫描完整枚举每个 `p∈{0,…,r}^n` 向量：共 **105** 个配置，`COUNTEREXAMPLE` 66 个，`SAFE_EXHAUSTIVE` 39 个；两两约束存在缺口的比例为 62.9%。

见证的判定同时满足 `p_i≤r`、`p_i+p_j≤B`（所有 `i<j`）和 `Σ_i p_i>B`。完整向量数记录在 `checked_assignments` 与 `total_assignments` 中，二者由独立审计脚本逐配置核对。

## 3. 实验 B：动作级桥接证书

证书表包含 **140** 行动作记录；PASS 140，FAIL 0，UNKNOWN 0。所有记录均覆盖声明的完整有限状态域，且全局一步义务与组件干扰义务均通过。

`Aff(a)` 是支持集与 Write 的语法交集；`Rel(a)` 是证明上下文，桥接模型保守地包含所有 owner/capacity/owned 子句，配额模型保守地包含所有 allocation/consumption 子句。因而管理器动作对所有相关子句的全局责任被显式保留。

| 模型 | 动作记录 | PASS | 失败义务 |
|---|---:|---:|---:|
| bridge | 84 | 84 | 无 |
| quota | 56 | 56 | 无 |

## 4. 实验 C：协调条件失效

| 变体 | 目标状态 | 反例步数 | 独立重放 | 候选不变量 | 失效义务 |
|---|---|---:|---|---|---|
| C_stale_bridge | COUNTEREXAMPLE | 6 | PASS | FAIL | global_step |
| C_early_release | COUNTEREXAMPLE | 7 | PASS | FAIL | global_step |
| C_non_atomic_quota | COUNTEREXAMPLE | 6 | PASS | FAIL | global_step |
| C_environment_write | COUNTEREXAMPLE | 7 | PASS | FAIL | global_step |

四个变体都产生目标安全性质反例，且轨迹独立重放通过。`candidate_invariant_status=FAIL` 表示桥接不变量在某个合法声明域状态的后继上失效；它与可达目标反例分别记录，不能混同为同一义务。

## 5. 可复现性与边界

- 搜索使用完整 BFS，并保存动作、前状态、后状态和违反性质；状态上限为 2,000,000。本次没有配置触及上限，因此没有 `UNKNOWN_LIMIT`。
- `python -m experiments.verify_outputs` 对所有 165 条动态反例逐条重放、对 105 个静态配置逐域核对、对证书和负例表执行一致性断言，输出 `results/verification_summary.json`。
- 运行环境和命令记录在 `environment.json`；实验确定性运行，不使用随机种子。
- 结论仅适用于代码定义的有限状态域和动作语义。它支持“局部/两两条件不足、原子桥接协议恢复安全”的有限实例证据，不替代参数化证明，也不提供未执行的成本优越性结论。

## 6. 代表性见证

详细见证保存在 `traces/`。例如 `A_bridge_n2_local.json` 展示两个 agent 依次进入导致 `Σ_i[q_i=2]>1`；`A_static_n3_B2_r1.json` 展示三维整数向量满足所有两两约束但总和超过容量；`C_early_release.json` 展示提前释放使 owner 与在桥状态失配。
