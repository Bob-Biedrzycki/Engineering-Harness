"""End-to-end checks of the model functions against hand calculations, and every example through the CLI.

Each hand calculation is written out in the comment so a reviewer can redo it with a calculator.
"""
from __future__ import annotations

import io
import math
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

from skidframe import __main__ as CLI                 # noqa: E402
from skidframe import design, local, supports         # noqa: E402
from skidframe.catalog import MODELS                  # noqa: E402


def rel(a, b):
    return abs(a - b) / max(abs(b), 1e-12)


class TestHandChecks(unittest.TestCase):
    def test_leveling_foot_stud(self):
        # 3/4-10 UNC stud: minor d = 0.75 - 1.2269/10 = 0.62731; A = 0.30906; r = 0.15683; Lc = 2.1 x 2.5 = 5.25
        # Lc/r 33.48; Fe = pi^2 28e6 / 1120.9 = 246.5 ksi; Fy/Fe 0.12168; curve A inelastic:
        # Fcr = 1.2 x 0.409^(0.12168^0.56 = 0.30740) x 30 = 27.35 ksi; Pc = 8,452 / 1.67 = 5,061 lb
        # Z = d^3/6 = 0.041142; Mc = 30,000 x 0.041142 / 1.67 = 739.1 lb-in; M = 300 x 2.5 = 750
        # H1-1a: 2200/5061 + 8/9 x 750/739.1 = 0.4347 + 0.9020 = 1.337
        c = supports.leveling_foot({"R": 2200, "H": 300, "rated_load": 4500, "stud_d": 0.75, "exposed": 2.5,
                                    "stud_material": "A276-304", "pad_d": 3.5, "mu": 0.3, "method": "ASD"})
        r = [ch for ch in c.checks if ch.name == "stud axial + bending"][0].ratio
        self.assertLess(rel(r, 1.337), 0.002)

    def test_rect_branch_joint(self):
        # chord 3x3x0.120 (t 0.114), branch 2x2: beta = eta = 0.6667; Qf = min(1, 1.3 - 0.4 x 0.4 / 0.6667) = 1
        # Pn = 30000 x 0.012996 x (2 x 0.6667/0.3333 + 4/sqrt(0.3333)) = 389.88 x 10.928 = 4,260.6; /1.5 = 2,840
        # Mip = 389.88 x 2 x (0.75 + 3.4641 + 2.0) = 4,845.4; /1.5 = 3,230
        # 1500/2840 + 2000/3230 = 0.5281 + 0.6192 = 1.147
        c = local.hss_joint({"type": "rect_branch", "material": "A554-304", "chord": {"B": 3, "H": 3, "t": 0.12},
                             "branch": {"B": 2, "H": 2, "t": 0.12}, "Pr": 1500, "Mr_ip": 2000, "chord_U": 0.4,
                             "method": "ASD"})
        r = [ch for ch in c.checks if ch.name == "combined P + Mip + Mop"][0].ratio
        self.assertLess(rel(r, 1.147), 0.002)

    def test_beam_closed_form_flexure(self):
        # 2x2x0.120 (t 0.114, r_out 0.228), compact; SS 42 in, P 1200 at mid: M = 12,600 + self weight
        # w = A x 0.2894 lb/in; M_sw = w 42^2 / 8; Mc = 30,000 Z / 1.67
        c = design.beam({"case": "ss_point", "section": {"shape": "square", "b": 2.0, "t": 0.12},
                         "material": "A554-304", "method": "ASD", "L": 42, "P": 1200, "a": 21})
        from skidframe import sections as S
        s = S.rect_tube(2, 2, 0.12)
        M = 1200 * 42 / 4 + s.A * 500 / 1728 * 42 ** 2 / 8
        want = M / (30000 * s.Zz / 1.67)
        r = [ch for ch in c.checks if ch.name == "flexure"][0].ratio
        self.assertLess(rel(r, want), 1e-5)

    def test_support_reactions_equal_feet(self):
        # 4 feet at a 100 x 40 rectangle, 4000 lb at the centre: 1000 each; one foot loose: the diagonal pair
        # carries it (rigid base on 3 supports): opposite corner 0, the other two 2000 each
        c = supports.support_reactions({"supports": [{"x": 0, "y": 0}, {"x": 100, "y": 0}, {"x": 100, "y": 40},
                                                     {"x": 0, "y": 40}],
                                        "loads": [{"W": 4000, "x": 50, "y": 20}]})
        self.assertAlmostEqual(c.value("max reaction"), 1000.0, places=3)
        self.assertAlmostEqual(c.value("max reaction, one support loose"), 2000.0, places=3)


class TestExamplesRun(unittest.TestCase):
    def test_every_example_runs(self):
        ex = sorted((HERE / "examples").glob("*.yaml"))
        self.assertGreaterEqual(len(ex), len(MODELS))
        covered = set()
        for f in ex:
            model = "frame_check" if f.stem.startswith("frame_check") else f.stem
            self.assertIn(model, MODELS, f.name)
            covered.add(model)
            buf = io.StringIO()
            with redirect_stdout(buf), redirect_stderr(buf):
                code = CLI.main(["check", model, str(f), "--quiet"])
            self.assertIn(code, (0, 1), f"{f.name}: {buf.getvalue()}")
        self.assertEqual(covered, set(MODELS), "every model has an example")


if __name__ == "__main__":
    unittest.main()
