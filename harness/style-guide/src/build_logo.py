"""Build the CPME vector logo (SVG) from measured geometry.

No original vector artwork for the CPME logo exists on Bob's computer (searched 2026-11-11: no AI, EPS, PDF or
SVG source; the portal SVG and cad-lib/cpme-logo.dxf are both traced pixel runs of the 288 x 216 px bitmap).
Bob, chat, 2026-11-11: "The vector logo should be somewhere on this computer, or you need to create it."

So this script creates it. Every shape was fitted to the original bitmap (assets/cpme-logo-original.png):
  - navy "C": ellipse E1 minus ellipse E2 (fit rms 0.25 and 0.14 px)
  - steel "C": ellipse G_out minus ellipse G_in (rms 0.17 and 0.12 px), minus the band between two straight
    cut lines (rms 0.12 and 0.15 px) that opens the C to the right
  - "CPME": Dubai Bold outlines (Windows font; closest of the installed fonts in weight, spacing and the
    short middle V of the M), each letter fitted to its measured box on the bitmap
Units are pixels of the 288 x 216 px source, y down. Colours are CPME Navy and CPME Steel (README section 4).
Check against the bitmap (2026-11-11): 97.9 % of pixels the same colour class; navy overlap 0.97, steel 0.89.

Run:  harness/tools/venv/Scripts/python.exe harness/style-guide/src/build_logo.py
Writes assets/cpme-logo.svg. Needs numpy and fontTools (repo venv) and C:/Windows/Fonts/DUBAI-BOLD.TTF.
The SVG holds the letters as outlines, so it needs no font where it is used.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "assets" / "cpme-logo.svg"
FONT = Path("C:/Windows/Fonts/DUBAI-BOLD.TTF")

NAVY = "#0D1554"
STEEL = "#7E849E"

# (cx, cy, rx, ry), source px, fitted to the bitmap 2026-11-11
# Edges are the 50 % brightness crossing between white and the colour (rms of each fit in brackets).
E1 = (139.90, 109.65, 139.11, 106.96)      # navy C, outer edge (0.25 px)
E2 = (201.45, 111.02, 130.75, 105.07)      # navy C, inner edge, cut out (0.14 px)
G_OUT = (192.91, 111.95, 99.41, 85.89)     # steel C, outer edge (0.17 px)
G_IN = (139.06, 112.28, 71.61, 62.17)      # steel C, inner edge, cut out (0.12 px)
TOP_CUT = ((236.75, 71.79), (0.9833, -0.1821))    # point, direction: lower edge of the top arm (0.12 px)
BOT_CUT = ((243.50, 142.52), (-0.9977, -0.0682))  # upper edge of the bottom arm (0.15 px)
# letter boxes measured on the bitmap: (left x, right x); cap top and baseline y
LETTERS = {"C": (178.0, 201.0), "P": (205.0, 226.0), "M": (231.0, 262.0), "E": (267.0, None)}  # E clipped by the edge
CAP_TOP, BASELINE = 95.0, 127.0


def ell_pt(e, t):
    cx, cy, rx, ry = e
    return np.array([cx + rx * math.cos(t), cy + ry * math.sin(t)])


def ell_t(e, p):
    cx, cy, rx, ry = e
    return math.atan2((p[1] - cy) / ry, (p[0] - cx) / rx)


def inside(e, p):
    cx, cy, rx, ry = e
    return ((p[0] - cx) / rx) ** 2 + ((p[1] - cy) / ry) ** 2


def ell_ell(a, b, near):
    """Intersection of two ellipses nearest to `near` (Newton on the parameter of a)."""
    t = ell_t(a, near)
    for _ in range(80):
        f = inside(b, ell_pt(a, t)) - 1
        h = 1e-6
        df = (inside(b, ell_pt(a, t + h)) - 1 - f) / h
        t -= f / df
    return ell_pt(a, t)


def line_ell(line, e, near):
    (px, py), (dx, dy) = line
    cx, cy, rx, ry = e
    # ((px+s dx - cx)/rx)^2 + ((py+s dy - cy)/ry)^2 = 1
    A = (dx / rx) ** 2 + (dy / ry) ** 2
    B = 2 * ((px - cx) * dx / rx ** 2 + (py - cy) * dy / ry ** 2)
    C = ((px - cx) / rx) ** 2 + ((py - cy) / ry) ** 2 - 1
    disc = math.sqrt(B * B - 4 * A * C)
    pts = [np.array([px + s * dx, py + s * dy]) for s in ((-B - disc) / (2 * A), (-B + disc) / (2 * A))]
    return min(pts, key=lambda q: np.hypot(*(q - np.array(near))))


def arc(e, p_from, p_to, via):
    """SVG arc command along ellipse e from p_from to p_to, passing near `via`."""
    t0, t1, tv = ell_t(e, p_from), ell_t(e, p_to), ell_t(e, via)
    d_pos = (t1 - t0) % (2 * math.pi)            # going with increasing t (clockwise on screen, y down)
    v_pos = (tv - t0) % (2 * math.pi)
    if v_pos <= d_pos:
        sweep, span = 1, d_pos
    else:
        sweep, span = 0, 2 * math.pi - d_pos
    large = 1 if span > math.pi else 0
    _, _, rx, ry = e
    return f"A{rx:.3f} {ry:.3f} 0 {large} {sweep} {p_to[0]:.3f} {p_to[1]:.3f}"


def P(p):
    return f"{p[0]:.3f} {p[1]:.3f}"


def navy_c() -> str:
    top = ell_ell(E1, E2, (165, 7))
    bot = ell_ell(E1, E2, (157, 212))
    return (f"M{P(top)} {arc(E1, top, bot, (3, 110))} "
            f"{arc(E2, bot, top, (70, 110))} Z")


def steel_arms() -> str:
    lt = ell_ell(G_OUT, G_IN, (122.6, 51.8))
    rt = line_ell(TOP_CUT, G_OUT, (275.6, 65.1))
    mt = line_ell(TOP_CUT, G_IN, (198.1, 78.1))
    lb = ell_ell(G_OUT, G_IN, (125.0, 172.5))
    rb = line_ell(BOT_CUT, G_OUT, (285.6, 146.6))
    mb = line_ell(BOT_CUT, G_IN, (202.1, 139.8))
    top = f"M{P(lt)} {arc(G_OUT, lt, rt, (190, 25))} L{P(mt)} {arc(G_IN, mt, lt, (160, 53))} Z"
    bot = f"M{P(lb)} {arc(G_OUT, lb, rb, (190, 198))} L{P(mb)} {arc(G_IN, mb, lb, (160, 170))} Z"
    return top + " " + bot


def letters() -> tuple[str, float]:
    font = TTFont(FONT)
    gs = font.getGlyphSet()
    cmap = font.getBestCmap()
    from fontTools.pens.boundsPen import BoundsPen
    bounds = {}
    for ch in LETTERS:
        bp = BoundsPen(gs)
        gs[cmap[ord(ch)]].draw(bp)
        bounds[ch] = bp.bounds
    # each letter is fitted to its measured box: height = cap top to baseline, width = measured width
    sx_seen = []
    paths, right = [], 0.0
    for ch, (x0, x1) in LETTERS.items():
        xmin, ymin, xmax, ymax = bounds[ch]
        sy = (BASELINE - CAP_TOP) / (ymax - ymin)
        sx = (x1 - x0) / (xmax - xmin) if x1 is not None else sum(sx_seen) / len(sx_seen)
        sx_seen.append(sx)
        pen = SVGPathPen(gs)
        # x' = x0 + (x - xmin) * sx ; y' = BASELINE - (y - ymin) * sy
        tp = TransformPen(pen, (sx, 0, 0, -sy, x0 - xmin * sx, BASELINE + ymin * sy))
        gs[cmap[ord(ch)]].draw(tp)
        paths.append(pen.getCommands())
        right = max(right, x0 + (xmax - xmin) * sx)
    return " ".join(paths), right


def main() -> None:
    text, right = letters()
    # canvas: the whole artwork (the bitmap cut the bottom of the navy C off), 0.5 px margin
    bot = ell_ell(E1, E2, (157, 212))
    x0 = E1[0] - E1[2] - 0.5
    y0 = min(ell_ell(E1, E2, (165, 7))[1], E1[1] - E1[3], G_OUT[1] - G_OUT[3]) - 0.5
    y1 = max(bot[1], E1[1] + E1[3]) + 0.5
    x1 = max(right, G_OUT[0] + G_OUT[2]) + 0.5
    w, h = x1 - x0, y1 - y0
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x0:.2f} {y0:.2f} {w:.2f} {h:.2f}" '
        f'width="{w:.1f}" height="{h:.1f}">\n'
        f'  <title>CPME USA</title>\n'
        f'  <!-- Built by harness/style-guide/src/build_logo.py from shapes fitted to assets/cpme-logo-original.png. -->\n'
        f'  <path fill="{NAVY}" d="{navy_c()}"/>\n'
        f'  <path fill="{STEEL}" d="{steel_arms()}"/>\n'
        f'  <path fill="{NAVY}" d="{text}"/>\n'
        f'</svg>\n'
    )
    OUT.write_text(svg, encoding="utf-8")
    print(f"wrote {OUT} ({len(svg)} bytes), viewBox {x0:.2f} {y0:.2f} {w:.2f} {h:.2f}")


if __name__ == "__main__":
    main()
