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
