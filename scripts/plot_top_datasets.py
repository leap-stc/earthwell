"""Top-N dataset families by number of LEAP papers/proceedings using them -> Figures/top_datasets.{png,pdf,csv}.

Counts distinct in-scope papers per dataset family (summarize.FAMILIES groups name variants). Bars colored by the
discipline most of the family's datasets were tagged with. Usage: python3 scripts/plot_top_datasets.py
"""
import collections
import csv

import matplotlib.pyplot as plt
from matplotlib.patches import Patch

from plot_testbed import DISCIPLINES
from summarize import DATA, family, load

FIG = DATA.parent / "Figures"
N = 10
CONF = {"conference_abstract", "conference_paper"}
INK, MUTED, GRID = "#1a1a19", "#6b6a64", "#e6e5e0"


def main():
    papers, datasets, _ = load()
    fam_papers, fam_domains = collections.defaultdict(set), collections.defaultdict(collections.Counter)
    for d in datasets:
        if papers[d["paper_id"]]["in_scope"]:
            f = family(d["name"])
            fam_papers[f].add(d["paper_id"])
            if d.get("scales"):
                fam_domains[f][d["scales"]["domain"]] += 1
    rows = []
    for f, pids in fam_papers.items():
        kinds = collections.Counter(papers[p]["doc_kind"] for p in pids)
        rows.append({"family": f, "papers": len(pids), "conference": sum(kinds[k] for k in CONF),
                     "domain": fam_domains[f].most_common(1)[0][0] if fam_domains[f] else "idealized_or_other",
                     "leap_years": ";".join(sorted({papers[p]["year"] for p in pids}))})
    rows.sort(key=lambda r: (-r["papers"], r["family"]))
    FIG.mkdir(exist_ok=True)
    with open(FIG / "top_datasets.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows[:50])

    top = rows[:N][::-1]  # largest at the top
    fig, ax = plt.subplots(figsize=(9, 5.4), dpi=200)
    colors = [DISCIPLINES[r["domain"]][1] for r in top]
    ax.barh(range(len(top)), [r["papers"] for r in top], height=0.68, color=colors, edgecolor="white",
            linewidth=1.5, zorder=3)
    for i, r in enumerate(top):
        extra = f"  ({r['conference']} conf.)" if r["conference"] else ""
        ax.text(r["papers"] + 0.6, i, f"{r['papers']}{extra}", va="center", fontsize=8.5, color=INK)
    ax.set_yticks(range(len(top)), [r["family"] for r in top], fontsize=9, color=INK)
    ax.set_xlim(0, top[-1]["papers"] * 1.18)
    ax.set_xlabel("Papers and conference proceedings using the dataset", color=MUTED, fontsize=9)
    ax.grid(axis="x", color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right", "bottom"):
        ax.spines[side].set_visible(False)
    ax.spines["left"].set_color(GRID)
    ax.tick_params(axis="x", colors=MUTED, length=0, labelsize=8)
    ax.tick_params(axis="y", length=0)

    used = [k for k in DISCIPLINES if any(r["domain"] == k for r in top)]
    ax.legend([Patch(color=DISCIPLINES[k][1]) for k in used], [DISCIPLINES[k][0] for k in used],
              loc="lower right", frameon=False, fontsize=8, title="Discipline", title_fontsize=8)
    n = sum(p["in_scope"] for p in papers.values())
    fig.suptitle(f"Most-used datasets across LEAP publications", x=0.02, y=0.98, ha="left", fontsize=13,
                 color=INK)
    fig.text(0.02, 0.925, f"Distinct papers/proceedings (of {n} in-scope) that use each dataset; name variants "
             "grouped into families (summarize.FAMILIES). Top 50 in Figures/top_datasets.csv.",
             fontsize=7.5, color=MUTED, va="top")
    fig.subplots_adjust(top=0.86, left=0.36, right=0.97, bottom=0.11)
    for ext in ("png", "pdf"):
        fig.savefig(FIG / f"top_datasets.{ext}", facecolor="white")
    for r in rows[:N]:
        print(r["papers"], r["conference"], r["domain"], r["family"])


if __name__ == "__main__":
    main()
