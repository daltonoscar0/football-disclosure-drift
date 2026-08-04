"""Stage 3: rule-based extraction of four line items per filing.

Approach ported from Ticker: tiered regex candidate-spotting over the P&L and notes
sections, then unit and sign normalisation. No parsing of PDF table geometry — the
line-level text is enough once the numeric conventions are handled:

  units         UK accounts state amounts in £'000 or £m at the column head. The
                multiplier is detected from the section text, falling back to the
                whole document.
  negatives     "(1,234)" is -1234. So is a leading minus or en-dash.
  note refs     "Turnover 2 468,712 442,364" — the lone "2" is a note reference, not
                a figure. Small comma-less integers are dropped when larger figures
                follow on the same row.
  restatements  Filings print current year then prior year (sometimes labelled
                "restated"). We always take the first figure, i.e. the current year.

Every value carries the exact source row it came from so it can be hand-checked.
Output: data/extracted/line_items.csv and data/extracted/VALIDATION.md
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

from .util import ROOT, has_parsed_filings, jload

PARSED = ROOT / "data" / "parsed"
EXTRACTED = ROOT / "data" / "extracted"
LINE_ITEMS_CSV = EXTRACTED / "line_items.csv"
VALIDATION_MD = EXTRACTED / "VALIDATION.md"

ITEMS = ("revenue", "wages", "player_amortisation", "profit_on_disposal")

# Tier 1 patterns are unambiguous; tier 2 are acceptable fallbacks; a tier-2 hit
# drops the confidence one notch. Patterns match at the start of a row's label.
PATTERNS: dict[str, list[tuple[int, re.Pattern]]] = {
    "revenue": [
        (1, re.compile(r"^\s*(?:group\s+|total\s+)?turnover\b(?!\s+by\b)", re.I)),
        (1, re.compile(r"^\s*(?:group\s+|total\s+)?revenue\b(?!\s+recognition)", re.I)),
        (2, re.compile(r"^\s*turnover\s+and\s+(?:group\s+)?operating", re.I)),
    ],
    "wages": [
        (1, re.compile(r"^\s*wages\s+and\s+salaries\b", re.I)),
        (2, re.compile(r"^\s*(?:total\s+)?staff\s+costs\b", re.I)),
        (2, re.compile(r"^\s*(?:total\s+)?employee\s+(?:costs|benefit\s+expense)\b", re.I)),
    ],
    "player_amortisation": [
        (
            1,
            re.compile(
                r"^\s*amortisation\s+(?:charge\s+)?(?:of|on)\s+"
                r"(?:players?[’'`]?s?\s+registrations?|player\s+registrations?)",
                re.I,
            ),
        ),
        (
            1,
            re.compile(
                r"^\s*(?:players?[’'`]?s?\s+registrations?|player\s+registrations?)"
                r"\s+amortisation",
                re.I,
            ),
        ),
        (2, re.compile(r"^\s*amortisation\s+of\s+intangible\s+(?:fixed\s+)?assets\b", re.I)),
        (2, re.compile(r"^\s*amortisation\b(?!\s+(?:policy|method|is\s+))", re.I)),
    ],
    "profit_on_disposal": [
        (
            1,
            re.compile(
                r"^\s*(?:net\s+)?(?:profit|gain)\s+on\s+(?:the\s+)?disposals?\s+of\s+"
                r"(?:players?[’'`]?s?\s+registrations?|player\s+registrations?)",
                re.I,
            ),
        ),
        (
            1,
            re.compile(
                r"^\s*(?:net\s+)?(?:profit|gain)\s+on\s+(?:the\s+)?disposals?\s+of\s+"
                r"(?:intangible|tangible|fixed)\s+assets\b",
                re.I,
            ),
        ),
        (
            1,
            re.compile(
                r"^\s*(?:net\s+)?(?:profit|gain)\s+on\s+(?:the\s+)?disposals?\s+of\s+"
                r"(?:a\s+)?(?:subsidiar(?:y|ies)|business(?:es)?|"
                r"fellow\s+group\s+(?:compan(?:y|ies)|undertakings?))",
                re.I,
            ),
        ),
        (2, re.compile(r"^\s*(?:net\s+)?(?:profit|gain)\s+on\s+(?:the\s+)?disposals?\b", re.I)),
        (2, re.compile(r"^\s*profits?\s+(?:arising\s+)?on\s+player\s+(?:sales|trading)\b", re.I)),
    ],
}

# Where to look, best section first.
SEARCH_ORDER: dict[str, tuple[str, ...]] = {
    "revenue": ("profit_and_loss", "notes", "strategic_report"),
    "wages": ("notes", "profit_and_loss"),
    "player_amortisation": ("notes", "profit_and_loss"),
    "profit_on_disposal": ("profit_and_loss", "notes"),
}

# Items that are economically costs. Filings print these bracketed (negative) in the
# P&L and unbracketed (positive) in the notes; we normalise to positive magnitudes
# and let the item name carry the sign convention.
COST_ITEMS = {"wages", "player_amortisation"}

UNIT_PATTERNS = [
    (1_000_000, re.compile(r"£\s*[’'`]?\s*m\b|£\s*million|in\s+millions", re.I)),
    (1_000, re.compile(r"£\s*[’'`]?\s*0{3}\b|in\s+thousands|£\s*[’'`]000", re.I)),
]

NUMBER = re.compile(r"\(?-?\d{1,3}(?:,\d{3})+(?:\.\d+)?\)?|\(?-?\d+(?:\.\d+)?\)?")


def detect_unit(section_text: str, doc_text: str) -> tuple[int, str]:
    """Return (multiplier, evidence). Section evidence beats document evidence."""
    for scope, label in ((section_text, "section"), (doc_text, "document")):
        counts = []
        for multiplier, pattern in UNIT_PATTERNS:
            hits = len(pattern.findall(scope))
            if hits:
                counts.append((hits, multiplier))
        if counts:
            counts.sort(reverse=True)
            multiplier = counts[0][1]
            return multiplier, f"{label}: £'000" if multiplier == 1_000 else f"{label}: £m"
    return 1_000, "default: £'000 (no unit marker found)"


def parse_number(raw: str) -> float | None:
    text = raw.strip()
    negative = text.startswith("(") and text.endswith(")")
    text = text.strip("()").replace(",", "").replace("−", "-").replace("–", "-")
    if text.startswith("-"):
        negative = True
        text = text[1:]
    if not text or not re.fullmatch(r"\d+(?:\.\d+)?", text):
        return None
    value = float(text)
    return -value if negative else value


def row_figures(line: str, label_end: int) -> list[tuple[float, str]]:
    """Numeric candidates to the right of the row label, in column order."""
    out = []
    for match in NUMBER.finditer(line, label_end):
        value = parse_number(match.group())
        if value is not None:
            out.append((value, match.group()))
    return out


def pick_current_year(figures: list[tuple[float, str]], multiplier: int) -> tuple[float, str] | None:
    """First real figure on the row. Note references are dropped first."""
    if not figures:
        return None
    substantial = [
        f
        for f in figures
        if "," in f[1] or "." in f[1] or abs(f[0]) >= 100
    ]
    # A leading small comma-less integer alongside larger figures is a note ref.
    if substantial and len(substantial) < len(figures):
        figures = substantial
    elif multiplier == 1_000_000 and figures:
        # In £m, genuine values are small; only drop a bare leading integer if a
        # decimal figure follows it.
        decimals = [f for f in figures if "." in f[1]]
        if decimals and "." not in figures[0][1] and abs(figures[0][0]) < 100:
            figures = decimals
    return figures[0]


def find_item(item: str, sections: dict[str, str], doc_text: str) -> dict:
    """Best candidate row for one line item."""
    best: dict | None = None
    for section_name in SEARCH_ORDER[item]:
        text = sections.get(section_name, "")
        if not text.strip():
            continue
        multiplier, unit_evidence = detect_unit(text, doc_text)
        lines = text.splitlines()
        for idx, line in enumerate(lines):
            for tier, pattern in PATTERNS[item]:
                match = pattern.match(line)
                if not match:
                    continue
                figures = row_figures(line, match.end())
                snippet = line.strip()
                if not figures and idx + 1 < len(lines):
                    # Wrapped row: label on one line, figures on the next.
                    figures = row_figures(lines[idx + 1], 0)
                    if figures:
                        snippet = f"{line.strip()} / {lines[idx + 1].strip()}"
                picked = pick_current_year(figures, multiplier)
                if picked is None:
                    continue
                value, raw = picked
                candidate = {
                    "item": item,
                    "value_gbp": value * multiplier,
                    "raw_figure": raw,
                    "multiplier": multiplier,
                    "unit_evidence": unit_evidence,
                    "source_section": section_name,
                    "source_snippet": re.sub(r"\s+", " ", snippet)[:220],
                    "tier": tier,
                    "n_figures_on_row": len(figures),
                }
                if best is None or _rank(candidate) < _rank(best):
                    best = candidate
                break  # first matching pattern wins for this line
        if best is not None and best["tier"] == 1:
            break  # a tier-1 hit in a preferred section is good enough

    if best is None:
        return {
            "item": item,
            "value_gbp": "",
            "source_section": "",
            "source_snippet": "",
            "confidence": "none",
            "note": "no matching row found",
        }

    value = best["value_gbp"]
    if best["item"] in COST_ITEMS:
        value = abs(value)
    confidence = "high" if best["tier"] == 1 else "medium"
    if best["unit_evidence"].startswith("default"):
        confidence = "low"
    elif best["unit_evidence"].startswith("document") and confidence == "high":
        confidence = "medium"
    if best["n_figures_on_row"] < 2:
        # Real P&L rows carry a comparative. A lone figure may be a mis-slice.
        confidence = "low" if confidence != "high" else "medium"

    return {
        "item": best["item"],
        "value_gbp": int(round(value)),
        "source_section": best["source_section"],
        "source_snippet": best["source_snippet"],
        "confidence": confidence,
        "note": f"{best['unit_evidence']}; matched tier {best['tier']}; "
        f"took figure {best['raw_figure']!r} of {best['n_figures_on_row']} on row",
    }


def _rank(candidate: dict) -> tuple:
    """Lower is better: prefer tier 1, then rows with a comparative column."""
    return (candidate["tier"], -min(candidate["n_figures_on_row"], 3))


def run() -> int:
    if not has_parsed_filings(PARSED):
        print("error: nothing parsed yet — run `make parse` first.", file=sys.stderr)
        return 1

    rows: list[dict] = []
    for club_dir in sorted(p for p in PARSED.iterdir() if p.is_dir()):
        for path in sorted(club_dir.glob("*.json")):
            parsed = jload(path)
            sections = parsed["sections"]
            doc_text = "\n".join(sections[k] for k in sorted(sections))
            for item in ITEMS:
                found = find_item(item, sections, doc_text)
                rows.append({"club": parsed["club"], "year": parsed["year"], **found})

    EXTRACTED.mkdir(parents=True, exist_ok=True)
    fields = [
        "club",
        "year",
        "item",
        "value_gbp",
        "source_section",
        "source_snippet",
        "confidence",
        "note",
    ]
    with LINE_ITEMS_CSV.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    write_validation(rows)

    found = sum(1 for r in rows if r["value_gbp"] != "")
    by_conf = {c: sum(1 for r in rows if r["confidence"] == c) for c in
               ("high", "medium", "low", "none")}
    print(f"extracted {found}/{len(rows)} values  {by_conf}")
    print(f"wrote {LINE_ITEMS_CSV.relative_to(ROOT)} and {VALIDATION_MD.relative_to(ROOT)}")
    return 0


def _fmt(value) -> str:
    if value == "":
        return "—"
    return f"£{value:,.0f}"


def write_validation(rows: list[dict]) -> None:
    lines = [
        "# Line-item validation",
        "",
        "Every extracted value with the exact filing row it came from. Fill in the",
        "`verified?` column with `y` or `n`; where the value is wrong put the correct",
        "figure in `corrected_value` **in pounds** (not thousands).",
        "",
        "`confidence` is the extractor's own assessment: `high` = unambiguous label",
        "matched in the expected section with an explicit unit marker; `medium` = a",
        "fallback label or a document-level unit inference; `low` = unit assumed or",
        "the row had no comparative column; `none` = nothing matched.",
        "",
    ]
    clubs = sorted({r["club"] for r in rows})
    for club in clubs:
        lines.append(f"## {club}")
        lines.append("")
        lines.append(
            "| year | item | value | conf | section | source row | verified? | corrected_value |"
        )
        lines.append("|---|---|---|---|---|---|---|---|")
        for year in sorted({r["year"] for r in rows if r["club"] == club}):
            for item in ITEMS:
                row = next(
                    (r for r in rows if r["club"] == club and r["year"] == year and r["item"] == item),
                    None,
                )
                if row is None:
                    continue
                snippet = row["source_snippet"].replace("|", "\\|") or "—"
                lines.append(
                    f"| {year} | {item} | {_fmt(row['value_gbp'])} | {row['confidence']} "
                    f"| {row['source_section'] or '—'} | `{snippet}` |  |  |"
                )
        lines.append("")
    VALIDATION_MD.write_text("\n".join(lines) + "\n")


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
