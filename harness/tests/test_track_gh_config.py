"""Unit tests for harness/scripts/track.py: the one gh config folder (GH_CONFIG_DIR) and the 'workflow' scope
preflight (Bob, 2026-10-06). Pure functions only: no gh, no git, no network. Stdlib unittest:

    .\\harness\\tools\\venv\\Scripts\\python.exe -m unittest discover -s harness\\tests -v
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path

REPO = next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists())
sys.path.insert(0, str(REPO / "harness" / "scripts"))
_saved = os.environ.get("GH_CONFIG_DIR")
import track as T  # noqa: E402  (importing sets GH_CONFIG_DIR in os.environ; restored in tearDownModule)


def tearDownModule() -> None:
    if _saved is None:
        os.environ.pop("GH_CONFIG_DIR", None)
    else:
        os.environ["GH_CONFIG_DIR"] = _saved


def status_json(*accounts: dict) -> str:
    """The shape `gh auth status --hostname github.com --json hosts` prints (token fields never appear)."""
    return json.dumps({"hosts": {"github.com": [
        {"active": a.get("active", True), "gitProtocol": "https", "host": "github.com", "login": a["login"],
         "scopes": a.get("scopes", ""), "state": a.get("state", "success"), "tokenSource": "keyring"}
        for a in accounts]}})


class GhConfigEnv(unittest.TestCase):
    def test_sets_folder_when_unset(self):
        env = {"PATH": "x"}
        self.assertEqual(T.apply_gh_config(env), str(T.GH_CONFIG_DIR))
        self.assertEqual(env["GH_CONFIG_DIR"], str(T.GH_CONFIG_DIR))
        self.assertEqual(env["PATH"], "x")

    def test_empty_counts_as_unset(self):
        env = {"GH_CONFIG_DIR": ""}
        self.assertEqual(T.apply_gh_config(env), str(T.GH_CONFIG_DIR))

    def test_keeps_caller_setting(self):
        env = {"GH_CONFIG_DIR": "D:/elsewhere/gh"}
        self.assertEqual(T.apply_gh_config(env), "D:/elsewhere/gh")
        self.assertEqual(env["GH_CONFIG_DIR"], "D:/elsewhere/gh")

    def test_folder_is_outside_appdata(self):
        self.assertEqual(T.GH_CONFIG_DIR, Path.home() / ".config" / "gh")
        self.assertNotIn("appdata", str(T.GH_CONFIG_DIR).lower())

    def test_import_exports_to_subprocess_env(self):
        # Another test module (test_track_daily) imports track first and restores os.environ in its
        # tearDownModule, so on CI (no GH_CONFIG_DIR in the runner) the import-time export is gone by the
        # time this runs. Re-applying is idempotent and tests the behaviour, not the module order.
        in_use = T.apply_gh_config(os.environ)
        self.assertTrue(os.environ.get("GH_CONFIG_DIR"))
        self.assertEqual(in_use, os.environ["GH_CONFIG_DIR"])
        self.assertTrue(T.GH_CONFIG_IN_USE)

    def test_signin_script_names_same_folder_and_scope(self):
        ps1 = (REPO / "harness" / "scripts" / "gh_signin.ps1").read_text(encoding="utf-8")
        self.assertIn("Join-Path $HOME '.config\\gh'", ps1)
        self.assertIn("--scopes workflow", ps1)
        self.assertIn("gh_signin.ps1", T.SIGNIN_CMD)
        self.assertTrue(ps1.isascii(), "PowerShell 5.1 reads a BOM-less script as ANSI; keep it ASCII")

    def test_signin_script_persists_folder_for_every_window(self):
        # Bob, 2026-10-07: a bare gh in his own window still said "not logged in" until the variable was persisted
        ps1 = (REPO / "harness" / "scripts" / "gh_signin.ps1").read_text(encoding="utf-8")
        self.assertIn("SetEnvironmentVariable('GH_CONFIG_DIR', $dir, 'User')", ps1)
        self.assertIn("already signed in with the 'workflow' scope", ps1, "no browser round-trip when nothing is needed")
        # one identity for git too: the script, run in Bob's own window, makes gh git's helper for github.com
        self.assertIn("auth setup-git --hostname github.com", ps1)

    def test_signin_command_is_absolute(self):
        # a relative path failed from C:\Users\Bob on 2026-10-07
        self.assertIn(str(REPO / "harness" / "scripts" / "gh_signin.ps1"), T.SIGNIN_CMD)
        self.assertIn('"', T.SIGNIN_CMD)   # quoted: the repo path may hold spaces one day

    def test_one_writer_account(self):
        self.assertEqual(T.WRITER_ACCOUNT, "Bob-Biedrzycki")
        self.assertFalse(hasattr(T, "AGENT_ACCOUNT"), "the separate agent account path is retired (Bob, 2026-10-07)")
        self.assertFalse(hasattr(T, "AS_BOB"))
        self.assertIs(T.require_agent, T.require_writer)   # old name still resolves for callers

    def test_local_settings_agree_when_present(self):
        p = REPO / ".claude" / "settings.local.json"
        if not p.is_file():
            self.skipTest("no .claude/settings.local.json on this machine (CI)")
        env = json.loads(p.read_text(encoding="utf-8")).get("env", {})
        if "GH_CONFIG_DIR" not in env:
            self.fail(f"{p} env lacks GH_CONFIG_DIR = {T.GH_CONFIG_DIR}")
        self.assertEqual(Path(env["GH_CONFIG_DIR"]), T.GH_CONFIG_DIR)


class TouchesWorkflows(unittest.TestCase):
    def test_paths(self):
        yes = [".github/workflows/checks.yml", ".github\\workflows\\checks.yml", "./.github/workflows/x.yml",
               ".github/workflows", ".github/workflows/", ".github", ".GitHub/Workflows/a.yml", "."]
        no = [".github/labels.yml", ".github/pull_request_template.md", "harness/scripts/track.py",
              "github/workflows/x.yml", ".github/workflows-old/x.yml", ""]
        for p in yes:
            self.assertTrue(T.touches_workflows([p]), p)
        for p in no:
            self.assertFalse(T.touches_workflows([p]), p)
        self.assertTrue(T.touches_workflows(["README.md", ".github/workflows/checks.yml"]))
        self.assertFalse(T.touches_workflows([]))


class WorkflowScopePreflight(unittest.TestCase):
    WF = [".github/workflows/checks.yml"]

    def test_parse(self):
        accts = T.parse_auth_hosts(status_json({"login": "Bob-Biedrzycki", "scopes": "gist, read:org, repo, workflow"}))
        self.assertEqual(accts, [{"login": "Bob-Biedrzycki", "active": True, "state": "success",
                                  "scopes": ["gist", "read:org", "repo", "workflow"]}])
        self.assertEqual(T.parse_auth_hosts('{"hosts":{}}\n'), [])
        self.assertEqual(T.parse_auth_hosts(""), [])
        self.assertEqual(T.parse_auth_hosts("not json"), [])

    def test_no_workflow_change_never_refused(self):
        self.assertIsNone(T.workflow_scope_refusal(["harness/scripts/track.py"], [], None))

    def test_refused_when_not_signed_in(self):
        why = T.workflow_scope_refusal(self.WF, T.parse_auth_hosts('{"hosts":{}}'), None)
        self.assertIsNotNone(why)
        self.assertIn(T.SIGNIN_CMD, why)
        self.assertIn("no sign-in", why)
        self.assertEqual(len(why.splitlines()), 1)

    def test_refused_when_scope_missing(self):
        accts = T.parse_auth_hosts(status_json({"login": "Bob-Biedrzycki", "scopes": "gist, read:org, repo"}))
        why = T.workflow_scope_refusal(self.WF, accts, None)
        self.assertIn("gist, read:org, repo", why)
        self.assertIn(T.SIGNIN_CMD, why)

    def test_passes_with_scope(self):
        accts = T.parse_auth_hosts(status_json({"login": "Bob-Biedrzycki", "scopes": "repo, workflow"}))
        self.assertIsNone(T.workflow_scope_refusal(self.WF, accts, None))

    def test_refused_when_token_invalid(self):
        accts = T.parse_auth_hosts(status_json({"login": "Bob-Biedrzycki", "scopes": "repo, workflow", "state": "error"}))
        self.assertIsNotNone(T.workflow_scope_refusal(self.WF, accts, None))

    def test_checks_the_pushing_account(self):
        accts = T.parse_auth_hosts(status_json(
            {"login": "someone-else", "active": True, "scopes": "repo, workflow"},
            {"login": "Bob-Biedrzycki", "active": False, "scopes": "repo"}))
        # writes switch gh to the writer account, so its scopes are the ones that count
        self.assertIsNotNone(T.workflow_scope_refusal(self.WF, accts, T.WRITER_ACCOUNT))
        # want None: the active account pushes
        self.assertIsNone(T.workflow_scope_refusal(self.WF, accts, None))
        # writer account not held: falls back to the active one
        self.assertIsNone(T.workflow_scope_refusal(self.WF, accts[:1], T.WRITER_ACCOUNT))


class GlobalFlagsAfterSubcommand(unittest.TestCase):
    """`track.py sync-main --dry-run` was refused on 2026-10-07; both flag positions now parse the same."""

    def parser(self):
        import argparse
        ap = argparse.ArgumentParser()
        ap.add_argument("--dry-run", action="store_true")
        ap.add_argument("--as-bob", action="store_true")
        sub = ap.add_subparsers(dest="cmd", required=True)
        sub.add_parser("sync-main").add_argument("--bob-go")
        sub.add_parser("status")
        T.add_global_flags_to_subcommands(sub)
        return ap

    def test_flag_before_and_after(self):
        ap = self.parser()
        self.assertTrue(ap.parse_args(["--dry-run", "sync-main"]).dry_run)
        self.assertTrue(ap.parse_args(["sync-main", "--dry-run"]).dry_run)
        self.assertTrue(ap.parse_args(["sync-main", "--dry-run", "--bob-go", "x"]).dry_run)
        self.assertFalse(ap.parse_args(["sync-main"]).dry_run)
        self.assertFalse(ap.parse_args(["status"]).as_bob)
        self.assertTrue(ap.parse_args(["status", "--as-bob"]).as_bob)

    def test_global_value_survives_subcommand(self):
        # the subparser's suppressed default must not overwrite the global True
        self.assertTrue(self.parser().parse_args(["--as-bob", "status"]).as_bob)


class TreeAndLocalBlobs(unittest.TestCase):
    """sync-main's batch hashing (one ls-tree per ref, one hash-object for the local files) against this repo."""

    def test_matches_per_path_git(self):
        import subprocess
        have = subprocess.run(["git", "rev-parse", "--verify", "--quiet", "HEAD:CLAUDE.md"], cwd=T.REPO,
                              capture_output=True, text=True).returncode == 0
        if not have:
            self.skipTest("no commit holding CLAUDE.md yet (a new repo before its first daily commit)")
        tree = T.tree_blobs("HEAD")
        self.assertIn("CLAUDE.md", tree)
        want = subprocess.run(["git", "rev-parse", "HEAD:CLAUDE.md"], cwd=T.REPO, capture_output=True, text=True).stdout.strip()
        self.assertEqual(tree["CLAUDE.md"], want)
        local = T.local_blobs(["CLAUDE.md", "harness/scripts/track.py"])
        one = subprocess.run(["git", "hash-object", "--", "CLAUDE.md"], cwd=T.REPO, capture_output=True, text=True).stdout.strip()
        self.assertEqual(local["CLAUDE.md"], one)
        self.assertEqual(len(local), 2)
        self.assertEqual(T.local_blobs([]), {})


if __name__ == "__main__":
    unittest.main()
