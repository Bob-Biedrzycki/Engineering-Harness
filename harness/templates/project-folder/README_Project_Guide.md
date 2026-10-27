# Project folder guide

Every CPME project is filed the same way (Bob, chat, 2026-10-26). A **job** is the product line and its repo
(`job/JOB.md` says which). A **project** is one order within a job. Its folder is
`job/Project-<Project Number>-<Type>-<Top Level Version>`, for example `job/Project-0000-00-TST-001`.
The Project Number in the folder name is the project code, e.g. 0000-00; `project_number` in project.yaml is
CPME's short order number, e.g. 0000-0.
Inside the project, document and model IDs use the same name without the `Project-` prefix:
`0000-00-TST-001-PID-001`, `0000-00-TST-001-MODEL`.

Each new project is copied from `harness/templates/project-folder/` by `harness/scripts/project_new.py`, so
every folder exists from day one. An empty folder means "nothing of this kind yet", not "this doesn't apply".
`harness/checks/project_layout.py` reports any folder that has gone missing.

Knowledge that covers the whole job (all projects in the job) lives in `job/knowledge/`, not in a project. Reusable components live in the job library `job/components/` (cut sheet, STEP, install practice and `component-register.csv`).

The project names itself in `project.yaml` in its folder (project ID, project number, project code, model and P&ID
IDs, customer, repo); harness code reads every ID from there (`harness/lib/repo_paths.py`, `rp.PROJECT_INFO`).

Design rules have three levels (Bob, chat, 2026-10-26; Bob picks the level before a rule is written, CLAUDE.md hard rule 11):
1. Harness: company-wide, every CPME job, `harness/design-rules/`.
2. Job: all projects in the job (the job's product rules), `job/design-rules/`.
3. Project: this project only, `01_Design_Basis/05_Standards_Specifications/Design_Rules/` in this folder.

Which rules apply to a line is set by its service class (PIPE-SVC-001 in `harness/design-rules/piping.yaml`; the
job's and the project's `piping.yaml`, and the `service_class` column of `line-list.csv`): sanitary rules on
hygienic lines, the job's product rules (`job/design-rules/`) on the classes they name.

| Folder | Holds |
|---|---|
| `project.yaml` | Project identity (IDs, customer, repo). Large files go to the job's one Google Drive store, `job/drive-store.yaml` |
| **00_Project_Admin** | Scope, schedule, communications, commercial records, project controls |
| 01_Scope_Contract | Scope, exclusions, deliverables, purchase and change orders |
| 02_Schedule_Milestones | `schedule.md`, milestones, dependencies, progress |
| 03_Contacts_Responsibilities | Contacts, responsibility matrix, approval authority |
| 04_Meetings_Correspondence | Meeting notes, action lists, key correspondence |
| 05_Decision_Log | `DEC-####.md` decision records |
| 06_Commercial_Restricted | Budgets, costs, invoices (access-controlled) |
| 07_Project_Controls | `tooling.md`, `question-log.md`, `change-log.md`, `documents-to-obtain.md`; `Registers/` (documents, sources, interfaces, verification, standards, path crosswalk) |
| **01_Design_Basis** | Requirements, customer inputs, utilities, interfaces, criteria |
| 01_Customer_Requirements | Customer intake, `holds.md`, the P&ID and other customer source files |
| 02_Process_Design_Criteria | Volumes, temperatures, flows, pressures, cycle assumptions |
| 03_Utilities | Water, heating and cooling media and their returns, electrical, compressed air |
| 04_Site_Layout_Interfaces | Access, battery limits, tie-ins, drains, connections |
| 05_Standards_Specifications | Customer specs and controlled references; `Design_Rules/` holds this project's rule scope and values |
| 06_Assumptions_Open_Items | P&ID questions, equipment concerns, open rule questions, missing inputs |
| 07_Approved_Baselines | Approved requirement and design-basis snapshots |
| **02_Engineering** | Calculations and supporting analysis. A calculation folder may hold `Inputs/`, `Working/` and `Checked_Results/` |
| 01 … 12 | Process cycle, thermal heat-up, hydraulics and pumps, heat exchanger sizing (`04_Heat_Exchanger_Sizing`), tanks, mechanical/structural, pressure protection, electrical loads, instrument selection, risk reviews, scripts and models, summaries. A folder the project's equipment does not need stays empty. `05_Tank_Sizing/tank-modifications.md` is used only if the project has a tank |
| **03_Working_Design** | Editable design files. Generated output is never hand-edited |
| CAD/01_Master_Assembly | build123d source of the project model, `<MODEL-ID>/` |
| CAD/02 … 04 | Subassemblies, fabricated parts, piping (routes, spools, supports, connection details) |
| CAD/05_Purchased_Components | Project-only components (one-off adapters, customer-supplied items): `component-register.csv` and one `COMP-nnnn_<Maker>_<Model>/` folder each. Reusable parts live in the job library `job/components/` |
| CAD/06_Drawings | `Generators/` (drawing scripts) and drawing-type folders |
| CAD/07 … 09 | Reference geometry, design alternatives, presentation builders and assets |
| CAD/Fast_Builds | Fast model builds; viewing copies, gitignored, never filed |
| PID/01_Native | P&ID and PFD working files |
| PID/02_Tag_Lists | The six P&ID lists: equipment, instrument, line, valve, tie-in, motor load |
| PID/03 … 04 | Process descriptions; legends and symbols |
| PID/Fast_Edits | P&ID fast edits; working copies, gitignored, never filed |
| Electrical_Controls | Placeholder; the electrical and controls teams fill it in their own structure |
| BOM/01 … 05 | Master BOM, equipment list, piping/valves/fittings, electrical and instruments, spares |
| Exports | Regenerated build output (STEP, GLB, takeoffs, previews); gitignored working copies |
| **04_Vendor_Data** | Supplier documents and manufacturer CAD, unchanged. One folder per tag, for example `02_Pumps/P-101_Maker_Model/` holding `01_Datasheets/ 02_CAD_Originals/ 03_Drawings_Submittals/ 04_Manuals/ 05_Certificates/ 06_Technical_Correspondence/` |
| **05_Reviews_Changes** | Internal, customer and vendor reviews, change requests, approved changes, approvals, closed records. One folder per review (`REVW-001_…`) or change (`CR-001_…`) holding `Request/ Markups/ Responses/ Closure/` |
| **06_Issued_Revisions** | Everything handed off, read-only (TR-08) |
| Drawings/`<DOC-ID>`/ | Each filed drawing revision, `<DOC-ID>-rev<X>.dwg/.pdf/.dxf`, with `revisions.csv` |
| Models/`<MODEL-ID>`/ | Each filed model revision and its takeoffs, with `revisions.csv` |
| Portals/ | Filed portal revisions |
| 00_Issue_Index | `Issue_Register.csv`: every issue, its files, and the original each copy came from |
| `ISS-###_<YYYY-MM-DD>_<Purpose>/` | One per transmittal, made only when something is sent out. It holds read-only copies named for the issue (`ISS-001_<DOC-ID>-rev<X>.pdf`), the transmittal, and the package README |
| **07_Fabrication_QA** | Shop planning, material traceability, welding and finish, dimensional, pressure tests, electrical inspections, calibration, FAT, nonconformances, redlines, photos and shipping |
| **08_Handover** | Commissioning and SAT, punch list, as-built package, O&M, spares, training, warranties, final backups (placeholder for controls), acceptance |
| `_work/` | Gitignored working copies: daily close-out, tracking, logs, filing scratch, portal builds |
