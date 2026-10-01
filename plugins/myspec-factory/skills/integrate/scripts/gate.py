#!/usr/bin/env python3
"""Ready-to-merge gate for one factory pull request (the integrate skill, section 3). Read-only.

Usage: gate.py <repo-clone-dir> <pr-number> --reviewer <login> [--verified-sha <sha>] [--paths <path> ...]
  --reviewer      the login whose approval gates the merge (the registry's policy.reviewer)
  --verified-sha  the head your own last verification covered (the registry entry's verified_sha)
  --paths         extra paths that count as this pull request's area for item 7, such as the shared
                  packages its projects build against (the projects it touches are found from its diff)

Runs every item of the gate from fresh GitHub state and prints one line per item:
  1 approval   the reviewer's latest review is APPROVED on the current head
  2 checks     every check on the head passed (SUCCESS, SKIPPED or NEUTRAL), none pending, and every
               required check of the base branch reported at all; a required check that never reported
               is usually skipped by a workflow `paths` filter
  3 threads    no unresolved review thread
  4 merge      the pull request is open, mergeStateStatus is CLEAN, auto-merge is off
  5 verified   --verified-sha is the head, or only documentation changed after it
  6 report     not a draft; no BLOCKED: or HOLD: first line; no BLOCKED: or "- Open question:" line in the
               newest Factory report (warns on report lines that say "pending")
  7 base       the base gained nothing in this pull request's areas since its merge base (documentation
               on either side is ignored; an area is projects/<x>, packages/<x> and the like, else the
               top-level directory or file), and its
               migrations still sort last and leave applied ones untouched (migration-check.py)
Not checked here, still the manager's: open board questions, deviations the owner has not decided,
a release hold recorded only in the registry (hold_until), and anything the checks cannot see.

Lines:
  gate PR #<n> head <sha8> base <branch>@<sha8>
  PASS|FAIL|WARN <item> <name>: <detail>
  gate: pass | gate: FAIL (items <list>)
  github-unreachable (<what failed>)    -- the state is UNKNOWN; exit 3
Exit codes: 0 every item passed, 1 an item failed, 2 usage or local git error, 3 GitHub unreachable.
Never checks out or switches branches: it only fetches into FETCH_HEAD and origin/<base>.
"""
import argparse
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PASS_STATES = {"SUCCESS", "SKIPPED", "NEUTRAL"}
PENDING_STATES = {"PENDING", "EXPECTED", "QUEUED", "IN_PROGRESS", "WAITING", "REQUESTED"}
# Top-level directories that hold one project per subdirectory: the area is two segments deep.
CONTAINERS = {"projects", "packages", "apps", "services", "libs", "modules", "plugins", "crates"}
DOC_RE = re.compile(r"\.(md|mdx|txt|rst|adoc)$|(^|/)docs?/|(^|/)(LICENSE|CHANGELOG|README)[^/]*$", re.I)
TEST_RE = re.compile(r"(^|/)(tests?|__tests__|spec|e2e|testdata|fixtures?)/|_test\.go$|\.(test|spec)\.[cm]?[jt]sx?$"
                     r"|(^|/)test_[^/]*\.py$|_test\.py$", re.I)


class Unreachable(Exception):
    pass


def sh(cmd, cwd, what=None, ok_404=False):
    """Run a command. gh/network failures raise Unreachable; ok_404 returns None on a 404."""
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if r.returncode == 0:
        return r.stdout
    if ok_404 and re.search(r"HTTP 404|Not Found|not protected", r.stderr):
        return None
    if re.search(r"Could not resolve to a PullRequest|no pull requests? found", r.stderr, re.I):
        print(f"gate: {r.stderr.strip()}", file=sys.stderr)
        sys.exit(2)
    raise Unreachable(what or " ".join(cmd[:3]))


def git(clone, *args):
    r = subprocess.run(["git", "-C", clone, *args], capture_output=True, text=True)
    if r.returncode != 0:
        print(f"gate: git {' '.join(args)} failed: {r.stderr.strip()}", file=sys.stderr)
        sys.exit(2)
    return r.stdout


def has_commit(clone, sha):
    return subprocess.run(["git", "-C", clone, "cat-file", "-e", f"{sha}^{{commit}}"],
                          capture_output=True).returncode == 0


def area_of(path):
    parts = path.split("/")
    if len(parts) > 2 and parts[0] in CONTAINERS:
        return "/".join(parts[:2])
    return parts[0]


def check_state(c):
    if c.get("__typename") == "StatusContext" or "context" in c:
        return (c.get("state") or "PENDING").upper()
    if (c.get("status") or "COMPLETED").upper() != "COMPLETED":
        return "PENDING"
    return (c.get("conclusion") or "PENDING").upper()


def main():
    p = argparse.ArgumentParser(description="Ready-to-merge gate for one pull request (read-only).",
                                formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    p.add_argument("clone")
    p.add_argument("pr", type=int)
    p.add_argument("--reviewer", required=True)
    p.add_argument("--verified-sha")
    p.add_argument("--paths", nargs="*", default=[])
    a = p.parse_args()
    clone = os.path.abspath(a.clone)
    if not os.path.isdir(clone):
        print(f"gate: no such directory {clone}", file=sys.stderr)
        return 2

    results = []  # (verdict, item, name, detail)

    def say(verdict, item, name, detail):
        results.append((verdict, item))
        print(f"{verdict} {item} {name}: {detail}")

    try:
        repo = sh(["gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"], clone,
                  "gh repo view").strip()
        pr = json.loads(sh(["gh", "pr", "view", str(a.pr), "--json",
                            "number,title,state,isDraft,headRefOid,headRefName,baseRefName,mergeStateStatus,"
                            "autoMergeRequest,statusCheckRollup,body,comments"], clone, "gh pr view"))
        head, base = pr["headRefOid"], pr["baseRefName"]
        sh(["git", "fetch", "-q", "origin", base], clone, "git fetch base")
        if not has_commit(clone, head):
            sh(["git", "fetch", "-q", "origin", f"pull/{a.pr}/head"], clone, "git fetch pull head")
        if not has_commit(clone, head):
            sh(["git", "fetch", "-q", "origin", head], clone, "git fetch head sha")
        tip = git(clone, "rev-parse", f"origin/{base}").strip()
        print(f"gate PR #{a.pr} head {head[:8]} base {base}@{tip[:8]}")

        # 1. Approval on the current head.
        rows = sh(["gh", "api", "--paginate", f"repos/{repo}/pulls/{a.pr}/reviews?per_page=100",
                   "--jq", '.[] | [.user.login, .state, .commit_id] | @tsv'], clone, "gh api reviews")
        last = None
        for line in rows.splitlines():
            cols = line.split("\t")
            if len(cols) == 3 and cols[0].lower() == a.reviewer.lower() and \
                    cols[1] in ("APPROVED", "CHANGES_REQUESTED", "DISMISSED"):
                last = cols
        if last is None:
            say("FAIL", 1, "approval", f"no review from {a.reviewer}; request it (gh pr edit {a.pr} --add-reviewer {a.reviewer})")
        elif last[1] != "APPROVED":
            say("FAIL", 1, "approval", f"{a.reviewer}'s latest review is {last[1]} on {last[2][:8]}")
        elif last[2] != head:
            say("FAIL", 1, "approval", f"{a.reviewer} approved {last[2][:8]}, not the head {head[:8]}; "
                f"re-request review (gh pr edit {a.pr} --add-reviewer {a.reviewer})")
        else:
            say("PASS", 1, "approval", f"{a.reviewer} APPROVED the head {head[:8]}")

        # 2. Checks on the head, and required checks that never reported.
        required = set()
        rules = sh(["gh", "api", f"repos/{repo}/rules/branches/{base}"], clone, "gh api rules", ok_404=True)
        for rule in json.loads(rules) if rules else []:
            for c in (rule.get("parameters") or {}).get("required_status_checks") or []:
                if c.get("context"):
                    required.add(c["context"])
        classic = sh(["gh", "api", f"repos/{repo}/branches/{base}/protection/required_status_checks",
                      "--jq", ".contexts[]"], clone, "gh api protection", ok_404=True)
        required.update(x for x in (classic or "").splitlines() if x)
        groups = {}
        for c in pr.get("statusCheckRollup") or []:
            name = c.get("name") or c.get("context") or "?"
            groups.setdefault(name, []).append(check_state(c))
        failing, pending = [], []
        for name, states in sorted(groups.items()):
            if any(s in PENDING_STATES for s in states):
                pending.append(name)
            elif not (any(s in PASS_STATES for s in states) and all(s in PASS_STATES or s == "CANCELLED" for s in states)):
                failing.append(f"{name}={'/'.join(sorted(set(states)))}")
        missing = sorted(required - set(groups))
        req = f"required: {', '.join(sorted(required))}" if required else f"no required checks on {base}"
        if failing or pending or missing:
            parts = []
            if failing:
                parts.append(f"failing [{', '.join(failing)}]")
            if pending:
                parts.append(f"pending [{', '.join(pending)}]")
            if missing:
                parts.append(f"required but never reported [{', '.join(missing)}] (a workflow `paths` filter "
                             "may skip them for this diff; never merge around it, see integrate §3)")
            say("FAIL", 2, "checks", "; ".join(parts) + f" ({req})")
        else:
            say("PASS", 2, "checks", f"{len(groups)} check name(s) green on the head ({req})")

        # 3. Review threads.
        owner, name = repo.split("/", 1)
        q = ("query($owner:String!,$name:String!,$n:Int!){repository(owner:$owner,name:$name){pullRequest(number:$n)"
             "{reviewThreads(first:100){totalCount nodes{isResolved}}}}}")
        t = json.loads(sh(["gh", "api", "graphql", "-f", f"query={q}", "-F", f"owner={owner}", "-F", f"name={name}",
                           "-F", f"n={a.pr}"], clone, "gh api graphql reviewThreads"))
        threads = t["data"]["repository"]["pullRequest"]["reviewThreads"]
        open_threads = sum(1 for n in threads["nodes"] if not n["isResolved"])
        if open_threads:
            say("FAIL", 3, "threads", f"{open_threads} unresolved review thread(s)")
        elif threads["totalCount"] > len(threads["nodes"]):
            say("WARN", 3, "threads", f"only the first {len(threads['nodes'])} of {threads['totalCount']} threads checked")
        else:
            say("PASS", 3, "threads", f"none unresolved ({threads['totalCount']} total)")

        # 4. Merge state.
        state, mss = pr["state"], pr.get("mergeStateStatus")
        hints = {"BLOCKED": "a required approval, check or thread is missing", "BEHIND": "update the branch",
                 "DIRTY": "merge conflicts: ask the worker to rebase", "UNSTABLE": "a non-required check is failing",
                 "UNKNOWN": "GitHub is still computing it: run the gate again", "DRAFT": "the pull request is a draft",
                 "HAS_HOOKS": "merge hooks pending"}
        if state != "OPEN":
            say("FAIL", 4, "merge", f"the pull request is {state}")
        elif pr.get("autoMergeRequest"):
            say("FAIL", 4, "merge", "auto-merge is enabled: turn it off (gh pr merge --disable-auto) and say so")
        elif mss != "CLEAN":
            say("FAIL", 4, "merge", f"mergeStateStatus {mss} ({hints.get(mss, 'not CLEAN')})")
        else:
            say("PASS", 4, "merge", "open, CLEAN, auto-merge off")

        # 5. Own verification covers the head.
        v = a.verified_sha
        if not v:
            say("FAIL", 5, "verified", "no --verified-sha (the registry entry's verified_sha)")
        elif head.startswith(v) or v.startswith(head):
            say("PASS", 5, "verified", f"verified_sha is the head {head[:8]}")
        else:
            if not has_commit(clone, v) and len(v) == 40:
                sh(["git", "fetch", "-q", "origin", v], clone, "git fetch verified sha")
            if not has_commit(clone, v):
                say("FAIL", 5, "verified", f"verified sha {v} is not known here; pass the full sha")
            elif subprocess.run(["git", "-C", clone, "merge-base", "--is-ancestor", v, head]).returncode != 0:
                say("FAIL", 5, "verified", f"{v[:8]} is not an ancestor of the head (history was rewritten): "
                    "re-verify the whole diff from the base")
            else:
                files = [f for f in git(clone, "diff", "--name-only", v, head).splitlines() if f]
                tests = [f for f in files if TEST_RE.search(f) and not DOC_RE.search(f)]
                prod = [f for f in files if not DOC_RE.search(f) and f not in tests]
                if prod:
                    say("FAIL", 5, "verified", f"production files changed after {v[:8]}: {', '.join(prod[:5])}"
                        + (" …" if len(prod) > 5 else "") + "; re-verify those commits")
                elif tests:
                    say("FAIL", 5, "verified", f"tests changed after {v[:8]}: {', '.join(tests[:5])}"
                        + (" …" if len(tests) > 5 else "") + "; run the verification checklist on them")
                else:
                    say("PASS", 5, "verified", f"only documentation changed after {v[:8]} ({len(files)} file(s))")

        # 6. Draft, holds, blocked lines and open questions in the newest Factory report.
        body = pr.get("body") or ""
        first = next((ln.strip() for ln in body.splitlines() if ln.strip()), "")
        report = body
        for c in pr.get("comments") or []:
            if (c.get("body") or "").lstrip().startswith("## Factory report"):
                report = c["body"]
        problems = []
        if pr.get("isDraft"):
            problems.append("draft")
        if first.startswith(("BLOCKED:", "HOLD:")):
            problems.append(f"first line: {first[:120]}")
        for ln in report.splitlines():
            s = ln.strip().lstrip("-* ").strip()
            if s.startswith("BLOCKED:") or ln.strip().startswith("- Open question:"):
                problems.append(ln.strip()[:120])
        if problems:
            say("FAIL", 6, "report", "; ".join(problems))
        else:
            say("PASS", 6, "report", "not a draft, no BLOCKED:/HOLD: line, no open question")
        for ln in [ln.strip() for ln in report.splitlines() if re.search(r"\bpending\b", ln, re.I)][:3]:
            say("WARN", 6, "report", f"says pending, check it is settled: {ln[:140]}")

        # 7. Base drift in this pull request's areas, and migration order.
        mb = git(clone, "merge-base", head, f"origin/{base}").strip()
        # Documentation on either side does not change what CI tested, so it never forces an update.
        mine = [f for f in git(clone, "diff", "--name-only", mb, head).splitlines() if f and not DOC_RE.search(f)]
        areas = sorted({area_of(f) for f in mine} | {x.strip("/") for x in a.paths if x.strip("/")})
        if mb == tip:
            say("PASS", 7, "base", f"the head is on the current {base} tip")
        else:
            moved = [f for f in git(clone, "diff", "--name-only", mb, tip).splitlines() if f and not DOC_RE.search(f)]
            hit = [f for f in moved if any(f == ar or f.startswith(ar + "/") for ar in areas)]
            if hit:
                say("FAIL", 7, "base", f"{base} changed {len(hit)} file(s) in this pull request's areas since its "
                    f"merge base ({', '.join(hit[:5])}{' …' if len(hit) > 5 else ''}): gh pr update-branch {a.pr}, "
                    "then wait for CI and a fresh approval on the new head")
            else:
                say("PASS", 7, "base", f"{base} moved ({len(moved)} file(s)) outside this pull request's areas "
                    f"({', '.join(areas) or 'none'})")
        r = subprocess.run([sys.executable, os.path.join(HERE, "migration-check.py"), clone, f"origin/{base}", head],
                           capture_output=True, text=True)
        if r.returncode == 2:
            print(r.stderr.strip(), file=sys.stderr)
            return 2
        for ln in r.stdout.splitlines():
            verdict, _, rest = ln.partition(" ")
            results.append((verdict, 7))
            print(f"{verdict} 7 {rest}")
    except Unreachable as e:
        print(f"github-unreachable ({e})")
        return 3

    bad = sorted({item for verdict, item in results if verdict == "FAIL"})
    print("gate: pass" if not bad else f"gate: FAIL (items {', '.join(map(str, bad))})")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
