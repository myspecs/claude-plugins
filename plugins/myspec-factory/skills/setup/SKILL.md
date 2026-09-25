---
name: setup
description: Prepare a repository and this machine for a MySpec software factory run, then pick the MySpec project and open its event feed. Use when the user runs /myspec-factory:setup or says "set up the factory", "prepare this repo for factory sessions", "factory prerequisites", before the first myspec-factory run in a repository, or when a factory worker session could not reach MySpec, GitHub, or the plugin. Checks MySpec sign-in, cloud-session readiness, repository configuration for plugins and MCP, GitHub access, and branch protection; ends by listing the user's MySpec projects and starting the event-stream Monitor for the one they choose.
user-invocable: true
argument-hint: "[project name] [path to the repository clone]"
---

# Factory setup

The factory has three parties: the manager (this session), worker sessions (Claude Code cloud sessions or local worktree sessions), and the MySpec platform. Each needs access. Check in order; stop at the first failure and give the user the fix. Every repository write below is opt-in: describe the change, get a yes (with `AskUserQuestion`), then write. The last step (7) picks the MySpec project and opens its event feed, so the run can start straight after setup.

**Never print a secret.** Settings files (`.claude/settings.local.json`, `.claude/settings.json`, `.mcp.json`, `~/.claude/settings.json`) and environment files hold tokens and API keys. Read only the key NAMES you need, never the values — for example `python3 -c 'import json;print(sorted(json.load(open(".claude/settings.local.json")).get("env",{})))'` — and never `cat` such a file. Redaction by pattern is not enough: token formats vary and one missed pattern prints the secret into the transcript. To check that a variable is set, test for it (`[ -n "${MYSPEC_API_TOKEN:-}" ] && echo set`) instead of echoing it.

## 0. Manager: output style

The manager persona lives in this plugin's `Software Factory Manager` output style. Check which style is active: your system prompt carries an `Output Style:` heading when one is set, and the `outputStyle` key in `.claude/settings.local.json`, `.claude/settings.json`, or `~/.claude/settings.json` shows what is configured. If the active style is not `Software Factory Manager`, tell the user to switch before the run, either interactively:

```
/config   →  Output style  →  Software Factory Manager
```

or in the repository's settings so only this checkout runs the persona (plugin styles are addressed as `<plugin>:<style>`):

```json
{ "outputStyle": "myspec-factory:Software Factory Manager" }
```

in `.claude/settings.local.json` (personal) or `.claude/settings.json` (shared with the team). A settings change applies to new sessions; `/config` applies immediately. Do not continue the run under a different style; the persona carries the prohibitions that keep the manager from coding or merging outside policy.

## 1. Manager: MySpec access

The `myspec-mcp@myspec` plugin must be installed and signed in. Confirm `mcp__plugin_myspec-mcp_myspec__list_projects` exists and returns a project list. If not, run the `myspec-mcp:setup` skill (it hands the interactive login to the user).

Also check for `mcp__plugin_myspec-mcp_myspec__create_stream_token`. Present (server 0.4.0+, today the `next` prerelease, and a platform with `REALTIME_STREAM_ENABLED`): the manager can open the project event feed with the `watch` skill. Absent: the manager polls instead; say so in the report.

## 1b. Manager: Remote Control (required for cloud visibility)

The manager sees and messages its cloud workers only while its own session is connected to Remote Control: `ListAgents` then lists the account's Claude Code on the web sessions (labelled `cloud`) and `SendMessage` reaches them by name through Anthropic's servers. Without it, cloud sessions are invisible to the manager and steering falls back to the `claude -p ... --cloud <id>` CLI.

Tell the user to start the manager one of these ways (all need a claude.ai sign-in, not an API key; on Team and Enterprise an Owner must enable Remote Control):

```bash
claude --remote-control "factory <bundle>"     # new interactive session, connected from the start
```

or, inside an already running session:

```
/remote-control factory <bundle>
```

Confirm with `/list-agents` (`/peers`): the listing should show this session's name on the first line and cloud sessions as rows labelled `cloud`. A `/rc active` indicator shows in the terminal while connected. Remote Control needs the terminal to stay open; the manager's own work keeps running locally.

If the repository or user settings set `isolatePeerMachines: true`, every message to a cloud session asks the user for approval first; say so.

## 1c. Manager: factory board tools

Workers report progress and ask questions mid-work on a factory board, a private claude.ai artifact the manager publishes once for the repository (or shares with another repository) and reuses for every run (the `board` skill). Check that this session has the tools: the `Artifact` tool is in the tool list, and `ToolSearch` `select:ArtifactData,ArtifactComments` loads both. Nothing is published during setup.

- Present: the run gets a board. Whether the owner's **Send to Claude** on a board comment wakes the manager shows in the board watch's status (`ArtifactComments` `watch` without a URL lists it) once a run starts on the board; without auto-replies armed, comments are read at the manager's next board check.
- Missing (an API-key or third-party-provider sign-in, or a build without them): the run works without a board; workers report through pull requests only. Say so in the report.
- Cloud workers get the same tools from the same claude.ai account; the first worker's Factory report (`- Board:` line) confirms it. Local `claude --bg` workers have them; `claude -p` (print) sessions do not.
- An existing board: the `<!-- myspec-factory:start -->` block in the repository's `CLAUDE.md` (or `AGENTS.md`), else `registry.py … board` from the dispatch skill. Report its link; every run reuses it. The block is written and committed by the `board` skill when it publishes the board, with the user's agreement; setup does not write it.

## 2. Manager: GitHub access

```bash
gh auth status
gh repo view --json nameWithOwner,defaultBranchRef,viewerPermission
```

Need push permission and the ability to open and merge pull requests. Record the default branch.

Check that the Claude GitHub App is installed at the organization level with `gh api orgs/{org}/installations --jq '.installations[].app_slug'`, which lists all installed GitHub Apps for the organization (replace `{org}` with the organization name from the repository). If "claude" appears in the output, the Claude GitHub App is installed. Auto-fix — the per-pull-request toggle that lets a worker answer CI failures and review comments on its own — needs it, and every factory pull request is meant to run with Auto-fix on. Without the App, say that workers will only react while their session is alive, and that the manager must steer them for each red check. Before recommending Auto-fix, check whether a pull-request comment can trigger privileged automation in this repository (Atlantis, Terraform Cloud, `issue_comment` workflows); Auto-fix replies post under the user's GitHub account and would trigger those. Check classic branch protection with `gh api repos/{owner}/{repo}/branches/<default>/protection` (a 404 means no classic protection) and rulesets with `gh api repos/{owner}/{repo}/rules/branches/<default>`. Required checks and required approvals found here become part of the merge policy.

## 3. Workers: cloud readiness

Cloud sessions run on Anthropic's infrastructure with a clone of the repository. They load the repository's `.claude/settings.json`, `.mcp.json`, and `CLAUDE.md`, and nothing from the user's `~/.claude`. Check:

1. `claude --help` lists `--cloud`; the CLI is signed in to claude.ai (`/status` shows a claude.ai login method; an API key or third-party provider cannot start cloud sessions); the organisation's `allow_remote_sessions` policy is on; and the GitHub App or `/web-setup` token grants access to this repository. Do not start a probe session; the first real dispatch happens only after the user allows cloud dispatch. If that dispatch is refused for policy or plan reasons, workers fall back to local worktrees; say so.
   The cloud clones the GitHub remote at the current branch, not the local checkout: before dispatching, the base branch must be pushed and the manager's checkout must sit on it.
2. A cloud environment exists with network egress to `registry.npmjs.org`, `auth.myspec.dev`, `app.myspec.dev`, and the platform host, and carries `MYSPEC_API_TOKEN` (there is no browser in the cloud, so `login` cannot run there). Prefer the environment's API credentials feature over a plain environment variable where the plan offers it. The user configures this at claude.ai/code; you cannot.
3. Workers do not strictly need MySpec access: the manager inlines the spec excerpts into every brief, and workers report through pull requests. MySpec access in workers is only needed when the brief tells them to read more of the bundle.

## 3b. Workers: local readiness and credentials

A local worker (worktree or background session) runs on this machine with the user's environment, so its MySpec access is the manager's responsibility:

1. Check what a local worker inherits: `claude mcp list` in the repository. A `myspec` row means it already has a server; verify that server reaches the target project with `list_projects` before the run. When there is no row, the worker gets a temporary `--mcp-config` file whose `env` references `${MYSPEC_API_TOKEN}` from the gitignored `.claude/settings.local.json` (recipe in the dispatch skill's `cloud-vs-local.md`). A PAT is scoped to one organisation — the wrong one fails with `API token exchange failed … invalid, disabled, or expired` — so report the organisation you verified against, and never print the token.
2. Two MySpec servers must not share `~/.myspec/oauth_creds.json` at the same time: a refresh in one rotates the refresh token and the other fails with `Refresh token rejected`, then `Not authenticated`, which takes the manager's own tools down mid-run. This is the reason workers get their own PAT.


## 4. Workers: repository configuration (opt-in writes)

Offer to add, never overwrite silently:

`.claude/settings.json` (merge into existing keys):

```json
{
  "extraKnownMarketplaces": {
    "myspec": { "source": { "source": "github", "repo": "myspecs/claude-plugins" } }
  },
  "enabledPlugins": {
    "myspec-mcp@myspec": true
  }
}
```

Enabling `myspec-mcp@myspec` already registers the `myspec` server for the session, so do not add a root `.mcp.json` for it as well; two declarations produce two tool sets. Whether cloud sessions install plugins from `enabledPlugins` automatically is documented but not verified here: treat it as an assumption and confirm on the first cloud worker (its tool list should contain `mcp__plugin_myspec-mcp_myspec__*`). If it does not, the fallback is a root `.mcp.json` declaring the server (tools then appear as `mcp__myspec__*`) with the plugin entry removed.

`.gitignore`: add `.specs/`.

`CLAUDE.md`: each plugin keeps its own block there. The `<!-- myspec-mcp:start -->` block names the MySpec project so workers and future managers find the specification; it belongs to the myspec-mcp plugin, so when it is missing, let the `myspec-mcp:implement` skill offer to write it (its session-handoff reference has the format) rather than writing it here. The `<!-- myspec-factory:start -->` block holds the factory board link; the `board` skill writes it, never setup.

Do not enable `myspec-factory` in the repository's `enabledPlugins`; workers must not run the manager persona.

## 5. Workers: local fallback

Local worktree sessions need `git worktree` support and the `claude` CLI; check `claude --help` lists `--worktree` and `--bg`. Each worker gets its own worktree under `.claude/worktrees/`, so the main checkout must be clean enough to branch from the default branch.

## 6. Report

Table: party, check, status, fix. Then say whether Remote Control is connected, whether the factory board tools are present, whether cloud dispatch is possible, whether MySpec-in-worker is configured, and the merge policy inputs you found (default branch, protection, required checks, the reviewer whose approval gates a merge). Keep those inputs for the run: once a bundle is chosen they go under `policy` in `.specs/<bundle>/factory-sessions.json`, so the run does not rediscover them. They are discoverable or run preferences, so they never go into `CLAUDE.md`; the only committed factory fact is the board link (`board` skill).

## 7. Pick the project and open its event feed

Setup ends with the manager listening to one MySpec project.

1. `mcp__plugin_myspec-mcp_myspec__list_projects` (no query, `limit` 100) to list every project this sign-in can access. When the user named a project in the arguments or earlier in the conversation and exactly one project matches it, use that one and skip to step 3.
2. Ask with one `AskUserQuestion`:
   - One project: do not ask; say which project you are using and continue.
   - Two to four projects: one option per project, labelled with its name, the description saying its last update and what it is (from `description`). Put the project whose `description` or name matches the repository clone first, marked "(Recommended)".
   - More than four: the four most recently updated as options (the repository's match first when it is among them); the user can type any other project name through the "Other" choice. Resolve a typed name with `list_projects(query: "<name>")`.
3. Run the `watch` skill for the chosen project: list its spec files to fill the `files` map, mint a stream token (8-hour `ttl_seconds`, the default event scope in `watch`, `label` `factory <project name> <YYYY-MM-DD>` since no bundle is chosen yet), and open the event-feed `Monitor`. No bundle registry exists yet, so record the token's `token_id`, `token_prefix`, `expires_at` and `last_seq` (never the URL) with the `files` map in `.specs/factory-stream.json`; the run moves them under `stream` in `.specs/<bundle>/factory-sessions.json` once a bundle is chosen. Wait for `stream.ready` and check its `resource.id` is the chosen project. When `create_stream_token` is missing, say the feed is not available and that the run will poll (the `watch` skill's fallback).
4. Report the project name and id, the token prefix and expiry (never the URL), and the bundles the project contains (`list_spec_file`, grouped by `specs/<bundle>/`), with any spec session still `generating`. Then offer the next step: pick the bundle and start the run (spec gate, then planning).
