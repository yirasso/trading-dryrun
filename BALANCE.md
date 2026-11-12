# Fake balance (dry run, no broker, no real money)

Updated 2026-11-12 21:37 UTC

| | |
|---|---|
| Start | $100.00 (2026-11-11) |
| Balance | **$99.19** |
| P&L | **-0.81 (-0.81%)** |
| Trades closed | 3 (1 won, 2 lost, 0 flat) |
| Open now | none |

## By day

| Day | Trades | P&L | Balance after |
|---|---|---|---|
| 2026-11-11 | 1 | -0.04 | $99.96 |
| 2026-11-12 | 2 | -0.77 | $99.19 |

## Trades

| Day | Stock | Qty | Entry | Stop | Target | Exit | Why | P&L | Time Machine said |
|---|---|---|---|---|---|---|---|---|---|
| 2026-11-11 09:50 | AFRM | 1 | 67.57 | 66.58 | 69.55 | 67.53 | flat by close | -0.04 | Leans toward the stop: at 2R the target has to come first in 33 % of the replays that hit  |
| 2026-11-12 09:50 | APLD | 5 | 17.11 | 16.80 | 17.73 | 16.8 | stop | -1.55 | Leans toward the stop: at 2R the target has to come first in 33 % of the replays that hit  |
| 2026-11-12 10:00 | DVN | 1 | 45.47 | 45.08 | 46.25 | 46.25 | target | +0.78 | Leans toward the stop: at 2R the target has to come first in 33 % of the replays that hit  |

Fills are simulated at the trigger price; stops and targets are played out on
5-minute bars (stop first when one bar touches both). No slippage, no fees.
