"""Streamlit explorer for the multi-scale LEAP datasets: space-time scatter, filters, and per-dataset metadata.
Usage: .venv/bin/streamlit run scripts/app.py
"""
import altair as alt
import pandas as pd
import streamlit as st

from summarize import family, load

st.set_page_config(page_title="LEAP Earth Well datasets", layout="wide")


@st.cache_data
def frame():
    papers, datasets, _ = load()
    rows = []
    for d in datasets:
        p, s = papers[d["paper_id"]], d.get("scales") or {}
        rows.append({
            "dataset_id": d["dataset_id"], "name": d["name"], "family": family(d["name"]),
            "domain": s.get("domain"), "scales": s.get("scales") or [d.get("scale")],
            "source_kind": d["source_kind"], "role": d["role"], "access_kind": d["access_kind"],
            "dx_min_m": s.get("dx_min_m"), "extent_m": s.get("extent_m"),
            "dt_min_s": s.get("dt_min_s"), "duration_s": s.get("duration_s"), "size_gb": s.get("size_gb"),
            "title": p["title"], "first_author": (p["authors"] or ["?"])[0], "pub_year": p["pub_year"],
            "leap_year": p["year"], "in_scope": p["in_scope"], "testbed_candidate": p["testbed_candidate"],
        })
    return pd.DataFrame(rows), papers, {d["dataset_id"]: d for d in datasets}


df, papers, by_id = frame()

with st.sidebar:
    st.header("Filters")
    q = st.text_input("Search name / model / title")
    doms = st.multiselect("Domain", sorted(df.domain.dropna().unique()))
    tags = st.multiselect("Scale", sorted({t for ts in df.scales for t in ts if t}),
                          help="e.g. DNS, LES, CRM, MMF_superparameterized, GCM_ESM")
    kinds = st.multiselect("Source kind", sorted(df.source_kind.unique()))
    access = st.multiselect("Access", sorted(df.access_kind.unique()))
    testbed = st.checkbox("Testbed-candidate papers only")
    in_scope = st.checkbox("In-scope papers only", value=True)
    axes = st.radio("Plot", ["Finest scale (dx, dt)", "Largest scale (extent, duration)"])

f = df
if q:
    hay = f.name + " " + f.title + " " + f.dataset_id.map(lambda i: by_id[i].get("model_or_instrument") or "")
    f = f[hay.str.contains(q, case=False, regex=False)]
if doms:
    f = f[f.domain.isin(doms)]
if tags:
    f = f[f.scales.map(lambda ts: bool(set(ts) & set(tags)))]
if kinds:
    f = f[f.source_kind.isin(kinds)]
if access:
    f = f[f.access_kind.isin(access)]
if testbed:
    f = f[f.testbed_candidate]
if in_scope:
    f = f[f.in_scope]

st.title("LEAP multi-scale datasets")
x, y = ("dx_min_m", "dt_min_s") if axes.startswith("Finest") else ("extent_m", "duration_s")
pts = f[(f[x] > 0) & (f[y] > 0)].assign(scale=f.scales.map(lambda ts: ts[0] if ts else None))
c1, c2, c3 = st.columns(3)
c1.metric("Datasets shown", len(f))
c2.metric("On plot (have both scales)", len(pts))
c3.metric("Papers", f.title.nunique())

pick = alt.selection_point(fields=["dataset_id"], name="pick")
chart = (alt.Chart(pts.drop(columns="scales")).mark_circle(size=70, opacity=0.75).encode(
    x=alt.X(f"{x}:Q", scale=alt.Scale(type="log"), title=f"{x} (m)"),
    y=alt.Y(f"{y}:Q", scale=alt.Scale(type="log"), title=f"{y} (s)"),
    color=alt.Color("scale:N", title="Scale"),
    tooltip=["name", "family", "domain", "scale", "source_kind", x, y, "size_gb", "first_author", "pub_year"],
).add_params(pick).properties(height=520).interactive())
event = st.altair_chart(chart, on_select="rerun", width="stretch")
st.caption("Click a point to show its metadata below. Scales are mostly estimated from the paper text (see `basis`).")

cols = ["name", "family", "domain", "scales", "source_kind", "role", "access_kind", "size_gb",
        "first_author", "pub_year", "dataset_id"]
table = st.dataframe(f[cols], on_select="rerun", selection_mode="single-row", hide_index=True,
                     width="stretch")

sel = [p["dataset_id"] for p in (event.selection.get("pick") or [])] if event and event.selection else []
sel += [f.iloc[i].dataset_id for i in table.selection.rows]
if sel:
    d = by_id[sel[-1]]
    p = papers[d["paper_id"]]
    st.subheader(d["name"])
    a, b = st.columns(2)
    with a:
        st.markdown(f"**Model / instrument:** {d.get('model_or_instrument') or '—'}  \n"
                    f"**Resolution:** {d.get('resolution') or '—'}  \n"
                    f"**Size (as stated):** {d.get('size_as_stated') or '—'}  \n"
                    f"**Access ({d['access_kind']}):** {d.get('access') or '—'}  \n"
                    f"**Data types:** {', '.join(d.get('data_types') or [])}")
        if (d.get("scales") or {}).get("note"):
            st.info(d["scales"]["note"])
    with b:
        st.markdown(f"**Paper:** {p['title']}  \n"
                    f"**Authors:** {', '.join(p['authors'][:6])}{' et al.' if len(p['authors']) > 6 else ''}  \n"
                    f"**Venue:** {p.get('venue') or '—'} ({p.get('pub_year')}), LEAP year {p['year']}  \n"
                    f"**Link:** {p.get('doi_or_url') or '—'}  \n"
                    f"**ML methods:** {', '.join(p.get('ml_methods') or []) or '—'}  \n"
                    f"**ML tasks:** {', '.join(p.get('ml_tasks') or [])}")
        if p.get("testbed_rationale"):
            st.success(f"Testbed: {p['testbed_rationale']}" if p["testbed_candidate"] else p["testbed_rationale"])
    other = df[(df.family == family(d["name"])) & (df.dataset_id != d["dataset_id"])]
    if len(other):
        st.markdown(f"**Same family used in {other.title.nunique()} other paper(s):**")
        st.dataframe(other[["name", "first_author", "pub_year", "dataset_id"]], hide_index=True)
    with st.expander("Raw JSON"):
        st.json({"dataset": d, "paper": p})
