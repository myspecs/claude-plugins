---
name: dispatch
description: Spawn one Claude Code worker session per ready factory task (or per lane of a manager-planned tasks.md) with a self-contained brief. Use when the user says "dispatch the wave", "start the workers", "spawn sessions for these tasks", "run task N in the cloud", "start the lanes", or after the plan skill has produced a wave or lanes. Cloud sessions first (claude --cloud or a remote subagent), local git worktree sessions as fallback. Never implements a task in the manager session.
user-invocable: false
---

# Factory dispatch

Inputs: an approved wave from the `plan` skill, and the run `policy` in `.specs/<bundle>/factory-sessions.json` (concurrency cap, cloud allowed, autonomy level). At `ask-each` and `merge-on-gate`, confirm each wave with one `AskUserQuestion` before starting sessions; at `full`, dispatch without asking and report what you started. Brief template: `references/worker-brief.md`. Mechanics per path: `references/cloud-vs-local.md`. Session bookkeeping: `references/session-registry.md`. Scripts: `<plugin root>/skills/dispatch/scripts/` (`build-brief.py`, `registry.py`) and `<plugin root>/skills/watch/scripts/`, where the plugin root is two directories above this skill's base directory.

## 1. Build one brief per task

A worker starts with zero context. Each brief must contain, inline: repository and default branch; the task block verbatim; every acceptance criterion; the text of each cited FR/NFR (or AR/CR, or OpenSpec requirement and scenarios); the constitution sections that bind the work (Technology, Architecture, Testing, Coding Standards, Security); the solution module excerpts the task touches; the output contract (branch, pull request title and body, `## Factory report`, blocked protocol); and the rule that the worker must not edit `tasks.md` or any spec file. Build the verbatim part with the script instead of copying by hand. Download the bundle files first (`download_spec_file`), then run:

```
python3 <plugin root>/skills/dispatch/scripts/build-brief.py --bundle-dir .specs/<bundle> --tasks 45,46,47 [--requirements <ids>] [--clarifications Q24,Q26] [--out <scratchpad>/brief-<N>.md]
```

It emits `## Tasks (in order)` (each task block verbatim), `## Requirements these tasks satisfy (verbatim)` (the ids given plus every id the tasks cite), `## Decisions already made` (the named Clarification rows) and, for a greenfield bundle, the Constitution section. Write the rest of the brief around it from `references/worker-brief.md`; keep the brief under roughly 400 lines by excerpting rather than pasting whole documents (a branch worker owning a long task chain may need more; cut proposal prose before acceptance criteria).

Brief checks that have cost a review round when skipped:
- Include every requirement id the acceptance criteria or implementation notes reference, not only the `_Requirements:_` line — a missing priority or ordering rule sends the worker to guess.
- List the test, lint and typecheck commands of every project the task may touch, taken from that project's pull-request workflow, together with ALL setup steps of that job, in order: dependency installs of sibling and shared packages, toolchain setup (for example bun). Running only the project's own install makes every test fail at import.
- Paste the numbered items of `<plugin root>/skills/integrate/references/verification-checklist.md`, except those marked verifier only, into the brief's `## Self-check before the PR` section. The worker runs in the target repository and cannot read the plugin.
- Keep the template's `## Test rules`, the revert-check step and the `- Revert checks:` report line in every brief; they are what stops review rounds that only fix tests.
- State the production rule: nothing fake, stubbed, or half-wired may become reachable in a production build. A consumer built ahead of its provider stays hidden or inert until the integration task wires it.
- Build a `## What already shipped (use it, do not rebuild it)` section from the registry's `contract_notes` and the `Notes for the manager` of every merged Factory report in this bundle: wire shapes, new SDK names, service and subject names, migrations, test helpers and fakes the task can reuse. Do not retype it from memory; read the registry.
- Name the reviewer whose approval gates the merge (for example the review bot) and tell the worker to request that review as soon as the pull request exists. Workers skip it when the brief only says to re-request review after fixes.
- Give every decision in the spec a place in the brief: the owner's Clarifications that bind the task, verbatim, under `## Decisions already made (do not re-decide)`.
- **Decision points.** When a task might need something the spec freezes or the owner has not decided — a response-shape change, a new public API symbol, a second query, a dependency, a migration beyond the one planned — add a `## Stop and report` section naming each such point and the exact condition: "if the fix needs X, do not implement it; report `BLOCKED: spec - <question with the options and your recommendation>` for that task and finish the others". A task marked as a decision in `tasks.md` (keep or change, A or B) states which way the worker must report its choice in the Factory report.

### Multi-task briefs (one worker, several tasks, one pull request)

When a sequential chain of tasks ships as one pull request (a milestone that `tasks.md` assigns to one agent, a PR split such as "PR 1 = tasks 28, 29, 35", or a convergence milestone), write one brief for the whole chain with the multi-task variant in `references/worker-brief.md`: every task verbatim in order, one commit per task, one pull request titled `task <N1>, <N2>, …: <summary>`, and a blocked rule that says whether a stuck task blocks the ones after it (a dependency chain) or only itself (independent follow-ups). Record one registry entry with `task` set to the list, for example `"28,29,35"`.

### Lane briefs (bundles with a `## Branch Plan`)

When `tasks.md` has a `## Branch Plan` section (a manager-planned brownfield bundle), build one brief per lane instead of per task and dispatch every lane at once; the concurrency cap was already applied when the lanes were planned. A lane brief carries, on top of the above: every task of the lane verbatim in the plan's order; the lane's `Owns` and `Does not touch` lists; each shared contract in full; branch `factory/<bundle>/lane-<L>`; one commit per task in order (`feat: task <N> <title> (<ids>)`); one pull request titled `lane <L>: tasks <N1>, <N2>, …` whose Factory report lists every task; and the report attachment name `factory-<bundle>-lane-<L>-report.md`. The brief's first line is `factory <bundle> lane <L>: <lane name>`. Use `--worktree lane-<L>` for local workers. Record one registry entry per lane with its `lane` number and `tasks` list.

## 2. Preflight, once per wave

Before the first cloud dispatch, in the **local clone of the target repository** (not the manager's own working directory):

1. `cd <clone> && git remote -v && git status -sb` — confirm it is the right repository and note the branch. Ask the user for the path when no clone is at hand; never dispatch from a directory whose remote you have not just read.
2. Confirm the base branch is pushed: `git fetch origin <base> && git rev-parse HEAD origin/<base>`. The cloud clones the GitHub remote, not the local checkout, so unpushed commits and uncommitted files do not reach the worker — say so when the checkout is dirty.
3. Write each brief to a file in the scratchpad. Briefs are passed as `"$(cat <file>)"`, never inlined.

## 3. Choose the path

| Order | Path | When |
|---|---|---|
| 1 | Agent tool with `isolation: "remote"` | Available in this build and the user allowed cloud dispatch. Runs in the background; its completion arrives as a notification |
| 2 | `claude --cloud` under a pseudo-terminal | Remote subagent unavailable, or the user asked for the CLI. `--cloud` **requires a TTY** and exits 1 in a plain background Bash call, so dispatch with `cd <clone> && script -q <typescript> claude --cloud "$(cat <brief>)" </dev/null` (see `references/cloud-vs-local.md`). Steer a running session with `claude -p "<message>" --cloud <session_id>` |
| 3 | Agent tool with `isolation: "worktree"` | Cloud not allowed or unavailable. Background subagent in its own worktree; results return as a notification |
| 4 | `cd <clone> && claude --bg "<brief>" --worktree task-<N> --permission-mode auto` via Bash | When a separate process is preferred. The prompt is positional (`--bg` and `-p` conflict) and `--permission-mode auto` keeps the worker unattended; monitor with `claude agents --json` |

Every command that starts or steers a cloud session begins with `cd <clone> &&`; the Bash tool's working directory does not carry over between calls.

Never exceed the concurrency cap. Never dispatch two tasks that share files in the same wave, or two lanes whose `Owns` lists overlap.

## 4. Dispatch and record

For each task, start the session, then immediately, before starting the next one:

1. Capture the session id and URL from the command output (`Created cloud session:`, `Session ID:` and `View:` lines, or `--output-format json`) or the agent id from the tool result, per `references/session-registry.md`. Strip terminal escapes before matching. With Remote Control connected, also run `ListAgents` once the session appears and record its listing name (`agent_name`) — the cloud rewrites the title, so it is rarely the brief's first line verbatim.
2. Append an entry to `.specs/<bundle>/factory-sessions.json` with `registry.py … add-session --task --title --path --session-id --url --branch --started-at` (usage in `references/session-registry.md`), never by editing the JSON by hand. This file is how the manager finds the session again to steer it; a dispatch whose id could not be captured is recorded with `session_id: null` and the user is asked for the URL.
3. Add a line to the run log `.specs/<bundle>/factory-run.md` (`registry.py … log --run-log <path> "<text>"`).
4. Arm one `Monitor` per pull request on the tested script, not a hand-written loop:

   ```
   Monitor({
     command: "<plugin root>/skills/watch/scripts/pr-watch.sh <clone> \"task <N>\" --since <started_at> --reviewer <policy.reviewer> --rerequest",
     description: "factory <bundle> task <N> branch, PR, checks and review state",
     timeout_ms: 3600000
   })
   ```

   Use how the pull request title will start (`"task 28"`, `"task 30, 31"`, `"lane 2"`) and the session's `started_at` from the registry. The script reports `claude/*` and `factory/*` branches whose tip is newer than `--since`, so a re-armed watch still shows the worker's branch; prints one line per change; adds `approved_head=yes|no|none` for the reviewer (the gate is `approved_head=yes`, not `review=APPROVED`); with `--rerequest`, re-requests that reviewer when the head moves and no request is pending (`re-requested review from <login> on <sha>`); prints `github-unreachable (…)` when a GitHub call fails (the state is unknown, not empty — never report "no branch" or "no PR" from such a line), and exits by itself once the pull request is merged or closed. Re-arm it on expiry without telling the user, and check the state directly whenever it expires with no events.
5. Confirm Auto-fix is on for each pull request as it appears (the brief asks the worker to enable it). If a worker reports it unavailable, or the pull request was opened by the manager, turn it on with a message to the session — `claude -p "watch PR #<n> and auto-fix CI failures and review comments" --cloud <session_id>` — or `/autofix-pr` from the branch. Record it with `registry.py … set --session <task> autofix=on`. See `references/worker-channels.md` for what Auto-fix does and does not cover.

Post the updated board to the user with the session URLs.

## 5. Hand over to integrate

Run the `integrate` skill for each pull request as it becomes ready (notification, `claude agents`, or a pull request turning approved and green); do not wait for the whole wave, and merge any ready pull request that depends on no unmerged pull request straight away. Do not start the next wave until every session in this one has merged or reported blocked. At `full` autonomy, start it as soon as that holds and the post-merge runs it depends on are green (`integrate` §4b); a split such as "PR 2 after PR 1 is merged and deployed" is dispatched the moment PR 1's deploy turns green. A pushed branch is not a finished worker: cloud sessions keep committing after the first push, so wait for the pull request, or for commits to have stopped, before treating the lane as done.

## Channels to a running worker

`references/worker-channels.md` lists every way the manager can talk to, watch, or take over a worker session, with what each one proves. Read it before improvising a check.

## Relaying between workers

Read each `## Factory report` and each first push as it lands. When one worker's output fixes something another in-flight worker must match — an internal event payload, a service or subject name, a response wrapper, the unit of an offset, an error `reason` — send that worker the exact facts with `SendMessage` straight away, and record them under `contract_notes` for later briefs (`registry.py … contract <key> "<fact>"`). Couplings found only at integration cost both branches a rework.

## Steering instead of redispatching

For a cloud worker that is still running, prefer one follow-up over a fresh session. Two channels, in order:

1. `SendMessage` (needs this session connected to Remote Control): run `ListAgents`, find the worker's row (labelled `cloud`; its name is the session title, which is why every brief starts with the line `factory <bundle> task <N>: <title>` or `factory <bundle> lane <L>: <lane name>`), and send the message to that name (append the `[ref]` only when the listing shows one). Cloud sessions receive messages but cannot message back, so ask the worker to answer through its pull request or branch, not in a reply.
2. `claude -p "<failing check output or review comment>" --cloud <session_id>` with the id from `.specs/<bundle>/factory-sessions.json`, when Remote Control is not connected or the session has fallen off the bounded listing.

Record the message and the channel with `registry.py … note --session <task> "<text>"`. Redispatch only when the session has ended, expired, or reported `BLOCKED`; append a new registry entry and mark the old one `redispatched` (`set --session <index> status=redispatched`).

## Redispatch rules

- A worker that reports `BLOCKED: spec` (ambiguous or contradictory spec) means the spec gate missed a gap: stop its lane and pause all new dispatch. Under `policy.minor_defaults: manager`, a low-impact detail is decided by the manager instead (see `references/session-registry.md`); otherwise the manager asks the user, records the answer under the task in `tasks.md` as `- Clarification:`, re-runs the spec gate, then redispatches.
- A worker that fails (red checks, no pull request, timeout) is redispatched once with the failure output added to the brief. A second failure stops the lane and is reported. Two consecutive failures across the wave stop dispatching until the user decides.
- A worker or verifier that finds a confirmed defect in already-merged code follows the reported-defect path in `integrate` §2b: the pinning pull request merges, and the fix is a new task, not a redispatch.
