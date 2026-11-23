"""list_delta - what the model says that the P&ID lists do not (CPME practice).

Lists stay the formal input layer and the model leads: every build emits a list delta, and the one owner of a
non-empty delta is harness/scripts/model_accept.py at acceptance, which writes it into the lists
(harness/lib/list_from_model.py, one rule per kind). A fast build only carries the rows to acceptance; nobody edits a
list by hand to clear them. Hard rule 2 stays intact: the delta is how a gap between the model and the P&ID is
surfaced, never a fix.

Reads one build or one filed revision (a folder and a file prefix):
    <prefix>manifest.json, <prefix>spool-list.csv, <prefix>weld-map.csv
and the lists in <project>/03_Working_Design/PID/02_Tag_Lists/ (equipment, valve, instrument, tie-in, line). Plain Python, no CAD kernel.

Delta rows (one per difference; zero rows = the model and the lists agree):
    model-tag-not-on-list   a tagged model item whose tag is on no <project>/03_Working_Design/PID/02_Tag_Lists list
    list-tag-not-in-model   a list tag (not off-skid, not 'unknown') with no model item
    untagged-item           a tagged kind with no tag, or an untagged kind (FM-/PS-/PL-) off its pattern
    line-not-routed         an on-skid line-list line with no spool and no component
    model-line-not-on-list  a spool or component on a line that line-list.csv does not have
    fitting-line            a loose fitting whose line is not on line-list.csv
    line-size               spool OD differs from line-list size_od_in
    line-wall               spool wall differs from line-list gauge
    line-material           spool material differs from line-list spec + material
    spool-id / weld-id      spool id not <LINE>-SP<nn> for its line (any line_no, e.g. CS-201-SP03;
                            rule_scope.spool_id_ok); weld id malformed or duplicated
    tag-part-changed        a tag on a list that has a component_id column (valve-list, instrument-list) whose row
                            names a different component than the one the model places on that tag (CAPA
                            2026-11-23: a maker swap on tags that stay). `model` = the placed id, `lists` = the
                            row's component_id ('unknown' when the row has none yet), `detail` names the list file.
                            The placed id is read from the model item's source text (manifest.json, else the BOM):
                            the id that prefixes the STEP file it places (COMP-0067-....step), else the id the
                            source starts with, else the only id it names; a source naming none, or several with
                            none of those forms, is not compared (information line). CMP-nnnn and COMP-nnnn are
                            the same component number (norm_ids, placed_component); a row naming several ids
                            agrees when the placed one is among them.
The tag and line rows are the ones harness/checks/pid_consistency.py fails on (same rules, same off-skid set).
Where the list says 'unknown' and the model has a value, that is reported as information in the .md, not as
a delta row (the list is not contradicted); tag-part-changed is the exception, since the component id is the
model's to give.
"""
from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import repo_paths as rp
import rule_scope

if str(rp.CHECKS) not in sys.path:
    sys.path.insert(0, str(rp.CHECKS))
if rp.HAS_MODEL and str(rp.SKID_MODEL) not in sys.path:
    sys.path.insert(0, str(rp.SKID_MODEL))

TAG_LISTS = ("equipment-list.csv", "valve-list.csv", "instrument-list.csv", "tie-in-list.csv")
FIELDS = ["kind", "subject", "line_no", "model", "lists", "detail"]


def _csv(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _num(s) -> float | None:
    m = re.match(r"\s*([0-9]*\.?[0-9]+)", str(s or ""))
    return float(m.group(1)) if m else None


def _unknown(s) -> bool:
    return not str(s or "").strip() or str(s).strip().lower().startswith("unknown")


def _list(name: str) -> list[dict]:
    """The rows of one P&ID list (rp.DATA/<name>). A model whose skidlib.inputs has list_rows(name) gives them
    itself: a job-level model keeps only the rows its configuration carries (Linear CPM-155)."""
    try:
        from skidlib import inputs
        fn = getattr(inputs, "list_rows", None)
    except ImportError:
        fn = None
    return fn(name) if fn else _csv(rp.DATA / name)


def list_material(row: dict) -> str:
    """'ASTM A270 S2 316L' from spec 'ASTM A270 S2 (rule ...)' and material '316L'."""
    spec = re.sub(r"\s*\(.*\)\s*$", "", (row.get("spec") or "").strip())
    return f"{spec} {(row.get('material') or '').strip()}".strip()


PART_LISTS = ("valve-list.csv", "instrument-list.csv")   # the lists whose rows may carry component_id
_ID = re.compile(r"\b(?:COMP|CMP)-(\d{4})\b")


def norm_ids(text) -> list[str]:
    """Every component number named in the text, as COMP-nnnn (CMP-nnnn is the old spelling of the same number),
    in order, without repeats."""
    out = []
    for n in _ID.findall(str(text or "")):
        cid = f"COMP-{n}"
        if cid not in out:
            out.append(cid)
    return out


def placed_component(source) -> str | None:
    """The component the model places, read from an item's source text (rule in the module docstring), or None."""
    s = str(source or "")
    step = re.search(r"\b(?:COMP|CMP)-(\d{4})-[^\s,;()]*\.(?:step|stp)\b", s, re.I)
    if step:
        return f"COMP-{step.group(1)}"
    lead = re.match(r"\s*(?:COMP|CMP)-(\d{4})\b", s)
    if lead:
        return f"COMP-{lead.group(1)}"
    ids = norm_ids(s)
    return ids[0] if len(ids) == 1 else None


def part_changes(man: dict, bom: list[dict], lists: dict[str, list[dict]]) -> tuple[list[dict], list[str]]:
    """tag-part-changed rows and information lines: each list row with a component_id column against the component
    the model places on its tag. `lists` maps a list file name to its rows."""
    src: dict[str, str] = {}
    for b in bom:
        if b.get("item") and b.get("source"):
            src.setdefault(b["item"].strip(), b["source"])
    for it in man.get("items", []):
        if it.get("tag") and it.get("key") == it.get("tag") and it.get("source"):
            src[it["tag"]] = it["source"]   # the item keyed by its tag is the tagged part itself
    rows, info = [], []
    for name, lrows in lists.items():
        for r in lrows:
            tag = (r.get("tag") or "").strip()
            if "component_id" not in r or not tag or tag not in src:
                continue
            placed = placed_component(src[tag])
            have = (r.get("component_id") or "").strip()
            if placed is None:
                info.append(f"{tag}: the model's source names no single component ({src[tag][:80]}); "
                            f"{name} says {have or 'unknown'}")
                continue
            if placed in norm_ids(have):
                continue
            rows.append({"kind": "tag-part-changed", "subject": tag,
                         "line_no": (r.get("line_no") or r.get("line_no_or_equip") or "").strip(),
                         "model": placed, "lists": have if not _unknown(have) else "unknown",
                         "detail": f"{name}: the model places {placed}, the row names {have or 'unknown'}"})
    return rows, info


def compute(folder: Path, prefix: str = "") -> dict:
    """Delta for the build or filed revision in `folder` (files named <prefix>manifest.json etc.)."""
    from pid_consistency import UNTAGGED_KINDS   # one definition of the untagged kinds
    from skidlib.params import OFF_SKID           # one definition of the off-skid tags and lines

    # a locked revision keeps these in Reports/ and Takeoffs/ (rp.model_subfolder); a work build is flat
    man = json.loads(rp.model_rev_file(folder, f"{prefix}manifest.json").read_text(encoding="utf-8"))
    spools = _csv(rp.model_rev_file(folder, f"{prefix}spool-list.csv"))
    welds = _csv(rp.model_rev_file(folder, f"{prefix}weld-map.csv"))
    lines = {r["line_no"].strip(): r for r in _list("line-list.csv")}
    expected: dict[str, str] = {}
    for name in TAG_LISTS:
        for r in _list(name):
            t = (r.get("tag") or "").strip()
            if t and t.lower() != "unknown":
                expected[t] = name

    rows: list[dict] = []
    info: list[str] = []

    def add(kind, subject, line_no="", model="", lists="", detail=""):
        rows.append({"kind": kind, "subject": subject, "line_no": line_no, "model": model, "lists": lists, "detail": detail})

    model_tags: dict[str, list[str]] = defaultdict(list)
    line_objects: dict[str, list[str]] = defaultdict(list)
    for it in man["items"]:
        if it.get("line"):
            line_objects[it["line"]].append(it["key"])
        kind, tag = it["kind"], it.get("tag") or ""
        if kind in UNTAGGED_KINDS:
            if not re.match(UNTAGGED_KINDS[kind], tag):
                add("untagged-item", it["key"], it.get("line", ""), tag, UNTAGGED_KINDS[kind], f"{kind} off its pattern")
            if kind == "fitting" and it.get("line") not in lines:
                add("fitting-line", it["key"], it.get("line", ""), it.get("line", ""), "", "loose fitting line not on line-list.csv")
            continue
        if not tag:
            add("untagged-item", it["key"], it.get("line", ""), "", "", f"untagged component ({kind})")
            continue
        model_tags[tag].append(it["key"])
    for sp in spools:
        line_objects[sp["line_no"]].append(sp["spool_id"])

    for t, src in sorted(expected.items()):
        if t in OFF_SKID:
            info.append(f"{t}: not modeled - {OFF_SKID[t]}")
        elif t not in model_tags:
            add("list-tag-not-in-model", t, "", "", src, "on the list, not in the model")
    for t in sorted(model_tags):
        if t not in expected:
            add("model-tag-not-on-list", t, "", ", ".join(model_tags[t]), "", "in the model, on no <project>/03_Working_Design/PID/02_Tag_Lists list")
    for ln in lines:
        if ln in OFF_SKID:
            info.append(f"{ln}: not routed - {OFF_SKID[ln]}")
        elif ln not in line_objects:
            add("line-not-routed", ln, ln, "", "line-list.csv", "no spool and no component on this line")
    for ln in sorted(line_objects):
        if ln not in lines:
            add("model-line-not-on-list", ln, ln, f"{len(line_objects[ln])} object(s)", "", "line not in line-list.csv")

    # size, wall and material per line (distinct spool values vs the line-list row)
    per_line: dict[str, list[dict]] = defaultdict(list)
    for sp in spools:
        per_line[sp["line_no"]].append(sp)
    for ln, sps in sorted(per_line.items()):
        row = lines.get(ln)
        if row is None:
            continue
        for fld, model_vals, lst in (
                ("line-size", {_num(s["od_in"]) for s in sps}, row.get("size_od_in")),
                ("line-wall", {_num(s["wall_in"]) for s in sps}, row.get("gauge")),
                ("line-material", {s["material"].strip() for s in sps}, list_material(row)
                 if not (_unknown(row.get("material")) or _unknown(row.get("spec"))) else "unknown")):
            if fld == "line-material":
                known = {v for v in model_vals if not _unknown(v)}
                if _unknown(lst):
                    if known:
                        info.append(f"{ln} material: list unknown, model uses {', '.join(sorted(known))}")
                    continue
                diff = sorted(v for v in known if v != lst)
                if diff:
                    add(fld, ln, ln, "; ".join(diff), lst, "spool material differs from line-list spec + material")
                continue
            lv = None if _unknown(lst) else _num(lst)
            known = {v for v in model_vals if v is not None}
            if lv is None:
                if known:
                    info.append(f"{ln} {fld[5:]}: list unknown, model uses {', '.join(f'{v:g}' for v in sorted(known))} in")
                continue
            diff = sorted(v for v in known if abs(v - lv) > 1e-6)
            if diff:
                add(fld, ln, ln, ", ".join(f"{v:g}" for v in diff), f"{lv:g}", f"spool {fld[5:]} differs from line-list.csv")

    # spool and weld ids (CLAUDE.md naming)
    seen: set[str] = set()
    for sp in spools:
        if not rule_scope.spool_id_ok(sp["spool_id"], sp["line_no"]):
            add("spool-id", sp["spool_id"], sp["line_no"], sp["spool_id"], "<LINE>-SP<nn>", "spool id off the naming rule")
    for w in welds:
        wid, sid = w.get("weld_id", ""), w.get("spool_id", "")
        if not wid.startswith(sid + "-W") or wid in seen:
            add("weld-id", wid, w.get("line_no", ""), wid, "<SPOOL>-W<nn>, unique", "weld id malformed or duplicated")
        seen.add(wid)

    # the part on each tag (CAPA 2026-11-23): the component the model places vs the list row's component_id
    bom_p = rp.model_rev_file(folder, f"{prefix}bom-model.csv")
    prow, pinfo = part_changes(man, _csv(bom_p) if bom_p.is_file() else [], {n: _list(n) for n in PART_LISTS})
    rows += prow
    info += pinfo

    counts = Counter(sp["line_no"] for sp in spools)
    spool_table = []
    for ln in sorted(set(lines) | set(counts)):
        if ln in OFF_SKID:
            state = "off skid"
        elif ln not in lines:
            state = "NOT ON LIST"
        elif ln in line_objects:
            state = "routed" if counts.get(ln) else "components only"
        else:
            state = "NOT ROUTED"
        spool_table.append({"line_no": ln, "spools": counts.get(ln, 0), "on_line_list": "yes" if ln in lines else "no",
                            "state": state})
    return {"rows": rows, "info": info, "spool_table": spool_table, "n_list_tags": len([t for t in expected if t not in OFF_SKID]),
            "n_model_tags": len(model_tags), "n_spools": len(spools), "n_welds": len(seen)}


def write(delta: dict, out: Path, title: str) -> tuple[Path, Path]:
    """Write list-delta.csv and list-delta.md into `out`."""
    out.mkdir(parents=True, exist_ok=True)
    p_csv, p_md = out / "list-delta.csv", out / "list-delta.md"
    with open(p_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(delta["rows"])
    L = [f"# List delta: {title}", "",
         "Generated by `harness/lib/list_delta.py`; do not hand-edit. The model leads; a "
         "non-empty delta becomes a list update or a P&ID revision request at close-out (`harness/scripts/closeout.py`).",
         "",
         f"**{len(delta['rows'])} delta row(s).** {delta['n_list_tags']} on-skid list tags, {delta['n_model_tags']} model tags, "
         f"{delta['n_spools']} spools, {delta['n_welds']} welds.", ""]
    if delta["rows"]:
        L += ["| kind | subject | line | model | lists | detail |", "|---|---|---|---|---|---|"]
        L += [f"| {r['kind']} | {r['subject']} | {r['line_no']} | {r['model']} | {r['lists']} | {r['detail']} |" for r in delta["rows"]]
        L.append("")
    L += ["## Spools per line (model) vs line-list.csv", "", "| line | spools | on line list | state |", "|---|---|---|---|"]
    L += [f"| {r['line_no']} | {r['spools']} | {r['on_line_list']} | {r['state']} |" for r in delta["spool_table"]]
    L += ["", "## Information (not delta rows)", ""] + ([f"- {i}" for i in delta["info"]] or ["- none"])
    p_md.write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")
    return p_csv, p_md
