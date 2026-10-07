"""Pain points across LEAP papers -> Figures/pain_points.{png,pdf,csv}.

(a) share of in-scope papers raising each pain-point category; (b) the same per domain, as a share of that
domain's papers so domains of different size compare. Categories from summarize.PAIN_POINTS (keyword rules,
multi-label); "Other" omitted. Usage: python3 scripts/plot_pain_points.py
"""
import collections
import csv

import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

from summarize import DATA, DOMAINS, PAIN_POINTS, load, pain_categories

FIG = DATA.parent / "Figures"
INK, MUTED, GRID, BAR = "#1a1a19", "#6b6a64", "#e6e5e0", "#2a78d6"
# dataviz reference sequential blue ramp, steps 100 -> 700 (magnitude: light = low)
RAMP = LinearSegmentedColormap.from_list("blue", ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf",
                                                  "#184f95", "#0d366b"])
SHORT = {"Land & hydrology": "Land &\nhydrology"}


def main():
    papers, _, _ = load()
    scope = [p for p in papers.values() if p["in_scope"]]
    cats = [c for c, _ in PAIN_POINTS]
    has = {p["paper_id"]: {c for x in p["pain_points"] for c in pain_categories(x)} for p in scope}
    doms = list(DOMAINS)
    n_dom = {d: sum(d in p["domains"] for p in scope) for d in doms}
    share = {c: 100 * sum(c in has[p["paper_id"]] for p in scope) / len(scope) for c in cats}
    cell = {(c, d): 100 * sum(c in has[p["paper_id"]] for p in scope if d in p["domains"]) / n_dom[d]
            for c in cats for d in doms}
    order = sorted(cats, key=lambda c: share[c])  # largest at top of the barh

    FIG.mkdir(exist_ok=True)
    with open(FIG / "pain_points.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["category", "pct_all_papers", *[f"pct_{d}" for d in doms]])
        for c in order[::-1]:
            w.writerow([c, round(share[c], 1), *[round(cell[(c, d)], 1) for d in doms]])
        w.writerow(["papers (n)", len(scope), *[n_dom[d] for d in doms]])

    fig, (ax, hx) = plt.subplots(1, 2, figsize=(12.5, 8), dpi=200, sharey=True,
                                 gridspec_kw={"width_ratios": [1, 1.1], "wspace": 0.12})
    ys = range(len(order))
    ax.barh(ys, [share[c] for c in order], height=0.7, color=BAR, edgecolor="white", linewidth=1.2, zorder=3)
    for y, c in zip(ys, order):
        ax.text(share[c] + 0.6, y, f"{share[c]:.0f}%", va="center", fontsize=7.5, color=INK)
    ax.set_yticks(list(ys), order, fontsize=8.5, color=INK)
    ax.set_xlim(0, max(share.values()) * 1.15)
    ax.tick_params(axis="y", length=0, pad=4)
    ax.tick_params(axis="x", colors=MUTED, length=0, labelsize=8)
    ax.grid(axis="x", color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    for side in ax.spines.values():
        side.set_visible(False)
    ax.set_xlabel(f"% of all {len(scope)} in-scope papers", color=MUTED, fontsize=8.5)
    ax.set_title("(a) How often each pain point is raised", loc="left", fontsize=10, color=INK)

    vmax = max(cell.values())
    for x, d in enumerate(doms):
        for y, c in zip(ys, order):
            v = cell[(c, d)]
            hx.add_patch(plt.Rectangle((x - 0.5, y - 0.5), 1, 1, color=RAMP(v / vmax), ec="white", lw=1.5))
            hx.text(x, y, f"{v:.0f}", ha="center", va="center", fontsize=7.5,
                    color="white" if v / vmax > 0.45 else INK)
    hx.set_xlim(-0.5, len(doms) - 0.5)
    hx.set_ylim(-0.5, len(order) - 0.5)
    hx.set_xticks(range(len(doms)), [f"{SHORT.get(d, d)}\n(n={n_dom[d]})" for d in doms], fontsize=8.5,
                  color=INK)
    hx.xaxis.tick_top()
    hx.tick_params(length=0)
    hx.tick_params(axis="y", left=False, labelleft=False)
    for side in hx.spines.values():
        side.set_visible(False)
    hx.set_title("(b) % of each domain's papers raising it", loc="left", fontsize=10, color=INK, pad=34)

    fig.suptitle("Pain points across LEAP research", x=0.015, y=0.985, ha="left", fontsize=14, color=INK)
    fig.text(0.015, 0.95, "Limitations extracted by Gemini from each paper, grouped by keyword rules "
             "(summarize.PAIN_POINTS); a paper counts once per category and can raise several.\n"
             "~19% of pain points fit no category and are omitted. Values: Figures/pain_points.csv.",
             fontsize=7.5, color=MUTED, va="top")
    fig.subplots_adjust(top=0.85, left=0.25, right=0.98, bottom=0.07)
    for ext in ("png", "pdf"):
        fig.savefig(FIG / f"pain_points.{ext}", facecolor="white")
    print(f"-> {FIG}/pain_points.{{png,pdf,csv}}")


if __name__ == "__main__":
    main()
