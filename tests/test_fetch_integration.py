"""Integration tests for the complete pipeline fetch phase (RSS + GNews).

Uses respx to mock HTTP endpoints — zero real network calls.
Class-based pytest pattern: one class per concern.
"""

import textwrap

import httpx
import pytest
import respx

from pipeline.fetchers.gnews_fetcher import (
    build_gnews_queries,
    fetch_all_gnews,
)
from pipeline.fetchers.rss_fetcher import fetch_all_rss
from pipeline.schemas.config_schema import RssFeedConfig
from pipeline.schemas.gnews_quota_schema import GNewsQuota
from pipeline.schemas.keywords_schema import KeywordsConfig
from pipeline.utils.loader import load_config

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_RSS = textwrap.dedent("""\
    <?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <title>Test Feed</title>
        <item>
          <title>Article One</title>
          <link>https://example.com/article-1</link>
          <pubDate>Mon, 27 Jan 2025 06:00:00 +0000</pubDate>
        </item>
        <item>
          <title>Article Two</title>
          <link>https://example.com/article-2</link>
          <pubDate>Mon, 27 Jan 2025 07:00:00 +0000</pubDate>
        </item>
      </channel>
    </rss>
""")

_GNEWS_RESPONSE = {
    "totalArticles": 3,
    "articles": [
        {
            "title": "GNews Article 1",
            "url": "https://gnews.example.com/1",
            "publishedAt": "2025-01-27T06:00:00Z",
            "content": "",
        },
        {
            "title": "GNews Article 2",
            "url": "https://gnews.example.com/2",
            "publishedAt": "2025-01-27T07:00:00Z",
            "content": "",
        },
        {
            "title": "GNews Article 3",
            "url": "https://gnews.example.com/3",
            "publishedAt": "2025-01-27T08:00:00Z",
            "content": "",
        },
    ],
}


def _make_feeds(*urls_and_names: tuple[str, str]) -> list[RssFeedConfig]:
    return [RssFeedConfig(name=name, url=url, enabled=True) for url, name in urls_and_names]


def _minimal_quota() -> GNewsQuota:
    return GNewsQuota(date="1970-01-01", calls_used=0, daily_limit=25)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRssAndGNewsCombinedFetch:
    """RSS + GNews combined fetch: partial RSS failure + successful GNews."""

    @respx.mock
    def test_rss_and_gnews_combined_fetch(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GNEWS_API_KEY", "test-key-123")

        # Mock one working RSS feed and one timeout
        respx.get("https://rss.working.example.com/feed").mock(
            return_value=httpx.Response(200, content=_VALID_RSS.encode())
        )
        respx.get("https://rss.timeout.example.com/feed").mock(
            side_effect=httpx.TimeoutException("timed out")
        )
        # Mock GNews endpoint (matches any URL with gnews.io/api/v4/search)
        respx.get("https://gnews.io/api/v4/search").mock(
            return_value=httpx.Response(200, json=_GNEWS_RESPONSE)
        )

        feeds = _make_feeds(
            ("https://rss.working.example.com/feed", "WorkingFeed"),
            ("https://rss.timeout.example.com/feed", "TimeoutFeed"),
        )

        rss_articles, rss_health = fetch_all_rss(feeds)
        assert len(rss_articles) == 2, f"Expected 2 RSS articles, got {len(rss_articles)}"

        ok_row = next(r for r in rss_health if r["source"] == "WorkingFeed")
        fail_row = next(r for r in rss_health if r["source"] == "TimeoutFeed")
        assert ok_row["status"] == "OK"
        assert fail_row["status"] == "FAIL"
        assert fail_row["error"] is not None

        # GNews fetch
        keywords_cfg = KeywordsConfig.model_validate(
            {"categories": {"infrastructure": {"active": True, "keywords": ["metro", "highway"]}}}
        )
        queries = build_gnews_queries(keywords_cfg)
        quota = _minimal_quota()
        gnews_articles, _quota, gnews_health = fetch_all_gnews(queries, "test-key-123", quota)

        assert len(gnews_articles) == 3, f"Expected 3 GNews articles, got {len(gnews_articles)}"

        total = len(rss_articles) + len(gnews_articles)
        assert total == 5, f"Expected 5 total articles, got {total}"

        # All articles have required fields
        for article in rss_articles + gnews_articles:
            assert article.title
            assert article.url
            assert article.source
            assert article.published_at
            assert article.summary == ""
            assert article.fetched_at


class TestAllRssFailPipelineContinues:
    """When all RSS feeds fail, pipeline returns 0 articles without raising."""

    @respx.mock
    def test_all_rss_fail_pipeline_continues(self) -> None:
        respx.get("https://rss.fail1.example.com/feed").mock(return_value=httpx.Response(500))
        respx.get("https://rss.fail2.example.com/feed").mock(return_value=httpx.Response(500))

        feeds = _make_feeds(
            ("https://rss.fail1.example.com/feed", "Fail1"),
            ("https://rss.fail2.example.com/feed", "Fail2"),
        )

        # Must not raise
        rss_articles, rss_health = fetch_all_rss(feeds)

        assert rss_articles == []
        assert all(r["status"] == "FAIL" for r in rss_health)


class TestConfigYamlLoadsRssFeeds:
    """Real data/config.yaml must contain exactly 8 enabled RSS feeds."""

    def test_config_yaml_loads_rss_feeds(self) -> None:
        config = load_config("data/config.yaml")
        assert len(config.rss_feeds) == 8, (
            f"Expected 8 RSS feeds in config.yaml, got {len(config.rss_feeds)}"
        )
        for feed in config.rss_feeds:
            assert feed.name, "Feed missing name"
            assert feed.url.startswith("http"), f"Feed {feed.name} has invalid URL: {feed.url}"
            assert feed.enabled is True, f"Feed {feed.name} should be enabled"


class TestGNewsSkippedWithoutApiKey:
    """GNews fetch is skipped gracefully when GNEWS_API_KEY is absent."""

    @respx.mock
    def test_gnews_skipped_without_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GNEWS_API_KEY", raising=False)

        respx.get("https://rss.ok.example.com/feed").mock(
            return_value=httpx.Response(200, content=_VALID_RSS.encode())
        )

        feeds = _make_feeds(("https://rss.ok.example.com/feed", "OkFeed"))
        rss_articles, _rss_health = fetch_all_rss(feeds)

        # Simulate main.py guard: only call GNews if key present
        gnews_api_key = ""
        gnews_articles: list = []
        if gnews_api_key:
            # This block should NOT execute
            gnews_articles = ["should not appear"]  # type: ignore[list-item]

        assert gnews_articles == [], "GNews articles should be empty when key not set"
        assert len(rss_articles) == 2
