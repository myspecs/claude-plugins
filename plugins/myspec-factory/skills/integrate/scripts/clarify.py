#!/usr/bin/env python3
"""Add a numbered decision to the `## Clarifications` section of a local copy of requirements.md.

Usage: clarify.py --file .specs/<bundle>/requirements.md --title "<short title>" --text "<rest of the entry>"
                  [--id C48] [--prefix C] [--dry-run]
       clarify.py --file .specs/<bundle>/requirements.md --line "<the full entry, with {id} where the id goes>"
                  [--id Q31] [--prefix Q] [--dry-run]

The section's entries are numbered bullets (`- **C47 — Title** (refs; owner decision, date). Text.`) or
table rows (`| Q30 | answer | reason |`). Several letters may share the section (C and D); the prefix is
the most frequent one unless --prefix names another. The new id is the highest number of that prefix
plus one unless --id is given.
  --title/--text  write a bullet: `- **<id> — <title>** <text>` (bullet sections only)
  --line          write this line as given, with {id} replaced (any style, including table rows)
The entry goes right after the last entry with the same prefix, so other blocks (D1-D6) stay where
they are. A file without the section gets one at the end.

Afterwards every range mention `<P>1–<P><old max>` (en dash or hyphen) in the file becomes
`<P>1–<P><new>`, and the lines that still name the old highest id are listed so the prose around them
can be checked by hand.
Then upload the file with `update_spec_file` and the `expected_version` of the revision it came from.
Exit codes: 0 ok, 1 bad input (id taken, wrong style), 2 usage.
"""
import argparse
import collections
import re
import sys

BULLET = re.compile(r"^- \*\*([A-Z])(\d+)\b")
ROW = re.compile(r"^\|\s*([A-Z])(\d+)\s*\|")


def main():
    p = argparse.ArgumentParser(description="Add a numbered Clarification to requirements.md.",
                                formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    p.add_argument("--file", required=True)
    p.add_argument("--title")
    p.add_argument("--text")
    p.add_argument("--line")
    p.add_argument("--id")
    p.add_argument("--prefix")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()
    if bool(a.line) == bool(a.title or a.text):
        p.error("pass either --title and --text, or --line")
    if not a.line and not (a.title and a.text):
        p.error("--title and --text go together")
    if a.line and "{id}" not in a.line:
        p.error("--line must contain {id} where the id goes")
    for v in (a.title, a.text, a.line):
        if v and ("\n" in v or "\r" in v):
            p.error("an entry is one line")
    if a.id and not re.fullmatch(r"[A-Z]\d+", a.id):
        p.error("--id looks like C48 or Q31")

    with open(a.file, newline="") as f:
        original = f.read()
    lines = original.splitlines(keepends=True)
    eol = "\r\n" if lines and lines[0].endswith("\r\n") else "\n"

    start = next((i for i, ln in enumerate(lines) if re.match(r"^##\s+Clarifications\b", ln)), None)
    end = len(lines)
    if start is not None:
        end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    entries = []  # (letter, number, index, style)
    if start is not None:
        for i in range(start + 1, end):
            m = BULLET.match(lines[i]) or ROW.match(lines[i])
            if m:
                entries.append((m.group(1), int(m.group(2)), i, "bullet" if BULLET.match(lines[i]) else "row"))

    prefix = a.prefix or (a.id[0] if a.id else None)
    if not prefix:
        counts = collections.Counter(e[0] for e in entries)
        prefix = counts.most_common(1)[0][0] if counts else "C"
    mine = [e for e in entries if e[0] == prefix]
    top = max((e[1] for e in mine), default=0)
    new_id = a.id or f"{prefix}{top + 1}"
    if any(f"{e[0]}{e[1]}" == new_id for e in entries):
        print(f"clarify: {new_id} already exists", file=sys.stderr)
        return 1
    style = mine[-1][3] if mine else ("row" if any(e[3] == "row" for e in entries) else "bullet")
    if style == "row" and not a.line:
        print("clarify: this section uses table rows; pass --line '| {id} | ... |'", file=sys.stderr)
        return 1
    entry = a.line.replace("{id}", new_id) if a.line else f"- **{new_id} — {a.title.strip()}** {a.text.strip()}"

    if start is None:
        tail = "" if not lines or lines[-1].endswith(("\n", "\r")) else eol
        lines.append(f"{tail}{eol}## Clarifications{eol}{eol}{entry}{eol}")
        where = "a new ## Clarifications section at the end"
    else:
        if mine:
            at = mine[-1][2] + 1
            # A bullet may continue on indented lines; a table row is one line.
            while style == "bullet" and at < end and lines[at].strip() and lines[at][:1] in (" ", "\t"):
                at += 1
        else:
            at = end
            while at > start + 1 and not lines[at - 1].strip():
                at -= 1
        if at == len(lines) and lines and not lines[-1].endswith(("\n", "\r")):
            lines[-1] += eol
        lines.insert(at, entry + eol)
        where = f"line {at + 1}"

    text = "".join(lines)
    ranges = 0
    if top:
        old_top = f"{prefix}{top}"
        new_num = int(new_id[1:])
        rng = re.compile(rf"\b{prefix}1(\s?[–-]\s?){prefix}{top}\b")
        text, ranges = rng.subn(lambda m: f"{prefix}1{m.group(1)}{prefix}{new_num}", text)
        others = [f"  line {n}: {ln.strip()[:120]}" for n, ln in enumerate(text.splitlines(), 1)
                  if re.search(rf"\b{old_top}\b", ln) and not BULLET.match(ln) and not ROW.match(ln)]
    else:
        others = []

    print(f"{new_id} added at {where}: {entry[:100]}")
    print(f"range mentions updated: {ranges}")
    if others:
        print(f"lines that still name {prefix}{top}, check the prose by hand:")
        print("\n".join(others))
    if a.dry_run:
        print("dry run: nothing written")
        return 0
    with open(a.file, "w", newline="") as f:
        f.write(text)
    print(f"wrote {a.file}; upload it with update_spec_file and the expected_version of the revision it came from")
    return 0


if __name__ == "__main__":
    sys.exit(main())
