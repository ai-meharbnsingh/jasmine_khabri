"""Tests for bot command handlers — /help, /status, unauthorized.

TDD Phase 8 Plan 02 — tests for help_command, status_command, unauthorized_handler.
Uses asyncio.run() for async handler tests (no pytest-asyncio dependency needed).
Phase 11-02: /status usage display tests.
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import respx

from pipeline.bot.handler import help_command, status_command, unauthorized_handler
from pipeline.schemas.ai_cost_schema import AICost
from pipeline.schemas.pipeline_status_schema import PipelineStatus


def _make_update_context():
    """Create mock Update and context objects for handler testing."""
    update = MagicMock()
    update.message = MagicMock()
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    return update, context


class TestHelpCommand:
    """Tests for /help command handler."""

    def test_reply_contains_help(self):
        """/help reply includes /help in the command list."""
        update, context = _make_update_context()
        asyncio.run(help_command(update, context))
        reply_text = update.message.reply_text.call_args[0][0]
        assert "/help" in reply_text

    def test_reply_contains_status(self):
        """/help reply includes /status in the command list."""
        update, context = _make_update_context()
        asyncio.run(help_command(update, context))
        reply_text = update.message.reply_text.call_args[0][0]
        assert "/status" in reply_text

    def test_reply_text_called_once(self):
        """/help calls reply_text exactly once."""
        update, context = _make_update_context()
        asyncio.run(help_command(update, context))
        update.message.reply_text.assert_called_once()

    def test_reply_contains_keywords_command(self):
        """/help reply includes /keywords in the command list."""
        update, context = _make_update_context()
        asyncio.run(help_command(update, context))
        reply_text = update.message.reply_text.call_args[0][0]
        assert "/keywords" in reply_text

    def test_reply_contains_menu_command(self):
        """/help reply includes /menu in the command list."""
        update, context = _make_update_context()
        asyncio.run(help_command(update, context))
        reply_text = update.message.reply_text.call_args[0][0]
        assert "/menu" in reply_text

    def test_reply_contains_add_remove_syntax(self):
        """/help reply includes keyword add/remove syntax."""
        update, context = _make_update_context()
        asyncio.run(help_command(update, context))
        reply_text = update.message.reply_text.call_args[0][0]
        assert "add" in reply_text.lower()
        assert "remove" in reply_text.lower()

    def test_reply_contains_pause_command(self):
        """/help reply includes /pause."""
        update, context = _make_update_context()
        asyncio.run(help_command(update, context))
        reply_text = update.message.reply_text.call_args[0][0]
        assert "/pause" in reply_text

    def test_reply_contains_resume_command(self):
        """/help reply includes /resume."""
        update, context = _make_update_context()
        asyncio.run(help_command(update, context))
        reply_text = update.message.reply_text.call_args[0][0]
        assert "/resume" in reply_text

    def test_reply_contains_stats_command(self):
        """/help reply includes /stats."""
        update, context = _make_update_context()
        asyncio.run(help_command(update, context))
        reply_text = update.message.reply_text.call_args[0][0]
        assert "/stats" in reply_text

    def test_reply_contains_schedule_command(self):
        """/help reply includes /schedule."""
        update, context = _make_update_context()
        asyncio.run(help_command(update, context))
        reply_text = update.message.reply_text.call_args[0][0]
        assert "/schedule" in reply_text

    def test_reply_mentions_natural_language(self):
        """/help reply mentions natural language support."""
        update, context = _make_update_context()
        asyncio.run(help_command(update, context))
        reply_text = update.message.reply_text.call_args[0][0]
        assert "natural" in reply_text.lower()


class TestUnauthorizedHandler:
    """Tests for unauthorized catch-all handler."""

    def test_replies_unauthorized(self):
        """Unauthorized handler replies with 'Unauthorized' text."""
        update, context = _make_update_context()
        asyncio.run(unauthorized_handler(update, context))
        reply_text = update.message.reply_text.call_args[0][0]
        assert "Unauthorized" in reply_text

    def test_reply_text_called_once(self):
        """Unauthorized handler calls reply_text exactly once."""
        update, context = _make_update_context()
        asyncio.run(unauthorized_handler(update, context))
        update.message.reply_text.assert_called_once()


class TestStatusCommandSuccess:
    """Tests for /status command with successful pipeline status fetch."""

    def test_status_formats_last_run(self):
        """/status reply shows last run time."""
        update, context = _make_update_context()
        mock_status = PipelineStatus(
            last_run_utc="2026-03-07T11:00:00Z",
            articles_fetched=25,
            articles_delivered=12,
            telegram_success=10,
            telegram_failures=2,
            email_success=3,
            sources_active=5,
            run_duration_seconds=8.3,
        )
        with patch(
            "pipeline.bot.handler.fetch_pipeline_status", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_status
            asyncio.run(status_command(update, context))
        reply_text = update.message.reply_text.call_args[0][0]
        assert "2026-03-07T11:00:00Z" in reply_text

    def test_status_formats_articles(self):
        """/status reply shows article counts."""
        update, context = _make_update_context()
        mock_status = PipelineStatus(
            last_run_utc="2026-03-07T11:00:00Z",
            articles_fetched=25,
            articles_delivered=12,
        )
        with patch(
            "pipeline.bot.handler.fetch_pipeline_status", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_status
            asyncio.run(status_command(update, context))
        reply_text = update.message.reply_text.call_args[0][0]
        assert "25" in reply_text
        assert "12" in reply_text

    def test_status_shows_never_when_no_run(self):
        """/status shows 'Never' when last_run_utc is empty."""
        update, context = _make_update_context()
        mock_status = PipelineStatus()
        with patch(
            "pipeline.bot.handler.fetch_pipeline_status", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_status
            asyncio.run(status_command(update, context))
        reply_text = update.message.reply_text.call_args[0][0]
        assert "Never" in reply_text


class TestStatusCommandFailure:
    """Tests for /status command when fetch fails."""

    def test_status_handles_fetch_exception(self):
        """/status replies with error message when fetch_pipeline_status raises."""
        update, context = _make_update_context()
        with patch(
            "pipeline.bot.handler.fetch_pipeline_status", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.side_effect = Exception("network error")
            asyncio.run(status_command(update, context))
        update.message.reply_text.assert_called_once()
        reply_text = update.message.reply_text.call_args[0][0]
        # Should not crash — should give user a message
        assert reply_text  # non-empty response


class TestReadGithubFile:
    """Tests for read_github_file — GitHub Contents API reader."""

    def test_returns_raw_content_on_success(self):
        """read_github_file returns raw response text on 200."""
        from pipeline.bot.status import read_github_file

        with respx.mock:
            respx.get("https://api.github.com/repos/owner/repo/contents/data/test.json").respond(
                200, text='{"key": "value"}'
            )
            result = asyncio.run(read_github_file("data/test.json", "token123", "owner", "repo"))
        assert result == '{"key": "value"}'

    def test_raises_on_non_200(self):
        """read_github_file raises on non-200 responses."""
        import pytest

        from pipeline.bot.status import read_github_file

        with respx.mock:
            respx.get("https://api.github.com/repos/owner/repo/contents/data/missing.json").respond(
                404, text="Not Found"
            )
            with pytest.raises(httpx.HTTPStatusError):
                asyncio.run(read_github_file("data/missing.json", "token123", "owner", "repo"))


class TestFetchPipelineStatus:
    """Tests for fetch_pipeline_status — high-level status fetcher."""

    def test_returns_parsed_status_on_success(self, monkeypatch):
        """fetch_pipeline_status returns PipelineStatus from GitHub API response."""
        from pipeline.bot.status import fetch_pipeline_status

        monkeypatch.setenv("GITHUB_PAT", "testtoken")
        monkeypatch.setenv("GITHUB_OWNER", "owner")
        monkeypatch.setenv("GITHUB_REPO", "repo")

        status_json = json.dumps(
            {
                "last_run_utc": "2026-03-07T11:00:00Z",
                "articles_fetched": 15,
                "articles_delivered": 8,
                "telegram_success": 6,
                "telegram_failures": 1,
                "email_success": 2,
                "sources_active": 4,
                "run_duration_seconds": 5.2,
            }
        )
        with respx.mock:
            respx.get(
                "https://api.github.com/repos/owner/repo/contents/data/pipeline_status.json"
            ).respond(200, text=status_json)
            result = asyncio.run(fetch_pipeline_status())

        assert result.last_run_utc == "2026-03-07T11:00:00Z"
        assert result.articles_fetched == 15
        assert result.telegram_success == 6

    def test_returns_default_on_api_failure(self, monkeypatch):
        """fetch_pipeline_status returns default PipelineStatus on API error."""
        from pipeline.bot.status import fetch_pipeline_status

        monkeypatch.setenv("GITHUB_PAT", "testtoken")
        monkeypatch.setenv("GITHUB_OWNER", "owner")
        monkeypatch.setenv("GITHUB_REPO", "repo")

        with respx.mock:
            respx.get(
                "https://api.github.com/repos/owner/repo/contents/data/pipeline_status.json"
            ).respond(500, text="Internal Server Error")
            result = asyncio.run(fetch_pipeline_status())

        assert result.last_run_utc == ""
        assert result.articles_fetched == 0

    def test_returns_default_on_missing_env_vars(self, monkeypatch):
        """fetch_pipeline_status returns default PipelineStatus when env vars missing."""
        from pipeline.bot.status import fetch_pipeline_status

        monkeypatch.delenv("GITHUB_PAT", raising=False)
        monkeypatch.delenv("GITHUB_OWNER", raising=False)
        monkeypatch.delenv("GITHUB_REPO", raising=False)

        result = asyncio.run(fetch_pipeline_status())
        assert result.last_run_utc == ""
        assert result.articles_fetched == 0


class TestStatusUsage:
    """/status displays free-tier usage section with Actions and AI spend percentages."""

    def test_status_shows_free_tier_usage_section(self):
        """/status response includes 'Free Tier Usage' header."""
        update, context = _make_update_context()
        mock_status = PipelineStatus(
            last_run_utc="2026-03-08T10:00:00Z",
            articles_fetched=20,
            usage_month="2026-03",
            monthly_deliver_runs=10,
            monthly_breaking_runs=50,
            monthly_breaking_alerts=3,
            est_actions_minutes=105.0,
        )
        with (
            patch(
                "pipeline.bot.handler.fetch_pipeline_status", new_callable=AsyncMock
            ) as mock_fetch,
            patch("pipeline.bot.handler.fetch_ai_cost", new_callable=AsyncMock) as mock_ai,
        ):
            mock_fetch.return_value = mock_status
            mock_ai.return_value = AICost(month="2026-03", total_cost_usd=1.50)
            asyncio.run(status_command(update, context))

        reply_text = update.message.reply_text.call_args[0][0]
        assert "Free Tier Usage" in reply_text

    def test_status_shows_actions_minutes(self):
        """/status shows estimated Actions minutes and percentage."""
        update, context = _make_update_context()
        mock_status = PipelineStatus(
            last_run_utc="2026-03-08T10:00:00Z",
            usage_month="2026-03",
            est_actions_minutes=200.0,
        )
        with (
            patch(
                "pipeline.bot.handler.fetch_pipeline_status", new_callable=AsyncMock
            ) as mock_fetch,
            patch("pipeline.bot.handler.fetch_ai_cost", new_callable=AsyncMock) as mock_ai,
        ):
            mock_fetch.return_value = mock_status
            mock_ai.return_value = AICost(month="2026-03", total_cost_usd=0.0)
            asyncio.run(status_command(update, context))

        reply_text = update.message.reply_text.call_args[0][0]
        assert "Actions" in reply_text
        assert "2000" in reply_text
        assert "10%" in reply_text  # 200/2000 = 10%

    def test_status_shows_ai_spend(self):
        """/status shows AI spend and percentage."""
        update, context = _make_update_context()
        mock_status = PipelineStatus(
            last_run_utc="2026-03-08T10:00:00Z",
            usage_month="2026-03",
        )
        with (
            patch(
                "pipeline.bot.handler.fetch_pipeline_status", new_callable=AsyncMock
            ) as mock_fetch,
            patch("pipeline.bot.handler.fetch_ai_cost", new_callable=AsyncMock) as mock_ai,
        ):
            mock_fetch.return_value = mock_status
            mock_ai.return_value = AICost(month="2026-03", total_cost_usd=2.50)
            asyncio.run(status_command(update, context))

        reply_text = update.message.reply_text.call_args[0][0]
        assert "AI spend" in reply_text
        assert "$2.50" in reply_text
        assert "$5.00" in reply_text
        assert "50%" in reply_text  # 2.50/5.00 = 50%

    def test_status_shows_run_counts(self):
        """/status shows deliver and breaking run counts."""
        update, context = _make_update_context()
        mock_status = PipelineStatus(
            last_run_utc="2026-03-08T10:00:00Z",
            usage_month="2026-03",
            monthly_deliver_runs=15,
            monthly_breaking_runs=60,
        )
        with (
            patch(
                "pipeline.bot.handler.fetch_pipeline_status", new_callable=AsyncMock
            ) as mock_fetch,
            patch("pipeline.bot.handler.fetch_ai_cost", new_callable=AsyncMock) as mock_ai,
        ):
            mock_fetch.return_value = mock_status
            mock_ai.return_value = AICost(month="2026-03")
            asyncio.run(status_command(update, context))

        reply_text = update.message.reply_text.call_args[0][0]
        assert "Runs" in reply_text
        assert "15" in reply_text
        assert "60" in reply_text

    def test_status_shows_breaking_alerts(self):
        """/status shows breaking alerts count."""
        update, context = _make_update_context()
        mock_status = PipelineStatus(
            last_run_utc="2026-03-08T10:00:00Z",
            usage_month="2026-03",
            monthly_breaking_alerts=7,
        )
        with (
            patch(
                "pipeline.bot.handler.fetch_pipeline_status", new_callable=AsyncMock
            ) as mock_fetch,
            patch("pipeline.bot.handler.fetch_ai_cost", new_callable=AsyncMock) as mock_ai,
        ):
            mock_fetch.return_value = mock_status
            mock_ai.return_value = AICost(month="2026-03")
            asyncio.run(status_command(update, context))

        reply_text = update.message.reply_text.call_args[0][0]
        assert "Breaking alerts" in reply_text
        assert "7" in reply_text


class TestStatusUsageNoData:
    """When pipeline_status has no usage data, zeroes display gracefully."""

    def test_empty_usage_shows_zeroes(self):
        """/status with empty usage_month still shows usage section with zeroes."""
        update, context = _make_update_context()
        mock_status = PipelineStatus()  # All defaults
        with (
            patch(
                "pipeline.bot.handler.fetch_pipeline_status", new_callable=AsyncMock
            ) as mock_fetch,
            patch("pipeline.bot.handler.fetch_ai_cost", new_callable=AsyncMock) as mock_ai,
        ):
            mock_fetch.return_value = mock_status
            mock_ai.return_value = AICost(month="")
            asyncio.run(status_command(update, context))

        reply_text = update.message.reply_text.call_args[0][0]
        # Should still have usage section, with graceful zeroes
        assert "Free Tier Usage" in reply_text
        assert "0%" in reply_text


class TestStatusAICostFetch:
    """status_command fetches AI cost and falls back gracefully on failure."""

    def test_ai_cost_fetch_failure_shows_zero(self):
        """When fetch_ai_cost raises, AI spend shows $0.00."""
        update, context = _make_update_context()
        mock_status = PipelineStatus(
            last_run_utc="2026-03-08T10:00:00Z",
            usage_month="2026-03",
        )
        with (
            patch(
                "pipeline.bot.handler.fetch_pipeline_status", new_callable=AsyncMock
            ) as mock_fetch,
            patch("pipeline.bot.handler.fetch_ai_cost", new_callable=AsyncMock) as mock_ai,
        ):
            mock_fetch.return_value = mock_status
            mock_ai.side_effect = Exception("API error")
            asyncio.run(status_command(update, context))

        reply_text = update.message.reply_text.call_args[0][0]
        assert "$0.00" in reply_text
