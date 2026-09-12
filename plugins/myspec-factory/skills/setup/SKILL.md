---
name: setup
description: Prepare a repository and this machine for a MySpec software factory run. Use when the user says "set up the factory", "prepare this repo for factory sessions", "factory prerequisites", before the first myspec-factory run in a repository, or when a factory worker session could not reach MySpec, GitHub, or the plugin. Checks MySpec sign-in, cloud-session readiness, repository configuration for plugins and MCP, GitHub access, and branch protection.
---

# Factory setup

The factory has three parties: the manager (this session), worker sessions (Claude Code cloud sessions or local worktree sessions), and the MySpec platform. Each needs access. Check in order; stop at the first failure and give the user the fix. Every repository write below is opt-in: describe the change, get a yes, then write.

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

## 2. Manager: GitHub access

```bash
gh auth status
gh repo view --json nameWithOwner,defaultBranchRef,viewerPermission
```

Need push permission and the ability to open and merge pull requests. Record the default branch. Check classic branch protection with `gh api repos/{owner}/{repo}/branches/<default>/protection` (a 404 means no classic protection) and rulesets with `gh api repos/{owner}/{repo}/rules/branches/<default>`. Required checks and required approvals found here become part of the merge policy.

## 3. Workers: cloud readiness

Cloud sessions run on Anthropic's infrastructure with a clone of the repository. They load the repository's `.claude/settings.json`, `.mcp.json`, and `CLAUDE.md`, and nothing from the user's `~/.claude`. Check:

1. `claude --help` lists `--cloud`; the CLI is signed in to claude.ai (`/status` shows a claude.ai login method; an API key or third-party provider cannot start cloud sessions); the organisation's `allow_remote_sessions` policy is on; and the GitHub App or `/web-setup` token grants access to this repository. Do not start a probe session; the first real dispatch happens only after the user allows cloud dispatch. If that dispatch is refused for policy or plan reasons, workers fall back to local worktrees; say so.
   The cloud clones the GitHub remote at the current branch, not the local checkout: before dispatching, the base branch must be pushed and the manager's checkout must sit on it.
2. A cloud environment exists with network egress to `registry.npmjs.org`, `auth.myspec.dev`, `app.myspec.dev`, and the platform host (or the dev equivalents), and carries `MYSPEC_API_TOKEN` (there is no browser in the cloud, so `login` cannot run there). Prefer the environment's API credentials feature over a plain environment variable where the plan offers it. The user configures this at claude.ai/code; you cannot.
3. Workers do not strictly need MySpec access: the manager inlines the spec excerpts into every brief, and workers report through pull requests. MySpec access in workers is only needed when the brief tells them to read more of the bundle.

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

`CLAUDE.md`: the managed `<!-- myspec:start -->` block from the `myspec-mcp:implement` skill's session-handoff reference, naming the project and bundle, so workers and future managers find the specification.

Do not enable `myspec-factory` in the repository's `enabledPlugins`; workers must not run the manager persona.

## 5. Workers: local fallback

Local worktree sessions need `git worktree` support and the `claude` CLI; check `claude --help` lists `--worktree` and `--bg`. Each worker gets its own worktree under `.claude/worktrees/`, so the main checkout must be clean enough to branch from the default branch.

## 6. Report

Table: party, check, status, fix. Then say whether Remote Control is connected, whether cloud dispatch is possible, whether MySpec-in-worker is configured, and the merge policy inputs you found (default branch, protection, required checks).
