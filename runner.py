"""Dry-run paper trader for the day-trader-skill pack.

Runs the pack's own tools in order (scanner -> entry -> exit -> timemachine ->
budget -> risk -> broker ticket) and stands in for the broker: no order is
sent anywhere. A trade that passes trader-risk is "filled" on paper at the
trigger price, and its bracket (stop / target / flat by 15:55 NY) is played
out on Yahoo's 5-minute bars. The fake balance lives in ledger.json and
BALANCE.md.

Safe to run as often as you like: each run only does what the New York clock
calls for and what has not been done yet today.
"""
import datetime as dt
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)
SKILLS = os.environ.get("DTS_DIR") or (
    "skills" if os.path.isdir("skills") else os.path.join("..", "day-trader-skill"))
PY = sys.executable
LEDGER = "ledger.json"
CONFIG = "trader/config.json"
ENTRY_FROM, ENTRY_UNTIL = "09:50", "15:30"   # ORB needs the 15-min range; no entries after 15:30
FLAT_BY = "15:55"
MAX_CANDIDATES = 6                            # hits to try per run before giving up


# ------------------------------------------------------------------ helpers
def tool(name, *args, check=False):
    path = os.path.join(SKILLS, name)
    p = subprocess.run([PY, path, *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=900)
    out = (p.stdout + p.stderr).strip()
    if check and p.returncode not in (0, 1):
        raise RuntimeError("%s failed (%s): %s" % (name, p.returncode, out[-800:]))
    return p.returncode, out


def jload(path, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def jsave(path, obj):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2)
        fh.write("\n")


def hm(text):
    """'12:00 PM' or '11:55' -> minutes after midnight."""
    text = text.strip()
    ampm = None
    if text[-2:].upper() in ("AM", "PM"):
        ampm, text = text[-2:].upper(), text[:-2].strip()
    h, m = (int(x) for x in text.split(":")[:2])
    if ampm == "PM" and h != 12:
        h += 12
    if ampm == "AM" and h == 12:
        h = 0
    return h * 60 + m


def fmt(minutes):
    return "%02d:%02d" % divmod(minutes, 60)


def log(msg):
    print(msg, flush=True)
    LOG.append(msg)


LOG = []
SCANNED = []


def journal(date, title, body=""):
    os.makedirs("journal", exist_ok=True)
    with open(os.path.join("journal", date + ".md"), "a", encoding="utf-8") as fh:
        fh.write("\n## %s\n" % title)
        if body:
            fh.write("\n```\n%s\n```\n" % body.strip())


def bars_5m(symbol, date):
    """Today's regular-session 5-minute bars: [(start_min_NY, o, h, l, c)]."""
    url = "https://query2.finance.yahoo.com/v8/finance/chart/%s?interval=5m&range=5d" % urllib.parse.quote(symbol)
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (dry-run paper trader)"})
            with urllib.request.urlopen(req, timeout=30) as r:
                res = json.load(r)["chart"]["result"][0]
            break
        except Exception:
            if attempt == 2:
                raise
            time.sleep(5)
            url = url.replace("query2", "query1")
    off = res["meta"].get("gmtoffset", -18000)
    q = res["indicators"]["quote"][0]
    out = []
    for i, ts in enumerate(res.get("timestamp") or []):
        t = dt.datetime.fromtimestamp(ts + off, dt.timezone.utc)
        if t.strftime("%Y-%m-%d") != date:
            continue
        vals = [q[k][i] for k in ("open", "high", "low", "close")]
        if None in vals or t.second or t.minute % 5:
            continue
        out.append((t.hour * 60 + t.minute, *vals))
    return out


# ------------------------------------------------------------------ ledger
def load_ledger(cfg):
    led = jload(LEDGER)
    if led is None:
        led = {"start_balance": float(cfg.get("budget", 5000)),
               "started": None, "trades": [], "days": {}}
    return led


def balance(led):
    return round(led["start_balance"] + sum(t.get("pnl") or 0 for t in led["trades"]
                                             if t["status"] == "closed"), 2)


def day(led, date):
    return led["days"].setdefault(date, {"premarket": False, "summary": False, "scans": 0})


# ------------------------------------------------------------------ exits
def settle(trade, date, now_min, closes_min, final=False):
    """Play the bracket out on 5-minute bars after the entry bar."""
    bars = bars_5m(trade["symbol"], date)
    flat = min(hm(FLAT_BY), closes_min - 5)
    entry_bar = hm(trade["entry_bar"])
    last_close = None
    for start, o, h, l, c in bars:
        if start <= entry_bar or start + 5 > now_min:
            continue
        if start >= flat:
            break
        last_close = (start, c)
        if l <= trade["stop"]:                      # stop first if both in one bar
            return "stop", round(min(trade["stop"], o), 2), fmt(start + 5)
        if h >= trade["target"]:
            return "target", round(max(trade["target"], o), 2), fmt(start + 5)
    if now_min >= flat or final:
        if last_close:
            return "flat by close", round(last_close[1], 2), fmt(last_close[0] + 5)
        return "flat by close", trade["entry"], fmt(flat)   # no bars after entry
    return None


def close_trade(trade, outcome, cfg, date):
    reason, price, at = outcome
    if trade.get("kind") == "cfd":                  # no broker tool: the spread was the cost
        gross = (price - trade["entry"]) * trade["qty"] - trade["spread_cost"]
        fx = round(abs(gross) * float(cfg.get("fx_fee_pct", 0)) / 100, 2)   # T212: 0.5% of the result
        trade["fx_fee"] = fx
        out = "CFD %s: sold %s units at %.2f (mid); spread cost %.2f, FX fee %.2f" % (
            trade["name"], q(trade["qty"]), price, trade["spread_cost"], fx)
        pnl = gross - fx
    else:
        rc, out = tool("trader-broker/ticket.py", "fill", "--symbol", trade["symbol"], "--side", "sell",
                       "--qty", str(trade["qty"]), "--price", "%.2f" % price, "--date", date)
        pnl = (price - trade["entry"]) * trade["qty"]
    trade.update(status="closed", exit=price, exit_time=at, exit_reason=reason, pnl=round(pnl, 2))
    log("CLOSED %s %s x%s at %.2f (%s %s): P&L %+.2f" % (
        date, label(trade), q(trade["qty"]), price, reason, at, trade["pnl"]))
    journal(date, "Exit %s %s at %s: %s, P&L %+.2f" % (label(trade), reason, at, price, trade["pnl"]), out)


def manage_open(led, cfg, date, now_min, closes_min, final=False):
    for t in led["trades"]:
        if t["status"] != "open":
            continue
        if t["date"] != date:                       # left open by a missed run: play out its own day
            outcome = settle(t, t["date"], 24 * 60, 16 * 60, final=True)
        else:
            outcome = settle(t, date, now_min, closes_min, final)
        if outcome:
            close_trade(t, outcome, cfg, t["date"])


# ------------------------------------------------------------------ affordable universe
AFFORDABLE = "trader/universe-affordable.txt"
MIN_PRICE, MIN_VOLUME = 5.0, 500_000


def max_price(cfg, led):
    """The most one whole share may cost: the position cap, the order cap, or the cash after
    the buffer, whichever is smallest (the same limits trader-budget sizes with)."""
    budget = float(cfg.get("budget", 100))
    cash = jload("trader/portfolio.json", {}).get("cash", balance(led))
    return min(budget * float(cfg.get("max_position_pct", 90)) / 100,
               float(cfg.get("max_order_usd", budget)),
               cash - budget * float(cfg.get("cash_buffer_pct", 10)) / 100)


def build_affordable(led, cfg, date):
    """Once a day: liquid stocks a whole share of which fits the budget (Yahoo spark, 20 a request)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("scan", os.path.join(SKILLS, "trader-scanner", "scan.py"))
    scan = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scan)
    syms = [l.split("|")[0] for l in open("trader/universe.txt", encoding="utf-8") if l.strip()]
    data, failed = scan.fetch_spark(syms, "5d", "1d", 0.3)
    top = max_price(cfg, led)
    keep = []
    for s, ser in data.items():
        meta = ser.get("meta") or {}
        p, v = meta.get("regularMarketPrice"), meta.get("regularMarketVolume") or 0
        if p and MIN_PRICE <= p <= top and v >= MIN_VOLUME:
            keep.append("%s|" % s)
    with open(AFFORDABLE, "w", encoding="utf-8") as fh:
        fh.write("\n".join(sorted(keep)) + "\n")
    led["affordable_date"] = date
    log("Affordable universe: %d of %d stocks between $%.0f and $%.2f with volume >= %d (%d failed)."
        % (len(keep), len(syms), MIN_PRICE, top, MIN_VOLUME, len(failed)))
    journal(date, "Affordable universe: %d stocks priced $%.0f-$%.2f" % (len(keep), MIN_PRICE, top))


# ------------------------------------------------------------------ CFD mode
def q(x):
    return ("%.2f" % x).rstrip("0").rstrip(".") if isinstance(x, float) else str(x)


def label(t):
    return t.get("name") or t["symbol"]


def cfd_mode(cfg):
    return cfg.get("mode") == "cfd"


def cfd_signals(cfg, date, traded):
    """trader-entry on each instrument: [(trigger_minute, sym, entry_doc_path, output)]; an
    instrument whose setup expired today is reported with trigger None."""
    out_list = []
    for sym in cfg["instruments"]:
        if sym in traded:
            continue
        path = "trader/entry-%s.json" % sym.replace("^", "").replace("=", "")
        if os.path.exists(path):
            os.remove(path)
        rc, out = tool("trader-entry/entry.py", "check", sym, "--write", path)
        ent = jload(path, {})
        if ent.get("status") == "triggered" and ent.get("date") == date:
            out_list.append((hm(ent["bar_start"]) + 5, sym, path, out))
        elif ent.get("status") == "expired":
            out_list.append((None, sym, path, out))
    return out_list


def open_cfd(led, cfg, date, sym, path, out):
    """Index CFD, like Trading 212's US 500 / US Tech 100: fractional units, leverage, a spread.
    The pack's trader-budget / trader-risk / trader-broker are built for whole shares on Alpaca,
    so the same limits are applied here instead."""
    inst = cfg["instruments"][sym]
    name = inst["name"]
    ent = jload(path, {})
    trig = hm(ent["bar_start"]) + 5
    N = "%s %s" % (date, fmt(trig))
    rc, out_exit = tool("trader-exit/exit.py", "plan", "--from", path, "--write", "--now", N)
    if rc != 0:
        return skip(led, date, sym, "exit plan refused", out_exit)
    _, out_tm = tool("trader-timemachine/timemachine.py", "run", "--write", "--until", FLAT_BY, "--now", N)
    tm = jload("trader/timemachine.json", {})
    plan = jload("trader/plan.json", {})
    entry, stop, target = float(plan["entry"]), float(plan["stop"]), float(plan["target"])
    spread = float(inst.get("spread", 0))
    bal = balance(led)
    usable = bal * (1 - float(cfg.get("cash_buffer_pct", 10)) / 100)
    lev = float(cfg.get("leverage", 20))
    max_loss = float(cfg["max_loss_per_trade_usd"])
    by_risk = max_loss / (entry - stop + spread)            # loss at the stop, spread included
    by_margin = usable * lev / entry                         # margin = notional / leverage
    qty = int(min(by_risk, by_margin) * 100) / 100.0         # 0.01-unit steps
    today = [t for t in led["trades"] if t["date"] == date]
    lost_today = -sum(min(t.get("pnl") or 0, 0) for t in today)
    worst = round(qty * (entry - stop + spread), 2)
    checks = [
        (hm(cfg.get("no_entries_before", "09:45")) <= trig <= hm(cfg.get("no_entries_after", "15:30")),
         "outside the entry window"),
        ((target - entry) / (entry - stop) >= float(cfg.get("min_reward_risk", 1)), "reward:risk too low"),
        (qty >= 0.01, "too small: under 0.01 units"),
        (lost_today + worst <= float(cfg.get("max_daily_loss_usd", 15)), "daily loss limit"),
    ]
    why = "\n".join("BLOCK: " + m for ok, m in checks if not ok)
    sizing = ("%s: %s units at %.2f (notional $%.2f, margin $%.2f at %g:1).\n"
              "Limits: risk $%.2f / (%.2f stop distance + %.2f spread) = %.2f units; "
              "margin $%.2f x %g / %.2f = %.2f units.\nLoss at the stop about $%.2f, spread cost $%.2f."
              % (name, q(qty), entry, qty * entry, qty * entry / lev, lev, max_loss, entry - stop, spread,
                 by_risk, usable, lev, entry, by_margin, worst, qty * spread))
    if why:
        return skip(led, date, sym, why.replace("BLOCK: ", ""), sizing + "\n" + why)
    trade = {"id": "DRYRUN-%s-%s-%s" % (date, sym, fmt(trig).replace(":", "")), "kind": "cfd",
             "name": name, "date": date, "symbol": sym, "qty": qty, "entry": entry,
             "entry_time": fmt(trig), "entry_bar": ent["bar_start"], "stop": stop, "target": target,
             "max_loss": worst, "spread_cost": round(qty * spread, 2),
             "timemachine": tm.get("verdict"), "status": "open"}
    led["trades"].append(trade)
    log("OPEN %s %s x%s at %.2f (%s), stop %.2f, target %.2f" % (
        date, name, q(qty), entry, fmt(trig), stop, target))
    journal(date, "Entry %s (CFD) x%s at %.2f (%s ET)" % (name, q(qty), entry, fmt(trig)),
            "\n\n".join([out, out_exit, out_tm, sizing]))
    return True


# ------------------------------------------------------------------ entries
def try_entries(led, cfg, date, now_min):
    max_trades = int(cfg.get("max_trades_per_day", 3))
    today = [t for t in led["trades"] if t["date"] == date]
    if len(today) >= max_trades or any(t["status"] == "open" for t in led["trades"]):
        return
    if cfd_mode(cfg):
        after = max([hm(t["exit_time"]) for t in today if t.get("exit_time")] or [0])
        traded = {t["symbol"] for t in today} | set(day(led, date).get("skipped", []))
        sigs = cfd_signals(cfg, date, traded)
        for trig, sym, path, out in sorted(sigs, key=lambda s: s[0] or 9999):
            if trig is None:
                skip(led, date, sym, "no breakout before the entry window closed", out)
            elif trig <= after:     # its first breakout came while another trade was open
                skip(led, date, sym, "breakout at %s, while another trade was open" % fmt(trig), out)
            elif open_cfd(led, cfg, date, sym, path, out):
                return True
        return False
    if led.get("affordable_date") != date or not os.path.exists(AFFORDABLE):
        build_affordable(led, cfg, date)
    if not SCANNED:                                   # one ORB scan per run, reused after an exit
        rc, out = tool("trader-scanner/scan.py", "orb", "--universe", AFFORDABLE,
                       "--max-confirm", "80", "--quiet")
        day(led, date)["scans"] += 1
        SCANNED.append(out)
    out = SCANNED[0]
    wl = jload("trader/watchlist.json", {})
    if not str(wl.get("as_of", "")).startswith(date):
        log("ORB scan: no hits today. " + out.splitlines()[-1] if out else "")
        return
    hits = sorted(wl.get("hits") or [], key=lambda h: hm(h.get("bar_start", "23:59")))
    after = max([hm(t["exit_time"]) for t in today if t.get("exit_time")] or [0])
    traded = {t["symbol"] for t in today} | set(day(led, date).get("skipped", []))
    top = max_price(cfg, led)
    cands = [h for h in hits if h["symbol"] not in traded and hm(h["bar_start"]) + 5 > after
             and hm(h["bar_start"]) + 5 <= hm(ENTRY_UNTIL) and float(h.get("price") or 0) <= top]
    log("ORB scan: %d hits, %d new candidates after %s." % (len(hits), len(cands), fmt(after)))
    for h in cands[:MAX_CANDIDATES]:
        if open_trade(led, cfg, date, h["symbol"], now_min):
            return True
    return False


def skip(led, date, sym, why, out=""):
    day(led, date).setdefault("skipped", []).append(sym)
    log("skip %s: %s" % (sym, why))
    journal(date, "Skipped %s: %s" % (sym, why), out[-3000:])


def open_trade(led, cfg, date, sym, now_min):
    rc, out = tool("trader-entry/entry.py", "check", sym, "--write")
    ent = jload("trader/entry.json", {})
    if rc != 0 or ent.get("status") != "triggered" or ent.get("symbol") != sym:
        return skip(led, date, sym, "entry not triggered", out)
    trig = hm(ent["bar_start"]) + 5
    N = "%s %s" % (date, fmt(trig))
    rc, out_exit = tool("trader-exit/exit.py", "plan", "--write", "--now", N)
    if rc != 0:
        return skip(led, date, sym, "exit plan refused", out_exit)
    _, out_tm = tool("trader-timemachine/timemachine.py", "run", "--write", "--until", FLAT_BY, "--now", N)
    tm = jload("trader/timemachine.json", {})
    rc, out_size = tool("trader-budget/size.py", "--write", "--now", N)
    if rc != 0:
        return skip(led, date, sym, "budget refused", out_size)
    rc, out_risk = tool("trader-risk/check.py", "--now", N)
    if rc != 0:
        return skip(led, date, sym, "risk BLOCK", out_risk)
    order = (jload("trader/orders.json", {}).get("orders") or [None])[0]
    plan = jload("trader/plan.json", {})
    if not order:
        return skip(led, date, sym, "no order written", out_size)
    qty = int(float(order["qty"]))
    entry = float(plan["entry"])
    _, out_t = tool("trader-broker/ticket.py", "show", "--now", N)
    tool("trader-broker/ticket.py", "approve", "--index", "1", "--reply", "yes", "--now", N)
    bid = "DRYRUN-%s-%s-%s" % (date, sym, fmt(trig).replace(":", ""))
    _, out_res = tool("trader-broker/ticket.py", "result", "--index", "1", "--status", "placed",
                      "--broker-id", bid, "--filled-qty", str(qty), "--filled-price", "%.2f" % entry,
                      "--now", N, "--note", "dry run: no broker, paper fill at the trigger price")
    _, out_news = tool("trader-news/news.py", "--tickers", sym, "--hours", "16", "--no-sec", "--all")
    trade = {"id": bid, "date": date, "symbol": sym, "qty": qty, "entry": entry,
             "entry_time": fmt(trig), "entry_bar": ent["bar_start"],
             "stop": float(plan["stop"]), "target": float(plan["target"]),
             "max_loss": round((entry - float(plan["stop"])) * qty, 2),
             "timemachine": tm.get("verdict"), "status": "open"}
    led["trades"].append(trade)
    log("OPEN %s %s x%d at %.2f (%s), stop %.2f, target %.2f" % (
        date, sym, qty, entry, fmt(trig), trade["stop"], trade["target"]))
    journal(date, "Entry %s x%d at %.2f (%s ET)" % (sym, qty, entry, fmt(trig)),
            "\n\n".join([out, out_exit, out_tm, out_size, out_risk, out_t, out_news[:4000]]))
    return True


# ------------------------------------------------------------------ pre-market / summary
def premarket(led, date):
    if cfd_mode(jload(CONFIG, {})):
        _, news = tool("trader-news/news.py", "--tickers", "SPY", "QQQ", "--hours", "16", "--no-sec")
        journal(date, "Pre-market news (S&P 500 / Nasdaq-100 ETFs)", news[-5000:])
        log("Pre-market: index news done.")
        return
    rc, out = tool("trader-scanner/scan.py", "daily", "--out", "trader/watchlist-daily.json", "--quiet")
    journal(date, "Pre-market daily scan", out[-4000:])
    wl = jload("trader/watchlist-daily.json", {})
    top = [h["symbol"] for h in (wl.get("hits") or [])[:8]]
    if top:
        _, news = tool("trader-news/news.py", "--tickers", *top, "--hours", "16", "--no-sec")
        journal(date, "Pre-market news (top daily hits)", news[-5000:])
    log("Pre-market: daily scan done, %d hits." % len(wl.get("hits") or []))


def summary(led, date):
    today = [t for t in led["trades"] if t["date"] == date]
    pnl = round(sum(t.get("pnl") or 0 for t in today), 2)
    lines = ["%s x%s  %s -> %s  %s  %+.2f" % (label(t), q(t["qty"]), t["entry"], t.get("exit"),
                                              t.get("exit_reason"), t.get("pnl") or 0) for t in today]
    journal(date, "End of day: %d trades, P&L %+.2f, balance %.2f" % (len(today), pnl, balance(led)),
            "\n".join(lines) or "no trades")
    log("Day summary %s: %d trades, P&L %+.2f" % (date, len(today), pnl))


def write_balance(led):
    b = balance(led)
    start = led["start_balance"]
    closed = [t for t in led["trades"] if t["status"] == "closed"]
    wins = [t for t in closed if t["pnl"] > 0]
    losses = [t for t in closed if t["pnl"] < 0]
    md = ["# Fake balance (dry run, no broker, no real money)", "",
          "Updated %s UTC" % dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M"), "",
          "| | |", "|---|---|",
          "| Start | $%s (%s) |" % (format(start, ",.2f"), led.get("started")),
          "| Balance | **$%s** |" % format(b, ",.2f"),
          "| P&L | **%+.2f (%+.2f%%)** |" % (b - start, (b - start) / start * 100),
          "| Trades closed | %d (%d won, %d lost, %d flat) |" % (
              len(closed), len(wins), len(losses), len(closed) - len(wins) - len(losses)),
          "| Open now | %s |" % (", ".join("%s x%s @ %.2f" % (label(t), q(t["qty"]), t["entry"])
                                         for t in led["trades"] if t["status"] == "open") or "none"),
          "", "## By day", "", "| Day | Trades | P&L | Balance after |", "|---|---|---|---|"]
    running = start
    for d in sorted({t["date"] for t in closed}):
        ts = [t for t in closed if t["date"] == d]
        p = sum(t["pnl"] for t in ts)
        running += p
        md.append("| %s | %d | %+.2f | $%s |" % (d, len(ts), p, format(running, ",.2f")))
    md += ["", "## Trades", "",
           "| Day | Instrument | Qty | Entry | Stop | Target | Exit | Why | P&L | Time Machine said |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    for t in led["trades"]:
        md.append("| %s %s | %s | %s | %.2f | %.2f | %.2f | %s | %s | %s | %s |" % (
            t["date"], t["entry_time"], label(t), q(t["qty"]), t["entry"], t["stop"], t["target"],
            t.get("exit", "open"), t.get("exit_reason", ""),
            "%+.2f" % t["pnl"] if t.get("pnl") is not None else "", (t.get("timemachine") or "")[:90]))
    md += ["", "Fills are simulated at the trigger price; stops and targets are played out on",
           "5-minute bars (stop first when one bar touches both). CFD costs as in Trading 212's Index CFD",
           "KID (08.06.2026): spread US Tech 100 1.2 pt (KID example), US 500 0.5 pt (estimate), FX fee 0.5%",
           "of each result (USD to EUR), 20:1 leverage; closed by 15:55 NY so no overnight fee.",
           "Stock trades before the switch paid no fees.", ""]
    with open("BALANCE.md", "w", encoding="utf-8") as fh:
        fh.write("\n".join(md))


# ------------------------------------------------------------------ main
def main():
    cfg = jload(CONFIG, {})
    if cfg.get("paper") is not True:
        sys.exit("refusing: trader/config.json must keep \"paper\": true for the dry run")
    rc, out = tool("trader-alerts/alerts.py", "clock", "--json")
    clock = json.loads(out[out.index("{"):])
    date = clock["date"]
    now_min = hm(clock["now_new_york"].split()[1])
    led = load_ledger(cfg)
    led["started"] = led.get("started") or date
    log("Run at %s NY, market %s (%s)." % (clock["now_new_york"], "OPEN" if clock["open"] else "closed",
                                           clock["reason"]))
    trading_day = clock.get("opens") is not None
    if not os.path.exists("trader/universe.txt") or led.get("universe_date", "") < (
            dt.date.fromisoformat(date) - dt.timedelta(days=7)).isoformat():
        tool("trader-scanner/scan.py", "universe")
        led["universe_date"] = date
    if trading_day:
        opens, closes = hm(clock["opens"]), hm(clock["closes"])
        d = day(led, date)
        if now_min < opens and not d["premarket"]:
            premarket(led, date)
            if not cfd_mode(cfg):
                build_affordable(led, cfg, date)
            d["premarket"] = True
        if now_min >= opens + 5:
            manage_open(led, cfg, date, now_min, closes)
        if clock["open"] and hm(ENTRY_FROM) <= now_min < min(hm(ENTRY_UNTIL), closes - 30):
            for _ in range(int(cfg.get("max_trades_per_day", 3))):
                if not try_entries(led, cfg, date, now_min):
                    break
                manage_open(led, cfg, date, now_min, closes)   # it may already be out
        if now_min >= closes and not d["summary"]:
            manage_open(led, cfg, date, now_min, closes, final=True)
            summary(led, date)
            d["summary"] = True
    else:
        manage_open(led, cfg, date, now_min, 16 * 60, final=True)
    jsave(LEDGER, led)
    write_balance(led)
    log("Balance $%.2f (start $%.2f)." % (balance(led), led["start_balance"]))


if __name__ == "__main__":
    main()
