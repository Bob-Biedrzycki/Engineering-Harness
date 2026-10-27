"""Fast PDF of a multi-sheet DXF, rendered by ezdxf + matplotlib (no AutoCAD Core Console).

For viewing copies only (P&ID fast edits; Bob, chat, 2026-10-11). A filed drawing's PDF is always exported
from its DWG by dwg-to-pdf.ps1 (TR-06); this script never writes into <project>/06_Issued_Revisions/Drawings/<DOC-ID>/.

The sheets sit side by side in model space, sheet k spanning x = k*pitch .. k*pitch + width (inches), as
model-to-pid.py draws them. One PDF page per sheet.

Runs in the cadgen venv (it has matplotlib; the repo venv harness/tools/venv does not):
    .\\harness\\tools\\venv-cadgen\\Scripts\\python.exe harness\\cad-lib\\dxf_pdf_fast.py <in.dxf> <out.pdf> --sheets 3
"""
from __future__ import annotations

import argparse
import sys

import ezdxf
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402
from ezdxf.addons.drawing import Frontend, RenderContext  # noqa: E402
from ezdxf.addons.drawing.config import BackgroundPolicy, ColorPolicy, Configuration  # noqa: E402
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("dxf")
    ap.add_argument("pdf")
    ap.add_argument("--sheets", type=int, default=3)
    ap.add_argument("--pitch", type=float, default=18.0, help="sheet spacing in model space, inches")
    ap.add_argument("--width", type=float, default=17.0)
    ap.add_argument("--height", type=float, default=11.0)
    a = ap.parse_args()

    doc = ezdxf.readfile(a.dxf)
    fig = plt.figure(figsize=(a.width, a.height))
    ax = fig.add_axes((0, 0, 1, 1))
    cfg = Configuration(background_policy=BackgroundPolicy.WHITE, color_policy=ColorPolicy.COLOR,
                        min_lineweight=0.1)
    Frontend(RenderContext(doc), MatplotlibBackend(ax), config=cfg).draw_layout(doc.modelspace(), finalize=True)
    fig.set_size_inches(a.width, a.height)  # finalize sizes the figure to all sheets; back to one page
    with PdfPages(a.pdf) as pdf:
        for k in range(a.sheets):
            ax.set_xlim(k * a.pitch, k * a.pitch + a.width)
            ax.set_ylim(0, a.height)
            ax.set_aspect("auto")  # page and sheet are both width x height, so 1:1 without a datalim fight
            ax.axis("off")
            pdf.savefig(fig)
    plt.close(fig)
    print(f"dxf_pdf_fast: {a.sheets} pages -> {a.pdf}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
