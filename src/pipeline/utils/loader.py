"""Data file loaders. All data access MUST go through these functions."""

import json
from datetime import UTC, datetime
from pathlib import Path

import yaml

from pipeline.schemas.ai_cost_schema import AICost
from pipeline.schemas.bot_state_schema import BotState
from pipeline.schemas.config_schema import AppConfig
from pipeline.schemas.keywords_schema import KeywordsConfig
from pipeline.schemas.pipeline_status_schema import PipelineStatus
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


def load_pipeline_status(path: str | Path = "data/pipeline_status.json") -> PipelineStatus:
    """Load and validate pipeline status from JSON.

    Returns PipelineStatus with defaults if file doesn't exist or is empty.
    Auto-resets monthly counters when usage_month differs from current month.
    """
    path = Path(path)
    current_month = datetime.now(UTC).strftime("%Y-%m")

    if not path.exists():
        return PipelineStatus()

    text = path.read_text().strip()
    if not text:
        return PipelineStatus()

    raw = json.loads(text)
    status = PipelineStatus.model_validate(raw)

    # Monthly reset: if stored month differs from current, reset usage counters
    if status.usage_month != current_month:
        return status.model_copy(
            update={
                "usage_month": current_month,
                "monthly_deliver_runs": 0,
                "monthly_breaking_runs": 0,
                "monthly_breaking_alerts": 0,
                "est_actions_minutes": 0.0,
            }
        )

    return status


def save_pipeline_status(
    status: PipelineStatus, path: str | Path = "data/pipeline_status.json"
) -> None:
    """Save PipelineStatus to JSON file."""
    path = Path(path)
    path.write_text(status.model_dump_json(indent=2) + "\n")


def load_bot_state(path: str | Path = "data/bot_state.json") -> BotState:
    """Load and validate bot state from JSON.

    Returns BotState with defaults if file doesn't exist or is empty.
    """
    path = Path(path)
    if not path.exists():
        return BotState()

    text = path.read_text().strip()
    if not text:
        return BotState()

    raw = json.loads(text)
    return BotState.model_validate(raw)
