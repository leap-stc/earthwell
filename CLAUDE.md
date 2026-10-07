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

## Tools available

- `pdftotext` (poppler) and `python3` are on PATH via the `IceSciML` conda env (`/opt/anaconda3/envs/IceSciML`). PyMuPDF (`fitz`) is not installed.
- macOS `textutil -convert txt -stdout <file.docx>` reads the year index docs.
