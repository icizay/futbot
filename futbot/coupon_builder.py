"""
Kupon olusturucu: birden fazla macin model olasiliklarini (ve varsa bahis
oranlarini) karsilastirip en 'degerli' secimlerden bir kupon kurar.

'Value' tanimi: model_olasiligi > oranin_ima_ettigi_olasilik
(bahis sirketinin fiyatladigindan daha olasi oldugunu modelin dusundugu secim)
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict


@dataclass
class Pick:
    match: str
    market: str
    selection: str
    model_prob: float
    odds: Optional[float] = None

    @property
    def implied_prob(self) -> Optional[float]:
        return 1 / self.odds if self.odds else None

    @property
    def edge(self) -> Optional[float]:
        if self.implied_prob is None:
            return None
        return self.model_prob - self.implied_prob


def picks_from_market_probs(
    match_name: str,
    market_probs: dict,
    odds: Optional[Dict[Tuple[str, str], float]] = None,
) -> List[Pick]:
    """market_probs: DixonColesModel.market_probabilities() ciktisi"""
    picks: List[Pick] = []
    odds = odds or {}

    for sel, p in market_probs["1x2"].items():
        picks.append(Pick(match_name, "1X2", sel, p, odds.get(("1x2", sel))))
    for sel, p in market_probs["over_under_2_5"].items():
        picks.append(Pick(match_name, "2.5 Alt/Ust", sel, p, odds.get(("over_under_2_5", sel))))
    for sel, p in market_probs["btts"].items():
        picks.append(Pick(match_name, "KG Var/Yok", sel, p, odds.get(("btts", sel))))
    return picks


def build_coupon(all_picks: List[Pick], top_n: int = 5, min_prob: float = 0.45) -> List[Pick]:
    """
    Oran verisi varsa 'edge'e (value) gore, yoksa saf model olasiligina gore siralar.
    min_prob: cok dusuk olasilikli secimleri kupon disi birakmak icin esik.
    Ayni mactan birden fazla secim eklenmez (korelasyon riskini azaltmak icin).
    """
    candidates = [p for p in all_picks if p.model_prob >= min_prob]
    has_odds = any(p.odds for p in candidates)
    candidates.sort(key=lambda p: (p.edge if has_odds and p.edge is not None else p.model_prob), reverse=True)

    coupon: List[Pick] = []
    used_matches = set()
    for p in candidates:
        if p.match in used_matches:
            continue
        coupon.append(p)
        used_matches.add(p.match)
        if len(coupon) >= top_n:
            break
    return coupon


def combined_probability(picks: List[Pick]) -> float:
    """Farkli maclardaki secimler bagimsiz kabul edilir."""
    prob = 1.0
    for p in picks:
        prob *= p.model_prob
    return prob
