---
phase: 01-project-scaffold
plan: 03
subsystem: infra
tags: [pytest, pre-commit, ruff, schema-validation, smoke-tests, test-fixtures]

# Dependency graph
requires:
  - phase: 01-project-scaffold/01-01
    provides: src-layout package structure, uv sync environment, placeholder modules
  - phase: 01-project-scaffold/01-02
    provides: Pydantic schema models, loader functions, default data files

provides:
  - tests/conftest.py with shared path fixtures (data_dir, config_path, keywords_path, seen_path, history_path)
  - tests/test_schemas.py with 23 passing tests across 4 classes
  - .pre-commit-config.yaml with ruff check + ruff-format hooks (v0.9.0)
  - Proof that all 7 Phase 1 success criteria are met
  - Ruff-clean codebase (lint + format, all files pass)

affects:
  - All future phases: test infrastructure ready, add tests to tests/ directory
  - Phase 2+: conftest.py fixture pattern is the template for additional fixtures
  - CI/CD: pre-commit hooks enforce code quality on every commit

# Tech tracking
tech-stack:
  added:
    - "pytest 9.0.2 — test runner with class-based test organization"
    - "pre-commit 3.0+ — git hooks for code quality enforcement"
    - "ruff v0.9.0 (pre-commit) — linter + formatter enforced at commit time"
  patterns:
    - "Class-based test organization: one class per concern (Config, Keywords, Seen, Imports)"
    - "Path fixtures in conftest.py: tests reference data files via fixtures, never hardcoded paths"
    - "Imports sorted stdlib before third-party (isort rule I001 enforced by ruff)"
    - "Comments on separate lines for long lines — ruff E501 line limit 100 chars"

key-files:
  created:
    - tests/conftest.py
    - tests/test_schemas.py
    - .pre-commit-config.yaml
  modified:
    - src/pipeline/schemas/config_schema.py (moved long comment to separate line for ruff E501)
    - tests/conftest.py (import sort: pathlib before pytest, ruff I001 fix)

key-decisions:
  - "Pre-commit ruff hooks pinned to v0.9.0 matching pyproject.toml dev dep spec (ruff>=0.9)"
  - "Import sort applied: stdlib (pathlib) before third-party (pytest) per PEP 8 / ruff I001"
  - "Long comment moved to separate line in config_schema.py rather than increasing line limit"
  - "23 tests cover all 4 concern areas: locked decisions have explicit assertions, not just 'loads without error'"

patterns-established:
  - "Pattern 5: Class-based pytest — group tests by concern, one class per data type or feature"
  - "Pattern 6: Fixture-based path resolution — conftest.py Path fixtures, never os.getcwd() or hardcoded paths"
  - "Pattern 7: Pre-commit as quality gate — ruff check + format enforced before every commit"
  - "Pattern 8: Explicit locked-decision tests — every locked decision from CONTEXT.md has a named assertion"

requirements-completed: [INFRA-06]

# Metrics
duration: 2min
completed: 2026-02-27
---

# Phase 1 Plan 03: Test Suite and Pre-commit Hooks Summary

**23-test pytest suite proving all Phase 1 scaffold criteria, with ruff pre-commit hooks enforcing code quality on every future commit**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-27T15:03:50Z
- **Completed:** 2026-02-27T15:05:37Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Created tests/conftest.py with 5 shared Path fixtures pointing to data/ directory (data_dir, config_path, keywords_path, seen_path, history_path)
- Created tests/test_schemas.py with 23 tests across 4 classes: TestConfigSchema (5), TestKeywordsSchema (8), TestSeenSchema (3), TestPackageImports (7)
- All 7 Phase 1 success criteria verified with explicit assertions:
  1. uv sync exits 0 — verified
  2. from pipeline.fetchers import rss_fetcher resolves — test passes
  3. Schemas validated by Pydantic — TestConfigSchema + TestKeywordsSchema + TestSeenSchema
  4. pytest exits 0 failures (23/23) — verified
  5. .gitignore excludes .env — verified
  6. pre-commit hooks configured — .pre-commit-config.yaml installed and working
  7. All code passes ruff — ruff check + ruff format both pass
- Pre-commit hooks installed: ruff and ruff-format run automatically on every git commit (verified working on Task 2 commit)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create pytest fixtures and schema validation tests** - `3342f5e` (feat)
2. **Task 2: Configure pre-commit hooks and run full scaffold verification** - `e208421` (feat)

## Files Created/Modified

- `tests/conftest.py` — 5 shared fixtures: data_dir (Path to data/), config_path, keywords_path, seen_path, history_path
- `tests/test_schemas.py` — 23 tests: config defaults, keyword active/inactive flags, seen store loading, all module import smoke tests, __version__ check
- `.pre-commit-config.yaml` — ruff (--fix) + ruff-format hooks, pinned to astral-sh/ruff-pre-commit v0.9.0
- `src/pipeline/schemas/config_schema.py` — moved long comment to separate line (ruff E501 fix)

## Decisions Made

- Pre-commit hooks pinned to v0.9.0 matching the ruff>=0.9 dev dep in pyproject.toml — ensures consistency between CI-time linting and commit-time hooks
- Every locked decision from CONTEXT.md (schedule times, max stories, category active/inactive flags) has its own named test — not just "loads without error"
- Import order fixed to stdlib-before-third-party (pathlib before pytest) — ruff I001 rule enforces PEP 8 import ordering

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Quality] Fixed ruff I001 import sort in tests/conftest.py**
- **Found during:** Task 2 (ruff check)
- **Issue:** `import pytest` appeared before `from pathlib import Path` — violates isort rule (stdlib before third-party)
- **Fix:** Moved `from pathlib import Path` above `import pytest`
- **Files modified:** tests/conftest.py
- **Commit:** e208421

**2. [Rule 1 - Quality] Fixed ruff E501 line too long in config_schema.py**
- **Found during:** Task 2 (ruff check)
- **Issue:** Comment on line 7 made the line 102 chars, exceeding 100-char limit
- **Fix:** Moved comment to dedicated line above the field definition
- **Files modified:** src/pipeline/schemas/config_schema.py
- **Commit:** e208421

**3. [Rule 1 - Quality] Applied ruff format to tests/test_schemas.py**
- **Found during:** Task 2 (ruff format --check)
- **Issue:** test_schemas.py had minor formatting differences (trailing whitespace or quote style)
- **Fix:** `uv run ruff format src/ tests/` — 1 file reformatted
- **Files modified:** tests/test_schemas.py
- **Commit:** e208421

---

**Total deviations:** 3 auto-fixed (all Rule 1 — code quality, not behavioral changes)
**Impact on plan:** None — ruff fixes are cosmetic. All tests still pass identically.

## Issues Encountered

None beyond the expected ruff formatting corrections.

## User Setup Required

None — all tooling is local, no external service configuration required.

## Phase 1 Complete

All 7 success criteria are now met and verified with concrete test evidence:

| Criterion | Status | Evidence |
|-----------|--------|----------|
| uv sync installs deps without errors | PASS | Resolved 25 packages, audited 24 |
| Python imports resolve | PASS | test_import_* all pass |
| Schemas defined + validated by Pydantic | PASS | TestConfigSchema + TestKeywordsSchema + TestSeenSchema |
| pytest exits 0 failures | PASS | 23/23 tests pass |
| .gitignore excludes secrets/.env | PASS | grep -q confirmed |
| Pre-commit hooks configured | PASS | .pre-commit-config.yaml, hooks installed |
| All code passes ruff | PASS | ruff check + ruff format --check both clean |

## Next Phase Readiness

- Phase 2 (scheduling) can add tests to tests/ immediately — conftest.py fixtures are shared
- pre-commit hooks will auto-check and auto-fix ruff issues on every future commit
- All 23 tests serve as regression guard: if Phase 2+ breaks imports or schema defaults, tests will catch it

## Self-Check: PASSED

All created files confirmed present on disk. Both task commits verified in git history.

- tests/conftest.py: FOUND
- tests/test_schemas.py: FOUND
- .pre-commit-config.yaml: FOUND
- Commit 3342f5e: FOUND (feat(01-03): create pytest fixtures and schema validation tests)
- Commit e208421: FOUND (feat(01-03): configure pre-commit hooks and verify all Phase 1 success criteria)

---
*Phase: 01-project-scaffold*
*Completed: 2026-02-27*
