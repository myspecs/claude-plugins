---
name: dispatch
description: Spawn one Claude Code worker session per ready factory task with a self-contained brief. Use when the user says "dispatch the wave", "start the workers", "spawn sessions for these tasks", "run task N in the cloud", or after the plan skill has produced a wave. Cloud sessions first (claude --cloud or a remote subagent), local git worktree sessions as fallback. Never implements a task in the manager session.
---

# Factory dispatch

Inputs: an approved wave from the `plan` skill, the concurrency cap, and the user's agreement to spawn sessions (asked once per run). Brief template: `references/worker-brief.md`. Mechanics per path: `references/cloud-vs-local.md`. Session bookkeeping: `references/session-registry.md`.

## 1. Build one brief per task

A worker starts with zero context. Each brief must contain, inline: repository and default branch; the task block verbatim; every acceptance criterion; the text of each cited FR/NFR (or AR/CR, or OpenSpec requirement and scenarios); the constitution sections that bind the work (Technology, Architecture, Testing, Coding Standards, Security); the solution module excerpts the task touches; the output contract (branch, pull request title and body, `## Factory report`, blocked protocol); and the rule that the worker must not edit `tasks.md` or any spec file. Fill `references/worker-brief.md`; keep the brief under roughly 400 lines by excerpting rather than pasting whole documents.

## 2. Choose the path

| Order | Path | When |
|---|---|---|
| 1 | Agent tool with `isolation: "remote"` | Available in this build and the user allowed cloud dispatch. Runs in the background; its completion arrives as a notification |
| 2 | `claude --cloud "<brief>"` via Bash with `run_in_background: true` | Remote subagent unavailable. Push the base branch first; the cloud clones the remote at the current branch. Read the session id and URL from the background output; if none appears, ask the user to paste the session URL from claude.ai/code. Steer a running session with `claude -p "<message>" --cloud <session_id>` |
| 3 | Agent tool with `isolation: "worktree"` | Cloud not allowed or unavailable. Background subagent in its own worktree; results return as a notification |
| 4 | `claude --bg --worktree task-<N> -p "<brief>"` via Bash | When a separate process is preferred; monitor with `claude agents` |

Never exceed the concurrency cap. Never dispatch two tasks that share files in the same wave.

## 3. Dispatch and record

For each task, start the session, then immediately, before starting the next one:

1. Capture the session id and URL from the command output (`Session ID:` and `View:` lines, or `--output-format json`) or the agent id from the tool result, per `references/session-registry.md`. With Remote Control connected, also run `ListAgents` once the session appears and record its listing name (`agent_name`).
2. Append an entry to `.specs/<bundle>/factory-sessions.json` (task, title, path, session id, URL, expected branch, start time, `status: "running"`). This file is how the manager finds the session again to steer it; a dispatch whose id could not be captured is recorded with `session_id: null` and the user is asked for the URL.
3. Add a line to the run log `.specs/<bundle>/factory-run.md`.

Post the updated board to the user with the session URLs.

## 4. Hand over to integrate

When every session in the wave has reported (notification, `claude agents`, or a pull request appearing), run the `integrate` skill. Do not start the next wave first.

## Steering instead of redispatching

For a cloud worker that is still running, prefer one follow-up over a fresh session. Two channels, in order:

1. `SendMessage` (needs this session connected to Remote Control): run `ListAgents`, find the worker's row (labelled `cloud`; its name is the session title, which is why every brief starts with the line `factory <bundle> task <N>: <title>`), and send the message to that name (append the `[ref]` only when the listing shows one). Cloud sessions receive messages but cannot message back, so ask the worker to answer through its pull request or branch, not in a reply.
2. `claude -p "<failing check output or review comment>" --cloud <session_id>` with the id from `.specs/<bundle>/factory-sessions.json`, when Remote Control is not connected or the session has fallen off the bounded listing.

Record the message and the channel in the entry's `notes`. Redispatch only when the session has ended, expired, or reported `BLOCKED`; append a new registry entry and mark the old one `redispatched`.

## Redispatch rules

- A worker that reports `BLOCKED: spec` (ambiguous or contradictory spec) stops its lane; the manager records the question under the task in `tasks.md` as `- Clarification:` after the user answers, then redispatches.
- A worker that fails (red checks, no pull request, timeout) is redispatched once with the failure output added to the brief. A second failure stops the lane and is reported. Two consecutive failures across the wave stop dispatching until the user decides.
