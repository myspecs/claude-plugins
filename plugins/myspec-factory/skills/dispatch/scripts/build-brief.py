#!/usr/bin/env python3
"""Assemble the spec-derived sections of a factory worker brief from a local bundle copy.

The bundle is the local mirror written by download_spec_file (.specs/<bundle>/). Every
section is copied verbatim from the bundle; nothing is paraphrased. Python 3 stdlib only.

Usage:
  build-brief.py --bundle-dir .specs/<bundle> --tasks 45,46,47
                 [--requirements AR-WEB-27,CR-WEB-4] [--clarifications Q24,Q26]
                 [--greenfield] [--out brief-part.md]

Sections, in order:
  ## Tasks (in order)            the milestone heading of each task (as ###), then each task
                                 block verbatim, indented sub-bullets (Clarification, Merged) included
  ## Requirements these tasks satisfy (verbatim)
                                 each requirement block (#{2,4} <ID> heading up to the next heading
                                 of the same or a higher level) for the --requirements ids, the ids on
                                 the tasks' _Requirements:_ lines and every AR/BR/CR/FR/NFR id in the
                                 task text, de-duplicated, in order of first appearance. OpenSpec
                                 "### Requirement: <name>" blocks match an id equal to <name> (best effort).
  ## Decisions already made (do not re-decide)
                                 the "| Qn |" rows of requirements.md for --clarifications and every
                                 Qn in the task text, under their table header
  ## Constitution (binding)      only when constitution.md and solution.md exist (greenfield) or with
                                 --greenfield: the Technology, Architecture, Testing, Coding Standards
                                 and Security sections (headings matched case-insensitively, best effort)
Ids that are not found are listed in a <!-- missing: ... --> comment and on stderr.
Exit codes: 0 ok (missing requirement/decision ids are warnings), 1 a task or a bundle file is missing,
2 usage error.
"""
import argparse
import glob
import os
import re
import sys

TASK_RE = re.compile(r"^- \[[ xX]\] (\d+)\\?\.")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
REQ_ID = r"[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*-\d+"
REQ_HEADING_RE = re.compile(r"^(#{2,4})\s+(" + REQ_ID + r")\b")
OPENSPEC_RE = re.compile(r"^(#{2,4})\s+Requirement:\s*(.+?)\s*$")
TEXT_REQ_RE = re.compile(r"\b(?:AR|BR|CR|FR|NFR)(?:-[A-Z0-9]+)*-\d+\b")
REQ_LINE_RE = re.compile(r"_Requirements?:\s*(.*?)_?\s*$")
Q_RE = re.compile(r"\bQ(\d+)(?![0-9])")
Q_ROW_RE = re.compile(r"^\|\s*Q(\d+)\s*\|")
CONSTITUTION_SECTIONS = ("technology", "architecture", "testing", "coding standards", "security")


def warn(msg):
    print(f"build-brief: {msg}", file=sys.stderr)


def read_lines(path):
    with open(path, encoding="utf-8") as f:
        return f.read().splitlines()


def split_ids(s):
    return [x.strip() for x in (s or "").split(",") if x.strip()]


def dedupe(items):
    seen, out = set(), []
    for i in items:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


def task_blocks(lines):
    """{task number: (milestone heading line or None, [block lines])}."""
    out = {}
    heading = None
    i = 0
    while i < len(lines):
        line = lines[i]
        h = HEADING_RE.match(line)
        if h and len(h.group(1)) <= 3:
            heading = line
        m = TASK_RE.match(line)
        if not m:
            i += 1
            continue
        block = [line]
        j = i + 1
        while j < len(lines):
            nxt = lines[j]
            if TASK_RE.match(nxt) or HEADING_RE.match(nxt) or nxt.strip() == "---":
                break
            if nxt.strip() == "":
                # A blank line ends the block when the next non-blank line is not indented.
                k = j
                while k < len(lines) and lines[k].strip() == "":
                    k += 1
                if k >= len(lines) or not lines[k].startswith((" ", "\t")):
                    break
            block.append(nxt)
            j += 1
        while block and block[-1].strip() == "":
            block.pop()
        out.setdefault(int(m.group(1)), (heading, block))
        i = j
    return out


def heading_sections(lines):
    """Yield (level, title, start, end) for every heading; end is exclusive and stops at the
    next heading of the same or a higher level."""
    heads = []
    for idx, line in enumerate(lines):
        h = HEADING_RE.match(line)
        if h:
            heads.append((idx, len(h.group(1)), h.group(2)))
    for n, (idx, level, title) in enumerate(heads):
        end = len(lines)
        for idx2, level2, _ in heads[n + 1:]:
            if level2 <= level:
                end = idx2
                break
        yield level, title, idx, end


def strip_block(block):
    while block and block[-1].strip() in ("", "---"):
        block = block[:-1]
    return block


def requirement_blocks(paths):
    """{id: [lines]} from requirement headings; OpenSpec names keyed in lower case."""
    out = {}
    for path in paths:
        lines = read_lines(path)
        for level, title, start, end in heading_sections(lines):
            if level < 2 or level > 4:
                continue
            m = REQ_HEADING_RE.match(lines[start])
            if m:
                out.setdefault(m.group(2), strip_block(lines[start:end]))
                continue
            m = OPENSPEC_RE.match(lines[start])
            if m:
                out.setdefault("openspec:" + m.group(2).lower(), strip_block(lines[start:end]))
    return out


def decision_rows(lines):
    """({Q number: row line}, {Q number: header lines of its table})."""
    rows, headers = {}, {}
    for idx, line in enumerate(lines):
        m = Q_ROW_RE.match(line)
        if not m:
            continue
        q = int(m.group(1))
        rows.setdefault(q, line)
        k = idx
        while k > 0 and lines[k - 1].startswith("|") and not Q_ROW_RE.match(lines[k - 1]):
            k -= 1
        hdr = lines[k:idx]
        if not hdr:
            # Row in the middle of a table: walk up to the table's first line.
            k = idx
            while k > 0 and lines[k - 1].startswith("|"):
                k -= 1
            hdr = [l for l in lines[k:idx] if not Q_ROW_RE.match(l)]
        headers.setdefault(q, hdr)
    return rows, headers


def constitution_sections(path):
    lines = read_lines(path)
    out, used = [], set()
    for want in CONSTITUTION_SECTIONS:
        for level, title, start, end in heading_sections(lines):
            if level >= 2 and want in title.lower() and start not in used:
                used.add(start)
                out.append(strip_block(lines[start:end]))
                break
        else:
            warn(f"constitution: no section heading containing {want!r}")
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    p.add_argument("--bundle-dir", required=True)
    p.add_argument("--tasks", required=True, help="comma-separated task numbers, e.g. 45,46,47")
    p.add_argument("--requirements", help="extra requirement ids, e.g. AR-WEB-27,CR-WEB-4")
    p.add_argument("--clarifications", help="extra decision ids, e.g. Q24,Q26")
    p.add_argument("--greenfield", action="store_true",
                   help="require the constitution section (default: added when constitution.md and solution.md exist)")
    p.add_argument("--out", help="write here instead of stdout")
    a = p.parse_args()

    bdir = a.bundle_dir
    tasks_path = os.path.join(bdir, "tasks.md")
    req_path = os.path.join(bdir, "requirements.md")
    if not os.path.exists(tasks_path):
        warn(f"{tasks_path} not found")
        return 1
    try:
        wanted = [int(t.strip()) for t in a.tasks.split(",") if t.strip()]
    except ValueError:
        warn("--tasks takes task numbers, e.g. 45,46,47")
        return 2

    blocks = task_blocks(read_lines(tasks_path))
    missing_tasks = [t for t in wanted if t not in blocks]
    if missing_tasks:
        warn(f"tasks not found in {tasks_path}: {', '.join(map(str, missing_tasks))}")
        return 1

    out = ["## Tasks (in order)", ""]
    last_heading = object()
    task_text = []
    for t in wanted:
        heading, block = blocks[t]
        if heading != last_heading and heading is not None:
            out += ["#" * 3 + " " + HEADING_RE.match(heading).group(2), ""]
        last_heading = heading
        out += block + [""]
        task_text += block

    # Requirement ids: given, then _Requirements:_ lines, then any AR/BR/CR/FR/NFR id in the text.
    req_ids = split_ids(a.requirements)
    for line in task_text:
        m = REQ_LINE_RE.search(line.strip())
        if m and "_Requirements" in line:
            req_ids += re.findall(REQ_ID, m.group(1))
    for line in task_text:
        req_ids += TEXT_REQ_RE.findall(line)
    req_ids = dedupe(req_ids)

    req_files = [req_path] if os.path.exists(req_path) else []
    req_files += sorted(glob.glob(os.path.join(bdir, "**", "spec.md"), recursive=True))
    if not req_files:
        warn(f"no requirements.md or OpenSpec spec.md under {bdir}")
    reqs = requirement_blocks(req_files)
    out += ["## Requirements these tasks satisfy (verbatim)", ""]
    missing_reqs = []
    for rid in req_ids:
        block = reqs.get(rid) or reqs.get("openspec:" + rid.lower())
        if block is None:
            missing_reqs.append(rid)
            continue
        out += block + [""]
    if missing_reqs:
        out += [f"<!-- missing: {', '.join(missing_reqs)} -->", ""]
        warn(f"requirements not found: {', '.join(missing_reqs)}")

    # Decisions: given Q ids, then every Qn in the task text.
    given_qs = [int(m) for q in split_ids(a.clarifications) for m in Q_RE.findall(q)]
    qs = list(given_qs)
    for line in task_text:
        qs += [int(m) for m in Q_RE.findall(line)]
    qs = dedupe(qs)
    out += ["## Decisions already made (do not re-decide)", ""]
    if qs:
        rows, headers = decision_rows(read_lines(req_path)) if os.path.exists(req_path) else ({}, {})
        found = [q for q in qs if q in rows]
        # A Q id cited only in the task text may be recorded only in its Clarification lines.
        missing_q = [f"Q{q}" for q in qs if q not in rows and q in given_qs]
        text_only = [f"Q{q}" for q in qs if q not in rows and q not in given_qs]
        if found:
            out += headers.get(found[0], [])
            out += [rows[q] for q in sorted(found)]
            out += [""]
        if missing_q:
            out += [f"<!-- missing: {', '.join(missing_q)} -->", ""]
            warn(f"decisions not found: {', '.join(missing_q)}")
        if text_only:
            out += [f"<!-- no row in requirements.md, cited in the task text above: {', '.join(text_only)} -->", ""]
            warn(f"decisions cited in the tasks without a requirements.md row: {', '.join(text_only)}")
    out += ["Each task's `- Clarification:` lines above are decisions too.", ""]

    const_path = os.path.join(bdir, "constitution.md")
    greenfield = os.path.exists(const_path) and os.path.exists(os.path.join(bdir, "solution.md"))
    if a.greenfield and not os.path.exists(const_path):
        warn(f"--greenfield: {const_path} not found")
    if greenfield or (a.greenfield and os.path.exists(const_path)):
        out += ["## Constitution (binding)", ""]
        for sec in constitution_sections(const_path):
            # Demote so each section sits under "## Constitution (binding)".
            h = HEADING_RE.match(sec[0])
            if h and len(h.group(1)) < 3:
                sec = ["###" + " " + h.group(2)] + sec[1:]
            out += sec + [""]

    text = "\n".join(out).rstrip("\n") + "\n"
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(text)
        warn(f"wrote {a.out} ({text.count(chr(10))} lines)")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
