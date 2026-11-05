"""model_build - what a skid-model build is made of, shared by the three tiers (CPME practice).

    harness/scripts/model_iterate.py   tier 1, every build: writes the work build (<project>/03_Working_Design/Exports/build/<MODEL-ID>/)
    harness/scripts/model_file.py      tier 2, when Bob looks at it: files the work build as the next revision
    harness/scripts/closeout.py        tier 3, once a day on Bob's word: Drive push, checks, portal, commit body

One place names the build's files, the filed name of each, and the source files a build is derived from,
so model_file can refuse a work build that is older than its source (TR-03, TR-08).

The model is the project's skid model unless a job-level model is chosen (--model-id / --config, harness/lib/
repo_paths.py). A job-level model files each configuration as its own document, DOC_ID = <MODEL-ID>-<CFG>, with its
own letters from Rev A: every filed name is <DOC_ID>-rev<X>..., and its revisions.csv rows are the rows whose
document_id is DOC_ID (B and X share the model's filed folder). A job-level model also files four review views
(VIEWS, harness/cad-lib/render_png.py from the build STEP).
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import repo_paths as rp
import components

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
