"""materials - the company-wide construction materials list (harness/design-rules/materials.yaml; MAT-LIB-001,
MAT-FORM-001, MAT-LOOK-001), read in one place for the models, the checks and the render scripts.

    resolve(text, form=None)   the list entry for a material as a list or model writes it ("ASTM A106 Gr B"),
                               or None when the list does not have it
    get(key)                   the entry by its key ("cs-pipe")
    may_bend(material)         True only when the entry says make.bend: allowed (MAT-FORM-001)
    turn(material)             how a run of it changes direction: "fitting", "none" or "bend"
    fitting_material(pipe, how)  the material of a fitting on that pipe ("butt_weld", "forged", "flange", "ferrule")
    look(material, finish="")  its surface {base_color, metallic, roughness, ...}; the `unknown` look when the
                               material is not on the list (MAT-LOOK-001)
    audit(records)             findings for bodies given as {"id", "kind", "material"}: a material not on the list,
                               or a bend in a material that is not bent. Reports, never blocks.
    problems()                 faults in the YAML itself (the tests run this)

Needs PyYAML only, so it runs in both venvs and under Blender's Python when PyYAML is there; render scripts that run
without it take the looks from dump_looks() written to JSON by the caller.
"""
from __future__ import annotations

import re
from functools import lru_cache

import repo_paths as rp

FILE = rp.HARNESS_DESIGN_RULES / "materials.yaml"
UNKNOWN_LOOK = "unknown"
BENT_KINDS = ("bend",)          # body kinds that are a bent piece of stock (an elbow is a fitting, not a bend)
_REQUIRED = ("key", "name", "spec", "family", "form", "used_for", "match", "make", "look")
_TURNS = ("fitting", "none", "bend")


@lru_cache(maxsize=1)
def load() -> dict:
    import yaml
    return yaml.safe_load(FILE.read_text(encoding="utf-8")) or {}


def entries() -> list[dict]:
    return list(load().get("materials") or [])


def get(key: str) -> dict:
    for e in entries():
        if e.get("key") == key:
            return e
    raise KeyError(f"material '{key}' is not in {FILE.name}")


def resolve(text, form: str | None = None) -> dict | None:
    """The entry for a material: a key, an entry already, or the text a list writes. form (an entry's `form`,
    e.g. "pipe") picks between entries that both match."""
    if isinstance(text, dict):
        return text
    s = str(text or "").strip()
    if not s or s.lower() == "unknown":
        return None
    hits = [e for e in entries() if e.get("key") == s or any(re.search(p, s) for p in e.get("match") or [])]
    if form:
        for e in hits:
            if e.get("form") == form:
                return e
    return hits[0] if hits else None


def may_bend(material) -> bool:
    e = resolve(material)
    return bool(e) and str((e.get("make") or {}).get("bend", "no")).lower() == "allowed"


def turn(material) -> str | None:
    e = resolve(material)
    return (e.get("make") or {}).get("turn") if e else None


def fitting_material(pipe_material, how: str) -> str:
    """The material of a fitting on a run of pipe_material, by how the fitting is made: "butt_weld" (elbow, tee,
    reducer, cap), "forged" (olet, threaded or socket weld fitting), "flange", "ferrule". "" when the list gives none
    (the pipe is not on the list, or it takes no fitting of that kind)."""
    e = resolve(pipe_material, form="pipe") or resolve(pipe_material)
    return str(((e or {}).get("make") or {}).get("fitting_materials", {}).get(how, ""))


def look_name(material, finish: str = "") -> str:
    e = resolve(material)
    if e is None:
        return UNKNOWN_LOOK
    return (e.get("finishes") or {}).get(finish) or e["look"]


def look(material, finish: str = "") -> dict:
    """The surface of a material (and finish, when the body names one). A copy: callers may change it."""
    return dict(load()["looks"][look_name(material, finish)])


def dump_looks() -> dict:
    """{"looks": {...}, "materials": [{key, match, form, look, finishes}]}: what a render script that cannot import
    this module needs, for the caller to write as JSON."""
    return {"looks": {k: dict(v) for k, v in load()["looks"].items()},
            "materials": [{k: e.get(k) for k in ("key", "match", "form", "look", "finishes")} for e in entries()]}


def audit(records) -> list[dict]:
    """Findings for modelled bodies. Each record: {"id", "kind", "material"} (kind as the model names it: tube,
    elbow, tee, frame, plate, bend ...). A finding is {"id", "rule", "finding"}."""
    out = []
    for r in records:
        e = resolve(r.get("material"))
        if e is None:
            out.append({"id": r.get("id", ""), "rule": "MAT-LIB-001",
                        "finding": f"material '{r.get('material') or ''}' is not on the construction materials list"})
            continue
        if r.get("kind") in BENT_KINDS and not may_bend(e):
            out.append({"id": r.get("id", ""), "rule": "MAT-FORM-001",
                        "finding": f"{e['name']} ({e['spec']}) is not bent: "
                                   f"{(e['make'].get('fittings') or 'use a fitting or a welded joint')}"})
    return out


def model_records(m) -> list[dict]:
    """The fabricated bodies of a routed model (skidlib Model) as audit() records: every pipe piece, and every
    frame member, plate and support, and every loose pipe fitting that is not a library part. Purchased parts
    are left out (MAT-LIB-001)."""
    import model_read as MR     # a model of either skidlib generation (harness/lib/model_read.py)
    spools = {sp.sid: sp for sp in m.spools}
    out = [{"id": pc.pid, "kind": pc.kind, "material": MR.piece_material(pc, spools)} for pc in MR.pieces(m)]
    for it in m.items.values():
        if it.kind in ("frame", "plate", "support") and (it.prims or it.member):
            out.append({"id": it.key, "kind": it.kind, "material": (it.member or {}).get("material", "")})
        elif it.kind == "fitting" and not MR.comp_id(it):      # a loose pipe fitting (reducer, cap, olet)
            out.append({"id": it.key, "kind": it.kind, "material": (getattr(it, "bom", None) or {}).get("material", "")})
    return out


def problems() -> list[str]:
    """Faults in materials.yaml itself."""
    d, bad, seen = load(), [], set()
    looks = d.get("looks") or {}
    if UNKNOWN_LOOK not in looks:
        bad.append(f"looks: no '{UNKNOWN_LOOK}' look")
    for name, lk in looks.items():
        c = lk.get("base_color")
        if not (isinstance(c, list) and len(c) == 3 and all(isinstance(x, (int, float)) and 0 <= x <= 1 for x in c)):
            bad.append(f"looks[{name}].base_color: three numbers 0..1 expected")
        for k in ("metallic", "roughness"):
            if not (isinstance(lk.get(k), (int, float)) and 0 <= lk[k] <= 1):
                bad.append(f"looks[{name}].{k}: a number 0..1 expected")
    for e in d.get("materials") or []:
        key = e.get("key", "?")
        if key in seen:
            bad.append(f"{key}: listed twice")
        seen.add(key)
        bad += [f"{key}: missing '{k}'" for k in _REQUIRED if not e.get(k)]
        for p in e.get("match") or []:
            try:
                re.compile(p)
            except re.error as x:
                bad.append(f"{key}.match '{p}': bad pattern ({x})")
        mk = e.get("make") or {}
        if mk.get("turn") not in _TURNS:
            bad.append(f"{key}.make.turn: one of {_TURNS} expected, got {mk.get('turn')!r}")
        if str(mk.get("bend")).lower() not in ("no", "allowed"):
            bad.append(f"{key}.make.bend: 'no' or 'allowed' expected, got {mk.get('bend')!r}")
        if str(mk.get("bend")).lower() == "allowed" and not mk.get("bend_limits"):
            bad.append(f"{key}.make: bend allowed without bend_limits")
        if not mk.get("basis"):
            bad.append(f"{key}.make: no basis")
        for where, name in [("look", e.get("look"))] + [(f"finishes[{f}]", n) for f, n in (e.get("finishes") or {}).items()]:
            if name not in looks:
                bad.append(f"{key}.{where}: look {name!r} is not defined")
    return bad

if __name__ == "__main__":
    import json
    import sys
    if "--dump" in sys.argv[1:]:
        json.dump(dump_looks(), sys.stdout)
    else:
        bad = problems()
        print(f"materials: {'PASS' if not bad else 'FAIL'} - {len(entries())} materials, {len(load()['looks'])} looks"
              + "".join(f"\n  {b}" for b in bad))
        sys.exit(1 if bad else 0)
