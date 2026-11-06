# Channels to an agent session

Every way the manager can send to, hear from, watch, or take over a team agent, and what each one actually proves. A cloud session receives messages but cannot message the manager back. Its answers arrive on the repository's factory board (the `board` skill), as a commit, a pull-request reply, or in a session transcript the user reads.

## Send to an agent

| Channel | Command | Needs | Proves |
|---|---|---|---|
| CLI message (the cloud channel) | `cd <clone> && claude -p "$(cat <message-file>)" --cloud <session_id> </dev/null` | Session id from `.specs/<bundle>/factory-sessions.json` | Delivery only: one message queued (a working session) or delivered (an idle one wakes on it), then the command exits. New commits, replies or a board `ack` are the proof. Carries next assignments, steering and doorbells |
| Remote Control message (local agents only) | `SendMessage` to the row's name from `ListAgents` | Manager connected to Remote Control; a local `claude --bg` agent | Same. Never for cloud agents: it left cloud sessions waiting on a human (the `board` skill §5) |
| Board message + doorbell | An entry in `mail/sfm~<worker id>` (assign, answer, decision, relay, steer), then a doorbell through the channel above that carries the same full text | The repository's factory board, and an agent whose report does not say `- Board: unavailable` | Durable. The agent's `cursors/<worker id>` moving past the entry proves it was read; its `ack` entry proves it acted |
| Pull-request review | `gh pr review`, `gh pr comment`, inline comments | The assignment's pull request exists and the brief told the agent to watch reviews | Durable, and the agent can answer in the same place |
| Replacement session | A new session for the same slot (`add-agent --replace`), with the failure output in its first assignment | — | Use only after a failed assignment, or when the session has ended, expired or needs recycling (the dispatch skill, Replacing an agent); a question on the board keeps the session |

## Auto-fix on the pull request

Claude Code's Auto-fix subscribes a cloud session to the pull request's GitHub events and answers CI failures and review comments on its own. Every factory pull request runs with it on, so a pull request keeps moving while its agent works on its next assignment and the manager is busy elsewhere.

| Turn it on | How |
|---|---|
| The agent, on its own pull request (default) | The brief tells it to select **Auto-fix** in the session's CI status bar as soon as the pull request exists |
| The manager, on a running agent | `claude -p "watch PR #<n> and auto-fix CI failures and review comments" --cloud <session_id>` |
| The manager, from a checkout | `/autofix-pr` while on the pull request's branch — spawns a cloud session and enables it in one step |
| Any existing pull request | Give a session the pull-request URL and ask it to auto-fix |

Facts that matter to the manager: Auto-fix needs the Claude GitHub App installed on the repository (the `setup` skill checks this); it is a per-pull-request toggle, cleared from the same CI status bar; it does not react to merge conflicts caused by an advancing base branch, so a rebase is still asked for explicitly; and its review replies post under the account's GitHub user, labelled as Claude Code. In a repository where a pull-request comment can trigger deploys or other privileged automation, tell the user before enabling it. Auto-fix never merges, and neither does anything else the manager arms: auto-merge is forbidden in every form — `gh pr merge --auto`, GitHub's auto-merge toggle, merge queues — because the decision to merge belongs to the manager under the agreed policy, or to the user. Record `autofix: on` (or why not) on the assignment in the registry.

With a board, put the message on the board and send a doorbell that carries the same full text (the `board` skill §5): agents often act on the doorbell without opening the board. Without one, write the message so it can be answered without a reply channel: "push a fix", "reply on the review thread", "put `BLOCKED: <reason>` as a pull-request comment". Record what was sent, and on which channel, in the registry's `notes` (`note --assignment` or `--agent`).

## Hear from an agent

| Signal | How it arrives | Notes |
|---|---|---|
| Commits on the branch | `git ls-remote --heads origin 'claude/*'`, `git log origin/<branch>` | First push is not the end; agents keep committing. One branch per assignment |
| Pull request and its `## Factory report` | `gh pr list`, `gh pr view <n> --json body,comments` | The contracted hand-back: tests run, deviations, `BLOCKED:` lines. It is at the end of the description, and after each later round also in a comment starting `## Factory report`; the newest one is current. Agents never upload it to MySpec |
| Factory board | `ArtifactData` on `mail/<worker id>~sfm` and `reports/<worker id>` (the `board` skill §5) | Progress at every checkpoint, questions asked mid-work, and a copy of the Factory report, before and after the pull request exists. Nothing wakes the manager when an agent writes: read it at every loop step and on every `board-tick.sh` line. The pull-request report still decides the merge |
| Review replies | `gh api repos/{owner}/{repo}/pulls/<n>/comments` | Agents handle their own review rounds and answer here |
| `waiting for next assignment` | The last line of the agent's turn, in its session transcript; `ListAgents` shows the session `idle` | The agent finished its current assignment for now; the pull request is the proof the manager acts on |
| Session transcript | claude.ai/code/`<session_id>`, or `/tasks` in an interactive session | The manager cannot read it; ask the user when an agent's reasoning matters |

## Watch without polling

| Mechanism | Use |
|---|---|
| `Monitor` on `gh pr view` / `git ls-remote` | Each assignment's branch, pull request, checks, review decision and merge state. One watch per assignment, re-armed on expiry |
| `Monitor` on `gh run list` | Post-merge deploy runs on the default branch |
| MySpec event feed (`watch` skill) | Spec changes and spec-session completion. Agent reports arrive on pull requests and the factory board, not on the feed |
| `Monitor` on `board-tick.sh` | A line every 10 minutes while an agent is working: the cue to read the factory board, which wakes nobody by itself. Stopped as soon as no agent is working |
| Board comment watch | Set up at every run start and after a restart (`board` skill §3): the owner's **Send to Claude** on a board comment wakes the manager. Plain comments, resolves and agent writes do not |
| Task notifications | The manager's own subagents and background Bash commands |
| `ListAgents` | Which cloud sessions exist and whether each is `running` or `idle` right now (listing only; message cloud agents with `claude -p`) |

A watch that expires with no events is a suspect watch: check the state directly before reporting quiet. See the monitoring rules in `cloud-vs-local.md` for the filter mistakes that cause silent watches.

## Take over

| Action | Command | When |
|---|---|---|
| Teleport | `cd <clone> && claude --teleport <session_id>` | Pull the agent's branch and history into the user's terminal to finish or debug by hand |
| Open the pull request for it | `gh pr create --head <branch> --title "task N1, N2: <summary>" --body-file <report>` (single task: `--title "task N: <title>"`) | The agent pushed but never opened one |
| Local verification | Read-only subagent in a throwaway worktree (`git worktree add --detach`) | Run the suites and check acceptance criteria without touching the user's checkout |

Taking over is outward-facing work: opening a pull request, merging, or pushing needs the user's agreement unless the run's policy already covers it.
