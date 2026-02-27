# Phase 3: News Fetching - Context

**Gathered:** 2026-02-27
**Status:** Ready for planning

<domain>
## Phase Boundary

The pipeline reliably fetches articles from all curated RSS feeds and GNews.io API, normalizes them to a unified schema, and logs per-source health without failing the entire run on individual source errors. Filtering, deduplication, and AI analysis belong to later phases.

</domain>

<decisions>
## Implementation Decisions

### RSS Feed Sources
- Feed URLs stored in config.yaml — add/remove feeds by editing YAML, no code changes needed
- Claude researcher finds the actual RSS/Atom URLs for each source (MOHUA, NHAI, AAI, Smart Cities, ET Realty, TOI Real Estate, Hindu BL, Moneycontrol RE)
- If a source has no RSS feed, skip it entirely — no scraping fallback
- 10-second timeout per feed before marking as failed and moving to next source

### GNews Quota Strategy
- 25 daily API calls split evenly: 12 for morning run, 13 for evening run
- Infrastructure keyword group gets priority over Regulatory when quota is limited
- GNews API key from environment variable (GNEWS_API_KEY via GitHub Actions secrets)
- Results filtered to India only (country=in parameter)
- English language only for GNews results
- Claude decides: query grouping strategy (broad vs specific), quota reset timing, quota-exhausted logging behavior

### Error & Retry Behavior
- No retries on RSS feed failures — log the failure and move on to next source
- Health summary table logged at end of each run: source name, status (OK/FAIL), article count, error if any
- Claude decides: exit code when all sources fail, GNews API error classification (auth vs transient)

### Article Schema
- Unified schema fields: title, url, source, published_at, summary, fetched_at (new — tracks when article was fetched)
- Summary field left EMPTY — do not populate from RSS feed descriptions. Phase 5 AI pipeline will generate all summaries.
- Claude decides: whether Article is a new Pydantic model or extends SeenEntry, how to handle missing/unparseable published_at dates

### Claude's Discretion
- GNews query construction strategy (few broad Boolean queries vs many specific ones)
- Quota tracker reset mechanism (first-run-of-day vs midnight IST)
- Whether to log warning or silently skip when GNews quota is exhausted
- Exit behavior when all sources fail in a single run
- GNews API error classification (special handling for auth failures vs same as RSS)
- Article model architecture (new model vs extending existing)
- Fallback for missing published_at dates

</decisions>

<specifics>
## Specific Ideas

- RSS feeds configurable via config.yaml so feeds can be added/removed without code deploys
- GNews filtered to India + English to stay focused on Indian infrastructure/regulatory news
- Health summary table at end of each run for quick visual check of pipeline health
- fetched_at timestamp on every article for debugging and purge alignment

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 03-news-fetching*
*Context gathered: 2026-02-27*
