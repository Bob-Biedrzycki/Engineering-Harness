"""Drawing revision filing for every drawing generator in this repository.

Rules (CLAUDE.md "Git and drawing revisions"; harness/knowledge/Todd Requirements.md
TR-06, TR-07, TR-08; Bob 2026-09-24: revision letters are sequential, nobody
assigns them, NO EXCEPTIONS):

  * Every drawing handed off is filed under <project>/06_Issued_Revisions/Drawings/<DOC-ID>/
    as <DOC-ID>-rev<X>.dxf, .dwg (native, AutoCAD Core Console) and .pdf
    (exported from that DWG). Nothing else counts as a hand-off.
  * <X> is the next letter after the last revision in that folder's
    revisions.csv: A..Z, then AA, AB, ... Nobody picks, skips or reuses one.
  * A filed file is never modified, overwritten, renamed or deleted. This
    module refuses to write over an existing target and marks filed files
    read-only.
  * Every revision gets a revision-block row with a note and revision clouds
    around what changed since the previous filed revision.

Generators call, in order:
    rev   = next_rev(DOC_ID)                      # letter for the title block
    ...build the drawing with that letter and the note in its revision block...
    add_revision_clouds(doc, DOC_ID, rev, scale, exclude_below_y=..., fallback_prev=...)
    add_sheet_text_clouds(doc, DOC_ID, rev, [title, subtitles...], scale)   # when the title wording changed
    info  = file_drawing(DOC_ID, rev, doc, layouts, note, description, source)

Set CPME_DRAWINGS_ROOT to a scratch folder to test without filing for real.
"""
from __future__ import annotations

import csv
import datetime as _dt
import hashlib
import math
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import ezdxf
from ezdxf import bbox as _bbox

sys.path.insert(0, str(next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists()) / "harness" / "lib"))
import repo_paths as rp  # noqa: E402

rp.require_project("revfile.py")   # filing needs a project: no project yet = exit 2, nothing written
REPO = rp.REPO
DRAWINGS = rp.DRAWINGS                   # honours CPME_DRAWINGS_ROOT
WORK = rp.FILING                         # gitignored staging
DXF_TO_DWG = rp.CAD_LIB / "dxf-to-dwg.ps1"
DWG_TO_PDF = rp.CAD_LIB / "dwg-to-pdf.ps1"
MANIFEST_COLS = ["document_id", "revision", "file", "file_date", "sha256", "bytes", "source", "notes",
                 "description"]
CLOUD_LAYER = "P-ANNO-REVC"
MAX_BLOCK_NOTE = 32  # characters that fit the revision-block DESCRIPTION cell of the CPME title block
SHEET_FORMAT_LAYERS = {"P-ANNO-BORD", "P-ANNO-TTLB", "P-ANNO-LOGO", CLOUD_LAYER}


# --------------------------------------------------------------------------
# revision letters
# --------------------------------------------------------------------------
def _letter_to_int(s: str) -> int:
    n = 0
    for ch in s:
        if not ("A" <= ch <= "Z"):
            raise ValueError(f"revision {s!r} is not a letter sequence")
        n = n * 26 + (ord(ch) - 64)
    return n


def _int_to_letter(n: int) -> str:
    out = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        out = chr(65 + r) + out
    return out


def doc_dir(doc_id: str) -> Path:
    return DRAWINGS / doc_id


def manifest_rows(doc_id: str) -> list[dict]:
    p = doc_dir(doc_id) / "revisions.csv"
    if not p.exists():
        return []
    with open(p, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def last_rev(doc_id: str) -> str | None:
    revs = [r["revision"].strip() for r in manifest_rows(doc_id) if r.get("revision", "").strip()]
    if not revs:
        return None
    return max(revs, key=_letter_to_int)


def next_rev(doc_id: str) -> str:
    """Next sequential revision letter: A for a new drawing, else the letter after the last filed one."""
    last = last_rev(doc_id)
    nxt = "A" if last is None else _int_to_letter(_letter_to_int(last) + 1)
    for ext in (".dxf", ".dwg", ".pdf"):
        if (doc_dir(doc_id) / f"{doc_id}-rev{nxt}{ext}").exists():
            raise SystemExit(f"{doc_id} rev {nxt}{ext} already exists but is not in revisions.csv; "
                             "fix the manifest before filing (never overwrite)")
    return nxt


def check_note(note: str) -> str:
    note = (note or "").strip().upper()
    if not note:
        raise SystemExit("a revision-block note is required for every revision (TR-07)")
    if len(note) > MAX_BLOCK_NOTE:
        raise SystemExit(f"revision-block note is {len(note)} characters; the title block cell holds "
                         f"{MAX_BLOCK_NOTE}. Put the detail in --description.")
    return note


def today() -> str:
    return _dt.date.today().isoformat()


# --------------------------------------------------------------------------
# revision clouds
# --------------------------------------------------------------------------
def _r(v: float) -> float:
    return round(float(v), 3)


def _sig(e) -> tuple:
    t = e.dxftype()
    lay = e.dxf.get("layer", "0")
    try:
        if t == "TEXT":
            p = e.dxf.insert
            return (t, lay, e.dxf.text, _r(p.x), _r(p.y), _r(e.dxf.height))
        if t == "MTEXT":
            p = e.dxf.insert
            return (t, lay, e.text, _r(p.x), _r(p.y))
        if t == "LINE":
            a, b = sorted(((_r(e.dxf.start.x), _r(e.dxf.start.y)), (_r(e.dxf.end.x), _r(e.dxf.end.y))))
            return (t, lay, a, b)
        if t == "LWPOLYLINE":
            return (t, lay, bool(e.closed), tuple((_r(x), _r(y), _r(b)) for x, y, *_, b in e.get_points("xyseb")))
        if t == "CIRCLE":
            c = e.dxf.center
            return (t, lay, _r(c.x), _r(c.y), _r(e.dxf.radius))
        if t == "ARC":
            c = e.dxf.center
            return (t, lay, _r(c.x), _r(c.y), _r(e.dxf.radius), _r(e.dxf.start_angle), _r(e.dxf.end_angle))
        if t == "INSERT":
            p = e.dxf.insert
            att = tuple(sorted((a.dxf.tag, a.dxf.text) for a in e.attribs))
            return (t, lay, e.dxf.name, _r(p.x), _r(p.y), _r(e.dxf.get("xscale", 1)), _r(e.dxf.get("yscale", 1)),
                    _r(e.dxf.get("rotation", 0)), att)
    except Exception:  # noqa: BLE001 - fall back to the extents signature
        pass
    ext = _bbox.extents([e], fast=True)
    if not ext.has_data:
        return (t, lay, "no-extents")
    return (t, lay, _r(ext.extmin.x), _r(ext.extmin.y), _r(ext.extmax.x), _r(ext.extmax.y))


def _entities(doc, exclude_below_y: float | None):
    for e in doc.modelspace():
        if e.dxf.get("layer", "0") in SHEET_FORMAT_LAYERS:
            continue
        if exclude_below_y is not None:
            ext = _bbox.extents([e], fast=True)
            if ext.has_data and ext.extmax.y <= exclude_below_y:
                continue
        yield e


def _box(e):
    ext = _bbox.extents([e], fast=True)
    if not ext.has_data:
        return None
    return [ext.extmin.x, ext.extmin.y, ext.extmax.x, ext.extmax.y]


def _merge(boxes: list[list[float]], gap: float) -> list[list[float]]:
    boxes = [b[:] for b in boxes]
    changed = True
    while changed:
        changed = False
        out: list[list[float]] = []
        for b in boxes:
            for o in out:
                if b[0] - gap <= o[2] and o[0] - gap <= b[2] and b[1] - gap <= o[3] and o[1] - gap <= b[3]:
                    o[0], o[1], o[2], o[3] = min(o[0], b[0]), min(o[1], b[1]), max(o[2], b[2]), max(o[3], b[3])
                    changed = True
                    break
            else:
                out.append(b)
        boxes = out
    return boxes


def previous_dxf(doc_id: str) -> Path | None:
    last = last_rev(doc_id)
    if last is None:
        return None
    p = doc_dir(doc_id) / f"{doc_id}-rev{last}.dxf"
    return p if p.exists() else None


def changed_boxes(new_doc, old_doc, exclude_below_y: float | None, gap: float) -> list[list[float]]:
    """Boxes around entities added, changed or removed between old_doc and new_doc."""
    old = {}
    for e in _entities(old_doc, exclude_below_y):
        old.setdefault(_sig(e), []).append(e)
    new = {}
    for e in _entities(new_doc, exclude_below_y):
        new.setdefault(_sig(e), []).append(e)
    boxes = []
    for s, es in new.items():
        for e in es[len(old.get(s, [])):]:
            b = _box(e)
            if b:
                boxes.append(b)
    for s, es in old.items():
        for e in es[len(new.get(s, [])):]:
            b = _box(e)
            if b:
                boxes.append(b)
    return _merge(boxes, gap)


def _cloud(msp, box, rev: str, scale: float):
    pad, chord = 0.06 * scale, 0.12 * scale
    x1, y1, x2, y2 = box[0] - pad, box[1] - pad, box[2] + pad, box[3] + pad
    corners = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]  # counter-clockwise
    pts = []
    for (ax, ay), (bx, by) in zip(corners, corners[1:] + corners[:1]):
        n = max(1, round(math.hypot(bx - ax, by - ay) / chord))
        for i in range(n):
            pts.append((ax + (bx - ax) * i / n, ay + (by - ay) * i / n, 0, 0, -0.5))  # negative bulge = outward
    msp.add_lwpolyline(pts, format="xyseb", close=True, dxfattribs={"layer": CLOUD_LAYER})
    t = 0.2 * scale  # revision delta triangle at the top-right corner
    tri = [(x2, y2), (x2 + t, y2), (x2 + t / 2, y2 + t * 0.866)]
    msp.add_lwpolyline(tri, close=True, dxfattribs={"layer": CLOUD_LAYER})
    txt = msp.add_text(rev, dxfattribs={"layer": CLOUD_LAYER, "height": 0.085 * scale})
    txt.set_placement((x2 + t / 2, y2 + t * 0.30), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)


def add_revision_clouds(doc, doc_id: str, rev: str, scale: float = 1.0, exclude_below_y: float | None = None,
                        fallback_prev: Path | None = None) -> int:
    """Cloud everything that differs from the previous filed revision. Returns the number of clouds.

    exclude_below_y: skip the title-block band (it changes on every revision by design).
    fallback_prev:   DXF of the previous revision when none is filed yet (e.g. a source P&ID received as DXF).
    """
    prev = previous_dxf(doc_id) or fallback_prev
    if prev is None:
        return 0  # first revision: nothing to compare against
    if CLOUD_LAYER not in doc.layers:
        doc.layers.add(CLOUD_LAYER, color=1, lineweight=35)
    old_doc = ezdxf.readfile(prev)
    boxes = changed_boxes(doc, old_doc, exclude_below_y, gap=0.25 * scale)
    msp = doc.modelspace()
    for b in boxes:
        _cloud(msp, b, rev, scale)
    return len(boxes)


def add_box_clouds(doc, boxes, rev: str, scale: float = 1.0) -> int:
    """Cloud the given model-space boxes [x0, y0, x1, y1] (each with the revision delta).

    For a generator whose revision cannot be compared entity by entity with the previous filed revision
    (for example the first issue of a drawing from a new generator with a new layout): the caller decides
    the changed items from its own record (<project>/03_Working_Design/CAD/06_Drawings/Generators/model-to-pid.py uses the P&ID revision requests
    issued) and passes their extents here. Returns the number of clouds.
    """
    if CLOUD_LAYER not in doc.layers:
        doc.layers.add(CLOUD_LAYER, color=1, lineweight=35)
    msp = doc.modelspace()
    n = 0
    for b in boxes:
        _cloud(msp, b, rev, scale)
        n += 1
    return n


def add_sheet_text_clouds(doc, doc_id: str, rev: str, texts, scale: float = 1.0) -> int:
    """Cloud the title-block texts given (drawing title, subtitles: identity fields, not the revision
    letter, date or revision-block rows) whose wording differs from the previous filed revision.

    add_revision_clouds skips the sheet-format layers, because the revision fields there change on
    every revision by design. A change to the drawing's own title is a modified item and is clouded
    (TR-07). Returns the number of clouds.
    """
    prev = previous_dxf(doc_id)
    if prev is None:
        return 0
    old = {e.dxf.text for e in ezdxf.readfile(prev).modelspace().query("TEXT") if e.dxf.get("layer", "0") in SHEET_FORMAT_LAYERS}
    want = {t for t in texts if t}
    if CLOUD_LAYER not in doc.layers:
        doc.layers.add(CLOUD_LAYER, color=1, lineweight=35)
    msp = doc.modelspace()
    boxes = [_box(e) for e in msp.query("TEXT")
             if e.dxf.get("layer", "0") in SHEET_FORMAT_LAYERS - {CLOUD_LAYER} and e.dxf.text in want and e.dxf.text not in old]
    boxes = _merge([b for b in boxes if b], gap=0.05 * scale)
    for b in boxes:
        _cloud(msp, b, rev, scale)
    return len(boxes)


# --------------------------------------------------------------------------
# sheet layout (for drawings drawn in model space only)
# --------------------------------------------------------------------------
def add_sheet_layout(doc, sheet_w: float, sheet_h: float, name: str = "01-SHEET",
                     paper_in: tuple[float, float] = (34.0, 22.0),
                     media: str = "ANSI_D_(34.00_x_22.00_Inches)") -> str:
    """Add one paperspace layout with a viewport that fits the whole model-space sheet, set up for
    'DWG To PDF.pc3' (CPME standard plot setup)."""
    if "P-ANNO-VPRT" not in doc.layers:
        doc.layers.add("P-ANNO-VPRT", color=8).dxf.plot = 0
    pw, ph = paper_in
    lay = doc.layouts.new(name)
    lay.page_setup(size=(pw, ph), margins=(0, 0, 0, 0), units="inch", scale=(1, 1), name=media,
                   device="DWG To PDF.pc3")
    for vp in lay.query("VIEWPORT"):
        if vp.dxf.id == 1:
            vp.dxf.layer = "0"
    lay.set_plot_type(5)
    view_h = max(sheet_h, sheet_w * ph / pw) * 1.01
    vp = lay.add_viewport(center=(pw / 2, ph / 2), size=(pw, ph), view_center_point=(sheet_w / 2, sheet_h / 2),
                          view_height=view_h, dxfattribs={"layer": "P-ANNO-VPRT", "flags": 16384})
    vp.dxf.id = 2
    lay.dxf_layout.dxf.plot_layout_flags = lay.dxf_layout.dxf.plot_layout_flags | 128 | 32
    for n in [n for n in doc.layouts.names() if n not in ("Model", name)]:
        doc.layouts.delete(n)
    doc.layouts.set_active_layout(name)
    doc.header["$TILEMODE"] = 0
    return name


# --------------------------------------------------------------------------
# filing
# --------------------------------------------------------------------------
def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _ps(script: Path, *args: str, cwd: Path | None = None) -> str:
    cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), *args]
    # Core Console writes plot.log and ErrorReports\ into its working folder: run it in the
    # gitignored staging folder, never the repo root.
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=1500, cwd=cwd)
    if r.returncode != 0:
        raise SystemExit(f"{script.name} failed:\n{r.stdout}\n{r.stderr}")
    return r.stdout


def file_drawing(doc_id: str, rev: str, doc, layouts: list[str], note: str, description: str,
                 source: str) -> dict:
    """Write DXF, DWG and PDF for one revision and file them. Refuses to overwrite anything."""
    if rev != next_rev(doc_id):
        raise SystemExit(f"{doc_id}: rev {rev} is not the next sequential letter ({next_rev(doc_id)})")
    stem = f"{doc_id}-rev{rev}"
    dest = doc_dir(doc_id)
    targets = {ext: dest / f"{stem}{ext}" for ext in (".dxf", ".dwg", ".pdf")}
    for p in targets.values():
        if p.exists():
            raise SystemExit(f"refusing to overwrite filed drawing {p}")

    stage = WORK / stem
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    sdxf, sdwg, spdf = (stage / f"{stem}{ext}" for ext in (".dxf", ".dwg", ".pdf"))
    doc.saveas(sdxf)
    audit = ezdxf.readfile(sdxf).audit()
    if audit.has_errors:
        raise SystemExit(f"DXF audit failed ({len(audit.errors)} errors); nothing filed")
    _ps(DXF_TO_DWG, "-Dxf", str(sdxf), "-Layouts", ",".join(layouts), "-WorkDir", str(stage / "acad"), cwd=stage)
    _ps(DWG_TO_PDF, "-Dwg", str(sdwg), "-Pdf", str(spdf), "-FirstLayout", layouts[0],
        "-ExpectPages", str(len(layouts)), "-WorkDir", str(stage / "acad"), cwd=stage)
    for p in (sdxf, sdwg, spdf):
        if not p.exists() or p.stat().st_size == 0:
            raise SystemExit(f"{p.name} was not produced; nothing filed")

    dest.mkdir(parents=True, exist_ok=True)
    for p in targets.values():  # re-check just before moving
        if p.exists():
            raise SystemExit(f"refusing to overwrite filed drawing {p}")
    stamp = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    rows = []
    for ext, src in ((".pdf", spdf), (".dwg", sdwg), (".dxf", sdxf)):
        dst = targets[ext]
        shutil.move(str(src), str(dst))
        os.chmod(dst, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)  # filed = read-only
        rows.append({"document_id": doc_id, "revision": rev, "file": dst.name, "file_date": stamp,
                     # notes = the revision-block note exactly as on the sheet (empty for line-segment-diagram
                     # Revs A and B, which carried it only at the head of description; fixed 2026-10-02)
                     "sha256": _sha(dst), "bytes": dst.stat().st_size, "source": source, "notes": note,
                     "description": description or note})

    man = dest / "revisions.csv"
    existing = manifest_rows(doc_id)
    cols = list(MANIFEST_COLS)
    for r in existing:
        for k in r:
            if k not in cols:
                cols.append(k)
    with open(man, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in existing + rows:
            w.writerow({k: r.get(k, "") for k in cols})
    return {"revision": rev, "files": [str(targets[e]) for e in (".pdf", ".dwg", ".dxf")],
            "sha256": {r["file"]: r["sha256"] for r in rows}}
