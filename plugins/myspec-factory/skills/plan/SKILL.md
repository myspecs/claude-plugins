---
name: plan
description: Build or refresh the factory wave plan from a MySpec tasks.md. Use when the user says "plan the factory run", "what can run in parallel", "build the waves", "which tasks are ready", or before dispatching workers. Read-only; derives the board from platform checkboxes and open pull requests, then groups ready tasks into waves of non-overlapping work.
---

# Factory plan

Tools are called as `mcp__plugin_myspec-mcp_myspec__<tool>`. Task grammar and the write-back rules are in the `myspec-mcp:implement` skill's references; this skill only reads.

## 0. Verify bundle completion

Before planning or dispatching workers, verify that the bundle's generate session is completed. Use `get_spec_session` with the session ID from the bundle metadata to check its status. If the session status is not `completed`, stop immediately and tell the user that the factory cannot start while the spec bundle is still being generated or edited on the MySpec platform. The user must complete their generate/edit session before factory workers can be dispatched. Only proceed to load the bundle and plan waves when the session status is `completed`.

## 1. Load the bundle

Locate project and bundle (managed `<!-- myspec:start -->` block in `CLAUDE.md`, else `list_projects` and `list_spec_file`). `get_spec_file` and `read_spec_file` on `tasks.md` (keep the `content_version` for the manager's later write), `requirements.md`, `solution.md`, and the constitution. For OpenSpec bundles, tasks are `## N. Group` / `- [ ] N.M`; treat each `N.M` as a task with no declared dependencies and the group as its module.

## 1b. When the bundle has no tasks.md

A brownfield bundle is often just `proposal.md` and a requirements delta. There is nothing to derive waves from and no checkbox to mark, so put the choice to the user before any dispatch:

| Option | When it fits |
|---|---|
| One worker for the whole change | The proposal's Technical Solution is concrete and the requirement ids are testable. The brief carries both documents in full; the pull request title names the bundle instead of a task number |
| Author `tasks.md` first (`myspec-mcp:spec-authoring`), then plan waves | The change spans modules that can progress independently, or the user wants milestone gates |
| Split by module without a `tasks.md` | Only when the modules truly do not share files; say that the shared-fixture or contract work between them will not be checked until integration |

Record the choice in `.specs/<bundle>/factory-run.md`. With no `tasks.md`, "done" is the merged pull request plus the verification in `integrate`; say so rather than implying a checkbox was ticked.

## 2. Derive the board

| Status | Source of truth |
|---|---|
| done | `- [x]` in `tasks.md` on the platform |
| in flight | An open pull request or remote branch named `factory/<bundle>/task-<N>` (also accept `claude/`-prefixed branches whose title or body names `task N`) |
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
- **Branch-ownership plans** (`tasks.md` assigns directory ownership and chains tasks inside a branch): dispatch one worker per branch chain rather than one per task, with the ownership map and the do-not-touch list in every brief.

## 4. Output

```markdown
## Board
| Task | Title | Status | Deps | Requirements | PR / session |
|------|-------|--------|------|--------------|--------------|

## Wave 1 (N sessions, cost note)
| Task | Modules / files | Size | Brief ready |

## Waiting
| Task | Blocked by |

## Flags
- Tasks needing a split or clarification before dispatch
- Dependency cycles or unknown requirement ids (send to the `myspec-mcp:analyze` skill)
```

State the cost before the manager dispatches: number of sessions, sizes, and that parallel sessions share and multiply rate-limit consumption.
