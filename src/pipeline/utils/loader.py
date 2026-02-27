"""Data file loaders. All data access MUST go through these functions."""

import json
from pathlib import Path

import yaml

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
