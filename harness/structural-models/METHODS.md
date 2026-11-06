# Methods: what each model computes, from which clause, and why it matters on a process skid

Research basis for the skidframe suite (2026-11-06). Sources read for this work:

- **ANSI/AISC 370-21**, Specification for Structural Stainless Steel Buildings (free from AISC). This is the
  governing member specification for ASTM A554 tube (listed in its Table A3.1). Chapters B, D, E, F, G, H, J, K,
  Appendix 3 (fatigue) and Appendix 4 (properties at temperature) were read from the PDF. Equations whose text
  extracted garbled were decoded, and each decode was checked by continuity at its range boundaries (below).
- ANSI/AISC 360-22 (carbon steel), ASCE/SEI 7-22 (loads), ACI 318-19 Ch. 17 (anchors), AISC Design Guide 1
  (base plates), ASME BTH-1-2020 (lifting devices), 49 CFR 393.102 / 393.106 (cargo securement, read from the
  Cornell LII text), Roark's Formulas 7th ed. (plates, beams), Blevins (natural frequencies), ISO 21940-11
  (balance grades), ACI 351.3R-18 (dynamic equipment frequency separation).
- An earlier skid job's frame calculation (report Rev H, kept in that job's repo): its lessons are listed at the end.

## 1. The checks a welded frame needs, and the model for each

Bob's starting list (2026-11-06) mapped to the suite:

| Check | Model(s) | Clause |
|---|---|---|
| Loads and support reactions (unequal legs, movement, impact, vibration) | `support_reactions`, `frame_check`, `loads.combinations`, `forklift`, `transport`, `pump_vibration` | ASCE 7-22 Ch. 2; statics |
| Beam bending and shear, σ = M/S | `frame_check`, `member_check`, `beam` | AISC 370 F7, F8, G3, G4 |
| Deflection, δ = PL³/48EI and other cases | `frame_check` (along every member), `beam`, `plate` | serviceability limits (design.DEFLECTION_LIMITS) |
| Leg buckling | `frame_check` (members + eigen-buckling), `member_check` | AISC 370 E3, E7; App. 8 via P-Delta |
| Combined loading and frame stability | `frame_check` (H1-1, H2-1, P-Delta), `overturning` | AISC 370 H1, H2 |
| Local failure: thin walls, plates, contact points | `concentrated_load`, `hss_joint`, `plate` | AISC 370 J12, K2; AISC 360 K1 |
| Welds and connections (throat 0.707 w) | `weld`, `hss_joint`, `bolt`, `lift_lug` | AISC 370 J2, J3, J4; AWS D1.6 |
| Feet, anchors, tipping | `leveling_foot`, `base_plate`, `anchors`, `overturning` | DG1, ACI 318-19 Ch. 17 |
| Fatigue | `fatigue`, `pump_vibration` | AISC 370 App. 3 |
| Added: lifting | `forklift`, `lift_lug`, `slings` | BTH-1, B30.9, B56.1 |
| Added: transport | `transport` | 49 CFR 393.102, 393.106 |
| Added: seismic | `seismic_force` | ASCE 7 Ch. 13 |
| Added: resonance | `natural_frequency`, `pump_vibration` | ACI 351.3R, ISO 21940-11 |

**Critical models** are the ones a skid cannot be released without: frame_check, support_reactions,
overturning, forklift, member_check, weld, hss_joint, concentrated_load, transport, and lift_lug (when lugs are used).
**Support models** answer a narrower question or feed a critical one.

## 2. Material: how the grade enters

- **Strength**: specified minimum, never "steel". A554 MT304/MT316: Fy 30 ksi, Fu 75 ksi. MT304L/316L: 25 / 70 ksi
  (AISC 370 Comm. Table C-A3.3). A240 plate: the same pairs (Table C-A3.2).
- **Stiffness**: E = 28,000 ksi and G = 10,800 ksi for austenitic; carbon is 29,000 / 11,200 ksi. A stronger grade
  does not reduce deflection. A deeper section or bracing does.
- **Stress-strain**: stainless yields gradually, so it gets its own column curves (E3, Table E3.1: curves A, B, C),
  a shear curve (G2.2 Cv2 up to 1.2) and local-buckling limits (B4.1). That is why carbon-steel formulas are not
  used for stainless members.
- **Temperature**: AISC 370 App. 4 retention factors. At 200 F: 304 ky 0.80, kE 0.96; 316 ky 0.87. A frame member
  under a 180-200 F tank loses about 20 % of its yield.
- **Corrosion** (why stainless): CIP caustic and acid washdown, chlorides, crevices. Use 304 for the frame and
  316/316L where chlorides or acid splash. Hollow members are seal welded all round (SAN-FRAME-001), so there is no
  crevice and no trapped liquid. Corrosion choices are sanitary rules, outside these models.
- **Welding**: the HAZ of cold-worked stainless anneals. Base metal strength at a weld is the annealed Fu
  (AISC 370 J2.4). Use E308L for 304 and E316L for 316; FEXX is 75 / 70 ksi (AWS A5.4). Strength above the
  specified minimum from cold forming (Fy,avg, B4.3) is not used at welded sections (B4.3 user note), so this
  suite never uses it.

## 3. Member strength (members.py), AISC 370-21

- **Classification (B4.1)**, E = 28,000 ksi, Fy = 30 ksi, √(E/Fy) = 30.55:
  - compression, rectangular walls: λr = 1.24√(E/Fy) = 37.9. Round: D/t ≤ 0.10 E/Fy = 93.3.
  - flexure, rectangular flange: λp 1.17√, λr 1.24√. Web: λp 2.54√, λr 3.01√. Round: λp 0.08 E/Fy,
    λr 0.31 E/Fy.
  - flat width b = B − 2t − 2r_in; design wall t = 0.95 t_nom (B4.2b).
  - **Consequence**: 3 x 3 x 0.065 tube (b/t ≈ 45) is slender in compression and flexure; 2 x 2 x 0.120 and the
    3.0 OD x 0.120 rails are compact.
- **Compression (E3)**: Fe = π²E/(Lc/r)².
  - Fy/Fe ≤ (β0/π)²: Fcr = Fy.
  - Fy/Fe ≤ 3.20: Fcr = 1.2 β1^((Fy/Fe)^α) Fy.
  - otherwise: Fcr = β2 Fe.
  - Curves (α, β0, β1, β2): A 0.56, 0.759, 0.409, 0.690 (I minor axis, other shapes); B 0.58, 0.891, 0.455, 0.820
    (round HSS, I major axis, welded box); C 0.69, 1.195, 0.501, 0.820 (rectangular HSS).
  - **Decode check**: E3-3 extracted as "1 2 1. β α". Reading it as 1.2 β1^((Fy/Fe)^α) gives 1.000 at the plateau
    boundary and β2/3.2 at the elastic boundary for all three curves. Every other reading was discontinuous.
  - Slender rectangular walls (E7-6, cold-formed HSS): be = b(1 − 0.22√(Fel/Fcr))√(Fel/Fcr), with
    Fel = 4π²E/(12(1−ν²)(b/t)²).
  - Slender round walls (E7-8): Ae = (0.6 λr Fy/(λ Fcr) + 2/5) Ag for λ < 2.8 λr Fy/Fcr. Beyond that the
    tube is outside the specification, and the model stops with an input error.
- **Flexure**:
  - F7 rectangular: Mp = Fy Z; noncompact Mn = Mp − (Mp − Fy S)(λ − λp)/(λr − λp); slender Mn = Fy Se, with
    be from F7-4.
  - F8 round noncompact: Mn = (1 + 0.068 λr/λ) Fy S ≤ Mp. Decode check: equals Mp at λ = λp for thin tubes.
  - F9 solid bars: Mp.
  - Rectangular HSS with h/b ≤ 3 has no lateral-torsional buckling (F7 user note).
- **Shear**:
  - G3 rectangular: Vn = 0.6 Fy Aw Cv2, Aw = 2ht, kv = 5. With x = (h/t)/√(kvE/Fy), Cv2 is 1.2 (x ≤ 0.33);
    1.2 − 0.62(x − 0.33) (≤ 0.97); (5.02 − x)/(1.62 + 3.55x) (≤ 2.68); 1.51/x² beyond. Decode checked by continuity.
  - G4 round: Vn = 0.6 Cv Fy Ag/2.
- **Torsion**:
  - G8.2 rectangular: Tn = 0.6 Cv Fy C, C = 2(B−t)(H−t)t − 4.5(4−π)t³. With x = (h/t)/√(E/Fy), Cv is 1.2 (≤ 0.74);
    1.2 − 0.28(x − 0.74) (≤ 2.17); (11.23 − x)/(3.62 + 3.55x) (≤ 5.99); 7.56/x². These are the G2 values × √5,
    consistent with kv = 5.
  - G4 / G8.1 round, read from the rendered pages:
    - Medium length (L/D ≤ 4.21√λ) uses y = √(L/D) λ^1.25/(E/Fy). Cv = 1.0 up to λ = a ((E/Fy)/√(L/D))^0.80,
      with the coefficient outside the power (so y = a^1.25 at the limit); then 1 − 0.61(c√y − 0.23) up to b;
      then d/y.
      Shear: a 0.32, b 4.65, c 0.47, d 2.67. Torsion: a 0.26, b 3.77, c 0.54, d 2.05.
    - Long members use x = λ^1.5/(E/Fy). Cv = 1.0 up to p (E/Fy)^0.67; then 1 − 0.61(s√x − 0.23) up to
      q (E/Fy)^0.67; then e/x.
      Shear: p 0.24, q 2.23, s 0.68, e 1.30. Torsion: p 0.20, q 1.87, s 0.77, e 1.00.
    - The bands meet at their limits (shear upper 0.391 = 2.67/6.834). Pass 2's reported "jumps" came from a
      misread (CPM-190 F-01).
  - F7 slender web (stainless): Mn = Rpg Fy S (or S_e), with Rpg = 1 − aw/(6.75 + 2.12 aw)(λ/λrw − 1) ≤ 1
    (F5-4) and aw = 2h/b ≤ 10.
  - Solid bars in torsion: τmax = T/(α b c²), with α from the rectangular-bar table (0.208 square to 1/3
    thin); J by Roark Table 10.7.
- **Interaction**: H1-1a for P/Pc ≥ 0.2, P/Pc + 8/9(Mz/Mcz + My/Mcy); H1-1b below it, P/(2Pc) + ΣM/Mc. When
  Tr > 0.2 Tc, H2-1: P/Pc + M/Mc + (V/Vc + T/Tc)². `frame_check` evaluates these at every station with the forces
  acting there together.
- **Factors**: φ 0.90 / Ω 1.67 for tension yield, compression, flexure, shear and torsion; φ 0.75 / Ω 2.00 for
  tension rupture.

## 4. The frame (frame.py)

Direct stiffness, 12-DOF Timoshenko beam elements:

- **Members**: each is subdivided (default 8, plus a cut at each point load). Uniform loads use consistent nodal
  loads, so nodal displacements are exact, and internal forces at any point come from element statics.
- **Releases**: static condensation.
- **Contacts**: active set. A support in tension is released; a released support the frame would pass through is
  restored. This reproduces feet lifting off and the skid "finding its seat" on fork tines, the behaviour the
  earlier frame calc established (FC-27/32).
- **P-Delta**: geometric stiffness iterated on the element axial forces. **Buckling**: linear eigenproblem
  (K + λKg)φ = 0. **Modes**: lumped mass, shift-invert eigensolution.
- **Why a frame model and not equal leg loads**: a welded grillage on 12 feet is highly indeterminate. Foot loads
  depend on member stiffness, where the loads sit, and which feet touch. The earlier calc found loose feet raising
  member ratios from 0.46 to 5.08.

## 5. Connections and local failure

- **Fillet weld** (J2.4, Table J2.5): Fnw = 0.60 FEXX on the throat 0.707w, φ 0.75 / Ω 2.00. A transverse load
  may take (1 + 0.50 sin^1.5 θ), but the suite does not use it (conservative).
- **Base metal along the weld** (J4.2): min(0.60 Fy t / 1.50, 0.60 Fu t / 2.00) per inch (ASD).
- **Weld groups**, elastic vector method (Blodgett; AISC Manual Part 8): the weld is a line with
  A = ΣL, Ix, Iy, Ip = Ix + Iy.
  - In plane: f = F/A plus torsion M r/Ip, perpendicular to the radius.
  - Out of plane: f = F/A + Mx y/Ix − My x/Iy.
  - The resultant is checked at every point.
- **Round tube on round tube** (K2.2, Table K2.1):
  - punching 0.6 Fy t π Db (1 + sinθ)/(2 sin²θ);
  - T/Y chord plastification Fy t² (3.1 + 15.6β²) γ^0.2 Qf / sinθ;
  - cross joint Fy t² (5.7/(1 − 0.81β)) Qf / sinθ;
  - Qf = 1 − 0.3U(1 + U) with the chord in compression.
- **Rectangular tube on rectangular tube**: not covered by AISC 370 (Chapter K user note). AISC 360-22 forms are
  used as a rational analysis (β ≤ 0.85):
  - axial: Fy t² [2η/(1−β) + 4/√(1−β)] Qf;
  - in-plane moment: Fy t² Hb [1/(2η) + 2/√(1−β) + η/(1−β)] Qf;
  - out-of-plane moment: Fy t² [0.5 Hb (1+β)/(1−β) + √(2 B Bb (1+β)/(1−β))] Qf;
  - φ 1.00 / Ω 1.50.
- **Point load on a rectangular tube wall** (J12-1):
  Rn = C t² Fy (1 − Cr√(r/t))(1 + Cl√(lb/t))(1 − Ch√(h/t)), with Table J12.1 coefficients for EOF/IOF/ETF/ITF.
  This is the check for a tank leg or a fork tine on a thin rail.
- **Bolts** (J3.7): Fnt 0.75 Fu; Fnv 0.45 Fu (threads in) or 0.55 Fu; J3-3 combined; φ 0.75 / Ω 2.00.

## 6. Floor, stability, lifting, transport

- **Rigid-base foot reactions**: R_i = k_i(a + b x_i + c y_i) from three equilibrium equations; contacts
  released. "One support loose" re-solves with each foot removed. That sizes feet when they are not re-checked
  after the first fill.
- **Base plate** (DG1): bearing fp = 0.85 f'c √(A2/A1) ≤ 1.7 f'c, φ 0.65 / Ω 2.31; m = (N − 0.95d)/2; ASD
  t = l √(2 fp Ω / Fy). For a large eccentricity, Y and the anchor tension come from the quadratic of DG1 §3.4.
- **Anchors** (ACI 318-19 Ch. 17):
  - steel: Nsa = Ase futa, with futa ≤ 1.9 fya and ≤ 125 ksi;
  - breakout: Ncbg = (ANc/ANco) ψed ψc ψcp Nb, with Nb = kc √f'c hef^1.5;
  - pullout: 8 Abrg f'c; pryout: kcp Ncpg; shear breakout to the edge;
  - interaction: ≤ 1.2;
  - seismic: 0.75 on the concrete modes;
  - post-installed anchors take their values from the ICC-ES report.
- **Overturning**: the convex hull of the bearing points; for each edge, resisting moment = gravity × distance,
  and overturning moment = lateral force × height. The tipping acceleration is d/h (static tip angle atan(d/h)).
  Sliding is ΣH against μ × gravity factor × W.
- **Seismic**:
  - ASCE 7-16: Fp = 0.4 ap SDS Wp (1 + 2z/h)/(Rp/Ip).
  - ASCE 7-22: Fp = 0.4 SDS Ip Wp (Hf/Rμ)(CAR/Rpo).
  - Both are bounded by 0.3 to 1.6 SDS Ip Wp, with Ev = 0.2 SDS D.
  - SDS and the component row are site and customer inputs. They never have defaults.
- **Transport**:
  - 49 CFR 393.102(a)(1) breaking-strength basis: 0.8 g forward, 0.5 g rearward, 0.5 g lateral, applied
    separately.
  - (a)(2) working-load basis: 0.435 / 0.5 / 0.25 g.
  - 393.106(d): aggregate tie-down WLL ≥ W/2.
- **Forklift**:
  - load centre = CG distance from the carriage stop; derated capacity = rated × LC_rated / LC (truck plate
    governs);
  - CG between the tines; impact factor (2.0 CPME practice) on the empty skid for the frame.
- **Lugs** (BTH-1-2020 3-3.3), each divided by Nd = 2.0 (category A) or 3.0 (category B):
  - Pt = Cr Fu 2t beff/(1.20 Nd), with Cr = 1 − 0.275√(1 − Dp²/Dh²) and beff ≤ 4t, be, and 0.6 be (Fu/Fy)√(Dh/be);
  - single plane Pb = Cr Fu/(1.20 Nd)[1.13(R − Dh/2) + 0.92 be/(1 + be/Dh)] t;
  - double plane Pv = 0.70 Fu Av/(1.20 Nd), with Av = 2[a + Dp/2 (1 − cos φ)] t and φ = 55 Dp/Dh deg;
  - bearing 1.25 Fy Dp t/Nd.
- **Slings**: T = V/sin(angle). A 4-leg bridle without an equalizer is designed with 2 legs carrying the load.

## 7. Dynamics and fatigue

- f = (1/2π)√(g/δ) = 3.13/√δ(in) Hz for a mass on a support with static deflection δ.
- Beams: (βL)² = π² (simple), 3.516 (cantilever). Rayleigh tip/centre masses add 0.2357 / 0.4857 / 0.3714 of the
  member mass.
- Separation: keep f_n outside 0.8 to 1.2 of 1× and 2× running speed and of vane pass (ACI 351.3R practice).
- Unbalance: F = m e ω², with e from balance grade G (G6.3 for pumps): e = G/ω.
- Amplification: 1/√((1 − r²)² + (2ζr)²).
- Fatigue (App. 3): FSR = 1000 (Cf/n)^0.333 ≥ FTH (ksi). Cf / FTH: A 25/24, B 12/16, B' 6.1/12, C 4.4/10,
  D 2.2/7, E 1.1/4.5, E' 0.39/2.6. Required above 20,000 cycles; valid to 300 F; mild environments only.

## 8. Lessons carried from an earlier skid job's frame calc

- Fork bearing: which members touch the tines depends on their underside heights. The analyst decides the contact
  set from the model's elevations, and the solver then finds which of them actually bear (FC-32).
- Torsion and grid action matter. Without torsional stiffness a frame on one tine line has a zero-stiffness mode
  (FC-29). The frame solver here always carries GJ.
- All feet are primary on a four-station base. Run the loose-foot and loose-row cases (support_reactions,
  frame_check with a foot removed).
- The earlier calc used a single 0.6 Fy elastic allowable (FC-03). This suite replaces it with the AISC 370 limit
  states, which credit the plastic modulus of compact tubes and penalize slender ones.
