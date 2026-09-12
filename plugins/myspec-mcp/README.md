# myspec-mcp

Connects Claude Code to the [MySpec](https://myspec.dev) platform and adds Spec Driven Development (SDD) skills on top of it: the specification bundle is the source of truth, each acceptance criterion becomes a test, and progress is recorded where every collaborator sees it.

## Overview

MySpec is an AI architect that interviews you and produces a reviewable specification bundle: `constitution.md`, `requirements.md`, `solution.md`, and `tasks.md` for greenfield projects, or change proposals and requirement deltas for existing codebases (MySpec brownfield and OpenSpec formats).

This plugin registers the official `@myspec/mcp-server` MCP server via `npx` and ships five skills so Claude Code can read those specs, implement them task by task, verify code against spec, write progress back, author new specs in the platform's exact formats, and share a local repository with a MySpec brownfield session.

## Features

- Zero-config MCP registration: `npx -y @myspec/mcp-server` over stdio. No secrets in the plugin.
- MySpec tools for projects, spec files with optimistic-concurrency writes, and attachments (17 tools on the stable 0.3.0 server). Spec sessions, artifacts, attachment listing and reading, event stream tokens, and paginated reads arrive with server 0.4.0 (today the `next` prerelease) and are documented ahead of time.
- `setup` skill: prerequisites, sign-in, API tokens, dev environments, troubleshooting.
- `implement` skill: resume from shared state, clarify before coding, derive tests from acceptance criteria, implement one task at a time, check it against the constitution, mark it done on the platform without clobbering other people's edits, and stop at milestone checkpoints.
- `analyze` skill: read-only verification. Spec consistency (constitution alignment, requirement-to-task coverage with a percentage, ambiguity, dependency cycles) and convergence (does the code implement the spec; append-only gap tasks on approval).
- `spec-authoring` skill: write constitution, requirements (EARS+), solution, tasks, proposals, requirement deltas, and OpenSpec changes exactly as MySpec's reviewers expect, then push them.
- `reverse-bridge` skill: expose a local repo read-only to the MySpec cloud agent for brownfield spec sessions.

## Prerequisites

- Node.js 22 or newer (`node -v`) and `npx`.
- A MySpec account. Sign-in happens in the browser; API tokens are available for unattended use.
- Network access to `auth.myspec.dev` and `app.myspec.dev` (or the dev equivalents).

## Installation

```
/plugin marketplace add myspecs/claude-plugins
/plugin install myspec-mcp@myspec
```

Restart Claude Code, then sign in once from your terminal (or with the `!` prefix inside Claude Code):

```bash
npx -y @myspec/mcp-server login
```

Check with `/mcp` that `myspec` is connected, or ask Claude to "set up MySpec".

## Authentication

| Mode | How | When |
|---|---|---|
| Browser sign-in (default) | `npx -y @myspec/mcp-server login` (add `--org <slug>` to pin an organization, `--paste` on remote machines) | Interactive use on a laptop |
| API token | Create it in the webapp (avatar menu, API tokens), then `export MYSPEC_API_TOKEN=msp_pat_...` in the shell that starts `claude` | CI, containers, shared machines. Needs server 0.3.0+ |
| Dev environment | `login --user-auth-url https://dev-auth.myspec.dev` or `MYSPEC_USER_AUTH_URL` | Projects on the dev platform |

The MCP server starts before you sign in; tool calls simply return a login hint until you do, and work right after without a restart. Credentials live in `~/.myspec/` (`oauth_creds.json` mode 0600, `settings.json`). Never put a token in `.mcp.json` or any repository file.

## Components

### Skills

| Skill | Invoke | Triggers on |
|---|---|---|
| `setup` | `/myspec-mcp:setup` | "set up MySpec", login and token questions, `Not authenticated`, `missing required claims`, HTTP 401/404 from MySpec |
| `implement` | `/myspec-mcp:implement` | "implement the next task", resume, tasks.md, requirements.md, FR/NFR ids, pulling specs, applying a change proposal |
| `analyze` | `/myspec-mcp:analyze` | "verify the spec", "does the code match the spec", coverage, traceability, drift, milestone checkpoints |
| `spec-authoring` | `/myspec-mcp:spec-authoring` | writing or updating any spec document, EARS+ acceptance criteria, AR/BR/CR deltas, OpenSpec changes, pushing specs |
| `reverse-bridge` | `/myspec-mcp:reverse-bridge` | sharing a local repo with a MySpec brownfield session, `reverse_mcp_unavailable` |

Skills also trigger automatically from natural language.

### MCP server

Server key `myspec`; tools are named `mcp__plugin_myspec-mcp_myspec__<tool>`. Full reference: [skills/implement/references/mcp-tools.md](skills/implement/references/mcp-tools.md).

| Group | Tools |
|---|---|
| Projects (0.3.0+) | `list_projects`, `get_project`, `create_project`, `update_project`, `archive_project`, `unarchive_project`, `delete_project` |
| Spec files (0.3.0+) | `list_spec_file`, `get_spec_file`, `read_spec_file`, `download_spec_file`, `upload_spec_file`, `update_spec_file`, `move_spec_file_to_trash`, `restore_spec_file_from_trash` |
| Attachments | `get_attachment`, `upload_attachment` (0.3.0+); `list_attachments`, `read_attachment` (0.4.0+) |
| Spec sessions (0.4.0+) | `list_spec_sessions`, `get_spec_session`, `rename_spec_session`, `archive_spec_session`, `unarchive_spec_session`, `delete_spec_session` |
| Artifacts (0.4.0+) | `list_artifacts`, `get_artifact`, `read_artifact_file`, `create_artifact`, `write_artifact_revision`, `rollback_artifact` |
| Stream tokens (0.4.0+) | `create_stream_token`, `list_stream_tokens`, `revoke_stream_token` |

## How the implementation loop works

1. Resume: read `tasks.md` checkboxes (shared truth), the local `.specs/<bundle>/progress.md`, and git history.
2. Read the constitution in full, then only the requirement and solution sections the next task cites.
3. Clarify open decisions with at most five multiple-choice questions; answers are written back into the bundle.
4. One test per acceptance criterion (EARS+ patterns map directly to test shapes), then the implementation, then a constitution check.
5. Mark the task `[x]` with optimistic concurrency, update the progress note, commit if the user opted in.
6. At each milestone: full test run, convergence analysis, human review before continuing.

## Usage examples

```
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

| Variable | Purpose |
|---|---|
| `MYSPEC_API_TOKEN` | Long-lived API token for unattended use (0.3.0+). Set in the shell that launches Claude Code |
| `MYSPEC_USER_AUTH_URL` | Auth server for non-production environments |
| `MYSPEC_DOWNLOAD_ROOT` | Cache root for `read_spec_file` (default `~/.myspec`) |
| `MYSPEC_AI_AGENT_WS_URL` | ai-agent WebSocket URL override for `reverse` |
| `MYSPEC_ACCESS_TOKEN` | Static access token for `reverse` only; rejected by the MCP server itself |

`download_spec_file` writes under `.specs/` in the directory Claude Code was started in. Add `.specs/` to your project's `.gitignore`.

## Troubleshooting

See [skills/setup/references/troubleshooting.md](skills/setup/references/troubleshooting.md). Common cases:

- `Not authenticated`: run the login command above.
- `missing required claims (sub, org)`: `npx -y @myspec/mcp-server login --org <slug>`.
- `myspec` shows as failed in `/mcp` on first use: run `npx -y @myspec/mcp-server --version` once (warms the npx cache), confirm Node 22+, restart.
- A tool from the 0.4.0 list is missing: the stable release is still 0.3.0. Wait for the release, or register `npx -y @myspec/mcp-server@next` yourself in a project `.mcp.json` and disable this plugin's server to avoid duplicates.
- Two sets of MySpec tools: the project's own `.mcp.json` also declares `myspec`; remove one.

## License

MIT. See [LICENSE](LICENSE).
