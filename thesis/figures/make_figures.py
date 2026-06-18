#!/usr/bin/env python3
"""Thesis figures — clean, restrained style (vector PDF + PNG preview).

Run:  python3 thesis/figures/make_figures.py
Design rules: sharp rectangles, thin dark borders, ONE accent colour, monospace
for commands, no chartjunk. Data figures trace to docs/findings_*.md (saved runs);
diagrams carry no fabricated data.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyArrowPatch
import os

OUT = os.path.dirname(os.path.abspath(__file__))

INK    = "#1a1a1a"   # near-black text / borders
GREY   = "#8a8a8a"   # secondary / inactive
LGREY  = "#e8e8e8"   # light fill
ACCENT = "#2b6cb0"   # single accent (calm blue)
ACC_FILL = "#dbe7f3"  # accent light fill

plt.rcParams.update({
    "font.size": 10.5,
    "font.family": "sans-serif",
    "font.sans-serif": ["DejaVu Sans", "Helvetica", "Arial"],
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.edgecolor": GREY,
    "axes.titlesize": 11.5,
    "axes.titleweight": "bold",
    "axes.labelsize": 10.5,
    "figure.dpi": 130,
})


def save(fig, name):
    for ext in ("pdf", "png"):
        fig.savefig(os.path.join(OUT, f"{name}.{ext}"), bbox_inches="tight")
    plt.close(fig)
    print(f"  {name}.pdf / .png")


def box(ax, x, y, w, h, lines, fill="white", border=INK, lw=1.2, fs=10,
        mono=False, tc=INK, align="center"):
    ax.add_patch(Rectangle((x, y), w, h, facecolor=fill, edgecolor=border,
                           linewidth=lw, zorder=2))
    fam = "monospace" if mono else "sans-serif"
    ax.text(x + w / 2, y + h / 2, lines, ha="center", va="center",
            fontsize=fs, family=fam, color=tc, zorder=3, linespacing=1.35)


def arr(ax, p1, p2, color=INK, lw=1.3, ls="-"):
    ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle="-|>", mutation_scale=12,
                                 linewidth=lw, color=color, linestyle=ls,
                                 shrinkA=1, shrinkB=1, zorder=1))


# =================================================== FIG: architecture (overview)
def fig_architecture():
    fig, ax = plt.subplots(figsize=(8.6, 2.5))
    ax.set_xlim(0, 12); ax.set_ylim(0, 3.4); ax.axis("off")
    y, h = 1.2, 1.0
    box(ax, 0.1, y, 1.7, h, "user\nrequest", fill=LGREY)
    box(ax, 2.3, y, 1.7, h, "Router", fill="white")
    box(ax, 4.7, 2.0, 2.4, 1.0, "Reflexer", fill=ACC_FILL, border=ACCENT, tc=ACCENT)
    box(ax, 4.7, 0.3, 2.4, 1.0, "Thinker", fill="white")
    box(ax, 7.8, y, 1.9, h, "skill CLI\n→ device", fill=LGREY)

    arr(ax, (1.8, y + h / 2), (2.3, y + h / 2))
    arr(ax, (4.0, y + h / 2 + 0.15), (4.7, 2.5), color=ACCENT)
    arr(ax, (4.0, y + h / 2 - 0.15), (4.7, 0.8))
    arr(ax, (7.1, 2.5), (7.8, y + h / 2 + 0.15), color=ACCENT)
    arr(ax, (7.1, 0.8), (7.8, y + h / 2 - 0.15))
    ax.text(4.35, 2.62, "head", fontsize=8, color=ACCENT, style="italic", ha="center")
    ax.text(4.35, 0.55, "tail", fontsize=8, color=GREY, style="italic", ha="center")
    save(fig, "fig_architecture")


# =================================================== FIG: reflexer internals
def fig_reflexer():
    fig, ax = plt.subplots(figsize=(9.2, 4.2))
    ax.set_xlim(0, 13); ax.set_ylim(0, 6); ax.axis("off")
    yc, h = 3.7, 1.2

    box(ax, 0.1, yc, 2.2, h,
        "user query\n+\nmatched pattern", fill=LGREY, fs=9.5)
    box(ax, 2.9, yc, 3.1, h,
        "Reflexer LLM (2B)\nprompt = command shape\n+ slot descriptions",
        fill=ACC_FILL, border=ACCENT, tc=ACCENT, fs=9.5)
    box(ax, 6.6, yc, 2.5, h,
        "one shell\ncommand\n(single pass)", fill="white", fs=9.5, mono=False)
    box(ax, 9.7, yc, 1.6, h, "execute\n(bash)", fill="white", fs=9.5)
    box(ax, 11.5, yc, 1.4, h, "validate", fill="white", fs=9.5)

    arr(ax, (2.3, yc + h / 2), (2.9, yc + h / 2))
    arr(ax, (6.0, yc + h / 2), (6.6, yc + h / 2))
    arr(ax, (9.1, yc + h / 2), (9.7, yc + h / 2))
    arr(ax, (11.3, yc + h / 2), (11.5, yc + h / 2))

    # success out (right/down)
    box(ax, 11.2, 1.0, 1.7, 0.95, "✓ success", fill="white", border=ACCENT, tc=ACCENT, fs=9.5)
    arr(ax, (12.2, yc), (12.2, 1.95), color=ACCENT)

    # escalation branch (failures converge downward)
    box(ax, 3.2, 0.7, 4.4, 1.0,
        "escalate → Thinker\n(llm / exec / validator error)",
        fill="white", border=GREY, tc=GREY, fs=9.5)
    for cx in (4.45, 7.85, 10.5, 12.2):  # llm, command/exec, exec, validate
        pass
    arr(ax, (4.45, yc), (4.7, 1.7), color=GREY, ls=(0, (4, 3)))
    arr(ax, (10.5, yc), (7.0, 1.7), color=GREY, ls=(0, (4, 3)))
    ax.text(6.5, 5.55, "what happens inside the reflexer", fontsize=10.5,
            weight="bold", ha="center", color=INK)
    ax.text(6.5, 5.15, "no JSON, no template render — the small model emits the "
            "command directly, then it is run and checked",
            fontsize=8.5, ha="center", color=GREY, style="italic")
    save(fig, "fig_reflexer")


# =================================================== FIG: distillation
def fig_distillation():
    fig, ax = plt.subplots(figsize=(9.0, 2.9))
    ax.set_xlim(0, 13); ax.set_ylim(0, 3.6); ax.axis("off")
    ax.axvline(6.6, 0.08, 0.78, color=GREY, ls=(0, (2, 3)), lw=1.0)
    ax.text(3.2, 3.35, "OFFLINE — once per intent", fontsize=8.5, color=GREY,
            ha="center", weight="bold")
    ax.text(9.9, 3.35, "ON-DEVICE — every request", fontsize=8.5, color=GREY,
            ha="center", weight="bold")
    y, h = 1.6, 1.0
    box(ax, 0.1, y, 2.1, h, "SKILL.md\n+ schema", fill=LGREY, fs=9.5)
    box(ax, 2.7, y, 2.0, h, "teacher\n(strong)", fill="white", fs=9.5)
    box(ax, 4.9, 0.2, 1.6, 0.9, "pattern", fill=ACC_FILL, border=ACCENT, tc=ACCENT, fs=9.5)
    box(ax, 7.2, y, 2.1, h, "Reflexer\n(2B student)", fill=ACC_FILL, border=ACCENT, tc=ACCENT, fs=9.5)
    box(ax, 9.8, y, 2.6, h, "command → device", fill=LGREY, fs=9.5)

    arr(ax, (2.2, y + h / 2), (2.7, y + h / 2))
    arr(ax, (4.7, y), (5.5, 1.1), color=INK)
    arr(ax, (5.7, 1.1), (7.4, y), color=ACCENT)
    arr(ax, (9.3, y + h / 2), (9.8, y + h / 2), color=ACCENT)
    ax.text(5.0, 1.28, "mints (frozen)", fontsize=7.5, color=INK, ha="left", style="italic")
    save(fig, "fig_distillation")


# =================================================== FIG: binding bar
def fig_binding():
    labels = ["Thinker 2B", "Thinker 4B*", "Thinker 35B", "Reflexer 2B\n+ pattern"]
    vals = [30, 10, 100, 100]
    cols = [GREY, GREY, GREY, ACCENT]
    fig, ax = plt.subplots(figsize=(6.0, 3.6))
    bars = ax.bar(labels, vals, color=cols, width=0.6, zorder=3)
    bars[2].set_color(INK)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 2.5, f"{v}", ha="center",
                fontsize=10.5, weight="bold", color=INK)
    ax.set_ylabel("binding accuracy (%)")
    ax.set_ylim(0, 116)
    ax.set_yticks([0, 50, 100])
    ax.set_title("Distillation substitutes for scale")
    ax.annotate("same accuracy,\n~17× fewer params", xy=(3, 100), xytext=(1.3, 66),
                fontsize=9, color=ACCENT, ha="center",
                arrowprops=dict(arrowstyle="-|>", color=ACCENT, lw=1.2))
    fig.text(0.10, -0.03, "*4B at ctx 4000 (confound).  Binding-only, balanced-10.",
             fontsize=7.5, color=GREY)
    save(fig, "fig_binding")


# =================================================== FIG: spectrum
def fig_spectrum():
    fig, (axL, axR) = plt.subplots(1, 2, figsize=(8.8, 3.5))
    fig.subplots_adjust(wspace=0.42)

    # left: SET-1 clean API — pass% bars, calls annotated as text (no twin axis)
    m = ["E1\nmanual", "E2\nscript"]
    p = [32, 100]; calls = [9, 2]
    bL = axL.bar(m, p, color=[GREY, ACCENT], width=0.55, zorder=3)
    for b, v, c in zip(bL, p, calls):
        axL.text(b.get_x()+b.get_width()/2, v+2.5, f"{v}%", ha="center",
                 fontsize=10, weight="bold")
        axL.text(b.get_x()+b.get_width()/2, 5, f"{c} calls", ha="center",
                 fontsize=8.5, color="white" if v > 40 else INK)
    axL.set_ylim(0, 116); axL.set_yticks([0, 50, 100])
    axL.set_ylabel("oracle pass (%)")
    axL.set_title("SET-1 clean API\nefficiency win", fontsize=10.5)

    # right: SET-2 realistic API — accuracy
    lb = ["Thinker\n2B", "Thinker\n35B", "Reflexer 2B\n+ distilled"]
    v = [25, 62.5, 80]
    bR = axR.bar(lb, v, color=[GREY, INK, ACCENT], width=0.6, zorder=3)
    for b, val in zip(bR, v):
        axR.text(b.get_x()+b.get_width()/2, val+2, f"{val:g}%", ha="center",
                 fontsize=10, weight="bold")
    axR.set_ylim(0, 100); axR.set_yticks([0, 50, 100])
    axR.set_ylabel("oracle pass (%)")
    axR.set_title("SET-2 realistic API\naccuracy win", fontsize=10.5)
    save(fig, "fig_spectrum")


# =================================================== FIG: discovery vs convention
def fig_discovery():
    fig, ax = plt.subplots(figsize=(6.4, 4.8))
    ax.set_xlim(0, 10); ax.set_ylim(0, 10)
    ax.set_xlabel("discovery  (which key?)  →  fixed by SCALE")
    ax.set_ylabel("convention  (what value?)  →  fixed by DISTILLATION")
    ax.set_title("Scale fixes discovery, not convention")
    ax.set_xticks([]); ax.set_yticks([])
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GREY)

    pts = [
        ("Thinker 2B",            1.7, 1.7, GREY,   (10, -18)),
        ("Thinker 35B",           8.2, 1.9, INK,    (0, -22)),
        ("Reflexer 2B + pattern", 8.2, 8.2, ACCENT, (0, 16)),
    ]
    for label, x, y, c, off in pts:
        ax.scatter([x], [y], s=260, color=c, zorder=3)
        ax.annotate(label, (x, y), textcoords="offset points", xytext=off,
                    ha="center", fontsize=9.5, weight="bold", color=c)
    arr(ax, (2.4, 1.7), (7.5, 1.85), color=GREY, lw=1.6)
    ax.text(4.9, 2.25, "scale", fontsize=9, color=GREY, ha="center", style="italic")
    arr(ax, (8.2, 2.7), (8.2, 7.5), color=ACCENT, lw=1.6)
    ax.text(8.55, 5.0, "distillation", fontsize=9, color=ACCENT, ha="left",
            style="italic", rotation=90)
    save(fig, "fig_discovery")


if __name__ == "__main__":
    print("figures ->", OUT)
    fig_architecture()
    fig_reflexer()
    fig_distillation()
    fig_binding()
    fig_spectrum()
    fig_discovery()
    print("done.")
