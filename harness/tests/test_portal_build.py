"""The project tracker builder end to end (Bob, chat, 2026-10-30: the Project Tracker and Mobile Optimized for this job).

- Zero filed model revisions: build_portal.py builds the records-only tracker (every page, no revision selector
  entries, no viewer, no data bundles, index.json with no revisions), and Mobile Optimized; --file files it with
  "<MODEL-ID> Rev none" in its revisions.csv rows.
- A fixture model revision set (harness/tests/portal_fixture.py, Revs A and B under a temp folder, read through
  CPME_PORTAL_MODELS_ROOT): the selector lists both, the current revision is the newest (no --rev, no code change),
  Rev A gets a page map, the web GLB and its base64 copy are in data/glb/, lines.html redirects to the line register.
- --file into a scratch filing root (--file-root): the next letters A then B from revisions.csv, the revision folder
  read-only, store files appended, a filed folder never overwritten (TR-08).
- build_landing.py: one tile (Project Tracker; mobile/ on a phone), a plain panel with no render; --file files once and
  an identical rebuild files nothing.
- portal_lib.data.line_families: the S6 families are the line list's service classes (PIPE-SVC-001).
- No page or link of a portal this job does not have (customer portal, estimating portal, quote page).

Every build writes under <project>/_work/ (gitignored) and every filing under a temp folder; nothing is filed into
06_Issued_Revisions/.

    .\\harness\\tools\\venv\\Scripts\\python.exe -m unittest harness.tests.test_portal_build -v
"""
from __future__ import annotations

import csv
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists())
sys.path.insert(0, str(REPO / "harness" / "lib"))
sys.path.insert(0, str(REPO / "harness" / "tests"))
import repo_paths as rp  # noqa: E402
if not rp.HAS_PROJECT:
    raise unittest.SkipTest("no project yet (the tracker presents a project)")
if not (rp.PRESENTATIONS / "build_portal.py").is_file():
    raise unittest.SkipTest(f"no presentation builders in {rp.PRESENTATIONS}")
sys.path.insert(0, str(rp.PRESENTATIONS))
import portal_fixture as FX  # noqa: E402
from portal_lib import data as D  # noqa: E402

PY = sys.executable
BUILD = rp.PRESENTATIONS / "build_portal.py"
LANDING = rp.PRESENTATIONS / "build_landing.py"
PAGES = ["index.html", "model.html", "pid.html", "fabrication.html", "equipment.html", "structure.html",
         "sanitary.html", "bom.html", "records.html"]
NOT_THIS_JOB = re.compile(r"(?i)customer-portal|quoting-portal|estimating/|Fabrication Estimating|quote\.html|tank-modifications")


def run(args: list, env_models: Path | None = None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.pop("CPME_PORTAL_MODELS_ROOT", None)
    if env_models is not None:
        env["CPME_PORTAL_MODELS_ROOT"] = str(env_models)
    return subprocess.run([PY, *map(str, args)], cwd=rp.REPO, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", env=env, timeout=600)


def rm_tree(p: Path) -> None:
    import shutil
    if p.exists():
        shutil.rmtree(p, onexc=lambda fn, q, _e: (os.chmod(q, stat.S_IWRITE), fn(q)))


class Scratch(unittest.TestCase):
    """A temp folder under <project>/_work/ for the work builds; one outside the repo for the fixture models."""

    def setUp(self):
        rp.WORK.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(dir=rp.WORK, prefix="test-portal-build-"))
        self.ext = Path(tempfile.mkdtemp(prefix="test-portal-models-"))

    def tearDown(self):
        rm_tree(self.work)
        rm_tree(self.ext)

    def zero_models(self) -> Path:
        """An empty models root: the project as it is before the first filed revision, whatever is filed."""
        root = self.ext / "zero"
        root.mkdir(exist_ok=True)
        return root


class ZeroRevisions(Scratch):
    def test_records_only_tracker_and_mobile(self):
        out = self.work / "portal"
        r = run([BUILD, "--out", out], env_models=self.zero_models())
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("records-only", r.stdout)
        for p in PAGES + ["lines.html"]:
            self.assertTrue((out / p).is_file(), p)
        idx = json.loads((out / "data" / "index.json").read_text(encoding="utf-8"))
        # no revision of the project's model; filed job-level models (typical models, the header's model selector) are
        # listed as non-current entries with their own page maps
        own = [r for r in idx["revisions"] if r["model_id"] == rp.SKID_MODEL_ID]
        typ = [r for r in idx["revisions"] if r["model_id"] != rp.SKID_MODEL_ID]
        self.assertEqual((idx["current"], own), (None, []))
        self.assertTrue(all(not r["current"] and r["pages"] for r in typ), typ)
        if not typ:
            self.assertEqual(list((out / "data" / "blocks").iterdir()), [])
        # no web GLB of the project's model; job-level models' web GLBs (typical models) may be there
        self.assertEqual([p.name for p in (out / "data" / "glb").iterdir() if p.name.startswith("skid-web")], [])
        html = {p: (out / p).read_text(encoding="utf-8") for p in PAGES}
        for p, h in html.items():
            # no selector entry for a project revision (the selector, if any, offers the records and typical models)
            self.assertNotRegex(h, rf'<option value="{re.escape(rp.SKID_MODEL_ID)}:\w+"', p)
            if not typ:
                self.assertNotIn('class="rev-select"', h, p)
            if p != "model.html":   # Photos and Modeling may show the job-level (typical) models
                self.assertNotIn('data-viewer=', h, p)               # no viewer host for the project's model
            self.assertNotIn("<!--viewer-js-->", h, p)
            self.assertNotRegex(h, NOT_THIS_JOB, p)
        self.assertIn("No model revision is filed yet", html["fabrication.html"])
        self.assertIn("no filed revision yet", html["index.html"])
        self.assertIn("customer not named yet" if rp.CUSTOMER.lower() in ("", "unknown") else rp.CUSTOMER, html["index.html"])
        self.assertIn("Details &amp; Sections", html["pid.html"])    # S9 placeholder
        self.assertIn('href="fabrication.html#register"', (out / "lines.html").read_text(encoding="utf-8"))
        self.assertNotIn("quote.html", html["index.html"])
        nav = re.findall(r'<nav class="nav">(.*?)</nav>', html["index.html"], re.S)[0]
        self.assertEqual(re.findall(r'href="([^"]+)"', nav), PAGES)   # nav order: the plan's page order

        mob = self.work / "mobile"
        r = run([BUILD, "--out", mob, "--audience", "mobile"], env_models=self.zero_models())
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        m = (mob / "index.html").read_text(encoding="utf-8")
        self.assertIn("data-mobile", m)
        self.assertIn("data-desktop-site", m)                        # the "Desktop site" link
        self.assertIn('location.replace("../mobile/"', html["index.html"])   # phone redirect on the tracker

    def test_file_records_only(self):
        # a records-only build files like any other (Bob, chat, 2026-10-30: "I approve for filing")
        r = run([BUILD, "--out", self.work / "portal", "--file", "--note", "x", "--file-root", self.ext / "filed"],
                env_models=self.zero_models())
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        rows = list(csv.DictReader((self.ext / "filed" / "revisions.csv").read_text(encoding="utf-8").splitlines()))
        self.assertEqual({x["revision"] for x in rows}, {"A"})
        self.assertIn(f"{rp.SKID_MODEL_ID} Rev none; P&ID", rows[0]["description"])


class FixtureRevisions(Scratch):
    def setUp(self):
        super().setUp()
        self.fx = FX.make_fixture(self.ext / "models", rp.SKID_MODEL_ID)

    def build(self, *extra, out=None):
        out = out or self.work / "portal"
        r = run([BUILD, "--media", self.fx["media"], "--out", out, *extra], env_models=self.fx["models"])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return out, r.stdout

    def test_newest_revision_picked_up(self):
        out, log = self.build()
        self.assertIn(f"model {rp.SKID_MODEL_ID} Rev B", log)
        idx = json.loads((out / "data" / "index.json").read_text(encoding="utf-8"))
        self.assertEqual(idx["current"], f"{rp.SKID_MODEL_ID}:B")
        own = [r for r in idx["revisions"] if r["model_id"] == rp.SKID_MODEL_ID]   # typical models are listed too
        self.assertEqual([r["revision"] for r in own], ["B", "A"])
        self.assertIsNotNone(next(r for r in own if r["revision"] == "A")["pages"])   # Rev A's page map
        for rev in "AB":
            self.assertTrue((out / "data" / rp.SKID_MODEL_ID / f"rev{rev}" / "takeoffs.json").is_file())
        page = (out / "fabrication.html").read_text(encoding="utf-8")
        self.assertEqual(len(re.findall(rf"<option value=\"{re.escape(rp.SKID_MODEL_ID)}:[AB]\"", page)), 2)
        self.assertIn("data-viewer=", page)                       # the floating model window (T1)
        self.assertIn("data-launch-float", page)
        self.assertIn(f"{FX.LINE_A}-SP01", page)
        glbs = sorted(p.name for p in (out / "data" / "glb").iterdir() if p.name.startswith("skid-"))   # the project's
        self.assertTrue(any(n.endswith(".glb") for n in glbs) and any(n.endswith(".glb.js") for n in glbs), glbs)
        self.assertTrue(all(n.startswith(f"skid-web-{rp.SKID_MODEL_ID}-revB") for n in glbs), glbs)
        man = json.loads((out / "shared-assets.json").read_text(encoding="utf-8"))["assets"]
        self.assertTrue(any(n.startswith("portal.") and n.endswith(".js") for n in man))

    def test_file_takes_the_next_letters_and_is_append_only(self):
        root = self.ext / "filed" / "project-portal"
        out, log = self.build("--file", "--note", "Fixture filing", "--file-root", root)
        self.assertIn("filed project-portal Rev A", log)
        rev_a = root / "project-portal-revA"
        self.assertTrue((rev_a / "index.html").is_file())
        self.assertFalse(os.access(rev_a / "index.html", os.W_OK))        # read-only (TR-08)
        self.assertIn('data-store="../data/"', (rev_a / "index.html").read_text(encoding="utf-8"))
        with open(root / "revisions.csv", newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual({r["revision"] for r in rows}, {"A"})
        self.assertTrue(any(r["file"] == "data/index.json" for r in rows))
        self.assertTrue(rows[0]["description"].startswith(f"{rp.SKID_MODEL_ID} Rev B; P&ID {rp.PID_DOC_ID} Rev"))
        n_store = sum(1 for _ in (root / "data").rglob("*"))
        out, log = self.build("--file", "--note", "Fixture filing 2", "--file-root", root)
        self.assertIn("filed project-portal Rev B", log)
        self.assertTrue((root / "project-portal-revB").is_dir())
        self.assertEqual(sum(1 for _ in (root / "data").rglob("*")), n_store)   # same data: nothing new in the store

    def test_mobile_current_revision_only(self):
        out, log = self.build("--audience", "mobile", out=self.work / "mobile")
        self.assertFalse((out / "data" / "index.json").exists())
        page = (out / "model.html").read_text(encoding="utf-8")
        self.assertIn("data-open-mobile", page)                   # Open 3D tap
        self.assertNotIn('class="rev-select"', page)


class Landing(Scratch):
    def test_one_tile_phone_detect_plain_panel_and_filing(self):
        out = self.work / "site-landing"
        r = run([LANDING, "--out", out])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        h = (out / "index.html").read_text(encoding="utf-8")
        # one tile (Bob, chat, 2026-10-30, Rev B); a phone that has not chosen the desktop site gets mobile/
        self.assertEqual(re.findall(r'class="land-tile[^"]*" href="([^"]+)"', h), ["tracker/index.html"])
        self.assertIn(">Project Tracker<", h)
        self.assertNotIn("Mobile Optimized", h)
        self.assertIn('a.href="mobile/index.html"', h)
        self.assertIn('"cpme-prefer-desktop")!=="1"', h)
        self.assertNotRegex(h, NOT_THIS_JOB)
        if not any(rp.PRESENTATION_RENDERS.glob("*.png")) and not any(rp.PRESENTATION_RENDERS.glob("*.jp*g")):
            self.assertIn('class="home-hero plain"', h)
        root = self.ext / "filed" / "portal-landing"
        r = run([LANDING, "--out", out, "--file", "--note", "Fixture", "--file-root", root])
        self.assertIn("filed portal-landing Rev A", r.stdout, r.stderr)
        r = run([LANDING, "--out", out, "--file", "--note", "Fixture", "--file-root", root])
        self.assertIn("identical to this build; nothing filed", r.stdout, r.stderr)


class LineFamilies(unittest.TestCase):
    def test_service_classes(self):
        lines = [{"line_no": "W-1", "service_class": "hygienic"}, {"line_no": "S-1", "service_class": "steam"},
                 {"line_no": "W-2", "service_class": "hygienic"}, {"line_no": "X-1", "service_class": ""}]
        fam = D.line_families(lines)
        self.assertEqual(fam["lines"], {"W-1": "hygienic", "S-1": "steam", "W-2": "hygienic", "X-1": "unknown"})
        keys = [k for k, _ in fam["families"]]
        self.assertEqual(sorted(keys), ["hygienic", "steam", "unknown"])
        self.assertEqual(dict(fam["families"])["hygienic"], "Hygienic")
        self.assertEqual(D.class_label("utility-water"), "Utility water")
        meaning, rules = D.service_classes()
        if meaning:   # the harness's PIPE-SVC-001 classes, the job's meanings over them
            self.assertIn("hygienic", meaning)
            self.assertIn("steam", rules)


if __name__ == "__main__":
    unittest.main()
