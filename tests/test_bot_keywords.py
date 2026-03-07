"""Tests for keyword management — mutations, display, and command handlers.

TDD Phase 9 Plan 01.
Task 1: Mutation tests (add_keyword, remove_keyword, serialize_keywords).
Task 2: Display and handler tests (format_keywords_display, commands).
"""

import yaml

from pipeline.bot.keywords import add_keyword, remove_keyword, serialize_keywords
from pipeline.schemas.keywords_schema import KeywordCategory, KeywordsConfig


def _make_config() -> KeywordsConfig:
    """Create a minimal KeywordsConfig for testing."""
    return KeywordsConfig(
        categories={
            "infrastructure": KeywordCategory(
                active=True, keywords=["metro", "highway", "airport"]
            ),
            "celebrity": KeywordCategory(active=False, keywords=["Salman Khan", "Virat Kohli"]),
        },
        exclusions=["obituary", "scandal"],
    )


class TestAddKeyword:
    """Tests for add_keyword pure mutation function."""

    def test_adds_keyword_to_existing_category(self):
        """add_keyword appends keyword to specified category."""
        config = _make_config()
        result = add_keyword(config, "infrastructure", "bullet train")
        assert "bullet train" in result.categories["infrastructure"].keywords
        assert len(result.categories["infrastructure"].keywords) == 4

    def test_returns_new_config_immutably(self):
        """add_keyword returns new KeywordsConfig, does not mutate original."""
        config = _make_config()
        result = add_keyword(config, "infrastructure", "bullet train")
        assert result is not config
        assert "bullet train" not in config.categories["infrastructure"].keywords

    def test_raises_on_unknown_category(self):
        """add_keyword raises ValueError for non-existent category."""
        config = _make_config()
        import pytest

        with pytest.raises(ValueError, match="Unknown category"):
            add_keyword(config, "nonexistent", "test")

    def test_raises_on_duplicate_case_insensitive(self):
        """add_keyword raises ValueError for duplicate keyword (case-insensitive)."""
        config = _make_config()
        import pytest

        with pytest.raises(ValueError, match="already exists"):
            add_keyword(config, "infrastructure", "Metro")

    def test_case_insensitive_category_lookup(self):
        """add_keyword finds category with different casing."""
        config = _make_config()
        result = add_keyword(config, "Infrastructure", "bullet train")
        assert "bullet train" in result.categories["infrastructure"].keywords


class TestRemoveKeyword:
    """Tests for remove_keyword pure mutation function."""

    def test_removes_keyword_from_category(self):
        """remove_keyword removes the specified keyword."""
        config = _make_config()
        result = remove_keyword(config, "celebrity", "Salman Khan")
        assert "Salman Khan" not in result.categories["celebrity"].keywords
        assert len(result.categories["celebrity"].keywords) == 1

    def test_returns_new_config_immutably(self):
        """remove_keyword returns new KeywordsConfig, does not mutate original."""
        config = _make_config()
        result = remove_keyword(config, "celebrity", "Salman Khan")
        assert result is not config
        assert "Salman Khan" in config.categories["celebrity"].keywords

    def test_raises_on_unknown_category(self):
        """remove_keyword raises ValueError for non-existent category."""
        config = _make_config()
        import pytest

        with pytest.raises(ValueError, match="Unknown category"):
            remove_keyword(config, "nonexistent", "test")

    def test_raises_on_keyword_not_found(self):
        """remove_keyword raises ValueError for keyword not in category."""
        config = _make_config()
        import pytest

        with pytest.raises(ValueError, match="not found"):
            remove_keyword(config, "infrastructure", "nonexistent keyword")

    def test_case_insensitive_category_and_keyword(self):
        """remove_keyword matches category and keyword case-insensitively."""
        config = _make_config()
        result = remove_keyword(config, "Celebrity", "salman khan")
        assert len(result.categories["celebrity"].keywords) == 1


class TestSerializeKeywords:
    """Tests for serialize_keywords — YAML round-trip."""

    def test_produces_valid_yaml(self):
        """serialize_keywords output is valid YAML."""
        config = _make_config()
        result = serialize_keywords(config)
        parsed = yaml.safe_load(result)
        assert "categories" in parsed

    def test_round_trips_through_keywords_config(self):
        """serialize_keywords output can be parsed back into KeywordsConfig."""
        config = _make_config()
        result = serialize_keywords(config)
        parsed = yaml.safe_load(result)
        restored = KeywordsConfig(**parsed)
        assert (
            restored.categories["infrastructure"].keywords
            == config.categories["infrastructure"].keywords
        )
        assert restored.exclusions == config.exclusions

    def test_preserves_active_status(self):
        """serialize_keywords preserves active/inactive boolean per category."""
        config = _make_config()
        result = serialize_keywords(config)
        parsed = yaml.safe_load(result)
        assert parsed["categories"]["infrastructure"]["active"] is True
        assert parsed["categories"]["celebrity"]["active"] is False
