# Pipe and fitting dimensions (company-wide)

Company level since 2026-11-10 (MAT-DIM-001, harness/design-rules/materials.yaml; Bob, chat, 2026-11-10: "yes company
level."). Before that the tables were in a job's typical-models folder; the values and sources are unchanged.

`fitting-dims.csv`: standard butt-weld fitting, weld-neck flange and pipe dimensions, NPS 1 to 8 in, inches, for
the routing of steel pipe in any skid model (in place of the framework placeholders of a model library's line walker;
Linear CPM-157).
Written by the helper session on 2026-10-30, at the skid session's request; the helper session is its only writer,
and the library and the cad-design-engineer only read it. No value is calculated or estimated: each is as printed by the source named in its row's
`source_*` column. A value no source gave would be `unknown` (none are).

## Sources

| Code | Values | Standard | Where read (2026-10-30) |
|---|---|---|---|
| S-PIPE | pipe OD, Sch 40 and Sch 80 wall | ASME B36.10M | projectmaterials.com, "ASME pipe wall thickness charts" (Sch 40 & 80); OD also matches engineeringtoolbox.com ANSI steel pipe chart |
| S-EL90 | 90 deg long-radius elbow centre-to-end A | ASME B16.9 | texasflange.com, 90 deg long radius elbow; wermac.org dim_elbows_a (mm: 38, 48, 57, 76, 95, 114, 152, 190, 229, 305) |
| S-EL45 | 45 deg long-radius elbow centre-to-end B | ASME B16.9 | texasflange.com, 45 deg long radius elbow; wermac.org dim_elbows_a (mm: 22, 25, 29, 35, 44, 51, 64, 79, 95, 127) |
| S-TEE | straight tee centre-to-end run C and outlet M | ASME B16.9 | wermac.org dim_tees_eq, printed in mm (38, 48, 57, 64, 76, 86, 105, 124, 143, 178), converted to in at 2 places |
| S-WN150 | Class 150 weld-neck flange OD and length through hub Y | ASME B16.5 Table 8C (cited by the source) | apiint.com Class 150 weld neck; wermac.org weld neck B16.5 (Class 150) prints the same values |
| S-WN300 | Class 300 weld-neck flange OD and length through hub Y | ASME B16.5 Table 11C (cited by the source) | apiint.com Class 300 weld neck (one source only) |
| S-RED | concentric (and eccentric) reducer end-to-end H, by the large-end NPS (one H per large end, any small end) | ASME B16.9 | wermac.org dim_reducers, printed in mm (51, 51, 64, 76, 89, 89, 102, 127, 140, 152), converted to in at 2 places (one source only; added 2026-10-30) |
| S-CAP | cap length E (wall up to `cap_E_max_wall_in`) and E1 (thicker wall) | ASME B16.9 | wermac.org dim_caps, printed in mm as H / H(1) (H 38, 38, 38, 38, 38, 51, 64, 76, 89, 102; H(1) 38, 38, 38, 44, 51, 64, 76, 89, 102, 127; wall limit 4.57 ... 12.70 mm), converted to in at 2 places (one source only; added 2026-10-30) |
| S-WN150 S-WN300 (tf, X) | weld-neck flange minimum thickness tf and hub diameter at the base X, Class 150 and 300 | ASME B16.5 Table 8C / 11C (cited by the source) | the same apiint.com pages as S-WN150 / S-WN300; the page notes "Minimum flange thickness does not include the raised face thickness" (added 2026-10-30) |
| S-WOL-STD | `olet-dims.csv`: Weldolet, reducing, STD wall, height A | MSS SP-97 (Bonney Forge, cited by the source) | wermac.org dimensions_weldolet_reducing_std-wt (one source only) |
| S-TOL-3000 | `olet-dims.csv`: Thredolet Class 3000, height A | MSS SP-97 (Bonney Forge, cited by the source) | wermac.org dimensions_thredolet_size-on-size_class-3000 (one source only) |

`olet-dims.csv` holds the 1/2, 3/4 and 1 in tap outlets. Its `base_od_in` is `unknown`: neither page prints the olet
base diameter. Take it from the olet maker's catalogue before it sets a clearance.

URLs: https://www.blog.projectmaterials.com/pipes/pipe-tube-sizes/asme-pipe-wall-thickness-charts,
https://texasflange.com/butt-weld-fittings/elbow-long-radius/, https://texasflange.com/butt-weld-fittings/elbow-45-long-radius/,
https://wermac.org/fittings/dim_elbows_a.html, https://www.wermac.org/fittings/dim_tees_eq.html,
https://apiint.com/flange-dimensions/weld-neck-flange-dimensions/class-150-weld-neck/,
https://apiint.com/flange-dimensions/weld-neck-flange-dimensions/class-300-weld-neck/,
https://wermac.org/flanges/dimensions_weldneck_in_asme-b16-5.html, https://www.wermac.org/fittings/dim_reducers.html,
https://wermac.org/fittings/dimensions_weldolet_reducing_std-wt.html,
https://wermac.org/fittings/dimensions_thredolet_size-on-size_class-3000.html

## Notes for the modeller

- The 90 deg elbow is 1.5 x NPS centre-to-end (not 1.5 x OD). The straight tee is not a multiple of OD; take C and M from the row.
- Neither flange source says whether the 0.06 in raised face of Class 150 and 300 is inside Y. Confirm against the
  maker's flange drawing before a flange-to-flange length is fixed, and record which one you used.
- Rounding as printed: Class 150 NPS 1-1/4 OD is 4.62 here (apiint prints 4.63; 4-5/8 in); Class 300 NPS 1-1/2 OD is
  6.13 (6-1/8 in).
- These are secondary sources quoting the standards. Where a value sets a clearance or the envelope, the
  cad-design-engineer checks it against the standard or the fitting maker's catalogue.
