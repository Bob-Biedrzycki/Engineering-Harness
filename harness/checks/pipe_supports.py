"""pipe_supports - STR-PS-002 placement and the STR-PS-001 support load calc, on the routed skidlib model.

Scope (PIPE-SVC-001; harness/lib/rule_scope.py): the lines whose service_class (line-list.csv) the project's
STR-PS-002 entry lists in applies_to (<project>/01_Design_Basis/05_Standards_Specifications/Design_Rules/structural.yaml,
`STR-PS-002: {applies_to: [...]}`): hygienic lines, and utility-water lines where the entry lists them (stainless tube).
applies_to `unknown`, no line in scope, or no model source yet: PASS - not checked, exit 0. (A project file in the
section layout, `pipe_supports: {applies_to_lines: [...]}`, is read too.)

Builds the centreline network of every in-scope line: tubes, elbows (arc length), tees (run and branch), ferrules,
and each in-line valve, instrument or strainer as one span between its clamp faces. Supports are the STR-PS-001
hangers (items PS-nnn-HGR) and the equipment nozzles and exchanger ports (HX-* faces) that carry the tube; a valve,
instrument or strainer never counts as a support (STR-PS-002), but a hanger clamped on a straight-run tube inside
a placed instrument spool part does: the part's span is split there. Pump (P-*) faces are pump connections (d);
tie-ins and capped branches are free ends.

Checks (harness/design-rules/structural.yaml STR-PS-002):
  (a) span between adjacent supports <= max_span_in; overhang from a free end to its support listed
  (b) every in-line component has a support within max_from_component_in of each clamp face
  (c) every elbow has a support within max_from_elbow_in of one of its tangent points
  (d) every pump connection has a support within max_from_pump_in
  (e) a vertical run longer than vertical_guide_over_in is listed for a guide
  (f) every hanger centre is >= min_clear_of_joint_in from its tube's end welds
Load calc (first pass, not a certification, Gate 3): weight of tube, fittings, clamps, water (SG 1.0) and
components, each element shared between its two nearest supports along the pipe by the lever rule (all of it
to the one support where the element overhangs past it). Per rod: axial stress, Euler load (fixed base, free
top, K = 2), bending + axial with 10 % of the load sideways at the clamp, sway at that load and at the
STR-PS-001 sizing side load. E is STR-PS-001 sizing_load_case E_psi and the side load its side_load_lb
(harness/design-rules/structural.yaml). The rod stress is compared with an allowable only where the rules give one
(STR-PS-001 sizing_load_case allowable_psi); the harness rule states its allowable in prose only, so until a value
field is designated (hard rule 11) the stress is listed and the stress check is NOT CHECKED.

Component weights: never assumed. The weight of an in-line or branch component is the project's record of it:
equipment-list.csv operating_weight_lb (else empty_weight_lb), or weight_lb of the current component register row
(job library, then project; harness/lib/components.py) whose component_id (or pid_tag, where a register carries that
column) is the key. A component with no recorded weight is listed "not checked (no weight)" and carries
nothing in the load calc, so the loads are a lower bound and say so.

Exit-code contract (harness/checks/README.md): 0 = PASS, 1 = FAIL, 3 = ERROR (could not run). First line = summary.
  python harness/checks/pipe_supports.py [--report <dir>]   writes pipe-support-calc.csv / .md there
"""
from __future__ import annotations

import argparse
import csv
import heapq
import math
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists()) / "harness" / "lib"))
import repo_paths as rp  # noqa: E402
import rule_scope  # noqa: E402
import components  # noqa: E402

if rp.HAS_PROJECT:
    sys.path.insert(0, str(rp.SKID_MODEL))

WATER = 0.036127            # lb/in^3, SG 1.0 (physics, not a rule value)
BASIS_LB = 50.0             # STR-PS-001 sizing load per support (harness structural.yaml STR-PS-001 sizing_basis)

# Findings accepted by decision on this project, with the record (as interference.py ACCEPTED). Printed, not failed.
# Every entry quotes Bob and names this project's record. All empty: nothing is accepted on this project yet.
ACCEPT_ZONE: dict = {"comps": set(), "why": ""}   # in-line components carried through other supports
ACCEPT_ON_NOZZLE: str | None = None    # a valve clamped straight on an equipment nozzle (tank, exchanger), carried by it
ACCEPT_TIE_IN: str | None = None       # a face that looks onto a tie-in (the plant pipe carries that side)
ACCEPT_NAMED: dict[str, str] = {}      # component tag -> record
ACCEPT_ELBOW: dict[str, str] = {}      # elbow piece id -> record
ACCEPT_PUMP: dict[str, str] = {}       # pump connection label ("P-nnn discharge") -> record
# Keyed by the support's role (the start of its PS-nnn member role, set by skidlib layout.rod_support), not its PS
# number: PS numbers follow the build order and shift when a support is added; the role does not.
ACCEPT_CLEARANCE: dict[str, str] = {}


def clearance_accept(m, hk):
    """The ACCEPT_CLEARANCE record for hanger hk (by its support member's role), or None."""
    it = m.items.get(hk)
    rod = m.items.get(it.tag) if it is not None else None
    role = (rod.member or {}).get("role", "") if rod is not None else ""
    return next((why for k, why in ACCEPT_CLEARANCE.items() if role.startswith(k)), None)


def rules(harness_dir: Path | None = None, project_dir: Path | None = None, classes_by_line: dict | None = None,
          job_dir: Path | None = None):
    """(STR-PS-002 values with by_od, lines in scope or None, notes, STR-PS-001 sizing load case).

    Three levels (harness/lib/rule_scope.py). Harness file: section layout (pipe_supports: [{id: STR-PS-002, ...}]).
    Job file (job/design-rules/structural.yaml) and project file: the rule id at the top level (STR-PS-002:
    {applies_to, values_by_od_in?}); a project file in the section layout (pipe_supports: {applies_to_lines,
    values_by_od_in}) is read as before. Values by tube OD: harness values_by_od_in ("3.0"), then the job's, then the
    project's; the top-level keys are the 2.0 in values. Scope: the job's applies_to narrowed by the project's."""
    h = rule_scope.read_yaml((harness_dir or rp.HARNESS_DESIGN_RULES) / "structural.yaml")
    jd = rule_scope.read_yaml((job_dir or rp.JOB_DESIGN_RULES) / "structural.yaml") or {}
    pdir = project_dir or rule_scope.project_rules_dir()
    j = (rule_scope.read_yaml(pdir / "structural.yaml") if pdir is not None else None) or {}
    r = rule_scope.find_rule(h, "STR-PS-002")
    if r is None:
        raise KeyError("STR-PS-002 not found in harness structural.yaml")
    sizing = dict((rule_scope.find_rule(h, "STR-PS-001") or {}).get("sizing_load_case") or {})
    old = j.get("pipe_supports") if isinstance(j.get("pipe_supports"), dict) else None
    entry = j.get("STR-PS-002") if isinstance(j.get("STR-PS-002"), dict) else None
    job_entry = rule_scope.find_rule(jd, "STR-PS-002")
    proj_by_od = ((entry or {}).get("values_by_od_in") or (old or {}).get("values_by_od_in") or {})
    r = dict(r)
    r["by_od"] = {**{float(k): v for k, v in (r.get("values_by_od_in") or {}).items()},
                  **{float(k): v for k, v in ((job_entry or {}).get("values_by_od_in") or {}).items()},
                  **{float(k): v for k, v in proj_by_od.items()}}
    if old is not None and entry is None and old.get("applies_to_lines"):
        return r, set(old["applies_to_lines"]), [], sizing
    scope_entry = rule_scope.merge_entries(None, job_entry, entry)
    lines, notes = rule_scope.lines_in_scope("STR-PS-002", scope_entry, classes_by_line)
    return r, lines, notes, sizing


def limits_for(r, od):
    """The STR-PS-002 values for a tube OD: the values_by_od_in entry when there is one, else the 2.0 in top level."""
    return {**r, **r["by_od"].get(round(float(od), 3), {})} if od is not None else r


def _num(v) -> float | None:
    try:
        return None if rule_scope.is_unknown(v) else float(str(v).strip())
    except ValueError:
        return None


def recorded_weights(data_dir: Path | None = None, libs: list | None = None) -> dict[str, tuple[float, str]]:
    """{tag: (lb, source)} from the records only: equipment-list.csv operating_weight_lb (water full), else
    empty_weight_lb; then weight_lb of the current component register rows (job library first, then project;
    harness/lib/components.py), keyed by component_id and by pid_tag where a register carries one. Nothing is assumed.
    libs: components.Library list (a test's scratch registers); default both libraries."""
    out: dict[str, tuple[float, str]] = {}
    eq = (data_dir or rp.DATA) / "equipment-list.csv"
    if eq.is_file():
        with open(eq, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                t = (row.get("tag") or "").strip()
                for col in ("operating_weight_lb", "empty_weight_lb"):
                    w = _num(row.get(col))
                    if t and w is not None:
                        out[t] = (w, f"equipment-list.csv {col} {w:g} lb")
                        break
    by_comp = components.weights(libs)
    for key, rec in by_comp.items():
        if key not in out:
            out[key] = rec
    # a P&ID tag names its part through the component_id column of the project's tag lists (Bob, chat, 2026-10-26)
    for name in ("equipment-list.csv", "valve-list.csv", "instrument-list.csv"):
        p = (data_dir or rp.DATA) / name
        if not p.is_file():
            continue
        with open(p, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                t, cid = (row.get("tag") or "").strip(), (row.get("component_id") or "").strip()
                if t and cid in by_comp and t not in out:
                    w, src = by_comp[cid]
                    out[t] = (w, f"{src} (via {name} component_id)")
    return out


WEIGHTS: dict[str, tuple[float, str]] | None = None   # read once per run (main), or set by a test


def comp_weight(key) -> tuple[float | None, str]:
    """(lb, source) for a component tag, or (None, 'not checked (no weight)') when the project records none."""
    global WEIGHTS
    if WEIGHTS is None:
        WEIGHTS = recorded_weights()
    if key in WEIGHTS:
        return WEIGHTS[key]
    return None, "not checked (no weight)"


class Net:
    def __init__(self):
        self.adj = defaultdict(list)        # node -> [(node, length, edge id)]
        self.edges = {}                     # id -> dict
        self.kind = {}                      # node -> support | pump | free | None
        self.label = {}

    @staticmethod
    def key(p):
        return tuple(round(c, 2) for c in p)

    def add(self, a, b, length, **info):
        ka, kb = self.snap(a) or self.key(a), self.snap(b) or self.key(b)
        eid = len(self.edges)
        self.edges[eid] = {"a": ka, "b": kb, "pa": tuple(a), "pb": tuple(b), "len": max(length, 1e-6), **info}
        self.adj[ka].append((kb, self.edges[eid]["len"], eid))
        self.adj[kb].append((ka, self.edges[eid]["len"], eid))
        return eid

    def snap(self, p, tol=0.06):
        """The network node at p, or the nearest within tol (faces and piece ends differ by rounding)."""
        k = self.key(p)
        if k in self.adj:
            return k
        best = min(self.adj, key=lambda n: sum((a - b) ** 2 for a, b in zip(n, p)), default=None)
        if best is not None and math.dist(best, p) <= tol:
            return best
        return None

    def mark(self, p, kind, label):
        k = self.snap(p)
        if k is None:
            return None
        if self.kind.get(k) != "support":
            self.kind[k] = kind
            self.label[k] = label
        return k

    def nearest_supports(self, start, skip_edge=None, n=2, start_dist=None, comps=False):
        """Up to n supports by path distance from start (a node, or {node: dist}), not passing a support.
        comps=True: each result also carries the in-line components on its path."""
        dist = dict(start_dist) if start_dist else {start: 0.0}
        prev = {}
        pq = [(d, k) for k, d in dist.items()]
        heapq.heapify(pq)
        found, seen = [], set()
        while pq and len(found) < n:
            d, u = heapq.heappop(pq)
            if u in seen:
                continue
            seen.add(u)
            if self.kind.get(u) == "support":
                if comps:
                    on, x = set(), u
                    while x in prev:
                        x, eid = prev[x]
                        if self.edges[eid].get("comp"):
                            on.add(self.edges[eid]["comp"])
                    found.append((u, d, on))
                else:
                    found.append((u, d))
                continue                    # never pass through a support
            for v, L, eid in self.adj[u]:
                if eid == skip_edge:
                    continue
                nd = d + L
                if nd < dist.get(v, 1e18):
                    dist[v] = nd
                    prev[v] = (u, eid)
                    heapq.heappush(pq, (nd, v))
        return found

    def reaches_free_end(self, start, skip_edge):
        """True when, leaving start away from skip_edge, the pipe ends at a free end (tie-in or open end) before
        any support or in-line component: the face looks onto the plant pipe."""
        stack, seen = [start], {start}
        while stack:
            u = stack.pop()
            if self.kind.get(u) == "free":
                return True
            if self.kind.get(u) == "support":
                continue
            for v, _, eid in self.adj[u]:
                if eid == skip_edge or v in seen or self.edges[eid].get("comp"):
                    continue
                seen.add(v)
                stack.append(v)
        return False


def build_net(m, lines):
    from skidlib.reports import piping_mass_rows
    from skidlib import vec as V
    from skidlib.model import elbow_chords
    net = Net()
    mass = {r["object"]: float(r["mass_lb"]) + float(r["liquid_in3"]) * WATER for r in piping_mass_rows(m)}
    point_loads = []                                   # (node, lb, what)
    hangers = [it for it in m.items.values() if it.key.endswith("-HGR")]
    hang_pts = [(it.key, it.step["plane_origin"]) for it in hangers]
    tube_hangers = defaultdict(list)                  # pid -> [(t, hanger key, point)]
    # clamp joints carry the gasket gap, so the two faces sit half of it either side of the joint point; seeding a
    # node there makes both faces snap to it and the joint stays one connection
    for j in m.joints:
        if j.line in lines:
            net.adj.setdefault(net.key(j.point), [])
    for sp in m.spools:
        if sp.line not in lines:
            continue
        for pc in sp.pieces:
            g, w = pc.geom, mass.get(pc.pid, 0.0)
            info = {"line": sp.line, "pid": pc.pid, "spool": sp.sid}
            if pc.kind == "tube":
                a, b = g["p0"], g["p1"]
                L = V.dist(a, b)
                cuts = []
                for hk, hp in hang_pts:
                    if V.point_seg_dist(hp, a, b) < 0.02:
                        t = V.dot(V.sub(hp, a), V.sub(b, a)) / (L * L)
                        cuts.append((t, hk, hp))
                        tube_hangers[pc.pid].append((t * L, L, hk))
                pts = [(0.0, a)] + [(t, hp) for t, _, hp in sorted(cuts)] + [(1.0, b)]
                for (t0, p0), (t1, p1) in zip(pts, pts[1:]):
                    net.add(p0, p1, (t1 - t0) * L, kind="tube", w=w * (t1 - t0), **info)
                for _, hk, hp in cuts:
                    net.mark(hp, "support", hk)
            elif pc.kind == "elbow":
                ch = elbow_chords(g, 8)
                for p0, p1 in zip(ch, ch[1:]):
                    net.add(p0, p1, pc.length / 8, kind="elbow", w=w / 8, elbow=pc.pid, **info)
                net.edges[len(net.edges) - 1]["elbow_end"] = True
            elif pc.kind == "tee":
                c = g["center"]
                for p in (g["run_p0"], g["run_p1"], g["branch_end"]):
                    net.add(c, p, V.dist(c, p), kind="tee", w=w / 3, **info)
            else:
                net.add(g["weld_end"], g["face"], V.dist(g["weld_end"], g["face"]), kind=pc.kind, w=w, **info)
    for j in m.joints:
        if j.line in lines and net.snap(j.point):
            point_loads.append((net.snap(j.point), mass.get(j.jid, 0.0), j.jid))
    comps, unplaced, no_weight = [], [], []
    # A hanger may clamp a straight-run tube inside a placed instrument spool part. Such a hanger is a support like
    # any other: the component's span is split at it and its clearance from the tube's end welds is checked against
    # that tube.
    inst_hangers = defaultdict(list)                  # instrument tag -> [(hanger key, point)]
    for sp in getattr(m, "inst_spools", []):
        for pc in sp.pieces:
            if pc.kind != "tube":
                continue
            a, b = pc.geom["p0"], pc.geom["p1"]
            L = V.dist(a, b)
            for hk, hp in hang_pts:
                if L > 0 and V.point_seg_dist(hp, a, b) < 0.02:
                    t = V.dot(V.sub(hp, a), V.sub(b, a)) / (L * L)
                    tube_hangers[pc.pid].append((t * L, L, hk))
                    inst_hangers[sp.inst_tag].append((hk, hp))

    def add_comp(it, f0, f1):
        """The component as one span between its clamp faces, split at any hanger on its own tube; returns the
        edge ids in face order (in face first)."""
        wt, why = comp_weight(it.key)
        if wt is None:
            no_weight.append(it.key)
            wt = 0.0
        L = math.dist(f0, f1)
        cuts = []
        for hk, hp in inst_hangers.get(it.tag, ()):
            if L > 0 and V.point_seg_dist(hp, f0, f1) < 0.05:
                cuts.append((V.dot(V.sub(hp, f0), V.sub(f1, f0)) / (L * L), hk, hp))
            else:
                unplaced.append(f"{hk} (on {it.key}'s tube, off its face-to-face line)")
        pts = [(0.0, f0)] + [(t, hp) for t, _, hp in sorted(cuts)] + [(1.0, f1)]
        eids = [net.add(p0, p1, (t1 - t0) * L, kind="component", w=wt * (t1 - t0), comp=it.key, why=why, line=it.line)
                for (t0, p0), (t1, p1) in zip(pts, pts[1:])]
        for _, hk, hp in cuts:
            net.mark(hp, "support", hk)
        return tuple(eids)

    # in-line components first: a valve clamped straight onto a nozzle has a face no pipe piece ends at, and
    # its span makes that node, so the nozzle can then mark it as a support
    for it in m.items.values():
        if it.kind in ("valve", "instrument", "equipment") and it.line in lines and "in" in it.faces \
                and "out" in it.faces and not it.key.startswith(("P-", "HX-")):
            f = [it.faces["in"][0], it.faces["out"][0]]
            if any(net.snap(p) for p in f):
                comps.append((it.key, add_comp(it, f[0], f[1])))
    done = {k for k, _ in comps}
    for it in m.items.values():
        if it.key in done:
            continue
        if it.kind == "nozzle":
            for pt, _ in it.faces.values():
                net.mark(pt, "support", it.key)
        elif it.key.startswith("HX-") and it.kind == "equipment":
            # an exchanger's ports carry the tube that lands on them; only the faces the model gives, and only
            # those on the network (an in-scope line), are marked
            for name, (pt, _) in (it.faces or {}).items():
                if net.snap(pt):
                    net.mark(pt, "support", f"{it.key} {name}")
        elif it.key.startswith("P-") and it.kind == "equipment":
            for name, (pt, _) in it.faces.items():
                net.mark(pt, "pump", f"{it.key} {name}")
        elif it.kind == "tie-in":
            net.mark(it.faces["face"][0], "free", it.key)
        elif it.kind == "fitting" and it.line in lines and "out" in it.faces and net.snap(it.faces["out"][0]):
            # a clamp x clamp reducer on an equipment port (a relief valve port, say): the line must carry no
            # load on the port, so its end there is a free end (overhang listed), not a support
            net.mark(it.faces["out"][0], "free", it.key)
        elif it.kind in ("valve", "instrument", "equipment") and it.line in lines:
            f = [net.snap(it.faces[k][0]) for k in ("in", "out") if k in it.faces]
            if len(f) == 2 and all(f):
                comps.append((it.key, add_comp(it, f[0], f[1])))
            elif "process" in it.faces and net.snap(it.faces["process"][0]):
                wt, why = comp_weight(it.key)
                if wt is None:
                    no_weight.append(it.key)
                else:
                    point_loads.append((net.snap(it.faces["process"][0]), wt, f"{it.key} ({why})"))
            elif it.faces and not it.key.startswith("IP-"):
                unplaced.append(it.key)
    net.unplaced = unplaced
    net.no_weight = sorted(set(no_weight))
    return net, comps, point_loads, tube_hangers


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", type=Path)
    a = ap.parse_args()
    if rp.skip_no_project("pipe_supports"):
        return 0
    try:
        r, lines, notes, sizing = rules()
    except Exception as e:  # noqa: BLE001
        print(f"pipe_supports: ERROR - design rules unreadable: {type(e).__name__}: {e}")
        return 3
    if not lines:
        why = "; ".join(notes) or "STR-PS-002: no line on line-list.csv has a service class in its applies_to"
        print(f"pipe_supports: PASS - not checked: no line in scope ({why}); nothing measured")
        return 0
    missing = rule_scope.model_missing()
    if missing:
        print(f"pipe_supports: PASS - not checked: {missing}; {len(lines)} line(s) in scope, nothing measured")
        return 0
    try:
        from skidlib import layout, params as P
        m = layout.build()
    except Exception as e:  # noqa: BLE001
        print(f"pipe_supports: ERROR - model did not load: {type(e).__name__}: {e}")
        return 3
    e_psi = float(sizing["E_psi"]) if not rule_scope.is_unknown(sizing.get("E_psi")) else None
    allow_psi = float(sizing["allowable_psi"]) if not rule_scope.is_unknown(sizing.get("allowable_psi")) else None
    side_lb = float(sizing["side_load_lb"]) if not rule_scope.is_unknown(sizing.get("side_load_lb")) else None
    net, comps, point_loads, tube_hangers = build_net(m, lines)
    od_of = {}
    for sp_ in m.spools:
        od_of.setdefault(sp_.line, getattr(sp_, "od", None))

    def R(line):
        return limits_for(r, od_of.get(line))
    sup = [k for k, v in net.kind.items() if v == "support"]
    fails, rows = [], []

    # (a) spans: walk out from every support to the next supports; free ends give overhangs
    spans, span_comps, span_line, accepted = {}, {}, {}, []
    for s in sup:
        for v, L, eid in net.adj[s]:
            on0 = {net.edges[eid]["comp"]} if net.edges[eid].get("comp") else set()
            for t, d, on in net.nearest_supports(None, start_dist={v: L}, n=8, comps=True):
                if t != s:
                    key = tuple(sorted((s, t)))
                    if d < spans.get(key, 1e18):
                        spans[key], span_comps[key] = d, on | on0
                        span_line[key] = net.edges[eid].get("line")
    for (a_, b_), d in sorted(spans.items(), key=lambda z: -z[1]):
        mx = R(span_line.get((a_, b_)))["max_span_in"]
        if d <= mx + 1e-6:
            continue
        msg = f"(a) span {d:.1f} in between {net.label[a_]} and {net.label[b_]} > {mx} in"
        if span_comps[(a_, b_)] & ACCEPT_ZONE["comps"]:
            accepted.append((msg, ACCEPT_ZONE["why"]))
        else:
            fails.append(msg)
    free = [k for k, v in net.kind.items() if v == "free"] + [k for k in net.adj if len(net.adj[k]) == 1 and k not in net.kind]
    overhangs = []
    for k in free:
        ns = net.nearest_supports(k, n=1)
        overhangs.append((net.label.get(k, f"open end {k}"), ns[0][1] if ns else None, net.label.get(ns[0][0]) if ns else "none"))
    # (b) components
    comp_rows = []
    for key, eids in comps:
        faces = {"a": net.edges[eids[0]]["a"], "b": net.edges[eids[-1]]["b"]}
        # one span: never walk through the component to its far face. Split at a hanger on its own tube:
        # walking in from a face meets that hanger first, so the walk may enter the component.
        skip = eids[0] if len(eids) == 1 else None
        for end in ("a", "b"):
            ns = net.nearest_supports(faces[end], skip_edge=skip, n=1)
            d = ns[0][1] if ns else None
            comp_rows.append((key, end, d, net.label.get(ns[0][0]) if ns else "none"))
            mc = R(net.edges[eids[0]].get("line"))["max_from_component_in"]
            if d is None or d > mc + 1e-6:
                msg = (f"(b) {key} {'in' if end == 'a' else 'out'} face: nearest support "
                       f"{'none' if d is None else f'{d:.1f} in'} > {mc} in")
                other = faces["b" if end == "a" else "a"]
                if key in ACCEPT_ZONE["comps"]:
                    accepted.append((msg, ACCEPT_ZONE["why"]))
                elif key in ACCEPT_NAMED:
                    accepted.append((msg, ACCEPT_NAMED[key]))
                # valve on an equipment nozzle (tank, exchanger); note: the test below matches TK- labels only
                elif ACCEPT_ON_NOZZLE and net.kind.get(other) == "support" and net.label.get(other, "").startswith("TK-"):
                    accepted.append((msg, ACCEPT_ON_NOZZLE))
                elif ACCEPT_TIE_IN and net.reaches_free_end(faces[end], eids[0 if end == "a" else -1]):
                    accepted.append((msg, ACCEPT_TIE_IN))
                else:
                    fails.append(msg)
    # (c) elbows
    elbows = defaultdict(list)
    for eid, e in net.edges.items():
        if e.get("elbow"):
            elbows[e["elbow"]].append(eid)
    elbow_rows = []
    for pid, eids in elbows.items():
        ends = [net.edges[eids[0]]["a"], net.edges[eids[-1]]["b"]]
        best = None
        for k in ends:
            ns = net.nearest_supports(k, n=1)
            if ns and (best is None or ns[0][1] < best[0]):
                best = (ns[0][1], net.label[ns[0][0]])
        elbow_rows.append((pid, best))
        me = R(net.edges[eids[0]].get("line"))["max_from_elbow_in"]
        if best is None or best[0] > me + 1e-6:
            msg = (f"(c) elbow {pid}: nearest support {'none' if best is None else f'{best[0]:.1f} in'} "
                   f"> {me} in")
            if pid in ACCEPT_ELBOW:
                accepted.append((msg, ACCEPT_ELBOW[pid]))
            else:
                fails.append(msg)
    # (d) pump connections
    pump_rows = []
    for k, v in net.kind.items():
        if v == "pump":
            ns = net.nearest_supports(k, n=1)
            d = ns[0][1] if ns else None
            pump_rows.append((net.label[k], d, net.label.get(ns[0][0]) if ns else "none"))
            if d is None or d > r["max_from_pump_in"] + 1e-6:
                msg = (f"(d) {net.label[k]}: nearest support {'none' if d is None else f'{d:.1f} in'} "
                       f"> {r['max_from_pump_in']} in")
                if net.label[k] in ACCEPT_PUMP:
                    accepted.append((msg, ACCEPT_PUMP[net.label[k]]))
                else:
                    fails.append(msg)
    # (e) vertical runs
    vert = []
    seen = set()
    for eid, e in net.edges.items():
        if eid in seen or e["kind"] not in ("tube", "ferrule", "branch_ferrule"):
            continue
        dz = abs(e["pb"][2] - e["pa"][2])
        if dz / e["len"] < 0.95:
            continue
        chain, stack = 0.0, [eid]
        while stack:
            x = stack.pop()
            if x in seen:
                continue
            seen.add(x)
            ex = net.edges[x]
            chain += ex["len"]
            for n_ in (ex["a"], ex["b"]):
                for _, _, y in net.adj[n_]:
                    ey = net.edges[y]
                    if y not in seen and ey["kind"] in ("tube", "ferrule", "branch_ferrule") and \
                            abs(ey["pb"][2] - ey["pa"][2]) / ey["len"] >= 0.95:
                        stack.append(y)
        vg = R(e["line"])["vertical_guide_over_in"]
        if chain > vg:
            vert.append((e["line"], e["pid"], chain))
            fails.append(f"(e) vertical run {chain:.1f} in on {e['line']} at {e['pid']} > {vg} in: needs a guide")
    # (f) hanger clearance on its tube
    clr_rows = []
    for pid, hs in tube_hangers.items():
        for s_, L, hk in hs:
            c = min(s_, L - s_)
            clr_rows.append((hk, pid, c))
            mj = R(pid.split("-SP")[0])["min_clear_of_joint_in"]
            if c < mj - 1e-6:
                msg = f"(f) {hk} on {pid}: {c:.2f} in from the tube end weld < {mj} in"
                why = clearance_accept(m, hk)
                if why:
                    accepted.append((msg, why))
                else:
                    fails.append(msg)

    # load calc
    reaction = defaultdict(float)
    contrib = defaultdict(list)
    unsupported = 0.0

    def share(node_dist, lb, what):
        nonlocal unsupported
        ns = net.nearest_supports(None, start_dist=node_dist, n=2)
        if not ns:
            unsupported += lb
            return
        if len(ns) == 1:
            reaction[ns[0][0]] += lb
            contrib[ns[0][0]].append((what, lb))
            return
        (s1, d1), (s2, d2) = ns
        f1 = d2 / (d1 + d2) if d1 + d2 > 0 else 1.0
        reaction[s1] += lb * f1
        reaction[s2] += lb * (1 - f1)
        contrib[s1].append((what, lb * f1))
        contrib[s2].append((what, lb * (1 - f1)))

    for eid, e in net.edges.items():
        n = max(1, int(math.ceil(e["len"] / 2.0)))
        for i in range(n):
            t = (i + 0.5) / n
            share({e["a"]: t * e["len"], e["b"]: (1 - t) * e["len"]}, e["w"] / n,
                  e.get("comp") or e.get("elbow") or e["kind"])
    for k, lb, what in point_loads:
        share({k: 0.0}, lb, what)

    rod = P.SUPPORT_ROD
    d_ = rod["d"]
    if rod.get("shape") == "square":
        # square tube supports (STR-PS-001); section from the model params
        sp_ = P.square_tube_props(rod["b"], rod["t"])
        A, I_, S_ = sp_["A"], sp_["I"], sp_["S"]
    elif rod.get("shape") == "round_tube" and hasattr(P, "round_tube_props"):
        # round tube supports: OD rod["b"] x wall rod["t"]
        sp_ = P.round_tube_props(rod["b"], rod["t"])
        A, I_, S_ = sp_["A"], sp_["I"], sp_["S"]
    else:
        A, I_ = math.pi * d_ ** 2 / 4, math.pi * d_ ** 4 / 64
        S_ = I_ / (d_ / 2)
    for s in sorted(sup, key=lambda k: net.label[k]):
        lab, F = net.label[s], reaction[s]
        top = sorted(((sum(v for w_, v in contrib[s] if w_ == w0), w0) for w0 in {w for w, _ in contrib[s]}), reverse=True)[:3]
        row = {"support": lab, "load_lb": round(F, 2), "largest": "; ".join(f"{w} {v:.1f}" for v, w in top)}
        it = m.items.get(lab)
        if it is not None and lab.endswith("-HGR"):
            ps = m.items[it.tag]
            L = ps.member["length"]
            sig = F / A + 0.1 * F * L / S_
            row.update({"rod": ps.key, "rod_d_in": d_, "section": rod.get("section", ""), "rod_len_in": round(L, 2),
                        "axial_bend_psi": round(sig),
                        "stress_ratio": round(sig / allow_psi, 3) if allow_psi else "not checked",
                        "over_50lb_basis": "YES" if F > BASIS_LB else ""})
            if e_psi:
                pcr = math.pi ** 2 * e_psi * I_ / (2 * L) ** 2
                row.update({"euler_lb": round(pcr), "euler_margin": round(pcr / F, 1) if F > 0 else "",
                            "sway_at_10pct_in": round(0.1 * F * L ** 3 / (3 * e_psi * I_), 4),
                            "sway_at_side_load_in": round(side_lb * L ** 3 / (3 * e_psi * I_), 4) if side_lb else ""})
            if allow_psi and sig > allow_psi:
                fails.append(f"rod {ps.key}: {sig:.0f} psi > {allow_psi:.0f} psi")
        else:
            row.update({"rod": "equipment nozzle / port (reaction only)"})
        rows.append(row)

    n_h = sum(1 for x in rows if str(x["support"]).endswith("-HGR"))
    max_span = max(spans.values()) if spans else 0.0
    status = "FAIL" if fails else "PASS"
    print(f"pipe_supports: {status} - {len(fails)} STR-PS-002 / rod finding(s), {len(accepted)} accepted by decision; {n_h} hangers, "
          f"{len(sup) - n_h} equipment supports, longest span {max_span:.1f} in, "
          f"{len(comps)} in-line components, {sum(reaction.values()):.0f} lb carried"
          + (f", {unsupported:.0f} lb on no support" if unsupported else ""))
    for f in fails:
        print("  " + f)
    for f, why in accepted:
        print(f"  ACCEPTED {f}: {why}")
    if net.unplaced:
        print("  not on the network (not checked): " + ", ".join(net.unplaced))
    if net.no_weight:
        print("  not checked (no weight): " + ", ".join(net.no_weight) + " - no weight recorded (equipment-list.csv, "
              "component index); they carry nothing above, so every support load is a lower bound")
    if not allow_psi:
        print("  rod stress NOT CHECKED: no allowable stress value in STR-PS-001 sizing_load_case (allowable_psi); "
              "stresses are listed in the report only")
    if not e_psi:
        print("  Euler load and sway NOT CHECKED: no E_psi in STR-PS-001 sizing_load_case")
    for n_ in notes:
        print(f"  NOTE {n_}")
    if a.report:
        a.report.mkdir(parents=True, exist_ok=True)
        keys = ["support", "load_lb", "rod", "rod_d_in", "section", "rod_len_in", "axial_bend_psi", "stress_ratio", "euler_lb",
                "euler_margin", "sway_at_10pct_in", "sway_at_side_load_in", "over_50lb_basis", "largest"]
        with open(a.report / "pipe-support-calc.csv", "w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=keys, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
        md = ["# Pipe support calc (STR-PS-001 load, STR-PS-002 placement)", "",
              "Generated by harness/checks/pipe_supports.py from the routed model. First pass, not a certification "
              "(Gate 3). Method and weights: the script docstring.", "",
              f"**Result: {status}**, {len(fails)} finding(s).", ""]
        md += [f"- {f}" for f in fails] or ["- none"]
        md += ["", f"Accepted by decision ({len(accepted)}):", ""] + [f"- {f}: {why}" for f, why in accepted]
        md += ["", f"Not checked (no weight recorded; loads are a lower bound): {', '.join(net.no_weight) or 'none'}"]
        md += ["", "## Supports and loads", "", "| Support | Load lb | Rod | Rod in | Stress ratio | Euler margin | "
               f"Sway 10 % in | Sway at {side_lb:g} lb in | Largest contributors |" if side_lb else
               "| Support | Load lb | Rod | Rod in | Stress ratio | Euler margin | Sway 10 % in | Sway at side load in | "
               "Largest contributors |", "|---|---|---|---|---|---|---|---|---|"]
        for x in rows:
            md.append(f"| {x['support']} | {x['load_lb']} | {x.get('rod', '')} | {x.get('rod_len_in', '')} | "
                      f"{x.get('stress_ratio', '')} | {x.get('euler_margin', '')} | {x.get('sway_at_10pct_in', '')} | "
                      f"{x.get('sway_at_side_load_in', '')} | {x['largest']} |")
        md += ["", "## (a) Spans between adjacent supports", "", "| From | To | Span in |", "|---|---|---|"]
        for (a_, b_), d in sorted(spans.items(), key=lambda z: -z[1]):
            md.append(f"| {net.label[a_]} | {net.label[b_]} | {d:.1f} |")
        md += ["", "## Free ends (overhang to the nearest support)", "", "| End | Overhang in | Support |", "|---|---|---|"]
        md += [f"| {x} | {'' if d is None else f'{d:.1f}'} | {s_} |" for x, d, s_ in overhangs]
        md += ["", "## (b) In-line components", "", "| Component | Face | Nearest support in | Support |", "|---|---|---|---|"]
        md += [f"| {k} | {'in' if e == 'a' else 'out'} | {'none' if d is None else f'{d:.1f}'} | {s_} |" for k, e, d, s_ in comp_rows]
        md += ["", "## (c) Elbows", "", "| Elbow | Nearest support in | Support |", "|---|---|---|"]
        md += [f"| {p} | {'none' if b is None else f'{b[0]:.1f}'} | {'' if b is None else b[1]} |" for p, b in elbow_rows]
        md += ["", "## (d) Pump connections", "", "| Connection | Nearest support in | Support |", "|---|---|---|"]
        md += [f"| {x} | {'none' if d is None else f'{d:.1f}'} | {s_} |" for x, d, s_ in pump_rows]
        md += ["", "## (f) Hanger clearance from the tube end welds", "", "| Hanger | Tube | Clearance in |", "|---|---|---|"]
        md += [f"| {h} | {p} | {c:.2f} |" for h, p, c in sorted(clr_rows)]
        (a.report / "pipe-support-calc.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
