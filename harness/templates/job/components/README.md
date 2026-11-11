# Component library (job level: every project in the job)

Bob, chat, 2026-10-26: the component library belongs to the job, so every project in the job reuses the same parts
instead of copying them. "Components should follow the same requirements we used before, like cut sheet, step file,
etc. It would also be great if there were a components register to record where the information was obtained as well
as component details."

## What lives here

- `component-register.csv`: one row per component revision. It records what the part is, its connections,
  ratings and weight, and **where every piece of information came from** (cut sheet, STEP, installation practice),
  with dates and sha256. It is the one authoritative list (hard rule 8).
- One folder per component, `COMP-nnnn_<Maker>_<Model>/`:

  | Subfolder | Holds |
  |---|---|
  | `01_Cut_Sheet/` | The maker's cut sheet / datasheet (PDF), unchanged |
  | `02_STEP_Vendor/` | The maker's STEP, unchanged, under the maker's own file name |
  | `03_STEP_CPME/` | Our revised STEP that carries the installation practice (straight run, ends, branch fitting, gaskets), `COMP-nnnn-<TAG-or-type>-<Maker>-<Model>[-spool]-Rev<X>.step`, read-only, never overwritten (TR-08) |
  | `04_Install_Practice/` | The maker's installation practice summarized with page citations (straight run, orientation, drop, immersion, torque) |
  | `src/` | The build123d script that builds the revised STEP around the maker's STEP |

  Large files (STEP, PDF, DWG, ZIP) live in the Google Drive store with a `.drive` pointer beside them; the text
  records stay in git.

## The requirements for every component (skill `component-add`)

1. **Pick** the part (specified equipment governs, TR-02; where a project DEC brings sizing in, agents select and Bob
   approves (`job/JOB.md`); TR-17 preferences for new selections; never Alibaba).
2. **Cut sheet:** the maker's datasheet saved in `01_Cut_Sheet/`, with its URL and date in the register.
3. **STEP:** the maker's STEP, saved unchanged in `02_STEP_Vendor/` (maker's site, TraceParts, 3Dfindit, BIMobject,
   McMaster-Carr; Bob, chat, 2026-10-29). The maker's model is the default. We draw our own only as the last resort:
   after all five places are searched and
   the search is recorded in `vendor_step_source`, and no equally good part has a maker model. Our drawing is built
   from the maker's dimensioned drawing, marked as ours in `notes`, and deleted once the maker's model is obtained
   (Bob, chat, 2026-10-28: "that should not be a default"; skill `component-add` step 2).
4. **Installation practice:** researched from the maker's manual with page citations, written in `04_Install_Practice/`.
   A job or project rule value beats the maker's minimum.
5. **Revised STEP** that carries the practice, with the ends of the line's service class (PIPE-SVC-001), filed in
   `03_STEP_CPME/` as the next revision; a register row is added; `drive_store.py pointers` is run.

Nothing is parked on a vendor, on a later decision or on a note to Bob (Bob, chat, 2026-10-29): decide it with a
recorded reason, take an equal part, or ask Bob once. `harness/checks/component_register.py` reports every current
row that is not finished.

A change to a filed component is the next revision: a new register row, never an edit of the old one (TR-08). The one
exception is a self-drawn body replaced by the maker's model: it is deleted, not superseded, so only the maker-based
part remains (Bob, chat, 2026-10-28).

## Job library or project folder?

A part that any project in the job could use goes here. A part made for one project only (a one-off adapter, a
customer-supplied item) goes in that project's `03_Working_Design/CAD/05_Purchased_Components/`, which keeps the same
register columns and folder layout. Code reads both registers; the job library is read first.

## Register columns

`component_id` (COMP-nnnn), `revision`, `status` (current / superseded), `supersedes`, `category`, `description`,
`manufacturer`, `model`, `part_number`, `size`, `end_connections`, `service_classes` (PIPE-SVC-001), `material`,
`pressure_rating`, `temperature_rating`, `weight_lb`, `envelope_in` (L x W x H), `frame` (origin and axes of the revised
STEP), `cut_sheet_file`, `cut_sheet_source`, `cut_sheet_obtained_on`, `vendor_step_file`, `vendor_step_source`,
`vendor_step_obtained_on`, `vendor_step_sha256`, `cpme_step_file`, `cpme_step_sha256`, `install_practice`,
`licence`, `obtained_by`, `used_on` (project ids), `notes`.

## File paths and tags

A file column (`cut_sheet_file`, `vendor_step_file`, `cpme_step_file`) holds a path relative to the register's own
folder, e.g. `COMP-0001_<Maker>_<Model>/01_Cut_Sheet/<file>.pdf`; a value starting `job/` or `harness/` is read as
repo-relative. A file kept only in the Drive store is found through its `.drive` pointer.

A P&ID tag names its part through the `component_id` column of the project's equipment, valve and instrument lists
(`03_Working_Design/PID/02_Tag_Lists/`); the checks follow that link for weights and the like. The register
itself carries no tags, because one part serves many projects (`used_on` lists them).
