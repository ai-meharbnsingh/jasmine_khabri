"""Tests for Article, GNewsQuota, and RssFeedConfig Pydantic schemas.

TDD Phase 3 Plan 01 — RED phase tests written before implementation.
"""

import pytest
from pydantic import ValidationError

from pipeline.schemas.article_schema import Article
from pipeline.schemas.config_schema import AppConfig, RssFeedConfig
from pipeline.schemas.gnews_quota_schema import GNewsQuota


class TestArticle:
    """Tests for the Article Pydantic model."""

    def test_valid_article(self):
        """All fields populated — validates OK."""
        article = Article(
            title="Mumbai Metro Phase 3 Opens",
            url="https://example.com/metro-phase-3",
            source="ET Realty",
            published_at="2026-02-27T10:00:00+00:00",
            summary="",
            fetched_at="2026-02-27T10:05:00+00:00",
        )
        assert article.title == "Mumbai Metro Phase 3 Opens"
        assert article.url == "https://example.com/metro-phase-3"
        assert article.source == "ET Realty"
        assert article.published_at == "2026-02-27T10:00:00+00:00"
        assert article.fetched_at == "2026-02-27T10:05:00+00:00"

    def test_summary_defaults_empty(self):
        """Summary defaults to '' when not provided — Phase 5 AI populates it."""
        article = Article(
            title="RERA Update",
            url="https://example.com/rera",
            source="Moneycontrol",
            published_at="2026-02-27T08:00:00+00:00",
            fetched_at="2026-02-27T08:01:00+00:00",
        )
        assert article.summary == ""

    def test_missing_required_field_raises(self):
        """title, url, source, published_at, fetched_at are all required."""
        with pytest.raises(ValidationError):
            Article(
                title="Missing URL",
                source="ET Realty",
                published_at="2026-02-27T10:00:00+00:00",
                fetched_at="2026-02-27T10:00:00+00:00",
            )

        with pytest.raises(ValidationError):
            Article(
                url="https://example.com/article",
                source="ET Realty",
                published_at="2026-02-27T10:00:00+00:00",
                fetched_at="2026-02-27T10:00:00+00:00",
            )

        with pytest.raises(ValidationError):
            Article(
                title="Missing Source",
                url="https://example.com/article",
                published_at="2026-02-27T10:00:00+00:00",
                fetched_at="2026-02-27T10:00:00+00:00",
            )

        with pytest.raises(ValidationError):
            Article(
                title="Missing published_at",
                url="https://example.com/article",
                source="ET Realty",
                fetched_at="2026-02-27T10:00:00+00:00",
            )

        with pytest.raises(ValidationError):
            Article(
                title="Missing fetched_at",
                url="https://example.com/article",
                source="ET Realty",
                published_at="2026-02-27T10:00:00+00:00",
            )

    def test_serialization_roundtrip(self):
        """model_dump_json -> model_validate_json preserves all fields."""
        original = Article(
            title="DPIIT Infrastructure Push",
            url="https://example.com/dpiit",
            source="Business Standard",
            published_at="2026-02-27T12:00:00+00:00",
            summary="AI summary here",
            fetched_at="2026-02-27T12:05:00+00:00",
        )
        json_str = original.model_dump_json()
        restored = Article.model_validate_json(json_str)
        assert restored.title == original.title
        assert restored.url == original.url
        assert restored.source == original.source
        assert restored.published_at == original.published_at
        assert restored.summary == original.summary
        assert restored.fetched_at == original.fetched_at


class TestGNewsQuota:
    """Tests for GNewsQuota tracking model."""

    def test_defaults(self):
        """calls_used defaults to 0, daily_limit defaults to 25."""
        quota = GNewsQuota(date="2026-02-27")
        assert quota.calls_used == 0
        assert quota.daily_limit == 25
        assert quota.date == "2026-02-27"

    def test_quota_serialization(self):
        """model_dump_json roundtrip preserves all fields."""
        quota = GNewsQuota(date="2026-02-27", calls_used=10, daily_limit=25)
        json_str = quota.model_dump_json()
        restored = GNewsQuota.model_validate_json(json_str)
        assert restored.date == quota.date
        assert restored.calls_used == quota.calls_used
        assert restored.daily_limit == quota.daily_limit


class TestRssFeedConfig:
    """Tests for RssFeedConfig and AppConfig.rss_feeds integration."""

    def test_feed_config(self):
        """name, url, enabled fields validate correctly."""
        feed = RssFeedConfig(
            name="ET Realty",
            url="https://realty.economictimes.indiatimes.com/rss",
            enabled=True,
        )
        assert feed.name == "ET Realty"
        assert feed.url == "https://realty.economictimes.indiatimes.com/rss"
        assert feed.enabled is True

    def test_enabled_defaults_true(self):
        """enabled defaults to True when not specified."""
        feed = RssFeedConfig(name="Moneycontrol", url="https://moneycontrol.com/rss")
        assert feed.enabled is True

    def test_app_config_with_rss_feeds(self):
        """AppConfig loads with rss_feeds list."""
        config = AppConfig(
            rss_feeds=[
                {"name": "ET Realty", "url": "https://et-realty.example.com/rss"},
                {"name": "Moneycontrol", "url": "https://mc.example.com/rss", "enabled": False},
            ]
        )
        assert len(config.rss_feeds) == 2
        assert config.rss_feeds[0].name == "ET Realty"
        assert config.rss_feeds[1].enabled is False
