---
name: implement
description: Implement software from a MySpec specification bundle using Spec Driven Development. Use when the user asks to implement, build, continue, resume, or "work on the next task" from a MySpec project; mentions tasks.md, requirements.md, solution.md, constitution.md, FR-xxx or NFR-xxx ids, milestones, acceptance criteria, the task board, "mark the task done" or "in progress", "assign the task to me", or "my tasks"; wants to pull, download, sync, or read spec files from MySpec; or wants to apply a MySpec change proposal or an OpenSpec change to the current repo. Requires the myspec MCP server (see the setup skill when tools are missing or return login errors).
user-invocable: false
---

# Implement from MySpec specs

Every tool below is called as `mcp__plugin_myspec-mcp_myspec__<tool>`. References: `references/mcp-tools.md` (signatures), `references/tasks-format.md` (task grammar and statuses), `references/write-back-protocol.md` (safe writes and task status), `references/acceptance-criteria-to-tests.md` (tests from criteria), `references/session-handoff.md` (resume and progress notes), `references/sdd-principles.md` (the rules behind this loop).

Principles: the spec bundle is the source of truth. When the spec turns out wrong or incomplete, change the spec with the user before changing the code; never adapt the spec to match code silently. Read before coding. One task per iteration, sized for one session. Acceptance criteria become tests. Progress is recorded where every collaborator sees it. Spec updates are part of the definition of done.

## 0. Preflight

Confirm `list_projects` works. If the tool is missing or returns "Not authenticated", stop and follow the `setup` skill.

## 1. Locate the project and bundle

1. If the repo's `CLAUDE.md` or `AGENTS.md` contains a `<!-- myspec-mcp:start -->` block (or the older `<!-- myspec:start -->`; see `references/session-handoff.md`), use the project it names, and find the bundle with step 3.
2. Otherwise `list_projects` with `query` set to the user's words. One match: use it. Several: ask. None: ask whether to `create_project`.
3. `list_spec_file` with `project_id` and `path: "specs"`; if empty, call again without `path` (OpenSpec changes live under `openspec/changes/<id>/`). A bundle is the set of files sharing a directory. Match documents by `file_type`, not filename; for `openspec-spec` files, which cover both `design.md` and every capability delta, use the path to tell them apart. If several bundles exist, ask.
4. Note coexisting local spec tooling (`.specify/`, `openspec/`, `.kiro/`) and do not overwrite its files.
5. When the block is missing, offer once to write it (the project line only) into `CLAUDE.md` and commit it, so every later session and every clone skips the project lookup. Write and commit only with the user's agreement (`references/session-handoff.md`).

Bundle shapes: greenfield (constitution, requirements, solution, tasks; the enterprise workflow adds `quality.md`); Spec Kit (constitution, spec, plan, tasks); MySpec brownfield (proposal, requirements delta with AR/BR/CR ids, optional tasks); OpenSpec (proposal, `specs/<capability>/spec.md` deltas, optional design, tasks). If a document is missing, say so; never invent it.

## 2. Resume state

- `list_tasks` with `project_id` and the bundle's `tasks.md` as `file_id`: each task's `status` (`[ ]` pending, `[-]` in progress, `[x]` done), assignee and relationships, plus the file's `content_version`. Then `read_spec_file` for the task text. The checkboxes are the shared truth. When the task board is turned off, `get_spec_file` and `read_spec_file` alone (`references/write-back-protocol.md` § Task status).
- A task `[-]` assigned to you (`assignee_user_id: "me"` filter) and without an `agent:<name>` label is one you or an earlier session started: resume it before picking a new one. A `[-]` task with an `agent:` label belongs to a Software Factory agent, even on your account: leave it alone.
- Read `.specs/<bundle>/progress.md` if it exists and `git log --oneline -20` for what the last session did.
- If the repo already has an implementation that the checkboxes do not reflect, run the `analyze` skill in convergence mode before continuing rather than redoing work.

## 3. Read the bundle

Read the constitution in full; it is binding. Read the rest in order, but load only what the current task needs when the bundle is large:

| Bundle | Order |
|---|---|
| Greenfield | constitution, requirements, solution, tasks |
| MySpec brownfield | proposal, requirements delta, tasks |
| OpenSpec | proposal, every `specs/*/spec.md`, design, tasks |

- `read_spec_file` is cached on disk and paginates (2000 lines per call; follow `next_offset`).
- A spec that links an artifact (`[Name](artifacts/<slug>)`, usually a clickable prototype of a screen or flow) gives the UI reference for the tasks that build it: find it with `list_artifacts` by slug and read its files as the `artifacts` skill shows. Build the UI to match it unless the requirements say otherwise; a difference between the prototype and the requirements is a spec question (step 5), not a choice to make alone.
- `download_spec_file` only when the user wants an editable local copy. It lands under `.specs/` in the directory Claude Code was started in; tell the user to gitignore `.specs/`.
- Brownfield bundles: match the existing architecture, conventions, and patterns of the codebase. This is a change to an existing project, not a greenfield build.

## 4. Pick the next task

Parse `tasks.md` per `references/tasks-format.md`. "Next" is the first pending task in document order whose `_Dependencies:_` are all `[x]` and that no board relationship marks `blocked_by` an unfinished task (Spec Kit: phase order; OpenSpec: the first unchecked box). Skip a `[-]` task that has another assignee or an `agent:<name>` label (a factory agent is building it; `references/tasks-format.md` § Choosing the next task). Honour a user-named task, but flag unmet dependencies and a task already in progress for someone else or an agent.

Claim it before coding, so collaborators on the board see who works on what: `set_task_status` to `in_progress` (with `expected_versions` from `list_tasks`), and, when the task has no assignee, `update_tasks` with `assignee_user_id: "me"`. Assign it to someone else only when the user asks. Before coding, restate the task title, its acceptance criteria, and the requirement ids on its `_Requirements:_` line, then re-read exactly those FR/NFR (or AR/CR) sections and the solution modules they touch.

Parallelism: tasks whose dependencies are met and whose solution modules and files are disjoint may be delegated to subagents in parallel. Default is sequential; never run two tasks that touch the same files at once. Subagents never change task status or write `tasks.md` or `progress.md`; the parent session does that after each subagent reports (one `set_task_status` call can carry several tasks).

## 5. Clarify before coding

If the task or its requirements leave a decision open (ambiguous criterion, missing edge case, two valid designs), ask at most five multiple-choice questions with `AskUserQuestion`, one topic each. Write the answers back so they outlive the chat:

- Task-scoped: an indented `- Clarification: <question>: <answer>` bullet under that task in `tasks.md` (it shows as the task's details on the board).
- Requirement-scoped: a `## Clarifications` section appended at the end of `requirements.md` with `- FR-001: <question>: <answer>` bullets. This section is a plugin convention; the platform does not generate it.

Both go through the write-back protocol. Do not proceed on a guess for a product decision.

## 6. Implement the task

1. Ask once, at the start of the loop, whether the user wants a commit after each task. Honour that answer for the rest of the session; never commit unasked.
2. Derive one test per acceptance criterion per `references/acceptance-criteria-to-tests.md`, named for traceability (for example `FR-003 AC2` in the test name). Write them first when the stack allows; they must fail before the change and pass after.
3. Implement following the solution's module layout, data model, and API design, and every constitution constraint (stack, testing approach, coding standards, security).
4. Run the tests for this task plus the affected suite. A green run is the stop condition, not "looks done".
5. Constitution check: re-read the Technology, Architecture, Coding Standards, and Security sections and confirm the change violates none. Fix before marking done.
6. Stay within the one task. Note out-of-scope discoveries for step 8 and the report.

## 7. Record progress

1. Mark the task done: `set_task_status` with `status: done` and `expected_versions` from a fresh `list_tasks` (`references/write-back-protocol.md` § Task status). On `file_changed`, list again, confirm the task is still yours and not already done, retry. When the task board is turned off, flip that task's marker to `[x]` with `update_spec_file` and `expected_version` instead, keeping every other byte. Never omit the version.
2. Update `.specs/<bundle>/progress.md` (format in `references/session-handoff.md`).
3. If the user opted in, commit with a message that names the task and requirement ids, for example `feat: task 4 checkout API (FR-003, NFR-001)`.

## 8. Spec drift

When implementation shows a requirement, design decision, or task is wrong or incomplete, do not silently diverge and do not quietly rewrite the spec either. Describe the discrepancy and the proposed wording, get the user's agreement, then apply it: small corrections through the write-back protocol; new sections or documents through the `spec-authoring` skill. Edits to your own task's sub-bullets (clarifications, progress) and its status and planning fields need no separate approval. Gaps discovered after the fact: the `analyze` skill's convergence mode appends tasks without rewriting existing ones. Mention every spec edit in the report.

## 9. Milestone checkpoint

When the last task of a `## Milestone` is done: run the full test suite, run the `analyze` skill's convergence mode for that milestone's requirements, summarise what the milestone delivers against its requirement ids, and stop for the user to review before starting the next milestone. Offer to `upload_attachment` the progress note or a test report as a shared snapshot.

## 10. Report

State: task number and title; requirement ids satisfied; what was built; tests written and their result; the status change (and the `tasks.md` revision it made); clarifications recorded; spec edits made or deferred; conflicts resolved; the next task and any blockers.
