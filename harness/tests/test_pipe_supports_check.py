"""Unit tests for harness/checks/pipe_supports.py (STR-PS-002 network; scope and weights, CPME practice).

Synthetic line built with the skidlib LineWalker (the records the skid model uses): TIE (x 0) > 30 in tube >
in-line instrument FT-T as one 20 in span (x 30..50) > 30 in tube > end. FT-T is made a placed instrument spool
part with a straight-run tube L-T-SP02.pc02 at x 33..47 (as build_inst_spools records it). The network cases need the
project's skidlib and are skipped while the project has no model source; the rule reader (both layouts, service
class scope), the recorded-weight reader and the not-checked exit always run. Stdlib unittest only:

    .\\harness\\tools\\venv\\Scripts\\python.exe -m unittest discover -s harness\\tests -v
"""
from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists())
sys.path.insert(0, str(REPO / "harness" / "lib"))
sys.path.insert(0, str(REPO / "harness" / "checks"))
import repo_paths as rp  # noqa: E402

if rp.HAS_PROJECT:
    sys.path.insert(0, str(rp.SKID_MODEL))
import pipe_supports as PS  # noqa: E402

try:
    from skidlib.model import Item, Model, Piece, Spool  # noqa: E402
    SKIDLIB = True
except ImportError:      # no model source on this project yet
    SKIDLIB = False
needs_skidlib = unittest.skipUnless(SKIDLIB, "no skidlib (no project or no model source yet)")

RULES = {"min_slope_in_per_ft": 0.125, "walls": {2.0: 0.065}, "tube_spec": "ASTM A270 S2", "grade": "316L"}
W_FT = 10.0   # a recorded weight for the synthetic FT-T (test value, not a design value)


def hanger(m, n, x, role):
    """PS-nnn support member with its role, and its PS-nnn-HGR hanger centred on the line at x."""
    rod = Item(key=f"PS-{n:03d}", tag=f"PS-{n:03d}", kind="support", source="test",
               member={"role": f"{role}, support tube", "length": 10.0})
    m.add_item(rod)
    m.add_item(Item(key=f"PS-{n:03d}-HGR", tag=rod.key, kind="support", source="test",
                    step={"plane_origin": (x, 0.0, 0.0)}))


def build(hanger_on_spool=True):
    m = Model(RULES)
    w = m.walker("L-T", 2.0)
    w.start((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), "TIE-T")
    w.fwd(30.0)
    it = w.comp("FT-T", "plain", 20.0)
    w.fwd(30.0)
    w.end("TIE-END")
    it.kind = "instrument"
    sp = Spool("L-T-SP02", "L-T", 2.0, 0.065, "test")
    sp.pieces.append(Piece("L-T-SP02.pc02", "L-T-SP02", "L-T", "tube", 2.0, {"p0": (33.0, 0.0, 0.0), "p1": (47.0, 0.0, 0.0)},
                           14.0))
    sp.inst_tag = "FT-T"
    m.inst_spools = [sp]
    if hanger_on_spool:
        hanger(m, 1, 40.0, "L-T FT-T upstream straight-run support")
    return m


def comp_eids(comps, key):
    return next(e for k, e in comps if k == key)


class WeightsBase(unittest.TestCase):
    def setUp(self):
        p = mock.patch.object(PS, "WEIGHTS", {"FT-T": (W_FT, "test record")})
        p.start()
        self.addCleanup(p.stop)


@needs_skidlib
class InstrumentSpoolHanger(WeightsBase):
    def test_hanger_on_spool_tube_is_a_support(self):
        m = build()
        net, comps, _, tube_hangers = PS.build_net(m, {"L-T"})
        sup = {net.label[k] for k, v in net.kind.items() if v == "support"}
        self.assertIn("PS-001-HGR", sup)
        eids = comp_eids(comps, "FT-T")
        self.assertEqual(len(eids), 2)                                       # split at the hanger
        self.assertAlmostEqual(sum(net.edges[e]["len"] for e in eids), 20.0, places=6)
        self.assertAlmostEqual(sum(net.edges[e]["w"] for e in eids), W_FT, places=6)   # weight kept whole
        (s_, L, hk), = tube_hangers["L-T-SP02.pc02"]                         # clearance checked on the spool tube
        self.assertEqual(hk, "PS-001-HGR")
        self.assertAlmostEqual(s_, 7.0, places=6)
        self.assertAlmostEqual(L, 14.0, places=6)
        a = net.edges[eids[0]]["a"]                                          # in face (x 30) to the hanger: 10 in
        (node, d), = net.nearest_supports(a, n=1)
        self.assertEqual(net.label[node], "PS-001-HGR")
        self.assertAlmostEqual(d, 10.0, places=2)

    def test_no_hanger_keeps_one_span(self):
        m = build(hanger_on_spool=False)
        net, comps, _, tube_hangers = PS.build_net(m, {"L-T"})
        self.assertEqual(len(comp_eids(comps, "FT-T")), 1)
        self.assertNotIn("L-T-SP02.pc02", tube_hangers)
        self.assertFalse([k for k, v in net.kind.items() if v == "support"])

    def test_hanger_on_pipe_tube_unchanged(self):
        m = build(hanger_on_spool=False)
        hanger(m, 2, 15.0, "L-T pipe support")
        net, comps, _, tube_hangers = PS.build_net(m, {"L-T"})
        self.assertEqual(len(comp_eids(comps, "FT-T")), 1)
        self.assertEqual([h for _, _, h in sum(tube_hangers.values(), [])], ["PS-002-HGR"])

    def test_no_recorded_weight_is_not_checked_and_carries_nothing(self):
        with mock.patch.object(PS, "WEIGHTS", {}):
            net, comps, _, _ = PS.build_net(build(), {"L-T"})
        self.assertEqual(net.no_weight, ["FT-T"])
        self.assertEqual(sum(net.edges[e]["w"] for e in comp_eids(comps, "FT-T")), 0.0)


@needs_skidlib
class ClearanceAccept(unittest.TestCase):
    """ACCEPT_CLEARANCE follows the support's role, not its PS number (renumbering)."""

    def test_by_role_not_number(self):
        m = Model(RULES)
        hanger(m, 14, 0.0, "L-T tail support (TIE-T end)")
        hanger(m, 13, 5.0, "L-T FT-T upstream straight-run support")
        with mock.patch.object(PS, "ACCEPT_CLEARANCE", {"L-T tail support (TIE-T end)": "test record (Bob, chat, test)"}):
            self.assertIn("test record", PS.clearance_accept(m, "PS-014-HGR"))
            self.assertIsNone(PS.clearance_accept(m, "PS-013-HGR"))
            self.assertIsNone(PS.clearance_accept(m, "PS-099-HGR"))       # unknown hanger


class AcceptLists(unittest.TestCase):
    def test_nothing_carried_over_and_every_entry_cites_bob(self):
        for d in (PS.ACCEPT_NAMED, PS.ACCEPT_ELBOW, PS.ACCEPT_PUMP, PS.ACCEPT_CLEARANCE):
            for k, why in d.items():
                self.assertFalse(k.startswith("PS-"), k)
                self.assertIn("Bob, chat", why)
        self.assertEqual(PS.ACCEPT_ZONE["comps"], set())
        self.assertIsNone(PS.ACCEPT_ON_NOZZLE)
        self.assertIsNone(PS.ACCEPT_TIE_IN)


HARNESS_STR = """pipe_supports:
  - id: STR-PS-001
    sizing_load_case: {side_load_lb: 5.0, E_psi: 28000000.0, sway_limit_in: 0.1}
  - id: STR-PS-002
    max_span_in: 84
    values_by_od_in: {"3.0": {max_span_in: 96}}
"""
LINES = "line_no,service_class\nW-901,hygienic\nW-902,utility-water\nS-901,steam\nC-901,\n"


class Scope(unittest.TestCase):
    """PIPE-SVC-001: STR-PS-002 runs on hygienic lines, and utility-water where the project entry lists it."""

    def rules(self, project: str, job: str = ""):
        with tempfile.TemporaryDirectory() as d:
            h, j, jb = Path(d) / "h", Path(d) / "j", Path(d) / "job"
            for x in (h, j, jb):
                x.mkdir()
            (h / "structural.yaml").write_text(HARNESS_STR, encoding="utf-8")
            (j / "structural.yaml").write_text(project, encoding="utf-8")
            (jb / "structural.yaml").write_text(job, encoding="utf-8")
            (Path(d) / "line-list.csv").write_text(LINES, encoding="utf-8")
            import rule_scope
            return PS.rules(h, j, rule_scope.line_classes(Path(d) / "line-list.csv"), jb)

    def test_job_level_scope_narrowed_by_project(self):
        job = "STR-PS-002: {applies_to: [hygienic, utility-water], values_by_od_in: {'3.0': {max_span_in: 90}}}\n"
        _, lines, _, _ = self.rules("", job)                                # no project entry: the job's scope
        self.assertEqual(lines, {"W-901", "W-902"})
        r, lines, _, _ = self.rules("STR-PS-002: {applies_to: [utility-water]}\n", job)
        self.assertEqual(lines, {"W-902"})                                  # project narrows the job
        self.assertEqual(r["by_od"][3.0]["max_span_in"], 90)                # job value over the harness's 96
        r, _, _, _ = self.rules("STR-PS-002: {applies_to: [utility-water], values_by_od_in: {'3.0': {max_span_in: 80}}}\n",
                                job)
        self.assertEqual(r["by_od"][3.0]["max_span_in"], 80)                # project value over the job's

    def test_unknown_is_not_checked(self):
        r, lines, notes, sizing = self.rules("STR-PS-002: {rule_ref: STR-PS-002, applies_to: unknown}\n")
        self.assertIsNone(lines)
        self.assertIn("applies_to unknown", notes[0])
        self.assertEqual(sizing["E_psi"], 28000000.0)
        self.assertEqual(r["by_od"][3.0]["max_span_in"], 96)

    def test_hygienic_only_and_steam_never(self):
        _, lines, notes, _ = self.rules("STR-PS-002: {applies_to: [hygienic, steam]}\n")
        self.assertEqual(lines, {"W-901"})
        self.assertTrue(any("steam ignored" in n for n in notes))
        self.assertTrue(any("C-901" in n for n in notes))                 # unknown class named, not checked

    def test_utility_water_when_listed(self):
        _, lines, _, _ = self.rules("STR-PS-002: {applies_to: 'hygienic, utility-water'}\n")
        self.assertEqual(lines, {"W-901", "W-902"})

    def test_section_layout_project_file(self):
        _, lines, notes, _ = self.rules("pipe_supports:\n  applies_to_lines: [W-901]\n")
        self.assertEqual(lines, {"W-901"})
        self.assertEqual(notes, [])


class Weights(unittest.TestCase):
    def test_recorded_only(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "equipment-list.csv").write_text(
                "tag,operating_weight_lb,empty_weight_lb\nHX-901,410,300\nP-901,unknown,95\nTK-901,unknown,unknown\n",
                encoding="utf-8")
            job, prj = Path(d) / "job", Path(d) / "project"
            job.mkdir()
            prj.mkdir()
            (job / "component-register.csv").write_text(
                "component_id,revision,status,weight_lb\nCOMP-0001,A,current,7.5\nCOMP-0003,A,superseded,9\n"
                "COMP-0003,B,current,\n", encoding="utf-8")
            (prj / "component-register.csv").write_text(   # pid_tag: a register that still carries the column
                "component_id,revision,status,weight_lb,pid_tag\nCOMP-0001,A,current,99,\nCOMP-0002,A,current,4,XV-901\n"
                "COMP-0004,A,current,,PT-901\n", encoding="utf-8")
            libs = [PS.components.Library("job", job, job / "component-register.csv"),
                    PS.components.Library("project", prj, prj / "component-register.csv")]
            w = PS.recorded_weights(Path(d), libs)
        self.assertEqual(w["HX-901"][0], 410.0)                             # water full first
        self.assertEqual(w["P-901"][0], 95.0)
        self.assertEqual(w["COMP-0001"][0], 7.5)                            # job library first
        self.assertIn("job component register COMP-0001", w["COMP-0001"][1])
        self.assertEqual(w["XV-901"][0], 4.0)
        self.assertNotIn("COMP-0003", w)                                    # superseded weight not used, current blank
        self.assertNotIn("TK-901", w)
        self.assertNotIn("PT-901", w)
        with mock.patch.object(PS, "WEIGHTS", w):
            self.assertEqual(PS.comp_weight("PT-901"), (None, "not checked (no weight)"))


class ThisProject(unittest.TestCase):
    def test_main_passes_not_checked_without_scope_or_model(self):
        _, lines, _, _ = PS.rules()
        if lines and PS.rule_scope.model_missing() is None:
            self.skipTest("this project has lines in scope and a model")
        out = io.StringIO()
        with contextlib.redirect_stdout(out), mock.patch.object(sys, "argv", ["pipe_supports.py"]):
            self.assertEqual(PS.main(), 0)
        self.assertTrue(out.getvalue().startswith("pipe_supports: PASS - not checked"))


if __name__ == "__main__":
    unittest.main()
