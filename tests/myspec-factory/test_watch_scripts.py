"""Tests for plugins/myspec-factory/skills/watch/scripts/pr-watch.sh and team-watch.sh.

Stub `gh` and `git fetch` on PATH, so no network is used. Each `gh pr list` call takes the next
line of the scenario (the last one repeats); a line is `STATE PENDING FAILING` or `FAIL`.

Run from the repository root: python3 -m unittest discover -s tests/myspec-factory -v
Python 3 standard library only.
"""
import os
import shutil
import signal
import stat
import subprocess
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS = os.path.join(ROOT, "plugins", "myspec-factory", "skills", "watch", "scripts")
PR_WATCH = os.path.join(SCRIPTS, "pr-watch.sh")
TEAM_WATCH = os.path.join(SCRIPTS, "team-watch.sh")

GH_STUB = r"""#!/usr/bin/env bash
dir="$STUB_DIR"
case "$1 $2" in
  "pr list")
    n=$(cat "$dir/n" 2>/dev/null || echo 0); n=$((n + 1)); echo "$n" > "$dir/n"
    total=$(wc -l < "$dir/scenario" | tr -d ' ')
    [ "$n" -gt "$total" ] && n=$total
    line=$(sed -n "${n}p" "$dir/scenario")
    [ "$line" = FAIL ] && exit 1
    set -- $line
    failing=${3:-}; [ "$failing" = - ] && failing=""
    printf '7\037abcdef1234567890\037%s\037false\037REVIEW_REQUIRED\037%s\037%s\037feat/x\n' "$1" "$failing" "$2" ;;
  "repo view") echo o/r ;;
  "api --paginate") echo "bot APPROVED abcdef1234567890" ;;
  *) exit 0 ;;
esac
"""

GIT_STUB = r"""#!/usr/bin/env bash
case "$1" in
  fetch) exit 0 ;;
  for-each-ref) exit 0 ;;
  *) exec "$REAL_GIT" "$@" ;;
esac
"""


class WatchScriptsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="watchtest-")
        self.bin = os.path.join(self.tmp, "bin")
        self.clone = os.path.join(self.tmp, "clone")
        os.makedirs(self.bin)
        real_git = shutil.which("git")
        subprocess.run([real_git, "init", "-q", self.clone], check=True)
        for name, body in (("gh", GH_STUB), ("git", GIT_STUB)):
            path = os.path.join(self.bin, name)
            with open(path, "w") as f:
                f.write(body)
            os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)
        self.env = dict(os.environ, PATH=self.bin + os.pathsep + os.environ["PATH"],
                        STUB_DIR=self.tmp, REAL_GIT=real_git, PR_WATCH_MIN_INTERVAL="1")
        self.state = os.path.join(self.tmp, "state")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def scenario(self, *lines):
        with open(os.path.join(self.tmp, "scenario"), "w") as f:
            f.write("\n".join(lines) + "\n")
        try:
            os.remove(os.path.join(self.tmp, "n"))
        except FileNotFoundError:
            pass

    def pr_watch(self, *extra, run_for=None):
        """Run pr-watch.sh; return (exit code or None if it was stopped, lines without the time)."""
        args = [PR_WATCH, self.clone, "task 1", "--since", "2026-11-15T00:00:00Z",
                "--interval", "1", *extra]
        p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, env=self.env)
        try:
            out, _ = p.communicate(timeout=run_for or 30)
            code = p.returncode
        except subprocess.TimeoutExpired:
            p.terminate()
            out, _ = p.communicate()
            code = None
        return code, [l.split(" ", 1)[1] for l in out.splitlines() if l.strip()]

    def test_shrinking_pending_count_is_silent(self):
        self.scenario("OPEN 5", "OPEN 4", "OPEN 3", "OPEN 0", "MERGED 0")
        code, lines = self.pr_watch()
        self.assertEqual(code, 0)
        self.assertEqual(len(lines), 4, lines)
        self.assertTrue(lines[0].endswith("pending=5"))
        self.assertTrue(lines[1].endswith("pending=0"))
        self.assertIn("state=MERGED", lines[2])
        self.assertEqual(lines[3], "done: PR #7 state=MERGED")

    def test_new_failing_check_prints(self):
        self.scenario("OPEN 3", "OPEN 2 lint", "MERGED 0 lint")
        code, lines = self.pr_watch()
        self.assertEqual(code, 0)
        self.assertIn("failing=[lint] pending=2", lines[1])

    def test_state_restart_replays_nothing(self):
        self.scenario("OPEN 3")
        _, first = self.pr_watch("--state", self.state, run_for=4)
        self.assertEqual(len(first), 1, first)
        self.scenario("OPEN 2")
        _, again = self.pr_watch("--state", self.state, run_for=4)
        self.assertEqual(again, [])

    def test_merged_done_not_replayed_on_restart(self):
        self.scenario("MERGED 0")
        code, first = self.pr_watch("--state", self.state)
        self.assertEqual((code, first[-1]), (0, "done: PR #7 state=MERGED"))
        self.scenario("MERGED 0")
        code, again = self.pr_watch("--state", self.state)
        self.assertEqual((code, again), (0, []))

    def test_single_failure_is_silent_and_recovery_reprints_nothing(self):
        self.scenario("OPEN 0", "FAIL", "OPEN 0", "MERGED 0")
        code, lines = self.pr_watch()
        self.assertEqual(code, 0)
        self.assertEqual(len(lines), 3, lines)
        self.assertNotIn("github-unreachable", " ".join(lines))

    def test_outage_prints_once(self):
        self.scenario("OPEN 0", "FAIL", "FAIL", "FAIL", "OPEN 0", "MERGED 0")
        code, lines = self.pr_watch()
        self.assertEqual(code, 0)
        self.assertEqual(sum(l.startswith("github-unreachable") for l in lines), 1, lines)
        self.assertEqual(sum("state=OPEN" in l for l in lines), 1, lines)

    def test_bad_interval_is_refused(self):
        # An empty value is refused by bash's ${2:?} (exit 1); malformed ones by the check (exit 2).
        for bad in ("90s", "1.5", ""):
            r = subprocess.run([PR_WATCH, self.clone, "task 1", "--interval", bad],
                               capture_output=True, text=True, env=self.env, timeout=10)
            self.assertIn(r.returncode, (1, 2) if bad == "" else (2,), bad)
            r = subprocess.run([TEAM_WATCH, self.clone, "--interval", bad, "A a1-1|task 1|2026-11-15T00:00:00Z"],
                               capture_output=True, text=True, env=self.env, timeout=10)
            self.assertIn(r.returncode, (1, 2) if bad == "" else (2,), bad)

    def test_team_watch_tags_lines_and_leaves_no_children(self):
        self.scenario("OPEN 3")
        p = subprocess.Popen([TEAM_WATCH, self.clone, "--interval", "1", "--fresh",
                              "Ada a1-1|task 1|2026-11-15T00:00:00Z",
                              "Linus a2-1|task 2|2026-11-15T00:00:00Z"],
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=self.env)
        time.sleep(4)
        p.send_signal(signal.SIGTERM)
        out, _ = p.communicate(timeout=10)
        self.assertIn("[Ada a1-1] branches=", out)
        self.assertIn("[Linus a2-1] branches=", out)
        time.sleep(6)  # children notice the missing parent within one 5-second step
        ps = subprocess.run(["ps", "-eo", "args"], capture_output=True, text=True).stdout
        self.assertNotIn(self.clone, ps)


if __name__ == "__main__":
    unittest.main()
