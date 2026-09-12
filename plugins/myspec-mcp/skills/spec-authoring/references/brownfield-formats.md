# MySpec brownfield formats

A MySpec brownfield bundle describes a change to an existing product. It lives at `specs/<bundle>/` and contains `proposal.md`, a requirements delta in `requirements.md`, and optionally `tasks.md` (same milestone format as greenfield, see `../../implement/references/tasks-format.md`, with `_Requirements:_` citing AR/BR/CR ids).

Every claim must be grounded in code or docs you actually read. Do not invent files, modules, dependencies, or behaviour.

## proposal.md

The H1 is `# Change Proposal: [Project Name]` for a wide-scope change or `# Change Request: [Project Name]` for a change isolated to one module. Four sections, in order:

```markdown
# Change Proposal: [Project Name]

## Why
2-5 sentences: the problem or motivation, referencing the concrete current state of the codebase (current behaviour, modules and files involved). Describe what is changing and why now, not a greenfield build.

## What Changes
- One concrete, observable change per bullet (new behaviour, modified behaviour, removals)
- ...

## Technical Solution
Concrete technical detail an engineer needs before writing requirements or code. State explicitly when a subsection does not apply ("No library changes.") rather than omitting it.

### Library/Framework Changes
New dependencies, version bumps, or replacements, and why the current one is insufficient.

### Core Flow Changes
Fundamental changes to a request or data flow, with a Mermaid sequence or flow diagram showing before and after (or the new flow).

### Data Model / DB Schema Changes
New, changed, or removed tables, columns, indexes, relationships, with a Mermaid `erDiagram` of the affected entities.

### API Breaking Changes
Any change to a public API's request/response shape, route, auth requirement, or removal. Write "No breaking API changes." if none.

## Impact
Who and what is affected: existing code, data, APIs, users, migrations, high-level risks. Note backward-incompatible changes.
```

Rules: keep it a proposal. The full requirement text lives in `requirements.md` and the task breakdown in `tasks.md`. Every Mermaid diagram must be valid. No metadata footer.

## requirements.md (delta)

```markdown
# Requirements Delta: [Project Name]

## Overview
Brief description of what this delta covers.

## Impacted User Roles
- Role 1: Description

## [Module Name / Capability Name]

### AR-001: [Added Feature Name]
**Description:** What the system must do.
**User Role:** Which role(s) this applies to.
**Acceptance Criteria:**
- WHEN [event] THEN the system SHALL [response]

### BR-001: [Name of the original requirement being removed]
**Description:** Why this requirement is removed.
**Reference:** [file_path]:[line-no]

### CR-001: [Name of the original requirement being changed]
**Description:** What changes in this requirement and why.
**User Role:** Which role(s) this applies to (may include new roles).
**Acceptance Criteria:**
- ~~WHEN [old event] THEN the system SHALL [old response]~~
- WHEN [event] THEN the system SHALL [new response]
```

Id contract:

| Prefix | Meaning | Shape |
|---|---|---|
| `AR-NNN` | Add Requirement: brand new | Description, User Role, EARS+ acceptance criteria |
| `BR-NNN` | Remove Requirement: existing requirement made obsolete | Description plus `**Reference:** file:line` to the code or doc that describes the original. No acceptance criteria |
| `CR-NNN` | Change Requirement: existing behaviour changes | Each changed criterion reproduced with `~~strikethrough~~` immediately followed by its replacement. Unchanged criteria are not repeated. A CR may add a new criterion for a new role without striking anything |

- Group entries under one `## [Module]` section per impacted module, using the same module names the proposal's Technical Solution used. Do not interleave modules.
- Within a module, AR, BR, and CR each number independently from 001.
- Acceptance criteria follow the EARS+ patterns in `requirements-format.md`: technology-neutral, testable. Generated files prefix each criterion with `AC1:`, `AC2:` (also inside the `~~strikethrough~~`); both the prefixed and bare forms are accepted.
- An optional final `## Requirement Diagram` section (one Mermaid `requirementDiagram`) is not a module section; codes inside it are references. Only add it when asked.
- No metadata footers.

## Examples

```markdown
### AR-001: Token refresh endpoint
**Description:** Allow a client to exchange a valid refresh token for a new access token.
**User Role:** End user.
**Acceptance Criteria:**
- WHEN a valid, unexpired refresh token is submitted THEN the system SHALL return a new 15-minute access token
- IF the refresh token is expired or revoked THEN the system SHALL return 401 and require re-login

### CR-001: Suspended Account Handling
**Description:** Suspended accounts are now rejected at the auth middleware, not only at login.
**User Role:** Admin, End user.
**Acceptance Criteria:**
- ~~WHEN a suspended user logs in THEN the system SHALL reject the login~~
- WHEN any authenticated request arrives from a suspended account THEN the system SHALL reject it with 403
```
