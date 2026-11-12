"""sanitary_routing - slope and dead legs of the routed skidlib model (SAN-SLOPE-001, SAN-DL-001).

The method is the model's own routing report, unchanged (Bob, 2026-11-11: "Use the previous methods of checking
slope and dead legs"): the check builds the model in memory, as sanitary.py does, and reads the rows that the
model's skidlib `reports.routing_rows(m)` measures. Nothing is measured here and no rule value is held here; the
limits are the ones the model reads from the design rules (harness/design-rules/sanitary.yaml SAN-SLOPE-001 min
slope, SAN-DL-001 max L/D).

  slope      every near-horizontal run of every spool, rise over run in in/ft against the minimum slope
             (SAN-SLOPE-001); an eccentric reducer on its invert. Vertical runs drain by gravity and have no row.
  dead leg   every tee branch from the run's bore wall to its first closure (valve seat, instrument seal line,
             equipment face), and the route's extra dead legs, as L/D against the limit (SAN-DL-001).

Each row's result is the model's, read as:
    ok                               PASS
    n/a ... (utility, plant water)   N/A     the model's scope note for that line
    BELOW, EXCEEDS, UNRESOLVED       FAIL    slope under the minimum, L/D over the limit, closure not found
    anything else                    KNOWN   a record the model source carries for that row (printed, not failed)

Accepted findings (CLAUDE.md: "Known findings are accepted with their record"): a FAIL row whose object and exact
measured value are listed in the project's accepted-findings.yaml `sanitary_routing` section is printed KNOWN with
its record; a changed value is a FAIL again; an entry that matches no FAIL row is printed STALE.

A model whose skidlib has no `reports.routing_rows` is not checked. A design finding: it reports and never blocks
(harness/scripts/run_checks.sh).

Exit-code contract (harness/checks/README.md): 0 = PASS (KNOWN and N/A rows are not failures), 1 = FAIL,
3 = ERROR (could not run). First printed line is the summary.

    python harness/checks/sanitary_routing.py [--report <dir>]   writes sanitary-routing.csv there
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists()) / "harness" / "lib"))
import repo_paths as rp  # noqa: E402
import rule_scope  # noqa: E402
import accepted_findings  # noqa: E402

if rp.HAS_MODEL:
    sys.path.insert(0, str(rp.SKID_MODEL))

NAME = "sanitary_routing"
PASS, FAIL, NA, KNOWN = "PASS", "FAIL", "N/A", "KNOWN"
FAIL_WORDS = ("BELOW", "EXCEEDS", "UNRESOLVED")     # the model's own words for a finding
FIELDS = ["status", "check", "object", "line_no", "value", "limit", "result", "length_in", "direction", "record"]


def status_of(result: str) -> str:
    """The model's result text as this check's status."""
    r = (result or "").strip()
    if r == "ok":
        return PASS
    if r.lower().startswith("n/a"):
        return NA
    if r in FAIL_WORDS:
        return FAIL
    return KNOWN


def classify(rows: list[dict], accepted: dict[tuple[str, str], str] | None = None) -> tuple[list[dict], list[tuple]]:
    """Every routing row with its status and record; and the accepted entries that matched no FAIL row (stale).

    accepted: (object, exact measured value) -> record, from the project's accepted-findings.yaml."""
    accepted = dict(accepted or {})
    used = set()
    out = []
    for r in rows:
        st = status_of(r.get("result", ""))
        rec = ""
        if st == FAIL:
            key = (str(r.get("object", "")), str(r.get("value", "")))
            if key in accepted:
                st, rec = KNOWN, accepted[key]
                used.add(key)
        elif st == KNOWN:
            rec = f"model record: {r.get('result', '')}"
        out.append({**r, "status": st, "record": rec})
    return out, [k for k in accepted if k not in used]


def kind(check: str) -> str:
    return "dead leg" if str(check).startswith("dead leg") else "slope"


def summary(rows: list[dict], what: str) -> str:
    n = Counter((kind(r.get("check", "")), r["status"]) for r in rows)
    fails = sum(1 for r in rows if r["status"] == FAIL)

    def part(k: str) -> str:
        tot = sum(v for (kk, _), v in n.items() if kk == k)
        bits = [f"{n[(k, s)]} {w}" for s, w in ((PASS, "pass"), (FAIL, "fail"), (KNOWN, "known"), (NA, "n/a"))
                if n[(k, s)]]
        return f"{tot} {k} rows ({', '.join(bits) or 'none'})"

    head = f"{NAME}: FAIL - {fails} finding(s)" if fails else f"{NAME}: PASS"
    return f"{head} - {part('slope')}, {part('dead leg')} on {what} (SAN-SLOPE-001, SAN-DL-001)"


def write_report(rows: list[dict], out: Path) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    p = out / "sanitary-routing.csv"
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    return p


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--report", type=Path, help="write sanitary-routing.csv into this folder")
    a = ap.parse_args(argv)
    if rp.skip_no_model(NAME):
        return 0
    missing = rule_scope.model_missing()
    if missing:
        print(f"{NAME}: PASS - not checked: {missing}; nothing measured")
        return 0
    accepted = accepted_findings.sanitary_routing()
    if accepted_findings.FAULT:
        print(f"{NAME}: ERROR - {accepted_findings.FAULT}")
        return 3
    try:
        from skidlib import layout
        m = layout.build()
    except Exception as e:  # noqa: BLE001
        print(f"{NAME}: ERROR - model did not build: {type(e).__name__}: {e}")
        return 3
    try:
        from skidlib import reports
        measure = reports.routing_rows
    except (ImportError, AttributeError) as e:
        print(f"{NAME}: PASS - not checked: this model's skidlib has no routing report to read "
              f"(reports.routing_rows: {e}); nothing measured")
        return 0
    try:
        raw = measure(m)
    except Exception as e:  # noqa: BLE001
        print(f"{NAME}: ERROR - the model's routing report did not run: {type(e).__name__}: {e}")
        return 3
    rows, stale = classify(raw, accepted)
    print(summary(rows, f"the {rp.SKID_MODEL_ID} source model"))
    order = {FAIL: 0, KNOWN: 1, PASS: 2, NA: 3}
    for r in sorted(rows, key=lambda r: (order[r["status"]], kind(r.get("check", "")), str(r.get("object", "")))):
        if r["status"] in (PASS, NA):
            continue
        print(f"  {r['status']:<5} {r.get('check', '')}: {r.get('object', '')} ({r.get('line_no', '')}) "
              f"{r.get('value', '')} | limit: {r.get('limit', '')} | {r.get('direction', '')}"
              + (f" | {r['record']}" if r["record"] else ""))
    for obj, val in stale:
        print(f"  STALE ACCEPT {obj} \"{val}\": no FAIL row has this object and measured value; remove the entry")
    na = Counter(r.get("result", "") for r in rows if r["status"] == NA)
    if na:
        print("  N/A rows, as the model scopes them: " + ", ".join(f"{v} {k}" for k, v in sorted(na.items())))
    if a.report:
        print(f"  wrote {write_report(rows, a.report)}")
    return 1 if any(r["status"] == FAIL for r in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
