# requirements.md format (greenfield)

Requirements say what the system must do and how well, never how it is built. Technology and architecture belong in `solution.md`.

## Skeleton

```markdown
# Requirements Specification: [Project Name]

## Overview
Brief description of what this requirements document covers.

## User Roles
- Role 1: Description

## Functional Requirements

### FR-001: [Feature Name]
**Description:** What the system must do.
**User Role:** Which role(s) this applies to.
**Acceptance Criteria:**
- WHEN [event] THEN the system SHALL [response]

## Non-Functional Requirements

### NFR-001: [Category, e.g. Performance]
**Description:** What quality attribute must be met.
**Target:** Measurable target (e.g. "Response time < 200ms at the 95th percentile")
**Priority:** High/Medium/Low

## Data Requirements
<!-- at most 5 bullets -->
- Key data entities and ownership
- Retention / privacy / compliance constraints
- Fields requiring encryption

## Integration Requirements
<!-- at most 5 bullets -->
- External systems / APIs to integrate with
- Data exchange formats and protocols
- API authentication mechanism
```

## Ids

- Functional: `### FR-001: Title`, `FR-002`, ... (three digits, zero padded, document-wide).
- Non-functional: `### NFR-001: Category`.
- Acceptance criteria are bullets under `**Acceptance Criteria:**`. Generated files sometimes prefix them `AC1:`, `AC2:`; both forms are accepted. Prefer the bare EARS+ form.

## EARS (requirement statements)

| Pattern | Keyword | Template |
|---|---|---|
| Ubiquitous | none | `The <system> SHALL <response>` |
| State-driven | `WHILE` | `WHILE <state>, the <system> SHALL <response>` |
| Event-driven | `WHEN` | `WHEN <trigger>, the <system> SHALL <response>` |
| Optional feature | `WHERE` | `WHERE <feature included>, the <system> SHALL <response>` |
| Unwanted behaviour | `IF ... THEN` | `IF <unwanted condition>, THEN the <system> SHALL <response>` |
| Complex | combined | `WHILE <state>, WHEN <trigger>, the <system> SHALL <response>` |

## EARS+ (acceptance criteria)

| Pattern | Template |
|---|---|
| Simple event | `WHEN <event> THEN <system> SHALL <response>` |
| Event with condition | `WHEN <event> AND <condition> THEN <system> SHALL <response>` |
| State-based | `WHILE <state> THEN <system> SHALL <response>` |
| Error handling | `IF <pre-condition> THEN <system> SHALL <response>` |
| Conditional event | `IF <pre-condition> WHEN <event> THEN <system> SHALL <response>` |

## Examples

```markdown
### FR-001: User Authentication
**Description:** Authenticated access to the application.
**User Role:** End user.
**Acceptance Criteria:**
- WHEN valid credentials are submitted THEN the system SHALL grant access and redirect to the dashboard
- IF invalid credentials are entered THEN the system SHALL display "Invalid username or password"
- WHEN 5 failed attempts occur within 15 minutes THEN the system SHALL lock the account for 30 minutes

### FR-002: Product Search
**Description:** Find products by free-text query.
**User Role:** Shopper.
**Acceptance Criteria:**
- WHEN a search query is submitted THEN the system SHALL return matching products within 2 seconds
- WHEN no results are found THEN the system SHALL display "No products found" AND suggest related categories
- WHERE autocomplete is enabled THEN the system SHALL show suggestions after 3 characters are typed

### NFR-001: Performance
**Description:** The application stays responsive under normal load.
**Target:** Page loads within 3 seconds on standard broadband; 1000 concurrent users without degradation.
**Priority:** High
```

## Rules the platform reviewer checks

- Technology-neutral: describe what, not how. No architectural patterns, no product names.
- Every FR has testable acceptance criteria; every NFR has a measurable target and a priority.
- Must not contradict the constitution.
- Data Requirements and Integration Requirements at most five bullets each; omit a section that does not apply.
- No metadata footers.

Writing tips (not reviewer-enforced): cover error and unwanted-behaviour cases with `IF ... THEN`, they are the most often skipped; replace universal quantifiers ("all", "any", "never") with specific entities and conditions; split a criterion that needs more than three preconditions.

Optional role-specific addition: a `## Requirement Diagrams` section (Mermaid `requirementDiagram`) placed after Non-Functional Requirements and before Data Requirements. Node names replace the hyphen with an underscore (`FR_001`) and carry `id: "FR-001"` inside the body. Only add it when asked.
