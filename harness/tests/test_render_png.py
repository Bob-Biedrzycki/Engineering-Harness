"""Unit tests for harness/cad-lib/render_png.py (review snapshots).

- assembly_bodies places every leaf with its ancestors' locations: on a nested assembly written to STEP and read
  back, the bodies land where the root's own solids() (which carries every location) puts them; walking leaf by
  leaf without the ancestors does not (a past defect).
- a body that cannot be tessellated is named in a warning and counted, not dropped silently.
- clip keeps only the triangles inside the box; the caption names the model given, default the MODEL-ID.

    .\\harness\\tools\\venv\\Scripts\\python.exe -m unittest discover -s harness\\tests -v
"""
from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import types
import unittest
from pathlib import Path

REPO = next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists())
sys.path.insert(0, str(REPO / "harness" / "cad-lib"))
sys.path.insert(0, str(REPO / "harness" / "lib"))
import render_png as R  # noqa: E402
import repo_paths as rp  # noqa: E402

bd = R.bd


def _box_key(shape):
    b = R._bbox(shape)
    return tuple(round(v, 3) for v in (b.min.X, b.min.Y, b.min.Z, b.max.X, b.max.Y, b.max.Z))


def nested_step(path: Path):
    """root (moved +100 X) > sub (moved +50 Y, rotated 90 about Z) > two boxes, plus one box straight under root."""
    a = bd.Box(10, 2, 2)
    a.label = "A"
    b = bd.Pos(0, 0, 20) * bd.Box(2, 2, 2)
    b.label = "B"
    sub = bd.Compound(children=[a, b], label="sub")
    sub.location = bd.Location((0, 50, 0), (0, 0, 90))
    c = bd.Pos(-30, 0, 0) * bd.Box(4, 4, 4)
    c.label = "C"
    c.color = bd.Color(1, 0, 0)
    root = bd.Compound(children=[sub, c], label="root")
    root.location = bd.Location((100, 0, 0))
    bd.export_step(root, str(path))


class AssemblyWalk(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        p = Path(cls.tmp.name) / "nested.step"
        nested_step(p)
        cls.asm = bd.import_step(str(p))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_bodies_land_where_the_root_puts_them(self):
        bodies = R.assembly_bodies(self.asm)
        self.assertEqual(sorted(_box_key(b.shape) for b in bodies), sorted(_box_key(s) for s in self.asm.solids()))
        self.assertEqual(len(bodies), 3)

    def test_leaf_by_leaf_without_ancestors_is_wrong(self):
        leaves = []

        def walk(n):
            kids = list(getattr(n, "children", None) or ())
            if not kids:
                leaves.extend(n.solids())
            for k in kids:
                walk(k)
        walk(self.asm)
        self.assertNotEqual(sorted(_box_key(s) for s in leaves), sorted(_box_key(s) for s in self.asm.solids()))

    def test_leaf_with_open_shells_is_drawn_whole(self):
        """A vendor leaf that is a solid plus loose faces (a vendor flow switch) keeps every face."""
        loose = bd.Pos(0, 0, 30) * bd.Face.make_rect(5, 5)
        leaf = bd.Compound([bd.Box(2, 2, 2), loose])
        leaf.label = "vendor"
        bodies = R.assembly_bodies(bd.Compound(children=[leaf], label="root"))
        self.assertEqual(sum(len(b.shape.faces()) for b in bodies), 7)

    def test_select_and_labels(self):
        bodies = R.assembly_bodies(self.asm, select=lambda p: p.endswith("/ C") or p.endswith(" C"))
        self.assertEqual(len(bodies), 1)
        self.assertTrue(bodies[0].label.endswith("C"))


class Painting(unittest.TestCase):
    def test_failed_tessellation_is_named(self):
        class Bad:
            color = None

            def tessellate(self, *a):
                raise RuntimeError("NbNodes")
        good = R.SnapBody("part", bd.Box(10, 10, 10), "good box")
        bad = types.SimpleNamespace(category="part", shape=Bad(), label="ifm SI6800 body")
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            tris, dropped = R.triangles([good, bad], (0, 0, -1))
        self.assertTrue(tris)
        self.assertEqual(dropped, ["ifm SI6800 body"])
        self.assertIn("ifm SI6800 body", err.getvalue())
        self.assertIn("1 bodies not drawn", R.caption("x", "M", len(tris), len(dropped)))

    def test_clip_keeps_the_window_only(self):
        body = R.SnapBody("part", bd.Box(100, 10, 10), "long box")
        full, _ = R.triangles([body], (0, -1, 0))
        part, _ = R.triangles([body], (0, -1, 0), clip=((-60, -6, -6), (0, 6, 6)))
        self.assertTrue(0 < len(part) < len(full))

    def test_caption_title(self):
        if rp.HAS_PROJECT:
            self.assertEqual(R.default_title(), rp.SKID_MODEL_ID)
        self.assertIn("|  Test Skid Mockup  |", R.caption("iso", "Test Skid Mockup", 10))
        self.assertEqual(R.title_from_file(Path("0000-00-TST-001-MODEL-revJ.step.zip")), "0000-00-TST-001-MODEL Rev J")
        self.assertEqual(R.title_from_file(Path("0000-00-TST-001-MODEL.step")), "0000-00-TST-001-MODEL")

    def test_render_writes_png(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "s.png"
            R.render([R.SnapBody("part", bd.Box(10, 10, 10), "b")], str(out), (-1, -1, -1), size=(200, 150), label="t")
            self.assertTrue(out.exists() and out.stat().st_size > 0)


if __name__ == "__main__":
    unittest.main()
