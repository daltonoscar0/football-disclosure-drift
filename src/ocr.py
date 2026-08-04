"""Stage 2a: OCR scanned filings to text.

Every filing Companies House serves for these five clubs is an image-only scan —
one image per page, zero embedded characters — so there is no text layer for
pdfplumber to read. This stage renders each page and runs Tesseract over it.

  rasteriser  pypdfium2 at 200 DPI. Character yield is identical to 300 DPI on
              these scans and it renders faster. pypdfium2 also opens two filings
              whose xref tables pdfminer rejects outright.
  engine      the `tesseract` CLI, invoked directly rather than through a wrapper
              package, with --psm 3 (automatic page segmentation). psm 3 keeps a
              P&L row and its figures on one output line — verified byte-identical
              to psm 6 on Arsenal's six-column statement — and it is the only mode
              that reads Everton's two-column designed annual report correctly.
              Under psm 6 that layout is read line-across, interleaving the two
              columns into nonsense and hiding the section headings entirely.

Output is cached per filing at data/ocr/<club>/<year>.json, so this expensive stage
runs once and every later run is offline and instant. Tesseract is deterministic for
a given image, so repeated runs are byte-identical.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pypdfium2 as pdfium

from .util import ROOT, jdump, jload

RAW = ROOT / "data" / "raw"
OCR = ROOT / "data" / "ocr"
MANIFEST_PATH = RAW / "manifest.json"

DPI = 200
PSM = 3


def ocr_page(args: tuple[str, int]) -> tuple[int, str]:
    """Render and OCR a single page. Module-level so it is picklable for the pool."""
    pdf_path, index = args
    pdf = pdfium.PdfDocument(pdf_path)
    try:
        image = pdf[index].render(scale=DPI / 72).to_pil()
    finally:
        pdf.close()
    with tempfile.TemporaryDirectory() as tmp:
        png = os.path.join(tmp, "page.png")
        image.save(png)
        # OMP_THREAD_LIMIT=1 stops each Tesseract process spawning its own thread
        # pool; without it the workers oversubscribe the CPU and the batch is slower.
        env = dict(os.environ, OMP_THREAD_LIMIT="1")
        result = subprocess.run(
            ["tesseract", png, "stdout", "--psm", str(PSM)],
            capture_output=True,
            text=True,
            env=env,
        )
    if result.returncode != 0:
        return index, ""
    return index, result.stdout


def page_count(pdf_path: Path) -> int:
    pdf = pdfium.PdfDocument(str(pdf_path))
    try:
        return len(pdf)
    finally:
        pdf.close()


def ocr_filing(pdf_path: Path, workers: int) -> dict:
    n_pages = page_count(pdf_path)
    jobs = [(str(pdf_path), i) for i in range(n_pages)]
    pages: list[str] = [""] * n_pages
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for index, text in pool.map(ocr_page, jobs):
            pages[index] = text
    return {
        "pages": pages,
        "n_pages": n_pages,
        "dpi": DPI,
        "psm": PSM,
        "engine": tesseract_version(),
    }


def tesseract_version() -> str:
    try:
        out = subprocess.run(
            ["tesseract", "--version"], capture_output=True, text=True
        ).stdout
        return out.splitlines()[0].strip()
    except FileNotFoundError:
        return "unknown"


def run(force: bool = False, workers: int | None = None) -> int:
    if not MANIFEST_PATH.exists():
        print(f"error: {MANIFEST_PATH} not found — run `make ingest` first.", file=sys.stderr)
        return 1
    if tesseract_version() == "unknown":
        print(
            "error: the `tesseract` binary was not found. Install it with "
            "`brew install tesseract`.",
            file=sys.stderr,
        )
        return 1

    workers = workers or max(1, (os.cpu_count() or 4) - 2)
    manifest = jload(MANIFEST_PATH)
    for record in sorted(manifest["filings"], key=lambda r: (r["club"], r["year"])):
        club, year = record["club"], record["year"]
        pdf_path = ROOT / record["path"]
        out_path = OCR / club / f"{year}.json"
        if out_path.exists() and not force:
            print(f"{club} {year}: cached")
            continue
        if not pdf_path.exists():
            print(f"{club} {year}: missing PDF, skipping", file=sys.stderr)
            continue
        result = ocr_filing(pdf_path, workers)
        result["club"] = club
        result["year"] = year
        jdump(result, out_path)
        chars = sum(len(p) for p in result["pages"])
        print(f"{club} {year}: {result['n_pages']} pages, {chars:,} chars")
    return 0


def load_pages(club: str, year: str) -> list[str] | None:
    """OCR text for a filing, or None if it has not been OCR'd."""
    path = OCR / club / f"{year}.json"
    if not path.exists():
        return None
    return jload(path)["pages"]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--force", action="store_true", help="re-OCR even if cached")
    ap.add_argument("--workers", type=int, default=None)
    args = ap.parse_args(argv)
    return run(force=args.force, workers=args.workers)


if __name__ == "__main__":
    raise SystemExit(main())
