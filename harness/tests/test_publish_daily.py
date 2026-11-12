"""Tests for publish_site.py's daily-branch publish (Bob, chat, 2026-11-09: "change publish_site.py to push to a daily
branch in the site repo. Then your merge is the publish, which settles the trigger question with no special
exception. It also needs to stop using git add -A.").

- daily_ref / push_refspec: only refs/heads/daily/<date>, never main, never forced; a bad date refuses.
- publish_branch on a fake site repo (a bare origin and the site clone, under <project>/_work/): the commit goes to
  origin's daily/<date> only; origin's main and the site checkout (HEAD and files) are unchanged; removals and
  additions are recorded; KEEP files are carried; the worktree is removed; no `git add -A` is run.
- stage_explicit: stages exactly the named paths (git rm for removals); a stray file stays untracked.
- saved_on: the filed folders must be byte for byte on origin/daily/<date> or origin/main (git mocked).

The commits and pushes go only to scratch repos under <project>/_work/; no real site checkout, design repo or remote
is touched. Needs a project (the scratch folder is the project's _work/); skipped in the harness master.

    .\\harness\\tools\\venv\\Scripts\\python.exe -m unittest harness.tests.test_publish_daily -v
"""
from __future__ import annotations

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
sys.path.insert(0, str(REPO / "harness" / "lib"))
sys.path.insert(0, str(REPO / "harness" / "scripts"))
import repo_paths as rp  # noqa: E402
if not rp.HAS_PROJECT:
    raise unittest.SkipTest("no project yet (the publish tests work in the project's _work/)")

import publish_site as PS  # noqa: E402

ID = ["-c", "user.name=Test", "-c", "user.email=test@example.invalid", "-c", "commit.gpgsign=false"]
DATE = "2026-11-10"


def g(cwd: Path, *args: str) -> str:
    r = subprocess.run(["git", *ID, *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8")
    if r.returncode:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr}")
    return r.stdout.strip()


def quiet(fn, *a, **k):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return fn(*a, **k)


class Refs(unittest.TestCase):
    def test_daily_only(self):
        self.assertEqual(PS.daily_ref(DATE), f"refs/heads/daily/{DATE}")
        spec = PS.push_refspec(DATE)
        self.assertEqual(spec, f"HEAD:refs/heads/daily/{DATE}")
        self.assertFalse(spec.startswith("+"))
        self.assertNotIn("main", spec)

    def test_bad_date_refused(self):
        for bad in ("main", "2026-13-01", "", "../main"):
            with self.assertRaises(SystemExit):
                quiet(PS.daily_ref, bad)


class Scratch(unittest.TestCase):
    def setUp(self):
        rp.WORK.mkdir(parents=True, exist_ok=True)
        self._tmp = tempfile.TemporaryDirectory(dir=rp.WORK, prefix="test-publish-daily-")
        self.root = Path(self._tmp.name)
        # a real site repo sets user.name in its own config; the scratch repos get it from the environment
        env = mock.patch.dict(os.environ, {"GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "test@example.invalid",
                                           "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "test@example.invalid"})
        env.start()
        self.addCleanup(env.stop)

    def tearDown(self):
        self._tmp.cleanup()


class StageExplicit(Scratch):
    def test_only_named_paths(self):
        repo = self.root / "r"
        g(self.root, "init", "-q", "--initial-branch=main", str(repo))
        (repo / "keep.txt").write_text("k\n", encoding="utf-8")
        (repo / "gone.txt").write_text("g\n", encoding="utf-8")
        g(repo, "add", "keep.txt", "gone.txt")
        g(repo, "commit", "-q", "-m", "base")
        (repo / "gone.txt").unlink()
        (repo / "new.txt").write_text("n\n", encoding="utf-8")
        (repo / "stray.txt").write_text("s\n", encoding="utf-8")
        PS.stage_explicit(repo, ["new.txt"], ["gone.txt"], self.root / "spec")
        status = g(repo, "status", "--porcelain").splitlines()
        self.assertIn("A  new.txt", status)
        self.assertIn("D  gone.txt", status)
        self.assertIn("?? stray.txt", status)   # not named, so not staged


class PublishBranch(Scratch):
    """origin.git (bare) with one "Site:" publish on main; site/ is the checkout publish_site.py reads but never writes."""

    def setUp(self):
        super().setUp()
        self.origin, self.site = self.root / "origin.git", self.root / "site"
        g(self.root, "init", "--bare", "-q", "--initial-branch=main", str(self.origin))
        g(self.root, "clone", "-q", str(self.origin), str(self.site))
        for k, v in {"README.md": "# site\n", "index.html": "<p>old landing</p>\n", "old.html": "<p>old</p>\n",
                     ".github/workflows/package.yml": "name: x\n"}.items():
            p = self.site / k
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(v, encoding="utf-8")
        g(self.site, "add", "README.md", "index.html", "old.html", ".github/workflows/package.yml")
        g(self.site, "commit", "-q", "-m", "Site: first publish")
        g(self.site, "push", "-q", "origin", "main")
        self.main_before = g(self.origin, "rev-parse", "refs/heads/main")
        self.site_head = g(self.site, "rev-parse", "HEAD")
        filed = self.root / "filed"
        filed.mkdir()
        (filed / "index.html").write_text("<p>new landing</p>\n", encoding="utf-8")
        (filed / "new.html").write_text("<p>new page</p>\n", encoding="utf-8")
        self.plan = {"index.html": filed / "index.html", "tracker/new.html": filed / "new.html"}
        self.git_calls: list[tuple] = []
        self.remote_calls: list[tuple] = []
        real_git = PS.git

        def spy_git(*args, cwd, check=True):
            self.git_calls.append(args)
            return real_git(*args, cwd=cwd, check=check)

        def plain_remote(*args, cwd=None, write=False):   # a local bare origin needs no gh credential
            self.remote_calls.append(args)
            return g(cwd, *args)

        for p in (mock.patch.object(PS, "git", side_effect=spy_git),
                  mock.patch.object(PS.T, "git_remote", side_effect=plain_remote)):
            p.start()
            self.addCleanup(p.stop)

    def run_publish(self):
        g(self.site, "fetch", "-q", "origin")
        return quiet(PS.publish_branch, self.site, "origin/main", DATE, self.plan, ["old.html"],
                     ["index.html", "tracker/new.html"], {"README.md": b"# site v2\n", PS.NOTES_FILE: b"{}\n"},
                     "Site: test publish\n", self.root / "scratch")

    def test_pushes_daily_only_and_leaves_main_and_checkout(self):
        local, remote = self.run_publish()
        self.assertEqual(local, remote)
        self.assertEqual(g(self.origin, "rev-parse", f"refs/heads/daily/{DATE}"), local)
        self.assertEqual(g(self.origin, "rev-parse", "refs/heads/main"), self.main_before)   # main untouched
        self.assertEqual(g(self.site, "rev-parse", "HEAD"), self.site_head)                 # checkout not moved
        self.assertEqual(g(self.site, "branch", "--show-current"), "main")
        self.assertEqual((self.site / "index.html").read_text(encoding="utf-8"), "<p>old landing</p>\n")
        self.assertEqual(g(self.site, "status", "--porcelain"), "")
        tree = set(g(self.origin, "ls-tree", "-r", "--name-only", f"refs/heads/daily/{DATE}").splitlines())
        self.assertEqual(tree, {"README.md", "index.html", "tracker/new.html", PS.NOTES_FILE,
                                ".github/workflows/package.yml"})              # old.html removed, KEEP carried
        self.assertEqual(g(self.origin, "show", f"refs/heads/daily/{DATE}:index.html"), "<p>new landing</p>")
        self.assertFalse((self.root / f"site-daily-{DATE}").exists())          # worktree removed
        self.assertEqual(len(g(self.site, "worktree", "list").splitlines()), 1)
        pushes = [c for c in self.remote_calls if c[0] == "push"]
        self.assertEqual(pushes, [("push", "origin", f"HEAD:refs/heads/daily/{DATE}")])
        self.assertFalse(any("-A" in c or "--all" in c for c in self.git_calls if c[0] == "add"))
        self.assertTrue(any(c[0] == "rm" for c in self.git_calls))

    def test_second_publish_same_day_builds_on_the_branch(self):
        first, _ = self.run_publish()
        g(self.site, "fetch", "-q", "origin", f"refs/heads/daily/{DATE}:refs/remotes/origin/daily/{DATE}")
        base = quiet(PS.publish_base, self.site, DATE, True)
        self.assertEqual(base, f"origin/daily/{DATE}")
        (self.root / "filed" / "new.html").write_text("<p>new page v2</p>\n", encoding="utf-8")
        second, remote = quiet(PS.publish_branch, self.site, base, DATE, self.plan, [], ["tracker/new.html"],
                               {"README.md": b"# site v3\n"}, "Site: second publish\n", self.root / "scratch")
        self.assertEqual(g(self.origin, "rev-parse", f"{second}^"), first)   # a plain fast-forward push
        self.assertEqual(g(self.origin, "rev-parse", "refs/heads/main"), self.main_before)

    def merge_on_github(self, squash: bool = False) -> None:
        """Stand-in for the end-of-day merge of daily/<date> into main on GitHub (merge commit, or squash)."""
        other = self.root / "merger"
        g(self.root, "clone", "-q", str(self.origin), str(other))
        g(other, "fetch", "-q", "origin", f"refs/heads/daily/{DATE}:refs/remotes/origin/daily/{DATE}")
        if squash:
            g(other, "merge", "--squash", "-q", f"origin/daily/{DATE}")
            g(other, "commit", "-q", "-m", "Site: test publish (#7)")
        else:
            g(other, "merge", "--no-ff", "-q", "-m", f"Merge pull request #7 from site-owner/daily/{DATE}",
              f"origin/daily/{DATE}")
        g(other, "push", "-q", "origin", "main")

    def second_base(self) -> str:
        g(self.site, "fetch", "-q", "origin")
        return PS.publish_base(self.site, DATE, quiet(PS.fetch_site_daily, self.site, DATE))

    def test_second_publish_after_merge_commit_builds_on_main(self):
        first, _ = self.run_publish()
        self.merge_on_github()
        base = quiet(self.second_base)
        self.assertEqual(base, "origin/main")
        (self.root / "filed" / "new.html").write_text("<p>new page v2</p>\n", encoding="utf-8")
        second, remote = quiet(PS.publish_branch, self.site, base, DATE, self.plan, [], ["tracker/new.html"],
                               {"README.md": b"# site v3\n"}, "Site: second publish\n", self.root / "scratch")
        self.assertEqual(second, remote)
        merged_main = g(self.origin, "rev-parse", "refs/heads/main")
        self.assertEqual(g(self.origin, "rev-parse", f"{second}^"), merged_main)   # built on main
        g(self.origin, "merge-base", "--is-ancestor", first, second)                # so the push fast-forwarded
        self.assertEqual(g(self.origin, "rev-parse", "refs/heads/main"), merged_main)   # main untouched by the push

    def test_second_publish_after_squash_merge_refuses(self):
        self.run_publish()
        self.merge_on_github(squash=True)
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
            self.second_base()
        self.assertIn("diverged", err.getvalue())
        self.assertIn("squash or rebase merge", err.getvalue())

    def test_leftover_worktree_folder_refuses(self):
        (self.root / f"site-daily-{DATE}").mkdir()
        with self.assertRaises(SystemExit):
            self.run_publish()
        self.assertFalse([c for c in self.remote_calls if c[0] == "push"])


class SavedOn(unittest.TestCase):
    """The rule: every file under the published filed folders is byte for byte on origin/daily/<date> or origin/main."""

    def run_with(self, disk: dict[str, str], refs: dict[str, dict[str, str]]):
        with mock.patch.object(PS, "disk_files", return_value=sorted(disk)), \
                mock.patch.object(PS, "disk_blobs", return_value=disk), \
                mock.patch.object(PS, "blobs_at", side_effect=lambda ref, folders: refs.get(ref, {})), \
                mock.patch.object(PS, "git", side_effect=lambda *a, cwd, check=True:
                                  "x" if a[0] == "rev-parse" and a[-1] in refs else ""):
            return PS.saved_on(["Portals/p/p-revA"], [f"origin/daily/{DATE}", "origin/main"])

    def test_on_daily(self):
        disk = {"a": "1", "b": "2"}
        self.assertEqual(self.run_with(disk, {f"origin/daily/{DATE}": dict(disk), "origin/main": {}})[0],
                         f"origin/daily/{DATE}")

    def test_on_main_when_no_daily(self):
        disk = {"a": "1"}
        self.assertEqual(self.run_with(disk, {"origin/main": dict(disk)})[0], "origin/main")

    def test_different_or_missing_refused(self):
        disk = {"a": "1", "b": "2"}
        ref, why = self.run_with(disk, {f"origin/daily/{DATE}": {"a": "1", "b": "9"}, "origin/main": {"a": "1"}})
        self.assertIsNone(ref)
        self.assertIn("1 different", why)
        self.assertIn("1 not saved", why)

    def test_extra_file_on_ref_refused(self):
        ref, _ = self.run_with({"a": "1"}, {"origin/main": {"a": "1", "z": "3"}})
        self.assertIsNone(ref)


if __name__ == "__main__":
    unittest.main()
