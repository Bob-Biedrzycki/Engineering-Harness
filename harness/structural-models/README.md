# skidframe: load-bearing models for CPME skid frames (agent guide)

**Company-wide tool** (`harness/structural-models/`, synced to every job from the Engineering Harness master). Built
and reviewed three times on an earlier skid job and moved here on 2026-11-06 (Bob, chat: "should be included in
the engineering Harness Master and applied to this Hot Water Set project appropriately"). **The tool lives in the
harness; every result lives in the project that used it**, saved by `run` with its use notes (the practice Bob set
for the thermal models, 2026-11-06). How a job applies it (its liquids, hot members, typical frames) is in that
job's knowledge; each project's `02_Engineering/06_Mechanical_Structural/README.md` says what applies there.

`skidframe` answers the structural questions a skid frame raises: will the frame carry the tanks, pump and
piping; does it stay stiff enough; do the legs buckle; do the welds, tube walls and joints hold; what does
each foot carry; can it tip, slide, be lifted by forklift or crane, and ride a truck. It is a working aid
for the engineer's Gate 3 check (CLAUDE.md, approval gates), **not a structural certification and never sealed**.

- Stainless members: **ANSI/AISC 370-21** (Specification for Structural Stainless Steel Buildings).
  Carbon members: **ANSI/AISC 360-22**. Loads: **ASCE/SEI 7-22**. Anchors: **ACI 318-19 Ch. 17**.
  Lifting lugs: **ASME BTH-1-2020**. Transport: **49 CFR 393.102 / 393.106**. Clause-by-clause notes are in
  [METHODS.md](METHODS.md).
- Units everywhere: **in, lb, psi, lb-in, F, Hz**.
- Verified: `tests/` (run them; the count is in REVIEW-LOG) against hand calculations, AISC Manual tables,
  closed-form solutions and the rendered specification pages.
  Every pass of the build and review is recorded in [REVIEW-LOG.md](REVIEW-LOG.md).

## Quick start

From this folder (`harness/structural-models`), with the repo venv:

```bash
..\tools\venv\Scripts\python.exe -m skidframe list
```

A preview (nothing saved; never quote it as a result):

```bash
..\tools\venv\Scripts\python.exe -m skidframe check frame_check examples\frame_check_skid_base.yaml
```

The result, saved into the active project (`rp.PROJECT`):

```bash
..\tools\venv\Scripts\python.exe -m skidframe run frame_check <inputs.yaml>
```

```bash
..\tools\venv\Scripts\python.exe -m unittest discover -s tests -v
```

Exit code 0: every check passes. 1: a check fails (the report says which and why). 2: bad input (the message
says what is missing). Inputs are YAML or JSON. Every model has a worked example in `examples/` to copy.

### Saving a result in the project (`run`)

`run` refuses an inputs file without its **use notes**, four top-level keys the models never see:
`name` (short case name), `purpose` (why it is run and what decision it supports), `inputs_source` (where each
input came from: the filed cut list, manifest, piping mass, vendor drawing; a text or a key-by-key map) and `run_by`
(the agent or person). Optional: `status` (default: working aid for Gate 3, not approved) and `notes`. It writes

- `<project>/02_Engineering/06_Mechanical_Structural/Frame_Calcs/<YYYY-MM-DD>_<model>_<name>[-n]/` holding the
  record `<name>.md` (use notes first, then the full report), `inputs.yaml` (the exact input) and `result.json`;
- one row in `<project>/02_Engineering/11_Scripts_Models/frame-calc-log.csv` (result, governing check, FAIL count,
  ASSUMPTION and warning counts, suite version and source hash).

A saved record is never overwritten: the same case on the same day takes `-2`, `-3`. Save the record folder and the
log with the repo's save tool after a run. Draft a project's inputs file in `<project>/_work/` (gitignored); the
record keeps the exact copy as `inputs.yaml`, and a rerun starts from that copy. Never put project inputs in
`examples/`.

In Python (`sys.path` to this folder): `from skidframe.catalog import MODELS; calc = MODELS["weld"][0](inputs)`;
`calc.to_dict()`, `calc.to_markdown()`, `calc.failed`, `calc.governing`.

## Folder

| Path | What |
|---|---|
| `skidframe/core.py` | `Calc` result record (results, PASS/FAIL checks with ratio and clause, ASSUMPTION lines, warnings) |
| `skidframe/save.py` | `run`: the project record folder, its use notes and the `frame-calc-log.csv` row |
| `skidframe/materials.py` | A554 / A240 / A276 stainless, A500 / A36 / A992 carbon, fillers, bolts; properties at temperature |
| `skidframe/sections.py` | Round and rectangular tube (rounded corners, design wall), bar, flat, angle, channel, I-shape |
| `skidframe/frame.py` | 3D frame solver: contacts (feet, tines), releases, P-Delta, buckling, natural frequencies |
| `skidframe/members.py` | AISC 370 / 360 tension, compression, flexure, shear, torsion, interaction |
| `skidframe/connections.py` | Fillet welds and weld groups, tube-to-tube joints, tube wall under point load, bolts |
| `skidframe/design.py` | Models `frame_check`, `member_check`, `beam`, `section_properties` |
| `skidframe/supports.py` | Models `support_reactions`, `base_plate`, `anchors`, `leveling_foot` |
| `skidframe/stability.py` | Models `seismic_force`, `overturning`, `transport` |
| `skidframe/lifting.py` | Models `forklift`, `lift_lug`, `slings` |
| `skidframe/local.py` | Models `weld`, `bolt`, `hss_joint`, `concentrated_load`, `plate` |
| `skidframe/dynamics.py` | Models `natural_frequency`, `pump_vibration`, `fatigue` |
| `skidframe/beams.py`, `loads.py` | Closed-form beams, columns, plates; ASCE 7 combinations and the skid load-case list |
| `examples/` | One input file per model (templates) |
| `tests/` | Verification suite (stdlib unittest) |

## Which model, when

**Critical models** decide whether the frame works. Run them on every skid.
**Support models** answer a narrower question, or feed a critical one. Run them when their trigger applies.

| Question | Model | Tier | Run it when |
|---|---|---|---|
| Does the frame carry every combination (members, deflection, reactions, lift-off, buckling, frequency)? | `frame_check` | critical | Always: base, stands, legs. Again for LIFT and TRANSPORT |
| What does each foot carry, and with one foot loose? | `support_reactions` | critical | Early layout, foot sizing, sanity check of `frame_check` |
| Can it tip or slide; what is the tip angle; what anchor uplift? | `overturning` | critical | Tall or narrow skids, seismic sites, transport, forklift handling |
| Forklift: load centre, truck capacity, fork length, CG between tines | `forklift` | critical | Every forklift-lifted skid; then `frame_check` with the tines as contacts |
| One member with known forces | `member_check` | critical | Hand-checked posts, legs, brackets |
| Welds: member ends, brackets, lugs, foot plates | `weld` | critical | Every load-carrying weld |
| A tube landing on a tube face | `hss_joint` | critical | Every tube-to-tube joint that carries load |
| A point load on a tube wall (tank leg, tine, foot, support) | `concentrated_load` | critical | Any bearing on a tube wall without a gusset or saddle |
| Truck: tie-down forces, tipping in the trailer, frame transport cases | `transport` | critical | Every shipped skid (TR-18: enclosed dry van) |
| Lifting lugs and their welds | `lift_lug` | critical | Crane lifts by lugs |
| Seismic force | `seismic_force` | support | Site has a seismic design category (SDS from the customer) |
| Anchors to the floor | `anchors` | support | Anchored skids |
| Base plates | `base_plate` | support | Posts or legs on plates |
| Leveling feet | `leveling_foot` | support | Skid on feet: with the max reaction from `frame_check` |
| Sling leg loads | `slings` | support | Crane lifts |
| Textbook beam | `beam` | support | Single members, quick sizing, checking `frame_check` |
| Plate panel | `plate` | support | Deck plates, drip pans, pump base plates, pads |
| Bolts | `bolt` | support | Bolted panels, pump bases |
| First natural frequency | `natural_frequency` | support | Pumps, motors, panels on brackets |
| Pump resonance and unbalance | `pump_vibration` | support | Every pump or motor on the frame |
| Fatigue | `fatigue` | support | More than 20,000 load cycles over the life |
| Section properties | `section_properties` | support | Choosing a tube |

## Workflow for a skid frame (the order to run things)

1. **Collect inputs from records, never invent them** (CLAUDE.md hard rule 1). Use frame members and sections from
   the filed model's cut list (`*-cut-list-frame.csv`), equipment weights and CGs from the manifest and
   the job's equipment weight record, and piping mass from `*-piping-mass.csv`. Take liquid volumes from the tank
   data. A missing value gets `unknown` or a question (`Q-nnnn`). Any value you must assume becomes an `ASSUMPTION:` line with its record.
2. **Load cases** (`loads.py`, `SKID_LOAD_CASES`): D (steel, equipment dry, empty piping), F (liquid; also run
   empty), HYDRO (brimful), L (only if people stand on it), Eh/Ev (seismic site only), T (hot line anchored twice),
   LIFT, TRANSPORT, PUMP.
3. **Quick look**: `support_reactions` for foot loads and the one-foot-loose case. Use `overturning` for the tip angle.
4. **Frame model** (`frame_check`): nodes at every joint, foot, tank leg and support; members from the cut list.
   Model feet as `uz: contact`. Fix `ux, uy` at one foot and `uy` at another to stop the frame sliding or spinning.
   Equipment goes in `masses` (lb), so one `body` case loads gravity, transport and seismic together. Put liquid
   in nodal or member point loads. Combinations come from `combinations`, or ASCE 7 automatically from the case
   names. Set K, Lb and deflection limits per member in `design`. Use `pdelta: true` for posts and legs with sway,
   `buckling: true` to see the buckling factor, and `modal: n` for frequencies.
5. **Lift**: `forklift` gives the load centre and impact factor. Then run `frame_check` again with the tines as
   contacts at the members that actually bear: the lowest undersides in the fork lane. Cut members at the tine
   lines so a node sits on each tine. Copy `examples/frame_check_forklift_lift.yaml`. **A cut member keeps its
   whole unbraced length**: give each segment `Lc_z`, `Lc_y`, `Lb` (and `Lv`, `L_torsion` for round tubes) in
   `design`. Otherwise every strength check uses the short segment length, which is unconservative (CPM-190 F-11).
6. **Transport**: `transport` gives the restraint forces and the body vectors `[0.8, 0, -1]`, `[-0.5, 0, -1]` and
   `[0, ±0.5, -1]`. Run `frame_check` with those cases and tie-down points as supports.
7. **Local checks at every load path joint**: `weld` (member ends, brackets), `hss_joint` (tube on tube),
   `concentrated_load` (legs, tines and feet on tube walls), `leveling_foot`, `base_plate` / `anchors` if used,
   and `lift_lug` / `slings` for crane lifts.
8. **Dynamics**: `pump_vibration` with the frame's frequency at the pump (`frame_check` modal, or
   `natural_frequency`), then `fatigue` for details that cycle.
9. **Report**: every number used in the design comes from a `run`, saved in the project's
   `02_Engineering/06_Mechanical_Structural/Frame_Calcs/` with its use notes (above). The handoff lists every FAIL, every ASSUMPTION, and every approximation warning. Only Bob approves at Gate 3.

## How to read a result

- `status` PASS / FAIL; `governing` is the highest demand/capacity ratio and the clause it applies.
- Each check has a `ratio` (≤ 1.00 passes) and a `rule`, the clause it applies. Cite that clause in the deliverable.
- `assumptions`: every default the model filled. Each one must reach the deliverable as an `ASSUMPTION:` line with
  its record (Q-nnnn, HOLD, EC). If it changes the answer, give the input instead.
- `warnings`: approximations and limits of the method. A warning on a governing check means a hand check or a
  better input before anyone relies on it.

## Rules for agents using this suite

- **ASD by default**: loads unfactored in ASD combinations, Ω on strength. LRFD needs LRFD combinations
  throughout. ACI 318 anchors are strength design: give them factored loads.
- **Design wall thickness**: HSS properties use 0.95 × the nominal wall (AISC 370 B4.2b) unless `t_factor` is
  set to 1.0 with a documented tolerance tighter than -5 %.
- **Material at temperature**: give `temperature_F` for a member that runs warm (under a hot tank). In
  `frame_check` it goes on the member, or at the top level for every member. Retention factors come from AISC 370
  App. 4. An unknown member key stops the run, so a misspelt key cannot be silently ignored.
- **LRFD**: `frame_check` adds an unfactored `SERVICE D+F(+L)` combination, used only for deflection. Strength
  is checked on the factored combinations.
- **Non-ASCE cases** (LIFT, TRANSPORT, PUMP...) are run on their own under automatic combinations, so each must
  carry its own gravity and factor. HYDRO is run with D.
- **Member orientation**: local y is the projection of global +Z; for members within 1° of vertical, the
  projection of global +X. Use `roll` or `ref` to turn a rectangular post the other way.
- **Effective length**: K defaults to 1.0 with an ASSUMPTION. A post fixed at the base and free at the top is
  K = 2.1 (`beams.K_FACTORS`). Do not leave a cantilever post at 1.0.
- **Deflection limits** are serviceability choices (`design.DEFLECTION_LIMITS`): L/360 equipment beams, L/180
  cantilevers, L/1000 pump bases. Set `kind: cantilever` on every cantilever (arm, overhang, post with a free top).
  A beam is measured as sag from the line between its ends; a cantilever is measured as tip movement from the
  tangent at its support. The beam measure understates a cantilever. They are not code rules; adopting one as a company rule follows CLAUDE.md hard
  rule 11: ask Bob harness or job first.
- **Never edit results by hand**. Change the input file and rerun (TR-01).
- A **mechanism** error (exit 2) means a missing restraint, not a weak frame: add horizontal restraint or check
  releases.

## Known limits (each is flagged in the result when it applies)

1. **Round HSS shear and torsion** (AISC 370 G4, G8.1) follow the printed equations exactly. They were read from
   the rendered pages in pass 2 and their band limits were corrected in pass 3 (CPM-190 F-01). The bands are
   continuous.
2. **Rectangular tube-to-tube joints** are outside AISC 370 Chapter K. The model uses AISC 360-22 Chapter K forms
   with stainless Fy as a rational analysis (warned).
3. **Open shapes** (angle, channel, I) in stainless: lateral-torsional and flexural-torsional buckling are not
   computed (warned). Use tubes, or hand-check.
4. **Lifting lug** equations are BTH-1-2020 as publicly reproduced. Confirm against the purchased standard before
   issue.
5. The frame solver is linear elastic (plus P-Delta). It has no plastic redistribution and no local wall
   distortion inside the beam elements; joints are rigid unless released.
6. Elevated-temperature properties come from AISC 370's fire-design tables (App. 4), the only published
   stainless retention data in the specification.

## Adding or changing a model

A model is a function `inputs dict -> Calc` registered in `catalog.MODELS` with its tier, question and trigger.
It needs an example in `examples/` and at least one test in `tests/` whose expected value is a hand calculation
written out in the comment, a published table value, or a closed-form solution, never the code's own output.
Run the whole suite, then add a REVIEW-LOG entry. This folder is harness code: change it in the Engineering
Harness master (or seed the change up to it) so every job gets the same tool, and never hold job data here.
