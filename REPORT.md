# 从安全反例到桥接不变量：多智能体系统的有限状态验证

## 1. 项目说明

本项目研究有限状态多智能体系统中，局部安全和两两安全何时不足以保证高阶安全，以及简单桥接协议能否恢复全局安全。实验不使用大语言模型训练；所有结果来自确定性的显式状态 BFS 和有限域不变量检查。

> 证据范围：本报告的结论只对代码中明确的有限状态模型、动作和参数成立。搜索未发现反例时，报告使用“该有限模型中安全”，不外推到任意规模系统。

## 2. 模型与安全性质

### 2.1 共享窄桥

每个 Agent 的位置状态为 `away=0`、`wait=1`、`on=2`。桥容量为 1，全局安全谓词为：

$$\Phi_{bridge}=\sum_i [q_i=on]\le 1.$$

比较 local、check-then-enter 和 atomic token 三种协议。前两者允许直接进入或先缓存桥状态后进入；atomic token 通过唯一 owner 串行化授权。

### 2.2 群体配额

每个 Agent 的消耗为 $p_i$，局部上限为 $r=1$，总容量为 $B=2$。全局安全谓词为：

$$\Phi_{quota}=\sum_i p_i\le B.$$

比较 local、pairwise、check-then-commit 和 atomic quota。pairwise 只检查任意两者的总量；atomic quota 先原子授予配额，再允许消耗。

## 3. 实验设置

- Agent 数量：$n=2,3,\ldots,8$。
- 每个配置从固定初始状态开始。
- 使用 BFS 搜索最短安全反例。
- 状态上限为 2,000,000；本次所有配置均未触发上限。
- 记录可达状态数、转移数、运行时间、是否安全和最短反例步数。
- 对 token/quota 协议在 $n=2,3,4,5$ 上枚举完整有限候选域，检查初始化、保持性和安全蕴含。

## 4. 实验结果

### 4.1 反例搜索

| 模型 | 协议 | n=2 | n=3–8 | 最短反例 |
|---|---|---|---|---|
| bridge | check-then-enter | counterexample | counterexample … counterexample | 6 |
| bridge | local | counterexample | counterexample … counterexample | 4 |
| bridge | atomic token | safe | safe … safe | — |
| quota | cached commit | safe | counterexample … counterexample | 6 |
| quota | local | safe | counterexample … counterexample | 3 |
| quota | pairwise | safe | counterexample … counterexample | 3 |
| quota | atomic quota | safe | safe … safe | — |

窄桥结果中，local 在所有 $n$ 上出现 4 步反例，check-then-enter 出现 6 步反例；atomic token 在 $n=2$ 至 $8$ 的搜索中均未发现违规状态。群体配额中，local 和 pairwise 从 $n=3$ 开始出现 3 步反例；cached commit 从 $n=3$ 开始出现 6 步竞态；atomic quota 在所有测试规模中均未发现反例。

![桥模型可达状态数](figures/bridge_reachable_states.png)

![桥模型运行时间](figures/bridge_runtime_ms.png)

![配额模型可达状态数](figures/quota_reachable_states.png)

![安全结果](figures/safety_by_protocol.png)

### 4.2 最短反例

窄桥 local 的最短轨迹为：

```text
initial → request(0) → enter(0) → request(1) → enter(1)
```

最终状态为 `(on_0, on_1)`，违反桥容量为 1 的安全性质。

cached commit 的反例包含两个 Agent 先后读取“有剩余容量”，再使用缓存完成提交，说明检查与提交分离会使局部检查失效。

### 4.3 归纳证书

8 组完整有限域检查全部通过：

| 模型 | n 范围 | base | step | invariant ⇒ safety |
|---|---:|---:|---:|---:|
| bridge | 2–5 | True | True | True |
| quota | 2–5 | True | True | True |

这意味着在本次枚举的完整有限候选域中，token 和 quota 桥接不变量分别满足初始化、所有动作保持性以及对全局安全的蕴含。它是有限模型内的形式证书，不是任意规模系统的定理。

## 5. 结论

1. 单体安全和两两安全不能覆盖高阶总量约束：当 $n=3$、每个 Agent 最多消耗 1、总容量为 2 时，任意两者总量不超过 2，但三者合计为 3。
2. 非原子检查和提交会产生动态竞态；最短反例可以由 BFS 自动给出。
3. 唯一令牌和原子配额协议在给定有限模型中恢复了全局安全，并通过完整候选域的不变量检查获得证书。
4. 桥接协议有状态和动作开销；运行时间与状态空间随 Agent 数量增长，报告中的结果只覆盖 $n\le8$。

## 6. 复现

```powershell
cd mas-bridge-verification
python run_experiments.py
python make_report.py
```

原始结果见 `data/experiments.csv`、`data/counterexamples.json` 和 `data/certificates.json`；运行环境与命令见 `data/provenance.json`。

## 7. 限制

- 模型采用有限整数状态，不代表真实 LLM Agent 的行为。
- 调度是非概率的全状态枚举，没有测量真实网络延迟。
- 协议安全依赖动作定义和 owner/quota 管理器可信。
- 尚未研究活性、饥饿、故障恢复和恶意协议实现。
