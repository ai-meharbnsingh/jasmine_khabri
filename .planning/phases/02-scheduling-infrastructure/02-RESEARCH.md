# Phase 2: Scheduling Infrastructure - Research

**Researched:** 2026-02-27
**Domain:** GitHub Actions cron scheduling, state commit-back, keepalive, Python pipeline entrypoint
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

None — all implementation decisions delegated to Claude.

### Claude's Discretion

**Pipeline entry point:**
- Main script structure and logging approach
- How partial failures are handled (e.g., fetcher fails but deliverer works)
- Entry/exit logging format

**State commit-back:**
- Commit message format for automated state commits
- Whether to commit when nothing changed vs skip
- Handling concurrent runs or merge conflicts on state files

**History purge rules:**
- Which files get purged (seen.json, history.json, or both)
- Whether purge is based on fetch time or publish time
- Exact purge implementation (inline vs separate utility)

**Workflow failure handling:**
- Concurrency settings (cancel in-progress or queue)
- Timeout limits for workflow runs
- Whether to notify on failure or run silently

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| INFRA-01 | System runs on GitHub Actions with UTC cron schedules correctly mapped to IST delivery times | Cron math: 7 AM IST = 01:30 UTC, 4 PM IST = 10:30 UTC. Covered by deliver.yml section. |
| INFRA-03 | System includes keepalive workflow to prevent GitHub's 60-day inactivity cron disable | `gautamkrishnar/keepalive-workflow@v2` via API mode. Covered by keepalive.yml section. |
| INFRA-05 | System auto-purges article history older than 7 days | Python datetime.fromisoformat + timedelta(days=7) filter on SeenStore entries. Covered by purge utility section. |
</phase_requirements>

---

## Summary

Phase 2 is a pure GitHub Actions + Python infrastructure phase. The core work is three YAML files and one Python utility: `deliver.yml` (the main cron + dispatch workflow), `keepalive.yml` (prevents 60-day disable), a pipeline entrypoint (`src/pipeline/main.py`), and a history purge utility. No new external APIs, no network calls — just wiring.

GitHub Actions runs all cron schedules in UTC only. IST is UTC+5:30, so the target times translate to `30 1 * * *` (7 AM IST) and `30 10 * * *` (4 PM IST). The schedules must be offset from round-hour boundaries — the success criteria specify 01:30 and 10:30 UTC exactly, which also avoids the documented peak-load delay that clusters at the top of every hour.

For state commit-back, `EndBug/add-and-commit@v9` is the standard action. It requires `permissions: contents: write` on the job and the default `GITHUB_TOKEN` is sufficient since downstream workflow re-triggering is not needed for this use case. For the keepalive, `gautamkrishnar/keepalive-workflow@v2` in API mode (no dummy commits) is the recommended approach, requiring only `permissions: actions: write`.

**Primary recommendation:** Two workflow files, one Python entrypoint, one purge utility function. Use `uv run python -m pipeline.main` as the runner command. Commit only `data/seen.json` and `data/history.json` — not the full repo — using EndBug with explicit `add` paths. Skip the commit step entirely (using the `committed` output) when no entries changed.

---

## Standard Stack

### Core

| Library / Action | Version | Purpose | Why Standard |
|-----------------|---------|---------|--------------|
| `gautamkrishnar/keepalive-workflow` | v2 (2.0.10) | Prevents 60-day inactivity cron disable via GitHub API | Official Marketplace action; v2 uses API not dummy commits, cleaner history |
| `EndBug/add-and-commit` | v9 | Commits state JSON files back to repo after each run | Most-used commit-back action; handles no-changes gracefully via `committed` output |
| `astral-sh/setup-uv` | v7 | Sets up uv in GitHub Actions runner | Official Astral action; built-in caching, matches project's uv toolchain |
| `actions/checkout` | v4 | Repo checkout with credential persistence for push | Current stable version; persist-credentials: true (default) required for EndBug |
| Python `datetime` (stdlib) | 3.12 | 7-day history purge logic | stdlib only — no additional dependency needed |

### Supporting

| Library / Action | Version | Purpose | When to Use |
|-----------------|---------|---------|-------------|
| `actions/setup-python` | v5 | Alternative Python setup if uv not managing Python | Use if `.python-version` file approach preferred over uv-managed Python |
| `uv run` | via setup-uv | Executes pipeline script in the uv virtual env | Preferred over `python -m` directly — respects lockfile |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `gautamkrishnar/keepalive-workflow@v2` | `liskin/gh-workflow-keepalive` | liskin's repo was disabled by GitHub Staff — do not use |
| `gautamkrishnar/keepalive-workflow@v2` | Manual dummy commit in deliver.yml | Every pipeline run would create a commit even on idle days — noisy history |
| `EndBug/add-and-commit@v9` | `stefanzweifel/git-auto-commit-action` | Both work; EndBug has more explicit file control via `add` input — preferred for selective path commits |
| `EndBug/add-and-commit@v9` | Manual git commands in `run:` | More control, but more lines and error handling to write — EndBug is standard |

**Installation:** No npm/pip installs. All actions are referenced by marketplace tag. `uv sync --locked` in the workflow installs Python deps from the existing lockfile.

---

## Architecture Patterns

### Recommended Project Structure

```
.github/
  workflows/
    deliver.yml       # Main pipeline: cron + workflow_dispatch + commit-back
    keepalive.yml     # Keepalive: weekly cron + gautamkrishnar action
src/
  pipeline/
    main.py           # Pipeline entrypoint: entry log, run phases, exit log
    utils/
      loader.py       # Existing: load_config, load_keywords, load_seen
      purge.py        # NEW: purge_old_entries(store, days=7) -> SeenStore
data/
  seen.json           # State file committed back after each run
  history.json        # State file committed back after each run
```

### Pattern 1: Main Workflow (deliver.yml)

**What:** Single workflow file combining `schedule` + `workflow_dispatch` triggers. Runs the Python pipeline, then commits changed state files back.

**When to use:** Always — this is the core of Phase 2.

```yaml
# Source: Official GitHub Actions docs + EndBug/add-and-commit README
name: Deliver

on:
  schedule:
    # 7 AM IST = 01:30 UTC
    - cron: "30 1 * * *"
    # 4 PM IST = 10:30 UTC
    - cron: "30 10 * * *"
  workflow_dispatch: {}   # Manual trigger — no inputs required for Phase 2

permissions:
  contents: write   # Required for EndBug/add-and-commit to push

concurrency:
  group: deliver
  cancel-in-progress: false   # Never cancel a running delivery — data integrity

jobs:
  run:
    runs-on: ubuntu-latest
    timeout-minutes: 15     # Fail loudly if pipeline hangs

    steps:
      - uses: actions/checkout@v4
        # persist-credentials: true (default) — REQUIRED for EndBug to push

      - uses: astral-sh/setup-uv@v7
        with:
          enable-cache: true

      - name: Install dependencies
        run: uv sync --locked

      - name: Run pipeline
        run: uv run python -m pipeline.main
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          # Add other secrets as phases build them out

      - name: Commit state back to repo
        uses: EndBug/add-and-commit@v9
        with:
          add: '["data/seen.json", "data/history.json"]'
          message: "chore(state): update seen/history after pipeline run [skip ci]"
          default_author: github_actions
```

**Key detail:** `[skip ci]` in the commit message prevents the commit from triggering the workflow again. `cancel-in-progress: false` for cron + dispatch workflows is the right default — cancelling a delivery mid-run could leave state files partially written.

### Pattern 2: Keepalive Workflow (keepalive.yml)

**What:** Runs weekly, uses GitHub API to touch the repo's workflow enabling state — no dummy commits.

**When to use:** Always — this satisfies INFRA-03.

```yaml
# Source: gautamkrishnar/keepalive-workflow v2 README (Marketplace)
name: Keepalive

on:
  schedule:
    # Weekly on Sunday at 00:00 UTC — low traffic time
    - cron: "0 0 * * 0"
  workflow_dispatch: {}

permissions:
  actions: write   # Required for API mode (no contents:write needed)

jobs:
  keepalive:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: gautamkrishnar/keepalive-workflow@v2
        with:
          use_api: true          # Default: API touch, no dummy commit
          time_elapsed: 45       # Default: trigger only if 45+ days since last commit
```

**Key detail:** `use_api: true` (the default in v2) is strongly preferred. It uses the GitHub API to re-enable the workflow rather than creating a git commit. This keeps the commit history clean and avoids polluting `git log` with keepalive noise.

### Pattern 3: Pipeline Entrypoint (main.py)

**What:** A `__main__`-compatible module that logs pipeline entry/exit and will eventually orchestrate fetching, filtering, AI, and delivery. In Phase 2 it is a stub that satisfies the `workflow_dispatch` success criterion: "produces a log showing pipeline entry and exit."

**When to use:** Phase 2 stub — extended in every subsequent phase.

```python
# src/pipeline/main.py
"""Khabri pipeline entrypoint. Run with: uv run python -m pipeline.main"""
import logging
import sys
from datetime import datetime, timezone

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
log = logging.getLogger(__name__)


def run() -> None:
    start = datetime.now(timezone.utc)
    log.info("=== Khabri pipeline START (%s) ===", start.isoformat())
    try:
        # Phase 2: stub — phases 3-7 will add fetch/filter/deliver calls here
        log.info("Pipeline phases: not yet implemented (Phase 2 scaffold)")
    except Exception as exc:  # noqa: BLE001
        log.error("Pipeline FAILED: %s", exc)
        sys.exit(1)
    finally:
        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        log.info("=== Khabri pipeline END (%.1fs) ===", elapsed)


if __name__ == "__main__":
    run()
```

**Logging choice:** `logging.basicConfig` with ISO timestamps to stdout/stderr — GitHub Actions captures all stdout in the run log automatically. No log file needed in Phase 2.

### Pattern 4: History Purge Utility (purge.py)

**What:** A pure function that filters `SeenStore` entries older than N days. Called from `main.py` before the commit-back step.

**Purge logic decision (Claude's discretion):**
- Purge **both** `seen.json` and `history.json` (both use `SeenStore` schema with `seen_at` field)
- Base purge on **`seen_at`** (fetch time), not publish time — publish time may be unreliable/missing from sources
- Implemented as a separate utility function in `utils/purge.py` — keeps `main.py` clean, testable in isolation

```python
# src/pipeline/utils/purge.py
"""History purge utility: removes SeenStore entries older than N days."""
import logging
from datetime import datetime, timedelta, timezone

from pipeline.schemas.seen_schema import SeenStore

log = logging.getLogger(__name__)


def purge_old_entries(store: SeenStore, days: int = 7) -> SeenStore:
    """Return a new SeenStore with entries older than `days` removed.

    Uses `seen_at` (ISO 8601, fetch time) as the age reference.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    before = len(store.entries)
    kept = []
    for entry in store.entries:
        try:
            ts = datetime.fromisoformat(entry.seen_at)
            # If seen_at has no tzinfo, assume UTC
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts >= cutoff:
                kept.append(entry)
        except ValueError:
            # Malformed timestamp — keep entry, log warning
            log.warning("Malformed seen_at for %s — keeping entry", entry.url_hash)
            kept.append(entry)
    purged = before - len(kept)
    if purged:
        log.info("Purged %d entries older than %d days from store", purged, days)
    return SeenStore(entries=kept)
```

**Key detail:** `datetime.fromisoformat()` in Python 3.7+ handles ISO 8601 strings. Python 3.11+ handles `+00:00` timezone suffix correctly; Python 3.12 (project target) is safe. The `seen_at` field is stored as a plain ISO string (from `SeenEntry` schema), so no json parsing needed — just `fromisoformat`.

### Anti-Patterns to Avoid

- **Top-of-hour cron timing:** `0 1 * * *`, `0 10 * * *` — avoid. GitHub queues peak at :00 UTC. The success criteria already specify :30, which is correct.
- **`cancel-in-progress: true` on delivery workflow:** Cancelling a mid-run delivery could leave `seen.json` written but Telegram not sent — inconsistent state. Use `false` or omit (defaults to false for same-group).
- **PAT for commit-back:** Not needed here. `GITHUB_TOKEN` with `permissions: contents: write` is sufficient since the commit-back must NOT re-trigger the delivery workflow (that would loop). `[skip ci]` in the message + GITHUB_TOKEN ensures no loop.
- **`git add .` instead of explicit paths:** The EndBug `add` input should list `data/seen.json` and `data/history.json` explicitly, not `.` — avoid accidentally committing `.env` files, pyc caches, or workflow changes.
- **Committing when nothing changed:** EndBug does this correctly — if `committed` output is `'false'`, no push happens. Do not force-commit an empty change.
- **Purging with naive `datetime.now()` (no timezone):** Always use `datetime.now(timezone.utc)` — naive datetimes will fail comparison if `seen_at` has timezone info.
- **liskin/gh-workflow-keepalive:** This repo was disabled by GitHub Staff for ToS violation as of early 2026. Do not use.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Commit state files back to repo | Custom `git add && git commit && git push` shell steps | `EndBug/add-and-commit@v9` | Handles no-changes gracefully, outputs `committed` boolean, proper author attribution |
| Prevent 60-day cron disable | Cron job that creates dummy commits | `gautamkrishnar/keepalive-workflow@v2` (API mode) | Uses GitHub API — no git history pollution, maintained Marketplace action |
| uv environment in CI | `pip install -r requirements.txt` or manual venv | `astral-sh/setup-uv@v7` with `enable-cache: true` | Built-in caching, respects `uv.lock`, official action |

**Key insight:** The commit-back and keepalive patterns both have subtle edge cases (no-op commits, race conditions, token scope) that the purpose-built actions handle correctly. Rolling custom shell commands introduces maintenance burden and subtle bugs.

---

## Common Pitfalls

### Pitfall 1: DST Does Not Apply to IST

**What goes wrong:** Developer wonders if IST cron times need adjustment for Daylight Saving Time.
**Why it happens:** IST (UTC+5:30) does not observe DST. India has a fixed offset year-round.
**How to avoid:** Set cron once (`30 1 * * *` and `30 10 * * *`) and never change it for seasonal adjustment.
**Warning signs:** N/A — this is a false concern.

### Pitfall 2: GitHub Cron Delays (15-40 minutes)

**What goes wrong:** Workflow is scheduled for 01:30 UTC but fires at 01:50 or later, causing Telegram delivery to arrive late.
**Why it happens:** GitHub treats scheduled workflows as best-effort. Under load (especially near :00 UTC), queues back up. The 7 AM / 4 PM IST delivery is for news briefings, not time-critical alerts — a 20-minute delay is acceptable.
**How to avoid:** No mitigation needed given the use case. Do not attempt to compensate with earlier cron times to "pre-empt" delays — this is undocumented and unreliable.
**Warning signs:** If Phase 6 (Telegram delivery) has user complaints about timing, revisit. Phase 2 just needs the workflow to fire — exact minute precision is out of scope.

### Pitfall 3: Workflow Re-triggering Loop

**What goes wrong:** The commit-back step (EndBug) pushes a commit, which triggers the `push` event, which re-runs the deliver workflow, causing a loop.
**Why it happens:** GITHUB_TOKEN push events can trigger other workflows unless suppressed.
**How to avoid:** Two defenses:
  1. The deliver.yml uses `schedule` + `workflow_dispatch` only — no `push` trigger. A commit from EndBug cannot trigger this workflow.
  2. Add `[skip ci]` to the commit message as belt-and-suspenders for any future `push`-triggered workflow additions.
**Warning signs:** Workflow run count doubling or tripling after merge.

### Pitfall 4: `persist-credentials: false` Breaking EndBug

**What goes wrong:** Developer sets `persist-credentials: false` on `actions/checkout@v4` for security hardening, then EndBug fails to push.
**Why it happens:** EndBug relies on credentials persisted by the checkout step. With `false`, there are no credentials in `.git/config`.
**How to avoid:** Leave `persist-credentials` at default (`true`) in deliver.yml. The `GITHUB_TOKEN` is scoped to the current repo and expires after the run — no meaningful security risk.
**Warning signs:** EndBug step fails with `403` or `remote: Permission to ... denied`.

### Pitfall 5: SeenStore `seen_at` Timezone Naivety

**What goes wrong:** Purge logic compares naive datetime (no tz) against timezone-aware datetime, raising `TypeError: can't compare offset-naive and offset-aware datetimes`.
**Why it happens:** `datetime.fromisoformat("2026-02-20T13:00:00")` returns a naive datetime. `datetime.now(timezone.utc)` is aware.
**How to avoid:** The purge utility above handles this explicitly — if `ts.tzinfo is None`, assume UTC. This is safe because all entries are written by the pipeline with UTC timestamps.
**Warning signs:** `TypeError` in purge step during workflow run.

### Pitfall 6: EndBug Committing `.env` or Cache Files

**What goes wrong:** `add: '.'` stages all changed files, including accidentally modified or untracked sensitive files.
**How to avoid:** Always specify explicit paths: `add: '["data/seen.json", "data/history.json"]'`. Rely on `.gitignore` as a secondary guard, but explicit paths are the primary control.
**Warning signs:** Unexpected files appearing in auto-commits.

---

## Code Examples

Verified patterns from official sources:

### IST to UTC Cron Conversion

```yaml
# IST = UTC+5:30 (no DST)
# 7:00 AM IST = 01:30 UTC
# 4:00 PM IST = 10:30 UTC
# Avoiding :00 boundary reduces peak-load delay risk
on:
  schedule:
    - cron: "30 1 * * *"   # 7 AM IST daily
    - cron: "30 10 * * *"  # 4 PM IST daily
```

### EndBug with Explicit File Paths and Skip-CI

```yaml
# Source: EndBug/add-and-commit README (verified from Marketplace page)
- name: Commit state back to repo
  uses: EndBug/add-and-commit@v9
  with:
    add: '["data/seen.json", "data/history.json"]'
    message: "chore(state): update seen/history after pipeline run [skip ci]"
    default_author: github_actions
```

### Keepalive API Mode

```yaml
# Source: gautamkrishnar/keepalive-workflow v2 Marketplace page (version 2.0.10)
- uses: gautamkrishnar/keepalive-workflow@v2
  with:
    use_api: true
    time_elapsed: 45
```

### uv in CI (from official Astral docs)

```yaml
# Source: https://docs.astral.sh/uv/guides/integration/github/
- uses: astral-sh/setup-uv@v7
  with:
    enable-cache: true

- name: Install project
  run: uv sync --locked

- name: Run pipeline
  run: uv run python -m pipeline.main
```

### 7-Day Purge Using stdlib datetime

```python
# Source: Python 3.12 stdlib — datetime, timedelta
from datetime import datetime, timedelta, timezone

cutoff = datetime.now(timezone.utc) - timedelta(days=7)
kept = [e for e in store.entries
        if datetime.fromisoformat(e.seen_at).replace(tzinfo=timezone.utc) >= cutoff]
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `dummy commit` keepalive (force-push empty commit) | `gautamkrishnar/keepalive-workflow@v2` API mode | v2 release (~2024) | No git history pollution |
| `liskin/gh-workflow-keepalive` | `gautamkrishnar/keepalive-workflow@v2` | Early 2026 (liskin repo disabled by GitHub Staff) | liskin is dead — do not reference |
| `actions/setup-python@v4` | `actions/setup-python@v5` (or skip and use `astral-sh/setup-uv@v7` alone) | v5 in 2024, v6 in 2025 | For uv projects, `setup-uv` alone is sufficient |

**Deprecated/outdated:**
- `liskin/gh-workflow-keepalive`: Disabled by GitHub Staff for ToS violation (February 2026). Do not use.
- `gautamkrishnar/keepalive-workflow@v1`: Commit-based mode. Still works but creates unnecessary commits.
- `EndBug/add-and-commit@v8` and earlier: Older inputs API. Use v9.

---

## Open Questions

1. **Secrets configuration for Phase 2 stub**
   - What we know: `deliver.yml` references `secrets.TELEGRAM_BOT_TOKEN` in the env block, but Phase 2 pipeline is a stub that doesn't call Telegram yet.
   - What's unclear: Should the Phase 2 workflow env block reference secrets that don't exist yet, or should they be added in Phase 6 when Telegram is wired?
   - Recommendation: Add a commented `# env:` block in deliver.yml with all anticipated secret names, but only activate them when the relevant phase implements their usage. This avoids workflow failures if secrets aren't set.

2. **Concurrency between cron and `workflow_dispatch`**
   - What we know: `concurrency: group: deliver, cancel-in-progress: false` queues a manual trigger if a cron run is active.
   - What's unclear: If two cron triggers fire close together (GitHub backlog), could they queue and both run, causing double state writes?
   - Recommendation: `cancel-in-progress: false` is correct — don't cancel. But add `timeout-minutes: 15` to ensure a hung first run eventually terminates and unblocks the queue.

3. **What to commit when seen.json has no new entries (first dry run)**
   - What we know: EndBug outputs `committed: false` if nothing changed, skips push.
   - What's unclear: Phase 2 pipeline is a stub — seen.json will never change. Is a dry-run commit needed to verify the commit-back mechanism works?
   - Recommendation: In the workflow, add a `run: echo "committed=${{ steps.commit.outputs.committed }}"` step to log the EndBug output. During Phase 2 verification, manually add a test entry to seen.json, trigger workflow_dispatch, and verify the commit-back fires.

---

## Sources

### Primary (HIGH confidence)

- GitHub Actions official docs (`docs.github.com/en/actions`) — schedule event, UTC cron, 60-day disable, workflow_dispatch, GITHUB_TOKEN permissions
- `gautamkrishnar/keepalive-workflow` Marketplace page (v2.0.10) — current version, API mode inputs, permissions
- `EndBug/add-and-commit` README (`github.com/EndBug/add-and-commit`) — v9 inputs, `committed` output, token behavior
- Astral uv docs (`docs.astral.sh/uv/guides/integration/github/`) — `setup-uv@v7`, `uv sync --locked`, `uv run`

### Secondary (MEDIUM confidence)

- GitHub community discussion #156282 — cron delay ranges (15-40 min), best-effort scheduling, avoid :00 boundary
- GitHub Actions billing docs — free tier: 2,000 min/month for private repos; unlimited for public repos (project repo is public — 0 cost risk)
- `liskin/gh-workflow-keepalive` GitHub page — confirmed disabled by GitHub Staff (verified 2026-02-27)

### Tertiary (LOW confidence)

- None for this phase — all critical claims are backed by official sources.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all actions verified against Marketplace pages and official docs
- Architecture: HIGH — cron math is deterministic (UTC+5:30 offset), patterns from official examples
- Pitfalls: HIGH for timing/token issues (multiple official sources), MEDIUM for delay ranges (community-reported, acknowledged by GitHub)

**Research date:** 2026-02-27
**Valid until:** 2026-08-27 (stable infra domain — actions versions may update, recheck before major changes)
