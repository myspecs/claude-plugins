# MySpec MCP troubleshooting

Diagnose by the exact error text. Commands marked "user runs" are interactive and must be given to the user, not run in a foreground Bash call.

| Symptom | Cause | Fix |
|---|---|---|
| `<tool> failed: Could not discover endpoints from .../api/v1/config (Not authenticated. Set MYSPEC_API_TOKEN ... or run npx @myspec/mcp-server login ...)` or a bare `Not authenticated ...` | No credentials, expired access token whose refresh failed, or `settings.json` missing while `oauth_creds.json` exists | User runs `npx -y @myspec/mcp-server login` (or exports `MYSPEC_API_TOKEN`) |
| `Could not discover endpoints from .../api/v1/config` without `Not authenticated` inside the parentheses | The webapp config endpoint is unreachable: no network, wrong `userAuthUrl` host, or the environment is down | Check connectivity to the host named in the message and `userAuthUrl` in `~/.myspec/settings.json`; retry |
| `missing required claims (sub, org)` or `MISSING_ORG_CLAIM` or `Your CLI session has no active organization` | The user belongs to two or more organizations and the session has no active one pinned | User runs `npx -y @myspec/mcp-server login --org <slug>` |
| `HTTP 401` that names a host (for example `dev-auth.myspec.dev`) with an API token | Token and environment do not match: dev token against prod, or prod token on a machine whose `settings.json` still points at dev | Set `MYSPEC_USER_AUTH_URL` to the environment the token was created on, or re-login against the right one |
| `HTTP 404: file not found` for a project or file that exists in the webapp | Signed in to the wrong environment (prod is the default; dev projects live on dev) | Check `userAuthUrl` in `~/.myspec/settings.json`; user runs `login --user-auth-url https://dev-auth.myspec.dev` (or the prod URL) |
| `OAuth code exchange failed: HTTP 401` during `login --paste` | The pasted code expired (60 seconds after sign-in completes) | Redo the login and paste immediately |
| `Pasted token is missing a state suffix` | The user copied the bare `?code=` value from the URL | Copy the whole `<code>.<state>` value from the box on the page, including the dot |
| Tools ignore `MYSPEC_API_TOKEN` and still ask for login | Cached server older than 0.3.0 | Run `npx -y @myspec/mcp-server@latest --version`, then restart Claude Code |
| `/mcp` shows `myspec` as failed or disconnected on first use | The first `npx` run downloads the package and exceeded the MCP start-up timeout, or Node is older than 22 | Run `npx -y @myspec/mcp-server --version` once, check `node -v`, restart Claude Code |
| Error about `oauth_creds.json` being readable by group or other | The credentials file must be mode 0600 | `chmod 600 ~/.myspec/oauth_creds.json` |
| Both `mcp__myspec__*` and `mcp__plugin_myspec-mcp_myspec__*` tools exist | The project's own `.mcp.json` (or a user-scope `claude mcp add`) also declares a `myspec` server | Remove one: delete the entry from the project `.mcp.json`, or `claude mcp remove myspec`, or disable the plugin |
| Skill or reference edits in this plugin do not show up | Claude Code caches plugins per version | Bump `version` in `plugin.json`, then `/plugin marketplace update myspec` and `/plugin update myspec-mcp@myspec` |
| `reverse_mcp_unavailable` in a MySpec brownfield session | No live reverse bridge for this account | See the `reverse-bridge` skill |

## Confirming the active organization

Decode the saved access token; a missing `org` key confirms the org-less session problem:

```bash
node -e "console.log(JSON.parse(Buffer.from(JSON.parse(require('fs').readFileSync(process.env.HOME+'/.myspec/oauth_creds.json','utf8')).accessToken.split('.')[1],'base64url').toString()))"
```

## URL resolution order

`--user-auth-url` flag, then `MYSPEC_USER_AUTH_URL`, then `userAuthUrl` in `~/.myspec/settings.json`, then the default `https://auth.myspec.dev`. The webapp URL is derived from the auth host (`auth.` becomes `app.`, `dev-auth.` becomes `dev-app.`). Platform and ai-agent URLs are discovered from the webapp after login and cached in `settings.json`.

## Environment variables

| Variable | Purpose |
|---|---|
| `MYSPEC_API_TOKEN` | Long-lived API token (`msp_pat_...`). Beats everything on disk, never written to disk. Needs 0.3.0+. |
| `MYSPEC_USER_AUTH_URL` | Auth server base URL when not using the default production environment |
| `MYSPEC_DOWNLOAD_ROOT` | Cache root for `read_spec_file` (default `~/.myspec`) |
| `MYSPEC_AI_AGENT_WS_URL` | ai-agent WebSocket URL for `reverse`; skips discovery |
| `MYSPEC_ACCESS_TOKEN` | Static access token for `reverse` only (no refresh); rejected by `serve` |
