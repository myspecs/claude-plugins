---
name: shift
description: Set up an unattended factory shift as a scheduled Claude Code cloud routine that runs the Software Factory Manager loop for one wave on a cadence. Use when the user says "schedule a factory shift", "run the factory every night", "create a routine for the factory", "unattended factory", or "factory on a cron". Explains prerequisites and drafts the routine; creates it only after the user confirms.
---

# Factory shift

A shift is one pass of the manager loop run by a cloud routine with no human present: integrate finished pull requests, mark tasks done, dispatch the next wave up to the cap, and stop at a milestone boundary or on failure. Routines are cloud sessions created on a schedule with the `RemoteTrigger` tool (load it with `ToolSearch select:RemoteTrigger`); the `/schedule` skill in Claude Code walks through the same API.

## Prerequisites (verify before drafting)

1. The repository is prepared per the `setup` skill: `.claude/settings.json` enables `myspec-mcp@myspec` through the `myspec` marketplace (a root `.mcp.json` only as the fallback setup describes), and `CLAUDE.md` carries the managed MySpec block naming project and bundle.
2. A cloud environment (Anthropic cloud or self-hosted, `env_...` id) with `MYSPEC_API_TOKEN` (read-write, scoped to the organisation) and egress to npm and the MySpec hosts. Routines cannot attach MCP servers configured in Claude Code; they only attach claude.ai connectors. Whether the routine's session loads the repository's plugin and MCP configuration is documented for cloud sessions in general, not for routines: the prompt below therefore discovers the MySpec tool prefix at run time and has an explicit no-MySpec branch. Run the first shift manually with `action: "run"` and read its run log before trusting the schedule.
3. `gh` authentication and a cloud dispatch path inside the routine's session are not guaranteed. The prompt checks both and stops with a report when either is missing; the first manual run must confirm them.
4. The GitHub App grants the routine's session push and pull-request rights on the repository.
5. A merge policy the user is willing to apply unattended: `squash` (merge green pull requests by squash inside the current milestone, never past a milestone boundary, never with failing or missing required checks) or `report only` (verify and report; merges wait for a human). The prompt carries the choice.
6. Caps: concurrency (default 2 for unattended), stop after two consecutive failures, minimum cadence one hour (cron in UTC; `*/30 * * * *` is rejected).

## Draft the routine

Body shape (fill placeholders; generate a fresh lowercase v4 UUID for `events[].data.uuid`):

```json
{
  "name": "factory shift: <project> / <bundle>",
  "cron_expression": "0 2 * * 1-5",
  "enabled": true,
  "job_config": {
    "ccr": {
      "environment_id": "<env_...>",
      "session_context": {
        "model": "claude-sonnet-5",
        "sources": [{"git_repository": {"url": "https://github.com/<owner>/<repo>"}}],
        "allowed_tools": ["Bash", "Read", "Write", "Edit", "Glob", "Grep", "Agent", "Skill", "mcp__plugin_myspec-mcp_myspec__list_projects", "mcp__plugin_myspec-mcp_myspec__list_spec_file", "mcp__plugin_myspec-mcp_myspec__get_spec_file", "mcp__plugin_myspec-mcp_myspec__read_spec_file", "mcp__plugin_myspec-mcp_myspec__update_spec_file", "mcp__myspec__list_projects", "mcp__myspec__list_spec_file", "mcp__myspec__get_spec_file", "mcp__myspec__read_spec_file", "mcp__myspec__update_spec_file"]
      },
      "events": [{"data": {
        "uuid": "<uuid>",
        "session_id": "",
        "type": "user",
        "parent_tool_use_id": null,
        "message": {"role": "user", "content": "<shift prompt>"}
      }}]
    }
  }
}
```

For a one-off shift use `"run_once_at": "<RFC3339 UTC in the future>"` instead of `cron_expression`; check the current time with `date -u` first.

## Shift prompt (self-contained; the session starts with zero context)

```
You are the Software Factory Manager for MySpec project "<name>" (<project_id>), bundle "<bundle>", repository <owner/repo>, default branch <main>. Run exactly one shift, then stop.

Rules: the specification bundle on MySpec is the source of truth; you never write application code; you are the only writer of tasks.md; workers report through pull requests; never force-push, bypass checks, or merge red pull requests; never enable auto-merge in any form (`gh pr merge --auto`, GitHub's auto-merge toggle, a merge queue) — each merge is a decision you make in this shift under the policy, or you leave it to the owner; merge policy <squash | report only>; concurrency cap <N>; stop after two consecutive worker failures; never cross a milestone boundary.

Shift:
0. Capabilities: run `gh auth status`; if it fails, stop and report "no GitHub access". Look for MySpec tools in your tool list: they are named mcp__plugin_myspec-mcp_myspec__<tool> or mcp__myspec__<tool>; use whichever prefix exists. If neither exists, you have no MySpec access: skip every tasks.md write, read tasks.md from the repository copy under .specs/<bundle>/ or specs/<bundle>/ if one is committed, and say in the report that "[x]" marking is deferred to the interactive manager.
1. Sign-in check (when MySpec tools exist): call list_projects; if it fails, continue without MySpec access as in step 0 and report it.
2. Integrate: list open pull requests with `gh pr list --state open --json number,title,headRefName,labels,isDraft,reviewDecision,statusCheckRollup,body`; a worker pull request has a branch factory/<bundle>/task-<N> or a title starting "task <N>:". Skip drafts and reports whose first line starts with "BLOCKED:" (list them in the report). For each remaining pull request with green required checks, an approving reviewDecision where protection requires it, and a "## Factory report", verify tests named after the acceptance criteria exist and the constitution is respected. With policy squash: merge ONE pull request with `gh pr merge <n> --squash`, then wait until every workflow run on the default branch for that merge commit has completed (and stop the shift if any failed) before merging the next; then, when MySpec tools exist, mark the task "[x]" in tasks.md using get_spec_file for content_version and update_spec_file with expected_version, adding "  - Merged: PR #<n>" under the task. With policy report only: list what is mergeable and do not merge.
3. Plan: derive ready tasks (unchecked, every _Dependencies_ done, not in flight). Group into a wave of at most <N> tasks with disjoint modules and files, within the current milestone.
4. Dispatch: for each task, start one worker session with a self-contained brief (task block, cited requirements, binding constitution sections, solution excerpts, branch factory/<bundle>/task-<N>, PR title "task <N>: <title>", Factory report at the end of the PR body, BLOCKED protocol). Tell each worker to turn on Auto-fix for its pull request and never to merge it. Use the Agent tool with isolation "remote" if available, otherwise `cd` into the repository checkout and run `claude --cloud` under a pseudo-terminal (`script -q <file> claude --cloud "$(cat <brief>)" </dev/null`; it exits 1 without a TTY). Capture each session id from the "Created cloud session:" / "View:" lines (or the agent id) immediately; expect the cloud to rewrite the session title and to push its own `claude/`-prefixed branch. If neither path works from this session, do not dispatch; report the ready wave instead.
5. Report: write a summary (merged, dispatched with a table of task, session id, URL, and branch; blocked; spec questions; milestone status; anything deferred) as a comment on the tracking issue #<n> with `gh issue comment` (or open a new issue titled "factory shift <date>"), and stop. The next shift reads the latest comment first to find running sessions and steers them with `claude -p "<message>" --cloud <session_id>` before dispatching new ones.
```

## Create and verify

1. Show the full body to the user and get explicit confirmation; the routine spends account rate limit unattended.
2. `RemoteTrigger` with `action: "create"`. Report the routine id and `https://claude.ai/code/routines/<id>`.
3. Run it once with `action: "run"`, then `action: "list_runs"` and `action: "get_run_log"` to confirm MySpec sign-in, GitHub access, and dispatch worked before leaving it scheduled.
4. Routines cannot be deleted from here; point the user to `https://claude.ai/code/routines` to pause or delete.
