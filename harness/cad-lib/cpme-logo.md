# cpme-logo.dxf - provenance

`cpme-logo.dxf` holds one block, `CPME_LOGO_EMBEDDED` (7 HATCH entities on layer `P-ANNO-LOGO`), CPME's own
logo artwork. `cpme_titleblock.py` inserts it in the title block of every drawing the harness generates.

- **Source:** CPME standard sheet format (CPME's own logo artwork), block `CPME_LOGO_EMBEDDED`, unchanged.
- **This file sha256:** `46dd0693500b05068452681ae9023fc8297d170c609da9e0117e7bbaf4ea1f30` (538,440 bytes)
- **Copied on:** 2026-10-26, by ezdxf `Importer.import_block` into a new DXF (AC1032)
- **Decision:** Bob, chat, 2026-10-26: the logo is copied once, read only, into a harness asset (CPME practice)

The file is a fixed asset, not generated output: it is not rebuilt, and a new logo is a new file with its own note.
