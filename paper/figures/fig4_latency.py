#!/usr/bin/env python3
"""Figure 4 — Reflexer (SLM, real LLM call) vs Thinker (full LLM, dry-bash) latency.

Box-plot on log scale; medians + p95 + max annotated.
n=35 atomic Reflexer + n=38 Thinker dry-bash tasks.

Output: paper/figures/fig4_latency.pdf
"""
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

R_REPORT = Path(__file__).parent.parent.parent / "benchmark/reports/thesis-reflexer-ministral-reflexer_only-2026-05-28T10-44-53.json"
T_REPORT = Path(__file__).parent.parent.parent / "benchmark/reports/thesis-thinker-ministral-dry-2026-05-28T10-31-41.json"
OUT = Path(__file__).parent / "fig4_latency.pdf"

with R_REPORT.open() as f:
    r = json.load(f)
with T_REPORT.open() as f:
    t = json.load(f)

reflexer = [x["reflexerLlmLatencyMs"] for x in r["tasks"] if x.get("reflexerLlmLatencyMs")]
thinker = [x["totalTime"] for x in t["tasks"] if x.get("totalTime")]


def stats(arr):
    arr_s = sorted(arr)
    return {
        "n": len(arr_s),
        "median": arr_s[len(arr_s) // 2],
        "p95": arr_s[int(len(arr_s) * 0.95)],
        "max": max(arr_s),
        "min": min(arr_s),
    }


sr, st = stats(reflexer), stats(thinker)

fig, ax = plt.subplots(figsize=(3.4, 3.0))

bp = ax.boxplot(
    [reflexer, thinker],
    tick_labels=[f"Reflexer\n(SLM, n={sr['n']})", f"Thinker\n(LLM, n={st['n']})"],
    showfliers=True,
    widths=0.55,
    patch_artist=True,
    medianprops=dict(color="black", linewidth=1.5),
    boxprops=dict(linewidth=0.6),
    whiskerprops=dict(linewidth=0.6),
    capprops=dict(linewidth=0.6),
    flierprops=dict(marker="o", markersize=2.5, markerfacecolor="gray",
                    markeredgewidth=0, alpha=0.5),
)
for patch, color in zip(bp["boxes"], ["#1f77b4", "#ff7f0e"]):
    patch.set_facecolor(color)
    patch.set_alpha(0.65)

ax.set_yscale("log")
ax.set_ylabel("Latency (ms, log scale)", fontsize=9)
ax.set_ylim(80, 200_000)
ax.grid(axis="y", which="both", linewidth=0.3, alpha=0.5)
ax.set_axisbelow(True)

# Annotate median, p95 next to each box
ax.text(1, sr["median"] * 1.25, f"med {sr['median']}ms", fontsize=7, ha="center", color="black")
ax.text(1, sr["p95"] * 1.25, f"p95 {sr['p95']}ms", fontsize=6.5, ha="center", color="gray")
ax.text(2, st["median"] * 1.25, f"med {st['median']}ms", fontsize=7, ha="center", color="black")
ax.text(2, st["p95"] * 1.25, f"p95 {st['p95']}ms", fontsize=6.5, ha="center", color="gray")

# Speedup callout
speedup = st["median"] / sr["median"]
ax.text(0.5, 0.97, f"Reflexer median is {speedup:.1f}× faster than Thinker",
        transform=ax.transAxes, ha="center", va="top",
        fontsize=8, style="italic",
        bbox=dict(boxstyle="round,pad=0.3", facecolor="lightyellow",
                  edgecolor="gray", linewidth=0.4))

plt.tight_layout()
plt.savefig(OUT, bbox_inches="tight", pad_inches=0.05)
print(f"wrote {OUT}  (reflexer median={sr['median']}ms, thinker median={st['median']}ms, speedup={speedup:.1f}x)")
