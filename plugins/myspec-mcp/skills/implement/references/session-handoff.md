# Session handoff

Implementation usually spans several Claude Code sessions and several people. Two things carry state: the checkboxes in `tasks.md` on the platform (shared truth) and a local progress note (private context).

## Resume order

1. `get_spec_file` and `read_spec_file` on `tasks.md`; the checked boxes say what is done.
2. `.specs/<bundle>/progress.md` if present; it says why and what is half-done.
3. `git log --oneline -20` and `git status`. Uncommitted changes are normal when the user declined per-task commits; reconcile them against `progress.md` and finish or set them aside deliberately. Never discard them without asking the user.
4. If checkboxes and code disagree, run the `analyze` skill in convergence mode.

## Progress note

Path: `.specs/<bundle>/progress.md` in the repository root (the `.specs/` directory is gitignored by convention; add it if missing). Keep it under a page; it is a note, not a log.

```markdown
# Progress: <project> / <bundle>

Updated: <YYYY-MM-DD> (session by <name or "Claude Code">)

## Done this session
- Task 4 checkout API (FR-003, NFR-001): tests in tests/checkout_test.ts, revision 7 written

## In progress
- Task 5 payment webhook: handler written, signature verification pending; see TODO in src/webhooks/payment.ts

## Blockers and decisions
- FR-006 rate limit unspecified; asked user, answer recorded under task 5 in tasks.md

## Next
- Finish task 5, then task 6 (depends on 4, 5)
```

At a milestone checkpoint, offer `upload_attachment` on this file (or a test report) so collaborators without repo access see the snapshot. Attachments are additive; use `override: true` to replace an earlier upload with the same name.

## Managed block in CLAUDE.md or AGENTS.md (opt-in)

Only when the user agrees, write a marker-delimited block so future sessions know which MySpec project this repo implements. Never touch text outside the markers; replace the block in place if it exists.

```markdown
<!-- myspec:start -->
## MySpec
- Project: <name> (`<project_id>`)
- Bundle: `specs/<bundle>/` (constitution, requirements, solution, tasks)
- Workflow: use the `myspec-mcp:implement` skill. Read constitution first. Take `content_version` from `get_spec_file` before every `update_spec_file`. Record clarifications in tasks.md or the `## Clarifications` section of requirements.md. Local notes in `.specs/<bundle>/progress.md` (gitignored).
<!-- myspec:end -->
```

If both `CLAUDE.md` and `AGENTS.md` exist, write to the one the user names; default to `CLAUDE.md`.
