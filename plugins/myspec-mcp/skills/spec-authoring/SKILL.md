---
name: spec-authoring
description: Write, edit, review, or push Spec Driven Development documents in the MySpec platform's exact formats. Use when the user asks to create or update a constitution, requirements, solution, tasks, or proposal document for MySpec; mentions EARS or EARS+ acceptance criteria ("WHEN ... THEN ... SHALL"), FR/NFR ids, a brownfield change proposal, a requirements delta (AR/BR/CR), or an OpenSpec change or delta spec; or wants local spec files uploaded or synced to a MySpec project. Requires the myspec MCP server for pushing (see the setup skill).
user-invocable: false
---

# Author specs in MySpec formats

Use this skill to produce documents that look exactly like the ones the MySpec platform generates, so they pass its reviewers, render correctly in the webapp, and can be consumed by the `implement` skill. Tool calls go through `mcp__plugin_myspec-mcp_myspec__<tool>` (signatures in `../implement/references/mcp-tools.md`).

## 1. Pick the document set

| Scenario | Documents, in writing order | Where they live on the platform |
|---|---|---|
| Greenfield (new product or service) | `constitution.md`, `requirements.md`, `solution.md`, `tasks.md` | `specs/<bundle>/` |
| MySpec brownfield (change to an existing product) | `proposal.md`, `requirements.md` (delta), optional `tasks.md` | `specs/<bundle>/` |
| OpenSpec brownfield (OpenSpec CLI compatible) | `proposal.md`, `specs/<capability>/spec.md` per capability, optional `design.md`, `tasks.md` | `openspec/changes/<change-id>/` |

`<bundle>` and `<change-id>` are lowercase kebab-case. Ask the user which scenario applies when it is not obvious from the request or the repository.

## 2. Read the matching format reference before writing

| Document | Reference |
|---|---|
| constitution | `references/constitution-format.md` |
| requirements (FR/NFR, EARS+) | `references/requirements-format.md` |
| solution | `references/solution-format.md` |
| tasks (MySpec milestone format) | `../implement/references/tasks-format.md` |
| proposal and requirements delta (MySpec brownfield) | `references/brownfield-formats.md` |
| OpenSpec proposal, delta spec, design, tasks | `references/openspec-formats.md` |

Each reference carries the section skeleton, id conventions, and the quality rules the platform's reviewers enforce. Reproduce headings exactly.

## 3. Gather inputs, then write

- Read what already exists first: local spec files, the repository (for brownfield work), and any bundle already on the platform (`list_spec_file`, `read_spec_file`). Later documents must build on earlier ones: requirements obey the constitution, the solution uses only constitution-approved technology, every FR gets a solution and at least one task.
- Ground brownfield claims in files you actually read. Never invent modules, dependencies, or behaviour. A `BR-` entry must reference a real `file:line`.
- Ask the user for decisions the documents need (target users, stack, non-goals) instead of guessing. Keep each document proportionate to the project; omit optional sections rather than padding them.
- Write locally under `specs/<bundle>/` or `openspec/changes/<change-id>/` in the repository unless the user wants another location.

## 4. Self-review against the platform's rules

Quality bar for every document: minimal but complete (focused, not thin), reviewable in one sitting (roughly five to ten pages, otherwise split the bundle), explicit about what is out of scope, every task completable in one session, and free of padding. If a reviewer would skim it thinking "the AI probably got it right", it is too large.

- Constitution: all nine sections present and in order; 3 to 5 items each; `N/A` where nothing applies; every constraint traceable to a user decision.
- Requirements: technology-neutral; every FR has testable EARS+ acceptance criteria; every NFR has a measurable target and a priority; no architecture prescriptions; Data and Integration sections at most five bullets each.
- Solution: only approved technology; Mermaid `flowchart` and `erDiagram` present (plus `sequenceDiagram` when three or more modules); every measurable NFR maps to a Success Criteria row; decisions carry rationale and alternatives.
- Tasks: every FR covered by at least one task; dependencies explicit; sizes within Small/Medium/Large; `- [ ] N\. Title` shape with the three annotation lines.
- OpenSpec deltas: every ADDED or MODIFIED requirement has SHALL/MUST text and at least one `#### Scenario:` with WHEN/THEN bullets; one capability per file; capability names are module nouns, not change names.
- No document metadata footers (version, date, status) anywhere.
- Plugin conventions the platform does not generate but tolerates: a `## Clarifications` section at the end of `requirements.md` and `- Clarification:` bullets under tasks (see the `implement` skill). Keep them; they record decisions.

## 5. Push to MySpec

1. Find the project with `list_projects` (offer `create_project` if none).
2. For each new file: `upload_spec_file` with `project_id`, the platform `file_path`, `local_file_path` (absolute), and `file_type`. The type is derived from the basename for constitution, requirements, solution, tasks, and proposal; pass `openspec-spec` for OpenSpec `design.md` and delta files (the only other value).
3. If the path already exists, `get_spec_file` for `content_version`, then `update_spec_file` with `expected_version`. Follow `../implement/references/write-back-protocol.md` on conflicts. Write one revision per file per run.
4. Report the file ids and paths written.

Path rules enforced by `upload_spec_file`: root `specs/` or `openspec/`, no `..`, at most three directory levels below the root. OpenSpec capability deltas at `openspec/changes/<id>/specs/<capability>/spec.md` are four levels deep, so new ones cannot be created through MCP even though the webapp workflow writes them. Upload the proposal, design, and tasks, keep new capability deltas local for the OpenSpec CLI, and tell the user. Deltas that already exist on the platform can still be updated with `update_spec_file`. Do not flatten the path; the OpenSpec tooling (`/opsx:apply`, `openspec archive`) depends on it.
