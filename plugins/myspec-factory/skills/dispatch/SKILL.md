---
name: dispatch
description: Run the factory's team of engineer agents. Groups related factory tasks, divides the groups evenly by size between a fixed team of long-lived Claude Code agent sessions (one per agent, for the whole run), names each agent (Ada, Linus, …) and sets its session title to that name, starts each agent with a self-contained brief and its first group, and sends each next group as an assignment message when the agent is free; rebalances queues when an agent runs dry and replaces an agent's session after a failure. Use when the user says "start the team", "start the agents", "divide the tasks between the agents", "assign the next tasks", "rebalance the agents", "replace agent a2", "name the agents", "the session title is wrong", "group these tasks into one assignment", "run task N in the cloud", or after the plan skill has produced the team plan. Cloud sessions first (claude --cloud), local claude --bg sessions as fallback. Never implements a task in the manager session.
user-invocable: false
---

# Factory dispatch: the team

The manager runs a **team**: `policy.team_size` engineer agents, each one long-lived Claude Code session for the whole run. The manager divides the work evenly between them, keeps each agent's queue, and hands an agent one group of related tasks at a time (an **assignment**: one branch, one pull request). Agents work in parallel; when one runs dry, the manager rebalances.

Inputs: the team plan from the `plan` skill (groups, weights, queues), the task board, and the run `policy` in `.specs/<bundle>/factory-sessions.json` (team size, cloud allowed, autonomy level). At `ask-each` and `merge-on-gate`, confirm the team plan (agents, queues, rungs, cost) with one `AskUserQuestion` before starting agents, and confirm each later assignment with the user; at `full`, start and assign without asking and report what you did. References: agent brief and assignment message `references/worker-brief.md`; paths `references/cloud-vs-local.md`; model and effort `references/model-and-effort.md`; registry `references/session-registry.md`; agent ↔ manager channel the `board` skill. Scripts: `<plugin root>/skills/dispatch/scripts/` (`build-brief.py`, `registry.py`) and `<plugin root>/skills/watch/scripts/`, where the plugin root is two directories above this skill's base directory.

## 0. Group related tasks

Always give one assignment as many related tasks as it can take: one group, one branch, one pull request. One brief section and one review round for several tasks cost far less than one per task, and tasks that touch the same code never conflict across branches. A group with a single task is the exception, used only when no other task relates to it.

1. Start from each ready task of the current milestone, lowest number first, as a new group.
2. Add every task related to a task already in the group:
   - it depends on a task in the group, and all its other `_Dependencies:_` are done or also in the group (a chain runs start to finish in one assignment, without waiting for merges in between);
   - a task in the group depends on it and it is ready;
   - it touches the same module or file (from the `_Requirements:_` modules and the files named in its implementation details);
   - it implements the same requirement ids or the same feature.
3. Repeat step 2 until nothing more attaches. Merge groups that end up sharing a task, a module or a file.
4. Weigh each group: the sum of its tasks' `_Complexity:_` — Small 1, Medium 2, Large 3; a task without one counts 2. This is the only place the weights are defined.

Limits that always win over grouping:

- Never cross a milestone. A group holds tasks of the current milestone only; the next one waits for the milestone gate.
- Keep a split that `tasks.md` declares (for example "PR 2 after PR 1 is merged and deployed"); group only inside each declared part. An older bundle's `## Branch Plan` (written by myspec-factory 1.x) declares its lanes: each lane is one group.
- Decision tasks get no assignment (`plan` §3b).
- A contract freeze task that several groups build on goes first, alone or with its own chain, unless those groups merge into one.
- A long assignment is a reason to excerpt harder, never to split a group.

Two groups that share a file are one group, so they always land on one agent and never run at the same time.

## 0b. Divide the groups between the agents

This section is the one source of truth for team size, division and rebalancing.

**Team size.** The user sets `policy.team_size` at run start (the output style's run loop). Recommend the number of groups that can run at the same time in the current milestone (groups with no unmerged dependency on each other), capped by what the user is willing to spend; never start an agent whose queue would be empty. A small change is one agent.

**Division**, once per milestone (at run start, then after each milestone gate):

1. Order the groups: a group others depend on comes first, then by milestone, then by lowest task number.
2. Take them in that order. A group that depends on a group already in an agent's queue goes to that agent (chain affinity) unless that would put the agent more than 3 (one Large task) above the average load; otherwise it goes to the agent with the lowest load (ties: the lowest agent number).
3. Each agent's rung (`references/model-and-effort.md`) is the highest rung over its queue. When one group needs a much higher rung than the rest, put it on one agent and keep the light groups off that agent where the balance allows.
4. Show the team table (agent with its name from §3a, queue in order, weight, rung) together with the task board. Record it: `registry.py … add-agent … --queue <group> …` for each agent as it starts (§4), or `registry.py … queue --agent a<k> <group> …` for a team that is already running.

**The manager keeps the queues; agents see one assignment at a time.** An agent's brief carries only its first group; each later group arrives as an assignment message when the agent is free (§5). Queues are a plan, so they can change: a spec change, a failed group, or rebalancing.

**When an agent is free.** An agent is free when its current assignment's pull request is open with the review requested (it may start the next group while the review runs; review fixes come first), or merged. Then:

1. Its next queued group whose dependencies are all merged, or depend only on this agent's own open pull request (then the assignment carries `## Stacked on PR #<p>`), is its next assignment.
2. Nothing ready in its queue: **rebalance**. Take the heaviest group that is ready and not started from the queue of the agent with the highest remaining load, provided the free agent's rung is at least that group's rung: `registry.py … move --group <tasks> --to a<k>`, then assign it. Log the move in `factory-run.md` and update both agents' board cards.
3. Nothing ready anywhere (everything left waits on another agent's unmerged pull request, or the milestone is done): the agent stays idle (`registry.py … agent --agent a<k> status=idle`). It costs nothing while idle; the next merge or the milestone gate wakes it with an assignment.

At most two assignments are open per agent: one pull request in review and one group in progress. Never give a free agent a group that another agent's in-flight assignment shares a file with; §0 already puts such tasks in one group.

## 1. The agent brief and the assignment message

An agent starts with zero context, and a cloud agent cannot read the plugin. Two texts carry everything, both from `references/worker-brief.md`:

- **Agent brief** (sent once, when the agent starts): repository and default branch; setup, test, lint and typecheck commands; the constitution sections that bind the work (Technology, Architecture, Testing, Coding Standards, Security); test rules, Definition of done, self-check, Factory report, where it goes, the factory board section, Auto-fix, review round, the rules for working on several assignments, the cannot-finish rules; then the first assignment.
- **Assignment message** (each later group, sent as the doorbell): first line `Software Factory Manager: assignment a<k>-<n> for <name>: task <N1>, <N2>, …: <summary>`; every task block verbatim in dependency order; the requirements and decisions they cite; `## What already shipped`; `## Stop and report`; `## Stacked on PR #<p>` or `## Release hold` when they apply; branch, pull request title, and the blocked rule for each task.

Build the verbatim part of both with the script. Download the bundle files first (`download_spec_file`), then:

```
python3 <plugin root>/skills/dispatch/scripts/build-brief.py --bundle-dir .specs/<bundle> --tasks 45,46,47 [--requirements <ids>] [--clarifications Q24,Q26] [--no-constitution] [--out <scratchpad>/a<k>-<n>.md]
```

It emits `## Tasks (in order)`, `## Requirements these tasks satisfy (verbatim)`, `## Decisions already made` and, for a greenfield bundle, `## Constitution (binding)`. Pass `--no-constitution` for an assignment message: the agent brief already carries it. Keep the agent brief under roughly 400 lines and each assignment message under roughly 250 by excerpting rather than pasting whole documents (cut proposal prose before acceptance criteria).

Checks that have cost a review round when skipped:
- Include every requirement id the acceptance criteria or implementation notes reference, not only the `_Requirements:_` line — a missing priority or ordering rule sends the agent to guess.
- List the test, lint and typecheck commands of every project the team may touch, taken from that project's pull-request workflow, together with ALL setup steps of that job, in order: dependency installs of sibling and shared packages, toolchain setup (for example bun). Running only the project's own install makes every test fail at import. An assignment that touches a project the agent brief did not list adds its commands.
- Paste the numbered items of `<plugin root>/skills/integrate/references/verification-checklist.md`, except those marked verifier only, into the agent brief's `## Self-check before the PR` section.
- Keep the template's `## Test rules`, the revert-check step and the `- Revert checks:` report line; they are what stops review rounds that only fix tests.
- State the production rule: nothing fake, stubbed, or half-wired may become reachable in a production build. A consumer built ahead of its provider stays hidden or inert until the integration task wires it.
- Build each assignment's `## What already shipped (use it, do not rebuild it)` from the registry's `contract_notes` and the `Notes for the manager` of every merged Factory report in this bundle, including other agents' work merged since this agent started. Do not retype it from memory; read the registry.
- Name the reviewer whose approval gates the merge and tell the agent to request that review as soon as each pull request exists.
- Keep the template's `## Where the Factory report goes`: on the pull request, copied to the agent's board report. Never tell an agent to upload it to MySpec with `upload_attachment`.
- A group that builds on a pull request that has not merged yet gets `## Stacked on PR #<p>`, with the parent's branch and its head sha; a change that may ship only after something reaches production gets `## Release hold`. Record both on the assignment (§4).
- Give every decision in the spec a place: the owner's Clarifications that bind the group, verbatim, under `## Decisions already made (do not re-decide)`.
- **Decision points.** When a task might need something the spec freezes or the owner has not decided — a response-shape change, a new public API symbol, a second query, a dependency, a migration beyond the one planned — add a `## Stop and report` section naming each such point and the exact condition: "if the fix needs X, do not implement it; ask it on the board as a `question` (without a board: report `BLOCKED: spec - <question with the options and your recommendation>`) for that task and finish the others". A task marked as a decision in `tasks.md` states how the agent reports its choice in the Factory report.

Naming: branch `factory/<bundle>/tasks-<N1>-<N2>-…` (`factory/<bundle>/task-<N>` for one task); one commit per task; pull request title `task <N1>, <N2>, …: <summary>` (`task <N>: <title>`), plus a split name when `tasks.md` declares one (`task 30, 31, 32: floating panel (PR 2)`). A cloud session pushes its own `claude/`-prefixed branch instead, which is why the title carries the task numbers.

## 1a. Choose each agent's model and effort

An agent runs with one rung for its whole session: the highest rung its queue needs (`references/model-and-effort.md`), `opus`/`medium` by default. Never `sonnet` above `medium`. Show the rung in the team table and pass it when the agent starts (§3). Rebalancing never moves a group to an agent with a lower rung than the group needs.

## 2. Preflight, once per run (and again after a base-branch problem)

Before the first agent starts, in the **local clone of the target repository** (not the manager's own working directory):

1. `cd <clone> && git remote -v && git status -sb` — confirm it is the right repository and note the branch. Ask the user for the path when no clone is at hand; never dispatch from a directory whose remote you have not just read. The clone must be a folder Claude Code already trusts (opened once interactively): `claude --cloud` stops at the folder-trust dialog in an untrusted folder, such as a fresh clone in the scratchpad.
2. Confirm the base branch is pushed: `git fetch origin <base> && git rev-parse HEAD origin/<base>`. The cloud clones the GitHub remote, not the local checkout, so unpushed commits and uncommitted files do not reach an agent — say so when the checkout is dirty.
3. Write each brief and assignment message to a file in the scratchpad. They are passed as `"$(cat <file>)"`, never inlined.
4. Once per run, before the first agent starts: find the repository's factory board (`registry.py … board`, then `Artifact` `list`) and start the run on it; publish one only when none exists (`board` skill §1-§3). No Artifact tools, or a refused publish: run without a board and drop the brief's `## Factory board` section.

## 3. Choose the path

An agent lives for the whole run, so the path must let the manager send it the next assignment:

| Order | Path | When | Next assignment through |
|---|---|---|---|
| 1 | `claude --cloud` under a pseudo-terminal | The default, whenever the user allowed cloud dispatch | `claude -p "$(cat <file>)" --cloud <session_id>` |
| 2 | `cd <clone> && claude --bg "<brief>" --name "<title>" --worktree a<k> --model <model> --effort <effort> --permission-mode auto` via Bash | Cloud not allowed or refused, or the user asked for local agents | `SendMessage` to its `agent_name` from `ListAgents` |

`claude --cloud` **requires a TTY** and exits 1 in a plain background Bash call, so start an agent with `cd <clone> && script -q <typescript> claude --cloud "$(cat <brief>)" --name "<title>" --model <model> --effort <effort> --permission-mode auto </dev/null` (`<title>` from §3a; the brief must come right after `--cloud`, which takes it as its value; other flags go after the brief or before `--cloud`; details in `references/cloud-vs-local.md`). A cloud agent that finished its turn and sits idle wakes on `claude -p … --cloud <id>`, acts on it, and can open a second branch and pull request in the same session (checked on 2026-11-06 with Claude Code 2.1.319). Start several agents at once by running the start commands in parallel; pick each name first (§3a: a name depends only on its slot, so they never collide) and record each agent as its start returns (`registry.py` serialises its writes with a lock, so parallel records are never lost).

The Agent tool (`isolation: "remote"` or `"worktree"`) is not used for team agents: there is no tested way to give a finished subagent its next assignment, and it ends with the manager's session.

Every command that starts or messages a session begins with `cd <clone> &&`; the Bash tool's working directory does not carry over between calls.

**Every agent runs in `auto` permission mode**, local and cloud, so it works unattended while Claude still refuses dangerous actions. Never start an agent with `bypassPermissions` or `--dangerously-skip-permissions`.

- `claude --bg` (path 2): `--permission-mode auto` on the command; honoured.
- `claude --cloud` (path 1): `--permission-mode auto` after the brief (`claude --cloud "<brief>" --permission-mode auto`); `claude --cloud --permission-mode auto "<brief>"` fails with `Error: --cloud requires a description`; `claude --permission-mode auto --cloud "<brief>"` works too. Where the organisation or model does not offer Auto, the session starts in another mode the manager cannot see; a cloud session in Accept edits still runs unattended, because cloud sessions pre-approve file edits.
- Do not put `permissions.defaultMode: "auto"` in the repository's `.claude/settings.json`: a project-level `auto` is ignored by local sessions, and cloud sessions do not read permission settings from the repository at all.
- Auto can be unavailable: the organisation turned it off (`permissions.disableAutoMode`), the model does not support it, or it was switched off server-side. Then stop and ask the user, with `AskUserQuestion`, which mode agents should use.

Never run more agents than `policy.team_size`.

## 3a. Name each agent and set its session title

Every agent has a person-style name, and its session's title is that name — never the title the AI makes up from the brief (it names the session after the first task, for example `Clean up internal/fdprobe`, which says nothing about which agent it is and changes meaning as the agent takes other work). This section is the one source of truth for names and titles.

1. **Pick the name** before the session starts: `registry.py … name --agent a<k>` (add `--replace` for a replacement session) prints the name, the title and the worker id, tab-separated: `Ada	Ada (a1)	w:a1`. Names come from the script's list of computing pioneers and depend only on the slot (a1 → Ada, a2 → Linus, a3 → Grace, …), so names picked for agents started in parallel never collide; they are unique for the run; the user may choose others (`add-agent --name`, one capitalised word). A replacement session keeps the slot's name: `Ada (a1.r2)`.
2. **Use the name everywhere the agent appears**: the agent brief opens `factory <bundle> agent Ada (a1)` and tells the agent "You are Ada"; every assignment message names it (`… assignment a1-2 for Ada: …`); the board card, the team table, the run log and your reports say `Ada (a1)`. Ids stay as they are for matching (`a1`, `w:a1`, `a1-2`).
3. **Set the title when the session starts**: pass `--name "<title>"` on the start command (§3). The cloud keeps it as the session title instead of making one up: `claude --cloud "<brief>" --name "Grace (a3)" …` printed `Created cloud session: Grace (a3)` (checked on 2026-11-06 with Claude Code 2.1.319).
4. **Check it took**: the start output's `Created cloud session: <title>` line shows the title the session got. When it is not `<title>` (an older CLI without `--name` for cloud sessions), rename the session with `cd <clone> && claude -p "/rename <title>" --cloud <session_id> </dev/null` — delivered, but not confirmed to rename a cloud session — and ask the user once, with `AskUserQuestion`, to check the title on claude.ai/code (with Remote Control connected, `ListAgents` shows it). If it still differs, tell the user once, keep the name in the brief, the board and the registry, and record what the session shows: `registry.py … agent --agent a<k> cloud_title="<shown title>"`.
5. A local `claude --bg` agent takes `--name "<title>"` as its display name, which is also its `ListAgents` name: record it as `agent_name`.

## 4. Start the team and record

For each agent, first name it (§3a). With a board, then pick its key, create its board documents and fill the brief's `## Factory board` section (`board` skill §4 steps 1-3). Then start the session, and immediately, before the next one:

1. Capture the session id and URL from the command output (`Created cloud session:`, `View:` and `Resume with:` lines) per `references/session-registry.md`. Strip terminal escapes before matching. Check the title and rename the session when needed (§3a step 4). With Remote Control connected, also run `ListAgents` once the session appears and record its listing name (`agent_name`).
2. Record the agent, its rung and its remaining queue, then its first assignment — never by editing the JSON by hand:
   ```
   registry.py … add-agent --agent a<k> --name <name> --path cloud-cli --session-id <id> --url <url> --started-at <now> --worker-key <key> --model <model> --effort <effort> --queue <group> <group> …
   registry.py … assign --agent a<k> --tasks <N1>,<N2> --title "<summary>" --branch factory/<bundle>/tasks-<N1>-<N2>
   ```
   `add-agent` records the agent's name, title (`Ada (a1)`) and worker id `w:a1`; `assign` prints the assignment id (`a<k>-1`) and drops the group from the queue. Add `session_url` to `board/w:a<k>`. For a stacked assignment also `set --assignment <id> stacked_on=<p>@<parent head sha>`, and for a held one `hold_until="<condition>"`. A start whose id could not be captured is recorded with `--session-id unknown`; ask the user for the session URL, then `registry.py … agent --agent a<k> session_id=<id> url=<url>`.
3. Add a line to the run log `.specs/<bundle>/factory-run.md` (`registry.py … log --run-log <path> "<text>"`).
4. Arm one `Monitor` per assignment on the tested script, not a hand-written loop:

   ```
   Monitor({
     command: "<plugin root>/skills/watch/scripts/pr-watch.sh <clone> \"task <N1>, <N2>\" --since <assigned_at> --reviewer <policy.reviewer> --rerequest",
     description: "factory <bundle> <name> a<k>-<n> tasks <N1>, <N2>: branch, PR, checks and review state",
     timeout_ms: 3600000
   })
   ```

   Use how the pull request title will start (`"task 30, 31"`, or `"task 28"` for one task) and the assignment's `assigned_at` from the registry. Until the pull request exists, the script reports every `claude/*` and `factory/*` branch whose tip is newer than `--since` (other agents' branches included); once it exists, only its head branch; prints one line per change; adds `approved_head=yes|no|none` for the reviewer (the gate is `approved_head=yes`, not `review=APPROVED`); with `--rerequest`, re-requests that reviewer when the head moves and no request is pending; prints `github-unreachable (…)` when a GitHub call fails (the state is unknown, not empty — never report "no branch" or "no PR" from such a line), and exits by itself once the pull request is merged or closed. Re-arm it on expiry without telling the user, and check the state directly whenever it expires with no events.
5. With a board, keep one `board-tick.sh` Monitor running while an agent is working (the `watch` skill), read the board on every line it prints, and stop it with TaskStop as soon as no agent is working.
6. Confirm Auto-fix is on for each pull request as it appears (the brief asks the agent to enable it). If an agent reports it unavailable, or the pull request was opened by the manager, ask the agent to watch it (`claude -p "watch PR #<n> and auto-fix CI failures and review comments" --cloud <session_id>`) or run `/autofix-pr` from the branch. Record it with `registry.py … set --assignment <id> autofix=on`. See `references/worker-channels.md` for what Auto-fix does and does not cover.

Post the task board and the team table to the user with the session URLs.

## 5. Next assignments

Whenever an agent becomes free (§0b), at `full` straight away, otherwise after confirming with the user:

1. Pick the group (§0b), build the assignment message (§1) into `<scratchpad>/a<k>-<n>.md`.
2. With a board, write an `assign` entry in `mail/sfm~w:a<k>` (assignment id, tasks, branch; the text stays short, the full message goes in the doorbell) and update `board/w:a<k>` (`assignment`, `queue`).
3. Send it: `cd <clone> && claude -p "$(cat <scratchpad>/a<k>-<n>.md)" --cloud <session_id> </dev/null` (a local agent: `SendMessage` to its `agent_name`).
4. `registry.py … assign --agent a<k> --tasks … --title … --branch …`, a log line, and a new `pr-watch.sh` Monitor with the new `assigned_at` (§4 step 4).

Run the `integrate` skill for each pull request as it becomes ready; merge any ready pull request that depends on no unmerged one straight away. A pushed branch is not a finished assignment: agents keep committing after the first push, so wait for the pull request, or for commits to have stopped. The milestone gate (`integrate` §6) runs when the milestone's last task is `[x]`; during it every agent idles, and after the user's answer the same agents get the next milestone's groups (§0b, divided again).

## Channels to a running agent

`references/worker-channels.md` lists every way the manager can talk to, watch, or take over an agent session, with what each one proves. Read it before improvising a check.

## Relaying between agents

Read each `## Factory report`, each board report and each first push as it lands. When one agent's output fixes something another agent must match — an internal event payload, a service or subject name, a response wrapper, the unit of an offset, an error `reason` — send that agent the exact facts straight away: a `relay` entry on the board plus a doorbell that repeats it, or without a board the facts themselves, through the doorbell channel of the `board` skill §5. Record them under `contract_notes` for later assignments (`registry.py … contract <key> "<fact>"`). Couplings found only at integration cost both branches a rework.

## Steering

For a running agent, prefer one follow-up over a new session. With a board, write the follow-up as a `steer` (or `answer`, `decision`) entry in `mail/sfm~w:a<k>`, then send the same full text as its doorbell; the agent's cursor and `ack` show it arrived and was acted on. The channel and the reasons are the `board` skill §5's:

- A cloud agent: `claude -p "$(cat <message-file>)" --cloud <session_id> </dev/null`, with the id from the registry. Never `SendMessage` to a cloud session: it left cloud workers waiting on a human until the owner opened them.
- A local `claude --bg` agent: `SendMessage` to its `agent_name` from `ListAgents`.
- Write every message so the agent can act on it without opening the board or asking back: the assignment it is about, the failing output or review item, what to change, the commands, one push, the report update, the review re-request. Agents cannot message back, so say where the answer goes (the board when there is one, else the pull request or branch).

Record the message and the channel with `registry.py … note --assignment <id> "<text>"` (or `--agent a<k>` for one about the agent itself).

## Replacing an agent

An agent keeps its slot (`a<k>`) for the run; its session can be replaced. `registry.py … add-agent --agent a<k> --replace …` marks the old session `replaced`, moves its queue to the new one, and gives it the worker id `w:a<k>.r2` (`.r3`, …) with a new key; it keeps the slot's name, with the title `<name> (a<k>.r2)` (§3a). Give the new session a fresh agent brief, create its board documents, and clean the old one's off the board (`board` skill §7). The script lists the old session's open assignments: set each `failed` or `reassigned` and assign what is left to the new session.

- **Failure.** An assignment that fails (red checks the agent could not fix, no pull request, a timeout, a verification that found real defects the agent could not fix in its rounds) gets one replacement session one rung higher (`references/model-and-effort.md`). Its first assignment is the failed group: base it on the failed branch (check it out in the clone and run the §2 preflight with it as the base), give it only the tasks not yet committed, add the failure output, and tell it to update the existing pull request. A second failure of the same group stops that group and is reported. Two consecutive failures across the team stop all new assignments until the user decides.
- **Recycle.** A long session carries a long context. Replace an agent at its next idle point (no open assignment) after 4 merged assignments, at a milestone gate when it carried 3 or more, or when its session ended, expired, or answers out of context (it repeats finished work, forgets the standing rules). Same rung; the queue moves with it.
- **Spec block.** An agent that reports `BLOCKED: spec` (ambiguous or contradictory spec) means the spec gate missed a gap: pause every new assignment. Under `policy.minor_defaults: manager`, a low-impact detail is decided by the manager instead (see `references/session-registry.md`); otherwise the manager asks the user, records the answer under the task in `tasks.md` as `- Clarification:`, re-runs the spec gate, then sends the answer to the same agent as a `decision` (its session continues; replace it only when it has ended).
- A spec `question` on the board is the same gap, and new assignments pause the same way, but the agent keeps working on what does not depend on the answer: record the answer as a Clarification, re-run the spec gate, send it as a `decision` entry with its doorbell, and wait for the agent's `ack`. Replace the session only when it has ended or does not read the answer (its cursor does not move after two doorbells).
- An agent or verifier that finds a confirmed defect in already-merged code follows the reported-defect path in `integrate` §2b: the pinning pull request merges, and the fix is a new task, queued like any other.
- An agent removed from the team (the user lowers `team_size`, or the run closes): `registry.py … agent --agent a<k> status=retired`, after its open assignments merged or moved; its queue goes to the others (`move`).
