"""Tests for bot entrypoint — Application builder and polling setup.

TDD Phase 8 Plan 02 + Phase 9 Plan 02 — tests for main() in entrypoint.py.
Mocks ApplicationBuilder to avoid real Telegram polling in tests.
Phase 9 additions: keyword/menu handlers, CallbackQueryHandler, allowed_updates.
"""

from unittest.mock import MagicMock, patch

import pytest

from pipeline.bot.entrypoint import main


class TestMainTokenValidation:
    """Tests for TELEGRAM_BOT_TOKEN validation in main()."""

    def test_raises_when_token_unset(self, monkeypatch):
        """main() raises RuntimeError when TELEGRAM_BOT_TOKEN is not set."""
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        with pytest.raises(RuntimeError, match="TELEGRAM_BOT_TOKEN"):
            main()

    def test_raises_when_token_empty(self, monkeypatch):
        """main() raises RuntimeError when TELEGRAM_BOT_TOKEN is empty string."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
        with pytest.raises(RuntimeError, match="TELEGRAM_BOT_TOKEN"):
            main()


class TestMainApplicationConstruction:
    """Tests for Application builder setup in main()."""

    @patch("pipeline.bot.entrypoint.ApplicationBuilder")
    def test_passes_token_to_builder(self, mock_builder_cls, monkeypatch):
        """main() passes TELEGRAM_BOT_TOKEN to ApplicationBuilder().token()."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token-123")
        monkeypatch.setenv("AUTHORIZED_USER_IDS", "111,222")

        mock_builder = MagicMock()
        mock_builder_cls.return_value = mock_builder
        mock_builder.token.return_value = mock_builder
        mock_app = MagicMock()
        mock_builder.build.return_value = mock_app

        main()

        mock_builder.token.assert_called_once_with("test-token-123")
        mock_builder.build.assert_called_once()

    @patch("pipeline.bot.entrypoint.ApplicationBuilder")
    def test_registers_help_and_status_handlers(self, mock_builder_cls, monkeypatch):
        """main() registers at least help and status command handlers."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token-123")
        monkeypatch.setenv("AUTHORIZED_USER_IDS", "111,222")

        mock_builder = MagicMock()
        mock_builder_cls.return_value = mock_builder
        mock_builder.token.return_value = mock_builder
        mock_app = MagicMock()
        mock_builder.build.return_value = mock_app

        main()

        # Should have called add_handler multiple times (help, status, start, unauthorized)
        assert mock_app.add_handler.call_count >= 3

    @patch("pipeline.bot.entrypoint.ApplicationBuilder")
    def test_calls_run_polling_with_drop_pending(self, mock_builder_cls, monkeypatch):
        """main() calls run_polling with drop_pending_updates=True."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token-123")
        monkeypatch.setenv("AUTHORIZED_USER_IDS", "111,222")

        mock_builder = MagicMock()
        mock_builder_cls.return_value = mock_builder
        mock_builder.token.return_value = mock_builder
        mock_app = MagicMock()
        mock_builder.build.return_value = mock_app

        main()

        mock_app.run_polling.assert_called_once()
        kwargs = mock_app.run_polling.call_args[1]
        assert kwargs.get("drop_pending_updates") is True


class TestMainPhase9Handlers:
    """Tests for Phase 9+10 handler registrations."""

    @patch("pipeline.bot.entrypoint.ApplicationBuilder")
    def test_registers_at_least_13_handlers_in_group_0(self, mock_builder_cls, monkeypatch):
        """main() registers at least 13 handlers in default group (0).

        Phase 8: help, status, start, run (4)
        Phase 9: keywords, menu, add_msg, remove_msg, callback (5)
        Phase 10: pause, resume, stats, schedule (4)
        Total group 0: at least 13
        """
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token-123")
        monkeypatch.setenv("AUTHORIZED_USER_IDS", "111,222")

        mock_builder = MagicMock()
        mock_builder_cls.return_value = mock_builder
        mock_builder.token.return_value = mock_builder
        mock_app = MagicMock()
        mock_builder.build.return_value = mock_app

        main()

        # Group 0 calls = those without group kwarg or group=0
        group_0_calls = [
            c for c in mock_app.add_handler.call_args_list if c[1].get("group", 0) == 0
        ]
        assert len(group_0_calls) >= 13

    @patch("pipeline.bot.entrypoint.ApplicationBuilder")
    def test_allowed_updates_includes_callback_query(self, mock_builder_cls, monkeypatch):
        """run_polling allowed_updates must include 'callback_query'."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token-123")
        monkeypatch.setenv("AUTHORIZED_USER_IDS", "111,222")

        mock_builder = MagicMock()
        mock_builder_cls.return_value = mock_builder
        mock_builder.token.return_value = mock_builder
        mock_app = MagicMock()
        mock_builder.build.return_value = mock_app

        main()

        kwargs = mock_app.run_polling.call_args[1]
        allowed = kwargs.get("allowed_updates", [])
        assert "callback_query" in allowed

    @patch("pipeline.bot.entrypoint.ApplicationBuilder")
    def test_allowed_updates_includes_message(self, mock_builder_cls, monkeypatch):
        """run_polling allowed_updates must still include 'message'."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token-123")
        monkeypatch.setenv("AUTHORIZED_USER_IDS", "111,222")

        mock_builder = MagicMock()
        mock_builder_cls.return_value = mock_builder
        mock_builder.token.return_value = mock_builder
        mock_app = MagicMock()
        mock_builder.build.return_value = mock_app

        main()

        kwargs = mock_app.run_polling.call_args[1]
        allowed = kwargs.get("allowed_updates", [])
        assert "message" in allowed


class TestMainUnauthorizedHandler:
    """Tests for unauthorized catch-all handler registration."""

    @patch("pipeline.bot.entrypoint.ApplicationBuilder")
    def test_registers_unauthorized_in_group_1(self, mock_builder_cls, monkeypatch):
        """main() registers unauthorized handler in group=1."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token-123")
        monkeypatch.setenv("AUTHORIZED_USER_IDS", "111,222")

        mock_builder = MagicMock()
        mock_builder_cls.return_value = mock_builder
        mock_builder.token.return_value = mock_builder
        mock_app = MagicMock()
        mock_builder.build.return_value = mock_app

        main()

        # Find the add_handler call with group=1
        group_1_calls = [c for c in mock_app.add_handler.call_args_list if c[1].get("group") == 1]
        assert len(group_1_calls) >= 1, "Expected at least one handler registered in group=1"


class TestMainPhase10NLHandler:
    """Tests for Phase 10 NL catch-all handler in group 2."""

    @patch("pipeline.bot.entrypoint.ApplicationBuilder")
    def test_registers_nl_handler_in_group_2(self, mock_builder_cls, monkeypatch):
        """main() registers NL catch-all MessageHandler in group=2."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token-123")
        monkeypatch.setenv("AUTHORIZED_USER_IDS", "111,222")

        mock_builder = MagicMock()
        mock_builder_cls.return_value = mock_builder
        mock_builder.token.return_value = mock_builder
        mock_app = MagicMock()
        mock_builder.build.return_value = mock_app

        main()

        group_2_calls = [c for c in mock_app.add_handler.call_args_list if c[1].get("group") == 2]
        assert len(group_2_calls) >= 1, "Expected at least one handler in group=2 for NL catch-all"


class TestMainEmptyAuthorizedUsers:
    """Tests for behavior when AUTHORIZED_USER_IDS is empty."""

    @patch("pipeline.bot.entrypoint.ApplicationBuilder")
    def test_runs_without_crashing_when_no_users(self, mock_builder_cls, monkeypatch):
        """main() still starts when AUTHORIZED_USER_IDS is not set (allows all)."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token-123")
        monkeypatch.delenv("AUTHORIZED_USER_IDS", raising=False)

        mock_builder = MagicMock()
        mock_builder_cls.return_value = mock_builder
        mock_builder.token.return_value = mock_builder
        mock_app = MagicMock()
        mock_builder.build.return_value = mock_app

        main()

        mock_app.run_polling.assert_called_once()
