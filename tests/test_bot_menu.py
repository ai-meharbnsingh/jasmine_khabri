"""Tests for inline keyboard menu — /menu command and callback handlers.

TDD Phase 9 Plan 02 — Task 1.
Tests menu_command (inline keyboard markup) and menu_callback (routing by callback_data).
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from pipeline.bot.menu import menu_callback, menu_command


def _make_message_update():
    """Create mock Update with message for /menu command."""
    update = MagicMock()
    update.message = MagicMock()
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    return update, context


def _make_callback_update(data: str, user_id: int = 123):
    """Create mock Update with callback_query for inline keyboard tap."""
    query = MagicMock()
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.data = data
    query.from_user = MagicMock()
    query.from_user.id = user_id
    update = MagicMock()
    update.callback_query = query
    update.message = None  # Callback queries do NOT have update.message
    context = MagicMock()
    return update, context


class TestMenuCommand:
    """Tests for /menu command — inline keyboard construction."""

    def test_reply_text_called_with_markup(self):
        """/menu replies with text and reply_markup."""
        update, context = _make_message_update()
        asyncio.run(menu_command(update, context))
        update.message.reply_text.assert_called_once()
        call_kwargs = update.message.reply_text.call_args
        # reply_markup should be passed
        assert call_kwargs[1].get("reply_markup") is not None or (len(call_kwargs[0]) > 1)

    def test_keyboard_has_three_buttons(self):
        """/menu keyboard has Keywords, Status, and Help buttons."""
        update, context = _make_message_update()
        asyncio.run(menu_command(update, context))
        call_kwargs = update.message.reply_text.call_args
        markup = call_kwargs[1].get("reply_markup")
        # Flatten all buttons from all rows
        all_buttons = []
        for row in markup.inline_keyboard:
            all_buttons.extend(row)
        assert len(all_buttons) == 3

    def test_keyboard_button_labels(self):
        """/menu keyboard buttons have correct labels."""
        update, context = _make_message_update()
        asyncio.run(menu_command(update, context))
        call_kwargs = update.message.reply_text.call_args
        markup = call_kwargs[1].get("reply_markup")
        all_buttons = []
        for row in markup.inline_keyboard:
            all_buttons.extend(row)
        labels = [b.text for b in all_buttons]
        assert "Keywords" in labels
        assert "Status" in labels
        assert "Help" in labels

    def test_keyboard_callback_data(self):
        """/menu buttons have correct callback_data values."""
        update, context = _make_message_update()
        asyncio.run(menu_command(update, context))
        call_kwargs = update.message.reply_text.call_args
        markup = call_kwargs[1].get("reply_markup")
        all_buttons = []
        for row in markup.inline_keyboard:
            all_buttons.extend(row)
        data_values = [b.callback_data for b in all_buttons]
        assert "menu_keywords" in data_values
        assert "menu_status" in data_values
        assert "menu_help" in data_values

    def test_keyboard_layout_two_rows(self):
        """/menu keyboard has 2 rows: [Keywords, Status] and [Help]."""
        update, context = _make_message_update()
        asyncio.run(menu_command(update, context))
        call_kwargs = update.message.reply_text.call_args
        markup = call_kwargs[1].get("reply_markup")
        assert len(markup.inline_keyboard) == 2
        assert len(markup.inline_keyboard[0]) == 2  # Keywords, Status
        assert len(markup.inline_keyboard[1]) == 1  # Help


class TestMenuCallbackAnswer:
    """Tests for callback query answer — must always be called."""

    def test_answer_called_on_keywords(self):
        """menu_callback calls query.answer() for menu_keywords."""
        update, context = _make_callback_update("menu_keywords")
        with patch("pipeline.bot.menu.read_github_file", new_callable=AsyncMock) as mock_read:
            mock_read.return_value = (
                "categories:\n  infra:\n    active: true\n    keywords: []\nexclusions: []"
            )
            asyncio.run(menu_callback(update, context))
        update.callback_query.answer.assert_called_once()

    def test_answer_called_on_status(self):
        """menu_callback calls query.answer() for menu_status."""
        update, context = _make_callback_update("menu_status")
        with patch("pipeline.bot.menu.fetch_pipeline_status", new_callable=AsyncMock) as mock_fetch:
            from pipeline.schemas.pipeline_status_schema import PipelineStatus

            mock_fetch.return_value = PipelineStatus()
            asyncio.run(menu_callback(update, context))
        update.callback_query.answer.assert_called_once()

    def test_answer_called_on_help(self):
        """menu_callback calls query.answer() for menu_help."""
        update, context = _make_callback_update("menu_help")
        asyncio.run(menu_callback(update, context))
        update.callback_query.answer.assert_called_once()


class TestMenuCallbackKeywords:
    """Tests for menu_keywords callback — displays keyword library."""

    def test_edits_message_with_keyword_text(self, monkeypatch):
        """menu_keywords callback edits message with formatted keywords."""
        monkeypatch.setenv("GITHUB_PAT", "tok")
        monkeypatch.setenv("GITHUB_OWNER", "owner")
        monkeypatch.setenv("GITHUB_REPO", "repo")
        monkeypatch.setenv("AUTHORIZED_USER_IDS", "123")
        update, context = _make_callback_update("menu_keywords", user_id=123)

        sample_yaml = (
            "categories:\n  infrastructure:\n    active: true\n"
            "    keywords:\n      - metro\nexclusions: []"
        )
        with patch("pipeline.bot.menu.read_github_file", new_callable=AsyncMock) as mock_read:
            mock_read.return_value = sample_yaml
            asyncio.run(menu_callback(update, context))

        update.callback_query.edit_message_text.assert_called_once()
        text = update.callback_query.edit_message_text.call_args[0][0]
        assert "metro" in text

    def test_edits_with_error_on_github_failure(self, monkeypatch):
        """menu_keywords callback shows error when GitHub API fails."""
        monkeypatch.setenv("GITHUB_PAT", "tok")
        monkeypatch.setenv("GITHUB_OWNER", "owner")
        monkeypatch.setenv("GITHUB_REPO", "repo")
        monkeypatch.setenv("AUTHORIZED_USER_IDS", "123")
        update, context = _make_callback_update("menu_keywords", user_id=123)

        with patch("pipeline.bot.menu.read_github_file", new_callable=AsyncMock) as mock_read:
            mock_read.side_effect = Exception("API error")
            asyncio.run(menu_callback(update, context))

        text = update.callback_query.edit_message_text.call_args[0][0]
        assert "failed" in text.lower()


class TestMenuCallbackStatus:
    """Tests for menu_status callback — displays pipeline status."""

    def test_edits_message_with_status_text(self, monkeypatch):
        """menu_status callback edits message with pipeline status info."""
        monkeypatch.setenv("AUTHORIZED_USER_IDS", "123")
        update, context = _make_callback_update("menu_status", user_id=123)

        from pipeline.schemas.pipeline_status_schema import PipelineStatus

        mock_status = PipelineStatus(
            last_run_utc="2026-03-07T11:00:00Z",
            articles_fetched=25,
            articles_delivered=12,
        )
        with patch("pipeline.bot.menu.fetch_pipeline_status", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_status
            asyncio.run(menu_callback(update, context))

        text = update.callback_query.edit_message_text.call_args[0][0]
        assert "2026-03-07T11:00:00Z" in text
        assert "25" in text

    def test_edits_with_error_on_status_failure(self, monkeypatch):
        """menu_status callback shows error when status fetch fails."""
        monkeypatch.setenv("AUTHORIZED_USER_IDS", "123")
        update, context = _make_callback_update("menu_status", user_id=123)

        with patch("pipeline.bot.menu.fetch_pipeline_status", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.side_effect = Exception("Network error")
            asyncio.run(menu_callback(update, context))

        text = update.callback_query.edit_message_text.call_args[0][0]
        assert "failed" in text.lower()


class TestMenuCallbackHelp:
    """Tests for menu_help callback — displays help text."""

    def test_edits_message_with_help_text(self, monkeypatch):
        """menu_help callback edits message with help commands."""
        monkeypatch.setenv("AUTHORIZED_USER_IDS", "123")
        update, context = _make_callback_update("menu_help", user_id=123)
        asyncio.run(menu_callback(update, context))

        text = update.callback_query.edit_message_text.call_args[0][0]
        assert "/help" in text
        assert "/status" in text


class TestMenuCallbackAuth:
    """Tests for defense-in-depth auth check in callback handler."""

    def test_unauthorized_user_gets_denied(self, monkeypatch):
        """menu_callback denies user not in AUTHORIZED_USER_IDS."""
        monkeypatch.setenv("AUTHORIZED_USER_IDS", "999")
        update, context = _make_callback_update("menu_keywords", user_id=123)
        asyncio.run(menu_callback(update, context))

        # answer() still called to dismiss spinner
        update.callback_query.answer.assert_called_once()
        text = update.callback_query.edit_message_text.call_args[0][0]
        assert "unauthorized" in text.lower()

    def test_authorized_user_passes(self, monkeypatch):
        """menu_callback allows user in AUTHORIZED_USER_IDS."""
        monkeypatch.setenv("AUTHORIZED_USER_IDS", "123,456")
        monkeypatch.setenv("GITHUB_PAT", "tok")
        monkeypatch.setenv("GITHUB_OWNER", "owner")
        monkeypatch.setenv("GITHUB_REPO", "repo")
        update, context = _make_callback_update("menu_help", user_id=123)
        asyncio.run(menu_callback(update, context))

        text = update.callback_query.edit_message_text.call_args[0][0]
        assert "unauthorized" not in text.lower()

    def test_empty_authorized_allows_all(self, monkeypatch):
        """menu_callback allows all users when AUTHORIZED_USER_IDS is empty."""
        monkeypatch.delenv("AUTHORIZED_USER_IDS", raising=False)
        update, context = _make_callback_update("menu_help", user_id=999)
        asyncio.run(menu_callback(update, context))

        text = update.callback_query.edit_message_text.call_args[0][0]
        assert "unauthorized" not in text.lower()
