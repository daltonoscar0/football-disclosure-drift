import shutil

import pytest

from src import ocr

needs_tesseract = pytest.mark.skipif(
    shutil.which("tesseract") is None, reason="tesseract not installed"
)


@needs_tesseract
def test_tesseract_is_available():
    assert ocr.tesseract_version().lower().startswith("tesseract")


@needs_tesseract
def test_ocr_round_trips_a_profit_and_loss_page(filing_pdf):
    """Rendering then OCR must preserve a P&L row as one line: label then figures.

    This is the property --psm 6 is chosen for, and the one the extractor depends
    on. Tesseract's default segmentation splits the columns apart instead.
    """
    index, text = ocr.ocr_page((str(filing_pdf), 4))
    assert index == 4
    row = next((ln for ln in text.splitlines() if "Turnover" in ln), None)
    assert row is not None, f"no Turnover row in OCR output:\n{text}"
    assert "468,712" in row
    assert "442,364" in row


@needs_tesseract
def test_page_count_matches_the_document(filing_pdf):
    assert ocr.page_count(filing_pdf) == 6


def test_load_pages_returns_none_when_not_ocred():
    assert ocr.load_pages("no-such-club", "1999") is None
