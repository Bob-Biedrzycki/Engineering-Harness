"""carryover_terms - read a job's job/carryover-terms.txt: the terms of earlier jobs that must not appear in this one.

CPME practice (Bob, 2026-10-27): the harness is the same in every job and names no job; each job lists the terms of
the jobs before it in its own job/carryover-terms.txt, and harness/tests/test_no_carryover.py fails on any hit.

File format (UTF-8, one entry per line):
  * blank lines and lines starting with `#` are comments;
  * `[banned]`, `[banned-here]` and `[this-job]` start a section; lines before any header are `[banned]`;
  * `<label> :: <pattern>` or just `<pattern>`: a Python regex WRITTEN REVERSED (the whole pattern string reversed),
    so the file itself carries none of the terms and scans clean; the label (not reversed) is what a hit reports;
  * `catch: <sample>` / `spare: <sample>`: a sample text, also reversed, that the section's patterns must / must not
    match (the test checks them, so a mistyped pattern is found at once).
Sections:
  [banned]       earlier jobs' terms: enforced here, and carried into a job made from this one (job_new.py)
  [banned-here]  enforced here only: record ids a new job reuses for its own records (decision numbers and the like)
  [this-job]     this job's own terms: not enforced here; job_new.py makes them [banned] in the next job
A missing file means no banned terms.

Stdlib only.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

SECTIONS = ("banned", "banned-here", "this-job")
ENFORCED = ("banned", "banned-here")
DEFAULT_LABEL = "carry-over term"
_HEADER = re.compile(r"^\[([\w-]+)\]\s*$")


def rev(s: str) -> str:
    """The terms are written reversed; reversing again gives the text."""
    return s[::-1]


@dataclass
class Section:
    patterns: list[tuple[str, str]] = field(default_factory=list)   # (label, pattern as read, i.e. un-reversed)
    catch: list[str] = field(default_factory=list)                   # samples, un-reversed
    spare: list[str] = field(default_factory=list)


def parse(text: str) -> dict[str, Section]:
    """{section: Section} from the file text. Raises ValueError on an unknown section or a pattern that does not
    compile, naming the line."""
    out = {s: Section() for s in SECTIONS}
    cur = "banned"
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = _HEADER.match(line)
        if m:
            if m.group(1) not in SECTIONS:
                raise ValueError(f"line {n}: unknown section [{m.group(1)}] (known: {', '.join(SECTIONS)})")
            cur = m.group(1)
            continue
        if line.startswith("catch:"):
            out[cur].catch.append(rev(line[len("catch:"):].strip()))
            continue
        if line.startswith("spare:"):
            out[cur].spare.append(rev(line[len("spare:"):].strip()))
            continue
        label, sep, pat = line.partition(" :: ")
        if not sep:
            label, pat = DEFAULT_LABEL, line
        pat = rev(pat.strip())
        try:
            re.compile(pat)
        except re.error as e:
            raise ValueError(f"line {n}: pattern does not compile once reversed ({e}): {pat!r}") from e
        out[cur].patterns.append((label.strip() or DEFAULT_LABEL, pat))
    return out


def load(path: Path) -> dict[str, Section]:
    """parse() of the file, or empty sections when it does not exist."""
    p = Path(path)
    return parse(p.read_text(encoding="utf-8")) if p.is_file() else {s: Section() for s in SECTIONS}


def compiled(sections: dict[str, Section], names=ENFORCED) -> list[tuple[str, re.Pattern[str]]]:
    """(label, compiled pattern) of the named sections, in file order."""
    return [(label, re.compile(p)) for s in names for label, p in sections[s].patterns]


def entry_line(label: str, pattern: str) -> str:
    """One file line for a pattern given forward (written reversed)."""
    return f"{label} :: {rev(pattern)}"


def sample_line(kind: str, text: str) -> str:
    return f"{kind}: {rev(text)}"


def next_job_text(sections: dict[str, Section], header: str) -> str:
    """The carry-over file for a job made from this one: this job's [banned] and [this-job] become the new job's
    [banned] (with their catch samples); spare samples are kept only where the combined patterns still spare them;
    [banned-here] is not carried (its ids are reused). An empty [this-job] section is left for the new job to fill."""
    pats = sections["banned"].patterns + sections["this-job"].patterns
    rx = [re.compile(p) for _, p in pats]
    catch = sections["banned"].catch + sections["this-job"].catch
    spare = [s for s in sections["banned"].spare + sections["this-job"].spare if not any(r.search(s) for r in rx)]
    lines = [header.rstrip(), "", "[banned]"]
    lines += [entry_line(label, p) for label, p in pats]
    lines += [sample_line("catch", s) for s in catch]
    lines += [sample_line("spare", s) for s in spare]
    lines += ["", "[banned-here]", "", "[this-job]",
              "# This job's own terms (job name, product code, first project number, Drive folder id), reversed,",
              "# so the next job made from this one bans them. Not enforced in this job.", ""]
    return "\n".join(lines)
