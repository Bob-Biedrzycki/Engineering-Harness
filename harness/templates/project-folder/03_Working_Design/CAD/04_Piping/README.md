# 04_Piping

Holds drawings, exports and notes **derived from the model** for piping (routes, spools, supports, connection details): for example a subassembly
drawing, a fabricated-part DXF, or a spool sheet. It never holds model source. The one home of the model
source (build123d) is `CAD/01_Master_Assembly/<MODEL-ID>/` (Bob, chat, 2026-10-26).

Kept in every project so filing stays the same; the folder may be removed later at Bob's word. To remove it,
delete it from `harness/templates/project-folder/` as well, so `harness/checks/project_layout.py` stops
expecting it.
