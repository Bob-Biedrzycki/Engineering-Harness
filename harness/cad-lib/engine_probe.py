"""engine_probe.py - a fixed set of small solids, built, written to STEP, read back and projected, as numbers.

Run by harness/scripts/engine_check.py with two interpreters (the pinned cad venv and a candidate) so the two
engines can be compared without touching a model build, a view cache or anything filed. It also reports whether the
names the harness and the job generators take from the engine are still there, because the drawing engine's
projection helpers are internal names that a release may rename.

    <interpreter> harness/cad-lib/engine_probe.py <out.json>

Writes one JSON file: versions, api (name -> present), solids (name -> volume, area, bbox, faces, edges, and the
volume after a STEP round trip), views (name -> projection map, bounds, visible and hidden edge counts and length).
Model units are millimetres. Nothing else is written; the STEP goes to a temporary folder.
"""
from __future__ import annotations

import json
import sys
import tempfile
from importlib import import_module
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

# every name taken from the engine by the harness or by a job's generators; add one here when code starts using it
API = {
    "cad": ["model", "step", "glb"],
    "cad.step": ["read"],
    "cad.eng_drawing": ["VIEW_DIRECTIONS", "_Projection", "_project_to_viewport", "_edges_bounds", "_circles",
                        "_centres", "Sheet", "eng_drawing"],
    "build123d": ["import_step", "export_step", "export_gltf", "Shape", "Compound", "Box", "Cylinder", "Pos"],
    "build123d.topology": ["downcast"],
}
PACKAGES = ["cad", "build123d", "cadquery-ocp-novtk", "ezdxf", "matplotlib"]


def versions() -> dict:
    out = {"python": sys.version.split()[0]}
    for p in PACKAGES:
        try:
            out[p] = version(p)
        except PackageNotFoundError:
            out[p] = None
    return out


def api() -> dict:
    out = {}
    for mod, names in API.items():
        try:
            m = import_module(mod)
        except Exception as e:  # noqa: BLE001
            out[mod] = f"import failed: {type(e).__name__}: {e}"
            continue
        for n in names:
            out[f"{mod}.{n}"] = hasattr(m, n)
    return out


def solids() -> dict:
    import build123d as bd
    plate = bd.Box(200, 100, 10)
    for x, y in ((-80, -30), (80, -30), (-80, 30), (80, 30)):
        plate -= bd.Pos(x, y, 0) * bd.Cylinder(5.5, 10)
    plate = bd.fillet(plate.edges().filter_by(bd.Axis.Z), 6)
    tee = bd.Cylinder(25.4, 150) + bd.Pos(0, 0, 0) * bd.Rot(0, 90, 0) * bd.Pos(0, 0, 40) * bd.Cylinder(19.05, 80)
    tee -= bd.Cylinder(23.75, 150)
    with bd.BuildPart() as elbow:
        with bd.BuildLine() as path:
            bd.CenterArc((0, 0), 76.2, 0, 90)
        with bd.BuildSketch(bd.Plane(origin=path.line @ 0, z_dir=path.line % 0)):
            bd.Circle(25.4)
            bd.Circle(23.75, mode=bd.Mode.SUBTRACT)
        bd.sweep()
    return {"plate": plate, "tee": tee, "elbow": elbow.part}


def measure(shape) -> dict:
    bb = shape.bounding_box()
    return {"volume": shape.volume, "area": shape.area,
            "bbox": [bb.min.X, bb.min.Y, bb.min.Z, bb.max.X, bb.max.Y, bb.max.Z],
            "faces": len(shape.faces()), "edges": len(shape.edges())}


def step_round_trip(shape, folder: Path, name: str) -> dict:
    import build123d as bd
    from cad import step
    f = folder / f"{name}.step"
    bd.export_step(shape, str(f))
    back = step.read(f)
    back = getattr(back, "shape", back)
    return {"step_entities": sum(1 for ln in f.read_text(encoding="utf-8", errors="replace").splitlines()
                                 if ln.startswith("#")),
            "step_volume": back.volume}


def view(shape, name: str) -> dict:
    from cad.eng_drawing import _Projection, _edges_bounds
    p = _Projection(shape, name)
    vis, hid = list(p.visible), list(p.hidden)
    b = _edges_bounds(vis)
    return {"c": list(p.c), "m": [list(r) for r in p.m], "bounds": list(b) if b else None,
            "visible": len(vis), "hidden": len(hid),
            "visible_length": sum(getattr(e, "length", 0.0) for e in vis),
            "hidden_length": sum(getattr(e, "length", 0.0) for e in hid)}


def main() -> int:
    out = {"versions": versions(), "api": api(), "solids": {}, "views": {}, "errors": []}
    try:
        shapes = solids()
    except Exception as e:  # noqa: BLE001
        out["errors"].append(f"solids: {type(e).__name__}: {e}")
        shapes = {}
    with tempfile.TemporaryDirectory() as td:
        for name, s in shapes.items():
            try:
                out["solids"][name] = measure(s)
                out["solids"][name].update(step_round_trip(s, Path(td), name))
            except Exception as e:  # noqa: BLE001
                out["errors"].append(f"{name}: {type(e).__name__}: {e}")
            for v in ("top", "front", "iso"):
                try:
                    out["views"][f"{name}-{v}"] = view(s, v)
                except Exception as e:  # noqa: BLE001
                    out["errors"].append(f"{name}-{v}: {type(e).__name__}: {e}")
    Path(sys.argv[1]).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"engine_probe: cad {out['versions']['cad']}, {len(out['solids'])} solids, {len(out['views'])} views, "
          f"{len(out['errors'])} errors")
    return 0


if __name__ == "__main__":
    sys.exit(main())
