"""Unit tests for harness/checks/sanitary_routing.py: the model's slope and dead leg rows read as PASS, FAIL,
KNOWN or N/A, and the project's accepted findings applied to them.

The measuring is the model's own (skidlib reports.routing_rows) and is not tested here; these tests give the check
rows in the form the model writes them. Stdlib unittest only:

    .\\harness\\tools\\venv\\Scripts\\python.exe -m unittest discover -s harness\\tests -v
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO = next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists())
sys.path.insert(0, str(REPO / "harness" / "lib"))
sys.path.insert(0, str(REPO / "harness" / "checks"))
import accepted_findings as AF  # noqa: E402
import sanitary_routing as SR  # noqa: E402


def row(check, obj, value, result):
    return {"check": check, "object": obj, "line_no": "L-T", "value": value, "limit": "limit", "result": result,
            "length_in": "1.00", "direction": "falls"}


ROWS = [row("slope", "L-T-SP01 run 1", "0.1250 in/ft", "ok"),
        row("slope", "L-T-SP01 run 2", "0.0000 in/ft", "BELOW"),
        row("slope", "L-U-SP01 run 1", "0.0000 in/ft", "n/a utility"),
        row("slope (eccentric reducer invert)", "L-T-SP02.pc03 reducer, FSD", "invert 0.2 in/ft", "ok"),
        row("dead leg", "tee A", "L 4.75 in, D 1.870 in, L/D 2.54", "EXCEEDS"),
        row("dead leg", "tee B", "L 1.00 in, D 1.870 in, L/D 0.53", "ok"),
        row("dead leg", "tee C", "L 9.00 in to the branch face, D 1.870 in", "n/a drain line"),
        row("dead leg", "tee D", "L 3.00 in, D 1.870 in, L/D 1.60", "UNRESOLVED"),
        row("dead leg", "tee E", "L 5.00 in, D 1.870 in, L/D 2.67", "accepted in the model source (test)")]


class Status(unittest.TestCase):
    def test_the_models_words(self):
        for text, want in (("ok", SR.PASS), ("n/a utility", SR.NA), ("n/a plant water", SR.NA),
                           ("BELOW", SR.FAIL), ("EXCEEDS", SR.FAIL), ("UNRESOLVED", SR.FAIL),
                           ("accepted (DEC-nnnn)", SR.KNOWN), ("", SR.KNOWN)):
            self.assertEqual(SR.status_of(text), want, text)


class Classify(unittest.TestCase):
    def test_nothing_accepted(self):
        rows, stale = SR.classify(ROWS)
        self.assertEqual([r["status"] for r in rows],
                         [SR.PASS, SR.FAIL, SR.NA, SR.PASS, SR.FAIL, SR.PASS, SR.NA, SR.FAIL, SR.KNOWN])
        self.assertEqual(stale, [])
        self.assertIn("model record", rows[-1]["record"])
        head = SR.summary(rows, "the test model")
        self.assertTrue(head.startswith("sanitary_routing: FAIL - 3 finding(s)"), head)
        self.assertIn("4 slope rows (2 pass, 1 fail, 1 n/a)", head)
        self.assertIn("5 dead leg rows (1 pass, 2 fail, 1 known, 1 n/a)", head)

    def test_an_accepted_finding_is_known_until_its_value_changes(self):
        acc = {("tee A", "L 4.75 in, D 1.870 in, L/D 2.54"): "kept for now (Bob, chat, test)"}
        rows, stale = SR.classify(ROWS, acc)
        a = next(r for r in rows if r["object"] == "tee A")
        self.assertEqual((a["status"], a["record"]), (SR.KNOWN, "kept for now (Bob, chat, test)"))
        self.assertEqual(stale, [])
        changed = [dict(r, value="L 5.00 in, D 1.870 in, L/D 2.67") if r["object"] == "tee A" else r for r in ROWS]
        rows, stale = SR.classify(changed, acc)
        self.assertEqual(next(r for r in rows if r["object"] == "tee A")["status"], SR.FAIL)
        self.assertEqual(stale, list(acc))

    def test_all_clear_passes(self):
        rows, _ = SR.classify([r for r in ROWS if r["result"] in ("ok", "n/a utility")])
        self.assertTrue(SR.summary(rows, "the test model").startswith("sanitary_routing: PASS - "))

    def test_report(self):
        rows, _ = SR.classify(ROWS)
        p = SR.write_report(rows, Path(tempfile.mkdtemp(prefix="sanrouting-")))
        lines = p.read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines[0].split(","), SR.FIELDS)
        self.assertEqual(len(lines), len(ROWS) + 1)


class Accepted(unittest.TestCase):
    def _file(self, text):
        p = Path(tempfile.mkdtemp(prefix="accepted-")) / AF.NAME
        p.write_text(text, encoding="utf-8")
        return p

    def test_section_is_read(self):
        d = AF.load(self._file('sanitary_routing:\n  - object: "tee A"\n    value: "L/D 2.54"\n'
                               '    record: "kept (Bob, chat, test)"\n'))
        self.assertEqual(AF.sanitary_routing(d), {("tee A", "L/D 2.54"): "kept (Bob, chat, test)"})
        self.assertEqual(AF.sanitary_routing({}), {})

    def test_faults_are_refused(self):
        for text, part in (('sanitary_routing:\n  - object: "tee A"\n    record: x\n', "no value"),
                           ('sanitary_routing:\n  - value: "v"\n    record: x\n', "no object"),
                           ('sanitary_routing:\n  - object: "tee A"\n    value: "v"\n', "no record"),
                           ("sanitary_routing: {}\n", None), ("sanitary_routing: yes\n", "not a list")):
            if part is None:
                self.assertEqual(AF.sanitary_routing(AF.load(self._file(text))), {})
                continue
            with self.assertRaises(ValueError) as cm:
                AF.load(self._file(text))
            self.assertIn(part, str(cm.exception), text)


if __name__ == "__main__":
    unittest.main()
