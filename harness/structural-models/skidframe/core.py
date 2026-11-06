"""Result record, input helpers and units shared by every skidframe model.

Units everywhere (inputs and results): inches, pounds-force (lb), psi, lb-in, degrees F, seconds.
Every model returns a Calc. A Calc carries its inputs, results, PASS/FAIL checks (each citing the clause
it applies), the ASSUMPTION lines for every default it filled, warnings, the method and references.
Same pattern as the job thermal model suites (for example job/knowledge/thermal-models on the hot water set job).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

G_IN_S2 = 386.0886          # standard gravity, in/s2
LB_PER_KIP = 1000.0
PSI_PER_KSI = 1000.0
WATER_LB_PER_IN3 = 62.37 / 1728.0   # water at 60 F, lb/in3 (62.37 lb/ft3)
WATER_LB_PER_GAL = 8.337            # US gal of water at 60 F


class InputError(ValueError):
    """Missing, impossible or out-of-range input. The CLI exits 2 on it."""


def need(inputs: dict, name: str, lo: float | None = None, hi: float | None = None, strict_lo: bool = False) -> float:
    """Fetch a required numeric input and range-check it."""
    if name not in inputs or inputs[name] is None:
        raise InputError(f"required input '{name}' is missing (no default: it decides the result)")
    v = inputs[name]
    try:
        v = float(v)
    except (TypeError, ValueError):
        raise InputError(f"input '{name}' must be a number, got {v!r}")
    if not math.isfinite(v):
        raise InputError(f"input '{name}' must be finite, got {v}")
    if lo is not None and (v < lo or (strict_lo and v == lo)):
        raise InputError(f"input '{name}' = {v} is below its limit {lo}")
    if hi is not None and v > hi:
        raise InputError(f"input '{name}' = {v} is above its limit {hi}")
    return v


def need_choice(inputs: dict, name: str, choices) -> str:
    if name not in inputs or inputs[name] is None:
        raise InputError(f"required input '{name}' is missing; one of {sorted(choices)}")
    v = str(inputs[name])
    if v not in choices:
        raise InputError(f"input '{name}' = {v!r} is not one of {sorted(choices)}")
    return v


@dataclass
class Check:
    name: str
    ratio: float | None          # demand / capacity (<= 1.0 passes); None for a yes/no check
    passed: bool
    detail: str
    rule: str = ""

    def to_dict(self):
        return {"name": self.name, "ratio": None if self.ratio is None else round(self.ratio, 4),
                "result": "PASS" if self.passed else "FAIL", "detail": self.detail, "rule": self.rule}


@dataclass
class Calc:
    model: str
    title: str
    inputs: dict = field(default_factory=dict)
    results: dict = field(default_factory=dict)          # name -> (value, unit)
    tables: dict = field(default_factory=dict)           # name -> {"columns": [...], "rows": [[...]]}
    checks: list = field(default_factory=list)
    assumptions: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    method: str = ""
    references: list = field(default_factory=list)

    # ------------------------------------------------------------ builders
    def r(self, name: str, value, unit: str = ""):
        if isinstance(value, float) and math.isfinite(value):
            value = float(f"{value:.6g}")
        self.results[name] = (value, unit)
        return value

    def ratio(self, name: str, demand: float, capacity: float, detail: str = "", rule: str = "", limit: float = 1.0):
        """Demand/capacity check; passes when demand/capacity <= limit. A zero capacity with demand fails."""
        if capacity <= 0:
            rat = math.inf if demand > 0 else 0.0
        else:
            rat = abs(demand) / capacity
        passed = rat <= limit + 1e-9
        d = detail or f"demand {demand:.4g} / capacity {capacity:.4g}"
        self.checks.append(Check(name, rat, passed, d, rule))
        return rat

    def check(self, name: str, passed: bool, detail: str, rule: str = ""):
        self.checks.append(Check(name, None, bool(passed), detail, rule))

    def assume(self, text: str):
        if not text.startswith("ASSUMPTION:"):
            text = "ASSUMPTION: " + text
        if text not in self.assumptions:
            self.assumptions.append(text)

    def warn(self, text: str):
        if text not in self.warnings:
            self.warnings.append(text)

    def default(self, inputs: dict, name: str, value, basis: str):
        """Optional input: use the given value or fill the default and record it as an ASSUMPTION line."""
        if name in inputs and inputs[name] is not None:
            return inputs[name]
        self.assume(f"{name} = {value} ({basis})")
        inputs[name] = value
        return value

    def table(self, name: str, columns: list, rows: list):
        self.tables[name] = {"columns": list(columns), "rows": [list(r) for r in rows]}

    def merge(self, other: "Calc", prefix: str = ""):
        """Fold a sub-calculation's checks, assumptions and warnings into this one."""
        for c in other.checks:
            self.checks.append(Check(prefix + c.name, c.ratio, c.passed, c.detail, c.rule))
        for a in other.assumptions:
            self.assume(a)
        for w in other.warnings:
            self.warn(w)
        for ref in other.references:
            if ref not in self.references:
                self.references.append(ref)

    # ------------------------------------------------------------ queries
    @property
    def failed(self) -> bool:
        return any(not c.passed for c in self.checks)

    @property
    def governing(self):
        rated = [c for c in self.checks if c.ratio is not None]
        return max(rated, key=lambda c: c.ratio) if rated else None

    def value(self, name: str):
        return self.results[name][0]

    def to_dict(self):
        g = self.governing
        return {
            "model": self.model,
            "title": self.title,
            "status": "FAIL" if self.failed else "PASS",
            "governing": None if g is None else {"name": g.name, "ratio": round(g.ratio, 4), "rule": g.rule},
            "inputs": self.inputs,
            "results": {k: {"value": v, "unit": u} for k, (v, u) in self.results.items()},
            "tables": self.tables,
            "checks": [c.to_dict() for c in self.checks],
            "assumptions": self.assumptions,
            "warnings": self.warnings,
            "method": self.method,
            "references": self.references,
        }

    def to_markdown(self) -> str:
        d = self.to_dict()
        out = [f"# {self.title}", "", f"Model `{self.model}`: **{d['status']}**"]
        if d["governing"]:
            out.append(f"Governing: {d['governing']['name']} at {d['governing']['ratio']:.3f} ({d['governing']['rule']})")
        out += ["", "## Results", "", "| Result | Value | Unit |", "|---|---|---|"]
        for k, (v, u) in self.results.items():
            out.append(f"| {k} | {v} | {u} |")
        if self.checks:
            out += ["", "## Checks", "", "| Check | Ratio | Result | Rule | Detail |", "|---|---|---|---|---|"]
            for c in self.checks:
                rt = "" if c.ratio is None else f"{c.ratio:.3f}"
                out.append(f"| {c.name} | {rt} | {'PASS' if c.passed else 'FAIL'} | {c.rule} | {c.detail} |")
        for name, t in self.tables.items():
            out += ["", f"## {name}", "", "| " + " | ".join(map(str, t["columns"])) + " |",
                    "|" + "---|" * len(t["columns"])]
            for row in t["rows"]:
                out.append("| " + " | ".join(_fmt(x) for x in row) + " |")
        for head, items in (("Assumptions", self.assumptions), ("Warnings", self.warnings),
                            ("References", self.references)):
            if items:
                out += ["", f"## {head}", ""] + [f"- {x}" for x in items]
        if self.method:
            out += ["", "## Method", "", self.method]
        return "\n".join(out) + "\n"


def _fmt(x):
    if isinstance(x, float):
        return f"{x:.4g}"
    return str(x)
