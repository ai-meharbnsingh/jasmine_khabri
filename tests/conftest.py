from pathlib import Path

import pytest


@pytest.fixture
def data_dir() -> Path:
    """Path to the data/ directory."""
    return Path(__file__).parent.parent / "data"


@pytest.fixture
def config_path(data_dir: Path) -> Path:
    """Path to config.yaml."""
    return data_dir / "config.yaml"


@pytest.fixture
def keywords_path(data_dir: Path) -> Path:
    """Path to keywords.yaml."""
    return data_dir / "keywords.yaml"


@pytest.fixture
def seen_path(tmp_path: Path) -> Path:
    """Isolated seen.json using tmp_path (not live data)."""
    p = tmp_path / "seen.json"
    p.write_text('{"entries": []}')
    return p


@pytest.fixture
def history_path(tmp_path: Path) -> Path:
    """Isolated history.json using tmp_path (not live data)."""
    p = tmp_path / "history.json"
    p.write_text('{"entries": []}')
    return p
