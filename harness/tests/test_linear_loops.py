"""Unit tests for harness/lib/linear_loops.py: the TR-12 Linear loop-closing audit (Bob, 2026-10-07).
Pure functions plus a temp-dir test of handoff_files: no git, no gh, no network. Stdlib unittest:

    .\\harness\\tools\\venv\\Scripts\\python.exe -m unittest discover -s harness\\tests -v
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists())
sys.path.insert(0, str(REPO / "harness" / "lib"))
import linear_loops as LL  # noqa: E402

D = "2026-10-07"

QUESTIONS = """# Agent-to-Agent Questions

## Entry format

```
### Q-0000
- **Date:** 2026-10-07
```

---

## Entries

### Q-0114
- **Date:** 2026-10-05
- **From:** engineering-manager (CPM-149)
- **Answer:**

### Q-0115
- **Date:** 2026-10-07
- **From:** cad-design-engineer
- **Answer:**

### Q-0116
- **Date:** 2026-10-07
- **From:** software-developer (CPM-150)
- **Answer:**

### Q-0117
- **Date:** 2026-10-06
- **Answer:** answered 2026-10-07 by Bob

### X-0118
- **Date:** 2026-10-07
- **Answer:** not a question entry: only Q-nnnn headings are read
"""


def issue(id_, labels=(), created="2026-10-01T10:00:00Z", updated="2026-10-01T10:00:00Z", comments=(), title="t"):
    return {"id": id_, "title": title, "labels": list(labels), "createdAt": created, "updatedAt": updated,
            "comments": [{"createdAt": c} for c in comments]}


class Refs(unittest.TestCase):
    def test_cpm_refs_unique_in_order(self):
        self.assertEqual(LL.cpm_refs("Relates to CPM-150, CPM-129; again CPM-150 and xCPM-131 CPM-"),
                         ["CPM-150", "CPM-129"])

    def test_cpm_refs_none(self):
        self.assertEqual(LL.cpm_refs(""), [])
        self.assertEqual(LL.cpm_refs("no issue here"), [])


class Next(unittest.TestCase):
    TEXT = "intro\n  NEXT: none\nnext: cad-design-engineer\nNEXT: cad-design-engineer files Rev F (CPM-151)\n" \
           "NEXT: Bob decides\nNEXT: process-engineer then software-developer\n"

    def test_next_lines_case_sensitive_stripped(self):
        self.assertEqual(LL.next_lines(self.TEXT), [
            "NEXT: none", "NEXT: cad-design-engineer files Rev F (CPM-151)", "NEXT: Bob decides",
            "NEXT: process-engineer then software-developer"])

    def test_next_agent_none(self):
        self.assertIsNone(LL.next_agent("NEXT: none"))
        self.assertIsNone(LL.next_agent("NEXT: Bob decides"))

    def test_next_agent_first_named(self):
        self.assertEqual(LL.next_agent("NEXT: process-engineer then software-developer"), "process-engineer")
        self.assertEqual(LL.next_agent("NEXT: label role:software-developer"), "software-developer")

    def test_next_agent_with_cpm_ref(self):
        self.assertEqual(LL.next_agent("NEXT: cad-design-engineer files Rev F (CPM-151)"), "cad-design-engineer")


class Questions(unittest.TestCase):
    def test_entries_dated(self):
        got = LL.question_entries_dated(QUESTIONS, D)
        # the template in the fence is skipped; Q-0117 is dated by its answer; X-0118 is not a question heading
        self.assertEqual(sorted(got), ["Q-0115", "Q-0116", "Q-0117"])
        self.assertIn("cad-design-engineer", got["Q-0115"])
        self.assertNotIn("Q-0116", got["Q-0115"])
        self.assertNotIn("X-0118", got["Q-0117"])

    def test_no_entries(self):
        self.assertEqual(LL.question_entries_dated(QUESTIONS, "2026-01-01"), {})


class Audit(unittest.TestCase):
    HAND = {
        f"{D}-a.md": "work for CPM-150\nNEXT: project-manager commits\n",
        f"{D}-b.txt": "no ref here\nNEXT: none\nLINEAR: unavailable (tool missing)\n",
        f"{D}-c.md": "CPM-152 done\nNEXT: cad-design-engineer rebuilds (CPM-153)\nNEXT: controls-engineer reviews\n",
    }

    def test_without_export(self):
        r = LL.audit(self.HAND, LL.question_entries_dated(QUESTIONS, D), None, D,
                     unavailable_reason=f"no export at x/{D}-linear.json")
        self.assertEqual(r["no_ref"], [f"{D}-b.txt", "Q-0115 (Agent-to-Agent Questions.md)",
                                       "Q-0117 (Agent-to-Agent Questions.md)"])
        self.assertEqual(r["no_comment"], [])
        self.assertEqual(r["next_without_issue"], [])
        self.assertEqual(r["ids_today"], [])
        self.assertEqual(r["unavailable"], f"no export at x/{D}-linear.json")
        self.assertEqual(r["linear_unavailable_in_handoffs"], [f"{D}-b.txt: LINEAR: unavailable (tool missing)"])
        lines = LL.finding_lines(r)
        self.assertTrue(lines[0].startswith("LINEAR: unavailable (no export"))

    def test_default_unavailable_reason(self):
        self.assertEqual(LL.audit({}, {}, None, D)["unavailable"], "no Linear export")

    def test_with_export(self):
        linear = {"exported": f"{D}T20:00:00Z", "issues": [
            issue("CPM-150", ["role:software-developer"], updated=f"{D}T15:00:00Z", comments=[f"{D}T15:00:00Z"]),
            issue("CPM-152", ["role:cad-design-engineer"], updated=f"{D}T09:00:00Z", comments=["2026-10-06T09:00:00Z"],
                  title="rebuild"),
            issue("CPM-154", ["role:project-manager"], created=f"{D}T08:00:00Z", updated=f"{D}T08:00:00Z"),
            issue("CPM-140", ["role:controls-engineer"]),     # neither today: not audited, and opened earlier
        ]}
        r = LL.audit(self.HAND, {}, linear, D)
        self.assertIsNone(r["unavailable"])
        self.assertEqual(r["ids_today"], ["CPM-150", "CPM-152", "CPM-154"])
        self.assertEqual(r["no_comment"], ["CPM-152 rebuild", "CPM-154 t"])
        # project-manager has an issue opened today; cad-design-engineer's NEXT names CPM-153; controls-engineer has none
        self.assertEqual(r["next_without_issue"], [f"controls-engineer (from {D}-c.md: NEXT: controls-engineer reviews)"])
        self.assertEqual(r["no_ref"], [f"{D}-b.txt"])

    def test_nothing_open(self):
        linear = {"issues": [issue("CPM-150", ["role:project-manager"], created=f"{D}T08:00:00Z",
                                   updated=f"{D}T08:00:00Z", comments=[f"{D}T09:00:00Z"])]}
        r = LL.audit({f"{D}-a.md": "CPM-150\nNEXT: project-manager commits\n"}, {}, linear, D)
        self.assertEqual(LL.finding_lines(r), [])

    def test_day_ids(self):
        linear = {"issues": [issue("CPM-160", updated=f"{D}T01:00:00Z"), issue("CPM-150", updated=f"{D}T01:00:00Z")]}
        self.assertEqual(LL.day_ids(self.HAND, linear, D), ["CPM-150", "CPM-152", "CPM-153", "CPM-160"])
        self.assertEqual(LL.day_ids(self.HAND, None, D), ["CPM-150", "CPM-152", "CPM-153"])


class Files(unittest.TestCase):
    def test_handoff_files_and_export(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            for n in (f"{D}-a.md", f"{D}-b.txt", f"{D}-checks.log", f"{D}-linear.json", f"{D}-moves.csv",
                      "2026-10-06-a.md", "notes.md",
                      # close-out outputs and track.py inputs are not handoffs
                      f"{D}-paths.txt", f"{D}-commit.md", f"{D}-linear-paths.txt", f"{D}-linear-commit.md"):
                (d / n).write_text("x", encoding="utf-8")
            (d / f"{D}-checks").mkdir()
            self.assertEqual([p.name for p in LL.handoff_files(d, D)], [f"{D}-a.md", f"{D}-b.txt"])
            self.assertEqual(LL.handoff_files(d / "missing", D), [])
            self.assertIsNone(LL.load_linear_export(d / f"{D}-linear.json"))         # "x" is not JSON
            self.assertIsNone(LL.load_linear_export(d / "absent.json"))
            p = LL.export_path(d, D)
            p.write_text(json.dumps({"exported": D, "issues": []}), encoding="utf-8")
            self.assertEqual(LL.load_linear_export(p), {"exported": D, "issues": []})
            p.write_text(json.dumps({"issues": "no"}), encoding="utf-8")
            self.assertIsNone(LL.load_linear_export(p))


class PrBody(unittest.TestCase):
    def test_warning_with_ids(self):
        w = LL.pr_body_linear_warning("## Todd's requirements\n## Drawings filed\n", ["CPM-150", "CPM-151"])
        self.assertTrue(w.startswith("WARNING:"))
        self.assertIn("names no Linear issue (CPM-nn)", w)
        self.assertIn("CPM-150, CPM-151", w)

    def test_warning_with_none(self):
        w = LL.pr_body_linear_warning("body", [])
        self.assertIn("none found today", w)

    def test_no_warning(self):
        self.assertIsNone(LL.pr_body_linear_warning("Relates to CPM-150", []))


if __name__ == "__main__":
    unittest.main()
