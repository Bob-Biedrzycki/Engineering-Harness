"""Snapshot renderer for review images (not drawings).

The text-to-cad `cadgen` snapshot tool times out on the whole skid, so this is the documented fallback: tessellate
every body with build123d, project the triangles with an orthographic camera and paint them back to front with
Pillow. Deterministic: same model, same view, same pixels. Review PNGs are not drawings and are never filed through
revfile.py (TR-06..08 cover DWG / PDF).

Library (any build123d venv: repo harness/tools/venv 0.13.0, cadgen harness/tools/venv-cadgen 0.11.1):

    render(bodies, path, direction, up=..., label=..., title=None, clip=None)
        bodies: objects with .shape and .category (and .label, used in warnings); title: the model named in the
        caption (default: the project's MODEL-ID, repo_paths.SKID_MODEL_ID); clip: (lo, hi) box in the bodies' units,
        triangles whose centroid is outside are not drawn (works on any body, vendor STEP bodies included).
    assembly_bodies(asm, select=None)
        one SnapBody per solid of each leaf of an imported STEP assembly (the whole leaf when it has no solid or
        faces outside its solids, as vendor compounds of a solid and open shells do), placed with the
        product of its ancestors' locations (a leaf's own shape carries only its location relative to its parent),
        colour inherited down the tree, label = the node path.
    clip_bodies(bodies, lo, hi)
        boolean intersection with a box, for a true section; a body whose boolean comes back empty while its box
        overlaps the window (vendor STEP shells) is kept whole with a warning: pass clip=(lo, hi) to render().

Command line (the views the review snapshots use; the caption names the model from the file name or --title):

    python harness/cad-lib/render_png.py <model.step | filed .step.zip> <out.png> [--view iso|front|plan|end|x,y,z]
        [--up x,y,z] [--title TEXT] [--label TEXT] [--only REGEX] [--clip x0,y0,z0,x1,y1,z1 (in)] [--size WxH]

A body that cannot be tessellated is retried at a coarse tolerance, then from a ShapeFix-repaired copy (invalid
vendor shapes; display only, the model is not touched), then face by face. Each fallback is named in a warning on
stderr; a body that still yields nothing is not drawn, named, and counted in the caption, never dropped silently.
"""
from __future__ import annotations

import argparse
import math
import re
import sys
from collections import namedtuple
from pathlib import Path

from PIL import Image, ImageDraw

try:
    import build123d as bd
except ImportError:            # cadgen venv: build123d 0.11.1 vendored under cadgen
    from cadgen import build123d as bd

Vector = bd.Vector
SnapBody = namedtuple("SnapBody", "category shape label")
MM_PER_IN = 25.4
VIEWS = {   # direction into the scene, up; +X along the skid, +Y the FRONT, +Z up
    "iso": ((-1.0, -1.1, -0.75), (0, 0, 1)),     # from the front and the +X end, above
    "front": ((0.0, -1.0, 0.0), (0, 0, 1)),      # front elevation, from +Y
    "plan": ((0.0, 0.0, -1.0), (0, 1, 0)),       # from above, +Y front at the top
    "end": ((-1.0, 0.0, 0.0), (0, 0, 1)),        # from the +X end
}


def _warn(msg: str):
    print(f"render_png: WARNING {msg}", file=sys.stderr)


def _bbox(shape):
    """Axis box without the optimal pass (minutes on vendor models; 2026-10-01 note)."""
    try:
        return shape.bounding_box(optimal=False)
    except TypeError:
        return shape.bounding_box()


def default_title() -> str:
    """The project's MODEL-ID (harness/lib/repo_paths.py), the default model name in the caption."""
    try:
        here = Path(__file__).resolve()
        lib = next(p for p in here.parents if (p / "CLAUDE.md").exists()) / "harness" / "lib"
        if str(lib) not in sys.path:
            sys.path.insert(0, str(lib))
        import repo_paths as rp
        return rp.SKID_MODEL_ID
    except Exception:  # noqa: BLE001  (a copy of this file outside the repo)
        return "model"


def caption(label: str, title: str, ntris: int, dropped: int = 0) -> str:
    return (f"{label}  |  {title}  |  review snapshot, not a drawing  |  {ntris} triangles"
            + (f"  |  {dropped} bodies not drawn (tessellation failed)" if dropped else ""))


# ---------------------------------------------------------------- assemblies
def _placed(shape, loc):
    """shape moved by loc without Shape.moved(), which deep-copies the whole imported tree (minutes on the skid)."""
    w = shape.wrapped.Moved(loc.wrapped)
    try:
        out = type(shape)(w)
    except Exception:  # noqa: BLE001
        out = bd.Shape.cast(w)
    out.label, out.color = getattr(shape, "label", ""), getattr(shape, "color", None)
    return out


def assembly_bodies(asm, select=None, category: str = "part") -> list[SnapBody]:
    """One SnapBody per solid of every leaf of an imported assembly, globally placed. select: optional predicate on
    the node path ("root / child / leaf"), True to keep."""
    out = []

    def walk(n, acc, col, path):
        lab = getattr(n, "label", "") or ""
        c = getattr(n, "color", None) or col
        p = f"{path} / {lab}" if path else lab
        kids = list(getattr(n, "children", None) or ())
        if kids:
            for k in kids:
                walk(k, acc * n.location, c, p)
            return
        if select is not None and not select(p):
            return
        solids = n.solids()
        # a vendor leaf can be a compound of a solid plus open shells (a vendor flow switch had 14 of 153 faces
        # in its solid); then the leaf is drawn whole, or the shells would vanish
        if not solids or sum(len(s.faces()) for s in solids) < len(n.faces()):
            solids = [n]
        for so in solids:
            s = _placed(so, acc)
            s.color = getattr(so, "color", None) or c
            out.append(SnapBody(category, s, p))

    walk(asm, bd.Location(), None, "")
    return out


def clip_bodies(bodies, lo, hi) -> list[SnapBody]:
    """Each body's solids intersected with the box lo..hi (the bodies' units)."""
    win = bd.Pos(*[(a + b) / 2 for a, b in zip(lo, hi)]) * bd.Box(*[b - a for a, b in zip(lo, hi)])
    out = []
    for b in bodies:
        label = getattr(b, "label", "")
        for so in (b.shape.solids() or [b.shape]):
            bb = _bbox(so)
            if any(bb.max.to_tuple()[i] < lo[i] or bb.min.to_tuple()[i] > hi[i] for i in range(3)):
                continue
            try:
                x = so & win
                parts = [p for p in ((x.solids() if hasattr(x, "solids") else [x]) if x is not None else [])
                         if p is not None and p.volume > 1e-9]
            except Exception:  # noqa: BLE001
                parts = []
            if not parts:
                _warn(f"clip: '{label}' gave no solid in the window (open shell or failed boolean); kept whole, "
                      f"pass clip=(lo, hi) to render() to trim its triangles")
                parts = [so]
            for p in parts:
                p.color = getattr(b.shape, "color", None)
                out.append(SnapBody(b.category, p, label))
    return out


# ---------------------------------------------------------------- painting
def _per_face(shape, tolerance, angular):
    """(verts, triangles, faces not drawn, faces) meshing each face on its own: a vendor body whose whole-body mesh
    leaves one face without a triangulation (build123d raises 'NoneType ... NbNodes') keeps its other faces."""
    verts, faces, bad, total = [], [], 0, 0
    try:
        fl = shape.faces()
    except Exception:  # noqa: BLE001
        return [], [], 0, 0
    for f in fl:
        total += 1
        try:
            v, t = f.tessellate(tolerance, angular)
        except Exception:  # noqa: BLE001
            try:
                v, t = f.tessellate(tolerance * 5, angular * 2)
            except Exception:  # noqa: BLE001
                bad += 1
                continue
        n0 = len(verts)
        verts += list(v)
        faces += [(i + n0, j + n0, k + n0) for i, j, k in t]
    return verts, faces, bad, total


def triangles(bodies, direction, up=(0, 0, 1), tolerance=0.4, angular=0.5, skip_categories=("zone",),
              light=(-0.4, -0.6, 0.7), skip=None, clip=None, retry=(2.0, 1.0)):
    """(triangles [(depth, 2D poly, colour)], labels of bodies not drawn) for one view."""
    d = Vector(*direction).normalized()
    if d.cross(Vector(*up)).length < 1e-9:     # looking along `up` (a plan view called with up Z): +Y is up instead
        up = (0, 1, 0) if abs(d.Y) < 0.9 else (1, 0, 0)
    right = d.cross(Vector(*up)).normalized()
    up2 = right.cross(d).normalized()
    lv = Vector(*light).normalized()
    tris, dropped = [], []
    for b in bodies:
        if b.category in skip_categories or b.shape is None:
            continue
        if skip is not None and skip(b):
            continue
        label = getattr(b, "label", "") or "(no label)"
        verts = faces = None
        err = None
        for tol, ang in ((tolerance, angular), retry):
            try:
                verts, faces = b.shape.tessellate(tol, ang)
                if faces:
                    break
                err = "no triangles"
            except Exception as e:  # noqa: BLE001
                err = f"{type(e).__name__}: {e}"
            verts = faces = None
        if not faces:
            try:        # an invalid vendor shape (a bad edge on one face) usually meshes once ShapeFix has run on a copy
                from OCP.ShapeFix import ShapeFix_Shape
                sf = ShapeFix_Shape(b.shape.wrapped)
                sf.Perform()
                verts, faces = bd.Shape.cast(sf.Shape()).tessellate(tolerance, angular)
            except Exception:  # noqa: BLE001
                verts = faces = None
            if faces:
                _warn(f"body '{label}': tessellation failed ({err}); drawn from a ShapeFix-repaired copy (display only)")
        if not faces:
            verts, faces, bad, total = _per_face(b.shape, tolerance, angular)
            if faces:
                _warn(f"body '{label}': whole-body tessellation failed ({err}); drawn face by face, {bad} of "
                      f"{total} faces not drawn")
            else:
                _warn(f"body '{label}' not drawn: tessellation failed ({err})")
                dropped.append(label)
                continue
        col = b.shape.color
        if col is None:
            rgb = (150, 150, 150)
        else:
            c = list(col)  # Color iterates (r, g, b, a)
            rgb = (int(c[0] * 255), int(c[1] * 255), int(c[2] * 255))
        pts = [(v.dot(right), v.dot(up2), v.dot(d)) for v in verts]
        for (i, j, k) in faces:
            p0, p1, p2 = verts[i], verts[j], verts[k]
            if clip is not None:
                cen = [(p0.X + p1.X + p2.X) / 3, (p0.Y + p1.Y + p2.Y) / 3, (p0.Z + p1.Z + p2.Z) / 3]
                if any(cen[q] < clip[0][q] or cen[q] > clip[1][q] for q in range(3)):
                    continue
            n = (p1 - p0).cross(p2 - p0)
            if n.length < 1e-12:
                continue
            n = n * (1.0 / n.length)
            if n.dot(d) > 0:  # back face
                continue
            shade = 0.45 + 0.55 * max(0.0, n.dot(lv))
            color = tuple(min(255, int(ch * shade)) for ch in rgb)
            a, bb, cc = pts[i], pts[j], pts[k]
            tris.append(((a[2] + bb[2] + cc[2]) / 3.0, ((a[0], a[1]), (bb[0], bb[1]), (cc[0], cc[1])), color))
    return tris, dropped


def render(bodies, path, direction, up=(0, 0, 1), size=(1800, 1200), label="", tolerance=0.4,
           angular=0.5, skip_categories=("zone",), light=(-0.4, -0.6, 0.7), skip=None, title=None, clip=None):
    """bodies: iterable of objects with .shape and .category (components_lib.Body, SnapBody). direction: view
    direction (into the scene). skip: optional predicate Body -> bool to hide bodies (e.g. tanks for a piping view).
    title: model name in the caption (default the MODEL-ID). clip: (lo, hi) box, triangles outside are not drawn."""
    title = title or default_title()
    tris, dropped = triangles(bodies, direction, up, tolerance, angular, skip_categories, light, skip, clip)
    if not tris:
        img = Image.new("RGB", size, "white")
        ImageDraw.Draw(img).text((10, 10), f"{label}: nothing to render ({title})", fill="black")
        img.save(path)
        return path
    xs = [p[0] for t in tris for p in t[1]]
    ys = [p[1] for t in tris for p in t[1]]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    W, H = size
    pad = 40
    scale = min((W - 2 * pad) / max(x1 - x0, 1e-6), (H - 2 * pad) / max(y1 - y0, 1e-6))
    ox = (W - (x1 - x0) * scale) / 2
    oy = (H - (y1 - y0) * scale) / 2

    def to_px(p):
        return (ox + (p[0] - x0) * scale, H - (oy + (p[1] - y0) * scale))

    tris.sort(key=lambda t: -t[0])  # far first
    img = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(img)
    for _, poly, color in tris:
        draw.polygon([to_px(p) for p in poly], fill=color)
    # scale bar: 12 in
    bar = 12.0 * scale
    draw.line([(pad, H - pad / 2), (pad + bar, H - pad / 2)], fill="black", width=3)
    draw.text((pad, H - pad / 2 - 14), "12 in", fill="black")
    draw.text((10, 10), caption(label, title, len(tris), len(dropped)), fill="black")
    img.save(path)
    return path


# ---------------------------------------------------------------- command line
def title_from_file(p: Path) -> str:
    """'<MODEL-ID> Rev <X>' from a filed name (<MODEL-ID>-rev<X>.step[.zip]), else the file stem (a work build is
    named <MODEL-ID>.step)."""
    m = re.match(r"^(?P<mid>.+?)-rev(?P<rev>[A-Z]{1,2})\.step(\.zip)?$", p.name, re.I)
    if m:
        return f"{m.group('mid')} Rev {m.group('rev')}"
    return re.sub(r"\.step(\.zip)?$", "", p.name, flags=re.I)


def _vec(s: str):
    v = tuple(float(x) for x in s.split(","))
    if len(v) != 3:
        raise argparse.ArgumentTypeError(f"{s!r}: three comma-separated numbers expected")
    return v


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Review snapshot PNG of a STEP model (not a drawing).")
    ap.add_argument("step", type=Path, help="model .step, or a filed .step.zip (unzipped to <project>/_work/unzipped/)")
    ap.add_argument("out", type=Path, help="PNG to write")
    ap.add_argument("--view", default="iso", help="iso, front, plan, end, or a direction x,y,z")
    ap.add_argument("--up", type=_vec, help="up vector x,y,z (default per view)")
    ap.add_argument("--title", help="model named in the caption (default: from the file name)")
    ap.add_argument("--label", default="", help="caption text before the model name")
    ap.add_argument("--only", help="regex on the node path: draw only matching leaves")
    ap.add_argument("--clip", help="x0,y0,z0,x1,y1,z1 in inches: draw only triangles inside this box")
    ap.add_argument("--size", default="2400x1600", help="W x H pixels")
    a = ap.parse_args(argv)
    repo = next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists())
    out = a.out.resolve()
    if (repo / "job") in out.parents and "06_Issued_Revisions" in out.parts:   # any project's filed folder
        print(f"render_png: ERROR - {out} is inside a filed folder (06_Issued_Revisions, TR-08); review PNGs go to "
              f"05_Reviews_Changes/01_Internal_Reviews/ or _work/ in the project folder")
        return 3
    src = a.step.resolve()
    if not src.is_file():
        print(f"render_png: ERROR - {src} not found (drive_store.py pull if only the pointer is here)")
        return 3
    if src.name.lower().endswith(".zip"):
        sys.path.insert(0, str(repo / "harness" / "lib"))
        import filed_step
        src = Path(filed_step.unzipped(src))
    if a.view in VIEWS:
        direction, up = VIEWS[a.view]
    else:
        direction, up = _vec(a.view), (0, 0, 1)
    up = a.up or up
    clip = None
    if a.clip:
        c = [float(x) * MM_PER_IN for x in a.clip.split(",")]
        if len(c) != 6:
            print("render_png: ERROR - --clip needs six numbers")
            return 3
        clip = (c[:3], c[3:])
    w, h = (int(x) for x in a.size.lower().split("x"))
    rx = re.compile(a.only) if a.only else None
    asm = bd.import_step(str(src))
    bodies = assembly_bodies(asm, select=(lambda p: bool(rx.search(p))) if rx else None)
    out.parent.mkdir(parents=True, exist_ok=True)
    render(bodies, str(out), direction, up=up, size=(w, h), label=a.label or f"{a.view} view",
           title=a.title or title_from_file(a.step), clip=clip)
    bb = [_bbox(b.shape) for b in bodies]
    lo = [min(getattr(x.min, k) for x in bb) / MM_PER_IN for k in "XYZ"] if bb else [math.nan] * 3
    hi = [max(getattr(x.max, k) for x in bb) / MM_PER_IN for k in "XYZ"] if bb else [math.nan] * 3
    print(f"render_png: wrote {out} ({len(bodies)} bodies, extent in X {lo[0]:.1f}..{hi[0]:.1f} "
          f"Y {lo[1]:.1f}..{hi[1]:.1f} Z {lo[2]:.1f}..{hi[2]:.1f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
