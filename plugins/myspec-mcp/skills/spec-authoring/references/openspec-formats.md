# OpenSpec brownfield formats

MySpec's OpenSpec workflow writes documents compatible with the OpenSpec CLI and its `/opsx:*` slash commands. A change lives at `openspec/changes/<change-id>/` with:

| File | Required | Purpose |
|---|---|---|
| `proposal.md` | yes | Why, what changes, which capabilities receive deltas, impact |
| `specs/<capability>/spec.md` | one per capability named in the proposal | Delta against that capability's long-lived baseline `openspec/specs/<capability>/spec.md` |
| `design.md` | optional | Context, goals, decisions, risks |
| `tasks.md` | yes | Numbered task groups, one per capability |

`<change-id>` is lowercase kebab-case; `archive` is reserved. Deltas are merged into the baseline on sync or archive, and the change folder moves to `openspec/changes/archive/` on archive.

Platform upload note: `upload_spec_file` allows at most three directory levels below `openspec/`, so a new `openspec/changes/<id>/specs/<capability>/spec.md` (four levels) cannot be created through MCP. Upload proposal, design, and tasks (pass `file_type: "openspec-spec"` for `design.md`); keep new capability deltas local for the CLI; never flatten the path. A delta the webapp workflow already wrote can still be updated with `update_spec_file` (by `file_id`, or `project_id` plus `file_path`), because the depth rule only applies to creating files.

## Lifecycle (OpenSpec tooling, run locally)

The platform stores the change documents; the OpenSpec CLI and its `/opsx:*` slash commands in the repository drive the lifecycle. The plugin documents it and does not reimplement it.

| Step | Surface | Command | Effect |
|---|---|---|---|
| Propose | CLI or slash | `openspec new change <name>`, `/opsx:new`, `/opsx:propose`, or the MySpec webapp workflow | Creates `openspec/changes/<change-id>/` with proposal, deltas, optional design, tasks |
| Apply | slash | `/opsx:apply` (or the `implement` skill) | Works through `tasks.md`, checking boxes as tasks finish; mid-way pivots fix the artefact first, then continue |
| Verify | slash | `/opsx:verify` (or the `analyze` skill) | Completeness (tasks done), correctness (code matches deltas and design), coherence (artefacts agree) |
| Sync | slash | `/opsx:sync` | Merges the deltas into the baseline `openspec/specs/<capability>/spec.md`: ADDED appended, MODIFIED replaced in full, REMOVED deleted, RENAMED retitled; untouched content preserved |
| Archive | CLI | `openspec archive <change-id>` (`--yes` when run without a terminal; `--skip-specs` to skip the merge) | Validates, warns about unchecked tasks and asks for confirmation, merges deltas unless skipped, then moves the change to `openspec/changes/archive/YYYY-MM-DD-<change-id>/` |

Completion means: every task checked, verification passes, deltas merged into the baseline, change archived with a date. Keep the archived folder; it is the history.

## Capability names

A capability is named after the domain, module, or component it touches: a short, stable, reusable kebab-case noun such as `webapp`, `user-auth`, `onboarding`, `billing`. Never the change or feature (`add-session-rename` is wrong; `webapp` is right). At most three words or 25 characters. For modified capabilities, reuse the exact existing name. The list in the proposal is the contract: exactly one delta file per name.

## proposal.md

```markdown
## Why
2-5 sentences on the problem or motivation, referencing the concrete current state of the codebase.

## What Changes
- One concrete, observable change per bullet
- ...

## Capabilities
### New Capabilities
- `<domain-or-module-name>`: what this capability covers

### Modified Capabilities
- `<existing-domain-or-module-name>`: which existing requirement or behaviour in that module is changing

## Impact
Affected code, data, APIs, users, migrations, high-level risks; backward-incompatible changes.
```

An optional `# <Change title>` H1 may precede the sections. Omit an empty Capabilities subsection. No implementation steps (those go in tasks) and no detailed requirement text (that goes in the deltas).

## specs/<capability>/spec.md (delta)

Use the exact headers; include only those that apply.

```markdown
## ADDED Requirements

### Requirement: <Requirement name>
The system SHALL <required behaviour in clear, testable language>.

#### Scenario: <Scenario name>
- **WHEN** <triggering condition or action>
- **THEN** <expected, observable outcome>
- **AND** <additional outcome, if needed>

## MODIFIED Requirements

### Requirement: <Existing requirement name>
The system SHALL <the full post-change behaviour, not just the diff>.

#### Scenario: <Scenario name>
- **WHEN** <condition>
- **THEN** <outcome>

## REMOVED Requirements

### Requirement: <Requirement being removed>
State that it is removed and why (cross-reference the proposal's What Changes).

## RENAMED Requirements

- FROM: `### Requirement: <Old name>`
- TO: `### Requirement: <New name>`
```

Validator-enforced rules: every ADDED or MODIFIED requirement contains SHALL or MUST text and at least one `#### Scenario:` with `- **WHEN**` and `- **THEN**` bullets. RENAMED uses FROM/TO pairs wrapping backtick-quoted headers, never an arrow. One capability per file. Ground MODIFIED, REMOVED, and RENAMED entries in real current behaviour.

## design.md (optional)

```markdown
## Context
Relevant current state of the codebase (modules, data flow, constraints) the change operates within.

## Goals / Non-Goals
**Goals:**
- What this change must achieve.

**Non-Goals:**
- What is explicitly out of scope.

## Decisions
- **Decision**: <what>. Rationale: <why>. Alternatives: <what was rejected>.

## Risks / Trade-offs
- **Risk / Trade-off**: <what>. Mitigation: <how>.
```

Write it when the change has non-trivial technical decisions; keep it brief otherwise. Do not introduce capabilities the proposal did not name.

## tasks.md

```markdown
## 1. <Capability one>
- [ ] 1.1 <First concrete, verifiable task>
- [ ] 1.2 <Next task>

## 2. <Capability two>
- [ ] 2.1 <Task>
```

Numbered groups `## N. Name`, one per capability named in the proposal; `- [ ] N.M` tasks, all unchecked when written. Planning level only.
