# skidframe review log

Bob asked (chat, 2026-11-06) for the suite to be built and then looped through three times, "preserving what was
learned and the review process". This log is that record. Every pass appends one entry; nothing above is edited
except to mark an open item closed, with the pass that closed it.

## The review procedure (every pass follows it)

1. Read this log: the open items and the lessons.
2. Run the whole suite: `python -m unittest discover -s tests -v` and every example through the CLI. Record the
   counts.
3. Independent re-derivation: pick code paths that no test covers yet. Work a hand calculation from the clause
   (not from the code), write it into a test with the arithmetic in the comment, and run it.
4. Adversarial inputs: zero, negative, degenerate geometry, mechanisms, unit mistakes (feet for inches). The model
   must exit 2 with a clear message or give the right answer, never a silent wrong number.
5. Documentation against code: every clause, default and limit in README.md and METHODS.md matches what the code
   does, and each ASSUMPTION text matches the value used.
6. Fix what was found, rerun everything, and log findings, fixes, lessons and open items.

Severity: **MUST** (wrong answer or unsafe direction), **SHOULD** (incomplete or misleading), **NOTE**.

---

## Pass 1, 2026-11-06: research, build, first verification

**Research.**
- Read AISC 370-21 from the free PDF (text extracted with pypdf in the session scratchpad; positions dumped to
  decode equations).
- Confirmed the material minimums for A554 tube (Comm. Table C-A3.3), E and G, the E3 curves, the F7/F8 limits,
  the G2.2 Cv2 and G8.2 Cv bands, H1/H2, the J2.5 weld values, J3 bolts, J12 concentrated forces, K2 round joints,
  the App. 3 fatigue constants and the App. 4 retention factors.
- Confirmed the 49 CFR 393.102(a) accelerations from the regulation text. Forklift load-centre derating and the
  AWS A5.4 filler strengths come from public sources.

**Built.** The `skidframe` package:
- 22 models: 10 critical, 12 support;
- a 3D frame solver with contacts, releases, P-Delta, buckling and modes;
- one example per model;
- README (agent guide) and METHODS (research and math).

**Verification.** 47 tests, all passing:
- sections against the AISC Manual (HSS4x4x1/4);
- the frame solver against closed forms: simple, cantilever, fixed and propped spans, two-span continuous,
  releases, torsion, shear deformation, Euler buckling (pinned and cantilever), P-Delta amplification, modal
  frequencies, local axes with roll, body loads, contact lift-off and mechanism detection;
- stainless column and member checks against hand calculations;
- carbon column against AISC Manual Table 4-4;
- welds, the round T joint, J12, bolts, rigid foot reactions, tipping, seismic bounds, BTH-1, forklift,
  combinations, fatigue, SDOF, plate strip limits and temperature retention;
- hand checks of leveling_foot, hss_joint, beam and support_reactions end to end;
- every example run through the CLI.

**Findings and fixes, pass 1.**

| # | Sev | Finding | Fix |
|---|---|---|---|
| P1-1 | MUST | Leveling-foot and anchor thread pitch was guessed (3/4 in stud at 11 TPI; UNC is 10). It surfaced because the end-to-end hand check gave 1.337 and the model 1.273. | ASME B1.1 UNC table (`connections.UNC_TPI`), tensile stress area and minor diameter from it; test added |
| P1-2 | MUST | `Result.disp` could not address internal station nodes | `_idx` resolves user and station names |
| P1-3 | SHOULD | Eigen-buckling crashed (ARPACK zero start vector) when no member is in compression | Returns "none"; seeded start vector |
| P1-4 | NOTE | Five expected values in my first tests were my own arithmetic slips (J12 9,980 → 9,546; K2-3 6,174 → 6,549; tube A and I rounding; the 2016 vs 2021 fatigue equation form) | Hand calculations rewritten with every step in the comment |
| P1-5 | SHOULD | The example base put tank loads straight onto the feet, so the members were barely loaded and the example taught nothing | Loads moved to mid-bay member point loads |

**Open items for pass 2.**

| # | Item |
|---|---|
| O-1 (closed pass 2) | AISC 370 G4-5, G4-8, G8-5, G8-8 (round HSS shear and torsion, intermediate band) could not be decoded from the PDF text; interpolated between exact end points with a warning. Try rendering the page (browser pane) and read the equations exactly. |
| O-2 (closed pass 2) | Deflection "relative to the chord" is wrong for a cantilever (the chord rotates with the tip). Needs a cantilever / tip-deflection mode for members of `kind: cantilever`. |
| O-3 (closed pass 2) | Weld group with an unsymmetric group (Ixy ≠ 0): sign of the general flexure formula not yet tested. |
| O-4 (closed pass 2) | base_plate, anchors, transport and the seismic 7-22 path have no hand-check test yet. |
| O-5 (partly, pass 2) | BTH-1 equations taken from public reproductions: check them against a second independent source. |
| O-6 (closed pass 2) | E7-6 slender-wall compression and F7 effective section: no continuity or hand test yet. |
| O-7 (partly, pass 2) | frame_check: the user cannot run a member check on part of a member (station range); Lv is fixed at L/2; the station ratio is computed three times (speed). |
| O-8 (closed pass 2) | Adversarial input sweep not yet done (step 4 of the procedure). |

**Lessons.**
- Decode garbled specification equations by continuity at their range boundaries. It discriminates sharply, and
  it found the right form of E3-3, G2-9/10 and G8-11/12.
- An end-to-end hand check of a whole model finds bugs that unit tests of the pieces miss (P1-1).
- Write the hand calculation's arithmetic in the test comment. A wrong expected value is then visible, and the
  code is not "fixed" to match a slip.

---

## Pass 2, 2026-11-06: open items, specification re-read, adversarial inputs

**Method.** Followed the procedure: read the log, ran everything (47 tests, all examples), then worked the open
items. The new move this pass was to render the specification pages to images (pypdfium2, scratchpad only) and
read every equation decoded in pass 1 against the printed page.

**Specification re-read (rendered pages).** Confirmed exactly as coded: E3-3, E7-6, F7-4, F8-2, G2-10, G8-11 to
G8-13. Found two differences:

| # | Sev | Finding | Fix |
|---|---|---|---|
| P2-1 | MUST | Round HSS shear / torsion (G4, G8.1). The pass 1 interpolation used the wrong band limits, and the medium/long selection was coded as L/D <= 4.21 lambda; the printed criterion is 4.21 sqrt(lambda). The printed intermediate equations are 1 - 0.61(c sqrt(y) - 0.23) (CvM) and 1 - 0.61(s sqrt(x) - 0.23) (CvL). | `members._round_cv_stainless` rewritten from the page; hand tests: torsion CvL 0.9616 (3.0 x 0.120, L 100), shear CvM 0.7968 (6 x 0.050, Lv 60) |
| P2-2 | SHOULD | E7-8 round slender area had a square root that is not in the print; its upper limit (2.8 lambda_r Fy/Fcr) was missing | Fixed; beyond the limit the model stops (input error); hand test 0.8433 Ag |
| P2-3 | SHOULD | Cantilever deflection was measured from the chord, which understates the tip (O-2) | `member_deflection` returns a tangent-based `cantilever` measure; `frame_check` uses it for `kind: cantilever`; README rule added |
| P2-4 | SHOULD | `frame_check` accepted an unknown `kind`, combinations naming unknown cases (they only failed deep inside), no supports, and lengths that are clearly feet typed as inches | Each now stops with a clear input error; a units warning flags members shorter than 1 in or longer than 100 ft |
| P2-5 | NOTE | `frame_check` computed every station ratio three times | Once per station |
| P2-6 | NOTE | **WRONG, corrected in pass 3 (CPM-190 F-01): the bands are continuous; the code had the limit coefficient inside the power.** The printed CvM bands are not continuous at their limits (shear upper 0.522 vs 0.574; torsion upper 0.501 vs 0.544; lower about 0.97 vs 1.0) | Code follows the print; a test bounds the jumps at 0.06 so a coefficient typo would still show |

**New verification (14 tests, total 61, all passing):**
- exact round Cv by hand, band jump bounds, E7-8 and E7-6 continuity;
- cantilever deflection, by itself and through `frame_check`;
- an L-shaped (unsymmetric) weld group checked by equilibrium (sum f y dl = Mx, sum f x dl = 0) and a hand peak
  value of 28.12 lb/in;
- base plate t = 0.2770 in by hand;
- anchor group breakout 10,850 lb and the 1/2-13 stress area 0.1419 in2 (published);
- ASCE 7-22 Fp 451.3 lb;
- transport tipping 0.714;
- 11 adversarial inputs that must stop, and the units warning.

**O-5 (BTH-1).** A second public source (a Hanford calculation package and an Eng-Tips discussion of the 2011
text) agrees with the beff limits and the form of Cr. It adds that the 2020 edition permits Cr = 1.0 when
Dp/Dh > 0.90. The model keeps the formula, which is the conservative side. The equations still need checking
against the purchased standard; the model says so in every lug result.

**Open items for pass 3.**

| # | Item |
|---|---|
| O-9 (closed pass 3, CPM-190) | Independent review by a fresh reader (not anchored on the author's view) of frame.py, members.py and design.py: an agent that reads the code and the specification and tries to break it. |
| O-10 (closed pass 3) | Cross-check the suite against the project's earlier frame calc (job/data/frame-calc.md, Rev G on model Rev AA) on something both can compute, to show that the new tool reproduces or explains the old numbers. |
| O-11 (closed pass 3: design keys Lv, L_torsion) | Lv for round-HSS shear in `frame_check` is L/2 (conservative for a UDL span; a point-load span has a shorter Lv). Document it, or derive Lv from the shear diagram. |
| O-12 | BTH-1 against the purchased standard (needs Bob or the standard; not something an agent can close). |

**Lessons.**
- Continuity is a good test of a decode, but it cannot prove one. In pass 1 it accepted the wrong band limits for
  G4/G8, because the interpolation was continuous by construction. Read the printed page whenever it can be
  rendered.
- A specification's own equations can be discontinuous. Follow the print, and record the jump so nobody "fixes"
  the code toward continuity.
---

## Pass 3, 2026-11-06: independent review (CPM-190), cross-check with the earlier frame calc

**Method.**
- The author did not review their own work this pass. A fresh reader (the engineering-manager agent, Linear
  CPM-190) had the code, the specification text and the rendered pages, and was told to break the suite. It could
  write only a repro test file, `tests/test_review_pass3.py`, with expected values from the clause or a hand calc.
- The author fixed every finding in the code, without changing a single expected value in the reviewer's file, and
  added regression tests for the findings that file did not cover.
- In parallel, the author cross-checked the suite against an earlier job's frame calc.

**Reviewer findings and fixes (all closed this pass).**

| # | Sev | Finding | Fix |
|---|---|---|---|
| F-01 | MUST | Round HSS G4 / G8.1 band limits. The printed limit is a ((E/Fy)/sqrt(L/D))^0.80, with the coefficient outside the power. Pass 2 put it inside. Unconservative up to 6.6 % (6 x 0.040, L 300). | `members._round_cv_stainless`; the pass 2 test now bounds band continuity at 0.01 |
| F-01a | SHOULD | The pass 2 log, README and METHODS said the printed bands jump by 0.05. That was an artefact of F-01. | Corrected everywhere; P2-6 above marked wrong |
| F-02 | MUST | Spring supports reported zero reaction | `Result.reaction` returns -k u for a spring |
| F-03 | MUST | A slender rectangular web gave Mn = Mp | AISC 370 F7-6/7 with Rpg (F5-4, read from the rendered page) |
| F-04 | MUST | Square and flat bar torsion used T r / J (the circular-shaft formula) | tau = T / (alpha b c^2) from the rectangular-bar table |
| F-05 | MUST | Base plate, large eccentricity with Y < m: coefficient 1.83 instead of 2.58 (ASD) | Fixed (2.58 ASD / 2.11 LRFD) |
| F-06 | MUST | `temperature_F` on a frame member was silently ignored | Per member and top level; unknown member keys now stop the run |
| F-07 | SHOULD | A 0.02 deg tilt from vertical swung a post's local axes 90 deg | Members within 1 deg of vertical take local y from global +X; documented |
| F-08 | SHOULD | Buckling with released members (no axial force) failed: Kg was condensed with its own Schur complement | Kg carried through the elastic condensation transform (assembly and P-Delta force recovery); a failure now warns |
| F-09 | SHOULD | Automatic combinations silently dropped LIFT / TRANSPORT / HYDRO / PUMP | `loads.combinations` runs them (HYDRO with D, the rest on their own); `frame_check` warns |
| F-10 | SHOULD | LRFD runs never checked deflection | A service-only `SERVICE D+F(+L)` combination is added under LRFD |
| F-11 | SHOULD | Members cut at tine lines took the segment length for Lc / Lb | README rule; new `Lv`, `L_torsion` design keys |
| N-1 | NOTE | Contact iteration cap of 60 | 60 + 3 x contacts |
| N-2 | NOTE | 2-lug sling with the CG outside the lugs gave a negative leg | Input error |
| N-3 | NOTE | Seismic 0.75 applied to the anchor shear modes (conservative) | Kept, conservative |
| N-4 | NOTE | F7 h/b <= 3 not checked | Warning |
| N-5 | NOTE | Carbon slender-flange be from the 360-16 form | Warning; the 360-22 text was not available |
| N-6 | NOTE | P-Delta with releases used combined condensation | Same transform as F-08 |
| N-7 | NOTE | Square bar J 0.123 a^4 | Roark 0.1406 a^4 |
| N-8 | NOTE | Test count in the log | Updated below |

**Cross-check with the earlier frame calc (O-10).** `tests/test_crosscheck_frame_calc.py`:
- section properties of the 3.0 x 0.120 rails are identical (A 1.086, I 1.128, S 0.752, J 2.255);
- on the same rail, skidframe's AISC 370 flexure (compact, Fy Z / 1.67 on the 0.95 design wall) is 1.261 x the
  old 0.6 Fy S. An old bending-only ratio R maps to about R / 1.26; the Rev G lift at 3.39 is still about 2.7, so
  the conclusions stand;
- AISC 370 torsion (G8.1) is 0.857 x the old 0.4 Fy basis, so the new suite is stricter in torsion.

**Verification at the end of pass 3.** 84 tests, all passing. That is the 64 from passes 1 and 2 plus the
cross-check, 15 reviewer repro tests and 5 fix regressions. Every example runs through the CLI.

**Still open (needs Bob or a document an agent cannot get).**

| # | Item |
|---|---|
| O-12 | Check the BTH-1 lug equations against the purchased ASME BTH-1-2020. The 2020 edition also lets Cr = 1.0 when Dp/Dh > 0.90; the code keeps the formula, which is conservative. |
| O-13 | Check the carbon slender-flange effective width against the AISC 360-22 text (N-5). |
| O-14 | Before skidframe becomes the Gate 3 frame tool, Bob decides: (a) whether the suite stays project engineering or moves to `harness/` (company-wide); (b) whether the default deflection limits (L/360, L/180, L/1000) become design rules (CLAUDE.md hard rule 11: harness or job first). |

**Lessons (for whoever extends this suite).**
- An independent reader found six MUST defects in code the author had reviewed twice. A fresh reader with the
  spec and permission to break things is worth more than another author pass. Keep it in the procedure as step 3b.
- The author can misread a rendered page too (F-01: a coefficient's position against a bracket). Every equation
  read from an image needs a check that does not come from the same reading. The pass 1 continuity check would
  have caught F-01, and pass 2 explained it away as a "specification jump". When continuity fails, suspect the
  reading before the specification.
- Silent acceptance is the most dangerous failure (F-06 ignored key, F-09 dropped case, F-02 zero reaction).
  Inputs the code does not understand must stop the run.

**Procedure update.** Step 3b, added after pass 3: when a pass changes more than a few clauses, a fresh reviewer
(a role agent with its own Linear issue) tries to break the suite with repro tests whose expected values the
author never edits.

---

## Move to the harness, 2026-11-06 (not a review pass)

Bob, chat, 2026-11-06: the frame modeling tools "should be included in the engineering Harness Master and applied
to this Hot Water Set project appropirately". Done from the hot water set job (Hot-Water-Set repo) and copied to
the master.

- Moved from the CIP project's `02_Engineering/11_Scripts_Models/Structural_Models/` to `harness/structural-models/`;
  the package `cipframe` is now `skidframe` (company-wide name), version 1.1.0. No model, clause or expected value
  changed. The job it was built on keeps its own copy until it pulls the harness.
- New `run` / `check` split (`skidframe/save.py`): `check` is the old preview; `run` saves the result in the active
  project with its use notes and a `frame-calc-log.csv` row, the practice Bob set for the thermal models the same
  day. Old `run` with `--md` / `--json` is now `check`. `tests/test_save.py` adds 4 tests.
- Load-case text in `loads.py` no longer names only CIP liquids (F: process liquid SG; T: hot water, steam and
  condensate lines too). README wording: questions are `Q-nnnn`.
- CI: `harness/tests/test_structural_models.py` runs this folder's tests from the harness tests, so every job and the
  master check it.
- Suite after the move: 88 tests, OK (84 carried over + 4 save tests); every example runs through `check`.

Open items carried unchanged: the BTH-1-2020 lug check against the purchased standard, the one AISC 360-22 carbon
formula, and whether the deflection limits become harness or job rules (hard rule 11, Bob decides).