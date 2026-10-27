"""Web GLB fallback after a look change (Bob, chat, 2026-10-12: "do not worry about the last 10 revisions
that need rebuilding ... I just want to be very certain that the next model that goes up on the website displays
correctly.").

- build_portal.older_look_copy: an older revision keeps its newest copy of any other look, filed store copy first,
  then web_glbs.py's working copy, then the legacy no-look name; never the current-look name, never a pointer only.
- closeout.report_web_glb: the current-revision WARNING and the "older look kept" lines become report rows, ok=True.

Scratch folders under <project>/_work/ only; nothing filed is read or written.

    .\\harness\\tools\\venv\\Scripts\\python.exe -m unittest harness.tests.test_web_glb_fallback -v
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists())
sys.path.insert(0, str(REPO / "harness" / "lib"))
sys.path.insert(0, str(REPO / "harness" / "scripts"))
import repo_paths as rp  # noqa: E402
if not rp.HAS_PROJECT:
    raise unittest.SkipTest("no project yet (close-out works on a project)")
sys.path.insert(0, str(rp.PRESENTATIONS))

import closeout as CO  # noqa: E402

try:
    import build_portal as BP  # noqa: E402
except ImportError:      # no presentation builders on this project yet (no site, CPME practice)
    BP = None


class Rev:
    model_id, rev, key = rp.SKID_MODEL_ID, "V", f"{rp.SKID_MODEL_ID}:V"


@unittest.skipIf(BP is None, f"no build_portal.py in {rp.PRESENTATIONS} (no site yet)")
class OlderLookCopy(unittest.TestCase):
    def setUp(self):
        rp.WORK.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=rp.WORK, prefix="test-web-glb-")
        root = Path(self.tmp.name)
        self.reviews, self.work = root / "reviews", root / "web-glb"
        self.filed = self.reviews / BP.PORTAL_ID / "data" / "glb"
        self.filed.mkdir(parents=True)
        self.work.mkdir()
        self.p = [mock.patch.object(BP, "REVIEWS", self.reviews), mock.patch.object(BP.D, "WEB_GLB_DIR", self.work)]
        for p in self.p:
            p.start()

    def tearDown(self):
        for p in self.p:
            p.stop()
        self.tmp.cleanup()

    def put(self, folder: Path, name: str, mtime: float) -> Path:
        f = folder / name
        f.write_bytes(b"glb")
        os.utime(f, (mtime, mtime))
        return f

    def test_order_and_exclusions(self):
        cur = "aaaaaaaa"
        self.assertIsNone(BP.older_look_copy(Rev, cur))
        self.put(self.filed, "skid-web-revV.glb", 1)                    # legacy, last resort
        self.assertEqual(BP.older_look_copy(Rev, cur)[1], "skid-web-revV.glb")
        self.put(self.work, "skid-web-revV-11111111.glb", 2)            # working copy beats legacy
        self.assertEqual(BP.older_look_copy(Rev, cur)[1], "skid-web-revV-11111111.glb")
        self.put(self.filed, "skid-web-revV-22222222.glb", 3)
        self.put(self.filed, "skid-web-revV-33333333.glb", 5)           # filed beats working; newest filed first
        self.put(self.filed, f"skid-web-revV-{cur}.glb", 9)             # the current look is never a fallback
        self.put(self.filed, "skid-web-revVA-44444444.glb", 9)          # another revision
        (self.filed / "skid-web-revV-55555555.glb.drive").write_text("pointer only")
        self.assertEqual(BP.older_look_copy(Rev, cur)[1], "skid-web-revV-33333333.glb")


class CloseoutReport(unittest.TestCase):
    def test_rows(self):
        R = CO.Report()
        out = "\n".join(["web GLB for X:A: no copy with look aaaaaaaa; older look kept: skid-web-revA-1.glb",
                         "web GLB for X:B: no copy with look aaaaaaaa; older look kept: skid-web-revB-1.glb",
                         "WARNING web GLB for the current revision X:W: no copy with look aaaaaaaa and no media"])
        with mock.patch("builtins.print"):
            CO.report_web_glb(R, out, "portal")
        self.assertEqual(R.failed, [])
        txt = " | ".join(r for _, r in R.steps)
        self.assertIn("WARNING web GLB for the current revision X:W", txt)
        self.assertIn("2 older revision(s) kept an older-look web GLB", txt)
        R2 = CO.Report()
        CO.report_web_glb(R2, "filed project-portal Rev Z", "portal")
        self.assertEqual(R2.steps, [])


if __name__ == "__main__":
    unittest.main()
