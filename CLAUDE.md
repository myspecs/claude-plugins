# Agent Instructions

Guidelines for developing and maintaining the plugins in this marketplace.

## Plugin structure

```
plugins/<plugin-name>/
├── .claude-plugin/
│   └── plugin.json           # metadata: name, description, version, author, license, keywords
├── .mcp.json                 # optional: MCP servers this plugin registers
├── skills/
│   └── <skill-name>/
│       ├── SKILL.md          # frontmatter (name, description) + instructions
│       └── references/*.md   # optional supporting docs
├── README.md
└── LICENSE
```

Only `plugin.json` goes inside `.claude-plugin/`. Skills, commands, agents, hooks, and `.mcp.json` live at the plugin root.

## Version management

- Bump the version in `plugin.json` on every change to plugin files other than `README.md` or `LICENSE`. That includes SKILL.md files, reference docs, `.mcp.json`, and `plugin.json` itself. Patch for edits to existing skills; minor for a new skill or a new MCP server; major for a breaking change to how users invoke the plugin.
- Reason: Claude Code caches plugins per version under `~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/`. An unbumped change is never picked up by `/plugin update`.
- Semantic versioning `MAJOR.MINOR.PATCH`; documentation-only edits to README or LICENSE need no bump.

## Marketplace registration

Every plugin must be listed in `.claude-plugin/marketplace.json`:

```json
{ "name": "my-plugin", "source": "./plugins/my-plugin" }
```

The marketplace `name` is `myspec`, so plugin ids are `<plugin>@myspec`. User-facing installation and troubleshooting live in `README.md`; keep development guidance here and do not repeat it there.

## Documentation requirements

READMEs are for users; this file is for developing the plugins. Do not repeat content between them.

- Root `README.md`: what each plugin does, how to install and update them in Claude Code, and troubleshooting.
- Plugin `README.md`: Overview, Features, Prerequisites, Installation (marketplace add, install, restart, sign-in, verify, update or remove), Components, Usage examples, Configuration, Troubleshooting, License. Write in plain language.
- Troubleshooting in READMEs covers problems a user can see and fix. Internal quirks that skills already handle (CLI flag conflicts, TTY wrappers, branch prefixes, session title rewrites) go in the skill's `references/` or in the conventions below, not in a README.
- Local development (installing from a path, validating) is covered under Validation below.

`SKILL.md` frontmatter:

```yaml
---
name: skill-name
description: What the skill does and the phrases or errors that should trigger it.
---
```

Skill names are lowercase with hyphens and do not repeat the plugin name (they surface as `/<plugin>:<skill>`). Descriptions must be specific about triggers. Put long tables and verbatim formats in `references/` and link them from SKILL.md.

## MCP server integration

- Declare servers in `.mcp.json` at the plugin root:

  ```json
  { "mcpServers": { "myspec": { "type": "stdio", "command": "npx", "args": ["-y", "@myspec/mcp-server"] } } }
  ```

- Never put credentials or `${ENV}` references to credentials in plugin config. Stdio servers inherit the environment of the shell that launched Claude Code, so users export tokens there.
- Tools from a plugin server are named `mcp__plugin_<plugin>_<server>__<tool>`; for this plugin, `mcp__plugin_myspec-mcp_myspec__<tool>`. State the prefix once per SKILL.md and use bare tool names elsewhere.

## MySpec facts

- npm package `@myspec/mcp-server`, bin `myspec-mcp`. `latest` is the stable release; `next` is a prerelease from every merge to main. Requires Node 22+.
- CLI: `serve` (default), `login [--org <slug>] [--paste] [--user-auth-url <url>]`, `logout`, `reverse --root <dir>`, `--version`.
- Environment: `MYSPEC_API_TOKEN` (0.3.0+), `MYSPEC_USER_AUTH_URL`, `MYSPEC_DOWNLOAD_ROOT`, `MYSPEC_AI_AGENT_WS_URL`, `MYSPEC_ACCESS_TOKEN` (`reverse` only).
- State: `~/.myspec/settings.json` (non-secret), `~/.myspec/oauth_creds.json` (mode 0600).
- Spec file paths on the platform are rooted at `specs/` or `openspec/` with at most three directory levels below the root. `download_spec_file` mirrors them under `.specs/` locally.
- `update_spec_file` takes `expected_version` (the `content_version` from the read the body was based on).
- Source of truth for tool behaviour: `projects/mcp-server/src/server/tools/*.ts` in the myspec-monorepo; document formats: the `.prompty` templates under `projects/ai-agent/src/modules/agentic-workflow/workflows/*/prompts/templates/`.

## Validation

Before committing:

```bash
python3 -m json.tool .claude-plugin/marketplace.json
python3 -m json.tool plugins/myspec-mcp/.claude-plugin/plugin.json
python3 -m json.tool plugins/myspec-mcp/.mcp.json
claude plugin validate --strict .
claude plugin validate --strict plugins/myspec-mcp
claude plugin validate --strict plugins/myspec-factory
```

`claude plugin validate` does not inspect `output-styles/`; check those by activating the style in a headless probe (`--settings` does not apply it; use `.claude/settings.local.json` in a scratch repo).

Then install locally (`/plugin marketplace add /path/to/claude-plugins`, `/plugin install myspec-mcp@myspec`), restart, and confirm `/mcp` shows `myspec` connected and the skills appear.

## Git workflow

- Conventional commits: `feat:`, `fix:`, `docs:`, `refactor:`, `chore:`.
- Mention the version bump in the commit body when one is included.
- Commit and push only when asked.

## SDD conventions the plugin defines

The platform emits `- [ ]` and never parses checkboxes, so these are plugin conventions. Keep every skill consistent with them:

- Done is `- [x]` in `tasks.md`, written with `expected_version`. No other markers.
- Extra information goes in indented sub-bullets under a task (`- Clarification:`, `- Progress:`, `- Merged:`) or in trailing sections (`## Clarifications` in requirements.md, `## Milestone N: Convergence` and `## Branch Plan` in tasks.md). Never new annotation lines or inline markers.
- Local, gitignored state lives in `.specs/<bundle>/progress.md`.
- Analysis is read-only; remediation needs approval and is append-only.
- Commits happen only when the user opts in at the start of a loop.

## myspec-factory conventions

- The output style is never `force-for-plugin`; users opt in (see `README.md`). Skills and settings refer to it as `myspec-factory:Software Factory Manager`, because plugin styles resolve as `<plugin>:<style name>` and the bare name does not resolve.
- Merging is decided by the manager under the agreed policy or by the user; auto-merge is never enabled (`gh pr merge --auto`, GitHub's auto-merge toggle, merge queues). Per-pull-request Auto-fix is expected and never merges.
- No dispatch until the spec gate passes: the whole bundle is complete, `myspec-mcp:analyze` (spec consistency) has no CRITICAL or HIGH finding, and every doubt is clarified with the user. A mid-run spec change or a `BLOCKED: spec` report pauses all dispatch until the gate passes again.
- The manager is the only writer of `tasks.md`; workers report through pull requests (`factory/<bundle>/task-<N>` branches, `task N:` titles, a `## Factory report` in the body).
- A brownfield bundle may have no `tasks.md`. The manager then writes one after the rest of the bundle passes the spec gate, grouped into lanes that run in parallel (one worker, one `factory/<bundle>/lane-<L>` branch, one `lane L:` pull request each). Parallelism is not mandatory: a small change is one lane; only a large change with independent parts gets 2-3 lanes (disjoint paths, no cross-lane dependencies, shared contracts written in full in both lanes), recorded in `## Branch Plan`, and uploads it only after the user approves. Bundles that ship their own `tasks.md` keep wave planning.
- The board is derived from platform checkboxes and open pull requests; `.specs/<bundle>/factory-run.md` is a cache.
- Stream token URLs from `create_stream_token` go straight into `Monitor` and are never written to any file, log, commit, issue, or reply; the registry keeps only the token id, prefix, expiry, and last `seq`.
- Every dispatched session is recorded at once in `.specs/<bundle>/factory-sessions.json` (task, session id, URL, branch, status); steering uses the id from that file with `claude -p "<message>" --cloud <session_id>`.
- Dispatch order: Agent tool `isolation: "remote"`, `claude --cloud`, Agent tool `isolation: "worktree"`, `claude --bg --worktree`. Verify availability; do not assume.
- Every cloud command runs from a local clone of the target repository (`cd <clone> && claude …`), and `claude --cloud` needs a TTY: dispatch through `script -q <file> claude --cloud "$(cat <brief>)" </dev/null`. The cloud clones the GitHub remote of the current directory at the current branch, rewrites the session title, and pushes its own `claude/`-prefixed branch.
- The manager session runs with Remote Control connected (`claude --remote-control` or `/remote-control`); steering order is `SendMessage` to the cloud session's listing name, then `claude -p ... --cloud <id>`. Worker briefs start with the line `factory <bundle> task <N>: <title>` (or `factory <bundle> lane <L>: <name>`) because that becomes the session title.
- Refer to the other plugin's skills by name (`myspec-mcp:implement`), never by relative path; plugins are cached in separate version directories.

## Writing style for skills

- Instructions are for Claude: imperative, ordered steps, explicit stop conditions.
- Interactive commands (browser login, long-running bridges) are handed to the user, not run in a foreground Bash call.
- Never instruct Claude to force a write by omitting `expected_version`.
