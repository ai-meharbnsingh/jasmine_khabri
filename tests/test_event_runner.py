"""Tests for event_runner — event scheduling execution logic.

TDD tests for:
- No active events exits early
- Events outside time window are skipped
- Events within window deliver news
- Interval is respected (won't deliver if too recent)
- Events auto-deactivate after date passes
- Event keyword matching in articles
- Format event update message
"""

from datetime import UTC, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from pipeline.event_runner import (
    _event_keyword_match,
    _is_event_in_window,
    _should_deliver,
    format_event_update,
    run_event_check,
)
from pipeline.schemas.article_schema import Article
from pipeline.schemas.bot_state_schema import BotState, EventSchedule

# IST timezone for test helpers
_IST = timezone(timedelta(hours=5, minutes=30))


def _make_article(title: str, summary: str = "", url: str = "https://example.com") -> Article:
    """Create a minimal Article for testing."""
    now = datetime.now(UTC).isoformat()
    return Article(
        title=title,
        url=url,
        source="TestSource",
        published_at=now,
        fetched_at=now,
        summary=summary,
    )


def _make_event(
    name: str = "Budget",
    date: str = "",
    start: str = "10:00",
    end: str = "15:00",
    interval: int = 30,
    active: bool = True,
    keywords: list[str] | None = None,
    last_delivered_at: str = "",
) -> EventSchedule:
    """Create an EventSchedule for testing."""
    if not date:
        date = datetime.now(_IST).strftime("%Y-%m-%d")
    return EventSchedule(
        name=name,
        date=date,
        interval_minutes=interval,
        start_time_ist=start,
        end_time_ist=end,
        active=active,
        keywords=keywords or [],
        last_delivered_at=last_delivered_at,
    )


class TestIsEventInWindow:
    """Tests for _is_event_in_window — time window checking."""

    def test_within_window(self):
        """Event is in window when current IST time is between start and end."""
        now_ist = datetime(2026, 3, 8, 12, 0, tzinfo=_IST)
        event = _make_event(start="10:00", end="15:00")
        assert _is_event_in_window(event, now_ist) is True

    def test_before_window(self):
        """Event is NOT in window when current time is before start."""
        now_ist = datetime(2026, 3, 8, 9, 0, tzinfo=_IST)
        event = _make_event(start="10:00", end="15:00")
        assert _is_event_in_window(event, now_ist) is False

    def test_after_window(self):
        """Event is NOT in window when current time is after end."""
        now_ist = datetime(2026, 3, 8, 16, 0, tzinfo=_IST)
        event = _make_event(start="10:00", end="15:00")
        assert _is_event_in_window(event, now_ist) is False

    def test_at_start_boundary(self):
        """Event IS in window at exact start time."""
        now_ist = datetime(2026, 3, 8, 10, 0, tzinfo=_IST)
        event = _make_event(start="10:00", end="15:00")
        assert _is_event_in_window(event, now_ist) is True

    def test_at_end_boundary(self):
        """Event IS in window at exact end time."""
        now_ist = datetime(2026, 3, 8, 15, 0, tzinfo=_IST)
        event = _make_event(start="10:00", end="15:00")
        assert _is_event_in_window(event, now_ist) is True

    def test_empty_start_defaults_to_all_day(self):
        """Empty start_time_ist means all day — always in window."""
        now_ist = datetime(2026, 3, 8, 5, 0, tzinfo=_IST)
        event = _make_event(start="", end="")
        assert _is_event_in_window(event, now_ist) is True


class TestShouldDeliver:
    """Tests for _should_deliver — interval respecting logic."""

    def test_never_delivered_should_deliver(self):
        """First delivery should always proceed."""
        event = _make_event(interval=30, last_delivered_at="")
        assert _should_deliver(event) is True

    def test_too_recent_should_not_deliver(self):
        """Should NOT deliver if last delivery was less than interval_minutes ago."""
        recent = (datetime.now(UTC) - timedelta(minutes=10)).isoformat()
        event = _make_event(interval=30, last_delivered_at=recent)
        assert _should_deliver(event) is False

    def test_enough_time_passed_should_deliver(self):
        """Should deliver if enough time has passed since last delivery."""
        old = (datetime.now(UTC) - timedelta(minutes=35)).isoformat()
        event = _make_event(interval=30, last_delivered_at=old)
        assert _should_deliver(event) is True

    def test_invalid_timestamp_should_deliver(self):
        """Should deliver if last_delivered_at is invalid (treat as never delivered)."""
        event = _make_event(interval=30, last_delivered_at="not-a-date")
        assert _should_deliver(event) is True


class TestEventKeywordMatch:
    """Tests for _event_keyword_match — article filtering by event keywords."""

    def test_matches_event_name_in_title(self):
        """Article title containing event name is a match."""
        article = _make_article("Union Budget 2026 highlights")
        assert _event_keyword_match(article, "Budget", []) is True

    def test_matches_event_name_in_summary(self):
        """Article summary containing event name is a match."""
        article = _make_article("Finance news", summary="Budget allocation increased")
        assert _event_keyword_match(article, "Budget", []) is True

    def test_no_match(self):
        """Article with no keyword match is filtered out."""
        article = _make_article("Cricket World Cup final")
        assert _event_keyword_match(article, "Budget", []) is False

    def test_matches_custom_keyword(self):
        """Article matching a custom keyword in the event's keyword list."""
        article = _make_article("Fiscal deficit target revised")
        assert (
            _event_keyword_match(article, "Budget", ["fiscal deficit", "finance minister"]) is True
        )

    def test_case_insensitive(self):
        """Matching is case-insensitive."""
        article = _make_article("BUDGET ANNOUNCEMENT TODAY")
        assert _event_keyword_match(article, "budget", []) is True


class TestFormatEventUpdate:
    """Tests for format_event_update — message formatting."""

    def test_format_single_article(self):
        """Single article produces correct HTML format."""
        articles = [_make_article("Budget tax changes")]
        msg = format_event_update("Budget", articles)
        assert "Budget" in msg
        assert "EVENT UPDATE" in msg
        assert "Budget tax changes" in msg

    def test_format_multiple_articles(self):
        """Multiple articles are numbered correctly."""
        articles = [
            _make_article("Budget tax changes"),
            _make_article("Budget infrastructure push"),
        ]
        msg = format_event_update("Budget", articles)
        assert "2 stories" in msg or "2 " in msg


class TestRunEventCheck:
    """Integration tests for run_event_check — full pipeline."""

    @patch("pipeline.event_runner.save_seen")
    @patch("pipeline.event_runner.send_telegram_message")
    @patch("pipeline.event_runner.filter_duplicates")
    @patch("pipeline.event_runner.fetch_all_rss")
    @patch("pipeline.event_runner.save_bot_state")
    @patch("pipeline.event_runner.load_seen")
    @patch("pipeline.event_runner.load_config")
    @patch("pipeline.event_runner.load_bot_state")
    def test_no_active_events_exits_early(
        self,
        mock_load_bot,
        mock_config,
        mock_seen,
        mock_save_bot,
        mock_fetch,
        mock_dedup,
        mock_send,
        mock_save_seen,
    ):
        """No active events → no fetch, no send."""
        mock_load_bot.return_value = BotState()  # empty events list
        run_event_check()
        mock_fetch.assert_not_called()
        mock_send.assert_not_called()

    @patch("pipeline.event_runner.save_seen")
    @patch("pipeline.event_runner.send_telegram_message")
    @patch("pipeline.event_runner.filter_duplicates")
    @patch("pipeline.event_runner.fetch_all_rss")
    @patch("pipeline.event_runner.save_bot_state")
    @patch("pipeline.event_runner.load_seen")
    @patch("pipeline.event_runner.load_config")
    @patch("pipeline.event_runner.load_bot_state")
    def test_inactive_event_skipped(
        self,
        mock_load_bot,
        mock_config,
        mock_seen,
        mock_save_bot,
        mock_fetch,
        mock_dedup,
        mock_send,
        mock_save_seen,
    ):
        """Inactive event (active=False) → no fetch, no send."""
        event = _make_event(active=False)
        mock_load_bot.return_value = BotState(events=[event])
        run_event_check()
        mock_fetch.assert_not_called()

    @patch("pipeline.event_runner.save_seen")
    @patch("pipeline.event_runner.send_telegram_message")
    @patch("pipeline.event_runner.filter_duplicates")
    @patch("pipeline.event_runner.fetch_all_rss")
    @patch("pipeline.event_runner.save_bot_state")
    @patch("pipeline.event_runner.load_seen")
    @patch("pipeline.event_runner.load_config")
    @patch("pipeline.event_runner.load_bot_state")
    def test_event_past_date_auto_deactivates(
        self,
        mock_load_bot,
        mock_config,
        mock_seen,
        mock_save_bot,
        mock_fetch,
        mock_dedup,
        mock_send,
        mock_save_seen,
    ):
        """Event with date in the past gets deactivated."""
        event = _make_event(date="2020-01-01")
        mock_load_bot.return_value = BotState(events=[event])
        mock_config.return_value = MagicMock()
        run_event_check()
        # save_bot_state should be called with the event deactivated
        mock_save_bot.assert_called_once()
        saved_state = mock_save_bot.call_args[0][0]
        assert saved_state.events[0].active is False

    @patch("pipeline.event_runner.datetime")
    @patch("pipeline.event_runner.save_seen")
    @patch("pipeline.event_runner.send_telegram_message")
    @patch("pipeline.event_runner.filter_duplicates")
    @patch("pipeline.event_runner.fetch_all_rss")
    @patch("pipeline.event_runner.save_bot_state")
    @patch("pipeline.event_runner.load_seen")
    @patch("pipeline.event_runner.load_config")
    @patch("pipeline.event_runner.load_bot_state")
    def test_event_in_window_delivers(
        self,
        mock_load_bot,
        mock_config,
        mock_seen,
        mock_save_bot,
        mock_fetch,
        mock_dedup,
        mock_send,
        mock_save_seen,
        mock_dt,
    ):
        """Active event within time window delivers matching articles."""
        # Fix time to 12:00 IST on today
        fixed_now_ist = datetime(2026, 3, 8, 12, 0, tzinfo=_IST)
        fixed_now_utc = datetime(2026, 3, 8, 6, 30, tzinfo=UTC)
        mock_dt.now.side_effect = lambda tz=None: fixed_now_utc if tz == UTC else fixed_now_ist
        mock_dt.fromisoformat = datetime.fromisoformat

        event = _make_event(
            date="2026-03-08", start="10:00", end="15:00", interval=30, last_delivered_at=""
        )
        mock_load_bot.return_value = BotState(events=[event])

        cfg = MagicMock()
        cfg.rss_feeds = []
        cfg.telegram.bot_token = "tok"
        cfg.telegram.chat_ids = ["123"]
        mock_config.return_value = cfg

        from pipeline.schemas.seen_schema import SeenStore

        mock_seen.return_value = SeenStore()

        # RSS returns articles matching event name
        matching = _make_article("Budget 2026 highlights", summary="Budget details")
        non_matching = _make_article("Cricket World Cup results")
        mock_fetch.return_value = ([matching, non_matching], [])
        # filter_duplicates marks articles as NEW
        matching_new = matching.model_copy(update={"dedup_status": "NEW"})
        non_matching_new = non_matching.model_copy(update={"dedup_status": "NEW"})
        mock_dedup.return_value = ([matching_new, non_matching_new], SeenStore())

        mock_send.return_value = (True, None)

        run_event_check()

        # Should have sent a message (only Budget-matching article)
        mock_send.assert_called()
        sent_text = mock_send.call_args[0][2]
        assert "Budget" in sent_text

    @patch("pipeline.event_runner.save_seen")
    @patch("pipeline.event_runner.send_telegram_message")
    @patch("pipeline.event_runner.filter_duplicates")
    @patch("pipeline.event_runner.fetch_all_rss")
    @patch("pipeline.event_runner.save_bot_state")
    @patch("pipeline.event_runner.load_seen")
    @patch("pipeline.event_runner.load_config")
    @patch("pipeline.event_runner.load_bot_state")
    def test_interval_not_met_skips_delivery(
        self,
        mock_load_bot,
        mock_config,
        mock_seen,
        mock_save_bot,
        mock_fetch,
        mock_dedup,
        mock_send,
        mock_save_seen,
    ):
        """Event that was delivered recently (within interval) is skipped."""
        recent = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
        event = _make_event(start="00:00", end="23:59", interval=30, last_delivered_at=recent)
        mock_load_bot.return_value = BotState(events=[event])
        run_event_check()
        mock_fetch.assert_not_called()
