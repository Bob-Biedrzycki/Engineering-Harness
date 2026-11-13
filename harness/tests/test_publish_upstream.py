"""Tests for publish_site.py and the site repo's own commits (upstream), and its packager run as a check.

- keep_path: .github/**, .gitattributes, README.md and the save tool's root .gitignore and drive-store.json are KEEP;
  published content is not.
- sync_site on a fake site repo (a bare origin, the site clone, and a second clone standing in for the site repo's
  owners):
    level                         -> "no upstream commits", nothing written
    behind, .github-only commits  -> listed KEEP-only, "based" (carried by the publish branch); checkout never moved
    behind, a content commit      -> dry run lists it TOUCHES PUBLISHED CONTENT; real run refuses, HEAD unchanged
    local commits only            -> no refusal (origin/main since the last publish is the reference)
    a merged daily/<date> branch  -> counts as the last publish; a content commit after it refuses
- checkout_refusal: an uncommitted change (dirty tree) and a wrong origin refuse.
- site_packaging with a stub packager: pass, fail (exit and text reported), missing script; stage_tree writes the plan
  plus README.md; reset_scratch refuses a folder outside <project>/_work/.
- closeout.site_packaging_lines carries the upstream and packager lines into the step result.

Every case works in a scratch folder under <project>/_work/ (gitignored); no real site checkout, remote or filed file
is read or written. Needs a project; skipped in the harness master.

    .\\harness\\tools\\venv\\Scripts\\python.exe -m unittest harness.tests.test_publish_upstream -v
"""
from __future__ import annotations

import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists())
sys.path.insert(0, str(REPO / "harness" / "lib"))
sys.path.insert(0, str(REPO / "harness" / "scripts"))
import repo_paths as rp  # noqa: E402
if not rp.HAS_PROJECT:
    raise unittest.SkipTest("no project yet (the publish tests work in the project's _work/)")

import publish_site as PS  # noqa: E402

ID = ["-c", "user.name=Test", "-c", "user.email=test@example.invalid", "-c", "commit.gpgsign=false"]


def g(cwd: Path, *args: str) -> str:
    r = subprocess.run(["git", *ID, *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8")
    if r.returncode:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr}")
    return r.stdout.strip()


def commit(repo: Path, files: dict[str, str], msg: str, push: bool = True) -> str:
    for k, v in files.items():
        p = repo / k
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(v, encoding="utf-8")
    g(repo, "add", "--", *files)
    g(repo, "commit", "-m", msg)
    if push:
        g(repo, "push", "origin", "main")
    return g(repo, "rev-parse", "HEAD")


def quiet(fn, *a, **k):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return fn(*a, **k)


class FakeSite(unittest.TestCase):
    """origin.git (bare), site/ (the checkout publish_site.py works in), owner/ (pushes upstream commits)."""

    def setUp(self):
        rp.WORK.mkdir(parents=True, exist_ok=True)
        self._tmp = tempfile.TemporaryDirectory(dir=rp.WORK, prefix="test-publish-upstream-")
        root = Path(self._tmp.name)
        self.origin, self.site, self.owner = root / "origin.git", root / "site", root / "owner"
        g(root, "init", "--bare", "--initial-branch=main", str(self.origin))
        g(root, "clone", str(self.origin), str(self.site))
        commit(self.site, {"README.md": "# site\n", "index.html": "<p>landing</p>\n",
                           ".github/workflows/package.yml": "name: x\n"}, "Site: first publish")
        g(root, "clone", str(self.origin), str(self.owner))

    def tearDown(self):
        self._tmp.cleanup()

    def head(self) -> str:
        return g(self.site, "rev-parse", "HEAD")


class KeepPath(unittest.TestCase):
    def test_keep_paths(self):
        for p in (".github/workflows/package.yml", ".github/packaging/package_portals.py", ".gitattributes", "README.md",
                  ".gitignore", "drive-store.json"):   # the last two: written by the global save tool (day.py)
            self.assertTrue(PS.keep_path(p), p)
        for p in ("index.html", "estimating/index.html", "data/glb/x.glb", "docs/README.md", ".git/config",
                  "tracker/drive-store.json", "data/.gitignore"):
            self.assertFalse(PS.keep_path(p), p)


class Sync(FakeSite):
    def test_level(self):
        before = self.head()
        lines, action = quiet(PS.sync_site, self.site, False)
        self.assertEqual(action, "level")
        self.assertIn("no upstream commits", lines[-1])
        self.assertEqual(self.head(), before)

    def test_behind_github_only_is_carried_not_fast_forwarded(self):
        """The publish branch is built on origin/main, so KEEP-only upstream commits are carried; the site checkout
        itself is never moved."""
        before = self.head()
        h = commit(self.owner, {".github/packaging/package_portals.py": "print('hi')\n"}, "Owner: packaging")
        for dry in (True, False):
            lines, action = quiet(PS.sync_site, self.site, dry)
            self.assertEqual(action, "based")
            self.assertTrue(any(h[:7] in ln and "KEEP-only" in ln and "Test" in ln and "Owner: packaging" in ln
                                for ln in lines), lines)
            self.assertEqual(self.head(), before)   # the checkout never moves

    def test_behind_content_commit_refuses(self):
        before = self.head()
        commit(self.owner, {".github/x.yml": "a\n"}, "Owner: keep")
        commit(self.owner, {"estimating/index.html": "<p>hand edit</p>\n"}, "Owner: content")
        lines, action = quiet(PS.sync_site, self.site, True)
        self.assertEqual(action, "refuse")
        self.assertTrue(any("TOUCHES PUBLISHED CONTENT (estimating/index.html)" in ln for ln in lines), lines)
        self.assertTrue(any("KEEP-only" in ln for ln in lines), lines)
        self.assertTrue(lines[-1].startswith("WARNING upstream: a real publish REFUSES"), lines)
        with self.assertRaises(SystemExit) as e:
            quiet(PS.sync_site, self.site, False)
        self.assertEqual(e.exception.code, 2)
        self.assertEqual(self.head(), before)

    def test_local_checkout_state_does_not_matter(self):
        """The reference is origin/main since the last publish, not the checkout's own main (which lags until synced
        after each merge). Local-only commits do not refuse; the checkout is left as it is."""
        before = commit(self.site, {"index.html": "<p>local</p>\n"}, "local commit not pushed", push=False)
        _, action = quiet(PS.sync_site, self.site, False)
        self.assertEqual(action, "level")
        self.assertEqual(self.head(), before)

    def test_merged_daily_publish_counts_as_the_last_publish(self):
        """The merge of a daily publish branch is a publish: its content files are not "upstream"; a content commit
        after it still refuses."""
        g(self.owner, "pull", "-q", "origin", "main")
        g(self.owner, "checkout", "-q", "-b", "daily/2026-11-10")
        commit(self.owner, {"estimating/index.html": "<p>Rev S</p>\n"}, "Site: quoting-portal Rev S", push=False)
        g(self.owner, "checkout", "-q", "main")
        g(self.owner, "merge", "--no-ff", "-q", "-m", "Merge pull request #5 from site-owner/daily/2026-11-10",
          "daily/2026-11-10")
        g(self.owner, "push", "-q", "origin", "main")
        _, action = quiet(PS.sync_site, self.site, False)
        self.assertEqual(action, "level")
        commit(self.owner, {"estimating/index.html": "<p>hand edit</p>\n"}, "Owner: content")
        with self.assertRaises(SystemExit):
            quiet(PS.sync_site, self.site, False)

    def test_is_publish(self):
        self.assertTrue(PS.is_publish("Site: project-portal Rev Z (model Rev A, P&ID Rev A)"))
        self.assertTrue(PS.is_publish("Merge pull request #12 from site-owner/daily/2026-11-10"))
        self.assertFalse(PS.is_publish("Merge pull request #13 from someone/packaging"))
        self.assertFalse(PS.is_publish("Owner: packaging"))

    def test_fetch_failure_warns_in_dry_run_and_refuses_for_real(self):
        g(self.site, "remote", "set-url", "origin", str(self.origin.parent / "no-such-origin.git"))
        lines, action = quiet(PS.sync_site, self.site, True)
        self.assertEqual(action, "unknown")
        self.assertTrue(lines[0].startswith("WARNING upstream: git fetch origin main failed"), lines)
        with self.assertRaises(SystemExit):
            quiet(PS.sync_site, self.site, False)


class Checkout(FakeSite):
    def test_clean_passes_and_dirty_refuses(self):
        slug = self.origin.name
        self.assertIsNone(PS.checkout_refusal(self.site, slug))
        (self.site / "index.html").write_text("<p>hand edit</p>\n", encoding="utf-8")
        why = PS.checkout_refusal(self.site, slug)
        self.assertIn("uncommitted changes", why or "")

    def test_wrong_origin_refuses(self):
        self.assertIn("not example-owner/", PS.checkout_refusal(self.site, "example-owner/example-site") or "")


STUB = """import argparse, pathlib, sys
ap = argparse.ArgumentParser(); ap.add_argument("--site"); ap.add_argument("--out"); a = ap.parse_args()
readme = pathlib.Path(a.site, "README.md")
if "quoting-portal **Rev R**" not in readme.read_text(encoding="utf-8"):
    print("package_portals: estimating: expected one 'quoting-portal **Rev X**' in README.md", file=sys.stderr)
    sys.exit(2)
pathlib.Path(a.out, "index.json").write_text("{}", encoding="utf-8")
print("packaged estimating Rev R: 1 files")
print("catalog: 1 project(s)")
"""


class Packager(unittest.TestCase):
    def setUp(self):
        rp.WORK.mkdir(parents=True, exist_ok=True)
        self._tmp = tempfile.TemporaryDirectory(dir=rp.WORK, prefix="test-publish-packager-")
        self.root = Path(self._tmp.name)
        self.script = self.root / "site" / PS.PACKAGER
        self.script.parent.mkdir(parents=True)
        self.script.write_text(STUB, encoding="utf-8")
        src = self.root / "filed" / "index.html"
        src.parent.mkdir(parents=True)
        src.write_text("<p>page</p>\n", encoding="utf-8")
        self.plan = {"estimating/index.html": src}

    def tearDown(self):
        self._tmp.cleanup()

    def run_with(self, readme: str) -> tuple[str, list[str]]:
        tree = PS.stage_tree(self.plan, {"README.md": readme.encode("utf-8")}, self.root / "stage")
        self.assertTrue((tree / "estimating/index.html").is_file())
        self.assertTrue((tree / "README.md").is_file())
        return PS.site_packaging(self.script, tree, self.root / "packages")

    def test_pass(self):
        status, lines = self.run_with("quoting-portal **Rev R**\n")
        self.assertEqual(status, "pass", lines)
        self.assertEqual(lines[0], "package_portals.py exit 0")
        self.assertIn("packaged estimating Rev R: 1 files", lines)
        self.assertTrue((self.root / "packages" / "index.json").is_file())

    def test_fail_reports_exit_and_text(self):
        status, lines = self.run_with("no revision line\n")
        self.assertEqual(status, "fail")
        self.assertEqual(lines[0], "package_portals.py exit 2")
        self.assertTrue(any("expected one 'quoting-portal **Rev X**'" in ln for ln in lines), lines)

    def test_missing_script(self):
        status, lines = PS.site_packaging(self.root / "nowhere" / "package_portals.py", self.root, self.root / "packages")
        self.assertEqual(status, "missing")
        self.assertIn("not in the site repo", lines[0])

    def test_restage_replaces_the_old_tree(self):
        tree = PS.stage_tree(self.plan, {"README.md": b"x"}, self.root / "stage")
        (tree / "stale.html").write_text("old", encoding="utf-8")
        tree = PS.stage_tree(self.plan, {"README.md": b"x"}, self.root / "stage")
        self.assertFalse((tree / "stale.html").exists())

    def test_scratch_outside_project_work_refused(self):
        with self.assertRaises(SystemExit):
            quiet(PS.reset_scratch, rp.REPO / "not-work-scratch")
        self.assertFalse((rp.REPO / "not-work-scratch").exists())


class CloseoutLines(unittest.TestCase):
    """closeout.py step 9 carries the dry run's upstream and packager lines into the step result (and so the go)."""

    def test_lines_picked(self):
        import closeout as C
        out = "\n".join([
            "publish_site (DRY RUN: nothing written, committed or pushed)",
            "  site:    C:\\site on main, clean",
            "  upstream: origin/main has 1 commit(s) since the last publish:",
            "            23ec616 site-owner 2026-10-22 \"cover customer page\": KEEP-only (.github/packaging/package_portals.py)",
            "  upstream: origin/main has 1 commit(s) since the last publish, each touching only KEEP paths",
            "  layout:  index.html",
            "  WARNING site packaging: fail: package_portals.py exit 2 (python -I ...)",
            "           package_portals.py exit 2",
        ])
        got = C.site_packaging_lines(out)
        self.assertEqual(len(got), 4, got)
        self.assertTrue(got[1].startswith("23ec616 site-owner"))
        self.assertTrue(got[3].startswith("WARNING site packaging: fail"))
        self.assertEqual(C.site_packaging_lines("  upstream: no upstream commits (x)\n  site packaging: pass: y"),
                         ["upstream: no upstream commits (x)", "site packaging: pass: y"])


if __name__ == "__main__":
    unittest.main()
