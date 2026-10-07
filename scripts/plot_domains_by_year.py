"""Papers per domain per LEAP year -> Figures/papers_by_domain_by_year.{png,pdf,csv}.

Usage: python3 scripts/plot_domains_by_year.py   (needs matplotlib)
"""
import collections
import csv
from pathlib import Path

import matplotlib.pyplot as plt

from summarize import DOMAINS, load

FIG = Path(__file__).resolve().parent.parent / "Figures"
YEARS = ["1", "2", "3", "4", "5"]
# categorical slots 1-5 of the dataviz reference palette, fixed order (validated: CVD + normal-vision pass;
# slots 3-5 are <3:1 on white: the legend + Figures/*.csv table carry identity and values)
SERIES = [*DOMAINS, "Climate system / methods (general)"]
COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]
LABELS = {"Climate system / methods (general)": "General / methods"}
INK, MUTED, GRID = "#1a1a19", "#6b6a64", "#e6e5e0"


def main():
    papers, _, _ = load()
    counts = collections.Counter((p["year"], d) for p in papers.values() for d in p["domains"])
    totals = collections.Counter(p["year"] for p in papers.values() if p["in_scope"])

    FIG.mkdir(exist_ok=True)
    with open(FIG / "papers_by_domain_by_year.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["domain", *[f"year_{y}" for y in YEARS]])
        for s in [*SERIES, "Out of scope"]:
            w.writerow([s, *[counts[(y, s)] for y in YEARS]])
        w.writerow(["In-scope papers (unique)", *[totals[y] for y in YEARS]])

    fig, ax = plt.subplots(figsize=(8, 4.8), dpi=200)
    n, width = len(SERIES), 0.16
    for i, (s, c) in enumerate(zip(SERIES, COLORS)):
        xs = [yi + (i - (n - 1) / 2) * width for yi in range(len(YEARS))]
        # white edge = the 2px surface gap between adjacent bars
        ax.bar(xs, [counts[(y, s)] for y in YEARS], width, color=c, edgecolor="white", linewidth=1.5,
               label=LABELS.get(s, s), zorder=3)
    for yi, y in enumerate(YEARS):  # year total replaces the old dashed line; bars overlap, so they don't sum to it
        top = max(counts[(y, s)] for s in SERIES)
        ax.annotate(f"{totals[y]} papers", (yi, top), xytext=(0, 6), textcoords="offset points",
                    ha="center", fontsize=8, color=MUTED)

    ax.set_xticks(range(len(YEARS)), [f"Year {y}" for y in YEARS])
    ax.set_ylim(0, max(counts[(y, s)] for y in YEARS for s in SERIES) * 1.12)  # headroom for year totals
    ax.set_ylabel("Papers", color=MUTED)
    ax.grid(axis="y", color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=MUTED, length=0)
    ax.set_title("LEAP papers by domain and reporting year", loc="left", fontsize=12, color=INK, pad=30)
    ax.text(0, 1.02, f"{sum(totals.values())} unique in-scope papers (total above each year). \nA paper can count"
            " in more than one domain; domains assigned by keyword rules.", transform=ax.transAxes,
            fontsize=8, color=MUTED)
    ax.legend(loc="upper left", frameon=False, fontsize=8)
    for ext in ("png", "pdf"):
        fig.savefig(FIG / f"papers_by_domain_by_year.{ext}", bbox_inches="tight", facecolor="white")
    print(f"-> {FIG}/papers_by_domain_by_year.{{png,pdf,csv}}")


if __name__ == "__main__":
    main()
