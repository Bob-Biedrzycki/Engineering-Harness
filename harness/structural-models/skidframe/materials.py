"""Material library: structural grades, weld fillers, bolts, and stainless properties at temperature.

Units: psi, lb/in3, in/in/F.

Sources (each value carries its own `source`):
- AISC 370-21 (Specification for Structural Stainless Steel Buildings, free from AISC):
  E = 28,000 ksi and G = 10,800 ksi for austenitic, 29,000 / 11,200 ksi for duplex (Table A3 notes, E3, B4.3);
  density 500 lb/ft3 and thermal expansion 9.1e-6 /F for austenitic (Commentary table of physical properties);
  minimum Fy / Fu for ASTM A554 tube (Commentary Table C-A3.3) and A240 plate (Table C-A3.2);
  retention factors kE, ky, ku at temperature (Appendix 4, Tables A-4.2.1 for 304/304L and A-4.2.2 for 316/316L).
- AISC 360-22 and ASTM A500-21 / A36 / A992 for carbon steel (E 29,000 ksi, G 11,200 ksi).
- AWS A5.4 minimum tensile strength of the deposited weld metal: E308L 75 ksi, E316L 70 ksi (manufacturer
  data sheets quoting A5.4); AWS A5.1 / A5.18 E70 70 ksi.

The temperature factors in AISC 370 Appendix 4 were written for fire design. They are used here as the best
published retention data for a frame member that sits warm (under a hot tank); the model says so when it uses them.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from .core import InputError

STAINLESS_FAMILIES = ("austenitic", "duplex")


@dataclass(frozen=True)
class Material:
    key: str
    name: str
    family: str            # austenitic | duplex | carbon
    Fy: float              # psi, specified minimum yield
    Fu: float              # psi, specified minimum tensile
    E: float               # psi
    G: float               # psi
    density: float         # lb/in3
    alpha: float           # in/in/F
    spec: str              # design specification the member checks use
    source: str
    temperature_F: float = 68.0

    @property
    def stainless(self) -> bool:
        return self.family in STAINLESS_FAMILIES


_SS_E, _SS_G = 28.0e6, 10.8e6
_SS_RHO = 500.0 / 1728.0        # lb/in3
_SS_ALPHA = 9.1e-6
_CS_E, _CS_G, _CS_RHO, _CS_ALPHA = 29.0e6, 11.2e6, 490.0 / 1728.0, 6.5e-6
_A370 = "AISC 370-21 Comm. Table C-A3.3 (A554) / C-A3.2 (A240); E, G per AISC 370-21 E3, E4"

MATERIALS = {
    # --- austenitic stainless tube (ASTM A554 mechanical tubing, used as HSS per AISC 370 Table A3.1)
    "A554-304": Material("A554-304", "ASTM A554 MT304 tube", "austenitic", 30e3, 75e3, _SS_E, _SS_G, _SS_RHO, _SS_ALPHA, "AISC370", _A370),
    "A554-316": Material("A554-316", "ASTM A554 MT316 tube", "austenitic", 30e3, 75e3, _SS_E, _SS_G, _SS_RHO, _SS_ALPHA, "AISC370", _A370),
    "A554-304L": Material("A554-304L", "ASTM A554 MT304L tube", "austenitic", 25e3, 70e3, _SS_E, _SS_G, _SS_RHO, _SS_ALPHA, "AISC370", _A370),
    "A554-316L": Material("A554-316L", "ASTM A554 MT316L tube", "austenitic", 25e3, 70e3, _SS_E, _SS_G, _SS_RHO, _SS_ALPHA, "AISC370", _A370),
    # --- sanitary process tube (A270) has the same minimums as the A554 L grades / plain grades
    "A270-316L": Material("A270-316L", "ASTM A270 316L sanitary tube", "austenitic", 25e3, 70e3, _SS_E, _SS_G, _SS_RHO, _SS_ALPHA, "AISC370",
                          "ASSUMPTION: A270 is not listed in AISC 370 Table A3.1; 316L plate minimums 25 / 70 ksi "
                          "(AISC 370 Comm. Table C-A3.2) are used for process tube carried as a member"),
    # --- plate and bar
    "A240-304": Material("A240-304", "ASTM A240 304 plate", "austenitic", 30e3, 75e3, _SS_E, _SS_G, _SS_RHO, _SS_ALPHA, "AISC370", _A370),
    "A240-304L": Material("A240-304L", "ASTM A240 304L plate", "austenitic", 25e3, 70e3, _SS_E, _SS_G, _SS_RHO, _SS_ALPHA, "AISC370", _A370),
    "A240-316": Material("A240-316", "ASTM A240 316 plate", "austenitic", 30e3, 75e3, _SS_E, _SS_G, _SS_RHO, _SS_ALPHA, "AISC370", _A370),
    "A240-316L": Material("A240-316L", "ASTM A240 316L plate", "austenitic", 25e3, 70e3, _SS_E, _SS_G, _SS_RHO, _SS_ALPHA, "AISC370", _A370),
    "A276-304": Material("A276-304", "ASTM A276 304 bar (annealed)", "austenitic", 30e3, 75e3, _SS_E, _SS_G, _SS_RHO, _SS_ALPHA, "AISC370",
                         "AISC 370-21 Comm. Table C-A3.4 (A276 annealed, condition A)"),
    "A240-2205": Material("A240-2205", "ASTM A240 2205 duplex plate", "duplex", 65e3, 95e3, 29.0e6, 11.2e6, 485.0 / 1728.0, 7.4e-6, "AISC370", _A370),
    # --- carbon steel (painted or galvanized frames; not for washdown zones)
    "A500C-rect": Material("A500C-rect", "ASTM A500 Gr C rectangular HSS", "carbon", 50e3, 62e3, _CS_E, _CS_G, _CS_RHO, _CS_ALPHA, "AISC360",
                           "ASTM A500-21 Gr C shaped (rect/square) Fy 50 ksi, Fu 62 ksi"),
    "A500C-round": Material("A500C-round", "ASTM A500 Gr C round HSS", "carbon", 46e3, 62e3, _CS_E, _CS_G, _CS_RHO, _CS_ALPHA, "AISC360",
                            "ASTM A500-21 Gr C round Fy 46 ksi, Fu 62 ksi"),
    "A36": Material("A36", "ASTM A36 plate / shapes", "carbon", 36e3, 58e3, _CS_E, _CS_G, _CS_RHO, _CS_ALPHA, "AISC360", "ASTM A36: Fy 36 ksi, Fu 58 ksi"),
    "A992": Material("A992", "ASTM A992 W-shape", "carbon", 50e3, 65e3, _CS_E, _CS_G, _CS_RHO, _CS_ALPHA, "AISC360", "ASTM A992: Fy 50 ksi, Fu 65 ksi"),
}

# Filler metal classification strength FEXX, psi
FILLERS = {
    "E308L": (75e3, "AWS A5.4 E308L-XX deposited metal min. tensile 75 ksi (ER308L wire per A5.9 is matched to it)"),
    "E316L": (70e3, "AWS A5.4 E316L-XX deposited metal min. tensile 70 ksi"),
    "E309L": (75e3, "AWS A5.4 E309L-XX min. tensile 75 ksi (stainless to carbon)"),
    "E2209": (100e3, "AWS A5.4 E2209 min. tensile 100 ksi (duplex)"),
    "E70": (70e3, "AWS A5.1 / A5.18 E70XX min. tensile 70 ksi (carbon steel)"),
}

# Bolt materials: Fu psi (nominal), with diameter range note. Values are the common ASTM minimums; confirm per order.
BOLTS = {
    "A193-B8-cl1": (75e3, "ASTM A193 B8 Class 1 (304, carbide solution treated): Fu 75 ksi"),
    "A193-B8M-cl1": (75e3, "ASTM A193 B8M Class 1 (316): Fu 75 ksi"),
    "F593-G1-CW": (100e3, "ASTM F593 Group 1 (304) condition CW, 1/4-5/8 in: Fu 100 ksi (85 ksi for 3/4-1-1/2 in)"),
    "F593-G2-CW": (100e3, "ASTM F593 Group 2 (316) condition CW, 1/4-5/8 in: Fu 100 ksi (85 ksi for 3/4-1-1/2 in)"),
    "A307": (60e3, "ASTM A307 Gr A: Fu 60 ksi (carbon)"),
    "F3125-A325": (120e3, "ASTM F3125 Gr A325: Fu 120 ksi (carbon, high strength)"),
    "F1554-36": (58e3, "ASTM F1554 Gr 36 anchor rod: Fu 58 ksi"),
}

# AISC 370-21 App. 4 retention factors: temperature F -> (kE, ky, ku)
_K_304 = [(68, 1.00, 1.00, 1.00), (200, 0.96, 0.80, 0.83), (400, 0.92, 0.65, 0.72), (600, 0.87, 0.59, 0.68),
          (750, 0.84, 0.55, 0.66), (800, 0.83, 0.54, 0.65), (1000, 0.78, 0.48, 0.58)]
_K_316 = [(68, 1.00, 1.00, 1.00), (200, 0.96, 0.87, 0.88), (400, 0.92, 0.72, 0.80), (600, 0.87, 0.66, 0.78),
          (750, 0.84, 0.62, 0.77), (800, 0.83, 0.61, 0.76), (1000, 0.78, 0.58, 0.71)]
_K_DUPLEX = [(68, 1.00, 1.00, 1.00), (200, 0.96, 0.84, 0.95), (400, 0.92, 0.75, 0.87), (600, 0.87, 0.67, 0.78),
             (750, 0.84, 0.58, 0.70), (800, 0.83, 0.54, 0.67), (1000, 0.78, 0.37, 0.54)]


def retention(material: Material, temperature_F: float):
    """(kE, ky, ku) at a temperature, linear between the AISC 370 App. 4 table rows. Carbon: 1.0 up to 200 F."""
    if material.family == "carbon":
        if temperature_F > 200:
            raise InputError("carbon steel at temperature above 200 F is outside this library; use AISC 360 App. 4")
        return 1.0, 1.0, 1.0
    if material.family == "duplex":
        table = _K_DUPLEX
    elif "316" in material.key:
        table = _K_316
    else:
        table = _K_304
    t = max(68.0, float(temperature_F))
    if t > table[-1][0]:
        raise InputError(f"temperature {temperature_F} F is above the {table[-1][0]} F limit of this library")
    for (t0, e0, y0, u0), (t1, e1, y1, u1) in zip(table, table[1:]):
        if t0 <= t <= t1:
            f = (t - t0) / (t1 - t0)
            return e0 + f * (e1 - e0), y0 + f * (y1 - y0), u0 + f * (u1 - u0)
    return table[0][1:]


def get(key: str, temperature_F: float | None = None) -> Material:
    """Material by key, optionally reduced to its properties at a service temperature."""
    if key not in MATERIALS:
        raise InputError(f"unknown material '{key}'; known: {', '.join(sorted(MATERIALS))}")
    m = MATERIALS[key]
    if temperature_F is None or temperature_F <= 100.0:
        return m
    kE, ky, ku = retention(m, temperature_F)
    return replace(m, Fy=m.Fy * ky, Fu=m.Fu * ku, E=m.E * kE, G=m.G * kE, temperature_F=float(temperature_F),
                   source=m.source + f"; reduced to {temperature_F:g} F by AISC 370-21 App. 4 kE={kE:.3f} ky={ky:.3f} ku={ku:.3f}")


def filler(key: str) -> float:
    if key not in FILLERS:
        raise InputError(f"unknown filler '{key}'; known: {', '.join(sorted(FILLERS))}")
    return FILLERS[key][0]


def bolt(key: str) -> float:
    if key not in BOLTS:
        raise InputError(f"unknown bolt material '{key}'; known: {', '.join(sorted(BOLTS))}")
    return BOLTS[key][0]
