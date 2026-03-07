# Phase 5: AI Analysis Pipeline - Research

**Researched:** 2026-03-07
**Domain:** LLM API integration (Anthropic Claude + Google Gemini), structured JSON extraction, cost-tracked AI pipeline
**Confidence:** HIGH

## Summary

Phase 5 transforms filtered articles into classified, summarized, entity-enriched output using Claude Sonnet as primary AI and Gemini Flash as fallback. The core technical challenge is designing a single-prompt batch call that classifies 15 articles with priority labels, generates writer-focused summaries, and extracts structured entities -- all within a $5/month budget.

The Anthropic Python SDK (`anthropic`) provides structured output via `client.messages.create()` with `output_config` or `client.messages.parse()` with Pydantic models. The `google-genai` SDK provides the same via `response_json_schema` in config. Both SDKs return token usage metadata in responses, enabling precise cost tracking. Prompt caching on the system prompt reduces per-call cost by 90% on cache hits.

**Primary recommendation:** Use `anthropic` SDK with Pydantic-based structured output (`output_format=Model` via `.parse()`), cache the system prompt with `cache_control`, track costs from `response.usage` token counts, and fall back to `google-genai` with identical prompt structure on any Claude failure. Use Haiku 4.5 (not Sonnet) as the default model -- it is 3x cheaper and sufficient for classification/summarization at this scale, keeping monthly costs under $1.50 even without caching.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Classification criteria**: HIGH = policy/regulatory + major milestones + market-moving; MEDIUM = progress updates + regional/Tier 2-3; LOW = catch-all for commentary/opinions/routine
- **Summary style**: Writer-focused impact summaries ("why this matters for your articles"), not generic news summaries
- **Entity extraction**: Four fields only (location, project_name, budget, authority), extracted in same batch call, empty string for missing
- **Cost controls**: Token-based tracking in `data/ai_cost.json`, warning at 80% ($4.00), degrade at 95% ($4.75) to keyword-only scoring, monthly reset
- **Fallback behavior**: Silent fallback, same prompt for both providers, any Claude failure triggers one Gemini attempt (no Claude retries), both fail = MEDIUM default with no summary/entities
- **ai_cost.json committed back**: Added to deliver.yml EndBug/add-and-commit file list

### Claude's Discretion
- Exact system prompt engineering and domain priming
- Article truncation strategy for input token optimization
- Prompt caching approach
- JSON output schema design for the batch response
- Gemini model selection (Flash vs Pro)
- Token price constants and update strategy
- ai_cost.json schema design

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| AI-01 | System classifies articles as HIGH/MEDIUM/LOW priority using Claude Sonnet with domain-primed prompt | Anthropic SDK structured output with Pydantic model, system prompt with domain classification criteria, batch 15 articles in single call |
| AI-02 | System generates 2-line AI summary per article explaining real estate/infrastructure impact | Summary field in batch JSON response schema, writer-focused prompt engineering |
| AI-05 | System extracts key entities per article (location, project_name, budget, authority) | Four entity fields in Pydantic output model, empty string defaults |
| AI-06 | System uses Gemini as fallback when Claude API fails | google-genai SDK with identical prompt, try/except wrapper, silent logging |
| AI-07 | System batches articles per AI call (up to 15 per batch) to stay within $5/month budget | Single prompt with all articles, token-based cost tracking from response.usage, Haiku 4.5 at $1/$5 MTok keeps costs under $1.50/month |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| anthropic | >=0.84 | Claude API client | Official Anthropic Python SDK, Pydantic structured output via `.parse()`, prompt caching, usage tracking |
| google-genai | >=1.56 | Gemini API client | Official Google GenAI SDK (NOT google-generativeai which is deprecated), structured JSON output via response_json_schema |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pydantic | >=2.5 | Response schema models | Already a project dependency -- define AI response schema as Pydantic model |
| httpx | >=0.28.1 | HTTP transport | Already a project dependency -- anthropic SDK uses it internally |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Claude Sonnet 4.6 ($3/$15 MTok) | Claude Haiku 4.5 ($1/$5 MTok) | 3x cheaper, sufficient for classification/summarization -- RECOMMENDED for budget constraint |
| Gemini 2.5 Flash ($0.30/$2.50 MTok) | Gemini 2.5 Flash-Lite ($0.10/$0.40 MTok) | Even cheaper fallback, but Flash is already very cheap and more capable |
| sentence-transformers | Keep Phase 4 SequenceMatcher dedup | sentence-transformers requires PyTorch (~2GB install), impractical for GitHub Actions; Phase 4 dedup already handles 0.50-0.80 similarity range |

**Installation:**
```bash
uv add anthropic google-genai
```

**NOTE on sentence-transformers (Plan 05-03):** This library pulls in PyTorch (~2GB) and transformer models (~80MB model download). On GitHub Actions (ubuntu-latest), this adds 60-90 seconds to `uv sync` every run, twice daily. Phase 4 already implements SequenceMatcher-based dedup with 0.50-0.80 similarity detection. For wire-service republication detection, consider using Claude/Gemini within the batch call to flag semantic duplicates instead of adding a heavy local ML dependency. If sentence-transformers is still desired, install the CPU-only PyTorch variant (`pip install torch --index-url https://download.pytorch.org/whl/cpu`) to reduce install size from ~2GB to ~200MB.

## Architecture Patterns

### Recommended Project Structure
```
src/pipeline/
  analyzers/
    classifier.py          # Main classify_articles() function + prompt construction
    ai_client.py           # Claude/Gemini client wrappers (create_claude_client, create_gemini_client)
    cost_tracker.py        # Load/save/check ai_cost.json, budget gate logic
  schemas/
    article_schema.py      # Add: priority, location, project_name, budget, authority fields
    ai_cost_schema.py      # NEW: AICost Pydantic model
    ai_response_schema.py  # NEW: BatchClassificationResponse Pydantic model for structured output
data/
  ai_cost.json             # NEW: monthly cost tracking state file
```

### Pattern 1: Single-Prompt Batch Classification
**What:** Send all 15 articles in one API call with a domain-primed system prompt requesting structured JSON output
**When to use:** Every pipeline run after dedup filter
**Example:**
```python
# Source: https://platform.claude.com/docs/en/build-with-claude/structured-outputs
from pydantic import BaseModel
import anthropic


class ArticleAnalysis(BaseModel):
    index: int
    priority: str  # "HIGH", "MEDIUM", "LOW"
    summary: str  # 2-line writer-focused impact summary
    location: str
    project_name: str
    budget: str
    authority: str


class BatchClassificationResponse(BaseModel):
    articles: list[ArticleAnalysis]


client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

response = client.messages.parse(
    model="claude-haiku-4-5",  # or "claude-sonnet-4-6"
    max_tokens=4096,
    system=[{
        "type": "text",
        "text": SYSTEM_PROMPT,  # Domain-primed classification instructions
        "cache_control": {"type": "ephemeral"},  # Cache for 5 min
    }],
    messages=[{"role": "user", "content": articles_text}],
    output_format=BatchClassificationResponse,
)

result = response.parsed_output  # Typed BatchClassificationResponse
usage = response.usage  # input_tokens, output_tokens, cache_read_input_tokens, etc.
```

### Pattern 2: Gemini Fallback with Identical Prompt
**What:** On any Claude API exception, retry with Gemini using the same prompt
**When to use:** Claude timeout, rate limit, auth error, 500
**Example:**
```python
# Source: https://ai.google.dev/gemini-api/docs/structured-output
from google import genai

client = genai.Client()  # reads GEMINI_API_KEY (or GOOGLE_API_KEY) from env

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=f"{SYSTEM_PROMPT}\n\n{articles_text}",
    config={
        "response_mime_type": "application/json",
        "response_json_schema": BatchClassificationResponse.model_json_schema(),
    },
)

# Parse and validate with Pydantic
result = BatchClassificationResponse.model_validate_json(response.text)
# Token usage from response.usage_metadata (input_token_count, candidates_token_count)
```

### Pattern 3: Cost Tracking from Response Usage
**What:** Extract token counts from API response, compute cost, accumulate in ai_cost.json
**When to use:** After every AI call (Claude or Gemini)
**Example:**
```python
# Claude usage
input_tokens = (
    response.usage.input_tokens
    + response.usage.cache_creation_input_tokens
    + response.usage.cache_read_input_tokens
)
output_tokens = response.usage.output_tokens

# Compute cost using per-token pricing
cost = (input_tokens * INPUT_PRICE_PER_TOKEN) + (output_tokens * OUTPUT_PRICE_PER_TOKEN)
# Add cache-specific pricing adjustments
```

### Pattern 4: Budget Degradation Gate
**What:** Check accumulated cost before making AI call; skip AI if over 95% budget
**When to use:** At the start of classify_articles()
**Example:**
```python
def classify_articles(articles, cost_state):
    if cost_state.month_total >= 4.75:  # 95% of $5
        logger.warning("AI budget exceeded 95%% — skipping AI classification")
        return [a.model_copy(update={"priority": "MEDIUM"}) for a in articles]
    if cost_state.month_total >= 4.00:  # 80% warning
        logger.warning("AI budget at 80%% ($%.2f/$5.00)", cost_state.month_total)
    # Proceed with AI call...
```

### Anti-Patterns to Avoid
- **One API call per article:** 15 separate calls = 15x latency, 15x overhead tokens from system prompt. Always batch.
- **Hardcoding model names:** Use constants (e.g., `CLAUDE_MODEL = "claude-haiku-4-5"`) so model can be changed without code surgery.
- **Ignoring cache_creation vs cache_read tokens:** These have different prices. Cache writes cost 1.25x base, cache reads cost 0.1x base. Track them separately.
- **Using google-generativeai instead of google-genai:** The old `google-generativeai` package is deprecated (EOL Nov 2025). Use `google-genai` (the `from google import genai` pattern).
- **Parsing AI output with regex:** Use structured output (Pydantic model) to get guaranteed JSON. Never regex-parse LLM text output.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSON output parsing | Custom regex/string parsing of LLM text | Anthropic structured output (`output_format=Model`) / Gemini `response_json_schema` | Guaranteed valid JSON matching your Pydantic schema; no parsing errors |
| Token cost calculation | Manual token counting with tiktoken | `response.usage.input_tokens` / `response.usage.output_tokens` from API response | Exact counts from the API, includes system prompt tokens, cache tokens |
| Prompt caching | Custom caching layer | Anthropic `cache_control: {"type": "ephemeral"}` on system prompt | Built-in 5-min TTL, 90% cost reduction on cache hits, no storage needed |
| HTTP error handling | Custom retry/timeout logic | anthropic SDK built-in retries + try/except for fallback | SDK handles transient errors; our fallback handles persistent failures |

**Key insight:** Both Anthropic and Google SDKs provide structured output guarantees and token usage metadata. The entire cost tracking and JSON parsing problem is solved by the SDKs -- no custom infrastructure needed.

## Common Pitfalls

### Pitfall 1: Prompt Too Large for Caching
**What goes wrong:** System prompt under 1,024 tokens (Sonnet minimum for caching) means cache_control is silently ignored -- no error, just no caching.
**Why it happens:** Anthropic has minimum token thresholds for prompt caching (Haiku 4.5: 4,096 tokens; Sonnet 4.x: 1,024 tokens).
**How to avoid:** Ensure system prompt meets minimum threshold. For Haiku 4.5, the system prompt needs 4,096+ tokens -- pad with detailed classification examples if needed, or accept no caching (still within budget at $1/MTok).
**Warning signs:** `cache_read_input_tokens` is always 0 in response.usage.

### Pitfall 2: Gemini Environment Variable Name
**What goes wrong:** google-genai looks for `GEMINI_API_KEY` by default, but project may set `GOOGLE_API_KEY` (matching the CONTEXT.md pattern from deliver.yml).
**Why it happens:** The genai.Client() auto-reads `GEMINI_API_KEY`, but you can also pass `api_key=` explicitly.
**How to avoid:** Use `genai.Client(api_key=os.environ.get("GOOGLE_API_KEY", ""))` to match the project's env var naming convention.
**Warning signs:** Gemini fallback fails with auth error despite key being set.

### Pitfall 3: Cost Tracking Race Condition
**What goes wrong:** Two concurrent pipeline runs could both read ai_cost.json, both compute costs, and the second write overwrites the first's cost addition.
**Why it happens:** deliver.yml has `cancel-in-progress: false`, but GitHub Actions could theoretically overlap.
**How to avoid:** The deliver.yml concurrency group already prevents parallel runs. Just document the assumption.
**Warning signs:** Monthly cost appears lower than expected.

### Pitfall 4: Structured Output Model Mismatch
**What goes wrong:** Anthropic's `.parse()` silently returns `None` for `parsed_output` if the response doesn't match the schema.
**Why it happens:** Stop reason might be `max_tokens` (truncated) or `end_turn` with malformed content.
**How to avoid:** Always check `response.stop_reason == "end_turn"` and `response.parsed_output is not None`. Set `max_tokens` high enough for 15-article batch (~4096 tokens).
**Warning signs:** `parsed_output` is None, articles get MEDIUM default silently.

### Pitfall 5: Budget Month Boundary
**What goes wrong:** A run at 23:59 UTC on month-end could read the cost file, make an API call, then the next run at 00:01 UTC resets the month -- losing the last call's cost record.
**Why it happens:** Month reset logic checks current date vs stored date.
**How to avoid:** Reset only at the start of a run (load, check date, reset if new month, then track). The cost from the last-day run is already committed back by deliver.yml before the next run.
**Warning signs:** None -- this is inherently safe with sequential runs.

### Pitfall 6: Article Truncation
**What goes wrong:** Articles with very long titles or summaries push the batch prompt over reasonable token limits, increasing cost.
**Why it happens:** Some RSS feeds include full article text in description fields.
**How to avoid:** Truncate each article's content to ~200 characters (title) + ~500 characters (summary/description) before building the prompt. Log truncation count.
**Warning signs:** Input token count per call exceeding 15,000.

## Code Examples

Verified patterns from official sources:

### Claude Structured Output with Prompt Caching
```python
# Source: https://platform.claude.com/docs/en/build-with-claude/structured-outputs
# Source: https://platform.claude.com/docs/en/build-with-claude/prompt-caching
import anthropic
from pydantic import BaseModel


class ArticleAnalysis(BaseModel):
    index: int
    priority: str  # "HIGH" | "MEDIUM" | "LOW"
    summary: str
    location: str
    project_name: str
    budget: str
    authority: str


class BatchResponse(BaseModel):
    articles: list[ArticleAnalysis]


def classify_with_claude(
    system_prompt: str, articles_text: str, model: str = "claude-haiku-4-5"
) -> tuple[BatchResponse | None, dict]:
    """Classify articles using Claude with structured output.

    Returns (parsed_response, usage_dict) or (None, {}) on failure.
    """
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY

    response = client.messages.parse(
        model=model,
        max_tokens=4096,
        system=[{
            "type": "text",
            "text": system_prompt,
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[{"role": "user", "content": articles_text}],
        output_format=BatchResponse,
    )

    usage = {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "cache_creation_input_tokens": getattr(
            response.usage, "cache_creation_input_tokens", 0
        ),
        "cache_read_input_tokens": getattr(
            response.usage, "cache_read_input_tokens", 0
        ),
    }
    return (response.parsed_output, usage)
```

### Gemini Fallback with Structured Output
```python
# Source: https://ai.google.dev/gemini-api/docs/structured-output
import os
from google import genai


def classify_with_gemini(
    system_prompt: str, articles_text: str, model: str = "gemini-2.5-flash"
) -> tuple[BatchResponse | None, dict]:
    """Classify articles using Gemini as fallback.

    Returns (parsed_response, usage_dict) or (None, {}) on failure.
    """
    api_key = os.environ.get("GOOGLE_API_KEY", "")
    if not api_key:
        return (None, {})

    client = genai.Client(api_key=api_key)

    # Gemini doesn't have separate system message -- prepend to content
    full_prompt = f"{system_prompt}\n\n{articles_text}"

    response = client.models.generate_content(
        model=model,
        contents=full_prompt,
        config={
            "response_mime_type": "application/json",
            "response_json_schema": BatchResponse.model_json_schema(),
        },
    )

    result = BatchResponse.model_validate_json(response.text)
    usage = {
        "input_tokens": getattr(response.usage_metadata, "prompt_token_count", 0),
        "output_tokens": getattr(
            response.usage_metadata, "candidates_token_count", 0
        ),
    }
    return (result, usage)
```

### Cost Tracking
```python
# AICost schema following gnews_quota.json pattern
from pydantic import BaseModel


class AICost(BaseModel):
    month: str  # "YYYY-MM" format
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    call_count: int = 0


# Price constants (USD per token, not per MTok)
CLAUDE_HAIKU_INPUT = 1.0 / 1_000_000   # $1/MTok
CLAUDE_HAIKU_OUTPUT = 5.0 / 1_000_000  # $5/MTok
GEMINI_FLASH_INPUT = 0.30 / 1_000_000  # $0.30/MTok
GEMINI_FLASH_OUTPUT = 2.50 / 1_000_000 # $2.50/MTok

MONTHLY_BUDGET = 5.00
BUDGET_WARNING_THRESHOLD = 4.00   # 80%
BUDGET_DEGRADE_THRESHOLD = 4.75   # 95%
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `google-generativeai` package | `google-genai` package | EOL Nov 2025 | Must use `from google import genai`, NOT `import google.generativeai` |
| Gemini 2.0 Flash | Gemini 2.5 Flash | Retired Mar 3, 2026 | Model name is `gemini-2.5-flash`, NOT `gemini-2.0-flash` |
| Claude 3.5 Sonnet | Claude Sonnet 4.6 | May 2025+ | Model names now `claude-sonnet-4-6`, `claude-haiku-4-5` etc. |
| Anthropic beta header for structured output | GA structured output | 2026 | No beta header needed; use `output_format=` or `output_config=` |
| Manual JSON parsing of LLM output | SDK structured output | 2025 | Both Anthropic and Google SDKs guarantee schema-valid JSON |

**Deprecated/outdated:**
- `google-generativeai`: Deprecated, EOL Nov 2025. Replaced by `google-genai`.
- `gemini-2.0-flash`: Retired Mar 3, 2026. Use `gemini-2.5-flash`.
- `claude-3-5-sonnet-*`: Legacy model naming. Current names: `claude-sonnet-4-6`, `claude-haiku-4-5`.
- Anthropic `anthropic-beta: structured-outputs-2025-11-13` header: No longer needed for structured output.

## Model Selection Recommendation

| Model | Input $/MTok | Output $/MTok | Est. Monthly Cost (60 calls) | Quality | Recommendation |
|-------|-------------|--------------|------------------------------|---------|----------------|
| Claude Sonnet 4.6 | $3.00 | $15.00 | ~$2.88 | Excellent | Good but expensive for this task |
| Claude Haiku 4.5 | $1.00 | $5.00 | ~$0.96 | Very Good | **RECOMMENDED** -- 3x cheaper, sufficient for classification |
| Gemini 2.5 Flash | $0.30 | $2.50 | ~$0.36 | Good | Fallback only -- cheapest option |
| Gemini 2.5 Flash-Lite | $0.10 | $0.40 | ~$0.06 | Adequate | Alternative fallback if Flash unavailable |

**Budget analysis (60 calls/month = 2 runs/day x 30 days):**
- Per call estimate: ~8,500 input tokens (system prompt + 15 articles) + ~1,500 output tokens
- Haiku 4.5: $0.0085 + $0.0075 = **$0.016/call** = **$0.96/month**
- With prompt caching (cache hit): $0.00085 + $0.0075 = **$0.008/call** = **$0.50/month**
- Even worst case (Sonnet, no caching): $2.88/month -- well within $5 budget

## Plan 05-03 Considerations (Semantic Dedup)

The CONTEXT.md plans include Plan 05-03 for sentence-transformers semantic dedup. Key research findings:

**Problem:** sentence-transformers requires PyTorch as a dependency:
- CPU-only PyTorch: ~200MB download, ~500MB installed
- Full PyTorch (with CUDA): ~2GB
- Model download (all-MiniLM-L6-v2): ~80MB additional
- GitHub Actions impact: adds 60-90 seconds to `uv sync` on every run (120 runs/month)

**Phase 4 already handles dedup:**
- AI-03 (duplicate detection) and AI-04 (story updates) are both marked COMPLETE in Phase 4
- SequenceMatcher handles 0.50-0.80 similarity range for UPDATE detection
- Title-hash handles exact duplicates

**Alternative approaches (lighter weight):**
1. **Use the AI batch call itself** -- add a "flag potential duplicates" instruction to the system prompt. Claude/Gemini can identify semantic duplicates across the 15-article batch with zero additional dependencies.
2. **TF-IDF + cosine similarity** using scikit-learn (already lightweight, no PyTorch): `TfidfVectorizer` + `cosine_similarity` from sklearn. Adds ~50MB dependency vs ~500MB for sentence-transformers.
3. **Keep SequenceMatcher** -- for a 15-article batch with 7-day history, the O(n*m) string comparison is fast enough (<100ms).

**Recommendation:** If semantic dedup beyond Phase 4's SequenceMatcher is needed, incorporate it into the AI batch prompt (option 1) rather than adding sentence-transformers. This is zero additional cost (already paying for the batch call) and zero additional dependencies.

## Open Questions

1. **Haiku 4.5 vs Sonnet for classification quality**
   - What we know: Haiku 4.5 is 3x cheaper and classified as "near-frontier intelligence" by Anthropic. For structured classification tasks (not creative writing), it performs very well.
   - What's unclear: Whether Haiku's classification matches Sonnet's quality for Indian real estate domain specifics
   - Recommendation: Start with Haiku 4.5 (cheapest), make model name a constant. If quality is insufficient during testing, switch to Sonnet -- still within budget.

2. **Prompt caching minimum for Haiku 4.5 (4,096 tokens)**
   - What we know: Haiku 4.5 requires 4,096+ tokens for prompt caching to activate. A typical system prompt is ~500-1,000 tokens.
   - What's unclear: Whether padding the system prompt to 4,096 tokens (with examples) is worth the complexity
   - Recommendation: Skip prompt caching for Haiku 4.5. At $1/MTok input, caching saves only $0.009/call. Not worth the prompt bloat. If using Sonnet (1,024 min), caching is more valuable.

3. **Gemini environment variable naming**
   - What we know: google-genai reads `GEMINI_API_KEY` by default; deliver.yml has `GOOGLE_API_KEY` commented out
   - What's unclear: Which env var name the user prefers
   - Recommendation: Use `GOOGLE_API_KEY` for consistency with deliver.yml comments, pass explicitly to `genai.Client(api_key=...)`.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.0+ (already configured) |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/test_classifier.py -x` |
| Full suite command | `uv run pytest tests/ -v --tb=short` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| AI-01 | 15 articles classified HIGH/MEDIUM/LOW in single Claude call | unit (mocked API) | `uv run pytest tests/test_classifier.py::TestBatchClassification -x` | No -- Wave 0 |
| AI-02 | Each article has 2-line impact summary | unit (mocked API) | `uv run pytest tests/test_classifier.py::TestSummaryGeneration -x` | No -- Wave 0 |
| AI-05 | Entities extracted (location, project_name, budget, authority) | unit (mocked API) | `uv run pytest tests/test_classifier.py::TestEntityExtraction -x` | No -- Wave 0 |
| AI-06 | Gemini fallback on Claude failure | unit (mocked API) | `uv run pytest tests/test_classifier.py::TestGeminiFallback -x` | No -- Wave 0 |
| AI-07 | Monthly cost tracked, budget gates enforced | unit | `uv run pytest tests/test_cost_tracker.py -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_classifier.py tests/test_cost_tracker.py -x`
- **Per wave merge:** `uv run pytest tests/ -v --tb=short`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_classifier.py` -- covers AI-01, AI-02, AI-05, AI-06 (mocked API responses with respx)
- [ ] `tests/test_cost_tracker.py` -- covers AI-07 (load/save/budget gates)
- [ ] `tests/test_ai_response_schema.py` -- covers Pydantic model validation for batch response
- [ ] `data/ai_cost.json` -- seed file with initial state (like gnews_quota.json pattern)
- [ ] Dependencies: `uv add anthropic google-genai` in pyproject.toml

## Sources

### Primary (HIGH confidence)
- [Anthropic Models Overview](https://platform.claude.com/docs/en/about-claude/models/overview) -- Model names, pricing, context windows
- [Anthropic Pricing](https://platform.claude.com/docs/en/about-claude/pricing) -- Complete token pricing table including cache pricing
- [Anthropic Structured Outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) -- `.parse()` method, Pydantic integration, no beta header needed
- [Anthropic Prompt Caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching) -- cache_control, minimum token thresholds, usage tracking
- [Gemini API Pricing](https://ai.google.dev/gemini-api/docs/pricing) -- Gemini 2.5 Flash pricing, free tier limits
- [Gemini Structured Output](https://ai.google.dev/gemini-api/docs/structured-output) -- response_json_schema with Pydantic
- [google-genai SDK](https://github.com/googleapis/python-genai) -- Official Python SDK, GA status

### Secondary (MEDIUM confidence)
- [anthropic PyPI](https://pypi.org/project/anthropic/) -- Latest version ~0.84.0
- [google-genai PyPI](https://pypi.org/project/google-genai/) -- Latest version ~1.56+
- [sentence-transformers/all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) -- Model size 22MB, repo 977MB total

### Tertiary (LOW confidence)
- Exact PyTorch CPU-only install size on GitHub Actions ubuntu-latest -- estimated ~200-500MB based on community reports

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- verified against official Anthropic and Google documentation
- Architecture: HIGH -- patterns verified with official SDK code examples
- Pitfalls: MEDIUM -- some pitfalls (e.g., prompt caching thresholds) verified with docs, others (e.g., race conditions) are theoretical
- Cost estimates: HIGH -- pricing from official docs, arithmetic verified
- sentence-transformers impact: MEDIUM -- size estimates from community reports, not measured on GitHub Actions

**Research date:** 2026-03-07
**Valid until:** 2026-04-07 (30 days -- stable APIs, pricing may change)
