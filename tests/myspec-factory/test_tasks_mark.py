"""Tests for plugins/myspec-factory/skills/integrate/scripts/tasks-mark.py, through its command line.

Run from the repository root: python3 -m unittest discover -s tests/myspec-factory -v
"""
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPT = os.environ.get("TASKS_MARK_SCRIPT") or os.path.join(
    ROOT, "plugins", "myspec-factory", "skills", "integrate", "scripts", "tasks-mark.py")

TASKS = """# Implementation Tasks: Demo

## Milestone 1: Core

- [ ] 1\\. First task
  - Acceptance Criteria:
    - it works
  - _Dependencies: none_

- [-] 2\\. Second task
  - _Dependencies: 1_

- [x] 22\\. Done already
  - _Dependencies: none_

- [ ] 22.1 OpenSpec-style child

```markdown
- [ ] 3\\. An example inside a code fence
```

- [ ] 3\\. Third task

## Phase 1: Setup
- [ ] T1 Spec Kit one (file: a.ts)
- [-] T10 Spec Kit ten (file: b.ts)
- [ ] T007 [P] [US1] Spec Kit seven (file: c.ts)

## Branch Plan

### Lane 1: core
- Tasks (in order): 1, 2
"""


class TasksMarkTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.file = os.path.join(self.tmp.name, "tasks.md")
        with open(self.file, "w") as f:
            f.write(TASKS)

    def tearDown(self):
        self.tmp.cleanup()

    def run_cmd(self, *args):
        return subprocess.run([sys.executable, SCRIPT, "--file", self.file, *args], capture_output=True, text=True)

    def text(self):
        with open(self.file) as f:
            return f.read()

    def test_pending_and_in_progress_become_done_with_the_note(self):
        r = self.run_cmd("--tasks", "1,2", "--done", "--note", "Merged: PR #9 (abc1234)")
        self.assertEqual(r.returncode, 0, r.stderr)
        expected = (TASKS
                    .replace("- [ ] 1\\. First task\n  - Acceptance Criteria:\n    - it works\n  - _Dependencies: none_\n",
                             "- [x] 1\\. First task\n  - Acceptance Criteria:\n    - it works\n  - _Dependencies: none_\n"
                             "  - Merged: PR #9 (abc1234)\n")
                    .replace("- [-] 2\\. Second task\n  - _Dependencies: 1_\n",
                             "- [x] 2\\. Second task\n  - _Dependencies: 1_\n  - Merged: PR #9 (abc1234)\n"))
        self.assertEqual(self.text(), expected)

    def test_running_twice_changes_nothing_more(self):
        self.run_cmd("--tasks", "1,2,T10", "--done", "--note", "Merged: PR #9 (abc1234)")
        once = self.text()
        r = self.run_cmd("--tasks", "1,2,T10", "--done", "--note", "Merged: PR #9 (abc1234)")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.text(), once)

    def test_spec_kit_ids_match_exactly(self):
        self.assertEqual(self.run_cmd("--tasks", "T1", "--done").returncode, 0)
        text = self.text()
        self.assertIn("- [x] T1 Spec Kit one", text)
        self.assertIn("- [-] T10 Spec Kit ten", text)
        self.assertEqual(self.run_cmd("--tasks", "T007", "--done").returncode, 0)
        self.assertIn("- [x] T007 [P] [US1] Spec Kit seven", self.text())
        self.assertEqual(self.run_cmd("--tasks", "T7", "--done").returncode, 1)

    def test_a_number_never_matches_its_children(self):
        self.assertEqual(self.run_cmd("--tasks", "22", "--note", "Clarification: x").returncode, 0)
        text = self.text()
        self.assertIn("- [x] 22\\. Done already\n  - _Dependencies: none_\n  - Clarification: x\n", text)
        self.assertIn("- [ ] 22.1 OpenSpec-style child\n\n", text)

    def test_fenced_examples_and_the_branch_plan_stay_unchanged(self):
        r = self.run_cmd("--tasks", "3", "--done")
        self.assertEqual(r.returncode, 0, r.stderr)
        text = self.text()
        self.assertIn("```markdown\n- [ ] 3\\. An example inside a code fence\n```", text)
        self.assertIn("- [x] 3\\. Third task", text)
        self.assertTrue(text.endswith("### Lane 1: core\n- Tasks (in order): 1, 2\n"))

    def test_unknown_task_writes_nothing(self):
        r = self.run_cmd("--tasks", "1,99", "--done")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.text(), TASKS)


if __name__ == "__main__":
    unittest.main()
