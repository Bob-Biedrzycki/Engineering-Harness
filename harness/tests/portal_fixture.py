"""A small synthetic filed model revision set for the project tracker builder (tests and the fixture preview build).

Writes, under a root folder the caller names (a temp folder; never 06_Issued_Revisions/), what model_file.py files for
a revision: <root>/<MODEL-ID>/revisions.csv and <MODEL-ID>-rev<X>-<takeoff>.csv / -layout-note.md / -manifest.json /
-pipe-support-calc.md, for Rev A and Rev B, plus a media folder with a tiny web GLB (one box per group). Every tag,
line and spool here is a fixture name (FX-...), never a project tag; the takeoff columns are the ones the tracker
reads. build_portal.py reads the root through CPME_PORTAL_MODELS_ROOT (harness/lib/repo_paths.py PORTAL_MODELS).

    .\\harness\\tools\\venv\\Scripts\\python.exe harness\\tests\\portal_fixture.py <root>    # writes the fixture, prints the paths
"""
from __future__ import annotations

import csv
import json
import struct
import sys
from pathlib import Path

LINE_A, LINE_B = "FX-101", "FX-102"   # fixture line numbers (not on any P&ID)
REVS = (("A", "2026-10-30 08:00", "Fixture first revision"), ("B", "2026-10-30 09:00", "Fixture second revision"))

TAKEOFFS = {
    "spool-list": (["spool_id", "line_no", "od_in", "from", "to", "pieces", "tube_total_in", "elbows", "tees", "ferrules", "welds", "centerline_in"],
                   [[f"{LINE_A}-SP01", LINE_A, "2.0", "FX-E01", "FX-V01", "3", "48.5", "2", "0", "2", "4", "60.0"],
                    [f"{LINE_B}-SP01", LINE_B, "1.5", "FX-V01", "FX-E02", "2", "30.0", "1", "1", "2", "3", "40.0"]]),
    "weld-map": (["weld_id", "spool_id", "line_no", "od_in", "x_in", "y_in", "z_in", "between", "type"],
                 [[f"{LINE_A}-SP01-W01", f"{LINE_A}-SP01", LINE_A, "2.0", "10", "5", "20", "pc01 / pc02", "orbital butt"],
                  [f"{LINE_B}-SP01-W01", f"{LINE_B}-SP01", LINE_B, "1.5", "30", "5", "20", "pc01 / pc02", "orbital butt"]]),
    "clamp-schedule": (["joint_id", "line_no", "size_od_in", "side_a", "side_b", "clamp", "gasket", "x_in", "y_in", "z_in"],
                       [["J001", LINE_A, "2.0", f"{LINE_A}-SP01", "FX-V01", "2 in clamp", "2 in gasket", "40", "5", "20"]]),
    "fittings-by-spool": (["piece_id", "spool_id", "line_no", "kind", "description", "qty", "source"],
                          [[f"{LINE_A}-SP01.pc02", f"{LINE_A}-SP01", LINE_A, "elbow", "2 in 90 deg elbow", "1", "fixture"],
                           [f"{LINE_B}-SP01.pc02", f"{LINE_B}-SP01", LINE_B, "tee", "1.5 in tee", "1", "fixture"]]),
    "bom-model": (["class", "item", "size_or_section", "qty", "source", "note"],
                  [["tube", "fixture tube", "2.0 in OD", "1", "fixture", ""], ["foot", "FX-FT01", "M16, >= 2,000 lb", "4", "fixture", ""]]),
    "cut-list-piping": (["piece_id", "spool_id", "line_no", "od_in", "wall_in", "spec_grade", "cut_length_in", "cut_length_frac16_in", "qty", "ends"],
                        [[f"{LINE_A}-SP01.pc01", f"{LINE_A}-SP01", LINE_A, "2.0", "0.065", "fixture", "24.25", "24 4/16", "1", "square"],
                         [f"{LINE_B}-SP01.pc01", f"{LINE_B}-SP01", LINE_B, "1.5", "0.065", "fixture", "12.0", "12", "1", "square"]]),
    "cut-list-frame": (["member", "kind", "section", "material", "cut_length_in", "cut_length_frac16_in", "qty", "axis", "role"],
                       [["FM-001", "rail", "fixture section", "fixture", "120", "120", "2", "X", "base rail"]]),
    "routing-report": (["check", "object", "line_no", "value", "limit", "result", "length_in", "direction"],
                       [["slope", f"{LINE_A}-SP01", LINE_A, "0.012", "0.010", "ok", "24", "-X"],
                        ["dead leg", f"{LINE_B}-SP01", LINE_B, "1.5", "2.0", "ok", "3", "+Z"]]),
    "piping-mass": (["object", "kind", "line_no", "od_in", "mass_lb", "liquid_in3", "method", "x_in", "y_in", "z_in"],
                    [[f"{LINE_A}-SP01.pc01", "tube", LINE_A, "2.0", "3.2", "70", "fixture", "10", "5", "20"],
                     [f"{LINE_A}-SP01.pc02", "elbow", LINE_A, "2.0", "0.8", "10", "fixture", "20", "5", "20"]]),
    "pipe-support-calc": (["support", "load_lb", "rod", "rod_d_in", "rod_len_in", "stress_ratio", "euler_margin", "sway_at_5lb_in", "largest"],
                          [["PS-001", "12.5", "fixture rod", "0.375", "10", "0.05", "40", "0.01", LINE_A]]),
}


def _wcsv(p: Path, cols: list[str], rows: list[list[str]]) -> None:
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        w.writerows(rows)


def make_glb(path: Path, groups: list[str]) -> None:
    """A tiny binary glTF: one cube mesh per named group node (node "<group>" > child "<group>_item"), in metres."""
    v = [(x, y, z) for x in (0, 1) for y in (0, 1) for z in (0, 1)]
    faces = [(0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5), (0, 4, 5), (0, 5, 1), (2, 3, 7), (2, 7, 6), (0, 2, 6), (0, 6, 4), (1, 5, 7), (1, 7, 3)]
    pos = b"".join(struct.pack("<3f", *(c * 0.3 for c in p)) for p in v)
    idx = b"".join(struct.pack("<3H", *f) for f in faces)
    idx += b"\0" * (-len(idx) % 4)
    bin_ = pos + idx
    nodes, top = [], []
    for i, g in enumerate(groups):
        nodes.append({"name": g, "children": [len(nodes) + 1], "translation": [i * 0.5, 0, 0]})
        nodes.append({"name": f"{g}_item", "mesh": 0})
        top.append(len(nodes) - 2)
    g = {"asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": top}], "nodes": nodes,
         "meshes": [{"primitives": [{"attributes": {"POSITION": 0}, "indices": 1, "material": 0}]}],
         "materials": [{"name": "fixture steel", "pbrMetallicRoughness": {"baseColorFactor": [0.7, 0.72, 0.75, 1], "metallicFactor": 0.8, "roughnessFactor": 0.35}}],
         "accessors": [{"bufferView": 0, "componentType": 5126, "count": 8, "type": "VEC3", "min": [0, 0, 0], "max": [0.3, 0.3, 0.3]},
                       {"bufferView": 1, "componentType": 5123, "count": 36, "type": "SCALAR"}],
         "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": len(pos)}, {"buffer": 0, "byteOffset": len(pos), "byteLength": 72}],
         "buffers": [{"byteLength": len(bin_)}]}
    js = json.dumps(g).encode()
    js += b" " * (-len(js) % 4)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.write(struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(bin_)))
        f.write(struct.pack("<II", len(js), 0x4E4F534A) + js)
        f.write(struct.pack("<II", len(bin_), 0x004E4942) + bin_)


def make_fixture(root: Path, model_id: str, revs=REVS) -> dict:
    """Write the fixture revisions under root/<model_id>/ and a media folder root/media/ (skid-web.glb). Returns the
    paths: {"models": root, "media": root/media}."""
    doc_folder = root / model_id
    doc_folder.mkdir(parents=True, exist_ok=True)
    rows = []
    for rev, date, note in revs:
        base = f"{model_id}-rev{rev}"
        folder = doc_folder / base   # one folder per filed revision (repo_paths.rev_folder)
        folder.mkdir(exist_ok=True)
        for k, (cols, data) in TAKEOFFS.items():
            _wcsv(folder / f"{base}-{k}.csv", cols, data)
        (folder / f"{base}-layout-note.md").write_text(
            f"# Layout note, {model_id} Rev {rev} (fixture)\n\n- Overall: 150.0 in L x 55.0 in W x 90.0 in H\n"
            f"- Base X 0 to 120 in\n", encoding="utf-8")
        (folder / f"{base}-pipe-support-calc.md").write_text("# Pipe support calc (fixture)\n\nResult: PASS\n", encoding="utf-8")
        (folder / f"{base}-manifest.json").write_text(json.dumps({"items": [
            {"tag": "FX-V01", "line": LINE_A, "group": "valves", "kind": "valve"},
            {"tag": "FX-FT01", "group": "feet", "kind": "foot", "bbox_in": [[0, 0, 0], [3, 3, 3]]}]}), encoding="utf-8")
        for f in sorted(folder.glob(f"{base}*")):
            rows.append({"document_id": model_id, "revision": rev, "file": f"{base}/{f.name}", "file_date": date, "sha256": "0" * 64,
                         "bytes": f.stat().st_size, "source": "fixture", "notes": note, "description": f"{note} (fixture, not a design)"})
    with open(doc_folder / "revisions.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    media = root / "media"
    make_glb(media / "skid-web.glb", [f"piping_{LINE_A}", f"piping_{LINE_B}", "valves", "frame", "equipment"])
    return {"models": root, "media": media}


if __name__ == "__main__":
    sys.path.insert(0, str(next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists()) / "harness" / "lib"))
    import repo_paths as rp
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    out = make_fixture(Path(sys.argv[1]).resolve(), rp.SKID_MODEL_ID)
    print(json.dumps({k: str(v) for k, v in out.items()}))
