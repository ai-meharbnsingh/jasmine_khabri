---
phase: 06
slug: telegram-delivery
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-07
---

# Phase 06 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.0+ |
| **Config file** | pyproject.toml `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/test_telegram_sender.py tests/test_selector.py -x` |
| **Full suite command** | `uv run pytest tests/ -v --tb=short` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_telegram_sender.py tests/test_selector.py -x`
- **After every plan wave:** Run `uv run pytest tests/ -v --tb=short`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 06-01-01 | 01 | 1 | DLVR-04 | unit | `uv run pytest tests/test_selector.py -x` | ❌ W0 | ⬜ pending |
| 06-01-02 | 01 | 1 | DLVR-04 | unit | `uv run pytest tests/test_selector.py::TestEdgeCases -x` | ❌ W0 | ⬜ pending |
| 06-02-01 | 02 | 1 | DLVR-01 | unit | `uv run pytest tests/test_telegram_sender.py -x` | ❌ W0 | ⬜ pending |
| 06-02-02 | 02 | 1 | DLVR-01 | unit | `uv run pytest tests/test_telegram_sender.py::TestChunking -x` | ❌ W0 | ⬜ pending |
| 06-02-03 | 02 | 1 | DLVR-01 | unit | `uv run pytest tests/test_telegram_sender.py::TestEscaping -x` | ❌ W0 | ⬜ pending |
| 06-02-04 | 02 | 1 | DLVR-02 | unit | `uv run pytest tests/test_telegram_sender.py::TestDeliveryPeriod -x` | ❌ W0 | ⬜ pending |
| 06-03-01 | 03 | 2 | DLVR-01 | unit | `uv run pytest tests/test_main.py -x` | ✅ update | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_selector.py` — stubs for DLVR-04 (selection algorithm, edge cases)
- [ ] `tests/test_telegram_sender.py` — stubs for DLVR-01, DLVR-02 (formatting, sending, chunking, escaping, period detection)
- [ ] Update `tests/test_main.py` — add delivery integration assertion

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Telegram message renders correctly on mobile | DLVR-01 | Visual rendering depends on Telegram client | Send test message, verify on phone |
| IST timestamps correct in delivered message | DLVR-02 | Requires real Telegram delivery | Manual pipeline run, check message timestamps |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
