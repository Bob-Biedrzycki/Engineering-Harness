"""Section properties for the shapes a skid frame uses.

Axis convention (same as frame.py): the member runs along local x. A section's depth H lies along local y
and its width B along local z. Iz bends the member in the x-y plane (major axis for a section deeper than wide);
Iy bends it in the x-z plane. Sz, Sy, Zz, Zy follow. J is the St Venant torsion constant (stiffness);
C is the HSS torsional constant used for torsional stress tau = T / C (AISC 370 G8 user note).

Design thickness (AISC 370-21 B4.2): HSS properties use t_design = t_factor x nominal wall. The spec default is
0.95; 1.0 is allowed only when the product's minimum wall tolerance is tighter than -5 %. The factor is an input.

Rectangular tube corners: outside radius r_out (default 2 t_design, the AISC Manual practice); the inside radius
is r_out - t. Properties are exact for that rounded geometry (rectangle minus corner spandrels).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .core import InputError


@dataclass
class Section:
    shape: str
    label: str
    dims: dict
    A: float
    Iz: float          # about local z (bending in x-y plane, depth H direction)
    Iy: float          # about local y
    Sz: float
    Sy: float
    Zz: float
    Zy: float
    J: float           # St Venant torsion constant
    C: float = 0.0     # HSS torsional constant (stress)
    Cw: float = 0.0    # warping constant (open sections)
    t: float = 0.0     # design wall / plate thickness
    elements: dict = field(default_factory=dict)   # width-to-thickness data for AISC 370 B4.1
    closed: bool = False
    Avy: float = 0.0   # shear area resisting Vy (shear along local y, the depth H); 0 = no shear deformation
    Avz: float = 0.0   # shear area resisting Vz (shear along local z, the width B)

    @property
    def rz(self):
        return math.sqrt(self.Iz / self.A)

    @property
    def ry(self):
        return math.sqrt(self.Iy / self.A)

    @property
    def r_min(self):
        rmin = self.elements.get("r_principal_min")
        return rmin if rmin else min(self.rz, self.ry)

    def weight_per_in(self, density: float) -> float:
        return self.A * density

    def to_dict(self):
        return {"shape": self.shape, "label": self.label, "dims": self.dims, "A": self.A, "Iz": self.Iz, "Iy": self.Iy,
                "Sz": self.Sz, "Sy": self.Sy, "Zz": self.Zz, "Zy": self.Zy, "J": self.J, "C": self.C, "Cw": self.Cw,
                "t_design": self.t, "rz": self.rz, "ry": self.ry, "elements": self.elements}


def _pos(name, v):
    if v is None or not (v > 0):
        raise InputError(f"section dimension '{name}' must be > 0, got {v}")
    return float(v)


# ---------------------------------------------------------------- round tube / pipe
def round_tube(D: float, t: float, t_factor: float = 0.95, label: str | None = None) -> Section:
    D, t = _pos("D", D), _pos("t", t)
    td = t * t_factor
    if 2 * td >= D:
        raise InputError("round tube wall is too thick for its diameter")
    d = D - 2 * td
    A = math.pi / 4 * (D ** 2 - d ** 2)
    I = math.pi / 64 * (D ** 4 - d ** 4)
    S = 2 * I / D
    Z = (D ** 3 - d ** 3) / 6.0
    J = 2 * I
    C = math.pi * (D - td) ** 2 * td / 2.0          # AISC 370 G8 user note
    return Section("round", label or f"{D:g} OD x {t:g} wall", {"D": D, "t_nom": t, "t_factor": t_factor},
                   A, I, I, S, S, Z, Z, J, C, 0.0, td, {"D_t": D / td}, True, A / 2, A / 2)


def solid_round(D: float, label: str | None = None) -> Section:
    D = _pos("D", D)
    A = math.pi * D ** 2 / 4
    I = math.pi * D ** 4 / 64
    return Section("rod", label or f"{D:g} dia bar", {"D": D}, A, I, I, 2 * I / D, 2 * I / D, D ** 3 / 6, D ** 3 / 6,
                   2 * I, 0.0, 0.0, D / 2, {}, False, 0.9 * A, 0.9 * A)


# ---------------------------------------------------------------- rectangle helpers (rounded corners)
def _spandrel(r: float):
    """Corner spandrel (r x r square minus quarter circle): area, centroid offset from the outer edges, own I."""
    if r <= 0:
        return 0.0, 0.0, 0.0
    As = r * r * (1 - math.pi / 4)
    xbar = r * (5.0 / 6.0 - math.pi / 4) / (1 - math.pi / 4)
    Aq = math.pi * r * r / 4
    cq = 4 * r / (3 * math.pi)
    Iq_own = math.pi * r ** 4 / 16 - Aq * cq ** 2
    Iq_edge = Iq_own + Aq * (r - cq) ** 2           # quarter circle about the outer edge line
    Isp_edge = r ** 4 / 3 - Iq_edge
    Isp_own = Isp_edge - As * xbar ** 2
    return As, xbar, Isp_own


def _rounded_rect(b: float, h: float, r: float):
    """Area, I about the axis parallel to b (bending over depth h), and plastic modulus about that axis."""
    As, xbar, Isp = _spandrel(r)
    A = b * h - 4 * As
    I = b * h ** 3 / 12 - 4 * (Isp + As * (h / 2 - xbar) ** 2)
    Q_half = b * (h / 2) ** 2 / 2 - 2 * As * (h / 2 - xbar)
    return A, I, 2 * Q_half


def rect_tube(B: float, H: float, t: float, r_out: float | None = None, t_factor: float = 0.95,
              label: str | None = None) -> Section:
    """Rectangular / square tube: B wide (local z), H deep (local y)."""
    B, H, t = _pos("B", B), _pos("H", H), _pos("t", t)
    td = t * t_factor
    ro = 2 * td if r_out is None else float(r_out)
    if ro < td:
        ro = td
    ri = max(ro - td, 0.0)
    if 2 * td >= min(B, H) or 2 * ro > min(B, H):
        raise InputError("rectangular tube wall or corner radius too large for its size")
    Ao, Izo, Zzo = _rounded_rect(B, H, ro)
    Ai, Izi, Zzi = _rounded_rect(B - 2 * td, H - 2 * td, ri)
    _, Iyo, Zyo = _rounded_rect(H, B, ro)
    _, Iyi, Zyi = _rounded_rect(H - 2 * td, B - 2 * td, ri)
    A = Ao - Ai
    Iz, Iy = Izo - Izi, Iyo - Iyi
    Zz, Zy = Zzo - Zzi, Zyo - Zyi
    rm = ro - td / 2
    Am = (B - td) * (H - td) - (4 - math.pi) * rm ** 2
    pm = 2 * (B - td) + 2 * (H - td) - (8 - 2 * math.pi) * rm
    J = 4 * Am ** 2 * td / pm                                   # Bredt
    C = 2 * (B - td) * (H - td) * td - 4.5 * (4 - math.pi) * td ** 3   # AISC 370 G8 user note
    b_flat = B - 2 * td - 2 * ri                                # AISC 370 B4.1b(c)
    h_flat = H - 2 * td - 2 * ri
    el = {"b_t": b_flat / td, "h_t": h_flat / td, "b_flat": b_flat, "h_flat": h_flat, "r_in": ri, "r_out": ro}
    return Section("rect", label or f"{H:g} x {B:g} x {t:g}", {"B": B, "H": H, "t_nom": t, "t_factor": t_factor, "r_out": ro},
                   A, Iz, Iy, 2 * Iz / H, 2 * Iy / B, Zz, Zy, J, C, 0.0, td, el, True, 2 * h_flat * td, 2 * b_flat * td)


def flat_bar(b: float, t: float, label: str | None = None) -> Section:
    """Flat bar / plate b wide (local z) and t thick (local y): strong axis bends about y."""
    b, t = _pos("b", b), _pos("t", t)
    A = b * t
    Iz = b * t ** 3 / 12
    Iy = t * b ** 3 / 12
    ha, hb = max(b, t) / 2, min(b, t) / 2     # Roark 7th Table 10.7 case 4 (half sides a >= b)
    J = ha * hb ** 3 * (16.0 / 3.0 - 3.36 * hb / ha * (1 - hb ** 4 / (12 * ha ** 4)))
    return Section("flat", label or f"{b:g} x {t:g} flat", {"b": b, "t": t}, A, Iz, Iy, 2 * Iz / t, 2 * Iy / b,
                   b * t ** 2 / 4, t * b ** 2 / 4, J, 0.0, 0.0, t, {"b_t": b / t}, False, A / 1.2, A / 1.2)


def solid_square(a: float, label: str | None = None) -> Section:
    a = _pos("a", a)
    s = flat_bar(a, a, label or f"{a:g} sq bar")
    s.shape = "bar"
    return s


def angle(b: float, d: float, t: float, label: str | None = None) -> Section:
    """Angle with legs b (horizontal, along z) and d (vertical, along y), thickness t, sharp corners.

    Iz / Iy are about the geometric axes through the centroid; elements['r_principal_min'] is the minor
    principal radius of gyration (governs flexural buckling of a single angle).
    """
    b, d, t = _pos("b", b), _pos("d", d), _pos("t", t)
    A1, A2 = d * t, (b - t) * t                     # vertical leg (full), horizontal leg (less overlap)
    A = A1 + A2
    zc = (A1 * t / 2 + A2 * (t + (b - t) / 2)) / A
    yc = (A1 * d / 2 + A2 * t / 2) / A
    Iz = t * d ** 3 / 12 + A1 * (d / 2 - yc) ** 2 + (b - t) * t ** 3 / 12 + A2 * (t / 2 - yc) ** 2
    Iy = d * t ** 3 / 12 + A1 * (t / 2 - zc) ** 2 + t * (b - t) ** 3 / 12 + A2 * (t + (b - t) / 2 - zc) ** 2
    Iyz = A1 * (t / 2 - zc) * (d / 2 - yc) + A2 * (t + (b - t) / 2 - zc) * (t / 2 - yc)
    avg, rad = (Iz + Iy) / 2, math.sqrt(((Iz - Iy) / 2) ** 2 + Iyz ** 2)
    Imin = avg - rad
    J = (b + d - t) * t ** 3 / 3
    Sz = Iz / max(yc, d - yc)
    Sy = Iy / max(zc, b - zc)
    el = {"b_t": max(b, d) / t, "r_principal_min": math.sqrt(Imin / A), "I_principal_min": Imin,
          "I_principal_max": avg + rad, "yc": yc, "zc": zc}
    # plastic moduli: conservative 1.5 S (angles are not checked for plastic moment here)
    return Section("angle", label or f"L{d:g} x {b:g} x {t:g}", {"b": b, "d": d, "t": t}, A, Iz, Iy, Sz, Sy,
                   1.5 * Sz, 1.5 * Sy, J, 0.0, 0.0, t, el, False, d * t, b * t)


def channel(d: float, bf: float, tf: float, tw: float, label: str | None = None) -> Section:
    """Channel, depth d (along y), flange width bf (along z), sharp corners. Iy about the centroidal minor axis."""
    d, bf, tf, tw = _pos("d", d), _pos("bf", bf), _pos("tf", tf), _pos("tw", tw)
    hw = d - 2 * tf
    A = 2 * bf * tf + hw * tw
    Iz = bf * d ** 3 / 12 - (bf - tw) * hw ** 3 / 12
    xc = (2 * bf * tf * bf / 2 + hw * tw * tw / 2) / A
    Iy = 2 * (tf * bf ** 3 / 12 + bf * tf * (bf / 2 - xc) ** 2) + hw * tw ** 3 / 12 + hw * tw * (tw / 2 - xc) ** 2
    Zz = bf * tf * (d - tf) + tw * hw ** 2 / 4
    J = (2 * bf * tf ** 3 + (d - tf) * tw ** 3) / 3
    return Section("channel", label or f"C{d:g} x {bf:g}", {"d": d, "bf": bf, "tf": tf, "tw": tw}, A, Iz, Iy,
                   2 * Iz / d, Iy / max(xc, bf - xc), Zz, 1.5 * Iy / max(xc, bf - xc), J, 0.0, 0.0, min(tf, tw),
                   {"bf_tf": bf / tf, "h_tw": hw / tw}, False, d * tw, 2 * bf * tf * 5 / 6)


def ishape(d: float, bf: float, tf: float, tw: float, label: str | None = None) -> Section:
    """Doubly symmetric I-shape (welded or rolled, fillets ignored)."""
    d, bf, tf, tw = _pos("d", d), _pos("bf", bf), _pos("tf", tf), _pos("tw", tw)
    hw = d - 2 * tf
    A = 2 * bf * tf + hw * tw
    Iz = bf * d ** 3 / 12 - (bf - tw) * hw ** 3 / 12
    Iy = 2 * tf * bf ** 3 / 12 + hw * tw ** 3 / 12
    Zz = bf * tf * (d - tf) + tw * hw ** 2 / 4
    Zy = 2 * tf * bf ** 2 / 4 + hw * tw ** 2 / 4
    J = (2 * bf * tf ** 3 + (d - tf) * tw ** 3) / 3
    h0 = d - tf
    Cw = Iy * h0 ** 2 / 4
    return Section("ishape", label or f"I{d:g} x {bf:g}", {"d": d, "bf": bf, "tf": tf, "tw": tw}, A, Iz, Iy, 2 * Iz / d,
                   2 * Iy / bf, Zz, Zy, J, 0.0, Cw, min(tf, tw), {"bf_2tf": bf / (2 * tf), "h_tw": hw / tw, "h0": h0},
                   False, d * tw, 2 * bf * tf * 5 / 6)


SHAPES = {
    "round": (round_tube, ("D", "t")),
    "rect": (rect_tube, ("B", "H", "t")),
    "square": (lambda b, t, **k: rect_tube(b, b, t, **k), ("b", "t")),
    "rod": (solid_round, ("D",)),
    "bar": (solid_square, ("a",)),
    "flat": (flat_bar, ("b", "t")),
    "angle": (angle, ("b", "d", "t")),
    "channel": (channel, ("d", "bf", "tf", "tw")),
    "ishape": (ishape, ("d", "bf", "tf", "tw")),
}


def from_spec(spec) -> Section:
    """Build a section from a dict like {"shape": "rect", "B": 2, "H": 3, "t": 0.12} (optional t_factor, r_out)."""
    if isinstance(spec, Section):
        return spec
    if not isinstance(spec, dict) or "shape" not in spec:
        raise InputError(f"section must be a dict with 'shape' (one of {sorted(SHAPES)}), got {spec!r}")
    shape = spec["shape"]
    if shape not in SHAPES:
        raise InputError(f"unknown section shape '{shape}'; known: {sorted(SHAPES)}")
    fn, req = SHAPES[shape]
    missing = [k for k in req if k not in spec]
    if missing:
        raise InputError(f"section '{shape}' needs {missing}")
    args = [spec[k] for k in req]
    kw = {k: spec[k] for k in ("t_factor", "r_out", "label") if k in spec}
    if shape in ("rod", "bar", "flat", "angle", "channel", "ishape"):
        kw.pop("t_factor", None)
        kw.pop("r_out", None)
    return fn(*args, **kw)
