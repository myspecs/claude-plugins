# myspec-factory

Turns Claude Code into a **Software Factory Manager**: a manager that runs a MySpec spec bundle to completion. It groups related tasks and starts one Claude Code worker session per group, checks and merges the pull requests they open, marks tasks done on MySpec, and stops at each milestone for your review.

## Overview

[MySpec](https://myspec.dev) produces a spec bundle (constitution, requirements, solution, tasks). The `myspec-mcp` plugin lets one Claude Code session build it task by task. This plugin adds the layer above that. The manager never writes feature code. It:

1. Groups related tasks (a chain of dependent tasks, tasks that touch the same code, tasks for the same requirement) so one worker does them all, and plans waves of groups that run in parallel, or, for a brownfield bundle without `tasks.md`, writes the task list itself: one worker for a small change, up to 3 parallel workers for a large one.
2. Starts one worker session per group: a Claude Code cloud session, or a local git worktree session only when the cloud is not allowed or not available. A worker gets a single task only when nothing relates to it.
3. Checks each pull request against its tasks' acceptance criteria and the constitution.
4. Merges under the policy you agree on, marks its tasks done on MySpec, and moves to the next wave.
5. Stops at the end of each milestone for your review.

It can also run unattended shifts on a schedule.

## Features

- **Software Factory Manager output style**: a clear role with hard limits (no work starts on an unfinished spec, no coding, no marking tasks done without checking, no force pushes, no auto-merge), the run loop, milestone gates, and a cost estimate before every wave.
- **Task planning for brownfield changes**: when a bundle has no `tasks.md`, the manager writes one. A small change goes to a single worker; a large change with independent parts is split into 2–3 lanes that run in parallel (one worker, one branch, one pull request each). You approve it before it is uploaded to MySpec.
- **Wave planning** from task dependencies and solution modules: related tasks go to one worker, one branch and one pull request, which saves setup and review rounds and avoids conflicts between branches. The board comes from MySpec checkboxes and open pull requests, so it is never out of date.
- **Dispatch** with self-contained worker briefs: the tasks, their acceptance criteria, the requirements and constitution sections it depends on, and what the pull request must contain.
- **Integration**: required checks, a test for each acceptance criterion, a constitution and scope review, a merge under the agreed policy, then `[x]` written to MySpec.
- **Live event feed**: changes to `tasks.md` and other spec files, worker reports, and finished spec sessions arrive as notifications instead of polling.
- **Scheduled shifts**: a cloud routine that integrates, marks tasks done, and dispatches the next wave on a schedule.

## Prerequisites

- Claude Code with plugin support (`/plugin` works).
- The [`myspec-mcp`](../myspec-mcp/README.md) plugin installed and signed in. The manager reads and writes the spec bundle through it.
- Node.js 22 or newer.
- The GitHub CLI (`gh`) signed in with push and pull-request rights on the target repository.
- A local clone of the target repository, with its default branch pushed to GitHub.

For **cloud workers** (optional, recommended):

- Claude Code on the web enabled for your account.
- The [Claude GitHub App](https://github.com/apps/claude) installed on the repository.
- A cloud environment at claude.ai/code with `MYSPEC_API_TOKEN` set, if workers need to read MySpec.

For **local workers** (fallback):

- The `claude` CLI and git worktrees.
- A MySpec API token for the workers (see [Configuration](#configuration)).

## Installation

### 1. Install both plugins

Inside Claude Code:

```text
/plugin marketplace add myspecs/claude-plugins
/plugin install myspec-mcp@myspec
/plugin install myspec-factory@myspec
```

Or from a terminal:

```bash
claude plugin marketplace add myspecs/claude-plugins
claude plugin install myspec-mcp@myspec
claude plugin install myspec-factory@myspec
```

Install `myspec-factory` only on the machine that runs the manager. Worker sessions need `myspec-mcp` only.

### 2. Restart Claude Code and sign in to MySpec

```bash
npx -y @myspec/mcp-server login
```

Run it in a terminal, or inside Claude Code with the `!` prefix. `/mcp` should show `myspec` as connected. See the [myspec-mcp README](../myspec-mcp/README.md#installation) for API tokens and organizations.

### 3. Prepare the repository

In your clone of the target repository, start Claude Code and run:

```text
/myspec-factory:setup
```

It checks MySpec and GitHub access, cloud readiness, and branch protection, then proposes repository settings so workers load `myspec-mcp`. It writes nothing until you approve. At the end it lists the MySpec projects you can access, asks you to pick one, and opens that project's live event feed, so you can start a run straight away.

### 4. Turn on the manager persona

The output style is off by default, so sessions that should write code keep the normal style. Turn it on for the managed repository only.

Either use `/config` → Output style → **Software Factory Manager**, or add this to the repository's `.claude/settings.local.json`:

```json
{ "outputStyle": "myspec-factory:Software Factory Manager" }
```

Use the full name `myspec-factory:Software Factory Manager` in settings files.

### 5. Start the manager with Remote Control

Remote Control lets the manager see its cloud workers and send them messages:

```bash
claude --remote-control "factory <bundle>"
```

Or run `/remote-control` inside a running session.

### 6. Start a run

```text
Run the factory for project X, bundle Y.
```

### Update or remove

```text
/plugin marketplace update myspec
/plugin update myspec-factory@myspec
```

Restart Claude Code after updating. To remove: `/plugin uninstall myspec-factory@myspec`.

## Components

### Output style

**Software Factory Manager** (`output-styles/software-factory-manager.md`). Keeps Claude's git and verification skills but forbids implementing tasks.

### Skills

| Skill | Invoke | Purpose |
|---|---|---|
| `setup` | `/myspec-factory:setup` | Check MySpec and GitHub access and cloud readiness; propose repository settings so workers load `myspec-mcp`; pick a MySpec project and open its event feed |
| `watch` | Used by the manager | Open the project's live event feed and react to each event; polls when the feed is not available |
| `plan` | Used by the manager | Build the board, group related tasks into one worker each, and plan waves of groups; write `tasks.md` when a brownfield bundle has none, as one lane or up to 3 parallel lanes by size |
| `dispatch` | Used by the manager | Start one worker per group of related tasks; cloud first, local worktree as fallback |
| `integrate` | Used by the manager | Verify and merge worker pull requests, mark tasks done on MySpec, run the milestone gate |
| `shift` | Used by the manager | Draft and create a scheduled cloud routine for one unattended shift |

The manager also uses `myspec-mcp:implement` (how progress is written back) and `myspec-mcp:analyze` (the code-to-spec check at milestone gates).

## A run, end to end

1. Run `/myspec-factory:setup` in the repository and approve the settings it proposes.
2. Switch to the Software Factory Manager style and ask: "Run the factory for project X, bundle Y."
3. The manager opens the event feed, then asks once for the number of parallel workers, the merge method, how much it may do without asking (the autonomy level, below), whether cloud sessions are allowed, and who settles minor implementation details (`minor_defaults`: you, or the manager with each choice recorded as a reversible Clarification). It checks that the spec is complete and asks you about every open question or doubt, bundling small defaults into one approve-or-change question; nothing is dispatched until that passes. Then it plans wave 1 and tells you the cost. For a brownfield bundle without `tasks.md`, it first drafts the task list (one lane for a small change, up to 3 parallel lanes for a large one) and asks for your approval.
4. Workers open pull requests titled `task N1, N2, …: <summary>` (or `task N: <title>` for a single task, `lane L: tasks …` for a lane) with a `## Factory report` at the end.
5. The manager verifies each pull request, merges it once it passes the merge gate, watches the deploy, marks its tasks `[x]` on MySpec, and dispatches the next wave.
6. At the end of a milestone it runs the test suite, checks the code against the spec, uploads a milestone summary, drafts the spec corrections and follow-up tasks, and asks you one question about what to apply and dispatch.

### Autonomy levels

| Level | Merges | Dispatches the next wave |
|---|---|---|
| `ask-each` | Asks before every merge | Asks |
| `merge-on-gate` (recommended) | Merges on its own once the gate passes | Asks |
| `full` | Merges on its own once the gate passes | Starts the next wave of the same milestone on its own when what it waits for has merged and deployed |

At every level the manager still asks you about spec questions, changes a worker made beyond the spec, rewrites of spec documents, and starting the next milestone. The merge gate is the same at every level: the reviewer approved the pull request's latest commit, required checks are green, review threads are resolved, the pull request merges cleanly with auto-merge off, the manager's own verification covers every change, and no spec question is open.

## What workers deliver

One group of related tasks, one branch, one pull request, titled `task N1, N2, …: <summary>`, with one commit per task. A task with nothing related to it gets its own worker and a pull request titled `task N: <title>`. A lane worker does every task of its lane in order on one branch and opens one pull request titled `lane L: tasks N1, N2, …`; it only edits the paths its lane owns. Tests are named after each acceptance criterion, and the body ends with a `## Factory report`. When a worker cannot finish, the report starts with `BLOCKED: spec` or `BLOCKED: env`. Workers never edit `tasks.md` or other spec files.

## Safety and cost

- The manager asks before writing repository settings or creating routines, and never merges outside the agreed policy. It asks before starting sessions unless you chose the `full` autonomy level for the run.
- Parallel sessions share your account's rate limit. The manager states how many sessions each wave starts and keeps to the limit you set.
- No force pushes, no bypassing branch protection, no merging red pull requests, no auto-merge. It merges one pull request at a time and waits for that merge's CI/CD before the next.

## Usage examples

```text
Set up the factory for this repository.
Run the factory for project "inventory-service", bundle "v1".
Plan the waves: which tasks can run in parallel?
Dispatch wave 2 in the cloud, at most 3 workers.
Integrate the open factory pull requests.
Schedule a factory shift every night at 2am.
```

## Configuration

| Setting | Where | Purpose |
|---|---|---|
| `outputStyle: "myspec-factory:Software Factory Manager"` | `.claude/settings.local.json` of the managed repository | Turns on the manager persona for that checkout only |
| Remote Control (`claude --remote-control` or `/remote-control`) | The manager's session | Lets the manager list cloud workers and message them |
| Parallel workers, merge method, autonomy level, cloud allowed, `minor_defaults` | Asked once per run, stored under `policy` in `.specs/<bundle>/factory-sessions.json` | Limits for every wave of the run; tell the manager to change the autonomy level at any time |
| `extraKnownMarketplaces` and `enabledPlugins` | Repository `.claude/settings.json` (written by `setup` when you approve) | Lets workers load `myspec-mcp` |
| `MYSPEC_API_TOKEN` | Cloud environment at claude.ai/code | MySpec access for cloud workers and scheduled shifts (they cannot use browser sign-in) |
| `MYSPEC_API_TOKEN` | `env` in the managed repository's gitignored `.claude/settings.local.json` | MySpec access for local workers. A separate token keeps workers off the manager's browser sign-in, which two servers cannot share |
| `.specs/<bundle>/factory-sessions.json` | Local, gitignored | Record of every dispatched worker: tasks, session id, URL, branch, status |
| `.specs/<bundle>/factory-run.md` | Local, gitignored | Run log and board cache |

Add `.specs/` to the repository's `.gitignore`.

## Troubleshooting

| Problem | Fix |
|---|---|
| **Software Factory Manager** is not in the output style list | Check `myspec-factory` is enabled in `/plugin`, then restart Claude Code. In settings files use `myspec-factory:Software Factory Manager`. |
| The manager writes code or skips its checks | The style is not active. Switch with `/config`; a change in a settings file only applies to new sessions. |
| The manager and local workers both lose MySpec access (`Refresh token rejected`, then `Not authenticated`) | They shared one browser sign-in. Give local workers their own `MYSPEC_API_TOKEN` in `.claude/settings.local.json`, then reconnect the manager's server in `/mcp`. |
| A worker's token fails with `API token exchange failed … invalid, disabled, or expired` | The token is revoked, expired, or from a different organization. Create a token in the organization that owns the project. |
| Cloud dispatch is refused | Your plan or organization does not allow cloud sessions. Enable Claude Code on the web, or let the manager use local worktrees. |
| Cloud workers do not show up, or the manager cannot message them | Connect Remote Control (`/remote-control`) in the manager session. Without it the manager can still steer workers with `claude -p "<message>" --cloud <session_id>`. |
| Cloud workers cannot reach MySpec | Add `MYSPEC_API_TOKEN` to the cloud environment and allow network access to npm and the MySpec hosts. Briefs already include the needed spec text, so this only matters when a worker must read more. |
| Workers have no MySpec tools | The repository settings from `setup` are missing or not pushed. Cloud sessions clone the branch from GitHub, so commit and push `.claude/settings.json`. If workers still have no tools, run `setup` again; it offers a root `.mcp.json` as a fallback. |
| Two sets of MySpec tools in a worker | The repository enables `myspec-mcp` and also declares `myspec` in a root `.mcp.json`. Keep the plugin entry and remove the `.mcp.json` server. |
| Auto-fix is not offered on a worker's pull request | Install the [Claude GitHub App](https://github.com/apps/claude) on the repository. Without it, workers only react while their session is running. |
| A green pull request never gets a bot review | No review was requested. Run `gh pr edit <n> --add-reviewer <bot>`. |
| The event feed went quiet | The connection dropped. Ask the manager to reopen the feed ("reopen the event feed"); it creates a new token and revokes the old one. |
| A deployment runs an older commit after two quick merges | Workflows that build a shared tag such as `:latest` raced. Re-run the workflow for the newest merge commit. |
| A scheduled shift ran but did nothing | Read the routine's run log. The usual causes are a missing `MYSPEC_API_TOKEN` in the cloud environment, or a repository that was not prepared with `/myspec-factory:setup`. |

For MySpec sign-in and connection errors, see the [myspec-mcp troubleshooting](../myspec-mcp/README.md#troubleshooting).

## License

MIT. See [LICENSE](LICENSE).
