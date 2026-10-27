"""One Drive store for the whole job (Bob, chat, 2026-10-26): job/drive-store.yaml, `*` matches any project folder.

    .\\harness\\tools\\venv\\Scripts\\python.exe -m unittest harness.tests.test_drive_store_job_level -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists())
sys.path.insert(0, str(REPO / "harness" / "lib"))
import drive_rules as D  # noqa: E402
import repo_paths as rp  # noqa: E402


class JobLevelStore(unittest.TestCase):
    def setUp(self):
        self.cfg = D.load(rp.DRIVE_STORE_CONFIG)

    def test_config_is_job_level(self):
        self.assertEqual(rp.DRIVE_STORE_CONFIG, rp.JOBS / "drive-store.yaml")
        if rp.HAS_PROJECT:
            self.assertFalse((rp.PROJECT / "drive-store.yaml").exists())

    def test_wildcard_covers_any_project(self):
        for p in ("job/Project-0000-00-TST-999/04_Vendor_Data/02_Pumps/P-1/a.pdf",
                  "job/Project-0000-00-TST-001/06_Issued_Revisions/Models/M/M-revA.step.zip",
                  "job/Project-0000-00-TST-999/03_Working_Design/CAD/05_Purchased_Components/COMP-0002_A_B/x.step",
                  "job/components/COMP-0001_A_B/02_STEP_Vendor/x.step"):
            self.assertEqual(D.rule_for(p, 10, self.cfg), "dir", p)

    def test_records_stay_in_git(self):
        for p in ("job/components/component-register.csv",
                  "job/Project-0000-00-TST-001/03_Working_Design/PID/02_Tag_Lists/line-list.csv",
                  "job/Project-0000-00-TST-001/06_Issued_Revisions/Models/M/revisions.csv"):
            self.assertIsNone(D.rule_for(p, 10, self.cfg), p)

    def test_work_folders_excluded_in_every_project(self):
        for p in ("job/_work/drive-root.txt", "job/Project-X/_work/a.bin",
                  "job/Project-X/03_Working_Design/Exports/build/a.step"):
            self.assertTrue(D.excluded(p, self.cfg), p)
        self.assertFalse(D.excluded("job/Project-X/04_Vendor_Data/a.pdf", self.cfg))

    def test_under(self):
        self.assertTrue(D.under("job/P-1/04_Vendor_Data/x", "job/*/04_Vendor_Data"))
        self.assertFalse(D.under("job/components/x", "job/*/04_Vendor_Data"))
        self.assertTrue(D.under("job/components", "job/components"))


if __name__ == "__main__":
    unittest.main()
