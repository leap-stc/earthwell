"""Summaries over data/papers + data/datasets -> data/summary/*.csv, printed as markdown.

Usage: python3 scripts/summarize.py
"""
import collections
import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = DATA / "summary"

# ponytail: keyword rules over research_field + title (processes as fallback); multi-label, so a paper can be
# atmosphere AND ocean. Upgrade path: add a `domains` enum to SCHEMA and re-extract.
DOMAINS = {
    "Atmosphere": r"atmos|cloud|convect|precip|radiat|aerosol|boundary.layer|weather|cyclone|monsoon|"
                  r"microphys|\brain|storm(?!.surge)|nowcast|air.quality|\bwinds?\b|ice.crystal|cirrus|meteorol|"
                  r"heatwave|heat.wave",  # not "turbulence": as often ocean or channel flow
    "Ocean": r"ocean|marine|sea.surface|air.sea|pco2|mesoscale|submesoscale|coastal|storm.surge|"
             r"oceanograph|oil.slick|\bargo\b",
    "Land & hydrology": r"\bland\b|land.surface|hydrolog|soil|vegetat|ecosystem|evapotrans|groundwater|river|streamflow|"
                        r"flood|drought|wildfire|\bfire|\bcrops?\b|(?<!random )forest|photosynth|\bgpp\b|\blakes?\b|limnolog|terrestrial|"
                        r"water.storage|phenolog|biosphere",
    "Cryosphere": r"glaci|ice.sheet|sea.ice|sea_ice|snow|permafrost|cryospher|basal.friction|greenland|"
                  r"antarctic|meltwater|ice.shelf",
}
CARBON = r"carbon|co2|biogeochem"  # cross-cutting tag, reported alongside the physical domain


def doi_key(p):
    m = re.search(r"10\.\d{4,}/\S+", (p["doi_or_url"] or "").lower())
    title = re.sub(r"[^a-z]", "", (p["title"] or "").lower())[:30]
    # DOI + title start: conference DOIs are shared by different papers
    return (m.group(0).rstrip("."), title) if m else None


def domains_of(p):
    # field + title first; the processes list is broad ("radiation" in land models, "atmospheric CO2" in
    # carbon papers), so it is only a fallback when field + title match nothing
    def match(text):
        return [d for d, pat in DOMAINS.items() if re.search(pat, text.lower())]
    found = match(f"{p['research_field']} {p['title']}") or match(" ".join(p["processes"]))
    if not p["in_scope"]:
        return ["Out of scope"]
    return found or ["Climate system / methods (general)"]


def md_table(rows, cols):
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join(str(r.get(c, "")).replace("|", "/").replace("\n", " ") for c in cols) + " |"
              for r in rows]
    return "\n".join(lines)


def write_csv(name, rows, cols):
    with open(OUT / name, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def top(counter, n=4):
    return ", ".join(f"{k} ({v})" for k, v in counter.most_common(n))


def load():
    """Papers (deduped by DOI, with 'domains') and their datasets."""
    papers, seen, dropped = {}, set(), 0
    # earliest LEAP year wins when the same paper was filed twice as different PDFs (inventory missed it)
    for p in sorted((json.loads(f.read_text()) for f in (DATA / "papers").glob("*.json")),
                    key=lambda p: (p["year"], p["paper_id"])):
        k = doi_key(p)
        if k and k in seen:
            dropped += 1
            continue
        seen.add(k)
        p["domains"] = domains_of(p)
        papers[p["paper_id"]] = p
    datasets = [d for d in (json.loads(f.read_text()) for f in sorted((DATA / "datasets").glob("*.json")))
                if d["paper_id"] in papers]
    return papers, datasets, dropped


def main():
    OUT.mkdir(exist_ok=True)
    papers, datasets, dropped = load()
    print(f"{len(papers)} papers ({dropped} same-DOI duplicates dropped), {len(datasets)} datasets\n")

    # --- multi-scale (DNS/LES/CRM) dataset table
    ms = []
    for d in datasets:
        if d["scale"] not in ("DNS", "LES", "CRM"):
            continue
        p = papers[d["paper_id"]]
        ms.append({
            "scale": d["scale"], "dataset": d["name"], "model": d["model_or_instrument"] or "",
            "size": d["size_as_stated"] or "", "access_kind": d["access_kind"], "access": d["access"] or "",
            "role": d["role"], "produced_here": d["produced_in_this_study"],
            "paper": p["title"], "first_author": (p["authors"] or [""])[0], "pub_year": p["pub_year"] or "",
            "leap_year": p["year"], "ml_tasks": ", ".join(p["ml_tasks"]),
            "testbed_candidate": p["testbed_candidate"], "dataset_id": d["dataset_id"],
        })
    ms.sort(key=lambda r: (["DNS", "LES", "CRM"].index(r["scale"]), r["model"].lower(), r["dataset"].lower()))
    cols = list(ms[0])
    write_csv("multiscale_datasets.csv", ms, cols)
    print(f"## DNS / LES / CRM datasets ({len(ms)})\n")
    print(md_table([{**r, "access": r["access"][:70]} for r in ms],
                   ["scale", "dataset", "model", "size", "access_kind", "access", "first_author", "pub_year"]))

    # --- domain summary (multi-label: rows overlap)
    by_dom = collections.defaultdict(list)
    for p in papers.values():
        for d in p["domains"]:
            by_dom[d].append(p)
    order = list(DOMAINS) + ["Climate system / methods (general)", "Out of scope"]
    rows = []
    for dom in order:
        ps = by_dom.get(dom, [])
        ids = {p["paper_id"] for p in ps}
        ds = [d for d in datasets if d["paper_id"] in ids]
        rows.append({
            "domain": dom, "papers": len(ps),
            "carbon_bgc_papers": sum(bool(re.search(CARBON, (p["research_field"] + " " + " ".join(p["processes"])).lower())) for p in ps),
            "datasets": len(ds), "testbed_candidates": sum(p["testbed_candidate"] for p in ps),
            "parameterization_papers": sum("parameterization" in p["ml_tasks"] for p in ps),
            "top_ml_tasks": top(collections.Counter(t for p in ps for t in p["ml_tasks"] if t not in ("none", "other"))),
            "top_methods": top(collections.Counter(m.lower() for p in ps for m in p["ml_methods"])),
            "dataset_scales": top(collections.Counter(d["scale"] for d in ds), 5),
            "top_processes": top(collections.Counter(x.lower() for p in ps for x in p["processes"])),
        })
    write_csv("domains.csv", rows, list(rows[0]))
    write_csv("paper_domains.csv",
              [{"paper_id": p["paper_id"], "leap_year": p["year"], "title": p["title"],
                "research_field": p["research_field"], "domains": "; ".join(p["domains"])} for p in papers.values()],
              ["paper_id", "leap_year", "title", "research_field", "domains"])
    multi = sum(len(p["domains"]) > 1 for p in papers.values())
    print(f"\n## Papers by domain ({len(papers)} papers; {multi} span more than one domain)\n")
    print(md_table(rows, ["domain", "papers", "carbon_bgc_papers", "datasets", "testbed_candidates",
                          "parameterization_papers", "top_ml_tasks", "dataset_scales"]))
    print(f"\nCSVs -> {OUT}")


if __name__ == "__main__":
    main()
