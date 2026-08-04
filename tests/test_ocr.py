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


def test_cache_is_stale_when_settings_change(tmp_path):
    """A cached result OCR'd under different settings must not be reused: mixing
    settings across clubs would vary text acquisition by club."""
    from src.util import jdump

    path = tmp_path / "2024.json"
    current = {
        "pages": [],
        "dpi": ocr.DPI,
        "psm": ocr.PSM,
        "method_version": ocr.METHOD_VERSION,
    }
    jdump(current, path)
    assert ocr.cache_is_stale(path) is None

    jdump({**current, "psm": ocr.PSM + 3}, path)
    assert "psm" in ocr.cache_is_stale(path)

    jdump({**current, "dpi": 72}, path)
    assert "dpi" in ocr.cache_is_stale(path)

    jdump({**current, "method_version": ocr.METHOD_VERSION - 1}, path)
    assert "method" in ocr.cache_is_stale(path)


def test_unreadable_cache_is_stale(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{not json")
    assert ocr.cache_is_stale(path) == "unreadable cache"
