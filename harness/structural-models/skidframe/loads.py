"""Load cases a process skid (CIP, hot water set, ...) sees, and the ASCE 7 combinations that put them together.

Load symbols (ASCE/SEI 7-22 Chapter 2):
  D   dead: frame steel, equipment dry weight, piping and valves empty, panel
  F   fluid: liquid in tanks, piping, pump, heat exchanger at the operating (or brimful) level. ASCE 7-22 2.3.1 /
      2.4.1: fluid loads with well-defined pressures and maximum heights take the same factor as D.
  L   live: maintenance personnel and tools on a platform or on the frame (only if people stand on the skid)
  E   seismic: Eh horizontal (ASCE 7 Chapter 13 or 15, see stability.seismic_force) and Ev = 0.2 SDS D vertical
  W   wind (outdoor skids only)
  T   self-straining (thermal growth of hot piping restrained by the frame)
Non-ASCE handling cases (checked on their own, never combined with E or W):
  LIFT       forklift or crane lift of the skid, normally EMPTY, times an impact factor (lifting.py)
  TRANSPORT  over-the-road accelerations 0.8 g forward, 0.5 g rearward, 0.5 g lateral, applied one at a time, plus
             the gravity load (49 CFR 393.102(a)(1), breaking-strength basis) (stability.transport)
  HYDRO      hydrotest or tanks brimful (overfill) with water SG 1.0: treated as F at its largest

Which combination governs a skid: usually D + F (tanks full) for members and feet; 0.6D + 0.7E (tanks empty or full,
check both) for anchors and overturning; LIFT for the base frame of an end-lifted skid; TRANSPORT for tie-downs.
"""
from __future__ import annotations

from .core import InputError

# ASCE/SEI 7-22 2.4.1 (ASD) and 2.3.1 (LRFD), with F carried at the D factor; E split as Eh and Ev.
_ASD = [
    ("ASD-1 D+F", {"D": 1.0, "F": 1.0}),
    ("ASD-2 D+F+L", {"D": 1.0, "F": 1.0, "L": 1.0}),
    ("ASD-5w D+F+0.6W", {"D": 1.0, "F": 1.0, "W": 0.6}),
    ("ASD-5e D+F+0.7Ev+0.7Eh", {"D": 1.0, "F": 1.0, "Ev": 0.7, "Eh": 0.7}),
    ("ASD-6w D+F+0.75L+0.45W", {"D": 1.0, "F": 1.0, "L": 0.75, "W": 0.45}),
    ("ASD-6e D+F+0.75L+0.525Ev+0.525Eh", {"D": 1.0, "F": 1.0, "L": 0.75, "Ev": 0.525, "Eh": 0.525}),
    ("ASD-7 0.6D+0.6W", {"D": 0.6, "W": 0.6}),
    ("ASD-8 0.6D-0.7Ev+0.7Eh", {"D": 0.6, "Ev": -0.7, "Eh": 0.7}),
    ("ASD-8F 0.6(D+F)-0.7Ev+0.7Eh", {"D": 0.6, "F": 0.6, "Ev": -0.7, "Eh": 0.7}),
    ("ASD-T D+F+T", {"D": 1.0, "F": 1.0, "T": 1.0}),
]
_LRFD = [
    ("LRFD-1 1.4(D+F)", {"D": 1.4, "F": 1.4}),
    ("LRFD-2 1.2(D+F)+1.6L", {"D": 1.2, "F": 1.2, "L": 1.6}),
    ("LRFD-3 1.2(D+F)+L+0.5W", {"D": 1.2, "F": 1.2, "L": 1.0, "W": 0.5}),
    ("LRFD-4 1.2(D+F)+1.0W+L", {"D": 1.2, "F": 1.2, "W": 1.0, "L": 1.0}),
    ("LRFD-6 1.2(D+F)+Ev+Eh+L", {"D": 1.2, "F": 1.2, "Ev": 1.0, "Eh": 1.0, "L": 1.0}),
    ("LRFD-5 0.9D+1.0W", {"D": 0.9, "W": 1.0}),
    ("LRFD-7 0.9D-Ev+Eh", {"D": 0.9, "Ev": -1.0, "Eh": 1.0}),
    ("LRFD-7F 0.9(D+F)-Ev+Eh", {"D": 0.9, "F": 0.9, "Ev": -1.0, "Eh": 1.0}),
    ("LRFD-T 1.2(D+F)+1.2T", {"D": 1.2, "F": 1.2, "T": 1.2}),
]


def combinations(method: str, present) -> dict:
    """Combinations that contain at least one case in `present` beyond D, with the absent cases dropped.

    present: iterable of case symbols defined in the model, e.g. {"D", "F", "Eh", "Ev"}. D must be present.
    Returns {name: {case: factor}}. Duplicates after dropping absent cases are removed."""
    present = set(present)
    if "D" not in present:
        raise InputError("combinations need a dead load case 'D'")
    if method not in ("ASD", "LRFD"):
        raise InputError("method must be ASD or LRFD")
    table = _ASD if method == "ASD" else _LRFD
    out, seen = {}, set()
    for name, fac in table:
        needs = [k for k in fac if k not in ("D", "F")]
        if any(k not in present for k in needs if k != "Ev"):
            continue
        f = {k: v for k, v in fac.items() if k in present}
        key = tuple(sorted(f.items()))
        if key in seen:
            continue
        seen.add(key)
        out[name] = f
    # cases outside ASCE 7 are never dropped (CPM-190 F-09): HYDRO with D, every other case on its own
    for case in sorted(present - ASCE_CASES):
        if case == "HYDRO":
            out["D+HYDRO (tanks brimful)"] = {"D": 1.0, "HYDRO": 1.0}
        else:
            out[f"{case} (on its own)"] = {case: 1.0}
    return out


ASCE_CASES = {"D", "F", "L", "Eh", "Ev", "W", "T"}


def ev_factor(SDS: float) -> float:
    """ASCE 7-22 12.4.2.2 vertical seismic load effect Ev = 0.2 SDS D: returns the factor on D."""
    return 0.2 * float(SDS)


def liquid_weight_gal(gallons: float, sg: float = 1.0) -> float:
    return gallons * 8.337 * sg


SKID_LOAD_CASES = [
    ("D", "Frame steel (automatic from the frame model), equipment dry weights, empty piping and valves, panel.",
     "always"),
    ("F", "Operating liquid in tanks, pump, heat exchanger and piping; SG of the process liquid (CIP caustic ~1.05; "
          "water 1.0, which is conservative for hot water).",
     "always; also check empty (F = 0) for uplift and overturning"),
    ("HYDRO", "Tanks brimful of water SG 1.0 (overfill or hydrotest).", "when tanks can be overfilled or are tested on the skid"),
    ("L", "Maintenance live load on platforms or steps on the skid (value from the customer spec or the governing "
          "building code's live-load table; OSHA 1910.22(b) requires the surface to carry its maximum intended load).",
     "only if people stand on the skid"),
    ("Eh/Ev", "Seismic: Fp per ASCE 7 Chapter 13 (component) or 15 (nonbuilding); Ev = 0.2 SDS D.",
     "when the site has seismic design requirements (site SDS is a customer input)"),
    ("W", "Wind on an outdoor skid (ASCE 7 Chapter 29 other structures).", "outdoor installations only"),
    ("T", "Restrained thermal growth of hot piping (CIP supply at 180-200 F; hot water, steam and "
          "condensate on a hot water set) anchored to the frame.",
     "when a hot line is anchored at two points on the frame without a loop or slide"),
    ("LIFT", "Empty skid on fork tines or slings x impact factor (1.5 to 2.0, ASSUMPTION).", "every skid that is lifted"),
    ("TRANSPORT", "Gravity plus 0.8 g fwd / 0.5 g rear / 0.5 g lateral, one at a time (49 CFR 393.102).",
     "every skid shipped by truck"),
    ("PUMP", "Pump unbalance (ISO 21940-11 grade G6.3) and nozzle loads; dynamic amplification.",
     "when a pump or motor is mounted on the frame"),
]
