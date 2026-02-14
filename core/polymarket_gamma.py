"""Client for Polymarket Gamma API – market/event discovery with embedded prices."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from core.schemas import MarketData, PriceInfo, FeeInfo, TokenInfo

logger = logging.getLogger(__name__)

GAMMA_BASE = "https://gamma-api.polymarket.com"
DEFAULT_TIMEOUT = 20.0
MAX_RETRIES = 3

# Polymarket default taker fee: ~2% (200 bps)
DEFAULT_FEE_BPS = 200.0


class GammaClient:
    """Fetches events & markets from the Gamma API with embedded price data."""

    def __init__(self, timeout: float = DEFAULT_TIMEOUT) -> None:
        self._timeout = timeout

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = f"{GAMMA_BASE}{path}"
        last_exc: Exception | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                with httpx.Client(timeout=self._timeout) as client:
                    resp = client.get(url, params=params)
                    resp.raise_for_status()
                    return resp.json()
            except (httpx.HTTPStatusError, httpx.RequestError) as exc:
                last_exc = exc
                logger.warning("Gamma GET %s attempt %d failed: %s", path, attempt, exc)
        raise RuntimeError(f"Gamma API {MAX_RETRIES}회 재시도 후 실패: {last_exc}")

    # ── Events API (better: includes markets with prices) ─────────────────

    def fetch_events(
        self,
        limit: int = 20,
        offset: int = 0,
        closed: bool = False,
        order: str = "liquidityClob",
        tag: str | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch events with embedded market data."""
        params: dict[str, Any] = {
            "limit": limit,
            "offset": offset,
            "closed": str(closed).lower(),
            "order": order,
            "ascending": "false",
        }
        if tag:
            params["tag"] = tag
        return self._get("/events", params)

    def fetch_all_active_markets(
        self,
        max_pages: int = 3,
        page_size: int = 20,
        tag: str | None = None,
    ) -> list[MarketData]:
        """
        Fetch active markets via events API.

        Uses the /events endpoint which provides:
        - Market metadata (question, slug, etc.)
        - Embedded price data (bestBid, bestAsk, outcomePrices, spread)
        - No need for separate CLOB API calls!

        Filters out: closed markets, non-accepting orders, resolved outcomes.
        """
        all_markets: list[MarketData] = []

        for page in range(max_pages):
            try:
                events = self.fetch_events(
                    limit=page_size,
                    offset=page * page_size,
                    closed=False,
                    tag=tag,
                )
            except Exception as exc:
                logger.error("이벤트 조회 실패 (page %d): %s", page, exc)
                break

            if not events:
                break

            for event in events:
                event_title = event.get("title", "")
                event_slug = event.get("slug", "")

                for m in event.get("markets", []):
                    # Skip closed or non-accepting markets
                    if m.get("closed", False):
                        continue
                    if not m.get("acceptingOrders", True):
                        continue

                    # Extract tokens
                    tokens = self._extract_tokens(m)
                    if not tokens:
                        continue

                    # Extract prices from Gamma response
                    best_bid = m.get("bestBid")
                    best_ask = m.get("bestAsk")
                    spread = m.get("spread")
                    outcome_prices = self._parse_outcome_prices(m.get("outcomePrices", "[]"))

                    # Skip if no price data
                    if best_bid is None and best_ask is None and not outcome_prices:
                        continue

                    # Skip resolved markets (any outcome = 1.0 or 0.0 exactly)
                    if outcome_prices and (1.0 in outcome_prices or all(p < 0.001 for p in outcome_prices)):
                        continue

                    all_markets.append(
                        MarketData(
                            condition_id=m.get("conditionId", m.get("condition_id", "")),
                            question=m.get("question", ""),
                            slug=m.get("slug", ""),
                            tokens=tokens,
                            category=m.get("category", event.get("category", "")),
                            end_date=m.get("endDate") or m.get("end_date"),
                            active=True,
                            volume=float(m.get("volumeClob", m.get("volume", 0)) or 0),
                            liquidity=float(m.get("liquidityClob", m.get("liquidity", 0)) or 0),
                            event_slug=event_slug or m.get("eventSlug", ""),
                            event_title=event_title or m.get("question", ""),
                            # Store embedded price data
                            best_bid=float(best_bid) if best_bid is not None else None,
                            best_ask=float(best_ask) if best_ask is not None else None,
                            spread=float(spread) if spread is not None else None,
                            outcome_prices=outcome_prices,
                        )
                    )

            if len(events) < page_size:
                break

        logger.info("총 %d개 활성 마켓 조회 완료", len(all_markets))
        return all_markets

    # ── Legacy: markets API (kept for compatibility) ──────────────────────

    def fetch_sports_markets(
        self,
        limit: int = 100,
        offset: int = 0,
        active_only: bool = True,
        tag: str = "sports",
    ) -> list[MarketData]:
        """Legacy: Return sports-tagged markets from /markets endpoint."""
        return self.fetch_all_active_markets(max_pages=1, page_size=limit, tag=tag)

    def fetch_all_sports_markets(self, max_pages: int = 5, page_size: int = 100) -> list[MarketData]:
        """Legacy: Paginate through sports markets."""
        return self.fetch_all_active_markets(max_pages=max_pages, page_size=min(page_size, 50))

    # ── helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _extract_tokens(m: dict[str, Any]) -> list[TokenInfo]:
        tokens: list[TokenInfo] = []
        clob_ids = m.get("clobTokenIds")
        outcomes = m.get("outcomes")
        if isinstance(clob_ids, str):
            try:
                clob_ids = json.loads(clob_ids)
            except (json.JSONDecodeError, TypeError):
                clob_ids = []
        if isinstance(outcomes, str):
            try:
                outcomes = json.loads(outcomes)
            except (json.JSONDecodeError, TypeError):
                outcomes = []

        if clob_ids and outcomes:
            for tid, label in zip(clob_ids, outcomes):
                tokens.append(TokenInfo(token_id=str(tid), outcome=str(label)))
        return tokens

    @staticmethod
    def _parse_outcome_prices(raw: str | list | None) -> list[float]:
        if raw is None:
            return []
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                return []
        if isinstance(raw, list):
            try:
                return [float(p) for p in raw]
            except (ValueError, TypeError):
                return []
        return []
