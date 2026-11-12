"""cpme_titleblock sheet helpers: content centred in the frame, the gap between stacked sections, and the
number cell's label as a field (Bob, chat, 2026-10-21: "Drawing centred in the frame & legend spacing")."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists())
sys.path.insert(0, str(REPO / "harness" / "cad-lib"))
sys.path.insert(0, str(REPO / "harness" / "lib"))

import ezdxf  # noqa: E402
from ezdxf import bbox  # noqa: E402

import repo_paths as rp  # noqa: E402

# The sheet format reads the project's identity when it is imported, so these run in a job that has a project
# (every job after its first pull) and are skipped in a folder with none, such as the master.
if not rp.HAS_PROJECT:
    raise unittest.SkipTest("no project yet: the sheet format needs a project's identity")

import cpme_titleblock as tb  # noqa: E402

W, H = 1700.0, 1100.0


class _Sheet:
    def __init__(self):
        self.texts = []
        self.text_boxes = [((0.0, 0.0, 10.0, 10.0), "t")]
        self.edges = [((0.0, 0.0), (10.0, 0.0), "o")]
        self.obst = [((0.0, 0.0, 10.0, 10.0), "o")]

    def text(self, s, x, y, cap, layer, align, bold=False, rgb=None):
        self.texts.append(s)

    def pline(self, pts, layer, close=False, owner=None):
        pass


class Helpers(unittest.TestCase):
    def test_section_gap_is_the_same_on_paper_at_any_unit(self):
        self.assertAlmostEqual(tb.section_gap(), tb.SECTION_GAP_IN * 100.0)
        self.assertAlmostEqual(tb.section_gap(1.0), tb.SECTION_GAP_IN)

    def test_centre_content_centres_in_the_window_and_moves_the_records(self):
        doc = ezdxf.new()
        msp = doc.modelspace()
        msp.add_line((100, 200), (300, 260))
        sh = _Sheet()
        dx, dy = tb.centre_content(list(msp), W, H, sheets=(sh,))
        ext = bbox.extents(list(msp), fast=True)
        x0, y0, x1, y1 = tb.content_window(W, H)
        self.assertAlmostEqual((ext.extmin.x + ext.extmax.x) / 2, (x0 + x1) / 2)
        self.assertAlmostEqual((ext.extmin.y + ext.extmax.y) / 2, (y0 + y1) / 2)
        self.assertEqual(sh.text_boxes[0][0], (dx, dy, 10.0 + dx, 10.0 + dy))
        self.assertEqual(sh.edges[0][0], (dx, dy))
        self.assertEqual(sh.obst[0][0], (dx, dy, 10.0 + dx, 10.0 + dy))

    def test_centre_content_vertical_only_and_under_the_stamp(self):
        doc = ezdxf.new()
        msp = doc.modelspace()
        msp.add_line((100, 200), (300, 260))
        dx, dy = tb.centre_content(list(msp), W, H, horizontal=False, under_stamp=True)
        self.assertEqual(dx, 0.0)
        ext = bbox.extents(list(msp), fast=True)
        _, y0, _, _ = tb.content_window(W, H)
        self.assertAlmostEqual((ext.extmin.y + ext.extmax.y) / 2, (y0 + tb.stamp_bottom(W, H)) / 2)

    def test_empty_content_is_left_alone(self):
        self.assertEqual(tb.centre_content([], W, H), (0.0, 0.0))

    def test_number_label_is_a_field_with_the_standard_default(self):
        fields = {"revision": "A", "rev_rows": (("A", "NOTE", "2026-01-01"),)}
        sh = _Sheet()
        tb.draw_cpme_sheet(sh, ezdxf.new(), W, H, fields)
        self.assertIn("NUMBER / PANEL", sh.texts)
        sh = _Sheet()
        tb.draw_cpme_sheet(sh, ezdxf.new(), W, H, {**fields, "number_label": "PROJECT NUMBER", "header": "",
                                                    "job_title": ""})
        self.assertIn("PROJECT NUMBER", sh.texts)
        self.assertNotIn("NUMBER / PANEL", sh.texts)


if __name__ == "__main__":
    unittest.main()
