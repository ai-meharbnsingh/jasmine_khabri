"""Gmail SMTP email delivery — HTML formatting and send.

Formats articles into styled HTML email digests with priority-colored
article cards. Sends via Gmail SMTP with App Password authentication
and STARTTLS. Mirrors telegram_sender.py orchestration pattern.
"""

import logging
import os
import smtplib
import ssl
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from pipeline.deliverers.selector import select_articles
from pipeline.deliverers.telegram_sender import (
    _IST,
    _escape_html,
    get_delivery_period,
)
from pipeline.schemas.article_schema import Article
from pipeline.schemas.config_schema import AppConfig

logger = logging.getLogger(__name__)

# Priority border colors for email cards
_PRIORITY_COLORS = {
    "HIGH": "#e53e3e",
    "MEDIUM": "#dd6b20",
    "LOW": "#38a169",
}


def format_article_card(article: Article, priority: str) -> str:
    """Render a single article as a styled HTML table row card.

    Card has a colored left border matching priority, #fafafa background,
    title as clickable link, source/location, ai_summary, and conditional
    entity metadata (budget/authority).

    Args:
        article: The article to render.
        priority: Priority string (HIGH/MEDIUM/LOW) for border color.

    Returns:
        HTML string for the article card.
    """
    color = _PRIORITY_COLORS.get(priority, "#718096")

    # Build entity line (conditional)
    entity_parts: list[str] = []
    if article.budget_amount:
        entity_parts.append(f"Budget: {_escape_html(article.budget_amount)}")
    if article.authority:
        entity_parts.append(f"Authority: {_escape_html(article.authority)}")
    entity_html = ""
    if entity_parts:
        entity_html = (
            f'<p style="margin:4px 0 0 0;font-size:12px;color:#a0aec0;">'
            f"{' | '.join(entity_parts)}</p>"
        )

    # Build summary line (conditional)
    summary_html = ""
    if article.summary:
        summary_html = (
            f'<p style="margin:4px 0 0 0;font-size:14px;color:#4a5568;">'
            f"{_escape_html(article.summary)}</p>"
        )

    # Source/location line
    source_line = _escape_html(article.source)
    if article.location:
        source_line += f" | {_escape_html(article.location)}"

    return (
        f'<table width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="margin-bottom:12px;">'
        f"<tr><td>"
        f'<table width="100%" cellpadding="12" cellspacing="0" border="0" '
        f'style="border-left:4px solid {color};background:#fafafa;">'
        f"<tr><td>"
        f'<a href="{_escape_html(article.url)}" '
        f'style="font-size:16px;font-weight:bold;color:#1a202c;text-decoration:none;">'
        f"{_escape_html(article.title)}</a>"
        f'<p style="margin:4px 0 0 0;font-size:13px;color:#718096;">{source_line}</p>'
        f"{summary_html}"
        f"{entity_html}"
        f"</td></tr></table>"
        f"</td></tr></table>"
    )


def format_email_html(
    high: list[Article],
    medium: list[Article],
    low: list[Article],
    config: AppConfig,
) -> str:
    """Build complete HTML email document with header, article cards, and footer.

    Uses table-based layout with inline CSS for maximum email client
    compatibility. Outer table max-width 600px, centered.

    Args:
        high: HIGH priority articles.
        medium: MEDIUM priority articles.
        low: LOW priority articles.
        config: Application config.

    Returns:
        Complete HTML document string.
    """
    from datetime import datetime

    period = get_delivery_period()
    now_ist = datetime.now(tz=_IST)
    date_str = now_ist.strftime("%d %b %Y")
    time_str = now_ist.strftime("%I:%M %p IST")

    total = len(high) + len(medium) + len(low)

    # Count breakdown
    count_parts: list[str] = []
    if high:
        count_parts.append(f"{len(high)} High")
    if medium:
        count_parts.append(f"{len(medium)} Medium")
    if low:
        count_parts.append(f"{len(low)} Low")
    count_breakdown = ", ".join(count_parts)

    # Next delivery time
    next_time = "4:00 PM" if period == "Morning" else "7:00 AM"

    # Build section HTML
    sections_html = ""
    section_defs = [
        ("\U0001f534", "HIGH PRIORITY", high, "HIGH"),
        ("\U0001f7e1", "MEDIUM PRIORITY", medium, "MEDIUM"),
        ("\U0001f7e2", "LOW PRIORITY", low, "LOW"),
    ]

    for emoji, label, articles, prio in section_defs:
        if not articles:
            continue
        sections_html += (
            f'<tr><td style="padding:16px 0 8px 0;font-size:16px;font-weight:bold;color:#2d3748;">'
            f"{emoji} {label} ({len(articles)})"
            f"</td></tr>"
        )
        for article in articles:
            sections_html += f"<tr><td>{format_article_card(article, prio)}</td></tr>"

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
        f'<table width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="max-width:600px;background:#ffffff;">'
        # Header
        '<tr><td style="padding:24px 20px;background:#1a202c;">'
        f'<h1 style="margin:0;font-size:22px;color:#ffffff;font-weight:bold;">'
        f"Khabri {period} Brief</h1>"
        f'<p style="margin:4px 0 0 0;font-size:14px;color:#a0aec0;">'
        f"{date_str} | {time_str}</p>"
        f'<p style="margin:4px 0 0 0;font-size:14px;color:#a0aec0;">'
        f"{total} stories &mdash; {count_breakdown}</p>"
        "</td></tr>"
        # Content
        '<tr><td style="padding:20px;">'
        '<table width="100%" cellpadding="0" cellspacing="0" border="0">'
        f"{sections_html}"
        "</table>"
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


def build_subject(high_count: int, total_count: int) -> str:
    """Build email subject line.

    Format: "Khabri {Morning/Evening} Brief -- {total} stories ({high} High)"

    Args:
        high_count: Number of HIGH priority articles.
        total_count: Total number of articles.

    Returns:
        Subject line string.
    """
    period = get_delivery_period()
    return f"Khabri {period} Brief -- {total_count} stories ({high_count} High)"


def build_plain_text(
    high: list[Article],
    medium: list[Article],
    low: list[Article],
) -> str:
    """Build plain-text email fallback.

    Simple readable format: section headers + title + url per article.

    Args:
        high: HIGH priority articles.
        medium: MEDIUM priority articles.
        low: LOW priority articles.

    Returns:
        Plain text string.
    """
    lines: list[str] = []

    section_defs = [
        ("HIGH PRIORITY", high),
        ("MEDIUM PRIORITY", medium),
        ("LOW PRIORITY", low),
    ]

    for label, articles in section_defs:
        if not articles:
            continue
        lines.append(f"\n=== {label} ===\n")
        for article in articles:
            lines.append(f"- {article.title}")
            lines.append(f"  {article.url}")
            if article.summary:
                lines.append(f"  {article.summary}")
            lines.append("")

    return "\n".join(lines)


def send_email(
    gmail_user: str,
    gmail_password: str,
    recipients: list[str],
    subject: str,
    html_body: str,
    text_body: str,
) -> tuple[bool, str | None]:
    """Send an HTML email via Gmail SMTP with STARTTLS.

    Constructs MIMEMultipart("alternative") with plain-text and HTML parts.
    Connects to smtp.gmail.com:587 with 15-second timeout.

    Args:
        gmail_user: Gmail address for authentication.
        gmail_password: Gmail App Password.
        recipients: List of recipient email addresses.
        subject: Email subject line.
        html_body: HTML email body.
        text_body: Plain-text fallback body.

    Returns:
        (True, None) on success, (False, error_message) on failure.
    """
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = gmail_user
    msg["To"] = ", ".join(recipients)

    # Attach text first, then HTML (email clients prefer last)
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=15) as server:
            server.starttls(context=ssl.create_default_context())
            server.login(gmail_user, gmail_password)
            server.sendmail(gmail_user, recipients, msg.as_string())
        return True, None
    except smtplib.SMTPException as exc:
        return False, str(exc)


def deliver_email(articles: list[Article], config: AppConfig) -> int:
    """Deliver HTML email digest to configured Gmail recipients.

    Orchestrates: check credentials -> select_articles -> format HTML ->
    send_email for each recipient. Mirrors telegram_sender.deliver_articles.

    Args:
        articles: All classified articles from the pipeline.
        config: Application config with email settings.

    Returns:
        Number of successful email sends.
    """
    # Check Gmail credentials
    gmail_user = os.environ.get("GMAIL_USER", "")
    if not gmail_user:
        logger.warning("GMAIL_USER not set -- skipping email delivery")
        return 0

    gmail_password = os.environ.get("GMAIL_APP_PASSWORD", "")
    if not gmail_password:
        logger.warning("GMAIL_APP_PASSWORD not set -- skipping email delivery")
        return 0

    # Check if email is enabled
    if not config.email.enabled:
        logger.warning("Email delivery disabled in config -- skipping")
        return 0

    # Resolve recipients: env var takes precedence over config
    recipients_env = os.environ.get("GMAIL_RECIPIENTS", "")
    if recipients_env:
        recipients = [r.strip() for r in recipients_env.split(",") if r.strip()]
    else:
        recipients = list(config.email.recipients)

    if not recipients:
        logger.warning("No email recipients configured -- skipping email delivery")
        return 0

    # Select articles by priority
    high, medium, low = select_articles(articles, config.delivery.max_stories)

    total_selected = len(high) + len(medium) + len(low)
    if total_selected == 0:
        logger.info("No articles to deliver via email")
        return 0

    # Format email content
    html_body = format_email_html(high, medium, low, config)
    text_body = build_plain_text(high, medium, low)
    subject = build_subject(len(high), total_selected)

    # Send to each recipient with single retry
    success_count = 0

    for recipient in recipients:
        ok, err = send_email(gmail_user, gmail_password, [recipient], subject, html_body, text_body)
        if ok:
            success_count += 1
        else:
            logger.warning("Email to %s failed: %s -- retrying once", recipient, err)
            time.sleep(2)
            ok, err = send_email(
                gmail_user, gmail_password, [recipient], subject, html_body, text_body
            )
            if ok:
                success_count += 1
            else:
                logger.warning("Email to %s failed after retry: %s", recipient, err)

    logger.info(
        "Email delivery: %d/%d recipients successful (%d articles)",
        success_count,
        len(recipients),
        total_selected,
    )

    return success_count
