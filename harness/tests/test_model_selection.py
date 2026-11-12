"""Unit tests for model selection by ID (harness/lib/repo_paths.py, model_build.py; Linear CPM-155).

Generic: a scratch job-level models folder (CPME_JOB_MODELS_ROOT) holds a model folder with its model.yaml; repo_paths
resolves in a fresh interpreter each time, because it resolves at import. Also the envelope check's rule reader and
pipe_supports' not-checked report. Stdlib unittest only:

    .\\harness\\tools\\venv\\Scripts\\python.exe -m unittest discover -s harness\\tests -v
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists())
sys.path.insert(0, str(REPO / "harness" / "lib"))
sys.path.insert(0, str(REPO / "harness" / "checks"))
import repo_paths as rp  # noqa: E402

PROBE = r"""
import json, sys
sys.path.insert(0, {lib!r})
import repo_paths as rp
import model_build as mb
out = {{"level": rp.MODEL_LEVEL, "argv": sys.argv[1:]}}
if rp.HAS_MODEL:
    out.update(model=rp.SKID_MODEL_ID, cfg=rp.MODEL_CONFIG, doc=rp.MODEL_DOC_ID, src=str(rp.SKID_MODEL),
               build=str(rp.SKID_BUILD), filed=str(rp.SKID_FILED), rules=str(rp.DESIGN_RULES), data=str(rp.DATA),
               step=mb.STEP.name, views=[p.name for p in mb.view_files()],
               filed_name=mb.filed_name(mb.STEP.name, "A"), takeoff=mb.filed_name("bom-model.csv", "C"))
    root = {root!r}
    if root:
        out["rows"] = [r["revision"] for r in mb.filed_rows(__import__("pathlib").Path(root))]
print(json.dumps(out))
"""


def probe(env: dict, args=(), root: str = "") -> dict:
    e = {k: v for k, v in os.environ.items() if k not in ("CPME_MODEL_ID", "CPME_MODEL_CONFIG", "CPME_JOB_MODELS_ROOT")}
    e.update(env)
    r = subprocess.run([sys.executable, "-c", PROBE.format(lib=str(REPO / "harness" / "lib"), root=root), *args],
                       capture_output=True, text=True, env=e, cwd=REPO)
    if r.returncode:
        raise RuntimeError(r.stderr.strip().splitlines()[-1] if r.stderr.strip() else f"exit {r.returncode}")
    return json.loads(r.stdout.strip().splitlines()[-1])


class JobLevelModel(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "M-1").mkdir()
        (self.root / "M-1" / "model.yaml").write_text("model_id: M-1\nlists: ../_lists/A  # list set\n",
                                                      encoding="utf-8")
        self.env = {"CPME_JOB_MODELS_ROOT": str(self.root)}

    def test_redirects_by_env(self):
        o = probe({**self.env, "CPME_MODEL_ID": "M-1", "CPME_MODEL_CONFIG": "x"})
        self.assertEqual(o["level"], "job")
        self.assertEqual((o["model"], o["cfg"], o["doc"]), ("M-1", "X", "M-1-X"))
        self.assertEqual(Path(o["src"]), self.root / "M-1")
        # no full build of this model yet: the path that says so, under the model's own builds folder
        self.assertEqual(Path(o["build"]), rp.JOB_MODELS_BUILDS / "M-1" / "X" / "none")
        self.assertEqual(Path(o["filed"]), rp.JOB_ISSUED / "Models" / "M-1")
        self.assertEqual(Path(o["rules"]), rp.JOB_DESIGN_RULES)
        self.assertEqual(Path(o["data"]), (self.root / "_lists" / "A").resolve())
        self.assertEqual(o["step"], "M-1-X.step")
        self.assertEqual(o["filed_name"], "M-1-X-revA/M-1-X-revA.step.zip")
        self.assertEqual(o["takeoff"], "M-1-X-revC/Takeoffs/M-1-X-revC-bom-model.csv")
        self.assertEqual(o["views"], ["view-iso.png", "view-plan.png", "view-front.png", "view-side.png"])

    def test_flags_are_taken_from_argv(self):
        o = probe(self.env, args=["--model-id", "M-1", "--config=E-OPT1", "--keep"])
        self.assertEqual((o["model"], o["cfg"]), ("M-1", "E-OPT1"))
        self.assertEqual(o["argv"], ["--keep"])            # the flags are gone, the rest is left for argparse

    def test_default_config_is_b(self):
        self.assertEqual(probe({**self.env, "CPME_MODEL_ID": "M-1"})["doc"], "M-1-B")

    def test_unknown_model_refused(self):
        with self.assertRaises(RuntimeError) as cm:
            probe({**self.env, "CPME_MODEL_ID": "NOPE"})
        self.assertIn("NOPE", str(cm.exception))

    def test_filed_rows_are_the_configurations_own(self):
        (self.root / "revisions.csv").write_text(
            "document_id,revision,file\nM-1-B,A,a\nM-1-X,A,b\nM-1-B,B,c\nM-1-X,B,d\nM-1-X,C,e\n", encoding="utf-8")
        o = probe({**self.env, "CPME_MODEL_ID": "M-1", "CPME_MODEL_CONFIG": "B"}, root=str(self.root))
        self.assertEqual(o["rows"], ["A", "B"])
        o = probe({**self.env, "CPME_MODEL_ID": "M-1", "CPME_MODEL_CONFIG": "X"}, root=str(self.root))
        self.assertEqual(o["rows"], ["A", "B", "C"])


class ProjectModelUnchanged(unittest.TestCase):
    @unittest.skipUnless(rp.HAS_PROJECT, "no project yet")
    def test_no_model_id_is_the_project_model(self):
        o = probe({})
        self.assertEqual(o["level"], "project")
        self.assertEqual(o["model"], rp.PROJECT_INFO["model_id"])
        self.assertEqual(o["doc"], o["model"])
        self.assertEqual(Path(o["filed"]), rp.ISSUED / "Models" / o["model"])
        self.assertEqual(Path(o["rules"]), rp.DESIGN_RULES)
        self.assertEqual(o["views"], [])
        self.assertEqual(o["filed_name"], f"{o['model']}-revA/{o['model']}-revA.step.zip")

    @unittest.skipUnless(rp.HAS_PROJECT, "no project yet")
    def test_project_model_id_named_is_the_project_model(self):
        self.assertEqual(probe({"CPME_MODEL_ID": rp.PROJECT_INFO["model_id"]})["level"], "project")

    @unittest.skipUnless(rp.HAS_PROJECT, "no project yet")
    def test_config_on_project_model_refused(self):
        e = {k: v for k, v in os.environ.items() if k not in ("CPME_MODEL_ID", "CPME_MODEL_CONFIG")}
        r = subprocess.run([sys.executable, str(REPO / "harness" / "scripts" / "model_file.py"), "--config", "B",
                            "--dry-run"], capture_output=True, text=True, env=e, cwd=REPO)
        self.assertEqual(r.returncode, 2)
        self.assertIn("needs a job-level model", r.stderr)


class EnvelopeRules(unittest.TestCase):
    def test_rule_limits_from_a_rules_folder(self):
        import envelope
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "layout.yaml").write_text("shipping_envelope:\n  design_max_length_in: 100\n"
                                                 "  design_max_width_in: 50\n  design_max_height_in: 90\n",
                                                 encoding="utf-8")
            lim = envelope.rule_limits(Path(d))
            self.assertEqual((lim["L"], lim["W"], lim["H"]), (100.0, 50.0, 90.0))
            (Path(d) / "layout.yaml").write_text("shipping_envelope:\n  design_max_length_in: unknown\n",
                                                 encoding="utf-8")
            with self.assertRaises(ValueError):
                envelope.rule_limits(Path(d))

    @unittest.skipUnless((rp.JOB_DESIGN_RULES / "layout.yaml").is_file(), "no job design rules (harness master)")
    def test_job_rules_carry_the_envelope(self):
        import envelope
        lim = envelope.rule_limits(rp.JOB_DESIGN_RULES)
        self.assertTrue(all(lim[k] > 0 for k in "LWH"))
        self.assertTrue(lim["source"].endswith("layout.yaml"))


class PipeSupportsNotChecked(unittest.TestCase):
    def test_report_written_when_nothing_is_measured(self):
        import pipe_supports as PS
        with tempfile.TemporaryDirectory() as d:
            PS.write_not_checked(Path(d), "No line in scope.")
            self.assertTrue((Path(d) / "pipe-support-calc.csv").is_file())
            self.assertIn("not checked", (Path(d) / "pipe-support-calc.md").read_text(encoding="utf-8"))
            PS.write_not_checked(None, "nothing")      # no --report: nothing written, no error


if __name__ == "__main__":
    unittest.main()
