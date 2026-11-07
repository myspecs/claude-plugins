#!/usr/bin/env python3
"""Add indented notes to tasks in a local copy of tasks.md, and mark them done, keeping every other byte.

Status normally changes through the MCP tool set_task_status; use --done only where the task board is
turned off (the fallback edit).

Usage: tasks-mark.py --file .specs/<bundle>/tasks.md --tasks 22,23,24 [--done] [--note "<text>" ...] [--dry-run]
  --done     flip each task's `- [ ]` or `- [-]` (in progress) to `- [x]` (a task already `[x]` is left as it is)
  --note     add `  - <text>` under each task, after its last indented line; repeatable. Use the
             plugin's sub-bullet names: "Merged: PR #123 (abc1234)", "Clarification: ...", "Progress: ..."
             A note already present under the task is not added twice.
  --dry-run  print what would change and write nothing

Task lines it recognises, with `[ ]`, `[-]` or `[x]`: `- [ ] 22\\. Title` and `- [ ] 22. Title` (MySpec),
`- [ ] 2.1 Title` (OpenSpec), `- [ ] T007 Title` (Spec Kit); `22` never matches `22.1`, `T1` never `T10`.
Lines inside fenced code blocks (``` or ~~~) are never tasks, as on the platform's task board. A task id that matches no line, or more than one, stops the run with nothing written.
Then upload the file with `update_spec_file` and the `expected_version` of the revision this copy came from.
Exit codes: 0 ok, 1 not found or ambiguous, 2 usage.
"""
import argparse
import re
import sys


def indent(line):
    return len(line) - len(line.lstrip(" \t"))


def main():
    p = argparse.ArgumentParser(description="Mark tasks done and add notes in tasks.md.",
                                formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    p.add_argument("--file", required=True)
    p.add_argument("--tasks", required=True, help="comma-separated task ids, e.g. 22,23,24 or 2.1,2.2")
    p.add_argument("--done", action="store_true")
    p.add_argument("--note", action="append", default=[])
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()
    if not a.done and not a.note:
        p.error("nothing to do: pass --done, --note, or both")
    for n in a.note:
        if "\n" in n or "\r" in n or not n.strip():
            p.error("a note is one non-empty line")
    ids = [t.strip() for t in a.tasks.split(",") if t.strip()]
    if not ids or not all(re.fullmatch(r"\d+(\.\d+)*|T\d+", t) for t in ids):
        p.error("--tasks takes task ids such as 22,23, 2.1 or T007")

    with open(a.file, newline="") as f:
        original = f.read()
    lines = original.splitlines(keepends=True)
    eol = "\r\n" if lines and lines[0].endswith("\r\n") else "\n"

    # Lines inside fenced code blocks are examples, not tasks (the platform's parser skips them too).
    in_code, fence = [], None
    for ln in lines:
        m = re.match(r"^[ \t]*(`{3,}|~{3,})", ln)
        if fence is None and m:
            fence = m.group(1)[0] * len(m.group(1))
            in_code.append(True)
        elif fence is not None:
            in_code.append(True)
            if m and m.group(1).startswith(fence):
                fence = None
        else:
            in_code.append(False)

    plan = []  # (task id, line index)
    for t in ids:
        pat = re.compile(r"^[ \t]*- \[[ xX-]\] " + re.escape(t) + r"(\\?\.)?(?=[ \t])")
        hits = [i for i, ln in enumerate(lines) if not in_code[i] and pat.match(ln)]
        if len(hits) != 1:
            print(f"tasks-mark: task {t} matches {len(hits)} lines" + (f" ({', '.join(str(h + 1) for h in hits)})" if hits else "")
                  + "; nothing written", file=sys.stderr)
            return 1
        plan.append((t, hits[0]))

    # Apply from the bottom up so earlier indexes stay valid.
    for t, i in sorted(plan, key=lambda x: -x[1]):
        changes = []
        line = lines[i]
        if a.done:
            m = re.match(r"^[ \t]*- \[([ -])\]", line)
            if m:
                lines[i] = line.replace(f"- [{m.group(1)}]", "- [x]", 1)
                changes.append(f"[{m.group(1)}] -> [x]")
            else:
                changes.append("already [x]")
        base = indent(line)
        end = i + 1
        while end < len(lines) and lines[end].strip() and indent(lines[end]) > base:
            end += 1
        block = {ln.strip() for ln in lines[i + 1:end]}
        pad = line[:base] + "  "
        add = []
        for n in a.note:
            if f"- {n.strip()}" in block:
                changes.append(f"note already there: {n.strip()[:60]}")
            else:
                add.append(f"{pad}- {n.strip()}{eol}")
                changes.append(f"+ note: {n.strip()[:60]}")
        if add and end == len(lines) and not lines[-1].endswith(("\n", "\r")):
            lines[-1] += eol
        lines[end:end] = add
        print(f"task {t} (line {i + 1}): " + "; ".join(changes))

    if a.dry_run:
        print("dry run: nothing written")
        return 0
    if "".join(lines) == original:
        print(f"{a.file} unchanged")
        return 0
    with open(a.file, "w", newline="") as f:
        f.write("".join(lines))
    print(f"wrote {a.file}; upload it with update_spec_file and the expected_version of the revision it came from")
    return 0


if __name__ == "__main__":
    sys.exit(main())
