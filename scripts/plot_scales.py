"""Stommel-style space-time diagram of LEAP datasets -> Figures/dataset_scales.{png,pdf,csv}.

Styled after the LEAP "multi-scales and multi-processes" slide: log-decade axes, gray = scales below a ~100 km
GCM grid, white = resolved, labelled process regions behind the data. Each dataset is a faint box from its finest
scale (grid spacing, output interval) to its domain extent and record length - overlapping boxes build up shading
where coverage is dense - plus a dot at its finest scale sized by data volume (hollow = unknown).
Needs the "scales" pass (scripts/extract_scales.py). Usage: python3 scripts/plot_scales.py
"""
import csv
import math

import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Ellipse, Rectangle

from summarize import DATA, load

FIG = DATA.parent / "Figures"
# same domain colors as papers_by_domain_by_year (dataviz categorical slots 1-4)
PANELS = [("atmosphere", "Atmosphere", "#2a78d6"), ("ocean", "Ocean", "#eb6834"),
          ("land_hydrology", "Land & hydrology", "#1baf7a"), ("cryosphere", "Cryosphere", "#eda100")]
INK, MUTED, SUBGRID, EDGE = "#1a1a19", "#6b6a64", "#e4e3de", "#4a4945"
X0, X1, Y0, Y1 = -3, 8, 0, 10.6  # log10 m, log10 s
GCM_DX, GCM_DT = 5, 4.5  # ponytail: one nominal GCM (~100 km, ~9 h); a real cutoff depends on the model

# Process regions traced by eye from the LEAP slide: (label, log10 x, log10 y, width, height [decades], angle deg).
PROCESSES = {
    "atmosphere": [
        ("cloud\nmicrophysics", -1.6, 0.3, 1.6, 0.8, 0), ("turbulence", -0.35, 1.2, 4.7, 1.4, 30),
        ("convection", 2.8, 3.1, 4.2, 1.6, 36), ("organized\nconvection", 5.1, 5.1, 2.2, 1.8, 30),
        ("planetary\nwaves", 6.6, 6.1, 2.0, 2.2, 0), ("MJO", 7.05, 6.8, 1.1, 0.5, 0),
        ("seasonal cycle", 6.35, 7.5, 2.1, 0.6, 0), ("El Niño", 6.45, 8.1, 2.3, 0.8, 0),
        ("climate\nchange", 6.45, 9.7, 2.4, 2.3, 0)],
    "ocean": [
        ("molecular\nprocesses", -2.0, 0.7, 2.2, 1.7, 0), ("sub-mesoscale:\nmixing & internal waves", 0.7, 2.3, 5.8, 3.0, 32),
        ("mesoscale\n& tides", 4.3, 5.2, 6.4, 2.6, 36), ("seasonal cycle", 6.3, 7.5, 2.1, 0.6, 0),
        ("El Niño", 6.35, 8.1, 2.4, 0.8, 0), ("basin-scale\nvariability", 6.9, 9.1, 1.4, 2.3, 0),
        ("climate\nchange", 6.35, 9.8, 2.4, 2.3, 0)],
}


def area(gb):
    return 12 + 20 * max(0.0, math.log10(gb) + 1) if gb else 12  # 0.1 GB -> 12, 1 PB -> 152


def lg(v):
    return math.log10(v) if v and v > 0 else None


def rows():
    papers, datasets, _ = load()
    out = []
    for d in datasets:
        s = d.get("scales")
        if not s or not papers[d["paper_id"]]["in_scope"]:
            continue
        out.append({"dataset_id": d["dataset_id"], "name": d["name"], "domain": s["domain"],
                    "scales": ";".join(s["scales"]), "dx_m": s["dx_min_m"], "dx_max_m": s["dx_max_m"],
                    "extent_m": s["extent_m"], "dt_s": s["dt_min_s"], "dt_max_s": s["dt_max_s"],
                    "duration_s": s["duration_s"], "size_gb": s["size_gb"], "basis": s["basis"]})
    return out


def decade_axis(ax):
    ax.set_xlim(X0, X1)
    ax.set_ylim(Y0, Y1)
    ax.set_xticks(range(-2, 9, 2), [f"$10^{{{v}}}$" for v in range(-2, 9, 2)])
    ax.set_yticks(range(0, 11, 2), [f"$10^{{{v}}}$" for v in range(0, 11, 2)])
    ax.set_xticks(range(X0, X1 + 1), minor=True)
    ax.set_yticks(range(Y0, 11), minor=True)
    ax.tick_params(which="both", direction="in", top=True, right=True, colors=MUTED, labelsize=8)
    ax.tick_params(labelcolor=INK)
    for side in ax.spines.values():
        side.set_color(MUTED)


def main():
    data = rows()
    plotted = [r for r in data if r["dx_m"] and r["dt_s"]]
    FIG.mkdir(exist_ok=True)
    with open(FIG / "dataset_scales.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(data[0]) + ["plotted"])
        w.writeheader()
        w.writerows({**r, "plotted": r in plotted} for r in data)

    fig, axes = plt.subplots(2, 2, figsize=(11, 10), dpi=200)
    for ax, (key, label, color), tag in zip(axes.flat, PANELS, "abcd"):
        ax.set_facecolor(SUBGRID)  # gray = below a ~100 km GCM grid; white = resolved
        ax.add_patch(Rectangle((GCM_DX, GCM_DT), X1 - GCM_DX, Y1 - GCM_DT, color="white", lw=0, zorder=0))
        for name, x, y, wd, ht, ang in PROCESSES.get(key, []):
            ax.add_patch(Ellipse((x, y), wd, ht, angle=ang, fill=False, ec=EDGE, lw=0.9, ls=(0, (3, 2)),
                                 alpha=0.75, zorder=2.5))  # above coverage boxes, below dots
            ax.text(x, y, name, ha="center", va="center", fontsize=6.5, color=INK, zorder=4, linespacing=0.95,
                    path_effects=[pe.withStroke(linewidth=2.2, foreground="white")])

        mine = [r for r in plotted if r["domain"] == key]
        for r in mine:  # coverage boxes: faint, so overlap = density
            x, y = lg(r["dx_m"]), lg(r["dt_s"])
            x2, y2 = lg(r["extent_m"]) or x, lg(r["duration_s"]) or y
            if x2 > x or y2 > y:
                ax.add_patch(Rectangle((x, y), max(x2 - x, 0.04), max(y2 - y, 0.04), color=color, alpha=0.018,
                                       lw=0, zorder=2))
        for r in sorted(mine, key=lambda r: -(r["size_gb"] or 0)):  # big dots first so small ones stay visible
            known = bool(r["size_gb"])
            ax.scatter(lg(r["dx_m"]), lg(r["dt_s"]), s=area(r["size_gb"]), zorder=3, linewidths=0.9,
                       facecolor=color if known else "white", edgecolor="white" if known else color)

        decade_axis(ax)
        ax.text(0.02, 0.98, f"({tag}) {label}", transform=ax.transAxes, ha="left", va="top", fontsize=10,
                color=INK, fontweight="bold", zorder=4)
        ax.text(0.02, 0.93, f"{len(mine)} datasets", transform=ax.transAxes, ha="left", va="top", fontsize=8,
                color=MUTED, zorder=4)
        if key not in PROCESSES:
            ax.text(0.98, 0.02, "process regions not drawn for this domain", transform=ax.transAxes,
                    ha="right", va="bottom", fontsize=6.5, color=MUTED, style="italic")
    for ax in axes[1]:
        ax.set_xlabel("Spatial Scale / m", color=INK)
    for ax in axes[:, 0]:
        ax.set_ylabel("Time Scale / s", color=INK)

    sizes = [(1, "1 GB"), (1e3, "1 TB"), (1e6, "1 PB")]
    handles = [Line2D([], [], ls="", marker="o", ms=math.sqrt(area(g)), mfc=MUTED, mec="white") for g, _ in sizes]
    handles += [Line2D([], [], ls="", marker="o", ms=math.sqrt(area(None)), mfc="white", mec=MUTED),
                Rectangle((0, 0), 1, 1, color=MUTED, alpha=0.25, lw=0),
                Rectangle((0, 0), 1, 1, fc=SUBGRID, ec=MUTED, lw=0.5)]
    fig.legend(handles, [t for _, t in sizes] + ["size unknown", "coverage (finest scale → extent, record)",
                                                 "below ~100 km GCM grid"],
               loc="upper left", ncol=6, frameon=False, fontsize=7.5, bbox_to_anchor=(0.06, 0.928))
    fig.suptitle("Multi-scale coverage of LEAP datasets", x=0.07, y=0.985, ha="left", fontsize=14, color=INK)
    n_known = sum(bool(r["size_gb"]) for r in plotted if r["domain"] in dict((k, 1) for k, _, _ in PANELS))
    fig.text(0.07, 0.96, f"{len(plotted)} of {len(data)} in-scope datasets have a grid spacing and time interval "
             f"({n_known} in these panels have a data volume). Coupled-system and idealized datasets not shown. "
             "Scales extracted by Gemini, many estimated; process regions traced approximately from the LEAP slide.",
             fontsize=7, color=MUTED, va="top", wrap=True)
    fig.subplots_adjust(top=0.885, hspace=0.12, wspace=0.12, left=0.07, right=0.98, bottom=0.06)
    for ext in ("png", "pdf"):
        fig.savefig(FIG / f"dataset_scales.{ext}", facecolor="white")
    print(f"{len(plotted)}/{len(data)} plotted -> {FIG}/dataset_scales.{{png,pdf,csv}}")


if __name__ == "__main__":
    main()
