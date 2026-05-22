# Multi-Strategy Day Trading Simulator — Design Spec
**Date:** 2026-05-22  
**Status:** Approved for implementation

---

## Overview

Extend the existing day trading tool from a single-strategy paper trader into a 6-strategy parallel experiment. One shared screener runs once per cycle; 6 independent trading engines each apply their own parameters to the same market data and trade against their own Alpaca paper accounts. At the end of each day, 6 Obsidian journal entries are written and a combined GitHub dashboard shows all strategies side-by-side.

**Goal:** Determine whether the scoring system generates a genuine edge, and which exit structure best exploits that edge.

---

## The 6 Strategies

| # | Name | Target | Stop | R:R | What it tests |
|---|---|---|---|---|---|
| 1 | Baseline | 5% | 2% | 2.5:1 | Control — current settings |
| 2 | Tight R:R | 2% | 2% | 1:1 | Does 1:1 R:R hurt? |
| 3 | Conservative R:R | 3% | 1.5% | 2:1 | 2:1 sweet spot? |
| 4 | High Conviction | 5% | 2% | 2.5:1 | MIN_SCORE 82 — does selectivity improve results? |
| 5 | Volume First | 5% | 2% | 2.5:1 | Boosted volume weight — is volume the real edge? |
| 6 | EMA Crossover Only | 5% | 2% | 2.5:1 | Only trade KRUIS OMHOOG — is the crossover signal predictive? |

All strategies share the same Alpaca paper endpoint. Each uses a separate account (Trading Tool 1–6) with its own API key pair, giving each its own virtual $100,000 and independent bracket order execution.

**Break-even win rates:**
- 1:1 R:R (Strategy 2) — needs 50% wins
- 2:1 R:R (Strategy 3) — needs 33% wins
- 2.5:1 R:R (Strategies 1, 4, 5, 6) — needs 29% wins

---

## Architecture

### Core principle: scan once, score six times

The screener (fetching RSI, VWAP, EMA, volume from yfinance) is the expensive operation. It runs once per cycle and returns raw market data. Each strategy then independently scores and filters that data using its own parameters.

```
main.py
  │
  ├── run_screener()
  │     ├── Morning: grote_scan (all NASDAQ/NYSE tickers → shortlist cache)
  │     └── Every 30 min: kleine_scan (shortlist only)
  │     └── Returns: raw market data per ticker (no scoring)
  │
  └── for each strategy in STRATEGIES:
        signals = score_signals(raw_data, strategy)
        engine.run(signals)  → trades against own Alpaca account
  │
  ├── update_combined_dashboard(all_6_portfolios, signals)
  │
  └── at 21:45 NL:
        for each strategy:
          engine.close_all_positions()
          engine.sync_closed_trades()
          schrijf_dagboek(strategy_naam, trades, scan_stats)
```

---

## Components

### `strategies.py` (NEW)

Defines all 6 strategy configurations as a list of dicts. Reads API keys from `alpaca_keys.txt` by wallet name (Trading Tool 1–6). Each config contains:

```python
{
    'naam': 'Baseline',
    'api_key': '...',
    'secret_key': '...',
    'min_score': 70,
    'doel_pct': 0.05,
    'stop_loss_pct': 0.02,
    'max_bedrag_per_trade': 1000,
    'risico_per_trade': 0.02,
    'gesimuleerd_kapitaal': 100000,
    'volume_gewicht': 1.0,    # multiplier on VOLUME_ZONES scoring (Strategy 5 uses 1.5)
    'ema_only': False,        # Strategy 6: pre-filter to KRUIS OMHOOG only
}
```

### `paper_trading.py` — refactored to `PaperTradingEngine` class

All module-level constants removed. Each strategy instantiates its own engine:

```python
class PaperTradingEngine:
    def __init__(self, strategy: dict):
        self.naam = strategy['naam']
        self.config = strategy
        self.log_bestand = f"trades_{naam_slug}.json"
        self.trading_client = TradingClient(api_key, secret_key, paper=True)
        self.data_client = StockHistoricalDataClient(api_key, secret_key)
```

Existing methods (`open_trade`, `sluit_trade`, `sync_gesloten_trades`, `sluit_alle_trades`) become instance methods using `self.config` values. Bracket order logic is unchanged — Alpaca still manages real-time exits.

Module-level `trading_client` is retained solely for `is_markt_open()` (uses Trading Tool 1 / Baseline account as the clock).

### `dashboard.py` — screener split

**Current:** `run_screener()` fetches data and scores in one pass.  
**New:** Split into two functions:

- `run_screener()` → returns raw market data list (no scores, no filtering)
- `score_signals(raw_data, strategy)` → applies strategy's scoring weights and `min_score` filter, returns tradeable signals

`bereken_confluence_score(data, volume_gewicht)` accepts a `volume_gewicht` parameter (default 1.0). Strategy 5 passes 1.5 to boost volume zone multipliers.

`score_signals` for Strategy 6 pre-filters `raw_data` to tickers where `ema_status == 'KRUIS OMHOOG'` before scoring.

The shortlist cache and grote/kleine scan logic are unchanged.

### `main.py` — orchestrator updated

Imports `STRATEGIES` from `strategies.py`. Initialises one `PaperTradingEngine` per strategy at startup. Run loop:

1. Check market open / closing time (unchanged)
2. `run_screener()` → raw data
3. For each strategy: `score_signals` → `engine.run(signals)`
4. `update_combined_dashboard(all_portfolios, signals)`
5. At 21:45: for each strategy → close positions → sync → write Obsidian journal

### `obsidian_logger.py` — strategy-aware

`schrijf_dagboek(trades, scan_stats, strategy_naam)` gains a `strategy_naam` parameter. The note filename and vault path include the strategy name. Format and content are identical to the current single-strategy journal.

### `github_dashboard.py` — combined view

Reads all 6 `trades_*.json` files. Displays per strategy:
- Total P&L ($ and %)
- Win rate
- Trade count
- Equity vs. starting $100k

Updated once per cycle, same as current.

### Data files

One trades file per strategy:
```
trades_baseline.json
trades_tight_rr.json
trades_conservative_rr.json
trades_high_conviction.json
trades_volume_first.json
trades_ema_crossover_only.json
```

---

## What does NOT change

- `cache_manager.py` — unchanged
- Bracket order logic in `paper_trading.py` — unchanged
- Shortlist cache / grote scan / kleine scan timing — unchanged
- 21:45 NL closing logic — unchanged, applied to all 6 engines
- `alpaca_keys.txt` format — keys are read by wallet name

---

## Implementation order

1. `strategies.py` — define configs, key loader
2. `paper_trading.py` — refactor to `PaperTradingEngine` class
3. `dashboard.py` — split fetch from scoring, add `volume_gewicht` param
4. `main.py` — wire up 6 engines to shared screener
5. `obsidian_logger.py` — add `strategy_naam` param
6. `github_dashboard.py` — combined multi-strategy dashboard

Each step is independently testable. Steps 1–4 can be verified by running one strategy (Baseline) and confirming it behaves identically to the current system before enabling all 6.
