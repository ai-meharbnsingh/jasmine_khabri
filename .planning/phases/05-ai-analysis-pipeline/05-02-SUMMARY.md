---
phase: 05-ai-analysis-pipeline
plan: 02
subsystem: ai
tags: [anthropic, google-genai, classifier, structured-output, budget-gate, fallback]

# Dependency graph
requires:
  - phase: 05-ai-analysis-pipeline
    provides: AI response schemas (ArticleAnalysis, BatchClassificationResponse), AICost model, cost tracker with budget gates, Article schema with AI fields
  - phase: 04-filtering-and-deduplication
    provides: Deduped articles with relevance_score and geo_tier for fallback scoring
provides:
  - classify_articles() function with Claude Haiku 4.5 primary, Gemini 2.5 Flash fallback
  - Domain-primed system prompt for Indian infrastructure/real estate classification
  - Budget gate degradation to keyword-only scoring at $4.75
  - Both-fail fallback with MEDIUM priority default
  - Pipeline wiring: classifier called after dedup in main.py
  - deliver.yml updated with AI API key secrets and ai_cost.json commit-back
affects: [06-telegram-delivery, 07-email-delivery, 11-breaking-news]

# Tech tracking
tech-stack:
  added: []
  patterns: [claude-structured-output-with-parse, gemini-structured-json-fallback, budget-gate-degradation, keyword-only-fallback]

key-files:
  created:
    - tests/test_classifier.py
  modified:
    - src/pipeline/analyzers/classifier.py
    - src/pipeline/main.py
    - .github/workflows/deliver.yml

key-decisions:
  - "Claude Haiku 4.5 as primary model ($1/$5 MTok) -- 3x cheaper than Sonnet, sufficient for classification"
  - "Domain-primed system prompt with Indian infra/real estate classification criteria from CONTEXT.md"
  - "Budget exceeded ($4.75) degrades to keyword-only: relevance_score >=80 HIGH, >=60 MEDIUM, else LOW"
  - "Both-providers-fail assigns MEDIUM priority with empty summary/entities -- pipeline never crashes"
  - "GOOGLE_API_KEY env var (not GEMINI_API_KEY) matches deliver.yml naming convention"

patterns-established:
  - "AI provider fallback: try Claude, catch any Exception, try Gemini, catch any Exception, apply default"
  - "Budget degradation: keyword-only scoring maps Phase 4 relevance_score to priority when AI unavailable"
  - "Structured output: Claude .parse() with output_format, Gemini response_json_schema -- both use same Pydantic model"
  - "Article enrichment: model_copy(update={...}) maps AI response fields to Article schema fields"

requirements-completed: [AI-01, AI-02, AI-05, AI-06, AI-07]

# Metrics
duration: 5min
completed: 2026-03-07
---

# Phase 5 Plan 02: AI Classifier Implementation Summary

**Batch classifier with Claude Haiku primary, Gemini Flash fallback, domain-primed prompt for Indian infra/real estate, budget gate degradation, and pipeline wiring**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-07T07:11:21Z
- **Completed:** 2026-03-07T07:16:25Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- classify_articles() classifies up to 15 articles in a single batch API call with priority, 2-line writer-focused summary, and entity extraction (location, project_name, budget, authority)
- Claude Haiku 4.5 primary with automatic Gemini 2.5 Flash fallback on any exception -- both-fail gracefully assigns MEDIUM default
- Budget gate at $4.75 degrades to keyword-only scoring (relevance_score mapping), pipeline never crashes on AI failures
- Classifier wired into main.py after dedup filter, deliver.yml updated with API key secrets and ai_cost.json commit-back
- 169 total tests passing (14 new classifier tests, all mocked -- no real API calls)

## Task Commits

Each task was committed atomically:

1. **Task 1: Classifier module with Claude primary, Gemini fallback, and budget gate**
   - `87154ae` (test: RED - failing tests for AI classifier)
   - `99f68a6` (feat: GREEN - implement classifier with structured output)
2. **Task 2: Wire classifier into pipeline and update deliver.yml**
   - `d2973e2` (feat: wire classifier into main.py, update deliver.yml)

## Files Created/Modified
- `src/pipeline/analyzers/classifier.py` - classify_articles() with Claude/Gemini providers, system prompt, budget gate, truncation
- `tests/test_classifier.py` - 14 mocked tests covering classification, summaries, entities, fallback, budget, truncation
- `src/pipeline/main.py` - Phase 5 classifier wired after dedup, AI key env var guard
- `.github/workflows/deliver.yml` - ANTHROPIC_API_KEY and GOOGLE_API_KEY uncommented, ai_cost.json in commit-back

## Decisions Made
- Claude Haiku 4.5 as primary model ($1/$5 MTok) -- 3x cheaper than Sonnet, sufficient for classification/summarization
- Domain-primed system prompt with Indian infrastructure/real estate classification criteria directly from CONTEXT.md
- Budget exceeded ($4.75) degrades to keyword-only scoring: relevance_score >=80 HIGH, >=60 MEDIUM, else LOW
- Both-providers-fail assigns MEDIUM priority with empty summary/entities -- pipeline never crashes on AI failures
- GOOGLE_API_KEY env var (not GEMINI_API_KEY) matches deliver.yml naming convention per Research Pitfall 2

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required. (API keys are configured as GitHub Secrets when ready.)

## Next Phase Readiness
- All Phase 5 AI analysis is complete -- articles are classified, summarized, and entity-enriched
- Phase 6 (Telegram Delivery) can consume classified articles with priority field for selection
- Phase 7 (Email Delivery) can use summaries and entities for formatting
- API keys (ANTHROPIC_API_KEY, GOOGLE_API_KEY) need to be added as GitHub Secrets before live pipeline runs

## Self-Check: PASSED

All 4 files verified present. All 3 commits verified in git log.

---
*Phase: 05-ai-analysis-pipeline*
*Completed: 2026-03-07*
