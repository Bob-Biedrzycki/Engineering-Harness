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
import re
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

# Job and projects (Bob, chat, 2026-10-26): a job is the product line and its folder (one repo); a project is one order
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
# The typicals: the drawings and models that serve every project in the job (typical P&IDs, typical models, their GA
# drawings) stay at job level (Bob, chat, 2026-10-27: "Job level, unless directed otherwise") in ONE folder laid out
# like a project, job/Typical-<ID prefix>/ (Bob, chat, 2026-11-09: "use the file structure of project 9876 sans the
# irelevant folders ... develop the typical models as we would an actual project"). Only the folders the typicals
# use exist; each has the name and the place it has in a project (README_Project_Guide.md in the folder):
#     03_Working_Design/CAD/01_Master_Assembly/    the typical models' source and their shared library (JOB_MODELS)
#     03_Working_Design/CAD/06_Drawings/Generators/ the typical drawing generators (JOB_DRAWING_SOURCES)
#     03_Working_Design/CAD/09_Presentation/       lifelike render tools (JOB_PRESENTATIONS)
#     03_Working_Design/PID/02_Tag_Lists/          the typical P&ID lists and each range model's lists (JOB_LISTS)
#     03_Working_Design/Exports/build/, CAD/Fast_Builds/   work builds (gitignored)
#     06_Issued_Revisions/Drawings/, Models/       locked revisions (JOB_DRAWINGS, JOB_MODELS_FILED; TR-08)
#     _work/                                       gitignored working copies (JOB_WORK)
# The JOB_* names are kept from when these sat loose in job/ (before 2026-11-09), so their users did not change.
def _typical() -> Path:
    """The job's typicals folder: the only job/Typical-* folder. A job with none gets a name that does not exist."""
    found = sorted(p for p in JOBS.glob("Typical-*") if p.is_dir())
    if len(found) > 1:
        raise RuntimeError(f"{JOBS} holds {len(found)} Typical-* folders; a job has one typicals folder")
    return found[0] if found else JOBS / "Typical-NONE"


TYPICAL = _typical()
TYPICAL_WORKING = TYPICAL / "03_Working_Design"
JOB_ISSUED = TYPICAL / "06_Issued_Revisions"
JOB_DRAWINGS = JOB_ISSUED / "Drawings"
JOB_WORK = TYPICAL / "_work"             # gitignored working copies of the typicals (job/*/_work/)
JOB_FILING = JOB_WORK / "filing"         # gitignored staging for filing a typical drawing
JOB_LISTS = TYPICAL_WORKING / "PID" / "02_Tag_Lists"
JOB_DRAWING_SOURCES = TYPICAL_WORKING / "CAD" / "06_Drawings" / "Generators"
JOB_PRESENTATIONS = TYPICAL_WORKING / "CAD" / "09_Presentation"
JOB_REGISTERS = TYPICAL / "00_Project_Admin" / "07_Project_Controls" / "Registers"   # path-crosswalk.csv


def rev_folder(doc_id: str, rev: str) -> str:
    """Name of one filed revision's own folder inside its document folder (Bob, chat, 2026-10-30: "Everything like
    for them should be in a folder for each rev."): <DOC-ID>-rev<X>/ holds every file of that revision, and the
    document folder holds only revisions.csv and these folders. revisions.csv `file` is "<DOC-ID>-rev<X>/<name>",
    so <document folder> / row["file"] is the filed file. harness/checks/filed_layout.py checks it."""
    return f"{doc_id}-rev{rev}"


# Inside a model revision folder (Bob, chat, 2026-11-03: "Move them into sub folders once" and presentations "in the
# Rev folder with all of the other rev files"): the model (GLB, zipped STEP, their pointers) at the top, then
# Takeoffs/ (what the shop builds from), Reports/ (checks and notes), Views/ (review pictures) and
# Presentations/P<nn>/ (lifelike renders, presentation GLB, Blender scene). File names keep the full
# <DOC-ID>-rev<X>... prefix. Drawing revision folders stay flat (DWG, PDF, DXF).
MODEL_TAKEOFFS = ("bom-model", "clamp-schedule", "cut-list-frame", "cut-list-piping", "fittings-by-spool",
                  "piping-mass", "spool-list", "weld-map")
MODEL_REPORTS = ("layout-note", "list-delta", "manifest", "pipe-support-calc", "routing-report",
                 "frame-calc-results", "instrument-rules")
_REV_PART = re.compile(r"-rev[A-Z]{1,2}(?P<rest>(?:-P\d{2})?(?:-.*)?)\.(?P<ext>[^.]+(?:\.[^.]+)*)$")


def model_subfolder(name: str) -> str:
    """Subfolder of a model revision folder that holds the filed file `name` ("" = the revision folder itself)."""
    m = _REV_PART.search(name.removesuffix(".drive"))
    rest = m.group("rest") if m else ""
    p = re.match(r"-(P\d{2})(?:-|$)", rest)
    if p:
        return f"Presentations/{p.group(1)}"
    if rest.startswith("-view-"):
        return "Views"
    kind = rest[1:]
    if kind in MODEL_TAKEOFFS:
        return "Takeoffs"
    if kind in MODEL_REPORTS:
        return "Reports"
    return ""


def model_rev_file(rev_dir: Path, name: str) -> Path:
    """A model revision's filed file `name`, in its subfolder (model_subfolder), or at the revision folder's top when
    it is still there (a record written before 2026-11-03, or a work build, which is flat)."""
    sub = model_subfolder(name)
    p = rev_dir / sub / name if sub else rev_dir / name
    return p if p.exists() or Path(f"{p}.drive").exists() or not (rev_dir / name).exists() else rev_dir / name
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


def _read_flat(path: Path) -> dict[str, str]:
    """Flat `key: value` lines, `#` comments; no PyYAML so every venv can import this module."""
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split(" #", 1)[0].strip() if not line.lstrip().startswith("#") else ""
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def _read_project_config(path: Path) -> dict[str, str]:
    """project.yaml as flat `key: value` lines (_read_flat)."""
    if not path.is_file():
        raise RuntimeError(f"{path} is missing: every project names itself there (keys {', '.join(PROJECT_KEYS)}; "
                           "harness/scripts/project_new.py)")
    out = _read_flat(path)
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
DESIGN_REPO = PROJECT_INFO["design_repo"]      # owner/name of this repo's origin (the job folder's repo)
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
# The work site is laid out as the published site (publish_site.py): the landing page at its root, tracker/ and
# mobile/ beside it, one shared assets/; so every link between the three works in the working copy too.
SITE_WORK = WORK / "site"
PORTAL_WORK = SITE_WORK / "tracker"      # build_portal.py working copy (the project tracker)
MOBILE_WORK = SITE_WORK / "mobile"       # build_portal.py --audience mobile working copy (Mobile Optimized)
LANDING_WORK = SITE_WORK                 # build_landing.py working copy (index.html at the site root)
# the work builds' shared assets/ is the parent of each --out (WORK / "assets" for the three above)
PORTALS = ISSUED / "Portals"             # filed portal revisions (was job/reviews/)
PORTAL_FILED = PORTALS / "project-portal"  # filed portal revisions and the shared data store
LANDING_FILED = PORTALS / "portal-landing"   # presentation site landing page revisions
MOBILE_FILED = PORTALS / "mobile-portal"     # Mobile Optimized: the tracker for phones (Bob, 2026-10-17)
INTERNAL_REVIEWS = REVIEWS / "01_Internal_Reviews"   # gate packages, review renders, frame-calc reports
PRESENTATIONS = CAD / "09_Presentation"  # presentation builders and portal assets (was job/cad/Presentations/)
SITE_CONFIG = PRESENTATIONS / "site.yaml"    # site settings: hidden_models (model IDs kept off the site), hidden_pages
PRESENTATION_RENDERS = PRESENTATIONS / "Renders"   # presentation stills kept with the source; the landing page's photo
EQUIPMENT_SELECTION = VENDOR_DATA        # vendor references, <category>/<tag>/ (Drive store)
# Records the project tracker shows (build_portal.py; a record that does not exist gives an empty section)
QUESTION_LOG = ADMIN / "07_Project_Controls" / "question-log.md"   # Q-nnnn snapshot of Agent-to-Agent Questions.md
HOLDS = CUSTOMER_REQUIREMENTS / "holds.md"                        # customer HOLDs (TR-23)
EQUIPMENT_CONCERNS = OPEN_ITEMS / "equipment-concerns.md"         # TR-02 concerns
FRAME_CALC_RESULTS = FRAME_CALC.parent / "frame-calc-results.md"  # frame_calc.py results (closeout.py step 2)
FRAME_CALC_REPORTS = INTERNAL_REVIEWS / "frame-calc-report"       # filed frame calc reports, frame-calc-report-rev<X>.html
LSD_DRAWINGS = DRAWINGS / "line-segment-diagram"   # the line segment diagram's filed revisions
PFD_DRAWINGS = DRAWINGS / "process-flow-diagram"   # the process flow diagram's filed revisions
# Filed model revisions as the presentation builders read them: MODELS, or CPME_PORTAL_MODELS_ROOT for a test or a
# fixture build (never a filing: the builders only read model revisions, TR-08)
PORTAL_MODELS = Path(os.environ["CPME_PORTAL_MODELS_ROOT"]) if os.environ.get("CPME_PORTAL_MODELS_ROOT") else MODELS
# presentation site checkout, a sibling of this repo: publishing target only (its own folder and repo; publish_site.py)
PRESENTATION_SITE = REPO.parent / SITE_REPO.rsplit("/", 1)[-1]

_PROJECT_NAMES = frozenset(n for n in set(globals()) - _BEFORE_PROJECT if not n.startswith("_"))
del _BEFORE_PROJECT
if not HAS_PROJECT:
    for _n in _PROJECT_NAMES:
        del globals()[_n]
    del _n
    PROJECT = None
    PROJECT_INFO = {}

# ---- which model the model tools work on (Linear CPM-155; Bob, chat, 2026-10-29). Default: the project's skid model
# (model_id in project.yaml), everything above unchanged. A job-level model is chosen by ID: model_iterate.py,
# model_file.py and the model checks take --model-id <ID> and --config <CFG>, or the environment variables
# CPME_MODEL_ID / CPME_MODEL_CONFIG. This module takes both flags out of sys.argv when it is imported and puts them in
# the environment, so every script accepts them and every check a script starts inherits them. An ID with a folder
# in the job-level models folder (JOB_MODELS, the typicals folder's 03_Working_Design/CAD/01_Master_Assembly/: models
# that serve every project in the job) is a
# job-level model; its configuration CFG (default B) is a document of its own, <MODEL-ID>-<CFG>, with its own
# letters. For a job-level model the names below are redirected (<typical> = TYPICAL, the job/Typical-* folder):
#     SKID_MODEL   JOB_MODELS/<MODEL-ID>/                         source (model.yaml, model.py, skidlib shim, exports)
#     SKID_BUILD   <typical>/03_Working_Design/Exports/build/<MODEL-ID>/<CFG>/      work build (gitignored)
#     FAST_BUILDS  <typical>/03_Working_Design/CAD/Fast_Builds/<MODEL-ID>/<CFG>/    fast builds (gitignored)
#     MODELS       <typical>/06_Issued_Revisions/Models/           filed; SKID_FILED = MODELS/<MODEL-ID>/, document
#                                                                  id MODEL_DOC_ID = <MODEL-ID>-<CFG>
#     DESIGN_RULES job/design-rules/   (a job-level model has no project level: its rules are the harness's and job's)
#     DATA         the list set named by `lists:` in the model's model.yaml (relative to the model folder)
JOB_MODELS = Path(os.environ["CPME_JOB_MODELS_ROOT"]) if os.environ.get("CPME_JOB_MODELS_ROOT") \
    else TYPICAL_WORKING / "CAD" / "01_Master_Assembly"   # CPME_JOB_MODELS_ROOT points a test run at a scratch folder
JOB_MODELS_WORK = JOB_WORK / "typical-models"   # gitignored caches of the typical-model library (step sizes, tag dumps)
JOB_MODELS_BUILD = TYPICAL_WORKING / "Exports" / "build"      # work builds, as a project's BUILD (gitignored)
JOB_MODELS_FAST = TYPICAL_WORKING / "CAD" / "Fast_Builds"     # fast builds, as a project's FAST_BUILDS (gitignored)
JOB_MODELS_FILED = JOB_ISSUED / "Models"


def _take_arg(flag: str) -> str | None:
    """Remove `flag value` or `flag=value` from sys.argv and return the value (None when absent)."""
    argv = sys.argv
    for i in range(1, len(argv)):
        a = argv[i]
        if a == flag and i + 1 < len(argv):
            v = argv[i + 1]
            del argv[i:i + 2]
            return v
        if a.startswith(flag + "="):
            del argv[i]
            return a.split("=", 1)[1]
    return None


for _flag, _env in (("--model-id", "CPME_MODEL_ID"), ("--config", "CPME_MODEL_CONFIG")):
    _v = _take_arg(_flag)
    if _v is not None:
        os.environ[_env] = _v.strip()
MODEL_ID_ARG = os.environ.get("CPME_MODEL_ID", "").strip()
MODEL_CONFIG_ARG = os.environ.get("CPME_MODEL_CONFIG", "").strip().upper()
JOB_MODEL: Path | None = None            # the job-level model folder, or None (the project's model)
MODEL_LEVEL = "project"
MODEL_INFO: dict[str, str] = {}          # the job-level model's model.yaml
MODEL_CONFIG = ""                        # the configuration of a job-level model ("" for a project model)
if MODEL_ID_ARG and not (HAS_PROJECT and MODEL_ID_ARG == PROJECT_INFO.get("model_id")):
    if not (JOB_MODELS / MODEL_ID_ARG / "model.yaml").is_file():
        raise RuntimeError(f"model {MODEL_ID_ARG!r} is not the project's model_id and has no "
                           f"{JOB_MODELS}/{MODEL_ID_ARG}/model.yaml")
    JOB_MODEL = JOB_MODELS / MODEL_ID_ARG
    MODEL_LEVEL = "job"
    MODEL_INFO = _read_flat(JOB_MODEL / "model.yaml")
    MODEL_CONFIG = MODEL_CONFIG_ARG or "B"
    SKID_MODEL_ID = MODEL_ID_ARG
    SKID_MODEL = JOB_MODEL
    MODEL_DOC_ID = f"{SKID_MODEL_ID}-{MODEL_CONFIG}"
    SKID_BUILD = JOB_MODELS_BUILD / SKID_MODEL_ID / MODEL_CONFIG
    FAST_BUILDS = JOB_MODELS_FAST / SKID_MODEL_ID / MODEL_CONFIG
    MODELS = JOB_MODELS_FILED
    SKID_FILED = MODELS / SKID_MODEL_ID
    DESIGN_RULES = JOB_DESIGN_RULES
    DATA = (JOB_MODEL / MODEL_INFO.get("lists", "lists")).resolve()
    RETIRED_MODEL_ID, RETIRED_MODEL = "", None
elif HAS_PROJECT:
    MODEL_DOC_ID = SKID_MODEL_ID         # a project model is one document: its MODEL-ID
HAS_MODEL = HAS_PROJECT or JOB_MODEL is not None   # a model to build or check (the project's, or a job-level one)


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


def skip_no_model(check: str) -> bool:
    """skip_no_project for a model check: False when there is a model to check, the project's or a job-level one
    (--model-id); else True after printing the not-checked line."""
    if HAS_MODEL:
        return False
    return skip_no_project(check)


def require_project(script: str) -> None:
    """For a script that works on a project: exit 2 with a plain message when the job has none yet."""
    if not HAS_PROJECT:
        print(f"{script}: REFUSED - {NO_PROJECT_HINT}", file=sys.stderr)
        raise SystemExit(2)


def require_model(script: str) -> None:
    """For a model tool: a job-level model (--model-id) needs no project; otherwise as require_project. A --config
    given for the project's model is refused (a project model has no configurations)."""
    if JOB_MODEL is None:
        require_project(script)
        if MODEL_CONFIG_ARG:
            print(f"{script}: REFUSED - --config {MODEL_CONFIG_ARG} needs a job-level model (--model-id <ID> with a "
                  f"folder in {JOB_MODELS}); the project's model has no configurations", file=sys.stderr)
            raise SystemExit(2)


def add_model_args(ap) -> None:
    """Document --model-id / --config on a script's argparse (this module has already taken them out of sys.argv)."""
    ap.add_argument("--model-id", dest="_model_id", metavar="ID",
                    help="job-level model (a folder in the job-level models folder); default: the project's model")
    ap.add_argument("--config", dest="_model_config", metavar="CFG",
                    help="configuration of a job-level model: B, X or its switch string (default B)")


def rel(p: Path) -> str:
    """Repo-relative path with forward slashes, for records and messages."""
    return Path(p).resolve().relative_to(REPO).as_posix()
