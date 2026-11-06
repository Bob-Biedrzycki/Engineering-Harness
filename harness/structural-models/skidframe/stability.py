"""Overall stability: seismic force, overturning / tipping, sliding, transport.

Models: seismic_force, overturning, transport. Units: lb, in.
"""
from __future__ import annotations

import math

import numpy as np

from .core import Calc, InputError, need
from .supports import rigid_reactions

REF_7_16 = "ASCE/SEI 7-16 Section 13.3.1, Eq. 13.3-1 to 13.3-3 (component seismic force)"
REF_7_22 = "ASCE/SEI 7-22 Section 13.3.1, Eq. 13.3-1 to 13.3-3 (component seismic force)"
REF_FMCSA = "49 CFR 393.102(a) and 393.106(d) (cargo securement performance and aggregate working load limit)"


# ================================================================ seismic
def seismic_force(inputs: dict) -> Calc:
    """WHEN: the site has a seismic design category (SDS from the customer / geotechnical report). Gives the
    horizontal design force Fp on the skid (or one component on it) and Ev. Strength level (LRFD); ASD uses 0.7 Fp.

    inputs: edition '7-22' | '7-16', SDS, Wp (lb), Ip (1.0 or 1.5), z (in, attachment height in the building;
    0 at grade), h (in, building roof height; needed when z > 0).
      7-16: ap, Rp (ASCE 7-16 Table 13.5-1 / 13.6-1 row for the component; no default: they decide the result)
      7-22: CAR, Rpo (Table 13.6-1), Rmu (13.3.1.1; 1.3 for at-grade or unknown structure), Hf (optional;
            1.0 at grade), a1, a2 (13.3-4/-5 when z > 0)
    The skid as a nonbuilding structure (ASCE 7 Chapter 15) is the other route: use it when the skid is large
    and the building official treats it so; this model covers the Chapter 13 component route only."""
    c = Calc("seismic_force", "Seismic design force on the skid (ASCE 7 Chapter 13)")
    c.inputs = inputs
    ed = inputs.get("edition") or c.default(inputs, "edition", "7-22", "current ASCE 7 edition (IBC 2024)")
    SDS = need(inputs, "SDS", lo=0.0)
    Wp = need(inputs, "Wp", lo=0.0)
    Ip = need(inputs, "Ip", lo=1.0, hi=1.5)
    z = float(inputs.get("z", 0.0))
    h = float(inputs.get("h", 0.0))
    if z > 0 and h <= 0:
        raise InputError("z > 0 needs the building height h")
    zr = min(z / h, 1.0) if h > 0 else 0.0
    if ed == "7-16":
        ap = need(inputs, "ap", lo=1.0, hi=2.5)
        Rp = need(inputs, "Rp", lo=1.0, hi=12.0)
        Fp = 0.4 * ap * SDS * Wp * (1 + 2 * zr) / (Rp / Ip)
        ref = REF_7_16
    elif ed == "7-22":
        CAR = need(inputs, "CAR", lo=0.0)
        Rpo = need(inputs, "Rpo", lo=1.0)
        Rmu = float(inputs.get("Rmu") or c.default(inputs, "Rmu", 1.3, "ASCE 7-22 13.3.1.1 for at-grade / unknown structure"))
        if "Hf" in inputs:
            Hf = float(inputs["Hf"])
        elif zr == 0:
            Hf = 1.0
        else:
            a1 = need(inputs, "a1")
            a2 = need(inputs, "a2")
            Hf = 1 + a1 * zr + a2 * zr ** 10
        Fp = 0.4 * SDS * Ip * Wp * (Hf / Rmu) * (CAR / Rpo)
        c.r("Hf", Hf)
        ref = REF_7_22
    else:
        raise InputError("edition must be '7-16' or '7-22'")
    Fmin, Fmax = 0.3 * SDS * Ip * Wp, 1.6 * SDS * Ip * Wp
    Fp_d = min(max(Fp, Fmin), Fmax)
    c.r("Fp (equation)", Fp, "lb")
    c.r("Fp min / max", f"{Fmin:.0f} / {Fmax:.0f}", "lb")
    c.r("Fp design (strength level)", Fp_d, "lb")
    c.r("Fp / Wp (horizontal coefficient)", Fp_d / Wp if Wp else 0.0, "g")
    c.r("Ev / D = 0.2 SDS", 0.2 * SDS, "g")
    c.r("ASD horizontal coefficient 0.7 Fp / Wp", 0.7 * Fp_d / Wp if Wp else 0.0, "g")
    c.method = ("Fp from the edition's Eq. 13.3-1, bounded by 0.3 SDS Ip Wp and 1.6 SDS Ip Wp; applied at the "
                "component's centre of mass in the direction that is worst; Ev = 0.2 SDS D (12.4.2.2).")
    c.references.append(ref)
    c.warn("SDS, Ip and the Table 13.6-1 row are site and customer facts: record their source; never assume them")
    return c


# ================================================================ overturning / tipping / sliding
def _hull(pts):
    P = sorted(set(map(tuple, pts)))
    if len(P) < 3:
        return P

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in P:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(P):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def overturning(inputs: dict) -> Calc:
    """WHEN: lateral load (seismic, transport, wind, a push, a slope) can tip or slide the skid; also gives the
    static tipping angle in every direction and the anchor uplift needed when weight alone does not hold it.

    inputs: footprint [[x, y], ...] (feet or bearing points), items [{name, W, x, y, z}] (or W and cg [x, y, z]),
    cases [{name, ax, ay, gravity}] with ax, ay horizontal accelerations in g (applied at each item's z) and
    gravity the factor on weight (0.6 for ASD 0.6D, 0.9 for LRFD, 1.0 plain), mu (friction), SF_required (1.5)."""
    c = Calc("overturning", "Overturning, tipping angle and sliding")
    c.inputs = inputs
    fp = inputs.get("footprint")
    if not fp or len(fp) < 3:
        raise InputError("footprint needs at least 3 points")
    if "items" in inputs:
        items = [(float(i["W"]), float(i["x"]), float(i["y"]), float(i["z"])) for i in inputs["items"]]
    else:
        W = need(inputs, "W", lo=0.0, strict_lo=True)
        cg = inputs.get("cg")
        if not cg or len(cg) != 3:
            raise InputError("give items or W with cg [x, y, z]")
        items = [(W, float(cg[0]), float(cg[1]), float(cg[2]))]
    W = sum(i[0] for i in items)
    cgx = sum(i[0] * i[1] for i in items) / W
    cgy = sum(i[0] * i[2] for i in items) / W
    cgz = sum(i[0] * i[3] for i in items) / W
    c.r("weight", W, "lb")
    c.r("CG", f"({cgx:.2f}, {cgy:.2f}, {cgz:.2f})", "in")
    hull = _hull([(float(p[0]), float(p[1])) for p in fp])
    # static tipping: distance from CG projection to each hull edge
    rows = []
    min_d = math.inf
    for k in range(len(hull)):
        a, b = np.array(hull[k]), np.array(hull[(k + 1) % len(hull)])
        t = b - a
        nrm = np.array([t[1], -t[0]]) / np.linalg.norm(t)         # outward for counter-clockwise hull
        d = float(np.dot(a - np.array([cgx, cgy]), nrm))
        ang = math.degrees(math.atan2(d, cgz)) if cgz > 0 else 90.0
        rows.append([f"edge {k + 1} {tuple(round(v, 2) for v in a)}-{tuple(round(v, 2) for v in b)}", round(d, 2),
                     round(d / cgz, 3) if cgz > 0 else "inf", round(ang, 1)])
        min_d = min(min_d, d)
    c.table("static tipping by edge", ["edge", "CG to edge in", "tipping accel (g)", "tip angle deg"], rows)
    if min_d <= 0:
        c.check("CG inside the footprint", False, "the CG projects outside the footprint: the skid tips at rest")
        return c
    c.r("least tipping acceleration", min_d / cgz if cgz > 0 else math.inf, "g")
    c.r("least tip angle", math.degrees(math.atan2(min_d, cgz)), "deg")
    SFreq = float(inputs.get("SF_required") or c.default(inputs, "SF_required", 1.5,
                  "overturning safety factor 1.5 (common practice for unanchored equipment; ASCE 7 combinations "
                  "with 0.6D are the code route)"))
    mu = inputs.get("mu")
    if mu is None:
        mu = 0.3
        c.assume("friction coefficient 0.3 (polymer or rubber foot on a wet washdown floor)")
    for case in inputs.get("cases", []):
        nm = case.get("name", "case")
        ax, ay = float(case.get("ax", 0.0)), float(case.get("ay", 0.0))
        gf = float(case.get("gravity", 1.0))
        loads = [(gf * w, x, y, ax * w, ay * w, z) for (w, x, y, z) in items]
        # overturning about each edge
        worst_sf = math.inf
        for k in range(len(hull)):
            a, b = np.array(hull[k]), np.array(hull[(k + 1) % len(hull)])
            t = b - a
            nrm = np.array([t[1], -t[0]]) / np.linalg.norm(t)
            Mr = sum(l[0] * float(np.dot(a - np.array([l[1], l[2]]), nrm)) for l in loads)
            Mo = sum((l[3] * nrm[0] + l[4] * nrm[1]) * l[5] for l in loads)
            if Mo > 0:
                worst_sf = min(worst_sf, Mr / Mo)
        if math.isfinite(worst_sf):
            c.ratio(f"{nm}: overturning", SFreq, worst_sf, f"resisting / overturning = {worst_sf:.2f} (need {SFreq})",
                    "statics; ASCE 7 2.4.1 0.6D combination when gravity = 0.6")
        H = math.hypot(ax, ay) * W
        c.ratio(f"{nm}: sliding", H, mu * gf * W, f"H {H:.0f} lb vs mu x {gf} W = {mu * gf * W:.0f} lb", "friction")
        R, act, ok = rigid_reactions([(float(p[0]), float(p[1])) for p in fp], loads, contact=False)
        upl = float(-R.min()) if R.min() < 0 else 0.0
        c.r(f"{nm}: max anchor uplift (rigid base, all points tied down)", upl, "lb")
        c.r(f"{nm}: max foot compression", float(R.max()), "lb")
    c.method = ("Convex hull of the bearing points; tipping acceleration d/h for each edge; overturning about each "
                "edge with lateral forces at each item's height; rigid-base reactions for uplift.")
    c.references.append("statics; ASCE/SEI 7-22 2.4.1 / 2.3.1 (0.6D, 0.9D combinations)")
    return c


# ================================================================ transport
def transport(inputs: dict) -> Calc:
    """WHEN: the skid ships by truck (TR-18: enclosed 53 ft dry van). Gives the inertia forces to design the
    tie-downs and the frame tie-down points for, the tipping check in the trailer, and the frame load cases
    (as 'body' vectors for frame_check).

    inputs: W (lb), cg [x, y, z] (z above the trailer deck, in), footprint [[x, y], ...] (bearing on the deck),
    travel_axis 'x' | 'y' (skid axis along the trailer), mu (deck friction, default 0: no credit)."""
    c = Calc("transport", "Over-the-road transport (49 CFR 393)")
    c.inputs = inputs
    W = need(inputs, "W", lo=0.0, strict_lo=True)
    cg = inputs.get("cg")
    fp = inputs.get("footprint")
    if not cg or not fp:
        raise InputError("cg [x, y, z] and footprint are needed")
    axis = inputs.get("travel_axis") or c.default(inputs, "travel_axis", "x", "skid long axis along the trailer")
    mu = float(inputs.get("mu") if inputs.get("mu") is not None else c.default(inputs, "mu", 0.0,
               "no friction credit between skid and deck (conservative)"))
    fwd = (1, 0) if axis == "x" else (0, 1)
    lat = (0, 1) if axis == "x" else (1, 0)
    cases = [("forward 0.8 g", 0.8, fwd), ("rearward 0.5 g", 0.5, (-fwd[0], -fwd[1])),
             ("lateral 0.5 g", 0.5, lat), ("lateral 0.5 g other side", 0.5, (-lat[0], -lat[1]))]
    rows, body = [], []
    for nm, a, d in cases:
        F = a * W
        net = max(F - mu * W, 0.0)
        rows.append([nm, round(F), round(net)])
        body.append([nm, [a * d[0], a * d[1], -1.0]])
    c.table("restraint force by direction (breaking-strength basis)", ["direction", "inertia lb", "net of friction lb"], rows)
    c.r("aggregate working load limit of tie-downs, minimum 0.5 W", 0.5 * W, "lb (393.106(d))")
    c.r("frame load cases (body factors for frame_check)", "; ".join(f"{n}: {b}" for n, b in body))
    sub = overturning({"footprint": fp, "W": W, "cg": cg, "mu": max(mu, 1e-9), "SF_required": 1.0,
                       "cases": [{"name": nm, "ax": a * d[0], "ay": a * d[1], "gravity": 1.0} for nm, a, d in cases]})
    for ch in sub.checks:
        if "overturning" in ch.name:
            c.checks.append(ch)
            if not ch.passed:
                c.warn(f"{ch.name}: the skid tips without tie-downs; tie-downs must hold it (their WLL and angle)")
    c.tables.update({k: v for k, v in sub.tables.items()})
    c.method = ("Accelerations of 49 CFR 393.102(a)(1) applied one at a time with gravity; tipping in the trailer "
                "with no tie-down; aggregate WLL >= W/2 (393.106(d)).")
    c.references.append(REF_FMCSA)
    c.assume("the 393.102(a)(1) breaking-strength accelerations are also used as the frame's ultimate transport "
             "cases; tie-down points and the members around them are checked with frame_check using the body vectors")
    return c
