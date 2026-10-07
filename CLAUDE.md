# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**LEAP "Earth Well"** — a hackathon project (Scientific Machine Learning thrust, lead: Kara Lamb) to data-mine LEAP's (Learning the Earth with AI and Physics) past 5 years of papers and conference proceedings. Full brief: `Project Description.md`. Inspiration: Polymathic AI's "The Well" (https://arxiv.org/abs/2412.00568).

Goals, in priority order:
1. Extract per-paper metadata from the PDFs: datasets/simulations used, research field/processes, data volume (MB/GB/TB), data type (time series, spatial, etc.), model vs. observations, ML methods, and where the data can be accessed.
2. Meta-analysis of methods and problem types across LEAP's research.
3. Identify the most promising datasets for a SciML parameterization-development testbed (especially multi-scale: DNS, LES, CRM) and start a pipeline for comparing methods across them.
4. Identify datasets useful for downstream tasks (e.g. an Earth system foundation model) and shared pain points SciML methods could address.

Known risk: much data lives only on HPC (e.g. NCAR Derecho) or is too large to access. Fallback is simple benchmark systems (Lorenz 96, QG model). Future direction: integrate with / document what's already on Pangeo.

## Layout

There is no code yet — this is currently a corpus plus a brief. Git repo on `main`; the PDF folder, zip, `.idea/` and `.DS_Store` are gitignored.

- `Kara_s hackathon project - Publications and conferences/Year 1` … `Year 5/` — ~340 PDFs, one folder per LEAP reporting year.
- Each year folder has a `Year N publications and conferences.docx` (Year 2's is `LEAP Year 2 ...`): the authoritative citation list, split into sections like *Peer Reviewed*, *Non-Peer Reviewed*, *Synergistic* (peer / non-peer), and *Conference Presentations and Proceedings*. Use it to map PDFs to citations and to tag publication type.
- The `.zip` at the root is the original ~1.6 GB download of the same folder — don't extract or modify it.

## Corpus gotchas

- Some PDFs have no `.pdf` extension (names ending in `._` or none at all). Detect by content (`file`), not extension.
- Duplicates exist, both within a year (e.g. `... .pdf` and `...(1).pdf`) and across years (e.g. PythonicDISORT appears in Year 3 and Year 4). Dedupe before counting for meta-analysis.
- Many entries are conference **abstracts** (filename often ends in `Abstract.pdf`) — little detail on data size or access location.
- The corpus includes "synergistic" papers outside climate ML (e.g. corporate sustainability, social cognition, electricity trading). Filter or flag these rather than forcing them into the dataset schema.
- Filenames have spaces, `_` substituted for `:`/`?`, and non-ASCII characters — always quote paths.

## Pipeline

```
python3 scripts/extract_text.py                                    # PDFs -> data/text/<sha>.txt + data/inventory.csv (local, ~90s, cached by hash)
set -a; . ~/.claude/credentials/credentials.env; set +a            # loads GEMINI_API_KEY
.venv/bin/python scripts/extract_metadata.py --year 1             # Gemini API -> data/papers/, data/datasets/; also --limit N; no flags = all
python3 scripts/summarize.py > data/summary/summary.md         # DOI dedupe, DNS/LES/CRM table, domains, testbed families, pain points -> data/summary/*.csv
python3 scripts/plot_domains_by_year.py                           # Figures/papers_by_domain_by_year.{png,pdf,csv} (needs matplotlib; IceSciML env has it)
(cd scripts && ../.venv/bin/python extract_scales.py)              # 2nd Gemini pass: numeric dx/extent/dt/duration/size/domain -> "scales" key in data/datasets/*.json
python3 scripts/plot_scales.py                                     # Figures/dataset_scales.{png,pdf,csv}: Stommel-style space-time diagram
python3 scripts/plot_authors.py                                    # Figures/author_network.{png,pdf} + nodes/edges CSVs (needs networkx)
python3 scripts/plot_testbed.py                                    # Figures/testbed_scales{,_slide}.{png,pdf} + .csv: testbed families on one space-time plot; "slide" style = 16:9, big type, fewer labels (STYLES)
python3 scripts/plot_top_datasets.py                               # Figures/top_datasets.{png,pdf,csv}: top-10 dataset families by number of publications
python3 scripts/plot_pain_points.py                                # Figures/pain_points.{png,pdf,csv}: pain-point categories overall + per-domain heatmap
python3 scripts/plot_scales_families.py                            # Figures/dataset_scales_families.{png,pdf,csv}: all datasets by family, legoESM-style ellipses per domain
```

- `inventory.csv`: one row per file. `dup_of` points to the first copy (same hash or same normalized title), and only rows with an empty `dup_of` go to the API. `needs_ocr` rows (image-only PDFs) are sent as the PDF itself; the rest go as extracted text.
- Output is one JSON file per paper, `data/papers/<sha>.json` (`paper_id` = inventory `sha`), and one per dataset, `data/datasets/<sha>-<nn>.json`. They're linked both ways: the paper has `dataset_ids`, each dataset has `paper_id`. The same real-world dataset (e.g. SPCAM) used by several papers is **not** deduplicated yet.
- `extract_metadata.py` is resumable: papers with an existing `data/papers/<sha>.json` are skipped, and failed papers write nothing, so a rerun retries them. To re-extract a paper, delete its paper file. The model is pinned in `MODEL`. `SCHEMA` and `PROMPT` in the same file define what gets extracted (Gemini `response_json_schema`). Only `PROMPT` text reaches the model, so field definitions go there, not in code comments.
- `summarize.py` drops papers that were filed twice as different PDFs (same DOI + title start). Domains come from keyword rules over research_field + title (`DOMAINS`), which is a heuristic. Add a domain field to `SCHEMA` if it needs to be exact.
- `extract_scales.py` sends each paper plus its existing dataset list, so dataset IDs stay stable. It is resumable: papers whose datasets all have `scales` are skipped. In `scales`, `domain` is a per-dataset Earth-system component (more reliable than the keyword `DOMAINS` in summarize.py) and `scales` is a multi-label list that tags ClimSim/SPCAM-type data as `MMF_superparameterized`. Most values are `estimated_from_paper` (see `basis`).
- The process ellipses in `plot_scales.py` (`PROCESSES`) were traced by eye from the LEAP multi-scale slide (atmosphere/ocean only).
- `plot_authors.py` merges author names on first initial + surname (`author_key`), so two people who share both are merged. Papers with more than `MAX_AUTHORS` (30) authors add no co-author links.
- The testbed tables (`testbed_datasets.csv`, `testbed_families.csv`) group dataset names into families via the hand-written `FAMILIES` regex list in summarize.py (first match wins; unmatched names stay as their own row).
- Pain points are categorized by the keyword rules in `PAIN_POINTS` (summarize.py), multi-label. About 19% fall to "Other".
- `FAMILIES` is shared by the testbed tables/figure and top_datasets. After editing it, rerun summarize.py, plot_testbed.py and plot_top_datasets.py.
- `plot_scales_families.py` pools families per panel: named families with fewer than `MIN_FAMILY` datasets, and unmatched datasets, go to type/scale pools, and pools under `MIN_POOL` go to "Other (misc.)". Markers are nudged apart (`spread`), so they can sit off their ellipse centres.
- Venv setup: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`. `data/text/` and `.venv/` are gitignored. Pushing anything to GitHub, or sending papers to an API, needs the user's confirmation (global rule).

## Tools available

- `pdftotext` (poppler) and `python3` are on PATH via the `IceSciML` conda env (`/opt/anaconda3/envs/IceSciML`). PyMuPDF (`fitz`) is not installed.
- macOS `textutil -convert txt -stdout <file.docx>` reads the year index docs.
