"""Priority-based article selector for delivery.

Allocates articles to HIGH/MEDIUM/LOW buckets for Telegram/Email delivery,
respecting a configurable max_stories cap (default 15).
"""

import logging

from pipeline.schemas.article_schema import Article

logger = logging.getLogger(__name__)

# Default tier caps
_HIGH_CAP = 8
_MEDIUM_MIN = 4
_LOW_MIN = 2


def select_articles(
    articles: list[Article],
    max_stories: int = 15,
) -> tuple[list[Article], list[Article], list[Article]]:
    """Select articles by priority tier, capped at max_stories total.

    Algorithm:
    1. Filter to only dedup_status="NEW" articles with a valid priority
    2. Separate into HIGH/MEDIUM/LOW buckets
    3. Take up to 8 HIGH
    4. Take all available MEDIUM
    5. Take all available LOW
    6. If total exceeds max_stories, trim from lowest priority first
    7. If total < max_stories and articles remain, backfill from surplus
    8. Return (high, medium, low) tuple

    Args:
        articles: All candidate articles (any dedup_status).
        max_stories: Maximum total articles to select (default 15).

    Returns:
        Tuple of (high, medium, low) article lists.
    """
    # Step 1: Filter to NEW articles with a valid priority
    new_articles = [
        a for a in articles if a.dedup_status == "NEW" and a.priority in ("HIGH", "MEDIUM", "LOW")
    ]

    if not new_articles:
        logger.info("No NEW articles to select")
        return [], [], []

    # Step 2: Separate into priority buckets
    all_high = [a for a in new_articles if a.priority == "HIGH"]
    all_medium = [a for a in new_articles if a.priority == "MEDIUM"]
    all_low = [a for a in new_articles if a.priority == "LOW"]

    # Step 3-5: Initial selection — take up to cap for HIGH, all for MED/LOW
    high = all_high[:_HIGH_CAP]
    medium = list(all_medium)
    low = list(all_low)

    total = len(high) + len(medium) + len(low)

    # Step 6: If over max, trim from lowest priority first
    if total > max_stories:
        excess = total - max_stories
        # Trim LOW first
        if len(low) > 0:
            trim_low = min(len(low), excess)
            low = low[: len(low) - trim_low]
            excess -= trim_low
        # Then trim MEDIUM
        if excess > 0 and len(medium) > 0:
            trim_med = min(len(medium), excess)
            medium = medium[: len(medium) - trim_med]
            excess -= trim_med
        # Then trim HIGH (unlikely but safe)
        if excess > 0 and len(high) > 0:
            trim_high = min(len(high), excess)
            high = high[: len(high) - trim_high]

    # Step 7: If under max, backfill from surplus (Medium, then Low, then High
    # beyond cap only as last resort — HIGH cap is a hard limit)
    total = len(high) + len(medium) + len(low)
    if total < max_stories:
        # Backfill from remaining MEDIUM first
        remaining_medium = all_medium[len(medium) :]
        if remaining_medium:
            backfill = min(len(remaining_medium), max_stories - total)
            medium = medium + remaining_medium[:backfill]
            total += backfill
    if total < max_stories:
        # Then from remaining LOW
        remaining_low = all_low[len(low) :]
        if remaining_low:
            backfill = min(len(remaining_low), max_stories - total)
            low = low + remaining_low[:backfill]
            total += backfill

    logger.info(
        "Selected %d articles: %d HIGH, %d MEDIUM, %d LOW (from %d NEW)",
        len(high) + len(medium) + len(low),
        len(high),
        len(medium),
        len(low),
        len(new_articles),
    )

    return high, medium, low
