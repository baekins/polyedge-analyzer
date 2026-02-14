"""엣지, 기대값(EV), ROI, 켈리 비율 계산 모듈.

개선사항:
- 리스크 조정 엣지 (변동성 대비 엣지)
- 성장률 기반 켈리 (로그 효용)
- 신뢰도 가중 켈리
- 시그널 분류
"""

from __future__ import annotations

import math
import logging

logger = logging.getLogger(__name__)


def compute_edge(p_hat: float, q_eff: float) -> float:
    """엣지 = p̂ − q_eff (양수면 기대이익)."""
    return p_hat - q_eff


def compute_ev_per_dollar(p_hat: float, q_eff: float) -> float:
    """
    $1 투자 시 기대값.

    승리 시 수익 = (1 − q_eff) / q_eff
    패배 시 손실 = -1

    EV/$ = p̂ * (1 - q_eff) / q_eff - (1 - p̂)
         = (p̂ - q_eff) / q_eff
    """
    if q_eff <= 0:
        return 0.0
    return (p_hat - q_eff) / q_eff


def compute_roi_pct(p_hat: float, q_eff: float) -> float:
    """ROI % = EV/$ × 100."""
    return compute_ev_per_dollar(p_hat, q_eff) * 100


def compute_kelly_fraction(p_hat: float, q_eff: float) -> float:
    """
    켈리 기준 최적 비율 (바이너리 베팅).

    f* = (p̂ − q_eff) / (1 − q_eff)

    엣지가 0 이하이면 0 반환.
    """
    if p_hat <= q_eff or q_eff >= 1.0:
        return 0.0
    return (p_hat - q_eff) / (1 - q_eff)


def compute_kelly_with_confidence(
    p_hat: float,
    q_eff: float,
    confidence: float = 1.0,
) -> float:
    """
    신뢰도 가중 켈리.

    p̂의 추정 신뢰도가 낮을수록 켈리를 줄임.
    confidence = 0~1 (1이면 완전 신뢰)

    f_adj = f* × confidence²
    (제곱을 사용해 불확실할 때 더 보수적으로)
    """
    f_star = compute_kelly_fraction(p_hat, q_eff)
    return f_star * (confidence ** 2)


def compute_risk_adjusted_edge(p_hat: float, q_eff: float) -> float:
    """
    리스크 조정 엣지 (Sharpe-like ratio).

    edge / σ, where σ = sqrt(p̂ × (1 − p̂))

    변동성이 높은 이벤트(p≈0.5)는 같은 엣지라도 낮은 점수.
    극단적 확률(p≈0 or 1) 이벤트는 엣지 가치가 높음.
    """
    edge = compute_edge(p_hat, q_eff)
    variance = p_hat * (1 - p_hat)
    if variance <= 0:
        return 0.0
    return edge / math.sqrt(variance)


def compute_expected_growth(p_hat: float, q_eff: float) -> float:
    """
    켈리 성장률 (로그 효용).

    G = p̂ × log(1/q_eff) + (1−p̂) × log(1/(1−q_eff))
      = −p̂ × log(q_eff) − (1−p̂) × log(1−q_eff)

    양수면 장기적으로 자산 성장, 음수면 파산.
    """
    if q_eff <= 0 or q_eff >= 1:
        return 0.0
    try:
        g = -p_hat * math.log(q_eff) - (1 - p_hat) * math.log(1 - q_eff)
        # Subtract entropy of p_hat to get net growth
        h = -p_hat * math.log(p_hat) - (1 - p_hat) * math.log(1 - p_hat) if 0 < p_hat < 1 else 0
        return g - h
    except (ValueError, ZeroDivisionError):
        return 0.0


def classify_signal(
    edge: float,
    roi_pct: float,
    confidence_score: float,
    bid_depth: float,
    ask_depth: float,
) -> str:
    """
    종합 시그널 분류.

    강력매수: edge > 3%, ROI > 5%, 충분한 유동성
    매수: edge > 1%, ROI > 2%
    보류: edge > 0% 이지만 약함
    패스: edge ≤ 0%
    """
    total_depth = bid_depth + ask_depth

    if edge <= 0:
        return "패스"
    if edge > 0.03 and roi_pct > 5 and total_depth > 100 and confidence_score > 0.5:
        return "강력매수"
    if edge > 0.01 and roi_pct > 2:
        return "매수"
    return "보류"
