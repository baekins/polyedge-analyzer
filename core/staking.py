"""켈리 기반 스테이크 사이징 (안전 캡 적용).

개선사항:
- 신뢰도 가중 켈리
- 최소 베팅 임계값
- 유동성 기반 캡 (유동성 부족 시 베팅 축소)
"""

from __future__ import annotations

import logging

from core.ev import compute_kelly_fraction, compute_kelly_with_confidence

logger = logging.getLogger(__name__)


def compute_stake(
    p_hat: float,
    q_eff: float,
    bankroll: float = 5000.0,
    kelly_fraction: float = 0.25,
    max_bet_pct: float = 0.05,
    min_stake: float = 1.0,
    confidence: float = 1.0,
    available_liquidity: float = 0.0,
) -> float:
    """
    추천 베팅 금액 (USDT).

    1. 켈리 최적 비율 계산
    2. 신뢰도 조정 (confidence가 낮으면 비율 축소)
    3. kelly_fraction 적용 (보수적 배율, 기본 0.25 = quarter-Kelly)
    4. max_bet_pct 캡 적용
    5. 유동성 캡: 총 유동성의 10% 이하
    6. 최소 베팅 임계값 이하면 0 반환

    Parameters
    ----------
    p_hat : 추정 실제 확률
    q_eff : 수수료/슬리피지 반영 유효 매수가
    bankroll : 총 자금 (USDT)
    kelly_fraction : 풀 켈리 대비 비율 (0.25 = quarter-Kelly)
    max_bet_pct : 자금 대비 최대 베팅 비율
    min_stake : 최소 베팅 금액 ($)
    confidence : p̂ 추정 신뢰도 (0~1)
    available_liquidity : 마켓 유동성 (0이면 제한 없음)
    """
    # 신뢰도 가중 켈리
    f_star = compute_kelly_with_confidence(p_hat, q_eff, confidence)

    # Kelly fraction 적용
    stake = bankroll * f_star * kelly_fraction

    # 자금 대비 최대 캡
    cap = bankroll * max_bet_pct
    stake = min(stake, cap)

    # 유동성 캡: 총 유동성의 10% 초과 금지
    if available_liquidity > 0:
        liq_cap = available_liquidity * 0.10
        stake = min(stake, liq_cap)

    # 최소 베팅 이하면 0 반환 (의미 없는 소액 방지)
    if stake < min_stake:
        return 0.0

    return round(max(stake, 0.0), 2)
