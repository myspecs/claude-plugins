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

The marketplace `name` is `myspec`; users install with `/plugin install <plugin>@myspec`.

## Documentation requirements

Plugin `README.md`: Overview, Features, Prerequisites, Installation, Components, Usage examples, Configuration, Troubleshooting, License.

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
```

Then install locally (`/plugin marketplace add /path/to/claude-plugins`, `/plugin install myspec-mcp@myspec`), restart, and confirm `/mcp` shows `myspec` connected and the skills appear.

## Git workflow

- Conventional commits: `feat:`, `fix:`, `docs:`, `refactor:`, `chore:`.
- Mention the version bump in the commit body when one is included.
- Commit and push only when asked.

## SDD conventions the plugin defines

The platform emits `- [ ]` and never parses checkboxes, so these are plugin conventions. Keep every skill consistent with them:

- Done is `- [x]` in `tasks.md`, written with `expected_version`. No other markers.
- Extra information goes in indented sub-bullets under a task (`- Clarification:`, `- Progress:`) or in trailing sections (`## Clarifications` in requirements.md, `## Milestone N: Convergence` in tasks.md). Never new annotation lines or inline markers.
- Local, gitignored state lives in `.specs/<bundle>/progress.md`.
- Analysis is read-only; remediation needs approval and is append-only.
- Commits happen only when the user opts in at the start of a loop.

## Writing style for skills

- Instructions are for Claude: imperative, ordered steps, explicit stop conditions.
- Interactive commands (browser login, long-running bridges) are handed to the user, not run in a foreground Bash call.
- Never instruct Claude to force a write by omitting `expected_version`.
