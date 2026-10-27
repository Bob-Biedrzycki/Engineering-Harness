"""One DXF paper-space sheet to SVG text, with ezdxf's drawing add-on (white sheet, true colours).

Shared by <project>/03_Working_Design/CAD/06_Drawings/Generators/pid-relabel.py (--preview sheets) and the quoting portal's Plan Set hero
(<project>/03_Working_Design/CAD/09_Presentation/build_portal.py) (neither exists on this project yet). Reads the document only; writes nothing itself.

    import dxf_svg
    svg_text = dxf_svg.sheet_svg(ezdxf.readfile(path), "01-PID")
"""
from __future__ import annotations

from ezdxf.addons.drawing import Frontend, RenderContext, layout, svg
from ezdxf.addons.drawing.config import BackgroundPolicy, ColorPolicy, Configuration


def sheet_svg(doc, layout_name: str, width_in: float = 17.0, height_in: float = 11.0) -> str:
    """The named layout of `doc` as an SVG string, fitted to a width_in x height_in page with no margins."""
    cfg = Configuration(background_policy=BackgroundPolicy.WHITE, color_policy=ColorPolicy.COLOR)
    be = svg.SVGBackend()
    Frontend(RenderContext(doc), be, config=cfg).draw_layout(doc.layouts.get(layout_name), finalize=True)
    page = layout.Page(width_in * 25.4, height_in * 25.4, layout.Units.mm, margins=layout.Margins.all(0))
    return be.get_string(page, settings=layout.Settings(fit_page=True, output_coordinate_space=100_000))
