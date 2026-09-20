---
name: integrate
description: Collect factory worker pull requests, verify them against the task's acceptance criteria and the constitution, merge per the agreed policy, mark the task done on MySpec, and run the milestone gate. Use when the user says "integrate the wave", "merge the factory PRs", "what did the workers deliver", "mark task N done", or after every dispatched session in a wave has reported.
user-invocable: false
---

# Factory integrate

Tools are called as `mcp__plugin_myspec-mcp_myspec__<tool>`. This skill runs per pull request, not per wave: whenever the `watch` skill reports a worker's `factory-<bundle>-task-<N>-report.md` attachment, a pull-request monitor line shows a pull request approved and green, or on request. Start by reading `.specs/<bundle>/factory-sessions.json` (the session registry written by `dispatch`) to know which sessions and branches belong to this wave. Inputs: the wave's tasks and their pull requests, the `policy` the user agreed to at run start (merge method, autonomy level `ask-each` / `merge-on-gate` / `full`, required checks and reviewer), and the `content_version` of `tasks.md`. Writes to `tasks.md` follow the write-back protocol in the `myspec-mcp:implement` skill; the manager is the only writer.

The watch scripts live in the `watch` skill: `<plugin root>/skills/watch/scripts/`, where the plugin root is two directories above this skill's base directory.

## 1. Collect

Cloud workers may have pushed a branch without a pull request: `git fetch --prune` and `git branch -r --list 'origin/claude/*' 'origin/factory/*'`; for a branch whose worker reported a task number but no pull request exists, open one with `gh pr create --head <branch> --title "task N: <title>" --body-file <report>` using the report from the worker's final message. Then `gh pr list --state open --json number,title,headRefName,labels,isDraft,reviewDecision,statusCheckRollup,body` and match each pull request to a task by branch `factory/<bundle>/task-<N>` or title `task N:` (cloud sessions push `claude/`-prefixed branches, so the title match matters). A lane pull request (branch `factory/<bundle>/lane-<L>` or title `lane L:`) covers every task the `## Branch Plan` lists for that lane: verify each of them, and merge or hold the pull request as a whole. Read the `## Factory report` at the end of the body. A missing report means the worker did not finish; treat as failed. A draft pull request or a report whose first line starts with `BLOCKED:` is blocked, not ready.

## 2. Verify each pull request (read-only)

1. Checks: every required check green. Red: do not merge; redispatch per the `dispatch` skill's rules with the failing output in the brief.
   Red checks on a cloud worker that is still running: with Auto-fix on, give it a little time to answer the failure itself before intervening; otherwise steer it with `claude -p "<failing output>" --cloud <session_id>` (id from the registry) before redispatching. A pull request whose `autofix` is not `on` gets no automatic response once its session goes idle — turn it on or steer it.
   Reviews: when branch protection requires approvals, `reviewDecision` must be `APPROVED`; ask the user to review or approve. `CHANGES_REQUESTED`: collect the review comments (`gh pr view <n> --comments` and `gh api repos/{owner}/{repo}/pulls/<n>/comments`) and redispatch the worker with them in the brief; the manager never rewrites the code itself.
2. Acceptance criteria: for each criterion on the task and its `_Requirements:_` entries, find the test that names it (`grep -riE 'FR[-_]?003'` style) in the diff. Missing tests are a failure unless the report explains why the criterion cannot be tested automatically. So is a `- Revert checks:` report line that does not name every new or changed test.
   Delegate this to a read-only subagent: ask it to verify acceptance criteria based on code analysis alone, never running tests, builds, or the project. The subagent should read the implementation code and test files to return a criterion-by-criterion table with `file:line` or test-name evidence. For each criterion, the subagent must analyze the test code to determine whether the test would actually fail if the implementation were reverted or broken — contract tests that only check one direction, or assert on objects the test builds itself, give false confidence.
   For high-risk criteria (authorization defaults, concurrency, ordering, what is published before commit), the subagent must READ THE IMPLEMENTATION CODE directly to verify the behavior matches the requirement, not just confirm a test exists.
   When several branches build against one contract, compare them directly — the producer's payloads, service names and response wrappers against the consumer's structs and client code, field by field. Neither branch's CI can see a mismatch between them.
   After a worker pushes fixes, re-verify only the fix commits (`git diff <verified-sha>..<head>`), item by item, with evidence and whether each test would fail on revert. A fix that is only partial goes straight back with the remaining gap. A fix round also re-scans the WHOLE fix diff for production changes nobody asked for — a refactor, a moved component, a new portal or listener — and verifies each one as carefully as the original diff; unrequested changes made while fixing are where new regressions come from. Record the verified head sha in the registry entry (`verified_sha`) after every pass.
   Give every verification subagent the weakness checklist in `references/verification-checklist.md` and tell it to go through it for each new or changed test. Tell it to work in priority order (the production changes and high-risk criteria first, then test integrity, then scope) and to hand back a partial report with evidence rather than nothing if it runs long. A verification subagent that makes no progress for ten minutes, or is stopped by the stream watchdog, is discarded and relaunched once on the current head with the same prompt; never merge on the missing report.
3. Constitution: the diff introduces no forbidden technology, pattern, or security violation. Delegate a read-only diff review to a subagent when the diff is large; ask it to report gaps against the acceptance criteria and constitution, not style.
4. Scope: the diff touches only the modules and files the task named plus tests. Unrelated changes are reported back and the pull request is not merged until the worker removes them. For a lane, the diff also stays inside the lane's `Owns` list; any path from another lane is a finding, and each shared contract is compared field by field with the other lanes' branches.
5. Spec issues raised in the report (`BLOCKED: spec`, deviations): stop this lane, put the question to the user, and after the answer record it as `- Clarification:` under the task in `tasks.md` (or `## Clarifications` in `requirements.md` for requirement-level answers) before redispatching.
   Deviations are often NOT flagged as blocked: an extra fallback rung, a broader delete rule, an added service. Look for behaviour beyond the requirements in the diff and the report. Put each to the user with the trade-off (including what the reviewer recommends, if it differs), record the answer as a numbered Clarification, and tell the worker so it neither reverts a kept deviation nor keeps a rejected one. Under `policy.minor_defaults: manager`, decide a low-impact detail yourself as defined in the dispatch skill's `references/session-registry.md`, and record it the same way, marked `(manager default, owner may reverse)`.
6. Red checks: a failure is the branch's until shown otherwise. Before re-running, establish that the diff does not touch the failing test or its code path and that the same test has failed elsewhere (another branch, main); then re-run the failed job, send the worker that evidence if a reviewer blamed the branch, and record the flaky test for the regression task. A `CANCELLED` run superseded by a newer push is not a failure.
7. Reviewer stalls: first check that a review was requested at all (`gh pr view <n> --json reviewRequests`, or `review_requested` events in `gh api repos/{owner}/{repo}/issues/<n>/timeline`). If no request was made, request it yourself with `gh pr edit <n> --add-reviewer <reviewer>`: that keeps the agreed gate, it does not lower it. When a requested reviewer has not reviewed a green pull request for well over its usual time, run your own verification meanwhile, and put the choice — keep waiting, or merge on your verification — to the user rather than lowering the gate yourself.

## 2b. Reported defect in merged code

When a worker or verifier finds a confirmed defect in code that already merged (for example a test that fails against shipped code, pinned with `it.skip` or `it.fails`):

1. File a GitHub issue for it, or link the existing one, and cite it next to the pinned test.
2. Merge the pinning pull request if it is otherwise ready; the skipped test documents the bug. The pin alone is not a reason to hold it, and a Factory report `DEFECT:` line (the worker brief's protocol for this case) does not count as a `BLOCKED:` line for gate item 6.
3. Add a fix task in a new `## Milestone <next>` section of `tasks.md` (headings and numbering per §4c), depending on the pinning task.
4. At `full`, dispatch the fix task after one notice to the owner; at the other levels, ask first.

## 3. Merge per policy

**Ready-to-merge gate.** Re-check every item immediately before `gh pr merge`, from one fresh `gh pr view <n> --json headRefOid,mergeStateStatus,reviewDecision,reviews,statusCheckRollup,autoMergeRequest` plus the review-thread query:

1. The gating reviewer's latest approval is on the **current head** commit (`reviews[].commit.oid` == `headRefOid`). An approval on an earlier commit does not count, even when GitHub still shows `reviewDecision: APPROVED`.
2. Every required check is `SUCCESS` (or `SKIPPED`/`NEUTRAL`) on that head; nothing pending.
3. No unresolved review threads (`gh api graphql` on `reviewThreads { isResolved }`).
4. `mergeStateStatus` is `CLEAN` and `autoMergeRequest` is null.
5. Your own verification covers every change up to that head: the registry's `verified_sha` is the head, or the only commits after it touch docs or comments (check with `git diff --stat <verified_sha>..<head>`). Commits that touch tests get a pass with `references/verification-checklist.md` first (a test-only commit can drop an assertion or weaken a check), and anything touching production code gets a full re-verification.
6. No open spec question, deviation or `BLOCKED:` line on the pull request.
7. The tested tree is the merged tree. If the base branch gained commits touching the pull request's projects since the head's CI ran (`git diff --stat <head>...origin/<base> -- <paths the PR touches and their shared packages>`), update the branch (`gh pr update-branch <n>`), wait for CI on the new head, re-request review, and re-run the gate. Commits touching unrelated projects do not require this.

Whenever a worker pushes after an approval, request the review again at once (`gh pr edit <n> --add-reviewer <reviewer>`, then confirm `reviewRequests` lists it) instead of waiting for the worker to do it; a `pr-watch.sh` armed with `--rerequest` does this for you. A watch line with `review=APPROVED` is not the gate; `approved_head=yes` is item 1. When all seven hold: at `merge-on-gate` or `full`, merge without asking and report it; at `ask-each`, present the evidence and ask with `AskUserQuestion`.

- Merge with `gh pr merge <n> --squash|--merge --match-head-commit <verified sha>` as agreed, so a push that lands after the gate check makes the merge fail instead of merging unverified code. Never `--admin`, never `--auto`, never a force push. Auto-merge is out of bounds in every form — the `--auto` flag, GitHub's auto-merge toggle, and merge queues — because a merge must be decided by the manager under the agreed policy or by the user, at the moment the evidence is in front of them. If a pull request arrives with auto-merge already enabled, turn it off before verifying and say so.
- Absent branch protection (`gh api repos/{owner}/{repo}/branches/<base>/protection` returns 404) nothing stops a merge; that is a reason to hold to the agreed policy, not to skip it. Say when the base is unprotected, since then a green `reviewDecision` is the only gate.
- **Merge one pull request at a time, and wait for its post-merge CI/CD to finish before merging the next.** Never merge several pull requests back to back, even when all are approved and green. Push workflows on the default branch build and deploy per merge commit; runs triggered seconds apart race, and a slower run for an OLDER commit can finish last — overwriting a mutable image tag such as `:latest` and redeploying older code over newer code. (Observed: two platform merges 2 s apart left the deployment running the older commit's image until the newer run was re-run.) After each merge:
  1. Watch `gh run list --branch <base> --json name,status,conclusion,headSha` filtered to that merge commit until every run is `completed`.
  2. Any failure: stop merging, report, and do not merge the next pull request on a red default branch.
  3. Only then re-check the next pull request is still on its approved head and `CLEAN` (it may need a rebase after the previous merge) and merge it.
- **Merge a pull request as soon as it is ready; do not hold it for the rest of the wave.** Ready means verified, approved, green and within the agreed merge policy (asking the user first when the policy says so). The only reason to hold a ready pull request is a dependency on another pull request that has not merged yet — its code calls, consumes or deploys against something only that other pull request provides (for example tools or clients that answer 501 until the platform pull request ships). Record the dependency in the registry entry's `notes` and merge it right after the one it waits for.
- When several ready pull requests are waiting, merge in dependency order — a pull request whose consumers would break without it goes first — then task-number order. After each merge, if a later pull request in the wave now conflicts, ask its worker (or a fresh worker) to rebase; do not resolve conflicts in the manager session beyond trivial lockfile or changelog conflicts, and say when you did.
- Delete the merged branch if the repository's policy does.

## 4. Mark done on MySpec

For each merged task: `get_spec_file` for the current `content_version`, `read_spec_file` for the body, flip that task's `- [ ]` to `- [x]`, keep every other byte, and `update_spec_file` with `expected_version`. On a conflict, take the new token, re-read, re-apply, retry. After the write, the event feed echoes a `spec_file.updated` frame carrying the returned `content_version`; ignore it. Add an indented note under the task with the pull request number: `  - Merged: PR #123 (<short sha>)`. One update per task is fine; batching all merged tasks into one update is better when several merged. A merged lane pull request marks every task of that lane in one update, each with its own `Merged:` note.

## 4b. Watch the merge land

A merge to the default branch starts the repository's push workflows. Arm one `Monitor` on the tested script rather than writing a loop by hand:

```
Monitor({
  command: "<plugin root>/skills/watch/scripts/postmerge-watch.sh <clone> <merge-sha> <base>",
  description: "post-merge runs on <base> for <merge-sha> (PR #<n>)",
  timeout_ms: 3600000
})
```

It prints one line per change and exits by itself once the same finished set is seen on two polls in a row: `post-merge-complete` with exit 0 when every run succeeded (or was skipped), exit 1 with a `failed:` line when any run failed, and exit 3 (`post-merge-watch-timeout`) after 60 polls — which is also where a merge that triggers no push workflow ends, after `no runs yet`. A `github-unreachable` or `no runs yet` line is not a result — check `gh run list` directly before saying anything. The Monitor window ends before the script does; re-arm it on expiry. The script sees only runs whose head is the merge commit: a deploy chained with `workflow_run` after another workflow may not carry that head, so check such deploys with `gh run list` when the repository has them. Report the outcome per workflow and say what actually shipped: a published package version and tag, which environments the deploy covers, and which are left to the normal release path. A red post-merge run is reported at once; do not start the next wave until it is understood.

At `full` autonomy, when this merge was the last thing the next wave or lane of the SAME milestone was waiting for (including a planned split such as "PR 2 after PR 1 is merged and deployed") and every run is green, hand over to `dispatch` for it straight away and report the dispatch together with the deploy result. Work in a later milestone never starts this way; it waits for the milestone gate (§6), whose only exceptions at `full` are test-only follow-ups and a fix task for a reported defect (§2b).

## 4c. Reconcile the spec with what shipped

When a bundle's last pull request merges, the spec should describe the code that exists. With the user's agreement, read each bundle document, and for every place the implementation deliberately diverged, rewrite that text and push one revision per file with `expected_version`:

- Keep acceptance-criterion numbers stable. Tests and comments cite `AR-012 AC2`; append new criteria at the end of an entry and broaden existing ones in place, never renumber or insert.
- Strikethrough belongs to `CR-` entries only. Correcting an `AR-` is a plain edit.
- Add a trailing `## Clarifications` section for decisions (why a transport differs, why a value is copied rather than imported) and a `## Known Gaps` section for what was accepted at merge and needs a follow-up change. Both are plugin conventions the platform tolerates; no metadata footer.
- A gap that needs code is a follow-up task, not a weakened requirement. Say which option you took.
- Every new or changed SHALL or behaviour statement drafted from a convergence report (requirements, Clarifications, Known Gaps) is checked against the code by the read-only verifier, with `file:line`, before upload. An unverified statement is not written. (Observed: a Clarification promised behaviour the loader did not have, and the next worker spent a round `BLOCKED` on it.)
- Heading and numbering rules for `tasks.md`: never renumber an existing task or milestone heading, and never create two headings with the same milestone number and text. Follow-up work goes into a NEW `## Milestone <next number>: Convergence` section placed just before `## Dependency Graph`, with task numbers continuing after the highest existing task. A misplaced older convergence record keeps its original milestone number and gets a distinct heading (for example `## Milestone 4: Convergence record (checked at <sha>)`) when it is moved above the dependency graph. After adding tasks, update every overview count the file states (task and milestone totals, complexity totals, the mermaid graph, the branch table, the dependency-graph prose, any "every id appears" claim).

**Draft with a subagent, write it yourself.** Large document edits (reconciliation, new clarifications, follow-up tasks) go to one drafting subagent that edits working copies under `.specs/<bundle>/draft/` only — never MySpec, never the repository. Copy the current platform revisions into `draft/` first. Give it the decisions, the evidence (file:line), and the rules above, and require these self-checks in its reply:

1. Every `### (AR|BR|CR)-…` heading is cited by at least one task's `_Requirements:_`, and every cited id exists as a heading (report the deliberate exceptions, such as struck entries still cited by shipped tasks).
2. Every `_Dependencies:_` number exists; no cycles.
3. No checkbox of an existing task changed, and no existing task was renumbered (diff the task lines against the platform copy).
4. No `TBD`, `TODO` or placeholder text.
5. The judgement calls it made, listed separately, so you can put any that change behaviour to the user.

Re-run checks 1-3 yourself on the drafts before writing, then write each file with `update_spec_file` and `expected_version` from a `get_spec_file` made just before, in dependency order (proposal, then requirements, then tasks), and expect each write's `spec_file.updated` echo on the feed.

## 5. Board and log

Update each registry entry with `registry.py … set --session <task> pr=<n> status=<pr-open|merged|blocked|failed>` (and `verified_sha=<sha>` after each verification pass; usage in the dispatch skill's `references/session-registry.md`), never by editing the JSON by hand. Re-derive the board (done, in flight, blocked, ready) and update `.specs/<bundle>/factory-run.md` with what merged, what was redispatched, and cost so far (sessions started this run, by path, and redispatches; that is the measurable unit). Post the board. For `--bg --worktree` workers whose task merged, clean up with `claude rm <id>` and `git worktree remove`.

## 6. Milestone gate

When the last task of a `## Milestone` is `[x]` (for a `tasks.md` with a `## Branch Plan`, lanes span every milestone and run at once, so run this gate once, after the last lane's pull request merges, over all milestones):

Do the whole gate in one pass, in parallel where the steps are independent, and ask the user once at the end:

1. Run the full test suite on the default branch through a test-runner subagent (or ask the user to, when it needs infrastructure). Give it every setup step of each project's pull-request CI job, in order (installs of sibling and shared packages, toolchain setup such as bun), not only the test command; without them every test fails at import. Launch it together with step 2.
2. Run the `myspec-mcp:analyze` skill in convergence mode for the milestone's requirement ids, through a read-only subagent; report coverage and any missing, partial, contradicting, or unrequested items, and whether every recorded Clarification matches the shipped code.
3. Write the summary to `.specs/<bundle>/milestone-<M>.md` (tasks merged with PRs and merge shas, requirement ids satisfied, spec decisions taken (listing every `(manager default, owner may reverse)` Clarification), verification findings fixed before merge, convergence result, open items, cost) and upload it with `upload_attachment` (absolute `file_path`, `file_name` `factory-<bundle>-milestone-<M>.md`, `override: true`). Uploading a summary is not a spec change and needs no question.
4. Draft (with the drafting subagent in §4c, into `draft/` only) the document reconciliation for every accepted deviation and a new `## Milestone <next>: Convergence` section with one small task per open item that needs code, each depending only on the last task of this milestone so they can run in any order.
5. Ask ONE `AskUserQuestion` call covering what needs the user: whether to write the reconciliation to MySpec, and whether to dispatch the follow-up tasks that change production code (at `full`, dispatching them is the recommended option; at the other levels, ask). At `full`, follow-ups that are all test-only (no production code) are dispatched without the question, after reporting them; a production follow-up in the set sends it to the question. At the other levels, test-only follow-ups are offered once, as optional, in the question. Then act on the answers without further questions.
6. When nothing is left in flight, revoke the stream token and stop every Monitor; mint a fresh one when work resumes. Do not keep re-arming watches over an idle factory.

**Closing the bundle.** When the gate of the bundle's last milestone yields no follow-up that changes production code, close the bundle once the test-only follow-ups (dispatched at `full`, or offered as optional) are settled: final `myspec-mcp:analyze`, the summary, revoke the token, stop. A convergence milestone is not followed by another convergence milestone unless it exposed a production defect (§2b).
