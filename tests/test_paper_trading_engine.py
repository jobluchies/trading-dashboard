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
