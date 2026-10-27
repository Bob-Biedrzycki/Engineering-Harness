"""Unit tests for harness/lib/rule_scope.py (CPME practice: rule layouts, the three levels, PIPE-SVC-001 scope, spool naming) and
harness/checks/tag_crosscheck.py (list-level tag cross-check). Synthetic tags and lines only. Stdlib unittest:

    .\\harness\\tools\\venv\\Scripts\\python.exe -m unittest discover -s harness\\tests -v
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO = next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists())
sys.path.insert(0, str(REPO / "harness" / "lib"))
sys.path.insert(0, str(REPO / "harness" / "checks"))
import rule_scope as RS  # noqa: E402
import tag_crosscheck as TC  # noqa: E402


class SpoolNaming(unittest.TestCase):
    """CLAUDE.md: spools are <LINE>-SP<nn> with LINE exactly as on the P&ID (e.g. CS-201-SP03)."""

    def test_any_line_number(self):
        self.assertTrue(RS.spool_id_ok("CS-201-SP03", "CS-201"))
        self.assertTrue(RS.spool_id_ok("HW-1-2in-SP01", "HW-1-2in"))
        self.assertTrue(RS.spool_id_ok("L-100-SP11", "L-100"))
        self.assertFalse(RS.spool_id_ok("CS-201-SP3", "CS-201"))           # two digits
        self.assertFalse(RS.spool_id_ok("CS-202-SP03", "CS-201"))          # another line
        self.assertFalse(RS.spool_id_ok("CS-201-SP03", "CS-201", {"CS-202"}))   # line not on the list
        self.assertFalse(RS.spool_id_ok("CS-201-SP03", ""))

    def test_spool_line_longest_match(self):
        self.assertEqual(RS.spool_line("ST-1-A-SP02", {"ST-1", "ST-1-A"}), "ST-1-A")
        self.assertIsNone(RS.spool_line("X-SP01", {"ST-1"}))


class RuleLayouts(unittest.TestCase):
    def test_find_rule_in_both_layouts(self):
        project = {"meta": {}, "SAN-DL-002": {"rule_ref": "SAN-DL-002", "applies_to": "unknown"}}
        harness_list = {"dead_leg": [{"id": "SAN-DL-001"}, {"id": "SAN-DL-002", "max_L": "D - d"}]}
        harness_map = {"straight_run": {"flow_meter_upstream_D": None, "INST-SR-001": {"rule": "x"}}}
        self.assertEqual(RS.find_rule(project, "SAN-DL-002")["applies_to"], "unknown")
        self.assertEqual(RS.find_rule(harness_list, "SAN-DL-002")["max_L"], "D - d")
        self.assertEqual(RS.find_rule(harness_map, "INST-SR-001"), {"rule": "x"})
        self.assertIsNone(RS.find_rule(project, "STR-PS-002"))
        self.assertIsNone(RS.find_rule(None, "STR-PS-002"))
        one_rule_section = {"meta": {}, "service_classes": {"id": "PIPE-SVC-001", "classes": {}}}
        self.assertEqual(RS.find_rule(one_rule_section, "PIPE-SVC-001")["classes"], {})


class ThreeLevels(unittest.TestCase):
    """harness -> job -> project: each lower level narrows the one above it (CLAUDE.md hard rule 11)."""

    def test_values_merge_in_order(self):
        h = {"id": "X-001", "max_in": 10, "by_od": {"2.0": 1, "3.0": 2}, "applies_to": "2.0 in OD tube"}
        j = {"rule_ref": "X-001", "max_in": 8, "by_od": {"3.0": 3}, "applies_to": ["hygienic", "steam"]}
        p = {"rule_ref": "X-001", "by_od": {"2.0": 4}, "applies_to": ["steam", "air"]}
        m = RS.merge_entries(h, j, p)
        self.assertEqual(m["max_in"], 8)                                  # job over harness
        self.assertEqual(m["by_od"], {"2.0": 4, "3.0": 3})                # nested mapping merged key by key
        self.assertEqual(m["applies_to"], ["steam"])                      # project narrows the job's classes
        self.assertEqual(m["id"], "X-001")
        self.assertEqual(h["by_od"], {"2.0": 1, "3.0": 2})                # inputs untouched

    def test_harness_applies_to_is_not_a_scope(self):
        self.assertNotIn("applies_to", RS.merge_entries({"applies_to": "2.0 in OD tube"}, None, None))
        self.assertIsNone(RS.merge_entries(None, None, None))

    def test_narrowing(self):
        self.assertIsNone(RS.narrow_applies_to(None, {"x": 1}))           # nobody states a scope
        self.assertEqual(RS.narrow_applies_to({"applies_to": "steam, condensate"}, None), ["condensate", "steam"])
        self.assertEqual(RS.narrow_applies_to({"applies_to": ["steam"]}, {"applies_to": "unknown"}), RS.UNKNOWN)
        self.assertEqual(RS.narrow_applies_to({"applies_to": "unknown"}, {"applies_to": ["air"]}), ["air"])
        self.assertEqual(RS.narrow_applies_to({"applies_to": ["steam"]}, {"applies_to": ["air"]}), [])
        self.assertIsNone(RS.scope_classes("X-001", {"applies_to": []})[0])   # narrowed to nothing: not checked

    def test_merged_rule_reads_three_folders(self):
        with tempfile.TemporaryDirectory() as d:
            h, j, p = (Path(d) / n for n in ("h", "j", "p"))
            for x in (h, j, p):
                x.mkdir()
            (h / "r.yaml").write_text("sec:\n  - {id: X-001, max_in: 10, rule: harness text}\n", encoding="utf-8")
            (j / "r.yaml").write_text("X-001: {rule_ref: X-001, max_in: 8, applies_to: [hygienic, steam]}\n",
                                      encoding="utf-8")
            (p / "r.yaml").write_text("X-001: {rule_ref: X-001, applies_to: [steam]}\n", encoding="utf-8")
            m = RS.merged_rule("r.yaml", "X-001", h, j, p)
            self.assertEqual((m["rule"], m["max_in"], m["applies_to"]), ("harness text", 8, ["steam"]))
            (p / "r.yaml").write_text("", encoding="utf-8")              # no project entry: the job's scope
            self.assertEqual(RS.merged_rule("r.yaml", "X-001", h, j, p)["applies_to"], ["hygienic", "steam"])
            self.assertIsNone(RS.merged_rule("missing.yaml", "X-001", h, j, p))

    def test_class_rules_harness_then_job(self):
        with tempfile.TemporaryDirectory() as d:
            h, j = Path(d) / "h", Path(d) / "j"
            h.mkdir()
            j.mkdir()
            (h / "piping.yaml").write_text(
                "service_classes:\n  id: PIPE-SVC-001\n  classes:\n    hygienic: {rules: [SAN-DL-001, TR-20]}\n"
                "    utility-water: {rules: 'SAN-DRAIN-001 (drains) and PIPE-CV-001; others where specified'}\n"
                "    steam: {rules: [SAN-PIPE-001]}\n", encoding="utf-8")
            (j / "piping.yaml").write_text(
                "PIPE-SVC-001:\n  rule_ref: PIPE-SVC-001\n  job_rules_by_class:\n    steam: [JOB-A-001, SAN-PIPE-001]\n"
                "    utility-water: [JOB-B-001]\n", encoding="utf-8")
            self.assertEqual(RS.class_rules("steam", h, j), ["SAN-PIPE-001", "JOB-A-001"])
            self.assertEqual(RS.class_rules("utility-water", h, j), ["SAN-DRAIN-001", "PIPE-CV-001", "JOB-B-001"])
            self.assertEqual(RS.class_rules("hygienic", h, j), ["SAN-DL-001", "TR-20"])
            self.assertEqual(RS.class_rules("air", h, j), [])

    def test_real_rule_files_read(self):
        """This repo's own three levels load (whatever the job holds)."""
        self.assertIn("SAN-PIPE-001", RS.class_rules("steam"))


class ServiceClassScope(unittest.TestCase):
    def test_applies_to(self):
        self.assertIsNone(RS.applies_to_classes({"applies_to": "unknown"}))
        self.assertIsNone(RS.applies_to_classes({"applies_to": "unknown until the intake"}))
        self.assertIsNone(RS.applies_to_classes(None))
        self.assertEqual(RS.applies_to_classes({"applies_to": ["Hygienic", "steam"]}), {"hygienic", "steam"})
        self.assertEqual(RS.applies_to_classes({"applies_to": "hygienic, utility-water"}), {"hygienic", "utility-water"})

    def test_hygienic_rules_never_leave_their_classes(self):
        self.assertEqual(RS.scope_classes("STR-PS-002", {"applies_to": ["steam", "hygienic"]})[0], {"hygienic"})
        cls, note = RS.scope_classes("SAN-RA-001", {"applies_to": ["condensate"]})
        self.assertIsNone(cls)
        self.assertIn("condensate ignored", note)
        self.assertEqual(RS.scope_classes("INST-SR-001", {"applies_to": ["steam"]})[0], {"steam"})   # not a SAN rule

    def test_lines_in_scope(self):
        by_line = {"W-1": "hygienic", "W-2": "utility-water", "S-1": "steam", "X-1": "unknown"}
        lines, notes = RS.lines_in_scope("STR-PS-002", {"applies_to": ["hygienic"]}, by_line)
        self.assertEqual(lines, {"W-1"})
        self.assertTrue(any("X-1" in n for n in notes))
        self.assertEqual(RS.lines_in_scope("STR-PS-002", {"applies_to": "unknown"}, by_line)[0], None)

    def test_line_classes_reads_the_column(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "line-list.csv"
            p.write_text("line_no,service_class,size_od_in\nW-1,Hygienic,2.0\nS-1,,1.5\n", encoding="utf-8")
            self.assertEqual(RS.line_classes(p), {"W-1": "hygienic", "S-1": "unknown"})


class TagCrosscheck(unittest.TestCase):
    def lists(self, d: Path, **files: str) -> Path:
        base = {"equipment-list.csv": "tag,description\nHX-901,exchanger\n",
                "valve-list.csv": "tag,type,line_no\nXV-901,ball,W-901\n",
                "instrument-list.csv": "tag,type,line_no_or_equip\nTT-901,temp,W-901\nPT-901,press,HX-901\n",
                "tie-in-list.csv": "tag,service\nTI-901,supply\n",
                "line-list.csv": "line_no,service_class\nW-901,hygienic\nS-901,\n"}
        base.update({k.replace("_", "-") + ".csv": v for k, v in files.items()})
        for n, t in base.items():
            (d / n).write_text(t, encoding="utf-8")
        return d

    def test_clean_lists_pass_with_class_info(self):
        with tempfile.TemporaryDirectory() as d:
            fails, info, n = TC.evaluate(self.lists(Path(d)))
        self.assertEqual(fails, [])
        self.assertEqual(n, 5)
        self.assertTrue(any("S-901" in i for i in info))

    def test_duplicates_and_dangling_references_fail(self):
        with tempfile.TemporaryDirectory() as d:
            fails, _, _ = TC.evaluate(self.lists(
                Path(d), valve_list="tag,type,line_no\nXV-901,ball,W-999\nTT-901,ball,unknown\n",
                instrument_list="tag,type,line_no_or_equip\nTT-901,temp,TK-999\n"))
        text = " | ".join(fails)
        self.assertIn("tag TT-901 appears 2 times", text)
        self.assertIn("line_no W-999 is not on line-list.csv", text)
        self.assertIn("TK-999 is neither a line nor an equipment tag", text)


if __name__ == "__main__":
    unittest.main()
