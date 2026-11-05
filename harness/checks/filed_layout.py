"""filed_layout - every filed drawing and model revision sits in its own folder.

Bob, chat, 2026-10-30: "Everything like for them should be in a folder for each rev." A document folder under
06_Issued_Revisions/Drawings/ or 06_Issued_Revisions/Models/ (job level and every project; any folder there holding a
revisions.csv) holds only revisions.csv and one folder per revision, <DOC-ID>-rev<X>/ (rp.rev_folder), with every file
of that revision inside it. revfile.py and model_file.py file that way; this check catches anything filed another way.

Checks, per document folder:
  * no file other than revisions.csv (and .gitkeep) lies loose in the document folder;
  * every revisions.csv row's `file` is "<document_id>-rev<revision>/<name>" (a drawing), or for a model
    "<document_id>-rev<revision>/<subfolder>/<name>" with the subfolder rp.model_subfolder names (Takeoffs, Reports,
    Views, Presentations/P<nn>; the GLB and zipped STEP at the top; Bob, chat, 2026-11-03), and that file or its
    .drive pointer exists;
  * every revision folder is named for a document and revision in revisions.csv.
Portals are filed their own way (build_portal.py, one folder per revision already) and are not checked here.

    .\\harness\\tools\\venv\\Scripts\\python.exe harness\\checks\\filed_layout.py [--fix]

--fix moves loose revision files (and their .drive pointers) into their revision folders without renaming them,
rewrites the `file` column of revisions.csv to match, and appends one row per moved file to the project's
path-crosswalk.csv. The bytes, names and sha256 of the filed files do not change (TR-08). Run
harness/scripts/drive_store.py pointers after it.
Exit 0 PASS, 1 FAIL. First line is the summary.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
import re
import stat
import sys
from pathlib import Path

sys.path.insert(0, str(next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists()) / "harness" / "lib"))
import repo_paths as rp  # noqa: E402

SUFFIX = ".drive"
KEEP = {"revisions.csv", ".gitkeep"}
REV = re.compile(r"^(?P<stem>.+?-rev(?P<rev>[A-Z]{1,2}))(?=[-.])")


def show(p: Path) -> str:
    """Repo-relative path, or the full path for a folder outside the repo (a test's scratch folder)."""
    try:
        return rp.rel(p)
    except ValueError:
        return Path(p).as_posix()


def doc_folders() -> list[Path]:
    """Every folder holding a revisions.csv under any 06_Issued_Revisions/Drawings or /Models of the job."""
    roots = [rp.JOB_ISSUED] + sorted(rp.JOBS.glob("Project-*/06_Issued_Revisions"))
    out = []
    for issued in roots:
        for kind in ("Drawings", "Models"):
            base = issued / kind
            if base.is_dir():
                out += sorted(p.parent for p in base.rglob("revisions.csv") if "_work" not in p.parts)
    return out


def read_rows(man: Path) -> tuple[list[str], list[dict]]:
    with open(man, newline="", encoding="utf-8-sig") as f:
        r = csv.DictReader(f)
        return list(r.fieldnames or []), list(r)


def stems(rows: list[dict]) -> set[str]:
    return {rp.rev_folder(r["document_id"].strip(), r["revision"].strip()) for r in rows}


def check(folder: Path) -> list[str]:
    problems = []
    _, rows = read_rows(folder / "revisions.csv")
    known = stems(rows)
    for p in sorted(folder.iterdir()):
        if p.is_file() and p.name not in KEEP:
            problems.append(f"loose file, not in a revision folder: {show(p)}")
        elif p.is_dir() and p.name not in known and not (p / "revisions.csv").is_file():
            problems.append(f"folder is not a revision in revisions.csv: {show(p)}")
    for r in rows:
        stem = rp.rev_folder(r["document_id"].strip(), r["revision"].strip())
        f = r["file"].strip()
        inner = f[len(stem) + 1:]
        sub, _, name = inner.rpartition("/")
        # a model revision keeps its files in subfolders (rp.model_subfolder, Bob, chat, 2026-11-03); a drawing is flat
        want = rp.model_subfolder(name) if "Models" in folder.parts else ""
        if not f.startswith(stem + "/"):
            problems.append(f"{show(folder / 'revisions.csv')}: file {f!r} is not in {stem}/")
        elif sub != want:
            problems.append(f"{show(folder / 'revisions.csv')}: file {f!r} belongs in {stem}/{want + '/' if want else ''}")
        elif not ((folder / f).is_file() or (folder / (f + SUFFIX)).is_file()):
            problems.append(f"{show(folder / 'revisions.csv')}: {f} missing (no file and no .drive pointer)")
    return problems


def fix(folder: Path, moved: list[tuple[str, str]]) -> None:
    man = folder / "revisions.csv"
    cols, rows = read_rows(man)
    known = stems(rows)
    for p in sorted(folder.iterdir()):
        if not p.is_file() or p.name in KEEP:
            continue
        m = REV.match(p.name)
        if not m or m.group("stem") not in known:
            print(f"  left as is (no revision in revisions.csv matches): {show(p)}")
            continue
        sub = rp.model_subfolder(p.name) if "Models" in folder.parts else ""
        dest = folder / m.group("stem") / sub / p.name
        if dest.exists():
            print(f"  left as is ({show(dest)} exists already): {show(p)}")
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        if p.name.endswith(SUFFIX):
            os.remove(p)   # drive_store.py pointers writes the pointer again at the new path (same file, same sha256)
            continue
        os.replace(p, dest)   # a move keeps the bytes, the name and the modified time
        os.chmod(dest, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
        moved.append((show(p), show(dest)))
    for r in rows:
        f = r["file"].strip()
        stem = rp.rev_folder(r["document_id"].strip(), r["revision"].strip())
        sub = rp.model_subfolder(f) if "Models" in folder.parts else ""
        if "/" not in f and (folder / stem / sub / f).exists():
            r["file"] = f"{stem}/{sub}/{f}" if sub else f"{stem}/{f}"
    with open(man, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--fix", action="store_true", help="move loose revision files into their revision folders")
    a = ap.parse_args()
    folders = doc_folders()
    if a.fix:
        moved: list[tuple[str, str]] = []
        for d in folders:
            fix(d, moved)
        if moved and rp.HAS_PROJECT:
            xw = rp.REGISTERS / "path-crosswalk.csv"
            today = dt.date.today().isoformat()
            with open(xw, "a", newline="", encoding="utf-8") as fh:
                csv.writer(fh).writerows((o.replace("\\", "/"), n.replace("\\", "/"), today) for o, n in moved)
            print(f"filed_layout: moved {len(moved)} file(s) into revision folders; crosswalk rows in {show(xw)}; "
                  "now run harness/scripts/drive_store.py pointers")
        else:
            print("filed_layout: nothing to move")
    problems = [p for d in folders for p in check(d)]
    print(f"filed_layout: {'FAIL' if problems else 'PASS'} - {len(folders)} document folder(s), {len(problems)} problem(s)"
          + ("" if rp.HAS_PROJECT else " (job level checked; no project yet)"))
    for p in problems[:200]:
        print(f"  {p}")
    if len(problems) > 200:
        print(f"  ... {len(problems) - 200} more")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
