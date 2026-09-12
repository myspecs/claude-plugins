# claude-plugins

Official, MySpec-managed directory of high quality Claude Code plugins that use the MySpec MCP server to run the software development lifecycle with Spec Driven Development.

## Quick start

1. Add the marketplace:

   ```
   /plugin marketplace add myspecs/claude-plugins
   ```

2. Install the plugins:

   ```
   /plugin install myspec-mcp@myspec
   /plugin install myspec-factory@myspec
   ```

3. Restart Claude Code, then sign in to MySpec from your terminal (or with the `!` prefix in Claude Code):

   ```bash
   npx -y @myspec/mcp-server login
   ```

4. Verify: `/mcp` lists `myspec` as connected, or ask Claude to "set up MySpec".

Requires Node.js 22 or newer and a [MySpec](https://myspec.dev) account.

## Plugins

| Plugin | What it does |
|---|---|
| [myspec-mcp](plugins/myspec-mcp/README.md) | Registers `@myspec/mcp-server` and adds five skills: `setup`, `implement` (task-by-task SDD from a spec bundle: clarify, tests from acceptance criteria, constitution check, progress written back), `analyze` (read-only spec consistency and code-to-spec convergence with coverage), `spec-authoring` (constitution, requirements, solution, tasks, proposals, deltas, OpenSpec changes in MySpec's formats), and `reverse-bridge` (share a local repo with a brownfield spec session) |
| [myspec-factory](plugins/myspec-factory/README.md) | The **Software Factory Manager** output style plus `setup`, `watch`, `plan`, `dispatch`, `integrate`, and `shift` skills: opens the project's live event feed (stream token into `Monitor`), plans waves from `tasks.md`, spawns one Claude Code cloud (or worktree) session per task, verifies and merges their pull requests, marks tasks done on MySpec, gates on milestones, and can run unattended shifts as a scheduled routine. Requires `myspec-mcp` |

## Local development

```
/plugin marketplace add /path/to/claude-plugins
/plugin install myspec-mcp@myspec
```

Validate before committing:

```bash
claude plugin validate --strict .
claude plugin validate --strict plugins/myspec-mcp
claude plugin validate --strict plugins/myspec-factory
```

Contribution rules (structure, version bumps, documentation) are in [CLAUDE.md](CLAUDE.md).

## License

MIT. See [LICENSE](LICENSE).
