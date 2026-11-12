"""Unit tests for harness/lib/accepted_findings.py: a project's accepted findings, read by the checks.

Bob, chat, 2026-11-10: accepted findings go in a per-project file the master's checks read. Scratch files only; the
active project's own file is checked for faults when there is one. Stdlib unittest only:

    .\\harness\\tools\\venv\\Scripts\\python.exe -m unittest discover -s harness\\tests -v
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO = next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists())
sys.path.insert(0, str(REPO / "harness" / "lib"))
import accepted_findings as AF  # noqa: E402

GOOD = """interference:
  - between: [TK-A, TK-B]
    record: "tanks butt (Bob, chat, test)"
pipe_supports:
  zone:
    components: [FT-T, CV-T]
    record: "carried by the bypass line (Bob, chat, test)"
  on_nozzle: "carried by the nozzle (Bob, chat, test)"
  named:
    STR-T: "no tube for a hanger (Bob, chat, test)"
  clearance:
    "L-T tail support": "tube too short (Bob, chat, test)"
"""


def scratch(text: str) -> Path:
    d = Path(tempfile.mkdtemp(prefix="accepted-"))
    p = d / AF.NAME
    p.write_text(text, encoding="utf-8")
    return p


class Load(unittest.TestCase):
    def test_missing_file_accepts_nothing(self):
        d = AF.load(Path(tempfile.mkdtemp(prefix="accepted-")) / AF.NAME)
        self.assertEqual(d, {})
        self.assertEqual(AF.interference_pairs(d), {})
        ps = AF.pipe_supports(d)
        self.assertEqual(ps["zone"], {"comps": set(), "why": ""})
        self.assertIsNone(ps["on_nozzle"])
        self.assertIsNone(ps["tie_in"])
        for k in AF.PS_MAPS:
            self.assertEqual(ps[k], {})

    def test_good_file(self):
        d = AF.load(scratch(GOOD))
        self.assertEqual(AF.interference_pairs(d), {frozenset({"TK-A", "TK-B"}): "tanks butt (Bob, chat, test)"})
        ps = AF.pipe_supports(d)
        self.assertEqual(ps["zone"]["comps"], {"FT-T", "CV-T"})
        self.assertIn("bypass line", ps["zone"]["why"])
        self.assertIn("nozzle", ps["on_nozzle"])
        self.assertIsNone(ps["tie_in"])
        self.assertEqual(list(ps["named"]), ["STR-T"])
        self.assertEqual(ps["elbow"], {})
        self.assertEqual(list(ps["clearance"]), ["L-T tail support"])

    def test_faults_are_refused(self):
        for text, part in (("- a list\n", "not a mapping"),
                           ("sanitary: {}\n", "unknown section"),
                           ("interference:\n  - between: [TK-A]\n    record: x\n", "two owner names"),
                           ("interference:\n  - between: [TK-A, TK-B]\n", "no record"),
                           ("pipe_supports:\n  named:\n    STR-T: \"\"\n", "no record"),
                           ("pipe_supports:\n  zone: {components: [FT-T]}\n", "zone"),
                           ("pipe_supports:\n  hangers: {}\n", "unknown key"),
                           ("interference: [\n", "could not be read")):
            with self.assertRaises(ValueError) as cm:
                AF.load(scratch(text))
            self.assertIn(part, str(cm.exception), text)

    def test_the_projects_own_file_has_no_fault(self):
        """The checks read the active project's file at import; a fault there makes them exit 3."""
        p = AF.path()
        if p is None or not p.is_file():
            self.skipTest("the project has no accepted-findings.yaml")
        AF.load(p)      # raises on a fault


if __name__ == "__main__":
    unittest.main()
