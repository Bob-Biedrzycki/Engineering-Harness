"""Unit tests for `track.py after-merge` taking Bob's go from chat (Bob, chat, 2026-11-06: "fix the in file
requirement. I will tell you to merge through the chat").

after-merge used to run only from the day's go file, which exists only inside a job/Project-* folder, so it crashed
in the harness master. It now takes Bob's words with --bob-go and falls back to the go file. gh, git and the site
publish are never called for real. Stdlib unittest, as CI runs it:

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

DATE = "2026-11-06"
_NoProjectError = getattr(T.rp, "NoProjectError", LookupError)


def tearDownModule() -> None:
    if _saved is None:
        os.environ.pop("GH_CONFIG_DIR", None)
    else:
        os.environ["GH_CONFIG_DIR"] = _saved


def _no_project(_date):
    """go_file in a repo with no project folder (the harness master): repo_paths.DAILY raises."""
    raise _NoProjectError("no project yet")


def _in(daily: Path):
    return lambda date: daily / f"{date}-go.txt"


class AfterMergeGo(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.synced: list[str] = []
        self.published: list[str] = []
        merged = '[{"number": 1, "state": "MERGED", "url": "https://github.com/example/repo/pull/1"}]'
        for target, new in (("require_auth", lambda: None), ("repo_slug", lambda: "example/repo"),
                            ("gh", lambda *a, **k: merged),
                            ("cmd_sync_main", lambda a: self.synced.append(a.bob_go)),
                            ("publish_after_merge", lambda go: self.published.append(go))):
            p = mock.patch.object(T, target, new)
            p.start()
            self.addCleanup(p.stop)

    def run_cmd(self, bob_go):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            T.cmd_after_merge(argparse.Namespace(date=DATE, bob_go=bob_go))
        return out.getvalue()

    def refused(self, bob_go) -> str:
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()), \
                self.assertRaises(SystemExit):
            T.cmd_after_merge(argparse.Namespace(date=DATE, bob_go=bob_go))
        return err.getvalue()

    def test_go_from_chat_with_no_project_folder(self):
        with mock.patch.object(T, "go_file", _no_project):
            out = self.run_cmd("Yes, run after-merge")
        self.assertIn('"Yes, run after-merge" (from chat, --bob-go)', out)
        self.assertEqual(self.synced, ["Yes, run after-merge"])
        self.assertEqual(self.published, ["Yes, run after-merge"])

    def test_go_from_chat_ignores_missing_go_file(self):
        with mock.patch.object(T, "go_file", _in(self.tmp / "daily")):
            self.run_cmd("merge it")
        self.assertEqual(self.synced, ["merge it"])

    @unittest.skipUnless(hasattr(T.rp, "NoProjectError"), "this repo's repo_paths has no NoProjectError")
    def test_no_go_and_no_project_is_refused_with_a_clear_message(self):
        with mock.patch.object(T, "go_file", _no_project):
            self.assertIn("--bob-go", self.refused(None))
        self.assertEqual(self.synced, [])

    def test_no_go_and_no_go_file_is_refused(self):
        with mock.patch.object(T, "go_file", _in(self.tmp / "daily")):
            self.assertIn("--bob-go", self.refused(""))
        self.assertEqual(self.synced, [])

    def test_go_file_still_works_as_fallback(self):
        daily = self.tmp / "daily"
        daily.mkdir()
        (daily / f"{DATE}-go.txt").write_text("Bob, chat: merged\n", encoding="utf-8")
        with mock.patch.object(T, "go_file", _in(daily)):
            self.run_cmd(None)
        self.assertEqual(self.synced, ["Bob, chat: merged"])


if __name__ == "__main__":
    unittest.main()
