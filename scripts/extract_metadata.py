"""Extract per-paper metadata with the Gemini API -> data/papers/*.json + data/datasets/*.json.

Reads data/inventory.csv + data/text/ (run scripts/extract_text.py first).
Text-layer PDFs are sent as extracted text; scanned PDFs (needs_ocr) are sent as the PDF itself.
Resumable: papers that already have data/papers/<sha>.json are skipped; failures write nothing and are retried.

Usage: .venv/bin/python scripts/extract_metadata.py [--year 1-5] [--limit N]   (needs GEMINI_API_KEY)
"""
import csv
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from google import genai
from google.genai import types

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CORPUS = ROOT / "Kara_s hackathon project - Publications and conferences"
PAPERS = DATA / "papers"      # <sha>.json, one per unique paper
DATASETS = DATA / "datasets"  # <sha>-<nn>.json, linked by paper_id
MODEL = "gemini-3.8-flash"  # pinned for reproducibility; gemini-3.1-pro-preview if flash quality falls short
WORKERS = 8


def obj(props, required=None):
    return {"type": "object", "properties": props,
            "required": required or list(props), "additionalProperties": False}


STR, NUM, BOOL = {"type": "string"}, {"type": "number"}, {"type": "boolean"}
NSTR, NNUM = {"type": ["string", "null"]}, {"type": ["number", "null"]}
STRS = {"type": "array", "items": STR}


def enum(*v):
    return {"type": "string", "enum": list(v)}


DATASET = obj({
    "name": STR,
    "role": enum("training", "evaluation", "both", "forcing_or_input", "reference_only"),
    "source_kind": enum("simulation", "observation", "reanalysis", "laboratory", "benchmark", "derived_product", "other"),
    "model_or_instrument": NSTR,  # e.g. "SAM CRM", "E3SM-MMF", "Argo floats", "SOCAT"
    "scale": enum("DNS", "LES", "CRM", "regional", "GCM_ESM", "column_or_box", "point_or_site", "global_obs", "other"),
    "data_types": {"type": "array", "items": enum(
        "time_series", "spatial_2d", "spatial_3d", "spatiotemporal", "tabular", "images", "trajectories", "text", "other")},
    "size_as_stated": NSTR,  # verbatim from paper, e.g. "~10 TB", "1.2M samples"
    "size_gb_estimate": NNUM,  # null unless the paper gives enough to estimate
    "resolution": NSTR,
    "produced_in_this_study": BOOL,
    "access": NSTR,  # URL / DOI / repo / "available on request" / "NCAR Derecho" verbatim
    "access_kind": enum("public_url_or_doi", "pangeo_or_cloud", "hpc_only", "on_request", "not_stated", "proprietary"),
})

SCHEMA = obj({
    "title": STR,
    "authors": STRS,  # full list in paper order; first author is authors[0]
    "pub_year": {"type": ["integer", "null"]},
    "venue": NSTR,
    "doi_or_url": NSTR,
    "doc_kind": enum("journal_article", "preprint", "conference_paper", "conference_abstract",
                     "thesis", "book_or_chapter", "report_or_review", "other"),
    "in_scope": BOOL,  # Earth/climate science or SciML for it; false for e.g. management/social-science papers
    "research_field": STR,
    "processes": STRS,
    "ml_methods": STRS,  # concrete architectures/algorithms, e.g. "U-Net", "Gaussian process", "symbolic regression"
    "ml_tasks": {"type": "array", "items": enum(
        "parameterization", "emulation", "downscaling_superres", "forecasting", "data_assimilation",
        "parameter_calibration", "uncertainty_quantification", "equation_discovery", "reconstruction_gapfilling",
        "classification_detection", "clustering_dimensionality_reduction", "causal_inference",
        "interpretability_xai", "other", "none")},
    "parameterization_target": NSTR,  # e.g. "subgrid convection", "cloud cover"; null if not a parameterization study
    "online_coupled": {"type": ["boolean", "null"]},  # ML model run coupled inside a host model?
    "host_model": NSTR,  # e.g. "CAM6", "ICON", "MITgcm"
    "datasets": {"type": "array", "items": DATASET},
    "code_availability": NSTR,
    "testbed_candidate": BOOL,  # good public dataset for benchmarking SciML parameterization methods
    "testbed_rationale": STR,
    "pain_points": STRS,  # stated limitations/challenges (stability, generalization, data access, cost...)
    "extraction_notes": STR,  # what was unclear or missing
})

PROMPT = """You are cataloguing LEAP (Learning the Earth with AI and Physics) research outputs to build \
"Earth Well", a benchmark collection of datasets for scientific machine learning in climate parameterization.

Read the document and fill the schema. Rules:
- Report only what the document states or clearly implies; use null rather than guessing. \
Put uncertainty in extraction_notes.
- List every distinct dataset or simulation the study uses or produces, with access info copied verbatim \
from data/code availability statements where present.
- size_as_stated is verbatim; size_gb_estimate only when the stated numbers allow a reasonable estimate.
- Conference abstracts are short: fill what you can and note it.
- in_scope is true for anything about Earth/climate/environmental science or ML methods for it, including \
reviews and books; false only for unrelated work (e.g. management, social science, energy markets).
- authors: every author in the order listed, as "Given Family" names; do not truncate to "et al.".
- ml_methods are concrete architectures or algorithms (e.g. "U-Net", "Gaussian process", "symbolic regression").
- online_coupled: whether the ML component runs coupled inside a host model; null if not applicable.
- testbed_candidate is true only if the data is (or is described as) accessible and suits training/evaluating \
ML parameterizations or emulators."""


def load_rows(limit=None, year=None):
    rows = [r for r in csv.DictReader(open(DATA / "inventory.csv"))
            if not r["dup_of"] and (year is None or r["year"] == year)]
    return rows[:limit] if limit else rows


def content_for(row):
    if row["needs_ocr"] == "True":  # image-only PDF: let the model read the pages
        pdf = (CORPUS / f"Year {row['year']}" / row["filename"]).read_bytes()
        doc = types.Part.from_bytes(data=pdf, mime_type="application/pdf")
    else:
        # -layout pads with runs of spaces; collapse them to save tokens
        text = re.sub(r"[ \t]+", " ", (DATA / "text" / f"{row['sha']}.txt").read_text(errors="ignore"))
        doc = types.Part.from_text(text=f"<document filename={row['filename']!r}>\n{text}\n</document>")
    return [doc, PROMPT]


CONFIG = types.GenerateContentConfig(response_mime_type="application/json", response_json_schema=SCHEMA)


def extract(client, row):
    """Returns (paper, datasets) or raises."""
    resp = client.models.generate_content(model=MODEL, contents=content_for(row), config=CONFIG)
    paper = {"paper_id": row["sha"], "year": row["year"], "filename": row["filename"], "model": MODEL,
             **json.loads(resp.text)}
    datasets = [{"dataset_id": f"{row['sha']}-{i:02d}", "paper_id": row["sha"], **d}
                for i, d in enumerate(paper.pop("datasets"), 1)]
    paper["dataset_ids"] = [d["dataset_id"] for d in datasets]
    return paper, datasets


def save(obj, path):
    tmp = path.with_suffix(".tmp")  # write-then-rename: a crash never leaves a half-written file
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False))
    tmp.rename(path)


def main(limit=None, year=None):
    PAPERS.mkdir(parents=True, exist_ok=True)
    DATASETS.mkdir(parents=True, exist_ok=True)
    todo = [r for r in load_rows(limit, year) if not (PAPERS / f"{r['sha']}.json").exists()]
    print(f"{len(todo)} to extract with {MODEL}", flush=True)
    client = genai.Client()

    def run(row):
        try:
            return row, extract(client, row), None
        except Exception as e:  # nothing is written, so the next run retries it
            return row, None, f"{type(e).__name__}: {e}"

    failed = []
    with ThreadPoolExecutor(WORKERS) as pool:
        for i, (row, result, err) in enumerate(pool.map(run, todo), 1):
            if result:
                paper, datasets = result
                for d in datasets:  # datasets first, so an existing paper file implies its datasets exist
                    save(d, DATASETS / f"{d['dataset_id']}.json")
                save(paper, PAPERS / f"{row['sha']}.json")
            else:
                failed.append(row["filename"])
            print(f"[{i}/{len(todo)}] {'ERR ' + err[:80] if err else 'ok'}  {row['filename'][:70]}", flush=True)
    print(f"{len(todo) - len(failed)} ok, {len(failed)} failed (rerun to retry) -> {PAPERS.parent}")


if __name__ == "__main__":
    def arg(flag):
        return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else None
    main(int(arg("--limit")) if arg("--limit") else None, arg("--year"))
