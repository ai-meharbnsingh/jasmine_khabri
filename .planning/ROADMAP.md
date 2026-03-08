# Roadmap: Khabri

## Overview

Khabri is built in eleven phases that follow a strict dependency chain: project scaffolding first, then
GitHub Actions scheduling infrastructure, then feed ingestion, then AI analysis, then delivery, then the
Railway-hosted Telegram bot, then advanced bot features, and finally breaking news and production hardening.
Each phase produces independently testable, deployable functionality. No phase begins until the prior phase
delivers its success criteria. The result is an automated news aggregation system that surfaces the right
Indian infrastructure and real estate news twice daily, eliminating 2+ hours of manual research for two
content writers.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Project Scaffold** - Repo structure, dependency management, data schemas, and dev environment (completed 2026-02-27)
- [x] **Phase 2: Scheduling Infrastructure** - GitHub Actions cron wiring, keepalive workflow, and JSON state management (completed 2026-02-27)
- [x] **Phase 3: News Fetching** - RSS feed ingestion and GNews.io API integration with error handling (completed 2026-02-27)
- [x] **Phase 4: Filtering and Deduplication** - Keyword filtering, geo-tier scoring, and title-hash dedup history (completed 2026-02-28)
- [ ] **Phase 5: AI Analysis Pipeline** - Claude classification, entity extraction, Gemini fallback, and cost controls
- [x] **Phase 6: Telegram Delivery** - Scheduled Telegram delivery at 7 AM and 4 PM IST to both users
- [ ] **Phase 7: Email Delivery and Edge Cases** - HTML email digest, overflow notices, slow-day handling
- [ ] **Phase 8: Railway Bot Foundation** - Persistent bot process on Railway with basic commands and auth guard
- [ ] **Phase 9: Keyword and Menu Management** - Keyword CRUD commands and interactive inline keyboard menu
- [x] **Phase 10: Advanced Bot Controls** - Natural language commands, schedule modification, event-based scheduling, and stats (completed 2026-03-08)
- [ ] **Phase 11: Breaking News and Production Hardening** - Breaking news watcher, system health monitoring, and free-tier compliance

## Phase Details

### Phase 1: Project Scaffold
**Goal**: A working local development environment with reproducible dependencies, validated data schemas, and an importable Python package structure
**Depends on**: Nothing (first phase)
**Requirements**: INFRA-01, INFRA-02, INFRA-06
**Success Criteria** (what must be TRUE):
  1. Running `uv sync` in a fresh checkout installs all dependencies without errors
  2. Python package imports (`from pipeline.fetchers import rss_fetcher`) resolve without errors
  3. The JSON schemas for `seen.json`, `config.json`, and `keywords.json` are defined and validated by a schema fixture
  4. A `pytest` run with zero test implementations exits with 0 failures and no import errors
  5. The repo contains a `.gitignore` excluding secrets, `.env`, and large model files
**Plans**: 3 plans

Plans:
- [x] 01-01-PLAN.md — Repo layout, pyproject.toml with hatchling, src/pipeline package structure, uv lockfile, .gitignore
- [ ] 01-02-PLAN.md — Pydantic v2 schema models, loader utilities, data files (config.yaml, keywords.yaml, seen.json, history.json)
- [ ] 01-03-PLAN.md — Schema validation tests, pre-commit hooks, full scaffold verification

### Phase 2: Scheduling Infrastructure
**Goal**: GitHub Actions workflows are deployed, cron schedules are wired to correct IST times, a keepalive workflow is active, and the pipeline can be triggered manually and commits state back to the repo
**Depends on**: Phase 1
**Requirements**: INFRA-01, INFRA-03, INFRA-05
**Success Criteria** (what must be TRUE):
  1. The `deliver.yml` workflow triggers at 01:30 UTC and 10:30 UTC (7 AM and 4 PM IST) with correct cron expressions visible in the YAML and documented in comments
  2. The keepalive workflow runs and prevents the 60-day GitHub inactivity disable
  3. A `workflow_dispatch` manual trigger runs the pipeline without errors and produces a log showing pipeline entry and exit
  4. After each pipeline run, updated JSON state files are committed back to the repo via `EndBug/add-and-commit`
  5. Article history older than 7 days is purged automatically on each run
**Plans**: 2 plans

Plans:
- [x] 02-01-PLAN.md — Pipeline entrypoint (main.py), deliver.yml (cron + dispatch + commit-back), keepalive.yml
- [x] 02-02-PLAN.md — 7-day history purge utility (TDD), save_seen helper, wire purge into main.py

### Phase 3: News Fetching
**Goal**: The pipeline reliably fetches articles from all curated RSS feeds and GNews.io API, normalizes them to a unified schema, and logs per-source health without failing the entire run on individual source errors
**Depends on**: Phase 2
**Requirements**: FETCH-01, FETCH-02, FETCH-06
**Success Criteria** (what must be TRUE):
  1. A manual pipeline run fetches articles from all configured RSS feeds (MOHUA, NHAI, AAI, Smart Cities, ET Realty, TOI Real Estate, Hindu BL, Moneycontrol RE) and logs a count per feed
  2. A manual pipeline run fetches articles from GNews.io using Boolean-grouped keyword queries and stays within 25 API calls per combined daily run
  3. When a single RSS feed returns a timeout, malformed XML, or HTTP error, the pipeline continues fetching from all other feeds and logs the failure without raising an uncaught exception
  4. All fetched articles are normalized to the unified schema (title, url, source, published_at, summary) and serializable to JSON
  5. A daily GNews quota tracker is updated in state JSON after each run
**Plans**: 3 plans

Plans:
- [ ] 03-01-PLAN.md — Article/GNewsQuota/RssFeedConfig schemas, RSS fetcher with httpx+feedparser (TDD), error isolation and bozo handling
- [ ] 03-02-PLAN.md — GNews.io API client with Boolean-grouped queries, daily quota tracker, auth/rate-limit handling (TDD)
- [ ] 03-03-PLAN.md — Pipeline integration: wire fetchers into main.py, RSS feed config in config.yaml, integration tests

### Phase 4: Filtering and Deduplication
**Goal**: Fetched articles are filtered by keyword relevance and exclusion rules, scored by geographic tier, and deduplicated against a 7-day rolling history using title-hash fast-path — so only novel, relevant articles reach the AI pipeline
**Depends on**: Phase 3
**Requirements**: FETCH-03, FETCH-04, FETCH-05, AI-03, AI-04
**Success Criteria** (what must be TRUE):
  1. An article mentioning "Delhi Metro Phase 4" scores above the 40-point relevance threshold and passes filtering
  2. An article containing exclusion keywords ("obituary", "gossip") is filtered out before reaching AI classification
  3. A Tier 1 city story (Delhi NCR, Mumbai, Bangalore, Hyderabad) always passes geographic filtering; a Tier 3 story is only included if its impact score exceeds 85
  4. An article whose normalized title hash exists in `seen.json` within the last 7 days is marked as a duplicate and not passed to the AI pipeline
  5. An article with 50-80% title similarity to an existing seen article is labeled "UPDATE" with a reference to the original
**Plans**: 3 plans

Plans:
- [ ] 04-01-PLAN.md — Article schema extension, shared hashing utilities, keyword relevance scorer and exclusion filter (TDD)
- [ ] 04-02-PLAN.md — Geographic tier classifier with Tier 1/2/3 priority rules and national-scope government feed handling (TDD)
- [ ] 04-03-PLAN.md — Title-hash deduplicator with UPDATE detection, pipeline wiring of all filters into main.py (TDD)

### Phase 5: AI Analysis Pipeline
**Goal**: Filtered articles are classified HIGH/MEDIUM/LOW by Claude Haiku 4.5 in a single batched API call, enriched with 2-line writer-focused impact summaries and structured entity extraction, with automatic Gemini fallback on Claude failure — all within the $5/month AI cost budget
**Depends on**: Phase 4
**Requirements**: AI-01, AI-02, AI-05, AI-06, AI-07
**Success Criteria** (what must be TRUE):
  1. A batch of 15 articles is classified HIGH/MEDIUM/LOW in a single Claude API call (not 15 separate calls) and results are logged showing priority labels
  2. Each classified article has a 2-line summary explaining its real estate or infrastructure impact, viewable in the pipeline log
  3. Each article has extracted entities (location, project name, budget, authority) stored in its normalized schema
  4. When Claude API is unavailable (simulated by setting an invalid API key), the pipeline automatically retries with Gemini and completes classification without manual intervention
  5. Monthly AI spend tracked in state JSON does not exceed the $5 budget based on token estimates logged per run
**Plans**: 2 plans

Plans:
- [ ] 05-01-PLAN.md — AI response schemas, AICost schema, Article extensions, cost tracker module with budget gates, SDK dependencies
- [ ] 05-02-PLAN.md — Claude batch classifier with domain-primed prompt, Gemini fallback, pipeline wiring, deliver.yml update

### Phase 6: Telegram Delivery
**Goal**: Classified articles are selected, formatted, and delivered to both Telegram users at 7 AM and 4 PM IST with priority-labelled sections, AI summaries, and source links — with the pipeline integrated into the GitHub Actions scheduled workflow
**Depends on**: Phase 5
**Requirements**: DLVR-01, DLVR-02, DLVR-04
**Success Criteria** (what must be TRUE):
  1. A manual pipeline run sends a Telegram message to both configured user IDs containing articles grouped into HIGH, MEDIUM, and LOW priority sections with summaries and links
  2. Messages longer than 4096 characters are automatically split into sequential Telegram messages without cutting mid-article
  3. The selection algorithm allocates up to 8 HIGH-priority, at least 4 MEDIUM, and at least 2 LOW stories — capped at 15 total — and the selection counts are visible in the log
  4. The GitHub Actions cron triggers delivery at 7 AM IST (01:30 UTC) and 4 PM IST (10:30 UTC), and delivery timestamps visible in Telegram messages confirm correct IST timing
**Plans**: 2 plans

Plans:
- [x] 06-01-PLAN.md — Priority-based article selector and Telegram HTML message formatter with chunking
- [x] 06-02-PLAN.md — Telegram API sender with retry, pipeline wiring into main.py, deliver.yml secrets

### Phase 7: Email Delivery and Edge Cases
**Goal**: Delivery is complete with HTML email digests sent via Gmail SMTP alongside Telegram, plus all edge cases handled gracefully — no-news days, slow-news days, and overflow HIGH stories all produce appropriate user-facing responses
**Depends on**: Phase 6
**Requirements**: DLVR-03, DLVR-06, DLVR-07
**Success Criteria** (what must be TRUE):
  1. A pipeline run sends an HTML email to the configured Gmail recipients with priority-colored article cards and source links rendered correctly
  2. When zero articles pass filtering, the pipeline sends a "no news today" message to Telegram (not a blank message or silence)
  3. When fewer than 15 articles are available, the pipeline sends all available articles and logs the slow-news condition without errors
  4. When more than 8 HIGH-priority stories are available, the delivery message includes a prompt "reply 'more' to see additional stories" referencing the overflow count
**Plans**: 2 plans

Plans:
- [ ] 07-01-PLAN.md — Gmail SMTP email sender with HTML card formatting, pipeline wiring, deliver.yml secrets
- [ ] 07-02-PLAN.md — Edge case handling: no-news, slow-news, HIGH overflow detection for both channels


### Phase 8: Railway Bot Foundation
**Goal**: A persistent Telegram bot process runs on Railway in polling mode, accepts commands only from authorized user IDs, responds to /help and /status, and dispatches heavy processing to GitHub Actions via repository_dispatch — with zero cold-start delays for command responses
**Depends on**: Phase 7
**Requirements**: INFRA-04, BOT-01, BOT-02, BOT-11
**Success Criteria** (what must be TRUE):
  1. Sending /help to the bot returns a formatted list of all available commands within 3 seconds, at any time of day with no cold-start delay
  2. Sending /status to the bot returns current system health (time of last pipeline run, number of active sources, delivery success rate for last 7 days)
  3. Sending any command from an unauthorized Telegram user ID receives an "unauthorized" response and the command is not processed
  4. The Railway deployment stays running continuously across 24 hours without process restarts visible in the Railway logs
  5. The bot dispatches a `run_now` event to GitHub Actions via `repository_dispatch` and the triggered pipeline run is visible in GitHub Actions UI
**Plans**: 3 plans

Plans:
- [ ] 08-01-PLAN.md — PipelineStatus schema, loader/saver, railway.json, python-telegram-bot dependency, deliver.yml updates
- [ ] 08-02-PLAN.md — Authorization guard, /help and /status command handlers, GitHub Contents API status reader, bot entrypoint
- [ ] 08-03-PLAN.md — Repository dispatch trigger for on-demand pipeline runs via /run command

### Phase 9: Keyword and Menu Management
**Goal**: Users can view, add, and remove keywords by category via Telegram commands, and can access all settings through an interactive inline keyboard menu — with changes persisted to the YAML keyword library and immediately applied to the next pipeline run
**Depends on**: Phase 8
**Requirements**: BOT-04, BOT-05, BOT-06
**Success Criteria** (what must be TRUE):
  1. Sending /keywords returns all current keywords organized by category (Infrastructure, Authorities/Regulatory, Celebrity real estate) in a readable format
  2. Sending "add keyword: bullet train" adds "bullet train" to the Infrastructure category in `keywords.yaml`, commits the file, and the bot confirms the addition
  3. Sending "remove celebrity: Salman Khan" removes the keyword from the Celebrity category, commits the file, and the bot confirms the removal
  4. Sending /menu opens an inline keyboard with buttons for settings, keywords, and stats — tapping a button navigates to that section without the user needing to type a command
**Plans**: 2 plans

Plans:
- [ ] 09-01-PLAN.md — GitHub file writer, keyword mutation functions, /keywords + add/remove command handlers
- [ ] 09-02-PLAN.md — Inline keyboard menu with callback handlers, entrypoint wiring, /help text update

### Phase 10: Advanced Bot Controls
**Goal**: Users can control delivery scheduling in natural language, pause and resume alerts with duration support, create event-based one-off schedules, view 7-day delivery statistics, and receive updates from dynamically modified schedules — all through the Telegram bot
**Depends on**: Phase 9
**Requirements**: BOT-03, BOT-07, BOT-08, BOT-09, BOT-10
**Success Criteria** (what must be TRUE):
  1. Sending "/pause 3 days" pauses all deliveries for exactly 3 days, and sending /resume before that period restores delivery immediately — both confirmed by bot reply
  2. Sending "stop evening alerts for a week" in natural language is parsed correctly and pauses only the 4 PM delivery for 7 days, confirmed by bot reply
  3. Sending "Budget on Feb 1, updates every 30 min from 10 AM to 3 PM" creates an event-based schedule entry in bot_state.json and the bot confirms the event with start/end times in IST
  4. Sending "change morning alert to 6:30 AM" updates the 7 AM delivery cron to 6:30 AM IST (01:00 UTC) in bot_state.json and the bot confirms the new time
  5. Sending /stats returns a formatted summary showing article counts, top topics, and duplicates prevented for the last 7 days
**Plans**: 3 plans

Plans:
- [ ] 10-01-PLAN.md — BotState schema, duration parser, /pause and /resume handlers with GitHub persistence
- [ ] 10-02-PLAN.md — /stats command with 7-day history aggregation and formatted display
- [ ] 10-03-PLAN.md — NL intent parser (Claude Haiku), schedule modification, event scheduling, entrypoint wiring

### Phase 11: Breaking News and Production Hardening
**Goal**: A separate lightweight breaking news watcher fires between scheduled deliveries for critical HIGH-priority stories, the system operates entirely within free-tier limits, and all monitoring surfaces in /status — making the system production-ready and self-sustaining
**Depends on**: Phase 10
**Requirements**: DLVR-05, INFRA-06
**Success Criteria** (what must be TRUE):
  1. A breaking news alert is sent to both Telegram users within 60 minutes of a genuinely HIGH-priority story appearing (verified with a mock HIGH-priority article injected into the test feed)
  2. The breaking news workflow uses keyword-only fast-path filtering and only calls the AI API when the keyword filter flags the article as HIGH, preventing unnecessary AI cost for every 30-minute check
  3. The system operates for a full calendar month without exceeding Railway $5 credit, GitHub Actions 2000 minutes, or $5 AI API costs — verified by reviewing usage dashboards
  4. The /status command shows current free-tier usage percentages (Actions minutes used, estimated AI spend this month) alongside system health
**Plans**: TBD

Plans:
- [ ] 11-01: Breaking news workflow (breaking.yml) with 30-60 min cron and keyword-only fast-path before AI confirmation
- [ ] 11-02: Free-tier usage tracker in state JSON and /status integration
- [ ] 11-03: End-to-end production validation (live run, live bot, real articles, real delivery)

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7 -> 8 -> 9 -> 10 -> 11

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Project Scaffold | 3/3 | Complete   | 2026-02-27 |
| 2. Scheduling Infrastructure | 2/2 | Complete   | 2026-02-27 |
| 3. News Fetching | 3/3 | Complete   | 2026-02-27 |
| 4. Filtering and Deduplication | 3/3 | Complete   | 2026-02-28 |
| 5. AI Analysis Pipeline | 2/2 | Complete | 2026-03-07 |
| 6. Telegram Delivery | 2/2 | Complete | 2026-03-07 |
| 7. Email Delivery and Edge Cases | 0/2 | Not started | - |
| 8. Railway Bot Foundation | 2/3 | In Progress|  |
| 9. Keyword and Menu Management | 1/2 | In Progress|  |
| 10. Advanced Bot Controls | 3/3 | Complete   | 2026-03-08 |
| 11. Breaking News and Production Hardening | 0/3 | Not started | - |
