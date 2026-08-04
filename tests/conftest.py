"""Test fixtures.

The smoke tests run against a synthetic filing rather than a real Companies House
PDF: real filings are gitignored (they live in data/raw/) and shipping one in the
repo would make the test suite depend on a download. The fixture is built with a
minimal hand-rolled PDF writer so no extra dependency is needed to produce it.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _escape(text: str) -> str:
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def make_pdf(pages: list[list[str]]) -> bytes:
    """Build a valid single-font PDF from a list of pages, each a list of lines."""
    objects: list[bytes] = []

    def add(body: bytes) -> int:
        objects.append(body)
        return len(objects)  # 1-based object number

    font_num = None
    content_nums = []
    for lines in pages:
        stream_lines = ["BT", "/F1 10 Tf", "50 800 Td", "13 TL"]
        for line in lines:
            stream_lines.append(f"({_escape(line)}) Tj")
            stream_lines.append("T*")
        stream_lines.append("ET")
        stream = "\n".join(stream_lines).encode("latin-1", "replace")
        content_nums.append(
            add(b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream))
        )
    font_num = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    # The page objects come next, then the page tree; pre-compute its number so the
    # /Parent references can be written before it exists.
    pages_num = len(objects) + len(pages) + 1
    page_nums = []
    for content_num in content_nums:
        page_nums.append(
            add(
                b"<< /Type /Page /Parent %d 0 R /MediaBox [0 0 595 842] "
                b"/Contents %d 0 R /Resources << /Font << /F1 %d 0 R >> >> >>"
                % (pages_num, content_num, font_num)
            )
        )
    actual_pages_num = add(
        b"<< /Type /Pages /Kids [%s] /Count %d >>"
        % (b" ".join(b"%d 0 R" % n for n in page_nums), len(page_nums))
    )
    assert actual_pages_num == pages_num, "page-tree object number mismatch"
    catalog_num = add(b"<< /Type /Catalog /Pages %d 0 R >>" % pages_num)

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + body + b"\nendobj\n"

    xref_at = len(out)
    out += b"xref\n0 %d\n" % (len(objects) + 1)
    out += b"0000000000 65535 f \n"
    for offset in offsets[1:]:
        out += b"%010d 00000 n \n" % offset
    out += b"trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        catalog_num,
        xref_at,
    )
    return bytes(out)


FILING_PAGES: list[list[str]] = [
    [
        "SAMPLE FOOTBALL CLUB HOLDINGS LIMITED",
        "Annual Report and Financial Statements",
        "For the year ended 30 June 2024",
    ],
    [
        "Contents",
        "Strategic Report 2",
        "Directors' Report 6",
        "Independent Auditor's Report 9",
        "Consolidated Profit and Loss Account 12",
        "Notes to the Financial Statements 16",
    ],
    [
        "Strategic Report",
        "The directors present their strategic report for the year ended 30 June 2024.",
        "The group delivered turnover growth driven by broadcast and commercial income,",
        "and the board continues to invest in the stadium and the academy. Wages",
        "remained the largest single cost and the directors monitor the wages to",
        "turnover ratio closely throughout the season. The group completed the disposal",
        "of two hotel properties to a fellow group undertaking during the year. The",
        "profit arising on that transaction is presented within operating profit and is",
        "described further in the notes to the financial statements. Player trading",
        "continued to contribute materially to the result for the year, and the",
        "directors expect amortisation of players registrations to remain elevated as a",
        "consequence of recent squad investment. Principal risks and uncertainties are",
        "set out below and include competition for playing talent, regulatory change in",
        "respect of profitability and sustainability rules, and reliance on qualification",
        "for European competition in future seasons.",
    ],
    [
        "Directors' Report",
        "The directors present their report and the audited financial statements for the",
        "year ended 30 June 2024. The directors who served during the year are listed",
        "on page 1. The group's policy on payment of creditors is to agree terms.",
    ],
    [
        "Consolidated Profit and Loss Account",
        "For the year ended 30 June 2024",
        "Note 2024 2023",
        "£'000 £'000",
        "Turnover 2 468,712 442,364",
        "Operating expenses (441,208) (409,552)",
        "Amortisation of players' registrations (118,940) (101,223)",
        "Profit on disposal of players' registrations 3 76,441 52,118",
        "Profit on disposal of fixed assets 4 82,500 -",
        "Operating profit 67,505 33,707",
    ],
    [
        "Notes to the Financial Statements",
        "For the year ended 30 June 2024",
        "2 Turnover",
        "Turnover 468,712 442,364",
        "5 Staff costs",
        "Wages and salaries 219,304 204,881",
        "Social security costs 26,115 24,002",
        "Total staff costs 245,419 228,883",
    ],
]


@pytest.fixture(scope="session")
def filing_pdf(tmp_path_factory) -> Path:
    path = tmp_path_factory.mktemp("fixtures") / "sample-2024.pdf"
    path.write_bytes(make_pdf(FILING_PAGES))
    return path


@pytest.fixture(scope="session")
def parsed_filing(filing_pdf):
    from src.parse import parse_filing

    return parse_filing(filing_pdf)
