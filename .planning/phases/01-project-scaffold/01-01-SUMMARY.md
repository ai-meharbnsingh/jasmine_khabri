---
phase: 01-project-scaffold
plan: 01
subsystem: infra
tags: [uv, hatchling, pydantic, pyyaml, ruff, pytest, python, src-layout]

# Dependency graph
requires: []
provides:
  - "src/pipeline Python package installable via uv sync"
  - "pyproject.toml with hatchling build backend, runtime + dev deps, tool config"
  - "uv.lock for reproducible installs"
  - "Placeholder subpackage modules for fetchers, analyzers, deliverers, bot, schemas, utils"
  - ".python-version pinned to 3.12"
  - ".gitignore with no exclusions on data state files"
affects: [02-scheduling, 03-rss-fetcher, 04-dedup, 05-classifier, 06-telegram-deliverer, 07-gmail-deliverer, 08-bot, 09-bot-commands]

# Tech tracking
tech-stack:
  added:
    - "uv 0.10.7 — package manager + lockfile"
    - "hatchling — build backend (installed via pyproject.toml)"
    - "pydantic>=2.5 — runtime schema validation"
    - "PyYAML>=6.0 — YAML loading"
    - "pytest>=8.0 — test runner"
    - "pytest-cov>=5.0 — coverage"
    - "ruff>=0.9 — linter + formatter"
    - "pre-commit>=3.0 — git hooks"
  patterns:
    - "src-layout: code lives in src/pipeline/, not repo root, prevents accidental flat imports"
    - "hatchling build backend declared in pyproject.toml enables uv editable install"
    - "All tool config in pyproject.toml (ruff, pytest) — single config file"
    - "Pydantic v2 for schema validation: model_validate() not parse_obj()"

key-files:
  created:
    - "pyproject.toml — build system, metadata, runtime deps, dev deps, pytest + ruff config"
    - ".python-version — Python 3.12 pin for uv"
    - "uv.lock — reproducible dependency lockfile (24 packages)"
    - "src/pipeline/__init__.py — root package with __version__ = 0.1.0"
    - "src/pipeline/fetchers/__init__.py + rss_fetcher.py — Phase 3 placeholder"
    - "src/pipeline/analyzers/__init__.py + classifier.py — Phase 5 placeholder"
    - "src/pipeline/deliverers/__init__.py + telegram_sender.py — Phase 6 placeholder"
    - "src/pipeline/bot/__init__.py + handler.py — Phase 8 placeholder"
    - "src/pipeline/schemas/__init__.py — Phase 2 schemas placeholder"
    - "src/pipeline/utils/__init__.py — shared utilities placeholder"
  modified:
    - ".gitignore — removed data/history.json and data/sent_news.json exclusions (INFRA-02), added large model files and .ruff_cache/"

key-decisions:
  - "Used hatchling build backend (uv default) — zero config for src-layout, replaces setuptools"
  - "Installed uv via astral.sh installer (not in PATH) — auto-fixed as Rule 3 blocking issue"
  - "src-layout chosen per research: prevents working-directory import trap, future-proof"
  - "Placeholder modules contain only docstrings — no imports, proves import path without false dependencies"
  - "Removed data/history.json and data/sent_news.json from .gitignore — INFRA-02 requires state files committed"

patterns-established:
  - "Pattern 1: src-layout — all package code under src/pipeline/, never in repo root"
  - "Pattern 2: pyproject.toml as single config file — never use pytest.ini, .flake8, setup.cfg"
  - "Pattern 3: uv sync for all installs — never pip install directly"
  - "Pattern 4: Commit uv.lock — reproducible installs across CI and dev environments"

requirements-completed: [INFRA-06]

# Metrics
duration: 2min
completed: 2026-02-27
---

# Phase 1 Plan 01: Project Scaffold — Repository Layout Summary

**hatchling-backed src/pipeline package with uv lockfile, placeholder submodules for all 6 future phases, and INFRA-06-compliant free toolchain**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-27T14:54:52Z
- **Completed:** 2026-02-27T14:57:00Z
- **Tasks:** 3
- **Files modified:** 14

## Accomplishments

- Created pyproject.toml with [build-system] hatchling backend — critical for `from pipeline.X import Y` to work from any working directory
- Ran `uv sync` successfully: installed 24 packages including khabri==0.1.0 in editable mode, generated uv.lock
- Created complete src/pipeline/ tree with 11 Python files — all 6 subpackages import cleanly, verified with uv run

## Task Commits

Each task was committed atomically:

1. **Task 1: Create pyproject.toml with build system, dependencies, and tool config** - `0f5316a` (feat)
2. **Task 2: Create src/pipeline package structure with placeholder modules** - `1221935` (feat)
3. **Task 3: Update .gitignore, run uv sync, and verify package imports** - `19ff2a6` (feat)

## Files Created/Modified

- `pyproject.toml` — Build system (hatchling), project metadata, runtime deps (pydantic, PyYAML), dev deps (pytest, ruff, pre-commit), pytest + ruff config
- `.python-version` — Python 3.12 pin read by uv
- `uv.lock` — 24-package reproducible lockfile
- `.gitignore` — Updated: removed state file exclusions, added model file patterns + .ruff_cache/
- `src/pipeline/__init__.py` — Root package with `__version__ = "0.1.0"`
- `src/pipeline/fetchers/__init__.py` — Subpackage init
- `src/pipeline/fetchers/rss_fetcher.py` — Placeholder for Phase 3
- `src/pipeline/analyzers/__init__.py` — Subpackage init
- `src/pipeline/analyzers/classifier.py` — Placeholder for Phase 5
- `src/pipeline/deliverers/__init__.py` — Subpackage init
- `src/pipeline/deliverers/telegram_sender.py` — Placeholder for Phase 6
- `src/pipeline/bot/__init__.py` — Subpackage init
- `src/pipeline/bot/handler.py` — Placeholder for Phase 8
- `src/pipeline/schemas/__init__.py` — Subpackage init (schemas for Phase 2)
- `src/pipeline/utils/__init__.py` — Subpackage init (loaders for Phase 2)

## Decisions Made

- **hatchling backend:** uv's default, zero-config for src-layout, no need for setuptools
- **src-layout:** Prevents the "working directory import trap" where Python imports from the wrong location; all future phases benefit from this foundation being correct
- **Placeholder modules as docstring-only files:** Proves import paths without creating false API contracts — future phases implement the actual code
- **Removed data file gitignore exclusions:** INFRA-02 requires seen.json and history.json to be committed (they are the state store for the GitHub Actions workflow)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Installed missing uv package manager**
- **Found during:** Task 3 (uv sync)
- **Issue:** `uv` not present in shell PATH — `which uv` returned nothing. Task 3 required `uv sync` to generate uv.lock.
- **Fix:** Installed uv via official installer `curl -LsSf https://astral.sh/uv/install.sh | sh` to `/Users/meharban/.local/bin/uv`
- **Files modified:** None (system-level install, not committed)
- **Verification:** `uv --version` returned `uv 0.10.7`, then `uv sync` completed successfully
- **Committed in:** N/A (system tool install, all subsequent commands used `export PATH="/Users/meharban/.local/bin:$PATH"`)

---

**Total deviations:** 1 auto-fixed (1 blocking — missing tool)
**Impact on plan:** Essential for plan execution. uv is the core toolchain. No scope creep.

## Issues Encountered

- uv not in default PATH on this machine — detected immediately, installed via official installer, no further issues

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- All `from pipeline.X import Y` imports verified working
- uv.lock committed for reproducible installs across CI and dev environments
- src/pipeline/schemas/ and src/pipeline/utils/ are empty placeholders ready for Plan 02 (schema definitions + data files)
- Plan 02 can reference `from pipeline.schemas import ...` and `from pipeline.utils import ...` immediately

## Self-Check: PASSED

All created files confirmed present on disk. All 3 task commits verified in git log.

- pyproject.toml: FOUND
- .python-version: FOUND
- uv.lock: FOUND
- src/pipeline/__init__.py: FOUND
- src/pipeline/fetchers/rss_fetcher.py: FOUND
- src/pipeline/analyzers/classifier.py: FOUND
- src/pipeline/deliverers/telegram_sender.py: FOUND
- src/pipeline/bot/handler.py: FOUND
- .planning/phases/01-project-scaffold/01-01-SUMMARY.md: FOUND
- Commit 0f5316a: FOUND
- Commit 1221935: FOUND
- Commit 19ff2a6: FOUND

---
*Phase: 01-project-scaffold*
*Completed: 2026-02-27*
