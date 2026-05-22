from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, TakeProfitRequest, StopLossRequest, GetOrdersRequest
from alpaca.trading.enums import QueryOrderStatus
from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass
from alpaca.data.historical import StockHistoricalDataClient
import json
import os
from datetime import datetime
import pytz

# ─── Keys laden ─────────────────────────────────────────

def laad_keys():
    keys = {}
    with open('alpaca_keys.txt', 'r') as f:
        for regel in f:
            if '=' in regel:
                k, v = regel.strip().split(' = ')
                keys[k.strip()] = v.strip()
    return keys

KEYS = laad_keys()
API_KEY = KEYS['API_KEY']
SECRET_KEY = KEYS['SECRET_KEY']

# ─── Instellingen ────────────────────────────────────────

GESIMULEERD_KAPITAAL = 100000
RISICO_PER_TRADE = 0.02
MAX_BEDRAG_PER_TRADE = 1000   # nooit meer dan $1k per trade
DOEL_PCT = 0.05
STOP_LOSS_PCT = 0.02
LOG_BESTAND = 'trades.json'
MIN_SCORE = 70
NY_TZ = pytz.timezone('America/New_York')

# ─── Alpaca clients ──────────────────────────────────────

trading_client = TradingClient(API_KEY, SECRET_KEY, paper=True)
data_client = StockHistoricalDataClient(API_KEY, SECRET_KEY)


# ─── Hulpfuncties ────────────────────────────────────────

def is_markt_open():
    return trading_client.get_clock().is_open


def haal_huidige_prijs(ticker):
    try:
        import yfinance as yf
        import time
        time.sleep(0.5)  # voorkom rate limiting bij meerdere opvragen achter elkaar
        data = yf.Ticker(ticker).history(period="2d")
        if not data.empty:
            return round(data['Close'].iloc[-1], 2)
    except Exception as e:
        print(f"  Prijs fout {ticker}: {e}")
    return None


def laad_portfolio():
    if os.path.exists(LOG_BESTAND):
        with open(LOG_BESTAND, 'r') as f:
            portfolio = json.load(f)
        # Zorg dat alle keys altijd aanwezig zijn
        portfolio.setdefault('open_trades', {})
        portfolio.setdefault('gesloten_trades', [])
        portfolio.setdefault('statistieken', {
            'totaal': 0, 'winstgevend': 0,
            'verliesgevend': 0, 'totaal_resultaat': 0.0
        })
        portfolio['statistieken'].setdefault('totaal', 0)
        portfolio['statistieken'].setdefault('winstgevend', 0)
        portfolio['statistieken'].setdefault('verliesgevend', 0)
        portfolio['statistieken'].setdefault('totaal_resultaat', 0.0)
        return portfolio
    account = trading_client.get_account()
    return {
        'startkapitaal': float(account.cash),
        'open_trades': {},
        'gesloten_trades': [],
        'statistieken': {
            'totaal': 0, 'winstgevend': 0,
            'verliesgevend': 0, 'totaal_resultaat': 0.0
        }
    }


def sla_portfolio_op(portfolio):
    with open(LOG_BESTAND, 'w') as f:
        json.dump(portfolio, f, indent=2)


# ─── Bracket order plaatsen ──────────────────────────────

def open_trade(portfolio, ticker, prijs, score):
    """
    Opent een bracket order: één order met ingebouwde stop loss én take profit.
    Alpaca beheert de exits automatisch — geen handmatige controle nodig.
    """
    if ticker in portfolio['open_trades']:
        print(f"  {ticker}: al open")
        return

    # Cash check — nooit meer kopen dan er beschikbaar is
    account = trading_client.get_account()
    beschikbaar = float(account.cash)
    if beschikbaar < MAX_BEDRAG_PER_TRADE:
        print(f"  ⛔ Niet genoeg cash voor nieuwe orders — ${beschikbaar:,.2f} beschikbaar (minimum: ${MAX_BEDRAG_PER_TRADE})")
        return

    risico_bedrag = min(GESIMULEERD_KAPITAAL * RISICO_PER_TRADE, MAX_BEDRAG_PER_TRADE)

    # Stop loss minimaal $0.01 van de prijs (Alpaca vereiste)
    # Bereken eerst de stop prijs, dan controleren of het verschil groot genoeg is
    stop_loss_prijs = round(prijs * (1 - STOP_LOSS_PCT), 2)
    if round(prijs - stop_loss_prijs, 2) < 0.01:
        stop_loss_prijs = round(prijs - 0.01, 2)
    if stop_loss_prijs <= 0:
        print(f"  {ticker}: prijs te laag voor stop loss")
        return
    doel_prijs = round(prijs * (1 + DOEL_PCT), 2)
    risico_per_aandeel = prijs - stop_loss_prijs

    # Aantal op basis van risico, maar nooit meer dan MAX_BEDRAG_PER_TRADE waard
    max_aandelen_op_budget = int(MAX_BEDRAG_PER_TRADE / prijs)
    aantal = min(int(risico_bedrag / risico_per_aandeel), max_aandelen_op_budget)

    if aantal < 1:
        print(f"  {ticker}: te weinig kapitaal")
        return

    try:
        order = MarketOrderRequest(
            symbol=ticker,
            qty=aantal,
            side=OrderSide.BUY,
            time_in_force=TimeInForce.DAY,
            order_class=OrderClass.BRACKET,          # ← bracket order
            take_profit=TakeProfitRequest(
                limit_price=doel_prijs               # ← automatische take profit
            ),
            stop_loss=StopLossRequest(
                stop_price=stop_loss_prijs           # ← automatische stop loss
            )
        )
        trading_client.submit_order(order)

        portfolio['open_trades'][ticker] = {
            'ticker': ticker,
            'instap_prijs': prijs,
            'aantal': aantal,
            'stop_loss': stop_loss_prijs,
            'doel': doel_prijs,
            'score': score,
            'tijdstip': datetime.now().strftime('%d/%m/%Y %H:%M')
        }
        print(
            f"  ✅ BRACKET ORDER: {aantal}x {ticker} @ ${prijs} "
            f"| Stop: ${stop_loss_prijs} | Doel: ${doel_prijs}"
        )
    except Exception as e:
        fout = str(e)
        if 'not tradable' in fout:
            print(f"  ⛔ {ticker}: niet tradable op Alpaca — overgeslagen")
        elif 'stop_loss' in fout:
            print(f"  ⛔ {ticker}: stop loss prijs probleem (prijs ${prijs}) — overgeslagen")
        else:
            print(f"  Order fout {ticker}: {e}")


# ─── Handmatig sluiten (markt sluit) ────────────────────

def sluit_trade(portfolio, ticker, prijs, reden):
    """
    Sluit een positie handmatig — wordt alleen gebruikt bij 'Markt sluit'.
    Normaal sluit Alpaca de bracket orders zelf via stop/take profit.
    """
    if ticker not in portfolio['open_trades']:
        return

    trade = portfolio['open_trades'][ticker]

    try:
        # Annuleer openstaande bracket legs eerst via alle open orders
        alle_orders = trading_client.get_orders()
        for order in alle_orders:
            if str(order.symbol) == ticker:
                try:
                    trading_client.cancel_order_by_id(order.id)
                except:
                    pass
    except Exception as e:
        print(f"  Annuleer fout {ticker}: {e}")

    # Check of positie nog echt open staat bij Alpaca
    try:
        posities = {p.symbol for p in trading_client.get_all_positions()}
        if ticker not in posities:
            print(f"  {ticker}: positie al gesloten door Alpaca bracket")
            del portfolio['open_trades'][ticker]
            return
    except:
        pass

    try:
        order = MarketOrderRequest(
            symbol=ticker,
            qty=trade['aantal'],
            side=OrderSide.SELL,
            time_in_force=TimeInForce.DAY
        )
        trading_client.submit_order(order)
    except Exception as e:
        print(f"  Verkoop fout {ticker}: {e}")
        return

    kosten = round(trade['aantal'] * trade['instap_prijs'], 2)
    opbrengst = round(trade['aantal'] * prijs, 2)
    resultaat = round(opbrengst - kosten, 2)
    resultaat_pct = round((resultaat / kosten) * 100, 2)

    portfolio['gesloten_trades'].append({
        **trade,
        'uitstap_prijs': prijs,
        'resultaat': resultaat,
        'resultaat_pct': resultaat_pct,
        'reden': reden,
        'gesloten_op': datetime.now().strftime('%d/%m/%Y %H:%M')
    })
    portfolio['statistieken']['totaal'] += 1
    portfolio['statistieken']['totaal_resultaat'] += resultaat

    if resultaat > 0:
        portfolio['statistieken']['winstgevend'] += 1
        print(f"  💰 WINST: {ticker} @ ${prijs} | +${resultaat} (+{resultaat_pct}%) | {reden}")
    else:
        portfolio['statistieken']['verliesgevend'] += 1
        print(f"  ❌ VERLIES: {ticker} @ ${prijs} | ${resultaat} ({resultaat_pct}%) | {reden}")

    del portfolio['open_trades'][ticker]


def sluit_alle_trades(portfolio):
    print("\n  Markt sluit — alle posities sluiten...")
    for ticker in list(portfolio['open_trades'].keys()):
        prijs = haal_huidige_prijs(ticker)
        if prijs:
            sluit_trade(portfolio, ticker, prijs, 'Markt sluit')


# ─── Open trades syncen met Alpaca ──────────────────────

def haal_order_data_op(ticker):
    """
    Haalt de meest recente gesloten sell order op via Alpaca.
    Geeft exacte uitvoerprijs en tijdstip terug.
    """
    try:
        orders = trading_client.get_orders(filter=GetOrdersRequest(
            status=QueryOrderStatus.CLOSED,
            symbols=[ticker],
            limit=5
        ))
        # Zoek meest recente sell order die filled is
        for order in orders:
            if str(order.side) == 'OrderSide.SELL' and str(order.status) in ('OrderStatus.FILLED', 'filled'):
                prijs = float(order.filled_avg_price) if order.filled_avg_price else None
                tijdstip = order.filled_at.strftime('%d/%m/%Y %H:%M') if order.filled_at else None
                return prijs, tijdstip
    except Exception as e:
        print(f"  Order data fout {ticker}: {e}")
    return None, None


def sync_gesloten_trades(portfolio):
    """
    Controleert via Alpaca welke bracket orders al geraakt zijn.
    Gebruikt exacte Alpaca order data voor uitvoerprijs en tijdstip.
    """
    try:
        alpaca_posities = {
            p.symbol for p in trading_client.get_all_positions()
        }
    except Exception as e:
        print(f"  Sync fout: {e}")
        return

    for ticker in list(portfolio['open_trades'].keys()):
        if ticker not in alpaca_posities:
            trade = portfolio['open_trades'][ticker]

            # Haal exacte Alpaca order data op
            alpaca_prijs, alpaca_tijdstip = haal_order_data_op(ticker)
            prijs = alpaca_prijs or haal_huidige_prijs(ticker) or trade['instap_prijs']
            tijdstip = alpaca_tijdstip or datetime.now().strftime('%d/%m/%Y %H:%M')

            kosten = trade['aantal'] * trade['instap_prijs']
            opbrengst = trade['aantal'] * prijs
            resultaat = round(opbrengst - kosten, 2)
            resultaat_pct = round((resultaat / kosten) * 100, 2)

            reden = 'Doel bereikt' if prijs >= trade['doel'] else 'Stop loss'

            portfolio['gesloten_trades'].append({
                **trade,
                'uitstap_prijs': prijs,
                'resultaat': resultaat,
                'resultaat_pct': resultaat_pct,
                'reden': reden,
                'gesloten_op': tijdstip  # ← exact Alpaca tijdstip
            })
            portfolio['statistieken']['totaal'] += 1
            portfolio['statistieken']['totaal_resultaat'] += resultaat

            if resultaat > 0:
                portfolio['statistieken']['winstgevend'] += 1
                print(f"  💰 BRACKET HIT: {ticker} +${resultaat} (+{resultaat_pct}%) | {reden} | {tijdstip}")
            else:
                portfolio['statistieken']['verliesgevend'] += 1
                print(f"  ❌ BRACKET HIT: {ticker} ${resultaat} ({resultaat_pct}%) | {reden} | {tijdstip}")

            del portfolio['open_trades'][ticker]


# ─── Overzicht ───────────────────────────────────────────

def toon_overzicht(portfolio):
    account = trading_client.get_account()
    portfolio_waarde = float(account.portfolio_value)
    startkapitaal = portfolio['startkapitaal']
    rendement = round(((portfolio_waarde - startkapitaal) / startkapitaal) * 100, 2)
    stats = portfolio['statistieken']

    print("\n" + "=" * 55)
    print("  PAPER TRADING OVERZICHT")
    print("=" * 55)
    print(f"  Startkapitaal:     ${startkapitaal:>10,.2f}")
    print(f"  Portfolio waarde:  ${portfolio_waarde:>10,.2f}")
    print(f"  Totaal rendement:  {rendement:>10}%")
    print("-" * 55)
    print(f"  Totaal trades:     {stats['totaal']:>10}")
    print(f"  Winstgevend:       {stats['winstgevend']:>10}")
    print(f"  Verliesgevend:     {stats['verliesgevend']:>10}")
    if stats['totaal'] > 0:
        winrate = round((stats['winstgevend'] / stats['totaal']) * 100, 1)
        print(f"  Winrate:           {winrate:>9}%")
    print("=" * 55)

    if portfolio['open_trades']:
        print(f"\n  OPEN POSITIES ({len(portfolio["open_trades"])} bracket actief):")
        print(f"  {'Ticker':<8} {'Instap':>8} {'Huidig':>8} {'Doel':>8} {'Stop':>8} {'P/L':>8}")
        print("  " + "-" * 50)
        for t in portfolio['open_trades'].values():
            huidig = haal_huidige_prijs(t['ticker']) or t['instap_prijs']
            pl = round(((huidig - t['instap_prijs']) / t['instap_prijs']) * 100, 2)
            print(f"  {t['ticker']:<8} ${t['instap_prijs']:>7} ${huidig:>7} ${t['doel']:>7} ${t['stop_loss']:>7} {pl:>7}%")

    if portfolio['gesloten_trades']:
        print(f"\n  RECENTE GESLOTEN TRADES ({len(portfolio["gesloten_trades"])} totaal):")
        print(f"  {'Ticker':<8} {'Instap':>8} {'Uitstap':>8} {'Resultaat':>10} {'Reden':<15}")
        print("  " + "-" * 55)
        for t in portfolio['gesloten_trades'][-10:]:
            print(f"  {t['ticker']:<8} ${t['instap_prijs']:>7} ${t['uitstap_prijs']:>7} {t['resultaat_pct']:>9}% {t['reden']:<15}")


# ─── Hoofd entry point ───────────────────────────────────

def run_paper_trading(signalen=None):
    portfolio = laad_portfolio()

    print("\n" + "=" * 55)
    print("  PAPER TRADING GESTART")
    print("=" * 55)

    if not is_markt_open():
        print("  Markt is gesloten — alleen overzicht tonen")
        toon_overzicht(portfolio)
        sla_portfolio_op(portfolio)
        return

    # Sync: welke bracket orders heeft Alpaca al gesloten?
    print("\n  Bracket orders syncen met Alpaca...")
    sync_gesloten_trades(portfolio)

    # Nieuwe signalen verwerken
    if signalen:
        print("\n  Nieuwe signalen verwerken...")
        for s in signalen:
            if s.get('score', 0) >= MIN_SCORE:
                # Gebruik prijs uit signaal — net opgehaald door screener
                # Alleen opnieuw ophalen als het signaal geen prijs bevat
                prijs = s.get('prijs') or haal_huidige_prijs(s['ticker'])
                if prijs:
                    open_trade(portfolio, s['ticker'], prijs, s['score'])

    sla_portfolio_op(portfolio)
    toon_overzicht(portfolio)

    # Geef de trades terug die in déze cyclus gesloten zijn
    # (main.py verzamelt ze over alle cycli voor het dagboek)
    return portfolio['gesloten_trades']


if __name__ == "__main__":
    run_paper_trading()
