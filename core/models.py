"""확률 추정: 마켓, 스포츠북, 통계모델, Claude AI 시그널 결합.

개선사항:
- 로그오즈 결합 (선형 평균보다 더 정확한 확률 결합)
- 신뢰도 점수 산출
- 스프레드 기반 불확실성 보정
"""

from __future__ import annotations

import math
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def clamp(value: float, lo: float = 0.01, hi: float = 0.99) -> float:
    return max(lo, min(hi, value))


def _to_log_odds(p: float) -> float:
    """확률을 로그오즈로 변환."""
    p = clamp(p)
    return math.log(p / (1 - p))


def _from_log_odds(lo: float) -> float:
    """로그오즈를 확률로 역변환."""
    return 1.0 / (1.0 + math.exp(-lo))


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
    로그오즈 기반 가중 확률 결합.

    선형 평균 대신 로그오즈 공간에서 결합하면
    극단적 확률값이 더 적절하게 처리됨.

    missing 소스는 가중치를 재분배.

    Returns p̂ clamped to [0.01, 0.99].
    """
    sources: list[tuple[float, float]] = []
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

    # 로그오즈 가중평균
    lo_weighted = sum(_to_log_odds(p) * (w / total_w) for p, w in sources)
    p_hat = _from_log_odds(lo_weighted)
    return clamp(p_hat)


def compute_confidence_score(
    spread: Optional[float],
    bid_depth: float,
    ask_depth: float,
    num_sources: int = 1,
) -> float:
    """
    데이터 품질 기반 신뢰도 점수 (0~1).

    요소:
    - 스프레드가 좁을수록 신뢰도 높음 (max 0.4)
    - 유동성이 높을수록 신뢰도 높음 (max 0.3)
    - 소스 수가 많을수록 신뢰도 높음 (max 0.3)
    """
    score = 0.0

    # 스프레드 요소 (0.4점 만점)
    if spread is not None and spread >= 0:
        # 스프레드 0이면 0.4점, 0.10 이상이면 0점
        spread_score = max(0, 1 - spread / 0.10) * 0.4
        score += spread_score
    else:
        score += 0.2  # 스프레드 정보 없으면 중간값

    # 유동성 요소 (0.3점 만점)
    total_liq = bid_depth + ask_depth
    # $1000 이상이면 만점
    liq_score = min(total_liq / 1000, 1.0) * 0.3
    score += liq_score

    # 소스 수 요소 (0.3점 만점)
    # 1소스=0.1, 2소스=0.2, 3+소스=0.3
    src_score = min(num_sources / 3, 1.0) * 0.3
    score += src_score

    return clamp(score, 0.0, 1.0)


def remove_vig(odds_list: list[float]) -> list[float]:
    """
    북메이커 비그 제거.
    예: 0.55 + 0.52 = 1.07 → 합이 1이 되도록 정규화.
    """
    total = sum(odds_list)
    if total <= 0:
        return odds_list
    return [p / total for p in odds_list]


def implied_prob_from_decimal_odds(decimal_odds: float) -> float:
    """소수점 배당률(예: 1.80)을 내재확률로 변환."""
    if decimal_odds <= 1.0:
        return 1.0
    return 1.0 / decimal_odds
