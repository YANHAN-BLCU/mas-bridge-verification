# 有限状态多智能体安全验证

本项目对应研究题目：**从安全反例到桥接不变量：多智能体系统的有限状态验证**。

项目用 Python 显式枚举有限状态转移系统，研究：

- 局部安全和两两安全何时不足以保证高阶安全；
- 非原子检查是否产生竞态反例；
- 唯一令牌和原子配额能否恢复全局安全；
- 桥接不变量能否在有限候选域中通过初始化、保持性和安全蕴含检查。

## 快速复现 A/B/C

```powershell
cd F:\wxx-mas\mas-bridge-verification
python -m experiments.run_all
python -m experiments.verify_outputs
python -m experiments.make_tables_figures
```

完整结果和方法边界见 [experiments/experiment_report.md](experiments/experiment_report.md)。

## 目录

- `experiments/models.py`：窄桥/配额状态、动作语义、完整 BFS 与轨迹重放
- `experiments/run_all.py`：运行实验 A、B、C
- `experiments/verify_outputs.py`：独立重放全部反例并核对静态见证和证书表
- `experiments/make_tables_figures.py`：由真实 CSV/JSON 结果生成报告
- `experiments/results/`：搜索、静态枚举、动作级证书和负例结果
- `experiments/traces/`：可重放反例与静态见证
- `experiments/configs/`：参数范围与变量域

## 结果摘要

- 共运行 251 组动态配置和 105 组静态容量配置；动态配置中 165 组发现安全反例。
- 窄桥覆盖 n=2–10：local 和 cached check-then-enter 产生反例；atomic token 未发现反例。
- 配额覆盖 B=1–4、局部上限 r=1–2：local、pairwise 和 cached commit 在相应参数区间产生反例；atomic quota 未发现反例。
- 静态容量扫描中 66 组显示两两约束不足以保证全局容量安全。
- 8 组完整有限域桥接证书对应 140 条动作记录，全部通过。
- 四个协调条件负例均产生目标性质反例，并通过独立重放。

这些结果只适用于代码中定义的有限状态模型和动作语义。
