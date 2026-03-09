"""RSS feed fetcher using httpx + feedparser fetch-then-parse pattern.

Pattern: httpx fetches raw bytes, feedparser.parse() parses content.
Never use feedparser URL mode (bypasses httpx timeout and redirect handling).
"""

import calendar
import logging
import re
import time
from datetime import UTC, datetime

import feedparser
import httpx

from pipeline.schemas.article_schema import Article
from pipeline.schemas.config_schema import RssFeedConfig

logger = logging.getLogger(__name__)


def _struct_time_to_iso(st: time.struct_time | None) -> str | None:
    """Convert feedparser's UTC struct_time to ISO 8601 UTC string.

    Uses calendar.timegm() (UTC-aware), NOT time.mktime() (local timezone).
    Returns None if st is None or conversion fails.
    """
    if st is None:
        return None
    try:
        timestamp = calendar.timegm(st)
        return datetime.fromtimestamp(timestamp, tz=UTC).isoformat()
    except (OSError, OverflowError, ValueError):
        return None


def fetch_rss_feed(
    url: str,
    source_name: str,
    timeout: float = 10.0,
) -> tuple[list[Article], str | None]:
    """Fetch and parse a single RSS feed.

    Uses fetch-then-parse pattern: httpx fetches raw bytes, feedparser parses content.
    Never passes URL directly to feedparser (no timeout/redirect control).

    Returns:
        (articles, None) on success
        ([], error_string) on any failure
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; KhabriBot/1.0; "
            "+https://github.com/ai-meharbnsingh/jasmine_khabri)"
        ),
        "Accept": "application/rss+xml, application/xml, text/xml, */*",
    }

    try:
        with httpx.Client(timeout=timeout, headers=headers) as client:
            response = client.get(url, follow_redirects=True)
            response.raise_for_status()

        feed = feedparser.parse(response.content)

        if feed.bozo:
            logger.warning(
                "Bozo feed from %s: %s — %d entries found, continuing",
                source_name,
                feed.bozo_exception,
                len(feed.entries),
            )

        now_iso = datetime.now(tz=UTC).isoformat()
        articles: list[Article] = []

        for entry in feed.entries:
            link = entry.get("link", "")
            if not link:
                logger.debug("Skipping entry with no link in feed %s", source_name)
                continue

            title = entry.get("title", "").strip()
            published_at = _struct_time_to_iso(entry.get("published_parsed")) or now_iso

            # Extract description/summary from RSS entry for relevance scoring.
            # feedparser exposes the <description> tag as entry.get("summary")
            # and the <content:encoded> tag as entry.get("content").
            raw_desc = entry.get("summary") or entry.get("description") or ""
            # Strip HTML tags for clean text matching
            clean_desc = re.sub(r"<[^>]+>", " ", raw_desc).strip()

            articles.append(
                Article(
                    title=title,
                    url=link,
                    source=source_name,
                    published_at=published_at,
                    summary=clean_desc[:500],  # Cap at 500 chars for relevance scoring
                    fetched_at=now_iso,
                )
            )

        return articles, None

    except httpx.TimeoutException as exc:
        error = f"timeout fetching {source_name}: {exc}"
        logger.warning(error)
        return [], error

    except httpx.HTTPStatusError as exc:
        error = f"HTTP {exc.response.status_code} fetching {source_name}: {exc}"
        logger.warning(error)
        return [], error

    except httpx.RequestError as exc:
        error = f"network error fetching {source_name}: {exc}"
        logger.warning(error)
        return [], error

    except Exception as exc:  # noqa: BLE001
        error = f"unexpected error fetching {source_name}: {exc}"
        logger.error(error)
        return [], error


def fetch_all_rss(
    feeds: list[RssFeedConfig],
) -> tuple[list[Article], list[dict]]:
    """Fetch all enabled RSS feeds with per-feed error isolation.

    Skips disabled feeds. One feed failure does not abort others.
    Logs a health summary table at the end.

    Returns:
        (all_articles, health_results)
        health_results: list of dicts with keys source, status, count, error
    """
    all_articles: list[Article] = []
    health_results: list[dict] = []

    enabled_feeds = [f for f in feeds if f.enabled]

    for feed_cfg in enabled_feeds:
        articles, error = fetch_rss_feed(feed_cfg.url, feed_cfg.name)
        all_articles.extend(articles)
        health_results.append(
            {
                "source": feed_cfg.name,
                "status": "OK" if error is None else "FAIL",
                "count": len(articles),
                "error": error,
            }
        )

    # Log health summary table
    logger.info("RSS fetch health summary:")
    for row in health_results:
        logger.info(
            "  %-30s | %-4s | %3d articles | %s",
            row["source"],
            row["status"],
            row["count"],
            row["error"] or "",
        )

    return all_articles, health_results
