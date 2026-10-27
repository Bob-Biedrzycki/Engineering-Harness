"""job_new.py - make a new CPME job repo folder from the Engineering Harness master copy.

CPME practice (Bob, 2026-10-27): a job is a product line and its own repo. Its harness (harness/, .claude/agents,
.claude/skills, .claude/settings.json, CLAUDE.md, .github/, .gitattributes, the core of .gitignore; the list is
harness/harness-manifest.txt) is copied unchanged from the master; everything about the product lives in job/, which
this script starts with placeholders (`unknown` until Bob gives the value). The first project is made by
harness/scripts/project_new.py, here with --project or later in the new repo.

    python harness/scripts/job_new.py <folder> --name "<Job name>" --repo <owner/name>
           [--master PATH] [--from-job PATH] [--project Project-<nnnn-nn>-<TYPE>-<nnn>]

Writes, in <folder> (which must not exist, or be empty):
  * the master's harness-owned files (harness_sync.py), and the .gitignore core;
  * job/JOB.md (loaded by CLAUDE.md): job name, product, current project, focus, origin repo, Drive remote, where the
    design framework lives - placeholders except the name and the repo;
  * job/drive-store.yaml: Drive folder and remote `unknown`; the size, directory and exclude rules of --from-job's;
  * job/carryover-terms.txt: --from-job's banned terms plus its own [this-job] terms (harness/lib/carryover_terms.py);
  * job/components/README.md and component-register.csv (header only), from --from-job;
  * job/design-rules/README.md and job/knowledge/README.md stubs;
  * Agent-to-Agent Questions.md and Agent-to-Bob Questions.md: --from-job's rules headers, no entries;
  * README.md stub;
  * then harness/scripts/drive_store.py pointers in the new folder (the only writer of the .gitignore drive-store
    block), and project_new.py when --project is given.
It makes no git repo, no remote, no Drive folder and no Linear project: those are Bob's (skill job-bootstrap).

--master defaults to CPME_HARNESS_MASTER, else C:\\Users\\Bob\\Documents\\Engineering Harness; --from-job (the job
whose terms, Drive rules and record headers are carried) defaults to the repo this script runs in.
Exit codes: 0 created, 1 created but a follow-on step failed or the carry-over guard found hits (listed), 2 refused.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

HERE_REPO = next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists())
sys.path.insert(0, str(HERE_REPO / "harness" / "lib"))
sys.path.insert(0, str(HERE_REPO / "harness" / "scripts"))
import carryover_terms as CT  # noqa: E402
import harness_sync as HS  # noqa: E402

REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
PROJECT_RE = re.compile(r"^Project-\d+-\d+-[A-Z]+-\d{3}$")
QUESTION_FILES = {"Agent-to-Agent Questions.md": ("## Entries", "Agent-to-Agent Questions"),
                  "Agent-to-Bob Questions.md": ("## Open", "Agent-to-Bob Questions")}


def job_md(name: str, repo: str, project: str | None) -> str:
    current = (f"**`{project}`** (`<project>` means `job/{project}`; its identity is in `<project>/project.yaml`)."
               if project else "none yet; make the first with `harness/scripts/project_new.py` (skill job-bootstrap).")
    return f"""# This job: {name}

Loaded by CLAUDE.md (`@job/JOB.md`). CLAUDE.md holds the rules for every CPME skid job; this file holds only what is
true of this job and its current project. Written by harness/scripts/job_new.py; `unknown` marks a value Bob has not
given yet (hard rule 1).

**The job.** This repo is the **{name}** job. Product: `unknown` (what this skid is and what it serves). What it holds
and which rules apply to which lines: `unknown` (the job's knowledge in `job/knowledge/`, its rules in
`job/design-rules/`, PIPE-SVC-001). How it is designed, intake to gates (the design framework): `unknown` (write it in
`job/knowledge/`). The job's review addendum: `unknown`. How the Todd Requirements rows are met on this job: `unknown`.

**Origin repo:** `https://github.com/{repo}.git`. **Google Drive store:** `job/drive-store.yaml` (folder `unknown`),
rclone remote `unknown`. **Linear project:** `unknown`.

**Current project:** {current}

**Current focus:** `unknown` (Bob sets it).

**Presentation site:** none (`site_repo` in the project's `project.yaml` is `unknown`).
"""


def drive_store_yaml(name: str, src: Path) -> str:
    """The Drive-store config: folder and remote unknown; the rules (size, directories, exclude) from --from-job."""
    import yaml
    cfg = (yaml.safe_load(src.read_text(encoding="utf-8")) or {}) if src.is_file() else {}
    rules = {"large_file_bytes": cfg.get("large_file_bytes", 5242880),
             "directories": cfg.get("directories") or {},
             "exclude": cfg.get("exclude") or [".git", "harness/tools", ".venv", "job/_work", "job/*/_work"]}
    dirs = "\n".join(f"  {d}: [{', '.join(str(e) for e in exts)}]" for d, exts in rules["directories"].items())
    return f"""# Drive store for the {name} job: ONE store shared by the job library and every project folder (CPME practice;
# Bob, 2026-09-28: large files use Google Drive as the database with pointers referencing this folder).
# Large files live in the Google Drive folder below at the same path they have in the repo; git holds a pointer per
# file (<file>.drive), written by harness/scripts/drive_store.py, which also keeps the managed block in .gitignore.
# A directory key may use `*` for one folder name. Edit this file, then run `drive_store.py pointers`.
# The local path of the Drive folder is machine-specific and is not stored here: pass --root, set CPME_DRIVE_ROOT,
# or write it to job/_work/drive-root.txt (gitignored).

# The job's Drive folder and its rclone remote: unknown until Bob makes them (skill job-bootstrap).
drive_folder_url: unknown
drive_folder_id: unknown
rclone_remote: unknown

# Large file: any file at or above this size, anywhere in the repo, goes to the Drive store.
large_file_bytes: {int(rules["large_file_bytes"])}

# Large directories: under each, every file with one of these extensions goes to the Drive store whatever its size.
directories:
{dirs}

# Never scanned (gitignored working copies and tool environments).
exclude: [{', '.join(str(e) for e in rules["exclude"])}]
"""


def question_file(src: Path, title: str, heading: str, name: str) -> str:
    """--from-job's question file: its rules header up to the entries heading, the title naming the new job, no
    entries."""
    text = src.read_text(encoding="utf-8") if src.is_file() else ""
    lines = text.splitlines()
    if heading in lines:
        lines = lines[:lines.index(heading) + 1]
    else:
        lines = [f"# {title}", "", heading]
    lines[0] = f"# {title} ({name} job)"
    return "\n".join(lines) + "\n\nNone yet.\n"


def register_header(src: Path) -> str:
    if src.is_file():
        first = src.read_text(encoding="utf-8-sig").splitlines()[:1]
        if first and first[0].strip():
            return first[0].strip() + "\n"
    import components   # harness/lib/components.py COLUMNS (needs this repo's repo_paths, which imports with no project)
    return ",".join(components.COLUMNS) + "\n"


def readme(name: str, repo: str) -> str:
    return f"""# CPME Skid Design Harness: {name} job

AI-assisted design environment for CPME skids. This repo is the {name} job (`origin`
https://github.com/{repo}); each project (order) in it is a folder under `job/`. The agent drafts and checks; the
engineer approves through pull requests.

Start with `CLAUDE.md` and `job/JOB.md`. Roles are in `.claude/agents/`. The harness (everything CLAUDE.md, `harness/`,
`.claude/agents`, `.claude/skills` and `.github/` hold) is the same in every CPME job and comes from the Engineering
Harness master copy: `harness/scripts/harness_sync.py check .` compares it, `pull .` updates it.

## Setup and status

| Item | Value |
|---|---|
| Current project | none yet (`harness/scripts/project_new.py`) |
| GitHub | `{repo}`, the job's one repo (TR-09) |
| Linear | `unknown` |
| Google Drive store | `job/drive-store.yaml` (folder `unknown`) |
| Presentation site | none |
"""


STUBS = {
    "job/design-rules/README.md": """# Job design rules (level 2: every project in the {name} job)

Rules that hold for every project in this job sit here, between the harness rules (`harness/design-rules/`, every CPME
job) and each project's own scope and values (`<project>/01_Design_Basis/05_Standards_Specifications/Design_Rules/`).
A lower level narrows the one above it (harness/lib/rule_scope.py). A new rule or value is asked of Bob first, with its
level (CLAUDE.md hard rule 11; skill design-rule-add). None yet.
""",
    "job/knowledge/README.md": """# Job knowledge ({name} job)

What this job's product is, what it holds, which rules apply to which lines, and how it is designed (the design
framework, intake to gates); the job's review addendum and its Todd Requirements notes. `job/JOB.md` names each file.
None yet.
""",
}


def _guard_hits(folder: Path) -> list[str]:
    sys.path.insert(0, str(HERE_REPO / "harness" / "tests"))
    import test_no_carryover as G   # the same scan the new job's own test makes
    return G.hits(folder)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("folder", type=Path, help="the new job repo folder (must not exist, or be empty)")
    ap.add_argument("--name", required=True, help='job name, e.g. "Widget Skids"')
    ap.add_argument("--repo", required=True, help="GitHub owner/name of the job's origin")
    ap.add_argument("--master", type=Path, default=None, help="master copy (default CPME_HARNESS_MASTER or "
                                                                f"{HS.DEFAULT_MASTER})")
    ap.add_argument("--from-job", type=Path, default=HERE_REPO, help="job whose terms and rules are carried "
                                                                      "(default this repo)")
    ap.add_argument("--project", help="also make this first project, Project-<nnnn-nn>-<TYPE>-<nnn>")
    a = ap.parse_args(argv)
    master = a.master or HS.default_master()
    folder: Path = a.folder
    name = a.name.strip()

    def refuse(msg: str) -> int:
        print(f"job_new: REFUSED - {msg}", file=sys.stderr)
        return 2

    if not name or any(c in name for c in "\r\n`"):
        return refuse("--name is blank or holds a line break or backtick")
    if not REPO_RE.match(a.repo):
        return refuse(f"--repo {a.repo!r} is not <owner>/<name>")
    if a.project and not PROJECT_RE.match(a.project):
        return refuse(f"--project {a.project!r} is not Project-<nnnn-nn>-<TYPE>-<nnn>")
    if folder.exists() and (not folder.is_dir() or any(folder.iterdir())):
        return refuse(f"{folder} exists and is not an empty folder; a job folder is never overwritten")
    if not (master / HS.MANIFEST_REL).is_file() or not (master / "CLAUDE.md").is_file():
        return refuse(f"master {master} holds no harness (no CLAUDE.md or {HS.MANIFEST_REL}); "
                      "fill it with harness_sync.py seed --master <folder>")
    if not a.from_job.is_dir():
        return refuse(f"--from-job {a.from_job} is not a folder")
    if folder.resolve() in (master.resolve(), a.from_job.resolve()):
        return refuse(f"{folder} is the master or the --from-job folder")

    folder.mkdir(parents=True, exist_ok=True)
    m = HS.read_manifest(master)
    keys = sorted(HS.owned_files(master, m)) + [rel + HS.CORE_SUFFIX for rel in m.core if (master / rel).is_file()]
    for k in keys:
        HS.copy_owned(k, master, folder, core_with_block=False)
    print(f"job_new: copied {len(keys)} harness-owned file(s) from {master}")

    src = a.from_job
    terms_header = "\n".join([
        f"# Carry-over guard terms for the {name} job (harness/lib/carryover_terms.py; harness/tests/test_no_carryover.py).",
        "# Written by harness/scripts/job_new.py from the job it was made from: the earlier jobs' terms are [banned].",
        "# Every pattern and sample is written REVERSED, so this file carries none of the terms."])
    files = {
        "job/JOB.md": job_md(name, a.repo, a.project),
        "job/drive-store.yaml": drive_store_yaml(name, src / "job" / "drive-store.yaml"),
        "job/carryover-terms.txt": CT.next_job_text(CT.load(src / "job" / "carryover-terms.txt"), terms_header),
        "job/components/component-register.csv": register_header(src / "job" / "components" / "component-register.csv"),
        "README.md": readme(name, a.repo),
        **{k: v.format(name=name) for k, v in STUBS.items()},
        **{f: question_file(src / f, title, heading, name) for f, (heading, title) in QUESTION_FILES.items()},
    }
    comp_readme = src / "job" / "components" / "README.md"
    if comp_readme.is_file():
        files["job/components/README.md"] = comp_readme.read_text(encoding="utf-8")
    for rel, text in files.items():
        p = folder / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")
        print(f"job_new: wrote {rel}")

    rc = 0
    py = sys.executable
    r = subprocess.run([py, str(folder / "harness" / "scripts" / "drive_store.py"), "pointers"], cwd=folder,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(f"job_new: drive_store.py pointers exit {r.returncode}: {(r.stdout or r.stderr).strip().splitlines()[-1:]}")
    rc |= 1 if r.returncode else 0
    if a.project:
        r = subprocess.run([py, str(folder / "harness" / "scripts" / "project_new.py"), a.project], cwd=folder,
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        print(f"job_new: project_new.py {a.project} exit {r.returncode}: {(r.stdout or r.stderr).strip()}")
        rc |= 1 if r.returncode else 0
    found = _guard_hits(folder)
    if found:
        print(f"job_new: WARN - {len(found)} carry-over hit(s) in the new job (its harness or the files carried):")
        for h in found[:50]:
            print(f"  {h}")
        rc |= 1
    print(f"job_new: {'created' if not rc else 'created, with the findings above'} {folder}; next: git init, origin "
          f"https://github.com/{a.repo}.git, the Drive folder and the Linear project (Bob; skill job-bootstrap)")
    return rc


if __name__ == "__main__":
    sys.exit(main())
