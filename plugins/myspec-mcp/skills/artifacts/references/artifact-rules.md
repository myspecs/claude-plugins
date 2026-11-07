# Artifact rules, limits and errors

Facts from `@myspec/mcp-server` 1.1.2 and the MySpec platform. The platform can change the limits by configuration; the server's messages are the final word.

## Limits

| Item | Limit |
|---|---|
| Live artifacts per project | 50 (`artifact_limit_reached`) |
| Files per revision | 50; at least 1; no path twice in one request |
| File size | 2 MiB, measured after base64 decoding |
| Revision size | 10 MiB |
| Revisions kept | The newest 50; older ones are pruned (reading or rolling back to one fails with not found) |
| Name | 200 characters |
| Description | 2000 characters |
| Message | 500 characters |
| Path | 255 bytes, at most 8 segments |
| `read_artifact_file` | 2000 lines and 1 MiB per call; files over 8 MiB refused |
| `list_artifacts` | default 50, max 100 per page |

## Paths

Relative and `/`-separated (`assets/app.js`). Refused: a leading `/`, `.` or `..` segments, empty segments, backslashes, NUL or control characters. Paths are case-sensitive. In a website prototype, every reference between files must be relative too, or the preview breaks.

## Slugs

`^[a-z0-9][a-z0-9-]{0,63}$`: 1-64 lowercase letters, digits or hyphens, starting with a letter or digit. Derived from the name when omitted (lower-cased, runs of other characters become one hyphen, trimmed); a name with no ASCII letters or digits fails with `could not derive a slug from the name; provide one explicitly`. A slug is unique in the project, including trashed artifacts, and is freed only about a day after a permanent delete.

## Encoding and content type

- `encoding: "utf8"` (default) content must be valid UTF-8; otherwise the platform asks to send it as `base64`.
- The content type comes from the extension when it is known (html, htm, css, js, mjs, json, map, svg, png, jpg, jpeg, gif, webp, ico, txt, md, xml, csv, woff, woff2, ttf, webm, mp4, mp3, wasm). The `content_type` hint is used only for other extensions; the fallback is `application/octet-stream`.
- MySpec's own website sessions use only text files (`.html .htm .css .js .mjs .json .svg .txt .md .xml .webmanifest`) and load images and fonts from https CDNs or inline SVG; follow the same habit for prototypes others will edit with MySpec's AI.

## Entry path

The file a renderer opens first. Defaults to `index.html` when present, else the only file; with several files and no `index.html` it is required (`entry_path is required when the files do not include index.html`). It must be one of the revision's files: a revision that drops it fails with `entry_path "x" is not one of the revision's files` unless the same call sets a new one. A rollback to a revision without it falls back to `index.html` or the only file.

## Versions

- `revision_count` is the head and the value to pass as `expected_version`. It only grows.
- `write_artifact_revision`: `expected_version` defaults to `base_revision` in patch mode and to the current head in full mode (unguarded: always pass it in full mode). Passing `expected_version` equal to the head together with an older `base_revision` is accepted and builds on the old base, dropping newer changes: keep the two equal.
- `remove` is valid only in patch mode; removing a path the base does not have is not an error.
- `rollback_artifact`: `expected_version` defaults to the head; the message defaults to `Rolled back to revision N`.
- Every write returns `{artifact, revision, no_change}`; revisions written through these tools show `changed_by_kind: "ai"`.

## Errors

| Message starts with | Meaning | Do |
|---|---|---|
| `Artifact <id> was NOT written: it changed since the revision this write was based on. The head is now revision N.` | `revision_mismatch`: someone wrote a newer revision | `get_artifact`, re-apply your change to the new head, retry with `expected_version` (or `base_revision`) set to it. Never resend the stale bundle |
| `Artifact <id> was NOT written: another write or a storage collection held its lock ...` | `lock_timeout` | Retry the same call as is |
| `Artifact <id> was NOT written: a file this write relied on from an older revision is no longer stored ...` | `blob_reclaimed`: the base revision was pruned | `get_artifact`, then resend the full content of every file (full mode, or patch on the head) |
| `Artifact was NOT created: the slug is already taken in this project (trashed artifacts keep their slug).` | `slug_taken` | Pick another slug, or `list_artifacts` and write a revision to the existing one |
| `Artifact was NOT created: ... timed out waiting for a lock.` | `lock_timeout` on create | Retry as is |
| `revision=N is greater than revision_count=M ...` | `get_artifact` asked for a revision past the head | Use a revision up to the head |
| `<tool> failed: ...` with 404 | Unknown artifact, one you cannot see, or a pruned revision | Re-list; confirm the revision exists |
| `<tool> failed: ...` with 410 | The artifact is trashed or deleted | Tell the user; restoring is done in the webapp |
| `<tool> failed: ...` with 400 or 413 | A limit or rule above (`artifact_limit_reached`, a bad path or slug, a file too large, invalid UTF-8) | Fix the input |
| `... appears to be binary ... and cannot be read through this tool` | `read_artifact_file` on an image or font | Use the manifest's size and checksum |
| `<tool> failed: permission denied — this action needs the write role ...` | Read-only role or token | Ask a project admin, or use a read-write token |

## In the product

- Viewer: `https://app.myspec.dev/projects/<project id>/artifacts/<artifact id>` (`?rev=N` for a revision). Read role: view, preview, source, history, ZIP download. Write role or higher: restore, Edit with AI, @-mention.
- Spec link: `[Name](artifacts/<slug>)` or `./artifacts/<slug>`; it always opens the latest revision. An absolute `/artifacts/<slug>` is not treated as an artifact link.
- MySpec's in-app spec sessions can read artifacts (only when the project has one) and are told to link the matching prototype when they write about screens and flows.
- Website prototypes are built in MySpec by the website-artifact workflow, one artifact per session, and edited with the webapp's **Edit with AI** button; neither is started with `start_spec_session` from the released server.
