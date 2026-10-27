---
name: model-file
description: Tier 2 of the skid-model pipeline for the project. Files the current work build of the project's skid model (rp.SKID_MODEL_ID, named in job/JOB.md) as the next sequential revision under <project>/06_Issued_Revisions/Models/ (STEP zipped, GLB, every takeoff, list delta), read-only, with revisions.csv rows and Drive pointers. Use whenever Bob is to look at the model or anything built from it. No push.
---

# Model file (tier 2, when Bob looks at it)

**When.** Before the model, a render of it or any takeoff is shown or handed to
Bob or anyone else (TR-08; Bob, 2026-09-24: "YOU ARE NO LONGER TO OVERWRITE
DESIGNS. THEY MUST BE LABELED AS REVISIONS."). Run `model-iterate` first; this
refuses a work build that is incomplete, failed a check, or is older than its
source.

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

**What it does.** Next letter after the last `revisions.csv` row (nobody
assigns it); refuses if any target file exists; copies the build to
`<project>/06_Issued_Revisions/Models/<MODEL-ID>/<MODEL-ID>-rev<X>*` (`<MODEL-ID>` is
`rp.SKID_MODEL_ID`, named in `job/JOB.md`) with the STEP
zipped as `-rev<X>.step.zip`; makes every file read-only; appends one
`revisions.csv` row per file (sha256, bytes, note, description); runs
`drive_store.py pointers`.

**Never.** Push to Drive (that is close-out), refile or overwrite a letter,
edit a filed file, rename or delete one, or give Bob a `<project>/_work/` path.

**Hand-off line.** `Filed <MODEL-ID> Rev <X>: <project>/06_Issued_Revisions/Models/<MODEL-ID>/<MODEL-ID>-rev<X>.*`
(file count, note), the checks recorded, "pointers written, push at close-out".
