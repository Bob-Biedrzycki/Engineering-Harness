"""Local failure models: welds, bolts, tube joints, concentrated loads on tube walls, plate panels.

Models: weld, bolt, hss_joint, concentrated_load, plate. Units: lb, in, psi, lb-in.
"""
from __future__ import annotations

import math

from . import beams as B
from . import connections as CN
from . import materials as MT
from . import sections as SC
from .core import Calc, InputError, need

REF_370 = "ANSI/AISC 370-21"


def _method(inputs, c):
    return inputs.get("method") or c.default(inputs, "method", "ASD", "allowable strength design")


# ================================================================ weld
def weld(inputs: dict) -> Calc:
    """WHEN: any welded joint carrying load: a member end welded all round, a bracket, a lug, a foot-plate weld,
    a pump-base weld. Elastic method on the weld group plus the base metal along the weld.

    inputs: group 'circle' {D} | 'box' {b, h} | 'two_lines' {b, h, vertical} | 'segments' [[x1, y1, x2, y2], ...],
    leg (in), filler (E308L...), loads Fx, Fy (in the weld plane), Fz (normal), Mx, My (bending), Mz (torsion),
    base_t (thinner connected part, in), base_material."""
    c = Calc("weld", "Fillet weld group (elastic method)")
    c.inputs = inputs
    method = _method(inputs, c)
    g = inputs.get("group")
    if g == "circle":
        segs = CN.circle_segments(need(inputs, "D", lo=0.0, strict_lo=True))
    elif g == "box":
        segs = CN.box_segments(need(inputs, "b", lo=0.0, strict_lo=True), need(inputs, "h", lo=0.0, strict_lo=True))
    elif g == "two_lines":
        segs = CN.two_lines(need(inputs, "b", lo=0.0), need(inputs, "h", lo=0.0, strict_lo=True),
                            bool(inputs.get("vertical", True)))
    elif g == "segments":
        segs = inputs.get("segments") or []
    else:
        raise InputError("group must be circle, box, two_lines or segments")
    leg = need(inputs, "leg", lo=0.0, strict_lo=True)
    fill = inputs.get("filler") or c.default(inputs, "filler", "E308L", "304 base metal")
    FEXX = MT.filler(fill)
    loads = {k: float(inputs.get(k, 0.0)) for k in ("Fx", "Fy", "Fz", "Mx", "My", "Mz")}
    f, det = CN.weld_group(segs, **loads)
    cap = CN.fillet_strength_per_in(leg, FEXX, method)
    c.r("weld length", det["length"], "in")
    c.r("resultant force per inch", f, "lb/in")
    c.r("fillet strength per inch", cap, "lb/in")
    c.r("critical point", str(tuple(round(v, 3) for v in det["critical_point"])) if det["critical_point"] else "-")
    c.ratio("fillet weld", f, cap, f"{leg:g} in {fill} fillet, throat {0.7071 * leg:.4f} in",
            f"{REF_370} J2.4, Table J2.5 (0.60 FEXX, phi 0.75 / Omega 2.00)")
    bt = inputs.get("base_t")
    if bt:
        bm = MT.get(inputs.get("base_material") or c.default(inputs, "base_material", "A554-304", "304 tube"))
        capb = CN.base_metal_shear_per_in(float(bt), bm.Fy, bm.Fu, method)
        c.ratio("base metal shear along the weld", f, capb, f"t = {float(bt):g} in ({bm.key})",
                f"{REF_370} J4.2 (annealed HAZ: annealed Fu, J2.4)")
        lmax = CN.max_fillet_leg_from_base(float(bt), FEXX, bm.Fu)
        c.r("leg above which the base metal governs", lmax, "in")
        if leg > 1.5 * float(bt):
            c.warn("fillet leg much larger than the part thickness: burn-through and distortion on thin tube; "
                   "AWS D1.6 minimum/maximum fillet sizes apply")
    c.method = det["method"] + "; no directional strength increase (conservative)."
    c.references += [f"{REF_370} J2", "AWS D1.6/D1.6M (structural welding, stainless steel)"]
    return c


# ================================================================ bolt
def bolt(inputs: dict) -> Calc:
    """WHEN: a bolted joint (panel to frame, pump to base, removable member): bolt shear, tension, combined,
    and bearing at the hole.

    inputs: d (in), bolt_material (A193-B8-cl1, F593-G1-CW...), n (bolts sharing the load), V (lb total shear),
    T (lb total tension, incl. prying), threads_excluded, planes, plate_t, plate_material, lc (clear edge distance)."""
    c = Calc("bolt", "Bolted joint (AISC 370 J3)")
    c.inputs = inputs
    method = _method(inputs, c)
    d = need(inputs, "d", lo=0.0, strict_lo=True)
    Fu = MT.bolt(inputs.get("bolt_material") or c.default(inputs, "bolt_material", "A193-B8-cl1", "304 stainless bolt"))
    n = int(inputs.get("n", 1))
    V = abs(float(inputs.get("V", 0.0))) / n
    T = abs(float(inputs.get("T", 0.0))) / n
    te = bool(inputs.get("threads_excluded", False))
    pl = int(inputs.get("planes", 1))
    cv = CN.bolt_shear(d, Fu, method, te, pl)
    ct = CN.bolt_tension(d, Fu, method)
    c.ratio("bolt shear", V, cv, rule=f"{REF_370} J3.7")
    c.ratio("bolt tension", T, ct, rule=f"{REF_370} J3.7")
    if V > 0 and T > 0:
        r, det = CN.bolt_combined(d, Fu, V / pl, T, method, te)
        c.ratio("combined shear and tension", r, 1.0, f"J3-3: F'nt {det['Fnt_prime']:.0f} psi", f"{REF_370} J3-3")
    if inputs.get("plate_t"):
        pm = MT.get(inputs.get("plate_material") or c.default(inputs, "plate_material", "A240-304", "304 plate"))
        lc = float(inputs.get("lc") or c.default(inputs, "lc", 1.5 * d, "clear edge distance 1.5 d"))
        cb = CN.bolt_bearing(d, float(inputs["plate_t"]), pm.Fu, lc, method)
        c.ratio("bearing / tear-out at the hole", V, cb, rule="AISC 360-22 J3.11 form (verify AISC 370 J3.10)")
    c.warn("stainless bolts gall: specify anti-seize; stainless bolts are not pretensioned (snug tight)")
    c.method = "Fnt = 0.75 Fu, Fnv = 0.45 Fu (0.55 threads excluded), phi 0.75 / Omega 2.00, J3-3 interaction."
    c.references.append(f"{REF_370} J3")
    return c


# ================================================================ HSS joints
def hss_joint(inputs: dict) -> Calc:
    """WHEN: a tube member is welded to the face of another tube (branch on chord): a cross member on a rail,
    a post on a rail, a brace. The chord wall can plastify or punch long before the members fail.

    inputs: type 'round_T' | 'round_X' | 'rect_branch'; chord {D, t} or {B, H, t}; branch {D, t} or {B, H, t};
    Pr (branch axial, lb), Mr_ip, Mr_op (branch moments, lb-in, rect only), theta_deg, chord_U (utilization of
    the chord from its own axial and bending, 0..1), chord_in_tension, l_end."""
    c = Calc("hss_joint", "Tube-to-tube welded joint (chord face)")
    c.inputs = inputs
    method = _method(inputs, c)
    typ = inputs.get("type")
    mat = MT.get(inputs.get("material") or c.default(inputs, "material", "A554-304", "304 tube"))
    tf = float(inputs.get("t_factor", 0.95))
    ch, br = inputs.get("chord") or {}, inputs.get("branch") or {}
    Pr = abs(float(inputs.get("Pr", 0.0)))
    th = float(inputs.get("theta_deg", 90.0))
    U = float(inputs.get("chord_U") if inputs.get("chord_U") is not None else
              c.default(inputs, "chord_U", 0.5, "chord utilization 0.5 for Qf (take it from the chord's member check)"))
    cten = bool(inputs.get("chord_in_tension", False))
    if typ in ("round_T", "round_X"):
        cap, d = CN.round_hss_joint(float(ch["D"]), float(ch["t"]) * tf, float(br["D"]), float(br["t"]) * tf,
                                    mat.Fy, mat.Fy, th, "T" if typ == "round_T" else "X", U, cten, method,
                                    inputs.get("l_end"))
        c.ratio("branch axial vs chord face", Pr, cap, d["governs"], d["clause"])
        for k, v in d["limit_states"].items():
            c.r(k, v, "lb available")
        for lim in d["limits_violated"]:
            c.warn("outside AISC 370 Table K2.1a: " + lim + " (rational analysis needed)")
        if inputs.get("Mr_ip") or inputs.get("Mr_op"):
            c.warn("branch moments on round HSS joints: AISC 370 Chapter K covers truss (axial) joints only; "
                   "moment joints need a rational analysis or a gusset / collar")
    elif typ == "rect_branch":
        d = CN.rect_hss_branch(float(ch["B"]), float(ch.get("H", ch["B"])), float(ch["t"]) * tf, float(br["B"]),
                               float(br["H"]), mat.Fy, th, Pr, U, cten, method)
        c.ratio("branch axial vs chord wall plastification", Pr, d["P"], rule=d["clause"])
        Mip, Mop = abs(float(inputs.get("Mr_ip", 0.0))), abs(float(inputs.get("Mr_op", 0.0)))
        rint = Pr / d["P"] + Mip / d["M_in_plane"] + Mop / d["M_out_of_plane"]
        c.ratio("branch moments vs chord wall plastification", Mip / d["M_in_plane"] + Mop / d["M_out_of_plane"], 1.0,
                f"Mip {Mip:.0f}, Mop {Mop:.0f} lb-in", d["clause"])
        c.ratio("combined P + Mip + Mop", rint, 1.0, "linear interaction (conservative)",
                d["clause"])
        c.r("beta", d["beta"])
        c.r("Qf", d["Qf"])
        c.warn("rectangular chord joints are outside AISC 370 Chapter K; AISC 360-22 Chapter K forms with stainless "
               "Fy are a rational analysis: an engineer reviews it")
    else:
        raise InputError("type must be round_T, round_X or rect_branch")
    c.references.append(f"{REF_370} Chapter K; ANSI/AISC 360-22 Chapter K")
    return c


# ================================================================ concentrated load on a tube wall
def concentrated_load(inputs: dict) -> Calc:
    """WHEN: a point load lands on a tube wall: a tank leg on a rail, a fork tine under a rail, a foot under a
    rail, a pipe support on a rail. The wall crushes or the web cripples before the member bends.

    inputs: tube {shape: rect, B, H, t} or {shape: round, D, t}; R (lb); lb (bearing length along the member, in);
    Bp (bearing width across a round tube, in); case for rect: EOF | IOF | ETF | ITF (AISC 370 Table J12.2)."""
    c = Calc("concentrated_load", "Concentrated load on a tube wall")
    c.inputs = inputs
    method = _method(inputs, c)
    sec = SC.from_spec(inputs.get("tube") or {})
    mat = MT.get(inputs.get("material") or c.default(inputs, "material", "A554-304", "304 tube"))
    R = need(inputs, "R", lo=0.0)
    if sec.shape == "rect":
        lb = need(inputs, "lb", lo=0.0)
        case = inputs.get("case") or c.default(inputs, "case", "IOF", "interior one-flange loading")
        cap, d = CN.rect_hss_concentrated(sec.t, sec.elements["h_flat"], sec.elements["r_in"], lb, mat.Fy, case, method)
        c.ratio("web local yielding / crippling", R, cap, d["case"], d["clause"])
        for lim in d["limits_violated"]:
            c.warn("outside the J12 limits: " + lim)
    elif sec.shape == "round":
        Bp = need(inputs, "Bp", lo=0.0, strict_lo=True)
        U = float(inputs.get("chord_U", 0.5))
        if "chord_U" not in inputs:
            c.assume("tube utilization 0.5 for Qf")
        cap, d = CN.round_hss_plate(sec.dims["D"], sec.t, Bp, mat.Fy, 90.0, U, False, method)
        c.ratio("round tube wall local yielding", R, cap, f"bearing width {Bp:g} in", d["clause"])
        c.warn("round tube wall under a point load: AISC 360 K1 form used by analogy for stainless")
    else:
        raise InputError("tube shape must be rect or round")
    c.references.append(f"{REF_370} J12; ANSI/AISC 360-22 Table K1.1")
    return c


# ================================================================ plate panel (Roark)
def plate(inputs: dict) -> Calc:
    """WHEN: a flat plate carries pressure or a spread load between supports: a deck plate, a drip pan, a pump
    base plate between stiffeners, a tank-leg pad, a panel back.

    inputs: a, b (panel sides, in), t (in), q (psi uniform) or P with A (lb over in2), edges simple | fixed,
    material, defl_limit (in, optional)."""
    c = Calc("plate", "Rectangular plate under uniform load (Roark)")
    c.inputs = inputs
    a, b = need(inputs, "a", lo=0.0, strict_lo=True), need(inputs, "b", lo=0.0, strict_lo=True)
    t = need(inputs, "t", lo=0.0, strict_lo=True)
    if "q" in inputs:
        q = need(inputs, "q", lo=0.0)
    else:
        q = need(inputs, "P", lo=0.0) / (a * b)
        c.assume("total load P spread uniformly over the whole panel")
    mat = MT.get(inputs.get("material") or c.default(inputs, "material", "A240-304", "304 plate"))
    edges = inputs.get("edges") or c.default(inputs, "edges", "simple", "simply supported edges (conservative)")
    res = B.plate_uniform(q, a, b, t, mat.E, edges)
    allow = mat.Fy / 1.67
    c.r("max bending stress", res["sigma_max"], "psi")
    c.r("max deflection", res["defl_max"], "in")
    c.ratio("plate bending stress (first yield / 1.67)", res["sigma_max"], allow,
            f"elastic surface stress vs Fy/1.67 = {allow:.0f} psi", "elastic, ASD first-yield basis")
    if inputs.get("defl_limit"):
        c.ratio("plate deflection", res["defl_max"], float(inputs["defl_limit"]), rule="serviceability (input)")
    if "note" in res:
        c.warn(res["note"])
    c.references.append(res["case"])
    c.method = "Small-deflection plate theory coefficients (Roark Table 11.4)."
    return c
