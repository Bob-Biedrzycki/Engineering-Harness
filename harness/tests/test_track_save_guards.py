"""Tests of the two `track.py save` guards (REVW-001, 2026-11-23): CAPA PA-2, a saved path in a folder nothing names is
refused unless its job/folder-register.csv row is in the same save; CAPA PA-3, a harness-owned file that differs from
the Engineering Harness master is refused (master missing: skipped; saving in the master itself: passes).

Scratch repos only; no Drive push, no commit, no push (subprocess and the commit step are mocked where cmd_save is
run). Stdlib unittest, as CI runs it:

    .\\harness\\tools\\venv\\Scripts\\python.exe -m unittest harness.tests.test_track_save_guards -v
"""
from __future__ import annotations

import argparse
import contextlib
import csv
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists())
sys.path.insert(0, str(REPO / "harness" / "scripts"))
sys.path.insert(0, str(REPO / "harness" / "lib"))
sys.path.insert(0, str(REPO / "harness" / "checks"))
_saved = os.environ.get("GH_CONFIG_DIR")
import track as T  # noqa: E402  (importing sets GH_CONFIG_DIR; restored in tearDownModule)
import folder_layout as FL  # noqa: E402
import harness_sync as HS  # noqa: E402

PROJ = "job/Project-0000-00-TST-001"
PROBE = f"{PROJ}/03_Working_Design/CAPA-probe-folder"
MANIFEST = "harness/**\n!harness/tools/**\n.gitignore#core\n"


def tearDownModule() -> None:
    if _saved is None:
        os.environ.pop("GH_CONFIG_DIR", None)
    else:
        os.environ["GH_CONFIG_DIR"] = _saved


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
                   check=True, capture_output=True)


def register(root: Path, *paths: str) -> None:
    with open(root / FL.REGISTER_REL, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(FL.COLUMNS)
        for p in paths:
            w.writerow([p, "project", "x", "hand", "tracked", "active", "test", "2026-11-23"])


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="track-guards-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.root = self.tmp / "job-repo"
        self.master = self.tmp / "master"
        for r in (self.root, self.master):
            (r / "harness" / "lib").mkdir(parents=True)
            (r / HS.MANIFEST_REL).write_text(MANIFEST, encoding="utf-8")
            (r / "harness" / "lib" / "tool.py").write_text("x = 1\n", encoding="utf-8")
        (self.root / FL.TEMPLATE_REL / "03_Working_Design").mkdir(parents=True)
        (self.root / PROJ / "03_Working_Design").mkdir(parents=True)
        (self.root / PROBE).mkdir()
        (self.root / PROBE / "probe.txt").write_text("probe\n", encoding="utf-8")
        self.paths = self.tmp / "paths.txt"
        # the folder tests run with no master on the machine, so only the folder guard speaks
        p = mock.patch.object(HS, "default_master", return_value=self.tmp / "no-master-here")
        p.start()
        self.addCleanup(p.stop)

    def save_paths(self, *paths: str) -> str:
        self.paths.write_text("\n".join(paths) + "\n", encoding="utf-8")
        return str(self.paths)

    def refused(self, fn, *a, **kw) -> str:
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()), \
                self.assertRaises(SystemExit) as cm:
            fn(*a, **kw)
        self.assertEqual(cm.exception.code, 2)
        return err.getvalue()

    def passes(self, fn, *a, **kw):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            r = fn(*a, **kw)
        return r, out.getvalue()


class FolderGuard(Base):
    def test_unnamed_folder_refused(self):
        register(self.root)
        err = self.refused(T.save_guards, self.save_paths(f"{PROBE}/probe.txt", FL.REGISTER_REL), "2026-11-23",
                           root=self.root)
        self.assertIn(f"{PROBE}/probe.txt is in a folder nothing names. Use an existing location, or (CLAUDE.md 'No new "
                      "location without a name') tell Bob the full path first and add it to job/folder-register.csv "
                      "in this same save.", err)
        self.assertTrue(err.startswith("REFUSED: "))

    def test_register_row_in_same_save_passes(self):
        register(self.root, PROBE)
        self.passes(T.save_guards, self.save_paths(f"{PROBE}/probe.txt", FL.REGISTER_REL), "2026-11-23", root=self.root)

    def test_register_row_left_out_of_the_save_refused(self):
        """The row is in the working copy only; the save's base (origin/main) does not have it and the register is
        not listed, so the commit would not hold it: refused. Listing the register passes."""
        register(self.root)
        git(self.root, "init", "-q")
        git(self.root, "add", FL.REGISTER_REL)
        git(self.root, "commit", "-q", "-m", "base")
        git(self.root, "update-ref", "refs/remotes/origin/main", "HEAD")
        register(self.root, PROBE)
        self.refused(T.save_guards, self.save_paths(f"{PROBE}/probe.txt"), "2026-11-23", root=self.root)
        self.passes(T.save_guards, self.save_paths(f"{PROBE}/probe.txt", FL.REGISTER_REL), "2026-11-23", root=self.root)

    def test_no_register_not_checked(self):
        _, out = self.passes(T.save_guards, self.save_paths(f"{PROBE}/probe.txt"), "2026-11-23", root=self.root)
        self.assertIn("folders: not checked (no job/folder-register.csv)", out)

    def test_cmd_save_refuses_before_any_push(self):
        register(self.root)
        a = argparse.Namespace(date="2026-11-23", paths_file=self.save_paths(f"{PROBE}/probe.txt", FL.REGISTER_REL),
                               message_file="unused", tag=[], moves_file=None, removes_file=None)
        with mock.patch.object(T, "REPO", self.root), mock.patch.object(T.subprocess, "run") as run, \
                mock.patch.object(T, "cmd_daily_commit") as commit:
            self.refused(T.cmd_save, a)
        run.assert_not_called()
        commit.assert_not_called()

    def test_cmd_save_goes_on_when_named(self):
        register(self.root, PROBE)
        a = argparse.Namespace(date="2026-11-23", paths_file=self.save_paths(f"{PROBE}/probe.txt", FL.REGISTER_REL),
                               message_file="unused", tag=[], moves_file=None, removes_file=None)
        done = subprocess.CompletedProcess([], 0, "drive push: nothing to push\n", "")
        dry = T.DRY
        self.addCleanup(setattr, T, "DRY", dry)
        T.DRY = True
        with mock.patch.object(T, "REPO", self.root), mock.patch.object(T.subprocess, "run", return_value=done), \
                mock.patch.object(T, "cmd_daily_commit") as commit, contextlib.redirect_stdout(io.StringIO()):
            T.cmd_save(a)
        commit.assert_called_once()


class MasterGuard(Base):
    def test_identical_passes(self):
        r, _ = self.passes(T.master_refusals, ["harness/lib/tool.py"], root=self.root, master=self.master)
        self.assertEqual(r, [])

    def test_differs_refused(self):
        (self.root / "harness/lib/tool.py").write_text("x = 2\n", encoding="utf-8")
        r, _ = self.passes(T.master_refusals, ["harness/lib/tool.py", f"{PROBE}/probe.txt"], root=self.root,
                           master=self.master)
        self.assertEqual(r, ["harness/lib/tool.py is a harness file that differs from the Engineering Harness master. "
                             "Make the change in the master and run harness_sync.py pull."])

    def test_absent_in_master_refused_and_folders_walked(self):
        (self.root / "harness/lib/new_tool.py").write_text("y = 1\n", encoding="utf-8")
        r, _ = self.passes(T.master_refusals, ["harness/lib"], root=self.root, master=self.master)
        self.assertEqual(len(r), 1)
        self.assertIn("harness/lib/new_tool.py is a harness file", r[0])
        self.assertIn("(absent in the master)", r[0])

    def test_gitignore_core_lines_compared(self):
        block = "# >>> drive-store (managed by harness/scripts/drive_store.py; do not edit) >>>\n"
        (self.master / ".gitignore").write_text("_work/\n", encoding="utf-8")
        (self.root / ".gitignore").write_text("_work/\n", encoding="utf-8")
        r, _ = self.passes(T.master_refusals, [".gitignore"], root=self.root, master=self.master)
        self.assertEqual(r, [])
        (self.root / ".gitignore").write_text("_work/\nmine/\n", encoding="utf-8")
        r, _ = self.passes(T.master_refusals, [".gitignore"], root=self.root, master=self.master)
        self.assertEqual(len(r), 1, block)

    def test_master_missing_skipped(self):
        (self.root / "harness/lib/tool.py").write_text("x = 2\n", encoding="utf-8")
        r, out = self.passes(T.master_refusals, ["harness/lib/tool.py"], root=self.root, master=self.tmp / "absent")
        self.assertEqual(r, [])
        self.assertIn("harness master: not checked (no master folder", out)

    def test_saving_in_the_master_passes(self):
        (self.master / "harness/lib/tool.py").write_text("x = 3\n", encoding="utf-8")
        r, _ = self.passes(T.master_refusals, ["harness/lib/tool.py"], root=self.master, master=self.master)
        self.assertEqual(r, [])

    def test_save_guards_refuses_a_changed_harness_file(self):
        (self.root / "harness/lib/tool.py").write_text("x = 2\n", encoding="utf-8")
        with mock.patch.object(HS, "default_master", return_value=self.master):
            err = self.refused(T.save_guards, self.save_paths("harness/lib/tool.py"), "2026-11-23", root=self.root)
        self.assertIn("harness/lib/tool.py is a harness file that differs from the Engineering Harness master.", err)


if __name__ == "__main__":
    unittest.main()
