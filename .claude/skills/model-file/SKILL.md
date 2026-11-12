---
name: model-file
description: Tier 2 of the skid-model pipeline for the project. Files the latest full build of the project's skid model (rp.SKID_MODEL_ID, named in job/JOB.md) as the next sequential revision under <project>/06_Issued_Revisions/Models/ (STEP zipped, GLB, every takeoff, list delta), read-only, with revisions.csv rows and Drive pointers. Use whenever Bob is to look at the model or anything built from it. No push.
---

# Model file (tier 2, when Bob looks at it)

**When.** Before the model, a render of it or any takeoff is shown or handed to
Bob or anyone else (TR-08; Bob, 2026-09-24: "YOU ARE NO LONGER TO OVERWRITE
DESIGNS. THEY MUST BE LABELED AS REVISIONS."). Run `model-iterate` first; this
refuses a build that is incomplete, failed a check, or is older than its
source.

**Which build** (Bob, chat, 2026-11-12: one numbered build series). The latest full build,
`<project>/03_Working_Design/CAD/Builds/rev<X>/rev<X>-full-<nnn>/`; `--build rev<X>-full-<nnn>` names another. A fast
build has no STEP and is never filed. The description starts "Filed from build <name>" and every `revisions.csv`
row's `source` gives the build folder, so a filed revision traces to the build it came from.

**Accepting fast edits is `model-accept`, not this skill** (Bob, chat, 2026-10-15: "they should be run
progamatically and deterministically. A P&ID revision should be part of the package."). `model_accept.py` calls
`model_file.py` itself, after its preflight and full build, and files the drawings from it. Run `model_file.py`
by hand only when Bob asks to file a build outside an acceptance. Never file and then ask about something found
before filing.

**The one command** (repo root, repo venv). Write the description to a
UTF-8 file first: PowerShell 5.1 mangles embedded double quotes.

```
.\harness\tools\venv\Scripts\python.exe harness\scripts\model_file.py --note "<at most 32 chars>" --description-file <file> --rev <X>
```

Add `--dry-run` first to see the file set and the next letter. `--rev X` is
optional and makes it refuse unless X is the next letter. The description says
what changed from the previous revision and why, with Bob's words, dates and
records; the script appends the model_iterate check lines. `--failing-ok
"<reason>"` files a build with a failing check, only on Bob's say-so, with the
reason recorded.

**Job-level typical models** (the models in the job's typicals folder, `job/Typical-<ID prefix>/`; Bob, chat, 2026-10-29; Linear CPM-155). Add
`--model-id <ID> --config <CFG>` to the command, for a configuration built by `model_iterate.py` with the same two
flags:

```
.\harness\tools\venv\Scripts\python.exe harness\scripts\model_file.py --model-id <MODEL-ID> --config B --note "<at most 32 chars>" --description-file <file>
```

Each configuration is its own document, `<MODEL-ID>-<CFG>`, with its own letters from Rev A (B and X are filed
separately). Files are named `<MODEL-ID>-<CFG>-rev<X>...`, the STEP zipped, with the four review views, into
`job/Typical-<ID prefix>/06_Issued_Revisions/Models/<MODEL-ID>/<MODEL-ID>-<CFG>-rev<X>/`, whose parent's one `revisions.csv` holds the rows of every configuration of
that model. A switch string equal to B or X is refused with the right name. Commands: `job/Typical-<ID prefix>/03_Working_Design/CAD/01_Master_Assembly/README.md`.

**What it does.** Next letter after the last `revisions.csv` row (nobody
assigns it); refuses if the revision's folder exists; copies the build into that revision's own folder
(Bob, chat, 2026-10-30: one folder per rev; `harness/checks/filed_layout.py` checks it),
`<project>/06_Issued_Revisions/Models/<MODEL-ID>/<MODEL-ID>-rev<X>/<MODEL-ID>-rev<X>*` (`<MODEL-ID>` is
`rp.SKID_MODEL_ID`, named in `job/JOB.md`) with the STEP
zipped as `-rev<X>.step.zip`; makes every file read-only; appends one
`revisions.csv` row per file (sha256, bytes, note, description); runs
`drive_store.py pointers`.

**Then save it** (`github-tracking`, `track.py save`): the revision folder and its `revisions.csv`, with a documented
message. That pushes the large files to Drive and backs the commit up on GitHub; no question to Bob.

**Never.** Refile or overwrite a letter, edit a locked file, rename or delete one, or give Bob a `<project>/_work/`
path.

**Hand-off line.** `Locked <MODEL-ID> Rev <X>: <project>/06_Issued_Revisions/Models/<MODEL-ID>/<MODEL-ID>-rev<X>/`
(file count, note), the checks recorded, and the `git status` check after the save (global "Git and backup").
