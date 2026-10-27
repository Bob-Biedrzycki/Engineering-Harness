# Design rules: harness, job and project

Design rules have three levels (Bob, chat, 2026-10-26). A **job** is
the product line and its repo; a **project** is one order in it.

| Level | File set | Holds | Example |
|---|---|---|---|
| 1. Harness | `harness/design-rules/*.yaml` | The rule and its value where the basis is a standard or CPME practice, so it applies to any CPME skid | PIPE-SVC-001 service classes; SAN-SLOPE-001 min slope 1/8 in/ft on hygienic lines; PIPE-CV-001 10 D |
| 2. Job | `job/design-rules/*.yaml` | Rules and values that hold for every project in the job | the job's product rules and its rules for each service class (`job/design-rules/README.md`) |
| 3. Project | `<project>/01_Design_Basis/05_Standards_Specifications/Design_Rules/*.yaml` | Where each rule applies on one project, and every value that depends on that project's lines, tags, equipment, customer HOLDs or DEC records | each line's service class; SAN-PIPE-001 governing code (B31.1, B31.9 or B31.3); where each job rule applies; the shipping envelope |

A rule keeps one id at every level. The harness entry carries the rule and value.
A job or project entry carries `rule_ref` to the level above it, plus its own scope
and values; a lower level narrows a higher one and never contradicts it. Cite rules
by id (e.g. SAN-DL-001), not by file. Which rules apply to a line is set by its
service class (PIPE-SVC-001): the class's company-wide rules here, plus the job's rules
for that class (`job/design-rules/piping.yaml`). The checks read harness, then job, then project.
`<project>` is the active project folder, `job/Project-<Project Number>-<Type>-<Top Level Version>/`
(`repo_paths.PROJECT`).

## Adding or changing a rule: ask Bob first

Bob, 2026-09-25: "In the future when a new rule is to be added to either i would
like to be asked which designation it belongs in."

- Before a new rule, or a new value field on an existing rule, is written at any
  level, the agent asks Bob whether it is **harness** (company-wide), **job** (all
  projects in this job) or **project** (this project only). The agent gives a
  recommendation in one line, with the reason, and waits for the answer.
- In a live session the question goes to Bob in chat. A subagent without chat
  puts it in root `Agent-to-Agent Questions.md` with a copy in `Agent-to-Bob Questions.md`, and does not write the rule
  until the answer is recorded.
- Moving an existing entry from one level to another is also asked first.
- Bob's answer is cited in the entry's basis (e.g. "designation: harness, Bob,
  chat, <date>").
- Rule owners: mechanical-piping-engineer (`piping.yaml`, `sanitary.yaml`, and the
  job's piping and product rules), electrical-engineer (`electrical-interface.yaml`),
  controls-engineer (`instrument-mounting.yaml`), the project engineer
  (`layout.yaml`, `structural.yaml`, `drafting.yaml`). Bob approves.

## Designations of the rules in this repo

| Rule | Level | Basis of the designation |
|---|---|---|
| PIPE-SVC-001 service classes (`piping.yaml`) | harness; each line's class and each class's scope per project | Bob, chat, 2026-10-26: "The rules need to be specific to the function." Product rules for each class moved to the job level (Bob, chat, 2026-10-27) |
| SAN-SLOPE-001, SAN-DL-001, SAN-DL-002, SAN-DRAIN-001, SAN-RA-001, SAN-WELD-001, SAN-PP-001, SAN-FRAME-001, SAN-ACC-001 (`sanitary.yaml`) | harness (rule and value); line scope, drain points and each instrument's values per project | CPME practice |
| SAN-MAT-001 tube spec and walls, incl. 3.0 in, and `drain_piping` | harness; product-contact grade and gasket selection per project | CPME practice |
| SAN-PIPE-001 governing code | the rule harness; the code (B31.1, B31.9 or B31.3) a project value, `unknown` until the customer or AHJ sets it | Bob, chat, 2026-10-26 |
| PIPE-CV-001 pump-discharge check valve, 10 D (`layout.yaml`) | harness; scope per project | CPME practice |
| LAY-FORK-001 forks under the heaviest equipment (`layout.yaml`) | harness; the fork lane's members and entry end per project | CPME practice; worded by Bob, chat, 2026-10-26 |
| `maintenance_pull_space` valve actuator removal (`layout.yaml`) | harness; equipment service space per project | CPME practice |
| INST-SR-001 maker's straight run (`instrument-mounting.yaml`) | principle harness; per-instrument values per project | CPME practice |
| INST-POS-001, INST-LEAK-001 (hygienic clamp-mounted instruments) | harness | CPME practice |
| STR-PS-001 tube clamp hanger, STR-PS-002 support spacing incl. 3.0 in (`structural.yaml`) | harness; lines in scope per project | CPME practice |
| DRF-LBL-*, DRF-ARR-*, DRF-PLC-* P&ID drafting (`drafting.yaml`) | harness; a brand new P&ID only | CPME practice |
| `panel_working_clearance`, `disconnect` and the other electrical-interface fields (`electrical-interface.yaml`, values null) | harness; enclosure type and hazardous area per project | CPME practice |
| Shipping envelope and lift points (TR-18, TR-19) | project (`layout.yaml` `shipping_envelope`, `lift_points`) | CPME practice |
| The job's product rules (`job/design-rules/`) | job; listed in `job/design-rules/README.md` | per that file |

Background for these rules: `harness/knowledge/Design Standards.md`; the job's own background is in `job/knowledge/`.
