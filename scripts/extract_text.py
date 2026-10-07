"""Walk the corpus, pdftotext every PDF, write data/text/<sha>.txt and data/inventory.csv.

Usage: python scripts/extract_text.py
"""
import csv
import hashlib
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "Kara_s hackathon project - Publications and conferences"
TEXT = ROOT / "data" / "text"
INVENTORY = ROOT / "data" / "inventory.csv"


def norm_title(name):
    # "Foo_ Bar(1).pdf" -> "foo bar"; used to spot the same paper filed twice
    name = re.sub(r"\.pdf$|\._$|\(\d\)", "", name.strip(), flags=re.I)
    return re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()


def pdf_pages(path):
    out = subprocess.run(["pdfinfo", path], capture_output=True, text=True).stdout
    m = re.search(r"^Pages:\s+(\d+)", out, re.M)
    return int(m.group(1)) if m else 0


def main():
    TEXT.mkdir(parents=True, exist_ok=True)
    rows, first = [], {}  # sha or normalized title -> first file seen with it
    for path in sorted(CORPUS.glob("Year */*")):
        with open(path, "rb") as f:
            head = f.read(5)
        if head != b"%PDF-":  # docx index, .DS_Store, etc.; some PDFs lack the extension
            continue
        sha = hashlib.sha1(path.read_bytes()).hexdigest()[:12]
        out = TEXT / f"{sha}.txt"
        if not out.exists():
            subprocess.run(["pdftotext", "-q", "-layout", path, out], check=False)
        n_chars = len(out.read_text(errors="ignore")) if out.exists() else 0
        title = norm_title(path.name)
        rows.append({
            "year": path.parent.name.split()[-1],
            "filename": path.name,
            "sha": sha,
            "pages": pdf_pages(path),
            "n_chars": n_chars,
            # ponytail: filename heuristic; the docx index is the real source for publication type
            "is_abstract": "abstract" in path.name.lower(),
            "dup_of": first.get(sha) or first.get(title, ""),
            "needs_ocr": n_chars < 500,
        })
        first.setdefault(sha, f"{path.parent.name}/{path.name}")
        first.setdefault(title, f"{path.parent.name}/{path.name}")
    with open(INVENTORY, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} PDFs, {sum(not r['dup_of'] for r in rows)} unique, "
          f"{sum(r['needs_ocr'] for r in rows)} need OCR, "
          f"{sum(r['is_abstract'] for r in rows)} abstracts -> {INVENTORY}")


if __name__ == "__main__":
    main()
