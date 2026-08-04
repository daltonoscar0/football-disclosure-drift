# Line-item validation

Every extracted value with the exact filing row it came from. Fill in the
`verified?` column with `y` or `n`; where the value is wrong put the correct
figure in `corrected_value` **in pounds** (not thousands).

`confidence` is the extractor's own assessment: `high` = unambiguous label
matched in the expected section with an explicit unit marker; `medium` = a
fallback label or a document-level unit inference; `low` = unit assumed or
the row had no comparative column; `none` = nothing matched.

## arsenal

| year | item | value | conf | section | source row | verified? | corrected_value |
|---|---|---|---|---|---|---|---|
| 2023 | revenue | £467,155,000 | medium | profit_and_loss | `Turnover of the Group including its share of joint ventures 465,698 1,457 467,155 370,384 1,978 372,362` |  |  |
| 2023 | wages | £234,766,000 | low | notes | `Staff costs 234,766 212,345` |  |  |
| 2023 | player_amortisation | £139,060,000 | high | notes | `Amortisation of player registrations 139,060 124,567` |  |  |
| 2023 | profit_on_disposal | — | none | — | `—` |  |  |
| 2024 | revenue | £617,167,000 | medium | profit_and_loss | `Turnover of the Group including its share of joint ventures 615,793 1,374 617,167 465,698 1,457 467,155` |  |  |
| 2024 | wages | £286,960,000 | low | notes | `Wages and salaries _ 286,960 204,648` |  |  |
| 2024 | player_amortisation | £171,099,000 | high | notes | `Amortisation of player registrations . 171,099 139,060` |  |  |
| 2024 | profit_on_disposal | — | none | — | `—` |  |  |
| 2025 | revenue | £692,026,000 | medium | profit_and_loss | `Turnover of the Group including its share of joint ventures 691,572 454 692,026 615,793 1,374 617,167` |  |  |
| 2025 | wages | £346,804,000 | medium | notes | `Staff costs 346,804 327,822` |  |  |
| 2025 | player_amortisation | £171,627,000 | high | notes | `Amortisation of player registrations . 171,627 171,099` |  |  |
| 2025 | profit_on_disposal | £-19,000 | medium | notes | `Profit on disposal of fixed assets (19)` |  |  |

_Context — profit on disposal of **player registrations**. Not one of the four tracked items (see DECISIONS.md), shown so the tracked non-player disposal figure above can be checked against it._

| year | player disposal profit | source row |
|---|---|---|
| 2023 | £10,732,000 | `Profit on disposal of player registrations - 10,732 10,732 - 22,238 22,238` |
| 2024 | £51,073,000 | `Profit on disposal of player registrations - 51,073 51,073 - 10,732 10,732` |
| 2025 | £81,237,000 | `Profit on disposal of player registrations - 81,237 81,237 - 51,073 51,073` |

## chelsea

| year | item | value | conf | section | source row | verified? | corrected_value |
|---|---|---|---|---|---|---|---|
| 2023 | revenue | £512,467,000 | medium | profit_and_loss | `Turnover se 3 512,467 - 512,467 481,278` |  |  |
| 2023 | wages | £352,355,000 | high | notes | `Wages and salaries 352,355 297,569` |  |  |
| 2023 | player_amortisation | £205,000,000 | medium | notes | `Amortisation charged for the year 1,750 203,250 205,000` |  |  |
| 2023 | profit_on_disposal | £76,524,000 | medium | profit_and_loss | `Profit on disposal of fixed assets 76,524 - 76,524 -` |  |  |
| 2024 | revenue | £468,486,000 | medium | profit_and_loss | `Turnover 3 468,486 - 468,486 512,467` |  |  |
| 2024 | wages | £294,629,000 | high | notes | `Wages and salaries 294,629 352,355` |  |  |
| 2024 | player_amortisation | £191,826,000 | medium | notes | `Amortisation charged for the year 1,770 190,056 191,826` |  |  |
| 2024 | profit_on_disposal | £198,749,000 | low | profit_and_loss | `Profit on disposal of fixed assets investments 17 198,749 - 198,749 -` |  |  |
| 2025 | revenue | £490,857,000 | medium | profit_and_loss | `Turnover 3 490,857 - 490,857 468,486` |  |  |
| 2025 | wages | — | none | — | `—` |  |  |
| 2025 | player_amortisation | £213,893,000 | medium | notes | `Amortisation charged for the year 1,646 212,247 213,893` |  |  |
| 2025 | profit_on_disposal | £0 | medium | profit_and_loss | `Profit on disposal of fixed asset investments 16 - - - 198,749` |  |  |

_Context — profit on disposal of **player registrations**. Not one of the four tracked items (see DECISIONS.md), shown so the tracked non-player disposal figure above can be checked against it._

| year | player disposal profit | source row |
|---|---|---|
| 2023 | £62,861,000 | `Profit on disposal of player registrations - 62,861 62,861 123,213` |
| 2024 | £152,463,000 | `Profit on disposal of player registrations - 152,463 152,463 62,861` |
| 2025 | £57,906,000 | `Profit on disposal of player registrations - 57,906 57,906 152,463` |

## everton

| year | item | value | conf | section | source row | verified? | corrected_value |
|---|---|---|---|---|---|---|---|
| 2023 | revenue | £7,215,000 | medium | profit_and_loss | `Turnover 2 7215S - 172,A55, 181,007 - 181,007` |  |  |
| 2023 | wages | £138,394,000 | high | notes | `Wages and salaries 138,394 141,390` |  |  |
| 2023 | player_amortisation | £77,621,000 | high | notes | `Amortisation of players’ registrations 77621 68,327` |  |  |
| 2023 | profit_on_disposal | £0 | low | profit_and_loss | `Profit on disposal of tangible . -` |  |  |
| 2024 | revenue | £186,902,000 | low | profit_and_loss | `Turnover 186,902 - 186,902 172,155 : 172,155` |  |  |
| 2024 | wages | £137,086,000 | high | notes | `Wages and salaries 137,086 138,394` |  |  |
| 2024 | player_amortisation | £64,581,000 | high | notes | `Amortisation of players’ registrations 64,581 77621` |  |  |
| 2024 | profit_on_disposal | £0 | low | profit_and_loss | `Profit on disposal of tangible . -` |  |  |
| 2025 | revenue | £196,697,000 | medium | profit_and_loss | `Turnover 196,697 : + 196,697 » 3186,902 - 186,902` |  |  |
| 2025 | wages | £132,430,000 | high | notes | `Wages and salaries 132,430 137,086.` |  |  |
| 2025 | player_amortisation | £50,901,000 | high | notes | `Amortisation of players’ registrations 50,901 64,581` |  |  |
| 2025 | profit_on_disposal | £0 | low | profit_and_loss | `Profit on disposal of tangible fixed assets 4 - 4 4 4` |  |  |

_Context — profit on disposal of **player registrations**. Not one of the four tracked items (see DECISIONS.md), shown so the tracked non-player disposal figure above can be checked against it._

| year | player disposal profit | source row |
|---|---|---|
| 2023 | £47,518,000 | `Profit on player trading - 47518 47,518 - 67,684 67,684` |
| 2024 | £48,545,000 | `Profit on player trading - 48,545 48,545 - 47518 47,518` |
| 2025 | £31,325,000 | `Profit on player trading : 31,325 31,325 - 48,545 48,545` |

## tottenham

| year | item | value | conf | section | source row | verified? | corrected_value |
|---|---|---|---|---|---|---|---|
| 2023 | revenue | £49,633,000 | medium | profit_and_loss | `Revenue 2 $49,633 - $49,633 443,415 - 443,415` |  |  |
| 2023 | wages | £251,121,000 | medium | notes | `Staff costs S) 251,121 209,180` |  |  |
| 2023 | player_amortisation | £109,073,000 | medium | notes | `Amortisation of intangible fixed assets 109,073 79,520` |  |  |
| 2023 | profit_on_disposal | £0 | low | notes | `Profit on disposal of property, plant and equipment (25) -` |  |  |
| 2024 | revenue | £517,763,000 | low | profit_and_loss | `Revenue 2 517,763 - 517,763 549,633 - $49,633` |  |  |
| 2024 | wages | £221,929,000 | medium | notes | `Staff costs 221,929 251,121` |  |  |
| 2024 | player_amortisation | £136,287,000 | medium | notes | `Amortisation of intangible fixed assets 136,287 109,073` |  |  |
| 2024 | profit_on_disposal | £82,305,000 | medium | profit_and_loss | `Profit on disposal of intangible fixed assets 6 : 82,305 82,305 - 15,510 15,510` |  |  |
| 2025 | revenue | £564,881,000 | medium | profit_and_loss | `Revenue 2 564,881 - $64,881 517,763 - 517,763` |  |  |
| 2025 | wages | £255,811,000 | medium | notes | `Staff costs 255,811 221,929` |  |  |
| 2025 | player_amortisation | £141,851,000 | medium | notes | `Amortisation of intangible fixed assets 141,851 136,287` |  |  |
| 2025 | profit_on_disposal | £52,565,000 | medium | profit_and_loss | `Profit on disposal of intangible fixed assets 6 - 52,565 52,565 - 82,305 82,305` |  |  |

_Context — profit on disposal of **player registrations**. Not one of the four tracked items (see DECISIONS.md), shown so the tracked non-player disposal figure above can be checked against it._

| year | player disposal profit | source row |
|---|---|---|
| 2023 | — | `—` |
| 2024 | — | `—` |
| 2025 | — | `—` |

## west-ham

| year | item | value | conf | section | source row | verified? | corrected_value |
|---|---|---|---|---|---|---|---|
| 2023 | revenue | £236,656,000 | medium | profit_and_loss | `Group turnover 3 236,656 - 236,656 252,720 - 252,720` |  |  |
| 2023 | wages | £118,823,000 | high | notes | `Wages and salaries 118,823 118,709` |  |  |
| 2023 | player_amortisation | £65,306,000 | medium | notes | `Amortisation of intangible fixed assets 65,306 48,825` |  |  |
| 2023 | profit_on_disposal | — | none | — | `—` |  |  |
| 2024 | revenue | £269,740,000 | medium | profit_and_loss | `Group turnover 3 269,740 - 269,740 236,656 - 236,656` |  |  |
| 2024 | wages | £140,747,000 | high | notes | `Wages and salaries 140,747 118,823` |  |  |
| 2024 | player_amortisation | £83,489,000 | medium | notes | `Amortisation of intangible fixed assets 83,489 65,306` |  |  |
| 2024 | profit_on_disposal | — | none | — | `—` |  |  |
| 2025 | revenue | £227,552,000 | medium | profit_and_loss | `Group turnover 3 227,552 - 227,552 269,740 - 269,740` |  |  |
| 2025 | wages | £152,926,000 | high | notes | `Wages and salaries 152,926 140,747` |  |  |
| 2025 | player_amortisation | £103,287,000 | medium | notes | `Amortisation of intangible fixed assets (99,408) (3,879) (103,287)` |  |  |
| 2025 | profit_on_disposal | — | none | — | `—` |  |  |

_Context — profit on disposal of **player registrations**. Not one of the four tracked items (see DECISIONS.md), shown so the tracked non-player disposal figure above can be checked against it._

| year | player disposal profit | source row |
|---|---|---|
| 2023 | £16,980,000 | `Profit on disposal of players - 16,980 16,980 - 709 709` |
| 2024 | £96,313,000 | `Profit on disposal of players - 96,313 96,313 - 16,980 16,980` |
| 2025 | £19,954,000 | `Profit on disposal of players - 19,954 19,954 - 96,313 96,313` |

