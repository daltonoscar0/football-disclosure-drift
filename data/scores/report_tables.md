# Report tables

_Line items: extractor output (NOT hand-validated)._

## Club ranking by disclosure drift

| rank | club | mean cosine novelty | max cosine novelty | mean surprisal (bits) |
|---:|---|---:|---:|---:|
| 1 | chelsea | 0.290 | 0.301 | 4.56 |
| 2 | tottenham | 0.256 | 0.329 | 5.28 |
| 3 | arsenal | 0.243 | 0.297 | 5.54 |
| 4 | west-ham | 0.241 | 0.247 | 4.52 |
| 5 | everton | 0.206 | 0.211 | 3.94 |

## Year-over-year drift, all pairs

| club | pair | cosine novelty | Jaccard novelty | surprisal (bits) |
|---|---|---:|---:|---:|
| arsenal | 2023→2024 | 0.297 | 0.493 | 6.41 |
| arsenal | 2024→2025 | 0.188 | 0.352 | 4.68 |
| chelsea | 2023→2024 | 0.280 | 0.397 | 5.56 |
| chelsea | 2024→2025 | 0.301 | 0.431 | 3.57 |
| everton | 2023→2024 | 0.211 | 0.349 | 3.77 |
| everton | 2024→2025 | 0.201 | 0.335 | 4.10 |
| tottenham | 2023→2024 | 0.183 | 0.324 | 4.30 |
| tottenham | 2024→2025 | 0.329 | 0.511 | 6.26 |
| west-ham | 2023→2024 | 0.247 | 0.402 | 4.52 |
| west-ham | 2024→2025 | 0.235 | 0.379 | 4.53 |

## Line items

| club | year | Revenue | Wages | Player amortisation | Profit on disposals |
|---|---|---:|---:|---:|---:|
| arsenal | 2023 | 467.2 | 234.8 | 139.1 | — |
| arsenal | 2024 | 617.2 | 287.0 | 171.1 | — |
| arsenal | 2025 | 692.0 | 346.8 | 171.6 | -0.0 |
| chelsea | 2023 | 512.5 | 352.4 | 205.0 | 76.5 |
| chelsea | 2024 | 468.5 | 294.6 | 191.8 | 198.7 |
| chelsea | 2025 | 490.9 | — | 213.9 | 0.0 |
| everton | 2023 | 7.2 | 138.4 | 77.6 | 0.0 |
| everton | 2024 | 186.9 | 137.1 | 64.6 | 0.0 |
| everton | 2025 | 196.7 | 132.4 | 50.9 | 0.0 |
| tottenham | 2023 | 49.6 | 251.1 | 109.1 | 0.0 |
| tottenham | 2024 | 517.8 | 221.9 | 136.3 | 82.3 |
| tottenham | 2025 | 564.9 | 255.8 | 141.9 | 52.6 |
| west-ham | 2023 | 236.7 | 118.8 | 65.3 | — |
| west-ham | 2024 | 269.7 | 140.7 | 83.5 | — |
| west-ham | 2025 | 227.6 | 152.9 | 103.3 | — |

_All figures £m._

## Chelsea: disposals vs disclosure drift

| year | profit on disposals (£m) | cosine novelty vs prior year | surprisal (bits) |
|---|---:|---:|---:|
| 2023 | 76.5 | — (no prior year) | — |
| 2024 | 198.7 | 0.280 | 5.56 |
| 2025 | 0.0 | 0.301 | 3.57 |

