"""Unit tests for harness/checks/sanitary.py (SAN-DL-002, INST-POS-001, INST-LEAK-001, INST-SR-001).

Synthetic geometry: a small line built with the skidlib LineWalker (the same Model, Spool, Piece and Item records
the skid model uses), so the checks are tested on the data structures they read, with known answers. Pass and fail
cases for each rule. The geometry cases need the project's skidlib and are skipped while the project has no model
source; the pure functions, the rule reader (both rule-file layouts) and the service-class scope always run.
Stdlib unittest only (no new dependency):

    .\\harness\\tools\\venv\\Scripts\\python.exe -m unittest discover -s harness\\tests -v
"""
from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import types
import unittest
from pathlib import Path

REPO = next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists())
sys.path.insert(0, str(REPO / "harness" / "lib"))
sys.path.insert(0, str(REPO / "harness" / "checks"))
import repo_paths as rp  # noqa: E402

if rp.HAS_PROJECT:
    sys.path.insert(0, str(rp.SKID_MODEL))
import sanitary as S  # noqa: E402

try:
    from skidlib import params as RP  # noqa: E402   (read only: TEE_STYLES, IFM_ADAPTER, JOINT_GAP)
    from skidlib.model import Item, Model, cyl  # noqa: E402
    SKIDLIB = True
except ImportError:      # no model source on this project yet
    SKIDLIB = False
needs_skidlib = unittest.skipUnless(SKIDLIB, "no skidlib (no project or no model source yet)")

RULES = {"min_slope_in_per_ft": 0.125, "walls": {2.0: 0.065}, "tube_spec": "ASTM A270 S2", "grade": "316L"}
GAP = 0.080
BORE_R = 0.935          # 2.0 in OD x 0.065 in wall


def build_line(style=None, inst_axis=(0.0, 1.0, 0.0), probe_tip_r=None, port=(0.0, 0.0, -1.0), adapter="E33209"):
    """TIE (x 0) > 3 in > valve V-T (x 3..7) > 13 in > tee SEN-T at x 20 > 20 in > 90 deg elbow at x 40 > +Y 20 in.
    The instrument SEN-T sits on the tee branch face along inst_axis (the tee branch points that way), held off
    the face by the A-58 gap. Returns (model, params stub)."""
    m = Model(RULES)
    w = m.walker("L-T", 2.0)
    w.start((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), "TIE-T")
    w.fwd(3.0)
    w.comp("V-T", "plain", 4.0)
    w.fwd(13.0)
    face, bdir = w.tee("SEN-T", inst_axis, style=style)
    w.fwd(20.0)
    w.go(dy=20.0)
    w.end("TIE-END")
    seat = tuple(f + b * GAP for f, b in zip(face, bdir))
    it = Item(key="SEN-T", tag="SEN-T", kind="instrument", line="L-T", source="test")
    it.faces = {"process": (seat, tuple(-b for b in bdir))}
    it.prims.append(cyl(seat, tuple(s + b * 3.0 for s, b in zip(seat, bdir)), 1.0))
    if probe_tip_r is not None:     # a probe from the seat back toward the run axis, tip probe_tip_r from the axis
        tip = tuple(20.0 * (k == 0) + b * probe_tip_r for k, b in enumerate(bdir))
        it.prims.append({**cyl(tip, seat, 0.4), "internal": True})
    if adapter:
        it.step_extra.append({"label": f"SEN-T adapter {adapter}", "x_dir": port})
    m.add_item(it)
    P = types.SimpleNamespace(INSTRUMENT_MODEL={"SEN-T": ("sensor", adapter, "")}, IFM_ADAPTER=RP.IFM_ADAPTER,
                              JOINT_GAP=GAP)
    return m, P


def cfg(row: dict | None = None, orient: dict | None = None, sr: dict | None = None) -> dict:
    r = {"tags": ["SEN-T"], "sensor": "ifm PI17xx in E33209", "d_mm": 0, "max_L_mm": 47.5}
    r.update(row or {})
    return {"dl": {"D_mm": 47.5, "D_in": 1.870, "run_bore_r_in": BORE_R, "gap_in": GAP, "rows": {"SEN-T": r},
                   "assumption": ""},
            "orientation": {"SEN-T": orient} if orient else {},
            "sr": {"SEN-T": sr} if sr else {}}


def only(rows, rule):
    rr = [r for r in rows if r.rule == rule and r.tag == "SEN-T"]
    assert len(rr) == 1, rr
    return rr[0]


class PureFunctions(unittest.TestCase):
    def test_dl002_is_strict(self):
        self.assertEqual(S.dl002_result(47.4, 47.5), S.PASS)
        self.assertEqual(S.dl002_result(47.5, 47.5), S.FAIL)

    def test_positions(self):
        h = (1.0, 0.0, 0.0)
        self.assertEqual(S.position_of((0, 0, 1), h), 1)
        self.assertEqual(S.position_of((0, 1, 1), h), 2)
        self.assertEqual(S.position_of((0, 1, 0), h), 3)
        self.assertEqual(S.position_of((0, 1, -1), h), 4)
        self.assertEqual(S.position_of((0, 0, -1), h), 5)
        self.assertIsNone(S.position_of((1, 0, 0), (0, 0, 1)))          # vertical pipe

    def test_allowed_positions_from_project_text(self):
        self.assertEqual(S.allowed_positions({"mounting": "3-A positions 1-3 only: horizontal or above"}), {1, 2, 3})
        self.assertEqual(S.allowed_positions({"mounting": "Side mount on horizontal pipe."}), {1, 2, 3, 4})
        self.assertEqual(S.allowed_positions(None), {1, 2, 3, 4})

    def test_leak_port(self):
        self.assertTrue(S.leak_port_ok((1, 0, 0), (0, 0, -1))[0])
        self.assertFalse(S.leak_port_ok((1, 0, 0), (0, 0, 1))[0])
        self.assertFalse(S.leak_port_ok((1, 0, 0), (0, 1, 0))[0])
        self.assertTrue(S.leak_port_ok((0, 0, 1), (0, 1, 0))[0])         # vertical axis: all radial ports level

    def test_sr_limits(self):
        lim = S.sr_limits({"upstream_DN": 5, "downstream_DN": 2, "line_DN": "DN50 (2.0 in OD)",
                           "disturbances": "T-sections and valves count as disturbances"}, 2.0)
        self.assertAlmostEqual(lim["up"], 250 / 25.4)
        self.assertAlmostEqual(lim["down"], 100 / 25.4)
        self.assertTrue(lim["tees_count"])
        lim = S.sr_limits({"upstream_D": "5 to 10", "downstream_D": "3 to 5",
                           "line_DN": "D is the OUTSIDE diameter of the pipe"}, 2.0)
        self.assertAlmostEqual(lim["up"], 10.0)
        self.assertAlmostEqual(lim["down"], 6.0)
        self.assertFalse(lim["tees_count"])
        lim = S.sr_limits({"upstream_D": 5, "line_DN": "no basis"}, 2.0)
        self.assertIsNone(lim["up"])

    def test_named_adapters(self):
        self.assertEqual(S.named_adapters("weld-in adapter (E43310 or E43412, pending)"), {"E43310", "E43412"})


@needs_skidlib
class DeadLeg(unittest.TestCase):
    def test_standard_tee_fails_flush_sensor(self):
        m, P = build_line()
        r = only(S.check_dl002(m, P, cfg()), "SAN-DL-002")
        self.assertEqual(r.result, S.FAIL)                 # 2.25 + 0.5 + 0.080 - 0.935 = 1.895 in = 48.1 mm
        self.assertIn("48.1 mm", r.measured)

    def test_short_outlet_tee_passes_probe(self):
        m, P = build_line(style="S7SWWK-2")
        r = only(S.check_dl002(m, P, cfg({"d_mm": 10.8, "max_L_mm": 36.7})), "SAN-DL-002")
        self.assertEqual(r.result, S.PASS)                 # 1.625 + 0.080 - 0.935 = 0.770 in = 19.6 mm < 36.7
        self.assertIn("19.6 mm", r.measured)

    def test_probe_d_fails_where_flush_would_pass(self):
        m, P = build_line(style="S7SWWK-2")
        r = only(S.check_dl002(m, P, cfg({"d_mm": 30.0, "max_L_mm": 17.5})), "SAN-DL-002")
        self.assertEqual(r.result, S.FAIL)                 # 19.6 mm vs 47.5 - 30 = 17.5 mm

    def test_missing_gap_is_added(self):
        m, P = build_line(style="S7SWWK-2")
        it = m.items["SEN-T"]
        (seat, d) = it.faces["process"]
        it.faces["process"] = (tuple(s + x * GAP for s, x in zip(seat, d)), d)   # instrument face on the tee face
        r = only(S.check_dl002(m, P, cfg()), "SAN-DL-002")
        self.assertIn("19.6 mm", r.measured)

    def test_immersion_not_checked_without_probe(self):
        m, P = build_line(style="S7SWWK-2")
        r = only(S.check_dl002(m, P, cfg({"d_mm": 10.8, "max_L_mm": 36.7, "min_immersion_mm": 12})), "SAN-DL-002")
        self.assertEqual(r.result, S.NC)

    def test_immersion_checked_with_probe(self):
        row = {"d_mm": 10.8, "max_L_mm": 36.7, "min_immersion_mm": 12}
        m, P = build_line(style="S7SWWK-2", probe_tip_r=0.4)            # tip 0.535 in = 13.6 mm into the bore
        self.assertEqual(only(S.check_dl002(m, P, cfg(row)), "SAN-DL-002").result, S.PASS)
        m, P = build_line(style="S7SWWK-2", probe_tip_r=0.8)            # 0.135 in = 3.4 mm
        self.assertEqual(only(S.check_dl002(m, P, cfg(row)), "SAN-DL-002").result, S.FAIL)

    def test_maker_rule_adapter(self):
        row = {"sensor": "ifm LDL220 through a weld-in adapter (E43310 or E43412)", "d_mm": None, "max_L_mm": None}
        m, P = build_line(style="S7SWWK-2", probe_tip_r=0.8, adapter="E43312")
        self.assertEqual(only(S.check_dl002(m, P, cfg(row)), "SAN-DL-002").result, S.FAIL)    # clamp adapter
        m, P = build_line(style="S7SWWK-2", probe_tip_r=0.8, adapter="E43412")
        self.assertEqual(only(S.check_dl002(m, P, cfg(row)), "SAN-DL-002").result, S.NC)      # channel not exposed
        m, P = build_line(style="S7SWWK-2", probe_tip_r=1.2, adapter="E43412")
        self.assertEqual(only(S.check_dl002(m, P, cfg(row)), "SAN-DL-002").result, S.FAIL)    # tip outside bore

    def test_branch_instrument_without_project_values_fails(self):
        m, P = build_line()
        c = cfg()
        c["dl"]["rows"] = {}
        rows = S.check_dl002(m, P, c)
        self.assertEqual(only(rows, "SAN-DL-002").result, S.FAIL)


@needs_skidlib
class Position(unittest.TestCase):
    def test_side_passes_bottom_fails(self):
        m, _ = build_line(inst_axis=(0.0, 1.0, 0.0))
        self.assertEqual(only(S.check_pos(m, cfg()), "INST-POS-001").result, S.PASS)
        m, _ = build_line(inst_axis=(0.0, 0.0, -1.0))
        r = only(S.check_pos(m, cfg()), "INST-POS-001")
        self.assertEqual(r.result, S.FAIL)
        self.assertIn("position 5", r.measured)

    def test_project_orientation_narrows(self):
        m, _ = build_line(inst_axis=(0.0, -0.7071, -0.7071))            # position 4: lower 45
        self.assertEqual(only(S.check_pos(m, cfg()), "INST-POS-001").result, S.PASS)
        self.assertEqual(only(S.check_pos(m, cfg(orient={"mounting": "3-A positions 1-3 only"})),
                              "INST-POS-001").result, S.FAIL)


@needs_skidlib
class Leak(unittest.TestCase):
    def test_port_down_passes_port_up_fails(self):
        m, P = build_line(port=(0.0, 0.0, -1.0))
        self.assertEqual(only(S.check_leak(m, P, cfg()), "INST-LEAK-001").result, S.PASS)
        m, P = build_line(port=(0.0, 0.0, 1.0))
        self.assertEqual(only(S.check_leak(m, P, cfg()), "INST-LEAK-001").result, S.FAIL)

    def test_adapter_named_but_not_modelled(self):
        m, P = build_line(adapter=None)
        self.assertEqual(only(S.check_leak(m, P, cfg()), "INST-LEAK-001").result, S.NC)


@needs_skidlib
class StraightRun(unittest.TestCase):
    SR = {"upstream_DN": 5, "downstream_DN": 5, "line_DN": "DN50"}

    def test_branch_sensor_distances(self):
        m, _ = build_line()
        up, dn, od = S.straight_runs(m, m.items["SEN-T"], False, 0.15)
        self.assertAlmostEqual(up["dist"], 13.0, places=3)                  # tee centre to the V-T out face
        self.assertIn("V-T", up["by"])
        self.assertAlmostEqual(dn["dist"], 20.0 - RP.ELBOW_CLR[2.0], places=3)   # to the elbow tangent
        self.assertIn("elbow", dn["by"])

    def test_pass_and_fail(self):
        m, P = build_line()
        self.assertEqual(only(S.check_sr(m, P, cfg(sr=self.SR)), "INST-SR-001").result, S.PASS)   # 13.0 / 17.0 >= 9.84
        sr = {"upstream_DN": 7, "downstream_DN": 2, "line_DN": "DN50"}                            # 13.78 in up
        self.assertEqual(only(S.check_sr(m, P, cfg(sr=sr)), "INST-SR-001").result, S.FAIL)

    def test_tees_count_for_inline_item(self):
        m, _ = build_line()
        v = m.items["V-T"]
        up, dn, _ = S.straight_runs(m, v, False, 0.15)
        self.assertTrue(up["end"])                                          # runs off the model at the tie
        self.assertAlmostEqual(up["dist"], 3.0, places=3)
        self.assertAlmostEqual(dn["dist"], 40.0 - RP.ELBOW_CLR[2.0] - 7.0, places=3)   # instrument tee is no disturbance
        _, dn, _ = S.straight_runs(m, v, True, 0.15)
        self.assertAlmostEqual(dn["dist"], 20.0 - 2.25 - 7.0, places=3)     # T-sections count: to the tee run end

    def test_probe_tip_in_run_is_a_disturbance(self):
        m, P = build_line()
        it = Item(key="TT-T", tag="TT-T", kind="instrument", line="L-T", source="test")
        it.prims.append({**cyl((30.0, 0.0, 0.0), (36.0, 0.0, 0.0), 0.12), "internal": True})
        m.add_item(it)
        _, dn, _ = S.straight_runs(m, m.items["SEN-T"], False, 0.15)
        self.assertAlmostEqual(dn["dist"], 10.0, places=3)
        self.assertIn("TT-T probe tip", dn["by"])


@needs_skidlib
class KnownFindings(unittest.TestCase):
    """ACCEPT (Bob, chat, 2026-10-05: "2."): an exact (rule, tag, measured) match is KNOWN; any change is a FAIL."""

    def _fail_row(self):
        m, P = build_line()
        r = only(S.check_dl002(m, P, cfg()), "SAN-DL-002")
        self.assertEqual(r.result, S.FAIL)
        return r

    def test_accepted_row_is_known_and_passes(self):
        r = self._fail_row()
        acc = {("SAN-DL-002", "SEN-T", r.measured): "TEST-RECORD"}
        self.assertEqual(S.apply_accepts([r], acc), [])
        self.assertEqual(r.result, S.KNOWN)
        self.assertIn("TEST-RECORD", r.detail)
        head = S.summary([r], "test")
        self.assertTrue(head.startswith("sanitary: PASS - 0 of 1"))
        self.assertIn("1 known", head)

    def test_changed_value_fails_again(self):
        r = self._fail_row()
        acc = {("SAN-DL-002", "SEN-T", "L 47.9 mm (1.886 in)"): "TEST-RECORD"}
        stale = S.apply_accepts([r], acc)
        self.assertEqual(r.result, S.FAIL)
        self.assertEqual(stale, list(acc))
        self.assertTrue(S.summary([r], "test").startswith("sanitary: FAIL"))

    def test_pass_row_is_not_touched(self):
        m, P = build_line(style="S7SWWK-2")
        r = only(S.check_dl002(m, P, cfg({"d_mm": 10.8, "max_L_mm": 36.7})), "SAN-DL-002")
        S.apply_accepts([r], {("SAN-DL-002", "SEN-T", r.measured): "x"})
        self.assertEqual(r.result, S.PASS)

    def test_every_entry_cites_a_record(self):
        for k, why in S.ACCEPT.items():
            self.assertIn("Bob, chat", why, k)   # every entry quotes Bob and names this project's record


@needs_skidlib
class SpoolPart(unittest.TestCase):
    """Instrument spool parts: the run inside the part is added from the part record and the
    row reads KNOWN; a row short even with it still fails; an item that is not a spool part is measured as before."""
    SPEC = {"faces": (-2.0, 2.0), "parts": ["ifm LDL220 (CMP-T033)", "ifm E43412 weld-in adapter, leakage port (CMP-T039)"]}

    def _line(self, spool=True):
        """build_line's V-T (x 3..7) re-made as an instrument spool part with its sensor at x 5."""
        m, P = build_line()
        v = m.items["V-T"]
        v.kind = "instrument"
        if spool:
            v.spool_cmp = "CMP-TEST"
            v.step = {"plane_origin": (5.0, 0.0, 0.0), "x_dir": (1.0, 0.0, 0.0)}
        P.INST_SPOOL = {"CMP-TEST": self.SPEC}
        P.INST_SPOOL_PARTS = {"CMP-TEST": {"joints": []}}
        return m, P, v

    @staticmethod
    def _sr(up_d, down_d):
        return {"upstream_D": up_d, "downstream_D": down_d, "line_DN": "D is the OUTSIDE diameter of the pipe"}

    def _row(self, m, P, up_d, down_d):
        c = cfg()
        c["sr"] = {"V-T": self._sr(up_d, down_d)}
        rr = [r for r in S.check_sr(m, P, c) if r.tag == "V-T"]
        self.assertEqual(len(rr), 1)
        return rr[0]

    def test_builtin_run_from_part_record(self):
        it = types.SimpleNamespace(spool_cmp="CMP-M", step={"plane_origin": (0.0, 0.0, 0.0), "x_dir": (1.0, 0.0, 0.0)},
                                   faces={"in": ((-14.286, 0, 0), (-1, 0, 0)), "out": ((8.411, 0, 0), (1, 0, 0))})
        P = types.SimpleNamespace(JOINT_GAP=0.08, INST_SPOOL={"CMP-M": {"faces": (-14.286, 8.411), "parts": []}},
                                  INST_SPOOL_PARTS={"CMP-M": {"joints": [((-4.371, 0, 0), (1, 0, 0), "a", "b"),
                                                                         ((4.371, 0, 0), (1, 0, 0), "c", "d")]}})
        sp = S.spool_part(it, P)                       # in-line meter: from its clamp faces (joint less half a gap)
        self.assertAlmostEqual(sp["builtin"]["in"], 14.286 - 4.331, places=6)
        self.assertAlmostEqual(sp["builtin"]["out"], 8.411 - 4.331, places=6)
        self.assertIsNone(sp["adapter"])
        it.step = {"plane_origin": (0.0, 0.0, 0.0), "x_dir": (-1.0, 0.0, 0.0)}     # part turned end for end
        self.assertAlmostEqual(S.spool_part(it, P)["builtin"]["in"], 14.286 - 4.331, places=6)
        self.assertIsNone(S.spool_part(types.SimpleNamespace(step=None, faces={}), P))   # not a spool part

    def test_known_when_inside_run_meets_the_value(self):
        m, P, _ = self._line()
        r = self._row(m, P, 2.5, 2)                    # up 3.0 walked + 2.0 inside = 5.0 >= 5.0 in
        self.assertEqual(r.result, S.KNOWN)
        self.assertIn("2.00 in inside CMP-TEST", r.measured)
        self.assertIn("known (spool part)", r.detail)

    def test_short_even_with_inside_run_fails(self):
        m, P, _ = self._line()
        self.assertEqual(self._row(m, P, 2.5, 20).result, S.FAIL)    # down ~32 in vs 40 in, not at the model end

    def test_not_a_spool_part_is_measured_as_before(self):
        m, P, _ = self._line(spool=False)
        r = self._row(m, P, 2.5, 2)                    # up 3.0 < 5.0 at the model end: not checked, never KNOWN
        self.assertEqual(r.result, S.NC)
        self.assertNotIn("inside", r.measured)

    def test_leak_and_dead_leg_take_the_part(self):
        m, P, _ = self._line()
        leak = [r for r in S.check_leak(m, P, cfg()) if r.tag == "V-T"][0]
        self.assertEqual(leak.result, S.NC)
        self.assertIn("E43412", leak.measured)
        c = cfg()
        c["dl"]["rows"]["V-T"] = c["dl"]["rows"]["SEN-T"]
        dl = [r for r in S.check_dl002(m, P, c) if r.tag == "V-T"][0]
        self.assertEqual(dl.result, S.NC)
        self.assertIn("spool part CMP-TEST", dl.measured)


HARNESS_SAN = """dead_leg:
  - id: SAN-DL-002
    max_L: "D - d"
"""
HARNESS_INST = """position:
  INST-POS-001: {rule: x}
leakage_port:
  INST-LEAK-001: {rule: x}
straight_run:
  INST-SR-001: {rule: x}
"""


def write_rules(d: Path, san: str, inst: str) -> tuple[Path, Path]:
    """Scratch harness and project rule folders, and an empty job level beside them (d/job; tests that need job rules
    write there), so the real job/design-rules never reach a fixture."""
    h, j = d / "harness", d / "project"
    h.mkdir()
    j.mkdir()
    (d / "job").mkdir()
    (h / "sanitary.yaml").write_text(HARNESS_SAN, encoding="utf-8")
    (h / "instrument-mounting.yaml").write_text(HARNESS_INST, encoding="utf-8")
    (j / "sanitary.yaml").write_text(san, encoding="utf-8")
    (j / "instrument-mounting.yaml").write_text(inst, encoding="utf-8")
    return h, j


class ProjectRuleLayout(unittest.TestCase):
    """The project files key each rule by its id at the top level (CPME practice); applies_to names service classes."""

    def test_unknown_scope_is_not_checked(self):
        with tempfile.TemporaryDirectory() as d:
            h, j = write_rules(Path(d), "SAN-DL-002: {rule_ref: SAN-DL-002, applies_to: unknown}\n",
                               "INST-SR-001: {rule_ref: INST-SR-001, applies_to: unknown}\n")
            c = S.load_rules(h, j, h.parent / "job")
        self.assertEqual(set(c["scope"]), set(S.RULES))
        self.assertTrue(all(cls is None for cls, _ in c["scope"].values()))
        self.assertIn("applies_to unknown", c["scope"]["SAN-DL-002"][1])

    def test_hygienic_scope_and_values(self):
        san = ("SAN-DL-002:\n  rule_ref: SAN-DL-002\n  applies_to: [hygienic, steam]\n  branch_D_mm: 47.5\n"
               "  branch_D_in: 1.870\n  run_bore_radius_in: 0.935\n  gasket_gap_in: 0.08\n"
               "  instruments:\n    - {tags: [PT-901], sensor: flush, d_mm: 0, max_L_mm: 47.5}\n")
        inst = ("INST-SR-001:\n  applies_to: [hygienic, utility-water]\n  values:\n"
                "    - {tags: [FT-901], upstream_DN: 5, downstream_DN: 3, line_DN: DN50}\n"
                "INST-POS-001: {applies_to: hygienic}\n")
        with tempfile.TemporaryDirectory() as d:
            h, j = write_rules(Path(d), san, inst)
            c = S.load_rules(h, j, h.parent / "job")
        cls, note = c["scope"]["SAN-DL-002"]
        self.assertEqual(cls, {"hygienic"})                       # a SAN rule never runs on steam (PIPE-SVC-001)
        self.assertIn("steam ignored", note)
        self.assertEqual(c["dl"]["D_mm"], 47.5)
        self.assertEqual(set(c["dl"]["rows"]), {"PT-901"})
        self.assertEqual(c["scope"]["INST-SR-001"][0], {"hygienic", "utility-water"})
        self.assertEqual(set(c["sr"]), {"FT-901"})
        self.assertIsNone(c["scope"]["INST-LEAK-001"][0])         # no entry: not checked

    def test_scope_without_values_is_not_checked(self):
        with tempfile.TemporaryDirectory() as d:
            h, j = write_rules(Path(d), "SAN-DL-002: {applies_to: [hygienic]}\n", "")
            c = S.load_rules(h, j, h.parent / "job")
        self.assertIsNone(c["scope"]["SAN-DL-002"][0])
        self.assertIn("project values missing", c["scope"]["SAN-DL-002"][1])

    def test_harness_section_layout_still_read(self):
        with tempfile.TemporaryDirectory() as d:
            h, j = write_rules(Path(d), "", "")
            (h / "sanitary.yaml").write_text("dead_leg:\n  - id: SAN-DL-002\n    max_L: D - d\n", encoding="utf-8")
            S.load_rules(h, j, h.parent / "job")                                    # no KeyError: found in its section list
            (h / "sanitary.yaml").write_text("dead_leg: []\n", encoding="utf-8")
            with self.assertRaises(KeyError):
                S.load_rules(h, j, h.parent / "job")


class JobLevel(unittest.TestCase):
    """Three levels: the job entry (job/design-rules) gives scope and values; the project entry narrows it."""

    DL_JOB = ("SAN-DL-002:\n  rule_ref: SAN-DL-002\n  applies_to: [hygienic, utility-water]\n  branch_D_mm: 47.5\n"
              "  branch_D_in: 1.870\n  run_bore_radius_in: 0.935\n  gasket_gap_in: 0.08\n"
              "  instruments:\n    - {tags: [PT-901], sensor: flush, d_mm: 0, max_L_mm: 47.5}\n")

    def load(self, job_san: str, proj_san: str):
        with tempfile.TemporaryDirectory() as d:
            h, j = write_rules(Path(d), proj_san, "")
            (Path(d) / "job" / "sanitary.yaml").write_text(job_san, encoding="utf-8")
            return S.load_rules(h, j, Path(d) / "job")

    def test_job_entry_applies_when_project_has_none(self):
        c = self.load(self.DL_JOB, "")
        self.assertEqual(c["scope"]["SAN-DL-002"][0], {"hygienic", "utility-water"})
        self.assertEqual(c["dl"]["D_mm"], 47.5)                   # the job's values

    def test_project_narrows_job_scope_and_overrides_values(self):
        c = self.load(self.DL_JOB, "SAN-DL-002: {applies_to: [hygienic, steam], gasket_gap_in: 0.05}\n")
        self.assertEqual(c["scope"]["SAN-DL-002"][0], {"hygienic"})   # {hyg, uw} & {hyg, steam}
        self.assertEqual(c["dl"]["gap_in"], 0.05)                    # project value over the job's
        self.assertEqual(c["dl"]["D_mm"], 47.5)                      # job value kept where the project is silent

    def test_project_unknown_holds_the_rule(self):
        c = self.load(self.DL_JOB, "SAN-DL-002: {rule_ref: SAN-DL-002, applies_to: unknown}\n")
        self.assertIsNone(c["scope"]["SAN-DL-002"][0])


class ServiceClassScope(unittest.TestCase):
    """apply_scope: a row on a line of another class is N/A, an unknown class NOT CHECKED, an unscoped rule one row."""

    def test_rows(self):
        cfg = {"scope": {"SAN-DL-002": ({"hygienic"}, ""), "INST-POS-001": (None, "INST-POS-001: applies_to unknown"),
                         "INST-LEAK-001": ({"hygienic"}, ""), "INST-SR-001": ({"hygienic"}, "")}}
        rows = [S.Row("PT-901", "SAN-DL-002", S.FAIL, "L 50 mm", "L < 47.5"),
                S.Row("PT-902", "SAN-DL-002", S.FAIL, "L 50 mm", "L < 47.5"),
                S.Row("PT-903", "SAN-DL-002", S.PASS, "L 10 mm", "L < 47.5"),
                S.Row("PT-901", "INST-POS-001", S.FAIL, "position 5", "not 5")]
        out = S.apply_scope(rows, cfg, {"PT-901": "hygienic", "PT-902": "steam", "PT-903": "unknown"})
        by = {(r.tag, r.rule): r for r in out}
        self.assertEqual(by[("PT-901", "SAN-DL-002")].result, S.FAIL)
        self.assertEqual(by[("PT-902", "SAN-DL-002")].result, S.NA)
        self.assertEqual(by[("PT-903", "SAN-DL-002")].result, S.NC)
        self.assertNotIn(("PT-901", "INST-POS-001"), by)          # the unscoped rule's rows are replaced ...
        self.assertEqual(by[("-", "INST-POS-001")].result, S.NC)  # ... by one NOT CHECKED row
        self.assertFalse(S.summary(out, "test").startswith("sanitary: PASS"))   # the hygienic FAIL still fails


class RealRules(unittest.TestCase):
    def test_project_rules_load_and_main_passes_not_checked(self):
        c = S.load_rules()
        self.assertEqual(set(c["scope"]), set(S.RULES))
        if any(cls is not None for cls, _ in c["scope"].values()):
            self.skipTest("this project has a sanitary rule in scope; main() then needs the model")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(S.main([]), 0)
        self.assertTrue(out.getvalue().startswith("sanitary: PASS - not checked"))

    def test_nothing_accepted_yet(self):
        self.assertEqual(S.ACCEPT, {})


if __name__ == "__main__":
    unittest.main()
