---
phase: 11
slug: breaking-news-production-hardening
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-08
---

# Phase 11 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.0+ |
| **Config file** | pyproject.toml `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/ -x --tb=short` |
| **Full suite command** | `uv run pytest tests/ -v --tb=short` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ -x --tb=short`
- **After every plan wave:** Run `uv run pytest tests/ -v --tb=short`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 11-01-01 | 01 | 1 | DLVR-05 | unit | `uv run pytest tests/test_breaking.py::TestBreakingFilter -x` | ❌ W0 | ⬜ pending |
| 11-01-02 | 01 | 1 | DLVR-05 | unit | `uv run pytest tests/test_breaking.py::TestBreakingDedup -x` | ❌ W0 | ⬜ pending |
| 11-01-03 | 01 | 1 | DLVR-05 | unit | `uv run pytest tests/test_breaking.py::TestBreakingAIGate -x` | ❌ W0 | ⬜ pending |
| 11-01-04 | 01 | 1 | DLVR-05 | unit | `uv run pytest tests/test_breaking.py::TestBreakingFormat -x` | ❌ W0 | ⬜ pending |
| 11-01-05 | 01 | 1 | DLVR-05 | unit | `uv run pytest tests/test_breaking.py::TestBreakingPause -x` | ❌ W0 | ⬜ pending |
| 11-01-06 | 01 | 1 | DLVR-05 | unit | `uv run pytest tests/test_breaking.py::TestBreakingTimeWindow -x` | ❌ W0 | ⬜ pending |
| 11-02-01 | 02 | 2 | INFRA-06 | unit | `uv run pytest tests/test_pipeline_status.py::TestUsageTracking -x` | ❌ W0 | ⬜ pending |
| 11-02-02 | 02 | 2 | INFRA-06 | unit | `uv run pytest tests/test_pipeline_status.py::TestUsageReset -x` | ❌ W0 | ⬜ pending |
| 11-02-03 | 02 | 2 | INFRA-06 | unit | `uv run pytest tests/test_bot_handler.py::TestStatusUsage -x` | ❌ W0 | ⬜ pending |
| 11-02-04 | 02 | 2 | INFRA-06 | unit | `uv run pytest tests/test_main.py::TestRunCounter -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_breaking.py` — stubs for DLVR-05 (breaking news filter, dedup, AI gate, format, pause, time window)
- [ ] `tests/test_pipeline_status.py` — add TestUsageTracking, TestUsageReset stubs for INFRA-06
- [ ] `tests/test_bot_handler.py` — add TestStatusUsage stub for INFRA-06
- [ ] `tests/test_main.py` — add TestRunCounter stub for INFRA-06

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Full month within free-tier limits | INFRA-06 | Requires 30-day production observation | Review Railway, Actions, AI dashboards after 1 month |
| Breaking alert within 60 min | DLVR-05 | Real-time delivery timing | Inject mock HIGH article, observe Telegram delivery time |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
