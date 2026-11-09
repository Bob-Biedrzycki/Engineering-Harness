"""The construction materials list (harness/design-rules/materials.yaml) and its reader (harness/lib/materials.py):
MAT-LIB-001, MAT-FORM-001, MAT-LOOK-001.

    .\\harness\\tools\\venv\\Scripts\\python.exe -m unittest harness.tests.test_materials -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists())
sys.path.insert(0, str(REPO / "harness" / "lib"))
import materials as mat  # noqa: E402

# material text exactly as the lists, rules and models in the harness and its jobs write it -> the entry expected
WRITTEN = {
    "ASTM A270 S2 316L": "ss-sanitary-tube",
    "ASTM A312 TP316L": "ss-pipe",
    "ASTM A106 Gr B": "cs-pipe",
    "A106 Gr B TBE": "cs-pipe",
    "ASTM A53 Gr B": "cs-pipe",
    "ASTM A234 WPB": "cs-bw-fitting",
    "ASTM A105": "cs-forged",
    "ASTM A500 Gr C": "cs-hss",
    "ASTM A36": "cs-shape",
    "ASTM A992": "cs-wide-flange",
    "ASTM A554 304 square tube": "ss-structural-tube",
    "ASTM A240 304": "ss-plate",
}


class TestMaterialsList(unittest.TestCase):
    def test_file_has_no_faults(self):
        self.assertEqual(mat.problems(), [])

    def test_written_materials_resolve(self):
        for text, key in WRITTEN.items():
            e = mat.resolve(text)
            self.assertIsNotNone(e, text)
            self.assertEqual(e["key"], key, text)

    def test_a53_does_not_swallow_other_specs(self):
        self.assertIsNone(mat.resolve("ASTM A536x"))
        self.assertEqual(mat.resolve("ASTM A536")["key"], "cast-iron")

    def test_unknown_material_is_none_and_shows_as_unknown(self):
        for text in ("", None, "unknown", "unobtainium"):
            self.assertIsNone(mat.resolve(text))
            self.assertEqual(mat.look_name(text), mat.UNKNOWN_LOOK)

    def test_pipe_tube_and_frame_members_are_never_bent(self):
        for key in ("ss-pipe", "ss-sanitary-tube", "cs-pipe", "cs-hss", "ss-structural-tube", "cs-wide-flange"):
            self.assertFalse(mat.may_bend(key), key)
        for key in ("ss-pipe", "ss-sanitary-tube", "cs-pipe"):
            self.assertEqual(mat.turn(key), "fitting", key)
            self.assertTrue(mat.get(key)["make"].get("fittings"), key)

    def test_plate_may_be_formed_with_stated_limits(self):
        for key in ("ss-plate", "cs-shape"):
            self.assertTrue(mat.may_bend(key), key)
            self.assertIn("unknown", mat.get(key)["make"]["bend_limits"])

    def test_looks(self):
        ss = mat.look("ASTM A312 TP304L")
        self.assertEqual(ss["metallic"], 1.0)
        self.assertNotEqual(mat.look("ASTM A106 Gr B"), ss)
        self.assertEqual(mat.look("ASTM A500 Gr C", "galvanized"), mat.load()["looks"]["galvanized"])
        self.assertEqual(mat.look("ASTM A500 Gr C", "no such finish"), mat.load()["looks"]["paint_frame"])
        ss["metallic"] = 0.0                                    # a copy: the list is not changed
        self.assertEqual(mat.look("ASTM A312 TP304L")["metallic"], 1.0)

    def test_audit_reports_a_bent_stainless_pipe_and_an_unlisted_material(self):
        found = mat.audit([
            {"id": "HWS-201-SP01.pc02", "kind": "bend", "material": "ASTM A312 TP316L"},
            {"id": "HWS-201-SP01.pc03", "kind": "elbow", "material": "ASTM A312 TP316L"},
            {"id": "PL-003", "kind": "bend", "material": "ASTM A240 304"},
            {"id": "FM-001", "kind": "frame", "material": "mystery steel"},
        ])
        self.assertEqual([(f["id"], f["rule"]) for f in found],
                         [("HWS-201-SP01.pc02", "MAT-FORM-001"), ("FM-001", "MAT-LIB-001")])
        self.assertIn("B16.9", found[0]["finding"])

    def test_structural_keys_exist_in_the_frame_suite(self):
        sys.path.insert(0, str(REPO / "harness" / "structural-models"))
        from skidframe.materials import MATERIALS
        for e in mat.entries():
            if e.get("structural_key"):
                self.assertIn(e["structural_key"], MATERIALS, e["key"])

    def test_model_records_take_pieces_and_members_not_purchased_parts(self):
        from types import SimpleNamespace as NS
        sp = NS(sid="SS-101-SP01", material="ASTM A106 Gr B",
                pieces=[NS(pid="SS-101-SP01.pc01", sid="SS-101-SP01", kind="tube", material=""),
                        NS(pid="SS-101-SP01.pc02", sid="SS-101-SP01", kind="elbow", material="ASTM A106 Gr B")])
        items = {"FM-001": NS(key="FM-001", kind="frame", prims=[1], member={"material": "ASTM A500 Gr C"}),
                 "PL-001": NS(key="PL-001", kind="plate", prims=[1], member={}),
                 "HV-101": NS(key="HV-101", kind="valve", prims=[1], member={})}
        m = NS(spools=[sp], items=items, pieces=lambda: iter(sp.pieces))
        recs = mat.model_records(m)
        self.assertEqual([r["id"] for r in recs], ["SS-101-SP01.pc01", "SS-101-SP01.pc02", "FM-001", "PL-001"])
        self.assertEqual(recs[0]["material"], "ASTM A106 Gr B")          # a piece with none takes its spool's
        self.assertEqual([f["id"] for f in mat.audit(recs)], ["PL-001"])  # a plate with no material is reported

    def test_dump_for_render_scripts(self):
        d = mat.dump_looks()
        self.assertEqual(len(d["materials"]), len(mat.entries()))
        self.assertIn(mat.UNKNOWN_LOOK, d["looks"])


if __name__ == "__main__":
    unittest.main()
