"""Pass 3: regression tests for CPM-190 findings not covered by tests/test_review_pass3.py."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from skidframe import design, lifting                 # noqa: E402
from skidframe import frame as FR                     # noqa: E402
from skidframe import sections as SC                  # noqa: E402
from skidframe.core import InputError                 # noqa: E402


def _beam(method):
    return {"method": method, "options": {"divisions": 4},
            "nodes": {"A": [0, 0, 0], "B": [96, 0, 0]},
            "members": [{"id": "M", "i": "A", "j": "B", "section": {"shape": "round", "D": 3, "t": 0.12},
                         "material": "A554-304"}],
            "supports": {"A": {"ux": "fixed", "uy": "fixed", "uz": "fixed", "rx": "fixed"},
                         "B": {"uy": "fixed", "uz": "fixed"}},
            "cases": {"D": {"self_weight": 1.0}, "F": {"member_point": [{"member": "M", "at": 0.5, "P": [0, 0, -800]}]}}}


class TestPass3Fixes(unittest.TestCase):
    def test_F10_lrfd_checks_deflection_on_service_loads(self):
        c = design.frame_check(_beam("LRFD"))
        dch = [ch for ch in c.checks if ch.name == "M deflection"]
        self.assertTrue(dch, "LRFD run must still check deflection")
        a = design.frame_check(_beam("ASD"))
        # the same service load (D + F unfactored) in both methods gives the same deflection ratio
        self.assertAlmostEqual(dch[0].ratio, [ch for ch in a.checks if ch.name == "M deflection"][0].ratio, places=6)

    def test_F09_lift_runs_under_auto(self):
        d = _beam("ASD")
        d["cases"]["LIFT"] = {"body": [0, 0, -2.0]}
        c = design.frame_check(d)
        self.assertTrue(any("LIFT" in r[0] for r in c.tables["member results by combination"]["rows"]))

    def test_N2_sling_cg_outside_lugs(self):
        with self.assertRaises(InputError):
            lifting.slings({"W": 1000, "cg": [150, 0], "lugs": [[0, 0], [100, 0]], "angle_deg": 60})

    def test_N7_square_bar_J(self):
        # Roark Table 10.7: square bar K = 0.1406 a^4
        s = SC.solid_square(1.0)
        self.assertAlmostEqual(s.J, 0.1406, places=3)

    def test_F07_near_vertical_axes_continuous(self):
        # a post tilted 0.02 deg must keep local y close to global +X, like an exactly vertical post
        R, _ = FR.rotation([0, 0, 0], [0, 0.01, 30])
        self.assertGreater(R[1][0], 0.999)


if __name__ == "__main__":
    unittest.main()
