from src.parse import classify_heading, parse_filing, segment, text_quality


def test_extracts_every_page(parsed_filing):
    assert parsed_filing["pages"] == 6
    assert parsed_filing["total_words"] > 200


def test_finds_the_four_required_sections(parsed_filing):
    detected = parsed_filing["meta"]["sections_detected"]
    for name in ("strategic_report", "directors_report", "profit_and_loss", "notes"):
        assert name in detected, f"{name} not detected"
        assert parsed_filing["sections"][name].strip(), f"{name} is empty"


def test_sections_hold_their_own_content(parsed_filing):
    sections = parsed_filing["sections"]
    assert "principal risks" in sections["strategic_report"].lower()
    assert "Turnover 2 468,712" in sections["profit_and_loss"]
    assert "Wages and salaries" in sections["notes"]
    # Content must not bleed across the boundary.
    assert "Wages and salaries" not in sections["profit_and_loss"]


def test_contents_page_does_not_open_sections(parsed_filing):
    assert 2 in parsed_filing["meta"]["contents_pages_skipped"]
    # The real strategic report starts on page 3, not the contents page.
    first_hit = next(
        h for h in parsed_filing["meta"]["heading_hits"] if h["section"] == "strategic_report"
    )
    assert first_hit["page"] == 3


def test_heading_classification():
    assert classify_heading("Strategic Report") == "strategic_report"
    assert classify_heading("STRATEGIC REPORT") == "strategic_report"
    assert classify_heading("Strategic Report and Directors' Report") == "strategic_report"
    assert classify_heading("Report of the Directors") == "directors_report"
    assert classify_heading("Consolidated Profit and Loss Account") == "profit_and_loss"
    assert classify_heading("Consolidated Statement of Comprehensive Income") == "profit_and_loss"
    assert classify_heading("Notes to the Financial Statements") == "notes"
    assert classify_heading("Notes forming part of the accounts") == "notes"
    assert classify_heading("Independent Auditor's Report") == "auditors_report"


def test_heading_classification_rejects_body_text():
    assert classify_heading("The directors present their strategic report for the year") is None
    assert classify_heading("Strategic Report ......... 2") is None
    assert classify_heading("") is None


def test_repeated_running_header_does_not_fragment_a_section():
    pages = [
        ["Strategic Report", "First page of prose about the season."],
        ["Strategic Report", "Second page of prose about the season."],
    ]
    sections, meta = segment(["\n".join(p) for p in pages])
    assert meta["sections_detected"] == ["strategic_report"]
    assert "First page" in sections["strategic_report"]
    assert "Second page" in sections["strategic_report"]


def test_empty_text_layer_is_flagged():
    result = parse_filing_from_pages(["", "", ""])
    assert "empty_text_layer" in result["flags"]


def parse_filing_from_pages(pages):
    """parse_filing() without the PDF step, for flag tests."""
    from src.parse import MIN_STRATEGIC_CHARS, REQUIRED_SECTIONS

    sections, meta = segment(pages)
    per_page = [text_quality(t) for t in pages]
    total_words = sum(q["words"] for q in per_page)
    flags = []
    if total_words < 500:
        flags.append("empty_text_layer")
    for name in REQUIRED_SECTIONS:
        if name not in sections or not sections[name].strip():
            flags.append(f"missing_section:{name}")
    if len(sections.get("strategic_report", "")) < MIN_STRATEGIC_CHARS:
        flags.append("short_strategic_report")
    return {"flags": flags, "sections": sections, "meta": meta}


def test_missing_sections_are_flagged():
    result = parse_filing_from_pages(["Strategic Report", "Some prose here."])
    assert "missing_section:profit_and_loss" in result["flags"]
    assert "missing_section:notes" in result["flags"]


def test_text_quality_distinguishes_prose_from_garbage():
    prose = text_quality("The group and the company have set out the results of the year.")
    garbage = text_quality("qxz vbn plkj wrtq zzxc mnbv lkjh gfds")
    assert prose["common_word_ratio"] > garbage["common_word_ratio"]


def test_combined_income_statement_heading_is_matched():
    """Tottenham puts two statements under one heading."""
    assert (
        classify_heading("Consolidated income statement and statement of other comprehensive income")
        == "profit_and_loss"
    )


def test_running_headers_with_continued_suffix():
    assert classify_heading("NOTES TO THE FINANCIAL STATEMENTS (CONTINUED)") == "notes"
    assert classify_heading("INDEPENDENT AUDITOR'S REPORT ... (continued)") is None
    assert classify_heading("Notes to the Accounts") == "notes"


def test_ocr_rule_line_artefacts_do_not_block_headings():
    """OCR leaves stray | and : characters on header lines."""
    assert classify_heading("CONSOLIDATED PROFIT AND LOSS ACCOUNT :") == "profit_and_loss"
    assert classify_heading(". CONSOLIDATED PROFIT AND LOSS ACCOUNT") == "profit_and_loss"
    assert classify_heading("STRATEGIC REPORT |") == "strategic_report"
