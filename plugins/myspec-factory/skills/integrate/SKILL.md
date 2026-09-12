---
name: integrate
description: Collect factory worker pull requests, verify them against the task's acceptance criteria and the constitution, merge per the agreed policy, mark the task done on MySpec, and run the milestone gate. Use when the user says "integrate the wave", "merge the factory PRs", "what did the workers deliver", "mark task N done", or after every dispatched session in a wave has reported.
---

# Factory integrate

Tools are called as `mcp__plugin_myspec-mcp_myspec__<tool>`. This skill runs when the `watch` skill reports a worker's `factory-<bundle>-task-<N>-report.md` attachment, a pull-request monitor line, or on request. Start by reading `.specs/<bundle>/factory-sessions.json` (the session registry written by `dispatch`) to know which sessions and branches belong to this wave. Inputs: the wave's tasks and their pull requests, the merge policy the user agreed to at run start (squash or merge commit; whether green pull requests may be merged without asking inside a milestone; required checks), and the `content_version` of `tasks.md`. Writes to `tasks.md` follow the write-back protocol in the `myspec-mcp:implement` skill; the manager is the only writer.

## 1. Collect

Cloud workers may have pushed a branch without a pull request: `git fetch --prune` and `git branch -r --list 'origin/claude/*' 'origin/factory/*'`; for a branch whose worker reported a task number but no pull request exists, open one with `gh pr create --head <branch> --title "task N: <title>" --body-file <report>` using the report from the worker's final message. Then `gh pr list --state open --json number,title,headRefName,labels,isDraft,reviewDecision,statusCheckRollup,body` and match each pull request to a task by branch `factory/<bundle>/task-<N>` or title `task N:` (cloud sessions push `claude/`-prefixed branches, so the title match matters). Read the `## Factory report` at the end of the body. A missing report means the worker did not finish; treat as failed. A draft pull request or a report whose first line starts with `BLOCKED:` is blocked, not ready.

## 2. Verify each pull request (read-only)

1. Checks: every required check green. Red: do not merge; redispatch per the `dispatch` skill's rules with the failing output in the brief.
   Red checks on a cloud worker that is still running: steer it first with `claude -p "<failing output>" --cloud <session_id>` (id from the registry) before redispatching.
   Reviews: when branch protection requires approvals, `reviewDecision` must be `APPROVED`; ask the user to review or approve. `CHANGES_REQUESTED`: collect the review comments (`gh pr view <n> --comments` and `gh api repos/{owner}/{repo}/pulls/<n>/comments`) and redispatch the worker with them in the brief; the manager never rewrites the code itself.
2. Acceptance criteria: for each criterion on the task and its `_Requirements:_` entries, find the test that names it (`grep -riE 'FR[-_]?003'` style) in the diff. Missing tests are a failure unless the report explains why the criterion cannot be tested automatically.
3. Constitution: the diff introduces no forbidden technology, pattern, or security violation. Delegate a read-only diff review to a subagent when the diff is large; ask it to report gaps against the acceptance criteria and constitution, not style.
4. Scope: the diff touches only the modules and files the task named plus tests. Unrelated changes are reported back and the pull request is not merged until the worker removes them.
5. Spec issues raised in the report (`BLOCKED: spec`, deviations): stop this lane, put the question to the user, and after the answer record it as `- Clarification:` under the task in `tasks.md` (or `## Clarifications` in `requirements.md` for requirement-level answers) before redispatching.

## 3. Merge per policy

- Merge with `gh pr merge <n> --squash` or `--merge` as agreed, never `--admin`, never a force push. If the policy requires the user's approval for each merge, present the verified list and wait.
- Merge in task-number order inside the wave. After each merge, if a later pull request in the wave now conflicts, ask its worker (or a fresh worker) to rebase; do not resolve conflicts in the manager session beyond trivial lockfile or changelog conflicts, and say when you did.
- Delete the merged branch if the repository's policy does.

## 4. Mark done on MySpec

For each merged task: `get_spec_file` for the current `content_version`, `read_spec_file` for the body, flip that task's `- [ ]` to `- [x]`, keep every other byte, and `update_spec_file` with `expected_version`. On a conflict, take the new token, re-read, re-apply, retry. After the write, the event feed echoes a `spec_file.updated` frame carrying the returned `content_version`; ignore it. Add an indented note under the task with the pull request number: `  - Merged: PR #123 (<short sha>)`. One update per task is fine; batching all merged tasks into one update is better when several merged.

## 5. Board and log

Update each registry entry (`pr`, `status`: `pr-open`, `merged`, `blocked`, `failed`). Re-derive the board (done, in flight, blocked, ready) and update `.specs/<bundle>/factory-run.md` with what merged, what was redispatched, and cost so far (sessions started this run, by path, and redispatches; that is the measurable unit). Post the board. For `--bg --worktree` workers whose task merged, clean up with `claude rm <id>` and `git worktree remove`.

## 6. Milestone gate

When the last task of a `## Milestone` is `[x]`:

1. Run the full test suite on the default branch (or ask the user to, when it needs infrastructure).
2. Run the `myspec-mcp:analyze` skill in convergence mode for the milestone's requirement ids; report coverage and any missing, partial, contradicting, or unrequested items.
3. Summarise the milestone: tasks merged, requirement ids satisfied, spec edits made, open questions, cost.
4. Offer to write the summary to `.specs/<bundle>/milestone-<M>.md` and `upload_attachment` it (absolute `file_path`) to the MySpec project.
5. Stop. Do not plan or dispatch the next milestone until the user says so.
