"""External odds provider plugin interface + CSV sample provider."""

from __future__ import annotations

import csv
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from core.models import implied_prob_from_decimal_odds, remove_vig

logger = logging.getLogger(__name__)


class OddsProvider(ABC):
    """Base class for external odds sources."""

    @abstractmethod
    def get_probabilities(self, event_key: str) -> Optional[dict[str, float]]:
        """
        Return outcome → fair probability (vig-removed) for an event.

        event_key can be a slug, condition_id, or custom identifier.
        Returns None if event not found.
        """
        ...


class CSVOddsProvider(OddsProvider):
    """
    Reads odds from a CSV file with columns:
      event_key, outcome, decimal_odds

    Example CSV:
      nba-lakers-celtics-2026,Yes,1.85
      nba-lakers-celtics-2026,No,2.05
    """

    def __init__(self, csv_path: str | Path) -> None:
        self._path = Path(csv_path)
        self._data: dict[str, dict[str, float]] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            logger.warning("Odds CSV not found: %s", self._path)
            return
        with open(self._path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            raw: dict[str, list[tuple[str, float]]] = {}
            for row in reader:
                key = row.get("event_key", "").strip()
                outcome = row.get("outcome", "").strip()
                odds = float(row.get("decimal_odds", 0))
                if key and outcome and odds > 1.0:
                    raw.setdefault(key, []).append((outcome, odds))

        # Remove vig per event
        for key, entries in raw.items():
            impl_probs = [implied_prob_from_decimal_odds(o) for _, o in entries]
            fair = remove_vig(impl_probs)
            self._data[key] = {
                outcome: prob for (outcome, _), prob in zip(entries, fair)
            }
        logger.info("Loaded odds for %d events from CSV", len(self._data))

    def get_probabilities(self, event_key: str) -> Optional[dict[str, float]]:
        return self._data.get(event_key)


class PlaceholderStatModel(OddsProvider):
    """Placeholder for Elo/Poisson/ML model. Always returns None (not implemented)."""

    def get_probabilities(self, event_key: str) -> Optional[dict[str, float]]:
        return None
