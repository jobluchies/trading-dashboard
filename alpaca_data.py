from datetime import datetime, timedelta

import pytz
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import (
    StockBarsRequest,
    StockLatestTradeRequest,
    StockSnapshotRequest,
)
from alpaca.data.timeframe import TimeFrame
from alpaca.data.enums import DataFeed

from strategies import laad_wallet_keys

CHUNK_SIZE = 200

_client = None


def _get_client():
    global _client
    if _client is None:
        keys = laad_wallet_keys('Trading Tool 1')
        _client = StockHistoricalDataClient(keys['API_KEY'], keys['SECRET_KEY'])
    return _client


def haal_bars_bulk(tickers, days=62):
    """
    Bulk dagelijkse OHLCV bars voor RSI/EMA/volume berekeningen.
    Haalt alle tickers op in chunks van 500 (typisch 8-10 requests voor ~4000 tickers).
    Geeft {ticker: {'c': [...], 'h': [...], 'l': [...], 'v': [...]}} terug.
    """
    client = _get_client()
    start = datetime.now(pytz.UTC) - timedelta(days=days + 10)  # +10 voor weekenden/feestdagen
    eind = datetime.now(pytz.UTC)

    resultaten = {}
    totaal_chunks = (len(tickers) + CHUNK_SIZE - 1) // CHUNK_SIZE

    for i in range(0, len(tickers), CHUNK_SIZE):
        chunk = tickers[i:i + CHUNK_SIZE]
        chunk_nr = i // CHUNK_SIZE + 1
        print(f"  Alpaca bars: chunk {chunk_nr}/{totaal_chunks} ({len(resultaten) + len(chunk)}/{len(tickers)} tickers)")
        try:
            request = StockBarsRequest(
                symbol_or_symbols=chunk,
                timeframe=TimeFrame.Day,
                start=start,
                end=eind,
                feed=DataFeed.IEX,
            )
            bars = client.get_stock_bars(request)
            for symbol, bar_list in bars.data.items():
                if len(bar_list) >= 25:
                    resultaten[symbol] = {
                        'c': [b.close for b in bar_list],
                        'h': [b.high for b in bar_list],
                        'l': [b.low for b in bar_list],
                        'v': [b.volume for b in bar_list],
                    }
        except Exception as e:
            print(f"  Alpaca bars fout chunk {chunk_nr}: {e}")

    return resultaten


def haal_snapshots_bulk(tickers):
    """
    Bulk real-time snapshots voor de kleine scan.
    Eén request geeft per ticker: actuele prijs, dagelijkse H/L, vorige sluit.
    Geeft {ticker: {'prijs': x, 'hoog': h, 'laag': l, 'vorige_sluit': v}} terug.
    """
    client = _get_client()
    resultaten = {}

    for i in range(0, len(tickers), CHUNK_SIZE):
        chunk = tickers[i:i + CHUNK_SIZE]
        try:
            snapshots = client.get_stock_snapshot(StockSnapshotRequest(symbol_or_symbols=chunk, feed=DataFeed.IEX))
            for symbol, snap in snapshots.items():
                try:
                    prijs = snap.latest_trade.price if snap.latest_trade else None
                    if not prijs and snap.daily_bar:
                        prijs = snap.daily_bar.close
                    resultaten[symbol] = {
                        'prijs':        prijs,
                        'hoog':         snap.daily_bar.high if snap.daily_bar else None,
                        'laag':         snap.daily_bar.low if snap.daily_bar else None,
                        'vorige_sluit': snap.previous_daily_bar.close if snap.previous_daily_bar else None,
                    }
                except Exception:
                    pass
        except Exception as e:
            print(f"  Alpaca snapshot fout: {e}")

    return resultaten


def haal_huidige_prijs(ticker):
    """Enkele real-time prijs voor een open positie."""
    client = _get_client()
    try:
        trades = client.get_stock_latest_trade(StockLatestTradeRequest(symbol_or_symbols=[ticker]))
        trade = trades.get(ticker)
        if trade:
            return round(trade.price, 2)
    except Exception:
        pass
    return None
