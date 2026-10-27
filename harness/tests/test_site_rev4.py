"""Tests for the presentation site's hosting switches (CPME practice) and the
builder pieces behind them, plus site_revs.site_dormant (CPME practice: no site yet on this project).

The builder cases (build_portal, portal_lib, portal_assets) need <project>/03_Working_Design/CAD/09_Presentation/;
they are skipped while that folder has no builders. The site_revs and publish_site cases always run.

- site_revs.hidden_models reads <project>/03_Working_Design/CAD/09_Presentation/site.yaml hidden_models (model IDs kept
  off the site); no file, no key or an empty list hides nothing.
- build_portal.SharedAssets names every shared asset by its content hash (drawings keep their filed name), so equal
  bytes give one file, and rewrites a page's assets/<path> references to ../assets/<file>; a reference to an asset
  that was not built is recorded, so the build stops instead of shipping a dead link.
- build_portal.assets_plan files only the listed assets the portal's asset store lacks; an asset already filed under
  its name with other bytes, or a listed asset missing from the work folder, is a conflict (TR-08, append-only).
- publish_site.source_plan puts each published revision's listed shared assets at the site root's assets/;
  publish_site.trim_store leaves out every page map, block and web GLB no published page reaches and a hidden model's
  bundles; a tracker built before the switch keeps what it reaches and the hidden model it still lists is reported.
- portal_lib.data.folder_tags reads the tags an equipment-selection folder is named for (lists and ranges).
- Bob, 2026-10-08: site_revs.hidden_pages reads site.yaml hidden_pages (the Quote page); the side menu carries
  "Launch floating model" only on a page with the floating window, under Expand all / Collapse all; the shared scripts
  carry the Pan toggle, the hint, the larger window default and the smaller pick box; portal_terms on a filed revision
  scans only the web GLBs its own pages name.

Every case works in a scratch folder under <project>/_work/ (gitignored); nothing filed is read or written.

    .\\harness\\tools\\venv\\Scripts\\python.exe -m unittest harness.tests.test_site_rev4 -v
"""
from __future__ import annotations

import contextlib
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
sys.path.insert(0, str(REPO / "harness" / "scripts"))
import repo_paths as rp  # noqa: E402
if not rp.HAS_PROJECT:
    raise unittest.SkipTest("no project yet (the site publishes a project's filed portals)")
sys.path.insert(0, str(rp.PRESENTATIONS))
import site_revs  # noqa: E402
import publish_site as PS  # noqa: E402

try:
    import build_portal as BP  # noqa: E402
    from portal_lib import data as D  # noqa: E402
    BUILDERS = True
except ImportError:      # no presentation builders on this project yet
    BP = D = None
    BUILDERS = False
needs_builders = unittest.skipUnless(BUILDERS, f"no presentation builders in {rp.PRESENTATIONS} (no site yet)")
needs_site_config = unittest.skipUnless(rp.SITE_CONFIG.is_file(), f"no {rp.SITE_CONFIG.name} on this project")


def scratch() -> tempfile.TemporaryDirectory:
    rp.WORK.mkdir(parents=True, exist_ok=True)
    return tempfile.TemporaryDirectory(dir=rp.WORK, prefix="test-site-rev4-")


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


class HiddenModels(unittest.TestCase):
    def test_reads_the_list_and_defaults_to_nothing(self):
        with scratch() as d:
            p = Path(d) / "site.yaml"
            self.assertEqual(site_revs.hidden_models(p), ())                       # no file
            p.write_text("# comment only\n", encoding="utf-8")
            self.assertEqual(site_revs.hidden_models(p), ())                       # no key
            p.write_text("hidden_models: []\n", encoding="utf-8")
            self.assertEqual(site_revs.hidden_models(p), ())                       # emptied: brought back
            p.write_text("hidden_models: [RETIRED-MODEL, Other]\n", encoding="utf-8")
            self.assertEqual(site_revs.hidden_models(p), ("RETIRED-MODEL", "Other"))
            p.write_text("hidden_models: RETIRED-MODEL\n", encoding="utf-8")
            self.assertEqual(site_revs.hidden_models(p), ("RETIRED-MODEL",))

    @needs_site_config
    def test_the_repo_setting_hides_the_retired_model(self):
        if not rp.RETIRED_MODEL_ID:
            self.skipTest("no retired model on this project")
        self.assertIn(rp.RETIRED_MODEL_ID, site_revs.hidden_models())
        text = rp.SITE_CONFIG.read_text(encoding="utf-8")
        self.assertIn("To bring them back", text)   # the switch says how to undo it


class SiteDormant(unittest.TestCase):
    """CPME practice: the site framework stays and skips cleanly while the project has no site."""

    def test_unknown_repo_or_missing_builder_is_dormant(self):
        with scratch() as d:
            pres = Path(d)
            self.assertIn("site_repo is unknown", site_revs.site_dormant(site_repo="unknown", presentations=pres))
            self.assertIn("site_repo is unknown", site_revs.site_dormant(site_repo="", presentations=pres))
            self.assertIn("build_portal.py", site_revs.site_dormant(site_repo="o/site", presentations=pres))
            (pres / "build_portal.py").write_text("# stub\n", encoding="utf-8")
            self.assertIsNone(site_revs.site_dormant(site_repo="o/site", presentations=pres))
            self.assertIn("web_glbs.py", site_revs.site_dormant(("build_portal.py", "web_glbs.py"), "o/site", pres))

    def test_this_project_has_no_site_yet(self):
        if not rp.SITE_REPO.lower().startswith("unknown") and (rp.PRESENTATIONS / "build_portal.py").is_file():
            self.skipTest("this project has a site")
        self.assertIn("no presentation site yet", site_revs.site_dormant())
        out = io.StringIO()
        with contextlib.redirect_stdout(out), mock.patch.object(sys, "argv", ["publish_site.py", "--rev", "A"]):
            self.assertEqual(PS.main(), 0)
        self.assertIn("no presentation site yet", out.getvalue())


class HiddenPages(unittest.TestCase):
    """site.yaml hidden_pages (Bob, 2026-10-08: the Quote page removed, with a switch to bring it back)."""

    def test_reads_the_list_by_stem(self):
        with scratch() as d:
            p = Path(d) / "site.yaml"
            self.assertEqual(site_revs.hidden_pages(p), ())
            p.write_text("hidden_models: [X]\n", encoding="utf-8")
            self.assertEqual(site_revs.hidden_pages(p), ())                        # no key: every page built
            p.write_text("hidden_pages: [quote, records.html]\n", encoding="utf-8")
            self.assertEqual(site_revs.hidden_pages(p), ("quote", "records"))

    @needs_site_config
    def test_the_repo_setting_hides_quote_and_says_how_to_restore(self):
        self.assertIn("quote", site_revs.hidden_pages())
        self.assertIn("To bring the Quote page back", rp.SITE_CONFIG.read_text(encoding="utf-8"))

    @needs_builders
    def test_toc_launch_button_only_with_a_floating_window(self):
        from types import SimpleNamespace
        from portal_lib.bits import Page, Section, render_page
        c = SimpleNamespace(audience="internal", past=False, customer="C", model_id="M", rev="N", pid_rev="T", pid_id="P", built="2026-10-08 00:00")
        nav = [("fabrication.html", "Fabrication")]
        sec = [Section("a", "A", "<p>x</p>")]
        with_float = render_page(Page("fabrication.html", "F", blocks=sec, float3d='<div data-viewer></div>'), c, nav)[0]
        without = render_page(Page("fabrication.html", "F", blocks=sec), c, nav)[0]
        self.assertIn("data-launch-float", with_float)
        self.assertLess(with_float.index("data-collapse"), with_float.index("data-launch-float"))   # under the two buttons
        self.assertNotIn("data-launch-float", without)


@needs_builders
class ViewerAssets(unittest.TestCase):
    """The shared viewer and portal scripts carry the 2026-10-08 window, pick box and pan changes."""

    def test_pan_toggle_hint_and_float_defaults(self):
        a = rp.PRESENTATIONS / "portal_assets"
        v, p, css = ((a / n).read_text(encoding="utf-8") for n in ("viewer.js", "portal.js", "portal.css"))
        self.assertIn("data-pan", v)
        self.assertIn("setPan(false)", v)                     # Reset turns Pan off
        self.assertIn("Shift+drag", v)                        # the hint names the methods
        self.assertIn("cpme-float-geom-2", p)                 # the Rev L size gives way once
        self.assertIn("W * 0.6", p)
        self.assertIn("H * 0.65", p)
        self.assertIn("[data-launch-float]", p)
        self.assertIn("max-width: min(300px, 50%)", css)      # the pick box: at most half by half of the viewer


class PortalTermsFiledGlbs(unittest.TestCase):
    """portal_terms on a filed revision scans only the web GLBs its own pages name, not an older revision's GLB in the
    shared append-only store (found on a filed quoting portal)."""

    @staticmethod
    def glb(names: list[str]) -> bytes:
        import struct
        j = json.dumps({"asset": {"version": "2.0"}, "nodes": [{"name": n} for n in names]}).encode()
        j += b" " * (-len(j) % 4)
        return b"glTF" + struct.pack("<II", 2, 20 + len(j)) + struct.pack("<I", len(j)) + b"JSON" + j

    def test_only_the_revisions_own_glb(self):
        sys.path.insert(0, str(REPO / "harness" / "checks"))
        import portal_terms as PT
        with scratch() as d:
            root = Path(d) / "quoting-portal"
            rev = root / "quoting-portal-revZ"
            (root / "data" / "glb").mkdir(parents=True)
            rev.mkdir()
            (rev / "index.html").write_text('<html><body><div data-glbs=\'{"k": "glb/skid-quote-revN.glb"}\'>x</div></body></html>', encoding="utf-8")
            (root / "data" / "glb" / "skid-quote-revN.glb").write_bytes(self.glb(["tube_T-901"]))
            (root / "data" / "glb" / "skid-quote-revB.glb").write_bytes(self.glb(["adapter CMP-T032"]))
            names = [n for n, _ in PT.texts(rev, fab=True)]
            self.assertIn("../data/glb/skid-quote-revN.glb (part names)", names)
            self.assertNotIn("../data/glb/skid-quote-revB.glb (part names)", names)


@needs_builders
class SharedAssetsNaming(unittest.TestCase):
    def test_hash_names_dedupe_and_rewrite(self):
        with scratch() as d:
            s = BP.SharedAssets(Path(d) / "assets")
            a = s.add("portal.js", b"console.log(1)")
            b = s.add("portal.js", b"console.log(1)")
            self.assertEqual(a, b)
            self.assertRegex(a, r"^\.\./assets/portal\.[0-9a-f]{10}\.js$")
            self.assertEqual(s.add("docs/X-revA.pdf", b"%PDF"), "../assets/docs/X-revA.pdf")   # filed name kept
            s.add("media/hero.webp", b"img")
            self.assertEqual(len(s.used), 3)
            html = ('<link href="assets/portal.js"><img src=assets/media/hero.webp alt=>'
                    '<iframe src="assets/docs/X-revA.pdf#view=FitH"></iframe><a href="assets/media/nope.png">')
            out = s.rewrite(html)
            self.assertIn(f'href="../assets/{s.map["portal.js"]}"', out)
            self.assertIn(f'src=../assets/{s.map["media/hero.webp"]} ', out)
            self.assertIn('src="../assets/docs/X-revA.pdf#view=FitH"', out)
            self.assertEqual(s.unknown, {"media/nope.png"})       # not built: the build stops on it
            self.assertTrue((Path(d) / "assets" / s.map["portal.js"]).is_file())


@needs_builders
class AssetsPlan(unittest.TestCase):
    def layout(self, d: Path, files: dict[str, bytes]) -> Path:
        work = d / "site" / "tracker"
        work.mkdir(parents=True)
        for n, b in files.items():
            (d / "site" / "assets" / n).parent.mkdir(parents=True, exist_ok=True)
            (d / "site" / "assets" / n).write_bytes(b)
        (work / BP.SHARED_MANIFEST).write_text(json.dumps({"assets": {n: sha(b) for n, b in files.items()}}), encoding="utf-8")
        return work

    def test_new_identical_and_conflicting(self):
        with scratch() as t:
            d = Path(t)
            work = self.layout(d, {"a.1.js": b"A", "b.2.css": b"B", "c.3.svg": b"C"})
            store = d / "filed" / "assets"
            store.mkdir(parents=True)
            (store / "b.2.css").write_bytes(b"B")        # filed before, same bytes: skipped
            new, conf = BP.assets_plan(work, store)
            self.assertEqual(sorted(t.name for _, t in new), ["a.1.js", "c.3.svg"])
            self.assertEqual(conf, [])
            (store / "c.3.svg").write_bytes(b"changed")   # filed before, other bytes: refused
            new, conf = BP.assets_plan(work, store)
            self.assertEqual([t.name for _, t in new], ["a.1.js"])
            self.assertTrue(any("c.3.svg" in c for c in conf))

    def test_missing_work_file_is_a_conflict_and_no_list_files_nothing(self):
        with scratch() as t:
            d = Path(t)
            work = self.layout(d, {"a.1.js": b"A"})
            (d / "site" / "assets" / "a.1.js").write_bytes(b"edited")   # differs from the listed sha256
            _, conf = BP.assets_plan(work, d / "filed" / "assets")
            self.assertTrue(conf)
            (work / BP.SHARED_MANIFEST).unlink()
            self.assertEqual(BP.assets_plan(work, d / "filed" / "assets"), ([], []))


class PublishPlan(unittest.TestCase):
    def test_shared_assets_go_to_the_site_root(self):
        with scratch() as t:
            root = Path(t) / "project-portal"
            (root / "project-portal-revL").mkdir(parents=True)
            (root / "assets").mkdir()
            (root / "assets" / "portal.abc.js").write_bytes(b"js")
            (root / "project-portal-revL" / "index.html").write_text("<html>", encoding="utf-8")
            (root / "project-portal-revL" / PS.SHARED_MANIFEST).write_text(json.dumps({"assets": {"portal.abc.js": sha(b"js")}}), encoding="utf-8")
            (root / "assets" / "old.zzz.js").write_bytes(b"old")   # in the store, not used by Rev L: not published
            plan = PS.source_plan([(root, "project-portal-revL", "tracker/")])
            self.assertIn("assets/portal.abc.js", plan)
            self.assertIn("tracker/index.html", plan)
            self.assertNotIn("assets/old.zzz.js", plan)

    def test_trim_store_hides_models_and_unreached_files(self):
        with scratch() as t:
            d = Path(t)

            def put(k: str, text: str) -> Path:
                p = d / k
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(text, encoding="utf-8")
                return p

            def pages_js(model: str, blocks: list) -> str:
                return "PortalRev.setPages(" + json.dumps({"model_id": model, "pages": {"a.html": {"blocks": blocks}}}) + ");"

            viewer = '<div data-glbs="{&quot;M&quot;:&quot;glb/skid-web-revM.glb&quot;}" data-glb-b64="glb/skid-web-revM.glb.js">'
            plan = {
                # a tracker built with the switch on: its picker names the CPME page map only
                "tracker/a.html": put("tracker/a.html", '<option data-pages="aaaaaaaaaaaaaaaa">' + viewer),
                "data/blocks/aaaaaaaaaaaaaaaa.js": put("b/a", pages_js("CPME", ["1111111111111111", None, "2222222222222222"])),
                "data/blocks/bbbbbbbbbbbbbbbb.js": put("b/b", pages_js("RETIRED-MODEL", ["2222222222222222", "3333333333333333"])),
                "data/blocks/1111111111111111.js": put("b/1", 'PortalRev.setBlock("1","<div data-glbs=\\"glb/skid-web-revK.glb\\">");'),
                "data/blocks/2222222222222222.js": put("b/2", 'PortalRev.setBlock("2","shared");'),
                "data/blocks/3333333333333333.js": put("b/3", 'PortalRev.setBlock("3","<div glb/skid-web-RETIRED-MODEL-revAQ.glb>");'),
                "data/blocks/9999999999999999.js": put("b/9", 'PortalRev.setBlock("9","old");'),
                "data/glb/skid-web-revM.glb": put("g/M", "m"), "data/glb/skid-web-revM.glb.js": put("g/Mjs", "m"),
                "data/glb/skid-web-revK.glb": put("g/K", "k"), "data/glb/skid-web-revA.glb": put("g/A", "a"),
                "data/glb/skid-web-RETIRED-MODEL-revAQ.glb": put("g/O", "o"),
                "data/RETIRED-MODEL/revAQ/takeoffs.json": put("o/t", "{}"),
                "data/CURRENT-MODEL/revM/takeoffs.json": put("c/t", "{}"),
                "data/index.json": put("i", "{}"),
            }
            kept, dropped, still = PS.trim_store(dict(plan), ("RETIRED-MODEL",))
            self.assertEqual(still, [])
            self.assertEqual(sorted(dropped), sorted([
                "data/blocks/bbbbbbbbbbbbbbbb.js", "data/blocks/3333333333333333.js", "data/blocks/9999999999999999.js",
                "data/glb/skid-web-revA.glb", "data/glb/skid-web-RETIRED-MODEL-revAQ.glb",
                "data/RETIRED-MODEL/revAQ/takeoffs.json"]))
            for k in ("data/blocks/aaaaaaaaaaaaaaaa.js", "data/blocks/1111111111111111.js", "data/blocks/2222222222222222.js",
                      "data/glb/skid-web-revM.glb", "data/glb/skid-web-revM.glb.js", "data/glb/skid-web-revK.glb",
                      "data/CURRENT-MODEL/revM/takeoffs.json", "data/index.json", "tracker/a.html"):
                self.assertIn(k, kept)
            # a tracker built before the switch (or with it off) still lists the retired model: everything it reaches stays, so its
            # picker never breaks, and the hidden model it still shows is reported
            put("tracker/a.html", '<option data-pages="aaaaaaaaaaaaaaaa"><option data-pages="bbbbbbbbbbbbbbbb">' + viewer)
            kept2, dropped2, still2 = PS.trim_store(dict(plan), ("RETIRED-MODEL",))
            self.assertEqual(still2, ["RETIRED-MODEL"])
            for k in ("data/blocks/bbbbbbbbbbbbbbbb.js", "data/blocks/3333333333333333.js",
                      "data/glb/skid-web-RETIRED-MODEL-revAQ.glb", "data/RETIRED-MODEL/revAQ/takeoffs.json"):
                self.assertIn(k, kept2)
            self.assertEqual(sorted(dropped2), ["data/blocks/9999999999999999.js", "data/glb/skid-web-revA.glb"])

    def test_conflicting_shared_asset_is_refused(self):
        with scratch() as t:
            d = Path(t)
            docs = []
            for name, body in (("project-portal", b"one"), ("quoting-portal", b"two")):
                root = d / name
                (root / f"{name}-revA").mkdir(parents=True)
                (root / "assets").mkdir()
                (root / "assets" / "docs").mkdir()
                (root / "assets" / "docs" / "X-revA.pdf").write_bytes(body)   # same filed name, other bytes
                (root / f"{name}-revA" / PS.SHARED_MANIFEST).write_text(json.dumps({"assets": {"docs/X-revA.pdf": sha(body)}}), encoding="utf-8")
                docs.append((root, f"{name}-revA", f"{name}/"))
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as cm:
                PS.source_plan(docs)
            self.assertEqual(cm.exception.code, 2)


@needs_builders
class FolderTags(unittest.TestCase):
    def test_lists_ranges_and_untagged(self):
        self.assertEqual(D.folder_tags("CV-901, CV-902, CV-951 - Check Valves"), ["CV-901", "CV-902", "CV-951"])
        self.assertEqual(D.folder_tags("XV-901..XV-904 - Butterfly Valves"), ["XV-901", "XV-902", "XV-903", "XV-904"])
        self.assertEqual(D.folder_tags("TK-901 - Test Tank"), ["TK-901"])
        self.assertEqual(D.folder_tags("Control Panel"), [])
        self.assertEqual(D.folder_tags("Tanks - Other Vendor References"), [])


if __name__ == "__main__":
    unittest.main()
