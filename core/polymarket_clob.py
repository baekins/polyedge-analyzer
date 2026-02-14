"""Client for Polymarket CLOB API – prices, orderbook, fee-rate, WebSocket."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable

import httpx

from core.schemas import FeeInfo, OrderBookLevel, OrderBookSnapshot, PriceInfo

logger = logging.getLogger(__name__)

CLOB_BASE = "https://clob.polymarket.com"
WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/"
DEFAULT_TIMEOUT = 15.0
MAX_RETRIES = 3


class CLOBClient:
    """REST client for the CLOB API (no auth – read-only market data)."""

    def __init__(self, timeout: float = DEFAULT_TIMEOUT) -> None:
        self._timeout = timeout

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = f"{CLOB_BASE}{path}"
        last_exc: Exception | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                with httpx.Client(timeout=self._timeout) as client:
                    resp = client.get(url, params=params)
                    resp.raise_for_status()
                    return resp.json()
            except (httpx.HTTPStatusError, httpx.RequestError) as exc:
                last_exc = exc
                logger.warning("CLOB GET %s attempt %d failed: %s", path, attempt, exc)
        raise RuntimeError(f"CLOB API failed after {MAX_RETRIES} retries: {last_exc}")

    # ── orderbook ─────────────────────────────────────────────────────────

    def get_orderbook(self, token_id: str) -> OrderBookSnapshot:
        """GET /book?token_id=..."""
        data = self._get("/book", params={"token_id": token_id})
        bids = [OrderBookLevel(price=float(b["price"]), size=float(b["size"])) for b in data.get("bids", [])]
        asks = [OrderBookLevel(price=float(a["price"]), size=float(a["size"])) for a in data.get("asks", [])]
        return OrderBookSnapshot(bids=bids, asks=asks)

    def get_price_info(self, token_id: str) -> PriceInfo:
        """Derive best bid/ask/mid/spread/depth from orderbook."""
        ob = self.get_orderbook(token_id)
        best_bid = ob.bids[0].price if ob.bids else None
        best_ask = ob.asks[0].price if ob.asks else None
        mid = None
        spread = None
        if best_bid is not None and best_ask is not None:
            mid = (best_bid + best_ask) / 2
            spread = best_ask - best_bid
        bid_depth = sum(b.size for b in ob.bids)
        ask_depth = sum(a.size for a in ob.asks)
        return PriceInfo(
            best_bid=best_bid,
            best_ask=best_ask,
            mid=mid,
            spread=spread,
            bid_depth=bid_depth,
            ask_depth=ask_depth,
        )

    # ── fee rate ──────────────────────────────────────────────────────────

    def get_fee_rate(self, token_id: str) -> FeeInfo:
        """GET /fee-rate?token_id=... — returns fee in basis points."""
        try:
            data = self._get("/fee-rate", params={"token_id": token_id})
            bps = float(data.get("fee_rate_bps", data.get("feeRateBps", 0)) or 0)
            return FeeInfo(fee_rate_bps=bps, fee_rate=bps / 10000)
        except Exception as exc:
            logger.warning("Fee-rate lookup failed for %s: %s – defaulting to 0", token_id, exc)
            return FeeInfo()

    # ── midpoint shortcut ─────────────────────────────────────────────────

    def get_midpoint(self, token_id: str) -> float | None:
        """GET /midpoint?token_id=..."""
        try:
            data = self._get("/midpoint", params={"token_id": token_id})
            return float(data.get("mid", 0))
        except Exception:
            return None


class CLOBWebSocket:
    """Async WebSocket listener for real-time price updates."""

    def __init__(self, on_message: Callable[[dict[str, Any]], None] | None = None) -> None:
        self._on_message = on_message
        self._ws: Any = None
        self._running = False

    async def connect(self, token_ids: list[str]) -> None:
        """Subscribe to price channels for given tokens."""
        try:
            import websockets  # type: ignore[import-untyped]
        except ImportError:
            logger.error("websockets package not installed")
            return

        self._running = True
        while self._running:
            try:
                async with websockets.connect(WS_URL) as ws:
                    self._ws = ws
                    # Subscribe to each token's market channel
                    for tid in token_ids:
                        sub_msg = json.dumps({
                            "type": "subscribe",
                            "channel": "market",
                            "assets_id": tid,
                        })
                        await ws.send(sub_msg)
                    logger.info("WS subscribed to %d tokens", len(token_ids))

                    async for raw in ws:
                        if not self._running:
                            break
                        try:
                            data = json.loads(raw)
                            if self._on_message:
                                self._on_message(data)
                        except json.JSONDecodeError:
                            pass
            except Exception as exc:
                if self._running:
                    logger.warning("WS connection lost: %s – reconnecting in 5s", exc)
                    await asyncio.sleep(5)

    async def disconnect(self) -> None:
        self._running = False
        if self._ws:
            await self._ws.close()
