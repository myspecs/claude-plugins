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
      "task": "4,5,7",
      "title": "Checkout API",
      "path": "cloud-cli",
      "session_id": "session_01DiUkqY2kzbUbDmW1w96rfi",
      "agent_name": "factory checkout tasks 4, 5, 7: Checkout API",
      "url": "https://claude.ai/code/session_01DiUkqY2kzbUbDmW1w96rfi",
      "branch": "factory/<bundle>/tasks-4-5-7",
      "started_at": "2026-09-12T13:05:00Z",
      "status": "running",
      "pr": null,
      "autofix": "unknown",
      "notes": ""
    }
  ]
}
```

- `task`: the group's task numbers as one string (`"4,5,7"`, what `add-session --task "4,5,7"` stores), or a number for a single-task worker (branch `factory/<bundle>/task-<N>`).
- Lane workers (manager-planned `tasks.md` with a `## Branch Plan`): add `"lane": <L>` and `"tasks": [<N1>, <N2>, …]`, set `task` to the first task of the lane, and expect branch `factory/<bundle>/lane-<L>`.
- `path`: `cloud-agent` (Agent tool, remote), `cloud-cli` (`claude --cloud`), `worktree-agent`, or `worktree-cli` (`claude --bg`).
- `agent_name`: the name the session shows in `ListAgents` while the manager is connected to Remote Control (the brief's first line); `SendMessage` uses it. `null` until seen.
- `session_id`: the cloud session id (`session_...` or `cse_...`), the background agent id, or the `claude --bg` id. Store the bare id; the `View:` line's query string (`?from=cli&m=0`) is dropped when saving the URL.
- `status`: `running`, `pushed` (branch seen, no pull request yet), `pr-open`, `blocked`, `merged`, `failed`, `redispatched`.
- `autofix`: `on` once the worker (or the manager) enabled Auto-fix for the pull request, `unavailable` with the reason in `notes`, `unknown` before a pull request exists.
- Append a new entry on redispatch rather than overwriting; set the old entry's status to `redispatched`.

## Run policy and contract notes

The run-start answers live under a top-level `policy` key; `dispatch` and `integrate` read them instead of asking again. `contract_notes` collects what merged work provides for later briefs.

```json
"policy": {
  "concurrency": 3,
  "merge_method": "squash",
  "autonomy": "merge-on-gate",
  "cloud_dispatch": "allowed",
  "reviewer": "0xgosu-bot",
  "required_checks": ["Lint", "Test & Coverage"],
  "minor_defaults": "owner"
},
"contract_notes": {
  "<short key>": "<exact fact: wire shape, service name, SDK export, migration name, fake-client option>"
}
```

- `autonomy`: `ask-each` (ask before every merge and dispatch), `merge-on-gate` (merge on the ready-to-merge gate without asking; ask before dispatch), `full` (also dispatch dependent waves, lanes and planned PR splits inside the current milestone without asking; a new milestone always waits for the milestone gate's question). Update it when the user changes the level mid-run. At `full`, the milestone gate may also dispatch convergence follow-ups without asking when every one of them is test-only (`integrate` §6).
- `reviewer`: the bare GitHub login whose approval gates the merge (it is passed to `pr-watch.sh --reviewer`). Keep any explanation elsewhere, for example in `contract_notes`.
- `minor_defaults`: `owner` (default: every doubt and worker deviation goes to the owner) or `manager`. With `manager`, the manager decides doubts and deviations that are low-impact UX or implementation details — wording and labels, ordering and tie-break rules, counting conventions, test-only choices — and change no API or wire shape, data model, security or authorization, requirement scope, or user-visible flow. It records each as a numbered Clarification marked `(manager default, owner may reverse)`, relays it to the worker, and lists them in the next report and in the milestone summary. Anything else still goes to the owner.
- Each session entry also carries `verified_sha`: the head the manager's last verification pass covered. `integrate`'s ready-to-merge gate compares it with the pull request's head.

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

Write the registry immediately after each successful dispatch, before starting the next session.

## Writing the registry

Every write goes through `<plugin root>/skills/dispatch/scripts/registry.py`, never an ad-hoc JSON edit. `registry.py …` elsewhere in the skills stands for:

```
python3 <plugin root>/skills/dispatch/scripts/registry.py --file .specs/<bundle>/factory-sessions.json <subcommand>
```

| Subcommand | Does |
|---|---|
| `show` | Print the registry |
| `add-session --task --title --path --session-id --url --branch --started-at [--notes]` | Append a session entry with `status: running` |
| `set --session <index, last, task list or task> key=value…` | Update `status`, `pr`, `branch`, `autofix`, `verified_sha`, `agent_name` or `cloud_title` |
| `note --session <index, last, task list or task> "text"` | Append to the entry's `notes` |
| `stream --token-id --prefix --expires-at [--revoked-at]` | Record the stream token (never the URL) |
| `stream-seq N` | Record `stream.last_seq` |
| `policy key=value…` | Set run policy keys |
| `contract <key> "text"` | Add or replace a `contract_notes` entry |
| `log --run-log <path> "text"` | Append one line to the run log |

`--session` takes an index from `show`, `last`, a group's task list (`"4,5,7"`), or one task number, which finds the newest entry carrying that task (a group's list or a lane's `tasks`); a bare number is read as an index only when no entry carries it. It refuses any value that contains a stream URL.

## Using the registry

- Steer: look up the entry whose `task` list holds the task; with Remote Control connected, `SendMessage` to `agent_name` (confirm it in `ListAgents` first); otherwise `claude -p "<message>" --cloud <session_id>`. Record what was sent and how in `notes`.
- Check: open `url`, or `/tasks` in an interactive session; `claude --teleport <session_id>` to pull the branch locally.
- Integrate: match pull requests to entries by `branch` or by the task numbers in the title (`task 4, 5, 7:`); set `pr` and `status`.
- Resume after a manager restart: read the registry first; entries with `status: "running"` are sessions to check before dispatching anything new.
- Unattended shifts have no local disk that persists between runs; they put the same entries into their report comment on the tracking issue and read the previous comment at the start of the next shift.
