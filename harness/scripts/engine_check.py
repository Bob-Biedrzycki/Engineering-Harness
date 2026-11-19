"""engine_check.py - is a newer release of the CAD engine safe to pin? One command, nothing filed, nothing rebuilt.

The job pins ONE engine, in harness/requirements-cad.txt (the cad venv, harness/tools/venv-cad): the skid build's
second interpreter and the plan set view projection both run on it. The plugin's skills and the computer's own
`cad` command update themselves; this pin moves only on purpose, after this comparison, on Bob's word.
Skill: .claude/skills/engine-update.

    .\\harness\\tools\\venv\\Scripts\\python.exe harness\\scripts\\engine_check.py status
    .\\harness\\tools\\venv\\Scripts\\python.exe harness\\scripts\\engine_check.py try [--version X] [--skip-model] [--skip-views]
    .\\harness\\tools\\venv\\Scripts\\python.exe harness\\scripts\\engine_check.py adopt --version X

status   the pinned release, what the cad venv holds, what the computer's `cad` is, and the newest release.
         Exit 0 = the pin is the newest release; 1 = a newer release exists; 2 = it could not tell.
try      builds harness/tools/venv-cad-try (gitignored) with the candidate release and the pin's other packages,
         then runs the same work on both engines and compares the numbers:
           probe   harness/cad-lib/engine_probe.py: fixed solids, a STEP round trip, exact projections, and the
                   engine names the code relies on
           model   the project model's quick GLB (export_glb_fast.py --out), when the job has a model
           views   the job's reference views, when job/engine-check.yaml names them (a scratch view cache)
         Writes harness/tools/engine-check/<release>/report.md and prints it. Touches no build folder, no pinned
         view cache, nothing filed. Exit 0 = no difference found; 1 = differences, read the report; 2 = refused.
adopt    after a `try` of the same release, and on Bob's word: freezes the candidate into
         harness/requirements-cad.txt, keeps the old venv as venv-cad-<old release>, and rebuilds venv-cad from the
         new file. It files nothing and re-projects nothing: views already cached stay as the old engine made them.
         Run it in the job that has the model; the changed requirements file then goes to the master and the other
         jobs (harness_sync.py), and each of those rebuilds its venv:
rebuild  builds venv-cad from harness/requirements-cad.txt when the venv does not hold the pinned release.

job/engine-check.yaml (optional, the job's own):
    views:
      script: <repo path of the projection script>
      batch:  <repo path of a JSON list of view jobs>
      args:   [extra arguments, e.g. --bodies <cache with the bodies>]
      cache_root: <repo path of the folder the script's --cache names live in>
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists()) / "harness" / "lib"))
import repo_paths as rp  # noqa: E402

REQ = rp.HARNESS / "requirements-cad.txt"
PY_PIN = rp.TOOLS / "venv-cad" / "Scripts" / "python.exe"
TRY_DIR = rp.TOOLS / "venv-cad-try"
PY_TRY = TRY_DIR / "Scripts" / "python.exe"
OUT = rp.TOOLS / "engine-check"
JOB_FILE = rp.REPO / "job" / "engine-check.yaml"
PACKAGE = "cad"
EXTRAS = ("pyyaml", "pandas", "ezdxf", "matplotlib")   # installed beside the engine, held at the pin's versions
LEN_TOL_MM = 0.01          # sizes, bounds and view origins
REL_TOL = 1e-6             # volumes, areas, the view matrix
LENGTH_REL_TOL = 1e-3      # drawn length of a view (the hidden-line pass splits edges differently between kernels)


# ---- the pin and the releases --------------------------------------------------------------------------------------
def pins(text: str) -> dict:
    """{package: version} from a requirements file's `name==version` lines."""
    return {m[1].lower(): m[2] for m in re.finditer(r"^([A-Za-z0-9_.\-]+)==(\S+)\s*$", text, re.M)}


def pinned() -> str | None:
    return pins(REQ.read_text(encoding="utf-8")).get(PACKAGE) if REQ.is_file() else None


def vkey(v: str) -> tuple:
    return tuple(int(x) if x.isdigit() else x for x in re.split(r"[.\-+]", v))


def newest_release() -> str | None:
    """The newest release on PyPI (the package name only is sent)."""
    try:
        with urllib.request.urlopen(f"https://pypi.org/pypi/{PACKAGE}/json", timeout=20) as r:
            return json.load(r)["info"]["version"]
    except Exception:  # noqa: BLE001
        return None


def computer_cad() -> str | None:
    exe = shutil.which("cad")
    if not exe:
        return None
    try:
        out = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=60).stdout
        m = re.search(r"(\d+\.\d+\.\d+\S*)", out)
        return m[1] if m else None
    except Exception:  # noqa: BLE001
        return None


def venv_versions(py: Path) -> dict:
    if not py.is_file():
        return {}
    code = ("import json;from importlib.metadata import version as v\n"
            "o={}\n"
            "for p in ('cad','build123d','cadquery-ocp-novtk','ezdxf','matplotlib'):\n"
            "    try: o[p]=v(p)\n"
            "    except Exception: o[p]=None\n"
            "print(json.dumps(o))")
    r = subprocess.run([str(py), "-c", code], capture_output=True, text=True)
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:  # noqa: BLE001
        return {}


# ---- comparisons (pure functions; harness/tests/test_engine_check.py) ----------------------------------------------
def close(a, b, abs_tol=LEN_TOL_MM, rel_tol=REL_TOL) -> bool:
    if a is None or b is None:
        return a is b
    return math.isclose(a, b, rel_tol=rel_tol, abs_tol=abs_tol)


def compare_probe(pin: dict, new: dict) -> list[str]:
    """Differences between two engine_probe.py results, as sentences. Empty = none found."""
    diffs = []
    for name, ok in new.get("api", {}).items():
        if ok is not True and pin.get("api", {}).get(name) is True:
            diffs.append(f"engine name gone: {name} ({'missing' if ok is False else ok})")
    for e in new.get("errors", []):
        if e not in pin.get("errors", []):
            diffs.append(f"probe error on the candidate: {e}")
    for name, a in pin.get("solids", {}).items():
        b = new.get("solids", {}).get(name)
        if b is None:
            diffs.append(f"solid {name}: not built on the candidate")
            continue
        for k in ("volume", "area", "step_volume"):
            if not close(a.get(k), b.get(k), abs_tol=1e-3):
                diffs.append(f"solid {name}: {k} {a.get(k):.6f} then, {b.get(k):.6f} now")
        if any(not close(x, y) for x, y in zip(a["bbox"], b["bbox"])):
            diffs.append(f"solid {name}: bounding box moved")
        for k in ("faces", "edges", "step_entities"):
            if a.get(k) != b.get(k):
                diffs.append(f"solid {name}: {k} {a.get(k)} then, {b.get(k)} now")
    for name, a in pin.get("views", {}).items():
        b = new.get("views", {}).get(name)
        if b is None:
            diffs.append(f"view {name}: not projected on the candidate")
            continue
        diffs += [f"view {name}: {d}" for d in compare_view(a, b)]
    return diffs


def compare_view(a: dict, b: dict) -> list[str]:
    """Differences between two projections of one view. Works on engine_probe views (c, m, counts, lengths) and on a
    job's cached views (proj, bounds, visible and hidden entity lists)."""
    a, b = view_numbers(a), view_numbers(b)
    diffs = []
    if any(not close(x, y, abs_tol=1e-9) for ra, rb in zip(a["m"], b["m"]) for x, y in zip(ra, rb)):
        diffs.append("the model-to-view matrix changed")
    if any(not close(x, y) for x, y in zip(a["c"], b["c"])):
        diffs.append("the view origin moved")
    if (a["bounds"] is None) != (b["bounds"] is None) or (
            a["bounds"] and any(not close(x, y) for x, y in zip(a["bounds"], b["bounds"]))):
        diffs.append(f"bounds {a['bounds']} then, {b['bounds']} now")
    for k in ("visible", "hidden"):
        la, lb = a[f"{k}_length"], b[f"{k}_length"]
        if not math.isclose(la, lb, rel_tol=LENGTH_REL_TOL, abs_tol=LEN_TOL_MM):
            pct = (lb - la) / la * 100 if la else float("inf")
            diffs.append(f"{k} linework {a[k]} pieces {la:.1f} mm then, {b[k]} pieces {lb:.1f} mm now ({pct:+.2f} %)")
    if a.get("cut_area") is not None and not close(a["cut_area"], b.get("cut_area"), abs_tol=0.01, rel_tol=1e-6):
        diffs.append(f"section cut area {a['cut_area']:.2f} then, {b.get('cut_area'):.2f} now")
    return diffs


def entity_length(e) -> float:
    if e[0] == "L":
        return math.hypot(e[3] - e[1], e[4] - e[2])
    if e[0] == "P":
        return sum(math.hypot(q[0] - p[0], q[1] - p[1]) for p, q in zip(e[1], e[1][1:]))
    if e[0] == "C":
        return 2 * math.pi * e[3]
    if e[0] == "A":
        return e[3] * math.radians((e[5] - e[4]) % 360 or 360)
    return 0.0


def loop_area(pts) -> float:
    return abs(sum(p[0] * q[1] - q[0] * p[1] for p, q in zip(pts, pts[1:] + pts[:1]))) / 2


def view_numbers(v: dict) -> dict:
    """One shape for both kinds of view record."""
    if "proj" not in v:
        return v
    cuts = v.get("cuts") or []
    return {"c": v["proj"]["c"], "m": v["proj"]["m"], "bounds": v.get("bounds"),
            "visible": len(v.get("visible") or []), "hidden": len(v.get("hidden") or []),
            "visible_length": sum(entity_length(e) for e in v.get("visible") or []),
            "hidden_length": sum(entity_length(e) for e in v.get("hidden") or []),
            "cut_area": sum(loop_area(c["outer"]) - sum(loop_area(i) for i in c.get("inner", [])) for c in cuts)
            if cuts else None}


def glb_numbers(path: Path) -> dict:
    """Counts and the overall box of a GLB, from its JSON chunk (no library needed)."""
    data = path.read_bytes()
    n = struct.unpack_from("<I", data, 12)[0]
    g = json.loads(data[20:20 + n].decode("utf-8"))
    pos = [g["accessors"][p["attributes"]["POSITION"]] for m in g.get("meshes", []) for p in m["primitives"]
           if "POSITION" in p.get("attributes", {})]
    return {"nodes": len(g.get("nodes", [])), "meshes": len(g.get("meshes", [])),
            "names": sorted({x.get("name", "") for x in g.get("nodes", [])}),
            "vertices": sum(a["count"] for a in pos),
            "min": [min(a["min"][i] for a in pos) for i in range(3)] if pos else None,
            "max": [max(a["max"][i] for a in pos) for i in range(3)] if pos else None}


def compare_glb(a: dict, b: dict) -> list[str]:
    diffs = []
    for k in ("nodes", "meshes"):
        if a[k] != b[k]:
            diffs.append(f"{k} {a[k]} then, {b[k]} now")
    if a["names"] != b["names"]:
        gone, new = set(a["names"]) - set(b["names"]), set(b["names"]) - set(a["names"])
        diffs.append(f"body names changed ({len(gone)} gone, {len(new)} new)")
    if a["vertices"] and abs(b["vertices"] - a["vertices"]) / a["vertices"] > 0.01:
        diffs.append(f"mesh vertices {a['vertices']} then, {b['vertices']} now")
    for k in ("min", "max"):
        if a[k] and b[k] and any(not close(x, y, abs_tol=1e-4, rel_tol=1e-6) for x, y in zip(a[k], b[k])):
            diffs.append(f"overall box {k} {a[k]} then, {b[k]} now")
    return diffs


# ---- the steps -----------------------------------------------------------------------------------------------------
def run(cmd, log: Path, **kw) -> int:
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "w", encoding="utf-8") as fh:
        return subprocess.run([str(c) for c in cmd], cwd=rp.REPO, stdout=fh, stderr=subprocess.STDOUT, **kw).returncode


def uv() -> str:
    exe = shutil.which("uv")
    if not exe:
        raise SystemExit("REFUSED: uv is not on PATH (tooling.md, the uv row)")
    return exe


def build_try_venv(version: str, out: Path) -> str | None:
    """harness/tools/venv-cad-try with the candidate and the pin's other packages. Returns a reason on failure."""
    have = venv_versions(PY_TRY).get(PACKAGE)
    if have == version:
        return None
    if TRY_DIR.exists():
        shutil.rmtree(TRY_DIR)
    held = pins(REQ.read_text(encoding="utf-8"))
    if run([uv(), "venv", "--python", "3.13", TRY_DIR], out / "logs" / "venv.log") != 0:
        return "uv venv failed (logs/venv.log)"
    want = [f"{PACKAGE}[build123d]=={version}"] + [f"{p}=={held[p]}" if p in held else p for p in EXTRAS]
    if run([uv(), "pip", "install", "--python", PY_TRY, *want], out / "logs" / "install.log") != 0:
        return "uv pip install failed (logs/install.log)"
    return None


def do_probe(out: Path) -> tuple[list[str], str]:
    res = {}
    for tag, py in (("pin", PY_PIN), ("try", PY_TRY)):
        f = out / f"probe-{tag}.json"
        if run([py, rp.CAD_LIB / "engine_probe.py", f], out / "logs" / f"probe-{tag}.log") != 0 or not f.is_file():
            return [f"the probe did not run on the {tag} engine (logs/probe-{tag}.log)"], "failed"
        res[tag] = json.loads(f.read_text(encoding="utf-8"))
    n = len(res["pin"]["solids"]), len(res["pin"]["views"])
    return compare_probe(res["pin"], res["try"]), f"{n[0]} solids, {n[1]} views, {len(res['try']['api'])} engine names"


def do_model(out: Path) -> tuple[list[str], str]:
    script = rp.SKID_MODEL / "export_glb_fast.py"
    if not rp.HAS_PROJECT or not script.is_file():
        return [], "not run: this job has no model with a quick GLB export"
    nums = {}
    for tag, py in (("pin", PY_PIN), ("try", PY_TRY)):
        glb = out / f"model-{tag}.glb"
        if glb.exists():
            glb.unlink()
        if run([py, script, "--out", glb], out / "logs" / f"model-{tag}.log") != 0 or not glb.is_file():
            return [f"the model did not build on the {tag} engine (logs/model-{tag}.log)"], "failed"
        nums[tag] = glb_numbers(glb)
        glb.unlink()        # a look-at file, tens of MB; the numbers are kept
    (out / "model-numbers.json").write_text(json.dumps(nums, indent=1), encoding="utf-8")
    return compare_glb(nums["pin"], nums["try"]), f"{nums['pin']['nodes']} nodes, {nums['pin']['vertices']} vertices"


def do_views(out: Path) -> tuple[list[str], str]:
    if not JOB_FILE.is_file():
        return [], "not run: the job names no reference views (job/engine-check.yaml)"
    import yaml
    cfg = (yaml.safe_load(JOB_FILE.read_text(encoding="utf-8")) or {}).get("views") or {}
    if not cfg:
        return [], "not run: job/engine-check.yaml has no views"
    root = rp.REPO / cfg["cache_root"]
    caches = {}
    for tag, py in (("pin", PY_PIN), ("try", PY_TRY)):
        name = f"engine-check-{tag}"
        if (root / name).exists():
            shutil.rmtree(root / name)
        rc = run([py, rp.REPO / cfg["script"], "--batch", rp.REPO / cfg["batch"], "--cache", name,
                  *[str(x) for x in cfg.get("args", [])]], out / "logs" / f"views-{tag}.log")
        if rc != 0 or not (root / name).is_dir():
            return [f"the views did not project on the {tag} engine (logs/views-{tag}.log)"], "failed"
        caches[tag] = root / name
    diffs, n = [], 0
    for job in json.loads((rp.REPO / cfg["batch"]).read_text(encoding="utf-8")):
        fa, fb = (caches[t] / f"{job['name']}.json" for t in ("pin", "try"))
        if not fa.is_file() or not fb.is_file():
            diffs.append(f"view {job['name']}: not projected on the {'pin' if not fa.is_file() else 'candidate'} engine")
            continue
        n += 1
        diffs += [f"view {job['name']}: {d}" for d in
                  compare_view(json.loads(fa.read_text(encoding="utf-8")), json.loads(fb.read_text(encoding="utf-8")))]
    for c in caches.values():
        shutil.rmtree(c)
    return diffs, f"{n} reference views"


def cmd_status() -> int:
    pin, new = pinned(), newest_release()
    have = venv_versions(PY_PIN)
    print(f"engine_check: pinned {PACKAGE} {pin or 'none'} (harness/requirements-cad.txt)")
    print(f"  cad venv holds   {have.get(PACKAGE) or 'no venv'}"
          + (f" (build123d {have.get('build123d')}, OCP {have.get('cadquery-ocp-novtk')})" if have else ""))
    print(f"  this computer    {computer_cad() or 'no cad command'} (updates itself; the skills use it)")
    print(f"  newest release   {new or 'could not ask PyPI'}")
    if not pin or not new:
        return 2
    if vkey(new) > vkey(pin):
        print(f"engine_check: a newer release exists. Compare it: engine_check.py try --version {new}")
        return 1
    print("engine_check: the pin is the newest release")
    return 0


def cmd_try(a) -> int:
    pin = pinned()
    if not pin or not PY_PIN.is_file():
        print("REFUSED: no pinned cad venv here (harness/requirements-cad.txt and harness/tools/venv-cad)", file=sys.stderr)
        return 2
    version = a.version or newest_release()
    if not version:
        print("REFUSED: no --version given and PyPI could not be asked", file=sys.stderr)
        return 2
    if version == pin:
        print(f"engine_check: {version} is already the pin; nothing to compare")
        return 0
    out = OUT / version
    out.mkdir(parents=True, exist_ok=True)
    print(f"engine_check: {PACKAGE} {pin} (pinned) against {version}", flush=True)
    why = build_try_venv(version, out)
    if why:
        print(f"REFUSED: {why}", file=sys.stderr)
        return 2
    old, new = venv_versions(PY_PIN), venv_versions(PY_TRY)
    sections = []
    for name, fn, skip in (("probe", do_probe, False), ("model", do_model, a.skip_model),
                           ("views", do_views, a.skip_views)):
        diffs, note = ([], "skipped on request") if skip else fn(out)
        sections.append((name, diffs, note))
        print(f"[{'ok  ' if not diffs else 'DIFF'}] {name:<6} {note}" + (f"; {len(diffs)} difference(s)" if diffs else ""),
              flush=True)
    kernel = [k for k in ("build123d", "cadquery-ocp-novtk") if old.get(k) != new.get(k)]
    total = sum(len(d) for _, d, _ in sections)
    lines = [f"# Engine check: {PACKAGE} {pin} (pinned) against {version}", "",
             f"Run {dt.datetime.now():%Y-%m-%d %H:%M}. Nothing was filed, rebuilt or re-projected; the pin is unchanged.", "",
             "| Package | Pinned | Candidate |", "|---|---|---|"]
    lines += [f"| {k} | {old.get(k)} | {new.get(k)} |" for k in ("cad", "build123d", "cadquery-ocp-novtk", "ezdxf", "matplotlib")]
    lines += ["", "The geometry kernel is the same in both." if not kernel else
              f"**The geometry kernel changes** ({', '.join(kernel)}): expect small differences in hidden lines and "
              "STEP numbers, and read every line below.", "",
              f"**Result: {'no difference found' if not total else f'{total} difference(s)'}.**", ""]
    for name, diffs, note in sections:
        lines += [f"## {name}", "", note + ".", ""] + [f"- {d}" for d in diffs] + ([""] if diffs else [])
    lines += ["## What this does not cover", "",
              "A full build's STEP and its checks, and views outside the reference set. Run one full build after the "
              "pin moves and compare its lists with the last one before anything is filed.", ""]
    (out / "report.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(f"engine_check: {'no difference found' if not total else f'{total} difference(s)'} -> {rp.rel(out / 'report.md')}")
    if not total:
        print(f"engine_check: to move the pin, on Bob's word: engine_check.py adopt --version {version}")
    return 0 if not total else 1


def cmd_adopt(a) -> int:
    pin = pinned()
    if venv_versions(PY_TRY).get(PACKAGE) != a.version or not (OUT / a.version / "report.md").is_file():
        print(f"REFUSED: run `engine_check.py try --version {a.version}` first (no candidate venv or report)", file=sys.stderr)
        return 2
    freeze = subprocess.run([uv(), "pip", "freeze", "--python", str(PY_TRY)], capture_output=True, text=True)
    if freeze.returncode != 0 or f"{PACKAGE}=={a.version}" not in freeze.stdout:
        print("REFUSED: could not freeze the candidate venv", file=sys.stderr)
        return 2
    text = REQ.read_text(encoding="utf-8")
    head = [ln for ln in text.splitlines() if ln.startswith("#") and not ln.startswith("# Frozen ")]
    head.append(f"# Frozen {dt.date.today()} from harness/tools/venv-cad-try by engine_check.py adopt "
                f"({PACKAGE} {pin} before); the comparison is harness/tools/engine-check/{a.version}/report.md.")
    REQ.write_text("\n".join(head) + "\n" + freeze.stdout.replace("\r\n", "\n"), encoding="utf-8", newline="\n")
    keep = rp.TOOLS / f"venv-cad-{pin}"
    venv = PY_PIN.parents[1]
    if venv.exists():
        if keep.exists():
            shutil.rmtree(keep)
        os.replace(venv, keep)
    rc = run([uv(), "venv", "--python", "3.13", venv], OUT / a.version / "logs" / "adopt-venv.log") or \
        run([uv(), "pip", "install", "--python", PY_PIN, "-r", REQ], OUT / a.version / "logs" / "adopt-install.log")
    if rc != 0 or venv_versions(PY_PIN).get(PACKAGE) != a.version:
        print(f"FAILED: venv-cad was not rebuilt; the old one is {rp.rel(keep)} (logs in {rp.rel(OUT / a.version / 'logs')})",
              file=sys.stderr)
        return 1
    print(f"engine_check: pin moved {pin} -> {a.version}; venv-cad rebuilt; the old venv is kept as {rp.rel(keep)}")
    print("engine_check: record it in the project's tooling.md, save harness/requirements-cad.txt, and run one full "
          "build before anything is filed. Views already cached stay as the old engine made them.")
    return 0


def cmd_rebuild() -> int:
    """venv-cad from the requirements file, when it does not hold the pin (a job that pulled a moved pin)."""
    pin = pinned()
    have = venv_versions(PY_PIN).get(PACKAGE)
    if not pin:
        print("REFUSED: harness/requirements-cad.txt names no cad release", file=sys.stderr)
        return 2
    if have == pin:
        print(f"engine_check: venv-cad already holds {PACKAGE} {pin}; nothing to do")
        return 0
    venv, logs = PY_PIN.parents[1], OUT / pin / "logs"
    if venv.exists():
        keep = rp.TOOLS / f"venv-cad-{have or 'old'}"
        if keep.exists():
            shutil.rmtree(keep)
        os.replace(venv, keep)
    rc = run([uv(), "venv", "--python", "3.13", venv], logs / "rebuild-venv.log") or \
        run([uv(), "pip", "install", "--python", PY_PIN, "-r", REQ], logs / "rebuild-install.log")
    if rc != 0 or venv_versions(PY_PIN).get(PACKAGE) != pin:
        print(f"FAILED: venv-cad was not rebuilt (logs in {rp.rel(logs)})", file=sys.stderr)
        return 1
    print(f"engine_check: venv-cad rebuilt with {PACKAGE} {pin}" + (f" (was {have})" if have else ""))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    sub.add_parser("rebuild")
    t = sub.add_parser("try")
    t.add_argument("--version", help="the release to compare (default: the newest)")
    t.add_argument("--skip-model", action="store_true")
    t.add_argument("--skip-views", action="store_true")
    ad = sub.add_parser("adopt")
    ad.add_argument("--version", required=True)
    a = ap.parse_args(argv)
    return {"status": cmd_status, "rebuild": cmd_rebuild, "try": lambda: cmd_try(a),
            "adopt": lambda: cmd_adopt(a)}[a.cmd]()


if __name__ == "__main__":
    sys.exit(main())
