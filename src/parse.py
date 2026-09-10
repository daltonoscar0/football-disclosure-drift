"""Stage 2: PDF -> per-page text -> sectioned JSON.

UK statutory accounts follow a stable running order — strategic report, directors'
report, auditor's report, the primary statements, then notes — so sections can be
recovered by finding the headings that open each block and treating everything up
to the next heading as that section's body.

Practical complications this handles:

  * Running page headers repeat a heading on every page of a block. Segments with
    the same label are merged, so repeats are harmless.
  * Contents pages look like a dense run of headings. Pages with many heading hits
    and dot-leader/page-number lines are skipped for heading detection.
  * Some filings use a combined "Strategic Report and Directors' Report" heading.
    That block is assigned to the strategic report and flagged.
  * Image-only scans yield an empty or garbage text layer. Those are flagged in the
    output rather than silently producing junk sections.

Output: data/parsed/<club>/<year>.json
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pdfplumber

from . import ocr
from .util import ROOT, has_parsed_filings, jdump, jload

RAW = ROOT / "data" / "raw"
PARSED = ROOT / "data" / "parsed"
MANIFEST_PATH = RAW / "manifest.json"

MIN_STRATEGIC_CHARS = 2000

# Ordered: the first pattern to match a line wins, so combined and more specific
# headings must come before their components.
HEADING_PATTERNS: list[tuple[str, re.Pattern]] = [
    (
        "strategic_report",
        re.compile(
            r"^(?:the\s+)?strategic\s+report\s+and\s+(?:the\s+)?"
            r"(?:report\s+of\s+the\s+)?directors[’'`]?s?\s*(?:report)?$",
            re.I,
        ),
    ),
    ("strategic_report", re.compile(r"^(?:the\s+)?strategic\s+report$", re.I)),
    (
        "directors_report",
        re.compile(
            r"^(?:the\s+)?(?:report\s+of\s+the\s+directors|directors[’'`]?s?\s+report)"
            r"(?:\s+for\s+the\s+year.*)?$",
            re.I,
        ),
    ),
    (
        "auditors_report",
        re.compile(
            r"^(?:independent\s+)?auditors?[’'`]?s?\s+report.*$|"
            r"^report\s+of\s+the\s+(?:independent\s+)?auditors.*$",
            re.I,
        ),
    ),
    (
        "profit_and_loss",
        re.compile(
            r"^(?:consolidated\s+|group\s+|company\s+)?"
            r"(?:profit\s+and\s+loss\s+account|income\s+statement|"
            r"statement\s+of\s+(?:comprehensive\s+income|profit\s+or\s+loss)"
            r"(?:\s+and\s+other\s+comprehensive\s+income)?)"
            # Tottenham: "Consolidated income statement and statement of other
            # comprehensive income", the two statements share one heading.
            r"(?:\s+and\s+(?:the\s+)?statement\s+of\s+other\s+comprehensive\s+income)?"
            r"(?:\s+for\s+the\s+(?:year|period).*)?$",
            re.I,
        ),
    ),
    (
        "notes",
        re.compile(
            r"^notes\s+(?:to|forming\s+part\s+of)\s+the\s+"
            r"(?:consolidated\s+|group\s+)?(?:financial\s+statements|accounts)"
            r"(?:\s+for\s+the\s+(?:year|period).*)?$",
            re.I,
        ),
    ),
    (
        "balance_sheet",
        re.compile(
            r"^(?:consolidated\s+|group\s+|company\s+)?"
            r"(?:balance\s+sheet|statement\s+of\s+financial\s+position)"
            r"(?:\s+as\s+at.*)?$",
            re.I,
        ),
    ),
    (
        "cash_flow",
        re.compile(
            r"^(?:consolidated\s+|group\s+|company\s+)?"
            r"(?:statement\s+of\s+)?cash\s*flow(?:\s+statement|s?)"
            r"(?:\s+for\s+the\s+(?:year|period).*)?$",
            re.I,
        ),
    ),
    (
        "changes_in_equity",
        re.compile(
            r"^(?:consolidated\s+|group\s+|company\s+)?statement\s+of\s+changes\s+in\s+"
            r"(?:equity|shareholders[’'`]?\s*funds).*$",
            re.I,
        ),
    ),
    (
        "company_information",
        re.compile(
            r"^(?:company\s+information|officers\s+and\s+professional\s+advis(?:e|o)rs|"
            r"directors\s+and\s+advis(?:e|o)rs)$",
            re.I,
        ),
    ),
    ("contents", re.compile(r"^contents$", re.I)),
]

# The four sections the rest of the pipeline depends on.
REQUIRED_SECTIONS = ("strategic_report", "directors_report", "profit_and_loss", "notes")

DOT_LEADER = re.compile(r"\.{3,}|\s\.\s\.\s")
TRAILING_PAGE_NO = re.compile(r"\s\d{1,3}$")
CONTINUED = re.compile(r"[\s(\[]*\bcontinued\b[)\]\s]*$", re.I)
COMBINED_SR_DR = HEADING_PATTERNS[0][1]

COMMON_WORDS = frozenset(
    "the and of to in for a is on as at by with that from are was were be this"
    " group company year its has have".split()
)


def classify_heading(line: str) -> str | None:
    """Return the canonical section a line opens, or None if it is body text."""
    text = line.strip()
    if not (3 <= len(text) <= 90):
        return None
    if DOT_LEADER.search(text):
        return None
    # Strip leading numbering ("1.", "2 ") and trailing page numbers.
    text = re.sub(r"^\d{1,2}[.)]?\s+", "", text)
    text = TRAILING_PAGE_NO.sub("", text)
    # Running headers on continuation pages are suffixed "(CONTINUED)". OCR also
    # leaves stray rule-line artefacts ("|", ":") at the end of header lines.
    text = CONTINUED.sub("", text)
    # Strip stray edge characters generally rather than a fixed set: OCR leaves ';',
    # '|', ':', '.', '*' and similar on header lines, and a single unlisted character
    # ("GROUP PROFIT AND LOSS ACCOUNT ;") was enough to lose a whole statement.
    text = re.sub(r"^[^0-9A-Za-z(]+|[^0-9A-Za-z)]+$", "", text)
    if not text:
        return None
    for canonical, pattern in HEADING_PATTERNS:
        if pattern.match(text):
            return canonical
    return None


def text_quality(text: str) -> dict:
    """Cheap heuristics for whether a page's text layer is real prose."""
    words = re.findall(r"[A-Za-z]{1,}", text)
    n_words = len(words)
    if n_words == 0:
        return {"words": 0, "common_word_ratio": 0.0, "alpha_ratio": 0.0}
    common = sum(1 for w in words if w.lower() in COMMON_WORDS)
    alpha = sum(1 for ch in text if ch.isalnum() or ch.isspace())
    return {
        "words": n_words,
        "common_word_ratio": round(common / n_words, 4),
        "alpha_ratio": round(alpha / max(len(text), 1), 4),
    }


def extract_pages(pdf_path: Path, club: str | None = None, year: str | None = None):
    """Page text plus its provenance.

    Prefers cached OCR output when it exists, because every Companies House filing
    in this study is an image-only scan. Falls back to the PDF's own text layer for
    native-text filings (and for the test fixture). Returns (pages, source).
    """
    if club and year:
        ocr_pages = ocr.load_pages(club, year)
        if ocr_pages is not None:
            return [_strip_noise(p) for p in ocr_pages], "ocr"

    pages: list[str] = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                try:
                    text = page.extract_text(x_tolerance=1.5) or ""
                except Exception:  # pragma: no cover - malformed page
                    text = ""
                pages.append(text)
    except Exception:
        # Two filings have xref tables pdfminer rejects. Nothing to fall back to
        # here beyond an empty result; the OCR stage handles them via pypdfium2.
        return [], "unreadable"
    return pages, "text_layer"


# The scans are e-signed, so every page carries a DocuSign envelope banner. It is
# identical on all pages of a filing and would otherwise inflate similarity between
# consecutive years.
DOCUSIGN = re.compile(r"^\s*Docusign\s+Envelope\s+ID:.*$", re.I | re.M)


def _strip_noise(text: str) -> str:
    return DOCUSIGN.sub("", text)


def _heading_dense_pages(pages: list[str]) -> set[int]:
    """Pages that look like a table of contents: several headings, few words."""
    dense = set()
    for i, text in enumerate(pages):
        lines = [ln for ln in text.splitlines() if ln.strip()]
        hits = sum(1 for ln in lines if classify_heading(ln))
        if hits >= 4 and len(lines) < 40:
            dense.add(i)
        elif re.search(r"^\s*contents\s*$", text, re.I | re.M) and hits >= 3:
            dense.add(i)
    return dense


def segment(pages: list[str]) -> tuple[dict[str, str], dict]:
    """Split page text into canonical sections. Returns (sections, meta)."""
    skip = _heading_dense_pages(pages)
    current = "front_matter"
    blocks: dict[str, list[str]] = {}
    order: list[str] = []
    combined_sr_dr = False
    heading_hits: list[dict] = []

    for page_no, text in enumerate(pages):
        for line in text.splitlines():
            canonical = None if page_no in skip else classify_heading(line)
            if canonical == "contents":
                canonical = None
            if canonical:
                if canonical == "strategic_report" and COMBINED_SR_DR.match(
                    re.sub(r"^\d{1,2}[.)]?\s+", "", line.strip()).strip(" .:-–—")
                ):
                    combined_sr_dr = True
                if canonical != current:
                    heading_hits.append(
                        {"page": page_no + 1, "section": canonical, "line": line.strip()}
                    )
                    current = canonical
                    if canonical not in order:
                        order.append(canonical)
                continue
            blocks.setdefault(current, []).append(line)

    sections = {name: "\n".join(lines).strip() for name, lines in blocks.items()}
    meta = {
        "sections_detected": order,
        "combined_strategic_and_directors_report": combined_sr_dr,
        "heading_hits": heading_hits,
        "contents_pages_skipped": sorted(p + 1 for p in skip),
    }
    return sections, meta


def parse_filing(pdf_path: Path, club: str | None = None, year: str | None = None) -> dict:
    pages, source = extract_pages(pdf_path, club, year)
    sections, meta = segment(pages)

    per_page = [text_quality(t) for t in pages]
    total_words = sum(q["words"] for q in per_page)
    common_ratio = (
        sum(q["common_word_ratio"] * q["words"] for q in per_page) / total_words
        if total_words
        else 0.0
    )
    flags = []
    if total_words < 500:
        flags.append("empty_text_layer")
    elif common_ratio < 0.08:
        flags.append("suspect_text_layer")
    for name in REQUIRED_SECTIONS:
        if name not in sections or not sections[name].strip():
            flags.append(f"missing_section:{name}")
    if len(sections.get("strategic_report", "")) < MIN_STRATEGIC_CHARS:
        flags.append("short_strategic_report")

    return {
        "pages": len(pages),
        "text_source": source,
        "total_words": total_words,
        "common_word_ratio": round(common_ratio, 4),
        "flags": flags,
        "meta": meta,
        "sections": {name: sections.get(name, "") for name in sorted(sections)},
        "section_chars": {name: len(sections[name]) for name in sorted(sections)},
    }


def run(force: bool = False) -> list[dict]:
    if not MANIFEST_PATH.exists():
        print(
            f"error: {MANIFEST_PATH} not found — run `make ingest` first.",
            file=sys.stderr,
        )
        return []
    manifest = jload(MANIFEST_PATH)
    results = []
    for record in manifest["filings"]:
        club, year = record["club"], record["year"]
        pdf_path = ROOT / record["path"]
        out_path = PARSED / club / f"{year}.json"
        if not pdf_path.exists():
            print(f"{club} {year}: missing PDF, skipping", file=sys.stderr)
            continue
        if out_path.exists() and not force:
            results.append(jload(out_path))
            print(f"{club} {year}: already parsed")
            continue
        parsed = parse_filing(pdf_path, club, year)
        parsed["club"] = club
        parsed["year"] = year
        parsed["company_number"] = record.get("company_number")
        jdump(parsed, out_path)
        results.append(parsed)
        print(
            f"{club} {year}: {parsed['pages']} pages ({parsed['text_source']}), "
            f"{len(parsed['meta']['sections_detected'])} sections"
            + (f", flags={parsed['flags']}" if parsed["flags"] else "")
        )
    return results


def check() -> int:
    """`make check-parse`: per-filing page count, sections, and char counts."""
    if not has_parsed_filings(PARSED):
        print("error: nothing parsed yet — run `make parse` first.", file=sys.stderr)
        return 1
    problems = 0
    header = f"{'club':<11}{'year':<6}{'pp':>4}  {'strategic':>10}{'directors':>11}{'p&l':>9}{'notes':>10}  flags"
    print(header)
    print("-" * len(header))
    for club_dir in sorted(p for p in PARSED.iterdir() if p.is_dir()):
        for path in sorted(club_dir.glob("*.json")):
            d = jload(path)
            chars = d["section_chars"]
            row = (
                f"{d['club']:<11}{d['year']:<6}{d['pages']:>4}  "
                f"{chars.get('strategic_report', 0):>10,}"
                f"{chars.get('directors_report', 0):>11,}"
                f"{chars.get('profit_and_loss', 0):>9,}"
                f"{chars.get('notes', 0):>10,}  "
                f"{','.join(d['flags'])}"
            )
            print(row)
            if chars.get("strategic_report", 0) < MIN_STRATEGIC_CHARS:
                problems += 1
    print(
        f"\n{problems} filing(s) below the {MIN_STRATEGIC_CHARS:,}-char strategic "
        "report threshold."
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="report on already-parsed filings")
    ap.add_argument("--force", action="store_true", help="re-parse even if cached")
    args = ap.parse_args(argv)
    if args.check:
        return check()
    run(force=args.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
