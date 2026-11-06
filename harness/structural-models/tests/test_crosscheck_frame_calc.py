"""O-10: cross-check against the project's earlier frame calculation (job/data/frame-calc.md, calc Rev G on
model Rev AA, report Rev H).

The earlier calc and skidframe share the section (3.0 OD x 0.120 rails) but not the strength basis:
- earlier: elastic allowable 0.6 Fy on S with the nominal wall (FC-03), torsion at 0.4 Fy shear (FC-30),
  combined as M / (0.6 Fy S) + (T / Tc)^2;
- skidframe: AISC 370-21 F8 (compact round: Mn = Fy Z, Omega 1.67) on the design wall 0.95 t (B4.2b),
  G8.1 torsion 0.6 Cv Fy C / 1.67, H1/H2 interaction.
These tests pin the conversion between the two, so a reader of the old report can see how its ratios move.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from skidframe import materials as MT     # noqa: E402
from skidframe import members as MB       # noqa: E402
from skidframe import sections as SC      # noqa: E402


def rel(a, b):
    return abs(a - b) / max(abs(b), 1e-12)


class TestCrossCheckOldFrameCalc(unittest.TestCase):
    def test_section_matches_old_calc(self):
        # frame-calc.md Rev G: 3.0 x 0.120: A 1.086 in2, I 1.128 in4, S 0.752 in3, J 2.255 in4 (nominal wall)
        s = SC.round_tube(3.0, 0.12, t_factor=1.0)
        for got, want in ((s.A, 1.086), (s.Iz, 1.128), (s.Sz, 0.752), (s.J, 2.255)):
            self.assertLess(rel(got, want), 0.001)

    def test_flexure_basis_ratio(self):
        # old allowable moment: 0.6 x 30,000 x 0.75176 = 13,532 lb-in
        # new: t 0.114, Z = (27 - 2.772^3) / 6 = (27 - 21.300) / 6 = 0.9500 in3; D/t 26.3 < 0.08 E/Fy = 74.7
        # (compact): Mc = 30,000 x 0.9500 / 1.67 = 17,066 lb-in -> 1.261 x the old allowable.
        # An old bending-only ratio R becomes about R / 1.261 (e.g. the Rev G lift 3.39 -> 2.69: still fails).
        old = 0.6 * 30e3 * SC.round_tube(3.0, 0.12, 1.0).Sz
        new, _ = MB.flexure(SC.round_tube(3.0, 0.12), MT.get("A554-304"), "z", "ASD")
        self.assertLess(rel(old, 13532), 1e-3)
        self.assertLess(rel(new, 17066), 1e-3)
        self.assertLess(rel(new / old, 1.261), 1e-3)

    def test_torsion_basis_ratio(self):
        # old Tc (FC-30) at 0.4 Fy shear on the nominal wall: 0.4 x 30,000 x J / (D/2) = 12,000 x 2.2553 / 1.5 = 18,042
        # new, rail 100 in long: C = pi (3 - 0.114)^2 x 0.114 / 2 = 1.4914; CvL 0.9617 (G8-8, pass 2 hand calc);
        # Tc = 0.6 x 0.9617 x 30,000 x 1.4914 / 1.67 = 15,460 lb-in -> 0.857 x the old value (new is stricter).
        old = 0.4 * 30e3 * SC.round_tube(3.0, 0.12, 1.0).J / 1.5
        new, d = MB.torsion(SC.round_tube(3.0, 0.12), MT.get("A554-304"), "ASD", 100.0)
        self.assertLess(rel(old, 18042), 1e-3)
        self.assertLess(rel(new, 15460), 1e-3)


if __name__ == "__main__":
    unittest.main()
