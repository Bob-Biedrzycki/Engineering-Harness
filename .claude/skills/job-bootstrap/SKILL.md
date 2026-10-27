---
name: job-bootstrap
description: Start a new CPME job or a new project. A new job is its own repo (TR-09) made by harness/scripts/job_new.py from the Engineering Harness master (the harness copied unchanged, plus job/JOB.md, drive-store, carryover terms, components, design-rules and knowledge stubs, question files); a new project is a numbered folder job/Project-<Project Number>-<Type>-<Top Level Version>/ made by harness/scripts/project_new.py from the project template, with its project.yaml, empty lists and registers, design-rule scope files, Drive store, Linear project and gate milestones, and job/JOB.md's current-project paragraph. Harness updates come from the master through harness/scripts/harness_sync.py. Use when Bob starts a new job or project, or wants to restart a project's design from scratch.
---

# Job bootstrap

A **job** is the product line and its repo (named in its `job/JOB.md`). A
**project** is one order in it, folder `job/Project-<nnnn-nn>-<TYPE>-<nnn>/`
(Project Number, Type, Top Level Version; Bob, chat, 2026-10-26). The Project
Number in the folder name is the project code, e.g. 0000-00; `project_number`
in project.yaml is CPME's short order number, e.g. 0000-0. IDs use the
folder name without `Project-`: `0000-00-TST-001-PID-001`,
`0000-00-TST-001-MODEL`. `harness/` (with `.claude/agents`, `.claude/skills`,
`CLAUDE.md` and `.github/`) is what every CPME job reuses unchanged; `job/`
holds the job's projects plus `job/JOB.md`, `job/knowledge/`,
`job/design-rules/` and `job/components/` for the whole job (CPME practice,
TR-09). A new job is a new repo with the same harness; a new project is a
new folder under its job's `job/`. Nothing from another job or project is
copied except as a reference the new one cites. Every project folder is
explained in `harness/templates/project-folder/README_Project_Guide.md`.

## The master and harness updates

- The master copy of the harness is `C:\Users\Bob\Documents\Engineering Harness`
  (Bob, 2026-10-27). `harness/harness-manifest.txt` lists the harness-owned
  paths; everything else (`job/**`, the question files, `README.md`,
  `.claude/launch.json`, `.claude/settings.local.json`) is job-owned.
- **Harness fixes are made in the master**, never in a job repo, then pulled
  into each job:

  ```powershell
  .\harness\tools\venv\Scripts\python.exe harness\scripts\harness_sync.py check <job repo>
  .\harness\tools\venv\Scripts\python.exe harness\scripts\harness_sync.py pull <job repo>
  ```

  `check` lists every harness-owned file that differs from the master
  (sha256); `pull` copies the master's harness-owned files into the job and
  never touches a job-owned file. There is no `push`.

## 1. Bob's items (ask once, in one message)

- New job only: the job name and the repo (`<owner>/<name>`). Bob creates the
  GitHub repo and signs `gh` in himself; agents never handle tokens. `origin`
  is set to what he names, nothing else.
- Project number, type and top level version (the folder name), CPME's short
  project number (`project_number`), customer, and where the P&ID files are,
  if any.
- Drive folder for large files (he creates the rclone remote with his own
  sign-in, once per machine).
- Anything known about the shipping envelope. The fork lane is not asked:
  the forks go directly under the heaviest equipment (LAY-FORK-001; Bob,
  chat, 2026-10-26).

## 2. A new job

From the master or any job repo:

```powershell
.\harness\tools\venv\Scripts\python.exe harness\scripts\job_new.py <folder> --name "<Job name>" --repo <owner/name>
```

It copies the harness-owned files from the master and writes the job-owned
stubs: `job/JOB.md` (what the job is, its repo, Drive store, Linear project,
current project, where its design framework and review addendum are),
`job/drive-store.yaml` (folder `unknown` until Bob gives it),
`job/carryover-terms.txt` (the earlier jobs' product terms the guard test
must not find in this repo), `job/components/` (README and register header),
empty `job/design-rules/` and `job/knowledge/`, the empty
`Agent-to-Agent Questions.md` and `Agent-to-Bob Questions.md`, and a README.
Change no harness file. Then:

- Fill `job/JOB.md` and start the job's knowledge: its design framework
  (what a unit holds, the intake questions, the design sequence, and the
  section "Layout and piping specifics for skid-layout and pipe-route"), its
  review addendum (`job/knowledge/Review Addendum.md`), and
  `job/knowledge/Todd Direction.md` (empty).
- `job/design-rules/`: the README and no YAML until Bob designates a rule
  job level (`design-rule-add`); the job's rules for each service class go in
  `job/design-rules/piping.yaml` `job_rules_by_class`.
- `job/drive-store.yaml` with Bob's folder (one store for the whole job; a new
  project in an existing job needs nothing), then `drive_store.py pointers`
  to write the `.gitignore` block.
- Rebuild the venvs from `harness/requirements*.txt` into `harness/tools/`.
- Then make the first project (section 3). Until it exists, checks report
  "no project yet" and exit 0.

## 3. A new project

From the job repo root:

```powershell
.\harness\tools\venv\Scripts\python.exe harness\scripts\project_new.py Project-<Project Number>-<Type>-<Top Level Version>
```

It copies `harness/templates/project-folder/` (the full numbered tree, every
folder from day one) and writes `project.yaml` with the IDs it can derive
(`project_id`, `project_code`, `model_id` = `<project_id>-MODEL`, `pid_doc_id` =
`<project_id>-PID-001`) and every other key `unknown`. It never overwrites
an existing folder. When `job/` then holds more than one project, name the
active one in `job/active-project.txt` (or `CPME_PROJECT`).

- Fill `<project>/project.yaml` (`<project>` is the new `job/Project-*` folder):
  project number, customer, location, skid name/title/description, design repo,
  site repo, Linear project, Drive remote. `repo_paths.py` reads it. Every
  harness script takes the project's IDs from it.
- Lists in `<project>/03_Working_Design/PID/02_Tag_Lists/` with headers only
  (line, equipment, valve, instrument, tie-in, motor-load). Empty
  `pid-questions.md` and `equipment-concerns.md` in
  `<project>/01_Design_Basis/06_Assumptions_Open_Items/`, and, only if the
  project has a tank, `tank-modifications.md` in
  `<project>/02_Engineering/05_Tank_Sizing/`.
- Registers in `<project>/00_Project_Admin/07_Project_Controls/Registers/`
  with headers only: documents, sources, interfaces, verification,
  standards-register; `<project>/03_Working_Design/CAD/05_Purchased_Components/component-register.csv`
  header (project-only parts).
- `<project>/01_Design_Basis/05_Standards_Specifications/Design_Rules/*.yaml`:
  one entry per harness or job-level rule in scope, with `rule_ref`,
  `applies_to: unknown` and the project values `unknown` until the P&ID and
  quote give them. Seed `piping.yaml` (PIPE-SVC-001 scope: each class's
  project rules, `unknown` until the line list gives each line's
  `service_class`) and a scope file for each of the job's product rule files.
  The shipping envelope and the fork lane's member tags (under the heaviest
  equipment) go in `layout.yaml`. A new rule or value field goes through
  `design-rule-add`.
- Empty `<project>/01_Design_Basis/01_Customer_Requirements/holds.md` and
  `customer-intake.md`, `<project>/00_Project_Admin/02_Schedule_Milestones/schedule.md`,
  and in `<project>/00_Project_Admin/07_Project_Controls/`: `tooling.md`
  (record the pinned text-to-cad version), `question-log.md`, `change-log.md`,
  `documents-to-obtain.md`.
- Run `harness/checks/project_layout.py` to confirm no folder is missing.

## 4. job/JOB.md and Linear

- Update `job/JOB.md`'s current-project paragraph (project folder, model ID,
  P&ID ID, any DEC that brings sizing in). CLAUDE.md and every other harness
  file stay as they are.
- Todd Requirements (`harness/knowledge/Todd Requirements.md`) apply
  unchanged; the job's notes on them go in
  `job/knowledge/Todd Requirements - job notes.md`. The job's narrative
  (`job/knowledge/Todd Direction.md`) starts empty on a new job and carries
  over to a new project in the same job.
- Linear: one project per CPME project, milestones Gate 1..4, labels `role:<agent>`
  (check they exist before creating).

## 5. Then

The intake questions come first (the job's design framework in
`job/knowledge/`; sizing only where a project DEC allows it), then
`pid-digitize`. Walk before running (TR-01): don't start layout
before the lists exist.

## Hand-off

Repo, job stubs or project folder created, files with headers, rules in scope with `unknown`
values, Bob items still open, TR rows (TR-01, TR-09, TR-12), CAPABILITY GAP,
`NEXT: process-engineer intake questions first (the job's design framework;
sizing only where a DEC allows it), then pid-digitize`.
