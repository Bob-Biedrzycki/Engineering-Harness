"""model_build - what a skid-model build is made of, shared by the three tiers (CPME practice).

    harness/scripts/model_iterate.py   tier 1, every build: a new numbered folder in <project>/03_Working_Design/CAD/Builds/
    harness/scripts/model_file.py      tier 2, when Bob looks at it: files a full build as the next revision
    harness/scripts/closeout.py        tier 3, once a day on Bob's word: Drive push, checks, portal, commit body

One place names the build's files, the filed name of each, and the source files a build is derived from,
so model_file can refuse a build that is older than its source (TR-03, TR-08).

One build series (Bob, chat, 2026-11-12): every build, fast or full, is a new folder
<project>/03_Working_Design/CAD/Builds/rev<X>/rev<X>-fast-<nnn>/ or rev<X>-full-<nnn>/, <X> the last filed revision
it starts from, one counter per letter shared by both kinds, never overwritten, one row each in Builds/build-log.md.
BUILD is the full build in hand: the latest one (repo_paths.current_build), or the one use_build names.

The model is the project's skid model unless a job-level model is chosen (--model-id / --config, harness/lib/
repo_paths.py). A job-level model files each configuration as its own document, DOC_ID = <MODEL-ID>-<CFG>, with its
own letters from Rev A: every filed name is <DOC_ID>-rev<X>..., and its revisions.csv rows are the rows whose
document_id is DOC_ID (B and X share the model's filed folder). A job-level model also files four review views
(VIEWS, harness/cad-lib/render_png.py from the build STEP).
"""
from __future__ import annotations

import csv
import datetime as dt
import os
import shutil
import stat
import sys
import zipfile
from pathlib import Path

import repo_paths as rp
import components

LOG_NAME = "build-log.md"            # the running list of builds, in the builds folder
EARLIER_LOG_NAME = "fast-log.md"     # its name before 2026-11-12
LOG_HEAD = "| Build | Time | Request | Result / note | Checks |\n|---|---|---|---|---|\n"

# Takeoffs and records the build writes, in the order revisions.csv lists them (as Rev A, 2026-10-02).
# The list delta is filed with each revision.
TAKEOFFS = ["bom-model.csv", "clamp-schedule.csv", "cut-list-frame.csv", "cut-list-piping.csv",
            "fittings-by-spool.csv", "piping-mass.csv", "routing-report.csv", "spool-list.csv", "weld-map.csv",
            "pipe-support-calc.csv", "pipe-support-calc.md", "layout-note.md", "manifest.json",
            "list-delta.csv", "list-delta.md"]
# Review views a job-level model files with each revision (view name for render_png.py --view, file name).
VIEWS = [("iso", "view-iso.png"), ("plan", "view-plan.png"), ("front", "view-front.png"), ("end", "view-side.png")]
JOB_LEVEL = rp.MODEL_LEVEL == "job"
if rp.HAS_MODEL:   # no model yet: the functions below that read a revisions.csv still work (last_revision)
    MODEL_ID = rp.SKID_MODEL_ID
    DOC_ID = rp.MODEL_DOC_ID     # the project's MODEL-ID, or <MODEL-ID>-<CFG> for a job-level model
    BUILD = rp.SKID_BUILD
    FILED = rp.SKID_FILED
    SUMMARY = BUILD / "iterate-summary.json"   # written by model_iterate.py, read by model_file.py
    STEP = BUILD / f"{DOC_ID}.step"
    GLB = BUILD / f"{DOC_ID}.glb"


def use_build(folder: Path | None = None) -> Path:
    """Point BUILD, SUMMARY, STEP and GLB at `folder`, or at the latest full build when none is given (a script that
    has just run model_iterate.py calls this, because these names were set when it started)."""
    global BUILD, SUMMARY, STEP, GLB
    BUILD = Path(folder) if folder is not None else rp.current_build(rp.BUILDS)
    SUMMARY = BUILD / "iterate-summary.json"
    STEP = BUILD / f"{DOC_ID}.step"
    GLB = BUILD / f"{DOC_ID}.glb"
    return BUILD


def series_stem(last: str | None) -> str:
    """The folder and name prefix of the builds that start from filed revision `last` (`first` before Rev A)."""
    return f"rev{last}" if last else "first"


def new_build_dir(kind: str, builds: Path, last: str | None) -> Path:
    """The next build folder, not yet made: `builds`/<stem>/<stem>-<kind>-<nnn>, <nnn> one more than the highest
    number of either kind for that letter (001 again after each filing). kind is "fast" or "full"."""
    stem = series_stem(last)
    nums = [k[2] for k in (rp.build_key(p.name) for p in (builds / stem).glob(f"{stem}-*") if p.is_dir()) if k]
    return builds / stem / f"{stem}-{kind}-{max(nums, default=0) + 1:03d}"


def find_build(name: str, builds: Path) -> Path | None:
    """The build folder called `name` (rev<X>-full-<nnn>) under `builds`, or None."""
    hits = [p for p in builds.glob(f"*/{name}") if p.is_dir() and rp.build_key(p.name)]
    return hits[0] if hits else None


def log_row(builds: Path, build: str, request: str, change: str, checks: str) -> None:
    """One row in `builds`/build-log.md under today's heading (Bob, 2026-10-10: "start to keep a running list in the
    fast folder for each revision."; every build since 2026-11-12)."""
    log = builds / LOG_NAME
    cell = lambda s: (s or "").replace("|", "/").replace("\r", " ").replace("\n", " ").strip()  # noqa: E731
    text = log.read_text(encoding="utf-8") if log.exists() else "# Builds: running list\n"
    day = dt.date.today().isoformat()
    add = "" if f"## {day}" in text else f"\n## {day}\n\n{LOG_HEAD}"
    add += f"| {build} | {dt.datetime.now():%H:%M} | {cell(request)} | {cell(change)} | {cell(checks)} |\n"
    log.parent.mkdir(parents=True, exist_ok=True)
    if not log.exists():
        log.write_text(text, encoding="utf-8", newline="\n")
    with open(log, "a", encoding="utf-8", newline="\n") as f:
        f.write(add if text.endswith("\n") else "\n" + add)


def adopt_earlier_layout(builds_root: Path, earlier_fast_root: Path, builds: Path, earlier_build: Path,
                         last: str | None) -> list[str]:
    """Once per checkout, bring the layout used before 2026-11-12 into the one series, and say what moved:
    the fast builds folder is renamed to `builds_root`, its fast-log.md to build-log.md, and the one full build that
    used to be overwritten (`earlier_build`, when it holds an iterate-summary.json) becomes the next numbered full
    build. Nothing is copied or deleted; a move that cannot be made is reported and left."""
    done = []
    if earlier_fast_root.is_dir() and not builds_root.exists():
        earlier_fast_root.rename(builds_root)
        done.append(f"{earlier_fast_root.name}/ is now {builds_root.name}/")
    elif earlier_fast_root.is_dir():
        done.append(f"NOT MOVED: both {earlier_fast_root} and {builds_root} exist")
    old_log, log = builds / EARLIER_LOG_NAME, builds / LOG_NAME
    if old_log.is_file() and not log.exists():
        old_log.rename(log)
        done.append(f"{EARLIER_LOG_NAME} is now {LOG_NAME}")
    if (earlier_build / "iterate-summary.json").is_file():
        dst = new_build_dir("full", builds, last)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(earlier_build), str(dst))
        log_row(builds, dst.name, "(none: the full build as it stood before every build was numbered)",
                f"moved from {earlier_build.parent.name}/{earlier_build.name}, nothing rebuilt", "as in its iterate-summary.json")
        done.append(f"the earlier full build is now {dst.name}")
    return done


def lock_build(folder: Path) -> None:
    """Make every file of a finished build read-only, so nothing run later (an export script started by hand writes
    into the latest full build) can change a build that is kept: it fails instead. Folders stay writable."""
    for p in folder.rglob("*"):
        if p.is_file():
            os.chmod(p, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)


def zip_earlier_steps(builds: Path, keep: Path) -> list[str]:
    """Zip the STEP of every full build under `builds` except `keep` (<name>.step becomes <name>.step.zip beside it),
    so only the build in hand holds an unzipped STEP (about a tenth of the size). Returns the builds zipped."""
    done = []
    for step in sorted(builds.glob("*/*-full-[0-9][0-9][0-9]/*.step")):
        if step.parent == keep or not rp.build_key(step.parent.name):
            continue
        dst = step.with_name(step.name + ".zip")
        part = dst.with_name(dst.name + ".partial")
        zi = zipfile.ZipInfo(step.name, date_time=dt.datetime.fromtimestamp(step.stat().st_mtime).timetuple()[:6])
        zi.compress_type = zipfile.ZIP_DEFLATED
        with zipfile.ZipFile(part, "w", zipfile.ZIP_DEFLATED) as z, open(step, "rb") as fin, \
                z.open(zi, "w", force_zip64=True) as fout:
            shutil.copyfileobj(fin, fout, 1 << 22)
        part.replace(dst)
        os.chmod(dst, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
        os.chmod(step, stat.S_IWRITE | stat.S_IREAD)   # a finished build's files are read-only (lock_build)
        step.unlink()
        done.append(step.parent.name)
    return done


def filed_name(build_name: str, rev: str) -> str:
    """Filed path of a build file, relative to the document folder, as revisions.csv `file` holds it: inside the
    revision's own folder (rp.rev_folder) and its subfolder (rp.model_subfolder: Takeoffs, Reports, Views), the STEP
    in a zip, every name carrying the revision."""
    stem = rp.rev_folder(DOC_ID, rev)
    if build_name == STEP.name:
        name = f"{stem}.step.zip"
    elif build_name == GLB.name:
        name = f"{stem}.glb"
    else:
        name = f"{stem}-{build_name}"
    sub = rp.model_subfolder(name)
    return f"{stem}/{sub}/{name}" if sub else f"{stem}/{name}"


def filed_file(rev: str, suffix: str, root: Path | None = None) -> Path:
    """A filed file of revision `rev`: suffix ".glb", ".step.zip" or "-<takeoff>" (default root: FILED)."""
    stem = rp.rev_folder(DOC_ID, rev)
    return rp.model_rev_file((root if root is not None else FILED) / stem, f"{stem}{suffix}")


def view_files() -> list[Path]:
    """The review views a job-level model files ([] for the project's model)."""
    return [BUILD / n for _, n in VIEWS] if JOB_LEVEL else []


def build_files() -> list[Path]:
    """Every work-build file a revision files, STEP and GLB first."""
    return [STEP, GLB] + [BUILD / n for n in TAKEOFFS] + view_files()


def canonical_config() -> tuple[str | None, str]:
    """(canonical name, message) of the chosen configuration of a job-level model, from the model's own skidlib
    (skidlib.canonical_config); (None, why) when the model refuses it. A project model: (None, '')."""
    if not JOB_LEVEL:
        return None, ""
    if str(rp.SKID_MODEL) not in sys.path:
        sys.path.insert(0, str(rp.SKID_MODEL))
    import skidlib
    fn = getattr(skidlib, "canonical_config", None)
    if fn is None:
        return rp.MODEL_CONFIG, ""
    try:
        return fn(rp.MODEL_CONFIG), ""
    except ValueError as e:
        return None, str(e)


def source_files() -> list[Path]:
    """Everything the build is derived from: model source, the named inputs, component models, rules."""
    if str(rp.SKID_MODEL) not in sys.path:
        sys.path.insert(0, str(rp.SKID_MODEL))
    from skidlib import inputs
    files = set(inputs.input_files())
    files |= {p for p in rp.SKID_MODEL.rglob("*.py") if "__pycache__" not in p.parts}
    files |= set(rp.SKID_MODEL.glob("*.json"))
    files |= set(components.step_files())   # job library, then project (harness/lib/components.py)
    files |= {rp.HARNESS_DESIGN_RULES / "structural.yaml", rp.JOB_DESIGN_RULES / "structural.yaml",
              rp.DESIGN_RULES / "structural.yaml",
              rp.CHECKS / "pipe_supports.py", rp.LIB / "list_delta.py"}
    return sorted(p for p in files if p.is_file())


def newest_source() -> tuple[float, Path]:
    """(mtime, path) of the most recently changed source file."""
    return max((p.stat().st_mtime, p) for p in source_files())


def next_letter(last: str | None) -> str:
    """A..Z, then AA, AB ... (CLAUDE.md ASSUMPTION: after Z the sequence continues AA, AB)."""
    if not last:
        return "A"
    s = list(last)
    i = len(s) - 1
    while i >= 0 and s[i] == "Z":
        s[i] = "A"
        i -= 1
    if i < 0:
        return "A" + "".join(s)
    s[i] = chr(ord(s[i]) + 1)
    return "".join(s)


def filed_rows(root: Path | None = None) -> list[dict]:
    """The rows of a filed document's revisions.csv (default: the skid model's filed folder); [] when none. For a
    job-level model only the rows of its configuration's document (document_id DOC_ID)."""
    if root is None and not rp.HAS_MODEL:
        return []
    p = (root if root is not None else FILED) / "revisions.csv"
    if not p.exists():
        return []
    with open(p, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    return [r for r in rows if r.get("document_id") == DOC_ID] if JOB_LEVEL else rows


def last_revision(root: Path | None = None) -> str | None:
    rows = filed_rows(root)
    # the highest letter, not the last row: a presentation locked later into an older revision appends rows too
    return max((r["revision"] for r in rows), key=lambda s: (len(s), s)) if rows else None
