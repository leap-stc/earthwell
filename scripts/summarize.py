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

# Dataset families for the testbed table: regex on dataset name -> family. First match wins; unmatched
# datasets stay as their own row. ponytail: hand-curated from the testbed-candidate names; extend as needed.
FAMILIES = [
    (r"climsim", "ClimSim (E3SM-MMF)"),
    (r"e3sm-mmf|hr-mmf", "E3SM-MMF online / hybrid runs"),
    (r"spcam|spcesm", "SPCAM / SPCESM superparameterized runs"),
    (r"dyamond|qubicc|narval", "DYAMOND / ICON storm-resolving (NARVAL, QUBICC)"),
    (r"\bsam\b.*(aquaplanet|hypohydro)", "SAM hypohydrostatic aquaplanet"),
    (r"(dns|les).*(boundary layer|channel)|a posteriori \(online\) les", "Convective boundary layer LES/DNS"),
    (r"monte carlo ray tracer|cloud botany|pinacles|trmm lba", "Cloud-scene LES + 3D radiation (Powell)"),
    (r"rising thermal bubble", "Rising thermal bubble LES (LEX / CM1)"),
    (r"tau |tau\)|kinematic driver|warm rain initiation|dsd", "Warm-rain bin microphysics box/column (TAU)"),
    (r"aida|levitation|button electrode", "Ice-growth cloud/diffusion chamber data"),
    (r"cam6.*ppe|cam6.*perturbed|cam6-ml", "CESM2/CAM6 perturbed parameter ensembles"),
    (r"\bclm", "CLM5 perturbed parameter ensembles"),
    (r"giss|\bmodele\b|modele3", "GISS ModelE runs (incl. PPE/CPE)"),
    (r"cesm2.*coupled and land", "CESM2 coupled + land PPE"),
    (r"chaosbench", "ChaosBench S2S benchmark"),
    (r"s2s forecasts", "S2S forecast archives (ECMWF, NCEP, UKMO, CMA)"),
    (r"neverworld|double gyre", "MOM6 idealized (NeverWorld2, double gyre)"),
    (r"pyqg|quasi-geostrophic", "Quasi-geostrophic turbulence (pyqg)"),
    (r"cm2\.6", "GFDL CM2.6 eddy-resolving"),
    (r"\bom4|mom6.*epbl", "GFDL OM4 / MOM6 ocean runs"),
    (r"spear", "GFDL SPEAR sea-ice DA increments"),
    (r"gotm|second-moment closure", "Ocean boundary-layer single-column (GOTM / SMC)"),
    (r"llc4320", "MITgcm LLC4320"),
    (r"the well", "The Well (Polymathic AI)"),
    (r"large ensemble testbed|pco2.*testbed", "pCO2 Large Ensemble Testbed"),
    (r"\blens\b|large ensemble|cesm.?le\b|cesm2?-le", "CESM / multi-model large ensembles"),
    (r"socat", "SOCAT surface ocean CO2"),
    (r"\bargo\b", "Argo / BGC-Argo floats"),
    (r"ceres", "CERES radiative fluxes"),
    (r"era5", "ERA5 reanalysis"),
    (r"\bcmip", "CMIP5/6 multi-model archive"),
    (r"\bmodis\b", "MODIS products"),
    (r"oisst|optimum interpolation sea surface", "NOAA OISST sea surface temperature"),
    (r"glodap", "GLODAP ocean carbon/bottle data"),
    (r"\ben4\b|en4\.", "Met Office EN4 temperature/salinity"),
    (r"\bjra|jra-?55", "JRA-55 reanalysis / JRA55-do forcing"),
    (r"merra", "MERRA-2 reanalysis"),
    (r"lorenz", "Lorenz-96 / Lorenz systems"),
    (r"\bcamels\b", "CAMELS catchment dataset"),
    (r"cloudsat|calipso", "CloudSat / CALIPSO"),
    (r"\bgoes\b", "GOES geostationary imagery"),
    (r"ibtracs", "IBTrACS tropical cyclone tracks"),
    (r"gpcp|imerg|trmm tmpa", "Satellite precipitation (GPCP, IMERG)"),
    (r"mac-lwp|liquid water path", "MAC-LWP liquid water path"),
    (r"fluxnet|fluxcom|metaflux", "FLUXNET / FLUXCOM eddy covariance"),
    (r"eddy covariance and sif|\bsif\b", "Site eddy covariance + SIF"),
    (r"nsidc", "NSIDC sea-ice concentration"),
    (r"wumi", "WUMI wildfire dataset"),
]


def family(name):
    n = name.lower()
    return next((f for pat, f in FAMILIES if re.search(pat, n)), name)


# Pain-point categories: keyword rules over the extracted pain_points text (multi-label). ponytail: ~80% of the
# 1071 pain points match at least one; the rest are one-off issues and land in "Other". Upgrade: LLM labelling.
PAIN_POINTS = [  # (category, regex); multi-label, a pain point can hit several
 ("Online stability / offline–online gap", r"online|offline|coupled (run|simulation|model)|prognostic|instabilit|unstable|drift|crash|blow.?up|a posteriori|when coupled"),
 ("Generalization / out-of-distribution", r"generali[sz]|out.of.(distribution|sample)|extrapolat|unseen|transferab|warmer climate|climate change.*(fail|limit)|\+\s?\d\s?k\b|different climate|new (region|site|climate)|domain shift|distribution shift"),
 ("Sparse / limited observations", r"sparse|sparsit|scarc|limited (observ|data|sampl|measure|in.situ)|lack of (observ|data|measure|in.situ|ground)|gaps? in|coverage|few (observ|sample|site|station)|undersampl|paucity|unobserved|partial observ|lack of (direct |continuous |temporal )?(daytime )?(observ|data|satellite|measure|continuity)|absence of (observ|data)|go offline"),
 ("Computational cost / scaling", r"comput\w* (cost|expens|burden|demand|resourc|intens)|expensive|prohibitiv|cost of|runtime|inference (cost|time)|memory|scal(e|ing) (to|up)|gpu|cpu|flops|wall.?clock"),
 ("Data volume / access / storage", r"storage|data volume|terabyte|petabyte|\btb\b|\bpb\b|archiv|data access|availab\w+ of data|not (publicly )?available|unavailab|proprietary|download|data management|i/o"),
 ("Physical consistency / conservation", r"conserv|physical(ly)? (consisten|inconsisten|constrain|implausib|realis)|non.?physical|unphysical|negative (value|concentration|diffusiv|precip)|positivity|energy balance|mass balance|violat"),
 ("Uncertainty quantification / ensembles", r"uncertaint|ensemble spread|probabilist|stochastic|aleatoric|epistemic|calibrat\w* (of )?uncertain|confidence interval|underdispers|\bspread\b|ensemble size|members"),
 ("Extremes / tails / imbalance", r"extreme|\btails?\b|\brare\b|imbalanc|false.positive|zero.?inflat|underestimat\w* (of )?(peak|high|intens)|intensity|regression toward|toward the mean"),
 ("Smoothing / loss of small-scale variance", r"blur|smooth|fine.scale (detail|variance|structure)|small.scale variance|spectral|variance (loss|underestim)|mse|double penalty|underpredict\w* variance"),
 ("Interpretability / causality / equifinality", r"interpretab|explainab|black.box|causal|equifinal|compensat\w* error|error compensation|identifiab|attribution|confound|spurious"),
 ("Structural / model error & biases", r"structural (error|uncertaint)|model (bias|error)|systematic (bias|error)|\bbias(ed|es)?\b|compensat|parametri[sz]ation (error|deficien)|inherit"),
 ("Scale mismatch / resolution / subgrid", r"resolution|scale (mismatch|aware|separat|gap)|coarse.grain|subgrid|sub.grid|footprint|representativ|spatial mismatch|grid.?scale|downscal|upscal|heterogeneit"),
 ("Measurement noise / data quality", r"label|outlier|noise|noisy|measurement (error|uncertaint)|observation(al)? (error|uncertaint|noise)|bias.correct|quality control|retriev\w* (error|uncertaint)|artifact|inconsisten\w* (between|across) (data|product|observ)"),
 ("Ill-posed inverse problems / non-uniqueness", r"ill.posed|non.?uniqu|inverse (problem|model|mapping)|invert|identifiab|degenera"),
 ("Nonlinearity / high dimensionality", r"non.?linear|high.dimension|dimensionalit|intrinsic dimension|parameter interaction|curse of"),
 ("Software / model–ML integration", r"fortran|python|interoperab|adjoint|tangent.linear|legacy|api\b|workflow|infrastructure|maintenance|software|implementation|bridg|forpy|differentiab"),
 ("Missing / simplified process representation", r"neglect|omit|ignor|exclu|absence of (dynamic|coupled|explicit)|lack of (direct )?representation|incomplete (physical )?understanding|not (explicitly )?(represent|resolv|includ|account)|missing (process|physics)|simplif|idealiz|assum"),
 ("Data harmonization / mismatch", r"regrid|coloc|mismatch|harmoni|different (grid|period|definition)|inconsistent (scaling|definition)|alignment|reconcil|distinct (spatial )?grid|fragment|heterogeneous (file|format|data)|file format"),
 ("Predictability / initialization / skill", r"predictab|initiali[sz]|lead time|horizon|skill|forecast"),
 ("Numerics / boundaries / discretization", r"boundar(y|ies)|padding|discretiz|numerical|time.?step|stiff|solver|grid.?point"),
 ("Parameter calibration / tuning", r"calibrat|tuning|tune|parameter (estimation|space|uncertaint|sensitiv|inference)|hyperparameter|perturbed parameter"),
]


def pain_categories(text):
    t = text.lower()
    return [c for c, pat in PAIN_POINTS if re.search(pat, t)] or ["Other"]


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


def testbed_datasets(papers, datasets):
    """Datasets of papers flagged testbed_candidate that are used for training/evaluation and not proprietary."""
    return [d for d in datasets
            if papers[d["paper_id"]]["testbed_candidate"] and papers[d["paper_id"]]["in_scope"]
            and d["role"] in ("training", "both", "evaluation") and d["access_kind"] != "proprietary"]


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

    # --- testbed candidates: datasets of papers flagged testbed_candidate, used for training/evaluation
    tb = []
    for d in testbed_datasets(papers, datasets):
        p = papers[d["paper_id"]]
        sc = d.get("scales", {})
        tb.append({"family": family(d["name"]), "dataset": d["name"], "domain": sc.get("domain", ""),
                   "scales": ";".join(sc.get("scales", [])), "access_kind": d["access_kind"],
                   "access": d["access"] or "", "size_gb": sc.get("size_gb") or "",
                   "dx_min_m": sc.get("dx_min_m") or "", "dt_min_s": sc.get("dt_min_s") or "",
                   "first_author": (p["authors"] or [""])[0], "pub_year": p["pub_year"] or "",
                   "paper": p["title"], "rationale": p["testbed_rationale"], "dataset_id": d["dataset_id"]})
    tb.sort(key=lambda r: (r["family"].lower(), r["dataset"].lower()))
    write_csv("testbed_datasets.csv", tb, list(tb[0]))
    rank = ["public_url_or_doi", "pangeo_or_cloud", "on_request", "hpc_only", "not_stated"]
    fams = collections.defaultdict(list)
    for r in tb:
        fams[r["family"]].append(r)
    frows = []
    for f, rs in fams.items():
        sizes = [float(r["size_gb"]) for r in rs if r["size_gb"]]
        frows.append({
            "family": f, "domain": collections.Counter(r["domain"] for r in rs).most_common(1)[0][0],
            "scales": ";".join(sorted({t for r in rs for t in r["scales"].split(";") if t})),
            "mentions": len(rs), "papers": len({r["paper"] for r in rs}),
            "best_access": min((r["access_kind"] for r in rs), key=lambda a: rank.index(a) if a in rank else 9),
            "pangeo_or_cloud": any(r["access_kind"] == "pangeo_or_cloud" for r in rs),
            "max_size_gb": max(sizes) if sizes else "",
            "authors": ", ".join(sorted({f"{r['first_author'].split()[-1]} {r['pub_year']}".strip()
                                         for r in rs if r["first_author"]})),
            "example_access": next((r["access"] for r in rs if r["access"].startswith("http")), rs[0]["access"]),
        })
    frows.sort(key=lambda r: (r["domain"], -r["papers"], r["family"]))
    write_csv("testbed_families.csv", frows, list(frows[0]))
    print(f"\n## Testbed candidate datasets ({len(tb)} datasets in {len(frows)} families)\n")
    print(md_table(frows, ["family", "domain", "scales", "papers", "best_access", "max_size_gb", "authors"]))

    # --- pain points: one row per extracted pain point, then a category summary
    pain = [{"paper_id": p["paper_id"], "leap_year": p["year"], "first_author": (p["authors"] or [""])[0],
             "pub_year": p["pub_year"] or "", "domains": "; ".join(p["domains"]), "title": p["title"],
             "pain_point": x, "categories": "; ".join(pain_categories(x))}
            for p in papers.values() if p["in_scope"] for x in p["pain_points"]]
    write_csv("pain_points.csv", pain, list(pain[0]))
    n_scope = sum(p["in_scope"] for p in papers.values())
    by_cat = collections.defaultdict(list)
    for r in pain:
        for c in r["categories"].split("; "):
            by_cat[c].append(r)
    crow = []
    for c, rs in by_cat.items():
        pids = {r["paper_id"] for r in rs}
        doms = collections.Counter(d for pid in pids for d in papers[pid]["domains"])
        example = min((r for r in rs if 40 < len(r["pain_point"]) < 140), key=lambda r: len(r["pain_point"]),
                      default=rs[0])
        crow.append({"category": c, "papers": len(pids), "pct_of_papers": round(100 * len(pids) / n_scope),
                     "mentions": len(rs), "top_domains": top(doms, 3),
                     "example": f'{example["pain_point"]} ({example["first_author"].split()[-1] if example["first_author"] else "?"} {example["pub_year"]})'})
    crow.sort(key=lambda r: (r["category"] == "Other", -r["papers"]))
    write_csv("pain_categories.csv", crow, list(crow[0]))
    print(f"\n## Pain points ({len(pain)} from {len({r['paper_id'] for r in pain})} papers; multi-label)\n")
    print(md_table(crow, ["category", "papers", "pct_of_papers", "mentions", "top_domains", "example"]))
    print(f"\nCSVs -> {OUT}")


if __name__ == "__main__":
    main()
