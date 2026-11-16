"""Unit tests of harness/checks/sheet_face.py (DRF-FACE-001: what may print on a drawing sheet)."""
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists())
spec = importlib.util.spec_from_file_location("sheet_face", ROOT / "harness" / "checks" / "sheet_face.py")
sf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sf)


class CheckTextTests(unittest.TestCase):
    def bad(self, s, what):
        r = sf.check_text(s)
        self.assertTrue(any(what in x for x in r), f"{s!r} -> {r}")

    def good(self, s):
        self.assertEqual(sf.check_text(s), [], s)

    # --- Bob's highlighted items on the spool drawing notes (review notes, 2026-11-16) ---
    def test_bob_highlights_fail(self):
        self.bad("PRODUCT-CONTACT FINISH PER LINE (SAN-RA-001).", "design rule id")
        self.bad("LASER CUT TO LENGTH (TR-14).", "requirement")
        self.bad("PER ASME BPE PART DT (GDT-PIPE-001).", "design rule id")
        self.bad("NO COPY ON HAND (job/design-rules/tolerancing.yaml).", "repo")
        self.bad("PIECES ARE SPLIT AT EVERY WELD (TR-24).", "requirement")
        self.bad("ARE X.XXX (TOLERANCE BLOCK; BRIEF RULE 15).", "internal word")
        self.bad("GASKETS: EPDM PEROXIDE-CURED; UNKNOWN (UTILITY, SAN-UTIL-001).", "unknown")
        self.bad("THE DEC-0009 UNITS-DIGIT NUMBERS IS OPEN QUESTION Q-0003", "decision")
        self.bad("THE DEC-0009 UNITS-DIGIT NUMBERS IS OPEN QUESTION Q-0003", "question")
        self.bad("ASSUMPTION: DATUM A IS THE PLANE OF THE FOOT POST BOTTOM ENDS", "ASSUMPTION")
        self.bad("WHICH ARE NOT ONE PLANE ON THIS FRAME. FOR BOB'S REVIEW.", "name")
        self.bad("butt weld, tube to fitting (WPS per SAN-WELD-001 / ASME IX)", "design rule id")
        self.bad("LINE NUMBERS PER LINE-NUM-001", "design rule id")

    def test_old_footer_fails(self):
        self.bad("Doc ID CIP-TYP-SPL-001 | spool_drawing.py | model CIP-TYP-MDL-001-B Rev A | text-to-cad "
                 "engineering-drawing (cadgen 0.7.24) | ezdxf 1.4.5", "repo file name")
        self.bad("text-to-cad engineering-drawing (cadgen 0.7.24)", "software")

    def test_register_and_holds(self):
        self.bad("SOURCE: COMP-0062 E+H PROMAG", "component register")
        self.bad("CMP-0014 HANGER", "component register")
        self.bad("CUSTOMER SPEC (H5)", "hold")
        self.bad("SEE EC-03", "equipment concern")
        self.bad("RFI-0149", "question")

    def test_model_record_codes(self):
        self.bad("FIRST-PASS SECTION (A-19, A-45)", "internal record")
        self.bad("[GN-LASER, GN-A19]", "internal record")
        self.bad("FLUSH WITH THE TOP (SI-02, SH-06)", "internal record")
        self.good("SECTION A-A")
        self.good("TANK MODIFICATION ITEM M-14")

    def test_reviewer_request_01(self):
        self.bad("DRAWN FROM CIP-TYP-MDL-001-B REV A", "model number")
        self.bad("model Project-1072-01-MDL-001 Rev B", "model number")
        self.bad("(A-127)", "internal record")
        self.bad("McMaster 4322K153 304 SS clamp / McMaster 1100N15 EPDM gasket", "commodity maker")
        self.good("HX-101 SHELL AND TUBE HEAT EXCHANGER McMaster-Carr 35185K48")   # specified equipment keeps its maker
        for s in ("IN THE ROUTING REPORT", "PER THE LINE LIST", "THE LAYOUT NOTE", "COMPONENT REGISTER",
                  "AT ITS WELD-MAP POSITION", "AS THE MODEL WRITES THEM", "WELD CENTRE AS MODELLED", "(FILED MODEL)",
                  "CPME COMPONENTS PLACED WHOLE"):
            self.bad(s, "reports and lists")
        for s in ("PLACEHOLDER LEVELLING FOOT", "FIRST-PASS SECTIONS", "THE GAP IS ASSUMED", "STALE"):
            self.bad(s, "assumption wording")
        for s in ("HOLD (NOT RECEIVED)", "UNTIL GATE 3 IS APPROVED", "FOR ENGINEER'S REVIEW", "REV 1, FOR REVIEW",
                  "CARRIED FROM AN EARLIER JOB"):
            self.bad(s, "hold, gate")
        for s in ("AIR CARRIES NO SAN RULE", "CPM-41", "PARTSLIB"):
            self.bad(s, "rule family")
        self.good("THE MEMBER TABLE IS THE CUT LIST")
        self.good("WELD AND HOLD FOR INSPECTION")

    # --- second reviewer, DS-22 (2026-11-16) ---
    def test_ds22_question_and_hold_numbers(self):
        self.bad("OPEN QUESTION Q-10", "question")
        self.bad("SEE Q-0003", "question")
        self.bad("CUSTOMER SPEC H-19", "hold")
        self.good("W6X12 H-BEAM")
        self.good("H-BEAM BASE")

    def test_ds22_prr_and_calc_items(self):
        self.bad("PER PRR-04", "revision request")
        self.bad("WEIGHT FROM W-12", "calculation item")
        for s in ("W6X12 BEAM", "WELD W01", "L-100-SP03-W01", "FW-068", "W 6 X 12"):
            self.good(s)

    def test_ds22_columns_and_register(self):
        self.bad("WEIGHT: weight_basis", "column")
        self.bad("SIZE_IN 0.065", "column")
        self.bad("WEIGHT PER REGISTER", "register")
        self.bad("REGISTER DESCRIPTION", "register")
        self.bad("UNREGISTERED PART", "register")
        self.good("REGISTERED TRADEMARK")       # not "unregistered"

    def test_ds22_model_revision(self):
        self.bad("DRAWN FROM THE MODEL REV B", "model revision")
        self.bad("REV C MODEL", "model revision")
        self.bad("FROM BUILD revB-full-007", "model revision")
        for s in ("REV A", "REVISION", "A", "REV  DESCRIPTION  DATE", "FAST-001 - NOT ISSUED", "REV A, FIRST ISSUE"):
            self.good(s)

    def test_ds27_model_revision_in_words(self):
        for s in ("BRANCH DESIGN OPEN FOR THE NEXT MODEL REVISION", "AT THE NEXT REVISION", "MODEL REVISIONS",
                  "THE REVISION OF THE MODEL"):
            self.bad(s, "model revision")
        for s in ("REVISION", "REVISION BLOCK", "REVISIONS ARE CLOUDED", "MODEL NO. 12 PUMP"):
            self.good(s)

    def test_internal_words(self):
        for w in ("PER THE TAKEOFF", "FROM THE MANIFEST", "HELPER 3", "ORCHESTRATOR", "HARNESS RULE"):
            self.bad(w, "internal word")

    # --- what may print ---
    def test_public_standards_pass(self):
        for s in ("WELD ACCEPTANCE PER AWS D18.1.", "WPS PER ASME IX.", "TOLERANCES PER PFI ES-3.",
                  "HYGIENIC TUBE AND FITTINGS PER ASME BPE PART DT.", "DIMENSIONING PER ASME Y14.5-2018.",
                  "MATERIAL ASTM A270 S2 316L", "AWS D1.1/D1.1M STRUCTURAL WELDING"):
            self.good(s)

    def test_tags_lines_spools_pass(self):
        for s in ("PI-101", "TCV-101", "FM-001", "PS-040", "PL-004", "L-100-SP03", "L-100-SP03-W01", "HWS-201",
                  "STR-101", "J104", "TK-101 END ELEVATION", "OI-3", "SEE OPEN ITEM OI-2"):
            self.good(s)

    def test_drawing_numbers_pass(self):
        for s in ("SEE CIP-TYP-DET-001 DETAIL D3.", "CIP-TYP-FRM-001", "Project-1072-01-FRM-001",
                  "CIP-TYP-DS-TCV-101", "SET ON THE SKID PER Project-1072-01-ISO-001."):
            self.good(s)

    def test_tbd_passes(self):
        self.good("TBD COMMODITY; MANUFACTURER NOT SELECTED")
        self.good("GASKET CURE TBD; CONFIRM AT PURCHASE")

    def test_own_footer_passes(self):
        self.good("job/Typical-CIP-TYP/03_Working_Design/Exports/Fast_Drawings/CIP-TYP-SPL-001/"
                  "CIP-TYP-SPL-001-revA-fast-001/CIP-TYP-SPL-001-revA-fast-001.dxf")
        self.good("job/Project-1072-01-CIP-001/06_Issued_Revisions/Drawings/Project-1072-01-SPL-001/"
                  "Project-1072-01-SPL-001-revA/Project-1072-01-SPL-001-revA.dwg")
        # but not a script path dressed as a footer
        self.bad("job/Typical-CIP-TYP/03_Working_Design/CAD/06_Drawings/Generators/piping/spool_drawing.py",
                 "repo")

    def test_words_inside_others_pass(self):
        self.good("BRIEFLY HOLD TACKS")       # not the word "brief"
        self.good("H2O")                      # not a hold number


class CheckDxfTests(unittest.TestCase):
    def test_dxf_round_trip(self):
        import ezdxf
        doc = ezdxf.new()
        msp = doc.modelspace()
        msp.add_text("WPS PER ASME IX", dxfattribs={"insert": (10, 10)})
        msp.add_text("FINISH (SAN-RA-001)", dxfattribs={"insert": (10, 20)})
        msp.add_mtext("NOTE (TR-24)\\PSECOND LINE", dxfattribs={"insert": (10, 30)})
        blk = doc.blocks.new("TB")
        blk.add_text("model CIP-TYP-MDL-001-B | ezdxf 1.4.5", dxfattribs={"insert": (0, 0)})
        msp.add_blockref("TB", (0, 0))
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "t.dxf"
            doc.saveas(p)
            f = sf.check_dxf(p)
            reasons = " ".join(x.reason for x in f)
            self.assertIn("SAN-RA-001", reasons)
            self.assertIn("TR-24", reasons)
            self.assertIn("software", reasons)
            self.assertNotIn("ASME IX", reasons)
            self.assertEqual(sf.main([str(p)]), 1)
            clean = ezdxf.new()
            clean.modelspace().add_text("WPS PER ASME IX", dxfattribs={"insert": (0, 0)})
            q = Path(td) / "c.dxf"
            clean.saveas(q)
            self.assertEqual(sf.main([str(q)]), 0)

    def test_missing_path_is_error(self):
        self.assertEqual(sf.main(["no/such/file.dxf"]), 3)

    def test_no_args_never_errors(self):
        # CI runs every check with no arguments: newest fast drawings only, or a PASS when there are none
        self.assertIn(sf.main([]), (0, 1))


if __name__ == "__main__":
    unittest.main()
