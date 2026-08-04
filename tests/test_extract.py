import pytest

from src.extract import detect_unit, find_item, parse_number, pick_current_year, row_figures


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("468,712", 468712.0),
        ("(441,208)", -441208.0),
        ("-1,234", -1234.0),
        ("82,500", 82500.0),
        ("12.4", 12.4),
        ("(12.4)", -12.4),
        ("-", None),
        ("", None),
    ],
)
def test_parse_number(raw, expected):
    assert parse_number(raw) == expected


def test_detect_unit_prefers_section_evidence():
    multiplier, evidence = detect_unit("Note 2024 2023\n£'000 £'000", "")
    assert multiplier == 1_000
    assert evidence.startswith("section")

    multiplier, _ = detect_unit("", "All amounts are stated in £m unless noted")
    assert multiplier == 1_000_000

    multiplier, evidence = detect_unit("", "")
    assert multiplier == 1_000 and evidence.startswith("default")


def test_note_reference_is_not_mistaken_for_a_figure():
    line = "Turnover 2 468,712 442,364"
    figures = row_figures(line, len("Turnover"))
    assert [f[0] for f in figures] == [2.0, 468712.0, 442364.0]
    assert pick_current_year(figures, 1_000)[0] == 468712.0


def test_current_year_column_wins_over_restated_prior_year():
    line = "Turnover 468,712 442,364 (restated)"
    figures = row_figures(line, len("Turnover"))
    assert pick_current_year(figures, 1_000)[0] == 468712.0


def test_millions_unit_keeps_decimal_figures():
    figures = row_figures("Turnover 3 468.7 442.4", len("Turnover"))
    assert pick_current_year(figures, 1_000_000)[0] == 468.7


def test_extracts_four_items_from_the_fixture(parsed_filing):
    sections = parsed_filing["sections"]
    doc = "\n".join(sections[k] for k in sorted(sections))

    revenue = find_item("revenue", sections, doc)
    assert revenue["value_gbp"] == 468_712_000
    assert revenue["confidence"] == "high"
    assert "Turnover" in revenue["source_snippet"]

    wages = find_item("wages", sections, doc)
    assert wages["value_gbp"] == 219_304_000
    assert wages["source_section"] == "notes"

    amort = find_item("player_amortisation", sections, doc)
    # Reported bracketed in the P&L; normalised to a positive magnitude.
    assert amort["value_gbp"] == 118_940_000

    disposal = find_item("profit_on_disposal", sections, doc)
    assert disposal["value_gbp"] == 76_441_000
    assert disposal["source_section"] == "profit_and_loss"


def test_missing_item_reports_no_match():
    result = find_item("revenue", {"notes": "Nothing relevant here at all."}, "")
    assert result["value_gbp"] == ""
    assert result["confidence"] == "none"
