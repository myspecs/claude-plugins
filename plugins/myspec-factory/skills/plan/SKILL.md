---
name: plan
description: Build or refresh the factory team plan from a MySpec tasks.md, or write the tasks.md a brownfield bundle lacks. Use when the user says "plan the factory run", "what can run in parallel", "how many agents do we need", "divide the tasks between the agents", "which tasks are ready", "plan the tasks for this proposal", or before starting the team. Derives the task board from platform checkboxes and open pull requests, groups related tasks (dependency chains, shared files or modules, the same requirement) into assignments, weighs them by complexity, and divides them evenly between the team's agents; when the bundle has no tasks.md, writes the task list for the change and uploads it only after the user approves it.
user-invocable: false
---

# Factory plan

Tools are called as `mcp__plugin_myspec-mcp_myspec__<tool>`. Task grammar and the write-back rules are in the `myspec-mcp:implement` skill's references. This skill only reads, except for uploading an approved `tasks.md` in step 1b.

## 0. Verify bundle completion

Before planning or starting the team, verify that the bundle's generate session is completed. Use `get_spec_session` with the session ID from the bundle metadata to check its status. If the session status is not `completed`, stop immediately and tell the user that the factory cannot start while the spec bundle is still being generated or edited on the MySpec platform. The user must complete their generate/edit session before factory agents can start. Only proceed to load the bundle and plan the team when the session status is `completed`.

## 1. Load the bundle

Locate project and bundle (the project from the managed `<!-- myspec-mcp:start -->` block in `CLAUDE.md`, else `list_projects`; the bundle from `list_spec_file`). `list_spec_file` first to see which documents the bundle has; the set depends on the workflow (greenfield: constitution, requirements, solution, tasks; MySpec brownfield: proposal, requirements delta, and `tasks.md` only in some workflows; OpenSpec: proposal, spec deltas, optional design, tasks). `get_spec_file` and `read_spec_file` on each: `tasks.md` when present (keep the `content_version` for the manager's later write), then the requirements, the design (`solution.md`, or the proposal and `design.md`), and the constitution when present. No `tasks.md` in a brownfield bundle is expected: go to 1b. For OpenSpec bundles, tasks are `## N. Group` / `- [ ] N.M`; treat each `N.M` as a task with no declared dependencies and the group as its module.

## 1b. When the bundle has no tasks.md: write it

A MySpec brownfield bundle may be only `proposal.md` and a requirements delta; `tasks.md` is optional there. The manager then writes the task list itself. Nothing is assigned until the user approves the list and it is on MySpec.

1. Pass the spec gate on the documents that exist (complete, every doubt clarified) before planning. A task list built on an unfinished proposal is unfinished too.
2. Map the change. From the proposal's Technical Solution and Impact, the requirements delta, and the repository itself, list every area the change touches: modules, directories, files, migrations, shared contracts (API shapes, event payloads, types, table columns, error strings), configuration, dependency manifests and lockfiles.
3. Cut it into tasks that the team can share: each task names the files it touches in its implementation details (that is what §3's grouping and the division read), carries its own acceptance criteria, and depends only on what it really needs. Keep independent areas in separate tasks without `_Dependencies:_` between them, so they can go to different agents; put a contract several areas share in one early task (a contract freeze, `§3b`) with its full text (every field, name, unit and error value), so the tasks after it code against the text. A shared file (migration sequence, route or DI registry, dependency manifest, lockfile) is touched by as few tasks as possible. Never split only to give more agents work; a small change is a few tasks for one agent.
4. Write `tasks.md` in the MySpec brownfield format with the `myspec-mcp:spec-authoring` skill (grammar in the `myspec-mcp:implement` skill's `references/tasks-format.md`): H1 `# Implementation Tasks: [Change Name]`, the brownfield milestones, document-wide numbering, and for each task implementation details naming the files it touches, `Acceptance Criteria:`, `_Dependencies:_`, `_Requirements:_` (AR/BR/CR ids), `_Complexity:_` (Small, Medium or Large: the division weighs by it). Every AR/BR/CR id appears in at least one task. `## Dependency Graph` closes the file. Do not write a `## Branch Plan`: which agent does what is a run-time plan, kept in the registry and on the board, not in the spec.
5. Show the user the draft with its groups and a proposed team (§3-§4), then ask for approval with `AskUserQuestion` (approve, or change). Apply every change they ask for; do not upload before they approve. Draft large task lists with a subagent into `.specs/<bundle>/draft/` and run the self-checks in the `integrate` skill's §4c before showing them.
6. Upload with `upload_spec_file` (`file_path` `specs/<bundle>/tasks.md`, `file_type` `tasks`), then `get_spec_file` for its `content_version`. Note in `.specs/<bundle>/factory-run.md` that the manager authored it and the user approved it.
7. Re-run the spec gate on the whole bundle, now including `tasks.md`. Then plan the team as for any bundle (§2-§4).

A `tasks.md` with a `## Branch Plan` (written by myspec-factory 1.x) keeps it: each lane is one group (`dispatch` §0); nothing new is written into that section.

## 2. Derive the task board

Read statuses with `list_tasks` (`file_id` the bundle's `tasks.md`; `[ ]` pending, `[-]` in progress, `[x]` done), or from the file when the task board is off. A `[-]` task with no registry assignment was started by someone outside the run: leave it out of the groups and ask the user.

| Status | Source of truth |
|---|---|
| done | `- [x]` in `tasks.md` on the platform (`list_tasks` status `done`) |
| in flight | An open pull request or remote branch named `factory/<bundle>/task-<N>` or `factory/<bundle>/tasks-<N1>-<N2>-…` listing N; a pull request titled `task N1, N2, …:` whose list holds N (also accept `claude/`-prefixed branches whose title or body names task N); an assignment in the registry with status `running` or `pushed` that carries N; a task `[-]` (`in_progress`) set by an agent's assignment; and from a 1.x run, `factory/<bundle>/lane-<L>` or a `lane L:` title for a lane listing N in `## Branch Plan` |
| blocked | A pull request labelled `blocked`, or whose `## Factory report` says `BLOCKED` |
| queued | `- [ ]`, not in flight, planned in an agent's `queue` in the registry |
| ready | `- [ ]`, not in flight, every `_Dependencies:_` number done |
| waiting | `- [ ]` with an unmet dependency |

Use `gh pr list --state open --json number,title,headRefName,labels,statusCheckRollup` and `git ls-remote --heads origin 'factory/*'`. Never store the task board as truth; a stored copy is a cache.

## 3. Group, weigh and divide

1. Take every not-done task of the current milestone that is not in flight. Ready tasks start groups; a waiting task joins the group of the tasks it waits on when they can all be done by one agent without waiting for a merge.
2. For each, list the solution modules and likely files: the `_Requirements:_` ids map to modules in `solution.md`; the task's implementation details name files.
3. Group them with the rules in the `dispatch` skill's §0: a dependency chain, tasks that share a module or file, and tasks for the same requirement or feature go to one group (one assignment, one branch, one pull request). Tasks that share a module or file are never in two groups. A task gets a group of its own only when nothing relates to it. Groups stay inside the current milestone and inside any split `tasks.md` declares. Weigh each group (`dispatch` §0: Small 1, Medium 2, Large 3).
4. Propose the team size: how many groups can run at the same time (no unmerged dependency between them), never more than the work fills, and say why (`dispatch` §0b). The user decides `policy.team_size`.
5. Divide the groups between the agents with the `dispatch` skill's §0b (chain affinity, then least load) and give each agent its rung (the highest of its groups).
6. Mark tasks the constitution or task text calls Large as single-assignment candidates only if their acceptance criteria are precise; otherwise flag them for splitting before any assignment.

On every later refresh (a merge, an idle agent, a spec change), re-derive the task board and compare it with the queues in the registry: drop finished or vanished groups, add new tasks (convergence follow-ups, fix tasks) to the least-loaded agent's queue, and rebalance as `dispatch` §0b says.

## 3b. Task shapes that change the plan

- **Decision tasks** ("resolve the open questions", "confirm scope"): the answer belongs to the user and usually edits `requirements.md`. The manager resolves them with the user, records the decisions as Clarifications, marks the task `[x]`, and assigns nothing for it — an agent may not edit spec files.
- **Contract freeze tasks** (shared types, stub routes, event kinds frozen before parallel branches start): assign them first, so the other agents' groups can start once they merge. Check the freeze is complete before merging it — request bodies as well as responses, list response wrappers, internal events and RPC or subject names the branches exchange, error `reason` strings, and the unit of any offset or length (bytes, code points, UTF-16). Drift tests must fail in BOTH directions. Anything left out becomes an unfrozen coupling the manager has to relay by hand.
- **Branch-ownership plans** (`tasks.md` assigns directory ownership and chains tasks inside a branch, or a 1.x `## Branch Plan`): each branch chain is one group, with the ownership map and the do-not-touch list in its assignment message.

## 4. Output

```markdown
## Task board
| Task | Title | Status | Deps | Requirements | Agent / assignment / PR |
|------|-------|--------|------|--------------|-------------------------|

## Team (N agents, cost note)
| Agent | Rung | Now | Queue (in order) | Weight | Why |
|-------|------|-----|------------------|--------|-----|

## Groups
| Group | Tasks (in order) | Why grouped | Modules / files | Weight | Rung | Agent |

## Waiting
| Task | Blocked by |

## Spec gate blockers (nothing is assigned until every item is resolved)
- Tasks needing a split or clarification
- Dependency cycles or unknown requirement ids (send to the `myspec-mcp:analyze` skill)
- Missing documents, a spec session still running, `TBD`/placeholder text, open questions, CRITICAL or HIGH analyze findings
```

Fill `Rung` from the ladder in the `dispatch` skill's `references/model-and-effort.md`, with a short reason for any agent not on `opus`/`medium`. `Now` is the agent's open assignment (`a1-2: tasks 4, 5`), or `idle`. State the cost before the manager starts the team: number of agents, each queue's weight, model and effort, and that parallel sessions share and multiply rate-limit consumption.
