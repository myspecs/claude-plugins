---
name: integrate
description: Collect factory worker pull requests, verify them against the task's acceptance criteria and the constitution, merge per the agreed policy, mark the task done on MySpec, and run the milestone gate. Use when the user says "integrate the wave", "merge the factory PRs", "what did the workers deliver", "mark task N done", or after every dispatched session in a wave has reported.
---

# Factory integrate

Tools are called as `mcp__plugin_myspec-mcp_myspec__<tool>`. This skill runs per pull request, not per wave: whenever the `watch` skill reports a worker's `factory-<bundle>-task-<N>-report.md` attachment, a pull-request monitor line shows a pull request approved and green, or on request. Start by reading `.specs/<bundle>/factory-sessions.json` (the session registry written by `dispatch`) to know which sessions and branches belong to this wave. Inputs: the wave's tasks and their pull requests, the merge policy the user agreed to at run start (squash or merge commit; whether green pull requests may be merged without asking inside a milestone; required checks), and the `content_version` of `tasks.md`. Writes to `tasks.md` follow the write-back protocol in the `myspec-mcp:implement` skill; the manager is the only writer.

## 1. Collect

Cloud workers may have pushed a branch without a pull request: `git fetch --prune` and `git branch -r --list 'origin/claude/*' 'origin/factory/*'`; for a branch whose worker reported a task number but no pull request exists, open one with `gh pr create --head <branch> --title "task N: <title>" --body-file <report>` using the report from the worker's final message. Then `gh pr list --state open --json number,title,headRefName,labels,isDraft,reviewDecision,statusCheckRollup,body` and match each pull request to a task by branch `factory/<bundle>/task-<N>` or title `task N:` (cloud sessions push `claude/`-prefixed branches, so the title match matters). Read the `## Factory report` at the end of the body. A missing report means the worker did not finish; treat as failed. A draft pull request or a report whose first line starts with `BLOCKED:` is blocked, not ready.

## 2. Verify each pull request (read-only)

1. Checks: every required check green. Red: do not merge; redispatch per the `dispatch` skill's rules with the failing output in the brief.
   Red checks on a cloud worker that is still running: with Auto-fix on, give it a little time to answer the failure itself before intervening; otherwise steer it with `claude -p "<failing output>" --cloud <session_id>` (id from the registry) before redispatching. A pull request whose `autofix` is not `on` gets no automatic response once its session goes idle — turn it on or steer it.
   Reviews: when branch protection requires approvals, `reviewDecision` must be `APPROVED`; ask the user to review or approve. `CHANGES_REQUESTED`: collect the review comments (`gh pr view <n> --comments` and `gh api repos/{owner}/{repo}/pulls/<n>/comments`) and redispatch the worker with them in the brief; the manager never rewrites the code itself.
2. Acceptance criteria: for each criterion on the task and its `_Requirements:_` entries, find the test that names it (`grep -riE 'FR[-_]?003'` style) in the diff. Missing tests are a failure unless the report explains why the criterion cannot be tested automatically.
   Delegate this to a read-only subagent: ask it to verify acceptance criteria based on code analysis alone, never running tests, builds, or the project. The subagent should read the implementation code and test files to return a criterion-by-criterion table with `file:line` or test-name evidence. For each criterion, the subagent must analyze the test code to determine whether the test would actually fail if the implementation were reverted or broken — contract tests that only check one direction, or assert on objects the test builds itself, give false confidence.
   For high-risk criteria (authorization defaults, concurrency, ordering, what is published before commit), the subagent must READ THE IMPLEMENTATION CODE directly to verify the behavior matches the requirement, not just confirm a test exists.
   When several branches build against one contract, compare them directly — the producer's payloads, service names and response wrappers against the consumer's structs and client code, field by field. Neither branch's CI can see a mismatch between them.
   After a worker pushes fixes, re-verify only the fix commits (`git diff <verified-sha>..<head>`), item by item, with evidence and whether each test would fail on revert. A fix that is only partial goes straight back with the remaining gap.
3. Constitution: the diff introduces no forbidden technology, pattern, or security violation. Delegate a read-only diff review to a subagent when the diff is large; ask it to report gaps against the acceptance criteria and constitution, not style.
4. Scope: the diff touches only the modules and files the task named plus tests. Unrelated changes are reported back and the pull request is not merged until the worker removes them.
5. Spec issues raised in the report (`BLOCKED: spec`, deviations): stop this lane, put the question to the user, and after the answer record it as `- Clarification:` under the task in `tasks.md` (or `## Clarifications` in `requirements.md` for requirement-level answers) before redispatching.
   Deviations are often NOT flagged as blocked: an extra fallback rung, a broader delete rule, an added service. Look for behaviour beyond the requirements in the diff and the report. Put each to the user with the trade-off (including what the reviewer recommends, if it differs), record the answer as a numbered Clarification, and tell the worker so it neither reverts a kept deviation nor keeps a rejected one.
6. Red checks: a failure is the branch's until shown otherwise. Before re-running, establish that the diff does not touch the failing test or its code path and that the same test has failed elsewhere (another branch, main); then re-run the failed job, send the worker that evidence if a reviewer blamed the branch, and record the flaky test for the regression task. A `CANCELLED` run superseded by a newer push is not a failure.
7. Reviewer stalls: when the automated reviewer has not reviewed a green pull request for well over its usual time, run your own verification meanwhile, and put the choice — keep waiting, or merge on your verification — to the user rather than lowering the gate yourself.

## 3. Merge per policy

- Merge with `gh pr merge <n> --squash` or `--merge` as agreed, never `--admin`, never `--auto`, never a force push. Auto-merge is out of bounds in every form — the `--auto` flag, GitHub's auto-merge toggle, and merge queues — because a merge must be decided by the manager under the agreed policy or by the user, at the moment the evidence is in front of them. If a pull request arrives with auto-merge already enabled, turn it off before verifying and say so. If the policy requires the user's approval for each merge, present the verified list and wait.
- Absent branch protection (`gh api repos/{owner}/{repo}/branches/<base>/protection` returns 404) nothing stops a merge; that is a reason to hold to the agreed policy, not to skip it. Say when the base is unprotected, since then a green `reviewDecision` is the only gate.
- **Merge one pull request at a time, and wait for its post-merge CI/CD to finish before merging the next.** Never merge several pull requests back to back, even when all are approved and green. Push workflows on the default branch build and deploy per merge commit; runs triggered seconds apart race, and a slower run for an OLDER commit can finish last — overwriting a mutable image tag such as `:latest` and redeploying older code over newer code. (Observed: two platform merges 2 s apart left dev running the older commit's image until the newer run was re-run.) After each merge:
  1. Watch `gh run list --branch <base> --json name,status,conclusion,headSha` filtered to that merge commit until every run is `completed`.
  2. Any failure: stop merging, report, and do not merge the next pull request on a red default branch.
  3. Only then re-check the next pull request is still on its approved head and `CLEAN` (it may need a rebase after the previous merge) and merge it.
- **Merge a pull request as soon as it is ready; do not hold it for the rest of the wave.** Ready means verified, approved, green and within the agreed merge policy (asking the user first when the policy says so). The only reason to hold a ready pull request is a dependency on another pull request that has not merged yet — its code calls, consumes or deploys against something only that other pull request provides (for example tools or clients that answer 501 until the platform pull request ships). Record the dependency in the registry entry's `notes` and merge it right after the one it waits for.
- When several ready pull requests are waiting, merge in dependency order — a pull request whose consumers would break without it goes first — then task-number order. After each merge, if a later pull request in the wave now conflicts, ask its worker (or a fresh worker) to rebase; do not resolve conflicts in the manager session beyond trivial lockfile or changelog conflicts, and say when you did.
- Delete the merged branch if the repository's policy does.

## 4. Mark done on MySpec

For each merged task: `get_spec_file` for the current `content_version`, `read_spec_file` for the body, flip that task's `- [ ]` to `- [x]`, keep every other byte, and `update_spec_file` with `expected_version`. On a conflict, take the new token, re-read, re-apply, retry. After the write, the event feed echoes a `spec_file.updated` frame carrying the returned `content_version`; ignore it. Add an indented note under the task with the pull request number: `  - Merged: PR #123 (<short sha>)`. One update per task is fine; batching all merged tasks into one update is better when several merged.

## 4b. Watch the merge land

A merge to the default branch starts the repository's push workflows. Arm one `Monitor` over `gh run list --branch <base>` filtered to the merge commit, report the outcome per workflow, and say what actually shipped: a published package version and tag, which environments the deploy covers, and which are left to the normal release path. A red post-merge run is reported at once; do not start the next wave until it is understood.

## 4c. Reconcile the spec with what shipped

When a bundle's last pull request merges, the spec should describe the code that exists. With the user's agreement, read each bundle document, and for every place the implementation deliberately diverged, rewrite that text and push one revision per file with `expected_version`:

- Keep acceptance-criterion numbers stable. Tests and comments cite `AR-012 AC2`; append new criteria at the end of an entry and broaden existing ones in place, never renumber or insert.
- Strikethrough belongs to `CR-` entries only. Correcting an `AR-` is a plain edit.
- Add a trailing `## Clarifications` section for decisions (why a transport differs, why a value is copied rather than imported) and a `## Known Gaps` section for what was accepted at merge and needs a follow-up change. Both are plugin conventions the platform tolerates; no metadata footer.
- A gap that needs code is a follow-up task, not a weakened requirement. Say which option you took.

## 5. Board and log

Update each registry entry (`pr`, `status`: `pr-open`, `merged`, `blocked`, `failed`). Re-derive the board (done, in flight, blocked, ready) and update `.specs/<bundle>/factory-run.md` with what merged, what was redispatched, and cost so far (sessions started this run, by path, and redispatches; that is the measurable unit). Post the board. For `--bg --worktree` workers whose task merged, clean up with `claude rm <id>` and `git worktree remove`.

## 6. Milestone gate

When the last task of a `## Milestone` is `[x]`:

1. Run the full test suite on the default branch (or ask the user to, when it needs infrastructure).
2. Run the `myspec-mcp:analyze` skill in convergence mode for the milestone's requirement ids; report coverage and any missing, partial, contradicting, or unrequested items.
3. Summarise the milestone: tasks merged, requirement ids satisfied, spec edits made, open questions, cost.
4. Offer to write the summary to `.specs/<bundle>/milestone-<M>.md` and `upload_attachment` it (absolute `file_path`) to the MySpec project.
5. Stop. Do not plan or dispatch the next milestone until the user says so.
