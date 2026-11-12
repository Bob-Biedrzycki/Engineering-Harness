"""Tests for where a new day's branch starts in harness/scripts/track.py (new_day_base, bring_in_earlier_days).

Bob, 2026-11-11 ("fix it"): when an earlier day is not merged, the new day's branch holds that day's work instead
of starting from main without it. Each test makes its own temporary origin and clone with real git; no network, and
the repo this test file sits in is never touched. Stdlib unittest:

    .\\harness\\tools\\venv\\Scripts\\python.exe -m unittest discover -s harness\\tests -v
"""
from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists())
sys.path.insert(0, str(REPO / "harness" / "scripts"))
sys.path.insert(0, str(REPO / "harness" / "lib"))
_saved = os.environ.get("GH_CONFIG_DIR")
import track as T  # noqa: E402  (importing sets GH_CONFIG_DIR in os.environ; restored in tearDownModule)

DAY1, DAY2, DAY3 = "daily/2026-01-01", "daily/2026-01-02", "daily/2026-01-03"


def tearDownModule() -> None:
    if _saved is None:
        os.environ.pop("GH_CONFIG_DIR", None)
    else:
        os.environ["GH_CONFIG_DIR"] = _saved


def g(cwd: Path, *args: str) -> str:
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed in {cwd}:\n{r.stdout}\n{r.stderr}")
    return r.stdout.strip()


def _rm(path: Path) -> None:
    def writable(fn, p, _exc):
        os.chmod(p, stat.S_IWRITE)
        fn(p)
    shutil.rmtree(path, onerror=writable)


@unittest.skipUnless(shutil.which("git"), "git is not on PATH")
class NewDay(unittest.TestCase):
    """origin (bare) with main; a clone that saves days the way track.py does (a worktree, pushed as a branch)."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="newday-"))
        self.addCleanup(_rm, self.tmp)
        self.origin = self.tmp / "origin.git"
        self.clone = self.tmp / "clone"
        g(self.tmp, "init", "-q", "--bare", "-b", "main", str(self.origin))
        g(self.tmp, "clone", "-q", str(self.origin), str(self.clone))
        for k, v in (("user.name", "Test"), ("user.email", "test@example.invalid"), ("commit.gpgsign", "false"),
                     ("core.autocrlf", "false")):
            g(self.clone, "config", k, v)
        g(self.clone, "checkout", "-q", "-b", "main")
        self.commit(self.clone, "base.txt", "base\n", "base")
        g(self.clone, "push", "-q", "origin", "main")
        g(self.clone, "fetch", "-q", "origin")

    def commit(self, where: Path, name: str, text: str, msg: str) -> None:
        (where / name).write_text(text, encoding="utf-8", newline="\n")
        g(where, "add", "--", name)
        g(where, "commit", "-q", "-m", msg)

    def save_day(self, branch: str, base: str, name: str, text: str) -> None:
        """One commit on a day branch built on `base`, pushed, the way a save leaves it."""
        wt = self.tmp / ("wt-" + branch.replace("/", "-"))
        g(self.clone, "worktree", "add", "-q", "--detach", str(wt), base)
        self.commit(wt, name, text, f"{branch}: {name}")
        g(wt, "push", "-q", "origin", f"HEAD:refs/heads/{branch}")
        g(self.clone, "worktree", "remove", "--force", str(wt))
        g(self.clone, "fetch", "-q", "origin")

    def main_moves_on(self, name: str, text: str) -> None:
        wt = self.tmp / "wt-main"
        g(self.clone, "worktree", "add", "-q", "--detach", str(wt), "origin/main")
        self.commit(wt, name, text, f"main: {name}")
        g(wt, "push", "-q", "origin", "HEAD:refs/heads/main")
        g(self.clone, "worktree", "remove", "--force", str(wt))
        g(self.clone, "fetch", "-q", "origin")

    def new_day(self, branch: str) -> tuple[Path, list[str]]:
        """Start `branch` as cmd_daily_commit does for a new day: worktree from new_day_base, then bring in."""
        base = T.new_day_base(branch, cwd=self.clone)
        wt = self.tmp / ("new-" + branch.replace("/", "-"))
        g(self.clone, "worktree", "add", "-q", "-b", branch, str(wt), base)
        return wt, T.bring_in_earlier_days(wt, branch, cwd=self.clone)

    def test_no_earlier_day_starts_from_main(self):
        self.assertEqual(T.earlier_unmerged_daily(DAY2, cwd=self.clone), [])
        self.assertEqual(T.new_day_base(DAY2, cwd=self.clone), "origin/main")

    def test_unmerged_earlier_day_is_the_base(self):
        self.save_day(DAY1, "origin/main", "day1.txt", "one\n")
        self.assertEqual(T.earlier_unmerged_daily(DAY2, cwd=self.clone), [f"origin/{DAY1}"])
        self.assertEqual(T.new_day_base(DAY2, cwd=self.clone), f"origin/{DAY1}")
        wt, notes = self.new_day(DAY2)
        self.assertTrue((wt / "day1.txt").is_file())
        self.assertEqual(notes, [])      # nothing left to bring in: the branch already holds it

    def test_two_unmerged_days_stacked(self):
        self.save_day(DAY1, "origin/main", "day1.txt", "one\n")
        self.save_day(DAY2, f"origin/{DAY1}", "day2.txt", "two\n")
        self.assertEqual(T.new_day_base(DAY3, cwd=self.clone), f"origin/{DAY2}")
        wt, notes = self.new_day(DAY3)
        self.assertTrue((wt / "day1.txt").is_file() and (wt / "day2.txt").is_file())
        self.assertEqual(notes, [])

    def test_a_later_day_is_not_an_earlier_one(self):
        self.save_day(DAY3, "origin/main", "day3.txt", "three\n")
        self.assertEqual(T.earlier_unmerged_daily(DAY2, cwd=self.clone), [])

    def test_merged_day_is_not_brought_in(self):
        self.save_day(DAY1, "origin/main", "day1.txt", "one\n")
        g(self.clone, "push", "-q", "origin", f"origin/{DAY1}:refs/heads/main")     # the day's merge
        g(self.clone, "fetch", "-q", "origin")
        self.assertEqual(T.earlier_unmerged_daily(DAY2, cwd=self.clone), [])
        self.assertEqual(T.new_day_base(DAY2, cwd=self.clone), "origin/main")

    def test_earlier_day_behind_main_is_merged_in(self):
        """A late save on a day branch that main has moved past: the new day starts from main and merges it."""
        self.save_day(DAY1, "origin/main", "day1.txt", "one\n")
        self.main_moves_on("main2.txt", "main\n")
        self.assertEqual(T.new_day_base(DAY2, cwd=self.clone), "origin/main")
        wt, notes = self.new_day(DAY2)
        self.assertTrue((wt / "day1.txt").is_file() and (wt / "main2.txt").is_file())
        self.assertEqual(len(notes), 1)
        self.assertIn(f"starts with the unmerged work of origin/{DAY1}", notes[0])
        self.assertEqual(g(wt, "status", "--porcelain"), "")
        g(wt, "merge-base", "--is-ancestor", f"origin/{DAY1}", "HEAD")              # raises if it is not

    def test_conflicting_earlier_day_is_left_out_and_reported(self):
        self.save_day(DAY1, "origin/main", "base.txt", "the day's edit\n")
        self.main_moves_on("base.txt", "main's edit\n")
        wt, notes = self.new_day(DAY2)
        self.assertEqual(len(notes), 1)
        self.assertTrue(notes[0].startswith("WARNING"), notes[0])
        self.assertEqual((wt / "base.txt").read_text(encoding="utf-8"), "main's edit\n")
        self.assertEqual(g(wt, "status", "--porcelain"), "")
        self.assertEqual(g(wt, "rev-parse", "HEAD"), g(self.clone, "rev-parse", "origin/main"))


@unittest.skipUnless(shutil.which("git"), "git is not on PATH")
class SameDayAfterAMerge(NewDay):
    """Bob, 2026-11-11 ("fix track.py now"): a day's branch that exists is brought level with origin/main before a
    save builds on it (bring_in_main). That day a morning merge was followed by afternoon saves on the same branch,
    and the evening merge conflicted."""

    def existing_day(self, branch: str) -> tuple[Path, list[str]]:
        """Open the existing day branch as cmd_daily_commit does, then bring main in."""
        wt = self.tmp / ("again-" + branch.replace("/", "-"))
        g(self.clone, "worktree", "add", "-q", "-b", branch, str(wt), f"origin/{branch}")
        return wt, T.bring_in_main(wt, branch)

    def merge_day(self, branch: str) -> None:
        """The day's pull request: a merge commit on main, as GitHub makes it."""
        wt = self.tmp / "wt-merge"
        g(self.clone, "worktree", "add", "-q", "--detach", str(wt), "origin/main")
        g(wt, "merge", "-q", "--no-ff", "-m", f"Merge {branch}", f"origin/{branch}")
        g(wt, "push", "-q", "origin", "HEAD:refs/heads/main")
        g(self.clone, "worktree", "remove", "--force", str(wt))
        g(self.clone, "fetch", "-q", "origin")

    def test_branch_level_with_main_is_left_alone(self):
        self.save_day(DAY1, "origin/main", "day1.txt", "one\n")
        wt, notes = self.existing_day(DAY1)
        self.assertEqual(notes, [])
        self.assertEqual(g(wt, "rev-parse", "HEAD"), g(self.clone, "rev-parse", f"origin/{DAY1}"))

    def test_merged_day_branch_moves_forward_to_main(self):
        """The fault of 2026-11-11: main holds an earlier day's files the merged day branch never had."""
        self.save_day(DAY1, "origin/main", "day1.txt", "one\n")
        self.save_day(DAY2, "origin/main", "day2.txt", "two\n")       # started without day 1 (the earlier fault)
        self.merge_day(DAY1)
        self.merge_day(DAY2)
        wt, notes = self.existing_day(DAY2)
        self.assertEqual(len(notes), 1)
        self.assertIn("already merged", notes[0])
        self.assertEqual(g(wt, "rev-parse", "HEAD"), g(self.clone, "rev-parse", "origin/main"))
        self.assertTrue((wt / "day1.txt").is_file() and (wt / "day2.txt").is_file())
        # an afternoon save that edits a day 1 file, then the evening merge: no conflict
        self.commit(wt, "day1.txt", "one, edited in the afternoon\n", "afternoon save")
        g(wt, "push", "-q", "origin", f"HEAD:refs/heads/{DAY2}")       # a fast-forward of the day's branch
        g(self.clone, "fetch", "-q", "origin")
        self.merge_day(DAY2)
        self.assertEqual(g(self.clone, "show", "origin/main:day1.txt"), "one, edited in the afternoon")

    def test_unmerged_day_branch_gets_a_merge_of_main(self):
        self.save_day(DAY1, "origin/main", "day1.txt", "one\n")
        self.main_moves_on("main2.txt", "main\n")
        wt, notes = self.existing_day(DAY1)
        self.assertEqual(len(notes), 1)
        self.assertIn("now holds", notes[0])
        self.assertTrue((wt / "day1.txt").is_file() and (wt / "main2.txt").is_file())
        g(wt, "merge-base", "--is-ancestor", "origin/main", "HEAD")                 # raises if it is not
        g(wt, "merge-base", "--is-ancestor", f"origin/{DAY1}", "HEAD")              # nothing reset or rebased
        self.assertEqual(g(wt, "status", "--porcelain"), "")

    def test_conflict_with_main_is_undone_and_reported(self):
        self.save_day(DAY1, "origin/main", "base.txt", "the day's edit\n")
        self.main_moves_on("base.txt", "main's edit\n")
        wt, notes = self.existing_day(DAY1)
        self.assertEqual(len(notes), 1)
        self.assertTrue(notes[0].startswith("WARNING"), notes[0])
        self.assertEqual((wt / "base.txt").read_text(encoding="utf-8"), "the day's edit\n")
        self.assertEqual(g(wt, "status", "--porcelain"), "")
        self.assertEqual(g(wt, "rev-parse", "HEAD"), g(self.clone, "rev-parse", f"origin/{DAY1}"))


if __name__ == "__main__":
    unittest.main()
