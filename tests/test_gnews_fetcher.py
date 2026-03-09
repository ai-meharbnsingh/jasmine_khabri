"""TDD tests for GNews API fetcher — RED phase.

Tests cover:
- Boolean OR query construction from KeywordsConfig
- Quota load/reset/save logic
- fetch_gnews_query: success, quota exhausted, auth failure, rate limit, network error
- fetch_all_gnews: multi-query accumulation, early stop on quota exhaustion, health results
"""

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import respx

from pipeline.fetchers.gnews_fetcher import (
    build_gnews_queries,
    fetch_all_gnews,
    fetch_gnews_query,
    load_or_reset_quota,
    save_quota,
)
from pipeline.schemas.gnews_quota_schema import GNewsQuota
from pipeline.schemas.keywords_schema import KeywordCategory, KeywordsConfig

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TODAY_UTC = datetime.now(UTC).strftime("%Y-%m-%d")
_YESTERDAY_UTC = datetime.fromtimestamp(datetime.now(UTC).timestamp() - 86400, tz=UTC).strftime(
    "%Y-%m-%d"
)

_GNEWS_URL = "https://gnews.io/api/v4/search"

_SAMPLE_RESPONSE = {
    "totalArticles": 2,
    "articles": [
        {
            "title": "Metro Rail Phase 4 Update",
            "url": "https://example.com/metro-rail",
            "source": {"name": "Times of India"},
            "publishedAt": "2024-06-01T08:00:00Z",
            "description": "Metro construction resumes in Delhi.",
            "content": "Full article content here.",
        },
        {
            "title": "NHAI Highway Project Approved",
            "url": "https://example.com/nhai-highway",
            "source": {"name": "Economic Times"},
            "publishedAt": "2024-06-01T09:00:00Z",
            "description": "NHAI approves major highway project.",
            "content": "Full article content here.",
        },
    ],
}


def _make_keywords_config(
    infrastructure_keywords: list[str] | None = None,
    regulatory_keywords: list[str] | None = None,
    celebrity_active: bool = False,
) -> KeywordsConfig:
    categories: dict[str, KeywordCategory] = {}
    if infrastructure_keywords is not None:
        categories["infrastructure"] = KeywordCategory(
            active=True, keywords=infrastructure_keywords
        )
    if regulatory_keywords is not None:
        categories["regulatory"] = KeywordCategory(active=True, keywords=regulatory_keywords)
    categories["celebrity"] = KeywordCategory(
        active=celebrity_active,
        keywords=["Bollywood", "Shah Rukh Khan", "Deepika"],
    )
    return KeywordsConfig(categories=categories)


# ---------------------------------------------------------------------------
# TestBuildGnewsQueries
# ---------------------------------------------------------------------------


class TestBuildGnewsQueries:
    def test_builds_boolean_or_queries_from_keywords(self) -> None:
        """Returns a small list of broad OR-joined query strings."""
        config = _make_keywords_config(
            infrastructure_keywords=["metro", "highway", "expressway", "NHAI", "airport"],
            regulatory_keywords=["RERA", "PMAY", "affordable housing"],
        )
        queries = build_gnews_queries(config)
        assert isinstance(queries, list)
        assert len(queries) >= 1
        assert len(queries) <= 4  # Must be broad, not one per keyword
        combined = " ".join(queries)
        # At least some infrastructure keywords should appear
        assert any(kw in combined for kw in ["metro", "highway", "NHAI", "airport"])

    def test_skips_inactive_categories(self) -> None:
        """Celebrity keywords must not appear when category is inactive."""
        config = _make_keywords_config(
            infrastructure_keywords=["metro", "highway"],
            celebrity_active=False,
        )
        queries = build_gnews_queries(config)
        combined = " ".join(queries)
        assert "Bollywood" not in combined
        assert "Shah Rukh Khan" not in combined

    def test_empty_keywords_returns_empty_queries(self) -> None:
        """No active categories → empty list."""
        config = KeywordsConfig(
            categories={
                "celebrity": KeywordCategory(active=False, keywords=["Bollywood"]),
            }
        )
        queries = build_gnews_queries(config)
        assert queries == []


# ---------------------------------------------------------------------------
# TestLoadOrResetQuota
# ---------------------------------------------------------------------------


class TestLoadOrResetQuota:
    def test_loads_existing_quota_same_day(self, tmp_path: Path) -> None:
        """If file has today's UTC date, return stored quota with calls_used."""
        quota_file = tmp_path / "gnews_quota.json"
        stored = GNewsQuota(date=_TODAY_UTC, calls_used=5, daily_limit=25)
        quota_file.write_text(stored.model_dump_json(indent=2) + "\n")

        result = load_or_reset_quota(quota_file)

        assert result.calls_used == 5
        assert result.date == _TODAY_UTC

    def test_resets_quota_on_new_day(self, tmp_path: Path) -> None:
        """If file has yesterday's date, reset to calls_used=0."""
        quota_file = tmp_path / "gnews_quota.json"
        old = GNewsQuota(date=_YESTERDAY_UTC, calls_used=18, daily_limit=25)
        quota_file.write_text(old.model_dump_json(indent=2) + "\n")

        result = load_or_reset_quota(quota_file)

        assert result.calls_used == 0
        assert result.date == _TODAY_UTC

    def test_creates_default_if_file_missing(self, tmp_path: Path) -> None:
        """Non-existent file → fresh quota with today's date and calls_used=0."""
        quota_file = tmp_path / "missing_quota.json"

        result = load_or_reset_quota(quota_file)

        assert result.calls_used == 0
        assert result.date == _TODAY_UTC
        assert result.daily_limit == 25


# ---------------------------------------------------------------------------
# TestSaveQuota
# ---------------------------------------------------------------------------


class TestSaveQuota:
    def test_save_and_reload(self, tmp_path: Path) -> None:
        """save_quota writes valid JSON that round-trips back to GNewsQuota."""
        quota_file = tmp_path / "gnews_quota.json"
        quota = GNewsQuota(date=_TODAY_UTC, calls_used=7, daily_limit=25)

        save_quota(quota, quota_file)

        raw = json.loads(quota_file.read_text())
        assert raw["calls_used"] == 7
        assert raw["date"] == _TODAY_UTC
        assert raw["daily_limit"] == 25

        reloaded = GNewsQuota.model_validate(raw)
        assert reloaded == quota


# ---------------------------------------------------------------------------
# TestFetchGnewsQuery
# ---------------------------------------------------------------------------


class TestFetchGnewsQuery:
    @respx.mock
    def test_success_returns_articles(self) -> None:
        """Successful response returns 2 Article objects and increments quota."""
        respx.get(_GNEWS_URL).mock(return_value=httpx.Response(200, json=_SAMPLE_RESPONSE))
        quota = GNewsQuota(date=_TODAY_UTC, calls_used=0, daily_limit=25)

        articles, new_quota, error = fetch_gnews_query("metro OR highway", "fake-key", quota)

        assert error is None
        assert len(articles) == 2
        assert articles[0].title == "Metro Rail Phase 4 Update"
        assert articles[0].source == "GNews"
        assert articles[0].published_at == "2024-06-01T08:00:00Z"
        assert new_quota.calls_used == 1

    @respx.mock
    def test_quota_exhausted_skips_call(self) -> None:
        """When calls_used >= daily_limit, no HTTP call is made and empty list returned."""
        quota = GNewsQuota(date=_TODAY_UTC, calls_used=25, daily_limit=25)
        route = respx.get(_GNEWS_URL).mock(return_value=httpx.Response(200, json=_SAMPLE_RESPONSE))

        articles, returned_quota, error = fetch_gnews_query("metro", "fake-key", quota)

        assert articles == []
        assert not route.called
        assert returned_quota.calls_used == 25
        assert error == "quota exhausted"

    @respx.mock
    def test_auth_failure_401(self) -> None:
        """401 response returns empty list, does NOT increment calls_used."""
        respx.get(_GNEWS_URL).mock(return_value=httpx.Response(401))
        quota = GNewsQuota(date=_TODAY_UTC, calls_used=3, daily_limit=25)

        articles, returned_quota, error = fetch_gnews_query("metro", "bad-key", quota)

        assert articles == []
        assert returned_quota.calls_used == 3  # unchanged
        assert error is not None
        assert "401" in error or "auth" in error.lower()

    @respx.mock
    def test_rate_limit_429(self) -> None:
        """429 response marks quota as exhausted (calls_used set to daily_limit)."""
        respx.get(_GNEWS_URL).mock(return_value=httpx.Response(429))
        quota = GNewsQuota(date=_TODAY_UTC, calls_used=10, daily_limit=25)

        articles, returned_quota, error = fetch_gnews_query("metro", "fake-key", quota)

        assert articles == []
        assert returned_quota.calls_used == returned_quota.daily_limit
        assert error is not None
        assert "429" in error or "rate" in error.lower()

    @respx.mock
    def test_network_error(self) -> None:
        """ConnectError returns empty list, quota unchanged."""
        respx.get(_GNEWS_URL).mock(side_effect=httpx.ConnectError("Connection refused"))
        quota = GNewsQuota(date=_TODAY_UTC, calls_used=2, daily_limit=25)

        articles, returned_quota, error = fetch_gnews_query("metro", "fake-key", quota)

        assert articles == []
        assert returned_quota.calls_used == 2
        assert error is not None

    @respx.mock
    def test_summary_from_description(self) -> None:
        """Article.summary is populated from GNews description field."""
        respx.get(_GNEWS_URL).mock(return_value=httpx.Response(200, json=_SAMPLE_RESPONSE))
        quota = GNewsQuota(date=_TODAY_UTC, calls_used=0, daily_limit=25)

        articles, _, _ = fetch_gnews_query("metro", "fake-key", quota)

        assert articles[0].summary == "Metro construction resumes in Delhi."
        assert articles[1].summary == "NHAI approves major highway project."


# ---------------------------------------------------------------------------
# TestFetchAllGnews
# ---------------------------------------------------------------------------


class TestFetchAllGnews:
    @respx.mock
    def test_fetches_multiple_queries_updating_quota(self) -> None:
        """3 queries → 3 HTTP calls, all articles collected, quota += 3."""
        respx.get(_GNEWS_URL).mock(return_value=httpx.Response(200, json=_SAMPLE_RESPONSE))
        quota = GNewsQuota(date=_TODAY_UTC, calls_used=0, daily_limit=25)
        queries = ["metro OR highway", "RERA OR PMAY", "real estate OR property"]

        articles, final_quota, health = fetch_all_gnews(queries, "fake-key", quota)

        assert len(articles) == 6  # 2 per query × 3
        assert final_quota.calls_used == 3
        assert len(health) == 3

    @respx.mock
    def test_stops_when_quota_exhausted_mid_run(self) -> None:
        """With 1 call remaining, only 1 HTTP call is made; remaining queries are skipped."""
        respx.get(_GNEWS_URL).mock(return_value=httpx.Response(200, json=_SAMPLE_RESPONSE))
        quota = GNewsQuota(date=_TODAY_UTC, calls_used=24, daily_limit=25)
        queries = ["metro OR highway", "RERA OR PMAY", "real estate OR property"]

        articles, final_quota, health = fetch_all_gnews(queries, "fake-key", quota)

        # Only 1 call can happen before quota exhausted
        assert len(articles) == 2
        assert final_quota.calls_used == 25
        # Health shows 1 OK and 2 SKIPs
        statuses = [h["status"] for h in health]
        assert statuses.count("OK") == 1
        assert statuses.count("SKIP") == 2

    @respx.mock
    def test_returns_health_results(self) -> None:
        """Health results are dicts with required keys: query, status, count, error."""
        respx.get(_GNEWS_URL).mock(return_value=httpx.Response(200, json=_SAMPLE_RESPONSE))
        quota = GNewsQuota(date=_TODAY_UTC, calls_used=0, daily_limit=25)
        queries = ["metro OR highway"]

        _, _, health = fetch_all_gnews(queries, "fake-key", quota)

        assert len(health) == 1
        h = health[0]
        assert "query" in h
        assert "status" in h
        assert "count" in h
        assert "error" in h
        assert h["status"] == "OK"
        assert h["count"] == 2
