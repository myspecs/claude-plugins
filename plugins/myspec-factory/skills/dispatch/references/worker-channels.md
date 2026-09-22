# Channels to a worker session

Every way the manager can send to, hear from, watch, or take over a worker, and what each one actually proves. Cloud sessions are one-way: they receive messages and cannot answer the manager, so every answer arrives as a commit, a pull-request reply, an attachment, or a session transcript the user reads.

## Send to a worker

| Channel | Command | Needs | Proves |
|---|---|---|---|
| Remote Control message | `SendMessage` to the row's name from `ListAgents` | Manager connected to Remote Control (`claude --remote-control "factory <bundle>"` or `/remote-control`); worker listed as `cloud` | Delivery to the session only. Not that it was read or acted on — new commits or replies are the proof |
| CLI steer | `cd <clone> && claude -p "<message>" --cloud <session_id>` | Session id from `.specs/<bundle>/factory-sessions.json` | Same: one message queued, then the command exits |
| Pull-request review | `gh pr review`, `gh pr comment`, inline comments | The worker's pull request exists and its brief told it to watch reviews | Durable, and the worker can answer in the same place |
| Redispatch | A new session with the failure output added to the brief | — | Use only when the session has ended, expired, or reported `BLOCKED` |

## Auto-fix on the pull request

Claude Code's Auto-fix subscribes a cloud session to the pull request's GitHub events and answers CI failures and review comments on its own. Every factory pull request runs with it on, so a wave keeps moving while the manager is between waves.

| Turn it on | How |
|---|---|
| The worker, on its own pull request (default) | The brief tells it to select **Auto-fix** in the session's CI status bar as soon as the pull request exists |
| The manager, on a running worker | `SendMessage` or `claude -p "watch PR #<n> and auto-fix CI failures and review comments" --cloud <session_id>` |
| The manager, from a checkout | `/autofix-pr` while on the pull request's branch — spawns a cloud session and enables it in one step |
| Any existing pull request | Give a session the pull-request URL and ask it to auto-fix |

Facts that matter to the manager: Auto-fix needs the Claude GitHub App installed on the repository (the `setup` skill checks this); it is a per-pull-request toggle, cleared from the same CI status bar; it does not react to merge conflicts caused by an advancing base branch, so a rebase is still asked for explicitly; and its review replies post under the account's GitHub user, labelled as Claude Code. In a repository where a pull-request comment can trigger deploys or other privileged automation, tell the user before enabling it. Auto-fix never merges, and neither does anything else the manager arms: auto-merge is forbidden in every form — `gh pr merge --auto`, GitHub's auto-merge toggle, merge queues — because the decision to merge belongs to the manager under the agreed policy, or to the user. Record `autofix: on` (or why not) in the registry entry.

Write the message so it can be answered without a reply channel: "push a fix", "reply on the review thread", "put `BLOCKED: <reason>` as a pull-request comment". Record what was sent, and on which channel, in the registry entry's `notes`.

## Hear from a worker

| Signal | How it arrives | Notes |
|---|---|---|
| Commits on the branch | `git ls-remote --heads origin 'claude/*'`, `git log origin/<branch>` | First push is not the end; workers keep committing |
| Pull request and its `## Factory report` | `gh pr list`, `gh pr view <n> --json body,comments` | The contracted hand-back: tests run, deviations, `BLOCKED:` lines. It is at the end of the description, and after each later round also in a comment starting `## Factory report`; the newest one is current. Workers never upload it to MySpec |
| Review replies | `gh api repos/{owner}/{repo}/pulls/<n>/comments` | Workers briefed to handle their own review round answer here |
| Agent-tool completion | Task notification with the agent's final report | `isolation: "remote"` and `isolation: "worktree"` paths only |
| Session transcript | claude.ai/code/`<session_id>`, or `/tasks` in an interactive session | The manager cannot read it; ask the user when a worker's reasoning matters |

## Watch without polling

| Mechanism | Use |
|---|---|
| `Monitor` on `gh pr view` / `git ls-remote` | The wave's board: branch, pull request, checks, review decision, merge state. One watch per wave, re-armed on expiry |
| `Monitor` on `gh run list` | Post-merge deploy runs on the default branch |
| MySpec event feed (`watch` skill) | Spec changes and spec-session completion. Worker reports arrive on pull requests, not on the feed |
| Task notifications | Agent-tool workers and background Bash commands |
| `ListAgents` | Which cloud sessions exist and whether each is `running` or `idle` right now |

A watch that expires with no events is a suspect watch: check the state directly before reporting quiet. See the monitoring rules in `cloud-vs-local.md` for the filter mistakes that cause silent watches.

## Take over

| Action | Command | When |
|---|---|---|
| Teleport | `cd <clone> && claude --teleport <session_id>` | Pull the worker's branch and history into the user's terminal to finish or debug by hand |
| Open the pull request for it | `gh pr create --head <branch> --title "task N1, N2: <summary>" --body-file <report>` (single task: `--title "task N: <title>"`; lane: `--title "lane L: tasks N1, N2"`) | The worker pushed but never opened one |
| Local verification | Read-only subagent in a throwaway worktree (`git worktree add --detach`) | Run the suites and check acceptance criteria without touching the user's checkout |

Taking over is outward-facing work: opening a pull request, merging, or pushing needs the user's agreement unless the run's policy already covers it.
