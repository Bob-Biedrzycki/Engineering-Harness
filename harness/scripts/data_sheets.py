"""data_sheets.py - equipment, instrument and valve data sheets, generated from a job's records.

One US Letter page per tag, laid out per harness/style-guide/README.md section 7.2 with the brand.css tokens. Every
value comes from a record, read at run time:
  - the six tag lists          the active project's (rp.DATA), or the folder the settings name   (hard rule 8)
  - the component register     the job library's, then the project's (maker, model, ratings; joined on component_id)
  - the filed model            named in the settings (location, neighbours, size as placed)
  - the datum record           a GDT-REC tolerance record the settings name (model coordinates of datums A, B, C)
  - optional overrides         a YAML file the settings name: a clean wording of a field, with its source, where the
                               list's prose does not read as a data sheet value
  - optional "who answers"     CSV files the settings name: who can answer an unknown value
A value no record gives is never estimated (hard rule 1): it prints TBD.

What prints follows the sheet-face rule (DRF-FACE-001, harness/checks/sheet_face.py; Bob, chat, 2026-11-16: a sheet
sent out may carry no internal reference). There is one sheet, the clean one: no record ids (SRC-, COMP-, Q-, H, EC-,
DEC-, rule ids), no file names, no model numbers, no people's names, no "unknown". A footnote keeps only a plain
reason a reader outside CPME can act on; when none is left the cell is just TBD. Nothing is lost: every printed cell
and footnote has a row in the basis CSV (`basis` in the settings; default data-sheets.basis.csv beside the overrides
file) with the record it came from, the record's own words, the reason with its ids, who can answer, and the sheet's
sources. A text that still fails the check after scrubbing prints TBD, and its row says so.

Everything about one job is in its settings file, job/data-sheets.yaml (rp.DATA_SHEET_SETTINGS); this script holds no
job's values. A job without that file makes no generated data sheets, and the script says so.

When to run it (Bob, 2026-11-16): when a piece of equipment, an instrument or a valve is new or has changed, not on
every plan set run. The normal run compares each tag's freshly generated sheet with its last filed revision (the
date and the revision letter set aside) and reports every tag as unchanged, changed, new or no longer in the lists;
only the changed and new sheets are written to the preview folder. It never files anything.

    python harness/scripts/data_sheets.py                    # compare every tag; preview the changed and new ones
    python harness/scripts/data_sheets.py --all              # preview every tag, changed or not
    python harness/scripts/data_sheets.py --tags <TAG> <TAG> # only these tags
    python harness/scripts/data_sheets.py --html-only        # no PDF (faster; no page check)
    python harness/scripts/data_sheets.py --fast --request "<the words it answers>" [--tags ...]   # fast drawings
    python harness/scripts/data_sheets.py --file --tags <TAG> --note "<32 characters>" --description "<what changed>"

Fast drawings (plan set round 2, brief D2): numbered working copies of every sheet named (all with no --tags), each in
<level>/03_Working_Design/Exports/Fast_Drawings/<DOC>/<DOC>-<base>-fast-<nnn>/ (<base> rev<X> for the last filed letter,
else first), HTML + PDF, never overwritten, not filed, with a row in that folder's fast-log.md and the sheet-face
result. The revision cell shows the base letter and FAST-<nnn> - NOT ISSUED.

File names (Bob, 2026-11-16: generated data sheets are "labeled in the file name as CPME Generated"): a generated
sheet files as <DOC-ID>-rev<X>/<DOC-ID>-rev<X>-CPME-Generated.html and .pdf, read-only, with a revisions.csv row per
file (the columns of harness/cad-lib/revfile.py). Revisions filed before the label keep their names (TR-08).
--file files only the tags named, each as its next letter, and refuses a tag whose sheet is unchanged since its last
filed revision. Filing is the engineer's word (BR#1: say what, how, why now and what changes before asking).

Exit codes: 0 done; 1 a sheet is not one page, or filing stopped; 2 refused (no settings, settings unreadable, no
project to read the lists from, a tag that is not in the lists).
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import html
import json
import math
import os
import re
import shutil
import stat
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists()) / "harness" / "lib"))
import repo_paths as rp  # noqa: E402
from model_build import next_letter  # noqa: E402

REPO = rp.REPO
LOGO = rp.HARNESS / "style-guide" / "assets" / "cpme-logo.svg"
BRAND_YAML = rp.HARNESS / "style-guide" / "brand.yaml"
EDGE = Path(os.environ.get("CPME_EDGE", r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"))
GENERATED_LABEL = "CPME-Generated"     # Bob, 2026-11-16: "labeled in the file name as CPME Generated"
MANIFEST_COLS = ["document_id", "revision", "file", "file_date", "sha256", "bytes", "source", "notes", "description"]
MAX_BLOCK_NOTE = 32                    # as revfile.py: the revision note fits the revision block
SOFT_LIMIT = 230                       # characters of whole clauses per cell; open clauses are kept beyond it


class Refused(Exception):
    """A plain message for the person running the script; exit 2, no traceback."""


# ------------------------------------------------------------------------------------------------ settings
@dataclass
class ModelRef:
    model_id: str = ""
    document_id: str = ""
    level: str = "job"
    revision: str = ""                 # empty: the latest filed revision
    same_design_as: dict = field(default_factory=dict)


@dataclass
class Settings:
    path: Path
    doc_prefix: str
    file_to: str                       # "job" (the typicals' drawings) or "project" (the active project's)
    subtitle: str = ""
    lists: Path | None = None
    model: ModelRef | None = None
    datum_record: Path | None = None
    overrides: Path | None = None
    answers: list[Path] = field(default_factory=list)
    preview_dir: Path | None = None
    valve_titles: dict = field(default_factory=dict)
    no_line_text: str = "mounted on equipment (no line, no service class)"
    text_rules: dict = field(default_factory=dict)
    basis: Path | None = None          # the basis CSV: what each printed cell came from (never printed)

    @property
    def basis_csv(self) -> Path:
        if self.basis:
            return self.basis
        return (self.overrides.parent if self.overrides else self.path.parent) / "data-sheets.basis.csv"


def _repo_path(v) -> Path | None:
    if not v:
        return None
    p = Path(str(v))
    return p if p.is_absolute() else REPO / p


def load_settings(path: Path | None = None) -> Settings:
    """The job's data sheet settings. Refused (with the reason) when the job has none or they cannot be read."""
    path = Path(path or rp.DATA_SHEET_SETTINGS)
    if not path.is_file():
        raise Refused(f"this job has no data sheet settings ({path.name} is not in {path.parent}); a job that makes "
                      "generated data sheets names its document prefix, filing level and records there "
                      "(harness/scripts/data_sheets.py docstring)")
    import yaml
    try:
        d = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        raise Refused(f"{path.name} is not readable YAML: {e}") from None
    if not isinstance(d, dict):
        raise Refused(f"{path.name} must be a mapping of settings")
    missing = [k for k in ("doc_prefix", "file_to") if not d.get(k)]
    if missing:
        raise Refused(f"{path.name} lacks {', '.join(missing)}")
    if d["file_to"] not in ("job", "project"):
        raise Refused(f"{path.name} file_to is {d['file_to']!r}; it is job or project")
    m = d.get("model")
    model = None
    if isinstance(m, dict) and m.get("model_id") and m.get("document_id"):
        model = ModelRef(str(m["model_id"]), str(m["document_id"]), str(m.get("level", "job")),
                         str(m.get("revision") or ""), dict(m.get("same_design_as") or {}))
    answers = d.get("answers") or []
    return Settings(path=path, doc_prefix=str(d["doc_prefix"]), file_to=d["file_to"],
                    subtitle=str(d.get("subtitle") or ""), lists=_repo_path(d.get("lists")), model=model,
                    datum_record=_repo_path(d.get("datum_record")), overrides=_repo_path(d.get("overrides")),
                    answers=[_repo_path(a) for a in (answers if isinstance(answers, list) else [answers])],
                    preview_dir=_repo_path(d.get("preview_dir")), valve_titles=dict(d.get("valve_titles") or {}),
                    no_line_text=str(d.get("no_line_text") or Settings.no_line_text),
                    text_rules=dict(d.get("text_rules") or {}), basis=_repo_path(d.get("basis")))


def drawings_root(cfg: Settings) -> Path:
    """Where the sheets file: CPME_DRAWINGS_ROOT (a test's scratch folder), else the job's or the project's drawings."""
    if os.environ.get("CPME_DRAWINGS_ROOT"):
        return Path(os.environ["CPME_DRAWINGS_ROOT"])
    if cfg.file_to == "job":
        return rp.JOB_DRAWINGS
    if not rp.HAS_PROJECT:
        raise Refused(f"{cfg.path.name} files data sheets at project level, and the job has no project yet")
    return rp.DRAWINGS


def work_root(cfg: Settings) -> Path:
    if cfg.preview_dir:
        return cfg.preview_dir
    return (rp.JOB_WORK if cfg.file_to == "job" or not rp.HAS_PROJECT else rp.WORK) / "data-sheets"


def generated_name(doc_id: str, rev: str, ext: str) -> str:
    """<DOC-ID>-rev<X>-CPME-Generated<ext>: starts <DOC-ID>-rev<X> like every filed file (rp.rev_folder)."""
    return f"{rp.rev_folder(doc_id, rev)}-{GENERATED_LABEL}{ext}"


# ------------------------------------------------------------------------------------------------ text rules
# The harness's own record conventions (source ids SRC-/COMP-, questions Q-, HOLDs H, DEC-, EC-, PRR-, dates, Bob's
# chat words, repo paths). A job adds its own record words under text_rules in its settings (each a regex list):
#   source_id_prefixes  id prefixes of source records besides SRC and COMP (an id with its page refs is dropped)
#   source_note         a (...) group carrying one is a source note: dropped from the cell
#   drop_inline         removed from a value before its clauses are read (after the source ids)
#   history             a clause carrying one is history: left in the record
#   open_ids            ids an "open" footnote names besides Q-, H, EC-, PRR-, A-
#   source_tokens       removed from a footnote's text, with the source ids and paths
#   reason_strip        removed from a footnote's text after the source tokens
#   reason_drop         a footnote clause carrying one is dropped
#   leftover            record words that should never reach a cell (counted in the preview index only)
OPEN_RX = re.compile(r"(?i)\b(unknown|pending|not resolved|not set|tbd|disposition open)\b|\bOPEN\b")
ABBREV = re.compile(r"\b(incl|approx|min|max|dia|No|nom|std|e\.g|i\.e)\.\s")
_PAGES = r"(?:\s*pp?\.?\s?\d+(?:[-–]\d+)?(?:,\s*p?\.?\s?\d+)*)?"


class R:
    """The compiled text rules (configure() sets them from the job's settings)."""
    REF_IN_PAREN = INLINE = HIST_CLAUSE = IDS_RX = SRC_TOKENS = REASON_STRIP = REASON_DROP = LEFTOVER = None


def configure(text_rules: dict | None = None) -> None:
    t = {k: list(v or []) for k, v in (text_rules or {}).items()}
    ids = "|".join(["SRC", "COMP"] + t.get("source_id_prefixes", []))
    alt = lambda base, extra: "|".join([b for b in [base] if b] + extra)
    R.REF_IN_PAREN = re.compile(alt(
        "|".join(f"{p}-\\d" for p in ids.split("|")) +
        r"|\bRev [A-Z]{1,2}\b|\bline \d+\b|\bpp?\.? ?\d|\bchat\b|\d{4}-\d{2}-\d{2}|\bQ-\d|\bH\d\b|DEC-\d|\bA-\d+|EC-\d|"
        r"\.(md|csv|yaml|pdf|stp|step)\b|\bsheet \d|job/|harness/|manifest|register|decod|to confirm|PRR-|"
        r"\bX -?\d|\bY -?\d|\bZ -?\d|supplier drawing|layer |Bob\b|STEP\b|model\b|option [A-Z]\b|vendor STEP",
        t.get("source_note", [])), re.I)
    R.INLINE = [
        re.compile(r"\s*-?\s*\b(?:SELECTED|CONFIRMED|ACCEPTED|APPROVED)\b[^,;()]*?\d{4}-\d{2}-\d{2}"),
        re.compile(r",?\s*(?:CONFIRMED|confirmed|approved|accepted|chosen|set) by Bob[^,;]*"),
        re.compile(r"\s*\(?Bob,? (?:chat,? )?\d{4}-\d{2}-\d{2}[^);]*\)?"),
        re.compile(rf"\s*\b(?:{ids})-\d{{4}}(?:\s*Rev [A-Z]+)?{_PAGES}"),
        *[re.compile(x) for x in t.get("drop_inline", [])],
        re.compile(r"\s*\bsheet \d+(?: sect \d+)?\b,?"),
        re.compile(r"^as modell?ed(?: at [^:]*)?:\s*", re.I),
        re.compile(r"\s*\((?:\s*[,;]?\s*)\)"),
    ]
    R.HIST_CLAUSE = re.compile(alt(r"\bchat\b|code of record|\bwas\b|History:|\d{4}-\d{2}-\d{2}|\bPRR-|\bDEC-\d|"
                                   r"job/|harness/|\.md\b|earlier|retired|^\s*STEPs?\b", t.get("history", [])), re.I)
    R.IDS_RX = re.compile(r"\b(" + alt(r"Q-\d{2,4}|H\d{1,2}|HOLD H\d{1,2}|EC-\d{2}|PRR-\d{2}|A-\d{1,3}",
                                       t.get("open_ids", [])) + r")\b")
    R.SRC_TOKENS = re.compile(alt(
        rf"\s*\b(?:{ids})-\d{{4}}(?:\s*Rev [A-Z]+)?(?:\s*(?:cut sheet\s*)?pp?\.?\s?\d+(?:[-–]\d+)?(?:,\s*p?\.?\s?\d+)*)?"
        r"|\s*(?:job|harness)/[^\s,;)]+|\s*\bsheet \d+(?: sect \d+)?\b:?"
        r"|\s*\(?Bob,? (?:chat,? )?\d{4}-\d{2}-\d{2}[^);]*\)?|\s*\bcut sheet,? \d+ pp\b",
        t.get("source_tokens", [])))
    R.REASON_STRIP = [re.compile(x) for x in t.get("reason_strip", [])]
    R.REASON_DROP = re.compile(alt(r"\bwas\b", t.get("reason_drop", [])))
    R.LEFTOVER = re.compile(alt(r"\bchat\b|\|\||\bSRC-\d{4}\b|job/|harness/|\(\s*:|,\)", t.get("leftover", [])))


configure()


# ------------------------------------------------------------------------------------------------ sheet face
# What may print (DRF-FACE-001). The check itself is harness/checks/sheet_face.py; this script scrubs a text to it and,
# when a text still fails, prints TBD and keeps the words in the basis CSV.
TBD = "TBD"


def _load_sheet_face():
    if "sheet_face" in sys.modules:
        return sys.modules["sheet_face"]
    import importlib.util
    spec = importlib.util.spec_from_file_location("sheet_face", rp.HARNESS / "checks" / "sheet_face.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["sheet_face"] = mod
    spec.loader.exec_module(mod)
    return mod


SF = _load_sheet_face()
# record words the check does not name but a reader outside CPME cannot act on (who answers, the settings, a register)
_WHO = re.compile(r"(?i)[;,]?\s*\banswers?:\s*[^;)]*")
_RECORD_WORDS = re.compile(r"(?i)\b(?:in|from|per) the (?:component )?register\b|\bdata sheet settings\b|"
                           r"\bthe filed model\b|\bthe tag lists?\b|\b(?:equipment|instrument|valve|line|motor-load)-list\b")
_UNACTIONABLE = re.compile(r"(?i)^(?:no record gives it yet|open|unknown|tbd|not given|none)\.?$")


def face_ok(text: str) -> bool:
    return not SF.check_text(text or "")


class _Fails:
    """A 'regex' for _drop_parens: a bracketed group fails when the sheet-face check finds anything in it."""
    @staticmethod
    def search(s: str) -> bool:
        return bool(SF.check_text(re.sub(r"(?i)\bunknown\b", TBD, s)))


_LEAD_ID = re.compile(r"^\s*(?:HOLD\s+)?(?:Q|RFI|EC|DEC|PRR)-\d{2,4}\b[\s:,-]*|^\s*(?:HOLD\s+)?H\d{1,2}\b[\s:,-]*")
# a reference hung on a clause by a comma or 'per / see / by / under': it goes alone, the clause stays
_HUNG_REF = re.compile(r"(?:,\s*|\s+(?:per|see|by|under)\s+)(HOLD\s+H\d{1,2}|[A-Z][A-Za-z]*(?:-[A-Z0-9]+)+|H\d{1,2})"
                       r"(?=[\s,;.)]|$)")
_MODEL_TALK = re.compile(r"(?i)\bASSUMED\b|\bmodell?ed as\b")


def scrub(text: str) -> str:
    """A text with every internal reference the sheet-face check names taken out, by whole pieces so no sentence is
    left broken: a bracketed group that carries one goes; an id that leads a clause goes; a clause that still
    carries one (a name or a rule id inside the sentence) goes whole. 'unknown' becomes TBD; who answers and record
    words go. May come back empty; callers gate with face_ok()."""
    v = _WHO.sub("", text or "")
    v = _RECORD_WORDS.sub("", v)
    v = _drop_parens(v, _Fails)
    out = []
    for c in clauses(v):
        c = _LEAD_ID.sub("", re.sub(r"(?i)\bunknown\b", TBD, c))
        c = _HUNG_REF.sub(lambda m: "" if _Fails.search(m.group(1)) else m.group(0), c)
        c = _tidy(re.sub(r"\(\s*(?:and|or|,|;|\s)*\)", "", c))
        if c and not SF.check_text(c) and not _MODEL_TALK.search(c):
            out.append(c)
    return _tidy("; ".join(out))


def plain_reason(text: str) -> str:
    """A footnote's reason as it may print: scrubbed, and empty when nothing a reader outside CPME can act on is
    left (orchestrator, 2026-11-16: 'if it has none, the cell is just TBD')."""
    v = scrub(text)
    v = re.sub(r"(?i)^(?:open:\s*)", "Open: ", v).strip(" :;,")
    if not v or _UNACTIONABLE.match(v) or not face_ok(v) or not re.search(r"[A-Za-z]{3}", v):
        return ""
    return v[:1].upper() + v[1:]


# ------------------------------------------------------------------------------------------------ records
def read_csv(p: Path) -> list[dict]:
    with open(p, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def read_overrides(path: Path | None) -> dict:
    """{"<TAG or COMP-id>": {"<field label>": {"value": ..., "reason": ..., "source": ...}}}."""
    if not path or not path.is_file():
        return {}
    import yaml
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def brand_one_line() -> str:
    for line in BRAND_YAML.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("one_line:"):
            return line.split(":", 1)[1].strip().strip('"')
    return "CPME USA LLC"


def who_answers(paths: list[Path]) -> dict:
    """(record file, row id, column) -> (waits on, who can answer), from the answers CSVs the settings name.
    Columns: file (the record; component-register.csv when absent and the id is a component), tag | component_id |
    id, column, waits_on, who_can_answer."""
    out = {}
    for p in paths:
        if not p or not p.is_file():
            continue
        for r in read_csv(p):
            key = next((k for k in ("tag", "component_id", "id") if k in r), None)
            if not key:
                continue
            rec = r.get("file") or ("component-register.csv" if key == "component_id" else "")
            out[(Path(rec).name, r[key], r["column"])] = (r.get("waits_on", ""), r.get("who_can_answer", ""))
    return out


def find_model(ref: ModelRef | None) -> tuple[dict, str]:
    """(model facts, reason) - facts: document_id, revision, folder, manifest; {} with the reason when there is none."""
    if ref is None:
        return {}, "no filed model is named in the data sheet settings"
    base = (rp.JOB_MODELS_FILED if ref.level == "job" else rp.MODELS) / ref.model_id
    man = base / "revisions.csv"
    if not man.is_file():
        return {}, f"model {ref.model_id} has no filed revision"
    revs = [r["revision"].strip() for r in read_csv(man) if r["document_id"].strip() == ref.document_id]
    if not revs:
        return {}, f"{ref.document_id} has no filed revision"
    rev = ref.revision or max(revs, key=lambda s: (len(s), s))
    if rev not in revs:
        return {}, f"{ref.document_id} Rev {rev} is not filed"
    folder = base / rp.rev_folder(ref.document_id, rev)
    mf = rp.model_rev_file(folder, f"{rp.rev_folder(ref.document_id, rev)}-manifest.json")
    if not mf.is_file():
        return {}, f"{ref.document_id} Rev {rev} has no manifest on disk"
    return {"document_id": ref.document_id, "revision": rev, "folder": folder, "manifest": mf,
            "same_design_as": str(ref.same_design_as.get(rev, ""))}, ""


def datum_origin(path: Path | None) -> tuple[dict | None, str, str]:
    """(model coordinates of datums C (X), B (Y), A (Z), the record's document id, reason when none) from a GDT-REC
    tolerance record: datums: {A: "... model Z <n> ...", B: "... model Y <n> ...", C: "... model X <n> ..."}."""
    if not path:
        return None, "", "no datum record is named in the data sheet settings"
    if not path.is_file():
        return None, "", f"the datum record {path.name} is missing"
    import yaml
    d = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out = {}
    for letter, axis in (("A", "Z"), ("B", "Y"), ("C", "X")):
        mm = re.search(rf"model {axis} (-?\d+(?:\.\d+)?)", str((d.get("datums") or {}).get(letter, "")))
        if not mm:
            return None, "", f"the datum record {path.name} gives no model {axis} for datum {letter}"
        out[axis] = float(mm.group(1))
    return out, str(d.get("document_id") or path.stem), ""


class Records:
    def __init__(self, cfg: Settings) -> None:
        self.cfg = cfg
        lists = cfg.lists
        if lists is None:
            if not rp.HAS_PROJECT:
                raise Refused("no tag lists: the job has no project yet and the settings name no lists folder")
            lists = rp.DATA
        if not (lists / "equipment-list.csv").is_file():
            raise Refused(f"no tag lists in {lists}")
        self.equipment = read_csv(lists / "equipment-list.csv")
        self.instruments = read_csv(lists / "instrument-list.csv")
        self.valves = read_csv(lists / "valve-list.csv")
        self.lines = {r["line_no"]: r for r in read_csv(lists / "line-list.csv")}
        self.motors = read_csv(lists / "motor-load-list.csv")
        self.register: dict[str, list[dict]] = {}
        regs = [rp.JOB_COMPONENT_REGISTER] + ([rp.COMPONENT_REGISTER] if rp.HAS_PROJECT else [])
        for reg in regs:                   # the job library first, then the project's (harness/lib/components.py)
            if reg.is_file():
                for r in read_csv(reg):
                    self.register.setdefault(r["component_id"], []).append(r)
        self.model, self.model_reason = find_model(cfg.model)
        self.items: dict = {}
        self.tagged: list = []
        if self.model:
            man = json.loads(self.model["manifest"].read_text(encoding="utf-8"))
            self.items = {it["key"]: it for it in man["items"]}
            self.tagged = [it for it in man["items"] if it["kind"] in ("equipment", "valve", "instrument")
                           and it.get("bbox_in") and it.get("tag")]
            self.model_label = f"{self.model['document_id']} Rev {self.model['revision']}"
            self.same_design = self.model["same_design_as"]
        else:
            self.model_label, self.same_design = "unknown", ""
        self.datums, self.datum_doc, self.datum_reason = datum_origin(cfg.datum_record)
        self.overrides = read_overrides(cfg.overrides)
        self.who = who_answers(cfg.answers)

    def component(self, cid: str) -> dict | None:
        rows = self.register.get((cid or "").strip(), [])
        cur = [r for r in rows if r["status"].strip().lower() == "current"]
        return cur[-1] if cur else (rows[-1] if rows else None)

    def neighbours(self, tag: str, n: int = 3) -> list[str]:
        me = self.items.get(tag)
        if not me:
            return []
        c = [sum(v) / 2 for v in zip(*me["bbox_in"])]
        seen, out = {tag}, []
        for it in sorted(self.tagged, key=lambda it: math.dist(c, [sum(v) / 2 for v in zip(*it["bbox_in"])])):
            if it["tag"] not in seen:
                seen.add(it["tag"])
                out.append(it["tag"])
            if len(out) == n:
                break
        return out


# ------------------------------------------------------------------------------------------------ text to fact
def is_unknown(v) -> bool:
    return v is None or not str(v).strip() or str(v).strip().lower().startswith(("unknown", "tbd"))


def is_open(v) -> bool:
    return is_unknown(v) or bool(OPEN_RX.search(str(v)))


def _drop_parens(v: str, rx) -> str:
    out, buf, depth = [], "", 0
    for ch in v:
        if ch == "(":
            if depth == 0:
                buf = ""
            depth += 1
        if depth:
            buf += ch
        else:
            out.append(ch)
        if ch == ")" and depth:
            depth -= 1
            if depth == 0:
                if rx.search(buf):
                    while out and out[-1] == " ":
                        out.pop()
                else:
                    out.append(buf)
    if depth:
        out.append(buf)
    return "".join(out)


def _tidy(v: str) -> str:
    v = re.sub(r"\s+", " ", v)
    v = re.sub(r"\s+([,;.:)])", r"\1", v)
    v = re.sub(r"([,;])\s*[,;]+", r"\1", v)
    v = re.sub(r"[,;:]\s*\)", ")", v)
    v = re.sub(r"\(\s*[,;:.]?\s*\)", "", v)
    v = re.sub(r"\(\s*[,;:]\s*", "(", v)
    if v.count(")") > v.count("("):            # a closing bracket whose opening was a dropped source note
        while v.count(")") > v.count("(") and ")" in v:
            i = v.rfind(")")
            v = v[:i] + v[i + 1:]
    if v.count("(") > v.count(")"):
        v = v + ")"
    v = re.sub(r"\s+(?:per|or)(?=\s*[;,)]|$)", "", v)        # never 'in': it is the inch unit
    v = re.sub(r"\(\s*cut sheet;\s*", "(", v)
    v = re.sub(r"\(\s+'", "('", v)
    v = re.sub(r"\s+or\s*/\s*", " ", v)
    v = re.sub(r"\s*/\s*(?=[;,)]|$)", "", v)
    v = v.strip(" ,;:")
    v = re.sub(r"^-\s+", "", v)            # a dash that led a dropped clause; a minus sign before a number stays
    return v.strip()


def clauses(v: str) -> list[str]:
    v = ABBREV.sub(lambda m: m.group(1) + "\x00 ", v)          # an abbreviation's full stop does not end a clause
    out = [c.replace("\x00", ".") for c in re.split(r";\s+|(?<=[a-z0-9)])\.\s+(?=[A-Z])", v)]
    return [c for c in out if c.strip()]


def fact(raw: str) -> str:
    """The value without its working record: history after '||', quotes, dates, source ids, history clauses. Nothing
    is cut mid-sentence; a clause that says what is still open is always kept."""
    v = (raw or "").split("||")[0]
    v = _drop_parens(v, R.REF_IN_PAREN)          # whole source notes first, so no half-stripped bracket is left
    for rx in R.INLINE:
        v = rx.sub("", v)
    cl = [_tidy(c) for c in clauses(v)]
    keep = [c for c in cl if c and not R.HIST_CLAUSE.search(c)]
    if not keep:
        keep = [c for c in cl if c][:1]
    out, n = [], 0
    for c in keep:
        if not out or n + len(c) <= SOFT_LIMIT or OPEN_RX.search(c):
            out.append(c)
            n += len(c) + 2
    v = "; ".join(out)
    if len(v) > SOFT_LIMIT * 1.6 and not OPEN_RX.search(v):     # one very long first clause: keep its first parts
        parts, acc = re.split(r",\s+", v), []
        for p in parts:
            if acc and len(", ".join(acc + [p])) > SOFT_LIMIT:
                break
            acc.append(p)
        v = ", ".join(acc)
    return _tidy(v)


def reason(raw: str) -> str:
    """Footnote text for an unknown value: what it waits on, keeping question / HOLD ids, without source paths,
    source ids, quotes, dates or history."""
    v = (raw or "").split("||")[0]
    v = re.sub(r"(?i)^\s*unknown\s*[:\-–]?\s*", "", v).strip()
    v = R.SRC_TOKENS.sub("", v)               # source ids out of the text; a bracket left empty is tidied away
    for rx in R.REASON_STRIP:
        v = rx.sub("", v)
    v = v.strip()
    if v.startswith("(") and v.endswith(")"):
        depth, whole = 0, True
        for i, ch in enumerate(v):
            depth += (ch == "(") - (ch == ")")
            if depth == 0 and i < len(v) - 1:
                whole = False
                break
        if whole:
            v = v[1:-1]
    cl = [c for c in clauses(v) if not R.REASON_DROP.search(c)]
    v = _tidy("; ".join(cl))
    v = re.sub(r"\bor in\b|\bin or\b", "", v)
    v = _tidy(v)
    v = v[:1].upper() + v[1:] if v else v
    if len(v) > 280:                       # whole clauses only, never a cut word or an ellipsis
        out = []
        for c in clauses(v):
            if out and len("; ".join(out + [c])) > 280:
                break
            out.append(c)
        v = "; ".join(out)
    return v


# ------------------------------------------------------------------------------------------------ sheet model
class Sheet:
    NOTE_IDS = re.compile(r"\b(Q-\d{2,4}|H-?\d{1,2}|EC-\d{2})\b")

    def __init__(self, rec: Records, kind: str, tag: str, title: str, listname: str):
        self.rec, self.kind, self.tag, self.title, self.list = rec, kind, tag, title, listname
        self.sections: list[tuple[str, list]] = []
        self.notes: list[str] = []
        self.open = 0
        self.sources: list[str] = [f"{listname} row {tag}"]
        self.basis: list[dict] = []        # one row per printed cell and footnote (basis CSV)
        self._pending: list[dict] = []     # cells made since the last add(): labelled there

    def note(self, text: str, record: str = "") -> int | None:
        """Number for a footnote, or None when the reason has nothing a reader outside CPME can act on (the cell is
        then just TBD). The printed words are scrubbed to the sheet-face rule; the full reason, ids included, goes to
        the basis CSV. A reason that names the same question / HOLD as an earlier note reuses its number."""
        full = (text or "").strip()
        text = plain_reason(full)
        if not text:
            return None
        ids = set(self.NOTE_IDS.findall(full))
        words = lambda s: set(re.findall(r"[a-z0-9]{3,}", s.lower())) - {"tbd", "the", "and", "open"}
        n = None
        if text in self.notes:
            n = self.notes.index(text) + 1
        else:
            for i, old in enumerate(self.notes):
                b = next((r for r in self.basis if r["field"] == f"note {i + 1}"), {})
                if ids and ids & set(self.NOTE_IDS.findall(b.get("reason", ""))):
                    n = i + 1
                    break
                a, c = words(text), words(old)       # the same reason in other words: one note
                if a and c and len(a & c) / len(a | c) >= 0.5:
                    n = i + 1
                    break
        if n is None:
            self.notes.append(text)
            n = len(self.notes)
            self.basis.append({"section": "Notes", "field": f"note {n}", "printed": text, "reason": full,
                               "record": record})
        return n

    def _keep(self, printed: str, raw: str = "", where: tuple | None = None, reason: str = "", note=None,
              who: str = "", status: str = "") -> None:
        self._pending.append({"printed": re.sub(r"<[^>]+>", "", printed), "raw": (raw or "")[:400],
                              "record": " | ".join(where) if where else "", "reason": reason, "note": note or "",
                              "who_can_answer": who, "status": status})

    def cell(self, raw, where: tuple | None = None, unit: str = "", override=None) -> str:
        """raw record text -> cell html. where = (record file, row id, column) for the who-answers lookup.
        override: a clean wording from the overrides file, {value, reason?, source}; printed as written.
        A value no record gives prints TBD; a value that fails the sheet-face check after scrubbing prints TBD and
        its basis row says why (status 'scrubbed to TBD')."""
        why = None
        if override is not None:
            if isinstance(override, dict):
                why = override.get("reason")
                if override.get("source"):
                    self.sources.append(override["source"])
                raw = override.get("value", "")
            else:
                raw = override
            raw = "" if raw is None else str(raw)
            f = raw.strip()
        else:
            raw = "" if raw is None else str(raw)
            f = None
        w = self.rec.who.get(where) if where else None
        who = (w[1] or "").strip() if w else ""          # who can answer: the basis CSV only, never the sheet
        rec_name = " | ".join(where) if where else ""
        sup = lambda n: f"<sup>{n}</sup>" if n else ""
        if is_unknown(raw) or not raw.strip():
            self.open += 1
            r = why or reason(raw) or ""
            n = self.note(r, rec_name)
            self._keep(TBD, raw, where, r, n, who, "TBD")
            return f'<span class="unk">{TBD}</span>{sup(n)}'
        f = f if f is not None else fact(raw)
        if unit and re.fullmatch(r"-?[\d.,]+", f):
            f = f"{f} {unit}"
        f_clean = scrub(f)
        if not f_clean or not face_ok(f_clean) or _UNACTIONABLE.match(f_clean):
            self.open += 1                 # nothing printable is left: TBD, the record's words kept in the basis
            n = self.note(why or reason(raw) or "", rec_name)
            self._keep(TBD, raw, where, why or "", n, who, "scrubbed to TBD")
            return f'<span class="unk">{TBD}</span>{sup(n)}'
        status = "scrubbed" if f_clean != f else ""
        f = f_clean
        if OPEN_RX.search(f):
            self.open += 1
            if why:
                r = why
            else:
                clause = next((c for c in re.split(r";\s+", f) if OPEN_RX.search(c)), f)
                ids = sorted(set(R.IDS_RX.findall(raw.split("||")[0])))
                r = f"Open: {clause}" + (f" ({', '.join(ids)})" if ids else "")
            n = self.note(r, rec_name)
            self._keep(f, raw, where, r, n, who, status or "open")
            return f'<span class="part">{html.escape(f)}</span>{sup(n)}'
        self._keep(f, raw, where, "", None, who, status)
        return html.escape(f)

    def plain(self, text: str) -> str:
        """A text the script composes itself (labels, positions): scrubbed like a record value."""
        t = scrub(text)
        t = t if face_ok(t) else TBD
        self._keep(t, text, None, "", None, "", "scrubbed" if t != text else "")
        return html.escape(t)

    def add(self, title: str, rows: list[tuple[str, str]]) -> None:
        rows = [r for r in rows if r is not None]
        self.sections.append((title, rows))
        # the cells made for these rows, in order, take the rows' labels (one cell() or plain() per row)
        made, self._pending = self._pending, []
        if len(made) >= len(rows):
            made = made[len(made) - len(rows):]
        for (label, _v), m in zip(rows, made):
            self.basis.append({"section": title, "field": label, **m})


def ov(rec: Records, key: str, label: str, comp_id: str = ""):
    """Clean wording for a field: by tag first, then by the tag's component (shared by every tag that uses it)."""
    for k in (key, comp_id):
        e = (rec.overrides.get(k) or {}).get(label) if k else None
        if e is not None:
            return e
    return None


def literature(comp: dict | None) -> str:
    if not comp or not comp.get("cut_sheet_file"):
        return ""
    return Path(comp["cut_sheet_file"]).stem.replace("_", " ")


MODELLING_TALK = re.compile(r"(?i)\bSTEP\b|layout model|filed model|\bmodell?ed\b|placed directly|credit marker|"
                            r"\bsolid\b|\bspool added\b|as placed")


def install_practice(raw: str) -> str:
    """How the part is installed per its maker: modelling notes are not installation practice. Clauses about the CAD
    model are left out; if nothing is left the value is unknown."""
    v = (raw or "").split("||")[0]
    keep = [c for c in clauses(v) if not MODELLING_TALK.search(c)]
    if not keep or is_unknown(v):
        return "unknown (the maker's installation practice is not on file)"
    return "; ".join(keep)


def held_instrument(rec: Records, comp: dict) -> dict | None:
    """The bought instrument or valve inside a CPME spool assembly: the first other component the assembly's part
    number, model or description names."""
    if not comp["manufacturer"].lower().startswith("cpme assembly"):
        return None
    for cid in re.findall(r"COMP-\d{4}", comp["part_number"] + " " + comp["model"] + " " + comp["description"]):
        if cid != comp["component_id"]:
            c = rec.component(cid)
            if c and not c["manufacturer"].lower().startswith("cpme"):
                return c
    return None


def purchased(sh: Sheet, comp: dict | None, raw_cid: str, maker: str = "", model: str = "") -> list:
    rec = sh.rec
    if comp is None:
        return [("Manufacturer", sh.cell(maker or "unknown")), ("Model", sh.cell(model or "unknown")),
                ("Component", sh.cell(raw_cid if is_unknown(raw_cid)
                                      else f"unknown (component {raw_cid} is not in the component register)"))]
    cid = comp["component_id"]
    sh.sources.append(f"component register {cid} Rev {comp['revision']}")
    lit = literature(comp)
    if lit:
        sh.sources.append(f"literature: {lit}")
    W = lambda col: ("component-register.csv", cid, col)
    inst = held_instrument(rec, comp)
    if inst:   # the instrument's own maker and model; the CPME spool on its own row
        iid = inst["component_id"]
        sh.sources.append(f"component register {iid} Rev {inst['revision']}")
        IW = lambda col: ("component-register.csv", iid, col)
        head = [
            ("Manufacturer", sh.cell(inst["manufacturer"], IW("manufacturer"), override=ov(rec, iid, "Manufacturer"))),
            ("Model", sh.cell(inst["model"], IW("model"), override=ov(rec, iid, "Model"))),
            ("Part number", sh.cell(inst["part_number"], IW("part_number"), override=ov(rec, iid, "Part number"))),
            ("Supplied as", sh.plain(f"CPME instrument spool, {fact(comp['size'])}")),   # no component number
        ]
    else:
        head = [
            ("Manufacturer", sh.cell(comp["manufacturer"], W("manufacturer"), override=ov(rec, cid, "Manufacturer"))),
            ("Model", sh.cell(comp["model"], W("model"), override=ov(rec, cid, "Model"))),
            ("Part number", sh.cell(comp["part_number"], W("part_number"), override=ov(rec, cid, "Part number"))),
            ("Size", sh.cell(comp["size"], W("size"), override=ov(rec, cid, "Size"))),
        ]
    return head + [
        ("Connections", sh.cell(comp["end_connections"], W("end_connections"), override=ov(rec, cid, "Connections"))),
        ("Material", sh.cell(comp["material"], W("material"), override=ov(rec, cid, "Material"))),
        ("Pressure rating", sh.cell(comp["pressure_rating"], W("pressure_rating"), override=ov(rec, cid, "Pressure rating"))),
        ("Temperature rating", sh.cell(comp["temperature_rating"], W("temperature_rating"),
                                       override=ov(rec, cid, "Temperature rating"))),
        ("Weight", sh.cell(comp["weight_lb"], W("weight_lb"), "lb")),
        ("Install practice", sh.cell(install_practice(comp["install_practice"]), W("install_practice"),
                                     override=ov(rec, cid, "Install practice"))),
        ("Literature", sh.plain(lit) if lit else sh.cell("unknown (no cut sheet on file)")),
    ]                                  # no 3D model row: it means nothing to a reader of a data sheet


def on_skid(sh: Sheet, lines: list[str]) -> list:
    rec = sh.rec
    if not rec.model:
        return [("Location", sh.cell(f"unknown ({rec.model_reason})"))]
    it = rec.items.get(sh.tag)
    if not it or not it.get("bbox_in"):
        return [("Location", sh.cell("unknown (location on the skid not yet set)"))]
    (x0, y0, z0), (x1, y1, z1) = it["bbox_in"]
    rows = [("Line", sh.plain(", ".join(lines) or "none (equipment)")),
            ("Next to", sh.plain(", ".join(rec.neighbours(sh.tag))))]
    if rec.datums:
        dx, dy, dz = rec.datums["X"], rec.datums["Y"], rec.datums["Z"]
        rows.append(("From datums", sh.plain(f"C {x0 - dx:.1f} to {x1 - dx:.1f} in · B {y0 - dy:.1f} to {y1 - dy:.1f} in"
                                             f" · A {z0 - dz:.1f} to {z1 - dz:.1f} in")))
        sh.sources.append(f"datums A, B, C per {rec.datum_doc}")
    else:
        rows.append(("From datums", sh.cell(f"unknown ({rec.datum_reason})")))
    rows.append(("Size on the skid", sh.plain(f"{x1 - x0:.1f} long × {y1 - y0:.1f} deep × {z1 - z0:.1f} high in")))
    return rows


def lines_for(rec: Records, tag: str) -> list[str]:
    out = []
    it = rec.items.get(tag)
    if it and it.get("line"):
        out.append(it["line"])
    for ln, r in rec.lines.items():
        ends = ";".join([r.get("from_tag", ""), r.get("to_tag", "")])
        if re.search(rf"(^|[;. ]){re.escape(tag)}($|[;. ])", ends) and ln not in out:
            out.append(ln)
    return out


def service(sh: Sheet, line_no: str) -> list:
    ln = sh.rec.lines.get((line_no or "").strip())
    if not ln:
        return [("Mounted on", sh.plain(f"{line_no}, {sh.rec.cfg.no_line_text}"))]
    W = lambda col: ("line-list.csv", ln["line_no"], col)
    return [
        ("Line", sh.plain(f"{ln['line_no']}, {fact(ln['service'])}")),
        ("Service class", sh.cell(ln["service_class"], W("service_class"))),
        ("Tube", sh.cell(f"{ln['size_od_in']} in OD × {fact(ln['gauge'])}" if not is_unknown(ln["size_od_in"]) else "unknown")),
        ("Material", sh.cell(f"{ln['material']}, {fact(ln['spec'])}" if not is_unknown(ln["material"]) else ln["material"],
                             W("material"))),
        ("Design pressure", sh.cell(ln["design_press_psig"], W("design_press_psig"), "psig")),
        ("Design temperature", sh.cell(ln["design_temp_f"], W("design_temp_f"), "°F")),
        ("Internal finish", sh.cell(ln["finish_ra"], W("finish_ra"))),
    ]


def off_skid(r: dict) -> bool:
    t = " ".join(r.get(k, "") for k in ("description", "weight_basis", "notes", "step_model_ref")).lower()
    return "off skid" in t or "supplied loose" in t


# ------------------------------------------------------------------------------------------------ sheets
def sheet_equipment(rec: Records, r: dict) -> Sheet:
    tag = r["tag"]
    title = fact(r["description"]).split(";")[0].split(",")[0]
    title = re.sub(r"^Tank - ", "Tank, ", title)[:44]
    sh = Sheet(rec, "Equipment Data Sheet", tag, title, "equipment-list.csv")
    W = lambda col: ("equipment-list.csv", tag, col)
    cid = (r.get("component_id") or "").strip()
    comp = rec.component(cid) if not is_unknown(cid) else None
    ovk = lambda label: ov(rec, tag, label, cid)
    loose = off_skid(r)
    sh.add("Duty", [
        ("Service", sh.cell(r["description"], override=ovk("Service"))),
        ("Size / rating", sh.cell(r["size_rating"], W("size_rating"), override=ovk("Size / rating"))),
        ("Supply", sh.plain("supplied loose, off the skid; not on the frame" if loose else "on the skid")),
        ("Lines", sh.plain(", ".join(lines_for(rec, tag)) or "none")),
        ("P&ID sheet", sh.cell(r["pid_sheet"])),
    ])
    if not loose:
        known = [c for c in ("empty_weight_lb", "operating_weight_lb", "operating_weight_max_lb") if not is_unknown(r[c])]
        n = sh.note("Weight basis: " + reason(r["weight_basis"]).rstrip(".")) if known else None
        wcell = lambda col: (sh.cell(r[col], W(col), "lb") + ("" if is_unknown(r[col]) or not n else f"<sup>{n}</sup>"))
        sh.add("Weights and supports", [
            ("Empty weight", wcell("empty_weight_lb")),
            ("Operating weight", wcell("operating_weight_lb")),
            ("Operating weight, max", wcell("operating_weight_max_lb")),
            ("Supports", sh.cell(r["support_count"], W("support_count"))),
            ("Load per support, max", sh.cell(r["load_per_support_max_lb"], W("load_per_support_max_lb"), "lb")),
        ])
    motor = next((m for m in rec.motors if m["driven_equipment"] == tag), None)
    if motor:
        M = lambda col: ("motor-load-list.csv", tag, col)
        sh.add("Motor", [
            ("Power", sh.cell(motor["hp"], M("hp"), "hp")),
            ("Supply", sh.cell(motor["voltage"] if is_unknown(motor["voltage"]) else
                               f"{motor['voltage']} V, {motor['phase']} phase", M("voltage"))),
            ("Drive", sh.cell(motor["starter_or_vfd"], M("starter_or_vfd"))),
            ("Motor tag", sh.cell(motor["tag"], M("tag"))),
        ])
        sh.sources.append(f"motor-load-list.csv row {tag}")
    sh.add("Purchased item", purchased(sh, comp, cid, r["vendor"], r["model"]))
    if not loose:
        sh.add("On the skid", on_skid(sh, lines_for(rec, tag)))
    return sh


def sheet_instrument(rec: Records, r: dict) -> Sheet:
    tag = r["tag"]
    meas = fact(r["type"].split(" - ")[0]).split(",")[0]
    sh = Sheet(rec, "Instrument Data Sheet", tag, meas[:1].upper() + meas[1:44], "instrument-list.csv")
    W = lambda col: ("instrument-list.csv", tag, col)
    comp = rec.component(r.get("component_id", ""))
    ovk = lambda label: ov(rec, tag, label, r.get("component_id", ""))
    where = r["line_no_or_equip"]
    sh.add("Measurement", [
        ("Measures", sh.plain(fact(r["type"].split(" - ")[0]))),
        ("Range", sh.cell(r["range"], W("range"), override=ovk("Range"))),
        ("Output", sh.cell(r["signal"], W("signal"), override=ovk("Output"))),
        ("P&ID sheet", sh.cell(r["pid_sheet"])),
    ])
    sh.add("Installation", [
        ("Process connection", sh.cell(r["process_connection"], W("process_connection"),
                                       override=ovk("Process connection"))),
        ("Orientation", sh.cell(r["mounting_orientation"], W("mounting_orientation"),
                                override=ovk("Orientation"))),
        ("Straight run", sh.cell(r["straight_run_req"], W("straight_run_req"), override=ovk("Straight run"))),
        ("Access", sh.cell(r["access_note"], W("access_note"), override=ovk("Access"))),
    ])
    sh.add("Process conditions", service(sh, where))
    sh.add("Purchased item", purchased(sh, comp, r.get("component_id", "")))
    sh.add("On the skid", on_skid(sh, [where] if where in rec.lines else []))
    return sh


def sheet_valve(rec: Records, r: dict) -> Sheet:
    tag = r["tag"]
    W = lambda col: ("valve-list.csv", tag, col)
    t = fact(r["type"]).split(":")[0].split(",")[0]
    titles = {str(k).lower(): str(v) for k, v in rec.cfg.valve_titles.items()}
    title = titles.get(t.strip().lower(), t[:1].upper() + t[1:44])
    sh = Sheet(rec, "Valve Data Sheet", tag, title, "valve-list.csv")
    comp = rec.component(r.get("component_id", ""))
    ovk = lambda label: ov(rec, tag, label, r.get("component_id", ""))
    size = r["size_od_in"].split(" ")[0]
    none = lambda v: v if (v or "").strip() else "none"
    sh.add("Valve", [
        ("Type", sh.plain(title if r["type"].strip() in rec.cfg.valve_titles else fact(r["type"]))),
        ("Size", sh.cell(size, W("size_od_in"), "in OD")),
        ("P&ID sheet", sh.cell(r["pid_sheet"])),
    ])
    sh.add("Actuation", [
        ("Actuator", sh.cell(none(r["actuator"]), W("actuator"), override=ovk("Actuator"))),
        ("Position feedback", sh.cell(none(r["feedback"]), W("feedback"), override=ovk("Position feedback"))),
        ("Solenoid", sh.cell(none(r["solenoid"]), W("solenoid"), override=ovk("Solenoid"))),
        ("Air connection", sh.cell(none(r["air_connection"]), W("air_connection"), override=ovk("Air connection"))),
    ])
    sh.add("Installation", [
        ("Process connection", sh.cell(r["process_connection"], W("process_connection"),
                                       override=ovk("Process connection"))),
        ("Orientation", sh.cell(r["orientation"], W("orientation"), override=ovk("Orientation"))),
    ])
    sh.add("Process conditions", service(sh, r["line_no"]))
    sh.add("Purchased item", purchased(sh, comp, r.get("component_id", "")))
    sh.add("On the skid", on_skid(sh, [r["line_no"]]))
    return sh


def all_sheets(rec: Records) -> list[Sheet]:
    out = [sheet_equipment(rec, r) for r in rec.equipment if not is_unknown(r["tag"])]
    out += [sheet_instrument(rec, r) for r in rec.instruments]
    out += [sheet_valve(rec, r) for r in rec.valves]
    return out


# ------------------------------------------------------------------------------------------------ html
CSS = """
@page { size: Letter; margin: 0; }
:root { --cpme-navy:#0D1554; --cpme-steel:#7E849E; --cpme-doc-blue:#0B5394; --ink:#0F1733; --ink-2:#3A4466;
  --ink-3:#6B7394; --line:#CFD5E6; --tint:#EEF2FB; --warn:#B7791F;
  --head:"Archivo","IBM Plex Sans",system-ui,"Segoe UI",Arial,sans-serif;
  --sans:"IBM Plex Sans",system-ui,"Segoe UI",Arial,sans-serif; --mono:"IBM Plex Mono",ui-monospace,Consolas,monospace; }
* { box-sizing:border-box; }
html,body { margin:0; padding:0; background:#fff; color:var(--ink); font-family:var(--sans); font-size:7.6pt;
  line-height:1.3; -webkit-print-color-adjust:exact; print-color-adjust:exact; }
.page { width:8.5in; min-height:10.98in; padding:0.4in 0.45in 0.35in; display:flex; flex-direction:column; }
/* min-height, not a clipped height: content that does not fit prints a second page, which the page check catches */
header { display:flex; align-items:center; border-bottom:2pt solid var(--cpme-doc-blue); padding-bottom:6pt; }
header .logo { width:0.95in; } header .logo svg { width:100%; height:auto; display:block; }
header .title { flex:1; padding:0 12pt; }
.kicker { font-size:6.6pt; letter-spacing:1.4pt; text-transform:uppercase; color:var(--cpme-doc-blue); font-weight:600; }
h1 { margin:1pt 0; font-family:var(--head); font-size:16pt; font-weight:700; color:var(--cpme-navy); line-height:1.1; }
h1 .tag { font-family:var(--mono); }
.sub { font-size:7.6pt; color:var(--ink-3); }
table.docinfo { border-collapse:collapse; font-size:6.6pt; }
table.docinfo td { border:0.6pt solid var(--line); padding:1.3pt 5pt; white-space:nowrap; }
table.docinfo td:first-child { background:var(--tint); color:var(--ink-3); text-transform:uppercase; letter-spacing:.4pt; font-size:6pt; }
.status { font-weight:700; color:var(--warn); }
.cols { display:grid; grid-template-columns:1fr 1fr; gap:10pt; margin-top:9pt; }
section { margin-bottom:8pt; break-inside:avoid; }
h2 { font-family:var(--head); font-size:7.2pt; text-transform:uppercase; letter-spacing:1pt; color:#fff;
  background:var(--cpme-navy); margin:0 0 2pt; padding:1.8pt 6pt; font-weight:600; }
table.spec { width:100%; border-collapse:collapse; table-layout:fixed; }
table.spec td { border-bottom:0.5pt solid var(--line); padding:1.4pt 4pt; vertical-align:top; text-align:left;
  overflow-wrap:anywhere; }
table.spec td.k { color:var(--ink-3); width:33%; }
.unk { color:var(--warn); font-weight:600; }
.part { border-left:2pt solid var(--warn); padding-left:3pt; display:inline; }
sup { font-size:5.4pt; color:var(--warn); font-weight:600; margin-left:1pt; }
.foot { margin-top:auto; padding-top:4pt; font-size:6.4pt; color:var(--ink-2); }
.foot ol { margin:0 0 3pt; padding-left:12pt; } .foot li { margin-bottom:0.8pt; }
.foot li::marker { color:var(--warn); font-weight:600; }
.foot .src { color:var(--ink-3); margin:3pt 0 0; }
footer { border-top:1pt solid var(--cpme-navy); padding-top:4pt; margin-top:6pt; display:flex;
  justify-content:space-between; font-size:6.4pt; color:var(--ink-3); }
"""

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;600;700;800&family=IBM+Plex+Sans:'
         'wght@400;500;600&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">')


def render(sh: Sheet, doc_id: str, rev: str, today: str, fast: str = "") -> str:
    """The sheet's self-contained HTML (logo inline) as revision `rev` dated `today`; `fast` ('FAST-001') marks a fast
    drawing: the revision cell then reads '<rev> FAST-001 - NOT ISSUED'. Prints nothing internal (DRF-FACE-001): the
    model, the sources and who answers are in the basis CSV, not on the sheet."""
    logo = re.sub(r"<\?xml[^>]*\?>", "", LOGO.read_text(encoding="utf-8"))
    weight = lambda rows: sum(1 + len(re.sub(r"<[^>]+>", "", v)) / 48 for _, v in rows) + 2
    sizes = [weight(r) for _, r in sh.sections]
    half, acc, split = sum(sizes) / 2, 0.0, len(sizes)
    for i, n in enumerate(sizes):
        if acc + n / 2 > half:
            split = i
            break
        acc += n
    split = max(1, split)

    def sec_html(title, rows):
        body = "".join(f'<tr><td class="k">{html.escape(k)}</td><td>{v}</td></tr>' for k, v in rows)
        return f"<section><h2>{html.escape(title)}</h2><table class='spec'>{body}</table></section>"
    left = "".join(sec_html(t, r) for t, r in sh.sections[:split])
    right = "".join(sec_html(t, r) for t, r in sh.sections[split:])
    foot = ""
    if sh.notes:
        foot += "<ol>" + "".join(f"<li>{html.escape(n)}</li>" for n in sh.notes) + "</ol>"
    foot += (f'<p class="src">Generated {today}. A value shown as TBD is not yet decided; nothing on this sheet is '
             "estimated. DRAFT: not for purchase or fabrication until approved.</p>")
    sub = html.escape(rec_subtitle(sh.rec))
    rev_cell = rev if not fast else f'{rev} &nbsp;<span class="status">{fast} - NOT ISSUED</span>'
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{html.escape(doc_id)} Rev {rev}</title>{FONTS}
<style>{CSS}</style></head><body><div class="page">
<header>
  <div class="logo">{logo}</div>
  <div class="title"><div class="kicker">{html.escape(sh.kind)}</div>
    <h1><span class="tag">{html.escape(sh.tag)}</span> &nbsp;{html.escape(sh.title)}</h1>
    <div class="sub">{sub}</div></div>
  <table class="docinfo">
    <tr><td>Doc No.</td><td><b>{html.escape(doc_id)}</b></td></tr>
    <tr><td>Revision</td><td>{rev_cell}</td></tr>
    <tr><td>Date</td><td>{today}</td></tr>
    <tr><td>TBD values</td><td>{sh.open}</td></tr>
    <tr><td>Status</td><td class="status">DRAFT</td></tr>
  </table>
</header>
<div class="cols"><div>{left}</div><div>{right}</div></div>
<div class="foot"><h2>Notes</h2>{foot}</div>
<footer><div>{html.escape(brand_one_line())}</div><div>{html.escape(doc_id)} Rev {rev}{(' ' + fast) if fast else ''} · Page 1 of 1</div></footer>
</div></body></html>"""


def rec_subtitle(rec: Records) -> str:
    """The line under the title: the settings' subtitle only (no model number on the sheet)."""
    return rec.cfg.subtitle or ""


def page_text(page_html: str) -> list[str]:
    """The visible text of a sheet, one string per text run, for the sheet-face check."""
    body = re.sub(r"(?is)<(style|script|title|svg)\b.*?</\1>", " ", page_html)
    body = re.sub(r"(?s)<head>.*?</head>", " ", body)
    return [html.unescape(" ".join(t.split())) for t in re.split(r"<[^>]+>", body) if t.strip()]


def face_findings(page_html: str) -> list[tuple[str, list[str]]]:
    """(text, reasons) for every visible text run that fails the sheet-face check."""
    return [(t, r) for t in page_text(page_html) if (r := SF.check_text(t))]


BASIS_COLS = ["document_id", "tag", "section", "field", "printed", "status", "note", "record", "raw", "reason",
              "who_can_answer"]


def basis_rows(sh: Sheet, doc_id: str) -> list[dict]:
    """The sheet's basis rows: every printed cell and footnote, then its model and sources (never printed)."""
    rows = [{"document_id": doc_id, "tag": sh.tag, **r} for r in sh.basis]
    m = sh.rec
    model = f"model {m.model_label}" + (f" (same design as {m.same_design})" if m.same_design else "")
    rows.append({"document_id": doc_id, "tag": sh.tag, "section": "Sources", "field": "sources", "printed": "",
                 "raw": "; ".join([model] + list(dict.fromkeys(sh.sources)))})
    return rows


def write_basis(cfg: Settings, rows: list[dict], docs: set[str]) -> Path:
    """Replace the rows of `docs` in the basis CSV with `rows` (other documents' rows are kept)."""
    p = cfg.basis_csv
    keep = [r for r in read_csv(p) if r.get("document_id") not in docs] if p.is_file() else []
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=BASIS_COLS)
        w.writeheader()
        for r in sorted(keep + rows, key=lambda r: r.get("document_id", "")):
            w.writerow({k: r.get(k, "") for k in BASIS_COLS})
    return p


def count_pages(pdf: Path) -> int:
    return len(re.findall(rb"/Type\s*/Page[^s]", pdf.read_bytes()))


def to_pdf(src: Path, pdf: Path) -> int:
    """Print the HTML to PDF with Edge headless; the page count (0 when no PDF came out)."""
    if not EDGE.is_file():
        raise Refused(f"Edge is not at {EDGE} (set CPME_EDGE to its path); no PDF made")
    import tempfile
    # its own throw-away profile each time: a headless Edge sharing the user's open profile can hang (seen
    # 2026-11-16, third sheet of a 44-sheet run). One retry on a timeout; then 0 pages, reported by the caller.
    for _attempt in range(2):
        with tempfile.TemporaryDirectory(prefix="ds-edge-") as prof:
            try:
                subprocess.run([str(EDGE), "--headless", "--disable-gpu", "--no-pdf-header-footer",
                                "--no-first-run", "--disable-extensions", f"--user-data-dir={prof}",
                                "--virtual-time-budget=4000", f"--print-to-pdf={pdf}", src.as_uri()],
                               capture_output=True, timeout=120)
            except subprocess.TimeoutExpired:
                continue
        if pdf.exists():
            return count_pages(pdf)
    return count_pages(pdf) if pdf.exists() else 0


# ------------------------------------------------------------------------------------------------ filed revisions
def filed_rows(root: Path, doc_id: str) -> list[dict]:
    p = root / doc_id / "revisions.csv"
    return read_csv(p) if p.is_file() else []


def last_filed(root: Path, doc_id: str) -> tuple[str | None, Path | None]:
    """(last filed revision letter, its filed HTML) of a document; (None, None) when it was never filed."""
    rows = filed_rows(root, doc_id)
    revs = [r["revision"].strip() for r in rows if r.get("revision", "").strip()]
    if not revs:
        return None, None
    last = max(revs, key=lambda s: (len(s), s))
    htm = [r["file"].strip() for r in rows if r["revision"].strip() == last and r["file"].strip().lower().endswith(".html")]
    return last, (root / doc_id / htm[-1]) if htm else None


DATE_CELL = re.compile(r"<tr><td>Date</td><td>(\d{4}-\d{2}-\d{2})</td></tr>")


def compare(sh: Sheet, doc_id: str, root: Path) -> tuple[str, str, str]:
    """(status, last filed revision or "", the first difference) for one sheet against its last filed revision:
    new (never filed), unchanged (the filed HTML is what this run makes with that revision's letter and date) or
    changed. A filed revision whose HTML is not on disk counts as changed, with the reason."""
    rev, htm = last_filed(root, doc_id)
    if rev is None:
        return "new", "", ""
    if htm is None or not htm.is_file():
        return "changed", rev, "the filed HTML of that revision is not on disk"
    old = htm.read_text(encoding="utf-8")
    m = DATE_CELL.search(old)
    new = render(sh, doc_id, rev, m.group(1) if m else "")
    if new == old:
        return "unchanged", rev, ""
    a, b = old.splitlines(), new.splitlines()
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            j = next((k for k in range(min(len(x), len(y))) if x[k] != y[k]), min(len(x), len(y)))
            return "changed", rev, f"line {i + 1}: filed ...{x[max(0, j - 40):j + 80]!r} now ...{y[max(0, j - 40):j + 80]!r}"
    return "changed", rev, f"{len(a)} filed lines, {len(b)} now"


def removed_docs(cfg: Settings, root: Path, sheets: list[Sheet]) -> list[str]:
    """Filed data sheet documents (doc_prefix) whose tag is no longer in the lists."""
    have = {cfg.doc_prefix + sh.tag for sh in sheets}
    return sorted(p.name for p in root.glob(cfg.doc_prefix + "*") if p.is_dir() and p.name not in have
                  and (p / "revisions.csv").is_file())


def next_rev(root: Path, doc_id: str) -> str:
    rev, _ = last_filed(root, doc_id)
    nxt = next_letter(rev)
    if (root / doc_id / rp.rev_folder(doc_id, nxt)).exists():
        raise Refused(f"{doc_id} Rev {nxt} folder already exists but is not in revisions.csv; fix the record "
                      "before filing (never overwrite, TR-08)")
    return nxt


def check_note(note: str) -> str:
    note = (note or "").strip().upper()
    if not note:
        raise Refused("a revision note is required for every revision (TR-07)")
    if len(note) > MAX_BLOCK_NOTE:
        raise Refused(f"the revision note is {len(note)} characters; {MAX_BLOCK_NOTE} fit. Put the detail in "
                      "--description.")
    return note


def _sha(p: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def file_sheets(cfg: Settings, sheets: list[Sheet], root: Path, stage_root: Path, note: str, description: str,
                today: str, pdf_maker=to_pdf) -> list[tuple[str, str, list[Path]]]:
    """File each sheet as its document's next revision: <DOC-ID>-rev<X>/<DOC-ID>-rev<X>-CPME-Generated.html and .pdf,
    read-only, with revisions.csv rows. Every sheet is checked (changed or new, target free, one page) before any is
    filed; nothing is filed when one fails. Returns (document, revision, filed files) per sheet."""
    note = check_note(note)
    plan = []
    for sh in sheets:
        doc_id = cfg.doc_prefix + sh.tag
        status, last, _ = compare(sh, doc_id, root)
        if status == "unchanged":
            raise Refused(f"{doc_id} is unchanged since Rev {last}; nothing to file (a revision records a change)")
        rev = next_rev(root, doc_id)
        rdir = root / doc_id / rp.rev_folder(doc_id, rev)
        if rdir.exists():
            raise Refused(f"refusing to file into an existing revision folder {rdir}")
        stage = stage_root / rp.rev_folder(doc_id, rev)
        if stage.exists():
            shutil.rmtree(stage)
        stage.mkdir(parents=True)
        shtml = stage / generated_name(doc_id, rev, ".html")
        shtml.write_text(render(sh, doc_id, rev, today), encoding="utf-8")
        spdf = stage / generated_name(doc_id, rev, ".pdf")
        pages = pdf_maker(shtml, spdf)
        if pages != 1:
            raise Refused(f"{doc_id} Rev {rev}: the PDF has {pages} page(s), expected 1; nothing filed")
        plan.append((doc_id, rev, rdir, [shtml, spdf]))
    stamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    try:
        source = rp.rel(Path(__file__)) + "; " + rp.rel(cfg.path)
    except ValueError:
        source = Path(__file__).name
    out = []
    for doc_id, rev, rdir, files in plan:
        rdir.mkdir(parents=True)
        rows, filed = [], []
        for src in sorted(files, key=lambda p: p.suffix != ".pdf"):     # the PDF row first, as revfile.py
            dst = rdir / src.name
            shutil.move(str(src), str(dst))
            os.chmod(dst, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
            filed.append(dst)
            rows.append({"document_id": doc_id, "revision": rev, "file": f"{rdir.name}/{dst.name}", "file_date": stamp,
                         "sha256": _sha(dst), "bytes": dst.stat().st_size, "source": source, "notes": note,
                         "description": description or note})
        man = root / doc_id / "revisions.csv"
        existing = read_csv(man) if man.is_file() else []
        cols = list(existing[0].keys()) if existing else MANIFEST_COLS
        with open(man, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            for r in existing + rows:
                w.writerow({k: r.get(k, "") for k in cols})
        out.append((doc_id, rev, filed))
    return out


# ------------------------------------------------------------------------------------------------ fast drawings
def fast_root(cfg: Settings) -> Path:
    """<level>/03_Working_Design/Exports/Fast_Drawings: the typicals' folder for file_to job, else the project's;
    CPME_FAST_ROOT (a test's scratch folder) overrides."""
    if os.environ.get("CPME_FAST_ROOT"):
        return Path(os.environ["CPME_FAST_ROOT"])
    level = rp.TYPICAL if cfg.file_to == "job" or not rp.HAS_PROJECT else rp.PROJECT
    return level / "03_Working_Design" / "Exports" / "Fast_Drawings"


def fast_name(froot: Path, doc_id: str, last: str | None) -> tuple[str, int]:
    """(<DOC>-<base>-fast-<nnn>, nnn): base rev<X> for the last filed letter, else first; nnn one more than any used."""
    base = f"rev{last}" if last else "first"
    d = froot / doc_id
    used = [int(m.group(1)) for p in (d.iterdir() if d.exists() else []) if (m := re.search(r"-fast-(\d{3})$", p.name))]
    nnn = max(used, default=0) + 1
    return f"{doc_id}-{base}-fast-{nnn:03d}", nnn


def log_fast(froot: Path, stem: str, build: str, request: str, layout_n: int, face_n: int, folder: Path) -> None:
    """One row in the fast drawings' fast-log.md (the plan set's log; same columns)."""
    log = froot / "fast-log.md"
    if not log.exists():
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text("# Fast drawings (not issued)\n\nEvery plan set fast drawing, newest at the bottom. Written by "
                       "plan_set_lib; never edited by hand.\n\n| Drawing | Date time | Model build | Request | Layout "
                       "problems | Sheet face | Folder |\n|---|---|---|---|---|---|---|\n", encoding="utf-8")
    try:
        rel = rp.rel(folder)
    except ValueError:
        rel = str(folder)
    req = " ".join(request.split()).replace("|", "/")[:160]
    with log.open("a", encoding="utf-8") as f:
        f.write(f"| {stem} | {dt.datetime.now():%Y-%m-%d %H:%M} | {build} | {req} | {layout_n} | "
                f"{'PASS' if not face_n else f'FAIL {face_n}'} | {rel} |\n")


def write_fast(cfg: Settings, rec: Records, sheets: list[Sheet], root: Path, request: str, today: str,
               pdf: bool = True, pdf_maker=to_pdf) -> list[tuple[str, Path, int, int]]:
    """A numbered fast drawing of each sheet (never overwritten, not filed). Returns (stem, folder, pages, sheet-face
    findings) per sheet."""
    if not (request or "").strip():
        raise Refused("--fast needs --request (the words it answers)")
    froot, out = fast_root(cfg), []
    for sh in sheets:
        doc_id = cfg.doc_prefix + sh.tag
        last, _ = last_filed(root, doc_id)
        stem, nnn = fast_name(froot, doc_id, last)
        folder = froot / doc_id / stem
        if folder.exists():
            raise Refused(f"{folder} exists: a fast drawing is never overwritten")
        folder.mkdir(parents=True)
        page = render(sh, doc_id, last or "A", today, fast=f"FAST-{nnn:03d}")
        htm = folder / f"{stem}.html"
        htm.write_text(page, encoding="utf-8")
        pages = pdf_maker(htm, folder / f"{stem}.pdf") if pdf else 1
        face = face_findings(page)
        log_fast(froot, stem, rec.model_label, request, 0 if pages == 1 else 1, len(face), folder)
        out.append((stem, folder, pages, len(face)))
    return out


# ------------------------------------------------------------------------------------------------ main
def run(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--tags", nargs="*", help="only these tags")
    ap.add_argument("--all", action="store_true", help="preview every tag, changed or not")
    ap.add_argument("--out", type=Path, default=None, help="preview folder (default: the settings' preview_dir, "
                                                            "else _work/data-sheets of the filing level)")
    ap.add_argument("--html-only", action="store_true", help="no PDF and no page check")
    ap.add_argument("--settings", type=Path, default=None, help=argparse.SUPPRESS)   # tests
    ap.add_argument("--file", action="store_true", help="file the --tags named as their next revision")
    ap.add_argument("--note", default="", help="revision note, 32 characters at most (with --file)")
    ap.add_argument("--description", default="", help="what changed, in full (with --file)")
    ap.add_argument("--fast", action="store_true", help="numbered fast drawings of the sheets named (all when no "
                                                         "--tags); not filed")
    ap.add_argument("--request", default="", help="with --fast: the words the fast drawings answer")
    a = ap.parse_args(argv)
    if a.fast and a.file:
        raise Refused("--fast and --file are two different things; give one")
    cfg = load_settings(a.settings)
    configure(cfg.text_rules)
    rec = Records(cfg)
    root = drawings_root(cfg)
    sheets = all_sheets(rec)
    known = {sh.tag for sh in sheets}
    if a.tags:
        unknown_tags = [t for t in a.tags if t not in known]
        if unknown_tags:
            raise Refused(f"not in the tag lists: {', '.join(unknown_tags)}")
        sheets = [sh for sh in sheets if sh.tag in a.tags]
    today = dt.date.today().isoformat()
    # what each printed cell came from (the cells were made as the sheets were built): rewritten for the sheets of
    # this run, every run; never printed
    bpath = write_basis(cfg, [r for sh in sheets for r in basis_rows(sh, cfg.doc_prefix + sh.tag)],
                        {cfg.doc_prefix + sh.tag for sh in sheets})

    if a.fast:
        made = write_fast(cfg, rec, sheets, root, a.request, today, pdf=not a.html_only)
        bad = 0
        for stem, folder, pages, face in made:
            ok = pages in (1,) and not face
            bad += not ok
            print(f"{stem:<38} pages {pages}  sheet face {'PASS' if not face else f'FAIL {face}'}"
                  f"{'' if ok else '  <-- NOT CLEAN'}")
        print(f"data_sheets: {len(made)} fast drawings in {fast_root(cfg)}; {bad} not clean; basis {bpath.name}. "
              "Nothing filed.")
        return 1 if bad else 0

    if a.file:
        if not a.tags:
            raise Refused("--file needs --tags: name each sheet to file (filing is the engineer's word)")
        stage = (rp.JOB_FILING if cfg.file_to == "job" or not rp.HAS_PROJECT else rp.FILING)
        for doc_id, rev, files in file_sheets(cfg, sheets, root, stage, a.note, a.description, today):
            print(f"filed {doc_id} Rev {rev}: " + ", ".join(f.name for f in files))
        print("next: harness/scripts/drive_store.py pointers, then the save (track.py save)")
        return 0

    out = (a.out or work_root(cfg)).resolve()
    out.mkdir(parents=True, exist_ok=True)
    rows, counts = [], {"unchanged": 0, "changed": 0, "new": 0}
    for sh in sheets:
        doc_id = cfg.doc_prefix + sh.tag
        status, last, diff = compare(sh, doc_id, root)
        counts[status] += 1
        write = a.all or status != "unchanged"
        nxt = next_letter(last or None)
        pages, leftover, name = "", 0, ""
        if write:
            page = render(sh, doc_id, nxt, today)
            src = out / generated_name(doc_id, nxt, ".html")
            src.write_text(page, encoding="utf-8")
            name = src.name
            pages = "" if a.html_only else to_pdf(src, src.with_suffix(".pdf"))
            cells = re.findall(r'<td class="k">[^<]*</td><td>(.*?)</td>', page)   # values only; footnotes may cite ids
            body = re.sub(r"<[^>]+>", " ", " ".join(c for c in cells if "Literature" not in c))
            leftover = len(R.LEFTOVER.findall(body))
        rows.append({"document_id": doc_id, "tag": sh.tag, "kind": sh.kind, "status": status,
                     "last_filed": last, "next_revision": nxt, "open_values": sh.open,
                     "footnotes": len(sh.notes), "record_text_in_cells": leftover if write else "",
                     "pages": pages, "html": name, "difference": diff})
        flag = "" if pages in ("", 1) else f"  <-- {pages} pages, expected 1"
        flag += f"  <-- {leftover} record mentions in cells" if leftover else ""
        print(f"{doc_id:<26} {status:<10} last {last or '-':<3} open {sh.open:>2}"
              f"{'  written' if write else ''}{f'  pages {pages}' if pages != '' else ''}{flag}")
        if diff:
            print(f"    {diff}")
    gone = removed_docs(cfg, root, all_sheets(rec)) if not a.tags else []
    for d in gone:
        print(f"{d:<26} no longer in the lists (filed revisions stay as filed)")
        rows.append({"document_id": d, "tag": d[len(cfg.doc_prefix):], "status": "no longer in the lists"})
    if rows:
        cols = ["document_id", "tag", "kind", "status", "last_filed", "next_revision", "open_values", "footnotes",
                "record_text_in_cells", "pages", "html", "difference"]
        with open(out / "index.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows({k: r.get(k, "") for k in cols} for r in rows)
    bad = [r for r in rows if r.get("pages") not in ("", 1, None)]
    print(f"data_sheets: {counts['unchanged']} unchanged, {counts['changed']} changed, {counts['new']} new, "
          f"{len(gone)} no longer in the lists; {sum(1 for r in rows if r.get('html'))} written to {out}"
          + (f"; {len(bad)} not one page" if bad else "") + ". Nothing filed.")
    return 1 if bad else 0


def main(argv: list[str] | None = None) -> int:
    try:
        return run(argv)
    except Refused as e:
        print(f"data_sheets: REFUSED - {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
