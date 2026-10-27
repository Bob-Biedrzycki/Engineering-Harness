"""pid_consistency - P&ID-to-model tag and line coverage for the project's skid model.

Verifies, against the routed model built by <project>/03_Working_Design/CAD/01_Master_Assembly/<MODEL-ID>/skidlib (rp.SKID_MODEL; the same
model the STEP is generated from):
  1. every tag in <project>/03_Working_Design/PID/02_Tag_Lists equipment / valve / instrument / tie-in lists
     is in the model, except the off-skid tags and lines in skidlib params.OFF_SKID (the model names them);
  2. every tagged model component carries a tag that is on those lists
     (frame FM-/PS-/PL- members, reservations and loose line fittings are the only
     untagged kinds; a loose fitting must carry a line on line-list.csv);
  3. every line in line-list.csv is routed (has a spool or a component);
  4. spool ids are <LINE>-SP<nn> with LINE the spool's own line, any line_no on line-list.csv (e.g. CS-201-SP03),
     weld ids are <SPOOL>-W<nn> and unique (CLAUDE.md naming; harness/lib/rule_scope.spool_id_ok).
With no model source yet (rule_scope.model_missing) it prints PASS - not checked and exits 0.

Exit-code contract (harness/checks/README.md): 0 = PASS, 1 = FAIL, 3 = ERROR (could not run). First printed line
is the summary.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists()) / "harness" / "lib"))
import repo_paths as rp  # noqa: E402
import rule_scope  # noqa: E402

REPO = rp.REPO
if rp.HAS_PROJECT:
    sys.path.insert(0, str(rp.SKID_MODEL))

# Untagged kinds and the id pattern each must carry (CLAUDE.md naming: FM-nnn, PS-nnn, PL-nnn). Leveling feet have no
# naming rule on this project: a "foot"
# item is checked as a tagged component until Bob sets one.
UNTAGGED_KINDS = {"frame": r"^FM-\d{3}$", "support": r"^PS-\d{3}$", "plate": r"^PL-\d{3}$", "reservation": r"^$",
                  # loose clamped commodity fittings (e.g. a TC end cap) are untagged like the spool fittings,
                  # but must carry a line on line-list.csv
                  "fitting": r"^$"}


def main() -> int:
    if rp.skip_no_project("pid_consistency"):
        return 0
    missing = rule_scope.model_missing()
    if missing:
        print(f"pid_consistency: PASS - not checked: {missing}; the lists are not compared with a model")
        return 0
    try:
        from skidlib import inputs, layout
        from skidlib.params import OFF_SKID
        m = layout.build()
    except Exception as e:  # noqa: BLE001
        print(f"pid_consistency: ERROR - model did not build: {type(e).__name__}: {e}")
        return 3
    expected = {}
    for name, rows in inputs.tag_lists().items():
        for r in rows:
            t = (r.get("tag") or "").strip()
            if t and t.lower() != "unknown":
                expected[t] = name
    fails, info = [], []
    model_tags: dict[str, list[str]] = {}
    lines = inputs.line_list()
    for it in m.items.values():
        if it.kind in UNTAGGED_KINDS:
            if not re.match(UNTAGGED_KINDS[it.kind], it.tag or ""):
                fails.append(f"{it.key}: {it.kind} carries tag '{it.tag}' (expected pattern {UNTAGGED_KINDS[it.kind]})")
            if it.kind == "fitting" and it.line not in lines:
                fails.append(f"{it.key}: fitting carries line '{it.line}', not on line-list.csv")
            continue
        if not it.tag:
            fails.append(f"{it.key}: untagged component ({it.kind})")
            continue
        model_tags.setdefault(it.tag, []).append(it.key)
    for t, src in sorted(expected.items()):
        if t in OFF_SKID:
            info.append(f"{t}: not modeled - {OFF_SKID[t]}")
        elif t not in model_tags:
            fails.append(f"{t} ({src}) is not in the model")
    for t in sorted(model_tags):
        if t not in expected:
            fails.append(f"model tag {t} ({', '.join(model_tags[t])}) is not on any <project>/03_Working_Design/PID/02_Tag_Lists list")
    for ln in lines:
        if ln in OFF_SKID:
            info.append(f"{ln}: not routed - {OFF_SKID[ln]}")
        elif ln not in m.line_objects:
            fails.append(f"{ln} (line-list.csv) is not routed")
    for ln in m.line_objects:
        if ln not in lines:
            fails.append(f"model line {ln} is not in line-list.csv")
    seen = set()
    for sp in m.spools:
        if not rule_scope.spool_id_ok(sp.sid, sp.line):   # a line off line-list.csv is its own FAIL above
            fails.append(f"spool id {sp.sid} does not follow <LINE>-SP<nn> for {sp.line}")
        for w in sp.welds:
            if not w.wid.startswith(sp.sid + "-W") or w.wid in seen:
                fails.append(f"weld id {w.wid} malformed or duplicated")
            seen.add(w.wid)
    n_tags = len([t for t in expected if t not in OFF_SKID])
    n_lines = len([ln for ln in lines if ln not in OFF_SKID])
    if fails:
        print(f"pid_consistency: FAIL - {len(fails)} issue(s); {n_tags} list tags, {len(model_tags)} model tags, "
              f"{len(lines)} lines")
    else:
        print(f"pid_consistency: PASS - {n_tags} list tags all in the model, {len(model_tags)} model tags all on the "
              f"lists, {n_lines}/{n_lines} on-skid lines routed,{len(m.spools)} spools, {len(seen)} welds")
    for f in fails:
        print(f"  FAIL {f}")
    for i in info:
        print(f"  INFO {i}")
    if m.problems:
        print(f"  INFO model build reported {len(m.problems)} routing problem(s) (see {rp.rel(rp.SKID_MODEL / 'export_lists.py')})")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
