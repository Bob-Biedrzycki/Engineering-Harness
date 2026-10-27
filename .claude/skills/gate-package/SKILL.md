---
name: gate-package
description: Assemble a review or gate package (Gate 1 P&ID data, Gate 2 layout, Gate 3 frame, Gate 4 final) for the project's skid - run the harness checks, write findings that cite rule IDs, respect accepted findings, and hand the engineering-manager a package for Bob. Agents prepare; only Bob approves. Use when a gate is ready or Bob asks for a review.
---

# Gate package

Gates (CLAUDE.md "Approval gates"): 1 P&ID data matches the drawing
(process-engineer); 2 equipment layout (cad-design + mechanical-piping); 3 frame
structural check and fork-lift case (TR-19, LAY-FORK-001; engineer performs it); 4 final model and drawing
sign-off (engineering-manager). Agents never sign a gate (hard rule 7).

## Steps

1. **Pin the inputs:** the filed revisions only (`<project>/06_Issued_Revisions/Models/<MODEL-ID>/...-rev<X>`,
   `<project>/06_Issued_Revisions/Drawings/<DOC-ID>/...-rev<X>`). Never a `<project>/_work/` copy.
2. **Run the checks** (repo venv; exit 0 PASS, 1 FAIL, 2 NOT IMPLEMENTED;
   first line is the summary):
   - `harness/checks/pid_consistency.py` (lists vs model; builds the model)
   - `harness/checks/tag_crosscheck.py`
   - `harness/checks/envelope.py`, `interference.py`
   - `harness/checks/sanitary.py` (hygienic lines only), `pipe_supports.py`
   - the mechanical-piping review of each line against its service class
     (PIPE-SVC-001: the company-wide rules for the class plus the job's
     rules for it, `job/design-rules/piping.yaml` `job_rules_by_class`) and
     the job's review addendum (`job/knowledge/Review Addendum.md`); a line
     with class `unknown` is listed "not checked"
   - `harness/checks/drive_pointers.py`
   Report every FAIL, skip and NOT IMPLEMENTED as it is.
3. **Findings** against `harness/templates/design-review-checklist.md`, the
   job's review addendum (`job/knowledge/Review Addendum.md`) and the
   TR register. Each finding: MUST-FIX / SHOULD / NOTE, the rule id
   (PIPE-CV-001, SAN-DL-001, LAY-FORK-001, TR-18, a job rule id...), the part or spool id, the number, the
   proposed fix. No finding without a rule; if none exists, say so and
   propose one through `design-rule-add`.
4. **Accepted findings stay accepted:** the ACCEPT lists in `sanitary.py` and
   `pipe_supports.py` and Bob's DEC records. Don't re-raise them.
5. **Lean** (Bob, 2026-10-08): SHOULD and NOTE items go in one backlog Linear
   issue for the next batch, never their own revision. Only a MUST-FIX gets a
   `NEXT:` line.
6. **Package:** one Markdown file under `<project>/05_Reviews_Changes/01_Internal_Reviews/` naming the gate, the
   filed revisions, check results, findings table, open questions and HOLDs (HOLDs
   never block, TR-23), every `ASSUMPTION:` with its record, and the TR
   compliance list. Hand it to the `engineering-manager`, who reviews last and
   never approves.

## Hand-off

Package path, check summary lines, count of MUST-FIX / SHOULD / NOTE, TR rows
touched, CAPABILITY GAP, NEXT (the MUST-FIX owner, or `engineering-manager`
review, or `none`).
