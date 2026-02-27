"""GNews.io API client with Boolean-grouped queries and daily quota tracking.

Free tier: 100 req/day total. We budget 25 calls/day here (split 12 morning /
13 evening in deliver.yml schedule). Quota persists in data/gnews_quota.json
and auto-resets on each new UTC calendar day.
"""

import logging
from datetime import UTC, datetime
from pathlib import Path

import httpx

from pipeline.schemas.article_schema import Article
from pipeline.schemas.gnews_quota_schema import GNewsQuota
from pipeline.schemas.keywords_schema import KeywordsConfig

logger = logging.getLogger(__name__)

GNEWS_BASE = "https://gnews.io/api/v4/search"
GNEWS_MAX_PER_REQUEST = 10  # Free tier hard limit


# ---------------------------------------------------------------------------
# Query builder
# ---------------------------------------------------------------------------

# Pre-built broad Boolean OR queries per category type.
# The planner research locked these as ~3-4 queries to stay well within budget.
_INFRA_QUERY = 'metro OR highway OR expressway OR NHAI OR airport OR AAI OR "smart city" OR DMRC'
_REGULATORY_QUERY = 'RERA OR PMAY OR "affordable housing" OR MahaRERA OR MoHUA OR CIDCO OR MMRDA'
_MARKET_QUERY = (
    '"real estate" OR "property market" OR "housing project" OR DDA OR "land acquisition"'
)

_CATEGORY_QUERIES: dict[str, str] = {
    "infrastructure": _INFRA_QUERY,
    "regulatory": _REGULATORY_QUERY,
    # transaction and market categories share a broad real-estate query
    "transaction": _MARKET_QUERY,
}


def build_gnews_queries(keywords_config: KeywordsConfig) -> list[str]:
    """Return 3-4 broad Boolean OR query strings from active keyword categories.

    Strategy: map each *active* category to a pre-built broad query rather than
    generating one query per keyword (which would exhaust the 25-call budget fast).
    """
    seen_queries: set[str] = set()
    queries: list[str] = []

    for category_name, category in keywords_config.categories.items():
        if not category.active:
            continue
        if not category.keywords:
            continue
        query = _CATEGORY_QUERIES.get(category_name)
        if query is None:
            # Fallback: OR-join the first 8 keywords from any unlisted category
            kws = category.keywords[:8]
            query = " OR ".join(f'"{kw}"' if " " in kw else kw for kw in kws)
        if query and query not in seen_queries:
            seen_queries.add(query)
            queries.append(query)

    return queries


# ---------------------------------------------------------------------------
# Quota persistence
# ---------------------------------------------------------------------------


def _today_utc() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


def load_or_reset_quota(path: str | Path) -> GNewsQuota:
    """Load quota from *path*; reset to zero if date differs or file missing."""
    today = _today_utc()
    try:
        text = Path(path).read_text()
        quota = GNewsQuota.model_validate_json(text)
        if quota.date == today:
            return quota
        # New UTC day — reset counter
        return GNewsQuota(date=today, calls_used=0, daily_limit=quota.daily_limit)
    except (FileNotFoundError, OSError):
        return GNewsQuota(date=today, calls_used=0, daily_limit=25)
    except Exception:  # noqa: BLE001
        return GNewsQuota(date=today, calls_used=0, daily_limit=25)


def save_quota(quota: GNewsQuota, path: str | Path) -> None:
    """Write *quota* as indented JSON to *path*."""
    Path(path).write_text(quota.model_dump_json(indent=2) + "\n")


# ---------------------------------------------------------------------------
# Article normalisation helper
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalise_article(raw: dict) -> Article:
    """Map a raw GNews API article dict to the canonical Article schema."""
    return Article(
        title=raw.get("title", ""),
        url=raw.get("url", ""),
        source="GNews",
        published_at=raw.get("publishedAt", _now_iso()),
        summary="",  # ALWAYS empty in Phase 3 — Phase 5 AI will populate
        fetched_at=_now_iso(),
    )


# ---------------------------------------------------------------------------
# Core fetch functions
# ---------------------------------------------------------------------------


def fetch_gnews_query(
    query: str,
    api_key: str,
    quota: GNewsQuota,
) -> tuple[list[Article], GNewsQuota, str | None]:
    """Fetch a single GNews search query.

    Returns:
        (articles, updated_quota, error_string_or_None)
    """
    # --- quota gate ---
    if quota.calls_used >= quota.daily_limit:
        logger.warning(
            "GNews daily quota exhausted (%d/%d) — skipping query",
            quota.calls_used,
            quota.daily_limit,
        )
        return [], quota, "quota exhausted"

    params = {
        "q": query,
        "lang": "en",
        "country": "in",
        "max": GNEWS_MAX_PER_REQUEST,
        "apikey": api_key,
    }

    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.get(GNEWS_BASE, params=params)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        if status == 401:
            logger.error("GNews auth failure (401) — check GNEWS_API_KEY environment variable")
            return [], quota, "auth failure 401"
        if status == 429:
            logger.warning("GNews rate limited (429) — marking quota as exhausted")
            exhausted = quota.model_copy(update={"calls_used": quota.daily_limit})
            return [], exhausted, "rate limited 429"
        logger.error("GNews HTTP error: %d for query=%r", status, query[:60])
        return [], quota, f"HTTP {status}"
    except Exception as exc:  # noqa: BLE001
        logger.error("GNews network error for query=%r: %s", query[:60], exc)
        return [], quota, str(exc)

    # Success
    data = response.json()
    raw_articles: list[dict] = data.get("articles", [])
    articles = [_normalise_article(a) for a in raw_articles]
    new_quota = quota.model_copy(update={"calls_used": quota.calls_used + 1})
    logger.info(
        "GNews: query=%r → %d articles (quota %d/%d)",
        query[:50],
        len(articles),
        new_quota.calls_used,
        new_quota.daily_limit,
    )
    return articles, new_quota, None


def fetch_all_gnews(
    queries: list[str],
    api_key: str,
    quota: GNewsQuota,
) -> tuple[list[Article], GNewsQuota, list[dict]]:
    """Fetch all queries, updating quota incrementally and stopping when exhausted.

    Returns:
        (all_articles, final_quota, health_results)

    Health result dicts have keys: query, status ("OK"/"FAIL"/"SKIP"), count, error.
    """
    all_articles: list[Article] = []
    health: list[dict] = []
    current_quota = quota

    for q in queries:
        if current_quota.calls_used >= current_quota.daily_limit:
            health.append(
                {"query": q[:50], "status": "SKIP", "count": 0, "error": "quota exhausted"}
            )
            continue

        articles, current_quota, error = fetch_gnews_query(q, api_key, current_quota)

        if error == "quota exhausted":
            health.append({"query": q[:50], "status": "SKIP", "count": 0, "error": error})
        elif error is not None:
            health.append({"query": q[:50], "status": "FAIL", "count": 0, "error": error})
        else:
            all_articles.extend(articles)
            health.append({"query": q[:50], "status": "OK", "count": len(articles), "error": None})

    return all_articles, current_quota, health
