---
phase: 8
slug: railway-bot-foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-07
---

# Phase 8 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | pyproject.toml `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/ -x -q` |
| **Full suite command** | `uv run pytest tests/ -v --tb=short` |
| **Estimated runtime** | ~8 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -v --tb=short`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 08-01-01 | 01 | 1 | INFRA-04 | unit | `uv run pytest tests/test_bot_entrypoint.py -x` | Wave 0 | pending |
| 08-01-02 | 01 | 1 | INFRA-04 | unit | `uv run pytest tests/test_pipeline_status.py -x` | Wave 0 | pending |
| 08-02-01 | 02 | 1 | BOT-11 | unit | `uv run pytest tests/test_bot_auth.py -x` | Wave 0 | pending |
| 08-02-02 | 02 | 1 | BOT-01, BOT-02 | unit | `uv run pytest tests/test_bot_handler.py -x` | Wave 0 | pending |
| 08-03-01 | 03 | 2 | INFRA-04 | unit | `uv run pytest tests/test_bot_dispatcher.py -x` | Wave 0 | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_bot_entrypoint.py` — stubs for INFRA-04 (Application construction, polling config)
- [ ] `tests/test_bot_handler.py` — stubs for BOT-01, BOT-02 (/help and /status)
- [ ] `tests/test_bot_auth.py` — stubs for BOT-11 (authorization guard)
- [ ] `tests/test_bot_dispatcher.py` — stubs for INFRA-04 (repository_dispatch)
- [ ] `tests/test_pipeline_status.py` — stubs for BOT-02 (PipelineStatus schema + main.py write)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Bot responds within 3s at any time of day | INFRA-04 | Requires live Railway deployment | Deploy to Railway, send /help at various times, measure response time |
| Railway stays running 24h without restarts | INFRA-04 | Requires monitoring Railway logs over time | Check Railway dashboard logs after 24h deployment |
| repository_dispatch triggers visible workflow | INFRA-04 | Requires live GitHub Actions + Railway | Send /run from Telegram, verify workflow appears in Actions tab |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
