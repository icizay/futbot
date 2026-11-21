"""
Canli mac takibi: devam eden bir mac icin, kalan sureye gore beklenen gol
sayisini yeniden olcekleyip olasiliklari gunceller.

Yaklasim: modelin 90 dk icin tahmin ettigi lambda (beklenen gol), kalan
dakika oranina gore olceklenir; mevcut skor sabit kabul edilip uzerine
kalan suredeki gol dagilimi eklenir. Basit ama gercek zamanli guncelleme
icin makul bir yaklastirma; daha ileri versiyon icin mac ici xG/sut verisi
de modele eklenebilir.
"""

from __future__ import annotations
import time
from typing import Callable, Optional

import numpy as np
from scipy.stats import poisson

from .poisson_model import DixonColesModel


def live_market_probabilities(
    model: DixonColesModel,
    home: str,
    away: str,
    minute: int,
    current_home_goals: int,
    current_away_goals: int,
    max_extra_goals: int = 6,
) -> dict:
    """Macin o anki dakikasina gore guncellenmis market olasiliklarini dondurur."""
    minute = min(max(minute, 0), 90)
    remaining_fraction = (90 - minute) / 90

    lam_home_full, lam_away_full = model.expected_goals(home, away)
    lam_home_remaining = lam_home_full * remaining_fraction
    lam_away_remaining = lam_away_full * remaining_fraction

    size = max_extra_goals + 1
    home_extra = [poisson.pmf(i, lam_home_remaining) for i in range(size)]
    away_extra = [poisson.pmf(i, lam_away_remaining) for i in range(size)]
    extra_matrix = np.outer(home_extra, away_extra)

    p_home = p_draw = p_away = 0.0
    goal_totals: dict = {}
    for i in range(size):
        for j in range(size):
            p = extra_matrix[i, j]
            final_home = current_home_goals + i
            final_away = current_away_goals + j
            if final_home > final_away:
                p_home += p
            elif final_home == final_away:
                p_draw += p
            else:
                p_away += p
            total = final_home + final_away
            goal_totals[total] = goal_totals.get(total, 0.0) + p

    over_25 = sum(p for g, p in goal_totals.items() if g >= 3)

    return {
        "minute": minute,
        "current_score": f"{current_home_goals}-{current_away_goals}",
        "1x2": {"home": p_home, "draw": p_draw, "away": p_away},
        "over_under_2_5": {"over": over_25, "under": 1 - over_25},
    }


def poll_live_match(
    fetch_live_state: Callable[[], dict],
    model: DixonColesModel,
    interval_seconds: int = 30,
    max_polls: Optional[int] = None,
    on_update: Optional[Callable[[dict], None]] = None,
) -> None:
    """
    fetch_live_state: her cagrida
        {"home": str, "away": str, "minute": int, "home_goals": int, "away_goals": int}
        dondurmesi gereken fonksiyon (gercek API'ye baglanacak yer burasi).
    on_update: her guncellemede sonucu isleyecek callback (varsayilan: print)
    """
    polls = 0
    while max_polls is None or polls < max_polls:
        state = fetch_live_state()
        probs = live_market_probabilities(
            model, state["home"], state["away"], state["minute"],
            state["home_goals"], state["away_goals"],
        )
        (on_update or print)(probs)
        polls += 1
        if max_polls is None or polls < max_polls:
            time.sleep(interval_seconds)
