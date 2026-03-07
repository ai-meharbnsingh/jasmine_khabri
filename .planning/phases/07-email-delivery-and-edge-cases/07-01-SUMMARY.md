---
phase: 07-email-delivery-and-edge-cases
plan: 01
subsystem: delivery
tags: [gmail, smtp, email, html, mime, starttls]

# Dependency graph
requires:
  - phase: 06-telegram-delivery
    provides: "selector.py, telegram_sender.py patterns (_IST, _escape_html, get_delivery_period)"
provides:
  - "Gmail SMTP email sender with HTML formatting (email_sender.py)"
  - "deliver_email orchestrator function for pipeline integration"
  - "deliver.yml Gmail secrets (GMAIL_USER, GMAIL_APP_PASSWORD, GMAIL_RECIPIENTS)"
affects: [07-02-edge-cases, 11-production-hardening]

# Tech tracking
tech-stack:
  added: [smtplib, email.mime.multipart, email.mime.text, ssl]
  patterns: [inline-css-html-email, table-based-email-layout, mime-multipart-alternative]

key-files:
  created:
    - src/pipeline/deliverers/email_sender.py
    - tests/test_email_sender.py
  modified:
    - src/pipeline/main.py
    - .github/workflows/deliver.yml

key-decisions:
  - "Reuse _IST, _escape_html, get_delivery_period from telegram_sender.py -- DRY, same timezone and escape logic"
  - "Table-based HTML with inline CSS -- maximum email client compatibility (Outlook, Gmail, Apple Mail)"
  - "MIMEMultipart('alternative') with plain-text fallback -- graceful degradation for text-only clients"
  - "Per-recipient send with single retry and 2s delay -- same pattern as Telegram sender"
  - "GMAIL_RECIPIENTS env var overrides config.email.recipients -- secrets in GitHub, not YAML"
  - "ssl.create_default_context() for STARTTLS -- secure default without manual cert management"

patterns-established:
  - "Email sender mirrors telegram_sender orchestration: check creds -> select -> format -> send -> retry"
  - "Priority-colored cards: #e53e3e HIGH, #dd6b20 MEDIUM, #38a169 LOW"
  - "Max-width 600px outer table for email client rendering"

requirements-completed: [DLVR-03]

# Metrics
duration: 4min
completed: 2026-03-07
---

# Phase 7 Plan 1: Email Sender Summary

**Gmail SMTP email sender with priority-colored HTML cards, MIMEMultipart alternative, and graceful credential skip**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-07T10:54:54Z
- **Completed:** 2026-03-07T10:59:16Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- HTML email digest with priority-colored article cards (table-based, inline CSS for email client compatibility)
- Gmail SMTP send via STARTTLS with App Password auth, 15s timeout, single-retry on failure
- Pipeline integration: email delivery runs after Telegram on every scheduled delivery
- 43 new tests (265 total) covering formatting, SMTP mocking, env var handling, retry logic

## Task Commits

Each task was committed atomically:

1. **Task 1: Email HTML formatter and SMTP sender** - `a75e4b2` (test: RED), `946fcfa` (feat: GREEN)
2. **Task 2: Wire email delivery into pipeline and deliver.yml** - `017ecf2` (feat)

_Note: Task 1 used TDD with separate test and implementation commits._

## Files Created/Modified
- `src/pipeline/deliverers/email_sender.py` - Gmail SMTP email sender with HTML formatting, MIME multipart, orchestrator
- `tests/test_email_sender.py` - 43 tests for email formatting, SMTP send, orchestrator
- `src/pipeline/main.py` - Added deliver_email call after Telegram delivery
- `.github/workflows/deliver.yml` - Added GMAIL_USER, GMAIL_APP_PASSWORD, GMAIL_RECIPIENTS secrets

## Decisions Made
- Reused _IST, _escape_html, get_delivery_period from telegram_sender.py for DRY
- Table-based HTML with inline CSS for email client compatibility
- MIMEMultipart("alternative") with plain-text fallback for text-only clients
- Per-recipient send loop with single retry (mirrors Telegram pattern)
- GMAIL_RECIPIENTS env var takes precedence over config.email.recipients
- ssl.create_default_context() for STARTTLS security

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required

**External services require manual configuration:**
- **GMAIL_USER**: Gmail address for sending (add as GitHub secret)
- **GMAIL_APP_PASSWORD**: Gmail App Password (Settings > Security > 2-Step Verification > App Passwords)
- **GMAIL_RECIPIENTS**: Comma-separated recipient emails (add as GitHub secret)

## Next Phase Readiness
- Email delivery is end-to-end wired into the pipeline
- Plan 07-02 (edge cases) can build on this foundation for error handling and empty digest scenarios
- 265 tests passing, full suite green

---
*Phase: 07-email-delivery-and-edge-cases*
*Completed: 2026-03-07*
