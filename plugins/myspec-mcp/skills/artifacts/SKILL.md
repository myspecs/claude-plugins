---
name: artifacts
description: Find, read, create, revise, and roll back MySpec artifacts — versioned multi-file bundles such as a clickable HTML/CSS/JS website prototype or UI mockup stored in a MySpec project — and link them from spec files. Use when the user says "artifact", "prototype", "mockup", "clickable demo", "upload this prototype to MySpec", "update the mockup", "show me the prototype for this screen", "roll back the artifact", "link the prototype in the spec", or pastes a link like app.myspec.dev/projects/<id>/artifacts/<id>; when a spec file contains a link `[Name](artifacts/<slug>)`; or when an artifact tool fails with "Artifact … was NOT written" or "Artifact was NOT created". Requires the myspec MCP server (see the setup skill).
user-invocable: false
---

# MySpec artifacts

Every tool below is called as `mcp__plugin_myspec-mcp_myspec__<tool>`. Signatures: the `implement` skill's `references/mcp-tools.md` § Artifacts. Limits, path and slug rules, and every error with its fix: `references/artifact-rules.md`.

An artifact is a set of files MySpec stores and versions as one unit, most often a clickable website prototype (`index.html` plus styles, scripts and SVG). Each write creates an immutable revision; `revision_count` is the head and only grows (a rollback appends a revision). The webapp previews it in a sandboxed frame at desktop, tablet and mobile widths, shows its source and history, and downloads it as a ZIP. Artifacts come from two places: MySpec's website-artifact sessions in the webapp, and agents using these tools.

## 1. Find and read

1. `list_artifacts` with `project_id` (paginate with `next_offset`). Match by `slug` when a spec links one (`[Name](artifacts/<slug>)`, also `./artifacts/<slug>`), by name otherwise; a viewer URL `/projects/<project>/artifacts/<artifact id>?rev=N` names the id and revision directly. Only live artifacts are listed.
2. `get_artifact` for the head (or `revision: N`): the manifest lists every file's path, content type, size and checksum, and the `entry_path` a renderer opens first.
3. `read_artifact_file` for each text file you need, starting with the entry file, then the CSS and scripts it references. Paginate with `next_offset`. Images, fonts and other binary files cannot be read; the manifest gives their size and checksum.
4. To see what changed between two revisions, read the same path at both revisions, or compare manifest checksums.

When implementing from a spec, treat a linked prototype as the visual and interaction reference for the screens it shows: layout, labels, states, navigation. The requirements still win: where the prototype and the requirements disagree, ask the user instead of choosing.

## 2. Create

Only when the user asks for an artifact on MySpec (for example "put this prototype on MySpec"). Requires the Write role on the project.

1. `list_artifacts` first: an artifact with the same purpose may exist; then write a revision to it (§3) instead of a second one. A project holds at most 50 live artifacts.
2. Collect the files. Text files go in as `utf8`; binary files (images, fonts) as `base64`. Paths are relative (`assets/logo.svg`), never with a leading `/`, since the sandboxed preview has no origin; the same sandbox has no cookies, localStorage or IndexedDB, and loads external scripts and styles only over https.
3. `create_artifact` with `project_id`, `name`, `files`, and a `slug` the user would recognise (lowercase letters, digits and hyphens; derived from the name when omitted, but a name with no ASCII letters or digits needs an explicit one). Give `entry_path` when there are several files and no `index.html`. Add a short `message` ("first version: checkout flow").
4. On `slug_taken`, pick another slug or write to the existing artifact. Report the artifact's name, slug and revision, and that the user can open it under the project's Artifacts in the webapp.

## 3. Revise

1. `get_artifact` for the head: save `revision_count` as `H`, and read the files you will change.
2. Write with the smallest safe call:
   - **Patch mode** (a few files change): `write_artifact_revision` with `base_revision: H`, only the changed or new files in `files`, and paths to drop in `remove`. `expected_version` defaults to `H`, so a write that raced with someone else conflicts instead of discarding their revision.
   - **Full mode** (most files change, or you rebuilt the bundle): `write_artifact_revision` with every file in `files` and **`expected_version: H`**. Without it the server takes the current head, an unguarded write that can silently replace a newer revision.
   - Keep the entry file in every revision, or change `entry_path` in the same call.
   - Always set a `message` describing the change.
3. Read the result: `revision.revision_number` is the new head; `no_change: true` means the files were identical to the previous head (the revision is still recorded).
4. On a conflict, follow the message (`references/artifact-rules.md`): `revision_mismatch` means re-read the head, re-apply only your change on top of it, and retry with the new head; `lock_timeout` means retry the same call unchanged; `blob_reclaimed` means re-read and resend the full content of every file. Never retry by dropping `expected_version`.

## 4. Roll back

`get_artifact` for the head `H`, confirm the target revision with the user (only the newest 50 revisions are kept; an older one fails with not found), then `rollback_artifact` with `revision_number` and `expected_version: H`. It appends a revision equal to the target; history is never rewritten. Rolling back to the head is recorded with `no_change: true`.

## 5. Link from a spec

A spec file links an artifact with a relative Markdown link: `[Checkout prototype](artifacts/checkout-flow)`. The webapp turns it into a marker that opens the latest revision. Use only slugs that exist (`list_artifacts`); a slug with no artifact stays a plain link. People who open a spec through a share link see the name but cannot open the artifact. Add or change such links through the write-back protocol (the `spec-authoring` skill for new sections), and write them where the spec describes the screens or flows the prototype shows.

## Limits of these tools

- No tool renames, trashes, restores or deletes an artifact; tell the user to do it in the webapp. A trashed artifact answers 410 and still owns its slug.
- Writes need the Write role and a read-write token; reading needs the Read role.
- There are no artifact events on the project stream: to notice a new revision, compare `revision_count` from `list_artifacts`.
- Editing an artifact with MySpec's own AI ("Edit with AI") is started from the webapp, not from these tools or `start_spec_session`.
