import json
import os
import base64
import requests
from datetime import datetime
import pytz

NL_TZ = pytz.timezone('Europe/Amsterdam')

# ─── GitHub keys laden ───────────────────────────────────

def laad_github_keys():
    keys = {}
    with open('github_keys.txt', 'r') as f:
        for regel in f:
            if '=' in regel:
                k, v = regel.strip().split(' = ', 1)
                keys[k.strip()] = v.strip()
    return keys

# ─── HTML dashboard genereren ────────────────────────────

def genereer_dashboard_html(portfolio, scan_resultaten=None):
    nu = datetime.now(NL_TZ).strftime('%d/%m/%Y %H:%M')
    stats = portfolio.get('statistieken', {})
    open_trades = portfolio.get('open_trades', {})
    gesloten_trades = portfolio.get('gesloten_trades', [])

    # Bereken dag nummer op basis van eerste trade
    from datetime import date as _date
    alle_trades = portfolio.get('gesloten_trades', [])
    dag_nummer = 1
    if alle_trades:
        eerste_str = alle_trades[0].get('tijdstip', alle_trades[0].get('gesloten_op', ''))[:10]
        try:
            if '/' in eerste_str:
                d, m, y = eerste_str.split('/')
                eerste_datum = _date(int(y), int(m), int(d))
            else:
                eerste_datum = _date.fromisoformat(eerste_str)
            dag_nummer = (_date.today() - eerste_datum).days + 1
        except:
            dag_nummer = 1

    startkapitaal = portfolio.get('startkapitaal', 100000)
    portfolio_waarde = portfolio.get('portfolio_waarde', startkapitaal)
    rendement = round(((portfolio_waarde - startkapitaal) / startkapitaal) * 100, 2) if startkapitaal else 0
    winrate = round((stats.get('winstgevend', 0) / stats['totaal']) * 100, 1) if stats.get('totaal', 0) > 0 else 0

    # Open P/L alleen berekenen als er open posities zijn
    open_pl = round(portfolio_waarde - startkapitaal - stats.get('totaal_resultaat', 0), 2) if open_trades else 0

    # ─── Open posities HTML ──────────────────────────────
    open_rijen = ''
    for t in open_trades.values():
        pl = t.get('huidig_pl', 0.0)
        pl_kleur = '#00ff88' if pl >= 0 else '#ff4466'
        pl_teken = '+' if pl >= 0 else ''
        open_rijen += f"""
        <tr>
            <td><span class="ticker">{t['ticker']}</span></td>
            <td>${t['instap_prijs']:.2f}</td>
            <td>${t['doel']:.2f}</td>
            <td>${t['stop_loss']:.2f}</td>
            <td>{t['aantal']}</td>
            <td style="color:{pl_kleur}">{pl_teken}{pl:.2f}%</td>
            <td><span class="score-badge">{t.get('score', '-')}</span></td>
        </tr>"""

    # ─── Gesloten trades HTML ────────────────────────────
    gesloten_rijen = ''
    for t in reversed(gesloten_trades[-20:]):
        resultaat = t.get('resultaat_pct', 0)
        kleur = '#00ff88' if resultaat >= 0 else '#ff4466'
        teken = '+' if resultaat >= 0 else ''
        gesloten_rijen += f"""
        <tr>
            <td><span class="ticker">{t['ticker']}</span></td>
            <td>${t['instap_prijs']:.2f}</td>
            <td>${t.get('uitstap_prijs', 0):.2f}</td>
            <td style="color:{kleur}">{teken}{resultaat:.2f}%</td>
            <td>{t.get('reden', '-')}</td>
            <td>{t.get('gesloten_op', '-')}</td>
        </tr>"""

    # ─── Scan signalen HTML ──────────────────────────────
    scan_rijen = ''
    if scan_resultaten:
        for d in scan_resultaten[:20]:
            ema_kort = {
                'KRUIS OMHOOG': '↑ KRUIS', 'KRUIS OMLAAG': '↓ KRUIS',
                'EMA BULL': '↑ BULL', 'EMA BEAR': '↓ BEAR'
            }.get(d.get('ema_status', ''), d.get('ema_status', ''))
            vwap = 'BOVEN' if d.get('boven_vwap') else 'ONDER'
            score = d.get('score', 0)
            score_kleur = '#00ff88' if score >= 85 else '#ffcc00' if score >= 70 else '#ffffff'
            scan_rijen += f"""
            <tr>
                <td><span class="ticker">{d['ticker']}</span></td>
                <td>${d.get('prijs', 0):.2f}</td>
                <td>{d.get('verandering_pct', 0):+.2f}%</td>
                <td>{d.get('rel_volume', 0):.1f}x</td>
                <td>{d.get('rsi', 0):.1f}</td>
                <td>{vwap}</td>
                <td>{ema_kort}</td>
                <td style="color:{score_kleur}"><b>{score}</b></td>
            </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="nl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="refresh" content="1800">
<title>Trading Dashboard</title>
<link href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;700;800&display=swap" rel="stylesheet">
<style>
  :root {{
    --bg: #080c12;
    --surface: #0d1520;
    --border: #1a2535;
    --accent: #00ff88;
    --accent2: #0088ff;
    --danger: #ff4466;
    --text: #c8d8e8;
    --muted: #4a6080;
    --mono: 'Space Mono', monospace;
    --sans: 'Syne', sans-serif;
  }}

  * {{ margin: 0; padding: 0; box-sizing: border-box; }}

  body {{
    background: var(--bg);
    color: var(--text);
    font-family: var(--mono);
    font-size: 13px;
    min-height: 100vh;
    background-image:
      radial-gradient(ellipse at 20% 20%, rgba(0,255,136,0.03) 0%, transparent 50%),
      radial-gradient(ellipse at 80% 80%, rgba(0,136,255,0.03) 0%, transparent 50%);
  }}

  header {{
    padding: 32px 40px 24px;
    border-bottom: 1px solid var(--border);
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
  }}

  header h1 {{
    font-family: var(--sans);
    font-size: 28px;
    font-weight: 800;
    letter-spacing: -0.5px;
    color: #fff;
  }}

  header h1 span {{ color: var(--accent); }}

  .timestamp {{
    color: var(--muted);
    font-size: 11px;
  }}

  .timestamp b {{ color: var(--accent); }}

  .grid {{
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 1px;
    background: var(--border);
    border-bottom: 1px solid var(--border);
  }}

  .stat {{
    background: var(--surface);
    padding: 24px 28px;
  }}

  .stat-label {{
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 2px;
    color: var(--muted);
    margin-bottom: 8px;
  }}

  .stat-value {{
    font-family: var(--sans);
    font-size: 32px;
    font-weight: 800;
    color: #fff;
  }}

  .stat-value.positive {{ color: var(--accent); }}
  .stat-value.negative {{ color: var(--danger); }}

  .section {{
    padding: 32px 40px;
    border-bottom: 1px solid var(--border);
  }}

  .section-title {{
    font-family: var(--sans);
    font-size: 13px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 3px;
    color: var(--muted);
    margin-bottom: 20px;
    display: flex;
    align-items: center;
    gap: 10px;
  }}

  .section-title::after {{
    content: '';
    flex: 1;
    height: 1px;
    background: var(--border);
  }}

  table {{
    width: 100%;
    border-collapse: collapse;
  }}

  th {{
    text-align: left;
    padding: 8px 12px;
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 2px;
    color: var(--muted);
    border-bottom: 1px solid var(--border);
  }}

  td {{
    padding: 10px 12px;
    border-bottom: 1px solid rgba(26,37,53,0.5);
    color: var(--text);
  }}

  tr:hover td {{ background: rgba(255,255,255,0.02); }}

  .ticker {{
    font-weight: 700;
    color: #fff;
    background: var(--border);
    padding: 2px 8px;
    border-radius: 3px;
    font-size: 12px;
  }}

  .score-badge {{
    background: rgba(0,255,136,0.1);
    color: var(--accent);
    padding: 2px 8px;
    border-radius: 3px;
    font-weight: 700;
  }}

  .empty {{
    color: var(--muted);
    padding: 24px 12px;
    font-style: italic;
  }}

  .live-dot {{
    width: 8px;
    height: 8px;
    background: var(--accent);
    border-radius: 50%;
    display: inline-block;
    animation: pulse 2s infinite;
  }}

  @keyframes pulse {{
    0%, 100% {{ opacity: 1; box-shadow: 0 0 0 0 rgba(0,255,136,0.4); }}
    50% {{ opacity: 0.7; box-shadow: 0 0 0 6px rgba(0,255,136,0); }}
  }}

  footer {{
    padding: 20px 40px;
    color: var(--muted);
    font-size: 11px;
    text-align: center;
  }}
</style>
</head>
<body>

<header>
  <div>
    <h1>TRADING <span>DASHBOARD</span></h1>
    <div style="margin-top:4px;color:var(--muted);font-size:11px">Paper trading — Alpaca Markets &nbsp;·&nbsp; <span style="color:var(--accent)">Dag {dag_nummer}</span></div>
  </div>
  <div style="text-align:right">
    <div style="margin-bottom:6px"><span class="live-dot"></span> <span style="color:var(--accent);font-size:11px">LIVE</span></div>
    <div class="timestamp">Laatste update: <b>{nu}</b></div>
    <div class="timestamp" style="margin-top:2px">Pagina ververst automatisch elke 30 min</div>
  </div>
</header>

<div class="grid">
  <div class="stat">
    <div class="stat-label">Portfolio waarde</div>
    <div class="stat-value">${portfolio_waarde:,.0f}</div>
    <div style="font-size:11px;margin-top:4px;color:{'var(--accent)' if rendement >= 0 else 'var(--danger)'}">{'+' if rendement >= 0 else ''}{rendement}% vs start</div>
  </div>
  <div class="stat">
    <div class="stat-label">Totaal trades</div>
    <div class="stat-value">{stats.get('totaal', 0)}</div>
  </div>
  <div class="stat">
    <div class="stat-label">Winrate</div>
    <div class="stat-value {'positive' if winrate >= 50 else 'negative'}">{winrate}%</div>
  </div>
  <div class="stat">
    <div class="stat-label">Gesloten P/L</div>
    <div class="stat-value {'positive' if stats.get('totaal_resultaat', 0) >= 0 else 'negative'}">${stats.get('totaal_resultaat', 0):+,.2f}</div>
  </div>
  <div class="stat">
    <div class="stat-label">Open P/L</div>
    <div class="stat-value {'positive' if open_pl >= 0 else 'negative'}">${open_pl:+,.2f}</div>
  </div>
</div>

<div class="section">
  <div class="section-title">Open posities ({len(open_trades)})</div>
  {'<table><thead><tr><th>Ticker</th><th>Instap</th><th>Doel</th><th>Stop</th><th>Aantal</th><th>P/L</th><th>Score</th></tr></thead><tbody>' + open_rijen + '</tbody></table>' if open_trades else '<div class="empty">Geen open posities</div>'}
</div>

<div class="section">
  <div class="section-title">Laatste signalen screener</div>
  {'<table><thead><tr><th>Ticker</th><th>Prijs</th><th>Wijz%</th><th>RelVol</th><th>RSI</th><th>VWAP</th><th>EMA</th><th>Score</th></tr></thead><tbody>' + scan_rijen + '</tbody></table>' if scan_resultaten else '<div class="empty">Nog geen scan data</div>'}
</div>

<div class="section">
  <div class="section-title">Recente gesloten trades</div>
  {'<table><thead><tr><th>Ticker</th><th>Instap</th><th>Uitstap</th><th>Resultaat</th><th>Reden</th><th>Gesloten op</th></tr></thead><tbody>' + gesloten_rijen + '</tbody></table>' if gesloten_trades else '<div class="empty">Nog geen gesloten trades</div>'}
</div>

<footer>
  Trading dashboard — automatisch gegenereerd · Vernieuw handmatig of wacht op automatische refresh
</footer>

</body>
</html>"""

    return html


# ─── Push naar GitHub ─────────────────────────────────────

def push_naar_github(html_inhoud):
    try:
        keys = laad_github_keys()
        token = keys['GITHUB_TOKEN']
        username = keys['GITHUB_USERNAME']
        repo = keys['GITHUB_REPO']

        api_url = f"https://api.github.com/repos/{username}/{repo}/contents/index.html"
        headers = {
            'Authorization': f'token {token}',
            'Content-Type': 'application/json',
            'User-Agent': 'trading-dashboard'
        }

        # Haal huidige SHA op (nodig voor update)
        sha = None
        resp = requests.get(api_url, headers=headers, verify=False)
        if resp.status_code == 200:
            sha = resp.json().get('sha')

        # Encode HTML als base64
        inhoud_b64 = base64.b64encode(html_inhoud.encode('utf-8')).decode('utf-8')

        payload = {
            'message': f'Dashboard update {datetime.now(NL_TZ).strftime("%d/%m/%Y %H:%M")}',
            'content': inhoud_b64,
        }
        if sha:
            payload['sha'] = sha

        resp = requests.put(api_url, headers=headers, json=payload, verify=False)
        if resp.status_code in (200, 201):
            print(f"  🌐 Dashboard gepusht naar GitHub Pages")
        else:
            print(f"  GitHub push fout: {resp.status_code} — {resp.text[:200]}")

    except Exception as e:
        print(f"  GitHub push fout: {e}")


# ─── Hoofd functie ────────────────────────────────────────

def update_dashboard(portfolio, scan_resultaten=None):
    """Genereert het HTML dashboard en pusht naar GitHub Pages."""
    html = genereer_dashboard_html(portfolio, scan_resultaten)
    push_naar_github(html)


if __name__ == "__main__":
    import os
    if os.path.exists('trades.json'):
        with open('trades.json', 'r') as f:
            portfolio = json.load(f)
        print("  trades.json geladen")
        # Haal actuele portfolio waarde op van Alpaca
        try:
            from paper_trading import trading_client
            account = trading_client.get_account()
            portfolio['portfolio_waarde'] = float(account.portfolio_value)
            print(f"  Portfolio waarde: ${portfolio['portfolio_waarde']:,.2f}")
        except Exception as e:
            print(f"  Kon portfolio waarde niet ophalen: {e}")
    else:
        portfolio = {
            'startkapitaal': 100000,
            'open_trades': {},
            'gesloten_trades': [],
            'statistieken': {'totaal': 0, 'winstgevend': 0, 'verliesgevend': 0, 'totaal_resultaat': 0.0}
        }
    update_dashboard(portfolio)
