---
name: skid-layout
description: Step 4a for the project's skid - lay out the equipment the job's product holds (from the project's equipment list and the job's design framework) and the frame inside the shipping envelope, as compact as possible, with forks under the heaviest equipment, equipment service space, insulation and actuator and instrument clearances, and the job's layout specifics; produce layout options with footprint and margins for Bob to pick. Use when starting a skid model, moving equipment, or comparing layout options.
---

# Skid layout (step 4a, cad-design-engineer)

`<project>` is the active project folder (`rp.PROJECT`, named in `job/JOB.md`).

Reads the step 1 lists, `job/components/` (the equipment, valve and
instrument STEPs as filed), `harness/design-rules/*.yaml`, `job/design-rules/*.yaml` and
`<project>/01_Design_Basis/05_Standards_Specifications/Design_Rules/*.yaml`,
and the job's design framework in `job/knowledge/` (named in `job/JOB.md`).
**Read the job's design framework for the equipment a unit holds and its
layout and piping specifics** (on every job, the section "Layout and piping
specifics for skid-layout and pipe-route"). Where the project has a tank,
also its `02_Engineering/05_Tank_Sizing/tank-modifications.md`.
Writes `<project>/03_Working_Design/CAD/01_Master_Assembly/<MODEL-ID>/` source and builds to `<project>/03_Working_Design/Exports/build/<MODEL-ID>/`
(`model-iterate`).

## What goes on the skid

From the project's equipment list (never assumed), and the job's design
framework for what a unit of this product holds. Place only what the
equipment list and the P&ID name.

## Hard constraints

- **Shipping envelope (TR-18):** ships in one piece in an enclosed 53 ft
  swing-door dry van; every option fits **170 L x 60 W x 106 H in**, height
  from the bottom of the base to the highest point, insulation included.
  Values and sources: the project's `Design_Rules/layout.yaml`
  `shipping_envelope`. Report the footprint and the margin on each axis for
  every option.
- **As compact as possible** within that (TR-18; Bob, 2026-09-24).
- **No lift points; forks only** (TR-19). **The forks go directly under the
  heaviest equipment** (LAY-FORK-001, harness `layout.yaml` `fork_lift`;
  Bob, chat, 2026-10-26). That equipment sits over a clear fork lane between
  two full-length rails, entered from a skid end; the frame under it is
  sized for the fork case. The project's lane is its `layout.yaml`
  `lift_points.fork_lane`, named by member tags once the frame exists. Never
  the long sides or the panel end.
- **Front and rear:** name them by member tags in the project's records.
- **Equipment is forced (TR-02):** place the specified models, or the
  Bob-approved ones where a project DEC brings sizing in (`job/JOB.md`);
  concerns go to `equipment-concerns.md`, accepted, and work goes on.
- **The job's layout specifics:** the heights, service spaces, drops, falls
  and edge positions the job's rules set for its equipment, from the job's
  design framework and `job/design-rules/`. Where a specific depends on a
  vendor drawing not yet in hand, reserve the space and flag it `unknown`.
- **Equipment service space:** keep each piece of equipment's maintenance
  pull and lift-out path clear, from the chosen part's vendor drawing
  (`unknown` until selected: reserve and flag), and the pull spaces in the
  project's `layout.yaml`.
- **Insulation:** on insulated lines and equipment, every clearance is
  measured to the insulation jacket, not the bare pipe or vessel. Thickness
  is `unknown` until the line list sets it; reserve and flag it.
- **Clearances:** valve actuator removal (`layout.yaml`
  `valve_actuator_removal`), pump motor pull, instrument access and
  orientation (`instrument-mounting.yaml`), panel working clearance
  (`electrical-interface.yaml`), with the panel clear of relief and vent
  discharge, joints that can leak, and hot surfaces.
- **Tank (only where the project has one):** the tank STEP as filed and its
  `tank-modifications.md`; a tank, if any, follows the P&ID nozzles.
  Nozzles marked `unknown` are not placed.
- **Standardize (TR-25):** repeated details (equipment stations, drip legs,
  nozzle and tap details) are the same parametric block on every unit; say
  so when a detail is one-off.

## Options

- Two or three options at most, each a parameter set in the same model
  source, not a separate model. One `<MODEL-ID>` per skid; never rebuild
  another agent's model.
- A short table per option: footprint L x W x H, margins, fork lane clear and
  under which equipment, equipment service space clear, each job layout
  specific achieved (or its named alternative), notable trade-off. Bob
  picks; agents don't sign Gate 2.
- Frame members `FM-nnn`, plates `PL-nnn`, supports `PS-nnn`. If member
  numbers change, check the members named for the fork lane in `layout.yaml`
  still name the same members.
- The frame calc (Gate 3) models only the fork case above; the engineer
  performs the check.

## Then

`model-iterate` (envelope and interference checks), `model-file` before Bob
looks, give him the filed GLB path and a `cad_show` link. No renders unless
he asks.

## Hand-off

Options with footprint and margins, filed revision, checks, assumptions with
their record, TR rows (TR-02, TR-04, TR-18, TR-19, TR-25), CAPABILITY GAP,
NEXT (`pipe-route` work, or `engineering-manager` Gate 2 package).
