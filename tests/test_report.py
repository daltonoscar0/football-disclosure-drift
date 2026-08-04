from src import report


def test_ranking_table_renders_in_order():
    rows = [
        {"club": "chelsea", "mean_cosine_novelty": "0.42", "max_cosine_novelty": "0.51",
         "mean_surprisal_bits": "9.10"},
        {"club": "arsenal", "mean_cosine_novelty": "0.21", "max_cosine_novelty": "0.25",
         "mean_surprisal_bits": "8.02"},
    ]
    table = report.ranking_table(rows)
    assert table[2].startswith("| 1 | chelsea")
    assert table[3].startswith("| 2 | arsenal")


def test_validated_line_items_take_precedence(tmp_path, monkeypatch):
    raw = tmp_path / "line_items.csv"
    validated = tmp_path / "line_items.validated.csv"
    raw.write_text("club,year,item,value_gbp\nchelsea,2023,revenue,1\n")
    monkeypatch.setattr(report, "RAW_ITEMS", raw)
    monkeypatch.setattr(report, "VALIDATED_ITEMS", validated)

    rows, provenance = report.line_items()
    assert provenance.startswith("extractor")
    assert rows[0]["value_gbp"] == "1"

    validated.write_text("club,year,item,value_gbp\nchelsea,2023,revenue,2\n")
    rows, provenance = report.line_items()
    assert provenance == "hand-validated"
    assert rows[0]["value_gbp"] == "2"


def test_corrected_value_overrides_the_extracted_value():
    rows = [
        {"club": "chelsea", "year": "2023", "item": "revenue",
         "value_gbp": "100000000", "corrected_value": "512300000"},
    ]
    table = report.items_table(rows)
    assert "512.3" in "\n".join(table)
    assert "100.0" not in "\n".join(table)


def test_chelsea_alignment_handles_the_earliest_year_without_a_pair():
    items = [
        {"club": "chelsea", "year": "2022", "item": "profit_on_disposal",
         "value_gbp": "10000000"},
        {"club": "chelsea", "year": "2023", "item": "profit_on_disposal",
         "value_gbp": "76400000"},
    ]
    drift = [{"club": "chelsea", "year_prev": "2022", "year": "2023",
              "cosine_novelty": "0.44", "surprisal_bits": "9.2"}]
    table = report.chelsea_alignment(drift, items)
    assert "no prior year" in table[2]
    assert "0.440" in table[3] and "76.4" in table[3]
