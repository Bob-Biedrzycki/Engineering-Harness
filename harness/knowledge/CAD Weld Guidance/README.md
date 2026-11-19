# CAD Weld Guidance

Research notes on how to show welds on a welded stainless square-tube skid frame, both on the plan set (2D weld
symbols) and in the 3D model. Gathered 2026-11-19 at Bob's request. Company-wide (harness level): it holds for any
CPME skid frame, not one order.

These are **reference notes, not rules**. Nothing here is a design rule until it is written into `harness/design-rules/`
(hard rule 11: Bob says which level first). The governing documents are AWS A2.4 (symbols) and AWS D1.6 (stainless
structural welding; listed in `../Design Standards.md`, where A2.4 is not yet listed). Both are paid, so they are not
in this folder.

The notes are paraphrased from the public pages, with each source's URL, publisher, date and how much of it was read.
Full copies are not stored: the pages are copyrighted, and four of them refuse automated download.

| File | What it covers |
|---|---|
| `01 Weld Symbols on Tube Frames.md` | AWS and STRUCTURE magazine articles on symbols at tube (HSS) joints: one symbol per joint and wall, all-around misuse, flush joints become flare-bevel grooves, fillets have no default size; takeaways for our frame |
| `02 Weld Symbol Basics.md` | Primer on A2.4 symbol parts (arrow/other side, flag, all-around, tail, fillet and groove sizes) and how ISO 2553 differs |
| `03 Welds in the 3D Model.md` | Cosmetic vs solid weld beads (SOLIDWORKS, Inventor), model-attached weld symbols, associativity with drawings, ASME Y14.41; what carries over to build123d |
| `04 Standards and Pages Not Retrieved.md` | A2.4, D1.6, AISC Design Guide 24, AISC Steelwise and others that could not be read, with what is known and how to get them |

## Short version

**Plan set**
- Every fillet has a stated size; a blank fillet symbol has no default. A general note may give the default size, with a
  TYP symbol at a representative joint.
- One symbol per joint and per tube wall; the all-around circle only where one joint's weld truly runs around without
  crossing a 3-D corner.
- Flush (matched-width) tube joints: the flush faces are flare-bevel grooves, effective throat in parentheses.
- Mitred butt joints: state the throat or CJP; do not leave the groove symbol blank.
- Check D1.6:2017 for fillet size limits before fixing the general note.

**3D model**
- Every weld is a data record (joint, edges, type, size, length, side, all-around, field/shop) shown as a light cosmetic
  bead; solid bead bodies only where clearance or mass matters.
- Weld maps, weld tables and plan-set symbols are generated from those records, never typed on a sheet.
