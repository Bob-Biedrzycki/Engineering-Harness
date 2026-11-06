"""Models that combine analysis and member strength: section_properties, member_check, beam, frame_check.

Each model takes a plain dict of inputs (the CLI reads it from JSON or YAML) and returns a core.Calc.
"""
from __future__ import annotations

import math

from . import beams as B
from . import frame as FR
from . import loads as LD
from . import materials as MT
from . import members as MB
from . import sections as SC
from .core import Calc, InputError, need

REF_370 = "ANSI/AISC 370-21, Specification for Structural Stainless Steel Buildings"
REF_360 = "ANSI/AISC 360-22, Specification for Structural Steel Buildings"
REF_ASCE7 = "ASCE/SEI 7-22, Minimum Design Loads, Chapter 2 load combinations"

DEFLECTION_LIMITS = {
    # serviceability limits used as defaults (each one an ASSUMPTION when used); source of the practice
    "beam_equipment": (360, "L/360: beams supporting equipment and piping (common practice; AISC Design Guide 3 "
                            "and IBC Table 1604.3 floor-member live-load limit)"),
    "beam_general": (240, "L/240: general frame members (IBC Table 1604.3 total-load limit for floors)"),
    "cantilever": (180, "2L/360 = L/180 for cantilevers (twice the span-limit practice)"),
    "pump_base": (1000, "L/1000 under the pump: alignment-sensitive base (practice; check the pump maker's limit)"),
}


def _mat(inputs, calc, key="material"):
    m = MT.get(inputs.get(key, "A554-304"), inputs.get("temperature_F"))
    if key not in inputs:
        calc.assume(f"{key} = A554-304 (default frame material)")
    if m.temperature_F > 100:
        calc.warn(f"properties reduced to {m.temperature_F:g} F with AISC 370 App. 4 retention factors "
                  "(fire-design data used as the published elevated-temperature properties)")
    calc.references.append(m.source)
    return m


def _method(inputs, calc):
    m = inputs.get("method")
    if m is None:
        calc.assume("method = ASD (allowable strength design; loads unfactored in ASD combinations)")
        m = "ASD"
    if m not in ("ASD", "LRFD"):
        raise InputError("method must be ASD or LRFD")
    inputs["method"] = m
    return m


# ================================================================ section_properties
def section_properties(inputs: dict) -> Calc:
    """WHEN: you need A, I, S, Z, J, r and slenderness of a tube, bar, angle, channel or I-shape."""
    c = Calc("section_properties", "Section properties")
    sec = SC.from_spec(inputs.get("section") or _need_dict(inputs, "section"))
    mat = _mat(inputs, c)
    c.inputs = inputs
    for k, u in (("A", "in2"), ("Iz", "in4"), ("Iy", "in4"), ("Sz", "in3"), ("Sy", "in3"), ("Zz", "in3"),
                 ("Zy", "in3"), ("J", "in4"), ("C", "in3")):
        c.r(k, getattr(sec, k), u)
    c.r("rz", sec.rz, "in")
    c.r("ry", sec.ry, "in")
    c.r("t_design", sec.t, "in")
    c.r("weight", sec.A * mat.density * 12, "lb/ft")
    cl = MB.classify(sec, mat)
    c.tables["classification"] = {"columns": ["item", "value"], "rows": [[k, str(v)] for k, v in cl.items()]}
    for k, v in sec.elements.items():
        c.r(k, v)
    c.method = ("Closed-form properties of the rounded-corner tube (outside radius 2 t_design unless given), "
                "design wall t_design = t_factor x nominal (AISC 370 B4.2b). J by Bredt for closed sections.")
    c.references.append(REF_370 + " B4")
    return c


def _need_dict(inputs, name):
    if name not in inputs:
        raise InputError(f"required input '{name}' is missing")
    return inputs[name]


# ================================================================ member_check
def _capacities(sec, mat, method, Lc_z, Lc_y, Lb, Cb, Lv, L):
    Pt, dt = MB.tension(sec, mat, method)
    Pc, dc = MB.compression(sec, mat, Lc_z, Lc_y, method)
    Mcz, dmz = MB.flexure(sec, mat, "z", method, Lb, Cb)
    Mcy, dmy = MB.flexure(sec, mat, "y", method, Lb, Cb)
    Vcy, dvy = MB.shear(sec, mat, "y", method, Lv)
    Vcz, dvz = MB.shear(sec, mat, "z", method, Lv)
    Tc, dtc = MB.torsion(sec, mat, method, L)
    return {"Pt": (Pt, dt), "Pc": (Pc, dc), "Mcz": (Mcz, dmz), "Mcy": (Mcy, dmy), "Vcy": (Vcy, dvy),
            "Vcz": (Vcz, dvz), "Tc": (Tc, dtc)}


def _station_ratio(st, cap):
    N = st["N"]
    Pc = cap["Pt"][0] if N >= 0 else cap["Pc"][0]
    Vr = math.hypot(st["Vy"], st["Vz"])
    Vc = min(cap["Vcy"][0], cap["Vcz"][0])
    r, eq, parts = MB.interaction(N, Pc, st["Mz"], cap["Mcz"][0], st["My"], cap["Mcy"][0], Vr, Vc, st["T"], cap["Tc"][0])
    rv = max(abs(st["Vy"]) / cap["Vcy"][0], abs(st["Vz"]) / cap["Vcz"][0])
    rt = abs(st["T"]) / cap["Tc"][0]
    return r, eq, rv, rt, parts


def member_check(inputs: dict) -> Calc:
    """WHEN: you know the forces in one member (from a hand calc or another model) and need its AISC check.

    inputs: section, material, method, L (in), K_z, K_y (or Lc_z, Lc_y), Lb, Cb, and the required forces
    P (lb, + tension / - compression), Mz, My (lb-in), Vy, Vz (lb), T (lb-in)."""
    c = Calc("member_check", "Member strength check (AISC 370 / 360)")
    c.inputs = inputs
    sec = SC.from_spec(_need_dict(inputs, "section"))
    mat = _mat(inputs, c)
    method = _method(inputs, c)
    L = need(inputs, "L", lo=0.0)
    Kz = c.default(inputs, "K_z", 1.0, "pinned-pinned effective length factor; set from the end restraint")
    Ky = c.default(inputs, "K_y", 1.0, "pinned-pinned effective length factor; set from the end restraint")
    Lc_z = float(inputs.get("Lc_z", Kz * L))
    Lc_y = float(inputs.get("Lc_y", Ky * L))
    Lb = float(inputs.get("Lb", L))
    Cb = float(inputs.get("Cb", 1.0))
    st = {k: float(inputs.get(k, 0.0)) for k in ("P", "Mz", "My", "Vy", "Vz", "T")}
    st["N"] = st.pop("P")
    cap = _capacities(sec, mat, method, Lc_z, Lc_y, Lb, Cb, inputs.get("Lv", L / 2), L)
    for k, (v, d) in cap.items():
        unit = "lb" if k.startswith(("P", "V")) else "lb-in"
        c.r(k, v, unit)
        c.tables[f"detail {k}"] = {"columns": ["item", "value"], "rows": [[a, _s(b)] for a, b in d.items()]}
        for key in ("note", "approximation"):
            if key in d:
                c.warn(f"{k}: {d[key]}")
    r, eq, rv, rt, parts = _station_ratio(st, cap)
    clause = REF_370.split(",")[0] if mat.stainless else REF_360.split(",")[0]
    c.ratio("combined axial + flexure (+ torsion)", r, 1.0, f"{eq}: {', '.join(f'{k} {v:.3f}' for k, v in parts.items())}",
            f"{clause} {eq}")
    c.ratio("shear", rv, 1.0, f"max(Vy/Vcy, Vz/Vcz) = {rv:.3f}", f"{clause} G")
    c.ratio("torsion", rt, 1.0, f"T/Tc = {rt:.3f}", f"{clause} G8 / H3")
    c.references += [REF_370 if mat.stainless else REF_360]
    c.method = ("Available strengths per chapter D (tension), E (compression, stainless curves of Table E3.1), "
                "F (flexure), G (shear, torsion), H (interaction).")
    return c


def _s(v):
    if isinstance(v, float):
        return f"{v:.5g}"
    return str(v)


# ================================================================ beam (closed form)
_BEAM_CASES = {
    "ss_point": ("P", "a"), "ss_udl": ("w",), "cantilever_point": ("P", "a"), "cantilever_udl": ("w",),
    "fixed_point": ("P", "a"), "fixed_udl": ("w",), "propped_udl": ("w",), "propped_point_center": ("P",),
    "overhang_tip_point": ("P", "a"),
}


def beam(inputs: dict) -> Calc:
    """WHEN: one member with textbook supports (simple span, cantilever, fixed, propped, overhang); quick
    stress / deflection answer without building a frame model. Strength check by AISC flexure and shear."""
    c = Calc("beam", "Closed-form beam check")
    c.inputs = inputs
    case = inputs.get("case")
    if case not in _BEAM_CASES:
        raise InputError(f"case must be one of {sorted(_BEAM_CASES)}")
    sec = SC.from_spec(_need_dict(inputs, "section"))
    mat = _mat(inputs, c)
    method = _method(inputs, c)
    L = need(inputs, "L", lo=0.0, strict_lo=True)
    args = [need(inputs, k) for k in _BEAM_CASES[case]]
    axis = inputs.get("axis", "z")
    I = sec.Iz if axis == "z" else sec.Iy
    add_sw = inputs.get("include_self_weight", True)
    fn = getattr(B, case)
    if case == "overhang_tip_point":
        res = fn(args[0], L, args[1], mat.E, I)
    else:
        res = fn(*args[:1], *(args[1:]), L, mat.E, I) if len(args) == 2 else fn(args[0], L, mat.E, I)
    if add_sw:
        wsw = sec.A * mat.density
        sw_case = {"ss_point": "ss_udl", "ss_udl": "ss_udl", "cantilever_point": "cantilever_udl",
                   "cantilever_udl": "cantilever_udl", "fixed_point": "fixed_udl", "fixed_udl": "fixed_udl",
                   "propped_udl": "propped_udl", "propped_point_center": "propped_udl",
                   "overhang_tip_point": "ss_udl"}[case]
        rs = getattr(B, sw_case)(wsw, L, mat.E, I)
        c.assume(f"self weight {wsw * 12:.2f} lb/ft added by superposing the {sw_case} maxima (conservative)")
        M = res["M_max"] + rs["M_max"]
        V = res["V_max"] + rs["V_max"]
        d = res.get("defl_max", res.get("defl_tip", 0.0)) + rs["defl_max"]
    else:
        M, V, d = res["M_max"], res["V_max"], res.get("defl_max", res.get("defl_tip", 0.0))
    c.r("M_max", M, "lb-in")
    c.r("V_max", V, "lb")
    c.r("deflection", d, "in")
    c.r("bending stress M/S", M / (sec.Sz if axis == "z" else sec.Sy), "psi")
    Mc, dm = MB.flexure(sec, mat, axis, method, float(inputs.get("Lb", L)), float(inputs.get("Cb", 1.0)))
    Vc, dv = MB.shear(sec, mat, "y" if axis == "z" else "z", method, L / 2)
    c.r("M_available", Mc, "lb-in")
    c.r("V_available", Vc, "lb")
    c.ratio("flexure", M, Mc, f"M {M:.0f} / Mc {Mc:.0f} lb-in ({dm.get('clause')})", dm.get("clause", ""))
    c.ratio("shear", V, Vc, f"V {V:.0f} / Vc {Vc:.0f} lb ({dv.get('clause')})", dv.get("clause", ""))
    kind = "cantilever" if case.startswith("cantilever") or case == "overhang_tip_point" else "beam_equipment"
    lim_n = inputs.get("defl_limit_L_over")
    if lim_n is None:
        lim_n, basis = DEFLECTION_LIMITS[kind]
        c.assume(f"deflection limit L/{lim_n} ({basis})")
    span = args[1] if case == "overhang_tip_point" else L
    c.ratio("deflection", d, span / float(lim_n), f"{d:.4f} in vs L/{lim_n} = {span / float(lim_n):.4f} in",
            "serviceability")
    c.tables["closed form"] = {"columns": ["item", "value"], "rows": [[k, _s(v)] for k, v in res.items()]}
    c.references += [res["case"], REF_370 if mat.stainless else REF_360]
    c.method = "Closed-form statics and elastic deflection; AISC available flexural and shear strength."
    return c


# ================================================================ frame_check
def frame_check(inputs: dict) -> Calc:
    """WHEN: any real frame — the skid base grillage, a stand, a pump base, legs with bracing, a fork lift on tines,
    feet that may lift off. Runs the 3D frame for every combination and checks every member and every support.

    inputs: the frame dict of frame.from_dict plus
      method: ASD | LRFD
      combinations: {name: {case: factor}}  (or "auto": true to build ASCE 7 combinations from the case names)
      design: {member_id or "*": {"K_z", "K_y", "Lb", "Cb", "defl_limit_L_over", "kind"}}
      pdelta: bool (second-order; use it when legs or posts carry compression with sway)
      buckling: bool (eigen-buckling load factor for each combination)
      modal: n (natural frequencies, Hz, from the frame steel plus 'masses')
    """
    c = Calc("frame_check", inputs.get("title", "3D frame analysis and member checks"))
    c.inputs = {k: v for k, v in inputs.items() if k not in ("nodes", "members")}
    c.inputs["n_nodes"] = len(inputs.get("nodes", {}))
    c.inputs["n_members"] = len(inputs.get("members", []))
    method = _method(inputs, c)
    model = FR.from_dict(inputs)
    if not model.members:
        raise InputError("frame_check needs members")
    if not model.supports:
        raise InputError("frame_check needs supports")
    for mid, m in model.members.items():
        if m.L < 1.0 or m.L > 1200.0:
            c.warn(f"{mid} is {m.L:.3f} in long: check units (skidframe uses inches)")
    for nm in inputs.get("combinations", {}) if isinstance(inputs.get("combinations"), dict) else {}:
        for case in inputs["combinations"][nm]:
            if case not in model.cases:
                raise InputError(f"combination '{nm}' uses unknown case '{case}'; cases are {sorted(model.cases)}")
    combos = inputs.get("combinations")
    service_only = set()
    if not combos or combos == "auto" or inputs.get("auto"):
        asce = LD.ASCE_CASES
        if "D" in model.cases:
            combos = LD.combinations(method, set(model.cases))
        else:   # e.g. a lift-only model: every case on its own
            combos = {f"{k} (on its own)": {k: 1.0} for k in sorted(model.cases)}
        c.assume(f"combinations built from ASCE 7-22 Chapter 2 for cases {sorted(set(model.cases) & asce)}")
        for case in sorted(set(model.cases) - asce - {"HYDRO"}):
            c.warn(f"case {case} is not an ASCE 7 load: it is run on its own, so it must carry its own gravity "
                   "and factors (e.g. LIFT body [0, 0, -impact]; TRANSPORT body [ax, ay, -1])")
    design = inputs.get("design", {})
    default = design.get("*", {})
    if not design:
        c.assume("every member: K = 1.0 both axes, Lb = member length, Cb = 1.0 (no 'design' block given)")
    pd = bool(inputs.get("pdelta", False))
    service = inputs.get("service_combinations")
    if service is None:
        if method == "LRFD":
            # LRFD strength combinations are factored; deflection needs unfactored service loads (CPM-190 F-10)
            sv = {k: 1.0 for k in ("D", "F", "L") if k in model.cases}
            if sv:
                combos = {**combos, "SERVICE " + "+".join(sv): sv}
                service_only.add("SERVICE " + "+".join(sv))
            service = sorted(service_only)
        else:
            service = [n for n, f in combos.items()
                       if not any(k in f for k in ("Eh", "Ev", "W", "LIFT", "TRANSPORT"))
                       and all(abs(v) <= 1.0 for v in f.values())]
        c.assume(f"deflection checked under the service combinations {service or 'none (give service_combinations)'}")
    member_rows, worst = [], {}
    support_rows = []
    lifted_all = set()
    for cname, fac in combos.items():
        res = model.solve(fac, pdelta=pd)
        for node in model.supports:
            name = model.names[node]
            r = res.reaction(name)
            support_rows.append([cname, name] + [round(float(x), 1) for x in r])
        for nm in res.lifted():
            lifted_all.add(f"{nm[0]} {nm[1]} ({cname})")
        for mid, m in model.members.items():
            d = {**default, **design.get(mid, {})}
            L = m.L
            Lc_z = float(d.get("Lc_z", float(d.get("K_z", 1.0)) * L))
            Lc_y = float(d.get("Lc_y", float(d.get("K_y", 1.0)) * L))
            Lb = float(d.get("Lb", L))
            cap = _capacities(m.section, m.material, method, Lc_z, Lc_y, Lb, float(d.get("Cb", 1.0)),
                              float(d.get("Lv", L / 2)), float(d.get("L_torsion", L)))
            for k, (v, det) in cap.items():
                for key in ("note", "approximation"):
                    if key in det:
                        c.warn(f"{mid} {k}: {det[key]}")
            env, stations = res.member_envelope(mid)
            best, rv_max, rt_max = (0.0, "service only", 0.0, 0.0, 0.0), 0.0, 0.0
            if cname not in service_only:
                best = None
                for st in stations:
                    r, eq, rv, rt, parts = _station_ratio(st, cap)
                    if best is None or r > best[0]:
                        best = (r, eq, st["s"], rv, rt)
                    rv_max, rt_max = max(rv_max, rv), max(rt_max, rt)
            dfl = res.member_deflection(mid)
            kind = d.get("kind", "beam_equipment")
            if kind not in DEFLECTION_LIMITS and kind != "none":
                raise InputError(f"design kind '{kind}' for {mid}: use one of {sorted(DEFLECTION_LIMITS)} or 'none'")
            n_lim = float(d.get("defl_limit_L_over", DEFLECTION_LIMITS.get(kind, DEFLECTION_LIMITS["beam_equipment"])[0]))
            # beams: sag from the chord between the ends; cantilevers: tip from the tangent at the support
            dmax = dfl["cantilever"] if kind == "cantilever" else math.hypot(dfl["rel_y"], dfl["rel_z"])
            # deflection is a service check: only the service combinations count
            rdef = dmax / (L / n_lim) if cname in service and kind != "none" else 0.0
            row = [cname, mid, m.section.label, round(env["N_min"][0]), round(env["N_max"][0]),
                   round(abs(env["Mz"][0])), round(abs(env["My"][0])), round(abs(env["T"][0])),
                   round(best[0], 3), best[1], round(best[2], 1), round(rv_max, 3), round(rt_max, 3),
                   round(dmax, 4), round(rdef, 3)]
            member_rows.append(row)
            w = worst.get(mid)
            gov = max(best[0], rv_max, rt_max, rdef)
            if w is None or gov > w[0]:
                worst[mid] = (gov, cname, best, rv_max, rt_max, rdef)
    c.table("member results by combination",
            ["combination", "member", "section", "N_min lb", "N_max lb", "|Mz| lb-in", "|My| lb-in", "|T| lb-in",
             "interaction", "eq", "at s in", "shear", "torsion", "defl in", "defl ratio"], member_rows)
    c.table("support reactions by combination",
            ["combination", "node", "Fx", "Fy", "Fz", "Mx", "My", "Mz"], support_rows)
    for mid, (gov, cname, best, rv, rt, rdef) in sorted(worst.items()):
        m = model.members[mid]
        clause = "AISC 370-21" if m.material.stainless else "AISC 360-22"
        c.ratio(f"{mid} interaction", best[0], 1.0, f"{best[1]} at s = {best[2]:.1f} in, {cname}", f"{clause} {best[1]}")
        c.ratio(f"{mid} shear", rv, 1.0, cname, f"{clause} G")
        c.ratio(f"{mid} torsion", rt, 1.0, cname, f"{clause} G8 / H3")
        if rdef:
            c.ratio(f"{mid} deflection", rdef, 1.0, cname, "serviceability (limit in 'design')")
    if not any("defl_limit_L_over" in v or "kind" in v for v in design.values()):
        c.assume("deflection limit L/360 for every member (beams supporting equipment); set 'kind' or "
                 "'defl_limit_L_over' per member in 'design'")
    if lifted_all:
        c.warn("contact supports not bearing: " + "; ".join(sorted(lifted_all)))
    # max support reactions
    if support_rows:
        fz = max(support_rows, key=lambda r: r[4])
        c.r("max vertical reaction", fz[4], f"lb ({fz[1]}, {fz[0]})")
    c.r("combinations analysed", len(combos))
    c.r("members", len(model.members))
    if inputs.get("buckling"):
        rows = []
        for cname, fac in combos.items():
            if cname in service_only:
                continue
            try:
                lam = model.buckling(fac, 1)
                rows.append([cname, round(lam[0], 3) if lam else "none"])
                if lam:
                    c.ratio(f"elastic buckling {cname}", 1.0, lam[0], f"load factor to buckling {lam[0]:.2f}",
                            "linear eigen-buckling; AISC 370 C (factor < 10 means second-order effects matter)")
                    if lam[0] < 10 and not pd:
                        c.warn(f"{cname}: buckling factor {lam[0]:.2f} < 10: rerun with pdelta: true "
                               "(AISC 370 Appendix 8 / direct analysis)")
            except Exception as exc:  # report and continue, loudly (CPM-190 F-08)
                rows.append([cname, f"not solved: {exc}"])
                c.warn(f"{cname}: elastic buckling not solved ({exc}); stability unverified for this combination")
        c.table("elastic buckling load factor", ["combination", "factor"], rows)
    if inputs.get("modal"):
        fr = model.modal(int(inputs["modal"]))
        c.table("natural frequencies", ["mode", "Hz"], [[k + 1, round(f, 3)] for k, f in enumerate(fr)])
        c.r("first natural frequency", fr[0], "Hz")
    c.references += [REF_370, REF_360, REF_ASCE7]
    c.method = ("3D direct stiffness frame analysis (Timoshenko beam elements, members subdivided), compression-only "
                "contacts by active set" + (", P-Delta by geometric stiffness iteration" if pd else "") +
                ". Each member is checked at every station for the concurrent forces (H1-1, H2-1), plus shear, "
                "torsion and deflection relative to its chord.")
    return c
