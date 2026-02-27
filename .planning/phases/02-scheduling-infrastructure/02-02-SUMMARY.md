---
phase: 02-scheduling-infrastructure
plan: "02"
subsystem: infra
tags: [purge, tdd, state-management, lifecycle, python, pytest, seen-store, history]

# Dependency graph
requires:
  - phase: 02-scheduling-infrastructure
    plan: "01"
    provides: pipeline.main.run() entrypoint, pipeline.utils.loader.load_seen

provides:
  - purge_old_entries(store, days=7) -> SeenStore in src/pipeline/utils/purge.py
  - save_seen(store, path) helper in src/pipeline/utils/loader.py
  - Pipeline entrypoint wired to load, purge (7 days), and save both state files on every run

affects:
  - deliver.yml (purge runs before EndBug commit-back, keeping state files lean)
  - 03-fetchers (fetch phase adds to seen/history after purge runs)
  - all future phases (purge is now always-on in the run() lifecycle)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "TDD RED/GREEN: tests written before implementation, ImportError confirmed before purge.py created"
    - "Purge utility: fail-safe design — malformed timestamps kept, naive timestamps assumed UTC"
    - "save_seen: minimal single-responsibility function, counterpart to load_seen"
    - "Ruff UP017 auto-fixed in test file: timezone.utc -> datetime.UTC (consistent with 02-01 decision)"

key-files:
  created:
    - src/pipeline/utils/purge.py
    - tests/test_purge.py
    - tests/test_main.py
  modified:
    - src/pipeline/utils/loader.py
    - src/pipeline/main.py

key-decisions:
  - "Malformed seen_at entries kept (not dropped): fail-safe over fail-silent — log warning and preserve"
  - "Naive timestamps assumed UTC: consistent with ISO 8601 pipeline convention, no silent date arithmetic error"
  - "purge_old_entries returns new SeenStore (not mutates): functional style, safe for re-assignment"
  - "save_seen added to loader.py (not a separate file): keeps all data-file I/O in one module"

requirements-completed: [INFRA-05]

# Metrics
duration: 2min
completed: "2026-02-27"
---

# Phase 2 Plan 02: 7-Day History Purge Utility Summary

**purge_old_entries(store, days=7) with fail-safe malformed-timestamp handling wired into pipeline.main; save_seen helper added to loader.py; full TDD RED/GREEN cycle**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-27T15:34:43Z
- **Completed:** 2026-02-27T15:36:35Z
- **Tasks:** 2 of 2
- **Files modified:** 5

## Accomplishments

- Created `src/pipeline/utils/purge.py` — `purge_old_entries(store, days=7)` returns a new SeenStore, removes entries older than 7 days, keeps malformed timestamps (logged as warning), treats naive timestamps as UTC
- Added `save_seen(store, path)` to `src/pipeline/utils/loader.py` — writes SeenStore back to disk, counterpart to existing `load_seen`
- Updated `src/pipeline/main.py` — `run()` now loads, purges, and saves both `data/seen.json` and `data/history.json` on every pipeline invocation
- Created `tests/test_purge.py` — 6 tests covering old, recent, mixed, malformed, empty, and naive-timestamp scenarios
- Created `tests/test_main.py` — 2 tests for `run()`: no exception, logs START and END markers
- All 31 project tests pass (8 new + 23 existing Phase 1 tests)

## Task Commits

Each task was committed atomically:

1. **Task 1: RED — Write failing tests** - `5274594` (test)
2. **Task 2: GREEN — Implement purge, save_seen, wire main.py** - `67e20df` (feat)

**Plan metadata:** _(docs commit, see below)_

## Files Created/Modified

- `src/pipeline/utils/purge.py` — Purge utility: `purge_old_entries()` with fail-safe malformed handling
- `src/pipeline/utils/loader.py` — Added `save_seen()` helper at bottom of file
- `src/pipeline/main.py` — Updated `run()`: load → purge → save → log counts → pipeline phases stub
- `tests/test_purge.py` — 6 RED-phase tests, class-based pattern, covers all edge cases
- `tests/test_main.py` — 2 tests for entrypoint: no exception, START/END log markers

## Decisions Made

- Malformed `seen_at` entries are kept, not dropped — fail-safe design: a corrupted timestamp should not silently lose data; log a warning and preserve the entry
- Naive timestamps (no tzinfo) assumed UTC — consistent with pipeline convention; avoids silent off-by-N date arithmetic
- `purge_old_entries` returns a new `SeenStore` (does not mutate input) — functional style, safe for `seen = purge_old_entries(seen)` re-assignment pattern
- `save_seen` added to `loader.py` (not a new file) — all disk I/O for data files stays in one module

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Ruff UP017 auto-fixed in test_purge.py: `timezone.utc` -> `datetime.UTC` alias**
- **Found during:** Task 1 (pre-commit ruff hook on test files)
- **Issue:** Test helper used `from datetime import datetime, timedelta, timezone` and `timezone.utc` — ruff UP017 flags this for Python 3.11+ which has `datetime.UTC`
- **Fix:** Ruff pre-commit hook auto-fixed: changed to `from datetime import UTC, datetime, timedelta` and replaced `timezone.utc` with `UTC`
- **Files modified:** `tests/test_purge.py`
- **Verification:** Ruff passed on re-commit
- **Committed in:** `5274594` (Task 1 commit — re-staged after auto-fix)

---

**Total deviations:** 1 auto-fixed (Rule 1 — linting/correctness, consistent with 02-01 decision)
**Impact on plan:** Trivial import modernization. No behavior change. Aligns with established `datetime.UTC` pattern.

## Issues Encountered

None — implementation matched plan exactly. All 6 purge edge cases (old, recent, mixed, malformed, empty, naive) passed first run without iteration.

## Next Phase Readiness

- `pipeline.main.run()` now has full lifecycle: load state → purge → save → pipeline phases (3-7 add here)
- `purge_old_entries` is importable from `pipeline.utils.purge` — future phases can call directly if needed
- `save_seen` is importable from `pipeline.utils.loader` — Phase 3 fetchers will use it after adding new entries
- deliver.yml EndBug commit-back targets `data/seen.json` + `data/history.json` — these are now always lean (7-day window) before commit
- Phase 3 (RSS fetchers) can proceed: entrypoint lifecycle is complete

---
*Phase: 02-scheduling-infrastructure*
*Completed: 2026-02-27*

## Self-Check: PASSED

- FOUND: src/pipeline/utils/purge.py
- FOUND: tests/test_purge.py
- FOUND: tests/test_main.py
- FOUND: src/pipeline/utils/loader.py
- FOUND: src/pipeline/main.py
- FOUND: .planning/phases/02-scheduling-infrastructure/02-02-SUMMARY.md
- FOUND commit: 5274594 (Task 1 — RED tests)
- FOUND commit: 67e20df (Task 2 — GREEN implementation)
