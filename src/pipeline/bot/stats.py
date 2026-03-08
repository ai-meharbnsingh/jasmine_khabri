"""Stats aggregation and /stats command handler.

Computes 7-day delivery statistics from history.json and formats
a human-readable summary for the Telegram /stats command.
"""

import json
import logging
import os
from collections import Counter
from datetime import UTC, datetime, timedelta

from pipeline.bot.status import read_github_file
from pipeline.schemas.seen_schema import SeenStore

logger = logging.getLogger(__name__)


def compute_stats(history: SeenStore, days: int = 7) -> dict:
    """Aggregate delivery statistics from seen-store history.

    Args:
        history: SeenStore with article entries.
        days: Number of days to look back (default 7).

    Returns:
        Dict with total_articles, duplicates_prevented, by_date, top_sources, days_covered.
    """
    cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
    recent = [e for e in history.entries if e.seen_at >= cutoff]

    by_date: dict[str, int] = dict(Counter(e.seen_at[:10] for e in recent))
    by_source = Counter(e.source for e in recent)
    top_sources = by_source.most_common(5)

    unique_hashes = len({e.title_hash for e in recent})
    duplicates_prevented = len(recent) - unique_hashes

    return {
        "total_articles": len(recent),
        "duplicates_prevented": duplicates_prevented,
        "by_date": by_date,
        "top_sources": top_sources,
        "days_covered": days,
    }


def format_stats_message(stats: dict) -> str:
    """Format stats dict into a human-readable message.

    Args:
        stats: Output of compute_stats.

    Returns:
        Formatted multi-line string.
    """
    days = stats["days_covered"]

    if stats["total_articles"] == 0:
        return f"No delivery data for the last {days} days."

    lines = [
        f"Delivery Statistics (Last {days} Days)",
        "",
        f"Total articles processed: {stats['total_articles']}",
        f"Duplicates prevented: {stats['duplicates_prevented']}",
        "",
        "Articles by date:",
    ]

    for date_str in sorted(stats["by_date"]):
        count = stats["by_date"][date_str]
        lines.append(f"  {date_str}: {count}")

    lines.append("")
    lines.append("Top sources:")
    for source, count in stats["top_sources"]:
        lines.append(f"  {source}: {count}")

    return "\n".join(lines)


async def stats_command(update, context) -> None:  # noqa: ARG001
    """Handle /stats command -- reply with 7-day delivery statistics.

    Reads history.json from GitHub, aggregates stats, and replies.
    """
    token = os.environ.get("GITHUB_PAT", "")
    owner = os.environ.get("GITHUB_OWNER", "")
    repo = os.environ.get("GITHUB_REPO", "")

    if not token or not owner or not repo:
        await update.effective_message.reply_text("GitHub integration not configured.")
        return

    try:
        raw = await read_github_file("data/history.json", token, owner, repo)
        data = json.loads(raw)
        history = SeenStore(**data)
        stats = compute_stats(history)
        message = format_stats_message(stats)
        await update.effective_message.reply_text(message)
    except Exception:
        logger.warning("Failed to fetch delivery statistics", exc_info=True)
        await update.effective_message.reply_text(
            "Failed to fetch statistics. Please try again later."
        )
