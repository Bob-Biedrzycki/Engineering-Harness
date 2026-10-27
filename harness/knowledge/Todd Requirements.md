# Todd Requirements — binding on every agent, every task

**Rule (Bob, chat, 2026-09-24, verbatim):** "All of Todd's asks must be met
and satisfied by ALL AGENTS, ALL OF THE TIME. INCLUDING HOW GIT IS
IMPLIMENTED."

**Owner:** Bob. **Source of the asks:** Todd Harris (CPME President), by
chat 2026-09-10..24, meeting 2026-09-18 and emails 2026-09-23 / 2026-09-24. The transcripts are held by Bob,
outside the repo. Todd's direction for a job is recorded in that job's `job/knowledge/Todd Direction.md`, and how each row is met on
a job, where it needs job detail, in the job's notes, `job/knowledge/Todd Requirements - job notes.md` (Bob, chat, 2026-10-27).

**Terms (Bob, chat, 2026-10-26; TR-09):** a **job** is the product line and its one repo; a **project** is one order in the job, with its own folder `job/Project-<Project Number>-<Type>-<Top Level
Version>/`, written `<project>` below (the active project, `job/JOB.md`).

**Scope of this register (Bob, chat, 2026-10-26):** only the asks that bear on the design of a CPME skid are kept, and the rows were
renumbered TR-01..TR-26 and C-01..C-08 on that date. "Irrelevant TR stuff needs to be entirely excluded so that there is
no chance for confusion."

## How agents use this register

1. **Read it at the start of every task**, after `CLAUDE.md`.
2. **Comply with every row that touches the task.** No row is optional and
   none is waived by an agent.
3. **Cite by ID** (`TR-08`) in rules, reviews, commit messages and handoffs.
4. **Report compliance in every handoff:** the TR rows the work touched and
   how each is met. Any row not met is stated as `NOT MET` with the reason.
5. **No exceptions (Bob, chat, 2026-09-24, verbatim: "moving forward there
   can be NO EXCEPTIONS.").** Work that fails a row the agent can meet is
   fixed before hand-off, never handed off with a `NOT MET`. `NOT MET` is only
   for a row blocked on Bob or an outside party.
6. **Conflicts:** where another instruction in this repo, including
   `CLAUDE.md`, a design rule or an agent file, conflicts with a TR row, the
   TR row governs (Bob, 2026-09-24). Record the conflict in the conflicts
   table below and fix the other instruction.
7. **Limits that still hold:** never invent data (`CLAUDE.md` hard rule 1),
   the engineer decides at gates (rule 7), and nothing is merged, released,
   sent externally or deleted without authorization (rule 9). Todd's asks do
   not relax these. Rows that need GitHub admin or a person outside the repo
   are marked **Bob action**.

## Register

### Workflow and priority

| ID | Todd's ask | Source | How every agent meets it |
|---|---|---|---|
| TR-01 | Walk before running. The workflow is four steps in order: well-documented P&ID; P&ID revision and change tracking; equipment (forced, TR-02); skid layout, pipe routing and takeoffs. | email 2026-09-24 | Work the earliest step whose output is missing or stale. Do not start a later step on an input the earlier step has not produced. |
| TR-02 | Skip equipment sizing and design for now. Force the specified equipment. Agents flag concerns in a separate file, accept them, and move on. | email 2026-09-24 | Specified equipment in `<project>/03_Working_Design/PID/02_Tag_Lists/equipment-list.csv` is fixed input. Do not resize, re-select or question it. Write each concern once in `<project>/01_Design_Basis/06_Assumptions_Open_Items/equipment-concerns.md` and continue. No question for an equipment concern. Where a project DEC brings sizing in, the agents size and Bob approves the selections; once approved, they are fixed input like any other (the job's notes, `job/knowledge/Todd Requirements - job notes.md`). |
| TR-03 | Standardize the information passed between steps, so a revision means changing one input, running one step and getting the output. | email 2026-09-24 | Use the step table in `CLAUDE.md` ("Workflow steps and hand-off"). Read only the named inputs, write only the named outputs, and make every output regenerable by script from its inputs. Never hand-edit an output. |
| TR-04 | Focus on piping configuration and skid layout. Design is not building an instrument BOM. | email 2026-09-23; Bob 2026-09-24 | A spec question is pursued only when it changes sizing (where a project DEC brings it in), an envelope, a connection or a clearance (`CLAUDE.md` "Current focus"). Otherwise record `unknown` and keep going. |
| TR-05 | Do not ask a million questions. Do not ask Todd what the quote, spec or drawings already answer. | email 2026-09-23, 2026-09-24; meeting 2026-09-18 | Answer from the documents first. A question to Bob or Todd is one direct sentence, says what it blocks, and is asked only when no document answers it. Flow rate, duty and pump head come from the quote or the customer intake (`<project>/01_Design_Basis/01_Customer_Requirements/customer-intake.md`). |

### Drawings and revisions

| ID | Todd's ask | Source | How every agent meets it |
|---|---|---|---|
| TR-06 | The P&ID master is a native DWG with functional layers. The PDF is exported from the DWG. The drawing carries the CPME title block. | chat 2026-09-14, 2026-09-15 | Every drawing is produced as a native DWG plus a PDF exported from it, with the CPME sheet format (`harness/cad-lib/cpme_titleblock.py`). |
| TR-07 | Revise drawings to drafting practice: a revision block with notes, the revision in the file name, and clouds around new or modified items. | email 2026-09-24 | Each revision adds a row to the revision block with a note of what changed. Changed items are clouded on the sheet. Files are named per `CLAUDE.md` "Git and drawing revisions". |
| TR-08 | Keep an artifact for every revision. It must be possible to open a PDF of any revision. The tool "shouldn't be updating the same file." | chat 2026-09-24 | Every drawing handed to Bob or anyone else is filed by `harness/cad-lib/revfile.py` as a new PDF, DWG and DXF that is never modified or deleted afterwards. No other path exists. The rules are in `CLAUDE.md` "Git and drawing revisions". **Designs too** (Bob, chat, 2026-09-24: "YOU ARE NO LONGER TO OVERWRITE DESIGNS. THEY MUST BE LABELED AS REVISIONS."): every 3D model output and takeoff handed off is filed as the next revision under `<project>/06_Issued_Revisions/Models/<MODEL-ID>/` and never overwritten (`CLAUDE.md` "Designs"). |

### Git and tracking

| ID | Todd's ask | Source | How every agent meets it |
|---|---|---|---|
| TR-09 | One GitHub repo per job; each project is a folder in it. | chat 2026-09-17 ("You should have it setup a github repo for each project"); intent clarified by Bob, chat, 2026-10-26, verbatim: "the intent of his message was that there should be one repo per Job, not per project at the current time." | A job is the product line and its repo (the job's repo is named in `job/JOB.md`). Each project in the job is its own folder, `job/Project-<Project Number>-<Type>-<Top Level Version>/`, made from `harness/templates/project-folder/` by `harness/scripts/project_new.py` (Bob, chat, 2026-10-26). Another job gets its own repo. Large files stay part of the same project record through the Google Drive store (one store for the whole job, `job/drive-store.yaml`, shared by the component library and every project; Bob, chat, 2026-10-26; pointers in git). |
| TR-10 | Use the company GitHub account, not a personal one. Yen and Lee set it up. | chat 2026-09-18 | Each job's repo is under Bob's account by Bob's direction (the repo is named in `job/JOB.md`). `harness/scripts/track.py` writes as `Bob-Biedrzycki`, the one writer (Bob, 2026-10-07; `CLAUDE.md` "GitHub sign-in"), and refuses to write as any other account. Agents never handle tokens and never push to any other account or repo. Bob merges. |
| TR-11 | Commit work with documentation on every commit, so changes can be compared (including MD files), reverted and tagged. | meeting 2026-09-18 | Commit message format and tagging in `CLAUDE.md` "Git and drawing revisions". Commits are made only when Bob says, by explicit paths. |
| TR-12 | Track the project with a scrum master agent working in GitHub Projects or Azure DevOps (Todd's profile, chat 2026-09-18). | meeting and chat 2026-09-18 | `project-manager` runs as the scrum master per its agent file and tracks agent work in **Linear**, which is linked to the GitHub repo (Bob, 2026-09-28; C-06): one Linear issue per agent task, named to its agent (`[<agent>]` title prefix, `role:<agent>` label), no cap, gates as project milestones per Linear's recommended structure. GitHub carries the code, CI, drawing tags and the daily PR. Pull requests are one per day, never one per file (Bob, 2026-09-24). |

### Deliverables

| ID | Todd's ask | Source | How every agent meets it |
|---|---|---|---|
| TR-13 | On an order, CPME is ready to place orders for every component and has buildable plans. | chat 2026-09-10 | Deliverables are judged by that test: complete BOM, cut lists and drawings a shop can build from. |
| TR-14 | All tubing for the frame and process piping is ordered laser cut to length (OSH Cut, instant pricing), so the welder only assembles. | chat 2026-09-10 | Cut lists give every piece as a separate line with exact cut length, size (tube OD or pipe NPS and schedule), wall, grade and quantity, in a form that can be uploaded for laser cutting. |
| TR-15 | A library of mechanical parts: tubing with tri-clamp ends, tri-clamps, tees, elbows, pumps, tanks. | chat 2026-09-10 | The job library `job/components/` holds reusable blocks for each, shared by every project in the job, with the cut sheet, STEP and installation practice and where each came from recorded in `component-register.csv` (Bob, chat, 2026-10-26), including the pipe, flange and other parts the job's product uses. |
| TR-16 | Two BOMs: a major-components BOM from the P&ID (valves, pump, HX, tanks) and a full BOM from the 3D design. | meeting 2026-09-18 | Never derive fitting or clamp counts from the P&ID. They come from the model. |
| TR-17 | Vendor preference: Alfa Laval pumps, IFM Efector instruments. Tubing and clamps are commodity items. Never Alibaba. | chat 2026-09-10 | Applies to every selection the agents make (the job's notes, `job/knowledge/Todd Requirements - job notes.md`). Specified equipment governs where it is specified (TR-02). Never propose an Alibaba source. |

### Layout and piping

| ID | Todd's ask | Source | How every agent meets it |
|---|---|---|---|
| TR-18 | As compact as possible. The skid ships in one piece in a semi with no site assembly. | chat 2026-09-11; trailer type Bob 2026-09-24 | Inside an **enclosed 53 ft swing-door dry van** (Bob 2026-09-24). Every layout option fits **170 in L x 60 in W x 106 in H** as shipped, is as compact as possible within that, and states its footprint, with height measured from the bottom of the base to the highest point on the skid. The limit is the rear door opening, 98 in W x 108 in H, less 2 in of loading clearance. Values and sources are in `<project>/01_Design_Basis/05_Standards_Specifications/Design_Rules/layout.yaml` `shipping_envelope`. |
| TR-19 | No lift points. Long forks go under the skid. | meeting 2026-09-18 | The frame provides clear fork access along its length, with the forks under the heaviest equipment (LAY-FORK-001). |
| TR-20 | Err on the side of removable joints. | meeting 2026-09-18 | On hygienic lines (PIPE-SVC-001), do not reduce clamp count to save cost. On other service classes, provide flanged or union breaks so every serviceable component can be removed (the job's notes, `job/knowledge/Todd Requirements - job notes.md`). |
| TR-21 | Instrument taps are a tee plus a welded tri-clamp ferrule. Off-the-shelf parts are preferred where they exist. No all-clamp spool piece. | meeting 2026-09-18 | On hygienic lines (PIPE-SVC-001), model and take off taps that way. On other service classes, taps follow that class's practice (threaded or socket-weld boss) per its rules (the job's notes, `job/knowledge/Todd Requirements - job notes.md`). |
| TR-22 | Every process connection is tri-clamp. A threaded port needs a matched thread-to-tri-clamp adapter, analyzed case by case (Bob). | email 2026-09-23; Bob 2026-09-24 | Applies to hygienic lines (PIPE-SVC-001). Other service classes take the joints PIPE-SVC-001 sets for them. A threaded port on a hygienic line is analyzed case by case (`CLAUDE.md` "Current focus"). |
| TR-23 | Customer and plant standards are the customer's. The skid is a black box judged by its supply and return connections. | chat 2026-09-13, 2026-09-21 | Customer and plant standards are HOLDs until received in writing (`<project>/01_Design_Basis/01_Customer_Requirements/holds.md`); HOLDs stay tracked but never block design work (Bob's ruling, 2026-09-24: "DISREGARD THE CUSTOMER HOLD FOR NOW"). Do not design to assumed customer content. |
| TR-24 | End game: 3D print the skid as separate pipes, elbows and tees that snap together where the welds are, at 1 ft = 1 in. | chat 2026-09-12 | Model piping as separate bodies split at every weld location, each carrying its spool and weld ID. |
| TR-25 | Standardize: the same detail on every repeated item so the shop can jig it, and one header design across as many skid variations as possible. | meeting 2026-09-18 | Prefer repeated, parametric details (equipment stations, nozzle and tap details; the job's notes, `job/knowledge/Todd Requirements - job notes.md`) over one-off ones. Say so when a detail is one-off. |
| TR-26 | Do not develop the configurator. | meeting 2026-09-18 | Out of scope for every agent. |

## Conflicts resolved in Todd's favor

| # | Other instruction | TR | Resolution |
|---|---|---|---|
| C-01 | `CLAUDE.md` naming: stable file names, revision only in the title block and register. | TR-07, TR-08 | Source files keep stable names. Every issued drawing is also saved with its revision in the file name. `CLAUDE.md` rewritten. |
| C-02 | Drawing binaries referenced by sha256 and not committed. | TR-08, TR-11 | Issued drawing revisions are committed under `<project>/06_Issued_Revisions/Drawings/`, with a sha256 manifest (`revisions.csv`). |
| C-03 | Proposed skid-wide thread ban SAN-THREAD-001. | TR-22 | Not entered as a blanket rule. Case by case on hygienic lines (`CLAUDE.md` "Current focus"); other service classes per PIPE-SVC-001. |
| C-04 | Equipment concerns raised to Bob as questions, such as re-selection proposals. | TR-02, TR-05 | Concerns go to `<project>/01_Design_Basis/06_Assumptions_Open_Items/equipment-concerns.md`, are accepted, and work continues. |
| C-05 | `CLAUDE.md` work cycle: one issue = one branch = one PR per change. | TR-11, TR-12 | **Resolved by Bob, 2026-09-24:** scrum-master tracking, one PR per day. Commits stay documented per TR-11; a day may hold several. |
| C-06 | TR-12 names GitHub Projects or Azure DevOps; Bob moves agent task tracking to Linear. | TR-12 | **Resolved by Bob, chat, 2026-09-28:** Linear "lives alongside of GitHub, and Linear uses the GitHub Repo"; it is primarily "an agent management tool for agentic tasks or issues/tasks that can be completed by agents", part of "a migration to a more cloud based workflow". Issues are named to the appropriate agent, no cap, structure per Linear's guidance. The scrum master role, one-per-day PRs and TR-11 commits are unchanged. |
| C-07 | "The engineer assigns revision letters" (`CLAUDE.md`, Bob 2026-09-23) vs one artifact per revision. | TR-07, TR-08 | **Resolved by Bob, chat, 2026-09-24, verbatim:** "Revision letters should not be assigned by me, they should simply be sequential." Every hand-off takes the next letter; no draft numbering. `CLAUDE.md` updated. |
| C-08 | TR-09 allows one repo per job; a presentation site needs a second repo to publish to. | TR-09 | **Resolved by Bob, chat, 2026-10-02, verbatim:** "MAKE THE RECORDING, THERE IS A VALID REASON FOR HANDLING IT THIS WAY." and "THE PAGE AND REPO ARE SIMPLY AN INVESTIGATION INTO HOW IT COULD BE DONE IN THE FUTURE AND WOULD REQUIRE MORE IN DEPTH DEVELOPMENT." A site repo (`site_repo` in `project.yaml`) is a publishing target, not a second job repo: it holds only generated copies of filed portal revisions (pages, assets, the shared data store and web GLBs), never a source, record or decision. The design repo stays the job (TR-09). Each publish is a copy of a filed revision, made and pushed on Bob's go at close-out. Bob tells Todd. |
