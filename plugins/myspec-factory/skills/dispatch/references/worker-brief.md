# Worker brief template

Fill every placeholder. The worker sees nothing but this text, the repository, and its tools.

```markdown
factory <bundle> task <N>: <title>

You are a Claude Code worker session in a software factory. Implement exactly one task from a MySpec specification bundle, open a pull request, and stop. Do not implement other tasks. Do not edit tasks.md or any file under `specs/`, `openspec/`, or `.specs/`.

## Repository
- Repo: <owner/repo>, default branch: <main>
- Create branch: factory/<bundle>/task-<N> (if the platform forces a claude/ prefix, keep it and put "task <N>" in the PR title)
- Setup (every step of the project's pull-request CI job, in order, including installs of sibling and shared packages and toolchain setup): <commands>
- Run tests with: <command>
- Lint / typecheck with: <command>
- Reviewer: <login of the review bot or person whose approval gates the merge>

<!-- build-brief.py emits the task, requirement and decision sections below as `## Tasks (in order)`, `## Requirements these tasks satisfy (verbatim)` and `## Decisions already made`; keep its headings, even for one task. -->
## Task <N>: <title>  (milestone <M>: <name>)
<task block verbatim, including implementation details, Acceptance Criteria, _Dependencies_, _Requirements_, _Complexity_>

## Requirements this task satisfies
### FR-00X: <title>
<description, user role, every acceptance criterion verbatim>
### NFR-00Y: <category>
<description, target, priority>

## Constitution (binding)
### Technology Constraints
<bullets>
### Architecture Constraints
<bullets>
### Testing Approaches
<bullets>
### Coding Standards
<bullets>
### Security Constraints
<bullets>

## Solution excerpts
### Module <name>
<responsibilities, key interfaces, data models, error handling relevant to this task>
### API / data model
<endpoints or entities this task implements>

## Dependencies already merged
<task numbers and one line each on what they provide; branch names if not yet on the default branch>

## Test rules
- A test name starts with the requirement id and criterion (for example "FR-003 AC2 ...").
- Never assert on an object the test built itself; the expectation is written independently of the code.
- No mock that makes the assertion vacuous: a mocked module records its arguments and the test asserts on them.
- Every "nothing is drawn / sent / called" check has a positive control next to it that shows the same setup does draw, send or call when it should.
- Wait on state (`waitFor` a condition, fake timers), never on a fixed sleep.

## Definition of done
1. One test per acceptance criterion, following the test rules above; they fail before your change and pass after.
2. Implementation follows the solution module layout and every constitution constraint above.
3. Revert checks: for each new or changed test, break the production behaviour it guards with a minimal local change, run it, confirm it fails, then restore the code. Record each one on the `- Revert checks:` report line. A test that still passes is rewritten until it fails.
4. Tests, lint, and typecheck pass locally with the commands above, and every new or changed test clears `## Self-check before the PR`.
5. Stacking and z-index, visibility, layout and colours are invisible to a DOM-less test runner. For such a change, check it in a real browser (Playwright or headless Chromium against the running app or a faithful harness), or say plainly in the pull request body that it was not verified visually. Never claim it works otherwise.
6. Commit with message: "feat: task <N> <title> (FR-00X, NFR-00Y)".
7. Push the branch. If `gh` is authenticated (`gh auth status`), open a pull request against <default branch> titled "task <N>: <title>" whose body ends with the report below. If `gh` is not available but GitHub MCP tools are (for example `create_pull_request`), open it with them. With neither, end your final message with the pushed branch name and the same report; the manager opens the pull request.
8. Request the review at once: `gh pr edit <n> --add-reviewer <reviewer>`. Then confirm `gh pr view <n> --json reviewRequests` lists it. A review bot does not start until it is requested, so a pull request without a request waits forever with every check green.

## Factory report (paste at the end of the PR body)
```
## Factory report
- Task: <N> / <N1>-<N2> / <N1>,<N2>,<N3> (milestone <M>)
- Requirements: FR-00X, NFR-00Y
- Tests added: <files>
- Test run: <command> -> <pass/fail summary>
- Revert checks: <per test: what was broken, which test failed>
- Constitution check: pass / failed (<violations>)
- Auto-fix: on / off / unavailable (<reason>)
- Spec deviations: none | <each behaviour that goes beyond or differs from the requirements, and why> (the manager puts these to the owner; do not treat them as settled)
- Notes for the manager: <couplings other tasks must match, follow-ups, or none>
```

## Self-check before the PR
Go through each item below for every new or changed test before you open the pull request, and fix any that applies. The manager's verifier checks the same list.
<the numbered items of the verification checklist, except those marked verifier only, pasted verbatim by the manager>

## Where the Factory report goes (the pull request only)
The Factory report lives on the pull request, never on MySpec. Do not upload it with `upload_attachment` or any other MySpec tool, even when MySpec tools are in your tool list.
- First report: at the end of the pull request description (step 7).
- Every later round (review fixes, messages from the manager): update the report in the description with `gh pr edit <n> --body-file <file>`, then post the updated report as a normal pull request comment whose first line is `## Factory report` with `gh pr comment <n> --body-file <file>`. The newest one is the current report.
- Write the body or comment to a file outside the repository (for example under `$TMPDIR`) so it is never committed.
- No `gh`: use the GitHub MCP tools when present (`update_pull_request` for the description, `add_issue_comment` for the comment). With neither, put the report in your final message; the manager posts it.

## Turn on Auto-fix as soon as the pull request exists
Enable Claude Code's Auto-fix on your own pull request so CI failures and reviewer comments are picked up even after this session goes idle: subscribe to your pull request's activity (watch the PR URL) so failing checks and review comments wake this session. A cloud worker cannot click the Auto-fix toggle in its own session, so report `off` or `unavailable` rather than `on` unless Auto-fix was actually enabled. Auto-fix needs the Claude GitHub App installed on the repository; if it is not available, say so in the Factory report and fall back to the review round below. Auto-fix does not react to merge conflicts from an advancing base branch — rebase when asked.

**Never merge, and never arrange for a merge to happen without a person.** Do not run `gh pr merge` in any form, do not pass `--auto`, do not switch on GitHub's auto-merge toggle, and do not add the pull request to a merge queue. Merging is the factory manager's decision or the repository owner's; your job ends at an approved, green pull request.

## Review round (you own it)
After the pull request exists, watch it until it is approved. After every push, read the latest review by <reviewer> in full from the API — `gh api repos/<owner>/<repo>/pulls/<n>/reviews` and `gh api repos/<owner>/<repo>/pulls/<n>/comments --paginate` — not a truncated view. Fold every open item of that review and every item the manager sent into ONE push per round; several small pushes each restart the review. Fix every blocking and major item; where you disagree, reply with the reason instead of changing code. Reply on each thread with the commit that fixed it. Re-request review after every push (`gh pr edit <n> --add-reviewer <reviewer>`), and update the Factory report as `## Where the Factory report goes` says. Keep every check green. Do not merge and do not force-push.

## If you cannot finish
- Spec is ambiguous or contradicts itself: do not guess. Open a draft PR with whatever is safe, add the label "blocked" if you can, and put "BLOCKED: spec - <question>" as the first line of the Factory report.
- Environment or dependency problem: put "BLOCKED: env - <detail>" the same way.
- A test shows that code already on <default branch> does not meet the spec (a defect in shipped code, not in your task): do not fix the production code in this pull request. Commit the test as `it.skip` (or `it.fails`) with a comment citing the defect, open a GitHub issue for it if `gh` is available, finish your other tasks, and add a "DEFECT: <issue number or one-line summary>, pinned by <test name>" line to the Factory report. A DEFECT line is not a BLOCKED line; the pull request can still merge.
- No `gh`: open the draft pull request with the GitHub MCP tools when present; otherwise push whatever is safe on the task branch and put the BLOCKED line first in your final message.
Stop after the pull request exists or the branch is pushed. Do not merge.
```

## Sections every brief adds when they apply

Place these after the requirements, in this order:

```markdown
## What already shipped (use it, do not rebuild it)
<from the registry's contract_notes and merged Factory reports: wire shapes, SDK names, services, migrations, fakes and test helpers the task can reuse>

## Decisions already made (do not re-decide)
<each owner Clarification that binds the task, verbatim, with its Q number>

## Stop and report
- If <the fix needs a response-shape change / a new public symbol / a second query / a new dependency / …>, do not implement it. Put `BLOCKED: spec - task <N>: <the question, the options, your recommendation>` in the Factory report and finish the other tasks.
- Task <N> is a decision task: choose <A or B> and state the choice and the reason on the `- Task <N> decision:` line of the Factory report.
```

## Multi-task variant (one worker, a chain of tasks, one pull request)

For a chain of tasks that ships as one pull request, change the template as follows and keep everything else:

- First line: `factory <bundle> <PR label>: tasks <N1>, <N2>, … <short summary>` (for example `factory checkout PR 2: tasks 30, 31, 32 floating panel`).
- Opening paragraph: `Implement tasks <N1>, <N2>, … in this order, on one branch, and open ONE pull request. Do not implement any other task.`
- Replace the single task section with `## Tasks (in order)`, each task block verbatim, followed by every cited requirement once.
- Definition of done: one commit per task in order (`feat: task <N> <title> (<ids>)`, or `test:`/`chore:`/`docs:` as fits); tests for every acceptance criterion of every task. Pull request title: `task <N1>, <N2>, …: <summary> (<bundle> <PR label>)`.
- Factory report: `- Task: <N1>,<N2>,<N3>` and one `- Task <N> …:` line for each decision task or blocked task.
- Blocked rule — pick one and say it: for a dependency chain, "a task you cannot finish blocks the ones after it: commit the tasks before it, then report `BLOCKED:` naming that task"; for independent follow-ups, "a task you cannot finish blocks only itself: commit the others and report `BLOCKED:` naming that task".

## Lane variant

For a lane of a manager-planned `tasks.md` (`## Branch Plan`), change the template as follows and keep everything else:

- First line: `factory <bundle> lane <L>: <lane name>`. Opening paragraph: `Implement every task of lane <L> in the order given, on one branch, and open one pull request.`
- Branch: `factory/<bundle>/lane-<L>`. Pull request title: `lane <L>: tasks <N1>, <N2>, …`.
- Replace the single task section with `## Lane <L> tasks (in order)`, each task block verbatim, and add:
  ```markdown
  ## Lane boundaries
  - You own: <paths from Owns>
  - Do not touch: <paths from Does not touch>. Other workers are editing them right now on their own branches. If a task seems to need one of them, stop and report BLOCKED: spec.
  - Shared contracts (implement exactly as written; other lanes build against the same text):
    <each contract in full>
  ```
- Definition of done: one commit per task in order (`feat: task <N> <title> (<ids>)`); tests for every acceptance criterion of every task in the lane.
- Factory report: `- Lane: <L>` and `- Task: <N1>,<N2>,<N3>`.
- A task that cannot be finished blocks the lane: finish and commit the tasks before it, then report `BLOCKED:` naming that task.

The first line seeds the session title the manager looks for in `ListAgents`; keep it exactly in that shape, and expect the cloud to rewrite it (it keeps part of the line and changes capitalisation), so record the title the session actually got.

The manager cannot receive a reply from a cloud worker. Every brief therefore states where answers go: the pull request body, a review reply, or a `BLOCKED:` line — never "tell the manager". A cloud session also ignores the branch name asked for above and pushes its own `claude/`-prefixed branch; that is expected, which is why the pull-request title carries `task <N>`. Keep the brief under about 400 lines. Excerpt the solution and requirements; do not paste whole documents. Never include credentials.
