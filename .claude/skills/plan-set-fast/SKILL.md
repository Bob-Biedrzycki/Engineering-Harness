---
name: plan-set-fast
description: Fast drawings of a plan set (fabrication drawings, general arrangement, details, tank modifications, spools, piping arrangement; never data sheets) for one target - the job's typical set or the active project's quoting set - drawn by the set's generator with --fast --target, DXF + PDF in <level>/03_Working_Design/Exports/Fast_Drawings/<DOC>/<DOC>-<base>-fast-<nnn>/ with a fast-log.md row, checked against DRF-FACE-001 (sheet_face.py) on the way out. Nothing filed. Use when a plan set drawing is to be drawn, redrawn or shown for review without filing a revision.
---

# Plan set fast drawings (plan set round 2, 2026-11-16)

Bob, chat, 2026-11-16: "I would like both a typical set of drawings, and a set for quoting that can be sent out for
1072-01 to be completed as Fast drawings." A fast drawing is a numbered working drawing of one set for one target. It
is not a revision and is never filed by this skill. Same idea as `pid-fast-edit` and the fast model loop.

**No data sheets** (Bob, chat, 2026-11-17: "It is not necessary for our plan set to include self generated data
sheets for equipment, valves, and instrumentation."). Fast drawings of the plan set never run
`harness/scripts/data_sheets.py` and never make, redraw or review the equipment, valve and instrument data sheets;
the combined PDF leaves them out. A data sheet is made only when Bob asks for one.

## The two targets

One generator draws both sets; only the target changes.

| Target | Documents | Level folder | Title block |
|---|---|---|---|
| `typical` | `CIP-TYP-<SET>-nnn` | the job's typicals folder (`rp.TYPICAL`) | PROJECT "TYPICAL", LOCATION and NUMBER "N/A" |
| `project` | `<project folder name less Project->-<SET>-nnn` (e.g. `Project-1072-01-FRM-001`) | the active project (`rp.PROJECT`) | customer, location and number from `project.yaml` |

Cross-references on a sheet (`{ref:FRM2}`, `{detail:D8}`) name the same target's drawing numbers. The set keys and
their generators are in `job/Typical-<ID prefix>/03_Working_Design/CAD/06_Drawings/Generators/README.md`.

## Run

From the repo root, in the harness venv:

```
.\harness\tools\venv\Scripts\python.exe "<Generators>\<set folder>\<generator>.py" --fast --target typical|project --request "<the words it answers>" --note "<short note>"
```

- `--request` is required: Bob's words, or the review finding the drawing answers. It goes into the fast log.
- `--preview` instead of `--fast` writes a gitignored preview for your own look (never shown as a drawing).
- `--file` is refused unless `CPME_ALLOW_FILE=1` is set, and that is set only for a filing Bob has agreed to (below).
- The generator reads the model pin, `job/Typical-<ID prefix>/_work/plan-set/model-pin.yaml`: the build its takeoffs
  come from (`build`, `folder`, `takeoffs`, `reports`) and the view cache its views come from (`views_cache`). The
  cache is projected by `plan_set_lib/project_views.py` (stage 1, cadgen environment, one agent at a time); a
  generator never projects. A pin that names a build whose takeoffs predate a column the generator needs (for
  example the cut list's `hole_dia_in` / `hole_qty`) stops with a message naming it.

## Output

Never overwritten, one folder per drawing:

```
<level>/03_Working_Design/Exports/Fast_Drawings/<DOC>/<DOC>-<base>-fast-<nnn>/<DOC>-<base>-fast-<nnn>.dxf  and .pdf
<level>/03_Working_Design/Exports/Fast_Drawings/fast-log.md   (one row per drawing, written by the toolkit)
```

- `<base>` is `rev<X>` when the document has a filed revision (`<X>` its last letter), else `first`.
- `<nnn>` counts up per document and never repeats.
- The revision box shows `<X>` (a never-filed document shows `A`, the letter it takes when filed), with `FAST-<nnn>`
  in red under it, and the revision-block row reads `FAST-<nnn> - NOT ISSUED`.
- The footer is the drawing file's own name and location. Its form is one setting, `FOOTER_FORM` in
  `plan_set_lib/sheet.py` (`"path"`: the repo path; `"name"`: the file name only).
- The PDF goes through the DWG route; the DWG is removed from a fast folder. The `Fast_Drawings` folders are working
  copies: gitignored, not in the Drive store.

## What is checked on the way out

The generator prints every sheet's layout problems and the DRF-FACE-001 result, and says `CLEAN` or `NOT CLEAN`.
Only a CLEAN drawing goes to a reviewer.

- **Layout:** text on text, text on linework, leaders, dimension and ordinate lines, views off the sheet, tables that
  overflow (`plan_set_lib` box checks).
- **Sheet face (DRF-FACE-001, `harness/design-rules/drafting.yaml`):** `harness/checks/sheet_face.py` reads every
  text in the DXF; the toolkit also checks each table cell and note whole before it wraps. A finding makes the
  drawing NOT CLEAN. Run the check by hand with `python harness\checks\sheet_face.py <dxf ...>`, or with no
  arguments for the newest fast drawing of every document.
- **Counts:** generators that have one run `--audit` (parts on the drawing against the takeoffs).

What prints follows the rule, done by the toolkit at print time: model axis letters become direction words
(`ps.axis_words`, the ends named from the manifest), commodity makers and catalogue numbers become
`TBD COMMODITY; MANUFACTURER NOT SELECTED`, `unknown` becomes `TBD`, internal references in brackets are dropped
(`ps.scrub`). A note the rule would refuse stops the generator; it is reworded in the basis file, or marked basis
only, never dropped silently.

## The basis files

Each set keeps `<SET>.basis.yaml` beside its generator (format: `plan_set_lib/basis.py`). It holds the printed general
notes, open items (OI-n) and sheet notes in plain words, and beside each the record behind it (rule ids, TR rows,
DEC / Q / H numbers, files), plus `basis_only` facts that do not print. Hard rules 3 and 4 are met there, not on the
sheet. Placeholders: `{ref:SET}`, `{detail:D3}`, `{oi:key}`, `{note:key}`, `{tbd}`, `{tbd_commodity}`, and from the
build `{range:name}`, `{count:name}`, `{countword:name}` (tag lists the generator computes). The loader refuses a text
that would fail the check, or one with no basis.

## The combined PDF

```
uv run --no-project --with pymupdf --with pyyaml python "<Generators>\plan-set-reference\combine_plan_set.py" --fast --target typical|project
```

joins the latest fast drawing of every set of that target (no data sheets) into one PDF with a linked index, in the target's
`Fast_Drawings/combined/`. A convenience copy, not a document.

## Report

Give the PDF path of each drawing, the CLEAN line and the fast number. No renders unless asked.

## Not a filed revision

Nothing here is filed, committed as a drawing, tagged or sent as a revision. Filing a set is a separate step, only on
Bob's word, explained to him first (BR#1: what it accomplishes, how, why now, what he will see change): skill
`drawing-revise`, the generator with `--file --note "<32 characters>" --description "<what changed>"` (and
`CPME_ALLOW_FILE=1` for the plan set toolkit), from a filed model revision. That takes the next letter through
`harness/cad-lib/revfile.py`: DXF, native DWG and a PDF from the DWG, clouds, `revisions.csv`, read only (TR-06,
TR-07, TR-08).
