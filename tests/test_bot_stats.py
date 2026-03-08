"""Tests for /stats command handler and stats aggregation."""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

from pipeline.bot.stats import compute_stats, format_stats_message, stats_command
from pipeline.schemas.seen_schema import SeenEntry, SeenStore


def _entry(source: str, title: str, days_ago: int = 0, title_hash: str | None = None) -> SeenEntry:
    """Helper to create a SeenEntry with a seen_at relative to now."""
    seen_at = (datetime.now(UTC) - timedelta(days=days_ago)).isoformat()
    return SeenEntry(
        url_hash=f"url_{title}",
        title_hash=title_hash or f"hash_{title}",
        seen_at=seen_at,
        source=source,
        title=title,
    )


class TestComputeStats:
    """Tests for compute_stats aggregation."""

    def test_normal_case_counts_and_sources(self):
        entries = [
            _entry("Times of India", "Article 1", days_ago=0),
            _entry("Times of India", "Article 2", days_ago=0),
            _entry("Hindu", "Article 3", days_ago=1),
            _entry("Hindu", "Article 4", days_ago=1),
            _entry("Hindu", "Article 5", days_ago=1),
            _entry("ET Infra", "Article 6", days_ago=2),
            _entry("ET Infra", "Article 7", days_ago=2),
            _entry("Mint", "Article 8", days_ago=2),
            _entry("Reuters", "Article 9", days_ago=3),
            _entry("Reuters", "Article 10", days_ago=3),
        ]
        store = SeenStore(entries=entries)
        stats = compute_stats(store)

        assert stats["total_articles"] == 10
        assert len(stats["by_date"]) == 4  # 4 distinct days
        assert stats["top_sources"][0][0] == "Hindu"  # 3 articles
        assert stats["top_sources"][0][1] == 3
        assert len(stats["top_sources"]) == 5
        assert stats["days_covered"] == 7

    def test_old_entries_excluded(self):
        entries = [
            _entry("Source A", "Recent", days_ago=1),
            _entry("Source B", "Old", days_ago=10),
        ]
        store = SeenStore(entries=entries)
        stats = compute_stats(store)

        assert stats["total_articles"] == 1

    def test_duplicates_counted(self):
        entries = [
            _entry("S1", "A", days_ago=0, title_hash="same_hash"),
            _entry("S2", "B", days_ago=0, title_hash="same_hash"),
            _entry("S3", "C", days_ago=0, title_hash="unique_hash"),
        ]
        store = SeenStore(entries=entries)
        stats = compute_stats(store)

        assert stats["total_articles"] == 3
        assert stats["duplicates_prevented"] == 1  # 3 total - 2 unique = 1

    def test_empty_history(self):
        store = SeenStore(entries=[])
        stats = compute_stats(store)

        assert stats["total_articles"] == 0
        assert stats["duplicates_prevented"] == 0
        assert stats["by_date"] == {}
        assert stats["top_sources"] == []

    def test_custom_days(self):
        entries = [
            _entry("S1", "Day0", days_ago=0),
            _entry("S2", "Day2", days_ago=2),
            _entry("S3", "Day5", days_ago=5),
        ]
        store = SeenStore(entries=entries)
        stats = compute_stats(store, days=3)

        assert stats["total_articles"] == 2  # Day0 and Day2 only
        assert stats["days_covered"] == 3


class TestFormatStatsMessage:
    """Tests for format_stats_message output."""

    def test_formatted_output_with_data(self):
        stats = {
            "total_articles": 10,
            "duplicates_prevented": 2,
            "by_date": {"2026-03-07": 5, "2026-03-06": 3, "2026-03-05": 2},
            "top_sources": [("Hindu", 4), ("TOI", 3), ("ET", 2), ("Mint", 1)],
            "days_covered": 7,
        }
        msg = format_stats_message(stats)

        assert "Delivery Statistics (Last 7 Days)" in msg
        assert "Total articles processed: 10" in msg
        assert "Duplicates prevented: 2" in msg
        assert "2026-03-05" in msg
        assert "2026-03-07" in msg
        assert "Hindu" in msg

    def test_empty_data_message(self):
        stats = {
            "total_articles": 0,
            "duplicates_prevented": 0,
            "by_date": {},
            "top_sources": [],
            "days_covered": 7,
        }
        msg = format_stats_message(stats)

        assert "No delivery data" in msg


class TestStatsCommand:
    """Tests for stats_command handler."""

    def _make_update(self):
        update = AsyncMock()
        update.effective_message = AsyncMock()
        update.effective_message.reply_text = AsyncMock()
        return update

    def test_successful_fetch(self):
        import asyncio

        update = self._make_update()
        context = AsyncMock()
        history_data = {
            "entries": [
                {
                    "url_hash": "u1",
                    "title_hash": "h1",
                    "seen_at": datetime.now(UTC).isoformat(),
                    "source": "Hindu",
                    "title": "Test Article",
                }
            ]
        }

        with patch(
            "pipeline.bot.stats.read_github_file",
            new_callable=AsyncMock,
            return_value=json.dumps(history_data),
        ):
            with patch.dict(
                "os.environ",
                {"GITHUB_PAT": "tok", "GITHUB_OWNER": "own", "GITHUB_REPO": "rep"},
            ):
                asyncio.run(stats_command(update, context))

        reply_text = update.effective_message.reply_text.call_args[0][0]
        assert "Delivery Statistics" in reply_text

    def test_github_failure(self):
        import asyncio

        update = self._make_update()
        context = AsyncMock()

        with patch(
            "pipeline.bot.stats.read_github_file",
            new_callable=AsyncMock,
            side_effect=Exception("API Error"),
        ):
            with patch.dict(
                "os.environ",
                {"GITHUB_PAT": "tok", "GITHUB_OWNER": "own", "GITHUB_REPO": "rep"},
            ):
                asyncio.run(stats_command(update, context))

        reply_text = update.effective_message.reply_text.call_args[0][0]
        assert "Failed to fetch statistics" in reply_text

    def test_missing_env_vars(self):
        import asyncio

        update = self._make_update()
        context = AsyncMock()

        with patch.dict("os.environ", {}, clear=True):
            asyncio.run(stats_command(update, context))

        reply_text = update.effective_message.reply_text.call_args[0][0]
        assert "not configured" in reply_text

    def test_empty_history(self):
        import asyncio

        update = self._make_update()
        context = AsyncMock()
        history_data = {"entries": []}

        with patch(
            "pipeline.bot.stats.read_github_file",
            new_callable=AsyncMock,
            return_value=json.dumps(history_data),
        ):
            with patch.dict(
                "os.environ",
                {"GITHUB_PAT": "tok", "GITHUB_OWNER": "own", "GITHUB_REPO": "rep"},
            ):
                asyncio.run(stats_command(update, context))

        reply_text = update.effective_message.reply_text.call_args[0][0]
        assert "No delivery data" in reply_text
