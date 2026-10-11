"""Co-authorship network page: same author merging and domain colors as plot_authors.py, but interactive."""
import collections
import itertools

import altair as alt
import networkx as nx
import pandas as pd
import streamlit as st

from plot_authors import COLORS, author_key
from summarize import load

st.set_page_config(page_title="LEAP authorship network", layout="wide")


@st.cache_data
def authors():
    papers, _, _ = load()
    variants, author_papers = collections.defaultdict(collections.Counter), collections.defaultdict(set)
    for p in papers.values():
        for a in p["authors"]:
            if k := author_key(a):
                variants[k][a] += 1
                author_papers[k].add(p["paper_id"])
    names = {k: max((n for n, c in v.items() if c == max(v.values())), key=len) for k, v in variants.items()}
    return papers, {k: sorted(v) for k, v in author_papers.items()}, names


@st.cache_data
def graph(min_papers, max_authors, years):
    papers, author_papers, names = authors()
    keep = {pid for pid, p in papers.items() if p["year"] in years}
    counts = {k: [p for p in ps if p in keep] for k, ps in author_papers.items()}
    G = nx.Graph()
    for k, ps in counts.items():
        if len(ps) >= min_papers:
            dom = collections.Counter(d for pid in ps for d in papers[pid]["domains"]).most_common(1)[0][0]
            G.add_node(k, name=names[k], papers=len(ps), domain=dom)
    w = collections.Counter()
    for pid in keep:
        ks = sorted({author_key(a) for a in papers[pid]["authors"]} - {None})
        if len(ks) <= max_authors:
            w.update(e for e in itertools.combinations(ks, 2) if e[0] in G and e[1] in G)
    G.add_weighted_edges_from((a, b, n) for (a, b), n in w.items())
    G.remove_nodes_from([n for n in list(G) if G.degree(n) == 0])
    pos = nx.spring_layout(G, k=1.5 / len(G) ** 0.5, iterations=200, seed=1, weight="weight") if len(G) else {}
    nodes = pd.DataFrame([{"key": k, **G.nodes[k], "coauthors": G.degree(k), "x": pos[k][0], "y": pos[k][1]}
                          for k in G])
    edges = pd.DataFrame([{"a": a, "b": b, "joint": d["weight"], "x": pos[a][0], "y": pos[a][1],
                           "x2": pos[b][0], "y2": pos[b][1]} for a, b, d in G.edges(data=True)])
    return nodes, edges


papers, author_papers, names = authors()
years = sorted({p["year"] for p in papers.values()})
with st.sidebar:
    st.header("Network")
    min_papers = st.slider("Min papers per author", 1, 15, 3)
    max_authors = st.slider("Skip co-author links from papers with more authors than", 5, 100, 30,
                            help="Consortium papers would otherwise connect everyone")
    yrs = st.multiselect("LEAP year", years, default=years)
    min_joint = st.slider("Min joint papers to draw a link", 1, 10, 1)

st.title("LEAP co-authorship network")
nodes, edges = graph(min_papers, max_authors, tuple(yrs))
if nodes.empty:
    st.warning("No authors match these settings.")
    st.stop()
edges = edges[edges.joint >= min_joint]
focus = st.selectbox("Find an author", [""] + sorted(nodes.name), help="Or click a node")

c1, c2, c3 = st.columns(3)
c1.metric("Authors", len(nodes))
c2.metric("Links", len(edges))
c3.metric("Papers (selected years)", sum(p["year"] in yrs for p in papers.values()))

pick = alt.selection_point(fields=["key"], name="pick")
ax = alt.Axis(labels=False, ticks=False, grid=False, title=None, domain=False)
hl = nodes.key[nodes.name == focus].tolist()
if hl:
    nbrs = set(edges.b[edges.a == hl[0]]) | set(edges.a[edges.b == hl[0]]) | {hl[0]}
    nodes = nodes.assign(dim=~nodes.key.isin(nbrs))
    edges = edges.assign(dim=~((edges.a == hl[0]) | (edges.b == hl[0])))
else:
    nodes, edges = nodes.assign(dim=False), edges.assign(dim=False)
op = alt.condition("datum.dim", alt.value(0.12), alt.value(0.85))
color = alt.Color("domain:N", scale=alt.Scale(domain=list(COLORS), range=list(COLORS.values())), title="Main domain")
chart = alt.layer(
    alt.Chart(edges).mark_rule(color="#b9b8b1").encode(
        x=alt.X("x:Q", axis=ax), y=alt.Y("y:Q", axis=ax), x2="x2", y2="y2",
        strokeWidth=alt.StrokeWidth("joint:Q", scale=alt.Scale(range=[0.4, 5]), legend=None),
        opacity=alt.condition("datum.dim", alt.value(0.05), alt.value(0.45))),
    alt.Chart(nodes).mark_circle(stroke="white", strokeWidth=0.8).encode(
        x="x:Q", y="y:Q", color=color, opacity=op,
        size=alt.Size("papers:Q", scale=alt.Scale(range=[30, 900]), title="Papers"),
        tooltip=["name", "papers", "coauthors", "domain"]).add_params(pick),
    alt.Chart(nodes.nlargest(25, "papers")).mark_text(dy=-12, fontSize=11).encode(x="x:Q", y="y:Q", text="name"),
).properties(height=700).interactive()
event = st.altair_chart(chart, on_select="rerun", width="stretch")
st.caption("Authors are merged on first initial + surname. Click a node, or pick a name above, to list their papers.")

clicked = [p["key"] for p in (event.selection.get("pick") or [])] if event and event.selection else []
key = clicked[-1] if clicked else (hl[0] if hl else None)
if key:
    st.subheader(names[key])
    co = pd.concat([edges[edges.a == key].rename(columns={"b": "k"}), edges[edges.b == key].rename(columns={"a": "k"})])
    a, b = st.columns([1, 2])
    with a:
        st.markdown("**Co-authors in network**")
        st.dataframe(co.assign(name=co.k.map(names))[["name", "joint"]].sort_values("joint", ascending=False),
                     hide_index=True)
    with b:
        st.markdown("**Papers**")
        st.dataframe(pd.DataFrame([{"title": papers[pid]["title"], "year": papers[pid]["pub_year"],
                                    "LEAP year": papers[pid]["year"], "domains": ", ".join(papers[pid]["domains"]),
                                    "link": papers[pid].get("doi_or_url")}
                                   for pid in author_papers[key] if papers[pid]["year"] in yrs]),
                     hide_index=True, column_config={"link": st.column_config.LinkColumn()})
