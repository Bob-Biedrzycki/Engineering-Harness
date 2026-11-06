"""Unit tests of harness/checks/gdt.py (GDT-* rules, harness/design-rules/tolerancing.yaml)."""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists())
spec = importlib.util.spec_from_file_location("gdt", ROOT / "harness" / "checks" / "gdt.py")
gdt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gdt)


def rec(*fcf, datums=None):
    return {"document_id": "TEST-001", "kind": "fabrication",
            "datums": datums if datums is not None else {"A": "base plane", "B": "side rail", "C": "end rail"},
            "fcf": list(fcf)}


GOOD_FLAT = {"feature": "pad", "control": "flatness", "value_in": 0.01, "datums": [], "reason": "soft foot"}


class GdtTests(unittest.TestCase):
    def test_good_record_has_no_findings(self):
        pos = {"feature": "4x holes", "control": "position", "value_in": 0.06, "modifier": "MMC",
               "datums": ["A", "B", "C"], "reason": "bolted to pump base",
               "fastener": {"type": "floating", "hole_mmc_in": 0.5625, "fastener_mmc_in": 0.5}}
        self.assertEqual(gdt.check_record(rec(GOOD_FLAT, pos), {}), [])

    def test_concentricity_not_used(self):
        f = gdt.check_record(rec({**GOOD_FLAT, "control": "concentricity"}), {})
        self.assertTrue(any("removed from ASME Y14.5-2018" in x for x in f))

    def test_undefined_datum(self):
        f = gdt.check_record(rec({**GOOD_FLAT, "control": "perpendicularity", "datums": ["D"]}), {})
        self.assertTrue(any("datum D is not defined" in x for x in f))

    def test_form_control_with_datum(self):
        f = gdt.check_record(rec({**GOOD_FLAT, "datums": ["A"]}), {})
        self.assertTrue(any("takes no datums" in x for x in f))

    def test_position_needs_datum_and_reason(self):
        f = gdt.check_record(rec({"feature": "h", "control": "position", "value_in": 0.03, "modifier": "MMC"}), {})
        self.assertTrue(any("needs at least one datum" in x for x in f))
        self.assertTrue(any("no reason" in x for x in f))

    def test_tighter_than_shop(self):
        f = gdt.check_record(rec({**GOOD_FLAT, "process": "laser_cut_profile_in"}), {"laser_cut_profile_in": 0.02})
        self.assertTrue(any("tighter than the shop" in x for x in f))

    def test_unknown_capability_is_not_a_finding(self):
        self.assertEqual(gdt.check_record(rec({**GOOD_FLAT, "process": "laser_cut_profile_in"}),
                                          {"laser_cut_profile_in": "unknown"}), [])

    def test_fastener_formula(self):
        pos = {"feature": "holes", "control": "position", "value_in": 0.08, "modifier": "MMC", "datums": ["A"],
               "reason": "r", "fastener": {"type": "floating", "hole_mmc_in": 0.5625, "fastener_mmc_in": 0.5}}
        self.assertTrue(any("fastener formula" in x for x in gdt.check_record(rec(pos), {})))

    def test_runout_only_machined(self):
        f = gdt.check_record(rec({**GOOD_FLAT, "control": "total_runout", "datums": ["A"]}), {})
        self.assertTrue(any("machined" in x for x in f))


if __name__ == "__main__":
    unittest.main()
