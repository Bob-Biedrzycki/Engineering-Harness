"""Pass 2 verification: the items REVIEW-LOG pass 1 left open (O-1 to O-8)."""
from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from skidframe import connections as CN               # noqa: E402
from skidframe import design, local, stability, supports, lifting   # noqa: E402
from skidframe import frame as FR                     # noqa: E402
from skidframe import materials as MT                 # noqa: E402
from skidframe import members as MB                   # noqa: E402
from skidframe import sections as SC                  # noqa: E402
from skidframe.core import InputError                 # noqa: E402

E, FY = 28e6, 30e3
EF = E / FY


def rel(a, b):
    return abs(a - b) / max(abs(b), 1e-12)


class TestRoundCvExact(unittest.TestCase):
    """O-1: AISC 370 G4 / G8.1 read from the rendered pages."""

    def test_torsion_long_band_ii(self):
        # 3.0 x 0.120 (t 0.114): D/t 26.32, L 100 in: L/D 33.3 > 4.21 sqrt(26.32) = 21.6 -> CvL
        # (E/Fy)^0.67 = 97.71: 0.20 x 97.71 = 19.5 < 26.32 <= 182.7 -> G8-8:
        # 26.32^1.5 / 933.3 = 0.14468, sqrt 0.38037 x 0.77 = 0.29288 - 0.23 = 0.06288 x 0.61 = 0.03836 -> 0.9616
        cv, branch, _ = MB._round_cv_stainless(3.0 / 0.114, 100 / 3.0, E, FY, "torsion")
        self.assertEqual(branch, "CvL")
        self.assertLess(rel(cv, 0.9616), 2e-4)

    def test_shear_medium_band_ii(self):
        # 6 x 0.050 (t 0.0475): D/t 126.32, Lv 60: Lv/D 10 <= 4.21 sqrt(126.32) = 47.3 -> CvM
        # limits (0.32 x 933.3 / 3.1623)^0.8 = 38.0 and (4.65 ...)^0.8 = 323.6 -> G4-5:
        # y = 3.1623 x 126.32^1.25 (423.6) / 933.3 = 1.4352, sqrt 1.1980 x 0.47 = 0.5631 - 0.23 = 0.3331 x 0.61 -> 0.7968
        cv, branch, _ = MB._round_cv_stainless(6 / 0.0475, 10.0, E, FY, "shear")
        self.assertEqual(branch, "CvM")
        self.assertLess(rel(cv, 0.7968), 3e-4)

    def test_bands_continuous(self):
        # CORRECTED in pass 3 (CPM-190 F-01): the limit is lambda <= a ((E/Fy)/sqrt(L/D))^0.80 with a OUTSIDE the
        # power, so at a limit y = a^1.25: shear upper 1 - 0.61 (0.47 sqrt(6.834) - 0.23) = 0.391 = 2.67 / 6.834.
        # The printed bands meet; pass 2 read the coefficient inside the power and wrongly reported jumps.
        for kind in ("shear", "torsion"):
            a, b = (0.32, 4.65) if kind == "shear" else (0.26, 3.77)
            for LD in (4.0, 9.0, 25.0):
                for lim in (a, b):
                    lam = lim * (EF / math.sqrt(LD)) ** 0.8
                    if LD > 4.21 * math.sqrt(lam):
                        continue
                    lo = MB._round_cv_stainless(lam * (1 - 1e-7), LD, E, FY, kind)[0]
                    hi = MB._round_cv_stainless(lam * (1 + 1e-7), LD, E, FY, kind)[0]
                    self.assertLess(abs(lo - hi), 0.01, (kind, LD, lim, lo, hi))
            p, q = (0.24, 2.23) if kind == "shear" else (0.20, 1.87)
            for lim in (p, q):
                lam = lim * EF ** 0.67
                LD = 4.21 * math.sqrt(lam) * 2
                lo = MB._round_cv_stainless(lam * (1 - 1e-7), LD, E, FY, kind)[0]
                hi = MB._round_cv_stainless(lam * (1 + 1e-7), LD, E, FY, kind)[0]
                self.assertLess(abs(lo - hi), 0.015, (kind, lim, lo, hi))

    def test_e7_8_round_slender(self):
        # 6 x 0.050: D/t 126.32 > 0.10 E/Fy = 93.33, very short (Fcr = Fy): Ae = (0.6 x 93.33/126.32 + 0.4) Ag = 0.8433 Ag
        s = SC.round_tube(6, 0.05)
        Pc, d = MB.compression(s, MT.get("A554-304"), 1.0, 1.0, "ASD")
        self.assertLess(rel(d["effective_area"], (0.6 * 93.333 / (6 / 0.0475) + 0.4) * s.A), 1e-4)

    def test_e7_6_rect_continuity(self):
        # be = b at lambda = lambda_r sqrt(Fy/Fcr) (with Fcr = Fy): E7-6 gives about b (1.016 b, capped at b)
        lam = 1.24 * math.sqrt(EF)
        Fel = 4 * math.pi ** 2 * E / (12 * 0.91 * lam ** 2)
        q = math.sqrt(Fel / FY)
        self.assertLess(abs((1 - 0.22 * q) * q - 1.0), 0.02)


class TestFramePass2(unittest.TestCase):
    def test_cantilever_deflection_measure(self):
        # O-2: horizontal cantilever 60 in, tip load 200 lb: PL^3 / 3EI from the tangent at the fixed end
        sec = SC.round_tube(3, 0.12, 1.0)
        m = FR.FrameModel(8, False)
        m.add_node("A", [0, 0, 0]); m.add_node("B", [60, 0, 0])
        m.add_member("C", "A", "B", sec, "A554-304")
        m.support("A", **{d: "fixed" for d in FR.DOFS})
        m.add_case("P", nodal={"B": [0, 0, -200]})
        dfl = m.solve({"P": 1}).member_deflection("C")
        self.assertLess(rel(dfl["cantilever"], 200 * 60 ** 3 / (3 * E * sec.Iz)), 1e-9)
        # the chord measure (end-to-end line) understates a cantilever's tip deflection: why kind matters
        self.assertLess(abs(dfl["rel_y"]), 0.5 * dfl["cantilever"])

    def test_frame_check_cantilever_kind(self):
        d = {"method": "ASD", "options": {"divisions": 4, "shear_deformation": False},
             "nodes": {"A": [0, 0, 0], "B": [60, 0, 0]},
             "members": [{"id": "C", "i": "A", "j": "B", "section": {"shape": "round", "D": 3, "t": 0.12},
                          "material": "A554-304"}],
             "supports": {"A": {d_: "fixed" for d_ in FR.DOFS}},
             "cases": {"D": {"nodal": {"B": [0, 0, -200]}}}, "combinations": {"D": {"D": 1.0}},
             "design": {"C": {"kind": "cantilever"}}}
        c = design.frame_check(d)
        dc = [ch for ch in c.checks if ch.name == "C deflection"][0]
        sec = SC.round_tube(3, 0.12)
        want = 200 * 60 ** 3 / (3 * E * sec.Iz) / (60 / 180)
        self.assertLess(rel(dc.ratio, want), 1e-3)


class TestWeldUnsymmetric(unittest.TestCase):
    def test_l_shaped_group_equilibrium(self):
        # O-3: L group (0,0)-(4,0) and (0,0)-(0,4): centroid (1,1), Ix = Iy = 13.333, Ixy = -8 (hand).
        # The normal force distribution from Mx must satisfy sum(f y dl) = Mx and sum(f x dl) = 0.
        segs = [(0, 0, 4, 0), (0, 0, 0, 4)]
        A, xc, yc, Ix, Iy, Ixy = CN._segments_props(segs)
        self.assertAlmostEqual(xc, 1.0); self.assertAlmostEqual(yc, 1.0)
        self.assertAlmostEqual(Ix, 40 / 3); self.assertAlmostEqual(Ixy, -8.0)
        Mx = 100.0
        det = Ix * Iy - Ixy ** 2
        sm_y = sm_x = 0.0
        n = 2000
        for (x1, y1, x2, y2) in segs:
            L = math.hypot(x2 - x1, y2 - y1)
            for k in range(n):
                s = (k + 0.5) / n
                x, y = x1 + (x2 - x1) * s - xc, y1 + (y2 - y1) * s - yc
                f = (Mx * Iy * y - Mx * Ixy * x) / det
                sm_y += f * y * L / n
                sm_x += f * x * L / n
        self.assertLess(rel(sm_y, Mx), 1e-5)
        self.assertLess(abs(sm_x), 1e-4)
        fmax, _ = CN.weld_group(segs, Mx=Mx, points_per_segment=40)
        # extreme: point (0, 4) -> x -1, y 3: f = 100 (13.333 x 3 - 8) / (177.78 - 64) = 28.12 lb/in
        self.assertLess(rel(fmax, 100 * (40 / 3 * 3 - 8) / (1600 / 9 - 64)), 1e-6)


class TestFloorModels(unittest.TestCase):
    def test_base_plate_concentric(self):
        # O-4: 8 x 8 plate, 4 x 4 post, P 10,000 lb, ASD: fp = 156.25 psi; m = n = (8 - 3.8)/2 = 2.1;
        # t = sqrt(2 x 1.67) x 2.1 x sqrt(156.25 / 30000) = 1.82757 x 2.1 x 0.072169 = 0.2770 in
        c = supports.base_plate({"P": 10000, "N": 8, "B": 8, "tp": 0.5, "plate_material": "A240-304",
                                 "column": {"shape": "rect", "B": 4, "H": 4, "t": 0.12}, "fc": 3000, "A2_A1": 1.0,
                                 "method": "ASD"})
        self.assertLess(rel(c.value("required plate thickness"), 0.2770), 2e-4)

    def test_anchor_group_breakout(self):
        # 2 x 2 at 4 in, hef 3.25, post-installed, cracked, f'c 3000, no edges, seismic:
        # Nb = 17 x 54.772 x 3.25^1.5 (5.859) = 5,455.6; ANc / ANco = 13.75^2 / 95.0625 = 1.98882 -> 10,850
        # available 0.65 x 0.75 x 10,850 = 5,289.6
        c = supports.anchors({"Nua": 3000, "Vua": 0, "n_x": 2, "n_y": 2, "s_x": 4, "s_y": 4, "da": 0.5,
                              "hef": 3.25, "fc": 3000, "anchor_type": "post-installed", "cracked": True,
                              "seismic": True})
        self.assertLess(rel(c.value("Ncbg (group breakout)"), 10850.4), 2e-4)
        ch = [x for x in c.checks if x.name == "concrete breakout, tension"][0]
        self.assertLess(rel(ch.ratio, 3000 / 5289.6), 2e-4)
        # steel: Ase(1/2-13) = 0.1419 in2 (published), 0.75 x 0.1419 x 75,000 = 7,982 per anchor
        self.assertLess(rel(CN.tensile_stress_area(0.5), 0.1419), 5e-4)

    def test_seismic_7_22(self):
        # 0.4 x 1.0 x 1.0 x 1000 x (1 / 1.3) x (2.2 / 1.5) = 451.3 lb (between 300 and 1600)
        c = stability.seismic_force({"edition": "7-22", "SDS": 1.0, "Ip": 1.0, "Wp": 1000, "CAR": 2.2, "Rpo": 1.5})
        self.assertLess(rel(c.value("Fp design (strength level)"), 451.28), 1e-4)

    def test_transport_tipping(self):
        # 42 in wide, CG 30 in up: lateral tipping accel 21/30 = 0.70 g; 0.5 g -> ratio 0.714
        c = stability.transport({"W": 4000, "cg": [72, 21, 30], "footprint": [[0, 0], [144, 0], [144, 42], [0, 42]]})
        lat = [ch for ch in c.checks if ch.name.startswith("lateral 0.5 g")]
        self.assertTrue(lat)
        self.assertLess(rel(max(ch.ratio for ch in lat), 0.5 / 0.7), 1e-6)
        self.assertAlmostEqual(c.value("aggregate working load limit of tie-downs, minimum 0.5 W"), 2000)


class TestAdversarial(unittest.TestCase):
    """O-8: bad inputs stop with InputError (CLI exit 2), never a silent number."""

    def test_bad_inputs(self):
        bad = [
            lambda: SC.rect_tube(2, 2, 1.2),
            lambda: SC.round_tube(2, -0.1),
            lambda: MT.get("A554-305"),
            lambda: SC.from_spec({"shape": "rect", "B": 2}),
            lambda: design.beam({"case": "ss_point", "section": {"shape": "round", "D": 3, "t": 0.12}, "L": -5,
                                 "P": 1, "a": 1}),
            lambda: design.beam({"case": "nope", "section": {"shape": "round", "D": 3, "t": 0.12}, "L": 5}),
            lambda: lifting.lift_lug({"P": 1, "t": 0.5, "Dh": 1.0, "Dp": 1.2, "R": 2, "be": 1, "a": 1}),
            lambda: MB.flexure(SC.round_tube(12, 0.03), MT.get("A554-304")),
            lambda: stability.seismic_force({"SDS": 1.0, "Wp": 100, "Ip": 1.0, "edition": "7-22"}),
            lambda: design.frame_check({"nodes": {"A": [0, 0, 0], "B": [10, 0, 0]},
                                        "members": [{"id": "M", "i": "A", "j": "B",
                                                     "section": {"shape": "round", "D": 3, "t": 0.12},
                                                     "material": "A554-304"}],
                                        "supports": {"A": {"uz": "fixed"}},
                                        "cases": {"D": {"self_weight": 1}}, "combinations": {"x": {"D": 1}}}),
            lambda: design.frame_check({"nodes": {"A": [0, 0, 0], "B": [10, 0, 0]},
                                        "members": [{"id": "M", "i": "A", "j": "B",
                                                     "section": {"shape": "round", "D": 3, "t": 0.12},
                                                     "material": "A554-304"}],
                                        "supports": {"A": {d: "fixed" for d in FR.DOFS}},
                                        "cases": {"D": {"self_weight": 1}}, "combinations": {"x": {"Q": 1}}}),
        ]
        for k, f in enumerate(bad):
            with self.assertRaises(InputError, msg=f"case {k}"):
                f()

    def test_units_warning(self):
        d = {"nodes": {"A": [0, 0, 0], "B": [10, 0, 0]},
             "members": [{"id": "M", "i": "A", "j": "B", "section": {"shape": "round", "D": 3, "t": 0.12},
                          "material": "A554-304"}],
             "supports": {"A": {d_: "fixed" for d_ in FR.DOFS}},
             "cases": {"D": {"self_weight": 1}}, "combinations": {"D": {"D": 1}}}
        d["nodes"]["B"] = [0.5, 0, 0]          # a 'half' -- someone typed feet as inches
        c = design.frame_check(d)
        self.assertTrue(any("check units" in w for w in c.warnings))


if __name__ == "__main__":
    unittest.main()
