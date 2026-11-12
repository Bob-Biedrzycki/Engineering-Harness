"""portal_terms - forbidden-terms lint for the CPME portal output.

The site framework (project tracker, Mobile Optimized, landing page) is CPME practice and dormant until Bob defines
the job's site. Three audiences:
  internal    the project tracker and Mobile Optimized (and the landing page of a site with no estimating portal):
              internal working language (who or what drafted the design, questions and assumptions, holds, record
              IDs, DRAFT / review wording, the repository) is reported, never failed, because the tracker is the
              internal record and shows those on purpose. It keeps a new term visible before a public page could
              carry it.
  fabricator  the Fabrication Estimating Portal (record ID quoting-portal) and, on a site that has it, the landing page:
              the internal terms plus the vendor and model names of the P&ID equipment list and the component
              registers, the portal's old name and issue wording ("Quoting Portal", "Quote Portal", "Issued for
              Quotation", "IFQ"), the comments in every shipped script and stylesheet (inline in the pages,
              assets/*.js / *.css and the shared ../assets/ scripts and stylesheets the folder's shared-assets.json
              lists), and the node, mesh and material names of the web GLBs in the store's glb/ (anyone can download
              and open them). Any hit is FAIL.
  customer    the customer site (record ID customer-portal): everything the fabricator audience checks, plus a jargon
              list (JARGON) on the text a reader sees (spool, ferrule, weld, takeoff, cut list, BOM, HOLD, Q-, DEC-,
              TR-, gate), and CUST_IDS on every data-* attribute value of the pages, the string literals of their
              inline scripts and of the shared scripts they load, and the GLB part names: component record IDs,
              FM / PS / PL IDs, the internal model name (model_id_pattern), "ASME" / "BPE", long part numbers and vendor-coded material names
              (pm_...). Line, spool and joint IDs, the issue date and revision letters in file names are allowed
              (Bob, 2026-10-21). The drawing PDFs are not scanned. Any hit is FAIL.
A project has the fabricator and customer portals only when its builders make them (site_revs.portals()).
The harness names no job's own record-ID forms. A job adds its own words or IDs to the fabricator and customer
audiences in <project>/03_Working_Design/CAD/09_Presentation/site.yaml `forbidden_terms` (a list of Python regexes,
matched case-sensitively; each hit is reported under its pattern); no key, nothing added.

    python harness/checks/portal_terms.py                                        # CI: newest filed portals
    python harness/checks/portal_terms.py --dir <project>/_work/site/tracker       # tracker work build (warn mode)
    python harness/checks/portal_terms.py --dir <project>/_work/site/mobile        # Mobile Optimized work build
    python harness/checks/portal_terms.py --dir <project>/_work/site/estimating --audience fabricator
    python harness/checks/portal_terms.py --dir <project>/_work/site/customer --audience customer
    python harness/checks/portal_terms.py --dir <project>/_work/site/tracker --json <project>/_work/logs/terms.json

Scanned: every *.html page (visible text, alt / title / placeholder / aria-label attributes, and the
JSON tables and markdown documents embedded in the page) and every data/ bundle file (HTML strings in
data/**/*.js, string values in data/**/*.json). The data store is the folder's own data/, or for a filed
revision the store beside it (../data/). Not scanned: assets/ media; web GLBs only for the fabricator and customer
audiences (a filed revision answers only for the GLBs its own pages name).
With no --dir: the newest <project>/06_Issued_Revisions/Portals/project-portal, mobile-portal and portal-landing
revisions, once they exist, and on a project that has them the newest quoting-portal (fabricator; the landing page
then too) and customer-portal (customer) revisions.
Exit 0 PASS (internal hits are listed as warnings), 1 FAIL (fabricator or customer hits), 3 ERROR (could not run).
First line is the summary.
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import re
import struct
import sys
from collections import Counter, defaultdict
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists()) / "harness" / "lib"))
import repo_paths as rp  # noqa: E402

I = re.I
TERMS = [  # (label, pattern, flags)
    ("AI", r"(?<!Rev )\bAI\b", 0),   # not the revision letter "Rev AI"
    ("agent", r"\bagents?\b", I), ("Claude", r"\bClaude\b", I),
    ("Q-n", r"\bQ-\d{4}\b", 0), ("assumption", r"\bassumptions?\b", I),   # Q-nnnn: internal question ids
    ("question", r"\bquestions?\b", I), ("HOLD", r"\bHOLDs?\b", 0), ("TR-n", r"\bTR-\d", 0), ("DEC-n", r"\bDEC-\d", 0),
    ("A-n", r"\bA-\d", 0), ("CMP-n", r"\bCMP-\d", 0), ("COMP-n", r"\bCOMP-\d", 0), ("chat", r"\bchat\b", I), ("DRAFT", r"\bDRAFT\b", I),
    ("engineer review", r"\bengineer review", I), ("repository", r"\brepository\b", I),
]
COMPILED = [(k, re.compile(p, f)) for k, p, f in TERMS]
# fabricator audience only (the tracker may have an Original Quote page): the estimating portal's old name and issue
# wording, so they cannot come back after the rename to Fabrication Estimating Portal (Bob, 2026-10-05: "Rename Quote
# portal to Fabrication Estimating Portal, would like to use quoting for different purpose in the future")
FAB_TERMS = [("old portal name", r"\bQuot(?:ing|e) Portal\b", I), ("Issued for Quotation", r"\bIssued for Quotation\b", I),
             ("IFQ", r"\bIFQ\b", 0)]
# customer audience only (the customer site; Bob, 2026-10-21: short and plain wording, no jargon): shop and internal
# words the customer pages never show, on top of the fabricator terms
JARGON = [("spool", r"\bspools?\b", I), ("ferrule", r"\bferrules?\b", I), ("weld", r"\bweld(?:s|ed|ing|ment)?\b", I),
          ("takeoff", r"\btake-?offs?\b", I), ("cut list", r"\bcut[- ]lists?\b", I), ("BOM", r"\bBOMs?\b", 0),
          ("HOLD", r"\bHOLDs?\b", 0), ("Q-", r"\bQ-\d", 0), ("DEC-", r"\bDEC-", 0), ("TR-", r"\bTR-", 0),
          ("gate", r"\bgates?\b", I)]


def model_id_pattern() -> str:
    """The internal model names the customer site never shows: CPME's working model name form
    CPME-<nnnn-nn>-<TYPE>-Skid, and the project's retired model ID (project.yaml retired_model_id). The project's
    current model ID (project.yaml model_id) is not on the list: a project may issue it to the customer (Bob decides
    per project; it is then in the customer site's GLB file names)."""
    ids = (rp.RETIRED_MODEL_ID,) if rp.HAS_PROJECT else ()   # no project yet: the form only
    own = [re.escape(m) for m in ids if m and m != "unknown"]
    return r"\b(?:" + "|".join(own + [r"CPME-\d{4}-\d{2}-[A-Za-z]+-Skid"]) + r")\b"


# customer audience only (Bob, 2026-10-21: "Keep both.  Also, spool numbers are fine."): the internal IDs and catalogue
# text the customer site never carries, in its page text, its data-* attributes, the string literals of every script
# its pages load, and its web GLB's part names. Line, spool and joint IDs, the issue date and the revision letters in
# file names are allowed.
CUST_IDS = [("CMP record ID", r"C(?:O)?MP-\d", 0), ("frame/support/plate ID", r"\b(?:FM|PS|PL)-\d{3}", 0),
            ("model ID", model_id_pattern(), I), ("ASME BPE", r"\b(?:ASME|BPE)\b", 0),
            ("part number", r"(?<![\w.-])\d{7,}(?![\w.-])", 0), ("vendor-coded material", r"\bpm[_ ][a-z]", 0),   # GLB names are read with "_" as " "
            # catalogue words the vendor columns do not name (seen in vendor STEP part names)
            ("catalogue text", r"\b(?:CADENAS|Aseptoflex|LKLA|LKB|McMaster|IDNR|31WMP)", I),
            # record IDs also glued to the word before them ("suctionA-85"), not P&ID tags (PT-101) and not a revision
            # letter in a file name ("revA-")
            ("record ID in a name", r"(?<![0-9])(?<!rev)(?<!revA)A-\d+|(?<![A-Za-z0-9])TC-Q\d+"
                                    r"|(?<![A-Z0-9])(?:Q|DEC|EC|TR|SRC|FC|PRR)-\d+|(?<![A-Za-z0-9])H\d+(?![A-Za-z0-9])", 0),
            ("placeholder", r"\bunknown\b", I)]
SHOWN_ATTRS = {"alt", "title", "placeholder", "aria-label"}
TEXT_SCRIPTS = {"application/json", "text/markdown"}
VENDOR_STOP = {"the", "company", "control", "engineering", "supply", "manufacturer", "unknown", "cpme", "oem", "not",
               "disclosed", "selected", "part", "number", "and", "&"}
FAIL_AUDIENCES = ("fabricator", "customer")


def vendor_terms() -> list[str]:
    """Vendor and model names from the P&ID equipment list and the component registers (job and project): each
    vendor's words (less generic ones) and each model's first token, plus its head before the first "-" when that is
    itself a part code (AS20H3-P062S54000 -> AS20H3)."""
    out = set()
    for f in (rp.DATA / "equipment-list.csv", rp.JOB_COMPONENT_REGISTER, rp.COMPONENT_REGISTER):
        if not f.is_file():
            continue
        with open(f, newline="", encoding="utf-8-sig") as fh:
            for r in csv.DictReader(fh):
                maker = r.get("vendor") or r.get("manufacturer") or ""
                for w in re.split(r"[\s;,()]+", re.sub(r"\([^)]*\)", " ", maker)):
                    if len(w) >= 3 and w.lower() not in VENDOR_STOP:
                        out.add(w)
                m = re.sub(r"\([^)]*\)", " ", r.get("model") or "").split()
                if m and m[0].lower() not in VENDOR_STOP:
                    out.add(m[0])
                    head = m[0].split("-")[0]
                    if head != m[0] and len(head) >= 3 and (re.search(r"\d", head) or head.isupper()):
                        out.add(head)
    return sorted(out, key=len, reverse=True)


def pid_tags() -> set[str]:
    """Every equipment, valve and instrument tag on the P&ID lists (the customer site shows them)."""
    out = set()
    for f in ("equipment-list.csv", "valve-list.csv", "instrument-list.csv"):
        if not (rp.DATA / f).is_file():
            continue
        with open(rp.DATA / f, newline="", encoding="utf-8-sig") as fh:
            out |= {r["tag"].strip() for r in csv.DictReader(fh) if (r.get("tag") or "").strip()}
    return out


def site_terms(config: Path | None = None) -> list[tuple[str, re.Pattern]]:
    """The job's own forbidden words for the fabricator and customer audiences: site.yaml `forbidden_terms`, a list of
    Python regexes (case-sensitive), each reported as "site.yaml: <pattern>". No project, file or key: none."""
    if config is None and not rp.HAS_PROJECT:
        return []
    p = config or rp.SITE_CONFIG
    if not p.is_file():
        return []
    import yaml
    v = (yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("forbidden_terms") or []
    return [(f"site.yaml: {s}", re.compile(str(s))) for s in ([v] if isinstance(v, str) else v) if str(s).strip()]


def fab_terms(allow: set[str] = frozenset()) -> list[tuple[str, re.Pattern]]:
    """allow: words never treated as vendor or model names (the customer lint passes the P&ID tags: a tag such as
    TCV-101 can also be a component model name)."""
    v = [w for w in vendor_terms() if w not in allow]
    vend = [("vendor/model", re.compile(r"(?<![\w-])(?:" + "|".join(re.escape(w) for w in v) + r")(?![\w-])", re.I))] if v else []
    return COMPILED + [(k, re.compile(p, f)) for k, p, f in FAB_TERMS] + vend + site_terms()


def js_comments(src: str) -> str:
    """The comment text of a script or stylesheet (strings and regex literals skipped roughly: enough to see
    whether any comment was shipped, which is what the fabricator build must not do)."""
    out, i, n = [], 0, len(src)
    while i < n:
        c = src[i]
        if c in "\"'`":
            j = i + 1
            while j < n and src[j] != c:
                j += 2 if src[j] == "\\" else 1
            i = j + 1
        elif src.startswith("/*", i):
            j = src.find("*/", i + 2)
            out.append(src[i + 2:j if j > 0 else n])
            i = n if j < 0 else j + 2
        elif src.startswith("//", i) and (i == 0 or src[i - 1] in " \t\n;{}(),"):
            j = src.find("\n", i)
            out.append(src[i + 2:j if j > 0 else n])
            i = n if j < 0 else j
        else:
            i += 1
    return "\n".join(out)


def js_strings(src: str) -> list[str]:
    """The string literals of a script: '...', "..." and the text parts of `...` (a ${...} expression inside a
    template is read as code again, so nested literals count); comments and regex literals are skipped (a "/" after an
    operator, "(", ",", "=", ":", "[", "!", "&", "|", "?", "{", "}", ";" or "return" starts a regex)."""
    out: list[str] = []
    n = len(src)

    def code(i: int, close: str | None) -> int:
        depth = 0
        while i < n:
            c = src[i]
            if close and c == "}" and depth == 0:
                return i + 1
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
            if c in "\"'":
                j = i + 1
                while j < n and src[j] != c and src[j] != "\n":
                    j += 2 if src[j] == "\\" else 1
                out.append(src[i + 1:j])
                i = j + 1
            elif c == "`":
                i = template(i + 1)
            elif src.startswith("/*", i):
                j = src.find("*/", i + 2)
                i = n if j < 0 else j + 2
            elif src.startswith("//", i):
                j = src.find("\n", i)
                i = n if j < 0 else j
            elif c == "/":
                k = i - 1
                while k >= 0 and src[k] in " \t\r\n":
                    k -= 1
                if k < 0 or src[k] in "(,=:[!&|?{};+-*%<>~^" or src[max(0, k - 5):k + 1] == "return":
                    j, cls = i + 1, False
                    while j < n and src[j] != "\n" and (src[j] != "/" or cls):
                        if src[j] == "\\":
                            j += 1
                        elif src[j] == "[":
                            cls = True
                        elif src[j] == "]":
                            cls = False
                        j += 1
                    i = j + 1
                else:
                    i += 1
            else:
                i += 1
        return i

    def template(i: int) -> int:
        buf = []
        while i < n and src[i] != "`":
            if src[i] == "\\":
                buf.append(src[i:i + 2])
                i += 2
            elif src.startswith("${", i):
                buf.append(" ")
                i = code(i + 2, "}")
            else:
                buf.append(src[i])
                i += 1
        out.append("".join(buf))
        return i + 1

    code(0, None)
    return out


class Attrs(HTMLParser):
    """Every data-* attribute value of a page (the viewer hosts carry their GLB, keys and maps there)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []

    def handle_starttag(self, tag, attrs):
        self.out += [f"{k}={v}" for k, v in attrs if k.startswith("data-") and v]


def glb_names(p: Path) -> list[str]:
    b = p.read_bytes()
    jlen = struct.unpack("<I", b[12:16])[0]
    j = json.loads(b[20:20 + jlen])
    return [x.get("name", "") for k in ("nodes", "meshes", "materials") for x in j.get(k, [])]


def store_of(root: Path) -> Path | None:
    """The data store a portal folder reads: its own data/ (work build), else ../data/ (a filed revision)."""
    if (root / "data").is_dir():
        return root / "data"
    if re.search(r"-rev[A-Z]+$", root.name) and (root.parent / "data").is_dir():
        return root.parent / "data"
    return None


class Text(HTMLParser):
    """Collect what a reader can see: text, a few attributes, and the data scripts the page renders."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        self.out += [v for k, v in a.items() if k in SHOWN_ATTRS and v]
        if tag == "style" or (tag == "script" and (a.get("type") or "") not in TEXT_SCRIPTS):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in ("style", "script") and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)


def html_text(s: str) -> str:
    p = Text()
    p.feed(s)
    p.close()
    return "\n".join(p.out)


def strings(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for v in o.values():
            yield from strings(v)
    elif isinstance(o, list):
        for v in o:
            yield from strings(v)


def texts(root: Path, fab: bool = False, customer: bool = False):
    """(relative path, text) for every scanned file. fab: also the comments of the shipped scripts and stylesheets
    (" (comments)") and the web GLB part names (" (part names)"). customer: also each page's data-* attribute values
    (" (data attributes)") and the string literals of its inline scripts and of the shared scripts it loads
    (" (script strings)")."""
    for f in sorted(root.glob("*.html")):
        page = f.read_text(encoding="utf-8")
        yield f.relative_to(root).as_posix(), html_text(page)
        if fab:   # comments shipped inside the page's own scripts and styles
            code = [m.group(2) for m in re.finditer(r"<(script|style)(?![^>]*application/json)(?![^>]*text/markdown)[^>]*>(.*?)</\1>", page, re.S)]
            yield f.relative_to(root).as_posix() + " (comments)", "\n".join(js_comments(c) for c in code) + "\n".join(
                re.findall(r"<!--(.*?)-->", page, re.S))
        if customer:
            a = Attrs()
            a.feed(page)
            a.close()
            yield f.relative_to(root).as_posix() + " (data attributes)", "\n".join(a.out)
            js = [m.group(1) for m in re.finditer(r"<script(?![^>]*application/json)(?![^>]*text/markdown)(?![^>]*importmap)[^>]*>(.*?)</script>", page, re.S)]
            yield f.relative_to(root).as_posix() + " (script strings)", "\n".join(
                html.unescape(s) for c in js for s in js_strings(c))
    if customer:
        man = root / "shared-assets.json"
        if man.is_file():
            for n in json.loads(man.read_text(encoding="utf-8"))["assets"]:
                f = root.parent / "assets" / n
                if n.endswith(".js") and f.is_file() and not (f.name.startswith("skid-") and f.stat().st_size > 1_000_000):
                    yield (Path("..") / "assets" / n).as_posix() + " (script strings)", "\n".join(
                        html.unescape(s) for s in js_strings(f.read_text(encoding="utf-8")))
    if fab:
        # the folder's own assets/, and the shared assets its shared-assets.json lists, in the site's (or the filed
        # portal's) assets/ one level up
        files = list(root.glob("assets/*.js")) + list(root.glob("assets/*.css"))
        man = root / "shared-assets.json"
        if man.is_file():
            files += [root.parent / "assets" / n for n in json.loads(man.read_text(encoding="utf-8"))["assets"]
                      if n.endswith((".js", ".css")) and (root.parent / "assets" / n).is_file()]
        for f in sorted(files):
            if f.name.startswith("skid-") and f.stat().st_size > 1_000_000:   # base64 payloads, no source text
                continue
            shown = f.relative_to(root) if f.is_relative_to(root) else Path("..") / f.relative_to(root.parent)
            yield shown.as_posix() + " (comments)", js_comments(f.read_text(encoding="utf-8"))
    data = store_of(root)
    if data is None:
        return
    shown = lambda f: (f.relative_to(root) if f.is_relative_to(root) else Path("..") / f.relative_to(root.parent)).as_posix()  # noqa: E731
    # a filed revision shares the append-only store with every other revision of its portal: only the web GLBs its own
    # pages name are its to answer for (an older revision's GLB in the store is not reached and never published,
    # publish_site.trim_store); a work build's own data/ holds only its own
    own = None
    if fab and not data.is_relative_to(root):
        own = set(re.findall(r"glb/([\w.-]+?\.glb)(?![\w.-])", "\n".join(f.read_text(encoding="utf-8") for f in root.glob("*.html"))))
    for f in sorted(data.rglob("*")):
        if f.suffix == ".json":
            yield shown(f), "\n".join(strings(json.loads(f.read_text(encoding="utf-8"))))
        elif f.suffix == ".glb" and fab and (own is None or f.name in own):
            yield shown(f) + " (part names)", "\n".join(n.replace("_", " ") for n in glb_names(f))
        elif f.suffix == ".js" and f.parent.name != "glb":
            s = f.read_text(encoding="utf-8")
            m = re.match(r"PortalRev\.\w+\((.*)\);\s*$", s, re.S)
            if not m:
                yield shown(f), s
                continue
            args = json.loads("[" + m.group(1) + "]")
            yield shown(f), "\n".join(html_text(x) if "<" in x else x for x in strings(args))


def jargon_terms() -> list[tuple[str, re.Pattern]]:
    return [(f"jargon: {k}", re.compile(p, f)) for k, p, f in JARGON]


def lint(root: Path, fab: bool = False, customer: bool = False) -> tuple[Counter, dict, dict]:
    """Internal (default): the TERMS. fab: plus FAB_TERMS, vendor and model names, shipped comments and GLB part names.
    customer: the fabricator lint plus CUST_IDS on everything it reads, including the pages' data-* attributes and
    script string literals, plus the jargon list on what a reader sees. The drawing PDFs are never scanned."""
    total, per_file, samples = Counter(), defaultdict(Counter), defaultdict(list)
    fab = fab or customer
    # the customer site also allows the generic "Co." of a customer's name
    terms = fab_terms(pid_tags() | {"Co.", "Co"} if customer else frozenset()) if fab else COMPILED
    jargon = jargon_terms() if customer else []
    # customer: the internal IDs everywhere; the jargon list on what a reader sees (page text, data attributes, data
    # store strings), not on script literals (the shared scripts carry the other portals' table labels, which no
    # customer page renders) or GLB part names
    ids = [(k, re.compile(p, f)) for k, p, f in CUST_IDS] if customer else []
    for name, text in texts(root, fab, customer):
        shown = not name.endswith((" (comments)", " (part names)", " (script strings)"))
        for label, rx in terms + ids + (jargon if shown else []):
            for m in rx.finditer(text):
                total[label] += 1
                per_file[name][label] += 1
                if len(samples[label]) < 3:
                    a, b = max(0, m.start() - 50), min(len(text), m.end() + 50)
                    samples[label].append(f"{name}: …{' '.join(text[a:b].split())}…")
    return total, per_file, samples


def newest(folder: Path, prefix: str) -> Path | None:
    revs = [p for p in folder.glob(f"{prefix}-rev*") if p.is_dir()]
    return max(revs, key=lambda p: (len(p.name), p.name)) if revs else None


def report(root: Path, what: str, json_out: Path | None, audience: str | None = None) -> int:
    """Lint one folder. what: the label printed; audience: internal (warn), fabricator or customer (fail). When
    audience is not given, a what of "fabricator" or "customer" is the audience, anything else is internal."""
    audience = audience or (what if what in FAIL_AUDIENCES else "internal")
    total, per_file, samples = lint(root, fab=audience == "fabricator", customer=audience == "customer")
    n = sum(total.values())
    fail = audience in FAIL_AUDIENCES and n > 0
    where = rp.rel(root) if root.is_relative_to(rp.REPO) else str(root)
    if n == 0:
        print(f"portal_terms: PASS - {what} {where}: no {'forbidden' if audience in FAIL_AUDIENCES else 'listed'} terms")
    elif fail:
        print(f"portal_terms: FAIL - {what} {where}: {n} forbidden-term hits ({len(total)} terms) in {len(per_file)} files")
    else:
        print(f"portal_terms: PASS (warn mode) - {what} {where}: {n} hits of {len(total)} terms in {len(per_file)} files; "
              "the tracker shows internal records on purpose")
    for label in ([t[0] for t in TERMS + FAB_TERMS] + ["vendor/model"] + [t[0] for t in CUST_IDS]
                  + sorted(k for k in total if k.startswith(("jargon: ", "site.yaml: ")))):
        if total[label]:
            files = sum(1 for c in per_file.values() if c[label])
            print(f"  {'FAIL' if fail else 'warn'} {label:<16} {total[label]:>6} hits in {files} files")
            for s in samples[label]:
                print(f"       {s[:200]}")
    if json_out:
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(json.dumps({"root": where, "portal": what, "total": dict(total)}
                                       | ({"audience": audience} if audience != "internal" else {}) | {
                                        "files": {k: dict(v) for k, v in sorted(per_file.items())}}, indent=1), encoding="utf-8")
    return 1 if fail else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=Path, help="portal folder (built or filed)")
    ap.add_argument("--audience", choices=("internal", "fabricator", "customer"), default="internal",
                    help="internal (tracker, Mobile Optimized: warn mode), fabricator (the estimating portal) or customer "
                         "(the customer site): those two fail on any hit")
    ap.add_argument("--json", type=Path, help="write the per-term and per-file counts here (to compare builds)")
    a = ap.parse_args()
    if a.dir:
        if not a.dir.is_dir():
            print(f"portal_terms: ERROR - {a.dir} is not a folder")
            return 3
        return report(a.dir.resolve(), "portal" if a.audience == "internal" else a.audience, a.json, a.audience)
    if rp.skip_no_project("portal_terms"):
        return 0
    import site_revs   # which portals this project's builders make
    have = site_revs.portals()
    est = "estimating" in have
    targets = [(newest(rp.PORTAL_FILED, "project-portal"), "project tracker", "internal"),
               (newest(rp.MOBILE_FILED, "mobile-portal"), "Mobile Optimized", "internal"),
               # the landing page links the estimating portal for fabricators on a site that has one
               (newest(rp.LANDING_FILED, "portal-landing"), "landing page", "fabricator" if est else "internal")]
    if est:
        targets.append((newest(rp.QUOTING_FILED, "quoting-portal"), "Fabrication Estimating Portal", "fabricator"))
    if "customer" in have:
        targets.append((newest(rp.CUSTOMER_FILED, "customer-portal"), "customer site", "customer"))
    targets = [(p, what, aud) for p, what, aud in targets if p]
    if not targets:
        print("portal_terms: PASS - no filed portal to lint")
        return 0
    rc = 0
    for p, what, aud in targets:
        rc |= report(p, what, None, aud)
    return rc


if __name__ == "__main__":
    sys.exit(main())
