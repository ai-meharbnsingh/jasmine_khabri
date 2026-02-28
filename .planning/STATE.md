---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: unknown
last_updated: "2026-02-28T08:43:09Z"
progress:
  total_phases: 11
  completed_phases: 3
  total_plans: 9
  completed_plans: 9
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-26)

**Core value:** Deliver the right infrastructure and real estate news at the right time — so the user never misses critical developments and saves 2+ hours of daily manual research.
**Current focus:** Phase 4 — Deduplication

## Current Position

Phase: 4 of 11 (Filtering and Deduplication) — In Progress
Plan: 1 of 3 in current phase (04-01 complete)
Status: Phase 4 Plan 1 Complete — Relevance filter with keyword scoring and exclusion gate, 86 tests passing
Last activity: 2026-02-28 — Plan 04-01 complete (relevance filter, hashing utilities, Article schema extended)

Progress: [████░░░░░░] 32%

## Performance Metrics

**Velocity:**
- Total plans completed: 4
- Average duration: 1.75 min
- Total execution time: 0.12 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-project-scaffold | 3 | 5 min | 1.7 min |
| 02-scheduling-infrastructure | 2 | 4 min | 2.0 min |
| 03-news-fetching | 3 | 14 min | 4.7 min |
| 04-filtering-and-deduplication | 1 | 13 min | 13.0 min |

**Recent Trend:**
- Last 5 plans: 03-01 (3 min), 03-02 (5 min), 03-03 (6 min), 04-01 (13 min)
- Trend: increasing (more complex TDD filtering logic)

*Updated after each plan completion*
| Phase 03-news-fetching P03 | 6 | 2 tasks | 4 files |
| Phase 04-filtering P01 | 13 | 2 tasks | 5 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Railway over Vercel for bot: persistent process, no cold starts, polling mode simpler than webhooks
- GitHub repo as data store: free, version-controlled, no DB needed — seen.json, config.json, keywords.json
- Claude primary, Gemini fallback: better analysis quality, fallback for reliability
- google-genai (not google-generativeai): deprecated EOL Nov 2025
- hatchling build backend: uv default, zero-config for src-layout, enables editable install via uv sync
- src-layout chosen: prevents working-directory import trap; from pipeline.X import Y works from any cwd
- data/history.json not gitignored: INFRA-02 requires state files committed to repo
- [Phase 01-project-scaffold]: SeenStore used for both seen.json and history.json — same schema, simpler than two separate models
- [Phase 01-project-scaffold]: Full keyword library (67 active) included from blueprint, not curated subset — per user intent
- [Phase 01-project-scaffold]: Schedule times stored as IST strings in YAML; UTC conversion deferred to Phase 2
- [Phase 01-project-scaffold]: Pre-commit ruff hooks pinned to v0.9.0 matching pyproject.toml dev dep
- [Phase 01-project-scaffold]: Class-based pytest pattern: one class per concern in test files
- [Phase 02-01]: datetime.UTC alias used (not timezone.utc) — ruff UP017 enforces modern Python 3.11+ stdlib
- [Phase 02-01]: cancel-in-progress: false on deliver concurrency — prevents seen.json corruption from mid-run cancellation
- [Phase 02-01]: EndBug add uses explicit JSON array paths (not '.') — prevents accidental secret commit
- [Phase 02-01]: keepalive time_elapsed: 45 days — fires only approaching 60-day window, not every run
- [Phase 02-01]: Secrets commented out in deliver.yml (not absent) — self-documents future phase requirements
- [Phase 02-02]: Malformed seen_at entries kept not dropped — fail-safe over fail-silent, log warning and preserve
- [Phase 02-02]: Naive timestamps assumed UTC — consistent with ISO 8601 pipeline convention
- [Phase 02-02]: purge_old_entries returns new SeenStore (not mutated) — functional style, safe re-assignment
- [Phase 02-02]: save_seen added to loader.py (not separate file) — all disk I/O for data files in one module
- [Phase 03-news-fetching]: Article standalone (not extending SeenEntry): different lifecycles — transient fetch output vs durable dedup state
- [Phase 03-news-fetching]: calendar.timegm() not time.mktime(): mktime uses local TZ causing wrong UTC conversion for feedparser struct_time
- [Phase 03-news-fetching]: fetch-then-parse pattern: feedparser URL mode bypasses httpx timeout+redirect, never used
- [Phase 03-news-fetching]: Pre-built static OR queries per category (not dynamic from keyword list) — 3 fixed queries stay within 25-call/day budget
- [Phase 03-news-fetching]: GNewsQuota.model_copy(update=...) for all mutations — immutable functional style, quota always returned even on failure paths
- [Phase 03-news-fetching]: gnews_quota.json seeded with 1970-01-01 — auto-resets on first run, no manual init; added to deliver.yml EndBug commit-back
- [Phase 03-03]: Health summary logged inline in main.py (not separate function) — sufficient for Phase 3; Phase 5 can refactor
- [Phase 03-03]: GNews guard uses empty-string falsy check on os.environ.get — explicit and consistent with Phase 3 env pattern
- [Phase 04-01]: Exclusion check runs before keyword scoring — short-circuits at O(n_exclusions) instead of O(n_keywords)
- [Phase 04-01]: normalize_title uses NFD decomposition so 'Phase-4' and 'Phase 4' produce identical tokens
- [Phase 04-01]: score_article returns (bool, int) tuple — caller decides rejection vs logging; no side effects
- [Phase 04-01]: hashing.py is canonical normalization source — 04-02 dedup MUST import from here, not reinvent
- [Phase 04-01]: All four Phase 4 filter fields on Article use Python defaults — zero code changes in Phase 3 constructors

### Pending Todos

None yet.

### Blockers/Concerns

- Phase 5 (AI classification): Prompt engineering for Indian real estate domain may need 2-3 iteration cycles — calibrate threshold against real article sets before locking system prompt
- Phase 3 (GNews quota): Design Boolean-grouped queries from day one — never one-query-per-keyword or 100 req/day limit will be exhausted
- Phase 2 (scheduling): Validate IST/UTC cron expressions against first 3 live runs before trusting automation

## Session Continuity

Last session: 2026-02-28
Stopped at: Completed 04-filtering-and-deduplication/04-01-PLAN.md (relevance filter, hashing utilities, 86 tests)
Resume file: None
Next: Phase 4 Plan 02 — URL deduplication using seen.json
