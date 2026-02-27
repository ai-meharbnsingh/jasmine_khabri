"""Pipeline entrypoint — invoked by GitHub Actions via `uv run python -m pipeline.main`."""

import logging
import os
import sys
from datetime import UTC, datetime

from pipeline.fetchers.gnews_fetcher import (
    build_gnews_queries,
    fetch_all_gnews,
    load_or_reset_quota,
    save_quota,
)
from pipeline.fetchers.rss_fetcher import fetch_all_rss
from pipeline.utils.loader import load_config, load_keywords, load_seen, save_seen
from pipeline.utils.purge import purge_old_entries

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)

logger = logging.getLogger(__name__)


def run() -> None:
    """Run the Khabri news pipeline."""
    start = datetime.now(UTC)
    iso = start.strftime("%Y-%m-%dT%H:%M:%SZ")
    logger.info("=== Khabri pipeline START (%s) ===", iso)

    try:
        # Load state files
        seen = load_seen("data/seen.json")
        history = load_seen("data/history.json")

        # Purge entries older than 7 days
        seen = purge_old_entries(seen, days=7)
        history = purge_old_entries(history, days=7)

        # Save purged state back
        save_seen(seen, "data/seen.json")
        save_seen(history, "data/history.json")

        logger.info(
            "State loaded and purged: seen=%d entries, history=%d entries",
            len(seen.entries),
            len(history.entries),
        )

        # Phase 3: Fetch articles from RSS + GNews
        config = load_config("data/config.yaml")
        keywords = load_keywords("data/keywords.yaml")

        # RSS fetching
        rss_articles, rss_health = fetch_all_rss(config.rss_feeds)
        logger.info(
            "RSS fetch complete: %d articles from %d feeds",
            len(rss_articles),
            len(config.rss_feeds),
        )

        # GNews fetching
        gnews_api_key = os.environ.get("GNEWS_API_KEY", "")
        gnews_articles: list = []
        gnews_health: list = []
        if gnews_api_key:
            quota = load_or_reset_quota("data/gnews_quota.json")
            queries = build_gnews_queries(keywords)
            gnews_articles, quota, gnews_health = fetch_all_gnews(queries, gnews_api_key, quota)
            save_quota(quota, "data/gnews_quota.json")
            logger.info(
                "GNews fetch complete: %d articles from %d queries",
                len(gnews_articles),
                len(queries),
            )
        else:
            logger.warning("GNEWS_API_KEY not set — skipping GNews fetch")

        all_articles = rss_articles + gnews_articles
        logger.info(
            "Total articles fetched: %d (RSS: %d, GNews: %d)",
            len(all_articles),
            len(rss_articles),
            len(gnews_articles),
        )

        # Log fetch health summary
        logger.info("Fetch health summary:")
        for row in rss_health:
            logger.info(
                "  RSS  | %-30s | %-4s | %3d articles | %s",
                row["source"],
                row["status"],
                row["count"],
                row["error"] or "",
            )
        for row in gnews_health:
            logger.info(
                "  GNews| %-50s | %-4s | %3d articles | %s",
                row["query"],
                row["status"],
                row["count"],
                row["error"] or "",
            )

        # Phase 4-7: filter, classify, deliver (not yet implemented)
        logger.info("Pipeline phases 4-7: not yet implemented")
    except Exception:  # noqa: BLE001
        logger.exception("Pipeline encountered an unhandled error")
        sys.exit(1)
    finally:
        end = datetime.now(UTC)
        elapsed = (end - start).total_seconds()
        logger.info("=== Khabri pipeline END (%.1fs) ===", elapsed)


if __name__ == "__main__":
    run()
