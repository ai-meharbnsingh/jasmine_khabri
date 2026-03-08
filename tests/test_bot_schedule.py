"""Tests for schedule modification and event scheduling handlers.

TDD Phase 10 Plan 03 — tests for parse_ist_time, ist_to_utc_cron,
schedule_command, create_event_schedule.
Mocks GitHub API functions to avoid real API calls.
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

from pipeline.bot.schedule import (
    create_event_schedule,
    ist_to_utc_cron,
    parse_ist_time,
    schedule_command,
)


class TestParseIstTime:
    """Tests for parse_ist_time — AM/PM and 24h time parsing."""

    def test_parses_6_30_am(self):
        """parse_ist_time('6:30 AM') returns (6, 30)."""
        assert parse_ist_time("6:30 AM") == (6, 30)

    def test_parses_16_00(self):
        """parse_ist_time('16:00') returns (16, 0)."""
        assert parse_ist_time("16:00") == (16, 0)

    def test_parses_12_pm(self):
        """parse_ist_time('12 PM') returns (12, 0)."""
        assert parse_ist_time("12 PM") == (12, 0)

    def test_parses_12_am(self):
        """parse_ist_time('12 AM') returns (0, 0)."""
        assert parse_ist_time("12 AM") == (0, 0)

    def test_parses_garbage_returns_none(self):
        """parse_ist_time('garbage') returns None."""
        assert parse_ist_time("garbage") is None

    def test_parses_5_pm(self):
        """parse_ist_time('5 PM') returns (17, 0)."""
        assert parse_ist_time("5 PM") == (17, 0)

    def test_parses_lowercase_am(self):
        """parse_ist_time('7:00 am') works case-insensitive."""
        assert parse_ist_time("7:00 am") == (7, 0)

    def test_parses_1_am(self):
        """parse_ist_time('1 AM') returns (1, 0)."""
        assert parse_ist_time("1 AM") == (1, 0)

    def test_parses_empty_returns_none(self):
        """parse_ist_time('') returns None."""
        assert parse_ist_time("") is None

    def test_parses_11_30_pm(self):
        """parse_ist_time('11:30 PM') returns (23, 30)."""
        assert parse_ist_time("11:30 PM") == (23, 30)


class TestISTToUTC:
    """Tests for ist_to_utc_cron — IST to UTC conversion."""

    def test_7_00_ist_to_1_30_utc(self):
        """ist_to_utc_cron(7, 0) returns (1, 30)."""
        assert ist_to_utc_cron(7, 0) == (1, 30)

    def test_6_30_ist_to_1_00_utc(self):
        """ist_to_utc_cron(6, 30) returns (1, 0)."""
        assert ist_to_utc_cron(6, 30) == (1, 0)

    def test_0_30_ist_wraps_to_19_00_utc(self):
        """ist_to_utc_cron(0, 30) returns (19, 0) — day wrap."""
        assert ist_to_utc_cron(0, 30) == (19, 0)

    def test_5_30_ist_to_0_0_utc(self):
        """ist_to_utc_cron(5, 30) returns (0, 0) — exactly offset."""
        assert ist_to_utc_cron(5, 30) == (0, 0)

    def test_22_00_ist_to_16_30_utc(self):
        """ist_to_utc_cron(22, 0) returns (16, 30)."""
        assert ist_to_utc_cron(22, 0) == (16, 30)


class TestScheduleCommand:
    """Tests for /schedule command handler."""

    def _make_update_context(self, text="/schedule"):
        """Create mock Update and context for handler testing."""
        update = MagicMock()
        update.message = MagicMock()
        update.message.text = text
        update.message.reply_text = AsyncMock()
        context = MagicMock()
        return update, context

    def _make_bot_state_json(self, morning="", evening=""):
        """Create a minimal bot_state.json string."""
        return json.dumps(
            {
                "pause": {"paused_until": "", "paused_slots": []},
                "events": [],
                "custom_schedule": {
                    "morning_ist": morning,
                    "evening_ist": evening,
                },
            }
        )

    @patch("pipeline.bot.schedule.write_github_file", new_callable=AsyncMock)
    @patch(
        "pipeline.bot.schedule.read_github_file_with_sha",
        new_callable=AsyncMock,
    )
    def test_morning_schedule_update(self, mock_read, mock_write, monkeypatch):
        """schedule_command with '6:30 AM' updates morning_ist."""
        monkeypatch.setenv("GITHUB_PAT", "token")
        monkeypatch.setenv("GITHUB_OWNER", "owner")
        monkeypatch.setenv("GITHUB_REPO", "repo")
        mock_read.return_value = (self._make_bot_state_json(), "sha123")
        mock_write.return_value = True

        update, context = self._make_update_context("/schedule 6:30 AM")
        asyncio.run(schedule_command(update, context))

        mock_write.assert_called_once()
        written_json = json.loads(mock_write.call_args[1]["content"])
        assert written_json["custom_schedule"]["morning_ist"] == "06:30"
        reply = update.message.reply_text.call_args[0][0]
        assert "06:30" in reply

    @patch("pipeline.bot.schedule.write_github_file", new_callable=AsyncMock)
    @patch(
        "pipeline.bot.schedule.read_github_file_with_sha",
        new_callable=AsyncMock,
    )
    def test_evening_schedule_update(self, mock_read, mock_write, monkeypatch):
        """schedule_command with 'evening 5 PM' updates evening_ist."""
        monkeypatch.setenv("GITHUB_PAT", "token")
        monkeypatch.setenv("GITHUB_OWNER", "owner")
        monkeypatch.setenv("GITHUB_REPO", "repo")
        mock_read.return_value = (self._make_bot_state_json(), "sha123")
        mock_write.return_value = True

        update, context = self._make_update_context("/schedule evening 5 PM")
        asyncio.run(schedule_command(update, context))

        mock_write.assert_called_once()
        written_json = json.loads(mock_write.call_args[1]["content"])
        assert written_json["custom_schedule"]["evening_ist"] == "17:00"

    @patch(
        "pipeline.bot.schedule.read_github_file_with_sha",
        new_callable=AsyncMock,
    )
    def test_show_current_schedule(self, mock_read, monkeypatch):
        """schedule_command with no args shows current schedule."""
        monkeypatch.setenv("GITHUB_PAT", "token")
        monkeypatch.setenv("GITHUB_OWNER", "owner")
        monkeypatch.setenv("GITHUB_REPO", "repo")
        mock_read.return_value = (
            self._make_bot_state_json("07:00", "16:30"),
            "sha",
        )

        update, context = self._make_update_context("/schedule")
        asyncio.run(schedule_command(update, context))

        reply = update.message.reply_text.call_args[0][0]
        assert "07:00" in reply
        assert "16:30" in reply

    def test_parse_failure_reply(self, monkeypatch):
        """schedule_command with bad time shows parse error."""
        monkeypatch.setenv("GITHUB_PAT", "token")
        monkeypatch.setenv("GITHUB_OWNER", "owner")
        monkeypatch.setenv("GITHUB_REPO", "repo")

        update, context = self._make_update_context("/schedule garbage")
        asyncio.run(schedule_command(update, context))

        reply = update.message.reply_text.call_args[0][0]
        assert "Could not parse" in reply


class TestCreateEventSchedule:
    """Tests for create_event_schedule function."""

    @patch("pipeline.bot.schedule.write_github_file", new_callable=AsyncMock)
    @patch(
        "pipeline.bot.schedule.read_github_file_with_sha",
        new_callable=AsyncMock,
    )
    def test_creates_event_successfully(self, mock_read, mock_write):
        """create_event_schedule adds event to bot_state.json."""
        state_json = json.dumps(
            {
                "pause": {"paused_until": "", "paused_slots": []},
                "events": [],
                "custom_schedule": {"morning_ist": "", "evening_ist": ""},
            }
        )
        mock_read.return_value = (state_json, "sha123")
        mock_write.return_value = True

        result = asyncio.run(
            create_event_schedule(
                name="Budget",
                date="2026-02-01",
                interval_minutes=30,
                start_time_ist="10:00",
                end_time_ist="15:00",
                token="tok",
                owner="own",
                repo="rep",
            )
        )

        assert result is True
        written = json.loads(mock_write.call_args[1]["content"])
        assert len(written["events"]) == 1
        assert written["events"][0]["name"] == "Budget"

    @patch("pipeline.bot.schedule.write_github_file", new_callable=AsyncMock)
    @patch(
        "pipeline.bot.schedule.read_github_file_with_sha",
        new_callable=AsyncMock,
    )
    def test_invalid_params_returns_false(self, mock_read, mock_write):
        """create_event_schedule with empty name returns False."""
        result = asyncio.run(
            create_event_schedule(
                name="",
                date="2026-02-01",
                interval_minutes=30,
                start_time_ist="10:00",
                end_time_ist="15:00",
                token="tok",
                owner="own",
                repo="rep",
            )
        )

        assert result is False
        mock_read.assert_not_called()

    @patch("pipeline.bot.schedule.write_github_file", new_callable=AsyncMock)
    @patch(
        "pipeline.bot.schedule.read_github_file_with_sha",
        new_callable=AsyncMock,
    )
    def test_github_write_failure(self, mock_read, mock_write):
        """create_event_schedule returns False on GitHub write failure."""
        state_json = json.dumps(
            {
                "pause": {"paused_until": "", "paused_slots": []},
                "events": [],
                "custom_schedule": {"morning_ist": "", "evening_ist": ""},
            }
        )
        mock_read.return_value = (state_json, "sha123")
        mock_write.return_value = False

        result = asyncio.run(
            create_event_schedule(
                name="Budget",
                date="2026-02-01",
                interval_minutes=30,
                start_time_ist="10:00",
                end_time_ist="15:00",
                token="tok",
                owner="own",
                repo="rep",
            )
        )

        assert result is False
