"""Unit tests for `track.py daily-pr` writing the PR body (Bob, 2026-11-06: "Yes, fix daily-pr").

The harness master and a new job have no job/Project-* folder, so rp.TRACKING raises NoProjectError. daily-pr used to
crash there; it now sends the body through a temp file. With a project, the body is still kept in its tracking folder.
gh and git are never called for real. Stdlib unittest, as CI runs it:

    .\\harness\\tools\\venv\\Scripts\\python.exe -m unittest discover -s harness\\tests -v
"""
from __future__ import annotations

import argparse
import contextlib
import io
import os
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

BODY = "## Day\nDate: 2026-11-06\n\n## Todd's requirements\nNone.\n\n## Drawings filed\nNone.\n"
GO = "Yes, fix daily-pr"


def tearDownModule() -> None:
    if _saved is None:
        os.environ.pop("GH_CONFIG_DIR", None)
    else:
        os.environ["GH_CONFIG_DIR"] = _saved


class _NoProject:
    """Stands in for repo_paths in a repo with no project folder."""
    NoProjectError = T.rp.NoProjectError

    @property
    def TRACKING(self):
        raise T.rp.NoProjectError("no project yet")


class _Project:
    NoProjectError = T.rp.NoProjectError

    def __init__(self, tracking: Path):
        self.TRACKING = tracking


class DailyPrBody(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.body_file = self.tmp / "body.md"
        self.body_file.write_text(BODY, encoding="utf-8")
        self.created: dict = {}

        def fake_gh(*args, **_kw):
            if args[:2] == ("pr", "list"):
                return "[]"
            if args[:2] == ("pr", "create"):
                path = Path(args[args.index("--body-file") + 1])
                self.created = {"path": path, "text": path.read_text(encoding="utf-8")}
                return "https://github.com/example/repo/pull/1"
            raise AssertionError(f"unexpected gh call {args}")

        for target, new in (("gh", fake_gh), ("require_writer", lambda: None), ("repo_slug", lambda: "example/repo"),
                            ("linear_pr_note", lambda body, date: None),
                            ("git_remote", lambda *a, **k: "abc123\trefs/heads/daily/2026-11-06")):
            p = mock.patch.object(T, target, new)
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(setattr, T, "DRY", T.DRY)
        T.DRY = False

    def call(self) -> str:
        a = argparse.Namespace(bob_go=GO, date="2026-11-06", title="t", body_file=str(self.body_file),
                               closes=[], reviewer=[], base=None)
        with contextlib.redirect_stdout(io.StringIO()):
            return T.cmd_daily_pr(a)

    def test_no_project_uses_temp_file(self):
        with mock.patch.object(T, "rp", _NoProject()):
            url = self.call()
        self.assertEqual(url, "https://github.com/example/repo/pull/1")
        self.assertIn("## Drawings filed", self.created["text"])
        self.assertIn(f'Bob\'s go (', self.created["text"])
        self.assertIn(GO, self.created["text"])
        self.assertFalse(self.created["path"].exists(), "temp body file is removed afterwards")

    def test_project_keeps_body_in_tracking(self):
        tracking = self.tmp / "tracking"
        with mock.patch.object(T, "rp", _Project(tracking)):
            self.call()
        self.assertEqual(self.created["path"], tracking / "pr-2026-11-06.md")
        self.assertTrue(self.created["path"].exists(), "the body stays in the project's tracking folder")


if __name__ == "__main__":
    unittest.main()
