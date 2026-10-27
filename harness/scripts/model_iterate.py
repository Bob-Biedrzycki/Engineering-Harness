"""model_iterate.py - tier 1 of the three-tier pipeline: one full build of the skid model, every iteration.

The three-tier model pipeline (Bob, chat, 2026-10-02: make
iteration fast and close-out unattended). Skill: .claude/skills/model-iterate.

Runs, in this order (independent steps in parallel):
    1. lists        <project>/03_Working_Design/CAD/01_Master_Assembly/<MODEL-ID>/export_lists.py      takeoffs, manifest, layout note (repo venv, harness/tools/venv)
    2. step         <project>/03_Working_Design/CAD/01_Master_Assembly/<MODEL-ID>/export_step_direct.py   assembly STEP (cadgen venv)
       in parallel with step:
         interference   harness/checks/interference.py
         pipe_supports  harness/checks/pipe_supports.py --report <build>   pipe-support-calc.csv / .md
         list_delta     harness/lib/list_delta.py    list-delta.csv / .md: the model vs <project>/03_Working_Design/PID/02_Tag_Lists lists
    3. after step, in parallel:
         envelope       harness/checks/envelope.py   (measures the new STEP too)
         glb            <project>/03_Working_Design/CAD/01_Master_Assembly/<MODEL-ID>/export_glb.py
    4. looks        <project>/03_Working_Design/CAD/09_Presentation/presentation_materials.py --glb <build GLB> --looks-only: one line,
                    "looks: n of m required instruments realistic; missing: ...", materials.yaml required_looks.
                    Report only: never fails the build. Not run by --fast (its GLB is not the export's).
                    With no presentation site yet (site_revs.site_dormant: site_repo unknown or the builder
                    absent) the line reads "looks: no presentation site yet (...)" and the step passes

Writes only to <project>/03_Working_Design/Exports/build/<MODEL-ID>/ (working copy, gitignored), plus logs/ and iterate-summary.json
there. Never files, never pushes, never builds the portal. Prints one summary line per step.

    .\\harness\\tools\\venv\\Scripts\\python.exe harness\\scripts\\model_iterate.py [--keep-going] [--no-glb] [--fast [--supports]]

--fast (Bob, chat, 2026-10-10: light-weight modelling that is very fast; "The fast build should still create a
new file, and not overwrite an existing."; "I need to be able to see it ... whatever is fastest.") runs lists, list
delta, interference and the model-only envelope (~6 s) beside export_glb_fast.py, a GLB to look at
straight from the model (~1 min); no STEP. The pipe supports check runs only with --supports, given only when Bob
asks for it (Bob, chat, 2026-10-15: "The pipe support check is completley unnecessary until i request it.  do not
check until i ask."). Each fast build writes into a new folder of its own,
<project>/03_Working_Design/CAD/Fast_Builds/rev<X>/rev<X>-fast-<nnn>/ (Bob, 2026-10-10: "I would like the root Fast folder in the Job/Models
folder"; Bob, 2026-10-11: "job/models/fast/revV/revV-fast-001. that way we can still track fast changes."), <X> the
last filed revision the build starts from and <nnn> the next number for that letter (001 again after each filing),
refused if it exists, and touches nothing else: the full build's files, its iterate-summary.json and
earlier fast builds stay as they are. <project>/03_Working_Design/CAD/Fast_Builds/ is gitignored and outside the Drive store: viewing copies,
not revisions. model_file.py never sees a fast build: run the full build once before filing.

Every fast build also draws the P&ID, line segment diagram and PFD from itself in check mode (about 1-2 s each,
beside the GLB, nothing written) and ends with the running list "OPEN BEFORE REV <next>": failed checks, drawing
errors, list delta rows, components registered since the last revision but not placed, questions opened since then
(harness/lib/accept_preflight.py; Bob, chat, 2026-10-15: acceptance "should be run progamatically and
deterministically"). --request "<Bob's words>" --change "<what changed>" appends the build's fast-log row itself.

Exit 0 = every step ran and every check passed; 1 = a step or check failed (see the lines and logs/);
2 = refused (missing venv).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists()) / "harness" / "lib"))
import repo_paths as rp  # noqa: E402
if __name__ == "__main__":
    rp.require_project("model_iterate.py")   # no project yet: exit 2, nothing to build
import model_build as mb  # noqa: E402
import accept_preflight as pf  # noqa: E402

PY = rp.TOOLS / "venv" / "Scripts" / "python.exe"
PY_CADGEN = rp.TOOLS / "venv-cadgen" / "Scripts" / "python.exe"
LOGS = mb.BUILD / "logs"
FAST = rp.FAST_BUILDS   # <project>/03_Working_Design/CAD/Fast_Builds (Bob, 2026-10-10)


class Step:
    """One subprocess step: its log goes to logs/<name>.log, its summary is the first line it prints."""

    def __init__(self, name: str, cmd: list[str], logs: Path = LOGS):
        self.name, self.cmd = name, [str(c) for c in cmd]
        self.log = logs / f"{name}.log"
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
                         "a quick GLB to look at, no STEP; a new <project>/03_Working_Design/CAD/Fast_Builds/rev<X>/rev<X>-fast-<nnn>/ folder each run, "
                         "nothing overwritten")
    ap.add_argument("--supports", action="store_true",
                    help="with --fast: also run the pipe supports check (only when Bob asks for it)")
    ap.add_argument("--request", default="",
                    help="with --fast: Bob's request (his words, trimmed); appends this build's fast-log row")
    ap.add_argument("--change", default="", help="with --fast and --request: what this build changed, for the fast log")
    a = ap.parse_args()
    for exe in (PY, PY_CADGEN):
        if not exe.is_file():
            print(f"REFUSED: missing {rp.rel(exe)} (rebuild the venv from harness/requirements*.txt)", file=sys.stderr)
            return 2
    import rule_scope
    missing = rule_scope.model_missing()
    if missing:
        print(f"REFUSED: {missing}; nothing to build (the cad-design-engineer writes the model source first)",
              file=sys.stderr)
        return 2
    if a.fast:
        return fast(a)

    src_dir = rp.SKID_MODEL
    t0 = time.time()
    started = dt.datetime.now().replace(microsecond=0).isoformat(sep=" ")
    mb.BUILD.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    mt, newest = mb.newest_source()
    print(f"model_iterate: {mb.MODEL_ID} -> {rp.rel(mb.BUILD)} (newest source {rp.rel(newest)}, "
          f"{dt.datetime.fromtimestamp(mt):%Y-%m-%d %H:%M:%S})", flush=True)
    results: dict[str, dict] = {}

    # stale STEP / GLB never survive a rebuild: a failed export leaves no file, so model_file refuses it
    for p in (mb.STEP, mb.GLB):
        p.unlink(missing_ok=True)

    results["lists"] = Step("lists", [PY, src_dir / "export_lists.py"]).wait()
    say("lists", results["lists"])
    if results["lists"]["exit"] != 0 and not a.keep_going:
        print("model_iterate: STOPPED - export_lists reported model problems (fix the model, or --keep-going)")
        return finish(results, started, t0, mt, newest)

    step = Step("step", [PY_CADGEN, src_dir / "export_step_direct.py"])
    side = {"interference": Step("interference", [PY, rp.CHECKS / "interference.py"]),
            "pipe_supports": Step("pipe_supports", [PY, rp.CHECKS / "pipe_supports.py", "--report", mb.BUILD])}
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
        for k, s in after.items():
            results[k] = s.wait()
            say(k, results[k])
        if results.get("glb", {}).get("exit") == 0 and mb.GLB.exists():
            results["looks"] = run_looks(mb.GLB)
            say("looks", results["looks"])
    else:
        results["envelope"] = Step("envelope", [PY, rp.CHECKS / "envelope.py"]).wait()
        results["envelope"]["summary"] += " (model only: no new STEP)"
        say("envelope", results["envelope"])
        print("model_iterate: GLB not exported (no STEP)")
    return finish(results, started, t0, mt, newest)


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
        list_delta.write(d, folder, f"{mb.MODEL_ID} {what} {dt.datetime.now():%Y-%m-%d %H:%M}")
        n = len(d["rows"])
        return {"exit": 0, "rows": n, "seconds": round(time.time() - td, 1),
                "summary": f"list_delta: {n} row(s) - {d['n_list_tags']} list tags, {d['n_model_tags']} "
                           f"model tags, {d['n_spools']} spools ({'model and lists agree' if not n else 'see list-delta.md'})"}
    except Exception as e:  # noqa: BLE001
        return {"exit": 1, "seconds": round(time.time() - td, 1), "summary": f"list_delta: FAIL - {type(e).__name__}: {e}"}


def fast(a) -> int:
    """--fast: the ~6 s checks and a quick GLB, into a new <project>/03_Working_Design/CAD/Fast_Builds/rev<X>/rev<X>-fast-<nnn>/ folder; the STEP and the STEP-based
    envelope and GLB, nearly all of a ~6 min build, are left out. Nothing outside the new folder is written or removed."""
    # named for the filed revision the build starts from, as P&ID fast edits are (Bob, chat, 2026-10-11:
    # "job/models/fast/revV/revV-fast-001. that way we can still track fast changes.")
    base = mb.last_revision()
    if not base:
        print(f"REFUSED: no filed revision of {mb.MODEL_ID} to start a fast build from", file=sys.stderr)
        return 2
    rev_dir = FAST / f"rev{base}"
    rev_dir.mkdir(parents=True, exist_ok=True)
    pre = f"rev{base}-fast-"
    nums = [int(p.name[len(pre):]) for p in rev_dir.glob(pre + "*") if p.name[len(pre):].isdigit()]
    out = rev_dir / f"{pre}{max(nums, default=0) + 1:03d}"
    if out.exists():
        print(f"REFUSED: {rp.rel(out)} already exists (never overwritten)", file=sys.stderr)
        return 2
    logs = out / "logs"
    logs.mkdir(parents=True)
    t0 = time.time()
    started = dt.datetime.now().replace(microsecond=0).isoformat(sep=" ")
    mt, newest = mb.newest_source()
    print(f"model_iterate --fast: {mb.MODEL_ID} -> {rp.rel(out)} (newest source {rp.rel(newest)}, "
          f"{dt.datetime.fromtimestamp(mt):%Y-%m-%d %H:%M:%S})", flush=True)
    results: dict[str, dict] = {}
    # the GLB to look at (about 1 min, straight from the model, no STEP) runs beside everything else
    glb = out / f"{mb.MODEL_ID}-{out.name}.glb"
    view = Step("glb", [PY_CADGEN, rp.SKID_MODEL / "export_glb_fast.py", "--out", glb], logs)
    results["lists"] = Step("lists", [PY, rp.SKID_MODEL / "export_lists.py", "--out", out], logs).wait()
    say("lists", results["lists"])
    drawing_items, drawing_info = [], {}
    if results["lists"]["exit"] != 0 and not a.keep_going:
        print("model_iterate: STOPPED - export_lists reported model problems (fix the model, or --keep-going)")
    else:
        # the P&ID, LSD and PFD drawn from this build in check mode, beside the GLB (writes nothing)
        drawings = pf.start_drawing_checks(out, logs)
        side = {"interference": Step("interference", [PY, rp.CHECKS / "interference.py"], logs),
                "envelope": Step("envelope", [PY, rp.CHECKS / "envelope.py", "--no-step"], logs)}
        # pipe supports only when Bob asks (Bob, chat, 2026-10-15: "do not check until i ask")
        if a.supports:
            side["pipe_supports"] = Step("pipe_supports", [PY, rp.CHECKS / "pipe_supports.py", "--report", out], logs)
        results["list_delta"] = run_list_delta(out, "fast build")
        say("list_delta", results["list_delta"])
        for k, s in side.items():
            results[k] = s.wait()
            say(k, results[k])
        drawing_items, drawing_info = pf.finish_drawing_checks(drawings)
        for name, d in drawing_info.items():
            print(f"[{'ok  ' if not any(i['key'].startswith(f'drawing:{name}:') for i in drawing_items) else 'FAIL'}] "
                  f"{'check ' + name:<13}        {d['summary']}", flush=True)
    results["glb"] = view.wait()
    if results["glb"]["exit"] == 0 and not glb.exists():
        results["glb"]["exit"] = 1
        results["glb"]["summary"] += " (but no GLB was written)"
    say("glb", results["glb"])
    if glb.exists():
        print(f"model_iterate --fast: view {glb}")
    # the running list of what stands between this build and the next revision (Bob, chat, 2026-10-15)
    items = pf.build_checks_from(results, a.supports) + drawing_items
    if results["lists"]["exit"] == 0 or a.keep_going:
        items += pf.collect(out, supports=a.supports, drawing_items=[], accept=False, with_build_checks=False)
    nxt = mb.next_letter(mb.last_revision())
    rc = finish(results, started, t0, mt, newest, out, open_items=items, drawings=drawing_info)
    pf.print_items(items, f"OPEN BEFORE REV {nxt}")
    if a.request:
        fast_log_row(out, a.request, a.change, results, len(items), nxt, time.time() - t0)
    return rc


def fast_log_row(out: Path, request: str, change: str, results: dict, n_open: int, nxt: str, secs: float) -> None:
    """One row in <project>/03_Working_Design/CAD/Fast_Builds/fast-log.md under today's heading (Bob, 2026-10-10: "start to keep a running list
    in the fast folder for each revision."). Pipe supports are named only when that check ran."""
    log = FAST / "fast-log.md"
    cell = lambda s: (s or "").replace("|", "/").replace("\r", " ").replace("\n", " ").strip()  # noqa: E731
    short = {"interference": "int", "envelope": "env", "pipe_supports": "pipe_supports", "list_delta": "list delta"}
    checks = "; ".join(f"{short[k]} {'PASS' if r['exit'] == 0 else 'FAIL'}" + (f" {r['rows']}" if k == "list_delta" else "")
                       for k, r in results.items() if k in short)
    checks += f"; open before Rev {nxt}: {n_open}; {secs:.0f} s"
    text = log.read_text(encoding="utf-8") if log.exists() else "# Fast builds: running list\n"
    day = dt.date.today().isoformat()
    add = "" if f"## {day}" in text else f"\n## {day}\n\n| Build | Time | Request | Result / note | Checks |\n|---|---|---|---|---|\n"
    add += f"| {out.name} | {dt.datetime.now():%H:%M} | {cell(request)} | {cell(change)} | {cell(checks)} |\n"
    with open(log, "a", encoding="utf-8", newline="\n") as f:
        f.write(add if text.endswith("\n") else "\n" + add)
    print(f"model_iterate --fast: fast-log row added for {out.name}")


def finish(results: dict, started: str, t0: float, mt: float, newest: Path, fast_dir: Path | None = None,
           open_items: list | None = None, drawings: dict | None = None) -> int:
    secs = time.time() - t0
    failed = [k for k, r in results.items() if r["exit"] != 0]
    summary = {"model_id": mb.MODEL_ID, "started": started,
               "finished": dt.datetime.now().replace(microsecond=0).isoformat(sep=" "), "seconds": round(secs, 1),
               "newest_source": {"path": rp.rel(newest), "mtime": mt}, "steps": results, "failed": failed,
               "complete": fast_dir is None and all(k in results for k in ("lists", "step", "interference", "envelope",
                                                                           "pipe_supports", "list_delta", "glb"))}
    if open_items is not None:
        summary["open_items"] = open_items
    if drawings:
        summary["drawing_checks"] = drawings
    # a fast build keeps its own summary; mb.SUMMARY (what model_file.py reads) stays the last full build's
    (fast_dir / "iterate-summary.json" if fast_dir else mb.SUMMARY).write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n")
    state = "PASS" if not failed else f"FAIL ({', '.join(failed)})"
    if fast_dir:
        print(f"model_iterate --fast: {state} in {secs:.0f} s -> {rp.rel(fast_dir)}; no STEP, nothing "
              f"overwritten (run without --fast before filing)")
    else:
        print(f"model_iterate: {state} in {secs / 60:.1f} min; working copy only, nothing filed "
              f"(file it with harness/scripts/model_file.py when Bob looks at it)")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
