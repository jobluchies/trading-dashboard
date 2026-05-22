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
