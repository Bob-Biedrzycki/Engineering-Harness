"""sanitary - instrument installation rules on the routed skidlib model (CPME practice).

Builds the model in memory the same way pid_consistency.py does (<project>/03_Working_Design/CAD/01_Master_Assembly/<MODEL-ID>/skidlib
layout.build(), the model the STEP is generated from; nothing is written there) and checks, per instrument tag:

  SAN-DL-002     branch-instrument dead leg L < (D - d), L along the branch axis from the run's bore wall to the
                 sensor seat, gasket gap included (harness/design-rules/sanitary.yaml dead_leg SAN-DL-002; tags, d,
                 gap and maker rules in <project>/01_Design_Basis/05_Standards_Specifications/Design_Rules/sanitary.yaml SAN-DL-002). Where the project row has no d and
                 no max_L (a conductivity probe, say) the maker rule governs: the adapter must be one the row names, and the
                 probe tip must be inside the bore; the measuring-channel extent is not exposed by the model, so
                 "channel completely in the bore" is reported, not passed. A min_immersion_mm is checked
                 only when the model carries the probe (an internal primitive); otherwise NOT CHECKED.
  INST-POS-001   no instrument at the bottom of a horizontal pipe (3-A position 5); a project orientation entry that
                 says "positions a-b only" (TD2947) narrows the allowed positions
                 (harness/design-rules/instrument-mounting.yaml position; <project>/01_Design_Basis/05_Standards_Specifications/Design_Rules/instrument-mounting.yaml
                 orientation).
  INST-LEAK-001  the adapter's leakage port at the lowest point of the connection (harness instrument-mounting.yaml
                 leakage_port). Visibility needs an occlusion check and is not made.
  INST-SR-001    straight run up and downstream, every tag with a project value (project instrument-mounting.yaml
                 straight_run INST-SR-001), measured along the centreline of the model's pieces from the sensor
                 (branch instrument: its tee centre; in-line meter: its clamp faces) to the near end of the nearest
                 disturbance (elbow, tee used as a turn or entered from its branch, a tee whose branch is not a
                 dead-ended instrument, any tee where the project value says T-sections count, a valve or other clamped
                 item, a TD2947-type probe lying along the run).

Scope (PIPE-SVC-001, harness/lib/rule_scope.py): each rule runs only where its job entry (job/design-rules/), narrowed
by the project entry, gives its `applies_to` service classes; no project yet: PASS - not checked; SAN-DL-002 only on hygienic lines (utility-water where the entry lists it). A rule whose
applies_to is `unknown` is reported NOT CHECKED, and with every rule unknown, or no model source yet, the check prints
PASS - not checked and exits 0. A row on a line of a class the rule does not cover is N/A; on a line whose
service_class is unknown it is NOT CHECKED.

Every number is read from the design-rules YAML or measured on the model; nothing here is a rule value.
Geometric tolerances (not rule values): ANGLE_TOL_DEG, the model's own fit-up kink tolerance (params KINK_MAX_DEG
is 2.0 deg); AXIS_TOL_IN for "this tee is on that instrument's axis".

ASSUMPTIONS (printed with the result): positions are the nearest 45 deg step of the instrument's outward axis from
straight up (1 top .. 5 bottom), on the flowing leg perpendicular to that axis; a pipe more than 45 deg off
horizontal is vertical and INST-POS-001 does not apply; the spool walk order is the flow direction (skidlib
model.py: lines are walked in P&ID flow direction); a straight-run range "a to b" enforces a (the minimum, the
conservative reading).

Known findings (ACCEPT below; Bob, chat, 2026-10-05: "2."): a FAIL row whose rule, tag and exact measured text are
listed is printed KNOWN with its record; a changed measured value is a FAIL again. Bob's direction on the same
message: manufacturer best practices are built into the component STEP files (each instrument STEP carries its
required spool length with ferrules), so this check reports and does not block design progress.

Instrument spool parts (skidlib model.spool_item, item.spool_cmp; CPME practice):
the instrument is placed as one spool part whose straight run and branch are built in, so its own clamp faces are
the part's run ends. INST-SR-001 adds the run inside the part, read from the part record (params INST_SPOOL faces,
from the sensor: the tee centre, or for an in-line meter its clamp faces from INST_SPOOL_PARTS joints), to the run
walked on the model beyond each face. A row that meets the project value that way prints `KNOWN` ("known (spool part)"):
the inside run comes from the part record, it is not measured on model pieces. A row short of the project value even with
the inside run is still a FAIL. Tags not placed as a spool part are measured as before. SAN-DL-002 on a spool part
is NOT CHECKED (the seat is inside the part); INST-LEAK-001 takes the adapter the part lists, not params
INSTRUMENT_MODEL.

Exit-code contract (harness/checks/README.md): 0 = PASS (KNOWN and NOT CHECKED rows listed, they are not
failures), 1 = FAIL, 3 = ERROR (could not run). First printed line is the summary.

    python harness/checks/sanitary.py [--report <dir>]   writes instrument-rules.csv / .json there
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

import yaml

sys.path.insert(0, str(next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists()) / "harness" / "lib"))
import repo_paths as rp  # noqa: E402
import rule_scope  # noqa: E402

if rp.HAS_PROJECT:
    sys.path.insert(0, str(rp.SKID_MODEL))

MM_PER_IN = 25.4
ANGLE_TOL_DEG = 2.0       # geometric tolerance, equal to the model's fit-up kink tolerance (params KINK_MAX_DEG)
AXIS_TOL_IN = 0.05        # a tee centre this close to an instrument's axis line is the tee it sits on
END_TOL_IN = 0.02         # piece ends closer than this are welded together (one spool)
MAX_BRANCH_IN = 8.0       # search depth along a branch axis for the tee / instrument at its end
RULES = ("SAN-DL-002", "INST-POS-001", "INST-LEAK-001", "INST-SR-001")
PASS, FAIL, NC, NA, KNOWN = "PASS", "FAIL", "NOT CHECKED", "N/A", "KNOWN"

# Known findings, tracked and not failed (as interference.py ACCEPTED and pipe_supports.py ACCEPT_*). Bob, chat,
# 2026-10-05, verbatim: "2." (list the known findings as tracked; do not fail CI on them). His direction on the same
# message: manufacturer best practices are to be built into the component STEP files (each instrument STEP carries
# its required spool length with ferrules), so this check REPORTS and must not block design progress.
# Key: (rule, tag, the row's exact measured text). A different measured value no longer matches and is a FAIL again;
# an entry that matches no FAIL row is printed as stale so it can be removed. Every entry names this project's record.
# Empty: nothing is accepted on this project yet.
ACCEPT: dict = {}
KNOWN_SPOOL = ("known (spool part): straight run inside the {cmp} spool part read from its part record (params "
               "INST_SPOOL, INST_SPOOL_PARTS), not measured on model pieces (maker minimum straight run built into "
               "the part)")


@dataclass
class Row:
    tag: str
    rule: str
    result: str
    measured: str
    limit: str
    detail: str = ""


# ------------------------------------------------------------------ vectors (no model import needed for tests)
def _sub(a, b): return tuple(x - y for x, y in zip(a, b))
def _add(a, b): return tuple(x + y for x, y in zip(a, b))
def _mul(a, k): return tuple(x * k for x in a)
def _dot(a, b): return sum(x * y for x, y in zip(a, b))
def _norm(a): return math.sqrt(_dot(a, a))
def _dist(a, b): return _norm(_sub(a, b))


def _unit(a):
    n = _norm(a)
    return tuple(x / n for x in a) if n > 1e-12 else (0.0, 0.0, 0.0)


def _angle_deg(a, b):
    c = max(-1.0, min(1.0, _dot(_unit(a), _unit(b))))
    return math.degrees(math.acos(c))


def _point_line_dist(p, origin, d):
    v = _sub(p, origin)
    return _norm(_sub(v, _mul(d, _dot(v, d))))


# ------------------------------------------------------------------ rules (YAML)
def _yaml(p: Path):
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f)


DL_KEYS = ("branch_D_mm", "branch_D_in", "run_bore_radius_in", "gasket_gap_in", "instruments")


def load_rules(harness_dir: Path | None = None, project_dir: Path | None = None, job_dir: Path | None = None) -> dict:
    """The four rules, their scope and their job and project values.

    Three levels (harness/lib/rule_scope.py): the harness files keep their section layout (dead_leg: [...],
    position: {INST-POS-001: ...}); the job (job/design-rules/) and project files may use either layout and key a
    rule by its id (SAN-DL-002: {rule_ref, applies_to, ...}); rule_scope.find_rule reads both. The values the check
    uses are the job entry with the project entry laid over it, and the scope is the job's applies_to narrowed by
    the project's (rule_scope.merge_entries). cfg["scope"][rule] = (service classes, note), classes None = not
    checked (applies_to unknown, or the values the rule needs are missing). Raises KeyError / ValueError when a
    harness rule is missing or has a form this check does not implement.
    Defaults: harness/design-rules, job/design-rules, the active project's Design_Rules (none with no project yet)."""
    harness_dir = harness_dir or rp.HARNESS_DESIGN_RULES
    job_dir = job_dir or rp.JOB_DESIGN_RULES
    project_dir = project_dir or rule_scope.project_rules_dir()

    def _level(d: Path | None, name: str):
        return rule_scope.read_yaml(d / name) if d is not None else None

    hs, hi = _yaml(harness_dir / "sanitary.yaml"), _yaml(harness_dir / "instrument-mounting.yaml")
    js, ji = _level(job_dir, "sanitary.yaml"), _level(job_dir, "instrument-mounting.yaml")
    ps, pi = _level(project_dir, "sanitary.yaml"), _level(project_dir, "instrument-mounting.yaml")
    hdl = rule_scope.find_rule(hs, "SAN-DL-002")
    if hdl is None:
        raise KeyError("SAN-DL-002 not found in harness sanitary.yaml")
    if str(hdl.get("max_L", "")).replace(" ", "") != "D-d":
        raise ValueError(f"SAN-DL-002 max_L is {hdl.get('max_L')!r}; this check implements 'D - d' only")
    for rid in ("INST-POS-001", "INST-LEAK-001", "INST-SR-001"):
        if rule_scope.find_rule(hi, rid) is None:
            raise KeyError(f"{rid} not found in harness instrument-mounting.yaml")

    def _entry(job_file, proj_file, rid):   # job values with the project's laid over them; scope narrowed
        return rule_scope.merge_entries(None, rule_scope.find_rule(job_file, rid), rule_scope.find_rule(proj_file, rid))

    jdl = _entry(js, ps, "SAN-DL-002") or {}
    jsr = _entry(ji, pi, "INST-SR-001") or {}
    jpos = _entry(ji, pi, "INST-POS-001") or {}
    entries = {"SAN-DL-002": jdl, "INST-POS-001": jpos, "INST-LEAK-001": _entry(ji, pi, "INST-LEAK-001"),
               "INST-SR-001": jsr}
    scope = {rid: rule_scope.scope_classes(rid, e or None) for rid, e in entries.items()}
    dl = {"D_mm": None, "D_in": None, "run_bore_r_in": None, "gap_in": None, "rows": {}, "assumption": ""}
    if scope["SAN-DL-002"][0] is not None:
        lack = [k for k in DL_KEYS if rule_scope.is_unknown(jdl.get(k)) or jdl.get(k) in ([], {})]
        if lack:
            scope["SAN-DL-002"] = (None, f"SAN-DL-002: project values missing ({', '.join(lack)}) (not checked)")
        else:
            dl = {"D_mm": float(jdl["branch_D_mm"]), "D_in": float(jdl["branch_D_in"]),
                  "run_bore_r_in": float(jdl["run_bore_radius_in"]), "gap_in": float(jdl["gasket_gap_in"]),
                  "rows": {t: row for row in jdl["instruments"] for t in row["tags"]},
                  "assumption": jdl.get("assumption", "")}
    orient = (jpos.get("orientation") or (pi or {}).get("orientation") or (ji or {}).get("orientation") or {})
    return {"dl": dl, "orientation": orient if isinstance(orient, dict) else {},
            "sr": {t: row for row in (jsr.get("values") or ()) for t in row.get("tags", ())},
            "scope": scope}


def tag_classes(m, classes_by_line: dict[str, str] | None = None) -> dict[str, str]:
    """{instrument tag: service class of its line}: the model item's line, else the instrument list's
    line_no_or_equip; `unknown` when neither names a line on line-list.csv."""
    by_line = rule_scope.line_classes() if classes_by_line is None else classes_by_line
    listed = {}
    p = rp.DATA / "instrument-list.csv"
    if p.is_file():
        with open(p, newline="", encoding="utf-8-sig") as f:
            listed = {(r.get("tag") or "").strip(): (r.get("line_no_or_equip") or "").strip() for r in csv.DictReader(f)}
    out = {}
    for it in m.items.values():
        ln = getattr(it, "line", None) or listed.get(it.tag, "")
        out[it.tag] = by_line.get(ln, rule_scope.UNKNOWN)
    return out


def apply_scope(rows: list[Row], cfg: dict, tag_class: dict[str, str]) -> list[Row]:
    """Rows of a rule that is not checked are replaced by one NOT CHECKED row; a row on a line of a class the rule
    does not cover is N/A; on a line of unknown class it is NOT CHECKED (PIPE-SVC-001)."""
    scope = cfg.get("scope")
    if not scope:
        return rows
    out, done = [], set()
    for r in rows:
        classes, note = scope.get(r.rule, (None, f"{r.rule}: no scope"))
        if classes is None:
            if r.rule not in done:
                out.append(Row("-", r.rule, NC, "rule not checked on this project", "", note))
                done.add(r.rule)
            continue
        c = tag_class.get(r.tag, rule_scope.UNKNOWN)
        if c == rule_scope.UNKNOWN:
            r.result, r.detail = NC, "line service_class unknown (PIPE-SVC-001)" + (f"; {r.detail}" if r.detail else "")
        elif c not in classes:
            r.result, r.detail = NA, f"line class {c}: {r.rule} applies to {', '.join(sorted(classes))} (PIPE-SVC-001)"
        out.append(r)
    for rid, (classes, note) in scope.items():
        if classes is None and rid not in done:
            out.append(Row("-", rid, NC, "rule not checked on this project", "", note))
    return out


def allowed_positions(orient_row: dict | None) -> set[int]:
    """INST-POS-001 forbids position 5; a project orientation 'positions a-b only' narrows it (TD2947)."""
    txt = (orient_row or {}).get("mounting", "")
    m = re.search(r"positions\s+(\d)\s*-\s*(\d)\s+only", txt, re.I)
    return set(range(int(m.group(1)), int(m.group(2)) + 1)) if m else {1, 2, 3, 4}


def named_adapters(text: str) -> set[str]:
    """ifm article numbers (E + 5 digits) named in a project row's text."""
    return set(re.findall(r"\bE\d{5}\b", text or ""))


def parse_lo_hi(v) -> tuple[float, float]:
    """A straight-run value: a number, or a range 'a to b' / 'a-b' / 'a..b'."""
    if isinstance(v, (int, float)):
        return float(v), float(v)
    m = re.match(r"^\s*([\d.]+)\s*(?:to|-|\.\.)\s*([\d.]+)\s*$", str(v))
    if not m:
        raise ValueError(f"straight-run value {v!r} is not a number or a range")
    return float(m.group(1)), float(m.group(2))


def sr_limits(row: dict, tube_od_in: float) -> dict:
    """INST-SR-001 limits in inches for one project row. *_DN keys: x metric DN read from line_DN ('DN50');
    *_D keys: x the tube OD when line_DN says D is the outside diameter. Ranges enforce their lower value."""
    out = {"tees_count": bool(re.search(r"T-section|\btees?\b", row.get("disturbances", ""), re.I))}
    line = row.get("line_DN", "")
    for side, key in (("up", "upstream"), ("down", "downstream")):
        if f"{key}_DN" in row:
            dn = re.search(r"\bDN\s*(\d+)", line)
            if not dn:
                out[side] = None
                out[side + "_why"] = f"{key}_DN given but no DN size in line_DN"
                continue
            lo, hi = parse_lo_hi(row[f"{key}_DN"])
            base, word = float(dn.group(1)) / MM_PER_IN, f"x DN{dn.group(1)}"
        elif f"{key}_D" in row:
            if not re.search(r"outside\s+diameter", line, re.I):
                out[side] = None
                out[side + "_why"] = f"{key}_D given but line_DN does not say which D"
                continue
            lo, hi = parse_lo_hi(row[f"{key}_D"])
            base, word = tube_od_in, f"x D (OD {tube_od_in:g} in)"
        else:
            out[side] = None
            out[side + "_why"] = f"no {key} value"
            continue
        out[side] = lo * base
        out[side + "_text"] = (f"{lo:g} {word} = {lo * base:.2f} in" if lo == hi else
                               f"{lo:g}..{hi:g} {word}: minimum {lo * base:.2f} in enforced (range, ASSUMPTION)")
    return out


# ------------------------------------------------------------------ pure rule evaluation (unit-tested)
def dl002_result(L_mm: float, limit_mm: float) -> str:
    """SAN-DL-002 is strict: L < (D - d)."""
    return PASS if L_mm < limit_mm else FAIL


def position_of(axis_out, pipe_dir) -> int | None:
    """3-A / ifm mounting position of an instrument whose outward axis is axis_out on a pipe along pipe_dir:
    1 top, 2 upper 45, 3 side, 4 lower 45, 5 bottom. None when the pipe is vertical (> 45 deg off horizontal)."""
    if abs(_unit(pipe_dir)[2]) > math.sin(math.radians(45.0)):
        return None
    return 1 + int(round(_angle_deg(axis_out, (0.0, 0.0, 1.0)) / 45.0))


def leak_port_ok(axis_out, port_dir, tol_deg: float = ANGLE_TOL_DEG) -> tuple[bool, str]:
    """INST-LEAK-001 lowest point: the port, a radial direction of the adapter, must point at the lowest radial
    direction (straight down projected on the plane normal to the axis). On a vertical axis every radial
    direction is at one height."""
    a = _unit(axis_out)
    down = _sub((0.0, 0.0, -1.0), _mul(a, _dot((0.0, 0.0, -1.0), a)))
    if _norm(down) < math.sin(math.radians(tol_deg)):
        return True, "instrument axis vertical: every radial port position is at the same height"
    ang = _angle_deg(port_dir, down)
    return ang <= tol_deg, f"port {ang:.1f} deg from the lowest radial direction"


# ------------------------------------------------------------------ model geometry
def _ends(pc) -> list:
    g = pc.geom
    if pc.kind == "tube":
        return [g["p0"], g["p1"]]
    if pc.kind in ("ferrule", "branch_ferrule"):
        return [g["face"], g["weld_end"]]
    if pc.kind == "elbow":
        return [g["T1"], g["T2"]]
    if pc.kind == "tee":
        return [g["run_p0"], g["run_p1"], g["branch_end"]]
    return []


def _tees(m):
    for sp in m.spools:
        for pc in sp.pieces:
            if pc.kind == "tee":
                yield sp, pc


def _bore_r(m, od: float) -> float:
    w = m.wall(od)
    return (od - 2.0 * w) / 2.0 if w else float("nan")


def outward_axis(it):
    """Unit vector from the process out along a clamp instrument (its 'process' face points into the process)."""
    return _unit(_mul(it.faces["process"][1], -1.0))


def spool_part(it, P) -> dict | None:
    """An instrument spool part: {cmp, builtin: {face: in}, adapter, port} or None for any other item.

    builtin[face] is the straight run inside the part from the sensor to that run-end clamp face, along the part's
    native X (step x_dir from step plane_origin, so a part turned end for end reads right): to the tee centre for a
    branch sensor, to the nearer meter clamp face for an in-line meter (an INST_SPOOL_PARTS joint along X on that
    side, less half the joint gap). A face not along the run (the TT branch face) has no built-in run (0).
    adapter: the ifm adapter article the part lists (E + 5 digits), port: True when that part text says it has a
    leakage port."""
    cmp = getattr(it, "spool_cmp", None)
    rec = (getattr(P, "INST_SPOOL", None) or {}).get(cmp)
    st = it.step or {}
    if not rec or "plane_origin" not in st or "x_dir" not in st:
        return None
    o, xd = st["plane_origin"], _unit(st["x_dir"])
    gap = float(getattr(P, "JOINT_GAP", 0.0))
    run_joints = [j[0][0] for j in ((getattr(P, "INST_SPOOL_PARTS", None) or {}).get(cmp, {}).get("joints") or ())
                  if abs(j[1][0]) > 0.9]
    builtin = {}
    for name, (pt, d) in it.faces.items():
        x = _dot(_sub(pt, o), xd)
        if abs(_dot(_unit(d), xd)) < 0.9:
            builtin[name] = 0.0
            continue
        datum = min((abs(jx) - gap / 2.0 for jx in run_joints if jx * x > 0 and abs(jx) < abs(x)), default=0.0)
        builtin[name] = abs(x) - datum
    text = "; ".join(rec.get("parts", ()))
    ad = re.search(r"\bE\d{5}\b", text)
    port = bool(ad) and any(ad.group(0) in p and "leakage port" in p for p in rec.get("parts", ()))
    return {"cmp": cmp, "builtin": builtin, "adapter": ad.group(0) if ad else None, "port": port}


def holding_tee(m, it):
    """The tee whose centre lies on the instrument's axis, nearest behind its process face: (spool, piece, t),
    t = distance from the tee centre to the instrument face along the axis. None if none is found."""
    face, a = it.faces["process"][0], outward_axis(it)
    best = None
    for sp, pc in _tees(m):
        v = _sub(face, pc.geom["center"])
        t = _dot(v, a)
        if 0.0 < t <= MAX_BRANCH_IN and _norm(_sub(v, _mul(a, t))) <= AXIS_TOL_IN and (best is None or t < best[2]):
            best = (sp, pc, t)
    return best


def tee_side_face_gap(m, face):
    """Distance from an instrument face to the nearest pipe-side clamp face (ferrule face or integral tee outlet)."""
    best = None
    for sp in m.spools:
        for pc in sp.pieces:
            for k in ("face", "branch_face"):
                p = pc.geom.get(k)
                if p is not None:
                    d = _dist(p, face)
                    best = d if best is None or d < best else best
    return best


def reference_leg(pc, axis_out):
    """Of the tee's legs (run, branch), the one most perpendicular to the instrument axis: the flowing pipe."""
    g = pc.geom
    legs = [_unit(_sub(g["run_p1"], g["run_p0"])), _unit(g["bdir"])]
    return min(legs, key=lambda d: abs(_dot(d, axis_out)))


def _instrument_on_branch(m, pc) -> str | None:
    g = pc.geom
    bd = _unit(g["bdir"])
    for it in m.items.values():
        if it.kind != "instrument" or "process" not in it.faces:
            continue
        v = _sub(it.faces["process"][0], g["center"])
        t = _dot(v, bd)
        if 0.0 < t <= MAX_BRANCH_IN and _norm(_sub(v, _mul(bd, t))) <= AXIS_TOL_IN:
            return it.tag
    return None


def _probes(m, exclude: str):
    """Probes lying in a pipe: internal primitives of instruments, (tag, tip, unit direction tip->face)."""
    for it in m.items.values():
        if it.kind != "instrument" or it.tag == exclude:
            continue
        for p in it.prims:
            if p.get("internal") and p.get("type") == "cyl":
                yield it.tag, p["p0"], _unit(_sub(p["p1"], p["p0"]))


def _probe_hit(m, P, Q, bore_r, exclude):
    """Nearest TD2947-type probe tip on the straight P -> Q: a probe parallel to the run with its tip in the bore."""
    s = _unit(_sub(Q, P))
    L = _dist(P, Q)
    best = None
    for tag, tip, u in _probes(m, exclude):
        if abs(_dot(u, s)) < 0.99:
            continue
        x = _dot(_sub(tip, P), s)
        if -1e-6 <= x <= L + 1e-6 and _point_line_dist(tip, P, s) < bore_r and (best is None or x < best[0]):
            best = (x, f"{tag} probe tip")
    return best


def _across(m, P, cur_sid, tol, exclude_items):
    """What is clamped at the face P: ('spool', spool, its face) or ('item', item, None) or None."""
    best = None
    for sp in m.spools:
        if sp.sid == cur_sid:
            continue
        for pc in sp.pieces:
            if pc.kind == "ferrule" and _dist(pc.geom["face"], P) <= tol:
                d = _dist(pc.geom["face"], P)
                if best is None or d < best[0]:
                    best = (d, "spool", sp, pc.geom["face"])
    if best:
        return best
    for it in m.items.values():
        if it.key in exclude_items:
            continue
        for f in it.faces.values():
            d = _dist(f[0], P)
            if d <= tol and (best is None or d < best[0]):
                best = (d, "item", it, None)
    return best


def walk(m, P, sp, visited: set, acc: float, tees_count: bool, exclude_items: set, bore_r: float, tag: str,
         face_tol: float) -> dict:
    """Walk the centreline from point P (on spool sp, or None at a clamp face) away from the visited pieces, to
    the nearest disturbance. Returns {dist, by, end} (end True when the walk ran off the model, so the run is at
    least dist long but what lies beyond is unknown)."""
    for _ in range(500):
        nxt = None
        for pc in (sp.pieces if sp else ()):
            if pc.pid in visited:
                continue
            for i, e in enumerate(_ends(pc)):
                if _dist(e, P) <= END_TOL_IN:
                    nxt = (pc, i)
                    break
            if nxt:
                break
        if nxt is None:
            c = _across(m, P, sp.sid if sp else None, face_tol, exclude_items)
            if c is None:
                return {"dist": acc, "by": "open end (nothing clamped at the face)", "end": True}
            d, kind, obj, Q = c
            if kind == "spool":
                acc += d
                sp, P = obj, Q
                continue
            if obj.kind in ("tie-in",):
                return {"dist": acc + d, "by": f"{obj.tag} battery limit (field piping beyond is not modelled)", "end": True}
            return {"dist": acc + d, "by": f"{obj.tag} ({obj.kind}) clamp face", "end": False}
        pc, i = nxt
        visited.add(pc.pid)
        g = pc.geom
        if pc.kind in ("tube", "ferrule", "branch_ferrule"):
            Q = _ends(pc)[1 - i]
            hit = _probe_hit(m, P, Q, bore_r, tag)
            if hit:
                return {"dist": acc + hit[0], "by": hit[1], "end": False}
            acc += _dist(P, Q)
            P = Q
            continue
        if pc.kind == "elbow":
            return {"dist": acc, "by": f"elbow {pc.pid} tangent", "end": False}
        if pc.kind == "tee":
            name = g.get("name", pc.pid)
            if g.get("corner"):
                return {"dist": acc, "by": f"{name} tee used as a turn (weld end)", "end": False}
            if i == 2:
                return {"dist": acc, "by": f"{name} tee entered from its branch", "end": False}
            if tees_count:
                return {"dist": acc, "by": f"{name} tee (T-sections count, project value)", "end": False}
            if _instrument_on_branch(m, pc) is None:
                return {"dist": acc, "by": f"{name} tee (branch is not a dead-ended instrument)", "end": False}
            Q = _ends(pc)[1 - i]
            hit = _probe_hit(m, P, Q, bore_r, tag)
            if hit:
                return {"dist": acc + hit[0], "by": hit[1], "end": False}
            acc += _dist(P, Q)
            P = Q
            continue
        return {"dist": acc, "by": f"{pc.kind} {pc.pid}", "end": False}
    return {"dist": acc, "by": "walk did not end (500 pieces)", "end": True}


def straight_runs(m, it, tees_count: bool, face_tol: float) -> tuple[dict, dict, float] | None:
    """(upstream, downstream, tube OD) for an in-line item (faces in / out) or a branch instrument (its tee
    centre). Upstream is against the spool walk order (the flow direction)."""
    spool_of = {pc.pid: sp for sp in m.spools for pc in sp.pieces}
    if "in" in it.faces and "out" in it.faces:
        od = 2.0
        sp_in = _across(m, it.faces["in"][0], None, face_tol, {it.key})
        if sp_in and sp_in[1] == "spool":
            od = sp_in[2].od
        r = _bore_r(m, od)
        up = walk(m, it.faces["in"][0], None, set(), 0.0, tees_count, {it.key}, r, it.tag, face_tol)
        dn = walk(m, it.faces["out"][0], None, set(), 0.0, tees_count, {it.key}, r, it.tag, face_tol)
        return up, dn, od
    if "process" not in it.faces:
        return None
    ht = holding_tee(m, it)
    if ht is None:
        return None
    sp, pc, _t = ht
    if pc.geom.get("corner"):
        return None                       # an instrument at a turn has no straight run of its own
    g, r = pc.geom, _bore_r(m, sp.od)
    out = []
    for end in (g["run_p0"], g["run_p1"]):
        hit = _probe_hit(m, g["center"], end, r, it.tag)
        if hit:
            out.append({"dist": hit[0], "by": hit[1], "end": False})
            continue
        out.append(walk(m, end, spool_of[pc.pid], {pc.pid}, _dist(g["center"], end), tees_count, {it.key}, r,
                        it.tag, face_tol))
    return out[0], out[1], sp.od


# ------------------------------------------------------------------ the four rules
def check_dl002(m, P, cfg) -> list[Row]:
    dl, rows = cfg["dl"], []
    D_mm = dl["D_mm"]
    for tag, jr in dl["rows"].items():
        it = m.items.get(tag)
        if it is None:
            rows.append(Row(tag, "SAN-DL-002", FAIL, "not in the model", "", "tag has SAN-DL-002 project values"))
            continue
        if "process" not in it.faces:
            sp_part = spool_part(it, P)
            if sp_part:
                rows.append(Row(tag, "SAN-DL-002", NC, f"spool part {sp_part['cmp']}: branch and seat inside "
                                "the part, not exposed by the model", "",
                                "the part carries the maker's branch (short-outlet tee or weld-in adapter flush with the "
                                "bore crown); measuring L would need the part's seat datum in the model"))
            else:
                rows.append(Row(tag, "SAN-DL-002", NC, "no branch (process) face in the model", "", ""))
            continue
        ht = holding_tee(m, it)
        if ht is None:
            rows.append(Row(tag, "SAN-DL-002", NC, "no tee found on the instrument axis", "",
                            "model would need the instrument on a tee whose centre lies on its axis"))
            continue
        sp, pc, t = ht
        r_run = _bore_r(m, pc.od)
        D_model = (pc.geom["bod"] - 2.0 * (m.wall(pc.geom["bod"]) or float("nan"))) * MM_PER_IN
        gap = tee_side_face_gap(m, it.faces["process"][0])
        notes = [f"tee {pc.geom.get('name')} ({pc.geom.get('style') or 'standard'}"
                 f"{', at a turn' if pc.geom.get('corner') else ''}), seat {t:.3f} in from the run axis"]
        if gap is not None:
            notes.append(f"gasket gap {gap:.3f} in in the model")
        if gap is not None and gap < dl["gap_in"] - 1e-3:
            t += dl["gap_in"] - gap
            notes.append(f"short of the project gap {dl['gap_in']:.3f} in: difference added to L")
        L_mm = (t - r_run) * MM_PER_IN
        ad_model = (getattr(P, "INSTRUMENT_MODEL", {}).get(tag) or (None, None, ""))[1]
        ad_named = named_adapters(jr.get("sensor", ""))
        bad = []
        if abs(D_model - D_mm) > 0.05:
            bad.append(f"model branch bore {D_model:.1f} mm, project D {D_mm:.1f} mm")
        if ad_named and ad_model and ad_model not in ad_named:
            bad.append(f"model adapter {ad_model}, project row names {'/'.join(sorted(ad_named))}")
        if ad_named and not ad_model:
            notes.append(f"adapter {'/'.join(sorted(ad_named))} not modelled (instrument is "
                         f"{it.source or 'a placeholder'})")
        if jr.get("d_mm") is None and jr.get("max_L_mm") is None:
            # maker rule governs (no d, no max_L on the project row): measuring channel completely in the bore
            tip = next((p["p0"] for p in it.prims if p.get("internal") and p.get("type") == "cyl"), None)
            run_dir = _unit(_sub(pc.geom["run_p1"], pc.geom["run_p0"]))
            measured = f"adapter process end {L_mm:.1f} mm outside the {D_mm:.1f} mm bore wall"
            if tip is not None:
                into = (r_run - _point_line_dist(tip, pc.geom["center"], run_dir)) * MM_PER_IN
                notes.append(f"probe tip {abs(into):.1f} mm {'inside' if into >= 0 else 'OUTSIDE'} the bore wall")
                if into < 0:
                    bad.append("probe tip outside the bore")
            notes.append("measuring-channel extent is not exposed by the model (would need the LDL220 channel "
                         "span along the axis), so 'channel completely in the bore' is not machine-checked")
            res = FAIL if bad else NC
            rows.append(Row(tag, "SAN-DL-002", res, measured,
                            "maker rule: measuring channel completely in the pipe; weld-in adapter "
                            + "/".join(sorted(ad_named)) + " (project SAN-DL-002)",
                            "; ".join(bad + notes)))
            continue
        d_mm = float(jr.get("d_mm") or 0.0)
        limit = D_mm - d_mm
        if jr.get("max_L_mm") is not None and abs(float(jr["max_L_mm"]) - limit) > 0.05:
            notes.append(f"project max_L_mm {jr['max_L_mm']} differs from D - d = {limit:.1f} mm; the smaller is used")
            limit = min(limit, float(jr["max_L_mm"]))
        res = dl002_result(L_mm, limit)
        if bad:
            res = FAIL
        if jr.get("min_immersion_mm") is not None:
            tip = next((p["p0"] for p in it.prims if p.get("internal") and p.get("type") == "cyl"), None)
            if tip is None:
                notes.append(f"immersion >= {jr['min_immersion_mm']} mm NOT CHECKED: the model has no probe for "
                             f"{tag} (would need the probe tip, i.e. the sensor's seat datum and probe length)")
                if res == PASS:
                    res = NC
            else:
                run_dir = _unit(_sub(pc.geom["run_p1"], pc.geom["run_p0"]))
                imm = (r_run - _point_line_dist(tip, pc.geom["center"], run_dir)) * MM_PER_IN
                ok = imm >= float(jr["min_immersion_mm"])
                notes.append(f"immersion {imm:.1f} mm (>= {jr['min_immersion_mm']} mm: {'ok' if ok else 'FAIL'})")
                if not ok:
                    res = FAIL
        rows.append(Row(tag, "SAN-DL-002", res, f"L {L_mm:.1f} mm ({L_mm / MM_PER_IN:.3f} in)",
                        f"L < {limit:.1f} mm (D {D_mm:.1f} - d {d_mm:g})", "; ".join(bad + notes)))
    # every branch-mounted instrument in the model must have project values
    for it in m.items.values():
        if it.kind == "instrument" and "process" in it.faces and it.tag not in dl["rows"]:
            rows.append(Row(it.tag, "SAN-DL-002", FAIL, "branch-mounted instrument in the model", "",
                            "no SAN-DL-002 project values for this tag (<project>/01_Design_Basis/05_Standards_Specifications/Design_Rules/sanitary.yaml)"))
    return rows


def _instruments(m):
    return sorted((it for it in m.items.values() if it.kind == "instrument"), key=lambda i: i.tag)


def check_pos(m, cfg) -> list[Row]:
    rows = []
    for it in _instruments(m):
        allowed = allowed_positions(cfg["orientation"].get(it.tag))
        lim = "position " + ",".join(str(x) for x in sorted(allowed)) + (
            " (project orientation)" if allowed != {1, 2, 3, 4} else " (not 5)")
        if "process" in it.faces:
            ht = holding_tee(m, it)
            if ht is None:
                rows.append(Row(it.tag, "INST-POS-001", NC, "no tee found on the instrument axis", lim))
                continue
            a = outward_axis(it)
            ref = reference_leg(ht[1], a)
            what = "instrument axis"
        elif "in" in it.faces and "out" in it.faces:
            fi, fo = it.faces["in"][0], it.faces["out"][0]
            ref = _unit(_sub(fo, fi))
            boxes = [p for p in it.prims if p.get("type") == "box"]
            if not boxes:
                rows.append(Row(it.tag, "INST-POS-001", NC, "no off-axis body (transmitter) in the model", lim))
                continue
            c = _mul(tuple(sum(x) for x in zip(*[_mul(_add(b["min"], b["max"]), 0.5) for b in boxes])), 1.0 / len(boxes))
            v = _sub(c, fi)
            a = _unit(_sub(v, _mul(ref, _dot(v, ref))))
            what = "transmitter (off-axis body)"
        else:
            rows.append(Row(it.tag, "INST-POS-001", NC, "no process or in/out faces", lim))
            continue
        pos = position_of(a, ref)
        ang = _angle_deg(a, (0.0, 0.0, 1.0))
        if pos is None:
            rows.append(Row(it.tag, "INST-POS-001", PASS, f"vertical pipe; {what} {ang:.0f} deg from up", lim,
                            "the rule applies to horizontal pipes"))
            continue
        rows.append(Row(it.tag, "INST-POS-001", PASS if pos in allowed else FAIL,
                        f"position {pos} ({what} {ang:.0f} deg from up, horizontal pipe)", lim))
    return rows


def check_leak(m, P, cfg) -> list[Row]:
    rows = []
    for it in _instruments(m):
        lim = "leakage port at the lowest point (visibility not checked)"
        sp_part = spool_part(it, P)
        if sp_part:     # a spool part: the adapter is the one the part lists
            ad, where = sp_part["adapter"], f"in the {sp_part['cmp']} spool part"
            if not ad:
                rows.append(Row(it.tag, "INST-LEAK-001", NA, f"no separate adapter {where}", lim,
                                "integrated clamp or in-line meter"))
            elif sp_part["port"]:
                rows.append(Row(it.tag, "INST-LEAK-001", NC, f"adapter {ad} {where}: port direction not in the model",
                                lim, "the port clocking is set by the part record (weld-map note where the part "
                                "carries one); the model would need the port direction"))
            else:
                rows.append(Row(it.tag, "INST-LEAK-001", NC, f"adapter {ad} {where}: leakage port not in the part "
                                "record", lim, "model would need the adapter's leakage port and its direction"))
            continue
        ad = (getattr(P, "INSTRUMENT_MODEL", {}).get(it.tag) or (None, None, ""))[1]
        named = named_adapters((cfg["dl"]["rows"].get(it.tag) or {}).get("sensor", ""))
        if ad:
            item = getattr(P, "IFM_ADAPTER", {}).get(ad, {}).get("item", "")
            ext = next((e for e in it.step_extra if ad in e.get("label", "")), None)
            if "leakage port" not in item:
                rows.append(Row(it.tag, "INST-LEAK-001", NA, f"adapter {ad} has no leakage port in the model", lim))
                continue
            if ext is None or "process" not in it.faces:
                rows.append(Row(it.tag, "INST-LEAK-001", NC, f"adapter {ad}: port direction not in the model", lim))
                continue
            ok, txt = leak_port_ok(outward_axis(it), ext["x_dir"])
            rows.append(Row(it.tag, "INST-LEAK-001", PASS if ok else FAIL, f"{ad}: {txt}", lim))
        elif named:
            rows.append(Row(it.tag, "INST-LEAK-001", NC, f"adapter {'/'.join(sorted(named))} not modelled", lim,
                            "model would need the adapter and its leakage-port direction (as for E33209)"))
        else:
            rows.append(Row(it.tag, "INST-LEAK-001", NA, "no separate adapter or leakage port in the model", lim,
                            "integrated clamp or in-line meter"))
    return rows


def check_sr(m, P, cfg) -> list[Row]:
    rows = []
    face_tol = float(getattr(P, "JOINT_GAP", 0.08)) + 0.07
    model_rows = {r["tag"]: r for r in m.params.get("inst_sr_rows", ())}
    for tag, jr in cfg["sr"].items():
        it = m.items.get(tag)
        if it is None:
            rows.append(Row(tag, "INST-SR-001", FAIL, "not in the model", "", "tag has INST-SR-001 project values"))
            continue
        lims0 = sr_limits(jr, 2.0)
        res = straight_runs(m, it, lims0["tees_count"], face_tol)
        if res is None:
            rows.append(Row(tag, "INST-SR-001", NC, "no straight run found (no tee on the axis, or at a turn)", ""))
            continue
        up, dn, od = res
        lims = sr_limits(jr, od)
        sp_part = spool_part(it, P) if "in" in it.faces and "out" in it.faces else None
        parts, meas, limt, notes = [], [], [], []
        for side, r, face in (("up", up, "in"), ("down", dn, "out")):
            lim = lims.get(side)
            inside = sp_part["builtin"].get(face, 0.0) if sp_part else 0.0
            dist = inside + r["dist"]
            meas.append(f"{side} {dist:.2f} in = {inside:.2f} in inside {sp_part['cmp']} + {r['dist']:.2f} in to "
                        f"{r['by']}" if sp_part else f"{side} {r['dist']:.2f} in to {r['by']}")
            if lim is None:
                parts.append(NC)
                limt.append(f"{side}: {lims.get(side + '_why')}")
                continue
            limt.append(f"{side} >= {lims[side + '_text']}")
            if dist >= lim - 1e-6:
                parts.append(KNOWN if sp_part else PASS)
            elif r["end"]:
                parts.append(NC)
                notes.append(f"{side}stream run reaches the model end at {dist:.2f} in")
            else:
                parts.append(FAIL)
        if sp_part:
            notes.insert(0, KNOWN_SPOOL.format(cmp=sp_part["cmp"]))
        mr = model_rows.get(tag)
        if mr:
            notes.append(f"model's own INST-SR-001 rows: up {mr['up']['dist']:.2f} in ({mr['up']['by']}), down "
                         f"{mr['down']['dist']:.2f} in ({mr['down']['by']})")
        for k in ("upstream_DN_min", "downstream_DN_min"):
            if k in jr:
                notes.append(f"{k} {jr[k]} (maker minimum; the rule value above is the project value the model checks)")
        result = FAIL if FAIL in parts else (NC if NC in parts else (KNOWN if KNOWN in parts else PASS))
        rows.append(Row(tag, "INST-SR-001", result, "; ".join(meas), "; ".join(limt), "; ".join(notes)))
    return rows


def apply_accepts(rows: list[Row], accept: dict = ACCEPT) -> list[tuple]:
    """FAIL rows whose (rule, tag, measured) is in accept become KNOWN, with the record in the detail.
    Returns the accept keys that matched no FAIL row (stale entries)."""
    used = set()
    for r in rows:
        key = (r.rule, r.tag, r.measured)
        if r.result == FAIL and key in accept:
            r.result = KNOWN
            r.detail = f"known, tracked: {accept[key]}" + (f"; {r.detail}" if r.detail else "")
            used.add(key)
    return [k for k in accept if k not in used]


def evaluate(m, P, cfg, tag_class: dict[str, str] | None = None) -> list[Row]:
    """Every rule in scope (cfg["scope"]; a cfg without it runs all four, as the unit tests build it)."""
    scope = cfg.get("scope") or {}

    def on(rid):
        return rid not in scope or scope[rid][0] is not None
    rows = ((check_dl002(m, P, cfg) if on("SAN-DL-002") else []) + (check_pos(m, cfg) if on("INST-POS-001") else [])
            + (check_leak(m, P, cfg) if on("INST-LEAK-001") else []) + (check_sr(m, P, cfg) if on("INST-SR-001") else []))
    if not scope:
        return rows
    return apply_scope(rows, cfg, tag_classes(m) if tag_class is None else tag_class)


# ------------------------------------------------------------------ output
def summary(rows: list[Row], what: str) -> str:
    n = {k: sum(1 for r in rows if r.result == k) for k in (PASS, FAIL, NC, NA, KNOWN)}
    by = {rid: sum(1 for r in rows if r.rule == rid and r.result == FAIL) for rid in RULES}
    per = ", ".join(f"{k} {v}" for k, v in by.items() if v)
    state = "FAIL" if n[FAIL] else "PASS"
    return (f"sanitary: {state} - {n[FAIL]} of {len(rows)} tag x rule rows fail" + (f" ({per})" if per else "")
            + f"; {n[KNOWN]} known (spool parts, ACCEPT records), {n[NC]} not checked, {n[PASS]} pass, "
            f"{n[NA]} n/a; {', '.join(RULES)} on {what}")


def write_report(rows: list[Row], out: Path, head: str) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    pc, pj = out / "instrument-rules.csv", out / "instrument-rules.json"
    with open(pc, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["tag", "rule", "result", "measured", "limit", "detail"], lineterminator="\n")
        w.writeheader()
        w.writerows(asdict(r) for r in rows)
    pj.write_text(json.dumps({"summary": head, "rows": [asdict(r) for r in rows]}, indent=1, ensure_ascii=False) + "\n",
                  encoding="utf-8", newline="\n")
    return [pc, pj]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--report", type=Path, help="write instrument-rules.csv / .json into this folder")
    a = ap.parse_args(argv)
    if rp.skip_no_project("sanitary"):
        return 0
    try:
        cfg = load_rules()
    except Exception as e:  # noqa: BLE001
        print(f"sanitary: ERROR - design rules unreadable: {type(e).__name__}: {e}")
        return 3
    notes = [note for c, note in cfg["scope"].values() if c is None]
    if len(notes) == len(cfg["scope"]):
        print(f"sanitary: PASS - not checked: no rule in scope on this project yet ({len(notes)} of {len(RULES)} "
              f"rules applies_to unknown or without project values); nothing measured")
        for n in notes:
            print(f"  NOT CHECKED {n}")
        return 0
    missing = rule_scope.model_missing()
    if missing:
        print(f"sanitary: PASS - not checked: {missing}; nothing measured")
        return 0
    try:
        from skidlib import layout
        from skidlib import params as P
        m = layout.build()
    except Exception as e:  # noqa: BLE001
        print(f"sanitary: ERROR - model did not build: {type(e).__name__}: {e}")
        return 3
    rows = evaluate(m, P, cfg)
    stale = apply_accepts(rows)
    head = summary(rows, f"the {rp.SKID_MODEL_ID} source model")
    print(head)
    order = {FAIL: 0, KNOWN: 1, NC: 2, PASS: 3, NA: 4}
    for r in sorted(rows, key=lambda r: (RULES.index(r.rule), order[r.result], r.tag)):
        print(f"  {r.result:<11} {r.rule:<13} {r.tag:<7} {r.measured} | limit: {r.limit}"
              + (f" | {r.detail}" if r.detail else ""))
    for k in stale:
        print(f"  STALE ACCEPT {k[0]} {k[1]} \"{k[2]}\": no FAIL row has this measured value; remove the entry")
    print("  ASSUMPTION: positions are the nearest 45 deg step of the outward axis from straight up (1 top .. 5 "
          "bottom), on the flowing leg perpendicular to it; a pipe > 45 deg off horizontal is vertical")
    print("  ASSUMPTION: spool walk order is the flow direction (skidlib model.py); a straight-run range enforces "
          "its lower value (the conservative reading)")
    if cfg["dl"].get("assumption"):
        print(f"  {cfg['dl']['assumption']} (<project>/01_Design_Basis/05_Standards_Specifications/Design_Rules/sanitary.yaml SAN-DL-002)")
    if a.report:
        for p in write_report(rows, a.report, head):
            print(f"  wrote {p}")
    return 1 if any(r.result == FAIL for r in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
