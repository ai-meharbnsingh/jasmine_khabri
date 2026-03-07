---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: in-progress
stopped_at: Completed 07-01-PLAN.md
last_updated: "2026-03-07T10:59:16Z"
last_activity: 2026-03-07 -- Plan 07-01 complete (Gmail SMTP email sender + pipeline integration, 43 new tests, 265 total)
progress:
  total_phases: 11
  completed_phases: 6
  total_plans: 17
  completed_plans: 16
  percent: 94
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-26)

**Core value:** Deliver the right infrastructure and real estate news at the right time — so the user never misses critical developments and saves 2+ hours of daily manual research.
**Current focus:** Phase 7 in progress — Email Delivery and Edge Cases (plan 1 of 2 complete)

## Current Position

Phase: 7 of 11 (Email Delivery and Edge Cases)
Plan: 1 of 2 in current phase (07-01 complete)
Status: Plan 07-01 complete -- Gmail SMTP email sender, 265 tests passing
Last activity: 2026-03-07 -- Plan 07-01 complete (Gmail SMTP email sender + pipeline integration, 43 new tests, 265 total)

Progress: [█████████░] 94%

## Performance Metrics

**Velocity:**
- Total plans completed: 16
- Average duration: 5.0 min
- Total execution time: 1.35 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-project-scaffold | 3 | 5 min | 1.7 min |
| 02-scheduling-infrastructure | 2 | 4 min | 2.0 min |
| 03-news-fetching | 3 | 14 min | 4.7 min |
| 04-filtering-and-deduplication | 1 | 13 min | 13.0 min |
| 05-ai-analysis-pipeline | 2 | 9 min | 4.5 min |
| 06-telegram-delivery | 2 | 7 min | 3.5 min |
| 07-email-delivery | 1 | 4 min | 4.0 min |

**Recent Trend:**
- Last 5 plans: 05-02 (5 min), 06-01 (4 min), 06-02 (3 min), 07-01 (4 min)
- Trend: stabilizing/improving

*Updated after each plan completion*
| Phase 03-news-fetching P03 | 6 | 2 tasks | 4 files |
| Phase 04-filtering P01 | 13 | 2 tasks | 5 files |
| Phase 04-filtering P02 | 8 | 2 tasks | 2 files |
| Phase 04-filtering P03 | 5 | 2 tasks | 3 files |
| Phase 05-ai-analysis P01 | 4 | 2 tasks | 11 files |
| Phase 05-ai-analysis P02 | 5 | 2 tasks | 4 files |
| Phase 06-telegram-delivery P01 | 4 | 2 tasks | 4 files |
| Phase 06-telegram-delivery P02 | 3 | 2 tasks | 5 files |
| Phase 07-email-delivery P01 | 4 | 2 tasks | 4 files |

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
- [Phase 04-02]: Government sources (MOHUA, NHAI, AAI, Smart Cities) with no city match treated as Tier 1 national-scope — per 04-RESEARCH.md Pitfall 4
- [Phase 04-02]: Tier 2 threshold 60 and Tier 3 threshold 85 are Phase 4 proxies — Phase 5 AI classification will refine with semantic understanding
- [Phase 04-02]: frozenset for O(1) city taxonomy lookup — TIER_1_CITIES/TIER_2_CITIES/GOV_SOURCES pattern for all categorical sets in pipeline
- [Phase 04-03]: Two-stage dedup: exact hash match first (O(n) short-circuit), then SequenceMatcher scan — avoids normalization cost on exact matches
- [Phase 04-03]: dedup_ref stores human-readable original title (not hash) — delivery phases can surface "UPDATE to: [title]" without extra lookup
- [Phase 04-03]: seen variable reassigned by filter_duplicates in main.py — second save_seen after dedup captures purge + new articles in one write
- [Phase 04-03]: SequenceMatcher ratio on normalized titles — punctuation/case differences excluded from similarity score
- [Phase 05-01]: AICost follows GNewsQuota pattern: simple Pydantic model with monthly reset in loader
- [Phase 05-01]: budget_amount field name avoids collision with Pydantic BaseModel internals
- [Phase 05-01]: Functional style record_cost via model_copy matches GNewsQuota immutability pattern
- [Phase 05-01]: Plain Pydantic models for AI response schemas (no custom validators) for Anthropic .parse() compatibility
- [Phase 05-02]: Claude Haiku 4.5 as primary model ($1/$5 MTok) -- 3x cheaper than Sonnet, sufficient for classification
- [Phase 05-02]: Domain-primed system prompt with Indian infra/real estate classification criteria from CONTEXT.md
- [Phase 05-02]: Budget exceeded ($4.75) degrades to keyword-only: relevance_score >=80 HIGH, >=60 MEDIUM, else LOW
- [Phase 05-02]: Both-providers-fail assigns MEDIUM priority with empty summary/entities -- pipeline never crashes
- [Phase 05-02]: GOOGLE_API_KEY env var (not GEMINI_API_KEY) matches deliver.yml naming convention
- [Phase 06-01]: HIGH cap at 8 is hard limit (no backfill beyond cap) -- prevents HIGH flooding
- [Phase 06-01]: Backfill order: MEDIUM surplus then LOW surplus (never exceeds HIGH cap)
- [Phase 06-01]: Pipe separator (|) for source-location and entity metadata instead of asterisk
- [Phase 06-01]: Section headers use color circle emojis (red/yellow/green) for visual priority distinction
- [Phase 06-01]: Empty priority articles silently excluded (no crash, no log noise)
- [Phase 06-02]: Env var TELEGRAM_BOT_TOKEN takes precedence over config.telegram.bot_token -- secrets stay in GitHub, not YAML
- [Phase 06-02]: TELEGRAM_CHAT_IDS comma-separated in single env var -- simpler than multiple secrets
- [Phase 06-02]: Single retry on 429/network errors with 2s delay -- Telegram API is fast, exponential backoff unnecessary
- [Phase 06-02]: link_preview_options.is_disabled=True -- prevents cluttered previews in delivery messages
- [Phase 06-02]: 0.5s inter-send delay -- respects Telegram 30 msg/sec rate limit without being slow
- [Phase 07-01]: Reused _IST, _escape_html, get_delivery_period from telegram_sender.py -- DRY, same timezone and escape logic
- [Phase 07-01]: Table-based HTML with inline CSS -- maximum email client compatibility (Outlook, Gmail, Apple Mail)
- [Phase 07-01]: MIMEMultipart('alternative') with plain-text fallback -- graceful degradation for text-only clients
- [Phase 07-01]: Per-recipient send with single retry and 2s delay -- same pattern as Telegram sender
- [Phase 07-01]: GMAIL_RECIPIENTS env var overrides config.email.recipients -- secrets in GitHub, not YAML
- [Phase 07-01]: ssl.create_default_context() for STARTTLS -- secure default without manual cert management

### Pending Todos

None yet.

### Blockers/Concerns

- Phase 5 (AI classification): Prompt engineering for Indian real estate domain may need 2-3 iteration cycles — calibrate threshold against real article sets before locking system prompt
- Phase 3 (GNews quota): Design Boolean-grouped queries from day one — never one-query-per-keyword or 100 req/day limit will be exhausted
- Phase 2 (scheduling): Validate IST/UTC cron expressions against first 3 live runs before trusting automation

## Session Continuity

Last session: 2026-03-07T10:59:16Z
Stopped at: Completed 07-01-PLAN.md
Resume file: .planning/phases/07-email-delivery-and-edge-cases/07-01-SUMMARY.md
Next: Plan 07-02 -- Edge Cases and Error Handling
