# Dispatch paths

Facts below come from `claude --help` in this build and the Claude Code documentation for cloud sessions, worktrees, and background agents. Verify availability in the current session before relying on a path.

## Choosing a path

Always dispatch to the cloud. The local paths are a fallback, not an equal choice; the order is in the dispatch skill's path table.

- **Why cloud**: each cloud session runs in its own isolated environment, with its own CPU, memory, disk, clone, dependency installs, and build and test runs. Parallel cloud workers never compete for machine resources.
- **Why not local**: local workers (worktree subagents and `claude --bg` sessions) all run on this machine, next to the manager. A worktree or a sandbox keeps their files apart but not their CPU and memory. Parallel installs, builds and test suites slow every worker and the manager, and can fail on timeouts or out-of-memory kills that look like real test failures. They can also clash on fixed ports, a shared local database, or the Docker daemon.
- **Parallel work makes the case stronger**: the more work streams a wave or a lane plan runs at once, the more the cloud wins. Never pick local to avoid the cloud set-up steps.
- **Fall back to local only when**:
  - the run `policy` has cloud dispatch not allowed;
  - the user asked for a local worker for this task;
  - the cloud refused the dispatch for a lasting reason: `isolation: "remote"` refused, the CLI not signed in to claude.ai, the organisation's `allow_remote_sessions` policy off, or GitHub not connected for this repository (the CLI then uploads a bundle instead, and without GitHub access the session cannot push its branch or open a pull request). A timeout or a failed GitHub or network call is not a refusal: retry, or check the state directly, before falling back.
- **When falling back with more than one worker**: tell the user why the cloud was not used and that the local workers will share this machine, then ask with `AskUserQuestion` whether to lower the concurrency cap or run the workers one at a time.
- Shared rate limits are not a reason to pick local: local and cloud sessions draw on the same account limits (see Cost).

## Cloud session via the Agent tool

The Agent tool accepts `isolation: "remote"`, which launches the agent in a remote cloud environment. It inherits the manager's permission mode (run the manager in `auto`). It always runs in the background and its availability is gated by plan and organisation policy. The completion notification carries the agent's final report; ask the worker to end with its pull request URL so the manager can find it. If the call is refused, fall through to the next path.

## Cloud session via the CLI

Source: the Claude Code on the web documentation (code.claude.com/docs/en/claude-code-on-the-web).

```bash
claude --cloud "<brief text>" --permission-mode auto         # new cloud session for the current repo, in auto mode
claude --cloud "<brief text>" --environment <ccpool_...> --permission-mode auto   # on a specific self-hosted environment
claude -p "<follow-up>" --cloud <session_id|url>             # queue one message into a running session, then exit
claude -p "<follow-up>" --cloud <session_id> --output-format json   # {ok, session_id, url}
claude --teleport <session_id>                               # pull the session's branch and history into this terminal
```

Facts that shape dispatch:

- `--cloud` takes the description (the brief) as its own value, so the brief goes right after it and every other flag after the brief. `claude --cloud --permission-mode auto "<brief>"` fails with `Error: --cloud requires a description` (observed with 2.1.283); `claude --cloud "<brief>" --permission-mode auto` creates the session.
- `claude --cloud "<task>"` creates a new cloud session for the **current directory's GitHub remote at the current branch**. It clones the remote, not the local checkout: push first, and start from the branch the workers should base on (normally the default branch). One repository per session. Each invocation is an independent session, so several tasks can be started back to back.
- **Always `cd` into a local clone of the target repository in the same command.** The manager's own working directory is usually a different repository (the plugin repo, a notes repo, the directory Claude Code was started in), and `--cloud` reads the remote of the current directory — dispatching from the wrong directory silently starts a session on the wrong repository. Every dispatch command therefore begins `cd /path/to/<clone> && claude --cloud …`, and the Bash tool's working directory does not persist between calls, so the `cd` is repeated in each one. If the user has no local clone of the target repository, ask for the path or clone it first; do not dispatch from a directory whose `git remote -v` you have not checked.
- **`--cloud` requires a TTY.** Run from a plain background Bash call it exits 1 with `Error: --cloud requires an interactive terminal. Non-interactive invocations (piped stdout, --init-only, --sdk-url) run locally and would silently ignore --cloud.` Give it a pseudo-terminal with `script`, which exists on macOS and Linux:

  ```bash
  cd /path/to/<clone> && script -q <typescript-file> claude --cloud "$(cat <brief-file>)" --permission-mode auto </dev/null
  ```

  `</dev/null` stops it waiting on stdin; `<typescript-file>` in the scratchpad captures the output. Keep the brief in a file and pass it with `$(cat …)` rather than inlining a multi-hundred-line string in the command.
- The command stays attached through a provisioning checklist. Run it with `run_in_background: true` and poll the typescript file for the session line, or run it in the foreground with a generous timeout when the wave is one session. The output is full of terminal escapes: strip them before matching, e.g. `sed 's/\x1b\[[0-9;?]*[a-zA-Z]//g' <file> | tr '\r' '\n'`.
- Requirements: signed in to claude.ai with `claude auth login` (an API key or a third-party provider is refused), the organisation's `allow_remote_sessions` policy on, GitHub connected through the Claude GitHub App or `/web-setup`. A repository without a remote, or one the App is not installed on, is uploaded as a bundle instead (tracked files only, under 100 MB).
- Steering: `claude -p "<message>" --cloud <session_id>` posts one message and exits, printing `Session ID:` and `View:` lines. This is how the manager sends a failing-check log or a review comment to a running worker instead of redispatching. The session id comes from `.specs/<bundle>/factory-sessions.json`, written at dispatch time (see `session-registry.md`).
- Monitoring: `/tasks` in an interactive Claude Code session lists cloud sessions (press `t` to teleport); the session URL at claude.ai/code shows the diff and conversation; `gh pr list` shows the pull request once it exists.
- Session title: the cloud session takes its title from the brief's first line, but **rewrites it** — it may keep only part of the line and change its capitalisation (`factory <bundle> task 2: <title>` became `Add-mcp-start-session-tool task 2`). Never assume the listing name equals the brief's first line: read the `Created cloud session: <title>` line from the output and confirm it with `ListAgents`, then store that exact string as `agent_name`.
- Results: the session pushes a `claude/`-prefixed branch when it reaches a stopping point and stays open — it ignores the branch name the brief asks for, so plan and monitoring must match on `claude/*` plus the `task N1, N2, …:` (or `task N:`, `lane L:`) title, never on the `factory/` branch name alone. Pull requests are normally created from the web session's **Create PR** button; `gh` has been available and authenticated inside cloud sessions (workers have opened pull requests, replied to review threads and re-requested review), but this is not guaranteed, so the brief asks for a pull request when possible and otherwise a pushed branch plus the report in the final message. The manager then opens the pull request itself with `gh pr create --head <branch>`.
- A worker keeps pushing after its first commits: a branch appearing is not the end of the work. Judge "finished" by the pull request, or by commits having stopped for a good while, not by the first push.
- Cloud sessions carry only what the cloud environment provides: no user-level plugins, no `~/.myspec` credentials. `MYSPEC_API_TOKEN` must be set on the environment if the worker needs MySpec. Permission modes available in the cloud are Accept edits, Plan, and Auto (Auto only when the organisation allows it and the model supports it; bypass is not offered). Workers are started with `--permission-mode auto` after the brief; on 2026-09-26 (2.1.283) a session started this way showed **Auto** in its selector on claude.ai/code and reported running in Auto mode itself, although the docs only describe setting the mode there. A session left in Accept edits still runs unattended, because cloud sessions pre-approve file edits, so the brief must be complete either way.
- Sessions expire after inactivity and are reclaimed; reopening from claude.ai/code restores the conversation. Rate limits are shared with the whole account; parallel sessions consume them proportionately.

## Local worktree via the Agent tool

Fallback only (see Choosing a path). The subagent inherits the manager's permission mode when the manager runs in `auto`, so run the manager in `auto`. `isolation: "worktree"` gives the subagent its own git worktree; the worktree is cleaned up automatically if it made no changes. Dispatch with `run_in_background: true` (a plain Agent call blocks until the subagent returns) and wait for the completion notification. Several worktree subagents may run at once as long as their files are disjoint.

## Local worktree via a background CLI session

Fallback only (see Choosing a path).

```bash
cd <clone> && claude --bg "<brief text>" --worktree tasks-<N1>-<N2> --permission-mode auto   # prompt is POSITIONAL
cd <clone> && claude --bg "$(cat <brief>)" --mcp-config /tmp/factory-<bundle>/.mcp.json --permission-mode auto
claude agents --json     # list background sessions (plain `claude agents` needs a TTY)
claude attach <id>       # open one interactively
claude logs <id>         # recent output
```

Start every local worker with `--permission-mode auto` so it runs unattended: without it the session stops at the first permission prompt with nobody to answer, and the manager sees a worker that is idle rather than blocked. `auto` lets Claude judge each call and still denies the dangerous ones, unlike `bypassPermissions`, which the factory never uses; the brief's own prohibitions (no merging, no spec edits, no force-push) are what bound the worker.

`--bg` and `-p/--print` conflict — `--print` never starts the attachable session, and the CLI refuses the combination: pass the brief as the positional argument. `claude agents` without `--json` fails when stdout is not a terminal, which it never is from the Bash tool.

`--mcp-config <file>` adds servers to whatever the repository already provides, with no trust prompt. Avoid `--strict-mcp-config`: it limits the session to that file and switches the repository's own servers off. A worker started in the target repository picks up that repository's server pins and its gitignored `env`.

`--worktree` creates `.claude/worktrees/tasks-<N1>-<N2>/` on a new branch; a worktree holds committed content only, so a worker that needs an uncommitted file (a local `.mcp.json`, a fixture) must run in the main checkout instead. `--bg` returns immediately and prints the id that `attach`, `logs`, `stop`, and `rm` take. The documentation describes isolation checks that keep a worktree session from editing the main checkout; still review the diff scope at integration. After the pull request merges, clean up with `claude rm <id>` and `git worktree remove .claude/worktrees/tasks-<N1>-<N2>`.

## Credentials for local workers

A local worker that needs MySpec tools gets a **long-lived personal access token**, not the manager's browser login: two servers sharing `~/.myspec/oauth_creds.json` rotate each other's refresh token, and the loser's next call fails with `Refresh token rejected`, then `Not authenticated` — which can take the manager's own tools down mid-run.

1. **Check what the repository already gives the worker**: `cd <clone> && claude mcp list`. A row named `myspec` means the worker inherits a working server (the row shows its command, e.g. `npx -y @myspec/mcp-server`); add nothing.
2. **Verify that server reaches the target project** before the run: call `list_projects` and look for the project id. A PAT is scoped to one organisation, so the wrong one fails with `API token exchange failed … invalid, disabled, or expired`, or quietly lists another organisation's projects.
3. **Only when no `myspec` row exists**, hand the worker one through a temporary config. Keep the PAT in the gitignored `.claude/settings.local.json` (`env` block) and reference it as `${MYSPEC_API_TOKEN}`, so the secret stays in the environment and never lands on disk, in the brief, or in a log:

   `/tmp/factory-<bundle>/.mcp.json`:

   ```json
   {
     "mcpServers": {
       "myspec": {
         "command": "npx",
         "args": ["-y", "@myspec/mcp-server"],
         "env": { "MYSPEC_API_TOKEN": "${MYSPEC_API_TOKEN}" }
       }
     }
   }
   ```

   ```bash
   cd <clone> && MYSPEC_API_TOKEN="$(python3 -c 'import json;print(json.load(open(".claude/settings.local.json"))["env"]["MYSPEC_API_TOKEN"])')" \
     claude --bg "$(cat <brief>)" --mcp-config /tmp/factory-<bundle>/.mcp.json --permission-mode auto
   rm -f /tmp/factory-<bundle>/.mcp.json
   ```

   Do not add `--strict-mcp-config`: it restricts the session to this file and switches the repository's own servers off. Pin a prerelease (`@myspec/mcp-server@next`) only when the worker needs a tool that is not in the stable release yet, and say so in the brief.

## Remote Control

Start the manager with `claude --remote-control "factory <bundle>"` or run `/remote-control` in the session. While connected, `ListAgents` lists the account's cloud sessions newest first (bounded pages; very old sessions drop off) and `SendMessage` delivers to them through Anthropic's servers. A cloud session receives the message but cannot message back, so instructions to workers must ask for an answer on the factory board when the run has one, else through the pull request or branch — say so in the message itself, and say where a question or a `BLOCKED:` line goes. `SendMessage` also never confirms that the worker read it; only new commits, replies or a pull request prove that it acted. Sessions started with `claude --cloud` derive their title from the first prompt line but rewrite it, so briefs begin with `factory <bundle> tasks <N1>, <N2>, …: <summary>` (or the `task <N>` / `lane <L>` form) and the manager stores the title the session actually got.

## Monitoring

| Path | Signal |
|---|---|
| Agent tool (remote or worktree) | Task notification on completion; `ListAgents` while running |
| `claude --cloud` | `ListAgents` (rows labelled `cloud`, only while this session is connected to Remote Control) and `SendMessage` by session name; session URL at claude.ai/code; `/tasks` in an interactive session; the `claude/` branch or pull request appearing; `claude -p "..." --cloud <id>` to steer without Remote Control |
| `claude --bg` | `claude agents`, `claude logs <id>` |
| All | `gh pr list --state open` filtered by `factory/` branches or `task N1, N2, …:` / `task N:` / `lane L:` titles |

Use the tested scripts in the `watch` skill's `scripts/` directory (`pr-watch.sh` per pull request, `postmerge-watch.sh` per merge) rather than writing a `Monitor` command. The rules below are what those scripts already implement; they matter only if a script has to be extended:

- Emit a baseline line on the first poll, then one line per change. A failed GitHub call prints `github-unreachable`, never an empty state. A filter that only matches the happy path is indistinguishable from a dead worker; cover "no branch yet", the branch, the pull request, failing checks, and the terminal states (`MERGED`, `CLOSED`).
- Never `echo "$json" | jq`: in `zsh`, `echo` eats backslash escapes and jq dies with `Invalid string: control characters ... must be escaped`, which produces a silent watch. Use `printf '%s'`, or let `gh` do it with `--jq`.
- Match cloud workers by `claude/*` branches and `task N1, N2, …:`, `task N:` or `lane L:` titles, not by the branch name the brief asked for.
- Count only `FAILURE` and `TIMED_OUT` as failures; a `CANCELLED` check is usually a run superseded by a newer push.
- `gh run list` reports `status` in lowercase (`queued`, `in_progress`, `completed`) and `conclusion` only once completed; a filter written for uppercase values treats every running job as finished.
- Run multi-step shell logic (loops over pull requests, `read`/`set --` word splitting) under `bash` explicitly: the manager's shell may be `zsh`, which does not split unquoted variables, and a merge loop that silently mis-parses its guard can stop — or worse, proceed — for the wrong reason.
- Poll GitHub every 60-90 s, re-arm on expiry, and check the current state directly when a watch expires with no events — an empty watch is a suspect watch, not proof that nothing happened.

## Cost

Every parallel session consumes rate limit from the same account. State the number of sessions and expected sizes before each wave, keep the concurrency cap, and prefer fewer, well-briefed sessions over many thin ones. Local workers draw on the same account limits, so this cost never tilts the choice toward local; local workers add the cost of sharing this machine on top.
