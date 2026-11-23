"""folder_layout - every folder under job/ is named by the project template, a guide, or job/folder-register.csv.

REVW-001 (2026-11-23, CAPA PA-2; Bob, chat, 2026-11-23: "clean up all of the little messes from deviations from the
intended workflow, as well as address preventative measures so they dont happen again"). Sessions made new folders,
names and counters during plan set work and nothing saw it: project_layout.py reports only MISSING template folders,
filed_layout.py looks only inside filed document folders, and CI runs on a clean checkout where the gitignored working
folders do not exist. This check walks the DISK (not git), so it sees tracked, gitignored and untracked folders alike.

A folder is named when it is
  * a folder of the project template tree (harness/templates/project-folder/), inside a job/Project-* folder;
  * a documented child of a template folder (README_Project_Guide.md in that template; GUIDE_CHILDREN below): a
    model source folder, a COMP-nnnn_* component, a <tag>_<Maker>_<Model> vendor folder, a REVW-nnn_ / CR-nnn_ review,
    a filed document folder under 06_Issued_Revisions/Drawings, /Models or /Portals, an ISS-nnn_ package, a
    calculation's Inputs / Working / Checked_Results;
  * a folder the CLAUDE.md "Repository map" names at job level or in the typicals folder (MAP below, kept short);
  * covered by a row of job/folder-register.csv (job-owned): `path` is repo-relative with forward slashes; `*`
    matches within one folder name (`job/components/COMP-*`), and a trailing `/**` means "this folder and
    everything below it" (not descended).
The walk does not descend below a `/**` row, a documented child above, a numbered build folder (rp.BUILD_NAME), a
<DOC-ID>-rev<X> folder, .git, __pycache__, node_modules or a Python venv. The first unnamed folder of a branch is
reported and the walk does not go below it.

    .\\harness\\tools\\venv\\Scripts\\python.exe harness\\checks\\folder_layout.py
    .\\harness\\tools\\venv\\Scripts\\python.exe harness\\checks\\folder_layout.py --paths-file P

--paths-file P (one repo-relative path per line, `#` comments; what track.py save passes): checks only the folder
chain of each listed path (and, for a listed folder that exists, the folders below it). A path not on disk yet is
taken as a file, so CI can check paths that do not exist in its checkout.

First line: `folder_layout: PASS|FAIL - ...`; then one line per unnamed folder (tracked, ignored or untracked);
register rows that match nothing on disk are notes (`stale register row`), as are rows with status `open`.
Exit 0 PASS, 1 FAIL (a repo-integrity check: run_checks.sh HARD_FAIL_CHECKS), 3 ERROR (the register is unreadable).
No job/folder-register.csv (a job not seeded yet, or the master): `PASS - not checked`, exit 0 (First Principle 5).
"""
from __future__ import annotations

import argparse
import csv
import io
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from fnmatch import fnmatchcase
from pathlib import Path

HERE_REPO = next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists())
sys.path.insert(0, str(HERE_REPO / "harness" / "lib"))
import repo_paths as rp  # noqa: E402  (BUILD_NAME only; every path here is relative to the root a caller passes)

NAME = "folder_layout"
REGISTER_REL = "job/folder-register.csv"
TEMPLATE_REL = "harness/templates/project-folder"
COLUMNS = ("path", "level", "holds", "written_by", "tracked", "status", "basis", "added")
LEVELS = {"job", "typical", "project", "root"}
STATUSES = {"active", "legacy-kept", "superseded-kept", "open"}
TRACKED = {"tracked", "ignored"}
SKIP_NAMES = {".git", "__pycache__", "node_modules", ".venv", "venv", "venv-cad", "venv-cadgen"}
REV_FOLDER = re.compile(r"^.+-rev[A-Z]{1,2}$")          # a <DOC-ID>-rev<X> folder (rp.rev_folder)
# README_Project_Guide.md:64 - a vendor folder per tag, <tag>_<Maker>_<Model> (no spaces)
VENDOR_TAG = re.compile(r"^[A-Za-z0-9.-]+_[^\s_/][^\s/]*_[^\s/]+$")

# Documented children of template folders, relative to a job/Project-* or job/Typical-* folder; each covers its
# folder and everything below (filed_layout.py, component_register.py and the tools that write them look inside).
# Source: harness/templates/project-folder/README_Project_Guide.md, the line given.
GUIDE_CHILDREN = (
    ("02_Engineering/*/Inputs", 48), ("02_Engineering/*/Working", 48), ("02_Engineering/*/Checked_Results", 48),
    ("03_Working_Design/CAD/01_Master_Assembly/*", 51),
    ("03_Working_Design/CAD/05_Purchased_Components/COMP-*", 53),
    ("04_Vendor_Data/*/" + "<tag>_<Maker>_<Model>", 64),
    ("05_Reviews_Changes/*/REVW-[0-9][0-9][0-9]_*", 65), ("05_Reviews_Changes/*/CR-[0-9][0-9][0-9]_*", 65),
    ("06_Issued_Revisions/Drawings/*", 67), ("06_Issued_Revisions/Models/*", 68),
    ("06_Issued_Revisions/Portals/*", 69), ("06_Issued_Revisions/ISS-[0-9][0-9][0-9]_*", 71),
)
# What the CLAUDE.md "Repository map" names at job level (job/ lines: knowledge/ with todd-notes/, design-rules/,
# components/ with one COMP-nnnn_<Maker>_<Model>/ per part, Typical-<ID prefix>/, Project-<code>-<TYPE>-<nnn>/) and in
# the typicals folder ("03_Working_Design/ (CAD/01_Master_Assembly ..., CAD/06_Drawings/Generators, CAD/09_Presentation,
# PID/02_Tag_Lists), 06_Issued_Revisions/ (Drawings/, Models/), _work/"). (path, covers everything below)
MAP = (
    ("job/knowledge", False), ("job/knowledge/todd-notes", False), ("job/design-rules", False),
    ("job/components", False), ("job/components/COMP-*", True),
    ("job/Project-*", False), ("job/Typical-*", False),
    ("job/Typical-*/03_Working_Design", False), ("job/Typical-*/03_Working_Design/CAD", False),
    ("job/Typical-*/03_Working_Design/CAD/01_Master_Assembly", False),
    ("job/Typical-*/03_Working_Design/CAD/06_Drawings", False),
    ("job/Typical-*/03_Working_Design/CAD/06_Drawings/Generators", False),
    ("job/Typical-*/03_Working_Design/CAD/09_Presentation", False),
    ("job/Typical-*/03_Working_Design/PID", False), ("job/Typical-*/03_Working_Design/PID/02_Tag_Lists", False),
    ("job/Typical-*/06_Issued_Revisions", False), ("job/Typical-*/06_Issued_Revisions/Drawings", False),
    ("job/Typical-*/06_Issued_Revisions/Models", False), ("job/Typical-*/_work", False),
)


class RegisterError(ValueError):
    """job/folder-register.csv cannot be read as a register."""


@dataclass
class Pattern:
    """A folder pattern: one glob (or regex) per folder name, and whether it covers everything below."""
    text: str
    segs: list
    deep: bool

    @classmethod
    def parse(cls, text: str) -> "Pattern":
        t = text.strip().replace("\\", "/").strip("/")
        deep = t.endswith("/**") or t == "**"
        if deep:
            t = t[:-3].rstrip("/") if t != "**" else ""
        segs = [VENDOR_TAG if s == "<tag>_<Maker>_<Model>" else s for s in t.split("/") if s]
        return cls(text, segs, deep)

    def match(self, parts: list[str]) -> bool:
        """True when this pattern names the folder `parts` (or, when deep, one of its parents)."""
        n = len(self.segs)
        if len(parts) < n or (len(parts) > n and not self.deep):
            return False
        return all(s.fullmatch(p) if isinstance(s, re.Pattern) else fnmatchcase(p, s)
                   for s, p in zip(self.segs, parts))


@dataclass
class Row:
    line: int
    values: dict
    pattern: Pattern = field(init=False)

    def __post_init__(self):
        self.pattern = Pattern.parse(self.values["path"])

    @property
    def path(self) -> str:
        return self.values["path"]


def read_register(text: str) -> list[Row]:
    """The register's rows; RegisterError on a missing column, an empty path, a duplicate path or an unknown level,
    status or tracked value."""
    rd = csv.DictReader(io.StringIO(text))
    missing = [c for c in COLUMNS if c not in (rd.fieldnames or [])]
    if missing:
        raise RegisterError(f"{REGISTER_REL} lacks column(s) {', '.join(missing)} (header: {', '.join(COLUMNS)})")
    rows, seen = [], set()
    for i, r in enumerate(rd, start=2):
        v = {c: (r.get(c) or "").strip() for c in COLUMNS}
        if not v["path"]:
            raise RegisterError(f"{REGISTER_REL} line {i}: empty path")
        if v["path"] in seen:
            raise RegisterError(f"{REGISTER_REL} line {i}: path {v['path']!r} is listed twice")
        seen.add(v["path"])
        for col, allowed in (("level", LEVELS), ("status", STATUSES), ("tracked", TRACKED)):
            if v[col] not in allowed:
                raise RegisterError(f"{REGISTER_REL} line {i}: {col} {v[col]!r} is not one of {', '.join(sorted(allowed))}")
        rows.append(Row(i, v))
    return rows


def template_dirs(root: Path) -> set[str]:
    """Folder paths of the project template, relative to a project folder (the root's template, else this repo's)."""
    t = root / TEMPLATE_REL
    if not t.is_dir():
        t = HERE_REPO / TEMPLATE_REL
    return {p.relative_to(t).as_posix() for p in t.rglob("*") if p.is_dir()}


class Namer:
    """Says whether a job/ folder is named, and whether the walk stops at it."""

    def __init__(self, root: Path, rows: list[Row]):
        self.template = template_dirs(root)
        self.rows = rows
        self.builtin = [(Pattern.parse(p + ("/**" if deep else "")), "map") for p, deep in MAP]
        for scope in ("job/Project-*", "job/Typical-*"):
            self.builtin += [(Pattern.parse(f"{scope}/{p}/**"), f"guide:{ln}") for p, ln in GUIDE_CHILDREN]

    def named(self, rel: str) -> tuple[str, bool] | None:
        """(what names it, stop here) for the repo-relative folder `rel`, or None when nothing names it."""
        parts = rel.split("/")
        stop_name = bool(rp.BUILD_NAME.match(parts[-1]) or REV_FOLDER.match(parts[-1]))
        if len(parts) >= 3 and parts[0] == "job" and parts[1].startswith("Project-") \
                and "/".join(parts[2:]) in self.template:
            return "template", stop_name
        for pat, src in self.builtin:
            if pat.match(parts):
                return src, pat.deep or stop_name
        for row in self.rows:
            if row.pattern.match(parts):
                return f"register:{row.path}", row.pattern.deep or stop_name
        return None


def skipped(d: Path) -> bool:
    return d.name in SKIP_NAMES or (d / "pyvenv.cfg").is_file()


def walk(root: Path, namer: Namer, start: str = "job") -> tuple[int, list[str]]:
    """(folders checked, unnamed folders) below `start` (repo-relative), first unnamed folder of each branch only."""
    checked, unnamed = 0, []
    top = root / start
    if not top.is_dir():
        return 0, []
    for dirpath, dirs, _ in os.walk(top):
        here = Path(dirpath)
        keep = []
        for d in sorted(dirs):
            p = here / d
            if skipped(p):
                continue
            rel = p.relative_to(root).as_posix()
            checked += 1
            hit = namer.named(rel)
            if hit is None:
                unnamed.append(rel)
            elif not hit[1]:
                keep.append(d)
        dirs[:] = keep
    return checked, unnamed


def norm(p: str) -> str:
    q = p.strip().replace("\\", "/")
    while q.startswith("./"):
        q = q[2:]
    return q.rstrip("/")


def unnamed_for_paths(root: Path, paths: list[str], namer: Namer) -> list[tuple[str, str]]:
    """[(listed path, the unnamed folder it is in or holds)] for the listed repo-relative paths. Only folders under
    job/ are checked; a path not on disk is taken as a file."""
    out = []
    for raw in paths:
        rel = norm(raw)
        if not rel.startswith("job/"):
            continue
        is_dir = (root / rel).is_dir()
        parts = rel.split("/")
        chain = ["/".join(parts[:i]) for i in range(2, len(parts) + (1 if is_dir else 0))]
        bad, stopped = None, False
        for d in chain:
            hit = namer.named(d)
            if hit is None:
                bad = d
                break
            if hit[1]:
                stopped = True
                break
        if bad:
            out.append((raw.strip(), bad))
        elif is_dir and not stopped:
            out += [(raw.strip(), u) for u in walk(root, namer, rel)[1]]
    return out


def git_state(root: Path, rel: str) -> str:
    """tracked (git holds a file below it), ignored, or untracked; `not a git checkout` when git cannot say."""
    try:
        r = subprocess.run(["git", "-C", str(root), "ls-files", "--", rel], capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        if r.returncode != 0:
            return "not a git checkout"
        if r.stdout.strip():
            return "tracked"
        r = subprocess.run(["git", "-C", str(root), "check-ignore", "-q", "--", rel + "/"], capture_output=True)
        return {0: "ignored", 1: "untracked"}.get(r.returncode, "not a git checkout")
    except OSError:
        return "not a git checkout"


def stale_rows(root: Path, rows: list[Row]) -> list[Row]:
    """Register rows whose path (without a trailing /**) matches nothing on disk."""
    out = []
    for row in rows:
        base = "/".join(s.pattern if isinstance(s, re.Pattern) else s for s in row.pattern.segs)
        if not base or not any(root.glob(base)):
            out.append(row)
    return out


def load(root: Path, register_text: str | None = None) -> list[Row] | None:
    """The register's rows (from `register_text` when given, else the file), or None when there is none."""
    if register_text is None:
        f = root / REGISTER_REL
        if not f.is_file():
            return None
        register_text = f.read_text(encoding="utf-8-sig")
    return read_register(register_text)


def main(argv=None, root: Path | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--paths-file", help="check only the folders these repo-relative paths are in (track.py save)")
    a = ap.parse_args(argv)
    root = Path(root or HERE_REPO)
    try:
        rows = load(root)
    except (RegisterError, OSError, csv.Error) as e:
        print(f"{NAME}: ERROR - {e}")
        return 3
    if rows is None:
        no_project = not any(p.is_dir() for p in (root / "job").glob("Project-*"))
        print(f"{NAME}: PASS - not checked: {'no project yet, ' if no_project else ''}no {REGISTER_REL}")
        return 0
    namer = Namer(root, rows)
    if a.paths_file:
        paths = [ln for ln in Path(a.paths_file).read_text(encoding="utf-8-sig").splitlines()
                 if ln.strip() and not ln.lstrip().startswith("#")]
        bad = unnamed_for_paths(root, paths, namer)
        print(f"{NAME}: {'FAIL' if bad else 'PASS'} - {len(paths)} path(s) checked, {len(bad)} in a folder nothing "
              f"names (the template, a guide or {REGISTER_REL})")
        for p, d in bad:
            print(f"  {p}: in {d}/ ({git_state(root, d)})")
        return 1 if bad else 0
    checked, unnamed = walk(root, namer)
    print(f"{NAME}: {'FAIL' if unnamed else 'PASS'} - {checked} folder(s) checked, {len(unnamed)} not named by the "
          f"template, a guide or {REGISTER_REL}")
    for d in unnamed:
        print(f"  {d}/ ({git_state(root, d)})")
    for row in stale_rows(root, rows):
        print(f"  note: stale register row (matches nothing on disk): {row.path} (line {row.line})")
    for row in rows:
        if row.values["status"] == "open":
            print(f"  note: open: {row.path} - {row.values['basis']}")
    return 1 if unnamed else 0


if __name__ == "__main__":
    sys.exit(main())
