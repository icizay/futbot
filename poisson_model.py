"""
Dixon-Coles / Poisson tabanli futbol mac sonucu olasilik modeli.

Gecmis mac sonuclarindan takimlarin hucum/savunma gucunu tahmin eder
ve bu gucleri kullanarak bir mac icin skor olasilik matrisini hesaplar.

Referans: Dixon, M.J. and Coles, S.G. (1997) "Modelling Association
Football Scores and Inefficiencies in the Football Betting Market"
"""

from __future__ import annotations
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple, Union
import numpy as np
from scipy.optimize import minimize
from scipy.stats import poisson


@dataclass
class TeamStrength:
    attack: float
    defense: float


@dataclass
class DixonColesModel:
    home_advantage: float = 0.25
    rho: float = -0.05  # dusuk skor korelasyon duzeltmesi
    team_strength: Dict[str, TeamStrength] = field(default_factory=dict)
    league_avg_goals: float = 2.6

    # ---------- Fitting ----------
    def fit(self, matches: List[dict]) -> None:
        """
        matches: [{"home": "Galatasaray", "away": "Fenerbahce",
                    "home_goals": 2, "away_goals": 1, "weight": 1.0}, ...]
        weight: opsiyonel, son maclara daha fazla agirlik vermek icin
        """
        if not matches:
            raise ValueError("Eğitim için maç verisi bulunamadı! Lig ID'sini veya sezonu kontrol edin.") #addedthis
    
         # ... mevcut kodlar ...
        
        teams = sorted({m["home"] for m in matches} | {m["away"] for m in matches})
        n = len(teams)
        idx = {t: i for i, t in enumerate(teams)}

        total_goals = sum(m["home_goals"] + m["away_goals"] for m in matches)
        self.league_avg_goals = total_goals / (2 * len(matches))

        x0 = np.concatenate([np.zeros(n), np.zeros(n), [0.25], [-0.05]])

        def neg_log_likelihood(x):
            attack = x[:n]
            defense = x[n:2 * n]
            home_adv = x[2 * n]
            rho = x[2 * n + 1]
            ll = 0.0
            for m in matches:
                hi, ai = idx[m["home"]], idx[m["away"]]
                lam_home = math.exp(attack[hi] - defense[ai] + home_adv)
                lam_away = math.exp(attack[ai] - defense[hi])
                w = m.get("weight", 1.0)
                ll += w * (
                    poisson.logpmf(m["home_goals"], lam_home)
                    + poisson.logpmf(m["away_goals"], lam_away)
                )
            ll -= 0.01 * (np.sum(attack ** 2) + np.sum(defense ** 2))
            return -ll

        res = minimize(neg_log_likelihood, x0, method="L-BFGS-B")
        x = res.x
        attack, defense = x[:n], x[n:2 * n]
        self.home_advantage = float(x[2 * n])
        self.rho = float(x[2 * n + 1])
        self.team_strength = {
            t: TeamStrength(attack=float(attack[i]), defense=float(defense[i]))
            for t, i in idx.items()
        }
        
        self.league_avg_goals = total_goals / (2 * len(matches)) # added

    # ---------- Prediction ----------
    def expected_goals(self, home: str, away: str) -> Tuple[float, float]:
        h = self.team_strength.get(home, TeamStrength(0, 0))
        a = self.team_strength.get(away, TeamStrength(0, 0))
        lam_home = math.exp(h.attack - a.defense + self.home_advantage)
        lam_away = math.exp(a.attack - h.defense)
        return lam_home, lam_away

    def score_matrix(self, home: str, away: str, max_goals: int = 8) -> np.ndarray:
        lam_home, lam_away = self.expected_goals(home, away)
        home_probs = [poisson.pmf(i, lam_home) for i in range(max_goals + 1)]
        away_probs = [poisson.pmf(i, lam_away) for i in range(max_goals + 1)]
        matrix = np.outer(home_probs, away_probs)

        tau = self._dc_adjustment(lam_home, lam_away, self.rho)
        matrix[0, 0] *= tau[0]
        matrix[0, 1] *= tau[1]
        matrix[1, 0] *= tau[2]
        matrix[1, 1] *= tau[3]

        matrix = np.clip(matrix, 0, None)
        matrix /= matrix.sum()
        return matrix

    @staticmethod
    def _dc_adjustment(lam_home, lam_away, rho):
        return (
            1 - lam_home * lam_away * rho,
            1 + lam_home * rho,
            1 + lam_away * rho,
            1 - rho,
        )

    # ---------- Persistence (cache icin) ----------
    def to_dict(self) -> dict:
        """Egitilmis modeli JSON'a uygun bir sozluge cevirir."""
        return {
            "home_advantage": self.home_advantage,
            "rho": self.rho,
            "league_avg_goals": self.league_avg_goals,
            "team_strength": {
                t: {"attack": s.attack, "defense": s.defense}
                for t, s in self.team_strength.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DixonColesModel":
        model = cls(
            home_advantage=data["home_advantage"],
            rho=data["rho"],
            league_avg_goals=data.get("league_avg_goals", 2.6),
        )
        model.team_strength = {
            t: TeamStrength(attack=v["attack"], defense=v["defense"])
            for t, v in data["team_strength"].items()
        }
        return model

    def save(self, path: Union[str, Path]) -> None:
        """Egitilmis modeli bir JSON dosyasina yazar (yeniden egitmeden tekrar kullanmak icin)."""
        Path(path).write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Union[str, Path]) -> "DixonColesModel":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(data)

    # ---------- Markets ----------
    def market_probabilities(self, home: str, away: str, max_goals: int = 8) -> dict:
        M = self.score_matrix(home, away, max_goals)
        n = M.shape[0]

        p_home = float(np.sum(np.tril(M, -1)))
        p_draw = float(np.sum(np.diag(M)))
        p_away = float(np.sum(np.triu(M, 1)))

        goal_totals: Dict[int, float] = {}
        for i in range(n):
            for j in range(n):
                total = i + j
                goal_totals[total] = goal_totals.get(total, 0.0) + M[i, j]

        over_25 = sum(p for g, p in goal_totals.items() if g >= 3)
        under_25 = 1 - over_25

        btts_yes = float(np.sum(M[1:, 1:]))
        btts_no = 1 - btts_yes

        flat = [((i, j), M[i, j]) for i in range(n) for j in range(n)]
        top_scores = sorted(flat, key=lambda x: -x[1])[:5]

        lam_home, lam_away = self.expected_goals(home, away)

        return {
            "1x2": {"home": p_home, "draw": p_draw, "away": p_away},
            "over_under_2_5": {"over": over_25, "under": under_25},
            "btts": {"yes": btts_yes, "no": btts_no},
            "top_scores": [{"score": f"{i}-{j}", "prob": p} for (i, j), p in top_scores],
            "expected_goals": {"home": lam_home, "away": lam_away},
        }
