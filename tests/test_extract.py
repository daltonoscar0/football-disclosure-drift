import pytest

from src.extract import (
    PLAYERS_DISPOSAL,
    detect_unit,
    find_item,
    find_total_column,
    parse_number,
    pick_current_year,
    row_figures,
)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("468,712", 468712.0),
        ("(441,208)", -441208.0),
        ("-1,234", -1234.0),
        ("82,500", 82500.0),
        ("12.4", 12.4),
        ("(12.4)", -12.4),
        ("-", 0.0),   # nil column, not an absent one
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

    # The tracked item is the non-player disposal (fixed assets), not the routine
    # player-registrations row that sits directly above it in the fixture's P&L.
    disposal = find_item("profit_on_disposal", sections, doc)
    assert disposal["value_gbp"] == 82_500_000
    assert disposal["source_section"] == "profit_and_loss"
    assert "fixed assets" in disposal["source_snippet"].lower()

    players = find_item(
        "profit_on_disposal_players", sections, doc, patterns=PLAYERS_DISPOSAL
    )
    assert players["value_gbp"] == 76_441_000


def test_missing_item_reports_no_match():
    result = find_item("revenue", {"notes": "Nothing relevant here at all."}, "")
    assert result["value_gbp"] == ""
    assert result["confidence"] == "none"


# -- real filing layouts, transcribed from OCR output -----------------------

ARSENAL_PL_ROW = "Group turnover 3 615,206 1,374 616,580 465,228 1,457 466,685"
ARSENAL_DISPOSAL_ROW = "Profit on disposal of player registrations - 51,073 51,073 - 10,732 10,732"
ARSENAL_OPEX_ROW = "Operating expenses 4 (493,875) (171,099) (664,974) (364,778) (157,151) (521,929)"


def test_analysis_columns_resolve_to_the_total_not_the_first_column():
    """Arsenal splits each year across 'excluding player trading | player trading |
    Total'. The current-year total is the third figure, not the first."""
    figures = row_figures(ARSENAL_PL_ROW, len("Group turnover"))
    assert pick_current_year(figures, 1_000)[0] == 616_580.0


def test_total_column_detection_handles_bracketed_negatives():
    figures = row_figures(ARSENAL_OPEX_ROW, len("Operating expenses"))
    assert pick_current_year(figures, 1_000)[0] == -664_974.0


def test_dashes_do_not_break_column_alignment():
    figures = row_figures(ARSENAL_DISPOSAL_ROW, len("Profit on disposal of player registrations"))
    assert pick_current_year(figures, 1_000)[0] == 51_073.0


def test_two_column_rows_are_untouched_by_total_detection():
    """The common layout must keep taking the first (current-year) figure."""
    for label, row, expected in [
        ("Wages and salaries", "Wages and salaries _ 286,960 204,648", 286_960.0),
        ("Staff costs", "Staff costs (see note 6) 327,822 234,766", 327_822.0),
        ("Amortisation of player registrations",
         "Amortisation of player registrations . 171,099 139,060", 171_099.0),
    ]:
        figures = row_figures(row, len(label))
        assert pick_current_year(figures, 1_000)[0] == expected, row


def test_ocr_mangled_unit_markers_are_recognised():
    """OCR reads the £'000 column head as £7000, £000, or E'000."""
    for header in ["Note £7000 £7000 £7000", "Note £000 £000", "E'000 E'000", "£'000"]:
        multiplier, evidence = detect_unit(header, "")
        assert multiplier == 1_000, header
        assert evidence.startswith("section"), header


def test_real_money_amounts_are_not_read_as_unit_markers():
    multiplier, evidence = detect_unit("a grant of £7,000 was received", "")
    assert evidence.startswith("default")


def test_player_disposals_never_leak_into_the_tracked_disposal_item():
    """The generic fallback must not match the player-registrations row, or every
    club would report routine player trading as an intra-group asset sale."""
    sections = {
        "profit_and_loss": "Profit on disposal of player registrations 51,073 10,732"
    }
    assert find_item("profit_on_disposal", sections, "")["value_gbp"] == ""


def test_loss_slash_profit_labels_are_matched():
    sections = {
        "profit_and_loss": "(Loss)/profit on disposal of fixed assets (2,985) - (2,985) | 54"
    }
    assert find_item("profit_on_disposal", sections, "")["value_gbp"] == -2_985_000


def test_nil_current_year_is_not_replaced_by_the_comparative():
    """Chelsea 2025: the current year is nil and £198.7m is last year's figure."""
    sections = {
        "profit_and_loss": "Profit on disposal of fixed asset investments 16 - - - 198,749"
    }
    assert find_item("profit_on_disposal", sections, "")["value_gbp"] == 0


# -- cross-year comparative check ------------------------------------------


def test_cross_check_flags_a_disagreeing_restatement():
    from src.extract import cross_check

    rows = [
        {"club": "spurs", "year": "2023", "item": "revenue",
         "value_gbp": 49_633_000, "comparative_gbp": 443_415_000},
        {"club": "spurs", "year": "2024", "item": "revenue",
         "value_gbp": 517_763_000, "comparative_gbp": 549_633_000},
    ]
    cross_check(rows)
    assert rows[0]["cross_check"].startswith("MISMATCH")
    assert rows[0]["restated_next_year"] == 549_633_000
    assert rows[0]["confidence"] == "low"


def test_cross_check_passes_agreeing_years():
    from src.extract import cross_check

    rows = [
        {"club": "c", "year": "2023", "item": "wages",
         "value_gbp": 352_355_000, "comparative_gbp": 297_569_000},
        {"club": "c", "year": "2024", "item": "wages",
         "value_gbp": 294_629_000, "comparative_gbp": 352_355_000},
    ]
    cross_check(rows)
    assert rows[0]["cross_check"].startswith("agrees")
    assert rows[0]["restated_next_year"] == ""


def test_comparative_is_blank_when_the_row_is_ambiguous():
    """A mangled row must not produce a confident-looking comparative."""
    from src.extract import pick_comparative

    clean = row_figures("Group turnover 615,206 1,374 616,580 465,228 1,457 466,685", 0)
    assert pick_comparative(clean, 1_000) == 466_685.0

    truncated = row_figures("Turnover 186,902 - 186,902 172,155 172,155", 0)
    assert pick_comparative(truncated, 1_000) is None
