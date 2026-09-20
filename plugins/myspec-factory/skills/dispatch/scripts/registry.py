#!/usr/bin/env python3
"""Read and update a factory session registry (.specs/<bundle>/factory-sessions.json).

Format: skills/dispatch/references/session-registry.md. Python 3 standard library only.
Writes are atomic (temp file + os.replace), keep unknown keys, and use indent=2.
A value that looks like a stream URL (contains "wss://" or "/realtime/v1/stream/") is refused
with exit 2: stream token URLs are never stored.

Usage (--file is required by every subcommand except `log`):
  registry.py show --file F [--session SEL | --last]
  registry.py add-session --file F --task "45,46,47" --title T --path cloud-cli --session-id S
                          --url U --branch B --started-at ISO [--notes N]
  registry.py set --file F --session SEL key=value ...
        keys: status, pr (int), branch, autofix, verified_sha, agent_name, cloud_title; value null -> null
  registry.py note --file F --session SEL "text"         appends "; [HH:MMZ] text" to notes
  registry.py stream --file F --token-id X --prefix P --expires-at ISO [--event-types a,b] [--revoked-at ISO]
        replaces `stream` (last_seq null); the old one moves to `stream_history` (revoked_at set when given)
  registry.py stream-seq --file F N                      sets stream.last_seq only when N is greater
  registry.py policy --file F key=value ...              true/false -> bool, digits -> int, [..] -> JSON list
  registry.py contract --file F key "text"               sets contract_notes[key]
  registry.py log --run-log .specs/<bundle>/factory-run.md "text"   appends "- <ISO now> text"

SEL is a session index as shown by `show` (0-based), `last`, or a task string ("52", "45,46,47");
a task string matching several entries picks the newest.
Exit codes: 0 ok, 1 not found / bad input, 2 refused (stream URL) or usage error.
"""
import argparse
import datetime
import json
import os
import sys
import tempfile

STATUSES = ("running", "pushed", "pr-open", "blocked", "merged", "failed", "redispatched")
SET_KEYS = ("status", "pr", "branch", "autofix", "verified_sha", "agent_name", "cloud_title")


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


def find_session(data, sel):
    sessions = data["sessions"]
    if not sessions:
        die("no sessions in the registry")
    if sel == "last":
        return len(sessions) - 1
    if sel.isdigit() and int(sel) < len(sessions) and not any(str(s.get("task")) == sel for s in sessions):
        return int(sel)
    matches = [i for i, s in enumerate(sessions) if str(s.get("task")).replace(" ", "") == sel.replace(" ", "")]
    if matches:
        return matches[-1]
    if sel.isdigit() and int(sel) < len(sessions):
        return int(sel)
    die(f"no session matches {sel!r} (use an index from `show`, `last`, or a task string)")


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
    st = data.get("stream")
    if st:
        print(f"stream token_id={st.get('token_id')} prefix={st.get('token_prefix')} expires_at={st.get('expires_at')} "
              f"last_seq={st.get('last_seq')} revoked_at={st.get('revoked_at')} event_types={len(st.get('event_types') or [])}")
    print(f"stream_history={len(data.get('stream_history') or [])} contract_notes={len(data.get('contract_notes') or {})}"
          f" files={len(data.get('files') or {})}")
    print(f"{'#':>3}  {'task':<12} {'status':<12} {'pr':<8} {'verified':<10} session_id")
    for i, s in enumerate(data["sessions"]):
        pr = s.get("pr")
        if isinstance(pr, str) and "/pull/" in pr:
            pr = "#" + pr.rsplit("/", 1)[-1]
        elif isinstance(pr, int):
            pr = f"#{pr}"
        print(f"{i:>3}  {short(s.get('task'), 12):<12} {short(s.get('status'), 12):<12} {short(pr, 8):<8} "
              f"{short((s.get('verified_sha') or '-')[:8], 10):<10} {s.get('session_id') or '-'}")


def cmd_add_session(a):
    data = load(a.file)
    task = int(a.task) if a.task.isdigit() else a.task
    entry = {
        "task": task, "title": a.title, "path": a.path, "session_id": a.session_id,
        "agent_name": None, "url": a.url, "branch": a.branch, "started_at": a.started_at,
        "status": "running", "pr": None, "autofix": "unknown", "verified_sha": None,
        "notes": a.notes or "",
    }
    guard(entry)
    data["sessions"].append(entry)
    save(a.file, data)
    print(f"added session [{len(data['sessions']) - 1}] task={task} status=running")


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
