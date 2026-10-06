"""Create publication-style line and bar charts from verified experiment CSVs.

All plotted values are read from ``experiments/results``.  The script writes
both 300-dpi PNG previews and vector PDF files into the paper's figures folder.
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "experiments" / "results"
OUT = ROOT / "experiments" / "figures"
OUT.mkdir(parents=True, exist_ok=True)

COLORS = {
    # Match the earlier AI illustrations: navy outlines, pastel panels,
    # coral for violations, and emerald for certified protocols.
    "local": "#F26B5E",
    "check_then_enter": "#B58BE8",
    "token": "#4DB6E6",
    "pairwise": "#F2C94C",
    "check_then_commit": "#F5A65B",
    "quota": "#59C478",
    "r1": "#56A8E0",
    "r2": "#59C478",
    "r3": "#B58BE8",
}
NAVY = "#17324D"
GRID = "#BFD8C8"
PANEL_BLUE = "#EEF9FF"
PANEL_LAVENDER = "#F5F0FF"
PANEL_YELLOW = "#FFF9E6"
PANEL_CORAL = "#FFF1F1"
PANEL_GREEN = "#F0FFF2"
LABELS = {
    "local": "local",
    "check_then_enter": "check-then-enter",
    "token": "atomic token",
    "pairwise": "pairwise",
    "check_then_commit": "cached commit",
    "quota": "atomic quota",
}


def read_rows(name: str) -> list[dict[str, str]]:
    with (RESULTS / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def enrich_search(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    enriched = []
    for row in rows:
        params = json.loads(row["parameters"])
        enriched.append(
            {
                **row,
                **params,
                "n": int(params["n"]),
                "safe": row["status"] == "SAFE_EXHAUSTIVE",
                "steps": float(row["counterexample_steps"])
                if row["counterexample_steps"]
                else np.nan,
                "states": int(row["discovered_states"]),
                "runtime_ms": float(row["elapsed_ms"]),
            }
        )
    return enriched


def apply_publication_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 11,
            "axes.titlesize": 12,
            "axes.labelsize": 11,
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
            "axes.linewidth": 1.4,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "legend.frameon": False,
            "figure.dpi": 160,
            "savefig.dpi": 300,
            "mathtext.fontset": "dejavusans",
            "text.color": NAVY,
            "axes.labelcolor": NAVY,
            "axes.titlecolor": NAVY,
            "axes.edgecolor": NAVY,
            "xtick.color": NAVY,
            "ytick.color": NAVY,
        }
    )


def save_figure(fig: plt.Figure, stem: str) -> None:
    fig.tight_layout(pad=0.8)
    fig.savefig(OUT / f"{stem}.png", dpi=300, bbox_inches="tight")
    fig.savefig(OUT / f"{stem}.pdf", bbox_inches="tight")
    plt.close(fig)


def protocol_series(rows: list[dict[str, object]], protocol: str, *, model: str, B: int | None = None, r: int | None = None) -> list[dict[str, object]]:
    selected = [row for row in rows if row["model"] == model and row["protocol"] == protocol]
    if B is not None:
        selected = [row for row in selected if row["B"] == B]
    if r is not None:
        selected = [row for row in selected if row["r"] == r]
    return sorted(selected, key=lambda row: int(row["n"]))


def plot_safety_rate_bars(rows: list[dict[str, object]]) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(8.6, 3.35), sharey=True)
    cases = [
        (axes[0], "bridge", None, None, ["local", "check_then_enter", "token"], "Bridge ($n=2\u201310$)"),
        (axes[1], "quota", 2, 1, ["local", "pairwise", "check_then_commit", "quota"], "Quota ($B=2$, $r=1$)"),
    ]
    for ax, model, B, r, protocols, title in cases:
        ax.set_facecolor(PANEL_BLUE if model == "bridge" else PANEL_GREEN)
        rates = []
        annotations = []
        for protocol in protocols:
            series = protocol_series(rows, protocol, model=model, B=B, r=r)
            safe = sum(bool(row["safe"]) for row in series)
            total = len(series)
            rates.append(100 * safe / total if total else 0)
            annotations.append(f"{safe}/{total}")
        x = np.arange(len(protocols))
        bars = ax.bar(
            x,
            rates,
            color=[COLORS[p] for p in protocols],
            edgecolor=NAVY,
            linewidth=0.9,
            width=0.68,
        )
        for bar, rate, annotation in zip(bars, rates, annotations):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                rate + 3,
                f"{rate:.1f}%\n({annotation})",
                ha="center",
                va="bottom",
                fontsize=8.5,
            )
        ax.set_title(title, fontweight="bold")
        ax.set_xticks(x, [LABELS[p] for p in protocols], rotation=25, ha="right")
        ax.set_ylim(0, 112)
        ax.set_yticks(np.arange(0, 101, 20))
        ax.grid(axis="y", color=GRID, alpha=0.75)
        ax.set_axisbelow(True)
    axes[0].set_ylabel("safe configurations (%)")
    fig.suptitle("Exhaustive safety coverage by protocol", fontweight="bold", y=1.02)
    save_figure(fig, "protocol_safety_rate_bar")


def plot_counterexample_steps(rows: list[dict[str, object]]) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(8.6, 3.35), sharey=True)
    cases = [
        (axes[0], "bridge", None, None, ["local", "check_then_enter"], "Shared narrow bridge"),
        (axes[1], "quota", 2, 1, ["local", "pairwise", "check_then_commit"], "Shared quota ($B=2$, $r=1$)"),
    ]
    for ax, model, B, r, protocols, title in cases:
        ax.set_facecolor(PANEL_CORAL if model == "bridge" else PANEL_YELLOW)
        for protocol in protocols:
            series = protocol_series(rows, protocol, model=model, B=B, r=r)
            x = [row["n"] for row in series]
            y = [row["steps"] for row in series]
            ax.plot(
                x,
                y,
                marker="o",
                markersize=5,
                linewidth=2,
                color=COLORS[protocol],
                label=LABELS[protocol],
            )
            for row in series:
                if not np.isnan(float(row["steps"])):
                    ax.annotate(
                        f"{int(row['steps'])}",
                        (row["n"], row["steps"]),
                        textcoords="offset points",
                        xytext=(0, 6),
                        ha="center",
                        fontsize=7.5,
                        color=COLORS[protocol],
                    )
        ax.set_title(title, fontweight="bold")
        ax.set_xlabel("number of agents, $n$")
        ax.set_xticks(sorted({int(row["n"]) for row in rows if row["model"] == model and (B is None or row.get("B") == B) and (r is None or row.get("r") == r)}))
        ax.grid(axis="both", color=GRID, alpha=0.75)
        ax.set_axisbelow(True)
        ax.legend(fontsize=8.5, loc="upper left")
        ax.text(
            0.98,
            0.96,
            "no counterexample" if model == "bridge" else "atomic quota: no counterexample",
            transform=ax.transAxes,
            ha="right",
            va="top",
            fontsize=8.2,
            color=COLORS["quota"],
            bbox={"boxstyle": "round,pad=0.25", "facecolor": PANEL_GREEN, "edgecolor": COLORS["quota"]},
        )
    axes[0].set_ylabel("shortest counterexample length (steps)")
    axes[0].set_ylim(0, 7.5)
    fig.suptitle("Shortest counterexamples found by BFS", fontweight="bold", y=1.02)
    save_figure(fig, "counterexample_steps_line")


def plot_bridge_scaling(rows: list[dict[str, object]]) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(8.6, 3.35))
    bridge = [row for row in rows if row["model"] == "bridge"]
    for ax, panel_color in zip(axes, [PANEL_BLUE, PANEL_LAVENDER]):
        ax.set_facecolor(panel_color)
    for protocol in ["local", "check_then_enter", "token"]:
        series = protocol_series(bridge, protocol, model="bridge")
        x = [row["n"] for row in series]
        axes[0].plot(x, [row["states"] for row in series], marker="o", linewidth=2, color=COLORS[protocol], label=LABELS[protocol])
        axes[1].plot(x, [row["runtime_ms"] for row in series], marker="o", linewidth=2, color=COLORS[protocol], label=LABELS[protocol])
    axes[0].set_title("Reachable state space", fontweight="bold")
    axes[0].set_ylabel("states")
    axes[0].set_xlabel("number of agents, $n$")
    axes[1].set_title("BFS runtime", fontweight="bold")
    axes[1].set_ylabel("runtime (ms, log scale)")
    axes[1].set_xlabel("number of agents, $n$")
    axes[1].set_yscale("log")
    for ax in axes:
        ax.set_xticks(range(2, 11, 2))
        ax.grid(color=GRID, alpha=0.75)
        ax.set_axisbelow(True)
    axes[1].legend(fontsize=8.5, loc="upper left")
    fig.suptitle("Scaling of the shared-bridge verification", fontweight="bold", y=1.02)
    save_figure(fig, "bridge_scaling_line")


def plot_static_gap_bars() -> None:
    rows = read_rows("capacity_scan.csv")
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    ax.set_facecolor(PANEL_YELLOW)
    capacities = list(range(1, 6))
    r_values = [1, 2, 3]
    x = np.arange(len(capacities))
    width = 0.24
    for idx, r_value in enumerate(r_values):
        rates = []
        for capacity in capacities:
            subset = [row for row in rows if int(row["r"]) == r_value and int(row["B"]) == capacity]
            rates.append(100 * sum(row["status"] == "COUNTEREXAMPLE" for row in subset) / len(subset))
        bars = ax.bar(
            x + (idx - 1) * width,
            rates,
            width,
            label=fr"local max $r={r_value}$",
            color=COLORS[f"r{r_value}"],
            edgecolor=NAVY,
            linewidth=0.8,
            hatch=["//", "..", "xx"][idx],
        )
        for bar, rate in zip(bars, rates):
            ax.text(bar.get_x() + bar.get_width() / 2, rate + 2.5, f"{rate:.0f}%", ha="center", va="bottom", fontsize=8)
    ax.set_title("Static pairwise capacity gap", fontweight="bold")
    ax.set_xlabel("global capacity $B$")
    ax.set_ylabel("configurations with pairwise gap (%)")
    ax.set_xticks(x, [str(capacity) for capacity in capacities])
    ax.set_ylim(0, 105)
    ax.set_yticks(np.arange(0, 101, 20))
    ax.grid(axis="y", color=GRID, alpha=0.75)
    ax.set_axisbelow(True)
    ax.legend(ncol=3, fontsize=9, loc="upper center", bbox_to_anchor=(0.5, -0.16))
    save_figure(fig, "static_pairwise_gap_bar")


def main() -> None:
    apply_publication_style()
    rows = enrich_search(read_rows("search_results.csv"))
    plot_safety_rate_bars(rows)
    plot_counterexample_steps(rows)
    plot_bridge_scaling(rows)
    plot_static_gap_bars()
    print(f"wrote publication charts to {OUT}")


if __name__ == "__main__":
    main()
