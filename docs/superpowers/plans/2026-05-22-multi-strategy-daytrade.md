# Multi-Strategy Day Trading Simulator — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the single-strategy paper trader into 6 parallel strategies sharing one screener, each with its own Alpaca paper account, trades file, and Obsidian journal entry.

**Architecture:** `strategies.py` defines 6 configs with per-wallet API keys. `PaperTradingEngine` replaces module-level constants with config-driven instance methods. `dashboard.py` returns raw market data; `score_signals(raw_data, strategy)` applies per-strategy scoring. `main.py` runs one scan then feeds all 6 engines. GitHub dashboard shows all 6 side-by-side.

**Tech Stack:** Python 3, alpaca-py, yfinance, pytest, requests, pytz

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `strategies.py` | CREATE | 6 strategy configs + wallet key loader |
| `paper_trading.py` | MODIFY | Refactor to `PaperTradingEngine` class |
| `dashboard.py` | MODIFY | Split scoring; add `score_signals`, `volume_gewicht` |
| `main.py` | MODIFY | Orchestrate 6 engines after shared scan |
| `obsidian_logger.py` | MODIFY | `strategy_naam` param on `schrijf_dagboek` |
| `github_dashboard.py` | MODIFY | Accept list of portfolios; strategy comparison table |
| `tests/conftest.py` | CREATE | Shared pytest fixtures |
| `tests/test_strategies.py` | CREATE | Key loader + config structure |
| `tests/test_paper_trading_engine.py` | CREATE | Engine init, log_bestand, config wiring |
| `tests/test_dashboard_scoring.py` | CREATE | score_signals, volume_gewicht, ema_only filter |
| `tests/test_obsidian_logger.py` | CREATE | Per-strategy journal filenames |

---

### Task 1: Test infrastructure

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create test directory and conftest**

Create `tests/__init__.py` (empty file).

Create `tests/conftest.py`:

```python
import pytest

@pytest.fixture
def mock_strategy():
    return {
        'naam': 'Baseline',
        'api_key': 'TESTKEY123',
        'secret_key': 'TESTSECRET123',
        'min_score': 70,
        'doel_pct': 0.05,
        'stop_loss_pct': 0.02,
        'max_bedrag_per_trade': 1000,
        'risico_per_trade': 0.02,
        'gesimuleerd_kapitaal': 100000,
        'volume_gewicht': 1.0,
        'ema_only': False,
    }

@pytest.fixture
def mock_ticker_data():
    return {
        'ticker': 'AAPL',
        'prijs': 150.00,
        'verandering': 3.00,
        'verandering_pct': 2.04,
        'rel_volume': 2.5,
        'rsi': 52.0,
        'boven_vwap': True,
        'ema_status': 'EMA BULL',
        'ema9': 148.0,
        'ema20': 145.0,
    }
```

- [ ] **Step 2: Verify pytest**

Run: `python -m pytest --version`
Expected: `pytest X.X.X` — if missing: `pip install pytest`

- [ ] **Step 3: Commit**

```
git add tests/__init__.py tests/conftest.py
git commit -m "test: add pytest infrastructure and shared fixtures"
```

---

### Task 2: `strategies.py`

**Files:**
- Create: `strategies.py`
- Create: `tests/test_strategies.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_strategies.py`:

```python
import os
import tempfile
from unittest.mock import patch

SAMPLE_KEYS = """username: test@example.com

Trading Tool 1
API_KEY = TESTKEY1
SECRET_KEY = TESTSECRET1
ENDPOINT = https://paper-api.alpaca.markets/v2

Trading Tool 2
API_KEY = TESTKEY2
SECRET_KEY = TESTSECRET2
ENDPOINT = https://paper-api.alpaca.markets/v2
"""

def _temp_keys_file():
    f = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
    f.write(SAMPLE_KEYS)
    f.close()
    return f.name

def test_laad_wallet_keys_reads_tool_1():
    path = _temp_keys_file()
    try:
        from strategies import laad_wallet_keys
        keys = laad_wallet_keys('Trading Tool 1', bestand=path)
        assert keys['API_KEY'] == 'TESTKEY1'
        assert keys['SECRET_KEY'] == 'TESTSECRET1'
    finally:
        os.unlink(path)

def test_laad_wallet_keys_reads_tool_2():
    path = _temp_keys_file()
    try:
        from strategies import laad_wallet_keys
        keys = laad_wallet_keys('Trading Tool 2', bestand=path)
        assert keys['API_KEY'] == 'TESTKEY2'
    finally:
        os.unlink(path)

def test_strategies_has_six_entries():
    with patch('strategies.laad_wallet_keys', return_value={'API_KEY': 'K', 'SECRET_KEY': 'S'}):
        import importlib, strategies
        importlib.reload(strategies)
        assert len(strategies.STRATEGIES) == 6

def test_all_strategies_have_required_keys():
    with patch('strategies.laad_wallet_keys', return_value={'API_KEY': 'K', 'SECRET_KEY': 'S'}):
        import importlib, strategies
        importlib.reload(strategies)
        required = {'naam','api_key','secret_key','min_score','doel_pct',
                    'stop_loss_pct','max_bedrag_per_trade','risico_per_trade',
                    'gesimuleerd_kapitaal','volume_gewicht','ema_only'}
        for s in strategies.STRATEGIES:
            assert required.issubset(s.keys()), f"Missing keys in '{s.get('naam')}'"

def test_only_ema_crossover_has_ema_only_true():
    with patch('strategies.laad_wallet_keys', return_value={'API_KEY': 'K', 'SECRET_KEY': 'S'}):
        import importlib, strategies
        importlib.reload(strategies)
        ema_only = [s for s in strategies.STRATEGIES if s['ema_only']]
        assert len(ema_only) == 1
        assert ema_only[0]['naam'] == 'EMA Crossover Only'

def test_volume_first_has_boosted_weight():
    with patch('strategies.laad_wallet_keys', return_value={'API_KEY': 'K', 'SECRET_KEY': 'S'}):
        import importlib, strategies
        importlib.reload(strategies)
        vol = next(s for s in strategies.STRATEGIES if s['naam'] == 'Volume First')
        assert vol['volume_gewicht'] > 1.0

def test_strategy_names_unique():
    with patch('strategies.laad_wallet_keys', return_value={'API_KEY': 'K', 'SECRET_KEY': 'S'}):
        import importlib, strategies
        importlib.reload(strategies)
        names = [s['naam'] for s in strategies.STRATEGIES]
        assert len(names) == len(set(names))
```

- [ ] **Step 2: Run — expect ImportError**

Run: `python -m pytest tests/test_strategies.py -v`
Expected: `ModuleNotFoundError: No module named 'strategies'`

- [ ] **Step 3: Create `strategies.py`**

```python
def laad_wallet_keys(naam, bestand='alpaca_keys.txt'):
    keys = {}
    in_section = False
    with open(bestand, 'r') as f:
        for regel in f:
            regel = regel.strip()
            if regel == naam:
                in_section = True
                continue
            if in_section:
                if regel.startswith('Trading Tool') or (regel.startswith('username') and keys):
                    break
                if '=' in regel:
                    k, v = regel.split(' = ', 1)
                    keys[k.strip()] = v.strip()
    return keys


def _maak_strategies():
    def w(n):
        return laad_wallet_keys(f'Trading Tool {n}')

    return [
        {
            'naam': 'Baseline',
            'api_key': w(1)['API_KEY'], 'secret_key': w(1)['SECRET_KEY'],
            'min_score': 70, 'doel_pct': 0.05, 'stop_loss_pct': 0.02,
            'max_bedrag_per_trade': 1000, 'risico_per_trade': 0.02,
            'gesimuleerd_kapitaal': 100000, 'volume_gewicht': 1.0, 'ema_only': False,
        },
        {
            'naam': 'Tight RR',
            'api_key': w(2)['API_KEY'], 'secret_key': w(2)['SECRET_KEY'],
            'min_score': 70, 'doel_pct': 0.02, 'stop_loss_pct': 0.02,
            'max_bedrag_per_trade': 1000, 'risico_per_trade': 0.02,
            'gesimuleerd_kapitaal': 100000, 'volume_gewicht': 1.0, 'ema_only': False,
        },
        {
            'naam': 'Conservative RR',
            'api_key': w(3)['API_KEY'], 'secret_key': w(3)['SECRET_KEY'],
            'min_score': 70, 'doel_pct': 0.03, 'stop_loss_pct': 0.015,
            'max_bedrag_per_trade': 1000, 'risico_per_trade': 0.02,
            'gesimuleerd_kapitaal': 100000, 'volume_gewicht': 1.0, 'ema_only': False,
        },
        {
            'naam': 'High Conviction',
            'api_key': w(4)['API_KEY'], 'secret_key': w(4)['SECRET_KEY'],
            'min_score': 82, 'doel_pct': 0.05, 'stop_loss_pct': 0.02,
            'max_bedrag_per_trade': 1000, 'risico_per_trade': 0.02,
            'gesimuleerd_kapitaal': 100000, 'volume_gewicht': 1.0, 'ema_only': False,
        },
        {
            'naam': 'Volume First',
            'api_key': w(5)['API_KEY'], 'secret_key': w(5)['SECRET_KEY'],
            'min_score': 70, 'doel_pct': 0.05, 'stop_loss_pct': 0.02,
            'max_bedrag_per_trade': 1000, 'risico_per_trade': 0.02,
            'gesimuleerd_kapitaal': 100000, 'volume_gewicht': 1.5, 'ema_only': False,
        },
        {
            'naam': 'EMA Crossover Only',
            'api_key': w(6)['API_KEY'], 'secret_key': w(6)['SECRET_KEY'],
            'min_score': 70, 'doel_pct': 0.05, 'stop_loss_pct': 0.02,
            'max_bedrag_per_trade': 1000, 'risico_per_trade': 0.02,
            'gesimuleerd_kapitaal': 100000, 'volume_gewicht': 1.0, 'ema_only': True,
        },
    ]


STRATEGIES = _maak_strategies()
```

- [ ] **Step 4: Run tests — expect all pass**

Run: `python -m pytest tests/test_strategies.py -v`
Expected: 7 tests PASS

- [ ] **Step 5: Commit**

```
git add strategies.py tests/test_strategies.py
git commit -m "feat: strategies.py — 6 strategy configs and wallet key loader"
```

---

### Task 3: Refactor `paper_trading.py` to `PaperTradingEngine`

**Files:**
- Modify: `paper_trading.py`
- Create: `tests/test_paper_trading_engine.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_paper_trading_engine.py`:

```python
from unittest.mock import patch

STRATEGY = {
    'naam': 'Baseline', 'api_key': 'TESTKEY', 'secret_key': 'TESTSECRET',
    'min_score': 70, 'doel_pct': 0.05, 'stop_loss_pct': 0.02,
    'max_bedrag_per_trade': 1000, 'risico_per_trade': 0.02,
    'gesimuleerd_kapitaal': 100000, 'volume_gewicht': 1.0, 'ema_only': False,
}

@patch('paper_trading.TradingClient')
@patch('paper_trading.StockHistoricalDataClient')
def test_log_bestand_baseline(mock_dc, mock_tc):
    from paper_trading import PaperTradingEngine
    assert PaperTradingEngine(STRATEGY).log_bestand == 'trades_baseline.json'

@patch('paper_trading.TradingClient')
@patch('paper_trading.StockHistoricalDataClient')
def test_log_bestand_spaces_replaced(mock_dc, mock_tc):
    from paper_trading import PaperTradingEngine
    e = PaperTradingEngine(dict(STRATEGY, naam='EMA Crossover Only'))
    assert e.log_bestand == 'trades_ema_crossover_only.json'

@patch('paper_trading.TradingClient')
@patch('paper_trading.StockHistoricalDataClient')
def test_engine_uses_strategy_doel_pct(mock_dc, mock_tc):
    from paper_trading import PaperTradingEngine
    e = PaperTradingEngine(dict(STRATEGY, doel_pct=0.03))
    assert e.config['doel_pct'] == 0.03

@patch('paper_trading.TradingClient')
@patch('paper_trading.StockHistoricalDataClient')
def test_engine_instantiates_own_trading_client(mock_dc, mock_tc):
    from paper_trading import PaperTradingEngine
    PaperTradingEngine(STRATEGY)
    mock_tc.assert_called_with('TESTKEY', 'TESTSECRET', paper=True)
```

- [ ] **Step 2: Run — expect ImportError**

Run: `python -m pytest tests/test_paper_trading_engine.py -v`
Expected: `ImportError: cannot import name 'PaperTradingEngine'`

- [ ] **Step 3: Replace `paper_trading.py`**

```python
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import (
    MarketOrderRequest, TakeProfitRequest, StopLossRequest, GetOrdersRequest
)
from alpaca.trading.enums import QueryOrderStatus, OrderSide, TimeInForce, OrderClass
from alpaca.data.historical import StockHistoricalDataClient
import json
import os
from datetime import datetime
import pytz

from strategies import laad_wallet_keys

NY_TZ = pytz.timezone('America/New_York')

# ─── Marktklok — Trading Tool 1 als klok ────────────────────

def _klok_client():
    keys = laad_wallet_keys('Trading Tool 1')
    return TradingClient(keys['API_KEY'], keys['SECRET_KEY'], paper=True)

trading_client = _klok_client()


def is_markt_open():
    return trading_client.get_clock().is_open


def haal_huidige_prijs(ticker):
    try:
        import yfinance as yf
        import time
        time.sleep(0.5)
        data = yf.Ticker(ticker).history(period="2d")
        if not data.empty:
            return round(data['Close'].iloc[-1], 2)
    except Exception as e:
        print(f"  Prijs fout {ticker}: {e}")
    return None


# ─── PaperTradingEngine ──────────────────────────────────────

class PaperTradingEngine:
    def __init__(self, strategy: dict):
        self.naam = strategy['naam']
        self.config = strategy
        slug = strategy['naam'].lower().replace(' ', '_')
        self.log_bestand = f'trades_{slug}.json'
        self.trading_client = TradingClient(
            strategy['api_key'], strategy['secret_key'], paper=True
        )
        self.data_client = StockHistoricalDataClient(
            strategy['api_key'], strategy['secret_key']
        )

    def laad_portfolio(self):
        if os.path.exists(self.log_bestand):
            with open(self.log_bestand, 'r') as f:
                return json.load(f)
        account = self.trading_client.get_account()
        return {
            'startkapitaal': float(account.cash),
            'open_trades': {},
            'gesloten_trades': [],
            'statistieken': {
                'totaal': 0, 'winstgevend': 0,
                'verliesgevend': 0, 'totaal_resultaat': 0.0
            }
        }

    def sla_portfolio_op(self, portfolio):
        with open(self.log_bestand, 'w') as f:
            json.dump(portfolio, f, indent=2)

    def open_trade(self, portfolio, ticker, prijs, score):
        if ticker in portfolio['open_trades']:
            print(f"  [{self.naam}] {ticker}: al open")
            return

        account = self.trading_client.get_account()
        beschikbaar = float(account.cash)
        max_bedrag = self.config['max_bedrag_per_trade']
        if beschikbaar < max_bedrag:
            print(f"  [{self.naam}] ⛔ Niet genoeg cash — ${beschikbaar:,.2f}")
            return

        risico_bedrag = min(
            self.config['gesimuleerd_kapitaal'] * self.config['risico_per_trade'],
            max_bedrag
        )
        stop_prijs = round(prijs * (1 - self.config['stop_loss_pct']), 2)
        if round(prijs - stop_prijs, 2) < 0.01:
            stop_prijs = round(prijs - 0.01, 2)
        if stop_prijs <= 0:
            print(f"  [{self.naam}] {ticker}: prijs te laag voor stop loss")
            return

        doel_prijs = round(prijs * (1 + self.config['doel_pct']), 2)
        risico_per_aandeel = prijs - stop_prijs
        max_aandelen = int(max_bedrag / prijs)
        aantal = min(int(risico_bedrag / risico_per_aandeel), max_aandelen)

        if aantal < 1:
            print(f"  [{self.naam}] {ticker}: te weinig kapitaal")
            return

        try:
            order = MarketOrderRequest(
                symbol=ticker, qty=aantal, side=OrderSide.BUY,
                time_in_force=TimeInForce.DAY, order_class=OrderClass.BRACKET,
                take_profit=TakeProfitRequest(limit_price=doel_prijs),
                stop_loss=StopLossRequest(stop_price=stop_prijs)
            )
            self.trading_client.submit_order(order)
            portfolio['open_trades'][ticker] = {
                'ticker': ticker, 'instap_prijs': prijs, 'aantal': aantal,
                'stop_loss': stop_prijs, 'doel': doel_prijs, 'score': score,
                'tijdstip': datetime.now().strftime('%d/%m/%Y %H:%M')
            }
            print(f"  [{self.naam}] ✅ BRACKET: {aantal}x {ticker} @ ${prijs} | Stop: ${stop_prijs} | Doel: ${doel_prijs}")
        except Exception as e:
            fout = str(e)
            if 'not tradable' in fout:
                print(f"  [{self.naam}] ⛔ {ticker}: niet tradable")
            elif 'stop_loss' in fout:
                print(f"  [{self.naam}] ⛔ {ticker}: stop loss probleem")
            else:
                print(f"  [{self.naam}] Order fout {ticker}: {e}")

    def sluit_trade(self, portfolio, ticker, prijs, reden):
        if ticker not in portfolio['open_trades']:
            return
        trade = portfolio['open_trades'][ticker]

        try:
            for order in self.trading_client.get_orders():
                if str(order.symbol) == ticker:
                    try:
                        self.trading_client.cancel_order_by_id(order.id)
                    except:
                        pass
        except Exception as e:
            print(f"  [{self.naam}] Annuleer fout {ticker}: {e}")

        try:
            self.trading_client.submit_order(MarketOrderRequest(
                symbol=ticker, qty=trade['aantal'],
                side=OrderSide.SELL, time_in_force=TimeInForce.DAY
            ))
        except Exception as e:
            print(f"  [{self.naam}] Verkoop fout {ticker}: {e}")
            return

        kosten = round(trade['aantal'] * trade['instap_prijs'], 2)
        opbrengst = round(trade['aantal'] * prijs, 2)
        resultaat = round(opbrengst - kosten, 2)
        resultaat_pct = round((resultaat / kosten) * 100, 2)

        portfolio['gesloten_trades'].append({
            **trade, 'uitstap_prijs': prijs, 'resultaat': resultaat,
            'resultaat_pct': resultaat_pct, 'reden': reden,
            'gesloten_op': datetime.now().strftime('%d/%m/%Y %H:%M')
        })
        portfolio['statistieken']['totaal'] += 1
        portfolio['statistieken']['totaal_resultaat'] += resultaat
        if resultaat > 0:
            portfolio['statistieken']['winstgevend'] += 1
            print(f"  [{self.naam}] 💰 WINST: {ticker} +${resultaat} | {reden}")
        else:
            portfolio['statistieken']['verliesgevend'] += 1
            print(f"  [{self.naam}] ❌ VERLIES: {ticker} ${resultaat} | {reden}")
        del portfolio['open_trades'][ticker]

    def sluit_alle_trades(self, portfolio):
        print(f"\n  [{self.naam}] Markt sluit — posities sluiten...")
        for ticker in list(portfolio['open_trades'].keys()):
            prijs = haal_huidige_prijs(ticker)
            if prijs:
                self.sluit_trade(portfolio, ticker, prijs, 'Markt sluit')

    def haal_order_data_op(self, ticker):
        try:
            orders = self.trading_client.get_orders(filter=GetOrdersRequest(
                status=QueryOrderStatus.CLOSED, symbols=[ticker], limit=5
            ))
            for order in orders:
                if str(order.side) == 'OrderSide.SELL' and str(order.status) in ('OrderStatus.FILLED', 'filled'):
                    prijs = float(order.filled_avg_price) if order.filled_avg_price else None
                    tijdstip = order.filled_at.strftime('%d/%m/%Y %H:%M') if order.filled_at else None
                    return prijs, tijdstip
        except Exception as e:
            print(f"  [{self.naam}] Order data fout {ticker}: {e}")
        return None, None

    def sync_gesloten_trades(self, portfolio):
        try:
            alpaca_posities = {p.symbol for p in self.trading_client.get_all_positions()}
        except Exception as e:
            print(f"  [{self.naam}] Sync fout: {e}")
            return

        for ticker in list(portfolio['open_trades'].keys()):
            if ticker not in alpaca_posities:
                trade = portfolio['open_trades'][ticker]
                alpaca_prijs, alpaca_tijdstip = self.haal_order_data_op(ticker)
                prijs = alpaca_prijs or haal_huidige_prijs(ticker) or trade['instap_prijs']
                tijdstip = alpaca_tijdstip or datetime.now().strftime('%d/%m/%Y %H:%M')

                kosten = trade['aantal'] * trade['instap_prijs']
                opbrengst = trade['aantal'] * prijs
                resultaat = round(opbrengst - kosten, 2)
                resultaat_pct = round((resultaat / kosten) * 100, 2)
                reden = 'Doel bereikt' if prijs >= trade['doel'] else 'Stop loss'

                portfolio['gesloten_trades'].append({
                    **trade, 'uitstap_prijs': prijs, 'resultaat': resultaat,
                    'resultaat_pct': resultaat_pct, 'reden': reden, 'gesloten_op': tijdstip
                })
                portfolio['statistieken']['totaal'] += 1
                portfolio['statistieken']['totaal_resultaat'] += resultaat
                if resultaat > 0:
                    portfolio['statistieken']['winstgevend'] += 1
                    print(f"  [{self.naam}] 💰 BRACKET HIT: {ticker} +${resultaat} | {reden}")
                else:
                    portfolio['statistieken']['verliesgevend'] += 1
                    print(f"  [{self.naam}] ❌ BRACKET HIT: {ticker} ${resultaat} | {reden}")
                del portfolio['open_trades'][ticker]

    def toon_overzicht(self, portfolio):
        try:
            portfolio_waarde = float(self.trading_client.get_account().portfolio_value)
        except:
            portfolio_waarde = portfolio.get('startkapitaal', 100000)
        startkapitaal = portfolio['startkapitaal']
        rendement = round(((portfolio_waarde - startkapitaal) / startkapitaal) * 100, 2)
        stats = portfolio['statistieken']
        print(f"  [{self.naam}] waarde: ${portfolio_waarde:,.2f} | rendement: {rendement}% | trades: {stats['totaal']}")

    def run(self, signalen=None):
        portfolio = self.laad_portfolio()

        if not is_markt_open():
            self.toon_overzicht(portfolio)
            self.sla_portfolio_op(portfolio)
            return []

        print(f"\n  [{self.naam}] Bracket orders syncen...")
        self.sync_gesloten_trades(portfolio)

        if signalen:
            print(f"\n  [{self.naam}] {len(signalen)} signalen verwerken...")
            for s in signalen:
                prijs = s.get('prijs') or haal_huidige_prijs(s['ticker'])
                if prijs:
                    self.open_trade(portfolio, s['ticker'], prijs, s['score'])

        self.sla_portfolio_op(portfolio)
        self.toon_overzicht(portfolio)
        return portfolio['gesloten_trades']
```

- [ ] **Step 4: Run tests — expect all pass**

Run: `python -m pytest tests/test_paper_trading_engine.py -v`
Expected: 4 tests PASS

- [ ] **Step 5: Commit**

```
git add paper_trading.py tests/test_paper_trading_engine.py
git commit -m "refactor: PaperTradingEngine class — config-driven per-strategy Alpaca client"
```

---

### Task 4: Split scoring from fetch in `dashboard.py`

**Files:**
- Modify: `dashboard.py`
- Create: `tests/test_dashboard_scoring.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_dashboard_scoring.py`:

```python
RAW = [
    {'ticker': 'AAPL', 'prijs': 150.0, 'verandering': 3.0, 'verandering_pct': 2.04,
     'rel_volume': 2.5, 'rsi': 52.0, 'boven_vwap': True, 'ema_status': 'EMA BULL',
     'ema9': 148.0, 'ema20': 145.0},
    {'ticker': 'TSLA', 'prijs': 200.0, 'verandering': 6.0, 'verandering_pct': 3.1,
     'rel_volume': 4.0, 'rsi': 58.0, 'boven_vwap': True, 'ema_status': 'KRUIS OMHOOG',
     'ema9': 195.0, 'ema20': 193.0},
    {'ticker': 'GME', 'prijs': 20.0, 'verandering': -0.5, 'verandering_pct': -2.4,
     'rel_volume': 0.8, 'rsi': 40.0, 'boven_vwap': False, 'ema_status': 'EMA BEAR',
     'ema9': 19.0, 'ema20': 21.0},
]

def test_bereken_confluence_score_returns_0_to_100():
    from dashboard import bereken_confluence_score
    assert 0 <= bereken_confluence_score(RAW[0], volume_gewicht=1.0) <= 100

def test_volume_gewicht_changes_score():
    from dashboard import bereken_confluence_score
    s1 = bereken_confluence_score(RAW[0], volume_gewicht=1.0)
    s2 = bereken_confluence_score(RAW[0], volume_gewicht=1.5)
    assert s1 != s2

def test_score_signals_min_score_filters():
    from dashboard import score_signals
    result = score_signals(RAW, {'min_score': 999, 'volume_gewicht': 1.0, 'ema_only': False})
    assert result == []

def test_score_signals_adds_score_key():
    from dashboard import score_signals
    result = score_signals(RAW, {'min_score': 0, 'volume_gewicht': 1.0, 'ema_only': False})
    assert all('score' in r for r in result)

def test_score_signals_sorted_descending():
    from dashboard import score_signals
    result = score_signals(RAW, {'min_score': 0, 'volume_gewicht': 1.0, 'ema_only': False})
    scores = [r['score'] for r in result]
    assert scores == sorted(scores, reverse=True)

def test_ema_only_keeps_only_crossover():
    from dashboard import score_signals
    result = score_signals(RAW, {'min_score': 0, 'volume_gewicht': 1.0, 'ema_only': True})
    assert [r['ticker'] for r in result] == ['TSLA']

def test_kleine_scan_returns_no_score_key():
    from unittest.mock import patch
    mock = {'ticker': 'AAPL', 'prijs': 150.0, 'verandering': 3.0, 'verandering_pct': 2.04,
            'rel_volume': 2.5, 'rsi': 52.0, 'boven_vwap': True, 'ema_status': 'EMA BULL',
            'ema9': 148.0, 'ema20': 145.0}
    with patch('dashboard.haal_data_op', return_value=mock):
        from dashboard import kleine_scan
        result = kleine_scan(['AAPL'])
        assert len(result) == 1
        assert 'score' not in result[0]
```

- [ ] **Step 2: Run — expect failures**

Run: `python -m pytest tests/test_dashboard_scoring.py -v`
Expected: Multiple FAIL — `bereken_confluence_score` missing `volume_gewicht`, `score_signals` not found

- [ ] **Step 3: Update `bereken_confluence_score` signature and volume section**

Replace the existing `bereken_confluence_score` function in `dashboard.py`:

```python
def bereken_confluence_score(data, volume_gewicht=1.0):
    score = SCORE_BASIS

    score *= VWAP_BOVEN_MULT if data['boven_vwap'] else VWAP_ONDER_MULT

    rsi = data['rsi']
    for grens, mult in RSI_ZONES:
        if rsi < grens:
            score *= mult
            break

    rv = data['rel_volume']
    pos = data['verandering_pct'] > 0
    for grens, mp, mn in VOLUME_ZONES:
        if rv > grens:
            vol_mult = mp if pos else mn
            vol_mult_adjusted = 1.0 + (vol_mult - 1.0) * volume_gewicht
            score *= vol_mult_adjusted
            break

    pct = data['verandering_pct']
    for grens, mult in VERANDERING_ZONES:
        if pct > grens:
            score *= mult
            break

    score *= EMA_MULTIPLIERS.get(data['ema_status'], 1.0)

    if pct > 2 and not data['boven_vwap']:
        score *= PENALTY_STIJGING_ONDER_VWAP
    if rsi > 65 and data['ema_status'] == 'KRUIS OMHOOG':
        score *= PENALTY_HOGE_RSI_BIJ_KRUIS_OMHOOG
    if rsi < 35 and data['ema_status'] == 'KRUIS OMLAAG':
        score *= BONUS_LAGE_RSI_BIJ_KRUIS_OMLAAG

    return round(max(0, min(100, score)), 1)
```

- [ ] **Step 4: Add `score_signals` directly after `bereken_confluence_score`**

```python
def score_signals(raw_data, strategy):
    data = raw_data
    if strategy.get('ema_only'):
        data = [d for d in data if d.get('ema_status') == 'KRUIS OMHOOG']

    resultaten = []
    for d in data:
        score = bereken_confluence_score(d, strategy.get('volume_gewicht', 1.0))
        if score >= strategy['min_score']:
            resultaten.append({**d, 'score': score})

    resultaten.sort(key=lambda x: x['score'], reverse=True)
    return resultaten
```

- [ ] **Step 5: Replace `kleine_scan` — return raw data only**

```python
def kleine_scan(shortlist_tickers):
    print(f"\n  🔄 KLEINE SCAN — {len(shortlist_tickers)} shortlist aandelen refreshen...")
    resultaten = []
    for ticker in shortlist_tickers:
        data = haal_data_op(ticker)
        if data:
            resultaten.append(data)
    print(f"  ✅ Kleine scan klaar — {len(resultaten)} aandelen opgehaald")
    return resultaten
```

- [ ] **Step 6: Update `run_screener` to return raw data**

Replace `run_screener`:

```python
def run_screener():
    print("\n  DAY TRADE SCREENER GESTART")
    print("  " + "=" * 40)

    alle_tickers = haal_alle_tickers_op()
    if not alle_tickers:
        print("  Kon geen tickers ophalen.")
        return [], {}

    shortlist_tickers, grote_scan_nodig = laad_shortlist_cache()

    if grote_scan_nodig:
        resultaten_met_score = grote_scan(alle_tickers)
        raw_data = [{k: v for k, v in d.items() if k != 'score'} for d in resultaten_met_score]
    else:
        raw_data = kleine_scan(shortlist_tickers)
        resultaten_met_score = [{**d, 'score': bereken_confluence_score(d)} for d in raw_data]

    print(f"\n  Top {TOP_RESULTATEN} meest extreme signalen:\n")
    toon_dashboard(resultaten_met_score[:TOP_RESULTATEN])
    sla_scan_historie_op(resultaten_met_score)

    stats = bereken_scan_statistieken(resultaten_met_score)
    return raw_data, stats
```

- [ ] **Step 7: Run tests — expect all pass**

Run: `python -m pytest tests/test_dashboard_scoring.py -v`
Expected: 7 tests PASS

- [ ] **Step 8: Commit**

```
git add dashboard.py tests/test_dashboard_scoring.py
git commit -m "feat: dashboard split — score_signals, volume_gewicht, raw data return"
```

---

### Task 5: Update `main.py`

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Replace `main.py`**

```python
import time
from datetime import datetime
import pytz

from dashboard import run_screener, score_signals
from paper_trading import is_markt_open, PaperTradingEngine
from obsidian_logger import schrijf_dagboek
from github_dashboard import update_dashboard
from strategies import STRATEGIES

NY_TZ = pytz.timezone('America/New_York')
NL_TZ = pytz.timezone('Europe/Amsterdam')

SLUIT_UUR_NL = 21
SLUIT_MINUUT_NL = 45

ENGINES = [PaperTradingEngine(s) for s in STRATEGIES]


def volgende_halve_uur():
    nu = datetime.now(NY_TZ)
    minuten = nu.minute
    seconden = nu.second
    wacht_minuten = 30 - minuten if minuten < 30 else 60 - minuten
    return wacht_minuten * 60 - seconden


def is_sluitingstijd():
    nu = datetime.now(NL_TZ)
    return (nu.hour > SLUIT_UUR_NL) or (nu.hour == SLUIT_UUR_NL and nu.minute >= SLUIT_MINUUT_NL)


def _laad_alle_portfolios():
    portfolios = []
    for engine in ENGINES:
        p = engine.laad_portfolio()
        p['naam'] = engine.naam
        try:
            account = engine.trading_client.get_account()
            p['portfolio_waarde'] = float(account.portfolio_value)
        except:
            p['portfolio_waarde'] = p.get('startkapitaal', 100000)
        portfolios.append(p)
    return portfolios


def run_cyclus():
    print("\n" + "=" * 55)
    print(f"  CYCLUS GESTART — {datetime.now(NL_TZ).strftime('%d/%m/%Y %H:%M')} NL")
    print("=" * 55)

    raw_data, scan_stats = run_screener()

    for engine in ENGINES:
        signalen = score_signals(raw_data, engine.config)
        engine.run(signalen)

    return scan_stats, raw_data


def sluit_dag_af(scan_stats):
    print("\n  ⏰ 21:45 NL — posities sluiten voor einde markt...")

    for engine in ENGINES:
        portfolio = engine.laad_portfolio()
        print(f"  [{engine.naam}] Alpaca uitlezen...")
        engine.sync_gesloten_trades(portfolio)

        try:
            alpaca_posities = {p.symbol for p in engine.trading_client.get_all_positions()}
            for ticker in list(portfolio['open_trades'].keys()):
                if ticker not in alpaca_posities:
                    del portfolio['open_trades'][ticker]
        except Exception as e:
            print(f"  [{engine.naam}] Alpaca sync fout: {e}")

        engine.sluit_alle_trades(portfolio)
        engine.sla_portfolio_op(portfolio)

        vandaag = datetime.now(NL_TZ).strftime('%d/%m/%Y')
        gesloten_vandaag = [
            t for t in portfolio['gesloten_trades']
            if t.get('gesloten_op', '').startswith(vandaag)
        ]
        schrijf_dagboek(trades=gesloten_vandaag, scan_stats=scan_stats, strategy_naam=engine.naam)

    update_dashboard(_laad_alle_portfolios(), None)
    print("  ✅ Dag afgesloten — dagboek en dashboard bijgewerkt.")


def main():
    print("DAY TRADE SYSTEEM GESTART — 6 STRATEGIEEN")
    print("=" * 55)
    for i, s in enumerate(STRATEGIES, 1):
        print(f"  {i}. {s['naam']} | doel: {s['doel_pct']*100:.0f}% | stop: {s['stop_loss_pct']*100:.1f}% | min_score: {s['min_score']}")
    print(f"\n  Posities sluiten om {SLUIT_UUR_NL}:{SLUIT_MINUUT_NL:02d} NL.\n")

    dag_afgesloten = False
    laatste_scan_stats = None

    while True:
        if not dag_afgesloten and is_sluitingstijd():
            sluit_dag_af(laatste_scan_stats)
            dag_afgesloten = True

        if not is_markt_open():
            if not dag_afgesloten:
                sluit_dag_af(laatste_scan_stats)
            print("  Markt gesloten — systeem stopt.")
            break

        if dag_afgesloten:
            print("  Posities gesloten — wachten tot markt sluit...")
            time.sleep(60)
            continue

        scan_stats, raw_data = run_cyclus()
        laatste_scan_stats = scan_stats

        baseline_signalen = score_signals(raw_data, STRATEGIES[0])
        update_dashboard(_laad_alle_portfolios(), baseline_signalen)

        wacht = volgende_halve_uur()
        nu_nl = datetime.now(NL_TZ)
        sluit_moment = nu_nl.replace(hour=SLUIT_UUR_NL, minute=SLUIT_MINUUT_NL, second=0, microsecond=0)
        seconden_tot_sluit = (sluit_moment - nu_nl).total_seconds()
        if 0 < seconden_tot_sluit < wacht:
            wacht = int(seconden_tot_sluit) + 5
        nu_ny = datetime.now(NY_TZ)
        print(f"\n  ⏱  Volgende scan over {round(wacht/60, 1)} min  |  NL: {nu_nl.strftime('%H:%M')}  NY: {nu_ny.strftime('%H:%M')}")

        gewacht = 0
        while gewacht < wacht:
            time.sleep(min(60, wacht - gewacht))
            gewacht += 60
            if not dag_afgesloten and is_sluitingstijd():
                break


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify import chain**

Run: `python -c "from strategies import STRATEGIES; print(len(STRATEGIES), 'strategies OK')"`
Expected: `6 strategies OK`

- [ ] **Step 3: Commit**

```
git add main.py
git commit -m "feat: main.py orchestrates 6 engines from one shared scan"
```

---

### Task 6: `obsidian_logger.py` — per-strategy journals

**Files:**
- Modify: `obsidian_logger.py`
- Create: `tests/test_obsidian_logger.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_obsidian_logger.py`:

```python
from unittest.mock import patch

MOCK_SNAP = {
    'versie': '2026-01-01 10:00', 'score_basis': 50,
    'vwap': {'boven': 1.15, 'onder': 0.85},
    'rsi_zones': [], 'volume_zones': [], 'verandering_zones': [],
    'ema_multipliers': {},
    'penalties': {'stijging_onder_vwap': 0.9, 'hoge_rsi_bij_kruis_omhoog': 0.88,
                  'bonus_lage_rsi_bij_kruis_omlaag': 1.1},
    'drempelwaarden': {'min_score': 70, 'min_beweging_pct': 3.0, 'min_rel_volume': 1.5},
    'trade_parameters': {'gesimuleerd_kapitaal': 100000, 'risico_per_trade_pct': 2,
                         'doel_pct': 5, 'stop_loss_pct': 2}
}

def test_baseline_filename_contains_baseline(tmp_path):
    (tmp_path / 'Dagboek').mkdir()
    with patch('obsidian_logger.OBSIDIAN_PAD', str(tmp_path)), \
         patch('obsidian_logger.haal_markt_data_op', return_value=None), \
         patch('obsidian_logger.scoring_snapshot', return_value=MOCK_SNAP):
        from obsidian_logger import schrijf_dagboek
        schrijf_dagboek(trades=[], scan_stats=None, strategy_naam='Baseline')
        files = list((tmp_path / 'Dagboek').iterdir())
        assert any('baseline' in f.name for f in files)

def test_two_strategies_write_two_files(tmp_path):
    (tmp_path / 'Dagboek').mkdir()
    with patch('obsidian_logger.OBSIDIAN_PAD', str(tmp_path)), \
         patch('obsidian_logger.haal_markt_data_op', return_value=None), \
         patch('obsidian_logger.scoring_snapshot', return_value=MOCK_SNAP):
        from obsidian_logger import schrijf_dagboek
        schrijf_dagboek(trades=[], scan_stats=None, strategy_naam='Baseline')
        schrijf_dagboek(trades=[], scan_stats=None, strategy_naam='Tight RR')
        files = list((tmp_path / 'Dagboek').iterdir())
        assert len(files) == 2
```

- [ ] **Step 2: Run — expect failure**

Run: `python -m pytest tests/test_obsidian_logger.py -v`
Expected: FAIL — `unexpected keyword argument 'strategy_naam'`

- [ ] **Step 3: Update `obsidian_logger.py`**

Change the signature on line 216:

```python
def schrijf_dagboek(trades=None, scan_stats=None, strategy_naam='Baseline'):
```

Change the file path line (find `pad = os.path.join(OBSIDIAN_PAD, 'Dagboek', f"{datum}.md")`):

```python
    slug = strategy_naam.lower().replace(' ', '_')
    pad = os.path.join(OBSIDIAN_PAD, 'Dagboek', f"{datum}-{slug}.md")
```

- [ ] **Step 4: Run tests — expect pass**

Run: `python -m pytest tests/test_obsidian_logger.py -v`
Expected: 2 tests PASS

- [ ] **Step 5: Commit**

```
git add obsidian_logger.py tests/test_obsidian_logger.py
git commit -m "feat: obsidian logger writes per-strategy journal — {date}-{strategy}.md"
```

---

### Task 7: Combined dashboard in `github_dashboard.py`

**Files:**
- Modify: `github_dashboard.py`

- [ ] **Step 1: Replace `genereer_dashboard_html` with multi-portfolio version**

```python
def genereer_dashboard_html(portfolios, scan_resultaten=None):
    nu = datetime.now(NL_TZ).strftime('%d/%m/%Y %H:%M')

    strategy_rijen = ''
    for p in portfolios:
        naam = p.get('naam', '?')
        stats = p.get('statistieken', {})
        start = p.get('startkapitaal', 100000)
        waarde = p.get('portfolio_waarde', start)
        rendement = round(((waarde - start) / start) * 100, 2) if start else 0
        winrate = round((stats.get('winstgevend', 0) / stats['totaal']) * 100, 1) if stats.get('totaal', 0) > 0 else 0
        pl = stats.get('totaal_resultaat', 0)
        ren_kleur = '#00ff88' if rendement >= 0 else '#ff4466'
        pl_kleur = '#00ff88' if pl >= 0 else '#ff4466'
        strategy_rijen += f"""
        <tr>
            <td><span class="ticker">{naam}</span></td>
            <td>${waarde:,.0f}</td>
            <td style="color:{ren_kleur}">{'+' if rendement >= 0 else ''}{rendement}%</td>
            <td style="color:{pl_kleur}">${pl:+,.2f}</td>
            <td>{stats.get('totaal', 0)}</td>
            <td>{winrate}%</td>
            <td>{len(p.get('open_trades', {}))}</td>
        </tr>"""

    scan_rijen = ''
    if scan_resultaten:
        for d in scan_resultaten[:20]:
            ema_kort = {
                'KRUIS OMHOOG': '↑ KRUIS', 'KRUIS OMLAAG': '↓ KRUIS',
                'EMA BULL': '↑ BULL', 'EMA BEAR': '↓ BEAR'
            }.get(d.get('ema_status', ''), d.get('ema_status', ''))
            vwap = 'BOVEN' if d.get('boven_vwap') else 'ONDER'
            score = d.get('score', 0)
            score_kleur = '#00ff88' if score >= 85 else '#ffcc00' if score >= 70 else '#ffffff'
            scan_rijen += f"""
            <tr>
                <td><span class="ticker">{d['ticker']}</span></td>
                <td>${d.get('prijs', 0):.2f}</td>
                <td>{d.get('verandering_pct', 0):+.2f}%</td>
                <td>{d.get('rel_volume', 0):.1f}x</td>
                <td>{d.get('rsi', 0):.1f}</td>
                <td>{vwap}</td>
                <td>{ema_kort}</td>
                <td style="color:{score_kleur}"><b>{score}</b></td>
            </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="nl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="refresh" content="1800">
<title>Trading Dashboard</title>
<link href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;700;800&display=swap" rel="stylesheet">
<style>
  :root {{--bg:#080c12;--surface:#0d1520;--border:#1a2535;--accent:#00ff88;--danger:#ff4466;--text:#c8d8e8;--muted:#4a6080;--mono:'Space Mono',monospace;--sans:'Syne',sans-serif;}}
  *{{margin:0;padding:0;box-sizing:border-box;}}
  body{{background:var(--bg);color:var(--text);font-family:var(--mono);font-size:13px;}}
  header{{padding:32px 40px 24px;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:flex-end;}}
  header h1{{font-family:var(--sans);font-size:28px;font-weight:800;color:#fff;}}
  header h1 span{{color:var(--accent);}}
  .timestamp{{color:var(--muted);font-size:11px;}}
  .timestamp b{{color:var(--accent);}}
  .section{{padding:32px 40px;border-bottom:1px solid var(--border);}}
  .section-title{{font-family:var(--sans);font-size:13px;font-weight:700;text-transform:uppercase;letter-spacing:3px;color:var(--muted);margin-bottom:20px;display:flex;align-items:center;gap:10px;}}
  .section-title::after{{content:'';flex:1;height:1px;background:var(--border);}}
  table{{width:100%;border-collapse:collapse;}}
  th{{text-align:left;padding:8px 12px;font-size:10px;text-transform:uppercase;letter-spacing:2px;color:var(--muted);border-bottom:1px solid var(--border);}}
  td{{padding:10px 12px;border-bottom:1px solid rgba(26,37,53,0.5);}}
  tr:hover td{{background:rgba(255,255,255,0.02);}}
  .ticker{{font-weight:700;color:#fff;background:var(--border);padding:2px 8px;border-radius:3px;font-size:12px;}}
  .live-dot{{width:8px;height:8px;background:var(--accent);border-radius:50%;display:inline-block;animation:pulse 2s infinite;}}
  @keyframes pulse{{0%,100%{{opacity:1;box-shadow:0 0 0 0 rgba(0,255,136,0.4);}}50%{{opacity:.7;box-shadow:0 0 0 6px rgba(0,255,136,0);}}}}
  footer{{padding:20px 40px;color:var(--muted);font-size:11px;text-align:center;}}
</style>
</head>
<body>
<header>
  <div>
    <h1>TRADING <span>DASHBOARD</span></h1>
    <div style="margin-top:4px;color:var(--muted);font-size:11px">6-strategy paper trading — Alpaca Markets</div>
  </div>
  <div style="text-align:right">
    <div style="margin-bottom:6px"><span class="live-dot"></span> <span style="color:var(--accent);font-size:11px">LIVE</span></div>
    <div class="timestamp">Laatste update: <b>{nu}</b></div>
  </div>
</header>
<div class="section">
  <div class="section-title">Strategy vergelijking</div>
  <table>
    <thead><tr><th>Strategie</th><th>Portfolio</th><th>Rendement</th><th>Gesloten P/L</th><th>Trades</th><th>Winrate</th><th>Open</th></tr></thead>
    <tbody>{strategy_rijen}</tbody>
  </table>
</div>
<div class="section">
  <div class="section-title">Laatste signalen screener (Baseline)</div>
  {'<table><thead><tr><th>Ticker</th><th>Prijs</th><th>Wijz%</th><th>RelVol</th><th>RSI</th><th>VWAP</th><th>EMA</th><th>Score</th></tr></thead><tbody>' + scan_rijen + '</tbody></table>' if scan_resultaten else '<div style="color:var(--muted);padding:24px 12px;font-style:italic">Nog geen scan data</div>'}
</div>
<footer>Trading dashboard — automatisch gegenereerd</footer>
</body>
</html>"""

    return html
```

- [ ] **Step 2: Replace `update_dashboard`**

```python
def update_dashboard(portfolios, scan_resultaten=None):
    html = genereer_dashboard_html(portfolios, scan_resultaten)
    push_naar_github(html)
```

- [ ] **Step 3: Smoke test**

Run:
```
python -c "
from github_dashboard import genereer_dashboard_html
p = [{'naam':'Baseline','startkapitaal':100000,'portfolio_waarde':100500,
      'open_trades':{},'gesloten_trades':[],
      'statistieken':{'totaal':2,'winstgevend':1,'verliesgevend':1,'totaal_resultaat':50.0}}]
html = genereer_dashboard_html(p, None)
print('HTML OK —', len(html), 'chars')
"
```
Expected: `HTML OK — XXXXX chars`

- [ ] **Step 4: Commit**

```
git add github_dashboard.py
git commit -m "feat: combined 6-strategy dashboard — strategy comparison table"
```

---

### Task 8: Full suite + migration

- [ ] **Step 1: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 2: Smoke test full import**

Run:
```
python -c "
from strategies import STRATEGIES
from paper_trading import PaperTradingEngine
from dashboard import score_signals
from obsidian_logger import schrijf_dagboek
from github_dashboard import update_dashboard
print('All imports OK —', len(STRATEGIES), 'strategies')
"
```
Expected: `All imports OK — 6 strategies`

- [ ] **Step 3: Rename existing trades.json (optional — preserves Baseline history)**

```
Rename trades.json → trades_baseline.json
```

Skip if you want a clean start across all 6.

- [ ] **Step 4: Final commit**

```
git add .
git commit -m "feat: complete multi-strategy day trading system — 6 parallel engines"
```
