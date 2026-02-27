---
phase: 01-project-scaffold
plan: 02
subsystem: infra
tags: [pydantic, yaml, json, schemas, data-validation, loaders]

# Dependency graph
requires:
  - phase: 01-project-scaffold/01-01
    provides: src-layout package structure, uv sync environment, pytest infra

provides:
  - Pydantic v2 models for config.yaml (AppConfig, ScheduleConfig, TelegramConfig, EmailConfig, DeliveryConfig)
  - Pydantic v2 models for keywords.yaml (KeywordsConfig, KeywordCategory with active_keywords())
  - Pydantic v2 models for seen.json/history.json (SeenStore, SeenEntry)
  - Data loaders: load_config(), load_keywords(), load_seen() as single entry point for all file I/O
  - Default data files: config.yaml (07:00/16:00 IST, max 15), keywords.yaml (67 active: infra+regulatory, celebrity+transaction inactive), seen.json and history.json (empty stores)
  - Re-exports of all models from pipeline.schemas.__init__

affects:
  - Phase 2 (scheduler): imports load_config() for IST schedule times
  - Phase 3 (fetcher): imports load_keywords() for active keyword list and load_seen() for dedup
  - Phase 5 (AI classifier): imports KeywordsConfig for context about active categories
  - Phase 6 (delivery): imports load_config() for max_stories, telegram/email config
  - All phases: must import from pipeline.schemas or pipeline.utils.loader — never raw dict access

# Tech tracking
tech-stack:
  added: [pydantic>=2.5 (already in pyproject.toml), PyYAML>=6.0 (already in pyproject.toml)]
  patterns:
    - Pydantic v2 model_validate() (not deprecated parse_obj())
    - YAML time strings MUST be quoted ("07:00" not 07:00) to prevent sexagesimal integer parsing
    - load_seen() handles missing/empty files gracefully — returns empty SeenStore()
    - load_config() and load_keywords() require files to exist (committed to repo, not generated)

key-files:
  created:
    - src/pipeline/schemas/config_schema.py
    - src/pipeline/schemas/keywords_schema.py
    - src/pipeline/schemas/seen_schema.py
    - src/pipeline/utils/loader.py
    - data/config.yaml
    - data/keywords.yaml
    - data/seen.json
    - data/history.json
  modified:
    - src/pipeline/schemas/__init__.py

key-decisions:
  - "SeenStore used for both seen.json and history.json — same schema, different file paths, simpler than two models"
  - "load_seen() is missing-file-tolerant but load_config/load_keywords are not — config files MUST exist in repo"
  - "Schedule times stored as IST strings in YAML — UTC conversion deferred to Phase 2 as computed property"
  - "Full keyword library from blueprint included (67 active) not just curated 30-40 — user decision from blueprint"
  - "bot_token defaults to empty string — secrets never committed, set via env var at runtime"

patterns-established:
  - "Schema-first: every data file has a Pydantic model before any reader code"
  - "Single entry point: all data file access MUST go through pipeline.utils.loader functions"
  - "No raw dict access: always validate via model_validate() before using data"
  - "Graceful empty store: missing/empty JSON returns valid empty model, not exception"

requirements-completed: [INFRA-01, INFRA-02]

# Metrics
duration: 1min
completed: 2026-02-27
---

# Phase 1 Plan 2: Schema Models and Data Loaders Summary

**Pydantic v2 schema layer with 3 model files, 3 loader functions, and 4 default data files (67 active keywords across infrastructure + regulatory categories)**

## Performance

- **Duration:** 1 min
- **Started:** 2026-02-27T14:59:49Z
- **Completed:** 2026-02-27T15:01:18Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments
- Pydantic v2 models for all three data file types: AppConfig (config.yaml), KeywordsConfig (keywords.yaml), SeenStore (seen.json/history.json)
- Three loader functions in pipeline.utils.loader as the single entry point for all file I/O — no raw dict access anywhere
- Default data files committed to repo: config.yaml with locked defaults (07:00/16:00 IST, max 15 stories), keywords.yaml with full blueprint keyword library (67 active, 26 inactive), empty seen.json and history.json
- All models re-exported from pipeline.schemas for clean imports across all future phases

## Task Commits

Each task was committed atomically:

1. **Task 1: Create Pydantic v2 schema models for all data files** - `61e09a1` (feat)
2. **Task 2: Create loader utilities and data files with keyword library** - `e099dc6` (feat)

**Plan metadata:** committed with docs commit below

## Files Created/Modified
- `src/pipeline/schemas/config_schema.py` - AppConfig, ScheduleConfig, TelegramConfig, EmailConfig, DeliveryConfig
- `src/pipeline/schemas/keywords_schema.py` - KeywordCategory, KeywordsConfig with active_keywords() and active_categories() methods
- `src/pipeline/schemas/seen_schema.py` - SeenEntry, SeenStore (used for both seen.json and history.json)
- `src/pipeline/schemas/__init__.py` - Re-exports all 9 public model names
- `src/pipeline/utils/loader.py` - load_config(), load_keywords(), load_seen()
- `data/config.yaml` - Default config: 07:00/16:00 IST schedule, max 15 stories, both channels active
- `data/keywords.yaml` - Full blueprint keyword library: 41 infrastructure + 26 regulatory (active), 13 celebrity + 13 transaction (inactive)
- `data/seen.json` - Empty entry store for deduplication
- `data/history.json` - Empty entry store for delivery history

## Decisions Made
- SeenStore model shared for both seen.json and history.json — same schema, simpler than two separate models
- load_seen() is tolerant of missing/empty files (returns SeenStore()), load_config/keywords require files to exist
- Full blueprint keyword library (67 active) included rather than curated subset — per user decision "Ship the FULL keyword library"
- Schedule times stored as IST strings in YAML; UTC conversion deferred to Phase 2 as computed property on ScheduleConfig

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required at this stage.

## Next Phase Readiness

- All schema models importable: `from pipeline.schemas import AppConfig, KeywordsConfig, SeenStore`
- All loaders work: `load_config()`, `load_keywords()`, `load_seen("data/seen.json")`, `load_seen("data/history.json")`
- Phase 2 (scheduling) can immediately import load_config() and read IST schedule times
- Phase 3 (fetcher) can immediately import load_keywords().active_keywords() for query construction
- Concern: 67 active keywords is more than the "30-40" mentioned in CONTEXT.md — Phase 3 Boolean grouping design must be built to handle this count without exhausting GNews quota

---
*Phase: 01-project-scaffold*
*Completed: 2026-02-27*

## Self-Check: PASSED

All 10 expected files exist on disk. Both task commits verified in git history (61e09a1, e099dc6).
