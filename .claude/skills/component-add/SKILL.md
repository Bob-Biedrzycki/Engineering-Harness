---
name: component-add
description: Add an instrument, valve, fitting or equipment part to the job's component library (job/components, shared by every project in the job; a project-only part goes in the project's 03_Working_Design/CAD/05_Purchased_Components) - pick it, save the maker's cut sheet, get the manufacturer STEP (or build our own), research and cite the maker's installation practice, build that practice into a revised STEP (straight run, ends for the line's service class, branch fitting, gaskets), and file it as a component revision with its component-register.csv row (details and where every piece came from) and Drive pointers. Use for any new or changed component before the modeller places it.
---

# Component add (Bob, 2026-10-05; job library, Bob, 2026-10-26)

Bob: "The hard rules are prebuilt in and don't require creating or changing
scripts, and flagging or BLOCKING progress towards the end goal." The part
carries the practice; the modeller just places it and routes to it.

Bob, 2026-10-26: "Components should follow the same requirements we used
before, like cut sheet, step file, etc. It would also be great if there were a
components register to record where the information was obtained as well as
component details."

## Where it goes

- **Job library** `job/components/` (`rp.JOB_COMPONENTS`): any part another
  project in the job could use again. Look here first; reuse an existing `current` row before
  adding a part.
- **Project folder** `<project>/03_Working_Design/CAD/05_Purchased_Components/`:
  a part for this project only (one-off adapter, customer-supplied item). Same
  register columns, same folder layout.
- Each component is a folder `COMP-nnnn_<Maker>_<Model>/` with `01_Cut_Sheet/`,
  `02_STEP_Vendor/`, `03_STEP_CPME/`, `04_Install_Practice/` and `src/`
  (`job/components/README.md`). Ids are `COMP-nnnn`, sequential across the job
  library and every project folder.

## The five steps

1. **Pick.** The specified part governs (TR-02; where a project DEC brings
   sizing in, `job/JOB.md`, agents select from the intake and Bob approves); Todd's preferences (Alfa
   Laval pumps, ifm instruments, never Alibaba) apply to new selections only
   (TR-17). Record the tag exactly as on the P&ID in `notes` and `used_on`.
2. **Cut sheet and STEP.**
   - Save the maker's cut sheet / datasheet unchanged in `01_Cut_Sheet/`;
     record its URL and date (`cut_sheet_source`, `cut_sheet_obtained_on`).
   - Manufacturer STEP first (Bob, 2026-09-30: "when they are availible from
     the manufacturer it is really best to use the one they provide"), saved
     unchanged under the maker's file name in `02_STEP_Vendor/`, with URL, date
     and sha256 in the row. Download methods per vendor:
     [vendor-downloads.md](vendor-downloads.md). Fetch it yourself; only a
     sign-in is Bob's. Never handle his password.
   - No vendor model at all: build our own from the cut sheet in `src/<name>.py`
     (build123d). Catalog dimensions plus flagged `ASSUMPTION:` lines are
     enough; no question to a vendor for CAD (Bob, 2026-09-25).
3. **Research the installation practice** from the maker's manual, with page
   citations: straight run up and down, orientation, branch or tee type, leak
   port, torque; on hygienic lines dead leg; on other service classes the
   maker's and the job's practice for that service class (orientation, drops,
   the fittings the class needs ahead of an instrument, immersion length).
   Write it in `04_Install_Practice/` and cite it in
   `install_practice`. Check `job/design-rules/*.yaml` (job level, every
   project in the job) and `<project>/01_Design_Basis/05_Standards_Specifications/Design_Rules/*.yaml`
   (project level) before choosing a value: a job or project value beats the
   maker's minimum.
4. **Revise the STEP to carry it.** A spool assembly from a script in `src/`,
   with the ends of the line's service class (PIPE-SVC-001):
   - the vendor STEP placed unmodified;
   - the required straight run each side, so the part is already the right
     length: tube with weld ferrules at the run ends on hygienic lines, pipe
     with flanges or weld ends on pipe classes, as PIPE-SVC-001 sets them;
   - the right branch fitting: on hygienic lines a short-outlet tee where
     SAN-DL-002 needs it, TR-21 tee plus welded ferrule, TR-22 thread adapter
     case by case; on other classes the class's practice (for example a
     threaded or socket-weld boss, threaded only where PIPE-SVC-001 allows);
   - gasket at each joint: clamp gaskets at the 0.080 in gap (CPME practice) on
     hygienic lines, flange gaskets at the flange class's thickness;
   - markers as separate solids: flow arrow, port rings;
   - frame stated in the row (`frame`): origin on the run axis, +X = flow,
     +Z = up, run-end face positions.
   Check at build: every solid valid, overlaps only the expected ones.
5. **File and stop.** Name
   `COMP-nnnn-<TAG-or-type>-<Maker>-<Model>[-spool]-Rev<X>.step` in
   `03_STEP_CPME/`, read-only, never overwritten (TR-08): a change is the next
   Rev, a new register row with `supersedes` set and the old row's `status`
   left as filed (a later row marks it superseded). Fill every register column
   you can (`job/components/README.md` lists them); `unknown` where the source
   does not say. Then:

   ```
   .\harness\tools\venv\Scripts\python.exe harness\scripts\drive_store.py pointers
   .\harness\tools\venv\Scripts\python.exe harness\checks\component_register.py
   ```

   Push is at close-out, not now. Materials for the site go in
   `<project>/03_Working_Design/CAD/01_Master_Assembly/<MODEL-ID>/materials.yaml`
   (`rp.SKID_MODEL_ID`, named in `job/JOB.md`; once the model source
   exists) only if Bob asks for a look.

   **A part that has a look** (a `face_colours` entry in `materials.yaml`;
   none yet: the presentation site is dormant until the job has one; Bob,
   2026-10-12: "make the corrections and appropriate changes to prevent this
   in the future"): a component that wraps, re-orients, cuts or
   moves it (a new spool, a new port, a housing turn) changes the GLB node
   names around it. In the same change, update that entry's `part` regex so it
   matches the new node name (and still not the item node above, which also
   holds adapters and tubes), and the tag's row in `required_looks` (a new
   instrument with a look gets a new row). On the next `model-iterate`, read
   the `looks:` line: every required tag realistic, or the missing tag is the
   next fix. Never change the STEP or its region boxes to make the line pass.

## Don't

- Place the part in the skid model unless Bob asks in the same request ("lets
  not try to do it all at once"); offer it as the next step.
- Answer a best practice with a new routing check, gate or blocking rule when
  the part can carry it. New rule values go through `design-rule-add`.
- Copy a job-library part into a project folder; reference its COMP id instead.
- Reopen spools a project DEC has settled, or vendor CAD licence questions (Bob, 2026-10-09: "this is an in house model").
- Render pictures; give Bob the STEP path and a `cad_show` link.

## Hand-off

`Filed COMP-nnnn <TAG> Rev <X>: job/components/COMP-nnnn_<Maker>_<Model>/03_STEP_CPME/<file>` (face to face,
envelope, cut sheet and STEP sources), practices section cited, assumptions with their record,
"pointer written, push at close-out", TR rows (TR-02, TR-08, TR-15, TR-21,
TR-22), CAPABILITY GAP, NEXT (usually `cad-design-engineer` place it, or
`NEXT: none`).
