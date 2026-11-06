"""Welds, bolts, and tube-wall local strength at joints and concentrated loads.

Units: lb, in, psi, lb-in.

Implemented:
- Fillet weld strength per inch [AISC 370-21 J2.4, Table J2.5: Fnw = 0.60 FEXX, phi 0.75 / Omega 2.00,
  effective throat 0.707 w for an equal-leg fillet; optional directional increase (1 + 0.50 sin^1.5 theta) J2-5],
  and the base metal at the weld [J4.2 shear: yielding 0.60 Fy (phi 1.00 / Omega 1.50), rupture 0.60 Fu
  (phi 0.75 / Omega 2.00)]. Carbon steel: AISC 360-22 J2 / J4, same factors.
- Weld groups by the elastic vector method (Blodgett, Design of Welded Structures, 7.4; AISC Manual Part 8,
  "elastic method"): the weld is treated as a line; forces in and out of the weld plane and moments about all three
  axes give a resultant force per inch at each point, compared with the weld's strength per inch. Conservative:
  no directional increase and no instantaneous-centre redistribution.
- Round HSS-to-HSS T/Y and cross joints [AISC 370 K2.2, Table K2.1: punching K2-2, chord plastification K2-3,
  K2-4, Qf K2-7] within Table K2.1a limits.
- Rectangular HSS chord with a branch (axial and moment): NOT in AISC 370 Chapter K (its user note excludes
  moment connections and rectangular truss joints). Implemented by analogy from AISC 360-22 Chapter K
  (chord wall plastification for beta <= 0.85; Qf), with stainless Fy, and flagged as a rational analysis.
- Concentrated force on a rectangular HSS wall [AISC 370 J12, Eq. J12-1, Table J12.1, limits (a)-(d)].
- Transverse plate / bearing pad on a round HSS [AISC 360-22 Table K1.1, Rn sin(theta) = Fy t^2 (5.5 / (1 - 0.81 Bp/D)) Qf],
  by analogy for stainless (flagged).
- Bolts in shear, tension and combined shear+tension [AISC 370 J3.7: Fnt 0.75 Fu, Fnv 0.45 Fu (threads in) or
  0.55 Fu (threads excluded), phi 0.75 / Omega 2.00, J3-3 interaction]; bearing / tear-out at the hole by the
  AISC 360-22 J3.11 form 2.4 d t Fu / 1.2 lc t Fu (flagged for stainless).
"""
from __future__ import annotations

import math

import numpy as np

from .core import InputError
from .members import ASD, LRFD


def _avail(Rn, phi, om, method):
    if method == ASD:
        return Rn / om
    if method == LRFD:
        return Rn * phi
    raise InputError(f"design method must be ASD or LRFD, got {method!r}")


# ---------------------------------------------------------------- fillet welds
def fillet_strength_per_in(leg: float, FEXX: float, method=ASD, theta_deg: float | None = None) -> float:
    """Available strength per inch of an equal-leg fillet weld (lb/in)."""
    if leg <= 0:
        raise InputError("fillet weld leg must be > 0")
    Fnw = 0.60 * FEXX
    if theta_deg is not None:
        Fnw *= 1.0 + 0.50 * math.sin(math.radians(theta_deg)) ** 1.5
    return _avail(Fnw * 0.7071 * leg, 0.75, 2.00, method)


def base_metal_shear_per_in(t: float, Fy: float, Fu: float, method=ASD) -> float:
    """Available shear per inch of the connected part along the weld (J4.2), lb/in."""
    y = _avail(0.60 * Fy * t, 1.00, 1.50, method)
    r = _avail(0.60 * Fu * t, 0.75, 2.00, method)
    return min(y, r)


def max_fillet_leg_from_base(t_thinner: float, FEXX: float, Fu: float) -> float:
    """Leg above which the base metal, not the weld, limits a fillet on a part of thickness t loaded in shear
    on one face (both rupture checks with the same phi): 0.6 Fu t = 0.6 FEXX 0.707 w  ->  w = Fu t / (0.707 FEXX)."""
    return Fu * t_thinner / (0.7071 * FEXX)


# ---------------------------------------------------------------- weld groups (elastic method)
def _segments_props(segs):
    L = np.array([math.hypot(x2 - x1, y2 - y1) for (x1, y1, x2, y2) in segs])
    if np.any(L <= 0):
        raise InputError("weld group has a zero-length segment")
    mx = np.array([(x1 + x2) / 2 for (x1, y1, x2, y2) in segs])
    my = np.array([(y1 + y2) / 2 for (x1, y1, x2, y2) in segs])
    A = L.sum()
    xc, yc = (L * mx).sum() / A, (L * my).sum() / A
    Ix = Iy = Ixy = 0.0
    for (x1, y1, x2, y2), l in zip(segs, L):
        # line segment second moments about the group centroid (unit throat)
        ax, ay = x1 - xc, y1 - yc
        bx, by = x2 - xc, y2 - yc
        Ix += l * (ay * ay + ay * by + by * by) / 3
        Iy += l * (ax * ax + ax * bx + bx * bx) / 3
        Ixy += l * (2 * ax * ay + ax * by + bx * ay + 2 * bx * by) / 6
    return A, xc, yc, Ix, Iy, Ixy


def weld_group(segments, Fx=0.0, Fy=0.0, Fz=0.0, Mx=0.0, My=0.0, Mz=0.0, points_per_segment=4):
    """Resultant force per inch of weld (lb/in) by the elastic method.

    segments: list of (x1, y1, x2, y2) in the weld plane (in). Loads act at the group centroid:
    Fx, Fy in plane; Fz normal to the plane; Mz torsion in the plane; Mx, My bending about in-plane axes.
    Returns (f_max, detail)."""
    segs = [tuple(map(float, s)) for s in segments]
    if not segs:
        raise InputError("weld group needs at least one segment")
    A, xc, yc, Ix, Iy, Ixy = _segments_props(segs)
    Ip = Ix + Iy
    det_I = Ix * Iy - Ixy ** 2
    fmax, at = 0.0, None
    for (x1, y1, x2, y2) in segs:
        for k in range(points_per_segment + 1):
            s = k / points_per_segment
            x, y = x1 + (x2 - x1) * s - xc, y1 + (y2 - y1) * s - yc
            fx = Fx / A - (Mz * y / Ip if Ip > 0 else 0.0)
            fy = Fy / A + (Mz * x / Ip if Ip > 0 else 0.0)
            # unsymmetric bending of a line group (general flexure formula)
            if det_I > 0:
                fz = Fz / A + ((Mx * Iy + My * Ixy) * y - (My * Ix + Mx * Ixy) * x) / det_I
            else:
                fz = Fz / A
            f = math.sqrt(fx * fx + fy * fy + fz * fz)
            if f > fmax:
                fmax, at = f, (x + xc, y + yc)
    return fmax, {"length": A, "centroid": (xc, yc), "Ix": Ix, "Iy": Iy, "Ip": Ip, "critical_point": at,
                  "method": "elastic vector method, line weld (Blodgett 7.4 / AISC Manual Part 8)"}


def circle_segments(D: float, n: int = 72):
    r = D / 2
    pts = [(r * math.cos(2 * math.pi * k / n), r * math.sin(2 * math.pi * k / n)) for k in range(n + 1)]
    return [(pts[k][0], pts[k][1], pts[k + 1][0], pts[k + 1][1]) for k in range(n)]


def box_segments(b: float, h: float):
    """All-round weld of a b (x) by h (y) rectangle, centred."""
    x, y = b / 2, h / 2
    return [(-x, -y, x, -y), (x, -y, x, y), (x, y, -x, y), (-x, y, -x, -y)]


def two_lines(b: float, h: float, vertical=True):
    """Two parallel welds of length h at x = +/- b/2 (vertical) or length b at y = +/- h/2."""
    if vertical:
        return [(-b / 2, -h / 2, -b / 2, h / 2), (b / 2, -h / 2, b / 2, h / 2)]
    return [(-b / 2, -h / 2, b / 2, -h / 2), (-b / 2, h / 2, b / 2, h / 2)]


# ---------------------------------------------------------------- round HSS joints (AISC 370 K2.2)
def round_qf(U: float, chord_in_tension: bool):
    if chord_in_tension:
        return 1.0
    return 1.0 - 0.3 * U * (1 + U)


def round_hss_joint(D, t, Db, tb, Fy, Fyb, theta_deg=90.0, kind="T", U=0.0, chord_in_tension=False,
                    method=ASD, l_end=None, E=28.0e6):
    """Available branch axial force for a round HSS T/Y or cross joint (AISC 370 Table K2.1)."""
    th = math.radians(theta_deg)
    s = math.sin(th)
    beta, gamma = Db / D, D / (2 * t)
    lim = []
    if not (0.2 < beta <= 1.0):
        lim.append(f"beta {beta:.3f} outside 0.2 < Db/D <= 1.0")
    if D / t > (50 if kind == "T" else 40):
        lim.append(f"chord D/t {D / t:.1f} above the Table K2.1a limit")
    if Db / tb > 50:
        lim.append("branch Db/tb above 50")
    if l_end is not None and l_end < D * (1.25 - beta / 2):
        lim.append(f"end distance {l_end:.2f} < D(1.25 - beta/2) = {D * (1.25 - beta / 2):.2f}")
    Qf = round_qf(U, chord_in_tension)
    out = {"beta": beta, "gamma": gamma, "Qf": Qf, "limits_violated": lim}
    cands = []
    if Db < D - 2 * t:
        Pp = 0.6 * Fy * t * math.pi * Db * (1 + s) / (2 * s * s)       # K2-2
        cands.append(("punching shear K2-2", _avail(Pp, 0.95, 1.58, method), Pp))
    if kind == "T":
        Pc = Fy * t * t * (3.1 + 15.6 * beta ** 2) * gamma ** 0.2 * Qf / s   # K2-3
        cands.append(("chord plastification K2-3", _avail(Pc, 0.90, 1.67, method), Pc))
    elif kind == "X":
        Pc = Fy * t * t * (5.7 / (1 - 0.81 * beta)) * Qf / s                # K2-4
        cands.append(("chord plastification K2-4", _avail(Pc, 0.90, 1.67, method), Pc))
    else:
        raise InputError("round HSS joint kind must be 'T' (T/Y) or 'X' (cross)")
    name, cap, Pn = min(cands, key=lambda c: c[1])
    out.update({"limit_states": {c[0]: c[1] for c in cands}, "governs": name, "Pn": Pn,
                "clause": "AISC 370-21 K2.2, Table K2.1"})
    return cap, out


# ---------------------------------------------------------------- rectangular HSS chord (AISC 360 analogy)
def rect_qf(U: float, beta: float, chord_in_tension: bool):
    if chord_in_tension:
        return 1.0
    return min(1.0, 1.3 - 0.4 * U / beta)


def rect_hss_branch(B, H_chord, t, Bb, Hb, Fy, theta_deg=90.0, Pr_axial=0.0, U=0.0, chord_in_tension=False,
                    method=ASD):
    """Rectangular HSS chord face under a rectangular branch (T joint): available branch axial force and
    in-plane / out-of-plane branch moments, chord wall plastification, beta <= 0.85.

    B: chord width (the face the branch lands on); t chord wall; Bb branch width across the chord;
    Hb branch depth along the chord. AISC 360-22 K2.3 (Table K2.2) and K3.3 (Table K3.2) forms with
    stainless Fy, phi 1.00 / Omega 1.50. Outside AISC 370 Chapter K: a rational analysis, flag it."""
    beta = Bb / B
    eta = Hb / B
    s = math.sin(math.radians(theta_deg))
    if beta > 0.85:
        raise InputError(f"beta = {beta:.3f} > 0.85: chord wall plastification does not govern; this joint needs "
                         "the sidewall / punching limit states (AISC 360-22 Table K2.2) by hand")
    Qf = rect_qf(U, beta, chord_in_tension)
    Pn = Fy * t * t * (2 * eta / (1 - beta) + 4 / math.sqrt(1 - beta)) * Qf / s
    Mip = Fy * t * t * Hb * (1 / (2 * eta) + 2 / math.sqrt(1 - beta) + eta / (1 - beta)) * Qf
    Mop = Fy * t * t * (0.5 * Hb * (1 + beta) / (1 - beta) + math.sqrt(2 * B * Bb * (1 + beta) / (1 - beta))) * Qf
    return {"P": _avail(Pn, 1.00, 1.50, method), "M_in_plane": _avail(Mip, 1.00, 1.50, method),
            "M_out_of_plane": _avail(Mop, 1.00, 1.50, method), "beta": beta, "eta": eta, "Qf": Qf,
            "clause": "AISC 360-22 K2.3 / K3.3 chord wall plastification, applied to stainless by analogy "
                      "(AISC 370-21 Chapter K excludes rectangular moment joints): rational analysis"}


def rect_hss_concentrated(t, h, r_in, lb, Fy, case="IOF", method=ASD):
    """Concentrated force normal to a rectangular HSS flange [AISC 370 J12, J12-1]."""
    table = {"EOF": (4, 0.32, 1.60, 0.040), "IOF": (2, 0.04, 2.30, 0.001),
             "ETF": (2, 0.35, 2.60, 0.050), "ITF": (8, 0.21, 0.75, 0.010)}
    if case not in table:
        raise InputError(f"J12 case must be one of {sorted(table)}")
    C, Cr, Cl, Ch = table[case]
    lim = []
    if h / t > 60:
        lim.append("h/t > 60")
    if lb / t > 55:
        lim.append("lb/t > 55")
    if lb / h > 3:
        lim.append("lb/h > 3")
    if r_in / t > 2:
        lim.append("r/t > 2")
    Rn = C * t * t * Fy * (1 - Cr * math.sqrt(r_in / t)) * (1 + Cl * math.sqrt(lb / t)) * (1 - Ch * math.sqrt(h / t))
    return _avail(Rn, 0.90, 1.67, method), {"Rn": Rn, "case": case, "limits_violated": lim,
                                             "clause": "AISC 370-21 J12, Eq. J12-1, Table J12.1"}


def round_hss_plate(D, t, Bp, Fy, theta_deg=90.0, U=0.0, chord_in_tension=False, method=ASD):
    """Transverse plate (or bearing pad of width Bp across the tube) on a round HSS: local yielding of the wall.
    AISC 360-22 Table K1.1 form, applied to stainless by analogy (flagged)."""
    if Bp >= D:
        raise InputError("plate width Bp must be less than the tube diameter D for this limit state")
    s = math.sin(math.radians(theta_deg))
    Qf = round_qf(U, chord_in_tension)
    Rn = Fy * t * t * (5.5 / (1 - 0.81 * Bp / D)) * Qf / s
    return _avail(Rn, 0.90, 1.67, method), {"Rn": Rn, "Qf": Qf,
                                             "clause": "AISC 360-22 Table K1.1 (transverse plate, round HSS), by analogy"}


# ---------------------------------------------------------------- bolts
UNC_TPI = {0.25: 20, 0.3125: 18, 0.375: 16, 0.4375: 14, 0.5: 13, 0.5625: 12, 0.625: 11, 0.75: 10, 0.875: 9,
           1.0: 8, 1.125: 7, 1.25: 7, 1.375: 6, 1.5: 6}
"""ASME B1.1 Unified Coarse threads per inch by nominal diameter."""


def unc_tpi(d: float) -> int:
    for k, v in UNC_TPI.items():
        if abs(k - d) < 1e-3:
            return v
    raise InputError(f"no UNC thread pitch on file for {d} in: give threads_per_in")


def tensile_stress_area(d: float, tpi: float | None = None) -> float:
    """ASME B1.1 tensile stress area: pi/4 (d - 0.9743 / n)^2."""
    n = tpi or unc_tpi(d)
    return math.pi / 4 * (d - 0.9743 / n) ** 2


def minor_diameter(d: float, tpi: float | None = None) -> float:
    """External thread minor diameter, d - 1.2269 / n (basic, ASME B1.1)."""
    n = tpi or unc_tpi(d)
    return d - 1.2269 / n


def bolt_area(d: float) -> float:
    return math.pi * d * d / 4


def bolt_shear(d, Fu, method=ASD, threads_excluded=False, planes=1):
    Fnv = (0.55 if threads_excluded else 0.45) * Fu
    return _avail(Fnv * bolt_area(d) * planes, 0.75, 2.00, method)


def bolt_tension(d, Fu, method=ASD):
    return _avail(0.75 * Fu * bolt_area(d), 0.75, 2.00, method)


def bolt_combined(d, Fu, Vr, Tr, method=ASD, threads_excluded=False):
    """Required tension Tr against the J3-3 reduced tensile strength with shear Vr present. Returns ratio."""
    Ab = bolt_area(d)
    Fnt = 0.75 * Fu
    Fnv = (0.55 if threads_excluded else 0.45) * Fu
    frv = Vr / Ab
    if method == ASD:
        Fnt_p = min(Fnt, 1.3 * Fnt - 2.00 * Fnt / Fnv * frv)
        cap_t = max(Fnt_p, 0.0) * Ab / 2.00
        cap_v = Fnv * Ab / 2.00
    else:
        Fnt_p = min(Fnt, 1.3 * Fnt - Fnt / (0.75 * Fnv) * frv)
        cap_t = max(Fnt_p, 0.0) * Ab * 0.75
        cap_v = Fnv * Ab * 0.75
    rv = Vr / cap_v
    rt = Tr / cap_t if cap_t > 0 else math.inf
    return max(rv, rt), {"shear_ratio": rv, "tension_ratio_J3-3": rt, "Fnt_prime": Fnt_p}


def bolt_bearing(d, t, Fu, lc, method=ASD):
    """Bearing and tear-out at a standard hole, deformation at service a design consideration (AISC 360 J3.11 form)."""
    Rn = min(2.4 * d * t * Fu, 1.2 * lc * t * Fu)
    return _avail(Rn, 0.75, 2.00, method)
