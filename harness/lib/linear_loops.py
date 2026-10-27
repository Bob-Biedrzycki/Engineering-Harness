"""linear_loops.py - the Linear loop-closing audit (TR-12; Bob, 2026-10-07: "do it").

Four rules in CLAUDE.md (notice block and "Where things are tracked"): every handoff and every question entry names its
Linear issue (CPM-nn); every issue touched today carries a comment from today; every `NEXT:` line that names an agent
has an issue opened for that agent today (or names its CPM-nn); and a handoff that could not reach Linear says
`LINEAR: unavailable (<reason>)`. Handoffs are today's <project>/_work/daily/<date>*.md/.txt files, except close-out's own
outputs and track.py inputs and artefacts (any name ending -paths.txt, -commit.md or -go.txt). This module only REPORTS: closeout.py step 7 and track.py daily-pr print its
findings as warnings, and nothing here changes an exit code.

closeout.py is a plain script with no MCP access, so it sees Linear only through an export file the
project-manager writes from the mcp__linear-server tools before close-out, by default
<project>/_work/daily/<date>-linear.json:

    {"exported": "<ISO>", "issues": [{"id": "CPM-120", "title": "...", "labels": ["role:software-developer"],
      "createdAt": "<ISO>", "updatedAt": "<ISO>", "comments": [{"createdAt": "<ISO>"}]}]}

The functions down to `pr_body_linear_warning` are pure (no I/O) and tested in harness/tests/test_linear_loops.py;
`handoff_files`, `read_handoffs` and `load_linear_export` read files and never write. Stdlib only.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

CPM_REF = re.compile(r"\bCPM-\d+\b")

AGENTS = (
    "cad-design-engineer",
    "controls-engineer",
    "electrical-engineer",
    "engineering-manager",
    "process-engineer",
    "project-manager",
    "mechanical-piping-engineer",
    "software-developer",
)
_AGENT_RE = re.compile(r"(?<![\w-])(" + "|".join(re.escape(a) for a in AGENTS) + r")(?![\w-])")
# Question entry heading: Q-nnnn (Bob, chat, 2026-10-26).
_QUESTION_HEAD = re.compile(r"^#{2,4}\s+(Q-\d+)\b")
_ANY_HEAD = re.compile(r"^#{1,6}\s")
HANDOFF_SUFFIXES = (".md", ".txt")
# close-out's own outputs and track.py inputs and artefacts, never handoffs (2026-10-07): <date>-paths.txt,
# <date>-commit.md, any variant such as <date>-linear-paths.txt or <date>-linear-commit.md, and <date>-go.txt
# (Bob's go, saved verbatim by `track.py daily`; it warned "no CPM ref: 2026-10-07-go.txt" on its first day)
NOT_HANDOFF_ENDINGS = ("-paths.txt", "-commit.md", "-go.txt")
UNAVAILABLE = "LINEAR: unavailable"


# ------------------------------------------------------------------ pure
def cpm_refs(text: str) -> list[str]:
    """Unique CPM-nn ids in order of first appearance."""
    return list(dict.fromkeys(CPM_REF.findall(text or "")))


def next_lines(text: str) -> list[str]:
    """Every line whose stripped text starts with 'NEXT:' (case-sensitive), stripped."""
    return [ln.strip() for ln in (text or "").splitlines() if ln.strip().startswith("NEXT:")]


def next_agent(line: str) -> str | None:
    """The first agent name (AGENTS) in the line, or None ('NEXT: none', free text)."""
    m = _AGENT_RE.search(line or "")
    return m.group(1) if m else None


def question_entries_dated(questions_text: str, date: str) -> dict[str, str]:
    """{entry id: entry text} for every Agent-to-Agent Questions.md entry whose text contains `date`. An entry starts at a heading
    that carries its id (`### Q-0115`) and ends at the next heading of any kind; fenced code (the entry-format
    template) is skipped."""
    entries: dict[str, list[str]] = {}
    cur: str | None = None
    fence = False
    for ln in (questions_text or "").splitlines():
        if ln.lstrip().startswith("```"):
            fence = not fence
            continue
        if fence:
            continue
        if _ANY_HEAD.match(ln):
            m = _QUESTION_HEAD.match(ln)
            cur = m.group(1) if m else None
            if cur:
                entries.setdefault(cur, [])
        if cur:
            entries[cur].append(ln)
    return {k: "\n".join(v) for k, v in entries.items() if date in "\n".join(v)}


def _on(ts, date: str) -> bool:
    return isinstance(ts, str) and ts[:10] == date


def audit(handoffs: dict[str, str], questions: dict[str, str], linear: dict | None, date: str,
          unavailable_reason: str | None = None) -> dict:
    """The loop-closing findings for `date`. handoffs = {file name: text}; questions = question_entries_dated(...);
    linear = the export (or None when there is none). Every list is a warning, never a refusal."""
    res = {
        "no_ref": [n for n, t in handoffs.items() if not cpm_refs(t)]
                  + [f"{qid} (Agent-to-Agent Questions.md)" for qid, t in questions.items() if not cpm_refs(t)],
        "no_comment": [],
        "next_without_issue": [],
        "linear_unavailable_in_handoffs": [f"{n}: {ln.strip()}" for n, t in handoffs.items()
                                           for ln in t.splitlines() if UNAVAILABLE in ln],
        "unavailable": None,
        "ids_today": [],
    }
    if linear is None:
        res["unavailable"] = unavailable_reason or "no Linear export"
        return res
    issues = [i for i in (linear.get("issues") or []) if isinstance(i, dict)]
    today = [i for i in issues if _on(i.get("createdAt"), date) or _on(i.get("updatedAt"), date)]
    res["ids_today"] = list(dict.fromkeys(str(i.get("id", "?")) for i in today))
    res["no_comment"] = [f"{i.get('id', '?')} {i.get('title', '')}".rstrip() for i in today
                         if not any(_on((c or {}).get("createdAt"), date) for c in (i.get("comments") or []))]
    opened = {lab for i in issues if _on(i.get("createdAt"), date) for lab in (i.get("labels") or [])}
    for name, text in handoffs.items():
        for ln in next_lines(text):
            agent = next_agent(ln)
            if agent and not cpm_refs(ln) and f"role:{agent}" not in opened:
                res["next_without_issue"].append(f"{agent} (from {name}: {ln})")
    return res


def finding_lines(res: dict) -> list[str]:
    """One line per finding, for close-out's console and the commit body. Empty = nothing open."""
    L = [f"LINEAR: unavailable ({res['unavailable']})"] if res.get("unavailable") else []
    L += [f"no CPM ref: {x}" for x in res.get("no_ref", [])]
    L += [f"no comment today: {x}" for x in res.get("no_comment", [])]
    L += [f"NEXT: names an agent with no issue opened today: {x}" for x in res.get("next_without_issue", [])]
    L += [f"handoff could not reach Linear: {x}" for x in res.get("linear_unavailable_in_handoffs", [])]
    return L


def day_ids(handoffs: dict[str, str], linear: dict | None, date: str) -> list[str]:
    """CPM ids the day touched: refs in today's handoffs, then issues the export shows created or updated today."""
    ids = [r for t in handoffs.values() for r in cpm_refs(t)]
    if linear is not None:
        ids += audit({}, {}, linear, date)["ids_today"]
    return list(dict.fromkeys(ids))


def pr_body_linear_warning(body: str, day_ids: list[str]) -> str | None:
    """None when the PR body names a Linear issue (CPM-nn); otherwise one WARNING line (never a refusal)."""
    if cpm_refs(body):
        return None
    found = ", ".join(day_ids) if day_ids else "none found today (handoffs, Linear export)"
    return ("WARNING: the PR body names no Linear issue (CPM-nn). Name each issue the day advanced as "
            f"'Relates to CPM-nn' (TR-12). The day's issue ids: {found}")


# ------------------------------------------------------------------ read-only I/O
def export_path(daily_dir: Path, date: str) -> Path:
    return Path(daily_dir) / f"{date}-linear.json"


def handoff_files(daily_dir: Path, date: str) -> list[Path]:
    """Files directly under daily_dir named <date>... with suffix .md or .txt (never .log/.json/.csv), sorted.
    Skips close-out's own outputs and track.py inputs and artefacts: any name ending -paths.txt, -commit.md or
    -go.txt."""
    d = Path(daily_dir)
    if not d.is_dir():
        return []
    return sorted(p for p in d.iterdir()
                  if p.is_file() and p.name.startswith(date) and p.suffix.lower() in HANDOFF_SUFFIXES
                  and not p.name.lower().endswith(NOT_HANDOFF_ENDINGS))


def read_handoffs(daily_dir: Path, date: str) -> dict[str, str]:
    return {p.name: p.read_text(encoding="utf-8", errors="replace") for p in handoff_files(daily_dir, date)}


def load_linear_export(path: Path) -> dict | None:
    """The export as a dict, or None when it is missing, unreadable or not the documented shape."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("issues"), list):
        return None
    return data
