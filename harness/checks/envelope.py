"""envelope - shipped envelope of the project's skid vs <project>/01_Design_Basis/05_Standards_Specifications/Design_Rules/layout.yaml (TR-18).

Measures the overall bounding box of every body in the routed model (base
bottom to highest point, including valve actuators, instrument heads, lids and
lugs) and compares it with shipping_envelope design_max_length_in /
design_max_width_in / design_max_height_in (the model's params envelope). If the
generated STEP exists and build123d is importable, its bounding box is
measured too and reported beside the model value; --no-step skips it (model_iterate.py --fast).

A job-level model (--model-id, harness/lib/repo_paths.py; Linear CPM-155) has no project level: its limits are read
from the job's rule file, job/design-rules/layout.yaml shipping_envelope (rp.DESIGN_RULES for that model), not from
the model's params, and the line names the file they came from.

Exit-code contract (harness/checks/README.md): 0 = PASS, 1 = FAIL, 3 = ERROR (could not run). First line = summary.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists()) / "harness" / "lib"))
import repo_paths as rp  # noqa: E402
import rule_scope  # noqa: E402

REPO = rp.REPO
if rp.HAS_MODEL:
    sys.path.insert(0, str(rp.SKID_MODEL))
    STEP = rp.SKID_BUILD / f"{rp.MODEL_DOC_ID}.step"


def rule_limits(rules_dir: Path) -> dict:
    """{L, W, H, source} from <rules_dir>/layout.yaml shipping_envelope design_max_length_in / width / height."""
    f = rules_dir / "layout.yaml"
    se = (rule_scope.read_yaml(f) or {}).get("shipping_envelope") or {}
    keys = {"L": "design_max_length_in", "W": "design_max_width_in", "H": "design_max_height_in"}
    src = rp.rel(f) if rp.REPO in f.resolve().parents else str(f)
    missing = [v for v in keys.values() if rule_scope.is_unknown(se.get(v))]
    if missing:
        raise ValueError(f"{src} shipping_envelope lacks {', '.join(missing)}")
    return {**{k: float(se[v]) for k, v in keys.items()}, "source": src}


def main() -> int:
    if rp.skip_no_model("envelope"):
        return 0
    missing = rule_scope.model_missing()
    if missing:
        print(f"envelope: PASS - not checked: {missing}; nothing measured")
        return 0
    try:
        from skidlib import layout, reports
        m = layout.build()
    except Exception as e:  # noqa: BLE001
        print(f"envelope: ERROR - model did not build: {type(e).__name__}: {e}")
        return 3
    env = reports.envelope(m)
    src = ""
    if rp.MODEL_LEVEL == "job":
        try:
            lim = rule_limits(rp.DESIGN_RULES)
        except Exception as e:  # noqa: BLE001
            print(f"envelope: ERROR - shipping envelope not read: {type(e).__name__}: {e}")
            return 3
        src = f" ({lim['source']} shipping_envelope)"
    else:
        lim = m.params["envelope"]
    over = [k for k in ("L", "W", "H") if env[k] > lim[k] + 1e-6]
    # adjustable feet: the height must also fit with every foot run up to its upper limit (when the model has them)
    if "H_raised" in env and env["H_raised"] > lim["H"] + 1e-6:
        over.append("H (feet raised)")
    no_step = "--no-step" in sys.argv[1:]
    step_txt = "STEP not measured (--no-step)" if no_step else "STEP not generated yet"
    if STEP.exists() and not no_step:
        try:
            import build123d as bd
            bb = bd.import_step(str(STEP)).bounding_box()
            s = (bb.size.X / 25.4, bb.size.Y / 25.4, bb.max.Z / 25.4)
            step_txt = f"STEP bbox {s[0]:.1f} x {s[1]:.1f} x {s[2]:.1f} in"
            for k, v in zip(("L", "W", "H"), s):
                if v > lim[k] + 1e-6 and k not in over:
                    over.append(k + " (STEP)")
        except Exception as e:  # noqa: BLE001
            step_txt = f"STEP bbox not measured ({type(e).__name__})"
    raised = f" ({env['H_raised']:.1f} H with the feet raised)" if "H_raised" in env else ""
    msg = (f"{env['L']:.1f} L x {env['W']:.1f} W x {env['H']:.1f} H in{raised} vs {lim['L']:.0f} x {lim['W']:.0f} x "
           f"{lim['H']:.0f}{src}; highest {env['highest'][0]} at {env['highest'][1]:.1f} in; {step_txt}")
    if over:
        print(f"envelope: FAIL - over on {', '.join(over)}: {msg}")
        return 1
    print(f"envelope: PASS - {msg}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
