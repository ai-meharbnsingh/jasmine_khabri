"""Event scheduling execution — checks active events and delivers event-specific news.

Runs via GitHub Actions (event_check.yml, every 15 min). For each active event
whose date matches today and current IST time is within the event's time window,
fetches RSS articles matching event keywords and delivers via Telegram.
"""

import logging
import os
import sys
from datetime import UTC, datetime, timedelta, timezone

from pipeline.deliverers.telegram_sender import _escape_html, send_telegram_message
from pipeline.fetchers.rss_fetcher import fetch_all_rss
from pipeline.filters.dedup_filter import filter_duplicates
from pipeline.schemas.article_schema import Article
from pipeline.schemas.bot_state_schema import EventSchedule
from pipeline.utils.loader import (
    load_bot_state,
    load_config,
    load_seen,
    save_bot_state,
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


def _is_event_in_window(event: EventSchedule, now_ist: datetime) -> bool:
    """Check if current IST time is within the event's start/end window.

    If start_time_ist or end_time_ist are empty, treat as all-day event.

    Args:
        event: The event schedule to check.
        now_ist: Current time in IST.

    Returns:
        True if within window (inclusive of boundaries).
    """
    if not event.start_time_ist or not event.end_time_ist:
        return True

    now_minutes = now_ist.hour * 60 + now_ist.minute

    try:
        start_parts = event.start_time_ist.split(":")
        start_minutes = int(start_parts[0]) * 60 + int(start_parts[1])
    except (ValueError, IndexError):
        return True  # Can't parse → treat as all-day

    try:
        end_parts = event.end_time_ist.split(":")
        end_minutes = int(end_parts[0]) * 60 + int(end_parts[1])
    except (ValueError, IndexError):
        return True

    return start_minutes <= now_minutes <= end_minutes


def _should_deliver(event: EventSchedule) -> bool:
    """Check if enough time has passed since last delivery.

    Args:
        event: Event with last_delivered_at and interval_minutes.

    Returns:
        True if ready for next delivery.
    """
    if not event.last_delivered_at:
        return True

    try:
        last = datetime.fromisoformat(event.last_delivered_at)
        if last.tzinfo is None:
            last = last.replace(tzinfo=UTC)
        elapsed = datetime.now(UTC) - last
        return elapsed >= timedelta(minutes=event.interval_minutes)
    except (ValueError, TypeError):
        return True  # Invalid timestamp → treat as never delivered


def _event_keyword_match(article: Article, event_name: str, keywords: list[str]) -> bool:
    """Check if an article matches the event's keywords.

    Matches event name and any custom keywords against article title + summary.
    Case-insensitive.

    Args:
        article: Article to check.
        event_name: Name of the event (always used as a keyword).
        keywords: Additional custom keywords for the event.

    Returns:
        True if any keyword matches.
    """
    text = (article.title + " " + (article.summary or "")).lower()
    all_keywords = [event_name.lower()] + [k.lower() for k in keywords]
    return any(kw in text for kw in all_keywords)


def format_event_update(event_name: str, articles: list[Article]) -> str:
    """Format event-specific news articles for Telegram HTML delivery.

    Args:
        event_name: Name of the event.
        articles: Matching articles to format.

    Returns:
        Telegram HTML formatted string.
    """
    lines: list[str] = []

    lines.append(
        f"\U0001f4e2 <b>EVENT UPDATE: {_escape_html(event_name)}</b> "
        f"({len(articles)} {'story' if len(articles) == 1 else 'stories'})"
    )
    lines.append("\u2500" * 24)

    for i, article in enumerate(articles, start=1):
        lines.append(f"{i}. <b>{_escape_html(article.title)}</b>")
        lines.append(f"   <i>{_escape_html(article.source)}</i>")
        if article.summary:
            lines.append(f"   {_escape_html(article.summary)}")
        lines.append(f'   <a href="{_escape_html(article.url)}">Read</a>')
        lines.append("")

    lines.append("\u2500" * 24)
    lines.append(f"Tracking: {_escape_html(event_name)}")

    return "\n".join(lines)


def run_event_check() -> None:
    """Run the event scheduling check pipeline.

    1. Load bot_state.json → get events
    2. Auto-deactivate past events
    3. For each active event in time window with interval met:
       - Fetch RSS, filter by event keywords, dedup, deliver
    4. Update last_delivered_at and save state
    """
    logger.info("=== Event check START ===")

    try:
        _run_event_check_inner()
    except Exception:
        logger.exception("Event check encountered an unhandled error")
        sys.exit(1)
    finally:
        logger.info("=== Event check END ===")


def _run_event_check_inner() -> None:
    """Inner logic for run_event_check."""
    bot_state = load_bot_state("data/bot_state.json")

    if not bot_state.events:
        logger.info("No events configured — nothing to check")
        return

    # Check if any events are active
    active_events = [e for e in bot_state.events if e.active]
    if not active_events:
        logger.info("No active events — nothing to check")
        return

    now_ist = datetime.now(tz=_IST)
    today_str = now_ist.strftime("%Y-%m-%d")
    state_changed = False
    events_to_process: list[tuple[int, EventSchedule]] = []

    # Phase 1: Auto-deactivate past events, identify processable events
    for idx, event in enumerate(bot_state.events):
        if not event.active:
            continue

        # Auto-deactivate if event date has passed
        if event.date < today_str:
            logger.info("Auto-deactivating past event: %s (date=%s)", event.name, event.date)
            bot_state.events[idx] = event.model_copy(update={"active": False})
            state_changed = True
            continue

        # Skip if date doesn't match today
        if event.date != today_str:
            logger.info(
                "Event '%s' is for %s, not today (%s) — skipping", event.name, event.date, today_str
            )
            continue

        # Check time window
        if not _is_event_in_window(event, now_ist):
            logger.info(
                "Event '%s' outside time window (%s-%s, now %s) — skipping",
                event.name,
                event.start_time_ist,
                event.end_time_ist,
                now_ist.strftime("%H:%M"),
            )
            continue

        # Check delivery interval
        if not _should_deliver(event):
            logger.info(
                "Event '%s' delivered too recently (interval=%dmin) — skipping",
                event.name,
                event.interval_minutes,
            )
            continue

        events_to_process.append((idx, event))

    # Save deactivation changes even if no events to process
    if state_changed and not events_to_process:
        save_bot_state(bot_state, "data/bot_state.json")
        return

    if not events_to_process:
        logger.info("No events ready for delivery right now")
        return

    # Phase 2: Fetch articles (shared across all events this run)
    config = load_config("data/config.yaml")
    rss_articles_raw, _ = fetch_all_rss(config.rss_feeds)

    # Filter to last 24h
    cutoff = (datetime.now(UTC) - timedelta(hours=24)).isoformat()
    rss_articles = [a for a in rss_articles_raw if a.published_at >= cutoff]
    logger.info(
        "Event check: %d RSS articles, %d within 24h", len(rss_articles_raw), len(rss_articles)
    )

    if not rss_articles:
        logger.info("No recent articles — saving state and returning")
        if state_changed:
            save_bot_state(bot_state, "data/bot_state.json")
        return

    # Dedup against seen.json
    seen = load_seen("data/seen.json")
    deduped, seen = filter_duplicates(rss_articles, seen)
    new_articles = [a for a in deduped if a.dedup_status == "NEW"]

    # Resolve Telegram credentials
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "") or config.telegram.bot_token
    chat_ids_env = os.environ.get("TELEGRAM_CHAT_IDS", "")
    if chat_ids_env:
        chat_ids = [cid.strip() for cid in chat_ids_env.split(",") if cid.strip()]
    else:
        chat_ids = list(config.telegram.chat_ids)

    # Phase 3: Process each event
    for idx, event in events_to_process:
        # Filter articles by event keywords
        matching = [a for a in new_articles if _event_keyword_match(a, event.name, event.keywords)]

        if not matching:
            logger.info("Event '%s': no matching articles", event.name)
            continue

        logger.info("Event '%s': %d matching articles", event.name, len(matching))

        # Format and send
        alert_text = format_event_update(event.name, matching)

        if not token or not chat_ids:
            logger.warning("Telegram credentials missing — cannot send event update")
            continue

        for cid in chat_ids:
            ok, err = send_telegram_message(token, cid, alert_text)
            if ok:
                logger.info("Event '%s' update sent to chat_id=%s", event.name, cid)
            else:
                logger.warning("Failed to send event '%s' to chat_id=%s: %s", event.name, cid, err)

        # Update last_delivered_at
        bot_state.events[idx] = event.model_copy(
            update={"last_delivered_at": datetime.now(UTC).isoformat()}
        )
        state_changed = True

    # Save all state
    save_seen(seen, "data/seen.json")
    if state_changed:
        save_bot_state(bot_state, "data/bot_state.json")


if __name__ == "__main__":
    run_event_check()
