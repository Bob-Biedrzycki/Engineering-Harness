"""Unit tests for the fast-edit scope (CAPA 2026-11-23; Bob, chat: "Planset updates should not be of concern or worry
when making model edits. When the model is accepted, thats when the plans should be updated." and "i thought our
harness made sure the correct list updates happened at the correct time.").

    - harness/scripts/model_iterate.py --fast: no drawing generator without --drawings; the closing report is the
      findings of the checks that ran, one carried-to-acceptance line and the fixed footer, last
    - harness/lib/accept_preflight.py: carried-to-acceptance.md, the count line, the footer text
    - harness/scripts/model_accept.py: the preflight draws the drawings, and a drawing error on the full build stops
      the acceptance before model_file.py
    - harness/lib/list_delta.py tag-part-changed and harness/lib/list_from_model.py apply() for it

Scratch folders only; no real list, build or filed file is written. The model_iterate and model_accept tests need a
project (both scripts name its folders on import) and are skipped in the harness master. Stdlib unittest:

    .\\harness\\tools\\venv\\Scripts\\python.exe -m unittest discover -s harness\\tests -v
"""
from __future__ import annotations

import argparse
import contextlib
import csv
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists())
sys.path.insert(0, str(REPO / "harness" / "lib"))
sys.path.insert(0, str(REPO / "harness" / "scripts"))
import repo_paths as rp  # noqa: E402
import accept_preflight as pf  # noqa: E402
import list_delta as LD  # noqa: E402
import list_from_model as LFM  # noqa: E402

FOOTER = """FAST EDIT SCOPE: this build changed the model only. Report the build and stop.
  - Tag lists (02_Tag_Lists) are written from the model by model_accept.py at acceptance. Do not edit them and do not ask Bob to approve a list change.
  - The P&ID, line segment diagram, process flow diagram and plan sets follow the accepted model. Do not run, fix or mention them unless Bob asked for that drawing.
  - Items carried to acceptance are notes for the acceptance run, not questions for Bob."""

CARRIED = [pf.item("delta:tag-part-changed:XV-101", "model and lists disagree: tag-part-changed XV-101"),
           pf.item("delta:line-size:L-110", "model and lists disagree: line-size L-110"),
           pf.item("component:COMP-0098", "COMP-0098 registered 2026-11-23 but not in the model"),
           pf.item("question:Q-0101", "Q-0101 open (2026-11-23): which actuator?")]


class Footer(unittest.TestCase):
    def test_footer_is_exact(self):
        self.assertEqual(pf.FAST_SCOPE_FOOTER, FOOTER)

    def test_carried_line_counts(self):
        with mock.patch.object(pf, "_rel", side_effect=lambda p: "B/revC-fast-001/carried-to-acceptance.md"):
            line = pf.carried_line(CARRIED, Path("x"))
        self.assertEqual(line, "carried to acceptance: 4 item(s) (2 list row(s) the model will write, 1 component(s) "
                               "not placed, 1 open question(s)) -> B/revC-fast-001/carried-to-acceptance.md")

    def test_carried_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = pf.write_carried(CARRIED, Path(d) / pf.CARRIED_NAME, "revC-fast-001", "D")
            text = p.read_text(encoding="utf-8")
        self.assertIn("# Carried to acceptance: revC-fast-001", text)
        self.assertIn("not questions for Bob", text)
        self.assertIn("## 2 list row(s) the model will write", text)
        self.assertIn("- Q-0101 open (2026-11-23): which actuator?", text)
        self.assertIn("**4 item(s).**", text)

    def test_empty_carried(self):
        with tempfile.TemporaryDirectory() as d:
            p = pf.write_carried([], Path(d) / pf.CARRIED_NAME, "revC-fast-001", "D")
            self.assertIn("## 0 open question(s)\n\n- none", p.read_text(encoding="utf-8"))


# ---- tag-part-changed ------------------------------------------------------------------------------------------
LT_SRC = ("ifm PI1708 (COMP-0031, SRC-0055) on tank side port N4: COMP-0067 "
          "(COMP-0067-LT-ifm-PI1708-E30501-tank-side-port-RevD.step)")
MAN = {"items": [
    {"key": "XV-101", "tag": "XV-101", "kind": "valve", "line": "L-110", "source": 'COMP-0096 (Tru-Flo STEP; BFY-316L-E-2"-)'},
    {"key": "XV-102", "tag": "XV-102", "kind": "valve", "line": "L-110", "source": "COMP-0096 (Tru-Flo STEP)"},
    {"key": "XV-103", "tag": "XV-103", "kind": "valve", "line": "L-110", "source": "COMP-0096 (Tru-Flo STEP)"},
    {"key": "HV-401", "tag": "HV-401", "kind": "valve", "line": "L-100", "source": "COMP-0097 (Tru-Flo STEP)"},
    {"key": "LT-101", "tag": "LT-101", "kind": "instrument", "line": "", "source": LT_SRC},
    {"key": "TK-101.N4", "tag": "LT-101", "kind": "nozzle", "line": "", "source": "COMP-0099 (not the tagged part)"},
    {"key": "PT-101", "tag": "PT-101", "kind": "instrument", "line": "L-100", "source": "CPME spool of COMP-0041 and COMP-0036"},
]}
VALVE_HEAD = ("tag,type,size_od_in,actuator,feedback,solenoid,line_no,process_connection,orientation,air_connection,"
              "pid_sheet,notes,component_id")
VALVES = [VALVE_HEAD,
          'XV-101,butterfly,2.0,"old actuator, spring return",old switch,old solenoid,L-110,old clamp,up,1/4 in NPT,1,'
          'first note,CMP-0012',
          "XV-102,butterfly,2.0,canister,top,manifold,L-110,Tri-Clamp,up,1/8 in,1,kept,COMP-0096",
          "XV-103,butterfly,2.0,canister,top,manifold,L-110,Tri-Clamp,up,1/8 in,1,old spelling,CMP-0096",
          "HV-401,manual,2.0,handle,none,none,L-100,unknown,down,none,1,,unknown"]
INSTR_HEAD = ("tag,type,range,process_connection,signal,line_no_or_equip,mounting_orientation,straight_run_req,"
              "access_note,pid_sheet,notes,component_id")
INSTRS = [INSTR_HEAD,
          "LT-101,level,0-10 ft,weld-in,4-20 mA,TK-101,side,none,front,1,,COMP-0067",
          "PT-101,pressure,0-150 psi,clamp,4-20 mA,L-100,side,none,front,1,,COMP-0041"]
REGISTER = [
    {"component_id": "COMP-0096", "status": "current", "category": "butterfly valve (automated)",
     "manufacturer": "Tru-Flo", "model": "BFY-316L 2 in", "part_number": 'BFY-316L-E-2"-MK-K-1111-3-',
     "end_connections": "Tri-Clamp / Tri-Clamp, 2.51 in ferrule"},
    {"component_id": "COMP-0097", "status": "current", "category": "butterfly valve (manual)",
     "manufacturer": "Tru-Flo", "model": "BFY-316L", "part_number": "unknown", "end_connections": "unknown"}]


def _rows(lines: list[str]) -> list[dict]:
    return list(csv.DictReader(io.StringIO("\n".join(lines) + "\n")))


class PlacedComponent(unittest.TestCase):
    def test_rules(self):
        self.assertEqual(LD.placed_component("COMP-0096 (Tru-Flo STEP)"), "COMP-0096")
        self.assertEqual(LD.placed_component("CMP-0011 (CPME layout model)"), "COMP-0011")      # old spelling
        self.assertEqual(LD.placed_component(LT_SRC), "COMP-0067")                             # the STEP it places
        self.assertEqual(LD.placed_component("ifm PI1708 (COMP-0031, SRC-0055)"), "COMP-0031")  # the only id
        self.assertIsNone(LD.placed_component("ifm PI1708 (COMP-0031) in COMP-0066"))          # two, no form
        self.assertIsNone(LD.placed_component("placeholder"))
        self.assertEqual(LD.norm_ids("CMP-0096; COMP-0096, COMP-0011"), ["COMP-0096", "COMP-0011"])


class TagPartChanged(unittest.TestCase):
    def test_detection(self):
        rows, info = LD.part_changes(MAN, [], {"valve-list.csv": _rows(VALVES), "instrument-list.csv": _rows(INSTRS)})
        got = {r["subject"]: r for r in rows}
        self.assertEqual(sorted(got), ["HV-401", "XV-101"])   # XV-102 agrees, XV-103 is CMP- of the same number
        self.assertEqual((got["XV-101"]["model"], got["XV-101"]["lists"]), ("COMP-0096", "CMP-0012"))
        self.assertEqual((got["HV-401"]["model"], got["HV-401"]["lists"]), ("COMP-0097", "unknown"))
        self.assertEqual(got["XV-101"]["kind"], "tag-part-changed")
        self.assertIn("valve-list.csv", got["XV-101"]["detail"])
        self.assertEqual(got["XV-101"]["line_no"], "L-110")
        # LT-101: the tagged item (key == tag) wins over the nozzle carrying the same tag; PT-101 names two ids
        self.assertNotIn("LT-101", got)
        self.assertTrue(any(i.startswith("PT-101:") for i in info))

    def test_bom_source_is_the_fallback(self):
        bom = [{"item": "XV-101", "source": "COMP-0096 (from the BOM)"}]
        rows, _ = LD.part_changes({"items": []}, bom, {"valve-list.csv": _rows(VALVES[:2])})
        self.assertEqual([(r["subject"], r["model"]) for r in rows], [("XV-101", "COMP-0096")])

    def test_list_without_component_column_is_not_compared(self):
        rows, _ = LD.part_changes(MAN, [], {"valve-list.csv": _rows(["tag,type", "XV-101,butterfly"])})
        self.assertEqual(rows, [])


class ApplyPartChange(unittest.TestCase):
    """list_from_model.apply() for tag-part-changed on copies of small lists in a scratch folder."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.data, self.build = root / "lists", root / "build"
        self.data.mkdir()
        self.build.mkdir()
        # the valve list with CRLF line endings, the others LF: each keeps its own
        (self.data / "valve-list.csv").write_bytes(("\r\n".join(VALVES) + "\r\n").encode("utf-8"))
        (self.data / "instrument-list.csv").write_bytes(("\n".join(INSTRS) + "\n").encode("utf-8"))
        (self.data / "line-list.csv").write_bytes(b"line_no,size_od_in,gauge,notes\nL-110,2.0,0.065,\n")
        self.before = {p.name: p.read_bytes() for p in self.data.iterdir()}
        rows, _ = LD.part_changes(MAN, [], {"valve-list.csv": _rows(VALVES), "instrument-list.csv": _rows(INSTRS)})
        with open(self.build / "list-delta.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=LD.FIELDS, lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
        (self.build / "manifest.json").write_text(json.dumps(MAN), encoding="utf-8")
        for p in (mock.patch.object(rp, "DATA", self.data, create=True),
                  mock.patch("components.rows", return_value=[dict(r, _library="job", _root=root) for r in REGISTER])):
            p.start()
            self.addCleanup(p.stop)
        self.report = LFM.apply(self.build, "Rev D")

    def valves(self) -> dict[str, dict]:
        with open(self.data / "valve-list.csv", newline="", encoding="utf-8") as f:
            return {r["tag"]: r for r in csv.DictReader(f)}

    def test_part_swapped_row(self):
        r = self.valves()["XV-101"]
        self.assertEqual(r["component_id"], "COMP-0096")
        self.assertEqual(r["type"], 'butterfly valve (automated) - Tru-Flo BFY-316L 2 in, part number '
                                    'BFY-316L-E-2"-MK-K-1111-3-')
        self.assertEqual(r["process_connection"], "Tri-Clamp / Tri-Clamp, 2.51 in ferrule")
        for c in ("actuator", "feedback", "solenoid", "orientation", "air_connection"):
            self.assertEqual(r[c], "unknown", c)
        self.assertEqual((r["tag"], r["size_od_in"], r["line_no"], r["pid_sheet"]), ("XV-101", "2.0", "L-110", "1"))
        self.assertTrue(r["notes"].startswith("first note || part CMP-0012 -> COMP-0096 from model Rev D ("), r["notes"])

    def test_row_with_no_part_yet(self):
        r = self.valves()["HV-401"]
        self.assertEqual(r["component_id"], "COMP-0097")
        self.assertEqual(r["type"], "manual")              # known, and nothing said it described another part
        self.assertEqual(r["actuator"], "handle")
        self.assertEqual(r["process_connection"], "unknown")   # the register gives unknown too
        self.assertTrue(r["notes"].startswith("part unknown -> COMP-0097 from model Rev D"), r["notes"])

    def test_report_lines(self):
        self.assertEqual(len(self.report), 2)
        self.assertTrue(self.report[0].startswith("valve-list.csv XV-101: part CMP-0012 -> COMP-0096"))
        self.assertIn("old part's columns set to unknown", self.report[0])

    def test_untouched_rows_and_files_are_byte_identical(self):
        new = (self.data / "valve-list.csv").read_bytes()
        self.assertIn(b"\r\n", new)
        self.assertNotIn(b"\n", new.replace(b"\r\n", b""))              # still CRLF only
        old_lines, new_lines = self.before["valve-list.csv"].split(b"\r\n"), new.split(b"\r\n")
        for i in (0, 2, 3):                                              # header, XV-102, XV-103
            self.assertEqual(old_lines[i], new_lines[i])
        self.assertEqual((self.data / "instrument-list.csv").read_bytes(), self.before["instrument-list.csv"])
        self.assertEqual((self.data / "line-list.csv").read_bytes(), self.before["line-list.csv"])


class RetireFastBuildText(unittest.TestCase):
    """REVW-001 C-11 (Bob, chat, 2026-11-23: "Yes, rewrite them"): at acceptance a list row that cites a fast build
    cites the accepted revision instead, and the joints and spools it names are checked against the build."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.data, self.build = root / "lists", root / "build"
        self.data.mkdir()
        self.build.mkdir()
        rows = [VALVE_HEAD,
                'XV-101,butterfly,2.0,canister,top,manifold,L-110,Tri-Clamp,'
                '"fast build revC-fast-023: horizontal, clamp J007 || was: as modeled at Rev B (J099)",1/8 in,1,'
                'kept,COMP-0096',
                "XV-102,butterfly,2.0,canister,top,manifold,L-110,Tri-Clamp,up,1/8 in,1,kept,COMP-0096",
                'HV-401,manual,2.0,handle,none,none,L-100,"J032 on the outlet, stub L-420-SP01 (fast build '
                'revC-fast-028)",fast build revC-fast-028: vertical; J034 below,none,1,,COMP-0097']
        (self.data / "valve-list.csv").write_bytes(("\r\n".join(rows) + "\r\n").encode("utf-8"))
        (self.data / "instrument-list.csv").write_bytes(("\n".join(INSTRS) + "\n").encode("utf-8"))
        (self.data / "line-list.csv").write_bytes(b"line_no,size_od_in,gauge,notes\nL-110,2.0,0.065,\n")
        self.before = {p.name: p.read_bytes() for p in self.data.iterdir()}
        (self.build / "clamp-schedule.csv").write_text("joint_id,line_no\nJ007,L-110\nJ032,L-100\n", encoding="utf-8")
        (self.build / "spool-list.csv").write_text("spool_id,line_no\nL-420-SP01,L-420\n", encoding="utf-8")
        p = mock.patch.object(rp, "DATA", self.data, create=True)
        p.start()
        self.addCleanup(p.stop)
        self.report = LFM.apply(self.build, "Rev D")     # no list-delta.csv: the citation step still runs

    def test_citations_become_the_accepted_revision(self):
        with open(self.data / "valve-list.csv", newline="", encoding="utf-8") as f:
            v = {r["tag"]: r for r in csv.DictReader(f)}
        self.assertEqual(v["XV-101"]["orientation"],
                         "model Rev D: horizontal, clamp J007 || was: as modeled at Rev B (J099)")
        self.assertEqual(v["HV-401"]["orientation"], "model Rev D: vertical; J034 below")
        self.assertEqual(v["HV-401"]["process_connection"], "J032 on the outlet, stub L-420-SP01 (model Rev D)")
        self.assertNotIn(b"fast build", (self.data / "valve-list.csv").read_bytes())

    def test_report_names_what_the_build_does_not_have(self):
        self.assertEqual(self.report, [
            "valve-list.csv XV-101: text that cited fast build revC-fast-023 now cites model Rev D",   # J099 is history
            "valve-list.csv HV-401: text that cited fast build revC-fast-028 now cites model Rev D; it names J034, "
            "which this build does not have: the row's text needs a look"])

    def test_other_rows_and_lists_are_byte_identical(self):
        new = (self.data / "valve-list.csv").read_bytes().split(b"\r\n")
        old = self.before["valve-list.csv"].split(b"\r\n")
        self.assertEqual((old[0], old[2]), (new[0], new[2]))             # header and XV-102
        for n in ("instrument-list.csv", "line-list.csv"):
            self.assertEqual((self.data / n).read_bytes(), self.before[n])
        self.assertEqual(LFM.retire_fast_build_text(self.build, "Rev D"), [])   # a second run changes nothing


# ---- model_iterate --fast and model_accept (need a project) ---------------------------------------------------
@unittest.skipUnless(rp.HAS_PROJECT, "no project yet (model_iterate.py names the project's folders on import)")
class BuildLock(unittest.TestCase):
    """REVW-001 OP-1: one build of a model at a time."""

    def test_second_build_is_refused_and_a_dead_lock_is_taken_over(self):
        sys.path.insert(0, str(rp.SCRIPTS))
        import model_iterate as mi
        with tempfile.TemporaryDirectory() as d:
            builds = Path(d) / "Builds"
            lock, why = mi.take_build_lock(builds, "first request")
            self.assertEqual((lock, why), (builds / mi.LOCK_NAME, ""))
            second, why = mi.take_build_lock(builds, "second request")
            self.assertIsNone(second)
            self.assertIn("another build of this model is running", why)
            self.assertIn("request: first request", why)
            mi.release_build_lock(lock)
            self.assertFalse(lock.exists())
            lock.write_text(json.dumps({"pid": 0, "started": "x", "request": "gone"}), encoding="utf-8")
            with mock.patch.object(mi, "_pid_alive", return_value=False):
                third, why = mi.take_build_lock(builds, "third")
            self.assertEqual((third, why), (lock, ""))
            self.assertEqual(json.loads(lock.read_text(encoding="utf-8"))["request"], "third")
            mi.release_build_lock(third)


@unittest.skipUnless(rp.HAS_PROJECT, "no project yet (model_iterate.py names the project's folders on import)")
class FastBuild(unittest.TestCase):
    def run_fast(self, drawings: bool):
        import model_iterate as mi
        started: list[str] = []

        class FakeStep:
            def __init__(s, name, cmd, logs=None):
                s.name = name
                started.append(name)
                if name == "glb":
                    Path(str(cmd[-1])).write_bytes(b"glb")

            def wait(s):
                return {"exit": 0, "summary": f"{s.name}: ok", "seconds": 0.0, "log": "x"}

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        out = Path(tmp.name) / "revC" / "revC-fast-001"
        logged, finished = [], {}
        start = mock.Mock(return_value={})
        fin = mock.Mock(return_value=([], {"P&ID": {"summary": "model-to-pid: check, 3 clouds", "clouds": 3,
                                                    "log": "l"}}))
        a = argparse.Namespace(keep_going=False, supports=False, drawings=drawings, request="CAPA test",
                               change="none")
        with mock.patch.object(mi, "Step", FakeStep), \
                mock.patch("subprocess.Popen", side_effect=AssertionError("no subprocess may start")), \
                mock.patch.object(mi.mb, "last_revision", return_value="C"), \
                mock.patch.object(mi.mb, "new_build_dir", return_value=out), \
                mock.patch.object(mi.mb, "newest_source", return_value=(0.0, Path(tmp.name) / "src.py")), \
                mock.patch.object(mi.mb, "next_letter", return_value="D"), \
                mock.patch.object(mi.mb, "JOB_LEVEL", False), \
                mock.patch.object(mi.mb, "log_row", side_effect=lambda *x: logged.append(x)), \
                mock.patch.object(mi.rp, "rel", side_effect=lambda p: str(p)), \
                mock.patch.object(mi, "run_list_delta", return_value={"exit": 0, "rows": 2, "seconds": 0.0,
                                                                       "summary": "list_delta: 2 row(s)"}), \
                mock.patch.object(mi.pf, "collect", return_value=list(CARRIED)), \
                mock.patch.object(mi.pf, "start_drawing_checks", start), \
                mock.patch.object(mi.pf, "finish_drawing_checks", fin), \
                mock.patch.object(mi, "finish", side_effect=lambda *x, **k: finished.update(k) or 0), \
                contextlib.redirect_stdout(io.StringIO()) as buf:
            rc = mi.fast(a)
        return rc, started, start, buf.getvalue(), logged, finished, out

    def test_default_draws_nothing(self):
        rc, started, start, text, logged, finished, out = self.run_fast(False)
        self.assertEqual(rc, 0)
        self.assertEqual(sorted(started), ["envelope", "glb", "interference", "lists", "materials"])
        start.assert_not_called()
        self.assertNotIn("check P&ID", text)
        self.assertNotIn("drawings", logged[0][4])
        self.assertTrue((out / pf.CARRIED_NAME).is_file())
        self.assertEqual(len(finished["open_items"]), len(CARRIED))   # every item still reaches iterate-summary.json
        tail = text.rstrip("\n").split("\n")
        self.assertEqual("\n".join(tail[-4:]), FOOTER)
        self.assertTrue(tail[-5].startswith("carried to acceptance: 4 item(s) (2 list row(s) the model will write, "
                                            "1 component(s) not placed, 1 open question(s)) -> "), tail[-5])
        self.assertTrue(tail[-5].endswith(pf.CARRIED_NAME))
        self.assertNotIn("OPEN BEFORE REV", text)
        self.assertNotIn("Q-0101", text)                               # carried items are not printed

    def test_drawings_flag_draws_them(self):
        rc, started, start, text, logged, finished, out = self.run_fast(True)
        start.assert_called_once()
        self.assertEqual(start.call_args[0][0], out)
        self.assertIn("check P&ID", text)
        self.assertIn("drawings PASS", logged[0][4])
        self.assertIn("P&ID", finished["drawings"])
        self.assertEqual("\n".join(text.rstrip("\n").split("\n")[-4:]), FOOTER)


@unittest.skipUnless(rp.HAS_PROJECT, "no project yet (model_accept.py names the project's folders on import)")
class AcceptDrawsBeforeFiling(unittest.TestCase):
    def test_preflight_flags(self):
        import model_accept as ma
        self.assertEqual(ma.PREFLIGHT_FLAGS, ("--fast", "--supports", "--drawings"))

    def test_drawing_error_on_the_full_build_stops_before_model_file(self):
        import model_accept as ma
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        fast = root / "revC-fast-001"
        fast.mkdir()
        (fast / "iterate-summary.json").write_text(json.dumps(
            {"seconds": 1, "open_items": [], "drawing_checks": {"P&ID": {"clouds": 1}}}), encoding="utf-8")
        calls = []

        def fake_run(cmd, echo=True):
            calls.append(" ".join(str(c) for c in cmd))
            if "model_file.py" in calls[-1]:
                raise AssertionError("model_file.py must not run")
            return 0, ""

        bad = [pf.item("drawing:P&ID:error: x", "P&ID cannot be drawn cleanly from this build - error: x "
                                               "(generator log L)", True)]
        argv = ["model_accept.py", "--rev", "D", "--bob", "accept it"]
        with mock.patch.object(sys, "argv", argv), \
                mock.patch.object(ma, "run", side_effect=fake_run), \
                mock.patch.object(ma, "ACCEPT", root / "accept"), \
                mock.patch.object(ma.mb, "last_revision", return_value="C"), \
                mock.patch.object(ma, "latest_fast_build", return_value=fast), \
                mock.patch("list_from_model.apply", return_value=[]), \
                mock.patch.object(ma.pf, "close_out_checks", return_value=[]), \
                mock.patch.object(ma.mb, "use_build"), \
                mock.patch.object(ma.mb, "BUILD", root / "revC-full-002"), \
                mock.patch.object(ma.pf, "start_drawing_checks", return_value={}) as start, \
                mock.patch.object(ma.pf, "finish_drawing_checks", return_value=(bad, {})), \
                mock.patch.object(ma.rp, "rel", side_effect=lambda p: str(p)), \
                contextlib.redirect_stdout(io.StringIO()) as buf:
            rc = ma.main()
        self.assertEqual(rc, 3)
        self.assertEqual(start.call_args[0][0], root / "revC-full-002")
        self.assertTrue(any("--drawings" in c for c in calls))             # the preflight drew them
        self.assertFalse(any("model_file.py" in c for c in calls))
        self.assertIn("NOTHING FILED", buf.getvalue())
        self.assertIn("generator log L", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
