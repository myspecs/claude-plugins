# MySpec MCP tools

All tools are exposed by the plugin's `myspec` server and called as `mcp__plugin_myspec-mcp_myspec__<name>`. Ids are UUIDs. Paginated tools return `total` and, while more rows remain, `next_offset`. Line-paginated readers (0.4.0+) take a 1-based `offset` and a `limit` (default and cap 2000 lines, 1 MiB per response) and return `content`, `start_line`, `end_line`, `read_lines`, `total_lines`, `truncated`, `next_offset`.

## Availability by server version

The plugin runs the `latest` npm release. Check the tool list before relying on a tool.

| Server version | Tools |
|---|---|
| 0.3.0 (`latest` today, 17 tools) | Projects (all 7), spec files (all 8), `get_attachment`, `upload_attachment` |
| 0.4.0 (currently the `next` prerelease, 34 tools) | Everything above plus `list_attachments`, `read_attachment`, spec sessions (6), artifacts (6), stream tokens (3), and `offset`/`limit` pagination on `read_spec_file` and `list_spec_file` |

In 0.3.0, `read_spec_file` takes only `file_id` and `revision`, returns the whole file, and refuses files over 1 MiB; `list_spec_file` takes only `project_id`, `path`, `trashed`. Take `content_version` from `get_spec_file`, which returns it in both versions.

## Projects

| Tool | Inputs | Returns and notes |
|---|---|---|
| `list_projects` | `query?`, `limit?` (default 20, max 100), `offset?` | Projects the signed-in user can access |
| `get_project` | `project_id` | Project plus active spec sessions, spec files (id and metadata), attachments (id and metadata) |
| `create_project` | `name`, `description?` | New project id and metadata |
| `update_project` | `project_id`, `name?`, `description?`, `project_type?` (`greenfield`, `brownfield`, `auto`) | Updated metadata; at least one field required |
| `archive_project` | `project_id` | Sets status `archived`; idempotent |
| `unarchive_project` | `project_id` | Sets status `active`; idempotent |
| `delete_project` | `project_id` | Soft-delete; refuses unless already archived. Never archive on the user's behalf to make a delete succeed |

## Spec files

| Tool | Inputs | Returns and notes |
|---|---|---|
| `list_spec_file` | `project_id`, `path?`, `trashed?`, `limit?` (default 50, max 200; 0.4.0+), `offset?` (0.4.0+) | `file_id`, `file_path`, `file_type`, `file_size_bytes`, `revision_count`, `session_id`, `updated_at` (plus `trashed_at` in the Trash Bin). `path` filters to an exact file or everything under a directory. Ordered by path when `path` or `trashed` is set, newest first otherwise |
| `get_spec_file` | `file_id`, `include_download_url?` | Metadata including `content_version`. `include_download_url=N` adds a signed URL for revision N (N greater than `revision_count` errors) |
| `read_spec_file` | `file_id`, `revision?`, `offset?` (0.4.0+), `limit?` (0.4.0+) | UTF-8 content, line-paginated from 0.4.0 (whole file, 1 MiB cap, in 0.3.0), plus `content_version` for the latest revision (0.4.0+; use `get_spec_file` on 0.3.0). Cached on disk under `~/.myspec`. Refuses binary files and files over 8 MiB (0.4.0) |
| `download_spec_file` | `file_id`, `destination_path?`, `revision?`, `overwrite?` | Writes raw bytes (binary ok, up to 50 MiB) and returns metadata only: `saved_path`, `bytes_written`, `revision_number`, `destination_source` (`default`, `redirected`, `explicit`). Default target mirrors the remote path under `.specs/` in the server's working directory; a relative `destination_path` rooted at `specs/` is redirected to `.specs/`; absolute paths are honoured as given. Refuses to replace an existing file unless `overwrite: true` |
| `upload_spec_file` | `project_id`, `file_path`, `content` or `local_file_path` (exactly one), `file_type?` | Creates a new session-less spec file. `file_path` must be rooted at `specs/` or `openspec/` with at most 3 directory levels below the root. `file_type` in `constitution`, `requirements`, `solution`, `tasks`, `proposal`, `openspec-spec`; derived from the basename when omitted (unknown basenames become `openspec-spec`). Rejects an existing path |
| `update_spec_file` | `file_id` or (`project_id` + `file_path`), `content` or `local_file_path` (exactly one), `expected_version?` | Saves a new revision and returns the file summary with the new `content_version`. Pass `expected_version` from the read you based the body on; a concurrent edit is reported as an actionable conflict instead of being overwritten |
| `move_spec_file_to_trash` | `file_id` | Recoverable; hidden from listings and AI tools |
| `restore_spec_file_from_trash` | `file_id` | Reverses the trash move |

## Attachments

| Tool | Inputs | Returns and notes |
|---|---|---|
| `list_attachments` (0.4.0+) | `project_id`, `limit?` (default 50, max 200), `offset?` | `id`, `name`, `mime_type`, `file_size_bytes`, `checksum`, `created_at` |
| `get_attachment` | `attachment_id`, `include_download_url?` | Metadata; any positive `include_download_url` adds a signed `download_url` and `expires_at` |
| `read_attachment` (0.4.0+) | `attachment_id`, `offset?`, `limit?` | Text: line-paginated. Images (png, jpeg, gif, webp): returned whole as an MCP image block, up to 10 MiB. PDF, DOCX, XLSX: refused; use the webapp or `get_attachment` with a download URL |
| `upload_attachment` | `project_id`, `file_path` (absolute, read on the MCP server host), `file_name?`, `mime_type?`, `override?` | Max 10 MB. Returns `attachment_id`, effective `file_name`, `has_file_name_conflict`, `mime_type`, `file_size_bytes`, `checksum` (`sha256:<hex>`), `file_uri`, `reused_existing_attachment` (same name and checksum already present; nothing re-uploaded). `override: true` soft-deletes same-named attachments first and returns `overridden_attachment_ids` |

## Spec sessions (0.4.0+)

Sessions are the AI conversations that generated a bundle. Tools expose metadata and the curated context, never the chat transcript.

| Tool | Inputs | Returns and notes |
|---|---|---|
| `list_spec_sessions` | `project_id`, `archive_filter?` (`active` default, `archived`, `all`), `status?`, `query?`, `limit?` (default 10, max 20), `offset?` | Metadata plus `session_summary` and `context_size_bytes` |
| `get_spec_session` | `session_id`, `include_context?` | Status, counters, timestamps, `archived_at`, `session_summary`, `context_size_bytes`, `context_keys`. `include_context: true` returns the context under a 1 MiB ceiling |
| `rename_spec_session` | `session_id`, `session_summary` (max 500 chars) | Sets the session title via read-merge-write; works on archived sessions |
| `archive_spec_session` | `session_id` | Idempotent; required before delete |
| `unarchive_spec_session` | `session_id` | Returns the session to the active list |
| `delete_spec_session` | `session_id` | Soft-delete; refuses unless archived. Never archive on the user's behalf |

## Artifacts (0.4.0+)

Artifacts are multi-file bundles (for example an HTML mockup) versioned as one snapshot. `revision_count` is the head number and the `expected_version` to pass when writing; rollback appends a revision, so it only grows.

| Tool | Inputs | Returns and notes |
|---|---|---|
| `list_artifacts` | `project_id`, `limit?`, `offset?` | Id, slug, entry path, `revision_count` per artifact |
| `get_artifact` | `artifact_id`, `revision?` | Metadata plus file manifest (path, content type, size, checksum) |
| `read_artifact_file` | `artifact_id`, `path`, `revision?`, `offset?`, `limit?` | Line-paginated UTF-8 content; binary files refused |
| `create_artifact` | `project_id`, `name`, `files[]` (`path`, `content`, `encoding?` utf8 or base64, `content_type?`), `slug?`, `description?`, `entry_path?`, `message?` | Revision 1. Limits: 50 files, 2 MiB per file, 10 MiB per revision. A taken slug conflicts |
| `write_artifact_revision` | `artifact_id`, `files[]`, `base_revision?` (patch mode), `remove[]?`, `expected_version?`, `message?`, `entry_path?` | Full mode replaces the bundle; patch mode sends only changed files plus paths to remove. Always pass `expected_version` from `get_artifact`; the server defaults to the current head when it is omitted, which is an unguarded write. A stale value is reported as a conflict naming the new head |
| `rollback_artifact` | `artifact_id`, `revision_number`, `expected_version?`, `message?` | Appends a revision equal to the target (git revert semantics). Only the newest 50 revisions are kept |

## Stream tokens (0.4.0+)

| Tool | Inputs | Returns and notes |
|---|---|---|
| `create_stream_token` | `resource_type`, `resource_id`, `event_types`, `ttl_seconds?` (default 24 h, max 7 days), `label?` | A short-lived `wss://` URL that streams a project's events (subprotocol `v1`, one JSON event per frame with a `seq` cursor; reconnect with `?after=<seq>`). The URL is the credential: pass it straight to a WebSocket client (for example Claude Code's Monitor tool), never write, log, or repeat it. Shown once |
| `list_stream_tokens` | `resource_id?`, `live_only?`, `mine_only?`, `limit?`, `offset?` | Tokens in the organisation with scope, expiry, liveness; secrets never returned |
| `revoke_stream_token` | `id` | Immediately closes the URL (a `stream.error` frame with reason `revoked`, then close code `4001`) and purges buffered events. Revoking someone else's token needs the organisation owner or admin role |

Feed protocol: the first frame is `stream.ready` (restates scope and `last_seq`); event frames are `{"v":1,"seq":N,"type":"spec_file.updated","at":"...","resource":{"type":"project","id":"..."},"data":{...}}`; `stream.expiring` arrives about a minute before expiry; `stream.error` precedes a refusal. Close codes: `4001` bad or revoked token, `4008` slow consumer, `4009` too many sockets for the token, `1013` feed unavailable (retry). Reconnect with `?after=<seq>` (`?after=0` replays the buffer). Event types: `project.updated|deleted`, `spec_file.created|updated|deleted|lock`, `attachment.created|deleted`, `spec_session.created|updated|deleted`, or `*`. Typical use: `Monitor({ ws: { url: <url>, protocols: ["v1"] }, description: "myspec project events" })`.

## Errors

- `<tool> failed: Could not discover endpoints from https://app.myspec.dev/api/v1/config (Not authenticated. Set MYSPEC_API_TOKEN to a MySpec API token, or run npx @myspec/mcp-server login to sign in.)` The user must sign in; see the `setup` skill. The same wrapper without the `Not authenticated` part is a real connectivity or discovery failure.
- `... was NOT updated: ... changed it ... since you read it.` A version conflict; see `write-back-protocol.md`.
- `file_path must be rooted at 'specs' or 'openspec' ...` Path rule violation on `upload_spec_file`.
