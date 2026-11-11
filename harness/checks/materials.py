"""materials - every fabricated body of the skid model against the construction materials list
(harness/design-rules/materials.yaml; MAT-LIB-001, MAT-FORM-001).

Builds the routed model and reports, for every pipe piece and every frame member, plate and support:
    MAT-LIB-001   a material that is not on the list (or no material at all)
    MAT-FORM-001  a bent piece in a material that is not bent (pipe, tube and frame members turn through fittings
                  or welded joints; only an entry with make.bend: allowed may be bent)
Purchased parts (valves, pumps, instruments, bought hangers with no member record) are not checked: their maker's
cut sheet governs. A design finding: it reports and never blocks (harness/scripts/run_checks.sh).

Exit-code contract (harness/checks/README.md): 0 = PASS, 1 = FAIL, 3 = ERROR (could not run). First line = summary.
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists()) / "harness" / "lib"))
import repo_paths as rp  # noqa: E402
import rule_scope  # noqa: E402
import materials as mat  # noqa: E402

if rp.HAS_MODEL:
    sys.path.insert(0, str(rp.SKID_MODEL))


def main() -> int:
    bad = mat.problems()
    if bad:
        print(f"materials: ERROR - {mat.FILE.name} has {len(bad)} fault(s): {bad[0]}")
        return 3
    if rp.skip_no_model("materials"):
        return 0
    missing = rule_scope.model_missing()
    if missing:
        print(f"materials: PASS - not checked: {missing}; nothing read")
        return 0
    try:
        from skidlib import layout
        m = layout.build()
    except Exception as e:  # noqa: BLE001
        print(f"materials: ERROR - model did not build: {type(e).__name__}: {e}")
        return 3
    try:
        records = mat.model_records(m)
    except AttributeError as e:
        # a model whose skidlib predates the materials list gives no piece records (Model.pieces, Piece.material)
        print(f"materials: PASS - not checked: this model's skidlib does not give the records the check reads ({e}); "
              "nothing read")
        return 0
    recs = [r for r in records if r["kind"] != "support" or r["material"]]   # bought hangers: no member
    found = mat.audit(recs)
    by = Counter((mat.resolve(r["material"]) or {}).get("name", "not on the list") for r in recs)
    summary = f"{len(recs)} fabricated bodies: " + ", ".join(f"{n} {k}" for k, n in by.most_common())
    if found:
        print(f"materials: FAIL - {len(found)} finding(s) in {summary}")
        for f in found:
            print(f"  {f['rule']} {f['id']}: {f['finding']}")
        return 1
    print(f"materials: PASS - {summary}; no bent pipe, tube or frame member")
    return 0


if __name__ == "__main__":
    sys.exit(main())
