# Write-back protocol for spec files

MySpec spec files are edited by several people and AI sessions at once. Every write must be based on a known version so nobody's work is overwritten. The mechanism is optimistic concurrency with an opaque token called `content_version`.

## Tokens

- `get_spec_file` returns `content_version` for the latest revision on every server version. `read_spec_file` returns it too on 0.4.0+, and omits it when you pass a historical `revision`.
- `update_spec_file` accepts `expected_version` and, on success, returns the file summary with the new `content_version`.
- `content_version` is not `revision_count`. Revision numbers can go down when a revision is discarded; the version token only ever moves forward. Never pass `revision_count` as `expected_version`.

## The loop

1. Read: `get_spec_file` for the token, then `read_spec_file` for the body (on 0.4.0+ paginate with `next_offset` until `truncated` is false). Save `content_version` as `V`. On 0.4.0+, if the two calls disagree on `content_version`, the file changed between them; read again.
2. Edit locally: apply the smallest change that expresses your intent (one checkbox, one section). Preserve everything else byte for byte, including `N\.` escapes and annotation lines.
3. Write: `update_spec_file` with `file_id` (or `project_id` plus `file_path`), the full new body via `content` or `local_file_path`, and `expected_version: V`.
4. On success, save the returned `content_version` as the new `V` for any further writes to this file in the session.

`local_file_path` is preferred when you edited a downloaded copy on disk: the server reads the bytes directly and nothing large passes through the model. Use an absolute path.

## Conflict handling

A lost race returns an error shaped like:

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

## Creating versus updating

- New file: `upload_spec_file` with `project_id`, a `file_path` rooted at `specs/` or `openspec/` (at most three directory levels below the root), `content` or `local_file_path`, and optionally `file_type`. It rejects a path that already exists.
- Existing file: `update_spec_file` as above. When `upload_spec_file` reports that the path exists, switch to `get_spec_file` for the token and then `update_spec_file`.

## Deleting

Prefer `move_spec_file_to_trash` (recoverable via `restore_spec_file_from_trash`). There is no permanent-delete tool for spec files.
