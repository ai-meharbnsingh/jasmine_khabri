# Phase 7: Email Delivery and Edge Cases - Context

**Gathered:** 2026-03-07
**Status:** Ready for planning

<domain>
## Phase Boundary

HTML email digests sent via Gmail SMTP alongside Telegram delivery, plus edge case handling for no-news days, slow-news days, and HIGH story overflow. Email uses the same article selection and detail level as Telegram but with a styled HTML card-based layout. Edge cases produce appropriate user-facing responses on both channels.

</domain>

<decisions>
## Implementation Decisions

### Gmail SMTP authentication
- App Password approach (not OAuth2) — simple, no Google Cloud project needed
- Two env vars: `GMAIL_USER` and `GMAIL_APP_PASSWORD` as GitHub Actions secrets
- Python stdlib `smtplib` with STARTTLS on smtp.gmail.com:587

### Email recipients
- Same two users as Telegram (husband and wife)
- Recipients from `config.yaml` email.recipients list or `GMAIL_RECIPIENTS` env var
- Always-on: every scheduled delivery sends both Telegram AND email
- Disabled via `config.yaml` email.enabled=false if needed

### Failure behavior
- Warn and skip if Gmail credentials not set — same pattern as TELEGRAM_BOT_TOKEN
- Log warning, skip email, continue pipeline — never crash on missing email config

### HTML email design
- Clean card-based layout with colored left border per priority
- Traffic light colors: red (#e53e3e) HIGH, amber/orange (#dd6b20) MEDIUM, green (#38a169) LOW
- Each article is a card: title, source, location, AI summary, conditional entities, clickable link
- Same full detail level as Telegram — consistent across both channels
- Header with brief title, IST time, date, and story count breakdown
- Footer with "Powered by Khabri" and next delivery time

### Email subject line
- Format: "Khabri Morning Brief — {N} stories ({X} High)"
- Includes story count and HIGH count for inbox scanning

### Claude's Discretion
- No-news / slow-news messaging (what message to send on zero or few articles, on which channels)
- HIGH story overflow behavior (how "reply 'more'" works, whether email includes overflow notice)
- Jinja2 template structure vs inline HTML strings
- Email retry logic on SMTP failures
- Responsive email CSS approach (table-based for compatibility)
- Whether to use multipart MIME (text + HTML) or HTML-only

</decisions>

<specifics>
## Specific Ideas

- Email should feel like a professional newsletter — card-based, clean, not cluttered
- Visual consistency with Telegram: same priority colors (traffic light), same article detail level
- Subject line gives enough info to decide whether to open: "Khabri Morning Brief — 15 stories (8 High)"

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/pipeline/deliverers/telegram_sender.py`: `deliver_articles` orchestrator, `select_articles` import, `get_delivery_period()`, `_escape_html()` — reusable for email flow
- `src/pipeline/deliverers/selector.py`: `select_articles()` — already returns (high, medium, low) tuple, shared between Telegram and email
- `src/pipeline/schemas/config_schema.py`: `EmailConfig` with enabled, recipients fields already defined
- `src/pipeline/schemas/article_schema.py`: Article model with all fields needed for email cards

### Established Patterns
- Functional style: deliver_articles selects, formats, sends — email can follow same pattern
- Env var precedence over config (TELEGRAM_BOT_TOKEN pattern → GMAIL_USER, GMAIL_APP_PASSWORD)
- Warn-and-skip on missing credentials (never crash)
- IST display via `_IST = timezone(timedelta(hours=5, minutes=30))`

### Integration Points
- `main.py` line 158: "Phase 7: email delivery (not yet implemented)" — wire email after Telegram delivery
- `deliver.yml`: needs GMAIL_USER and GMAIL_APP_PASSWORD secrets added
- `selector.py`: shared selection — email uses same (high, medium, low) output as Telegram
- Edge case handlers need to interact with both Telegram and email delivery paths

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 07-email-delivery-and-edge-cases*
*Context gathered: 2026-03-07*
