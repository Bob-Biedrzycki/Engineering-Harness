"""A P&ID tag finds its part's weight through the component_id column of the tag lists (Bob, chat, 2026-10-26).

    .\\harness\\tools\\venv\\Scripts\\python.exe -m unittest harness.tests.test_component_tag_link -v
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO = next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists())
sys.path[:0] = [str(REPO / "harness" / "lib"), str(REPO / "harness" / "checks")]
import components  # noqa: E402
import pipe_supports as P  # noqa: E402


class TagLink(unittest.TestCase):
    def test_tag_takes_its_component_weight(self):
        d = Path(tempfile.mkdtemp())
        (d / "valve-list.csv").write_text("tag,component_id,type\nXV-901,COMP-0007,butterfly\nXV-902,,ball\n",
                                          encoding="utf-8")
        lib = d / "lib"
        lib.mkdir()
        hdr = (REPO / "job" / "components" / "component-register.csv").read_text(encoding="utf-8").splitlines()[0]
        cols = hdr.split(",")
        row = dict.fromkeys(cols, "")
        row.update(component_id="COMP-0007", revision="A", status="current", weight_lb="9.5")
        (lib / "component-register.csv").write_text(hdr + "\n" + ",".join(row[c] for c in cols) + "\n",
                                                   encoding="utf-8")
        w = P.recorded_weights(d, [components.Library("job", lib, lib / "component-register.csv")])
        self.assertEqual(w["COMP-0007"][0], 9.5)
        self.assertEqual(w["XV-901"][0], 9.5)
        self.assertIn("via valve-list.csv component_id", w["XV-901"][1])
        self.assertNotIn("XV-902", w)   # no component picked: no weight assumed


if __name__ == "__main__":
    unittest.main()
