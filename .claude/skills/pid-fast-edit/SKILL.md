---
name: pid-fast-edit
description: Light-weight P&ID working copies for the project - model-to-pid.py --fast redraws the project's P&ID (rp.PID_DOC_ID, named in job/JOB.md) from the latest fast model build (or a filed model revision) in about 7 s, DXF + PDF, saved as a new <PID-DOC-ID>-rev<X>-fast-<nnn> in <project>/03_Working_Design/PID/Fast_Edits/ with a fast-log.md row. No DWG, no clouds, nothing filed. Use when Bob says "P&ID fast edit" or wants to see a P&ID change quickly.
---

# P&ID fast edit (Bob, chat, 2026-10-11)

Bob: "as light weight as possible, while still saving each change as a new revision." Same idea as the
fast model loop (`model-iterate`, `--fast`).

## Run

```
.\harness\tools\venv\Scripts\python.exe "<project>\03_Working_Design\PID\Fast_Edits\src\model-to-pid.py" --fast --request "<Bob's words, trimmed>"
```

- **Run the working copy in `src/`**, never the project generator. `src/` holds copies of `model-to-pid.py`,
  `model_schematic.py`, `model_runs.py`, `model_topology.py`, `typical-pid.py` (from `<project>/03_Working_Design/CAD/06_Drawings/Generators/`) and
  `cpme_titleblock.py` (from `harness/cad-lib/`); they import each other from `src/` first. If `src/` is missing,
  copy those six files in, once the generators exist (until then there is no fast edit
  to run). The copy refuses to run without `--fast`, so it can never file. Bob, chat, 2026-10-11:
  "Fast changes should be able to change anything requested without affecting the project files."

- **Source:** the latest fast model build in `<project>/03_Working_Design/CAD/Fast_Builds/rev<X>/rev<X>-fast-<nnn>/` (default), or
  `--fast-build revA-fast-001` (also `A-001`, or `001` for the latest letter), or `--model-rev <X>` for a filed model
  revision.
- **Changes live in the fast-edit folder, never in project files** (Bob, chat, 2026-10-11: "Fast edits should
  collect changes in the fast edits folder, and not edit any project files unless instructed to do so. project
  files can be updated when a fast edit is converted to a project file should that happen."). Each change Bob asks
  for is one entry in `<project>/03_Working_Design/PID/Fast_Edits/fast-changes.yaml`: `FC-<nnn>`, date, his words, the
  first edit that shows it, `kind`, the old value, `convert_to`, `status: open`. Kinds: `list` (a <project>/03_Working_Design/PID/02_Tag_Lists list
  field, applied in memory), `text` (drawn text find/replace), `code` (anything else: edit the copy in `src/`,
  mark the edit with an `FC-nnn` comment, describe it in the entry). Never edit `<project>/03_Working_Design/PID/02_Tag_Lists`, the project generator
  or any other tracked file for a fast edit. Topology changes still come from the model (a fast model build).
- Each edit with code changes writes `<edit>-src.diff` (every difference between `src/` and the project files).
- **Converting** (only when Bob says): write each open change into its `convert_to` file (for `code`, apply the
  latest edit's `-src.diff`), set it to `status: converted`, then file the revision with `drawing-revise`.
  If the project generator changed since `src/` was copied, merge before converting.
- **Output**, never overwritten, one folder per edit (Bob, chat, 2026-10-11: "create a new folder for each fast
  edit within P&ID Fast Edits seeing as each has multiple files"):
  `<project>/03_Working_Design/PID/Fast_Edits/rev<X>-fast-<nnn>/<PID-DOC-ID>-rev<X>-fast-<nnn>.dxf`
  (`<PID-DOC-ID>` is `rp.PID_DOC_ID`, named in `job/JOB.md`), `.pdf`,
  `-changes.yaml` and (when `src/` differs from the project code) `-src.diff`. The top folder holds only
  `fast-log.md`, `fast-changes.yaml`, `src/` and the edit folders.
  `<X>` is the last filed P&ID revision the edit starts from. `<nnn>` counts up for that letter and starts again
  at 001 after the next filed revision. The revision box shows `<X>`, and the revision-block row says
  `FAST-<nnn> - NOT ISSUED`.
- The PDF is rendered from the DXF by `harness/cad-lib/dxf_pdf_fast.py` in the cadgen venv (matplotlib, no AutoCAD).
  `--no-pdf` writes only the DXF.
- The script appends the `fast-log.md` row itself (edit, time, source, request, change IDs, result) and copies
  the change set beside the edit as `<edit>-changes.yaml`, so every edit shows exactly what it was drawn with.
- Checks (tags drawn once, lines labelled, layout) are printed and logged. They never stop a fast edit.

- **Drafting rules do not apply here.** `harness/design-rules/drafting.yaml` (DRF-LBL / ARR / PLC) is for a brand
  new P&ID; a fast edit or a revision changes exactly what Bob asks and keeps the discretion already applied
  (Bob, chat, 2026-10-11: "The rules should only apply when creating a brand new P&ID, not revising an existing
  one." and "never when revising one, unless requested, or asked for"). No questions for formatting (Bob, same day). Code positions are keyed by MODEL tag: after a `retag`, look a drawn tag up by its model tag.

## Report

Give Bob the PDF path and the check line. No renders, previews or viewer.

## Not a filed revision

The folder is gitignored and excluded from the Drive store. A fast edit is never committed, pushed, tagged or
handed to anyone outside the team as a revision. When Bob wants it issued, file it with `drawing-revise`: the
same generator without `--fast`, from a filed model revision, with `--note`. That takes the next letter and
writes DWG + PDF from the DWG, with clouds (TR-06, TR-07, TR-08).
