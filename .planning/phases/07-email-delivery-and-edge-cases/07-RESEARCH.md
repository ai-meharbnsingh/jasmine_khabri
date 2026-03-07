# Phase 7: Email Delivery and Edge Cases - Research

**Researched:** 2026-03-07
**Domain:** Gmail SMTP email delivery (Python stdlib) + pipeline edge case handling
**Confidence:** HIGH

## Summary

Phase 7 adds HTML email digests via Gmail SMTP alongside existing Telegram delivery, plus handles three edge cases: no-news days, slow-news days, and HIGH story overflow. The email sender follows the exact same pattern as `telegram_sender.py` -- functional style, env var precedence, warn-and-skip on missing credentials. Python's stdlib `smtplib` + `email.mime` is the entire email stack; no third-party libraries needed.

Edge case handling is a cross-cutting concern that touches both delivery channels. The selector already returns empty tuples for zero articles, but neither `deliver_articles` nor any future `deliver_email` currently sends a "no news today" message -- they silently return 0. The overflow detection (>8 HIGH) requires checking `all_high` count against the `_HIGH_CAP` and passing overflow metadata to the formatter.

**Primary recommendation:** Build `email_sender.py` mirroring `telegram_sender.py` structure (format + send + orchestrate), use multipart MIME (text/plain + text/html) for maximum compatibility, and add edge case handling as a shared utility consumed by both delivery channels.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Gmail SMTP with App Password (not OAuth2) -- `GMAIL_USER` and `GMAIL_APP_PASSWORD` env vars
- Python stdlib `smtplib` with STARTTLS on smtp.gmail.com:587
- Recipients from `config.yaml` email.recipients list or `GMAIL_RECIPIENTS` env var
- Always-on: every scheduled delivery sends both Telegram AND email
- Disabled via `config.yaml` email.enabled=false if needed
- Warn-and-skip if Gmail credentials not set (never crash)
- Card-based HTML layout with colored left border per priority
- Traffic light colors: red (#e53e3e) HIGH, amber (#dd6b20) MEDIUM, green (#38a169) LOW
- Each card: title, source, location, AI summary, conditional entities, clickable link
- Same full detail level as Telegram
- Header with title, IST time, date, story count breakdown
- Footer with "Powered by Khabri" and next delivery time
- Subject: "Khabri Morning Brief -- {N} stories ({X} High)"

### Claude's Discretion
- No-news / slow-news messaging (what message to send on zero or few articles, on which channels)
- HIGH story overflow behavior (how "reply 'more'" works, whether email includes overflow notice)
- Jinja2 template structure vs inline HTML strings
- Email retry logic on SMTP failures
- Responsive email CSS approach (table-based for compatibility)
- Whether to use multipart MIME (text + HTML) or HTML-only

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DLVR-03 | System delivers HTML email digest via Gmail SMTP with styled template (priority-colored sections, article cards) | Gmail SMTP via stdlib smtplib, multipart MIME, inline CSS card layout, env var auth pattern |
| DLVR-05 | System sends breaking news alerts for critical HIGH-priority stories between scheduled deliveries | **NOTE: REQUIREMENTS.md maps DLVR-05 to Phase 11, not Phase 7. Phase description lists it but it is OUT OF SCOPE for this phase per traceability matrix.** |
| DLVR-06 | System handles slow news days gracefully (sends all available if <15, sends "no news" message if zero) | Edge case handler utility, "no news" message for both Telegram and email channels |
| DLVR-07 | System notifies users when overflow HIGH stories exist (>8 HIGH, "reply 'more' to see them") | Overflow count passed from selector, appended to delivery message on both channels |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| smtplib | stdlib | SMTP connection and sending | Python built-in, no dependencies, Gmail SMTP well-supported |
| email.mime.multipart | stdlib | MIME multipart message construction | Standard for HTML+text emails |
| email.mime.text | stdlib | Text/HTML parts | Pairs with multipart |
| ssl | stdlib | STARTTLS context | Required for Gmail SMTP security |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| string.Template or f-strings | stdlib | HTML template rendering | Inline HTML -- no Jinja2 needed for 1 template |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Inline HTML strings | Jinja2 templates | Jinja2 adds dependency for a single template; inline f-strings are sufficient and keep zero new deps |
| Multipart MIME | HTML-only | Multipart adds plain-text fallback for old/text-only clients; minimal extra code |
| smtplib | SendGrid/Mailgun | External service adds API key management; Gmail SMTP is free and sufficient for 2 recipients |

**Installation:**
```bash
# No new packages needed -- all Python stdlib
```

## Architecture Patterns

### Recommended Project Structure
```
src/pipeline/deliverers/
  __init__.py
  selector.py           # Existing -- shared selection logic
  telegram_sender.py    # Existing -- Telegram delivery
  email_sender.py       # NEW -- Gmail SMTP delivery
  edge_cases.py         # NEW -- shared edge case handling
```

### Pattern 1: Email Sender (mirror telegram_sender.py)
**What:** `email_sender.py` follows identical structure: format functions, send function, orchestrator
**When to use:** All email delivery
**Example:**
```python
# Source: stdlib smtplib docs + project pattern from telegram_sender.py
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

def send_email(
    gmail_user: str,
    gmail_password: str,
    recipients: list[str],
    subject: str,
    html_body: str,
    text_body: str,
) -> tuple[bool, str | None]:
    """Send HTML email via Gmail SMTP with STARTTLS."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = gmail_user
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    context = ssl.create_default_context()
    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=15) as server:
            server.starttls(context=context)
            server.login(gmail_user, gmail_password)
            server.sendmail(gmail_user, recipients, msg.as_string())
        return True, None
    except smtplib.SMTPException as exc:
        return False, str(exc)
```

### Pattern 2: Edge Case Handler (shared utility)
**What:** Functions that detect edge conditions and produce appropriate messages for both channels
**When to use:** Called from both Telegram and email delivery orchestrators
**Example:**
```python
def check_edge_cases(
    articles: list[Article],
    all_high_count: int,
    high_cap: int,
) -> EdgeCaseResult:
    """Detect no-news, slow-news, and overflow conditions."""
    # Returns typed result with flags and messages
```

### Pattern 3: HTML Email Template (inline, table-based)
**What:** Table-based HTML for email client compatibility, inline CSS (no external stylesheets)
**When to use:** Email body formatting
**Key rules:**
- Use `<table>` layout (not `<div>`) for Outlook/Gmail web compatibility
- All CSS must be inline `style=""` attributes (email clients strip `<style>` tags)
- Priority color as left border: `border-left: 4px solid #e53e3e`
- Max width 600px centered for mobile readability
- Background colors for card distinction

### Anti-Patterns to Avoid
- **External CSS or `<style>` block:** Gmail, Outlook strip `<head>` styles; all CSS must be inline
- **`<div>`-based responsive layout:** Outlook renders `<div>` unpredictably; use `<table>` for structure
- **Background images:** Most email clients block them; use background colors only
- **Large inline images:** Adds size, gets clipped; use text + colored borders
- **Shared orchestrator for Telegram+Email:** Keep separate orchestrators that share selector -- cleaner error isolation

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| MIME construction | Manual header formatting | email.mime.multipart + email.mime.text | RFC 2045 compliance, encoding handled |
| TLS/SSL | Manual socket setup | ssl.create_default_context() + server.starttls() | Certificate validation built in |
| HTML entity escaping | Custom replace chains | Reuse `_escape_html()` from telegram_sender.py | Already handles &, <, > in correct order |
| Article selection | Separate selector for email | `selector.py` select_articles() | Already returns (high, med, low) tuple |
| IST timezone | New timezone logic | Reuse `_IST` and `get_delivery_period()` from telegram_sender.py | Already defined and tested |

**Key insight:** The email sender shares 80% of its data flow with Telegram. The selector, period detection, IST timezone, and HTML escaping are all reusable. Only the formatting (HTML cards vs Telegram markup) and sending (SMTP vs Bot API) differ.

## Common Pitfalls

### Pitfall 1: Gmail App Password vs Regular Password
**What goes wrong:** Using regular Gmail password instead of App Password fails with authentication error
**Why it happens:** Gmail blocks "less secure app" sign-ins by default since May 2022
**How to avoid:** Documentation must specify: Gmail Settings > Security > 2FA enabled > App Passwords > generate one for "Mail"
**Warning signs:** `smtplib.SMTPAuthenticationError` with "Application-specific password required"

### Pitfall 2: Email Client CSS Stripping
**What goes wrong:** Styled email looks broken in Gmail web, Outlook, Apple Mail
**Why it happens:** Email clients strip `<style>` blocks and external CSS for security
**How to avoid:** ALL CSS must be inline `style=""` attributes on each element. Use table-based layout.
**Warning signs:** Email looks styled in browser preview but plain/broken in actual email client

### Pitfall 3: Gmail Send Limits
**What goes wrong:** Hitting Gmail's 500 recipients/day limit
**Why it happens:** Not a concern for 2 recipients, but worth documenting
**How to avoid:** Only 2 recipients -- well within limits. Log send count for monitoring.
**Warning signs:** `SMTPDataError` with "Daily user sending quota exceeded"

### Pitfall 4: SMTP Connection Timeout in GitHub Actions
**What goes wrong:** SMTP connection hangs or times out in CI environment
**Why it happens:** Network restrictions or DNS resolution delays in GitHub Actions runners
**How to avoid:** Set explicit timeout (15s) on `smtplib.SMTP()`, single retry on timeout, warn-and-skip on failure
**Warning signs:** Pipeline hangs at email step, exceeds workflow timeout

### Pitfall 5: Edge Case -- Empty deliver_articles Return
**What goes wrong:** When zero articles pass filtering, `select_articles` returns empty tuples and `deliver_articles` returns 0 silently -- no "no news" message sent
**Why it happens:** Current code treats 0 articles as "nothing to do" not "tell the user"
**How to avoid:** Edge case handler must intercept BEFORE the "no articles, return 0" early exit and send appropriate message
**Warning signs:** Silent pipeline runs with no user notification on zero-article days

### Pitfall 6: Overflow Detection Requires Pre-Selection Count
**What goes wrong:** After `select_articles` caps HIGH at 8, the overflow count is lost
**Why it happens:** `select_articles` returns only selected articles, not total available
**How to avoid:** Either: (a) return overflow count from selector, or (b) count HIGH articles before calling selector
**Warning signs:** Cannot tell if 8 HIGH articles means "exactly 8" or "8 selected from 12"

## Code Examples

### Gmail SMTP with STARTTLS
```python
# Source: Python stdlib smtplib docs
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

context = ssl.create_default_context()
with smtplib.SMTP("smtp.gmail.com", 587, timeout=15) as server:
    server.starttls(context=context)
    server.login("user@gmail.com", "app-password-here")
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Test"
    msg["From"] = "user@gmail.com"
    msg["To"] = "recipient@example.com"
    msg.attach(MIMEText("Plain text fallback", "plain"))
    msg.attach(MIMEText("<h1>HTML version</h1>", "html"))
    server.sendmail("user@gmail.com", ["recipient@example.com"], msg.as_string())
```

### Table-Based Email Card Template
```html
<!-- Source: Email client compatibility best practices -->
<table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;margin:0 auto;font-family:Arial,sans-serif;">
  <tr>
    <td style="padding:12px 16px;border-left:4px solid #e53e3e;background:#fafafa;margin-bottom:8px;">
      <p style="margin:0 0 4px;font-weight:bold;font-size:15px;">
        <a href="https://example.com/article" style="color:#1a202c;text-decoration:none;">Article Title Here</a>
      </p>
      <p style="margin:0 0 4px;font-size:13px;color:#718096;">ET Realty | Mumbai</p>
      <p style="margin:0 0 4px;font-size:14px;color:#4a5568;">AI summary of the article impact...</p>
      <p style="margin:0;font-size:12px;color:#a0aec0;">Budget: 500 Cr | Authority: NHAI</p>
    </td>
  </tr>
  <tr><td style="height:8px;"></td></tr> <!-- spacer -->
</table>
```

### Edge Case: No-News Message
```python
# Recommended: send on both channels
NO_NEWS_TELEGRAM = (
    "\U0001f4f0 <b>Khabri {period} Brief</b>\n"
    "{date} | {time}\n"
    "\u2500" * 24 + "\n\n"
    "No relevant infrastructure or real estate news found this cycle.\n"
    "We'll check again at {next_time} IST.\n\n"
    "\u2500" * 24 + "\n"
    "Powered by Khabri"
)
```

### Overflow HIGH Notice
```python
# Append to delivery message when all_high > _HIGH_CAP
overflow_count = all_high_count - HIGH_CAP  # e.g., 12 - 8 = 4
overflow_notice = f"\n\u26a0\ufe0f {overflow_count} more HIGH-priority stories available -- reply 'more' to see them"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Gmail "less secure apps" toggle | App Passwords with 2FA | May 2022 | Must use App Password, not regular password |
| `<div>` email layouts | `<table>` layouts | Always for email | Outlook still requires tables for reliable rendering |
| smtplib without context manager | `with smtplib.SMTP() as server:` | Python 3.x | Auto-closes connection, prevents resource leaks |

## Open Questions

1. **Overflow "reply 'more'" mechanism**
   - What we know: DLVR-07 says "reply 'more' to see them" when >8 HIGH
   - What's unclear: There is no Telegram bot listener yet (Phase 8). The "reply 'more'" cannot be functional until the bot exists.
   - Recommendation: Include the overflow notice text in the delivery message now. The actual bot handler for "more" will be built in Phase 8-10. For email, include overflow notice but note that email reply is not supported -- "more" only works via Telegram.

2. **DLVR-05 (Breaking News) scope**
   - What we know: REQUIREMENTS.md maps DLVR-05 to Phase 11, not Phase 7
   - What's unclear: Phase description includes DLVR-05 in the requirement list
   - Recommendation: Follow REQUIREMENTS.md traceability -- DLVR-05 is Phase 11 scope. Phase 7 should NOT implement breaking news alerts.

3. **Selector overflow metadata**
   - What we know: `select_articles` currently returns only `(high, med, low)` tuple
   - What's unclear: Whether to modify selector signature or count before calling it
   - Recommendation: Count all HIGH articles before calling `select_articles` in the orchestrator. Avoids modifying existing tested selector API. Simple: `all_high_count = sum(1 for a in articles if a.priority == "HIGH" and a.dedup_status == "NEW")`.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (via uv) |
| Config file | pyproject.toml [tool.pytest.ini_options] |
| Quick run command | `uv run pytest tests/test_email_sender.py tests/test_edge_cases.py -x` |
| Full suite command | `uv run pytest tests/ -x` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DLVR-03 | HTML email sent via Gmail SMTP with styled cards | unit | `uv run pytest tests/test_email_sender.py -x` | No -- Wave 0 |
| DLVR-06 | No-news sends message; slow-news sends all available | unit | `uv run pytest tests/test_edge_cases.py -x` | No -- Wave 0 |
| DLVR-07 | Overflow HIGH notice appended when >8 HIGH | unit | `uv run pytest tests/test_edge_cases.py -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_email_sender.py tests/test_edge_cases.py -x`
- **Per wave merge:** `uv run pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_email_sender.py` -- covers DLVR-03 (email formatting, SMTP send mock, orchestrator)
- [ ] `tests/test_edge_cases.py` -- covers DLVR-06, DLVR-07 (no-news, slow-news, overflow)

## Sources

### Primary (HIGH confidence)
- Python stdlib docs: smtplib, email.mime.multipart, email.mime.text, ssl -- SMTP with Gmail STARTTLS
- Project source: `src/pipeline/deliverers/telegram_sender.py` -- established delivery pattern
- Project source: `src/pipeline/deliverers/selector.py` -- shared article selection
- Project source: `src/pipeline/schemas/config_schema.py` -- EmailConfig already defined

### Secondary (MEDIUM confidence)
- Gmail App Password requirements (post-May 2022 policy change)
- Email client CSS compatibility (table-based, inline styles) -- widely documented best practice

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- Python stdlib only, no external dependencies, Gmail SMTP well-documented
- Architecture: HIGH -- mirrors existing telegram_sender.py pattern exactly, established project conventions
- Pitfalls: HIGH -- Gmail SMTP and email client rendering are well-understood domains
- Edge cases: MEDIUM -- overflow "reply more" has a dependency on unbuilt bot (Phase 8+)

**Research date:** 2026-03-07
**Valid until:** 2026-04-07 (stable domain, stdlib, no fast-moving dependencies)
