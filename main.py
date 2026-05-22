import time
from datetime import datetime
import pytz

from dashboard import run_screener
from paper_trading import run_paper_trading, is_markt_open, sluit_alle_trades, laad_portfolio, sla_portfolio_op, sync_gesloten_trades
from obsidian_logger import schrijf_dagboek
from github_dashboard import update_dashboard

NY_TZ = pytz.timezone('America/New_York')
NL_TZ = pytz.timezone('Europe/Amsterdam')

SLUIT_UUR_NL  = 21
SLUIT_MINUUT_NL = 45  # verkoop om 21:45 NL — 15 min voor markt sluit


def volgende_halve_uur():
    """Geeft het aantal seconden tot het volgende hele of halve uur (NY tijd)."""
    nu = datetime.now(NY_TZ)
    minuten = nu.minute
    seconden = nu.second
    wacht_minuten = 30 - minuten if minuten < 30 else 60 - minuten
    return wacht_minuten * 60 - seconden


def is_sluitingstijd():
    """Geeft True als het 21:45 NL of later is — tijd om posities te sluiten."""
    nu = datetime.now(NL_TZ)
    return (nu.hour > SLUIT_UUR_NL) or (nu.hour == SLUIT_UUR_NL and nu.minute >= SLUIT_MINUUT_NL)


def run_cyclus():
    """Één volledige scan + trading cyclus."""
    print("\n" + "="*55)
    print(f"  CYCLUS GESTART — {datetime.now(NL_TZ).strftime('%d/%m/%Y %H:%M')} NL")
    print("="*55)

    signalen, scan_stats = run_screener()
    gesloten_trades = run_paper_trading(signalen)
    return gesloten_trades, scan_stats, signalen


def sluit_dag_af(alle_gesloten_trades, scan_stats):
    """Sluit alle posities en schrijft het dagboek weg."""
    print("\n  ⏰ 21:45 NL — posities sluiten voor einde markt...")
    portfolio = laad_portfolio()

    # Eerst syncen met Alpaca — dit is de bron van waarheid
    print("  Alpaca uitlezen voor eindstand...")
    sync_gesloten_trades(portfolio)

    # Zet open_trades op leeg voor posities die Alpaca al gesloten heeft
    try:
        from paper_trading import trading_client
        alpaca_posities = {p.symbol for p in trading_client.get_all_positions()}
        for ticker in list(portfolio['open_trades'].keys()):
            if ticker not in alpaca_posities:
                print(f"  {ticker}: al gesloten door Alpaca — verwijderd uit open trades")
                del portfolio['open_trades'][ticker]
    except Exception as e:
        print(f"  Alpaca sync fout: {e}")

    # Sluit wat er nog over is
    sluit_alle_trades(portfolio)
    sla_portfolio_op(portfolio)

    # Voeg slotverkopen toe aan dagoverzicht
    vandaag = datetime.now(NL_TZ).strftime('%d/%m/%Y')
    nieuwe_gesloten = [
        t for t in portfolio['gesloten_trades']
        if t.get('gesloten_op', '').startswith(vandaag)
    ]
    alle_gesloten_trades.extend(nieuwe_gesloten)
    schrijf_dagboek(trades=alle_gesloten_trades, scan_stats=scan_stats)

    # Laatste dashboard push met eindstand van de dag
    try:
        account = trading_client.get_account()
        portfolio['portfolio_waarde'] = float(account.portfolio_value)
    except:
        pass
    update_dashboard(portfolio, None)
    print("  ✅ Dag afgesloten — dagboek en dashboard bijgewerkt.")


def main():
    print("DAY TRADE SYSTEEM GESTART")
    print("="*55)
    print("  Eerste scan direct starten...")
    print(f"  Posities worden automatisch gesloten om {SLUIT_UUR_NL}:{SLUIT_MINUUT_NL:02d} NL.\n")

    # Laad al gesloten trades van vandaag uit trades.json
    alle_gesloten_trades = []
    laatste_scan_stats = None
    try:
        import json, os
        from datetime import date
        if os.path.exists('trades.json'):
            with open('trades.json', 'r') as f:
                portfolio = json.load(f)
            vandaag = date.today().strftime('%d/%m/%Y')
            alle_gesloten_trades = [
                t for t in portfolio.get('gesloten_trades', [])
                if t.get('gesloten_op', '').startswith(vandaag)
            ]
            if alle_gesloten_trades:
                print(f"  {len(alle_gesloten_trades)} gesloten trades van vandaag geladen uit trades.json")
    except Exception as e:
        print(f"  Kon trades.json niet laden: {e}")

    dag_afgesloten = False

    while True:
        # Sluitingstijd check — voor de scan
        if not dag_afgesloten and is_sluitingstijd():
            sluit_dag_af(alle_gesloten_trades, laatste_scan_stats)
            dag_afgesloten = True

        # Markt dicht — stoppen
        if not is_markt_open():
            if not dag_afgesloten:
                sluit_dag_af(alle_gesloten_trades, laatste_scan_stats)
            print("  Markt gesloten — systeem stopt.")
            break

        # Na sluitingstijd geen nieuwe scans meer
        if dag_afgesloten:
            print("  Posities gesloten — wachten tot markt sluit...")
            time.sleep(60)
            continue

        gesloten, scan_stats, signalen = run_cyclus()
        laatste_scan_stats = scan_stats
        if gesloten:
            alle_gesloten_trades.extend(gesloten)

        # Dashboard updaten na elke cyclus — actuele waarde van Alpaca ophalen
        portfolio = laad_portfolio()
        try:
            from paper_trading import trading_client
            account = trading_client.get_account()
            portfolio['portfolio_waarde'] = float(account.portfolio_value)
        except Exception as e:
            portfolio['portfolio_waarde'] = portfolio.get('startkapitaal', 100000)
        update_dashboard(portfolio, signalen)

        wacht = volgende_halve_uur()

        # Als het volgende halve uur na 21:45 valt, wacht dan alleen tot 21:45
        nu_nl = datetime.now(NL_TZ)
        sluit_moment = nu_nl.replace(hour=SLUIT_UUR_NL, minute=SLUIT_MINUUT_NL, second=0, microsecond=0)
        seconden_tot_sluit = (sluit_moment - nu_nl).total_seconds()
        if 0 < seconden_tot_sluit < wacht:
            wacht = int(seconden_tot_sluit) + 5  # 5 seconden buffer
            print(f"\n  ⏱  Volgende scan over {round(wacht/60, 1)} min (aangepast voor sluitingstijd)  |  NL: {nu_nl.strftime('%H:%M')}  NY: {datetime.now(NY_TZ).strftime('%H:%M')}")
        else:
            nu_ny = datetime.now(NY_TZ)
            print(f"\n  ⏱  Volgende scan over {round(wacht/60, 1)} min  |  NL: {nu_nl.strftime('%H:%M')}  NY: {nu_ny.strftime('%H:%M')}")

        # Wacht in stukjes van 60 sec zodat 21:45 check niet gemist wordt
        gewacht = 0
        while gewacht < wacht:
            time.sleep(min(60, wacht - gewacht))
            gewacht += 60
            if not dag_afgesloten and is_sluitingstijd():
                break


if __name__ == "__main__":
    main()
