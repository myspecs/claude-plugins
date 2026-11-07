# Write-back protocol for spec files

MySpec spec files are edited by several people and AI sessions at once. Every write must be based on a known version so nobody's work is overwritten. The mechanism is optimistic concurrency with an opaque token called `content_version`.

## Tokens

- `get_spec_file` and `read_spec_file` return `content_version` for the latest revision (`read_spec_file` omits it when you pass a historical `revision`).
- `update_spec_file` accepts `expected_version` and, on success, returns the file summary with the new `content_version`.
- `content_version` is not `revision_count`. Revision numbers can go down when a revision is discarded; the version token only ever moves forward. Never pass `revision_count` as `expected_version`.

## The loop

1. Read: `get_spec_file` for the token, then `read_spec_file` for the body (paginate with `next_offset` until `truncated` is false). Save `content_version` as `V`. If the two calls disagree on `content_version`, the file changed between them; read again.
2. Edit locally: apply the smallest change that expresses your intent (one checkbox, one section). Preserve everything else byte for byte, including `N\.` escapes and annotation lines.
3. Write: `update_spec_file` with `file_id` (or `project_id` plus `file_path`), the full new body via `content` or `local_file_path`, and `expected_version: V`.
4. On success, save the returned `content_version` as the new `V` for any further writes to this file in the session.

`local_file_path` is preferred when you edited a downloaded copy on disk: the server reads the bytes directly and nothing large passes through the model. Use an absolute path.

## Conflict handling

A lost race returns an error shaped like this (the actor reads "an AI session" when another AI wrote it):

```
specs/my-app/tasks.md was NOT updated: another user (id ...) changed it at 2026-... since you read it.
It is now at revision 7. Their version was kept — nothing of theirs was overwritten. Re-read the file
with get_spec_file (or read_spec_file), decide how your change should combine with theirs, then update
again passing the content_version that re-read returns as expected_version. (It was at version 12 when
your write was rejected.) Do not simply resend the same content — you would undo their work.
```

Recovery:

1. `get_spec_file` for the new `content_version`, then `read_spec_file` for the fresh body.
2. Compare the fresh body with what you read before. Someone may have checked other tasks or edited text; keep all of that.
3. Re-apply only your own change to the fresh body. If your task is already `[x]` in the fresh copy, stop and tell the user; do not write.
4. `update_spec_file` with the new token.
5. If it conflicts again, repeat. Never resend the stale body and never drop `expected_version` to force the write.

The "version ... when your write was rejected" number in the message is history, not the token to resend. The token is whatever the re-read returns.

## Precondition-required projects

Some projects reject any update without `expected_version`:

```
... was NOT updated: this project requires every update to declare the version it was based on.
Read the file with get_spec_file (or read_spec_file), then call update_spec_file again passing its
content_version as expected_version.
```

Follow the loop above; there is no legitimate reason to write without a token.

## Task status

A task's status is its checkbox, and the platform owns the write: use `set_task_status` instead of editing the box by hand. It rewrites only the marker (`[ ]` pending, `[-]` in progress, `[x]` done), one new revision per file, recorded as an AI change, and keeps every other byte.

1. `list_tasks` with `project_id` (and `file_id` for one bundle's `tasks.md`). Find the task by its `key` (`4` for `4\.`, `1.2`, `T007`; empty for a task line in another shape, then match its `title` and `section`) and take its `task_id`, plus the file's `content_version` from `files[]`.
2. `set_task_status` with `project_id`, `task_ids`, `status` (`in_progress` when you start, `done` when the acceptance criteria pass) and `expected_versions: [{spec_file_id, content_version}]` from step 1, so the change lands only on the lines you saw.
3. Read the result per task: `updated` or `unchanged` is fine; `removed` means the task is no longer in its file (re-list and tell the user); `failed` carries a code:
   - `file_changed`: the file changed since your `list_tasks`. List again, check the task is still the one you mean and not already done by someone else, and retry with the new version.
   - `conflict`: the file kept changing under three attempts. Retry once after a fresh `list_tasks`; then report.
   - `quota_exceeded`, `not_found`: report to the user; do not fall back to a hand edit.
4. The file's new `content_version` is in the result's `files[]`; use it for any later `update_spec_file` of the same file.

Several tasks of one bundle: pass them in one call (up to 200). The call is partial: a file that cannot be written fails only its own tasks, and the tool reports an error only when every task failed.

Fallback: when a task tool answers `the task board is turned off in this MySpec environment`, edit the checkbox with the loop above (read, change only that marker, `update_spec_file` with `expected_version`). The same markers apply.

Planning fields (assignee, priority, story points, cycle, dates, labels, relationships) are not in the file: change them with `update_tasks` (all or nothing, up to 200 tasks, `null` clears a field, labels and relationships are added or removed, never replaced). `list_task_assignees` lists who can be assigned and your own `self_user_id`; `"me"` works as an assignee.

## Creating versus updating

- New file: `upload_spec_file` with `project_id`, a `file_path` rooted at `specs/` or `openspec/` (at most three directory levels below the root), `content` or `local_file_path`, and optionally `file_type`. It rejects a path that already exists.
- Existing file: `update_spec_file` as above. When `upload_spec_file` reports that the path exists, switch to `get_spec_file` for the token and then `update_spec_file`.

## Deleting

Prefer `move_spec_file_to_trash` (recoverable via `restore_spec_file_from_trash`). There is no permanent-delete tool for spec files.
