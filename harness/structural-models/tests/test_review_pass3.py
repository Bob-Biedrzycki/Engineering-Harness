"""Pass 3: independent review (engineering-manager agent, CPM-190, 2026-11-06).

Every expected value below is a hand calculation from the clause or from statics, written out in the comment. It is
not the code's output. A test named test_Fnn_... reproduces finding Fnn of the pass 3 review. It FAILS until that
finding is fixed; do not change the expected value to make it pass.

Hand-check tests that pass (HC-...) confirm paths no earlier test covered.
"""
from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from skidframe import design, supports                # noqa: E402
from skidframe import frame as FR                     # noqa: E402
from skidframe import loads as LD                     # noqa: E402
from skidframe import materials as MT                 # noqa: E402
from skidframe import members as MB                   # noqa: E402
from skidframe import sections as SC                  # noqa: E402

E, FY = 28e6, 30e3
EF = E / FY          # 933.333


def rel(a, b):
    return abs(a - b) / max(abs(b), 1e-12)


# ====================================================================== F-01  AISC 370 G4 / G8.1 CvM band limits
class TestF01RoundCvBandLimits(unittest.TestCase):
    """AISC 370-21 G8-4..G8-6 (and G4-4..G4-6), printed page 75 (scratchpad p125.png): the band limits are
    0.26 ((E/Fy)/sqrt(L/D))^0.80 and 3.77 ((E/Fy)/sqrt(L/D))^0.80: the coefficient is OUTSIDE the power.
    members._round_cv_stainless lines 373-374 compute (0.26 (E/Fy)/sqrt(L/D))^0.80 = 0.3404 X^0.8 and
    (3.77 ...)^0.80 = 2.891 X^0.8 (X = (E/Fy)/sqrt(L/D)), so band (i) is too wide and band (iii) starts too early,
    both on the unsafe side."""

    def test_F01_torsion_lower_band_realistic_tube(self):
        # 2.0 OD x 0.065 tube, t = 0.95 x 0.065 = 0.06175, lambda = 2.0 / 0.06175 = 32.389; L = 16 in, L/D = 8.
        # Medium length: L/D 8 <= 4.21 sqrt(32.389) = 23.96 -> CvM (G8-2).
        # X = 933.333 / sqrt(8) = 933.333 / 2.828427 = 329.983; X^0.8 = exp(0.8 ln 329.983) = exp(4.63923) = 103.47
        # printed lower limit 0.26 x 103.47 = 26.90 < 32.389 <= 3.77 x 103.47 = 390.1 -> band (ii), G8-5:
        # lambda^1.25 = exp(1.25 ln 32.389) = exp(4.34733) = 77.274
        # y = sqrt(L/D) lambda^1.25 / (E/Fy) = 2.828427 x 77.274 / 933.333 = 0.234176; sqrt(y) = 0.48392
        # CvM = 1 - 0.61 (0.54 x 0.48392 - 0.23) = 1 - 0.61 x 0.031316 = 0.98090
        # (code: limit (0.26 x 329.983)^0.8 = 35.22 > 32.389 -> Cv = 1.0, 1.9 % high)
        lam = 2.0 / (0.065 * 0.95)
        cv, branch, _ = MB._round_cv_stainless(lam, 8.0, E, FY, "torsion")
        self.assertEqual(branch, "CvM")
        self.assertLess(rel(cv, 0.98090), 3e-4, cv)

    def test_F01_torsion_upper_band_thin_tube(self):
        # 6.0 OD x 0.040 wall, t_factor 1.0: lambda = 150; L = 300 in, L/D = 50 <= 4.21 sqrt(150) = 51.56 -> CvM.
        # X = 933.333 / 7.0711 = 131.993; X^0.8 = exp(0.8 x 4.88275) = exp(3.90620) = 49.71
        # printed upper limit 3.77 x 49.71 = 187.4 >= 150 -> band (ii), G8-5:
        # lambda^1.25 = exp(1.25 x 5.010635) = exp(6.263294) = 524.95
        # y = 7.0711 x 524.95 / 933.333 = 3.97704; sqrt = 1.99425; 0.54 x 1.99425 = 1.07690; - 0.23 = 0.84690
        # CvM = 1 - 0.61 x 0.84690 = 0.48339
        # (code: limit (3.77 x 131.993)^0.8 = 143.7 < 150 -> G8-6 2.05 / 3.97704 = 0.5155, 6.6 % high)
        cv, branch, _ = MB._round_cv_stainless(150.0, 50.0, E, FY, "torsion")
        self.assertEqual(branch, "CvM")
        self.assertLess(rel(cv, 0.48339), 3e-4, cv)

    def test_F01_printed_bands_are_continuous(self):
        # With the coefficient outside the power the printed bands meet (to the 3-figure rounding of the print):
        # at lambda = b X^0.8, y = b^1.25: torsion upper y = 3.77^1.25 = 5.2565, sqrt 2.2927,
        # G8-5 1 - 0.61 (0.54 x 2.2927 - 0.23) = 0.3851 vs G8-6 2.05 / 5.2565 = 0.3900 (jump 0.005, not 0.043);
        # shear upper y = 4.65^1.25 = 6.8304, sqrt 2.6135, G4-5 1 - 0.61 (0.47 x 2.6135 - 0.23) = 0.3910 vs
        # G4-6 2.67 / 6.8304 = 0.3909. Lower limits: torsion y = 0.26^1.25 = 0.18594, sqrt 0.43121,
        # 0.54 x 0.43121 = 0.2329 -> 0.998; shear y = 0.32^1.25 = 0.24063, 0.47 x 0.49054 = 0.2306 -> 1.000.
        # So README "Known limits" 1, METHODS section 3 and REVIEW-LOG P2-6 (jumps up to 0.05) are artefacts of F-01.
        for kind, a, b in (("shear", 0.32, 4.65), ("torsion", 0.26, 3.77)):
            LD_ = 9.0
            X = EF / math.sqrt(LD_)
            for lim in (a, b):
                lam = lim * X ** 0.8
                if LD_ > 4.21 * math.sqrt(lam):
                    continue
                lo = MB._round_cv_stainless(lam * (1 - 1e-7), LD_, E, FY, kind)[0]
                hi = MB._round_cv_stainless(lam * (1 + 1e-7), LD_, E, FY, kind)[0]
                self.assertLess(abs(lo - hi), 0.006, (kind, lim, lo, hi))


# ====================================================================== F-02  spring support reactions
class TestF02SpringReaction(unittest.TestCase):
    def test_F02_spring_support_reports_its_force(self):
        # Beam A-B, 100 in, pinned at A (ux uy uz rx fixed, ry rz free), B on a vertical spring k = 1000 lb/in,
        # uy fixed at B. 500 lb down at B.
        # Statics: moments about A: R_B x 100 = 500 x 100 -> R_B = +500 lb (up), R_A = 0. Spring shortens
        # 500 / 1000 = 0.500 in. Code: Rfull = K u - F is zero at a free DOF that carries a spring (the spring is
        # inside K), so reaction('B')[2] = 0 and the support reactions do not sum to the load.
        m = FR.FrameModel(divisions=4)
        m.add_node("A", [0, 0, 0])
        m.add_node("B", [100, 0, 0])
        m.add_member("B1", "A", "B", {"shape": "round", "D": 3.0, "t": 0.12}, "A554-304")
        m.support("A", ux="fixed", uy="fixed", uz="fixed", rx="fixed")
        m.support("B", uy="fixed", uz=1000.0)
        m.add_case("P", nodal={"B": [0, 0, -500]})
        r = m.solve({"P": 1.0})
        self.assertAlmostEqual(r.disp("B")[2], -0.5, places=6)          # passes: the displacement is right
        self.assertAlmostEqual(r.reaction("B")[2], 500.0, places=3)     # F-02: code returns 0.0


# ====================================================================== F-03  F7 slender web
class TestF03SlenderWebFlexure(unittest.TestCase):
    def test_F03_slender_web_not_above_yield_moment(self):
        # 6 x 2 x 0.065 304 tube bent about z (depth 6 in along local y). t = 0.06175, r_out = 2t = 0.1235,
        # r_in = 0.06175, h_flat = 6 - 2(0.06175) - 2(0.06175) = 5.753, h/t = 93.17.
        # Table B4.1b case 5: lambda_r = 3.01 sqrt(28000/30) = 3.01 x 30.551 = 91.96 < 93.17 -> slender web.
        # AISC 370 F7.3(c): Mn = Rpg Fy S (F7-6) or Rpg Fy Se (F7-7), Rpg <= 1.0 (F5-4) -> Mn <= Fy Sz.
        # Code line 231-233 keeps Mn_w = Mp = Fy Zz (> Fy Sz) with only a note: unsafe, and higher than the
        # noncompact answer just below lambda_r (F7-5 there gives ~Fy S).
        s = SC.rect_tube(2.0, 6.0, 0.065)
        mat = MT.get("A554-304")
        lam = s.elements["h_flat"] / s.t
        self.assertGreater(lam, 3.01 * math.sqrt(EF))
        _, d = MB.flexure(s, mat, "z", "ASD")
        self.assertLessEqual(d["Mn"], FY * s.Sz * (1 + 1e-9), (d["Mn"], FY * s.Sz, FY * s.Zz))


# ====================================================================== F-04  solid square bar torsion
class TestF04SquareBarTorsion(unittest.TestCase):
    def test_F04_square_bar_torsional_shear_yield(self):
        # 1.0 in square 304 bar. Roark 7th Table 10.7 case 4 (square, a/b = 1): tau_max = T / (0.208 a^3)
        # (alpha = 0.208), at mid-side. Shear yield 0.6 Fy: Tn = 0.6 x 30,000 x 0.208 x 1.0 = 3,744 lb-in.
        # Code: rmax = a/2 = 0.5 and J = a^4/3 (1 - 0.63) = 0.12333 -> Tn = 0.6 x 30,000 x 0.12333 / 0.5 = 4,440
        # lb-in, 18.6 % high (T r / J is the circular-shaft formula; it does not hold for a square).
        s = SC.from_spec({"shape": "bar", "a": 1.0})
        _, d = MB.torsion(s, MT.get("A276-304"), "ASD")
        self.assertLess(rel(d["Tn"], 3744.0), 0.02, d["Tn"])


# ====================================================================== F-05  base plate, large eccentricity
class TestF05BasePlateLargeEccentricity(unittest.TestCase):
    def test_F05_bearing_interface_thickness_when_Y_less_than_m(self):
        # AISC DG1 large-eccentricity, ASD. Plate N = B = 10 in, column 6 x 6 HSS, P = 10,000 lb, M = 60,000 lb-in,
        # f'c 3000, A2/A1 1, anchors 2.0 in from the edge, 304 plate Fy 30,000.
        # fp = 0.85 x 3000 / 2.31 = 1103.90 psi; qmax = fp B = 11,039.0 lb/in
        # e = 6.0 in > e_crit = 5 - 10,000 / (2 x 11,039.0) = 4.547 in -> large eccentricity
        # f = 5 - 2 = 3.0; (f + N/2)^2 = 64; 2 P (e + f) / qmax = 2 x 10,000 x 9 / 11,039.0 = 16.306
        # Y = 8 - sqrt(47.694) = 8 - 6.9061 = 1.0939 in; m = (10 - 0.95 x 6) / 2 = 2.15 in > Y
        # DG1 (Y < m): t = 2.58 sqrt(fp Y (m - Y/2) / Fy) (ASD; 2.11 LRFD), the same form the code uses for the
        # small-eccentricity branch (supports.py line 168-169):
        #   fp Y (m - Y/2) = 1103.90 x 1.0939 x (2.15 - 0.54695) = 1935.8; / 30,000 = 0.064525; sqrt 0.25402
        #   t_bear = 2.58 x 0.25402 = 0.6554 in
        # anchor side: T = 11,039.0 x 1.0939 - 10,000 = 2,075.6 lb; x = 3.0 - 0.95 x 6 / 2 = 0.15 in;
        #   t_tens = 2.58 sqrt(2,075.6 x 0.15 / (10 x 30,000)) = 2.58 x 0.032215 = 0.0831 in
        # t_req = 0.6554 in. Code line 180 uses k_t = sqrt(2 x 1.67) = 1.8276 for Y < m: 0.4642 in (under by sqrt 2).
        c = supports.base_plate({"P": 10000.0, "M": 60000.0, "N": 10.0, "B": 10.0, "tp": 0.75, "method": "ASD",
                                 "plate_material": "A240-304", "fc": 3000.0, "A2_A1": 1.0, "anchor_edge": 2.0,
                                 "column": {"shape": "rect", "B": 6.0, "H": 6.0, "t": 0.12}})
        self.assertLess(rel(c.results["bearing length Y"][0], 1.0939), 1e-3)          # passes
        self.assertLess(rel(c.results["anchor group tension T"][0], 2075.6), 1e-3)    # passes
        self.assertLess(rel(c.results["required plate thickness"][0], 0.6554), 2e-3)  # F-05: code 0.4642


# ====================================================================== F-06  temperature in frame_check
def _ss_frame(member_extra=None, top_extra=None):
    mem = {"id": "B1", "i": "A", "j": "B", "section": "R", "material": "A554-304"}
    mem.update(member_extra or {})
    d = {"method": "ASD",
         "sections": {"R": {"shape": "round", "D": 3.0, "t": 0.12}},
         "nodes": {"A": [0, 0, 0], "B": [100, 0, 0]},
         "members": [mem],
         "supports": {"A": {"ux": "fixed", "uy": "fixed", "uz": "fixed", "rx": "fixed"},
                      "B": {"uy": "fixed", "uz": "fixed"}},
         "cases": {"D": {"member_point": [{"member": "B1", "at": 0.5, "P": [0, 0, -1000]}]}},
         "combinations": {"C1": {"D": 1.0}},
         "design": {"*": {"kind": "none"}}}
    d.update(top_extra or {})
    return d


class TestF06TemperatureIgnoredByFrameCheck(unittest.TestCase):
    def test_F06_member_temperature_reduces_strength(self):
        # README "Rules": give temperature_F for a member that runs warm. 304 at 400 F: ky = 0.65 (AISC 370 App. 4,
        # materials._K_304), so Fy 30,000 -> 19,500 psi and the flexural capacity (compact round, Mp = Fy Z) drops
        # by 0.65: the interaction ratio of this flexure-only beam must rise by about 1 / 0.65 = 1.54.
        # Code: from_dict passes the member's extra keys into meta and frame_check never reads temperature_F, so
        # the ratio is unchanged (silently room-temperature strength).
        def ratio(calc):
            return [ch.ratio for ch in calc.checks if ch.name == "B1 interaction"][0]
        r0 = ratio(design.frame_check(_ss_frame()))
        r1 = ratio(design.frame_check(_ss_frame({"temperature_F": 400})))
        self.assertGreater(r1 / r0, 1.45, (r0, r1))


# ====================================================================== F-07  near-vertical local axes
class TestF07NearVerticalAxes(unittest.TestCase):
    def test_F07_local_y_continuous_near_vertical(self):
        # A post 30 in tall exactly vertical gets local y = +X (frame.py line 102-103). The same post with its top
        # 0.01 in off in Y (tilt 0.019 deg, below any fabrication tolerance) takes the other branch: local y is the
        # projection of +Z, normalised = (0, -1.000, 0.0003). A rectangular post's strong axis turns 90 degrees.
        # Expected: a convention that does not jump for a sub-tolerance tilt (local y stays ~ +X).
        R1, _ = FR.rotation([0, 0, 0], [0, 0, 30])
        R2, _ = FR.rotation([0, 0, 0], [0, 0.01, 30])
        self.assertGreater(float(R1[1] @ R2[1]), 0.99, (R1[1], R2[1]))


# ====================================================================== F-08  buckling with a released member
class TestF08BucklingWithReleasedMember(unittest.TestCase):
    def test_F08_buckling_with_pinned_beam_at_zero_axial(self):
        # Column A-B (60 in, fixed base) carries 1000 lb; beam B-C pinned at both ends (ry, rz released) and has
        # zero axial force. The geometric matrix of the beam is all zero, so _condense(kg) inverts a zero block and
        # buckling() raises "member releases leave the member unstable". frame_check catches it and prints
        # "not solved" with no warning. Expected: a factor (column braced at B by the pinned beam and C: between
        # the fixed-pinned 2.046 pi^2 EI / L^2 and fixed-free pi^2 EI / (4 L^2) values, i.e. > 0).
        sec = {"shape": "round", "D": 3.0, "t": 0.12}
        m = FR.FrameModel(divisions=4)
        m.add_node("A", [0, 0, 0])
        m.add_node("B", [0, 0, 60])
        m.add_node("C", [60, 0, 60])
        m.add_member("COL", "A", "B", sec, "A554-304")
        m.add_member("BM", "B", "C", sec, "A554-304", releases={"i": ["ry", "rz"], "j": ["ry", "rz"]})
        m.support("A", ux="fixed", uy="fixed", uz="fixed", rx="fixed", ry="fixed", rz="fixed")
        m.support("C", ux="fixed", uy="fixed", uz="fixed", rx="fixed", ry="fixed", rz="fixed")
        m.add_case("P", nodal={"B": [0, 0, -1000]})
        lam = m.buckling({"P": 1.0}, 1)
        self.assertTrue(lam and lam[0] > 0)

    def test_HC_released_column_coarse_mesh(self):
        # NOTE (part of F-08): condensing Kg with its own Schur complement is mesh sensitive. Pinned-pinned column
        # 100 in, 3.0 x 0.120 (I = 1.1045 in4 from sections), no shear deformation: Euler factor
        # pi^2 x 28e6 x I / 100^2 / 1000. With 8 divisions released and unreleased agree to 0.02 % (passes).
        sec = {"shape": "round", "D": 3.0, "t": 0.12}
        s = SC.from_spec(sec)
        euler = math.pi ** 2 * E * s.Iz / 100 ** 2 / 1000

        def col(release, div):
            m = FR.FrameModel(divisions=div, shear_deformation=False)
            m.add_node("A", [0, 0, 0])
            m.add_node("B", [0, 0, 100])
            m.add_member("C", "A", "B", sec, "A554-304",
                         releases={"i": ["ry", "rz"], "j": ["ry", "rz"]} if release else None)
            if release:
                m.support("A", ux="fixed", uy="fixed", uz="fixed", rx="fixed", ry="fixed", rz="fixed")
                m.support("B", ux="fixed", uy="fixed", rx="fixed", ry="fixed")
            else:
                m.support("A", ux="fixed", uy="fixed", uz="fixed", rz="fixed")
                m.support("B", ux="fixed", uy="fixed")
            m.add_case("P", nodal={"B": [0, 0, -1000]})
            return m.buckling({"P": 1.0}, 1)[0]
        self.assertLess(rel(col(True, 8), euler), 2e-3)
        # at 2 divisions the released model gives 32.19 vs Euler 29.78 (+8 %, unconservative) while the unreleased
        # model gives 30.01 (+0.8 %): recorded in the review, not asserted (a mesh study, not a defect by itself).


# ====================================================================== F-09  auto combinations drop LIFT etc.
class TestF09AutoCombinationsDropHandlingCases(unittest.TestCase):
    def test_F09_lift_case_is_not_silently_dropped(self):
        # loads.combinations("ASD", {"D", "LIFT"}) returns only "ASD-1 D+F" -> {D: 1.0}; LIFT (and TRANSPORT,
        # HYDRO, PUMP) never enter any combination, and frame_check's assumption line lists the cases as if they
        # were combined. Expected: each handling case analysed on its own (LIFT alone, per the loads.py docstring
        # "checked on their own") or an input error naming it.
        combos = LD.combinations("ASD", {"D", "LIFT"})
        self.assertTrue(any("LIFT" in f for f in combos.values()), combos)


# ====================================================================== hand checks that pass
class TestHandChecksPass3(unittest.TestCase):
    def test_HC_vertical_cantilever_roll90_member_forces(self):
        # Post A(0,0,0)-B(0,0,60), rect 2 (B, local z) x 4 (H, local y) x 0.12, roll 90.
        # Vertical member: y0 = +X, z0 = x cross y0 = Z cross X = +Y. Roll 90: y = z0 = +Y, z = -y0 = -X.
        # 100 lb in +X at B is -100 along local z. Force on the lower part at a cut s from the upper part:
        # (0, 0, -100) -> Vz = -100. Moment of the tip load about the cut: (60 - s) x_hat x (-100 z_hat)
        # = +100 (60 - s) y_hat -> My(0) = +6,000 lb-in, Mz = 0. It bends about local y (Iy, B along z):
        # tip ux = P L^3 / (3 E Iy) = 100 x 216,000 / (3 x 28e6 x Iy).
        sec = {"shape": "rect", "B": 2.0, "H": 4.0, "t": 0.12}
        s = SC.from_spec(sec)
        m = FR.FrameModel(divisions=4, shear_deformation=False)
        m.add_node("A", [0, 0, 0])
        m.add_node("B", [0, 0, 60])
        m.add_member("C", "A", "B", sec, "A554-304", roll=90)
        m.support("A", ux="fixed", uy="fixed", uz="fixed", rx="fixed", ry="fixed", rz="fixed")
        m.add_case("H", nodal={"B": [100, 0, 0]})
        r = m.solve({"H": 1.0})
        f0 = r.member_forces("C")[0]
        self.assertAlmostEqual(f0["My"], 6000.0, places=3)
        self.assertAlmostEqual(f0["Vz"], -100.0, places=6)
        self.assertAlmostEqual(f0["Mz"], 0.0, places=6)
        self.assertLess(rel(r.disp("B")[0], 100 * 60 ** 3 / (3 * E * s.Iy)), 1e-9)

    def test_HC_pdelta_cantilever_base_moment_exact(self):
        # Cantilever post L = 100 in, round 3.0 x 0.120 (EI = 28e6 x Iz), axial P = 0.3 Pcr, Pcr = pi^2 EI/(4 L^2).
        # Exact second-order base moment (Timoshenko & Gere, beam-column with end load H):
        # M0 = H tan(kL) / k, k = sqrt(P/EI); kL = (pi/2) sqrt(0.3) = 0.86036; tan(kL) = 1.16516;
        # M0 = H L tan(kL)/(kL) = 100 x 100 x 1.16516 / 0.86036 = 13,542.6 ... computed below to full precision;
        # tip deflection d = H (tan kL - kL) / (P k).
        # Checks member_forces with pdelta (end forces from (k + kg) u) and the reaction moment.
        sec = {"shape": "round", "D": 3.0, "t": 0.12}
        s = SC.from_spec(sec)
        EI = E * s.Iz
        L, H = 100.0, 100.0
        P = 0.3 * math.pi ** 2 * EI / (4 * L * L)
        k = math.sqrt(P / EI)
        M0 = H * math.tan(k * L) / k
        dtip = H * (math.tan(k * L) - k * L) / (P * k)
        m = FR.FrameModel(divisions=8, shear_deformation=False)
        m.add_node("A", [0, 0, 0])
        m.add_node("B", [0, 0, L])
        m.add_member("C", "A", "B", sec, "A554-304")
        m.support("A", ux="fixed", uy="fixed", uz="fixed", rx="fixed", ry="fixed", rz="fixed")
        m.add_case("H", nodal={"B": [H, 0, -P]})
        r = m.solve({"H": 1.0}, pdelta=True)
        f0 = r.member_forces("C")[0]
        self.assertLess(rel(abs(f0["Mz"]), M0), 1e-4)
        self.assertLess(rel(abs(r.reaction("A")[4]), M0), 1e-4)
        self.assertLess(rel(r.disp("B")[0], dtip), 1e-4)
        self.assertLess(rel(f0["N"], -P), 1e-6)

    def test_HC_overturning_lateral_at_height(self):
        # 2 ft square of 4 feet at (0,0) (24,0) (24,24) (0,24); W 1000 lb, CG (12, 12, 30); ax = 0.2 g.
        # About the x = 24 edge: Mr = 1000 x 12 = 12,000; Mo = 0.2 x 1000 x 30 = 6,000 -> SF = 2.00.
        # Least static tipping acceleration d/h = 12 / 30 = 0.400 g.
        from skidframe import stability
        c = stability.overturning({"footprint": [[0, 0], [24, 0], [24, 24], [0, 24]], "W": 1000.0,
                                   "cg": [12, 12, 30], "mu": 0.5, "SF_required": 1.5,
                                   "cases": [{"name": "x", "ax": 0.2, "ay": 0.0, "gravity": 1.0}]})
        self.assertAlmostEqual(c.results["least tipping acceleration"][0], 0.4, places=6)
        ch = [k for k in c.checks if k.name == "x: overturning"][0]
        self.assertAlmostEqual(ch.ratio, 1.5 / 2.0, places=6)


if __name__ == "__main__":
    unittest.main()
