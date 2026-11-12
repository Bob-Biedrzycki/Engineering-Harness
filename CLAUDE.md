# CPME Skid Design Harness — Agent Instructions

This file is the master instruction set for AI agents working in this repository.

## Git: the global rules, and how this repo saves

**Git, GitHub, branches, commits, pull requests and repos follow only the "Git and backup" section of Bob's global
instructions** (`%USERPROFILE%\.claude\CLAUDE.md`; Bob, chat, 2026-11-04). This file says only *how* this repo
carries those rules out; it never adds or changes one. If a git rule turns up anywhere in this repo (a skill, an
agent file, a knowledge file), the global rules win and Bob is told so it can be removed.

How this repo saves (the save tool the global rules name):
- **Save:** `harness/scripts/track.py save --paths-file P --message-file M` (skill `github-tracking`). One command
  pushes the listed large files to Google Drive, commits the listed paths on `daily/<date>` in a separate worktree,
  and pushes the branch to GitHub; CI runs the checks on that push. A drawing revision is tagged with `--tag`.
- **End of day (pull request, merge, bringing this checkout up to date):** nothing to do here. When Bob says his
  day is over, the global `end-of-day` skill does it for every repo (`Claude-Git-Tools\day.py end-day`; global
  rules, Bob, 2026-11-09). `track.py daily-pr` and `track.py after-merge` are no longer part of the day. The site
  publish that `after-merge` used to run is not part of end of day; run `publish_site.py` on its own when a
  project has a site to publish.
- If `track.py` will not run, or reports the GitHub or Drive sign-in missing, stop and tell Bob (global failsafes).

> **TODD'S REQUIREMENTS GOVERN (Bob, 2026-09-24), EXCEPT GIT (Bob, 2026-11-04).** "All of Todd's asks must be
> met and satisfied by ALL AGENTS, ALL OF THE TIME." Git is no longer one of them: it follows the global rules
> only (see above). Every agent reads `harness/knowledge/Todd Requirements.md` (TR-01 to
> TR-26) on every task, complies with every row the task touches, and reports
> compliance in its handoff. Where anything in this file conflicts with a TR
> row, the TR row governs. **Moving forward there are NO EXCEPTIONS (Bob,
> 2026-09-24).** An agent never hands off work that fails a TR row it can
> meet; it fixes the work first. Only a row that needs Bob or someone outside
> the repo may be reported `NOT MET`, and nothing is described as done while
> it is.

> **NOTICE (Bob, 2026-09-24; replaces the 2026-09-23 suspension).**
> - **Linear is the agent task board** (Bob, 2026-09-28). This is
>   the move to a cloud-based workflow. Every task an agent can complete is one Linear
>   issue, named to the agent that does it: title prefix `[<agent>]` (for
>   example `[cad-design-engineer]`) and label `role:<agent>`. No cap on open
>   issues. Teams, projects, gates (as project milestones) and cycles follow
>   Linear's own recommended structure. The scrum master
>   (`project-manager`) opens and closes Linear issues; the named agent posts
>   progress, findings and dead ends as comments on its issue. Agents reach
>   Linear only through the `linear-server` MCP tools, signed in by Bob.
>   **The board fills itself (Bob, 2026-10-07: "do it").** The session that
>   starts a task opens its Linear issue (body = the prompt verbatim) before
>   the `Agent(...)` call; the agent posts its handoff verbatim as a comment;
>   every handoff ends with one `NEXT:` line that the delegating session acts
>   on; close-out audits the loops and the PR carries the issue IDs,
>   both as warnings, never stops. The steps are in the skill
>   `.claude/skills/agent-task`. **Verbatim copy only. Nothing blocks and
>   nothing waits on Linear:** if the Linear tools are missing, not signed in
>   or fail, do the work and write `LINEAR: unavailable (<reason>)` in the
>   handoff. One extra tool call to open, one to comment, nothing else.
> - **No GitHub issues or milestones**; work is tracked in Linear.
> - **Questions** between agents and to Bob stay in root `Agent-to-Agent Questions.md` /
>   `Agent-to-Bob Questions.md`.
> - "Where things are tracked" and "Work cycle" below follow this notice.

## What this repository is

A Git-based design environment for the **mechanical design of CPME skids** for beverage plants. The agent drafts and
checks; the human engineer reviews and approves through pull requests.

**This job and its current project are described in `job/JOB.md`, loaded here:**

@job/JOB.md

**Job and project (Bob, chat, 2026-10-26).** A **job** is a product line and its folder, which is one repo
(global "Git and backup"). A **project** is one
order within it, with its own folder `job/Project-<Project Number>-<Type>-<Top Level Version>/` (the Project Number in
the folder name is the project code, e.g. 0000-00; `project_number` in project.yaml is CPME's short order number,
e.g. 0000-0), laid out from `harness/templates/project-folder/` (every folder is explained in its
`README_Project_Guide.md`). Document and model IDs use the folder name without `Project-`. Everything about one order
(P&ID, lists, model, drawings, schedule, gates, customer, HOLDs, DECs, Drive folder, its rule scope and values) is the
project's; "job" means only the product line and its repo. Design rules sit at three levels: harness (company-wide),
job (every project in the job) and project. `<project>` means the active project folder (`rp.PROJECT`), named in
`job/JOB.md`.

**Shipping envelope (TR-18; Bob, 2026-09-24):** the skid ships in one piece
inside an enclosed 53 ft swing-door dry van. Every layout option fits
**628 in L x 96 in W x 106 in H** as shipped (a typical 53 ft van's inside
length and door opening less 2 in; Bob, 2026-11-02), with height measured from the
bottom of the base to the highest point, and is **as compact as possible**
within that. Values and sources are in
`<project>/01_Design_Basis/05_Standards_Specifications/Design_Rules/layout.yaml` `shipping_envelope`.

## Scope

**In scope:** layout, piping, frame, fabrication deliverables (BOM, cut lists,
spool lists, DXF), design verification against the piping rules of each line's service class
(PIPE-SVC-001) and the layout rules, and
the mechanical interfaces to controls and electrical (instrument process
connections, valve actuator envelopes, panel mounting and clearances).

**Out of scope:** PLC/HMI/SCADA programming, equipment sizing and re-selection
(the specified equipment is forced, TR-02) except where a project DEC brings
sizing in (`job/JOB.md`), the configurator (TR-26), structural
certification, and anything that requires a professional engineer's seal.

## First principles (Bob, 2026-11-11)

When a case is not named below, or something could go in two places, decide it from
`harness/knowledge/First Principles.md` before asking: (1) one place per fact; (2) a thing lives at the level where
it is true (harness, job, project; job level if it would hold for a different customer's order of the same
product); (3) the master flows down, a job never patches the harness; (4) filed things never change, a fix rides
the next revision; (5) a check either checks or says it did not; (6) unknown stays unknown until it is given, and
nothing is filled in for the sake of a folder or a field; (7) Bob decides rule levels, gates and Todd's rows, and
agents decide the rest, do it and report in a line. That file gives the reasoning, how to use it and worked cases.

## Hard rules

1. **Never invent** part numbers, dimensions, tag numbers, material grades,
   test results, approvals, or signatures. Use `unknown` or raise a question.
2. **Trace everything to the P&ID.** Every component in the model traces to a
   P&ID tag; every P&ID tag appears in the model. Every spool carries its line
   number.
3. **Cite the rule.** Every design decision names the design rule by its id
   (the rule and value in `harness/design-rules/*.yaml`, company-wide; job-wide
   values for every project in the job in `job/design-rules/*.yaml`; its scope and
   project-only values in `<project>/01_Design_Basis/05_Standards_Specifications/Design_Rules/*.yaml`), standard
   (`harness/knowledge/Design Standards.md`), or customer requirement behind
   it. If no rule exists, say so and propose one.
4. **Flag every assumption** in a visible `ASSUMPTION:` line in the deliverable
   and in the PR body.
5. **Customer and plant requirements are HOLDs until received in writing.** Do
   not design to assumed customer content. HOLDs stay tracked but never block
   design work (TR-23).
6. **STEP and DXF are derived output.** Edit build123d source, regenerate.
   Never hand-edit generated geometry in the repo. **Regenerating never
   overwrites a design that has been shown or handed off** (TR-08; Bob,
   2026-09-24: "YOU ARE NO LONGER TO OVERWRITE DESIGNS. THEY MUST BE LABELED
   AS REVISIONS."). Every design change is filed as the next revision, per
   "Designs" under "Drawing and design revisions".
7. **The engineer decides at gates.** Agents do not sign off Gate 1–4 items.
8. **One authoritative location per fact.** The project's lists in `<project>/03_Working_Design/PID/02_Tag_Lists/`
   and registers in `<project>/00_Project_Admin/07_Project_Controls/Registers/` are the source of truth; drawings
   and docs link to them.
9. Do not merge, release, transmit externally, or delete retained records
   unless the assignment explicitly authorizes it.
10. **Todd's requirements are met on every task, no exceptions** (`harness/knowledge/Todd
    Requirements.md`; Bob 2026-09-24). Work that fails a row the agent can
    meet is not handed off. Only a row blocked on Bob or an outside party is
    reported `NOT MET`, with the reason, and never skipped silently.
11. **Ask Bob where a new design rule goes** (Bob, 2026-09-25: "In the future
    when a new rule is to be added to either i would like to be asked which
    designation it belongs in."). Before writing a new rule, a new value field
    on a rule, or moving an entry between `harness/design-rules/`,
    `job/design-rules/` and `<project>/01_Design_Basis/05_Standards_Specifications/Design_Rules/`,
    ask Bob whether it is **harness** (company-wide), **job** (every project in
    the job) or **project** (this project only; Bob, chat, 2026-10-26), with a
    one-line recommendation and reason. A designation recorded as "job" before
    2026-10-26 meant the order and is project level now. Ask in
    chat, or in `Agent-to-Agent Questions.md` / `Agent-to-Bob Questions.md` from a subagent, and write nothing until
    he answers. Cite his answer in the entry's basis. See
    `harness/design-rules/README.md` and the skill `design-rule-add`.
12. **Never edit `harness/knowledge/Todd Requirements.md` unless Bob asks for
    that change** (Bob, chat, 2026-10-12: "Todd Requirements are never to be
    changed without my request for them to be changed."). That covers every
    TR row, note and table in it. Status and proposed changes go in the
    handoff or `Agent-to-Agent Questions.md` / `Agent-to-Bob Questions.md`, never in the file.

## Units and naming

- Units: inches and US customary for fabrication; state units on every value.
  Tube sizes are nominal OD (e.g. `2.0" OD`, `1.5" OD`); pipe is NPS and
  schedule (e.g. `2 in NPS Sch 40`).
- Line numbers, equipment tags, valve tags and instrument tags: **exactly as
  shown on the P&ID.** Do not normalize, reformat or abbreviate. Every P&ID
  from 2026-10-30 assigns them by `harness/design-rules/tagging.yaml`: ISA-5.1
  tags with loop numbers (`PI-101`, `TCV-201`) and line numbers
  `<service>-<series><nn>` (`SS-101`, `HWS-201`), one size and spec per line
  (TAG-*, LINE-NUM-001; Bob, chat, 2026-10-30).
- Spools: `<LINE>-SP<nn>` (e.g. `<LINE>-SP03`, with `<LINE>` a line number exactly as on the P&ID). Welds: `<SPOOL>-W<nn>`.
- Frame members: `FM-<nnn>`. Plates: `PL-<nnn>`. Supports: `PS-<nnn>`.
- Files: **source files** (scripts, CSV, YAML, MD, build123d) keep stable
  working names, and git history is their revision record. **Every drawing
  handed off** is also saved with its revision in the file name, per "Drawing
  and design revisions" below (TR-07, TR-08; conflict C-01).
- Dates ISO 8601. Materials by ASTM grade (`A270 S2 316L`, `A554 304`,
  `A106 Gr B`, `A53 Gr B`).
- **Everything CPME sends out follows `harness/style-guide/README.md`** (Bob, chat, 2026-11-10): proposals,
  quotes, data sheets, portals, slides and emails take the name, contact block, logo, colours and fonts from it
  (`brand.yaml`, `brand.css`), not from a copy kept in a job.
- **Every new drawing carries the CPME sheet format** (border, DRAFT stamp until approved, CPME title block
  with logo; no header text, no notes sheet, the drawing centred in the frame; Bob, chat, 2026-10-21, company-wide
  2026-11-11): use `harness/cad-lib/cpme_titleblock.py`. **Revision letters
  are sequential and nobody assigns them** (Bob, 2026-09-24; supersedes the
  2026-09-23 rule that the engineer assigns letters). The DRAFT stamp stays
  until the engineer approves; approval does not change the letter.

## Repository map

Two halves (CPME practice): `harness/` is what every CPME job reuses;
`job/` is this job (`job/JOB.md`): job-wide knowledge, design rules and components, the job's typicals folder
(`job/Typical-*/`, laid out like a project; Bob, chat, 2026-11-09) plus one numbered folder per
project (Bob, chat, 2026-10-26). Code names locations through `harness/lib/repo_paths.py`, never by counting
parent folders. `rp.PROJECT` is the active project folder: the only `job/Project-*` folder, or the one named in
`CPME_PROJECT` or `job/active-project.txt`. A new project is made only by `harness/scripts/project_new.py`,
and `harness/checks/project_layout.py` reports any template folder that has gone missing. Paths in records
written before 2026-10-26 (filed revisions and their `revisions.csv`, DEC files, question entries, daily handoffs)
keep the old layout, and `<project>/00_Project_Admin/07_Project_Controls/Registers/path-crosswalk.csv` maps
each old path to its new one.

```
CLAUDE.md  README.md     This file; setup and status
Agent-to-Agent Questions.md  Agent-to-Bob Questions.md       Questions between agents, and Bob's copy
.claude/                 agents/ (one subagent per role), skills/, settings
.github/                 PR template, CODEOWNERS, labels, CI checks
harness/
  knowledge/             Team, standards, documents, lists, setup plan,
                         Todd Requirements.md (TR-01..TR-26, binding on every agent),
                         Approval Ladder.md: what needs Bob's word, by rung and category,
                         First Principles.md: the seven principles the structure decides by
  checks/                Automated verification scripts (P&ID-to-model, sanitary, interference)
  scripts/               model_iterate.py / model_accept.py (+ model_file.py) / closeout.py (the model tiers),
                         track.py (GitHub tracking), drive_store.py (Google Drive store),
                         label sync, lists workbook
  structural-models/     skidframe: skid frame load-bearing models (AISC 370/360, ASCE 7) for the Gate 3 check;
                         `run` saves each result in <project>/02_Engineering/06_Mechanical_Structural/Frame_Calcs/
  templates/             Review checklist, project-folder/ (the project tree)
  design-rules/          Company-wide design rules (YAML), engineer-owned; README.md
                         gives the three levels (harness, job, project) and that Bob is asked first
  cad-lib/               revfile.py (drawing filing), dxf-to-dwg / dwg-to-pdf,
                         cpme_titleblock.py (CPME sheet format), render_png.py
  style-guide/           CPME USA style guide (company-wide): name, contact block, logo files, colours, fonts,
                         writing, and the layout of proposals, data sheets, portals, slides and signatures;
                         brand.yaml / brand.css hold the values for scripts and HTML
  lib/repo_paths.py      Every repo location, by name
  requirements*.txt      Pinned Python dependencies (repo venv; cadgen venv)
  tools/                 venv/ and venv-cadgen/ (gitignored, rebuilt from requirements)
job/
  JOB.md                 This job and its current project (loaded by CLAUDE.md)
  knowledge/             Job-wide: the product's research and design framework, review addendum,
                         Todd Requirements job notes, Todd Direction.md, Todd Questions.md, todd-notes/
  design-rules/          Job-wide design rules (level 2, every project in the job); README.md
  drive-store.yaml       Google Drive store for the whole job: the Drive folder and the large-file rules
  components/            Job component library: component-register.csv (details and sources) and one
                         COMP-nnnn_<Maker>_<Model>/ folder per part (cut sheet, vendor STEP, CPME STEP,
                         install practice, src); large files in the Drive store
  Typical-<ID prefix>/   The job's typicals (typical P&IDs, typical models, their GA drawings), laid out like a
                         project with only the folders they use (Bob, chat, 2026-11-09): 03_Working_Design/
                         (CAD/01_Master_Assembly model source and shared library, CAD/06_Drawings/Generators,
                         CAD/09_Presentation, PID/02_Tag_Lists), 06_Issued_Revisions/ (Drawings/, Models/),
                         _work/; README_Project_Guide.md there; rp.TYPICAL and the rp.JOB_* names
  Project-<code>-<TYPE>-<nnn>/   One folder per project, from harness/templates/project-folder/
    project.yaml         Project identity (project_id, project_number, project_code, model_id,
                         pid_doc_id, repo, Linear)
    README_Project_Guide.md  What every folder holds
    00_Project_Admin/    02_Schedule_Milestones/schedule.md; 05_Decision_Log/ (DEC-####.md);
                         07_Project_Controls/ (tooling, question-log, change-log, documents-to-obtain,
                         Registers/: documents, sources, interfaces, verification, standards, path-crosswalk)
    01_Design_Basis/     01_Customer_Requirements/ (intake, holds.md, P&ID sources);
                         05_Standards_Specifications/Design_Rules/ (this project's rule scope and values,
                         engineer-owned); 06_Assumptions_Open_Items/ (pid-questions, equipment-concerns,
                         open rule questions, P&ID revision requests)
    02_Engineering/      Calculations: thermal, hydraulics and pumps, exchanger, tanks
                         (tank-modifications.md), structural (frame-calc/), and the rest of 01..12
    03_Working_Design/   CAD/01_Master_Assembly/<MODEL-ID>/ (build123d source), 05_Purchased_Components/
                         (project-only components), 06_Drawings/Generators/, 09_Presentation/;
                         CAD/Builds/ (every model build, numbered, gitignored); PID/02_Tag_Lists/ (the six
                         P&ID lists, CSV);
                         PID/Fast_Edits/ (gitignored, pid-fast-edit); BOM/; Electrical_Controls/
                         (placeholder for the other teams); Exports/ (gitignored drawing previews)
    04_Vendor_Data/      Supplier documents and CAD, <category>/<tag>/ (Drive store)
    05_Reviews_Changes/  Internal, customer and vendor reviews, change requests, approvals
    06_Issued_Revisions/ Drawings/<DOC-ID>/ and Models/<MODEL-ID>/, one <ID>-rev<X>/ folder per handed-off revision,
                         immutable, revisions.csv per document (TR-08); large files in the Drive
                         store with <file>.drive pointers; Portals/; 00_Issue_Index/
                         (Issue_Register.csv) and ISS-###_<date>_<purpose>/ transmittal packages of
                         renamed copies (Bob, 2026-10-26)
    07_Fabrication_QA/  08_Handover/   Shop, QA, FAT, commissioning and handover records
    _work/               Gitignored working copies: filing/, daily/, tracking/, logs/, portal
```

## Adding an instrument or component (Bob, 2026-10-05)

Bob: "The hard rules are prebuilt in and don't require creating or changing scripts, and flagging or BLOCKING
progress towards the end goal." Every new instrument or component goes: pick it; save the maker's cut
sheet; get the manufacturer STEP (the maker's own model is the default; we draw our own only after a recorded search of
the maker's site, TraceParts, 3Dfindit, BIMobject and McMaster-Carr (Bob, chat, 2026-10-29) finds none and no equally
good part has one, and it is deleted
once the maker's model is obtained; Bob, chat, 2026-10-28: "that should not be a default"); research and
cite the maker's installation practice;
revise the STEP so the part carries it (straight run, ends for the line's service class, branch fitting,
orientation), filed as a new component revision (TR-08); done, the modeller places it. Components live in
the job library `job/components/`, shared by every project in the job, one `COMP-nnnn_<Maker>_<Model>/`
folder each, with `component-register.csv` recording each part's details and where every cut sheet, STEP
and practice came from (Bob, chat, 2026-10-26). A part for one project only goes in that project's
`03_Working_Design/CAD/05_Purchased_Components/`, same layout. The steps are in the skill
`.claude/skills/component-add`.

Do not answer a best practice with a new routing check, gate or blocking rule when a better part solves it.
Checks report; they do not block design progress. Known findings are accepted with their record: a clash or a pipe
support finding Bob has accepted is written, with his words, in the project's
`<project>/01_Design_Basis/06_Assumptions_Open_Items/accepted-findings.yaml`, which `interference.py` and
`pipe_supports.py` read (`harness/lib/accepted_findings.py`; Bob, chat, 2026-11-10), so no check file holds a
project's records; the `sanitary.py` ACCEPT list is still in the check.

## Workflow steps and hand-off (TR-01, TR-03)

Work runs in this order. Each step reads only its named inputs and writes only
its named outputs, so a revision means changing one input, rerunning one step
and getting the new output. Outputs are regenerated by script from inputs,
never hand-edited.

| Step | Owner | Reads | Writes | Skill |
|---|---|---|---|---|
| 0. New project | project-manager | `harness/`, Bob's project details | A new `job/Project-*` folder from the template (`project_new.py`), Drive store, Linear project; a new job (product line) also gets its own repo | `job-bootstrap` |
| 1. P&ID data | process-engineer | Current P&ID revision in `<project>/06_Issued_Revisions/Drawings/<PID-DOC-ID>/` | `<project>/03_Working_Design/PID/02_Tag_Lists/` line, equipment, valve, instrument, tie-in and motor-load lists; `pid-questions.md` | `pid-digitize` |
| 2. P&ID revision | process-engineer (content), cad-design-engineer (generation, `<project>/03_Working_Design/CAD/06_Drawings/Generators/`) | Previous revision, `<project>/00_Project_Admin/05_Decision_Log/`, revision requests | New revision DWG + PDF filed in `<project>/06_Issued_Revisions/Drawings/`, with revision block row and clouds (TR-06..08) | `drawing-revise` |
| 3. Equipment (forced) | process-engineer | `equipment-list.csv` as specified, `job/components/component-register.csv` | `<project>/01_Design_Basis/06_Assumptions_Open_Items/equipment-concerns.md` only. No sizing, no re-selection (TR-02). | `component-add` (STEPs only) |
| 4a. Skid layout | cad-design-engineer | Step 1 lists, `<project>/03_Working_Design/CAD/05_Purchased_Components/`, `harness/design-rules/*.yaml`, `job/design-rules/*.yaml` and `<project>/01_Design_Basis/05_Standards_Specifications/Design_Rules/*.yaml`, `<project>/02_Engineering/05_Tank_Sizing/tank-modifications.md` (only if the project has a tank) | `<project>/03_Working_Design/CAD/01_Master_Assembly/<MODEL-ID>/` source, builds in `<project>/03_Working_Design/CAD/Builds/`, layout options, general arrangement drawing | `skid-layout` |
| 4b. Pipe routing | cad-design-engineer | `line-list.csv`, step 4a output | `<project>/03_Working_Design/CAD/01_Master_Assembly/<MODEL-ID>/piping/<line>/`, spool list, weld map; piping split into separate bodies at every weld (TR-24) | `pipe-route` |
| 4c. Takeoffs | cad-design-engineer | Step 4b model | Full BOM (TR-16), laser-cut-ready cut lists (TR-14), clamp, flange and gasket schedule | `model-iterate`, `model-file` |
| Review | mechanical-piping, controls, electrical, engineering-manager | Outputs of 4a-4c | Findings against the rules and the TR register | `gate-package` |

Skills (`.claude/skills/`) hold the how; this file holds the rules. Also:
`component-add` (any new part), `partslib-load` (its facts and PDFs into Todd's PartsLib), `design-rule-add` (before any rule YAML edit,
hard rule 11), `pid-fast-edit` (P&ID working copies; drafting rules in
`harness/design-rules/drafting.yaml` apply to a brand new P&ID only, CPME practice),
`agent-task` (before every `Agent(...)` call), `model-accept` (Bob accepts fast edits as a revision), `closeout`
(optional full check run) and `github-tracking` (how this repo saves; see "Git" at the top). When a rule here changes,
the skill that repeats it changes in the same edit.

## Drawing and design revisions (TR-06 to TR-08)

**Drawings.** The working steps (Bob's hand edits folded in first, preview,
file) are in the skill `.claude/skills/drawing-revise`; the rules are below.
- **Every drawing generator files through `harness/cad-lib/revfile.py`, no
  exceptions.** It takes the next letter, draws the revision clouds, writes
  DXF, native DWG (`harness/cad-lib/dxf-to-dwg.ps1`) and a PDF exported from that DWG
  (`harness/cad-lib/dwg-to-pdf.ps1`), checks the page count, moves all three into
  the drawings folder read-only, and appends `revisions.csv`. A generator
  that writes a drawing any other way is a defect. Current generators: none
  on this project yet; the first is written per skill `drawing-revise` "A new
  drawing" and files through `revfile.py`. Every generator takes `--note`
  (required) and `--description`.
- **P&ID fast edits** (Bob, 2026-10-11; skill `pid-fast-edit`): `model-to-pid.py
  --fast` (run from the working copy in that folder's `src/`) writes a DXF + PDF
  working copy `<PID-DOC-ID>-rev<X>-fast-<nnn>` into its own folder under
  `<project>/03_Working_Design/PID/Fast_Edits/` (gitignored, never overwritten, logged in its
  `fast-log.md`). Like `--preview`, it is not a filed revision. A fast edit's changes
  are held in that folder's `fast-changes.yaml` and no project file is edited until
  Bob says to convert it.
- `--preview` writes to `<project>/03_Working_Design/Exports/preview/` (gitignored) for the agent's own
  check only. A preview is never shown, sent or described as a revision.
- **One folder per revision** (Bob, chat, 2026-10-30: "Everything like for
  them should be in a folder for each rev."). A document folder under
  `06_Issued_Revisions/Drawings/` or `06_Issued_Revisions/Models/` (the job's
  typicals folder and every project) holds only its `revisions.csv` and one folder per
  revision, `<DOC-ID>-rev<X>/`, with every file of that revision inside it.
  `revisions.csv` `file` is `<DOC-ID>-rev<X>/<name>`. `revfile.py` and
  `model_file.py` file this way (`rp.rev_folder`); nothing is filed by hand.
  `harness/checks/filed_layout.py` fails CI and close-out on anything loose
  (repo integrity, like `drive_pointers.py`); its `--fix` moves loose files in
  without renaming them and records the moves in `path-crosswalk.csv`.
- Every drawing handed to Bob or anyone else is filed under
  `<project>/06_Issued_Revisions/Drawings/<DOC-ID>/<DOC-ID>-rev<X>/` as a native DWG plus a PDF exported
  from that DWG, with the DXF beside them (TR-06).
- File names carry the revision (TR-07): `<DOC-ID>-rev<X>.dwg` / `.pdf`.
  A drawing with no document ID yet uses its working name as `<DOC-ID>`.
- **Revision letters are sequential** (Bob, 2026-09-24). A drawing's first
  hand-off is Rev A. Each later hand-off takes the next letter after the
  last row in that document's `revisions.csv`. Nobody assigns, skips or
  reuses a letter. ASSUMPTION: after Z the sequence continues AA, AB and so
  on (common drafting practice; no drawing is near Z yet).
- **A filed drawing is never modified, overwritten, renamed or deleted**
  (TR-08). Any change after a hand-off is the next letter. Generators read
  the next letter from `revisions.csv`, check that the target revision folder
  does not exist, and stop if it does.
- Every revision adds a revision-block row with a note of what changed (at
  most 32 characters; detail goes in `--description`), and clouds with a
  revision delta around everything added, changed or removed since the
  previous filed revision (TR-07). The title-block band is not clouded.
- Each document folder holds `revisions.csv` (document_id, revision, file,
  file_date, sha256, bytes, source, notes, description), one row per filed
  file, written only by `revfile.py`, beside the revision folders.
- Generators do not write drawings under `<project>/03_Working_Design/CAD/`.

**Designs** (TR-08; Bob, 2026-09-24, verbatim: "YOU ARE NO LONGER TO
OVERWRITE DESIGNS. THEY MUST BE LABELED AS REVISIONS.")
- A design is any model output shown or handed to Bob or anyone else: 3D
  assembly STEP, GLB or other viewer/Blender exports, and the takeoffs built
  from the model (spool list, weld map, cut lists, BOM, clamp schedule, layout
  note). The same rules as drawings apply.
- Every design handed off is filed under
  `<project>/06_Issued_Revisions/Models/<MODEL-ID>/<MODEL-ID>-rev<X>/` (one folder per
  revision, as for drawings) with the revision in every file name,
  `<MODEL-ID>-rev<X>.<ext>` (takeoffs as `<MODEL-ID>-rev<X>-<list>.csv`), made
  read-only, with a `revisions.csv` row per file (sha256, bytes, note of what
  changed). Letters are sequential from Rev A, as for drawings.
- **Inside a model revision folder** (Bob, chat, 2026-11-03: "Move them into
  sub folders once"; `rp.model_subfolder`, checked by `filed_layout.py`): the
  model (GLB, zipped STEP and their `.drive` pointers) at the top, then
  `Takeoffs/` (BOM, cut lists, spool list, weld map, fittings by spool, clamp
  schedule, piping mass), `Reports/` (layout note, list delta, manifest, pipe
  support calc, routing report), `Views/` (the four review pictures) and, only
  when one is made, `Presentations/P<nn>/`. File names keep the full
  `<MODEL-ID>-rev<X>` prefix; folder names are short. Revisions locked before
  2026-11-03 were moved once (`harness/scripts/model_subfolders.py`, moves in
  `path-crosswalk.csv`). Drawing revision folders stay flat.
- **The filed STEP is zipped** (CPME practice; Bob, 2026-10-02):
  `<MODEL-ID>-rev<X>.step.zip` holding one STEP named `<MODEL-ID>-rev<X>.step`.
  The `revisions.csv` row and the pointer hash the zip. Consumers (Blender,
  exploded parts, checks) unzip to `<project>/_work/unzipped/` with
  `harness/lib/filed_step.py` and never write beside the filed file.
- **GLBs** (Bob, 2026-10-02: "future models to
  primarily be stored where they have, and only done for presentation and
  stored that way when necessary"): the **filed GLB** of a design revision is
  the plain build export, as today. A **presentation** (lifelike pictures, the
  presentation model with realistic surfaces, and the Blender scene with the
  shop and cameras) is made only on request and is locked inside the model
  revision it was made from (Bob, chat, 2026-11-03: "filed in the Rev folder
  with all of the other rev files"; names "match the files/revisions they came
  from", no repeated words): `<MODEL-ID>-rev<X>/Presentations/P<nn>/` holding
  `<MODEL-ID>-rev<X>-P<nn>.glb`, `<MODEL-ID>-rev<X>-P<nn>.blend` and
  `<MODEL-ID>-rev<X>-P<nn>-<view>.png`, with rows in that model's
  `revisions.csv` (notes start `P<nn>`). P numbers count within one revision;
  a locked P folder never changes. Tool: `job/Typical-<ID prefix>/03_Working_Design/CAD/09_Presentation/`
  (README.md). The **web GLB** (decimated for the browser) is a portal asset,
  not a locked file.
- **3D print files** (Bob, 2026-10-01: "make sure all future 3D Print files
  do so in the future") are filed under `<project>/06_Issued_Revisions/Models/3D Print Models/`, and
  **every file carries the revision in its own name**, including each
  single-piece STL/3MF in subfolders: `<MODEL-ID>-rev<X>-<piece>.<ext>`,
  never just a `revX` folder.
- **A filed design is never modified, overwritten, renamed or deleted.** A
  change to the model, however small (removing a part, moving a nozzle), is
  the next letter. Before any rebuild, check that the next revision's folder does
  not exist yet, and stop if it does.
- The build folders (`<project>/03_Working_Design/CAD/Builds/`) and `<project>/_work/` are
  working copies. Never point Bob at a working copy as the design: give him
  the filed revision's path. When he has been viewing a working copy, file it
  as a revision before rebuilding over it.
- Two models of the same skid are two `<MODEL-ID>`s, each with its own
  revision sequence. One agent never rebuilds or re-exports another's model.
- Models are filed with `harness/scripts/model_file.py` (skill `model-file`,
  from 2026-10-02), which does exactly the above; before it, revisions were
  filed by hand. The filing step is part of the change, not a follow-up.

**Issue packages** (Bob, chat, 2026-10-26: "For a Human it is helpful to have a copy of the issued files in
the folder"). When anything is sent out, it goes as a package
`<project>/06_Issued_Revisions/ISS-###_<YYYY-MM-DD>_<Purpose>/`. The package holds read-only copies of the
filed revisions, each renamed for the issue (`ISS-001_<DOC-ID>-rev<X>.pdf`), plus the transmittal and a package
README. Every copy gets a row in `00_Issue_Index/Issue_Register.csv` (issue, copy, original path, document,
revision, sha256). The per-document folders under `Drawings/` and `Models/` remain the record that revision
letters come from (TR-08); a package never takes a letter. Issue numbers are sequential, like letters.

**Large files: the Google Drive store** (Bob, 2026-09-28, verbatim:
"All large files or Large Directories should use Google Drive as the database
with pointers referencing this folder.")
- Large files are never committed. Any file of 5 MiB or more, and every CAD,
  drawing, archive or datasheet file under `<project>/06_Issued_Revisions/`, `<project>/04_Vendor_Data/` and the component
  libraries, lives in the job's one Google Drive folder named in `job/drive-store.yaml`
  (shared by `job/components/` and every project; Bob, chat, 2026-10-26), at the same
  path it has in the repo. Git holds a pointer beside that path,
  `<file>.drive` (path, bytes, sha256, md5, mtime, folder). The text records
  next to them (`revisions.csv`, takeoffs, notes, manifests, source records)
  stay in git. `track.py save` runs the Drive push with every save.
- `harness/scripts/drive_store.py` is the only writer of pointers and of the
  managed block in `.gitignore`: `pointers` after adding or filing a large
  file, `push` to copy it into the Drive folder, `pull` to fetch missing files
  into a checkout, `verify` to hash both sides against the pointers. A
  pointer exists for every large file before it is Saved; `push` runs before
  the commit in every `track.py save`.
  A pointer whose file has changed is refused (TR-08); the change is the next
  revision.
- Transport is rclone (Bob, 2026-09-28) through the remote named in
  `job/drive-store.yaml` (`rclone_remote`, an alias of the machine's
  `cpme-drive` sign-in), rooted at the Drive folder. Each machine creates that
  remote once with Bob's own Google sign-in (command in the YAML); agents
  never sign in. Drive reports MD5, so `verify` checks size and md5 on the
  Drive side and sha256 locally. `--root <folder>` uses a plain local folder
  instead (Google Drive for Desktop, or a staging mirror); that path is
  machine-specific and never goes in a tracked file.
- `harness/checks/drive_pointers.py` fails CI if a large file is tracked or a
  pointer is malformed. Never use Git LFS here.

**What `track.py save` expects** (how this repo carries out the global rules).
- The paths file lists only this piece of work's files (other sessions share the checkout).
- The message file has a subject line `<area>: <what changed>` of at most 72 characters, then a body with **Why**,
  **Changed IDs**, **Sources and rules cited**, **TR rows touched**, **Drawings filed** (`<DOC-ID>-rev<X>`), and
  **Checks run**. `track.py` refuses a message without these sections.
- `--tag` puts an annotated tag `<DOC-ID>-rev<X>` on the commit that saves a drawing revision. Never move or
  delete a tag.
- `.gitattributes` marks DWG, PDF, STEP, GLB, ZIP and images binary.

**GitHub sign-in** (Bob, 2026-10-07). `track.py` writes as `Bob-Biedrzycki`. The gh sign-in lives in
`%USERPROFILE%\.config\gh` (`GH_CONFIG_DIR`, persisted for every window) and
stays in the Windows keyring, so saving never needs a new sign-in.
**Never hand Bob a raw `gh auth ...`, `gh auth refresh` or `git push` command
to type.** If `track.py status` reports NOT signed in or the `workflow` scope
MISSING, give Bob exactly the one command `status` prints (the sign-in
script by full path) and stop. Nothing else about credentials is an agent's
to do.

## The agent team

Each role in `.claude/agents/` mirrors a human role in `harness/knowledge/Team.md`.
Invoke the role whose deliverable you are working on. The **engineering-manager**
agent is the reviewer of last resort before anything goes to the human engineer.

| Agent | Owns (drafts and checks) | Hands off to |
|---|---|---|
| `project-manager` | Scope, schedule, change log, question log, customer HOLD list, gate readiness | everyone |
| `process-engineer` | P&ID digitization (line/equipment/valve/instrument lists), tag integrity, P&ID-to-model consistency; sizing records where a project DEC brings sizing in | cad-design, mechanical-piping, controls |
| `cad-design-engineer` | build123d source, layout options, frame, piping routing, STEP/DXF, BOM, cut lists, spool lists | mechanical-piping, engineering-manager |
| `mechanical-piping-engineer` | Mechanical piping review by service class (PIPE-SVC-001): each class's company-wide rules plus the job's rules for it (`job/design-rules/`), SAN-* sanitary rules on hygienic lines; slope, drainability, trap and relief arrangement, weld and fitting spec | cad-design (rework), engineering-manager |
| `controls-engineer` | Instrument index and valve schedule *as mechanical interfaces*: process connections, actuator envelopes, I/O tag consistency with P&ID | cad-design, electrical |
| `electrical-engineer` | Panel envelope, mounting, clearances, conduit/cable routing space, NFPA 79 / UL 508A interface items on the skid | cad-design |
| `engineering-manager` | Design review checklists, gate packages, PR review, drawing approval readiness | human engineer |
| `software-developer` | The repo's own code (Bob, 2026-10-05): `harness/scripts/`, `harness/checks/`, `harness/lib/`, `harness/cad-lib/` tooling, `<project>/03_Working_Design/CAD/09_Presentation/` builders and web assets, CI, venvs and pinned dependencies. Writes and runs code and tests; never geometry, portal content or the daily commit | engineering-manager; cad-design, project-manager as users of the tools |

Every agent file's `tools:` line names both shell tools, `Bash` and
`PowerShell`, because the desktop app exposes only the host's shell to a
subagent and silently drops the other name. On this Windows host an agent
file that named only `Bash` got no shell at all (found 2026-09-24, cause
confirmed 2026-10-05), so it could write code but not run it. The fix is the
tool name, nothing else; `software-developer.md` is the reference.

The `tools:` line is an allowlist: anything not named is withheld, including
MCP servers. Every agent file therefore also names both browsers,
`mcp__Claude_Browser` (the app's browser pane) and `mcp__claude-in-chrome`
(Bob's Chrome extension), so any agent can verify rendered output and read
web pages (Bob, 2026-10-05: every agent gets both). Every agent file also
names `mcp__linear-server`, so each agent posts progress and findings on its
own Linear issue (Bob, 2026-10-05: "YES PLEASE"). `controls-engineer` also
names `WebSearch` and `WebFetch`, so instrument and vendor research runs on the
role that knows the repo, in parallel copies when needed (Bob, 2026-10-05,
approving the recommendation from the instrument installation research). A new tool an agent needs
is added to its `tools:` line, never worked around. Agent definitions load at
session start, so a `tools:` change takes effect in the next session. A
subagent run in the background keeps only a reduced tool set; run an agent
in the foreground when it must use the browser.

## Approval gates (human only)

| Gate | Approved | Prepared by |
|---|---|---|
| 1 | Digitized P&ID data matches the drawing | process-engineer |
| 2 | Equipment layout | cad-design-engineer + mechanical-piping-engineer |
| 3 | Frame structural check and fork-lift case (TR-19, LAY-FORK-001) | cad-design-engineer, with saved `skidframe` runs (`harness/structural-models/`) as working aids (engineer performs the check) |
| 4 | Final model and drawing sign-off | engineering-manager |

## Where things are tracked

The goal is one place per kind of fact, so nothing has to be reconciled.

| Kind of thing | Lives in | Not in |
|---|---|---|
| Work to do | Linear: one issue per agent task, named to its agent, under the gate's project milestone (opened by the session that starts the task, body = the prompt verbatim; audited and closed by `project-manager`; Bob, 2026-10-07) | chat, TODO comments, notes files, GitHub issues |
| Question between agents, or to Bob | root `Agent-to-Agent Questions.md`; Bob's copy in `Agent-to-Bob Questions.md` | issues |
| Customer requirement not in writing | `<project>/01_Design_Basis/01_Customer_Requirements/holds.md` (HOLDs never block design, TR-23) | assumed content |
| Choice only the engineer can make | `<project>/00_Project_Admin/05_Decision_Log/DEC-####.md` | PR comments alone |
| What changed and why | commit messages and the day's PR body | `change-log.md` (generated at release) |
| Equipment concerns | `<project>/01_Design_Basis/06_Assumptions_Open_Items/equipment-concerns.md` (TR-02) | question entries |
| Design data | `<project>/03_Working_Design/PID/02_Tag_Lists/`, `<project>/00_Project_Admin/07_Project_Controls/Registers/`, `harness/design-rules/` (company-wide), `job/design-rules/` (every project in the job), `<project>/01_Design_Basis/05_Standards_Specifications/Design_Rules/` (this project) | issues, PR bodies, drawings |
| Durable design record | `<project>/00_Project_Admin/05_Decision_Log/`, `<project>/00_Project_Admin/07_Project_Controls/Registers/` | issue threads |

Rules for agents:

- **Work does not wait for an issue, and never waits on Linear** (Bob,
  2026-10-07). The delegating session opens the issue and acts on `NEXT:`
  (skill `agent-task`). The scrum master audits and closes issues; the named
  agent never opens or closes one. **Progress, findings and dead ends** go
  in the handoff, posted verbatim as a comment on the agent's own issue.
  Never a new issue.
- **Close-out audits the loops** (`harness/scripts/closeout.py`, step
  "Linear loops"; a warning, never a stop): today's handoffs under
  `<project>/_work/daily/` and `Agent-to-Agent Questions.md` entries dated today with no `CPM-nn`,
  today's Linear issues with no comment today, and `NEXT:` agents with no
  issue opened today. The three lists go under a "Linear loops" heading in
  the commit-body skeleton and into the PR body.
- **Every assumption points at its record**: `ASSUMPTION: ... (Q-nnnn)`,
  `(H5)`, `(EC-03)`. If none exists, add an `Agent-to-Agent Questions.md` entry.
- **Markdown logs are snapshots.** The project's logs (`<project>/00_Project_Admin/07_Project_Controls/`) are regenerated
  from the records at each release, never hand-edited between releases.
- Labels on a Linear issue: `role:<agent>` always, plus the gate's project
  milestone. `.github/labels.yml` still labels the PR.

## Work cycle

Model work runs in **three tiers** (CPME practice; Bob, chat, 2026-10-02), one script and one skill each:

| Tier | When | Script | Skill |
|---|---|---|---|
| 1. Iterate | every model build | `harness/scripts/model_iterate.py`: lists, STEP, interference, envelope, materials, pipe supports, GLB, list delta, into a new numbered folder under `<project>/03_Working_Design/CAD/Builds/` only | `model-iterate` |
| 2. Accept | Bob says he accepts, or would like to file, the fast edit as Rev <X> | `harness/scripts/model_accept.py`: preflight (lists written from the model, open items recorded as notes), full build, `model_file.py`, then the P&ID, LSD and PFD filed when changed, PRRs, pointers; no push | `model-accept` |
| 2a. File | Bob asks to file a build outside an acceptance | `harness/scripts/model_file.py`: the latest full build (or `--build <name>`), next letter, filed read-only under `<project>/06_Issued_Revisions/Models/<MODEL-ID>/<MODEL-ID>-rev<X>/`, `revisions.csv`, pointers, no push | `model-file` |
| 3. Close-out (optional) | only when Bob asks for a full check run: CI already runs the checks on every save | `harness/scripts/closeout.py`: all checks, list delta review, portal media and portal filing, Drive push and verify, commit body skeleton; no commit | `closeout` |

**One build series** (Bob, chat, 2026-11-12). All model editing is in `<project>/03_Working_Design/CAD/`: the source in
`01_Master_Assembly/`, and every build of it, fast or full, in `Builds/rev<X>/` as a new numbered folder
(`rev<X>-fast-<nnn>`, `rev<X>-full-<nnn>`; `<X>` the last filed revision, one counter per letter for both kinds).
No build overwrites another, and each has a row in `Builds/build-log.md` naming the checks that ran. A revision is
filed from a full build, and its `revisions.csv` rows name that build. `Exports/` holds only drawing previews.

1. Read this file, `harness/knowledge/Todd Requirements.md`, and the sources the task
   names.
2. Work in the shared working tree. Never switch branches or reset there;
   save only through `track.py save` (it commits in a separate worktree).
3. Make the bounded change; update affected registers in the same change.
   For the model: tier 1 after every change, tier 2 before anything is shown.
   **Acceptance is one scripted pass** (Bob, chat, 2026-10-15: "they should be run
   progamatically and deterministically. A P&ID revision should be part of the package."). It starts only when Bob
   says he accepts, or would like to file, the fast edit as Rev <X>. A request for part of it before that is that
   part only, as a fast edit: nothing is filed, and nobody asks whether to do the rest. Every fast build prints
   what is still open before the next letter, as notes. **At acceptance the model is the source of truth** (Bob,
   chat, 2026-10-16: "when accepted, all of the lists and other drawings get updated based on the model ... not a
   list of questions for me to answer prior to acceptance"): `model_accept.py` writes the model's changes into the
   `<project>/03_Working_Design/PID/02_Tag_Lists/` lists, records every open item as a note in the description, and files the model and its drawings in
   one go. Only a model or drawing that cannot be produced stops it, and that is the agent's to fix. There are no side sessions during an acceptance and no filing by hand.
4. Run `harness/checks/` relevant to the change. Report failures, skips and
   limitations. Then save it (`track.py save`, "Git" at the top); CI
   (`.github/workflows/checks.yml`) runs every check on that push. The handoff
   shows the `git status` check the global rules require.
5. **Hand off** in chat or `Agent-to-Agent Questions.md`: files changed, changed IDs, checks,
   blockers, exact next action, a **`CAPABILITY GAP:`** line, a **`NEXT:`**
   line, and the **TR compliance list** (each TR row the work touched and
   how it is met). The handoff is then posted verbatim, one tool call, as a
   comment on the agent's Linear issue (the `Linear issue: CPM-nn` in its
   prompt); if Linear is unavailable the handoff says
   `LINEAR: unavailable (<reason>)` and the work goes on (Bob, 2026-10-07).
   The `NEXT:` line (Bob, 2026-10-07) is exactly one line: the next agent
   and its deliverable, or `NEXT: none`; the delegating session acts on it
   (skill `agent-task`). Since Bob, 2026-10-08, only a MUST-FIX opens a new
   model revision; reviewer SHOULD / NOTE items wait in one backlog issue.
   The capability-gap line (Bob, 2026-10-05) is exactly one line: `none`,
   or the need the agent could not meet and what it did instead, for
   example "needed to view the rendered portal page; read the HTML
   instead". It names the need, not a tool: an agent sees only its own
   `tools:` line, so it does not speculate about tools beyond that line.
   The delegating session maps a gap to an existing tool with a one-line
   recommendation to Bob (`agent-task`); the **project-manager** rolls the
   day's gap lines into the PR body. Bob decides; the
   fix is a `tools:` line edit with his approval, effective next session.
6. **The pull request, when Bob asks for it, then Bob's merge, then
   everything else runs on its own** (Bob, 2026-10-07, verbatim: "THIS SHOULD BE 1 "GO" THEN MY
   MERGE. THE SYNC SHOULD BE AUTOMATED."). The day's work is already saved and
   backed up. The project-manager writes
   the PR body and names the PR to Bob in one message, with what follows his
   merge (sync, and the site publish when a portal revision is newer than the
   site holds). **Bob answers once.** His words are saved verbatim to
   `<project>/_work/daily/<date>-go.txt` and passed as `--bob-go`:
   `track.py daily-pr`, and after the merge `track.py after-merge` (sync,
   site publish). The
   **PR** from `.github/pull_request_template.md`, whose body lists
   every change of the day with its IDs and names each Linear issue it
   advances (`Relates to <ID>`; `Fixes <ID>` only when the whole issue is
   satisfied, since Linear closes it on merge); and the PR bound to the
   desktop app's PR monitor. The engineering-manager reviews it; Bob merges
   on GitHub, his only action after the go.
   **After the merge, on the merge event or Bob saying it is merged, with
   the day's go and no new ask:** `track.py sync-main` moves the shared
   checkout's `main` to `origin/main` with a mixed reset (no file written)
   after proving every local difference is already merged (the commit was
   made in a worktree, so without this the checkout reads stale rules and
   reports merged work as uncommitted; Bob, 2026-10-02; never `stash`,
   `reset --hard` or `checkout .` instead); then `publish_site.py` when the
   dry run named a newer revision (Bob, 2026-10-07: "IF THE ORIGINAL PR WAS
   APPROVED, THE CONTENT HAS ALREADY BEEN APPROVED AND IT SHOULD BE DONE").
   While a job has no presentation site
   (`site_repo` in `project.yaml` is `unknown`), `publish_site.py`
   then finds no site and stops, and nothing is published. The desktop
   app's permission classifier may refuse `publish_site.py` from an agent
   shell as a production deploy; the allow rule is added only as under
   "Tooling" below.

## Tooling

- CAD generation: `text-to-cad` plugin (build123d), **pinned version recorded
  in `<project>/00_Project_Admin/07_Project_Controls/tooling.md`**. Its CAD skill is for geometry, not FEA or
  certification.
- Python dependencies pinned in `harness/requirements.txt` (repo venv,
  `harness/tools/venv/`) and `harness/requirements-cadgen.txt` (cadgen venv,
  `harness/tools/venv-cadgen/`).
- No vendor STEP model may be committed without its source, revision and
  license recorded in `job/components/component-register.csv`.
- **Permission rules in `.claude/settings.json`** (Bob, 2026-10-07, verbatim:
  "I CAN NOT EDIT A JSON. YOU'RE APPROVED, PLEASE MAKE THE CHANGE, AS WELL
  AS, OPEN IT UP FOR FUTURE CHANGES WITH MY PERMISSION."). The desktop
  app's classifier blocks some commands even when the repo rules allow
  them (first case: `publish_site.py`, refused as a production deploy). When
  that happens the agent names the exact command and the one allow rule it
  needs, in chat; Bob approves in chat; the agent then adds that rule
  itself, no wider than the named command, cites Bob's words in the
  handoff and the commit body, and runs the command. Agents never add a
  rule Bob did not approve for that command, and never add one that
  touches `main`, force-pushes or merges (the `deny` list stays).
