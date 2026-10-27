# Skid Engineering Firm: Schedules & Lists

> **Question:** Can you provide a complete list of schedules/lists for equipment, welds, piping, clamps, frame material, etc.? It would also be helpful to know in what specific documents they live in.

Most schedules exist in two places: a **master register** (usually a spreadsheet, ERP, or CAD database) that serves as the source of truth, and a **printed version** on a drawing or in a document package. Firms get into trouble when those two drift apart.

In each table, **"Lives in"** is where the schedule normally sits in the document set.

---

## Process & Equipment

| Schedule / List | Contents | Lives In |
|---|---|---|
| Equipment list | Tag, description, size, rating, vendor, model | Standalone register; referenced on P&IDs and in the FDS |
| Pump schedule | Flow, head, motor HP, seal type, inlet/outlet size | Pump data sheets and the equipment list |
| Equipment data sheet (per major item) | Duty, design conditions, connections, internals and type | Equipment data sheets and sizing calcs |
| Tank / vessel schedule (if any) | Volume, dimensions, insulation, level instruments, code stamp (ASME VIII or exempt) | Tank or vessel drawings and the equipment list |
| Nozzle schedule (per tank or vessel) | Nozzle ID, size, connection type, orientation, service | Fabrication drawing, as a table on the sheet |
| Product-specific schedules | The schedules the job's product adds to this list | The job's review addendum and design framework in `job/knowledge/` |
| Relief valve schedule | Tag, service, set pressure, capacity, inlet/outlet size, discharge destination | Equipment list and relief data sheets |
| Insulation schedule | Line or equipment, operating temperature, insulation type and thickness, jacket, removable covers | Insulation spec and GA notes |
| Utility schedule | Water, air, drain, heating or cooling media, and electrical demand at each connection | Installation guide and GA drawing notes |

## Piping

| Schedule / List | Contents | Lives In |
|---|---|---|
| Line list | Line number, service class, tube OD and gauge or pipe NPS and schedule, material, spec, from/to, design pressure and temperature, finish, slope | Standalone register; line numbers appear on P&IDs and isometrics |
| Piping specification / material classes | Allowed tube, fittings, finish, and gaskets for each service | Piping spec document, often company-standard |
| Valve schedule | Tag, type (control, butterfly, ball, globe, check), size, end connection, actuator, feedback, solenoid, air requirement | Standalone register; tags on P&IDs; ties to the I/O list |
| Spool list | Spool number, line, drawing reference, weight, status | Fabrication package index |
| Fitting take-off (per spool) | Tube or pipe lengths, elbows, tees, ferrules, flanges, reducers | BOM table on each spool / isometric drawing |
| Clamp, flange & gasket schedule | Connection ID, clamp or flange size and rating, gasket size and material (EPDM, FKM, PTFE, spiral-wound, graphite) | Isometric BOMs, rolled up into the project BOM; gasket list also goes in the O&M spares list |
| Tie-in / interface schedule | Customer connection points with size, type, elevation, and service | GA or interface drawing |
| Pipe support / hanger schedule | Support ID, type, location, spacing | Frame or spool drawings |

## Welding

| Schedule / List | Contents | Lives In |
|---|---|---|
| Weld map | Every weld numbered on the isometric | Isometric / spool drawings |
| Weld log | Weld number, welder ID, WPS, date, heat numbers joined, inspection result | QC record set, then the turnover package |
| Borescope / weld inspection log | Weld number, pass or fail, video or photo reference | QC records, attached to the weld log |
| Weld coupon log | Daily orbital weld test coupons, per machine and welder | QC records |
| Purge log | Oxygen level readings before welding | QC records; often combined with the coupon log |
| WPS/PQR index | Procedures and their qualified ranges | Company quality manual; copies go in the turnover package |
| Welder qualification register (WPQ) | Welder, processes, positions, continuity dates | Company quality system |

## Materials & Frame

| Schedule / List | Contents | Lives In |
|---|---|---|
| Material take-off (MTO) | Total tube, fittings, plate, and structural material by size and grade | Procurement package, derived from the model |
| Heat number / MTR traceability log | Heat number mapped to MTR, then to spool and weld | QC traceability matrix |
| Frame cut list | Member mark, profile (tube, angle, channel), size, length, grade (304/316), quantity | Frame fabrication drawing, as a BOM table |
| Plate / sheet list | Base plates, gussets, drip pans, panel mounts | Frame and detail drawings |
| Fastener / hardware schedule | Bolts, anchors, leveling feet, grade and size | Frame drawing BOM and the project BOM |
| Surface finish schedule | Ra requirement by component (product contact vs. non-contact), polish, passivation | Spec or ITP; verified in QC records |

## Electrical & Controls

| Schedule / List | Contents | Lives In |
|---|---|---|
| Instrument index | Tag, type, range, process connection, signal, vendor | Standalone register; tags on P&IDs |
| Instrument data sheets | Full spec per instrument | Controls package and turnover |
| I/O list | Every point with tag, type (DI/DO/AI/AO), PLC address, description | Controls design package; ties to the schematics |
| Motor / load list | HP, FLA, starter or VFD, circuit | Electrical package |
| Cable schedule | Cable ID, from/to, type, conductor count, length | Electrical drawings |
| Terminal / wire schedule | Terminal block and wire numbers | Panel schematics |
| Panel BOM | Every component in the control panel | Panel drawing set |
| Alarm list | Alarm, trigger, priority, operator action | FDS / control narrative |
| Interlock list / cause & effect matrix | Which conditions stop or permit which actions | FDS |
| Setpoint / parameter list | Supply temperature, high limit, pressures, flows | FDS as designed; commissioning report as-tuned |
| Network / IP address schedule | PLC, HMI, VFD, and remote I/O addresses | Controls package |
| Nameplate / tag label schedule | Every label, its text, and its location | Fabrication package |

## Testing & QA

| Schedule / List | Contents | Lives In |
|---|---|---|
| Inspection & Test Plan (ITP) | Every hold, witness, and inspection point | Quality plan, agreed with the customer early in the project |
| Hydro test boundary list | Test packages, boundaries, pressures, results | Test reports |
| Instrument calibration schedule | Calibration certs and due dates | QC records and turnover |
| Punch list | Open items from FAT and SAT | FAT/SAT reports |
| NCR log | Nonconformances and their dispositions | Quality system |

## Project Management

| Schedule / List | Contents | Lives In |
|---|---|---|
| Master document register / drawing list | Every document with its revision and status | Document control; the index to everything else |
| Submittal log | Documents sent for customer approval, with status | PM records |
| Transmittal log | What was sent to whom, and when | Document control |
| Question log | Open questions with the customer | PM records |
| Change order log | Scope, cost, and schedule changes | PM records |
| Procurement / expediting schedule | Order dates, lead times, promised and actual delivery | Purchasing records |
| Project schedule | Milestones and dependencies | PM records |

## Turnover / O&M

| Schedule / List | Contents | Lives In |
|---|---|---|
| Recommended spare parts list | Part, quantity, vendor, lead time | O&M manual |
| Gasket & seal replacement schedule | Replacement intervals by location | O&M manual |
| Preventive maintenance schedule | Tasks and intervals | O&M manual |
| Lubrication schedule | Pumps, motors, points, lubricant, interval | O&M manual |
| As-built drawing list | Final revision of every drawing | Turnover package |

---

## The Most Important Connection

The **line list, valve schedule, instrument index, and I/O list** all share tag numbers with the **P&ID**. Mature firms generate these from a single database or model so they can't drift apart. Shops that keep them in separate spreadsheets spend a lot of time reconciling them.
