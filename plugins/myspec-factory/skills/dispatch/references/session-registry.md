# Session registry

Every worker session the manager starts is recorded in a local registry so the manager can find the session id again to steer, check, or teleport it. The registry is a cache of dispatch facts, never the board: task status still comes from `tasks.md` checkboxes and pull requests.

## Location

`.specs/<bundle>/factory-sessions.json` in the repository root (`.specs/` is gitignored). Create the directory if missing. One file per bundle.

## Format

```json
{
  "project_id": "<uuid>",
  "bundle": "<bundle>",
  "sessions": [
    {
      "task": 4,
      "title": "Checkout API",
      "path": "cloud-cli",
      "session_id": "session_01DiUkqY2kzbUbDmW1w96rfi",
      "agent_name": "factory checkout task 4: Checkout API",
      "url": "https://claude.ai/code/session_01DiUkqY2kzbUbDmW1w96rfi",
      "branch": "factory/<bundle>/task-4",
      "started_at": "2026-09-12T13:05:00Z",
      "status": "running",
      "pr": null,
      "autofix": "unknown",
      "notes": ""
    }
  ]
}
```

- `path`: `cloud-agent` (Agent tool, remote), `cloud-cli` (`claude --cloud`), `worktree-agent`, or `worktree-cli` (`claude --bg`).
- `agent_name`: the name the session shows in `ListAgents` while the manager is connected to Remote Control (the brief's first line); `SendMessage` uses it. `null` until seen.
- `session_id`: the cloud session id (`session_...` or `cse_...`), the background agent id, or the `claude --bg` id. Store the bare id; the `View:` line's query string (`?from=cli&m=0`) is dropped when saving the URL.
- `status`: `running`, `pushed` (branch seen, no pull request yet), `pr-open`, `blocked`, `merged`, `failed`, `redispatched`.
- `autofix`: `on` once the worker (or the manager) enabled Auto-fix for the pull request, `unavailable` with the reason in `notes`, `unknown` before a pull request exists.
- Append a new entry on redispatch rather than overwriting; set the old entry's status to `redispatched`.

## Stream token (never the URL)

The watch skill records the feed it opened under a top-level `stream` key. The URL is never stored anywhere; only the id needed to revoke and the cursor needed to resume.

```json
"stream": {
  "token_id": "<id from create_stream_token>",
  "token_prefix": "pR9x1a2b",
  "expires_at": "2026-09-12T17:05:00Z",
  "last_seq": 42,
  "revoked_at": null
}
```

## File map (for the event feed)

`spec_file.created` and `spec_file.lock` frames carry only `file_id`. The watch skill keeps a map so frames can be tied to a bundle file:

```json
"files": {
  "<file_id>": "specs/<bundle>/tasks.md"
}
```

Filled from `list_spec_file` at watch start, refreshed on every `spec_file.created`.

## Capturing the id

A new `claude --cloud` session prints its title and URL but not a `Session ID:` line:

```
Created cloud session: <rewritten title>
View: https://claude.ai/code/session_01KtmAVhNWdS6WFWFhguY46R?from=cli&m=0
Resume with: claude --teleport session_01KtmAVhNWdS6WFWFhguY46R
```

Take the id from the `View:` or `Resume with:` line, and `agent_name` from the `Created cloud session:` line (confirm it with `ListAgents`). The output is a terminal capture, so strip escapes first: `sed 's/\x1b\[[0-9;?]*[a-zA-Z]//g' <file> | tr '\r' '\n'`.

`claude -p "..." --cloud <id>` prints lines shaped like:

```
Sent to cloud session.
Session ID: session_01DiUkqY2kzbUbDmW1w96rfi
View: https://claude.ai/code/session_01DiUkqY2kzbUbDmW1w96rfi?from=cli&m=0
```

Parse them from the command output (background Bash output file or captured stdout):

```bash
SESSION_ID=$(grep -oE 'Session ID: *[A-Za-z0-9_]+' <output> | head -1 | awk '{print $3}')
SESSION_URL=$(grep -oE 'https://claude\.ai/code/[A-Za-z0-9_]+' <output> | head -1)
```

When `--output-format json` is accepted, read `session_id` and `url` from the JSON instead. If neither yields an id, set `session_id` to `null`, keep `status: "running"`, and ask the user to paste the session URL from claude.ai/code; update the entry when they do.

Write the registry immediately after each successful dispatch, before starting the next session. Update it with a small script rather than rewriting by hand, for example:

```bash
python3 - "$REG" <<'PY'
import json, sys, datetime
p = sys.argv[1]; d = json.load(open(p))
d["sessions"].append({"task": 4, "title": "Checkout API", "path": "cloud-cli",
  "session_id": "session_01DiUkqY2kzbUbDmW1w96rfi",
  "url": "https://claude.ai/code/session_01DiUkqY2kzbUbDmW1w96rfi",
  "branch": "factory/<bundle>/task-4",
  "started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
  "status": "running", "pr": None, "notes": ""})
json.dump(d, open(p, "w"), indent=2)
PY
```

## Using the registry

- Steer: look up the task's entry; with Remote Control connected, `SendMessage` to `agent_name` (confirm it in `ListAgents` first); otherwise `claude -p "<message>" --cloud <session_id>`. Record what was sent and how in `notes`.
- Check: open `url`, or `/tasks` in an interactive session; `claude --teleport <session_id>` to pull the branch locally.
- Integrate: match pull requests to entries by `branch` or task number; set `pr` and `status`.
- Resume after a manager restart: read the registry first; entries with `status: "running"` are sessions to check before dispatching anything new.
- Unattended shifts have no local disk that persists between runs; they put the same entries into their report comment on the tracking issue and read the previous comment at the start of the next shift.
