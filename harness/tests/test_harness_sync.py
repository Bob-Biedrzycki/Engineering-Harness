"""harness_sync.py: check / pull / seed between a job repo and the master copy, on scratch folders only.

    .\\harness\\tools\\venv\\Scripts\\python.exe -m unittest harness.tests.test_harness_sync -v
"""
from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

REPO = next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists())
sys.path.insert(0, str(REPO / "harness" / "scripts"))
sys.path.insert(0, str(REPO / "harness" / "lib"))
import harness_sync as HS  # noqa: E402
import drive_rules  # noqa: E402

MANIFEST = (REPO / HS.MANIFEST_REL).read_text(encoding="utf-8")
BLOCK = [drive_rules.BLOCK_BEGIN, "/job/*/04_Vendor_Data/**/*.pdf", drive_rules.BLOCK_END]


def make_repo(root: Path, extra: dict[str, str] | None = None, block: bool = True) -> Path:
    files = {
        "CLAUDE.md": "# rules for every job\n",
        HS.MANIFEST_REL: MANIFEST,
        "harness/lib/a.py": "A = 1\n",
        "harness/scripts/b.py": "B = 2\n",
        "harness/tools/venv/junk.txt": "venv, never synced\n",
        "harness/lib/__pycache__/a.cpython.pyc": "cache\n",
        ".claude/agents/x.md": "agent\n",
        ".claude/launch.json": "{}\n",                      # job-owned
        "job/JOB.md": "# this job\n",                       # job-owned
        "README.md": "job readme\n",                        # job-owned
        ".gitignore": "harness/tools/\n__pycache__/\n" + ("\n" + "\n".join(BLOCK) + "\n" if block else ""),
    }
    files.update(extra or {})
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return root


def run(*argv) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        rc = HS.main(list(map(str, argv)))
    return rc, out.getvalue()


class Manifest(unittest.TestCase):
    def test_ownership(self):
        m = HS.parse_manifest(MANIFEST)
        for rel in ("harness/lib/repo_paths.py", "harness/harness-manifest.txt", ".claude/agents/a.md",
                    ".claude/skills/s/SKILL.md", ".claude/settings.json", "CLAUDE.md", ".github/workflows/c.yml",
                    ".gitattributes"):
            self.assertTrue(HS.owned(rel, m), rel)
        for rel in ("job/JOB.md", "README.md", "Agent-to-Agent Questions.md", "Agent-to-Bob Questions.md",
                    ".claude/launch.json", ".claude/settings.local.json", "harness/tools/venv/x.py",
                    "harness/lib/__pycache__/a.pyc", ".gitignore"):
            self.assertFalse(HS.owned(rel, m), rel)
        self.assertEqual(m.core, [".gitignore"])

    def test_walk_skips_excluded(self):
        with tempfile.TemporaryDirectory() as d:
            root = make_repo(Path(d))
            files = set(HS.owned_files(root, HS.parse_manifest(MANIFEST)))
        self.assertEqual(files, {"CLAUDE.md", HS.MANIFEST_REL, "harness/lib/a.py", "harness/scripts/b.py",
                                 ".claude/agents/x.md"})


class Commands(unittest.TestCase):
    def setUp(self):
        self._d = tempfile.TemporaryDirectory()
        self.d = Path(self._d.name)
        self.job = make_repo(self.d / "job-repo")
        self.master = self.d / "master"

    def tearDown(self):
        self._d.cleanup()

    def test_seed_then_check_identical(self):
        rc, out = run("seed", "--master", self.master, "--job", self.job)
        self.assertEqual(rc, 1, out)
        self.assertTrue((self.master / "harness/lib/a.py").is_file())
        self.assertFalse((self.master / "job").exists())                         # job-owned: not seeded
        self.assertFalse((self.master / "harness/tools").exists())
        self.assertNotIn(drive_rules.BLOCK_BEGIN, (self.master / ".gitignore").read_text(encoding="utf-8"))
        self.assertEqual(run("seed", "--master", self.master, "--job", self.job)[0], 0)
        rc, out = run("check", self.job, "--master", self.master)
        self.assertEqual(rc, 0, out)
        self.assertIn("IDENTICAL", out)

    def test_seed_refuses_a_differing_master_unless_forced(self):
        run("seed", "--master", self.master, "--job", self.job)
        (self.master / "harness/lib/a.py").write_text("A = 'master fix'\n", encoding="utf-8")
        rc, out = run("seed", "--master", self.master, "--job", self.job)
        self.assertEqual(rc, 2, out)
        self.assertIn("harness/lib/a.py", out)
        self.assertEqual((self.master / "harness/lib/a.py").read_text(encoding="utf-8"), "A = 'master fix'\n")
        self.assertEqual(run("seed", "--master", self.master, "--job", self.job, "--force")[0], 1)
        self.assertEqual((self.master / "harness/lib/a.py").read_text(encoding="utf-8"), "A = 1\n")

    def test_check_lists_added_changed_missing(self):
        run("seed", "--master", self.master, "--job", self.job)
        (self.master / "harness/lib/new.py").write_text("N = 1\n", encoding="utf-8")       # added
        (self.master / "harness/lib/a.py").write_text("A = 2\n", encoding="utf-8")         # changed
        (self.job / "harness/lib/local.py").write_text("L = 1\n", encoding="utf-8")        # missing (job only)
        (self.job / "job/JOB.md").write_text("# changed job file\n", encoding="utf-8")     # job-owned: ignored
        rc, out = run("check", self.job, "--master", self.master)
        self.assertEqual(rc, 1, out)
        self.assertRegex(out, r"added\s+harness/lib/new.py")
        self.assertRegex(out, r"changed\s+harness/lib/a.py")
        self.assertRegex(out, r"missing\s+harness/lib/local.py")
        self.assertNotIn("JOB.md", out)

    def test_pull_copies_harness_and_keeps_job_files_and_block(self):
        run("seed", "--master", self.master, "--job", self.job)
        (self.master / "harness/lib/a.py").write_text("A = 'fixed'\n", encoding="utf-8")
        (self.master / ".gitignore").write_text("harness/tools/\n__pycache__/\n*.tmp\n", encoding="utf-8")
        (self.job / "harness/lib/local.py").write_text("L = 1\n", encoding="utf-8")
        rc, out = run("pull", self.job, "--master", self.master)
        self.assertEqual(rc, 1, out)
        self.assertEqual((self.job / "harness/lib/a.py").read_text(encoding="utf-8"), "A = 'fixed'\n")
        self.assertTrue((self.job / "harness/lib/local.py").is_file())              # job-only file left alone
        self.assertEqual((self.job / "job/JOB.md").read_text(encoding="utf-8"), "# this job\n")
        gi = (self.job / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn("*.tmp", gi)                                                   # master core pulled
        self.assertIn(drive_rules.BLOCK_BEGIN, gi)                                   # job's own block kept
        self.assertIn("/job/*/04_Vendor_Data/**/*.pdf", gi)
        rc, out = run("check", self.job, "--master", self.master)
        self.assertEqual(rc, 1)                                                      # only the job-only file
        self.assertNotRegex(out, r"(?m)^\s+(added|changed)\s")
        self.assertEqual(run("pull", self.job, "--master", self.master)[0], 1)

    def test_refusals(self):
        self.assertEqual(run("check", self.job, "--master", self.d / "nowhere")[0], 2)
        self.assertEqual(run("check", self.d / "nowhere", "--master", self.job)[0], 2)
        self.assertEqual(run("pull", self.job, "--master", self.job)[0], 2)
        self.assertEqual(run("seed", "--master", self.job, "--job", self.job)[0], 2)
        self.assertEqual(run("seed", "--master", self.d / "no" / "parent", "--job", self.job)[0], 2)

    def test_master_default_from_environment(self):
        import os
        from unittest import mock
        with mock.patch.dict(os.environ, {"CPME_HARNESS_MASTER": str(self.master)}):
            self.assertEqual(HS.default_master(), self.master)
        with mock.patch.dict(os.environ, {"CPME_HARNESS_MASTER": ""}):
            self.assertEqual(HS.default_master(), HS.DEFAULT_MASTER)


if __name__ == "__main__":
    unittest.main()
