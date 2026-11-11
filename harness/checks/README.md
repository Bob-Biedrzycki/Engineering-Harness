# harness/checks/ — automated verification

Every `harness/checks/*.py` runs on each pull request and on every push to `main`
(`.github/workflows/checks.yml`, through `harness/scripts/run_checks.sh`). Each
script is standalone: run it from the repository root with
`python harness/checks/<name>.py`.

**Design findings are reported as warnings on the PR and never fail it** (Bob,
chat, 2026-10-07: "The PR should not be flagging design findings."; CLAUDE.md:
checks report, they do not block design progress). Only broken tooling, the unit
tests (`harness/tests`) and a repo-integrity check fail the PR. The hard-fail
(repo-integrity) checks are listed once, in `HARD_FAIL_CHECKS` at the top of
`harness/scripts/run_checks.sh`: `drive_pointers.py` (a large file
committed or a malformed Drive pointer; CPME practice) and `filed_layout.py` (a
filed revision not in its own folder; Bob, chat, 2026-10-30). Run the same policy locally
with `PYTHON=harness/tools/venv/Scripts/python.exe bash harness/scripts/run_checks.sh`
(on Windows, MinGit's `usr\bin\sh.exe` with that `usr\bin` on `PATH`).

## Exit-code contract

| Exit | Meaning | CI effect |
|---|---|---|
| `0` | PASS — the check ran and found no violations | row in the CI job summary |
| `1` with a `<name>: FAIL - ...` summary line | FINDINGS — the check ran and found violations | `::warning` annotation, CI job passes; status FINDINGS, details in the log group |
| `1` with that summary, from a `HARD_FAIL_CHECKS` check | FAIL — repo integrity broken | `::error` annotation, **CI job fails** |
| `2` | NOT IMPLEMENTED — stub; nothing was verified | `::warning` annotation, CI job passes |
| `3` with a `<name>: ERROR - ...` line | ERROR — the check could not run (model did not build, rules unreadable) | `::error` annotation, **CI job fails** |
| `1` without the FAIL summary line, any other code, or a Python traceback | ERROR — the check is broken | `::error` annotation, **CI job fails** |

"CI job" here is the GitHub Actions run, not the CPME job (the product line and its repo).

Rules for check authors:

- Print **one summary line first**, starting with the check name, e.g.
  `sanitary: PASS — 42 spools checked` or
  `sanitary: FAIL — 3 dead legs exceed rule SAN-DL-001`. The workflow quotes that
  line in the CI job summary table and the PR body quotes it under "Checks run".
  A check that lints several targets may print one summary per target; the
  first `FAIL` one is quoted.
- Exit `1` **only** for findings, always with the `<name>: FAIL` summary. When
  the check cannot run (the model does not build, an input is unreadable),
  print `<name>: ERROR - <reason>` and exit `3`, so CI tells a broken tool from
  a finding.
- Print details after the summary line. They appear in a collapsed log group.
- Exit `2` **only** while the check is a stub. Once implemented, a check
  returns `0` or `1`; never exit `2` to skip part of a real check.
- A NOT IMPLEMENTED result is a warning, not a pass. It means the PR has
  **not** been verified by that check; the engineer must weigh that at review.

## Checks

The software-developer owns every check's code, exit codes and messages
(`.claude/agents/software-developer.md`). The owner role below answers for
what the check verifies.

| Script | Verifies | Owner role |
|---|---|---|
| `pid_consistency.py` | every P&ID tag in the model and vice versa; line from/to | process-engineer, cad-design-engineer |
| `sanitary.py` | instrument installation rules on the skidlib model, one row per tag x rule: SAN-DL-002 branch-instrument dead leg L < (D - d) to the sensor seat incl. the gasket gap, or the maker rule where the project row has no d; INST-POS-001 not position 5 (a project orientation value narrows it); INST-LEAK-001 leakage port at the lowest point; INST-SR-001 straight run up / downstream for every tag with a project value. SAN-DL-002, INST-POS-001 and INST-LEAK-001 apply to hygienic lines (PIPE-SVC-001); INST-SR-001 to every inline instrument. Values from `harness/design-rules/sanitary.yaml` / `instrument-mounting.yaml` and their project files (`<project>/01_Design_Basis/05_Standards_Specifications/Design_Rules/`, `<project>` = the project folder, `job/Project-*`); the third level, `job/design-rules/`, sits between them: the checks read harness and project today; job level is read once the first job-level rule exists. A row is PASS, FAIL, KNOWN, NOT CHECKED (the model does not carry the datum; listed, not a failure) or N/A. KNOWN: a finding tracked in the script's `ACCEPT` list, keyed by rule, tag and exact measured value, printed with its record and not failed; a changed value is a FAIL again, an unmatched entry prints as STALE; or an INST-SR-001 row of an instrument spool part that meets the project value once the straight run inside the part, read from its part record, is added to the run walked beyond its faces (short even then is still a FAIL). On a spool part SAN-DL-002 is NOT CHECKED and INST-LEAK-001 takes the adapter the part lists (Bob, chat, 2026-10-05: manufacturer best practices are built into the component STEP files, each instrument STEP carrying its required spool length with ferrules, so this check reports and does not block design progress). `--report <dir>` writes `instrument-rules.csv` / `.json`. SAN-SLOPE-001 and SAN-DL-001 are measured by the model's own routing report and checked by `sanitary_routing.py` (not this check). Tests: `python -m unittest discover -s harness/tests` | mechanical-piping-engineer |
| `sanitary_routing.py` | slope and dead legs, by the model's own routing report (skidlib `reports.routing_rows`; Bob, 2026-11-11: "Use the previous methods of checking slope and dead legs"): SAN-SLOPE-001 every near-horizontal spool run and each eccentric reducer's invert against the minimum slope; SAN-DL-001 every tee branch to its first closure, and the route's extra dead legs, as L/D against the limit. The check measures nothing and holds no rule value. A row is PASS (`ok`), N/A (the model's `n/a ...` scope note), FAIL (`BELOW`, `EXCEEDS`, `UNRESOLVED`) or KNOWN: a record the model source carries for the row, or a FAIL listed by object and exact measured value in the project's `accepted-findings.yaml` `sanitary_routing` section (a changed value is a FAIL again, an unmatched entry prints as STALE). A model whose skidlib has no routing report is not checked. `--report <dir>` writes `sanitary-routing.csv` | mechanical-piping-engineer |
| `interference.py` | piping vs frame vs equipment clashes (envelope level, skidlib model) | cad-design-engineer |
| `solid_clash.py` | clashes on the exported solids (placed CPME STEPs, every pipe piece), adjacent pairs included, so a valve lever into the pipe, valve or equipment beside it is found (interference.py skips every pair that meets by design); OPEN: a placed part's port that meets no joint, pipe end, pipe wall or other part; GAP: a part standing off what it is joined to; LOOSE: a valve or instrument with no ports. Information only, not failed: tap stacks (boss, well, thermometer in its well), SEAT (a thin slab at a shared face: a vendor STEP end a few hundredths off its port), PORT (studs, bolts or the companion flange envelope a vendor STEP carries in front of its port face, register `studs to X`), drain and relief outlets open by design; a face a model keeps as a reference point (names with actuator, door, pull, access, service) is counted, not reported OPEN, and a leveling foot bears like frame. Reads a model of either skidlib generation (`harness/lib/model_read.py`); the solids need the model's `skidlib/cad.py` (`piece_solid`, `placed_step`, `prim_solid`; optional `attach(m)`, `has_step(it)`), and where that module needs the cadgen venv the check is run with it, else only the port checks run and the summary says so. About 1-3 min per build; `--pairs-only` runs the port checks in seconds (Bob, chat, 2026-10-30: "eliminating collisions, and making sure all components are connected") | cad-design-engineer |
| `materials.py` | every pipe piece, frame member, plate and support against the construction materials list (`harness/design-rules/materials.yaml`): a material not on the list (MAT-LIB-001), or a bent piece in a material that is not bent (MAT-FORM-001). Purchased parts are not checked. Reads a model of either skidlib generation (`harness/lib/model_read.py`) | cad-design-engineer |
| `envelope.py` | shipped L x W x H vs `<project>/01_Design_Basis/05_Standards_Specifications/Design_Rules/layout.yaml` `shipping_envelope` (TR-18); height also with the leveling feet raised to their limit | cad-design-engineer |
| `drive_pointers.py` | no large file tracked in git; every `<file>.drive` pointer well formed (CPME practice) | software-developer |
| `filed_layout.py` | every filed drawing and model revision (job level and every project, `06_Issued_Revisions/Drawings` and `/Models`) sits in its own `<DOC-ID>-rev<X>/` folder: nothing loose beside `revisions.csv`, every `revisions.csv` `file` is `<DOC-ID>-rev<X>/<name>` and present (file or `.drive` pointer). `--fix` moves loose files into their folders without renaming them and records the moves in `path-crosswalk.csv` (Bob, chat, 2026-10-30: "Everything like for them should be in a folder for each rev.") | software-developer |
| `pipe_supports.py` | STR-PS-002 support placement (spans, valves, elbows, pump, vertical guides, hanger-to-weld clearance) and the first-pass STR-PS-001 load per support; the support member check is NOT CHECKED until STR-PS-001 has an allowable-stress field; `--report <dir>` writes `pipe-support-calc.csv` / `.md` | cad-design-engineer |
| `portal_terms.py` | terms lint on portal output (internal words and record IDs such as AI, agent, HOLD, TR- and DEC- IDs, DRAFT, repository ...), the tracker's rules only: warn mode, never FAIL (the tracker shows internal records on purpose; no estimating or customer portal on this job, Bob, chat, 2026-10-30); no arguments = newest filed project-portal, mobile-portal and portal-landing revisions; `--dir <folder> [--json <file>]` for a build. The site framework (project tracker, Mobile Optimized, landing page) is dormant until Bob defines the job's site | cad-design-engineer |
| `component_register.py` | the job and project component registers (`job/components/component-register.csv`, `<project>/03_Working_Design/CAD/05_Purchased_Components/component-register.csv`; `harness/lib/components.py`): full header; COMP-nnnn ids, status current / superseded, each (id, revision) once, one current row per id, an id in one library only; every named cut sheet, vendor STEP and CPME STEP present (file or `.drive` pointer) with a matching sha256 where given; every `COMP-nnnn_*` folder has a row. Reports only | software-developer (code), cad-design-engineer (register content) |
| `tag_crosscheck.py` | list-level tag integrity: no duplicate tag across the P&ID lists, and every valve and instrument reference resolves to a line or equipment tag | controls-engineer |
