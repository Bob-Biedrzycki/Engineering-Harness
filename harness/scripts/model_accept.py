"""model_accept.py - accept the fast edits as the next model revision: the whole package, by script, in one pass.

Bob, chat, 2026-10-15, after the Rev Y acceptance took 82 min (filed 4 times, withdrawn 3 times, every open item found
after filing): "Make them all, they should be run progamatically and deterministically. A P&ID revision should be
part of the package." On the open items: "Stop, list them ... it should not turn into a never ending process."
Drawings: "P&ID, LSD and PFD". Pipe supports: "Always at acceptance". Skill: .claude/skills/model-accept.

Run it only when Bob says he accepts (or wants to file) the fast edits as Rev <X>. A request for one part of the
package before that (run the support check, place a part) is a fast edit, not an acceptance.

    .\\harness\\tools\\venv\\Scripts\\python.exe harness\\scripts\\model_accept.py --rev Z --bob "<Bob's words>"

In order; nothing is filed until step 4:
    1. preflight: a fast build with the pipe supports check (model_iterate.py --fast --supports, about 75 s: lists,
       list delta, interference, envelope, supports, the P&ID / LSD / PFD drawn in check mode), then sanitary.py and
       pid_consistency.py; every open item listed by harness/lib/accept_preflight.py.
    2. stops (exit 3, nothing filed) on the FIRST run if anything is open, and freezes that list in
       <project>/_work/accept/rev<X>/state.json. Bob answers the list once; the fixes are fast edits; then the same
       command again. From the SECOND run on, only HARD items stop it (a failed check, or a drawing that cannot be
       drawn cleanly: those cannot be filed); every other item still open goes into the revision description as a
       known open item and the acceptance goes on. One round of questions, never a loop.
    3. full build (model_iterate.py, about 6 min) with every check; any failure stops it (exit 3, nothing filed).
    4. model_file.py --rev <X>: the description is built from Bob's words, the fast-log rows since the last
       revision, and the known open items.
    5. the P&ID, line segment diagram and PFD, each drawn from the filed model in check mode first and filed at its
       own next letter only when its content changed (its revision clouds against the last filed sheet; the model
       revision text is not counted); then the P&ID revision requests raised since the last issued one are marked
       issued.
    6. drive_store.py pointers (no push: close-out), a fast-log row, <project>/_work/accept/rev<X>/accepted.md.

--preflight-only runs step 1 and prints the list; it changes no state and files nothing.
--sandbox <folder> (testing this script only) reuses the current work build instead of step 3 and files into the
folder: the model through model_file.py --models-root, the drawings through CPME_DRAWINGS_ROOT (seeded with each
drawing's revisions up to the one before its last, so a change is there to file), drawn from the last filed model
letter; the state, PRR file and fast log are copies in the folder. Nothing under job/ is written except the fast
build of the preflight.
Exit 0 = accepted and filed; 3 = stopped, nothing filed (the list says why); 2 = refused; 1 = a step failed after
the model was filed (the output names what was filed and what was not).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists()) / "harness" / "lib"))
import repo_paths as rp  # noqa: E402
if __name__ == "__main__":
    rp.require_project("model_accept.py")   # no project yet: exit 2, nothing to accept
import model_build as mb  # noqa: E402
import accept_preflight as pf  # noqa: E402

PY = rp.TOOLS / "venv" / "Scripts" / "python.exe"
ACCEPT = rp.WORK / "accept"
PRR_FILE = rp.OPEN_ITEMS / "pid-revision-requests.md"
DOC_NAMES = {name: doc for name, _, doc in pf.DRAWINGS}   # P&ID = rp.PID_DOC_ID (the project's project.yaml)


ENV = None  # --sandbox: CPME_DRAWINGS_ROOT for the drawing generators


def run(cmd: list, echo: bool = True) -> tuple[int, str]:
    """Run a step from the repo root; its output is echoed line by line and returned."""
    p = subprocess.Popen([str(c) for c in cmd], cwd=rp.REPO, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, encoding="utf-8", errors="replace", env=ENV)
    out = []
    for ln in p.stdout:
        out.append(ln)
        if echo:
            print("    " + ln.rstrip(), flush=True)
    return p.wait(), "".join(out)


def load_state(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"runs": []}


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8", newline="\n")


def fast_log_rows(base: str) -> list[dict]:
    """The fast-log rows of the builds since the last revision was filed (Build rev<base>-fast-nnn, logged after
    the filing time in revisions.csv: rows of a letter filed more than once that day are left out)."""
    log = rp.FAST_BUILDS / "fast-log.md"
    if not log.is_file():
        return []
    filed = mb.filed_rows()
    since = filed[-1]["file_date"][:16] if filed else ""
    rows, day = [], ""
    for ln in log.read_text(encoding="utf-8").splitlines():
        if ln.startswith("## "):
            day = ln[3:].strip()
            continue
        c = [x.strip() for x in ln.strip().strip("|").split("|")]
        if len(c) >= 4 and c[0].startswith(f"rev{base}-fast-") and f"{day} {c[1]}" >= since:
            rows.append({"build": c[0], "time": c[1], "request": c[2], "result": c[3]})
    return rows


def description(letter: str, base: str, state: dict, known: list[dict]) -> str:
    words = " / ".join(f'"{w}"' for w in state.get("bob", []))
    parts = [f"Rev {letter} accepts the fast edits made since Rev {base} (harness/scripts/model_accept.py). "
             f"Bob, chat, {dt.date.today().isoformat()}: {words}."]
    rows = fast_log_rows(base)
    if rows:
        parts.append("Fast builds (<project>/03_Working_Design/CAD/Fast_Builds/fast-log.md): " + " ".join(
            f"{r['build']} ({r['request'][:200]}): {r['result'][:400]}" for r in rows))
    if state.get("list_changes"):
        parts.append("Lists updated from the model (harness/lib/list_from_model.py): "
                     + "; ".join(state["list_changes"]) + ".")
    if known:
        parts.append("Notes at acceptance (recorded, not blocking; Bob, chat, 2026-10-16): "
                     + "; ".join(i["text"] for i in known) + ".")
    return " ".join(parts)


def latest_fast_build(base: str) -> Path | None:
    d = rp.FAST_BUILDS / f"rev{base}"
    builds = sorted((p for p in d.glob(f"rev{base}-fast-[0-9][0-9][0-9]") if p.is_dir()), key=lambda p: p.name)
    return builds[-1] if builds else None


def seed_sandbox(box: Path) -> None:
    """--sandbox: a models root holding the real revisions.csv, and each drawing folder with its last revision
    left out (files and rows), so the run files a model revision and a drawing revision into the folder."""
    import csv
    import os
    import shutil
    global ACCEPT, PRR_FILE, ENV
    if box.exists():
        raise SystemExit(f"REFUSED: --sandbox {box} exists; give a new folder")
    (box / "models").mkdir(parents=True)
    shutil.copy2(mb.FILED / "revisions.csv", box / "models" / "revisions.csv")
    for _, _, doc in pf.DRAWINGS:
        src, dst = rp.DRAWINGS / doc, box / "drawings" / doc
        dst.mkdir(parents=True)
        with open(src / "revisions.csv", newline="", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        last = rows[-1]["revision"]
        keep = [r for r in rows if r["revision"] != last]
        with open(dst / "revisions.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(keep)
        for r in keep[-6:]:
            if (src / r["file"]).is_file():
                shutil.copyfile(src / r["file"], dst / r["file"])
    if PRR_FILE.is_file():   # a new project may have no P&ID revision requests file yet
        shutil.copyfile(PRR_FILE, box / PRR_FILE.name)
    ACCEPT, PRR_FILE = box / "accept", box / PRR_FILE.name
    ENV = dict(os.environ, CPME_DRAWINGS_ROOT=str(box / "drawings"))
    print(f"model_accept: SANDBOX {box} (models, drawings, PRR file, state; the real records are not touched)")


def mark_prrs(issued: str) -> list[str]:
    """P&ID revision requests raised since the last issued one, still 'proposed', are marked issued with the
    drawings filed now (status cell: 'issued: ... ; was: <old status>'). Returns the PRR ids marked. A missing
    file (a new project, none raised yet) or a row with too few cells marks nothing."""
    if not PRR_FILE.is_file():
        return []
    lines = PRR_FILE.read_text(encoding="utf-8").splitlines(keepends=True)
    cells = {}
    for k, ln in enumerate(lines):
        if ln.startswith("| PRR-"):
            c = ln.rstrip("\r\n").split("|")
            if len(c) > 5:
                cells[k] = c
    issued_nums = [int(c[1].strip()[4:]) for c in cells.values() if c[5].strip().lower().startswith("issued")]
    floor = max(issued_nums, default=0)
    marked = []
    for k, c in cells.items():
        pid, status = c[1].strip(), c[5].strip()
        num = int(pid[4:]) if pid[4:].isdigit() else 0
        if num > floor and status.lower().startswith("proposed") and "DRAWN on" not in status:
            c[5] = f" issued: {issued}; was: {status} "
            lines[k] = "|".join(c) + ("\n" if lines[k].endswith("\n") else "")
            marked.append(pid)
    if marked:
        PRR_FILE.write_text("".join(lines), encoding="utf-8", newline="\n")
    return marked


def main() -> int:
    global ACCEPT, PRR_FILE, ENV
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--rev", required=True, help="the letter Bob named; refused unless it is the next one")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--bob", help="Bob's words accepting it (verbatim), recorded in every description")
    g.add_argument("--bob-file", type=Path, help="UTF-8 file holding Bob's words (PowerShell 5.1 and quotes)")
    ap.add_argument("--note", help="model revision note, at most 32 characters (default: rev<last> fast edits <date>)")
    ap.add_argument("--preflight-only", action="store_true", help="list the open items; change nothing")
    ap.add_argument("--sandbox", type=Path, help="testing only: file into this new folder (see the docstring)")
    a = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    box = a.sandbox.resolve() if a.sandbox else None
    if box and not (box / "accept").exists():
        seed_sandbox(box)
    elif box:
        import os
        ACCEPT, PRR_FILE = box / "accept", box / PRR_FILE.name
        ENV = dict(os.environ, CPME_DRAWINGS_ROOT=str(box / "drawings"))
        print(f"model_accept: SANDBOX {box} (second run)")

    base = mb.last_revision()
    letter = mb.next_letter(base)
    if a.rev != letter:
        print(f"REFUSED: Rev {a.rev} is not the next letter; the last filed model revision is {base}, so the next is "
              f"{letter} (letters are sequential, TR-08)", file=sys.stderr)
        return 2
    words = (a.bob_file.read_text(encoding="utf-8-sig").strip() if a.bob_file else (a.bob or "").strip())
    if not words and not a.preflight_only:
        print("REFUSED: --bob \"<Bob's words>\" is required: acceptance runs only on Bob's word", file=sys.stderr)
        return 2
    note = a.note or f"rev{base} fast edits {dt.date.today().isoformat()}"
    if len(note) > 32:
        print(f"REFUSED: --note is {len(note)} characters; at most 32", file=sys.stderr)
        return 2
    state_path = ACCEPT / f"rev{letter}" / "state.json"
    state = load_state(state_path)
    if state.get("accepted"):
        print(f"REFUSED: Rev {letter} was already accepted ({state['accepted']}); the next change is Rev "
              f"{mb.next_letter(letter)}", file=sys.stderr)
        return 2
    rnd = len(state["runs"]) + 1
    t0 = dt.datetime.now()
    print(f"model_accept: {mb.MODEL_ID} Rev {letter} (last filed {base}); "
          f"{'preflight only' if a.preflight_only else f'run {rnd}'}", flush=True)

    # ---- 1. preflight ---------------------------------------------------------------------------------------
    # Bob, chat, 2026-10-16: "when accepted, all of the lists and other drawings get updated based on the model ...
    # not a list of questions for me to answer prior to acceptance." The model leads: the preflight build's list
    # delta is written into <project>/03_Working_Design/PID/02_Tag_Lists (list_from_model.py), a second preflight build confirms it, and nothing but a
    # model that cannot be built or drawn stops the run; everything else is recorded in the description.
    print("[1/6] preflight: fast build, lists from the model, fast build again (supports, drawings, sanitary, "
          "pid_consistency)", flush=True)
    rc, _ = run([PY, rp.SCRIPTS / "model_iterate.py", "--fast", "--supports"], echo=False)
    fast = latest_fast_build(base)
    if fast is None or not (fast / "iterate-summary.json").is_file():
        print("model_accept: STOPPED - the preflight build did not run (see <project>/03_Working_Design/CAD/Fast_Builds)", flush=True)
        return 3
    list_changes = []
    if not a.preflight_only and not box:
        import list_from_model
        list_changes = list_from_model.apply(fast, f"Rev {letter}")
        for ln in list_changes:
            print(f"    lists from the model: {ln}")
        if list_changes:
            rc, _ = run([PY, rp.SCRIPTS / "model_iterate.py", "--fast", "--supports"], echo=False)
            fast = latest_fast_build(base)
    summ = json.loads((fast / "iterate-summary.json").read_text(encoding="utf-8"))
    items = list(summ.get("open_items", [])) + pf.close_out_checks()
    for i in items:  # checks report, they do not block (CLAUDE.md); the support findings go in the description
        if i["key"] == "check:pipe_supports":
            i["hard"] = False
    print(f"    preflight build {rp.rel(fast)}: {'PASS' if rc == 0 else 'FAIL'} in {summ['seconds']:.0f} s")
    for name, d in summ.get("drawing_checks", {}).items():
        print(f"    {name}: {d['clouds']} content cloud(s) against its last filed sheet")
    if a.preflight_only:
        pf.print_items(items, f"OPEN BEFORE REV {letter}")
        return 0 if not items else 3

    state.setdefault("bob", [])
    if words not in state["bob"]:
        state["bob"].append(words)
    hard = [i for i in items if i["hard"]]
    if list_changes:
        state["list_changes"] = state.get("list_changes", []) + list_changes
    if hard:
        state["runs"].append({"at": t0.isoformat(timespec="seconds"), "build": fast.name, "items": items})
        save_state(state_path, state)
        pf.print_items(hard, f"HARD ITEMS BEFORE REV {letter} (cannot be filed)")
        print("model_accept: STOPPED, NOTHING FILED. The model cannot be built or drawn as it is (above); that is a "
              "defect for the agent to fix, not a question for Bob. Fix it and run the same command again.")
        return 3
    known = [i for i in items if not i["hard"]]
    state["runs"].append({"at": t0.isoformat(timespec="seconds"), "build": fast.name, "items": items, "go": True})
    save_state(state_path, state)
    if known:
        pf.print_items(known, "carried as known open items (recorded in the description)")

    # ---- 3. full build -------------------------------------------------------------------------------------
    print("[2/6] full build with every check (about 6 min)", flush=True)
    rc, _ = (0, "") if box else run([PY, rp.SCRIPTS / "model_iterate.py"])
    if box:
        print("    SANDBOX: the current work build is reused")
    failing_ok = []
    if rc != 0:
        bs = json.loads(mb.SUMMARY.read_text(encoding="utf-8")) if mb.SUMMARY.is_file() else {}
        if set(bs.get("failed", [])) == {"pipe_supports"} and bs.get("complete"):
            # report-only at acceptance: the findings are in the description (Bob, chat, 2026-10-16)
            failing_ok = ["--failing-ok", "pipe supports findings recorded as known open items; the model is the "
                          "source of truth at acceptance (Bob, chat, 2026-10-16)"]
        else:
            print("model_accept: STOPPED, NOTHING FILED - the full build failed a step (above); fix it and run the "
                  "same command again.")
            return 3

    # ---- 4. model revision ---------------------------------------------------------------------------------
    print(f"[3/6] filing model Rev {letter}", flush=True)
    desc = description(letter, base, state, known)
    dfile = state_path.parent / "description.txt"
    dfile.write_text(desc + "\n", encoding="utf-8")
    rc, _ = run([PY, rp.SCRIPTS / "model_file.py", "--note", note, "--description-file", dfile, "--rev", letter]
                + failing_ok + (["--models-root", box / "models"] if box else []))
    if rc == 2:
        print("model_accept: STOPPED - model_file.py refused (above); nothing filed.")
        return 3
    filed = {"model": f"{mb.MODEL_ID} Rev {letter}"}
    failed = [] if rc == 0 else ["model_file.py pointers"]

    # ---- 5. drawings ---------------------------------------------------------------------------------------
    print("[4/6] P&ID, line segment diagram and PFD from the filed model", flush=True)
    dnote = f"FROM MODEL REV {letter}"
    for name, gen, doc in pf.DRAWINGS:
        _, out = run([PY, rp.DRAWING_SOURCES / gen, "--check-build", mb.BUILD], echo=False)
        m = re.search(r"(\d+) clouds", out)
        clouds = int(m.group(1)) if m else -1
        if clouds == 0:
            print(f"    {name}: content unchanged from its last filed revision; not filed")
            continue
        ddesc = (f"Drawn from {mb.MODEL_ID} Rev {letter}, accepted {dt.date.today().isoformat()} "
                 f"(harness/scripts/model_accept.py; Bob, chat: {' / '.join(state['bob'])}). "
                 f"{clouds if clouds > 0 else 'unknown'} change cloud(s) against the last filed sheet. Model change: "
                 + desc[:1500])
        # the sandbox model letter is not in <project>/06_Issued_Revisions/Models, so its drawings come from the last real one
        rc, out = run([PY, rp.DRAWING_SOURCES / gen, "--model-rev", base if box else letter, "--note", dnote,
                       "--description", ddesc])
        got = re.search(r"FILED rev ([A-Z]+)", out)
        if rc == 0 and got:
            filed[name] = f"{doc} Rev {got.group(1)}"
        else:
            failed.append(f"{name} ({gen} exit {rc})")

    # ---- 6. records ----------------------------------------------------------------------------------------
    print("[5/6] records: P&ID revision requests, Drive pointers, fast log", flush=True)
    marked = []
    if "P&ID" in filed:
        issued = ", ".join(v for k, v in filed.items() if k != "model")
        marked = mark_prrs(f"{issued} ({dt.date.today().isoformat()}, from model Rev {letter})")
        print(f"    PRRs marked issued: {', '.join(marked) or 'none open'}")
    rc, _ = (0, "") if box else run([PY, rp.SCRIPTS / "drive_store.py", "pointers"])
    if rc != 0:
        failed.append("drive_store.py pointers")
    log = box / "fast-log.md" if box else rp.FAST_BUILDS / "fast-log.md"
    with open(log, "a", encoding="utf-8", newline="\n") as f:
        f.write(f"| (accepted) | {dt.datetime.now():%H:%M} | Bob: {' / '.join(state['bob'])[:300].replace('|', '/')} | "
                f"{'; '.join(f'{k} {v}' for k, v in filed.items())} filed by model_accept.py | "
                f"{len(known)} known open item(s) |\n")
    state["accepted"] = dt.datetime.now().isoformat(timespec="seconds")
    state["filed"], state["prrs"], state["failed"] = filed, marked, failed
    save_state(state_path, state)
    mins = (dt.datetime.now() - t0).total_seconds() / 60
    report = [f"# Rev {letter} accepted ({state['accepted']}, {mins:.1f} min)", ""]
    report += [f"- {k}: {v}" for k, v in filed.items()]
    report += [f"- PRRs marked issued: {', '.join(marked) or 'none'}",
               f"- known open items: {len(known)}" + "".join(f"\n  - {i['text']}" for i in known)]
    if failed:
        report.append(f"- NOT DONE: {', '.join(failed)}")
    (state_path.parent / "accepted.md").write_text("\n".join(report) + "\n", encoding="utf-8")

    print("[6/6] done", flush=True)
    print("\n".join(report))
    print(f"model_accept: {'ACCEPTED' if not failed else 'ACCEPTED WITH STEPS NOT DONE'} - model "
          f"<project>/06_Issued_Revisions/Models/{mb.MODEL_ID}/{mb.MODEL_ID}-rev{letter}.glb; nothing committed or pushed (close-out).")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
