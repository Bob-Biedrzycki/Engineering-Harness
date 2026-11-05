"""model_subfolders - move every locked model revision's files into its subfolders, once (Bob, chat, 2026-11-03).

Bob, chat, 2026-11-03: "Move them into sub folders once." A model revision folder keeps the model (GLB, zipped STEP
and their .drive pointers) at the top and the rest in Takeoffs/, Reports/ and Views/ (rp.model_subfolder). Revisions
locked before that are flat. This moves each file into its subfolder without renaming it or changing a byte, rewrites
the `file` column of each revisions.csv to match, appends one row per move to the project's path-crosswalk.csv, and
writes the moves as old_path,new_path CSV for `track.py save --moves-file` (git records them as renames).
model_file.py locks new revisions this way already. Drawing folders are not touched (flat: DWG, PDF, DXF).

    .\\harness\\tools\\venv\\Scripts\\python.exe harness\\scripts\\model_subfolders.py [--dry-run]

Exit 0 = moved (or nothing to move, or dry run); 2 = refused (a target exists, a file is missing).
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
import stat
import sys
from pathlib import Path

sys.path.insert(0, str(next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists()) / "harness" / "lib"))
import repo_paths as rp  # noqa: E402

MOVES = rp.PROJECT / "_work" / "filing" / "model-subfolders-moves.csv" if rp.HAS_PROJECT else rp.JOBS / "_work" / "model-subfolders-moves.csv"


def model_doc_folders() -> list[Path]:
    roots = [rp.JOB_ISSUED / "Models"] + sorted(p / "Models" for p in rp.JOBS.glob("Project-*/06_Issued_Revisions"))
    return sorted(m.parent for r in roots if r.is_dir() for m in r.rglob("revisions.csv") if "_work" not in m.parts)


def plan(folder: Path) -> tuple[list[str], list[dict], list[tuple[Path, Path]]]:
    with open(folder / "revisions.csv", newline="", encoding="utf-8-sig") as f:
        r = csv.DictReader(f)
        cols, rows = list(r.fieldnames or []), list(r)
    moves = []
    for row in rows:
        f = row["file"].strip()
        stem = rp.rev_folder(row["document_id"].strip(), row["revision"].strip())
        name = f.rsplit("/", 1)[-1]
        sub = rp.model_subfolder(name)
        want = f"{stem}/{sub}/{name}" if sub else f"{stem}/{name}"
        if f == want:
            continue
        src, dst = folder / f, folder / want
        if dst.exists():
            sys.exit(f"REFUSED: {rp.rel(dst)} exists already; nothing moved")
        if not src.is_file():
            sys.exit(f"REFUSED: {rp.rel(src)} is in revisions.csv but missing; nothing moved")
        moves.append((src, dst))
        row["file"] = want
    return cols, rows, moves


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true", help="list the moves; change nothing")
    a = ap.parse_args()
    plans = [(d, *plan(d)) for d in model_doc_folders()]   # every refusal before any move
    total = sum(len(m) for *_, m in plans)
    print(f"model_subfolders: {total} file(s) to move in {sum(1 for *_, m in plans if m)} of {len(plans)} model "
          f"document folder(s){'  [DRY RUN]' if a.dry_run else ''}")
    for d, _, _, m in plans:
        if m:
            subs = sorted({dst.parent.name for _, dst in m})
            print(f"  {rp.rel(d)}: {len(m)} file(s) into {', '.join(subs)}")
    if a.dry_run or not total:
        return 0
    today = dt.date.today().isoformat()
    log = []
    for d, cols, rows, moves in plans:
        for src, dst in moves:
            dst.parent.mkdir(parents=True, exist_ok=True)
            os.replace(src, dst)   # a move keeps the bytes, the name and the modified time
            os.chmod(dst, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
            log.append((rp.rel(src), rp.rel(dst)))
        if moves:
            with open(d / "revisions.csv", "w", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, fieldnames=cols)
                w.writeheader()
                w.writerows(rows)
    MOVES.parent.mkdir(parents=True, exist_ok=True)
    with open(MOVES, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["old_path", "new_path"])
        w.writerows(log)
    if rp.HAS_PROJECT:
        with open(rp.REGISTERS / "path-crosswalk.csv", "a", newline="", encoding="utf-8") as fh:
            csv.writer(fh).writerows((o, n, today) for o, n in log)
    print(f"model_subfolders: moved {len(log)} file(s); revisions.csv rewritten; crosswalk rows in "
          f"{rp.rel(rp.REGISTERS / 'path-crosswalk.csv') if rp.HAS_PROJECT else '(no project)'}; git moves in {rp.rel(MOVES)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
