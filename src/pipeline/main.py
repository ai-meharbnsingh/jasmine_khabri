"""Pipeline entrypoint — invoked by GitHub Actions via `uv run python -m pipeline.main`."""

import logging
import os
import sys
from datetime import UTC, datetime

from pipeline.analyzers.classifier import classify_articles
from pipeline.deliverers.email_sender import deliver_email
from pipeline.deliverers.telegram_sender import deliver_articles
from pipeline.fetchers.gnews_fetcher import (
    build_gnews_queries,
    fetch_all_gnews,
    load_or_reset_quota,
    save_quota,
)
from pipeline.fetchers.rss_fetcher import fetch_all_rss
from pipeline.filters.dedup_filter import filter_duplicates
from pipeline.filters.geo_filter import filter_by_geo_tier
from pipeline.filters.relevance_filter import filter_by_relevance
from pipeline.schemas import PipelineStatus
from pipeline.utils.loader import (
    load_ai_cost,
    load_config,
    load_keywords,
    load_pipeline_status,
    load_seen,
    save_ai_cost,
    save_pipeline_status,
    save_seen,
)
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
        # Load previous pipeline status for usage counter increments
        prev_status = load_pipeline_status("data/pipeline_status.json")

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

        # Phase 4: Filter and deduplicate
        relevant_articles = filter_by_relevance(all_articles, keywords)
        geo_filtered = filter_by_geo_tier(relevant_articles)
        deduped_articles, seen = filter_duplicates(geo_filtered, seen)

        # Save updated seen store (with new articles added by dedup filter)
        save_seen(seen, "data/seen.json")

        logger.info(
            "Filter pipeline: %d fetched -> %d relevant -> %d geo-passed -> %d after dedup",
            len(all_articles),
            len(relevant_articles),
            len(geo_filtered),
            len(deduped_articles),
        )

        # Phase 5: AI classification
        if not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("GOOGLE_API_KEY"):
            logger.warning(
                "Neither ANTHROPIC_API_KEY nor GOOGLE_API_KEY set "
                "-- AI classification will use fallback defaults"
            )

        ai_cost = load_ai_cost("data/ai_cost.json")
        classified_articles, ai_cost = classify_articles(deduped_articles, ai_cost)
        save_ai_cost(ai_cost, "data/ai_cost.json")

        logger.info(
            "AI classification complete: %d articles classified (cost: $%.4f this month, %d calls)",
            len(classified_articles),
            ai_cost.total_cost_usd,
            ai_cost.call_count,
        )

        # Phase 6: Telegram delivery
        delivered = deliver_articles(classified_articles, config)
        logger.info("Telegram delivery complete: %d successful sends", delivered)

        # Phase 7: Email delivery
        email_count = deliver_email(classified_articles, config)
        logger.info("Email delivery: %d emails sent", email_count)

        # Phase 8: Save pipeline status for bot /status command
        status = PipelineStatus(
            last_run_utc=start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            articles_fetched=len(all_articles),
            articles_delivered=delivered + email_count,
            telegram_success=delivered,
            telegram_failures=0,
            email_success=email_count,
            sources_active=len(config.rss_feeds) + (1 if gnews_api_key else 0),
            run_duration_seconds=round((datetime.now(UTC) - start).total_seconds(), 1),
            # Phase 11-02: Usage tracking — increment deliver run counter
            usage_month=datetime.now(UTC).strftime("%Y-%m"),
            monthly_deliver_runs=prev_status.monthly_deliver_runs + 1,
            monthly_breaking_runs=prev_status.monthly_breaking_runs,
            monthly_breaking_alerts=prev_status.monthly_breaking_alerts,
            est_actions_minutes=prev_status.est_actions_minutes + 3.0,
        )
        save_pipeline_status(status, "data/pipeline_status.json")
        logger.info(
            "Pipeline status saved: %d fetched, %d delivered",
            status.articles_fetched,
            status.articles_delivered,
        )
    except Exception:  # noqa: BLE001
        logger.exception("Pipeline encountered an unhandled error")
        sys.exit(1)
    finally:
        end = datetime.now(UTC)
        elapsed = (end - start).total_seconds()
        logger.info("=== Khabri pipeline END (%.1fs) ===", elapsed)


if __name__ == "__main__":
    run()
