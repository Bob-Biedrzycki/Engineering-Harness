# Design Review Checklist — Skid Mechanical

Review id: DR-__   Project: ________ (project ID, e.g. 0000-00-TST-001)   Commit: ________   Date: ________
Reviewer (agent): engineering-manager   Approver (human): ____________

Each line is reviewed against the rules of its service class (PIPE-SVC-001). Items marked **hygienic lines only**
are n/a on the other service classes unless the customer spec calls for them; record "n/a" with the class, not a
blank. The items below are reviewed on every CPME skid, **plus the job's review addendum,
`job/knowledge/Review Addendum.md`** (its product-specific items, recorded on this review with their HA-nn numbers).

| # | Item | Result | Evidence / finding |
|---|---|---|---|
| 1 | Every P&ID tag present in model; every model component tagged | | pid_consistency.py |
| 2 | Every line from/to matches line list; every line carries a service class | | PIPE-SVC-001 |
| 3 | Every spool carries its line number; every weld numbered | | |
| 4 | Every design decision cites a rule or standard | | |
| 5 | Mechanical piping review exists; no open MAJOR | | mechanical-piping-engineer |
| 6 | Hygienic lines only: slope continuous to drain | | SAN-SLOPE-001, in the model's routing report (not sanitary.py) |
| 7 | Every low point of a hygienic or utility-water line drained | | SAN-DRAIN-001 |
| 8 | Hygienic lines only: dead legs within limit at every branch/instrument/valve: L/D <= 2 (SAN-DL-001); instrument branches L < (D - d) to the sensor seat incl. gasket gap, and any stricter maker rule (SAN-DL-002) | | SAN-DL-001, SAN-DL-002 |
| 9 | Hygienic lines only: finish, weld and gasket spec correct for service | | SAN-RA-001, SAN-WELD-001, SAN-MAT-001 |
| 10 | Job's review addendum items recorded (HA-nn), each with a result or "n/a" and the reason | | `job/knowledge/Review Addendum.md` |
| 11 | Every line's pipe or tube material, schedule or gauge, joints and gaskets per its service class | | PIPE-SVC-001, TR-20, TR-22 |
| 12 | Frame cleanable: no open ends, no water-holding ledges | | SAN-FRAME-001 |
| 13 | Interference check clean | | interference.py |
| 14 | Shipping envelope, fork access under the heaviest equipment, CG recorded | | envelope.py, LAY-FORK-001 |
| 15 | Maintenance pull space (pump motors, actuators, equipment internals) verified | | |
| 16 | Panel working clearance and door swing verified | | |
| 17 | Instrument straight-runs (INST-SR-001); on hygienic lines, position on the pipe (INST-POS-001) and leakage port visible at the lowest point (INST-LEAK-001); orientation and torque per tag (project `instrument-mounting.yaml`); access verified | | INST-SR-001, INST-POS-001, INST-LEAK-001 |
| 18 | Tie-in points match tie-in list | | |
| 19 | Interfaces register updated | | |
| 20 | Assumptions all logged as HOLDs / questions | | |
| 21 | Customer-spec HOLDs listed and none closed without a document | | TR-23 |
| 22 | STEP/DXF regenerated; tool versions recorded | | |
| 23 | Registers updated; no duplicate IDs | | |
| 24 | Nothing out of scope (PLC/SCADA, certification; sizing except where a project DEC brings it in) | | |

Result: PASS — ready for human review / RETURN

Decisions required from the engineer:
1.

Findings returned to:
