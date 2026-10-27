# CPME Skid Engineering: Roles & Accountability

---

## Sales & Proposal

* **Sales / Applications Engineer:** Captures customer requirements such as what the skid serves, duty, flow and temperature needs, and the utilities at the skid (the job's intake questions, in its design framework in `job/knowledge/`). Owns the proposal and quote.
* **Process Engineer:** Sizes pumps, process equipment and tanks for the quote (in this repo only where a project DEC brings sizing in; `job/JOB.md` names it).
* **Estimator (or PM at smaller firms):** Owns costing and margin.

## Engineering & Design

* **Project Manager:** Owns scope, schedule, budget, change orders, and all customer communication after the PO is placed.
* **Process Engineer:** Owns the P&IDs, the functional specification, and the control narrative.
* **CAD Design Engineer:** Owns the 3D model, general arrangement drawings, spool and isometric drawings, and the frame design.
* **Mechanical Piping Engineer:** Owns piping design details by service class (PIPE-SVC-001): drainability, dead-leg limits and slope on hygienic lines; on the other classes, the job's class rules (`job/design-rules/`) and its review addendum (`job/knowledge/`).
* **Controls / Automation Engineer:** Owns PLC and HMI programming, the I/O list, instrument selection, and integration with the plant's systems.
* **Electrical Engineer:** Owns panel design, schematics, and UL 508A or NFPA 79 compliance.
* **Engineering Manager:** Owns design reviews and final drawing approval.
* **Software Developer:** Owns the design harness's own code: the model build, filing, close-out and publishing scripts, the automated checks and CI, the shared libraries, the drawing-filing and title-block tooling, the project and quoting portal builders (the site framework, project tracker, quoting/estimating portal and landing page, is dormant until Bob defines the job's site), and the pinned tool environment. Writes and runs code and tests; does not decide geometry, piping-rule questions or what the portals say.

## Procurement & Fabrication

* **Purchasing / Procurement:** Owns vendor selection, long-lead items such as pumps, valves, and major process equipment, and material certifications (MTRs).
* **Shop / Fabrication Manager:** Owns the build schedule, shop labor, and fit-up quality.
* **Certified Welders / Pipefitters:** Perform orbital, sanitary and carbon-steel pipe welding to the weld procedure (WPS/PQR). The Shop Manager remains accountable for their work.
* **Panel Shop Lead:** Owns control panel build and wiring.

## Quality & Testing

* **QA/QC Manager:** Owns weld inspection (borescope), weld logs, hydrostatic testing, and, on hygienic lines, surface finish (Ra) verification, passivation records and 3-A or EHEDG conformance.
* **Controls Engineer:** Owns FAT (Factory Acceptance Testing) execution. The PM is accountable for customer sign-off.
* **Document Control:** Owns the turnover package, which includes manuals, as-built drawings, and the certs listed above.

## Delivery & Aftermarket

* **Field Service / Commissioning Engineer:** Owns installation support, SAT (Site Acceptance Testing), control loop tuning at the customer site, and operator training.
* **Service / Aftermarket Manager:** Owns warranty claims, spare parts, and service contracts.

---

## Role Summary

|Role|Primary Accountability|
|-|-|
|Sales / Applications Engineer|Requirements capture, proposal, quote|
|Estimator|Costing, margin|
|Project Manager|Scope, schedule, budget, change orders, customer communication, FAT sign-off|
|Process Engineer|Sizing, P&IDs, functional spec, control narrative|
|CAD Design Engineer|3D model, GA, spool/isometric drawings, frame|
|Mechanical Piping Engineer|Piping by service class (PIPE-SVC-001), every class on the skid|
|Controls / Automation Engineer|PLC/HMI, I/O list, instruments, plant integration, FAT execution|
|Electrical Engineer|Panel design, schematics, UL 508A / NFPA 79|
|Engineering Manager|Design reviews, drawing approval|
|Software Developer|Harness scripts, checks, CI, libraries, filing tooling, portal builders, tool environment|
|Purchasing / Procurement|Vendors, long-lead items, MTRs|
|Shop / Fabrication Manager|Build schedule, shop labor, fit-up quality, welder work|
|Certified Welders / Pipefitters|Orbital, sanitary and pipe welding per WPS/PQR|
|Panel Shop Lead|Control panel build and wiring|
|QA/QC Manager|Weld inspection, weld logs, hydro; Ra, passivation, 3-A/EHEDG on hygienic lines|
|Document Control|Turnover package|
|Field Service / Commissioning Engineer|Installation support, SAT, loop tuning, training|
|Service / Aftermarket Manager|Warranty, spares, service contracts|

## Agent mapping (this repository)

The Engineering & Design roles above are implemented as subagents in
`.claude/agents/`. Controls and Electrical are scoped in this repository to
the mechanical interfaces only; see `CLAUDE.md`. The Mechanical Piping Engineer is
`mechanical-piping-engineer` (renamed from the sanitary role, CPME practice). The Software Developer is
`software-developer`, who owns the harness code so the CAD and project-manager
roles do not carry it in passing. The site framework (project tracker,
quoting/estimating portal, landing page) is dormant until Bob defines the
job's site. For what the job's product holds and how it is designed, every
agent reads `job/JOB.md` and the job's design framework in `job/knowledge/`.
