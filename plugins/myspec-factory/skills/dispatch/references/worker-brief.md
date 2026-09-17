# Worker brief template

Fill every placeholder. The worker sees nothing but this text, the repository, and its tools.

```markdown
factory <bundle> task <N>: <title>

You are a Claude Code worker session in a software factory. Implement exactly one task from a MySpec specification bundle, open a pull request, and stop. Do not implement other tasks. Do not edit tasks.md or any file under `specs/`, `openspec/`, or `.specs/`.

## Repository
- Repo: <owner/repo>, default branch: <main>
- Create branch: factory/<bundle>/task-<N> (if the platform forces a claude/ prefix, keep it and put "task <N>" in the PR title)
- Run tests with: <command>
- Lint / typecheck with: <command>

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

## Definition of done
1. One test per acceptance criterion, named with the requirement id and criterion (for example "FR-003 AC2 ..."); they fail before your change and pass after.
2. Implementation follows the solution module layout and every constitution constraint above.
3. Tests, lint, and typecheck pass locally with the commands above.
4. Commit with message: "feat: task <N> <title> (FR-00X, NFR-00Y)".
5. Push the branch. If `gh` is authenticated (`gh auth status`), open a pull request against <default branch> titled "task <N>: <title>" whose body ends with the report below. If `gh` is not available, end your final message with the pushed branch name and the same report; the manager opens the pull request.

## Factory report (paste at the end of the PR body)
```
## Factory report
- Task: <N> / <N1>-<N2> / <N1>,<N2>,<N3> (milestone <M>)
- Requirements: FR-00X, NFR-00Y
- Tests added: <files>
- Test run: <command> -> <pass/fail summary>
- Constitution check: pass / failed (<violations>)
- Auto-fix: on / off / unavailable (<reason>)
- Spec deviations: none | <each behaviour that goes beyond or differs from the requirements, and why> (the manager puts these to the owner; do not treat them as settled)
- Notes for the manager: <couplings other tasks must match, follow-ups, or none>
```

## Report to the platform (only if MySpec tools are available to you)
If your tool list contains mcp__plugin_myspec-mcp_myspec__upload_attachment or mcp__myspec__upload_attachment: after the pull request exists (or the branch is pushed), write the Factory report to a file outside the repository (for example under $TMPDIR, so it is never committed) and upload it with upload_attachment(project_id="<project_id>", file_path="<absolute path>", file_name="factory-<bundle>-task-<N>-report.md", override=true). This tells the manager you are done. Do not call any other MySpec write tool.

## Turn on Auto-fix as soon as the pull request exists
Enable Claude Code's Auto-fix on your own pull request so CI failures and reviewer comments are picked up even after this session goes idle: subscribe to your pull request's activity (watch the PR URL) so failing checks and review comments wake this session. A cloud worker cannot click the Auto-fix toggle in its own session, so report `off` or `unavailable` rather than `on` unless Auto-fix was actually enabled. Auto-fix needs the Claude GitHub App installed on the repository; if it is not available, say so in the Factory report and fall back to the review round below. Auto-fix does not react to merge conflicts from an advancing base branch — rebase when asked.

**Never merge, and never arrange for a merge to happen without a person.** Do not run `gh pr merge` in any form, do not pass `--auto`, do not switch on GitHub's auto-merge toggle, and do not add the pull request to a merge queue. Merging is the factory manager's decision or the repository owner's; your job ends at an approved, green pull request.

## Review round (you own it)
After the pull request exists, watch it until it is approved. Read `gh api repos/<owner>/<repo>/pulls/<n>/reviews` and `gh api repos/<owner>/<repo>/pulls/<n>/comments --paginate` in full — a review body may be long, so read it from the API rather than a truncated view. Fix every blocking and major item, push, and reply on each thread with the commit that fixed it; where you disagree, reply with the reason instead of changing code. Then re-request review (`gh pr edit <n> --add-reviewer <reviewer>`). Keep every check green. Repeat for each further round. Do not merge and do not force-push.

## If you cannot finish
- Spec is ambiguous or contradicts itself: do not guess. Open a draft PR with whatever is safe, add the label "blocked" if you can, and put "BLOCKED: spec - <question>" as the first line of the Factory report.
- Environment or dependency problem: put "BLOCKED: env - <detail>" the same way.
- No `gh`: push whatever is safe on the task branch and put the BLOCKED line first in your final message.
Stop after the pull request exists or the branch is pushed. Do not merge.
```

The first line seeds the session title the manager looks for in `ListAgents`; keep it exactly in that shape, and expect the cloud to rewrite it (it keeps part of the line and changes capitalisation), so record the title the session actually got.

The manager cannot receive a reply from a cloud worker. Every brief therefore states where answers go: the pull request body, a review reply, or a `BLOCKED:` line — never "tell the manager". A cloud session also ignores the branch name asked for above and pushes its own `claude/`-prefixed branch; that is expected, which is why the pull-request title carries `task <N>`. Keep the brief under about 400 lines. Excerpt the solution and requirements; do not paste whole documents. Never include credentials.
