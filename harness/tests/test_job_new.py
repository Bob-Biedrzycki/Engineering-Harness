"""job_new.py and the no-project mode, end to end on scratch folders (never the real master).

A scratch master is seeded from this repo (harness_sync.py seed), a new job is made from it (job_new.py), and in that
job, which has no project yet:
  * repo_paths imports, PROJECT is None, PROJECT_INFO is {}, a project name raises NoProjectError when used;
  * every harness/checks/*.py exits 0 and says "no project yet";
  * the scripts that need a project refuse with exit 2 and a plain message.
Then --project makes a first project and the checks run on it.

    .\\harness\\tools\\venv\\Scripts\\python.exe -m unittest harness.tests.test_job_new -v
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
sys.path.insert(0, str(REPO / "harness" / "scripts"))
sys.path.insert(0, str(REPO / "harness" / "lib"))
import harness_sync as HS  # noqa: E402
import job_new as JN  # noqa: E402
import carryover_terms as CT  # noqa: E402

PY = sys.executable
CHECKS = sorted(p.name for p in (REPO / "harness" / "checks").glob("*.py"))
NEEDS_PROJECT = (("closeout.py", "--dry-run"), ("model_iterate.py",), ("model_file.py",), ("model_accept.py",),
                 ("publish_site.py", "--dry-run"))


def quiet(fn, *a, **k):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        rc = fn(*a, **k)
    return rc, out.getvalue()


def py(root: Path, *args, env=None) -> subprocess.CompletedProcess:
    return subprocess.run([PY, *map(str, args)], cwd=root, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=300, env=env)


class NewJob(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._d = tempfile.TemporaryDirectory()
        d = Path(cls._d.name)
        cls.master = d / "master"
        rc, out = quiet(HS.main, ["seed", "--master", str(cls.master), "--job", str(REPO)])
        assert rc in (0, 1), out
        cls.job = d / "Widget-Skids"
        cls.rc, cls.out = quiet(JN.main, [str(cls.job), "--name", "Widget Skids", "--repo", "cpme-test/Widget-Skids",
                                          "--master", str(cls.master)])
        import os
        cls.env = {k: v for k, v in os.environ.items() if k not in ("CPME_PROJECT", "CPME_DRAWINGS_ROOT")}

    @classmethod
    def tearDownClass(cls):
        cls._d.cleanup()

    def test_created(self):
        self.assertIn(self.rc, (0, 1), self.out)          # 1 = created, with carry-over hits listed as warnings
        for rel in ("CLAUDE.md", "harness/lib/repo_paths.py", HS.MANIFEST_REL, "job/JOB.md", "job/drive-store.yaml",
                    "job/carryover-terms.txt", "job/components/component-register.csv", "job/design-rules/README.md",
                    "job/knowledge/README.md", "Agent-to-Agent Questions.md", "Agent-to-Bob Questions.md",
                    "README.md", ".gitignore"):
            self.assertTrue((self.job / rel).is_file(), rel)
        self.assertFalse(any((self.job / "job").glob("Project-*")))
        self.assertFalse((self.job / "harness" / "tools").exists())
        job_md = (self.job / "job" / "JOB.md").read_text(encoding="utf-8")
        self.assertIn("# This job: Widget Skids", job_md)
        self.assertIn("https://github.com/cpme-test/Widget-Skids.git", job_md)
        self.assertIn("none yet", job_md)
        q = (self.job / "Agent-to-Agent Questions.md").read_text(encoding="utf-8")
        self.assertTrue(q.startswith("# Agent-to-Agent Questions (Widget Skids job)"))
        self.assertNotIn("### Q-0", q.split("## Entries")[-1])           # rules header kept, no entries
        gi = (self.job / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("drive-store", gi)                                  # block written by drive_store.py pointers

    def test_drive_store_unknown_with_this_jobs_rules(self):
        import yaml
        new = yaml.safe_load((self.job / "job" / "drive-store.yaml").read_text(encoding="utf-8"))
        old = yaml.safe_load((REPO / "job" / "drive-store.yaml").read_text(encoding="utf-8"))
        self.assertEqual((new["drive_folder_url"], new["drive_folder_id"], new["rclone_remote"]),
                         ("unknown", "unknown", "unknown"))
        self.assertEqual(new["directories"], old["directories"])
        self.assertEqual(new["exclude"], old["exclude"])
        self.assertEqual(new["large_file_bytes"], old["large_file_bytes"])

    def test_carryover_terms_carry_banned_and_this_job(self):
        src = CT.load(REPO / "job" / "carryover-terms.txt")
        new = CT.load(self.job / "job" / "carryover-terms.txt")
        self.assertEqual(new["banned"].patterns, src["banned"].patterns + src["this-job"].patterns)
        self.assertEqual(new["banned-here"].patterns, [])
        self.assertEqual(new["this-job"].patterns, [])

    def test_refuses_non_empty_target_and_bad_arguments(self):
        rc, _ = quiet(JN.main, [str(self.job), "--name", "X", "--repo", "a/b", "--master", str(self.master)])
        self.assertEqual(rc, 2)
        with tempfile.TemporaryDirectory() as d:
            t = str(Path(d) / "j")
            self.assertEqual(quiet(JN.main, [t, "--name", "X", "--repo", "not a repo", "--master", str(self.master)])[0], 2)
            self.assertEqual(quiet(JN.main, [t, "--name", "X", "--repo", "a/b", "--master", d])[0], 2)   # no harness
            self.assertEqual(quiet(JN.main, [t, "--name", "X", "--repo", "a/b", "--master", str(self.master),
                                             "--project", "P-1"])[0], 2)
            self.assertFalse(Path(t).exists())

    def test_repo_paths_with_no_project(self):
        code = ("import sys; sys.path.insert(0, 'harness/lib'); import repo_paths as rp\n"
                "print(rp.PROJECT, rp.PROJECT_INFO, rp.HAS_PROJECT, rp.rel(rp.JOB_DESIGN_RULES))\n"
                "try:\n    rp.DATA\nexcept rp.NoProjectError as e:\n    print('raised', isinstance(e, AttributeError), e)\n"
                "print(getattr(rp, 'SKID_MODEL', 'default'))\n")
        r = py(self.job, "-c", code, env=self.env)
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = r.stdout.splitlines()
        self.assertEqual(lines[0], "None {} False job/design-rules")
        self.assertTrue(lines[1].startswith("raised True repo_paths.DATA is not available: no project yet"), lines[1])
        self.assertEqual(lines[2], "default")

    def test_every_check_passes_with_no_project_yet(self):
        for c in CHECKS:
            r = py(self.job, f"harness/checks/{c}", env=self.env)
            first = (r.stdout.splitlines() or [""])[0]
            self.assertEqual(r.returncode, 0, f"{c}: {r.stdout}{r.stderr}")
            self.assertIn("PASS", first, c)
            self.assertIn("no project yet", first, c)

    def test_project_scripts_refuse_with_no_project(self):
        for script, *args in NEEDS_PROJECT:
            r = py(self.job, f"harness/scripts/{script}", *args, env=self.env)
            self.assertEqual(r.returncode, 2, f"{script}: {r.stdout}{r.stderr}")
            self.assertIn("REFUSED - no project yet", r.stderr, script)
            self.assertNotIn("Traceback", r.stderr, script)

    def test_first_project(self):
        with tempfile.TemporaryDirectory() as d:
            j = Path(d) / "Gadget-Skids"
            rc, out = quiet(JN.main, [str(j), "--name", "Gadget Skids", "--repo", "cpme-test/Gadget-Skids",
                                      "--master", str(self.master), "--project", "Project-0000-00-TST-001"])
            self.assertIn(rc, (0, 1), out)
            self.assertTrue((j / "job" / "Project-0000-00-TST-001" / "project.yaml").is_file())
            self.assertIn("Project-0000-00-TST-001", (j / "job" / "JOB.md").read_text(encoding="utf-8"))
            r = py(j, "harness/checks/project_layout.py", env=self.env)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("1 project folder(s), 0 template folder(s) missing", r.stdout)
            r = py(j, "harness/checks/sanitary.py", env=self.env)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertNotIn("no project yet", r.stdout)


if __name__ == "__main__":
    unittest.main()
