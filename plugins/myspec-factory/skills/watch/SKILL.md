---
name: watch
description: Open the MySpec project event feed for a factory run and react to it. Use when the user says "watch the project", "listen for events", "open the event stream", "start the factory feed", "create a stream token for the factory", or when the Software Factory Manager begins a run or a milestone and needs to know, without polling, when tasks.md or other spec files change, when a spec session completes, or when a project is deleted. Mints a stream token, feeds its URL straight into Claude Code's Monitor tool, and maps each event to a manager action.
user-invocable: false
---

# Factory watch

The MySpec platform streams a project's events over a presigned WebSocket URL. The manager mints one with `mcp__plugin_myspec-mcp_myspec__create_stream_token`, hands the URL to Claude Code's `Monitor` tool, and then acts on each event instead of polling. Event vocabulary and reactions: `references/event-handling.md`.

Requires `@myspec/mcp-server` 0.4.0 or newer (today the `next` prerelease) and a platform with `REALTIME_STREAM_ENABLED`. When `create_stream_token` is not in the tool list, use the polling fallback at the end of this skill.

## Security rule (read first)

The returned URL is the credential. Anyone holding it can read every event on the project until it expires, without authenticating, and it cannot be retrieved again.

- Pass it directly from the tool result into `Monitor`. Never write it to the session registry, the run log, `CLAUDE.md`, a commit, an issue, a pull request, an attachment, or a chat reply, and never repeat it in a summary. Refer to the token by its `id` and `token_prefix` only.
- Ask for the shortest `ttl_seconds` that covers the work (a working session of the team, not the 24-hour default).
- Revoke with `revoke_stream_token(id)` as soon as the run ends, at every milestone gate, and immediately if the URL may have been exposed.

## 1. Mint

```
create_stream_token(
  resource_type: "project",
  resource_id: "<project_id>",
  event_types: ["spec_file.created", "spec_file.updated", "spec_file.deleted",
                "spec_session.updated", "project.updated", "project.deleted"],
  ttl_seconds: 28800,   # 8 hours while agents run; see "Keeping the feed alive"
  label: "factory <bundle> <YYYY-MM-DD>"
)
```

Add `spec_file.lock` only when the user wants it; it fires on every lock renewal while someone edits in the webapp and is the likeliest way to trip the Monitor's firehose suppression. Pass `["*"]` only when the user wants everything. The result carries `id`, `token_prefix`, `expires_at`, and `url`. Record them as `token_id`, `token_prefix`, `expires_at`, plus `last_seq: null`, under `stream` in `.specs/<bundle>/factory-sessions.json` with the dispatch skill's `registry.py … stream --token-id --prefix --expires-at` (and `stream-seq N` for `last_seq`; see its `session-registry.md`). Do not record `url`; the script refuses it.

Before minting, `list_spec_file` for the project and cache `file_id` to `file_path` under `files` in the registry (not secret): `spec_file.created` and `spec_file.lock` frames carry no path, so this map is how a frame is tied to a bundle. Refresh it on every `spec_file.created`.

## 2. Open the feed

```
Monitor({
  ws: { url: "<url from the mint result>", protocols: ["v1"] },
  description: "myspec factory events for <bundle> (token <token_prefix>)",
  timeout_ms: 3600000
})
```

Omit `?after=` on the first open so the feed starts from now. The first frame is `stream.ready`; check that its `resource.id` is the project and its `event_types` list is what you asked for, then note `last_seq`. Open the feed before deriving the task board (or re-derive it right after `stream.ready`), otherwise a write that lands between your read and the socket opening is lost.

Watch pull requests with the tested scripts in this skill's `scripts/` directory (this skill's base directory + `/scripts/`), because agents report through their pull requests (the `## Factory report` in the description or a pull request comment) and the repository's factory board, never through platform events. Never hand-write the loop: inline versions have failed on shell word splitting, on `echo "$json" | jq` in zsh, and on GitHub's lowercase status values.

| Script | Watches | Exits |
|---|---|---|
| `team-watch.sh <clone> [--reviewer <login>] [--rerequest] [--tick <minutes>] "<label>\|<title prefix>\|<assigned_at>" …` | **The default: every open assignment in one `Monitor`.** Runs one `pr-watch.sh` per assignment and tags each line `[<label>]` (`[Ada a1-3]`); with `--tick 10` (only when the run has a board) it also prints `board-tick` every 10 minutes. One Monitor for the team means one expiry notice per 30-minute window instead of one per pull request plus one for the tick. Restart it (TaskStop, then a new Monitor with the current list) when an assignment is added; an assignment whose pull request merges or closes drops out by itself. It keeps each assignment's last printed state under `<clone>/.git/factory-team-watch/`, so a restart prints only real changes; pass `--fresh` after a session restart or compaction to get every assignment's current state once | when every pull request is merged or closed (`team-watch-done`, exit 0) |
| `pr-watch.sh <clone> "<title prefix>" --since <assigned_at> [--reviewer <login>] [--rerequest]` | one assignment's branch, its pull request, failing and pending checks, review decision. Before the pull request exists, branches are the `claude/*` and `factory/*` ones whose tip is newer than `--since` (other sessions' branches included), so a re-armed watch still shows the agent's branch; once it exists, only its head branch. The PR is the one whose title starts with the prefix ("task 3" never matches "task 30") created after `--since` (the assignment's `assigned_at`), so an older PR with the same title is ignored. `--reviewer` adds `approved_head=yes\|no\|none` to the PR line: whether that reviewer's latest approval is on the current head. `--rerequest` (opt-in) re-requests that reviewer when the head moves and no request is pending, and prints `re-requested review from <login> on <sha>`. Pass `--reviewer <policy.reviewer> --rerequest` for agent pull requests | when the pull request is merged or closed (exit 0) |
| `postmerge-watch.sh <clone> <merge-sha> [base] [interval]` | the `push` and `workflow_run` runs on the default branch for one merge commit; Dependabot (`dynamic`), scheduled and tag-push runs on the same commit are ignored | when the same finished set is seen twice: 0 all green, 1 any failure, 3 after 60 polls (also a merge that triggers no workflow) |
| `board-tick.sh [minutes] [ticks]` | nothing: it prints `board-tick <n>/<ticks>` every 10 minutes by default. Use it only when an agent is working but no `team-watch.sh` runs (for example an agent whose assignment has no pull request title yet); `team-watch.sh --tick` replaces it otherwise | after the last tick (default 3, 30 minutes at 10 minutes, the longest Monitor window) |

The scripts print only changes the manager acts on, so every line costs a turn of the manager's whole context; never replace them with a chattier loop. `pr-watch.sh` stays silent while the pending-check count only moves between non-zero values and while a branch only gains commits before its pull request exists; it prints when the first branch appears, the pull request opens, a check fails, every check finished (`pending=0`), the head moves, the review or draft state changes, and at merge or close. `postmerge-watch.sh` prints when the runs first appear, when one fails, and the final result; run it with Bash `run_in_background` (integrate §4b), not a Monitor. Both print `github-unreachable (…)` when a GitHub call fails: that means the state is **unknown**, not empty. Never report "no branch", "no PR" or "no runs" from it — check directly with `git ls-remote`, `gh pr view` or `gh run list` first.

## 3. React

Each frame arrives as a notification. Keep `last_seq` from every event frame in the registry (`registry.py … stream-seq N`). Map the frame to an action with `references/event-handling.md`; the short version:

| Frame | Action |
|---|---|
| `spec_file.updated` (revision shape) on the bundle's `tasks.md` by someone else | `get_spec_file` for the new `content_version`, re-read, refresh the task board; if a manager write was pending, redo it on the fresh body |
| `spec_file.created` or `spec_file.updated` on requirements, solution, constitution, proposal, or a delta | Spec changed mid-run: pause new assignments for tasks that cite affected requirement ids, run `myspec-mcp:analyze` (consistency), report to the user |
| `spec_file.updated` lifecycle shape (`data.state`): `trashed` on a bundle file | Stop new assignments, report; `restored`: re-read the file |
| `spec_file.lock` (when subscribed) with state acquired on a bundle file | Someone is editing; delay manager writes to that file until released or taken over |
| Any `spec_file.*` whose path is outside the bundle's directory | Ignore; mention in the next report |
| `spec_session.updated` with a completed status | A spec session finished; a new or revised bundle may exist. Offer to plan it |
| `project.deleted` | Stop every agent you can (`claude -p "stop" --cloud <id>` for cloud agents, `SendMessage` for local ones); the token is already revoked, so set `stream.revoked_at`, stop the pull-request monitor, do not mint, report |
| `stream.expiring`, or `expires_at` less than five minutes away | Rotate: mint a replacement with the same scope, open a new Monitor on it (no `?after=`; buffers are per token), wait for its `stream.ready`, then stop the old one. Drop any frame you have already processed. Update the registry |
| `stream.error` then close `4001` | Token unknown, revoked, or expired: if the run continues, mint a replacement and resync (`get_spec_file` on every bundle file; Factory reports are on the pull requests, which the pull-request monitor covers) because the gap is unrecoverable. `reason` resource deleted: do not mint; see `project.deleted` |
| close `4009` | Too many sockets on this token: wait, do not discard the token |
| close `1013` or `4008` | Feed unavailable or the consumer fell behind: back off and reconnect to the same URL with `?after=<last_seq>` (omit `?after=` when `last_seq` is null). Frames from the outage arrive on reconnect; if the reconnect fails past the token's expiry, resync as for `4001` |
| Monitor stopped itself (too many events) | Reconnect to the same URL with `?after=<last_seq>`; if `spec_file.lock` was in the scope, mint a narrower token |

Session status: with Remote Control connected, `ListAgents` shows each cloud agent as busy or idle; an idle agent whose current assignment's branch has not appeared is a candidate for a nudge through the doorbell channel (`board` skill §5: `claude -p … --cloud` for cloud workers).

Factory board: read it (the `board` skill §5) on every `board-tick` line, on a `team-watch.sh` expiry notice (it doubles as a tick; skip the read when the last one was under 10 minutes ago), before every integrate or assignment step, and when a board comment wakes the session — not on every pull-request or feed line, where a read almost always finds nothing. A comment wake-up arrives only for a comment the owner sent to Claude, and only while the board watch is on; answer it as the `board` skill §6 says. When no agent is working and no board question waits for the owner, the tick stops at once (restart `team-watch.sh` without `--tick`, or stop `board-tick.sh`), and the watch stays on until that Monitor's window would have ended, then stops at the next wake and is not re-armed until work resumes (the output style's polling rule). A read that finds nothing new is not reported.

A line that needs no action — the pull request is still waiting on checks or a review, a re-requested review, a feed frame outside the bundle — gets no tool call and no message: end the turn. Act only on the transitions below.

Pull-request script lines (`team-watch.sh` prefixes each with `[<label>]`): a new branch means the agent pushed (it may keep pushing; do not treat it as finished); a pull request with `pending=0`, empty `failing=[]` and `approved_head=yes` triggers `integrate`; `review=APPROVED` alone is not the gate, because GitHub keeps it after new pushes; a new `head=` after an approval means the review must be requested again (a `re-requested review from …` line says the script already did); `done: PR #<n> MERGED` that the manager did not merge itself means a human merged it — verify and mark `[x]`. A `github-unreachable` line triggers a direct check, never a report.

## When to keep the feed open

The feed costs a re-arm every 30 minutes and a token rotation every 8 hours, for frames that rarely come once agents are building. Keep it open while the spec is likely to change under you: planning, the spec gate, a MySpec spec session that is running, and the user saying they are editing the bundle. At a milestone gate it is revoked (§4) and reopened with a fresh token only when the next milestone's spec work needs it. While the team only builds against a finished spec, close it (§4) and use the polling fallback below: the `content_version` check before every integrate, assignment or spec-write step catches the same changes at the only moments they matter. Reopen it with a fresh token when one of those phases starts again.

## Keeping the feed alive

A `Monitor` window lasts at most 30 minutes in practice (pass `timeout_ms: 3600000`; the harness caps it) and a token lasts its `ttl_seconds`; neither renews itself.

Quiet upkeep — none of these is a message to the user:
- **Expiry notice:** re-arm the same watch at once, with no other tool call unless the expiry is also the board tick. Reopen the feed with `?after=<last_seq>` (or `?after=0` while `last_seq` is null) so nothing is lost.
- **Close `1006`, or a socket that ends with no reason:** reconnect the same URL with `?after=<last_seq>` right away. Idle sockets drop every 15-25 minutes; it is not a token problem.
- **`stream.ready` after a reconnect that missed nothing:** record `last_seq` and carry on.

Token lifetime:
- Mint for the working session in front of you: 8 hours (`ttl_seconds: 28800`) while agents run, not the 24-hour default.
- Rotate when `expires_at` is less than one Monitor window (30 minutes) away, at the next re-arm, not at the last minute: mint, open the new feed, wait for its `stream.ready`, then revoke the old token.
- Revoke the token and stop every Monitor when nothing is in flight — a milestone gate reached, the run finished, or the factory idle waiting on the user with no agent working. Re-arming watches over an idle factory only costs turns. Mint a fresh token when work resumes.

Before asking the user a question that may wait a long time while agents are still working, check the token's `expires_at` and rotate first — a token that lapses while you wait leaves an unrecoverable gap. When a gap happens anyway, rotate and resync (`get_spec_file` on every bundle file) before relying on the task board. Update `last_seq` from every event frame, and resume with `?after=<last_seq>` after any reconnect.

A feed can also die with no notice reaching you: a `1006` drop the Monitor does not surface, a session restart (which stops every Monitor), or context compaction. Silence then looks exactly like a quiet project, and the URL cannot be retrieved again to reconnect. Check that the feed is alive:
- While the feed is open, after each of your own spec writes, expect its `spec_file.updated` frame within a minute. No frame means the feed is dead.
- While the feed is open, at every loop step (before integrating, sending an assignment, or asking the user), call `list_stream_tokens(resource_id: "<project_id>", mine_only: true, live_only: true)`. If the token's `last_connected_at` is older than your current Monitor's start, nothing is connected.
- After any "background tasks didn't finish before the previous session ended" notice, treat every feed and pull-request Monitor and every background post-merge watch as stopped.

A dead feed whose URL you no longer hold cannot be resumed. Mint a replacement with the same scope, open a Monitor on it, and wait for `stream.ready`. Then resync (`get_spec_file` on every bundle file), revoke the old token, and update the registry. When the remaining work needs no spec events (for example a last pull request watched through `gh`), revoke instead and say so.

## 4. Close

At the end of the run or at a milestone gate: `revoke_stream_token(token_id)`, stop every Monitor of the run (TaskStop), and set `stream.revoked_at` in the registry (`registry.py … stream --revoked-at`).

## Polling fallback (no stream tokens)

Skip the mint. Run the pull-request scripts above (they need only `gh` and `git`). MCP tools cannot be called from a bash Monitor, so spec changes are detected from the manager loop itself: before every integrate and assignment step, call `get_spec_file` on `tasks.md` and the other bundle files and compare `content_version` with the registry's last-known values; a change triggers the same reactions as the corresponding `spec_file.updated` frame. Agent reports are on the pull requests (the description, or a comment starting `## Factory report`), which the pull-request monitor finds, and on the factory board, which the `team-watch.sh` tick prompts you to read. Everything else in the manager loop stays the same.
