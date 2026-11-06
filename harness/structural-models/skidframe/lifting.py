"""Lifting the skid: forklift, lifting lugs (pin-connected plates), slings.

Models: forklift, lift_lug, slings. Units: lb, in, psi.

The base frame on the tines is a frame_check problem: model the tines as compression-only (contact) supports at
the members' undersides where they cross the tine lines, restrain one node in x and y, and load the EMPTY skid
with an impact factor (case body [0, 0, -impact]). See README "Recipe: forklift lift".
"""
from __future__ import annotations

import math

from . import connections as CN
from . import materials as MT
from .core import Calc, InputError, need
from .supports import rigid_reactions

REF_BTH = ("ASME BTH-1-2020, Design of Below-the-Hook Lifting Devices, 3-3.3 pinned connections (Eq. 3-45 to "
           "3-53) and Table 2-1 design categories (Nd 2.00 category A, 3.00 category B)")


def forklift(inputs: dict) -> Calc:
    """WHEN: the skid is lifted by a forklift: load centre, derated truck capacity, fork length, CG between the
    tines; produces the impact load case for frame_check.

    inputs: W (lb, as lifted, normally empty), cg [x, y, z], carriage_stop (coordinate of the face the fork heel
    stops against, along the lift axis), lift_axis 'x' | 'y', tines [y1, y2] (tine centre lines across the lift
    axis, in), tine_width (in), fork_length (in), truck_capacity (lb), rated_load_centre (in, 24 for most trucks
    up to 15,000 lb), impact (factor for the frame check)."""
    c = Calc("forklift", "Forklift lift: load centre, truck capacity, tine placement")
    c.inputs = inputs
    W = need(inputs, "W", lo=0.0, strict_lo=True)
    cg = inputs.get("cg")
    if not cg or len(cg) != 3:
        raise InputError("cg [x, y, z] is needed")
    axis = inputs.get("lift_axis") or c.default(inputs, "lift_axis", "x", "forks run along the skid's x axis")
    stop = need(inputs, "carriage_stop")
    along = float(cg[0] if axis == "x" else cg[1])
    across = float(cg[1] if axis == "x" else cg[0])
    LC = abs(along - stop)
    c.r("load centre (fork heel to CG)", LC, "in")
    lcr = float(inputs.get("rated_load_centre") or c.default(inputs, "rated_load_centre", 24.0,
                "rated load centre 24 in (most counterbalanced trucks to 15,000 lb; confirm on the data plate)"))
    cap = inputs.get("truck_capacity")
    if cap:
        der = float(cap) * lcr / LC if LC > lcr else float(cap)
        c.r("derated capacity at this load centre", der, "lb")
        c.ratio("truck capacity (derated by load centre)", W, der,
                rule="load-moment derating, capacity x rated LC / actual LC (truck data plate governs)")
    c.r("truck capacity needed at the rated load centre", W * max(LC, lcr) / lcr, "lb")
    c.warn("attachments (fork extensions, positioners) and lift height derate the truck further: confirm with the "
           "dealer in writing")
    fl = inputs.get("fork_length")
    if fl:
        fl = float(fl)
        c.ratio("fork length past the CG", LC, fl, f"CG {LC:.1f} in from the heel; forks {fl:.1f} in",
                "forks must reach past the CG (practice: tips past the CG by a margin; common rule forks >= 2/3 "
                "of the load depth)")
    tines = inputs.get("tines")
    if tines and len(tines) == 2:
        y1, y2 = sorted(map(float, tines))
        tw = float(inputs.get("tine_width", 0.0))
        inner, outer = y1 + tw / 2, y2 - tw / 2
        inside = y1 <= across <= y2
        c.check("CG between the tines", inside, f"CG at {across:.2f}, tines at {y1:.2f} / {y2:.2f}",
                "lateral stability on the forks")
        if inside:
            m = min(across - y1, y2 - across)
            c.r("CG margin to the nearer tine", m, "in")
            c.r("lateral tipping accel on the forks", m / float(cg[2]) if float(cg[2]) > 0 else math.inf, "g")
    imp = float(inputs.get("impact") or c.default(inputs, "impact", 2.0,
                "impact factor 2.0 on the empty weight for the frame strength check (CPME frame calc practice, "
                "FC-02; ASME BTH-1 uses Nd 2 to 3 on lifting devices)"))
    c.r("frame_check case body vector", f"[0, 0, {-imp}]", "x weight (empty skid)")
    c.method = "Load centre from the carriage stop; load-moment derating; CG between tines; impact factor."
    c.references.append("ANSI/ITSDF B56.1 (powered industrial trucks: capacity plate and load centre)")
    return c


def lift_lug(inputs: dict) -> Calc:
    """WHEN: the skid (or a tank, panel or pump) is lifted by shackles through plate lugs welded to the frame.

    inputs: P (sling force on this lug, lb), t, Dh (hole), Dp (pin of the shackle), R (hole centre to the plate
    edge in the line of the load), be (edge distance from the hole edge, each side, normal to the load), a (hole
    edge to plate edge in the line of the load), material, Nd (2.0 category A, 3.0 category B), out_of_plane_deg
    (sling angle out of the lug plane), weld {leg, length, two_sided, filler} (fillet welds along the lug base),
    base_length (in, lug base along the frame member)."""
    c = Calc("lift_lug", "Lifting lug, pin-connected plate (ASME BTH-1)")
    c.inputs = inputs
    P = need(inputs, "P", lo=0.0)
    t = need(inputs, "t", lo=0.0, strict_lo=True)
    Dh = need(inputs, "Dh", lo=0.0, strict_lo=True)
    Dp = need(inputs, "Dp", lo=0.0, strict_lo=True)
    R = need(inputs, "R", lo=0.0, strict_lo=True)
    be = need(inputs, "be", lo=0.0, strict_lo=True)
    a = need(inputs, "a", lo=0.0, strict_lo=True)
    if Dp > Dh:
        raise InputError("pin diameter Dp exceeds hole Dh")
    mat = MT.get(inputs.get("material") or c.default(inputs, "material", "A240-304", "304 plate"))
    Nd = float(inputs.get("Nd") or c.default(inputs, "Nd", 3.0, "BTH-1 Design Category B (unknown service, "
                                                                "recommended for general lifting)"))
    Fy, Fu = mat.Fy, mat.Fu
    Cr = 1 - 0.275 * math.sqrt(1 - Dp * Dp / (Dh * Dh))
    beff = min(4 * t, be, be * 0.6 * Fu / Fy * math.sqrt(Dh / be))
    Pt = Cr * Fu * 2 * t * beff / (1.20 * Nd)
    Pb = Cr * Fu / (1.20 * Nd) * (1.13 * (R - Dh / 2) + 0.92 * be / (1 + be / Dh)) * t
    phi = math.radians(55 * Dp / Dh)
    Av = 2 * (a + Dp / 2 * (1 - math.cos(phi))) * t
    Pv = 0.70 * Fu / (1.20 * Nd) * Av
    Pp = 1.25 * Fy * Dp * t / Nd
    c.r("Cr", Cr)
    c.r("beff", beff, "in")
    for nm, cap, eq in (("tension across the pinhole", Pt, "BTH-1 3-45"), ("single plane fracture", Pb, "BTH-1 3-48"),
                        ("double plane (shear-out) fracture", Pv, "BTH-1 3-49"), ("bearing on the pin", Pp, "BTH-1 3-53")):
        c.r(nm, cap, "lb allowable")
        c.ratio(nm, P, cap, rule=eq)
    if Dh > Dp + max(0.0625, 0.1 * Dp):
        c.warn("hole much larger than the pin: BTH-1 strength reductions assume a close fit; use a pin plate or "
               "a smaller hole")
    oop = float(inputs.get("out_of_plane_deg", 0.0))
    w = inputs.get("weld")
    if w:
        leg = float(w["leg"])
        Lw = float(w["length"])
        FEXX = MT.filler(w.get("filler", "E308L"))
        two = bool(w.get("two_sided", True))
        ip = float(inputs.get("in_plane_deg", 0.0))  # sling angle from the lug axis, in the lug plane
        Pz = P * math.cos(math.radians(oop)) * math.cos(math.radians(ip))   # pull off the member
        Py = P * math.cos(math.radians(oop)) * math.sin(math.radians(ip))   # along the lug base
        Px = P * math.sin(math.radians(oop))                                # out of the lug plane
        h_load = float(inputs.get("hole_height_above_base") or c.default(inputs, "hole_height_above_base", 2 * R,
                       "hole centre 2R above the lug base"))
        segs = CN.two_lines(t, Lw, vertical=True) if two else [(0, -Lw / 2, 0, Lw / 2)]
        f, det = CN.weld_group(segs, Fx=Px, Fy=Py, Fz=Pz, Mx=Py * h_load, My=Px * h_load)
        # Nd on welds: BTH-1 3-3.4 uses the same design factor on weld strength
        fa = 0.60 * FEXX * 0.7071 * leg / (1.20 * Nd) * 1.0
        c.r("weld force per inch", f, "lb/in")
        c.ratio("lug-to-frame fillet welds", f, fa, "elastic method; allowable 0.60 FEXX x throat / (1.20 Nd)",
                "BTH-1 3-3.4 (weld allowable at Nd)")
    if oop > 5 and not w:
        c.warn("sling out of the lug plane: check lug bending about its weak axis and the welds (give 'weld')")
    c.method = "ASME BTH-1 pinned-connection limit states at the design factor Nd; welds by the elastic method."
    c.references += [REF_BTH, "Values as given in BTH-1-2020; confirm against the purchased standard before issue"]
    return c


def slings(inputs: dict) -> Calc:
    """WHEN: a crane lifts the skid with a 2- or 4-leg bridle: leg tensions with an off-centre CG, the horizontal
    squeeze on the frame between lugs, and the load each lug sees (input to lift_lug).

    inputs: W, cg [x, y], lugs [[x, y], ...], angle_deg (sling angle from horizontal), legs_carrying (for 4 legs
    without an equalizer: 2 per ASME B30.9 guidance, the conservative case), impact."""
    c = Calc("slings", "Sling leg loads and lug forces")
    c.inputs = inputs
    W = need(inputs, "W", lo=0.0, strict_lo=True)
    cg = inputs.get("cg")
    lugs = inputs.get("lugs")
    if not cg or not lugs or len(lugs) < 2:
        raise InputError("cg [x, y] and at least 2 lugs are needed")
    ang = need(inputs, "angle_deg", lo=1.0, hi=90.0)
    if ang < 45:
        c.warn("sling angle below 45 deg: leg tension and frame squeeze rise steeply; ASME B30.9 tables stop at 30 deg")
    imp = float(inputs.get("impact") or c.default(inputs, "impact", 1.15, "crane impact allowance (practice 1.15)"))
    Wd = W * imp
    pts = [(float(p[0]), float(p[1])) for p in lugs]
    if len(pts) == 2:
        (x1, y1), (x2, y2) = pts
        L = math.hypot(x2 - x1, y2 - y1)
        s = ((float(cg[0]) - x1) * (x2 - x1) + (float(cg[1]) - y1) * (y2 - y1)) / (L * L)
        if not (0.0 <= s <= 1.0):
            raise InputError("the CG lies outside the line between the two lugs: the load tips off the slings "
                             "(move the lugs or use a spreader)")
        V = [Wd * (1 - s), Wd * s]
    else:
        R, act, ok = rigid_reactions(pts, [(Wd, float(cg[0]), float(cg[1]), 0, 0, 0)])
        V = list(R)
        carrying = int(inputs.get("legs_carrying") or c.default(inputs, "legs_carrying", 2,
                       "4-leg bridle without an equalizer: 2 legs carry the load (ASME B30.9 practice)"))
        if carrying == 2:
            V = [Wd / 2] * len(pts)
            c.warn("design every lug for half the load (two legs may carry it all)")
        elif carrying == 3:
            V = [max(v, Wd / 3) for v in V]
    sinA = math.sin(math.radians(ang))
    rows = []
    for k, v in enumerate(V):
        T = v / sinA
        H = T * math.cos(math.radians(ang))
        rows.append([k + 1, round(v), round(T), round(H)])
    c.table("lug loads", ["lug", "vertical lb", "leg tension lb", "horizontal (frame squeeze) lb"], rows)
    c.r("max leg tension", max(r[2] for r in rows), "lb")
    c.method = "Statics of the bridle; leg tension = vertical / sin(angle); horizontal = tension x cos(angle)."
    c.references.append("ASME B30.9 (slings) and B30.26 (rigging hardware) for rated loads and angles")
    return c
