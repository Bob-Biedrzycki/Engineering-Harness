"""Tests for harness/scripts/run_checks.sh, the CI policy for harness/checks/.

Bob, chat, 2026-10-07: "The PR should not be flagging design findings." A design
finding (exit 1 with the "<name>: FAIL" summary) is a warning and the run exits 0;
a broken check (traceback, exit 1 without the summary, any other exit code) or a
HARD_FAIL_CHECKS (repo-integrity) failure exits 1.

Each case runs the real script against a temporary folder of stand-in checks, so no
repo file or pointer is touched. Needs bash: on Windows MinGit's usr/bin/sh.exe
beside git (never the WSL bash.exe); skipped when none is found.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists())
SCRIPT = REPO / "harness" / "scripts" / "run_checks.sh"


def _shell() -> tuple[str, dict] | None:
    env = dict(os.environ)
    if os.name == "nt":
        git = shutil.which("git")
        if not git:
            return None
        usr_bin = Path(git).resolve().parents[1] / "usr" / "bin"
        sh = usr_bin / "sh.exe"
        if not sh.is_file():
            return None
        env["PATH"] = str(usr_bin) + os.pathsep + env.get("PATH", "")
        return str(sh), env
    bash = shutil.which("bash")
    return (bash, env) if bash else None


SHELL = _shell()

FINDING = "import sys\nprint('{n}: FAIL - 3 findings')\nprint('  detail')\nsys.exit(1)\n"


@unittest.skipIf(SHELL is None, "no bash / MinGit sh.exe on this machine")
class RunChecksPolicy(unittest.TestCase):
    def run_with(self, checks: dict[str, str]) -> tuple[int, str, str]:
        sh, env = SHELL
        with tempfile.TemporaryDirectory() as d:
            for name, body in checks.items():
                (Path(d) / name).write_text(body, encoding="utf-8", newline="\n")
            summary = Path(d) / "summary.md"
            env = dict(env, PYTHON=Path(sys.executable).as_posix(), CHECKS_DIR=Path(d).as_posix(),
                       GITHUB_STEP_SUMMARY=summary.as_posix())
            r = subprocess.run([sh, SCRIPT.as_posix()], cwd=REPO, env=env, capture_output=True,
                               text=True, encoding="utf-8", errors="replace", timeout=120)
            return r.returncode, r.stdout, summary.read_text(encoding="utf-8") if summary.exists() else ""

    def test_design_findings_warn_and_pass(self):
        rc, out, summ = self.run_with({"sanitary.py": FINDING.format(n="sanitary"),
                                       "pipe_supports.py": FINDING.format(n="pipe_supports"),
                                       "ok.py": "print('ok: PASS - fine')\n"})
        self.assertEqual(rc, 0, out)
        self.assertIn("::warning file=", out)
        self.assertNotIn("::error", out)
        self.assertIn("| FINDINGS |", summ)

    def test_not_implemented_passes(self):
        rc, out, _ = self.run_with({"stub.py": "import sys\nprint('stub: NOT IMPLEMENTED - nothing')\nsys.exit(2)\n"})
        self.assertEqual(rc, 0, out)
        self.assertIn("::warning", out)

    def test_traceback_fails(self):
        rc, out, _ = self.run_with({"crash.py": "raise RuntimeError('simulated crash')\n"})
        self.assertEqual(rc, 1, out)
        self.assertIn("RuntimeError: simulated crash", out)

    def test_traceback_after_fail_summary_fails(self):
        rc, out, _ = self.run_with({"late.py": "print('late: FAIL - 1 finding')\nraise ValueError('x')\n"})
        self.assertEqual(rc, 1, out)

    def test_exit1_without_summary_fails(self):
        rc, out, _ = self.run_with({"silent.py": "import sys\nprint('oops')\nsys.exit(1)\n"})
        self.assertEqual(rc, 1, out)

    def test_error_exit3_fails(self):
        rc, out, _ = self.run_with({"nobuild.py": "import sys\nprint('nobuild: ERROR - model did not build')\nsys.exit(3)\n"})
        self.assertEqual(rc, 1, out)

    def test_drive_pointers_fail_is_hard(self):
        rc, out, summ = self.run_with({"drive_pointers.py": FINDING.format(n="drive_pointers")})
        self.assertEqual(rc, 1, out)
        self.assertIn("| FAIL |", summ)


class HardFailList(unittest.TestCase):
    def test_list_is_repo_integrity_only(self):
        line = next(ln for ln in SCRIPT.read_text(encoding="utf-8").splitlines() if ln.startswith("HARD_FAIL_CHECKS="))
        self.assertEqual(line.split("=", 1)[1].strip('"').split(), ["drive_pointers.py"])


if __name__ == "__main__":
    unittest.main()
