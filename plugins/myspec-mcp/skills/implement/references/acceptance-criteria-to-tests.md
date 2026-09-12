# Acceptance criteria to tests

Every acceptance criterion in a MySpec requirement is written in an EARS+ pattern, which maps directly onto a test. Write one test per criterion, name it so the requirement and criterion are traceable, and make it fail before the change and pass after.

## Pattern to test shape

| Criterion pattern | Test structure |
|---|---|
| `WHEN <event> THEN <system> SHALL <response>` | Arrange the normal preconditions, act with the event, assert the response |
| `WHEN <event> AND <condition> THEN ...` | Two tests: condition true (response happens) and condition false (it does not) |
| `WHILE <state> THEN <system> SHALL <response>` | Arrange the state, then assert the behaviour holds; add a test outside the state when the difference matters |
| `IF <pre-condition> THEN <system> SHALL <response>` | Error or edge path: arrange the unwanted condition, assert the protective response (status code, message, lock, rollback) |
| `IF <pre-condition> WHEN <event> THEN ...` | Arrange the precondition, act with the event, assert the response; pair with the same event without the precondition |
| `WHERE <feature> ...` | Feature flag or configuration test: enabled and disabled |
| Ubiquitous `The <system> SHALL ...` | An invariant: assert it in the most representative flow, or as a property test |
| NFR `**Target:**` (latency, throughput, size) | A measurable check: benchmark, load test, or a bounded assertion run in CI; if it cannot run in unit tests, record how it was verified in the report |

Given/When/Then criteria (older bundles) map the same way: Given is arrange, When is act, Then is assert.

## Naming for traceability

Include the requirement id and criterion position in the test name or description, so a coverage check can find them by grep:

```
test("FR-003 AC2: IF the cart is empty THEN checkout returns 409", ...)
def test_fr_003_ac2_empty_cart_returns_409():
func TestFR003_AC2_EmptyCartReturns409(t *testing.T)
```

Analysis searches for these with the separator optional and case-insensitive (`FR[-_]?003`), so any of the forms above is found. For brownfield deltas use the module and delta id: `orders CR-001 AC2`. For OpenSpec deltas use the capability and scenario name: `billing: Scenario "Refund after capture"`.

## Placement

Follow the constitution's Testing Approaches section for the layer and framework. Default: unit tests beside the module for FR criteria; integration tests for criteria that cross module boundaries named in `solution.md`; end-to-end tests only where the constitution or a task's acceptance criteria call for them.

## Definition of done for a task

- Every acceptance criterion on the task and on its `_Requirements:_` entries has at least one test, or a written reason it cannot be tested automatically.
- The task's tests and the affected suite pass.
- No constitution constraint is violated.
- The task is `[x]` on the platform and the progress note is updated.
