"""closeout.py - tier 3 of the three-tier pipeline: the daily close-out, on Bob's word. Does not commit.

The three-tier model pipeline (CPME practice). Skill: .claude/skills/closeout.
Run by the project-manager when Bob says to close out the day. It leaves the day ready for the one commit and
one PR, which go through harness/scripts/track.py on Bob's go (skill github-tracking).
Steps 4, 5 and 9 (the site framework: project tracker, quoting/estimating portal, landing page) are CPME practice
and dormant until Bob defines the job's site. No project yet: closeout.py refuses with exit 2.

Steps, in this order:
    1. checks       every harness/checks/*.py, as CI runs them (pid_consistency, interference, envelope,
                    pipe_supports, sanitary, tag_crosscheck, drive_pointers); first line and exit of each.
                    portal_terms.py runs at the end of step 5 instead, on the portal revision just filed
    2. frame calc   <project>/02_Engineering/06_Mechanical_Structural/frame-calc/frame_calc.py is run separately on a filed revision (as now): reports which
                    revision <project>/02_Engineering/06_Mechanical_Structural/frame-calc-results.md is for, and whether that is the newest; --frame-calc
                    reruns it (about 20 min)
    3. list delta   the newest filed model revision vs <project>/03_Working_Design/PID/02_Tag_Lists lists (harness/lib/list_delta.py). Non-empty:
                    append it to <project>/01_Design_Basis/06_Assumptions_Open_Items/pid-revision-requests.md and STOP (exit 3): the process-engineer step
                    updates the lists, or Bob makes it a P&ID revision request; rerun close-out after. Lists changed
                    since the line segment diagram / PFD were filed: says so (diagrams regenerate only then)
    4. portal media the presentation renders when one was made from the newest filed revision
                    (<project>/_work/portal-media/presentation-rev<P>/); otherwise presentation_materials.py and the EEVEE
                    studio pass portal_media.py --materials --studio into <project>/_work/portal-media/rev<X>/ if missing.
                    First the looks line for the newest filed GLB (presentation_materials.py --looks-only):
                    "looks: n of m required instruments realistic; missing: ..."; read-only, runs in --dry-run too,
                    a report in the step list and the commit body, never a failure
    5. portal       web_glbs.py --rev <X>, the 3D viewer's web GLB for the newest filed revision only (cached; Bob,
                    2026-10-12: older revisions are not rebuilt for a look change, build_portal keeps their newest
                    copy of any look; a current revision with no current-look GLB is a WARNING row, not a stop), then
                    build_portal.py --rev <X> --file: the portal filed as the next <project>/06_Issued_Revisions/Portals/project-portal/ letter
                    (skipped if one was already filed today for the same model revision); then the quoting
                    portal, --audience fabricator --file, the next <project>/06_Issued_Revisions/Portals/quoting-portal/ letter once per model
                    revision; then Mobile Optimized (2026-10-17): web_glbs.py --phone and --audience mobile --file, the
                    next <project>/06_Issued_Revisions/Portals/mobile-portal/ letter once per model revision; and build_landing.py --file, the
                    site landing page, filed only when it changed.
                    One refile flag per document, neither implies the other (2026-10-03): --refile-portal files the
                    tracker again on a day it was already filed; --refile-quoting files the quoting portal again for
                    a model revision it was already issued for
    6. Drive        drive_store.py pointers, push (every pointer whose file is not in Drive yet), verify (nothing
                    goes outside the repo before this). Push runs after the portal so the portal's large files go too.
    7. Linear loops TR-12 (Bob, 2026-10-07; harness/lib/linear_loops.py): today's <project>/_work/daily/<date>* handoffs and
                    today's Agent-to-Agent Questions.md entries with no CPM-nn ref; issues touched today with no comment today; NEXT: lines
                    naming an agent with no issue opened for it today; handoffs saying LINEAR: unavailable. Linear is
                    read from the export the project-manager writes first (<project>/_work/daily/<date>-linear.json, or
                    --linear-json). Read-only, so it runs in --dry-run too; warnings only, never a failure
    8. commit body  <project>/_work/daily/<date>-commit.md: Why, Changed IDs, Sources and rules cited, TR rows touched,
                    Drawings filed, Checks run, Linear loops, with the day's filed revisions and the --tag list; and
                    <project>/_work/daily/<date>-paths.txt, candidate paths from git status, for Bob's track.py run
    9. site plan    publish_site.py --rev <P> --quoting <Q> --landing <L> --dry-run, each the newest filed revision
                    (harness/lib/site_revs.py, shared with track.py after-merge): the presentation site publish plan
                    and the command (C-08). Never publishes on its own; track.py after-merge publishes
                    after the day's PR merges, on the day's go

Steps 4, 5 and 9 and the portal wording lint are the presentation site's. While the project has none
(project.yaml site_repo `unknown`, or the builders are not in <project>/03_Working_Design/CAD/09_Presentation/;
site_revs.site_dormant), each prints "no presentation site yet" and passes (CPME practice: the framework stays for
the planned site). A missing <project>/01_Design_Basis/06_Assumptions_Open_Items/pid-revision-requests.md is started with
its one-line header when step 3 first appends to it.

    .\\harness\\tools\\venv\\Scripts\\python.exe harness\\scripts\\closeout.py --dry-run     list every step, push nothing
    .\\harness\\tools\\venv\\Scripts\\python.exe harness\\scripts\\closeout.py --bob-go "<the day's go>"   the real run
Normally run for you by `track.py daily` (skill github-tracking), with the day's one go (Bob, 2026-10-07).

Checks are judged as CI judges them (harness/scripts/run_checks.sh; Bob, 2026-10-07: "The PR should not be flagging
design findings."): exit 0 PASS; 2 NOT IMPLEMENTED (warning); 1 with the "<name>: FAIL" summary = design FINDINGS
(warning), or FAIL for a repo-integrity check (HARD_FAIL_CHECKS); anything else, or a traceback, = ERROR (broken).

Exit 0 = close-out done (design findings, if any, are listed as warnings); 1 = done, but a step failed, a check is
broken or a repo-integrity check failed (listed); 2 = refused; 3 = stopped at the list delta.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists()) / "harness" / "lib"))
import repo_paths as rp  # noqa: E402
if __name__ == "__main__":
    rp.require_project("closeout.py")   # no project yet: exit 2 (close-out works on the active project)
import model_build as mb  # noqa: E402
import site_revs  # noqa: E402

PY = rp.TOOLS / "venv" / "Scripts" / "python.exe"
# Repo-integrity checks whose FAIL is a failure, not a design finding. Mirrors HARD_FAIL_CHECKS in
# harness/scripts/run_checks.sh (CI); harness/tests/test_track_daily.py fails if the two lists differ.
HARD_FAIL_CHECKS = {"drive_pointers"}
BLENDER = Path(r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe")
PRESENT = rp.PRESENTATIONS
PORTAL_REVS = rp.PORTAL_FILED / "revisions.csv"
QUOTING_REVS = rp.QUOTING_FILED / "revisions.csv"
MOBILE_REVS = rp.MOBILE_FILED / "revisions.csv"
PRR = rp.OPEN_ITEMS / "pid-revision-requests.md"
PRR_HEADER = "# P&ID revision requests\n"   # the seed's one-line header (harness/templates/project-folder)
PORTAL_TERMS = rp.CHECKS / "portal_terms.py"
LOG = rp.DAILY


def rcsv(p: Path) -> list[dict]:
    if not p.is_file():
        return []
    with open(p, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def run(cmd: list, log: Path | None = None, timeout: int | None = None) -> tuple[int, str]:
    r = subprocess.run([str(c) for c in cmd], cwd=rp.REPO, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    out = (r.stdout or "") + (r.stderr or "")
    if log:
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(out, encoding="utf-8")
    return r.returncode, out


def first(out: str) -> str:
    return next((ln.strip() for ln in out.splitlines() if ln.strip()), "(no output)")


def head(n: int, title: str) -> None:
    print(f"\n== {n}. {title}", flush=True)


class Report:
    def __init__(self):
        self.checks: list[tuple[str, int, str]] = []
        self.steps: list[tuple[str, str]] = []
        self.failed: list[str] = []
        self.linear: list[str] | None = None   # step 7 finding lines ([] = nothing open; None = step not run)

    def step(self, name: str, result: str, ok: bool = True):
        self.steps.append((name, result))
        if not ok:
            self.failed.append(name)
        print(f"   [{'ok  ' if ok else 'FAIL'}] {name}: {result}", flush=True)


# ------------------------------------------------------------------ steps
def step_checks(R: Report, dry: bool, date: str) -> None:
    head(1, "checks (every harness/checks/*.py, as CI)")
    # portal_terms lints the newest filed portal, so it runs after step 5 (step_portal_terms), not here
    checks = sorted(p for p in rp.CHECKS.glob("*.py") if p.name != PORTAL_TERMS.name)
    if dry:
        for p in checks:
            print(f"   would run {rp.rel(p)}")
        print(f"   {rp.rel(PORTAL_TERMS)} runs after step 5, on the portal revision just filed")
        return
    for p in checks:
        run_check(R, p, date)


def check_status(name: str, rc: int, out: str) -> str:
    """PASS, NOT IMPLEMENTED, FINDINGS, FAIL or ERROR, exactly as harness/scripts/run_checks.sh classifies a check."""
    if re.search(r"^Traceback \(most recent call last\)", out, re.M):
        return "ERROR"
    if rc == 0:
        return "PASS"
    if rc == 2:
        return "NOT IMPLEMENTED"
    if rc == 1 and re.search(rf"^{re.escape(name)}: FAIL", out, re.M):
        return "FAIL" if name in HARD_FAIL_CHECKS else "FINDINGS"
    return "ERROR"


def run_check(R: Report, p: Path, date: str) -> None:
    t0 = time.time()
    rc, out = run([PY, p], LOG / f"{date}-checks" / f"{p.stem}.log")
    line = first(out)
    R.checks.append((p.stem, rc, line))
    status = check_status(p.stem, rc, out)
    # design findings and NOT IMPLEMENTED stubs are warnings, never a failure (CI policy, Bob 2026-10-07)
    if status in ("FAIL", "ERROR"):
        R.failed.append(p.stem)
    tag = {"PASS": "ok  ", "NOT IMPLEMENTED": "WARN", "FINDINGS": "WARN"}.get(status, "FAIL")
    print(f"   [{tag}] {time.time() - t0:6.1f} s  {line}" + ("  (design findings: reported, not blocking)"
                                                           if status == "FINDINGS" else ""), flush=True)


def step_portal_terms(R: Report, dry: bool, date: str) -> None:
    """The portal wording lint, after step 5 so it reads the revision just filed (with no --dir it takes the
    newest <project>/06_Issued_Revisions/Portals/project-portal revision)."""
    print("   portal wording lint (portal_terms.py) on the newest filed portal:", flush=True)
    if dry:
        print(f"   would run {rp.rel(PORTAL_TERMS)}")
        return
    run_check(R, PORTAL_TERMS, date)


def step_frame_calc(R: Report, dry: bool, newest: str | None, run_it: bool) -> None:
    head(2, "frame calc (run separately on a filed revision)")
    res = rp.FRAME_CALC.parent / "frame-calc-results.md"
    if not newest and not res.is_file() and not (rp.FRAME_CALC / "frame_calc.py").is_file():
        msg = "no frame calc and no filed model revision yet; nothing to compare"
        print(f"   {msg}") if dry else R.step("frame calc", msg)
        return
    text = res.read_text(encoding="utf-8") if res.is_file() else ""
    m = re.search(r"Rev (\w+): (?:[\w.-]+ )?Rev (\w+)", text)   # "Rev B: model Rev K" (an optional model word)
    basis = f"calc Rev {m.group(1)} on model Rev {m.group(2)}" if m else "basis not found"
    calc = rp.FRAME_CALC / "frame_calc.py"
    src = calc.read_text(encoding="utf-8") if calc.is_file() else ""   # a new project has no frame calc yet
    # the calc names its input model: the retired model when its source reads it (project.yaml retired_model_id)
    model = (rp.RETIRED_MODEL_ID if rp.RETIRED_MODEL_ID and re.search(r"MODEL_ID\s*=\s*RP\.RETIRED_MODEL_ID", src)
             else mb.MODEL_ID)
    stale = not (model == mb.MODEL_ID and m and m.group(2) == newest)
    msg = (f"{rp.rel(res)}: {basis} ({model}); newest filed {mb.MODEL_ID} Rev {newest}"
           + (" - NOT the newest revision: rerun is Bob's call (frame_calc.py names its input revision; --frame-calc reruns as is)"
              if stale else " - current"))
    if dry:
        print(f"   {msg}" + ("\n   would rerun frame_calc.py (--frame-calc)" if run_it else ""))
        return
    R.step("frame calc", msg, ok=True)
    if run_it:
        rc, out = run([PY, rp.FRAME_CALC / "frame_calc.py"], LOG / "frame-calc.log")
        R.step("frame calc rerun", first(out), ok=rc == 0)


def step_list_delta(R: Report, dry: bool, newest: str | None, date: str) -> bool:
    """True = stop here (non-empty delta)."""
    head(3, f"list delta ({mb.MODEL_ID} Rev {newest} vs {rp.rel(rp.DATA)} lists)")
    import list_delta
    if not newest:
        print("   no filed revision")
        return False
    d = list_delta.compute(mb.FILED, f"{mb.MODEL_ID}-rev{newest}-")
    n = len(d["rows"])
    lsd = [r for r in rcsv(rp.DRAWINGS / "line-segment-diagram" / "revisions.csv")]
    pfd = [r for r in rcsv(rp.DRAWINGS / "process-flow-diagram" / "revisions.csv")]
    rc, st = run(["git", "status", "--porcelain", "--", rp.rel(rp.DATA)])
    changed_lists = sorted({ln[3:].strip() for ln in st.splitlines() if ln[3:].strip().endswith("-list.csv")})
    if changed_lists:
        print(f"   lists changed since the last commit: {', '.join(changed_lists)}; the line segment diagram "
              f"(Rev {lsd[-1]['revision'] if lsd else '-'}) and PFD (Rev {pfd[-1]['revision'] if pfd else '-'}) "
              "regenerate only when a list change touches them (process-engineer step)")
    if not n:
        msg = f"0 rows - the model and the lists agree ({d['n_list_tags']} list tags, {d['n_spools']} spools)"
        if dry:
            print(f"   {msg}")
        else:
            R.step("list delta", msg)
        return False
    marker = f"<!-- closeout list-delta {mb.MODEL_ID} Rev {newest} {date} -->"
    body = [marker, f"## List delta from {mb.MODEL_ID} Rev {newest} (close-out {date}, harness/scripts/closeout.py)", "",
            "Generated: the model leads and the lists are the formal input. Each row becomes a list update "
            "(process-engineer) or a P&ID revision request (Bob). Status: open.", "",
            "| kind | subject | line | model | lists | detail |", "|---|---|---|---|---|---|"]
    body += [f"| {r['kind']} | {r['subject']} | {r['line_no']} | {r['model']} | {r['lists']} | {r['detail']} |" for r in d["rows"]]
    text = PRR.read_text(encoding="utf-8") if PRR.is_file() else PRR_HEADER
    if dry:
        print(f"   {n} row(s): would append them to {rp.rel(PRR)} and STOP")
        for r in d["rows"]:
            print(f"     {r['kind']}: {r['subject']} {r['detail']}")
        return False
    if marker not in text:
        PRR.parent.mkdir(parents=True, exist_ok=True)
        PRR.write_text(text.rstrip("\n") + "\n\n" + "\n".join(body) + "\n", encoding="utf-8", newline="\n")
        where = f"appended to {rp.rel(PRR)}"
    else:
        where = f"already in {rp.rel(PRR)}"
    R.step("list delta", f"{n} row(s), {where}", ok=False)
    print(f"\ncloseout: STOPPED at the list delta. The process-engineer updates <project>/03_Working_Design/PID/02_Tag_Lists lists (or Bob turns the rows into "
          f"a P&ID revision request), then rerun closeout.py.")
    return True


def presentation_media(rev: str) -> Path | None:
    """A presentation render folder (<project>/_work/portal-media/presentation-rev<P>/) made from design Rev <rev>,
    complete with the hero still and the web GLB; its material-assignments.json names the design revision.
    Order (2026-10-03): the newest presentation letter first, and within it the highest re-render -r<n>
    (presentation-revA-r2, Quote Site Rev 2 media, before presentation-revA); a name sort would put -r10 before -r2."""
    import json
    import re

    def order(d: Path):
        m = re.fullmatch(r"presentation-rev([A-Z]+)(?:-r(\d+))?", d.name)
        return (len(m.group(1)), m.group(1), int(m.group(2) or 1)) if m else (0, "", 0)

    for d in sorted((p for p in rp.PORTAL_MEDIA.glob("presentation-rev*") if p.is_dir()), key=order, reverse=True):
        a = d / "material-assignments.json"
        try:
            src = json.loads(a.read_text(encoding="utf-8")).get("source") or {}
        except (OSError, ValueError):
            continue
        if src.get("design_revision") == rev and (d / "hero-iso-front-floor.png").is_file() and (d / "skid-web.glb").is_file():
            return d
    return None


def media_dir(rev: str) -> Path:
    return presentation_media(rev) or rp.PORTAL_MEDIA / f"rev{rev}"


def step_looks(R: Report, newest: str) -> None:
    """The required_looks line for the newest filed GLB (presentation_materials.py --looks-only; Bob
    2026-10-12). Read-only, so it runs in --dry-run too; a report, never a failure (CLAUDE.md: checks report)."""
    glb = mb.FILED / f"{mb.MODEL_ID}-rev{newest}.glb"
    if not glb.is_file():
        R.step("looks", f"not checked: {rp.rel(glb)} not here (drive_store.py pull)", ok=True)
        return
    rc, out = run([PY, PRESENT / "presentation_materials.py", "--glb", glb, "--looks-only"],
                  LOG / f"looks-rev{newest}.log")
    line = next((ln.strip() for ln in out.splitlines() if ln.strip().startswith("looks:")), None)
    # the step prints as "looks: Rev <X>: n of m required instruments realistic; missing: ..."
    R.step("looks", f"Rev {newest}: " + (line[len("looks:"):].strip() if line else f"not resolved (exit {rc}): {first(out)}"),
           ok=True)


def dormant(R: Report, dry: bool, name: str, why: str) -> None:
    """A presentation-site step on a project with no site yet: say so and pass (CPME practice)."""
    msg = f"{why}; passed"
    print(f"   {msg}") if dry else R.step(name, msg)


def step_media(R: Report, dry: bool, newest: str) -> None:
    head(4, f"portal media for Rev {newest}")
    why = site_revs.site_dormant(("presentation_materials.py", "portal_media.py"))
    if why:
        dormant(R, dry, "portal media", why)
        return
    step_looks(R, newest)
    out = media_dir(newest)
    if (out / "hero-iso-front-floor.png").is_file() and (out / "skid-web.glb").is_file():
        msg = f"present in {rp.rel(out)}"
        print(f"   {msg}") if dry else R.step("portal media", msg)
        return
    # from G1 (Bob, 2026-10-02) every render uses the materials map: resolve it, then the fast EEVEE studio pass
    glb = mb.FILED / f"{mb.MODEL_ID}-rev{newest}.glb"
    resolve = [PY, PRESENT / "presentation_materials.py", "--rev", newest, "--out", out.resolve()]
    cmd = [BLENDER, "-b", "-P", (PRESENT / "portal_media.py").resolve(), "--", glb.resolve(), out.resolve(),
           "--materials", (out / "materials.json").resolve(), "--studio"]
    if dry:
        print(f"   missing; would run: {' '.join(str(c) for c in resolve)}\n   then: {' '.join(str(c) for c in cmd)}")
        return
    if not BLENDER.is_file() or not glb.is_file():
        R.step("portal media", f"cannot render: {'Blender' if not BLENDER.is_file() else rp.rel(glb)} missing", ok=False)
        return
    t0 = time.time()
    rc, o = run(resolve, LOG / f"portal-materials-rev{newest}.log")
    if rc != 0:
        R.step("portal media", f"materials map did not resolve (exit {rc}); see {rp.rel(LOG)}", ok=False)
        return
    rc, o = run(cmd, LOG / f"portal-media-rev{newest}.log")
    R.step("portal media", f"Blender exit {rc} in {(time.time() - t0) / 60:.1f} min -> {rp.rel(out)}", ok=rc == 0)


def step_portal(R: Report, dry: bool, newest: str, date: str, refile: bool, refile_quoting: bool = False) -> None:
    head(5, "portal (build_portal.py --file)")
    why = site_revs.site_dormant(("build_portal.py", "web_glbs.py"))
    if why:
        dormant(R, dry, "portal", why)
        return
    rows = rcsv(PORTAL_REVS)
    last = rows[-1] if rows else None
    note = f"Close-out {date} model {newest}"[:32]
    nxt = mb.next_letter(last["revision"] if last else None)
    done_today = [r for r in rows if r["file_date"].startswith(date) and r["description"].startswith(f"{mb.MODEL_ID} Rev {newest};")]
    if done_today and not refile:
        msg = f"project-portal Rev {done_today[-1]['revision']} already filed today for Rev {newest}; not refiled (--refile-portal)"
        print(f"   {msg}") if dry else R.step("portal", msg)
        step_quoting(R, dry, newest, date, refile_quoting)
        return
    cmd = [PY, PRESENT / "build_portal.py", "--rev", newest, "--media", media_dir(newest), "--out", rp.PORTAL_WORK,
           "--file", "--note", note]
    # the viewer's web GLB for the newest filed revision only (Bob, 2026-10-12: "do not worry about the last 10
    # revisions that need rebuilding ... I just want to be very certain that the next model that goes up on the website
    # displays correctly."). Older revisions keep the copy they have, of any look (build_portal.older_look_copy)
    wg = [PY, PRESENT / "web_glbs.py", "--rev", newest]
    if dry:
        rc, out = run(wg + ["--dry-run"])
        print(f"   web GLB for Rev {newest} only (web_glbs.py --rev {newest}): "
              + "; ".join(ln.split(None, 1)[1].strip() for ln in out.splitlines() if ln.strip())[:600])
        print(f"   would build and file project-portal Rev {nxt}, note \"{note}\":\n   {' '.join(str(c) for c in cmd)}")
        step_quoting(R, True, newest, date, refile_quoting)
        return
    rc, out = run(wg, LOG / f"{date}-web-glbs.log")
    R.step("web GLB", f"web_glbs.py --rev {newest} exit {rc}: "
           + ("up to date" if "up to date" in out else "made" if ("Blender" in out or "copied" in out) else first(out)),
           ok=rc == 0)
    rc, out = run(cmd, LOG / f"{date}-portal.log")
    filed = [ln for ln in out.splitlines() if ln.startswith("filed ")]
    R.step("portal", filed[-1] if filed else first(out), ok=rc == 0 and bool(filed))
    report_web_glb(R, out, "portal")
    step_quoting(R, False, newest, date, refile_quoting)


def report_web_glb(R: Report, out: str, what: str) -> None:
    """build_portal.py's web GLB lines as report rows: a WARNING that the current revision has no current-look
    GLB (report, not stop), and how many older revisions kept an older look."""
    for ln in out.splitlines():
        if ln.startswith("WARNING web GLB for the current revision"):
            R.step(f"{what} web GLB", ln, ok=True)
    kept = sum(ln.startswith("web GLB for ") and "older look kept" in ln for ln in out.splitlines())
    if kept:
        R.step(f"{what} web GLB", f"{kept} older revision(s) kept an older-look web GLB (not rebuilt; Bob, 2026-10-12)",
               ok=True)


def step_quoting(R: Report, dry: bool, newest: str, date: str, refile: bool) -> None:
    """The quoting portal (fabricator audience), filed as the next <project>/06_Issued_Revisions/Portals/quoting-portal/ letter once per
    model revision (an issue for quotation follows the design, not the day), and the site landing page, filed as the
    next <project>/06_Issued_Revisions/Portals/portal-landing/ letter only when it changed."""
    rows = rcsv(QUOTING_REVS)
    issued = [r for r in rows if f"; {mb.MODEL_ID} Rev {newest};" in r.get("description", "")]
    nxt = mb.next_letter(rows[-1]["revision"] if rows else None)
    note = f"Issue for model Rev {newest}"[:32]
    cmd = [PY, PRESENT / "build_portal.py", "--rev", newest, "--media", media_dir(newest), "--out", rp.WORK / "quoting",
           "--audience", "fabricator", "--file", "--note", note]
    land = [PY, PRESENT / "build_landing.py", "--out", rp.WORK / "site-landing", "--file", "--note", f"Close-out {date}"[:32]]
    if dry:
        if issued and not refile:
            print(f"   quoting-portal Rev {issued[-1]['revision']} already issued for model Rev {newest}; not refiled (--refile-quoting)")
        else:
            print(f"   would build and file quoting-portal Rev {nxt}, note \"{note}\":\n   {' '.join(str(c) for c in cmd)}")
        step_mobile(R, True, newest, date)
        print(f"   would build the landing page and file it only if it changed:\n   {' '.join(str(c) for c in land)}")
        return
    if issued and not refile:
        R.step("quoting portal", f"quoting-portal Rev {issued[-1]['revision']} already issued for model Rev {newest}; not refiled (--refile-quoting)")
    else:
        # the phone GLB first: the estimating portal carries a scrubbed copy for phones (2026-10-17)
        rc, out = run([PY, PRESENT / "web_glbs.py", "--phone", "--rev", newest], LOG / f"{date}-phone-glb.log")
        R.step("phone GLB", f"web_glbs.py --phone --rev {newest} exit {rc}", ok=rc == 0)
        rc, out = run(cmd, LOG / f"{date}-quoting.log")
        filed = [ln for ln in out.splitlines() if ln.startswith("filed ")]
        R.step("quoting portal", filed[-1] if filed else first(out), ok=rc == 0 and bool(filed))
        report_web_glb(R, out, "quoting portal")
    step_mobile(R, False, newest, date)
    rc, out = run(land, LOG / f"{date}-landing.log")
    R.step("landing page", [ln for ln in out.splitlines() if ln.strip()][-1] if out.strip() else "(no output)", ok=rc == 0)


def step_mobile(R: Report, dry: bool, newest: str, date: str) -> None:
    """Mobile Optimized (Bob, chat, 2026-10-17: "a 3rd page selection from home called Mobile Optimized that will
    produce optimized formats for everything in the project tracker"): the phone web GLB (web_glbs.py --phone, newest
    revision only), then the tracker for phones filed as the next <project>/06_Issued_Revisions/Portals/mobile-portal/ letter, once per model
    revision. It shows the current revision only, so a new model revision is what makes a new one."""
    rows = rcsv(MOBILE_REVS) if MOBILE_REVS.is_file() else []
    issued = [r for r in rows if r.get("description", "").startswith(f"{mb.MODEL_ID} Rev {newest};")]
    nxt = mb.next_letter(rows[-1]["revision"] if rows else None)
    note = f"Mobile for model Rev {newest}"[:32]
    wg = [PY, PRESENT / "web_glbs.py", "--phone", "--rev", newest]
    cmd = [PY, PRESENT / "build_portal.py", "--rev", newest, "--media", media_dir(newest), "--out", rp.WORK / "mobile",
           "--audience", "mobile", "--file", "--note", note]
    if issued:
        msg = f"mobile-portal Rev {issued[-1]['revision']} already filed for model Rev {newest}; not refiled"
        print(f"   {msg}") if dry else R.step("mobile portal", msg)
        return
    if dry:
        print(f"   would make the phone GLB ({' '.join(str(c) for c in wg[2:])}) and build and file mobile-portal Rev {nxt}, "
              f"note \"{note}\":\n   {' '.join(str(c) for c in cmd)}")
        return
    rc, out = run(wg, LOG / f"{date}-phone-glb.log")
    R.step("phone GLB", f"web_glbs.py --phone --rev {newest} exit {rc}: "
           + ("up to date" if "up to date" in out else "made" if ("Blender" in out or "copied" in out) else first(out)), ok=rc == 0)
    rc, out = run(cmd, LOG / f"{date}-mobile.log")
    filed = [ln for ln in out.splitlines() if ln.startswith("filed ")]
    R.step("mobile portal", filed[-1] if filed else first(out), ok=rc == 0 and bool(filed))


def step_drive(R: Report, dry: bool, date: str) -> None:
    head(6, "Google Drive store: pointers, push, verify")
    ds = rp.SCRIPTS / "drive_store.py"
    if dry:
        rc, out = run([PY, ds, "push", "--dry-run"])
        if rc == 2:
            print(f"   push cannot reach the store: {out.strip()}")
            ptrs = sorted(rp.JOBS.rglob("*.drive"))
            print(f"   {len(ptrs)} pointer(s) exist; which are not yet in Drive is unknown until the store is reachable")
        else:
            print("   would run drive_store.py pointers, then push:")
            print("   " + "\n   ".join(out.strip().splitlines()))
            print("   then drive_store.py verify")
        return
    for sub, name in ((["pointers"], "pointers"), (["push"], "push"), (["verify"], "verify")):
        rc, out = run([PY, ds, *sub], LOG / f"{date}-drive-{name}.log")
        lines = [ln for ln in out.splitlines() if ln.strip()]
        summ = next((ln for ln in reversed(lines) if re.match(r"^(pointers|push|verify|REFUSED)", ln.strip())), first(out))
        R.step(f"drive {name}", summ.strip(), ok=rc == 0)
        if rc != 0 and name == "push":
            break


def filed_today(date: str) -> dict[str, list[tuple[str, str, str]]]:
    """{'models': [(doc, rev, note)], 'drawings': [...], 'reviews': [...]} from every revisions.csv, rows dated today."""
    out = {"models": [], "drawings": [], "reviews": []}
    for kind, root in (("models", rp.MODELS), ("drawings", rp.DRAWINGS), ("reviews", rp.PORTALS)):
        for p in sorted(root.rglob("revisions.csv")):
            seen = set()
            for r in rcsv(p):
                if r.get("file_date", "").startswith(date) and (r["document_id"], r["revision"]) not in seen:
                    seen.add((r["document_id"], r["revision"]))
                    out[kind].append((r["document_id"], r["revision"], r.get("notes", "")))
    return out


def step_linear_loops(R: Report, dry: bool, date: str, export: Path | None) -> None:
    """TR-12 loop-closing audit (Bob, 2026-10-07). Read-only, so it runs in --dry-run too. Every finding is a
    warning: recorded with ok=True and never added to R.failed, so it cannot change the exit code."""
    head(7, "Linear loops (TR-12; read-only, warnings only)")
    import linear_loops as LL
    p = Path(export) if export else LL.export_path(LOG, date)

    def show(q: Path) -> str:   # --linear-json may name a file outside the repo, where rp.rel raises
        try:
            return rp.rel(q)
        except ValueError:
            return str(q)
    try:
        hand = LL.read_handoffs(LOG, date)
        q_p = rp.AGENT_QUESTIONS
        questions = (LL.question_entries_dated(q_p.read_text(encoding="utf-8", errors="replace"), date)
                     if q_p.is_file() else {})
        linear = LL.load_linear_export(p)
        reason = None if linear is not None else (
            f"export at {show(p)} unreadable or not the documented shape" if p.is_file() else f"no export at {show(p)}")
        lines = LL.finding_lines(LL.audit(hand, questions, linear, date, unavailable_reason=reason))
        scope = f"{len(hand)} handoff file(s), {len(questions)} question entr{'y' if len(questions) == 1 else 'ies'} dated {date}"
    except Exception as e:  # noqa: BLE001 - the audit never blocks close-out
        lines, scope = [f"LINEAR: unavailable (audit error: {type(e).__name__}: {e})"], "audit error"
    R.linear = lines
    print(f"   read {scope}; Linear export {show(p)}", flush=True)
    for ln in lines:
        print(f"   [WARN] {ln}", flush=True)
    R.step("Linear loops", "nothing open" if not lines else
           f"{len(lines)} warning(s){' (dry run: no commit body written)' if dry else ', listed in the commit body'}", ok=True)


def step_commit_body(R: Report, dry: bool, date: str) -> None:
    head(8, "commit body skeleton and candidate paths (for Bob's track.py run; no commit)")
    body_p, paths_p = LOG / f"{date}-commit.md", LOG / f"{date}-paths.txt"
    if dry:
        print(f"   would write {rp.rel(body_p)} and {rp.rel(paths_p)}")
        return
    f = filed_today(date)
    tags = [f"{d}-rev{r}" for d, r, _ in f["drawings"]]
    rc, st = run(["git", "status", "--porcelain", "-uall"])
    paths, removed = [], []
    for ln in st.splitlines():
        code, rest = ln[:2], ln[3:].strip().strip('"')
        if " -> " in rest:
            rest = rest.split(" -> ", 1)[1].strip('"')
        if rest.startswith((rp.rel(rp.WORK) + "/", rp.rel(rp.EXPORTS) + "/", "harness/tools/")):
            continue
        (removed if "D" in code else paths).append(rest)
    L = [f"<area>: <what changed, at most 72 characters>", "",
         "**Why**", "<fill: Bob's direction for the day, quoted with dates>", "",
         "**Changed IDs**"]
    L += [f"- {d} Rev {r} filed ({n})" for d, r, n in f["models"]] or ["- no model revision filed today"]
    L += [f"- {d} Rev {r} filed ({n})" for d, r, n in f["reviews"]]
    L += ["- <fill: DEC, Q, list rows, rules changed>", "",
          "**Sources and rules cited**", "<fill: design rule ids, standards, Bob's chat dates>", "",
          "**TR rows touched**", "- TR-11 (documented commit, explicit paths)"]
    if f["models"] or f["drawings"] or f["reviews"]:
        L.append("- TR-08 (every filed revision new, read-only, sha256 in revisions.csv)")
    if f["drawings"]:
        L.append("- TR-06, TR-07 (DWG + PDF from the DWG, revision block row and clouds)")
    L += ["- <fill: other rows the day's work touched>", "", "**Drawings filed**"]
    L += [f"- {t} ({n})" for (d, r, n), t in zip(f["drawings"], tags)] or ["- none"]
    L += ["", "**Checks run**"]
    L += [f"- {line} (exit {rc_})" for _n, rc_, line in R.checks] or ["- checks not run"]
    L += [f"- {name}: {res}" for name, res in R.steps]
    L += ["", "**Linear loops**"]
    L += ([f"- {ln}" for ln in R.linear] or ["- none open"]) if R.linear is not None else ["- not run"]
    L += ["", f"<!-- track.py daily-commit --date {date} --paths-file {rp.rel(paths_p)} --message-file <this file, edited>"
          + "".join(f" --tag {t}" for t in tags) + ' --bob-go "<Bob\'s words>" -->']
    LOG.mkdir(parents=True, exist_ok=True)
    body_p.write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")
    paths_p.write_text("# CANDIDATE paths from git status (review: other sessions share this checkout).\n"
                       "# Deleted paths are not here; name them to Bob:\n"
                       + "".join(f"#   deleted: {p}\n" for p in removed) + "\n".join(paths) + "\n",
                       encoding="utf-8", newline="\n")
    R.step("commit body", f"{rp.rel(body_p)}, {rp.rel(paths_p)} ({len(paths)} candidate paths, {len(tags)} drawing tag(s))")


def step_site_plan(R: Report, dry: bool) -> None:
    head(9, "presentation site publish plan (publish_site.py --dry-run; track.py after-merge publishes)")
    why = site_revs.site_dormant()
    if why:
        dormant(R, dry, "site plan", why)
        return
    revs = site_revs.newest()
    if not revs["rev"]:
        print("   no filed portal revision")
        return
    args = site_revs.publish_args(revs)
    if dry:
        print(f"   would run publish_site.py {' '.join(args)} --dry-run; track.py after-merge publishes after the merge")
        return
    rc, out = run([PY, rp.SCRIPTS / "publish_site.py", *args, "--dry-run"])
    print("   " + "\n   ".join(out.strip().splitlines()))
    R.step("site plan", f"publish_site.py {' '.join(args)}: dry run exit {rc}; published by track.py after-merge "
           "on the day's go", ok=rc == 0)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true", help="list every step and the pointers push would copy; change nothing")
    ap.add_argument("--date", default=dt.date.today().isoformat(), help="close-out date (default today)")
    ap.add_argument("--frame-calc", action="store_true", help="also rerun <project>/02_Engineering/06_Mechanical_Structural/frame-calc/frame_calc.py (about 20 min)")
    ap.add_argument("--refile-portal", action="store_true",
                    help="file the project tracker (project-portal) even if it was filed today for this rev; the quoting portal is not affected")
    ap.add_argument("--refile-quoting", action="store_true",
                    help="file the quoting portal again even if it was already issued for this rev; the tracker is not affected")
    ap.add_argument("--linear-json", type=Path, default=None,
                    help="the Linear export for step 7 (default <project>/_work/daily/<date>-linear.json, written by the project-manager)")
    ap.add_argument("--bob-go", default=None,
                    help="the day's one go, quoted verbatim (<project>/_work/daily/<date>-go.txt; track.py daily passes it); recorded in the log")
    a = ap.parse_args()
    if not PY.is_file():
        print(f"REFUSED: missing {rp.rel(PY)}", file=sys.stderr)
        return 2
    newest = mb.last_revision()
    t0 = time.time()
    print(f"closeout {a.date}{' (DRY RUN: nothing run, written or pushed)' if a.dry_run else ''}: "
          f"{mb.MODEL_ID} newest filed Rev {newest}; no commit, no PR (track.py on Bob's go)"
          + (f"\nBob's go (the day's one go): \"{a.bob_go.strip()}\"" if a.bob_go and a.bob_go.strip() else ""))
    R = Report()
    step_checks(R, a.dry_run, a.date)
    step_frame_calc(R, a.dry_run, newest, a.frame_calc)
    if step_list_delta(R, a.dry_run, newest, a.date):
        return 3
    if newest:
        step_media(R, a.dry_run, newest)
        step_portal(R, a.dry_run, newest, a.date, a.refile_portal, a.refile_quoting)
    step_portal_terms(R, a.dry_run, a.date)
    step_drive(R, a.dry_run, a.date)
    step_linear_loops(R, a.dry_run, a.date, a.linear_json)   # read-only: runs for real in --dry-run too
    step_commit_body(R, a.dry_run, a.date)
    step_site_plan(R, a.dry_run)
    secs = time.time() - t0
    if a.dry_run:
        print(f"\ncloseout: dry run listed 9 steps in {secs:.0f} s; the real run is Bob's call")
        return 0
    state = "done" if not R.failed else f"done with failures: {', '.join(R.failed)}"
    print(f"\ncloseout: {state} in {secs / 60:.1f} min. Next: the commit and PR with the day's go "
          "(track.py daily runs them straight after this; skill github-tracking).")
    return 0 if not R.failed else 1


if __name__ == "__main__":
    sys.exit(main())
