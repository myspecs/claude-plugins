#!/usr/bin/env python3
"""Read and update a factory team registry (.specs/<bundle>/factory-sessions.json).

Format: skills/dispatch/references/session-registry.md. Python 3 standard library only.
Writes are atomic (temp file + os.replace), keep unknown keys, and use indent=2.
A value that looks like a stream URL (contains "wss://" or "/realtime/v1/stream/") is refused
with exit 2: stream token URLs are never stored.

The registry holds the run's team: one `team` entry per agent session, each with its planned
`queue` of task groups and the `assignments` (one per pull request) it has been given.

Usage (--file is required by every subcommand except `log` and `new-key`):
  registry.py show --file F [--agent SEL | --assignment SEL]
  registry.py name --file F --agent a1 [--replace]   print the agent's name, its session title and worker id
        (tab-separated) for the session about to start: the slot's name when it has one, else the next free
        name from NAMES. Writes nothing; pass the title to `claude --cloud ... --name` and the name to add-agent
  registry.py add-agent --file F --agent a1 --path cloud-cli --session-id S --url U --started-at ISO
                        [--name Ada]                        default: the slot's name, else the next free one;
                        a name is unique to one slot for the run; the title is "<name> (<slot or slot.rN>)"
                        [--worker-key K]                    key generated when omitted; worker id is w:<agent>
                        [--model opus --effort medium [--off-ladder]]   rungs: sonnet/medium, opus/medium,
                        opus/high, opus/xhigh (references/model-and-effort.md); --off-ladder records a
                        setting the user chose
                        [--queue "12,13" "20" ...]          planned task groups, in order
                        [--replace]                         replace the agent's live session: the old entry
                        becomes `replaced`, its queue moves to the new one, the worker id gets .r2, .r3, ...
  registry.py agent --file F --agent SEL key=value ...
        keys: status (running, idle, ended, replaced, retired), session_id, url, path, agent_name,
              cloud_title, worker_key; value null -> null
  registry.py queue --file F --agent SEL [GROUP ...] [--clear]   replace the agent's planned queue
  registry.py move --file F --group "20,21" --to SEL     rebalance: take a planned (not started) group from
        whichever queue holds it and put it first in SEL's queue
  registry.py assign --file F --agent SEL --tasks "12,13" --title T --branch B [--assigned-at ISO]
        give the agent its next assignment (one pull request): appends it with status running, removes
        the group from the agent's queue, sets the agent running, prints the assignment id (a1-2)
  registry.py set --file F --assignment SEL key=value ...
        keys: status, pr (int), branch, title, autofix, verified_sha, merge_sha, hold_until, stacked_on;
              value null -> null
  registry.py note --file F (--agent SEL | --assignment SEL) "text"   appends "; [HH:MMZ] text" to notes
  registry.py artifact --file F --url https://claude.ai/... --published-at ISO [--run-key K]
        records the repository's factory board for this run (run key generated when omitted, kept
        when already set; never a stream URL) and in .specs/factory-board.json, a local fallback
        pointer every later bundle finds
  registry.py board --file F                             print the board URL to reuse: the repository's
        CLAUDE.md (or AGENTS.md) board block, else this registry's, else .specs/factory-board.json;
        the source goes to stderr; exit 1 when there is none. F need not exist yet
  registry.py claude-md --file F --url U [--target PATH] write or replace the myspec-factory block in the
        repository's CLAUDE.md (AGENTS.md when only that exists; created when neither does). The block
        holds only the board link, the one factory fact persisted in the repository; text outside
        the markers is never touched. Committing the file is a separate, agreed step.
        F need not exist yet: its path only locates the repository root
  registry.py whois --file F --from ID --key K           who wrote a board message: prints "sfm" or the
        agent; exit 1 when the id and key do not match the registry or the agent session was replaced
  registry.py new-key                                    print a fresh worker key (for the brief, before
        add-agent records it)
  registry.py stream --file F --token-id X --prefix P --expires-at ISO [--event-types a,b] [--revoked-at ISO]
        replaces `stream` (last_seq null); the old one moves to `stream_history` (revoked_at set when given)
  registry.py stream-seq --file F N                      sets stream.last_seq only when N is greater
  registry.py policy --file F key=value ...              true/false -> bool, digits -> int, [..] -> JSON list
  registry.py contract --file F key "text"               sets contract_notes[key]
  registry.py log --run-log .specs/<bundle>/factory-run.md "text"   appends "- <ISO now> text"

Agent SEL: a slot (a1: its live session), the agent's name (Ada, any case), a worker id (w:a1, w:a1.r2), a session id (session_...,
cse_...), an index as shown by `show` (0-based), or `last`.
Assignment SEL: an assignment id (a1-2), a pull request (pr:57 or #57), `last` (the newest assignment made),
or a task string ("52", "45,46,47"); a single task number also matches the assignment that carries it.
Assignments marked `reassigned` are skipped when another carries the task; when two live assignments carry
it, the command refuses and lists them: pass the assignment id instead.
Exit codes: 0 ok, 1 not found / bad input, 2 refused (stream URL) or usage error.
"""
import argparse
import datetime
import json
import os
import re
import secrets
import sys
import tempfile

AGENT_STATUSES = ("running", "idle", "ended", "replaced", "retired")
ASSIGNMENT_STATUSES = ("running", "pushed", "pr-open", "blocked", "merged", "failed", "reassigned")
AGENT_KEYS = ("status", "session_id", "url", "path", "agent_name", "cloud_title", "worker_key")
# Person-style agent names (computing pioneers), handed out in order; a slot keeps its name for the run.
NAMES = ("Ada", "Linus", "Grace", "Alan", "Barbara", "Dennis", "Margaret", "Ken", "Radia", "Edsger",
         "Frances", "Donald", "Katherine", "John", "Hedy", "Tim", "Annie", "Guido", "Jean", "Bjarne")
NAME_RE = re.compile(r"^[A-Z][A-Za-z]{1,19}$")
SET_KEYS = ("status", "pr", "branch", "title", "autofix", "verified_sha", "merge_sha", "hold_until",
            "stacked_on")
LADDER = (("sonnet", "medium"), ("opus", "medium"), ("opus", "high"), ("opus", "xhigh"))
AGENT_RE = re.compile(r"^a[1-9][0-9]*$")


def die(msg, code=1):
    print(f"registry: {msg}", file=sys.stderr)
    sys.exit(code)


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def guard(*values):
    """Refuse anything that looks like a stream URL, wherever it would be written."""
    for v in values:
        if isinstance(v, str) and ("wss://" in v or "/realtime/v1/stream/" in v):
            die("refused: value looks like a stream URL; stream URLs are never stored "
                "(keep only token id, prefix, expiry and last seq)", 2)
        if isinstance(v, (list, tuple)):
            guard(*v)
        if isinstance(v, dict):
            guard(*v.keys(), *v.values())


def load(path):
    if not path:
        die("--file is required (.specs/<bundle>/factory-sessions.json)", 2)
    if not os.path.exists(path):
        die(f"{path} does not exist; create it with {{\"project_id\": ..., \"bundle\": ..., \"team\": []}}")
    try:
        with open(path) as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        die(f"cannot read {path}: {e}")
    if not isinstance(data, dict):
        die(f"{path} is not a JSON object")
    if data.get("sessions"):
        print("registry: note: this registry has 1.x `sessions` entries (one worker per group); they are kept "
              "but not read. Finish or close those pull requests by hand; the team lives under `team`",
              file=sys.stderr)
    data.setdefault("team", [])
    return data


def save(path, data):
    # Only new values are guarded (see guard calls); existing content is kept as it is.
    d = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(prefix=".factory-sessions.", suffix=".tmp", dir=d)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        if os.path.exists(path):
            os.chmod(tmp, os.stat(path).st_mode & 0o7777)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def parse_scalar(v, policy=False):
    if v == "null":
        return None
    if policy:
        if v in ("true", "false"):
            return v == "true"
        if v.startswith("["):
            try:
                return json.loads(v)
            except ValueError:
                die(f"not a JSON list: {v}")
    if v.lstrip("-").isdigit():
        return int(v)
    return v


def pairs(items):
    out = []
    for it in items:
        if "=" not in it:
            die(f"expected key=value, got {it!r}", 2)
        k, v = it.split("=", 1)
        out.append((k.strip(), v))
    return out


def norm_group(g):
    """'12, 13' -> '12,13'; a bare number stays a string."""
    parts = [p.strip() for p in str(g).split(",") if p.strip()]
    if not parts or not all(p.replace(".", "").isdigit() for p in parts):
        die(f"not a task list: {g!r} (expected numbers such as 12 or 12,13)", 2)
    return ",".join(parts)


def team_of(data):
    return data["team"]


def slot_name(data, agent):
    for e in team_of(data):
        if e.get("agent") == agent and e.get("name"):
            return e["name"]
    return None


def pick_name(data, agent, wanted=None):
    taken = {e.get("name", "").lower(): e.get("agent") for e in team_of(data) if e.get("name")}
    own = slot_name(data, agent)
    if wanted:
        if not NAME_RE.match(wanted):
            die(f"--name must be one capitalised word of letters (for example Ada), got {wanted!r}", 2)
        holder = taken.get(wanted.lower())
        if holder and holder != agent:
            die(f"name {wanted} is already agent {holder}'s; agent names are unique for the run", 2)
        if own and own != wanted:
            die(f"agent {agent} is named {own}; a replacement session keeps the slot's name", 2)
        return wanted
    if own:
        return own
    for n in NAMES:
        if n.lower() not in taken:
            return n
    i = 2
    while f"{NAMES[0]}{i}".lower() in taken:
        i += 1
    return f"{NAMES[0]}{i}"


def worker_suffix(data, agent):
    n = sum(1 for e in team_of(data) if e.get("agent") == agent)
    return agent if n == 0 else f"{agent}.r{n + 1}"


def describe_agent(i, e):
    return (f"[{i}] agent={e.get('agent')} name={e.get('name') or '-'} worker_id={e.get('worker_id')} status={e.get('status')} "
            f"session_id={e.get('session_id') or '-'}")


def find_agent(data, sel):
    team = team_of(data)
    if not team:
        die("no agents in the registry")
    if sel == "last":
        return len(team) - 1
    if sel.startswith(("session_", "cse_", "w:")):
        key = "worker_id" if sel.startswith("w:") else "session_id"
        hits = [i for i, e in enumerate(team) if e.get(key) == sel]
        if len(hits) == 1:
            return hits[0]
        if not hits:
            die(f"no agent has {key} {sel!r}")
        die(f"{len(hits)} agents have {key} {sel!r}: " + "; ".join(describe_agent(i, team[i]) for i in hits)
            + ". Pass the index instead")
    if AGENT_RE.match(sel):
        hits = [i for i, e in enumerate(team) if e.get("agent") == sel]
        if not hits:
            die(f"no agent {sel!r}")
        live = [i for i in hits if team[i].get("status") != "replaced"]
        if len(live) > 1:
            die(f"agent {sel!r} has {len(live)} live sessions: " + "; ".join(describe_agent(i, team[i]) for i in live)
                + ". Pass the worker id instead")
        return live[0] if live else hits[-1]
    if sel.isdigit() and int(sel) < len(team):
        return int(sel)
    named = [e.get("agent") for e in team if (e.get("name") or "").lower() == sel.lower()]
    if named:
        return find_agent(data, named[0])
    die(f"no agent matches {sel!r} (use a1, the agent's name, a worker id, a session id, an index from `show`, or `last`)")


def all_assignments(data):
    for i, e in enumerate(team_of(data)):
        for j, s in enumerate(e.get("assignments") or []):
            yield i, j, s


def carries(s, want):
    stored = norm_group(s.get("tasks"))
    if stored == want:
        return True
    return "," not in want and want in stored.split(",")


def describe_assignment(i, j, s):
    return f"{s.get('id')} tasks={s.get('tasks')} status={s.get('status')} pr={s.get('pr') or '-'}"


def find_assignment(data, sel):
    rows = list(all_assignments(data))
    if not rows:
        die("no assignments in the registry")
    if sel == "last":
        return max(rows, key=lambda r: (r[2].get("seq") or 0, r[2].get("assigned_at") or ""))[:2]
    if re.match(r"^a[1-9][0-9]*-[0-9]+$", sel):
        hits = [r for r in rows if r[2].get("id") == sel]
        if not hits:
            die(f"no assignment {sel!r}")
        return hits[0][:2]
    m = re.match(r"^(?:pr:|#)([0-9]+)$", sel)
    if m:
        n = int(m.group(1))
        hits = [r for r in rows if r[2].get("pr") == n]
        if len(hits) > 1:
            # A replacement session continues the failed session's pull request: prefer the live entry.
            live = [r for r in hits if r[2].get("status") not in ("reassigned", "failed")]
            hits = live or hits
        if len(hits) == 1:
            return hits[0][:2]
        if not hits:
            die(f"no assignment has pr {n}")
        die(f"{len(hits)} assignments have pr {n}: " + "; ".join(describe_assignment(*h) for h in hits))
    want = norm_group(sel)
    hits = [r for r in rows if carries(r[2], want)]
    if not hits:
        die(f"no assignment matches {sel!r} (use an assignment id such as a1-2, pr:N, `last`, or a task string)")
    live = [r for r in hits if r[2].get("status") != "reassigned"]
    if len(live) == 1:
        return live[0][:2]
    if not live:
        return hits[-1][:2]
    # Guessing here once wrote a verified_sha onto the wrong entry: refuse instead.
    die(f"{sel!r} matches {len(live)} assignments: " + "; ".join(describe_assignment(*r) for r in live)
        + ". Pass the assignment id instead")


def new_key():
    return secrets.token_hex(4)


def short(v, n):
    s = "-" if v is None else str(v)
    return s if len(s) <= n else s[: n - 1] + "…"


def cmd_show(a):
    data = load(a.file)
    if a.agent is not None:
        i = find_agent(data, a.agent)
        print(f"agent [{i}]")
        print(json.dumps(team_of(data)[i], indent=2, ensure_ascii=False))
        return
    if a.assignment is not None:
        i, j = find_assignment(data, a.assignment)
        print(f"assignment of agent [{i}] {team_of(data)[i].get('worker_id')}")
        print(json.dumps(team_of(data)[i]["assignments"][j], indent=2, ensure_ascii=False))
        return
    print(f"bundle={data.get('bundle', '-')} project_id={data.get('project_id', '-')}")
    for k, v in (data.get("policy") or {}).items():
        if not isinstance(v, (dict, list)):
            print(f"policy.{k}={short(v, 100)}")
        elif isinstance(v, list):
            print(f"policy.{k}={','.join(map(str, v))}")
        else:
            print(f"policy.{k}={{{', '.join(v.keys())}}}")
    art = data.get("artifact")
    if art:
        print(f"artifact url={art.get('url')} run_key={art.get('run_key')} published_at={art.get('published_at')}")
    st = data.get("stream")
    if st:
        print(f"stream token_id={st.get('token_id')} prefix={st.get('token_prefix')} expires_at={st.get('expires_at')} "
              f"last_seq={st.get('last_seq')} revoked_at={st.get('revoked_at')} event_types={len(st.get('event_types') or [])}")
    print(f"stream_history={len(data.get('stream_history') or [])} contract_notes={len(data.get('contract_notes') or {})}"
          f" files={len(data.get('files') or {})}")
    for i, e in enumerate(team_of(data)):
        rung = f"{e.get('model') or '-'}/{e.get('effort') or '-'}"
        queue = " | ".join(e.get("queue") or []) or "-"
        print(f"[{i}] {e.get('worker_id')} {e.get('title') or e.get('name') or '-'} status={e.get('status')} rung={rung} "
              f"session_id={e.get('session_id') or '-'}")
        print(f"     queue: {queue}")
        for s in e.get("assignments") or []:
            pr = s.get("pr")
            pr = f"#{pr}" if isinstance(pr, int) else short(pr, 8)
            print(f"     {short(s.get('id'), 7):<7} {short(s.get('tasks'), 14):<14} {short(s.get('status'), 11):<11} "
                  f"{pr:<7} verified={short((s.get('verified_sha') or '-')[:8], 8)}")


def check_rung(a):
    if (a.model is None) != (a.effort is None):
        die("--model and --effort go together", 2)
    if a.model is not None and (a.model, a.effort) not in LADDER and not a.off_ladder:
        rungs = ", ".join(f"{m}/{e}" for m, e in LADDER)
        die(f"{a.model}/{a.effort} is not on the ladder ({rungs}); pass --off-ladder when the user chose it", 2)


def cmd_add_agent(a):
    data = load(a.file)
    if not AGENT_RE.match(a.agent):
        die("--agent must be a1, a2, ... (the team slot)", 2)
    check_rung(a)
    team = team_of(data)
    same = [i for i, e in enumerate(team) if e.get("agent") == a.agent]
    live = [i for i in same if team[i].get("status") != "replaced"]
    queue = [norm_group(g) for g in (a.queue or [])]
    if live and not a.replace:
        die(f"agent {a.agent} already has a live session ({describe_agent(live[0], team[live[0]])}); "
            "pass --replace to replace it, or pick the next agent name", 2)
    if a.replace and not live:
        die(f"agent {a.agent} has no live session to replace", 2)
    name = pick_name(data, a.agent, a.name)
    suffix = worker_suffix(data, a.agent)
    worker_id = f"w:{suffix}"
    entry = {
        "agent": a.agent, "name": name, "title": f"{name} ({suffix})",
        "worker_id": worker_id, "worker_key": a.worker_key or new_key(),
        "session_id": a.session_id, "url": a.url, "path": a.path, "agent_name": None,
        "started_at": a.started_at, "status": "idle", "queue": queue, "assignments": [], "notes": a.notes or "",
    }
    if a.model is not None:
        entry["model"] = a.model
        entry["effort"] = a.effort
    guard(entry)
    old = None
    if a.replace:
        old = team[live[0]]
        if not queue:
            entry["queue"] = list(old.get("queue") or [])
        old["queue"] = []
        old["status"] = "replaced"
    team.append(entry)
    save(a.file, data)
    if old:
        open_ = [x for x in old.get("assignments") or [] if x.get("status") in ("running", "pushed", "pr-open", "blocked")]
        for x in open_:
            print(f"registry: note: {x.get('id')} (tasks {x.get('tasks')}, status {x.get('status')}) is still open on "
                  f"{old['worker_id']}: set it failed or reassigned, then assign what is left to {worker_id} "
                  "(it may continue the same branch and pull request)", file=sys.stderr)
    extra = f" (replaces {old['worker_id']}; queue moved)" if old else ""
    print(f"added agent [{len(team) - 1}] {worker_id} \"{entry['title']}\" worker_key={entry['worker_key']} "
          f"queue={' | '.join(entry['queue']) or '-'}{extra}")


def cmd_name(a):
    data = load(a.file)
    if not AGENT_RE.match(a.agent):
        die("--agent must be a1, a2, ... (the team slot)", 2)
    team = team_of(data)
    live = [e for e in team if e.get("agent") == a.agent and e.get("status") != "replaced"]
    if live and not a.replace:
        die(f"agent {a.agent} already has a live session; pass --replace for its replacement's title", 2)
    if a.replace and not live:
        die(f"agent {a.agent} has no live session to replace", 2)
    name = pick_name(data, a.agent)
    suffix = worker_suffix(data, a.agent)
    print(f"{name}\t{name} ({suffix})\tw:{suffix}")


def cmd_agent(a):
    data = load(a.file)
    i = find_agent(data, a.agent)
    e = team_of(data)[i]
    for k, v in pairs(a.pairs):
        if k not in AGENT_KEYS:
            die(f"cannot set {k!r} on an agent; allowed: {', '.join(AGENT_KEYS)} (queue: use `queue`)", 2)
        guard(v)
        val = None if v == "null" else v
        if k == "status" and val is not None and val not in AGENT_STATUSES:
            die(f"agent status must be one of {', '.join(AGENT_STATUSES)}")
        e[k] = val
        print(f"[{i}] {e.get('worker_id')} {k}={val}")
    save(a.file, data)


def cmd_queue(a):
    data = load(a.file)
    i = find_agent(data, a.agent)
    e = team_of(data)[i]
    if a.clear and a.groups:
        die("pass groups or --clear, not both", 2)
    groups = [] if a.clear else [norm_group(g) for g in a.groups]
    if not a.clear and not groups:
        die("give the planned groups in order (\"12,13\" \"20\"), or --clear", 2)
    e["queue"] = groups
    warn_carried(data, groups, skip=None, planned=(i,))
    save(a.file, data)
    print(f"[{i}] {e.get('worker_id')} queue={' | '.join(groups) or '-'}")


def cmd_move(a):
    data = load(a.file)
    group = norm_group(a.group)
    to = find_agent(data, a.to)
    team = team_of(data)
    src = [i for i, e in enumerate(team) if group in (e.get("queue") or [])]
    if not src:
        die(f"group {group} is in no agent's queue (a started group is never moved; reassign it after a failure)")
    if len(src) > 1:
        die(f"group {group} is in {len(src)} queues: " + "; ".join(describe_agent(i, team[i]) for i in src))
    if src[0] == to:
        die(f"group {group} is already in {team[to].get('worker_id')}'s queue")
    if team[to].get("status") in ("replaced", "retired", "ended"):
        die(f"{team[to].get('worker_id')} is {team[to].get('status')}; pick a live agent")
    team[src[0]]["queue"].remove(group)
    team[to].setdefault("queue", []).insert(0, group)
    save(a.file, data)
    print(f"moved {group} from {team[src[0]].get('worker_id')} to {team[to].get('worker_id')} (first in its queue)")


def warn_carried(data, groups, skip, planned=()):
    for g in groups:
        for t in g.split(","):
            for i, j, s in all_assignments(data):
                if (i, j) != skip and s.get("status") not in ("reassigned", "failed") and carries(s, t):
                    print(f"registry: note: task {t} is also carried by assignment {describe_assignment(i, j, s)}",
                          file=sys.stderr)
            for i, e in enumerate(team_of(data)):
                if i in planned or e.get("status") == "replaced":
                    continue
                for q in e.get("queue") or []:
                    if t in q.split(","):
                        print(f"registry: note: task {t} is also planned in {e.get('worker_id')}'s queue ({q})",
                              file=sys.stderr)


def cmd_assign(a):
    data = load(a.file)
    i = find_agent(data, a.agent)
    e = team_of(data)[i]
    if e.get("status") in ("replaced", "retired", "ended"):
        die(f"{e.get('worker_id')} is {e.get('status')}; assign to a live agent session", 2)
    group = norm_group(a.tasks)
    n = 1 + sum(len(x.get("assignments") or []) for x in team_of(data) if x.get("agent") == e.get("agent"))
    seq = 1 + max([x.get("seq") or 0 for _, _, x in all_assignments(data)] or [0])
    asg = {
        "id": f"{e.get('agent')}-{n}", "seq": seq, "tasks": group, "title": a.title, "branch": a.branch,
        "assigned_at": a.assigned_at or now_iso(), "status": "running", "pr": None, "autofix": "unknown",
        "verified_sha": None, "merge_sha": None, "hold_until": None, "stacked_on": None, "notes": a.notes or "",
    }
    guard(asg)
    queue = e.setdefault("queue", [])
    if group in queue:
        queue.remove(group)
    e.setdefault("assignments", []).append(asg)
    warn_carried(data, [group], skip=(i, len(e["assignments"]) - 1), planned=(i,))
    e["status"] = "running"
    save(a.file, data)
    print(f"assigned {asg['id']} tasks={group} to {e.get('worker_id')} (queue left: {' | '.join(queue) or '-'})")


def cmd_set(a):
    data = load(a.file)
    i, j = find_assignment(data, a.assignment)
    s = team_of(data)[i]["assignments"][j]
    for k, v in pairs(a.pairs):
        if k not in SET_KEYS:
            die(f"cannot set {k!r}; allowed: {', '.join(SET_KEYS)}", 2)
        guard(v)
        if v == "null":
            val = None
        elif k == "pr":
            if not v.lstrip("#").isdigit():
                die(f"pr must be a number, got {v!r}")
            val = int(v.lstrip("#"))
        else:
            val = v
        if k == "status" and val is not None and val not in ASSIGNMENT_STATUSES:
            die(f"assignment status must be one of {', '.join(ASSIGNMENT_STATUSES)}")
        s[k] = val
        print(f"{s.get('id')} {k}={val}")
    save(a.file, data)


def cmd_note(a):
    data = load(a.file)
    guard(a.text)
    if (a.agent is None) == (a.assignment is None):
        die("pass exactly one of --agent and --assignment", 2)
    if a.agent is not None:
        i = find_agent(data, a.agent)
        target, label = team_of(data)[i], team_of(data)[i].get("worker_id")
    else:
        i, j = find_assignment(data, a.assignment)
        target = team_of(data)[i]["assignments"][j]
        label = target.get("id")
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("[%H:%MZ]")
    old = target.get("notes") or ""
    target["notes"] = f"{old}; {stamp} {a.text}" if old else f"{stamp} {a.text}"
    save(a.file, data)
    print(f"{label} note added")


def cmd_stream(a):
    data = load(a.file)
    guard(a.token_id, a.prefix, a.expires_at, a.event_types, a.revoked_at)
    old = data.get("stream")
    if old:
        if a.revoked_at:
            old["revoked_at"] = a.revoked_at
        data.setdefault("stream_history", []).append(old)
    new = {"token_id": a.token_id, "token_prefix": a.prefix, "expires_at": a.expires_at}
    if a.event_types:
        new["event_types"] = [t.strip() for t in a.event_types.split(",") if t.strip()]
    new["last_seq"] = None  # each token has its own buffer; the old cursor does not apply
    new["revoked_at"] = None
    data["stream"] = new
    save(a.file, data)
    print(f"stream prefix={a.prefix} expires_at={a.expires_at}" + (f" (old {old.get('token_prefix')} moved to history)" if old else ""))


def cmd_stream_seq(a):
    data = load(a.file)
    st = data.get("stream")
    if not st:
        die("no stream recorded")
    cur = st.get("last_seq") or 0
    if a.seq > cur:
        st["last_seq"] = a.seq
        save(a.file, data)
        print(f"last_seq={a.seq}")
    else:
        print(f"last_seq={cur} (unchanged)")


def cmd_policy(a):
    data = load(a.file)
    pol = data.setdefault("policy", {})
    for k, v in pairs(a.pairs):
        guard(k, v)
        pol[k] = parse_scalar(v, policy=True)
        print(f"policy.{k}={json.dumps(pol[k])}")
    save(a.file, data)


def cmd_contract(a):
    data = load(a.file)
    guard(a.key, a.text)
    data.setdefault("contract_notes", {})[a.key] = a.text
    save(a.file, data)
    print(f"contract_notes.{a.key} set")


def cmd_artifact(a):
    data = load(a.file)
    guard(a.url, a.published_at, a.run_key)
    if not a.url.startswith("https://claude.ai/"):
        die("--url must be the board's claude.ai artifact URL", 2)
    old = data.get("artifact") or {}
    run_key = a.run_key or old.get("run_key") or new_key()
    data["artifact"] = {"url": a.url, "published_at": a.published_at, "run_key": run_key,
                        "protocol": "factory-board/1"}
    save(a.file, data)
    # The board is shared by every bundle of the repository: keep a pointer next to the bundle folders.
    shared = shared_board_path(a.file)
    pointer = {"url": a.url, "protocol": "factory-board/1", "recorded_at": now_iso(),
               "last_bundle": data.get("bundle")}
    save(shared, pointer)
    print(f"artifact url={a.url} run_key={run_key} (shared pointer {shared})")


BOARD_START = "<!-- myspec-factory:start -->"
BOARD_END = "<!-- myspec-factory:end -->"


def repo_root(registry_file):
    # .specs/<bundle>/factory-sessions.json -> the repository root
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(registry_file))))


def instruction_files(registry_file):
    root = repo_root(registry_file)
    return [os.path.join(root, n) for n in ("CLAUDE.md", "AGENTS.md")]


def board_block(url):
    return "\n".join([BOARD_START, f"- Board: {url}", BOARD_END])


def url_in_block(text):
    if BOARD_START not in text or BOARD_END not in text:
        return None
    block = text.split(BOARD_START, 1)[1].split(BOARD_END, 1)[0]
    for line in block.splitlines():
        line = line.strip()
        if line.startswith("- Board:"):
            url = line[len("- Board:"):].strip()
            return url or None
    return None


def shared_board_path(registry_file):
    # .specs/<bundle>/factory-sessions.json -> .specs/factory-board.json
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(registry_file))), "factory-board.json")


def cmd_board(a):
    if not a.file:
        die("--file is required (.specs/<bundle>/factory-sessions.json)", 2)
    # The registry may not exist yet (setup, a new bundle): its path still locates the repository.
    data = load(a.file) if os.path.exists(a.file) else {}
    url = None
    for path in instruction_files(a.file):
        if os.path.exists(path):
            with open(path) as f:
                url = url_in_block(f.read())
            if url:
                print(f"board from {path}", file=sys.stderr)
                break
    if not url:
        url = (data.get("artifact") or {}).get("url")
        if url:
            print(f"board from {a.file} (not yet in CLAUDE.md)", file=sys.stderr)
    if not url:
        shared = shared_board_path(a.file)
        if os.path.exists(shared):
            try:
                with open(shared) as f:
                    url = (json.load(f) or {}).get("url")
            except (OSError, ValueError) as e:
                die(f"cannot read {shared}: {e}")
            if url:
                print(f"board from {shared} (not yet in CLAUDE.md)", file=sys.stderr)
    if not url:
        die("no factory board recorded; look with Artifact list, then publish one")
    print(url)


def cmd_claude_md(a):
    if not a.file:
        die("--file is required (.specs/<bundle>/factory-sessions.json); it locates the repository root", 2)
    guard(a.url)
    if not a.url.startswith("https://claude.ai/"):
        die("--url must be the board's claude.ai artifact URL", 2)
    if a.target:
        path = a.target
    else:
        claude_md, agents_md = instruction_files(a.file)
        path = agents_md if (not os.path.exists(claude_md) and os.path.exists(agents_md)) else claude_md
    text = ""
    if os.path.exists(path):
        with open(path) as f:
            text = f.read()
    block = board_block(a.url)
    if BOARD_START in text and BOARD_END in text:
        before = text.split(BOARD_START, 1)[0]
        after = text.split(BOARD_END, 1)[1]
        new = before + block + after
    else:
        new = (text.rstrip("\n") + "\n\n" if text.strip() else "") + block + "\n"
    if new == text:
        print(f"{path} unchanged (board {a.url})")
        return
    with open(path, "w") as f:
        f.write(new)
    print(f"{path} updated with board {a.url}; commit it only with the user's agreement")


def cmd_whois(a):
    data = load(a.file)
    if a.sender == "sfm":
        art = data.get("artifact") or {}
        if art.get("run_key") and art.get("run_key") == a.key:
            print("sfm")
            return
        die(f"from=sfm but the key does not match artifact.run_key")
    for i, e in enumerate(team_of(data)):
        if e.get("worker_id") == a.sender:
            if e.get("worker_key") != a.key:
                die(f"from={a.sender} but the key does not match agent [{i}]")
            if e.get("status") == "replaced":
                die(f"from={a.sender}: agent [{i}] was replaced by a new session; its messages are invalid")
            cur = [s for s in e.get("assignments") or [] if s.get("status") not in ("merged", "reassigned")]
            now = ",".join(s.get("id") for s in cur) or "none"
            print(f"agent [{i}] {a.sender} ({e.get('name') or '-'}) status={e.get('status')} open assignments={now}")
            return
    die(f"no agent has worker_id {a.sender!r}")


def cmd_new_key(a):
    print(new_key())


def cmd_log(a):
    guard(a.text)
    with open(a.run_log, "a") as f:
        f.write(f"- {now_iso()} {a.text}\n")
    print(f"logged to {a.run_log}")


def main():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--file", help=".specs/<bundle>/factory-sessions.json (required)")
    p = argparse.ArgumentParser(description="Factory team registry tool.",
                                formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    # --file is accepted before or after the subcommand.
    p.add_argument("--file", dest="global_file", help=argparse.SUPPRESS)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("show", parents=[common])
    g = s.add_mutually_exclusive_group()
    g.add_argument("--agent")
    g.add_argument("--assignment")
    s.set_defaults(fn=cmd_show)

    s = sub.add_parser("add-agent", parents=[common])
    for opt in ("--agent", "--path", "--session-id", "--url", "--started-at"):
        s.add_argument(opt, required=True)
    s.add_argument("--notes")
    s.add_argument("--worker-key")
    s.add_argument("--model")
    s.add_argument("--effort")
    s.add_argument("--off-ladder", action="store_true")
    s.add_argument("--queue", nargs="+")
    s.add_argument("--replace", action="store_true")
    s.add_argument("--name")
    s.set_defaults(fn=cmd_add_agent)

    s = sub.add_parser("name", parents=[common])
    s.add_argument("--agent", required=True)
    s.add_argument("--replace", action="store_true")
    s.set_defaults(fn=cmd_name)

    s = sub.add_parser("agent", parents=[common])
    s.add_argument("--agent", required=True)
    s.add_argument("pairs", nargs="+", metavar="key=value")
    s.set_defaults(fn=cmd_agent)

    s = sub.add_parser("queue", parents=[common])
    s.add_argument("--agent", required=True)
    s.add_argument("groups", nargs="*", metavar="GROUP")
    s.add_argument("--clear", action="store_true")
    s.set_defaults(fn=cmd_queue)

    s = sub.add_parser("move", parents=[common])
    s.add_argument("--group", required=True)
    s.add_argument("--to", required=True)
    s.set_defaults(fn=cmd_move)

    s = sub.add_parser("assign", parents=[common])
    s.add_argument("--agent", required=True)
    s.add_argument("--tasks", required=True)
    s.add_argument("--title", required=True)
    s.add_argument("--branch", required=True)
    s.add_argument("--assigned-at")
    s.add_argument("--notes")
    s.set_defaults(fn=cmd_assign)

    s = sub.add_parser("set", parents=[common])
    s.add_argument("--assignment", required=True)
    s.add_argument("pairs", nargs="+", metavar="key=value")
    s.set_defaults(fn=cmd_set)

    s = sub.add_parser("note", parents=[common])
    g = s.add_mutually_exclusive_group(required=True)
    g.add_argument("--agent")
    g.add_argument("--assignment")
    s.add_argument("text")
    s.set_defaults(fn=cmd_note)

    s = sub.add_parser("stream", parents=[common])
    s.add_argument("--token-id", required=True)
    s.add_argument("--prefix", required=True)
    s.add_argument("--expires-at", required=True)
    s.add_argument("--event-types")
    s.add_argument("--revoked-at")
    s.set_defaults(fn=cmd_stream)

    s = sub.add_parser("stream-seq", parents=[common])
    s.add_argument("seq", type=int)
    s.set_defaults(fn=cmd_stream_seq)

    s = sub.add_parser("policy", parents=[common])
    s.add_argument("pairs", nargs="+", metavar="key=value")
    s.set_defaults(fn=cmd_policy)

    s = sub.add_parser("contract", parents=[common])
    s.add_argument("key")
    s.add_argument("text")
    s.set_defaults(fn=cmd_contract)

    s = sub.add_parser("artifact", parents=[common])
    s.add_argument("--url", required=True)
    s.add_argument("--published-at", required=True)
    s.add_argument("--run-key")
    s.set_defaults(fn=cmd_artifact)

    s = sub.add_parser("board", parents=[common])
    s.set_defaults(fn=cmd_board)

    s = sub.add_parser("claude-md", parents=[common])
    s.add_argument("--url", required=True)
    s.add_argument("--target")
    s.set_defaults(fn=cmd_claude_md)

    s = sub.add_parser("whois", parents=[common])
    s.add_argument("--from", dest="sender", required=True)
    s.add_argument("--key", required=True)
    s.set_defaults(fn=cmd_whois)

    s = sub.add_parser("new-key")
    s.set_defaults(fn=cmd_new_key)

    s = sub.add_parser("log")
    s.add_argument("--run-log", required=True)
    s.add_argument("text")
    s.set_defaults(fn=cmd_log)

    a = p.parse_args()
    if getattr(a, "file", None) is None and a.global_file:
        a.file = a.global_file
    a.fn(a)


if __name__ == "__main__":
    main()
