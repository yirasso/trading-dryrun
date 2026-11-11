# Dry-run paper trader

Runs the [day-trader-skill](https://github.com/Jakeschincariol/day-trader-skill) tools on a
schedule (GitHub Actions, weekdays 11:00–21:10 Lisbon) with **no broker and no real money**.

- Strategy: the pack's defaults. 15-minute opening-range breakout on 5-minute bars, stop at the
  range midpoint, target 2R, flat by 15:55 NY, max 3 trades a day, max $50 loss a trade,
  $5,000 fake budget (`trader/config.json`).
- Each trade goes through trader-entry → trader-exit → trader-timemachine → trader-budget →
  trader-risk → trader-broker ticket. Only a risk PASS is "filled", on paper, at the trigger
  price; the bracket is then played out on Yahoo 5-minute bars.
- **[BALANCE.md](BALANCE.md)**: the fake balance, P&L by day and every trade.
- `journal/YYYY-MM-DD.md`: what each step printed. `ledger.json`: the raw trades.

Limits: fills at the trigger price with no slippage or fees, stop first when one bar touches
both stop and target, free delayed Yahoo data. A real account will do somewhat worse.

Run by hand: `python runner.py` (with `DTS_DIR` pointing at a day-trader-skill checkout), or
"Run workflow" in the Actions tab.
