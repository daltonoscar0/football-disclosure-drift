# Decisions

A running log of judgment calls made while building Ledger.

## Setup

**2026-08-04 — Python 3.12 rather than a system interpreter.**
The macOS system Python is 3.9.6, below the 3.11+ floor. `~/.local/bin/python3.12`
(uv-managed CPython 3.12.13) is used, with a project-local `.venv`.

**2026-08-04 — Dependencies.**
`requests` for the Companies House REST API, `pdfplumber` for PDF text extraction,
`pytest` for smoke tests. Scoring (TF-IDF cosine, Jaccard, KN-smoothed n-gram
surprisal) is implemented in pure stdlib rather than pulling in scikit-learn or
nltk — the maths is small and hand-rolling it keeps the dependency surface at three
packages and makes determinism easier to guarantee.

**2026-08-04 — pdfplumber over pymupdf.**
Companies House filings are a mix of native-text PDFs and image-only scans.
pdfplumber's word-level positional output makes it easier to detect table-like
P&L rows (columns of figures) than a plain text dump, which matters for milestone 2.
PyMuPDF's AGPL licensing is also a mild negative for a shareable repo.

## Entity resolution

_(filled in during milestone 1)_

## Parsing

_(filled in during milestone 1)_

## Extraction

_(filled in during milestone 2)_

## Scoring

_(filled in during milestone 3)_
