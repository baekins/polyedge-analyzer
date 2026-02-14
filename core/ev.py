"""Edge, Expected Value, and ROI calculations."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def compute_edge(p_hat: float, q_eff: float) -> float:
    """Edge = p̂ − q_eff."""
    return p_hat - q_eff


def compute_ev_per_dollar(p_hat: float, q_eff: float) -> float:
    """
    EV per $1 risked on a YES share bought at q_eff.

    If the share wins, you receive $1 (profit = 1 − q_eff).
    If it loses, you lose q_eff.

    EV = p̂ * (1 − q_eff) − (1 − p̂) * q_eff
       = p̂ − q_eff
    Per dollar risked (risked amount = q_eff):
    EV/$ = (p̂ − q_eff) / q_eff
    """
    if q_eff <= 0:
        return 0.0
    return (p_hat - q_eff) / q_eff


def compute_roi_pct(p_hat: float, q_eff: float) -> float:
    """ROI % = EV_per_dollar * 100."""
    return compute_ev_per_dollar(p_hat, q_eff) * 100


def compute_kelly_fraction(p_hat: float, q_eff: float) -> float:
    """
    Kelly criterion for a binary bet bought at q_eff paying $1 on win.

    f* = (p̂ − q_eff) / (1 − q_eff)

    Returns 0 when edge is non-positive.
    """
    if p_hat <= q_eff or q_eff >= 1.0:
        return 0.0
    return (p_hat - q_eff) / (1 - q_eff)
