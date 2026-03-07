"""Tests for bot /run command — repository_dispatch trigger via GitHub API.

TDD Phase 8 Plan 03 — tests for trigger_pipeline and run_now_command.
Uses respx for httpx mocking and asyncio.run() for async tests.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import respx


class TestTriggerPipelineSuccess:
    """Tests for trigger_pipeline returning True on 204 No Content."""

    def test_returns_true_on_204(self):
        """trigger_pipeline returns True when GitHub API responds with 204."""
        from pipeline.bot.dispatcher import trigger_pipeline

        with respx.mock:
            respx.post("https://api.github.com/repos/owner/repo/dispatches").respond(204)
            result = asyncio.run(trigger_pipeline("token123", "owner", "repo"))
        assert result is True


class TestTriggerPipelineFailure:
    """Tests for trigger_pipeline returning False on non-204 and errors."""

    def test_returns_false_on_404(self):
        """trigger_pipeline returns False when GitHub API responds with 404."""
        from pipeline.bot.dispatcher import trigger_pipeline

        with respx.mock:
            respx.post("https://api.github.com/repos/owner/repo/dispatches").respond(404)
            result = asyncio.run(trigger_pipeline("token123", "owner", "repo"))
        assert result is False

    def test_returns_false_on_500(self):
        """trigger_pipeline returns False on server error response."""
        from pipeline.bot.dispatcher import trigger_pipeline

        with respx.mock:
            respx.post("https://api.github.com/repos/owner/repo/dispatches").respond(500)
            result = asyncio.run(trigger_pipeline("token123", "owner", "repo"))
        assert result is False

    def test_returns_false_on_network_error(self):
        """trigger_pipeline returns False on network error, no crash."""
        from pipeline.bot.dispatcher import trigger_pipeline

        with respx.mock:
            respx.post("https://api.github.com/repos/owner/repo/dispatches").mock(
                side_effect=httpx.ConnectError("connection refused")
            )
            result = asyncio.run(trigger_pipeline("token123", "owner", "repo"))
        assert result is False


class TestTriggerPipelinePayload:
    """Tests for trigger_pipeline sending correct URL, headers, and payload."""

    def test_sends_correct_url(self):
        """trigger_pipeline POSTs to the correct dispatches URL."""
        from pipeline.bot.dispatcher import trigger_pipeline

        with respx.mock:
            route = respx.post("https://api.github.com/repos/myowner/myrepo/dispatches").respond(
                204
            )
            asyncio.run(trigger_pipeline("tok", "myowner", "myrepo"))
        assert route.called

    def test_sends_bearer_token(self):
        """trigger_pipeline sends Authorization: Bearer {token} header."""
        from pipeline.bot.dispatcher import trigger_pipeline

        with respx.mock:
            route = respx.post("https://api.github.com/repos/owner/repo/dispatches").respond(204)
            asyncio.run(trigger_pipeline("my-secret-token", "owner", "repo"))
        request = route.calls[0].request
        assert request.headers["authorization"] == "Bearer my-secret-token"

    def test_sends_accept_header(self):
        """trigger_pipeline sends Accept: application/vnd.github.v3+json header."""
        from pipeline.bot.dispatcher import trigger_pipeline

        with respx.mock:
            route = respx.post("https://api.github.com/repos/owner/repo/dispatches").respond(204)
            asyncio.run(trigger_pipeline("tok", "owner", "repo"))
        request = route.calls[0].request
        assert request.headers["accept"] == "application/vnd.github.v3+json"

    def test_sends_correct_payload(self):
        """trigger_pipeline sends event_type 'run_now' with client_payload."""
        import json

        from pipeline.bot.dispatcher import trigger_pipeline

        with respx.mock:
            route = respx.post("https://api.github.com/repos/owner/repo/dispatches").respond(204)
            asyncio.run(trigger_pipeline("tok", "owner", "repo"))
        request = route.calls[0].request
        body = json.loads(request.content)
        assert body["event_type"] == "run_now"
        assert body["client_payload"]["triggered_by"] == "telegram_bot"


class TestRunNowCommandSuccess:
    """Tests for run_now_command on successful dispatch."""

    def test_replies_success_on_true(self, monkeypatch):
        """run_now_command replies with success message when trigger returns True."""
        from pipeline.bot.handler import run_now_command

        monkeypatch.setenv("GITHUB_PAT", "tok")
        monkeypatch.setenv("GITHUB_OWNER", "owner")
        monkeypatch.setenv("GITHUB_REPO", "repo")

        update = MagicMock()
        update.message = MagicMock()
        update.message.reply_text = AsyncMock()
        context = MagicMock()

        with patch("pipeline.bot.handler.trigger_pipeline", new_callable=AsyncMock) as mock_trigger:
            mock_trigger.return_value = True
            asyncio.run(run_now_command(update, context))

        # Should have replied twice: "Triggering..." and success
        assert update.message.reply_text.call_count == 2
        last_reply = update.message.reply_text.call_args_list[-1][0][0]
        assert "dispatched" in last_reply.lower() or "pipeline" in last_reply.lower()

    def test_sends_triggering_feedback_first(self, monkeypatch):
        """run_now_command sends immediate 'Triggering...' feedback before dispatching."""
        from pipeline.bot.handler import run_now_command

        monkeypatch.setenv("GITHUB_PAT", "tok")
        monkeypatch.setenv("GITHUB_OWNER", "owner")
        monkeypatch.setenv("GITHUB_REPO", "repo")

        update = MagicMock()
        update.message = MagicMock()
        update.message.reply_text = AsyncMock()
        context = MagicMock()

        with patch("pipeline.bot.handler.trigger_pipeline", new_callable=AsyncMock) as mock_trigger:
            mock_trigger.return_value = True
            asyncio.run(run_now_command(update, context))

        first_reply = update.message.reply_text.call_args_list[0][0][0]
        assert "triggering" in first_reply.lower()


class TestRunNowCommandFailure:
    """Tests for run_now_command on failed dispatch."""

    def test_replies_failure_on_false(self, monkeypatch):
        """run_now_command replies with failure message when trigger returns False."""
        from pipeline.bot.handler import run_now_command

        monkeypatch.setenv("GITHUB_PAT", "tok")
        monkeypatch.setenv("GITHUB_OWNER", "owner")
        monkeypatch.setenv("GITHUB_REPO", "repo")

        update = MagicMock()
        update.message = MagicMock()
        update.message.reply_text = AsyncMock()
        context = MagicMock()

        with patch("pipeline.bot.handler.trigger_pipeline", new_callable=AsyncMock) as mock_trigger:
            mock_trigger.return_value = False
            asyncio.run(run_now_command(update, context))

        last_reply = update.message.reply_text.call_args_list[-1][0][0]
        assert "failed" in last_reply.lower()


class TestRunNowCommandMissingEnv:
    """Tests for run_now_command with missing environment variables."""

    def test_replies_error_on_missing_github_pat(self, monkeypatch):
        """run_now_command replies with config error when GITHUB_PAT is missing."""
        from pipeline.bot.handler import run_now_command

        monkeypatch.delenv("GITHUB_PAT", raising=False)
        monkeypatch.setenv("GITHUB_OWNER", "owner")
        monkeypatch.setenv("GITHUB_REPO", "repo")

        update = MagicMock()
        update.message = MagicMock()
        update.message.reply_text = AsyncMock()
        context = MagicMock()

        asyncio.run(run_now_command(update, context))

        update.message.reply_text.assert_called_once()
        reply_text = update.message.reply_text.call_args[0][0]
        assert "not configured" in reply_text.lower() or "GITHUB_PAT" in reply_text

    def test_replies_error_on_missing_owner(self, monkeypatch):
        """run_now_command replies with config error when GITHUB_OWNER is missing."""
        from pipeline.bot.handler import run_now_command

        monkeypatch.setenv("GITHUB_PAT", "tok")
        monkeypatch.delenv("GITHUB_OWNER", raising=False)
        monkeypatch.setenv("GITHUB_REPO", "repo")

        update = MagicMock()
        update.message = MagicMock()
        update.message.reply_text = AsyncMock()
        context = MagicMock()

        asyncio.run(run_now_command(update, context))

        update.message.reply_text.assert_called_once()
        reply_text = update.message.reply_text.call_args[0][0]
        assert "not configured" in reply_text.lower() or "GITHUB_OWNER" in reply_text

    def test_replies_error_on_missing_repo(self, monkeypatch):
        """run_now_command replies with config error when GITHUB_REPO is missing."""
        from pipeline.bot.handler import run_now_command

        monkeypatch.setenv("GITHUB_PAT", "tok")
        monkeypatch.setenv("GITHUB_OWNER", "owner")
        monkeypatch.delenv("GITHUB_REPO", raising=False)

        update = MagicMock()
        update.message = MagicMock()
        update.message.reply_text = AsyncMock()
        context = MagicMock()

        asyncio.run(run_now_command(update, context))

        update.message.reply_text.assert_called_once()
        reply_text = update.message.reply_text.call_args[0][0]
        assert "not configured" in reply_text.lower() or "GITHUB_REPO" in reply_text

    def test_does_not_call_trigger_when_env_missing(self, monkeypatch):
        """run_now_command does NOT call trigger_pipeline when env vars are missing."""
        from pipeline.bot.handler import run_now_command

        monkeypatch.delenv("GITHUB_PAT", raising=False)
        monkeypatch.delenv("GITHUB_OWNER", raising=False)
        monkeypatch.delenv("GITHUB_REPO", raising=False)

        update = MagicMock()
        update.message = MagicMock()
        update.message.reply_text = AsyncMock()
        context = MagicMock()

        with patch("pipeline.bot.handler.trigger_pipeline", new_callable=AsyncMock) as mock_trigger:
            asyncio.run(run_now_command(update, context))
            mock_trigger.assert_not_called()
