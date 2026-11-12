"""accepted_findings - a project's findings accepted by decision, read by the checks.

CLAUDE.md: "Checks report; they do not block design progress. Known findings are accepted with their record." A
finding Bob has accepted is printed with its record and not failed. The records are the project's, so they live in
the project, not in a check (Bob, chat, 2026-11-10: accepted findings go in a per-project file the master's checks
read; the harness is the same in every job and carries no project's records):

    <project>/01_Design_Basis/06_Assumptions_Open_Items/accepted-findings.yaml

Every record quotes Bob (or names the DEC / Q) and says what was accepted. A missing file, or a job-level model
(--model-id), means nothing is accepted. The file (every section optional):

    interference:                 # harness/checks/interference.py
      - between: [TK-101, TK-102]            # the two owners whose bodies touch
        record: "tanks butt; corner lugs trimmed to fit (DEC-nnnn)"
    pipe_supports:                # harness/checks/pipe_supports.py (STR-PS-002)
      zone:                                   # in-line components carried through other supports
        components: [FT-101, CV-103]
        record: "..."
      on_nozzle: "..."                        # a valve clamped straight on an equipment nozzle
      tie_in: "..."                           # a face that looks onto a tie-in
      named: {STR-101: "..."}                 # component tag -> record
      elbow: {L-140-SP01.pc05: "..."}         # elbow piece id -> record
      pump: {"P-101 discharge": "..."}        # pump connection label -> record
      clearance: {"L-100 supply tail support": "..."}   # start of the support member's role -> record
    sanitary_routing:             # harness/checks/sanitary_routing.py (SAN-SLOPE-001, SAN-DL-001)
      - object: "L-100 riser drain tee"                 # the routing row's object
        value: "L 4.75 in, D 1.870 in, L/D 2.54"        # its exact measured value; a changed value fails again
        record: "..."

Stdlib plus PyYAML (the repo venv). A file that cannot be read sets FAULT; a check that finds FAULT prints
"<check>: ERROR - ..." and exits 3 instead of quietly accepting nothing or everything.
"""
from __future__ import annotations

from pathlib import Path

import repo_paths as rp

NAME = "accepted-findings.yaml"
PS_MAPS = ("named", "elbow", "pump", "clearance")
PS_TEXTS = ("on_nozzle", "tie_in")
FAULT = ""      # why the project's file could not be used ("" = fine, or no file)


def path() -> Path | None:
    """The active project's file, or None (no project yet, or a job-level model: nothing is accepted)."""
    if not rp.HAS_PROJECT or rp.MODEL_LEVEL != "project":
        return None
    return rp.OPEN_ITEMS / NAME


def problems(d) -> list[str]:
    """What is wrong with a loaded file ([] = fine)."""
    if d is None:
        return []
    if not isinstance(d, dict):
        return ["the file is not a mapping of sections"]
    out = [f"unknown section {k!r} (sections: interference, pipe_supports, sanitary_routing)" for k in d
           if k not in ("interference", "pipe_supports", "sanitary_routing")]
    sr = d.get("sanitary_routing") or []
    if not isinstance(sr, list):
        out.append("sanitary_routing is not a list of entries")
        sr = []
    for i, e in enumerate(sr):
        for k in ("object", "value", "record"):
            if not (isinstance(e, dict) and str(e.get(k) or "").strip()):
                out.append(f"sanitary_routing entry {i + 1}: no {k}")
    for i, e in enumerate(d.get("interference") or []):
        b = e.get("between") if isinstance(e, dict) else None
        if not (isinstance(b, list) and len(b) == 2 and all(isinstance(x, str) and x.strip() for x in b)):
            out.append(f"interference entry {i + 1}: `between` is not two owner names")
        if not (isinstance(e, dict) and str(e.get("record") or "").strip()):
            out.append(f"interference entry {i + 1}: no record")
    ps = d.get("pipe_supports") or {}
    if not isinstance(ps, dict):
        return out + ["pipe_supports is not a mapping"]
    out += [f"pipe_supports: unknown key {k!r}" for k in ps if k not in ("zone", *PS_TEXTS, *PS_MAPS)]
    z = ps.get("zone")
    if z is not None and not (isinstance(z, dict) and isinstance(z.get("components"), list)
                              and str(z.get("record") or "").strip()):
        out.append("pipe_supports zone: needs `components` (a list) and a `record`")
    for k in PS_TEXTS:
        if ps.get(k) is not None and not str(ps[k]).strip():
            out.append(f"pipe_supports {k}: empty record")
    for k in PS_MAPS:
        m = ps.get(k)
        if m is None:
            continue
        if not isinstance(m, dict):
            out.append(f"pipe_supports {k}: not a mapping of name -> record")
        else:
            out += [f"pipe_supports {k} {n!r}: no record" for n, r in m.items() if not str(r or "").strip()]
    return out


def load(p: Path | None = None) -> dict:
    """The file as a dict ({} when there is none). Raises ValueError with the reason when it cannot be used."""
    p = path() if p is None else p
    if p is None or not Path(p).is_file():
        return {}
    try:
        import yaml
        d = yaml.safe_load(Path(p).read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001  (unreadable, not YAML, or PyYAML missing)
        raise ValueError(f"{Path(p).name} could not be read: {type(e).__name__}: {e}") from e
    bad = problems(d)
    if bad:
        raise ValueError(f"{Path(p).name}: {bad[0]}" + (f" (and {len(bad) - 1} more)" if len(bad) > 1 else ""))
    return d or {}


def interference_pairs(d: dict | None = None) -> dict[frozenset, str]:
    """frozenset({owner_a, owner_b}) -> record, as harness/checks/interference.py ACCEPTED."""
    d = _project() if d is None else d
    return {frozenset(x.strip() for x in e["between"]): str(e["record"]).strip() for e in d.get("interference") or []}


def pipe_supports(d: dict | None = None) -> dict:
    """The seven accept records of harness/checks/pipe_supports.py: zone ({"comps": set, "why": str}), on_nozzle and
    tie_in (str or None), named, elbow, pump, clearance (dicts name -> record)."""
    d = _project() if d is None else d
    ps = d.get("pipe_supports") or {}
    z = ps.get("zone") or {}
    out = {"zone": {"comps": {str(c).strip() for c in z.get("components") or []}, "why": str(z.get("record") or "").strip()}}
    for k in PS_TEXTS:
        out[k] = str(ps[k]).strip() if ps.get(k) else None
    for k in PS_MAPS:
        out[k] = {str(n): str(r).strip() for n, r in (ps.get(k) or {}).items()}
    return out


def sanitary_routing(d: dict | None = None) -> dict[tuple[str, str], str]:
    """(routing row object, exact measured value) -> record, for harness/checks/sanitary_routing.py."""
    d = _project() if d is None else d
    return {(str(e["object"]).strip(), str(e["value"]).strip()): str(e["record"]).strip()
            for e in d.get("sanitary_routing") or []}


def _project() -> dict:
    """The active project's file, {} and FAULT set when it cannot be used."""
    global FAULT
    try:
        FAULT = ""
        return load()
    except ValueError as e:
        FAULT = str(e)
        return {}
