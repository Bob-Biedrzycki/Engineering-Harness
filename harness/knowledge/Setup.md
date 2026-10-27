# Setup: AI-Assisted Mechanical Design Environment for CPME Skids

How a CPME skid job is set up and run in this harness: mechanical skid design only, by a seasoned mechanical
engineer and his team, with Claude Code and the text-to-cad plugin drafting and checking. What the current job
builds, and its current project, are in `job/JOB.md`; the job's product knowledge is in `job/knowledge/`.

---

## Scope and Assumptions

* **In scope:** Mechanical skid design only. That covers layout, piping, frame, fabrication deliverables, and design verification.
* **Out of scope:** PLC/SCADA design (`CLAUDE.md` "Scope").
* **Inputs:** the customer intake and the P&ID. Equipment is the specified equipment (TR-02), or, where a project DEC brings sizing in (named in `job/JOB.md`), the selections Bob approves.
* **CAD capability:** the text-to-cad skill has been pilot tested and produced very good results.
* **Authority:** The engineer (Bob) is the approval authority for every deliverable. The AI drafts and checks. It does not sign off.

---

## Core Concept

Claude Code is not a CAD package. It is an agent that works inside a file repository. The "IDE" is a Git repository that holds the project data, design rules, component models, CAD source, and automated checks. The agent works in that repository. The engineer reviews and approves through pull requests.

Claude Code reads its instructions from `CLAUDE.md` at the repository root. Keep all agent instructions in that one file; skills in `.claude/skills/` hold the how.

---

## text-to-cad Review Summary

**What it is:** An MIT-licensed library of agent skills for CAD work, installable as a Claude Code plugin.

**Relevant skills:**

|Skill|What it does|Use on a skid project|
|-|-|-|
|CAD|Writes build123d Python source and generates STEP parts and assemblies. Supports named mating datums and joints. Includes inspection (measure, align, diff) and mandatory snapshot review.|Frame, baseplates, supports, piping assembly, full skid assembly|
|CAD Viewer|Local browser preview of STEP and related files|Design reviews and 3D walkthroughs|
|step.parts|Finds off-the-shelf STEP parts (screws, bearings, motors, connectors)|General hardware only; it has no sanitary fitting, flange or process valve library|
|DXF|Creates 2D profiles, gaskets, and cut layouts|Laser-cut parts: gussets, baseplates, drip pans, kickplates|
|SendCutSend|Checks DXF and STEP files before upload to that service|Optional, if that fabrication service is used|

**Limits to plan around:**

* The skill states it is not for engineering certification or FEA conclusions. Structural checks and sign-off stay with the engineer.
* It has no fitting, valve or process-component library. Vendor STEP models must be supplied (skill `component-add`).
* The project releases frequently. Pin one version for production work and upgrade on purpose (`<project>/00_Project_Admin/07_Project_Controls/tooling.md`).

---

## Plan

The central task is turning the customer intake and the P&ID into a 3D skid that matches the P&ID exactly, meets the design rules for each line's service class (PIPE-SVC-001), and has a clear record showing both. The order is the job's design framework (named in `job/JOB.md`, kept in `job/knowledge/`; TR-01).

### Phase 0 – Environment Setup (before project start)

1. Settle data-retention terms (enterprise or zero-retention plans) before any customer specs or drawings enter Claude Code.
2. One GitHub repo per job (TR-09) with `harness/` (company-wide) and `job/` (this job, one folder per project); the map is in `CLAUDE.md` "Repository map". A new project folder is made by `harness/scripts/project_new.py` (skill `job-bootstrap`).
3. `CLAUDE.md` carries scope, units and naming, and the hard rules: never invent part numbers or dimensions; always cite the design rule behind a decision; flag every assumption; trace every component to a P&ID tag.
4. Install text-to-cad at a pinned version.

### Phase 1 – Make the Inputs Machine-Readable

5. **Customer intake and sizing.** The job's intake questions are answered in the project's `customer-intake.md`; where a project DEC brings sizing in, the sizing record goes to Bob for approval.
6. **Digitize the P&ID into data** (skill `pid-digitize`): line list (line number, size, service class, from, to, material), equipment, valve, instrument, tie-in and motor-load lists. The engineer confirms they match the drawing before any modeling starts. **(Gate 1)**
7. **Collect vendor STEP models** for every selected item: major equipment, pumps, tanks or vessels, valves, instruments and fittings. Record each model's source, revision and licence in the component library.
8. **Layout constraints in YAML:** shipping envelope, operator access, maintenance pull space (pump motors, equipment internals that are pulled for service), customer tie-in points, fork access.
9. **Design rules in YAML** at three levels (harness, job, project; `harness/design-rules/README.md`): piping by service class, sanitary rules for hygienic lines, the job's product rules for its other service classes (`job/design-rules/`), structural and layout. The automated checks test against these rules.

### Phase 2 – Layout

10. The agent generates two or three layout options, placing equipment on a parametric frame (skill `skid-layout`).
11. The engineer selects one based on access, drainability and footprint, and approves it before any piping is routed. Layout is the most expensive thing to change later. **(Gate 2)**

### Phase 3 – Piping and Frame

12. Route the piping line by line from the line list (skill `pipe-route`). Tag every spool with its P&ID line number.
13. Detail the frame: members, baseplates, gussets, drip pans and support locations.
14. The engineer performs the structural check and the fork-lift case (TR-19, LAY-FORK-001). The tool does not certify structures. **(Gate 3)**

### Phase 4 – Automated Verification (runs on every revision)

15. **P&ID-to-model consistency:** every P&ID tag appears in the model, every model component traces back to a P&ID tag, every line connects the correct from/to points.
16. **Piping checks by service class:** slope, dead legs and drains on hygienic lines; the job's class rules on its other lines; tested against the YAML rules.
17. **Interference and envelope checks** between piping, frame, equipment and insulation.
18. Checks run on each pull request and report; they never block design progress (`CLAUDE.md` "Adding an instrument or component"). Bob reads the findings and decides.

### Phase 5 – Fabrication Deliverables

19. The agent generates the BOM, cut lists, spool lists and DXFs for laser-cut parts (TR-13, TR-14, TR-16).
20. GA drawings, isometrics and weld maps come from the model; designers review and finish them rather than draw them from scratch.
21. Draft the ITP, weld log template and turnover package index from `lists.md`, filled in with this project's tags.

### Phase 6 – Review and Release

22. Hold a formal design review with a 3D walkthrough. The engineer signs off the model and drawings. **(Gate 4)**
23. Every handed-off drawing and model is a filed revision that is never overwritten (TR-08), so the Git history of the model, rules and data is the design record.
24. After FAT, record any field fit-up issues as new design rules (asking Bob the level first, hard rule 11). Each project makes the next one better.

---

## Engineer Approval Gates

|Gate|What is approved|Phase|
|-|-|-|
|1|Digitized P&ID data matches the drawing|Phase 1|
|2|Equipment layout|Phase 2|
|3|Frame structural check and fork-lift case (TR-19, LAY-FORK-001)|Phase 3|
|4|Final model and drawing sign-off|Phase 6|

Between gates, the agent drafts and the automated checks verify. At the gates, the engineer decides.

---

## Governance

* **Pull requests are the review record.** One per day (`CLAUDE.md` "Work cycle"). The engineer approves every change to rules, component data, CAD source and project deliverables.
* **STEP is derived output.** Edit the build123d source, then regenerate. Never hand-edit generated STEP files in the repository.
* **Pin tool versions** (text-to-cad, agent version, Python dependencies) for each project, and record them in the project's `tooling.md`.
* **Customer data stays under agreed retention terms.** No customer drawings or specs go into tools without those terms in place.

---

## Related Files

* **Team.md** – Roles and responsibilities across the project lifecycle
* **documents.md** – Internal record keeping and project documentation
* **lists.md** – Schedules and lists used in skid projects (source for the ITP and turnover index in Phase 5)
* **Design Standards.md** – Codes and standards the rules summarize
* **Approval Ladder.md** – What needs Bob's word
* **Setup.md** – This file
