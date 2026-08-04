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

**2026-08-04 — Ranking rule for picking a club's filing entity.**
Search returns both operating companies and holding companies. Candidates are
ranked by (1) best accounts type in their recent filing history, with
`accounts-with-accounts-type-group` — consolidated accounts — ahead of `full`, then
(2) how many of the last six accounts filings are usable, then (3) recency, then
(4) company number as a deterministic tie-break. This favours the holding company
by construction, which is what the Chelsea case study needs: intra-group disposal
profits only appear in the consolidated P&L, and are eliminated or absent in a
single-entity operating company's accounts.

Supporters' trusts, foundations, and dissolved companies are filtered out by name
and status before any filing history is pulled, to keep request counts down.

**2026-08-04 — One filing per made-up date.**
Amended accounts for a period are filed under the same made-up date as the
original. Taking the three most recent filings naively would let two versions of
one year crowd out an earlier year, so filings are deduplicated by made-up date
(keeping the most recently filed version) before taking the top three.

**2026-08-04 — Filing year is the made-up date's year, not the filing date's.**
Accounts are filed 6–12 months after the period end. Labelling by filing date
would misalign clubs against each other and against the disposal events.

## Parsing

**2026-08-04 — Heading detection over sequential assignment, not page ranges.**
UK statutory accounts have a stable running order, so each detected heading opens a
section that runs until the next heading. Three failure modes are handled
explicitly:

- *Running page headers.* Many filings repeat "Strategic Report" as a header on
  every page of the block. Segments carrying the same label are merged, so repeats
  are harmless rather than fragmenting.
- *Contents pages.* A contents page is a dense run of heading-like lines and would
  otherwise open and immediately close every section. Pages with ≥4 heading matches
  and few lines are excluded from heading detection, as are lines with dot leaders.
- *Combined headings.* Some filings use "Strategic Report and Directors' Report" as
  one heading. That block is assigned to the strategic report and the filing is
  flagged `combined_strategic_and_directors_report`, since its strategic report
  section will then include directors' report content.

Headings we do not output (auditor's report, balance sheet, cash flow, changes in
equity) are still detected, because they are what terminates the sections we do
want.

**2026-08-04 — Text-layer quality is flagged, not silently accepted.**
Image-only scans yield empty or garbage text. Two heuristics: total words across
the filing (<500 ⇒ `empty_text_layer`), and the share of tokens that are common
English function words (<8% ⇒ `suspect_text_layer`, which is the signature of OCR
noise or a symbol-encoded font). Flagged filings are excluded from scoring rather
than contributing junk.

## Extraction

**2026-08-04 — Tiered patterns with a confidence downgrade, not a single regex.**
Each line item has tier-1 patterns (unambiguous labels, e.g. "Amortisation of
players' registrations") and tier-2 fallbacks (e.g. a bare "Amortisation of
intangible fixed assets", which at a football club is usually but not always player
registrations). A tier-2 match still produces a value but drops confidence to
`medium`, so the human validation pass knows where to look first.

**2026-08-04 — Note references are stripped before taking the current-year column.**
P&L rows read "Turnover 2 468,712 442,364" where `2` is a note reference. Small
comma-less integers are dropped when larger figures appear later on the same row.
The first surviving figure is the current year; the second is the comparative,
which we never take even when it is labelled "restated".

**2026-08-04 — Costs are normalised to positive magnitudes.**
Wages and player amortisation are printed bracketed (negative) in the P&L and
unbracketed in the notes. Storing the signed value as printed would make the same
economic quantity differ in sign by source section, so both are stored as positive
magnitudes and the item name carries the convention. Profit on disposal keeps its
sign, because a loss on disposal is a genuinely different fact.

**2026-08-04 — Unit detection is per-section with a document fallback.**
`£'000` vs `£m` is read from the section being searched first, then the whole
document. If neither yields a marker the extractor assumes `£'000` — by far the
more common convention at this size of company — and marks the value `low`
confidence so it is checked by hand.

## Scoring

**2026-08-04 — Digits are stripped before tokenising.**
Every strategic report restates last year's figures. Leaving numerals in would
score routine numeric updating as language drift, which is exactly the confound
Lazy Prices is designed to avoid.

**2026-08-04 — TF-IDF is fit per club, over that club's own filings only.**
A club-specific document frequency discounts that club's own boilerplate against
itself, so the score measures how much *this* club changed its language rather than
how unusual its house style is relative to other clubs. It also keeps clubs
independent, so adding or dropping a comparator cannot change another club's score.

**2026-08-04 — Interpolated Kneser-Ney trigram, hand-rolled.**
Order 3 with discount 0.75. Fit on year t−1's report, scored on year t. KN's
continuation counts matter here because filing prose is full of frequent but
context-bound phrases ("the year ended", "the directors"); a plain
backoff model would treat their reappearance as informative. Implemented in stdlib
— roughly 40 lines — rather than adding nltk. `tests/test_score.py` checks it is a
proper distribution (probabilities over the vocabulary for a fixed context sum to
≤1), which is the property most easily broken by a hand-rolled smoother.

**2026-08-04 — Sanity checks run as part of `make score` and gate its exit code.**
Identical documents must score ~0 novelty, and a deterministically shuffled
document must be more surprising than the original. The shuffle is a fixed stride
permutation rather than an RNG shuffle, so the check adds no seed dependency.
