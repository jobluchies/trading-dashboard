import time
from datetime import datetime
import pytz

from dashboard import run_screener, score_signals
from paper_trading import is_markt_open, PaperTradingEngine
from obsidian_logger import schrijf_dagboek
from github_dashboard import update_dashboard
from strategies import STRATEGIES

NY_TZ = pytz.timezone('America/New_York')
NL_TZ = pytz.timezone('Europe/Amsterdam')

SLUIT_UUR_NL = 21
SLUIT_MINUUT_NL = 45

ENGINES = [PaperTradingEngine(s) for s in STRATEGIES]


def volgende_halve_uur():
    nu = datetime.now(NY_TZ)
    minuten = nu.minute
    seconden = nu.second
    wacht_minuten = 30 - minuten if minuten < 30 else 60 - minuten
    return wacht_minuten * 60 - seconden


def is_sluitingstijd():
    nu = datetime.now(NL_TZ)
    return (nu.hour > SLUIT_UUR_NL) or (nu.hour == SLUIT_UUR_NL and nu.minute >= SLUIT_MINUUT_NL)


def _laad_alle_portfolios():
    portfolios = []
    for engine in ENGINES:
        p = engine.laad_portfolio()
        p['naam'] = engine.naam
        try:
            account = engine.trading_client.get_account()
            p['portfolio_waarde'] = float(account.portfolio_value)
        except:
            p['portfolio_waarde'] = p.get('startkapitaal', 100000)
        portfolios.append(p)
    return portfolios


def run_cyclus():
    print("\n" + "=" * 55)
    print(f"  CYCLUS GESTART — {datetime.now(NL_TZ).strftime('%d/%m/%Y %H:%M')} NL")
    print("=" * 55)

    raw_data, scan_stats = run_screener()

    for engine in ENGINES:
        signalen = score_signals(raw_data, engine.config)
        engine.run(signalen)

    return scan_stats, raw_data


def sluit_dag_af(scan_stats):
    print("\n  ⏰ 21:45 NL — posities sluiten voor einde markt...")

    for engine in ENGINES:
        portfolio = engine.laad_portfolio()
        print(f"  [{engine.naam}] Alpaca uitlezen...")
        engine.sync_gesloten_trades(portfolio)

        try:
            alpaca_posities = {p.symbol for p in engine.trading_client.get_all_positions()}
            for ticker in list(portfolio['open_trades'].keys()):
                if ticker not in alpaca_posities:
                    del portfolio['open_trades'][ticker]
        except Exception as e:
            print(f"  [{engine.naam}] Alpaca sync fout: {e}")

        engine.sluit_alle_trades(portfolio)
        engine.sla_portfolio_op(portfolio)

        vandaag = datetime.now(NL_TZ).strftime('%d/%m/%Y')
        gesloten_vandaag = [
            t for t in portfolio['gesloten_trades']
            if t.get('gesloten_op', '').startswith(vandaag)
        ]
        schrijf_dagboek(trades=gesloten_vandaag, scan_stats=scan_stats, strategy_naam=engine.naam)

    update_dashboard(_laad_alle_portfolios(), None)
    print("  ✅ Dag afgesloten — dagboek en dashboard bijgewerkt.")


def main():
    print("DAY TRADE SYSTEEM GESTART — 6 STRATEGIEEN")
    print("=" * 55)
    for i, s in enumerate(STRATEGIES, 1):
        print(f"  {i}. {s['naam']} | doel: {s['doel_pct']*100:.0f}% | stop: {s['stop_loss_pct']*100:.1f}% | min_score: {s['min_score']}")
    print(f"\n  Posities sluiten om {SLUIT_UUR_NL}:{SLUIT_MINUUT_NL:02d} NL.\n")

    dag_afgesloten = False
    laatste_scan_stats = None

    while True:
        if not dag_afgesloten and is_sluitingstijd():
            sluit_dag_af(laatste_scan_stats)
            dag_afgesloten = True

        if not is_markt_open():
            if not dag_afgesloten:
                sluit_dag_af(laatste_scan_stats)
            print("  Markt gesloten — systeem stopt.")
            break

        if dag_afgesloten:
            print("  Posities gesloten — wachten tot markt sluit...")
            time.sleep(60)
            continue

        scan_stats, raw_data = run_cyclus()
        laatste_scan_stats = scan_stats

        baseline_signalen = score_signals(raw_data, STRATEGIES[0])
        update_dashboard(_laad_alle_portfolios(), baseline_signalen)

        wacht = volgende_halve_uur()
        nu_nl = datetime.now(NL_TZ)
        sluit_moment = nu_nl.replace(hour=SLUIT_UUR_NL, minute=SLUIT_MINUUT_NL, second=0, microsecond=0)
        seconden_tot_sluit = (sluit_moment - nu_nl).total_seconds()
        if 0 < seconden_tot_sluit < wacht:
            wacht = int(seconden_tot_sluit) + 5
        nu_ny = datetime.now(NY_TZ)
        print(f"\n  ⏱  Volgende scan over {round(wacht/60, 1)} min  |  NL: {nu_nl.strftime('%H:%M')}  NY: {nu_ny.strftime('%H:%M')}")

        gewacht = 0
        while gewacht < wacht:
            time.sleep(min(60, wacht - gewacht))
            gewacht += 60
            if not dag_afgesloten and is_sluitingstijd():
                break


if __name__ == "__main__":
    main()
