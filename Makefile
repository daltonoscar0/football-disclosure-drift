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

# Removes everything derived. Deliberately preserves three things: data/raw/ and
# data/ocr/ (expensive to rebuild) and line_items.validated.csv, which is
# hand-validation work and an input to the report, not an output of the pipeline.
clean-derived:
	rm -rf data/parsed/* data/scores/*
	find data/extracted -type f ! -name 'line_items.validated.csv' ! -name '.gitkeep' -delete
