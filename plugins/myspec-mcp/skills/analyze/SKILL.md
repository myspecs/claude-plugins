---
name: analyze
description: Read-only verification of a MySpec specification bundle. Use when the user asks to analyze, verify, audit, review, or check a spec bundle for consistency; wants requirement-to-task coverage or traceability; asks whether the code matches the spec, what is missing or drifted, or "are we converged"; or before starting implementation and at milestone checkpoints. Reports findings with severities and never edits anything unless the user approves a remediation. Requires the myspec MCP server (see the setup skill).
user-invocable: false
---

# Analyze a MySpec bundle

Tools are called as `mcp__plugin_myspec-mcp_myspec__<tool>`. Checks and scoring live in `references/checks.md`; the rules behind them in `../implement/references/sdd-principles.md`.

This skill only reads. It produces a findings table and, when asked, a remediation plan. It never writes to the platform or the repo until the user approves a specific remediation, and gap-filling is append-only.

## Modes

| Mode | Question it answers | Inputs |
|---|---|---|
| Spec consistency | Are the documents complete, unambiguous, and consistent with each other? | The bundle only |
| Convergence | Does the code implement what the spec says, and only that? | The bundle plus the repository |

Pick spec consistency before implementation starts or after spec edits. Pick convergence at milestone checkpoints, when resuming a repo whose checkboxes look wrong, or when the user asks "does the code match the spec".

## Procedure

1. Locate the project and bundle as in the `implement` skill (managed block in `CLAUDE.md` or `AGENTS.md`, else `list_projects` and `list_spec_file`). Read every document of the bundle with `read_spec_file`.
2. Build an inventory: requirement ids (FR/NFR, AR/BR/CR, or OpenSpec `### Requirement:` names) with their acceptance criteria; tasks with number, status, `_Dependencies:_`, `_Requirements:_`, `_Complexity:_`; constitution constraints as a checklist.
3. Run the checks for the chosen mode from `references/checks.md`. For convergence, inspect the repository (grep for requirement ids in tests, read the modules `solution.md` names, run the test suite if the user allows) and classify every requirement as implemented, partial, missing, contradicts, or unrequested.
4. Score coverage: percentage of requirements with at least one task, and (convergence) percentage with at least one passing test that names them.
5. Report in this shape:

```markdown
## Findings
| ID | Severity | Category | Location | Finding | Recommendation |
|----|----------|----------|----------|---------|----------------|
| A1 | CRITICAL | constitution | solution.md Technology Stack | Uses Redis; constitution allows PostgreSQL only | Replace or amend constitution |

## Coverage
| Requirement | Tasks | Tests (convergence) | Status |
|-------------|-------|---------------------|--------|
| FR-001 | 2, 3 | 2 passing | implemented |

Coverage: 18/20 requirements have tasks (90%). Uncovered: FR-014, NFR-003.
```

Severity: CRITICAL for constitution conflicts, uncovered functional requirements, and contradictions between code and spec; HIGH for missing acceptance criteria, dependency cycles, tasks that reference unknown requirements; MEDIUM for ambiguity, duplicates, oversized tasks; LOW for style and ordering.

6. Stop. Ask whether the user wants remediation. Only then:
   - Spec fixes: edit the document through the write-back protocol (`../implement/references/write-back-protocol.md`) or hand to `spec-authoring`.
   - Missing or partial implementation, MySpec format: append a `## Milestone N: Convergence` section to `tasks.md` before `## Dependency Graph`, with N continuing the milestone numbering and task numbers continuing after the highest existing task, in the standard format citing the affected requirement ids. OpenSpec format: append a `## N. Convergence` group with `- [ ] N.M` tasks. No `tasks.md` in the bundle: propose creating one through `spec-authoring`. Never edit or renumber existing tasks. If everything is converged, leave `tasks.md` untouched and say so.
   - Unrequested behaviour: propose either a new requirement (spec-authoring) or removal; do not decide alone.

## Limits

- Do not mark tasks done during analysis; that belongs to `implement`.
- Do not run destructive commands; test runs only with the user's consent.
- If the bundle has no `tasks.md`, report coverage against requirements only and say the tasks document is missing.
