"""repo_paths - the one place that names every location in the repo.

Layout (CPME practice; project folders, Bob 2026-10-26): harness/ holds
the company tools, rules and knowledge; job/ holds the job (product line), one
numbered project folder per order, job/Project-<nnnn-nn>-<TYPE>-<nnn>/. Scripts
import these names instead of counting parent folders, so a future move is an
edit here only.

Bootstrap from any script in the repo:

    import sys
    from pathlib import Path
    sys.path.insert(0, str(next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists()) / "harness" / "lib"))
    import repo_paths as rp

No project yet (a new job repo before harness/scripts/project_new.py has run): the import still succeeds.
PROJECT is None, PROJECT_INFO is {}, the repo, harness and job names work, and every project name (DATA,
SKID_MODEL, PROJECT_ID, ...) raises NoProjectError, an AttributeError that says so, only when it is used. A check's
main() starts with `if rp.skip_no_project("<check>"): return 0`; a script that needs a project calls
`rp.require_project("<script>")`, which exits 2 with a plain message.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists())

HARNESS = REPO / "harness"
CAD_LIB = HARNESS / "cad-lib"
CHECKS = HARNESS / "checks"
SCRIPTS = HARNESS / "scripts"
LIB = HARNESS / "lib"
HARNESS_DESIGN_RULES = HARNESS / "design-rules"   # level 1: company-wide rules (every CPME job)
TOOLS = HARNESS / "tools"
# Questions between agents, and the copy addressed to Bob (Bob, chat, 2026-10-26).
AGENT_QUESTIONS = REPO / "Agent-to-Agent Questions.md"
BOB_QUESTIONS = REPO / "Agent-to-Bob Questions.md"

# Job and projects (Bob, chat, 2026-10-26; TR-09): a job is the product line and its repo; a project is one order
# in it, job/Project-<Project Number>-<Type>-<Top Level Version>/, laid out from harness/templates/project-folder/
# (README_Project_Guide.md there). The Project Number in the folder name is the project code (nnnn-nn);
# `project_number` in project.yaml is CPME's short order number. PROJECT is the active project folder.
JOBS = REPO / "job"                      # the job: job-wide folders plus one folder per project
JOB_KNOWLEDGE = JOBS / "knowledge"       # job-wide knowledge (every project in the job)
JOB_DESIGN_RULES = JOBS / "design-rules"  # level 2: job-wide rules (every project in the job); level 3 is DESIGN_RULES
# Component library of the job (Bob, chat, 2026-10-26: every project in the job reuses it): component-register.csv
# and one COMP-nnnn_<Maker>_<Model>/ folder per component (job/components/README.md). Read through
# harness/lib/components.py.
JOB_COMPONENTS = JOBS / "components"
JOB_COMPONENT_REGISTER = JOB_COMPONENTS / "component-register.csv"
PROJECT_TEMPLATE = HARNESS / "templates" / "project-folder"
ACTIVE_PROJECT_FILE = JOBS / "active-project.txt"   # names the project when job/ holds more than one
DRIVE_STORE_CONFIG = JOBS / "drive-store.yaml"   # one Drive store for the whole job (Bob, chat, 2026-10-26); drive_store.py
DRIVE_ROOT_FILE = JOBS / "_work" / "drive-root.txt"  # machine-specific local path of the Drive folder (Google Drive for Desktop)
CARRYOVER_TERMS = JOBS / "carryover-terms.txt"   # earlier jobs' terms, reversed (harness/tests/test_no_carryover.py)
NO_PROJECT_HINT = "no project yet: job/ has no Project-* folder (make one with harness/scripts/project_new.py)"


class NoProjectError(AttributeError):
    """A project name (DATA, SKID_MODEL, PROJECT_ID, ...) was used while the job has no project yet."""


def _active_project() -> Path | None:
    """CPME_PROJECT, else job/active-project.txt, else the only Project-* folder; None when job/ has none.
    Stops when a named project has no folder, or several folders exist and nothing names one."""
    name = os.environ.get("CPME_PROJECT", "").strip()
    if not name and ACTIVE_PROJECT_FILE.is_file():
        name = ACTIVE_PROJECT_FILE.read_text(encoding="utf-8").strip()
    if name:
        if not (JOBS / name).is_dir():
            raise RuntimeError(f"active project {name!r} has no folder under {JOBS}")
        return JOBS / name
    found = sorted(p for p in JOBS.glob("Project-*") if p.is_dir())
    if not found:
        return None
    if len(found) == 1:
        return found[0]
    raise RuntimeError(f"{JOBS} holds {len(found)} project folders; set CPME_PROJECT or write the folder name "
                       f"in {ACTIVE_PROJECT_FILE.name} (new project: harness/scripts/project_new.py)")


def _read_project_config(path: Path) -> dict[str, str]:
    """Flat `key: value` lines, `#` comments; no PyYAML so every venv can import this module."""
    if not path.is_file():
        raise RuntimeError(f"{path} is missing: every project names itself there (keys {', '.join(PROJECT_KEYS)}; "
                           "harness/scripts/project_new.py)")
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split(" #", 1)[0].strip() if not line.lstrip().startswith("#") else ""
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    missing = [k for k in PROJECT_KEYS if k not in out]
    if missing:
        raise RuntimeError(f"{path} lacks {', '.join(missing)}")
    return out


PROJECT_KEYS = ("project_id", "project_number", "project_code", "customer", "location", "skid_name", "skid_title",
                "skid_description", "model_id", "pid_doc_id", "retired_model_id", "design_repo", "site_repo")
_FOUND = _active_project()
HAS_PROJECT = _FOUND is not None

# ---- project names: everything from here to _PROJECT_NAMES is about the active project. With no project yet the
# block runs once on a placeholder folder (so the names are known), then the names are removed and raise
# NoProjectError when used (module __getattr__ below).
_BEFORE_PROJECT = set(globals())
PROJECT = _FOUND if HAS_PROJECT else JOBS / "Project-0000-00-NONE-000"
ADMIN = PROJECT / "00_Project_Admin"
DESIGN_BASIS = PROJECT / "01_Design_Basis"
ENGINEERING = PROJECT / "02_Engineering"
WORKING = PROJECT / "03_Working_Design"
VENDOR_DATA = PROJECT / "04_Vendor_Data"
REVIEWS = PROJECT / "05_Reviews_Changes"
ISSUED = PROJECT / "06_Issued_Revisions"
FABRICATION_QA = PROJECT / "07_Fabrication_QA"
HANDOVER = PROJECT / "08_Handover"

DATA = WORKING / "PID" / "02_Tag_Lists"  # the six P&ID lists (was job/data/)
OPEN_ITEMS = DESIGN_BASIS / "06_Assumptions_Open_Items"   # pid-questions, equipment-concerns, open rule questions
CUSTOMER_REQUIREMENTS = DESIGN_BASIS / "01_Customer_Requirements"   # intake, holds.md, customer source files
REGISTERS = ADMIN / "07_Project_Controls" / "Registers"
DECISIONS = ADMIN / "05_Decision_Log"
DESIGN_RULES = DESIGN_BASIS / "05_Standards_Specifications" / "Design_Rules"   # level 3: this project only
SOURCES = VENDOR_DATA                    # supplier documents and CAD, one folder per tag (was job/sources/)
CAD = WORKING / "CAD"
# Project-only components (a one-off adapter, a customer-supplied item): same register columns and COMP-* folders as
# JOB_COMPONENTS; the job library is read first (harness/lib/components.py).
COMPONENTS = CAD / "05_Purchased_Components"
COMPONENT_REGISTER = COMPONENTS / "component-register.csv"

# Project identity: project.yaml in the project folder is the one place a project names itself; harness
# code takes IDs from here, never as literals, so a new project writes project.yaml and changes no harness code.
PROJECT_CONFIG = PROJECT / "project.yaml"

PROJECT_INFO = _read_project_config(PROJECT_CONFIG) if HAS_PROJECT else dict.fromkeys(PROJECT_KEYS, "")
PROJECT_ID = PROJECT_INFO["project_id"]          # <nnnn-nn>-<TYPE>-<nnn> (folder Project-<project_id>)
PROJECT_NUMBER = PROJECT_INFO["project_number"]  # CPME's short order number
PROJECT_CODE = PROJECT_INFO["project_code"]      # title block NUMBER cell, <nnnn-nn>
CUSTOMER = PROJECT_INFO["customer"]
PID_DOC_ID = PROJECT_INFO["pid_doc_id"]        # <project_id>-PID-001; filed under DRAWINGS / PID_DOC_ID
DESIGN_REPO = PROJECT_INFO["design_repo"]      # owner/name of this repo's origin (the job's repo, TR-09)
SITE_REPO = PROJECT_INFO["site_repo"]          # owner/name of the presentation site repo

# The skid model source, one folder per MODEL-ID (model_id in project.yaml).
SKID_MODEL_ID = PROJECT_INFO["model_id"]
SKID_MODEL = CAD / "01_Master_Assembly" / SKID_MODEL_ID
FRAME_CALC = ENGINEERING / "06_Mechanical_Structural" / "frame-calc"   # frame_calc.py and its results
EXPORTS = WORKING / "Exports"            # regenerated build output (gitignored working copies)
BUILD = EXPORTS / "build"
PREVIEW = EXPORTS / "preview"
SKID_BUILD = BUILD / SKID_MODEL_ID       # working copy of the build (gitignored)
MODELS = ISSUED / "Models"               # filed designs (TR-08)
SKID_FILED = MODELS / SKID_MODEL_ID      # filed revisions of the model (TR-08)
# History only: a retired model ID whose filed revisions stay untouched (TR-08) after its source moved to
# SKID_MODEL. Blank in project.yaml on a project that has none: then "" and None.
RETIRED_MODEL_ID = PROJECT_INFO["retired_model_id"]
RETIRED_MODEL = MODELS / RETIRED_MODEL_ID if RETIRED_MODEL_ID else None   # the old FILED folder
DRAWING_SOURCES = CAD / "06_Drawings" / "Generators"
# Filed drawings (TR-08); CPME_DRAWINGS_ROOT points a test run at a scratch folder.
DRAWINGS = Path(os.environ["CPME_DRAWINGS_ROOT"]) if os.environ.get("CPME_DRAWINGS_ROOT") else ISSUED / "Drawings"
PID_FAST_EDITS = WORKING / "PID" / "Fast_Edits"  # model-to-pid.py --fast, rev<X>-fast-<nnn>; gitignored, not filed
FAST_BUILDS = CAD / "Fast_Builds"        # model_iterate.py --fast, one new rev<X>/rev<X>-fast-<nnn>/ per run; gitignored, not filed
ISSUE_INDEX = ISSUED / "00_Issue_Index"  # Issue_Register.csv; ISS-### packages sit beside it (Bob, 2026-10-26)

WORK = PROJECT / "_work"                    # gitignored working copies
FILING = WORK / "filing"
TRACKING = WORK / "tracking"
DAILY = WORK / "daily"                   # close-out output: commit body skeleton, candidate paths (closeout.py)
PORTAL_MEDIA = WORK / "portal-media"     # portal_media.py output, one rev<X>/ folder per filed model revision
PORTAL_WORK = WORK / "portal"            # build_portal.py working copy
PORTALS = ISSUED / "Portals"             # filed portal revisions (was job/reviews/)
PORTAL_FILED = PORTALS / "project-portal"  # filed portal revisions and the shared data store
QUOTING_FILED = PORTALS / "quoting-portal"   # Fabrication Estimating Portal revisions (record ID quoting-portal)
LANDING_FILED = PORTALS / "portal-landing"   # presentation site landing page revisions
MOBILE_FILED = PORTALS / "mobile-portal"     # Mobile Optimized: the tracker for phones (Bob, 2026-10-17)
INTERNAL_REVIEWS = REVIEWS / "01_Internal_Reviews"   # gate packages, review renders, frame-calc reports
PRESENTATIONS = CAD / "09_Presentation"  # presentation builders and portal assets (was job/cad/Presentations/)
SITE_CONFIG = PRESENTATIONS / "site.yaml"    # site settings: hidden_models (model IDs kept off the site), hidden_pages
EQUIPMENT_SELECTION = VENDOR_DATA        # vendor references, <category>/<tag>/ (Drive store)
# presentation site checkout, a sibling of this repo: publishing target only (TR-09 conflict C-08; publish_site.py)
PRESENTATION_SITE = REPO.parent / SITE_REPO.rsplit("/", 1)[-1]

_PROJECT_NAMES = frozenset(n for n in set(globals()) - _BEFORE_PROJECT if not n.startswith("_"))
del _BEFORE_PROJECT
if not HAS_PROJECT:
    for _n in _PROJECT_NAMES:
        del globals()[_n]
    del _n
    PROJECT = None
    PROJECT_INFO = {}


def __getattr__(name: str):
    """Module attribute fallback: a project name used while the job has no project yet."""
    if name in _PROJECT_NAMES:
        raise NoProjectError(f"repo_paths.{name} is not available: {NO_PROJECT_HINT}")
    raise AttributeError(f"module 'repo_paths' has no attribute {name!r}")


def skip_no_project(check: str) -> bool:
    """For a check's main(): True, after printing `<check>: PASS - not checked: no project yet`, when the job has no
    project yet (the check then returns 0); False when there is a project to check."""
    if HAS_PROJECT:
        return False
    print(f"{check}: PASS - not checked: no project yet")
    return True


def require_project(script: str) -> None:
    """For a script that works on a project: exit 2 with a plain message when the job has none yet."""
    if not HAS_PROJECT:
        print(f"{script}: REFUSED - {NO_PROJECT_HINT}", file=sys.stderr)
        raise SystemExit(2)


def rel(p: Path) -> str:
    """Repo-relative path with forward slashes, for records and messages."""
    return Path(p).resolve().relative_to(REPO).as_posix()
