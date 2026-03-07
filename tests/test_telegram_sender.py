"""Tests for Telegram message delivery — HTML formatting, chunking, API sender, and orchestrator."""

import logging
from unittest.mock import patch

import httpx
import respx

from pipeline.deliverers.telegram_sender import (
    _escape_html,
    chunk_message,
    deliver_articles,
    format_article_html,
    format_delivery_message,
    get_delivery_period,
    send_telegram_message,
)
from pipeline.schemas.article_schema import Article
from pipeline.schemas.config_schema import AppConfig


def _make_article(
    title: str = "Test Article",
    url: str = "https://example.com/article",
    source: str = "Test Source",
    summary: str = "A test summary.",
    location: str = "",
    project_name: str = "",
    budget_amount: str = "",
    authority: str = "",
    priority: str = "HIGH",
    dedup_status: str = "NEW",
) -> Article:
    """Helper to create a test article with configurable fields."""
    return Article(
        title=title,
        url=url,
        source=source,
        published_at="2026-03-07T00:00:00Z",
        fetched_at="2026-03-07T00:00:00Z",
        summary=summary,
        location=location,
        project_name=project_name,
        budget_amount=budget_amount,
        authority=authority,
        priority=priority,
        dedup_status=dedup_status,
    )


class TestEscapeHtml:
    """Test HTML escaping for Telegram messages."""

    def test_escapes_ampersand_lt_gt(self):
        """AT&T <Corp> -> AT&amp;T &lt;Corp&gt;"""
        assert _escape_html("AT&T <Corp>") == "AT&amp;T &lt;Corp&gt;"

    def test_no_change_for_safe_text(self):
        """Normal text passes through unchanged."""
        assert _escape_html("normal text") == "normal text"

    def test_empty_string(self):
        """Empty string returns empty string."""
        assert _escape_html("") == ""

    def test_ampersand_first_order(self):
        """& must be escaped first to avoid double-escaping."""
        result = _escape_html("A&B <C>")
        assert "&amp;" in result
        assert "&lt;" in result
        assert "&gt;" in result
        # Must NOT have &amp;lt; (double-escaped)
        assert "&amp;lt;" not in result


class TestFormatArticleHtml:
    """Test single article HTML formatting."""

    def test_full_article_with_all_fields(self):
        """Article with all fields produces complete HTML block."""
        article = _make_article(
            title="New Metro Line",
            source="ET Realty",
            summary="Delhi metro extends to airport.",
            location="Delhi",
            project_name="Metro Phase IV",
            budget_amount="Rs 5000 Cr",
            authority="DMRC",
        )
        html = format_article_html(article, 1)
        assert "1. <b>New Metro Line</b>" in html
        assert "<i>ET Realty</i>" in html
        assert "Delhi" in html
        assert "Delhi metro extends to airport." in html
        assert "Rs 5000 Cr" in html
        assert "DMRC" in html
        assert '<a href="https://example.com/article">Read</a>' in html

    def test_article_no_entities_omits_entity_line(self):
        """Article without entities omits entity line entirely."""
        article = _make_article(
            title="Simple News",
            summary="Just a summary.",
        )
        html = format_article_html(article, 3)
        assert "3. <b>Simple News</b>" in html
        assert "Budget" not in html
        assert "Authority" not in html

    def test_article_no_summary_omits_summary_line(self):
        """Article without summary omits summary line."""
        article = _make_article(title="No Summary News", summary="")
        html = format_article_html(article, 5)
        assert "5. <b>No Summary News</b>" in html
        # Should have title, source, and Read link but no extra blank lines for summary

    def test_url_with_ampersand_escaped(self):
        """Ampersand in URL is escaped in href."""
        article = _make_article(
            url="https://example.com/article?a=1&b=2",
        )
        html = format_article_html(article, 1)
        assert "a=1&amp;b=2" in html

    def test_title_with_special_chars_escaped(self):
        """Special characters in title are escaped."""
        article = _make_article(title="<Bold> & Beautiful")
        html = format_article_html(article, 1)
        assert "&lt;Bold&gt; &amp; Beautiful" in html

    def test_partial_entities_budget_only(self):
        """When only budget is present, authority is not shown."""
        article = _make_article(budget_amount="Rs 100 Cr")
        html = format_article_html(article, 1)
        assert "Rs 100 Cr" in html
        assert "Authority" not in html

    def test_partial_entities_authority_only(self):
        """When only authority is present, budget is not shown."""
        article = _make_article(authority="NHAI")
        html = format_article_html(article, 1)
        assert "NHAI" in html
        assert "Budget" not in html

    def test_location_appended_to_source(self):
        """Location is appended after source with separator."""
        article = _make_article(source="ET Realty", location="Mumbai")
        html = format_article_html(article, 1)
        assert "ET Realty" in html
        assert "Mumbai" in html


class TestGetDeliveryPeriod:
    """Test morning/evening period detection."""

    def test_morning_before_noon_ist(self):
        """IST hour < 12 returns Morning."""
        from datetime import datetime, timedelta, timezone

        ist = timezone(timedelta(hours=5, minutes=30))
        morning_time = datetime(2026, 3, 7, 7, 0, 0, tzinfo=ist)
        with patch("pipeline.deliverers.telegram_sender.datetime") as mock_dt:
            mock_dt.now.return_value = morning_time
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            assert get_delivery_period() == "Morning"

    def test_evening_after_noon_ist(self):
        """IST hour >= 12 returns Evening."""
        from datetime import datetime, timedelta, timezone

        ist = timezone(timedelta(hours=5, minutes=30))
        evening_time = datetime(2026, 3, 7, 16, 0, 0, tzinfo=ist)
        with patch("pipeline.deliverers.telegram_sender.datetime") as mock_dt:
            mock_dt.now.return_value = evening_time
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            assert get_delivery_period() == "Evening"


class TestFormatDeliveryMessage:
    """Test full message formatting."""

    def test_full_message_with_all_tiers(self):
        """Message with all tiers has header, sections, footer."""
        high = [_make_article(title="High Story", priority="HIGH")]
        medium = [_make_article(title="Med Story", priority="MEDIUM")]
        low = [_make_article(title="Low Story", priority="LOW")]
        chunks = format_delivery_message(high, medium, low, period="Morning")
        full_msg = "\n".join(chunks)
        assert "Khabri" in full_msg
        assert "Morning" in full_msg
        assert "HIGH" in full_msg
        assert "MEDIUM" in full_msg
        assert "LOW" in full_msg
        assert "High Story" in full_msg
        assert "Med Story" in full_msg
        assert "Low Story" in full_msg

    def test_empty_tier_omitted(self):
        """Sections with 0 articles are not in the output."""
        high = [_make_article(title="Only High", priority="HIGH")]
        chunks = format_delivery_message(high, [], [], period="Morning")
        full_msg = "\n".join(chunks)
        assert "HIGH" in full_msg
        assert "MEDIUM" not in full_msg
        assert "LOW" not in full_msg

    def test_continuous_numbering(self):
        """Articles are numbered continuously across sections."""
        high = [_make_article(title=f"High {i}", priority="HIGH") for i in range(2)]
        medium = [_make_article(title="Med 0", priority="MEDIUM")]
        low = [_make_article(title="Low 0", priority="LOW")]
        chunks = format_delivery_message(high, medium, low, period="Morning")
        full_msg = "\n".join(chunks)
        assert "1. <b>High 0</b>" in full_msg
        assert "2. <b>High 1</b>" in full_msg
        assert "3. <b>Med 0</b>" in full_msg
        assert "4. <b>Low 0</b>" in full_msg

    def test_header_contains_story_count(self):
        """Header shows total story count."""
        high = [_make_article(priority="HIGH")]
        medium = [_make_article(priority="MEDIUM")]
        chunks = format_delivery_message(high, medium, [], period="Evening")
        full_msg = "\n".join(chunks)
        # Should contain count info
        assert "2" in full_msg  # 2 total stories

    def test_footer_contains_next_delivery(self):
        """Footer shows next delivery time."""
        high = [_make_article(priority="HIGH")]
        chunks = format_delivery_message(high, [], [], period="Morning")
        full_msg = "\n".join(chunks)
        assert "4:00 PM" in full_msg  # Morning -> next is 4:00 PM

    def test_footer_evening_shows_morning_next(self):
        """Evening footer shows 7:00 AM as next delivery."""
        high = [_make_article(priority="HIGH")]
        chunks = format_delivery_message(high, [], [], period="Evening")
        full_msg = "\n".join(chunks)
        assert "7:00 AM" in full_msg


class TestChunkMessage:
    """Test message chunking at article boundaries."""

    def test_single_chunk_when_under_limit(self):
        """Short message stays as single chunk."""
        header = "Header\n---"
        blocks = ["Article 1 text", "Article 2 text"]
        footer = "---\nFooter"
        chunks = chunk_message(header, blocks, footer, max_chars=4096)
        assert len(chunks) == 1
        assert "Header" in chunks[0]
        assert "Footer" in chunks[0]

    def test_splits_at_article_boundary(self):
        """Long message splits between articles, not mid-article."""
        header = "H" * 20
        blocks = ["A" * 80, "B" * 80, "C" * 80]
        footer = "F" * 20
        # max_chars small enough to force splitting
        chunks = chunk_message(header, blocks, footer, max_chars=150)
        assert len(chunks) > 1
        # Each chunk is under limit
        for chunk in chunks:
            assert len(chunk) <= 150

    def test_header_in_first_chunk_only(self):
        """Header appears only in the first chunk."""
        header = "HEADER_MARKER"
        blocks = ["A" * 80, "B" * 80, "C" * 80]
        footer = "FOOTER_MARKER"
        chunks = chunk_message(header, blocks, footer, max_chars=150)
        assert "HEADER_MARKER" in chunks[0]
        for chunk in chunks[1:]:
            assert "HEADER_MARKER" not in chunk

    def test_footer_in_last_chunk_only(self):
        """Footer appears only in the last chunk."""
        header = "HEADER_MARKER"
        blocks = ["A" * 80, "B" * 80, "C" * 80]
        footer = "FOOTER_MARKER"
        chunks = chunk_message(header, blocks, footer, max_chars=150)
        assert "FOOTER_MARKER" in chunks[-1]
        for chunk in chunks[:-1]:
            assert "FOOTER_MARKER" not in chunk


# ---------------------------------------------------------------------------
# Telegram API send_telegram_message tests
# ---------------------------------------------------------------------------

_TELEGRAM_SEND_URL = "https://api.telegram.org/bot{token}/sendMessage"


class TestSendTelegramMessage:
    """Tests for send_telegram_message HTTP calls."""

    @respx.mock
    def test_success_returns_true(self):
        """HTTP 200 with {"ok": true} returns (True, None)."""
        respx.post("https://api.telegram.org/botTEST_TOKEN/sendMessage").mock(
            return_value=httpx.Response(200, json={"ok": True, "result": {}})
        )
        ok, err = send_telegram_message("TEST_TOKEN", "12345", "Hello")
        assert ok is True
        assert err is None

    @respx.mock
    def test_success_ok_false_returns_error(self):
        """HTTP 200 with ok=false returns (False, description)."""
        respx.post("https://api.telegram.org/botTEST_TOKEN/sendMessage").mock(
            return_value=httpx.Response(
                200, json={"ok": False, "description": "Bad Request: chat not found"}
            )
        )
        ok, err = send_telegram_message("TEST_TOKEN", "12345", "Hello")
        assert ok is False
        assert "Bad Request" in err

    @respx.mock
    @patch("pipeline.deliverers.telegram_sender.time.sleep")
    def test_429_retries_once_then_succeeds(self, mock_sleep):
        """429 triggers single retry; success on retry returns (True, None)."""
        route = respx.post("https://api.telegram.org/botTEST_TOKEN/sendMessage")
        route.side_effect = [
            httpx.Response(429, json={"ok": False, "description": "Too Many Requests"}),
            httpx.Response(200, json={"ok": True, "result": {}}),
        ]
        ok, err = send_telegram_message("TEST_TOKEN", "12345", "Hello")
        assert ok is True
        assert err is None
        assert mock_sleep.call_count == 1
        mock_sleep.assert_called_with(2)

    @respx.mock
    @patch("pipeline.deliverers.telegram_sender.time.sleep")
    def test_429_retries_once_then_fails(self, mock_sleep):
        """429 on both attempts returns (False, 'rate limited (429)')."""
        respx.post("https://api.telegram.org/botTEST_TOKEN/sendMessage").mock(
            return_value=httpx.Response(429, json={"ok": False, "description": "Too Many Requests"})
        )
        ok, err = send_telegram_message("TEST_TOKEN", "12345", "Hello")
        assert ok is False
        assert "429" in err
        assert mock_sleep.call_count == 1

    @respx.mock
    def test_http_400_returns_error(self):
        """HTTP 400 returns (False, 'HTTP 400')."""
        respx.post("https://api.telegram.org/botTEST_TOKEN/sendMessage").mock(
            return_value=httpx.Response(400, json={"ok": False, "description": "Bad Request"})
        )
        ok, err = send_telegram_message("TEST_TOKEN", "12345", "Hello")
        assert ok is False
        assert "400" in err

    @respx.mock
    @patch("pipeline.deliverers.telegram_sender.time.sleep")
    def test_network_error_retries_once_then_succeeds(self, mock_sleep):
        """Network error triggers single retry; success on retry."""
        route = respx.post("https://api.telegram.org/botTEST_TOKEN/sendMessage")
        route.side_effect = [
            httpx.ConnectError("Connection refused"),
            httpx.Response(200, json={"ok": True, "result": {}}),
        ]
        ok, err = send_telegram_message("TEST_TOKEN", "12345", "Hello")
        assert ok is True
        assert err is None
        assert mock_sleep.call_count == 1

    @respx.mock
    @patch("pipeline.deliverers.telegram_sender.time.sleep")
    def test_network_error_retries_once_then_fails(self, mock_sleep):
        """Network error on both attempts returns (False, error message)."""
        respx.post("https://api.telegram.org/botTEST_TOKEN/sendMessage").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        ok, err = send_telegram_message("TEST_TOKEN", "12345", "Hello")
        assert ok is False
        assert err is not None
        assert mock_sleep.call_count == 1

    @respx.mock
    @patch("pipeline.deliverers.telegram_sender.time.sleep")
    def test_timeout_error_retries_once(self, mock_sleep):
        """Timeout triggers retry like other network errors."""
        respx.post("https://api.telegram.org/botTEST_TOKEN/sendMessage").mock(
            side_effect=httpx.TimeoutException("Request timed out")
        )
        ok, err = send_telegram_message("TEST_TOKEN", "12345", "Hello")
        assert ok is False
        assert err is not None
        assert mock_sleep.call_count == 1

    @respx.mock
    def test_sends_html_parse_mode(self):
        """Request payload includes parse_mode=HTML and link preview disabled."""
        route = respx.post("https://api.telegram.org/botTEST_TOKEN/sendMessage").mock(
            return_value=httpx.Response(200, json={"ok": True, "result": {}})
        )
        send_telegram_message("TEST_TOKEN", "12345", "<b>bold</b>")
        assert route.called
        request = route.calls[0].request
        import json

        body = json.loads(request.content)
        assert body["parse_mode"] == "HTML"
        assert body["link_preview_options"]["is_disabled"] is True
        assert body["chat_id"] == "12345"
        assert body["text"] == "<b>bold</b>"


# ---------------------------------------------------------------------------
# deliver_articles orchestrator tests
# ---------------------------------------------------------------------------


class TestDeliverArticles:
    """Tests for deliver_articles orchestrator."""

    def _make_config(self) -> AppConfig:
        """Create a minimal AppConfig for tests."""
        return AppConfig()

    @patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_IDS": ""}, clear=False)
    def test_empty_token_skips_delivery(self, caplog):
        """Empty TELEGRAM_BOT_TOKEN logs warning and returns 0."""
        config = self._make_config()
        articles = [_make_article()]
        with caplog.at_level(logging.WARNING):
            result = deliver_articles(articles, config)
        assert result == 0
        assert "TELEGRAM_BOT_TOKEN not set" in caplog.text

    @patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "TOK", "TELEGRAM_CHAT_IDS": ""}, clear=False)
    def test_empty_chat_ids_skips_delivery(self, caplog):
        """Empty TELEGRAM_CHAT_IDS logs warning and returns 0."""
        config = self._make_config()
        articles = [_make_article()]
        with caplog.at_level(logging.WARNING):
            result = deliver_articles(articles, config)
        assert result == 0
        assert "No Telegram chat IDs configured" in caplog.text

    @patch.dict(
        "os.environ", {"TELEGRAM_BOT_TOKEN": "TOK", "TELEGRAM_CHAT_IDS": "111,222"}, clear=False
    )
    @patch("pipeline.deliverers.telegram_sender.send_telegram_message")
    @patch("pipeline.deliverers.telegram_sender.time.sleep")
    def test_delivers_to_all_chat_ids(self, mock_sleep, mock_send):
        """deliver_articles sends messages to each chat_id."""
        mock_send.return_value = (True, None)
        config = self._make_config()
        articles = [_make_article(priority="HIGH", dedup_status="NEW")]
        result = deliver_articles(articles, config)
        # Should have sent to 2 chat ids
        chat_ids_called = [call.args[1] for call in mock_send.call_args_list]
        assert "111" in chat_ids_called
        assert "222" in chat_ids_called
        assert result > 0

    @patch.dict(
        "os.environ", {"TELEGRAM_BOT_TOKEN": "TOK", "TELEGRAM_CHAT_IDS": "111"}, clear=False
    )
    @patch("pipeline.deliverers.telegram_sender.send_telegram_message")
    @patch("pipeline.deliverers.telegram_sender.time.sleep")
    def test_returns_successful_send_count(self, mock_sleep, mock_send):
        """deliver_articles returns the count of successful sends."""
        mock_send.return_value = (True, None)
        config = self._make_config()
        articles = [_make_article(priority="HIGH", dedup_status="NEW")]
        result = deliver_articles(articles, config)
        assert result == mock_send.call_count

    @patch.dict(
        "os.environ", {"TELEGRAM_BOT_TOKEN": "TOK", "TELEGRAM_CHAT_IDS": "111"}, clear=False
    )
    @patch("pipeline.deliverers.telegram_sender.send_telegram_message")
    @patch("pipeline.deliverers.telegram_sender.time.sleep")
    def test_failed_send_counted_correctly(self, mock_sleep, mock_send):
        """Failed sends are not counted in the return value."""
        mock_send.return_value = (False, "HTTP 400")
        config = self._make_config()
        articles = [_make_article(priority="HIGH", dedup_status="NEW")]
        result = deliver_articles(articles, config)
        assert result == 0

    @patch.dict(
        "os.environ", {"TELEGRAM_BOT_TOKEN": "TOK", "TELEGRAM_CHAT_IDS": "111"}, clear=False
    )
    @patch("pipeline.deliverers.telegram_sender.send_telegram_message")
    @patch("pipeline.deliverers.telegram_sender.time.sleep")
    def test_calls_select_articles(self, mock_sleep, mock_send):
        """deliver_articles calls select_articles for priority allocation."""
        mock_send.return_value = (True, None)
        config = self._make_config()
        articles = [_make_article(priority="HIGH", dedup_status="NEW")]
        with patch("pipeline.deliverers.telegram_sender.select_articles") as mock_select:
            mock_select.return_value = (articles, [], [])
            deliver_articles(articles, config)
            mock_select.assert_called_once()

    @patch.dict(
        "os.environ", {"TELEGRAM_BOT_TOKEN": "TOK", "TELEGRAM_CHAT_IDS": "111"}, clear=False
    )
    def test_no_articles_returns_zero(self, caplog):
        """Empty article list results in 0 sends."""
        config = self._make_config()
        with caplog.at_level(logging.INFO):
            result = deliver_articles([], config)
        assert result == 0

    @patch.dict(
        "os.environ", {"TELEGRAM_BOT_TOKEN": "TOK", "TELEGRAM_CHAT_IDS": "111"}, clear=False
    )
    @patch("pipeline.deliverers.telegram_sender.send_telegram_message")
    @patch("pipeline.deliverers.telegram_sender.time.sleep")
    def test_logs_delivery_summary(self, mock_sleep, mock_send, caplog):
        """deliver_articles logs a summary with articles, messages, users, and failures."""
        mock_send.return_value = (True, None)
        config = self._make_config()
        articles = [_make_article(priority="HIGH", dedup_status="NEW")]
        with caplog.at_level(logging.INFO):
            deliver_articles(articles, config)
        assert "Delivered" in caplog.text

    @patch.dict("os.environ", {}, clear=False)
    def test_config_token_used_when_env_not_set(self, caplog):
        """Falls back to config.telegram.bot_token when env var not set."""
        config = AppConfig()
        config.telegram.bot_token = ""
        # Remove env var entirely if present
        import os

        env_backup = os.environ.pop("TELEGRAM_BOT_TOKEN", None)
        try:
            with caplog.at_level(logging.WARNING):
                result = deliver_articles([_make_article()], config)
            assert result == 0
            assert "TELEGRAM_BOT_TOKEN not set" in caplog.text
        finally:
            if env_backup is not None:
                os.environ["TELEGRAM_BOT_TOKEN"] = env_backup
