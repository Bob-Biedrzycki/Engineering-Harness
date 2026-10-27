"""Unit tests for the manufacturer CAD face colours of the presentation builder:
rp.PRESENTATIONS/presentation_materials.py (step_faces, mesh_pieces, match_pieces, face_parts) and
portal_lib/materials_map.check (face_colours).

Fixture: the ifm TD2947 STEP (found by file name in the job or project component library, components.find_step;
83 KB, 62 faces in 4 colours). The test
tessellates its faces itself, writes them as the primitives of a small GLB in a shuffled order and checks every
piece gets the material of its own face: the match must not depend on face order. Stdlib unittest + the pinned
build123d / OCP of harness/requirements.txt:

    .\\harness\\tools\\venv\\Scripts\\python.exe -m unittest discover -s harness\\tests -v
"""
from __future__ import annotations

import json
import random
import struct
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

REPO = next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists())
sys.path.insert(0, str(REPO / "harness" / "lib"))
import repo_paths as rp  # noqa: E402
if not rp.HAS_PROJECT:
    raise unittest.SkipTest("no project yet (presentation builders live in a project)")
sys.path.insert(0, str(rp.PRESENTATIONS))
try:
    import presentation_materials as PM  # noqa: E402
    from portal_lib import materials_map as MM  # noqa: E402
except ImportError as e:   # no presentation builders on this project yet (no site, CPME practice): the module is skipped
    raise unittest.SkipTest(f"presentation builders not in {rp.PRESENTATIONS}: {e}")

import components  # noqa: E402
FIXTURE_NAME = "ifm_TD2947_temperature-transmitter-2in-clamp-EL150.stp"
_fixture = components.find_step(FIXTURE_NAME)   # job library, then the project's (harness/lib/components.py)
if _fixture is None:
    raise unittest.SkipTest(f"fixture {FIXTURE_NAME} not in the job or project component library")
FIXTURE = rp.rel(_fixture)
COLOURS = {"#B0B0B0": "steel", "#4D4D4D": "glass", "#FF9900": "orange", "#000000": "dark"}


def coloured_triangles(step: Path):
    """[(sRGB hex, [(x, y, z) mm per triangle vertex ...])] per face, read and meshed here with OCP directly."""
    from OCP.BRep import BRep_Tool
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.Quantity import Quantity_Color
    from OCP.STEPCAFControl import STEPCAFControl_Reader
    from OCP.TCollection import TCollection_ExtendedString
    from OCP.TDocStd import TDocStd_Document
    from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopLoc import TopLoc_Location
    from OCP.TopoDS import TopoDS
    from OCP.XCAFDoc import XCAFDoc_ColorGen, XCAFDoc_ColorSurf, XCAFDoc_DocumentTool
    doc = TDocStd_Document(TCollection_ExtendedString("XmlOcaf"))
    r = STEPCAFControl_Reader()
    r.SetColorMode(True)
    r.ReadFile(str(step))
    r.Transfer(doc)
    st, ct = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main()), XCAFDoc_DocumentTool.ColorTool_s(doc.Main())
    labs = PM._label_sequence()
    st.GetFreeShapes(labs)
    as_face = getattr(TopoDS, "Face_s", None) or TopoDS.Face      # OCP 7.7 / 7.8 names
    out = []
    for i in range(1, labs.Length() + 1):
        shape = st.GetShape_s(labs.Value(i))
        BRepMesh_IncrementalMesh(shape, 0.05, False, 0.3, True)
        ex = TopExp_Explorer(shape, TopAbs_FACE)
        while ex.More():
            f = as_face(ex.Current())
            c = Quantity_Color()
            ok = ct.GetColor(f, XCAFDoc_ColorSurf, c) or ct.GetColor(f, XCAFDoc_ColorGen, c)
            loc = TopLoc_Location()
            tri = BRep_Tool.Triangulation_s(f, loc)
            ex.Next()
            if tri is None:
                continue
            trsf = loc.Transformation()
            pts = []
            for k in range(1, tri.NbTriangles() + 1):
                a, b, cc = tri.Triangle(k).Get()
                if f.Orientation() == TopAbs_REVERSED:
                    b, cc = cc, b
                for n in (a, b, cc):
                    p = tri.Node(n).Transformed(trsf)
                    pts.append((p.X(), p.Y(), p.Z()))
            out.append((PM._hex(c) if ok else None, pts))
    return out


def write_glb(path: Path, node_name: str, pieces: list[list[tuple]]):
    """A one-node GLB whose mesh has one primitive per piece (vertex triples in mm, written in metres)."""
    bin_ = bytearray()
    views, accs, prims = [], [], []
    for pts in pieces:
        pos = b"".join(struct.pack("<3f", *(v / 1000.0 for v in p)) for p in pts)
        idx = b"".join(struct.pack("<I", k) for k in range(len(pts)))
        for data, target, comp, typ, count in ((pos, 34962, 5126, "VEC3", len(pts)), (idx, 34963, 5125, "SCALAR", len(pts))):
            while len(bin_) % 4:
                bin_ += b"\0"
            views.append({"buffer": 0, "byteOffset": len(bin_), "byteLength": len(data), "target": target})
            bin_ += data
            accs.append({"bufferView": len(views) - 1, "componentType": comp, "count": count, "type": typ})
        prims.append({"attributes": {"POSITION": len(accs) - 2}, "indices": len(accs) - 1})
    while len(bin_) % 4:
        bin_ += b"\0"
    g = {"asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [{"name": node_name, "mesh": 0}],
         "meshes": [{"primitives": prims}], "accessors": accs, "bufferViews": views, "buffers": [{"byteLength": len(bin_)}]}
    js = json.dumps(g).encode()
    js += b" " * (-len(js) % 4)
    with open(path, "wb") as f:
        f.write(struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(bin_)))
        f.write(struct.pack("<II", len(js), 0x4E4F534A) + js)
        f.write(struct.pack("<II", len(bin_), 0x004E4942) + bytes(bin_))


class StepFaces(unittest.TestCase):
    def test_fixture_colours(self):
        faces = PM.step_faces(REPO / FIXTURE)
        self.assertEqual(len(faces), 62)
        self.assertEqual(Counter(c for c, _, _ in faces), Counter({"#B0B0B0": 37, "#000000": 10, "#FF9900": 9, "#4D4D4D": 6}))

    def test_missing_step_names_the_file(self):
        with self.assertRaises(PM.FaceColourError) as cm:
            PM.step_faces(rp.JOB_COMPONENTS / "no-such-part.stp")
        self.assertIn("no-such-part.stp", str(cm.exception))


class Matching(unittest.TestCase):
    def test_order_independent_end_to_end(self):
        """Faces tessellated here, written to a GLB in a shuffled order: every piece takes its own face's colour."""
        tris = coloured_triangles(REPO / FIXTURE)
        random.Random(60).shuffle(tris)
        with tempfile.TemporaryDirectory() as d:
            glb = Path(d) / "t.glb"
            write_glb(glb, "T-901-SP01_TT-901_instrument_-_CMP-0044_TD2947_CMP-0034__ifm", [p for _, p in tris])
            warnings = []
            m = {"face_colours": {"CMP-T034": {"part": "TD2947_CMP-0034", "step": FIXTURE, "colours": COLOURS}}}
            fp = PM.face_parts(m, glb, warn=warnings.append)
        self.assertEqual(len(fp), 1)
        e = fp[0]
        self.assertEqual(e["materials"], [COLOURS[c] for c, _ in tris])
        self.assertEqual(e["matched"], len(tris))
        self.assertEqual(e["tris"], [len(p) // 3 for _, p in tris])
        self.assertEqual(len(e["centroids"]), len(tris))
        self.assertEqual(warnings, [])

    def test_no_node_and_unknown_colour_warn(self):
        tris = coloured_triangles(REPO / FIXTURE)
        with tempfile.TemporaryDirectory() as d:
            glb = Path(d) / "t.glb"
            write_glb(glb, "TD2947_CMP-0034", [p for _, p in tris])
            warnings = []
            m = {"face_colours": {"CMP-T034": {"part": "TD2947_CMP-0034", "step": FIXTURE,
                                               "colours": {"#B0B0B0": "steel"}},
                                  "CMP-T999": {"part": "NOPE", "step": FIXTURE, "colours": {}}}}
            fp = PM.face_parts(m, glb, warn=warnings.append)
        self.assertEqual(fp[0]["unknown_colours"], ["#000000", "#4D4D4D", "#FF9900"])
        self.assertEqual(fp[0]["matched"], 37)
        self.assertTrue(any("CMP-T999" in w and "no GLB mesh node" in w for w in warnings))
        self.assertTrue(any("no entry" in w for w in warnings))

    def test_coincident_centroids_decided_by_area(self):
        faces = [("#111111", (0.0, 0.0, 0.0), 10.0), ("#222222", (0.0, 0.0, 0.004), 100.0)]
        piece = {"tris": 4, "centroid": [0.0, 0.0, 0.0], "area": 96.0}
        mats, st = PM.match_pieces([piece], faces, {"#111111": "disc", "#222222": "ring"})
        self.assertEqual(mats, ["ring"])
        self.assertEqual(st["by_area"], 1)
        mats, st = PM.match_pieces([dict(piece, centroid=[9.0, 0.0, 0.0])], faces, {"#111111": "disc"})
        self.assertEqual((mats, st["unmatched"]), ([None], 1))


class Regions(unittest.TestCase):
    """face_colours `regions`: centroid boxes in the STEP's native frame, first match wins, then colours."""

    def test_in_region_and_first_match(self):
        regs = [{"material": "a", "x": [-1, 1], "z": [0, 5]}, {"material": "b", "x_abs_min": 10},
                {"material": "c", "z": [-100, 100]}]
        faces = [("#009EE3", (0.5, 99.0, 2.0), 1.0),    # a (y unbounded)
                 ("#009EE3", (-12.0, 0.0, 2.0), 1.0),   # b (|x| >= 10), before c
                 ("#009EE3", (3.0, 0.0, 2.0), 1.0),     # c
                 ("#009EE3", (3.0, 0.0, 500.0), 1.0)]   # no region: keeps its colour
        out, n = PM.region_faces(faces, regs)
        self.assertEqual([f[0] for f in out], ["region[0]", "region[1]", "region[2]", "#009EE3"])
        self.assertEqual(n, {"region[0]": 1, "region[1]": 1, "region[2]": 1})
        self.assertEqual(PM.region_faces(faces, []), (faces, {}))

    def test_regions_end_to_end_and_unchanged_without(self):
        """Every TD2947 face in one region box takes the region material; without regions the result is as before."""
        tris = coloured_triangles(REPO / FIXTURE)
        with tempfile.TemporaryDirectory() as d:
            glb = Path(d) / "t.glb"
            write_glb(glb, "TD2947_CMP-0034", [p for _, p in tris])
            base = {"part": "TD2947_CMP-0034", "step": FIXTURE, "colours": COLOURS}
            plain = PM.face_parts({"face_colours": {"CMP-T034": base}}, glb, warn=lambda s: None)
            reg = [{"what": "everything below z 1e6", "material": "painted", "z": [-1e6, 1e6]}]
            fp = PM.face_parts({"face_colours": {"CMP-T034": dict(base, regions=reg)}}, glb, warn=lambda s: None)
        self.assertNotIn("regions", plain[0])
        self.assertEqual(set(fp[0]["materials"]), {"painted"})
        self.assertEqual(fp[0]["regions"][0]["pieces"], len(tris))
        self.assertEqual(fp[0]["regions"][-1], {"what": "colours", "faces": 0, "pieces": 0})

    def test_loose_pass_only_for_unmatched(self):
        faces = [("#111111", (0.0, 0.0, 0.0), 1000.0)]
        p = {"tris": 9, "centroid": [0.61, 0.0, 0.0], "area": 980.0}
        mats, st = PM.match_pieces([p], faces, {"#111111": "x"})
        self.assertEqual((mats, st["loose"], st["unmatched"]), (["x"], 1, 0))
        mats, st = PM.match_pieces([dict(p, area=500.0)], faces, {"#111111": "x"})   # areas disagree: stays unmatched
        self.assertEqual((mats, st["loose"], st["unmatched"]), ([None], 0, 1))
        mats, st = PM.match_pieces([dict(p, centroid=[0.2, 0, 0])], faces, {"#111111": "x"})
        self.assertEqual(st["loose"], 0)


def write_glb_child(path: Path, parent: str, child: str, pieces: list[list[tuple]], rotation: list[float]):
    """A GLB whose matched node `parent` has no mesh and one child mesh node `child` with a node rotation."""
    write_glb(path, child, pieces)
    with open(path, "rb") as f:
        f.read(12)
        clen, _ = struct.unpack("<II", f.read(8))
        g = json.loads(f.read(clen))
        rest = f.read()
    g["nodes"] = [{"name": parent, "children": [1]}, {"name": child, "mesh": 0, "rotation": rotation}]
    js = json.dumps(g).encode()
    js += b" " * (-len(js) % 4)
    with open(path, "wb") as f:
        f.write(struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(js) + len(rest)))
        f.write(struct.pack("<II", len(js), 0x4E4F534A) + js + rest)


RZ180 = [0.0, 0.0, 1.0, 0.0]     # glTF quaternion (x, y, z, w): 180 deg about Z


class ChildMeshes(unittest.TestCase):
    """A mesh below the node that matches `part` (CMP-T057 `COMPOUND`), in its own or the anchor's frame."""

    def setUp(self):
        self.tris = coloured_triangles(REPO / FIXTURE)
        self.m = {"face_colours": {"CMP-T034": {"part": "TD2947_CMP-0034", "step": FIXTURE, "colours": COLOURS}},
                  "required_looks": {"TT-901": "CMP-T034", "TT-902": "CMP-T034"}}

    def run_case(self, pieces):
        with tempfile.TemporaryDirectory() as d:
            glb = Path(d) / "t.glb"
            write_glb_child(glb, "TT-901_instrument_-_CMP-0044_TD2947_CMP-0034", "COMPOUND", pieces, RZ180)
            det, warnings = [], []
            fp = PM.face_parts(self.m, glb, warn=warnings.append, detail=det)
        return fp, det, warnings

    def test_child_in_step_frame_own_frame_wins(self):
        """Vertices already in the STEP frame, the node rotation a placement (a housing turn)."""
        fp, det, warnings = self.run_case([p for _, p in self.tris])
        self.assertEqual(fp[0]["nodes"], ["COMPOUND"])
        self.assertEqual(fp[0]["anchors"], ["TT-901_instrument_-_CMP-0044_TD2947_CMP-0034"])
        self.assertEqual(fp[0]["materials"], [COLOURS[c] for c, _ in self.tris])
        self.assertEqual((det[0]["frame"], warnings), ("own", []))

    def test_child_in_rotated_frame_anchor_wins(self):
        """Vertices in a frame turned against the STEP, the node rotation bringing them back."""
        fp, det, warnings = self.run_case([[(-x, -y, z) for x, y, z in p] for _, p in self.tris])
        self.assertEqual(fp[0]["materials"], [COLOURS[c] for c, _ in self.tris])
        self.assertEqual(fp[0].get("frame"), "anchor")
        self.assertEqual(warnings, [])

    def test_looks_coverage(self):
        _, det, _ = self.run_case([p for _, p in self.tris])
        n, total, missing, line = PM.looks_coverage(self.m, det)
        self.assertEqual((n, total), (1, 2))
        self.assertEqual(missing, ["TT-902 (no CMP-T034 mesh)"])
        self.assertTrue(line.startswith("looks: 1 of 2 required instruments realistic; missing: TT-902"))
        m = dict(self.m, face_colours={"CMP-T034": dict(self.m["face_colours"]["CMP-T034"],
                                                        regions=[{"what": "nowhere", "material": "steel", "z": [1e6, 1e7]}])})
        _, det2, _ = (None, [], None)
        with tempfile.TemporaryDirectory() as d:
            glb = Path(d) / "t.glb"
            write_glb_child(glb, "TT-901_instrument_-_CMP-0044_TD2947_CMP-0034", "COMPOUND", [p for _, p in self.tris], RZ180)
            PM.face_parts(m, glb, warn=lambda s: None, detail=det2)
        self.assertIn("TT-901 (CMP-T034: regions without pieces: nowhere)", PM.looks_coverage(m, det2)[2])

    def test_position_pass_only_with_regions(self):
        faces = [("region[0]", (0.0, 0.0, 0.0), 10.0), ("#009EE3", (50.0, 0.0, 0.0), 10.0)]
        regs = [{"material": "black", "x": [-5, 5]}]
        cols = {"#009EE3": "blue", "region[0]": "black"}
        pcs = [{"tris": 2, "centroid": [3.0, 0.0, 0.0], "area": 99.0}, {"tris": 2, "centroid": [30.0, 0.0, 0.0], "area": 99.0}]
        mats, st = PM.match_pieces(pcs, faces, cols, regs)
        self.assertEqual((mats, st["by_position"], st["unmatched"]), (["black", "blue"], 2, 0))
        mats, st = PM.match_pieces(pcs, faces, cols)
        self.assertEqual((mats, st["by_position"], st["unmatched"]), ([None, None], 0, 2))


class MapCheck(unittest.TestCase):
    def test_required_looks_validation(self):
        base = {"materials": {"steel": {}}, "groups": {"x": "steel"},
                "face_colours": {"CMP-1": {"part": "A_CMP-1", "step": "s.stp", "colours": {"#B0B0B0": "steel"}}}}
        self.assertEqual(MM.check(dict(base, required_looks={"LT-101": "CMP-1"})), [])
        txt = " | ".join(MM.check(dict(base, required_looks={"LT-101": "CMP-2"})))
        self.assertIn("required_looks[LT-101]: 'CMP-2' is not a face_colours entry", txt)
        self.assertIn("required_looks: a mapping", " ".join(MM.check(dict(base, required_looks=["LT-101"]))))

    def test_regions_validation(self):
        base = {"materials": {"steel": {}}, "groups": {"x": "steel"}}
        fc = {"part": "A_CMP-1", "step": "s.stp", "colours": {"#B0B0B0": "steel"}}
        ok = dict(base, face_colours={"CMP-1": dict(fc, regions=[{"what": "a, b", "material": "steel", "x": [-1, 1],
                                                                   "x_abs_min": 2}])})
        self.assertEqual(MM.check(ok), [])
        bad = dict(base, face_colours={"CMP-1": dict(fc, regions=[{"material": "nope", "y": [3, 1], "316L)": None}])})
        txt = " | ".join(MM.check(bad))
        for want in ("unknown material 'nope'", "[min, max]", "unknown key '316L)'"):
            self.assertIn(want, txt)

    def test_face_colours_validation(self):
        base = {"materials": {"steel": {}}, "groups": {"x": "steel"}}
        ok = dict(base, face_colours={"CMP-1": {"part": "A_CMP-1", "step": "s.stp", "colours": {"#B0B0B0": "steel"}}})
        self.assertEqual(MM.check(ok), [])
        bad = dict(base, face_colours={"CMP-1": {"part": "(", "step": "", "colours": {"b0b0b0": "nope"}}})
        txt = " | ".join(MM.check(bad))
        for want in ("bad regex", "missing 'step'", "not an sRGB hex", "unknown material 'nope'"):
            self.assertIn(want, txt)


if __name__ == "__main__":
    unittest.main()
