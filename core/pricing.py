"""Effective price calculation: fees + slippage estimation."""

from __future__ import annotations

import logging

from core.schemas import EffectivePrice, FeeInfo, OrderBookLevel

logger = logging.getLogger(__name__)


def compute_q_eff(
    best_ask: float,
    fee_info: FeeInfo,
    order_size: float = 0.0,
    ask_levels: list[OrderBookLevel] | None = None,
) -> EffectivePrice:
    """
    Compute effective buy price for a YES share.

    q_eff = q / (1 - r * min(q, 1-q) * q)   (taker buy approximation)
    + optional slippage from walking the book.

    Parameters
    ----------
    best_ask : raw best ask price (0–1 range)
    fee_info : fee rate info
    order_size : intended order size in shares (for slippage calc)
    ask_levels : ask side of orderbook for slippage estimation
    """
    q = best_ask
    r = fee_info.fee_rate  # decimal

    # Fee component
    if r > 0 and 0 < q < 1:
        fee_adj = r * min(q, 1 - q) * q
        denom = 1 - fee_adj
        if denom > 0:
            q_after_fee = q / denom
        else:
            q_after_fee = q
        fee_component = q_after_fee - q
    else:
        q_after_fee = q
        fee_component = 0.0

    # Slippage estimation (walk the book)
    slippage = 0.0
    if order_size > 0 and ask_levels:
        slippage = _estimate_slippage(order_size, ask_levels, best_ask)

    q_eff = q_after_fee + slippage

    # Clamp to (0, 1)
    q_eff = max(0.001, min(q_eff, 0.999))

    return EffectivePrice(
        q_raw=best_ask,
        q_eff=q_eff,
        fee_component=fee_component,
        slippage_estimate=slippage,
    )


def _estimate_slippage(
    order_size: float,
    ask_levels: list[OrderBookLevel],
    best_ask: float,
) -> float:
    """Estimate average slippage above best_ask for a given order size."""
    remaining = order_size
    weighted_sum = 0.0
    filled = 0.0

    for level in sorted(ask_levels, key=lambda x: x.price):
        if remaining <= 0:
            break
        fill = min(remaining, level.size)
        weighted_sum += fill * level.price
        filled += fill
        remaining -= fill

    if filled <= 0:
        return 0.0

    vwap = weighted_sum / filled
    return max(0.0, vwap - best_ask)
