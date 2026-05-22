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
