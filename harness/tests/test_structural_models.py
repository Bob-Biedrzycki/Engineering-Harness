"""Runs the skid frame structural suite's own verification tests (harness/structural-models/tests) as part of the
harness tests, so CI checks it in every job repo and in the Engineering Harness master.

The suite's tests import its package from their own folder, so they run in a child interpreter from
harness/structural-models, exactly as its README says:

    .\\harness\\tools\\venv\\Scripts\\python.exe -m unittest harness.tests.test_structural_models -v
"""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

REPO = next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists())
SUITE = REPO / "harness" / "structural-models"


class TestStructuralModels(unittest.TestCase):
    def test_suite_verification_passes(self):
        self.assertTrue((SUITE / "tests").is_dir(), f"{SUITE / 'tests'} is missing")
        p = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"], cwd=SUITE,
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
        tail = "\n".join((p.stdout + p.stderr).strip().splitlines()[-40:])
        self.assertEqual(p.returncode, 0, f"skidframe tests failed:\n{tail}")
        self.assertIn("OK", tail)


if __name__ == "__main__":
    unittest.main()
