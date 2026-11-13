"""Unit tests for the one build series (harness/lib/repo_paths.py current_build / build_key, model_build.py
new_build_dir, find_build, log_row, adopt_earlier_layout, zip_earlier_steps; Bob, chat, 2026-11-12).

Every build, fast or full, is a numbered folder that is never overwritten. Scratch folders only. Stdlib unittest:

    .\\harness\\tools\\venv\\Scripts\\python.exe -m unittest discover -s harness\\tests -v
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

REPO = next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists())
sys.path.insert(0, str(REPO / "harness" / "lib"))
import repo_paths as rp  # noqa: E402
import model_build as mb  # noqa: E402


class Scratch(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.builds = self.root / "CAD" / "Builds"
        self.saved = os.environ.pop("CPME_BUILD_DIR", None)
        self.addCleanup(lambda: os.environ.__setitem__("CPME_BUILD_DIR", self.saved) if self.saved else None)

    def make(self, name: str, *files: str) -> Path:
        d = self.builds / name.split("-")[0] / name
        d.mkdir(parents=True)
        for f in files:
            (d / f).write_text("x", encoding="utf-8")
        return d


class Names(unittest.TestCase):
    def test_key_orders_letters_then_numbers(self):
        names = ["revAA-full-001", "revB-fast-002", "revA-full-010", "revB-full-001", "first-full-003"]
        self.assertEqual(sorted(names, key=rp.build_key),
                         ["first-full-003", "revA-full-010", "revB-full-001", "revB-fast-002", "revAA-full-001"])

    def test_other_names_are_not_builds(self):
        for n in ("none", "revA", "revA-fast-1", "reva-fast-001", "revA-quick-001", "build-log.md"):
            self.assertIsNone(rp.build_key(n), n)


class CurrentBuild(Scratch):
    def test_none_when_no_full_build(self):
        self.make("revA-fast-001")
        self.assertEqual(rp.current_build(self.builds), self.builds / "none")
        self.assertFalse(rp.current_build(self.builds).exists())

    def test_latest_full_build_fast_ones_ignored(self):
        self.make("revA-full-002")
        self.make("revA-fast-009")
        want = self.make("revB-full-001")
        self.make("revB-fast-002")
        self.assertEqual(rp.current_build(self.builds), want)

    def test_running_build_is_named_by_the_environment(self):
        self.make("revA-full-002")
        os.environ["CPME_BUILD_DIR"] = str(self.builds / "revA" / "revA-full-003")
        self.addCleanup(lambda: os.environ.pop("CPME_BUILD_DIR", None))
        self.assertEqual(rp.current_build(self.builds), self.builds / "revA" / "revA-full-003")


class NewBuild(Scratch):
    def test_one_counter_for_both_kinds(self):
        self.assertEqual(mb.new_build_dir("fast", self.builds, "A").name, "revA-fast-001")
        self.make("revA-fast-001")
        self.make("revA-fast-002")
        self.assertEqual(mb.new_build_dir("full", self.builds, "A").name, "revA-full-003")
        self.make("revA-full-003")
        self.assertEqual(mb.new_build_dir("fast", self.builds, "A").name, "revA-fast-004")

    def test_counter_restarts_after_a_filing(self):
        self.make("revA-full-035")
        new = mb.new_build_dir("fast", self.builds, "B")
        self.assertEqual((new.parent.name, new.name), ("revB", "revB-fast-001"))

    def test_before_the_first_revision(self):
        self.assertEqual(mb.new_build_dir("full", self.builds, None).name, "first-full-001")

    def test_new_folder_is_not_made_and_never_an_existing_one(self):
        self.make("revA-full-001")
        new = mb.new_build_dir("full", self.builds, "A")
        self.assertFalse(new.exists())

    def test_find_build(self):
        d = self.make("revA-full-003")
        self.assertEqual(mb.find_build("revA-full-003", self.builds), d)
        self.assertIsNone(mb.find_build("revA-full-004", self.builds))


class Log(Scratch):
    def test_rows_under_one_heading_per_day(self):
        mb.log_row(self.builds, "revA-fast-001", "move | the pump", "moved\nit", "int PASS; 80 s")
        mb.log_row(self.builds, "revA-full-002", "", "full build", "int PASS; STEP PASS; 6.1 min")
        text = (self.builds / mb.LOG_NAME).read_text(encoding="utf-8")
        self.assertEqual(text.count("## "), 1)
        self.assertEqual(text.count(mb.LOG_HEAD), 1)
        self.assertIn("| revA-fast-001 |", text)
        self.assertIn("move / the pump", text)          # a pipe in a cell would break the table
        self.assertIn("moved it", text)
        self.assertIn("| revA-full-002 |", text)


class Adopt(Scratch):
    def test_earlier_layout_becomes_the_one_series(self):
        old_fast = self.root / "CAD" / "Fast_Builds"
        (old_fast / "revA" / "revA-fast-001").mkdir(parents=True)
        (old_fast / "revA" / "revA-fast-002").mkdir()
        (old_fast / "fast-log.md").write_text("# Fast builds: running list\n", encoding="utf-8")
        old_build = self.root / "Exports" / "build" / "M-1"
        old_build.mkdir(parents=True)
        (old_build / "iterate-summary.json").write_text("{}", encoding="utf-8")
        (old_build / "bom-model.csv").write_text("a,b\n", encoding="utf-8")

        done = mb.adopt_earlier_layout(self.builds, old_fast, self.builds, old_build, "A")
        self.assertEqual(len(done), 3, done)
        self.assertFalse(old_fast.exists())
        self.assertFalse(old_build.exists())
        self.assertTrue((self.builds / "revA" / "revA-fast-002").is_dir())
        self.assertFalse((self.builds / "fast-log.md").exists())
        moved = self.builds / "revA" / "revA-full-003"
        self.assertEqual((moved / "bom-model.csv").read_text(encoding="utf-8"), "a,b\n")
        self.assertIn("| revA-full-003 |", (self.builds / mb.LOG_NAME).read_text(encoding="utf-8"))
        self.assertEqual(rp.current_build(self.builds), moved)
        # a second run finds nothing to move
        self.assertEqual(mb.adopt_earlier_layout(self.builds, old_fast, self.builds, old_build, "A"), [])

    def test_nothing_to_adopt(self):
        self.assertEqual(mb.adopt_earlier_layout(self.builds, self.root / "CAD" / "Fast_Builds", self.builds,
                                                 self.root / "Exports" / "build" / "M-1", "A"), [])
        self.assertFalse(self.builds.exists())

    def test_both_roots_present_is_reported_not_merged(self):
        old_fast = self.root / "CAD" / "Fast_Builds"
        old_fast.mkdir(parents=True)
        self.builds.mkdir(parents=True)
        done = mb.adopt_earlier_layout(self.builds, old_fast, self.builds, self.root / "nope", "A")
        self.assertTrue(done[0].startswith("NOT MOVED"))
        self.assertTrue(old_fast.is_dir())


class ZipSteps(Scratch):
    def test_only_the_build_in_hand_keeps_its_step(self):
        a = self.make("revA-full-001", "M-1.step", "bom-model.csv")
        b = self.make("revA-full-004", "M-1.step")
        f = self.make("revA-fast-002", "bom-model.csv")
        self.assertEqual(mb.zip_earlier_steps(self.builds, b), ["revA-full-001"])
        self.assertFalse((a / "M-1.step").exists())
        with zipfile.ZipFile(a / "M-1.step.zip") as z:
            self.assertEqual(z.namelist(), ["M-1.step"])
            self.assertEqual(z.read("M-1.step"), b"x")
        self.assertTrue((a / "bom-model.csv").is_file())
        self.assertTrue((b / "M-1.step").is_file())
        self.assertTrue((f / "bom-model.csv").is_file())
        self.assertEqual(mb.zip_earlier_steps(self.builds, b), [])     # nothing left to zip

    def test_a_locked_build_cannot_be_written_and_is_still_zipped(self):
        a = self.make("revA-full-001", "M-1.step", "bom-model.csv")
        (a / "logs").mkdir()
        (a / "logs" / "lists.log").write_text("x", encoding="utf-8")
        b = self.make("revA-full-002", "M-1.step")
        mb.lock_build(a)
        for f in (a / "bom-model.csv", a / "logs" / "lists.log", a / "M-1.step"):
            with self.assertRaises(PermissionError):
                f.write_text("changed", encoding="utf-8")
        self.assertEqual(mb.zip_earlier_steps(self.builds, b), ["revA-full-001"])
        self.assertFalse((a / "M-1.step").exists())
        with self.assertRaises(PermissionError):
            (a / "M-1.step.zip").write_bytes(b"changed")
        self.assertEqual((a / "bom-model.csv").read_text(encoding="utf-8"), "x")


if __name__ == "__main__":
    unittest.main()
