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
import re
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
# Fallback mode for statement pages whose labels and figures split into separate
# layout blocks under PSM. See looks_split().
PSM_TABLE = 6
# Bumped when the text-production method changes, so cached output is re-derived.
METHOD_VERSION = 2


def ocr_page(args: tuple[str, int] | tuple[str, int, int]) -> tuple[int, str]:
    """Render and OCR a single page. Module-level so it is picklable for the pool."""
    pdf_path, index = args[0], args[1]
    psm = args[2] if len(args) > 2 else PSM
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
            ["tesseract", png, "stdout", "--psm", str(psm)],
            capture_output=True,
            text=True,
            env=env,
        )
    if result.returncode != 0:
        return index, ""
    return index, result.stdout


WORD = re.compile(r"[A-Za-z]{3,}")
FIGURE = re.compile(r"\(?-?\d[\d,]*\)?")


def table_rows(text: str) -> int:
    """Lines carrying both a label and at least two figures — i.e. usable table rows."""
    n = 0
    for line in text.splitlines():
        if WORD.search(line) and len(FIGURE.findall(line)) >= 2:
            n += 1
    return n


def orphan_figure_lines(text: str) -> int:
    """Lines of figures with no label attached."""
    n = 0
    for line in text.splitlines():
        if not WORD.search(line) and len(FIGURE.findall(line)) >= 2:
            n += 1
    return n


def looks_split(text: str) -> bool:
    """Whether a page's labels and figures landed in separate layout blocks.

    Automatic segmentation sometimes reads a financial statement as two blocks — the
    label column, then the figure columns — and emits them one after the other:

        Turnover se 3                 512,467 - 512,467 481,278
        Cost of sales      becomes    (467,205) - (467,205) (386,794)

    which leaves no label+figure rows for the extractor to match. Chelsea's 2023 and
    2025 statements do this; Everton's two-column prose needs psm 3 and must not be
    disturbed. So the mode is chosen per page rather than per filing or per club.
    """
    return orphan_figure_lines(text) >= 3 and table_rows(text) < orphan_figure_lines(text)


def page_count(pdf_path: Path) -> int:
    pdf = pdfium.PdfDocument(str(pdf_path))
    try:
        return len(pdf)
    finally:
        pdf.close()


def repair_split_tables(pdf_path: Path, pages: list[str], workers: int) -> tuple[list[str], list[int]]:
    """Re-OCR pages whose labels and figures split apart, keeping the better result."""
    suspect = [i for i, text in enumerate(pages) if looks_split(text)]
    if not suspect:
        return pages, []
    jobs = [(str(pdf_path), i, PSM_TABLE) for i in suspect]
    repaired: list[int] = []
    pages = list(pages)
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for index, text in pool.map(ocr_page, jobs):
            if table_rows(text) > table_rows(pages[index]):
                pages[index] = text
                repaired.append(index)
    return pages, sorted(repaired)


def ocr_filing(pdf_path: Path, workers: int, pages: list[str] | None = None) -> dict:
    n_pages = page_count(pdf_path)
    if pages is None:
        jobs = [(str(pdf_path), i) for i in range(n_pages)]
        pages = [""] * n_pages
        with ProcessPoolExecutor(max_workers=workers) as pool:
            for index, text in pool.map(ocr_page, jobs):
                pages[index] = text
    pages, repaired = repair_split_tables(pdf_path, pages, workers)
    return {
        "pages": pages,
        "n_pages": n_pages,
        "dpi": DPI,
        "psm": PSM,
        "psm_table_fallback_pages": [i + 1 for i in repaired],
        "method_version": METHOD_VERSION,
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
        reuse: list[str] | None = None
        if out_path.exists() and not force:
            stale = cache_is_stale(out_path)
            if not stale:
                print(f"{club} {year}: cached")
                continue
            print(f"{club} {year}: re-OCR ({stale})")
            # A method-version bump alone does not invalidate the page text itself,
            # only the post-processing applied to it. Reuse the cached pages and
            # re-derive, rather than paying for a full pass over every page again.
            if stale.startswith("method"):
                cached = jload(out_path)
                if cached.get("dpi") == DPI and cached.get("psm") == PSM:
                    reuse = cached["pages"]
        if not pdf_path.exists():
            print(f"{club} {year}: missing PDF, skipping", file=sys.stderr)
            continue
        result = ocr_filing(pdf_path, workers, pages=reuse)
        result["club"] = club
        result["year"] = year
        jdump(result, out_path)
        chars = sum(len(p) for p in result["pages"])
        print(f"{club} {year}: {result['n_pages']} pages, {chars:,} chars")
    return 0


def cache_is_stale(path: Path) -> str | None:
    """Why a cached OCR result no longer matches current settings, or None.

    Presence on disk is not enough: text OCR'd under different settings is not
    interchangeable with text OCR'd under the current ones, and mixing the two
    across clubs would mean the study varied its text acquisition by club.
    """
    try:
        cached = jload(path)
    except (ValueError, OSError):
        return "unreadable cache"
    if cached.get("dpi") != DPI:
        return f"dpi {cached.get('dpi')} != {DPI}"
    if cached.get("psm") != PSM:
        return f"psm {cached.get('psm')} != {PSM}"
    if cached.get("method_version") != METHOD_VERSION:
        return f"method {cached.get('method_version')} != {METHOD_VERSION}"
    return None


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
