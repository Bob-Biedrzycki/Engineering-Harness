---
name: plan-set-fast
description: Plan set fast edits (general arrangement, frame weldment, pipe supports, tank modifications, spools, piping arrangement, standard details), for the job's typical plan set or the active project's quoting plan set - plan_set.py edit takes one plan set and the drawings an edit touches, redraws every sheet the edit changed with a revision cloud round what changed, joins the sets and writes the complete plan set PDF, so no sheet is left loose; the single-sheet commands (sheet, changed, set, combine, status) are kept. Working copies under <level>/03_Working_Design/Exports/Fast_Drawings, checked against DRF-FACE-001 on the way out. Nothing filed. Use when a plan set sheet is to be edited, redrawn, checked or shown without filing a revision.
---

# Plan set fast edits: one plan set in, the complete plan set out

The 2026-11-17 words below set up the single-sheet tools; Bob's 2026-11-18 words (next section) changed the loop
that uses them.

Bob, chat, 2026-11-17: "I no longer trust edits on the entire plan set. We need to work with the individual plans,
individually, then plan to merge the complete set ... whenever that is needed or appropriate", and "we need to work
through the process in reverse for making a small edit on a single sheet, to adding it to a drawing set, then
ultimately combining the full set ... I would like predefined scripts and processes."

## A fast edit: one plan set in, the complete plan set out (Bob, chat, 2026-11-18)

Bob: "let's change our fast edits so that we are not left with several sheets in different stages. We'll target fast
edits to a specific plan set, and the output should be the completed planset with edit clouds like we've done for
other drawings."

So a fast edit is one command, for one plan set (`typical` or `project`), and it ends in one PDF:

```
plan_set.py edit typical FRM1 PSP --request "<Bob's words>"      the drawings the edit touches
plan_set.py edit project --all --request "<Bob's words>"         all seven rebuilt (about 5 minutes more)
```

What it does, in order, and it stops with `PLAN SET NOT WRITTEN` rather than leave anything part-way:

1. Builds each named drawing whole in memory and redraws **every** sheet whose content changed (the asked one and
   any other the edit reached), each as its next sheet version. Nothing is listed as "also changed" and left.
2. Draws a **revision cloud** round everything added, changed or removed on each redrawn sheet, compared with that
   sheet's previous version, with the new version's FAST number in the delta (the same cloud a filed revision gets,
   `revfile.add_box_clouds`). A sheet redrawn later loses its earlier clouds; a sheet not redrawn keeps the clouds
   and number of the edit that last changed it.
3. Rebuilds the general arrangement too when a drawing's sheet count changed (its cover lists the counts).
4. Joins each rebuilt drawing's set, and any other set that is older than its sheets.
5. Writes the complete plan set: `Fast_Drawings/<prefix>-Full Planset/<prefix>-PLAN-SET-fast-<nnn>.pdf`, with the
   changed sheets listed on the index page (each a link) and under a "Changed in fast edit <nnn>" bookmark, a
   `.json` record beside it, and a row in that folder's `edit-log.md`.

Measured 2026-11-18 (sandbox trial, typical, one pipe support sheet): 14 s from command to plan set PDF. A drawing
costs its build time below; the join and the plan set add about 5 s.

Report to Bob: the plan set PDF path, the `FAST EDIT <nnn> DONE` line (sheets changed, clouds, CLEAN or NOT CLEAN),
the PDF page of each changed sheet, and the drawings that were not rebuilt. The other plan set is not touched: an
edit meant for both is run once for each. A drawing that was not named is taken as it stood, so name every drawing
whose basis, notes or generator was edited, or use `--all` after a change to something shared (the toolkit, the
model pin). `NOTHING CHANGED` means the edit reached no sheet of the named drawings.

The clouds need a record of each sheet's previous content (`<sheet version>.content.json`, written with every sheet
version and, for versions drawn before 2026-11-18, by the next build that finds them current). A sheet with none
prints `NO CLOUDS` once and is clouded from then on.

## The single-sheet tools (kept, no longer the standing loop)

The levels below still exist for a look at one sheet or to see where things stand, and `edit` is built from them:

| Level | Command | What comes out |
|---|---|---|
| 1. One sheet | `plan_set.py sheet <SET> <KEY> --request "<words>"` | That sheet only, as its own numbered DXF + PDF, with its true `SHEET n OF N`; a list of every OTHER sheet the edit changed (not written) |
| 1. Several sheets | `plan_set.py changed <SET> --request "<words>"` | Every sheet that differs from its latest version |
| 2. The drawing's set | `plan_set.py set <SET>` | One PDF from the latest version of every sheet; refused while any sheet is missing or old |
| 3. The plan set | `plan_set.py combine` | The seven drawings joined, with an index page and bookmarks |
| Where things stand | `plan_set.py status [<SET>] [--verify] [--brief]` | Every sheet: its number, latest version, and current / changed / renumbered / never drawn |

`plan_set.py` is `job/Typical-<ID prefix>/03_Working_Design/CAD/06_Drawings/Generators/plan-set-reference/plan_set.py`,
run from the repo root with the harness Python:

```
.\harness\tools\venv\Scripts\python.exe "<Generators>\plan-set-reference\plan_set.py" status
```

Every command takes `--target typical|project|both` (default `both`). Nothing here files anything, and no command
reads or writes a data sheet.

## The seven drawings and their sheets

| SET | Typical document | Project document | Drawing |
|---|---|---|---|
| `GA` | `CIP-TYP-GA-001` | `Project-<code>-GA-001` | General Arrangement |
| `FRM1` (also `FRM`) | `CIP-TYP-FRM-001` | `Project-<code>-FRM-001` | Frame Weldment, with every pipe support |
| `PSP` | `CIP-TYP-PSP-001` | `Project-<code>-PSP-001` | Pipe Supports |
| `TNK` | `CIP-TYP-TNK-001` | `Project-<code>-TNK-001` | Tank Modifications |
| `SPL` | `CIP-TYP-SPL-001` | `Project-<code>-SPL-001` | Pipe Spools, one sheet per spool |
| `ISO` | `CIP-TYP-ISO-001` | `Project-<code>-ISO-001` | Piping Arrangement, by line |
| `DET` | `CIP-TYP-DET-001` | `Project-<code>-DET-001` | Standard Details |

There is one frame drawing (Bob, chat, 2026-11-17: "We no longer need the two sets of frame plans, the frame plans
should include all supports."). The frame-only drawing `FRM-002` is retired: its filed Rev A stays as filed and it is
not drawn again.

A sheet is named by its **key**, which `status` lists: `FRM1 MEMBERS-3`, `GA 02-PLAN`, `SPL L-100-SP03`,
`ISO L-200-T1`, `TNK TK-102-ELEV`. A key does not move when sheets are added before it (spool, piping and tank keys
carry no running number). Talk with Bob about a sheet as `<set> <key>`.

## The standing loop

1. Bob names the plan set (typical or project) and an edit.
2. Make the edit where the content comes from: the set's basis file (`<SET>.basis.yaml`), its sheets or notes yaml,
   or the generator.
3. `plan_set.py edit <typical|project> <SET> [<SET> ...] --request "<Bob's words>"`.
4. Report the plan set PDF, the DONE line and the changed sheets with their PDF pages. A changed sheet Bob did not
   expect is clouded in front of him; if the edit was not meant to reach it, fix the edit and run it again.
5. `sheet`, `changed`, `set` and `combine` on their own only when Bob asks for that piece.

## What `sheet` does, and why it can be trusted

The generator still builds the **whole drawing in memory**, exactly as for a whole-drawing fast drawing, because
sheets depend on each other: tables page across sheets, a sheet index lists the others, a weld symbol reads "SEE"
the first one, the general arrangement's cover counts every drawing's sheets. So the asked sheet has the right sheet
number, the right table page and the right references. Then only that sheet is written:

```
<level>/03_Working_Design/Exports/Fast_Drawings/<DOC>/
  Sheets/<KEY>/<DOC>-<KEY>-fast-<nnn>.dxf  and .pdf   one counter per sheet, never overwritten
  Sheets/sheets-state.json                            per sheet: latest version, what the last build held
  Sheets/sheet-log.md                                 one row per sheet drawing
  Set/<DOC>-<base>-set-<nnn>.pdf  and .json           an assembled set and the sheet versions in it
  <DOC>-<base>-fast-<nnn>/                            whole-drawing fast drawings, as before
```

Every other sheet is compared with its latest version by a hash of its own content (linework, text, dimensions,
title; not the footer, date, FAST number or sheet number) and reported:

- `ALSO CHANGED: <keys> (not written)`: their content differs from the version Bob last saw. This is the line that
  catches an edit reaching a sheet nobody asked about.
- `RENUMBERED: <keys>`: same content, but the drawing now has more or fewer sheets, so their `SHEET n OF N` is old.
  `changed` redraws them; `set` refuses until then.
- `NEVER DRAWN: <keys>`: no sheet version yet (`baseline` draws them).

The sheet's revision box shows the letter (A for a never-filed document) with `FAST-<nnn>` under it and the row
`FAST-<nnn> - NOT ISSUED`; the footer is the sheet file's own name and location.

Measured 2026-11-17, one sheet, one target, PDF included: pipe supports 10 s, frame 13 s, tank modifications 13 s,
standard details 16 s, general arrangement 49 s, spools 56 s, piping arrangement 89 s. `--target both` (the default)
runs the two targets one after the other, so it takes twice that.

## What is checked on the way out

Each sheet drawing prints its layout problems and its DRF-FACE-001 result and says `CLEAN` or `NOT CLEAN`. Only a
CLEAN sheet goes to a reviewer.

- **Layout:** text on text, text on linework, leaders, dimension and ordinate lines, views off the sheet, tables that
  overflow (`plan_set_lib` box checks).
- **Sheet face (DRF-FACE-001, `harness/design-rules/drafting.yaml`):** `harness/checks/sheet_face.py` reads every text
  in the sheet's DXF; the toolkit also checks each table cell and note whole before it wraps. `set` and `combine`
  check each PDF page's text again. Run the check by hand with `python harness\checks\sheet_face.py <dxf ...>`.
- **Counts:** generators that have one run `--audit` (parts on the drawing against the takeoffs).

What prints follows the rule, done by the toolkit at print time: model axis letters become direction words
(`ps.axis_words`), commodity makers and catalogue numbers become `TBD COMMODITY; MANUFACTURER NOT SELECTED`,
`unknown` becomes `TBD`, internal references in brackets are dropped (`ps.scrub`). A note the rule would refuse stops
the generator; it is reworded in the basis file, or marked basis only, never dropped silently.

## Level 2: the set

`plan_set.py set <SET>` first builds the drawing in memory again (so it is compared with the files as they are now,
not as remembered; `--no-verify` skips that), then joins the latest PDF of every sheet in order into
`Set/<DOC>-<base>-set-<nnn>.pdf` (`<base>` is `rev<X>` after a filed revision, else `first`). It refuses, naming each
sheet, when a sheet was never drawn, changed since its latest version, prints an old `SHEET n OF N`, or has no PDF.
The `.json` beside the PDF records which sheet versions are in it. With no `<SET>` it assembles all seven.

## Level 3: the plan set

`plan_set.py combine` joins each drawing's latest assembled set (a drawing with none falls back to its latest
whole-drawing fast drawing) into one PDF with a linked index and bookmarks, in the target's
`Fast_Drawings/<prefix>-Full Planset/` (`CIP-TYP-Full Planset`, `Project-<code>-Full Planset`; Bob, chat,
2026-11-17; the folder was `combined` before). Seven drawings, no data sheets. A convenience copy, not a document.

## First time, and after the model pin changes

`plan_set.py baseline [<SET> ...]` writes every sheet of every drawing as a sheet version (about 20 minutes per
target; it can be stopped and finished later with `changed`). The generators read the model pin,
`job/Typical-<ID prefix>/_work/plan-set/model-pin.yaml` (the build the takeoffs come from and the view cache the views
come from; the cache is projected by `plan_set_lib/project_views.py`, cadgen environment, one agent at a time). The
saved copy of the pin is `plan-set-reference/model-pin.yaml`; `status` says when the two differ. After a pin change,
run `baseline`.

## The basis files

Each set keeps `<SET>.basis.yaml` beside its generator (format: `plan_set_lib/basis.py`). It holds the printed general
notes, open items (OI-n) and sheet notes in plain words, and beside each the record behind it (rule ids, TR rows,
DEC / Q / H numbers, files), plus `basis_only` facts that do not print. Hard rules 3 and 4 are met there, not on the
sheet. Placeholders: `{ref:SET}`, `{detail:D3}`, `{oi:key}`, `{note:key}`, `{tbd}`, `{tbd_commodity}`, and from the
build `{range:name}`, `{count:name}`, `{countword:name}`. The loader refuses a text that would fail the check, or one
with no basis.

## The whole-drawing tools (kept)

- A whole drawing in one go: `<generator> --fast --target typical|project --request "<words>"` writes
  `<DOC>-<base>-fast-<nnn>/` with a row in `Fast_Drawings/fast-log.md`. `--preview` writes a gitignored preview for
  your own look.
- `plan-set-reference/split_fast_sheets.py` breaks a whole-drawing fast drawing that already exists into one PDF and
  DXF per sheet inside its own fast folder (`uv run --no-project --with ezdxf --with pymupdf python ...`).
- A generator's own partial flags (`--sheets`, `--only`) are for previews only; sheet-first output refuses them,
  because a sheet drawn from part of a drawing cannot be trusted.

## Report

For a fast edit: as under "A fast edit" above. For a single-sheet command, per target: the sheet's PDF path, the
CLEAN line, the FAST number and the ALSO CHANGED list. No renders unless asked.

## Not a filed revision

Nothing here is filed, committed as a drawing, tagged or sent as a revision. Filing is the whole drawing, a separate
step, only on Bob's word, explained to him first (BR#1: what it accomplishes, how, why now, what he will see change):
skill `drawing-revise`, the generator with `--file --note "<32 characters>" --description "<what changed>"` (and
`CPME_ALLOW_FILE=1` for the plan set toolkit), from a filed model revision. That takes the next letter through
`harness/cad-lib/revfile.py`: DXF, native DWG and a PDF from the DWG, clouds, `revisions.csv`, read only (TR-06,
TR-07, TR-08). Before it files, the generator warns of every sheet whose content differs from the latest sheet
version drawn, so nothing is filed that nobody has looked at.
