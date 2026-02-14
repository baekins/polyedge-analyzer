"""Anthropic Claude API wrapper with caching and throttling."""

from __future__ import annotations

import json
import logging
import time
from typing import Optional

from cachetools import TTLCache

from core.schemas import ClaudeAnalysis, ClaudeRiskFlag

logger = logging.getLogger(__name__)

# Cache analysis results for 5 minutes to avoid redundant API calls
_analysis_cache: TTLCache[str, ClaudeAnalysis] = TTLCache(maxsize=256, ttl=300)

# Rate limiting: minimum seconds between calls
_MIN_INTERVAL = 2.0
_last_call_time: float = 0.0

SYSTEM_PROMPT = """You are a sports betting analyst assistant. Your role is to provide structured risk analysis for prediction market positions. You must:

1. NEVER guarantee outcomes or predict winners with certainty
2. ALWAYS highlight uncertainty and data limitations
3. Focus on identifying risk factors, key variables, and information gaps
4. Return structured JSON only

Respond ONLY with valid JSON in this exact schema:
{
  "summary": "Brief 1-2 sentence overview of the event context",
  "key_factors": ["factor1", "factor2", ...],
  "risk_flags": [
    {"flag": "name", "severity": "info|warning|critical", "detail": "explanation"}
  ],
  "suggested_p_adj": null or float between -0.05 and 0.05,
  "confidence_note": "How confident the analysis is and why"
}"""


def analyze_market(
    api_key: str,
    market_question: str,
    current_price: float,
    additional_context: str = "",
) -> ClaudeAnalysis:
    """
    Call Claude to produce a risk/context analysis for a market.

    Returns cached result if available. Throttles to respect rate limits.
    """
    global _last_call_time

    # Check cache
    cache_key = f"{market_question}:{current_price:.3f}"
    if cache_key in _analysis_cache:
        cached = _analysis_cache[cache_key]
        cached.cached = True
        return cached

    # Throttle
    elapsed = time.time() - _last_call_time
    if elapsed < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - elapsed)

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)

        user_msg = f"""Analyze this prediction market position:

Market: {market_question}
Current market price (implied probability): {current_price:.1%}
{f"Additional context: {additional_context}" if additional_context else ""}

Provide risk analysis as JSON."""

        response = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )

        _last_call_time = time.time()

        # Parse response
        text = response.content[0].text.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        data = json.loads(text)
        analysis = ClaudeAnalysis(
            summary=data.get("summary", ""),
            key_factors=data.get("key_factors", []),
            risk_flags=[
                ClaudeRiskFlag(**rf) for rf in data.get("risk_flags", [])
            ],
            suggested_p_adj=data.get("suggested_p_adj"),
            confidence_note=data.get("confidence_note", ""),
            cached=False,
        )
        _analysis_cache[cache_key] = analysis
        return analysis

    except ImportError:
        logger.error("anthropic package not installed")
        return ClaudeAnalysis(summary="Error: anthropic SDK not installed")
    except json.JSONDecodeError as exc:
        logger.warning("Claude returned non-JSON: %s", exc)
        return ClaudeAnalysis(summary="Error: could not parse Claude response")
    except Exception as exc:
        logger.error("Claude API call failed: %s", exc)
        return ClaudeAnalysis(summary=f"Error: {exc}")


def clear_cache() -> None:
    _analysis_cache.clear()
