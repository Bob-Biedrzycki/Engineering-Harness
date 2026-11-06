"""Feet, base plates, anchors and leveling feet: how the skid meets the floor.

Models: support_reactions, base_plate, anchors, leveling_foot. Units: lb, in, psi, lb-in.
"""
from __future__ import annotations

import math

import numpy as np

from . import connections as CN
from . import materials as MT
from . import members as MB
from . import sections as SC
from .core import Calc, InputError, need

REF_DG1 = "AISC Design Guide 1, Base Connection Design for Steel Structures, 3rd ed. (2024) / 2nd ed. (2006) method"
REF_ACI = "ACI 318-19, Building Code Requirements for Structural Concrete, Chapter 17 (anchoring to concrete)"


# ================================================================ rigid-base reactions
def rigid_reactions(points, loads, k=None, contact=True):
    """Vertical reactions of a rigid base on point supports (elastic, stiffness k each) under vertical loads and
    lateral forces at height. points: [(x, y)], loads: [(W, x, y, Fx, Fy, z)] with W downward weight.
    Returns (R array, active mask, stable flag). Supports that would pull are released when contact=True."""
    pts = np.asarray(points, float)
    n = len(pts)
    kk = np.ones(n) if k is None else np.asarray(k, float)
    W = sum(l[0] for l in loads)
    Mx = sum(l[0] * l[2] + l[4] * l[5] for l in loads)     # sum of R*y must equal this
    My = sum(l[0] * l[1] + l[3] * l[5] for l in loads)     # sum of R*x must equal this
    active = np.ones(n, bool)
    for _ in range(4 * n):
        P = pts[active]
        ka = kk[active]
        A = np.array([[ka.sum(), (ka * P[:, 0]).sum(), (ka * P[:, 1]).sum()],
                      [(ka * P[:, 0]).sum(), (ka * P[:, 0] ** 2).sum(), (ka * P[:, 0] * P[:, 1]).sum()],
                      [(ka * P[:, 1]).sum(), (ka * P[:, 0] * P[:, 1]).sum(), (ka * P[:, 1] ** 2).sum()]])
        rhs = np.array([W, My, Mx])
        if np.linalg.matrix_rank(A) < 3:
            # line or point support: solve least squares, then test equilibrium
            sol, *_ = np.linalg.lstsq(A, rhs, rcond=None)
        else:
            sol = np.linalg.solve(A, rhs)
        R = np.zeros(n)
        R[active] = ka * (sol[0] + sol[1] * P[:, 0] + sol[2] * P[:, 1])
        ok = abs(R.sum() - W) < 1e-6 * max(W, 1) and abs((R * pts[:, 0]).sum() - My) < 1e-6 * max(abs(My), W, 1) \
            and abs((R * pts[:, 1]).sum() - Mx) < 1e-6 * max(abs(Mx), W, 1)
        if not contact or (R >= -1e-9 * max(W, 1)).all():
            return R, active, ok
        worst = np.argmin(np.where(active, R, np.inf))
        active[worst] = False
        if active.sum() == 0:
            return np.zeros(n), active, False
    return R, active, False


def support_reactions(inputs: dict) -> Calc:
    """WHEN: first-pass foot loads before a frame model exists, or a sanity check on a frame model's reactions;
    unequal leg loads from off-centre equipment, lateral loads at height, and the 'one foot loose' cases.

    inputs: supports [{id, x, y, k?}], loads [{name, W, x, y, z?, Fx?, Fy?}], rated_load (lb, optional),
    loose_cases: true (default) re-solves with each support removed in turn."""
    c = Calc("support_reactions", "Support (foot) reactions, rigid base")
    c.inputs = inputs
    sups = inputs.get("supports") or []
    lds = inputs.get("loads") or []
    if len(sups) < 3:
        raise InputError("at least 3 supports are needed")
    if not lds:
        raise InputError("loads are needed")
    pts = [(float(s["x"]), float(s["y"])) for s in sups]
    ids = [str(s.get("id", f"S{k + 1}")) for k, s in enumerate(sups)]
    kk = [float(s.get("k", 1.0)) for s in sups]
    L = [(float(l["W"]), float(l["x"]), float(l["y"]), float(l.get("Fx", 0)), float(l.get("Fy", 0)),
          float(l.get("z", 0))) for l in lds]
    W = sum(l[0] for l in L)
    cg = (sum(l[0] * l[1] for l in L) / W, sum(l[0] * l[2] for l in L) / W)
    c.r("total weight", W, "lb")
    c.r("CG x", cg[0], "in")
    c.r("CG y", cg[1], "in")
    if "k" not in sups[0]:
        c.assume("all supports equally stiff and the base rigid (true reactions on a flexible frame come from "
                 "frame_check; a leveling error redistributes load: see the loose cases)")
    R, act, ok = rigid_reactions(pts, L, kk)
    rows = [[ids[i], pts[i][0], pts[i][1], round(R[i], 1), "bearing" if act[i] else "LIFTED"] for i in range(len(pts))]
    c.table("reactions, all supports set", ["support", "x", "y", "R lb", "state"], rows)
    c.check("stable on its supports", ok, "equilibrium found with the bearing supports" if ok else
            "resultant outside the bearing supports: the skid tips", "statics")
    Rmax = float(R.max())
    c.r("max reaction", Rmax, "lb")
    c.r("min reaction", float(R.min()), "lb")
    c.r("max / average", Rmax / (W / len(pts)), "")
    rated = inputs.get("rated_load")
    worst = Rmax
    if inputs.get("loose_cases", True):
        lrows = []
        for i in range(len(pts)):
            p2 = [p for j, p in enumerate(pts) if j != i]
            k2 = [q for j, q in enumerate(kk) if j != i]
            R2, a2, ok2 = rigid_reactions(p2, L, k2)
            mx = float(R2.max()) if ok2 else math.inf
            lrows.append([ids[i], round(mx, 1) if ok2 else "TIPS", "yes" if ok2 else "no"])
            worst = max(worst, mx)
        c.table("one support loose (not touching)", ["loose support", "max reaction of the rest lb", "stable"], lrows)
        c.r("max reaction, one support loose", worst, "lb")
    if rated:
        c.ratio("foot load vs rating (all set)", Rmax, float(rated), rule="vendor rating")
        if inputs.get("loose_cases", True):
            c.ratio("foot load vs rating (one loose)", worst, float(rated), rule="vendor rating",
                    detail="design for this when feet are not checked tight after the first fill")
    c.method = ("Rigid base on point supports of stiffness k: reactions R_i = k_i (a + b x_i + c y_i) from vertical "
                "force and moment equilibrium; tension supports released (contact).")
    c.references.append("statics (rigid body on elastic supports)")
    return c


# ================================================================ base plate (AISC DG1)
def base_plate(inputs: dict) -> Calc:
    """WHEN: a post, leg or column lands on a base plate on concrete (anchored or not): plate thickness,
    concrete bearing, anchor tension from moment.

    inputs: P (lb, compression +), M (lb-in, optional), N (plate length in the moment direction), B (width),
    tp (in), plate_material, column {"shape": "rect"|"round", ...} , fc (psi), A2_A1 (>=1, default 1),
    anchor_edge (in, anchor centre to plate edge, for the moment case), method."""
    c = Calc("base_plate", "Base plate on concrete (AISC Design Guide 1)")
    c.inputs = inputs
    method = inputs.get("method") or c.default(inputs, "method", "ASD", "allowable strength design")
    P = need(inputs, "P", lo=0.0)
    M = abs(float(inputs.get("M", 0.0)))
    N = need(inputs, "N", lo=0.0, strict_lo=True)
    Bp = need(inputs, "B", lo=0.0, strict_lo=True)
    tp = need(inputs, "tp", lo=0.0, strict_lo=True)
    mat = MT.get(inputs.get("plate_material") or c.default(inputs, "plate_material", "A240-304", "304 plate"))
    fc = float(inputs.get("fc") or c.default(inputs, "fc", 3000.0, "concrete f'c 3000 psi: confirm the floor"))
    a2a1 = float(inputs.get("A2_A1") or c.default(inputs, "A2_A1", 1.0, "no confinement credit"))
    col = SC.from_spec(inputs.get("column") or {"shape": "rect", "B": 3, "H": 3, "t": 0.12})
    if col.shape == "rect":
        d, bf = col.dims["H"], col.dims["B"]
        m = (N - 0.95 * d) / 2
        n = (Bp - 0.95 * bf) / 2
    elif col.shape == "round":
        d = bf = col.dims["D"]
        m = n = (N - 0.8 * d) / 2
    else:
        raise InputError("column shape must be rect or round for this model")
    if m <= 0 or n <= 0:
        raise InputError("base plate is not larger than the column")
    fp_n = min(0.85 * fc * math.sqrt(max(a2a1, 1.0)), 1.7 * fc)          # J8 / DG1 3.1
    fp = fp_n / 2.31 if method == "ASD" else 0.65 * fp_n
    c.r("available bearing stress", fp, "psi")
    l = max(m, n)
    qmax = fp * Bp
    e = M / P if P > 0 else math.inf
    ecrit = N / 2 - P / (2 * qmax)
    c.r("eccentricity e = M/P", e if math.isfinite(e) else 0.0, "in")
    c.r("e_crit", ecrit, "in")
    T = 0.0
    k_t = math.sqrt(2 * 1.67) if method == "ASD" else math.sqrt(2 / 0.9)    # t = l sqrt(2 fp Omega / Fy)
    if e <= ecrit:
        Y = N - 2 * e if math.isfinite(e) else N
        q = P / Y
        fp_act = q / Bp
        c.ratio("concrete bearing", fp_act, fp, f"{fp_act:.0f} psi on Y = {Y:.2f} in", "AISC 370 J8 / DG1")
        if Y >= m:
            t_req = k_t * l * math.sqrt(fp_act / mat.Fy)
        else:
            t_req = 2.11 * math.sqrt(fp_act * Y * (m - Y / 2) / mat.Fy) if method == "LRFD" else \
                2.58 * math.sqrt(fp_act * Y * (m - Y / 2) / mat.Fy)
        c.r("bearing length Y", Y, "in")
    else:
        f = N / 2 - float(inputs.get("anchor_edge") or c.default(inputs, "anchor_edge", 1.5, "anchor 1.5 in from the edge"))
        disc = (f + N / 2) ** 2 - 2 * P * (e + f) / qmax
        if disc < 0:
            raise InputError("moment too large for this plate: no bearing solution (DG1 eq. 3.4.4): enlarge N or B")
        Y = (f + N / 2) - math.sqrt(disc)
        T = qmax * Y - P
        c.r("bearing length Y", Y, "in")
        c.r("anchor group tension T", T, "lb")
        k_y = 2.58 if method == "ASD" else 2.11      # DG1 Y < m form (CPM-190 F-05)
        t_bear = k_t * l * math.sqrt(fp / mat.Fy) if Y >= m else k_y * math.sqrt(fp * Y * (m - Y / 2) / mat.Fy)
        x = max(f - 0.95 * d / 2, 0.0)        # anchor line to the bending line at 0.95 d (DG1 3.4)
        t_tens = (2.58 if method == "ASD" else 2.11) * math.sqrt(T * x / (Bp * mat.Fy))
        t_req = max(t_bear, t_tens)
        c.check("concrete bearing at the limit", True, "bearing stress at the available limit over Y", "DG1 3.4")
    c.r("required plate thickness", t_req, "in")
    c.ratio("plate bending", t_req ** 2, tp ** 2, f"t_req {t_req:.3f} in vs tp {tp:.3f} in (ratio on t^2, i.e. on moment)",
            "AISC DG1 eq. 3.3.14 / 3.4.7 (cantilever m, n)")
    c.r("cantilever m", m, "in")
    c.r("cantilever n", n, "in")
    c.method = ("AISC Design Guide 1: uniform bearing stress block; cantilever plate bending over m, n (lambda n' "
                "omitted for HSS); large eccentricity solved for Y and anchor tension.")
    c.references += [REF_DG1, "AISC 370-21 J8 (concrete bearing: phi 0.65 / Omega 2.31)"]
    return c


# ================================================================ anchors (ACI 318-19 Ch. 17)
def anchors(inputs: dict) -> Calc:
    """WHEN: the skid is anchored (seismic site, customer requirement, overturning or sliding not resisted by
    weight and friction). Checks one anchor group: steel, concrete breakout, pullout, pryout, interaction.

    inputs: Nua (factored tension on the group, lb), Vua (factored shear, lb), n_x, n_y, s_x, s_y (in), da (in),
    hef (in), fc (psi), edges {cx_minus, cx_plus, cy_minus, cy_plus} (in, large if none), anchor_type
    'cast-in' | 'post-installed', futa, fya (psi), Ase (in2, effective threaded area), cracked (bool),
    seismic (bool), Abrg (in2, bearing area of the head, cast-in only)."""
    c = Calc("anchors", "Anchor group (ACI 318-19 Chapter 17)")
    c.inputs = inputs
    Nua = float(inputs.get("Nua", 0.0))
    Vua = float(inputs.get("Vua", 0.0))
    nx, ny = int(inputs.get("n_x", 2)), int(inputs.get("n_y", 2))
    sx, sy = float(inputs.get("s_x", 0.0)), float(inputs.get("s_y", 0.0))
    n = nx * ny
    da = need(inputs, "da", lo=0.0, strict_lo=True)
    hef = need(inputs, "hef", lo=0.0, strict_lo=True)
    fc = float(inputs.get("fc") or c.default(inputs, "fc", 3000.0, "concrete f'c 3000 psi: confirm the floor"))
    typ = inputs.get("anchor_type") or c.default(inputs, "anchor_type", "post-installed", "expansion or adhesive anchor")
    cracked = bool(inputs.get("cracked", True))
    if "cracked" not in inputs:
        c.assume("concrete cracked (ACI 17.6.2.5: uncracked credit needs analysis)")
    futa = float(inputs.get("futa") or c.default(inputs, "futa", 75000.0, "304 / 316 stainless anchor, ASTM F593 / A193 B8 cl1 min"))
    fya = float(inputs.get("fya") or c.default(inputs, "fya", 30000.0, "stainless anchor yield"))
    futa = min(futa, 1.9 * fya, 125000.0)
    Ase = float(inputs.get("Ase") or CN.tensile_stress_area(da, inputs.get("threads_per_in")))
    e = inputs.get("edges", {})
    big = 1e6
    cxm, cxp = float(e.get("cx_minus", big)), float(e.get("cx_plus", big))
    cym, cyp = float(e.get("cy_minus", big)), float(e.get("cy_plus", big))
    seismic = bool(inputs.get("seismic", False))
    lam = 1.0
    # --- steel
    phi_st, phi_sv = 0.75, 0.65
    Nsa = Ase * futa
    Vsa = 0.6 * Ase * futa
    c.ratio("steel tension (per anchor)", Nua / n, phi_st * Nsa, rule="ACI 318-19 17.6.1")
    c.ratio("steel shear (per anchor)", Vua / n, phi_sv * Vsa, rule="ACI 318-19 17.7.1")
    # --- concrete breakout in tension
    if typ == "cast-in":
        kc, phi_c = 24.0, 0.70
        psi_c = 1.0 if cracked else 1.25
    else:
        kc, phi_c = 17.0, 0.65
        psi_c = 1.0 if cracked else 1.4
        c.warn("post-installed anchor: kc = 17 and phi 0.65 are ACI defaults (Category 1); use the anchor's "
               "ICC-ES evaluation report values when the product is chosen")
    Nb = kc * lam * math.sqrt(fc) * hef ** 1.5
    if hef > 11:
        Nb = min(Nb, 16 * lam * math.sqrt(fc) * hef ** (5.0 / 3.0)) if typ == "cast-in" else Nb
    ANco = 9 * hef * hef
    wx = min(cxm, 1.5 * hef) + (nx - 1) * sx + min(cxp, 1.5 * hef)
    wy = min(cym, 1.5 * hef) + (ny - 1) * sy + min(cyp, 1.5 * hef)
    ANc = min(wx * wy, n * ANco)
    camin = min(cxm, cxp, cym, cyp)
    psi_ed = 1.0 if camin >= 1.5 * hef else 0.7 + 0.3 * camin / (1.5 * hef)
    psi_cp = 1.0
    if typ != "cast-in" and not cracked:
        cac = 2.0 * hef
        psi_cp = 1.0 if camin >= cac else max(camin / cac, 1.5 * hef / cac)
    Ncbg = ANc / ANco * psi_ed * psi_c * psi_cp * Nb
    sf = 0.75 if seismic else 1.0
    c.r("Nb (single anchor basic breakout)", Nb, "lb")
    c.r("Ncbg (group breakout)", Ncbg, "lb")
    c.ratio("concrete breakout, tension", Nua, sf * phi_c * Ncbg, rule="ACI 318-19 17.6.2" + (" with 17.10.5.4 0.75" if seismic else ""))
    if typ == "cast-in" and inputs.get("Abrg"):
        Np = 8 * float(inputs["Abrg"]) * fc
        psi_cP = 1.0 if cracked else 1.4
        c.ratio("pullout (per anchor)", Nua / n, sf * phi_c * psi_cP * Np, rule="ACI 318-19 17.6.3")
    # --- shear breakout toward the nearest edge in the shear direction (x+ assumed)
    Ncp = Ncbg
    kcp = 1.0 if hef < 2.5 else 2.0
    c.ratio("concrete pryout, shear", Vua, sf * phi_c * kcp * Ncp, rule="ACI 318-19 17.7.3")
    ca1 = cxp
    if ca1 < 1e5:
        le = min(hef, 8 * da)
        Vb = min(7 * (le / da) ** 0.2 * math.sqrt(da) * lam * math.sqrt(fc) * ca1 ** 1.5,
                 9 * lam * math.sqrt(fc) * ca1 ** 1.5)
        AVco = 4.5 * ca1 ** 2
        AVc = min(1.5 * ca1, cym) + (ny - 1) * sy + min(1.5 * ca1, cyp)
        AVc *= min(1.5 * ca1, float(inputs.get("ha", 1.5 * ca1)))
        ca2 = min(cym, cyp)
        psi_edV = 1.0 if ca2 >= 1.5 * ca1 else 0.7 + 0.3 * ca2 / (1.5 * ca1)
        Vcbg = AVc / AVco * psi_edV * Vb
        c.r("Vcbg (shear breakout to the +x edge)", Vcbg, "lb")
        c.ratio("concrete breakout, shear (+x edge)", Vua, sf * 0.70 * Vcbg, rule="ACI 318-19 17.7.2")
    # --- interaction
    rn = max(ch.ratio for ch in c.checks if "tension" in ch.name or "pullout" in ch.name)
    rv = max(ch.ratio for ch in c.checks if "shear" in ch.name)
    inter = rn + rv if (rn > 0.2 and rv > 0.2) else max(rn, rv)
    c.ratio("tension-shear interaction", inter, 1.2 if (rn > 0.2 and rv > 0.2) else 1.0,
            f"N {rn:.3f} + V {rv:.3f}", "ACI 318-19 17.8")
    c.assume("Nua, Vua are factored (strength-level) loads: ACI 318 is strength design. From ASD results use the "
             "LRFD combination, or multiply ASD seismic forces by 1/0.7")
    c.method = "ACI 318-19 Chapter 17: steel, concrete breakout (projected areas), pullout, pryout, interaction."
    c.references.append(REF_ACI)
    return c


# ================================================================ leveling foot
def leveling_foot(inputs: dict) -> Calc:
    """WHEN: the skid stands on threaded leveling feet (sanitary feet with a stud and a pad) on the floor.

    inputs: R (max vertical reaction, lb), H (lateral force at the foot, lb), rated_load (lb, vendor),
    stud_d (in), stud_root_d (in, optional), exposed (in, stud length from the pad swivel to the frame nut),
    stud_material, pad_d (in), floor_allow (psi), mu (friction), method."""
    c = Calc("leveling_foot", "Leveling foot: rating, stud, floor bearing, sliding")
    c.inputs = inputs
    method = inputs.get("method") or c.default(inputs, "method", "ASD", "allowable strength design")
    R = need(inputs, "R", lo=0.0)
    H = abs(float(inputs.get("H", 0.0)))
    rated = inputs.get("rated_load")
    if rated:
        c.ratio("vertical load vs vendor rating", R, float(rated), rule="vendor catalog (static rating)")
    else:
        c.warn("no vendor rating given: the foot's own rating is the first check; get it from the cut sheet")
    d = need(inputs, "stud_d", lo=0.0, strict_lo=True)
    dr = float(inputs.get("stud_root_d") or CN.minor_diameter(d, inputs.get("threads_per_in")))
    e = need(inputs, "exposed", lo=0.0)
    mat = MT.get(inputs.get("stud_material") or c.default(inputs, "stud_material", "A276-304", "304 stud"))
    rod = SC.solid_round(dr, label=f"{d:g} stud, root {dr:.3f}")
    Pc, dc = MB.compression(rod, mat, 2.1 * e if e > 0 else 0.0, None, method)
    Mc, _ = MB.flexure(rod, mat, "z", method)
    M = H * e
    r, eq, parts = MB.interaction(-R, Pc, M, Mc, 0.0, Mc)
    c.r("stud root diameter", dr, "in")
    c.r("stud moment H x exposed", M, "lb-in")
    c.ratio("stud axial + bending", r, 1.0, f"{eq}: fixed-free stud, K = 2.1 over {e:.2f} in", "AISC 370 E3, F9, H1")
    pad = inputs.get("pad_d")
    if pad:
        A = math.pi * float(pad) ** 2 / 4
        q = R / A
        qa = inputs.get("floor_allow")
        if qa is None:
            fc = 3000.0
            qa = 0.85 * fc / 2.31
            c.assume("floor allowable bearing 0.85 f'c / 2.31 with f'c 3000 psi (bare concrete; a coated or tiled "
                     "floor or a drain grate needs its own value)")
        c.r("pad bearing pressure", q, "psi")
        c.ratio("floor bearing under the pad", q, float(qa), rule="AISC 370 J8 / floor allowable")
    mu = inputs.get("mu")
    if H > 0:
        if mu is None:
            mu = 0.3
            c.assume("friction coefficient 0.3 (rubber or polymer pad on a wet washdown floor is lower than dry; "
                     "use anchors where sliding governs)")
        c.ratio("sliding (lateral / friction)", H, float(mu) * R, rule="Coulomb friction")
    c.method = "Vendor rating; stud as a fixed-free beam-column on its thread root; pad pressure; friction."
    c.references.append("AISC 370-21 E3, F9, H1")
    return c
