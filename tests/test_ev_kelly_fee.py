"""Tests for EV, Kelly, fee/pricing calculations – minimum 10 cases per spec."""

from __future__ import annotations

import pytest

from core.ev import compute_edge, compute_ev_per_dollar, compute_kelly_fraction, compute_roi_pct
from core.pricing import compute_q_eff
from core.staking import compute_stake
from core.models import combine_probabilities, remove_vig, implied_prob_from_decimal_odds
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
        # p=0.6, q_eff=0.50 → EV/$ = (0.6-0.5)/0.5 = 0.2
        assert compute_ev_per_dollar(0.60, 0.50) == pytest.approx(0.2)

    def test_zero_ev(self) -> None:
        assert compute_ev_per_dollar(0.50, 0.50) == pytest.approx(0.0)

    def test_negative_ev(self) -> None:
        # p=0.4, q_eff=0.5 → EV/$ = (0.4-0.5)/0.5 = -0.2
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
        # f* = (0.6 - 0.5) / (1 - 0.5) = 0.2
        assert compute_kelly_fraction(0.60, 0.50) == pytest.approx(0.2)

    def test_no_edge_kelly_zero(self) -> None:
        assert compute_kelly_fraction(0.50, 0.50) == 0.0

    def test_negative_edge_kelly_zero(self) -> None:
        assert compute_kelly_fraction(0.40, 0.55) == 0.0

    def test_high_edge_kelly(self) -> None:
        # f* = (0.9 - 0.2) / (1 - 0.2) = 0.7/0.8 = 0.875
        assert compute_kelly_fraction(0.90, 0.20) == pytest.approx(0.875)

    def test_qeff_near_one(self) -> None:
        assert compute_kelly_fraction(0.99, 1.0) == 0.0

    def test_tiny_edge(self) -> None:
        # f* = (0.51 - 0.50) / (1 - 0.50) = 0.01/0.50 = 0.02
        assert compute_kelly_fraction(0.51, 0.50) == pytest.approx(0.02)


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
        # r = 200bps = 0.02, q = 0.50
        # fee_adj = 0.02 * min(0.5, 0.5) * 0.5 = 0.005
        # q_eff = 0.5 / (1 - 0.005) = 0.5 / 0.995 ≈ 0.50251
        fee = FeeInfo(fee_rate_bps=200, fee_rate=0.02)
        result = compute_q_eff(0.50, fee)
        assert result.q_eff > 0.50
        assert result.q_eff == pytest.approx(0.50 / 0.995, abs=0.001)

    def test_high_price_with_fee(self) -> None:
        # q = 0.90, r = 0.02
        # fee_adj = 0.02 * min(0.9, 0.1) * 0.9 = 0.02 * 0.1 * 0.9 = 0.0018
        # q_eff = 0.9 / (1 - 0.0018) = 0.9 / 0.9982 ≈ 0.9016
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
        # VWAP: (100*0.50 + 50*0.52) / 150 = (50+26)/150 = 0.5067
        # Slippage: 0.5067 - 0.50 = 0.0067
        assert result.slippage_estimate == pytest.approx(0.5067 - 0.50, abs=0.001)
        assert result.q_eff > 0.50

    def test_qeff_clamped(self) -> None:
        fee = FeeInfo(fee_rate_bps=0, fee_rate=0)
        result = compute_q_eff(0.001, fee)
        assert result.q_eff >= 0.001
        result2 = compute_q_eff(0.999, fee)
        assert result2.q_eff <= 0.999


# ═══════════════════════════════════════════════════════════════════════════════
# Staking tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestStake:
    def test_basic_stake(self) -> None:
        # p=0.6, q=0.5 → kelly=0.2 → half_kelly → 5000*0.2*0.5=500
        # but max_bet = 5000*0.03 = 150 → capped at 150
        stake = compute_stake(0.60, 0.50, bankroll=5000, kelly_fraction=0.5, max_bet_pct=0.03)
        assert stake == 150.0

    def test_no_edge_no_stake(self) -> None:
        assert compute_stake(0.50, 0.55) == 0.0

    def test_small_edge_under_cap(self) -> None:
        # p=0.52, q=0.50 → kelly=0.04 → half_kelly → 5000*0.04*0.5=100
        # max_bet=150 → not capped → 100
        stake = compute_stake(0.52, 0.50, bankroll=5000, kelly_fraction=0.5, max_bet_pct=0.03)
        assert stake == 100.0

    def test_custom_bankroll(self) -> None:
        stake = compute_stake(0.60, 0.50, bankroll=10000, kelly_fraction=0.5, max_bet_pct=0.03)
        # kelly=0.2 → 10000*0.2*0.5=1000 → cap=300 → 300
        assert stake == 300.0


# ═══════════════════════════════════════════════════════════════════════════════
# Probability model tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestCombineProbabilities:
    def test_market_only(self) -> None:
        # Only p_mkt provided → result should be p_mkt (clamped)
        result = combine_probabilities(0.55)
        assert result == pytest.approx(0.55)

    def test_two_sources(self) -> None:
        # p_mkt=0.50 w=0.4, p_books=0.60 w=0.4 → renorm total=0.8
        # p = (0.50*0.4/0.8) + (0.60*0.4/0.8) = 0.25+0.30 = 0.55
        result = combine_probabilities(0.50, p_books=0.60)
        assert result == pytest.approx(0.55)

    def test_clamping_low(self) -> None:
        result = combine_probabilities(0.001)
        assert result >= 0.01

    def test_clamping_high(self) -> None:
        result = combine_probabilities(0.999)
        assert result <= 0.99


class TestRemoveVig:
    def test_no_vig(self) -> None:
        result = remove_vig([0.50, 0.50])
        assert result == pytest.approx([0.50, 0.50])

    def test_with_vig(self) -> None:
        # 0.55 + 0.52 = 1.07
        result = remove_vig([0.55, 0.52])
        assert sum(result) == pytest.approx(1.0)
        assert result[0] == pytest.approx(0.55 / 1.07, abs=0.001)


class TestImpliedProb:
    def test_decimal_odds(self) -> None:
        assert implied_prob_from_decimal_odds(2.0) == pytest.approx(0.50)
        assert implied_prob_from_decimal_odds(1.5) == pytest.approx(1 / 1.5)

    def test_odds_at_one(self) -> None:
        assert implied_prob_from_decimal_odds(1.0) == 1.0
