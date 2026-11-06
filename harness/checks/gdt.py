"""gdt - GD&T tolerance records of fabrication drawings vs harness/design-rules/tolerancing.yaml.

Every fabrication drawing has a tolerance record beside its generator, <DOC-ID>.tol.yaml (GDT-REC-001):

    document_id: <DOC-ID>
    kind: fabrication
    datums:                       # letter: the real feature that carries it (GDT-DAT-001 / GDT-DAT-002)
      A: "bottom plane of base rails FM-001, FM-002"
    general_tolerances: job       # "job" = the job's GDT-STD-001 values (the only choice today)
    fcf:                          # one entry per feature control frame (GDT-FCF-001)
      - feature: "pump pad PL-004 top face"
        control: flatness         # see CONTROLS below
        value_in: 0.010
        modifier: null            # MMC / LMC / null; position of clearance holes uses MMC
        datums: []                # form controls take none; position needs at least one
        reason: "pump base soft foot (CHAIN-PUMP-BASE)"
        process: machined_after_welding_flatness_in   # optional: a key of the job's process_capability
        fastener: {type: floating, hole_mmc_in: 0.5625, fastener_mmc_in: 0.500}   # optional, position only

What it reports (a finding never blocks: exit 1 is a warning on the PR, harness/checks/README.md):
- a control CPME does not use (concentricity, symmetry; runout on an as-welded part), or not a Y14.5 control;
- a datum referenced that the record does not define; a form control with datums; position with none;
- a missing value, reason or feature;
- a value tighter than the job's process capability for the named process (GDT-CAP-001);
- a position value larger than the fastener formula allows (GDT-FAST-001);
- the job's general tolerance values still unknown, once any fabrication record exists (they print TBD).
With no records yet it passes and says how many job values are still unknown.

Exit-code contract (harness/checks/README.md): 0 = PASS, 1 = FAIL (findings), 3 = ERROR. First line = summary.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists()) / "harness" / "lib"))
import repo_paths as rp  # noqa: E402

FORM = {"flatness", "straightness", "circularity", "cylindricity"}
ORIENT = {"parallelism", "perpendicularity", "angularity"}
LOCATE = {"position"}
PROFILE = {"profile_surface", "profile_line"}
RUNOUT = {"circular_runout", "total_runout"}
NOT_USED = {"concentricity": "removed from ASME Y14.5-2018; use position or profile (GDT-FCF-001)",
            "symmetry": "removed from ASME Y14.5-2018; use position or profile (GDT-FCF-001)"}
CONTROLS = FORM | ORIENT | LOCATE | PROFILE | RUNOUT
SKIP_PARTS = {"_work", "Exports", "tools", ".git", "__pycache__", "node_modules"}


def _yaml(p: Path) -> dict:
    import yaml
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def _unknown(v) -> bool:
    return v is None or (isinstance(v, str) and v.strip().lower() in ("", "unknown", "tbd"))


def job_values(job_rules: Path) -> dict:
    """{'general': {...}, 'capability': {...}} from job/design-rules/tolerancing.yaml (empty if absent)."""
    f = job_rules / "tolerancing.yaml"
    if not f.is_file():
        return {"general": {}, "capability": {}}
    d = _yaml(f)
    return {"general": (d.get("GDT-STD-001") or {}).get("general_tolerances") or {},
            "capability": (d.get("GDT-CAP-001") or {}).get("process_capability") or {}}


def check_record(rec: dict, capability: dict, name: str = "record") -> list[str]:
    """Findings for one tolerance record (pure: unit-tested in harness/tests/test_gdt.py)."""
    out: list[str] = []
    doc = rec.get("document_id") or name
    if rec.get("kind") != "fabrication":
        out.append(f"{doc}: kind {rec.get('kind')!r}; a tolerance record is for a fabrication drawing (GDT-STD-001)")
    datums = rec.get("datums") or {}
    for letter, feat in datums.items():
        if _unknown(feat):
            out.append(f"{doc}: datum {letter} names no feature (GDT-DAT-002)")
    for i, f in enumerate(rec.get("fcf") or [], 1):
        where = f"{doc} fcf {i} ({f.get('feature') or 'no feature'})"
        c = str(f.get("control") or "").strip().lower()
        if not f.get("feature"):
            out.append(f"{where}: no feature named")
        if c in NOT_USED:
            out.append(f"{where}: {c} - {NOT_USED[c]}")
            continue
        if c not in CONTROLS:
            out.append(f"{where}: control {c!r} is not one of {sorted(CONTROLS)}")
            continue
        if c in RUNOUT and not f.get("machined"):
            out.append(f"{where}: runout only on a machined feature (GDT-FCF-001); set machined: true or use position/profile")
        refs = list(f.get("datums") or [])
        for r in refs:
            if r not in datums:
                out.append(f"{where}: datum {r} is not defined on the drawing (GDT-FCF-001)")
        if c in FORM and refs:
            out.append(f"{where}: {c} is a form control and takes no datums")
        if (c in LOCATE or c in ORIENT or c in RUNOUT) and not refs:
            out.append(f"{where}: {c} needs at least one datum")
        v = f.get("value_in")
        if _unknown(v):
            out.append(f"{where}: no value_in")
            v = None
        else:
            try:
                v = float(v)
                if v <= 0:
                    out.append(f"{where}: value_in {v} must be > 0")
            except (TypeError, ValueError):
                out.append(f"{where}: value_in {v!r} is not a number")
                v = None
        if _unknown(f.get("reason")):
            out.append(f"{where}: no reason recorded (GDT-FCF-001: tolerance only what the function needs)")
        proc = f.get("process")
        if proc and v is not None:
            if proc not in capability:
                out.append(f"{where}: process {proc!r} is not in the job's process_capability (GDT-CAP-001)")
            elif not _unknown(capability[proc]) and v < float(capability[proc]):
                out.append(f"{where}: {v} in is tighter than the shop's {proc} {capability[proc]} in (GDT-CAP-001)")
        fast = f.get("fastener")
        if fast and c == "position" and v is not None:
            try:
                h, fm = float(fast["hole_mmc_in"]), float(fast["fastener_mmc_in"])
                allowed = h - fm   # floating: T = H - F per part; fixed: T1 + T2 = H - F
                if str(fast.get("type", "floating")).lower() == "fixed" and fast.get("mating_value_in") is not None:
                    allowed = h - fm - float(fast["mating_value_in"])
                if v > allowed + 1e-9:
                    out.append(f"{where}: position {v} in exceeds the fastener formula {allowed:.4f} in (GDT-FAST-001)")
                if c == "position" and str(f.get("modifier") or "").upper() != "MMC":
                    out.append(f"{where}: clearance-hole position is stated at MMC (GDT-FCF-001)")
            except (KeyError, TypeError, ValueError):
                out.append(f"{where}: fastener needs hole_mmc_in and fastener_mmc_in (GDT-FAST-001)")
    return out


def find_records(root: Path) -> list[Path]:
    base = root / "job"
    if not base.is_dir():
        return []
    return sorted(p for p in base.rglob("*.tol.yaml") if not SKIP_PARTS.intersection(p.parts))


def main() -> int:
    if rp.skip_no_project("gdt"):   # a new job with no project yet: nothing to check (harness/tests/test_job_new.py)
        return 0
    try:
        if not (rp.HARNESS_DESIGN_RULES / "tolerancing.yaml").is_file():
            print("gdt: ERROR - harness/design-rules/tolerancing.yaml not found")
            return 3
        jv = job_values(rp.JOB_DESIGN_RULES) if hasattr(rp, "JOB_DESIGN_RULES") else {"general": {}, "capability": {}}
        unknown_gen = [k for k, v in jv["general"].items() if _unknown(v)]
        unknown_cap = [k for k, v in jv["capability"].items() if _unknown(v)]
        records = find_records(rp.REPO)
        findings: list[str] = []
        for p in records:
            try:
                findings += check_record(_yaml(p), jv["capability"], p.stem)
            except Exception as e:  # noqa: BLE001
                findings.append(f"{rp.rel(p)}: unreadable ({type(e).__name__}: {e})")
        if records and unknown_gen:
            findings.append(f"job general tolerances unknown ({', '.join(unknown_gen)}); fabrication drawings print TBD "
                            "(GDT-CAP-001, job/design-rules/tolerancing.yaml)")
    except Exception as e:  # noqa: BLE001
        print(f"gdt: ERROR - {type(e).__name__}: {e}")
        return 3
    note = f"{len(unknown_gen)} general tolerance and {len(unknown_cap)} shop capability values unknown"
    if findings:
        print(f"gdt: FAIL - {len(findings)} finding(s) in {len(records)} tolerance record(s); {note}")
        for f in findings:
            print(f"  - {f}")
        return 1
    print(f"gdt: PASS - {len(records)} tolerance record(s) checked; {note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
