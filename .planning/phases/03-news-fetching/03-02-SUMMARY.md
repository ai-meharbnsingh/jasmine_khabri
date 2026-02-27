---
phase: 03-news-fetching
plan: 02
subsystem: fetchers
tags: [gnews, api-client, quota-tracking, tdd, httpx, respx]
dependency_graph:
  requires: [03-01]
  provides: [GNews API client, quota persistence, boolean query builder]
  affects: [pipeline.fetchers, data/gnews_quota.json, deliver.yml]
tech_stack:
  added: []
  patterns: [TDD RED-GREEN, respx mocking, Pydantic model_copy for immutable updates]
key_files:
  created:
    - src/pipeline/fetchers/gnews_fetcher.py
    - data/gnews_quota.json
    - tests/test_gnews_fetcher.py
  modified:
    - src/pipeline/fetchers/__init__.py
    - .github/workflows/deliver.yml
decisions:
  - Pre-built broad OR queries per category (not dynamic from keyword list) — 3 fixed query strings map to infrastructure/regulatory/market categories; avoids budget exhaustion
  - model_copy(update=...) for quota mutation — keeps GNewsQuota immutable per function call, no in-place mutation
  - fetch_gnews_query returns tuple (articles, quota, error) — caller always gets updated quota even on failure paths (429 exhausted quota is returned)
  - data/gnews_quota.json starts at 1970-01-01 — auto-resets on first real run, no manual init needed
metrics:
  duration: 5 min
  completed: "2026-02-27"
  tasks_completed: 2
  files_created: 3
  files_modified: 2
---

# Phase 3 Plan 02: GNews Fetcher Summary

**One-liner:** GNews.io API client with 3-query Boolean grouping, UTC daily quota reset, and per-error-type handling (401/429/network) using httpx + respx TDD.

## What Was Built

GNews API fetcher that:
- Constructs 3 broad Boolean OR queries (infrastructure / regulatory / real-estate market) from active keyword categories — never one query per keyword
- Tracks daily quota in `data/gnews_quota.json` (resets on UTC date change, persists across pipeline runs)
- Handles all error classes distinctly: 401 auth failure (ERROR log, quota unchanged), 429 rate limit (quota marked exhausted), network errors (WARNING, skip)
- Stops early in `fetch_all_gnews` when quota exhausted — remaining queries get `SKIP` in health results
- Normalises all GNews articles to the canonical `Article` schema with `summary=""` always

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Write failing tests — RED phase | cba7c81 | tests/test_gnews_fetcher.py |
| 2 | Implement GNews fetcher — GREEN phase | c94119d | gnews_fetcher.py, __init__.py, gnews_quota.json, deliver.yml |

## Verification Results

```
uv run pytest tests/test_gnews_fetcher.py -v  →  16 passed
uv run pytest -v                               →  69 passed (0 regressions)
uv run ruff check src/ tests/                 →  All checks passed
from pipeline.fetchers.gnews_fetcher import …  →  GNews imports OK
json.load(open('data/gnews_quota.json'))       →  Quota JSON valid
```

## Deviations from Plan

None — plan executed exactly as written.

## Decisions Made

- Pre-built static OR query strings per category rather than dynamic construction from full keyword lists — 3 fixed queries stay well within the 25-call/day budget ceiling
- `GNewsQuota.model_copy(update=...)` used throughout to avoid mutation — functional style consistent with Phase 2 `purge_old_entries` decision
- `data/gnews_quota.json` seeded with `1970-01-01` — guaranteed auto-reset on first real run, no manual intervention needed
- `gnews_quota.json` added to EndBug `add` path in `deliver.yml` — quota state persists across GitHub Actions runs via repo commit-back

## Self-Check: PASSED

- src/pipeline/fetchers/gnews_fetcher.py: FOUND
- data/gnews_quota.json: FOUND
- tests/test_gnews_fetcher.py: FOUND
- commit cba7c81 (RED tests): FOUND
- commit c94119d (GREEN implementation): FOUND
