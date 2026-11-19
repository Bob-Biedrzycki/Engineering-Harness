---
name: engine-update
description: Keep the text-to-cad plugin current without letting it move a build or a drawing. The plugin's skills and the computer's `cad` command update themselves; the engine that makes builds and drawing views is one pin (harness/requirements-cad.txt) that moves only after harness/scripts/engine_check.py compares the new release against it and Bob says yes. Use when a newer text-to-cad or cad release exists, when the weekly check reports one, when Bob asks whether the CAD tooling is current, or when a build or projection fails after the plugin changed.
---

# Engine update (two tiers)

Bob, chat, 2026-11-18: "this skill updates frequently and we rely heavily on it. Should we rethink how to better
handle the updates. That took a lot of time!"; then "go ahead with all five". The update before that crossed four
releases at once and took most of a day. The answer is two tiers and one small step at a time.

## Tier 1: floats, nobody pins it

- **The plugin's skills** (`text-to-cad@earthtojake`): the marketplace follows upstream's `latest` branch and
  updates itself. Keeping it current is Claude's job, without asking Bob.
- **The computer's `cad` command**: updates itself within its major version (`cad update auto status`). A new major
  version is `cad update --major`, after reading upstream's migration notes
  (`https://github.com/earthtojake/text-to-cad/tree/main/docs/migrations`).
- Harness text names no plugin version and no plugin skill by its release: say "the CAD skill", "the engineering
  drawing skill", "the CAD Viewer link". When upstream renames or merges skills, nothing here needs editing.

## Tier 2: one pin, moved on purpose

- **The pin** is the `cad==` line of `harness/requirements-cad.txt`, a full freeze. The cad venv
  (`harness/tools/venv-cad`) is built from it. The skid build's second interpreter and a job's plan set view
  projection both run on that venv, so a filed revision rebuilds the same way next month whatever the computer's
  `cad` has become.
- **Never edit a version in that file by hand**, and never run a build or project a view a sheet is drawn from
  with `cad run` (that is the floating release).

## The one command

From the job that has a model (repo root, repo venv):

    .\harness\tools\venv\Scripts\python.exe harness\scripts\engine_check.py status
    .\harness\tools\venv\Scripts\python.exe harness\scripts\engine_check.py try [--version X]

`try` builds a candidate venv beside the pinned one and runs the same work on both: a fixed probe (solids, a STEP
round trip, projections, and the engine names the code relies on), the project model's quick GLB, and the job's
reference views (`job/engine-check.yaml`). It writes `harness/tools/engine-check/<release>/report.md`. It touches no
build folder, no pinned view cache and nothing filed. Exit 0 means no difference was found.

## What to do with the result

1. **No difference found.** Tell Bob in plain words: which release, that the probe, the model and the reference
   views came out the same, and what moving the pin does and does not do (it changes which engine the next build
   and the next projected view use; it files nothing, redraws nothing, and views already cached stay as they are).
   On his yes: `engine_check.py adopt --version X`, record the move in each project's `tooling.md`, save, carry
   `harness/requirements-cad.txt` to the master and the other jobs (`harness_sync.py`), and run
   `engine_check.py rebuild` in each. Run one full build before anything is next filed and compare its lists with
   the last one.
2. **Differences.** Read the report with Bob. A changed kernel (build123d or OCP) usually shows as hidden lines
   split differently or a section that cuts where it used to graze: say which views and what a reader of the sheet
   would see. A missing engine name means code must change first; fix it against the candidate venv
   (`harness/tools/venv-cad-try`), run `try` again, then go to 1.
3. **Staying one release behind is fine.** Being four behind is what made the last update slow.

## Stops

- `adopt` needs Bob's word in chat, quoted in `tooling.md`.
- Moving the pin never re-projects a plan set and never files anything; both are separate, on Bob's word.
- If another session is part-way through a plan set, wait: views from two engines must not be mixed on one set.
