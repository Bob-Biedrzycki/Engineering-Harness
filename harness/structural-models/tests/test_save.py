"""The project-level save (skidframe/save.py): a run is saved only with its use notes, into the project's
06_Mechanical_Structural/Frame_Calcs, with a log row, and a saved record is never overwritten."""
from __future__ import annotations

import csv
import io
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

from skidframe import __main__ as CLI  # noqa: E402

NOTES = ("name: base check\npurpose: test of the save step\ninputs_source: examples/beam.yaml (illustrative)\n"
         "run_by: test_save\n")


class TestSave(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.project = self.tmp / "Project-0000-00-TST-001"
        (self.project / "02_Engineering").mkdir(parents=True)
        self.inputs = self.tmp / "beam.yaml"
        self.inputs.write_text(NOTES + (HERE / "examples" / "beam.yaml").read_text(encoding="utf-8"),
                               encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _cli(self, *args):
        buf = io.StringIO()
        with redirect_stdout(buf), redirect_stderr(buf):
            code = CLI.main(list(args))
        return code, buf.getvalue()

    def test_run_saves_record_and_log(self):
        code, out = self._cli("run", "beam", str(self.inputs), "--quiet", "--project", str(self.project))
        self.assertIn(code, (0, 1), out)
        recs = list((self.project / "02_Engineering" / "06_Mechanical_Structural" / "Frame_Calcs").iterdir())
        self.assertEqual(len(recs), 1)
        rec = recs[0]
        self.assertTrue(rec.name.endswith("_beam_base-check"))
        md = (rec / "base-check.md").read_text(encoding="utf-8")
        self.assertIn("## Use notes", md)
        self.assertIn("test of the save step", md)
        self.assertTrue((rec / "inputs.yaml").exists() and (rec / "result.json").exists())
        log = self.project / "02_Engineering" / "11_Scripts_Models" / "frame-calc-log.csv"
        with log.open(encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["model"], "beam")
        self.assertEqual(rows[0]["run_by"], "test_save")

    def test_second_run_never_overwrites(self):
        self._cli("run", "beam", str(self.inputs), "--quiet", "--project", str(self.project))
        self._cli("run", "beam", str(self.inputs), "--quiet", "--project", str(self.project))
        recs = sorted(p.name for p in (self.project / "02_Engineering" / "06_Mechanical_Structural"
                                       / "Frame_Calcs").iterdir())
        self.assertEqual(len(recs), 2)
        self.assertTrue(recs[1].endswith("-2"))

    def test_run_without_notes_is_refused(self):
        code, out = self._cli("run", "beam", str(HERE / "examples" / "beam.yaml"), "--quiet",
                              "--project", str(self.project))
        self.assertEqual(code, 2)
        self.assertIn("use notes", out)
        self.assertFalse((self.project / "02_Engineering" / "06_Mechanical_Structural").exists())

    def test_check_with_notes_saves_nothing(self):
        code, out = self._cli("check", "beam", str(self.inputs), "--quiet")
        self.assertIn(code, (0, 1), out)
        self.assertFalse((self.project / "02_Engineering" / "06_Mechanical_Structural").exists())


if __name__ == "__main__":
    unittest.main()
