"""
Komut satiri arayuzu.

Kullanim ornekleri:
  python -m futbot.cli predict --home Galatasaray --away Fenerbahce --demo
  python -m futbot.cli live --home Galatasaray --away Fenerbahce --minute 60 --score 1-0 --demo
  python -m futbot.cli coupon --demo --top 5
"""

from __future__ import annotations
import argparse
import time
from pathlib import Path
from tabulate import tabulate

from .poisson_model import DixonColesModel
from .data_fetcher import DataFetcher, generate_demo_history
from .live_tracker import live_market_probabilities
from .coupon_builder import picks_from_market_probs, build_coupon, combined_probability

# Egitilmis modellerin diske kaydedildigi klasor (futbot/.cache/)
CACHE_DIR = Path(__file__).resolve().parent / ".cache"


def _cache_path(demo: bool, league_id, season) -> Path:
    key = "demo" if demo else f"league{league_id}_season{season}"
    return CACHE_DIR / f"model_{key}.json"


def _build_model(
    demo: bool,
    league_id=None,
    season=None,
    refresh: bool = False,
    cache_hours: float = 24.0,
) -> DixonColesModel:
    """
    Modeli mumkunse diskteki cache'ten yukler; cache yoksa/eskiyse
    (cache_hours'tan eski) gecmis veriyi cekip yeniden egitir ve cache'e yazar.
    --refresh verilirse cache tamamen yok sayilir, her zaman yeniden egitir.
    """
    cache_file = _cache_path(demo, league_id, season)

    if not refresh and cache_file.exists():
        age_hours = (time.time() - cache_file.stat().st_mtime) / 3600
        if age_hours < cache_hours:
            print(f"[cache] Onceden egitilmis model kullaniliyor "
                  f"({age_hours:.1f} saat once egitilmis, {cache_file.name})")
            return DixonColesModel.load(cache_file)

    if demo:
        history = generate_demo_history()
    else:
        if not league_id or not season:
            raise SystemExit("--demo kullanmiyorsaniz --league-id ve --season zorunludur.")
        history = DataFetcher().get_historical_fixtures(league_id, season)

    print("[cache] Model (yeniden) egitiliyor...")
    model = DixonColesModel()
    model.fit(history)

    CACHE_DIR.mkdir(exist_ok=True)
    model.save(cache_file)
    return model


def _pct_table(d: dict) -> str:
    return tabulate([[k.upper(), f"{v * 100:.1f}%"] for k, v in d.items()], headers=["Secim", "Olasilik"])


def cmd_predict(args):
    model = _build_model(args.demo, args.league_id, args.season, args.refresh, args.cache_hours)
    probs = model.market_probabilities(args.home, args.away)

    print(f"\n{args.home} vs {args.away}")
    print(f"Beklenen gol: {probs['expected_goals']['home']:.2f} - {probs['expected_goals']['away']:.2f}\n")

    print("1X2:")
    print(_pct_table(probs["1x2"]))

    print("\n2.5 Alt/Ust:")
    print(_pct_table(probs["over_under_2_5"]))

    print("\nKarsilikli Gol (KG):")
    print(_pct_table(probs["btts"]))

    print("\nEn olasi skorlar:")
    print(tabulate(
        [[s["score"], f"{s['prob'] * 100:.1f}%"] for s in probs["top_scores"]],
        headers=["Skor", "Olasilik"],
    ))
    print()


def cmd_live(args):
    model = _build_model(args.demo, args.league_id, args.season, args.refresh, args.cache_hours)
    hg, ag = map(int, args.score.split("-"))
    probs = live_market_probabilities(model, args.home, args.away, args.minute, hg, ag)

    print(f"\n{args.home} {probs['current_score']} {args.away}  |  {probs['minute']}'")
    print("\nMac sonu (1X2) olasiligi:")
    print(_pct_table(probs["1x2"]))
    print("\n2.5 Alt/Ust:")
    print(_pct_table(probs["over_under_2_5"]))
    print()


def cmd_coupon(args):
    model = _build_model(args.demo, args.league_id, args.season, args.refresh, args.cache_hours)

    if args.demo:
        fixtures = [
            ("Galatasaray", "Kasimpasa"),
            ("Fenerbahce", "Konyaspor"),
            ("Besiktas", "Basaksehir"),
            ("Trabzonspor", "Adana Demirspor"),
        ]
    else:
        raise SystemExit(
            "Su an icin --demo disi fikstur listesi entegre edilmedi; "
            "gercek fikstur listenizi cmd_coupon icine (DataFetcher.get_live_fixtures ile) ekleyin."
        )

    all_picks = []
    for home, away in fixtures:
        probs = model.market_probabilities(home, away)
        all_picks.extend(picks_from_market_probs(f"{home} - {away}", probs))

    coupon = build_coupon(all_picks, top_n=args.top, min_prob=args.min_prob)

    print("\nOnerilen kupon:")
    print(tabulate(
        [[p.match, p.market, p.selection.upper(), f"{p.model_prob * 100:.1f}%"] for p in coupon],
        headers=["Mac", "Pazar", "Secim", "Olasilik"],
    ))
    print(f"\nKombine olasilik (bagimsizlik varsayimiyla): {combined_probability(coupon) * 100:.2f}%")
    print("\nNot: Bu olasiliklar istatistiksel bir modelden gelir, garanti degildir. Sorumlu bahis oynayin.\n")


def cmd_backtest(args):
    from .backtest import run_backtest

    print(f"Backtest: {args.league} {', '.join(args.season)} "
          f"(ilk %{args.split * 100:.0f} egitim, kalan test)\n")
    res = run_backtest(args.league, args.season, args.split)

    labels = {"model": "futbot (Dixon-Coles)", "pinnacle": "Pinnacle kapanis",
              "baseline": "Baz cizgi (H/D/A frekansi)"}
    print()
    print(tabulate(
        [[labels[k], f"{v['log_loss']:.4f}", f"{v['brier']:.4f}"] for k, v in res.items()],
        headers=["Tahminci", "Log-loss", "Brier"],
    ))

    m, b, base = res["model"]["log_loss"], res["pinnacle"]["log_loss"], res["baseline"]["log_loss"]
    # Baz cizgiden piyasaya olan mesafenin ne kadarini model kapatiyor?
    gap_closed = (base - m) / (base - b) if base != b else float("nan")
    print(f"\n{res['model']['n']} mac | log-loss farki (model - piyasa): {m - b:+.4f} | "
          f"baz cizgi -> piyasa mesafesinin %{gap_closed * 100:.0f}'i kapatildi")
    print("(Dusuk log-loss/Brier daha iyidir.)")


def main():
    parser = argparse.ArgumentParser(description="Futbol mac olasilik ve kupon botu")
    sub = parser.add_subparsers(dest="command", required=True)

    p_predict = sub.add_parser("predict", help="Tek mac icin olasilik tahmini")
    p_predict.add_argument("--home", required=True)
    p_predict.add_argument("--away", required=True)
    p_predict.add_argument("--demo", action="store_true")
    p_predict.add_argument("--league-id", type=int)
    p_predict.add_argument("--season", type=int)
    p_predict.add_argument("--refresh", action="store_true", help="Cache'i yok say, modeli yeniden egit")
    p_predict.add_argument("--cache-hours", type=float, default=24.0, help="Cache'in gecerli sayilacagi sure (saat)")
    p_predict.set_defaults(func=cmd_predict)

    p_live = sub.add_parser("live", help="Canli mac icin guncellenmis olasilik")
    p_live.add_argument("--home", required=True)
    p_live.add_argument("--away", required=True)
    p_live.add_argument("--minute", type=int, required=True)
    p_live.add_argument("--score", required=True, help="Ornek: 1-0")
    p_live.add_argument("--demo", action="store_true")
    p_live.add_argument("--league-id", type=int)
    p_live.add_argument("--season", type=int)
    p_live.add_argument("--refresh", action="store_true", help="Cache'i yok say, modeli yeniden egit")
    p_live.add_argument("--cache-hours", type=float, default=24.0, help="Cache'in gecerli sayilacagi sure (saat)")
    p_live.set_defaults(func=cmd_live)

    p_coupon = sub.add_parser("coupon", help="Birden fazla mactan kupon oner")
    p_coupon.add_argument("--demo", action="store_true")
    p_coupon.add_argument("--top", type=int, default=5)
    p_coupon.add_argument("--min-prob", type=float, default=0.45)
    p_coupon.add_argument("--league-id", type=int)
    p_coupon.add_argument("--season", type=int)
    p_coupon.add_argument("--refresh", action="store_true", help="Cache'i yok say, modeli yeniden egit")
    p_coupon.add_argument("--cache-hours", type=float, default=24.0, help="Cache'in gecerli sayilacagi sure (saat)")
    p_coupon.set_defaults(func=cmd_coupon)

    p_bt = sub.add_parser("backtest", help="Modeli bahis piyasasina karsi geriye donuk test et")
    p_bt.add_argument("--league", default="T1", help="football-data.co.uk lig kodu (T1=Super Lig, E0=Premier League)")
    p_bt.add_argument("--season", nargs="+", default=["2223", "2324"], help="Sezon kodlari, orn. 2324 = 2023/24")
    p_bt.add_argument("--split", type=float, default=0.5, help="Egitime ayrilan mac orani")
    p_bt.set_defaults(func=cmd_backtest)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
