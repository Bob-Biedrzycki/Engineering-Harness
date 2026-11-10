"""solid_clash - clashes measured on the real solids, and parts left unconnected.

interference.py works at envelope level and skips every pair that meets by design, so a valve lever that hits the
pipe or the valve beside it is never measured (Bob, chat, 2026-10-30: "valve handles with collisions", "valves that
weren't connected to anything"). This check builds each body as it is exported (cad.compound: the placed CPME STEP
of every library part, every pipe piece as its own solid, frame, plates and supports from their primitives) and,
for every pair whose boxes overlap, adjacent pairs included, measures the volume the two solids share.

    CLASH   two solids share more than VOL_TOL in^3 (adjacent pairs too: a lever into its neighbour)
    OPEN    a port of a placed part that meets no joint, pipe end or other part's port (connected to nothing)
    GAP     a port that has a joint but whose part's solid stands off the solid across it by more than GAP_TOL

Frame-to-frame, support-to-frame and plate pairs are not measured (they bear on each other by design). A port named
in OPEN_BY_DESIGN (drains, vents, relief outlets that discharge to atmosphere or a funnel) is listed, not failed.

Exit-code contract (harness/checks/README.md): 0 = PASS, 1 = FAIL, 3 = ERROR (could not run). First line = summary.
Run with --model-id / --config like the other model checks. --pairs-only skips the solids (OPEN only, seconds).
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists()) / "harness" / "lib"))
import repo_paths as rp  # noqa: E402

if rp.HAS_MODEL:
    sys.path.insert(0, str(rp.SKID_MODEL))

MM3 = 25.4 ** 3
VOL_TOL = 0.01      # in^3 shared before a pair is a clash (touching faces and tessellation noise stay under it)
BOX_TOL = 0.05      # in, box prefilter
PORT_TOL = 0.10     # in, a port meets a joint / pipe end / port within this
GAP_TOL = 0.06      # in, solid stand-off across a joint
BEARING = {"frame", "support", "plate"}
OPEN_BY_DESIGN = ("drain", "vent", "outlet_atm", "discharge", "test", "plug")


def _bbox_of_prims(prims, prim_bbox):
    bs = [prim_bbox(p) for p in prims]
    if not bs:
        return None
    return (tuple(min(b[0][k] for b in bs) for k in range(3)), tuple(max(b[1][k] for b in bs) for k in range(3)))


def main() -> int:
    if rp.skip_no_model("solid_clash"):
        return 0
    import rule_scope
    missing = rule_scope.model_missing()
    if missing:                                      # as interference.py: the project has no model yet
        print(f"solid_clash: PASS - not checked: {missing}; no bodies to compare")
        return 0
    pairs_only = "--pairs-only" in sys.argv
    t0 = time.time()
    try:
        from skidlib import layout
        from skidlib import vec as V
        from skidlib.model import piece_prims
        from skidlib.reports import prim_bbox
        m = layout.build(rp.MODEL_CONFIG or None)
    except (ImportError, TypeError) as e:
        # a model whose skidlib predates this check (no piece_prims / prim_bbox, or a build() that takes no
        # configuration) cannot be read by it; interference.py still compares its bodies at envelope level
        print(f"solid_clash: PASS - not checked: this model's skidlib does not give what the check reads "
              f"({type(e).__name__}: {e}); no bodies compared")
        return 0
    except Exception as e:  # noqa: BLE001
        print(f"solid_clash: ERROR - model did not build: {type(e).__name__}: {e}")
        return 3

    # ---- OPEN: every port of a placed part meets something ---------------------------------------------------------
    anchors = [j.point for j in m.joints]
    for pc in m.pieces():
        for v in pc.geom.values():
            if isinstance(v, tuple) and len(v) == 3 and all(isinstance(c, (int, float)) for c in v):
                anchors.append(v)
    face_pts = [(it.key, name, pt) for it in m.items.values() for name, (pt, _d) in it.faces.items()]
    # parts stacked on a tap (root valve, siphon, gauge, thermowell) are joined by `connects`, not by a joint
    partners: dict[str, set] = {}
    for it in m.items.values():
        if it.kind == "reservation":
            continue
        for c in it.connects:
            if c in m.items and m.items[c].kind == "reservation":
                continue
            partners.setdefault(it.key, set()).add(c)
            partners.setdefault(c, set()).add(it.key)

    def near_box(key, pt) -> bool:
        it = m.items.get(key)
        bb = _bbox_of_prims([p for p in it.prims if not p.get("zone")], prim_bbox) if it is not None else None
        return bb is not None and all(bb[0][k] - PORT_TOL <= pt[k] <= bb[1][k] + PORT_TOL for k in range(3))

    tubes = [(pc.geom["p0"], pc.geom["p1"], pc.od / 2) for pc in m.pieces() if pc.kind == "tube"]

    def on_pipe_wall(pt) -> bool:
        # a weld boss or adapter seated on a pipe's outside surface
        return any(abs(V.point_seg_dist(pt, a, b) - r) <= PORT_TOL for a, b, r in tubes)

    open_ports, open_ok = [], []
    for it in m.items.values():
        if it.kind in ("tie-in", "reservation") or it.kind in BEARING:
            continue
        joined = {n for n, (p, _d) in it.faces.items()
                  if any(V.dist(p, a) <= PORT_TOL for a in anchors)
                  or any(k != it.key and V.dist(p, q) <= PORT_TOL for k, _n, q in face_pts)
                  or any(near_box(k, p) for k in partners.get(it.key, ())) or on_pipe_wall(p)}
        for name, (pt, d) in it.faces.items():
            if name in joined:
                continue
            discharge = any(k.startswith(it.key + "-DISCH") for k in m.items)   # its kept-clear discharge route
            if any(w in name.lower() for w in OPEN_BY_DESIGN):
                open_ok.append((it, name, pt, "named open"))
            elif it.kind == "valve" and joined and (d is not None and d[2] < -0.7 or "drain valve" in it.note):
                open_ok.append((it, name, pt, "drain outlet"))
            elif it.kind == "valve" and joined and discharge:
                open_ok.append((it, name, pt, "relief discharge to the plant's safe point (HWS-RELIEF-001, HOLD)"))
            else:
                open_ports.append((it, name, pt))
    loose = [it for it in m.items.values()
             if it.kind in ("valve", "instrument") and not it.faces and not partners.get(it.key)]
    # a spool whose first or last face meets nothing (no joint, part, tie-in or other spool recorded there)
    joint_pts = [j.point for j in m.joints]
    for sp in m.spools:
        for end, label in ((sp.start, "start"), (sp.end, "end")):
            if end:
                continue
            pcs = sp.pieces[0] if label == "start" else sp.pieces[-1]
            g = pcs.geom
            pt = g.get("face") or (g.get("p0") if label == "start" else g.get("p1"))
            if pt is not None and any(V.dist(pt, q) <= PORT_TOL for q in joint_pts):
                continue
            # welded to another spool's branch stub or end, or seated on a part's port
            if pt is not None and (any(V.dist(pt, q) <= PORT_TOL for o in m.spools if o is not sp for pc2 in o.pieces
                                       for q in pc2.geom.values()
                                       if isinstance(q, tuple) and len(q) == 3 and not isinstance(q[0], tuple))
                                   or any(V.dist(pt, p) <= PORT_TOL for _k, _n, p in face_pts)):
                continue
            open_ports.append((type("S", (), {"key": sp.sid, "kind": "spool", "comp_id": "", "source": sp.line})(),
                               label, pt or (0.0, 0.0, 0.0)))

    # a tap stack (thredolet boss and what threads into it: root valve, siphon, gauge, thermowell, thermometer,
    # switch) overlaps its boss and its own pipe by design: the boss is drawn solid and the pipe wall unbored, so
    # thread engagement and the well's insertion read as shared volume. Those pairs are TAP, not clashes; a well tip
    # through the far wall is the model's own bore guard (hws.insertion_problems), not this check.
    stack_of: dict[str, str] = {}
    for it in m.items.values():
        if it.kind == "fitting" and it.source.startswith(("thredolet", "weldolet")):
            todo, seen = [it.key], {it.key}
            while todo:
                k = todo.pop()
                stack_of[k] = it.key
                for c in partners.get(k, ()):
                    if c in m.items and c not in seen and m.items[c].kind not in BEARING:
                        seen.add(c)
                        todo.append(c)
    piece_line = {pc.pid: pc.line for pc in m.pieces()}

    def tap_pair(a, b) -> bool:
        # the boss itself, the run pipe under the boss, and a thermometer in its own well; two other parts of one
        # stack (a vent valve's lever into the vent above it) are measured like any pair
        sa_, sb_ = stack_of.get(a), stack_of.get(b)
        if sa_ and sa_ == sb_ and (a == sa_ or b == sb_ or a + "-TW" == b or b + "-TW" == a):
            return True
        for s, other in ((sa_, b), (sb_, a)):
            if s and other in piece_line and piece_line[other] == m.items[s].line:
                return True
        return False

    # two parts joined at a face whose solids overlap only in a thin slab at that face: the vendor STEP's end sits a
    # few hundredths off its listed port. SEAT (information), not a clash
    SEAT_T = 0.15
    SEAT_V = 0.15       # in^3 shared by two parts joined at that face (a vendor STEP's flange a little off its port)
    BOLT_T = 1.5
    SLOPE_V = 0.25      # in^3: a 1:40 run's end against a square face, or a support under it, shares a sliver
    meet_pts: dict[frozenset, list] = {}
    for jn in m.joints:
        meet_pts.setdefault(frozenset((jn.a, jn.b)), []).append(jn.point)
    for k1, _n1, p1 in face_pts:
        for k2, _n2, p2 in face_pts:
            if k1 < k2 and V.dist(p1, p2) <= PORT_TOL:
                meet_pts.setdefault(frozenset((k1, k2)), []).append(p1)

    # a studded port (the plate exchangers: register frame "studded port face X 0 ... studs to X -54 mm") carries its
    # studs and the companion flange envelope in front of the port face in the vendor STEP; what bolts on there (the
    # pipe's flange, a flanged or threaded valve) overlaps them by design. Only the outside of the face, to the stud
    # tips, is excused: anything reaching back into the equipment (a lever into the frame plate) stays a clash.
    import re
    import components
    stud_depth = {}
    for r in components.current_rows():
        mo = re.search(r"studs to X -([\d.]+) mm", r.get("frame", ""))
        if mo:
            stud_depth[r["component_id"]] = float(mo.group(1)) / 25.4
    studded = {it.key: (it, stud_depth[it.comp_id]) for it in m.items.values() if it.comp_id in stud_depth}

    clashes, gaps, measured, failed, taps, seats, ports_ok = [], [], 0, [], 0, [], []
    if not pairs_only:
        try:
            from skidlib import cad
            from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
            from OCP.BRepExtrema import BRepExtrema_DistShapeShape
            from OCP.GProp import GProp_GProps
            from OCP.BRepGProp import BRepGProp
            from OCP.Bnd import Bnd_Box
            from OCP.BRepBndLib import BRepBndLib
        except Exception as e:  # noqa: BLE001
            print(f"solid_clash: ERROR - geometry kernel not importable: {type(e).__name__}: {e}")
            return 3
        REPO = rp.REPO
        bodies = []          # (owner, kind, group, bbox, lazy solid)
        for it in m.items.values():
            if it.kind in ("tie-in", "reservation") or not (it.prims or it.step.get("file")):
                continue
            prims = [p for p in it.prims if not p.get("zone")]
            bb = _bbox_of_prims(prims, prim_bbox)
            if bb is None:
                continue
            bodies.append([it.key, it.kind, it.key, bb, None, it])
        for sp in m.spools:
            for pc in sp.pieces:
                bb = _bbox_of_prims(piece_prims(pc), prim_bbox)
                if bb is not None:
                    bodies.append([pc.pid, "pipe", sp.sid, bb, None, pc])

        def solid(b):
            if b[4] is None:
                obj = b[5]
                if b[1] == "pipe":
                    s = cad.piece_solid(obj)
                elif obj.step.get("file") and (REPO / obj.step["file"]).is_file():
                    s = cad.placed_step(obj)
                else:
                    parts = [x for x in (cad.prim_solid(p) for p in obj.prims if not p.get("zone")) if x is not None]
                    s = parts[0] if parts else None
                    for x in parts[1:]:
                        s = s + x
                b[4] = s.wrapped if s is not None else False
            return b[4]

        def volume(shape) -> float:
            g = GProp_GProps()
            BRepGProp.VolumeProperties_s(shape, g)
            return abs(g.Mass()) / MM3

        # the pieces of one spool are consecutive by design: only pieces that are not neighbours are compared
        order = {}
        for sp in m.spools:
            for i, pc in enumerate(sp.pieces):
                order[pc.pid] = i
        for i in range(len(bodies)):
            oa, ka, ga, (la, ha), *_ = bodies[i]
            for j in range(i + 1, len(bodies)):
                ob, kb, gb, (lb, hb), *_ = bodies[j]
                if any(la[k] > hb[k] + BOX_TOL or lb[k] > ha[k] + BOX_TOL for k in range(3)):
                    continue
                if ka in BEARING and kb in BEARING:
                    continue
                if ka == "pipe" and kb == "pipe" and ga == gb and abs(order[oa] - order[ob]) <= 1:
                    continue
                if tap_pair(oa, ob):
                    taps += 1
                    continue
                sa, sb = solid(bodies[i]), solid(bodies[j])
                if not sa or not sb:
                    continue
                measured += 1
                try:
                    op = BRepAlgoAPI_Common(sa, sb)
                    v = volume(op.Shape()) if op.IsDone() else None
                except Exception as e:  # noqa: BLE001
                    failed.append((oa, ob, type(e).__name__))
                    continue
                if v is None:
                    failed.append((oa, ob, "boolean not done"))
                elif v > VOL_TOL:
                    # a joint names the spool, not its end piece
                    pts = (meet_pts.get(frozenset((oa, ob))) or meet_pts.get(frozenset((ga, ob)))
                           or meet_pts.get(frozenset((oa, gb))) or meet_pts.get(frozenset((ga, gb))))
                    eq = studded.get(oa) or studded.get(ob)
                    if eq is None and pts:
                        # a maker's equipment model drawn with its flange bolts: they pass through the mating flange
                        # within BOLT_T outside the port face (pump, pump-trap); only that side is excused
                        for k in (oa, ob):
                            it_k = m.items.get(k)
                            if it_k is not None and it_k.kind == "equipment" and it_k.step.get("file"):
                                eq = (it_k, BOLT_T)
                                break
                    if pts or eq:
                        bb = Bnd_Box()
                        BRepBndLib.Add_s(op.Shape(), bb)
                        lo, hi = bb.CornerMin(), bb.CornerMax()
                        lo = (lo.X() / 25.4, lo.Y() / 25.4, lo.Z() / 25.4)
                        hi = (hi.X() / 25.4, hi.Y() / 25.4, hi.Z() / 25.4)
                    if pts and ka == "pipe" and kb == "pipe" and v < SLOPE_V:
                        seats.append((v, oa, ob))         # a sloped (1:40) run butted square to a fitting
                        continue
                    if v < SLOPE_V / 2.5 and {ka, kb} == {"pipe", "support"}:
                        seats.append((v, oa, ob))         # a support set to the level line under a sloped run
                        continue
                    if pts and v < SEAT_V:
                        seats.append((v, oa, ob))         # a sliver at a bolted joint face: port data slop
                        continue
                    if pts:
                        thin = min(hi[k] - lo[k] for k in range(3)) <= SEAT_T
                        at_face = any(all(lo[k] - SEAT_T <= p[k] <= hi[k] + SEAT_T for k in range(3)) for p in pts)
                        if thin and at_face:
                            seats.append((v, oa, ob))
                            continue
                    if eq:
                        it_eq, depth = eq
                        corners = [(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
                        for fname, (fp, fd) in it_eq.faces.items():
                            ts = [V.dot(V.sub(c, fp), fd) for c in corners]
                            lat = max(V.dist(c, V.add(fp, V.mul(fd, t))) for c, t in zip(corners, ts))
                            if min(ts) >= -BOX_TOL and max(ts) <= depth + BOX_TOL and lat <= 10.0:
                                ports_ok.append((v, oa, ob, fname))
                                break
                        else:
                            clashes.append((v, oa, ka, ob, kb))
                        continue
                    clashes.append((v, oa, ka, ob, kb))

        # GAP: across each joint between a placed part and a pipe piece, and between parts stacked by `connects`,
        # the two solids should touch
        by_owner = {b[0]: b for b in bodies}
        links = [(jn.jid, jn.a, jn.b) for jn in m.joints if jn.kind != "tie-in"]
        # a `connects` pair is measured only where a port of one sits on the other (parts stacked on a tap); the rest
        # are envelope-level adjacency for interference.py (a routed line's pieces near the unit it leaves)
        def touching(a, b):
            ia, ib = m.items.get(a), m.items.get(b)
            if ia is None or ib is None:
                return False
            return any(V.dist(p, q) <= PORT_TOL for p, _d in ia.faces.values() for q, _e in ib.faces.values())
        links += [("connects", a, b) for a in sorted(partners) for b in sorted(partners[a]) if a < b and touching(a, b)]
        for jid, a, b in links:
            if a not in by_owner or b not in by_owner:
                continue
            ba, bb_ = by_owner[a], by_owner[b]
            if ba[1] == "pipe" and bb_[1] == "pipe":
                continue
            if ba[1] in BEARING or bb_[1] in BEARING:
                continue
            jn = type("L", (), {"jid": jid, "a": a, "b": b})
            sa, sb = solid(ba), solid(bb_)
            if not sa or not sb:
                continue
            try:
                d = BRepExtrema_DistShapeShape(sa, sb)
                gap = d.Value() / 25.4 if d.IsDone() else None
            except Exception:  # noqa: BLE001
                gap = None
            if gap is not None and gap > GAP_TOL:
                gaps.append((gap, jn))

    bad = len(clashes) + len(open_ports) + len(loose) + len(gaps)
    head = (f"{len(clashes)} clash(es) on the solids ({measured} pairs measured, {taps} tap-stack pairs by design), "
            f"{len(open_ports)} open port(s), "
            f"{len(gaps)} gap(s) at joints, {len(loose)} part(s) with no ports") if not pairs_only else (
            f"{len(open_ports)} open port(s), {len(loose)} part(s) with no ports (solids not measured: --pairs-only)")
    print(f"solid_clash: {'FAIL' if bad else 'PASS'} - {head}; {time.time() - t0:.0f} s")
    for v, oa, ka, ob, kb in sorted(clashes, reverse=True):
        print(f"  CLASH {v:8.3f} in^3  {oa} ({ka})  x  {ob} ({kb})")
    for it, name, pt in open_ports:
        print(f"  OPEN  {it.key} ({it.kind}, {it.comp_id or it.source}) port '{name}' at "
              f"({pt[0]:.1f}, {pt[1]:.1f}, {pt[2]:.1f}) meets nothing")
    for it in loose:
        print(f"  LOOSE {it.key} ({it.kind}) has no ports: it cannot be connected")
    for gap, jn in sorted(gaps, key=lambda g: -g[0]):
        print(f"  GAP   {gap:.3f} in  {jn.jid}  {jn.a} / {jn.b}")
    for it, name, _pt, why in open_ok:
        print(f"  open by design: {it.key} port '{name}' ({why})")
    for v, oa, ob in sorted(seats, reverse=True):
        print(f"  SEAT (information) {v:.3f} in^3 at the face  {oa} / {ob}: a STEP end a few hundredths off its port, "
              f"or a sloped run square against its fitting or support")
    for v, oa, ob, fname in sorted(ports_ok, reverse=True):
        print(f"  PORT (information) {v:.3f} in^3  {oa} / {ob} at {fname}: inside the studs, bolts or companion "
              f"flange envelope the vendor STEP carries in front of its port face")
    for oa, ob, why in failed:
        print(f"  NOT MEASURED {oa} x {ob}: {why}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
