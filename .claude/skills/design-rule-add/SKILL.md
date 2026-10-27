---
name: design-rule-add
description: Add a design rule, add a value field to an existing rule, or move a rule between the three levels - harness (company-wide, harness/design-rules), job (every project in the job, job/design-rules) and project (this project only, the project folder's 01_Design_Basis/05_Standards_Specifications/Design_Rules) - ask Bob the level first, never rename or remove keys the model reads, cite the basis, and rerun pid_consistency. Use before any edit to a design-rule YAML.
---

# Design rule add (hard rule 11)

## The three levels

Design rules have three levels (Bob, chat, 2026-10-26). A **job** is the
product line and its repo (named in `job/JOB.md`); a **project** is one
order in the job, its own folder `job/Project-<Project Number>-<Type>-<Top Level Version>/`
(the active one is `<project>/`, `rp.PROJECT`). The Project Number in the
folder name is the project code, e.g. 0000-00; `project_number` in project.yaml
is CPME's short order number, e.g. 0000-0.

| Level | Folder | Holds |
|---|---|---|
| 1. Harness | `harness/design-rules/` (`rp.HARNESS_DESIGN_RULES`) | The rule and value where the basis is a standard or CPME practice; every CPME job |
| 2. Job | `job/design-rules/` (`rp.JOB_DESIGN_RULES`) | Rules and values that hold for every project in this job |
| 3. Project | `<project>/01_Design_Basis/05_Standards_Specifications/Design_Rules/` (`rp.DESIGN_RULES`) | Where each rule applies on this project, and every value that depends on its lines, tags, equipment, service conditions, customer HOLDs or DEC records |

Designations recorded before 2026-10-26 as **job** (including "job only")
meant the order, so they are project level now. Leave those
records as written.

## 1. Ask Bob first, write nothing until he answers

Bob, 2026-09-25: "In the future when a new rule is to be added to either i
would like to be asked which designation it belongs in."

One line in chat: the rule, **harness**, **job** or **project**, your
recommendation and why. A subagent without chat writes the question to root
`Agent-to-Agent Questions.md` with a copy in `Agent-to-Bob Questions.md` and waits. Moving an entry between
levels is asked too.

Criterion (`harness/design-rules/README.md`, `job/design-rules/README.md`):
basis is a standard or CPME practice -> harness (rule and value). Holds for
every project in the job whatever the order -> job. Depends on this project's
lines, tags, equipment, service conditions, HOLDs or DEC records -> project (scope and
project-only values, `rule_ref` to the level above). Often split: principle
harness, values project (e.g. INST-SR-001).

## 2. Before writing: does a part solve it?

If a better component carries the requirement (straight run in the spool, a
short-outlet tee), do that through `component-add` instead of a rule or a
blocking check (Bob, 2026-10-05).

## 3. Write it

- Same rule id at every level; the harness entry has the rule and value, a
  job or project entry has `rule_ref` to the level above, its scope and its
  own values. A lower level narrows a higher one and never contradicts it.
- Basis cites the standard, page or DEC, plus "designation: <harness|job|project>,
  Bob, chat, <date>".
- Add the designation to the harness README "Split record" list.
- The loaders (`harness/checks/`, `harness/lib/`) read `rp.JOB_DESIGN_RULES`
  between harness and project. A job rule file a loader does not read yet
  needs that loader taught in the same change (`job/design-rules/README.md`);
  that code is the software-developer's.
- **Add fields, never rename or remove a key.** The model reads rule keys
  through `<project>/03_Working_Design/CAD/01_Master_Assembly/<MODEL-ID>/skidlib/inputs.py` once the model
  source exists (e.g. INST-SR-001 `upstream_DN`); a renamed key breaks the build, often with a misleading
  `KeyError`. Grep `skidlib/` for the key before touching it.
- Owners: piping.yaml, sanitary.yaml and the job's piping and product rule
  files (`job/design-rules/`) mechanical-piping-engineer; electrical-interface.yaml electrical-engineer; instrument-mounting.yaml controls-engineer; layout.yaml
  and structural.yaml the project engineer. Bob approves.
- Guidance prose, if any, goes in `harness/knowledge/Design Standards.md`
  (company-wide) or the job's knowledge files in `job/knowledge/` (job level).

## 4. Check

```
.\harness\tools\venv\Scripts\python.exe harness\checks\pid_consistency.py
```

It builds the model. A `KeyError` on a face id usually means a route failed
earlier; print the model's `problems` to find the cause.

## Hand-off

Rule id, level and file(s), Bob's designation words, checks, TR rows touched,
CAPABILITY GAP, NEXT.
