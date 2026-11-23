"""model_iterate.py - tier 1 of the three-tier pipeline: one build of the skid model, every iteration.

One build series (Bob, chat, 2026-11-12: "many times it takes 30+ edits to get to the desired result"; one numbered,
never-overwritten series in place of two build folders): every run, full or --fast, writes a new folder
<project>/03_Working_Design/CAD/Builds/rev<X>/rev<X>-full-<nnn>/ or rev<X>-fast-<nnn>/, <X> the last filed revision
the build starts from (`first` before Rev A) and <nnn> the next number for that letter, shared by both kinds (001 again
after each filing). Every build gets a row in Builds/build-log.md saying which checks ran. A full build is what
model_file.py files; the steps a full build starts find its folder through CPME_BUILD_DIR (repo_paths.current_build).
When a full build starts, the STEP of each earlier full build is zipped beside its other files. A finished build's
files are read-only: the model's export scripts are run only by this script, and one started by hand, which would
write into the latest full build, fails instead of changing it.

The three-tier model pipeline (Bob, chat, 2026-10-02: make
iteration fast and close-out unattended). Skill: .claude/skills/model-iterate.

Runs, in this order (independent steps in parallel):
    1. lists        <project>/03_Working_Design/CAD/01_Master_Assembly/<MODEL-ID>/export_lists.py      takeoffs, manifest, layout note (repo venv, harness/tools/venv)
    2. step         <project>/03_Working_Design/CAD/01_Master_Assembly/<MODEL-ID>/export_step_direct.py   assembly STEP (cad venv, harness/tools/venv-cad)
       in parallel with step:
         interference   harness/checks/interference.py
         pipe_supports  harness/checks/pipe_supports.py --report <build>   pipe-support-calc.csv / .md
         list_delta     harness/lib/list_delta.py    list-delta.csv / .md: the model vs <project>/03_Working_Design/PID/02_Tag_Lists lists
    3. after step, in parallel:
         envelope       harness/checks/envelope.py   (measures the new STEP too)
         materials      harness/checks/materials.py  (every fabricated body against the materials list)
         glb            <project>/03_Working_Design/CAD/01_Master_Assembly/<MODEL-ID>/export_glb.py
    4. looks        <project>/03_Working_Design/CAD/09_Presentation/presentation_materials.py --glb <build GLB> --looks-only: one line,
                    "looks: n of m required instruments realistic; missing: ...", materials.yaml required_looks.
                    Report only: never fails the build. Not run by --fast (its GLB is not the export's).
                    With no presentation site yet (site_revs.site_dormant: site_repo unknown or the builder
                    absent) the line reads "looks: no presentation site yet (...)" and the step passes

Writes only to its new folder under <project>/03_Working_Design/CAD/Builds/ (working copies, gitignored), with logs/ and
iterate-summary.json there. Never files, never pushes, never builds the portal. Prints one summary line per step.

    .\\harness\\tools\\venv\\Scripts\\python.exe harness\\scripts\\model_iterate.py [--keep-going] [--no-glb] [--fast [--supports] [--drawings]] [--request "..." --change "..."]

--fast (Bob, chat, 2026-10-10: light-weight modelling that is very fast; "The fast build should still create a
new file, and not overwrite an existing."; "I need to be able to see it ... whatever is fastest.") runs lists, list
delta, interference and the model-only envelope (~6 s) beside export_glb_fast.py, a GLB to look at
straight from the model (~1 min); no STEP. The pipe supports check runs only with --supports, given only when Bob
asks for it (Bob, chat, 2026-10-15: "The pipe support check is completley unnecessary until i request it.  do not
check until i ask."). Each fast build writes into a new folder of its own,
<project>/03_Working_Design/CAD/Builds/rev<X>/rev<X>-fast-<nnn>/ (Bob, 2026-10-10: "I would like the root Fast folder in the Job/Models
folder"; Bob, 2026-10-11: "job/models/fast/revV/revV-fast-001. that way we can still track fast changes."),
refused if it exists, and touches nothing else: every earlier build stays as it is.
<project>/03_Working_Design/CAD/Builds/ is gitignored and outside the Drive store: working copies,
not revisions. model_file.py never files a fast build: run the full build once before filing.

A fast build changes and checks the model only (CAPA 2026-11-23; Bob, chat: "Planset updates should not be of concern
or worry when making model edits. When the model is accepted, thats when the plans should be updated." and the line
diagram "should not be a concern during model fast edits"). It draws no drawing: --drawings, given only when Bob asks
for it, also draws the P&ID, line segment diagram and PFD from the build in check mode (about 1-2 s each, beside the
GLB, nothing written), as model_accept.py does in its preflight. The build ends with:
    - the hard items of the checks it ran (lists / model problems, interference, envelope, GLB, pipe supports with
      --supports, drawings with --drawings), harness/lib/accept_preflight.py;
    - one line, "carried to acceptance: n item(s) (...) -> <path>", for everything else (list delta rows, components
      registered since the last revision but not placed, questions opened since then), written to
      carried-to-acceptance.md in the build folder for model_accept.py, which writes the lists from the model and
      records the rest in the revision description;
    - the fixed FAST EDIT SCOPE footer (accept_preflight.FAST_SCOPE_FOOTER).
A full build and model_accept.py still print the whole open list. --request "<Bob's words>" --change "<what changed>"
go in the build's build-log row (a fast build is logged when --request is given, a full build always); the row names
only the checks that ran.

--model-id <ID> [--config <CFG>] (or CPME_MODEL_ID / CPME_MODEL_CONFIG; Linear CPM-155) builds a job-level model
(a folder in the job-level models folder, harness/lib/repo_paths.py) in one configuration (B, X or a switch string the
model accepts; default B) into job/Typical-<ID prefix>/03_Working_Design/CAD/Builds/<MODEL-ID>/<CFG>/, numbered the same way; the checks it starts inherit the
choice. A job-level build also renders the review views (iso, plan, front, side PNGs from the build STEP,
harness/cad-lib/render_png.py), which model_file.py files with it. Its fast build never draws the P&ID drawing
checks, even with --drawings (those are the project's drawings). Without --model-id everything is as above.

Exit 0 = every step ran and every check passed; 1 = a step or check failed (see the lines and logs/);
2 = refused (missing venv, or a configuration the model does not accept).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import threading
import sys
import time
from pathlib import Path

sys.path.insert(0, str(next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists()) / "harness" / "lib"))
import repo_paths as rp  # noqa: E402
if __name__ == "__main__":
    rp.require_model("model_iterate.py")   # no project and no --model-id: exit 2, nothing to build
import model_build as mb  # noqa: E402
import accept_preflight as pf  # noqa: E402

PY = rp.TOOLS / "venv" / "Scripts" / "python.exe"
# the second interpreter: the cad venv (cad[build123d] with ezdxf and matplotlib), built from the job's one
# engine pin, harness/requirements-cad.txt; harness/scripts/engine_check.py compares a newer release and moves it
PY_CAD = rp.TOOLS / "venv-cad" / "Scripts" / "python.exe"
BUILDS = rp.BUILDS      # <project>/03_Working_Design/CAD/Builds: every build, fast or full (Bob, 2026-11-12)
LOCK_NAME = ".build-lock"   # one build of a model at a time (REVW-001 OP-1, 2026-11-23)


def _pid_alive(pid: int) -> bool:
    """True when a process with this id is running. (os.kill(pid, 0) ends the process on Windows, so it is not used.)"""
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        k = ctypes.windll.kernel32
        h = k.OpenProcess(0x1000, False, pid)            # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        code = ctypes.c_ulong()
        ok = k.GetExitCodeProcess(h, ctypes.byref(code))
        k.CloseHandle(h)
        return bool(ok) and code.value == 259            # STILL_ACTIVE
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def take_build_lock(builds: Path, request: str, pid: int | None = None) -> tuple[Path | None, str]:
    """(lock file, "") when this build may run, (None, why) when another build of this model is running.

    REVW-001 (2026-11-23, OP-1): two sessions built in the shared checkout at the same time, so builds held both
    sessions' half-made source and raced for the next build number, and nothing said so. One build at a time: the
    second is refused with who holds the lock, and is run again when that one ends. A lock whose process is gone
    (a build that was stopped) is taken over."""
    builds.mkdir(parents=True, exist_ok=True)
    lock = builds / LOCK_NAME
    me = {"pid": pid or os.getpid(), "started": dt.datetime.now().replace(microsecond=0).isoformat(sep=" "),
          "request": (request or "")[:120]}
    for _ in range(2):
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                held = json.loads(lock.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                held = {}
            if _pid_alive(int(held.get("pid") or 0)):
                return None, (f"another build of this model is running (started {held.get('started', '?')}"
                              + (f", request: {held['request']}" if held.get("request") else "") + "). One build at a "
                              "time: this one would hold that session's half-made source and race it for the build "
                              "number. Run it again when that build has ended; do not mention this to Bob.")
            try:
                lock.unlink()                             # the build that wrote it is gone
            except OSError:
                pass
            continue
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(me, f)
        return lock, ""
    return None, f"could not take the build lock {lock}"


def release_build_lock(lock: Path | None) -> None:
    try:
        if lock and json.loads(lock.read_text(encoding="utf-8")).get("pid") == os.getpid():
            lock.unlink()
    except (OSError, ValueError):
        pass


class Step:
    """One subprocess step: its log goes to logs/<name>.log, its summary is the first line it prints."""

    def __init__(self, name: str, cmd: list[str], logs: Path | None = None):
        self.name, self.cmd = name, [str(c) for c in cmd]
        self.log = (logs or mb.BUILD / "logs") / f"{name}.log"
        self.t0 = time.time()
        self.fh = open(self.log, "w", encoding="utf-8")
        self.proc = subprocess.Popen(self.cmd, cwd=rp.REPO, stdout=self.fh, stderr=subprocess.STDOUT,
                                     text=True, encoding="utf-8", errors="replace")

    def wait(self) -> dict:
        rc = self.proc.wait()
        self.fh.close()
        secs = time.time() - self.t0
        text = self.log.read_text(encoding="utf-8", errors="replace").splitlines()
        # the summary is the script's own first line (named after it); library noise such as font warnings is skipped
        key = Path(self.cmd[1]).stem
        first = next((ln for ln in text if ln.strip().startswith(key)), None) \
            or next((ln for ln in text if ln.strip()), "(no output)")
        return {"exit": rc, "summary": first.strip(), "seconds": round(secs, 1), "log": rp.rel(self.log)}


def say(name: str, r: dict) -> None:
    tag = "ok  " if r["exit"] == 0 else "FAIL"
    print(f"[{tag}] {name:<13} {r['seconds']:>6.1f} s  {r['summary']}", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--keep-going", action="store_true",
                    help="continue after export_lists reports model problems (default: stop, as the fast loop does)")
    ap.add_argument("--no-glb", action="store_true", help="skip the GLB export (a build without a GLB cannot be filed)")
    ap.add_argument("--fast", action="store_true",
                    help="quick loop: lists, list delta, interference, model-only envelope; "
                         "a quick GLB to look at, no STEP; a new <project>/03_Working_Design/CAD/Builds/rev<X>/rev<X>-fast-<nnn>/ folder each run, "
                         "nothing overwritten")
    ap.add_argument("--supports", action="store_true",
                    help="with --fast: also run the pipe supports check (only when Bob asks for it)")
    ap.add_argument("--drawings", action="store_true",
                    help="with --fast: also draw the P&ID, line segment diagram and process flow diagram in check "
                         "mode; only when Bob asks for it")
    ap.add_argument("--request", default="",
                    help="Bob's request (his words, trimmed), for this build's build-log row")
    ap.add_argument("--change", default="", help="what this build changed, for the build log")
    rp.add_model_args(ap)
    a = ap.parse_args()
    for exe in (PY, PY_CAD):
        if not exe.is_file():
            print(f"REFUSED: missing {rp.rel(exe)} (rebuild the venv from harness/requirements*.txt)", file=sys.stderr)
            return 2
    import rule_scope
    missing = rule_scope.model_missing()
    if missing:
        print(f"REFUSED: {missing}; nothing to build (the cad-design-engineer writes the model source first)",
              file=sys.stderr)
        return 2
    if mb.JOB_LEVEL:
        name, why = mb.canonical_config()
        if name is None:
            print(f"REFUSED: {mb.MODEL_ID} does not accept --config {rp.MODEL_CONFIG}: {why}", file=sys.stderr)
            return 2
        if name != rp.MODEL_CONFIG:
            print(f"REFUSED: --config {rp.MODEL_CONFIG} is configuration {name} of {mb.MODEL_ID}; use --config {name} "
                  "(one document per configuration)", file=sys.stderr)
            return 2
    for line in mb.adopt_earlier_layout(rp.BUILDS_ROOT, rp.EARLIER_FAST_ROOT, BUILDS, rp.EARLIER_SKID_BUILD,
                                        mb.last_revision()):
        print(f"model_iterate: {line}", flush=True)
    lock, why = take_build_lock(BUILDS, a.request)
    if lock is None:
        print(f"REFUSED: {why}", file=sys.stderr)
        return 2
    import atexit
    atexit.register(release_build_lock, lock)
    if a.fast:
        return fast(a)

    src_dir = rp.SKID_MODEL
    t0 = time.time()
    started = dt.datetime.now().replace(microsecond=0).isoformat(sep=" ")
    # a new numbered folder, never an earlier build's (Bob, chat, 2026-11-12); the steps started below find it
    # through CPME_BUILD_DIR (repo_paths.current_build), and this process through mb.use_build
    out = mb.new_build_dir("full", BUILDS, mb.last_revision())
    if out.exists():
        print(f"REFUSED: {rp.rel(out)} already exists (never overwritten)", file=sys.stderr)
        return 2
    (out / "logs").mkdir(parents=True)
    os.environ["CPME_BUILD_DIR"] = str(out)
    mb.use_build(out)
    mt, newest = mb.newest_source()
    print(f"model_iterate: {mb.DOC_ID} -> {rp.rel(mb.BUILD)} (newest source {rp.rel(newest)}, "
          f"{dt.datetime.fromtimestamp(mt):%Y-%m-%d %H:%M:%S})", flush=True)
    results: dict[str, dict] = {}
    # the STEP of each earlier full build is zipped while this one runs
    zipped: list[str] = []
    zipper = threading.Thread(target=lambda: zipped.extend(mb.zip_earlier_steps(BUILDS, out)), daemon=True)
    zipper.start()

    results["lists"] = Step("lists", [PY, src_dir / "export_lists.py"]).wait()
    say("lists", results["lists"])
    if results["lists"]["exit"] != 0 and not a.keep_going:
        print("model_iterate: STOPPED - export_lists reported model problems (fix the model, or --keep-going)")
        return finish_full(a, results, started, t0, mt, newest, zipper, zipped)

    step = Step("step", [PY_CAD, src_dir / "export_step_direct.py"])
    side = {"interference": Step("interference", [PY, rp.CHECKS / "interference.py"]),
            "pipe_supports": Step("pipe_supports", [PY, rp.CHECKS / "pipe_supports.py", "--report", mb.BUILD]),
            "materials": Step("materials", [PY, rp.CHECKS / "materials.py"])}
    # list delta in this process while the subprocesses run
    results["list_delta"] = run_list_delta(mb.BUILD, "work build")
    say("list_delta", results["list_delta"])
    for k, s in side.items():
        results[k] = s.wait()
        say(k, results[k])
    results["step"] = step.wait()
    if results["step"]["exit"] == 0 and not mb.STEP.exists():
        results["step"]["exit"] = 1
        results["step"]["summary"] += " (but no STEP was written)"
    say("step", results["step"])

    if results["step"]["exit"] == 0:
        after = {"envelope": Step("envelope", [PY, rp.CHECKS / "envelope.py"])}
        if not a.no_glb:
            after["glb"] = Step("glb", [PY, src_dir / "export_glb.py"])
        # a job-level model files its review views (Linear CPM-155): render_png.py from the build STEP
        for view, name in mb.VIEWS if mb.JOB_LEVEL else ():
            after[f"view_{view}"] = Step(f"view_{view}", [PY_CAD, rp.CAD_LIB / "render_png.py", mb.STEP,
                                                          mb.BUILD / name, "--view", view, "--title", mb.DOC_ID])
        for k, s in after.items():
            results[k] = s.wait()
            if k.startswith("view_") and results[k]["exit"] == 0 and not (mb.BUILD / dict(mb.VIEWS)[k[5:]]).exists():
                results[k]["exit"] = 1
                results[k]["summary"] += " (but no PNG was written)"
            say(k, results[k])
        if not mb.JOB_LEVEL and results.get("glb", {}).get("exit") == 0 and mb.GLB.exists():
            results["looks"] = run_looks(mb.GLB)
            say("looks", results["looks"])
    else:
        results["envelope"] = Step("envelope", [PY, rp.CHECKS / "envelope.py"]).wait()
        results["envelope"]["summary"] += " (model only: no new STEP)"
        say("envelope", results["envelope"])
        print("model_iterate: GLB not exported (no STEP)")
    return finish_full(a, results, started, t0, mt, newest, zipper, zipped)


def finish_full(a, results: dict, started: str, t0: float, mt: float, newest: Path, zipper, zipped: list) -> int:
    """The end of a full build: its summary, the earlier STEPs zipped, and its build-log row."""
    rc = finish(results, started, t0, mt, newest)
    zipper.join()
    if zipped:
        print(f"model_iterate: STEP zipped in earlier full build(s): {', '.join(zipped)}")
    mb.log_row(BUILDS, mb.BUILD.name, a.request or "(none given)", a.change or "full build",
               checks_cell(results, f"{(time.time() - t0) / 60:.1f} min"))
    print(f"model_iterate: build-log row added for {mb.BUILD.name}")
    return rc


def checks_cell(results: dict, tail: str) -> str:
    """The Checks cell of a build-log row: only the checks that ran are named."""
    short = {"interference": "int", "envelope": "env", "materials": "materials", "pipe_supports": "pipe_supports",
             "list_delta": "list delta", "step": "STEP", "glb": "GLB", "drawings": "drawings"}
    cell = "; ".join(f"{short[k]} {'PASS' if r['exit'] == 0 else 'FAIL'}" + (f" {r['rows']}" if k == "list_delta" and "rows" in r else "")
                     for k, r in results.items() if k in short)
    return f"{cell}; {tail}"


def run_looks(glb: Path) -> dict:
    """The required_looks line for the build GLB (presentation_materials.py --looks-only; Bob 2026-10-12):
    which instruments in materials.yaml required_looks get their face_colours look. Report only: exit 0 whatever the
    coverage, and a broken map or tool is reported in the line, never a build failure (CLAUDE.md: checks report)."""
    import site_revs
    why = site_revs.site_dormant(("presentation_materials.py",))
    if why:
        return {"exit": 0, "summary": f"looks: {why}", "seconds": 0.0, "report_only": True}
    s = Step("looks", [PY, rp.PRESENTATIONS / "presentation_materials.py", "--glb", glb, "--looks-only"])
    r = s.wait()
    text = s.log.read_text(encoding="utf-8", errors="replace").splitlines()
    line = next((ln.strip() for ln in text if ln.strip().startswith("looks:")), None)
    r["summary"] = line or f"looks: not resolved (exit {r['exit']}): {r['summary']}"
    r["tool_exit"], r["exit"], r["report_only"] = r["exit"], 0, True
    return r


def run_list_delta(folder: Path, what: str) -> dict:
    td = time.time()
    try:
        import list_delta
        d = list_delta.compute(folder)
        list_delta.write(d, folder, f"{mb.DOC_ID} {what} {dt.datetime.now():%Y-%m-%d %H:%M}")
        n = len(d["rows"])
        return {"exit": 0, "rows": n, "seconds": round(time.time() - td, 1),
                "summary": f"list_delta: {n} row(s) - {d['n_list_tags']} list tags, {d['n_model_tags']} "
                           f"model tags, {d['n_spools']} spools ({'model and lists agree' if not n else 'see list-delta.md'})"}
    except Exception as e:  # noqa: BLE001
        return {"exit": 1, "seconds": round(time.time() - td, 1), "summary": f"list_delta: FAIL - {type(e).__name__}: {e}"}


def fast(a) -> int:
    """--fast: the ~6 s checks and a quick GLB, into a new <project>/03_Working_Design/CAD/Builds/rev<X>/rev<X>-fast-<nnn>/ folder; the STEP and the STEP-based
    envelope and GLB, nearly all of a ~6 min build, are left out. Nothing outside the new folder is written or removed."""
    # named for the filed revision the build starts from, as P&ID fast edits are (Bob, chat, 2026-10-11:
    # "job/models/fast/revV/revV-fast-001. that way we can still track fast changes.")
    base = mb.last_revision()
    if not base:
        print(f"REFUSED: no filed revision of {mb.DOC_ID} to start a fast build from", file=sys.stderr)
        return 2
    out = mb.new_build_dir("fast", BUILDS, base)   # one counter per letter, shared with the full builds
    if out.exists():
        print(f"REFUSED: {rp.rel(out)} already exists (never overwritten)", file=sys.stderr)
        return 2
    logs = out / "logs"
    logs.mkdir(parents=True)
    t0 = time.time()
    started = dt.datetime.now().replace(microsecond=0).isoformat(sep=" ")
    mt, newest = mb.newest_source()
    print(f"model_iterate --fast: {mb.DOC_ID} -> {rp.rel(out)} (newest source {rp.rel(newest)}, "
          f"{dt.datetime.fromtimestamp(mt):%Y-%m-%d %H:%M:%S})", flush=True)
    results: dict[str, dict] = {}
    # the GLB to look at (about 1 min, straight from the model, no STEP) runs beside everything else
    glb = out / f"{mb.DOC_ID}-{out.name}.glb"
    view = Step("glb", [PY_CAD, rp.SKID_MODEL / "export_glb_fast.py", "--out", glb], logs)
    results["lists"] = Step("lists", [PY, rp.SKID_MODEL / "export_lists.py", "--out", out], logs).wait()
    say("lists", results["lists"])
    drawing_items, drawing_info = [], {}
    if results["lists"]["exit"] != 0 and not a.keep_going:
        print("model_iterate: STOPPED - export_lists reported model problems (fix the model, or --keep-going)")
    else:
        # the P&ID, LSD and PFD only with --drawings (CAPA 2026-11-23: drawings follow the accepted model, and
        # model_accept.py draws them before filing); never for a job-level model (they are the project's drawings)
        drawings = pf.start_drawing_checks(out, logs) if a.drawings and not mb.JOB_LEVEL else None
        if a.drawings and mb.JOB_LEVEL:
            print("model_iterate --fast: --drawings ignored: the P&ID, line segment diagram and PFD are the "
                  "project's drawings, not a job-level model's")
        td = time.time()
        side = {"interference": Step("interference", [PY, rp.CHECKS / "interference.py"], logs),
                "envelope": Step("envelope", [PY, rp.CHECKS / "envelope.py", "--no-step"], logs),
                "materials": Step("materials", [PY, rp.CHECKS / "materials.py"], logs)}
        # pipe supports only when Bob asks (Bob, chat, 2026-10-15: "do not check until i ask")
        if a.supports:
            side["pipe_supports"] = Step("pipe_supports", [PY, rp.CHECKS / "pipe_supports.py", "--report", out], logs)
        results["list_delta"] = run_list_delta(out, "fast build")
        say("list_delta", results["list_delta"])
        for k, s in side.items():
            results[k] = s.wait()
            say(k, results[k])
        if drawings is not None:
            drawing_items, drawing_info = pf.finish_drawing_checks(drawings)
            for name, d in drawing_info.items():
                print(f"[{'ok  ' if not any(i['key'].startswith(f'drawing:{name}:') for i in drawing_items) else 'FAIL'}] "
                      f"{'check ' + name:<13}        {d['summary']}", flush=True)
            results["drawings"] = {"exit": 1 if drawing_items else 0, "seconds": round(time.time() - td, 1),
                                   "summary": f"drawings: {len(drawing_info)} drawn in check mode, "
                                              f"{len(drawing_items)} error(s)"}
    results["glb"] = view.wait()
    if results["glb"]["exit"] == 0 and not glb.exists():
        results["glb"]["exit"] = 1
        results["glb"]["summary"] += " (but no GLB was written)"
    say("glb", results["glb"])
    if glb.exists():
        print(f"model_iterate --fast: view {glb}")
    nxt = mb.next_letter(mb.last_revision())
    # CAPA 2026-11-23: printed = the hard items of the checks this build ran (and, with --supports, the lines outside
    # that check's scope); everything else is carried to acceptance in a file, with one count line
    shown = pf.build_checks_from(results, a.supports) + drawing_items
    carried = []
    if (results["lists"]["exit"] == 0 or a.keep_going) and not mb.JOB_LEVEL:
        rest = pf.collect(out, supports=a.supports, drawing_items=[], accept=False, with_build_checks=False)
        shown += [i for i in rest if i["key"].startswith("scope:")]
        carried = [i for i in rest if not i["key"].startswith("scope:")]
    carried_p = pf.write_carried(carried, out / pf.CARRIED_NAME, out.name, nxt)   # before finish() locks the folder
    rc = finish(results, started, t0, mt, newest, out, open_items=shown + carried, drawings=drawing_info)
    if a.request:
        hard = sum(1 for i in shown if i["hard"])
        mb.log_row(BUILDS, out.name, a.request, a.change,
                   checks_cell(results, f"hard {hard}; carried to acceptance {len(carried)}; "
                                        f"{time.time() - t0:.0f} s"))
        print(f"model_iterate --fast: build-log row added for {out.name}")
    report_fast(shown, carried, carried_p)
    return rc


def report_fast(shown: list[dict], carried: list[dict], carried_p: Path) -> None:
    """The end of a fast build's output (CAPA 2026-11-23): the findings of the checks it ran, the one carried line,
    then the fixed scope footer, always last."""
    pf.print_items(shown, "FAST BUILD FINDINGS (only the checks this build ran)")
    print(pf.carried_line(carried, carried_p))
    print(pf.FAST_SCOPE_FOOTER, flush=True)


def finish(results: dict, started: str, t0: float, mt: float, newest: Path, fast_dir: Path | None = None,
           open_items: list | None = None, drawings: dict | None = None) -> int:
    secs = time.time() - t0
    failed = [k for k, r in results.items() if r["exit"] != 0]
    need = ["lists", "step", "interference", "envelope", "pipe_supports", "list_delta", "glb"]
    need += [f"view_{v}" for v, _ in mb.VIEWS] if mb.JOB_LEVEL else []
    summary = {"model_id": mb.MODEL_ID, "started": started,
               "finished": dt.datetime.now().replace(microsecond=0).isoformat(sep=" "), "seconds": round(secs, 1),
               "newest_source": {"path": rp.rel(newest), "mtime": mt}, "steps": results, "failed": failed,
               "build": (fast_dir or mb.BUILD).name, "kind": "fast" if fast_dir else "full",
               "complete": fast_dir is None and all(k in results for k in need)}
    if mb.JOB_LEVEL:
        summary.update({"document_id": mb.DOC_ID, "config": rp.MODEL_CONFIG})
    if open_items is not None:
        summary["open_items"] = open_items
    if drawings:
        summary["drawing_checks"] = drawings
    # every build keeps its own summary; model_file.py reads a full build's
    (fast_dir / "iterate-summary.json" if fast_dir else mb.SUMMARY).write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n")
    mb.lock_build(fast_dir or mb.BUILD)   # a finished build is kept as it is: its files are read-only from here
    state = "PASS" if not failed else f"FAIL ({', '.join(failed)})"
    if fast_dir:
        print(f"model_iterate --fast: {state} in {secs:.0f} s -> {rp.rel(fast_dir)}; no STEP, nothing "
              f"overwritten (run without --fast before filing)")
    else:
        print(f"model_iterate: {state} in {secs / 60:.1f} min -> {rp.rel(mb.BUILD)}; nothing overwritten, nothing "
              f"filed (file it with harness/scripts/model_file.py when Bob looks at it)")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
