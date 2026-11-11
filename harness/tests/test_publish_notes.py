"""Tests for the publish notes publish_site.py writes on every publish (the "Notes for packaging" section and
publish-notes.json).

- find_anomalies: every code in publish_site.CODES fires on its case and carries CODES' severity and a one-line message;
  a normal publish (next letters, store churn, nothing new) gives no anomalies; leaving out the customer site is an
  anomaly only on a project that has one (or when the last publish carried it).
- commit_message: the subject unchanged, a blank line, "Notes for packaging:" with one bullet per anomaly or
  "No anomalies.", a blank line, the body.
- build_notes / validate_notes: the publish-notes.json schema (keys in order, types, anomaly shape); bad objects refused.
- On a fake site repo under <project>/_work/: site_snapshot from README.md + tree (a publish with no notes) and from
  publish-notes.json; commits_since_last_publish (the site repo's own commits after the last "Site:" commit);
  site_files and tree_paths never count publish-notes.json; packager_portals reads PORTALS with ast and falls back to
  the project's portals.
- parse_packager reads package_portals.py's summary lines and the new-since-last counts.
- closeout.site_packaging_lines carries the "packaging note(s):" lines into the go.

No real site checkout, remote or filed file is read or written. Needs a project; skipped in the harness master.

    .\\harness\\tools\\venv\\Scripts\\python.exe -m unittest harness.tests.test_publish_notes -v
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists())
sys.path.insert(0, str(REPO / "harness" / "lib"))
sys.path.insert(0, str(REPO / "harness" / "scripts"))
sys.path.insert(0, str(REPO / "harness" / "tests"))
import repo_paths as rp  # noqa: E402
if not rp.HAS_PROJECT:
    raise unittest.SkipTest("no project yet (the publish tests work in the project's _work/)")

import publish_site as PS  # noqa: E402
from test_publish_upstream import commit, g  # noqa: E402

SEEN: set[str] = set()   # codes the tests below made fire; checked against CODES last


def portals(**revs) -> list[dict]:
    names = {"landing": "portal-landing", "tracker": "project-portal", "estimating": "quoting-portal",
             "mobile": "mobile-portal", "customer": "customer-portal"}
    return [{"document": names[k], "revision": v, "folder": PS.DOC_FOLDER[names[k]]} for k, v in revs.items()]


BASE = dict(landing="E", tracker="Z", estimating="R", mobile="C", customer="B")
PREV_PATHS = ([f"tracker/p{i}.html" for i in range(12)] + [f"estimating/p{i}.html" for i in range(6)]
              + [f"mobile/p{i}.html" for i in range(12)] + [f"customer/p{i}.html" for i in range(4)]
              + [f"assets/a{i}.js" for i in range(60)] + [f"data/blocks/b{i}.js" for i in range(800)] + ["index.html"])
PASS = {"status": "pass", "exit_code": 0, "packager_portals": ["customer", "estimating", "tracker"],
        "packager_portals_source": "PORTALS in .github/packaging/package_portals.py", "warnings": [],
        "portals": {"tracker": {"revision": "Z", "files": 9, "links_out": [], "unresolved_count": 0, "unresolved_shown": []}},
        "new_since_last": {"links_out": [], "unresolved": 0}}


def snap(model=("M-1", "A"), pid=("P-1", "A"), revs=None, paths=None, top=None) -> dict:
    revs = dict(BASE) if revs is None else revs
    paths = PREV_PATHS if paths is None else paths
    return {"model": {"id": model[0], "revision": model[1]}, "pid": {"id": pid[0], "revision": pid[1]},
            "portals": portals(**revs), "paths": paths,
            "top_folders": top if top is not None else sorted({p.split("/")[0] for p in paths if "/" in p})}


def files(removed=(), added=()) -> dict:
    return {"prev_by_folder": PS.count_by_folder(PREV_PATHS), "prev_total": len(PREV_PATHS),
            "removed": list(removed), "added": list(added), "changed": [], "plan_paths": PREV_PATHS}


def run(prev=None, cur=None, f=None, ups=(), pk=None, customer_site=True) -> list[dict]:
    out = PS.find_anomalies(prev or snap(), cur or snap(), f or files(), list(ups), pk or PASS, customer_site)
    for a in out:
        SEEN.add(a["code"])
    return out


def codes(out: list[dict]) -> list[str]:
    return [a["code"] for a in out]


class Anomalies(unittest.TestCase):
    def check(self, out: list[dict], code: str) -> dict:
        hit = [a for a in out if a["code"] == code]
        self.assertTrue(hit, f"{code} not in {codes(out)}")
        a = hit[0]
        self.assertEqual(a["severity"], PS.CODES[code])
        self.assertNotIn("\n", a["message"])
        self.assertIsInstance(a["details"], dict)
        return a

    def test_no_anomalies(self):
        churn = files(removed=[f"assets/a{i}.js" for i in range(20)] + [f"data/blocks/b{i}.js" for i in range(80)],
                      added=[f"assets/n{i}.js" for i in range(22)] + [f"data/blocks/n{i}.js" for i in range(90)])
        nxt = snap(revs=dict(BASE, tracker="AA", estimating="S"))
        self.assertEqual(run(cur=nxt, f=churn), [])
        self.assertEqual(PS.notes_lines([]), ["Notes for packaging:", "No anomalies."])
        self.assertEqual(PS.anomaly_summary([]), ["packaging notes: no anomalies"])

    def test_model_id_changed(self):
        a = self.check(run(cur=snap(model=("M-2", "A"))), "MODEL_ID_CHANGED")
        self.assertIn("M-1 Rev A to M-2 Rev A", a["message"])

    def test_model_rev_backwards(self):
        self.check(run(prev=snap(model=("M-1", "AB")), cur=snap(model=("M-1", "Z"))), "MODEL_REV_BACKWARDS")
        self.assertEqual(run(prev=snap(model=("M-1", "Z")), cur=snap(model=("M-1", "AA"))), [])

    def test_pid_id_changed(self):
        self.check(run(cur=snap(pid=("P-2", "A"))), "PID_ID_CHANGED")

    def test_portal_added_and_removed(self):
        no_mobile = dict(BASE)
        del no_mobile["mobile"]
        self.check(run(prev=snap(revs=no_mobile)), "PORTAL_ADDED")
        a = self.check(run(cur=snap(revs=no_mobile)), "PORTAL_REMOVED")
        self.assertEqual(a["details"]["document"], "mobile-portal")

    def test_rev_skipped_and_backwards(self):
        a = self.check(run(cur=snap(revs=dict(BASE, customer="D"))), "REV_SKIPPED")
        self.assertIn("Rev B to Rev D, skipping 1", a["message"])
        self.check(run(cur=snap(revs=dict(BASE, tracker="AB"))), "REV_SKIPPED")   # Z -> AB skips AA
        self.check(run(cur=snap(revs=dict(BASE, estimating="Q"))), "REV_BACKWARDS")
        self.assertEqual(PS.rev_index("A"), 1)
        self.assertEqual(PS.rev_index("Z"), 26)
        self.assertEqual(PS.rev_index("AA"), 27)

    def test_customer_left_out(self):
        no_cus = dict(BASE)
        del no_cus["customer"]
        out = run(cur=snap(revs=no_cus))
        a = self.check(out, "CUSTOMER_LEFT_OUT")
        self.assertIn("was in the last publish", a["message"])
        self.assertNotIn("PORTAL_REMOVED", codes(out))   # reported once, as CUSTOMER_LEFT_OUT
        a = self.check(run(prev=snap(revs=no_cus), cur=snap(revs=no_cus)), "CUSTOMER_LEFT_OUT")
        self.assertIn("not in the last publish either", a["message"])

    def test_no_customer_site_no_anomaly(self):
        """A project without a customer site (tracker, landing and Mobile Optimized only) never gets CUSTOMER_LEFT_OUT."""
        plain = dict(landing="E", tracker="Z", mobile="C")
        paths = [p for p in PREV_PATHS if not p.startswith(("estimating/", "customer/"))]
        self.assertEqual(run(prev=snap(revs=plain, paths=paths), cur=snap(revs=dict(plain, tracker="AA"), paths=paths),
                             customer_site=False), [])
        # one that had customer/ on the site and drops it is still told
        self.check(run(cur=snap(revs=plain), customer_site=False), "CUSTOMER_LEFT_OUT")

    def test_upstream_commits(self):
        c = {"hash": "23ec616a599c15940dda5e7b2128b6a9c0bf6d3d", "author": "site-owner", "date": "2026-10-22",
             "subject": "cover customer page", "files": [".github/packaging/package_portals.py"]}
        a = self.check(run(ups=[c]), "UPSTREAM_COMMITS")
        self.assertIn('23ec616 site-owner "cover customer page"', a["message"])

    def test_packager_failed_warned_not_run(self):
        self.check(run(pk=dict(PASS, status="fail", exit_code=2)), "PACKAGER_FAILED")
        self.check(run(pk=dict(PASS, warnings=["WARNING: x"])), "PACKAGER_WARNED")
        self.check(run(pk=dict(PASS, status="missing", exit_code=None)), "PACKAGER_NOT_RUN")
        self.check(run(pk=dict(PASS, status="skipped", exit_code=None)), "PACKAGER_NOT_RUN")

    def test_packager_new_findings_and_unknown_baseline(self):
        a = self.check(run(pk=dict(PASS, new_since_last={"links_out": ["tracker: index.html"], "unresolved": 3})),
                       "PACKAGER_NEW_FINDINGS")
        self.assertIn("1 new link(s) out (tracker: index.html)", a["message"])
        found = dict(PASS, portals={"tracker": {"revision": "Z", "files": 9, "links_out": ["index.html"],
                                                "unresolved_count": 5, "unresolved_shown": []}},
                     new_since_last={"links_out": None, "unresolved": None})
        a = self.check(run(pk=found), "PACKAGER_FINDINGS")
        self.assertIn("1 link(s) out and 5 unresolved", a["message"])

    def test_large_removal(self):
        a = self.check(run(f=files(removed=[f"tracker/p{i}.html" for i in range(4)])), "LARGE_REMOVAL")
        self.assertEqual(a["details"]["folder"], "tracker")
        self.assertNotIn("LARGE_REMOVAL", codes(run(f=files(removed=["tracker/p1.html", "tracker/p2.html"]))))
        # the shared stores churn on every publish: no per-folder rule for assets/ and data/
        self.assertNotIn("LARGE_REMOVAL", codes(run(f=files(removed=[f"assets/a{i}.js" for i in range(40)]))))
        a = self.check(run(f=files(removed=[f"data/blocks/b{i}.js" for i in range(300)])), "LARGE_REMOVAL")
        self.assertEqual(a["details"]["folder"], "*")

    def test_new_folder_not_packaged(self):
        cur = snap(paths=PREV_PATHS + ["quoting/index.html"])
        a = self.check(run(cur=cur), "NEW_FOLDER_NOT_PACKAGED")
        self.assertEqual(a["details"]["folder"], "quoting")
        self.assertEqual(run(), [])   # mobile/ is not packaged but is not new: no anomaly
        # a site repo with no packager: PACKAGER_NOT_RUN only, not a folder-by-folder list
        self.assertEqual(codes(run(cur=cur, pk=dict(PASS, status="missing", exit_code=None))), ["PACKAGER_NOT_RUN"])

    def test_every_code_is_tested(self):
        for name in sorted(n for n in dir(self) if n.startswith("test_") and n != "test_every_code_is_tested"):
            getattr(self, name)()
        self.assertEqual(SEEN, set(PS.CODES))


class Message(unittest.TestCase):
    def test_format(self):
        an = [{"code": "MODEL_ID_CHANGED", "severity": "warn", "message": "Model ID changed.", "details": {}},
              {"code": "UPSTREAM_COMMITS", "severity": "info", "message": "One commit.", "details": {}}]
        msg = PS.commit_message("Site: project-portal Rev Z (model Rev A, P&ID Rev A)", an, ["Body line.", "Last."])
        self.assertEqual(msg, "Site: project-portal Rev Z (model Rev A, P&ID Rev A)\n\nNotes for packaging:\n"
                              "- [warn] MODEL_ID_CHANGED: Model ID changed.\n- [info] UPSTREAM_COMMITS: One commit.\n"
                              "\nBody line.\nLast.\n")
        self.assertEqual(PS.commit_message("Site: x", [], ["b"]), "Site: x\n\nNotes for packaging:\nNo anomalies.\n\nb\n")
        self.assertEqual(PS.anomaly_summary(an)[0], "packaging notes: 2 anomalies (1 warn)")
        self.assertEqual(PS.anomaly_summary(an)[1], "packaging note: [warn] MODEL_ID_CHANGED: Model ID changed.")


class Schema(unittest.TestCase):
    def notes(self, **kw) -> dict:
        return PS.build_notes(published_at="2026-10-22T14:00:00-05:00", design_commit="1" * 40, parent="2" * 40,
                              prev=dict(snap(), source="README.md and tree", site_commit="2" * 40),
                              cur=snap(model=("M-2", "A")), files=dict(files(removed=["tracker/p1.html"]), bytes=10),
                              upstream_commits=[], packager=PASS, customer_site=True, **kw)

    def test_valid_and_round_trips(self):
        n = self.notes()
        self.assertEqual(PS.validate_notes(n), [])
        self.assertEqual(list(n), list(PS.NOTES_KEYS))
        self.assertEqual(n["schema"], PS.NOTES_SCHEMA)
        self.assertEqual(n["design_repo"]["repo"], rp.DESIGN_REPO)
        back = json.loads(PS.notes_json(n))
        self.assertEqual(PS.validate_notes(back), [])
        self.assertEqual(back["files"]["removed"], 1)
        self.assertEqual(back["files"]["removed_paths"], ["tracker/p1.html"])
        self.assertEqual(back["files"]["unchanged"], len(PREV_PATHS))
        self.assertEqual([a["code"] for a in back["anomalies"]], ["MODEL_ID_CHANGED"])
        self.assertTrue(PS.notes_json(n).endswith("}\n"))

    def test_removed_paths_capped(self):
        n = PS.build_notes(published_at="t", design_commit="c", parent="p", prev=snap(), cur=snap(),
                           files=files(removed=[f"data/blocks/b{i}.js" for i in range(80)]), upstream_commits=[],
                           packager=PASS, customer_site=True)
        self.assertEqual(len(n["files"]["removed_paths"]), PS.NOTES_PATHS_MAX)
        self.assertTrue(n["files"]["removed_paths_truncated"])

    def test_invalid_refused(self):
        n = self.notes()
        bad = dict(n, schema="other/1")
        self.assertTrue(any("schema" in b for b in PS.validate_notes(bad)))
        bad = dict(n, anomalies=[{"code": "NOPE", "severity": "warn", "message": "m", "details": {}}])
        self.assertTrue(PS.validate_notes(bad))
        bad = dict(n, anomalies=[{"code": "MODEL_ID_CHANGED", "severity": "warn", "message": "a\nb", "details": {}}])
        self.assertTrue(any("one line" in b for b in PS.validate_notes(bad)))
        bad = {k: n[k] for k in reversed(PS.NOTES_KEYS)}
        self.assertTrue(any("keys" in b for b in PS.validate_notes(bad)))


def readme_fixture(estimating: bool = True, customer: bool = True) -> str:
    """A site README as publish_site.py writes it (README6), with or without the estimating and customer sentences."""
    fmt = dict(PS.PROJECT_FMT, rev="Z", model="M-1", mrev="AB", prev="AC", date="2026-10-22", commit="1d8a678",
               rows="| x |")
    fmt["pid_doc_id"] = "P-1"
    return PS.README6.format(
        land="E", mob_note=" **Rev C**",
        est_intro=PS.README6_EST_INTRO if estimating else "",
        est_content=PS.README6_EST_CONTENT.format(quote="R", **PS.PROJECT_FMT) if estimating else "",
        cus_intro=PS.README6_CUS_INTRO.format(cus_note=" **Rev B**") if customer else "", **fmt)


class FakeSiteNotes(unittest.TestCase):
    def setUp(self):
        rp.WORK.mkdir(parents=True, exist_ok=True)
        self._tmp = tempfile.TemporaryDirectory(dir=rp.WORK, prefix="test-publish-notes-")
        root = Path(self._tmp.name)
        self.origin, self.site, self.owner = root / "origin.git", root / "site", root / "owner"
        g(root, "init", "--bare", "--initial-branch=main", str(self.origin))
        g(root, "clone", str(self.origin), str(self.site))
        self.pub = commit(self.site, {"README.md": readme_fixture(), "index.html": "<p>landing</p>\n",
                                      "tracker/index.html": "t\n", "data/x.js": "d\n",
                                      ".github/packaging/package_portals.py": 'PORTALS = {"tracker": "project-portal"}\n'},
                          "Site: project-portal Rev Z (model Rev AB, P&ID Rev AC)")
        g(root, "clone", str(self.origin), str(self.owner))

    def tearDown(self):
        self._tmp.cleanup()

    def test_snapshot_from_readme(self):
        s = PS.site_snapshot(self.site, "HEAD")
        self.assertEqual(s["source"], "README.md and tree")
        self.assertEqual(s["model"], {"id": "M-1", "revision": "AB"})
        self.assertEqual(s["pid"], {"id": "P-1", "revision": "AC"})
        self.assertEqual(s["design_commit"], "1d8a678")
        self.assertEqual([(p["document"], p["revision"], p["folder"]) for p in s["portals"]],
                         [("portal-landing", "E", ""), ("project-portal", "Z", "tracker/"),
                          ("quoting-portal", "R", "estimating/"), ("mobile-portal", "C", "mobile/"),
                          ("customer-portal", "B", "customer/")])
        self.assertEqual(sorted(s["paths"]), ["data/x.js", "index.html", "tracker/index.html"])
        self.assertIsNone(s["packager"])

    def test_plain_readme_names_only_the_three(self):
        """A project with the tracker, landing page and Mobile Optimized only: the README names those three."""
        text = readme_fixture(estimating=False, customer=False)
        self.assertNotIn("estimating", text.lower())
        self.assertNotIn("customer", text.lower().replace(str(PS.PROJECT_FMT["customer"]).lower(), ""))
        self.assertEqual([p["document"] for p in PS.portals_from_readme(text)],
                         ["portal-landing", "project-portal", "mobile-portal"])

    def test_snapshot_from_notes_and_notes_file_never_counted(self):
        notes = {"schema": PS.NOTES_SCHEMA, "design_repo": {"commit": "abc"}, "model": {"id": "M-2", "revision": "A"},
                 "pid": {"id": "P-2", "revision": "A"}, "portals": portals(tracker="AA"), "packager": PASS}
        commit(self.site, {PS.NOTES_FILE: json.dumps(notes)}, "Site: project-portal Rev AA")
        s = PS.site_snapshot(self.site, "HEAD")
        self.assertEqual(s["source"], PS.NOTES_FILE)
        self.assertEqual(s["model"]["id"], "M-2")
        self.assertEqual(s["packager"]["status"], "pass")
        self.assertNotIn(PS.NOTES_FILE, s["paths"])
        self.assertNotIn(PS.NOTES_FILE, PS.site_files(self.site))
        self.assertFalse(PS.keep_path(PS.NOTES_FILE))   # not KEEP: an upstream commit touching it is content

    def test_commits_since_last_publish(self):
        self.assertEqual(PS.commits_since_last_publish(self.site, "HEAD"), [])
        h = commit(self.owner, {".github/workflows/package.yml": "x\n"}, "Owner: workflow")
        g(self.site, "fetch", "origin", "main")
        got = PS.commits_since_last_publish(self.site, "origin/main")
        self.assertEqual([c["hash"] for c in got], [h])
        self.assertEqual(got[0]["files"], [".github/workflows/package.yml"])
        self.assertEqual(PS.commits_since_last_publish(self.site, "HEAD"), [])

    def test_packager_portals(self):
        names, src = PS.packager_portals(self.site / PS.PACKAGER)
        self.assertEqual(names, ["tracker"])
        self.assertIn("PORTALS in", src)
        names, src = PS.packager_portals(self.site / "nowhere.py")
        self.assertEqual(names, sorted(PS.packager_portals_default()))
        self.assertIn("default", src)
        self.assertIn("tracker", PS.packager_portals_default())
        self.assertNotIn("mobile", PS.packager_portals_default())


PK_LINES = [
    "package_portals.py exit 0 (python -I ...)",
    "packaged M-1 estimating Rev R (model Rev A): 42 files, 47.6 MB -> C:\\x",
    "  assets: 33, data/glb: 3, estimating: 6",
    "  links out of the portal, not packaged (will not resolve in the package): index.html",
    "  17 file-like mention(s) not in the site, ignored (prose or code): a.png, b.csv ...",
    "packaged M-1 tracker Rev Z (model Rev A): 793 files, 101.4 MB -> C:\\y",
    "catalog: 1 project(s) in C:\\z",
]


class Packager(unittest.TestCase):
    def test_parse(self):
        p = PS.parse_packager("pass", PK_LINES, None, None)
        self.assertEqual(p["exit_code"], 0)
        self.assertEqual(p["portals"]["estimating"], {"revision": "R", "files": 42, "links_out": ["index.html"],
                                                      "unresolved_count": 17, "unresolved_shown": ["a.png", "b.csv"]})
        self.assertEqual(p["portals"]["tracker"]["unresolved_count"], 0)
        self.assertEqual(p["new_since_last"], {"links_out": None, "unresolved": None})
        self.assertEqual(p["warnings"], [])

    def test_new_since_last(self):
        prev = PS.parse_packager("pass", PK_LINES[:4] + ["  12 file-like mention(s) not in the site, ignored: a.png"], None, None)
        prev["portals"]["estimating"]["links_out"] = []
        p = PS.parse_packager("pass", PK_LINES, None, prev)
        self.assertEqual(p["new_since_last"], {"links_out": ["estimating: index.html"], "unresolved": 5})


class CloseoutCarries(unittest.TestCase):
    def test_packaging_note_lines(self):
        import closeout as C
        out = "\n".join(["  upstream: no upstream commits (x)", "  site packaging: pass: y",
                         "  packaging notes: 1 anomaly (1 warn)",
                         "  packaging note: [warn] MODEL_ID_CHANGED: Model ID changed.",
                         "- [warn] MODEL_ID_CHANGED: Model ID changed.", ' "upstream_commits": [],'])
        self.assertEqual(C.site_packaging_lines(out), ["upstream: no upstream commits (x)", "site packaging: pass: y",
                                                       "packaging notes: 1 anomaly (1 warn)",
                                                       "packaging note: [warn] MODEL_ID_CHANGED: Model ID changed."])


if __name__ == "__main__":
    unittest.main()
