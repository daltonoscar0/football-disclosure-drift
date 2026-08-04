# Line-item validation

Every extracted value with the exact filing row it came from. Fill in the
`verified?` column with `y` or `n`; where the value is wrong put the correct
figure in `corrected_value` **in pounds** (not thousands).

`cross-check vs next year` compares each value with the comparative column
the *following* year's filing prints for the same line. `ok` means the two
agree. A **MISMATCH** means they disagree — which may be OCR damage on either
side, or a genuine change of basis (e.g. "Wages and salaries" one year and
"Staff costs" the next). These are the rows to check first.

`confidence` is the extractor's own assessment: `high` = unambiguous label
matched in the expected section with an explicit unit marker; `medium` = a
fallback label or a document-level unit inference; `low` = unit assumed or
the row had no comparative column; `none` = nothing matched.

## arsenal

| year | item | value | conf | cross-check vs next year | section | source row | verified? | corrected_value |
|---|---|---|---|---|---|---|---|---|
| 2023 | revenue | £467,155,000 | medium | ok | profit_and_loss | `Turnover of the Group including its share of joint ventures 465,698 1,457 467,155 370,384 1,978 372,362` |  |  |
| 2023 | wages | £234,766,000 | high | ok | notes | `Staff costs 234,766 212,345` |  |  |
| 2023 | player_amortisation | £139,060,000 | high | ok | notes | `Amortisation of player registrations 139,060 124,567` |  |  |
| 2023 | profit_on_disposal | £0 | high | — | notes | `Loss on disposal of tangible fixed assets - -` |  |  |
| 2024 | revenue | £617,167,000 | medium | ok | profit_and_loss | `Turnover of the Group including its share of joint ventures 615,793 1,374 617,167 465,698 1,457 467,155` |  |  |
| 2024 | wages | £327,822,000 | high | ok | notes | `Staff costs 327,822 234,766` |  |  |
| 2024 | player_amortisation | £171,099,000 | high | ok | notes | `Amortisation of player registrations . 171,099 139,060` |  |  |
| 2024 | profit_on_disposal | — | none | — | — | `—` |  |  |
| 2025 | revenue | £692,026,000 | medium | — | profit_and_loss | `Turnover of the Group including its share of joint ventures 691,572 454 692,026 615,793 1,374 617,167` |  |  |
| 2025 | wages | £346,804,000 | high | — | notes | `Staff costs 346,804 327,822` |  |  |
| 2025 | player_amortisation | £171,627,000 | high | — | notes | `Amortisation of player registrations . 171,627 171,099` |  |  |
| 2025 | profit_on_disposal | £-19,000 | medium | — | notes | `Profit on disposal of fixed assets (19)` |  |  |

_Context — profit on disposal of **player registrations**. Not one of the four tracked items (see DECISIONS.md), shown so the tracked non-player disposal figure above can be checked against it._

| year | player disposal profit | source row |
|---|---|---|
| 2023 | £10,732,000 | `Profit on disposal of player registrations - 10,732 10,732 - 22,238 22,238` |
| 2024 | £51,073,000 | `Profit on disposal of player registrations - 51,073 51,073 - 10,732 10,732` |
| 2025 | £81,237,000 | `Profit on disposal of player registrations - 81,237 81,237 - 51,073 51,073` |

## chelsea

| year | item | value | conf | cross-check vs next year | section | source row | verified? | corrected_value |
|---|---|---|---|---|---|---|---|---|
| 2023 | revenue | £512,467,000 | medium | — | profit_and_loss | `Turnover se 3 512,467 - 512,467 481,278` |  |  |
| 2023 | wages | £403,962,000 | medium | — | notes | `derived total staff costs: 352,355 + 49,831 + 1,776 = 403,962` |  |  |
| 2023 | player_amortisation | £205,000,000 | medium | — | notes | `Amortisation charged for the year 1,750 203,250 205,000` |  |  |
| 2023 | profit_on_disposal | £76,524,000 | medium | — | profit_and_loss | `Profit on disposal of fixed assets 76,524 - 76,524 -` |  |  |
| 2024 | revenue | £468,486,000 | medium | — | profit_and_loss | `Turnover 3 468,486 - 468,486 512,467` |  |  |
| 2024 | wages | £338,021,000 | medium | — | notes | `derived total staff costs: 294,629 + 41,035 + 2,357 = 338,021` |  |  |
| 2024 | player_amortisation | £191,826,000 | medium | — | notes | `Amortisation charged for the year 1,770 190,056 191,826` |  |  |
| 2024 | profit_on_disposal | £198,749,000 | low | **MISMATCH: 2025 filing restates this as 0** | profit_and_loss | `Profit on disposal of fixed assets investments 17 198,749 - 198,749 -` |  |  |
| 2025 | revenue | £490,857,000 | medium | — | profit_and_loss | `Turnover 3 490,857 - 490,857 468,486` |  |  |
| 2025 | wages | £359,265,000 | medium | — | notes | `derived total staff costs: 312,812 + 44,041 + 2,412 = 359,265` |  |  |
| 2025 | player_amortisation | £213,893,000 | medium | — | notes | `Amortisation charged for the year 1,646 212,247 213,893` |  |  |
| 2025 | profit_on_disposal | £0 | medium | — | profit_and_loss | `Profit on disposal of fixed asset investments 16 - - - 198,749` |  |  |

_Context — profit on disposal of **player registrations**. Not one of the four tracked items (see DECISIONS.md), shown so the tracked non-player disposal figure above can be checked against it._

| year | player disposal profit | source row |
|---|---|---|
| 2023 | £62,861,000 | `Profit on disposal of player registrations - 62,861 62,861 123,213` |
| 2024 | £152,463,000 | `Profit on disposal of player registrations - 152,463 152,463 62,861` |
| 2025 | £57,906,000 | `Profit on disposal of player registrations - 57,906 57,906 152,463` |

## everton

| year | item | value | conf | cross-check vs next year | section | source row | verified? | corrected_value |
|---|---|---|---|---|---|---|---|---|
| 2023 | revenue | £7,215,000 | low | OUTLIER: 0.04x this club's median revenue (186,902,000) | profit_and_loss | `Turnover 2 7215S - 172,A55, 181,007 - 181,007` |  |  |
| 2023 | wages | £159,026,000 | high | ok | notes | `Staff costs (nate 7) 159,026 162,010` |  |  |
| 2023 | player_amortisation | £77,621,000 | high | ok | notes | `Amortisation of players’ registrations 77621 68,327` |  |  |
| 2023 | profit_on_disposal | £0 | low | — | profit_and_loss | `Profit on disposal of tangible . -` |  |  |
| 2024 | revenue | £186,902,000 | low | **MISMATCH: 2025 filing restates this as 196,697,000** | profit_and_loss | `Turnover 186,902 - 186,902 172,155 : 172,155` |  |  |
| 2024 | wages | £156,631,000 | high | ok | notes | `Staff costs 156,631 159,026` |  |  |
| 2024 | player_amortisation | £64,581,000 | high | ok | notes | `Amortisation of players’ registrations 64,581 77621` |  |  |
| 2024 | profit_on_disposal | £0 | low | — | profit_and_loss | `Profit on disposal of tangible . -` |  |  |
| 2025 | revenue | £196,697,000 | medium | — | profit_and_loss | `Turnover 196,697 : + 196,697 » 3186,902 - 186,902` |  |  |
| 2025 | wages | £152,064,000 | high | — | notes | `Staff costs 152,064 156,631` |  |  |
| 2025 | player_amortisation | £50,901,000 | high | — | notes | `Amortisation of players’ registrations 50,901 64,581` |  |  |
| 2025 | profit_on_disposal | £0 | medium | — | profit_and_loss | `Profit on disposal of tangible fixed assets 4 - 4 4 4` |  |  |

_Context — profit on disposal of **player registrations**. Not one of the four tracked items (see DECISIONS.md), shown so the tracked non-player disposal figure above can be checked against it._

| year | player disposal profit | source row |
|---|---|---|
| 2023 | £47,518,000 | `Profit on player trading - 47518 47,518 - 67,684 67,684` |
| 2024 | £48,545,000 | `Profit on player trading - 48,545 48,545 - 47518 47,518` |
| 2025 | £31,325,000 | `Profit on player trading : 31,325 31,325 - 48,545 48,545` |

## tottenham

| year | item | value | conf | cross-check vs next year | section | source row | verified? | corrected_value |
|---|---|---|---|---|---|---|---|---|
| 2023 | revenue | £49,633,000 | low | ok | profit_and_loss | `Revenue 2 $49,633 - $49,633 443,415 - 443,415` |  |  |
| 2023 | wages | £251,121,000 | high | ok | notes | `Staff costs S) 251,121 209,180` |  |  |
| 2023 | player_amortisation | £109,073,000 | medium | ok | notes | `Amortisation of intangible fixed assets 109,073 79,520` |  |  |
| 2023 | profit_on_disposal | £0 | low | **MISMATCH: 2024 filing restates this as -25,000** | notes | `Profit on disposal of property, plant and equipment (25) -` |  |  |
| 2024 | revenue | £517,763,000 | low | **MISMATCH: 2025 filing restates this as 0** | profit_and_loss | `Revenue 2 517,763 - 517,763 549,633 - $49,633` |  |  |
| 2024 | wages | £221,929,000 | high | ok | notes | `Staff costs 221,929 251,121` |  |  |
| 2024 | player_amortisation | £136,287,000 | medium | ok | notes | `Amortisation of intangible fixed assets 136,287 109,073` |  |  |
| 2024 | profit_on_disposal | £6,000 | high | — | notes | `Loss/(profit) on disposal of property, plant and equipment 6 (25)` |  |  |
| 2025 | revenue | £564,881,000 | medium | — | profit_and_loss | `Revenue 2 564,881 - $64,881 517,763 - 517,763` |  |  |
| 2025 | wages | £255,811,000 | high | — | notes | `Staff costs 255,811 221,929` |  |  |
| 2025 | player_amortisation | £141,851,000 | medium | — | notes | `Amortisation of intangible fixed assets 141,851 136,287` |  |  |
| 2025 | profit_on_disposal | — | none | — | — | `—` |  |  |

_Context — profit on disposal of **player registrations**. Not one of the four tracked items (see DECISIONS.md), shown so the tracked non-player disposal figure above can be checked against it._

| year | player disposal profit | source row |
|---|---|---|
| 2023 | £15,510,000 | `Profit on disposal of intangible fixed assets 6 - 15,510 15,510 - 19,150 19,150` |
| 2024 | £82,305,000 | `Profit on disposal of intangible fixed assets 6 : 82,305 82,305 - 15,510 15,510` |
| 2025 | £52,565,000 | `Profit on disposal of intangible fixed assets 6 - 52,565 52,565 - 82,305 82,305` |

## west-ham

| year | item | value | conf | cross-check vs next year | section | source row | verified? | corrected_value |
|---|---|---|---|---|---|---|---|---|
| 2023 | revenue | £236,656,000 | medium | ok | profit_and_loss | `Group turnover 3 236,656 - 236,656 252,720 - 252,720` |  |  |
| 2023 | wages | £136,844,000 | medium | — | notes | `derived total staff costs: 118,823 + 17,726 + 295 = 136,844` |  |  |
| 2023 | player_amortisation | £65,306,000 | medium | ok | notes | `Amortisation of intangible fixed assets 65,306 48,825` |  |  |
| 2023 | profit_on_disposal | — | none | — | — | `—` |  |  |
| 2024 | revenue | £269,740,000 | medium | ok | profit_and_loss | `Group turnover 3 269,740 - 269,740 236,656 - 236,656` |  |  |
| 2024 | wages | £160,969,000 | medium | — | notes | `derived total staff costs: 140,747 + 19,917 + 305 = 160,969` |  |  |
| 2024 | player_amortisation | £83,489,000 | medium | — | notes | `Amortisation of intangible fixed assets 83,489 65,306` |  |  |
| 2024 | profit_on_disposal | — | none | — | — | `—` |  |  |
| 2025 | revenue | £227,552,000 | medium | — | profit_and_loss | `Group turnover 3 227,552 - 227,552 269,740 - 269,740` |  |  |
| 2025 | wages | £175,893,000 | medium | — | notes | `derived total staff costs: 152,926 + 22,638 + 329 = 175,893` |  |  |
| 2025 | player_amortisation | £103,287,000 | medium | — | notes | `Amortisation of intangible fixed assets (99,408) (3,879) (103,287)` |  |  |
| 2025 | profit_on_disposal | — | none | — | — | `—` |  |  |

_Context — profit on disposal of **player registrations**. Not one of the four tracked items (see DECISIONS.md), shown so the tracked non-player disposal figure above can be checked against it._

| year | player disposal profit | source row |
|---|---|---|
| 2023 | £16,980,000 | `Profit on disposal of players - 16,980 16,980 - 709 709` |
| 2024 | £96,313,000 | `Profit on disposal of players - 96,313 96,313 - 16,980 16,980` |
| 2025 | £19,954,000 | `Profit on disposal of players - 19,954 19,954 - 96,313 96,313` |

