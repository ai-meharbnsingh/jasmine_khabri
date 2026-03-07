---
phase: 5
slug: ai-analysis-pipeline
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-07
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.0+ (already configured) |
| **Config file** | pyproject.toml `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/test_classifier.py tests/test_cost_tracker.py -x` |
| **Full suite command** | `uv run pytest tests/ -v --tb=short` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_classifier.py tests/test_cost_tracker.py -x`
- **After every plan wave:** Run `uv run pytest tests/ -v --tb=short`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 05-01-01 | 01 | 1 | AI-01 | unit (mocked API) | `uv run pytest tests/test_classifier.py::TestBatchClassification -x` | No - W0 | pending |
| 05-01-02 | 01 | 1 | AI-02 | unit (mocked API) | `uv run pytest tests/test_classifier.py::TestSummaryGeneration -x` | No - W0 | pending |
| 05-01-03 | 01 | 1 | AI-05 | unit (mocked API) | `uv run pytest tests/test_classifier.py::TestEntityExtraction -x` | No - W0 | pending |
| 05-02-01 | 02 | 2 | AI-06 | unit (mocked API) | `uv run pytest tests/test_classifier.py::TestGeminiFallback -x` | No - W0 | pending |
| 05-02-02 | 02 | 2 | AI-07 | unit | `uv run pytest tests/test_cost_tracker.py -x` | No - W0 | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_classifier.py` — stubs for AI-01, AI-02, AI-05, AI-06 (mocked API responses)
- [ ] `tests/test_cost_tracker.py` — stubs for AI-07 (load/save/budget gates)
- [ ] `tests/test_ai_response_schema.py` — Pydantic model validation for batch response
- [ ] `data/ai_cost.json` — seed file with initial state
- [ ] Dependencies: `uv add anthropic google-genai` in pyproject.toml

*Existing infrastructure (pytest, respx, Pydantic) covers test framework needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Actual AI classification quality | AI-01 | Requires real API calls with real articles | Set ANTHROPIC_API_KEY, run pipeline with live articles, review priority labels |
| Writer-focused summary quality | AI-02 | Subjective quality judgment | Review AI summaries for domain relevance and writer utility |

---

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
