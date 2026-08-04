PY := .venv/bin/python

.PHONY: pipeline ingest parse check-parse extract score report test clean-derived

pipeline: ingest parse extract score report

ingest:
	$(PY) -m src.ingest

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

# Removes everything derived. Leaves data/raw/ (the expensive, cached part) alone.
clean-derived:
	rm -rf data/parsed/* data/extracted/* data/scores/*
