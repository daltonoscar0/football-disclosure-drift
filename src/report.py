"""Stage 5: assemble the tables that go into FINDINGS.md.

Prefers hand-validated line items when they exist. `data/extracted/line_items.csv`
is the raw extractor output; if `data/extracted/line_items.validated.csv` is present
it wins, so the findings note is never built on unchecked numbers.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from .util import ROOT

EXTRACTED = ROOT / "data" / "extracted"
SCORES = ROOT / "data" / "scores"
RAW_ITEMS = EXTRACTED / "line_items.csv"
VALIDATED_ITEMS = EXTRACTED / "line_items.validated.csv"
DRIFT_CSV = SCORES / "drift.csv"
RANKING_CSV = SCORES / "ranking.csv"
OUT = SCORES / "report_tables.md"

ITEM_LABELS = {
    "revenue": "Revenue",
    "wages": "Wages",
    "player_amortisation": "Player amortisation",
    "profit_on_disposal": "Profit on disposals",
}


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="") as fh:
        return list(csv.DictReader(fh))


def line_items() -> tuple[list[dict], str]:
    if VALIDATED_ITEMS.exists():
        return read_csv(VALIDATED_ITEMS), "hand-validated"
    return read_csv(RAW_ITEMS), "extractor output (NOT hand-validated)"


def _money(value: str) -> str:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return "—"
    return f"{n / 1_000_000:,.1f}"


def drift_table(rows: list[dict]) -> list[str]:
    out = [
        "| club | pair | cosine novelty | Jaccard novelty | surprisal (bits) |",
        "|---|---|---:|---:|---:|",
    ]
    for r in rows:
        out.append(
            f"| {r['club']} | {r['year_prev']}→{r['year']} | "
            f"{float(r['cosine_novelty']):.3f} | {float(r['jaccard_novelty']):.3f} | "
            f"{float(r['surprisal_bits']):.2f} |"
        )
    return out


def ranking_table(rows: list[dict]) -> list[str]:
    out = [
        "| rank | club | mean cosine novelty | max cosine novelty | mean surprisal (bits) |",
        "|---:|---|---:|---:|---:|",
    ]
    for i, r in enumerate(rows, 1):
        out.append(
            f"| {i} | {r['club']} | {float(r['mean_cosine_novelty']):.3f} | "
            f"{float(r['max_cosine_novelty']):.3f} | {float(r['mean_surprisal_bits']):.2f} |"
        )
    return out


def items_table(rows: list[dict]) -> list[str]:
    clubs = sorted({r["club"] for r in rows})
    years = sorted({r["year"] for r in rows})
    out = ["| club | year | " + " | ".join(ITEM_LABELS[i] for i in ITEM_LABELS) + " |"]
    out.append("|---|---|" + "---:|" * len(ITEM_LABELS))
    for club in clubs:
        for year in years:
            cells = []
            present = False
            for item in ITEM_LABELS:
                match = next(
                    (
                        r
                        for r in rows
                        if r["club"] == club and r["year"] == year and r["item"] == item
                    ),
                    None,
                )
                if match:
                    present = True
                value = (match or {}).get("corrected_value") or (match or {}).get(
                    "value_gbp", ""
                )
                cells.append(_money(value))
            if present:
                out.append(f"| {club} | {year} | " + " | ".join(cells) + " |")
    out.append("")
    out.append("_All figures £m._")
    return out


def chelsea_alignment(drift: list[dict], items: list[dict]) -> list[str]:
    """Line up Chelsea's YoY drift against its profit-on-disposal figures."""
    out = [
        "| year | profit on disposals (£m) | cosine novelty vs prior year | surprisal (bits) |",
        "|---|---:|---:|---:|",
    ]
    years = sorted({r["year"] for r in items if r["club"] == "chelsea"})
    for year in years:
        disposal = next(
            (
                r
                for r in items
                if r["club"] == "chelsea"
                and r["year"] == year
                and r["item"] == "profit_on_disposal"
            ),
            None,
        )
        value = (disposal or {}).get("corrected_value") or (disposal or {}).get(
            "value_gbp", ""
        )
        pair = next(
            (r for r in drift if r["club"] == "chelsea" and r["year"] == year), None
        )
        cos = f"{float(pair['cosine_novelty']):.3f}" if pair else "— (no prior year)"
        sur = f"{float(pair['surprisal_bits']):.2f}" if pair else "—"
        out.append(f"| {year} | {_money(value)} | {cos} | {sur} |")
    return out


def run() -> int:
    drift = read_csv(DRIFT_CSV)
    ranking = read_csv(RANKING_CSV)
    items, provenance = line_items()

    if not drift:
        print("error: no drift scores — run `make score` first.", file=sys.stderr)
        return 1

    blocks: list[str] = ["# Report tables", ""]
    blocks.append(f"_Line items: {provenance}._")
    blocks += ["", "## Club ranking by disclosure drift", ""]
    blocks += ranking_table(ranking)
    blocks += ["", "## Year-over-year drift, all pairs", ""]
    blocks += drift_table(drift)
    if items:
        blocks += ["", "## Line items", ""]
        blocks += items_table(items)
        blocks += ["", "## Chelsea: disposals vs disclosure drift", ""]
        blocks += chelsea_alignment(drift, items)
    blocks.append("")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(blocks) + "\n")
    print("\n".join(blocks))
    print(f"\nwrote {OUT.relative_to(ROOT)}", file=sys.stderr)
    if provenance.startswith("extractor"):
        print(
            "warning: line items have not been hand-validated. Do not publish "
            "FINDINGS.md from these numbers.",
            file=sys.stderr,
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
