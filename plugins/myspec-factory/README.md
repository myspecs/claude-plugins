# myspec-factory

Turns Claude Code into a **Software Factory Manager**: an orchestrator that runs a MySpec specification bundle to completion by dispatching one Claude Code session per task, integrating the resulting pull requests, marking tasks done on MySpec, and stopping at milestone gates for human review.

## Overview

[MySpec](https://myspec.dev) produces a reviewable bundle (constitution, requirements, solution, tasks). The `myspec-mcp` plugin lets one Claude Code session implement it task by task. This plugin adds the layer above: a manager persona that never writes feature code, plans waves of non-overlapping tasks from the dependency graph, spawns worker sessions (Claude Code cloud sessions when available, local git worktrees otherwise), verifies each pull request against acceptance criteria and the constitution, merges per an agreed policy, records progress on the platform, and can run unattended shifts on a schedule.

## Features

- **Software Factory Manager output style**: explicit role, prohibitions (no coding, no unverified done-marking, no force pushes), the run loop, milestone gates, cost statements before every wave.
- **Wave planning** from `_Dependencies:_` and solution modules; the board is derived from platform checkboxes and open pull requests, never stored as truth.
- **Dispatch** with self-contained worker briefs: task, acceptance criteria, cited requirements, binding constitution sections, solution excerpts, and a pull-request output contract. Cloud first (`claude --cloud` or a remote subagent), worktree fallback.
- **Integration**: required checks, tests named for each acceptance criterion, constitution and scope review, merge per policy, `[x]` written to MySpec with optimistic concurrency.
- **Live event feed**: the manager mints a MySpec stream token and feeds its `wss://` URL straight into Claude Code's `Monitor` tool, so `tasks.md` edits, spec changes, worker report uploads, and session completions arrive as notifications instead of polling. The URL is treated as a password and never persisted.
- **Scheduled shifts**: a cloud routine that integrates, marks done, and dispatches the next wave on a cadence.

## Prerequisites

- `myspec-mcp@myspec` installed and signed in (the manager reads and writes the bundle through it).
- GitHub CLI (`gh`) authenticated with push and pull-request rights on the repository.
- For the live event feed: `@myspec/mcp-server` 0.4.0 or newer (today `@next`) and a platform with stream tokens enabled; otherwise the manager polls.
- For cloud workers: Claude Code on the web enabled for the account, the GitHub App on the repository, and a cloud environment carrying `MYSPEC_API_TOKEN` when workers need MySpec access.
- For local workers: git worktrees and the `claude` CLI, plus a long-lived `MYSPEC_API_TOKEN` in the repository's gitignored `.claude/settings.local.json` when they need MySpec tools — a PAT keeps them off the manager's OAuth credentials, which two servers cannot share.

## Installation

```
/plugin marketplace add myspecs/claude-plugins
/plugin install myspec-mcp@myspec
/plugin install myspec-factory@myspec
```

Restart Claude Code, then start the manager session with Remote Control so it can see and message its cloud workers:

```bash
claude --remote-control "factory <bundle>"
```

(or run `/remote-control factory <bundle>` inside a session). While connected, `ListAgents` lists the account's cloud sessions and `SendMessage` reaches them by name; without it the manager only has the `claude -p ... --cloud <id>` CLI for steering.

Then activate the persona (the `setup` skill checks this and tells you when the active style is something else): `/config`, Output style, choose **Software Factory Manager**, or set it in a settings file (plugin styles are addressed as `<plugin>:<style name>`):

```json
{ "outputStyle": "myspec-factory:Software Factory Manager" }
```

Put that in `.claude/settings.local.json` of the repository you are managing so only that checkout runs the manager persona. The style is not forced on; sessions that should implement tasks themselves keep the default style.

## Components

### Output style

`Software Factory Manager` (`output-styles/software-factory-manager.md`). Keeps Claude's coding guidance for git and verification work but forbids implementing tasks.

### Skills

| Skill | Invoke | Purpose |
|---|---|---|
| `setup` | `/myspec-factory:setup` | MySpec and GitHub access, cloud readiness, opt-in repository configuration so cloud workers load the plugin and MCP server |
| `watch` | `/myspec-factory:watch` | Mint a stream token, open the project event feed in `Monitor`, map each event to a manager action; polling fallback when the server lacks stream tokens |
| `plan` | `/myspec-factory:plan` | Derive the board and group ready tasks into waves of disjoint work |
| `dispatch` | `/myspec-factory:dispatch` | Spawn one worker per task with a self-contained brief; cloud first, worktree fallback |
| `integrate` | `/myspec-factory:integrate` | Verify and merge worker pull requests, mark tasks done on MySpec, run the milestone gate |
| `shift` | `/myspec-factory:shift` | Draft and create a scheduled cloud routine that runs one unattended shift |

The manager also uses `myspec-mcp:implement` (write-back protocol) and `myspec-mcp:analyze` (convergence check at milestone gates).

## A run, end to end

1. `/myspec-factory:setup` in the repository. Approve the repository configuration it proposes.
2. Switch to the Software Factory Manager output style and ask: "Run the factory for project X, bundle Y."
3. The manager opens the project event feed, then asks once for the concurrency cap, merge policy, and cloud permission, plans wave 1, and states its cost.
4. Workers open pull requests titled `task N: <title>` with a `## Factory report`.
5. The manager verifies, merges, marks `[x]` on MySpec, and dispatches the next wave.
6. At the end of a milestone it runs the convergence analysis and stops for your review.

## Worker contract

Branch `factory/<bundle>/task-<N>`, one task, one pull request, tests named after each acceptance criterion, a `## Factory report` at the end of the body, `BLOCKED: spec` or `BLOCKED: env` as the report's first line when the worker cannot finish. Workers never edit `tasks.md` or spec files.

## Safety and cost

- The manager asks before spawning sessions, writing repository configuration, merging outside the agreed policy, or creating routines.
- Parallel sessions share and multiply the account's rate limit; the manager states session counts before each wave and keeps the cap.
- No force pushes, no bypassing branch protection, no merging red pull requests.

## Configuration

| Setting | Where | Purpose |
|---|---|---|
| `outputStyle: "myspec-factory:Software Factory Manager"` | `.claude/settings.local.json` of the managed repository | Activates the manager persona for that checkout only |
| Remote Control (`claude --remote-control` or `/remote-control`) | The manager's own session | Makes cloud workers visible in `ListAgents` and reachable with `SendMessage` |
| Concurrency cap, merge policy, cloud permission | Asked once per run by the manager | Bound every wave of the run |
| `extraKnownMarketplaces` / `enabledPlugins` | Repository `.claude/settings.json` (written by `setup` on approval) | Lets cloud workers load `myspec-mcp` |
| `MYSPEC_API_TOKEN` | Cloud environment at claude.ai/code | MySpec access for cloud workers and shifts (no browser login there) |
| `MYSPEC_API_TOKEN` (+ `MYSPEC_USER_AUTH_URL` when the deployments differ) | `env` in the managed repository's gitignored `.claude/settings.local.json` | MySpec access for local workers. Check `claude mcp list` first: a `myspec` row means the worker already has a server; otherwise pass a temporary `--mcp-config` file that reads `${MYSPEC_API_TOKEN}` from the environment. Scoped to one deployment and organisation, so verify with `list_projects` before a run |
| `.specs/<bundle>/factory-sessions.json` | Local, gitignored | Session registry: task, session id, URL, branch, status for every dispatched worker, plus the stream token id, prefix, expiry, and last `seq` (never the stream URL); the manager reads it to steer a session with `claude -p "..." --cloud <session_id>` |
| `.specs/<bundle>/factory-run.md` | Local, gitignored | Run log and board cache; never the source of truth |

## Troubleshooting

- A worker's MySpec calls fail with `Refresh token rejected` then `Not authenticated`, and the manager's MySpec tools stop working too: two servers shared `~/.myspec/oauth_creds.json` and one rotated the refresh token. Give local workers their own `MYSPEC_API_TOKEN` (gitignored `.claude/settings.local.json`), then reconnect the manager's server with `/mcp`.
- A worker's PAT 401s with `API token exchange failed … invalid, disabled, or expired`: the token belongs to a different deployment or organisation than `~/.myspec/settings.json` names. Set `MYSPEC_USER_AUTH_URL` for that worker to the PAT's auth host, or mint a PAT in the right organisation; verify with `list_projects` before the run.
- `claude --bg -p "…"` is refused (`--bg and --print conflict`): pass the brief as the positional argument, `claude --bg "<brief>"`. `claude agents` also needs `--json` when stdout is not a terminal.
- Auto-fix is not offered on a worker's pull request: the Claude GitHub App is not installed on the repository (check the repository's Settings > GitHub Apps; `gh api repos/{owner}/{repo}/installation` needs an App JWT and returns 401 to a normal `gh` login). A cloud worker also cannot click the Auto-fix toggle in its own session; it subscribes to its pull request's activity instead. Install the App from [github.com/apps/claude](https://github.com/apps/claude), or accept that workers only react while their session is alive.
- Dev ends up running an older commit after two merges: push workflows that build a mutable tag such as `:latest` race when merges land seconds apart. The manager merges one pull request at a time and waits for its post-merge runs; to recover, re-run the newest merge commit's workflow.
- `claude --cloud` exits with `--cloud requires an interactive terminal`: it needs a TTY, so the manager dispatches through `script -q <file> claude --cloud "$(cat <brief>)" </dev/null` from a local clone of the target repository.
- A cloud session started on the wrong repository: `--cloud` reads the git remote of the current directory, so every dispatch command must `cd` into a clone of the target repository first; the Bash tool does not keep a working directory between calls.
- The worker's branch is not `factory/<bundle>/task-<N>`: cloud sessions always push their own `claude/`-prefixed branch. Match on the branch prefix and the `task N:` pull-request title.
- The session name in `ListAgents` does not match the brief's first line: the cloud rewrites the title. Record the name from `Created cloud session:` and confirm it with `ListAgents`.
- Workers cannot reach MySpec in the cloud: the cloud environment lacks `MYSPEC_API_TOKEN` or egress to the MySpec hosts; briefs already inline the spec excerpts, so this only matters when the brief asks workers to read more.
- Cloud workers missing from `ListAgents`: the manager session is not connected to Remote Control (`/remote-control`), or the sessions are older than the bounded listing; steer with `claude -p ... --cloud <id>` instead.
- Cloud dispatch refused: plan or organisation policy; the manager falls back to worktrees.
- Two sets of MySpec tools in a worker: the repository declares `myspec` both through `enabledPlugins` and a root `.mcp.json`; keep the plugin entry and drop the `.mcp.json` server.
- A routine ran but did nothing: read its run log (`RemoteTrigger` `get_run_log`); the usual causes are a missing token or a repository without the managed `CLAUDE.md` block.

## License

MIT. See [LICENSE](LICENSE).
