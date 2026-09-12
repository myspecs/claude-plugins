# claude-plugins

Official, MySpec-managed directory of high quality Claude Code plugins that use the MySpec MCP server to run the software development lifecycle with Spec Driven Development.

## Quick start

1. Add the marketplace:

   ```
   /plugin marketplace add myspecs/claude-plugins
   ```

2. Install the plugin:

   ```
   /plugin install myspec-mcp@myspec
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

## Local development

```
/plugin marketplace add /path/to/claude-plugins
/plugin install myspec-mcp@myspec
```

Validate before committing:

```bash
claude plugin validate --strict .
claude plugin validate --strict plugins/myspec-mcp
```

Contribution rules (structure, version bumps, documentation) are in [CLAUDE.md](CLAUDE.md).

## License

MIT. See [LICENSE](LICENSE).
