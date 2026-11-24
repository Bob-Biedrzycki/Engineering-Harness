"""list_from_model - at acceptance the model leads: write a build's list delta into the <project>/03_Working_Design/PID/02_Tag_Lists lists.

Bob, chat, 2026-10-16, after the first Rev Z acceptance run stopped on 26 items (every list difference was one of his
own fast edits): "This process was supposed to work in a way that we made model edits, then when accepted, all of the
lists and other drawings get updated based on the model." So harness/scripts/model_accept.py calls apply() on its
preflight build before the drawings are drawn, and the drawings follow the model.

One rule per list delta kind (harness/lib/list_delta.py), the same every time:
    line-size               line-list size_od_in (and gauge) set to the model's spool size
    model-line-not-on-list  a line-list row from the model's spools: size, wall, material, from / to, service from the
                            spool note; every field the model does not carry is 'unknown'
    model-tag-not-on-list   a valve-list or instrument-list row (by the BOM class): tag, line, size, the part the model
                            uses (type, and component_id where the list has that column); the rest 'unknown'
    list-tag-not-in-model   the row is removed from its list, the tag is dropped from other rows' from / to lists,
                            and from each service text the comma-separated phrase naming it
    line-not-routed         the row is removed only when its from or to tag was removed with it (a relief line with its
                            relief valve);
                            otherwise it stays, as a note
    tag-part-changed        the tag stays, its part changed (CAPA 2026-11-23). The row's component_id becomes the
                            model's; the columns the component register can give are filled from the placed
                            component's register row (harness/lib/components.py, the current row, else its latest);
                            every other column that described the old part becomes 'unknown'; notes gain
                            "part <old> -> <new> from model <revision> (...)". When the row had no component id
                            ('unknown' or blank) only component_id and the register columns that read 'unknown' are
                            written: nothing else on the row was said to describe another part.
                            Register mapping (list column <- register columns), only where they mean the same thing:
                                type                <- category - manufacturer model, part number <part_number>
                                process_connection  <- end_connections
                            Kept as they are (they belong to the tag and the line, not the part): tag, tag_rev_*,
                            size_od_in (the line size at the tag), line_no, line_no_or_equip, pid_sheet, notes
                            (appended), component_id (written). Every other column is the old part's and becomes
                            'unknown': on today's lists valve-list actuator, feedback, solenoid, orientation,
                            air_connection; instrument-list range, signal, mounting_orientation, straight_run_req,
                            access_note. A register value of 'unknown', or no register row, gives 'unknown'
                            (hard rule 1: nothing is filled in that no record gives).
After the delta, whatever it held (REVW-001 C-11, 2026-11-23): a list row whose text cites a fast build has that
citation replaced by "model <revision>" and the joints and spools it names checked against the accepted build
(retire_fast_build_text).
Each change is one line of the returned report, recorded in the revision description. git history keeps the old rows.
Rows no rule touches are written back as they were read (same columns, same line endings).
"""
from __future__ import annotations

import csv
import io
import json
import re
from pathlib import Path

import repo_paths as rp

LISTS = {"line": "line-list.csv", "valve": "valve-list.csv", "instrument": "instrument-list.csv"}
# tag-part-changed: the columns that belong to the tag and the line, not to the part (left as they are)
KEEP = {"tag", "size_od_in", "line_no", "line_no_or_equip", "pid_sheet", "notes", "component_id"}
KEEP_PREFIX = ("tag_rev_",)


def _known(v) -> bool:
    s = str(v or "").strip()
    return bool(s) and not s.lower().startswith("unknown")


def register_row(cid: str) -> dict | None:
    """The placed component's register row: the current one, else the latest; None when it is in no register."""
    import components
    rows = [r for r in components.rows() if r.get("component_id") == cid]
    cur = [r for r in rows if r.get("status", "").lower() in ("", "current")]
    return (cur or rows or [None])[-1]


def from_register(reg: dict | None) -> dict[str, str]:
    """{list column: value} for the columns the register can give (mapping in the module docstring)."""
    if not reg:
        return {"type": "unknown", "process_connection": "unknown"}
    head = " ".join(v for v in (reg.get("manufacturer"), reg.get("model")) if _known(v))
    typ = " - ".join(v for v in (reg.get("category") if _known(reg.get("category")) else "", head) if v)
    if typ and _known(reg.get("part_number")):
        typ += f", part number {reg['part_number']}"
    return {"type": typ or "unknown",
            "process_connection": reg["end_connections"] if _known(reg.get("end_connections")) else "unknown"}


def _part_columns(fields: list[str]) -> list[str]:
    return [c for c in fields if c not in KEEP and not c.startswith(KEEP_PREFIX)]


def _read(name: str) -> tuple[list[str], list[dict], str]:
    p = rp.DATA / name
    raw = p.read_bytes().decode("utf-8-sig")
    nl = "\r\n" if raw.split("\n", 1)[0].endswith("\r") else "\n"
    r = csv.DictReader(io.StringIO(raw, newline=""))
    return list(r.fieldnames or []), list(r), nl


def _write(name: str, fields: list[str], rows: list[dict], nl: str) -> None:
    buf = io.StringIO(newline="")
    w = csv.DictWriter(buf, fieldnames=fields, lineterminator=nl)
    w.writeheader()
    w.writerows(rows)
    (rp.DATA / name).write_bytes(buf.getvalue().encode("utf-8"))


def _rows(p: Path) -> list[dict]:
    if not p.is_file():
        return []
    with open(p, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _drop_phrases(text: str, tags: set[str]) -> str:
    """Remove from a service text each comma-separated phrase that names one of the tags."""
    if not text or not tags:
        return text
    pat = re.compile(r"\b(" + "|".join(re.escape(t) for t in sorted(tags)) + r")\b")
    parts = re.split(r"(, )", text)
    out, skip_sep = [], False
    for p in parts:
        if p == ", ":
            if not skip_sep and out:
                out.append(p)
            skip_sep = False
            continue
        if pat.search(p) and not re.search(r"[;:]", p):
            skip_sep = True
            if out and out[-1] == ", ":
                out.pop()
            continue
        out.append(p)
    return "".join(out)


def _drop_tokens(cell: str, gone: set[str]) -> str:
    toks = [t for t in (cell or "").split(";")]
    keep = [t for t in toks if t.strip() not in gone]
    return ";".join(keep) if len(keep) != len(toks) else cell


FAST_CITE = re.compile(r"\bfast build (rev[A-Za-z]+-(?:fast|full)-\d{3})\b")
_JOINT = re.compile(r"\bJ\d{3}\b")
_SPOOL = re.compile(r"\b[A-Z]{1,5}-\d{2,4}-SP\d{2}\b")


def retire_fast_build_text(build: Path, revision: str) -> list[str]:
    """A list row written between acceptances may cite the working copy it described ("fast build revC-fast-028:
    vertical, flow down ..."). Bob asked for 16 valve rows that way on 2026-11-23, and on the question of that text
    said (chat, 2026-11-23, REVW-001 C-11): "Yes, rewrite them." So at acceptance every such citation becomes
    "model <revision>", the accepted design the row now describes; a fast build is never the citation of a list
    that is the formal input. The joint and spool ids named in the same passage (up to the next "||", which starts
    the row's history) are checked against the build being accepted, and one that it does not have is named in the
    report line, which goes into the revision description. Nothing else in the row changes; a list with no such
    citation is not rewritten. Returns one report line per row changed."""
    joints = {r.get("joint_id", "") for r in _rows(build / "clamp-schedule.csv")}
    spools = {r.get("spool_id", "") for r in _rows(build / "spool-list.csv")}
    report: list[str] = []
    for name in LISTS.values():
        if not (rp.DATA / name).is_file():
            continue
        fields, rows, nl = _read(name)
        touched = False
        for row in rows:
            cited: list[str] = []
            missing: set[str] = set()
            for c in fields:
                v = row.get(c) or ""
                if not FAST_CITE.search(v):
                    continue
                parts = v.split("||")
                for i, part in enumerate(parts):
                    found = FAST_CITE.findall(part)
                    if not found:
                        continue
                    cited += [b for b in found if b not in cited]
                    if joints:
                        missing |= {j for j in _JOINT.findall(part) if j not in joints}
                    if spools:
                        missing |= {s for s in _SPOOL.findall(part) if s not in spools}
                    parts[i] = FAST_CITE.sub(f"model {revision}", part)
                row[c] = "||".join(parts)
            if cited:
                touched = True
                who = row.get("tag") or row.get("line_no") or "?"
                report.append(f"{name} {who}: text that cited fast build {', '.join(cited)} now cites model {revision}"
                              + (f"; it names {', '.join(sorted(missing))}, which this build does not have: "
                                 "the row's text needs a look" if missing else ""))
        if touched:
            _write(name, fields, rows, nl)
    return report


def apply(build: Path, revision: str) -> list[str]:
    """Write the build's list delta into the <project>/03_Working_Design/PID/02_Tag_Lists lists, then retire any
    fast-build citation in a list row (retire_fast_build_text). Returns one report line per change."""
    return _apply_delta(build, revision) + retire_fast_build_text(build, revision)


def _apply_delta(build: Path, revision: str) -> list[str]:
    delta = _rows(build / "list-delta.csv")
    if not delta:
        return []
    spools = _rows(build / "spool-list.csv")
    bom = {r["item"]: r for r in _rows(build / "bom-model.csv")}
    man = {}

    def walk(x):
        if isinstance(x, dict):
            if isinstance(x.get("tag"), str) and x["tag"] not in man:
                man[x["tag"]] = x
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    if (build / "manifest.json").is_file():
        walk(json.loads((build / "manifest.json").read_text(encoding="utf-8")))
    lists = {k: _read(v) for k, v in LISTS.items()}
    changed: set[str] = set()
    lines_f, lines, _ = lists["line"]
    by_line = {r["line_no"]: r for r in lines}
    src = f"from model {revision} (model_accept.py; Bob, chat, 2026-10-16: lists follow the model)"
    report: list[str] = []

    def sp_of(ln: str) -> list[dict]:
        return [s for s in spools if s.get("line_no") == ln]

    gone_tags: set[str] = set()
    for d in delta:
        kind, subj = d["kind"], d["subject"]
        if kind == "line-size" and subj in by_line:
            sp = sp_of(subj)
            if sp:
                row = by_line[subj]
                old = row.get("size_od_in", "")
                row["size_od_in"] = sp[0]["od_in"]
                if sp[0].get("wall_in"):
                    row["gauge"] = f"{sp[0]['wall_in']} in wall"
                row["notes"] = (row.get("notes", "") + f" || size {old} -> {sp[0]['od_in']} in {src}").strip(" |")
                changed.add("line")
                report.append(f"line-list {subj}: size {old} -> {sp[0]['od_in']} in")
        elif kind == "model-line-not-on-list" and subj not in by_line:
            sp = sorted(sp_of(subj), key=lambda s: s["spool_id"])
            if not sp:
                continue
            row = {k: "unknown" for k in lines_f}
            mat = sp[0].get("material", "")
            row.update({"line_no": subj, "size_od_in": sp[0]["od_in"], "gauge": f"{sp[0]['wall_in']} in wall",
                        "material": "316L" if "316L" in mat else (mat or "unknown"),
                        "spec": mat.replace(" 316L", "") if mat else "unknown",
                        "from_tag": sp[0].get("from", "") or "unknown", "to_tag": sp[-1].get("to", "") or "unknown",
                        "service": sp[0].get("notes", "") or "unknown", "pid_sheet": "1", "segment_ref": subj,
                        "notes": f"NEW {src}; spools {', '.join(s['spool_id'] for s in sp)}",
                        "pid_label": "DRAIN" if "drain" in (sp[0].get("notes", "") + subj).lower() else ""})
            lines.append(row)
            by_line[subj] = row
            changed.add("line")
            report.append(f"line-list {subj}: added ({row['size_od_in']} in, {row['from_tag']} to "
                          f"{row['to_tag'][:60]})")
        elif kind == "model-tag-not-on-list":
            b, m = bom.get(subj, {}), man.get(subj, {})
            cls = (m.get("kind") or b.get("class") or "").lower()
            key = "instrument" if cls.startswith("instr") else "valve"
            f, rows, _ = lists[key]
            if any(r.get("tag") == subj for r in rows):
                continue
            starts = [s for s in spools if s.get("from") == subj]
            ends = [s for s in spools if s.get("to") == subj]
            line = m.get("line") or (ends[0]["line_no"] if ends else starts[0]["line_no"] if starts else "unknown")
            size = starts[0]["od_in"] if starts else ends[0]["od_in"] if ends else "unknown"
            row = {k: "unknown" for k in f}
            row["tag"] = subj
            if "size_od_in" in f:
                row["size_od_in"] = size
            if "line_no" in f:
                row["line_no"] = line
            if "line_no_or_equip" in f:
                row["line_no_or_equip"] = line
            row["type"] = m.get("source") or b.get("source") or "unknown"
            if "component_id" in f:
                import list_delta
                row["component_id"] = list_delta.placed_component(m.get("source") or b.get("source")) or "unknown"
            row["pid_sheet"] = "1"
            row["notes"] = (f"NEW {src}"
                            + (f"; outlet line {starts[0]['line_no']}" if starts and starts[0]["line_no"] != line else "")
                            + (f"; model note: {m['note']}" if m.get("note") else ""))
            rows.append(row)
            changed.add(key)
            report.append(f"{LISTS[key]} {subj}: added (line {line}, {size} in, {row['type'][:70]})")
        elif kind == "tag-part-changed":
            new = d["model"].strip()
            for key in ("valve", "instrument"):
                f, rows, _ = lists[key]
                row = next((r for r in rows if r.get("tag") == subj), None)
                if row is None or "component_id" not in f:
                    continue
                old = (row.get("component_id") or "").strip() or "unknown"
                had = _known(old)
                reg = register_row(new)
                for c, v in from_register(reg).items():
                    if c in f and (had or not _known(row.get(c))):
                        row[c] = v
                if had:
                    for c in _part_columns(f):
                        if c not in ("type", "process_connection"):
                            row[c] = "unknown"
                row["component_id"] = new
                row["notes"] = (row.get("notes", "") + f" || part {old} -> {new} {src}").strip(" |")
                changed.add(key)
                report.append(f"{LISTS[key]} {subj}: part {old} -> {new}"
                              + ("" if reg else " (not in a component register: type and connection unknown)")
                              + ("; the old part's columns set to unknown" if had else ""))
                break
        elif kind == "list-tag-not-in-model":
            for key in ("valve", "instrument"):
                f, rows, nl = lists[key]
                keep = [r for r in rows if r.get("tag") != subj]
                if len(keep) != len(rows):
                    lists[key] = (f, keep, nl)
                    gone_tags.add(subj)
                    changed.add(key)
                    report.append(f"{LISTS[key]} {subj}: removed (not in the model)")
    # lines that only served a removed tag go with it; then the removed names leave the other rows
    gone_lines = set()
    for d in delta:
        if d["kind"] == "line-not-routed" and d["subject"] in by_line:
            row = by_line[d["subject"]]
            if {row.get("from_tag", "").strip(), row.get("to_tag", "").strip()} & gone_tags:
                gone_lines.add(d["subject"])
                report.append(f"line-list {d['subject']}: removed (its {', '.join(sorted(gone_tags))} is out of "
                              f"the model, no spool on it)")
    if gone_lines:
        lines[:] = [r for r in lines if r["line_no"] not in gone_lines]
    gone = gone_tags | gone_lines
    if gone:
        for r in lines:
            for c in ("from_tag", "to_tag"):
                new = _drop_tokens(r.get(c, ""), gone)
                if new != r.get(c, ""):
                    report.append(f"line-list {r['line_no']} {c}: {', '.join(sorted(gone))} dropped")
                    r[c] = new
            new = _drop_phrases(r.get("service", ""), gone)
            if new != r.get("service", ""):
                report.append(f"line-list {r['line_no']} service: the phrase naming {', '.join(sorted(gone))} dropped")
                r["service"] = new
    if gone_lines or any(ln.startswith("line-list") for ln in report):
        changed.add("line")
    lists["line"] = (lines_f, lines, lists["line"][2])
    for key in sorted(changed):
        f, rows, nl = lists[key]
        _write(LISTS[key], f, rows, nl)
    return report
