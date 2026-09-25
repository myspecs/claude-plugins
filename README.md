# claude-plugins

Claude Code plugins from MySpec. They connect Claude Code to the [MySpec](https://myspec.dev) platform and use it to build software with Spec Driven Development: the spec bundle (constitution, requirements, solution, tasks) is the source of truth, and Claude reads it, builds from it, and writes progress back.

The marketplace is named `myspec` and has two plugins.

## Plugins

### myspec-mcp

Connects Claude Code to MySpec. It registers the `@myspec/mcp-server` MCP server (as `myspec`) and adds five skills. Install this one first: `myspec-factory` needs it.

| Skill | Use it to |
|---|---|
| `/myspec-mcp:setup` | Sign in, use an API token, switch organization, fix connection errors |
| `implement` | Build a spec bundle one task at a time: ask about open points, write tests from acceptance criteria, check the constitution, mark the task done on MySpec |
| `analyze` | Check a bundle for gaps and conflicts, and check whether the code matches the spec (read-only) |
| `spec-authoring` | Write or update constitution, requirements, solution, tasks, change proposals, and OpenSpec changes in MySpec's formats, then push them |
| `reverse-bridge` | Share a local repository with a MySpec brownfield spec session |

Details: [plugins/myspec-mcp/README.md](plugins/myspec-mcp/README.md).

### myspec-factory

Turns Claude Code into a **Software Factory Manager**. The manager does not write code. It plans waves of tasks from `tasks.md`, groups related tasks and starts one Claude Code worker session per group (in the cloud, or in a local git worktree when the cloud is not allowed or not available), checks and merges their pull requests, marks tasks done on MySpec, and stops at each milestone for your review.

It ships the **Software Factory Manager** output style and seven skills:

| Skill | Use it to |
|---|---|
| `/myspec-factory:setup` | Check MySpec and GitHub access, cloud readiness, and repository settings before the first run; pick a MySpec project and open its event feed |
| `watch` | Open the project's live event feed so changes arrive without polling |
| `plan` | Build the task board and group ready tasks into waves |
| `dispatch` | Start one worker session per group of related tasks |
| `integrate` | Verify and merge worker pull requests, mark tasks done, run the milestone gate |
| `board` | Keep the repository's factory board: one private claude.ai page where workers post progress and questions and the manager answers |
| `shift` | Schedule an unattended shift as a cloud routine |

Details: [plugins/myspec-factory/README.md](plugins/myspec-factory/README.md).

Only the two `setup` skills are slash commands. The other skills start on their own when you describe the task in plain words, for example "implement the next task from project X" or "run the factory for bundle Y".

## Requirements

- Claude Code with plugin support (`/plugin` works).
- Node.js 22 or newer, with `npx` on your `PATH`.
- A MySpec account.
- For `myspec-factory`: the GitHub CLI (`gh`) signed in with push and pull-request rights on the target repository. Cloud workers also need Claude Code on the web and the Claude GitHub App on the repository.

## Installation

### 1. Add the marketplace and install

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

Skip `myspec-factory` if you only want to work on specs and tasks in a single session.

### 2. Restart Claude Code

Plugins load at startup.

### 3. Sign in to MySpec

From a terminal, or inside Claude Code with the `!` prefix:

```bash
npx -y @myspec/mcp-server login
```

Add `--org <slug>` to pick an organization, or `--paste` on a remote machine without a browser. For CI, containers, or shared machines, create an API token in the MySpec webapp (avatar menu, API tokens) and export it in the shell that starts `claude`:

```bash
export MYSPEC_API_TOKEN=msp_pat_...
```

No restart is needed after signing in. Never put a token in `.mcp.json` or any file in a repository.

### 4. Check it works

- `/mcp` shows `myspec` as connected.
- `/plugin` lists the plugins you installed as enabled.
- Ask Claude: "set up MySpec and check I'm signed in."

### 5. Set up the factory (myspec-factory only)

1. In the repository you want to manage, run `/myspec-factory:setup` and approve the settings it proposes.
2. Turn on the manager persona for that repository only. Use `/config` → Output style → **Software Factory Manager**, or add this to the repository's `.claude/settings.local.json`:

   ```json
   { "outputStyle": "myspec-factory:Software Factory Manager" }
   ```

   The style is not turned on by default. Sessions that should write code themselves keep the default style.
3. Start the manager with Remote Control, so it can see and message its cloud workers:

   ```bash
   claude --remote-control "factory <bundle>"
   ```

   Or run `/remote-control` inside a running session.
4. Ask: "Run the factory for project X, bundle Y."

### Install for a whole team

Commit this to the repository's `.claude/settings.json`. Team members are offered the marketplace and `myspec-mcp` when they open the repository. This is the same block `/myspec-factory:setup` proposes:

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

Install `myspec-factory` only on the machine that runs the manager, not in shared settings, so worker sessions do not load the manager skills.

Also add `.specs/` to the repository's `.gitignore`; that folder holds spec files downloaded from MySpec and local progress notes.

### Update or remove

```text
/plugin marketplace update myspec
/plugin update myspec-mcp@myspec
/plugin update myspec-factory@myspec
```

Restart Claude Code after updating. To remove a plugin: `/plugin uninstall <plugin>@myspec`.

## Troubleshooting

| Problem | Fix |
|---|---|
| `/plugin install` says the plugin is not found | Add the marketplace first (`/plugin marketplace add myspecs/claude-plugins`) and use the `@myspec` suffix. Check with `/plugin marketplace list`. |
| Skills or the output style do not appear after install | Restart Claude Code. Check that the plugin is enabled in `/plugin`. |
| `myspec` shows as failed in `/mcp` | Check `node -v` is 22 or newer. Run `npx -y @myspec/mcp-server --version` once to fill the npx cache, then restart. |
| MySpec tools return `Not authenticated` or "run login" | Run `npx -y @myspec/mcp-server login`. |
| `missing required claims (sub, org)` | Sign in with an organization: `npx -y @myspec/mcp-server login --org <slug>`. |
| HTTP 401 with `MYSPEC_API_TOKEN` | The token is expired, disabled, or from another organization or environment. Create a new one, and make sure it is exported in the shell that starts `claude`. |
| Two sets of MySpec tools | A project `.mcp.json` also declares `myspec`. Remove that entry and keep the plugin. |
| A tool mentioned in a skill is missing | Your cached server is old. Compare `npx -y @myspec/mcp-server --version` with `npm view @myspec/mcp-server version`. If it is older, run `npx -y @myspec/mcp-server@latest --version`, then restart. |
| `/plugin update` does nothing | Run `/plugin marketplace update myspec` first, then update the plugin and restart. |
| **Software Factory Manager** is not in the output style list | Make sure `myspec-factory` is installed and enabled, then restart. In settings files use the full name `myspec-factory:Software Factory Manager`. |
| The manager cannot see or message cloud workers | Connect Remote Control (`/remote-control`). Without it, the manager steers workers with `claude -p "<message>" --cloud <session_id>`. |
| Local workers and the manager both lose MySpec access (`Refresh token rejected`) | Both shared the same browser sign-in. Give local workers their own `MYSPEC_API_TOKEN` in the repository's gitignored `.claude/settings.local.json`, then reconnect the manager's server in `/mcp`. |

More cases:

- myspec-mcp: [plugins/myspec-mcp/README.md](plugins/myspec-mcp/README.md#troubleshooting) and [skills/setup/references/troubleshooting.md](plugins/myspec-mcp/skills/setup/references/troubleshooting.md)
- myspec-factory: [plugins/myspec-factory/README.md](plugins/myspec-factory/README.md#troubleshooting)

Or ask Claude to "troubleshoot my MySpec setup"; the `setup` skill walks through the checks.

## Contributing

Plugin structure, versioning, validation, and conventions for changing these plugins are in [CLAUDE.md](CLAUDE.md).

## License

MIT. See [LICENSE](LICENSE).
