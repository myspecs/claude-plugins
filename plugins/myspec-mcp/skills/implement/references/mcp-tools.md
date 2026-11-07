# MySpec MCP tools

All tools are exposed by the plugin's `myspec` server and called as `mcp__plugin_myspec-mcp_myspec__<name>`. The plugin runs the `latest` npm release of `@myspec/mcp-server` (1.1.2, 45 tools); check the tool list before relying on a tool, since an older cached server lacks some. Ids are UUIDs. Paginated tools return `total` and, while more rows remain, `next_offset`. Line-paginated readers take a 1-based `offset` (0 means 1) and a `limit` (default and cap 2000 lines, 1 MiB per response) and return `content`, `start_line`, `end_line`, `read_lines`, `total_lines`, `truncated`, `next_offset`.

Every write is recorded as an AI change. Access follows the project role (read, write, admin): `get_project` returns your `viewer_role`, and a tool the role does not allow fails with `permission denied — this action needs the <role> role on the project`.

| Server version | Added |
|---|---|
| 0.4.0 | `list_attachments`, `read_attachment`, spec sessions, artifacts, stream tokens, pagination |
| 0.5.0 | `start_spec_session`, spec file comments, the `quality` file type |
| 1.1.1 | Task board tools, project roles (`viewer_role`), `auth status` |
| 1.1.2 | `move_spec_folder` |

## Projects

| Tool | Inputs | Returns and notes |
|---|---|---|
| `list_projects` | `query?`, `limit?` (default 20, max 100), `offset?` | Projects the signed-in user can access, most recently active first |
| `get_project` | `project_id` | Project (with `viewer_role`) plus active spec sessions (up to 100), spec files (up to 200) and attachments; no paging, so use the list tools for large projects |
| `create_project` | `name`, `description?` | New project id and metadata |
| `update_project` | `project_id`, `name?`, `description?`, `project_type?` (`greenfield`, `brownfield`, `auto`) | Updated metadata; at least one field required |
| `archive_project` | `project_id` | Sets status `archived`; idempotent |
| `unarchive_project` | `project_id` | Sets status `active`; idempotent |
| `delete_project` | `project_id` | Soft-delete; refuses unless already archived. Never archive on the user's behalf to make a delete succeed |

## Spec files

| Tool | Inputs | Returns and notes |
|---|---|---|
| `list_spec_file` | `project_id`, `path?`, `trashed?`, `limit?` (default 50, max 200), `offset?` | `file_id`, `file_path`, `file_type`, `file_size_bytes`, `revision_count`, `session_id`, `updated_at` (plus `trashed_at` in the Trash Bin). `path` filters to an exact file or everything under a directory. Ordered by path when `path` or `trashed` is set, newest first otherwise |
| `get_spec_file` | `file_id`, `include_download_url?` | Metadata including `content_version`. `include_download_url=N` adds a signed URL for revision N (N greater than `revision_count` errors) |
| `read_spec_file` | `file_id`, `revision?`, `offset?`, `limit?` | Line-paginated UTF-8 content, plus `content_version` for the latest revision, `revision_number`, `cache_path`, `cache_hit`. Cached on disk under `~/.myspec`. Refuses binary files and files over 8 MiB (use `download_spec_file`) |
| `download_spec_file` | `file_id`, `destination_path?`, `revision?`, `overwrite?` | Writes raw bytes (binary ok, up to 50 MiB) and returns metadata only: `saved_path`, `bytes_written`, `revision_number`, `destination_source` (`default`, `redirected`, `explicit`). Default target mirrors the remote path under `.specs/` in the server's working directory (or under `MYSPEC_DOWNLOAD_ROOT`); a relative `destination_path` rooted at `specs/` is redirected to `.specs/`; absolute paths are honoured as given. Refuses to replace an existing file unless `overwrite: true` |
| `upload_spec_file` | `project_id`, `file_path`, `content` or `local_file_path` (exactly one), `file_type?` | Creates a new session-less spec file. `file_path` must be rooted at `specs/` or `openspec/` with at most 3 directory levels below the root. `file_type` in `constitution`, `requirements`, `solution`, `tasks`, `quality`, `proposal`, `openspec-spec`; derived from the basename when omitted (unknown basenames become `openspec-spec`). Rejects an existing path |
| `update_spec_file` | `file_id` or (`project_id` + `file_path`), `content` or `local_file_path` (exactly one), `expected_version?` | Saves a new revision and returns the file summary with the new `content_version`. Pass `expected_version` from the read you based the body on; a concurrent edit is reported as an actionable conflict instead of being overwritten |
| `move_spec_file_to_trash` | `file_id` | Recoverable; hidden from listings and AI tools |
| `restore_spec_file_from_trash` | `file_id` | Reverses the trash move |
| `move_spec_folder` | `project_id`, `from_path`, `to_path` | Moves or renames a folder under `specs/` (a bundle, or a group folder of bundles) with everything in it. `to_path` is `specs` plus 1-3 lowercase kebab-case segments. File ids, contents and revisions stay; only paths change. Refused for `openspec/` folders, `specs/memory`, a target inside the folder, an existing target (Trash included), a folder inside a bundle, a bundle still generating, and nesting deeper than 3 levels. Returns `moved`, `file_count`, `files[{id, file_path}]` |

## Tasks (the task board)

The platform indexes every checkbox task of a project's live `tasks` files (`[ ]` pending, `[-]` in progress, `[x]` done) with a stable `task_id` and planning fields kept outside the file. Format rules: `tasks-format.md`; how to change a status safely: `write-back-protocol.md` § Task status. Where the board is turned off, every task tool fails with `the task board is turned off in this MySpec environment`; fall back to editing the checkbox with `update_spec_file`.

| Tool | Inputs | Returns and notes |
|---|---|---|
| `list_tasks` | `project_id`, `status?` (`pending`, `in_progress`, `done`), `assignee_user_id?` (an id, `"me"`, `"none"`), `cycle?`, `label?`, `file_id?`, `include_details?`, `limit?` (default 100, max 500), `offset?` | `tasks[]` in file order: `task_id`, `spec_file_id`, `key` (`4`, `1.2`, `T007`; empty when the line has no recognised key), `title` (Markdown as written), `section` (heading path), `parent_task_id`, `status`, `assignee_user_id`, `priority` (0 none, 1 urgent, 2 high, 3 medium, 4 low) and `priority_name`, `story_points`, `cycle`, `start_date`, `end_date`, `labels`, `relationships[{type, task_id}]`; `include_details` adds the sub-bullets (previewed to 500 characters). Also `files[{spec_file_id, file_path, content_version}]` (the version the tasks reflect), the labels and cycles in use, `total_tasks` |
| `set_task_status` | `project_id`, `task_ids` (1-200), `status`, `expected_versions?` (`[{spec_file_id, content_version}]` from `list_tasks`) | Rewrites only the checkbox markers, one revision per file. Partial: per task `updated`, `unchanged`, `removed` or `failed` (`file_changed`, `conflict`, `quota_exceeded`, `not_found`); per file the new `content_version`; the tasks as they are now. An error only when every task failed |
| `update_tasks` | `project_id`, `task_ids` (1-200), `assignee_user_id?` (`"me"`, `null` unassigns), `priority?`, `story_points?`, `cycle?`, `start_date?`, `end_date?` (YYYY-MM-DD), `add_labels?`, `remove_labels?` (a task carries at most 20), `add_relationships?` (`[{type: blocks, blocked_by or related, task_id}]`; a pair has one, the other task sees the inverse), `remove_relationships?` (task ids) | Planning fields only, never status or text. The same change applies to every task; a field left out is unchanged, `null` clears it. All or nothing |
| `list_task_assignees` | `project_id` | `assignees[{user_id, username, display_name}]` (who `update_tasks` accepts), `self_user_id`, `truncated` (at most 1000) |

## Spec file comments

Review threads anchored to a passage of a spec file. An AI can open, reply, and edit or delete its own comments; it cannot resolve, reopen or re-anchor a thread (the platform refuses with 403), so say what changed in a reply and let a person resolve.

| Tool | Inputs | Returns and notes |
|---|---|---|
| `list_spec_file_comments` | `file_id`, `status?` (`open`, `resolved`, `orphaned`) | Up to 100 threads (`total_threads`, `truncated`): `thread_id`, `anchor_quote`, `anchor_status` (`anchored`, `orphaned`), `resolved`, `created_by_kind`, `comments[{comment_id, author_kind, body, deleted, content_version}]` (bodies previewed to 1000 characters, `body_truncated`). Works on trashed files. Read it before editing a file under review |
| `create_spec_file_comment_thread` | `file_id`, `body` (markdown, max 10000), `anchor_quote` (verbatim passage, max 2000), `anchor_prefix?`, `anchor_suffix?` (max 64 each; text just before and after, to tell repeats apart) | Never send offsets; the server finds the quote in the current content, so read the file first. Refused on a trashed file. A conflict `lock_timeout`: retry as is; `content_moved`: re-read and retry |
| `reply_spec_file_comment_thread` | `file_id`, `thread_id`, `body` | Answer a reviewer or report what you changed |
| `update_spec_file_comment` | `file_id`, `comment_id`, `body`, `expected_version?` (the comment's own `content_version`, not the file's) | Own comments only |
| `delete_spec_file_comment` | `file_id`, `comment_id` | Own comments only. A reply disappears (`comment: null`); a first comment with live replies becomes a tombstone; a first comment alone takes the thread (`thread_deleted: true`) |

## Attachments

| Tool | Inputs | Returns and notes |
|---|---|---|
| `list_attachments` | `project_id`, `limit?` (default 50, max 200), `offset?` | `id`, `name`, `mime_type`, `file_size_bytes`, `checksum`, `created_at` |
| `get_attachment` | `attachment_id`, `include_download_url?` | Metadata; any positive `include_download_url` adds a signed `download_url` and `expires_at` |
| `read_attachment` | `attachment_id`, `offset?`, `limit?` | Text: line-paginated. Images (png, jpeg, gif, webp): returned whole as an MCP image block, up to 10 MiB. PDF, DOCX, XLSX: refused; use the webapp or `get_attachment` with a download URL |
| `upload_attachment` | `project_id`, `file_path` (absolute, read on the MCP server host), `file_name?`, `mime_type?`, `override?` | Max 10 MB. Returns `attachment_id`, effective `file_name`, `has_file_name_conflict`, `mime_type`, `file_size_bytes`, `checksum` (`sha256:<hex>`), `file_uri`, `reused_existing_attachment` (same name and checksum already present; nothing re-uploaded). `override: true` soft-deletes same-named attachments first and returns `overridden_attachment_ids` |

## Spec sessions

Sessions are the AI conversations that generate and edit a bundle in the MySpec webapp. Tools expose metadata and the curated context, never the chat transcript.

| Tool | Inputs | Returns and notes |
|---|---|---|
| `list_spec_sessions` | `project_id`, `archive_filter?` (`active` default, `archived`, `all`), `status?` (`generating`, `pending_input`, `completed`), `query?`, `limit?` (default 10, max 20), `offset?` | Metadata plus `session_summary` and `context_size_bytes` |
| `get_spec_session` | `session_id`, `include_context?` | Status, counters, timestamps, `archived_at`, `session_summary`, `context_size_bytes`, `context_keys`. `include_context: true` returns the context under a 1 MiB ceiling |
| `start_spec_session` | `project_id`, `mode` (`generate`, `edit`), `prompt`, `workflow_id?`, `language?` (`en`, `zh`, `ja`, `vi`; fixed once set), `model_id?`, `attachment_ids?`, `spec_file_ids?` (max 25 each; edit sessions need the files they change), `session_title?` (max 500) | Starts ONE real session, runs its first turn (waits up to 75 s; a longer turn keeps running) and returns `session_url`, `session_id`, `assistant_text`, `pending_action` (`mcq_form_pending`, `spec_file_pending_decision`, `review_feedback_pending`, `user_choice_pending`, `site_plan_pending`, `artifact_revision_pending`, `turn_still_running`, `none`), `next_step_instruction`, and `first_turn_error`/`warnings` when something limits it (the session still exists). Bills model tokens: once per intent, and after a timeout or transport error check `list_spec_sessions` before calling again. Relay the URL; never drive the workflow yourself. Workflow ids: generate `myspec-greenfield-v1` (default), `enterprise-greenfield-v1`, `speckit-greenfield-v1`, `myspec-brownfield-v1`, `openspec-brownfield-v1`; edit `myspec-edit-v1` (default), `myspec-edit-brownfield-v1`. A `mode` that contradicts the workflow is rejected. Brownfield: start the reverse bridge first (the `reverse-bridge` skill) |
| `rename_spec_session` | `session_id`, `session_summary` (max 500 chars) | Sets the session title via read-merge-write; works on archived sessions |
| `archive_spec_session` | `session_id` | Idempotent; required before delete |
| `unarchive_spec_session` | `session_id` | Returns the session to the active list |
| `delete_spec_session` | `session_id` | Soft-delete; refuses unless archived. Never archive on the user's behalf |

## Artifacts

Versioned multi-file bundles, such as a clickable HTML prototype, stored as one snapshot per revision. How to work with them: the `artifacts` skill (its `references/artifact-rules.md` holds every limit and error).

| Tool | Inputs | Returns and notes |
|---|---|---|
| `list_artifacts` | `project_id`, `limit?` (default 50, max 100), `offset?` | Live artifacts: `id`, `name`, `slug`, `kind`, `description`, `entry_path`, `revision_count`, `session_id`, `created_by`, timestamps |
| `get_artifact` | `artifact_id`, `revision?` | `{artifact, revision}`; the revision has `source` (`create`, `snapshot`, `rollback`), `message`, `changed_by_kind`, `file_count`, `total_bytes` and `files[{path, content_type, size_bytes, checksum}]`. `revision_count` is the head and the `expected_version` for the next write |
| `read_artifact_file` | `artifact_id`, `path`, `revision?`, `offset?`, `limit?` | Line-paginated UTF-8 content with `content_type` and `checksum`. Binary files (a NUL byte), invalid UTF-8 and files over 8 MiB are refused |
| `create_artifact` | `project_id`, `name`, `files[]` (`path`, `content`, `encoding?` `utf8` or `base64`, `content_type?`), `slug?`, `description?`, `entry_path?`, `message?` | Revision 1; returns `{artifact, revision, no_change}` |
| `write_artifact_revision` | `artifact_id`, `files[]`, `base_revision?` (patch mode), `remove[]?` (patch mode only), `expected_version?`, `message?`, `entry_path?` | Full mode (no `base_revision`): `files` is the whole bundle. Patch mode: upsert `files`, drop `remove`. Returns `{artifact, revision, no_change}` |
| `rollback_artifact` | `artifact_id`, `revision_number`, `expected_version?`, `message?` | Appends a revision equal to the target (the new head is `revision_count + 1`); `no_change: true` when the target is the head |

There is no tool to rename, trash or delete an artifact; that is done in the webapp.

## Stream tokens

| Tool | Inputs | Returns and notes |
|---|---|---|
| `create_stream_token` | `resource_type?` (`project`, the only and default value), `resource_id`, `event_types`, `ttl_seconds?` (default 24 h, max 7 days; out-of-range values are clamped, check `expires_at`), `label?` | A short-lived `wss://` URL that streams a project's events (subprotocol `v1`, one JSON event per frame with a `seq` cursor; reconnect with `?after=<seq>`). The URL is the credential: pass it straight to a WebSocket client (for example Claude Code's Monitor tool), never write, log, or repeat it. Shown once |
| `list_stream_tokens` | `resource_id?`, `live_only?`, `mine_only?`, `limit?` (default 50, max 200), `offset?` | Tokens in the organisation with scope, expiry, liveness; secrets never returned |
| `revoke_stream_token` | `id` | Immediately closes the URL (a `stream.error` frame with reason `revoked`, then close code `4001`) and purges buffered events. Revoking someone else's token needs the organisation owner or admin role |

Feed protocol: the first frame is `stream.ready` (restates scope and `last_seq`); event frames are `{"v":1,"seq":N,"type":"spec_file.updated","at":"...","resource":{"type":"project","id":"..."},"data":{...}}`; `stream.expiring` arrives about a minute before expiry; `stream.error` precedes a refusal. Close codes: `4001` bad or revoked token, `4008` slow consumer, `4009` too many sockets for the token, `1013` feed unavailable (retry). Reconnect with `?after=<seq>` (`?after=0` replays the buffer).

Event types: `project.updated|deleted`; `spec_file.created|updated|deleted|lock` (`updated` covers new revisions, rollbacks and trash moves; a task status change is a new revision of its tasks file); `spec_file_comment.created|updated|thread_state_changed|anchors_updated`; `attachment.created|deleted`; `spec_session.created|updated|deleted`; or `*`. There are no task or artifact events: watch `spec_file.updated` on the tasks file, and poll `list_artifacts` (`revision_count`) for artifacts. Typical use: `Monitor({ ws: { url: <url>, protocols: ["v1"] }, description: "myspec project events" })`.

## Errors

- ``<tool> failed: Could not discover endpoints from https://app.myspec.dev/api/v1/config (Not authenticated. Set MYSPEC_API_TOKEN to a MySpec API token, or run `npx @myspec/mcp-server login` to sign in.). Run `npx @myspec/mcp-server login` and retry.`` The user must sign in; see the `setup` skill. The same wrapper without the `Not authenticated` part is a real connectivity or discovery failure.
- `<tool> failed: permission denied — this action needs the <role> role on the project; you have <role>. Ask a project admin for access.` A role problem, not a sign-in problem: a new token does not help.
- `<tool> failed: the task board is turned off in this MySpec environment, so the task tools are unavailable here until it is turned on.` Use the `update_spec_file` checkbox fallback.
- `... was NOT updated: ... changed it ... since you read it.` A spec file version conflict; see `write-back-protocol.md`.
- `Artifact <id> was NOT written: ...` An artifact conflict; the message says whether to retry as is, re-read the head, or resend full content (the `artifacts` skill).
- `file_path must be rooted at 'specs' or 'openspec' ...` Path rule violation on `upload_spec_file`.
