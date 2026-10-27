"""model_build - what a skid-model build is made of, shared by the three tiers (CPME practice).

    harness/scripts/model_iterate.py   tier 1, every build: writes the work build (<project>/03_Working_Design/Exports/build/<MODEL-ID>/)
    harness/scripts/model_file.py      tier 2, when Bob looks at it: files the work build as the next revision
    harness/scripts/closeout.py        tier 3, once a day on Bob's word: Drive push, checks, portal, commit body

One place names the build's files, the filed name of each, and the source files a build is derived from,
so model_file can refuse a work build that is older than its source (TR-03, TR-08).
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
if rp.HAS_PROJECT:   # no project yet: the functions below that read a revisions.csv still work (last_revision)
    MODEL_ID = rp.SKID_MODEL_ID
    BUILD = rp.SKID_BUILD
    FILED = rp.SKID_FILED
    SUMMARY = BUILD / "iterate-summary.json"   # written by model_iterate.py, read by model_file.py
    STEP = BUILD / f"{MODEL_ID}.step"
    GLB = BUILD / f"{MODEL_ID}.glb"


def filed_name(build_name: str, rev: str) -> str:
    """Filed file name for a build file: the STEP goes into a zip, everything carries the revision."""
    if build_name == STEP.name:
        return f"{MODEL_ID}-rev{rev}.step.zip"
    if build_name == GLB.name:
        return f"{MODEL_ID}-rev{rev}.glb"
    return f"{MODEL_ID}-rev{rev}-{build_name}"


def build_files() -> list[Path]:
    """Every work-build file a revision files, STEP and GLB first."""
    return [STEP, GLB] + [BUILD / n for n in TAKEOFFS]


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
    """The rows of a filed document's revisions.csv (default: the skid model's filed folder); [] when none."""
    if root is None and not rp.HAS_PROJECT:
        return []
    p = (root if root is not None else FILED) / "revisions.csv"
    if not p.exists():
        return []
    with open(p, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def last_revision(root: Path | None = None) -> str | None:
    rows = filed_rows(root)
    return rows[-1]["revision"] if rows else None
