"""
Backtest: modeli bahis piyasasina karsi olcer.

Her sezon icin maclar tarihe gore siralanir; ilk yarisiyla model egitilir,
ikinci yarisi tahmin edilir. Tahminler 1X2 sonucu uzerinden log-loss ve
Brier skoruyla puanlanir ve ayni maclar icin Pinnacle kapanis oranlarinin
ima ettigi olasiliklarla karsilastirilir.

Veri kaynagi: football-data.co.uk (sonuclar + kapanis oranlari ayni satirda).
Lig kodlari: T1 = Super Lig, E0 = Premier League, SP1 = La Liga, D1 = Bundesliga ...
Sezon kodu: "2324" = 2023/24.
"""

from __future__ import annotations

import csv
import io
import math
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import requests

from .poisson_model import DixonColesModel

FD_URL = "https://www.football-data.co.uk/mmz4281/{season}/{league}.csv"
CACHE_DIR = Path(__file__).resolve().parent / ".cache" / "football-data"

OUTCOMES = ("H", "D", "A")  # ev sahibi / beraberlik / deplasman
Probs = Tuple[float, float, float]


# ---------------- Veri ----------------
def load_season(league: str, season: str) -> List[dict]:
    """Bir sezonun maclarini (sonuc + Pinnacle kapanis oranlari) dondurur, CSV'yi diske cache'ler."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{league}_{season}.csv"
    if not path.exists():
        r = requests.get(FD_URL.format(league=league, season=season), timeout=30)
        r.raise_for_status()
        path.write_bytes(r.content)

    text = path.read_bytes().decode("utf-8-sig", errors="replace")
    matches = []
    for row in csv.DictReader(io.StringIO(text)):
        try:
            odds = (float(row["PSCH"]), float(row["PSCD"]), float(row["PSCA"]))
            matches.append({
                "date": _parse_date(row["Date"]),
                "home": row["HomeTeam"],
                "away": row["AwayTeam"],
                "home_goals": int(row["FTHG"]),
                "away_goals": int(row["FTAG"]),
                "result": row["FTR"],
                "odds": odds,
            })
        except (KeyError, ValueError):
            continue  # oran ya da skor eksik satirlari atla
    matches.sort(key=lambda m: m["date"])
    return matches


def _parse_date(s: str) -> datetime:
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    raise ValueError(f"Tarih okunamadi: {s}")


# ---------------- Oranlar -> olasilik ----------------
def implied_probabilities(odds: Sequence[float]) -> Probs:
    """
    Ondalik oranlari (ev, beraberlik, deplasman) olasiliga cevirir.

    1/oran toplami 1'den buyuktur (orn. 1.03): aradaki fark bahis sirketinin
    marji (overround). Donen uc olasiligin toplami tam 1 olmali.

    Power yontemi: sum((1/oran)^k) = 1 olacak k bulunur. Her 1/oran < 1
    oldugu icin k > 1 ust alma, kucuk olasiliklari (surprizleri) oransal
    olarak daha cok kucultur; bu da bahisciilerin marji daha cok surpriz
    sonuclara yukledigi favori/surpriz yanliligini (favorite-longshot bias)
    hesaba katar. Basit normalizasyona gore piyasayi daha adil temsil eder.
    """
    raw = [1.0 / o for o in odds]
    lo, hi = 1.0, 10.0  # toplam(k=1) >= 1, toplam(k=10) << 1
    for _ in range(100):  # ikili arama; toplam k'ye gore monoton azalir
        k = (lo + hi) / 2
        if sum(r ** k for r in raw) > 1.0:
            lo = k
        else:
            hi = k
    p = [r ** k for r in raw]
    s = sum(p)
    return (p[0] / s, p[1] / s, p[2] / s)


# ---------------- Metrikler ----------------
def log_loss(p: Probs, outcome: int) -> float:
    return -math.log(max(p[outcome], 1e-15))


def brier(p: Probs, outcome: int) -> float:
    return sum((p[k] - (1.0 if k == outcome else 0.0)) ** 2 for k in range(3))


# ---------------- Backtest ----------------
def backtest_season(matches: List[dict], split: float = 0.5) -> Dict[str, dict]:
    """Ilk `split` oraniyla egitir, kalan maclarda model / piyasa / baz cizgiyi puanlar."""
    cut = int(len(matches) * split)
    train, test = matches[:cut], matches[cut:]

    model = DixonColesModel()
    model.fit(train)

    # Baz cizgi: egitim setindeki H/D/A frekanslari (takimlardan habersiz tahmin)
    freq = [sum(m["result"] == o for m in train) / len(train) for o in OUTCOMES]
    baseline: Probs = (freq[0], freq[1], freq[2])

    scores = {name: {"log_loss": 0.0, "brier": 0.0} for name in ("model", "pinnacle", "baseline")}
    for m in test:
        y = OUTCOMES.index(m["result"])
        p1x2 = model.market_probabilities(m["home"], m["away"])["1x2"]
        preds = {
            "model": (p1x2["home"], p1x2["draw"], p1x2["away"]),
            "pinnacle": implied_probabilities(m["odds"]),
            "baseline": baseline,
        }
        for name, p in preds.items():
            scores[name]["log_loss"] += log_loss(p, y)
            scores[name]["brier"] += brier(p, y)

    for s in scores.values():
        s["log_loss"] /= len(test)
        s["brier"] /= len(test)
        s["n"] = len(test)
    return scores


def run_backtest(league: str, seasons: Sequence[str], split: float = 0.5) -> Dict[str, dict]:
    """Birden fazla sezonu ayri ayri backtest edip mac sayisina gore agirlikli ortalar."""
    total: Dict[str, dict] = {}
    for season in seasons:
        res = backtest_season(load_season(league, season), split)
        print(f"  {league} {season}: model {res['model']['log_loss']:.4f} | "
              f"pinnacle {res['pinnacle']['log_loss']:.4f} | n={res['model']['n']}")
        for name, s in res.items():
            t = total.setdefault(name, {"log_loss": 0.0, "brier": 0.0, "n": 0})
            t["log_loss"] += s["log_loss"] * s["n"]
            t["brier"] += s["brier"] * s["n"]
            t["n"] += s["n"]
    for t in total.values():
        t["log_loss"] /= t["n"]
        t["brier"] /= t["n"]
    return total
