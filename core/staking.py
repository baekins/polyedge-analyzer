"""Kelly-based stake sizing with safety caps."""

from __future__ import annotations

import logging

from core.ev import compute_kelly_fraction

logger = logging.getLogger(__name__)


def compute_stake(
    p_hat: float,
    q_eff: float,
    bankroll: float = 5000.0,
    kelly_fraction: float = 0.5,
    max_bet_pct: float = 0.03,
) -> float:
    """
    Recommended stake in USDT.

    stake = bankroll × f* × kelly_fraction
    stake = min(stake, bankroll × max_bet_pct)
    stake = max(stake, 0)

    Parameters
    ----------
    p_hat : estimated true probability
    q_eff : effective buy price (after fees/slippage)
    bankroll : total bankroll in USDT
    kelly_fraction : fraction of full Kelly (e.g. 0.5 = half-Kelly)
    max_bet_pct : maximum bet as fraction of bankroll
    """
    f_star = compute_kelly_fraction(p_hat, q_eff)
    stake = bankroll * f_star * kelly_fraction
    cap = bankroll * max_bet_pct
    stake = min(stake, cap)
    stake = max(stake, 0.0)
    return round(stake, 2)
