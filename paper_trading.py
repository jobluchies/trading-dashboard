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


def _klok_client():
    keys = laad_wallet_keys('Trading Tool 1')
    return TradingClient(keys['API_KEY'], keys['SECRET_KEY'], paper=True)

trading_client = _klok_client()


def is_markt_open():
    return trading_client.get_clock().is_open


def haal_huidige_prijs(ticker):
    try:
        import alpaca_data
        return alpaca_data.haal_huidige_prijs(ticker)
    except Exception as e:
        print(f"  Prijs fout {ticker}: {e}")
    return None


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
                portfolio = json.load(f)
            portfolio.setdefault('open_trades', {})
            portfolio.setdefault('gesloten_trades', [])
            portfolio.setdefault('statistieken', {
                'totaal': 0, 'winstgevend': 0, 'verliesgevend': 0, 'totaal_resultaat': 0.0
            })
            for k in ('totaal', 'winstgevend', 'verliesgevend', 'totaal_resultaat'):
                portfolio['statistieken'].setdefault(k, 0 if k != 'totaal_resultaat' else 0.0)
            return portfolio
        account = self.trading_client.get_account()
        return {
            'startkapitaal': float(account.cash),
            'open_trades': {},
            'gesloten_trades': [],
            'statistieken': {
                'totaal': 0, 'winstgevend': 0, 'verliesgevend': 0, 'totaal_resultaat': 0.0
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
