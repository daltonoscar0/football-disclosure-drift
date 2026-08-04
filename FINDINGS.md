# Findings

**Does disclosure-language drift in football club filings track intra-group asset sales?**

Chelsea ranks first of five clubs on mean year-over-year disclosure drift, and it is
the only club in the sample booking material intra-group asset disposals. But within
Chelsea the year-by-year alignment does not hold: the two novelty measures disagree
about which year is the outlier, and the measure that best matches the disposals is
the one with the weaker methodological standing. The cross-club signal is real; the
within-club timing claim is not supported by n=2 pairs.

---

## Method

Fifteen filings — five clubs × three most recent full accounts — pulled from the
Companies House document API. For each club the filing entity is the one whose
accounts consolidate the group, since intra-group disposal profits appear only in a
consolidated P&L and are eliminated a level higher (see `DECISIONS.md`).

| Club | Filing entity | Company no. |
|---|---|---|
| Chelsea | Chelsea FC Holdings Limited | 02536231 |
| Arsenal | Arsenal Holdings Limited | 04250459 |
| Tottenham | Tottenham Hotspur Limited | 01706358 |
| West Ham | WH Holding Limited | 05993863 |
| Everton | Everton Football Club Company, Limited | 00036624 |

Every filing is an image-only scan with no text layer, so all text comes from OCR
(Tesseract, 200 DPI, segmentation mode chosen per page). Each filing is segmented
into sections by heading detection; the strategic report is the unit of analysis.
All 15 yielded a strategic report between 17k and 43k characters, with no filing
excluded.

Two novelty measures per consecutive year pair, both computed on the strategic
report only, in the spirit of Cohen, Malloy & Nguyen's *Lazy Prices* — the quantity
of interest is **change** between consecutive filings, not absolute complexity:

1. **Similarity drop.** TF-IDF cosine and Jaccard between year *t* and *t−1*,
   novelty = 1 − similarity. TF-IDF is fit per club over that club's own three
   documents, so a club's boilerplate is discounted against itself and clubs stay
   independent of one another.
2. **Surprisal.** Mean per-token surprisal of year *t*'s report under an
   interpolated Kneser–Ney trigram model fit on year *t−1*'s report.

Digits are stripped before tokenising: every strategic report restates last year's
figures, and leaving numerals in would score routine numeric updating as language
drift — the exact confound the method exists to avoid. The per-page DocuSign banner
is stripped for the same reason.

Sanity checks run as part of `make score` and gate its exit code: identical
documents score 0 novelty on both similarity measures, and a deterministically
shuffled document scores 9.45 bits against 1.97 for the original.

---

## Ranking by disclosure drift

| Rank | Club | Mean cosine novelty | Max cosine novelty | Mean surprisal (bits) |
|---:|---|---:|---:|---:|
| 1 | **Chelsea** | **0.290** | 0.301 | 4.56 |
| 2 | Tottenham | 0.256 | 0.329 | 5.28 |
| 3 | Arsenal | 0.243 | 0.297 | 5.54 |
| 4 | West Ham | 0.241 | 0.247 | 4.52 |
| 5 | Everton | 0.206 | 0.211 | 3.94 |

Chelsea rewrites more of its strategic report year-over-year than any comparator.
The spread is modest — 0.290 against a 0.206 floor — and with two pairs per club
no significance can be attached to the ordering.

Note that the two measures rank clubs differently. Chelsea is first on cosine
novelty but fourth on mean surprisal. These measure different things: cosine
novelty responds to *which words appear*, surprisal to *word order and phrasing*.
A club can substantially reorganise its vocabulary while keeping familiar sentence
constructions, which is what Chelsea's profile looks like.

### All year pairs

| Club | Pair | Cosine novelty | Jaccard novelty | Surprisal (bits) |
|---|---|---:|---:|---:|
| Arsenal | 2023→2024 | 0.297 | 0.493 | 6.41 |
| Arsenal | 2024→2025 | 0.188 | 0.352 | 4.68 |
| **Chelsea** | **2023→2024** | **0.280** | 0.397 | 5.56 |
| **Chelsea** | **2024→2025** | **0.301** | 0.431 | 3.57 |
| Everton | 2023→2024 | 0.211 | 0.349 | 3.77 |
| Everton | 2024→2025 | 0.201 | 0.335 | 4.10 |
| Tottenham | 2023→2024 | 0.183 | 0.324 | 4.30 |
| Tottenham | 2024→2025 | 0.329 | 0.511 | 6.26 |
| West Ham | 2023→2024 | 0.247 | 0.402 | 4.52 |
| West Ham | 2024→2025 | 0.235 | 0.379 | 4.53 |

---

## Line items

All figures £m. Wages are **total staff costs** (wages and salaries plus social
security and pension costs) — Tottenham discloses no wages-and-salaries line, so
this is the only basis available for every club-year. Profit on disposals is
**non-player** disposals only; player-registration disposals are a separate routine
line, shown below as context.

These are **pipeline output, not hand-validated**. Two values are known bad and are
shown as extracted, marked ⚠, rather than silently corrected.

| Club | Year | Revenue | Wages | Player amortisation | Profit on disposals |
|---|---|---:|---:|---:|---:|
| Arsenal | 2023 | 467.2 | 234.8 | 139.1 | 0.0 |
| Arsenal | 2024 | 617.2 | 327.8 | 171.1 | — |
| Arsenal | 2025 | 692.0 | 346.8 | 171.6 | −0.0 |
| **Chelsea** | **2023** | 512.5 | 404.0 | 205.0 | **76.5** |
| **Chelsea** | **2024** | 468.5 | 338.0 | 191.8 | **198.7** |
| **Chelsea** | **2025** | 490.9 | 359.3 | 213.9 | 0.0 |
| Everton | 2023 | ⚠ 7.2 | 159.0 | 77.6 | 0.0 |
| Everton | 2024 | 186.9 | 156.6 | 64.6 | 0.0 |
| Everton | 2025 | 196.7 | 152.1 | 50.9 | 0.0 |
| Tottenham | 2023 | ⚠ 49.6 | 251.1 | 109.1 | 0.0 |
| Tottenham | 2024 | 517.8 | 221.9 | 136.3 | 0.0 |
| Tottenham | 2025 | 564.9 | 255.8 | 141.9 | — |
| West Ham | 2023 | 236.7 | 136.8 | 65.3 | — |
| West Ham | 2024 | 269.7 | 161.0 | 83.5 | — |
| West Ham | 2025 | 227.6 | 175.9 | 103.3 | — |

`—` means the line is not disclosed at all; `0.0` means a disclosed nil. West Ham
discloses only player disposals in all three years, which is why its column is
empty rather than zero.

⚠ **Two revenue figures are OCR-damaged and flagged by the pipeline.** Everton FY2023
reads `Turnover 2 7215S - 172,A55` — the scan mangled 172,155 — and Tottenham FY2023
reads `Revenue 2 $49,633` where the digit 5 was lost from 549,633. Both are caught by
the series check as order-of-magnitude departures from the club's own median
(0.04× and 0.10×). The true figures are legible in the following year's comparative
column (£172.2m and £549.6m) but are **not** substituted here, because correcting
extracted values by hand is the validation step's job, not the extractor's.

Tottenham FY2023 is the more instructive failure: it *passed* the cross-year check,
because the FY2024 filing's comparative column carries the same OCR damage. Two
independent readings agreed on a wrong number. Only the series check caught it —
which is a useful reminder that agreement between checks is not proof of
correctness.

None of this affects the drift results, which are computed from the strategic report
text and never touch these figures.

**Chelsea is the only club in the sample with material non-player disposal profits.**
Every comparator is nil or absent in every year. That, rather than the drift
ranking, is the cleanest result here.

### Context: player-registration disposals (not a tracked item)

| Club | 2023 | 2024 | 2025 |
|---|---:|---:|---:|
| Arsenal | 10.7 | 51.1 | 81.2 |
| Chelsea | 62.9 | 152.5 | 57.9 |
| Everton | 47.5 | 48.5 | 31.3 |
| Tottenham | 15.5 | 82.3 | 52.6 |
| West Ham | 17.0 | 96.3 | 20.0 |

Included because these are large and routine, and conflating them with intra-group
asset sales would have buried the signal. Every club has them in every year; only
Chelsea also has material non-player disposals.

Clubs label this line differently, which is why separating the two mattered:
Tottenham calls it "profit on disposal of intangible fixed assets" (at a football
club the intangible fixed assets *are* the player registrations), Everton calls it
"profit on player trading", and West Ham "profit on disposal of players". Each of
those was, at some point during development, being counted as an intra-group asset
sale.

---

## Chelsea case study

The two transactions the study was built to test are both inside the window, and
both are described explicitly in the filings:

- **FY2023** — hotel buildings and car park sold to *Blueco 22 Properties Limited, a
  fellow subsidiary of the intermediate parent*. Profit on disposal of fixed assets
  **£76.5m**.
- **FY2024** — sale of the women's team. *"This sale resulted in a profit on disposal
  of subsidiaries of £198.7m to the Group."*
- **FY2025** — Kingsmeadow stadium sold to a fellow group company, booked as a
  **loss**; non-player disposal profit is nil.

### Does drift spike in the disposal years?

| Filing year | Disposals (£m) | Cosine novelty vs prior year | Surprisal (bits) |
|---|---:|---:|---:|
| 2023 | 76.5 | — (no prior year in sample) | — |
| 2024 | **198.7** | 0.280 | **5.56** |
| 2025 | 0.0 | **0.301** | 3.57 |

**The alignment does not hold cleanly, and the two measures disagree.**

Cosine novelty is *higher* in 2025 (0.301), the year non-player disposals fell to
nil, than in 2024 (0.280), the year of the £198.7m women's-team sale. On this
measure the drift signal points the wrong way.

Surprisal points the other way: 2024 scores 5.56 bits against 3.57 for 2025, a
substantial gap in the direction the hypothesis predicts. So the year of the large
intra-group sale *is* the more linguistically unexpected one under an n-gram model
fit on the previous year.

Two reasons not to lean on the surprisal reading:

1. **Document length is confounded.** Chelsea's 2025 strategic report is 2,853
   tokens against 5,152 in 2024 — it nearly halved. Surprisal is a per-token mean,
   but a much shorter document drawn from a smaller vocabulary is easier to predict
   under a model fit on a longer one. Some of the 2024/2025 gap is length, not
   novelty.
2. **Cosine novelty is the measure with the closer claim to Lazy Prices**, which
   works from document similarity rather than a language model. Preferring surprisal
   here because it agrees with the hypothesis would be choosing the metric to fit
   the result.

The honest reading: Chelsea's *overall* level of disclosure rewriting is the highest
in the sample, which is consistent with a group doing unusual things and having to
describe them. But with two year-pairs there is no basis for claiming the drift
score *times* the disposals. The FY2023 hotel sale cannot be tested at all — it is
the earliest year in the sample, so it has no prior year to compare against, which
removes exactly one of the two events from the analysis.

---

## Limitations

- **n = 15 filings, 10 year-pairs, 2 per club.** No statistical claim is available.
  Ranking differences of 0.05 in cosine novelty are not distinguishable from noise.
- **One league, one country, one accounting framework.** Nothing here generalises
  beyond English club accounts without retesting.
- **The earliest year in each club's window has no pair**, which costs one of
  Chelsea's two disposal events.
- **OCR quality is the dominant technical risk.** Every filing is a scan. Real
  damage was found and corrected during development — a note heading absorbing the
  movement row beneath it and reporting the year 2023 as a £2,023,000 amortisation
  charge; nil dashes collapsing so a comparative was read as the current year;
  `$49,633` for 549,633. Two checks run over every value: a cross-year check against
  the comparative the *following* year's filing prints for the same line, and a
  series check against the club's own median. Of the 60 values, 18 agree with the
  next year's restatement, 6 are flagged (4 cross-year mismatches, 2 series
  outliers), and 5 lines are not disclosed. All flags are in
  `data/extracted/VALIDATION.md`. Note that one damaged value passed the cross-year
  check because both filings carried the same OCR error — checks agreeing is not
  proof of correctness.
- **Heading detection is brittle.** Sections are recovered from running headers. A
  single stray OCR character (`GROUP PROFIT AND LOSS ACCOUNT ;`) was enough to lose
  an entire statement before it was fixed. Other filings may fail in ways this
  sample did not exercise.
- **The line items in this note are extractor output, not hand-validated.** The two
  automated checks give independent support for most values, but the six flagged
  figures and five absent lines have not been confirmed by eye against the source
  PDFs. `make report` warns whenever it builds tables from unvalidated numbers.
- **Strategic report length varies substantially** both across clubs and within a
  club across years (Chelsea: 5,152 → 2,853 tokens). This is not controlled for and
  affects the surprisal measure in particular.
- **Drift is measured, not attributed.** A club can rewrite its strategic report for
  reasons entirely unrelated to disposals — new ownership, a new stadium, a
  regulatory change, or simply a new author. Nothing here identifies *why* language
  changed.

## Reproducing

```
make pipeline    # ~3s once data/raw and data/ocr are populated
make check-parse # per-filing sections and character counts
make test        # 80 tests
```

All outputs are deterministic: fixed iteration order, no RNG, stable JSON key
ordering.
