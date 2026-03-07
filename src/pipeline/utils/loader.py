"""Data file loaders. All data access MUST go through these functions."""

import json
from datetime import UTC, datetime
from pathlib import Path

import yaml

from pipeline.schemas.ai_cost_schema import AICost
from pipeline.schemas.config_schema import AppConfig
from pipeline.schemas.keywords_schema import KeywordsConfig
from pipeline.schemas.seen_schema import SeenStore


def load_config(path: str | Path = "data/config.yaml") -> AppConfig:
    """Load and validate application config from YAML."""
    with open(path) as f:
        raw = yaml.safe_load(f)
    return AppConfig.model_validate(raw or {})


def load_keywords(path: str | Path = "data/keywords.yaml") -> KeywordsConfig:
    """Load and validate keyword library from YAML."""
    with open(path) as f:
        raw = yaml.safe_load(f)
    return KeywordsConfig.model_validate(raw or {})


def load_seen(path: str | Path = "data/seen.json") -> SeenStore:
    """Load and validate seen article store from JSON.

    Returns empty store if file doesn't exist or is empty.
    """
    path = Path(path)
    if not path.exists():
        return SeenStore()
    text = path.read_text().strip()
    if not text:
        return SeenStore()
    raw = json.loads(text)
    return SeenStore.model_validate(raw)


def save_seen(store: SeenStore, path: str | Path = "data/seen.json") -> None:
    """Save SeenStore to JSON file."""
    path = Path(path)
    path.write_text(store.model_dump_json(indent=2) + "\n")


def load_ai_cost(path: str | Path = "data/ai_cost.json") -> AICost:
    """Load and validate AI cost tracking from JSON.

    Returns AICost with current month and zero values if file doesn't exist.
    Auto-resets to current month if stored month differs (monthly reset).
    """
    path = Path(path)
    current_month = datetime.now(UTC).strftime("%Y-%m")

    if not path.exists():
        return AICost(month=current_month)

    text = path.read_text().strip()
    if not text:
        return AICost(month=current_month)

    raw = json.loads(text)
    cost = AICost.model_validate(raw)

    # Monthly reset: if stored month differs from current, reset counters
    if cost.month != current_month:
        return AICost(month=current_month)

    return cost


def save_ai_cost(cost: AICost, path: str | Path = "data/ai_cost.json") -> None:
    """Save AICost to JSON file."""
    path = Path(path)
    path.write_text(cost.model_dump_json(indent=2) + "\n")
