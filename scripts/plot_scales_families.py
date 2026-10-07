"""All LEAP datasets by family on space-time axes, styled after the legoESM dataset-scales figure
-> Figures/dataset_scales_families.{png,pdf,csv}.

One panel per domain; one translucent ellipse per dataset family spanning the median member's finest scale
(grid spacing, sampling interval) to its domain size and record length; colored by data type; numbered markers
with a key under each panel ([n] = datasets in the family). Datasets with space but no time go in a "static" row.
Named families come from summarize.FAMILIES; small or unmatched ones are pooled by data type and scale so each
panel stays readable. Usage: python3 scripts/plot_scales_families.py
"""
import collections
import csv
import math
import statistics

import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse, Patch

from summarize import DATA, FAMILIES, family, load

FIG = DATA.parent / "Figures"
PANELS = [("Atmosphere", {"atmosphere"}), ("Ocean & cryosphere", {"ocean", "cryosphere"}),
          ("Land & hydrology", {"land_hydrology"}), ("Coupled & idealized", {"coupled_earth_system", "idealized_or_other"})]
TYPES = {  # legoESM categories and colors
    "Idealized benchmark": "#9a7fc0", "Model simulation": "#e0a04a", "Derived / generated product": "#3a9a6a",
    "Observation / reanalysis": "#2f6db5", "Other": "#8a8983",
}
POOL = {"DNS": "process-scale", "LES": "process-scale", "CRM": "process-scale", "column_or_box": "process-scale",
        "MMF_superparameterized": "global", "GCM_ESM": "global", "global_obs": "global", "regional": "regional",
        "point_or_site": "site/point", "other": "misc."}
MIN_FAMILY, MIN_POOL = 3, 4  # named families < MIN_FAMILY (within a panel) are pooled; pools < MIN_POOL -> "Other (misc.)"
STATIC_Y, SEP_Y, Y0, Y1, X0, X1 = 13.6, 13.15, -1, 14.1, 0, 8
X_REFS = [(0, "1 m"), (3, "1 km"), (6, "1000 km"), (7.6, "Earth")]
Y_REFS = [(0, "1 s"), (3.556, "1 h"), (4.936, "1 d"), (7.5, "1 yr"), (9.5, "100 yr"), (11.5, "10 kyr")]
INK, MUTED, PANEL_BG = "#1a1a19", "#6b6a64", "#f3f3f2"


def data_type(d):
    kind, dom = d["source_kind"], d["scales"]["domain"]
    if kind == "benchmark" or (kind == "simulation" and dom == "idealized_or_other"):
        return "Idealized benchmark"
    return {"simulation": "Model simulation", "observation": "Observation / reanalysis",
            "reanalysis": "Observation / reanalysis", "derived_product": "Derived / generated product"}.get(kind, "Other")


def lg(v):
    return math.log10(v) if v and v > 0 else None


def build():
    papers, datasets, _ = load()
    named = {f for _, f in FAMILIES}
    ds = [d for d in datasets if papers[d["paper_id"]]["in_scope"] and d.get("scales")]
    panel_of = {dom: name for name, doms in PANELS for dom in doms}

    def pool(d):
        scale = POOL.get((d["scales"]["scales"] or ["other"])[0], "misc.")
        return f"Other {data_type(d).split(' /')[0].lower()}: {scale}"

    # pool within each panel: small named families -> type/scale pools -> small pools -> "Other (misc.)"
    by_panel = collections.defaultdict(list)
    for d in ds:
        by_panel[panel_of[d["scales"]["domain"]]].append(d)
    merged = {}
    for panel, members in by_panel.items():
        size = collections.Counter(family(d["name"]) for d in members)
        label = {id(d): family(d["name"]) if family(d["name"]) in named and size[family(d["name"])] >= MIN_FAMILY
                 else pool(d) for d in members}
        pools = collections.Counter(label.values())
        for d in members:
            f = label[id(d)] if label[id(d)] in named or pools[label[id(d)]] >= MIN_POOL else "Other (misc.)"
            merged.setdefault((panel, f), []).append(d)

    fams = []
    for (panel, f), members in merged.items():
        if True:
            xs = [(lg(m["scales"]["dx_min_m"]), lg(m["scales"]["extent_m"]) or lg(m["scales"]["dx_min_m"]))
                  for m in members if m["scales"]["dx_min_m"]]
            if not xs:
                continue  # no spatial scale (e.g. Lorenz-96): not placeable
            timed = [m for m in members if m["scales"]["dt_min_s"] or m["scales"]["duration_s"]]
            ys = [(lg(m["scales"]["dt_min_s"]) or lg(m["scales"]["duration_s"]),
                   lg(m["scales"]["duration_s"]) or lg(m["scales"]["dt_min_s"])) for m in timed]
            x_lo, x_hi = statistics.median(a for a, _ in xs), statistics.median(b for _, b in xs)
            static = not timed  # only families with no time dimension at all (maps) go in the static row
            y_lo, y_hi = ((statistics.median(a for a, _ in ys), statistics.median(b for _, b in ys))
                          if not static else (STATIC_Y, STATIC_Y))
            fams.append({"panel": panel, "family": f, "n": len(members), "static": static,
                         "type": collections.Counter(data_type(m) for m in members).most_common(1)[0][0],
                         "x_lo": x_lo, "x_hi": max(x_hi, x_lo), "y_lo": y_lo, "y_hi": max(y_hi, y_lo)})
    return fams, len(ds)


def spread(fams, gap=0.42, iters=200):
    """Nudge numbered markers apart (in log-decade units) so they don't overprint; ellipses stay put.
    ponytail: simple pairwise repulsion; markers can drift ~0.5 decade from their ellipse centre in dense clusters."""
    for f in fams:
        f["mx"], f["my"] = (f["x_lo"] + f["x_hi"]) / 2, (f["y_lo"] + f["y_hi"]) / 2
    for _ in range(iters):
        moved = False
        for i, a in enumerate(fams):
            for b in fams[i + 1:]:
                dx, dy = b["mx"] - a["mx"], (b["my"] - a["my"]) * 0.75  # y decades are drawn shorter than x
                d = math.hypot(dx, dy)
                if d < gap:
                    ux, uy = (dx / d, dy / d) if d > 1e-6 else (1.0, 0.0)
                    push = (gap - d) / 2
                    a["mx"] -= ux * push; a["my"] -= uy * push
                    b["mx"] += ux * push; b["my"] += uy * push
                    moved = True
        if not moved:
            break


def main():
    fams, n_total = build()
    FIG.mkdir(exist_ok=True)
    with open(FIG / "dataset_scales_families.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(fams[0]))
        w.writeheader()
        w.writerows(sorted(fams, key=lambda f: (f["panel"], -f["n"])))

    any_static = any(f["static"] for f in fams)  # static row only when some family has no time dimension
    fig, axes = plt.subplots(1, len(PANELS), figsize=(28, 15), dpi=150, sharey=True)
    for ax, (panel, _), tag in zip(axes, PANELS, "abcd"):
        mine = sorted((f for f in fams if f["panel"] == panel),
                      key=lambda f: (f["static"], f["x_lo"] + f["x_hi"] + f["y_lo"] + f["y_hi"]))
        ax.set_facecolor(PANEL_BG)
        for v, _ in X_REFS:
            ax.axvline(v, color="white", lw=1.2, zorder=0)
        for v, _ in Y_REFS:
            ax.axhline(v, color="white", lw=1.2, zorder=0)
        if any_static:
            ax.axhline(SEP_Y, color=MUTED, lw=0.8, ls="--", zorder=1)
        for f in mine:
            cx, cy = (f["x_lo"] + f["x_hi"]) / 2, (f["y_lo"] + f["y_hi"]) / 2
            w = max(f["x_hi"] - f["x_lo"], 0.8)
            h = 0.6 if f["static"] else max(f["y_hi"] - f["y_lo"], 0.8)
            ax.add_patch(Ellipse((cx, cy), w, h, fc=TYPES[f["type"]], ec="none", alpha=0.28, zorder=2))
        spread(mine)
        for i, f in enumerate(mine, 1):
            cx, cy = f["mx"], f["my"]
            ax.scatter(cx, cy, s=480, color=TYPES[f["type"]], ec="white", lw=1.2, zorder=4)
            ax.text(cx, cy, str(i), ha="center", va="center", fontsize=11.5, color="white", fontweight="bold", zorder=5)
            f["num"] = i
        ax.set_xlim(X0, X1)
        ax.set_ylim(Y0, Y1 if any_static else 12.6)
        ax.set_xticks(range(X0, X1 + 1, 2), [f"$10^{{{v}}}$" for v in range(X0, X1 + 1, 2)])
        ax.set_yticks([*range(0, 13, 2), *([STATIC_Y] if any_static else [])],
                      [*[f"$10^{{{v}}}$" for v in range(0, 13, 2)], *(["static"] if any_static else [])])
        ax.tick_params(colors=INK, labelsize=13, length=3)
        for v, t in X_REFS:
            ax.text(v + 0.05, Y0 + 0.1, t, fontsize=10, color=MUTED, va="bottom")
        for v, t in Y_REFS:
            ax.text(X1 - 0.05, v + 0.08, t, fontsize=10, color=MUTED, ha="right", va="bottom")
        for s in ax.spines.values():
            s.set_color(MUTED)
        ax.set_xlabel("Spatial scale / m  (grid spacing to domain size)", fontsize=14, color=INK)
        ax.set_title(f"({tag}) {panel}", loc="left", fontsize=17, color=INK)
        key = "\n".join(f"{f['num']:>3}  {f['family'][:46]} [{f['n']}]" for f in mine)
        ax.text(0.0, -0.13, key, transform=ax.transAxes, va="top", ha="left", fontsize=11, family="monospace",
                color=INK)
    axes[0].set_ylabel("Time scale / s  (sampling interval to record length)", fontsize=14, color=INK)

    placed = sum(f["n"] for f in fams)
    fig.suptitle(f"LEAP datasets across scales ({placed} of {n_total} datasets with a spatial scale; "
                 "[n] = datasets per family; extents approximate)", fontsize=20, color=INK, y=0.99)
    fig.legend([Patch(fc=c, alpha=0.5) for c in TYPES.values()], list(TYPES), loc="upper center", ncol=5,
               frameon=False, fontsize=14, bbox_to_anchor=(0.5, 0.963))
    fig.subplots_adjust(top=0.89, bottom=0.43, left=0.045, right=0.99, wspace=0.08)
    for ext in ("png", "pdf"):
        fig.savefig(FIG / f"dataset_scales_families.{ext}", facecolor="white")
    for panel, _ in PANELS:
        print(panel, sum(f["panel"] == panel for f in fams), "families")


if __name__ == "__main__":
    main()
