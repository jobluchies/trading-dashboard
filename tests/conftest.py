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
