---
phase: 10-advanced-bot-controls
plan: 01
subsystem: bot
tags: [pause, resume, bot-state, duration-parser, github-api]
dependency_graph:
  requires: [pipeline.bot.github, pipeline.schemas]
  provides: [pipeline.schemas.bot_state_schema, pipeline.bot.pause]
  affects: [deliver.yml, data/bot_state.json]
tech_stack:
  added: []
  patterns: [read-mutate-write-github, duration-regex-parser, pydantic-model-copy]
key_files:
  created:
    - src/pipeline/schemas/bot_state_schema.py
    - src/pipeline/bot/pause.py
    - data/bot_state.json
  modified:
    - src/pipeline/schemas/__init__.py
    - src/pipeline/utils/loader.py
    - .github/workflows/deliver.yml
    - tests/test_bot_pause.py
decisions:
  - "Indefinite pause uses paused_until='' with paused_slots=['all'] -- empty string signals no expiry"
  - "Duration regex: (\\d+|a|an)\\s*(minute|hour|day|week|month)s? with IGNORECASE -- covers all natural forms"
  - "write_github_file called with keyword args -- matches existing GitHub API pattern in keywords.py"
  - "IST display via timezone(timedelta(hours=5, minutes=30)) -- same _IST constant as telegram_sender.py"
metrics:
  duration: 4 min
  completed: "2026-03-08T00:20:00Z"
  tasks_completed: 2
  tasks_total: 2
  test_count: 28
  total_suite: 442
---

# Phase 10 Plan 01: Pause/Resume Commands Summary

BotState Pydantic schema with PauseState/EventSchedule/CustomSchedule, parse_duration regex parser for natural durations, /pause and /resume handlers persisting to bot_state.json via GitHub Contents API.

## Tasks Completed

| # | Task | Commit | Test Count |
|---|------|--------|------------|
| 1 | BotState schema, loader, duration parser, seed file | a61ad28 | 20 |
| 2 | /pause and /resume command handlers | dfc49d4 | 28 (8 new) |

## What Was Built

### BotState Schema (bot_state_schema.py)
- PauseState: paused_until (ISO 8601 or empty), paused_slots (list of slot names)
- EventSchedule: name, date, interval_minutes, start/end times, active flag
- CustomSchedule: morning_ist, evening_ist (empty = use config.yaml defaults)
- BotState: top-level model with pause, events, custom_schedule fields

### Duration Parser (pause.py)
- Regex-based parser for "3 days", "a week", "an hour", "1 month", "30 minutes"
- "a"/"an" maps to amount 1, month = 30 days
- Returns None for unparseable input

### Pause/Resume Handlers (pause.py)
- pause_command: extracts text after /pause, parses duration, reads bot_state.json from GitHub with SHA, sets paused_until + paused_slots=["all"], writes back, replies with IST expiry
- resume_command: reads bot_state.json, checks if paused, clears PauseState, writes back, replies "Deliveries resumed."
- Both handle: missing env vars, GitHub write failures, unparseable duration

### Infrastructure
- data/bot_state.json seed file with empty state
- deliver.yml: bot_state.json added to EndBug commit-back list
- load_bot_state in loader.py with safe defaults on missing/empty file
- Schemas exported from __init__.py

## Deviations from Plan

None -- plan executed exactly as written.

## Verification

- `uv run pytest tests/test_bot_pause.py -v`: 28 passed
- `uv run pytest tests/ -x -q`: 442 passed (0 regressions)
- Schema importable, handlers importable, seed file valid JSON

## Self-Check: PASSED
