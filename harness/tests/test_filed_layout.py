"""Tests of harness/checks/filed_layout.py: one folder per filed revision (Bob, chat, 2026-10-30).

    .\\harness\\tools\\venv\\Scripts\\python.exe -m unittest harness.tests.test_filed_layout -v
"""
from __future__ import annotations

import csv
import os
import shutil
import stat
import sys
import tempfile
import unittest
from pathlib import Path

REPO = next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists())
sys.path.insert(0, str(REPO / "harness" / "lib"))
sys.path.insert(0, str(REPO / "harness" / "checks"))
import filed_layout as FL  # noqa: E402

COLS = ["document_id", "revision", "file", "file_date", "sha256", "bytes", "source", "notes", "description"]


def write_rows(folder: Path, rows: list[dict]) -> None:
    with open(folder / "revisions.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows({k: r.get(k, "") for k in COLS} for r in rows)


def read_files(folder: Path) -> list[str]:
    with open(folder / "revisions.csv", newline="", encoding="utf-8") as f:
        return [r["file"] for r in csv.DictReader(f)]


class FiledLayout(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="filed-layout-test-"))
        self.doc = self.tmp / "M-1"
        self.doc.mkdir()

        def unlock(func, path, _exc):
            os.chmod(path, stat.S_IWRITE)
            func(path)
        self.addCleanup(shutil.rmtree, self.tmp, onerror=unlock)

    def flat(self):
        """Two configurations, B Rev A and B, X Rev A, all loose beside revisions.csv (the old layout)."""
        rows = []
        for doc, rev in (("M-1-B", "A"), ("M-1-B", "B"), ("M-1-X", "A")):
            for suffix in (".glb", "-bom-model.csv"):
                name = f"{doc}-rev{rev}{suffix}"
                (self.doc / name).write_text(name, encoding="utf-8")
                rows.append({"document_id": doc, "revision": rev, "file": name})
        (self.doc / "M-1-B-revA.glb.drive").write_text("{}", encoding="utf-8")
        write_rows(self.doc, rows)

    def test_flat_layout_fails(self):
        self.flat()
        problems = FL.check(self.doc)
        self.assertTrue(any("loose file" in p for p in problems))
        self.assertTrue(any("is not in M-1-B-revA/" in p for p in problems))

    def test_fix_moves_without_renaming(self):
        self.flat()
        before = {p.name: p.read_bytes() for p in self.doc.iterdir() if not p.name.endswith((".csv", ".drive"))
                  or p.name.endswith("-bom-model.csv")}
        moved = []
        FL.fix(self.doc, moved)
        self.assertEqual(FL.check(self.doc), [])
        self.assertEqual(sorted(p.name for p in self.doc.iterdir()),
                         ["M-1-B-revA", "M-1-B-revB", "M-1-X-revA", "revisions.csv"])
        for name, data in before.items():
            stem = name.split("-rev")[0] + "-rev" + name.split("-rev")[1][0]
            p = self.doc / stem / name
            self.assertEqual(p.read_bytes(), data)
            self.assertFalse(os.access(p, os.W_OK), "a filed file stays read-only")
        self.assertIn("M-1-B-revB/M-1-B-revB.glb", read_files(self.doc))
        self.assertEqual(len(moved), 6)
        self.assertFalse((self.doc / "M-1-B-revA.glb.drive").exists(), "old pointer removed; drive_store rewrites it")

    def test_pointer_counts_as_present(self):
        (self.doc / "M-1-revA").mkdir()
        (self.doc / "M-1-revA" / "M-1-revA.glb.drive").write_text("{}", encoding="utf-8")
        write_rows(self.doc, [{"document_id": "M-1", "revision": "A", "file": "M-1-revA/M-1-revA.glb"}])
        self.assertEqual(FL.check(self.doc), [])

    def test_model_revision_subfolders(self):
        """A model revision (a folder under Models/) keeps the model at the top and the rest in Takeoffs/, Reports/,
        Views/ and Presentations/P<nn>/ (Bob, chat, 2026-11-03); a takeoff at the top is reported."""
        doc = self.tmp / "Models" / "M-2"
        rev = doc / "M-2-X-revA"
        files = {"M-2-X-revA/M-2-X-revA.glb": "", "M-2-X-revA/Takeoffs/M-2-X-revA-bom-model.csv": "",
                 "M-2-X-revA/Reports/M-2-X-revA-manifest.json": "", "M-2-X-revA/Views/M-2-X-revA-view-iso.png": "",
                 "M-2-X-revA/Presentations/P01/M-2-X-revA-P01-front.png": ""}
        for f in files:
            (doc / f).parent.mkdir(parents=True, exist_ok=True)
            (doc / f).write_text("x", encoding="utf-8")
        write_rows(doc, [{"document_id": "M-2-X", "revision": "A", "file": f} for f in files])
        self.assertEqual(FL.check(doc), [])
        (rev / "M-2-X-revA-spool-list.csv").write_text("x", encoding="utf-8")
        write_rows(doc, [{"document_id": "M-2-X", "revision": "A", "file": f} for f in files]
                   + [{"document_id": "M-2-X", "revision": "A", "file": "M-2-X-revA/M-2-X-revA-spool-list.csv"}])
        self.assertTrue(any("belongs in M-2-X-revA/Takeoffs/" in p for p in FL.check(doc)))

    def test_unknown_revision_folder(self):
        write_rows(self.doc, [])
        (self.doc / "M-1-revC").mkdir()
        self.assertTrue(any("not a revision" in p for p in FL.check(self.doc)))


if __name__ == "__main__":
    unittest.main()
