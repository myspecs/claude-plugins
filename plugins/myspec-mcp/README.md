# myspec-mcp

Connects Claude Code to the [MySpec](https://myspec.dev) platform and adds Spec Driven Development (SDD) skills on top of it. The spec bundle is the source of truth, each acceptance criterion becomes a test, and progress is written back to MySpec where every collaborator sees it.

## Overview

MySpec is an AI architect that interviews you and produces a spec bundle: `constitution.md`, `requirements.md`, `solution.md`, and `tasks.md` for new projects, or change proposals and requirement deltas for existing codebases (MySpec brownfield and OpenSpec formats).

This plugin registers the official `@myspec/mcp-server` MCP server and adds five skills, so Claude Code can read those specs, build them task by task, check code against the spec, write progress back, write new specs in MySpec's formats, and share a local repository with a MySpec brownfield session.

## Features

- **No-config MCP server**: runs `npx -y @myspec/mcp-server` over stdio. The plugin holds no secrets.
- **MySpec tools** for projects, spec files (with safe concurrent writes), attachments, spec sessions, artifacts, and event stream tokens.
- **Build from the spec** (`implement`): resume where the team left off, ask about open points before coding, write tests from acceptance criteria, build one task at a time, check it against the constitution, mark it done on MySpec without overwriting other people's edits, and stop at milestones.
- **Check the spec** (`analyze`, read-only): constitution alignment, requirement-to-task coverage with a percentage, unclear wording, dependency cycles, and whether the code matches the spec. Adds gap tasks only when you approve.
- **Write specs** (`spec-authoring`): constitution, requirements (EARS+), solution, tasks, proposals, requirement deltas, and OpenSpec changes in the exact formats MySpec's reviewers expect, then push them.
- **Share local code** (`reverse-bridge`): give a MySpec brownfield session read-only access to a local repository.
- **Setup help** (`setup`): sign-in, API tokens, organizations, and error fixes.

## Prerequisites

- Claude Code with plugin support (`/plugin` works).
- Node.js 22 or newer (`node -v`) with `npx` on your `PATH`.
- A MySpec account.
- Network access to `auth.myspec.dev` and `app.myspec.dev`.

## Installation

### 1. Install the plugin

Inside Claude Code:

```text
/plugin marketplace add myspecs/claude-plugins
/plugin install myspec-mcp@myspec
```

Or from a terminal:

```bash
claude plugin marketplace add myspecs/claude-plugins
claude plugin install myspec-mcp@myspec
```

### 2. Restart Claude Code

The MCP server and skills load at startup.

### 3. Sign in

Pick one:

| Mode | How | When |
|---|---|---|
| Browser sign-in (default) | `npx -y @myspec/mcp-server login`. Add `--org <slug>` to pick an organization, or `--paste` on a remote machine without a browser | Your own laptop |
| API token | Create a token in the MySpec webapp (avatar menu, API tokens), then `export MYSPEC_API_TOKEN=msp_pat_...` in the shell that starts `claude` | CI, containers, shared machines |

Run the login command in a terminal, or inside Claude Code with the `!` prefix. The server starts before you sign in; tools return a login hint until you do, then work without a restart. Credentials are stored in `~/.myspec/`. Never put a token in `.mcp.json` or any file in a repository.

### 4. Check it works

- `/mcp` shows `myspec` as connected.
- Ask Claude: "set up MySpec and check I'm signed in." The `setup` skill runs the checks.

### Install for a whole team

Commit this to the repository's `.claude/settings.json`. Team members are offered the marketplace and plugin when they open the repository:

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

Each person still signs in (or exports `MYSPEC_API_TOKEN`) on their own machine.

### Update or remove

```text
/plugin marketplace update myspec
/plugin update myspec-mcp@myspec
```

Restart Claude Code after updating. To remove: `/plugin uninstall myspec-mcp@myspec`.

## Components

### Skills

| Skill | Invoke | Starts when you mention |
|---|---|---|
| `setup` | `/myspec-mcp:setup` | "set up MySpec", login or token questions, `Not authenticated`, `missing required claims`, HTTP 401/404 from MySpec |
| `implement` | Automatic | "implement the next task", resume, `tasks.md`, `requirements.md`, FR/NFR ids, pulling specs, applying a change proposal |
| `analyze` | Automatic | "verify the spec", "does the code match the spec", coverage, traceability, drift, milestone checks |
| `spec-authoring` | Automatic | writing or updating a spec document, EARS+ acceptance criteria, AR/BR/CR deltas, OpenSpec changes, pushing specs |
| `reverse-bridge` | Automatic | sharing a local repository with a MySpec brownfield session, `reverse_mcp_unavailable` |

Only `setup` is a slash command. The other skills start when you describe the task.

### MCP server

The server is named `myspec`. Its tools show up in Claude Code as `mcp__plugin_myspec-mcp_myspec__<tool>`.

| Group | Tools |
|---|---|
| Projects | `list_projects`, `get_project`, `create_project`, `update_project`, `archive_project`, `unarchive_project`, `delete_project` |
| Spec files | `list_spec_file`, `get_spec_file`, `read_spec_file`, `download_spec_file`, `upload_spec_file`, `update_spec_file`, `move_spec_file_to_trash`, `restore_spec_file_from_trash` |
| Attachments | `get_attachment`, `upload_attachment`, `list_attachments`, `read_attachment` |
| Spec sessions | `list_spec_sessions`, `get_spec_session`, `rename_spec_session`, `archive_spec_session`, `unarchive_spec_session`, `delete_spec_session` |
| Artifacts | `list_artifacts`, `get_artifact`, `read_artifact_file`, `create_artifact`, `write_artifact_revision`, `rollback_artifact` |
| Stream tokens | `create_stream_token`, `list_stream_tokens`, `revoke_stream_token` |

Full tool reference: [skills/implement/references/mcp-tools.md](skills/implement/references/mcp-tools.md).

## How `implement` works

1. Resume: read the `tasks.md` checkboxes on MySpec, the local `.specs/<bundle>/progress.md`, and git history.
2. Read the constitution in full, then only the requirement and solution sections the next task cites.
3. Ask about open decisions (at most five multiple-choice questions) and write the answers back into the bundle.
4. Write one test per acceptance criterion, then the code, then check it against the constitution.
5. Mark the task `[x]` on MySpec, update the progress note, and commit if you asked for commits.
6. At each milestone: run the full test suite, check code against the spec, and wait for your review.

## Usage examples

```text
Set up MySpec and check I'm signed in.
Implement the next task from the "inventory-service" project on MySpec.
Analyze the spec bundle for project X and show requirement coverage.
Does the code in this repo match the MySpec spec? What's missing?
Pull the specs for project X into .specs/ and summarise the requirements.
Write a requirements.md for this feature in MySpec format and push it to project X.
Draft an OpenSpec change proposal for adding rate limiting to the billing module.
Share this repo with my MySpec brownfield session.
```

## Configuration

Set these in the shell that starts `claude`:

| Variable | Purpose |
|---|---|
| `MYSPEC_API_TOKEN` | Long-lived API token for unattended use |
| `MYSPEC_DOWNLOAD_ROOT` | Cache folder for `read_spec_file` (default `~/.myspec`) |
| `MYSPEC_ACCESS_TOKEN` | Static access token for the reverse bridge only; the MCP server rejects it |

`download_spec_file` writes under `.specs/` in the folder Claude Code was started in. Add `.specs/` to your project's `.gitignore`.

## Troubleshooting

| Problem | Fix |
|---|---|
| `myspec` shows as failed in `/mcp` on first use | Check `node -v` is 22 or newer. Run `npx -y @myspec/mcp-server --version` once to fill the npx cache, then restart Claude Code. |
| `Not authenticated` or "run login" | Run `npx -y @myspec/mcp-server login`, or export `MYSPEC_API_TOKEN`. |
| `Could not discover endpoints` without `Not authenticated` | MySpec is unreachable: check your network, then retry. If it keeps failing, sign in again with `npx -y @myspec/mcp-server login`. |
| `missing required claims (sub, org)` or `no active organization` | You belong to more than one organization. Run `npx -y @myspec/mcp-server login --org <slug>`. |
| HTTP 401 while using an API token | The token is unknown, revoked, or expired. Create a new one in the MySpec webapp. |
| HTTP 404 for a project you can see in the webapp | You are signed in to a different organization. Run `npx -y @myspec/mcp-server login --org <slug>` for the organization that owns the project. |
| `OAuth code exchange failed: HTTP 401` during `login --paste` | The code expired (60 seconds). Sign in again and paste right away. |
| `Pasted token is missing a state suffix` | Copy the whole `<code>.<state>` value from the page, including the dot. |
| Error that `oauth_creds.json` is readable by others | Run `chmod 600 ~/.myspec/oauth_creds.json`. |
| A tool listed above is missing, or `MYSPEC_API_TOKEN` is ignored | Your cached server is old. Run `npx -y @myspec/mcp-server@latest --version`, then restart Claude Code. |
| Two sets of MySpec tools (`mcp__myspec__*` and `mcp__plugin_myspec-mcp_myspec__*`) | A project `.mcp.json` or `claude mcp add` also registers `myspec`. Remove that entry (or run `claude mcp remove myspec`) and keep the plugin. |
| Skills do not appear after install or update | Restart Claude Code. For updates, run `/plugin marketplace update myspec` before `/plugin update myspec-mcp@myspec`. |
| `reverse_mcp_unavailable` in a brownfield session | No reverse bridge is running for your account. Ask Claude to "share this repo with MySpec" (`reverse-bridge` skill). |

More detail, including how to check your active organization: [skills/setup/references/troubleshooting.md](skills/setup/references/troubleshooting.md).

## License

MIT. See [LICENSE](LICENSE).
