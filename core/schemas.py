"""Pydantic data models for the entire pipeline."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ── Polymarket raw data ──────────────────────────────────────────────────────

class OutcomeSide(str, Enum):
    YES = "YES"
    NO = "NO"


class OrderBookLevel(BaseModel):
    price: float
    size: float


class OrderBookSnapshot(BaseModel):
    bids: list[OrderBookLevel] = Field(default_factory=list)
    asks: list[OrderBookLevel] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class TokenInfo(BaseModel):
    token_id: str
    outcome: str  # "Yes", "No", or custom outcome label
    winner: Optional[bool] = None


class MarketData(BaseModel):
    """A single binary or multi-outcome market from Gamma."""
    condition_id: str
    question: str
    slug: str
    tokens: list[TokenInfo]
    category: str = ""
    end_date: Optional[datetime] = None
    active: bool = True
    volume: float = 0.0
    liquidity: float = 0.0
    event_slug: str = ""
    event_title: str = ""


# ── Pricing / analysis ───────────────────────────────────────────────────────

class PriceInfo(BaseModel):
    best_bid: Optional[float] = None
    best_ask: Optional[float] = None
    mid: Optional[float] = None
    spread: Optional[float] = None
    bid_depth: float = 0.0
    ask_depth: float = 0.0


class FeeInfo(BaseModel):
    fee_rate_bps: float = 0.0  # basis points
    fee_rate: float = 0.0      # decimal (bps / 10000)


class EffectivePrice(BaseModel):
    q_raw: float               # best ask (raw buy price)
    q_eff: float               # effective price after fees
    fee_component: float = 0.0
    slippage_estimate: float = 0.0


class EVResult(BaseModel):
    p_hat: float
    q_eff: float
    edge: float
    ev_per_dollar: float
    roi_pct: float
    kelly_fraction: float      # raw f*
    recommended_stake: float   # after half-kelly & caps


class AnalysisRow(BaseModel):
    """One row in the main analysis table."""
    market_question: str
    event_title: str
    outcome: str
    token_id: str
    slug: str
    best_bid: Optional[float] = None
    best_ask: Optional[float] = None
    mid: Optional[float] = None
    spread: Optional[float] = None
    bid_depth: float = 0.0
    ask_depth: float = 0.0
    fee_rate_bps: float = 0.0
    p_hat: float = 0.0
    q_eff: float = 0.0
    edge: float = 0.0
    ev_per_dollar: float = 0.0
    roi_pct: float = 0.0
    kelly_raw: float = 0.0
    stake: float = 0.0
    confidence: str = "market-implied"
    claude_flags: str = ""
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ── Claude AI ─────────────────────────────────────────────────────────────────

class ClaudeRiskFlag(BaseModel):
    flag: str
    severity: str = "info"  # info / warning / critical
    detail: str = ""


class ClaudeAnalysis(BaseModel):
    summary: str = ""
    key_factors: list[str] = Field(default_factory=list)
    risk_flags: list[ClaudeRiskFlag] = Field(default_factory=list)
    suggested_p_adj: Optional[float] = None  # optional micro-adjustment
    confidence_note: str = ""
    cached: bool = False


# ── Settings ──────────────────────────────────────────────────────────────────

class AppSettings(BaseModel):
    bankroll: float = 5000.0
    kelly_fraction: float = 0.5
    max_bet_pct: float = 0.03
    min_edge: float = 0.0
    min_liquidity: float = 0.0
    claude_enabled: bool = False
    anthropic_api_key: str = ""
    refresh_interval_sec: int = 30
    ws_enabled: bool = False
    # probability model weights
    w_mkt: float = 0.4
    w_books: float = 0.4
    w_model: float = 0.15
    w_claude: float = 0.05
