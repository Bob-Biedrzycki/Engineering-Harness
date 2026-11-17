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

    def test_file_folder_puts_the_sheets_in_a_folder_under_drawings(self):
        self.addCleanup(os.environ.pop, "CPME_DRAWINGS_ROOT", None)
        os.environ["CPME_DRAWINGS_ROOT"] = str(self.root)
        self.assertEqual(DS.drawings_root(DS.load_settings(self.settings)), self.root)
        self.settings.write_text(self.settings.read_text(encoding="utf-8") + "file_folder: Data Sheets\n",
                                 encoding="utf-8")
        cfg = DS.load_settings(self.settings)
        self.assertEqual(cfg.file_folder, "Data Sheets")
        self.assertEqual(DS.drawings_root(cfg), self.root / "Data Sheets")

    def test_file_folder_outside_drawings_is_refused(self):
        for bad in ("../elsewhere", "C:/elsewhere", "a/../../b"):
            self.settings.write_text(self.settings.read_text(encoding="utf-8").split("file_folder")[0]
                                     + f"file_folder: {bad}\n", encoding="utf-8")
            with self.assertRaises(DS.Refused):
                DS.load_settings(self.settings)

    def test_settings_lacking_a_key_are_refused(self):
        self.settings.write_text("file_to: job\n", encoding="utf-8")
        with self.assertRaises(DS.Refused) as c:
            DS.load_settings(self.settings)
        self.assertIn("doc_prefix", str(c.exception))

    def test_no_model_and_no_datum_record_print_tbd_and_keep_the_reason_in_the_basis(self):
        # Before the sheet-face rule (DRF-FACE-001, 2026-11-16) the page printed "unknown" and the reason; the reason
        # is a record matter, so the page prints TBD and the basis row keeps the reason (Helper 4, plan set round 2).
        _, rec, sheets = self.records()
        page = DS.render(sheets["EQ-1"], "TST-DS-EQ-1", "A", "2026-01-01")
        self.assertNotIn("unknown", page.lower())
        self.assertIn('<span class="unk">TBD</span>', page)
        rows = DS.basis_rows(sheets["EQ-1"], "TST-DS-EQ-1")
        loc = next(r for r in rows if r["field"] == "Location")
        self.assertEqual(loc["printed"], "TBD")
        self.assertIn("no filed model is named in the data sheet settings", loc["raw"])
        self.assertIn("model unknown", next(r for r in rows if r["field"] == "sources")["raw"])
        self.assertEqual(DS.datum_origin(None)[2], "no datum record is named in the data sheet settings")
        self.assertIn("is missing", DS.datum_origin(self.tmp / "absent.tol.yaml")[2])

    # ---- the sheet-face rule (DRF-FACE-001): the clean sheet is the only sheet
    def test_the_sheet_prints_no_internal_reference_and_the_basis_keeps_it(self):
        write_csv(self.lists / "equipment-list.csv", EQUIPMENT_COLS, [{
            "tag": "EQ-1", "description": "Holding vessel, 10 gal (SRC-0011 p. 3)", "pid_sheet": "1",
            "size_rating": "10 gal per SAN-DL-001; checked by Bob", "component_id": "unknown",
            "empty_weight_lb": "unknown (waits on the maker's drawing, Q-0010)", "operating_weight_lb": "unknown",
            "operating_weight_max_lb": "unknown", "weight_basis": "unknown", "support_count": "4",
            "load_per_support_max_lb": "unknown - answers: Bob"}])
        answers = self.tmp / "answers.csv"
        write_csv(answers, ["file", "tag", "column", "waits_on", "who_can_answer"],
                  [{"file": "equipment-list.csv", "tag": "EQ-1", "column": "load_per_support_max_lb",
                    "waits_on": "frame calc", "who_can_answer": "Bob"}])
        self.settings.write_text(self.settings.read_text(encoding="utf-8") + f"answers: [{answers.as_posix()}]\n",
                                 encoding="utf-8")
        cfg, rec, sheets = self.records()
        page = DS.render(sheets["EQ-1"], "TST-DS-EQ-1", "A", "2026-01-01")
        self.assertEqual(DS.face_findings(page), [], "nothing on the sheet fails the sheet-face check")
        for word in ("SRC-0011", "SAN-DL-001", "Q-0010", "Bob", "answers:", "unknown", "Sources:", ".csv"):
            self.assertNotIn(word, page)
        self.assertIn("Holding vessel, 10 gal", page)
        self.assertIn("4", page)
        # a footnote keeps a plain reason; one with nothing a reader can act on is left off and the cell is just TBD
        self.assertIn("Waits on the maker's drawing.", DS.page_text(page))
        rows = DS.basis_rows(sheets["EQ-1"], "TST-DS-EQ-1")
        load = next(r for r in rows if r["field"] == "Load per support, max")
        self.assertEqual((load["printed"], load["note"], load["who_can_answer"]), ("TBD", "", "Bob"))
        self.assertIn("equipment-list.csv", load["record"])
        size = next(r for r in rows if r["field"] == "Size / rating")
        self.assertIn("SAN-DL-001", size["raw"], "the record's own words are kept in the basis")
        self.assertNotIn("SAN-DL-001", size["printed"])
        # the basis CSV keeps other documents' rows when one document is rewritten
        p = DS.write_basis(cfg, [{"document_id": "TST-DS-EQ-9", "field": "x", "printed": "y"}], {"TST-DS-EQ-9"})
        DS.write_basis(cfg, rows, {"TST-DS-EQ-1"})
        with open(p, encoding="utf-8") as fh:
            docs = {r["document_id"] for r in csv.DictReader(fh)}
        self.assertEqual(docs, {"TST-DS-EQ-1", "TST-DS-EQ-9"})

    def test_scrub_takes_whole_pieces_never_half_a_sentence(self):
        self.assertEqual(DS.scrub("none upstream of the seat (SAN-UTIL-002); PIPE-SVC-001 air carries no rule"),
                         "none upstream of the seat")
        self.assertEqual(DS.scrub("H5 plant air conditions at BL-08"), "plant air conditions at BL-08")
        self.assertEqual(DS.scrub("plug seal unknown"), "plug seal TBD")
        self.assertEqual(DS.plain_reason("No record gives it yet"), "")
        self.assertEqual(DS.plain_reason("whether it takes the lowest rating is Bob's decision"), "")

    # ---- the orchestrator's three scrub rules after the second review (round 2, DS-round1)
    def test_rule_a_none_is_a_value_and_prints_none(self):
        _, rec, sheets = self.records()
        sh = sheets["EQ-1"]
        self.assertEqual(sh.cell("none"), "none")
        self.assertEqual(sh.cell("none (PRR-11)"), "none")
        self.assertIn(">TBD<", sh.cell("unknown"))

    def test_rule_b_a_scrub_never_leaves_a_fragment(self):
        self.assertEqual(DS.scrub("No weight on the brochure; Q-0068 for the vendor drawing"),
                         "No weight on the brochure; waits for the vendor drawing")
        self.assertEqual(DS.plain_reason("Q-0067 panel weight"), "Panel weight is not yet known.")
        # only the failing comma piece goes, the rest of the clause stays
        self.assertEqual(DS.scrub("1 in clamp ends, joint J033 to SAN-UTIL-002 spool, 316L wetted body"),
                         "1 in clamp ends, 316L wetted body")
        # a kept comma piece is never model working talk (second review DS-27)
        self.assertEqual(DS.scrub("1 in clamp branch, branch design open for the next model revision"),
                         "1 in clamp branch")
        # nothing printable left: empty, so the cell prints TBD (never a blank cell)
        self.assertEqual(DS.scrub("PIPE-SVC-001 air"), "")
        _, rec, sheets = self.records()
        self.assertIn(">TBD<", sheets["EQ-1"].cell("PIPE-SVC-001 air"))

    def test_every_printed_note_is_a_sentence(self):
        # orchestrator, round 2: a note is a full sentence a reader outside CPME can act on, or it is not printed
        self.assertFalse(DS.note_ok("Panel weight"))                      # no verb
        self.assertFalse(DS.note_ok("No weight on the FZX brochure; for the vendor drawing"))
        self.assertFalse(DS.note_ok("The weight is to be taken from the"))  # dangling word
        self.assertTrue(DS.note_ok("Panel weight is not yet known."))
        self.assertEqual(DS.plain_reason("Q-0067 panel weight"), "Panel weight is not yet known.")
        self.assertEqual(DS.plain_reason("Not on brochure"), "The value is not given on brochure.")
        # the generator's own short forms are reworded; any other note that is not a sentence stops the run, and
        # is never dropped (orchestrator, round 2, DS-29 / DS-30)
        self.assertEqual(DS.plain_reason("6P739 manufacturer and model not resolved"),
                         "6P739 manufacturer and model are not yet resolved.")
        with self.assertRaises(DS.NoteFails):
            DS.plain_reason("Plant air conditions at BL-08")
        with self.assertRaises(DS.NoteFails):
            DS.plain_reason("Weight basis: empty 375 lb; water SG 1.0; 4 legs")
        _, rec, sheets = self.records()
        for sh in sheets.values():
            for n in sh.notes:
                self.assertTrue(DS.note_ok(n), f"{sh.tag} prints a note that is not a sentence: {n!r}")

    def test_a_note_that_is_not_a_sentence_stops_the_run_and_the_values_file_answers_it(self):
        write_csv(self.lists / "equipment-list.csv", EQUIPMENT_COLS, [{
            "tag": "EQ-1", "description": "Holding vessel", "pid_sheet": "1", "size_rating": "unknown (Plant air at BL-08)",
            "component_id": "unknown", "empty_weight_lb": "unknown", "operating_weight_lb": "unknown",
            "operating_weight_max_lb": "unknown", "weight_basis": "unknown", "support_count": "4",
            "load_per_support_max_lb": "unknown"}])
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            code = DS.main(["--settings", str(self.settings), "--html-only", "--out", str(self.tmp / "p")])
        self.assertEqual(code, 2)
        self.assertIn("EQ-1 | Plant air at BL-08", err.getvalue())        # the tag and the text, nothing dropped
        values = self.tmp / "values.yaml"
        values.write_text("EQ-1:\n  Size / rating:\n    reason: \"The plant air conditions at BL-08 are not yet known\"\n"
                          "  Empty weight:\n    basis_only: true\n    reason: kept in the basis on purpose\n",
                          encoding="utf-8")
        self.settings.write_text(self.settings.read_text(encoding="utf-8") + f"overrides: {values.as_posix()}\n",
                                 encoding="utf-8")
        _, rec, sheets = self.records()
        self.assertEqual(sheets["EQ-1"].failed, [])
        self.assertIn("The plant air conditions at BL-08 are not yet known.", sheets["EQ-1"].notes)

    def test_axis_letters_print_as_the_drawing_words(self):
        # orchestrator, 2026-11-16: no model axis letters on a sheet; the same words as the plan set toolkit
        DS.set_ends({"a": {"tag": "TK-101", "bbox_in": [[0, 0, 0], [30, 30, 40]]},
                     "b": {"tag": "TK-103", "bbox_in": [[100, 0, 0], [130, 30, 40]]}})
        self.addCleanup(DS.set_ends, {})
        self.assertEqual(DS.axis_words("horizontal, flow -X, actuator up (+Z)"),
                         "horizontal, flow toward the TK-101 END, actuator up")
        self.assertEqual(DS.axis_words("on the +Y short outlet, actuator +Y (front)"),
                         "on the FRONT short outlet, actuator toward the FRONT")
        self.assertEqual(DS.axis_words("flow in at -X, out the +Y branch"),
                         "flow in at the TK-101 END, out the FRONT branch")
        self.assertEqual(DS.axis_words("sensor horizontal out of the tank wall (+Y)"),
                         "sensor horizontal out of the tank wall (FRONT)")
        self.assertTrue(DS.face_ok(DS.scrub("eccentric flat at the bottom (+Z up); flow +X")))

    def test_a_basis_only_clause_never_prints(self):
        # DS-20 / DS-27: model-revision talk stays in the basis CSV; a cell keeps only the connection itself
        _, rec, sheets = self.records()
        sh = sheets["EQ-1"]
        raw = ("integrated 2 in clamp, no thread; branch design open for the next model revision, dead-leg case "
               "for the sanitary review")
        page = sh.cell(raw)
        self.assertNotIn("model revision", page)
        self.assertNotIn("sanitary review", page)
        self.assertIn("integrated 2 in clamp", page)

    def test_rule_c_a_commodity_loses_its_number_a_selected_item_keeps_its_own(self):
        reg = {"COMP-0001": [{"component_id": "COMP-0001", "selection": "commodity", "model": "S7SWWK-2-PL",
                              "part_number": "S7SWWK-2-PL"}],
               "COMP-0002": [{"component_id": "COMP-0002", "selection": "commodity", "model": "4322K153",
                              "part_number": "4322K153"}],
               "COMP-0003": [{"component_id": "COMP-0003", "selection": "selected", "model": "PI1704",
                              "part_number": "PI1704"}]}
        self.addCleanup(DS.set_commodity_numbers, {})
        DS.set_commodity_numbers(reg)
        self.assertEqual(DS.scrub("PI1704 flush on the S7SWWK-2 short-outlet tee"), "PI1704 flush on the short-outlet tee")
        self.assertEqual(DS.scrub("McMaster 4322K153 clamp and the PI1704 sensor"), "clamp and the PI1704 sensor")
        self.assertTrue(DS.face_ok("PI1704"))
        self.assertFalse(DS.face_ok("S7SWWK-2-PL"))

    # ---- fast drawings (plan set round 2, brief D2)
    def test_fast_drawings_are_numbered_never_overwritten_and_logged(self):
        # a real-form document prefix: the sheet-face check knows CPME document numbers, and the fast file name in
        # the footer must pass it (a made-up prefix such as TST-DS- reads as a rule id)
        self.settings.write_text(self.settings.read_text(encoding="utf-8").replace("TST-DS-", "CIP-TYP-DS-"),
                                 encoding="utf-8")
        cfg, rec, sheets = self.records()
        fast = self.tmp / "Fast_Drawings"
        os.environ["CPME_FAST_ROOT"] = str(fast)
        self.addCleanup(os.environ.pop, "CPME_FAST_ROOT", None)
        DS.file_sheets(cfg, [sheets["EQ-1"]], self.root, self.stage, "first issue", "", "2026-01-01",
                       pdf_maker=fake_pdf)
        with self.assertRaises(DS.Refused):
            DS.write_fast(cfg, rec, [sheets["EQ-1"]], self.root, "", "2026-01-02", pdf_maker=fake_pdf)
        one = DS.write_fast(cfg, rec, list(sheets.values()), self.root, "clean sheets", "2026-01-02",
                            pdf_maker=fake_pdf)
        two = DS.write_fast(cfg, rec, [sheets["EQ-1"]], self.root, "again", "2026-01-02", pdf_maker=fake_pdf)
        self.assertEqual([s for s, *_ in one], ["CIP-TYP-DS-EQ-1-revA-fast-001", "CIP-TYP-DS-EQ-2-first-fast-001"])
        self.assertEqual(two[0][0], "CIP-TYP-DS-EQ-1-revA-fast-002")
        self.assertTrue(all(pages == 1 and face == 0 for _, _, pages, face in one + two))
        page = (fast / "CIP-TYP-DS-EQ-1" / "CIP-TYP-DS-EQ-1-revA-fast-002" / "CIP-TYP-DS-EQ-1-revA-fast-002.html").read_text(
            encoding="utf-8")
        self.assertIn("FAST-002 - NOT ISSUED", page)
        log = (fast / "fast-log.md").read_text(encoding="utf-8")
        self.assertEqual(log.count("| CIP-TYP-DS-EQ-"), 3)
        self.assertIn("| clean sheets |", log)
        self.assertEqual(sorted(p.name for p in (self.root / "CIP-TYP-DS-EQ-1").iterdir()),
                         ["CIP-TYP-DS-EQ-1-revA", "revisions.csv"], "a fast drawing never touches the filed revisions")

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
