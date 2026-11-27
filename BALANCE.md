# Fake balance (dry run, no broker, no real money)

Updated 2026-11-27 19:37 UTC

| | |
|---|---|
| Start | $100.00 (2026-11-13) |
| Balance | **$101.02** |
| P&L | **+1.02 (+1.02%)** |
| Trades closed | 11 (4 won, 7 lost, 0 flat) |
| Open now | none |

## By day

| Day | Trades | P&L | Balance after |
|---|---|---|---|
| 2026-11-13 | 1 | +8.44 | $108.44 |
| 2026-11-16 | 1 | +8.95 | $117.39 |
| 2026-11-17 | 1 | +7.96 | $125.35 |
| 2026-11-18 | 2 | -9.55 | $115.80 |
| 2026-11-19 | 1 | +6.68 | $122.48 |
| 2026-11-20 | 1 | -4.37 | $118.11 |
| 2026-11-23 | 1 | -4.39 | $113.72 |
| 2026-11-24 | 1 | -5.01 | $108.71 |
| 2026-11-25 | 1 | -4.25 | $104.46 |
| 2026-11-27 | 1 | -3.44 | $101.02 |

## Trades

| Day | Instrument | Qty | Entry | Stop | Target | Exit | Why | P&L | Time Machine said |
|---|---|---|---|---|---|---|---|---|---|
| 2026-11-13 09:50 | US Tech 100 SHORT | 0.03 | 28155.50 | 28297.38 | 27871.74 | 27871.74 | target | +8.44 | n/a (short) |
| 2026-11-16 10:00 | US 500 SHORT | 0.26 | 7505.00 | 7522.50 | 7470.00 | 7470.0 | target | +8.95 | n/a (short) |
| 2026-11-17 10:10 | US Tech 100 SHORT | 0.04 | 27175.50 | 27276.00 | 26974.50 | 26974.5 | target | +7.96 | n/a (short) |
| 2026-11-18 09:50 | US 500 SHORT | 0.16 | 7335.25 | 7364.50 | 7276.75 | 7364.5 | stop | -4.77 | n/a (short) |
| 2026-11-18 11:20 | US Tech 100 SHORT | 0.03 | 27003.50 | 27161.25 | 26688.00 | 27161.25 | stop | -4.78 | n/a (short) |
| 2026-11-19 10:15 | US Tech 100 SHORT | 0.02 | 27565.00 | 27733.13 | 27228.74 | 27228.74 | target | +6.68 | n/a (short) |
| 2026-11-20 09:55 | US Tech 100 | 0.03 | 26364.00 | 26219.87 | 26652.26 | 26219.87 | stop | -4.37 | Leans toward the stop: at 2R the target has to come first in 33 % of the replays that hit  |
| 2026-11-23 10:25 | US 500 | 0.06 | 7296.75 | 7224.37 | 7441.51 | 7224.37 | stop | -4.39 | Strongly toward the stop: at 2R the target has to come first in 33 % of the replays that h |
| 2026-11-24 09:50 | US 500 | 0.16 | 7211.75 | 7181.00 | 7273.25 | 7181.0 | stop | -5.01 | Strongly toward the stop: at 2R the target has to come first in 33 % of the replays that h |
| 2026-11-25 10:00 | US Tech 100 | 0.02 | 25459.75 | 25249.25 | 25880.75 | 25249.25 | stop | -4.25 | Strongly toward the stop: at 2R the target has to come first in 33 % of the replays that h |
| 2026-11-27 10:00 | US Tech 100 SHORT | 0.02 | 26254.00 | 26424.13 | 25913.74 | 26424.13 | stop | -3.44 | n/a (short) |

Fills are simulated at the trigger price; stops and targets are played out on
5-minute bars (stop first when one bar touches both). CFD costs as in Trading 212's Index CFD
costs: average spread US Tech 100 1.12 pt, US 500 0.42 pt (T212 instrument list), FX fee 0.5%
of each result (USD to EUR), 20:1 leverage; closed by 15:55 NY so no overnight fee.
Long and short: the first opening-range breakout of the day, up or down.
Stock trades before the switch paid no fees.
