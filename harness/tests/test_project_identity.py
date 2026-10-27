"""Project identity comes from <project>/project.yaml, never from harness literals (TR-09).

- repo_paths._read_project_config: flat `key: value` lines with `#` comments, every key required, blank values allowed.
- No string literal in harness code (scripts, checks, lib, cad-lib; docstrings and comments excepted) holds one of
  this project's identity values (model ID, P&ID document ID, retired model ID, repos, customer), so a new project writes
  project.yaml and changes no harness file. Decision records quoting Bob ("Bob, chat") are history and stay.
Carry-over from an earlier job (its names, customer, records) is guarded repo-wide by test_no_carryover.py from the
job's own job/carryover-terms.txt. With no project yet the tests that read one are skipped.

    .\\harness\\tools\\venv\\Scripts\\python.exe -m unittest harness.tests.test_project_identity -v
"""
from __future__ import annotations

import ast
import re
import sys
import tempfile
import unittest
from pathlib import Path

REPO = next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists())
sys.path.insert(0, str(REPO / "harness" / "lib"))
import repo_paths as rp  # noqa: E402

CODE_DIRS = (rp.SCRIPTS, rp.CHECKS, rp.LIB, rp.CAD_LIB)
IDENTITY_KEYS = ("model_id", "pid_doc_id", "retired_model_id", "design_repo", "site_repo", "customer")


def _docstrings(tree: ast.AST) -> set[int]:
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                out.add(id(first.value))
    return out


class ReadProjectConfig(unittest.TestCase):
    def _write(self, text: str) -> Path:
        d = tempfile.mkdtemp()
        p = Path(d) / "project.yaml"
        p.write_text(text, encoding="utf-8")
        return p

    def test_parses_flat_keys_comments_and_blanks(self):
        lines = [f"{k}: v-{k}   # note" for k in rp.PROJECT_KEYS if k != "retired_model_id"]
        p = self._write("# header\n" + "\n".join(lines) + "\nretired_model_id:\ncustomer: \"A & B Co.\"\n")
        cfg = rp._read_project_config(p)
        self.assertEqual(cfg["model_id"], "v-model_id")
        self.assertEqual(cfg["retired_model_id"], "")
        self.assertEqual(cfg["customer"], "A & B Co.")

    def test_missing_key_or_file_refused(self):
        with self.assertRaises(RuntimeError):
            rp._read_project_config(self._write("model_id: X\n"))
        with self.assertRaises(RuntimeError):
            rp._read_project_config(Path(tempfile.mkdtemp()) / "project.yaml")

    @unittest.skipUnless(rp.HAS_PROJECT, "no project yet")
    def test_this_project_reads_its_file(self):
        self.assertEqual(rp.SKID_MODEL_ID, rp.PROJECT_INFO["model_id"])
        self.assertEqual(rp.SKID_FILED, rp.MODELS / rp.SKID_MODEL_ID)
        self.assertEqual(rp.PRESENTATION_SITE.name, rp.SITE_REPO.rsplit("/", 1)[-1])


@unittest.skipUnless(rp.HAS_PROJECT, "no project yet")
class NoIdentityLiterals(unittest.TestCase):
    def test_harness_code_reads_identity_from_repo_paths(self):
        # `unknown` is the repo's word for a value not received yet (CLAUDE.md hard rule 1), not an identity
        values = {k: rp.PROJECT_INFO[k] for k in IDENTITY_KEYS if rp.PROJECT_INFO[k] and rp.PROJECT_INFO[k].lower() != "unknown"}
        hits = []
        for d in CODE_DIRS:
            for f in sorted(d.glob("*.py")):
                if f.name == "repo_paths.py":
                    continue
                tree = ast.parse(f.read_text(encoding="utf-8"))
                docs = _docstrings(tree)
                for node in ast.walk(tree):
                    if not (isinstance(node, ast.Constant) and isinstance(node.value, str)) or id(node) in docs:
                        continue
                    if "Bob, chat" in node.value:   # a decision record quoting Bob: history, stays as written
                        continue
                    hits += [f"{rp.rel(f)}:{node.lineno} {k}={v!r}" for k, v in values.items()
                             if v.lower() in node.value.lower()]
        self.assertEqual(hits, [], "project identity literals in harness code; read them from repo_paths (<project>/project.yaml)")


if __name__ == "__main__":
    unittest.main()
