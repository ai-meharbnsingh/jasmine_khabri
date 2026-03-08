"""Tests for pause/resume — duration parsing, BotState schema, loader, and command handlers.

TDD Phase 10 Plan 01.
Task 1: Schema, loader, and duration parser tests.
Task 2: Pause/resume command handler tests.
"""

import json
from datetime import timedelta

from pipeline.bot.pause import parse_duration
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
