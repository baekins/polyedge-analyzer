"""Probability estimation: combine market, bookmaker, stat-model, and Claude signals."""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def clamp(value: float, lo: float = 0.01, hi: float = 0.99) -> float:
    return max(lo, min(hi, value))


def combine_probabilities(
    p_mkt: float,
    p_books: Optional[float] = None,
    p_stat: Optional[float] = None,
    p_claude: Optional[float] = None,
    w_mkt: float = 0.4,
    w_books: float = 0.4,
    w_model: float = 0.15,
    w_claude: float = 0.05,
) -> float:
    """
    Weighted-average probability estimator.

    If some sources are missing (None), their weight is redistributed
    proportionally among available sources.

    Returns p̂ clamped to [0.01, 0.99].
    """
    sources: list[tuple[float, float]] = []  # (probability, weight)
    sources.append((p_mkt, w_mkt))
    if p_books is not None:
        sources.append((p_books, w_books))
    if p_stat is not None:
        sources.append((p_stat, w_model))
    if p_claude is not None:
        sources.append((p_claude, w_claude))

    total_w = sum(w for _, w in sources)
    if total_w <= 0:
        return clamp(p_mkt)

    p_hat = sum(p * (w / total_w) for p, w in sources)
    return clamp(p_hat)


def remove_vig(odds_list: list[float]) -> list[float]:
    """
    Remove bookmaker vig from a list of implied probabilities.

    E.g. if two outcomes imply 0.55 + 0.52 = 1.07, normalize to sum=1.
    """
    total = sum(odds_list)
    if total <= 0:
        return odds_list
    return [p / total for p in odds_list]


def implied_prob_from_decimal_odds(decimal_odds: float) -> float:
    """Convert decimal odds (e.g. 1.80) to implied probability."""
    if decimal_odds <= 1.0:
        return 1.0
    return 1.0 / decimal_odds
