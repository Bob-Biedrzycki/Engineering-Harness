---
name: model-iterate
description: Tier 1 of the skid-model pipeline for the project. One build of the project's skid model (rp.SKID_MODEL_ID, named in job/JOB.md) after every model change - a fast build (takeoffs, interference, envelope, materials, a GLB to look at) or a full build (adds STEP, pipe supports, export GLB) - into a new numbered folder under <project>/03_Working_Design/CAD/Builds/ (never overwritten). Use after any edit to the model source, component models or the design rules the model reads, before showing anything to Bob. A fast edit is the model only - no tag list edits, no P&ID or line diagram work, no plan sets. Never files, never pushes.
---

# Model iterate (tier 1, every build)

**Fast edit scope: the model only** (Bob, chat, 2026-11-23; CLAUDE.md "Work cycle"; CAPA-2026-11-23). Read this
before anything else in this skill. A fast edit changes the model source, builds, reports the build and stops.
- **Tag lists** (`<project>/03_Working_Design/PID/02_Tag_Lists/`): do not edit them and do not ask Bob to approve
  a list change. `model_accept.py` writes them from the model at acceptance: new tags, removed tags, line sizes,
  and the part on a tag that stays (`harness/lib/list_from_model.py`). A line the model adds before the list has
  it is named in the model's parameters (`UNNUMBERED_LINES`), a removed one in `REMOVED_LINES`; never by editing
  `line-list.csv`. If Bob himself asks for a list entry, do exactly that.
- **P&ID, line segment diagram, process flow diagram**: not drawn, checked, fixed or mentioned. Never edit a
  drawing generator in a model fast edit. The acceptance run checks they draw before it files anything; a failure
  there is fixed there. `--drawings` adds the check to one fast build, only when Bob asks for it.
- **Plan sets** (frame, general arrangement, pipe supports, spools and the rest): never mentioned, offered or
  described as stale. The model pin they read moves after an acceptance, or when Bob asks for a plan set fast
  edit (skill `plan-set-fast`). A reviewer agent's remark about a plan set is not passed on to Bob.
- **Carried to acceptance**: the build writes `carried-to-acceptance.md` in its folder and prints one line with
  the count. Do not paste its items into the report and do not ask Bob about them.
- **The report** is: what changed in the model, the build's GLB path, the check lines the build printed, and
  "working copy only, not filed". No closing offer of further work on lists, drawings or plan sets.

**When.** After every change to `<project>/03_Working_Design/CAD/01_Master_Assembly/<MODEL-ID>/`
(`rp.SKID_MODEL`; `<MODEL-ID>` is `rp.SKID_MODEL_ID`, named in `job/JOB.md`), `job/components/` models or the
design rules the model reads. Run it as often as you like; it only writes a new working copy.

**One build series** (Bob, chat, 2026-11-12: one numbered, never-overwritten series in place of two build folders;
"many times it takes 30+ edits to get to the desired result"). Every run, full or `--fast`, writes a new folder
`<project>/03_Working_Design/CAD/Builds/rev<X>/rev<X>-full-<nnn>/` or `rev<X>-fast-<nnn>/`. `<X>` is the last filed
model revision the build starts from (`first` before Rev A); `<nnn>` is one counter per letter shared by both kinds
and starts again at 001 after the next filing. No build overwrites or removes another. Fast edits are the unit of
iteration; the full build is one more numbered entry, run when the result is where Bob wants it, and it is what
`model_file.py` files (`rp.SKID_BUILD` is the latest full build). When a full build starts, the STEP of each
earlier full build is zipped beside its other files. The folder is gitignored and outside the Drive store.
A finished build's files are read-only. Run the model's export scripts only through `model_iterate.py`: one started
by hand writes into the latest full build and is refused by the file system, as it should be.
Acceptance (`model-accept`) runs its own full build; don't run one by hand before it.

**The one command** (repo root, repo venv; it calls the cad venv, `harness/tools/venv-cad`, for the
STEP itself):

```
.\harness\tools\venv\Scripts\python.exe harness\scripts\model_iterate.py
```

**Job-level typical models** (the models in the job's typicals folder, `job/Typical-<ID prefix>/`; Bob, chat, 2026-10-29; Linear CPM-155). Add
`--model-id <ID> --config <CFG>` (or set `CPME_MODEL_ID` / `CPME_MODEL_CONFIG`; the checks it starts inherit
them). `<CFG>` is `B`, `X` or a switch string such as `E-OPT1-OPT3` (default `B`); a string equal to B or X is
refused with the right name, and one that is not a row of `job/knowledge/size-range/config-matrix.csv` is refused
with the reason. Source is `job/Typical-<ID prefix>/03_Working_Design/CAD/01_Master_Assembly/<MODEL-ID>/`, the build goes to
`job/Typical-<ID prefix>/03_Working_Design/CAD/Builds/<MODEL-ID>/<CFG>/`, numbered the same way (with the iso, plan, front and side review PNGs), and the rules
are the harness and job levels only: `envelope.py` reads `job/design-rules/layout.yaml` `shipping_envelope`. The
list delta compares against the configuration's rows of `job/Typical-<ID prefix>/03_Working_Design/PID/02_Tag_Lists/<CL|DS>/`. `--fast` needs a filed
revision of that configuration and skips the P&ID drawing checks. Commands and the model-writing rules:
`job/Typical-<ID prefix>/03_Working_Design/CAD/01_Master_Assembly/README.md`. Without `--model-id` everything below is the project's model, as before.

```
.\harness\tools\venv\Scripts\python.exe harness\scripts\model_iterate.py --model-id <MODEL-ID> --config X
```

`--keep-going` continues past model problems reported by `export_lists.py`
(default: stop and fix, as in the fast loop). `--no-glb` skips the GLB, but a
build without a GLB cannot be filed.

**Fast loop** (Bob, 2026-10-10: light-weight modelling that is very fast):
`--fast` runs only the takeoffs (`export_lists.py`), list delta, interference, materials and the
model-only envelope (about 6 s), and beside them `export_glb_fast.py`, a GLB to
look at straight from the model with no STEP (about 1 min, instead of about
6 min for the full build; Bob, 2026-10-10: "I need to be able to see it ...
whatever is fastest"). Each run writes a new folder,
`<project>/03_Working_Design/CAD/Builds/rev<X>/rev<X>-fast-<nnn>/` (Bob, 2026-10-11: so
fast changes can still be tracked), numbered in the one series above; refused if
it exists. The folder holds
`<MODEL-ID>-rev<X>-fast-<nnn>.glb`, its own takeoffs, logs and
`iterate-summary.json`, and overwrites or removes nothing else (Bob,
2026-10-10: "The fast build should still create a new file, and not overwrite
an existing."). Give Bob the fast GLB's path; do not start the CAD viewer or
make a CAD Viewer link (`cad viewer`) for a fast build (Bob, 2026-10-10: "remove launching the viewer server from the fast skill.
It is unnecesarry."). A fast build is a viewing copy with a coarser
mesh, not a revision, never filed, committed or pushed. `model_file.py` never
files a fast build: run once without `--fast` before filing. **When Bob's prompt says "fast build"**,
run every build of that task with `--fast`, do not file, and report the
path to the fast GLB and the check lines (no viewer); a full build and filing only when he
asks for them. **No pipe supports check in a fast edit until Bob asks for it** (Bob, chat, 2026-10-15: "The pipe
support check is completley unnecessary until i request it.  do not check until i ask."; earlier, 2026-10-11: "I'm
not worried about pipe supports for these fast edits."): `--fast` does not run `pipe_supports.py`; add `--supports`
only on a build where Bob has asked for the support check. Don't mention supports in the report or the build log
otherwise, and make no hanger edit to clear a finding unless he asks.

**Build log** (Bob, 2026-10-10: "start to keep a running list in the fast folder for each revision."): every
build gets one row in `<project>/03_Working_Design/CAD/Builds/build-log.md` (`fast-log.md` before 2026-11-12), written by the script; the row names
only the checks that ran. A full build is always logged; for a fast build pass
`--request "<Bob's words, trimmed>" --change "<what this build changed, or why it was superseded>"` and it adds
the row (build name, time, request, change, the check results, the open count) under today's heading. Never write
the row by hand. A build another session made gets its row from that session.
`model_accept.py` builds Rev <X>'s description from these rows, so the change cell says what changed.

**What a fast build prints at the end** (Bob, chat, 2026-10-15: acceptance "should be run progamatically and
deterministically"; 2026-10-16: "not a list of questions for me to answer prior to acceptance"; 2026-11-23, fast
edit scope above). Hard items only for the checks it ran (a model problem, interference, envelope, materials, the
GLB); then one line, `carried to acceptance: n item(s) ... -> <build>/carried-to-acceptance.md` (list rows the
model will write, components not placed, open questions; `harness/lib/accept_preflight.py`); then the
`FAST EDIT SCOPE` footer. Fix a hard item, because the model is wrong. Leave the carried items where they are:
the acceptance run reads them.

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
the build folder's `logs/`; `iterate-summary.json` there is
what `model_file.py` checks.

**List delta.** `list-delta.csv` / `.md`: tags in the model not on the
`<project>/03_Working_Design/PID/02_Tag_Lists/*-list.csv`, list tags not in the model, line size / wall /
material differences, spools per line vs the line list, and the part on a tag
that differs from the list's (`tag-part-changed`). It is what `model_accept.py`
will write into the lists at acceptance, and nothing else: a non-empty delta is
not fixed here, not handed to anyone and not put to Bob.

**Never.** File, push, build the portal, edit a generated output (TR-03), edit a tag list or a drawing
generator in a fast edit, or point Bob at `<project>/_work/` as the design (TR-08). Not a substitute for
`pid_consistency` (the acceptance run does it) or the frame calc.

**Hand-off line.** `model_iterate: PASS|FAIL in <min>`, each check's summary
line, the `looks:` line (full build), the build's name (`rev<X>-fast-<nnn>` or `rev<X>-full-<nnn>`), and
"working copy only, not filed".
