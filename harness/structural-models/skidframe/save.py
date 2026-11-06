"""Save a model run as a project-level calculation record.

The suite is company-wide (harness/structural-models/, every CPME skid job); every result lives in the project that
used it, with notes on its use (the practice Bob set for the thermal models, chat, 2026-11-06: "The results from
using them must be saved on the project level with proper notes relating to their use."):

    <project>/02_Engineering/06_Mechanical_Structural/Frame_Calcs/<YYYY-MM-DD>_<model>_<case-slug>[-n]/
        <case-slug>.md      the calculation record, opening with the use notes
        inputs.yaml         the exact input file (regenerate with: python -m skidframe run inputs.yaml <model>)
        result.json         the full machine-readable result
    <project>/02_Engineering/11_Scripts_Models/frame-calc-log.csv   one row per saved run

A saved run is never overwritten: a second run of the same case on the same day takes the next -n suffix (the
TR-08 practice for records). The inputs file must state why the run was made (purpose), where each input came from
(inputs_source: filed cut list, manifest, vendor drawing) and who ran it (run_by); a run without them is refused,
because a number without its use notes cannot be traced (hard rules 1, 2 and 4). The structural result is a working
aid for the engineer's Gate 3 check, never a certification.
"""
from __future__ import annotations

import csv
import datetime as _dt
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

from . import __version__

PKG = Path(__file__).resolve().parent
LOG_NAME = "frame-calc-log.csv"
TOPIC = "06_Mechanical_Structural"
RECORDS = "Frame_Calcs"
LOG_FIELDS = ["date", "record", "model", "case", "purpose", "inputs_source", "run_by", "status", "result",
              "governing", "fail_checks", "assumptions", "warnings", "suite_version", "suite_sha256"]
DEFAULT_STATUS = "working aid for the Gate 3 frame check - not approved, not a certification (only Bob approves)"
NOTE_KEYS = ("name", "purpose", "inputs_source", "run_by", "status", "notes")
REQUIRED_NOTES = ("name", "purpose", "inputs_source", "run_by")


def split_notes(data: dict) -> tuple[dict, dict]:
    """(use notes, model inputs): the note keys are removed so a model never sees them."""
    data = dict(data or {})
    notes = {k: data.pop(k) for k in NOTE_KEYS if k in data}
    return notes, data


def suite_hash() -> str:
    """sha256 (first 12 hex) of the model source, so a record names the exact code that produced it."""
    h = hashlib.sha256()
    for p in sorted(PKG.glob("*.py")):
        h.update(p.name.encode())
        h.update(p.read_bytes().replace(b"\r\n", b"\n"))
    return h.hexdigest()[:12]


def active_project_dir() -> Path:
    repo = next(p for p in PKG.parents if (p / "CLAUDE.md").exists())
    sys.path.insert(0, str(repo / "harness" / "lib"))
    import repo_paths as rp  # noqa: E402
    if not rp.HAS_PROJECT:
        raise ValueError(f"no active project to save into: {rp.NO_PROJECT_HINT}")
    return rp.PROJECT


def check_notes(notes: dict) -> None:
    missing = [k for k in REQUIRED_NOTES if not str(notes.get(k) or "").strip()]
    if missing:
        raise ValueError("the inputs file needs its use notes before a run is saved: " + ", ".join(missing)
                         + " (name = short case name; purpose = why it is run and what decision it supports; "
                           "inputs_source = where each input comes from; run_by = the agent or person). "
                           "Use 'check' for a preview.")


def _slug(text: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "-", str(text)).strip("-").lower()
    return s[:60] or "case"


def _sources_text(src) -> str:
    if isinstance(src, dict):
        return "; ".join(f"{k}: {v}" for k, v in src.items())
    return str(src)


def use_notes_md(notes: dict, out: dict, rec_dir: Path, repo: Path, date: str) -> str:
    fails = [c for c in out["checks"] if c["result"] == "FAIL"]
    g = out.get("governing")
    src = notes.get("inputs_source")
    L = ["## Use notes", "",
         "| Item | Note |", "|---|---|",
         f"| Purpose | {notes['purpose']} |",
         f"| Run by | {notes['run_by']} |",
         f"| Date | {date} |",
         f"| Status | {notes.get('status') or DEFAULT_STATUS} |",
         f"| Model | `{out['model']}` - {out['title']} |",
         f"| Tool | skidframe {__version__}, source sha256 {suite_hash()} (harness/structural-models) |",
         f"| Regenerate | `python -m skidframe run {out['model']} "
         f"{(rec_dir / 'inputs.yaml').relative_to(repo).as_posix()}` from harness/structural-models (saves a new "
         "record; this one is never overwritten) |",
         f"| Result | {out['status']}"
         + (f"; governing {g['name']} at {g['ratio']:.3f} ({g['rule']})" if g else "") + " |",
         f"| Findings | {len(fails)} FAIL check(s){': ' + '; '.join(c['name'] for c in fails) if fails else ''} |",
         f"| Assumptions | {len(out['assumptions'])} ASSUMPTION line(s), listed below: carry each into the handoff "
         "with its record and replace it when a document gives the value (hard rule 4) |",
         f"| Warnings | {len(out['warnings'])}: a warning on a governing check needs a hand check or a better input |"]
    if notes.get("notes"):
        L.append(f"| Notes | {notes['notes']} |")
    L += ["", "**Where each input came from**", ""]
    if isinstance(src, dict):
        L += [f"- `{k}`: {v}" for k, v in src.items()]
    else:
        L.append(f"- {src}")
    return "\n".join(L) + "\n"


def save_run(notes: dict, out: dict, md: str, inputs_path: Path, project_dir: Path | None = None) -> Path:
    """Write the record folder and the log row; return the record (.md) path."""
    check_notes(notes)
    project = Path(project_dir) if project_dir else active_project_dir()
    eng = project / "02_Engineering"
    if not eng.is_dir():
        raise ValueError(f"{eng} is missing: not a project folder")
    repo = next((p for p in project.parents if (p / "CLAUDE.md").exists()), project.parent)
    model = out["model"]
    date = _dt.date.today().isoformat()
    base = f"{date}_{model}_{_slug(notes['name'])}"
    parent = eng / TOPIC / RECORDS
    rec_dir = parent / base
    n = 1
    while rec_dir.exists():
        n += 1
        rec_dir = parent / f"{base}-{n}"
    rec_dir.mkdir(parents=True)
    shutil.copyfile(inputs_path, rec_dir / "inputs.yaml")
    (rec_dir / "result.json").write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    head, rest = md.split("\n", 1)
    rec = rec_dir / f"{_slug(notes['name'])}.md"
    rec.write_text(head + "\n\n" + use_notes_md(notes, out, rec_dir, repo, date) + rest, encoding="utf-8")

    log = eng / "11_Scripts_Models" / LOG_NAME
    log.parent.mkdir(parents=True, exist_ok=True)
    new = not log.exists()
    g = out.get("governing")
    with log.open("a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=LOG_FIELDS)
        if new:
            w.writeheader()
        w.writerow(dict(date=date, record=rec.relative_to(project).as_posix(), model=model, case=notes["name"],
                        purpose=notes["purpose"], inputs_source=_sources_text(notes["inputs_source"]),
                        run_by=notes["run_by"], status=notes.get("status") or DEFAULT_STATUS,
                        result=out["status"], governing="" if not g else f"{g['name']} {g['ratio']:.3f}",
                        fail_checks=sum(c["result"] == "FAIL" for c in out["checks"]),
                        assumptions=len(out["assumptions"]), warnings=len(out["warnings"]),
                        suite_version=__version__, suite_sha256=suite_hash()))
    return rec
