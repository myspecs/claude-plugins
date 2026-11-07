---
name: shift
description: Set up an unattended factory shift as a scheduled Claude Code cloud routine that runs one pass of the Software Factory Manager loop on a cadence: integrate, then give the team's idle agents their next assignments. Use when the user says "schedule a factory shift", "run the factory every night", "create a routine for the factory", "unattended factory", or "factory on a cron". Explains prerequisites and drafts the routine; creates it only after the user confirms.
user-invocable: false
---

# Factory shift

A shift is one pass of the manager loop run by a cloud routine with no human present: integrate finished pull requests, mark tasks done, send each idle agent of the team its next group of tasks (starting agents only up to the team size), and stop at a milestone boundary or on failure. The team outlives a shift: agents are long-lived cloud sessions, and each shift finds them again in the previous shift's report. Routines are cloud sessions created on a schedule with the `RemoteTrigger` tool (load it with `ToolSearch select:RemoteTrigger`); the `/schedule` skill in Claude Code walks through the same API.

## Prerequisites (verify before drafting)

1. The repository is prepared per the `setup` skill: `.claude/settings.json` enables `myspec-mcp@myspec` through the `myspec` marketplace (a root `.mcp.json` only as the fallback setup describes), and `CLAUDE.md` carries the managed `<!-- myspec-mcp:start -->` block naming the project (the routine prompt names the bundle).
2. A cloud environment (Anthropic cloud or self-hosted, `env_...` id) with `MYSPEC_API_TOKEN` (read-write, scoped to the organisation) and egress to npm and the MySpec hosts. Routines cannot attach MCP servers configured in Claude Code; they only attach claude.ai connectors. Whether the routine's session loads the repository's plugin and MCP configuration is documented for cloud sessions in general, not for routines: the prompt below therefore discovers the MySpec tool prefix at run time and has an explicit no-MySpec branch. Run the first shift manually with `action: "run"` and read its run log before trusting the schedule.
3. `gh` authentication and `claude --cloud` inside the routine's session are not guaranteed. The prompt checks both and stops with a report when either is missing; the first manual run must confirm them.
4. The GitHub App grants the routine's session push and pull-request rights on the repository.
5. A merge policy the user is willing to apply unattended: `squash` (merge green pull requests by squash inside the current milestone, never past a milestone boundary, never with failing or missing required checks) or `report only` (verify and report; merges wait for a human). The prompt carries the choice.
6. Caps: team size (default 2 for unattended), stop after two consecutive failures, minimum cadence one hour (cron in UTC; `*/30 * * * *` is rejected).

A shift runs without a factory board (the `board` skill): a routine cannot keep the board's comment watch between runs, so its agent briefs carry no `## Factory board` section and its agents report through pull requests only. The repository's board, if the interactive manager has one, is left as it is.

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
        "allowed_tools": ["Bash", "Read", "Write", "Edit", "Glob", "Grep", "Agent", "Skill", "mcp__plugin_myspec-mcp_myspec__list_projects", "mcp__plugin_myspec-mcp_myspec__list_spec_file", "mcp__plugin_myspec-mcp_myspec__get_spec_file", "mcp__plugin_myspec-mcp_myspec__read_spec_file", "mcp__plugin_myspec-mcp_myspec__update_spec_file", "mcp__plugin_myspec-mcp_myspec__list_tasks", "mcp__plugin_myspec-mcp_myspec__set_task_status", "mcp__plugin_myspec-mcp_myspec__update_tasks", "mcp__myspec__list_projects", "mcp__myspec__list_spec_file", "mcp__myspec__get_spec_file", "mcp__myspec__read_spec_file", "mcp__myspec__update_spec_file", "mcp__myspec__list_tasks", "mcp__myspec__set_task_status", "mcp__myspec__update_tasks"]
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

Rules: the specification bundle on MySpec is the source of truth; you never write application code; you are the only writer of tasks.md (task statuses included: [ ] pending, [-] in progress, [x] done); agents report through pull requests; never force-push, bypass checks, or merge red pull requests; never enable auto-merge in any form (`gh pr merge --auto`, GitHub's auto-merge toggle, a merge queue) — each merge is a decision you make in this shift under the policy, or you leave it to the owner; merge policy <squash | report only>; team size <N> agents; stop after two consecutive failed assignments; never cross a milestone boundary (a tasks.md with "## Branch Plan" from an older factory version: each lane is one group, and its gate comes after the last lane merges); never assign work while the spec is unfinished (a missing document, TBD or placeholder text, an open question) — report it instead; if the bundle has no tasks.md, do not plan one — report that the interactive manager must plan it with the user.

The team: up to <N> agents a1, a2, …, each with a person-style name (Ada, Linus, Grace, Alan, … — one per agent, kept for the run) and one long-lived Claude Code cloud session titled "<name> (a<k>)", that works one assignment (a group of related tasks, one branch, one pull request) at a time. You find them in the latest comment on the tracking issue #<n> (a "Team" table: agent, name, session id, model/effort, open assignment, queue). Message an agent only with `claude -p "$(cat <file>)" --cloud <session_id> </dev/null` (from the repository checkout); it wakes an idle session.

Shift:
0. Capabilities: run `gh auth status`; if it fails, stop and report "no GitHub access". Look for MySpec tools in your tool list: they are named mcp__plugin_myspec-mcp_myspec__<tool> or mcp__myspec__<tool>; use whichever prefix exists. If neither exists, you have no MySpec access: skip every tasks.md write, read tasks.md from the repository copy under .specs/<bundle>/ or specs/<bundle>/ if one is committed, and say in the report that "[x]" marking is deferred to the interactive manager.
1. Sign-in check (when MySpec tools exist): call list_projects; if it fails, continue without MySpec access as in step 0 and report it. Read the latest comment on the tracking issue for the team table.
2. Integrate: list open pull requests with `gh pr list --state open --json number,title,headRefName,labels,isDraft,reviewDecision,statusCheckRollup,body`; an agent's pull request has a branch factory/<bundle>/tasks-<N1>-<N2>-…, factory/<bundle>/task-<N> or claude/…, and a title starting "task <N1>, <N2>, …:" or "task <N>:", and covers every task its title lists (an older lane pull request, "lane <L>:", covers every task listed for that lane under "## Branch Plan"). Skip drafts and reports whose first line starts with "BLOCKED:" (list them in the report). For each remaining pull request with green required checks on its current head, an approval from the gating reviewer on that same head commit (an approval on an earlier commit does not count; request the review again instead), no unresolved review threads, and a "## Factory report", verify tests named after the acceptance criteria exist and the constitution is respected. Red checks or review items: send them to the pull request's agent, which fixes them before its current work. With policy squash: first check the tested tree is the merged tree (if the default branch gained commits touching the pull request's projects since its checks ran, run `gh pr update-branch <n>` and leave it for the next shift), then merge ONE pull request with `gh pr merge <n> --squash --match-head-commit <the head you verified>`, then wait until every workflow run on the default branch for that merge commit has completed (and stop the shift if any failed) before merging the next; then, when MySpec tools exist, mark every task the pull request covers done: list_tasks for their task_id values and the file's content_version, set_task_status with status done and expected_versions; then add "  - Merged: PR #<n>" under each task with get_spec_file for the new content_version, read_spec_file, and update_spec_file with expected_version. When the task tools answer "the task board is turned off", write "[x]" and the notes in one update_spec_file instead. With policy report only: list what is mergeable and do not merge.
3. Plan: derive the not-done tasks of the current milestone that are in no open pull request. Group related tasks: a dependency chain (a waiting task joins when all its unmet dependencies are in the same group), tasks that share a module or file, and tasks for the same requirement go together; a task is a group of its own only when nothing relates to it; tasks that share a module or file are never in two groups; keep groups within the current milestone and inside any split tasks.md declares. Weigh each group by its tasks' _Complexity_ (Small 1, Medium 2, Large 3, none 2). Divide the groups between the agents: start from the queues in the last team table, drop groups that are done or in flight, give a group to the agent that holds the group it depends on, otherwise to the agent with the lowest load.
4. Assign: an agent is free when it has no assignment still in progress (its last pull request is merged, or open with the review requested). For each free agent, its next group whose dependencies are all merged is its next assignment; with nothing ready in its queue, take the heaviest ready group from the most loaded agent's queue. Mark its tasks in progress (set_task_status in_progress, when the task board is on), then send it as one message: first line "Software Factory Manager: assignment a<k>-<n> for <name>: task <N1>, <N2>, …: <summary>", then branch factory/<bundle>/tasks-<N1>-<N2>-… from a fresh origin/<main>, PR title "task <N1>, <N2>, …: <summary>", one commit per task, the blocked rule for each task, every task block in order, the cited requirements, the decisions, the solution excerpts, what already shipped, and "When the pull request exists and the review is requested, end your turn with exactly: waiting for next assignment". When the team has fewer than <N> live agents and a ready group has no free agent, start a new agent: `cd` into the repository checkout and give it the next free name, run `script -q <file> claude --cloud "$(cat <brief>)" --name "<name> (a<k>)" --model <model> --effort <effort> --permission-mode auto </dev/null` (it exits 1 without a TTY) with a self-contained agent brief (first line "factory <bundle> agent <name> (a<k>)", then "You are <name>"; repository, setup, test and lint commands, binding constitution sections, test rules, Definition of done with one commit per task, the Factory report at the end of the PR body, the rules for several assignments: a new branch from a fresh origin/<main> per assignment, review fixes on an earlier pull request first, at most one pull request in review and one in progress, only assignment messages add tasks; request review from <reviewer> as soon as each pull request exists, turn on Auto-fix, never merge; the BLOCKED protocol) followed by its first assignment. Give each agent one model and effort for its whole session, the highest its queue needs: opus with medium effort by default; sonnet with medium only when every group in its queue is small and mechanical (docs, config, renames, tests for listed cases); opus with high for shared contracts, migrations, security, concurrency or a large group; opus with xhigh for the hardest cross-cutting work and for a replacement session after a failure at high. Never sonnet above medium, and when unsure take the higher one. Capture each new session id from the "Created cloud session:" / "View:" lines immediately; when the "Created cloud session:" title is not "<name> (a<k>)", send `claude -p "/rename <name> (a<k>)" --cloud <session_id>`, and report the title it showed. Expect the cloud to push its own `claude/`-prefixed branch for each assignment. An agent whose session ended, or whose assignment failed (red checks it could not fix, no pull request), is replaced by a new session for the same agent (same name, title "<name> (a<k>.r2)") one rung higher on failure, with the failed group as its first assignment based on the failed branch. If `claude --cloud` does not work from this session, do not start agents; report the ready assignments instead.
5. Report: write a summary as a comment on the tracking issue #<n> with `gh issue comment` (or open a new issue titled "factory shift <date>"): merged; the "Team" table (agent, name, session id, URL, session title, model/effort, open assignment with tasks and branch, queue in order); assignments sent this shift; blocked; spec questions; milestone status; anything deferred. Then stop. The next shift starts from this table.
```

## Create and verify

1. Show the full body to the user and get explicit confirmation; the routine spends account rate limit unattended.
2. `RemoteTrigger` with `action: "create"`. Report the routine id and `https://claude.ai/code/routines/<id>`.
3. Run it once with `action: "run"`, then `action: "list_runs"` and `action: "get_run_log"` to confirm MySpec sign-in, GitHub access, and that agents started or received assignments before leaving it scheduled.
4. Routines cannot be deleted from here; point the user to `https://claude.ai/code/routines` to pause or delete.
