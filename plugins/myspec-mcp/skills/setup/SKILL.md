---
name: setup
description: Set up, sign in to, verify, or troubleshoot the MySpec MCP server (@myspec/mcp-server) in Claude Code. Use when the user says "set up MySpec", "connect to MySpec", "myspec login", "myspec not connected", "use a MySpec API token", "MYSPEC_API_TOKEN", "switch MySpec organization", or when any mcp__plugin_myspec-mcp_myspec__* tool call fails with "Not authenticated", "run login", "missing required claims (sub, org)", or an HTTP 401/404 from MySpec.
user-invocable: true
---

# MySpec MCP setup

The `myspec-mcp` plugin registers the `myspec` MCP server as `npx -y @myspec/mcp-server` (stdio). Its tools appear as `mcp__plugin_myspec-mcp_myspec__<tool>`. The server starts fine before sign-in; every tool call errors with a login hint until the user signs in, and works immediately after (no restart needed). The plugin works against the production MySpec platform only (`https://auth.myspec.dev`, `https://app.myspec.dev`).

Follow the steps in order. Stop at the first step that fails and give the user the fix.

## 1. Prerequisites (run these yourself)

```bash
node -v                                   # must be v22 or newer
npx -y @myspec/mcp-server --version       # warms the npx cache; must be 0.3.0 or newer
```

- Node below 22: tell the user to install Node 22+ (nvm, brew, or nodejs.org) and stop.
- Version below 0.3.0: the npx cache is stale. Run `npx -y @myspec/mcp-server@latest --version`, then ask the user to restart Claude Code.
- Version 0.3.x exposes 17 tools (projects, spec files, `get_attachment`, `upload_attachment`). Spec sessions, artifacts, attachment listing and reading, stream tokens, and paginated reads need 0.4.0, which is currently only the `next` prerelease. Tell the user when a request needs one of those.
- Confirm the server is registered: the tool list should contain `mcp__plugin_myspec-mcp_myspec__list_projects`. If not, the plugin is not installed or enabled. Tell the user to run `/plugin install myspec-mcp@myspec`, then restart Claude Code.
- Never run `claude mcp add myspec ...`. That registers a second copy of the server next to the plugin's own.

## 2. Sign-in check

Call `mcp__plugin_myspec-mcp_myspec__list_projects` with `limit: 1`.

- A project list (even empty) means the user is signed in. Report the result and stop.
- An error containing `Not authenticated. Set MYSPEC_API_TOKEN ... or run npx @myspec/mcp-server login` means go to step 3. On 0.3.0 it is wrapped as `list_projects failed: Could not discover endpoints from https://app.myspec.dev/api/v1/config (Not authenticated. ...)`; the parenthetical is the real cause.
- Any other error: see `references/troubleshooting.md`.

## 3. Sign in (the user runs this, not you)

`login` opens a browser and blocks on a loopback callback, and it prompts for an organization when the user belongs to several. It cannot complete inside a foreground Bash call. Hand the command to the user to run in their own terminal, or with the `!` prefix in the Claude Code prompt:

```bash
npx -y @myspec/mcp-server login                 # browser on this machine
npx -y @myspec/mcp-server login --org <slug>    # also pin the active organization
npx -y @myspec/mcp-server login --paste         # remote box or container: no auto-open
```

Notes for `--paste`: the page shows a token shaped like `<code>.<state>`. The user must copy the whole value including the dot, and paste it within 60 seconds of finishing sign-in.

After the user confirms, repeat step 2. No Claude Code restart is needed.

## 4. Unattended use: API token

For CI, containers, or any session without a browser, use a long-lived API token instead of `login`.

1. In the MySpec webapp: avatar menu, then API tokens, then Create token. Choose the organization, read-only or read-write, and an expiry. The token is shown once.
2. Export it in the shell that launches Claude Code. The plugin's MCP server inherits that environment:

   ```bash
   export MYSPEC_API_TOKEN=msp_pat_...
   claude
   ```

   Never put the token in `.mcp.json`, `plugin.json`, or any file in a repository.
3. Verify the token works before blaming the server. Run this only when the variable is already exported in the shell; never ask the user to paste the token into the chat:

   ```bash
   curl -sS -X POST "https://auth.myspec.dev/api/auth/token/exchange" \
     -H "x-api-key: $MYSPEC_API_TOKEN" -w '\n%{http_code}\n'
   ```

   200 with an `accessToken` is good. 401 is an unknown, revoked, or expired token. 403 means the token's organization is gone or the owner left it.

Precedence is `MYSPEC_API_TOKEN`, then `apiToken` in `~/.myspec/oauth_creds.json`, then the refresh token saved by `login`. The winner is used exclusively. A rejected token fails the call rather than falling back to another identity.

## 5. Sign out

```bash
npx -y @myspec/mcp-server logout
```

This revokes the refresh token and deletes `~/.myspec/oauth_creds.json`, including any file-based `apiToken`. `settings.json` and an exported `MYSPEC_API_TOKEN` are left untouched.

## Local state

| Path | Contents |
|---|---|
| `~/.myspec/settings.json` | Non-secret: `userAuthUrl` plus discovered webapp, platform, and ai-agent URLs |
| `~/.myspec/oauth_creds.json` | Secret, mode 0600: access token, refresh token, expiry, user identity, optional `apiToken` |
| `~/.myspec/project/<project>/file/<file>/rev/<n>/<name>` | Read cache used by `read_spec_file` (root overridable with `MYSPEC_DOWNLOAD_ROOT`) |

## Troubleshooting

See `references/troubleshooting.md` for a symptom-to-fix table.
