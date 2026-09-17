---
name: plan
description: Build or refresh the factory wave plan from a MySpec tasks.md, or write the tasks.md a brownfield bundle lacks. Use when the user says "plan the factory run", "what can run in parallel", "build the waves", "which tasks are ready", "plan the tasks for this proposal", or before dispatching workers. Derives the board from platform checkboxes and open pull requests and groups ready tasks into waves of non-overlapping work; when the bundle has no tasks.md, plans the whole change into lanes sized to the change (one worker for a small change, up to 3 parallel lanes for a large one; one branch each) and uploads the list only after the user approves it.
---

# Factory plan

Tools are called as `mcp__plugin_myspec-mcp_myspec__<tool>`. Task grammar and the write-back rules are in the `myspec-mcp:implement` skill's references. This skill only reads, except for uploading an approved `tasks.md` in step 1b.

## 0. Verify bundle completion

Before planning or dispatching workers, verify that the bundle's generate session is completed. Use `get_spec_session` with the session ID from the bundle metadata to check its status. If the session status is not `completed`, stop immediately and tell the user that the factory cannot start while the spec bundle is still being generated or edited on the MySpec platform. The user must complete their generate/edit session before factory workers can be dispatched. Only proceed to load the bundle and plan waves when the session status is `completed`.

## 1. Load the bundle

Locate project and bundle (managed `<!-- myspec:start -->` block in `CLAUDE.md`, else `list_projects` and `list_spec_file`). `list_spec_file` first to see which documents the bundle has; the set depends on the workflow (greenfield: constitution, requirements, solution, tasks; MySpec brownfield: proposal, requirements delta, and `tasks.md` only in some workflows; OpenSpec: proposal, spec deltas, optional design, tasks). `get_spec_file` and `read_spec_file` on each: `tasks.md` when present (keep the `content_version` for the manager's later write), then the requirements, the design (`solution.md`, or the proposal and `design.md`), and the constitution when present. No `tasks.md` in a brownfield bundle is expected: go to 1b. For OpenSpec bundles, tasks are `## N. Group` / `- [ ] N.M`; treat each `N.M` as a task with no declared dependencies and the group as its module.

## 1b. When the bundle has no tasks.md: plan it into lanes

A MySpec brownfield bundle may be only `proposal.md` and a requirements delta; `tasks.md` is optional there. The manager then writes the task list itself and groups it into **lanes**: one worker, one branch, one pull request per lane, all lanes running at once. The number of lanes follows the size and scope of the change: a small change is one lane (a single worker); only a large change that splits cleanly gets 2 or 3. Nothing is dispatched until the user approves the list and it is on MySpec.

1. Pass the spec gate on the documents that exist (complete, every doubt clarified) before planning. A task list built on an unfinished proposal is unfinished too.
2. Map the change. From the proposal's Technical Solution and Impact, the requirements delta, and the repository itself, list every area the change touches: modules, directories, files, migrations, shared contracts (API shapes, event payloads, types, table columns, error strings), configuration, dependency manifests and lockfiles.
3. Choose the lanes. Start from one lane. A small change — one module or service, a handful of tasks, roughly a few days of work or less — stays one lane with a single worker; parallel workers would add coordination and review cost without saving time. Use 2 or 3 lanes (never above the user's concurrency cap) only when the change is large, spans areas that are independent in the code, and each lane would carry substantial work (not a single Small task). Every lane must be able to run from start to finish at the same time as the others:
   - Lanes own disjoint paths; no file is edited by two lanes. A shared file (migration sequence, route or DI registry, dependency manifest, lockfile) is owned by exactly one lane.
   - No `_Dependencies:_` crosses lanes. Work a lane would have to wait for moves into that lane, or the two lanes become one.
   - A contract two lanes share is written out in full (every field, name, unit and error value) in the tasks of both lanes, so each codes against the text, not against the other branch.
   - When the work cannot be split this way, use fewer lanes. Never split only to add workers. Balance lane sizes where the split allows.
   - Tell the user why you chose that number of lanes (size, independent areas) when you show the plan.
4. Write `tasks.md` in the MySpec brownfield format with the `myspec-mcp:spec-authoring` skill (grammar in the `myspec-mcp:implement` skill's `references/tasks-format.md`): H1 `# Implementation Tasks: [Change Name]`, the brownfield milestones, document-wide numbering, and for each task implementation details naming the files it touches, `Acceptance Criteria:`, `_Dependencies:_` (same lane only), `_Requirements:_` (AR/BR/CR ids), `_Complexity:_`. Every AR/BR/CR id appears in at least one task. `## Dependency Graph` closes the file and states that the lanes run in parallel with no cross-lane dependencies. Put the `## Branch Plan` section just before it:

   ```markdown
   ## Branch Plan

   Planned by the Software Factory Manager: <K> lanes, run in parallel, one pull request each.

   ### Lane 1: <short name>
   - Branch: factory/<bundle>/lane-1
   - Tasks (in order): 1, 3, 4
   - Owns: <directories, files, modules>
   - Does not touch: <paths owned by other lanes>
   - Shared contracts: <each contract, and the task numbers in both lanes that carry its full text>
   ```

5. Show the user a lanes table (lane, branch, tasks, owned paths, size) and the draft. Apply every change they ask for; do not upload before they approve.
6. Upload with `upload_spec_file` (`file_path` `specs/<bundle>/tasks.md`, `file_type` `tasks`), then `get_spec_file` for its `content_version`. Note in `.specs/<bundle>/factory-run.md` that the manager authored it and the user approved it.
7. Re-run the spec gate on the whole bundle, now including `tasks.md`. Then the plan has a single wave: every lane at once, one worker per lane (see `dispatch`).

Bundles that arrive with their own `tasks.md` keep the wave planning below; do not re-plan them into lanes unless the user asks.

## 2. Derive the board

| Status | Source of truth |
|---|---|
| done | `- [x]` in `tasks.md` on the platform |
| in flight | An open pull request or remote branch named `factory/<bundle>/task-<N>`, or `factory/<bundle>/lane-<L>` for a lane listing task N in `## Branch Plan` (also accept `claude/`-prefixed branches whose title or body names `task N` or `lane L`) |
| blocked | A pull request labelled `blocked`, or whose `## Factory report` says `BLOCKED` |
| ready | `- [ ]`, not in flight, every `_Dependencies:_` number done |
| waiting | `- [ ]` with an unmet dependency |

Use `gh pr list --state open --json number,title,headRefName,labels,statusCheckRollup` and `git ls-remote --heads origin 'factory/*'`. Never store the board as truth; a stored copy is a cache.

## 3. Build waves

1. Take every ready task.
2. For each, list the solution modules and likely files: the `_Requirements:_` ids map to modules in `solution.md`; the task's implementation details name files. When two ready tasks share a module or file, they go in different waves (the lower task number first).
3. Order the wave by milestone, then task number. Cap the wave at the concurrency limit the user set; leftover ready tasks form the next wave.
4. Mark tasks the constitution or task text calls Large as single-session candidates only if their acceptance criteria are precise; otherwise flag them for splitting before dispatch.

## 3b. Task shapes that change dispatch

- **Decision tasks** ("resolve the open questions", "confirm scope"): the answer belongs to the user and usually edits `requirements.md`. The manager resolves them with the user, records the decisions as Clarifications, marks the task `[x]`, and dispatches nothing for it — a worker may not edit spec files.
- **Contract freeze tasks** (shared types, stub routes, event kinds frozen before parallel branches start): check the freeze is complete before merging it — request bodies as well as responses, list response wrappers, internal events and RPC or subject names the branches exchange, error `reason` strings, and the unit of any offset or length (bytes, code points, UTF-16). Drift tests must fail in BOTH directions. Anything left out becomes an unfrozen coupling the manager has to relay by hand.
- **Branch-ownership plans** (`tasks.md` assigns directory ownership and chains tasks inside a branch): dispatch one worker per branch chain rather than one per task, with the ownership map and the do-not-touch list in every brief. A `## Branch Plan` written in step 1b is the manager-written form of this.

## 4. Output

```markdown
## Board
| Task | Title | Status | Deps | Requirements | PR / session |
|------|-------|--------|------|--------------|--------------|

## Wave 1 (N sessions, cost note)
| Task | Modules / files | Size | Brief ready |

## Lanes (manager-planned bundles only; replaces Wave 1)
| Lane | Branch | Tasks | Owns | Size | Brief ready |

## Waiting
| Task | Blocked by |

## Spec gate blockers (no task is dispatched until every item is resolved)
- Tasks needing a split or clarification
- Dependency cycles or unknown requirement ids (send to the `myspec-mcp:analyze` skill)
- Missing documents, a spec session still running, `TBD`/placeholder text, open questions, CRITICAL or HIGH analyze findings
```

State the cost before the manager dispatches: number of sessions, sizes, and that parallel sessions share and multiply rate-limit consumption.
