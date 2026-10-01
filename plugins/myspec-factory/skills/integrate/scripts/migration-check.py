#!/usr/bin/env python3
"""Check the database migrations a change adds against the base it will merge into. Read-only.

Usage: migration-check.py <repo-clone-dir> <base-ref> <head-ref>
  <base-ref>  what the change merges into, as it is now (for example origin/main; fetch it first)
  <head-ref>  the change's head commit (for example the pull request's head sha)

A migration is an entry directly under a directory named `migrations` whose name starts with a
digit: a file (`0003_drop_seen.sql`, `000123_add.up.sql`) or a directory
(`20260930000100_drop_column/migration.sql`). Other names (`migration_lock.toml`, `README.md`,
Flyway's `V2__x.sql`) are ignored. Names compare naturally: digit runs as numbers, so `9_x` sorts
before `10_x`.

Two rules, per migrations directory:
  1. Applied migrations never change: the change must not add, modify, rename or delete anything
     inside an entry that already exists on <base-ref>.
  2. New migrations sort last: every entry the change adds must sort after every entry on
     <base-ref>. A migration that sorts before one already on the base may never run, or run in
     an order nobody tested.

Lines:
  PASS migrations: none in this change
  PASS migrations: <dir>: <new entries> sort(s) after <last base entry>
  FAIL migrations: <dir>: <entry> sorts before <base entry> on <base-ref>; rename it to sort last
  FAIL migrations: <dir>: changes applied migration <entry> (<status> <path>)
Exit codes: 0 pass, 1 fail, 2 usage or git error.
"""
import re
import subprocess
import sys


def git(clone, *args):
    r = subprocess.run(["git", "-C", clone, *args], capture_output=True, text=True)
    if r.returncode != 0:
        print(f"migration-check: git {' '.join(args)} failed: {r.stderr.strip()}", file=sys.stderr)
        sys.exit(2)
    return r.stdout


def natural_key(name):
    return [(0, int(p), "") if p.isdigit() else (1, 0, p) for p in re.split(r"(\d+)", name) if p != ""]


def split_migration(path):
    """'a/migrations/0003_x.sql' -> ('a/migrations', '0003_x.sql'); None when not a migration."""
    parts = path.split("/")
    for i in range(len(parts) - 1):
        if parts[i] == "migrations" and parts[i + 1][:1].isdigit():
            return "/".join(parts[: i + 1]), parts[i + 1]
    return None


def main():
    if len(sys.argv) != 4:
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        sys.exit(2)
    clone, base, head = sys.argv[1:]
    mb = git(clone, "merge-base", base, head).strip()
    changes = []  # (status, path) for every side of a rename
    for line in git(clone, "diff", "--name-status", "-M", mb, head).splitlines():
        cols = line.split("\t")
        status = cols[0][:1]
        for path in cols[1:]:
            changes.append((status, path))

    dirs = {}
    for status, path in changes:
        hit = split_migration(path)
        if hit:
            dirs.setdefault(hit[0], []).append((status, path, hit[1]))
    if not dirs:
        print("PASS migrations: none in this change")
        return 0

    failed = False
    for d in sorted(dirs):
        on_base = git(clone, "ls-tree", "--name-only", base, f"{d}/").splitlines()
        dir_failed = False
        base_entries = sorted({n.split("/")[-1] for n in on_base if n.split("/")[-1][:1].isdigit()}, key=natural_key)
        new_entries = set()
        for status, path, entry in dirs[d]:
            if entry in base_entries:
                print(f"FAIL migrations: {d}: changes applied migration {entry} ({status} {path})")
                dir_failed = True
            elif status in ("A", "R", "C"):
                new_entries.add(entry)
            else:
                # Modified or deleted, but absent from the base: it was added and removed again on the base side.
                print(f"FAIL migrations: {d}: changes migration {entry} that the base no longer has ({status} {path})")
                dir_failed = True
        failed = failed or dir_failed
        if not new_entries:
            continue
        last = base_entries[-1] if base_entries else None
        for entry in sorted(new_entries, key=natural_key):
            if last is not None and natural_key(entry) < natural_key(last):
                print(f"FAIL migrations: {d}: {entry} sorts before {last} on {base}; rename it to sort last")
                dir_failed = failed = True
        if not dir_failed:
            after = f"after {last}" if last else "first in the directory"
            verb = "sorts" if len(new_entries) == 1 else "sort"
            print(f"PASS migrations: {d}: {', '.join(sorted(new_entries, key=natural_key))} {verb} {after}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
