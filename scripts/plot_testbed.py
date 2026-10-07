"""Testbed-candidate dataset families on one space-time diagram -> Figures/testbed_scales{,_slide}.{png,pdf} + .csv.

Same style as plot_scales.py (log-decade axes, gray = below a ~100 km GCM grid). One mark per dataset family
(summarize.FAMILIES): a box from the family's finest grid spacing / time interval to its largest extent /
longest record, and a dot at the finest scale sized by the largest known data volume (hollow = unknown).
Colored by discipline. Usage: python3 scripts/plot_testbed.py
"""
import collections
import csv
import math
import re

import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
from matplotlib.text import Text

from plot_scales import FIG, GCM_DT, GCM_DX, INK, MUTED, SUBGRID, X1, Y1, area, decade_axis, lg
from summarize import family, load, testbed_datasets

DISCIPLINES = {  # same colors as the other figures; "idealized / other" is neutral gray
    "atmosphere": ("Atmosphere", "#2a78d6"), "ocean": ("Ocean", "#eb6834"),
    "land_hydrology": ("Land & hydrology", "#1baf7a"), "cryosphere": ("Cryosphere", "#eda100"),
    "coupled_earth_system": ("Coupled Earth system", "#e87ba4"), "idealized_or_other": ("Idealized / other", "#8a8983"),
}


def families():
    papers, datasets, _ = load()
    groups = collections.defaultdict(list)
    for d in testbed_datasets(papers, datasets):
        groups[family(d["name"])].append(d)
    out = []
    for name, ds in groups.items():
        sc = [d["scales"] for d in ds if d.get("scales")]

        def pick(key, f):
            vals = [s[key] for s in sc if s.get(key)]
            return f(vals) if vals else None
        out.append({
            "family": name, "datasets": len(ds), "papers": len({d["paper_id"] for d in ds}),
            "domain": collections.Counter(s["domain"] for s in sc).most_common(1)[0][0] if sc else "",
            "dx_min_m": pick("dx_min_m", min), "extent_m": pick("extent_m", max),
            "dt_min_s": pick("dt_min_s", min), "duration_s": pick("duration_s", max),
            "size_gb": pick("size_gb", max),
            "access": "public" if any(d["access_kind"] in ("public_url_or_doi", "pangeo_or_cloud") for d in ds)
            else ds[0]["access_kind"],
        })
    return out


def short(name):
    name = re.sub(r"\s*\(.*?\)", "", name)  # drop parentheticals to keep labels compact
    return name if len(name) <= 34 else name[:34].rsplit(" ", 1)[0] + "…"


# "paper" = full detail for documents; "slide" = 16:9, big type, only the most-used families labelled
STYLES = {
    "paper": dict(suffix="", figsize=(13, 10), dot=1.4, box_lw=0.6, label_fs=6.8, tick_fs=8, axis_fs=10,
                  legend_fs=7.5, title_fs=14, sub_fs=7.5, sub_y=0.95, label_if=lambda f: True, legend_out=False, rings=(4, 7, 11),
                  margins=dict(top=0.91, left=0.07, right=0.98, bottom=0.07)),
    "slide": dict(suffix="_slide", figsize=(13.33, 7.5), dot=4.0, box_lw=1.1, label_fs=13, tick_fs=14, axis_fs=16,
                  legend_fs=12, title_fs=22, sub_fs=12, sub_y=0.91,
                  label_if=lambda f: f["papers"] >= 3 or (f["size_gb"] or 0) >= 1000 or f["dx_min_m"] < 500,
                  legend_out=True, rings=(4, 7),
                  margins=dict(top=0.86, left=0.08, right=0.75, bottom=0.12)),
}


def plot(fams, plotted, style):
    st = STYLES[style]
    fig, ax = plt.subplots(figsize=st["figsize"], dpi=200)
    ax.set_facecolor(SUBGRID)
    ax.add_patch(Rectangle((GCM_DX, GCM_DT), X1 - GCM_DX, Y1 - GCM_DT, color="white", lw=0, zorder=0))
    for f in plotted:
        color = DISCIPLINES[f["domain"]][1]
        x, y = lg(f["dx_min_m"]), lg(f["dt_min_s"])
        x2, y2 = lg(f["extent_m"]) or x, lg(f["duration_s"]) or y
        if x2 > x or y2 > y:
            ax.add_patch(Rectangle((x, y), max(x2 - x, 0.05), max(y2 - y, 0.05), fill=False, ec=color,
                                   lw=st["box_lw"], alpha=0.22, zorder=1))  # outlines only: fills mix to mud
    for f in sorted(plotted, key=lambda f: -(f["size_gb"] or 0)):
        color = DISCIPLINES[f["domain"]][1]
        known = bool(f["size_gb"])
        ax.scatter(lg(f["dx_min_m"]), lg(f["dt_min_s"]), s=area(f["size_gb"]) * st["dot"], zorder=3,
                   linewidths=1.2, facecolor=color if known else "white", edgecolor="white" if known else color)
    decade_axis(ax)
    ax.set_xlim(0, X1)  # testbed data starts at ~10 m; drop the empty sub-meter range
    ax.set_xticks(range(0, 9, 2), [f"$10^{{{v}}}$" for v in range(0, 9, 2)])
    ax.set_xticks(range(0, X1 + 1), minor=True)
    ax.tick_params(labelsize=st["tick_fs"])
    ax.set_xlabel("Spatial Scale / m", color=INK, fontsize=st["axis_fs"])
    ax.set_ylabel("Time Scale / s", color=INK, fontsize=st["axis_fs"])

    # labels: greedy, most-used families first; try 8 spots around the dot, skip if all collide
    fig.subplots_adjust(**st["margins"])
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    placed, dropped = [], []
    near = [(7, 0, "left", "center"), (-7, 0, "right", "center"), (0, 7, "center", "bottom"),
            (0, -7, "center", "top"), (6, 6, "left", "bottom"), (-6, 6, "right", "bottom"),
            (6, -6, "left", "top"), (-6, -6, "right", "top")]
    # second ring further out, drawn with a leader line so the label still points at its dot
    spots = [(*s, False) for s in near] + [(dx * k, dy * k, ha, va, True) for k in st["rings"]
                                           for dx, dy, ha, va in near]
    for f in sorted(plotted, key=lambda f: (-f["papers"], -(f["size_gb"] or 0))):
        if not st["label_if"](f):
            continue
        r = math.sqrt(area(f["size_gb"]) * st["dot"]) / 2
        for dx, dy, ha, va, leader in spots:
            off = (dx + math.copysign(r, dx) if dx else 0, dy + math.copysign(r, dy) if dy else 0)
            t = ax.annotate(short(f["family"]), (lg(f["dx_min_m"]), lg(f["dt_min_s"])), xytext=off,
                            textcoords="offset points", ha=ha, va=va, fontsize=st["label_fs"], color=INK, zorder=5,
                            path_effects=[pe.withStroke(linewidth=st["label_fs"] / 3, foreground="white")],
                            arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.8, shrinkA=2, shrinkB=r + 1)
                            if leader else None)
            t.update_positions(renderer)  # text-only extent: Annotation.get_window_extent would include the leader
            box = Text.get_window_extent(t, renderer).expanded(1.04, 1.1)
            if not any(box.overlaps(b) for b in placed) and ax.bbox.contains(box.x0, box.y0) \
                    and ax.bbox.contains(box.x1, box.y1):
                placed.append(box)
                break
            t.remove()
        else:
            dropped.append(f["family"])

    used = collections.Counter(f["domain"] for f in plotted)
    mk = st["legend_fs"] * 0.8
    handles = [Line2D([], [], ls="", marker="s", ms=mk, mfc=c, mec="white") for k, (_, c) in DISCIPLINES.items()
               if used[k]]
    labels = [f"{n} ({used[k]})" for k, (n, _) in DISCIPLINES.items() if used[k]]
    sizes = [(1, "1 GB"), (1e3, "1 TB"), (1e6, "1 PB")]
    handles += [Line2D([], [], ls="", marker="o", ms=math.sqrt(area(g) * st["dot"]), mfc=MUTED, mec="white")
                for g, _ in sizes]
    handles += [Line2D([], [], ls="", marker="o", ms=math.sqrt(area(None) * st["dot"]), mfc="white", mec=MUTED),
                Rectangle((0, 0), 1, 1, fc=SUBGRID, ec=MUTED, lw=0.5)]
    labels += [t for _, t in sizes] + ["size unknown", "below ~100 km\nGCM grid"]
    where = dict(loc="upper left", bbox_to_anchor=(1.02, 1.0)) if st["legend_out"] else dict(loc="upper left")
    ax.legend(handles, labels, **where, frameon=not st["legend_out"], facecolor="white", edgecolor="none",
              framealpha=0.9, fontsize=st["legend_fs"], labelspacing=1.0, borderaxespad=0,
              title="Discipline (families)" if st["legend_out"] else "Discipline (families)  ·  data volume",
              title_fontsize=st["legend_fs"], alignment="left")

    m = st["margins"]
    fig.suptitle("Testbed candidate datasets across space and time scales", x=m["left"], y=0.975, ha="left",
                 fontsize=st["title_fs"], color=INK)
    if style == "slide":
        sub = (f"{len(plotted)} dataset families · dot = finest resolved scale, sized by data volume · "
               "outline = full extent and record length")
    else:
        sub = (f"{len(plotted)} of {len(fams)} dataset families from papers flagged as testbed candidates (others "
               "lack a grid spacing or time interval). Outline = finest scale → largest extent and record; dot = "
               "finest scale.\nScales extracted by Gemini, many estimated; families grouped by name "
               "(summarize.FAMILIES). Values: Figures/testbed_scales.csv."
               + (f" Unlabelled for space: {len(dropped)}." if dropped else ""))
    fig.text(m["left"], st["sub_y"], sub, fontsize=st["sub_fs"], color=MUTED, va="top")
    for ext in ("png", "pdf"):
        fig.savefig(FIG / f"testbed_scales{st['suffix']}.{ext}", facecolor="white")
    plt.close(fig)
    print(f"[{style}] {len(plotted)}/{len(fams)} families plotted, {len(placed)} labelled, {len(dropped)} crowded out")


def main():
    fams = families()
    plotted = [f for f in fams if f["dx_min_m"] and f["dt_min_s"]]
    FIG.mkdir(exist_ok=True)
    with open(FIG / "testbed_scales.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(fams[0]) + ["plotted"])
        w.writeheader()
        w.writerows({**f, "plotted": f in plotted} for f in sorted(fams, key=lambda f: f["family"]))
    for style in STYLES:
        plot(fams, plotted, style)


if __name__ == "__main__":
    main()
