"""CPME sheet format: border, grid letters, header band, DRAFT stamp and the
CPME title block with logo, for every drawing generated in this repository.

Rule (Bob, chat, 2026-09-23): every new drawing carries the CPME title block.
Rule (Bob, chat, 2026-09-24): revision letters are sequential, nobody assigns
them, no exceptions. draw_cpme_sheet refuses a missing or '-' revision.

Geometry is taken from the CPME standard sheet format, a 17 x 11 in
sheet: outer border 0.25 in, inner border 0.375 in,
title block from y 0.375 to 1.417 in with cell dividers at x 3.194, 7.222,
11.528, 13.056 and 14.375 in, revision block columns at 14.931 and 16.181 in,
logo block CPME_LOGO_EMBEDDED at (0.528, 0.556) in. Text heights and positions
are the standard values. Everything is scaled by W / 17 so the block keeps the
P&ID proportions on any sheet width; taller sheets get more grid rows.

The logo (vector hatches, CPME's own artwork) is the block CPME_LOGO_EMBEDDED in the harness asset
harness/cad-lib/cpme-logo.dxf (provenance in cpme-logo.md; CPME practice, 2026-10-26). If that file is
missing or unreadable a plain "CPME" placeholder is drawn and the caller is told, so the drawing still generates.

Usage (see line-segment-diagram.py / process-flow-diagram.py):
    from cpme_titleblock import draw_cpme_sheet, reserved_bands
    top, bottom = reserved_bands(W)       # keep drawing content out of these
    warnings = draw_cpme_sheet(sh, doc, W, H, fields)

`sh` must provide sh.text(s, x, y, cap, layer, align, bold=..., rgb=...) and
sh.pline(pts, layer, close=..., owner=...) so the title block texts take part
in the caller's overlap check.
"""
from __future__ import annotations

import sys
from pathlib import Path

import ezdxf
from ezdxf.addons.importer import Importer

sys.path.insert(0, str(next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists()) / "harness" / "lib"))
import repo_paths as rp  # noqa: E402

REPO = rp.REPO
SHEET_W_IN = 17.0
LOGO_BLOCK = "CPME_LOGO_EMBEDDED"
LAYERS = {  # name: (rgb, aci)
    "P-ANNO-BORD": ((0, 0, 0), 7),
    "P-ANNO-TTLB": ((0, 0, 0), 7),
    "P-ANNO-LOGO": ((0, 0, 0), 7),
}
DEFAULT_FIELDS = {
    "company": "CPME USA",
    "address": ("441 MILWAUKEE AVE STE 6", "BURLINGTON WI 53105"),
    # project identity from <project>/project.yaml (<project> = rp.PROJECT).
    # The keys name the sheet's cells as drawn on the standard sheet format ("job_title", "project"), not our terms
    "header": f"CPME USA  /  {rp.CUSTOMER.upper()}",
    "job_title": rp.PROJECT_INFO["skid_title"],
    "header_subtitle": "",
    "project": rp.CUSTOMER.upper(),
    "location": rp.PROJECT_INFO["location"],
    "number": f"{rp.PROJECT_CODE} / N/A",
    "title": "",
    "subtitle": rp.PROJECT_INFO["skid_title"],
    "source_line": "",
    "revision": None,  # required: the next sequential letter from harness/cad-lib/revfile.next_rev (Bob 2026-09-24)
    "sheet": "1 OF 1",
    "rev_rows": (),  # required: ((rev, note, date),) for the current revision (TR-07)
    "appr": "",
    "revision_sub": "",  # small red line under the revision letter, e.g. "FAST-004" on a P&ID fast edit (Bob, 2026-10-11)
    "stamp": ("DRAFT - FOR ENGINEERING REVIEW", "NOT FOR CONSTRUCTION OR OPERATION"),
}


def reserved_bands(W: float) -> tuple[float, float]:
    """(top, bottom) heights in drawing units that the sheet format occupies."""
    s = W / SHEET_W_IN
    return 1.50 * s, 1.50 * s


LOGO_DXF = rp.CAD_LIB / "cpme-logo.dxf"   # harness asset; provenance in cpme-logo.md (CPME practice)


def logo_dxf_path() -> Path:
    return LOGO_DXF


def _ensure_layers(doc):
    for name, (rgb, aci) in LAYERS.items():
        if name not in doc.layers:
            doc.layers.add(name, color=aci, true_color=ezdxf.rgb2int(rgb), lineweight=35)


def _import_logo(doc) -> str | None:
    if LOGO_BLOCK in doc.blocks:
        return None
    src = logo_dxf_path()
    if not src.is_file():
        return f"logo: {src} not found; placeholder drawn"
    try:
        sdoc = ezdxf.readfile(src)
        imp = Importer(sdoc, doc)
        imp.import_block(LOGO_BLOCK)
        imp.finalize()
        return None
    except Exception as ex:  # noqa: BLE001
        return f"logo: import failed ({ex}); placeholder drawn"


def draw_cpme_sheet(sh, doc, W: float, H: float, fields: dict) -> list[str]:
    f = {**DEFAULT_FIELDS, **fields}
    rev = f["revision"]
    if not rev or not str(rev).isalpha() or not str(rev).isupper():
        raise ValueError(f"revision {rev!r}: every drawing carries its sequential revision letter "
                         "(CLAUDE.md, Bob 2026-09-24, no exceptions); get it from harness/cad-lib/revfile.next_rev")
    if not f["rev_rows"] or list(f["rev_rows"])[-1][0] != rev:
        raise ValueError("rev_rows must end with a row for the current revision (TR-07)")
    s = W / SHEET_W_IN
    warnings: list[str] = []
    _ensure_layers(doc)
    msp = doc.modelspace()

    def X(v):
        return v * s

    def Y(v):  # from the bottom, inches
        return v * s

    def YT(v):  # inches below the top edge
        return H - v * s

    def T(txt, x, y, h, align="L", bold=False, layer="P-ANNO-TTLB", rgb=None):
        if txt:
            sh.text(txt, x, y, h * s, layer, align, bold=bold, rgb=rgb)

    def L(a, b, layer="P-ANNO-BORD"):
        sh.pline([a, b], layer, owner="sheet format")

    # ---- borders ----------------------------------------------------------
    for m in (0.25, 0.375):
        sh.pline([(X(m), Y(m)), (W - X(m), Y(m)), (W - X(m), H - X(m)), (X(m), H - X(m))], "P-ANNO-BORD",
                 close=True, owner="sheet format")
    # grid: column numbers along the top, row letters down both sides (standard pitch)
    ncol = int((SHEET_W_IN - 0.5) / 1.0155)
    for i in range(ncol):
        T(str(i + 1), X(0.88 + i * 1.0155), YT(0.35), 0.048, "C")
    y = YT(0.97)
    k = 0
    while y > Y(1.9) and k < 26:
        T(chr(ord("A") + k), X(0.31), y, 0.048, "C")
        T(chr(ord("A") + k), W - X(0.31), y, 0.048, "C")
        y -= 1.152 * s
        k += 1

    # ---- header band ------------------------------------------------------
    T(f["header"], X(0.53), YT(0.65), 0.113, "L", bold=True)
    T(f["job_title"], X(0.53), YT(1.01), 0.247, "L", bold=True)
    T(f["header_subtitle"], X(0.53), YT(1.31), 0.103, "L")
    stamp = f["stamp"]
    if stamp:
        T(stamp[0], X(14.65), YT(0.75), 0.103, "C", bold=True, rgb=(200, 0, 0))
        if len(stamp) > 1:
            T(stamp[1], X(14.65), YT(1.03), 0.082, "C", rgb=(200, 0, 0))

    # ---- title block cells -----------------------------------------------
    yb, yt = Y(0.5), Y(1.417)
    L((X(0.375), yt), (W - X(0.375), yt))
    for xv in (3.194, 7.222, 11.528, 13.056, 14.375):
        L((X(xv), yt), (X(xv), yb))
    for yv in (1.111, 0.806):
        L((X(3.194), Y(yv)), (X(7.222), Y(yv)))
    for yv in (1.111, 0.806, 0.5):
        L((X(14.375), Y(yv)), (W - X(0.375), Y(yv)))
    for xv in (14.931, 16.181):
        L((X(xv), yt), (X(xv), yb))
    L((X(0.375), yb), (X(14.375), yb))

    # logo + company
    warn = _import_logo(doc)
    if warn is None:
        ins = msp.add_blockref(LOGO_BLOCK, (X(0.528), Y(0.556)), dxfattribs={"layer": "P-ANNO-LOGO",
                                                                          "xscale": s, "yscale": s})
        ins.set_xdata("CPME_TAG", [(1000, "cpme logo")]) if "CPME_TAG" in doc.appids else None
    else:
        warnings.append(warn)
        sh.pline([(X(0.53), Y(0.56)), (X(1.45), Y(0.56)), (X(1.45), Y(1.25)), (X(0.53), Y(1.25))], "P-ANNO-LOGO",
                 close=True, owner="logo placeholder")
        T("CPME", X(0.99), Y(0.85), 0.2, "C", bold=True, layer="P-ANNO-LOGO")
    T(f["company"], X(1.61), Y(1.06), 0.092, "L", bold=True)
    addr = f["address"]
    T(addr[0], X(1.61), Y(0.85), 0.067)
    if len(addr) > 1:
        T(addr[1], X(1.61), Y(0.69), 0.067)
    # project / location / number
    T("PROJECT", X(3.31), Y(1.21), 0.064, bold=True)
    T(f["project"], X(4.31), Y(1.21), 0.074)
    T("LOCATION", X(3.31), Y(0.9), 0.064, bold=True)
    T(f["location"], X(4.31), Y(0.9), 0.074)
    T("NUMBER / PANEL", X(3.31), Y(0.6), 0.064, bold=True)
    T(f["number"], X(4.31), Y(0.6), 0.074)
    # drawing title cell
    xc = X((7.222 + 11.528) / 2)
    T(f["title"], xc, Y(1.03), 0.098, "C", bold=True)
    T(f["subtitle"], xc, Y(0.75), 0.082, "C")
    T(f["source_line"], xc, Y(0.56), 0.05, "C", rgb=(105, 105, 105))
    # revision / sheet
    T("REVISION", X(12.29), Y(1.15), 0.064, "C", bold=True)
    T(f["revision"], X(12.29), Y(0.86), 0.144, "C", bold=True)
    T(f["revision_sub"], X(12.29), Y(0.62), 0.072, "C", bold=True, rgb=(200, 0, 0))
    T("SHEET", X(13.72), Y(1.15), 0.064, "C", bold=True)
    T(f["sheet"], X(13.72), Y(0.86), 0.092, "C", bold=True)
    # revision block
    T("REV", X(14.46), Y(1.21), 0.057, bold=True)
    T("DESCRIPTION", X(15.0), Y(1.21), 0.057, bold=True)
    T("DATE", X(16.25), Y(1.21), 0.057, bold=True)
    rows = list(f["rev_rows"])[-1:]  # the standard block has one row; keep the newest
    for (rev, desc, date) in rows:
        # the note must fit its cell (DESCRIPTION 15.0 in to the DATE text at about 16.15 in): a 32-character
        # limit alone is not enough for wide upper-case text (LSD Rev B, 2026-10-02, ran into the date)
        if desc and hasattr(sh, "width") and sh.width(desc, 0.057 * s, False) > X(16.15 - 15.0):
            raise ValueError(f"revision-block note {desc!r} is wider than the DESCRIPTION cell; shorten it")
        T(rev, X(14.54), Y(0.9), 0.067, bold=True)
        T(desc, X(15.0), Y(0.9), 0.057)
        T(date, X(16.4), Y(0.9), 0.053, "C")
    T("APPR.", X(14.46), Y(0.6), 0.057, bold=True)
    T(f["appr"], X(15.0), Y(0.6), 0.057)
    return warnings
