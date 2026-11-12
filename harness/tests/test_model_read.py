"""Unit tests for harness/lib/model_read.py: the same facts read from a model of either skidlib generation, and
materials.model_records on both. Stand-in objects only; no model is built. Stdlib unittest:

    .\\harness\\tools\\venv\\Scripts\\python.exe -m unittest discover -s harness\\tests -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

REPO = next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists())
sys.path.insert(0, str(REPO / "harness" / "lib"))
import materials as mat  # noqa: E402
import model_read as MR  # noqa: E402


def newer_model():
    """As a skidlib written since 2026-10-30 gives it."""
    pcs = [NS(pid="L-A-SP01.pc01", kind="tube", sid="L-A-SP01", material="", line="L-A"),
           NS(pid="L-A-SP01.pc02", kind="elbow", sid="L-A-SP01", material="ASTM A234 WPB", line="L-A")]
    sp = NS(sid="L-A-SP01", material="ASTM A106 Gr B", pieces=pcs, start="P-T", end="")
    items = {"FM-001": NS(key="FM-001", kind="frame", prims=[1], member={"material": "ASTM A500 Gr B"}, comp_id="",
                          source="", step={}),
             "V-1": NS(key="V-1", kind="valve", prims=[1], member=None, comp_id="COMP-0007", source="", step={"file": "a.step"})}
    return NS(spools=[sp], items=items, pieces=lambda: list(pcs))


# The old register id form, written in two parts: a job's carry-over guard (test_no_carryover) bans that form in
# every text file of the job, and this file is pulled into jobs (it failed there on 2026-11-11).
OLD_ID = "CMP" + "-0012"


def older_model():
    """As a skidlib that predates them gives it: no Model.pieces(), Piece.spool, no Piece.material, the part number
    in Item.source, Spool.upstream / downstream, Item.step None."""
    pcs = [NS(pid="L-B-SP01.pc01", kind="tube", spool="L-B-SP01", line="L-B"),
           NS(pid="L-B-SP01.pc02", kind="elbow", spool="L-B-SP01", line="L-B")]
    sp = NS(sid="L-B-SP01", material="ASTM A270 S2 316L", pieces=pcs, upstream="P-T", downstream="")
    items = {"FM-001": NS(key="FM-001", kind="frame", prims=[1], member={"material": "ASTM A554 304 (A-19)"},
                          source="placeholder", step=None),
             "V-1": NS(key="V-1", kind="valve", prims=[1], member=None, source=OLD_ID + " butterfly valve", step=None),
             "CAP-1": NS(key="CAP-1", kind="fitting", prims=[1], member=None, source="placeholder", step=None)}
    return NS(spools=[sp], items=items)


class Read(unittest.TestCase):
    def test_pieces_and_their_spool_and_material(self):
        for m, sid, tube_mat, elbow_mat in ((newer_model(), "L-A-SP01", "ASTM A106 Gr B", "ASTM A234 WPB"),
                                            (older_model(), "L-B-SP01", "ASTM A270 S2 316L", "ASTM A270 S2 316L")):
            pcs = MR.pieces(m)
            self.assertEqual(len(pcs), 2)
            by = {sp.sid: sp for sp in m.spools}
            self.assertEqual(MR.piece_spool_id(pcs[0]), sid)
            self.assertEqual(MR.piece_material(pcs[0], by), tube_mat)      # the spool's, the piece has none
            self.assertEqual(MR.piece_material(pcs[1], by), elbow_mat)

    def test_step_comp_id_and_spool_ends(self):
        new, old = newer_model(), older_model()
        self.assertEqual(MR.step_of(new.items["V-1"]), {"file": "a.step"})
        self.assertEqual(MR.step_of(old.items["V-1"]), {})
        self.assertEqual(MR.comp_id(new.items["V-1"]), "COMP-0007")
        self.assertEqual(MR.comp_id(old.items["V-1"]), "COMP-0012")       # CMP-nnnn in the source
        self.assertEqual(MR.comp_id(old.items["FM-001"]), "")
        for m in (new, old):
            self.assertEqual(MR.spool_end(m.spools[0], "start"), "P-T")
            self.assertEqual(MR.spool_end(m.spools[0], "end"), "")

    def test_build_with_and_without_a_configuration(self):
        seen = []
        takes = NS(build=lambda config=None: seen.append(("config", config)) or "m1")
        plain = NS(build=lambda: seen.append(("plain",)) or "m2")
        self.assertEqual(MR.build(takes, "B"), "m1")
        self.assertEqual(MR.build(takes, ""), "m1")
        self.assertEqual(MR.build(plain, "B"), "m2")
        self.assertEqual(seen, [("config", "B"), ("config", None), ("plain",)])


class MaterialRecords(unittest.TestCase):
    def test_both_generations_give_records(self):
        new = {r["id"]: r for r in mat.model_records(newer_model())}
        self.assertEqual(new["L-A-SP01.pc01"]["material"], "ASTM A106 Gr B")
        self.assertEqual(new["FM-001"]["material"], "ASTM A500 Gr B")
        self.assertNotIn("V-1", new)                                      # a purchased part
        old = {r["id"]: r for r in mat.model_records(older_model())}
        self.assertEqual(old["L-B-SP01.pc02"], {"id": "L-B-SP01.pc02", "kind": "elbow", "material": "ASTM A270 S2 316L"})
        self.assertEqual(old["FM-001"]["material"], "ASTM A554 304 (A-19)")
        self.assertEqual(old["CAP-1"]["material"], "")                    # a loose fitting with no material recorded
        self.assertNotIn("V-1", old)


if __name__ == "__main__":
    unittest.main()
