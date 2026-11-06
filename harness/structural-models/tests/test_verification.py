"""Verification of skidframe against independent results.

Each expected value is a hand calculation (worked in the comment), a published table value, or a closed-form
textbook solution. None is produced by the code under test. Run from the Structural_Models folder:

  ..\\..\\..\\..\\..\\harness\\tools\\venv\\Scripts\\python.exe -m unittest discover -s tests -v

Stdlib unittest only (same as harness/tests).
"""
from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from skidframe import beams as B                     # noqa: E402
from skidframe import connections as CN              # noqa: E402
from skidframe import dynamics as DY                 # noqa: E402
from skidframe import frame as FR                    # noqa: E402
from skidframe import lifting as LF                  # noqa: E402
from skidframe import loads as LD                    # noqa: E402
from skidframe import materials as MT                # noqa: E402
from skidframe import members as MB                  # noqa: E402
from skidframe import sections as SC                 # noqa: E402
from skidframe import stability as ST                # noqa: E402
from skidframe import supports as SP                 # noqa: E402
from skidframe.core import InputError                # noqa: E402

E_SS = 28.0e6


def rel(a, b):
    return abs(a - b) / max(abs(b), 1e-12)


# ===================================================================== sections
class TestSections(unittest.TestCase):
    def test_hss4x4x1_4_matches_aisc_manual(self):
        # AISC Manual 16th ed. Table 1-12, HSS4x4x1/4: t_des 0.233, A 3.37, I 7.80, S 3.90, Z 4.69, J 12.8
        s = SC.rect_tube(4, 4, 0.25, t_factor=0.233 / 0.25)
        for got, want in ((s.A, 3.37), (s.Iz, 7.80), (s.Sz, 3.90), (s.Zz, 4.69), (s.J, 12.8)):
            self.assertLess(rel(got, want), 0.006, (got, want))

    def test_round_tube_exact(self):
        # 3.0 OD x 0.120 nominal wall: A = pi/4 (9 - 7.6176) = 1.08573, I = pi/64 (81 - 58.0278) = 1.12765
        s = SC.round_tube(3.0, 0.12, t_factor=1.0)
        self.assertAlmostEqual(s.A, 1.08573, places=5)
        self.assertAlmostEqual(s.Iz, 1.12764, places=5)
        self.assertAlmostEqual(s.J, 2 * 1.12765, places=4)
        self.assertAlmostEqual(s.Zz, (27 - 2.76 ** 3) / 6, places=6)

    def test_sharp_rectangle_limit(self):
        A, I, Z = SC._rounded_rect(2.0, 3.0, 0.0)
        self.assertAlmostEqual(A, 6.0)
        self.assertAlmostEqual(I, 2 * 27 / 12)
        self.assertAlmostEqual(Z, 2 * 9 / 4)

    def test_spandrel_full_quarter_circle_area(self):
        # a 2r x 2r rounded square of radius r is a circle: area pi r^2, I = pi r^4 / 4
        A, I, _ = SC._rounded_rect(2.0, 2.0, 1.0)
        self.assertAlmostEqual(A, math.pi, places=9)
        self.assertAlmostEqual(I, math.pi / 4, places=9)

    def test_angle_principal(self):
        # L2x2x1/4 (sharp): A = 0.9375; Ix about centroid: centroid 0.5917 from heel; AISC (with fillets) 0.348 in4
        s = SC.angle(2, 2, 0.25)
        self.assertAlmostEqual(s.A, 0.9375)
        self.assertLess(rel(s.Iz, 0.348), 0.03)
        self.assertLess(rel(s.r_min, 0.391), 0.03)   # AISC rz 0.391 in (with fillet)


# ===================================================================== frame solver vs closed form
def beam_model(L=120.0, sec=None, divisions=8, shear=False):
    m = FR.FrameModel(divisions=divisions, shear_deformation=shear)
    m.add_node("A", [0, 0, 0])
    m.add_node("B", [L, 0, 0])
    m.add_member("M", "A", "B", sec or {"shape": "round", "D": 3, "t": 0.12, "t_factor": 1.0}, "A554-304")
    return m


class TestFrame(unittest.TestCase):
    def setUp(self):
        self.sec = SC.round_tube(3, 0.12, 1.0)
        self.EI = E_SS * self.sec.Iz

    def test_simple_span_point_and_udl(self):
        m = beam_model()
        m.support("A", ux="fixed", uy="fixed", uz="fixed", rx="fixed")
        m.support("B", uy="fixed", uz="fixed")
        m.add_case("P", member_point=[{"member": "M", "at": 0.3, "P": [0, 0, -1000]}])
        m.add_case("W", member_udl=[{"member": "M", "w": [0, 0, -5]}])
        L, a = 120.0, 36.0
        r = m.solve({"P": 1})
        env, _ = r.member_envelope("M")
        self.assertLess(rel(abs(env["Mz"][0]), 1000 * a * (L - a) / L), 1e-9)
        self.assertLess(rel(r.reaction("A")[2], 1000 * (L - a) / L), 1e-9)
        # deflection under the load: P a^2 b^2 / (3 E I L)
        d_load = -r.disp(m.names[m.members["M"].node_ids[m.members["M"].stations.index(36.0)]])[2]
        self.assertLess(rel(d_load, 1000 * a * a * (L - a) ** 2 / (3 * self.EI * L)), 1e-9)
        r = m.solve({"W": 1})
        self.assertLess(rel(-r.member_deflection("M")["rel_y"], 5 * 5 * L ** 4 / (384 * self.EI)), 1e-9)

    def test_cantilever_tip_load_and_torque(self):
        m = beam_model()
        m.support("A", **{d: "fixed" for d in FR.DOFS})
        m.add_case("P", nodal={"B": [0, 0, -500, 0, 0, 0]})
        m.add_case("T", nodal={"B": [0, 0, 0, 2000, 0, 0]})
        r = m.solve({"P": 1})
        self.assertLess(rel(-r.disp("B")[2], 500 * 120 ** 3 / (3 * self.EI)), 1e-9)
        env, _ = r.member_envelope("M")
        self.assertLess(rel(abs(env["Mz"][0]), 500 * 120), 1e-9)
        r = m.solve({"T": 1})
        G = 10.8e6
        self.assertLess(rel(r.disp("B")[3], 2000 * 120 / (G * self.sec.J)), 1e-9)

    def test_shear_deformation_term(self):
        # Timoshenko cantilever: delta = P L^3 / 3EI + P L / (G Av); rect 4x4x1/4, L = 20 in
        sec = SC.rect_tube(4, 4, 0.25)
        m = beam_model(L=20.0, sec=sec, shear=True)
        m.support("A", **{d: "fixed" for d in FR.DOFS})
        m.add_case("P", nodal={"B": [0, 0, -1000]})
        r = m.solve({"P": 1})
        want = 1000 * 20 ** 3 / (3 * E_SS * sec.Iz) + 1000 * 20 / (10.8e6 * sec.Avy)
        self.assertLess(rel(-r.disp("B")[2], want), 1e-9)

    def test_fixed_fixed_and_propped(self):
        L, w = 100.0, 4.0
        m = beam_model(L)
        m.support("A", **{d: "fixed" for d in FR.DOFS})
        m.support("B", **{d: "fixed" for d in FR.DOFS})
        m.add_case("W", member_udl=[{"member": "M", "w": [0, 0, -w]}])
        r = m.solve({"W": 1})
        self.assertLess(rel(abs(r.reaction("A")[4]), w * L * L / 12), 1e-9)
        m2 = beam_model(L)
        m2.support("A", **{d: "fixed" for d in FR.DOFS})
        m2.support("B", uy="fixed", uz="fixed")
        m2.add_case("W", member_udl=[{"member": "M", "w": [0, 0, -w]}])
        r = m2.solve({"W": 1})
        self.assertLess(rel(r.reaction("A")[2], 5 * w * L / 8), 1e-9)
        self.assertLess(rel(r.reaction("B")[2], 3 * w * L / 8), 1e-9)

    def test_releases_make_simple_span(self):
        L, w = 100.0, 4.0
        m = FR.FrameModel(8, False)
        m.add_node("A", [0, 0, 0]); m.add_node("B", [L, 0, 0])
        m.add_member("M", "A", "B", {"shape": "round", "D": 3, "t": 0.12, "t_factor": 1.0}, "A554-304",
                     releases={"i": ["ry", "rz"], "j": ["ry", "rz"]})
        m.support("A", **{d: "fixed" for d in FR.DOFS})
        m.support("B", **{d: "fixed" for d in FR.DOFS})
        m.add_case("W", member_udl=[{"member": "M", "w": [0, 0, -w]}])
        r = m.solve({"W": 1})
        env, _ = r.member_envelope("M")
        self.assertLess(rel(abs(env["Mz"][0]), w * L * L / 8), 1e-9)

    def test_two_span_continuous(self):
        # two equal spans, UDL: centre reaction 1.25 w L, end reactions 0.375 w L, support moment w L^2 / 8
        L, w = 60.0, 3.0
        m = FR.FrameModel(8, False)
        for n, x in (("A", 0), ("B", L), ("C", 2 * L)):
            m.add_node(n, [x, 0, 0])
        for mid, i, j in (("M1", "A", "B"), ("M2", "B", "C")):
            m.add_member(mid, i, j, {"shape": "round", "D": 3, "t": 0.12, "t_factor": 1.0}, "A554-304")
        m.support("A", ux="fixed", uy="fixed", uz="fixed", rx="fixed")
        m.support("B", uy="fixed", uz="fixed")
        m.support("C", uy="fixed", uz="fixed")
        m.add_case("W", member_udl=[{"member": "M1", "w": [0, 0, -w]}, {"member": "M2", "w": [0, 0, -w]}])
        r = m.solve({"W": 1})
        self.assertLess(rel(r.reaction("B")[2], 1.25 * w * L), 1e-9)
        self.assertLess(rel(r.reaction("A")[2], 0.375 * w * L), 1e-9)

    def test_contact_lifts_off(self):
        # beam on 3 contact supports; an upward load at one end lifts that end's support off
        L = 60.0
        m = FR.FrameModel(8, False)
        for n, x in (("A", 0), ("B", L), ("C", 2 * L)):
            m.add_node(n, [x, 0, 0])
        m.add_member("M1", "A", "B", {"shape": "round", "D": 3, "t": 0.12}, "A554-304")
        m.add_member("M2", "B", "C", {"shape": "round", "D": 3, "t": 0.12}, "A554-304")
        m.support("A", ux="fixed", uy="fixed", uz="contact", rx="fixed")
        m.support("B", uy="fixed", uz="contact")
        m.support("C", uy="fixed", uz="contact")
        # downward 1000 at the B-C mid-span, nothing else: A carries tension in a bilateral model (it would pull),
        # so it must lift off and the load splits between B and C as a simple span
        m.add_case("P", member_point=[{"member": "M2", "at": 0.5, "P": [0, 0, -1000]}])
        r = m.solve({"P": 1})
        self.assertIn(("A", "uz"), r.lifted())
        self.assertLess(rel(r.reaction("B")[2], 500), 1e-6)
        self.assertLess(rel(r.reaction("C")[2], 500), 1e-6)

    def test_euler_buckling_pinned_and_cantilever(self):
        L = 100.0
        sec = SC.round_tube(3, 0.12, 1.0)
        Pe = math.pi ** 2 * E_SS * sec.Iz / L ** 2
        m = FR.FrameModel(10, False)
        m.add_node("A", [0, 0, 0]); m.add_node("B", [0, 0, L])
        m.add_member("C", "A", "B", sec, "A554-304")
        m.support("A", ux="fixed", uy="fixed", uz="fixed", rz="fixed")
        m.support("B", ux="fixed", uy="fixed", rz="fixed")
        m.add_case("P", nodal={"B": [0, 0, -1.0]})
        lam = m.buckling({"P": 1})[0]
        self.assertLess(rel(lam, Pe), 0.005)
        m2 = FR.FrameModel(10, False)
        m2.add_node("A", [0, 0, 0]); m2.add_node("B", [0, 0, L])
        m2.add_member("C", "A", "B", sec, "A554-304")
        m2.support("A", **{d: "fixed" for d in FR.DOFS})
        m2.add_case("P", nodal={"B": [0, 0, -1.0]})
        lam = m2.buckling({"P": 1})[0]
        self.assertLess(rel(lam, Pe / 4), 0.005)

    def test_pdelta_amplification(self):
        # cantilever column, axial P = 0.3 Pcr, lateral H: tip drift ~ first order / (1 - P / Pcr) (within 2 %)
        L = 100.0
        sec = SC.round_tube(3, 0.12, 1.0)
        Pcr = math.pi ** 2 * E_SS * sec.Iz / (2 * L) ** 2
        m = FR.FrameModel(10, False)
        m.add_node("A", [0, 0, 0]); m.add_node("B", [0, 0, L])
        m.add_member("C", "A", "B", sec, "A554-304")
        m.support("A", **{d: "fixed" for d in FR.DOFS})
        m.add_case("P", nodal={"B": [10.0, 0, -0.3 * Pcr]})
        d1 = m.solve({"P": 1}).disp("B")[0]
        d2 = m.solve({"P": 1}, pdelta=True).disp("B")[0]
        self.assertLess(rel(d2 / d1, 1 / (1 - 0.3)), 0.02)

    def test_modal_simple_and_cantilever(self):
        L = 120.0
        sec = SC.round_tube(3, 0.12, 1.0)
        mat = MT.get("A554-304")
        mbar = sec.A * mat.density / 386.0886
        f_ss = math.pi / 2 * math.sqrt(E_SS * sec.Iz / (mbar * L ** 4))
        m = beam_model(L, sec, divisions=20)
        m.support("A", ux="fixed", uy="fixed", uz="fixed", rx="fixed")
        m.support("B", uy="fixed", uz="fixed")
        f = m.modal(2)[0]
        self.assertLess(rel(f, f_ss), 0.01)
        f_c = 1.8751 ** 2 / (2 * math.pi) * math.sqrt(E_SS * sec.Iz / (mbar * L ** 4))
        m2 = beam_model(L, sec, divisions=20)
        m2.support("A", **{d: "fixed" for d in FR.DOFS})
        self.assertLess(rel(m2.modal(2)[0], f_c), 0.01)

    def test_local_axes_vertical_and_roll(self):
        # vertical cantilever loaded in +Y: rect 2 wide x 4 deep; with roll 90 the deep side faces Y
        sec = SC.rect_tube(2, 4, 0.12)
        for roll, I in ((0.0, sec.Iy), (90.0, sec.Iz)):
            m = FR.FrameModel(4, False)
            m.add_node("A", [0, 0, 0]); m.add_node("B", [0, 0, 50])
            m.add_member("C", "A", "B", sec, "A554-304", roll=roll)
            m.support("A", **{d: "fixed" for d in FR.DOFS})
            m.add_case("H", nodal={"B": [0, 100, 0]})
            d = m.solve({"H": 1}).disp("B")[1]
            self.assertLess(rel(d, 100 * 50 ** 3 / (3 * E_SS * I)), 1e-9)

    def test_body_load_equals_self_weight(self):
        m = beam_model()
        m.support("A", ux="fixed", uy="fixed", uz="fixed", rx="fixed")
        m.support("B", uy="fixed", uz="fixed")
        m.add_mass("B", 0.0)
        m.add_case("SW", self_weight=1.0)
        m.add_case("BD", body=[0, 0, -1])
        r1, r2 = m.solve({"SW": 1}), m.solve({"BD": 1})
        self.assertAlmostEqual(r1.reaction("A")[2], r2.reaction("A")[2], places=9)
        w = SC.round_tube(3, 0.12, 1.0).A * MT.get("A554-304").density * 120
        self.assertLess(rel(r1.reaction("A")[2] + r1.reaction("B")[2], w), 1e-9)

    def test_mechanism_is_reported(self):
        m = beam_model()
        m.support("A", uz="fixed")
        m.add_case("P", nodal={"B": [0, 0, -1]})
        with self.assertRaises(InputError):
            m.solve({"P": 1})


# ===================================================================== AISC 370 member strength
class TestMembers(unittest.TestCase):
    def test_e3_curves_continuous(self):
        for cv, (alpha, b0, b1, b2) in MB.CURVES.items():
            lo = (b0 / math.pi) ** 2
            self.assertLess(abs(1.2 * b1 ** (lo ** alpha) - 1.0), 0.002, cv)
            self.assertLess(abs(1.2 * b1 ** (3.2 ** alpha) - b2 / 3.2), 0.002 * 3, cv)

    def test_round_column_hand_calc(self):
        # A554-304 3.0 x 0.120, t_des 0.114, Lc 100 in, curve B:
        # A 1.0335, I 1.0778, r 1.0212, Lc/r 97.92, Fe 28.82 ksi, Fy/Fe 1.0409,
        # Fcr = 1.2 * 0.455^(1.0409^0.58) * 30 = 16.08 ksi, Pn 16.62 kips, ASD Pn/1.67 = 9.95 kips
        s = SC.round_tube(3.0, 0.12)
        Pc, d = MB.compression(s, MT.get("A554-304"), 100.0, 100.0, "ASD")
        self.assertEqual(d["curve"], "B")
        self.assertLess(rel(d["Fcr"], 16.08e3), 0.003)
        self.assertLess(rel(Pc, 9951.0), 0.004)

    def test_carbon_column_aisc_manual(self):
        # AISC Manual Table 4-4 HSS4x4x1/4 Fy 50, Lc 10 ft: phi Pn about 96 kips (hand: Fcr 31.7 ksi x 3.37 x 0.9)
        s = SC.rect_tube(4, 4, 0.25, t_factor=0.233 / 0.25)
        Pc, d = MB.compression(s, MT.get("A500C-rect"), 120.0, 120.0, "LRFD")
        self.assertLess(rel(Pc, 96.2e3), 0.01)

    def test_rect_classification_and_slender_flange(self):
        # 3 x 3 x 0.065 A554-304: t 0.06175, b_flat 2.753, b/t 44.6 > 1.24 sqrt(E/Fy) = 37.9: slender
        s = SC.rect_tube(3, 3, 0.065)
        cl = MB.classify(s, MT.get("A554-304"))
        self.assertEqual(cl["compression"]["class"], "slender")
        Mc, d = MB.flexure(s, MT.get("A554-304"), "z", "ASD")
        self.assertEqual(d["flange"], "slender")
        self.assertLess(d["Mn"], 30e3 * s.Sz)
        self.assertGreater(d["Mn"], 0.7 * 30e3 * s.Sz)

    def test_compact_rect_reaches_mp(self):
        s = SC.rect_tube(2, 2, 0.12)
        Mc, d = MB.flexure(s, MT.get("A554-304"), "z", "ASD")
        self.assertAlmostEqual(d["Mn"], 30e3 * s.Zz)
        self.assertAlmostEqual(Mc, 30e3 * s.Zz / 1.67)

    def test_round_noncompact_f8(self):
        # D/t between 0.08 E/Fy (74.7) and 0.31 E/Fy (289): 6 x 0.050, t 0.0475, D/t 126.3
        # Mn = (1 + 0.068 * 289.33 / 126.32) Fy S
        s = SC.round_tube(6, 0.05)
        Mc, d = MB.flexure(s, MT.get("A554-304"), "z", "ASD")
        lr = 0.31 * 28e6 / 30e3
        self.assertLess(rel(d["Mn"], min((1 + 0.068 * lr / (6 / 0.0475)) * 30e3 * s.Sz, 30e3 * s.Zz)), 1e-9)

    def test_shear_and_torsion_coefficients_continuous(self):
        E, Fy = 28e6, 30e3
        r5 = math.sqrt(5 * E / Fy)
        for x in (0.97, 2.68):
            self.assertLess(abs(MB._cv2_stainless(x * r5 * (1 - 1e-9), 5, E, Fy) -
                                MB._cv2_stainless(x * r5 * (1 + 1e-9), 5, E, Fy)), 0.005)

    def test_interaction(self):
        r, eq, _ = MB.interaction(-30, 100, 40, 100, 0, 100)
        self.assertEqual(eq, "H1-1a")
        self.assertAlmostEqual(r, 0.3 + 8 / 9 * 0.4)
        r, eq, _ = MB.interaction(-10, 100, 40, 100, 20, 100)
        self.assertEqual(eq, "H1-1b")
        self.assertAlmostEqual(r, 0.05 + 0.6)
        r, eq, _ = MB.interaction(0, 100, 50, 100, 0, 100, 10, 100, 30, 100)
        self.assertEqual(eq, "H2-1")
        self.assertAlmostEqual(r, 0.5 + (0.1 + 0.3) ** 2)


# ===================================================================== connections
class TestConnections(unittest.TestCase):
    def test_fillet_strength(self):
        # 1/4 in E308L, ASD: 0.60 x 75 ksi x 0.7071 x 0.25 / 2.00 = 3.977 kip/in
        self.assertLess(rel(CN.fillet_strength_per_in(0.25, 75e3, "ASD"), 3977.4), 1e-4)
        self.assertLess(rel(CN.fillet_strength_per_in(0.25, 75e3, "LRFD"), 5966.2), 1e-4)

    def test_weld_box_torsion(self):
        # 4 x 4 all-round weld, Mz = 10,000 lb-in: Ip = 2 (4 x 2^2) x 2 + 4 x 4^3/12 = 85.33 in^3,
        # corner r = 2.828: f = 10000 x 2.828 / 85.33 = 331.5 lb/in
        f, d = CN.weld_group(CN.box_segments(4, 4), Mz=10000)
        self.assertLess(rel(d["Ip"], 85.333), 1e-4)
        self.assertLess(rel(f, 10000 * math.sqrt(8) / 85.333), 1e-3)

    def test_weld_circle_bending(self):
        # circular line weld radius r: Sw = pi r^2; f = M / (pi r^2)
        f, d = CN.weld_group(CN.circle_segments(3.0, 360), Mx=1000)
        self.assertLess(rel(f, 1000 / (math.pi * 1.5 ** 2)), 0.002)

    def test_round_T_joint_hand(self):
        # D 3, t 0.114, Db 2, tb 0.114, Fy 30 ksi, 90 deg, chord in tension (Qf 1):
        # beta 0.667, gamma 13.16; K2-3: 389.88 x (3.1 + 6.933) x 13.16^0.2 (1.6743) = 6,549 lb nominal
        cap, d = CN.round_hss_joint(3.0, 0.114, 2.0, 0.114, 30e3, 30e3, 90, "T", 0.0, True, "ASD")
        Pn = 30e3 * 0.114 ** 2 * (3.1 + 15.6 * (2 / 3) ** 2) * (3 / 0.228) ** 0.2
        self.assertLess(rel(d["limit_states"]["chord plastification K2-3"], Pn / 1.67), 1e-9)
        self.assertLess(rel(Pn, 6549), 0.002)

    def test_j12_hand(self):
        # IOF, t 0.114, h 1.544, r 0.114, lb 3, Fy 30 ksi:
        # Rn = 779.76 x 0.96 x (1 + 2.30 x 5.130) x (1 - 0.001 x 3.680) = 748.57 x 12.799 x 0.99632 = 9,546 lb
        cap, d = CN.rect_hss_concentrated(0.114, 1.544, 0.114, 3.0, 30e3, "IOF", "ASD")
        want = 2 * 0.114 ** 2 * 30e3 * (1 - 0.04) * (1 + 2.30 * math.sqrt(3 / 0.114)) * (1 - 0.001 * math.sqrt(1.544 / 0.114))
        self.assertLess(rel(d["Rn"], want), 1e-12)
        self.assertLess(rel(want, 9546), 0.001)

    def test_bolt(self):
        # 1/2 in A193 B8 cl1 (Fu 75 ksi): Ab 0.19635; ASD shear 0.45 x 75 x 0.19635 / 2 = 3.313 kips
        self.assertLess(rel(CN.bolt_shear(0.5, 75e3, "ASD"), 3313.4), 1e-4)
        self.assertLess(rel(CN.bolt_tension(0.5, 75e3, "ASD"), 5522.3), 1e-4)


# ===================================================================== supports, stability, lifting
class TestSupportsStability(unittest.TestCase):
    def test_rigid_four_feet_eccentric(self):
        # feet at (+-a/2, +-b/2), a 100, b 40, W 1000 at (10, 5):
        # R = W/4 + W ex / (2a) sx + W ey / (2b) sy  ->  (+,+) 250 + 50 + 62.5 = 362.5
        pts = [(50, 20), (-50, 20), (-50, -20), (50, -20)]
        R, act, ok = SP.rigid_reactions(pts, [(1000, 10, 5, 0, 0, 0)])
        self.assertTrue(ok)
        self.assertAlmostEqual(R[0], 362.5)
        self.assertAlmostEqual(R[2], 137.5)

    def test_tipping_acceleration(self):
        # 40 x 40 footprint, CG at centre 50 in high: tip accel 20/50 = 0.4 g, angle atan(0.4) = 21.8 deg
        c = ST.overturning({"footprint": [[0, 0], [40, 0], [40, 40], [0, 40]], "W": 1000, "cg": [20, 20, 50],
                            "cases": [{"name": "half g", "ax": 0.5, "gravity": 1.0}], "SF_required": 1.0, "mu": 0.6})
        self.assertAlmostEqual(c.value("least tipping acceleration"), 0.4)
        self.assertAlmostEqual(c.value("least tip angle"), math.degrees(math.atan(0.4)), places=4)
        ot = [ch for ch in c.checks if "overturning" in ch.name][0]
        self.assertFalse(ot.passed)          # 0.5 g > 0.4 g tips it
        self.assertAlmostEqual(ot.ratio, 0.5 / 0.4)

    def test_seismic_bounds(self):
        c = ST.seismic_force({"edition": "7-16", "SDS": 1.0, "Wp": 1000, "Ip": 1.0, "ap": 1.0, "Rp": 2.5})
        # equation 0.4 x 1 x 1 x 1000 / 2.5 = 160 < 0.3 x 1000 = 300 -> 300
        self.assertAlmostEqual(c.value("Fp design (strength level)"), 300.0)

    def test_lug_bth1_hand(self):
        # t 0.5, Dh 1.0625, Dp 1.0, R 2.0, be 1.47, a 1.47, A240-304 (Fy 30, Fu 75 ksi), Nd 3:
        # Cr = 1 - 0.275 sqrt(1 - 1/1.12891) = 0.9012; beff = min(2.0, 1.47, 1.47*0.6*2.5*sqrt(1.0625/1.47)) = 1.47
        # Pt = 0.9012 x 75000 x 2 x 0.5 x 1.47 / 3.6 = 27,600 lb
        c = LF.lift_lug({"P": 5000, "t": 0.5, "Dh": 1.0625, "Dp": 1.0, "R": 2.0, "be": 1.47, "a": 1.47,
                         "material": "A240-304", "Nd": 3.0})
        Cr = 1 - 0.275 * math.sqrt(1 - 1 / 1.0625 ** 2)
        self.assertLess(rel(Cr, 0.9071), 1e-3)          # hand: sqrt(1 - 0.88581) = 0.33792 -> 0.90707
        self.assertLess(rel(c.value("Cr"), Cr), 1e-5)    # results are stored to 6 significant figures
        self.assertLess(rel(c.value("tension across the pinhole"), Cr * 75e3 * 2 * 0.5 * 1.47 / 3.6), 1e-5)
        self.assertLess(rel(c.value("bearing on the pin"), 1.25 * 30e3 * 1.0 * 0.5 / 3), 1e-5)

    def test_forklift_derate(self):
        c = LF.forklift({"W": 4000, "cg": [70, 20, 30], "carriage_stop": -4, "truck_capacity": 15000,
                         "rated_load_centre": 24, "tines": [9.5, 32.75], "fork_length": 96, "impact": 2.0})
        self.assertAlmostEqual(c.value("load centre (fork heel to CG)"), 74.0)
        self.assertLess(rel(c.value("derated capacity at this load centre"), 15000 * 24 / 74), 1e-5)


# ===================================================================== loads, dynamics, plates
class TestOther(unittest.TestCase):
    def test_combinations(self):
        c = LD.combinations("ASD", {"D", "F", "Eh", "Ev"})
        self.assertIn("ASD-8 0.6D-0.7Ev+0.7Eh", c)
        self.assertEqual(c["ASD-8 0.6D-0.7Ev+0.7Eh"], {"D": 0.6, "Ev": -0.7, "Eh": 0.7})
        self.assertNotIn("ASD-2 D+F+L", c)

    def test_fatigue_category_c(self):
        # AISC 370 A-3-1: 1000 (4.4 / 2e6)^0.333 = 1000 x exp(0.333 x -13.0269) = 13.07 ksi;
        # the AISC 360-16 form (44e8 / 2e6)^0.333 = 12.97 ksi agrees within 1 % (0.333 vs 1/3)
        c = DY.fatigue({"category": "C", "stress_range": 5000, "cycles": 2e6})
        self.assertLess(rel(c.value("allowable stress range FSR") / 1000, 13.07), 1e-3)
        self.assertLess(rel(c.value("allowable stress range FSR") / 1000, 2200 ** 0.333), 0.01)
        c = DY.fatigue({"category": "C", "stress_range": 5000, "cycles": 1e9})
        self.assertAlmostEqual(c.value("allowable stress range FSR"), 10000.0)   # threshold

    def test_sdof_frequency(self):
        # 0.1 in static deflection: f = sqrt(386.09 / 0.1) / 2 pi = 9.889 Hz
        c = DY.natural_frequency({"case": "static_deflection", "delta": 0.1})
        self.assertLess(rel(c.value("first natural frequency"), 9.889), 1e-3)

    def test_plate_strip_limits(self):
        q, b, t, E = 1.0, 10.0, 0.25, 28e6
        r = B.plate_uniform(q, 1e10, b, t, E, "simple")
        self.assertLess(rel(r["sigma_max"], 0.75 * q * b * b / t ** 2), 1e-3)
        self.assertLess(rel(r["defl_max"], 5 * 12 * (1 - 0.09) * q * b ** 4 / (384 * E * t ** 3)), 2e-3)
        r = B.plate_uniform(q, 1e10, b, t, E, "fixed")
        self.assertLess(rel(r["sigma_max"], 0.5 * q * b * b / t ** 2), 1e-3)

    def test_retention_at_200F(self):
        m = MT.get("A554-304", 200)
        self.assertAlmostEqual(m.Fy, 30e3 * 0.80)
        self.assertAlmostEqual(m.E, 28e6 * 0.96)


if __name__ == "__main__":
    unittest.main()
