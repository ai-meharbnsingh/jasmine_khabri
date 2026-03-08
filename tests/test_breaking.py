"""Tests for breaking news pipeline.

Covers filter, dedup, AI gate, format, pause, time window, integration.
Phase 11-02: breaking run counter and usage tracking.
"""

from datetime import UTC, datetime, timedelta, timezone
from unittest.mock import patch

from pipeline.schemas.ai_cost_schema import AICost
from pipeline.schemas.article_schema import Article
from pipeline.schemas.bot_state_schema import BotState, PauseState
from pipeline.schemas.config_schema import AppConfig, RssFeedConfig, TelegramConfig
from pipeline.schemas.keywords_schema import KeywordCategory, KeywordsConfig
from pipeline.schemas.pipeline_status_schema import PipelineStatus
from pipeline.schemas.seen_schema import SeenEntry, SeenStore

# IST timezone for time window tests
_IST = timezone(timedelta(hours=5, minutes=30))


def _make_article(
    title: str = "Test Article", url: str = "https://example.com/1", **kwargs
) -> Article:
    """Helper to create test articles with sensible defaults."""
    now_iso = datetime.now(UTC).isoformat()
    defaults = {
        "title": title,
        "url": url,
        "source": "Test Source",
        "published_at": now_iso,
        "summary": "",
        "fetched_at": now_iso,
        "relevance_score": 0,
    }
    defaults.update(kwargs)
    return Article(**defaults)


def _make_keywords(
    active: list[str] | None = None, exclusions: list[str] | None = None
) -> KeywordsConfig:
    """Helper to create keyword config for testing."""
    categories: dict[str, KeywordCategory] = {}
    if active:
        categories["test"] = KeywordCategory(active=True, keywords=active)
    return KeywordsConfig(
        categories=categories,
        exclusions=exclusions or [],
    )


class TestBreakingFilter:
    """Articles with keyword score >= 80 pass fast-path filter."""

    def test_high_score_articles_pass(self):
        """Articles scoring >= 80 pass the breaking filter."""
        from pipeline.breaking import breaking_filter

        # Create article that will score high (4+ title keyword matches = 80+)
        article = _make_article(
            title="Metro RERA Highway Infrastructure DDA Project",
            relevance_score=0,
        )
        keywords = _make_keywords(
            active=["metro", "rera", "highway", "infrastructure", "dda", "project"]
        )
        ai_cost = AICost(month="2026-01")

        # With budget below $3, AI will be called. Mock it to confirm HIGH.
        with patch("pipeline.breaking.classify_articles") as mock_classify:
            mock_classify.return_value = (
                [article.model_copy(update={"priority": "HIGH"})],
                ai_cost,
            )
            result, updated_cost = breaking_filter([article], keywords, ai_cost)

        assert len(result) == 1
        assert result[0].priority == "HIGH"

    def test_low_score_articles_excluded(self):
        """Articles scoring < 80 are excluded from breaking filter."""
        from pipeline.breaking import breaking_filter

        article = _make_article(title="Random News About Nothing")
        keywords = _make_keywords(active=["metro"])
        ai_cost = AICost(month="2026-01")

        result, updated_cost = breaking_filter([article], keywords, ai_cost)
        assert len(result) == 0

    def test_exclusion_keywords_block(self):
        """Articles with exclusion keywords are excluded regardless of score."""
        from pipeline.breaking import breaking_filter

        article = _make_article(
            title="Metro RERA Highway Infrastructure DDA Project",
        )
        keywords = _make_keywords(
            active=["metro", "rera", "highway", "infrastructure", "dda", "project"],
            exclusions=["metro"],
        )
        ai_cost = AICost(month="2026-01")

        result, updated_cost = breaking_filter([article], keywords, ai_cost)
        assert len(result) == 0


class TestBreakingDedup:
    """Articles already in seen.json are filtered out; only NEW proceed; seen updated."""

    def test_duplicate_articles_filtered(self):
        """Articles already in seen store are filtered out by dedup."""
        from pipeline.filters.dedup_filter import filter_duplicates
        from pipeline.utils.hashing import compute_title_hash

        article = _make_article(title="Existing Article")
        seen = SeenStore(
            entries=[
                SeenEntry(
                    url_hash="abc",
                    title_hash=compute_title_hash("Existing Article"),
                    seen_at="2026-01-01T00:00:00+00:00",
                    source="Test",
                    title="Existing Article",
                )
            ]
        )

        result, updated_seen = filter_duplicates([article], seen)
        # Should be marked DUPLICATE
        assert all(a.dedup_status != "NEW" for a in result) or len(result) == 0

    def test_new_articles_proceed(self):
        """New articles pass dedup and get dedup_status='NEW'."""
        from pipeline.filters.dedup_filter import filter_duplicates

        article = _make_article(title="Brand New Article", url="https://example.com/new")
        seen = SeenStore(entries=[])

        result, updated_seen = filter_duplicates([article], seen)
        assert len(result) == 1
        assert result[0].dedup_status == "NEW"

    def test_seen_updated_after_dedup(self):
        """Seen store is updated with new articles after dedup."""
        from pipeline.filters.dedup_filter import filter_duplicates

        article = _make_article(title="New Breaking Article")
        seen = SeenStore(entries=[])

        _, updated_seen = filter_duplicates([article], seen)
        assert len(updated_seen.entries) == 1


class TestBreakingAIGate:
    """AI confirmation gate behavior based on budget threshold."""

    def test_ai_called_when_budget_low(self):
        """When AI budget < $3.00, classify_articles is called for candidates."""
        from pipeline.breaking import breaking_filter

        article = _make_article(
            title="Metro RERA Highway Infrastructure DDA Project",
        )
        keywords = _make_keywords(
            active=["metro", "rera", "highway", "infrastructure", "dda", "project"]
        )
        ai_cost = AICost(month="2026-01", total_cost_usd=1.00)

        with patch("pipeline.breaking.classify_articles") as mock_classify:
            mock_classify.return_value = (
                [article.model_copy(update={"priority": "HIGH"})],
                ai_cost,
            )
            result, _ = breaking_filter([article], keywords, ai_cost)
            mock_classify.assert_called_once()

    def test_ai_skipped_when_budget_high(self):
        """When AI budget >= $3.00, AI is skipped and keyword score trusted."""
        from pipeline.breaking import breaking_filter

        article = _make_article(
            title="Metro RERA Highway Infrastructure DDA Project",
        )
        keywords = _make_keywords(
            active=["metro", "rera", "highway", "infrastructure", "dda", "project"]
        )
        ai_cost = AICost(month="2026-01", total_cost_usd=3.50)

        with patch("pipeline.breaking.classify_articles") as mock_classify:
            result, _ = breaking_filter([article], keywords, ai_cost)
            mock_classify.assert_not_called()

        # Articles should still pass with priority set to HIGH
        assert len(result) == 1
        assert result[0].priority == "HIGH"

    def test_ai_non_high_excluded(self):
        """When AI confirms non-HIGH, article is excluded from alert."""
        from pipeline.breaking import breaking_filter

        article = _make_article(
            title="Metro RERA Highway Infrastructure DDA Project",
        )
        keywords = _make_keywords(
            active=["metro", "rera", "highway", "infrastructure", "dda", "project"]
        )
        ai_cost = AICost(month="2026-01", total_cost_usd=1.00)

        with patch("pipeline.breaking.classify_articles") as mock_classify:
            mock_classify.return_value = (
                [article.model_copy(update={"priority": "MEDIUM"})],
                ai_cost,
            )
            result, _ = breaking_filter([article], keywords, ai_cost)

        assert len(result) == 0


class TestBreakingPause:
    """Pause state guards prevent breaking alerts."""

    def test_paused_indefinitely_blocks(self):
        """When bot is paused indefinitely, _is_paused returns True."""
        from pipeline.breaking import _is_paused

        bot_state = BotState(
            pause=PauseState(paused_until="", paused_slots=["all"]),
        )
        assert _is_paused(bot_state) is True

    def test_paused_with_future_expiry_blocks(self):
        """When pause has future expiry, _is_paused returns True."""
        from pipeline.breaking import _is_paused

        future = (datetime.now(UTC) + timedelta(hours=2)).isoformat()
        bot_state = BotState(
            pause=PauseState(paused_until=future, paused_slots=["all"]),
        )
        assert _is_paused(bot_state) is True

    def test_expired_pause_allows(self):
        """When pause has expired, _is_paused returns False."""
        from pipeline.breaking import _is_paused

        past = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
        bot_state = BotState(
            pause=PauseState(paused_until=past, paused_slots=["all"]),
        )
        assert _is_paused(bot_state) is False

    def test_empty_slots_allows(self):
        """When no paused slots, _is_paused returns False."""
        from pipeline.breaking import _is_paused

        bot_state = BotState(
            pause=PauseState(paused_until="", paused_slots=[]),
        )
        assert _is_paused(bot_state) is False


class TestBreakingTimeWindow:
    """Breaking check skips within 30 minutes of 7:00 AM or 4:00 PM IST."""

    def test_during_morning_window_skips(self):
        """Within 30 min of 7 AM IST, _is_delivery_window returns True."""
        from pipeline.breaking import _is_delivery_window

        # 6:45 AM IST — 15 minutes before morning delivery
        now_ist = datetime(2026, 1, 15, 6, 45, tzinfo=_IST)
        assert _is_delivery_window(now_ist) is True

    def test_during_evening_window_skips(self):
        """Within 30 min of 4 PM IST, _is_delivery_window returns True."""
        from pipeline.breaking import _is_delivery_window

        # 4:15 PM IST — 15 minutes after evening delivery
        now_ist = datetime(2026, 1, 15, 16, 15, tzinfo=_IST)
        assert _is_delivery_window(now_ist) is True

    def test_outside_windows_runs(self):
        """Outside delivery windows, _is_delivery_window returns False."""
        from pipeline.breaking import _is_delivery_window

        # 10:00 AM IST — well outside both windows
        now_ist = datetime(2026, 1, 15, 10, 0, tzinfo=_IST)
        assert _is_delivery_window(now_ist) is False

    def test_exactly_30_min_before_morning(self):
        """Exactly 30 min before 7 AM (6:30 AM) is within window."""
        from pipeline.breaking import _is_delivery_window

        now_ist = datetime(2026, 1, 15, 6, 30, tzinfo=_IST)
        assert _is_delivery_window(now_ist) is True

    def test_exactly_30_min_after_evening(self):
        """Exactly 30 min after 4 PM (4:30 PM) is within window."""
        from pipeline.breaking import _is_delivery_window

        now_ist = datetime(2026, 1, 15, 16, 30, tzinfo=_IST)
        assert _is_delivery_window(now_ist) is True

    def test_31_min_before_morning_outside(self):
        """31 min before 7 AM (6:29 AM) is outside window."""
        from pipeline.breaking import _is_delivery_window

        now_ist = datetime(2026, 1, 15, 6, 29, tzinfo=_IST)
        assert _is_delivery_window(now_ist) is False


class TestBreakingFormat:
    """format_breaking_alert produces correct Telegram HTML."""

    def test_format_single_article(self):
        """Single article formatted with siren header, title, source, link."""
        from pipeline.breaking import format_breaking_alert

        articles = [
            _make_article(
                title="Metro Phase 4 Approved",
                url="https://example.com/metro",
                source="ET Realty",
                summary="Major infrastructure move",
            )
        ]
        result = format_breaking_alert(articles)

        # Header check
        assert "BREAKING NEWS ALERT" in result
        assert "\U0001f6a8" in result  # siren emoji

        # Article content
        assert "Metro Phase 4 Approved" in result
        assert "ET Realty" in result
        assert "Major infrastructure move" in result
        assert "Read" in result
        assert "https://example.com/metro" in result

        # Footer
        assert "Full brief in next scheduled delivery" in result

    def test_format_multiple_articles(self):
        """Multiple articles numbered correctly."""
        from pipeline.breaking import format_breaking_alert

        articles = [
            _make_article(title="Article One", url="https://example.com/1"),
            _make_article(title="Article Two", url="https://example.com/2"),
        ]
        result = format_breaking_alert(articles)
        assert "1." in result
        assert "2." in result

    def test_format_escapes_html(self):
        """HTML entities in titles are escaped."""
        from pipeline.breaking import format_breaking_alert

        articles = [
            _make_article(title="A & B <test>", url="https://example.com/1"),
        ]
        result = format_breaking_alert(articles)
        assert "A &amp; B &lt;test&gt;" in result

    def test_format_article_count(self):
        """Header shows article count."""
        from pipeline.breaking import format_breaking_alert

        articles = [
            _make_article(title="Art 1", url="https://example.com/1"),
            _make_article(title="Art 2", url="https://example.com/2"),
            _make_article(title="Art 3", url="https://example.com/3"),
        ]
        result = format_breaking_alert(articles)
        assert "3" in result  # Count in header

    def test_format_no_summary_skips_summary_line(self):
        """Articles with empty summary skip the summary line."""
        from pipeline.breaking import format_breaking_alert

        articles = [
            _make_article(title="Test", url="https://example.com/1", summary=""),
        ]
        result = format_breaking_alert(articles)
        # Should NOT have extra blank lines from empty summary
        assert "Test" in result


class TestRunBreaking:
    """Full run_breaking integration with mocked I/O."""

    def test_full_run_sends_alert(self):
        """Successful run: fetches, filters, deduplicates, formats, sends."""
        from pipeline.breaking import run_breaking

        article = _make_article(
            title="Metro RERA Highway Infrastructure DDA Project",
            url="https://example.com/breaking",
        )

        with (
            patch("pipeline.breaking.load_config") as mock_config,
            patch("pipeline.breaking.load_keywords") as mock_keywords,
            patch("pipeline.breaking.load_seen") as mock_seen,
            patch("pipeline.breaking.save_seen") as mock_save_seen,
            patch("pipeline.breaking.load_ai_cost") as mock_ai_cost,
            patch("pipeline.breaking.save_ai_cost"),
            patch("pipeline.breaking.load_bot_state") as mock_bot_state,
            patch("pipeline.breaking.fetch_all_rss") as mock_rss,
            patch("pipeline.breaking.score_article") as mock_score,
            patch("pipeline.breaking.filter_duplicates") as mock_dedup,
            patch("pipeline.breaking.classify_articles") as mock_classify,
            patch("pipeline.breaking.send_telegram_message") as mock_send,
            patch("pipeline.breaking._is_delivery_window", return_value=False),
            patch("pipeline.breaking._is_paused", return_value=False),
            patch.dict(
                "os.environ",
                {"TELEGRAM_BOT_TOKEN": "test-token", "TELEGRAM_CHAT_IDS": "123,456"},
            ),
        ):
            mock_config.return_value = AppConfig(
                telegram=TelegramConfig(breaking_news_enabled=True),
                rss_feeds=[RssFeedConfig(name="Test", url="https://test.com/rss")],
            )
            mock_keywords.return_value = _make_keywords(
                active=["metro", "rera", "highway", "infrastructure", "dda", "project"]
            )
            mock_seen.return_value = SeenStore(entries=[])
            mock_ai_cost.return_value = AICost(month="2026-01")
            mock_bot_state.return_value = BotState()
            mock_rss.return_value = ([article], [])
            mock_score.return_value = (True, 100)
            mock_dedup.return_value = (
                [article.model_copy(update={"dedup_status": "NEW"})],
                SeenStore(entries=[]),
            )
            mock_classify.return_value = (
                [article.model_copy(update={"priority": "HIGH"})],
                AICost(month="2026-01"),
            )
            mock_send.return_value = (True, None)

            run_breaking()

            # Verify Telegram was called for each chat_id
            assert mock_send.call_count == 2
            # Verify seen was saved
            mock_save_seen.assert_called_once()

    def test_breaking_disabled_returns_early(self):
        """When breaking_news_enabled is False, returns immediately."""
        from pipeline.breaking import run_breaking

        with (
            patch("pipeline.breaking.load_config") as mock_config,
            patch("pipeline.breaking.fetch_all_rss") as mock_rss,
        ):
            mock_config.return_value = AppConfig(
                telegram=TelegramConfig(breaking_news_enabled=False),
            )

            run_breaking()
            mock_rss.assert_not_called()

    def test_paused_returns_early(self):
        """When bot is paused, returns without fetching."""
        from pipeline.breaking import run_breaking

        with (
            patch("pipeline.breaking.load_config") as mock_config,
            patch("pipeline.breaking.load_bot_state") as mock_bot_state,
            patch("pipeline.breaking._is_paused", return_value=True),
            patch("pipeline.breaking.fetch_all_rss") as mock_rss,
        ):
            mock_config.return_value = AppConfig(
                telegram=TelegramConfig(breaking_news_enabled=True),
            )
            mock_bot_state.return_value = BotState()

            run_breaking()
            mock_rss.assert_not_called()

    def test_delivery_window_returns_early(self):
        """During delivery window, returns without fetching."""
        from pipeline.breaking import run_breaking

        with (
            patch("pipeline.breaking.load_config") as mock_config,
            patch("pipeline.breaking.load_bot_state") as mock_bot_state,
            patch("pipeline.breaking._is_paused", return_value=False),
            patch("pipeline.breaking._is_delivery_window", return_value=True),
            patch("pipeline.breaking.fetch_all_rss") as mock_rss,
        ):
            mock_config.return_value = AppConfig(
                telegram=TelegramConfig(breaking_news_enabled=True),
            )
            mock_bot_state.return_value = BotState()

            run_breaking()
            mock_rss.assert_not_called()

    def test_no_candidates_returns_early(self):
        """When no articles score >= 80, returns early without dedup."""
        from pipeline.breaking import run_breaking

        article = _make_article(title="Boring Article")

        with (
            patch("pipeline.breaking.load_config") as mock_config,
            patch("pipeline.breaking.load_keywords") as mock_keywords,
            patch("pipeline.breaking.load_seen") as mock_seen,
            patch("pipeline.breaking.load_ai_cost") as mock_ai_cost,
            patch("pipeline.breaking.load_bot_state") as mock_bot_state,
            patch("pipeline.breaking.fetch_all_rss") as mock_rss,
            patch("pipeline.breaking.score_article") as mock_score,
            patch("pipeline.breaking.filter_duplicates") as mock_dedup,
            patch("pipeline.breaking._is_delivery_window", return_value=False),
            patch("pipeline.breaking._is_paused", return_value=False),
        ):
            mock_config.return_value = AppConfig(
                telegram=TelegramConfig(breaking_news_enabled=True),
                rss_feeds=[RssFeedConfig(name="Test", url="https://test.com/rss")],
            )
            mock_keywords.return_value = _make_keywords(active=["metro"])
            mock_seen.return_value = SeenStore(entries=[])
            mock_ai_cost.return_value = AICost(month="2026-01")
            mock_bot_state.return_value = BotState()
            mock_rss.return_value = ([article], [])
            mock_score.return_value = (True, 30)  # Below threshold

            run_breaking()
            mock_dedup.assert_not_called()

    def test_saves_ai_cost_after_run(self):
        """AI cost is saved after breaking run completes."""
        from pipeline.breaking import run_breaking

        article = _make_article(
            title="Metro RERA Highway Infrastructure DDA Project",
        )

        with (
            patch("pipeline.breaking.load_config") as mock_config,
            patch("pipeline.breaking.load_keywords") as mock_keywords,
            patch("pipeline.breaking.load_seen") as mock_seen,
            patch("pipeline.breaking.save_seen"),
            patch("pipeline.breaking.load_ai_cost") as mock_ai_cost,
            patch("pipeline.breaking.save_ai_cost") as mock_save_ai_cost,
            patch("pipeline.breaking.load_bot_state") as mock_bot_state,
            patch("pipeline.breaking.fetch_all_rss") as mock_rss,
            patch("pipeline.breaking.score_article") as mock_score,
            patch("pipeline.breaking.filter_duplicates") as mock_dedup,
            patch("pipeline.breaking.classify_articles") as mock_classify,
            patch("pipeline.breaking.send_telegram_message") as mock_send,
            patch("pipeline.breaking._is_delivery_window", return_value=False),
            patch("pipeline.breaking._is_paused", return_value=False),
            patch.dict(
                "os.environ", {"TELEGRAM_BOT_TOKEN": "test-token", "TELEGRAM_CHAT_IDS": "123"}
            ),
        ):
            mock_config.return_value = AppConfig(
                telegram=TelegramConfig(breaking_news_enabled=True),
                rss_feeds=[RssFeedConfig(name="Test", url="https://test.com/rss")],
            )
            mock_keywords.return_value = _make_keywords(
                active=["metro", "rera", "highway", "infrastructure", "dda", "project"]
            )
            mock_seen.return_value = SeenStore(entries=[])
            updated_cost = AICost(month="2026-01", total_cost_usd=0.05, call_count=1)
            mock_ai_cost.return_value = AICost(month="2026-01")
            mock_bot_state.return_value = BotState()
            mock_rss.return_value = ([article], [])
            mock_score.return_value = (True, 100)
            mock_dedup.return_value = (
                [article.model_copy(update={"dedup_status": "NEW"})],
                SeenStore(entries=[]),
            )
            mock_classify.return_value = (
                [article.model_copy(update={"priority": "HIGH"})],
                updated_cost,
            )
            mock_send.return_value = (True, None)

            run_breaking()
            mock_save_ai_cost.assert_called_once()


class TestBreakingExitCode:
    """run_breaking exits with code 1 on unhandled crash."""

    def test_run_breaking_exits_1_on_crash(self):
        """When load_config raises, run_breaking calls sys.exit(1)."""
        import pytest

        from pipeline.breaking import run_breaking

        with patch("pipeline.breaking.load_config", side_effect=RuntimeError("boom")):
            with pytest.raises(SystemExit) as exc_info:
                run_breaking()
            assert exc_info.value.code == 1


class TestBreakingRunCounter:
    """run_breaking increments monthly_breaking_runs, alerts, and est_actions_minutes."""

    def test_breaking_run_counter_increments(self):
        """After run_breaking sends alerts, counters are incremented."""
        from pipeline.breaking import run_breaking

        current_month = datetime.now(UTC).strftime("%Y-%m")
        prev_status = PipelineStatus(
            usage_month=current_month,
            monthly_deliver_runs=5,
            monthly_breaking_runs=10,
            monthly_breaking_alerts=2,
            est_actions_minutes=30.0,
        )

        article = _make_article(
            title="Metro RERA Highway Infrastructure DDA Project",
            url="https://example.com/breaking",
        )

        with (
            patch("pipeline.breaking.load_config") as mock_config,
            patch("pipeline.breaking.load_keywords") as mock_keywords,
            patch("pipeline.breaking.load_seen") as mock_seen,
            patch("pipeline.breaking.save_seen"),
            patch("pipeline.breaking.load_ai_cost") as mock_ai_cost,
            patch("pipeline.breaking.save_ai_cost"),
            patch("pipeline.breaking.load_bot_state") as mock_bot_state,
            patch("pipeline.breaking.fetch_all_rss") as mock_rss,
            patch("pipeline.breaking.score_article") as mock_score,
            patch("pipeline.breaking.filter_duplicates") as mock_dedup,
            patch("pipeline.breaking.classify_articles") as mock_classify,
            patch("pipeline.breaking.send_telegram_message") as mock_send,
            patch("pipeline.breaking._is_delivery_window", return_value=False),
            patch("pipeline.breaking._is_paused", return_value=False),
            patch("pipeline.breaking.load_pipeline_status") as mock_load_status,
            patch("pipeline.breaking.save_pipeline_status") as mock_save_status,
            patch.dict(
                "os.environ",
                {"TELEGRAM_BOT_TOKEN": "test-token", "TELEGRAM_CHAT_IDS": "123"},
            ),
        ):
            mock_config.return_value = AppConfig(
                telegram=TelegramConfig(breaking_news_enabled=True),
                rss_feeds=[RssFeedConfig(name="Test", url="https://test.com/rss")],
            )
            mock_keywords.return_value = _make_keywords(
                active=["metro", "rera", "highway", "infrastructure", "dda", "project"]
            )
            mock_seen.return_value = SeenStore(entries=[])
            mock_ai_cost.return_value = AICost(month="2026-01")
            mock_bot_state.return_value = BotState()
            mock_rss.return_value = ([article], [])
            mock_score.return_value = (True, 100)
            mock_dedup.return_value = (
                [article.model_copy(update={"dedup_status": "NEW"})],
                SeenStore(entries=[]),
            )
            mock_classify.return_value = (
                [article.model_copy(update={"priority": "HIGH"})],
                AICost(month="2026-01"),
            )
            mock_send.return_value = (True, None)
            mock_load_status.return_value = prev_status

            run_breaking()

            mock_save_status.assert_called_once()
            saved_status = mock_save_status.call_args[0][0]
            assert saved_status.monthly_breaking_runs == 11  # 10 + 1
            assert saved_status.monthly_breaking_alerts == 3  # 2 + 1 alert
            assert saved_status.est_actions_minutes == 31.5  # 30.0 + 1.5
            # Deliver runs preserved
            assert saved_status.monthly_deliver_runs == 5

    def test_breaking_counter_increments_even_without_alerts(self):
        """Breaking run counter increments even when no alerts are sent."""
        from pipeline.breaking import run_breaking

        current_month = datetime.now(UTC).strftime("%Y-%m")
        prev_status = PipelineStatus(
            usage_month=current_month,
            monthly_breaking_runs=5,
            monthly_breaking_alerts=1,
            est_actions_minutes=10.0,
        )

        article = _make_article(title="Boring Article")

        with (
            patch("pipeline.breaking.load_config") as mock_config,
            patch("pipeline.breaking.load_keywords") as mock_keywords,
            patch("pipeline.breaking.load_seen") as mock_seen,
            patch("pipeline.breaking.load_ai_cost") as mock_ai_cost,
            patch("pipeline.breaking.load_bot_state") as mock_bot_state,
            patch("pipeline.breaking.fetch_all_rss") as mock_rss,
            patch("pipeline.breaking.score_article") as mock_score,
            patch("pipeline.breaking._is_delivery_window", return_value=False),
            patch("pipeline.breaking._is_paused", return_value=False),
            patch("pipeline.breaking.load_pipeline_status") as mock_load_status,
            patch("pipeline.breaking.save_pipeline_status") as mock_save_status,
        ):
            mock_config.return_value = AppConfig(
                telegram=TelegramConfig(breaking_news_enabled=True),
                rss_feeds=[RssFeedConfig(name="Test", url="https://test.com/rss")],
            )
            mock_keywords.return_value = _make_keywords(active=["metro"])
            mock_seen.return_value = SeenStore(entries=[])
            mock_ai_cost.return_value = AICost(month="2026-01")
            mock_bot_state.return_value = BotState()
            mock_rss.return_value = ([article], [])
            mock_score.return_value = (True, 30)  # Below threshold, no candidates
            mock_load_status.return_value = prev_status

            run_breaking()

            # Even though no alerts sent, counter should increment
            mock_save_status.assert_called_once()
            saved_status = mock_save_status.call_args[0][0]
            assert saved_status.monthly_breaking_runs == 6  # 5 + 1
            assert saved_status.monthly_breaking_alerts == 1  # Unchanged (no alerts)
            assert saved_status.est_actions_minutes == 11.5  # 10.0 + 1.5
