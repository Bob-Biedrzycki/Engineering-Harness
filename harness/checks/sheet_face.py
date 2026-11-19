"""sheet_face - what may print on a drawing sheet (DRF-FACE-001, harness/design-rules/drafting.yaml).

A sheet is read by a fabricator, estimator or customer who has never seen this repo (Bob, chat, 2026-11-16: "I can't
send out a drawing for quoting spools that has a TR reference on it"). This check reads every piece of text in a DXF
(TEXT, MTEXT, ATTRIB, ATTDEF defaults and DIMENSION text overrides, in model space, every layout and every block)
and reports any of the internal references the rule names:

- Todd's requirement numbers (TR-nn);
- design rule ids (two or more letter groups and a three-digit number: SAN-RA-001, GDT-PIPE-001, LINE-NUM-001),
  but not a drawing number (CIP-TYP-FRM-001, Project-1072-01-FRM-001) and not a tag (PI-101, FM-001);
- decision, question, RFI, equipment-concern and hold numbers (DEC-nnnn, Q-nnnn, RFI-nnnn, EC-nn, Hn);
- component register numbers (COMP-nnnn, CMP-nnnn), and the model's record codes (A-19, GN-LASER, SI-02, SH-06);
- repo paths and the file names of scripts, YAML, CSV, JSON and Markdown;
- software names and versions (cadgen, ezdxf, build123d, text-to-cad, OCCT, python, uvx, Blender);
- the words brief, helper, orchestrator, harness, takeoff, manifest, ASSUMPTION and unknown;
- people's names (Bob, Todd);
- model numbers (CIP-TYP-MDL-001-B, Project-1072-01-MDL-001), the names of the model's own reports and lists
  (routing report, layout note, component register, line list), "as modelled", assumption wording (placeholder,
  first-pass, is assumed), hold, gate and review status, rule families and tracker names (SAN rule, CPM-41,
  PartsLib), and a McMaster catalogue number beside a commodity word (Reviewer, round 2 request 01);
- the customer's name (Bob, chat, 2026-11-17: "We need to keep our customer private on all drawings unless we are
  specifically developing a set for them"): the `customer` of every project in the job (project.yaml), the same
  name without its company ending (Co., Inc., LLC ...), and every name in `customer_aliases` (comma separated).
  A drawing made for the customer is named in that project's `customer_drawings` (comma-separated document
  numbers) and is the only drawing the name may print on. The word "customer" itself may print.

Public standards (AWS D18.1, ASME BPE, ASME IX, PFI ES-3, ASME Y14.5) are not internal references and pass.
The one repo path allowed is the sheet's own footer: the drawing file's path (a .dxf or .dwg under a drawings,
fast drawing or preview folder), which the rule asks for.

Usage:
    sheet_face.py [<dxf or folder> ...] [--json]
A folder is searched for *.dxf. With no paths (as CI runs it) the newest fast drawing of every document in the
job's Fast_Drawings folders is checked; there are none on the check server (Fast_Edits/ is gitignored), which passes. Exit-code contract (harness/checks/README.md): 0 = PASS, 1 = FAIL (findings),
3 = ERROR. First line = summary. Filed revisions are a record and are not rechecked (First Principle 4); the check
runs on every fast drawing (plan_set_lib) and on any DXF named on the command line.

Importable: check_text(s, customer_ok=False) -> list[str] (reasons, empty when clean);
check_dxf(path, customer_ok=None) -> list[Finding].
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from typing import NamedTuple
from pathlib import Path

sys.path.insert(0, str(next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists()) / "harness" / "lib"))
import repo_paths as rp  # noqa: E402

RULE_ID = "DRF-FACE-001"

# drawing numbers are not rule ids: CIP-TYP-FRM-001, CIP-TYP-PSP-001, Project-1072-01-FRM-001
_DOC_ID = re.compile(r"\b(?:CIP-TYP(?:-[A-Z0-9]+)+|Project-\d{4}-\d{2}(?:-[A-Z0-9]+)+)\b", re.I)

# (name, pattern) - case-insensitive unless the pattern says otherwise
PATTERNS: list[tuple[str, re.Pattern]] = [
    ("Todd's requirement number", re.compile(r"\bTR-\d{1,2}\b", re.I)),
    ("design rule id", re.compile(r"\b[A-Z]{2,6}(?:-[A-Z]{2,8})+-\d{3}[A-Z]?\b", re.I)),
    ("decision number", re.compile(r"\bDEC-\d{3,4}\b", re.I)),
    # any digit count (Q-10 as well as Q-0003)
    ("question number", re.compile(r"\b(?:Q|RFI)-\d{1,4}\b", re.I)),
    ("equipment concern number", re.compile(r"\bEC-\d{2,3}\b", re.I)),
    ("hold number", re.compile(r"(?<![\w.-])H\d{1,2}(?![\w.-])")),
    # H-19 with a hyphen; digits only, so H-BEAM passes
    ("hold number", re.compile(r"(?<![\w.-])H-\d{1,2}(?![\w.-])")),
    ("P&ID revision request number", re.compile(r"\bPRR-\d{1,4}\b", re.I)),
    # calc item ids (W-12): W, a hyphen and digits, standing alone. W6X12 (no hyphen), weld numbers W01 and
    # L-100-SP03-W01 (W follows a hyphen with no hyphen after it), FW-068 (W inside a word) pass
    ("calculation item id", re.compile(r"(?<![\w-])W-\d{1,3}(?![\w-])", re.I)),
    # a list or register column name in snake_case (weight_basis, size_in): letters, an underscore, letters
    ("list column name", re.compile(r"\b[A-Za-z]{2,}(?:_[A-Za-z0-9]+)+\b")),
    ("register wording", re.compile(r"\bper\s+(?:the\s+)?register\b|\bregister\s+description\b|\bunregistered\b",
                                    re.I)),
    # the model's revision: "REV B" only next to the word MODEL, so the drawing's own revision box and a bare
    # "REV A" pass; and a model build name (revB-full-007). The sheet's own footer path is exempt as a whole.
    ("model revision", re.compile(
        r"\bMODEL\b[^.;]{0,30}?\bREV(?:ISION)?\.?\s+[A-Z]{1,2}\b|\bREV(?:ISION)?\.?\s+[A-Z]{1,2}\s+(?:OF\s+THE\s+)?MODEL\b|"
        r"\brev[A-Z]{1,2}-(?:fast|full)-\d{3}\b|"
        # the model's revision named in words ("OPEN FOR THE NEXT MODEL REVISION"): the design process, not the drawing. The drawing's own REVISION box and "REV A" have no MODEL / NEXT in them
        r"\bmodel\s+revisions?\b|\bnext\s+(?:model\s+)?revisions?\b|\brevision\s+of\s+the\s+model\b", re.I)),
    ("component register number", re.compile(r"\bC(?:O)?MP-\d{4}\b", re.I)),
    # the model's own record codes: assumption numbers (A-19), general-note keys (GN-LASER), install and
    # support-install items (SI-02, SH-06)
    ("internal record number", re.compile(r"\b(?:A|SI|SH)-\d{2,3}\b|\bGN-[A-Z0-9]+\b", re.I)),
    ("repo file name", re.compile(r"[\w-]\.(?:py|ya?ml|csv|json|md)\b", re.I)),
    ("repo path", re.compile(r"(?:^|[\s(\"'])(?:harness|job|\.claude|_work)[/\\]|[A-Z]:\\", re.I)),
    ("software name", re.compile(r"\b(?:cadgen|ezdxf|build123d|text-to-cad|OCCT|python|uvx|blender)\b", re.I)),
    ("internal word", re.compile(r"\b(?:brief|helpers?|orchestrator|harness|take-?offs?|manifest)\b", re.I)),
    ("ASSUMPTION", re.compile(r"\bASSUMPTIONS?\b", re.I)),
    ("the word unknown", re.compile(r"\bunknown\b", re.I)),
    ("a person's name", re.compile(r"\b(?:Bob|Bob's|Todd|Todd's)\b", re.I)),
    # Reviewer, round 2 request 01 (2026-11-16): wording the first patterns let through on the filed Rev A sheets
    ("the model's own reports and lists", re.compile(
        r"\b(?:routing report|layout note|component register|line list|weld[- ]map position|model writes|"
        r"filed model|retired model|placed whole|as modell?ed)\b", re.I)),
    ("assumption wording", re.compile(r"\b(?:placeholders?|first-pass|is assumed|are assumed|stale)\b", re.I)),
    ("hold, gate or review status", re.compile(
        r"\bHOLD\s*\((?:NOT RECEIVED|H\d+)\)|\bGATE\s+\d\b|\bFOR\s+(?:THE\s+)?(?:ENGINEER'?S?\s+)?REVIEW\b|"
        r"\bREV\s+\d+,\s+FOR\s+REVIEW\b|\bEARLIER JOB\b", re.I)),
    # a model axis with its sign as a word (-X END, +Y SIDE, (-X, REAR); orchestrator 2026-11-16): a fabricator has no
    # axes; the drawings name FRONT, REAR, TK-101 END, TK-103 END. Coordinate headings (X FROM C, X FR C), sizes
    # (4 X 3), SECTION X-X and tolerances (+/-.010) pass: no sign directly before the letter, or a word or hyphen
    # before the sign
    ("model axis letter", re.compile(r"(?<![\w-])[+-][XYZ](?!\w)", re.I)),
    ("rule family or tracker name", re.compile(
        r"\b(?:SAN|GDT|PIPE|LAY|DRF|TAG|STR|INST|MAT|CHAIN)\s+RULES?\b|\bCPM-\d+\b|\bPARTSLIB\b", re.I)),
]

# a model number is not a drawing of the set: checked before drawing numbers are masked
_MODEL_ID = re.compile(r"\b(?:CIP-TYP|Project-\d{4}-\d{2})-MDL-\d{3}(?:-[A-Z0-9]+)?\b", re.I)
# a commodity's maker and catalogue number (DRF-FACE-001 item 4): McMaster and a part number with a commodity word
# within the next few words ("McMaster 4322K153 304 SS clamp"); specified equipment bought there keeps its maker
_MCMASTER_PN = re.compile(r"\bMcMaster(?:-Carr)?\s+[0-9]{2,}[A-Z][0-9A-Z]*(?:\s+\S+){0,5}?\s+(?:clamps?|gaskets?|"
                          r"ferrules?|hangers?|washers?|tub(?:e|ing)|fittings?|elbows?|tees?|nuts?|bolts?|studs?|"
                          r"caps?|reducers?)\b", re.I)

# the sheet's own footer: the drawing file's repo path (a .dxf or .dwg in a drawings, fast or preview folder)
_FOOTER = re.compile(r"^job/[\w./ -]+/(?:Fast_Drawings|Drawings|preview)/[\w./ -]+\.(?:dxf|dwg)$|"
                     # or the file name only (the toolkit's FOOTER_FORM = "name"): a drawing number's own file
                     r"^(?:CIP-TYP|Project-\d{4}-\d{2})(?:-[A-Z0-9]+)+-(?:rev[A-Z]{1,2}|first|preview)"
                     r"(?:-fast-\d{3})?(?:-preview)?\.(?:dxf|dwg)$", re.I)


class Finding(NamedTuple):
    file: str
    sheet: str
    text: str
    reason: str


# ---- the customer's name (Bob, chat, 2026-11-17): private on every sheet not made for that customer
_COMPANY_ENDING = re.compile(r"[\s,]+(?:co|company|corp|corporation|inc|incorporated|llc|ltd|limited|lp|llp|plc|"
                             r"gmbh)\.?$", re.I)
_NOT_A_NAME = {"", "unknown", "tbd", "n/a", "na", "none", "typical"}


def name_pattern(name: str) -> re.Pattern | None:
    """A pattern that finds a name however it is spaced or punctuated ("ACME BEVERAGE CO", "Acme-Beverage Co.")."""
    words = re.findall(r"[A-Za-z0-9&']+", name or "")
    if not words:
        return None
    return re.compile(r"(?<![A-Za-z0-9])" + r"[\W_]*".join(re.escape(w) for w in words) + r"(?![A-Za-z0-9])", re.I)


def customer_patterns(names) -> list[re.Pattern]:
    """Patterns for each name as given and, when a company ending (Co., Inc., LLC ...) is on it, without the ending
    (a name of four letters or more, so a short stem does not match ordinary words)."""
    seen, out = set(), []
    for raw in names:
        name = " ".join((raw or "").split())
        for n in (name, _COMPANY_ENDING.sub("", name)):
            key = n.lower()
            if key in _NOT_A_NAME or key in seen or len(re.sub(r"[^A-Za-z0-9]", "", n)) < 4:
                continue
            seen.add(key)
            pat = name_pattern(n)
            if pat:
                out.append(pat)
    return out


def _project_configs() -> list[dict]:
    """project.yaml of every project in the job (a sheet of one project, or a typical, names no project's customer)."""
    out = []
    for p in sorted(rp.JOBS.glob("Project-*/project.yaml")):
        try:
            out.append(rp._read_flat(p))
        except OSError:
            continue
    return out


def _split(v: str) -> list[str]:
    return [x.strip() for x in (v or "").split(",") if x.strip()]


_CUSTOMERS: list[re.Pattern] | None = None      # read once; a test sets it with customer_patterns([...])
_CUSTOMER_DRAWINGS: list[str] | None = None


def _customers() -> list[re.Pattern]:
    global _CUSTOMERS
    if _CUSTOMERS is None:
        names = []
        for cfg in _project_configs():
            names += [cfg.get("customer", "")] + _split(cfg.get("customer_aliases", ""))
        _CUSTOMERS = customer_patterns(names)
    return _CUSTOMERS


def made_for_customer(path) -> bool:
    """True when the drawing file's name starts with a document number a project lists in `customer_drawings`."""
    global _CUSTOMER_DRAWINGS
    if _CUSTOMER_DRAWINGS is None:
        _CUSTOMER_DRAWINGS = [d.lower() for cfg in _project_configs() for d in _split(cfg.get("customer_drawings", ""))]
    name = Path(path).name.lower()
    return any(name == d or name.startswith(d + "-") or name.startswith(d + ".") for d in _CUSTOMER_DRAWINGS)


def check_text(s: str, customer_ok: bool = False) -> list[str]:
    """The reasons a piece of sheet text breaks the rule (empty when it may print). customer_ok: the sheet is one
    made for the customer, so the customer's name may print."""
    t = " ".join((s or "").split())
    if not t or _FOOTER.match(t):
        return []
    out = []
    if not customer_ok:
        for pat in _customers():
            m = pat.search(t)
            if m:
                out.append(f"the customer's name ({m.group(0)})")
                break
    m = _MODEL_ID.search(t)
    if m:
        out.append(f"model number ({m.group(0)})")
    m = _MCMASTER_PN.search(t)
    if m:
        out.append(f"commodity maker and catalogue number ({m.group(0)})")
    masked = _DOC_ID.sub(lambda m: "#" * len(m.group(0)), _MODEL_ID.sub("", t))
    for name, pat in PATTERNS:
        m = pat.search(masked)
        if m:
            out.append(f"{name} ({t[m.start():m.end()].strip()})")
    return out


def _texts(doc):
    """(entity, text) for every piece of text in the document."""
    for e in doc.entitydb.values():
        if not e.is_alive:
            continue
        kind = e.dxftype()
        try:
            if kind in ("TEXT", "ATTRIB"):
                yield e, e.dxf.get("text", "")
            elif kind == "ATTDEF":
                yield e, e.dxf.get("text", "")
            elif kind == "MTEXT":
                yield e, e.plain_text()
            elif kind == "DIMENSION":
                t = e.dxf.get("text", "")
                if t and t not in ("<>", " "):
                    yield e, t.replace("<>", "")
        except Exception:      # an unreadable entity is not a sheet-face finding
            continue


def _sheet_map(doc):
    """[(x0, x1, layout name)] from each layout's viewport onto model space (the plan set and P&ID layouts)."""
    spans = []
    for lay in doc.layouts:
        if lay.name == "Model":
            continue
        for vp in lay.query("VIEWPORT"):
            if vp.dxf.get("id", 0) == 1:
                continue
            c = vp.dxf.get("view_center_point")
            h = vp.dxf.get("view_height", 0.0)
            w, ph = vp.dxf.get("width", 0.0), vp.dxf.get("height", 0.0)
            if c is None or not h or not ph:
                continue
            half = h * (w / ph) / 2.0
            spans.append((c[0] - half, c[0] + half, lay.name))
    return spans


def _where(e, spans) -> str:
    try:
        owner = e.dxf.owner
        doc = e.doc
        blk = doc.entitydb.get(owner) if owner else None
        if blk is not None and blk.dxftype() == "BLOCK_RECORD":
            name = blk.dxf.name
            if name.lower() != "*model_space":
                return name if not name.startswith("*") else "paper space" if name.lower().startswith("*paper") else name
        p = e.dxf.get("insert") or e.dxf.get("defpoint")
        if p is not None:
            for x0, x1, name in spans:
                if x0 <= p[0] <= x1:
                    return name
    except Exception:
        pass
    return "model space"


def check_dxf(path, customer_ok: bool | None = None) -> list[Finding]:
    """customer_ok None: decided from the file name (made_for_customer)."""
    import ezdxf
    path = Path(path)
    doc = ezdxf.readfile(path)
    spans = _sheet_map(doc)
    if customer_ok is None:
        customer_ok = made_for_customer(path)
    out = []
    seen = set()
    for e, t in _texts(doc):
        for reason in check_text(t, customer_ok):
            key = (e.dxf.handle, reason)
            if key in seen:
                continue
            seen.add(key)
            out.append(Finding(str(path), _where(e, spans), " ".join(t.split())[:160], reason))
    return out


def latest_fast_drawings() -> list[Path]:
    """With no paths: the newest fast drawing of every document under each Fast_Drawings folder of the job (the
    typicals and every project). Fast_Edits/ is gitignored, so on the check server this finds none."""
    root = next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists())
    out = []
    for fd in sorted((root / "job").glob("*/03_Working_Design/Fast_Edits/Fast_Drawings")):
        for doc in sorted(p for p in fd.iterdir() if p.is_dir()):
            runs = sorted((p for p in doc.iterdir() if p.is_dir() and re.search(r"-fast-\d{3}$", p.name)),
                          key=lambda p: int(p.name.rsplit("-", 1)[-1]))
            if runs:
                out += sorted(runs[-1].glob("*.dxf"))
    return out


def _files(args) -> list[Path]:
    if not args:
        return latest_fast_drawings()
    out = []
    for a in args:
        p = Path(a)
        if p.is_dir():
            out += sorted(p.rglob("*.dxf"))
        elif p.exists():
            out.append(p)
        else:
            raise FileNotFoundError(a)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("paths", nargs="*", help="DXF files or folders (none: the newest fast drawing of each document)")
    ap.add_argument("--json", action="store_true", help="print the findings as JSON after the summary")
    a = ap.parse_args(argv)
    try:
        files = _files(a.paths)
        if not files:
            if a.paths:
                print("sheet_face: ERROR no DXF found")
                return 3
            if rp.skip_no_project("sheet_face"):   # a new job with no project yet (harness/tests/test_job_new.py)
                return 0
            print("sheet_face: PASS - no fast drawings in this checkout (filed revisions are a record, not rechecked)")
            return 0
        findings = [f for p in files for f in check_dxf(p)]
    except Exception as exc:  # noqa: BLE001
        print(f"sheet_face: ERROR {exc}")
        return 3
    if findings:
        print(f"sheet_face: FAIL {len(findings)} internal reference(s) on {len({f.file for f in findings})} of "
              f"{len(files)} drawing(s) ({RULE_ID})")
    else:
        print(f"sheet_face: PASS {len(files)} drawing(s), no internal reference ({RULE_ID})")
    if a.json:
        print(json.dumps([f._asdict() for f in findings], indent=1))
    else:
        for f in findings:
            print(f"  {Path(f.file).name} | {f.sheet} | {f.reason} | {f.text!r}")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
