"""filed_step - open a filed model STEP that may be zipped (CPME practice).

The filed STEP is `<MODEL-ID>-rev<X>.step.zip` holding one STEP. Consumers
(Blender, exploded parts, checks) never read the zip in place and never write next to the filed file: they
call `unzipped(path)`, which extracts the one STEP into <project>/_work/unzipped/<zip name>/ (gitignored working
copy) and returns its path. A plain .step (a revision filed before the zip rule, unzipped) is returned as is.

    sys.path.insert(0, str(<repo>/"harness"/"lib")); from filed_step import unzipped
    step_path = unzipped(rp.SKID_FILED / f"{rp.SKID_MODEL_ID}-revA.step.zip")
"""
from __future__ import annotations

import zipfile
from pathlib import Path

import repo_paths as rp

UNZIP_ROOT = rp.WORK / "unzipped" if rp.HAS_PROJECT else rp.JOBS / "_work" / "unzipped"   # gitignored either way


def unzipped(path: Path) -> Path:
    """Path to a readable STEP for a filed STEP or STEP zip. Extracts once; re-extracts if the zip is newer."""
    path = Path(path)
    if path.suffix.lower() != ".zip":
        return path
    with zipfile.ZipFile(path) as z:
        steps = [n for n in z.namelist() if n.lower().endswith((".step", ".stp"))]
        if len(steps) != 1:
            raise ValueError(f"{path.name}: expected exactly one STEP inside, found {steps}")
        dest = UNZIP_ROOT / path.name / Path(steps[0]).name
        info = z.getinfo(steps[0])
        if not (dest.exists() and dest.stat().st_size == info.file_size
                and dest.stat().st_mtime >= path.stat().st_mtime):
            dest.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as src, open(dest, "wb") as out:
                while chunk := src.read(1 << 22):
                    out.write(chunk)
    return dest
