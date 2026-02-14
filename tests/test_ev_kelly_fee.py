"""Tests for EV, Kelly, fee/pricing calculations – v0.2.0."""

from __future__ import annotations

import pytest

from core.ev import (
    compute_edge, compute_ev_per_dollar, compute_kelly_fraction,
    compute_roi_pct, compute_kelly_with_confidence, classify_signal,
    compute_risk_adjusted_edge, compute_expected_growth,
)
from core.pricing import compute_q_eff
from core.staking import compute_stake
from core.models import (
    combine_probabilities, remove_vig, implied_prob_from_decimal_odds,
    compute_confidence_score,
)
from core.schemas import FeeInfo, OrderBookLevel


# ═══════════════════════════════════════════════════════════════════════════════
# EV / Edge tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestEdge:
    def test_positive_edge(self) -> None:
        assert compute_edge(0.60, 0.55) == pytest.approx(0.05)

    def test_zero_edge(self) -> None:
        assert compute_edge(0.50, 0.50) == pytest.approx(0.0)

    def test_negative_edge(self) -> None:
        assert compute_edge(0.40, 0.55) == pytest.approx(-0.15)


class TestEVPerDollar:
    def test_positive_ev(self) -> None:
        assert compute_ev_per_dollar(0.60, 0.50) == pytest.approx(0.2)

    def test_zero_ev(self) -> None:
        assert compute_ev_per_dollar(0.50, 0.50) == pytest.approx(0.0)

    def test_negative_ev(self) -> None:
        assert compute_ev_per_dollar(0.40, 0.50) == pytest.approx(-0.2)

    def test_zero_qeff_returns_zero(self) -> None:
        assert compute_ev_per_dollar(0.50, 0.0) == 0.0


class TestROI:
    def test_roi_positive(self) -> None:
        assert compute_roi_pct(0.60, 0.50) == pytest.approx(20.0)

    def test_roi_negative(self) -> None:
        assert compute_roi_pct(0.40, 0.50) == pytest.approx(-20.0)


# ═══════════════════════════════════════════════════════════════════════════════
# Kelly fraction tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestKelly:
    def test_basic_kelly(self) -> None:
        assert compute_kelly_fraction(0.60, 0.50) == pytest.approx(0.2)

    def test_no_edge_kelly_zero(self) -> None:
        assert compute_kelly_fraction(0.50, 0.50) == 0.0

    def test_negative_edge_kelly_zero(self) -> None:
        assert compute_kelly_fraction(0.40, 0.55) == 0.0

    def test_high_edge_kelly(self) -> None:
        assert compute_kelly_fraction(0.90, 0.20) == pytest.approx(0.875)

    def test_qeff_near_one(self) -> None:
        assert compute_kelly_fraction(0.99, 1.0) == 0.0

    def test_tiny_edge(self) -> None:
        assert compute_kelly_fraction(0.51, 0.50) == pytest.approx(0.02)


class TestKellyWithConfidence:
    def test_full_confidence(self) -> None:
        # confidence=1.0 → same as regular kelly
        assert compute_kelly_with_confidence(0.60, 0.50, 1.0) == pytest.approx(0.2)

    def test_half_confidence(self) -> None:
        # confidence=0.5 → 0.2 * 0.25 = 0.05
        assert compute_kelly_with_confidence(0.60, 0.50, 0.5) == pytest.approx(0.05)

    def test_zero_confidence(self) -> None:
        assert compute_kelly_with_confidence(0.60, 0.50, 0.0) == 0.0

    def test_no_edge(self) -> None:
        assert compute_kelly_with_confidence(0.40, 0.50, 1.0) == 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# Risk-adjusted edge & growth rate
# ═══════════════════════════════════════════════════════════════════════════════

class TestRiskAdjustedEdge:
    def test_positive_edge(self) -> None:
        # edge=0.1, σ=sqrt(0.6*0.4)=0.4899 → ratio ≈ 0.2041
        result = compute_risk_adjusted_edge(0.60, 0.50)
        assert result > 0

    def test_zero_edge(self) -> None:
        assert compute_risk_adjusted_edge(0.50, 0.50) == pytest.approx(0.0)


class TestExpectedGrowth:
    def test_positive_growth(self) -> None:
        # With edge, growth should be positive
        g = compute_expected_growth(0.60, 0.50)
        assert g > 0

    def test_no_edge_zero_growth(self) -> None:
        g = compute_expected_growth(0.50, 0.50)
        assert g == pytest.approx(0.0, abs=0.001)


# ═══════════════════════════════════════════════════════════════════════════════
# Signal classification
# ═══════════════════════════════════════════════════════════════════════════════

class TestClassifySignal:
    def test_strong_buy(self) -> None:
        s = classify_signal(edge=0.05, roi_pct=10, confidence_score=0.7, bid_depth=500, ask_depth=500)
        assert s == "강력매수"

    def test_buy(self) -> None:
        s = classify_signal(edge=0.02, roi_pct=4, confidence_score=0.3, bid_depth=10, ask_depth=10)
        assert s == "매수"

    def test_hold(self) -> None:
        s = classify_signal(edge=0.005, roi_pct=1, confidence_score=0.3, bid_depth=10, ask_depth=10)
        assert s == "보류"

    def test_skip(self) -> None:
        s = classify_signal(edge=-0.01, roi_pct=-2, confidence_score=0.3, bid_depth=10, ask_depth=10)
        assert s == "패스"


# ═══════════════════════════════════════════════════════════════════════════════
# Fee / effective price tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestQEff:
    def test_zero_fee(self) -> None:
        fee = FeeInfo(fee_rate_bps=0, fee_rate=0)
        result = compute_q_eff(0.50, fee)
        assert result.q_eff == pytest.approx(0.50)
        assert result.fee_component == pytest.approx(0.0)

    def test_with_fee(self) -> None:
        fee = FeeInfo(fee_rate_bps=200, fee_rate=0.02)
        result = compute_q_eff(0.50, fee)
        assert result.q_eff > 0.50
        assert result.q_eff == pytest.approx(0.50 / 0.995, abs=0.001)

    def test_high_price_with_fee(self) -> None:
        fee = FeeInfo(fee_rate_bps=200, fee_rate=0.02)
        result = compute_q_eff(0.90, fee)
        assert result.q_eff == pytest.approx(0.90 / 0.9982, abs=0.001)

    def test_slippage_estimation(self) -> None:
        fee = FeeInfo(fee_rate_bps=0, fee_rate=0)
        asks = [
            OrderBookLevel(price=0.50, size=100),
            OrderBookLevel(price=0.52, size=100),
        ]
        result = compute_q_eff(0.50, fee, order_size=150, ask_levels=asks)
        assert result.slippage_estimate == pytest.approx(0.5067 - 0.50, abs=0.001)
        assert result.q_eff > 0.50

    def test_qeff_clamped(self) -> None:
        fee = FeeInfo(fee_rate_bps=0, fee_rate=0)
        result = compute_q_eff(0.001, fee)
        assert result.q_eff >= 0.001
        result2 = compute_q_eff(0.999, fee)
        assert result2.q_eff <= 0.999


# ═══════════════════════════════════════════════════════════════════════════════
# Staking tests (updated for new defaults & confidence)
# ═══════════════════════════════════════════════════════════════════════════════

class TestStake:
    def test_basic_stake_quarter_kelly(self) -> None:
        # p=0.6, q=0.5 → kelly=0.2 → confidence=1 → f_adj=0.2
        # quarter-kelly → 5000*0.2*0.25=250 → max_bet=5000*0.05=250 → 250
        stake = compute_stake(0.60, 0.50, bankroll=5000, kelly_fraction=0.25, max_bet_pct=0.05, min_stake=1.0)
        assert stake == 250.0

    def test_no_edge_no_stake(self) -> None:
        assert compute_stake(0.50, 0.55) == 0.0

    def test_confidence_reduces_stake(self) -> None:
        # Full confidence
        full = compute_stake(0.60, 0.50, bankroll=5000, kelly_fraction=0.25, max_bet_pct=0.05, confidence=1.0, min_stake=1.0)
        # Half confidence → kelly reduced by 0.5²=0.25
        half = compute_stake(0.60, 0.50, bankroll=5000, kelly_fraction=0.25, max_bet_pct=0.05, confidence=0.5, min_stake=1.0)
        assert half < full

    def test_min_stake_filter(self) -> None:
        # Tiny edge → tiny stake → should be 0 if below min_stake
        stake = compute_stake(0.501, 0.50, bankroll=100, kelly_fraction=0.25, max_bet_pct=0.05, min_stake=1.0)
        assert stake == 0.0  # too small

    def test_liquidity_cap(self) -> None:
        # Large bankroll but low liquidity → capped at 10% of liquidity
        stake = compute_stake(
            0.70, 0.50, bankroll=100000, kelly_fraction=0.25,
            max_bet_pct=0.05, min_stake=1.0, available_liquidity=100,
        )
        assert stake <= 10.0  # 10% of 100


# ═══════════════════════════════════════════════════════════════════════════════
# Probability model tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestCombineProbabilities:
    def test_market_only(self) -> None:
        result = combine_probabilities(0.55)
        assert result == pytest.approx(0.55, abs=0.01)

    def test_two_sources(self) -> None:
        # Log-odds combining, close to linear for moderate probabilities
        result = combine_probabilities(0.50, p_books=0.60)
        assert 0.54 < result < 0.56

    def test_clamping_low(self) -> None:
        result = combine_probabilities(0.001)
        assert result >= 0.01

    def test_clamping_high(self) -> None:
        result = combine_probabilities(0.999)
        assert result <= 0.99


class TestConfidenceScore:
    def test_tight_spread_high_liq(self) -> None:
        score = compute_confidence_score(spread=0.01, bid_depth=500, ask_depth=500, num_sources=3)
        assert score > 0.7

    def test_wide_spread_low_liq(self) -> None:
        score = compute_confidence_score(spread=0.10, bid_depth=0, ask_depth=0, num_sources=1)
        assert score < 0.3

    def test_none_spread(self) -> None:
        score = compute_confidence_score(spread=None, bid_depth=100, ask_depth=100, num_sources=1)
        assert 0.1 < score < 0.7


class TestRemoveVig:
    def test_no_vig(self) -> None:
        result = remove_vig([0.50, 0.50])
        assert result == pytest.approx([0.50, 0.50])

    def test_with_vig(self) -> None:
        result = remove_vig([0.55, 0.52])
        assert sum(result) == pytest.approx(1.0)
        assert result[0] == pytest.approx(0.55 / 1.07, abs=0.001)


class TestImpliedProb:
    def test_decimal_odds(self) -> None:
        assert implied_prob_from_decimal_odds(2.0) == pytest.approx(0.50)
        assert implied_prob_from_decimal_odds(1.5) == pytest.approx(1 / 1.5)

    def test_odds_at_one(self) -> None:
        assert implied_prob_from_decimal_odds(1.0) == 1.0
