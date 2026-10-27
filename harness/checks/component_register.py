"""component_register - the component registers agree with the component folders and the files they name.

Bob, chat, 2026-10-26: components follow the same requirements as before (cut sheet, STEP file, ...), with a
components register recording where the information was obtained and the component details. Two registers, same
columns (job/components/README.md; read through harness/lib/components.py):

    job/components/component-register.csv                                              (every project in the job)
    <project>/03_Working_Design/CAD/05_Purchased_Components/component-register.csv     (this project's one-off parts)

Per register: the header holds every register column; every row has a COMP-nnnn id, a status of current or
superseded, and an (id, revision) pair used once; an id has at most one current row; an id is in one library only;
every file the row names (cut_sheet_file, vendor_step_file, cpme_step_file; relative to the register's folder) exists
in the working tree or as a Drive store pointer, and its sha256 matches vendor_step_sha256 / cpme_step_sha256 when
given; every COMP-nnnn_* folder has a row for its id in its own library's register. `unknown` or blank = not named.

Reports, never blocks (CLAUDE.md: checks report; a design-record finding, not a repo-integrity one, so CI shows it as
a warning). Exit contract (harness/checks/README.md): 0 PASS, 1 with the "component_register: FAIL" summary =
findings, 3 ERROR (a register could not be read). No rows and no folders yet = PASS.

    .\\harness\\tools\\venv\\Scripts\\python.exe harness\\checks\\component_register.py
"""
from __future__ import annotations

import csv
import hashlib
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists()) / "harness" / "lib"))
import repo_paths as rp  # noqa: E402
import components as C  # noqa: E402


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _where(lib: C.Library) -> str:
    try:
        return rp.rel(lib.register)
    except ValueError:
        return str(lib.register)


def findings(libs: list[C.Library] | None = None) -> tuple[int, int, list[str]]:
    """(rows, folders, findings) over the libraries (default: job, then project)."""
    libs = libs or C.libraries()
    out: list[str] = []
    n_rows = 0
    library_of: dict[str, set[str]] = defaultdict(set)
    for lib in libs:
        where = _where(lib)
        if not lib.register.is_file():
            out.append(f"{where}: register missing (header: job/components/component-register.csv)")
            continue
        header, rows = C.read_register(lib.register)
        missing = [c for c in C.COLUMNS if c not in header]
        if missing:
            out.append(f"{where}: header lacks {', '.join(missing)}")
        pairs: Counter = Counter()
        current: Counter = Counter()
        for i, raw in enumerate(rows, 2):   # line 1 is the header
            n_rows += 1
            r = {**{k: (v or "").strip() for k, v in raw.items() if k is not None}, "_library": lib.level, "_root": lib.root}
            cid, rev, status = r.get("component_id", ""), r.get("revision", ""), r.get("status", "").lower()
            tag = f"{where}:{i} {cid or '(no id)'} rev {rev or '?'}"
            if not C.ID_RE.match(cid):
                out.append(f"{tag}: component_id is not COMP-nnnn")
            if not rev:
                out.append(f"{tag}: revision blank")
            if status not in C.STATUSES:
                out.append(f"{tag}: status {r.get('status', '')!r} is not one of {', '.join(C.STATUSES)}")
            pairs[(cid, rev)] += 1
            if status == "current":
                current[cid] += 1
            if cid:
                library_of[cid].add(lib.level)
            for col, sha_col in C.FILE_COLUMNS:
                p = C.resolve(r, r.get(col, ""))
                if p is None:
                    continue
                want = (r.get(sha_col, "") if sha_col else "").lower()
                want = "" if want == "unknown" else want
                if p.is_file():
                    if want and _sha256(p) != want:
                        out.append(f"{tag}: {col} {r[col]} sha256 differs from {sha_col}")
                    continue
                ptr = C.pointer_of(p)
                if ptr is None:
                    out.append(f"{tag}: {col} {r[col]} not found (no file, no .drive pointer)")
                elif want and ptr.get("sha256", "").lower() != want:
                    out.append(f"{tag}: {col} {r[col]} Drive pointer sha256 differs from {sha_col}")
        out += [f"{where}: {cid} rev {rev} has {n} rows" for (cid, rev), n in sorted(pairs.items()) if n > 1]
        out += [f"{where}: {cid} has {n} current rows" for cid, n in sorted(current.items()) if n > 1]
    out += [f"{cid} is in both the job and the project register (an id is in one library only)"
            for cid, levels in sorted(library_of.items()) if len(levels) > 1]
    folders = C.component_folders(libs)
    for lib, d in folders:
        cid = C.FOLDER_RE.match(d.name).group(1)
        if lib.level not in library_of.get(cid, set()):
            out.append(f"{rp.rel(d) if d.is_relative_to(rp.REPO) else d}: folder has no row in {_where(lib)}")
    return n_rows, len(folders), out


def main() -> int:
    try:
        n_rows, n_dirs, found = findings()
    except (OSError, csv.Error, UnicodeDecodeError) as e:
        print(f"component_register: ERROR - a register could not be read: {e}")
        return 3
    what = (f"{n_rows} register row(s), {n_dirs} component folder(s) in the job and project libraries"
            if rp.HAS_PROJECT else
            f"{n_rows} register row(s), {n_dirs} component folder(s) in the job library; project library not checked: "
            "no project yet")
    if not found:
        print(f"component_register: PASS - {what}")
        return 0
    print(f"component_register: FAIL - {what}: {len(found)} finding(s) (reported, not blocking)")
    for f in found:
        print(f"  {f}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
