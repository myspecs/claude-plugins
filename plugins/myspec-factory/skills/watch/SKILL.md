---
name: watch
description: Open the MySpec project event feed for a factory run and react to it. Use when the user says "watch the project", "listen for events", "open the event stream", "start the factory feed", "create a stream token for the factory", or when the Software Factory Manager begins a run or a wave and needs to know, without polling, when tasks.md or other spec files change, when a worker uploads its report, when a spec session completes, or when a project is deleted. Mints a stream token, feeds its URL straight into Claude Code's Monitor tool, and maps each event to a manager action.
---

# Factory watch

The MySpec platform streams a project's events over a presigned WebSocket URL. The manager mints one with `mcp__plugin_myspec-mcp_myspec__create_stream_token`, hands the URL to Claude Code's `Monitor` tool, and then acts on each event instead of polling. Event vocabulary and reactions: `references/event-handling.md`.

Requires `@myspec/mcp-server` 0.4.0 or newer (today the `next` prerelease) and a platform with `REALTIME_STREAM_ENABLED`. When `create_stream_token` is not in the tool list, use the polling fallback at the end of this skill.

## Security rule (read first)

The returned URL is the credential. Anyone holding it can read every event on the project until it expires, without authenticating, and it cannot be retrieved again.

- Pass it directly from the tool result into `Monitor`. Never write it to the session registry, the run log, `CLAUDE.md`, a commit, an issue, a pull request, an attachment, or a chat reply, and never repeat it in a summary. Refer to the token by its `id` and `token_prefix` only.
- Ask for the shortest `ttl_seconds` that covers the work (a wave or a working session, not the 24-hour default).
- Revoke with `revoke_stream_token(id)` as soon as the run ends, at every milestone gate, and immediately if the URL may have been exposed.

## 1. Mint

```
create_stream_token(
  resource_type: "project",
  resource_id: "<project_id>",
  event_types: ["spec_file.created", "spec_file.updated", "spec_file.deleted",
                "attachment.created", "spec_session.updated", "project.updated", "project.deleted"],
  ttl_seconds: <seconds for this run, for example 14400>,
  label: "factory <bundle> <YYYY-MM-DD>"
)
```

Add `spec_file.lock` only when the user wants it; it fires on every lock renewal while someone edits in the webapp and is the likeliest way to trip the Monitor's firehose suppression. Pass `["*"]` only when the user wants everything. The result carries `id`, `token_prefix`, `expires_at`, and `url`. Record them as `token_id`, `token_prefix`, `expires_at`, plus `last_seq: null`, under `stream` in `.specs/<bundle>/factory-sessions.json` (see the dispatch skill's `session-registry.md`). Do not record `url`.

Before minting, `list_spec_file` for the project and cache `file_id` to `file_path` under `files` in the registry (not secret): `spec_file.created` and `spec_file.lock` frames carry no path, so this map is how a frame is tied to a bundle. Refresh it on every `spec_file.created`.

## 2. Open the feed

```
Monitor({
  ws: { url: "<url from the mint result>", protocols: ["v1"] },
  description: "myspec factory events for <bundle> (token <token_prefix>)",
  persistent: true
})
```

Omit `?after=` on the first open so the feed starts from now. The first frame is `stream.ready`; check that its `resource.id` is the project and its `event_types` list is what you asked for, then note `last_seq`. Open the feed before deriving the board (or re-derive the board right after `stream.ready`), otherwise a write that lands between your read and the socket opening is lost.

Open a second, bash-based Monitor for pull-request state, because cloud workers do not emit platform events unless they upload their report:

```bash
d=$(mktemp -d)
snap() {
  gh pr list --state all --limit 200 --search "in:title task" \
    --json number,title,state,isDraft,statusCheckRollup,headRefName \
    --jq '.[] | "\(.number)|\(.state)|\(.isDraft)|\(.title)|\(.headRefName)|\([.statusCheckRollup[]? | (.conclusion // .state // .status)] | join(","))"' | sort
}
snap > "$d/prev"          # seed, so the first pass emits nothing
while true; do
  sleep 90
  snap > "$d/cur" || continue
  comm -13 "$d/prev" "$d/cur"
  mv "$d/cur" "$d/prev"
done
```

Description: `factory pull requests for <bundle>`. `persistent: true`. Files rather than process substitution, because the Monitor's shell may be `/bin/sh`.

## 3. React

Each frame arrives as a notification. Keep `last_seq` from every event frame in the registry. Map the frame to an action with `references/event-handling.md`; the short version:

| Frame | Action |
|---|---|
| `spec_file.updated` (revision shape) on the bundle's `tasks.md` by someone else | `get_spec_file` for the new `content_version`, re-read, refresh the board; if a manager write was pending, redo it on the fresh body |
| `spec_file.created` or `spec_file.updated` on requirements, solution, constitution, proposal, or a delta | Spec changed mid-run: pause dispatching tasks that cite affected requirement ids, run `myspec-mcp:analyze` (consistency), report to the user |
| `spec_file.updated` lifecycle shape (`data.state`): `trashed` on a bundle file | Stop dispatch, report; `restored`: re-read the file |
| `spec_file.lock` (when subscribed) with state acquired on a bundle file | Someone is editing; delay manager writes to that file until released or taken over |
| Any `spec_file.*` whose path is outside the bundle's directory | Ignore; mention in the next report |
| `attachment.created` whose name matches `factory-<bundle>-task-<N>-report.md` or `factory-<bundle>-lane-<L>-report.md` | A worker finished and uploaded its report: run `integrate` for task N, or for every task of lane L |
| `spec_session.updated` with a completed status | A spec session finished; a new or revised bundle may exist. Offer to plan it |
| `project.deleted` | Stop every worker you can (`SendMessage` or `claude -p "stop" --cloud <id>`); the token is already revoked, so set `stream.revoked_at`, stop the pull-request monitor, do not mint, report |
| `stream.expiring`, or `expires_at` less than five minutes away | Rotate: mint a replacement with the same scope, open a new Monitor on it (no `?after=`; buffers are per token), wait for its `stream.ready`, then stop the old one. Drop any frame you have already processed. Update the registry |
| `stream.error` then close `4001` | Token unknown, revoked, or expired: if the run continues, mint a replacement and resync (`get_spec_file` on every bundle file, `list_attachments` for reports) because the gap is unrecoverable. `reason` resource deleted: do not mint; see `project.deleted` |
| close `4009` | Too many sockets on this token: wait, do not discard the token |
| close `1013` or `4008` | Feed unavailable or the consumer fell behind: back off and reconnect to the same URL with `?after=<last_seq>` (omit `?after=` when `last_seq` is null). Frames from the outage arrive on reconnect; if the reconnect fails past the token's expiry, resync as for `4001` |
| Monitor stopped itself (too many events) | Reconnect to the same URL with `?after=<last_seq>`; if `spec_file.lock` was in the scope, mint a narrower token |

Session status: with Remote Control connected, `ListAgents` shows each cloud worker as busy or idle; an idle worker whose branch has not appeared is a candidate for a nudge through `SendMessage`.

Pull-request monitor lines: a line with `OPEN` and green checks for a task not yet integrated triggers `integrate`; a line with `MERGED` that the manager did not merge itself means a human merged it; verify and mark `[x]`.

## Keeping the feed alive

A `Monitor` window lasts at most 60 minutes (max `timeout_ms=3600000`) and a token last 24 hours (default); neither renews itself. Re-arm on every expiry notice, and before asking the user a question that may wait a long time, check the token's `expires_at` and rotate first — a token that lapses while you wait leaves an unrecoverable gap. When a gap happens anyway, rotate and resync (`get_spec_file` on every bundle file) before relying on the board. Update `last_seq` from every event frame, and resume with `?after=<last_seq>` after any reconnect.

A feed can also die with no notice reaching you: a `1006` drop the Monitor does not surface, a session restart (which stops every Monitor), or context compaction. Silence then looks exactly like a quiet project, and the URL cannot be retrieved again to reconnect. Check that the feed is alive:
- After each of your own spec writes, expect its `spec_file.updated` frame within a minute. No frame means the feed is dead.
- At every loop step (before integrating, dispatching, or asking the user), call `list_stream_tokens(resource_id: "<project_id>", mine_only: true, live_only: true)`. If the token's `last_connected_at` is older than your current Monitor's start, nothing is connected.
- After any "background tasks didn't finish before the previous session ended" notice, treat every feed and pull-request Monitor as stopped.

A dead feed whose URL you no longer hold cannot be resumed. Mint a replacement with the same scope, open a Monitor on it, and wait for `stream.ready`. Then resync (`get_spec_file` on every bundle file, `list_attachments` for reports), revoke the old token, and update the registry. When the remaining work needs no spec events (for example a last pull request watched through `gh`), revoke instead and say so.

## 4. Close

At the end of the run or at a milestone gate: `revoke_stream_token(token_id)`, stop both monitors (TaskStop), and set `stream.revoked_at` in the registry.

## Polling fallback (no stream tokens)

Skip the mint. Run the pull-request Monitor above (it needs only `gh`). MCP tools cannot be called from a bash Monitor, so spec changes are detected from the manager loop itself: before every integrate and dispatch step, call `get_spec_file` on `tasks.md` and the other bundle files and compare `content_version` with the registry's last-known values; a change triggers the same reactions as the corresponding `spec_file.updated` frame. Worker reports are found with `list_attachments` (0.4.0+) or the pull-request monitor. Everything else in the manager loop stays the same.
