# Skid Engineering Firm: Record Keeping & Project Documents

> **Question:** What would internal record keeping look like? Also, what is the list of typical project documents that cover the process?

Internal record keeping at a skid shop usually splits into three layers: records tied to each project, records the company keeps across all projects, and quality/compliance records that have to survive audits and warranty claims.

---

# Part 1: Internal Record Keeping

## Per-Project Records

- **Project file:** One master folder or ERP/PLM record per project number (in this harness, the project folder `job/Project-*`). It holds the contract, PO, change orders, correspondence, and meeting minutes. Document Control or the PM owns it.
- **Drawing and revision control:** Every drawing and spec carries a revision history with approval signatures. There should be one controlled "current" set so the shop never builds from a superseded drawing.
- **Cost tracking:** Labor hours by task, material costs, and budget versus actual. This feeds future estimates, so it matters beyond the single project.
- **Traceability records:** Heat numbers from material certs, linked to specific spools and welds. This lets you trace any weld back to its material, welder, and procedure.
- **Weld log:** Weld number, welder ID, WPS used, date, and inspection result (including borescope video or photos).
- **Nonconformance reports (NCRs):** Anything built or received out of spec, plus its disposition (rework, use-as-is, scrap).
- **Punch lists:** Open items from FAT and SAT, and when each was closed.

## Company-Level Records

- **Welder qualifications (WPQ) and weld procedures (WPS/PQR):** Kept current, with continuity logs so certifications don't lapse.
- **Calibration records:** For inspection gauges, surface roughness testers, and test instruments.
- **Approved vendor list:** Supplier qualifications and performance history.
- **Standard library:** Reusable P&ID templates, PLC code blocks, standard BOMs, and standard details. This is where much of a firm's efficiency comes from.
- **Lessons learned / CAPA log:** Corrective and preventive actions from recurring problems.
- **Training records:** For shop, controls, and field staff.

## Retention

- Most firms keep project records for at least the warranty period plus several years.
- Quality and traceability records are often kept 7–10 years or longer, since beverage customers may ask for them during their own audits.

---

# Part 2: Typical Project Documents (Lifecycle Order)

## Sales / Contract

1. Customer URS (User Requirement Specification) or RFQ
2. Proposal / quotation, including scope, exclusions, and assumptions
3. Purchase order and contract terms
4. Project kickoff notes and project schedule

## Design

5. Functional Design Specification (FDS)
6. Process Flow Diagram (PFD)
7. P&IDs
8. Control narrative / sequence of operations
9. Customer intake and utility data (water, power, air, heating or cooling media, returns)
10. Equipment sizing calculations (duties and loads, major equipment, pumps, relief; the job's list is in its design framework in `job/knowledge/`)
11. General arrangement (GA) drawings
12. Fabrication and spool drawings, isometrics
13. Electrical schematics and panel layouts
14. I/O list, instrument list, and instrument data sheets
15. Bill of Materials (BOM)
16. Design review records and customer drawing approvals

## Procurement / Fabrication

17. Vendor POs and submittals
18. Material test reports (MTRs)
19. Weld procedures (WPS/PQR) and welder qualifications (WPQ)
20. Weld map and weld log
21. Inspection and Test Plan (ITP)

## Quality / Testing

22. Hydrostatic or pressure test reports
23. Surface finish verification and passivation certificates (hygienic lines)
24. Borescope inspection records (hygienic lines)
25. FAT protocol, executed FAT report, and punch list
26. NCRs, if any

## Delivery / Turnover

27. Shipping and packing lists, plus rigging and lifting instructions
28. Installation guide and utility requirements
29. SAT protocol and executed SAT report
30. Commissioning report, including the tuned control parameters
31. Operator training records and sign-in sheets
32. O&M manual, which includes vendor component manuals
33. As-built drawings and final PLC/HMI program backups
34. Recommended spare parts list
35. Warranty certificate and final turnover / acceptance sign-off

---

## Where Firms Get Into Trouble

- Items 33 and 34 (as-builts / program backups and the spare parts list) are the ones most often done late or skipped.
- The link between items 18 and 20 (material traceability to welds) is what 3-A and demanding beverage customers scrutinize most closely.
