# Dispatch paths

Facts below come from `claude --help` in this build and the Claude Code documentation for cloud sessions, worktrees, and background agents. Verify availability in the current session before relying on a path.

## Choosing a path

Always start agents in the cloud. The local path is a fallback, not an equal choice; the order is in the dispatch skill's path table. Every agent lives for the whole run, so a path is usable only when the manager can send the agent its next assignment: `claude -p … --cloud <id>` for a cloud agent, `SendMessage` for a local `claude --bg` agent.

- **Why cloud**: each cloud session runs in its own isolated environment, with its own CPU, memory, disk, clone, dependency installs, and build and test runs. Parallel cloud agents never compete for machine resources.
- **Why not local**: local agents (`claude --bg` sessions) all run on this machine, next to the manager. A worktree keeps their files apart but not their CPU and memory. Parallel installs, builds and test suites slow every agent and the manager, and can fail on timeouts or out-of-memory kills that look like real test failures. They can also clash on fixed ports, a shared local database, or the Docker daemon.
- **A bigger team makes the case stronger**: the more agents run at once, the more the cloud wins. Never pick local to avoid the cloud set-up steps.
- **Fall back to local only when**:
  - the run `policy` has cloud dispatch not allowed;
  - the user asked for local agents;
  - the cloud refused the start for a lasting reason: the CLI not signed in to claude.ai, the organisation's `allow_remote_sessions` policy off, or GitHub not connected for this repository (the CLI then uploads a bundle instead, and without GitHub access the session cannot push its branch or open a pull request). A timeout or a failed GitHub or network call is not a refusal: retry, or check the state directly, before falling back.
- **When falling back with more than one agent**: tell the user why the cloud was not used and that the local agents will share this machine, then ask with `AskUserQuestion` whether to lower the team size or run a team of one.
- Shared rate limits are not a reason to pick local: local and cloud sessions draw on the same account limits (see Cost).

## Not for team agents: the Agent tool

The Agent tool's `isolation: "remote"` and `isolation: "worktree"` subagents are not used as team agents. A subagent's run ends with its final report, there is no tested way to hand it a next assignment, it has no effort setting, and it ends with the manager's own session (a manager restart loses the team). The manager still uses the Agent tool for its own read-only helpers: verification, drafting, test runs.

## Cloud session via the CLI

Source: the Claude Code on the web documentation (code.claude.com/docs/en/claude-code-on-the-web).

```bash
claude --cloud "<brief text>" --permission-mode auto         # new cloud session for the current repo, in auto mode
claude --cloud "<brief text>" --name "Ada (a1)" --model opus --effort high --permission-mode auto   # named, with the agent's model and effort
claude --cloud "<brief text>" --environment <ccpool_...> --permission-mode auto   # on a specific self-hosted environment
claude -p "<follow-up>" --cloud <session_id|url>             # send one message to a running or idle session, then exit
claude -p "<follow-up>" --cloud <session_id> --output-format json   # {ok, session_id, url}
claude --teleport <session_id>                               # pull the session's branch and history into this terminal
```

Facts that shape dispatch:

- `--cloud` takes the description (the brief) as its own value: nothing may come between `--cloud` and the brief. `claude --cloud --permission-mode auto "<brief>"` fails with `Error: --cloud requires a description` (observed with 2.1.283); `claude --cloud "<brief>" --permission-mode auto` creates the session, and so does `claude --permission-mode auto --cloud "<brief>"` (other flags before `--cloud`; used for every dispatch of a factory run with 2.1.28x, 2026-09).
- `--model` and `--effort` work with `--cloud` and set the new session's model and effort level, placed after the brief like `--permission-mode` (checked on 2026-10-04 with 2.1.289: `--model sonnet --effort low` started a Sonnet session at low effort). Which ones to pass: `model-and-effort.md`.
- `claude --cloud "<task>"` creates a new cloud session for the **current directory's GitHub remote at the current branch**. It clones the remote, not the local checkout: push first, and start from the branch the agents should base on (normally the default branch). One repository per session. Each invocation is an independent session, so several agents can be started back to back or in parallel.
- **Always `cd` into a local clone of the target repository in the same command.** The manager's own working directory is usually a different repository (the plugin repo, a notes repo, the directory Claude Code was started in), and `--cloud` reads the remote of the current directory — dispatching from the wrong directory silently starts a session on the wrong repository. Every dispatch command therefore begins `cd /path/to/<clone> && claude --cloud …`, and the Bash tool's working directory does not persist between calls, so the `cd` is repeated in each one. If the user has no local clone of the target repository, ask for the path or clone it first; do not dispatch from a directory whose `git remote -v` you have not checked.
- **The clone must be a trusted folder.** Run from a folder Claude Code has not trusted yet (a fresh clone in the scratchpad), `claude --cloud` stops at the folder-trust dialog and never creates the session (observed 2026-11-06, 2.1.319). Use a clone the user has opened in Claude Code before, or ask the user to open the new clone once and accept the dialog.
- **`--cloud` requires a TTY.** Run from a plain background Bash call it exits 1 with `Error: --cloud requires an interactive terminal. Non-interactive invocations (piped stdout, --init-only, --sdk-url) run locally and would silently ignore --cloud.` Give it a pseudo-terminal with `script`, which exists on macOS and Linux:

  ```bash
  cd /path/to/<clone> && script -q <typescript-file> claude --cloud "$(cat <brief-file>)" --name "<title>" --model <model> --effort <effort> --permission-mode auto </dev/null
  ```

  `</dev/null` stops it waiting on stdin; `<typescript-file>` in the scratchpad captures the output. Keep the brief in a file and pass it with `$(cat …)` rather than inlining a multi-hundred-line string in the command.
- The command stays attached through a provisioning checklist. Run it with `run_in_background: true` and poll the typescript file for the session line, or run it in the foreground with a generous timeout when the team is one agent. It returns about a minute after the session line appears. The output is full of terminal escapes: strip them before matching, e.g. `sed 's/\x1b\[[0-9;?]*[a-zA-Z]//g' <file> | tr '\r' '\n'`.
- Requirements: signed in to claude.ai with `claude auth login` (an API key or a third-party provider is refused), the organisation's `allow_remote_sessions` policy on, GitHub connected through the Claude GitHub App or `/web-setup`. A repository without a remote, or one the App is not installed on, is uploaded as a bundle instead (tracked files only, under 100 MB).
- Next assignments and steering: `claude -p "$(cat <message-file>)" --cloud <session_id> </dev/null` posts one message and exits, printing `Sent to cloud session.`, `Session ID:` and `View:` lines. It reaches a session that is working (the message is queued) and one that finished its turn and sits idle (it wakes and acts: checked on 2026-11-06 with 2.1.319, where an idle session answered a message within seconds and, given a second assignment, created a second branch and opened a second pull request). This is how the manager sends an agent its next assignment, a failing-check log, a review comment or a board doorbell, and the only channel for cloud agents (the `board` skill §5 has the rule and why). Keep the message in a file: a permission hook may block a command line that quotes a rebase or a lease-protected push, and `</dev/null` stops the three-second wait for stdin. The session id comes from `.specs/<bundle>/factory-sessions.json`, written when the agent started (see `session-registry.md`).
- Monitoring: `/tasks` in an interactive Claude Code session lists cloud sessions (press `t` to teleport); the session URL at claude.ai/code shows the diff and conversation; `gh pr list` shows the pull request once it exists.
- Session title: left alone, the cloud makes up a title from the brief — it may keep only part of the first line or name the session after the first assignment's work (`factory <bundle> task 2: <title>` became `Add-mcp-start-session-tool task 2`; `factory spike agent a1` became `Clean up internal/fdprobe`). The manager therefore sets each agent's title to its name (`Ada (a1)`): `--name "<title>"` on the start command, then, when the `Created cloud session: <title>` line shows another title, `claude -p "/rename <title>" --cloud <session_id>`. `--name` works for cloud sessions: `claude --cloud "<brief>" --name "Grace (a3)" …` printed `Created cloud session: Grace (a3)` (2026-11-06, 2.1.319). `/rename` sent through `claude -p` is delivered but not confirmed to rename a cloud session, and the title cannot be read back from the CLI (attaching to a cloud session is not enabled on every account), so the start output is the check. The procedure, including the one-time check with the user, is the dispatch skill's §3a; store what the session shows as `agent_name` (and `cloud_title` when it differs).
- Results: the session pushes a `claude/`-prefixed branch per assignment and stays open — it ignores the branch name the assignment asks for, so plan and monitoring must match on `claude/*` plus the `task N1, N2, …:` (or `task N:`) title, never on the `factory/` branch name alone. Pull requests are normally created from the web session's **Create PR** button; `gh` has been available and authenticated inside cloud sessions (workers have opened pull requests, replied to review threads and re-requested review), but this is not guaranteed, so the brief asks for a pull request when possible and otherwise a pushed branch plus the report in the final message. The manager then opens the pull request itself with `gh pr create --head <branch>`.
- An agent keeps pushing after its first commits: a branch appearing is not the end of the work. Judge "finished" by the pull request, or by commits having stopped for a good while, not by the first push.
- Cloud sessions carry only what the cloud environment provides: no user-level plugins, no `~/.myspec` credentials. `MYSPEC_API_TOKEN` must be set on the environment if the agent needs MySpec. Permission modes available in the cloud are Accept edits, Plan, and Auto (Auto only when the organisation allows it and the model supports it; bypass is not offered). Agents are started with `--permission-mode auto` after the brief; on 2026-09-26 (2.1.283) a session started this way showed **Auto** in its selector on claude.ai/code and reported running in Auto mode itself, although the docs only describe setting the mode there. A session left in Accept edits still runs unattended, because cloud sessions pre-approve file edits, so the brief must be complete either way.
- Sessions expire after long inactivity and are reclaimed; reopening from claude.ai/code restores the conversation. An agent whose session expired is replaced (the dispatch skill, Replacing an agent). Rate limits are shared with the whole account; parallel sessions consume them proportionately.

## Local agent via a background CLI session

Fallback only (see Choosing a path).

```bash
cd <clone> && claude --bg "<brief text>" --name "<title>" --worktree a<k> --model <model> --effort <effort> --permission-mode auto   # prompt is POSITIONAL
cd <clone> && claude --bg "$(cat <brief>)" --mcp-config /tmp/factory-<bundle>/.mcp.json --model <model> --effort <effort> --permission-mode auto
claude agents --json     # list background sessions (plain `claude agents` needs a TTY)
claude attach <id>       # open one interactively
claude logs <id>         # recent output
```

Start every local agent with its rung's `--model` and `--effort` (`model-and-effort.md`; the same ladder as cloud agents) and with `--permission-mode auto` so it runs unattended: without it the session stops at the first permission prompt with nobody to answer, and the manager sees an agent that is idle rather than blocked. `auto` lets Claude judge each call and still denies the dangerous ones, unlike `bypassPermissions`, which the factory never uses; the brief's own prohibitions (no merging, no spec edits, no force-push) are what bound the agent.

`--bg` and `-p/--print` conflict — `--print` never starts the attachable session, and the CLI refuses the combination: pass the brief as the positional argument. `claude agents` without `--json` fails when stdout is not a terminal, which it never is from the Bash tool.

`--mcp-config <file>` adds servers to whatever the repository already provides, with no trust prompt. Avoid `--strict-mcp-config`: it limits the session to that file and switches the repository's own servers off. An agent started in the target repository picks up that repository's server pins and its gitignored `env`.

`--worktree` creates `.claude/worktrees/a<k>/`; the agent creates one branch per assignment inside it (from a fresh `origin/<default>`). A worktree holds committed content only, so an agent that needs an uncommitted file (a local `.mcp.json`, a fixture) must run in the main checkout instead. `--bg` returns immediately and prints the id that `attach`, `logs`, `stop`, and `rm` take. The documentation describes isolation checks that keep a worktree session from editing the main checkout; still review the diff scope at integration. When the agent is retired or replaced, clean up with `claude rm <id>` and `git worktree remove .claude/worktrees/a<k>`.

## Credentials for local agents

A local agent that needs MySpec tools gets a **long-lived personal access token**, not the manager's browser login: two servers sharing `~/.myspec/oauth_creds.json` rotate each other's refresh token, and the loser's next call fails with `Refresh token rejected`, then `Not authenticated` — which can take the manager's own tools down mid-run.

1. **Check what the repository already gives the agent**: `cd <clone> && claude mcp list`. A row named `myspec` means the agent inherits a working server (the row shows its command, e.g. `npx -y @myspec/mcp-server`); add nothing.
2. **Verify that server reaches the target project** before the run: call `list_projects` and look for the project id. A PAT is scoped to one organisation, so the wrong one fails with `API token exchange failed … invalid, disabled, or expired`, or quietly lists another organisation's projects.
3. **Only when no `myspec` row exists**, hand the agent one through a temporary config. Keep the PAT in the gitignored `.claude/settings.local.json` (`env` block) and reference it as `${MYSPEC_API_TOKEN}`, so the secret stays in the environment and never lands on disk, in the brief, or in a log:

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
     claude --bg "$(cat <brief>)" --mcp-config /tmp/factory-<bundle>/.mcp.json --model <model> --effort <effort> --permission-mode auto
   rm -f /tmp/factory-<bundle>/.mcp.json
   ```

   Do not add `--strict-mcp-config`: it restricts the session to this file and switches the repository's own servers off. Pin a prerelease (`@myspec/mcp-server@next`) only when the agent needs a tool that is not in the stable release yet, and say so in the brief.

## Remote Control

Start the manager with `claude --remote-control "factory <bundle>"` or run `/remote-control` in the session. While connected, `ListAgents` lists the account's cloud sessions newest first (bounded pages; very old sessions drop off), which shows whether each is busy or idle. Do not message cloud agents with `SendMessage`, although it delivers: in a factory run (2026-09) it left cloud sessions waiting on a human until the owner opened them, so cloud agents get assignments and steering through `claude -p … --cloud` only (the `board` skill §5); `SendMessage` stays for local `claude --bg` sessions. A cloud session receives a message but cannot message back, so instructions to agents must ask for an answer on the factory board when the run has one, else through the pull request or branch — say so in the message itself, and say where a question or a `BLOCKED:` line goes. No message channel confirms that the agent read it; only new commits, replies, a board `ack` or a pull request prove that it acted. Sessions started with `claude --cloud` derive their title from the first prompt line but rewrite it, so the manager sets the title to the agent's name (the dispatch skill's §3a), agent briefs begin with `factory <bundle> agent <name> (a<k>)`, and the manager stores the title the session actually shows.

## Monitoring

| Path | Signal |
|---|---|
| `claude --cloud` | `ListAgents` (rows labelled `cloud`, only while this session is connected to Remote Control); session URL at claude.ai/code; `/tasks` in an interactive session; the `claude/` branch or pull request appearing; `claude -p "..." --cloud <id>` to steer |
| `claude --bg` | `claude agents`, `claude logs <id>` |
| All | `gh pr list --state open` filtered by `factory/` branches or `task N1, N2, …:` / `task N:` titles |

Use the tested scripts in the `watch` skill's `scripts/` directory (`pr-watch.sh` per pull request, `postmerge-watch.sh` per merge) rather than writing a `Monitor` command. The rules below are what those scripts already implement; they matter only if a script has to be extended:

- Emit a baseline line on the first poll, then one line per change. A failed GitHub call prints `github-unreachable`, never an empty state. A filter that only matches the happy path is indistinguishable from a dead agent; cover "no branch yet", the branch, the pull request, failing checks, and the terminal states (`MERGED`, `CLOSED`).
- Never `echo "$json" | jq`: in `zsh`, `echo` eats backslash escapes and jq dies with `Invalid string: control characters ... must be escaped`, which produces a silent watch. Use `printf '%s'`, or let `gh` do it with `--jq`.
- Match cloud agents by `claude/*` branches and `task N1, N2, …:` or `task N:` titles, not by the branch name the brief asked for.
- Count only `FAILURE` and `TIMED_OUT` as failures; a `CANCELLED` check is usually a run superseded by a newer push.
- `gh run list` reports `status` in lowercase (`queued`, `in_progress`, `completed`) and `conclusion` only once completed; a filter written for uppercase values treats every running job as finished.
- Run multi-step shell logic (loops over pull requests, `read`/`set --` word splitting) under `bash` explicitly: the manager's shell may be `zsh`, which does not split unquoted variables, and a merge loop that silently mis-parses its guard can stop — or worse, proceed — for the wrong reason.
- Poll GitHub every 60-90 s, re-arm on expiry, and check the current state directly when a watch expires with no events — an empty watch is a suspect watch, not proof that nothing happened.

## Cost

Every parallel session consumes rate limit from the same account. State the team size, each agent's queue weight and rung before starting the team, keep to `policy.team_size`, and prefer a smaller, well-briefed team over many thin agents. An idle agent costs nothing; a long-lived one saves a setup per assignment. Local agents draw on the same account limits, so this cost never tilts the choice toward local; local agents add the cost of sharing this machine on top.
