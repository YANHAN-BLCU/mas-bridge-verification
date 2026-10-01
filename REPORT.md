# 实验报告入口

实验 A/B/C 的完整结果、模型语义、证书义务、负例见证和范围限制由脚本自动生成：

- [experiments/experiment_report.md](experiments/experiment_report.md)
- [experiments/README.md](experiments/README.md)
- [experiments/results/](experiments/results/)
- [experiments/traces/](experiments/traces/)

在仓库根目录运行：

```powershell
python -m experiments.run_all
python -m experiments.verify_outputs
python -m experiments.make_tables_figures
```

报告中的所有数字来自当前运行产生的 CSV/JSON，不以预期结果作为硬编码输入。
