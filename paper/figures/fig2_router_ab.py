#!/usr/bin/env python3
"""Figure 2 — Router A/B accuracy, 5 variants x 6 categories.

Honesty rules: y starts at 0; n=53 in caption; colourblind-safe palette.
Each bar is labelled with raw correct/total to avoid percentage/count confusion.

Output: paper/figures/fig2_router_ab.pdf
"""
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

REPORT = Path(__file__).parent.parent.parent / "benchmark/reports/routing-ab-2026-05-28T10-26-15.json"
OUT = Path(__file__).parent / "fig2_router_ab.pdf"

VARIANTS = ["baseline", "+laplace", "+margin", "+position", "all_combined"]
CATS = [
    ("atomic_easy",              "Atomic\neasy"),
    ("v1_collision_regression",  "Collision\nregr."),
    ("v1_activation_regression", "Activation\nregr."),
    ("composite_easy",           "Composite\neasy"),
    ("real_world",               "Real-\nworld"),
    ("off_distribution",         "Off-\ndistr."),
]
# Distinct colourblind-safe palette (Okabe-Ito subset)
COLORS = ["#0072B2", "#E69F00", "#009E73", "#D55E00", "#CC79A7"]

with REPORT.open() as f:
    data = json.load(f)

n_v, n_c = len(VARIANTS), len(CATS)
bar_w = 0.8 / n_v
x = np.arange(n_c)

fig, ax = plt.subplots(figsize=(7.2, 3.4))

for i, v in enumerate(VARIANTS):
    by = data[v]["byCategory"]
    accs, labels = [], []
    for ckey, _ in CATS:
        s = by.get(ckey, {"correct": 0, "total": 1})
        tot = max(s["total"], 1)
        accs.append(100.0 * s["correct"] / tot)
        labels.append(f"{s['correct']}/{s['total']}")
    offs = x + (i - (n_v - 1) / 2) * bar_w
    bars = ax.bar(offs, accs, bar_w, label=v, color=COLORS[i],
                  edgecolor="black", linewidth=0.4)
    for b, lab in zip(bars, labels):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 1.5, lab,
                ha="center", va="bottom", fontsize=5.2, rotation=90)

# Legend with overall totals
legend_labels = [
    f"{v} ({data[v]['correct']}/{data[v]['total']}, {100*data[v]['correct']/data[v]['total']:.1f}%)"
    for v in VARIANTS
]
ax.set_xticks(x)
ax.set_xticklabels([c[1] for c in CATS], fontsize=8)
ax.set_ylabel("Routing accuracy (%)", fontsize=9)
ax.set_ylim(0, 118)
ax.set_yticks([0, 20, 40, 60, 80, 100])
ax.axhline(100, color="gray", linewidth=0.4, linestyle=":")
ax.grid(axis="y", linewidth=0.3, alpha=0.5)
ax.set_axisbelow(True)
ax.legend(legend_labels, fontsize=7, loc="lower center", ncol=2,
          bbox_to_anchor=(0.5, -0.46), frameon=False)

plt.tight_layout()
plt.savefig(OUT, bbox_inches="tight", pad_inches=0.05)
print(f"wrote {OUT}")
for v in VARIANTS:
    print(f"  {v}: {data[v]['correct']}/{data[v]['total']}")
