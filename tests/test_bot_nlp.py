"""Tests for NL intent parser — Claude Haiku intent classification and dispatch.

TDD Phase 10 Plan 03 — tests for parse_nl_intent, NLIntent model, nl_command_handler.
Mocks anthropic.Anthropic to avoid real API calls in tests.
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

from pipeline.bot.nlp import NLIntent, nl_command_handler, parse_nl_intent


class TestNLIntentModel:
    """Tests for NLIntent Pydantic model validation."""

    def test_pause_intent_fields(self):
        """NLIntent with pause intent has slot and duration."""
        intent = NLIntent(intent="pause", confidence=0.9, slot="evening", duration="a week")
        assert intent.intent == "pause"
        assert intent.confidence == 0.9
        assert intent.slot == "evening"
        assert intent.duration == "a week"

    def test_schedule_modify_intent(self):
        """NLIntent with schedule_modify has new_time."""
        intent = NLIntent(
            intent="schedule_modify", confidence=0.85, slot="morning", new_time="06:30"
        )
        assert intent.intent == "schedule_modify"
        assert intent.new_time == "06:30"

    def test_event_schedule_intent(self):
        """NLIntent with event_schedule has event fields."""
        intent = NLIntent(
            intent="event_schedule",
            confidence=0.9,
            event_name="Budget",
            event_date="2026-02-01",
            interval_minutes=30,
            start_time="10:00",
            end_time="15:00",
        )
        assert intent.event_name == "Budget"
        assert intent.interval_minutes == 30

    def test_keyword_add_intent(self):
        """NLIntent with keyword_add has category and keyword."""
        intent = NLIntent(
            intent="keyword_add", confidence=0.8, category="celebrity", keyword="Priyanka Chopra"
        )
        assert intent.category == "celebrity"
        assert intent.keyword == "Priyanka Chopra"

    def test_unknown_intent_defaults(self):
        """NLIntent with unknown intent has default empty fields."""
        intent = NLIntent(intent="unknown")
        assert intent.confidence == 0.0
        assert intent.slot == ""
        assert intent.duration == ""

    def test_keyword_remove_intent(self):
        """NLIntent with keyword_remove has category and keyword."""
        intent = NLIntent(
            intent="keyword_remove", confidence=0.8, category="infrastructure", keyword="NHAI"
        )
        assert intent.intent == "keyword_remove"


class TestParseNLIntent:
    """Tests for parse_nl_intent — mocked Claude Haiku calls."""

    def _mock_claude_response(self, response_json: dict):
        """Create a mock Anthropic client that returns the given JSON."""
        mock_client = MagicMock()
        mock_message = MagicMock()
        mock_block = MagicMock()
        mock_block.text = json.dumps(response_json)
        mock_message.content = [mock_block]
        mock_client.messages.create.return_value = mock_message
        return mock_client

    @patch("pipeline.bot.nlp.anthropic")
    def test_parses_pause_intent(self, mock_anthropic):
        """parse_nl_intent classifies 'stop evening alerts for a week' as pause."""
        mock_anthropic.Anthropic.return_value = self._mock_claude_response(
            {"intent": "pause", "confidence": 0.95, "slot": "evening", "duration": "a week"}
        )
        result = parse_nl_intent("stop evening alerts for a week")
        assert result.intent == "pause"
        assert result.slot == "evening"
        assert result.confidence >= 0.7

    @patch("pipeline.bot.nlp.anthropic")
    def test_parses_keyword_add(self, mock_anthropic):
        """parse_nl_intent classifies 'track Priyanka Chopra' as keyword_add."""
        mock_anthropic.Anthropic.return_value = self._mock_claude_response(
            {
                "intent": "keyword_add",
                "confidence": 0.85,
                "category": "celebrity",
                "keyword": "Priyanka Chopra",
            }
        )
        result = parse_nl_intent("track Priyanka Chopra")
        assert result.intent == "keyword_add"
        assert result.keyword == "Priyanka Chopra"

    @patch("pipeline.bot.nlp.anthropic")
    def test_parses_schedule_modify(self, mock_anthropic):
        """parse_nl_intent classifies 'change morning alert to 6:30 AM' as schedule_modify."""
        mock_anthropic.Anthropic.return_value = self._mock_claude_response(
            {"intent": "schedule_modify", "confidence": 0.9, "slot": "morning", "new_time": "06:30"}
        )
        result = parse_nl_intent("change morning alert to 6:30 AM")
        assert result.intent == "schedule_modify"
        assert result.new_time == "06:30"

    @patch("pipeline.bot.nlp.anthropic")
    def test_parses_event_schedule(self, mock_anthropic):
        """parse_nl_intent classifies event scheduling request."""
        mock_anthropic.Anthropic.return_value = self._mock_claude_response(
            {
                "intent": "event_schedule",
                "confidence": 0.88,
                "event_name": "Budget",
                "event_date": "2026-02-01",
                "interval_minutes": 30,
                "start_time": "10:00",
                "end_time": "15:00",
            }
        )
        result = parse_nl_intent("Budget on Feb 1, updates every 30 min from 10 AM to 3 PM")
        assert result.intent == "event_schedule"
        assert result.event_name == "Budget"
        assert result.interval_minutes == 30

    @patch("pipeline.bot.nlp.anthropic")
    def test_parses_unknown_for_greeting(self, mock_anthropic):
        """parse_nl_intent classifies 'hello' as unknown with low confidence."""
        mock_anthropic.Anthropic.return_value = self._mock_claude_response(
            {"intent": "unknown", "confidence": 0.3}
        )
        result = parse_nl_intent("hello")
        assert result.intent == "unknown"
        assert result.confidence < 0.7

    @patch("pipeline.bot.nlp.anthropic")
    def test_returns_unknown_on_api_failure(self, mock_anthropic):
        """parse_nl_intent returns unknown intent on Claude API failure."""
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("API error")
        mock_anthropic.Anthropic.return_value = mock_client
        result = parse_nl_intent("stop evening alerts")
        assert result.intent == "unknown"

    @patch("pipeline.bot.nlp.anthropic")
    def test_returns_unknown_on_invalid_json(self, mock_anthropic):
        """parse_nl_intent returns unknown when Claude returns invalid JSON."""
        mock_client = MagicMock()
        mock_message = MagicMock()
        mock_block = MagicMock()
        mock_block.text = "not valid json"
        mock_message.content = [mock_block]
        mock_client.messages.create.return_value = mock_message
        mock_anthropic.Anthropic.return_value = mock_client
        result = parse_nl_intent("some text")
        assert result.intent == "unknown"


class TestNLCommandHandler:
    """Tests for nl_command_handler — dispatch logic."""

    def _make_update_context(self, text=""):
        """Create mock Update and context for handler testing."""
        update = MagicMock()
        update.message = MagicMock()
        update.message.text = text
        update.message.reply_text = AsyncMock()
        context = MagicMock()
        return update, context

    @patch("pipeline.bot.nlp.parse_nl_intent")
    def test_ignores_short_messages(self, mock_parse):
        """nl_command_handler skips messages shorter than 6 chars."""
        update, context = self._make_update_context("hi")
        asyncio.run(nl_command_handler(update, context))
        mock_parse.assert_not_called()
        update.message.reply_text.assert_not_called()

    @patch("pipeline.bot.nlp.parse_nl_intent")
    def test_sends_processing_feedback(self, mock_parse):
        """nl_command_handler sends 'Processing...' before API call."""
        mock_parse.return_value = NLIntent(intent="unknown", confidence=0.3)
        update, context = self._make_update_context("what is happening today")
        asyncio.run(nl_command_handler(update, context))
        first_call = update.message.reply_text.call_args_list[0]
        assert "Processing" in first_call[0][0]

    @patch("pipeline.bot.nlp._dispatch_pause", new_callable=AsyncMock)
    @patch("pipeline.bot.nlp.parse_nl_intent")
    def test_dispatches_pause_intent(self, mock_parse, mock_dispatch):
        """nl_command_handler dispatches pause intent to pause logic."""
        mock_parse.return_value = NLIntent(
            intent="pause", confidence=0.9, slot="evening", duration="a week"
        )
        update, context = self._make_update_context("stop evening alerts for a week")
        asyncio.run(nl_command_handler(update, context))
        mock_dispatch.assert_called_once()

    @patch("pipeline.bot.nlp.parse_nl_intent")
    def test_replies_unknown_for_low_confidence(self, mock_parse):
        """nl_command_handler replies with help text for unknown intent."""
        mock_parse.return_value = NLIntent(intent="unknown", confidence=0.3)
        update, context = self._make_update_context("random gibberish text here")
        asyncio.run(nl_command_handler(update, context))
        last_call = update.message.reply_text.call_args_list[-1]
        assert "didn't understand" in last_call[0][0].lower() or "help" in last_call[0][0].lower()

    @patch("pipeline.bot.nlp._dispatch_resume", new_callable=AsyncMock)
    @patch("pipeline.bot.nlp.parse_nl_intent")
    def test_dispatches_resume_intent(self, mock_parse, mock_dispatch):
        """nl_command_handler dispatches resume intent."""
        mock_parse.return_value = NLIntent(intent="resume", confidence=0.9)
        update, context = self._make_update_context("resume my deliveries please")
        asyncio.run(nl_command_handler(update, context))
        mock_dispatch.assert_called_once()

    @patch("pipeline.bot.nlp._dispatch_schedule_modify", new_callable=AsyncMock)
    @patch("pipeline.bot.nlp.parse_nl_intent")
    def test_dispatches_schedule_modify(self, mock_parse, mock_dispatch):
        """nl_command_handler dispatches schedule_modify intent."""
        mock_parse.return_value = NLIntent(
            intent="schedule_modify", confidence=0.9, slot="morning", new_time="06:30"
        )
        update, context = self._make_update_context("change morning alert to 6:30 AM")
        asyncio.run(nl_command_handler(update, context))
        mock_dispatch.assert_called_once()
