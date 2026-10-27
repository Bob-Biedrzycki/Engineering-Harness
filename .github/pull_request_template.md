## Day
<!-- One PR per day (Bob, 2026-09-24). Branch daily/YYYY-MM-DD. List every change of the day below. -->
Date:

## Linear issues advanced
<!-- Agent tasks live in Linear (Bob, 2026-09-28; TR-12, C-06). One line per issue, by its Linear ID. -->
Relates to    (use "Fixes <ID>" only if this merge satisfies the whole issue; Linear closes it on merge)

## Role / agent
<!-- which .claude/agents role produced this -->

## Scope of change

## Affected IDs
<!-- P&ID tags, line numbers, spools, FM/PL/PS members, document IDs -->

## Before / after

## Rules and standards cited
<!-- rule ids from harness/design-rules/ (company), job/design-rules/ (every project in the job) and <project>/01_Design_Basis/05_Standards_Specifications/Design_Rules/ (this project; <project> = job/Project-*) *.yaml, per each line's service class (PIPE-SVC-001); harness/knowledge/Design Standards.md sections and the job's standards in job/knowledge/ -->

## Checks run
- [ ] harness/checks/pid_consistency.py — result:
- [ ] harness/checks/sanitary.py — result:
- [ ] harness/checks/interference.py — result:
- [ ] harness/checks/envelope.py — result:
- [ ] harness/checks/tag_crosscheck.py — result:
Skipped checks and why:

## Derived output
- [ ] STEP/DXF regenerated from source in this PR
- [ ] Snapshot images attached
- [ ] Tool versions recorded

## ASSUMPTIONS
<!-- each traced to its record: "ASSUMPTION: ... (H1)" or "(Q-0001)" -->

## Todd's requirements (harness/knowledge/Todd Requirements.md)
<!-- every TR row this change touches: "TR-08: met, rev A filed with PDF" or "TR-xx: NOT MET, <reason>" -->

## Drawings filed (TR-06 to TR-08)
- [ ] Each drawing handed off is filed in <project>/06_Issued_Revisions/Drawings/<DOC-ID>/ as DWG + exported PDF
- [ ] Next sequential revision letter in the file name; no filed file modified or overwritten
- [ ] Revision block row with note; changed items clouded
- [ ] revisions.csv row with sha256 for every file filed
- [ ] Annotated tag <DOC-ID>-rev<X> for each issued revision

## Open questions / decisions needed from the engineer

## Registers updated
<!-- documents.csv, sources.csv, interfaces.csv, verification.csv -->

## Handoff
Branch / commit:
Next action:
