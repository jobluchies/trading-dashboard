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
