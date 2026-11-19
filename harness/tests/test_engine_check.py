"""engine_check.py: the pin is read from the requirements file, and the comparisons report a real difference and
stay quiet on numerical noise. No engine is installed or run here."""
import copy
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists())
sys.path.insert(0, str(ROOT / "harness" / "scripts"))
import engine_check as E  # noqa: E402

SOLID = {"volume": 1000.0, "area": 600.0, "bbox": [0, 0, 0, 10, 10, 10], "faces": 6, "edges": 12,
         "step_entities": 300, "step_volume": 1000.0}
VIEW = {"c": [1.0, 2.0], "m": [[1, 0], [0, 0], [0, 1]], "bounds": [0, 10, 0, 10], "visible": 4, "hidden": 0,
        "visible_length": 40.0, "hidden_length": 0.0}
PROBE = {"api": {"cad.step.read": True, "cad.eng_drawing._Projection": True}, "errors": [],
         "solids": {"box": SOLID}, "views": {"box-top": VIEW}}


class Pin(unittest.TestCase):
    def test_pins_reads_name_version_lines_only(self):
        p = E.pins("# cad==9.9.9 in a comment\nbuild123d==0.13.0\ncad==0.11.12\ncadquery-ocp-novtk==8.0.1.1.0\n")
        self.assertEqual(p["cad"], "0.11.12")
        self.assertEqual(p["cadquery-ocp-novtk"], "8.0.1.1.0")

    def test_version_order_is_numeric(self):
        self.assertGreater(E.vkey("0.11.13"), E.vkey("0.11.9"))
        self.assertGreater(E.vkey("0.12.0"), E.vkey("0.11.13"))

    def test_this_repo_names_one_engine_pin(self):
        self.assertIsNotNone(E.pinned(), "harness/requirements-cad.txt has no cad== line")


class Probe(unittest.TestCase):
    def test_same_probe_has_no_difference(self):
        self.assertEqual(E.compare_probe(PROBE, copy.deepcopy(PROBE)), [])

    def test_noise_below_tolerance_is_quiet(self):
        b = copy.deepcopy(PROBE)
        b["solids"]["box"]["volume"] += 1e-7
        b["views"]["box-top"]["bounds"][1] += 1e-5
        self.assertEqual(E.compare_probe(PROBE, b), [])

    def test_a_renamed_engine_name_is_reported(self):
        b = copy.deepcopy(PROBE)
        b["api"]["cad.eng_drawing._Projection"] = False
        self.assertIn("engine name gone: cad.eng_drawing._Projection (missing)", E.compare_probe(PROBE, b))

    def test_a_changed_solid_and_view_are_reported(self):
        b = copy.deepcopy(PROBE)
        b["solids"]["box"]["volume"] = 1001.0
        b["solids"]["box"]["faces"] = 7
        b["views"]["box-top"]["visible_length"] = 44.0
        d = "\n".join(E.compare_probe(PROBE, b))
        self.assertIn("solid box: volume", d)
        self.assertIn("solid box: faces 6 then, 7 now", d)
        self.assertIn("view box-top: visible linework", d)

    def test_a_missing_solid_and_a_new_error_are_reported(self):
        b = copy.deepcopy(PROBE)
        del b["solids"]["box"]
        b["errors"].append("box: ValueError: x")
        d = E.compare_probe(PROBE, b)
        self.assertIn("solid box: not built on the candidate", d)
        self.assertIn("probe error on the candidate: box: ValueError: x", d)


class Views(unittest.TestCase):
    CACHED = {"proj": {"c": [0.0, 0.0], "m": [[1, 0], [0, 0], [0, 1]]}, "bounds": [0, 10, 0, 10],
              "visible": [["L", 0, 0, 10, 0], ["P", [[0, 0], [0, 10], [10, 10]]], ["C", 5, 5, 1], ["A", 5, 5, 2, 0, 90]],
              "hidden": [], "cuts": [{"outer": [[0, 0], [4, 0], [4, 4], [0, 4]], "inner": [[[1, 1], [2, 1], [2, 2], [1, 2]]]}]}

    def test_cached_view_numbers(self):
        n = E.view_numbers(self.CACHED)
        self.assertEqual(n["visible"], 4)
        self.assertAlmostEqual(n["visible_length"], 10 + 20 + 2 * 3.141592653589793 + 3.141592653589793)
        self.assertAlmostEqual(n["cut_area"], 15.0)

    def test_split_linework_of_the_same_length_is_quiet(self):
        b = copy.deepcopy(self.CACHED)
        b["visible"][0:1] = [["L", 0, 0, 4, 0], ["L", 4, 0, 10, 0]]
        self.assertEqual(E.compare_view(self.CACHED, b), [])

    def test_a_moved_view_and_a_changed_cut_are_reported(self):
        b = copy.deepcopy(self.CACHED)
        b["proj"]["c"] = [0.5, 0.0]
        b["cuts"][0]["inner"] = []
        d = "\n".join(E.compare_view(self.CACHED, b))
        self.assertIn("the view origin moved", d)
        self.assertIn("section cut area 15.00 then, 16.00 now", d)


class Glb(unittest.TestCase):
    def glb(self, folder: Path, name: str, count: int) -> Path:
        g = {"nodes": [{"name": "FM-001"}, {"name": "TK-101"}], "meshes": [{"primitives": [{"attributes": {"POSITION": 0}}]}],
             "accessors": [{"count": count, "min": [0, 0, 0], "max": [1, 2, 3]}]}
        js = json.dumps(g).encode()
        js += b" " * (-len(js) % 4)
        f = folder / name
        f.write_bytes(b"glTF" + struct.pack("<II", 2, 20 + len(js)) + struct.pack("<I", len(js)) + b"JSON" + js)
        return f

    def test_glb_numbers_and_comparison(self):
        with tempfile.TemporaryDirectory() as td:
            a = E.glb_numbers(self.glb(Path(td), "a.glb", 1000))
            b = E.glb_numbers(self.glb(Path(td), "b.glb", 1005))
            c = E.glb_numbers(self.glb(Path(td), "c.glb", 1200))
        self.assertEqual((a["nodes"], a["meshes"], a["vertices"], a["max"]), (2, 1, 1000, [1, 2, 3]))
        self.assertEqual(E.compare_glb(a, b), [])
        self.assertEqual(E.compare_glb(a, c), ["mesh vertices 1000 then, 1200 now"])


if __name__ == "__main__":
    unittest.main()
