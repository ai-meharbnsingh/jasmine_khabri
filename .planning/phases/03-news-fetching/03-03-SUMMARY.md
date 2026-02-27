---
phase: 03-news-fetching
plan: "03"
subsystem: pipeline-entrypoint
tags: [pipeline, rss, gnews, integration, wiring]
dependency_graph:
  requires: [03-01, 03-02]
  provides: [runnable-fetch-pipeline]
  affects: [deliver.yml, main.py, config.yaml]
tech_stack:
  added: []
  patterns: [respx-mocking, env-guard-pattern, health-summary-logging]
key_files:
  created:
    - tests/test_fetch_integration.py
  modified:
    - src/pipeline/main.py
    - data/config.yaml
    - .github/workflows/deliver.yml
decisions:
  - "Health summary logged inline (not separate function) — sufficient for Phase 3, Phase 5 can refactor"
  - "GNews guard uses empty-string check on os.environ.get — falsy check is explicit and consistent with Phase 3 pattern"
metrics:
  duration: "~6 min"
  completed: "2026-02-27"
  tasks_completed: 2
  files_modified: 4
---

# Phase 3 Plan 03: Pipeline Wiring and Integration Test Summary

**One-liner:** RSS + GNews fetchers wired into pipeline.main with env-guarded API key, 8 curated RSS feeds in config.yaml, GNEWS_API_KEY activated in deliver.yml, and 4 integration tests proving end-to-end fetch with mocked HTTP.

## What Was Built

### Task 1: Config + Main + Workflow Wiring

**`data/config.yaml`** — Added `rss_feeds` section with all 8 curated sources (MOHUA, NHAI, AAI, Smart Cities, ET Realty, TOI Real Estate, Hindu BL, Moneycontrol RE), all enabled by default.

**`src/pipeline/main.py`** — Replaced "not yet implemented" Phase 3 placeholder with:
- `fetch_all_rss(config.rss_feeds)` — fetches all enabled RSS feeds
- `os.environ.get("GNEWS_API_KEY", "")` guard — skips GNews with WARNING if key absent
- `load_or_reset_quota` / `fetch_all_gnews` / `save_quota` — GNews fetch with persistent quota
- Full fetch health summary logged (RSS rows + GNews rows)
- Moved all imports to module top (no inline imports)

**`.github/workflows/deliver.yml`** — Uncommented `GNEWS_API_KEY: ${{ secrets.GNEWS_API_KEY }}` in the "Run pipeline" step env block. Other secrets remain commented for later phases.

### Task 2: Integration Tests

**`tests/test_fetch_integration.py`** — 4 tests, zero real network calls (respx mocks):

| Test | What it proves |
|------|---------------|
| `test_rss_and_gnews_combined_fetch` | 2 RSS + 3 GNews = 5 articles; one RSS timeout doesn't block others |
| `test_all_rss_fail_pipeline_continues` | All-fail RSS returns [] without raising |
| `test_config_yaml_loads_rss_feeds` | Real config.yaml has exactly 8 enabled feeds |
| `test_gnews_skipped_without_api_key` | GNews guard works; 0 gnews articles when key absent |

## Verification Results

```
uv run pytest tests/test_fetch_integration.py -v  → 4 passed
uv run pytest -v                                   → 73 passed
uv run ruff check src/ tests/                      → All checks passed
config.yaml loads 8 RSS feeds                      → Confirmed
pipeline.main imports resolve                      → Confirmed
deliver.yml GNEWS_API_KEY uncommented              → Confirmed
```

## Deviations from Plan

None — plan executed exactly as written. Ruff auto-fixed one minor formatting issue in the test file during pre-commit hook (multi-line `httpx.Response()` call collapsed to single line).

## Self-Check: PASSED

- `src/pipeline/main.py` exists and imports OK
- `data/config.yaml` has 8 rss_feeds
- `.github/workflows/deliver.yml` has GNEWS_API_KEY uncommented
- `tests/test_fetch_integration.py` exists, 4 tests pass
- Commits: 917e1f8 (Task 1), efc0e83 (Task 2)
