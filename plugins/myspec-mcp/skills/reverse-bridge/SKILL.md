---
name: reverse-bridge
description: Share a local repository with a MySpec brownfield spec session by running the MySpec reverse MCP bridge. Use when the user says "share my local code with MySpec", "let MySpec read this repo", "myspec reverse", "mount my workspace for MySpec", or when a MySpec webapp session reports reverse_mcp_unavailable or cannot read local files. Requires a signed-in MySpec CLI (see the setup skill).
---

# MySpec reverse bridge

When a user drafts a brownfield spec in the MySpec webapp, the cloud AI agent needs to read their existing codebase. The `reverse` command flips the usual MCP direction: the CLI dials out to the ai-agent over WebSocket and becomes an MCP server exposing read-only tools scoped to one local directory. Nothing inbound reaches the laptop.

This is a long-running process, separate from the `myspec` server that this plugin registers. It does not affect Claude Code's own MySpec tools.

## Exposed tools (read-only, confined to `--root`)

`local_fs_list_dir`, `local_fs_read_file` (5 MiB per file, 2000 lines per call), `local_fs_grep` (ripgrep with a Node fallback), `local_pack_codebase` (repomix XML pack, paginated), `local_pack_codebase_read_page`. Absolute paths and `..` are rejected; ignore rules apply.

## Prerequisites

1. Signed in with an active organization: run the `setup` skill's sign-in check first. `reverse` exits with `Your CLI session has no active organization` otherwise; fix with `login --org <slug>` (user runs it).
2. Same account: the browser session driving the brownfield chat must be signed in as the same MySpec account as the CLI. Routing is keyed by user id.
3. One live bridge per account: a newer connection evicts the older one (WebSocket close code 4002).

## Start the bridge

State the absolute directory you intend to expose and get an explicit yes from the user before anything starts; the cloud agent will be able to read every file under it. Then give the user the command for a separate terminal, or run it yourself in the background:

```bash
npx -y @myspec/mcp-server reverse --root /absolute/path/to/repo
```

Expected output:

```
myspec-mcp reverse: discovered agent URL via https://app.myspec.dev/api/v1/config
myspec-mcp reverse: granting read access to /absolute/path/to/repo
Press Ctrl-C to stop. Auto-reconnect enabled.
myspec-mcp reverse: connected; awaiting tool calls.
```

If you start it from Claude Code (only after the user confirmed the root), use Bash with `run_in_background: true`, then confirm the `connected` line in its output before telling the user to continue in the webapp. Stop it with Ctrl-C (or the background task's stop action) when the session is done.

## Readiness check

The first tool call right after start-up can race and return `reverse_mcp_unavailable`. Poll until connected (needs `jq` and `curl`):

```bash
ACCESS_TOKEN="$(jq -r '.accessToken' ~/.myspec/oauth_creds.json)"
AGENT_URL="$(jq -r '.aiAgentMcpReverseUrl' ~/.myspec/settings.json | sed -E 's#^ws://#http://#; s#^wss://#https://#; s#/mcp/reverse$##')"
curl -sS -H "Authorization: Bearer $ACCESS_TOKEN" "$AGENT_URL/api/me/reverse-mcp/status"
# {"connected":true,"rootLabel":"repo","connectedSince":"..."}
```

## Overrides

| Flag or variable | Purpose |
|---|---|
| `--root <dir>` | Directory to expose (default: current directory). Nothing outside it is reachable |
| `--agent-url <url>` or `MYSPEC_AI_AGENT_WS_URL` | Skip discovery, for example `ws://localhost:3001/mcp/reverse` against a local ai-agent |
| `--access-token <jwt>` or `MYSPEC_ACCESS_TOKEN` | Static token for testing (`reverse` only); no refresh; overrides `MYSPEC_API_TOKEN` with a warning |

The agent URL is normally discovered from the webapp's authenticated config endpoint and cached in `~/.myspec/settings.json`. If discovery fails, the cached URL is used; if none exists, the command exits with a config error instead of guessing.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Your CLI session has no active organization` or a 401 loop on connect | Org-less session | User runs `login --org <slug>` |
| `WebSocket upgrade rejected: HTTP 401` | Expired or wrong-environment credentials | Re-login against the environment the webapp session uses |
| Webapp session still cannot read files while the bridge says connected | Browser account differs from the CLI account | Sign in to the browser as the same account |
| Bridge disconnects with close code 4002 | Another `reverse` for the same account started elsewhere | Stop the other one, or accept that the newest wins |
| `reverse_mcp_unavailable` right after start | Registration not finished | Poll the readiness check, then retry in the webapp |
| Headless machine, no browser for login | Interactive login impossible | Use an API token for `serve`. For `reverse` the same-account rule needs a real session: run `login --paste` and open the printed URL on any machine with a browser. Do not copy `~/.myspec/` between machines; refresh tokens are single-use and go stale |
