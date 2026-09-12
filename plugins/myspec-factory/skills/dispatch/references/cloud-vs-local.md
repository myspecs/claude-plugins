# Dispatch paths

Facts below come from `claude --help` in this build and the Claude Code documentation for cloud sessions, worktrees, and background agents. Verify availability in the current session before relying on a path.

## Cloud session via the Agent tool

The Agent tool accepts `isolation: "remote"`, which launches the agent in a remote cloud environment. It always runs in the background and its availability is gated by plan and organisation policy. The completion notification carries the agent's final report; ask the worker to end with its pull request URL so the manager can find it. If the call is refused, fall through to the next path.

## Cloud session via the CLI

Source: the Claude Code on the web documentation (code.claude.com/docs/en/claude-code-on-the-web).

```bash
claude --cloud "<brief text>"                                # new cloud session for the current repo
claude --cloud --environment <ccpool_...> "<brief text>"     # run on a specific self-hosted environment
claude -p "<follow-up>" --cloud <session_id|url>             # queue one message into a running session, then exit
claude -p "<follow-up>" --cloud <session_id> --output-format json   # {ok, session_id, url}
claude --teleport <session_id>                               # pull the session's branch and history into this terminal
```

Facts that shape dispatch:

- `claude --cloud "<task>"` creates a new cloud session for the **current directory's GitHub remote at the current branch**. It clones the remote, not the local checkout: push first, and start from the branch the workers should base on (normally the default branch). One repository per session. Each invocation is an independent session, so several tasks can be started back to back.
- The command is interactive: it shows a provisioning checklist and stays attached, queueing anything typed until the session is ready. From the manager, run it through Bash with `run_in_background: true` so the manager is not blocked, and read the background output for the session id and URL (`claude.ai/code/<session_id>`). If the output does not yield an id, ask the user to copy the session URL from claude.ai/code.
- Requirements: signed in to claude.ai with `claude auth login` (an API key or a third-party provider is refused), the organisation's `allow_remote_sessions` policy on, GitHub connected through the Claude GitHub App or `/web-setup`. A repository without a remote, or one the App is not installed on, is uploaded as a bundle instead (tracked files only, under 100 MB).
- Steering: `claude -p "<message>" --cloud <session_id>` posts one message and exits, printing `Session ID:` and `View:` lines. This is how the manager sends a failing-check log or a review comment to a running worker instead of redispatching. The session id comes from `.specs/<bundle>/factory-sessions.json`, written at dispatch time (see `session-registry.md`).
- Monitoring: `/tasks` in an interactive Claude Code session lists cloud sessions (press `t` to teleport); the session URL at claude.ai/code shows the diff and conversation; `gh pr list` shows the pull request once it exists.
- Results: the session pushes a `claude/`-prefixed branch when it reaches a stopping point and stays open. Pull requests are normally created from the web session's **Create PR** button; whether `gh` is authenticated inside the session is not guaranteed, so the worker brief asks for a pull request when possible and otherwise a pushed branch plus the report in the final message. The manager then opens the pull request itself with `gh pr create --head <branch>`.
- Cloud sessions carry only what the cloud environment provides: no user-level plugins, no `~/.myspec` credentials. `MYSPEC_API_TOKEN` must be set on the environment if the worker needs MySpec. Permission modes available in the cloud are Accept edits, Plan, and Auto; the session runs unattended in Accept edits, so the brief must be complete.
- Sessions expire after inactivity and are reclaimed; reopening from claude.ai/code restores the conversation. Rate limits are shared with the whole account; parallel sessions consume them proportionately.

## Local worktree via the Agent tool

`isolation: "worktree"` gives the subagent its own git worktree; the worktree is cleaned up automatically if it made no changes. Dispatch with `run_in_background: true` (a plain Agent call blocks until the subagent returns) and wait for the completion notification. Several worktree subagents may run at once as long as their files are disjoint.

## Local worktree via a background CLI session

```bash
claude --bg --worktree task-<N> -p "<brief text>"
claude agents            # list background sessions and their state
claude attach <id>       # open one interactively
```

`--worktree` creates `.claude/worktrees/task-<N>/` on a new branch; `--bg` returns immediately and prints the id that `attach`, `logs`, `stop`, and `rm` take. The documentation describes isolation checks that keep a worktree session from editing the main checkout; still review the diff scope at integration. After the task merges, clean up with `claude rm <id>` and `git worktree remove .claude/worktrees/task-<N>`.

## Remote Control

Start the manager with `claude --remote-control "factory <bundle>"` or run `/remote-control` in the session. While connected, `ListAgents` lists the account's cloud sessions newest first (bounded pages; very old sessions drop off) and `SendMessage` delivers to them through Anthropic's servers. A cloud session receives the message but cannot message back, so instructions to workers must ask for an answer through the pull request or branch. Sessions started with `claude --cloud` take their title from the first prompt line, so briefs begin with `factory <bundle> task <N>: <title>`.

## Monitoring

| Path | Signal |
|---|---|
| Agent tool (remote or worktree) | Task notification on completion; `ListAgents` while running |
| `claude --cloud` | `ListAgents` (rows labelled `cloud`, only while this session is connected to Remote Control) and `SendMessage` by session name; session URL at claude.ai/code; `/tasks` in an interactive session; the `claude/` branch or pull request appearing; `claude -p "..." --cloud <id>` to steer without Remote Control |
| `claude --bg` | `claude agents`, `claude logs <id>` |
| All | `gh pr list --state open` filtered by `factory/` branches or `task N:` titles |

## Cost

Every parallel session consumes rate limit from the same account. State the number of sessions and expected sizes before each wave, keep the concurrency cap, and prefer fewer, well-briefed sessions over many thin ones.
