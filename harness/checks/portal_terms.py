"""portal_terms - forbidden-terms lint for the CPME portal output.

The site framework (project tracker, quoting/estimating portal, landing page) is CPME practice and dormant
until Bob defines the job's site.

The fabricator portal (the Fabrication Estimating Portal, record ID quoting-portal) must not show internal working language: who or what drafted the
design, questions and assumptions, holds, record IDs, DRAFT / review wording or the repository.
The internal portal is linted the same way in warn mode, so a new term is visible before it can
leak into the fabricator build.

    python harness/checks/portal_terms.py                                  # CI: newest filed portals
    python harness/checks/portal_terms.py --dir <project>/_work/portal            # internal build, warn mode
    python harness/checks/portal_terms.py --dir <project>/_work/quoting --audience fabricator   # fail mode
    python harness/checks/portal_terms.py --dir <project>/_work/portal --json <project>/_work/logs/terms.json

Scanned: every *.html page (visible text, alt / title / placeholder / aria-label attributes, and the
JSON tables and markdown documents embedded in the page) and every data/ bundle file (HTML strings in
data/**/*.js, string values in data/**/*.json). The data store is the folder's own data/, or for a filed
revision the store beside it (../data/). Not scanned: assets/ media.
Fabricator audience, in addition: the vendor and model names of <project>/03_Working_Design/PID/02_Tag_Lists/equipment-list.csv
and the manufacturer and model of every component register row (job/components/component-register.csv, then
<project>/03_Working_Design/CAD/05_Purchased_Components/component-register.csv; harness/lib/components.py) are forbidden terms too, and so are the portal's old name and issue wording
("Quoting Portal", "Quote Portal", "Issued for Quotation", "IFQ"; Site Rev 3); the comments in every shipped script and
stylesheet (inline in the pages, assets/*.js / *.css, and from Site Rev 4 the shared ../assets/ scripts and
stylesheets the folder's shared-assets.json lists) are scanned; and so are the node, mesh and
material names of the web GLBs in the store's glb/ (anyone can download and open them).
Fabricator audience: any hit is FAIL (exit 1). Internal audience: hits are reported, exit 0.
With no --dir: the newest <project>/06_Issued_Revisions/Portals/project-portal revision (internal, warn) and, once they exist,
the newest <project>/06_Issued_Revisions/Portals/quoting-portal and <project>/06_Issued_Revisions/Portals/portal-landing revisions (fabricator, fail).
Exit 0 PASS, 1 FAIL, 3 ERROR (could not run). First line is the summary.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import struct
import sys
from collections import Counter, defaultdict
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists()) / "harness" / "lib"))
import repo_paths as rp  # noqa: E402
import components  # noqa: E402

I = re.I
TERMS = [  # (label, pattern, flags)
    ("AI", r"(?<!Rev )\bAI\b", 0),   # not the revision letter "Rev AI"
    ("agent", r"\bagents?\b", I), ("Claude", r"\bClaude\b", I), ("Opus", r"\bOpus\b", I),
    ("Q-n", r"\bQ-\d{4}\b", 0), ("assumption", r"\bassumptions?\b", I),   # Q-nnnn: internal question ids
    ("question", r"\bquestions?\b", I), ("HOLD", r"\bHOLDs?\b", 0), ("TR-n", r"\bTR-\d", 0), ("DEC-n", r"\bDEC-\d", 0),
    ("A-n", r"\bA-\d", 0), ("CMP-n", r"\bCMP-\d", 0), ("COMP-n", r"\bCOMP-\d", 0), ("chat", r"\bchat\b", I), ("DRAFT", r"\bDRAFT\b", I),
    ("engineer review", r"\bengineer review", I), ("repository", r"\brepository\b", I),
]
COMPILED = [(k, re.compile(p, f)) for k, p, f in TERMS]
# fabricator audience only (the tracker has an Original Quote page): the portal's old name and issue wording, so they
# cannot come back after the rename to Fabrication Estimating Portal (Site Rev 3; Bob, 2026-10-05: "Rename Quote portal
# to Fabrication Estimating Portal, would like to use quoting for different purpose in the future")
FAB_TERMS = [("old portal name", r"\bQuot(?:ing|e) Portal\b", I), ("Issued for Quotation", r"\bIssued for Quotation\b", I),
             ("IFQ", r"\bIFQ\b", 0)]
SHOWN_ATTRS = {"alt", "title", "placeholder", "aria-label"}
TEXT_SCRIPTS = {"application/json", "text/markdown"}
VENDOR_STOP = {"the", "company", "control", "engineering", "supply", "manufacturer", "unknown", "cpme", "oem", "not",
               "disclosed", "selected", "part", "number", "and", "&"}


def vendor_terms() -> list[str]:
    """Vendor and model names: each vendor's words (less generic ones) and each model's first token, plus its
    head before the first "-" when that is itself a part code (AS20H3-P062S54000 -> AS20H3)."""
    pairs: list[tuple[str, str]] = []
    eq = rp.DATA / "equipment-list.csv" if rp.HAS_PROJECT else None
    if eq is not None and eq.is_file():
        with open(eq, newline="", encoding="utf-8-sig") as fh:
            pairs += [(r.get("vendor") or "", r.get("model") or "") for r in csv.DictReader(fh)]
    pairs += components.vendor_names()   # job component register, then the project's (manufacturer, model)
    out = set()
    for vendor, model in pairs:
        for w in re.split(r"[\s;,()]+", re.sub(r"\([^)]*\)", " ", vendor)):
            if len(w) >= 3 and w.lower() not in VENDOR_STOP:
                out.add(w)
        m = re.sub(r"\([^)]*\)", " ", model).split()
        if m and m[0].lower() not in VENDOR_STOP:
            out.add(m[0])
            head = m[0].split("-")[0]
            if head != m[0] and len(head) >= 3 and (re.search(r"\d", head) or head.isupper()):
                out.add(head)
    return sorted(out, key=len, reverse=True)


def fab_terms() -> list[tuple[str, re.Pattern]]:
    v = vendor_terms()
    return COMPILED + [(k, re.compile(p, f)) for k, p, f in FAB_TERMS] + [("vendor/model", re.compile(r"(?<![\w-])(?:" + "|".join(re.escape(w) for w in v) + r")(?![\w-])", re.I))]


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


def texts(root: Path, fab: bool = False):
    """(relative path, text) for every scanned file."""
    for f in sorted(root.glob("*.html")):
        page = f.read_text(encoding="utf-8")
        yield f.relative_to(root).as_posix(), html_text(page)
        if fab:   # comments shipped inside the page's own scripts and styles
            code = [m.group(2) for m in re.finditer(r"<(script|style)(?![^>]*application/json)(?![^>]*text/markdown)[^>]*>(.*?)</\1>", page, re.S)]
            yield f.relative_to(root).as_posix() + " (comments)", "\n".join(js_comments(c) for c in code) + "\n".join(
                re.findall(r"<!--(.*?)-->", page, re.S))
    if fab:
        # the folder's own assets/ (before Site Rev 4), and the shared assets its shared-assets.json lists, in the
        # site's (or the filed portal's) assets/ one level up (Site Rev 4, 2b)
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
    if not data.is_relative_to(root):
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


def lint(root: Path, fab: bool = False) -> tuple[Counter, dict, dict]:
    total, per_file, samples = Counter(), defaultdict(Counter), defaultdict(list)
    terms = fab_terms() if fab else COMPILED
    for name, text in texts(root, fab):
        for label, rx in terms:
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


def report(root: Path, audience: str, json_out: Path | None) -> int:
    total, per_file, samples = lint(root, fab=audience == "fabricator")
    n = sum(total.values())
    fail = audience == "fabricator" and n > 0
    where = rp.rel(root) if root.is_relative_to(rp.REPO) else str(root)
    if n == 0:
        print(f"portal_terms: PASS - {audience} {where}: no forbidden terms")
    elif fail:
        print(f"portal_terms: FAIL - {audience} {where}: {n} forbidden-term hits ({len(total)} terms) in {len(per_file)} files")
    else:
        print(f"portal_terms: PASS (warn mode) - {audience} {where}: {n} hits of {len(total)} terms in {len(per_file)} files; "
              "fails only on the fabricator audience")
    for label in [t[0] for t in TERMS + FAB_TERMS] + ["vendor/model"]:
        if total[label]:
            files = sum(1 for c in per_file.values() if c[label])
            print(f"  {'FAIL' if fail else 'warn'} {label:<16} {total[label]:>6} hits in {files} files")
            for s in samples[label]:
                print(f"       {s[:200]}")
    if json_out:
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(json.dumps({"root": where, "audience": audience, "total": dict(total),
                                        "files": {k: dict(v) for k, v in sorted(per_file.items())}}, indent=1), encoding="utf-8")
    return 1 if fail else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=Path, help="portal folder (built or filed)")
    ap.add_argument("--audience", choices=("internal", "fabricator"), default="internal")
    ap.add_argument("--json", type=Path, help="write the per-term and per-file counts here (to compare builds)")
    a = ap.parse_args()
    if a.dir:
        if not a.dir.is_dir():
            print(f"portal_terms: ERROR - {a.dir} is not a folder")
            return 3
        return report(a.dir.resolve(), a.audience, a.json)
    if rp.skip_no_project("portal_terms"):
        return 0
    targets =[(newest(rp.PORTAL_FILED, "project-portal"), "internal"),
               (newest(rp.QUOTING_FILED, "quoting-portal"), "fabricator"),
               (newest(rp.LANDING_FILED, "portal-landing"), "fabricator")]
    targets = [(p, aud) for p, aud in targets if p]
    if not targets:
        print("portal_terms: PASS - no filed portal to lint")
        return 0
    rc = 0
    for p, aud in targets:
        rc |= report(p, aud, None)
    return rc


if __name__ == "__main__":
    sys.exit(main())
