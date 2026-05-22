import yfinance as yf
import urllib.request
import json
from datetime import datetime
from cache_manager import (
    laad_ticker_cache, sla_ticker_cache_op,
    laad_shortlist_cache, sla_shortlist_cache_op,
    sla_scan_historie_op
)

# ─── Instellingen ───────────────────────────────────────
TOP_RESULTATEN = 50
SHORTLIST_GROOTTE = 75
MIN_PRIJS = 5
MAX_PRIJS = 150
MIN_VOLUME = 500000

# ─── Scoring parameters — hier aanpassen, snapshot pikt ze automatisch op ───

SCORE_BASIS = 50.0

# VWAP
VWAP_BOVEN_MULT   = 1.15
VWAP_ONDER_MULT   = 0.85

# RSI zones (grens, multiplier) — van laag naar hoog
RSI_ZONES = [
    (25,  1.35),   # RSI < 25
    (35,  1.20),   # RSI < 35
    (45,  1.08),   # RSI < 45
    (55,  1.00),   # RSI 45-55 neutraal
    (65,  0.92),   # RSI > 55
    (75,  0.80),   # RSI > 65
    (999, 0.65),   # RSI > 75
]

# Relatief volume (grens, mult_positief, mult_negatief)
VOLUME_ZONES = [
    (5,   1.50, 0.50),
    (3,   1.35, 0.65),
    (1.5, 1.18, 0.82),
    (0,   0.92, 0.92),   # laag volume — altijd licht negatief
]

# Dagverandering % (van hoog naar laag)
VERANDERING_ZONES = [
    (6,    1.25),
    (3,    1.14),
    (1,    1.06),
    (-1,   1.00),  # -1% tot +1% neutraal
    (-3,   0.94),
    (-6,   0.86),
    (-999, 0.75),
]

# EMA status
EMA_MULTIPLIERS = {
    'KRUIS OMHOOG':  1.28,
    'KRUIS OMLAAG':  0.72,
    'EMA BULL':      1.12,
    'EMA BEAR':      0.88,
}

# Tegenstrijdigheid penalties/bonussen
PENALTY_STIJGING_ONDER_VWAP        = 0.90   # verandering > 2% maar onder VWAP
PENALTY_HOGE_RSI_BIJ_KRUIS_OMHOOG  = 0.88   # RSI > 65 + KRUIS OMHOOG
BONUS_LAGE_RSI_BIJ_KRUIS_OMLAAG    = 1.10   # RSI < 35 + KRUIS OMLAAG

# Drempelwaarden
MIN_SCORE        = 70
MIN_BEWEGING_PCT = 3.0
MIN_REL_VOLUME   = 1.5

# Trade parameters
GESIMULEERD_KAPITAAL = 100000
RISICO_PER_TRADE     = 0.02
DOEL_PCT             = 0.05
STOP_LOSS_PCT        = 0.02


# ─── Scoring snapshot ────────────────────────────────────

def scoring_snapshot():
    """
    Geeft een dict met alle scoring parameters zoals ze nu ingesteld zijn.
    Wordt meegeschreven in het Obsidian dagboek en elke trade-notitie,
    zodat je later exact weet met welke versie van het systeem gehandeld werd.
    """
    return {
        'versie': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'score_basis': SCORE_BASIS,
        'vwap': {
            'boven': VWAP_BOVEN_MULT,
            'onder': VWAP_ONDER_MULT,
        },
        'rsi_zones': [
            {'grens': g, 'multiplier': m} for g, m in RSI_ZONES
        ],
        'volume_zones': [
            {'grens': g, 'mult_pos': mp, 'mult_neg': mn}
            for g, mp, mn in VOLUME_ZONES
        ],
        'verandering_zones': [
            {'grens': g, 'multiplier': m} for g, m in VERANDERING_ZONES
        ],
        'ema_multipliers': EMA_MULTIPLIERS,
        'penalties': {
            'stijging_onder_vwap':        PENALTY_STIJGING_ONDER_VWAP,
            'hoge_rsi_bij_kruis_omhoog':  PENALTY_HOGE_RSI_BIJ_KRUIS_OMHOOG,
            'bonus_lage_rsi_bij_kruis_omlaag': BONUS_LAGE_RSI_BIJ_KRUIS_OMLAAG,
        },
        'drempelwaarden': {
            'min_score':        MIN_SCORE,
            'min_beweging_pct': MIN_BEWEGING_PCT,
            'min_rel_volume':   MIN_REL_VOLUME,
        },
        'trade_parameters': {
            'gesimuleerd_kapitaal':  GESIMULEERD_KAPITAAL,
            'risico_per_trade_pct':  RISICO_PER_TRADE * 100,
            'doel_pct':              DOEL_PCT * 100,
            'stop_loss_pct':         STOP_LOSS_PCT * 100,
        }
    }


# ─── Ticker ophalen (met Cache 1) ────────────────────────

def haal_alle_tickers_op():
    gecached = laad_ticker_cache()
    if gecached:
        return gecached

    print("  Ophalen lijst van alle aandelen...")
    tickers = []
    urls = [
        'https://raw.githubusercontent.com/datasets/nasdaq-listings/master/data/nasdaq-listed-symbols.csv',
        'https://raw.githubusercontent.com/datasets/nyse-listings/master/data/nyse-listed.csv'
    ]
    headers = {'User-Agent': 'Mozilla/5.0'}
    for url in urls:
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as response:
                lines = response.read().decode('utf-8').splitlines()
                for line in lines[1:]:
                    parts = line.split(',')
                    if parts:
                        ticker = parts[0].strip().replace('"', '')
                        if ticker and '/' not in ticker and len(ticker) <= 5:
                            tickers.append(ticker)
        except Exception as e:
            print(f"  Fout bij ophalen lijst: {e}")

    print(f"  {len(tickers)} aandelen gevonden")
    sla_ticker_cache_op(tickers)
    return tickers


# ─── Technische berekeningen ─────────────────────────────

def bereken_rsi(closes, periode=14):
    winst, verlies = [], []
    for i in range(1, len(closes)):
        v = closes[i] - closes[i - 1]
        winst.append(v if v > 0 else 0)
        verlies.append(abs(v) if v < 0 else 0)
    gem_w = sum(winst[-periode:]) / periode
    gem_v = sum(verlies[-periode:]) / periode
    if gem_v == 0:
        return 100
    return round(100 - (100 / (1 + gem_w / gem_v)), 1)


def bereken_ema(closes, periode):
    m = 2 / (periode + 1)
    ema = closes[0]
    for p in closes[1:]:
        ema = (p * m) + (ema * (1 - m))
    return round(ema, 2)


def detecteer_ema_crossover(closes):
    e9g = bereken_ema(closes[:-1], 9)
    e20g = bereken_ema(closes[:-1], 20)
    e9h = bereken_ema(closes, 9)
    e20h = bereken_ema(closes, 20)
    if e9g < e20g and e9h > e20h:
        return 'KRUIS OMHOOG', e9h, e20h
    elif e9g > e20g and e9h < e20h:
        return 'KRUIS OMLAAG', e9h, e20h
    elif e9h > e20h:
        return 'EMA BULL', e9h, e20h
    else:
        return 'EMA BEAR', e9h, e20h


def bereken_confluence_score(data):
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
            score *= mp if pos else mn
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


# ─── Data ophalen per ticker ──────────────────────────────

def haal_data_op(ticker):
    try:
        aandeel = yf.Ticker(ticker)
        historie = aandeel.history(period="60d")
        if historie.empty or len(historie) < 25:
            return None
        sluitkoersen = list(historie['Close'])
        volumes = list(historie['Volume'])
        prijs = round(sluitkoersen[-1], 2)
        vorige = sluitkoersen[-2]
        verandering = round(prijs - vorige, 2)
        verandering_pct = round((verandering / vorige) * 100, 2)
        gem_volume = sum(volumes[:-1]) / len(volumes[:-1])
        rel_volume = round(volumes[-1] / gem_volume, 2)
        rsi = bereken_rsi(sluitkoersen)
        hoog = historie['High'].iloc[-1]
        laag = historie['Low'].iloc[-1]
        vwap = round((hoog + laag + prijs) / 3, 2)
        boven_vwap = prijs >= vwap
        ema_status, ema9, ema20 = detecteer_ema_crossover(sluitkoersen)
        return {
            'ticker': ticker,
            'prijs': prijs,
            'verandering': verandering,
            'verandering_pct': verandering_pct,
            'rel_volume': rel_volume,
            'rsi': rsi,
            'boven_vwap': boven_vwap,
            'ema_status': ema_status,
            'ema9': ema9,
            'ema20': ema20
        }
    except:
        return None


# ─── Dashboard weergave ───────────────────────────────────

def toon_dashboard(resultaten):
    print("\n" + "=" * 80)
    print(f"  DAY TRADE SCREENER  |  {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print("=" * 80)
    print(f"{'Ticker':<8} {'Prijs':>8} {'Wijz%':>7} {'RelVol':>7} {'RSI':>6} {'VWAP':>7} {'EMA':>12} {'Score':>6} {'Signaal':<10}")
    print("-" * 80)

    for d in resultaten:
        vwap_label = "BOVEN" if d['boven_vwap'] else "ONDER"
        ema_kort = {
            'KRUIS OMHOOG': '↑ KRUIS', 'KRUIS OMLAAG': '↓ KRUIS',
            'EMA BULL': '↑ BULL',     'EMA BEAR':     '↓ BEAR'
        }.get(d['ema_status'], d['ema_status'])
        signaal = '🟢 BULLISH' if d['score'] >= 65 else '🔴 BEARISH' if d['score'] <= 35 else '⚪ NEUTRAAL'
        print(f"{d['ticker']:<8} ${d['prijs']:>7} {d['verandering_pct']:>6}% {d['rel_volume']:>7}x {d['rsi']:>6} {vwap_label:>7} {ema_kort:>12} {d['score']:>6} {signaal:<10}")

    print("-" * 80)
    bull = sum(1 for d in resultaten if d['score'] >= 65)
    bear = sum(1 for d in resultaten if d['score'] <= 35)
    print(f"  Bullish: {bull}  |  Bearish: {bear}  |  Neutraal: {len(resultaten) - bull - bear}")
    print("=" * 80)

    kruisingen = [d for d in resultaten if 'KRUIS' in d['ema_status']]
    if kruisingen:
        print("\n  EMA KRUISINGEN:")
        for d in kruisingen:
            richting = "omhoog" if d['ema_status'] == 'KRUIS OMHOOG' else "omlaag"
            print(f"  {d['ticker']}: 9 EMA kruist {richting}  |  Score: {d['score']}  →  sterk signaal!")


# ─── Scan statistieken ───────────────────────────────────

def bereken_scan_statistieken(resultaten):
    """
    Geeft een overzicht van de score-verdeling van de volledige shortlist.
    Wordt meegeschreven in het dagboek zodat je achteraf kunt beoordelen
    of je drempelwaarden te streng of te los waren.
    """
    if not resultaten:
        return {}

    scores = [d['score'] for d in resultaten]
    handelbaar  = [d for d in resultaten if d['score'] >= MIN_SCORE]
    bullish     = [d for d in resultaten if 65 <= d['score'] < MIN_SCORE]
    neutraal    = [d for d in resultaten if 35 < d['score'] < 65]
    bearish     = [d for d in resultaten if d['score'] <= 35]

    hoogste = max(resultaten, key=lambda x: x['score'])
    laagste = min(resultaten, key=lambda x: x['score'])

    return {
        'shortlist_grootte':   len(resultaten),
        'score_verdeling': {
            f'handelbaar_score_boven_{MIN_SCORE}': len(handelbaar),
            'bullish_65_tot_min_score':            len(bullish),
            'neutraal_35_tot_65':                  len(neutraal),
            'bearish_onder_35':                    len(bearish),
        },
        'hoogste_score': {'ticker': hoogste['ticker'], 'score': hoogste['score']},
        'laagste_score': {'ticker': laagste['ticker'], 'score': laagste['score']},
        'gemiddelde_score': round(sum(scores) / len(scores), 1),
    }


# ─── Grote scan (16:00) ───────────────────────────────────

def grote_scan(alle_tickers):
    print(f"\n  🔍 GROTE SCAN — {len(alle_tickers)} tickers analyseren...")
    print("  Dit duurt een paar minuten — even geduld...\n")

    resultaten = []
    for i, ticker in enumerate(alle_tickers):
        if i % 100 == 0:
            print(f"  Voortgang: {i}/{len(alle_tickers)} ({round(i / len(alle_tickers) * 100)}%)")
        data = haal_data_op(ticker)
        if data:
            if abs(data['verandering_pct']) > MIN_BEWEGING_PCT and data['rel_volume'] > MIN_REL_VOLUME:
                data['score'] = bereken_confluence_score(data)
                resultaten.append(data)

    resultaten.sort(key=lambda x: abs(x['score'] - 50), reverse=True)
    shortlist_data = resultaten[:SHORTLIST_GROOTTE]  # shortlist bewaart extremen in beide richtingen
    sla_shortlist_cache_op([d['ticker'] for d in shortlist_data])
    print(f"\n  ✅ Grote scan klaar — {len(shortlist_data)} aandelen in shortlist")
    return shortlist_data


# ─── Kleine scan (elke 30 min) ────────────────────────────

def kleine_scan(shortlist_tickers):
    print(f"\n  🔄 KLEINE SCAN — {len(shortlist_tickers)} shortlist aandelen refreshen...")

    resultaten = []
    for ticker in shortlist_tickers:
        data = haal_data_op(ticker)
        if data:
            data['score'] = bereken_confluence_score(data)
            resultaten.append(data)

    # Sorteer hoog naar laag — alleen bullish signalen teruggeven
    resultaten.sort(key=lambda x: x['score'], reverse=True)
    resultaten = [r for r in resultaten if r['score'] >= 65]
    print(f"  ✅ Kleine scan klaar — {len(resultaten)} bullish aandelen geanalyseerd")
    return resultaten


# ─── Hoofd entry point ────────────────────────────────────

def run_screener():
    print("\n  DAY TRADE SCREENER GESTART")
    print("  " + "=" * 40)

    alle_tickers = haal_alle_tickers_op()
    if not alle_tickers:
        print("  Kon geen tickers ophalen. Controleer je internetverbinding.")
        return []

    shortlist_tickers, grote_scan_nodig = laad_shortlist_cache()
    resultaten = grote_scan(alle_tickers) if grote_scan_nodig else kleine_scan(shortlist_tickers)

    print(f"\n  Top {TOP_RESULTATEN} meest extreme signalen:\n")
    toon_dashboard(resultaten[:TOP_RESULTATEN])
    sla_scan_historie_op(resultaten)

    stats = bereken_scan_statistieken(resultaten)
    return resultaten, stats


if __name__ == "__main__":
    run_screener()
