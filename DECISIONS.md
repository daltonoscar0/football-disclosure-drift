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
- *`--psm 3` (automatic page segmentation).* **Corrected from an earlier choice of
  psm 6.** I originally picked psm 6 ("uniform block of text") on the assumption
  that automatic segmentation would split P&L columns into separate blocks and
  interleave them. That assumption was asserted, not tested, and it was wrong. On
  Arsenal's six-column consolidated P&L the two modes produce byte-identical
  output. On Everton they do not: Everton files a designed, two-column magazine-
  style annual report, and psm 6 reads it *line-across*, welding the left and right
  columns into one line ("...significant to **Gate receipts revenue of £19.1m was
  generated from 19 Premier League**") and missing the section headings entirely.
  psm 3 reads the columns correctly and recovers "STRATEGIC REPORT" and
  "CONSOLIDATED PROFIT AND LOSS ACCOUNT" as clean running headers.

  This is why all 15 filings were re-OCR'd with a single setting rather than
  special-casing Everton: a study that measures language change across clubs should
  not vary its text-acquisition method by club.
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

**2026-08-04 — Everton needed no special-casing once the OCR mode was right.**
Everton's three filings initially came out with no strategic report and no notes
section detected — 3 of 15, past the "flag and exclude" threshold. The apparent
cause was that its section titles appear only on the contents page, which pointed
towards building a contents-page-to-page-range fallback. That turned out to be
unnecessary: the titles *are* present as running headers on every page, and psm 6
was simply failing to read them out of the two-column layout. Switching to psm 3
fixed all three filings with no Everton-specific code. Worth recording as a case
where the tempting fix would have added machinery to paper over a bad upstream
setting.

**2026-08-04 — Tottenham combines two statements under one heading.**
Tottenham's heading is "Consolidated income statement and statement of other
comprehensive income", which the P&L pattern rejected because it requires a
whole-line match. The pattern now accepts the trailing "and statement of other
comprehensive income".

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

**2026-08-04 — `profit_on_disposal` tracks non-player disposals only. FLAGGED FOR
REVIEW AT CHECKPOINT A.**
The brief names the item "profit on disposal of players/assets", which is ambiguous,
and the two readings produce materially different deliverables. These filings carry
*two* distinct disposal lines:

- *Profit on disposal of player registrations* — routine, present at every club
  every year, large (Chelsea: £62.9m FY23, £152.5m FY24, £57.9m FY25).
- *Profit on disposal of fixed assets / subsidiaries* — the intra-group sales this
  project exists to test (Chelsea: £76.5m FY23 hotels and car park to Blueco 22
  Properties Limited, £198.7m FY24 women's team, a £3.0m loss FY25 Kingsmeadow).

Tracking the player line would bury the intra-group signal underneath a much larger
routine number, and the stated objective explicitly concerns "profit on disposals
spikes from the intra-group sales". So the tracked item is the non-player line, and
player-registration disposals are extracted separately and printed in VALIDATION.md
as a context table rather than as one of the four items. This keeps the deliverable
at four items / 60 values while leaving both figures visible for checking.

Where a club has no non-player disposal line, the value is blank rather than zero —
absence of the line is different from a disclosed nil, and for the comparators that
absence is itself part of the finding.

**2026-08-04 — A standalone dash is a nil column, not an absent one.**
This was a real bug caught against Chelsea's FY2025 P&L. The row reads:

    Profit on disposal of fixed asset investments 16 - - - 198,749

The current year is nil and £198,749k is the *comparative*. Discarding unparseable
dash tokens collapsed the column positions and reported last year's £198.7m as this
year's figure — a wrong number that would have looked entirely plausible in the
findings note. Dashes now parse to 0.0 and hold their column. The same fix makes
Arsenal's `- 51,073 51,073 - 10,732 10,732` and Chelsea's
`76,524 - 76,524 -` resolve correctly, and all three are pinned by tests.

**2026-08-04 — Segmentation mode is chosen per page, not per filing.**
Neither Tesseract mode works everywhere. On some statement pages automatic
segmentation reads the label column and the figure columns as two separate blocks
and emits them one after the other, leaving no label+figure rows at all:

    Turnover se 3                  512,467 - 512,467 481,278
    Cost of sales        becomes   (467,205) - (467,205) (386,794)

That hit Chelsea's 2023 and 2025 statements — the case-study club. psm 6 reads
those correctly but ruins Everton's two-column prose. So pages are OCR'd with
psm 3, then any page whose figures came out orphaned from their labels is re-OCR'd
with psm 6 and kept only if it yields more usable rows. 30 of 770 pages were
repaired this way.

**2026-08-04 — Labels that wrap across lines are rejoined before matching.**
A wrapped label had to be rejoined *before* pattern matching, not after, because a
negative lookahead cannot exclude words it cannot see. "Profit on disposal of" /
"player registrations 10,732" was matching the generic disposal pattern and leaking
Arsenal's routine player trading into the tracked intra-group item. Only lines
starting with a lowercase word count as continuations — that is what stops
"Amortisation and impairment" from swallowing the "At 1 July 2023" movement row
beneath it and reporting a £2,023,000 amortisation charge, which it did across six
filings.

**2026-08-04 — Each value is cross-checked against the next year's filing.**
Every filing restates the prior year as a comparative, so the same audited figure
appears in two independent documents. Comparing them catches OCR damage that is
otherwise invisible: Tottenham's FY2023 revenue reads "$49,633" in its own filing
and 549,633 in FY2024's comparative column.

Disagreements are reported, never auto-corrected. Either side can be the damaged
one, and a disagreement can also be a genuine basis change rather than an error —
which is how the Arsenal wages problem surfaced (below). 20 of the extracted values
agree with the following year's restatement; 6 disagree and are flagged.

**2026-08-04 — Arsenal's wages basis is inconsistent across years. UNRESOLVED,
FOR CHECKPOINT A.**
Arsenal's 2023 and 2025 filings put "Wages and salaries" in a split block with no
figures on its line, so extraction falls back to "Staff costs" — which includes
social security and pension costs and is therefore a materially larger number
(2023: £234.8m staff costs vs £204.6m wages and salaries). 2024 resolves to
"Wages and salaries". Mixing the two bases across years would make Arsenal's
wages series meaningless.

Both figures are defensible; what is not defensible is switching between them
mid-series. VALIDATION.md shows which label each value came from so the basis can
be made consistent by hand. Flagged rather than silently patched, because choosing
the basis is an analyst's call.

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

## Validation (Checkpoint A outcome)

**2026-08-04 — Wages basis: total staff costs, agreed at Checkpoint A.**
Tottenham discloses no "wages and salaries" line in any year, so total staff costs
is the only basis available for every club-year. The narrower basis would have left
Tottenham blank and made the wages column non-comparable across clubs. Chelsea and
West Ham print the components without a labelled total, so their totals are summed
from the components and verified by the arithmetic
(`152,926 + 22,638 + 329 = 175,893`). Basis includes social security and pension
costs and runs 12–15% above pure wages.

**2026-08-04 — Three of six flagged values were genuine errors; three flags were
spurious.**
Corrections are recorded in `data/extracted/line_items.validated.csv` with the
evidence for each. Every correction is justified by a second, independent appearance
of the figure inside the filings, never by judgement:

- Everton FY2023 revenue 7.2 → 172.2 (OCR read 172,155 as "7215S")
- Tottenham FY2023 revenue 49.6 → 549.6 (leading 5 lost from 549,633)
- Tottenham FY2024 disposals −0.025 → 0 (the single printed figure is the FY2023
  comparative)

The three upheld flags were comparative-reader failures rather than wrong values.

**2026-08-04 — Tottenham FY2023 revenue passed the cross-year check while being
wrong.** The FY2024 filing's comparative column carries the same OCR damage, so two
independent readings agreed on 49,633. Only the series check — an order-of-magnitude
departure from the club's own median — caught it. This is why both checks exist, and
why agreement between them is reported rather than treated as proof.

**2026-08-04 — Parenthesised figures are never note references.**
"(25)" is a real −25 column however small. Treating small comma-less numbers as note
references collapsed Tottenham's "Profit on disposal of property, plant and
equipment (25) -" to the nil column and reported 0 instead of a £25k loss.
