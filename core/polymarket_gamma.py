"""Client for Polymarket Gamma API – market/event discovery."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from core.schemas import MarketData, TokenInfo

logger = logging.getLogger(__name__)

GAMMA_BASE = "https://gamma-api.polymarket.com"
DEFAULT_TIMEOUT = 15.0
MAX_RETRIES = 3


class GammaClient:
    """Fetches market & event metadata from the Gamma API (no auth required)."""

    def __init__(self, timeout: float = DEFAULT_TIMEOUT) -> None:
        self._timeout = timeout

    # ── helpers ───────────────────────────────────────────────────────────

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """HTTP GET with retries."""
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
        raise RuntimeError(f"Gamma API failed after {MAX_RETRIES} retries: {last_exc}")

    # ── public ────────────────────────────────────────────────────────────

    def fetch_sports_markets(
        self,
        limit: int = 100,
        offset: int = 0,
        active_only: bool = True,
        tag: str = "sports",
    ) -> list[MarketData]:
        """Return sports-tagged markets with token info."""
        params: dict[str, Any] = {
            "limit": limit,
            "offset": offset,
            "tag": tag,
            "active": str(active_only).lower(),
            "order": "volume",
            "ascending": "false",
        }
        raw_markets: list[dict[str, Any]] = self._get("/markets", params)
        results: list[MarketData] = []
        for m in raw_markets:
            tokens = self._extract_tokens(m)
            if not tokens:
                continue
            results.append(
                MarketData(
                    condition_id=m.get("conditionId", m.get("condition_id", "")),
                    question=m.get("question", ""),
                    slug=m.get("slug", ""),
                    tokens=tokens,
                    category=m.get("category", m.get("tag", "")),
                    end_date=m.get("endDate") or m.get("end_date"),
                    active=m.get("active", True),
                    volume=float(m.get("volume", 0) or 0),
                    liquidity=float(m.get("liquidity", 0) or 0),
                    event_slug=m.get("eventSlug", m.get("event_slug", "")),
                    event_title=m.get("eventTitle", m.get("event_title", m.get("question", ""))),
                )
            )
        logger.info("Fetched %d sports markets from Gamma (offset=%d)", len(results), offset)
        return results

    def fetch_all_sports_markets(self, max_pages: int = 5, page_size: int = 100) -> list[MarketData]:
        """Paginate through sports markets."""
        all_markets: list[MarketData] = []
        for page in range(max_pages):
            batch = self.fetch_sports_markets(limit=page_size, offset=page * page_size)
            all_markets.extend(batch)
            if len(batch) < page_size:
                break
        return all_markets

    # ── token extraction ──────────────────────────────────────────────────

    @staticmethod
    def _extract_tokens(m: dict[str, Any]) -> list[TokenInfo]:
        tokens: list[TokenInfo] = []
        # Gamma v2 format: clobTokenIds as JSON string or list
        clob_ids = m.get("clobTokenIds")
        outcomes = m.get("outcomes")
        if isinstance(clob_ids, str):
            import json
            try:
                clob_ids = json.loads(clob_ids)
            except (json.JSONDecodeError, TypeError):
                clob_ids = []
        if isinstance(outcomes, str):
            import json
            try:
                outcomes = json.loads(outcomes)
            except (json.JSONDecodeError, TypeError):
                outcomes = []

        if clob_ids and outcomes:
            for tid, label in zip(clob_ids, outcomes):
                tokens.append(TokenInfo(token_id=str(tid), outcome=str(label)))
        return tokens
