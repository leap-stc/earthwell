"""LEAP co-authorship network -> Figures/author_network.{png,pdf} + author_network_{nodes,edges}.csv.

Node = author with >= MIN_PAPERS papers (size = papers, color = domain they publish in most).
Edge = co-authored papers (width = count). Papers with > MAX_AUTHORS authors (consortium papers such as
Global Carbon Budget) count toward paper totals but add no edges, or they would connect everyone.
Usage: python3 scripts/plot_authors.py   (needs matplotlib, networkx)
"""
import collections
import csv
import itertools
import re
import unicodedata

import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import networkx as nx
from matplotlib.lines import Line2D

from summarize import DATA, load

FIG = DATA.parent / "Figures"
MIN_PAPERS, MAX_AUTHORS, N_LABELS = 3, 30, 35
COLORS = {"Atmosphere": "#2a78d6", "Ocean": "#eb6834", "Land & hydrology": "#1baf7a", "Cryosphere": "#eda100",
          "Climate system / methods (general)": "#e87ba4", "Out of scope": "#8a8983"}
LABELS = {"Climate system / methods (general)": "General / methods"}
INK, MUTED, EDGE = "#1a1a19", "#6b6a64", "#b9b8b1"


def author_key(name):
    # ponytail: first initial + surname; merges "Kara D. Lamb"/"Kara Lamb" and "A. R. Fay"/"Amanda R. Fay",
    # but would also merge two different people sharing both. Upgrade: ORCID lookup.
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    parts = re.findall(r"[a-z][a-z'\-]*", s)
    return f"{parts[0][0]} {parts[-1]}" if len(parts) >= 2 else None


def place_labels(fig, ax, G, pos):
    """Greedy: biggest authors first; try right/left/above/below the node, keep the first spot that overlaps no
    earlier label. ponytail: skips a label if all four collide; adjustText if that drops important names."""
    renderer = fig.canvas.get_renderer()
    placed = []
    spots = [(8, 0, "left", "center"), (-8, 0, "right", "center"), (0, 8, "center", "bottom"), (0, -8, "center", "top")]
    for k in sorted(G, key=lambda k: -G.nodes[k]["papers"])[:N_LABELS]:
        r = (12 + 9 * G.nodes[k]["papers"]) ** 0.5 / 2  # node radius in points
        for dx, dy, ha, va in spots:
            t = ax.annotate(G.nodes[k]["name"], pos[k], xytext=(dx + (r if dx > 0 else -r if dx < 0 else 0),
                                                                 dy + (r if dy > 0 else -r if dy < 0 else 0)),
                            textcoords="offset points", ha=ha, va=va, fontsize=7, color=INK, zorder=5,
                            path_effects=[pe.withStroke(linewidth=2.5, foreground="white")])
            box = t.get_window_extent(renderer).expanded(1.05, 1.15)
            if not any(box.overlaps(b) for b in placed):
                placed.append(box)
                break
            t.remove()


def main():
    papers, _, _ = load()
    variants = collections.defaultdict(collections.Counter)
    author_papers = collections.defaultdict(set)
    edges = collections.Counter()
    for p in papers.values():
        keys = []
        for a in p["authors"]:
            k = author_key(a)
            if k and k not in keys:
                keys.append(k)
                variants[k][a] += 1
                author_papers[k].add(p["paper_id"])
        if len(keys) <= MAX_AUTHORS:
            edges.update(itertools.combinations(sorted(keys), 2))

    def display(k):  # longest of the most common spellings, e.g. "Kara D. Lamb" over "K. Lamb"
        top = variants[k].most_common()
        return max((n for n, c in top if c == top[0][1]), key=len)

    def domain(k):
        c = collections.Counter(d for pid in author_papers[k] for d in papers[pid]["domains"])
        return c.most_common(1)[0][0]

    G = nx.Graph()
    for k, ps in author_papers.items():
        if len(ps) >= MIN_PAPERS:
            G.add_node(k, papers=len(ps), name=display(k), domain=domain(k))
    for (a, b), w in edges.items():
        if a in G and b in G:
            G.add_edge(a, b, weight=w)
    isolated = [n for n in G if G.degree(n) == 0]
    G.remove_nodes_from(isolated)

    FIG.mkdir(exist_ok=True)
    with open(FIG / "author_network_nodes.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["author", "papers", "coauthors_in_network", "main_domain"])
        for k in sorted(G, key=lambda k: -G.nodes[k]["papers"]):
            w.writerow([G.nodes[k]["name"], G.nodes[k]["papers"], G.degree(k), G.nodes[k]["domain"]])
    with open(FIG / "author_network_edges.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["author_a", "author_b", "joint_papers"])
        for a, b, d in sorted(G.edges(data=True), key=lambda e: -e[2]["weight"]):
            w.writerow([G.nodes[a]["name"], G.nodes[b]["name"], d["weight"]])

    for a, b, d in G.edges(data=True):  # more joint papers = shorter target distance in the layout
        d["dist"] = 1 / d["weight"] ** 0.5
    pos = nx.kamada_kawai_layout(G, weight="dist")
    fig, ax = plt.subplots(figsize=(13, 11), dpi=200)
    ws = [G[a][b]["weight"] for a, b in G.edges]
    nx.draw_networkx_edges(G, pos, ax=ax, edge_color=EDGE, width=[0.3 + 0.6 * w for w in ws],
                           alpha=[min(0.9, 0.25 + 0.15 * w) for w in ws])
    order = sorted(G, key=lambda k: G.nodes[k]["papers"])  # big nodes on top
    nx.draw_networkx_nodes(G, pos, nodelist=order, ax=ax, edgecolors="white", linewidths=0.8,
                           node_size=[12 + 9 * G.nodes[k]["papers"] for k in order],
                           node_color=[COLORS[G.nodes[k]["domain"]] for k in order])
    ax.set_axis_off()
    place_labels(fig, ax, G, pos)

    used = collections.Counter(G.nodes[k]["domain"] for k in G)
    handles = [Line2D([], [], ls="", marker="o", ms=8, mfc=c, mec="white") for d, c in COLORS.items() if used[d]]
    labels = [f"{LABELS.get(d, d)} ({used[d]})" for d in COLORS if used[d]]
    handles += [Line2D([], [], ls="", marker="o", ms=(12 + 9 * n) ** 0.5, mfc=MUTED, mec="white") for n in (3, 10, 40)]
    labels += [f"{n} papers" for n in (3, 10, 40)]
    ax.legend(handles, labels, loc="lower left", frameon=False, fontsize=8, title="Main domain  ·  papers",
              title_fontsize=8, labelspacing=1.1)
    fig.suptitle("LEAP co-authorship network", x=0.05, y=0.97, ha="left", fontsize=15, color=INK)
    fig.text(0.05, 0.945,
             f"{G.number_of_nodes()} authors with ≥{MIN_PAPERS} LEAP papers who co-authored with another of them "
             f"({len(isolated)} with no such link omitted); {G.number_of_edges()} co-author links, thicker = more joint "
             f"papers.\nFrom {len(papers)} papers; the {sum(len(p['authors']) > MAX_AUTHORS for p in papers.values())} "
             f"papers with >{MAX_AUTHORS} authors add no links. Names merged on first initial + surname. "
             f"Labels: top {N_LABELS} by paper count. Color = domain of most of their papers (keyword rules).",
             fontsize=8, color=MUTED, va="top")
    fig.subplots_adjust(left=0.02, right=0.98, top=0.92, bottom=0.02)
    for ext in ("png", "pdf"):
        fig.savefig(FIG / f"author_network.{ext}", facecolor="white")
    print(f"{G.number_of_nodes()} authors, {G.number_of_edges()} links -> {FIG}/author_network.{{png,pdf}}")


if __name__ == "__main__":
    main()
