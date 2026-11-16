"""Tests of harness/scripts/data_sheets.py: the job's settings, the changed / unchanged comparison with the last filed
revision, and the CPME-Generated file name label (Bob, 2026-11-16). Every test works in a scratch folder with
scratch lists; nothing is read from or written to a job's filed revisions.

    .\\harness\\tools\\venv\\Scripts\\python.exe -m unittest harness.tests.test_data_sheets -v
"""
from __future__ import annotations

import contextlib
import csv
import io
import os
import shutil
import stat
import sys
import tempfile
import unittest
from pathlib import Path

REPO = next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists())
sys.path.insert(0, str(REPO / "harness" / "lib"))
sys.path.insert(0, str(REPO / "harness" / "scripts"))
sys.path.insert(0, str(REPO / "harness" / "checks"))
import data_sheets as DS  # noqa: E402
import filed_layout as FL  # noqa: E402

EQUIPMENT_COLS = ["tag", "description", "size_rating", "pid_sheet", "component_id", "vendor", "model",
                  "empty_weight_lb", "operating_weight_lb", "operating_weight_max_lb", "weight_basis",
                  "support_count", "load_per_support_max_lb", "notes", "step_model_ref"]
HEADERS = {
    "instrument-list.csv": ["tag", "type", "range", "signal", "pid_sheet", "process_connection", "mounting_orientation",
                            "straight_run_req", "access_note", "line_no_or_equip", "component_id"],
    "valve-list.csv": ["tag", "type", "size_od_in", "pid_sheet", "actuator", "feedback", "solenoid", "air_connection",
                       "process_connection", "orientation", "line_no", "component_id"],
    "line-list.csv": ["line_no", "service", "service_class", "size_od_in", "gauge", "material", "spec",
                      "design_press_psig", "design_temp_f", "finish_ra", "from_tag", "to_tag"],
    "motor-load-list.csv": ["tag", "driven_equipment", "hp", "voltage", "phase", "starter_or_vfd"],
}


def write_csv(path: Path, cols: list[str], rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows({k: r.get(k, "") for k in cols} for r in rows)


def fake_pdf(_src: Path, pdf: Path) -> int:
    pdf.write_bytes(b"%PDF-1.4\n1 0 obj << /Type /Page >> endobj\n%%EOF\n")
    return 1


class DataSheets(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="data-sheets-test-"))

        def unlock(func, path, _exc):
            os.chmod(path, stat.S_IWRITE)
            func(path)
        self.addCleanup(shutil.rmtree, self.tmp, onerror=unlock)
        self.addCleanup(DS.configure)
        self.lists = self.tmp / "lists"
        self.lists.mkdir()
        self.root = self.tmp / "Drawings"
        self.root.mkdir()
        self.stage = self.tmp / "stage"
        for name, cols in HEADERS.items():
            write_csv(self.lists / name, cols, [])
        self.equipment([("EQ-1", "Holding vessel, 10 gal"), ("EQ-2", "Transfer unit")])
        self.settings = self.tmp / "data-sheets.yaml"
        self.settings.write_text(f"doc_prefix: TST-DS-\nfile_to: job\nsubtitle: Test product\n"
                                 f"lists: {self.lists.as_posix()}\n", encoding="utf-8")

    def equipment(self, rows):
        write_csv(self.lists / "equipment-list.csv", EQUIPMENT_COLS,
                  [{"tag": t, "description": d, "size_rating": "unknown", "pid_sheet": "1", "component_id": "unknown",
                    "empty_weight_lb": "unknown", "operating_weight_lb": "unknown",
                    "operating_weight_max_lb": "unknown", "weight_basis": "unknown", "support_count": "unknown",
                    "load_per_support_max_lb": "unknown"} for t, d in rows])

    def records(self):
        cfg = DS.load_settings(self.settings)
        DS.configure(cfg.text_rules)
        rec = DS.Records(cfg)
        return cfg, rec, {sh.tag: sh for sh in DS.all_sheets(rec)}

    # ---- settings
    def test_no_settings_is_a_plain_refusal(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            code = DS.main(["--settings", str(self.tmp / "absent.yaml")])
        self.assertEqual(code, 2)
        self.assertIn("this job has no data sheet settings", err.getvalue())
        self.assertNotIn("Traceback", err.getvalue())

    def test_settings_lacking_a_key_are_refused(self):
        self.settings.write_text("file_to: job\n", encoding="utf-8")
        with self.assertRaises(DS.Refused) as c:
            DS.load_settings(self.settings)
        self.assertIn("doc_prefix", str(c.exception))

    def test_no_model_and_no_datum_record_print_unknown_with_the_reason(self):
        _, rec, sheets = self.records()
        page = DS.render(sheets["EQ-1"], "TST-DS-EQ-1", "A", "2026-01-01")
        self.assertIn("no filed model is named in the data sheet settings", page.lower())
        self.assertIn("model unknown", page)
        self.assertEqual(DS.datum_origin(None)[2], "no datum record is named in the data sheet settings")
        self.assertIn("is missing", DS.datum_origin(self.tmp / "absent.tol.yaml")[2])

    # ---- the CPME-Generated label
    def test_generated_name_carries_the_label_after_the_revision(self):
        self.assertEqual(DS.generated_name("TST-DS-EQ-1", "B", ".pdf"), "TST-DS-EQ-1-revB-CPME-Generated.pdf")
        self.assertTrue(DS.generated_name("D", "AA", ".html").startswith("D-revAA"))

    # ---- comparison with the last filed revision, and filing
    def test_new_then_filed_then_unchanged_then_changed(self):
        cfg, rec, sheets = self.records()
        self.assertEqual(DS.compare(sheets["EQ-1"], "TST-DS-EQ-1", self.root)[0], "new")
        filed = DS.file_sheets(cfg, [sheets["EQ-1"]], self.root, self.stage, "first issue", "", "2026-01-01",
                               pdf_maker=fake_pdf)
        (doc, rev, files), = filed
        self.assertEqual((doc, rev), ("TST-DS-EQ-1", "A"))
        self.assertEqual(sorted(f.name for f in files),
                         ["TST-DS-EQ-1-revA-CPME-Generated.html", "TST-DS-EQ-1-revA-CPME-Generated.pdf"])
        for f in files:
            self.assertFalse(os.access(f, os.W_OK), "a filed file is read-only")
        with open(self.root / doc / "revisions.csv", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual([r["file"] for r in rows], ["TST-DS-EQ-1-revA/TST-DS-EQ-1-revA-CPME-Generated.pdf",
                                                     "TST-DS-EQ-1-revA/TST-DS-EQ-1-revA-CPME-Generated.html"])
        self.assertEqual(FL.check(self.root / doc), [], "filed_layout accepts the labelled names")

        # the same records on another day: unchanged (date and letter set aside); filing it again is refused
        _, _, sheets = self.records()
        self.assertEqual(DS.compare(sheets["EQ-1"], "TST-DS-EQ-1", self.root)[:2], ("unchanged", "A"))
        with self.assertRaises(DS.Refused):
            DS.file_sheets(cfg, [sheets["EQ-1"]], self.root, self.stage, "again", "", "2026-02-02",
                           pdf_maker=fake_pdf)
        self.assertEqual(DS.compare(sheets["EQ-2"], "TST-DS-EQ-2", self.root)[0], "new")

        # a changed list row: changed, with the difference named; the next filing is Rev B beside Rev A
        self.equipment([("EQ-1", "Holding vessel, 20 gal"), ("EQ-2", "Transfer unit")])
        _, _, sheets = self.records()
        status, last, diff = DS.compare(sheets["EQ-1"], "TST-DS-EQ-1", self.root)
        self.assertEqual((status, last), ("changed", "A"))
        self.assertIn("20 gal", diff)
        (_, rev, _), = DS.file_sheets(cfg, [sheets["EQ-1"]], self.root, self.stage, "vessel size", "",
                                      "2026-03-03", pdf_maker=fake_pdf)
        self.assertEqual(rev, "B")
        self.assertTrue((self.root / doc / "TST-DS-EQ-1-revA" / "TST-DS-EQ-1-revA-CPME-Generated.html").is_file())
        self.assertEqual(FL.check(self.root / doc), [])

    def test_a_tag_gone_from_the_lists_is_reported(self):
        cfg, rec, sheets = self.records()
        DS.file_sheets(cfg, [sheets["EQ-2"]], self.root, self.stage, "first issue", "", "2026-01-01",
                       pdf_maker=fake_pdf)
        self.equipment([("EQ-1", "Holding vessel, 10 gal")])
        _, rec, _ = self.records()
        self.assertEqual(DS.removed_docs(cfg, self.root, DS.all_sheets(rec)), ["TST-DS-EQ-2"])

    def test_the_preview_run_writes_only_changed_and_new(self):
        cfg, rec, sheets = self.records()
        DS.file_sheets(cfg, [sheets["EQ-1"]], self.root, self.stage, "first issue", "", "2026-01-01",
                       pdf_maker=fake_pdf)
        out = self.tmp / "preview"
        os.environ["CPME_DRAWINGS_ROOT"] = str(self.root)
        self.addCleanup(os.environ.pop, "CPME_DRAWINGS_ROOT", None)
        with contextlib.redirect_stdout(io.StringIO()) as so:
            code = DS.main(["--settings", str(self.settings), "--html-only", "--out", str(out)])
        self.assertEqual(code, 0, so.getvalue())
        self.assertEqual(sorted(p.name for p in out.glob("*.html")), ["TST-DS-EQ-2-revA-CPME-Generated.html"])
        self.assertIn("1 unchanged, 0 changed, 1 new", so.getvalue())


if __name__ == "__main__":
    unittest.main()
