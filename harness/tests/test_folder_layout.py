"""Tests of harness/checks/folder_layout.py: every folder under job/ is named (REVW-001 CAPA PA-2, 2026-11-23).

Each test builds a scratch repo (a two-folder project template, a job/ tree and job/folder-register.csv) and runs the
check on it; git is used only to mark folders tracked or ignored (no commit).

    .\\harness\\tools\\venv\\Scripts\\python.exe -m unittest harness.tests.test_folder_layout -v
"""
from __future__ import annotations

import contextlib
import csv
import io
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists())
sys.path.insert(0, str(REPO / "harness" / "lib"))
sys.path.insert(0, str(REPO / "harness" / "checks"))
import folder_layout as FL  # noqa: E402

PROJ = "job/Project-0000-00-TST-001"
TYP = "job/Typical-TST"


def make_repo(root: Path) -> None:
    for d in ("00_Admin/Registers", "03_Working_Design/CAD/01_Master_Assembly", "06_Issued_Revisions/Drawings"):
        (root / FL.TEMPLATE_REL / d).mkdir(parents=True)
        (root / PROJ / d).mkdir(parents=True)
    (root / PROJ / "06_Issued_Revisions/Drawings/D-1/D-1-revA/sub").mkdir(parents=True)
    (root / TYP / "_work").mkdir(parents=True)
    (root / "job/components/COMP-0001_Maker_Model/01_Cut_Sheet").mkdir(parents=True)


def write_register(root: Path, rows: list[str]) -> None:
    with open(root / FL.REGISTER_REL, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(FL.COLUMNS)
        for path in rows:
            w.writerow([path, "project", "x", "hand", "ignored", "active", "test", "2026-11-23"])


def run(root: Path, *argv: str) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        rc = FL.main(list(argv), root=root)
    return rc, out.getvalue()


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


class FolderLayout(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="folder-layout-test-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        make_repo(self.root)

    def test_no_register_is_not_checked(self):
        rc, out = run(self.root)
        self.assertEqual(rc, 0)
        self.assertIn("folder_layout: PASS - not checked: no job/folder-register.csv", out)
        shutil.rmtree(self.root / "job" / PROJ.split("/")[1])
        rc, out = run(self.root)
        self.assertEqual(rc, 0)
        self.assertIn("folder_layout: PASS - not checked: no project yet, no job/folder-register.csv", out)

    def test_template_guide_and_map_pass(self):
        write_register(self.root, [])
        rc, out = run(self.root)
        self.assertEqual(rc, 0, out)
        self.assertTrue(out.startswith("folder_layout: PASS - "), out)
        self.assertIn("0 not named", out)

    def test_registered_folder_passes(self):
        (self.root / PROJ / "03_Working_Design/Fast_Edits").mkdir()
        write_register(self.root, [f"{PROJ}/03_Working_Design/Fast_Edits"])
        rc, out = run(self.root)
        self.assertEqual(rc, 0, out)

    def test_unregistered_tracked_folder_fails(self):
        d = self.root / PROJ / "03_Working_Design/CAPA-probe-folder"
        d.mkdir()
        (d / "probe.txt").write_text("x", encoding="utf-8")
        git(self.root, "init", "-q")
        git(self.root, "add", f"{PROJ}/03_Working_Design/CAPA-probe-folder/probe.txt")
        write_register(self.root, [])
        rc, out = run(self.root)
        self.assertEqual(rc, 1, out)
        self.assertTrue(out.startswith("folder_layout: FAIL - "), out)
        self.assertIn(f"{PROJ}/03_Working_Design/CAPA-probe-folder/ (tracked)", out)

    def test_unregistered_folder_in_ignored_area_fails(self):
        (self.root / PROJ / "_work/new-scratch").mkdir(parents=True)
        (self.root / ".gitignore").write_text("_work/\n", encoding="utf-8")
        git(self.root, "init", "-q")
        write_register(self.root, [f"{PROJ}/_work"])
        rc, out = run(self.root)
        self.assertEqual(rc, 1, out)
        self.assertIn(f"{PROJ}/_work/new-scratch/ (ignored)", out)

    def test_untracked_folder_reported_untracked(self):
        (self.root / "job/knowledge/new-notes").mkdir(parents=True)
        git(self.root, "init", "-q")
        write_register(self.root, [])
        rc, out = run(self.root)
        self.assertEqual(rc, 1, out)
        self.assertIn("job/knowledge/new-notes/ (untracked)", out)

    def test_deep_row_stops_descent(self):
        (self.root / PROJ / "_work/site/a/b/c").mkdir(parents=True)
        write_register(self.root, [f"{PROJ}/_work", f"{PROJ}/_work/site/**"])
        rc, out = run(self.root)
        self.assertEqual(rc, 0, out)
        # without /** the children are walked and reported
        write_register(self.root, [f"{PROJ}/_work", f"{PROJ}/_work/site"])
        rc, out = run(self.root)
        self.assertEqual(rc, 1, out)
        self.assertIn(f"{PROJ}/_work/site/a/", out)
        self.assertNotIn(f"{PROJ}/_work/site/a/b/", out, "only the first unnamed folder of a branch is listed")

    def test_family_row_matches(self):
        for n in ("revA", "revB"):
            (self.root / PROJ / f"03_Working_Design/CAD/Builds/{n}/{n}-fast-001/logs").mkdir(parents=True)
        write_register(self.root, [f"job/Project-*/03_Working_Design/CAD/Builds",
                                   f"job/Project-*/03_Working_Design/CAD/Builds/rev*",
                                   f"job/Project-*/03_Working_Design/CAD/Builds/rev*/rev*-*-*"])
        rc, out = run(self.root)
        self.assertEqual(rc, 0, out)   # a numbered build folder is not descended (logs/ needs no row)

    def test_typical_needs_map_or_register(self):
        (self.root / TYP / "03_Working_Design/CAD/Typical-Named-Copy").mkdir(parents=True)
        write_register(self.root, [])
        rc, out = run(self.root)
        self.assertEqual(rc, 1, out)
        self.assertIn(f"{TYP}/03_Working_Design/CAD/Typical-Named-Copy/", out)
        self.assertNotIn(f"{TYP}/03_Working_Design/ ", out, "the map names the typical's 03_Working_Design/CAD")

    def test_vendor_tag_folder_by_guide_pattern(self):
        (self.root / PROJ / "04_Vendor_Data/02_Pumps/P-101_Fristam_FZX2150").mkdir(parents=True)
        (self.root / PROJ / "04_Vendor_Data/02_Pumps/P-101, P-102 - Pumps").mkdir(parents=True)
        write_register(self.root, [f"{PROJ}/04_Vendor_Data", f"{PROJ}/04_Vendor_Data/02_Pumps"])
        rc, out = run(self.root)
        self.assertEqual(rc, 1, out)
        self.assertIn("P-101, P-102 - Pumps/", out)
        self.assertNotIn("P-101_Fristam_FZX2150", out)

    def test_stale_and_open_rows_are_notes(self):
        write_register(self.root, [f"{PROJ}/_work/daily/**"])
        with open(self.root / FL.REGISTER_REL, "a", newline="", encoding="utf-8") as f:
            csv.writer(f, lineterminator="\n").writerow(
                [f"{TYP}/_work", "typical", "x", "hand", "ignored", "open", "Bob to decide", "2026-11-23"])
        rc, out = run(self.root)
        self.assertEqual(rc, 0, out)
        self.assertIn(f"note: stale register row (matches nothing on disk): {PROJ}/_work/daily/**", out)
        self.assertIn(f"note: open: {TYP}/_work - Bob to decide", out)

    def test_bad_register_is_an_error(self):
        write_register(self.root, [])
        with open(self.root / FL.REGISTER_REL, "a", newline="", encoding="utf-8") as f:
            f.write(f"{PROJ}/x,project,x,hand,ignored,maybe,test,2026-11-23\n")
        rc, out = run(self.root)
        self.assertEqual(rc, 3, out)
        self.assertIn("folder_layout: ERROR - ", out)

    def test_paths_file_mode(self):
        d = self.root / PROJ / "03_Working_Design/CAPA-probe-folder"
        d.mkdir()
        (d / "probe.txt").write_text("x", encoding="utf-8")
        write_register(self.root, [])
        pf = self.root / "paths.txt"
        pf.write_text(f"{PROJ}/03_Working_Design/CAPA-probe-folder/probe.txt\nharness/scripts/track.py\n"
                      f"{PROJ}/00_Admin/Registers/not-on-disk-yet.csv\n"
                      f"job/components/COMP-0001_Maker_Model/01_Cut_Sheet/x.pdf\n", encoding="utf-8")
        rc, out = run(self.root, "--paths-file", str(pf))
        self.assertEqual(rc, 1, out)
        self.assertIn("folder_layout: FAIL - 4 path(s) checked, 1 in a folder nothing names", out)
        self.assertIn(f"{PROJ}/03_Working_Design/CAPA-probe-folder/probe.txt: in "
                      f"{PROJ}/03_Working_Design/CAPA-probe-folder/", out)
        # a listed folder that holds an unnamed folder
        (self.root / PROJ / "00_Admin/Registers/new-sub").mkdir()
        pf.write_text(f"{PROJ}/00_Admin\n", encoding="utf-8")
        rc, out = run(self.root, "--paths-file", str(pf))
        self.assertEqual(rc, 1, out)
        self.assertIn(f"{PROJ}/00_Admin/Registers/new-sub/", out)
        # a path that does not exist yet, in a named folder (CI)
        pf.write_text(f"{PROJ}/06_Issued_Revisions/Drawings/D-2/D-2-revA/D-2-revA.pdf\n", encoding="utf-8")
        rc, out = run(self.root, "--paths-file", str(pf))
        self.assertEqual(rc, 0, out)

    def test_paths_file_passes_with_register_row(self):
        d = self.root / PROJ / "03_Working_Design/CAPA-probe-folder"
        d.mkdir()
        write_register(self.root, [f"{PROJ}/03_Working_Design/CAPA-probe-folder"])
        pf = self.root / "paths.txt"
        pf.write_text(f"{PROJ}/03_Working_Design/CAPA-probe-folder/probe.txt\n", encoding="utf-8")
        rc, out = run(self.root, "--paths-file", str(pf))
        self.assertEqual(rc, 0, out)


if __name__ == "__main__":
    unittest.main()
