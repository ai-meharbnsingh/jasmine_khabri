---
phase: 06-telegram-delivery
plan: 01
subsystem: delivery
tags: [telegram, html, formatting, chunking, priority-selector]

requires:
  - phase: 05-ai-analysis-pipeline
    provides: "Article with priority, location, project_name, budget_amount, authority fields"
  - phase: 04-filtering-and-deduplication
    provides: "Article with dedup_status field for NEW filtering"
provides:
  - "select_articles: priority-based article allocation algorithm (HIGH/MEDIUM/LOW buckets)"
  - "format_delivery_message: full Telegram HTML message builder with section headers and continuous numbering"
  - "format_article_html: single article HTML formatter with conditional entity/summary lines"
  - "chunk_message: 4096-char boundary splitter for Telegram API"
  - "get_delivery_period: IST-based Morning/Evening detection"
  - "_escape_html: Telegram-safe HTML escaping for &, <, >"
affects: [06-02-telegram-delivery, 07-email-delivery]

tech-stack:
  added: []
  patterns:
    - "Priority allocation with tier caps and backfill"
    - "HTML escaping with &-first ordering to prevent double-escape"
    - "Article-boundary message chunking for Telegram 4096-char limit"

key-files:
  created:
    - src/pipeline/deliverers/selector.py
    - tests/test_selector.py
    - tests/test_telegram_sender.py
  modified:
    - src/pipeline/deliverers/telegram_sender.py

key-decisions:
  - "HIGH cap at 8 is hard limit (no backfill beyond cap) -- prevents HIGH flooding"
  - "Backfill order: MEDIUM surplus then LOW surplus (never exceeds HIGH cap)"
  - "Pipe separator (|) for source-location and entity metadata instead of asterisk"
  - "Section headers use color circle emojis (red/yellow/green) for visual priority distinction"
  - "Empty priority articles silently excluded (no crash, no log noise)"

patterns-established:
  - "Priority tier allocation: cap HIGH, take all MEDIUM/LOW, trim from bottom, backfill from middle"
  - "Conditional HTML line omission: empty fields produce no output (not empty lines)"
  - "IST timezone via timezone(timedelta(hours=5, minutes=30)) -- stdlib only, no pytz"

requirements-completed: [DLVR-04, DLVR-01, DLVR-02]

duration: 4min
completed: 2026-03-07
---

# Phase 6 Plan 1: Selector and Formatter Summary

**Priority-based article selector with 8-HIGH cap and Telegram HTML formatter with 4096-char chunking, IST period detection, and conditional entity rendering**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-07T09:57:40Z
- **Completed:** 2026-03-07T10:01:30Z
- **Tasks:** 2
- **Files modified:** 4
- **Tests added:** 34 (10 selector + 24 formatter)
- **Total test count:** 203

## Accomplishments
- Priority selector allocates articles across HIGH/MEDIUM/LOW tiers respecting configurable max_stories cap
- Telegram HTML formatter produces valid messages with priority sections, continuous numbering, and conditional entity/summary lines
- Message chunking splits at article boundaries keeping each chunk under 4096 characters
- Morning/Evening period detection using IST timezone offset

## Task Commits

Each task was committed atomically:

1. **Task 1: Priority-based article selector** - `5e9c592` (feat)
2. **Task 2: Telegram HTML message formatter with chunking** - `d1f8561` (feat)

_Both tasks followed TDD: RED (failing tests) -> GREEN (implementation) -> verify._

## Files Created/Modified
- `src/pipeline/deliverers/selector.py` - Priority allocation algorithm with HIGH cap and backfill
- `src/pipeline/deliverers/telegram_sender.py` - HTML formatting, escaping, chunking, IST time helpers
- `tests/test_selector.py` - 10 tests covering allocation, filtering, edge cases
- `tests/test_telegram_sender.py` - 24 tests covering escaping, formatting, chunking, period detection

## Decisions Made
- HIGH cap at 8 is hard limit -- backfill from MEDIUM/LOW surplus but never adds more HIGH beyond 8
- Pipe separator (|) used between source and location, and between budget and authority for visual clarity
- Empty-string priority articles are silently excluded alongside non-NEW dedup_status articles
- Section headers use Unicode circle emojis (red HIGH, yellow MEDIUM, green LOW)
- Footer shows next delivery time (Morning -> 4:00 PM, Evening -> 7:00 AM)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed backfill logic exceeding HIGH cap**
- **Found during:** Task 1 (GREEN phase)
- **Issue:** Backfill from surplus added HIGH articles beyond the 8-article cap when total was under max_stories
- **Fix:** Changed backfill order to fill from MEDIUM then LOW surplus only, preserving HIGH cap as hard limit
- **Files modified:** src/pipeline/deliverers/selector.py
- **Verification:** test_standard_allocation_caps_high_at_8 passes with len(high) == 8
- **Committed in:** 5e9c592 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Bug fix was necessary for correct allocation behavior. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Selector and formatter ready for 06-02 (Telegram API integration)
- 06-02 will use select_articles + format_delivery_message to build and send messages via bot token
- All pure logic tested; I/O (HTTP send to Telegram API) deferred to 06-02

---
*Phase: 06-telegram-delivery*
*Completed: 2026-03-07*
