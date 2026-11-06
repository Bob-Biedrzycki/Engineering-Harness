"""Member strength: tension, compression, flexure, shear, torsion and their interaction.

Stainless (austenitic, duplex): ANSI/AISC 370-21. Carbon: ANSI/AISC 360-22. ASD (Omega) or LRFD (phi).
Every function returns (available_strength, detail dict). Units: lb, in, psi, lb-in.

Implemented, AISC 370-21 (clause in brackets):
- section classification for compression and flexure [B4.1, Tables B4.1a/b]; design wall thickness is the
  Section's t (sections.py applies B4.2)
- tension yielding / rupture [D2]
- flexural buckling with the three stainless curves A, B, C [E3, Table E3.1]: Fcr = Fy (plateau),
  1.2 beta1^((Fy/Fe)^alpha) Fy (inelastic), beta2 Fe (elastic); slender rectangular HSS walls by effective width
  [E7-6, cold-formed HSS], slender round HSS [E7-8]
- flexure: rectangular HSS yielding / flange local buckling / web local buckling [F7], round HSS [F8], solid
  rounds and bars [F9 yielding]; open shapes yielding only (lateral-torsional buckling flagged, not computed)
- shear: rectangular HSS [G3 with G2.2 Cv2, kv = 5], round HSS [G4]
- torsion: rectangular HSS [G8.2], round HSS [G8.1]
- combined forces [H1-1a/b], with torsion [H2-1] when Tr > 0.2 Tc
Carbon steel uses the AISC 360-22 counterparts (E3, E7, F7, F8, G4, G5, H1, H3).

Every AISC 370 equation used here was checked against the rendered specification page (REVIEW-LOG pass 2).
"""
from __future__ import annotations

import math

from .core import InputError

ASD, LRFD = "ASD", "LRFD"
NU = 0.3

# (phi, Omega) by limit state, AISC 370-21 / AISC 360-22 (identical values)
FACTORS = {
    "tension_yield": (0.90, 1.67), "tension_rupture": (0.75, 2.00), "compression": (0.90, 1.67),
    "flexure": (0.90, 1.67), "shear": (0.90, 1.67), "torsion": (0.90, 1.67),
}
# AISC 360-22 G2.1(a): rolled I-shape webs meeting h/tw <= 2.24 sqrt(E/Fy) use phi 1.00 / Omega 1.50 (not used for HSS)

CURVES = {"A": (0.56, 0.759, 0.409, 0.690), "B": (0.58, 0.891, 0.455, 0.820), "C": (0.69, 1.195, 0.501, 0.820)}


def available(nominal: float, limit_state: str, method: str) -> float:
    phi, om = FACTORS[limit_state]
    if method == ASD:
        return nominal / om
    if method == LRFD:
        return nominal * phi
    raise InputError(f"design method must be ASD or LRFD, got {method!r}")


# ---------------------------------------------------------------- classification
def classify(sec, mat) -> dict:
    """Width-to-thickness classification [AISC 370 B4.1 / AISC 360 B4.1]."""
    E, Fy, ss = mat.E, mat.Fy, mat.stainless
    rt = math.sqrt(E / Fy)
    out = {}
    if sec.shape == "rect":
        bt, ht = sec.elements["b_t"], sec.elements["h_t"]
        lr_c = (1.24 if ss else 1.40) * rt
        out["compression"] = {"walls_b_t": bt, "walls_h_t": ht, "lambda_r": lr_c,
                              "class": "slender" if max(bt, ht) > lr_c else "nonslender"}
        lpf, lrf = ((1.17, 1.24) if ss else (1.12, 1.40))
        lpw, lrw = ((2.54, 3.01) if ss else (2.42, 5.70))
        out["flexure_flange"] = {"lambda_p": lpf * rt, "lambda_r": lrf * rt}
        out["flexure_web"] = {"lambda_p": lpw * rt, "lambda_r": lrw * rt}
    elif sec.shape == "round":
        Dt = sec.elements["D_t"]
        lr_c = (0.10 if ss else 0.11) * E / Fy
        out["compression"] = {"D_t": Dt, "lambda_r": lr_c, "class": "slender" if Dt > lr_c else "nonslender"}
        lp, lr = ((0.08, 0.31) if ss else (0.07, 0.31))
        out["flexure"] = {"lambda_p": lp * E / Fy, "lambda_r": lr * E / Fy}
    elif sec.shape in ("angle", "channel", "ishape", "flat"):
        lr = (0.41 if ss else 0.45) * rt
        key = {"angle": "b_t", "channel": "bf_tf", "ishape": "bf_2tf", "flat": "b_t"}[sec.shape]
        v = sec.elements.get(key, 0.0)
        out["compression"] = {"b_t": v, "lambda_r": lr, "class": "slender" if v > lr else "nonslender"}
    else:
        out["compression"] = {"class": "nonslender"}
    return out


# ---------------------------------------------------------------- tension
def tension(sec, mat, method=ASD, An=None, U=1.0):
    Pn_y = mat.Fy * sec.A
    Ae = (An if An is not None else sec.A) * U
    Pn_r = mat.Fu * Ae
    a_y, a_r = available(Pn_y, "tension_yield", method), available(Pn_r, "tension_rupture", method)
    return min(a_y, a_r), {"Pn_yield": Pn_y, "Pn_rupture": Pn_r, "governs": "yield" if a_y <= a_r else "rupture",
                           "clause": "AISC 370 D2" if mat.stainless else "AISC 360 D2"}


# ---------------------------------------------------------------- compression
def curve_for(sec, axis: str) -> str:
    """Stainless flexural buckling curve [AISC 370 Table E3.1]."""
    if sec.shape == "rect":
        return "C"
    if sec.shape == "round":
        return "B"
    if sec.shape == "ishape" and axis == "major":
        return "B"
    return "A"


def fcr_stainless(Fy, Fe, curve):
    alpha, b0, b1, b2 = CURVES[curve]
    r = Fy / Fe
    if r <= (b0 / math.pi) ** 2:
        return Fy, "E3-2 (yield plateau)"
    if r <= 3.20:
        return 1.2 * b1 ** (r ** alpha) * Fy, "E3-3 (inelastic)"
    return b2 * Fe, "E3-4 (elastic)"


def fcr_carbon(Fy, Fe):
    if Fy / Fe <= 2.25:
        return 0.658 ** (Fy / Fe) * Fy, "AISC 360 E3-2"
    return 0.877 * Fe, "AISC 360 E3-3"


def compression(sec, mat, Lc_z: float, Lc_y: float | None = None, method=ASD):
    """Flexural buckling about both axes. Lc_z: effective length for buckling about local z (in the x-y plane,
    radius rz); Lc_y about local y. For angles the minor principal radius is used with the larger Lc."""
    if Lc_y is None:
        Lc_y = Lc_z
    E, Fy = mat.E, mat.Fy
    cl = classify(sec, mat)
    det = {"classification": cl["compression"]}
    cases = []
    if sec.shape == "angle":
        cases.append(("principal minor", max(Lc_z, Lc_y), sec.r_min, "minor"))
    else:
        cases.append(("about z", Lc_z, sec.rz, "major" if sec.Iz >= sec.Iy else "minor"))
        cases.append(("about y", Lc_y, sec.ry, "major" if sec.Iy > sec.Iz else "minor"))
    worst = None
    for name, Lc, r, axis in cases:
        if Lc <= 0:
            Fe = math.inf
        else:
            Fe = math.pi ** 2 * E / (Lc / r) ** 2
        if mat.stainless:
            cv = curve_for(sec, axis)
            Fcr, eq = fcr_stainless(Fy, Fe, cv) if math.isfinite(Fe) else (Fy, "E3-2 (Lc = 0)")
        else:
            cv = "-"
            Fcr, eq = fcr_carbon(Fy, Fe) if math.isfinite(Fe) else (Fy, "Lc = 0")
        if worst is None or Fcr < worst[1]:
            worst = (name, Fcr, eq, Lc / r if Lc > 0 else 0.0, Fe, cv)
    name, Fcr, eq, slender, Fe, cv = worst
    Ae = sec.A
    if cl["compression"]["class"] == "slender":
        Ae = _effective_area(sec, mat, Fcr)
        det["effective_area"] = Ae
    Pn = Fcr * Ae
    det.update({"axis": name, "Lc_over_r": slender, "Fe": Fe, "Fcr": Fcr, "equation": eq, "curve": cv, "Pn": Pn,
                "clause": "AISC 370 E3/E7" if mat.stainless else "AISC 360 E3/E7"})
    if slender > 200:
        det["note"] = "Lc/r > 200 (AISC 370 E2 user note: preferably not exceeded)"
    if sec.shape in ("angle", "channel"):
        det["note"] = "flexural-torsional buckling (E4/E5) not evaluated; flexural buckling only"
    return available(Pn, "compression", method), det


def _effective_area(sec, mat, Fcr):
    E, Fy = mat.E, mat.Fy
    t = sec.t
    if sec.shape == "rect":
        lr = (1.24 if mat.stainless else 1.40) * math.sqrt(E / Fy)
        Ae = sec.A
        for b in (sec.elements["b_flat"], sec.elements["h_flat"]):
            lam = b / t
            if lam > lr * math.sqrt(Fy / Fcr):
                if mat.stainless:      # AISC 370 E7-4 (k = 4) and E7-6
                    Fel = 4.0 * math.pi ** 2 * E / (12 * (1 - NU ** 2) * lam ** 2)
                    q = math.sqrt(Fel / Fcr)
                    be = min(b, b * (1 - 0.22 * q) * q)
                else:                  # AISC 360-22 E7-3, Table E7.1 case (b) HSS walls: c1 0.20, c2 1.38
                    Fel = (1.38 * lr / lam) ** 2 * Fy
                    q = math.sqrt(Fel / Fcr)
                    be = min(b, b * (1 - 0.20 * q) * q)
                Ae -= 2 * (b - be) * t
        return Ae
    if sec.shape == "round":
        lam = sec.elements["D_t"]
        if mat.stainless:              # AISC 370 E7-7 / E7-8
            lr = 0.10 * E / Fy
            if lam <= lr * Fy / Fcr:
                return sec.A
            if lam >= 2.8 * lr * Fy / Fcr:
                raise InputError(f"round HSS D/t = {lam:.1f} is beyond the E7-8 range (2.8 lambda_r Fy/Fcr): "
                                 "outside AISC 370; use a thicker wall")
            return min(sec.A, (0.6 * lr / lam * Fy / Fcr + 0.4) * sec.A)
        return min(sec.A, (0.038 * E / (Fy * lam) + 2.0 / 3.0) * sec.A)   # AISC 360 E7-2
    raise InputError(f"slender {sec.shape} in compression is outside this library (AISC E7 effective width for "
                     "open shapes); use a stockier section or a hand check")


# ---------------------------------------------------------------- flexure
def flexure(sec, mat, axis: str = "z", method=ASD, Lb: float = 0.0, Cb: float = 1.0):
    """Available moment about local z (default, bending over the depth H) or y."""
    E, Fy = mat.E, mat.Fy
    S = sec.Sz if axis == "z" else sec.Sy
    Z = sec.Zz if axis == "z" else sec.Zy
    Mp = Fy * Z
    det = {"Mp": Mp, "My": Fy * S}
    note = None
    if sec.shape == "rect":
        cl = classify(sec, mat)
        # compression flange is the face across the bending axis
        if axis == "z":
            bf, hw = sec.elements["b_flat"], sec.elements["h_flat"]
        else:
            bf, hw = sec.elements["h_flat"], sec.elements["b_flat"]
        t = sec.t
        lf, lw = bf / t, hw / t
        lpf, lrf = cl["flexure_flange"]["lambda_p"], cl["flexure_flange"]["lambda_r"]
        lpw, lrw = cl["flexure_web"]["lambda_p"], cl["flexure_web"]["lambda_r"]
        Mn_f = Mp
        if lf > lrf:
            Se = _rect_Se(sec, axis, mat)
            Mn_f = Fy * Se
            det["Se"] = Se
            det["flange"] = "slender"
        elif lf > lpf:
            if mat.stainless:
                Mn_f = Mp - (Mp - Fy * S) * (lf - lpf) / (lrf - lpf)
            else:
                Mn_f = Mp - (Mp - Fy * S) * (3.57 * lf * math.sqrt(Fy / E) - 4.0)
            det["flange"] = "noncompact"
        else:
            det["flange"] = "compact"
        Mn_w = Mp
        if lw > lrw:
            det["web"] = "slender"
            if mat.stainless:
                # AISC 370 F7-6 / F7-7 with Rpg from F5-4, aw = 2 h t / (b t) <= 10 (pass 3, CPM-190 F-03)
                aw = min(2 * hw / bf, 10.0)
                Rpg = min(1.0, 1 - aw / (6.75 + 2.12 * aw) * (lw / lrw - 1.0))
                Sc = det.get("Se", _rect_Se(sec, axis, mat) if lf > lrf else S)
                Mn_w = Rpg * Fy * Sc
                det["Rpg"] = Rpg
            else:
                Mn_w = Fy * S
                note = "carbon slender web: limited to Fy S; AISC 360 F7 slender-web provisions not evaluated"
        elif lw > lpw:
            if mat.stainless:
                Mn_w = Mp - (Mp - Fy * S) * (lw - lpw) / (lrw - lpw)
            else:
                Mn_w = Mp - (Mp - Fy * S) * (0.305 * lw * math.sqrt(Fy / E) - 0.738)
            det["web"] = "noncompact"
        else:
            det["web"] = "compact"
        Mn = min(Mp, Mn_f, Mn_w)
        det.update({"flange_b_t": lf, "web_h_t": lw, "clause": "AISC 370 F7" if mat.stainless else "AISC 360 F7"})
        depth = sec.dims["H"] if axis == "z" else sec.dims["B"]
        width = sec.dims["B"] if axis == "z" else sec.dims["H"]
        if depth / width > 3:
            note = f"h/b = {depth / width:.2f} > 3: outside AISC F7 (lateral-torsional buckling possible); hand check"
        if not mat.stainless and det.get("flange") == "slender":
            note = "carbon slender flange: effective width by the AISC 360-16 F7-4 form; confirm against 360-22"
    elif sec.shape == "round":
        Dt = sec.elements["D_t"]
        cl = classify(sec, mat)["flexure"]
        lp, lr = cl["lambda_p"], cl["lambda_r"]
        if Dt <= lp:
            Mn, det["class"] = Mp, "compact"
        elif Dt <= lr:
            if mat.stainless:
                Mn = min(Mp, (1 + 0.068 * lr / Dt) * Fy * S)      # AISC 370 F8-2
            else:
                Mn = min(Mp, (0.021 * E / Dt + Fy) * S)          # AISC 360 F8-2
            det["class"] = "noncompact"
        else:
            raise InputError(f"round HSS D/t = {Dt:.1f} exceeds lambda_r = {lr:.1f}: slender, outside F8")
        det.update({"D_t": Dt, "clause": "AISC 370 F8" if mat.stainless else "AISC 360 F8"})
    elif sec.shape in ("rod",):
        Mn = Mp if mat.stainless else min(Mp, 1.6 * Fy * S)
        det["clause"] = "AISC 370 F9-1" if mat.stainless else "AISC 360 F11-1"
    elif sec.shape in ("bar", "flat"):
        Mn = Mp if mat.stainless else min(Mp, 1.6 * Fy * S)
        det["clause"] = "AISC 370 F9-1 yielding" if mat.stainless else "AISC 360 F11-1"
        if sec.shape == "flat" and axis == "y" and Lb > 0:
            d, t = sec.dims["b"], sec.dims["t"]
            if Lb * d / t ** 2 > 0.08 * E / Fy:
                note = "flat bar on edge: lateral-torsional buckling (F9-2/3) not evaluated; brace it or hand check"
    elif sec.shape == "ishape" and axis == "z":
        if mat.stainless:
            Mn = Mp
            note = "AISC 370 F2 lateral-torsional buckling not evaluated: valid only for a continuously braced flange"
            det["clause"] = "AISC 370 F2-1 yielding"
        else:
            Mn = _ltb_carbon_ishape(sec, mat, Lb, Cb, det)
            det["clause"] = "AISC 360 F2"
    else:
        Mn = Fy * S
        note = (f"{sec.shape}: Mn taken as the first-yield moment Fy S; lateral-torsional and local buckling "
                "(F6/F10) not evaluated")
        det["clause"] = "AISC F6/F10 (yield moment only)"
    if note:
        det["note"] = note
    det["Mn"] = Mn
    return available(Mn, "flexure", method), det


def _rect_Se(sec, axis, mat):
    """Effective section modulus with the compression flange reduced [AISC 370 F7-4 / AISC 360 F7-4]."""
    E, Fy, t = mat.E, mat.Fy, sec.t
    if axis == "z":
        b, H, I, A = sec.elements["b_flat"], sec.dims["H"], sec.Iz, sec.A
    else:
        b, H, I, A = sec.elements["h_flat"], sec.dims["B"], sec.Iy, sec.A
    lam = b / t
    if mat.stainless:
        Fel = 4.0 * math.pi ** 2 * E / (12 * (1 - NU ** 2) * lam ** 2)
        q = math.sqrt(Fel / Fy)
        be = min(b, b * (1 - 0.22 * q) * q)
    else:
        be = min(b, 1.92 * t * math.sqrt(E / Fy) * (1 - 0.38 / lam * math.sqrt(E / Fy)))
    dA = (b - be) * t
    yf = H / 2 - t / 2
    A2 = A - dA
    c = -dA * yf / A2                       # centroid moves away from the compression flange
    I2 = I - dA * yf ** 2 - A2 * c ** 2     # about the new centroid
    return I2 / (H / 2 - c)


def _ltb_carbon_ishape(sec, mat, Lb, Cb, det):
    E, Fy = mat.E, mat.Fy
    Mp = Fy * sec.Zz
    ry = sec.ry
    h0 = sec.elements["h0"]
    rts = math.sqrt(math.sqrt(sec.Iy * sec.Cw) / sec.Sz)
    c = 1.0
    Lp = 1.76 * ry * math.sqrt(E / Fy)
    jc = sec.J * c / (sec.Sz * h0)
    Lr = 1.95 * rts * E / (0.7 * Fy) * math.sqrt(jc + math.sqrt(jc ** 2 + 6.76 * (0.7 * Fy / E) ** 2))
    if Lb <= Lp:
        Mn = Mp
    elif Lb <= Lr:
        Mn = min(Mp, Cb * (Mp - (Mp - 0.7 * Fy * sec.Sz) * (Lb - Lp) / (Lr - Lp)))
    else:
        Fcr = Cb * math.pi ** 2 * E / (Lb / rts) ** 2 * math.sqrt(1 + 0.078 * jc * (Lb / rts) ** 2)
        Mn = min(Mp, Fcr * sec.Sz)
    det.update({"Lp": Lp, "Lr": Lr, "Lb": Lb, "Cb": Cb})
    return Mn


# ---------------------------------------------------------------- shear
def _cv2_stainless(lam, kv, E, Fy):
    """AISC 370 G2.2 web shear buckling coefficient (G2-8..G2-11)."""
    x = lam / math.sqrt(kv * E / Fy)
    if x <= 0.33:
        return 1.2
    if x <= 0.97:
        return 1.2 - 0.62 * (x - 0.33)
    if x <= 2.68:
        return (5.02 - x) / (1.62 + 3.55 * x)
    return 1.51 / x ** 2


def _cv2_carbon(lam, kv, E, Fy):
    """AISC 360-22 G2.2."""
    a = 1.10 * math.sqrt(kv * E / Fy)
    if lam <= a:
        return 1.0
    if lam <= 1.37 * math.sqrt(kv * E / Fy):
        return a / lam
    return 1.51 * kv * E / (lam ** 2 * Fy)


def _round_cv_stainless(Dt, L_over_D, E, Fy, kind):
    """AISC 370-21 G4 (kind='shear', L = Lv) or G8.1 (kind='torsion', L = member length), exact.

    Medium length (L/D <= 4.21 sqrt(lambda), G4-2 / G8-2): CvM with
      (i)   lambda <= a ((E/Fy) / sqrt(L/D))^0.80 (a outside the power)   CvM = 1.0
      (ii)  up to  b ((E/Fy) / sqrt(L/D))^0.80             CvM = 1 - 0.61 (c sqrt(sqrt(L/D) lambda^1.25 / (E/Fy)) - 0.23)
      (iii) beyond                                          CvM = d E / (sqrt(L/D) lambda^1.25 Fy)
      shear a 0.32, b 4.65, c 0.47, d 2.67; torsion a 0.26, b 3.77, c 0.54, d 2.05
    Long (CvL): (i) lambda <= p (E/Fy)^0.67: 1.0; (ii) up to q (E/Fy)^0.67:
      1 - 0.61 (s sqrt(lambda^1.5 / (E/Fy)) - 0.23); (iii) e E / (lambda^1.5 Fy)
      shear p 0.24, q 2.23, s 0.68, e 1.30; torsion p 0.20, q 1.87, s 0.77, e 1.00
    Read from the rendered specification pages 72-73 and 75 (REVIEW-LOG pass 2)."""
    ef = E / Fy
    if kind == "shear":
        a, b, cc, d, p, q, s, e = 0.32, 4.65, 0.47, 2.67, 0.24, 2.23, 0.68, 1.30
    else:
        a, b, cc, d, p, q, s, e = 0.26, 3.77, 0.54, 2.05, 0.20, 1.87, 0.77, 1.00
    LD = max(L_over_D, 1e-9)
    if LD <= 4.21 * math.sqrt(Dt):
        # the coefficient sits OUTSIDE the power: lambda <= a ((E/Fy) / sqrt(L/D))^0.80 (pass 3, CPM-190 F-01)
        lim1 = a * (ef / math.sqrt(LD)) ** 0.80
        lim2 = b * (ef / math.sqrt(LD)) ** 0.80
        if Dt <= lim1:
            cv = 1.0
        elif Dt <= lim2:
            cv = 1 - 0.61 * (cc * math.sqrt(math.sqrt(LD) * Dt ** 1.25 / ef) - 0.23)
        else:
            cv = d * ef / (math.sqrt(LD) * Dt ** 1.25)
        return min(cv, 1.0), "CvM", False
    if Dt <= p * ef ** 0.67:
        cv = 1.0
    elif Dt <= q * ef ** 0.67:
        cv = 1 - 0.61 * (s * math.sqrt(Dt ** 1.5 / ef) - 0.23)
    else:
        cv = e * ef / Dt ** 1.5
    return min(cv, 1.0), "CvL", False


def shear(sec, mat, axis: str = "y", method=ASD, Lv: float | None = None):
    """Available shear along local y (default) or z."""
    E, Fy = mat.E, mat.Fy
    det = {}
    if sec.shape == "rect":
        h = sec.elements["h_flat"] if axis == "y" else sec.elements["b_flat"]
        t = sec.t
        Aw = 2 * h * t
        lam = h / t
        Cv2 = _cv2_stainless(lam, 5.0, E, Fy) if mat.stainless else _cv2_carbon(lam, 5.0, E, Fy)
        Vn = 0.6 * Fy * Aw * Cv2
        det.update({"Aw": Aw, "h_t": lam, "Cv2": Cv2, "clause": "AISC 370 G3" if mat.stainless else "AISC 360 G4"})
    elif sec.shape == "round":
        Dt = sec.elements["D_t"]
        D = sec.dims["D"]
        LvD = (Lv / D) if Lv else 1.0
        if mat.stainless:
            Cv, which, approx = _round_cv_stainless(Dt, LvD, E, Fy, "shear")
            Vn = 0.6 * Cv * Fy * sec.A / 2
            det.update({"Cv": Cv, "branch": which, "clause": "AISC 370 G4"})
            if approx:
                det["approximation"] = "AISC 370 G4 intermediate band interpolated; hand-verify if ratio > 0.8"
        else:
            Fcr = max(1.60 * E / (math.sqrt(LvD) * Dt ** 1.25), 0.78 * E / Dt ** 1.5)
            Fcr = min(Fcr, 0.6 * Fy)
            Vn = Fcr * sec.A / 2
            det.update({"Fcr": Fcr, "clause": "AISC 360 G5"})
    else:
        Aw = sec.Avy if axis == "y" else sec.Avz
        Vn = 0.6 * Fy * Aw
        det.update({"Aw": Aw, "clause": "AISC G6 (shear yielding, no buckling reduction)"})
    det["Vn"] = Vn
    return available(Vn, "shear", method), det


# ---------------------------------------------------------------- torsion
def torsion(sec, mat, method=ASD, L: float | None = None):
    E, Fy = mat.E, mat.Fy
    det = {}
    if sec.shape == "rect":
        h = max(sec.elements["h_flat"], sec.elements["b_flat"])
        lam = h / sec.t
        if mat.stainless:
            x = lam / math.sqrt(E / Fy)
            if x <= 0.74:
                Cv = 1.2
            elif x <= 2.17:
                Cv = 1.2 - 0.28 * (x - 0.74)
            elif x <= 5.99:
                Cv = (11.23 - x) / (3.62 + 3.55 * x)
            else:
                Cv = 7.56 / x ** 2
            Tn = 0.6 * Cv * Fy * sec.C
            det.update({"Cv": Cv, "h_t": lam, "clause": "AISC 370 G8.2"})
        else:
            r = math.sqrt(E / Fy)
            if lam <= 2.45 * r:
                Fcr = 0.6 * Fy
            elif lam <= 3.07 * r:
                Fcr = 0.6 * Fy * 2.45 * r / lam
            else:
                Fcr = 0.458 * math.pi ** 2 * E / lam ** 2
            Tn = Fcr * sec.C
            det.update({"Fcr": Fcr, "clause": "AISC 360 H3.1"})
    elif sec.shape == "round":
        Dt = sec.elements["D_t"]
        D = sec.dims["D"]
        LD = (L / D) if L else 1.0
        if mat.stainless:
            Cv, which, approx = _round_cv_stainless(Dt, LD, E, Fy, "torsion")
            Tn = 0.6 * Cv * Fy * sec.C
            det.update({"Cv": Cv, "branch": which, "clause": "AISC 370 G8.1"})
            if approx:
                det["approximation"] = "AISC 370 G8.1 intermediate band interpolated; hand-verify if ratio > 0.8"
        else:
            Fcr = min(max(1.23 * E / (math.sqrt(LD) * Dt ** 1.25), 0.60 * E / Dt ** 1.5), 0.6 * Fy)
            Tn = Fcr * sec.C
            det.update({"Fcr": Fcr, "clause": "AISC 360 H3.1"})
    elif sec.shape == "rod":
        # solid round: tau = T r / J exactly
        Tn = 0.6 * Fy * sec.J / (sec.dims["D"] / 2)
        det["clause"] = "shear yielding 0.6 Fy at the surface, tau = T r / J (G9-2 analogy)"
    elif sec.shape in ("bar", "flat"):
        # solid rectangle long side b, short side c: tau_max = T / (alpha b c^2), Roark 7th Table 10.7 case 4
        b, cc = max(sec.dims["b"], sec.dims["t"]), min(sec.dims["b"], sec.dims["t"])
        alpha = _roark_alpha(b / cc)
        Tn = 0.6 * Fy * alpha * b * cc * cc
        det.update({"alpha": alpha, "clause": "shear yielding 0.6 Fy, tau = T / (alpha b c^2) (Roark Table 10.7)"})
    else:
        Tn = 0.6 * Fy * sec.J / max(sec.t, 1e-9)
        det["clause"] = "open section St Venant shear yielding 0.6 Fy (G9-2); warping stresses not evaluated"
        det["note"] = "open sections in torsion: warping normal stress not evaluated; avoid torsion on open shapes"
    det["Tn"] = Tn
    return available(Tn, "torsion", method), det


_ALPHA = [(1.0, 0.208), (1.5, 0.231), (2.0, 0.246), (2.5, 0.258), (3.0, 0.267), (4.0, 0.282), (5.0, 0.291),
          (6.0, 0.299), (10.0, 0.312), (1e9, 1.0 / 3.0)]
"""Torsional shear coefficient alpha (tau_max = T / (alpha b c^2)) for solid rectangles, b/c (Timoshenko & Goodier,
Theory of Elasticity, Table for torsion of rectangular bars; reproduced in Roark)."""


def _roark_alpha(r):
    for (r0, a0), (r1, a1) in zip(_ALPHA, _ALPHA[1:]):
        if r0 <= r <= r1:
            return a0 + (a1 - a0) * (r - r0) / (r1 - r0)
    return _ALPHA[0][1]


# ---------------------------------------------------------------- interaction
def interaction(Pr, Pc, Mrz, Mcz, Mry, Mcy, Vr=0.0, Vc=math.inf, Tr=0.0, Tc=math.inf):
    """AISC H1-1a/b, and H2-1 when Tr > 0.2 Tc. Pr may be tension or compression (Pc the matching strength)."""
    p = abs(Pr) / Pc if Pc > 0 else math.inf
    mz = abs(Mrz) / Mcz if Mcz > 0 else (math.inf if Mrz else 0.0)
    my = abs(Mry) / Mcy if Mcy > 0 else (math.inf if Mry else 0.0)
    if p >= 0.2:
        h1 = p + 8.0 / 9.0 * (mz + my)
        eq = "H1-1a"
    else:
        h1 = p / 2 + mz + my
        eq = "H1-1b"
    t = abs(Tr) / Tc if Tc > 0 and math.isfinite(Tc) else 0.0
    v = abs(Vr) / Vc if Vc > 0 and math.isfinite(Vc) else 0.0
    if t > 0.2:
        h2 = p + mz + my + (v + t) ** 2
        return max(h1, h2), ("H2-1" if h2 > h1 else eq), {"P": p, "Mz": mz, "My": my, "V": v, "T": t}
    return h1, eq, {"P": p, "Mz": mz, "My": my, "V": v, "T": t}
