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
                "restated"). We take the current-year column, never the comparative.
  analysis      Some filings split each year across sub-columns ("excluding player
  columns       trading | player trading | Total"), so a row can carry six figures
                and the current-year total is the third. The total column is found
                arithmetically — the first figure that the figures before it sum to.

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

# Rows are labelled "Profit on disposal of ...", "Gain on disposal of ...", and
# — where the line can swing either way — "(Loss)/profit on disposal of ..." or
# "Profit/(loss) on disposal of ...". All four forms occur in these filings.
# A "Loss on disposal of ..." row discloses the same line item with the opposite
# sign; treating it as no-match reported a disclosed nil as missing data.
_PROFIT_ON_DISPOSAL = (
    r"^\s*(?:\(loss\)\s*/\s*)?(?:net\s+)?(?:profit|gain|surplus|loss(?:es)?)"
    r"(?:\s*/\s*\(?(?:loss|profit)\)?)?\s+on\s+(?:the\s+)?disposals?"
)
# Matches only a row whose label leads with "loss" outright (not "(loss)/profit"),
# whose figures are therefore printed as positive magnitudes of a loss.
_BARE_LOSS = re.compile(r"^\s*(?:net\s+)?loss(?:es)?\s+on\s", re.I)
_PROFIT_PREFIX = _PROFIT_ON_DISPOSAL + r"\s+of\s+"
# Everything the generic fallback must NOT treat as an intra-group asset sale.
# West Ham labels the routine line "Profit on disposal of players" and Tottenham
# calls it "... of intangible fixed assets"; both are player trading.
_NOT_PLAYER_TRADING = (
    r"(?!\s+of\s+(?:the\s+)?(?:players?[’'`]?s?\b|intangible\s+(?:fixed\s+)?assets\b))"
)

# Tier 1 patterns are unambiguous; tier 2 are acceptable fallbacks; a tier-2 hit
# drops the confidence one notch. Patterns match at the start of a row's label.
PATTERNS: dict[str, list[tuple[int, re.Pattern]]] = {
    "revenue": [
        (1, re.compile(r"^\s*(?:group\s+|total\s+)?turnover\b(?!\s+by\b)", re.I)),
        (1, re.compile(r"^\s*(?:group\s+|total\s+)?revenue\b(?!\s+recognition)", re.I)),
        (2, re.compile(r"^\s*turnover\s+and\s+(?:group\s+)?operating", re.I)),
    ],
    # Basis: total staff costs, not "wages and salaries". Tottenham discloses no
    # wages-and-salaries line at all, so staff costs is the only basis available for
    # every club in every year — and a wages column that is not like-for-like across
    # clubs is worse than one that is consistently broader. Includes social security
    # and pension costs; runs ~12-15% above pure wages.
    "wages": [
        (1, re.compile(r"^\s*(?:total\s+)?staff\s+costs\b(?!\s*:)", re.I)),
        (1, re.compile(r"^\s*(?:total\s+)?employee\s+(?:costs|benefit\s+expense)\b", re.I)),
        (2, re.compile(r"^\s*wages\s+and\s+salaries\b", re.I)),
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
        # "Amortisation charged in the year" inside the intangibles note. Deliberately
        # NOT a bare "^amortisation" — that matched the note's own heading
        # ("Amortisation and impairment") and read the movement table's "At 1 July
        # 2023" beneath it as a £2,023,000 figure.
        (2, re.compile(r"^\s*amortisation\s+(?:charged?|expense)\b", re.I)),
    ],
    # Non-player disposals only — see PLAYERS_DISPOSAL below for why.
    "profit_on_disposal": [
        (
            1,
            re.compile(
                # NOT "intangible assets": at a football club the intangible fixed
                # assets *are* the player registrations, so Tottenham's "profit on
                # disposal of intangible fixed assets" is routine player trading and
                # belongs with PLAYERS_DISPOSAL, not here.
                _PROFIT_PREFIX + r"(?:tangible\s+)?fixed\s+assets?"
                r"(?:\s+investments?)?\b",
                re.I,
            ),
        ),
        (
            1,
            re.compile(
                _PROFIT_PREFIX + r"(?:a\s+)?(?:subsidiar(?:y|ies)|business(?:es)?|"
                r"investments?|propert(?:y|ies)|"
                r"fellow\s+group\s+(?:compan(?:y|ies)|undertakings?))",
                re.I,
            ),
        ),
        # Generic fallback, but never the player-registrations row.
        (
            2,
            re.compile(
                _PROFIT_ON_DISPOSAL + _NOT_PLAYER_TRADING,
                re.I,
            ),
        ),
    ],
}

# Profit on disposal of *player registrations* is a routine, every-club line and is
# a different economic event from selling a hotel to a fellow group company. Tracking
# it as "profit_on_disposal" would bury the intra-group signal this project exists to
# test, so it is extracted separately and reported in VALIDATION.md as context rather
# than as one of the four line items.
PLAYERS_DISPOSAL = [
    (
        1,
        re.compile(_PROFIT_PREFIX + r"players?[’'`]?s?(?:\s+registrations?)?\b", re.I),
    ),
    (1, re.compile(_PROFIT_PREFIX + r"intangible\s+(?:fixed\s+)?assets\b", re.I)),
    (2, re.compile(r"^\s*profits?\s+(?:arising\s+)?on\s+player\s+(?:sales|trading)\b", re.I)),
]

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

# OCR mangles the £'000 column head in predictable ways: the apostrophe is read as
# a 7 ("£7000"), dropped ("£000"), or the pound sign is read as E or €. All of these
# appear in the actual filings, so the unit patterns have to absorb them.
UNIT_PATTERNS = [
    (1_000_000, re.compile(r"[£€E]\s*[’'`]?\s*m\b|£\s*million|in\s+millions", re.I)),
    (
        1_000,
        re.compile(r"[£€E]\s*[’'`7]?\s*0{3}(?![\d,])|in\s+thousands", re.I),
    ),
]

# A standalone dash is a nil column, not an absent one. Dropping it would collapse
# the column positions: "Profit on disposal of fixed asset investments 16 - - - 198,749"
# has a nil current year and £198,749k as the *comparative*, so ignoring the dashes
# would report last year's figure as this year's.
NIL_TOKENS = frozenset({"-", "–", "—"})
NUMBER = re.compile(
    r"\(?-?\d{1,3}(?:,\d{3})+(?:\.\d+)?\)?"
    r"|\(?-?\d+(?:\.\d+)?\)?"
    r"|(?<![\w-])[-–—](?![\w-])"
)


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
    if text in NIL_TOKENS:
        return 0.0
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


TOTAL_TOLERANCE = 1.0


def find_total_column(figures: list[tuple[float, str]]) -> int | None:
    """Index of a total column, if the row is split into analysis columns.

    Several filings analyse the P&L across columns rather than presenting one figure
    per year. Arsenal's runs "excluding player trading | player trading | Total" for
    each of two years, so a turnover row carries six figures and the current-year
    total is the *third*, not the first:

        Group turnover 3   615,206   1,374   616,580   465,228   1,457   466,685

    Taking figures[0] would silently report the football-only column. We detect the
    total by arithmetic: the smallest k such that the figures before it sum to it.
    On an ordinary two-column row (current year, comparative) no such k exists and
    the first figure is used, which is the correct behaviour there.
    """
    for k in range(2, len(figures)):
        prefix = sum(f[0] for f in figures[:k])
        if abs(prefix - figures[k][0]) <= TOTAL_TOLERANCE and abs(figures[k][0]) > 0:
            return k
    return None


def clean_figures(
    figures: list[tuple[float, str]], multiplier: int
) -> list[tuple[float, str]]:
    """Drop note references, leaving only genuine figure columns."""
    substantial = [
        f
        for f in figures
        if f[1].strip() in NIL_TOKENS or "," in f[1] or "." in f[1] or abs(f[0]) >= 100
    ]
    # A leading small comma-less integer alongside larger figures is a note ref.
    if substantial and len(substantial) < len(figures):
        return substantial
    if multiplier == 1_000_000 and figures:
        # In £m, genuine values are small; only drop a bare leading integer if a
        # decimal figure follows it.
        decimals = [f for f in figures if "." in f[1]]
        if decimals and "." not in figures[0][1] and abs(figures[0][0]) < 100:
            return decimals
    return figures


def pick_comparative(figures: list[tuple[float, str]], multiplier: int) -> float | None:
    """The prior-year figure on the row.

    In an analysis-column layout the comparative total sits symmetrically: if the
    current-year total is at index k, the prior-year total is at 2k+1. Otherwise it
    is simply the second column.
    """
    figures = clean_figures(figures, multiplier)
    if len(figures) < 2:
        return None
    total_at = find_total_column(figures)
    index = 2 * total_at + 1 if total_at is not None else 1
    return figures[index][0] if index < len(figures) else None


def pick_current_year(
    figures: list[tuple[float, str]], multiplier: int
) -> tuple[float, str] | None:
    """The current-year figure on a row. Note references are dropped first."""
    if not figures:
        return None
    figures = clean_figures(figures, multiplier)
    if not figures:
        return None
    total_at = find_total_column(figures)
    if total_at is not None:
        return figures[total_at]
    return figures[0]


NOTE_REF = re.compile(r"[(\[]?\s*(?:see\s+)?notes?\s+\d{1,2}\s*[)\]]?", re.I)
LEADING_JUNK = re.compile(r"^[\s\-–—•*·:;|>»_]+")


def strip_note_refs(line: str) -> str:
    """Remove "(note 11)" style cross-references.

    Left in, the reference number is read as the current-year figure:
    "Amortisation of intangible fixed assets (note 11" became £11,000.
    """
    return NOTE_REF.sub(" ", line)


def logical_rows(text: str) -> list[str]:
    """Join labels that wrap across lines back into one row.

    A wrapped label must be rejoined *before* pattern matching, not after, or a
    negative lookahead cannot see the words it needs to exclude:

        Profit on disposal of
        player registrations   10,732   ...

    matched the generic disposal pattern, because "player registrations" was on the
    next line. Only lines beginning with a lowercase word are treated as
    continuations — that distinguishes a genuine wrap from the next labelled row,
    which is what stopped "Amortisation and impairment" from swallowing the
    "At 1 July 2023" movement row beneath it and reporting £2,023,000.
    """
    lines = [ln.rstrip() for ln in text.splitlines()]
    rows: list[str] = []
    i = 0
    while i < len(lines):
        row = lines[i]
        while (
            i + 1 < len(lines)
            and not row_figures(strip_note_refs(row), 0)
            and re.match(r"\s*[a-z]", lines[i + 1])
        ):
            row = f"{row.strip()} {lines[i + 1].strip()}"
            i += 1
        rows.append(row)
        i += 1
    return rows


WAGES_LABEL = re.compile(r"^\s*wages\s+and\s+salaries\b", re.I)
MAX_STAFF_COST_COMPONENTS = 6


def derive_staff_costs(sections: dict[str, str], doc_text: str) -> dict | None:
    """Total staff costs, summed from the components in the employees note.

    Chelsea and West Ham do not print a *labelled* staff-costs total — they list
    wages, social security and pension costs and then an unlabelled total row. In
    Chelsea's 2025 filing the note is a split block, so even the component labels
    are separated from their figures. Both are handled the same way: from the
    "Wages and salaries" label onwards, take the current-year figures in order and
    find the first run that sums to the figure following it.

        352,355 + 49,831 + 1,776 = 403,962   <- Chelsea 2023
        312,812 + 44,041 + 2,412 = 359,265   <- Chelsea 2025, split block
        152,926 + 22,638 +   329 = 175,893   <- West Ham 2025
        204,648 + 28,569 + 1,549 = 234,766   <- Arsenal 2023, agrees with its
                                                own labelled "Staff costs" row

    The arithmetic is the verification: a run that does not sum to the next figure
    is not a component breakdown, so nothing is returned.
    """
    for section_name in ("notes", "profit_and_loss"):
        text = sections.get(section_name, "")
        if not text.strip():
            continue
        multiplier, unit_evidence = detect_unit(text, doc_text)
        rows = logical_rows(text)
        for start, row in enumerate(rows):
            if not WAGES_LABEL.match(strip_note_refs(LEADING_JUNK.sub("", row))):
                continue
            figures: list[float] = []
            for candidate in rows[start : start + 40]:
                picked = pick_current_year(
                    row_figures(strip_note_refs(candidate), 0), multiplier
                )
                # A split-block note interleaves the column heading's year into the
                # figure run ("2025" above "312,812"), which would break the sum.
                if picked is not None and not _is_year(picked[1]):
                    figures.append(picked[0])
                if len(figures) > MAX_STAFF_COST_COMPONENTS + 2:
                    break
            # The run of components need not begin at the label — in a split block
            # other figures can precede it — so try each starting point.
            for first in range(max(1, len(figures) - 2)):
                for k in range(first + 2, len(figures)):
                    total = figures[k]
                    if not total or abs(sum(figures[first:k]) - total) > TOTAL_TOLERANCE:
                        continue
                    if figures[first] == 0:  # a nil column ahead of the components
                        continue
                    return {
                        "item": "wages",
                        "value_gbp": int(round(total * multiplier)),
                        "comparative_gbp": "",
                        "source_section": section_name,
                        "source_snippet": (
                            "derived total staff costs: "
                            + " + ".join(f"{f:,.0f}" for f in figures[first:k])
                            + f" = {total:,.0f}"
                        ),
                        "confidence": "medium",
                        "note": f"{unit_evidence}; summed from the components in the "
                        "employees note (no labelled total is printed)",
                    }
    return None


def _is_year(raw: str) -> bool:
    text = raw.strip()
    return bool(re.fullmatch(r"\d{4}", text)) and 1990 <= int(text) <= 2100


def find_item(
    item: str,
    sections: dict[str, str],
    doc_text: str,
    patterns: list[tuple[int, re.Pattern]] | None = None,
    search_order: tuple[str, ...] | None = None,
) -> dict:
    """Best candidate row for one line item."""
    patterns = patterns if patterns is not None else PATTERNS[item]
    search_order = search_order or SEARCH_ORDER.get(item, ("profit_and_loss", "notes"))
    best: dict | None = None
    for section_name in search_order:
        text = sections.get(section_name, "")
        if not text.strip():
            continue
        multiplier, unit_evidence = detect_unit(text, doc_text)
        for row in logical_rows(text):
            # OCR prefixes some rows with a bullet or rule fragment ("-Wages and
            # salaries"), which would defeat the ^-anchored label patterns.
            row = strip_note_refs(LEADING_JUNK.sub("", row))
            for tier, pattern in patterns:
                match = pattern.match(row)
                if not match:
                    continue
                figures = row_figures(row, match.end())
                snippet = row.strip()
                picked = pick_current_year(figures, multiplier)
                if picked is None:
                    continue
                value, raw = picked
                columns = clean_figures(figures, multiplier)
                candidate = {
                    "item": item,
                    "value_gbp": value * multiplier,
                    "raw_figure": raw,
                    "multiplier": multiplier,
                    "unit_evidence": unit_evidence,
                    "source_section": section_name,
                    "source_snippet": re.sub(r"\s+", " ", snippet)[:220],
                    "tier": tier,
                    "comparative_gbp": (
                        c * multiplier
                        if (c := pick_comparative(figures, multiplier)) is not None
                        else None
                    ),
                    "n_figures_on_row": len(columns),
                    "total_column": find_total_column(columns) is not None,
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
    elif _BARE_LOSS.match(best["source_snippet"]) and value > 0:
        value = -value
    confidence = "high" if best["tier"] == 1 else "medium"
    if best["unit_evidence"].startswith("default"):
        confidence = "low"
    elif best["unit_evidence"].startswith("document") and confidence == "high":
        confidence = "medium"
    if best["n_figures_on_row"] < 2:
        # Real P&L rows carry a comparative. A lone figure may be a mis-slice.
        confidence = "low" if confidence != "high" else "medium"
    if best["n_figures_on_row"] > 2:
        # An analysis-column layout. The total-column arithmetic is reliable when it
        # fires, but this is exactly the shape most worth a human glance.
        confidence = "medium" if confidence == "high" else confidence

    column_note = (
        f"; row has {best['n_figures_on_row']} figures, took the "
        + ("computed total column" if best["total_column"] else "first column")
        if best["n_figures_on_row"] > 2
        else ""
    )
    return {
        "item": best["item"],
        "value_gbp": int(round(value)),
        "comparative_gbp": (
            int(round(best["comparative_gbp"]))
            if best.get("comparative_gbp") is not None
            else ""
        ),
        "source_section": best["source_section"],
        "source_snippet": best["source_snippet"],
        "confidence": confidence,
        "note": f"{best['unit_evidence']}; matched tier {best['tier']}; "
        f"took figure {best['raw_figure']!r} of {best['n_figures_on_row']} on row"
        + column_note,
    }


def _rank(candidate: dict) -> tuple:
    """Lower is better: prefer tier 1, then rows with a comparative column."""
    return (candidate["tier"], -min(candidate["n_figures_on_row"], 3))


def run() -> int:
    if not has_parsed_filings(PARSED):
        print("error: nothing parsed yet — run `make parse` first.", file=sys.stderr)
        return 1

    rows: list[dict] = []
    context: list[dict] = []
    for club_dir in sorted(p for p in PARSED.iterdir() if p.is_dir()):
        for path in sorted(club_dir.glob("*.json")):
            parsed = jload(path)
            sections = parsed["sections"]
            doc_text = "\n".join(sections[k] for k in sorted(sections))
            for item in ITEMS:
                found = find_item(item, sections, doc_text)
                if item == "wages" and _needs_derived_total(found):
                    # Keep the basis identical across clubs: a labelled "Staff costs"
                    # total where one exists, otherwise the same total summed from
                    # its components. Falling back to "Wages and salaries" would
                    # silently narrow the basis for some clubs and not others.
                    derived = derive_staff_costs(sections, doc_text)
                    if derived is not None:
                        found = derived
                rows.append({"club": parsed["club"], "year": parsed["year"], **found})
            # Context only, not one of the four tracked items.
            players = find_item(
                "profit_on_disposal_players", sections, doc_text, patterns=PLAYERS_DISPOSAL
            )
            context.append({"club": parsed["club"], "year": parsed["year"], **players})

    cross_check(rows)
    series_check(rows)
    EXTRACTED.mkdir(parents=True, exist_ok=True)
    fields = [
        "club",
        "year",
        "item",
        "value_gbp",
        "comparative_gbp",
        "source_section",
        "source_snippet",
        "confidence",
        "cross_check",
        "restated_next_year",
        "note",
    ]
    with LINE_ITEMS_CSV.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    write_validation(rows, context)

    found = sum(1 for r in rows if r["value_gbp"] != "")
    by_conf = {c: sum(1 for r in rows if r["confidence"] == c) for c in
               ("high", "medium", "low", "none")}
    print(f"extracted {found}/{len(rows)} values  {by_conf}")
    print(f"wrote {LINE_ITEMS_CSV.relative_to(ROOT)} and {VALIDATION_MD.relative_to(ROOT)}")
    return 0


CROSS_CHECK_TOLERANCE = 0.01


def cross_check(rows: list[dict]) -> None:
    """Verify each value against the next year's filing, in place.

    Every filing restates the prior year as a comparative. That restated figure is
    the same audited number, printed in a different document — so it is an
    independent check on a value we extracted from elsewhere. Where they disagree
    the usual cause is OCR damage to one of the two: Tottenham's FY2023 revenue read
    as "$49,633" where FY2024's comparative column plainly reads 549,633.

    Disagreement is reported, not resolved. Either side can be the damaged one — the
    comparative column is OCR'd from a scan too — and a disagreement can also mean
    the two filings were read off different labels ("Wages and salaries" one year,
    "Staff costs" the next), which is a real basis change rather than an error.
    Nothing is overwritten; adjudicating is the validator's job.
    """
    by_key = {(r["club"], r["year"], r["item"]): r for r in rows}
    for row in rows:
        row.setdefault("cross_check", "")
        row.setdefault("restated_next_year", "")
    for (club, year, item), row in sorted(by_key.items()):
        later = by_key.get((club, str(int(year) + 1), item))
        if later is None or row["value_gbp"] == "" or later.get("comparative_gbp") in ("", None):
            continue
        value = float(row["value_gbp"])
        restated = float(later["comparative_gbp"])
        scale = max(abs(value), abs(restated), 1.0)
        if abs(value - restated) / scale <= CROSS_CHECK_TOLERANCE:
            row["cross_check"] = f"agrees with {year}+1 comparative"
            continue
        row["cross_check"] = (
            f"MISMATCH: {int(year) + 1} filing restates this as {restated:,.0f}"
        )
        row["restated_next_year"] = int(round(restated))
        row["confidence"] = "low"


def _needs_derived_total(found: dict) -> bool:
    """Whether a wages hit is something other than a total staff-costs figure."""
    if found.get("value_gbp") == "":
        return True
    return bool(WAGES_LABEL.match(found.get("source_snippet", "")))


# Revenue, wages and amortisation move by tens of percent between years, not by
# an order of magnitude. Disposals legitimately swing from nil to hundreds of
# millions, so they are exempt.
SERIES_ITEMS = ("revenue", "wages", "player_amortisation")
SERIES_LOW, SERIES_HIGH = 0.25, 4.0


def series_check(rows: list[dict]) -> None:
    """Flag values wildly out of line with the same club's own series, in place.

    The cross-year check only fires when the following year's comparative could be
    read. Where it could not, an OCR-damaged figure passes silently: Everton's FY2023
    revenue came out as £7.2m against £187m and £197m either side, because the scan
    rendered 172,155 as "7215S". An order-of-magnitude departure from a club's own
    median is not a business event, it is a reading error.
    """
    from statistics import median

    for club in sorted({r["club"] for r in rows}):
        for item in SERIES_ITEMS:
            series = [
                r for r in rows
                if r["club"] == club and r["item"] == item and r["value_gbp"] != ""
            ]
            values = [abs(float(r["value_gbp"])) for r in series]
            if len(values) < 2:
                continue
            mid = median(values)
            if not mid:
                continue
            for row in series:
                ratio = abs(float(row["value_gbp"])) / mid
                if ratio < SERIES_LOW or ratio > SERIES_HIGH:
                    row["confidence"] = "low"
                    note = f"OUTLIER: {ratio:.2f}x this club's median {item} ({mid:,.0f})"
                    row["cross_check"] = (
                        f"{row['cross_check']}; {note}" if row["cross_check"] else note
                    )


def _fmt(value) -> str:
    if value == "":
        return "—"
    return f"£{value:,.0f}"


def write_validation(rows: list[dict], context: list[dict] | None = None) -> None:
    lines = [
        "# Line-item validation",
        "",
        "Every extracted value with the exact filing row it came from. Fill in the",
        "`verified?` column with `y` or `n`; where the value is wrong put the correct",
        "figure in `corrected_value` **in pounds** (not thousands).",
        "",
        "`cross-check vs next year` compares each value with the comparative column",
        "the *following* year's filing prints for the same line. `ok` means the two",
        "agree. A **MISMATCH** means they disagree — which may be OCR damage on either",
        "side, or a genuine change of basis (e.g. \"Wages and salaries\" one year and",
        "\"Staff costs\" the next). These are the rows to check first.",
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
            "| year | item | value | conf | cross-check vs next year | section | source row "
            "| verified? | corrected_value |"
        )
        lines.append("|---|---|---|---|---|---|---|---|---|")
        for year in sorted({r["year"] for r in rows if r["club"] == club}):
            for item in ITEMS:
                row = next(
                    (r for r in rows if r["club"] == club and r["year"] == year and r["item"] == item),
                    None,
                )
                if row is None:
                    continue
                snippet = row["source_snippet"].replace("|", "\\|") or "—"
                check = row.get("cross_check") or "—"
                if check.startswith("agrees"):
                    check = "ok"
                elif check.startswith("MISMATCH"):
                    check = f"**{check}**"
                lines.append(
                    f"| {year} | {item} | {_fmt(row['value_gbp'])} | {row['confidence']} "
                    f"| {check} | {row['source_section'] or '—'} | `{snippet}` |  |  |"
                )
        lines.append("")
        club_context = [c for c in (context or []) if c["club"] == club]
        if club_context:
            lines.append(
                "_Context — profit on disposal of **player registrations**. Not one of "
                "the four tracked items (see DECISIONS.md), shown so the tracked "
                "non-player disposal figure above can be checked against it._"
            )
            lines.append("")
            lines.append("| year | player disposal profit | source row |")
            lines.append("|---|---|---|")
            for c in sorted(club_context, key=lambda c: c["year"]):
                snippet = c["source_snippet"].replace("|", "\\|") or "—"
                lines.append(f"| {c['year']} | {_fmt(c['value_gbp'])} | `{snippet}` |")
            lines.append("")
    VALIDATION_MD.write_text("\n".join(lines) + "\n")


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
