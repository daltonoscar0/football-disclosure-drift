# Ledger

Year-over-year disclosure-language drift in English football club annual accounts.

A Lazy Prices-style novelty score computed over the strategic report sections of
Companies House filings for five Premier League clubs, alongside rule-based
extraction of four financial line items per filing.

## Headline result

Chelsea ranks **first of five** on mean year-over-year disclosure drift (cosine
novelty 0.290 vs a 0.206 floor), and is the only club in the sample booking material
intra-group asset disposals — £76.5m of hotels and car park sold to a fellow
subsidiary in FY2023, and £198.7m for the women's team in FY2024.

Within Chelsea, though, the year-by-year alignment does not hold. Cosine novelty is
*higher* in the year disposals fell to nil than in the year of the £198.7m sale;
surprisal points the other way. With two year-pairs per club, no timing claim
survives. Full write-up, including why the disagreement is not resolved in the
hypothesis's favour, is in `FINDINGS.md`.

## Setup

```
brew install tesseract          # required: every filing is a scan
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
export COMPANIES_HOUSE_API_KEY=...
```

Tesseract is a hard prerequisite, not an optional extra. Companies House serves
these filings as image-only PDFs with no text layer, so OCR is the only route to
the text this project measures.

### Getting an API key

1. Register at <https://developer.company-information.service.gov.uk/> and sign in.
2. **Manage applications → Add an application**, environment **Live**.
3. Inside the application, **Create new key** with key type **REST**. The streaming
   and document-only key types will not work for the filing-history calls.
4. Export the key in your shell. It is read from the environment only and is never
   written to disk by any stage of this pipeline.

The key is needed for `make ingest` alone. Once `data/raw/` is populated every
later stage runs offline, and `ingest` re-run is a no-op for anything already
cached.

## Run

```
make pipeline
```

Individual stages:

```
make ingest        # resolve entities, download filings to data/raw/
make ocr           # scanned pages -> text in data/ocr/ (slow, cached)
make parse         # PDF -> sectioned JSON in data/parsed/
make check-parse   # per-filing page counts, sections, char counts
make extract       # four line items per filing -> data/extracted/
make score         # YoY surprisal -> data/scores/
make report        # tables and ranking for FINDINGS.md
make test          # smoke tests
```

`data/raw/` and `data/ocr/` are cached and gitignored. Once populated the whole
pipeline runs offline in about 3 seconds and needs no API key — `ingest` detects a
complete cache and skips.

The expensive stage is `ocr`: every filing Companies House serves for these clubs is
an image-only scan with no text layer, so ~770 pages go through Tesseract. That is
paid once and cached.

## Checking the numbers

`data/extracted/VALIDATION.md` lists all 60 extracted values with the exact filing
row each came from, plus two independent checks: each value against the comparative
the *following* year's filing prints for the same line, and against the club's own
median. `make report` warns if it is asked to build tables from values that have not
been hand-validated.
