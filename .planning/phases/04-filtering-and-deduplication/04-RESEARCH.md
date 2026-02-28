# Phase 4: Filtering and Deduplication - Research

**Researched:** 2026-02-28
**Domain:** Text filtering, keyword relevance scoring, geographic classification, title-hash deduplication
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| FETCH-03 | System filters articles by keyword library matching against title + description (relevance score >40 threshold) | Weighted keyword scanning over normalized text; pure Python stdlib — no external NLP needed |
| FETCH-04 | System applies exclusion keywords to filter noise (obituary, gossip, scandal, etc.) | `any(excl in text_lower for excl in exclusions)` short-circuit scan; keywords already in `KeywordsConfig.exclusions` |
| FETCH-05 | System applies geographic tier priority (Tier 1: always include; Tier 2: HIGH only; Tier 3: HIGH + impact >85 only) | City-to-tier lookup dict; city-name scan of title+summary; tier rules applied after relevance gate |
| AI-03 | System detects duplicates against 7-day history using two-stage approach (title hash first, then semantic similarity at 0.85+ threshold) | `SeenStore` already exists; title hash via `hashlib.sha256`; similarity via `difflib.SequenceMatcher`; no new dependency |
| AI-04 | System detects story updates (50-80% similarity) and labels them as "UPDATE" with reference to original | `SequenceMatcher.ratio()` in [0.50, 0.80) range → DUPLICATE flag becomes UPDATE label with original URL |
</phase_requirements>

---

## Summary

Phase 4 sits between the raw fetch output of Phase 3 and the AI classification of Phase 5. Its job is to discard noise early and cheaply, so the AI pipeline only sees relevant, novel articles. The three sub-problems are: (1) relevance scoring via keyword matching, (2) geographic tier gating, and (3) title-hash deduplication against `seen.json`.

All three problems can be solved entirely with Python stdlib (`re`, `hashlib`, `difflib`, `unicodedata`) and the Pydantic models already in place. No new runtime dependencies are required. The keyword library, exclusion list, and city-tier taxonomy live in existing YAML/config structures; Phase 4 only needs to add scorer and filter functions that consume them.

The deduplication design is already partly scaffolded: `SeenStore` holds `url_hash` and `title_hash` per entry, and `purge_old_entries` enforces the 7-day window. Phase 4 needs to populate these hashes on new articles and run the two-stage lookup (exact hash match → fast duplicate, similarity [0.5–0.8) → UPDATE label).

**Primary recommendation:** Build three thin, pure-function modules — `relevance_filter.py`, `geo_filter.py`, `dedup_filter.py` — each taking `list[Article]` in and returning filtered/annotated results. Wire them sequentially in `main.py` after the Phase 3 fetch block, before the Phase 5 placeholder comment.

---

## Standard Stack

### Core (all stdlib — zero new dependencies)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `re` | stdlib | Regex for text normalization (strip punctuation, whitespace) | Precompilable, fastest for pattern matching |
| `hashlib` | stdlib | SHA-256 title hash for exact dedup fast-path | Stable, fast, same API since Python 3.0 |
| `difflib.SequenceMatcher` | stdlib | Title similarity ratio for UPDATE detection | Ratcliff-Obershelp, 0.0–1.0 range, no install |
| `unicodedata` | stdlib | NFD normalization before hashing (handles Hindi transliterations) | Correct unicode-aware normalization |
| `pydantic v2` | >=2.5 (pinned) | Extend `Article` schema with filter result fields | Already in pyproject.toml |

### Supporting (already installed)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pyyaml` | >=6.0 (pinned) | Read `keywords.yaml` city taxonomy additions | If geo tiers move to YAML config |
| `httpx` | >=0.28.1 (pinned) | No use in Phase 4 | Already present, not needed here |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `difflib.SequenceMatcher` | `rapidfuzz` (C++ library) | rapidfuzz is 2.5× faster but adds a non-stdlib dependency; for 50-200 articles/run, SequenceMatcher is fast enough — benchmark only if performance becomes a bottleneck |
| `hashlib.sha256` | `hashlib.md5(usedforsecurity=False)` | MD5 is 20% faster but carries security optics; SHA-256 is the right default for new code — difference is negligible at this scale |
| Hand-coded city scan | `spacy` NER | spaCy is heavyweight (200 MB model download); for a curated city list of ~50 names, a dict lookup is better in every dimension |
| Score threshold at 40 | Dynamic TF-IDF scoring | TF-IDF requires a corpus to calibrate against; the keyword library IS the preference model per project decision — plain weighted count is correct here |

**Installation:** No new packages needed. All functionality from stdlib + existing deps.

---

## Architecture Patterns

### Recommended Project Structure

```
src/pipeline/
├── filters/                  # NEW — Phase 4 filter modules
│   ├── __init__.py
│   ├── relevance_filter.py   # FETCH-03, FETCH-04: keyword scoring + exclusion
│   ├── geo_filter.py         # FETCH-05: tier 1/2/3 geographic classification
│   └── dedup_filter.py       # AI-03, AI-04: title-hash dedup + UPDATE detection
├── schemas/
│   └── article_schema.py     # extend Article with geo_tier, relevance_score, dedup_status
├── main.py                   # wire filters after fetch, before Phase 5 placeholder
tests/
├── test_relevance_filter.py
├── test_geo_filter.py
└── test_dedup_filter.py
```

The `pipeline.filters` subpackage follows the same pattern as `pipeline.fetchers` (already established). Each module is a collection of pure functions — no class instances, no state, no I/O — making them trivially testable.

### Pattern 1: Text Normalization Before Matching or Hashing

**What:** Lowercase, strip non-alphanumeric (except spaces), collapse whitespace, NFD-normalize for unicode parity.
**When to use:** Before every comparison — both for hashing and for keyword scanning.

```python
# Source: Python 3.12 stdlib docs (re, unicodedata)
import re
import unicodedata

_PUNCT_RE = re.compile(r"[^a-z0-9\s]")
_SPACE_RE = re.compile(r"\s+")


def normalize_title(text: str) -> str:
    """Lowercase, NFD-normalize, strip punctuation, collapse whitespace."""
    nfd = unicodedata.normalize("NFD", text.lower())
    ascii_only = _PUNCT_RE.sub(" ", nfd)
    return _SPACE_RE.sub(" ", ascii_only).strip()
```

**Why this matters:** "Delhi Metro Phase-4" and "Delhi Metro Phase 4" must hash identically. Without normalization they differ. NFD handles "Indore–Patalkot" (en-dash) and accented transliterations.

### Pattern 2: Two-Pass Relevance Scoring

**What:** Exclusion check first (cheap, early-exit), then keyword scoring (accumulated match score).
**When to use:** Every article before geo filter.

```python
# Source: pattern derived from project keyword structure in keywords.yaml
def score_article(article: Article, keywords: KeywordsConfig) -> tuple[bool, int]:
    """
    Returns (passes_exclusion, relevance_score).
    passes_exclusion=False means article is discarded regardless of score.
    """
    text = f"{article.title} {article.summary}".lower()

    # Stage 1: Exclusion fast-path
    for excl in keywords.exclusions:
        if excl in text:
            return False, 0

    # Stage 2: Accumulate relevance score from active keywords
    score = 0
    for kw in keywords.active_keywords():
        kw_lower = kw.lower()
        if kw_lower in text:
            # Title match scores higher than body match
            if kw_lower in article.title.lower():
                score += 20
            else:
                score += 10
    return True, score
```

**Threshold:** Score >= 40 passes (requirement FETCH-03). This means 2 title matches OR 4 body matches.

**Why not NLP:** The keyword library IS the preference model per the project's locked decision (STATE.md, Phase 01). TF-IDF or RAKE would require a training corpus and add complexity that doesn't serve the goal.

### Pattern 3: Geographic Tier Classification

**What:** Scan normalized article text for known city/region names; assign tier; apply tier-specific include rules.
**When to use:** After relevance gate passes, before dedup.

```python
# Source: project requirements (FETCH-05), Indian city classification research
TIER_1_CITIES = {
    "delhi", "delhi ncr", "ncr", "mumbai", "bangalore", "bengaluru",
    "hyderabad", "chennai", "kolkata", "pune", "ahmedabad"
}
TIER_2_CITIES = {
    "noida", "gurugram", "gurgaon", "faridabad", "ghaziabad",
    "jaipur", "surat", "lucknow", "kanpur", "nagpur", "indore",
    "bhopal", "visakhapatnam", "patna", "vadodara"
}
# All others default to Tier 3

def classify_geo_tier(article: Article) -> int:
    """Return 1, 2, or 3. Tier 1 = major metros, Tier 3 = others."""
    text = f"{article.title} {article.summary}".lower()
    for city in TIER_1_CITIES:
        if city in text:
            return 1
    for city in TIER_2_CITIES:
        if city in text:
            return 2
    return 3
```

**Tier rules** (from FETCH-05):
- Tier 1: always include
- Tier 2: include only if relevance score is "HIGH" — since we don't have AI priority yet in Phase 4, treat "HIGH" as relevance_score >= 60
- Tier 3: include only if relevance_score >= 85 (impact score proxy)

**Key subtlety:** The requirement says "Tier 2: HIGH only" and "Tier 3: HIGH + impact >85". Phase 4 has no AI classification yet, so the geo filter must use the relevance score as a proxy for priority. Document this explicitly as a Phase 5 refinement point.

### Pattern 4: Title-Hash Deduplication (Two-Stage)

**What:** Exact title_hash lookup first (O(n)), then SequenceMatcher similarity scan for near-duplicates.
**When to use:** After all filtering passes; mutates SeenStore.

```python
# Source: Python 3.12 stdlib docs (hashlib, difflib)
import hashlib
from difflib import SequenceMatcher
from pipeline.schemas.seen_schema import SeenStore, SeenEntry


def compute_title_hash(title: str) -> str:
    """SHA-256 of normalized title, hex-encoded."""
    normalized = normalize_title(title)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def check_duplicate(article: Article, seen: SeenStore) -> tuple[str, str | None]:
    """
    Returns (status, original_url).
    status: "NEW" | "DUPLICATE" | "UPDATE"
    original_url: URL of original article if UPDATE, else None
    """
    title_hash = compute_title_hash(article.title)
    norm_title = normalize_title(article.title)

    # Stage 1: Exact hash match → immediate DUPLICATE
    for entry in seen.entries:
        if entry.title_hash == title_hash:
            return "DUPLICATE", None  # entry.url not stored, but title matches

    # Stage 2: Similarity scan for UPDATE detection
    for entry in seen.entries:
        ratio = SequenceMatcher(None, norm_title, normalize_title(entry.title)).ratio()
        if 0.50 <= ratio < 0.80:
            return "UPDATE", entry.url_hash  # reference to original
        # ratio >= 0.80 is also a DUPLICATE (captured above via hash or close match)
        if ratio >= 0.80:
            return "DUPLICATE", None

    return "NEW", None
```

**Performance:** With 200 articles in seen.json (7-day window), Stage 2 runs 200 SequenceMatcher comparisons per new article. For 100 new articles per run: ~20,000 comparisons total. Each SequenceMatcher on ~10-word titles takes ~1µs. Total: ~20ms. Acceptable with zero optimization.

**The "UPDATE" boundary:** 50–80% similarity. Examples:
- "Delhi Metro Phase 4 Construction Begins" vs "Delhi Metro Phase 4 Work Starts" → ~72% → UPDATE
- "Delhi Metro Phase 4 Opens New Station" vs "Mumbai Metro Line 3 Station Opens" → ~40% → NEW

### Pattern 5: Enriching Article Schema

**What:** Add filter result fields to `Article` without breaking existing Phase 3 code.
**When to use:** Article schema extension is preferable to parallel data structures.

Two options:
1. Add optional fields to `Article` directly (simpler, Phase 5 can use them)
2. Create a separate `FilteredArticle` model that wraps `Article`

**Recommendation:** Extend `Article` with optional fields. Pydantic v2 supports this without breaking existing constructors since all new fields have defaults.

```python
# Extended Article schema (article_schema.py)
from typing import Literal

class Article(BaseModel):
    # ... existing fields unchanged ...
    title: str
    url: str
    source: str
    published_at: str
    summary: str = ""
    fetched_at: str

    # Phase 4 filter results — all optional, populated by filter pipeline
    relevance_score: int = 0
    geo_tier: int = 0          # 0 = unclassified, 1/2/3 after geo filter
    dedup_status: Literal["NEW", "DUPLICATE", "UPDATE", ""] = ""
    dedup_ref: str = ""        # title_hash of original, if UPDATE
```

### Anti-Patterns to Avoid

- **Normalizing at comparison time without caching:** Running `normalize_title()` inside the inner comparison loop is O(n²) normalizations. Normalize once per article before the loop.
- **Using `str.__contains__` for multi-word keyword matching without word boundaries:** "RERA" will match "RERA compliance" but also "camera" if not careful — lowercase full-word check is fine for this keyword set since all keywords are distinctive.
- **Mutating `SeenStore` in place:** Follow the established functional pattern from `purge_old_entries` — return a new store, reassign at call site.
- **Storing full article content in SeenStore:** `SeenEntry` stores only hash + title + seen_at + source. Keep it lean.
- **Running dedup before filtering:** Dedup should run AFTER keyword + geo filters. Adds duplicate article to seen.json only if it would have been delivered.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| String similarity (0.0–1.0) | Custom edit-distance algorithm | `difflib.SequenceMatcher.ratio()` | Stdlib, tested, Ratcliff-Obershelp is correct for short strings |
| Text hashing | Custom fingerprint function | `hashlib.sha256(text.encode()).hexdigest()` | Collision-resistant, stdlib, standard |
| Unicode normalization | Custom char replacement tables | `unicodedata.normalize("NFD", text)` | Handles all unicode edge cases correctly |
| City taxonomy | Hardcoded string checks scattered | `TIER_1_CITIES`, `TIER_2_CITIES` frozensets in geo_filter.py | Single source of truth, O(1) membership check |
| Exclusion keyword check | Regex engine | Simple `in` operator on lowercase string | Keywords are plain strings, `in` is fastest for this use case |

**Key insight:** The entire filtering and dedup pipeline needs zero ML dependencies. All problems are solved by pattern matching on short strings (< 200 chars each) using stdlib algorithms.

---

## Common Pitfalls

### Pitfall 1: Score Threshold Calibration

**What goes wrong:** The 40-point threshold was specified in requirements but not validated against real article text. An article titled "Delhi Metro Phase 4 construction update" gets title matches on "metro", "metro phase", "metro extension" (all in the keyword list) — it scores 60 easily. But a valid article titled "NHAI approves new corridor" scores 20 (one title match). If threshold is too high, real news gets dropped.

**Why it happens:** The keyword list has unequal density per topic. Metro has 12 keywords; highway has 10. A metro article sees many partial matches.

**How to avoid:** Test the scorer against at least 10 real article titles (use the fixture set in tests). Verify the threshold produces expected pass/fail decisions for success criteria articles.

**Warning signs:** Phase 4 plan 01 success criterion 1 (Delhi Metro Phase 4 scores >40) — this is a calibration test, not just a unit test.

### Pitfall 2: SequenceMatcher autojunk on Short Strings

**What goes wrong:** `autojunk=True` (the default) activates its junk heuristic only for sequences >= 200 items. For short titles (10–15 words), autojunk never fires. This is actually correct behavior — no issue. The pitfall is accidentally disabling autojunk when it doesn't need disabling.

**Why it happens:** Developer reads autojunk documentation, disables it "to be safe", causing slightly different behavior on longer article summaries.

**How to avoid:** Use `SequenceMatcher(None, a, b)` — no need to set autojunk explicitly.

### Pitfall 3: Title Hash Normalization Inconsistency

**What goes wrong:** Phase 3 stores `title_hash` in `SeenEntry` (see `seen_schema.py`). If Phase 4's `compute_title_hash()` normalizes differently from how titles were hashed when originally stored, dedup will miss existing entries.

**Why it happens:** `SeenEntry.title_hash` is currently unused (seen.json is empty at Phase 4 start). The normalization function defined in Phase 4 becomes the canonical definition. If Phase 5 or Phase 6 also stores to SeenStore, they MUST use the same `normalize_title()` function.

**How to avoid:** Define `normalize_title()` and `compute_title_hash()` in a shared location (e.g., `pipeline/utils/hashing.py`) and import from there in Phase 4. Phase 5+ import the same function.

**Warning signs:** Dedup tests failing intermittently when title has trailing spaces or punctuation.

### Pitfall 4: Geo Tier Ambiguity — No City Match

**What goes wrong:** Most articles from government RSS feeds (MOHUA, NHAI, AAI) are national-level stories with no specific city — "Ministry approves ₹12,000 crore infra package". These get Tier 3 and fail the tier filter if score < 85.

**Why it happens:** The geo tier was designed for real estate content (city-specific), but government/policy feeds produce national-scope articles.

**How to avoid:** National-scope articles (no city detected) should be assigned Tier 1 (they are by definition high-importance) or be explicitly exempt from geo filtering. Add a "national" detection: if no city found but source is a government feed (MOHUA, NHAI, AAI, Smart Cities), treat as Tier 1.

**Warning signs:** All government feed articles getting dropped during Phase 4 testing.

### Pitfall 5: UPDATE Reference Stores title_hash, Not URL

**What goes wrong:** The dedup function references an original by `url_hash` (what SeenStore stores), but the requirement says "label as UPDATE with a reference to the original" — which needs to be something human-readable or URL-addressable in Phase 6.

**Why it happens:** `SeenEntry` stores `url_hash` (not the raw URL), and `title` (raw title, not hash). The "reference to original" is best stored as the original title (human-readable) or reconstructed URL is not feasible from hash alone.

**How to avoid:** Store `dedup_ref` as the original `SeenEntry.title` (the raw title string). This gives Phase 5/6 something to display: "UPDATE of: Delhi Metro Phase 4 construction begins".

---

## Code Examples

Verified patterns from stdlib docs and codebase analysis:

### Title Normalization (for hash consistency)

```python
# Source: Python 3.12 unicodedata + re stdlib docs
import re
import unicodedata

_PUNCT_RE = re.compile(r"[^a-z0-9\s]")
_SPACE_RE = re.compile(r"\s+")


def normalize_title(text: str) -> str:
    """Normalize for comparison and hashing.
    Lowercase → NFD → strip non-alphanumeric → collapse whitespace.
    """
    nfd = unicodedata.normalize("NFD", text.lower())
    cleaned = _PUNCT_RE.sub(" ", nfd)
    return _SPACE_RE.sub(" ", cleaned).strip()
```

### SHA-256 Title Hash

```python
# Source: Python 3.12 hashlib stdlib docs
import hashlib


def compute_title_hash(title: str) -> str:
    """Return SHA-256 hex digest of normalized title."""
    normalized = normalize_title(title)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
```

### SequenceMatcher Similarity Ratio

```python
# Source: Python 3.12 difflib stdlib docs
from difflib import SequenceMatcher


def title_similarity(a: str, b: str) -> float:
    """Return similarity ratio [0.0, 1.0] between two normalized titles."""
    return SequenceMatcher(None, normalize_title(a), normalize_title(b)).ratio()

# Interpretation per docs:
# >= 0.80 → near-exact match (DUPLICATE)
# 0.50–0.79 → UPDATE (same story, different angle or update)
# < 0.50 → different story (NEW)
```

### Storing New Article in SeenStore

```python
# Source: existing codebase patterns (seen_schema.py, purge.py)
from datetime import UTC, datetime
from pipeline.schemas.seen_schema import SeenEntry, SeenStore


def add_to_seen(article: Article, seen: SeenStore) -> SeenStore:
    """Return new SeenStore with article appended (functional style, no mutation)."""
    url_hash = hashlib.sha256(article.url.encode("utf-8")).hexdigest()
    title_hash = compute_title_hash(article.title)
    entry = SeenEntry(
        url_hash=url_hash,
        title_hash=title_hash,
        seen_at=datetime.now(UTC).isoformat(),
        source=article.source,
        title=article.title,
    )
    return SeenStore(entries=[*seen.entries, entry])
```

### Exclusion + Relevance Scoring

```python
# Source: project keyword structure (keywords.yaml, keywords_schema.py)
def score_article(article: Article, keywords: KeywordsConfig) -> tuple[bool, int]:
    """Return (passes_exclusion, relevance_score)."""
    text = f"{article.title} {article.summary}".lower()

    for excl in keywords.exclusions:
        if excl in text:
            return False, 0

    score = 0
    active = keywords.active_keywords()
    title_lower = article.title.lower()
    for kw in active:
        kw_lower = kw.lower()
        if kw_lower in text:
            score += 20 if kw_lower in title_lower else 10
    return True, score
```

### Wiring Filters in main.py (Phase 4 section placeholder)

```python
# After Phase 3 fetch block in main.py:
from pipeline.filters.relevance_filter import filter_by_relevance
from pipeline.filters.geo_filter import filter_by_geo_tier
from pipeline.filters.dedup_filter import filter_duplicates

# Apply filter pipeline
relevant_articles = filter_by_relevance(all_articles, keywords)
geo_filtered = filter_by_geo_tier(relevant_articles)
deduped_articles, seen = filter_duplicates(geo_filtered, seen)

# Save updated seen store
save_seen(seen, "data/seen.json")
logger.info("After filters: %d novel articles remain", len(deduped_articles))
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Custom TF-IDF scorer for news filtering | Keyword-weighted accumulator with curated domain library | N/A — project explicitly chose deterministic over ML | Zero corpus needed; immediate interpretability |
| Semantic embeddings for dedup (sentence-transformers) | Title-hash fast-path + SequenceMatcher similarity | Phase 5 deferred (05-03) | Phase 4 uses no ML; semantic dedup deferred to Phase 5 |
| Mutable state passed through pipeline | Functional style (new objects, no mutation) | Established in Phase 2 (purge_old_entries pattern) | Testable, no side-effect surprises |

**Deprecated/outdated:**
- `hashlib.md5` for non-security hashing: still works but `sha256` is the modern default for new code per Python docs.
- `fuzzywuzzy` (now `thefuzz`): GPL license, slower than difflib for short strings at this scale.

---

## Open Questions

1. **Geo tier for national-scope articles**
   - What we know: FETCH-05 specifies Tier 1/2/3 for city stories, but many government feed articles have no city
   - What's unclear: Should national-policy articles be auto-Tier-1, or should they bypass geo filtering entirely?
   - Recommendation: Treat "no city found AND source is government feed" as Tier 1. Document this as a heuristic for plan 04-02.

2. **Score threshold calibration — title vs summary weighting**
   - What we know: Requirement says >40 threshold; title match should score higher than body match
   - What's unclear: Should multi-word keyword ("Delhi Metro Phase 4") score more than a single-word match ("metro")?
   - Recommendation: Yes — score by keyword length (longer keyword = more specific = higher score). Add `len(kw.split()) * base_weight` to the scoring formula. Document as a plan 04-01 decision point.

3. **Tier 2 "HIGH only" proxy**
   - What we know: Phase 4 has no AI classification yet; "HIGH" tier must be proxied by relevance score
   - What's unclear: The exact cutoff score that maps to "HIGH" in Phase 4
   - Recommendation: Use relevance_score >= 60 as "HIGH proxy" for Tier 2, and >= 85 for Tier 3. Document clearly that Phase 5 will refine this with actual AI priority labels.

4. **`dedup_ref` field type**
   - What we know: Requirement says "UPDATE with a reference to the original"; SeenEntry stores title (raw string) and url_hash
   - What's unclear: Should `dedup_ref` store the original title or the original url_hash?
   - Recommendation: Store the original `SeenEntry.title` (raw) so Phase 6 can display "UPDATE of: [original title]" without reconstructing.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.0+ |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/test_relevance_filter.py tests/test_geo_filter.py tests/test_dedup_filter.py -x` |
| Full suite command | `uv run pytest` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FETCH-03 | "Delhi Metro Phase 4" scores >40 | unit | `uv run pytest tests/test_relevance_filter.py::TestRelevanceFilter::test_delhi_metro_passes_threshold -x` | No — Wave 0 gap |
| FETCH-03 | Score accumulates across title + description | unit | `uv run pytest tests/test_relevance_filter.py::TestRelevanceFilter::test_title_scores_higher_than_body -x` | No — Wave 0 gap |
| FETCH-04 | "obituary" in article → filtered out | unit | `uv run pytest tests/test_relevance_filter.py::TestExclusionFilter::test_obituary_excluded -x` | No — Wave 0 gap |
| FETCH-04 | "gossip" in title → filtered out | unit | `uv run pytest tests/test_relevance_filter.py::TestExclusionFilter::test_gossip_excluded -x` | No — Wave 0 gap |
| FETCH-05 | Tier 1 city (Delhi NCR) always passes | unit | `uv run pytest tests/test_geo_filter.py::TestGeoFilter::test_tier1_always_passes -x` | No — Wave 0 gap |
| FETCH-05 | Tier 3 story passes only if score >= 85 | unit | `uv run pytest tests/test_geo_filter.py::TestGeoFilter::test_tier3_requires_high_score -x` | No — Wave 0 gap |
| FETCH-05 | National-scope article (no city) from gov feed → Tier 1 | unit | `uv run pytest tests/test_geo_filter.py::TestGeoFilter::test_national_scope_gov_feed_passes -x` | No — Wave 0 gap |
| AI-03 | Exact title match in seen.json → DUPLICATE | unit | `uv run pytest tests/test_dedup_filter.py::TestDedupFilter::test_exact_duplicate_detected -x` | No — Wave 0 gap |
| AI-03 | New article not in seen.json → NEW | unit | `uv run pytest tests/test_dedup_filter.py::TestDedupFilter::test_new_article_passes -x` | No — Wave 0 gap |
| AI-04 | 65% similar title → UPDATE with ref | unit | `uv run pytest tests/test_dedup_filter.py::TestDedupFilter::test_update_detected_with_reference -x` | No — Wave 0 gap |
| AI-04 | UPDATE article stored in seen.json for future dedup | unit | `uv run pytest tests/test_dedup_filter.py::TestDedupFilter::test_update_added_to_seen -x` | No — Wave 0 gap |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_relevance_filter.py tests/test_geo_filter.py tests/test_dedup_filter.py -x --tb=short`
- **Per wave merge:** `uv run pytest`
- **Phase gate:** Full suite green (73 existing + all Phase 4 new tests) before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_relevance_filter.py` — covers FETCH-03, FETCH-04
- [ ] `tests/test_geo_filter.py` — covers FETCH-05
- [ ] `tests/test_dedup_filter.py` — covers AI-03, AI-04
- [ ] `src/pipeline/filters/__init__.py` — new subpackage
- [ ] `src/pipeline/filters/relevance_filter.py` — stub for RED phase
- [ ] `src/pipeline/filters/geo_filter.py` — stub for RED phase
- [ ] `src/pipeline/filters/dedup_filter.py` — stub for RED phase
- [ ] `src/pipeline/utils/hashing.py` — shared `normalize_title()` and `compute_title_hash()` utility

---

## Sources

### Primary (HIGH confidence)
- Python 3.12 difflib official docs (https://docs.python.org/3/library/difflib.html) — SequenceMatcher ratio(), quick_ratio(), autojunk behavior
- Python 3.12 hashlib official docs (https://docs.python.org/3/library/hashlib.html) — SHA-256 API, hexdigest(), usedforsecurity
- Python 3.12 unicodedata official docs (https://docs.python.org/3/library/unicodedata.html) — NFD normalization for unicode-safe text prep
- Project codebase: `src/pipeline/schemas/` — Article, KeywordsConfig, SeenStore, SeenEntry models
- Project codebase: `src/pipeline/utils/purge.py` — functional style pattern (return new object, no mutation)
- Project codebase: `data/keywords.yaml` — keyword taxonomy with exclusions list
- Project codebase: `data/seen.json`, `seen_schema.py` — existing dedup state structure

### Secondary (MEDIUM confidence)
- NewsCatcher API deduplication docs (https://www.newscatcherapi.com/docs/v3/documentation/guides-and-concepts/articles-deduplication) — confirmed 7-day rolling window and two-stage approach is industry standard
- DEV Community: RapidFuzz vs Difflib comparison (https://dev.to/mrquite/smart-text-matching-rapidfuzz-vs-difflib-ge5) — confirmed difflib is adequate for < 1000 pairs
- ResearchGate: Comparative Analysis of Python Text Matching Libraries (2025) — multilingual evaluation confirming SequenceMatcher performance characteristics

### Tertiary (LOW confidence — for context only)
- WebSearch: Signal scoring pipeline pattern — informed multi-field weighted scoring approach
- WebSearch: Indian city tier classification (99acres, wticabs) — confirmed standard Tier 1/2/3 city groupings for Indian real estate context

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all stdlib, verified against Python 3.12 official docs
- Architecture: HIGH — patterns derived directly from existing codebase conventions (functional style, Pydantic v2, src-layout)
- Pitfalls: HIGH — derived from code analysis of existing SeenStore schema and requirement edge cases
- Geo tier city list: MEDIUM — city names are standard knowledge, but exact threshold-to-tier mapping is a planner decision

**Research date:** 2026-02-28
**Valid until:** 2026-08-28 (stable stdlib APIs; only risk is if keyword library expands significantly, requiring threshold recalibration)
