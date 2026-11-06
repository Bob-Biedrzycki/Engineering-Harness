"""Closed-form beam, column and plate formulas (hand-check library).

Use these for a single member whose supports are clearly one of the standard cases, and to cross-check the frame
solver. Every function returns a dict: reactions, M_max (lb-in), V_max (lb), defl_max (in, positive down) and where.
Units: lb, in, psi.

Sources: AISC Steel Construction Manual, 16th ed., Table 3-23 (Shears, Moments and Deflections); Roark's Formulas
for Stress and Strain, 7th ed. (Young & Budynas), Table 8.1 (beams), Table 11.4 (rectangular plates, nu = 0.3).
"""
from __future__ import annotations

import math

from .core import InputError


def _chk(E, I, L):
    if E <= 0 or I <= 0 or L <= 0:
        raise InputError("E, I and L must be > 0")


# ---------------------------------------------------------------- simply supported
def ss_point(P, a, L, E, I):
    """Simple span, point load P at distance a from the left support."""
    _chk(E, I, L)
    if not (0 <= a <= L):
        raise InputError("load position a must be within the span")
    b = L - a
    R1, R2 = P * b / L, P * a / L
    M = P * a * b / L
    big, small = max(a, b), min(a, b)
    if small == 0:
        dmax, x = 0.0, a
    else:
        x = math.sqrt((L * L - small * small) / 3)          # from the end nearer the larger segment's support
        dmax = P * small * (L * L - small * small) ** 1.5 / (9 * math.sqrt(3) * E * I * L)
    d_load = P * a * a * b * b / (3 * E * I * L)
    return {"R1": R1, "R2": R2, "M_max": M, "V_max": max(R1, R2), "defl_max": dmax, "defl_at_load": d_load,
            "case": "AISC Manual Table 3-23 case 8 / Roark Table 8.1 1e"}


def ss_udl(w, L, E, I):
    _chk(E, I, L)
    return {"R1": w * L / 2, "R2": w * L / 2, "M_max": w * L * L / 8, "V_max": w * L / 2,
            "defl_max": 5 * w * L ** 4 / (384 * E * I), "case": "AISC Manual Table 3-23 case 1"}


# ---------------------------------------------------------------- cantilever
def cantilever_point(P, a, L, E, I):
    """Cantilever fixed at x = 0, point load P at distance a from the fixed end; deflection at the free tip."""
    _chk(E, I, L)
    if not (0 <= a <= L):
        raise InputError("load position a must be within the span")
    return {"R": P, "M_fixed": P * a, "M_max": P * a, "V_max": P,
            "defl_max": P * a * a * (3 * L - a) / (6 * E * I), "case": "AISC Manual Table 3-23 cases 21/22"}


def cantilever_udl(w, L, E, I):
    _chk(E, I, L)
    return {"R": w * L, "M_max": w * L * L / 2, "V_max": w * L, "defl_max": w * L ** 4 / (8 * E * I),
            "case": "AISC Manual Table 3-23 case 19"}


# ---------------------------------------------------------------- fixed both ends
def fixed_point(P, a, L, E, I):
    _chk(E, I, L)
    b = L - a
    M1, M2 = P * a * b * b / L ** 2, P * a * a * b / L ** 2
    Mload = 2 * P * a * a * b * b / L ** 3
    R1 = P * b * b * (3 * a + b) / L ** 3
    R2 = P * a * a * (a + 3 * b) / L ** 3
    d_load = P * a ** 3 * b ** 3 / (3 * E * I * L ** 3)
    if a >= b:
        x = 2 * a * L / (3 * a + b)
        dmax = 2 * P * a ** 3 * b * b / (3 * E * I * (3 * a + b) ** 2)
    else:
        x = L - 2 * b * L / (3 * b + a)
        dmax = 2 * P * b ** 3 * a * a / (3 * E * I * (3 * b + a) ** 2)
    return {"R1": R1, "R2": R2, "M1": M1, "M2": M2, "M_load": Mload, "M_max": max(M1, M2, Mload),
            "V_max": max(R1, R2), "defl_max": dmax, "defl_at_load": d_load, "case": "AISC Manual Table 3-23 case 18"}


def fixed_udl(w, L, E, I):
    _chk(E, I, L)
    return {"R1": w * L / 2, "R2": w * L / 2, "M_end": w * L * L / 12, "M_mid": w * L * L / 24,
            "M_max": w * L * L / 12, "V_max": w * L / 2, "defl_max": w * L ** 4 / (384 * E * I),
            "case": "AISC Manual Table 3-23 case 15"}


# ---------------------------------------------------------------- propped cantilever (fixed at x = 0, pinned at L)
def propped_udl(w, L, E, I):
    _chk(E, I, L)
    return {"R_fixed": 5 * w * L / 8, "R_pin": 3 * w * L / 8, "M_fixed": w * L * L / 8, "M_span": 9 * w * L * L / 128,
            "M_max": w * L * L / 8, "V_max": 5 * w * L / 8,
            "defl_max": w * L ** 4 / (185 * E * I), "case": "AISC Manual Table 3-23 case 12"}


def propped_point_center(P, L, E, I):
    _chk(E, I, L)
    return {"R_fixed": 11 * P / 16, "R_pin": 5 * P / 16, "M_fixed": 3 * P * L / 16, "M_load": 5 * P * L / 32,
            "M_max": 3 * P * L / 16, "V_max": 11 * P / 16, "defl_max": P * L ** 3 / (48 * math.sqrt(5) * E * I),
            "case": "AISC Manual Table 3-23 case 13"}


# ---------------------------------------------------------------- overhang (beam on two supports, one overhang)
def overhang_tip_point(P, L, a, E, I):
    """Span L between supports, overhang a past the right support, point P at the overhang tip."""
    _chk(E, I, L)
    return {"R1": -P * a / L, "R2": P * (L + a) / L, "M_max": P * a, "V_max": P,
            "defl_tip": P * a * a * (L + a) / (3 * E * I),
            "defl_span_up": P * a * L * L / (9 * math.sqrt(3) * E * I), "case": "AISC Manual Table 3-23 case 26"}


# ---------------------------------------------------------------- columns
K_FACTORS = {
    "fixed-fixed": (0.5, 0.65), "fixed-pinned": (0.7, 0.80), "pinned-pinned": (1.0, 1.0),
    "fixed-guided": (1.0, 1.2), "fixed-free": (2.0, 2.1), "pinned-guided": (2.0, 2.0),
}
"""(theoretical K, AISC recommended design K) per AISC 360 Commentary Table C-A-7.1."""


def euler(E, I, KL):
    if KL <= 0:
        raise InputError("effective length must be > 0")
    return math.pi ** 2 * E * I / KL ** 2


# ---------------------------------------------------------------- rectangular plates (Roark Table 11.4, nu = 0.3)
_SS_TABLE = [(1.0, 0.2874, 0.0444), (1.2, 0.3762, 0.0616), (1.4, 0.4530, 0.0770), (1.6, 0.5172, 0.0906),
             (1.8, 0.5688, 0.1017), (2.0, 0.6102, 0.1110), (3.0, 0.7134, 0.1335), (4.0, 0.7410, 0.1400),
             (5.0, 0.7476, 0.1417), (1e9, 0.7500, 0.1421)]
_FX_TABLE = [(1.0, 0.3078, 0.0138), (1.2, 0.3834, 0.0188), (1.4, 0.4356, 0.0226), (1.6, 0.4680, 0.0251),
             (1.8, 0.4872, 0.0267), (2.0, 0.4974, 0.0277), (1e9, 0.5000, 0.0284)]


def _interp(table, r):
    for (r0, b0, a0), (r1, b1, a1) in zip(table, table[1:]):
        if r0 <= r <= r1:
            f = (r - r0) / (r1 - r0)
            return b0 + f * (b1 - b0), a0 + f * (a1 - a0)
    return table[-1][1], table[-1][2]


def plate_uniform(q, a, b, t, E, edges="simple"):
    """Rectangular plate a x b (a >= b), thickness t, uniform pressure q (psi).

    edges 'simple': all edges simply supported (Roark 11.4 case 1a): sigma_max = beta q b^2 / t^2 at the centre.
    edges 'fixed': all edges fixed (case 8a): sigma_max = beta1 q b^2 / t^2 at the centre of the long edges.
    Deflection y_max = alpha q b^4 / (E t^3). Small deflection theory: valid while y_max < about t / 2."""
    if a < b:
        a, b = b, a
    table = _SS_TABLE if edges == "simple" else _FX_TABLE if edges == "fixed" else None
    if table is None:
        raise InputError("edges must be 'simple' or 'fixed'")
    beta, alpha = _interp(table, a / b)
    s = beta * q * b * b / (t * t)
    y = alpha * q * b ** 4 / (E * t ** 3)
    out = {"sigma_max": s, "defl_max": y, "beta": beta, "alpha": alpha,
           "case": f"Roark 7th Table 11.4 case {'1a' if edges == 'simple' else '8a'} (nu 0.3)"}
    if y > 0.5 * t:
        out["note"] = "deflection exceeds t/2: membrane action; small-deflection result is conservative for stress"
    return out
