---
name: plan
description: Build or refresh the factory wave plan from a MySpec tasks.md. Use when the user says "plan the factory run", "what can run in parallel", "build the waves", "which tasks are ready", or before dispatching workers. Read-only; derives the board from platform checkboxes and open pull requests, then groups ready tasks into waves of non-overlapping work.
---

# Factory plan

Tools are called as `mcp__plugin_myspec-mcp_myspec__<tool>`. Task grammar and the write-back rules are in the `myspec-mcp:implement` skill's references; this skill only reads.

## 1. Load the bundle

Locate project and bundle (managed `<!-- myspec:start -->` block in `CLAUDE.md`, else `list_projects` and `list_spec_file`). `get_spec_file` and `read_spec_file` on `tasks.md` (keep the `content_version` for the manager's later write), `requirements.md`, `solution.md`, and the constitution. For OpenSpec bundles, tasks are `## N. Group` / `- [ ] N.M`; treat each `N.M` as a task with no declared dependencies and the group as its module.

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
