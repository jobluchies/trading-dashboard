import os
import json
import yfinance as yf
from datetime import datetime
from dashboard import scoring_snapshot

# Pad naar je Obsidian vault
OBSIDIAN_PAD = r"C:\Users\joblu\trading_tool\Trading Journal"


# ─── Marktdata ────────────────────────────────────────────

def haal_markt_data_op():
    try:
        sp500  = yf.Ticker("^GSPC").history(period="2d")
        nasdaq = yf.Ticker("^IXIC").history(period="2d")
        vix    = yf.Ticker("^VIX").history(period="2d")

        sp500_pct  = round(((sp500['Close'].iloc[-1]  - sp500['Close'].iloc[-2])  / sp500['Close'].iloc[-2])  * 100, 2)
        nasdaq_pct = round(((nasdaq['Close'].iloc[-1] - nasdaq['Close'].iloc[-2]) / nasdaq['Close'].iloc[-2]) * 100, 2)
        vix_stand  = round(vix['Close'].iloc[-1], 2)

        sentiment = "bullish" if sp500_pct > 0.5 else "bearish" if sp500_pct < -0.5 else "neutraal"
        vix_label = "laag (<15)" if vix_stand < 15 else "hoog (>20)" if vix_stand > 20 else "normaal (15-20)"

        return {
            'sp500': sp500_pct, 'nasdaq': nasdaq_pct,
            'vix': vix_stand, 'vix_label': vix_label, 'sentiment': sentiment
        }
    except Exception as e:
        print(f"Fout bij ophalen marktdata: {e}")
        return None


# ─── Automatische observaties ─────────────────────────────

def genereer_observaties(trades, markt):
    if not trades:
        return "- Geen trades vandaag"

    observaties = []
    winst_trades  = [t for t in trades if t['resultaat'] > 0]
    verlies_trades = [t for t in trades if t['resultaat'] < 0]

    if verlies_trades:
        gem_vol_verlies = sum(t.get('rel_volume', 0) for t in verlies_trades) / len(verlies_trades)
        gem_vol_winst   = sum(t.get('rel_volume', 0) for t in winst_trades)   / len(winst_trades) if winst_trades else 0
        if gem_vol_verlies < gem_vol_winst * 0.7:
            observaties.append(f"⚠️ Verliezende trades hadden gemiddeld {gem_vol_verlies:.1f}x volume vs {gem_vol_winst:.1f}x bij winstgevende trades — overweeg volume drempel te verhogen")

    if verlies_trades:
        gem_rsi_verlies = sum(t['rsi'] for t in verlies_trades) / len(verlies_trades)
        if gem_rsi_verlies > 60:
            observaties.append(f"⚠️ Verliezende trades hadden gemiddelde RSI van {gem_rsi_verlies:.1f} — mogelijk te overbought ingekocht")

    if markt and markt['vix'] > 20 and len(verlies_trades) > len(trades) / 2:
        observaties.append(f"🔴 VIX was {markt['vix']} (hoog) — meer dan helft verliesgevend. Overweeg niet te handelen bij VIX > 20")

    win_rate = round(len(winst_trades) / len(trades) * 100, 1)
    if win_rate >= 70:
        observaties.append(f"✅ Sterke dag — win rate {win_rate}%")
    elif win_rate <= 30:
        observaties.append(f"🔴 Zwakke dag — win rate {win_rate}%. Wat was er anders vandaag?")

    kruis_trades = [t for t in winst_trades if t.get('ema_status') == 'KRUIS OMHOOG']
    if len(kruis_trades) > len(winst_trades) * 0.7:
        observaties.append(f"📊 {len(kruis_trades)} van {len(winst_trades)} winstgevende trades hadden EMA kruising — sterk signaal bevestigd")

    return "\n".join(f"- {o}" for o in observaties) if observaties else "- Geen opvallende patronen vandaag"


# ─── Scoring snapshot → leesbare Markdown ────────────────

def snapshot_naar_markdown(snap):
    """Zet de scoring snapshot om naar een leesbaar Markdown blok."""
    r = snap

    regels = [
        f"### Scoring systeem — versie {r['versie']}",
        "",
        "#### Basisinstellingen",
        f"- Score basis: {r['score_basis']}",
        f"- Min score voor trade: {r['drempelwaarden']['min_score']}",
        f"- Min beweging: {r['drempelwaarden']['min_beweging_pct']}%",
        f"- Min relatief volume: {r['drempelwaarden']['min_rel_volume']}x",
        "",
        "#### Trade parameters",
        f"- Gesimuleerd kapitaal: ${r['trade_parameters']['gesimuleerd_kapitaal']}",
        f"- Risico per trade: {r['trade_parameters']['risico_per_trade_pct']}%",
        f"- Doel: +{r['trade_parameters']['doel_pct']}%",
        f"- Stop loss: -{r['trade_parameters']['stop_loss_pct']}%",
        "",
        "#### VWAP multipliers",
        f"- Boven VWAP: ×{r['vwap']['boven']}",
        f"- Onder VWAP: ×{r['vwap']['onder']}",
        "",
        "#### RSI zones",
    ]

    for zone in r['rsi_zones']:
        regels.append(f"- RSI < {zone['grens']}: ×{zone['multiplier']}")

    regels += ["", "#### Volume zones"]
    for zone in r['volume_zones']:
        regels.append(f"- RelVol > {zone['grens']}: ×{zone['mult_pos']} (stijging) / ×{zone['mult_neg']} (daling)")

    regels += ["", "#### Dagverandering zones"]
    for zone in r['verandering_zones']:
        regels.append(f"- Wijziging > {zone['grens']}%: ×{zone['multiplier']}")

    regels += ["", "#### EMA multipliers"]
    for status, mult in r['ema_multipliers'].items():
        regels.append(f"- {status}: ×{mult}")

    regels += [
        "",
        "#### Penalties / bonussen",
        f"- Stijging maar onder VWAP (>2%): ×{r['penalties']['stijging_onder_vwap']}",
        f"- Hoge RSI (>65) bij KRUIS OMHOOG: ×{r['penalties']['hoge_rsi_bij_kruis_omhoog']}",
        f"- Lage RSI (<35) bij KRUIS OMLAAG: ×{r['penalties']['bonus_lage_rsi_bij_kruis_omlaag']}",
    ]

    return "\n".join(regels)


# ─── Trade notitie ────────────────────────────────────────

def schrijf_trade_notitie(trade, snap=None):
    datum   = datetime.now().strftime('%Y-%m-%d')
    tijdstip = datetime.now().strftime('%H:%M')
    dag     = datetime.now().strftime('%A').lower()
    dag_nl  = {'monday': 'maandag', 'tuesday': 'dinsdag', 'wednesday': 'woensdag',
               'thursday': 'donderdag', 'friday': 'vrijdag'}.get(dag, dag)

    resultaat_tag = 'winst' if trade.get('resultaat', 0) > 0 else 'verlies'

    if snap is None:
        snap = scoring_snapshot()
    scoring_md = snapshot_naar_markdown(snap)

    inhoud = f"""# {trade['ticker']} — {datum}

## Trade details
- Ticker: {trade['ticker']}
- Datum: {datum}
- Dag van de week: {dag_nl}
- Instapprijs: ${trade['instap_prijs']}
- Instaptijdstip: {trade.get('instap_tijdstip', tijdstip)}
- Uitstapprijs: ${trade.get('uitstap_prijs', 'open')}
- Uitstaptijdstip: {trade.get('uitstap_tijdstip', 'open')}
- Duur van de trade: {trade.get('duur', 'open')}
- Aantal aandelen: {trade['aantal']}
- Resultaat $: {trade.get('resultaat_dollar', 'open')}
- Resultaat %: {trade.get('resultaat_pct', 'open')}
- Reden sluiting: {trade.get('reden', 'open')}

## Signalen op moment van koop
- Confluence score: {trade.get('score', '')}
- RSI: {trade.get('rsi', '')}
- EMA status: {trade.get('ema_status', '')}
- Relatief volume: {trade.get('rel_volume', '')}x
- VWAP: {trade.get('vwap_positie', '')}
- Prijsverandering die dag: {trade.get('verandering_pct', '')}%
- Pre-market beweging: {trade.get('premarket_pct', '')}%

## Marktcontext
- S&P500 die dag: {trade.get('sp500', '')}%
- VIX stand: {trade.get('vix', '')}
- Sector van aandeel: {trade.get('sector', '')}
- Nieuws catalyst: {trade.get('catalyst', 'onbekend')}

## Tijdstip categorie
- Opening (15:30-16:00): {'ja' if trade.get('tijdstip_cat') == 'opening' else 'nee'}
- Mid-dag (16:00-19:00): {'ja' if trade.get('tijdstip_cat') == 'middag' else 'nee'}
- Laatste uur (21:00-22:00): {'ja' if trade.get('tijdstip_cat') == 'laatste_uur' else 'nee'}

## Scoringssysteem op moment van trade
{scoring_md}

## Observaties
<!-- wat viel je op? was het signaal logisch achteraf? -->

## Tags
#trade #{trade['ticker'].lower()} #{resultaat_tag} #{dag_nl}
"""

    pad = os.path.join(OBSIDIAN_PAD, 'Trades', f"{trade['ticker']}-{datum}.md")
    with open(pad, 'w', encoding='utf-8') as f:
        f.write(inhoud)
    print(f"  Notitie aangemaakt: {trade['ticker']}-{datum}.md")


# ─── Dagboek ──────────────────────────────────────────────

def scan_stats_naar_markdown(stats):
    """Zet de scan statistieken om naar een leesbaar Markdown blok."""
    if not stats:
        return "- Geen scan data beschikbaar"

    v = stats['score_verdeling']
    keys = list(v.keys())

    return "\n".join([
        f"- Shortlist grootte: {stats['shortlist_grootte']} aandelen",
        f"- Score verdeling:",
        f"  - {keys[0].replace('_', ' ')}: {v[keys[0]]}",
        f"  - {keys[1].replace('_', ' ')}: {v[keys[1]]}",
        f"  - {keys[2].replace('_', ' ')}: {v[keys[2]]}",
        f"  - {keys[3].replace('_', ' ')}: {v[keys[3]]}",
        f"- Hoogste score: {stats['hoogste_score']['ticker']} ({stats['hoogste_score']['score']})",
        f"- Laagste score: {stats['laagste_score']['ticker']} ({stats['laagste_score']['score']})",
        f"- Gemiddelde score shortlist: {stats['gemiddelde_score']}",
    ])


def schrijf_dagboek(trades=None, scan_stats=None):
    if trades is None:
        trades = []

    datum   = datetime.now().strftime('%Y-%m-%d')
    dag     = datetime.now().strftime('%A').lower()
    dag_nl  = {'monday': 'maandag', 'tuesday': 'dinsdag', 'wednesday': 'woensdag',
               'thursday': 'donderdag', 'friday': 'vrijdag'}.get(dag, dag)

    print("  Marktdata ophalen...")
    markt = haal_markt_data_op()
    snap  = scoring_snapshot()
    scoring_md = snapshot_naar_markdown(snap)

    winst_trades   = [t for t in trades if t.get('resultaat', 0) > 0]
    verlies_trades = [t for t in trades if t.get('resultaat', 0) < 0]
    totaal_resultaat = round(sum(t.get('resultaat', 0) for t in trades), 2)

    beste     = max(trades, key=lambda x: x.get('resultaat_pct', 0)) if trades else None
    slechtste = min(trades, key=lambda x: x.get('resultaat_pct', 0)) if trades else None
    gem_duur   = round(sum(t.get('duur_minuten', 0) for t in trades) / len(trades)) if trades else 0
    gem_score  = round(sum(t.get('score', 0) for t in trades) / len(trades), 1) if trades else 0
    gem_volume = round(sum(t.get('rel_volume', 0) for t in trades) / len(trades), 2) if trades else 0

    observaties = genereer_observaties(trades, markt)

    inhoud = f"""# Dagboek — {datum}

## Marktoverzicht — automatisch
- S&P500: {markt['sp500'] if markt else 'n/a'}%
- NASDAQ: {markt['nasdaq'] if markt else 'n/a'}%
- VIX: {markt['vix'] if markt else 'n/a'} ({markt['vix_label'] if markt else 'n/a'})
- Sentiment: {markt['sentiment'] if markt else 'n/a'}

## Trades vandaag — automatisch
- Aantal trades: {len(trades)}
- Winstgevend: {len(winst_trades)}
- Verliesgevend: {len(verlies_trades)}
- Totaal resultaat: ${totaal_resultaat}
- Beste trade: {beste['ticker'] + ' (+' + str(beste.get('resultaat_pct', 0)) + '%)' if beste else 'n/a'}
- Slechtste trade: {slechtste['ticker'] + ' (' + str(slechtste.get('resultaat_pct', 0)) + '%)' if slechtste else 'n/a'}
- Gemiddelde duur trade: {gem_duur} minuten

## Signaal kwaliteit vandaag — automatisch
- Gemiddelde confluence score: {gem_score}
- Gemiddeld relatief volume: {gem_volume}x

## Automatische observaties — gegenereerd door Python
{observaties}

## Scan kwaliteit vandaag — automatisch
{scan_stats_naar_markdown(scan_stats)}

## Scoringssysteem vandaag — referentiekader
{scoring_md}

## Jouw beslissing — handmatig
<!-- Alleen invullen als een observatie hierboven actie vereist -->
<!-- Altijd redeneren vanuit data, niet vanuit gevoel -->

## Tags
#dagboek #{datum} #{dag_nl}
"""

    pad = os.path.join(OBSIDIAN_PAD, 'Dagboek', f"{datum}.md")
    with open(pad, 'w', encoding='utf-8') as f:
        f.write(inhoud)
    print(f"  Dagboek aangemaakt: {datum}.md")


if __name__ == "__main__":
    print("Obsidian logger testen...")
    schrijf_dagboek()
    print("Klaar — check je Obsidian Dagboek map!")
