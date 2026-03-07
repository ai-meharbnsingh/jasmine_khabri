"""Shared edge case detection and message generation for delivery channels.

Detects no-news, slow-news, and HIGH story overflow conditions.
Provides formatted messages for both Telegram (HTML) and email (HTML) channels.

Note: _IST, _escape_html, get_delivery_period are defined locally to avoid
circular imports with telegram_sender.py (which imports from this module).
"""

from datetime import datetime, timedelta, timezone

from pydantic import BaseModel

from pipeline.schemas.article_schema import Article

# IST timezone offset (UTC+5:30) — duplicated from telegram_sender to avoid circular import
_IST = timezone(timedelta(hours=5, minutes=30))


def _escape_html(text: str) -> str:
    """Escape &, <, > for Telegram HTML mode."""
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    return text


def get_delivery_period() -> str:
    """Return 'Morning' if current IST hour < 12, else 'Evening'."""
    now_ist = datetime.now(tz=_IST)
    return "Morning" if now_ist.hour < 12 else "Evening"


# Default caps (mirrored from selector.py)
_HIGH_CAP = 8


class EdgeCaseResult(BaseModel):
    """Result of edge case detection on article list."""

    is_no_news: bool = False
    is_slow_news: bool = False
    has_overflow: bool = False
    overflow_count: int = 0
    total_available: int = 0


def check_edge_cases(
    articles: list[Article],
    high_cap: int = _HIGH_CAP,
    max_stories: int = 15,
) -> EdgeCaseResult:
    """Detect edge cases in the article list before delivery.

    Counts only NEW articles with valid priority (HIGH/MEDIUM/LOW).

    Args:
        articles: All candidate articles.
        high_cap: Maximum HIGH articles before overflow (default 8).
        max_stories: Maximum stories per delivery (default 15).

    Returns:
        EdgeCaseResult with detection flags and counts.
    """
    valid = [
        a for a in articles if a.dedup_status == "NEW" and a.priority in ("HIGH", "MEDIUM", "LOW")
    ]
    total = len(valid)
    high_count = sum(1 for a in valid if a.priority == "HIGH")

    return EdgeCaseResult(
        is_no_news=total == 0,
        is_slow_news=0 < total < max_stories,
        has_overflow=high_count > high_cap,
        overflow_count=max(0, high_count - high_cap),
        total_available=total,
    )


def format_no_news_telegram() -> str:
    """Format a Telegram HTML message for no-news days.

    Includes period header, date/time in IST, explanation text,
    next delivery time, and footer.

    Returns:
        Telegram HTML-formatted no-news message.
    """
    period = get_delivery_period()
    now_ist = datetime.now(tz=_IST)
    date_str = now_ist.strftime("%d %b %Y")
    time_str = now_ist.strftime("%I:%M %p")

    next_time = "4:00 PM" if period == "Morning" else "7:00 AM"

    line = "\u2500" * 24

    return (
        f"\U0001f4f0 <b>Khabri {period} Brief</b>\n"
        f"{date_str} | {time_str} IST\n"
        f"{line}\n\n"
        f"No relevant infrastructure or real estate news found this cycle.\n"
        f"We'll check again at {next_time} IST.\n\n"
        f"{line}\n"
        f"Powered by Khabri"
    )


def format_no_news_email() -> str:
    """Format an HTML email body for no-news days.

    Minimal styled HTML with Khabri branding, explanation text,
    and next delivery time.

    Returns:
        Complete HTML document string for no-news email.
    """
    period = get_delivery_period()
    now_ist = datetime.now(tz=_IST)
    date_str = now_ist.strftime("%d %b %Y")
    time_str = now_ist.strftime("%I:%M %p IST")

    next_time = "4:00 PM" if period == "Morning" else "7:00 AM"

    return (
        "<!DOCTYPE html>"
        '<html lang="en">'
        "<head>"
        '<meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
        f"<title>Khabri {period} Brief</title>"
        "</head>"
        '<body style="margin:0;padding:0;background:#f7fafc;">'
        '<table width="100%" cellpadding="0" cellspacing="0" border="0">'
        '<tr><td align="center" style="padding:20px;">'
        '<table width="100%" cellpadding="0" cellspacing="0" border="0" '
        'style="max-width:600px;background:#ffffff;">'
        # Header
        '<tr><td style="padding:24px 20px;background:#1a202c;">'
        f'<h1 style="margin:0;font-size:22px;color:#ffffff;font-weight:bold;">'
        f"Khabri {period} Brief</h1>"
        f'<p style="margin:4px 0 0 0;font-size:14px;color:#a0aec0;">'
        f"{date_str} | {time_str}</p>"
        "</td></tr>"
        # Content
        '<tr><td style="padding:40px 20px;text-align:center;">'
        '<p style="margin:0;font-size:16px;color:#4a5568;">'
        "No relevant infrastructure or real estate news found this cycle.</p>"
        f'<p style="margin:12px 0 0 0;font-size:14px;color:#a0aec0;">'
        f"We'll check again at {next_time} IST.</p>"
        "</td></tr>"
        # Footer
        '<tr><td style="padding:20px;border-top:1px solid #e2e8f0;text-align:center;">'
        '<p style="margin:0;font-size:13px;color:#a0aec0;">Powered by Khabri</p>'
        f'<p style="margin:4px 0 0 0;font-size:12px;color:#cbd5e0;">'
        f"Next delivery: {next_time} IST</p>"
        "</td></tr>"
        "</table>"
        "</td></tr></table>"
        "</body></html>"
    )


def format_overflow_notice_telegram(overflow_count: int) -> str:
    """Format a Telegram overflow notice for HIGH story surplus.

    Args:
        overflow_count: Number of HIGH articles beyond the cap.

    Returns:
        HTML-escaped Telegram notice string starting with newline.
    """
    return (
        f"\n\u26a0\ufe0f {_escape_html(str(overflow_count))} more HIGH-priority "
        f"stories available -- reply 'more' to see them"
    )


def format_overflow_notice_email(overflow_count: int) -> str:
    """Format an email HTML overflow notice for HIGH story surplus.

    Returns an HTML <tr> row with a warning-style card noting the
    overflow count. Directs users to Telegram for additional stories.

    Args:
        overflow_count: Number of HIGH articles beyond the cap.

    Returns:
        HTML table row string.
    """
    return (
        "<tr><td>"
        '<table width="100%" cellpadding="12" cellspacing="0" border="0" '
        'style="margin-top:12px;background:#fffbeb;border-left:4px solid #d69e2e;">'
        "<tr><td>"
        f'<p style="margin:0;font-size:14px;color:#744210;">'
        f"\u26a0\ufe0f {overflow_count} more HIGH-priority stories available. "
        f"More stories available via Telegram.</p>"
        "</td></tr></table>"
        "</td></tr>"
    )


def format_slow_news_log(total: int, max_stories: int) -> str:
    """Format a log message for slow news days.

    Args:
        total: Number of available articles.
        max_stories: Maximum stories cap.

    Returns:
        Log message string.
    """
    return f"Slow news day: {total} articles available (below {max_stories} cap)"
