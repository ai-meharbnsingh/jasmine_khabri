"""Breaking news alerting pipeline -- lightweight entrypoint for critical HIGH-priority stories.

Fires between scheduled deliveries (7 AM / 4 PM IST). Uses RSS-only fetch
(no GNews to preserve quota), keyword fast-path scoring (>= 80 threshold),
optional AI confirmation, and Telegram-only delivery.
"""

import logging
import os
from datetime import UTC, datetime, timedelta, timezone

from pipeline.analyzers.classifier import classify_articles
from pipeline.deliverers.telegram_sender import _escape_html, send_telegram_message
from pipeline.fetchers.rss_fetcher import fetch_all_rss
from pipeline.filters.dedup_filter import filter_duplicates
from pipeline.filters.relevance_filter import score_article
from pipeline.schemas.ai_cost_schema import AICost
from pipeline.schemas.article_schema import Article
from pipeline.schemas.bot_state_schema import BotState
from pipeline.schemas.keywords_schema import KeywordsConfig
from pipeline.utils.loader import (
    load_ai_cost,
    load_bot_state,
    load_config,
    load_keywords,
    load_pipeline_status,
    load_seen,
    save_ai_cost,
    save_pipeline_status,
    save_seen,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)

logger = logging.getLogger(__name__)

# IST timezone offset (UTC+5:30)
_IST = timezone(timedelta(hours=5, minutes=30))

# Keyword score threshold for breaking news fast-path
_BREAKING_HIGH_THRESHOLD = 80

# Reserve $2 for scheduled runs — only use AI for breaking if under $3
_BREAKING_AI_BUDGET_RESERVE = 3.00


def format_breaking_alert(articles: list[Article]) -> str:
    """Format breaking news articles for Telegram HTML delivery.

    Layout:
        siren BREAKING NEWS ALERT (N stories)
        ────────────────────────
        1. <b>Title</b>
           <i>Source</i>
           [Summary]
           <a href="url">Read</a>
        ────────────────────────
        Full brief in next scheduled delivery

    Args:
        articles: HIGH-priority articles to format.

    Returns:
        Telegram HTML formatted string.
    """
    lines: list[str] = []

    # Header
    lines.append(
        f"\U0001f6a8 <b>BREAKING NEWS ALERT</b> ({len(articles)} "
        f"{'story' if len(articles) == 1 else 'stories'})"
    )
    lines.append("\u2500" * 24)

    # Articles
    for i, article in enumerate(articles, start=1):
        lines.append(f"{i}. <b>{_escape_html(article.title)}</b>")
        lines.append(f"   <i>{_escape_html(article.source)}</i>")
        if article.summary:
            lines.append(f"   {_escape_html(article.summary)}")
        lines.append(f'   <a href="{_escape_html(article.url)}">Read</a>')
        lines.append("")  # blank line between articles

    # Footer
    lines.append("\u2500" * 24)
    lines.append("Full brief in next scheduled delivery")

    return "\n".join(lines)


def breaking_filter(
    articles: list[Article],
    keywords: KeywordsConfig,
    ai_cost: AICost,
) -> tuple[list[Article], AICost]:
    """Two-stage breaking news filter: keyword fast-path + optional AI confirmation.

    Stage 1: Keyword scoring -- only articles with score >= 80 pass.
    Stage 2: AI confirmation -- only if budget allows (< $3.00).
             When budget exceeded, trust keyword score and set priority=HIGH.

    Args:
        articles: Candidate articles to filter.
        keywords: Keyword configuration for scoring.
        ai_cost: Current AI cost state.

    Returns:
        Tuple of (high_priority_articles, updated_ai_cost).
    """
    # Stage 1: Keyword fast-path
    candidates: list[Article] = []
    for article in articles:
        passes_exclusion, score = score_article(article, keywords)
        if not passes_exclusion:
            continue
        if score >= _BREAKING_HIGH_THRESHOLD:
            candidates.append(article.model_copy(update={"relevance_score": score}))

    if not candidates:
        return ([], ai_cost)

    logger.info(
        "Breaking filter stage 1: %d/%d articles scored >= %d",
        len(candidates),
        len(articles),
        _BREAKING_HIGH_THRESHOLD,
    )

    # Stage 2: AI confirmation or keyword trust
    if ai_cost.total_cost_usd < _BREAKING_AI_BUDGET_RESERVE:
        # Budget allows AI confirmation
        classified, ai_cost = classify_articles(candidates, ai_cost)
        high_articles = [a for a in classified if a.priority == "HIGH"]
    else:
        # Budget exceeded -- trust keyword score
        logger.info(
            "AI budget reserve exceeded ($%.2f >= $%.2f) -- trusting keyword score for breaking",
            ai_cost.total_cost_usd,
            _BREAKING_AI_BUDGET_RESERVE,
        )
        high_articles = [a.model_copy(update={"priority": "HIGH"}) for a in candidates]

    logger.info(
        "Breaking filter stage 2: %d HIGH articles after AI gate",
        len(high_articles),
    )

    return (high_articles, ai_cost)


def _is_delivery_window(now_ist: datetime) -> bool:
    """Check if current IST time is within 30 minutes of a scheduled delivery.

    Delivery windows: 7:00 AM IST and 4:00 PM IST.
    Returns True if now_ist is within 30 minutes before or after either window.

    Args:
        now_ist: Current time in IST timezone.

    Returns:
        True if within a delivery window, False otherwise.
    """
    # Convert to minutes since midnight for easier comparison
    minutes = now_ist.hour * 60 + now_ist.minute

    # Morning delivery: 7:00 AM = 420 minutes
    morning = 7 * 60  # 420
    if abs(minutes - morning) <= 30:
        return True

    # Evening delivery: 4:00 PM = 960 minutes
    evening = 16 * 60  # 960
    if abs(minutes - evening) <= 30:
        return True

    return False


def _is_paused(bot_state: BotState) -> bool:
    """Check if breaking news is paused based on bot state.

    Pause is active when:
    - paused_slots is non-empty (any slot present)
    - AND either paused_until is empty (indefinite) or paused_until is in the future

    Args:
        bot_state: Current bot state.

    Returns:
        True if breaking is paused, False otherwise.
    """
    pause = bot_state.pause

    if not pause.paused_slots:
        return False

    # If paused_until is empty, it's an indefinite pause
    if not pause.paused_until:
        return True

    # Check if pause has expired
    try:
        paused_until = datetime.fromisoformat(pause.paused_until)
        # Ensure timezone-aware comparison
        if paused_until.tzinfo is None:
            paused_until = paused_until.replace(tzinfo=UTC)
        return datetime.now(UTC) < paused_until
    except (ValueError, TypeError):
        # Invalid date format -- treat as not paused
        return False


def _save_breaking_status(alerts_sent: int = 0) -> None:
    """Load previous pipeline status and save with incremented breaking counters.

    Args:
        alerts_sent: Number of breaking alerts sent in this run.
    """
    prev_status = load_pipeline_status("data/pipeline_status.json")
    updated = prev_status.model_copy(
        update={
            "monthly_breaking_runs": prev_status.monthly_breaking_runs + 1,
            "monthly_breaking_alerts": prev_status.monthly_breaking_alerts + alerts_sent,
            "est_actions_minutes": prev_status.est_actions_minutes + 1.5,
            "usage_month": datetime.now(UTC).strftime("%Y-%m"),
        }
    )
    save_pipeline_status(updated, "data/pipeline_status.json")


def run_breaking() -> None:
    """Run the breaking news alerting pipeline.

    Lightweight entrypoint that:
    1. Checks guards (breaking enabled, pause, delivery window)
    2. Fetches RSS only (no GNews)
    3. Applies keyword fast-path (score >= 80)
    4. Deduplicates against seen.json
    5. Optionally AI-confirms (budget permitting)
    6. Formats and sends Telegram alerts
    7. Saves state (seen.json, ai_cost.json)
    """
    logger.info("=== Breaking news check START ===")

    # Load config and check breaking enabled
    config = load_config("data/config.yaml")
    if not config.telegram.breaking_news_enabled:
        logger.info("Breaking news disabled in config -- skipping")
        return

    # Check pause guard
    bot_state = load_bot_state("data/bot_state.json")
    if _is_paused(bot_state):
        logger.info("Bot is paused -- skipping breaking news check")
        return

    # Check delivery window guard
    now_ist = datetime.now(tz=_IST)
    if _is_delivery_window(now_ist):
        logger.info(
            "Within delivery window (%s IST) -- skipping breaking news check",
            now_ist.strftime("%H:%M"),
        )
        return

    # Fetch RSS only (no GNews -- preserve quota for scheduled runs)
    rss_articles_raw, _ = fetch_all_rss(config.rss_feeds)

    # Filter to articles published within the last 24 hours
    cutoff = (datetime.now(UTC) - timedelta(hours=24)).isoformat()
    rss_articles = [a for a in rss_articles_raw if a.published_at >= cutoff]
    logger.info(
        "Breaking: fetched %d RSS articles, %d within 24h",
        len(rss_articles_raw),
        len(rss_articles),
    )

    if not rss_articles:
        logger.info("No RSS articles fetched -- nothing to check")
        _save_breaking_status(alerts_sent=0)
        return

    # Keyword fast-path: score each article, keep only >= 80
    keywords = load_keywords("data/keywords.yaml")
    candidates: list[Article] = []
    for article in rss_articles:
        passes_exclusion, score = score_article(article, keywords)
        if passes_exclusion and score >= _BREAKING_HIGH_THRESHOLD:
            candidates.append(article.model_copy(update={"relevance_score": score}))

    if not candidates:
        logger.info("No articles scored >= %d -- no breaking alert", _BREAKING_HIGH_THRESHOLD)
        _save_breaking_status(alerts_sent=0)
        return

    logger.info("Breaking: %d candidates scored >= %d", len(candidates), _BREAKING_HIGH_THRESHOLD)

    # Deduplicate against seen.json
    seen = load_seen("data/seen.json")
    deduped, seen = filter_duplicates(candidates, seen)

    # Keep only NEW articles (not UPDATEs)
    new_articles = [a for a in deduped if a.dedup_status == "NEW"]

    if not new_articles:
        logger.info("No new articles after dedup -- saving seen and returning")
        save_seen(seen, "data/seen.json")
        _save_breaking_status(alerts_sent=0)
        return

    logger.info("Breaking: %d new articles after dedup", len(new_articles))

    # AI gate: confirm HIGH priority (or trust keyword if budget exceeded)
    ai_cost = load_ai_cost("data/ai_cost.json")
    high_articles, ai_cost = breaking_filter(new_articles, keywords, ai_cost)

    if not high_articles:
        logger.info("No HIGH articles after AI gate -- saving state and returning")
        save_seen(seen, "data/seen.json")
        save_ai_cost(ai_cost, "data/ai_cost.json")
        _save_breaking_status(alerts_sent=0)
        return

    logger.info("Breaking: %d HIGH articles to alert", len(high_articles))

    # Format breaking alert
    alert_text = format_breaking_alert(high_articles)

    # Resolve Telegram credentials
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "") or config.telegram.bot_token
    chat_ids_env = os.environ.get("TELEGRAM_CHAT_IDS", "")
    if chat_ids_env:
        chat_ids = [cid.strip() for cid in chat_ids_env.split(",") if cid.strip()]
    else:
        chat_ids = list(config.telegram.chat_ids)

    if not token or not chat_ids:
        logger.warning("Telegram credentials missing -- cannot send breaking alert")
        save_seen(seen, "data/seen.json")
        save_ai_cost(ai_cost, "data/ai_cost.json")
        _save_breaking_status(alerts_sent=0)
        return

    # Send to each chat ID
    success_count = 0
    for cid in chat_ids:
        ok, err = send_telegram_message(token, cid, alert_text)
        if ok:
            success_count += 1
        else:
            logger.warning("Failed to send breaking alert to chat_id=%s: %s", cid, err)

    logger.info(
        "Breaking alert sent to %d/%d users (%d articles)",
        success_count,
        len(chat_ids),
        len(high_articles),
    )

    # Save state
    save_seen(seen, "data/seen.json")
    save_ai_cost(ai_cost, "data/ai_cost.json")
    _save_breaking_status(alerts_sent=len(high_articles))

    logger.info("=== Breaking news check END ===")


if __name__ == "__main__":
    run_breaking()
