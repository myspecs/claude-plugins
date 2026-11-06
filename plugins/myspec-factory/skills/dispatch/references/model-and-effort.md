# Agent model and effort

The manager picks one model and one effort level for every agent session, cloud or local (`claude --bg`), before it starts the session (dispatch skill §1a). A session keeps its rung for its whole life, so an agent's rung is the highest rung any group in its queue needs. This file is the only place the rules live.

## The ladder

Pick exactly one rung. Never use any other combination: no `sonnet` with `high` or `xhigh`, no `low` or `max` effort.

| Rung | Model | Effort | Use for |
|---|---|---|---|
| 1 | `sonnet` | `medium` | Small, mechanical, fully specified work: documentation, configuration, copy and label changes, renames, adding tests for cases the task lists, a change that copies an existing pattern in one module |
| 2 | `opus` | `medium` | **The default.** Ordinary feature work: a group of related tasks, several files, new endpoints or components that follow the solution's design |
| 3 | `opus` | `high` | Work where a wrong guess is expensive: a contract shared across modules or services, data migrations, auth, security or permissions, concurrency, caching or ordering rules, money or other exact arithmetic, a large group, a stacked branch that must rebase onto its parent |
| 4 | `opus` | `xhigh` | The hardest work: a large group of a brownfield change across several services, subtle cross-cutting behaviour (consistency, retries, distributed state), a fix for a confirmed defect in merged code whose cause is not obvious, and every replacement after a failure on rung 3 |

When a rung between Sonnet and Opus would fit, take Opus with `medium` effort: it beats Sonnet at higher effort. Sonnet runs only at `medium`.

## How to pick

1. Rate each group: start at rung 2.
2. Go down to rung 1 only when every task of the group is rung-1 work. One task that is not pulls the whole group up.
3. Go up to rung 3 when any task of the group, or the group as a whole, matches rung 3. Go up to rung 4 only for the cases rung 4 names.
4. An agent's rung is the highest rung of the groups in its queue: a session runs with one setting. When dividing (dispatch skill §0b), keep a single heavy group from pulling a whole queue of light groups up where the balance allows, and never move a group to an agent whose rung is below the group's.
5. When unsure between two rungs, take the higher one. A failed assignment costs a replacement session and a review round; a stronger setting costs only tokens.
6. A replacement after a failure (red checks the agent could not fix, no pull request, a timeout, a verification that found real defects) moves up one rung from the failed session's rung, up to rung 4. A replacement for another reason (recycling a long session, the session ended or expired) keeps the rung.
7. The user's choice wins. When the user names a model or effort for a run or an agent, use it, even off the ladder, and record it.

Signals to read, from the task blocks, the requirements and the solution excerpts of each group: how many tasks and files, how many modules or services the group touches, whether it changes a shared contract or stored data, whether it touches security, money or concurrency, and how much the assignment leaves to the agent's judgement.

## Passing it to the agent

| Path | How |
|---|---|
| `claude --cloud` | `--model <model> --effort <effort>` after the brief, with `--permission-mode auto`: `claude --cloud "$(cat <brief>)" --model opus --effort high --permission-mode auto`. Nothing may come between `--cloud` and the brief |
| `claude --bg` | `--model <model> --effort <effort>` next to `--permission-mode auto` |

An assignment message or a steering message (`claude -p … --cloud <session_id>`) keeps the session's model and effort; never pass `--model` or `--effort` with it. A group that needs a higher rung than any agent has goes to a replacement session for one agent at that rung (dispatch skill, Replacing an agent).

## Recording and showing it

- Show the rung for each agent in the team table the user confirms (the `plan` skill), with one reason when it is not rung 2.
- Record it with `registry.py … add-agent … --model <model> --effort <effort>`. The script refuses combinations off the ladder unless `--off-ladder` is given (step 6 above).
