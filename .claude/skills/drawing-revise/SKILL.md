---
name: drawing-revise
description: Make and file a drawing revision (P&ID, line segment diagram, process flow diagram or any new generator) through harness/cad-lib/revfile.py - CPME title block, sequential letter, revision-block note of 32 characters or less, clouds, DXF + native DWG + PDF from the DWG, read-only, revisions.csv, annotated tag at commit. Use whenever a drawing changes or a new drawing is to be handed to anyone.
---

# Drawing revise (TR-06, TR-07, TR-08)

## Before regenerating: fold in Bob's hand edits

Bob edits generated DWGs in AutoCAD LT. If the last filed DWG, or a working
DWG he has, is newer than its DXF: export it to DXF with Core Console
(`harness/cad-lib/dxf-to-dwg.ps1` round-trip section), diff the TEXT entities
against the generated DXF with ezdxf, put his changes into the generator's
`.py`, then regenerate and say so. Otherwise his edit disappears.

## Preview, then file

Generators: `<project>/03_Working_Design/CAD/06_Drawings/Generators/model-to-pid.py` (the project's P&ID,
`rp.PID_DOC_ID`, drawn from a filed model revision; `--fast` is the skill `pid-fast-edit`, never a filing), `line-segment-diagram.py`,
`process-flow-diagram.py`, once each generator exists (the first is written per "A new drawing" below). Each takes `--note` (required, at most 32
characters), `--description` (full change, for `revisions.csv`) and `--preview`.

```
.\harness\tools\venv\Scripts\python.exe <project>\03_Working_Design\CAD\06_Drawings\Generators\<generator>.py --preview --note "<note>"
```

`--preview` writes to `<project>/03_Working_Design/Exports/preview/` for your own check only; never show,
send or describe a preview as a revision. Then file:

```
.\harness\tools\venv\Scripts\python.exe <project>\03_Working_Design\CAD\06_Drawings\Generators\<generator>.py --note "<= 32 chars" --description "<what changed, why, Bob's words, records>"
```

`revfile.py` takes the next letter from the document's `revisions.csv`
(nobody assigns it; after Z comes AA), refuses if the target exists, clouds
everything added, changed or removed since the previous filed revision (not
the title band), writes DXF, DWG (`dxf-to-dwg.ps1`, ~5 s) and a PDF exported
from the DWG (`dwg-to-pdf.ps1`), checks the page count, files all three
read-only under `<project>/06_Issued_Revisions/Drawings/<DOC-ID>/<DOC-ID>-rev<X>.*` and appends
`revisions.csv`.

## A new drawing

- Write a generator under `<project>/03_Working_Design/CAD/06_Drawings/Generators/` that draws through
  `harness/cad-lib/cpme_titleblock.py` (`draw_cpme_sheet()`, content kept out
  of `reserved_bands(W)`) and files only through `revfile.py`. A generator
  that writes a drawing any other way is a defect.
- First hand-off is Rev A. No document ID yet: use the working name.
- DRAFT stamp until Bob approves; approval does not change the letter.

## Never

Modify, overwrite, rename or delete a filed drawing; reuse or skip a letter;
write drawings under `<project>/03_Working_Design/CAD/`; call `Start-Process -Wait` on Core Console
(it hangs on Autodesk helpers). Calling `dxf-to-dwg.ps1` by hand, pass
`-Layouts "02-Notes,03-Legend,01-PID"` as one comma-separated string (an
array does not survive `-File`).

## At commit (project-manager, on Bob's go)

Annotated tag `<DOC-ID>-rev<X>` on the commit that files it; listed under
"Drawings filed" in the commit body. Never move or delete a tag.

## Hand-off

`Filed <DOC-ID> Rev <X>: <project>/06_Issued_Revisions/Drawings/<DOC-ID>/<DOC-ID>-rev<X>.pdf` (pages,
cloud count, note), DWG sha256, Bob edits folded in (or none), TR rows
(TR-06, TR-07, TR-08, TR-11), CAPABILITY GAP, NEXT.
