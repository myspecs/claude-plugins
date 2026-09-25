#!/usr/bin/env python3
"""Read and update a factory session registry (.specs/<bundle>/factory-sessions.json).

Format: skills/dispatch/references/session-registry.md. Python 3 standard library only.
Writes are atomic (temp file + os.replace), keep unknown keys, and use indent=2.
A value that looks like a stream URL (contains "wss://" or "/realtime/v1/stream/") is refused
with exit 2: stream token URLs are never stored.

Usage (--file is required by every subcommand except `log` and `new-key`):
  registry.py show --file F [--session SEL | --last]
  registry.py add-session --file F --task "45,46,47" --title T --path cloud-cli --session-id S
                          --url U --branch B --started-at ISO [--notes N]
                          [--worker-id w:tasks-45-46-47 [--worker-key K]]   key generated when omitted
  registry.py set --file F --session SEL key=value ...
        keys: status, pr (int), branch, autofix, verified_sha, agent_name, cloud_title, worker_id,
              worker_key; value null -> null
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
        session; exit 1 when the id and key do not match the registry or the session was redispatched
  registry.py new-key                                    print a fresh worker key (for the brief, before
        add-session records it)
  registry.py note --file F --session SEL "text"         appends "; [HH:MMZ] text" to notes
  registry.py stream --file F --token-id X --prefix P --expires-at ISO [--event-types a,b] [--revoked-at ISO]
        replaces `stream` (last_seq null); the old one moves to `stream_history` (revoked_at set when given)
  registry.py stream-seq --file F N                      sets stream.last_seq only when N is greater
  registry.py policy --file F key=value ...              true/false -> bool, digits -> int, [..] -> JSON list
  registry.py contract --file F key "text"               sets contract_notes[key]
  registry.py log --run-log .specs/<bundle>/factory-run.md "text"   appends "- <ISO now> text"

SEL is a session index as shown by `show` (0-based), `last`, or a task string ("52", "45,46,47");
a single task number also matches the group or lane entry that carries it ("46" finds "45,46,47"),
and is read as an index only when no entry carries it. A task string matching several entries picks the newest.
Exit codes: 0 ok, 1 not found / bad input, 2 refused (stream URL) or usage error.
"""
import argparse
import datetime
import json
import os
import secrets
import sys
import tempfile

STATUSES = ("running", "pushed", "pr-open", "blocked", "merged", "failed", "redispatched")
SET_KEYS = ("status", "pr", "branch", "autofix", "verified_sha", "agent_name", "cloud_title",
            "worker_id", "worker_key")


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
        die(f"{path} does not exist; create it with {{\"project_id\": ..., \"bundle\": ..., \"sessions\": []}}")
    try:
        with open(path) as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        die(f"cannot read {path}: {e}")
    if not isinstance(data, dict):
        die(f"{path} is not a JSON object")
    data.setdefault("sessions", [])
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


def holds_task(s, sel):
    """True when the entry's task string equals sel, or sel is one task number the entry carries
    (a group's "4,5,7" list or a lane's `tasks`)."""
    want = sel.replace(" ", "")
    stored = str(s.get("task")).replace(" ", "")
    if stored == want:
        return True
    if not want.isdigit():
        return False
    return want in stored.split(",") or want in [str(t) for t in (s.get("tasks") or [])]


def find_session(data, sel):
    sessions = data["sessions"]
    if not sessions:
        die("no sessions in the registry")
    if sel == "last":
        return len(sessions) - 1
    if sel.isdigit() and int(sel) < len(sessions) and not any(holds_task(s, sel) for s in sessions):
        return int(sel)
    matches = [i for i, s in enumerate(sessions) if holds_task(s, sel)]
    if matches:
        return matches[-1]
    if sel.isdigit() and int(sel) < len(sessions):
        return int(sel)
    die(f"no session matches {sel!r} (use an index from `show`, `last`, or a task string)")


def new_key():
    return secrets.token_hex(4)


def short(v, n):
    s = "-" if v is None else str(v)
    return s if len(s) <= n else s[: n - 1] + "…"


def cmd_show(a):
    data = load(a.file)
    if a.last or a.session is not None:
        i = find_session(data, "last" if a.last else a.session)
        print(f"session [{i}]")
        print(json.dumps(data["sessions"][i], indent=2, ensure_ascii=False))
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
    print(f"{'#':>3}  {'task':<12} {'status':<12} {'pr':<8} {'verified':<10} {'worker_id':<20} session_id")
    for i, s in enumerate(data["sessions"]):
        pr = s.get("pr")
        if isinstance(pr, str) and "/pull/" in pr:
            pr = "#" + pr.rsplit("/", 1)[-1]
        elif isinstance(pr, int):
            pr = f"#{pr}"
        print(f"{i:>3}  {short(s.get('task'), 12):<12} {short(s.get('status'), 12):<12} {short(pr, 8):<8} "
              f"{short((s.get('verified_sha') or '-')[:8], 10):<10} {short(s.get('worker_id'), 20):<20} "
              f"{s.get('session_id') or '-'}")


def cmd_add_session(a):
    data = load(a.file)
    task = int(a.task) if a.task.isdigit() else a.task
    entry = {
        "task": task, "title": a.title, "path": a.path, "session_id": a.session_id,
        "agent_name": None, "url": a.url, "branch": a.branch, "started_at": a.started_at,
        "status": "running", "pr": None, "autofix": "unknown", "verified_sha": None,
        "notes": a.notes or "",
    }
    if a.worker_key and not a.worker_id:
        die("--worker-key needs --worker-id", 2)
    if a.worker_id:
        if not a.worker_id.startswith("w:"):
            die("--worker-id must start with 'w:' (for example w:tasks-45-46-47)", 2)
        if any(s.get("worker_id") == a.worker_id for s in data["sessions"]):
            die(f"worker id {a.worker_id} is already used; add a redispatch suffix such as .r2", 2)
        entry["worker_id"] = a.worker_id
        entry["worker_key"] = a.worker_key or new_key()
    guard(entry)
    data["sessions"].append(entry)
    save(a.file, data)
    extra = f" worker_id={entry['worker_id']} worker_key={entry['worker_key']}" if a.worker_id else ""
    print(f"added session [{len(data['sessions']) - 1}] task={task} status=running{extra}")


def cmd_set(a):
    data = load(a.file)
    i = find_session(data, a.session)
    s = data["sessions"][i]
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
        if k == "status" and val is not None and val not in STATUSES:
            die(f"status must be one of {', '.join(STATUSES)}")
        if k == "worker_id" and val is not None and not str(val).startswith("w:"):
            die("worker_id must start with 'w:' (for example w:tasks-45-46-47)", 2)
        s[k] = val
        print(f"[{i}] {k}={val}")
    save(a.file, data)


def cmd_note(a):
    data = load(a.file)
    guard(a.text)
    i = find_session(data, a.session)
    s = data["sessions"][i]
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("[%H:%MZ]")
    old = s.get("notes") or ""
    s["notes"] = f"{old}; {stamp} {a.text}" if old else f"{stamp} {a.text}"
    save(a.file, data)
    print(f"[{i}] note added")


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
    for i, s in enumerate(data["sessions"]):
        if s.get("worker_id") == a.sender:
            if s.get("worker_key") != a.key:
                die(f"from={a.sender} but the key does not match session [{i}]")
            if s.get("status") == "redispatched":
                die(f"from={a.sender}: session [{i}] was replaced by a redispatch; its messages are invalid")
            print(f"session [{i}] task={s.get('task')} status={s.get('status')}")
            return
    die(f"no session has worker_id {a.sender!r}")


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
    p = argparse.ArgumentParser(description="Factory session registry tool.",
                                formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    # --file is accepted before or after the subcommand.
    p.add_argument("--file", dest="global_file", help=argparse.SUPPRESS)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("show", parents=[common])
    g = s.add_mutually_exclusive_group()
    g.add_argument("--session")
    g.add_argument("--last", action="store_true")
    s.set_defaults(fn=cmd_show)

    s = sub.add_parser("add-session", parents=[common])
    for opt in ("--task", "--title", "--path", "--session-id", "--url", "--branch", "--started-at"):
        s.add_argument(opt, required=True)
    s.add_argument("--notes")
    s.add_argument("--worker-id")
    s.add_argument("--worker-key")
    s.set_defaults(fn=cmd_add_session)

    s = sub.add_parser("set", parents=[common])
    s.add_argument("--session", required=True)
    s.add_argument("pairs", nargs="+", metavar="key=value")
    s.set_defaults(fn=cmd_set)

    s = sub.add_parser("note", parents=[common])
    s.add_argument("--session", required=True)
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
