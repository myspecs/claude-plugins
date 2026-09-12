# Worker brief template

Fill every placeholder. The worker sees nothing but this text, the repository, and its tools.

```markdown
factory <bundle> task <N>: <title>

You are a Claude Code worker session in a software factory. Implement exactly one task from a MySpec specification bundle, open a pull request, and stop. Do not implement other tasks. Do not edit tasks.md or any file under specs/, openspec/, or .specs/.

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
- Task: <N>
- Requirements: FR-00X, NFR-00Y
- Tests added: <files>
- Test run: <command> -> <pass/fail summary>
- Constitution check: pass | <violations>
- Notes for the manager: <deviations, follow-ups, or none>
```

## Report to the platform (only if MySpec tools are available to you)
If your tool list contains mcp__plugin_myspec-mcp_myspec__upload_attachment or mcp__myspec__upload_attachment: after the pull request exists (or the branch is pushed), write the Factory report to a file outside the repository (for example under $TMPDIR, so it is never committed) and upload it with upload_attachment(project_id="<project_id>", file_path="<absolute path>", file_name="factory-<bundle>-task-<N>-report.md", override=true). This tells the manager you are done. Do not call any other MySpec write tool.

## If you cannot finish
- Spec is ambiguous or contradicts itself: do not guess. Open a draft PR with whatever is safe, add the label "blocked" if you can, and put "BLOCKED: spec - <question>" as the first line of the Factory report.
- Environment or dependency problem: put "BLOCKED: env - <detail>" the same way.
- No `gh`: push whatever is safe on the task branch and put the BLOCKED line first in your final message.
Stop after the pull request exists or the branch is pushed. Do not merge.
```

The first line is the session title the manager uses to find this session in `ListAgents`; keep it exactly in that shape. Keep the brief under about 400 lines. Excerpt the solution and requirements; do not paste whole documents. Never include credentials.
