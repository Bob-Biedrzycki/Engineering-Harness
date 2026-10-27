"""components - the component registers and libraries, job first, then project.

Bob, chat, 2026-10-26: the component library belongs to the job (every project in it), so projects reuse parts; a
part made for one project only stays in that project. Two libraries, same layout (job/components/README.md):

    job      rp.JOB_COMPONENTS  (job/components/)                             register rp.JOB_COMPONENT_REGISTER
    project  rp.COMPONENTS      (<project>/03_Working_Design/CAD/05_Purchased_Components/)  register rp.COMPONENT_REGISTER

Each holds component-register.csv (one row per component revision, COLUMNS below) and one folder per component,
COMP-nnnn_<Maker>_<Model>/ with 01_Cut_Sheet/, 02_STEP_Vendor/, 03_STEP_CPME/, 04_Install_Practice/ and src/.

File columns (cut_sheet_file, vendor_step_file, cpme_step_file) name a path relative to the register's own folder
(e.g. COMP-0001_ifm_TD2947/01_Cut_Sheet/TD2947.pdf); a value starting with job/ or harness/ is read as repo-relative.
A file held only in the Google Drive store is found through its <file>.drive pointer (drive_store.py pull fetches it).

Every reader of component data uses this module (accept_preflight, pipe_supports, portal_terms, model_build,
harness/checks/component_register.py); nothing else opens a register. Stdlib only, so every venv can import it.
"""
from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path

import repo_paths as rp

COLUMNS = ("component_id", "revision", "status", "supersedes", "category", "description", "manufacturer", "model",
           "part_number", "size", "end_connections", "service_classes", "material", "pressure_rating",
           "temperature_rating", "weight_lb", "envelope_in", "frame", "cut_sheet_file", "cut_sheet_source",
           "cut_sheet_obtained_on", "vendor_step_file", "vendor_step_source", "vendor_step_obtained_on",
           "vendor_step_sha256", "cpme_step_file", "cpme_step_sha256", "install_practice", "licence", "obtained_by",
           "used_on", "notes")
FILE_COLUMNS = (("cut_sheet_file", None), ("vendor_step_file", "vendor_step_sha256"),
                ("cpme_step_file", "cpme_step_sha256"))
DATE_COLUMNS = ("cut_sheet_obtained_on", "vendor_step_obtained_on")
STATUSES = ("current", "superseded")
ID_RE = re.compile(r"^COMP-\d{4}$")
FOLDER_RE = re.compile(r"^(COMP-\d{4})_")
STEP_SUBDIRS = ("03_STEP_CPME", "02_STEP_Vendor", "src")   # search order inside a component folder
STEP_SUFFIXES = (".step", ".stp")
POINTER_SUFFIX = ".drive"


@dataclass(frozen=True)
class Library:
    level: str        # "job" or "project"
    root: Path        # the library folder
    register: Path    # its component-register.csv


def libraries() -> list[Library]:
    """The job library first, then the project's (the job library only while the job has no project yet)."""
    libs = [Library("job", rp.JOB_COMPONENTS, rp.JOB_COMPONENT_REGISTER)]
    if rp.HAS_PROJECT:
        libs.append(Library("project", rp.COMPONENTS, rp.COMPONENT_REGISTER))
    return libs


def read_register(path: Path) -> tuple[list[str], list[dict]]:
    """(header, rows) of one register; ([], []) when the file is missing."""
    if not path.is_file():
        return [], []
    with open(path, newline="", encoding="utf-8-sig") as f:
        r = csv.DictReader(f)
        return list(r.fieldnames or []), [dict(row) for row in r]


def rows(libs: list[Library] | None = None) -> list[dict]:
    """Every register row, job library first. Each row also carries `_library` (job / project) and `_root` (Path)."""
    out = []
    for lib in libs or libraries():
        for row in read_register(lib.register)[1]:
            out.append({**{k: (v or "").strip() for k, v in row.items() if k is not None},
                        "_library": lib.level, "_root": lib.root})
    return out


def current_rows(libs: list[Library] | None = None) -> list[dict]:
    """Rows whose status is `current` (blank counts as current until the register check reports it)."""
    return [r for r in rows(libs) if r.get("status", "").lower() in ("", "current")]


def obtained_on(row: dict) -> str:
    """YYYY-MM-DD the row's information came in: the latest of its obtained_on dates, '' if none."""
    return max(((row.get(c) or "")[:10] for c in DATE_COLUMNS), default="")


def resolve(row: dict, value: str) -> Path | None:
    """The file a file column names (see the module docstring), or None for a blank / unknown value."""
    v = (value or "").strip()
    if not v or v.lower() == "unknown":
        return None
    if v.startswith(("job/", "harness/")):
        return rp.REPO / v
    return Path(row["_root"]) / v


def pointer_of(p: Path) -> dict | None:
    """The Drive store pointer beside a file, or None."""
    ptr = p.with_name(p.name + POINTER_SUFFIX)
    if not ptr.is_file():
        return None
    try:
        return json.loads(ptr.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return None


def component_folders(libs: list[Library] | None = None) -> list[tuple[Library, Path]]:
    """(library, folder) for every COMP-nnnn_* folder, job library first."""
    out = []
    for lib in libs or libraries():
        if lib.root.is_dir():
            out += [(lib, d) for d in sorted(lib.root.iterdir()) if d.is_dir() and FOLDER_RE.match(d.name)]
    return out


def step_files(libs: list[Library] | None = None) -> list[Path]:
    """Every component STEP in both libraries: 03_STEP_CPME, 02_STEP_Vendor, then src/ outputs, per folder."""
    out = []
    for _, d in component_folders(libs):
        for sub in STEP_SUBDIRS:
            if (d / sub).is_dir():
                out += sorted(p for p in (d / sub).rglob("*") if p.is_file() and p.suffix.lower() in STEP_SUFFIXES)
    return out


def find_step(name: str, libs: list[Library] | None = None) -> Path | None:
    """The first component STEP with this file name (job library first), or None."""
    return next((p for p in step_files(libs) if p.name == name), None)


def _num(v) -> float | None:
    try:
        s = str(v).strip()
        return None if not s or s.lower() == "unknown" else float(s)
    except ValueError:
        return None


def weights(libs: list[Library] | None = None) -> dict[str, tuple[float, str]]:
    """{key: (lb, source)} from the current rows' weight_lb, keyed by component_id, and by pid_tag where a register
    still carries that column. The first library to give a key wins (job first)."""
    out: dict[str, tuple[float, str]] = {}
    for r in current_rows(libs):
        w = _num(r.get("weight_lb"))
        if w is None:
            continue
        src = f"{r['_library']} component register {r.get('component_id', '')} rev {r.get('revision', '')} weight_lb {w:g} lb"
        for key in (r.get("component_id", ""), r.get("pid_tag", "")):
            if key and key not in out:
                out[key] = (w, src)
    return out


def vendor_names(libs: list[Library] | None = None) -> list[tuple[str, str]]:
    """(manufacturer, model) of every row, for the portal forbidden-terms lint."""
    return [(r.get("manufacturer", ""), r.get("model", "")) for r in rows(libs)]
