"""Application settings with pydantic-settings, persisted to JSON."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from core.schemas import AppSettings

logger = logging.getLogger(__name__)


def _config_dir() -> Path:
    """Return platform config directory."""
    import os
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".config"))
    d = base / "PolyEdgeAnalyzer"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _config_path() -> Path:
    return _config_dir() / "settings.json"


def load_settings() -> AppSettings:
    """Load settings from JSON file, or return defaults."""
    p = _config_path()
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            return AppSettings(**data)
        except Exception as exc:
            logger.warning("Failed to load settings: %s – using defaults", exc)
    return AppSettings()


def save_settings(settings: AppSettings) -> None:
    """Persist settings to JSON."""
    p = _config_path()
    p.write_text(settings.model_dump_json(indent=2), encoding="utf-8")
    logger.info("Settings saved to %s", p)


def has_accepted_disclaimer() -> bool:
    """Check if user previously accepted the risk disclaimer."""
    flag = _config_dir() / ".disclaimer_accepted"
    return flag.exists()


def set_disclaimer_accepted() -> None:
    flag = _config_dir() / ".disclaimer_accepted"
    flag.write_text("accepted", encoding="utf-8")
