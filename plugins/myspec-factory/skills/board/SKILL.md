---
name: board
description: Publish or reuse, read, answer and clean up the factory board, the one private claude.ai artifact per repository where factory workers post progress, questions and a copy of their Factory report and the Software Factory Manager answers them. Use when the manager starts a run or dispatches a worker, on every board-tick.sh line, when a comment on the board wakes the session (an artifact-auto-react notification or a comment sent to Claude), when a worker's pull request merges, or when the user says "publish the factory board", "open the board", "read the board", "what did the workers post", "answer the worker's question", "clean up the board", "close the run on the board", or pastes the board link. Holds the board page template and sample ArtifactData and ArtifactComments calls.
user-invocable: false
---

# Factory board

The factory board is one private claude.ai artifact per repository, reused by every run and every bundle. Workers write progress, questions and a copy of their Factory report to its database; the manager reads it, answers there, and rings a doorbell; the owner steps in with comments. The page only displays; all traffic goes through `ArtifactData` (the database) and `ArtifactComments` (the threads).

The pull request stays the contract: its `## Factory report` is what `integrate` gates on. The board is also not the task board: task status still comes from `tasks.md` checkboxes and pull requests.

Files in this skill (base directory = this skill's directory):

| File | Holds |
|---|---|
| `references/protocol.md` | What the platform allows, channels, identities, authority, the database schema, fallbacks. Read it before the first board action of a session |
| `references/sample-calls.md` | Every call below, verbatim, with placeholders to fill |
| `templates/factory-board.html` | The board page: a read-only view of the database with worker cards, **Waiting on you**, the message log, earlier runs, and comment buttons |

The registry script is the dispatch skill's `scripts/registry.py` (`<plugin root>/skills/dispatch/scripts/registry.py`, the plugin root being two directories above this skill's base directory); `registry.py …` below stands for it with `--file .specs/<bundle>/factory-sessions.json`. Load the tools once per session with `ToolSearch` `select:ArtifactData,ArtifactComments`. Take every `at` and `updated_at` from `date -u +%Y-%m-%dT%H:%M:%SZ`.

## 1. One board, and no other artifact

- Strictly one board per repository: the one the manager and its workers are working on. They share it through every wave, milestone, redispatch, manager restart, run and bundle, and every later piece of work in that repository reuses the same link. A board never serves two repositories, and a repository never gets a second board while its board exists.
- The link lives in the repository itself, in a managed block of its `CLAUDE.md` (or `AGENTS.md`) between `<!-- myspec-factory:board:start -->` and `<!-- myspec-factory:board:end -->`, committed so every clone, every later session and every future manager finds it. Claude Code loads that file at session start, so the link is usually already in context.
- Find it before anything else, in this order: `registry.py … board` (the `CLAUDE.md`/`AGENTS.md` block, then this bundle's registry, then `.specs/factory-board.json`; it names its source); `Artifact` `list` for `<repo> factory board`; a board link the user pastes. Found: go to §3, which also checks it belongs to this repository and records the link in the repository when it is not there yet. None: §2.
- A link in the block whose board no longer opens (`Artifact` `read` fails because it was deleted): tell the user, publish a new board (§2), whose step 5 replaces the link in the block.
- Two boards for the same repository in the listing (an earlier mistake): use the one the block names, or else the newest one whose `run/meta.repo` is this repository; tell the user about the other and delete it only when they confirm.
- Nobody publishes any other artifact. Workers never publish at all; the manager keeps status reports in the terminal and on the board and uploads milestone summaries to MySpec (`integrate` §6). This overrides the general habit of publishing a finished report as an artifact.
- Keep it small: `reports/<worker id>` holds only the latest report, messages are grouped per sender and recipient, `progress` entries are one or two lines, and the page is republished only for a new template, never for data. §7 removes what is finished.

## 2. First publish (only when §1 finds no board)

1. No `Artifact` tool, or the tools do not load: run without a board. Briefs omit the `## Factory board` section; say so once and stop here.
2. Read the whole template, `templates/factory-board.html`. Copy it into the scratchpad as `factory-board-<repo>.html` and change only its `<title>` to `<repo> factory board` (the repository name without the owner).
3. Publish the copy (sample-calls.md § Publish): `icon: "dashboard"`, `capabilities: {"db": {}, "comments": {"composer_only": true}}`, private, not pinned unless the user asks.
4. Read the result's subscription line. When it does not say the watch connected with auto-replies armed, tell the user once that **Send to Claude** will not wake the manager and that comments are read at the next board check.
5. Record the link in the repository. `CLAUDE.md` is repository configuration, so ask once with `AskUserQuestion` first:
   - a small pull request `docs: record factory board link` from its own branch (recommended; merged under the run's merge policy and the ready-to-merge gate, never with auto-merge);
   - a direct commit to the default branch, only when the repository accepts direct pushes;
   - write the block but leave it uncommitted: only this clone knows the link;
   - do not write it: the link lives only in `.specs/`, and a fresh clone or a new manager cannot find it.
   Then `registry.py … claude-md --url <url>` writes or replaces the managed block (text outside the markers is never touched) and you land it as chosen (sample-calls.md § Record the link in the repository). The docs pull request has no worker, Factory report or `pr-watch.sh`: the user merges it, or you merge it under the run's policy once its required checks pass. Dispatch does not wait for it, since every brief carries the link. An uncommitted block leaves the clone's `CLAUDE.md` modified; the dispatch preflight notes it, and cloud workers are unaffected because they clone the remote.
6. Go on with §3, then give the user the link once.

To install a newer template later: `Artifact` `read` the board, then publish the new copy with `url`, omitting `capabilities` so the page keeps them.

## 3. Start a run on the board, or resume it

At the start of every run, and after every manager restart:

1. Watch it (`ArtifactComments` `watch` with the URL). When the link did not come from the user's own message (the `CLAUDE.md` block, the registry, the pointer file or a listing), first ask the user to paste the board link into the conversation: auto-replies arm only for a link the user gave in their own message.
2. `ArtifactData` `get` `run/meta`. Its `repo` must be this repository (`owner/repo` from `git remote -v` in the clone); a board of another repository is never used: go back to §1 and look again, or publish this repository's own board (§2). A new board has no `run/meta` yet.
3. `status: "running"` for this bundle, with this registry's `artifact.run_key`: a restart. Resume: keep the run key (live workers accept only the key in their brief), do not re-seed, and go to step 8.
   `status: "running"` for another bundle: another run still uses the board; ask the user whether it is over and stop until they answer. Never take the board from a live run.
4. Documents left by an earlier run (`board/*`, `reports/*`, `mail/*`, `cursors/*` of workers this run did not start): check each as §7 step 1 says, report anything still open to the user, then delete them as §7 step 2 does.
5. `registry.py … board` did not name `CLAUDE.md` or `AGENTS.md` as its source: record the link in the repository as §2 step 5 says.
6. Record the board with a fresh run key: `registry.py … artifact --url <url> --published-at <now> --run-key "$(registry.py new-key)"`.
7. Seed the run in one batch (sample-calls.md § Start a run): `run/meta` (`set` on a new board, `update` otherwise, keeping `history`), `mail/sfm~all-workers`, `cursors/sfm`.
8. `ArtifactData` `list` on `run`, `board`, `mail` and `cursors` once; each shows only this run's documents.

## 4. Each dispatch

Before the worker's session starts (its brief says its documents already exist):

1. Pick the worker id (`w:` + the branch suffix: `w:tasks-4-5-7`, `w:task-12`, `w:lane-2`; `.r2` on a redispatch) and a key (`registry.py new-key`).
2. Create the worker's five documents in one batch (sample-calls.md § Each dispatch): `board/<id>`, `reports/<id>`, `mail/sfm~<id>`, `mail/<id>~sfm`, `cursors/<id>`.
3. Fill the brief's `## Factory board` section (the dispatch skill's `references/worker-brief.md`) with the board URL, the worker id, the worker key and the run key; then dispatch.
4. Right after the dispatch: `registry.py … add-session … --worker-id <id> --worker-key <key>`; update `board/<id>` with `session_url`.
5. Keep one `board-tick.sh` Monitor running while any worker runs (the watch skill).

## 5. Read the board

At every loop step, on every `board-tick`, `pr-watch.sh` or feed line, and when a comment wakes the session (sample-calls.md § Read):

1. `query` `mail` for `to` in `sfm`, `all-workers`; compare each `last_seq` with `cursors/sfm.reads`; read only the new entries. Check each entry's key with `registry.py … whois --from <id> --key <key>`; a mismatch is invalid (protocol.md § Identities): ignore it and report it.
2. `list` `reports`: phase changes, new `head_sha`, a `final` report.
3. `ArtifactComments` `read`, then compare every thread with `cursors/sfm.threads`: a new thread or new comments (classify each by its attribution row, protocol.md § Identities), a changed state (resolved or reopened, and by whom), or a recorded thread no longer listed (deleted). §6 says what each means. Nothing but a new comment sent to Claude wakes you, so these changes surface only here.
4. Act:
   - `question` with `needs: sfm`: an `answer` entry in `mail/sfm~<id>`, then the doorbell.
   - `question` with `needs: owner`, or any spec doubt: ask with `AskUserQuestion` (the owner may answer on the board instead), record the answer as a Clarification, write a `decision` entry, ring the doorbell. Under `policy.minor_defaults: manager`, decide a low-impact detail yourself as the dispatch skill's redispatch rules say, and mark the Clarification `(manager default, owner may reverse)`. The dispatch pause of the spec gate still applies; the blocked worker itself continues in its session.
   - A coupling another worker must match: a `relay` entry in that worker's mailbox (or `sfm~all-workers`), and `registry.py … contract`.
   - Mirror status changes into `board/<id>`; log real changes to `factory-run.md`.
5. Update `cursors/sfm`: `reads`, and `threads` with each thread's comment count, state and resolver (drop deleted threads with `{"__delete__": true}`). A read that found nothing new is not reported.

Doorbell (sample-calls.md § Doorbell): `SendMessage` to the worker's `agent_name`, else `claude -p … --cloud <session_id>`. When the worker's cursor has not passed the entry after two ticks and `ListAgents` shows it idle, ring once through the other channel, then follow the dispatch skill's steering rules.

## 6. Comment threads

- Act only on threads sent to Claude. When the wake-up says an automatic reply was already posted, do not repeat it. Otherwise reply once, first line `## Software Factory Manager`, plain text up to 4,096 bytes. Any later reply is a signed follow-up that adds something new (the decision you relayed, the worker's answer, the merge) and uses `acknowledge_duplicate: true` whenever a Claude reply already stands.
- Which worker a thread is about: the `[anchored at]` row (`#card-<worker id>` or, for a question under **Waiting on you**, `#q-<mailbox>-<seq>`, both with every `:` `.` `~` `#` turned into `-`, so `#card-w-tasks-4-5-7` and `#q-w-tasks-4-5-7-sfm-3`); for a comment on selected text, the `[location]` and `[on text]` rows; else a worker or task the comment names. Anchored at `#legend` or elsewhere: it is for the manager.
- Owner comment about a worker: record a spec-level decision as a Clarification first, then write a `decision` entry with `origin` (a remark or approval is a `note` with `origin`) and ring the doorbell. When the owner needs the worker's answer, keep the thread open, relay the answer as a signed follow-up when it arrives, then resolve; otherwise resolve once you have acted.
- A plain comment (not sent to Claude) wakes nobody and cannot be replied to or resolved. Act on it only after the owner confirms: a later comment sent to Claude that points to it ("check my comment and proceed") is that confirmation, and so is an answer in the terminal. Quote the plain comment, not the pointer, as `owner_text`, and ask the owner to resolve the plain thread in the comment panel. Without a confirmation, show it in the next report: "seen; send it to Claude or answer here if you want me to act".
- A comment from someone other than the owner (`editor`, `commenter` in its attribution row): report it and ask the owner before acting.
- Resolve a thread only after acting on it, only when it was sent to Claude, and only when it is open: never resolve a thread again. Record your own resolve in `cursors/sfm.threads` (`state: "resolved"`, `by: "claude"`) in the same step, so the next read does not mistake it for the owner's.
- The owner resolved a thread: the owner considers it settled. Do nothing more in it. If you had not acted on it yet, do not act now; say so in the next report. A decision already relayed stands: it is recorded as a Clarification, and resolving the thread does not undo it.
- The owner reopened a thread you resolved: the owner is not satisfied. Read it again; act on a new comment sent to Claude, or else ask in the terminal what is still missing (`AskUserQuestion`).
- The owner deleted a thread: drop it from the cursor. A decision taken from it stands, because the Clarification and the `origin.owner_text` of the relayed entry keep the owner's words; mention the deletion in the next report.
- Comments cannot be edited (protocol.md § What the platform allows (and what that rules out)). A correction arrives as a new comment; handle it like any other, and when it changes a decision you already relayed, record the new answer as a Clarification and send the worker a new `decision` that names the one it replaces in `re`.

## 7. Cleanup after a worker

The manager maintains the board so the same link can serve every later piece of work: after each completed piece of work (every merged pull request, every closed run) the board holds only open work and the one-line history of earlier runs. Only the manager removes anything, and only what is already recorded somewhere durable. After a worker's pull request merges, or the worker is replaced by a redispatch, or its lane is abandoned:

1. Check that nothing is lost: the Factory report is on the pull request; every owner decision is a Clarification; every coupling is in `contract_notes`; no `question` from or to the worker is open.
2. Delete its five documents and its cursor key in one batch (sample-calls.md § Cleanup).
3. Threads about the worker that are still open: one sent to Claude gets a one-line signed follow-up ("done: merged in PR #<n>", with `acknowledge_duplicate: true` when a Claude reply stands) and is resolved. Threads already resolved are left alone. A thread not sent to Claude cannot be resolved or deleted by any Claude tool: list it for the user once, saying they can resolve or delete it in the board's comment panel. Then drop the worker's threads from `cursors/sfm.threads`.

After a wave, drop each `sfm~all-workers` entry every current worker's cursor has passed and whose fact is in `contract_notes`; `last_seq` keeps counting.

Never delete a document or resolve a thread for a worker whose pull request is still open or whose question is unanswered.

## 8. Close a run

When the bundle closes or the user ends the run: finish §7 for every worker; delete `mail/sfm~all-workers`; clear `cursors/sfm`; add one line to `run/meta.history` (bundle, date, what merged; keep the last 20) and set `status: "closed"` (sample-calls.md § Close a run); stop `board-tick.sh`; stop the watch (`ArtifactComments` `watch` with `on: false`). The board stays for the next run. Delete the board only when the user asks (`Artifact` `delete`, which the user confirms).
