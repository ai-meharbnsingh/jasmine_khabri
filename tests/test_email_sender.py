"""Tests for email delivery — HTML formatting, SMTP send, and orchestrator."""

import logging
from unittest.mock import MagicMock, patch

from pipeline.deliverers.email_sender import (
    build_plain_text,
    build_subject,
    deliver_email,
    format_article_card,
    format_email_html,
    send_email,
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


class TestFormatArticleCard:
    """Test format_article_card HTML rendering."""

    def test_high_priority_has_red_border(self):
        """HIGH priority article card has #e53e3e left border."""
        article = _make_article(priority="HIGH")
        html = format_article_card(article, "HIGH")
        assert "#e53e3e" in html

    def test_medium_priority_has_orange_border(self):
        """MEDIUM priority article card has #dd6b20 left border."""
        article = _make_article(priority="MEDIUM")
        html = format_article_card(article, "MEDIUM")
        assert "#dd6b20" in html

    def test_low_priority_has_green_border(self):
        """LOW priority article card has #38a169 left border."""
        article = _make_article(priority="LOW")
        html = format_article_card(article, "LOW")
        assert "#38a169" in html

    def test_title_as_clickable_link(self):
        """Article card title is a clickable <a> link."""
        article = _make_article(title="Metro Project", url="https://example.com/metro")
        html = format_article_card(article, "HIGH")
        assert '<a href="https://example.com/metro"' in html
        assert "Metro Project" in html

    def test_source_and_location_shown(self):
        """Article card shows source and location."""
        article = _make_article(source="ET Realty", location="Mumbai")
        html = format_article_card(article, "HIGH")
        assert "ET Realty" in html
        assert "Mumbai" in html

    def test_ai_summary_shown(self):
        """Article card shows ai_summary when present."""
        article = _make_article(summary="Delhi metro extends to airport.")
        html = format_article_card(article, "HIGH")
        assert "Delhi metro extends to airport." in html

    def test_entities_shown_when_present(self):
        """Budget and authority shown when present."""
        article = _make_article(budget_amount="Rs 5000 Cr", authority="DMRC")
        html = format_article_card(article, "HIGH")
        assert "Rs 5000 Cr" in html
        assert "DMRC" in html

    def test_entities_hidden_when_empty(self):
        """No entity line when budget and authority are empty."""
        article = _make_article(budget_amount="", authority="")
        html = format_article_card(article, "HIGH")
        assert "Budget" not in html
        assert "Authority" not in html

    def test_budget_only_no_authority(self):
        """Only budget shown when authority is empty."""
        article = _make_article(budget_amount="Rs 100 Cr", authority="")
        html = format_article_card(article, "HIGH")
        assert "Rs 100 Cr" in html
        assert "Authority" not in html

    def test_authority_only_no_budget(self):
        """Only authority shown when budget is empty."""
        article = _make_article(budget_amount="", authority="NHAI")
        html = format_article_card(article, "HIGH")
        assert "NHAI" in html
        assert "Budget" not in html

    def test_html_escaping_in_title(self):
        """Special characters in title are escaped."""
        article = _make_article(title="<Bold> & Beautiful")
        html = format_article_card(article, "HIGH")
        assert "&lt;Bold&gt;" in html
        assert "&amp;" in html

    def test_card_has_background_color(self):
        """Article card has #fafafa background."""
        article = _make_article()
        html = format_article_card(article, "HIGH")
        assert "#fafafa" in html


class TestFormatEmailHtml:
    """Test full HTML email rendering."""

    def test_contains_header_with_title(self):
        """Email HTML has Khabri Brief title."""
        high = [_make_article(priority="HIGH")]
        html = format_email_html(high, [], [], AppConfig())
        assert "Khabri" in html
        assert "Brief" in html

    def test_contains_story_count(self):
        """Header shows story count breakdown."""
        high = [_make_article(priority="HIGH")]
        medium = [_make_article(priority="MEDIUM"), _make_article(priority="MEDIUM")]
        html = format_email_html(high, medium, [], AppConfig())
        assert "3 stories" in html
        assert "1 High" in html
        assert "2 Medium" in html

    def test_contains_ist_date(self):
        """Header includes IST date."""
        high = [_make_article(priority="HIGH")]
        html = format_email_html(high, [], [], AppConfig())
        # Should contain a date string (e.g., "07 Mar 2026")
        assert "IST" in html or "202" in html  # Year present in some form

    def test_section_headers_for_nonempty_priorities(self):
        """Non-empty priority groups have section headers."""
        high = [_make_article(priority="HIGH")]
        medium = [_make_article(priority="MEDIUM")]
        low = [_make_article(priority="LOW")]
        html = format_email_html(high, medium, low, AppConfig())
        assert "HIGH PRIORITY" in html
        assert "MEDIUM PRIORITY" in html
        assert "LOW PRIORITY" in html

    def test_empty_priority_section_omitted(self):
        """Empty priority groups don't have section headers."""
        high = [_make_article(priority="HIGH")]
        html = format_email_html(high, [], [], AppConfig())
        assert "HIGH PRIORITY" in html
        assert "MEDIUM PRIORITY" not in html
        assert "LOW PRIORITY" not in html

    def test_footer_contains_powered_by(self):
        """Footer has 'Powered by Khabri'."""
        high = [_make_article(priority="HIGH")]
        html = format_email_html(high, [], [], AppConfig())
        assert "Powered by Khabri" in html

    def test_max_width_600(self):
        """Outer table has max-width 600px for email clients."""
        high = [_make_article(priority="HIGH")]
        html = format_email_html(high, [], [], AppConfig())
        assert "600px" in html

    def test_is_valid_html(self):
        """Email HTML has <html>, <head>, <body> tags."""
        high = [_make_article(priority="HIGH")]
        html = format_email_html(high, [], [], AppConfig())
        assert "<html" in html
        assert "<head" in html
        assert "<body" in html


class TestBuildSubject:
    """Test email subject line building."""

    def test_morning_format(self):
        """Morning subject: 'Khabri Morning Brief -- N stories (X High)'."""
        with patch("pipeline.deliverers.email_sender.get_delivery_period", return_value="Morning"):
            subject = build_subject(high_count=3, total_count=10)
        assert "Khabri Morning Brief" in subject
        assert "10 stories" in subject
        assert "3 High" in subject

    def test_evening_format(self):
        """Evening subject: 'Khabri Evening Brief -- N stories (X High)'."""
        with patch("pipeline.deliverers.email_sender.get_delivery_period", return_value="Evening"):
            subject = build_subject(high_count=1, total_count=5)
        assert "Khabri Evening Brief" in subject
        assert "5 stories" in subject
        assert "1 High" in subject


class TestBuildPlainText:
    """Test plain-text fallback building."""

    def test_contains_article_titles(self):
        """Plain text includes article titles."""
        high = [_make_article(title="High Story", priority="HIGH")]
        medium = [_make_article(title="Med Story", priority="MEDIUM")]
        text = build_plain_text(high, medium, [])
        assert "High Story" in text
        assert "Med Story" in text

    def test_contains_urls(self):
        """Plain text includes article URLs."""
        high = [_make_article(url="https://example.com/1", priority="HIGH")]
        text = build_plain_text(high, [], [])
        assert "https://example.com/1" in text

    def test_section_headers(self):
        """Plain text has section headers for non-empty priorities."""
        high = [_make_article(priority="HIGH")]
        low = [_make_article(priority="LOW")]
        text = build_plain_text(high, [], low)
        assert "HIGH" in text
        assert "LOW" in text

    def test_empty_section_omitted(self):
        """Empty priority section header is omitted."""
        high = [_make_article(priority="HIGH")]
        text = build_plain_text(high, [], [])
        assert "HIGH" in text
        assert "MEDIUM" not in text
        assert "LOW" not in text


class TestSendEmail:
    """Test SMTP email sending (mocked smtplib)."""

    @patch("pipeline.deliverers.email_sender.smtplib.SMTP")
    def test_success_returns_true_none(self, mock_smtp_cls):
        """Successful send returns (True, None)."""
        mock_smtp = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_smtp)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
        ok, err = send_email(
            "user@gmail.com",
            "password",
            ["to@example.com"],
            "Subject",
            "<h1>HTML</h1>",
            "Plain text",
        )
        assert ok is True
        assert err is None

    @patch("pipeline.deliverers.email_sender.smtplib.SMTP")
    def test_calls_starttls(self, mock_smtp_cls):
        """SMTP connection uses STARTTLS."""
        mock_smtp = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_smtp)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
        send_email(
            "user@gmail.com",
            "password",
            ["to@example.com"],
            "Subject",
            "<h1>HTML</h1>",
            "text",
        )
        mock_smtp.starttls.assert_called_once()

    @patch("pipeline.deliverers.email_sender.smtplib.SMTP")
    def test_calls_login(self, mock_smtp_cls):
        """SMTP connection calls login with credentials."""
        mock_smtp = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_smtp)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
        send_email(
            "user@gmail.com",
            "mypassword",
            ["to@example.com"],
            "Subject",
            "<h1>HTML</h1>",
            "text",
        )
        mock_smtp.login.assert_called_once_with("user@gmail.com", "mypassword")

    @patch("pipeline.deliverers.email_sender.smtplib.SMTP")
    def test_calls_sendmail(self, mock_smtp_cls):
        """SMTP sends email to recipients via sendmail."""
        mock_smtp = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_smtp)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
        send_email(
            "user@gmail.com",
            "password",
            ["to@example.com"],
            "Subject",
            "<h1>HTML</h1>",
            "text",
        )
        mock_smtp.sendmail.assert_called_once()
        args = mock_smtp.sendmail.call_args
        assert args[0][0] == "user@gmail.com"
        assert args[0][1] == ["to@example.com"]

    @patch("pipeline.deliverers.email_sender.smtplib.SMTP")
    def test_constructs_mime_multipart(self, mock_smtp_cls):
        """Email uses MIMEMultipart('alternative') with text and HTML parts."""
        mock_smtp = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_smtp)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
        send_email(
            "user@gmail.com",
            "password",
            ["to@example.com"],
            "Test Subject",
            "<h1>HTML</h1>",
            "Plain text",
        )
        # Check sendmail was called with a MIME message
        msg_str = mock_smtp.sendmail.call_args[0][2]
        assert "multipart/alternative" in msg_str
        assert "text/plain" in msg_str
        assert "text/html" in msg_str
        assert "Test Subject" in msg_str

    @patch("pipeline.deliverers.email_sender.smtplib.SMTP")
    def test_smtp_exception_returns_false(self, mock_smtp_cls):
        """SMTPException returns (False, error_msg)."""
        import smtplib

        mock_smtp = MagicMock()
        mock_smtp.sendmail.side_effect = smtplib.SMTPException("Auth failed")
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_smtp)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
        ok, err = send_email(
            "user@gmail.com",
            "password",
            ["to@example.com"],
            "Subject",
            "<h1>HTML</h1>",
            "text",
        )
        assert ok is False
        assert "Auth failed" in err

    @patch("pipeline.deliverers.email_sender.smtplib.SMTP")
    def test_timeout_15_seconds(self, mock_smtp_cls):
        """SMTP connection uses 15s timeout."""
        mock_smtp = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_smtp)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
        send_email(
            "user@gmail.com",
            "password",
            ["to@example.com"],
            "Subject",
            "<h1>HTML</h1>",
            "text",
        )
        mock_smtp_cls.assert_called_once_with("smtp.gmail.com", 587, timeout=15)


class TestDeliverEmail:
    """Test deliver_email orchestrator."""

    @patch.dict("os.environ", {"GMAIL_USER": "", "GMAIL_APP_PASSWORD": ""}, clear=False)
    def test_skips_when_gmail_user_missing(self, caplog):
        """Missing GMAIL_USER env var logs warning and returns 0."""
        with caplog.at_level(logging.WARNING):
            result = deliver_email([_make_article()], AppConfig())
        assert result == 0
        assert "GMAIL_USER" in caplog.text

    @patch.dict("os.environ", {"GMAIL_USER": "a@b.com", "GMAIL_APP_PASSWORD": ""}, clear=False)
    def test_skips_when_gmail_password_missing(self, caplog):
        """Missing GMAIL_APP_PASSWORD env var logs warning and returns 0."""
        with caplog.at_level(logging.WARNING):
            result = deliver_email([_make_article()], AppConfig())
        assert result == 0
        assert "GMAIL_APP_PASSWORD" in caplog.text

    @patch.dict(
        "os.environ",
        {"GMAIL_USER": "a@b.com", "GMAIL_APP_PASSWORD": "pass"},
        clear=False,
    )
    def test_skips_when_email_disabled(self, caplog):
        """email.enabled=False logs warning and returns 0."""
        config = AppConfig()
        config.email.enabled = False
        with caplog.at_level(logging.WARNING):
            result = deliver_email([_make_article()], config)
        assert result == 0
        assert "disabled" in caplog.text.lower()

    @patch.dict(
        "os.environ",
        {"GMAIL_USER": "a@b.com", "GMAIL_APP_PASSWORD": "pass", "GMAIL_RECIPIENTS": ""},
        clear=False,
    )
    def test_skips_when_no_recipients(self, caplog):
        """Empty recipients (env and config) logs warning and returns 0."""
        config = AppConfig()
        config.email.recipients = []
        with caplog.at_level(logging.WARNING):
            result = deliver_email([_make_article()], config)
        assert result == 0
        assert "recipients" in caplog.text.lower()

    @patch.dict(
        "os.environ",
        {
            "GMAIL_USER": "a@b.com",
            "GMAIL_APP_PASSWORD": "pass",
            "GMAIL_RECIPIENTS": "x@y.com,z@w.com",
        },
        clear=False,
    )
    @patch("pipeline.deliverers.email_sender.send_email")
    def test_env_recipients_override_config(self, mock_send):
        """GMAIL_RECIPIENTS env var overrides config.email.recipients."""
        mock_send.return_value = (True, None)
        config = AppConfig()
        config.email.recipients = ["config@example.com"]
        articles = [_make_article(priority="HIGH", dedup_status="NEW")]
        deliver_email(articles, config)
        # send_email should be called with env recipients, not config ones
        recipients_called = [c.args[2] for c in mock_send.call_args_list]
        # Flatten to check individual recipients
        all_recipients = [r for sublist in recipients_called for r in sublist]
        assert "x@y.com" in all_recipients
        assert "z@w.com" in all_recipients
        assert "config@example.com" not in all_recipients

    @patch.dict(
        "os.environ",
        {"GMAIL_USER": "a@b.com", "GMAIL_APP_PASSWORD": "pass", "GMAIL_RECIPIENTS": "x@y.com"},
        clear=False,
    )
    @patch("pipeline.deliverers.email_sender.send_email")
    def test_calls_select_articles(self, mock_send):
        """deliver_email calls select_articles."""
        mock_send.return_value = (True, None)
        articles = [_make_article(priority="HIGH", dedup_status="NEW")]
        with patch("pipeline.deliverers.email_sender.select_articles") as mock_select:
            mock_select.return_value = (articles, [], [])
            deliver_email(articles, AppConfig())
            mock_select.assert_called_once()

    @patch.dict(
        "os.environ",
        {"GMAIL_USER": "a@b.com", "GMAIL_APP_PASSWORD": "pass", "GMAIL_RECIPIENTS": "x@y.com"},
        clear=False,
    )
    @patch("pipeline.deliverers.email_sender.send_email")
    def test_returns_send_count(self, mock_send):
        """deliver_email returns count of successful sends."""
        mock_send.return_value = (True, None)
        articles = [_make_article(priority="HIGH", dedup_status="NEW")]
        result = deliver_email(articles, AppConfig())
        assert result == mock_send.call_count
        assert result > 0

    @patch.dict(
        "os.environ",
        {
            "GMAIL_USER": "a@b.com",
            "GMAIL_APP_PASSWORD": "pass",
            "GMAIL_RECIPIENTS": "x@y.com",
        },
        clear=False,
    )
    @patch("pipeline.deliverers.email_sender.send_email")
    @patch("pipeline.deliverers.email_sender.time.sleep")
    def test_retries_once_on_failure(self, mock_sleep, mock_send):
        """deliver_email retries once on SMTP failure."""
        # First call fails, second succeeds
        mock_send.side_effect = [(False, "SMTP error"), (True, None)]
        articles = [_make_article(priority="HIGH", dedup_status="NEW")]
        result = deliver_email(articles, AppConfig())
        assert mock_send.call_count == 2
        assert result == 1  # One successful send after retry

    @patch.dict(
        "os.environ",
        {
            "GMAIL_USER": "a@b.com",
            "GMAIL_APP_PASSWORD": "pass",
            "GMAIL_RECIPIENTS": "x@y.com",
        },
        clear=False,
    )
    @patch("pipeline.deliverers.email_sender.send_email")
    @patch("pipeline.deliverers.email_sender.time.sleep")
    def test_logs_warning_on_final_failure(self, mock_sleep, mock_send, caplog):
        """deliver_email logs warning when retry also fails."""
        mock_send.return_value = (False, "SMTP error")
        articles = [_make_article(priority="HIGH", dedup_status="NEW")]
        with caplog.at_level(logging.WARNING):
            result = deliver_email(articles, AppConfig())
        assert result == 0
        assert "fail" in caplog.text.lower() or "SMTP" in caplog.text

    @patch.dict(
        "os.environ",
        {"GMAIL_USER": "a@b.com", "GMAIL_APP_PASSWORD": "pass", "GMAIL_RECIPIENTS": "x@y.com"},
        clear=False,
    )
    def test_no_articles_returns_zero(self):
        """Empty article list returns 0."""
        result = deliver_email([], AppConfig())
        assert result == 0
