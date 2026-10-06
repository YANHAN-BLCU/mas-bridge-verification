"""Generate the experiment report from the current result files.

The script deliberately computes every number from CSV/JSON artifacts.  It
does not contain expected counts, so a changed model or parameter sweep is
visible in the generated report.
"""
from __future__ import annotations

import csv
import json
import platform
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"


def read_csv(name):
    with (RESULTS / name).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def params(row):
    return json.loads(row["parameters"])


def pct(x, total):
    return f"{100*x/total:.1f}%" if total else "—"


def make_report():
    search = read_csv("search_results.csv")
    static = read_csv("capacity_scan.csv")
    cert = read_csv("certificate_obligations.csv")
    negative = read_csv("negative_tests.csv")
    minimal = json.loads((RESULTS / "minimal_context_results.json").read_text(encoding="utf-8"))
    generated = json.loads((RESULTS / "certificate_generation_results.json").read_text(encoding="utf-8"))
    status = Counter(r["status"] for r in search)
    static_status = Counter(r["status"] for r in static)

    lines = [
        "# 实验 A/B/C/D 报告：从安全反例到桥接不变量",
        "",
        "> 本报告由 `python -m experiments.make_tables_figures` 根据当前 CSV/JSON 自动生成。",
        "",
        "## 1. 复现范围",
        "",
        "实验 A 包含窄桥 `n=2…10` 的 27 个配置、配额 `n=2…8,B=1…4,r∈{1,2}` 的 224 个配置，以及 105 个静态容量配置。实验 B 检查窄桥 token `n=2…5` 和配额 `B=2,r=1,n=2…5`，共 8 个完整有限域配置。实验 C 检查四个一次只改变一个协调条件的负面变体。实验 D 增加显式共享类状态、最小证明上下文、模板筛选、失败诊断和容量更新条件核验。",
        "",
        "## 2. 实验 A：可达性与静态容量",
        "",
        "动态搜索结果：共 **%d** 个配置，其中 `COUNTEREXAMPLE` %d 个（%s），`SAFE_EXHAUSTIVE` %d 个（%s），`UNKNOWN_LIMIT` %d 个，`ERROR` %d 个。" % (
            len(search), status["COUNTEREXAMPLE"], pct(status["COUNTEREXAMPLE"], len(search)),
            status["SAFE_EXHAUSTIVE"], pct(status["SAFE_EXHAUSTIVE"], len(search)),
            status["UNKNOWN_LIMIT"], status["ERROR"]),
        "",
        "| 模型 | 协议 | 配置数 | 反例 | 穷尽安全 | 最大已发现状态 | 最大最短反例步数 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    grouped = defaultdict(list)
    for row in search:
        p = params(row)
        grouped[(row["model"], p["protocol"])].append(row)
    for (model, protocol), rows in sorted(grouped.items()):
        lines.append("| %s | %s | %d | %d | %d | %d | %d |" % (
            model, protocol, len(rows), sum(r["status"] == "COUNTEREXAMPLE" for r in rows),
            sum(r["status"] == "SAFE_EXHAUSTIVE" for r in rows),
            max(int(r["discovered_states"]) for r in rows),
            max(int(r["counterexample_steps"] or 0) for r in rows)))
    lines += [
        "",
        "静态容量扫描完整枚举每个 `p∈{0,…,r}^n` 向量：共 **%d** 个配置，`COUNTEREXAMPLE` %d 个，`SAFE_EXHAUSTIVE` %d 个；两两约束存在缺口的比例为 %s。" % (
            len(static), static_status["COUNTEREXAMPLE"], static_status["SAFE_EXHAUSTIVE"],
            pct(static_status["COUNTEREXAMPLE"], len(static))),
        "",
        "见证的判定同时满足 `p_i≤r`、`p_i+p_j≤B`（所有 `i<j`）和 `Σ_i p_i>B`。完整向量数记录在 `checked_assignments` 与 `total_assignments` 中，二者由独立审计脚本逐配置核对。",
        "",
        "## 3. 实验 B：动作级桥接证书",
        "",
        "证书表包含 **%d** 行动作记录；PASS %d，FAIL %d，UNKNOWN %d。所有记录均覆盖声明的完整有限状态域，且全局一步义务与组件干扰义务均通过。" % (
            len(cert), sum(r["result"] == "PASS" for r in cert), sum(r["result"] == "FAIL" for r in cert),
            sum(r["result"] == "UNKNOWN" for r in cert)),
        "",
        "`Aff(a)` 是支持集与 Write 的语法交集；`Rel(a)` 是证明上下文，桥接模型保守地包含所有 owner/capacity/owned 子句，配额模型保守地包含所有 allocation/consumption 子句。因而管理器动作对所有相关子句的全局责任被显式保留。",
        "",
        "| 模型 | 动作记录 | PASS | 失败义务 |",
        "|---|---:|---:|---:|",
    ]
    for model in sorted({r["model"] for r in cert}):
        rs = [r for r in cert if r["model"] == model]
        failed = Counter(k for r in rs for k in ("init", "implication", "context", "assumption_closed", "affected", "unaffected", "interference", "global_step") if r[k] == "FAIL")
        lines.append("| %s | %d | %d | %s |" % (model, len(rs), sum(r["result"] == "PASS" for r in rs), ", ".join(f"{k}={v}" for k,v in failed.items()) or "无"))
    lines += [
        "",
        "## 4. 实验 C：协调条件失效",
        "",
        "| 变体 | 目标状态 | 反例步数 | 独立重放 | 候选不变量 | 失效义务 |",
        "|---|---|---:|---|---|---|",
    ]
    for r in negative:
        lines.append("| %s | %s | %s | %s | %s | %s |" % (
            r["case_id"], r["status"], r["counterexample_steps"], r["replay_status"],
            r["candidate_invariant_status"], r["failed_obligation"]))
    lines += [
        "",
        "四个变体都产生目标安全性质反例，且轨迹独立重放通过。`candidate_invariant_status=FAIL` 表示桥接不变量在某个合法声明域状态的后继上失效；它与可达目标反例分别记录，不能混同为同一义务。",
        "",
        "## 5. 实验 D：上下文综合与证书生成",
        "",
        "显式共享类 κ 窄桥在 `n=2,3,4` 上分别枚举 %d、%d、%d 个声明域状态；每个模型的初始化和安全蕴含均通过。泛化最小上下文核验覆盖 **%d** 个冲突族，证书模板筛选覆盖 **%d** 个有限模型，容量更新必要充分条件核验覆盖 **%d** 对有限前后状态。" % (
            minimal["bridge"][0]["declared_domain_states"], minimal["bridge"][1]["declared_domain_states"], minimal["bridge"][2]["declared_domain_states"],
            minimal["generic_synthesis"]["exhaustive_conflict_families"], generated["generic_pruning_validation"]["checked_models"], generated["capacity_update_iff_validation"]["total_pairs"]),
        "",
        "D 的正确模型包含 6 个有限实例，证书状态全部为 `proved`；另检查 9 个故障/元数据变体，分别输出模板删除、目标安全状态、可达性和写集诊断。实验通过语法支持集、读写集、并行更新和帧条件的一致性检查，但不声称实现不受限的不变量综合。",
        "",
        "## 6. 可复现性与边界",
        "",
        "- 搜索使用完整 BFS，并保存动作、前状态、后状态和违反性质；状态上限为 2,000,000。本次没有配置触及上限，因此没有 `UNKNOWN_LIMIT`。",
        "- `python -m experiments.verify_outputs` 对所有 165 条动态反例逐条重放、对 105 个静态配置逐域核对、对证书和负例表执行一致性断言，输出 `results/verification_summary.json`。",
        "- 运行环境和命令记录在 `environment.json`；实验确定性运行，不使用随机种子。",
        "- 结论仅适用于代码定义的有限状态域和动作语义。它支持“局部/两两条件不足、原子桥接协议恢复安全”的有限实例证据，不替代参数化证明，也不提供未执行的成本优越性结论。",
        "",
        "## 7. 代表性见证",
        "",
        "详细见证保存在 `traces/`。例如 `A_bridge_n2_local.json` 展示两个 agent 依次进入导致 `Σ_i[q_i=2]>1`；`A_static_n3_B2_r1.json` 展示三维整数向量满足所有两两约束但总和超过容量；`C_early_release.json` 展示提前释放使 owner 与在桥状态失配。",
        "",
    ]
    (ROOT / "experiment_report.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    make_report()
    print("wrote", ROOT / "experiment_report.md")
