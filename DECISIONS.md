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

## OCR

**2026-08-04 — All 15 filings are image-only scans. OCR added as a pipeline stage.**
This was not anticipated in the original plan, which assumed a PDF text extractor
would be enough. It is not: all 15 filings contain exactly one image per page and
**zero** embedded text characters. pdfplumber returns empty strings for every page
of every filing. The failure rate is 15/15, well past the "fix the stage rather
than exclude" threshold, so OCR is mandatory rather than a nice-to-have.

Checked first, and ruled out: the Companies House document API exposes only
`application/pdf` for these filings — there is no iXBRL or XHTML alternative to
fall back on, which there would be for a smaller company's accounts.

Choices made:

- *Rasteriser: pypdfium2 at 200 DPI.* Character yield at 200 DPI is identical to
  300 DPI on these scans (4,175 chars/page on the test page either way) and it
  renders faster. pypdfium2 is already present as a pdfplumber dependency, so this
  adds no new install.
- *Engine: the `tesseract` CLI, called directly.* Invoking the binary via
  `subprocess` avoids adding `pytesseract` for what amounts to one command line.
  Tesseract itself is a new **system** prerequisite (`brew install tesseract`), now
  documented in the README. This is a real widening of the dependency surface and
  is justified only because there is no text without it.
- *`--psm 6` ("uniform block of text").* The default fully-automatic page
  segmentation treats P&L columns as separate blocks and interleaves them, which
  destroys row structure. psm 6 keeps a label and its figures on one output line,
  which is exactly what the extractor's row regexes need.
- *`OMP_THREAD_LIMIT=1` per worker.* Each Tesseract process otherwise spawns its
  own thread pool; with a process pool on top, the workers oversubscribe the CPU
  and the batch runs slower than with the limit set.

Cost: ~770 pages at ~8.6 s/page. Cached per filing in `data/ocr/<club>/<year>.json`
so it is paid once; `data/ocr/` is gitignored alongside `data/raw/`.

**2026-08-04 — pypdfium2 also rescues two filings pdfminer cannot open.**
`chelsea/2023.pdf` and `tottenham/2025.pdf` raise `Unexpected EOF` in pdfminer.
Both files are complete (they end in a valid `%%EOF`); the xref tables are simply
malformed in a way pdfminer refuses and pdfium tolerates. pypdfium2 opens both and
reports 50 and 65 pages respectively. Had OCR not been necessary anyway, these two
would have been the ≤2 "degrade gracefully" exclusions; instead the new rasteriser
fixes them for free.

**2026-08-04 — DocuSign banners are stripped before scoring.**
The scans are e-signed, so every page carries an identical
`Docusign Envelope ID: ...` line. Left in, it would repeat once per page and
inflate year-over-year similarity — a systematic bias against detecting drift.
Stripped at parse time.

## Parsing

**2026-08-04 — Running headers are the section signal, and carry "(CONTINUED)".**
These filings repeat the section name at the top of every page
("NOTES TO THE FINANCIAL STATEMENTS (CONTINUED)"). Heading matching therefore
strips a trailing "(continued)" and OCR rule-line artefacts (`|`, `:`) before
testing the pattern. Segment merging (below) makes the repetition harmless.

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
