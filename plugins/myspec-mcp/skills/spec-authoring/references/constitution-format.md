# constitution.md format

The constitution is the project's ground rules. Everything downstream must comply with it, so keep it short and only include constraints the user actually decided.

## Skeleton (all nine sections, in this order)

```markdown
# Project Constitution: [Project Name]

## Project Vision
A brief statement of the problem being solved, the target users, and the intended long-term outcome.

## Core Principles
Non-negotiable values that guide decisions and trade-offs.
- Principle 1
- ...

## Technology Constraints
Approved and disallowed technologies, platforms, and tools.
- MUST use X for Y
- ...

## Architecture Constraints
Required patterns, boundaries, and structural rules.
- Pattern or boundary 1
- ...

## Testing Approaches
Mandatory testing strategies and coverage expectations.
- Strategy 1
- ...

## Coding Standards
Enforced rules for code style, structure, and maintainability.
- Standard 1
- ...

## Security Constraints
Required security practices and risk controls.
- Constraint 1 (or "N/A")

## Performance Targets
Key performance requirements and benchmarks.
- Target 1 (or "N/A")

## Integration Points
External systems, APIs, or services the project must integrate with.
- Integration 1 (or "N/A")
```

## Rules

- All nine sections must be present, in order. Never drop one; write `N/A` when the user gave no relevant information (most often Security Constraints, Performance Targets, Integration Points).
- About 3 to 5 items per section. Do not write exhaustive lists or invent sections.
- Every constraint must trace to a user decision and must not contradict any other answer.
- Phrase hard constraints as `MUST use X for Y` or `MUST NOT ...`.
- No document metadata footers (version, date, status).

## Example

```markdown
# Project Constitution: A Generic Product

## Project Vision

Build a product that solves a real user problem with minimal friction, remains easy to evolve, and can be operated by a small team. Favour clarity over cleverness and maintainability over short-term velocity.

## Core Principles

- MVP scope only: essential features first
- User-centric design: prioritise user experience in all decisions
- Performance first: optimise for speed and responsiveness

## Technology Constraints

- MUST use TypeScript for all frontend and backend code
- MUST use PostgreSQL as the primary database
- MUST use AWS services for cloud infrastructure

## Architecture Constraints

- Microservices with clear service boundaries
- Stateless services for horizontal scalability
- Event-driven communication between services

## Testing Approaches

- Minimum 80% unit test coverage
- Integration tests for all API endpoints
- E2E tests for critical user flows

## Coding Standards

- Functional programming style preferred
- Dependency injection required for testability
- ESLint and Prettier for formatting

## Security Constraints

- OWASP Top 10 compliance required
- No secrets or credentials in code repositories
- All data encrypted at rest and in transit

## Performance Targets

N/A

## Integration Points

N/A
```
