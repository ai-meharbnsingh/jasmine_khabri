# Phase 1: Project Scaffold - Research

**Researched:** 2026-02-27
**Domain:** Python project scaffolding — uv package management, src-layout packaging, YAML/JSON schema validation, dev tooling
**Confidence:** HIGH

## Summary

Phase 1 establishes the foundational scaffold that every subsequent phase builds on. The domain is well-understood Python project setup using the modern `uv` toolchain. The key decisions are already locked (YAML for config/keywords, JSON for seen/history, `pipeline` as the importable package name), and the research confirms these are sound choices with clear implementation paths.

The primary complexity is not technical difficulty but rather **getting the package structure right from the start**: if the `src/` layout and `pyproject.toml` build system declaration are done correctly, all future imports will work. If they are wrong, every future phase will encounter import errors that are painful to debug.

For schema validation, Pydantic v2 is the clear standard for 2025/2026 Python projects: faster than jsonschema, Python-native type hints, excellent error messages, and directly supports loading YAML via `yaml.safe_load()` + `model_validate()`. No additional library (`pydantic-yaml`) is needed for this project's use case.

**Primary recommendation:** Use `uv init --package` for the src-layout Python package, define Pydantic v2 models for all three data files (config.yaml, keywords.yaml, seen.json), and configure ruff + pytest entirely within `pyproject.toml`.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Default keyword library:** Ship the FULL keyword library from the blueprint in keywords.yaml, but only two categories active by default: Infrastructure and Regulatory (RERA/PMAY). Celebrity and Transaction keyword categories are present in the file but marked as `active: false`. Users can enable disabled categories later via the Telegram bot (Phase 9). Start with a focused set of ~30-40 active keywords across Infrastructure + Regulatory, not the full 80+.
- **Config defaults:** Both delivery channels (Telegram + Gmail email) active from day one. Default schedule: 7 AM IST (morning) and 4 PM IST (evening). Both user Telegram chat IDs configured for delivery. Breaking news alerts: enabled by default. Max stories per delivery: 15.
- **Data file format:** Use YAML (not JSON) for config.yaml and keywords.yaml — human-readable, easy to edit manually. seen.json remains JSON — programmatic only, never hand-edited. history.json remains JSON — same reasoning.

### Claude's Discretion
- Python package structure and module naming
- Exact YAML schema design for config and keywords
- Dev tooling choices (ruff config, pytest config, pre-commit hooks)
- Dependency versions and lockfile strategy
- .gitignore contents beyond secrets

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| INFRA-01 | System runs on GitHub Actions with UTC cron schedules correctly mapped to IST delivery times | The scaffold sets up the Python package that GitHub Actions will invoke; the schedule config structure (IST times stored in config.yaml, UTC conversion in code) must be defined in the schema this phase |
| INFRA-02 | System stores mutable state (seen articles, config, keywords) as JSON/YAML files committed back to repo | Defines the data file locations, schemas, and validation models — seen.json, config.yaml, keywords.yaml all live in `data/` and are loaded/validated by Pydantic models in this phase |
| INFRA-06 | System operates within free tier limits (Railway $5/month credit for bot, $0 GitHub Actions, <$5/month AI API) | The scaffold must NOT introduce paid dependencies; all dev tooling (uv, ruff, pytest) and runtime libraries selected in this phase must be free/open source |
</phase_requirements>

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| uv | latest (≥0.4) | Package manager, virtualenv, lockfile | Industry standard 2025; 10-100x faster than pip; manages Python version too |
| Python | 3.12+ | Runtime | Latest stable with `tomllib` built-in, better type hints, faster |
| pydantic | v2.x (≥2.5) | Schema validation for all data files | 3.5x faster than jsonschema; Python-native models; excellent errors; already the standard for 2025/2026 |
| PyYAML | ≥6.0 | Load YAML files before Pydantic validation | Standard YAML loader; `yaml.safe_load()` is the secure default |
| pytest | ≥8.x | Test runner | Standard Python test framework; configured in pyproject.toml |
| ruff | latest (≥0.9) | Linter + formatter (replaces flake8, black, isort) | Rust-based; 100x faster; single tool replaces entire toolchain |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pre-commit | ≥3.x | Git hooks for ruff checks | When committing code; enforces quality at commit time |
| pytest-cov | ≥5.x | Coverage reporting | When running full test suite |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| PyYAML | ruamel.yaml | ruamel.yaml preserves comments and round-trips; overkill since we only read YAML, never write it back programmatically |
| PyYAML | strictyaml | Safer YAML parsing; but more setup complexity than needed here |
| pydantic v2 | jsonschema | jsonschema is cross-language but 3.5x slower; Pydantic is strictly better for a Python-only project |
| pydantic v2 | pydantic-yaml | An extra library — not needed; `yaml.safe_load()` + `model_validate()` is all we need |
| ruff | flake8 + black + isort | Three tools vs one; ruff is strictly better |

**Installation:**
```bash
# Runtime (in pyproject.toml [project.dependencies])
uv add pydantic PyYAML

# Dev (in pyproject.toml [dependency-groups])
uv add --dev pytest pytest-cov ruff pre-commit
```

---

## Architecture Patterns

### Recommended Project Structure
```
khabri/                        # repo root
├── pyproject.toml             # SINGLE config file: uv, pytest, ruff, package metadata
├── uv.lock                    # committed to repo — reproducible installs
├── .python-version            # "3.12" — uv reads this
├── .pre-commit-config.yaml    # ruff-check + ruff-format hooks
├── .gitignore                 # updated this phase
├── README.md                  # project readme
│
├── src/
│   └── pipeline/              # the importable package
│       ├── __init__.py        # version string here
│       ├── fetchers/
│       │   ├── __init__.py
│       │   └── rss_fetcher.py      # placeholder module (Phase 3)
│       ├── analyzers/
│       │   ├── __init__.py
│       │   └── classifier.py       # placeholder module (Phase 5)
│       ├── deliverers/
│       │   ├── __init__.py
│       │   └── telegram_sender.py  # placeholder module (Phase 6)
│       ├── bot/
│       │   ├── __init__.py
│       │   └── handler.py          # placeholder module (Phase 8)
│       ├── schemas/
│       │   ├── __init__.py
│       │   ├── config_schema.py    # Pydantic model for config.yaml
│       │   ├── keywords_schema.py  # Pydantic model for keywords.yaml
│       │   └── seen_schema.py      # Pydantic model for seen.json
│       └── utils/
│           ├── __init__.py
│           └── loader.py           # load_config(), load_keywords(), load_seen()
│
├── data/
│   ├── config.yaml            # COMMITTED — human-editable config
│   ├── keywords.yaml          # COMMITTED — full keyword library, 2 active categories
│   ├── seen.json              # COMMITTED empty — runtime state (gitignored content)
│   └── history.json           # COMMITTED empty — runtime state (gitignored content)
│
└── tests/
    ├── conftest.py            # shared fixtures
    └── test_schemas.py        # schema validation tests (Phase 1 deliverable)
```

**Important naming note:** The success criterion uses `from pipeline.fetchers import rss_fetcher` — so the package is named `pipeline` (not `khabri`). The repo/project is `khabri` but the importable package is `pipeline`.

### Pattern 1: src Layout with uv Package Declaration

**What:** Code lives in `src/pipeline/` and the `pyproject.toml` declares a build system, making the package installable. uv installs it in editable mode automatically.

**When to use:** Any project where you want `from pipeline.x import y` to work reliably — prevents the "working directory import" trap where Python accidentally imports from the wrong location.

**Example:**
```toml
# pyproject.toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "khabri"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "pydantic>=2.5",
    "PyYAML>=6.0",
]

[tool.hatch.build.targets.wheel]
packages = ["src/pipeline"]

[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "ruff>=0.9",
    "pre-commit>=3.0",
]
```

**Why hatchling:** uv's default build backend. Zero configuration for the common case. Can be replaced with setuptools if needed later.

### Pattern 2: Pydantic v2 Schema Validation for YAML/JSON

**What:** Load YAML/JSON files with standard library tools, validate against Pydantic models.

**When to use:** All three data files (config.yaml, keywords.yaml, seen.json).

**Example:**
```python
# Source: pydantic.dev/latest + verified pattern
import json
import yaml
from pydantic import BaseModel, Field

# config.yaml schema
class ScheduleConfig(BaseModel):
    morning_ist: str = "07:00"   # "HH:MM" in IST
    evening_ist: str = "16:00"   # "HH:MM" in IST

class TelegramConfig(BaseModel):
    chat_ids: list[str]
    breaking_news_enabled: bool = True

class EmailConfig(BaseModel):
    enabled: bool = True

class AppConfig(BaseModel):
    schedule: ScheduleConfig = Field(default_factory=ScheduleConfig)
    telegram: TelegramConfig
    email: EmailConfig
    max_stories_per_delivery: int = Field(default=15, ge=1, le=50)

def load_config(path: str = "data/config.yaml") -> AppConfig:
    with open(path) as f:
        raw = yaml.safe_load(f)
    return AppConfig.model_validate(raw)
```

**For seen.json (array of article hashes):**
```python
class SeenEntry(BaseModel):
    url_hash: str
    title_hash: str
    seen_at: str  # ISO 8601
    source: str

class SeenStore(BaseModel):
    entries: list[SeenEntry] = Field(default_factory=list)

def load_seen(path: str = "data/seen.json") -> SeenStore:
    try:
        with open(path) as f:
            raw = json.load(f)
        return SeenStore.model_validate(raw)
    except FileNotFoundError:
        return SeenStore()
```

### Pattern 3: keywords.yaml with Category active Flag

**What:** YAML structure where each category has an `active` boolean, allowing the Telegram bot to toggle categories in Phase 9.

**Example:**
```yaml
# data/keywords.yaml
categories:
  infrastructure:
    active: true
    keywords:
      - metro
      - metro rail
      - NHAI
      - highway
      - expressway
      - airport
      # ... ~20 keywords
  regulatory:
    active: true
    keywords:
      - RERA
      - MahaRERA
      - PMAY
      - Pradhan Mantri Awas Yojana
      # ... ~15 keywords
  celebrity:
    active: false
    keywords:
      - Amitabh Bachchan
      - Shah Rukh Khan
      # ... full list, inactive
  transaction:
    active: false
    keywords:
      - luxury apartment
      - penthouse
      # ... full list, inactive
exclusions:
  - obituary
  - scandal
  - gossip
  - horoscope
```

**Corresponding Pydantic model:**
```python
class KeywordCategory(BaseModel):
    active: bool
    keywords: list[str]

class KeywordsConfig(BaseModel):
    categories: dict[str, KeywordCategory]
    exclusions: list[str] = Field(default_factory=list)

    def active_keywords(self) -> list[str]:
        """Return all keywords from active categories."""
        result = []
        for cat in self.categories.values():
            if cat.active:
                result.extend(cat.keywords)
        return result
```

### Pattern 4: pytest Configuration in pyproject.toml

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v --tb=short"
```

### Pattern 5: ruff Configuration in pyproject.toml

```toml
[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP"]  # pycodestyle, pyflakes, isort, pyupgrade
ignore = []

[tool.ruff.format]
quote-style = "double"
```

### Anti-Patterns to Avoid

- **Flat layout without build system:** `from pipeline.fetchers import rss_fetcher` will fail intermittently depending on working directory. Always use src layout + `[build-system]` in pyproject.toml.
- **Not committing uv.lock:** Breaks reproducibility — future phases (especially CI) need exact dependency versions.
- **Separate config files (pytest.ini, .flake8, setup.cfg):** All configuration belongs in `pyproject.toml` for this project. One file to rule them all.
- **Writing seen.json/history.json by hand in .gitignore:** The DATA files should be committed (they ARE the state store for INFRA-02). Only their generated content is excluded — but actually for this project both files are committed on every run. Do NOT gitignore seen.json or history.json.
- **Using `json.dumps` without indent:** Makes seen.json/history.json unreadable when diffed in GitHub. Use `json.dumps(data, indent=2, ensure_ascii=False)`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| YAML loading + validation | Custom parser | `yaml.safe_load()` + Pydantic | Edge cases in YAML: anchors, type coercion, null handling |
| Import path management | sys.path manipulation | src layout + `uv install -e` | The src layout + build backend handles this correctly |
| Type checking at load time | Manual isinstance checks | Pydantic Field validators | Pydantic generates clear ValidationError with field paths |
| Dependency locking | requirements.txt | uv.lock | uv.lock is cross-platform and handles transitive deps |
| Linting + formatting | Custom scripts | ruff | Covers 900+ rules, 100x faster than alternatives |

**Key insight:** The schema validation layer (Pydantic models in `pipeline/schemas/`) is the single source of truth for data shape — every module that reads a data file MUST go through these models, never raw dict access. This prevents the "works in dev, breaks in CI" category of bugs.

---

## Common Pitfalls

### Pitfall 1: Package Not Importable After `uv sync`

**What goes wrong:** Running `from pipeline.fetchers import rss_fetcher` gives `ModuleNotFoundError` even after `uv sync`.

**Why it happens:** The `pyproject.toml` is missing the `[build-system]` table, so uv treats the project as an "app" (not a package) and does not install the `pipeline` package into the venv.

**How to avoid:** Always include `[build-system]` with `requires = ["hatchling"]` and `build-backend = "hatchling.build"`. Verify with `uv pip show khabri` — if it shows the package, imports will work.

**Warning signs:** `uv sync` completes but `python -c "from pipeline.fetchers import rss_fetcher"` fails.

### Pitfall 2: uv.lock Not Committed

**What goes wrong:** A fresh `uv sync` on CI installs different (potentially incompatible) versions of transitive dependencies.

**Why it happens:** Without uv.lock, uv resolves the latest compatible versions — which may differ from development.

**How to avoid:** Commit uv.lock. Add a CI check: `uv lock --check` (exits non-zero if lockfile is stale).

**Warning signs:** Tests pass locally but fail on GitHub Actions with mysterious import errors or API incompatibilities.

### Pitfall 3: config.yaml Missing Required Fields

**What goes wrong:** Pydantic raises `ValidationError` at startup with a cryptic field path error.

**Why it happens:** The committed config.yaml is missing a newly added required field, or a field type changed.

**How to avoid:** All required fields in Pydantic models MUST have defaults, OR the config.yaml template must be committed with all required fields pre-filled. For this project: give all config fields sensible defaults so that a minimal config.yaml still validates.

**Warning signs:** `ValidationError: 1 validation error for AppConfig` at startup.

### Pitfall 4: YAML Type Coercion Surprises

**What goes wrong:** A schedule time like `07:00` in YAML is parsed as an integer or float (0 in some cases) instead of a string.

**Why it happens:** YAML's type inference converts `07:00` to a sexagesimal number in older YAML 1.1 parsers.

**How to avoid:** Quote time values in YAML: `morning_ist: "07:00"`. Use `yaml.safe_load()` (not `yaml.load()` which uses the full YAML loader).

**Warning signs:** `morning_ist` field has value `420` (7 * 60) instead of `"07:00"`.

### Pitfall 5: seen.json and history.json Accidentally Gitignored

**What goes wrong:** The state files are excluded from git, so GitHub Actions can't commit them back in Phase 2.

**Why it happens:** The current `.gitignore` already excludes `data/sent_news.json` and `data/history.json` — but INFRA-02 requires these files be committed to the repo.

**How to avoid:** Remove `data/history.json` from `.gitignore`. The files should be committed. Only the `.env` and secrets should be excluded.

**Warning signs:** `git status` shows `data/history.json` as untracked but not showing in `git add .` output.

---

## Code Examples

### Minimal pyproject.toml for This Project

```toml
# Source: docs.astral.sh/uv/concepts/projects/config/
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "khabri"
version = "0.1.0"
description = "Automated infrastructure and real estate news pipeline"
requires-python = ">=3.12"
dependencies = [
    "pydantic>=2.5",
    "PyYAML>=6.0",
]

[tool.hatch.build.targets.wheel]
packages = ["src/pipeline"]

[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "ruff>=0.9",
    "pre-commit>=3.0",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v --tb=short"

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP"]

[tool.ruff.format]
quote-style = "double"
```

### Schema Validation Test (conftest.py + test_schemas.py)

```python
# tests/conftest.py
import pytest
from pathlib import Path

@pytest.fixture
def data_dir() -> Path:
    return Path(__file__).parent.parent / "data"

@pytest.fixture
def config_path(data_dir) -> Path:
    return data_dir / "config.yaml"

@pytest.fixture
def keywords_path(data_dir) -> Path:
    return data_dir / "keywords.yaml"

@pytest.fixture
def seen_path(data_dir) -> Path:
    return data_dir / "seen.json"
```

```python
# tests/test_schemas.py
from pipeline.utils.loader import load_config, load_keywords, load_seen

def test_config_loads_and_validates(config_path):
    config = load_config(str(config_path))
    assert config.max_stories_per_delivery == 15
    assert config.telegram.breaking_news_enabled is True

def test_keywords_loads_and_validates(keywords_path):
    kw = load_keywords(str(keywords_path))
    active = kw.active_keywords()
    assert len(active) >= 30, "Should have ~30-40 active keywords"
    # Celebrity category must be inactive by default
    assert kw.categories["celebrity"].active is False

def test_seen_loads_empty(seen_path):
    # seen.json starts empty — should load without error
    store = load_seen(str(seen_path))
    assert store.entries == []

def test_import_resolves():
    # Smoke test: package structure is correct
    from pipeline.fetchers import rss_fetcher  # noqa: F401
    from pipeline.analyzers import classifier   # noqa: F401
```

### Initializing the Project with uv

```bash
# Source: docs.astral.sh/uv/guides/projects/

# Step 1: Init as package (creates src/ layout)
uv init --package khabri

# Step 2: Add runtime dependencies
uv add pydantic PyYAML

# Step 3: Add dev dependencies
uv add --dev pytest pytest-cov ruff pre-commit

# Step 4: Verify imports work
uv run python -c "from pipeline.fetchers import rss_fetcher; print('OK')"

# Step 5: Run tests
uv run pytest
```

### .pre-commit-config.yaml

```yaml
# Source: docs.astral.sh/uv/guides/integration/pre-commit/
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.9.0  # pin to a specific version
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| pip + requirements.txt | uv + uv.lock | 2024-2025 | Reproducible installs, 100x faster |
| flake8 + black + isort | ruff | 2023-2025 | Single tool, 100x faster |
| setup.py / setup.cfg | pyproject.toml | 2021+ (PEP 621) | Single config file |
| pydantic v1 | pydantic v2 | Nov 2023 | `model_validate()` not `parse_obj()`, 10x faster |
| `google-generativeai` | `google-genai` | Nov 2025 | Old SDK deprecated EOL; project already uses correct one |

**Deprecated/outdated:**
- `setup.py`: Do not use — pyproject.toml is the standard
- `pydantic v1 .parse_obj()`: Replaced by `.model_validate()` in v2
- `yaml.load()` without Loader: Use `yaml.safe_load()` — security issue
- `pip install -e .`: Use `uv sync` — same effect, lockfile-backed

---

## Open Questions

1. **Should `seen.json` use a flat array or object keyed by hash?**
   - What we know: seen.json stores article hashes for dedup; needs 7-day rolling purge
   - What's unclear: flat array is simpler to read/write but O(n) lookup; object keyed by hash is O(1) but slightly more complex
   - Recommendation: Use flat array in Phase 1 schema (simplicity); Phase 4 will implement the lookup logic and can migrate if needed. Document the tradeoff in the schema module.

2. **Where do IST→UTC conversions live?**
   - What we know: config.yaml stores times as IST strings (user-facing); GitHub Actions needs UTC cron expressions
   - What's unclear: Should the schema store both, or compute UTC on load?
   - Recommendation: Store only IST in config.yaml; add a `utc_cron()` computed property to `ScheduleConfig` that derives the UTC equivalent. This belongs in Phase 2 but the schema should anticipate it.

3. **Does `uv init --package` work with the existing repo (non-empty directory)?**
   - What we know: uv init works on existing directories with `--no-readme` to skip README creation
   - What's unclear: Whether it will conflict with existing .gitignore
   - Recommendation: Do NOT run `uv init` — manually create the directory structure and pyproject.toml from scratch to avoid any conflicts with the existing repo state.

---

## Sources

### Primary (HIGH confidence)
- [docs.astral.sh/uv/guides/projects/](https://docs.astral.sh/uv/guides/projects/) — uv project structure, init commands, sync behavior
- [docs.astral.sh/uv/concepts/projects/config/](https://docs.astral.sh/uv/concepts/projects/config/) — pyproject.toml configuration, build system, package declaration
- [docs.astral.sh/uv/concepts/projects/dependencies/](https://docs.astral.sh/uv/concepts/projects/dependencies/) — dependency groups, `uv add --dev`
- [docs.astral.sh/ruff/configuration/](https://docs.astral.sh/ruff/configuration/) — ruff pyproject.toml config
- [packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/) — src vs flat layout tradeoffs
- [docs.pydantic.dev/latest/concepts/json_schema/](https://docs.pydantic.dev/latest/concepts/json_schema/) — Pydantic v2 validation

### Secondary (MEDIUM confidence)
- [pypi.org/project/pydantic-yaml/](https://pypi.org/project/pydantic-yaml/) — verified that pydantic-yaml v1.6.0 exists but is not needed for this use case
- [docs.astral.sh/uv/guides/integration/pre-commit/](https://docs.astral.sh/uv/guides/integration/pre-commit/) — uv + pre-commit integration

### Tertiary (LOW confidence)
- WebSearch results on ML model .gitignore patterns — used for .gitignore guidance; standard patterns are well-established

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — uv, pydantic v2, ruff are all verified against official 2025/2026 docs
- Architecture: HIGH — src layout, pyproject.toml patterns verified against official Python packaging guide
- Pitfalls: MEDIUM-HIGH — derived from official docs (build system requirement, YAML type coercion) + known ecosystem patterns

**Research date:** 2026-02-27
**Valid until:** 2026-05-27 (stable tooling — 90 days is safe; ruff and uv release often but no breaking changes expected)
