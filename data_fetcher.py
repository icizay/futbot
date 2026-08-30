"""
Veri katmani: API-Football (RapidAPI / api-sports.io) uzerinden gecmis ve
canli mac verisi ceker.

API anahtari almak icin: https://www.api-football.com/  (ucretsiz plan mevcut)
Ortam degiskeni: API_FOOTBALL_KEY

Not: football-data.org da alternatif/ucretsiz bir kaynaktir, ancak canli
veri destegi sinirlidir; live-tracker icin api-football.com onerilir.
"""

from __future__ import annotations
import math
import os
import random
from typing import List, Optional

from pathlib import Path

import requests
from dotenv import load_dotenv

# .env dosyasini, calisma dizini ne olursa olsun bu dosyanin (data_fetcher.py)
# bulundugu klasorden okur -> futbot/.env
load_dotenv(Path(__file__).resolve().parent / ".env")

API_BASE = "https://v3.football.api-sports.io"


class DataFetcher:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("API_FOOTBALL_KEY")

    def _headers(self):
        if not self.api_key:
            raise RuntimeError(
                "API_FOOTBALL_KEY bulunamadi. Ortam degiskeni olarak ayarlayin "
                "ya da --demo modunu kullanin."
            )
        return {"x-apisports-key": self.api_key}

    def get_historical_fixtures(self, league_id: int, season: int) -> List[dict]:
        r = requests.get(
            f"{API_BASE}/fixtures",
            headers=self._headers(),
            params={"league": league_id, "season": season, "status": "FT"},
            timeout=15,
        )
        r.raise_for_status()
        
        # --- ŞU İKİ SATIRI EKLER MİSİN? ---
        json_data = r.json()
        if "errors" in json_data and json_data["errors"]:
            print("API HATASI:", json_data["errors"])
        # ----------------------------------
        
        data = json_data["response"]
        # ... (listenin kalanı devam ediyor)
        
        data = r.json()["response"]
        return [
            {
                "home": f["teams"]["home"]["name"],
                "away": f["teams"]["away"]["name"],
                "home_goals": f["goals"]["home"],
                "away_goals": f["goals"]["away"],
                "date": f["fixture"]["date"],
            }
            for f in data
        ]
        
    def get_upcoming_fixtures(self, league_id: int, season: int, next_n: int = 10) -> List[dict]:
        r = requests.get(
            f"{API_BASE}/fixtures",
            headers=self._headers(),
            params={"league": league_id, "season": season, "next": next_n},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()["response"]
        return [
            {"home": f["teams"]["home"]["name"], "away": f["teams"]["away"]["name"],
            "fixture_id": f["fixture"]["id"], "date": f["fixture"]["date"]}
            for f in data
        ]       

    def get_live_fixtures(self, league_id: Optional[int] = None) -> List[dict]:
        params = {"live": "all"}
        if league_id:
            params["league"] = league_id
        r = requests.get(f"{API_BASE}/fixtures", headers=self._headers(), params=params, timeout=15)
        r.raise_for_status()
        return r.json()["response"]

    def get_odds(self, fixture_id: int) -> dict:
        r = requests.get(
            f"{API_BASE}/odds",
            headers=self._headers(),
            params={"fixture": fixture_id},
            timeout=15,
        )
        r.raise_for_status()
        return r.json()["response"]


# ---------------- Demo / offline mod ----------------
DEMO_TEAMS = [
    "Galatasaray", "Fenerbahce", "Besiktas", "Trabzonspor",
    "Basaksehir", "Adana Demirspor", "Konyaspor", "Kasimpasa",
]


def _poisson_sample(rng: random.Random, lam: float) -> int:
    L = math.exp(-lam)
    k, p = 0, 1.0
    while True:
        k += 1
        p *= rng.random()
        if p <= L:
            return k - 1


def generate_demo_history(n_matches: int = 200, seed: int = 42) -> List[dict]:
    """Test/gelistirme amacli, tutarli (sabit seed) sentetik mac verisi uretir."""
    rng = random.Random(seed)
    strengths = {t: rng.uniform(0.7, 1.5) for t in DEMO_TEAMS}
    matches = []
    for _ in range(n_matches):
        home, away = rng.sample(DEMO_TEAMS, 2)
        lam_home = strengths[home] * 1.3
        lam_away = strengths[away] * 0.9
        matches.append({
            "home": home,
            "away": away,
            "home_goals": _poisson_sample(rng, lam_home),
            "away_goals": _poisson_sample(rng, lam_away),
        })
    return matches
