"""tag_crosscheck - instrument and valve tags consistent across the project's P&ID lists.

Checks the lists in <project>/03_Working_Design/PID/02_Tag_Lists (equipment, valve, instrument, tie-in, line):
  1. every tag appears once: no tag twice in one list, none on two lists;
  2. every valve's line_no is a line on line-list.csv (or `unknown`);
  3. every instrument's line_no_or_equip is a line on line-list.csv or an equipment tag (or `unknown`);
  4. every line on line-list.csv has a service_class (PIPE-SVC-001); a blank or `unknown` class is listed as
     information (the class-dependent checks report those lines as not checked), not a failure.
The model side is pid_consistency.py (every list tag in the model and back). Tags read off the P&ID drawing itself
are not compared here: the project has no P&ID tag extraction yet, and the summary says so.

Exit-code contract (harness/checks/README.md): 0 = PASS, 1 = FAIL, 3 = ERROR (a list unreadable). First line = summary.
"""
from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists()) / "harness" / "lib"))
import repo_paths as rp  # noqa: E402

TAG_LISTS = ("equipment-list.csv", "valve-list.csv", "instrument-list.csv", "tie-in-list.csv")


def _rows(name: str, folder: Path) -> list[dict]:
    p = folder / name
    if not p.is_file():
        return []
    with open(p, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _known(v) -> str:
    s = (v or "").strip()
    return "" if not s or s.lower().startswith("unknown") else s


def evaluate(folder: Path | None = None) -> tuple[list[str], list[str], int]:
    """(failures, information lines, number of tags). folder: default the project's tag lists."""
    folder = folder or rp.DATA
    fails, info = [], []
    where: dict[str, list[str]] = defaultdict(list)
    lists = {n: _rows(n, folder) for n in TAG_LISTS}
    for name, rows in lists.items():
        for r in rows:
            t = _known(r.get("tag"))
            if t:
                where[t].append(name)
    for t, names in sorted(where.items()):
        if len(names) > 1:
            fails.append(f"tag {t} appears {len(names)} times ({', '.join(names)})")
    lines = {r["line_no"].strip(): r for r in _rows("line-list.csv", folder) if _known(r.get("line_no"))}
    equipment = {_known(r.get("tag")) for r in lists["equipment-list.csv"]} - {""}
    for r in lists["valve-list.csv"]:
        ln = _known(r.get("line_no"))
        if ln and ln not in lines:
            fails.append(f"valve {r.get('tag')}: line_no {ln} is not on line-list.csv")
    for r in lists["instrument-list.csv"]:
        ref = _known(r.get("line_no_or_equip"))
        if ref and ref not in lines and ref not in equipment:
            fails.append(f"instrument {r.get('tag')}: line_no_or_equip {ref} is neither a line nor an equipment tag")
    no_class = sorted(ln for ln, r in lines.items() if not _known(r.get("service_class")))
    if no_class:
        info.append(f"service_class unknown on {', '.join(no_class)} (PIPE-SVC-001; class-dependent checks: not checked)")
    return fails, info, len(where)


def main() -> int:
    if rp.skip_no_project("tag_crosscheck"):
        return 0
    try:
        fails, info, n = evaluate()
    except Exception as e:  # noqa: BLE001
        print(f"tag_crosscheck: ERROR - lists unreadable: {type(e).__name__}: {e}")
        return 3
    tail = "P&ID drawing tags not compared (no P&ID tag extraction yet); model side is pid_consistency.py"
    if fails:
        print(f"tag_crosscheck: FAIL - {len(fails)} issue(s) among {n} list tags; {tail}")
    else:
        print(f"tag_crosscheck: PASS - {n} list tags, each once, every valve and instrument reference resolves; {tail}")
    for f in fails:
        print(f"  FAIL {f}")
    for i in info:
        print(f"  INFO {i}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
