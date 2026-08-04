# Ledger

Year-over-year disclosure-language drift in English football club annual accounts.

A Lazy Prices-style novelty score computed over the strategic report sections of
Companies House filings for five Premier League clubs, alongside rule-based
extraction of four financial line items per filing.

Results summary is filled in at the end of the project — see `FINDINGS.md`.

## Setup

```
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
export COMPANIES_HOUSE_API_KEY=...
```

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
make parse         # PDF -> sectioned JSON in data/parsed/
make check-parse   # per-filing page counts, sections, char counts
make extract       # four line items per filing -> data/extracted/
make score         # YoY surprisal -> data/scores/
make report        # tables and ranking for FINDINGS.md
make test          # smoke tests
```

`data/raw/` is cached and gitignored. Once populated, every stage after
`ingest` runs fully offline.
