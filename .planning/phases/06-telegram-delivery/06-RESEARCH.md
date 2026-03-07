# Phase 6: Telegram Delivery - Research

**Researched:** 2026-03-07
**Domain:** Telegram Bot API message delivery, article selection/formatting, GitHub Actions integration
**Confidence:** HIGH

## Summary

Phase 6 delivers classified articles to two Telegram users via the Telegram Bot HTTP API. The project already uses httpx for all HTTP calls (RSS, GNews, AI providers), so direct httpx calls to `https://api.telegram.org/bot{TOKEN}/sendMessage` are the natural choice -- no additional library needed. The Telegram Bot API is a simple REST endpoint accepting JSON with `chat_id`, `text`, and `parse_mode` parameters.

The main technical challenges are: (1) formatting articles as clean Telegram HTML (limited tag support -- only `<b>`, `<i>`, `<a>`, `<u>`, `<s>`, `<code>`, `<pre>`, no `<br>` or custom styling), (2) splitting messages that exceed the 4096-character limit without breaking HTML tags or cutting mid-article, and (3) implementing the priority-based selection algorithm (up to 8 HIGH, min 4 MEDIUM, min 2 LOW, capped at 15 total) with graceful handling of low-article scenarios.

**Primary recommendation:** Use httpx directly to call the Telegram sendMessage API (consistent with project stack), format messages in HTML parse mode, split at article boundaries (never mid-article), and use `link_preview_options` to disable link previews.

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions
- Telegram HTML parse mode (not Markdown V2 or plain text)
- Full detail per article: bold title, italic source + location, AI summary, entity line (budget/authority when present), clickable "Read" link
- Entities shown conditionally -- only when AI extracted non-empty values; entity line omitted entirely if all empty
- Priority section indicators: colored circle emojis (red HIGH, yellow MEDIUM, green LOW) with bold headers and story count
- Continuous numbering across sections (1-8 HIGH, 9-12 MEDIUM, 13-15 LOW) -- no reset per section
- Header: "Khabri Morning/Evening Brief" with IST time, date, and story count breakdown
- Horizontal separator between header and articles
- Footer: "Powered by Khabri" with next delivery time
- Section separators between priority groups
- Only articles with `dedup_status="NEW"` are delivered -- UPDATEs and DUPLICATEs dropped entirely
- All user-facing times in Telegram messages display as IST (UTC+5:30)
- All backend/pipeline timestamps remain UTC

### Claude's Discretion
- Story selection edge cases (fewer than 15 articles, 0 of a priority level, flexible allocation)
- Message chunking strategy for 4096-char Telegram limit (split by section vs per-article)
- Delivery error handling (retry logic, partial failure handling)
- Telegram API library choice (httpx direct vs python-telegram-bot)
- Rate limit handling for Telegram API
- Morning vs Evening brief title detection logic

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DLVR-01 | System delivers curated news brief via Telegram to both users at 7 AM IST (formatted with priority sections, summaries, metadata, links) | Telegram sendMessage API with HTML parse_mode, article formatting template, IST time display via UTC+5:30 offset |
| DLVR-02 | System delivers curated news brief via Telegram to both users at 4 PM IST | Same delivery function, morning/evening detection from schedule config or current UTC hour |
| DLVR-04 | System selects max 15 stories per delivery with priority-based allocation (all HIGH up to 8, fill MEDIUM min 4, fill LOW min 2) | Selection algorithm with priority bucketing and flexible allocation for edge cases |

</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| httpx | >=0.28.1 | HTTP POST to Telegram sendMessage API | Already a project dependency, used for RSS + GNews; no new dep needed |
| respx | >=0.22.0 | Mock httpx calls in tests | Already a dev dependency, established pattern in test_gnews_fetcher.py |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| datetime (stdlib) | 3.12 | UTC to IST conversion for display timestamps | All user-facing time formatting |
| zoneinfo (stdlib) | 3.12 | IST timezone via ZoneInfo("Asia/Kolkata") | Converting UTC timestamps for Telegram display |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| httpx direct | python-telegram-bot | Adds heavy dependency (async framework, ~20 sub-deps) for just sendMessage; project already uses httpx everywhere |
| httpx direct | pyTelegramBotAPI (telebot) | Similar overhead for a single endpoint; inconsistent with project HTTP pattern |
| zoneinfo | timedelta(hours=5, minutes=30) | zoneinfo handles DST edge cases (India doesn't have DST, but zoneinfo is more correct and stdlib) |

**Recommendation:** Use httpx directly. The project calls exactly ONE Telegram endpoint (sendMessage). Adding a full Telegram bot library for one POST call is unnecessary complexity. httpx is already imported and tested throughout the codebase. For Phase 8+ (Railway bot with polling), python-telegram-bot would be appropriate -- but that is out of scope here.

**Installation:** No new dependencies needed.

## Architecture Patterns

### Recommended Project Structure
```
src/pipeline/
  deliverers/
    telegram_sender.py    # Core: format + send messages via Telegram API
    selector.py           # Article selection algorithm (priority allocation)
```

### Pattern 1: Article Selection Algorithm
**What:** Priority-based story allocation with a hard cap of 15 articles total.
**When to use:** Before formatting, after classification.
**Algorithm:**
1. Separate classified articles (dedup_status="NEW" only) into HIGH/MEDIUM/LOW buckets
2. Take up to 8 HIGH-priority articles
3. Fill MEDIUM: take at least 4 (or all available if fewer)
4. Fill LOW: take at least 2 (or all available if fewer)
5. If total < 15 and articles remain, backfill from highest-priority surplus
6. Cap at max_stories (default 15 from config)

**Edge cases to handle:**
- Fewer than 15 total articles: send all, adjust section headers to reflect actual counts
- Zero articles in a priority tier: omit that section entirely, no empty headers
- Zero total articles: send a "no news today" brief (deferred to Phase 7 per DLVR-06, but function should return empty list gracefully)

```python
# Source: project convention (functional style, returns results, no mutation)
def select_articles(
    articles: list[Article],
    max_stories: int = 15,
) -> tuple[list[Article], list[Article], list[Article]]:
    """Select and allocate articles by priority.

    Returns (high, medium, low) tuples of selected articles.
    """
    new_only = [a for a in articles if a.dedup_status == "NEW"]
    high = [a for a in new_only if a.priority == "HIGH"][:8]
    medium = [a for a in new_only if a.priority == "MEDIUM"]
    low = [a for a in new_only if a.priority == "LOW"]

    # Ensure minimums and cap at max_stories
    # ... allocation logic
    return high, medium, low
```

### Pattern 2: Telegram Message Formatting (HTML)
**What:** Build Telegram-compatible HTML message from selected articles.
**When to use:** After selection, before sending.
**Key constraints:**
- Only these HTML tags work: `<b>`, `<i>`, `<a href="...">`, `<u>`, `<s>`, `<code>`, `<pre>`, `<blockquote>`
- NO `<br>` -- use `\n` for line breaks
- Must escape `<`, `>`, `&` in article text as `&lt;`, `&gt;`, `&amp;`
- The 4096 character limit applies to the text AFTER HTML parsing (tag overhead doesn't count against limit in the same way, but the rendered text + tags combined must be under 4096)

```python
# Source: CONTEXT.md approved mockup + Telegram API docs
def format_article_html(article: Article, number: int) -> str:
    """Format a single article as Telegram HTML."""
    # Escape user-generated content
    title = _escape_html(article.title)
    source = _escape_html(article.source)

    lines = [
        f"{_number_emoji(number)} <b>{title}</b>",
        f"   <i>{source}</i>",  # + location if present
    ]
    if article.summary:
        lines.append(f"   {_escape_html(article.summary)}")
    # Conditional entity line
    entities = _build_entity_line(article)
    if entities:
        lines.append(f"   {entities}")
    lines.append(f'   <a href="{article.url}">Read</a>')
    return "\n".join(lines)

def _escape_html(text: str) -> str:
    """Escape HTML special characters for Telegram."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
```

### Pattern 3: Message Chunking
**What:** Split messages exceeding 4096 chars at article boundaries.
**When to use:** After formatting the full message, before sending.
**Strategy:** Split at article boundaries (never mid-article). Each chunk gets a part indicator if multiple chunks needed (e.g., "Part 1/3" appended to header). Header goes in first chunk only; footer in last chunk only.

```python
def chunk_message(
    header: str,
    article_blocks: list[str],
    footer: str,
    max_chars: int = 4096,
) -> list[str]:
    """Split formatted message into chunks that fit Telegram's limit."""
    chunks: list[str] = []
    current = header + "\n"

    for block in article_blocks:
        if len(current) + len(block) + 2 > max_chars:
            chunks.append(current.rstrip())
            current = ""
        current += "\n" + block + "\n"

    # Append footer to last chunk
    if current.strip():
        current += "\n" + footer
        chunks.append(current.rstrip())

    return chunks
```

### Pattern 4: httpx POST to Telegram
**What:** Send formatted message via Telegram Bot API sendMessage endpoint.
**When to use:** For each chunk, for each chat_id.

```python
# Source: Telegram Bot API docs + project httpx pattern (gnews_fetcher.py)
TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"

def send_telegram_message(
    token: str,
    chat_id: str,
    text: str,
) -> tuple[bool, str | None]:
    """Send a single message via Telegram Bot API.

    Returns (success, error_message_or_none).
    """
    url = TELEGRAM_API.format(token=token)
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "link_preview_options": {"is_disabled": True},
    }
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            return False, data.get("description", "Unknown Telegram error")
        return True, None
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 429:
            # Rate limited -- could retry after Retry-After header
            return False, "rate limited (429)"
        return False, f"HTTP {exc.response.status_code}"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)
```

### Pattern 5: Morning vs Evening Detection
**What:** Determine if current delivery is morning or evening based on IST time.
**When to use:** When building the message header.

```python
from datetime import UTC, datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))

def get_delivery_period() -> str:
    """Return 'Morning' or 'Evening' based on current IST hour."""
    now_ist = datetime.now(UTC).astimezone(IST)
    return "Morning" if now_ist.hour < 12 else "Evening"
```

### Anti-Patterns to Avoid
- **Importing python-telegram-bot for one endpoint:** Massive dependency for a simple POST call. The project already has httpx.
- **Using Markdown parse mode:** Telegram MarkdownV2 has aggressive escaping requirements (must escape `.`, `-`, `(`, `)`, `!` etc.). HTML is far simpler and explicitly locked by user decision.
- **Hard-cutting messages at 4096 chars:** Breaks HTML tags, cuts articles mid-sentence. Always split at article boundaries.
- **Sending all messages in parallel:** Telegram delivers messages out of order. Sequential sending preserves correct message order.
- **Forgetting to escape HTML in article content:** Titles with `<`, `>`, `&` will break Telegram's HTML parser, causing the entire message to fail silently (Telegram returns 400 Bad Request).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTML escaping | Custom regex replacer | Simple str.replace chain for &, <, > | Only 3 entities needed per Telegram docs; regex is overkill |
| Timezone conversion | Manual hour arithmetic | `datetime.astimezone(IST)` with `timezone(timedelta(hours=5, minutes=30))` | Stdlib handles edge cases correctly |
| HTTP retries | Custom retry loop | Simple single-retry with sleep for 429 | Only 2 chat_ids; sophisticated retry logic unnecessary |
| Number emojis | Lookup table of 20+ emojis | Format string with digit-to-keycap mapping | Unicode keycap digits work: chr(0x0031)+chr(0xFE0F)+chr(0x20E3) for "1" etc., but simpler to use f"{n}." plain text numbering |

**Key insight:** This phase is a "last mile" formatter + HTTP poster. The Telegram Bot API is deliberately simple (one POST endpoint, JSON payload). Resist over-engineering.

## Common Pitfalls

### Pitfall 1: HTML Escaping Failures
**What goes wrong:** Article titles or summaries containing `<`, `>`, or `&` characters cause Telegram to return HTTP 400 "Bad Request: can't parse entities."
**Why it happens:** RSS/GNews article titles often contain ampersands ("AT&T", "R&D"), angle brackets, or HTML fragments.
**How to avoid:** Escape ALL user-generated text (title, summary, source, location, project_name, budget_amount, authority) with `&amp;`, `&lt;`, `&gt;` BEFORE inserting into the HTML template.
**Warning signs:** Tests pass with clean test data but fail with real articles.

### Pitfall 2: 4096 Character Limit Calculation
**What goes wrong:** Message appears under 4096 chars by len() but Telegram rejects it.
**Why it happens:** The 4096 limit applies to the UTF-8 encoded text. Emojis and special characters count as multiple bytes. However, Python's `len()` counts characters, and Telegram also counts characters (not bytes) -- so `len()` is actually correct for this limit. The real issue is confusing "visible text length" with "HTML source length" -- the limit applies to the HTML source including tags.
**How to avoid:** Measure `len(html_text)` to stay under 4096. Include HTML tags in the count.
**Warning signs:** Messages near the limit sometimes fail.

### Pitfall 3: Rate Limiting with Multiple Chat IDs
**What goes wrong:** Second chat_id send fails with 429 when sent immediately after first.
**Why it happens:** Telegram allows ~1 msg/sec per chat, but with 2 chat_ids the bot sends 2 requests in quick succession. At 2 users this is unlikely to trigger limits, but chunked messages (3-4 chunks x 2 users = 6-8 rapid requests) could.
**How to avoid:** Add a small delay (0.5s) between consecutive sendMessage calls. With only 2 users and max ~4 chunks, this adds at most 4 seconds total.
**Warning signs:** Intermittent 429 errors in GitHub Actions logs.

### Pitfall 4: Link Preview Flooding
**What goes wrong:** Telegram generates link previews for every article URL, making messages extremely long and cluttered.
**Why it happens:** Default sendMessage behavior shows link previews.
**How to avoid:** Set `link_preview_options: {"is_disabled": true}` in every sendMessage payload. Note: the older `disable_web_page_preview` parameter still works but is deprecated since Bot API 7.0.
**Warning signs:** Messages display with large preview cards instead of clean text.

### Pitfall 5: Empty Priority Sections
**What goes wrong:** Message includes "HIGH PRIORITY (0 stories)" header with nothing below it.
**Why it happens:** Formatter doesn't check if a priority tier has zero articles.
**How to avoid:** Only include section headers for tiers that have at least one article. The selection algorithm should return empty lists for missing tiers, and the formatter should skip those sections.
**Warning signs:** Awkward empty sections in test output.

### Pitfall 6: Article URL Escaping in href
**What goes wrong:** URLs with `&` characters break the `<a href="...">` tag.
**Why it happens:** `&` in URLs must be `&amp;` inside HTML attribute values.
**How to avoid:** Escape `&` in URLs too: `article.url.replace("&", "&amp;")`.
**Warning signs:** "Read" links point to wrong or truncated URLs.

## Code Examples

Verified patterns from project codebase and Telegram API docs:

### Telegram sendMessage API Call
```python
# Source: Telegram Bot API docs (core.telegram.org/bots/api#sendmessage)
# + project pattern from gnews_fetcher.py (httpx.Client with timeout)
import httpx

def send_message(token: str, chat_id: str, text: str) -> dict:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "link_preview_options": {"is_disabled": True},
    }
    with httpx.Client(timeout=15.0) as client:
        resp = client.post(url, json=payload)
        resp.raise_for_status()
    return resp.json()
```

### HTML Message Template (from approved mockup)
```python
# Source: CONTEXT.md approved format
HEADER_TEMPLATE = (
    "\U0001f4f0 <b>Khabri {period} Brief</b>\n"
    "{time_ist} IST \u2022 {date_str}\n"
    "{total} stories \u2022 {high_count} HIGH \u2022 {med_count} MED \u2022 {low_count} LOW\n"
    "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"
)

SECTION_HEADER = "\n\U0001f534 <b>{label} PRIORITY ({count} stories)</b>\n"
# Use \U0001f534 for HIGH (red), \U0001f7e1 for MEDIUM (yellow), \U0001f7e2 for LOW (green)

FOOTER_TEMPLATE = (
    "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
    "Powered by Khabri \u2022 Next: {next_time}"
)
```

### respx Mocking Pattern for Telegram API Tests
```python
# Source: project pattern from test_gnews_fetcher.py + test_rss_fetcher.py
import httpx
import respx

TELEGRAM_URL = "https://api.telegram.org/bot{token}/sendMessage"

@respx.mock
def test_send_message_success():
    token = "test-bot-token"
    route = respx.post(f"https://api.telegram.org/bot{token}/sendMessage").respond(
        200, json={"ok": True, "result": {"message_id": 123}}
    )

    success, error = send_telegram_message(token, "12345", "Hello")

    assert success is True
    assert error is None
    assert route.called

@respx.mock
def test_send_message_rate_limited():
    token = "test-bot-token"
    respx.post(f"https://api.telegram.org/bot{token}/sendMessage").respond(
        429, json={"ok": False, "description": "Too Many Requests: retry after 5"}
    )

    success, error = send_telegram_message(token, "12345", "Hello")

    assert success is False
    assert "429" in error
```

### UTC to IST Conversion
```python
# Source: Python stdlib + project convention (datetime.UTC alias from Phase 2)
from datetime import UTC, datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))

def format_ist_time(utc_str: str = "") -> str:
    """Format current time as IST string for Telegram display."""
    now = datetime.now(UTC).astimezone(IST)
    return now.strftime("%-I:%M %p")  # e.g. "7:00 AM"

def format_ist_date(utc_str: str = "") -> str:
    """Format current date as IST string for Telegram display."""
    now = datetime.now(UTC).astimezone(IST)
    return now.strftime("%a, %-d %b %Y")  # e.g. "Fri, 7 Mar 2026"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `disable_web_page_preview` param | `link_preview_options` param | Bot API 7.0 (Jan 2024) | Old param still works but deprecated; use new one |
| `<span class="tg-spoiler">` | `<tg-spoiler>` tag | Bot API 6.x | Both work, but dedicated tag is cleaner |
| No blockquote support | `<blockquote>` and `<blockquote expandable>` | Bot API 7.0 (Jan 2024) | New option for collapsible content |

**Deprecated/outdated:**
- `disable_web_page_preview`: Replaced by `link_preview_options` in Bot API 7.0. Still functional but prefer new API.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.0+ |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/test_telegram_sender.py tests/test_selector.py -x` |
| Full suite command | `uv run pytest tests/ -v --tb=short` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DLVR-01 | Formatted Telegram message sent with HTML priority sections, summaries, metadata, links | unit | `uv run pytest tests/test_telegram_sender.py -x` | No - Wave 0 |
| DLVR-02 | Morning/Evening detection and correct IST display in header | unit | `uv run pytest tests/test_telegram_sender.py::TestDeliveryPeriod -x` | No - Wave 0 |
| DLVR-04 | Selection algorithm: max 8 HIGH, min 4 MED, min 2 LOW, cap 15 | unit | `uv run pytest tests/test_selector.py -x` | No - Wave 0 |
| DLVR-04 | Edge case: fewer than 15 total articles, empty priority tiers | unit | `uv run pytest tests/test_selector.py::TestEdgeCases -x` | No - Wave 0 |
| DLVR-01 | Messages over 4096 chars split correctly at article boundaries | unit | `uv run pytest tests/test_telegram_sender.py::TestChunking -x` | No - Wave 0 |
| DLVR-01 | HTML special chars escaped in article text | unit | `uv run pytest tests/test_telegram_sender.py::TestEscaping -x` | No - Wave 0 |
| DLVR-01 | Pipeline integration: deliver step wired into main.py | unit | `uv run pytest tests/test_main.py -x` | Yes - update needed |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_telegram_sender.py tests/test_selector.py -x`
- **Per wave merge:** `uv run pytest tests/ -v --tb=short`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_telegram_sender.py` -- covers DLVR-01, DLVR-02 (formatting, sending, chunking, escaping)
- [ ] `tests/test_selector.py` -- covers DLVR-04 (selection algorithm, edge cases)
- [ ] Update `tests/test_main.py` -- add delivery integration assertion

## Open Questions

1. **Chat IDs source at runtime**
   - What we know: config.yaml has `chat_ids: []` (empty), bot_token comes from env var TELEGRAM_BOT_TOKEN
   - What's unclear: Should chat_ids also come from an env var (e.g., TELEGRAM_CHAT_IDS comma-separated) or be hardcoded in config.yaml?
   - Recommendation: Use env var `TELEGRAM_CHAT_IDS` (comma-separated) for consistency with other secrets. Config.yaml keeps the empty default. This matches the TELEGRAM_BOT_TOKEN pattern.

2. **Number emoji format**
   - What we know: CONTEXT.md mockup shows "1" with keycap emoji styling
   - What's unclear: Whether to use actual keycap emojis (complex Unicode sequences) or simple "1." plain text numbering
   - Recommendation: Use simple numbered format like "1." or Unicode digit + period. Keycap emojis add visual clutter in mobile rendering and are harder to maintain. The mockup intent is "numbered list", not "emoji art."

3. **Retry strategy for failed sends**
   - What we know: Only 2 users, rate limits are generous (30 msg/sec global)
   - What's unclear: Whether to retry on failure or just log and continue
   - Recommendation: Single retry with 2-second delay for 429/network errors. Log failures but don't crash the pipeline. For 2 users, a single retry is sufficient.

## Sources

### Primary (HIGH confidence)
- [Telegram Bot API docs](https://core.telegram.org/bots/api) - sendMessage endpoint, HTML formatting, link_preview_options
- [Telegram Bot FAQ](https://core.telegram.org/bots/faq) - Rate limits (1 msg/sec/chat, 30 msg/sec global)
- Project codebase: `src/pipeline/fetchers/gnews_fetcher.py` - httpx Client pattern with timeout
- Project codebase: `tests/test_gnews_fetcher.py` - respx mocking pattern for HTTP calls
- Project codebase: `src/pipeline/schemas/config_schema.py` - TelegramConfig, DeliveryConfig, ScheduleConfig schemas
- Project codebase: `src/pipeline/schemas/article_schema.py` - Article model with all fields
- Project codebase: `src/pipeline/main.py` line 153 - Integration point for delivery

### Secondary (MEDIUM confidence)
- [Telegram HTML formatting guide](https://www.misterchatter.com/docs/telegram-html-formatting-guide-supported-tags/) - Supported HTML tags
- [python-telegram-bot issue #768](https://github.com/python-telegram-bot/python-telegram-bot/issues/768) - Message splitting strategies
- [Telegram Bot API changelog](https://core.telegram.org/bots/api-changelog) - link_preview_options replacing disable_web_page_preview

### Tertiary (LOW confidence)
- None -- all findings verified against official docs or project codebase

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - httpx is already used, Telegram API is simple REST
- Architecture: HIGH - follows established project patterns (functional style, Pydantic models, httpx + respx)
- Pitfalls: HIGH - HTML escaping and 4096 limit are well-documented Telegram API constraints
- Selection algorithm: MEDIUM - edge case allocation logic is straightforward but has combinatorial edge cases that need thorough testing

**Research date:** 2026-03-07
**Valid until:** 2026-04-07 (stable -- Telegram Bot API changes infrequently)
