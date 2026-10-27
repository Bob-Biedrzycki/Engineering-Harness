"""project_new.py - create a project folder under job/ from the CPME project template.

Bob, chat, 2026-10-26: every project is filed exactly the same way, with the full folder tree from day one,
"so it is automatically known that this is exactly how we are going to file". A job is the product line (this
repo); a project is one order in it, folder `Project-<Project Number>-<Type>-<Top Level Version>`. The Project Number in the folder name is the
project code, e.g. 1234-01; `project_number` in project.yaml is CPME's short order number, e.g. 1234-1.

The tree is harness/templates/project-folder/ (README_Project_Guide.md there explains every folder). This script
copies it, then writes the project's project.yaml with every key `unknown` except the IDs it can derive from the name.
The Google Drive store is the job's (job/drive-store.yaml), so a project has none: fill project.yaml (skill job-bootstrap). It never overwrites an existing folder.

Does not import repo_paths: it needs nothing from a project, and this is what makes the first one.

Run from the repo root:
  .\\harness\\tools\\venv\\Scripts\\python.exe harness\\scripts\\project_new.py Project-1234-01-ABC-001
  ... --root <folder>     create under another folder (a test run); default job/
Exit codes: 0 created, 2 refused.
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

REPO = next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists())
TEMPLATE = REPO / "harness" / "templates" / "project-folder"
NAME = re.compile(r"^Project-(?P<number>\d+-\d+)-(?P<type>[A-Z]+)-(?P<version>\d{3})$")


def project_yaml(m: re.Match) -> str:
    pid = f"{m['number']}-{m['type']}-{m['version']}"
    return f"""# Project identity: the one place a project names itself (TR-09; project folders, Bob 2026-10-26).
# A job is the product line and its repo; a project is one order in it, this folder (Bob, chat, 2026-10-26; TR-09).
# harness/lib/repo_paths.py reads this file; harness code takes every ID from here, never as literals.
# Flat `key: value` lines only (read without PyYAML, so the cadgen venv can import it).
# Values are exactly as on the project's records; do not normalize. `unknown` = not received yet.

project_id: {pid}                  # folder name without "Project-" (Bob, chat, 2026-10-26)
project_number: unknown
project_code: {m['number']}
customer: unknown
location: unknown
skid_name: unknown
skid_title: unknown
skid_description: unknown
model_id: {pid}-MODEL
pid_doc_id: {pid}-PID-001
retired_model_id:
design_repo: unknown
site_repo: unknown
linear_project: unknown
drive_remote: unknown
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("name", help="Project-<Project Number>-<Type>-<Top Level Version>, e.g. Project-1234-01-ABC-001")
    ap.add_argument("--root", type=Path, default=REPO / "job", help="parent folder (default job/)")
    a = ap.parse_args()
    m = NAME.match(a.name)
    if not m:
        print(f"REFUSED: {a.name!r} is not Project-<nnnn-nn>-<TYPE>-<nnn> (e.g. Project-1234-01-ABC-001)", file=sys.stderr)
        return 2
    dst = a.root / a.name
    if dst.exists():
        print(f"REFUSED: {dst} already exists; a project folder is never overwritten", file=sys.stderr)
        return 2
    if not TEMPLATE.is_dir():
        print(f"REFUSED: template missing at {TEMPLATE}", file=sys.stderr)
        return 2
    shutil.copytree(TEMPLATE, dst)
    (dst / "project.yaml").write_text(project_yaml(m), encoding="utf-8")
    n = sum(1 for p in dst.rglob("*") if p.is_dir())
    print(f"created {dst} ({n} folders); next: fill project.yaml (skill job-bootstrap)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
