"""Schema validation tests for Phase 1 scaffold.

Tests cover:
- Config loading and default validation
- Keyword library structure and active/inactive flags
- Seen/history store loading
- Package import smoke tests
"""

from pipeline.utils.loader import load_config, load_keywords, load_seen


class TestConfigSchema:
    """Tests for config.yaml loading and validation."""

    def test_config_loads_and_validates(self, config_path):
        """Config loads without validation errors."""
        config = load_config(str(config_path))
        assert config is not None

    def test_config_schedule_defaults(self, config_path):
        """Schedule defaults match locked decisions: 07:00 and 16:00 IST."""
        config = load_config(str(config_path))
        assert config.schedule.morning_ist == "07:00"
        assert config.schedule.evening_ist == "16:00"

    def test_config_delivery_max_stories(self, config_path):
        """Max stories per delivery is 15 (locked decision)."""
        config = load_config(str(config_path))
        assert config.delivery.max_stories == 15

    def test_config_telegram_breaking_news_enabled(self, config_path):
        """Breaking news alerts enabled by default (locked decision)."""
        config = load_config(str(config_path))
        assert config.telegram.breaking_news_enabled is True

    def test_config_email_enabled(self, config_path):
        """Email delivery enabled by default (locked decision)."""
        config = load_config(str(config_path))
        assert config.email.enabled is True


class TestKeywordsSchema:
    """Tests for keywords.yaml loading and validation."""

    def test_keywords_loads_and_validates(self, keywords_path):
        """Keywords load without validation errors."""
        kw = load_keywords(str(keywords_path))
        assert kw is not None

    def test_infrastructure_category_active(self, keywords_path):
        """Infrastructure category is active by default."""
        kw = load_keywords(str(keywords_path))
        assert kw.categories["infrastructure"].active is True

    def test_regulatory_category_active(self, keywords_path):
        """Regulatory category is active by default."""
        kw = load_keywords(str(keywords_path))
        assert kw.categories["regulatory"].active is True

    def test_celebrity_category_inactive(self, keywords_path):
        """Celebrity category is inactive by default (locked decision)."""
        kw = load_keywords(str(keywords_path))
        assert kw.categories["celebrity"].active is False

    def test_transaction_category_inactive(self, keywords_path):
        """Transaction category is inactive by default (locked decision)."""
        kw = load_keywords(str(keywords_path))
        assert kw.categories["transaction"].active is False

    def test_active_keywords_count(self, keywords_path):
        """Active keywords should be 30+ from Infrastructure + Regulatory."""
        kw = load_keywords(str(keywords_path))
        active = kw.active_keywords()
        assert len(active) >= 30, f"Expected 30+ active keywords, got {len(active)}"

    def test_exclusions_present(self, keywords_path):
        """Exclusion keywords are defined."""
        kw = load_keywords(str(keywords_path))
        assert len(kw.exclusions) >= 4
        assert "obituary" in kw.exclusions
        assert "gossip" in kw.exclusions

    def test_four_categories_exist(self, keywords_path):
        """All four categories exist: infrastructure, regulatory, celebrity, transaction."""
        kw = load_keywords(str(keywords_path))
        expected = {"infrastructure", "regulatory", "celebrity", "transaction"}
        assert set(kw.categories.keys()) == expected


class TestSeenSchema:
    """Tests for seen.json and history.json loading."""

    def test_seen_loads_empty(self, seen_path):
        """seen.json starts empty and loads without error."""
        store = load_seen(str(seen_path))
        assert store.entries == []

    def test_history_loads_empty(self, history_path):
        """history.json starts empty and loads without error."""
        store = load_seen(str(history_path))
        assert store.entries == []

    def test_seen_handles_missing_file(self, tmp_path):
        """load_seen gracefully handles missing file."""
        store = load_seen(str(tmp_path / "nonexistent.json"))
        assert store.entries == []


class TestPackageImports:
    """Smoke tests: package structure is correct and all modules importable."""

    def test_import_fetchers(self):
        from pipeline.fetchers import rss_fetcher  # noqa: F401

    def test_import_analyzers(self):
        from pipeline.analyzers import classifier  # noqa: F401

    def test_import_deliverers(self):
        from pipeline.deliverers import telegram_sender  # noqa: F401

    def test_import_bot(self):
        from pipeline.bot import handler  # noqa: F401

    def test_import_schemas(self):
        from pipeline.schemas import AppConfig, KeywordsConfig, SeenStore  # noqa: F401

    def test_import_utils(self):
        from pipeline.utils.loader import load_config, load_keywords, load_seen  # noqa: F401

    def test_version_exists(self):
        from pipeline import __version__

        assert __version__ == "0.1.0"
