"""project_layout.py - every project folder still has every folder of the CPME project template.

Bob, chat, 2026-10-26: every project is filed exactly the same way, from the full tree in
harness/templates/project-folder/ (harness/scripts/project_new.py copies it). This check reports MISSING template
folders of job/Project-*/ folders only. It reports and never blocks (CLAUDE.md: checks report): exit 0 always.
It does not look for extra folders, nor at the typicals folder: harness/checks/folder_layout.py does that (every
folder under job/ named by the template, a guide or job/folder-register.csv; REVW-001, 2026-11-23).

  .\\harness\\tools\\venv\\Scripts\\python.exe harness\\checks\\project_layout.py
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists())
TEMPLATE = REPO / "harness" / "templates" / "project-folder"


def missing(project: Path) -> list[str]:
    want = sorted(p.relative_to(TEMPLATE).as_posix() for p in TEMPLATE.rglob("*") if p.is_dir())
    return [d for d in want if not (project / d).is_dir()]


def main() -> int:
    projects = sorted(p for p in (REPO / "job").glob("Project-*") if p.is_dir())
    if not TEMPLATE.is_dir():
        print(f"project_layout: WARN - template missing at {TEMPLATE.relative_to(REPO).as_posix()}")
        return 0
    if not projects:
        print("project_layout: PASS - not checked: no project yet")
        return 0
    gaps = {p.name: missing(p) for p in projects}
    n = sum(len(v) for v in gaps.values())
    print(f"project_layout: {'PASS' if not n else 'WARN'} - {len(projects)} project folder(s), {n} template folder(s) "
          f"missing (missing folders only; extra folders are folder_layout.py's)")
    for name, dirs in gaps.items():
        for d in dirs:
            print(f"   {name}/{d}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
