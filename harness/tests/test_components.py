"""Unit tests for harness/lib/components.py (the job and project component registers and libraries) and
harness/checks/component_register.py (the register check), on scratch libraries. Stdlib unittest only:

    .\\harness\\tools\\venv\\Scripts\\python.exe -m unittest discover -s harness\\tests -v
"""
from __future__ import annotations

import contextlib
import csv
import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists())
sys.path.insert(0, str(REPO / "harness" / "lib"))
sys.path.insert(0, str(REPO / "harness" / "checks"))
import repo_paths as rp  # noqa: E402
import components as C  # noqa: E402
import component_register as CR  # noqa: E402

CUT = b"%PDF-1.4 test cut sheet\n"
STEP = b"ISO-10303-21; test vendor step\n"


def write_register(path: Path, rows: list[dict], header=C.COLUMNS) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(header), extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in header})


def row(cid="COMP-0001", rev="A", status="current", **kw) -> dict:
    return {"component_id": cid, "revision": rev, "status": status, **kw}


class Scratch(unittest.TestCase):
    """Two scratch libraries, job and project, in a temporary folder."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.job = C.Library("job", self.root / "job", self.root / "job" / "component-register.csv")
        self.prj = C.Library("project", self.root / "prj", self.root / "prj" / "component-register.csv")
        self.libs = [self.job, self.prj]

    def tearDown(self):
        self._tmp.cleanup()

    def part(self, lib: C.Library, folder: str, sub: str, name: str, data: bytes) -> Path:
        p = lib.root / folder / sub / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return p


class Reader(Scratch):
    def test_rows_job_first_and_current(self):
        write_register(self.job.register, [row("COMP-0001", "A", "superseded", weight_lb="3"),
                                           row("COMP-0001", "B", "current", weight_lb="4",
                                               manufacturer="ifm", model="TD2947 x")])
        write_register(self.prj.register, [row("COMP-0002", "A", "current", weight_lb="unknown",
                                               cut_sheet_obtained_on="2026-10-20",
                                               vendor_step_obtained_on="2026-10-25T09:00")])
        rs = C.rows(self.libs)
        self.assertEqual([(r["component_id"], r["_library"]) for r in rs],
                         [("COMP-0001", "job"), ("COMP-0001", "job"), ("COMP-0002", "project")])
        self.assertEqual([r["revision"] for r in C.current_rows(self.libs)], ["B", "A"])
        self.assertEqual(C.obtained_on(rs[2]), "2026-10-25")
        self.assertEqual(C.obtained_on(rs[0]), "")
        w = C.weights(self.libs)
        self.assertEqual(w["COMP-0001"][0], 4.0)                 # the current revision, not the superseded one
        self.assertNotIn("COMP-0002", w)                         # unknown is not a weight
        self.assertIn(("ifm", "TD2947 x"), C.vendor_names(self.libs))

    def test_missing_registers_are_empty(self):
        self.assertEqual(C.rows(self.libs), [])
        self.assertEqual(C.read_register(self.job.register), ([], []))

    def test_resolve(self):
        r = {"_root": self.job.root}
        self.assertEqual(C.resolve(r, "COMP-0001_ifm_TD2947/01_Cut_Sheet/a.pdf"),
                         self.job.root / "COMP-0001_ifm_TD2947" / "01_Cut_Sheet" / "a.pdf")
        self.assertEqual(C.resolve(r, "job/components/x.step"), rp.REPO / "job" / "components" / "x.step")
        self.assertIsNone(C.resolve(r, "unknown"))
        self.assertIsNone(C.resolve(r, " "))

    def test_step_files_order_and_find(self):
        cpme = self.part(self.job, "COMP-0001_ifm_TD2947", "03_STEP_CPME", "COMP-0001-TT-ifm-TD2947-RevA.step", STEP)
        vend = self.part(self.job, "COMP-0001_ifm_TD2947", "02_STEP_Vendor", "TD2947.STP", STEP)
        src = self.part(self.job, "COMP-0001_ifm_TD2947", "src", "out/own.step", STEP)
        self.part(self.job, "COMP-0001_ifm_TD2947", "01_Cut_Sheet", "TD2947.pdf", CUT)
        self.part(self.job, "notes", "02_STEP_Vendor", "stray.step", STEP)          # not a COMP-nnnn_ folder
        same = self.part(self.prj, "COMP-0002_Acme_X1", "02_STEP_Vendor", "TD2947.STP", STEP)
        self.assertEqual(C.step_files(self.libs), [cpme, vend, src, same])
        self.assertEqual(C.find_step("TD2947.STP", self.libs), vend)               # job library first
        self.assertIsNone(C.find_step("nope.step", self.libs))

    def test_real_libraries_named_by_repo_paths(self):
        self.assertEqual([lib.level for lib in C.libraries()], ["job", "project"] if rp.HAS_PROJECT else ["job"])
        self.assertEqual(C.libraries()[0].register, rp.JOB_COMPONENT_REGISTER)
        if rp.HAS_PROJECT:
            self.assertEqual(C.libraries()[1].register, rp.COMPONENT_REGISTER)
        header, _ = C.read_register(rp.JOB_COMPONENT_REGISTER)
        self.assertEqual(tuple(header), C.COLUMNS)                               # the register's header is the spec


class Check(Scratch):
    def test_empty_registers_pass(self):
        write_register(self.job.register, [])
        write_register(self.prj.register, [])
        self.assertEqual(CR.findings(self.libs), (0, 0, []))

    def test_good_row_passes(self):
        cut = self.part(self.job, "COMP-0001_ifm_TD2947", "01_Cut_Sheet", "TD2947.pdf", CUT)
        vend = self.part(self.job, "COMP-0001_ifm_TD2947", "02_STEP_Vendor", "TD2947.stp", STEP)
        cpme = self.job.root / "COMP-0001_ifm_TD2947" / "03_STEP_CPME" / "COMP-0001-TT-RevA.step"
        cpme.parent.mkdir(parents=True)
        sha = hashlib.sha256(STEP).hexdigest()
        (cpme.parent / (cpme.name + ".drive")).write_text(json.dumps({"path": "x", "bytes": 1, "sha256": sha}),
                                                          encoding="utf-8")   # held in the Drive store only
        write_register(self.job.register, [row(
            cut_sheet_file=cut.relative_to(self.job.root).as_posix(),
            vendor_step_file=vend.relative_to(self.job.root).as_posix(), vendor_step_sha256=sha,
            cpme_step_file=cpme.relative_to(self.job.root).as_posix(), cpme_step_sha256=sha.upper())])
        write_register(self.prj.register, [])
        self.assertEqual(CR.findings(self.libs), (1, 1, []))

    def test_findings(self):
        self.part(self.job, "COMP-0001_ifm_TD2947", "02_STEP_Vendor", "TD2947.stp", STEP)
        self.part(self.job, "COMP-0009_Acme_X", "01_Cut_Sheet", "x.pdf", CUT)       # folder with no row
        write_register(self.job.register, [
            row("COMP-0001", "A", "current", vendor_step_file="COMP-0001_ifm_TD2947/02_STEP_Vendor/TD2947.stp",
                vendor_step_sha256="0" * 64, cut_sheet_file="COMP-0001_ifm_TD2947/01_Cut_Sheet/gone.pdf"),
            row("COMP-0001", "A", "current"),                      # same id + revision; second current row
            row("COMP-02", "A", "draft"),                          # not COMP-nnnn, bad status
            row("COMP-0003", "", "superseded"),
        ])
        write_register(self.prj.register, [row("COMP-0003", "B", "current")], header=C.COLUMNS[:-1])
        n, dirs, out = CR.findings(self.libs)
        text = "\n".join(out)
        self.assertEqual((n, dirs), (5, 2))
        for want in ("sha256 differs from vendor_step_sha256", "gone.pdf not found", "COMP-0001 rev A has 2 rows",
                     "COMP-0001 has 2 current rows", "component_id is not COMP-nnnn", "status 'draft'",
                     "revision blank", "COMP-0003 is in both the job and the project register",
                     "COMP-0009_Acme_X: folder has no row", "header lacks notes"):
            self.assertIn(want, text)

    def test_missing_register_reported(self):
        write_register(self.job.register, [])
        out = CR.findings(self.libs)[2]
        self.assertEqual(len(out), 1)
        self.assertIn("register missing", out[0])

    def test_main_exit_codes(self):
        buf = io.StringIO()
        with mock.patch.object(CR, "findings", return_value=(0, 0, [])), contextlib.redirect_stdout(buf):
            self.assertEqual(CR.main(), 0)
        self.assertTrue(buf.getvalue().startswith("component_register: PASS"))
        buf = io.StringIO()
        with mock.patch.object(CR, "findings", return_value=(1, 0, ["x"])), contextlib.redirect_stdout(buf):
            self.assertEqual(CR.main(), 1)
        self.assertTrue(buf.getvalue().startswith("component_register: FAIL"))
        buf = io.StringIO()
        with mock.patch.object(CR, "findings", side_effect=csv.Error("bad")), contextlib.redirect_stdout(buf):
            self.assertEqual(CR.main(), 3)
        self.assertTrue(buf.getvalue().startswith("component_register: ERROR"))


class Preflight(Scratch):
    def test_unplaced_components_reads_both_registers(self):
        import accept_preflight as AP
        write_register(self.job.register, [row("COMP-0001", cut_sheet_obtained_on="2026-10-20", description="in"),
                                           row("COMP-0002", cut_sheet_obtained_on="2026-10-01", description="old")])
        write_register(self.prj.register, [row("COMP-0003", vendor_step_obtained_on="2026-10-21",
                                               description="one-off adapter")])
        build = self.root / "build"
        build.mkdir()
        (build / "bom-model.csv").write_text("item,component\n1,COMP-0001\n", encoding="utf-8")
        with mock.patch.object(C, "libraries", return_value=self.libs):
            out = AP.unplaced_components(build, "2026-10-10")
        self.assertEqual([i["key"] for i in out], ["component:COMP-0003"])
        self.assertIn("project library", out[0]["text"])


if __name__ == "__main__":
    unittest.main()
