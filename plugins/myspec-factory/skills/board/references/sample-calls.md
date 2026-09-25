# Factory board: sample calls

Every board call the manager makes, verbatim; fill the `<placeholders>`. Shapes and rules are in `protocol.md`; the order of the steps is in `SKILL.md`. The `Artifact`, `ArtifactData`, `ArtifactComments` and `SendMessage` calls were exercised against a live board with a manager session and a `claude --bg` worker; the `claude -p --cloud` doorbell was not.

Placeholders: `<url>` the board URL, `<run key>` from `registry.py … artifact`, `<id>` a worker id such as `w:tasks-4-5-7`, `<worker key>` from `registry.py new-key`, `<now>` from `date -u +%Y-%m-%dT%H:%M:%SZ`, `<v>` the `version` your last read or write of that document returned.

## Load the tools

```
ToolSearch({ query: "select:ArtifactData,ArtifactComments", max_results: 2 })
```

## Publish

The first publish of a repository's board (SKILL.md §2), from the scratchpad copy of `templates/factory-board.html` with only its `<title>` changed:

```
Artifact({
  file_path: "<scratchpad>/factory-board-<repo>.html",
  icon: "dashboard",
  description: "Factory board for <owner/repo>: the current run's workers, reports, questions and messages.",
  capabilities: { "db": {}, "comments": { "composer_only": true } }
})
```

A newer template later: `Artifact({ action: "read", url: "<url>" })`, then the same publish with `url: "<url>"` and without `capabilities` or `icon`.

## Record the link in the repository

After the user chose how to land it (SKILL.md §2 step 5), write or replace the managed block (the command prints the file it changed):

```bash
python3 <plugin root>/skills/dispatch/scripts/registry.py --file .specs/<bundle>/factory-sessions.json claude-md --url <url>
```

The block it writes:

```markdown
<!-- myspec-factory:board:start -->
## Factory board
- Board: https://claude.ai/artifact/<id>
- One board per repository: the Software Factory Manager reuses this link for all work here and never publishes
  another. It publishes, maintains and cleans the board; workers use it only as their brief says.
<!-- myspec-factory:board:end -->
```

Land it the way the user chose. A pull request, leaving the clone back on the base branch and clean:

```bash
cd <clone> && git switch -c docs/factory-board-link && git add <the file claude-md printed: CLAUDE.md or AGENTS.md> \
  && git commit -m "docs: record factory board link" && git push -u origin HEAD \
  && gh pr create --title "docs: record factory board link" --body "## Software Factory Manager
Records the repository's factory board link so later sessions reuse it instead of publishing a new board." \
  && git switch <base>
```

A direct commit (only when the default branch accepts direct pushes):

```bash
cd <clone> && git add <CLAUDE.md or AGENTS.md> && git commit -m "docs: record factory board link" && git push origin <base>
```

Find it later: `registry.py … board` prints the URL and names its source on stderr (`board from …/CLAUDE.md`).

## Start a run

On a new board `run/meta` does not exist yet: use `set` with `history: []`. On a reused board use `update` with `if_version`, which keeps `history`.

```
ArtifactData({
  action: "batch", url: "<url>",
  writes: [
    { op: "update", collection: "run", doc_id: "meta", if_version: <v>,
      data: { bundle: "<bundle>", project_id: "<project id>", repo: "<owner/repo>",
              protocol: "factory-board/1", status: "running", started_at: "<now>", updated_at: "<now>" } },
    { op: "set", collection: "mail", doc_id: "sfm~all-workers",
      data: { from: "sfm", to: "all-workers", key: "<run key>", last_seq: 0, messages: {}, updated_at: "<now>" } },
    { op: "set", collection: "cursors", doc_id: "sfm",
      data: { reads: {}, threads: {}, updated_at: "<now>" } }
  ]
})
```

Check: `ArtifactData({ action: "list", url: "<url>", collection: "run" })`, and the same for `board`, `mail`, `cursors`.

## Each dispatch

```
ArtifactData({
  action: "batch", url: "<url>",
  writes: [
    { op: "set", collection: "board", doc_id: "<id>",
      data: { worker_id: "<id>", tasks: [4, 5, 7], title: "<summary>", status: "running",
              branch: "factory/<bundle>/tasks-4-5-7", pr: null, verified_sha: null,
              next: "Waiting for the first progress report", updated_at: "<now>" } },
    { op: "set", collection: "reports", doc_id: "<id>",
      data: { worker_id: "<id>", key: "<worker key>", tasks: [4, 5, 7], phase: "dispatched",
              tasks_done: [], branch: null, head_sha: null, pr: null, report: "", updated_at: "<now>" } },
    { op: "set", collection: "mail", doc_id: "sfm~<id>",
      data: { from: "sfm", to: "<id>", key: "<run key>", last_seq: 0, messages: {}, updated_at: "<now>" } },
    { op: "set", collection: "mail", doc_id: "<id>~sfm",
      data: { from: "<id>", to: "sfm", key: "<worker key>", last_seq: 0, messages: {}, updated_at: "<now>" } },
    { op: "set", collection: "cursors", doc_id: "<id>",
      data: { reads: {}, updated_at: "<now>" } }
  ]
})
```

## Read

New messages for the manager:

```
ArtifactData({ action: "query", url: "<url>", collection: "mail",
               query: { where: [["to", "in", ["sfm", "all-workers"]]] } })
```

Reports, the manager's cursor, and comments:

```
ArtifactData({ action: "list", url: "<url>", collection: "reports" })
ArtifactData({ action: "get", url: "<url>", collection: "cursors", doc_id: "sfm" })
ArtifactComments({ action: "read", url: "<url>" })
```

Check a sender: `registry.py … whois --from <id> --key <key from the entry>` prints `sfm` or the session, and exits 1 on a mismatch.

## Answer

Append to the worker's inbox (`get` it first for `<v>` and `last_seq`; nested maps merge, so only the new entry is sent), and move your cursor in the same batch:

```
ArtifactData({
  action: "batch", url: "<url>",
  writes: [
    { op: "update", collection: "mail", doc_id: "sfm~<id>", if_version: <v>,
      data: { messages: { "002": { seq: 2, key: "<run key>", kind: "decision", re: "<id>~sfm#2",
                                   tasks: [4], needs: "none",
                                   text: "Decision for task 4: <the answer>. Recorded as a Clarification under task 4. Continue and ack.",
                                   origin: { thread: "<thread id>", owner_text: "<the owner's words, verbatim>" },
                                   at: "<now>" } },
              last_seq: 2, updated_at: "<now>" } },
    { op: "update", collection: "cursors", doc_id: "sfm", if_version: <v>,
      data: { reads: { "<id>~sfm": 2 },
              threads: { "<thread id>": { comments: 2, state: "resolved", by: "claude" } },
              updated_at: "<now>" } },
    { op: "update", collection: "board", doc_id: "<id>", if_version: <v>,
      data: { next: "Owner decided task 4 (sfm~<id>#2). Waiting for the worker's ack.", updated_at: "<now>" } }
  ]
})
```

Leave `origin` out when the answer is the manager's own. Kinds the manager sends: `answer`, `decision`, `relay`, `steer`, `note`.

## Doorbell

```
SendMessage({ to: "<agent_name from the registry>",
              message: "Software Factory Manager: board message sfm~<id>#2 (decision) is waiting for you. Read it on the factory board and answer there." })
```

Without Remote Control, or when the session left the listing:

```bash
cd <clone> && claude -p "Software Factory Manager: board message sfm~<id>#2 (decision) is waiting for you. Read it on the factory board and answer there." --cloud <session_id>
```

The worker's `cursors/<id>.reads["sfm~<id>"]` reaching 2 proves it read the entry; its `ack` entry proves it acted.

## Comment threads

A signed reply (only when no automatic reply was posted, or as a follow-up that adds something new):

```
ArtifactComments({ action: "reply", url: "<url>", thread_id: "<thread id>",
                   text: "## Software Factory Manager\nSent to worker <id> as decision sfm~<id>#2: <the answer>.",
                   acknowledge_duplicate: true })
ArtifactComments({ action: "resolve", url: "<url>", thread_id: "<thread id>" })
```

Drop `acknowledge_duplicate` when no Claude reply stands in the thread yet.

Record what the read found, in the same batch as the rest of the cursor update: a thread the owner resolved, one reopened, one deleted:

```
{ op: "update", collection: "cursors", doc_id: "sfm", if_version: <v>,
  data: { threads: { "<thread id>": { comments: 3, state: "resolved", by: "owner" },
                     "<reopened thread id>": { comments: 4, state: "open", by: null },
                     "<deleted thread id>": { "__delete__": true } },
          updated_at: "<now>" } }
```

## Cleanup

After a merged worker (`<v>` from your last read of each document):

```
ArtifactData({
  action: "batch", url: "<url>",
  writes: [
    { op: "delete", collection: "board",   doc_id: "<id>",      if_version: <v> },
    { op: "delete", collection: "reports", doc_id: "<id>",      if_version: <v> },
    { op: "delete", collection: "mail",    doc_id: "<id>~sfm",  if_version: <v> },
    { op: "delete", collection: "mail",    doc_id: "sfm~<id>",  if_version: <v> },
    { op: "delete", collection: "cursors", doc_id: "<id>",      if_version: <v> },
    { op: "update", collection: "cursors", doc_id: "sfm",       if_version: <v>,
      data: { reads: { "<id>~sfm": { "__delete__": true } }, updated_at: "<now>" } }
  ]
})
```

Drop one relay every worker has read:

```
ArtifactData({ action: "update", url: "<url>", collection: "mail", doc_id: "sfm~all-workers", if_version: <v>,
               data: { messages: { "003": { "__delete__": true } }, updated_at: "<now>" } })
```

## Close a run

After the per-worker cleanup (`history` is an array, so send the whole list: the previous entries plus the new one, at most 20):

```
ArtifactData({
  action: "batch", url: "<url>",
  writes: [
    { op: "delete", collection: "mail", doc_id: "sfm~all-workers", if_version: <v> },
    { op: "set", collection: "cursors", doc_id: "sfm", if_version: <v>,
      data: { reads: {}, threads: {}, updated_at: "<now>" } },
    { op: "update", collection: "run", doc_id: "meta", if_version: <v>,
      data: { status: "closed", updated_at: "<now>",
              history: [ /* earlier entries */ { bundle: "<bundle>", closed_at: "<now>",
                                                  summary: "<n> tasks merged in PRs #<a>, #<b>; follow-ups: <none | list>" } ] } }
  ]
})
ArtifactComments({ action: "watch", url: "<url>", on: false })
```

## Worker side

A worker's calls are in its brief (the dispatch skill's `references/worker-brief.md`, `## Factory board`): `get` then `update` of `mail/<id>~sfm` to send, `update` of `reports/<id>` at each checkpoint, `get` of `mail/sfm~<id>` and `mail/sfm~all-workers` plus an `update` of `cursors/<id>` to read. A worker never calls `Artifact` or writes a comment.
