# Factory board: sample calls

Every board call the manager makes, verbatim; fill the `<placeholders>`. Shapes and rules are in `protocol.md`; the order of the steps is in `SKILL.md`. The `Artifact`, `ArtifactData`, `ArtifactComments` and `SendMessage` calls were exercised against a live board with a manager session and a `claude --bg` worker; the `claude -p --cloud` doorbell was exercised with cloud workers in a factory run (2026-09), and on idle cloud agents with a second assignment (2026-11).

Placeholders: `<url>` the board URL, `<run key>` from `registry.py … artifact`, `<id>` an agent's worker id such as `w:a1` (`w:a1.r2` for a replacement session), `<asg>` an assignment id such as `a1-2`, `<worker key>` from `registry.py new-key`, `<now>` from `date -u +%Y-%m-%dT%H:%M:%SZ`, `<v>` the `version` your last read or write of that document returned.

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
  description: "Factory board for <owner/repo>: the current run's agents, reports, questions and messages.",
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
<!-- myspec-factory:start -->
- Board: https://claude.ai/artifact/<id>
<!-- myspec-factory:end -->
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

## Each agent start

Once per agent session (a replacement session gets its own five documents):

```
ArtifactData({
  action: "batch", url: "<url>",
  writes: [
    { op: "set", collection: "board", doc_id: "<id>",
      data: { worker_id: "<id>", agent: "a1", name: "Ada", agent_title: "Ada (a1)", rung: "opus/medium", status: "running",
              assignment: "a1-1", tasks: [4, 5, 7], title: "<summary>",
              branch: "factory/<bundle>/tasks-4-5-7", pr: null, verified_sha: null,
              queue: [[9, 10], [14]], merged: [],
              next: "Waiting for the first progress report", updated_at: "<now>" } },
    { op: "set", collection: "reports", doc_id: "<id>",
      data: { worker_id: "<id>", key: "<worker key>", assignment: "a1-1", tasks: [4, 5, 7], phase: "dispatched",
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

## Next assignment

The `assign` entry names the assignment; the full assignment message goes in the doorbell (§ Doorbell), because it is longer than a message's 2,000 characters. Card first, so the owner sees the new assignment and the shorter queue:

```
ArtifactData({
  action: "batch", url: "<url>",
  writes: [
    { op: "update", collection: "mail", doc_id: "sfm~<id>", if_version: <v>,
      data: { messages: { "004": { seq: 4, key: "<run key>", kind: "assign", re: null, tasks: [9, 10], needs: "none",
                                   text: "Assignment a1-2 for Ada: tasks 9, 10 (<summary>). Branch factory/<bundle>/tasks-9-10 from a fresh origin/<base>. The full assignment message is in this session.",
                                   at: "<now>" } },
              last_seq: 4, updated_at: "<now>" } },
    { op: "update", collection: "board", doc_id: "<id>", if_version: <v>,
      data: { status: "running", assignment: "a1-2", tasks: [9, 10], title: "<summary>",
              branch: "factory/<bundle>/tasks-9-10", pr: null, verified_sha: null, queue: [[14]],
              next: "Assignment a1-2 sent (sfm~<id>#4); waiting for its first progress report", updated_at: "<now>" } }
  ]
})
```

Rebalancing moves a group between two cards: update both `queue` arrays in one batch.

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

Check a sender: `registry.py … whois --from <id> --key <key from the entry>` prints `sfm` or the agent, and exits 1 on a mismatch or a replaced session.

## Answer

Append to the agent's inbox (`get` it first for `<v>` and `last_seq`; nested maps merge, so only the new entry is sent), and move your cursor in the same batch:

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
      data: { next: "Owner decided task 4 (sfm~<id>#2). Waiting for the agent's ack.", updated_at: "<now>" } }
  ]
})
```

Leave `origin` out when the answer is the manager's own. Kinds the manager sends: `assign`, `answer`, `decision`, `relay`, `steer`, `note`.

## Doorbell

The rule is in SKILL.md §5: a cloud agent is rung only with `claude -p … --cloud`, and the doorbell carries the whole instruction (for an `assign` entry: the whole assignment message, `dispatch` §5). Write it to a file first (a permission hook may block a command line that quotes a rebase or a lease-protected push):

```bash
cat > <scratchpad>/doorbell-<id>-2.md <<'EOF'
Software Factory Manager: decision sfm~<id>#2 for task 4 (also on the factory board): <the full decision>.
Do now: <what to change, and the exact commands when there are any>.
Then: one push, update the Factory report, re-request review from <reviewer>, and send an `ack` with re "sfm~<id>#2" on the board. Never merge.
EOF
cd <clone> && claude -p "$(cat <scratchpad>/doorbell-<id>-2.md)" --cloud <session_id> </dev/null
```

`</dev/null` keeps `claude -p` from waiting three seconds for stdin. It prints `Sent to cloud session.` with the `Session ID:` and `View:` lines.

A local `claude --bg` agent gets the same text through Remote Control instead:

```
SendMessage({ to: "<agent_name from ListAgents>", message: "<the same text>" })
```

The agent's `cursors/<id>.reads["sfm~<id>"]` reaching 2 proves it read the entry; its `ack` entry, or the push the message asked for, proves it acted.

## Comment threads

A signed reply (only when no automatic reply was posted, or as a follow-up that adds something new):

```
ArtifactComments({ action: "reply", url: "<url>", thread_id: "<thread id>",
                   text: "## Software Factory Manager\nSent to agent <id> as decision sfm~<id>#2: <the answer>.",
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

**After a merged assignment** (the agent stays): read the agent's documents again first (an `ack` or a final report may have landed since your last read), handle anything new, then in one batch record the merge on the card and drop the handled entries of your own mailbox to the agent (every entry its cursor has passed whose fact is recorded elsewhere). The agent trims its own mailbox to you at the start of its next assignment.

```
ArtifactData({ action: "get", url: "<url>", collection: "board",   doc_id: "<id>" })
ArtifactData({ action: "get", url: "<url>", collection: "mail",    doc_id: "sfm~<id>" })
ArtifactData({ action: "get", url: "<url>", collection: "cursors", doc_id: "<id>" })
ArtifactData({
  action: "batch", url: "<url>",
  writes: [
    { op: "update", collection: "board", doc_id: "<id>", if_version: <v>,
      data: { merged: [ /* earlier entries */ { assignment: "a1-1", tasks: [4, 5, 7], pr: 57, sha: "<short sha>" } ],
              next: "a1-1 merged in PR #57 (<short sha>)", updated_at: "<now>" } },
    { op: "update", collection: "mail", doc_id: "sfm~<id>", if_version: <v>,
      data: { messages: { "001": { "__delete__": true }, "002": { "__delete__": true } }, updated_at: "<now>" } }
  ]
})
```

`merged` is an array, so send the whole list (the card shows the last 10; keep at most 20).

**After an agent session is replaced or retired, or when the run closes**: read every document of that session again first: the agent may have written after your last read (an `ack`, its final report), and then a pin fails and nothing is deleted. An unpinned delete of an existing document is refused too, so pin each entry to the version this read returns:

```
ArtifactData({ action: "get", url: "<url>", collection: "board",   doc_id: "<id>" })
ArtifactData({ action: "get", url: "<url>", collection: "reports", doc_id: "<id>" })
ArtifactData({ action: "get", url: "<url>", collection: "mail",    doc_id: "<id>~sfm" })
ArtifactData({ action: "get", url: "<url>", collection: "mail",    doc_id: "sfm~<id>" })
ArtifactData({ action: "get", url: "<url>", collection: "cursors", doc_id: "<id>" })
ArtifactData({ action: "get", url: "<url>", collection: "cursors", doc_id: "sfm" })
```

Handle any entry you had not read (SKILL.md §5), then delete (`<v>` from these reads):

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

A replacement session's card (`w:a1.r2`) carries the slot's `merged` list over: copy it into the new card when you create it.

Drop one relay every agent has read:

```
ArtifactData({ action: "update", url: "<url>", collection: "mail", doc_id: "sfm~all-workers", if_version: <v>,
               data: { messages: { "003": { "__delete__": true } }, updated_at: "<now>" } })
```

## Close a run

After the per-agent cleanup (`history` is an array, so send the whole list: the previous entries plus the new one, at most 20):

```
ArtifactData({
  action: "batch", url: "<url>",
  writes: [
    { op: "delete", collection: "mail", doc_id: "sfm~all-workers", if_version: <v> },
    { op: "set", collection: "cursors", doc_id: "sfm", if_version: <v>,
      data: { reads: {}, threads: {}, updated_at: "<now>" } },
    { op: "update", collection: "run", doc_id: "meta", if_version: <v>,
      data: { status: "closed", updated_at: "<now>",
              history: [ /* earlier entries */ { repo: "<owner/repo>", bundle: "<bundle>", closed_at: "<now>",
                                                  summary: "<n> tasks merged in PRs #<a>, #<b>; follow-ups: <none | list>" } ] } }
  ]
})
ArtifactComments({ action: "watch", url: "<url>", on: false })
```

## Agent side

An agent's calls are in its brief (the dispatch skill's `references/worker-brief.md`, `## Factory board`): `get` then `update` of `mail/<id>~sfm` to send, `update` of `reports/<id>` at each checkpoint (its `assignment` field names the one it works on), `get` of `mail/sfm~<id>` and `mail/sfm~all-workers` plus an `update` of `cursors/<id>` to read, and at the start of each new assignment a trim of the entries the manager has read from `mail/<id>~sfm`. An agent never calls `Artifact` or writes a comment.
