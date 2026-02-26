# Phase 1: Project Scaffold - Context

**Gathered:** 2026-02-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Set up the foundational project structure: repo layout, Python package structure, dependency management (uv), data schema definitions (seen.json, config.yaml, keywords.yaml), dev tooling (pytest, ruff). No fetching, no AI, no delivery — just a working scaffold that all future phases build on.

</domain>

<decisions>
## Implementation Decisions

### Default keyword library
- Ship the FULL keyword library from the blueprint in keywords.yaml, but only two categories active by default: **Infrastructure** and **Regulatory (RERA/PMAY)**
- Celebrity and Transaction keyword categories are present in the file but marked as `active: false`
- Users can enable disabled categories later via the Telegram bot (Phase 9)
- Start with a focused set of ~30-40 active keywords across Infrastructure + Regulatory, not the full 80+

### Config defaults
- Both delivery channels (Telegram + Gmail email) active from day one
- Default schedule: 7 AM IST (morning) and 4 PM IST (evening)
- Both user Telegram chat IDs configured for delivery
- Breaking news alerts: enabled by default
- Max stories per delivery: 15 (as per blueprint)

### Data file format
- Use **YAML** (not JSON) for config.yaml and keywords.yaml — human-readable, easy to edit manually
- seen.json remains JSON — programmatic only, never hand-edited
- history.json remains JSON — same reasoning

### Claude's Discretion
- Python package structure and module naming
- Exact YAML schema design for config and keywords
- Dev tooling choices (ruff config, pytest config, pre-commit hooks)
- Dependency versions and lockfile strategy
- .gitignore contents beyond secrets

</decisions>

<specifics>
## Specific Ideas

- Keywords.yaml should support an `active: true/false` flag per category so the bot can toggle entire categories
- The blueprint's keyword lists (AUTOMATED_NEWS_SYSTEM_BLUEPRINT.md lines 278-436) are the source of truth for the full keyword library
- Config should store schedule times in IST (user-facing) with UTC conversion handled in code

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-project-scaffold*
*Context gathered: 2026-02-26*
