"""rule_scope - where a design rule applies on the active project, read the same way by every check.

Three levels of rule files (CLAUDE.md hard rule 11; harness/design-rules/README.md), read in this order:
  1. harness  harness/design-rules/*.yaml                                       company-wide (every CPME job)
  2. job      job/design-rules/*.yaml                                           every project in the job
  3. project  <project>/01_Design_Basis/05_Standards_Specifications/Design_Rules/*.yaml   this project only
A lower level narrows the one above it: `merged_rule` lays the job entry over the harness entry and the project entry
over that (nested mappings merged key by key, any other value replaced), and the service-class scope `applies_to` is
the job's classes narrowed (intersected) by the project's. `applies_to` on a harness entry is prose about the rule
(e.g. "2.0 in OD tube"), not a class scope, so it never sets the scope.

Two layouts are read in any level's file (CPME practice):
  * section layout: sections holding lists of rules, `dead_leg: [{id: SAN-DL-002, ...}]`, or a mapping by rule id,
    `straight_run: {INST-SR-001: {...}}`;
  * id layout: each rule keyed by its id at the top level, `SAN-DL-002: {rule_ref, applies_to, note, <values>}`.
`find_rule` finds a rule in either layout.

A service class's rule list (`class_rules`) is the harness PIPE-SVC-001 classes.<class>.rules plus the job's
job/design-rules/piping.yaml PIPE-SVC-001 job_rules_by_class.<class>.

Scope (harness/design-rules/piping.yaml PIPE-SVC-001, service classes): every line in line-list.csv carries one
`service_class`. A rule entry's `applies_to` names the classes it applies to (a list, or a comma-separated
string); `unknown` (or no entry) means not decided yet, and the check reports the rule as not checked. The SAN-* and
STR-PS-* rules are hygienic-line rules: they apply to class `hygienic`, and to `utility-water` only where the
project entry lists it (the customer spec calls for them); any other class named for them is ignored and reported.
SAN-PP-001, SAN-FRAME-001 and SAN-ACC-001 are skid-wide (PIPE-SVC-001 skid_wide) and take any class.

Also here, so pid_consistency.py, list_delta.py and accept_preflight.py agree: the spool id rule
`<LINE>-SP<nn>` (CLAUDE.md naming), with LINE any line_no on line-list.csv, and whether the model source exists.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

import repo_paths as rp

UNKNOWN = "unknown"
HYGIENIC_RULE_PREFIXES = ("SAN-", "STR-PS-")
# Skid-wide rules that sit in sanitary.yaml but are not hygienic-line rules (PIPE-SVC-001 skid_wide): their
# applies_to names any class, or `skid`.
SKID_WIDE_RULES = ("SAN-PP-001", "SAN-FRAME-001", "SAN-ACC-001")
HYGIENIC_CLASSES = ("hygienic", "utility-water")   # utility-water only when the project entry lists it


def read_yaml(path: Path):
    import yaml
    if not path.is_file():
        return None
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def find_rule(data, rule_id: str) -> dict | None:
    """The rule entry `rule_id` in a rule file of either layout, or None."""
    if not isinstance(data, dict):
        return None
    top = data.get(rule_id)
    if isinstance(top, dict):
        return top
    for v in data.values():
        if isinstance(v, list):
            for x in v:
                if isinstance(x, dict) and x.get("id") == rule_id:
                    return x
        elif isinstance(v, dict):
            if v.get("id") == rule_id:   # a section that is one rule, `service_classes: {id: PIPE-SVC-001, ...}`
                return v
            x = v.get(rule_id)
            if isinstance(x, dict):
                return x
    return None


def project_rules_dir() -> Path | None:
    """The active project's Design_Rules folder, or None while the job has no project yet."""
    return rp.DESIGN_RULES if rp.HAS_PROJECT else None


def project_rule(file_name: str, rule_id: str, rules_dir: Path | None = None) -> dict | None:
    """The project's entry for rule_id in <project> Design_Rules/<file_name>, or None (also with no project yet)."""
    d = rules_dir or project_rules_dir()
    return find_rule(read_yaml(d / file_name), rule_id) if d is not None else None


def job_rule(file_name: str, rule_id: str, rules_dir: Path | None = None) -> dict | None:
    """The job's entry for rule_id in job/design-rules/<file_name>, or None."""
    return find_rule(read_yaml((rules_dir or rp.JOB_DESIGN_RULES) / file_name), rule_id)


def harness_rule(file_name: str, rule_id: str, rules_dir: Path | None = None) -> dict | None:
    return find_rule(read_yaml((rules_dir or rp.HARNESS_DESIGN_RULES) / file_name), rule_id)


def level_rules(file_name: str, rule_id: str, harness_dir: Path | None = None, job_dir: Path | None = None,
                project_dir: Path | None = None) -> tuple[dict | None, dict | None, dict | None]:
    """(harness, job, project) entries for rule_id in <level>/<file_name>; None where a level has none."""
    return (harness_rule(file_name, rule_id, harness_dir), job_rule(file_name, rule_id, job_dir),
            project_rule(file_name, rule_id, project_dir))


def _deep_merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in over.items():
        out[k] = _deep_merge(out[k], v) if isinstance(out.get(k), dict) and isinstance(v, dict) else v
    return out


def narrow_applies_to(*entries: dict | None):
    """The service-class scope of entries given top level first (job, then project): each level that states
    applies_to narrows the one above it. A level saying `unknown` makes the scope unknown (not decided at that level
    yet); classes intersect with the classes above. Returns a sorted list of classes, UNKNOWN, or None when no level
    states applies_to."""
    scope = None
    for e in entries:
        if not isinstance(e, dict) or "applies_to" not in e:
            continue
        if is_unknown(e["applies_to"]):
            scope = UNKNOWN
            continue
        cls = applies_to_classes(e) or set()
        scope = (scope & cls) if isinstance(scope, set) else cls
    return sorted(scope) if isinstance(scope, set) else scope


def merge_entries(harness: dict | None, job: dict | None, project: dict | None) -> dict | None:
    """One rule entry from its three levels: job over harness, project over job (nested mappings merged key by key),
    and applies_to = the job's class scope narrowed by the project's (narrow_applies_to). The harness entry's own
    applies_to (prose) is dropped. None when no level has the rule."""
    if harness is None and job is None and project is None:
        return None
    out: dict = {}
    for e in (harness, job, project):
        if isinstance(e, dict):
            out = _deep_merge(out, e)
    out.pop("applies_to", None)
    scope = narrow_applies_to(job, project)
    if scope is not None:
        out["applies_to"] = scope
    return out


def merged_rule(file_name: str, rule_id: str, harness_dir: Path | None = None, job_dir: Path | None = None,
                project_dir: Path | None = None) -> dict | None:
    """rule_id as it applies on the active project: harness, narrowed by the job, narrowed by the project."""
    return merge_entries(*level_rules(file_name, rule_id, harness_dir, job_dir, project_dir))


_RULE_ID = re.compile(r"\b(?:[A-Z]+-)+\d{2,3}\b")


def class_rules(service_class: str, harness_dir: Path | None = None, job_dir: Path | None = None) -> list[str]:
    """The rule ids of one service class: harness piping.yaml PIPE-SVC-001 classes.<class>.rules (a list, or prose
    naming the ids), then the job's piping.yaml PIPE-SVC-001 job_rules_by_class.<class>. Each id once, in that order."""
    c = service_class.strip().lower()
    h = find_rule(read_yaml((harness_dir or rp.HARNESS_DESIGN_RULES) / "piping.yaml"), "PIPE-SVC-001") or {}
    j = find_rule(read_yaml((job_dir or rp.JOB_DESIGN_RULES) / "piping.yaml"), "PIPE-SVC-001") or {}
    out: list[str] = []
    for v in (((h.get("classes") or {}).get(c) or {}).get("rules"), (j.get("job_rules_by_class") or {}).get(c)):
        ids = v if isinstance(v, (list, tuple)) else _RULE_ID.findall(str(v or ""))
        out += [str(x).strip() for x in ids if str(x).strip() and str(x).strip() not in out]
    return out


def is_unknown(v) -> bool:
    """None, blank, or a string starting `unknown` (the repo's word for a value not received yet)."""
    return v is None or (isinstance(v, str) and (not v.strip() or v.strip().lower().startswith(UNKNOWN)))


def applies_to_classes(entry: dict | None) -> set[str] | None:
    """The service classes a project rule entry applies to, or None while it is unknown (or the entry is missing)."""
    if entry is None:
        return None
    v = entry.get("applies_to")
    if is_unknown(v):
        return None
    items = v if isinstance(v, (list, tuple)) else re.split(r"[,;]", str(v))
    out = {str(x).strip().lower() for x in items if str(x).strip()}
    return out or None


def scope_classes(rule_id: str, entry: dict | None) -> tuple[set[str] | None, str]:
    """(classes the rule is checked on, note). None = not checked: applies_to unknown or names no usable class."""
    classes = applies_to_classes(entry)
    if classes is None:
        return None, f"{rule_id}: applies_to unknown in the job and project rules (not checked)"
    if rule_id.startswith(HYGIENIC_RULE_PREFIXES) and rule_id not in SKID_WIDE_RULES:
        ignored = sorted(classes - set(HYGIENIC_CLASSES))
        keep = classes & set(HYGIENIC_CLASSES)
        note = (f"{rule_id}: hygienic-line rule (PIPE-SVC-001); classes {', '.join(ignored)} ignored"
                if ignored else "")
        if not keep:
            return None, (note or f"{rule_id}: applies_to names no hygienic class") + " (not checked)"
        return keep, note
    return classes, ""


def line_list(path: Path | None = None) -> list[dict]:
    if path is None and not rp.HAS_PROJECT:
        return []
    p = path or rp.DATA / "line-list.csv"
    if not p.is_file():
        return []
    with open(p, newline="", encoding="utf-8-sig") as f:
        return [r for r in csv.DictReader(f) if (r.get("line_no") or "").strip()]


def line_classes(path: Path | None = None) -> dict[str, str]:
    """{line_no: service_class} from line-list.csv; a blank class reads `unknown`."""
    return {r["line_no"].strip(): ((r.get("service_class") or "").strip().lower() or UNKNOWN)
            for r in line_list(path)}


def lines_in_scope(rule_id: str, entry: dict | None, classes_by_line: dict[str, str] | None = None
                   ) -> tuple[set[str] | None, list[str]]:
    """(lines the rule is checked on, notes). None = the rule is not checked at all (scope unknown).
    Lines whose class is unknown are named in the notes as not checked."""
    classes, note = scope_classes(rule_id, entry)
    notes = [note] if note else []
    if classes is None:
        return None, notes
    by_line = line_classes() if classes_by_line is None else classes_by_line
    unk = sorted(ln for ln, c in by_line.items() if c == UNKNOWN)
    if unk:
        notes.append(f"{rule_id}: service_class unknown on {', '.join(unk)} (not checked)")
    return {ln for ln, c in by_line.items() if c in classes}, notes


def spool_id_ok(spool_id: str, line: str, lines=None) -> bool:
    """CLAUDE.md naming: a spool id is <LINE>-SP<nn> for its own line; `lines` (if given) must hold that line."""
    if not line or (lines is not None and line not in lines):
        return False
    return re.fullmatch(re.escape(line) + r"-SP\d{2}", spool_id or "") is not None


def spool_line(spool_id: str, lines) -> str | None:
    """The line_no of `lines` that spool_id is named for (<LINE>-SP<nn>), longest match first; None if none."""
    for ln in sorted(lines, key=len, reverse=True):
        if spool_id_ok(spool_id, ln):
            return ln
    return None


def model_missing() -> str | None:
    """None when the project's model source (skidlib) exists; else why a model check has nothing to check."""
    if not rp.HAS_PROJECT:
        return "no project yet"
    src = rp.SKID_MODEL / "skidlib"
    if (src / "__init__.py").is_file() or (src / "layout.py").is_file():
        return None
    return f"no model yet ({rp.rel(rp.SKID_MODEL)} has no skidlib source)"
