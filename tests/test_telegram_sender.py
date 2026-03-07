"""Tests for Telegram HTML message formatter and chunking."""

from unittest.mock import patch

from pipeline.deliverers.telegram_sender import (
    _escape_html,
    chunk_message,
    format_article_html,
    format_delivery_message,
    get_delivery_period,
)
from pipeline.schemas.article_schema import Article


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
