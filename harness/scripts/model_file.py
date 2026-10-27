"""model_file.py - tier 2 of the three-tier pipeline: file the work build as the next model revision.

The three-tier model pipeline (CPME practice). Skill: .claude/skills/model-file.
Run it when Bob is to look at the model: a design shown or handed off is filed first, never pointed at in
<project>/_work/ (TR-08; Bob, 2026-09-24: "YOU ARE NO LONGER TO OVERWRITE DESIGNS. THEY MUST BE LABELED AS REVISIONS.").

What it does, in order (it stops at the first refusal and writes nothing):
    1. reads <project>/03_Working_Design/Exports/build/<MODEL-ID>/iterate-summary.json (written by model_iterate.py); refuses if the
       build is incomplete, a check failed (unless --failing-ok "<reason>", recorded in the description), or
       the STEP, GLB or any takeoff is older than the newest source file (model source, <project>/03_Working_Design/PID/02_Tag_Lists lists,
       component models, design rules), or the GLB is older than the STEP;
    2. takes the next letter after the last row of <project>/06_Issued_Revisions/Models/<MODEL-ID>/revisions.csv (sequential, nobody
       assigns it); --rev X makes it refuse unless X is that letter; refuses if any target file exists;
    3. copies the build into <project>/06_Issued_Revisions/Models/<MODEL-ID>/ with the revision in every name, the STEP zipped as
       <MODEL-ID>-rev<X>.step.zip holding <MODEL-ID>-rev<X>.step, every file read-only;
    4. appends one revisions.csv row per file (sha256, bytes, note <= 32 chars, description + checks);
    5. runs drive_store.py pointers. No push: that happens once a day at close-out.

    .\\harness\\tools\\venv\\Scripts\\python.exe harness\\scripts\\model_file.py --note "<= 32 chars" --description-file <utf-8 file> [--rev X] [--dry-run]

--description "<text>" works too, but PowerShell 5.1 mangles embedded double quotes in native arguments, so
long descriptions with quotes go through --description-file. --models-root <folder> files into another
folder (a scratch copy, for testing this script; pointers are skipped there).
Exit 0 = filed (or dry run shown); 1 = filed but drive_store pointers reported a problem; 2 = refused.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists()) / "harness" / "lib"))
import repo_paths as rp  # noqa: E402
if __name__ == "__main__":
    rp.require_project("model_file.py")   # no project yet: exit 2, nothing to file
import model_build as mb  # noqa: E402

PY = rp.TOOLS / "venv" / "Scripts" / "python.exe"
KEYS = ["document_id", "revision", "file", "file_date", "sha256", "bytes", "source", "notes", "description"]


def refuse(msg: str) -> None:
    print(f"REFUSED: {msg}", file=sys.stderr)
    sys.exit(2)


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for block in iter(lambda: f.read(1 << 22), b""):
            h.update(block)
    return h.hexdigest()


def when(t: float) -> str:
    return f"{dt.datetime.fromtimestamp(t):%Y-%m-%d %H:%M:%S}"


def check_build(failing_ok: str | None) -> dict:
    if not mb.SUMMARY.is_file():
        refuse(f"no {rp.rel(mb.SUMMARY)}: run harness/scripts/model_iterate.py first")
    s = json.loads(mb.SUMMARY.read_text(encoding="utf-8"))
    if not s.get("complete"):
        refuse(f"the last model_iterate run did not complete every step ({', '.join(s['steps'])}); rerun it")
    if s["failed"] and not failing_ok:
        refuse(f"the last model_iterate run failed {', '.join(s['failed'])}; fix it, or pass --failing-ok \"<reason>\" "
               "to file it anyway with the reason recorded")
    missing = [rp.rel(p) for p in mb.build_files() if not p.is_file()]
    if missing:
        refuse("work build is missing: " + ", ".join(missing))
    mt, newest = mb.newest_source()
    stale = [f"{p.name} ({when(p.stat().st_mtime)})" for p in mb.build_files() if p.stat().st_mtime < mt]
    if stale:
        refuse(f"work build is older than its source {rp.rel(newest)} ({when(mt)}): {', '.join(stale)}; rerun model_iterate.py")
    if mb.GLB.stat().st_mtime < mb.STEP.stat().st_mtime:
        refuse(f"{mb.GLB.name} is older than {mb.STEP.name}; rerun model_iterate.py")
    if mb.SUMMARY.stat().st_mtime < max(p.stat().st_mtime for p in mb.build_files()):
        refuse("a build file changed after the last model_iterate run finished; rerun model_iterate.py")
    return s


def checks_text(s: dict) -> str:
    order = ["interference", "envelope", "pipe_supports", "list_delta", "lists", "step", "glb"]
    parts = [s["steps"][k]["summary"] for k in order if k in s["steps"]]
    return (f"Checks (harness/scripts/model_iterate.py, {s['finished']}): " + "; ".join(parts)
            + ". pid_consistency, frame calc and sanitary run at close-out (harness/scripts/closeout.py).")


def same_as_previous(root: Path, prev: str | None) -> list[str]:
    """Takeoffs whose content equals the previous revision's after replacing the revision strings."""
    if not prev:
        return []
    same = []
    for n in mb.TAKEOFFS:
        old = root / mb.filed_name(n, prev)
        if old.is_file() and old.read_bytes() == (mb.BUILD / n).read_bytes():
            same.append(n)
    return same


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--note", help="revision note, at most 32 characters (revision-block practice, TR-07)")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--description", help="what changed and why, with Bob's words and the records cited")
    g.add_argument("--description-file", type=Path, help="UTF-8 text file holding the description")
    ap.add_argument("--rev", help="expected letter: refuse unless it is the next one")
    ap.add_argument("--failing-ok", metavar="REASON", help="file a build whose checks failed; the reason is recorded")
    ap.add_argument("--dry-run", action="store_true", help="show the file set and the rows; write nothing")
    ap.add_argument("--models-root", type=Path, help="file into this folder instead (testing; pointers skipped)")
    a = ap.parse_args()

    root = (a.models_root or mb.FILED).resolve()
    real = root == mb.FILED.resolve()
    note = a.note or ("(dry run)" if a.dry_run else None)
    if not note:
        refuse("--note is required")
    if len(note) > 32:
        refuse(f"--note is {len(note)} characters; at most 32 (detail goes in the description)")
    desc = a.description_file.read_text(encoding="utf-8-sig").strip() if a.description_file else (a.description or "").strip()
    if not desc and not a.dry_run:
        refuse("--description or --description-file is required: what changed from the previous revision and why")

    s = check_build(a.failing_ok)
    prev = mb.last_revision(root)
    letter = mb.next_letter(prev)
    if a.rev and a.rev != letter:
        refuse(f"--rev {a.rev} is not the next letter: the last filed revision is {prev or 'none'}, so this one is "
               f"{letter} (letters are sequential; a filed revision is never refiled, TR-08)")
    if any(r["revision"] == letter for r in mb.filed_rows(root)):
        refuse(f"Rev {letter} already has rows in {root / 'revisions.csv'} (TR-08)")
    plan = [(p, root / mb.filed_name(p.name, letter)) for p in mb.build_files()]
    exists = [rp.rel(d) if real else str(d) for _, d in plan if d.exists()]
    if exists:
        refuse(f"Rev {letter} files already exist, a filed design is never overwritten (TR-08): {', '.join(exists)}")

    full_desc = desc + (" " if desc else "") + checks_text(s)
    if a.failing_ok:
        full_desc += f" FILED WITH FAILING CHECKS ({', '.join(s['failed'])}): {a.failing_ok}"
    same = same_as_previous(root, prev)
    print(f"model_file: {mb.MODEL_ID} Rev {letter} (last filed {prev or 'none'}) -> {rp.rel(root) if real else root}"
          f"{'  [DRY RUN, nothing written]' if a.dry_run else ''}")
    for src, dst in plan:
        extra = " (zipped)" if src == mb.STEP else ""
        print(f"  {src.stat().st_size:>12,} B  {src.name:<34} -> {dst.name}{extra}")
    print(f"  revisions.csv: {len(plan)} row(s), note \"{note}\"")
    print(f"  description: {full_desc[:400]}{' ...' if len(full_desc) > 400 else ''}")
    if same:
        print(f"  info: {len(same)} of {len(mb.TAKEOFFS)} takeoffs equal Rev {prev}'s byte for byte: {', '.join(same)}")
    if a.dry_run:
        print(f"model_file: dry run; a real run files Rev {letter} and runs drive_store.py pointers (no push)")
        return 0

    root.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    rows = []
    for src, dst in plan:
        if src == mb.STEP:
            part = dst.with_name(dst.name + ".partial")
            inner = dst.name[:-len(".zip")]
            zi = zipfile.ZipInfo(inner, date_time=dt.datetime.fromtimestamp(src.stat().st_mtime).timetuple()[:6])
            zi.compress_type = zipfile.ZIP_DEFLATED
            with zipfile.ZipFile(part, "w", zipfile.ZIP_DEFLATED) as z, open(src, "rb") as fin, z.open(zi, "w", force_zip64=True) as fout:
                shutil.copyfileobj(fin, fout, 1 << 22)
            part.rename(dst)
            source = f"{rp.rel(src)} (zipped)".replace("/", "\\")
        else:
            shutil.copy2(src, dst)
            source = rp.rel(src).replace("/", "\\")
        rows.append({"document_id": mb.MODEL_ID, "revision": letter, "file": dst.name, "file_date": stamp,
                     "sha256": sha256(dst), "bytes": dst.stat().st_size, "source": source, "notes": note,
                     "description": full_desc})
        os.chmod(dst, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
        print(f"  filed {dst.name}")
    manifest = root / "revisions.csv"
    new = not manifest.exists()
    with open(manifest, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=KEYS)
        if new:
            w.writeheader()
        w.writerows(rows)
    print(f"model_file: filed {mb.MODEL_ID} Rev {letter}, {len(rows)} files, rows appended to {manifest.name}")
    if not real:
        print("model_file: --models-root given; drive_store.py pointers skipped")
        return 0
    r = subprocess.run([str(PY), str(rp.SCRIPTS / "drive_store.py"), "pointers"], cwd=rp.REPO,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    print("  " + "\n  ".join((r.stdout + r.stderr).strip().splitlines()))
    print("model_file: pointers written; Drive push waits for close-out. Give Bob the filed paths, never <project>/_work/.")
    return 0 if r.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
