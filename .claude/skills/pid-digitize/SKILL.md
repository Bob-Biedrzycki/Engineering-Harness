---
name: pid-digitize
description: Step 1 for a project - digitize the current revision of the project's P&ID (rp.PID_DOC_ID, named in job/JOB.md) into the <project>/03_Working_Design/PID/02_Tag_Lists line, equipment, valve, instrument, tie-in and motor-load lists plus pid-questions.md, with tags exactly as drawn, sources registered by sha256, and a Gate 1 package. Use when a new P&ID or a new P&ID revision arrives, or when a list disagrees with the drawing.
---

# P&ID digitize (step 1, process-engineer)

Reads only the current filed P&ID revision in `<project>/06_Issued_Revisions/Drawings/<PID-DOC-ID>/`
(`rp.PID_DOC_ID`; DWG/DXF/PDF) and its decisions. Writes only `<project>/03_Working_Design/PID/02_Tag_Lists/` lists and
`<project>/01_Design_Basis/06_Assumptions_Open_Items/pid-questions.md` (TR-03). Equipment is forced input (TR-02): copy it,
never size or re-select (where a project DEC brings sizing in, `job/JOB.md`:
agents size from the intake and Bob approves; copy the approved selections); concerns go once to `<project>/01_Design_Basis/06_Assumptions_Open_Items/equipment-concerns.md`.

## Steps

1. **Register the source.** Add the drawing files to `<project>/00_Project_Admin/07_Project_Controls/Registers/sources.csv`
   (SRC-nnnn, path, sha256). A P&ID that has not been filed yet is filed
   through `revfile.py` first (`drawing-revise`), or imported unchanged with a
   sha256 manifest if it is the customer's.
2. **Extract tags from the DXF with ezdxf**, then read the PDF to confirm.
   Watch for split TEXT bubbles ("LT" + "101" as two entities): a tag regex
   alone misses them. Retired tags shown on the sheet are excluded with a
   question.
3. **Fill the lists** (headers as in the project's existing lists):
   - `line-list.csv` (line_no, service_class, size_od_in, gauge, size_nps,
     schedule, material, spec, from_tag, to_tag, service, design_press_psig,
     design_temp_f, finish_ra, slope_req, insulation, pid_sheet, segment_ref,
     notes, pid_label). `service_class` is one PIPE-SVC-001 class per line
     (hygienic, utility-water, steam, condensate, relief-vent, air), from the
     drawing's service and line spec; `unknown` with a Q-nn when it isn't
     shown, never guessed.
   - `equipment-list.csv`, `valve-list.csv`, `instrument-list.csv`,
     `tie-in-list.csv`, `motor-load-list.csv`
   Tags and line numbers **exactly as drawn** (hard rule 2, "Units and naming").
   Unnumbered piping gets a repo working key `UNNUM-nn` in `segment_ref`, never
   an invented line number.
4. **Values not on the drawing** (from the quote or equipment selection) carry
   their source citation and a pid-questions entry "value supplied from <SRC>".
   Unknown stays `unknown` (hard rule 1).
5. **Retagging between revisions:** keep the old tag in a `tag_rev_<X>` column
   and apply any tag map in **one simultaneous pass**, never sequentially (old
   XV-101 -> XV-202 while old XV-111 -> XV-101 corrupts both). Drawings show
   current tags only; crosswalks live in the DEC and the `tag_rev_*` column.
6. **Questions** go in `pid-questions.md` as Q-nn, one direct sentence each,
   only where no document answers it (TR-05). Questions a project DEC has
   settled are not re-asked.
7. **Checks:** `harness/checks/tag_crosscheck.py` (exit 2 = not implemented
   yet; say so) and, once a model exists, `harness/checks/pid_consistency.py`.
8. **Gate 1 package:** list counts per list, the open Q-nn, assumptions, and
   the statement that the lists match the drawing. Bob approves Gate 1;
   agents never sign it.

## Hand-off

Lists changed with row counts, sources registered, questions opened, checks
with their result, TR rows (TR-01, TR-02, TR-03, TR-05), CAPABILITY GAP, NEXT
(`cad-design-engineer` layout, or `engineering-manager` Gate 1 package).
