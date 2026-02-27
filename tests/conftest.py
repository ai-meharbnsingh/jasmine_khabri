import pytest
from pathlib import Path


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
def seen_path(data_dir: Path) -> Path:
    """Path to seen.json."""
    return data_dir / "seen.json"


@pytest.fixture
def history_path(data_dir: Path) -> Path:
    """Path to history.json."""
    return data_dir / "history.json"
