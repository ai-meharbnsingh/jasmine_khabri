---
phase: 03-news-fetching
plan: "01"
subsystem: fetchers + schemas
tags: [rss, httpx, feedparser, pydantic, tdd, article-schema]
dependency_graph:
  requires:
    - 01-project-scaffold (src-layout, pyproject.toml, pytest convention)
    - 02-scheduling-infrastructure (SeenStore, loader utilities)
  provides:
    - Article Pydantic model (consumed by phases 4-7)
    - GNewsQuota model (consumed by phase 4 GNews fetcher)
    - RssFeedConfig + AppConfig.rss_feeds (consumed by config loader phase)
    - fetch_rss_feed / fetch_all_rss (consumed by pipeline orchestration phase 6)
  affects:
    - src/pipeline/schemas/config_schema.py (AppConfig extended with rss_feeds)
    - src/pipeline/schemas/__init__.py (new re-exports)
    - src/pipeline/fetchers/__init__.py (now exports fetch_rss_feed, fetch_all_rss)
tech_stack:
  added:
    - httpx==0.28.1 (async-capable HTTP client with timeout + redirect control)
    - feedparser==6.0.12 (RSS/Atom parser, content-mode only — never URL mode)
    - respx==0.22.0 (dev: httpx mock transport for zero-network tests)
  patterns:
    - fetch-then-parse: httpx fetches bytes, feedparser.parse(content) parses
    - calendar.timegm() for UTC struct_time conversion (not time.mktime)
    - per-feed error isolation in fetch_all_rss — one fail does not abort others
    - summary always "" in Phase 3 — Phase 5 AI populates
key_files:
  created:
    - src/pipeline/schemas/article_schema.py
    - src/pipeline/schemas/gnews_quota_schema.py
    - tests/test_article_schema.py
    - tests/test_rss_fetcher.py
  modified:
    - src/pipeline/schemas/config_schema.py (RssFeedConfig + AppConfig.rss_feeds)
    - src/pipeline/schemas/__init__.py (Article, GNewsQuota, RssFeedConfig exports)
    - src/pipeline/fetchers/rss_fetcher.py (full implementation)
    - src/pipeline/fetchers/__init__.py (fetch_rss_feed, fetch_all_rss exports)
    - pyproject.toml (httpx, feedparser runtime; respx dev)
    - uv.lock (regenerated)
decisions:
  - "Article standalone (not extending SeenEntry): transient fetch output vs durable dedup state — different lifecycles"
  - "calendar.timegm() not time.mktime(): mktime uses local TZ causing wrong UTC conversion"
  - "Bozo feeds logged but not discarded: parseable entries still yielded, warn-not-abort"
  - "summary='' enforced in Phase 3: Phase 5 AI will populate — never copy RSS description"
  - "fetch-then-parse pattern: feedparser URL mode bypasses httpx timeout+redirect, never used"
  - "GNewsQuota UTC date reset: simpler than IST midnight boundary, consistent with pipeline UTC convention"
metrics:
  duration_seconds: 198
  duration_human: "3 min 18 sec"
  tasks_completed: 2
  tests_added: 22
  tests_total: 53
  files_created: 4
  files_modified: 6
  completed_date: "2026-02-27"
---

# Phase 3 Plan 01: RSS Fetcher + Article Schema Summary

**One-liner:** Article/GNewsQuota/RssFeedConfig Pydantic models + RSS fetcher using httpx fetch-then-parse with per-feed error isolation and zero-network respx TDD tests.

## What Was Built

**Schemas (3 new models):**
- `Article` — transient fetch output: title, url, source, published_at, fetched_at required; summary="" (Phase 5 populates)
- `GNewsQuota` — daily API quota tracker: date (UTC), calls_used=0, daily_limit=25
- `RssFeedConfig` — feed config: name, url, enabled=True; added as `rss_feeds: list[RssFeedConfig]` to AppConfig

**RSS Fetcher (`src/pipeline/fetchers/rss_fetcher.py`):**
- `_struct_time_to_iso()`: feedparser struct_time → ISO 8601 UTC via `calendar.timegm()` (not `time.mktime`)
- `fetch_rss_feed(url, source_name, timeout=10.0)`: httpx GET → feedparser.parse(content) → Article list. Returns `(articles, None)` or `([], error_string)` on any failure type (timeout, HTTP error, network error, unexpected)
- `fetch_all_rss(feeds)`: iterates enabled feeds, isolates failures, logs ASCII health summary table, returns `(all_articles, health_results)`

**Dependencies installed:** httpx==0.28.1, feedparser==6.0.12, sgmllib3k==1.0.0 (feedparser dep), respx==0.22.0 (dev)

## Test Results

| Test File | Tests | Result |
|-----------|-------|--------|
| tests/test_article_schema.py | 9 | PASS |
| tests/test_rss_fetcher.py | 13 | PASS |
| Full suite | 53 | PASS |

TDD lifecycle: RED (import error confirmed) → GREEN (implementation) → lint fix (ruff: unused import, line length) → all 53 pass.

## Commits

| Task | Description | Commit |
|------|-------------|--------|
| Task 1 | Article, GNewsQuota, RssFeedConfig schemas + install deps | 7f74f64 |
| Task 2 | RSS fetcher implementation (fetch-then-parse, error isolation) | a3d2c82 |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Lint] Fixed ruff violations in test file**
- **Found during:** Task 2 GREEN phase (pre-commit hook)
- **Issue:** Unused `pytest` import (F401), two lines exceeding 100-char limit (E501) in `tests/test_rss_fetcher.py`
- **Fix:** Removed unused import, reformatted long lines to multi-line style, ran `ruff-format` to satisfy pre-commit hook
- **Files modified:** tests/test_rss_fetcher.py
- **Commit:** a3d2c82 (included in same commit after restage)

No architectural deviations. Plan executed as written.

## Self-Check: PASSED

All files confirmed on disk. All commits found in git log.

| Item | Status |
|------|--------|
| src/pipeline/schemas/article_schema.py | FOUND |
| src/pipeline/schemas/gnews_quota_schema.py | FOUND |
| src/pipeline/fetchers/rss_fetcher.py | FOUND |
| tests/test_article_schema.py | FOUND |
| tests/test_rss_fetcher.py | FOUND |
| Commit 7f74f64 (schemas) | FOUND |
| Commit a3d2c82 (fetcher) | FOUND |
