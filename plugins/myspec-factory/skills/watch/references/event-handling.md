# Project event feed: protocol and handling

Source: the MySpec platform API reference (`projects/platform/docs/API.md`, Stream Token Endpoints) and the `create_stream_token` tool in `@myspec/mcp-server` 0.4.0+.

## Protocol

- Endpoint: `wss://<platform host>/realtime/v1/stream/<token>`, returned whole as `url` by `create_stream_token`. The token is a path segment, not a query parameter, and is the only credential.
- Subprotocol `v1`. Frames are single-line JSON text, never binary. Claude Code's `Monitor` turns each text frame into one notification.
- Resume cursor: every event frame carries `seq`. Reconnect with `?after=<seq>` to receive everything after that frame; `?after=0` replays the whole buffer; no `after` means "from now on". A malformed value is treated as omitted.
- Retention: events are kept for the token's remaining lifetime, then expire with it. Revoking purges them at once.
- Liveness: the server pings; a socket that misses two pongs is closed.
- Limits: mint rate 30 per minute per user; a per-token connection cap (close `4009` when exceeded); TTL clamped to 60 seconds up to 7 days, default 24 hours.

## Frame shapes

```json
{"v":1,"type":"stream.ready","token_id":"…","resource":{"type":"project","id":"…"},"event_types":["…"],"expires_at":"…","last_seq":41}
{"v":1,"seq":42,"type":"spec_file.updated","at":"2026-09-10T12:00:00Z","resource":{"type":"project","id":"…"},"data":{ …the platform's own event payload… }}
{"v":1,"type":"stream.expiring","…"}
{"v":1,"type":"stream.error","reason":"revoked"}
```

Control frames are namespaced `stream.*` and never collide with event types: `stream.ready` (first frame, restates the scope), `stream.expiring` (about a minute before expiry; mint a replacement), `stream.error` (a refusal in words, before the close code).

## Close codes

| Code | Meaning | Manager action |
|---|---|---|
| `4001` | Credential unknown, revoked, expired, or its project deleted (`stream.error.reason` says which) | Stop, or mint a replacement if the run continues |
| `4008` | Slow consumer; the server dropped the socket because frames were not being read | Reconnect with `?after=<last_seq>` |
| `4009` | Too many concurrent sockets for this token | Wait for a slot; keep the token |
| `1013` | Feed not available right now (stream tokens not started, journal unreachable) | Back off and retry the same URL |
| `1006` | Abnormal close with no reason; idle sockets have been observed to drop every 15-25 minutes | Reconnect at once with `?after=<last_seq>`; frames from the gap replay. Frequent drops are a platform issue worth reporting, not a token problem |

## Event types (resource `project`)

`data` is the platform's own event payload, forwarded byte for byte (snake_case). Keys pinned by the platform's payload schema tests:

| Type | Fires on | `data` keys |
|---|---|---|
| `project.updated` | name, description, type, status, archive, unarchive | `project_id, org, owner_id, name, description, project_type, status, archived, changed[], updated_at` |
| `project.deleted` | soft delete; also revokes the token, so this is the last frame | `project_id, org, owner_id, name, deleted_at` |
| `spec_file.created` | a new spec file | `file_id, project_id, session_id, file_type, org, created_at` |
| `spec_file.updated` | new revision or rollback | `file_id, file_path, file_type, project_id, session_id, org, revision_number, previous_revision, content_version, checksum, file_size_bytes, changed_by, changed_by_kind, source, updated_at` |
| `spec_file.updated` | moved to trash or restored | lifecycle shape: `file_id, file_path, file_type, project_id, session_id, org, state (trashed or restored), changed_at` |
| `spec_file.deleted` | permanent delete | lifecycle shape with `state: deleted` |
| `spec_file.lock` | acquired, renewed, released, taken over | `file_id, project_id, session_id, org, holder_id, holder_kind (human or ai), holder_name, state, acquired_at, expires_at` |
| `attachment.created` | content upload completed (not the reservation) | `attachment_id, project_id, org, name, mime_type, file_size_bytes, checksum, uploaded_by, created_at` |
| `attachment.deleted` | soft delete | `attachment_id, project_id, org, name, deleted_at` |
| `spec_session.created` | new spec session | `session_id, project_id, org, user_id, status, created_at` |
| `spec_session.updated` | completed, archived, unarchived, status moves, rename | `session_id, project_id, org, user_id, status, archived, changed[], updated_at` (plus `completed_at` or `archived_at` on those transitions) |
| `spec_session.deleted` | soft delete | `session_id, project_id, org, deleted_at` |

`changed[]` names the fields that moved (`name`, `description`, `status`, `project_type`, `metadata`, `archived`, `summary`, `context`). Session `message_count`, `token_count`, and chat history never emit. `spec_file.updated` and `spec_file.deleted` carry `file_path`; `spec_file.created` and `spec_file.lock` carry only `file_id`, so keep a `file_id` to `file_path` map (from `list_spec_file`, refreshed on `spec_file.created`) in the registry. A frame belongs to the bundle when its path sits under the bundle's directory (`specs/<bundle>/` or `openspec/changes/<id>/`); frames for other bundles in the same project are ignored and mentioned in the next report. `content_version` on a revision frame recognises the echo of your own write.

Platform limits worth knowing: 20 live tokens per user, 10 per project, 3 concurrent sockets per token, 5000 buffered frames per token, mint rate 30 per minute.

## Manager reactions in detail

### The bundle's `tasks.md` changed (`spec_file.updated`)

0. Branch on shape first. A lifecycle frame (`data.state` present, no `content_version`): `trashed` on a bundle file means stop dispatching and report; `restored` means re-read the file. A revision frame continues below.
1. Ignore the event if it is the echo of the manager's own write (`data.content_version` or `data.revision_number` matches what the last `update_spec_file` returned).
2. Otherwise `get_spec_file` for the new `content_version` and `read_spec_file` for the body.
3. Diff against the last known body: newly checked tasks (a human or another agent finished something), new tasks (convergence milestone added by an analysis, or a spec edit), reworded acceptance criteria.
4. Refresh the board; if a task now marked `[x]` has a worker running, steer that worker to stop and report; if a dispatched task's text changed, steer the worker with the new text or redispatch.
5. If the manager had a pending write, redo it on the fresh body with the new token.

### Requirements, solution, constitution, proposal, or a delta changed

Spec changes mid-run are a human review event, not a manager decision. Pause new dispatches for tasks whose `_Requirements:_` cite affected ids (or every task when the constitution changed), run `myspec-mcp:analyze` in spec-consistency mode, and report what changed and which in-flight workers may be building against stale text. Resume only when the user says so.

### `spec_file.lock`

`data.state` is `acquired` or `renewed` on a bundle file (`data.holder_kind` says human or ai, `data.holder_name` who): another editor is active; defer manager writes to that file and retry after `released` or a takeover. Locks are advisory; the `content_version` check still protects the write.

### `attachment.created`

Workers with MySpec access upload their Factory report as `factory-<bundle>-task-<N>-report.md` when they finish (the bundle is in the name because task numbers repeat across bundles and `override` would otherwise replace another bundle's report) (the brief asks for `upload_attachment` with `override: true`). On a matching `data.name`, read it with `read_attachment` (0.4.0+) or `get_attachment` with a download URL, then run `integrate` for task N. Other attachments are informational; mention them in the next report.

### `spec_session.updated`

A completed session means the bundle may have gained or changed documents. Re-list the bundle (`list_spec_file`) and offer to plan. Archive or rename events need no action.

### `project.updated` and `project.deleted`

Archived project: stop dispatching, report. Deleted project: the feed ends; stop workers that can be reached and report.

### Rotation

Rotate from the registry's `expires_at` about five minutes before expiry; `stream.expiring` (one minute before) is the backstop, which can arrive while the manager is busy integrating. Mint a replacement with the same scope and a fresh TTL, open a new Monitor on the new URL without `?after=` (each token has its own buffer, so the old cursor does not replay on the new one), wait for its `stream.ready`, then stop the old Monitor at once. Sequence numbers are allocated across all live tokens on the project, so while two tokens overlap the same event arrives on both with different `seq`, and a single feed shows gaps for numbers taken by the other token until it expires: drop any frame already handled (same `type`, `at`, and resource id) and do not treat those gaps as lost events. Update `stream` in the registry (new `token_id`, `token_prefix`, `expires_at`; reset `last_seq`). If the old token expired before the new feed was ready, or the socket closed `4001`, resync: `get_spec_file` on every bundle file and `list_attachments` for reports. Never mention either URL.
