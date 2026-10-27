"""Unit tests for the day's one go in harness/scripts/track.py (Bob, 2026-10-07: "THIS SHOULD BE 1 "GO" THEN MY
MERGE. THE SYNC SHOULD BE AUTOMATED."): `daily` (go file, close-out, commit, PR) and `after-merge` (merged-PR check,
sync-main, site publish), plus the shared pieces they lean on (site_revs, closeout.check_status).

subprocess, gh and the commit / PR / sync commands are mocked: no network, no git write, no repo file written
(the go file goes to a temporary folder). Stdlib unittest, as CI runs it:

    .\\harness\\tools\\venv\\Scripts\\python.exe -m unittest discover -s harness\\tests -v
"""
from __future__ import annotations

import argparse
import contextlib
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists())
sys.path.insert(0, str(REPO / "harness" / "scripts"))
sys.path.insert(0, str(REPO / "harness" / "lib"))
import repo_paths as rp  # noqa: E402
if not rp.HAS_PROJECT:
    raise unittest.SkipTest("no project yet (the daily close-out works on a project)")
_saved = os.environ.get("GH_CONFIG_DIR")
import track as T  # noqa: E402  (importing sets GH_CONFIG_DIR in os.environ; restored in tearDownModule)
import closeout as C  # noqa: E402
import drive_rules  # noqa: E402
import linear_loops  # noqa: E402
import site_revs  # noqa: E402

# Fixture paths in the project-folder layout (Bob, 2026-10-26); a made-up project, never on disk in the repo.
PROJ = "job/Project-0000-00-TST-001"
PORTALS_DIR = f"{PROJ}/06_Issued_Revisions/Portals"
PORTAL_DIR = f"{PORTALS_DIR}/project-portal"
MODELS_DIR = f"{PROJ}/06_Issued_Revisions/Models"
WORK_DIR = f"{PROJ}/_work"

MSG = """docs: test commit subject

**Why**
x
**Changed IDs**
x
**Sources and rules cited**
x
**TR rows touched**
x
**Drawings filed**
- none
**Checks run**
x
"""
BODY = "## Todd's requirements\n- TR-11\n## Drawings filed\n- none\nRelates to CPM-152\n"


def tearDownModule() -> None:
    if _saved is None:
        os.environ.pop("GH_CONFIG_DIR", None)
    else:
        os.environ["GH_CONFIG_DIR"] = _saved


class Base(unittest.TestCase):
    """A temporary <project>/_work/daily/ and input files; T.DRY restored after each test."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.daily = self.tmp / "daily"
        p = mock.patch.object(T.rp, "DAILY", self.daily)
        p.start()
        self.addCleanup(p.stop)
        self._dry = T.DRY
        self.addCleanup(setattr, T, "DRY", self._dry)
        T.DRY = False
        self.addCleanup(self._tmp.cleanup)
        (self.tmp / "paths.txt").write_text(f"harness/scripts/track.py\n{PORTAL_DIR}\n", encoding="utf-8")
        (self.tmp / "msg.md").write_text(MSG, encoding="utf-8")
        (self.tmp / "body.md").write_text(BODY, encoding="utf-8")

    def args(self, **kw) -> argparse.Namespace:
        d = dict(date="2026-10-07", paths_file=str(self.tmp / "paths.txt"), message_file=str(self.tmp / "msg.md"),
                 title="Daily 2026-10-07: test", body_file=str(self.tmp / "body.md"), tag=[], bob_go="GO",
                 local=False, start=None, moves_file=None, removes_file=None, closes=[], reviewer=[], base=None)
        d.update(kw)
        return argparse.Namespace(**d)

    def refused(self, fn, *a):
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()), \
                self.assertRaises(SystemExit) as cm:
            fn(*a)
        self.assertEqual(cm.exception.code, 2)
        return err.getvalue()


class GoFile(Base):
    def test_written_once_verbatim(self):
        with contextlib.redirect_stdout(io.StringIO()):
            p = T.save_go("2026-10-07", 'THIS SHOULD BE 1 "GO"')
        self.assertEqual(p, self.daily / "2026-10-07-go.txt")
        self.assertEqual(p.read_text(encoding="utf-8"), 'THIS SHOULD BE 1 "GO"\n')
        with contextlib.redirect_stdout(io.StringIO()) as out:   # a rerun with the same words is fine
            T.save_go("2026-10-07", 'THIS SHOULD BE 1 "GO"')
        self.assertIn("already holds these words", out.getvalue())
        self.assertEqual(T.read_go("2026-10-07"), 'THIS SHOULD BE 1 "GO"')

    def test_different_words_refused(self):
        with contextlib.redirect_stdout(io.StringIO()):
            T.save_go("2026-10-07", "go")
        err = self.refused(T.save_go, "2026-10-07", "go, and publish")
        self.assertIn("already holds the go", err)
        self.assertEqual((self.daily / "2026-10-07-go.txt").read_text(encoding="utf-8"), "go\n")   # untouched

    def test_read_missing_refused(self):
        self.assertIn("no go file", self.refused(T.read_go, "2026-10-07"))

    def test_ps_quote(self):
        self.assertEqual(T.ps_quote('1 "GO" it\'s'), "'1 \\\"GO\\\" it''s'")


class Daily(Base):
    def run_daily(self, closeout_rc: int, dry: bool = False, **kw):
        T.DRY = dry
        calls = []
        with mock.patch.object(T, "run_closeout", side_effect=lambda d, g, dr: calls.append((d, g, dr)) or closeout_rc), \
                mock.patch.object(T, "cmd_daily_commit") as commit, \
                mock.patch.object(T, "cmd_daily_pr", return_value="" if dry else "https://github.com/o/r/pull/12") as pr, \
                mock.patch.object(T, "uncovered_filed_reviews", return_value=[]), \
                contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()):
            code = None
            try:
                T.cmd_daily(self.args(**kw))
            except SystemExit as e:
                code = e.code
        return code, calls, commit, pr, out.getvalue()

    def test_stops_when_closeout_fails(self):
        for rc in (1, 2, 3):
            code, calls, commit, pr, out = self.run_daily(rc)
            self.assertEqual(code, rc, f"daily exits with close-out's code {rc}")
            commit.assert_not_called()
            pr.assert_not_called()
            self.assertIn(f"closeout: exit {rc}", out)
        self.assertIn("list delta", self.run_daily(3)[4])

    def test_success_runs_commit_then_pr_and_prints_url(self):
        # after close-out the paths are checked to exist: name only a real path here (the fixture project is not on disk)
        (self.tmp / "paths.txt").write_text("harness/scripts/track.py\n", encoding="utf-8")
        code, calls, commit, pr, out = self.run_daily(0)
        self.assertIsNone(code)
        self.assertEqual(calls, [("2026-10-07", "GO", False)])
        commit.assert_called_once()
        pr.assert_called_once()
        self.assertIn("PR: https://github.com/o/r/pull/12", out.splitlines())
        self.assertEqual((self.daily / "2026-10-07-go.txt").read_text(encoding="utf-8"), "GO\n")

    def test_dry_run_writes_no_go_file(self):
        code, calls, commit, pr, out = self.run_daily(0, dry=True)
        self.assertIsNone(code)
        self.assertEqual(calls, [("2026-10-07", "GO", True)])
        self.assertFalse((self.daily / "2026-10-07-go.txt").exists())
        commit.assert_called_once()
        pr.assert_called_once()
        self.assertIn("PR: (dry run)", out.splitlines())

    def test_bad_inputs_refused_before_closeout(self):
        (self.tmp / "msg.md").write_text(MSG.replace("**Checks run**", ""), encoding="utf-8")
        code, calls, commit, *_ = self.run_daily(0)
        self.assertEqual(code, 2)
        self.assertEqual(calls, [], "close-out never runs on inputs the commit would refuse")
        self.assertFalse((self.daily / "2026-10-07-go.txt").exists())

    def test_skeleton_placeholder_refused(self):
        (self.tmp / "msg.md").write_text(MSG + "<fill: other rows>\n", encoding="utf-8")
        self.assertEqual(self.run_daily(0)[0], 2)

    def test_closeout_output_files_refused(self):
        self.daily.mkdir(parents=True)
        own = self.daily / "2026-10-07-commit.md"
        own.write_text(MSG, encoding="utf-8")
        code, calls, *_ = self.run_daily(0, message_file=str(own))
        self.assertEqual(code, 2)
        self.assertEqual(calls, [])

    def test_no_go_refused(self):
        self.assertEqual(self.run_daily(0, bob_go=None)[0], 2)

    def test_dry_run_needs_no_go(self):
        code, calls, commit, pr, out = self.run_daily(0, dry=True, bob_go=None)
        self.assertIsNone(code)
        self.assertEqual(len(calls), 1)
        self.assertFalse((self.daily / "2026-10-07-go.txt").exists())


class UncoveredFiledReviews(Base):
    def test_rows_dated_today_must_be_covered(self):
        reviews = self.tmp / PORTAL_DIR
        reviews.mkdir(parents=True)
        (reviews / "revisions.csv").write_text(
            "document_id,revision,file,file_date\nproject-portal,I,project-portal-revI/index.html,2026-10-05\n"
            "project-portal,J,project-portal-revJ/index.html,2026-10-07T18:00\n", encoding="utf-8")
        with mock.patch.object(T.rp, "PORTALS", self.tmp / PORTALS_DIR), mock.patch.object(T.rp, "rel",
                                                                                 lambda p: Path(p).relative_to(self.tmp).as_posix()):
            self.assertEqual(T.uncovered_filed_reviews("2026-10-07", ["harness/scripts/track.py"]),
                             [f"{PORTAL_DIR}/project-portal-revJ/index.html",
                              f"{PORTAL_DIR}/revisions.csv"])
            self.assertEqual(T.uncovered_filed_reviews("2026-10-07", [f"{PORTAL_DIR}/"]), [])
            self.assertEqual(T.uncovered_filed_reviews("2026-10-06", []), [])


class AfterMerge(Base):
    PRS = '[{"number": 12, "state": "MERGED", "url": "https://github.com/o/r/pull/12"}]'

    def run_after(self, prs_json: str | None, dry: bool = False):
        T.DRY = dry
        with mock.patch.object(T, "require_auth"), mock.patch.object(T, "repo_slug", return_value="o/r"), \
                mock.patch.object(T, "gh", return_value=prs_json or "[]") as gh, \
                mock.patch.object(T, "cmd_sync_main") as sync, \
                mock.patch.object(T, "publish_after_merge") as pub, \
                contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()) as err:
            code = None
            try:
                T.cmd_after_merge(argparse.Namespace(date="2026-10-07"))
            except SystemExit as e:
                code = e.code
        return code, gh, sync, pub, out.getvalue() + err.getvalue()

    def write_go(self):
        self.daily.mkdir(parents=True, exist_ok=True)
        (self.daily / "2026-10-07-go.txt").write_text("GO\n", encoding="utf-8")

    def test_refused_without_go_file(self):
        code, gh, sync, pub, out = self.run_after(self.PRS)
        self.assertEqual(code, 2)
        self.assertIn("no go file", out)
        gh.assert_not_called()
        sync.assert_not_called()
        pub.assert_not_called()

    def test_refused_without_merged_pr(self):
        self.write_go()
        for prs in ("[]", '[{"number": 12, "state": "OPEN", "url": "u12"}]',
                    '[{"number": 12, "state": "CLOSED", "url": "u12"}]',
                    '[{"number": 11, "state": "MERGED", "url": "u11"}, {"number": 12, "state": "OPEN", "url": "u12"}]'):
            code, gh, sync, pub, out = self.run_after(prs)
            self.assertEqual(code, 2, prs)
            sync.assert_not_called()
            pub.assert_not_called()

    def test_merged_runs_sync_then_publish_with_the_go(self):
        self.write_go()
        code, gh, sync, pub, out = self.run_after(self.PRS)
        self.assertIsNone(code)
        self.assertEqual(sync.call_args[0][0].bob_go, "GO")
        pub.assert_called_once_with("GO")
        self.assertIn("PR: merged https://github.com/o/r/pull/12", out)
        self.assertIn("sync-main: done", out)

    def test_merge_refusal(self):
        self.assertIsNone(T.merge_refusal([{"state": "MERGED", "url": "a"}, {"state": "MERGED", "url": "b"}], "d"))
        self.assertIn("run `track.py daily`", T.merge_refusal([], "daily/2026-10-07"))


class PublishAfterMerge(Base):
    REVS = {"rev": "J", "quoting": "E", "landing": "D"}

    def dry_out(self, added=0, changed=0, removed=0):
        return (f"publish_site (DRY RUN: nothing written, committed or pushed)\n"
                f"  vs site: {added} added, {changed} changed, 3005 unchanged, {removed} removed (KEEP: .git)\n")

    def run_pub(self, results, dry=False):
        T.DRY = dry
        it = iter(results)
        calls = []

        def fake_run(cmd, **kw):
            calls.append(cmd)
            rc, out = next(it)
            return subprocess.CompletedProcess(cmd, rc, out, "")
        with mock.patch.object(T.site_revs, "newest", return_value=dict(self.REVS)), \
                mock.patch.object(T.site_revs, "site_dormant", return_value=None), \
                mock.patch.object(T.subprocess, "run", side_effect=fake_run), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            code = None
            try:
                T.publish_after_merge('1 "GO"')
            except SystemExit as e:
                code = e.code
        return code, calls, out.getvalue()

    def test_skipped_when_no_difference(self):
        code, calls, out = self.run_pub([(0, self.dry_out())])
        self.assertIsNone(code)
        self.assertEqual(len(calls), 1, "only the dry run runs")
        self.assertIn("--dry-run", calls[0])
        self.assertEqual(calls[0][2:10], ["--rev", "J", "--quoting", "E", "--landing", "D", "--mobile", "none"])
        self.assertIn("publish skipped", out)

    def test_publishes_when_the_site_differs(self):
        code, calls, out = self.run_pub([(0, self.dry_out(added=12, changed=3)), (0, "published")])
        self.assertIsNone(code)
        self.assertEqual(len(calls), 2)
        self.assertNotIn("--dry-run", calls[1])
        self.assertEqual(calls[1][-2:], ["--bob-go", '1 "GO"'])

    def test_dry_run_never_publishes(self):
        code, calls, out = self.run_pub([(0, self.dry_out(removed=1))], dry=True)
        self.assertIsNone(code)
        self.assertEqual(len(calls), 1)
        self.assertIn("DRY-RUN would publish", out)

    def test_refused_publish_prints_command_and_exits_2(self):
        code, calls, out = self.run_pub([(0, self.dry_out(changed=1)), (2, "")])
        self.assertEqual(code, 2)
        self.assertIn(r"harness\scripts\publish_site.py --rev J --quoting E --landing D --mobile none --bob-go '1 \"GO\"'",
                      out)

    def test_dry_run_refused_exits_2(self):
        code, calls, out = self.run_pub([(2, "REFUSED: the site checkout is on x, not main")])
        self.assertEqual(code, 2)
        self.assertEqual(len(calls), 1)

    def test_no_site_yet_publishes_nothing(self):
        T.DRY = False
        with mock.patch.object(T.site_revs, "site_dormant", return_value="no presentation site yet (test)"), \
                mock.patch.object(T.subprocess, "run") as run, contextlib.redirect_stdout(io.StringIO()) as out:
            T.publish_after_merge("GO")
        run.assert_not_called()
        self.assertIn("no presentation site yet (test); nothing to publish", out.getvalue())

    def test_site_difference(self):
        self.assertEqual(T.site_difference(self.dry_out(1, 2, 3)), (1, 2, 3))
        self.assertIsNone(T.site_difference("REFUSED: no"))


class SiteRevs(unittest.TestCase):
    def test_publish_args(self):
        self.assertEqual(site_revs.publish_args({"rev": "J", "quoting": "E", "landing": "D"}),
                         ["--rev", "J", "--quoting", "E", "--landing", "D", "--mobile", "none"])
        self.assertEqual(site_revs.publish_args({"rev": "J", "quoting": "E", "landing": "D", "mobile": "B"}),
                         ["--rev", "J", "--quoting", "E", "--landing", "D", "--mobile", "B"])
        self.assertEqual(site_revs.publish_args({"rev": "J", "quoting": None, "landing": "D"}),
                         ["--rev", "J", "--quoting", "none"])
        with self.assertRaises(ValueError):
            site_revs.publish_args({"rev": None})

    def test_newest_is_last_row(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "revisions.csv").write_text("document_id,revision,file\nx,A,a\nx,B,b\nx,B,c\n", encoding="utf-8")
            self.assertEqual(site_revs.newest({"rev": Path(d), "quoting": Path(d) / "none"}),
                             {"rev": "B", "quoting": None})

    def test_closeout_and_publish_share_it(self):
        src = (REPO / "harness" / "scripts" / "closeout.py").read_text(encoding="utf-8")
        self.assertIn("site_revs.newest()", src)
        pub = (REPO / "harness" / "scripts" / "publish_site.py").read_text(encoding="utf-8")
        self.assertIn("site_revs.newest(", pub)


class CloseoutCheckStatus(unittest.TestCase):
    """closeout.py judges checks as CI does (run_checks.sh), so a design finding does not stop `track.py daily`."""

    def test_classes(self):
        self.assertEqual(C.check_status("sanitary", 0, "sanitary: PASS"), "PASS")
        self.assertEqual(C.check_status("tag_crosscheck", 2, "tag_crosscheck: NOT IMPLEMENTED"), "NOT IMPLEMENTED")
        self.assertEqual(C.check_status("sanitary", 1, "sanitary: FAIL - 4 of 33 rows"), "FINDINGS")
        self.assertEqual(C.check_status("portal_terms", 1, "portal_terms: PASS a\nportal_terms: FAIL b"), "FINDINGS")
        self.assertEqual(C.check_status("drive_pointers", 1, "drive_pointers: FAIL - 1 problem"), "FAIL")
        self.assertEqual(C.check_status("sanitary", 1, "something else"), "ERROR")
        self.assertEqual(C.check_status("sanitary", 3, "sanitary: ERROR - could not run"), "ERROR")
        self.assertEqual(C.check_status("sanitary", 0, "Traceback (most recent call last):\n  x"), "ERROR")

    def test_site_steps_pass_while_dormant(self):
        """CPME practice: with no presentation site, close-out's media, portal and site-plan steps say so and pass."""
        why = "no presentation site yet (test)"
        with mock.patch.object(C.site_revs, "site_dormant", return_value=why), \
                mock.patch.object(C, "run", side_effect=AssertionError("nothing may run")), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            R = C.Report()
            C.step_media(R, False, "A")
            C.step_portal(R, False, "A", "2026-10-26", False)
            C.step_site_plan(R, False)
            C.step_media(C.Report(), True, "A")
        self.assertEqual(R.failed, [])
        self.assertEqual([n for n, _ in R.steps], ["portal media", "portal", "site plan"])
        self.assertTrue(all(res == f"{why}; passed" for _, res in R.steps))
        self.assertIn(f"{why}; passed", out.getvalue())

    def test_list_delta_starts_a_missing_prr_file(self):
        with tempfile.TemporaryDirectory() as d:
            prr = Path(d) / "sub" / "pid-revision-requests.md"
            delta = {"rows": [{"kind": "line-size", "subject": "W-901", "line_no": "W-901", "model": "2", "lists": "3",
                               "detail": "x"}], "n_list_tags": 0, "n_spools": 1}
            import list_delta
            with mock.patch.object(C, "PRR", prr), mock.patch.object(list_delta, "compute", return_value=delta), \
                    mock.patch.object(C, "run", return_value=(0, "")), \
                    mock.patch.object(C.rp, "rel", side_effect=lambda p: str(p)), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertTrue(C.step_list_delta(C.Report(), False, "A", "2026-10-26"))
            text = prr.read_text(encoding="utf-8")
        self.assertTrue(text.startswith(C.PRR_HEADER))
        self.assertIn("| line-size | W-901 |", text)

    def test_hard_fail_list_matches_ci(self):
        sh = (REPO / "harness" / "scripts" / "run_checks.sh").read_text(encoding="utf-8")
        m = re.search(r'^HARD_FAIL_CHECKS="([^"]*)"', sh, re.M)
        self.assertIsNotNone(m)
        self.assertEqual({n.removesuffix(".py") for n in m.group(1).split()}, C.HARD_FAIL_CHECKS)


MP4 = f"{PORTAL_DIR}/project-portal-revJ/assets/media/turntable.mp4"
OUTSIDE = ["__pycache__/", f"{WORK_DIR}/"]
BLOCK_OLD = [drive_rules.BLOCK_BEGIN, "# Files in the Google Drive store.", f"/{MODELS_DIR}/**/*.step",
             f"/{PORTAL_DIR}/**/*.glb", drive_rules.BLOCK_END]
BLOCK_NEW = BLOCK_OLD[:-1] + ["/" + MP4, drive_rules.BLOCK_END]
CFG = drive_rules.normalize({"large_file_bytes": 1000, "exclude": [".git", WORK_DIR],
                             "directories": {MODELS_DIR: ["step"], f"{PORTAL_DIR}": ["glb"]}})


def gi_text(outside, block) -> str:
    return "\n".join(outside + [""] + block) + "\n"


class DriveStoreCommit(Base):
    """The daily commit and the Drive store: the defect of 2026-10-07, where
    `git add` of a portal folder took the 10.2 MB turntable.mp4 because .gitignore was not in the paths."""

    def setUp(self):
        super().setUp()
        self.repo = self.tmp / "repo"
        for rel, data in ((f"{PORTAL_DIR}/revisions.csv", b"document_id,revision\n"),
                          (f"{PORTAL_DIR}/project-portal-revJ/index.html", b"<html></html>\n"),
                          (MP4, b"\0" * 2000)):   # over CFG's 1,000-byte limit (the .gitignore stays under it)
            (self.repo / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.repo / rel).write_bytes(data)
        (self.repo / ".gitignore").write_text(gi_text(OUTSIDE, BLOCK_NEW), encoding="utf-8")
        self.base_gi = gi_text(OUTSIDE, BLOCK_OLD)   # the branch's copy, before close-out added the mp4 line
        self.base_tree = {".gitignore": "aa", f"{PORTAL_DIR}/revisions.csv": "bb"}
        for target, value in ((T, "REPO"), (T, "drive_cfg")):
            p = mock.patch.object(target, value, self.repo if value == "REPO" else (lambda: CFG))
            p.start()
            self.addCleanup(p.stop)
        self.wt = self.tmp / "repo-daily-2026-10-07"
        self.added: list[str] = []
        self.wt_files: list[str] = []
        self.addCleanup(shutil.rmtree, self.wt, True)

    def fake_git(self, *args, cwd=None, write=False, check=True):
        """git as daily-commit uses it, no repository: a new day's branch from origin/main."""
        if args[:2] == ("branch", "--list") or args[:3] == ("rev-parse", "--verify", "--quiet") and "refs/remotes" in args[3]:
            return ""
        if args[0] == "rev-parse":
            return "abc123\n"
        if args[0] == "show":
            return self.base_gi if args[1].endswith(":.gitignore") else ""
        if args[0] == "ls-tree":
            return "".join(f"100644 blob {h}\t{p}\0" for p, h in self.base_tree.items())
        if args[:2] == ("worktree", "add"):
            self.wt.mkdir(parents=True)
            return ""
        if args[0] == "add":
            spec = Path(args[1].split("=", 1)[1])
            self.added = spec.read_text(encoding="utf-8").split()
            self.wt_files = sorted(p.relative_to(self.wt).as_posix() for p in self.wt.rglob("*") if p.is_file())
            return ""
        if args[0] in ("commit", "tag") or args[:2] == ("worktree", "remove"):
            return ""
        raise AssertionError(f"unexpected git call {args}")

    def commit(self, paths: str, ignored=None, **kw):
        """Run daily-commit --local with mocked git; `ignored` is what git check-ignore would report (None = real)."""
        (self.tmp / "p.txt").write_text(paths, encoding="utf-8")
        patches = [mock.patch.object(T, "git", side_effect=self.fake_git)]
        if ignored is not None:
            patches.append(mock.patch.object(T, "ignored_by", side_effect=lambda gis, rels: set(ignored) & set(rels)))
        out, err = io.StringIO(), io.StringIO()
        code = None
        with contextlib.ExitStack() as st:
            mocks = [st.enter_context(p) for p in patches]
            st.enter_context(contextlib.redirect_stdout(out))
            st.enter_context(contextlib.redirect_stderr(err))
            try:
                T.cmd_daily_commit(self.args(paths_file=str(self.tmp / "p.txt"), local=True, **kw))
            except SystemExit as e:
                code = e.code
        self.ignored_mock = mocks[1] if len(mocks) > 1 else None
        return code, out.getvalue(), err.getvalue()

    def pointer(self):
        (self.repo / (MP4 + ".drive")).write_text('{"path": "%s"}\n' % MP4, encoding="utf-8")

    # 1. .gitignore joins the paths when only its managed block changed
    def test_gitignore_added_when_block_changed(self):
        with contextlib.redirect_stdout(io.StringIO()) as out, mock.patch.object(T, "git", side_effect=self.fake_git):
            got = T.gitignore_autoadd([f"{PORTAL_DIR}"], "origin/main")
        self.assertEqual(got, [f"{PORTAL_DIR}", ".gitignore"])
        self.assertEqual(len(out.getvalue().splitlines()), 1)
        self.assertIn("paths: added .gitignore", out.getvalue())

    def test_gitignore_not_added_otherwise(self):
        cases = {"same": (gi_text(OUTSIDE, BLOCK_NEW), "", ["x"]),
                 "outside edit": (gi_text(OUTSIDE[:1], BLOCK_OLD), "WARNING", ["x"]),
                 "already listed": (self.base_gi, "", ["x", "./.gitignore"])}
        for name, (base, said, paths) in cases.items():
            self.base_gi = base
            with contextlib.redirect_stdout(io.StringIO()) as out, mock.patch.object(T, "git", side_effect=self.fake_git):
                got = T.gitignore_autoadd(list(paths), "origin/main")
            self.assertEqual(got, paths, name)
            self.assertNotIn("added .gitignore", out.getvalue(), name)
            if said:
                self.assertIn(said, out.getvalue(), name)

    def test_gitignore_change_kinds(self):
        self.assertEqual(drive_rules.gitignore_change(gi_text(OUTSIDE, BLOCK_OLD), gi_text(OUTSIDE, BLOCK_NEW)), "block")
        self.assertEqual(drive_rules.gitignore_change("a\nb\n", "a\nb\n"), "same")
        self.assertEqual(drive_rules.gitignore_change("a\n", "a\n\n" + "\n".join(BLOCK_OLD) + "\n"), "block")
        self.assertEqual(drive_rules.gitignore_change(gi_text(["a"], BLOCK_OLD), gi_text(["a", "b"], BLOCK_NEW)), "outside")
        self.assertEqual(drive_rules.gitignore_change("a\r\nb\r\n", "a\nb\n"), "same")

    # 2. a selected large file without its pointer is refused, before any worktree exists
    def test_selected_file_without_pointer_refused(self):
        code, out, err = self.commit(f"{PORTAL_DIR}\n", ignored=[MP4])
        self.assertEqual(code, 2)
        self.assertIn("REFUSED:", err)
        self.assertIn(MP4 + " (2,000 B, rule size): no pointer", err)
        self.assertIn("List its pointer instead: " + MP4 + ".drive", err)
        self.assertFalse(self.wt.exists(), "refused before the worktree was made")
        self.assertEqual(self.added, [])

    def test_selected_file_not_ignored_refused(self):
        self.pointer()
        code, out, err = self.commit(f"{PORTAL_DIR}\n", ignored=[])
        self.assertEqual(code, 2)
        self.assertIn("not ignored by the .gitignore this commit carries", err)

    def test_selected_file_still_tracked_on_base_refused(self):
        self.pointer()
        self.base_tree[MP4] = "cc"
        code, out, err = self.commit(f"{PORTAL_DIR}\n", ignored=[MP4])
        self.assertEqual(code, 2)
        self.assertIn("still tracked on origin/main (list it in --removes-file)", err)

    # 3. with its pointer and ignored, the file stays out of the add and out of the worktree
    def test_pointer_and_ignored_skipped_from_add(self):
        self.pointer()
        code, out, err = self.commit(f"{PORTAL_DIR}\n", ignored=[MP4])
        self.assertIsNone(code, err)
        self.assertEqual(self.added, [f"{PORTAL_DIR}", ".gitignore"])
        self.assertIn(MP4 + ".drive", self.wt_files)
        self.assertNotIn(MP4, self.wt_files)
        self.assertIn(".gitignore", self.wt_files)
        self.assertIn("paths: added .gitignore", out)
        self.assertIn("Drive store: 1 file(s) under the listed paths stay out of the commit", out)
        gis, rels = self.ignored_mock.call_args[0]
        self.assertEqual(rels, [MP4])
        self.assertIn("/" + MP4, gis[".gitignore"], "checked against the .gitignore the commit carries")

    def test_selected_file_listed_by_name_becomes_its_pointer(self):
        self.pointer()
        code, out, err = self.commit(MP4 + "\n", ignored=[MP4])
        self.assertIsNone(code, err)
        self.assertEqual(self.added, [MP4 + ".drive", ".gitignore"])
        self.assertNotIn(MP4, self.wt_files)

    @unittest.skipUnless(shutil.which("git"), "git not installed")
    def test_pr12_replay_with_git_check_ignore(self):
        """The 2026-10-07 case end to end, with git's own ignore matching in a scratch repository."""
        self.pointer()
        code, out, err = self.commit(f"{PORTAL_DIR}\n")
        self.assertIsNone(code, err)
        self.assertNotIn(MP4, self.wt_files)
        self.assertIn(".gitignore", self.added)
        # without the new block line (the branch's old .gitignore) git does not ignore it, so the commit is refused
        (self.repo / ".gitignore").write_text(self.base_gi, encoding="utf-8")
        shutil.rmtree(self.wt, ignore_errors=True)
        code, out, err = self.commit(f"{PORTAL_DIR}\n")
        self.assertEqual(code, 2)
        self.assertIn("not ignored by the .gitignore this commit carries", err)

    @unittest.skipUnless(shutil.which("git"), "git not installed")
    def test_ignored_by_uses_only_the_given_gitignore(self):
        gis = {".gitignore": gi_text(OUTSIDE, BLOCK_NEW)}
        self.assertEqual(T.ignored_by(gis, [MP4, f"{PORTAL_DIR}/a.glb", f"{PORTALS_DIR}/x.mp4",
                                            f"{WORK_DIR}/anything.txt"]),
                         {MP4, f"{PORTAL_DIR}/a.glb", f"{WORK_DIR}/anything.txt"})
        self.assertEqual(T.ignored_by({".gitignore": ""}, [MP4]), set())


class HandoffFiles(unittest.TestCase):
    def test_go_file_is_not_a_handoff(self):
        with tempfile.TemporaryDirectory() as d:
            for n in ("2026-10-07-go.txt", "2026-10-07-paths.txt", "2026-10-07-commit.md", "2026-10-07-sd-CPM-153.md"):
                (Path(d) / n).write_text("x", encoding="utf-8")
            self.assertEqual([p.name for p in linear_loops.handoff_files(Path(d), "2026-10-07")],
                             ["2026-10-07-sd-CPM-153.md"])


class Parser(unittest.TestCase):
    def setUp(self):
        self.addCleanup(setattr, T, "DRY", T.DRY)   # main() sets the global

    def test_new_subcommands_parse(self):
        argv = ["track.py", "daily", "--date", "2026-10-07", "--paths-file", "p", "--message-file", "m", "--title", "t",
                "--body-file", "b", "--tag", "X-revA", "--bob-go", "go", "--dry-run"]
        seen = {}
        with mock.patch.object(sys, "argv", argv), mock.patch.object(T, "cmd_daily", side_effect=lambda a: seen.update(vars(a))):
            T.main()
        self.assertTrue(seen["dry_run"])
        self.assertEqual(seen["tag"], ["X-revA"])
        self.assertEqual((seen["local"], seen["closes"], seen["base"]), (False, [], None))
        with mock.patch.object(sys, "argv", ["track.py", "after-merge", "--date", "2026-10-07"]), \
                mock.patch.object(T, "cmd_after_merge", side_effect=lambda a: seen.update(after=a.date)):
            T.main()
        self.assertEqual(seen["after"], "2026-10-07")


if __name__ == "__main__":
    unittest.main()
