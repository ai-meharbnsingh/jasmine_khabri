"""Tests for RSS feed fetcher using httpx + feedparser fetch-then-parse pattern.

TDD Phase 3 Plan 01 — RED phase tests written before implementation.
Uses respx to mock httpx calls — no real network requests.
"""

import httpx
import respx

from pipeline.fetchers.rss_fetcher import fetch_all_rss, fetch_rss_feed
from pipeline.schemas.config_schema import RssFeedConfig

# ---------------------------------------------------------------------------
# RSS XML fixtures
# ---------------------------------------------------------------------------

VALID_RSS_1_ITEM = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>ET Realty</title>
    <link>https://et-realty.example.com</link>
    <item>
      <title>Mumbai Metro Phase 3 Opens</title>
      <link>https://et-realty.example.com/metro-phase-3</link>
      <pubDate>Fri, 27 Feb 2026 04:30:00 +0000</pubDate>
      <description>Metro Phase 3 officially inaugurated today.</description>
    </item>
  </channel>
</rss>
"""

VALID_RSS_3_ITEMS = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Moneycontrol Realty</title>
    <link>https://mc.example.com</link>
    <item>
      <title>Article One</title>
      <link>https://mc.example.com/one</link>
      <pubDate>Thu, 26 Feb 2026 10:00:00 +0000</pubDate>
    </item>
    <item>
      <title>Article Two</title>
      <link>https://mc.example.com/two</link>
      <pubDate>Thu, 26 Feb 2026 11:00:00 +0000</pubDate>
    </item>
    <item>
      <title>Article Three</title>
      <link>https://mc.example.com/three</link>
      <pubDate>Thu, 26 Feb 2026 12:00:00 +0000</pubDate>
    </item>
  </channel>
</rss>
"""

# RSS with an item that has no link — should be skipped
RSS_ITEM_NO_LINK = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <link>https://test.example.com</link>
    <item>
      <title>Article With Link</title>
      <link>https://test.example.com/with-link</link>
      <pubDate>Fri, 27 Feb 2026 04:30:00 +0000</pubDate>
    </item>
    <item>
      <title>Article Without Link</title>
      <pubDate>Fri, 27 Feb 2026 04:30:00 +0000</pubDate>
    </item>
  </channel>
</rss>
"""

# RSS with IST pubDate (+0530) — must be converted to UTC ISO 8601
RSS_IST_PUBDATE = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Hindu Business Line</title>
    <link>https://hbl.example.com</link>
    <item>
      <title>RERA Budget Update</title>
      <link>https://hbl.example.com/rera-budget</link>
      <pubDate>Thu, 27 Feb 2026 10:00:00 +0530</pubDate>
    </item>
  </channel>
</rss>
"""

# RSS item with no pubDate — should fall back to fetched_at
RSS_NO_PUBDATE = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <link>https://test.example.com</link>
    <item>
      <title>Undated Article</title>
      <link>https://test.example.com/undated</link>
      <description>No publication date here.</description>
    </item>
  </channel>
</rss>
"""

# RSS with description content — summary should still be empty
RSS_WITH_DESCRIPTION = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <link>https://test.example.com</link>
    <item>
      <title>Article With Description</title>
      <link>https://test.example.com/described</link>
      <pubDate>Fri, 27 Feb 2026 04:30:00 +0000</pubDate>
      <description>A rich description that AI will summarize in Phase 5.</description>
    </item>
  </channel>
</rss>
"""

# Slightly malformed XML — feedparser marks as bozo but still parses entries
BOZO_RSS = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Bozo Feed</title>
    <link>https://bozo.example.com
    <item>
      <title>Parseable Despite Bozo</title>
      <link>https://bozo.example.com/article</link>
      <pubDate>Fri, 27 Feb 2026 04:30:00 +0000</pubDate>
    </item>
  </channel>
</rss>
"""

FEED_URL = "https://et-realty.example.com/rss"


class TestFetchRssFeed:
    """Tests for fetch_rss_feed() — single feed fetching with error isolation."""

    @respx.mock
    def test_success_single_article(self):
        """Mock 200 with 1 item — returns 1 Article, error is None."""
        respx.get(FEED_URL).mock(
            return_value=httpx.Response(200, content=VALID_RSS_1_ITEM.encode())
        )

        articles, error = fetch_rss_feed(FEED_URL, "ET Realty")

        assert error is None
        assert len(articles) == 1
        assert articles[0].title == "Mumbai Metro Phase 3 Opens"
        assert articles[0].url == "https://et-realty.example.com/metro-phase-3"
        assert articles[0].source == "ET Realty"

    @respx.mock
    def test_success_multiple_articles(self):
        """Mock 200 with 3 items — returns 3 Articles."""
        respx.get(FEED_URL).mock(
            return_value=httpx.Response(200, content=VALID_RSS_3_ITEMS.encode())
        )

        articles, error = fetch_rss_feed(FEED_URL, "Moneycontrol Realty")

        assert error is None
        assert len(articles) == 3

    @respx.mock
    def test_timeout_returns_empty_with_error(self):
        """Timeout exception — returns ([], error_string) with 'timeout' in error."""
        respx.get(FEED_URL).mock(side_effect=httpx.TimeoutException("timed out"))

        articles, error = fetch_rss_feed(FEED_URL, "ET Realty")

        assert articles == []
        assert error is not None
        assert "timeout" in error.lower()

    @respx.mock
    def test_http_error_returns_empty_with_error(self):
        """HTTP 500 response — returns ([], error_string) with 'HTTP 500' in error."""
        respx.get(FEED_URL).mock(return_value=httpx.Response(500))

        articles, error = fetch_rss_feed(FEED_URL, "ET Realty")

        assert articles == []
        assert error is not None
        assert "500" in error

    @respx.mock
    def test_network_error_returns_empty_with_error(self):
        """ConnectError — returns ([], error_string) with 'network error' in error."""
        respx.get(FEED_URL).mock(side_effect=httpx.ConnectError("connection refused"))

        articles, error = fetch_rss_feed(FEED_URL, "ET Realty")

        assert articles == []
        assert error is not None
        assert "network error" in error.lower()

    @respx.mock
    def test_bozo_feed_still_yields_articles(self):
        """Bozo-flagged feed still returns parseable entries — not discarded."""
        respx.get(FEED_URL).mock(return_value=httpx.Response(200, content=BOZO_RSS.encode()))

        articles, error = fetch_rss_feed(FEED_URL, "Bozo Feed")

        # Bozo feeds with parseable entries should not return empty
        assert len(articles) >= 1

    @respx.mock
    def test_entry_with_no_link_skipped(self):
        """RSS item without <link> is skipped — only items with links returned."""
        respx.get(FEED_URL).mock(
            return_value=httpx.Response(200, content=RSS_ITEM_NO_LINK.encode())
        )

        articles, error = fetch_rss_feed(FEED_URL, "Test Feed")

        assert error is None
        # Only the article WITH a link should be returned
        assert len(articles) == 1
        assert articles[0].url == "https://test.example.com/with-link"

    @respx.mock
    def test_published_at_uses_parsed_utc(self):
        """IST pubDate +0530 is converted to UTC ISO 8601 string."""
        respx.get(FEED_URL).mock(return_value=httpx.Response(200, content=RSS_IST_PUBDATE.encode()))

        articles, error = fetch_rss_feed(FEED_URL, "Hindu Business Line")

        assert error is None
        assert len(articles) == 1
        # 10:00 IST (+0530) == 04:30 UTC
        # The published_at should be a UTC ISO string (not the raw RSS string)
        pub = articles[0].published_at
        assert "+0530" not in pub, f"published_at should be UTC, got: {pub}"
        assert "04:30" in pub, f"Expected 04:30 UTC in published_at, got: {pub}"

    @respx.mock
    def test_missing_published_at_falls_back_to_fetched_at(self):
        """RSS item with no <pubDate> uses fetched_at as published_at."""
        respx.get(FEED_URL).mock(return_value=httpx.Response(200, content=RSS_NO_PUBDATE.encode()))

        articles, error = fetch_rss_feed(FEED_URL, "Test Feed")

        assert error is None
        assert len(articles) == 1
        article = articles[0]
        # published_at should equal fetched_at when no pubDate
        assert article.published_at == article.fetched_at

    @respx.mock
    def test_summary_extracted_from_description(self):
        """summary is extracted from RSS description for relevance scoring."""
        respx.get(FEED_URL).mock(
            return_value=httpx.Response(200, content=RSS_WITH_DESCRIPTION.encode())
        )

        articles, error = fetch_rss_feed(FEED_URL, "Test Feed")

        assert error is None
        assert len(articles) == 1
        assert articles[0].summary == "A rich description that AI will summarize in Phase 5."


class TestFetchAllRss:
    """Tests for fetch_all_rss() — batch fetching with error isolation and health results."""

    FEED_CONFIGS = [
        RssFeedConfig(name="ET Realty", url="https://et-realty.example.com/rss", enabled=True),
        RssFeedConfig(name="Moneycontrol", url="https://mc.example.com/rss", enabled=True),
        RssFeedConfig(name="Disabled Feed", url="https://disabled.example.com/rss", enabled=False),
    ]

    @respx.mock
    def test_fetches_all_enabled_feeds(self):
        """2 enabled + 1 disabled — articles from both enabled, none from disabled."""
        respx.get("https://et-realty.example.com/rss").mock(
            return_value=httpx.Response(200, content=VALID_RSS_1_ITEM.encode())
        )
        respx.get("https://mc.example.com/rss").mock(
            return_value=httpx.Response(200, content=VALID_RSS_3_ITEMS.encode())
        )

        articles, health = fetch_all_rss(self.FEED_CONFIGS)

        # 1 from ET Realty + 3 from Moneycontrol = 4 total
        assert len(articles) == 4

        sources = {a.source for a in articles}
        assert "ET Realty" in sources
        assert "Moneycontrol" in sources
        assert "Disabled Feed" not in sources

    @respx.mock
    def test_one_feed_failure_doesnt_stop_others(self):
        """First feed times out — second feed's articles still returned."""
        respx.get("https://et-realty.example.com/rss").mock(
            side_effect=httpx.TimeoutException("timed out")
        )
        respx.get("https://mc.example.com/rss").mock(
            return_value=httpx.Response(200, content=VALID_RSS_3_ITEMS.encode())
        )

        articles, health = fetch_all_rss(self.FEED_CONFIGS)

        # ET Realty failed, but Moneycontrol's 3 articles should still be returned
        assert len(articles) == 3
        assert all(a.source == "Moneycontrol" for a in articles)

    @respx.mock
    def test_returns_health_results(self):
        """fetch_all_rss returns health list with source/status/count/error per feed."""
        respx.get("https://et-realty.example.com/rss").mock(
            return_value=httpx.Response(200, content=VALID_RSS_1_ITEM.encode())
        )
        respx.get("https://mc.example.com/rss").mock(
            side_effect=httpx.TimeoutException("timed out")
        )

        articles, health = fetch_all_rss(self.FEED_CONFIGS)

        assert isinstance(health, list)
        # Only enabled feeds appear in health results
        assert len(health) == 2

        health_by_source = {h["source"]: h for h in health}

        et_health = health_by_source["ET Realty"]
        assert et_health["status"] == "OK"
        assert et_health["count"] == 1
        assert et_health["error"] is None

        mc_health = health_by_source["Moneycontrol"]
        assert mc_health["status"] == "FAIL"
        assert mc_health["count"] == 0
        assert mc_health["error"] is not None
