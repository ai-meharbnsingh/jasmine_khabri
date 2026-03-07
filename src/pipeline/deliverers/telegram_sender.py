"""Telegram message delivery — HTML formatting, chunking, IST time helpers.

Formats articles into Telegram-compatible HTML messages with priority
section headers, continuous numbering, and 4096-character chunking.
"""

import logging
from datetime import datetime, timedelta, timezone

from pipeline.schemas.article_schema import Article

logger = logging.getLogger(__name__)

# IST timezone offset (UTC+5:30)
_IST = timezone(timedelta(hours=5, minutes=30))

# Telegram message length limit
_MAX_CHARS = 4096


def _escape_html(text: str) -> str:
    """Escape &, <, > for Telegram HTML mode.

    Order matters: & must be escaped first to avoid double-escaping
    the & in &lt; or &gt;.
    """
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    return text


def format_article_html(article: Article, number: int) -> str:
    """Format a single article as Telegram HTML.

    Layout:
        {number}. <b>{title}</b>
           <i>{source}</i> [* {location}]
           [{summary}]
           [Budget: {budget} [* Authority: {authority}]]
           <a href="{url}">Read</a>

    Conditional lines are omitted entirely when their content is empty.
    """
    lines: list[str] = []

    # Line 1: Numbered bold title
    lines.append(f"{number}. <b>{_escape_html(article.title)}</b>")

    # Line 2: Italic source, optional location
    source_line = f"   <i>{_escape_html(article.source)}</i>"
    if article.location:
        source_line += f" | {_escape_html(article.location)}"
    lines.append(source_line)

    # Line 3 (conditional): Summary
    if article.summary:
        lines.append(f"   {_escape_html(article.summary)}")

    # Line 4 (conditional): Entity metadata (budget + authority)
    entity_parts: list[str] = []
    if article.budget_amount:
        entity_parts.append(f"Budget: {_escape_html(article.budget_amount)}")
    if article.authority:
        entity_parts.append(f"Authority: {_escape_html(article.authority)}")
    if entity_parts:
        lines.append(f"   {' | '.join(entity_parts)}")

    # Line 5: Read link
    lines.append(f'   <a href="{_escape_html(article.url)}">Read</a>')

    return "\n".join(lines)


def get_delivery_period() -> str:
    """Return 'Morning' if current IST hour < 12, else 'Evening'."""
    now_ist = datetime.now(tz=_IST)
    return "Morning" if now_ist.hour < 12 else "Evening"


def format_delivery_message(
    high: list[Article],
    medium: list[Article],
    low: list[Article],
    period: str = "",
) -> list[str]:
    """Build full Telegram delivery message and return as list of chunk strings.

    Builds header with story count breakdown and IST date/time, priority
    section headers with circle emojis, continuous article numbering,
    and footer with next delivery time. Chunks at article boundaries
    if message exceeds 4096 chars.

    Args:
        high: HIGH priority articles.
        medium: MEDIUM priority articles.
        low: LOW priority articles.
        period: "Morning" or "Evening". Auto-detected if empty.

    Returns:
        List of message strings (chunks), each under 4096 chars.
    """
    if not period:
        period = get_delivery_period()

    total_count = len(high) + len(medium) + len(low)
    now_ist = datetime.now(tz=_IST)
    date_str = now_ist.strftime("%d %b %Y")
    time_str = now_ist.strftime("%I:%M %p IST")

    # Build count breakdown
    count_parts: list[str] = []
    if high:
        count_parts.append(f"{len(high)} High")
    if medium:
        count_parts.append(f"{len(medium)} Medium")
    if low:
        count_parts.append(f"{len(low)} Low")
    count_breakdown = " | ".join(count_parts)

    # Header
    header_lines = [
        f"\U0001f4f0 <b>Khabri {period} Brief</b>",
        f"{date_str} | {time_str}",
        f"{total_count} stories ({count_breakdown})",
        "\u2500" * 24,
    ]
    header = "\n".join(header_lines)

    # Next delivery time
    next_time = "4:00 PM" if period == "Morning" else "7:00 AM"

    # Footer
    footer_lines = [
        "\u2500" * 24,
        "Powered by Khabri",
        f"Next: {next_time} IST",
    ]
    footer = "\n".join(footer_lines)

    # Build article blocks with continuous numbering
    article_blocks: list[str] = []
    number = 1

    # Section definitions: (emoji, label, articles)
    sections = [
        ("\U0001f534", "HIGH PRIORITY", high),
        ("\U0001f7e1", "MEDIUM PRIORITY", medium),
        ("\U0001f7e2", "LOW PRIORITY", low),
    ]

    for emoji, label, articles in sections:
        if not articles:
            continue
        # Section header
        section_header = f"\n{emoji} <b>{label}</b> ({len(articles)})\n"
        article_blocks.append(section_header)
        for article in articles:
            block = format_article_html(article, number)
            article_blocks.append(block)
            number += 1

    return chunk_message(header, article_blocks, footer, max_chars=_MAX_CHARS)


def chunk_message(
    header: str,
    article_blocks: list[str],
    footer: str,
    max_chars: int = 4096,
) -> list[str]:
    """Split message at article boundaries to stay under max_chars.

    Header appears in the first chunk only.
    Footer appears in the last chunk only.
    Each chunk must be under max_chars.

    Args:
        header: Message header text.
        article_blocks: List of article HTML blocks (one per article/section).
        footer: Message footer text.
        max_chars: Maximum characters per chunk.

    Returns:
        List of message chunk strings.
    """
    if not article_blocks:
        return [f"{header}\n\n{footer}"]

    chunks: list[str] = []
    current_parts: list[str] = []
    is_first_chunk = True

    # Reserve space for header in first chunk
    prefix = header + "\n\n"
    current_len = len(prefix)

    for block in article_blocks:
        block_with_sep = "\n" + block if current_parts else block
        block_len = len(block_with_sep)

        # Check if adding this block would exceed limit
        # Account for footer space in case this is the last block
        would_exceed = current_len + block_len > max_chars

        if would_exceed and current_parts:
            # Flush current chunk
            chunk_text = (
                prefix + "\n".join(current_parts) if is_first_chunk else "\n".join(current_parts)
            )
            chunks.append(chunk_text)
            is_first_chunk = False
            current_parts = [block]
            current_len = len(block)
        else:
            current_parts.append(block)
            current_len += block_len

    # Final chunk with footer
    if current_parts:
        parts_text = "\n".join(current_parts)
        if is_first_chunk:
            chunk_text = f"{prefix}{parts_text}\n\n{footer}"
        else:
            chunk_text = f"{parts_text}\n\n{footer}"
        chunks.append(chunk_text)
    elif not chunks:
        # Edge case: no article blocks fit
        chunks.append(f"{header}\n\n{footer}")

    return chunks
