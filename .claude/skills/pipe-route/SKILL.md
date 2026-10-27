---
name: pipe-route
description: Route or change process piping on the project's skid model (step 4b) the way Bob wants it, scoped by each line's service class (PIPE-SVC-001) - on hygienic lines one clamp at valve-on-nozzle, tee-on-valve, gaskets at the clamp gap, taps as tee plus ferrule; on pipe classes flanged or welded per the class, with the job's rules for each class (slopes, drains and the arrangement its equipment needs); like valves at one level, check valves at PIPE-CV-001 10 D, piping split at every weld (TR-24), uniform supports that allow for insulation. Use for any routing, spool or support edit in <project>/03_Working_Design/CAD/01_Master_Assembly/<MODEL-ID>/piping/ or skidlib, before model-iterate.
---

# Pipe route (step 4b)

`<project>` is the active project folder (`rp.PROJECT`, named in `job/JOB.md`).

Reads `<project>/03_Working_Design/PID/02_Tag_Lists/line-list.csv`, the step 4a layout, `job/components/` and the
rule YAMLs (harness `piping.yaml`, `sanitary.yaml`, `structural.yaml`; the job's `job/design-rules/`
files, starting with `piping.yaml` `job_rules_by_class`; the project's `Design_Rules/` scope and values).
**Read the job's design framework for the equipment a unit holds and its layout and piping specifics**
(`job/knowledge/`, named in `job/JOB.md`; the section "Layout and piping specifics for skid-layout and
pipe-route").
Writes the model source only (`<project>/03_Working_Design/CAD/01_Master_Assembly/<MODEL-ID>/piping/<line>/`,
`skidlib/`). Then `model-iterate`; `model-file` before Bob looks.

## Service class first (PIPE-SVC-001)

Read each line's `service_class` before routing it. The class sets its material, joints and rules; a rule of
one class is never applied to a line of another. A line with class `unknown` is routed to the layout only and
reported "class unknown".

| Class | Material and joints (harness PIPE-SVC-001) | Rules |
|---|---|---|
| hygienic | A270 S2 316L tube; tri-clamp ferrules and orbital butt welds | SAN-*, INST-*, STR-PS-*, PIPE-CV-001, TR-20 to TR-22, plus the job's rules for the class |
| utility-water | per the customer spec, `unknown` until given | SAN-DRAIN-001, PIPE-CV-001, the governing code (SAN-PIPE-001); other SAN-* only where the spec calls for them; plus the job's rules |
| steam | carbon steel A106 / A53 Gr B, Sch 40 (Sch 80 threaded and small bore); flanged or butt welded; threaded only at 2 in and below | SAN-PIPE-001, plus the job's rules |
| condensate | as steam (Sch 80 common) | SAN-PIPE-001, plus the job's rules |
| relief-vent | as the line it relieves | SAN-PIPE-001, plus the job's rules |
| air | per the actuator and instrument makers | none, plus the job's rules |

"The job's rules" for a class are `job/design-rules/piping.yaml` `job_rules_by_class.<class>`, with their
values in the job's rule files and the project's scope. A job with none for a class adds nothing.

## Bob's piping preferences (2026-09-30 onward)

Company-wide practice, carried to every project; each applies only to the classes named.

- **One clamp (hygienic).** A valve clamps straight onto the equipment
  nozzle; a tee clamps straight onto the valve. No filler spools. On
  flanged classes the same idea holds with flanges: no filler spools.
- **Like valves at one level (all classes).** Identical branches sit at one
  valve elevation, and their stubs are the same height (CPME practice).
- **Slope where a rule needs it, nowhere else.** On hygienic lines,
  SAN-SLOPE-001 only on lines in its project scope; on other classes, the
  falls, drip legs and drains the job's rules for that class set. A sloped
  header's fall goes in a welded tee-branch extension
  (`Walker.tee(..., branch_ext=)` once the model source exists; one weld, no
  clamp), never a ferrule-to-ferrule spool. Never a V-sloped header.
- **Check valve after a pump (water side: hygienic and utility-water):** PIPE-CV-001, 10 nominal D developed (20 in at
  2 in), shortest clean route; more is not better. If anything asks for more,
  ask why first.
- **Gaskets in every joint.** Hygienic clamp joints at the 0.080 in gap (CPME practice)
  (`skidlib/joint_gaps.py`, once the model source exists); flanged joints
  carry the gasket thickness of the flange class.
- **Removable joints are fine** (TR-20). Hygienic: don't cut clamps to save
  cost. Other classes: flanged or union breaks at every serviceable
  component so each can come out.
- **Instrument taps.** Hygienic: a tee plus welded ferrule (TR-21). Other
  classes: the maker's and the job's practice for that service class
  (threaded or socket-weld boss, and any fitting the class needs ahead of the
  instrument). Inline instruments are placed as their component spools,
  which already carry the straight run (`component-add`). Don't re-derive
  straight run in routing.
- **Connections.** Hygienic: every process connection is tri-clamp, threads
  case by case (TR-22). Steam and condensate: flanged or welded, threaded
  only at 2 in and below (PIPE-SVC-001).
- **Equipment nozzles:** where the job's rules say a nozzle takes no piping
  load, support the piping independently and give it a flexible leg (offset
  or bend) for growth.
- **Relief and vent discharge:** as the job's rules for the relief-vent
  class set them.
- **The job's piping specifics:** the arrangement each of the job's
  equipment pieces needs (from the job's design framework and rules).
- **Split at every weld** into separate bodies carrying spool and weld IDs
  (TR-24): spools `<LINE>-SP<nn>`, welds `<SPOOL>-W<nn>`, line numbers
  exactly as on the P&ID.
- **Supports:** uniform spacing (planner `plan_run`), STR-PS-001 / STR-PS-002
  (harness `structural.yaml`) on stainless tube; on carbon steel, per the
  governing piping code (SAN-PIPE-001). Supports and their clearances allow
  for the insulation thickness on insulated lines, `unknown` until the line
  list sets it. Accepted findings stay in the `pipe_supports.py` ACCEPT lists;
  don't re-raise them.
- **Hard minimums:** when geometry sets one (e.g. an elbow's centreline),
  tell Bob the number instead of fighting it.

## Envelope and orientation

- Stay inside TR-18 (170 x 60 x 106 in), insulation included. Growth on the
  piping face is the usual risk; give the margin in the hand-off.
- Go by member tags for front and rear.
- Don't rotate a pump casing; turn the discharge elbow instead.

## Working with Bob's edits

- One revision per batch of his edits: build, `model-file`, show the filed
  GLB path and a `cad_show` link, stop. No re-review loop per letter and no
  renders unless he asks (Bob, 2026-10-08).
- A tag in his text that does not exist: match it to the geometry he named
  and ask in one line. Never guess the tag.
- He reads the model piece by piece (`<LINE>-SP<nn>.pc<nn>`); keep piece ids
  stable where you can.

## Hand-off

Filed revision path, one line per edit with numbers (lengths, elevations,
falls and drops the job's rules set, margins), lines whose class is
`unknown`, checks from model-iterate, assumptions with their record, TR rows
(TR-18, TR-20..22, TR-24, TR-08), CAPABILITY GAP, NEXT (`none` unless a
check failed).
