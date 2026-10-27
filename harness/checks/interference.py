"""interference - piping vs frame vs equipment clashes, envelope level.

Checks every pair of bodies in the routed model built by <project>/03_Working_Design/CAD/01_Master_Assembly/<MODEL-ID>/skidlib
(pipe pieces, valves, instruments, equipment envelopes, frame, supports,
reservations / keep-outs). Bodies that meet by design are skipped: pieces of
the same spool, anything that shares a clamp face or tee branch face, a
nozzle and its tank, a support and what it stands on, frame-to-frame, and the
tie-in markers. Vendor models are checked through envelope primitives
(boxes / cylinders in skidlib), not their exact B-rep, so a PASS here means no
envelope overlap deeper than TOL. Clamp to clamp (2026-10-07): every pair of clamps
within 8 in is measured on its ring and lobes in the clamp's own frame (skidlib.reports.clamp_gap); an overlap deeper
than TOL is a clash, a gap under 0.5 in is printed as NEAR (information).

Exit-code contract (harness/checks/README.md): 0 = PASS, 1 = FAIL, 3 = ERROR (could not run). First line = summary.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists()) / "harness" / "lib"))
import repo_paths as rp  # noqa: E402
import rule_scope  # noqa: E402

REPO = rp.REPO
if rp.HAS_PROJECT:
    sys.path.insert(0, str(rp.SKID_MODEL))

TOL = 0.05   # in; touching faces are not clashes
# Pairs accepted by decision on this project: frozenset({owner_a, owner_b}) -> the record (DEC / Q and Bob's words).
# Empty: nothing is accepted on this project yet.
ACCEPTED: dict[frozenset, str] = {}


def main() -> int:
    if rp.skip_no_project("interference"):
        return 0
    missing = rule_scope.model_missing()
    if missing:
        print(f"interference: PASS - not checked: {missing}; no bodies to compare")
        return 0
    try:
        from skidlib import layout
        from skidlib import vec as V
        from skidlib.model import elbow_chords, piece_prims
        from skidlib.reports import prim_bbox
        m = layout.build()
    except Exception as e:  # noqa: BLE001
        print(f"interference: ERROR - model did not build: {type(e).__name__}: {e}")
        return 3

    def rkey(p):
        return tuple(round(c, 2) for c in p)

    # ---- bodies: (owner, group, prims) --------------------------------------
    bodies = []
    kind_of = {}
    for it in m.items.values():
        if it.kind == "tie-in" or not it.prims:
            continue
        prims = [p for p in it.prims if not p.get("internal")]
        bodies.append((it.key, it.kind, prims))
        kind_of[it.key] = it.kind
    spool_of = {}
    for sp in m.spools:
        for pc in sp.pieces:
            bodies.append((pc.pid, "pipe", piece_prims(pc)))
            spool_of[pc.pid] = sp.sid
            kind_of[pc.pid] = "pipe"

    # ---- adjacency by design --------------------------------------------------
    at_point: dict[tuple, set] = {}
    jpts = [j.point for j in m.joints]

    def jkey(pt):
        # a clamp face sits half the gasket gap off its joint point: key it to the joint
        best = min(jpts, key=lambda q: V.dist(q, pt), default=None)
        return rkey(best) if best is not None and V.dist(best, pt) <= 0.1 else rkey(pt)

    for j in m.joints:
        at_point.setdefault(rkey(j.point), set()).update({j.a, j.b})
    for sp in m.spools:
        for pc in sp.pieces:
            if pc.kind == "branch_ferrule":
                at_point.setdefault(jkey(pc.geom["face"]), set()).add(sp.sid)
            if pc.kind == "tee":
                # an integral clamp outlet has its own face; else ferrule at 2.75
                face = pc.geom.get("branch_face") or V.add(pc.geom["center"], V.mul(pc.geom["bdir"], 2.75))
                at_point.setdefault(jkey(face), set()).add(sp.sid)
    for it in m.items.values():            # nozzle, valve, instrument, equipment clamp faces
        for (pt, _d) in it.faces.values():
            at_point.setdefault(jkey(pt), set()).add(it.key)
    adj: dict[str, set] = {}
    for owners in at_point.values():
        for a in owners:
            adj.setdefault(a, set()).update(owners)
    for it in m.items.values():
        for c in it.connects:
            adj.setdefault(it.key, set()).add(c)
            adj.setdefault(c, set()).add(it.key)
    # items touch the spools of their joints; tags vs keys are the same for tagged items

    def group(owner):
        return spool_of.get(owner, owner)

    def adjacent(a, b):
        ga, gb = group(a), group(b)
        if ga == gb:
            return True
        return gb in adj.get(ga, set()) or ga in adj.get(gb, set())

    # ---- primitive geometry ----------------------------------------------------
    def segs(p):
        if p["type"] == "cyl":
            # flat-ended cylinder approximated by a capsule shortened by its radius at
            # each end, so coaxial parts that meet end to end do not read as overlap
            a, b, r = p["p0"], p["p1"], p["r"]
            L = V.dist(a, b)
            if L < 1e-9:
                return [(a, b, r)]
            cut = min(r, 0.45 * L) / L
            return [(V.lerp(a, b, cut), V.lerp(a, b, 1.0 - cut), r)]
        if p["type"] == "sphere":
            return [(p["c"], p["c"], p["r"])]
        if p["type"] == "elbow":
            pts = elbow_chords(p, 4)
            return [(a, b, p["r"]) for a, b in zip(pts, pts[1:])]
        return []

    def coaxial_pen(p, q):
        # flat-ended cylinders on one axis (a valve body over a nozzle, say): the
        # capsule shape above bulges past the flat ends, so measure the axial overlap
        # exactly; None when the two are not coaxial
        a, b = p["p0"], p["p1"]
        L = V.dist(a, b)
        if L < 1e-9:
            return None
        u = V.unit(V.sub(b, a))
        tq = []
        for c in (q["p0"], q["p1"]):
            rel = V.sub(c, a)
            t = V.dot(rel, u)
            if V.dist(rel, V.mul(u, t)) > 1e-3:
                return None
            tq.append(t)
        return min(L, max(tq)) - max(0.0, min(tq))

    def pen(p, q):
        if p["type"] == "cyl" and q["type"] == "cyl":
            c = coaxial_pen(p, q)
            if c is not None:
                return c
        if p["type"] == "box" and q["type"] == "box":
            return V.aabb_overlap(p["min"], p["max"], q["min"], q["max"])
        if p["type"] == "box" or q["type"] == "box":
            bx, other = (p, q) if p["type"] == "box" else (q, p)
            return max(r - V.seg_aabb_dist(a, b, bx["min"], bx["max"]) for a, b, r in segs(other))
        best = -1e9
        for a1, b1, r1 in segs(p):
            for a2, b2, r2 in segs(q):
                best = max(best, r1 + r2 - V.seg_seg_dist(a1, b1, a2, b2))
        return best

    boxes = []
    for owner, kind, prims in bodies:
        pb = [(p, prim_bbox(p)) for p in prims]
        if not pb:
            continue
        lo = tuple(min(b[0][k] for _, b in pb) for k in range(3))
        hi = tuple(max(b[1][k] for _, b in pb) for k in range(3))
        boxes.append((owner, kind, pb, lo, hi))

    hits, accepted, pairs = [], [], 0
    for i in range(len(boxes)):
        oa, ka, pa, la, ha = boxes[i]
        for j in range(i + 1, len(boxes)):
            ob, kb, pb, lb, hb = boxes[j]
            if any(la[k] > hb[k] + TOL or lb[k] > ha[k] + TOL for k in range(3)):
                continue
            if ka in ("frame", "support", "plate") and kb in ("frame", "support", "plate"):
                continue
            if adjacent(oa, ob):
                continue
            pairs += 1
            worst = -1e9
            for p, bp in pa:
                for q, bq in pb:
                    if any(bp[0][k] > bq[1][k] + TOL or bq[0][k] > bp[1][k] + TOL for k in range(3)):
                        continue
                    worst = max(worst, pen(p, q))
            if worst > TOL:
                key = frozenset({oa, ob})
                if key in ACCEPTED:
                    accepted.append((oa, ob, worst, ACCEPTED[key]))
                else:
                    hits.append((worst, oa, ka, ob, kb))
    # clamp to clamp (added 2026-10-07: two clamps overlapped and no check saw it, because clamps are not bodies
    # above). Each clamp is its ring and lobes in its own frame (reports.clamp_gap); a pair overlapping deeper than
    # TOL is a clash; pairs under 0.5 in are printed for information.
    near = []
    try:
        from skidlib.reports import clamp_pairs
        for g, ja, jb in clamp_pairs(m, report_under=0.5):
            if g < -TOL:
                hits.append((-g, ja.jid, "clamp", jb.jid, "clamp"))
            else:
                near.append((g, ja, jb))
        pairs += len(near)
    except Exception as e:  # noqa: BLE001
        print(f"interference: ERROR - clamp-to-clamp check did not run: {type(e).__name__}: {e}")
        return 3
    hits.sort(reverse=True)
    if hits:
        print(f"interference: FAIL - {len(hits)} clash(es) deeper than {TOL} in among {len(boxes)} bodies "
              f"({pairs} candidate pairs, envelope level)")
    else:
        print(f"interference: PASS - no clash deeper than {TOL} in among {len(boxes)} bodies "
              f"({pairs} candidate pairs, envelope level; {len(accepted)} accepted by decision)")
    for w, oa, ka, ob, kb in hits:
        print(f"  CLASH {w:.3f} in  {oa} ({ka})  x  {ob} ({kb})")
    for oa, ob, w, why in accepted:
        print(f"  ACCEPTED {w:.3f} in  {oa} x {ob}: {why}")
    for g, ja, jb in near:
        print(f"  NEAR (clamp to clamp, information) {g:.3f} in  {ja.jid} ({ja.a} / {ja.b})  x  {jb.jid} ({jb.a} / {jb.b})")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
