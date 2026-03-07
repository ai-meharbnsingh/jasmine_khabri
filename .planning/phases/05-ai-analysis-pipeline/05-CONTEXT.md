# Phase 5: AI Analysis Pipeline - Context

**Gathered:** 2026-03-07
**Status:** Ready for planning

<domain>
## Phase Boundary

Filtered articles are classified HIGH/MEDIUM/LOW by Claude Sonnet in a single batched API call, enriched with 2-line writer-focused impact summaries and structured entity extraction (location, project name, budget, authority), with automatic Gemini fallback on Claude failure — all within $5/month AI cost budget tracked via token-based accounting.

</domain>

<decisions>
## Implementation Decisions

### Classification criteria
- **HIGH priority** — all three of: (1) policy & regulatory impact (RERA changes, PMAY updates, metro approvals, highway sanctions), (2) major project milestones (metro line approvals, airport expansions, smart city awards, large land deals), (3) market-moving events (interest rate changes, stamp duty revisions, celebrity transactions, large builder announcements)
- **MEDIUM priority** — progress updates on known projects (construction updates, tender awards, deadline extensions) AND regional/Tier 2-3 developments (new industrial corridors, smart city progress, local RERA actions)
- **LOW priority** — catch-all for anything that passed keyword/geo filters but doesn't meet HIGH or MEDIUM: industry commentary, expert opinions, market forecasts, routine operational news, standard compliance updates

### Summary style
- Writer-focused impact summaries, not generic news summaries
- Each 2-line summary answers "why this matters for your articles" for Magic Bricks content writers
- Example: "Delhi Metro Phase 4 approval unlocks 3 new corridor stories for NCR real estate coverage. Budget: Rs 46,000 crore."

### Entity extraction
- Structured fields on Article schema: location, project_name, budget, authority — four entities only
- All extracted in the same batch API call as classification and summary (single prompt, single call)
- Empty string for missing entities (consistent with existing Article schema pattern: summary='', dedup_ref='')

### Cost controls
- Token-based cost tracking using API response metadata (input/output token counts, per-token pricing)
- Cost state stored in new `data/ai_cost.json` (separate file like gnews_quota.json, committed back by deliver.yml)
- Warning logged at 80% ($4.00) of $5/month budget
- Degrade to keyword-only scoring at 95% ($4.75) — articles pass through with priority based on Phase 4 relevance scores, no AI summaries/entities
- Monthly reset (similar to gnews_quota.json pattern)

### Fallback behavior
- Silent fallback — invisible to users, logged for debugging only
- Same prompt for Gemini as Claude — identical system prompt, same JSON output structure
- Any Claude API failure (timeout, rate limit, auth error, 500) triggers one Gemini attempt immediately — no Claude retries
- If both Claude and Gemini fail: articles pass through unclassified with priority='MEDIUM' default, no summary, no entities — users still get news

### Claude's Discretion
- Exact system prompt engineering and domain priming
- Article truncation strategy for input token optimization
- Prompt caching approach
- JSON output schema design for the batch response
- Gemini model selection (Flash vs Pro)
- Token price constants and update strategy
- ai_cost.json schema design

</decisions>

<specifics>
## Specific Ideas

- Summaries should feel like editorial briefs: "why this matters for your next article" — not wire-service summaries
- The batch call should handle up to 15 articles in one request (matching the delivery cap)
- AI cost tracking follows the same commit-back pattern as gnews_quota.json via EndBug/add-and-commit in deliver.yml
- Phase 4 geo tier thresholds (Tier 2: 60, Tier 3: 85) are proxies — the AI classifier adds semantic understanding on top

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/pipeline/analyzers/classifier.py`: Empty placeholder ready for implementation
- `src/pipeline/schemas/article_schema.py`: Article model with summary='', needs new entity fields (location, project_name, budget, authority) and priority field
- `data/gnews_quota.json` pattern: Monthly-resetting JSON state file — same pattern for ai_cost.json
- `src/pipeline/utils/loader.py`: load/save utilities for JSON state files

### Established Patterns
- Pydantic v2 models for all data (schemas/), loader utilities for disk I/O (utils/loader.py)
- httpx for HTTP calls (already a dependency)
- Functional style: functions return new state, no mutation (e.g., purge_old_entries, filter_duplicates)
- Environment variables for API keys (GNEWS_API_KEY pattern — same for ANTHROPIC_API_KEY, GOOGLE_API_KEY)

### Integration Points
- `main.py` line 127: "Phase 5-7: classify, deliver (not yet implemented)" — wire classifier after dedup_articles
- Article.summary field: currently always empty, Phase 5 populates it
- deliver.yml: needs ai_cost.json added to EndBug/add-and-commit file list
- pyproject.toml dependencies: needs anthropic SDK and google-genai SDK added

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 05-ai-analysis-pipeline*
*Context gathered: 2026-03-07*
