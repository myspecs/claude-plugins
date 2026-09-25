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

Skill names are lowercase with hyphens and do not repeat the plugin name. Only each plugin's `setup` skill is a slash command (`/<plugin>:setup`, `user-invocable: true`); every other skill sets `user-invocable: false` in its frontmatter and is started by Claude from its description, so descriptions must name the phrases and errors that should trigger it. Set the key explicitly in every new skill. Descriptions must be specific about triggers. Put long tables and verbatim formats in `references/` and link them from SKILL.md.

## MCP server integration

- Declare servers in `.mcp.json` at the plugin root:

  ```json
  { "mcpServers": { "myspec": { "type": "stdio", "command": "npx", "args": ["-y", "@myspec/mcp-server"] } } }
  ```

- Never put credentials or `${ENV}` references to credentials in plugin config. Stdio servers inherit the environment of the shell that launched Claude Code, so users export tokens there.
- Tools from a plugin server are named `mcp__plugin_<plugin>_<server>__<tool>`; for this plugin, `mcp__plugin_myspec-mcp_myspec__<tool>`. State the prefix once per SKILL.md and use bare tool names elsewhere.

## MySpec facts

- npm package `@myspec/mcp-server`, bin `myspec-mcp`. `latest` is the stable release; `next` is a prerelease from every merge to main. Requires Node 22+.
- Skills and READMEs target the production MySpec platform only (`auth.myspec.dev`, `app.myspec.dev`). Do not document dev or staging environments, `--user-auth-url`, or `MYSPEC_USER_AUTH_URL` in any skill, reference or README.
- CLI: `serve` (default), `login [--org <slug>] [--paste]`, `logout`, `reverse --root <dir>`, `--version`.
- Environment: `MYSPEC_API_TOKEN` (0.3.0+), `MYSPEC_DOWNLOAD_ROOT`, `MYSPEC_ACCESS_TOKEN` (`reverse` only).
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

How the manager and workers behave lives in the output style and the skills. This section lists only what a change must keep intact; when one of these rules changes, update every file that states it.

- The output style is never `force-for-plugin` (users opt in) and is always referenced as `myspec-factory:Software Factory Manager`; the bare name does not resolve.
- Safety rules every skill keeps: auto-merge is never enabled in any form (per-pull-request Auto-fix is fine; it never merges); merges happen only under the run `policy` or by the user, through the ready-to-merge gate (`integrate` §3); nothing is dispatched until the spec gate passes; the manager is the only writer of `tasks.md`; every question to the user goes through `AskUserQuestion`.
- One source of truth per topic; other files point to it instead of restating it: task grouping (`dispatch` §0), dispatch paths and cloud mechanics (`dispatch/references/cloud-vs-local.md`), the worker brief (`dispatch/references/worker-brief.md`), the registry (`dispatch/references/session-registry.md`), the factory board (the `board` skill).
- Cross-skill contracts that change together: pull-request titles `task N1, N2, …:`, `task N:`, `lane L:` (matched by `pr-watch.sh` and `integrate`); the brief's first line `factory <bundle> …` (the cloud session title); the `## Factory report` format (brief, `integrate`); the board's database layout (`board` skill `references/protocol.md`, `references/sample-calls.md`, `templates/factory-board.html`, and the brief's `## Factory board` section).
- Registry state, including the board link, run key and worker keys, is written through `skills/dispatch/scripts/registry.py`, never by hand; board data is written with `ArtifactData` as the `board` skill shows. Stream token URLs are never stored anywhere; keep `registry.py`'s refusal of them.
- Monitors use the tested scripts in `skills/watch/scripts/`; skills never describe hand-written loops. A script prints `github-unreachable` for a failed GitHub call, and skills treat it as unknown state. Test script changes against a real repository before committing (`bash -n`, then a run against a merged pull request and a finished merge commit; `board-tick.sh` with a 1-minute interval).
- Test a factory board change on a throwaway board with a `claude --bg` worker (`claude -p` sessions have no Artifact tools), then delete the board.
- Refer to the other plugin's skills by name (`myspec-mcp:implement`), never by relative path; plugins are cached in separate version directories.

## Writing style for skills

- Instructions are for Claude: imperative, ordered steps, explicit stop conditions.
- Interactive commands (browser login, long-running bridges) are handed to the user, not run in a foreground Bash call.
- Never instruct Claude to force a write by omitting `expected_version`.
