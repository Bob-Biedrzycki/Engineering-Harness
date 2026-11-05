"""portal_terms - forbidden-terms lint for the CPME portal output (the project tracker and Mobile Optimized).

The site framework (project tracker, Mobile Optimized, landing page) is CPME practice and dormant until Bob defines
the job's site. This job has no Fabrication Estimating Portal and no Customer Portal (Bob, chat, 2026-10-30), so the
lint has the tracker's rules only: internal working language (who or what drafted the design, questions and
assumptions, holds, record IDs, DRAFT / review wording, the repository) is reported, never failed, because the
tracker is the internal record and shows those on purpose. It keeps a new term visible before a public page could
carry it.

    python harness/checks/portal_terms.py                                        # CI: newest filed portals
    python harness/checks/portal_terms.py --dir <project>/_work/site/tracker       # tracker work build
    python harness/checks/portal_terms.py --dir <project>/_work/site/mobile        # Mobile Optimized work build
    python harness/checks/portal_terms.py --dir <project>/_work/site/tracker --json <project>/_work/logs/terms.json

Scanned: every *.html page (visible text, alt / title / placeholder / aria-label attributes, and the
JSON tables and markdown documents embedded in the page) and every data/ bundle file (HTML strings in
data/**/*.js, string values in data/**/*.json). The data store is the folder's own data/, or for a filed
revision the store beside it (../data/). Not scanned: assets/ media and web GLBs.
With no --dir: the newest <project>/06_Issued_Revisions/Portals/project-portal, mobile-portal and portal-landing
revisions, once they exist. Exit 0 PASS (hits are listed as warnings), 3 ERROR (could not run). First line is the
summary.
"""
from __future__ import annotations

import argparse
import json
import re
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
SHOWN_ATTRS = {"alt", "title", "placeholder", "aria-label"}
TEXT_SCRIPTS = {"application/json", "text/markdown"}

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


def texts(root: Path):
    """(relative path, text) for every scanned file."""
    for f in sorted(root.glob("*.html")):
        page = f.read_text(encoding="utf-8")
        yield f.relative_to(root).as_posix(), html_text(page)
    data = store_of(root)
    if data is None:
        return
    shown = lambda f: (f.relative_to(root) if f.is_relative_to(root) else Path("..") / f.relative_to(root.parent)).as_posix()  # noqa: E731
    for f in sorted(data.rglob("*")):
        if f.suffix == ".json":
            yield shown(f), "\n".join(strings(json.loads(f.read_text(encoding="utf-8"))))
        elif f.suffix == ".js" and f.parent.name != "glb":
            s = f.read_text(encoding="utf-8")
            m = re.match(r"PortalRev\.\w+\((.*)\);\s*$", s, re.S)
            if not m:
                yield shown(f), s
                continue
            args = json.loads("[" + m.group(1) + "]")
            yield shown(f), "\n".join(html_text(x) if "<" in x else x for x in strings(args))


def lint(root: Path) -> tuple[Counter, dict, dict]:
    total, per_file, samples = Counter(), defaultdict(Counter), defaultdict(list)
    for name, text in texts(root):
        for label, rx in COMPILED:
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


def report(root: Path, what: str, json_out: Path | None) -> int:
    total, per_file, samples = lint(root)
    n = sum(total.values())
    where = rp.rel(root) if root.is_relative_to(rp.REPO) else str(root)
    if n == 0:
        print(f"portal_terms: PASS - {what} {where}: no listed terms")
    else:
        print(f"portal_terms: PASS (warn mode) - {what} {where}: {n} hits of {len(total)} terms in {len(per_file)} files; "
              "the tracker shows internal records on purpose")
    for label in [t[0] for t in TERMS]:
        if total[label]:
            files = sum(1 for c in per_file.values() if c[label])
            print(f"  warn {label:<16} {total[label]:>6} hits in {files} files")
            for s in samples[label]:
                print(f"       {s[:200]}")
    if json_out:
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(json.dumps({"root": where, "portal": what, "total": dict(total),
                                        "files": {k: dict(v) for k, v in sorted(per_file.items())}}, indent=1), encoding="utf-8")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=Path, help="portal folder (built or filed)")
    ap.add_argument("--json", type=Path, help="write the per-term and per-file counts here (to compare builds)")
    a = ap.parse_args()
    if a.dir:
        if not a.dir.is_dir():
            print(f"portal_terms: ERROR - {a.dir} is not a folder")
            return 3
        return report(a.dir.resolve(), "portal", a.json)
    if rp.skip_no_project("portal_terms"):
        return 0
    targets = [(newest(rp.PORTAL_FILED, "project-portal"), "project tracker"),
               (newest(rp.MOBILE_FILED, "mobile-portal"), "Mobile Optimized"),
               (newest(rp.LANDING_FILED, "portal-landing"), "landing page")]
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
