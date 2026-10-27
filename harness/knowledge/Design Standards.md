# CPME Skids — Engineering Standards Reference

**Scope:** Design, fabrication and assembly of CPME skids for food and beverage plants. Company-wide (harness). Which standards apply to which line follows the line's service class (`harness/design-rules/piping.yaml` PIPE-SVC-001): hygienic design (§1) on hygienic lines; the job's product-specific standards (§8) on its other classes.
**Owner:** CPME Engineering
**Revision:** B — 2026-10-27, job-neutral: product-specific content moved to the job's `job/knowledge/` (§8 is now a pointer; sections 1-7 keep their numbers). A — 2026-10-26.

---

## How to use this document

This file covers the **industry and consensus standards** that a CPME skid is normally designed and built against. It does **not** cover customer-specific requirements: those are HOLDs until received in writing, kept in the project's `holds.md`, and never assumed (`CLAUDE.md` hard rule 5, TR-23).

Precedence, highest first:

1. Applicable law and code (OSHA, NEC/NFPA 70, state and local jurisdiction)
2. Customer specification, where one has been issued in writing
3. The consensus standards below
4. CPME internal practice

Where a customer spec is silent, the standards below govern. Where it conflicts, the customer spec governs — but the conflict gets logged, not absorbed silently.

**Edition control:** no edition years are given here on purpose. Standards revise on their own cycles and a stale year in a reference document is worse than no year. Confirm the current edition at the time of design freeze and record the edition actually used in the project's standards register.

---

## 1. Hygienic design (hygienic lines only, PIPE-SVC-001)

| Standard | Covers | Typical applicability |
|---|---|---|
| **3-A Sanitary Standards** (numbered by component) | Component-level sanitary design and certification | Mandatory for dairy; common as a reference for other food/bev |
| — 3-A 02-xx | Centrifugal and positive displacement pumps | |
| — 3-A 63-xx | Sanitary fittings | |
| — 3-A 00-xx | General requirements: baseline hygienic design rules, seals, gasket joints, leak-detection paths | Not on file; cited by makers |
| — 3-A 74-xx | Sensors and sensor fittings and connections: leak-detection (telltale) path and its self-drainage | Not on file; cited by makers. Bears on every clamp-adapter instrument |
| — 3-A 28-xx | Flow meters, including magnetic flowmeters | Not on file; cited by makers |
| **3-A Accepted Practice 605** | Installation and cleaning of processing equipment and hygienic pipelines, including instrument fittings | Hygienic pipelines |
| **ASME BPE** | Part SD (design for cleanability, drainability, slope, dead legs), SF (surface finish / Ra), MJ (material joining), DT (dimensions and tolerances: hygienic tube, fittings, instrument and short-outlet tees, ferrules, clamp unions), MC (seals, clamp-union gasket intrusion), PM (polymeric materials), **PI (process instrumentation: instrument installation, orientation, insertion)** | Bioprocessing standard, increasingly cited in food/bev. BPE-2024 has no Part SG or Part DF |
| **EHEDG Guideline 8** | Hygienic design principles | European reference, widely recognized. Free download |
| **EHEDG Guidelines 10, 35** | Hygienic design of closed equipment for processing liquid food (10); hygienic welding of stainless steel tubing (35) | European reference, widely recognized |
| **EHEDG Guideline 37** | Hygienic design and application of sensors (Part 1) | Not on file; cited by makers |
| **EHEDG Position Paper, Easy Cleanable Pipe Couplings and Process Connections** | Sensor dead leg in a tee L ≤ (D − d); accepted couplings and process connections | Not on file; cited by makers. Lists ISO 2852 as withdrawn: name the ferrule standard actually purchased (ASME BPE Part DT, or DIN 32676 series C), not ISO 2852 |
| **ISO 14159** | Safety of machinery — hygiene requirements | Cited by FSSC 22000 guidance |
| **EN 1672-2** | Food processing machinery — hygiene and cleanability requirements | Required for CE marking |
| **NSF/ANSI 51** | Food equipment materials | Material acceptance |
| **21 CFR 177** | Indirect food additives — polymers (gaskets, seals, elastomers) | Elastomer selection |
| **21 CFR 110 / 117** | Current Good Manufacturing Practice | Umbrella requirement |
| — 21 CFR 117.40 | Equipment and utensils: cleanable, installed for cleaning and maintenance, closed systems kept sanitary; (f) instruments that measure or control conditions preventing microbial growth accurate, precise, maintained and adequate in number | Equipment clause of the umbrella requirement; covers temperature instruments on a product-side heating duty |

**Dairy note:** where the process is non-dairy, 3-A certification is generally not contractually required, but 3-A design principles and Accepted Practice 605 remain a sound and defensible basis. Record the n/a determination rather than leaving it unstated.

**Utility note:** whether a utility line that does not touch product is hygienic is the customer's call, recorded as the line's service class (PIPE-SVC-001). Component standards for the job's own equipment, and the job's notes on its utility lines, are in its `job/knowledge/` (§8).

---

## 2. Materials, piping and welding

### Piping design

| Standard | Covers |
|---|---|
| **ASME B31.3 / B31.1 / B31.9** | Candidate governing piping codes: B31.3 process piping, B31.1 power piping, B31.9 building services piping (heating water and low-pressure steam within its limits). Which governs is the owner's or AHJ's decision, a project value (SAN-PIPE-001) |
| **ASME B36.10M / B36.19M** | Carbon steel and stainless steel pipe dimensions |
| **ASME B16.5 / B16.9 / B16.11** | Flanges, buttweld fittings, forged socket-weld and threaded fittings |

### Check valves after a pump discharge (CPME practice; rule PIPE-CV-001)

This is **CPME internal practice** (precedence 4 above), not a code or standard requirement.

- **Guidance:** give a check valve downstream of a centrifugal pump about **5 to 10 pipe diameters** of developed pipe from the pump outlet, so the flow has settled before it reaches the disc.
- **Why:** right at the pump flange the flow is swirling and uneven. A disc sitting in it flutters (chatter), which wears the seat, the hinge or spring and the guide, and can make noise and a water-hammer slam at shutdown. Swing checks are the most sensitive; spring-loaded (lift / poppet) checks much less.
- **CPME value:** **10 nominal diameters** of developed centerline length, pump outlet face to check valve inlet face (20 in for 2 in). Rule and value: `harness/design-rules/layout.yaml` PIPE-CV-001 (designation: harness, CPME practice).
- **More is not better.** Extra length only adds pipe, welds, hold-up volume and drain paths. Route no longer than the rule needs.
- **What overrides it:** a valve or pump maker's installation instruction that asks for more, or a written customer requirement. Record which one governs. If a P&ID or reviewer asks for a larger distance, find out why before designing to it.
- **Do not confuse with:** straight-run requirements for flow meters and other instruments (a different reason, set by the instrument maker), or NPSH / suction-side straight run (pump inlet, not discharge).

### Materials

| Standard | Covers |
|---|---|
| **ASTM A270 Grade S2** | Sanitary stainless tubing — the product-contact specification (hygienic lines) |
| **ASTM A312 / A403** | Stainless pipe and wrought fittings |
| **ASTM A106 Gr B / A53 Gr B** | Carbon steel pipe (non-hygienic service classes, per PIPE-SVC-001) |
| **ASTM A234 WPB / A105** | Carbon steel buttweld fittings / forged fittings and flanges |
| **ASTM A240** | Stainless plate and sheet |
| **ASTM A554** | Welded stainless mechanical/structural tubing |
| **ASTM A380** | Cleaning, descaling and passivation — procedure |
| **ASTM A967** | Passivation — chemical treatments and acceptance testing |

### Welding

| Standard | Covers |
|---|---|
| **AWS D18.1** | Welding of austenitic stainless steel tube and pipe in sanitary applications — **the acceptance criteria document for product-contact welds** |
| **AWS D18.2** | Weld discoloration levels / purge acceptance color chart |
| **AWS D1.6** | Structural welding code — stainless steel (skid frame) |
| **AWS D1.1** | Structural welding code — steel (any carbon steel members) |
| **ASME BPVC Section IX** | Welding procedure and performer qualification (also carbon steel pressure piping under B31.1 / B31.3) |

### Pressure equipment

| Standard | Covers |
|---|---|
| **ASME BPVC Section VIII Div. 1** | Pressure vessels — process vessels, tanks, air receivers and equipment shells above code threshold, unless exempt (exemptions are jurisdiction-dependent) |

Atmospheric tanks are typically outside code scope; capture the vendor data sheet and nameplate in the package regardless.

---

## 3. Frame, fork-lift case and transport

The skid has no lift points; it is handled by forks under the heaviest equipment (TR-19, LAY-FORK-001). ASME B30.20 and BTH-1 apply only if a lift point is ever specified.

| Standard | Covers |
|---|---|
| **AISC 360** | Specification for structural steel buildings — frame member design, carbon steel members |
| **AISC 370** | Specification for structural stainless steel buildings — frame member design in stainless (the stainless counterpart of AISC 360: austenitic material properties, stainless column curve, section limits, strain-hardening allowances) |
| **AISC Design Guide 27** | Structural stainless steel — design guidance, material properties, grade selection and fabrication. Predates AISC 370; use it as guidance, with AISC 370 as the specification |
| **AWS D1.6 / D1.1** | Frame welding (see above) |
| **ASME B30.20** | Below-the-hook lifting devices — safety standard (only if a lift point is ever specified) |
| **ASME BTH-1** | Design of below-the-hook lifting devices — lifting lug design (only if a lift point is ever specified) |

**Transport envelope** is a legal/permit constraint, not a design standard: DOT/FMCSA and state limits define the shippable width, height and length. Where a skid is specified to ship in one piece on a standard trailer, the envelope becomes a hard design input and should be stated as such in the design basis. For an enclosed dry van the rear door opening governs, not the legal road limits: 53 ft swing-door vans publish about 98-99 in W x 108-111 in H openings, and roll-up doors are lower. Each project's values are in `<project>/01_Design_Basis/05_Standards_Specifications/Design_Rules/layout.yaml` `shipping_envelope` (`<project>` = the project folder, `job/Project-*`).

---

## 4. Electrical and controls

| Standard | Covers |
|---|---|
| **NFPA 79** | Electrical Standard for Industrial Machinery — the governing standard for skid-mounted machinery |
| **NFPA 70 (NEC)** | National Electrical Code — plant interface, feeders, grounding |
| **UL 508A** | Industrial control panels — panel build and shop listing |
| **UL 698A** | Industrial control panels for hazardous locations, if applicable |
| **NEMA 250 / UL 50E** | Enclosure type ratings — 4X typical in washdown areas |
| **IEC 60204-1** | Electrical equipment of machines — required in place of NFPA 79 for CE-marked export |

### Controls and documentation

| Standard | Covers |
|---|---|
| **ISA-5.1** | Instrumentation symbols and identification — **P&ID symbology** |
| **ISA-5.4** | Instrument loop diagrams |
| **ISA-101** | Human-machine interfaces for process automation |
| **IEC 61131-3** | PLC programming languages |
| **ISA-7.0.01** | Quality standard for instrument air |

---

## 5. Machine safety

| Standard | Covers |
|---|---|
| **ISO 12100** | Safety of machinery — risk assessment and risk reduction |
| **ISO 13849-1** | Safety-related parts of control systems — performance levels |
| **IEC 62061** | Functional safety of safety-related control systems (alternative to 13849) |
| **ISO 14120** | Guards — general requirements for design and construction (also hot-surface guards) |
| **ANSI B11.0 / B11.19** | US machine safety — general requirements and risk reduction measures |
| **OSHA 29 CFR 1910.147** | Control of hazardous energy (lockout/tagout), including thermal and pressure energy isolation |
| **ANSI/ASSP Z244.1** | Lockout/tagout and alternative methods |

---

## 6. Documentation and quality

| Standard | Covers |
|---|---|
| **ASME Y14.5** | Dimensioning and tolerancing (GD&T) |
| **ASME Y14.100** | Engineering drawing practices |
| **ISO 9001** | Quality management system |
| **FSSC 22000, Additional Requirement 2.5.15** | Equipment management — obliges the customer to issue a purchase specification and obliges the supplier to provide evidence of hygienic design compliance before installation (hygienic scope only) |
| **ISPE Baseline Guide 5** | Commissioning and qualification — only where a pharmaceutical client is involved |

---

## 7. Standards register — project use

For each project, record per line: standard, edition used, applicable / not applicable, basis for an n/a call, and whether the customer spec overrides. An unrecorded n/a is the item most likely to resurface in review. The register is the project's `00_Project_Admin/07_Project_Controls/Registers/` standards register.

| Standard | Edition | Applicable | Basis / override |
|---|---|---|---|
| | | | |

---

## 8. Product-specific standards

A job's product-specific standards are in its `job/knowledge/` (named in `job/JOB.md`).

---

## Sources

- FSSC 22000 V6 Guidance Document — Equipment Management: https://www.fssc.com/wp-content/uploads/2023/03/FSSC-22000-V6-Guidance-Document-Equipment-Management.pdf
- §1: ASME BPE part names are from the free ASME BPE-2024 contents PDF; EHEDG titles from EHEDG catalogue and news pages; 3-A numbers from 3-a.org/standards; 21 CFR 117.40 from the eCFR text (Cornell LII copy).
- §8: the job's own standards file in `job/knowledge/` carries its sources.

Standard titles and scopes above are stated from general engineering practice, except where a source is named. Purchase and verify the governing text of any standard before citing it as a contractual basis.
