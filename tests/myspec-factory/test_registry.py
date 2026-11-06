"""Tests for plugins/myspec-factory/skills/dispatch/scripts/registry.py, through its command line.

Run from the repository root: python3 -m unittest discover -s tests/myspec-factory -v
Python 3 standard library only, like the script.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPT = os.environ.get("REGISTRY_SCRIPT") or os.path.join(
    ROOT, "plugins", "myspec-factory", "skills", "dispatch", "scripts", "registry.py")


class RegistryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.makedirs(os.path.join(self.tmp.name, ".specs", "b"))
        self.file = os.path.join(self.tmp.name, ".specs", "b", "factory-sessions.json")
        with open(self.file, "w") as f:
            json.dump({"project_id": "p", "bundle": "b", "team": []}, f)

    def tearDown(self):
        self.tmp.cleanup()

    def run_cmd(self, *args, ok=True):
        r = subprocess.run([sys.executable, SCRIPT, "--file", self.file, *args],
                           capture_output=True, text=True)
        if ok:
            self.assertEqual(r.returncode, 0, f"{args}: {r.stderr}")
        return r

    def data(self):
        with open(self.file) as f:
            return json.load(f)

    def add(self, agent, *extra):
        return self.run_cmd("add-agent", "--agent", agent, "--path", "cloud-cli", "--session-id",
                            f"session_{agent}_{len(self.data()['team'])}", "--url", "u",
                            "--started-at", "2026-11-06T10:00:00Z", *extra)

    # names
    def test_default_name_follows_the_slot(self):
        self.assertEqual(self.run_cmd("name", "--agent", "a3").stdout.split("\t")[0], "Grace")
        self.add("a3")
        self.add("a1")
        names = {e["agent"]: (e["name"], e["title"]) for e in self.data()["team"]}
        self.assertEqual(names, {"a3": ("Grace", "Grace (a3)"), "a1": ("Ada", "Ada (a1)")})

    def test_parallel_names_and_adds_never_collide_or_get_lost(self):
        slots = [f"a{k}" for k in range(1, 13)]
        with ThreadPoolExecutor(len(slots)) as pool:
            names = list(pool.map(lambda s: self.run_cmd("name", "--agent", s).stdout.split("\t")[0], slots))
        self.assertEqual(len(set(names)), len(slots))
        with ThreadPoolExecutor(len(slots)) as pool:
            results = list(pool.map(lambda s: subprocess.run(
                [sys.executable, SCRIPT, "--file", self.file, "add-agent", "--agent", s, "--path", "cloud-cli",
                 "--session-id", f"session_{s}", "--url", "u", "--started-at", "t"],
                capture_output=True, text=True), slots))
        self.assertTrue(all(r.returncode == 0 for r in results), [r.stderr for r in results])
        team = self.data()["team"]
        self.assertEqual(sorted(e["agent"] for e in team), sorted(slots))
        self.assertEqual(sorted(e["name"] for e in team), sorted(names))

    def test_name_rules(self):
        self.add("a1")
        self.assertEqual(self.run_cmd("add-agent", "--agent", "a2", "--name", "Ada", "--path", "p",
                                      "--session-id", "s", "--url", "u", "--started-at", "t", ok=False).returncode, 2)
        self.assertEqual(self.run_cmd("add-agent", "--agent", "a2", "--name", "grace", "--path", "p",
                                      "--session-id", "s", "--url", "u", "--started-at", "t", ok=False).returncode, 2)
        # A replacement keeps the slot's name, and a different name is refused.
        self.assertEqual(self.run_cmd("name", "--agent", "a1", "--replace").stdout.strip(), "Ada\tAda (a1.r2)\tw:a1.r2")
        self.assertEqual(self.run_cmd("add-agent", "--agent", "a1", "--replace", "--name", "Bob", "--path", "p",
                                      "--session-id", "s", "--url", "u", "--started-at", "t", ok=False).returncode, 2)

    # replacement
    def test_replace_merges_the_queue(self):
        self.add("a1", "--queue", "1,2", "3", "4")
        self.add("a1", "--replace", "--queue", "4", "9")
        team = self.data()["team"]
        self.assertEqual(team[0]["status"], "replaced")
        self.assertEqual(team[0]["queue"], [])
        self.assertEqual(team[1]["worker_id"], "w:a1.r2")
        self.assertEqual(team[1]["queue"], ["4", "9", "1,2", "3"])

    def test_whois_rejects_a_replaced_session(self):
        self.add("a1")
        self.add("a1", "--replace")
        old, new = self.data()["team"]
        self.assertEqual(self.run_cmd("whois", "--from", "w:a1", "--key", old["worker_key"], ok=False).returncode, 1)
        self.run_cmd("whois", "--from", "w:a1.r2", "--key", new["worker_key"])
        self.assertEqual(self.run_cmd("whois", "--from", "w:a1.r2", "--key", "bad", ok=False).returncode, 1)

    # queues and assignments
    def test_assign_pops_the_queue_and_move_rebalances(self):
        self.add("a1", "--queue", "1,2", "3")
        self.add("a2")
        out = self.run_cmd("assign", "--agent", "a1", "--tasks", "1, 2", "--title", "t", "--branch", "b").stdout
        self.assertIn("a1-1", out)
        self.run_cmd("move", "--group", "3", "--to", "linus")
        a1, a2 = self.data()["team"]
        self.assertEqual(a1["queue"], [])
        self.assertEqual(a2["queue"], ["3"])
        self.assertEqual(a1["status"], "running")
        self.assertEqual(self.run_cmd("move", "--group", "1,2", "--to", "a2", ok=False).returncode, 1)

    def test_assignment_selectors(self):
        self.add("a1")
        self.run_cmd("assign", "--agent", "a1", "--tasks", "1,2", "--title", "t", "--branch", "b")
        self.run_cmd("set", "--assignment", "2", "pr=7")
        self.run_cmd("set", "--assignment", "pr:7", "verified_sha=abc")
        self.run_cmd("assign", "--agent", "Ada", "--tasks", "2", "--title", "t", "--branch", "b2")
        # Task 2 is now carried by two live assignments: refuse rather than guess.
        self.assertEqual(self.run_cmd("set", "--assignment", "2", "status=merged", ok=False).returncode, 1)
        self.run_cmd("set", "--assignment", "a1-2", "status=pr-open")
        self.run_cmd("note", "--assignment", "last", "x")
        asg = self.data()["team"][0]["assignments"]
        self.assertEqual((asg[0]["pr"], asg[0]["verified_sha"]), (7, "abc"))
        self.assertEqual((asg[1]["status"], asg[1]["notes"].endswith("x")), ("pr-open", True))

    def test_pr_selector_prefers_the_live_assignment(self):
        self.add("a1")
        self.run_cmd("assign", "--agent", "a1", "--tasks", "1", "--title", "t", "--branch", "b")
        self.run_cmd("set", "--assignment", "a1-1", "pr=10", "status=failed")
        self.add("a1", "--replace")
        self.run_cmd("assign", "--agent", "a1", "--tasks", "1", "--title", "t", "--branch", "b")
        self.run_cmd("set", "--assignment", "a1-2", "pr=10")
        self.run_cmd("set", "--assignment", "pr:10", "verified_sha=def")
        old, new = self.data()["team"]
        self.assertIsNone(old["assignments"][0]["verified_sha"])
        self.assertEqual(new["assignments"][0]["verified_sha"], "def")

    # guards
    def test_stream_urls_are_refused(self):
        self.add("a1")
        r = self.run_cmd("agent", "--agent", "a1", "url=wss://x/realtime/v1/stream/abc", ok=False)
        self.assertEqual(r.returncode, 2)
        with open(self.file) as f:
            self.assertNotIn("wss://", f.read())

    def test_rung_must_be_on_the_ladder(self):
        r = self.run_cmd("add-agent", "--agent", "a1", "--path", "p", "--session-id", "s", "--url", "u",
                         "--started-at", "t", "--model", "sonnet", "--effort", "high", ok=False)
        self.assertEqual(r.returncode, 2)


if __name__ == "__main__":
    unittest.main()
