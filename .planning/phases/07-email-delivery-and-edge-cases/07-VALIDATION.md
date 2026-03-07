---
phase: 07
slug: email-delivery-and-edge-cases
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-07
---

# Phase 07 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (via uv) |
| **Config file** | pyproject.toml `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/test_email_sender.py tests/test_edge_cases.py -x` |
| **Full suite command** | `uv run pytest tests/ -v --tb=short` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_email_sender.py tests/test_edge_cases.py -x`
- **After every plan wave:** Run `uv run pytest tests/ -v --tb=short`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 07-01-01 | 01 | 1 | DLVR-03 | unit | `uv run pytest tests/test_email_sender.py -x` | ❌ W0 | ⬜ pending |
| 07-01-02 | 01 | 1 | DLVR-03 | unit | `uv run pytest tests/test_email_sender.py -x` | ❌ W0 | ⬜ pending |
| 07-02-01 | 02 | 1 | DLVR-06 | unit | `uv run pytest tests/test_edge_cases.py -x` | ❌ W0 | ⬜ pending |
| 07-02-02 | 02 | 1 | DLVR-07 | unit | `uv run pytest tests/test_edge_cases.py -x` | ❌ W0 | ⬜ pending |
| 07-03-01 | 03 | 2 | DLVR-03 | unit | `uv run pytest tests/test_main.py -x` | ✅ update | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_email_sender.py` — stubs for DLVR-03 (email formatting, SMTP send mock, orchestrator)
- [ ] `tests/test_edge_cases.py` — stubs for DLVR-06, DLVR-07 (no-news, slow-news, overflow)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Email renders correctly in Gmail | DLVR-03 | Visual rendering depends on email client | Send test email, verify in Gmail web |
| Card border colors visible | DLVR-03 | CSS rendering varies by client | Check red/amber/green borders in Gmail |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
