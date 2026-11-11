"""Unit test for the untagged kinds of harness/checks/pid_consistency.py (shared with harness/lib/list_delta.py).

Bob, chat, 2026-11-10: leveling feet have no relation to the P&ID. A "foot" item is frame hardware: it is not
compared with the P&ID lists, and with no naming rule for feet any id is accepted. Stdlib unittest only:

    .\\harness\\tools\\venv\\Scripts\\python.exe -m unittest discover -s harness\\tests -v
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

REPO = next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists())
sys.path.insert(0, str(REPO / "harness" / "lib"))
sys.path.insert(0, str(REPO / "harness" / "checks"))
import pid_consistency as PC  # noqa: E402


class UntaggedKinds(unittest.TestCase):
    def test_feet_are_untagged_hardware_with_any_id(self):
        self.assertIn("foot", PC.UNTAGGED_KINDS)
        for tag in ("FT-01", "FT-12", "FOOT-3", ""):
            self.assertTrue(re.match(PC.UNTAGGED_KINDS["foot"], tag), tag)

    def test_named_hardware_keeps_its_pattern(self):
        self.assertTrue(re.match(PC.UNTAGGED_KINDS["frame"], "FM-001"))
        self.assertFalse(re.match(PC.UNTAGGED_KINDS["frame"], "FT-01"))
        self.assertFalse(re.match(PC.UNTAGGED_KINDS["support"], "PS-1"))


if __name__ == "__main__":
    unittest.main()
