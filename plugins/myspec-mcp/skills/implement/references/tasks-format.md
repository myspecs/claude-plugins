# tasks.md formats

MySpec produces task lists in four shapes (MySpec, enterprise, Spec Kit, OpenSpec), all GitHub-flavoured Markdown task lists. The platform **parses** every checkbox in a `tasks` file into its task board (`list_tasks`) and **writes** them (`set_task_status`, the webapp board): `[ ]` pending, `[-]` in progress, `[x]` done. Each task gets a stable `task_id` that survives edits to its text; planning fields (assignee, priority, labels, cycle, dates, relationships) live on the board, not in the file. The file stays the source of truth for status and text.

What the parser counts as a task: a checkbox bullet (`-`, `*`, `+`, `1.` or `1)`) outside fenced code blocks and front matter, keyed `1\.` (MySpec), `1.1` (OpenSpec) or `T001` (Spec Kit). A nested checkbox becomes a child task. At most 2000 tasks per file. Any other checkbox line you add (a checklist in a note, a copied task list) becomes a board task too, so never write checkboxes except the task lines themselves.

## MySpec format (greenfield and MySpec brownfield)

Produced by the MySpec generate workflows. Skeleton:

```markdown
# Implementation Tasks: [Project Name]

## Overview
Brief summary of task breakdown approach and total task count.

## Milestone 1: [Name]

- [ ] 1\. [Task Title]
  - Implementation detail 1
  - Implementation detail 2
  - Acceptance Criteria:
    - Testable criterion 1
    - Testable criterion 2
  - _Dependencies: none_
  - _Requirements: FR-001, NFR-001_
  - _Complexity: Small/Medium/Large_

- [ ] 2\. [Task Title]
  - ...
  - _Dependencies: 1_
  - _Requirements: FR-002_
  - _Complexity: Medium_

## Milestone 2: [Name]
...

## Dependency Graph
Summary of critical path and parallelization opportunities.
```

Grammar:

- Milestone heading: `## Milestone N: Name`. Numbering is document-wide; task numbers do not restart per milestone.
- Task line: `- [ ] N\. Title`. The backslash before the period is deliberate (it stops Markdown from rendering an ordered list). Keep it when editing. A parser must accept `N\.` and plain `N.`.
- Sub-bullets (two-space indent): free-text implementation details, an `Acceptance Criteria:` bullet with nested criteria, then exactly these annotation lines with the value inside the italics:
  - `_Dependencies: none_` or `_Dependencies: 1, 3_` (bare task numbers)
  - `_Requirements: FR-001, NFR-002_` (greenfield) or, for a brownfield delta, `_Requirements: AR-XX-001, CR-YY-002_` where `XX`/`YY` abbreviate the module. Both shapes are current: `tasks.md` cites `AR-XX-001`, while `requirements.md` numbers `AR-001` per `## [Module]` section. Parse loosely and match on the trailing number plus module.
  - `_Complexity: Small_`, `Medium`, or `Large` (Small up to 4 hours, Medium 1-2 days, Large more than 2 days)
  - Optional `_Estimate: 1.5 man-days_` (added when the author role is project manager); tolerate, never require.
- Optional trailing sections produced for some roles: `## Milestone N: QA Verification` (continues numbering, placed before `## Dependency Graph`) and `## Delivery Timeline` (Mermaid gantt).
- Closing section: `## Dependency Graph`.

Recommended milestone order in generated greenfield files: Infrastructure, Core Features, Supporting Features, Integration, Testing, Documentation, Deployment. Brownfield tasks files use the H1 `# Implementation Tasks: [Change Name]` and the milestones Foundation & Prerequisites, Core Changes, Supporting Changes, Integration, Testing, Documentation & Deployment; the task grammar is identical.

## Enterprise format (`enterprise-greenfield-v1`)

The MySpec format plus two annotation lines per task, after `_Complexity:_`:

```markdown
  - _Verification: unit test — an expired token is rejected; integration test_
  - _Quality Gate: G1_
```

`_Verification:_` names how completion is proven (for risky logic, the test that fails if it breaks); `_Quality Gate:_` names the gate in `quality.md` (`file_type` `quality`) the task must pass, or `none`. The Testing milestone is called "Testing & Verification". Treat the verification line as an extra acceptance criterion.

## Spec Kit format (`speckit-greenfield-v1`)

```markdown
## Phase 1: Setup (Shared Infrastructure)
- [ ] T001 Create project structure per plan.md (file: repo root)
- [ ] T003 [P] Configure linting and formatting tools (file: .eslintrc.json)

## Phase 3: User Story 1 - <Title> (Priority: P1)
- [ ] T007 [P] [US1] Create <Entity1> model (file: src/models/entity1.ts)
```

Grammar: phases in fixed order (Setup, Foundational, one per user story by priority, Polish), each user-story phase with a Goal, an Independent Test and a closing `**Checkpoint**:` line. Task ids `T001…`; `[P]` marks a task that can run in parallel with its phase peers (different file, no dependency); `[US1]` ties a task to a user story; `(file: …)` names the files. No `_Dependencies:_` lines: a phase depends on the phases before it, and inside a phase tasks without `[P]` run in order.

## OpenSpec format (`openspec/changes/<id>/tasks.md`)

```markdown
## 1. <Capability one>
- [ ] 1.1 <First concrete, verifiable task>
- [ ] 1.2 <Next task>

## 2. <Capability two>
- [ ] 2.1 <Task>
```

Grammar: numbered groups `## N. Name` (one per capability named in the proposal) and `- [ ] N.M Task` lines. No annotation lines, no escaped period, no dependency graph. "Next task" is simply the first unchecked box in document order.

## Status convention

| Marker | Status | Meaning |
|---|---|---|
| `- [ ]` | `pending` | Not started |
| `- [-]` | `in_progress` | Someone is working on it (the webapp shows a half-filled box) |
| `- [x]` | `done` | Implemented, acceptance criteria verified, written back |

Change a status with `set_task_status` (`write-back-protocol.md` § Task status), which rewrites only the marker. Use no other markers (`[~]`, `[P]` as a status, emoji). The generators keep existing `[x]` and `[-]` markers when they revise a tasks file, so progress survives a spec edit.

## Plugin conventions the platform tolerates

These are written by this plugin, never generated by MySpec. They are indented sub-bullets (shown as the task's details on the board) or trailing sections, so the platform's template, parser and reviewers accept them. None of them is a checkbox.

| Convention | Where | Shape |
|---|---|---|
| Clarification recorded for a task | Indented under the task, after the annotation lines | `  - Clarification: <question>: <answer>` |
| Partial progress, when the task stays `[-]` across sessions | Indented under the task | `  - Progress: <what is done, what is left>` |
| Merge record written by the factory manager | Indented under the task | `  - Merged: PR #<n> (<short sha>)` |
| Convergence tasks added by `analyze` | New `## Milestone N: Convergence` before `## Dependency Graph`, N continuing document numbering | Standard task format, each citing the requirement ids it closes |
| Branch plan (written by myspec-factory 1.x; read, never written now) | `## Branch Plan` just before `## Dependency Graph` | One `### Lane L: <name>` per lane with `Branch:`, `Tasks (in order):`, `Owns:`, `Does not touch:`, `Shared contracts:` bullets, no checkboxes |
| Requirement-level clarifications | `requirements.md`, final section | `## Clarifications` with `- FR-001: <question>: <answer>` bullets |

## Choosing the next task (MySpec format)

1. Walk tasks in document order.
2. Skip any task already `[x]`. A `[-]` task is taken unless it is assigned to you **and** carries no `agent:<name>` label: skip it when it has another assignee or an `agent:` label (a Software Factory agent is building it, under the account that runs the factory). An unassigned `[-]` task without a label was started by someone who did not claim it: ask the user before resuming it.
3. For each remaining task, read `_Dependencies:_`. If it is `none` or every listed number is `[x]`, this is the next task. A board relationship `blocked_by` a task that is not done blocks it too.
4. If nothing qualifies but open tasks remain, the dependency lines are inconsistent; show the user the blocked tasks and ask.

Spec Kit: the first open task of the earliest phase whose earlier phases are done. OpenSpec: the first unchecked box.

## Requirement id families

| Prefix | Document | Meaning |
|---|---|---|
| `FR-001` | requirements.md (greenfield) | Functional requirement |
| `NFR-001` | requirements.md (greenfield) | Non-functional requirement with a measurable target |
| `AR-001` | requirements.md (MySpec brownfield delta) | Added requirement |
| `BR-001` | requirements.md (MySpec brownfield delta) | Removed requirement (no acceptance criteria; has a file:line reference) |
| `CR-001` | requirements.md (MySpec brownfield delta) | Changed requirement (old criteria struck through above the new ones) |

Delta ids restart at 001 inside each `## [Module]` section, so cite them together with the module name when reporting.
