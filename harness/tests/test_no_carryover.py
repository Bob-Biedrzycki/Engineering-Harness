"""Guard: nothing from an earlier job carries over into this job's repo.

CPME practice (Bob, chat, 2026-10-26: nothing from an earlier job belongs in a job repo; Bob, 2026-10-27: the harness
names no job). The banned terms are the job's own list, job/carryover-terms.txt (format and sections:
harness/lib/carryover_terms.py; every term written reversed). This test scans every text file in the repository and
fails on any hit of the enforced sections. No terms file: nothing is banned, and the test passes.

Run alone to list every hit as file:line:
    harness/tools/venv/Scripts/python.exe harness/tests/test_no_carryover.py
"""
from __future__ import annotations

import re
import sys
import tempfile
import unittest
from pathlib import Path

REPO = next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists())
sys.path.insert(0, str(REPO / "harness" / "lib"))
import carryover_terms as CT  # noqa: E402

TERMS_FILE = REPO / "job" / "carryover-terms.txt"
SKIP_DIRS = {".git", "__pycache__", "node_modules"}
SKIP_PREFIXES = (REPO / "harness" / "tools",)

# Lines that match a pattern but are not carry-over: the model line of an agent file's frontmatter.
ALLOWED_LINE = re.compile(r"^\s*model:\s*opus\s*$")   # in .claude/agents/*.md only
# A DXF line that is only a number or a hex entity handle (group code values: coordinates, handles, pointers) is
# drawing data, not words: the CL-R4 GA revA DXF has an LWPOLYLINE whose handle reads like the old job number
# (2026-11-03). Text in a DXF (TEXT, MTEXT, attributes) still has letters or spaces and is still scanned.
DXF_DATA_LINE = re.compile(r"^\s*[-+]?[0-9A-Fa-f]+(?:\.[0-9]*)?(?:[eE][-+]?\d+)?\s*$")
# PDF content is compressed streams; a match there is noise, not text (a maker's installation manual, 2026-11-03).
# The words of our own drawings are scanned in their DXF.
SKIP_SUFFIXES = {".pdf"}


def _is_text(path: Path) -> bool:
    try:
        head = path.read_bytes()[:8192]
    except OSError:
        return False
    return b"\x00" not in head


def _files(root: Path = REPO, skip_prefixes=SKIP_PREFIXES):
    stack = [root]
    while stack:
        d = stack.pop()
        try:
            entries = list(d.iterdir())
        except OSError:
            continue
        for p in entries:
            if p.is_dir():
                if p.name in SKIP_DIRS or any(p == s or s in p.parents for s in skip_prefixes):
                    continue
                stack.append(p)
            elif p.is_file() and _is_text(p):   # the terms file is scanned too: its terms are written reversed
                yield p


def hits(root: Path = REPO, terms_file: Path | None = None) -> list[str]:
    patterns = CT.compiled(CT.load(terms_file or root / "job" / "carryover-terms.txt"))
    if not patterns:
        return []
    out: list[str] = []
    for path in _files(root, (root / "harness" / "tools",)):
        if path.suffix.lower() in SKIP_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = path.relative_to(root).as_posix()
        agent_file = rel.startswith(".claude/agents/") and rel.endswith(".md")
        dxf = path.suffix.lower() == ".dxf"
        for n, line in enumerate(text.splitlines(), 1):
            if agent_file and ALLOWED_LINE.match(line):
                continue
            if dxf and DXF_DATA_LINE.match(line):
                continue
            for label, pat in patterns:
                m = pat.search(line)
                if m:
                    out.append(f"{rel}:{n}: {label}: {m.group(0)!r}")
    return sorted(out)


class NoCarryOver(unittest.TestCase):
    def test_terms_file_samples(self):
        """Each section's catch samples are caught by its patterns; spare samples by no enforced pattern."""
        secs = CT.load(TERMS_FILE)
        enforced = CT.compiled(secs)
        for name, sec in secs.items():
            own = [re.compile(p) for _, p in sec.patterns]
            for s in sec.catch:
                self.assertTrue(any(p.search(s) for p in own), f"[{name}] catch sample not caught: {s!r}")
            check = own if name == "this-job" else [p for _, p in enforced]
            for s in sec.spare:
                self.assertFalse(any(p.search(s) for p in check), f"[{name}] spare sample caught: {s!r}")
        self.assertTrue(ALLOWED_LINE.match("model: opus"))

    def test_repo_has_no_carryover(self):
        found = hits()
        self.assertEqual(found, [], f"{len(found)} carry-over hit(s):\n" + "\n".join(found))


class TermsFormat(unittest.TestCase):
    """The format itself, on scratch text (no job's terms)."""

    def test_parse_sections_labels_comments(self):
        text = "\n".join(["# comment", "", CT.entry_line("old name", r"(?i)\bzorblax\b"), CT.rev(r"QX-\d{3}"),
                          CT.sample_line("catch", "the Zorblax job"), CT.sample_line("spare", "zorblaxes"),
                          "[banned-here]", CT.entry_line("old id", r"\bREC-00[5-9]\b"),
                          "[this-job]", CT.entry_line("this job", r"\bWIDGET\b")])
        s = CT.parse(text)
        self.assertEqual([lab for lab, _ in s["banned"].patterns], ["old name", CT.DEFAULT_LABEL])
        self.assertEqual(s["banned"].catch, ["the Zorblax job"])
        self.assertEqual(s["banned"].spare, ["zorblaxes"])
        labels = [lab for lab, _ in CT.compiled(s)]
        self.assertEqual(labels, ["old name", CT.DEFAULT_LABEL, "old id"])   # [this-job] not enforced
        self.assertTrue(any(p.search("see QX-123") for _, p in CT.compiled(s)))
        with self.assertRaises(ValueError):
            CT.parse("[nonsense]\n")
        with self.assertRaises(ValueError):
            CT.parse(CT.rev("(unclosed") + "\n")

    def test_missing_file_bans_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "note.md").write_text("anything at all\n", encoding="utf-8")
            self.assertEqual(CT.compiled(CT.load(root / "job" / "carryover-terms.txt")), [])
            self.assertEqual(hits(root), [])

    def test_hits_in_scratch_repo(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "job").mkdir()
            (root / "job" / "carryover-terms.txt").write_text(CT.entry_line("old name", r"(?i)zorblax") + "\n",
                                                               encoding="utf-8")
            (root / "a.md").write_text("ok\nthe Zorblax skid\n", encoding="utf-8")
            self.assertEqual(hits(root), ["a.md:2: old name: 'Zorblax'"])

    def test_dxf_numbers_and_pdf_skipped(self):
        """A DXF handle or coordinate line, and PDF content, are data; DXF text is still scanned."""
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "job").mkdir()
            (root / "job" / "carryover-terms.txt").write_text(CT.entry_line("old number", r"\b4321\b") + "\n",
                                                               encoding="utf-8")
            (root / "a.dxf").write_text("  5\n4321\n 10\n4321.0\n  1\nJOB 4321 NOTE\n", encoding="utf-8")
            (root / "b.pdf").write_text("stream 4321 endstream\n", encoding="utf-8")
            self.assertEqual(hits(root), ["a.dxf:6: old number: '4321'"])

    def test_next_job_text(self):
        s = CT.parse("\n".join([CT.entry_line("old", r"\bOLDJOB\b"), CT.sample_line("spare", "goldjob"),
                                "[banned-here]", CT.entry_line("old id", r"\bREC-0007\b"),
                                "[this-job]", CT.entry_line("this", r"\bNEWJOB\b"), CT.sample_line("catch", "NEWJOB-1"),
                                CT.sample_line("spare", "NEWJOBS")]))
        n = CT.parse(CT.next_job_text(s, "# header"))
        self.assertEqual([lab for lab, _ in n["banned"].patterns], ["old", "this"])
        self.assertEqual(n["banned"].catch, ["NEWJOB-1"])
        self.assertEqual(n["banned"].spare, ["goldjob", "NEWJOBS"])
        self.assertEqual(n["banned-here"].patterns, [])
        self.assertEqual(n["this-job"].patterns, [])


if __name__ == "__main__":
    found = hits()
    print("\n".join(found))
    print(f"{len(found)} hit(s)")
    sys.exit(1 if found else 0)
