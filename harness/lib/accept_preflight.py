"""accept_preflight - what still stands between a model build and its acceptance as the next revision.

Bob, chat, 2026-10-15, after the Rev Y acceptance took 82 min (filed 4 times, withdrawn 3 times, open items found one
at a time): "they should be run progamatically and deterministically. A P&ID revision should be part of the package."
One function lists every open item, the same way every time, so nothing is discovered after filing:

    hard   a check failed (lists, interference, envelope, pipe supports, STEP/GLB), or a drawing generator reports an
           error or layout issue (it refuses to file the P&ID, line segment diagram or PFD). Nothing can be filed.
    open   the model and the lists disagree (list delta rows); a routed line outside the pipe support check's scope
           (STR-PS-002 applies_to service classes, PIPE-SVC-001; only with supports); a component registered since the
           last filed revision but not in the model; a question (Q-nnnn) opened since the last filed revision and still open;
           sanitary.py or pid_consistency.py failing (accept only).

Used by harness/scripts/model_accept.py (the acceptance package: every item, before anything is filed) and
harness/scripts/model_iterate.py --fast. A fast build prints only the hard items of the checks it ran; the open items
go to carried-to-acceptance.md in its folder with one count line (write_carried, carried_line) and the fixed
FAST_SCOPE_FOOTER (CAPA 2026-11-23; Bob, chat: "Planset updates should not be of concern or worry when making model
edits. When the model is accepted, thats when the plans should be updated."). Reports only; the callers decide what
stops.
"""
from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
from pathlib import Path

import repo_paths as rp
import components
import model_build as mb
import rule_scope

PY = rp.TOOLS / "venv" / "Scripts" / "python.exe"
DRAWINGS = [("P&ID", "model-to-pid.py", rp.PID_DOC_ID if rp.HAS_PROJECT else "unknown"),
            ("LSD", "line-segment-diagram.py", "line-segment-diagram"),
            ("PFD", "process-flow-diagram.py", "process-flow-diagram")]
CHECK_STEPS = ["lists", "interference", "envelope", "pipe_supports", "step", "glb"]


def _rel(p: Path) -> str:
    try:
        return rp.rel(p)
    except ValueError:
        return str(p)


def item(key: str, text: str, hard: bool = False) -> dict:
    return {"key": key, "text": text, "hard": hard}


def _rows(p: Path) -> list[dict]:
    if not p.is_file():
        return []
    with open(p, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def last_filed_date() -> str:
    """YYYY-MM-DD of the last filed model revision (the start of 'since the last revision')."""
    rows = mb.filed_rows()
    return rows[-1]["file_date"][:10] if rows else "0000-00-00"


# ---- the pieces ------------------------------------------------------------------------------------------------

def build_checks(build: Path, supports: bool) -> list[dict]:
    p = build / "iterate-summary.json"
    if not p.is_file():
        return [item("build", f"no iterate-summary.json in {_rel(build)}: the build did not run", True)]
    return build_checks_from(json.loads(p.read_text(encoding="utf-8"))["steps"], supports)


def build_checks_from(steps: dict, supports: bool) -> list[dict]:
    """Hard items for the model_iterate steps that failed (pipe supports only when that check is in play)."""
    out = []
    for k in CHECK_STEPS:
        r = steps.get(k)
        if r is None or (k == "pipe_supports" and not supports):
            continue
        if r.get("exit", 0) != 0:
            out.append(item(f"check:{k}", f"{k} failed: {r.get('summary', '')}", True))
    return out


def list_delta(build: Path) -> list[dict]:
    return [item(f"delta:{r['kind']}:{r['subject']}",
                 f"model and lists disagree: {r['kind']} {r['subject']} (model: {r['model'] or '-'}; "
                 f"lists: {r['lists'] or '-'}) {r['detail']}".strip())
            for r in _rows(build / "list-delta.csv")]


def support_scope(build: Path) -> list[dict]:
    """Routed lines the pipe support check does not cover, as open items. Scope is the one pipe_supports.rules()
    reads (STR-PS-002 applies_to service classes, PIPE-SVC-001). A line whose class is outside STR-PS-002 (steam,
    condensate: no support rule yet) is a known gap listed once; a line of unknown class is an open item."""
    if str(rp.CHECKS) not in sys.path:
        sys.path.insert(0, str(rp.CHECKS))
    import pipe_supports
    _, scope, _notes, _ = pipe_supports.rules()
    classes = rule_scope.line_classes()
    lines = sorted({r["line_no"] for r in _rows(build / "spool-list.csv") if r.get("line_no")})
    out = []
    for ln in lines:
        if scope is not None and ln in scope:
            continue
        cls = classes.get(ln, rule_scope.UNKNOWN)
        why = ("STR-PS-002 applies_to unknown" if scope is None else
               "service_class unknown" if cls == rule_scope.UNKNOWN else f"class {cls} is outside STR-PS-002")
        out.append(item(f"scope:pipe_supports:{ln}", f"{ln} is routed but outside the pipe support check ({why}; "
                        "<project> Design_Rules/structural.yaml STR-PS-002, PIPE-SVC-001)"))
    return out


def unplaced_components(build: Path, since: str) -> list[dict]:
    """Current components (job and project registers, harness/lib/components.py) whose information came in on or
    after the last filing date (latest obtained_on date of the row) that the build does not use. 'Uses' = the COMP id
    is in the BOM, the manifest or the clamp schedule of this build."""
    text = " ".join((build / n).read_text(encoding="utf-8", errors="replace")
                    for n in ("bom-model.csv", "manifest.json", "clamp-schedule.csv", "fittings-by-spool.csv")
                    if (build / n).is_file())
    out, seen = [], set()
    for r in components.current_rows():
        cid, got = r.get("component_id", ""), components.obtained_on(r)
        # a row with no real date (blank or 'unknown') is library stock of unknown age, not "registered since the
        # last revision": 'unknown' sorts after every date as text and was reported as new (CAPA REVW-001)
        if not cid or cid in seen or not re.match(r"\d{4}-\d{2}-\d{2}$", got) or got < since:
            continue
        seen.add(cid)
        if not re.search(rf"\b{re.escape(cid)}\b", text):
            desc = re.sub(r"\s+", " ", r.get("description", ""))[:90]
            out.append(item(f"component:{cid}", f"{cid} registered {got} ({r['_library']} library) but not in the "
                                                f"model: {desc}"))
    return out


def open_questions(since: str) -> list[dict]:
    """Agent-to-Agent Questions.md entries dated on or after the last filing date whose Status is open."""
    p = rp.AGENT_QUESTIONS
    if not p.is_file():
        return []
    out = []
    # entries are Q-nnnn (Bob, chat, 2026-10-26)
    for block in re.split(r"(?m)^#{2,4} (?=Q-\d{4}\b)", p.read_text(encoding="utf-8")):
        m = re.match(r"(Q-\d{4})", block)
        if not m:
            continue
        date = re.search(r"\*\*Date:\*\*\s*(\d{4}-\d{2}-\d{2})", block)
        status = re.search(r"\*\*Status:\*\*\s*([^\n]+)", block)
        q = re.search(r"\*\*Question:\*\*\s*([^\n]+)", block)
        if not (date and status) or date.group(1) < since:
            continue
        if not status.group(1).strip().lower().startswith("open"):
            continue
        out.append(item(f"question:{m.group(1)}", f"{m.group(1)} open ({date.group(1)}): {(q.group(1) if q else '')[:120]}"))
    # one entry per question (Agent-to-Agent Questions.md may hold an id twice)
    seen, uniq = set(), []
    for i in out:
        if i["key"] not in seen:
            seen.add(i["key"])
            uniq.append(i)
    return uniq


def start_drawing_checks(build: Path, logs: Path, env: dict | None = None) -> dict:
    """Start the three generators in --check-build mode (about 1-2 s each, nothing written). Returns the processes.
    `env` (model_accept.py --sandbox) carries CPME_DRAWINGS_ROOT to the generators."""
    logs.mkdir(parents=True, exist_ok=True)
    procs = {}
    for name, gen, _ in DRAWINGS:
        log = logs / f"check-{gen.replace('.py', '')}.log"
        fh = open(log, "w", encoding="utf-8")
        procs[name] = (subprocess.Popen([str(PY), str(rp.DRAWING_SOURCES / gen), "--check-build", str(build)],
                                        cwd=rp.REPO, stdout=fh, stderr=subprocess.STDOUT, text=True,
                                        encoding="utf-8", errors="replace", env=env), fh, log)
    return procs


def finish_drawing_checks(procs: dict) -> tuple[list[dict], dict]:
    """Wait for the generators; items for errors and layout issues, plus {name: summary line, clouds}."""
    out, info = [], {}
    for name, (p, fh, log) in procs.items():
        p.wait()
        fh.close()
        text = log.read_text(encoding="utf-8", errors="replace").splitlines()
        head = next((ln for ln in text if re.match(r"^(model-to-pid|line-segment-diagram|process-flow-diagram):", ln)),
                    text[-1] if text else "(no output)")
        clouds = re.search(r"(\d+) clouds", head)
        info[name] = {"summary": head.strip(), "clouds": int(clouds.group(1)) if clouds else None, "log": _rel(log)}
        errs, sect = [], None
        for ln in text:
            if ln.startswith("ERRORS:") or ln.startswith("LAYOUT"):
                sect = ln
            elif ln.startswith("  - ") and sect:
                errs.append(f"{'layout' if sect.startswith('LAYOUT') else 'error'}: {ln[4:].strip()}")
            elif not ln.startswith("  "):
                sect = None
        if p.returncode not in (0, 1) and not errs:
            errs.append(f"generator stopped (exit {p.returncode}); see {_rel(log)}")
        for e in errs:
            out.append(item(f"drawing:{name}:{e}", f"{name} cannot be drawn cleanly from this build - {e} "
                                                    f"(generator log {_rel(log)})", True))
    return out, info


def close_out_checks() -> list[dict]:
    """sanitary.py and pid_consistency.py (about 2 s each), as close-out runs them."""
    out = []
    for c in ("sanitary.py", "pid_consistency.py"):
        r = subprocess.run([str(PY), str(rp.CHECKS / c)], cwd=rp.REPO, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        first = next((ln for ln in r.stdout.splitlines() if ln.strip()), "(no output)")
        if r.returncode != 0:
            out.append(item(f"check:{c}", f"{c} reports: {first.strip()}"))
    return out


def collect(build: Path, *, supports: bool, drawing_items: list[dict], accept: bool,
            with_build_checks: bool = True) -> list[dict]:
    """Every open item for this build, in a fixed order."""
    since = last_filed_date()
    items = (build_checks(build, supports) if with_build_checks else []) + drawing_items + list_delta(build)
    if supports:
        items += support_scope(build)
    items += unplaced_components(build, since) + open_questions(since)
    if accept:
        items += close_out_checks()
    return items


# ---- the fast build's closing report (CAPA 2026-11-23) ------------------------------------------------------------
CARRIED_NAME = "carried-to-acceptance.md"
# the instruction a session reads at the end of every fast build: short and literal, never reworded per build
FAST_SCOPE_FOOTER = (
    "FAST EDIT SCOPE: this build changed the model only. Report the build and stop.\n"
    "  - Tag lists (02_Tag_Lists) are written from the model by model_accept.py at acceptance. Do not edit them and "
    "do not ask Bob to approve a list change.\n"
    "  - The P&ID, line segment diagram, process flow diagram and plan sets follow the accepted model. Do not run, "
    "fix or mention them unless Bob asked for that drawing.\n"
    "  - Items carried to acceptance are notes for the acceptance run, not questions for Bob.")
CARRIED_KINDS = (("delta:", "list row(s) the model will write"), ("component:", "component(s) not placed"),
                 ("question:", "open question(s)"))


def carried_counts(items: list[dict]) -> list[int]:
    """How many carried items are list rows, unplaced components and open questions (CARRIED_KINDS order)."""
    return [sum(1 for i in items if i["key"].startswith(p)) for p, _ in CARRIED_KINDS]


def carried_line(items: list[dict], path: Path) -> str:
    """The one line a fast build prints for everything it carries to acceptance."""
    parts = ", ".join(f"{n} {what}" for n, (_, what) in zip(carried_counts(items), CARRIED_KINDS))
    return f"carried to acceptance: {len(items)} item(s) ({parts}) -> {_rel(path)}"


def write_carried(items: list[dict], path: Path, build: str, letter: str) -> Path:
    """carried-to-acceptance.md: the open items of a fast build, for model_accept.py, which writes the list rows
    from the model and records the rest as notes in the revision description. Not a question list."""
    L = [f"# Carried to acceptance: {build}", "",
         f"Written by `harness/scripts/model_iterate.py --fast`; do not hand-edit. These are notes for the acceptance "
         f"run of Rev {letter} (`harness/scripts/model_accept.py`), not questions for Bob: at acceptance the model is "
         "the source of truth, the tag lists are written from it and every other item is recorded in the revision "
         "description.", "", f"**{len(items)} item(s).**", ""]
    for (prefix, what), n in zip(CARRIED_KINDS, carried_counts(items)):
        L += [f"## {n} {what}", ""] + ([f"- {i['text']}" for i in items if i["key"].startswith(prefix)]
                                       or ["- none"]) + [""]
    other = [i for i in items if not i["key"].startswith(tuple(p for p, _ in CARRIED_KINDS))]
    if other:
        L += [f"## {len(other)} other", ""] + [f"- {i['text']}" for i in other] + [""]
    path.write_text("\n".join(L), encoding="utf-8", newline="\n")
    return path


def print_items(items: list[dict], title: str) -> None:
    print(f"{title}: {len(items)}" + ("" if items else " (nothing open)"))
    for n, i in enumerate(items, 1):
        print(f"  {n:>2}. [{'HARD' if i['hard'] else 'open'}] {i['text']}")
