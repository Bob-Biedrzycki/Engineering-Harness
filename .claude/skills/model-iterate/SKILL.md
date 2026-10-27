---
name: model-iterate
description: Tier 1 of the skid-model pipeline for the project. One full build of the project's skid model (rp.SKID_MODEL_ID, named in job/JOB.md) after every model change - takeoffs, STEP, interference, envelope, pipe supports, GLB and the list delta - into the working copy <project>/03_Working_Design/Exports/build/. Use after any edit to the model source, the <project>/03_Working_Design/PID/02_Tag_Lists lists, component models or design rules, before showing anything to Bob. Never files, never pushes.
---

# Model iterate (tier 1, every build)

**When.** After every change to `<project>/03_Working_Design/CAD/01_Master_Assembly/<MODEL-ID>/`
(`rp.SKID_MODEL`; `<MODEL-ID>` is `rp.SKID_MODEL_ID`, named in `job/JOB.md`), the `<project>/03_Working_Design/PID/02_Tag_Lists/`
lists, `job/components/` models or the design rules. Run it as often as you like; it only writes the working copy.
Acceptance (`model-accept`) runs its own full build; don't run one by hand before it.

**The one command** (repo root, repo venv; it calls the cadgen venv for the
STEP itself):

```
.\harness\tools\venv\Scripts\python.exe harness\scripts\model_iterate.py
```

`--keep-going` continues past model problems reported by `export_lists.py`
(default: stop and fix, as in the fast loop). `--no-glb` skips the GLB, but a
build without a GLB cannot be filed.

**Fast loop** (Bob, 2026-10-10: light-weight modelling that is very fast):
`--fast` runs only lists, list delta, interference and the
model-only envelope (about 6 s), and beside them `export_glb_fast.py`, a GLB to
look at straight from the model with no STEP (about 1 min, instead of about
6 min for the full build; Bob, 2026-10-10: "I need to be able to see it ...
whatever is fastest"). Each run writes a new folder,
`<project>/03_Working_Design/CAD/Fast_Builds/rev<X>/rev<X>-fast-<nnn>/` (Bob, 2026-10-11: so
fast changes can still be tracked). `<X>` is the last filed model revision the build starts from (`revisions.csv`), `<nnn>`
counts up for that letter and starts again at 001 after the next filing, the same as P&ID fast edits; refused if
it exists. The folder holds
`<MODEL-ID>-rev<X>-fast-<nnn>.glb`, its own takeoffs, logs and
`iterate-summary.json`, and overwrites or removes nothing else (Bob,
2026-10-10: "The fast build should still create a new file, and not overwrite
an existing."). Give Bob the fast GLB's path; do not start the CAD viewer or
make a `cad_show` link for a fast build (Bob, 2026-10-10: "remove launching the viewer server from the fast skill.
It is unnecesarry."). `<project>/03_Working_Design/CAD/Fast_Builds/` is
gitignored and excluded from the Drive store: viewing copies with a coarser
mesh, not revisions, never filed, committed or pushed. `model_file.py` never
sees a fast build: run once without `--fast` before filing. **When Bob's prompt says "fast build"**,
run every build of that task with `--fast`, do not file, and report the
path to the fast GLB and the check lines (no viewer); a full build and filing only when he
asks for them. **No pipe supports check in a fast edit until Bob asks for it** (Bob, chat, 2026-10-15: "The pipe
support check is completley unnecessary until i request it.  do not check until i ask."; earlier, 2026-10-11: "I'm
not worried about pipe supports for these fast edits."): `--fast` does not run `pipe_supports.py`; add `--supports`
only on a build where Bob has asked for the support check. Don't mention supports in the report or the fast log
otherwise, and make no hanger edit to clear a finding unless he asks.

**Fast log** (Bob, 2026-10-10: "start to keep a running list in the fast folder for each revision."): every
fast build gets one row in `<project>/03_Working_Design/CAD/Fast_Builds/fast-log.md`, written by the script: pass
`--request "<Bob's words, trimmed>" --change "<what this build changed, or why it was superseded>"` and it adds
the row (build name, time, request, change, the check results, the open count) under today's heading. Never write
the row by hand. A build another session made gets its row from that session.
`model_accept.py` builds Rev <X>'s description from these rows, so the change cell says what changed.

**Open before Rev <next>** (Bob, chat, 2026-10-15: acceptance "should be run progamatically and
deterministically"). Every fast build also draws the P&ID, line segment diagram and PFD from itself in check mode
(about 1-2 s each, beside the GLB, nothing written; a failure is a `[FAIL] check P&ID` line), then prints
`OPEN BEFORE REV <next>: n` with each item: failed checks, drawing errors and layout issues (HARD), list delta
rows, components registered since the last revision but not in the model, questions opened since then
(`harness/lib/accept_preflight.py`). **Put that list, as printed, at the end of every fast-edit report**, so Bob
sees what acceptance will ask before he asks for it. Do not fix items he did not ask about, and do not offer to.

**A request for part of the acceptance is only that part** (Bob, chat, 2026-10-15: "If I request parts of the
acceptance prior to aceptance it does not mean do everything else, or ask if i would like everything else
completed."). "Run the support check" is one `--fast --supports` build; "place the hanger" is a fast edit. Neither
files anything, and neither ends with "want me to do the rest?". Acceptance starts only when Bob says he accepts,
or wants to file, the fast edit as Rev <X>: then use the skill `model-accept`.

**What it runs** (the model's own export scripts, once the model source
exists). `export_lists.py`, then in parallel `export_step_direct.py`,
`interference.py`, `pipe_supports.py --report` and the list delta
(`harness/lib/list_delta.py`); after the STEP, `envelope.py` and
`export_glb.py` in parallel; after the GLB, the looks line
(`presentation_materials.py --glb <build GLB> --looks-only`; Bob,
2026-10-12): `looks: n of m required instruments realistic; missing: ...`,
the tags in `materials.yaml` `required_looks` whose `face_colours` look
resolves on this GLB. Report only, never a build failure; a tag missing means
its `face_colours` `part` no longer finds the mesh (see `component-add`).
The looks feed the presentation site, dormant until the job has one: with no
`materials.yaml` the line says so and is not a failure.
`--fast` does not run it. One summary line per step; full logs in
`<project>/03_Working_Design/Exports/build/<MODEL-ID>/logs/`; `iterate-summary.json` there is
what `model_file.py` checks.

**List delta.** `list-delta.csv` / `.md`: tags in the model not on the
`<project>/03_Working_Design/PID/02_Tag_Lists/*-list.csv`, list tags not in the model, line size / wall /
material differences, spools per line vs the line list. Zero rows means the
model and the lists agree. A non-empty delta is not fixed here: it goes to the
process-engineer at close-out (lists stay the formal input, hard rule 2).

**Never.** File, push, build the portal, edit a generated output (TR-03), or
point Bob at `<project>/_work/` as the design (TR-08). Not a substitute for
`pid_consistency` (close-out runs it) or the frame calc.

**Hand-off line.** `model_iterate: PASS|FAIL in <min>`, each check's summary
line, the list delta row count, the `looks:` line, and "working copy only,
not filed".
