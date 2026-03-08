---
phase: 10
slug: advanced-bot-controls
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-08
---

# Phase 10 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | pyproject.toml `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/ -x -q` |
| **Full suite command** | `uv run pytest tests/ -v --tb=short` |
| **Estimated runtime** | ~12 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -v --tb=short`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 12 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 10-01-01 | 01 | 1 | BOT-07 | unit | `uv run pytest tests/test_bot_pause.py -x` | Wave 0 | pending |
| 10-02-01 | 02 | 1 | BOT-03 | unit | `uv run pytest tests/test_bot_nl_parser.py -x` | Wave 0 | pending |
| 10-03-01 | 03 | 2 | BOT-08, BOT-09 | unit | `uv run pytest tests/test_bot_schedule.py -x` | Wave 0 | pending |
| 10-04-01 | 04 | 2 | BOT-10 | unit | `uv run pytest tests/test_bot_stats.py -x` | Wave 0 | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_bot_pause.py` — stubs for BOT-07 (pause/resume with duration)
- [ ] `tests/test_bot_nl_parser.py` — stubs for BOT-03 (natural language intent parsing)
- [ ] `tests/test_bot_schedule.py` — stubs for BOT-08, BOT-09 (event scheduling, schedule modification)
- [ ] `tests/test_bot_stats.py` — stubs for BOT-10 (7-day delivery stats)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| NL message correctly parsed by Claude Haiku | BOT-03 | Requires live AI API call | Send freeform text like "stop evening alerts for a week", verify intent parsed |
| Pause persists across bot restarts | BOT-07 | Requires live Railway deployment | Pause, restart Railway service, verify pause still active |
| Event-based schedule triggers delivery | BOT-08 | Requires live pipeline + cron | Create event, wait for trigger time, verify delivery occurs |
| Schedule change reflected in next delivery | BOT-09 | Requires live pipeline run at new time | Change morning time, verify next delivery at new time |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 12s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
