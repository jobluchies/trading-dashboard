import json
import os
from datetime import datetime, date

CACHE_BESTAND_TICKERS = 'cache_tickers.json'
CACHE_BESTAND_SHORTLIST = 'cache_shortlist.json'


# ─────────────────────────────────────────────
#  Cache 1 — Tickerlijst (1x per dag)
# ─────────────────────────────────────────────

def laad_ticker_cache():
    """Geeft de gecachede tickerlijst terug als die van vandaag is, anders None."""
    if not os.path.exists(CACHE_BESTAND_TICKERS):
        return None
    with open(CACHE_BESTAND_TICKERS, 'r') as f:
        data = json.load(f)
    if data.get('datum') == str(date.today()):
        print(f"  ✅ Ticker cache geladen — {len(data['tickers'])} tickers (van vandaag)")
        return data['tickers']
    print("  ♻️  Ticker cache verlopen — nieuwe lijst ophalen")
    return None


def sla_ticker_cache_op(tickers):
    """Slaat de tickerlijst op met de datum van vandaag."""
    with open(CACHE_BESTAND_TICKERS, 'w') as f:
        json.dump({'datum': str(date.today()), 'tickers': tickers}, f)
    print(f"  💾 Ticker cache opgeslagen — {len(tickers)} tickers")


# ─────────────────────────────────────────────
#  Cache 2 — Shortlist (aangemaakt bij 16:00 scan)
# ─────────────────────────────────────────────

def laad_shortlist_cache():
    """
    Geeft de shortlist terug als die van vandaag is.
    Geeft ook mee of het de eerste scan is (grote scan nodig).
    """
    if not os.path.exists(CACHE_BESTAND_SHORTLIST):
        return None, True  # geen cache → grote scan nodig

    with open(CACHE_BESTAND_SHORTLIST, 'r') as f:
        data = json.load(f)

    if data.get('datum') != str(date.today()):
        print("  ♻️  Shortlist cache verlopen — grote scan nodig")
        return None, True  # nieuwe dag → grote scan

    tickers = data['tickers']
    tijdstip = data.get('aangemaakt_om', 'onbekend')
    print(f"  ✅ Shortlist cache geladen — {len(tickers)} aandelen (aangemaakt om {tijdstip})")
    return tickers, False  # cache geldig → kleine scan


def sla_shortlist_cache_op(tickers):
    """Slaat de shortlist op (lijst van ticker-strings)."""
    with open(CACHE_BESTAND_SHORTLIST, 'w') as f:
        json.dump({
            'datum': str(date.today()),
            'aangemaakt_om': datetime.now().strftime('%H:%M'),
            'tickers': tickers
        }, f, indent=2)
    print(f"  💾 Shortlist cache opgeslagen — {len(tickers)} aandelen")


def verwijder_shortlist_cache():
    """Forceert een nieuwe grote scan bij de volgende run."""
    if os.path.exists(CACHE_BESTAND_SHORTLIST):
        os.remove(CACHE_BESTAND_SHORTLIST)
        print("  🗑️  Shortlist cache verwijderd — volgende run doet grote scan")


# ─────────────────────────────────────────────
#  Scan historie — volledige shortlist data per scan
# ─────────────────────────────────────────────

def sla_scan_historie_op(resultaten):
    """
    Slaat de volledige shortlist data op per scan (datum + tijdstip).
    Elke scan wordt toegevoegd aan het dagbestand, zodat je meerdere
    scans per dag kunt terugkijken.
    """
    import os
    os.makedirs('scan_historie', exist_ok=True)

    bestand = os.path.join('scan_historie', f"{date.today()}.json")

    # Laad bestaand bestand als het er al is
    if os.path.exists(bestand):
        try:
            with open(bestand, 'r') as f:
                dag_data = json.load(f)
        except json.JSONDecodeError:
            print("  ⚠️  Scan historie bestand corrupt — opnieuw beginnen")
            dag_data = []
    else:
        dag_data = []

    dag_data.append({
        'tijdstip': datetime.now().strftime('%H:%M'),
        'aantal':   len(resultaten),
        'aandelen': resultaten
    })

    with open(bestand, 'w') as f:
        json.dump(dag_data, f, indent=2, default=lambda o: bool(o) if hasattr(o, 'item') else str(o))

    print(f"  💾 Scan historie opgeslagen — {len(resultaten)} aandelen ({datetime.now().strftime('%H:%M')})")
