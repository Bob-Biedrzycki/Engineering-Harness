"""Tests of the repo_paths names for the plan set and working locations (REVW-001, 2026-11-23): each resolves under
the level it belongs to, and the four names that pointed at folders that never existed are gone (F-061).

    .\\harness\\tools\\venv\\Scripts\\python.exe -m unittest harness.tests.test_repo_paths_work_names -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists())
sys.path.insert(0, str(REPO / "harness" / "lib"))
import repo_paths as rp  # noqa: E402


class TypicalLevel(unittest.TestCase):
    def test_fast_drawings(self):
        self.assertEqual(rp.fast_drawings("typical"), rp.TYPICAL / "03_Working_Design" / "Fast_Edits" / "Fast_Drawings")
        self.assertEqual(rp.fast_drawings("typical").parent.parent, rp.TYPICAL_WORKING)

    def test_plan_set_sheets(self):
        self.assertEqual(rp.plan_set_sheets("typical"), rp.JOB_WORK / "plan-set-sheets")

    def test_plan_set_work(self):
        self.assertEqual(rp.PLAN_SET_WORK, rp.TYPICAL / "_work" / "plan-set")

    def test_bad_level(self):
        with self.assertRaises(ValueError):
            rp.fast_drawings("job")

    def test_removed_names(self):
        for name in ("JOB_PRESENTATIONS", "JOB_LISTS", "JOB_REGISTERS", "JOB_MODELS_WORK"):
            self.assertFalse(hasattr(rp, name), name)


class ProjectLevel(unittest.TestCase):
    def test_project_names(self):
        if not rp.HAS_PROJECT:
            with self.assertRaises(rp.NoProjectError):
                rp.fast_drawings("project")
            with self.assertRaises(rp.NoProjectError):
                rp.ACCEPT_WORK  # noqa: B018
            return
        self.assertEqual(rp.fast_drawings("project"), rp.EXPORTS / "Fast_Drawings")
        self.assertEqual(rp.plan_set_sheets("project"), rp.WORK / "plan-set-sheets")
        self.assertEqual(rp.ACCEPT_WORK, rp.PROJECT / "_work" / "accept")
        self.assertEqual(rp.WELD_BEAD_CACHE, rp.PROJECT / "_work" / "weld-bead-cache")


if __name__ == "__main__":
    unittest.main()
