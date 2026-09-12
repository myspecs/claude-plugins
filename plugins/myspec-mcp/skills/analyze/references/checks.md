# Analysis checks

Weights follow the MySpec platform's own tasks reviewer: requirements coverage 30%, task quality 25%, dependencies 20%, sizing 15%, organisation 10%. Any functional requirement without a task is a must-fix.

## Spec consistency mode

### Constitution alignment (CRITICAL on conflict)
- Solution Technology Stack and every task use only technologies the constitution allows (and none it forbids).
- Architecture, testing approach, coding standards, and security constraints are reflected in solution.md and the tasks, not contradicted.
- All nine constitution sections present, in order; `N/A` is acceptable, silence is not.

### Requirements quality
- Every FR has at least one acceptance criterion in an EARS+ pattern; every NFR has a measurable `**Target:**` and a `**Priority:**` (HIGH when missing).
- Requirements are technology-neutral; a requirement that names a product or pattern belongs in solution.md (MEDIUM).
- Ambiguity: vague quantifiers ("fast", "all", "as needed"), unresolved placeholders, criteria without an observable outcome (MEDIUM).
- Duplicates or contradictions between requirements (HIGH when contradictory, MEDIUM when duplicated).
- Brownfield deltas: BR entries carry a real `Reference: file:line`; CR entries show struck-through old criteria above replacements; AR/BR/CR numbering restarts per module.
- OpenSpec deltas: exact `## ADDED|MODIFIED|REMOVED|RENAMED Requirements` headers; every ADDED/MODIFIED requirement has SHALL/MUST text and a `#### Scenario:` with WHEN/THEN; one capability per file; capability names match the proposal's list exactly.

### Solution completeness
- Every FR is addressed by at least one module or API in solution.md (HIGH when not).
- Every measurable NFR has a row in Success Criteria (MEDIUM).
- Mermaid `flowchart` and `erDiagram` present; `sequenceDiagram` when three or more modules (LOW).
- Key decisions carry rationale and alternatives (LOW).

### Task coverage and quality (coverage 30%, quality 25%)
- Every FR appears on at least one task's `_Requirements:_` line (CRITICAL when not). NFRs appear on relevant tasks (MEDIUM).
- Every `_Requirements:_` id exists in requirements.md (HIGH when unknown).
- Every task has acceptance criteria, implementation detail, and the three annotation lines with values inside the italics; task lines use `- [ ] N\. Title` (MEDIUM).
- Tasks use the components, APIs, and data models named in solution.md (MEDIUM).

### Dependencies (20%)
- Every `_Dependencies:_` number exists; no cycles; no task depends on a later milestone without reason (HIGH).
- Foundational tasks precede the tasks that need them; the critical path is stated in `## Dependency Graph` (LOW).

### Sizing and organisation (15% + 10%)
- Complexity values are Small, Medium, or Large; nothing implies more than five days (MEDIUM).
- Milestones are outcome-named `## Milestone N: Name`, numbering is document-wide, `## Dependency Graph` closes the file (LOW).

## Convergence mode

Classify each requirement after reading the modules solution.md names and searching tests for requirement ids. Test names normalise the id (`FR-003`, `fr_003`, `FR003`), so search case-insensitively with the separator optional, for example `grep -riE 'FR[-_]?003' <test dirs>`:

| Status | Meaning |
|---|---|
| implemented | Behaviour present and at least one passing test names the requirement or criterion |
| partial | Some criteria implemented or tested, others not |
| missing | No implementation found |
| contradicts | Code does something the criterion forbids, or the constitution forbids (CRITICAL) |
| unrequested | Behaviour or module in the code with no requirement or task (MEDIUM; may be legitimate) |

Also check:
- Checkbox drift: tasks marked `[x]` whose acceptance criteria are not met, or unchecked tasks whose work exists (HIGH). Report; do not flip boxes.
- Test traceability: percentage of criteria with a test whose name carries the requirement id.
- Constitution drift: dependencies added, patterns introduced, or standards broken since the spec was approved (CRITICAL when forbidden).

Remediation for missing or partial items is append-only. MySpec format: a `## Milestone N: Convergence` section before `## Dependency Graph`, task numbers continuing after the highest existing one, one task per gap in the standard format, each citing the requirement ids and sized Small or Medium. OpenSpec format: a `## N. Convergence` group with `- [ ] N.M` tasks. Existing tasks are never edited or renumbered.
