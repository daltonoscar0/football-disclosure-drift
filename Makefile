PY := .venv/bin/python

.PHONY: pipeline ingest ocr parse check-parse extract score report test clean-derived

pipeline: ingest ocr parse extract score report

ingest:
	$(PY) -m src.ingest

# Every filing is an image-only scan, so text comes from OCR. Expensive but cached
# per filing under data/ocr/ — a second run is a no-op.
ocr:
	$(PY) -m src.ocr

parse:
	$(PY) -m src.parse

check-parse:
	$(PY) -m src.parse --check

extract:
	$(PY) -m src.extract

score:
	$(PY) -m src.score

report:
	$(PY) -m src.report

test:
	.venv/bin/pytest -q tests

# Removes everything derived. Leaves data/raw/ and data/ocr/ — the two expensive,
# cached stages — alone.
clean-derived:
	rm -rf data/parsed/* data/extracted/* data/scores/*
