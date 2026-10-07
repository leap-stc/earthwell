"""Second Gemini pass: numeric space/time scales, size and domain for each existing dataset.

For each paper, sends the paper (same input as extract_metadata.py) plus its already-extracted dataset list,
and merges the answers into data/datasets/<id>.json under the key "scales". Dataset IDs stay stable.
Resumable: papers whose datasets all have "scales" are skipped.

Usage: .venv/bin/python scripts/extract_scales.py [--year 1-5] [--limit N]   (needs GEMINI_API_KEY)
"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor

from google import genai
from google.genai import types

from extract_metadata import DATASETS, MODEL, PAPERS, WORKERS, content_for, load_rows, save

NNUM = {"type": ["number", "null"]}
SCALES = {
    "type": "object",
    "properties": {
        "dataset_id": {"type": "string"},
        "domain": {"type": "string", "enum": ["atmosphere", "ocean", "land_hydrology", "cryosphere",
                                              "coupled_earth_system", "idealized_or_other"]},
        "scales": {"type": "array", "items": {"type": "string", "enum": [
            "DNS", "LES", "CRM", "MMF_superparameterized", "regional", "GCM_ESM", "column_or_box",
            "point_or_site", "global_obs", "other"]}},
        "dx_min_m": NNUM, "dx_max_m": NNUM, "extent_m": NNUM,
        "dt_min_s": NNUM, "dt_max_s": NNUM, "duration_s": NNUM,
        "size_gb": NNUM,
        "basis": {"type": "string", "enum": ["stated", "estimated_from_paper", "unknown"]},
        "note": {"type": "string"},
    },
    "required": ["dataset_id", "domain", "scales", "dx_min_m", "dx_max_m", "extent_m", "dt_min_s", "dt_max_s",
                 "duration_s", "size_gb", "basis", "note"],
    "additionalProperties": False,
}
SCHEMA = {"type": "object", "properties": {"datasets": {"type": "array", "items": SCALES}},
          "required": ["datasets"], "additionalProperties": False}

PROMPT = """The datasets below were previously extracted from this document. For EACH dataset_id, give its \
space and time scales as numbers in SI units, using the document (and well-known facts about named datasets \
such as ERA5, CMIP6, SOCAT, ClimSim when the document names them).

- dx_min_m / dx_max_m: finest and coarsest horizontal grid spacing or sampling resolution in meters \
(equal if only one; 1 degree = 111000 m). Several resolutions (e.g. low-res and high-res) -> min and max.
- extent_m: largest horizontal size of the domain in meters (global = 4.0e7; a single site or column = its \
footprint or grid cell if stated, else null).
- dt_min_s / dt_max_s: model time step or output/sampling interval in seconds (hourly = 3600, daily = 86400, \
monthly = 2.6e6, annual = 3.15e7). Use the output/sampling interval of the data as used, not the solver step, \
unless only the solver step is given.
- duration_s: total time span of the record or simulation in seconds (e.g. 1980-2020 = 41 years = 1.29e9).
- size_gb: total data volume in GB if stated or computable (grid points x variables x time steps x 4 bytes); vague statements give an order of magnitude ("several TB" -> 3000, basis estimated_from_paper); else null.
- domain: the Earth-system component this dataset represents. coupled_earth_system only for genuinely \
coupled multi-component output; idealized_or_other for toy models, lab or non-Earth data.
- scales: every applicable label. Multi-scale modeling framework / superparameterized output (e.g. ClimSim, \
E3SM-MMF, SPCAM) gets both MMF_superparameterized and GCM_ESM.
- basis: "stated" if the numbers are in the document, "estimated_from_paper" if inferred, "unknown" if all null.
- For simulations (DNS/LES/CRM/GCM), look for grid spacing, domain size, number of grid points, time step and run length in the methods, tables and appendices: dx = domain size / grid points when only those are given.
- Use null when there is no basis for a value; do not invent. Non-spatial data (e.g. Lorenz-96) has null \
spatial fields. note: one short line on anything assumed.

Datasets:
"""


def datasets_of(paper):
    return [json.loads((DATASETS / f"{i}.json").read_text()) for i in paper["dataset_ids"]]


def extract(client, row, paper):
    ds = datasets_of(paper)
    listing = "\n".join(json.dumps({k: d.get(k) for k in ("dataset_id", "name", "model_or_instrument", "scale",
                                                          "resolution", "size_as_stated")}, ensure_ascii=False)
                        for d in ds)
    doc = content_for(row)[0]
    resp = client.models.generate_content(
        model=MODEL, contents=[doc, PROMPT + listing],
        config=types.GenerateContentConfig(response_mime_type="application/json", response_json_schema=SCHEMA))
    got = {s["dataset_id"]: s for s in json.loads(resp.text)["datasets"]}
    missing = [d["dataset_id"] for d in ds if d["dataset_id"] not in got]
    if missing:  # write nothing, so a rerun retries the whole paper
        raise ValueError(f"no answer for {missing}")
    for d in ds:
        d["scales"] = {k: v for k, v in got[d["dataset_id"]].items() if k != "dataset_id"} | {"model": MODEL}
        save(d, DATASETS / f"{d['dataset_id']}.json")


def main(limit=None, year=None):
    todo = []
    for row in load_rows(None, year):
        paper = json.loads((PAPERS / f"{row['sha']}.json").read_text())
        if paper["dataset_ids"] and not all("scales" in d for d in datasets_of(paper)):
            todo.append((row, paper))
    todo = todo[:limit] if limit else todo
    print(f"{len(todo)} papers to process with {MODEL}", flush=True)
    client = genai.Client()

    def run(item):
        try:
            extract(client, *item)
            return item[0], None
        except Exception as e:
            return item[0], f"{type(e).__name__}: {e}"

    failed = 0
    with ThreadPoolExecutor(WORKERS) as pool:
        for i, (row, err) in enumerate(pool.map(run, todo), 1):
            failed += bool(err)
            print(f"[{i}/{len(todo)}] {'ERR ' + err[:80] if err else 'ok'}  {row['filename'][:70]}", flush=True)
    print(f"{len(todo) - failed} ok, {failed} failed (rerun to retry)")


if __name__ == "__main__":
    def arg(flag):
        return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else None
    main(int(arg("--limit")) if arg("--limit") else None, arg("--year"))
