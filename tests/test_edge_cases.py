"""Tests for edge case detection — no-news, slow-news, and overflow handling."""

from unittest.mock import patch

from pipeline.deliverers.edge_cases import (
    check_edge_cases,
    format_no_news_email,
    format_no_news_telegram,
    format_overflow_notice_email,
    format_overflow_notice_telegram,
    format_slow_news_log,
)
from pipeline.schemas.article_schema import Article


def _make_article(
    title: str = "Test Article",
    url: str = "https://example.com/article",
    source: str = "Test Source",
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
        priority=priority,
        dedup_status=dedup_status,
    )


class TestCheckEdgeCases:
    """Test check_edge_cases detection logic."""

    def test_empty_articles_is_no_news(self):
        """Empty article list returns is_no_news=True."""
        result = check_edge_cases([])
        assert result.is_no_news is True
        assert result.is_slow_news is False
        assert result.has_overflow is False
        assert result.overflow_count == 0
        assert result.total_available == 0

    def test_five_articles_is_slow_news(self):
        """5 articles returns is_slow_news=True, is_no_news=False."""
        articles = [_make_article(priority="HIGH") for _ in range(5)]
        result = check_edge_cases(articles)
        assert result.is_slow_news is True
        assert result.is_no_news is False
        assert result.total_available == 5

    def test_fifteen_articles_not_slow_news(self):
        """15 articles returns is_slow_news=False, is_no_news=False."""
        articles = [_make_article(priority="HIGH") for _ in range(15)]
        result = check_edge_cases(articles)
        assert result.is_slow_news is False
        assert result.is_no_news is False
        assert result.total_available == 15

    def test_twelve_high_has_overflow(self):
        """12 HIGH articles returns has_overflow=True, overflow_count=4."""
        articles = [_make_article(priority="HIGH") for _ in range(12)]
        result = check_edge_cases(articles)
        assert result.has_overflow is True
        assert result.overflow_count == 4

    def test_six_high_no_overflow(self):
        """6 HIGH articles returns has_overflow=False, overflow_count=0."""
        articles = [_make_article(priority="HIGH") for _ in range(6)]
        result = check_edge_cases(articles)
        assert result.has_overflow is False
        assert result.overflow_count == 0

    def test_only_counts_new_articles(self):
        """Only dedup_status='NEW' articles are counted."""
        new = [_make_article(priority="HIGH", dedup_status="NEW") for _ in range(3)]
        dup = [_make_article(priority="HIGH", dedup_status="DUPLICATE") for _ in range(10)]
        result = check_edge_cases(new + dup)
        assert result.total_available == 3
        assert result.is_slow_news is True

    def test_only_counts_valid_priority(self):
        """Only articles with valid priority (HIGH/MEDIUM/LOW) are counted."""
        valid = [_make_article(priority="HIGH") for _ in range(3)]
        no_priority = [_make_article(priority="") for _ in range(10)]
        result = check_edge_cases(valid + no_priority)
        assert result.total_available == 3
        assert result.is_slow_news is True

    def test_mixed_priorities_overflow(self):
        """Overflow only counts HIGH articles, not MEDIUM/LOW."""
        high = [_make_article(priority="HIGH") for _ in range(10)]
        medium = [_make_article(priority="MEDIUM") for _ in range(5)]
        result = check_edge_cases(high + medium)
        assert result.has_overflow is True
        assert result.overflow_count == 2  # 10 - 8

    def test_exactly_eight_high_no_overflow(self):
        """Exactly 8 HIGH articles does not trigger overflow."""
        articles = [_make_article(priority="HIGH") for _ in range(8)]
        result = check_edge_cases(articles)
        assert result.has_overflow is False
        assert result.overflow_count == 0

    def test_exactly_max_stories_not_slow(self):
        """Exactly max_stories articles is not slow news."""
        articles = [_make_article(priority="MEDIUM") for _ in range(15)]
        result = check_edge_cases(articles, max_stories=15)
        assert result.is_slow_news is False


class TestFormatNoNewsTelegram:
    """Test Telegram no-news message formatting."""

    def test_contains_khabri_title(self):
        """No-news Telegram message has 'Khabri' title."""
        with patch("pipeline.deliverers.edge_cases.get_delivery_period", return_value="Morning"):
            msg = format_no_news_telegram()
        assert "Khabri" in msg
        assert "Morning" in msg

    def test_contains_no_news_text(self):
        """No-news message contains explanation text."""
        with patch("pipeline.deliverers.edge_cases.get_delivery_period", return_value="Morning"):
            msg = format_no_news_telegram()
        assert "No relevant" in msg or "no relevant" in msg.lower()

    def test_morning_shows_evening_next(self):
        """Morning no-news message shows 4:00 PM as next delivery."""
        with patch("pipeline.deliverers.edge_cases.get_delivery_period", return_value="Morning"):
            msg = format_no_news_telegram()
        assert "4:00 PM" in msg

    def test_evening_shows_morning_next(self):
        """Evening no-news message shows 7:00 AM as next delivery."""
        with patch("pipeline.deliverers.edge_cases.get_delivery_period", return_value="Evening"):
            msg = format_no_news_telegram()
        assert "7:00 AM" in msg

    def test_has_bold_html_tags(self):
        """No-news Telegram message uses HTML <b> formatting."""
        with patch("pipeline.deliverers.edge_cases.get_delivery_period", return_value="Morning"):
            msg = format_no_news_telegram()
        assert "<b>" in msg

    def test_contains_ist_reference(self):
        """No-news message references IST timezone."""
        with patch("pipeline.deliverers.edge_cases.get_delivery_period", return_value="Morning"):
            msg = format_no_news_telegram()
        assert "IST" in msg

    def test_contains_powered_by(self):
        """No-news message has 'Powered by Khabri' footer."""
        with patch("pipeline.deliverers.edge_cases.get_delivery_period", return_value="Morning"):
            msg = format_no_news_telegram()
        assert "Powered by Khabri" in msg


class TestFormatNoNewsEmail:
    """Test email no-news message formatting."""

    def test_contains_no_news_text(self):
        """No-news email has explanation text."""
        with patch("pipeline.deliverers.edge_cases.get_delivery_period", return_value="Morning"):
            html = format_no_news_email()
        assert "No relevant" in html or "no relevant" in html.lower()

    def test_is_html(self):
        """No-news email is valid HTML with html/body tags."""
        with patch("pipeline.deliverers.edge_cases.get_delivery_period", return_value="Morning"):
            html = format_no_news_email()
        assert "<html" in html
        assert "<body" in html

    def test_contains_khabri_branding(self):
        """No-news email has Khabri branding."""
        with patch("pipeline.deliverers.edge_cases.get_delivery_period", return_value="Morning"):
            html = format_no_news_email()
        assert "Khabri" in html

    def test_contains_next_delivery_time(self):
        """No-news email shows next delivery time."""
        with patch("pipeline.deliverers.edge_cases.get_delivery_period", return_value="Evening"):
            html = format_no_news_email()
        assert "7:00 AM" in html


class TestFormatOverflowNoticeTelegram:
    """Test Telegram overflow notice formatting."""

    def test_contains_overflow_count(self):
        """Overflow notice includes the count."""
        notice = format_overflow_notice_telegram(4)
        assert "4" in notice

    def test_contains_high_priority(self):
        """Overflow notice mentions HIGH-priority."""
        notice = format_overflow_notice_telegram(3)
        assert "HIGH" in notice or "high" in notice.lower()

    def test_starts_with_newline(self):
        """Overflow notice starts with newline for appending."""
        notice = format_overflow_notice_telegram(2)
        assert notice.startswith("\n")


class TestFormatOverflowNoticeEmail:
    """Test email overflow notice formatting."""

    def test_contains_overflow_count(self):
        """Email overflow notice includes the count."""
        html = format_overflow_notice_email(5)
        assert "5" in html

    def test_is_html_table_row(self):
        """Email overflow notice is an HTML <tr> element."""
        html = format_overflow_notice_email(3)
        assert "<tr>" in html or "<tr " in html

    def test_mentions_telegram(self):
        """Email overflow notice mentions Telegram for more stories."""
        html = format_overflow_notice_email(2)
        assert "Telegram" in html


class TestFormatSlowNewsLog:
    """Test slow news log message formatting."""

    def test_contains_counts(self):
        """Slow news log message includes available and cap counts."""
        msg = format_slow_news_log(7, 15)
        assert "7" in msg
        assert "15" in msg

    def test_contains_slow_news_text(self):
        """Slow news log message mentions slow news."""
        msg = format_slow_news_log(5, 15)
        assert "slow" in msg.lower() or "Slow" in msg
