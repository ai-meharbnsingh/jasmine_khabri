"""Tests for pause/resume — duration parsing, BotState schema, loader, and command handlers.

TDD Phase 10 Plan 01.
Task 1: Schema, loader, and duration parser tests.
Task 2: Pause/resume command handler tests.
"""

import asyncio
import json
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from pipeline.bot.pause import parse_duration, pause_command, resume_command
from pipeline.schemas.bot_state_schema import (
    BotState,
    CustomSchedule,
    EventSchedule,
    PauseState,
)
from pipeline.utils.loader import load_bot_state


class TestParseDuration:
    """Tests for parse_duration utility."""

    def test_parses_days(self):
        assert parse_duration("3 days") == timedelta(days=3)

    def test_parses_single_day(self):
        assert parse_duration("1 day") == timedelta(days=1)

    def test_parses_a_week(self):
        assert parse_duration("a week") == timedelta(weeks=1)

    def test_parses_two_hours(self):
        assert parse_duration("2 hours") == timedelta(hours=2)

    def test_parses_one_month(self):
        assert parse_duration("1 month") == timedelta(days=30)

    def test_parses_an_hour(self):
        assert parse_duration("an hour") == timedelta(hours=1)

    def test_parses_minutes(self):
        assert parse_duration("30 minutes") == timedelta(minutes=30)

    def test_returns_none_for_garbage(self):
        assert parse_duration("garbage") is None

    def test_returns_none_for_empty(self):
        assert parse_duration("") is None

    def test_case_insensitive(self):
        assert parse_duration("3 Days") == timedelta(days=3)


class TestBotStateSchema:
    """Tests for BotState Pydantic models."""

    def test_default_bot_state(self):
        state = BotState()
        assert state.pause.paused_until == ""
        assert state.pause.paused_slots == []
        assert state.events == []
        assert state.custom_schedule.morning_ist == ""
        assert state.custom_schedule.evening_ist == ""

    def test_pause_state_serializes(self):
        pause = PauseState(paused_until="2026-03-10T00:00:00Z", paused_slots=["all"])
        data = pause.model_dump()
        assert data["paused_until"] == "2026-03-10T00:00:00Z"
        assert data["paused_slots"] == ["all"]

    def test_pause_state_deserializes(self):
        data = {"paused_until": "2026-03-10T00:00:00Z", "paused_slots": ["all"]}
        pause = PauseState.model_validate(data)
        assert pause.paused_until == "2026-03-10T00:00:00Z"
        assert pause.paused_slots == ["all"]

    def test_model_copy_update_pause(self):
        state = BotState()
        new_pause = PauseState(paused_until="2026-04-01T00:00:00Z", paused_slots=["all"])
        updated = state.model_copy(update={"pause": new_pause})
        assert updated.pause.paused_until == "2026-04-01T00:00:00Z"
        assert state.pause.paused_until == ""  # original unchanged

    def test_event_schedule_defaults(self):
        evt = EventSchedule(name="election", date="2026-04-01")
        assert evt.interval_minutes == 30
        assert evt.active is True

    def test_custom_schedule_defaults(self):
        cs = CustomSchedule()
        assert cs.morning_ist == ""
        assert cs.evening_ist == ""


class TestLoadBotState:
    """Tests for load_bot_state loader function."""

    def test_loads_from_file(self, tmp_path):
        data = {
            "pause": {"paused_until": "2026-03-10T00:00:00Z", "paused_slots": ["all"]},
            "events": [],
            "custom_schedule": {"morning_ist": "", "evening_ist": ""},
        }
        p = tmp_path / "bot_state.json"
        p.write_text(json.dumps(data))
        state = load_bot_state(str(p))
        assert state.pause.paused_until == "2026-03-10T00:00:00Z"

    def test_returns_default_on_missing_file(self):
        state = load_bot_state("/nonexistent/bot_state.json")
        assert state.pause.paused_until == ""
        assert state.events == []

    def test_returns_default_on_empty_file(self, tmp_path):
        p = tmp_path / "bot_state.json"
        p.write_text("")
        state = load_bot_state(str(p))
        assert state.pause.paused_until == ""

    def test_returns_default_on_empty_values(self, tmp_path):
        data = {
            "pause": {"paused_until": "", "paused_slots": []},
            "events": [],
            "custom_schedule": {"morning_ist": "", "evening_ist": ""},
        }
        p = tmp_path / "bot_state.json"
        p.write_text(json.dumps(data))
        state = load_bot_state(str(p))
        assert state.pause.paused_until == ""
        assert state.events == []


# --- Helpers for handler tests ---

_DEFAULT_STATE_JSON = json.dumps(
    {
        "pause": {"paused_until": "", "paused_slots": []},
        "events": [],
        "custom_schedule": {"morning_ist": "", "evening_ist": ""},
    }
)

_PAUSED_STATE_JSON = json.dumps(
    {
        "pause": {"paused_until": "2026-03-11T00:00:00Z", "paused_slots": ["all"]},
        "events": [],
        "custom_schedule": {"morning_ist": "", "evening_ist": ""},
    }
)

_ENV = {
    "GITHUB_PAT": "fake-token",
    "GITHUB_OWNER": "test-owner",
    "GITHUB_REPO": "test-repo",
}


def _make_update(text: str) -> MagicMock:
    """Create a mock Telegram Update with message text."""
    update = MagicMock()
    update.message.text = text
    update.message.reply_text = AsyncMock()
    return update


class TestPauseCommand:
    """Tests for pause_command handler."""

    def test_pause_with_duration(self):
        """pause_command with '3 days' sets paused_until and writes to GitHub."""
        update = _make_update("/pause 3 days")
        ctx = MagicMock()

        with (
            patch.dict("os.environ", _ENV),
            patch(
                "pipeline.bot.pause.read_github_file_with_sha",
                new_callable=AsyncMock,
                return_value=(_DEFAULT_STATE_JSON, "sha123"),
            ),
            patch(
                "pipeline.bot.pause.write_github_file",
                new_callable=AsyncMock,
                return_value=True,
            ) as mock_write,
        ):
            asyncio.run(pause_command(update, ctx))

        mock_write.assert_called_once()
        # Verify the written JSON has paused_until set
        written_content = mock_write.call_args.kwargs["content"]
        written_json = json.loads(written_content)
        assert written_json["pause"]["paused_until"] != ""
        assert written_json["pause"]["paused_slots"] == ["all"]
        # Reply should mention "paused"
        reply_text = update.message.reply_text.call_args[0][0]
        assert "paused" in reply_text.lower() or "Paused" in reply_text

    def test_pause_without_duration(self):
        """pause_command with no args sets indefinite pause."""
        update = _make_update("/pause")
        ctx = MagicMock()

        with (
            patch.dict("os.environ", _ENV),
            patch(
                "pipeline.bot.pause.read_github_file_with_sha",
                new_callable=AsyncMock,
                return_value=(_DEFAULT_STATE_JSON, "sha123"),
            ),
            patch(
                "pipeline.bot.pause.write_github_file",
                new_callable=AsyncMock,
                return_value=True,
            ) as mock_write,
        ):
            asyncio.run(pause_command(update, ctx))

        written_content = mock_write.call_args.kwargs["content"]
        written_json = json.loads(written_content)
        assert written_json["pause"]["paused_until"] == ""
        assert written_json["pause"]["paused_slots"] == ["all"]
        reply_text = update.message.reply_text.call_args[0][0]
        assert "indefinitely" in reply_text.lower()

    def test_pause_unparseable_duration(self):
        """pause_command with garbage text replies with help message."""
        update = _make_update("/pause garbage")
        ctx = MagicMock()

        with (
            patch.dict("os.environ", _ENV),
            patch(
                "pipeline.bot.pause.read_github_file_with_sha",
                new_callable=AsyncMock,
                return_value=(_DEFAULT_STATE_JSON, "sha123"),
            ),
        ):
            asyncio.run(pause_command(update, ctx))

        reply_text = update.message.reply_text.call_args[0][0]
        assert "could not parse" in reply_text.lower()

    def test_pause_github_write_failure(self):
        """pause_command replies with error when GitHub write fails."""
        update = _make_update("/pause 3 days")
        ctx = MagicMock()

        with (
            patch.dict("os.environ", _ENV),
            patch(
                "pipeline.bot.pause.read_github_file_with_sha",
                new_callable=AsyncMock,
                return_value=(_DEFAULT_STATE_JSON, "sha123"),
            ),
            patch(
                "pipeline.bot.pause.write_github_file",
                new_callable=AsyncMock,
                return_value=False,
            ),
        ):
            asyncio.run(pause_command(update, ctx))

        reply_text = update.message.reply_text.call_args[0][0]
        assert "error" in reply_text.lower() or "failed" in reply_text.lower()

    def test_pause_missing_env_vars(self):
        """pause_command replies with error when env vars missing."""
        update = _make_update("/pause 3 days")
        ctx = MagicMock()

        with patch.dict("os.environ", {}, clear=True):
            asyncio.run(pause_command(update, ctx))

        reply_text = update.message.reply_text.call_args[0][0]
        assert "error" in reply_text.lower() or "not configured" in reply_text.lower()


class TestResumeCommand:
    """Tests for resume_command handler."""

    def test_resume_when_paused(self):
        """resume_command clears pause state and writes to GitHub."""
        update = _make_update("/resume")
        ctx = MagicMock()

        with (
            patch.dict("os.environ", _ENV),
            patch(
                "pipeline.bot.pause.read_github_file_with_sha",
                new_callable=AsyncMock,
                return_value=(_PAUSED_STATE_JSON, "sha456"),
            ),
            patch(
                "pipeline.bot.pause.write_github_file",
                new_callable=AsyncMock,
                return_value=True,
            ) as mock_write,
        ):
            asyncio.run(resume_command(update, ctx))

        written_content = mock_write.call_args.kwargs["content"]
        written_json = json.loads(written_content)
        assert written_json["pause"]["paused_until"] == ""
        assert written_json["pause"]["paused_slots"] == []
        reply_text = update.message.reply_text.call_args[0][0]
        assert "resumed" in reply_text.lower()

    def test_resume_when_not_paused(self):
        """resume_command when not paused replies accordingly."""
        update = _make_update("/resume")
        ctx = MagicMock()

        with (
            patch.dict("os.environ", _ENV),
            patch(
                "pipeline.bot.pause.read_github_file_with_sha",
                new_callable=AsyncMock,
                return_value=(_DEFAULT_STATE_JSON, "sha789"),
            ),
        ):
            asyncio.run(resume_command(update, ctx))

        reply_text = update.message.reply_text.call_args[0][0]
        assert "not paused" in reply_text.lower()

    def test_resume_github_write_failure(self):
        """resume_command replies with error when GitHub write fails."""
        update = _make_update("/resume")
        ctx = MagicMock()

        with (
            patch.dict("os.environ", _ENV),
            patch(
                "pipeline.bot.pause.read_github_file_with_sha",
                new_callable=AsyncMock,
                return_value=(_PAUSED_STATE_JSON, "sha456"),
            ),
            patch(
                "pipeline.bot.pause.write_github_file",
                new_callable=AsyncMock,
                return_value=False,
            ),
        ):
            asyncio.run(resume_command(update, ctx))

        reply_text = update.message.reply_text.call_args[0][0]
        assert "error" in reply_text.lower() or "failed" in reply_text.lower()
