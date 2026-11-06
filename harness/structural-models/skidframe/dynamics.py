"""Vibration and fatigue: natural frequency, pump / motor resonance and unbalance, fatigue of welded details.

Models: natural_frequency, pump_vibration, fatigue. Units: lb, in, s, Hz, psi.
"""
from __future__ import annotations

import math

from .core import G_IN_S2, Calc, InputError, need

REF_FAT = "ANSI/AISC 370-21 Appendix 3 (fatigue), Eq. A-3-1, Table A-3.1 (same constants as AISC 360-22 App. 3)"
REF_ISO = "ISO 21940-11:2016 (formerly ISO 1940-1), balance quality grades; G6.3 for pump impellers and motor rotors"
REF_ACI351 = "ACI 351.3R-18, Foundations for Dynamic Equipment: keep natural frequencies at least 20 % away from operating frequencies"

# AISC 370-21 Table A-3.1: category -> (Cf, F_TH ksi)
FATIGUE = {"A": (25.0, 24.0), "B": (12.0, 16.0), "B'": (6.1, 12.0), "C": (4.4, 10.0), "D": (2.2, 7.0),
           "E": (1.1, 4.5), "E'": (0.39, 2.6)}
FATIGUE_GUIDE = {
    "A": "plain base metal away from welds (cut edges smooth)",
    "B": "base metal at continuous longitudinal fillet welds (e.g. a tube to a flat bar along its length)",
    "C": "base metal at the toe of transverse fillet welds of short attachments (< 2 in along the stress); "
         "drilled holes with pretensioned bolts",
    "D": "base metal at attachments 2 to 4 in long (or 12 t) in the stress direction; open holes",
    "E": "base metal at fillet-welded attachments longer than 4 in, cover plates, end of longitudinal welds",
    "E'": "the lowest welded category: long fillet-welded attachments on thicker parts and several HSS "
          "connection details",
}
GUIDE_NOTE = ("category descriptions here are short summaries: choose the category from the detail drawings of "
              "AISC 370 Table A-3.1 (HSS joint details have their own rows)")


def _sdof_from_static(delta_in: float) -> float:
    """f = (1/2 pi) sqrt(g / delta) for a mass on a spring whose static deflection under its own weight is delta."""
    if delta_in <= 0:
        raise InputError("static deflection must be > 0")
    return math.sqrt(G_IN_S2 / delta_in) / (2 * math.pi)


def natural_frequency(inputs: dict) -> Calc:
    """WHEN: a pump, motor, agitator or panel on a frame member, bracket or leg could resonate; quick first natural
    frequency without a full modal model (frame_check with 'modal' gives the full answer).

    inputs: case 'static_deflection' (delta: static deflection under the supported weight, in) or a beam case:
    'ss_mass' / 'cantilever_mass' / 'fixed_mass' (mass at mid-span / tip / centre) with E, I, L, W (lb, carried
    weight), w (lb/in, member self weight, optional), or 'ss_beam' / 'cantilever_beam' (distributed only)."""
    c = Calc("natural_frequency", "First natural frequency")
    c.inputs = inputs
    case = inputs.get("case", "static_deflection")
    if case == "static_deflection":
        f = _sdof_from_static(need(inputs, "delta", lo=0.0, strict_lo=True))
        c.method = "SDOF: f = (1 / 2 pi) sqrt(g / delta_static) = 3.13 / sqrt(delta in) Hz"
    else:
        E, I, L = need(inputs, "E", lo=0.0, strict_lo=True), need(inputs, "I", lo=0.0, strict_lo=True), need(inputs, "L", lo=0.0, strict_lo=True)
        w = float(inputs.get("w", 0.0))
        if case in ("ss_beam", "cantilever_beam"):
            if w <= 0:
                raise InputError("distributed-mass beam needs w (lb/in)")
            m = w / G_IN_S2
            lam = math.pi ** 2 if case == "ss_beam" else 1.8751 ** 2
            f = lam / (2 * math.pi) * math.sqrt(E * I / (m * L ** 4))
            c.method = "Euler-Bernoulli beam, first mode: (beta L)^2 = pi^2 (simple) or 3.516 (cantilever)"
        else:
            W = need(inputs, "W", lo=0.0)
            k, frac = {"ss_mass": (48 * E * I / L ** 3, 0.4857), "cantilever_mass": (3 * E * I / L ** 3, 0.2357),
                       "fixed_mass": (192 * E * I / L ** 3, 0.3714)}.get(case, (None, None))
            if k is None:
                raise InputError("case must be static_deflection, ss_mass, cantilever_mass, fixed_mass, ss_beam or "
                                 "cantilever_beam")
            M = (W + frac * w * L) / G_IN_S2
            f = math.sqrt(k / M) / (2 * math.pi)
            c.r("stiffness at the mass", k, "lb/in")
            c.method = ("Rayleigh: k at the mass, effective mass = W + (fraction) x member weight (0.4857 simple, "
                        "0.2357 cantilever, 0.3714 fixed-fixed)")
    c.r("first natural frequency", f, "Hz")
    c.r("in rpm", f * 60, "cpm")
    c.references.append("Blevins, Formulas for Natural Frequency and Mode Shape (1979), Tables 8-1, 8-2")
    return c


def pump_vibration(inputs: dict) -> Calc:
    """WHEN: a pump or motor sits on the skid frame. Checks frequency separation of the mount from running speed,
    2x running speed and vane pass, the unbalance force, and the forced response amplification.

    inputs: rpm, vanes (impeller vane count), f_natural (Hz, from natural_frequency or frame_check modal) or
    k (lb/in) with W (lb, the vibrating weight), rotor_weight (lb), G (balance grade mm/s, default 6.3),
    damping (ratio, default 0.02), separation (fraction, default 0.20)."""
    c = Calc("pump_vibration", "Pump / motor resonance and unbalance")
    c.inputs = inputs
    rpm = need(inputs, "rpm", lo=0.0, strict_lo=True)
    fr = rpm / 60
    if "f_natural" in inputs:
        fn = need(inputs, "f_natural", lo=0.0, strict_lo=True)
    else:
        k, W = need(inputs, "k", lo=0.0, strict_lo=True), need(inputs, "W", lo=0.0, strict_lo=True)
        fn = math.sqrt(k * G_IN_S2 / W) / (2 * math.pi)
    sep = float(inputs.get("separation") or c.default(inputs, "separation", 0.20, "20 % margin (ACI 351.3R practice)"))
    zeta = float(inputs.get("damping") or c.default(inputs, "damping", 0.02, "2 % damping, welded steel frame"))
    excit = [("1x running speed", fr), ("2x running speed (misalignment)", 2 * fr)]
    if inputs.get("vanes"):
        excit.append(("vane pass", fr * int(inputs["vanes"])))
    rows = []
    for nm, fe in excit:
        r = fn / fe
        ok = r <= 1 - sep or r >= 1 + sep
        rows.append([nm, round(fe, 2), round(r, 3), "OK" if ok else "TOO CLOSE"])
        c.check(f"separation from {nm}", ok, f"f_n / f = {r:.3f}; keep outside {1 - sep:.2f}..{1 + sep:.2f}",
                "ACI 351.3R-18 / HI 9.6.8 practice")
    c.table("excitation frequencies", ["source", "Hz", "f_n / f", "result"], rows)
    c.r("natural frequency", fn, "Hz")
    c.r("running speed", fr, "Hz")
    if inputs.get("rotor_weight"):
        G = float(inputs.get("G") or c.default(inputs, "G", 6.3, "balance grade G6.3 (ISO 21940-11, pumps)"))
        w = 2 * math.pi * fr
        e_in = (G / 1000.0 / w) / 0.0254                       # G = e * omega in mm/s -> e in inches
        Fu = float(inputs["rotor_weight"]) / G_IN_S2 * e_in * w * w
        r = fr / fn
        daf = 1 / math.sqrt((1 - r * r) ** 2 + (2 * zeta * r) ** 2)
        c.r("permissible unbalance eccentricity", e_in * 1e3, "mil")
        c.r("unbalance force amplitude", Fu, "lb")
        c.r("dynamic amplification at running speed", daf, "")
        c.r("amplified dynamic force", Fu * daf, "lb (add to the static case as an alternating load)")
    c.references += [REF_ACI351, REF_ISO, "Hydraulic Institute ANSI/HI 9.6.8 (dynamics of pumping machinery)"]
    c.method = "Frequency separation; unbalance F = m e omega^2 with e from the balance grade; SDOF amplification."
    return c


def fatigue(inputs: dict) -> Calc:
    """WHEN: a member or weld sees more than 20,000 load cycles (AISC 370 App. 3.1): pump or agitator vibration,
    daily fill/drain of tanks over the design life, cyclic thermal stress at a hot line support.

    inputs: category (A, B, B', C, D, E, E'), stress_range (psi, the full range at the detail), cycles
    (number over the design life) or cycles_per_day with years."""
    c = Calc("fatigue", "Fatigue of a welded or plain detail (AISC 370 Appendix 3)")
    c.inputs = inputs
    cat = inputs.get("category")
    if cat not in FATIGUE:
        raise InputError(f"category must be one of {sorted(FATIGUE)}; guide: {FATIGUE_GUIDE}")
    sr = need(inputs, "stress_range", lo=0.0) / 1000.0
    if "cycles" in inputs:
        n = need(inputs, "cycles", lo=1.0)
    else:
        n = need(inputs, "cycles_per_day", lo=0.0) * 365.0 * need(inputs, "years", lo=0.0)
    Cf, Fth = FATIGUE[cat]
    Fsr = max(1000.0 * (Cf / max(n, 1.0)) ** 0.333, Fth)
    c.r("cycles over the design life", n)
    c.r("allowable stress range FSR", Fsr * 1000, "psi")
    c.r("threshold FTH", Fth * 1000, "psi")
    if n <= 20000:
        c.check("fatigue evaluation required", True, f"{n:.0f} cycles <= 20,000: no fatigue check needed (App. 3.1)",
                "AISC 370 App. 3.1")
    c.ratio(f"stress range, category {cat}", sr, Fsr, f"{sr * 1000:.0f} psi vs FSR {Fsr * 1000:.0f} psi", "AISC 370 A-3-1")
    c.r("detail description", FATIGUE_GUIDE.get(cat, ""))
    c.warn(GUIDE_NOTE)
    c.warn("App. 3 applies up to 300 F and to mildly corrosive atmospheres: chloride washdown can shorten the life "
           "of stainless details; keep stress ranges below the threshold where possible")
    c.references.append(REF_FAT)
    c.method = "FSR = 1000 (Cf / nSR)^0.333 >= FTH (ksi)."
    return c
