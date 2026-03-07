---
phase: 05-ai-analysis-pipeline
plan: 01
subsystem: ai
tags: [pydantic, anthropic, google-genai, cost-tracking, schemas]

# Dependency graph
requires:
  - phase: 04-filtering-and-deduplication
    provides: Article schema with filter fields (relevance_score, geo_tier, dedup_status, dedup_ref)
  - phase: 03-news-fetching
    provides: Article model, GNewsQuota pattern for cost tracking
provides:
  - ArticleAnalysis and BatchClassificationResponse Pydantic models for structured AI output
  - AICost Pydantic model for monthly cost tracking
  - Cost tracker module with budget gates (ok/warning/exceeded)
  - Article schema extended with AI-populated fields (priority, location, project_name, budget_amount, authority)
  - anthropic and google-genai SDK dependencies installed
affects: [05-02-ai-classifier, 06-telegram-delivery, 07-email-delivery]

# Tech tracking
tech-stack:
  added: [anthropic, google-genai]
  patterns: [ai-response-schema, cost-tracking-with-budget-gates, monthly-reset]

key-files:
  created:
    - src/pipeline/schemas/ai_response_schema.py
    - src/pipeline/schemas/ai_cost_schema.py
    - src/pipeline/analyzers/cost_tracker.py
    - data/ai_cost.json
    - tests/test_ai_response_schema.py
    - tests/test_cost_tracker.py
  modified:
    - src/pipeline/schemas/article_schema.py
    - src/pipeline/schemas/__init__.py
    - src/pipeline/utils/loader.py
    - pyproject.toml
    - uv.lock

key-decisions:
  - "AICost follows GNewsQuota pattern: simple Pydantic model with monthly reset in loader"
  - "budget_amount field name avoids collision with Pydantic BaseModel internals"
  - "Functional style record_cost via model_copy matches GNewsQuota immutability pattern"
  - "Plain Pydantic models for AI response schemas (no custom validators) for Anthropic .parse() compatibility"

patterns-established:
  - "Cost tracking: load_ai_cost/save_ai_cost in loader.py following save_seen pattern"
  - "Budget gates: check_budget returns Literal['ok','warning','exceeded'] threshold states"
  - "AI response models: ArticleAnalysis/BatchClassificationResponse as structured output contracts"

requirements-completed: [AI-07]

# Metrics
duration: 4min
completed: 2026-03-07
---

# Phase 5 Plan 01: AI Pipeline Schemas and Cost Tracker Summary

**Pydantic schemas for AI classification output and cost tracking with $4.00/$4.75 budget gates, plus Claude Haiku and Gemini Flash pricing constants**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-07T07:04:00Z
- **Completed:** 2026-03-07T07:08:09Z
- **Tasks:** 2
- **Files modified:** 11

## Accomplishments
- ArticleAnalysis and BatchClassificationResponse Pydantic models validate structured AI output with priority, summary, and entity fields
- AICost schema with monthly reset, cost tracker with check_budget and record_cost using Claude Haiku ($1/$5 MTok) and Gemini Flash ($0.30/$2.50 MTok) pricing
- Article schema extended with 5 new AI-populated fields, all backward-compatible with existing Phase 3/4 constructors
- anthropic and google-genai SDK dependencies installed and importable
- 155 total tests passing (35 new)

## Task Commits

Each task was committed atomically:

1. **Task 1: AI response schema, AICost schema, and Article extensions**
   - `fbc17b9` (test: RED - failing tests for schemas)
   - `2fd7aa2` (feat: GREEN - implement schemas, extensions, seed data, SDK deps)
2. **Task 2: Cost tracker module with budget gates**
   - `46dc5ae` (test: RED - failing tests for cost tracker)
   - `7e728e9` (feat: GREEN - implement cost tracker and loader extensions)

## Files Created/Modified
- `src/pipeline/schemas/ai_response_schema.py` - ArticleAnalysis and BatchClassificationResponse Pydantic models
- `src/pipeline/schemas/ai_cost_schema.py` - AICost Pydantic model for monthly cost tracking
- `src/pipeline/schemas/article_schema.py` - Extended with priority, location, project_name, budget_amount, authority
- `src/pipeline/schemas/__init__.py` - Updated exports for new schemas
- `src/pipeline/analyzers/cost_tracker.py` - check_budget, record_cost with provider-specific pricing
- `src/pipeline/utils/loader.py` - load_ai_cost, save_ai_cost with monthly reset logic
- `data/ai_cost.json` - Seed file with 1970-01 epoch month
- `pyproject.toml` - anthropic and google-genai dependencies added
- `tests/test_ai_response_schema.py` - 20 tests for AI response, AICost, and Article extensions
- `tests/test_cost_tracker.py` - 15 tests for budget gates, pricing, load/save, monthly reset

## Decisions Made
- AICost follows GNewsQuota pattern: simple Pydantic model with monthly reset in loader
- budget_amount field name avoids collision with Pydantic BaseModel internals
- Functional style record_cost via model_copy matches GNewsQuota immutability pattern
- Plain Pydantic models for AI response schemas (no custom validators) for Anthropic .parse() compatibility

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- All AI pipeline contracts (schemas) are stable for Plan 05-02 classifier implementation
- Cost tracker ready to be called by classifier to track API usage
- Article schema has all fields needed for AI-populated analysis results
- SDK dependencies (anthropic, google-genai) installed and importable

## Self-Check: PASSED

All 8 files verified present. All 4 commits verified in git log.

---
*Phase: 05-ai-analysis-pipeline*
*Completed: 2026-03-07*
