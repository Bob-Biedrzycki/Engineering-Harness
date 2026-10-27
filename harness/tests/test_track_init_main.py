"""Unit tests for `track.py init-main`: the one-time first commit of a new job repo (Bob, 2026-10-27: "fix track.py's
first-commit path so the first commit can be made"). A brand-new GitHub repo has no `main`, so daily-commit has
nothing to build the day's branch on; init-main pushes one EMPTY commit as `main` and changes no working-tree file.

Runs against a scratch clone with a local bare repo as `origin`; gh is never called (require_writer and the gh
credential helper are patched out). Stdlib unittest, as CI runs it:

    .\\harness\\tools\\venv\\Scripts\\python.exe -m unittest discover -s harness\\tests -v
"""
from __future__ import annotations

import argparse
import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists())
sys.path.insert(0, str(REPO / "harness" / "scripts"))
sys.path.insert(0, str(REPO / "harness" / "lib"))
_saved = os.environ.get("GH_CONFIG_DIR")
import track as T  # noqa: E402  (importing sets GH_CONFIG_DIR in os.environ; restored in tearDownModule)

EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


def tearDownModule() -> None:
    if _saved is None:
        os.environ.pop("GH_CONFIG_DIR", None)
    else:
        os.environ["GH_CONFIG_DIR"] = _saved


def sh(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


class InitMain(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        tmp = Path(self._tmp.name)
        self.bare, self.work = tmp / "origin.git", tmp / "work"
        sh(tmp, "init", "--bare", "-b", "main", str(self.bare))
        sh(tmp, "init", "-b", "main", str(self.work))
        sh(self.work, "config", "user.name", "Test")
        sh(self.work, "config", "user.email", "test@example.com")
        sh(self.work, "remote", "add", "origin", str(self.bare))
        (self.work / "untracked.txt").write_text("stays untracked\n", encoding="utf-8")
        for target, new in (("REPO", self.work), ("require_writer", lambda: None),
                            ("git_remote", lambda *a, cwd=None, write=False: T.git(*a, cwd=cwd, write=write))):
            p = mock.patch.object(T, target, new)
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(setattr, T, "DRY", T.DRY)
        T.DRY = False

    def call(self, go="Yes, make the first commit"):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            T.cmd_init_main(argparse.Namespace(bob_go=go))
        return out.getvalue()

    def refused(self, go="go") -> str:
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()), \
                self.assertRaises(SystemExit) as cm:
            T.cmd_init_main(argparse.Namespace(bob_go=go))
        self.assertEqual(cm.exception.code, 2)
        return err.getvalue()

    def test_creates_empty_main_on_origin_and_locally(self):
        self.call()
        remote = sh(self.bare, "rev-parse", "refs/heads/main")
        self.assertEqual(sh(self.work, "rev-parse", "refs/heads/main"), remote)
        self.assertEqual(sh(self.work, "rev-parse", "refs/remotes/origin/main"), remote)
        self.assertEqual(sh(self.bare, "rev-parse", "main^{tree}"), EMPTY_TREE)
        msg = sh(self.bare, "log", "-1", "--format=%B", "main")
        for part in ("repo: empty first commit", "**Why**", "**Checks run**", 'Bob\'s go: "Yes, make the first commit"'):
            self.assertIn(part, msg)

    def test_working_tree_untouched(self):
        self.call()
        self.assertTrue((self.work / "untracked.txt").exists())
        self.assertIn("?? untracked.txt", sh(self.work, "status", "--porcelain"))

    def test_refused_without_go(self):
        self.assertIn("Bob's go", self.refused(go=""))

    def test_refused_when_origin_has_a_branch(self):
        self.call()
        self.assertIn("origin already has branches", self.refused())

    def test_refused_when_local_main_has_a_commit(self):
        (self.work / "a.txt").write_text("a\n", encoding="utf-8")
        sh(self.work, "add", "a.txt")
        sh(self.work, "commit", "-m", "x")
        self.assertIn("local main already has a commit", self.refused())

    def test_dry_run_writes_nothing(self):
        T.DRY = True
        out = self.call()
        self.assertIn("DRY-RUN would run: git push", out)
        self.assertEqual(sh(self.bare, "for-each-ref"), "")
        self.assertEqual(subprocess.run(["git", "rev-parse", "--verify", "--quiet", "refs/heads/main"],
                                        cwd=self.work, capture_output=True).returncode, 1)


if __name__ == "__main__":
    unittest.main()
