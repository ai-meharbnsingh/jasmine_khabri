---
phase: 9
slug: keyword-and-menu-management
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-08
---

# Phase 9 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | pyproject.toml `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/ -x -q` |
| **Full suite command** | `uv run pytest tests/ -v --tb=short` |
| **Estimated runtime** | ~10 seconds |

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
| 09-01-01 | 01 | 1 | BOT-05 | unit | `uv run pytest tests/test_bot_keywords.py -x` | Wave 0 | pending |
| 09-02-01 | 02 | 2 | BOT-05 | unit | `uv run pytest tests/test_bot_keywords.py -x` | Wave 0 | pending |
| 09-02-02 | 02 | 2 | BOT-05 | unit | `uv run pytest tests/test_bot_github.py -x` | Wave 0 | pending |
| 09-03-01 | 03 | 3 | BOT-04, BOT-06 | unit | `uv run pytest tests/test_bot_menu.py -x` | Wave 0 | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_bot_keywords.py` — stubs for BOT-05 (/keywords display, add, remove)
- [ ] `tests/test_bot_github.py` — stubs for GitHub Contents API write (PUT with SHA)
- [ ] `tests/test_bot_menu.py` — stubs for BOT-04, BOT-06 (inline keyboard, callback handlers)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Inline keyboard buttons respond on tap | BOT-04 | Requires live Telegram interaction | Send /menu, tap each button, verify navigation |
| Keyword changes persist across pipeline runs | BOT-05 | Requires live GitHub + pipeline run | Add keyword via bot, trigger /run, verify keyword used in filtering |
| Menu navigates without typing commands | BOT-06 | Requires live Telegram interaction | Use only button taps to reach all menu sections |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
