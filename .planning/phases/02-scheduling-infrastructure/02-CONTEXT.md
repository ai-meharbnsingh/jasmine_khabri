# Phase 2: Scheduling Infrastructure - Context

**Gathered:** 2026-02-27
**Status:** Ready for planning

<domain>
## Phase Boundary

GitHub Actions workflows are deployed with cron schedules wired to correct IST times (7 AM / 4 PM), a keepalive workflow prevents 60-day inactivity disable, manual `workflow_dispatch` trigger works, and state files are committed back to the repo after each run. History older than 7 days is purged automatically.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
User delegated all implementation decisions to Claude. The following areas are open for best-judgment choices during research and planning:

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

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches. Follow the success criteria from the roadmap exactly:
1. `deliver.yml` triggers at 01:30 UTC and 10:30 UTC (7 AM and 4 PM IST)
2. Keepalive workflow prevents 60-day GitHub inactivity disable
3. `workflow_dispatch` manual trigger runs pipeline without errors
4. `EndBug/add-and-commit` commits updated state files back to repo
5. Article history older than 7 days is purged automatically

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 02-scheduling-infrastructure*
*Context gathered: 2026-02-27*
