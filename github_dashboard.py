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

def genereer_dashboard_html(portfolios, scan_resultaten=None):
    nu = datetime.now(NL_TZ).strftime('%d/%m/%Y %H:%M')

    strategy_rijen = ''
    for p in portfolios:
        naam = p.get('naam', '?')
        stats = p.get('statistieken', {})
        start = p.get('startkapitaal', 100000)
        waarde = p.get('portfolio_waarde', start)
        rendement = round(((waarde - start) / start) * 100, 2) if start else 0
        winrate = round((stats.get('winstgevend', 0) / stats['totaal']) * 100, 1) if stats.get('totaal', 0) > 0 else 0
        pl = stats.get('totaal_resultaat', 0)
        ren_kleur = '#00ff88' if rendement >= 0 else '#ff4466'
        pl_kleur = '#00ff88' if pl >= 0 else '#ff4466'
        strategy_rijen += f"""
        <tr>
            <td><span class="ticker">{naam}</span></td>
            <td>${waarde:,.0f}</td>
            <td style="color:{ren_kleur}">{'+' if rendement >= 0 else ''}{rendement}%</td>
            <td style="color:{pl_kleur}">${pl:+,.2f}</td>
            <td>{stats.get('totaal', 0)}</td>
            <td>{winrate}%</td>
            <td>{len(p.get('open_trades', {}))}</td>
        </tr>"""

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
  :root {{--bg:#080c12;--surface:#0d1520;--border:#1a2535;--accent:#00ff88;--danger:#ff4466;--text:#c8d8e8;--muted:#4a6080;--mono:'Space Mono',monospace;--sans:'Syne',sans-serif;}}
  *{{margin:0;padding:0;box-sizing:border-box;}}
  body{{background:var(--bg);color:var(--text);font-family:var(--mono);font-size:13px;}}
  header{{padding:32px 40px 24px;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:flex-end;}}
  header h1{{font-family:var(--sans);font-size:28px;font-weight:800;color:#fff;}}
  header h1 span{{color:var(--accent);}}
  .timestamp{{color:var(--muted);font-size:11px;}}
  .timestamp b{{color:var(--accent);}}
  .section{{padding:32px 40px;border-bottom:1px solid var(--border);}}
  .section-title{{font-family:var(--sans);font-size:13px;font-weight:700;text-transform:uppercase;letter-spacing:3px;color:var(--muted);margin-bottom:20px;display:flex;align-items:center;gap:10px;}}
  .section-title::after{{content:'';flex:1;height:1px;background:var(--border);}}
  table{{width:100%;border-collapse:collapse;}}
  th{{text-align:left;padding:8px 12px;font-size:10px;text-transform:uppercase;letter-spacing:2px;color:var(--muted);border-bottom:1px solid var(--border);}}
  td{{padding:10px 12px;border-bottom:1px solid rgba(26,37,53,0.5);}}
  tr:hover td{{background:rgba(255,255,255,0.02);}}
  .ticker{{font-weight:700;color:#fff;background:var(--border);padding:2px 8px;border-radius:3px;font-size:12px;}}
  .live-dot{{width:8px;height:8px;background:var(--accent);border-radius:50%;display:inline-block;animation:pulse 2s infinite;}}
  @keyframes pulse{{0%,100%{{opacity:1;box-shadow:0 0 0 0 rgba(0,255,136,0.4);}}50%{{opacity:.7;box-shadow:0 0 0 6px rgba(0,255,136,0);}}}}
  footer{{padding:20px 40px;color:var(--muted);font-size:11px;text-align:center;}}
</style>
</head>
<body>
<header>
  <div>
    <h1>TRADING <span>DASHBOARD</span></h1>
    <div style="margin-top:4px;color:var(--muted);font-size:11px">6-strategy paper trading — Alpaca Markets</div>
  </div>
  <div style="text-align:right">
    <div style="margin-bottom:6px"><span class="live-dot"></span> <span style="color:var(--accent);font-size:11px">LIVE</span></div>
    <div class="timestamp">Laatste update: <b>{nu}</b></div>
  </div>
</header>
<div class="section">
  <div class="section-title">Strategy vergelijking</div>
  <table>
    <thead><tr><th>Strategie</th><th>Portfolio</th><th>Rendement</th><th>Gesloten P/L</th><th>Trades</th><th>Winrate</th><th>Open</th></tr></thead>
    <tbody>{strategy_rijen}</tbody>
  </table>
</div>
<div class="section">
  <div class="section-title">Laatste signalen screener (Baseline)</div>
  {'<table><thead><tr><th>Ticker</th><th>Prijs</th><th>Wijz%</th><th>RelVol</th><th>RSI</th><th>VWAP</th><th>EMA</th><th>Score</th></tr></thead><tbody>' + scan_rijen + '</tbody></table>' if scan_resultaten else '<div style="color:var(--muted);padding:24px 12px;font-style:italic">Nog geen scan data</div>'}
</div>
<footer>Trading dashboard — automatisch gegenereerd</footer>
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

def update_dashboard(portfolios, scan_resultaten=None):
    html = genereer_dashboard_html(portfolios, scan_resultaten)
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
