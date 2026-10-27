"""track.py - the scrum master's GitHub tool for this repo, with Bob's rules built in.

Wraps the GitHub CLI (`gh`). Authentication is gh's own: Bob signs in once
with harness/scripts/gh_signin.ps1 (scopes include `workflow`), into the one gh
config folder GH_CONFIG_DIR below that every window and subprocess uses. The
sign-in is a one-time event: the token stays in the Windows keyring, and this
tool never asks for it again unless `status` shows it gone. This script never
reads, prints or stores a token. A push that changes .github/workflows/ is
refused up front when the sign-in lacks `workflow`.

Rules enforced (CLAUDE.md notice 2026-09-24; harness/knowledge/Todd Requirements.md
TR-09..TR-12):
  * Only the scrum master (project-manager) uses this tool.
  * No GitHub issues or milestones: Linear is the task board (TR-12; CLAUDE.md "GitHub keeps the code"). The
    issue, milestone and issue-comment commands were removed 2026-10-26 (CPME practice).
  * Pull requests: one per day, from branch daily/<YYYY-MM-DD> into main.
    Closing keywords ("Closes #7", "fixes #3", "please close #7" ...) are
    refused unless that issue is passed with --closes (a PR body once closed
    an undecided issue by accident).
  * Commits: explicit paths only, message from a file, made in a separate git
    worktree so the shared checkout is never switched (several sessions share it).
    No Drive-store file is ever added: .gitignore joins the paths when
    only its managed block changed, and a selected large file is refused unless
    its pointer exists and the committed .gitignore ignores it (2026-10-07).
  * Anything that writes to GitHub or pushes needs --bob-go "<Bob's words>".
    --dry-run prints what would happen and sends nothing.
  * Writes go out as Bob-Biedrzycki (WRITER_ACCOUNT). Bob, 2026-10-07: one
    account writes; a separate agent account never got access, and Bob
    approves and merges the daily PR himself (2026-09-29). This is the rule;
    `--as-bob` is accepted and ignored. Pushes use gh as the git credential
    helper for that command only, so they go out as the same account.

Run with the repo venv from the repo root:
    .\\harness\\tools\\venv\\Scripts\\python.exe harness\\scripts\\track.py status
    .\\harness\\tools\\venv\\Scripts\\python.exe harness\\scripts\\track.py daily-commit --date YYYY-MM-DD --paths-file P --message-file M [--tag DOC-revX ...] [--local] [--start REF] [--moves-file CSV] [--removes-file F] --bob-go "..."
    .\\harness\\tools\\venv\\Scripts\\python.exe harness\\scripts\\track.py daily-push --date YYYY-MM-DD --bob-go "..."
    .\\harness\\tools\\venv\\Scripts\\python.exe harness\\scripts\\track.py daily-pr --date YYYY-MM-DD --title T --body-file F [--closes N ...] [--base daily/YYYY-MM-DD] --bob-go "..."
    .\\harness\\tools\\venv\\Scripts\\python.exe harness\\scripts\\track.py pr-retarget --date YYYY-MM-DD --bob-go "..."
    .\\harness\\tools\\venv\\Scripts\\python.exe harness\\scripts\\track.py sync-main [--dry-run] --bob-go "..."   (after the PR merges)
--dry-run is accepted before or after the subcommand (it was refused after it until 2026-10-07).

The normal end of day is two commands and one go (Bob, 2026-10-07, verbatim: "THIS SHOULD BE 1 "GO" THEN MY MERGE.
THE SYNC SHOULD BE AUTOMATED." and "IF THE ORIGINAL PR WAS APPROVED, THE CONTENT HAS ALREADY BEEN APPROVED AND IT
SHOULD BE DONE."):
    track.py daily --date YYYY-MM-DD --paths-file P --message-file M --title T --body-file B [--tag DOC-revX ...] --bob-go "..." [--dry-run]
        saves the go verbatim to <project>/_work/daily/<date>-go.txt, runs closeout.py, then daily-commit and daily-pr with
        that go, and prints "PR: <url>" on its own line (for the app's PR monitor)
    track.py after-merge --date YYYY-MM-DD [--dry-run]
        after Bob merges: reads the go file, checks the day's PR merged, runs sync-main, then publish_site.py with the
        newest filed portal, quoting and landing revisions when its dry run shows a difference from the site; while
        the project has no presentation site (site_revs.site_dormant) it prints "no presentation site yet" and stops
        there, passing
The single commands stay as the fallback.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists()) / "harness" / "lib"))
import repo_paths as rp  # noqa: E402
import drive_rules  # noqa: E402  (Drive-store rules and .gitignore block markers; shared with drive_store.py, drive_pointers.py)
import linear_loops  # noqa: E402
import site_revs  # noqa: E402  (newest filed portal / quoting / landing revisions; shared with closeout.py step 9)

REPO = rp.REPO
VENV_PY = rp.TOOLS / "venv" / "Scripts" / "python.exe"   # the repo venv runs closeout.py and publish_site.py
BASE = "main"
WRITER_ACCOUNT = "Bob-Biedrzycki"  # the one account this tool writes as (Bob, 2026-10-07)
GH_FALLBACK = Path.home() / "AppData/Local/Microsoft/WinGet/Packages/GitHub.cli_Microsoft.Winget.Source_8wekyb3d8bbwe/bin/gh.exe"
# One gh config folder for every window (Bob, 2026-10-06). Shells run by the Claude desktop app (MSIX) see a
# virtualized %APPDATA%, so gh's default config there is a different file from the one Bob's own terminals read:
# a sign-in made in one window was invisible in the other. Every gh and git subprocess of this tool (and of
# publish_site.py and sync_labels.py, which import it) gets GH_CONFIG_DIR = this folder unless it is already set.
# The same folder is named in harness/scripts/gh_signin.ps1 and .claude/settings.local.json env (test-guarded).
GH_CONFIG_DIR = Path.home() / ".config" / "gh"
# Absolute path, so Bob can paste it into any window (2026-10-07: a relative path failed from C:\Users\Bob).
SIGNIN_CMD = f'powershell -ExecutionPolicy Bypass -File "{REPO / "harness" / "scripts" / "gh_signin.ps1"}"'
WORKFLOWS_DIR = ".github/workflows"   # GitHub refuses pushes changing these without the gh 'workflow' scope
CLOSING = re.compile(r"\b(close[sd]?|fix(?:e[sd])?|resolve[sd]?)\b[\s:]*((?:[\w.-]+/[\w.-]+)?#\d+)", re.I)
TOKEN_LIKE = re.compile(r"(gh[opusr]_|github_pat_)[A-Za-z0-9_]{8,}")
DRY = False


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def die(msg: str) -> None:
    print(f"REFUSED: {msg}", file=sys.stderr)
    sys.exit(2)


def mask(s: str) -> str:
    return TOKEN_LIKE.sub(lambda m: m.group(1) + "***", s)


def apply_gh_config(environ) -> str:
    """Set GH_CONFIG_DIR in `environ` to GH_CONFIG_DIR unless already set (non-empty); return the folder in use."""
    if not environ.get("GH_CONFIG_DIR"):
        environ["GH_CONFIG_DIR"] = str(GH_CONFIG_DIR)
    return environ["GH_CONFIG_DIR"]


GH_CONFIG_IN_USE = apply_gh_config(os.environ)   # inherited by every gh and git subprocess from here on


def touches_workflows(paths) -> bool:
    """True if any repo-relative path is, contains or lies under .github/workflows/."""
    for p in paths:
        q = p.strip().replace("\\", "/").lower()
        while q.startswith("./"):
            q = q[2:]
        q = q.rstrip("/")
        if q in (".", ".github", WORKFLOWS_DIR) or q.startswith(WORKFLOWS_DIR + "/"):
            return True
    return False


def parse_auth_hosts(text: str) -> list[dict]:
    """Accounts from `gh auth status --json hosts` output: login, active, scopes (list), state. No token is in it."""
    try:
        hosts = json.loads(text or "{}").get("hosts") or {}
    except (ValueError, AttributeError):
        return []
    return [{"login": a.get("login", ""), "active": bool(a.get("active")), "state": a.get("state", ""),
             "scopes": [s.strip() for s in (a.get("scopes") or "").split(",") if s.strip()]}
            for a in hosts.get("github.com", []) or []]


def scope_account(accounts: list[dict], want: str | None) -> dict | None:
    """The account a push will use: `want` if gh holds it, else the active one."""
    return next((a for a in accounts if want and a["login"] == want), None) or \
        next((a for a in accounts if a["active"]), None)


def workflow_scope_refusal(paths, accounts: list[dict], want: str | None) -> str | None:
    """None if the push may go; else the one-line reason (paths touch .github/workflows/ and the account lacks 'workflow')."""
    if not touches_workflows(paths):
        return None
    acct = scope_account(accounts, want)
    if acct and acct["state"] == "success" and "workflow" in acct["scopes"]:
        return None
    state = (f"{acct['login']} has scopes {', '.join(acct['scopes']) or 'none'}" if acct else "no sign-in")
    return (f"this push changes {WORKFLOWS_DIR}/ and GitHub refuses that without the gh 'workflow' scope "
            f"(gh config {GH_CONFIG_IN_USE}: {state}). Bob runs once, in any PowerShell window:  {SIGNIN_CMD}")


def gh_exe() -> str:
    exe = shutil.which("gh") or (str(GH_FALLBACK) if GH_FALLBACK.exists() else None)
    if not exe:
        die("the GitHub CLI (gh) is not installed. Bob installs it: winget install --id GitHub.cli --scope user")
    return exe


def run(cmd: list[str], *, cwd: Path | None = None, write: bool = False, check: bool = True) -> str:
    shown = " ".join(f'"{c}"' if " " in c else c for c in cmd)
    if write and DRY:
        print(f"DRY-RUN would run: {shown}")
        return ""
    r = subprocess.run(cmd, cwd=cwd or REPO, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check and r.returncode != 0:
        die(f"command failed ({r.returncode}): {shown}\n{mask(r.stdout)}\n{mask(r.stderr)}")
    return mask(r.stdout)


def gh(*args: str, write: bool = False, check: bool = True) -> str:
    return run([gh_exe(), *args], write=write, check=check)


def git(*args: str, cwd: Path | None = None, write: bool = False, check: bool = True) -> str:
    return run(["git", *args], cwd=cwd, write=write, check=check)


def repo_slug() -> str:
    url = git("remote", "get-url", "origin").strip()
    m = re.search(r"github\.com[/:]([^/]+)/([^/]+?)(?:\.git)?$", url)
    if not m:
        die(f"origin is not a GitHub repo: {url}")
    slug = f"{m.group(1)}/{m.group(2)}"
    # origin may carry a pre-move URL (a renamed or transferred repo redirects); ask GitHub for the current name.
    return gh("api", f"repos/{slug}", "--jq", ".full_name", check=False).strip() or slug


def require_auth() -> None:
    r = subprocess.run([gh_exe(), "auth", "status", "--hostname", "github.com"], capture_output=True, text=True)
    if r.returncode != 0:
        die(f"gh is not signed in (gh config {GH_CONFIG_IN_USE}). Bob runs once, in any PowerShell window:  "
            f"{SIGNIN_CMD}   (agents never sign in or handle tokens)")


def gh_accounts() -> tuple[list[str], str | None]:
    """Accounts gh holds for github.com, and the active one. Reads names only, never tokens."""
    r = subprocess.run([gh_exe(), "auth", "status", "--hostname", "github.com"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    names, active, last = [], None, None
    for line in (r.stdout + r.stderr).splitlines():
        m = re.search(r"Logged in to github\.com account (\S+)", line)
        if m:
            last = m.group(1)
            names.append(last)
        elif last and re.search(r"Active account:\s*true", line):
            active = last
    return names, active


def gh_auth_hosts() -> list[dict]:
    """Accounts gh holds for github.com in GH_CONFIG_IN_USE: login, active, scopes, state. Never reads a token."""
    r = subprocess.run([gh_exe(), "auth", "status", "--hostname", "github.com", "--json", "hosts"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return parse_auth_hosts(r.stdout)


def unpushed_paths(branch: str) -> list[str]:
    """Paths changed by the commits on local `branch` that origin does not have yet (from origin/<branch> if it
    exists, else from origin/main), as last fetched."""
    if not git("branch", "--list", branch).strip():
        return []
    remote = f"refs/remotes/origin/{branch}"
    base = remote if git("rev-parse", "--verify", "--quiet", remote, check=False).strip() else f"origin/{BASE}"
    out = git("log", "--name-only", "--format=", f"{base}..{branch}", check=False)
    return sorted({ln.strip() for ln in out.splitlines() if ln.strip()})


def changed_workflow_paths(paths: list[str], branch: str, start: str | None = None) -> list[str]:
    """Workflow files a daily-commit of `paths` would change: listed paths that cover .github/workflows/ and whose
    working-tree copy differs from what the day's branch builds on (or is new there)."""
    if not touches_workflows(paths):
        return []
    base = next((r for r in (branch, f"refs/remotes/origin/{branch}", start, f"origin/{BASE}")
                 if r and git("rev-parse", "--verify", "--quiet", r, check=False).strip()), None)
    covered = lambda f: touches_workflows([f]) and any(  # noqa: E731
        f == p or f.startswith(p.rstrip("/") + "/") for p in (x.replace("\\", "/").removeprefix("./") for x in paths))
    if not base:
        return [p for p in paths if touches_workflows([p])]   # nothing to compare with: assume they change
    diff = git("diff", "--name-only", base, "--", WORKFLOWS_DIR, check=False).splitlines()
    new = git("ls-files", "--others", "--exclude-standard", "--", WORKFLOWS_DIR, check=False).splitlines()
    return [f for f in sorted(set(diff + new)) if covered(f)]


def require_workflow_scope(paths) -> None:
    """Refuse before a push GitHub would reject: changes under .github/workflows/ need the gh 'workflow' scope."""
    if not touches_workflows(paths):
        return
    why = workflow_scope_refusal(paths, gh_auth_hosts(), WRITER_ACCOUNT)
    if why:
        die(why)
    print(f"push changes {WORKFLOWS_DIR}/: gh 'workflow' scope present")


def require_writer() -> None:
    """Make gh act as WRITER_ACCOUNT (Bob-Biedrzycki) for this run, or refuse with the one sign-in command.

    Bob, 2026-10-07: a separate agent account never got access; writes go out as Bob, and a per-run flag
    for that was forgotten and refused (2026-10-06).
    Bob approves and merges the daily PR himself (2026-09-29). One account, no flag, no switching back.
    """
    require_auth()
    names, active = gh_accounts()
    if WRITER_ACCOUNT not in names:
        die(f"gh is signed in as {', '.join(names) or 'nobody'}, not {WRITER_ACCOUNT} (gh config {GH_CONFIG_IN_USE}). "
            f"Bob runs once, in any PowerShell window:  {SIGNIN_CMD}")
    if active != WRITER_ACCOUNT and not DRY:
        run([gh_exe(), "auth", "switch", "--hostname", "github.com", "--user", WRITER_ACCOUNT])
    who = gh("api", "user", "--jq", ".login", check=False).strip() if not DRY else WRITER_ACCOUNT
    if who != WRITER_ACCOUNT:
        die(f"gh is acting as {who or 'unknown'}, not {WRITER_ACCOUNT}")


require_agent = require_writer   # old name, kept for callers (publish_site.py) and transcripts


def git_remote(*args: str, cwd: Path | None = None, write: bool = False) -> str:
    """git fetch/push/ls-remote with gh's active account (WRITER_ACCOUNT) as the credential, not Git Credential Manager."""
    helper = "!" + gh_exe().replace("\\", "/") + " auth git-credential"
    return git("-c", "credential.https://github.com.helper=", "-c", f"credential.https://github.com.helper={helper}",
               *args, cwd=cwd, write=write)


def require_go(go: str | None, what: str) -> str:
    if not go or not go.strip():
        die(f"{what} needs Bob's go, quoted verbatim with --bob-go \"...\". Name it to Bob in chat first.")
    return go.strip()


def check_date(d: str) -> str:
    try:
        dt.date.fromisoformat(d)
    except ValueError:
        die(f"--date must be YYYY-MM-DD, got {d!r}")
    return d


def read_text(p: str) -> str:
    path = Path(p)
    if not path.is_file():
        die(f"file not found: {p}")
    return path.read_text(encoding="utf-8-sig")  # PowerShell writes a BOM; strip it


# --------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------
def cmd_status(a) -> None:
    slug = repo_slug()
    print(f"repo: {slug}")
    print(f"gh: {gh_exe()}")
    print(f"gh config: {GH_CONFIG_IN_USE}"
          + ("" if Path(GH_CONFIG_IN_USE) == GH_CONFIG_DIR else f" (GH_CONFIG_DIR set by the caller; default {GH_CONFIG_DIR})"))
    r = subprocess.run([gh_exe(), "auth", "status", "--hostname", "github.com"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    print("auth:", "signed in" if r.returncode == 0 else f"NOT signed in - Bob runs once, in any PowerShell window:  {SIGNIN_CMD}")
    for line in mask(r.stdout + r.stderr).splitlines():
        if "account" in line.lower() or "logged in" in line.lower():
            print("  " + line.strip())
    acct = scope_account(gh_auth_hosts(), WRITER_ACCOUNT)
    has_wf = bool(acct and "workflow" in acct["scopes"])
    print(f"workflow scope ({acct['login'] if acct else 'no account'}): "
          + ("present" if has_wf else f"MISSING - pushes that change {WORKFLOWS_DIR}/ are refused until Bob runs:  {SIGNIN_CMD}"))
    if r.returncode != 0:
        return
    names, active = gh_accounts()
    print(f"writer account {WRITER_ACCOUNT}: "
          + ("ready" + ("" if active == WRITER_ACCOUNT else " (writes switch gh to it)") if WRITER_ACCOUNT in names else
             f"NOT signed in (gh holds {', '.join(names) or 'nobody'}) - writes are refused until Bob runs:  {SIGNIN_CMD}"))
    persisted = os.environ.get("GH_CONFIG_DIR") and Path(os.environ["GH_CONFIG_DIR"]) == GH_CONFIG_DIR
    print(f"GH_CONFIG_DIR in this shell's environment: {'yes' if persisted else 'NO - gh_signin.ps1 persists it for new windows'}")
    # TR-10: is the repo under an organization, and which organizations can the signed-in account see?
    info = gh("repo", "view", slug, "--json", "nameWithOwner,isInOrganization,visibility", check=False)
    try:
        j = json.loads(info or "{}")
        print(f"TR-10: repo {j.get('nameWithOwner', slug)} is "
              f"{'in an organization' if j.get('isInOrganization') else 'under a personal account (Bob, chat, 2026-10-19)'}"
              f" ({j.get('visibility', '?')})")
    except json.JSONDecodeError:
        print("TR-10: could not read repo owner type")
    orgs = gh("api", "user/orgs", "--jq", ".[].login", check=False).split()
    print(f"organizations visible to this sign-in: {', '.join(orgs) if orgs else '(none, or the token lacks read:org)'}")
    print("tasks: Linear (TR-12); this tool opens no GitHub issue or milestone")
    print(f"current branch of the shared checkout: {git('branch', '--show-current').strip()} (never switched by this tool)")


COMMIT_SECTIONS = ("Why", "Changed IDs", "Sources and rules cited", "TR rows touched", "Drawings filed", "Checks run")
# Placeholders of the close-out skeleton (closeout.py step 8): a message still holding one was never filled in.
SKELETON_MARKS = ("<fill:", "<area>:", "<what changed")


def commit_inputs(a, check_exist: bool = True) -> tuple[list[str], str]:
    """The paths and message of a daily commit, refused on any TR-11 rule. One copy of the rules, used by
    daily-commit and, before close-out runs, by daily (check_exist=False there: close-out has not filed yet)."""
    paths = [ln.strip() for ln in read_text(a.paths_file).splitlines() if ln.strip() and not ln.startswith("#")]
    if not paths:
        die("the paths file lists no paths")
    for pth in paths:
        if pth in (".", "*") or "*" in pth:
            die(f"explicit paths only, no wildcards: {pth!r}")
        if check_exist and not (REPO / pth).exists():
            die(f"path does not exist in the working tree: {pth}")
    msg = read_text(a.message_file)
    for sect in COMMIT_SECTIONS:
        if sect.lower() not in msg.lower():
            die(f"commit message is missing the '{sect}' section (CLAUDE.md, TR-11)")
    if len(msg.splitlines()[0]) > 72:
        die("commit subject line is longer than 72 characters")
    if CLOSING.search(msg):
        die("commit messages must not contain closing keywords")
    left = [m for m in SKELETON_MARKS if m in msg]
    if left:
        die(f"commit message still holds close-out skeleton placeholder(s) {', '.join(left)}; fill them in (TR-11)")
    for t in a.tag:
        if not re.fullmatch(r"[\w.-]+-rev[A-Z]+", t):
            die(f"tag {t!r} is not <DOC-ID>-rev<X>")
    return paths, msg


# --------------------------------------------------------------------------
# the Drive store in the daily commit. 2026-10-07: the paths file named
# a portal folder; close-out filed a portal revision and drive_store.py put its 10.2 MB turntable.mp4 in the managed
# .gitignore block, but .gitignore was not listed, so the worktree kept the branch's copy and `git add` of the
# folder took the large file with its pointer. Two guards: .gitignore joins the paths when only its managed block
# changed, and no file the Drive-store rules select reaches `git add` unless its pointer exists and the committed
# .gitignore ignores it.
# --------------------------------------------------------------------------
def norm_rel(p: str) -> str:
    q = p.strip().replace("\\", "/")
    while q.startswith("./"):
        q = q[2:]
    return q.rstrip("/")


def covered_by(rel: str, paths: list[str]) -> bool:
    """True if a listed path is `rel` or a folder holding it."""
    return any(rel == p or rel.startswith(p + "/") for p in (norm_rel(x) for x in paths))


def drive_cfg() -> dict:
    try:
        return drive_rules.load(rp.DRIVE_STORE_CONFIG)
    except (OSError, KeyError) as e:
        die(f"cannot read the Drive-store rules {rp.rel(rp.DRIVE_STORE_CONFIG)} ({type(e).__name__}: {e})")


def base_text(ref: str, rel: str) -> str:
    """The text of `rel` in commit `ref`, or "" when it has none."""
    return git("show", f"{ref}:{rel}", check=False)


def gitignore_autoadd(paths: list[str], base_ref: str) -> list[str]:
    """`paths` plus .gitignore when the shared checkout's copy differs from `base_ref`'s only inside the drive-store
    managed block (drive_store.py pointers wrote it). A change outside the block is somebody's edit: warned, not
    added; the Drive-store guard below then refuses any large file that copy would have kept out."""
    if any(norm_rel(p) == ".gitignore" for p in paths):
        return paths
    gi = REPO / ".gitignore"
    if not gi.is_file():
        return paths
    kind = drive_rules.gitignore_change(base_text(base_ref, ".gitignore"), gi.read_text(encoding="utf-8-sig"))
    if kind == "block":
        print(f"paths: added .gitignore (its drive-store block differs from {base_ref}; written by drive_store.py)",
              flush=True)
        return paths + [".gitignore"]
    if kind == "outside":
        print(f"WARNING: .gitignore differs from {base_ref} outside the drive-store block too; not added "
              f"automatically. List it in the paths file if those changes belong in this commit", flush=True)
    return paths


def expand_paths(paths: list[str], cfg: dict) -> list[tuple[str, int]]:
    """(repo-relative file, bytes) for every file the listed paths name in the shared checkout, folders walked.
    Skips .git and the Drive store's excluded folders (gitignored working copies)."""
    out: list[tuple[str, int]] = []
    for p in (norm_rel(x) for x in paths):
        src = REPO / p
        if src.is_file():
            out.append((p, src.stat().st_size))
        elif src.is_dir():
            for root, dirs, files in os.walk(src):
                rel_root = Path(root).relative_to(REPO).as_posix()
                dirs[:] = sorted(d for d in dirs if d != ".git" and not drive_rules.excluded(f"{rel_root}/{d}", cfg))
                out += [(f"{rel_root}/{f}", os.path.getsize(Path(root) / f)) for f in sorted(files)]
    return sorted(set(out))


def ignored_by(gitignores: dict[str, str], rels: list[str]) -> set[str]:
    """Which of `rels` the given .gitignore files ({repo-relative .gitignore path: text}) ignore, asked of git itself
    in a scratch repository (no global excludes, no info/exclude entries), so the answer is what a fresh checkout of
    the commit would do."""
    if not rels:
        return set()
    with tempfile.TemporaryDirectory(prefix="track-ignore-") as d:
        root = Path(d)
        r = subprocess.run(["git", "init", "-q", str(root)], capture_output=True, text=True)
        if r.returncode != 0:
            die(f"git init of a scratch repository failed: {r.stderr.strip()}")
        for rel, text in gitignores.items():
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_text(text, encoding="utf-8", newline="\n")
        for rel in rels:   # empty stand-ins, so directory patterns see their directories
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).touch()
        no_global = root / ".git" / "no-global-excludes"
        no_global.write_text("", encoding="utf-8")
        r = subprocess.run(["git", "-c", f"core.excludesFile={no_global.as_posix()}", "check-ignore", "--no-index",
                            "--stdin", "-z"], cwd=root, input="\0".join(rels) + "\0", capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
        if r.returncode not in (0, 1):   # 1 = none ignored
            die(f"git check-ignore failed ({r.returncode}): {r.stderr.strip()}")
        return {p for p in r.stdout.split("\0") if p}


def drive_store_plan(paths: list[str], base_ref: str, removes: list[str]) -> tuple[list[str], set[str]]:
    """(pathspecs for `git add`, files kept out of the worktree copy). Refuses any file under the listed paths that
    the Drive-store rules select unless its pointer exists, the .gitignore this commit carries ignores it, and the
    base does not still track it (or --removes-file untracks it). A selected file listed by name is replaced by its
    pointer. Same rules as harness/checks/drive_pointers.py (CI) and drive_store.py (harness/lib/drive_rules.py)."""
    cfg = drive_cfg()
    files = expand_paths(paths, cfg)
    selected = [(rel, size, rule) for rel, size in files if (rule := drive_rules.rule_for(rel, size, cfg))]
    if not selected:
        return list(dict.fromkeys(norm_rel(p) for p in paths)), set()
    in_base = tree_blobs(base_ref)
    commit_gi = {}   # every .gitignore as this commit will hold it: the listed copy, else the base's
    for gi in sorted({f for f in in_base if f == ".gitignore" or f.endswith("/.gitignore")}
                     | {rel for rel, _ in files if rel.rsplit("/", 1)[-1] == ".gitignore"}):
        commit_gi[gi] = ((REPO / gi).read_text(encoding="utf-8-sig") if covered_by(gi, paths) and (REPO / gi).is_file()
                         else base_text(base_ref, gi))
    ignored = ignored_by(commit_gi, [rel for rel, _, _ in selected])
    untracked = {norm_rel(r) for r in removes}
    problems = []
    for rel, size, rule in selected:
        ptr = drive_rules.pointer_rel(rel)
        why = []
        if not (REPO / ptr).is_file():
            why.append("no pointer (run harness/scripts/drive_store.py pointers)")
        if rel not in ignored:
            why.append("not ignored by the .gitignore this commit carries (list .gitignore after drive_store.py pointers)")
        if rel in in_base and rel not in untracked:
            why.append(f"still tracked on {base_ref} (list it in --removes-file)")
        if why:
            problems.append(f"{rel} ({size:,} B, rule {rule}): {'; '.join(why)}. List its pointer instead: {ptr}")
    if problems:
        die(f"{len(problems)} file(s) under the listed paths belong in the Google Drive store (CI "
            f"drive_pointers fails on a tracked one) and would be committed:\n  " + "\n  ".join(problems[:40])
            + ("\n  ..." if len(problems) > 40 else ""))
    keep_out = {rel for rel, _, _ in selected}
    specs = []
    for p in (norm_rel(x) for x in paths):
        if p in keep_out:
            ptr = drive_rules.pointer_rel(p)
            if not covered_by(ptr, paths):
                specs.append(ptr)
            print(f"paths: {p} is in the Drive store; committing its pointer {ptr} instead", flush=True)
        else:
            specs.append(p)
    print(f"Drive store: {len(keep_out)} file(s) under the listed paths stay out of the commit (pointer committed, "
          f"file ignored)", flush=True)
    for rel in sorted(keep_out)[:10]:
        print(f"  {rel}", flush=True)
    return list(dict.fromkeys(specs)), keep_out


def cmd_daily_commit(a) -> None:
    go = require_go(a.bob_go, "committing and pushing the day's work")
    date = check_date(a.date)
    branch = f"daily/{date}"
    paths, msg = commit_inputs(a)

    # --local: commit and tag on the local daily branch only, no GitHub, no sign-in needed. daily-push sends it later.
    if not a.local:
        # the push carries the new commit (these paths) and any earlier local commits origin lacks
        require_workflow_scope(changed_workflow_paths(paths, branch, a.start) + unpushed_paths(branch))
        require_writer()
        git_remote("fetch", "origin", write=True)
    wt = REPO.parent / f"{REPO.name}-daily-{date}"
    if wt.exists():
        die(f"worktree folder already exists: {wt} (finish or remove the previous run first)")
    local_has = bool(git("branch", "--list", branch).strip())
    if a.local:
        remote_has = bool(git("rev-parse", "--verify", "--quiet", f"refs/remotes/origin/{branch}", check=False).strip())
    else:
        remote_has = bool(git_remote("ls-remote", "--heads", "origin", branch).strip())
    if local_has:
        # Build on the local branch; never reset it (earlier local commits would be lost).
        if remote_has and not a.local and subprocess.run(
                ["git", "merge-base", "--is-ancestor", f"origin/{branch}", branch], cwd=REPO).returncode != 0:
            die(f"local {branch} does not contain origin/{branch}; reconcile by hand with Bob before committing")
        base_ref = branch
    else:
        if a.start and remote_has:
            die(f"--start given but origin/{branch} already exists; the branch must build on origin/{branch}")
        # --start: stack the day's branch on another (e.g. an unmerged daily branch; Bob, 2026-09-25).
        base_ref = a.start or (f"origin/{branch}" if remote_has else f"origin/{BASE}")
        git("rev-parse", "--verify", "--quiet", base_ref)
    # Drive store, before any worktree exists: .gitignore joins the paths when only its managed block
    # changed, and a selected large file is refused unless its pointer goes in its place (2026-10-07).
    removes = ([ln.strip() for ln in read_text(a.removes_file).splitlines() if ln.strip() and not ln.startswith("#")]
               if a.removes_file else [])
    paths = gitignore_autoadd(paths, base_ref)
    pathspecs, keep_out = drive_store_plan(paths, base_ref, removes)
    if local_has:
        git("worktree", "add", str(wt), branch, write=True)
    else:
        git("worktree", "add", "-b", branch, str(wt), base_ref, write=True)

    def leave_out(dirpath: str, names: list[str]) -> list[str]:
        """copytree filter: Drive-store files never enter the worktree (their pointers do)."""
        rel_dir = Path(dirpath).relative_to(REPO).as_posix()
        return [n for n in names if f"{rel_dir}/{n}" in keep_out]
    try:
        if a.moves_file:
            # Record moves as renames: git mv each tracked old_path before the listed paths are copied in.
            import csv
            with open(a.moves_file, newline="", encoding="utf-8-sig") as fh:
                rows = [(r["old_path"].strip(), r["new_path"].strip()) for r in csv.DictReader(fh)]
            tracked = set(git("ls-files", cwd=wt if not DRY else REPO).splitlines())
            moved = 0
            for old, new in rows:
                if old not in tracked:
                    continue
                if not DRY:
                    (wt / new).parent.mkdir(parents=True, exist_ok=True)
                git("mv", old, new, cwd=wt, write=True)
                moved += 1
            print(f"recorded {moved} tracked move(s) from {a.moves_file}")
        if a.removes_file:
            # Record removals from the index (e.g. a large file moved to the Drive store). The
            # working tree keeps the file; only its tracking ends. Each path must be tracked.
            tracked = set(git("ls-files", cwd=wt if not DRY else REPO).splitlines())
            for old in removes:
                if old not in tracked:
                    die(f"--removes-file: not a tracked path: {old}")
                git("rm", "--cached", "--quiet", "--", old, cwd=wt, write=True)
            print(f"recorded {len(removes)} removal(s) from the index from {a.removes_file}")
        if not DRY:
            for pth in pathspecs:
                src, dst = REPO / pth, wt / pth
                if src.is_dir():
                    shutil.copytree(src, dst, dirs_exist_ok=True, ignore=leave_out)
                else:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
        # Pathspecs from a file: a day's explicit paths can exceed the Windows command-line limit.
        spec = wt / ".git-daily-paths"
        if not DRY:
            spec.write_text("\n".join(pathspecs) + "\n", encoding="utf-8")
        git("add", f"--pathspec-from-file={spec}", "--", cwd=wt, write=True)
        if not DRY:
            spec.unlink()
        # Commit from a BOM-free copy: PowerShell's Set-Content -Encoding utf8 writes a BOM that git keeps in the subject.
        msg_file = wt / ".git-daily-msg"
        if not DRY:
            msg_file.write_text(msg, encoding="utf-8")
        git("commit", "-F", str(msg_file), cwd=wt, write=True)
        if not DRY:
            msg_file.unlink()
        for t in a.tag:
            git("tag", "-a", t, "-m", f"{t} filed (TR-08)", cwd=wt, write=True)
        tags = f", tags {', '.join(a.tag)}" if a.tag else ""
        if a.local:
            print(f"committed {len(paths)} path(s) to local {branch}{tags}. Not pushed: run daily-push on Bob's go")
        else:
            git_remote("push", "origin", branch, cwd=wt, write=True)
            for t in a.tag:
                git_remote("push", "origin", f"refs/tags/{t}", cwd=wt, write=True)
            print(f"{'DRY-RUN: would have ' if DRY else ''}committed and pushed {len(paths)} path(s) to {branch}{tags}")
    finally:
        git("worktree", "remove", "--force", str(wt), write=True, check=False)


INIT_MAIN_MSG = """repo: empty first commit, the base for the first daily PR

**Why**
A new job repo has no commits and GitHub has no `main`, so the day's branch has nothing to build on and
the daily PR has no base. This commit holds no files: it only creates `main`, so the first day's work goes
through the normal daily branch and one PR that Bob reviews and merges (TR-11, one PR a day).

**Changed IDs**
none

**Sources and rules cited**
CLAUDE.md "Commits" and "Work cycle" step 6; harness/scripts/track.py init-main.

**TR rows touched**
TR-11 (documented commit), TR-12 (daily PR flow unchanged).

**Drawings filed**
none

**Checks run**
none (no files)

Bob's go: "{go}"
"""


def cmd_init_main(a) -> None:
    """Only for a brand-new job repo: create `main` on GitHub as one EMPTY commit (no files), so daily-commit can
    build the day's branch on origin/main and daily-pr has a base. Refuses when origin already has any branch or
    the local main already has a commit. Nothing in the working tree changes: the local `main` ref is set to the
    same empty commit, so every file stays as it was (untracked until the first daily PR merges and sync-main runs).
    """
    go = require_go(a.bob_go, "creating main as the repo's first, empty commit")
    require_writer()
    heads = git_remote("ls-remote", "--heads", "origin").strip()
    if heads:
        die("origin already has branches; init-main is only for an empty repo. Use daily-commit.\n" + heads)
    if git("rev-parse", "--verify", "--quiet", f"refs/heads/{BASE}", check=False).strip():
        die(f"local {BASE} already has a commit; init-main is only for a repo with no commits")
    r = subprocess.run(["git", "mktree"], cwd=REPO, input="", capture_output=True, text=True)
    if r.returncode != 0:
        die(f"git mktree failed: {r.stderr.strip()}")
    tree = r.stdout.strip()
    # A new job may have no project folder yet (no rp.TRACKING), so the message goes through a temp file.
    with tempfile.TemporaryDirectory() as tmp:
        msg_file = Path(tmp) / "init-main-commit.md"
        msg_file.write_text(INIT_MAIN_MSG.replace("{go}", go), encoding="utf-8")
        commit = git("commit-tree", tree, "-F", str(msg_file), write=True).strip() or "<new-commit>"
    git_remote("push", "origin", f"{commit}:refs/heads/{BASE}", write=True)
    git("update-ref", f"refs/heads/{BASE}", commit, write=True)
    git_remote("fetch", "origin", write=True)
    print(f"{'DRY-RUN: would have ' if DRY else ''}created {BASE} on origin as one empty commit ({commit if DRY else commit[:7]}); "
          f"no file changed. Next: the day's daily-commit and daily-pr (Bob's go: \"{go}\")")


def cmd_daily_push(a) -> None:
    go = require_go(a.bob_go, "pushing the day's branch")
    date = check_date(a.date)
    branch = f"daily/{date}"
    if not git("branch", "--list", branch).strip():
        die(f"no local {branch}; run daily-commit first")
    require_workflow_scope(unpushed_paths(branch))
    require_writer()
    # --follow-tags sends the annotated drawing tags (<DOC-ID>-rev<X>) on the pushed commits.
    git_remote("push", "--follow-tags", "origin", branch, write=True)
    print(f"pushed {branch} with its tags. Next: daily-pr (Bob's go: \"{go}\")")


def linear_pr_note(body: str, date: str) -> None:
    """TR-12 (Bob, 2026-10-07): say whether the PR body names the day's Linear issues. A warning only:
    never refuses, never changes the exit code."""
    try:
        hand = linear_loops.read_handoffs(rp.DAILY, date)
        export = linear_loops.load_linear_export(linear_loops.export_path(rp.DAILY, date))
        warn = linear_loops.pr_body_linear_warning(body, linear_loops.day_ids(hand, export, date))
        print(warn or f"Linear issues named: {', '.join(linear_loops.cpm_refs(body))}", flush=True)
    except Exception as e:  # noqa: BLE001 - the note never blocks the PR
        print(f"WARNING: Linear issue check skipped ({type(e).__name__}: {e})", flush=True)


def pr_body(a) -> str:
    """The day's PR body, refused on a missing template section or a stray closing keyword. One copy of the rules,
    used by daily-pr and, before close-out runs, by daily."""
    body = read_text(a.body_file)
    for need in ("Todd's requirements", "Drawings filed"):
        if need.lower() not in body.lower():
            die(f"PR body is missing the '{need}' section (.github/pull_request_template.md)")
    allowed = {f"#{n}" for n in a.closes}
    for m in CLOSING.finditer(body):
        ref = "#" + m.group(2).split("#")[-1]
        if ref not in allowed:
            die(f"closing keyword '{m.group(0)}' would close {ref}. Rephrase (e.g. 'Relates to {ref}'), or pass "
                f"--closes {ref[1:]} only if the whole issue is satisfied")
    return body


def cmd_daily_pr(a) -> str:
    """Open the day's PR; returns its URL ("" in a dry run)."""
    go = require_go(a.bob_go, "opening the day's PR")
    date = check_date(a.date)
    branch = f"daily/{date}"
    body = pr_body(a)
    linear_pr_note(body, date)
    require_writer()
    slug = repo_slug()
    if not git_remote("ls-remote", "--heads", "origin", branch).strip() and not DRY:
        die(f"{branch} is not on origin; run daily-commit first")
    existing = json.loads(gh("pr", "list", "--repo", slug, "--head", branch, "--state", "all",
                             "--json", "number,state,url") or "[]")
    # One OPEN PR per day. Once the day's PR has merged, later work the same day may open another on Bob's
    # go (Bob, 2026-09-29: "go with 1"). A PR closed without merging is still refused: raise it with Bob.
    for pr in existing:
        if pr["state"] != "MERGED":
            die(f"{branch} already has a PR ({pr['url']}, {pr['state'].lower()}). One PR per day: push more "
                f"commits to it instead")
    if existing:
        print(f"{branch}: earlier PR(s) merged ({', '.join(p['url'] for p in existing)}); opening the next one")
    tmp = rp.TRACKING / f"pr-{date}.md"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(body.rstrip() + f"\n\n---\nOpened by the scrum master on Bob's go ({dt.date.today()}): \"{go}\"\n",
                   encoding="utf-8")
    extra = [x for r in a.reviewer for x in ("--reviewer", r)]
    base = a.base or BASE
    if base != BASE and not re.fullmatch(r"daily/\d{4}-\d{2}-\d{2}", base):
        die(f"--base must be {BASE} or an earlier daily/<date> branch (stacked PR), not {base!r}")
    url = gh("pr", "create", "--repo", slug, "--base", base, "--head", branch, "--title", a.title,
             "--body-file", str(tmp), *extra, write=True).strip()
    print(f"PR {url or '(dry run)'} - the engineer reviews and merges on GitHub. Never merge from here.")
    if base != BASE:
        print(f"Stacked on {base}. When that PR merges (merge commit, not squash), run pr-retarget --date {date}")
    return url


def tree_blobs(ref: str) -> dict[str, str]:
    """path -> blob hash for every file in `ref`, from one `git ls-tree -r -z` call."""
    out = {}
    for e in git("ls-tree", "-r", "-z", ref).split("\0"):
        if e:
            meta, path = e.split("\t", 1)
            out[path] = meta.split(" ")[2]
    return out


def local_blobs(paths: list[str]) -> dict[str, str]:
    """path -> blob hash of each working-tree file, from one `git hash-object --stdin-paths` call (same text
    filters as the index, like `git hash-object -- <path>`)."""
    if not paths:
        return {}
    r = subprocess.run(["git", "hash-object", "--stdin-paths"], cwd=REPO, input="\n".join(paths) + "\n",
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        die(f"git hash-object failed ({r.returncode}): {r.stderr.strip()}")
    hashes = r.stdout.split()
    if len(hashes) != len(paths):
        die(f"git hash-object returned {len(hashes)} hashes for {len(paths)} paths")
    return dict(zip(paths, hashes))


def cmd_sync_main(a) -> None:
    """After the day's PR has merged: move the shared checkout's `main` to origin/main without touching any file.

    Why (Bob, 2026-10-02, "an ongoing problem"): daily-commit works in a separate worktree so the shared checkout is
    never switched, which also means the checkout's `main` never moves. After the merge the same files sit there as
    untracked or modified copies, byte-identical to origin/main, and `git merge --ff-only` refuses to step over them.
    The checkout then reads stale rule files and reports three days of work as uncommitted (it happened 2026-09-29
    and twice on 2026-10-02). The fix is a MIXED reset: branch and index move, the working tree is not written.

    Safety: refuses unless every local difference is already in origin/main. Files that origin/main changed but the
    checkout never saw (edited only inside a worktree) are refreshed from origin/main only when the local copy still
    equals HEAD's version, so nothing anyone typed is lost. Any other difference is listed and the tool stops.
    """
    cur = git("branch", "--show-current").strip()
    if cur != BASE:
        die(f"the shared checkout is on {cur!r}, not {BASE}; never switch it (another session may own that branch)")
    # The fetch runs in --dry-run too: it writes no working-tree file, and a dry run against a stale origin/main
    # reported "already at origin/main" right after a merge it had not seen (2026-10-07).
    git_remote("fetch", "origin")
    head = git("rev-parse", "HEAD").strip()
    target = git("rev-parse", f"origin/{BASE}").strip()
    if head == target:
        print(f"{BASE} already at origin/{BASE} ({head[:7]}); nothing to do")
        return
    if subprocess.run(["git", "merge-base", "--is-ancestor", head, target], cwd=REPO).returncode != 0:
        die(f"local {BASE} ({head[:7]}) has commits origin/{BASE} ({target[:7]}) lacks; that never happens by design. "
            "Raise it with Bob; do not reset")

    # Three git calls hash everything (one ls-tree per ref, one hash-object for the local copies), instead of two
    # subprocesses per path: a 1,352-file day took five minutes on 2026-10-07.
    in_target, in_head = tree_blobs(f"origin/{BASE}"), tree_blobs(head)
    # 1. local changes relative to HEAD (modified, deleted, untracked): each must already be what origin/main holds
    local_changes = []
    raw = git("status", "--porcelain=v1", "-z", "--untracked-files=all")
    entries, i = raw.split("\0"), 0
    while i < len(entries):
        e = entries[i]
        i += 1
        if not e:
            continue
        code, path = e[:2], e[3:]
        if code[0] in "RC":
            i += 1  # the original name follows; the new path is what matters here
        local_changes.append(path)
    # 2. files origin/main changed since HEAD that the checkout never received (edited only in a worktree).
    #    `diff --name-status -z` alternates status and path (status, old, new for renames and copies).
    parts = [p for p in git("diff", "--name-status", "-z", head, target).split("\0") if p != ""]
    remote_changes, j = [], 0
    while j < len(parts):
        st = parts[j]
        if st[0] in "RC":
            remote_changes += [(parts[j + 1], "D"), (parts[j + 2], "A")]
            j += 3
        else:
            remote_changes.append((parts[j + 1], st[0]))
            j += 2
    local = local_blobs([p for p in sorted(set(local_changes) | {p for p, _ in remote_changes}) if (REPO / p).is_file()])

    problems, refresh, remove, keep_untracked = [], [], [], []
    for path in local_changes:
        if path in local:   # a file
            if path in in_target:
                if local[path] != in_target[path]:
                    problems.append(f"{path}: differs from origin/{BASE} (uncommitted work?)")
            else:
                keep_untracked.append(path)  # not in origin/main: another session's work in progress, left alone
        elif path in in_target:
            problems.append(f"{path}: missing locally but present in origin/{BASE}")
    for path, kind in remote_changes:
        if kind == "D":
            if path in local and path not in in_target:
                if local[path] == in_head.get(path):
                    remove.append(path)
                else:
                    problems.append(f"{path}: removed in origin/{BASE} but the local copy is not HEAD's version")
            continue
        if path not in local:
            refresh.append(path)  # absent locally; the reset makes it show as deleted unless restored
        elif local[path] == in_target.get(path):
            continue
        elif local[path] == in_head.get(path):
            refresh.append(path)
        else:
            problems.append(f"{path}: changed in origin/{BASE} and edited locally; resolve by hand")
    refresh = sorted(set(refresh))
    remove = sorted(set(remove))
    if problems:
        die(f"not safe to move {BASE} to origin/{BASE}; {len(problems)} path(s) hold work that is not in origin/{BASE}:\n  "
            + "\n  ".join(problems[:40]) + ("\n  ..." if len(problems) > 40 else ""))
    print(f"{BASE} {head[:7]} -> origin/{BASE} {target[:7]}: mixed reset (no file written), then refresh {len(refresh)} "
          f"file(s) from origin/{BASE}, remove {len(remove)} file(s) deleted there (local copies equal HEAD), leave "
          f"{len(keep_untracked)} untracked file(s) alone")
    for p in refresh[:20]:
        print(f"  refresh {p}")
    for p in remove[:20]:
        print(f"  remove  {p}")
    if DRY:
        print("DRY-RUN: nothing changed")
        return
    require_go(a.bob_go, f"moving the shared checkout's {BASE} to origin/{BASE} (a reset; agents never do it alone)")
    git("reset", "--mixed", f"origin/{BASE}", write=True)
    if refresh:
        git("checkout", "--", *refresh, write=True)
    for p in remove:
        (REPO / p).unlink()
    git("branch", f"--set-upstream-to=origin/{BASE}", BASE, write=True, check=False)
    left = [e[3:] for e in git("status", "--porcelain=v1", "-z", "--untracked-files=all").split("\0") if e and not e.startswith("??")]
    if left:
        die(f"after the reset {len(left)} tracked path(s) still differ; look before doing anything else:\n  " + "\n  ".join(left[:20]))
    print(f"{BASE} is at origin/{BASE} ({target[:7]}); tracked tree clean; {len(keep_untracked)} untracked file(s) untouched")


def cmd_pr_retarget(a) -> None:
    """Point a stacked daily PR at main once the PR it was stacked on has merged."""
    go = require_go(a.bob_go, "retargeting the day's PR")
    date = check_date(a.date)
    branch = f"daily/{date}"
    require_writer()
    slug = repo_slug()
    prs = json.loads(gh("pr", "list", "--repo", slug, "--head", branch, "--state", "open",
                        "--json", "number,baseRefName,url") or "[]")
    if not prs:
        die(f"no open PR from {branch}")
    pr = prs[0]
    if pr["baseRefName"] == BASE:
        print(f"{pr['url']} already targets {BASE}")
        return
    git_remote("fetch", "origin", write=True)
    old_base = pr["baseRefName"]
    if subprocess.run(["git", "merge-base", "--is-ancestor", f"origin/{old_base}", f"origin/{BASE}"],
                      cwd=REPO).returncode != 0 and not DRY:
        die(f"origin/{old_base} is not merged into origin/{BASE} yet (or was squash-merged); do not retarget")
    gh("pr", "edit", str(pr["number"]), "--repo", slug, "--base", BASE, write=True)
    print(f"{pr['url']} now targets {BASE} (Bob's go: \"{go}\")")


# --------------------------------------------------------------------------
# the day's one go: daily (close-out, commit, PR) and after-merge (sync, publish)
# Bob, 2026-10-07, verbatim: "THIS SHOULD BE 1 "GO" THEN MY MERGE. THE SYNC SHOULD BE AUTOMATED." and, on the site
# publish, "IF THE ORIGINAL PR WAS APPROVED, THE CONTENT HAS ALREADY BEEN APPROVED AND IT SHOULD BE DONE."
# --------------------------------------------------------------------------
def show(p: Path) -> str:
    """Repo-relative path for messages; the absolute path when it lies outside the repo (tests, a scratch file)."""
    try:
        return rp.rel(p)
    except ValueError:
        return str(p)


def go_file(date: str) -> Path:
    return rp.DAILY / f"{date}-go.txt"


def save_go(date: str, go: str) -> Path:
    """Write the day's go verbatim, once. The same words again are fine (a rerun); different words are refused:
    one go a day, and nobody rewrites what Bob said."""
    p = go_file(date)
    if p.is_file():
        old = p.read_text(encoding="utf-8-sig").strip()
        if old != go.strip():
            die(f"{show(p)} already holds the go for {date}: \"{old}\". One go a day: rerun with those exact words, "
                f"or, if Bob gave a new go, raise it with him; this tool never rewrites the go file")
        print(f"go: {show(p)} already holds these words", flush=True)
        return p
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(go.strip() + "\n", encoding="utf-8", newline="\n")
    print(f"go: saved verbatim to {show(p)}", flush=True)
    return p


def read_go(date: str) -> str:
    p = go_file(date)
    if not p.is_file():
        die(f"no go file {show(p)}: the day's go is saved by `track.py daily` (or write Bob's words there "
            f"verbatim). after-merge never runs without it")
    go = p.read_text(encoding="utf-8-sig").strip()
    if not go:
        die(f"{show(p)} is empty")
    return go


def ps_quote(s: str) -> str:
    """A PowerShell 5.1 argument that reaches a Python program as `s`: single quotes (' doubled), and " escaped as
    \\" because 5.1 passes embedded double quotes to native programs unescaped (Bob's go may hold them)."""
    return "'" + s.replace("'", "''").replace('"', '\\"') + "'"


def guard_closeout_outputs(date: str, *files: str) -> None:
    """close-out step 8 rewrites <project>/_work/daily/<date>-commit.md and <date>-paths.txt with its skeleton. A commit
    message, paths file or PR body read from either would be the skeleton, not what was named to Bob."""
    owned = {(rp.DAILY / f"{date}-commit.md").resolve(), (rp.DAILY / f"{date}-paths.txt").resolve()}
    for f in files:
        if Path(f).resolve() in owned:
            die(f"{f} is rewritten by closeout.py (step 8 skeleton) during this run; copy it to another name "
                f"(e.g. {date}-commit-final.md / {date}-paths-final.txt) and pass that")


def run_closeout(date: str, go: str, dry: bool) -> int:
    """closeout.py with the repo venv, output streamed (it can run for an hour); returns its exit code."""
    if not VENV_PY.is_file():
        die(f"missing {rp.rel(VENV_PY)} (the repo venv)")
    cmd = [str(VENV_PY), str(rp.SCRIPTS / "closeout.py"), "--date", date] + (["--dry-run"] if dry else ["--bob-go", go])
    print(f"closeout: running {'closeout.py --dry-run' if dry else 'closeout.py'} --date {date}", flush=True)
    return subprocess.run(cmd, cwd=REPO).returncode


CLOSEOUT_NEXT = {
    3: "close-out STOPPED at the list delta (rows appended to <project>/01_Design_Basis/06_Assumptions_Open_Items/pid-revision-requests.md). Nothing committed. "
       "Next: the process-engineer updates the <project>/03_Working_Design/PID/02_Tag_Lists lists (or Bob turns the rows into a P&ID revision request), "
       "then rerun this same `track.py daily` command; the go file keeps the day's go, no new ask.",
    1: "close-out finished with failures (listed above: a broken check, a repo-integrity check, or a step such as "
       "the portal filing or the Drive push). Nothing committed. Fix the cause, then rerun this same `track.py daily` "
       "command with the same go.",
    2: "close-out refused (REFUSED line above). Nothing committed. Fix the cause and rerun this same `track.py daily` "
       "command with the same go.",
}


def uncovered_filed_reviews(date: str, paths: list[str]) -> list[str]:
    """Files filed under <project>/06_Issued_Revisions/Portals/ today (revisions.csv rows dated <date>: close-out's portal, quoting and landing
    filings) that no listed path covers, with each document's revisions.csv. A large file counts by its .drive
    pointer. Left out of the commit, the filed revision is not in the PR and after-merge cannot publish it."""
    listed = [p.strip().replace("\\", "/").removeprefix("./").rstrip("/") for p in paths]

    def covered(f: str) -> bool:
        return any(f == p or f.startswith(p + "/") for p in listed)

    out = set()
    for revs_csv in sorted(rp.PORTALS.rglob("revisions.csv")):
        with open(revs_csv, newline="", encoding="utf-8-sig") as fh:
            rows = [r for r in csv.DictReader(fh) if r.get("file_date", "").startswith(date)]
        if not rows:
            continue
        need = [rp.rel(revs_csv)]
        for r in rows:
            f = revs_csv.parent / r["file"]
            ptr = Path(str(f) + ".drive")
            need.append(rp.rel(ptr if ptr.is_file() else f))
        out.update(n for n in need if not covered(n))
    return sorted(out)


def cmd_daily(a) -> None:
    """The day's close-out, commit and PR on one go. Every input is checked before close-out runs."""
    if DRY and not (a.bob_go or "").strip():
        a.bob_go = "(dry run: no go yet)"   # the rehearsal comes before Bob is asked; nothing is saved or sent
    go = require_go(a.bob_go, "the day's close-out, commit and PR")
    date = check_date(a.date)
    guard_closeout_outputs(date, a.paths_file, a.message_file, a.body_file)
    commit_inputs(a, check_exist=False)   # paths are checked again after close-out, when its filings exist
    pr_body(a)
    if DRY:
        print(f"go: DRY-RUN would save the go verbatim to {show(go_file(date))}", flush=True)
    else:
        save_go(date, go)
    rc = run_closeout(date, go, DRY)
    if rc != 0:
        print(f"closeout: exit {rc}. {CLOSEOUT_NEXT.get(rc, 'Nothing committed. Read the output above, fix, and rerun.')}",
              flush=True)
        sys.exit(rc)
    print(f"closeout: {'dry run listed every step' if DRY else 'done'} (exit 0)", flush=True)
    if not DRY:
        missing = uncovered_filed_reviews(date, commit_inputs(a)[0])
        if missing:
            die(f"{len(missing)} path(s) filed under <project>/06_Issued_Revisions/Portals/ today are not in {a.paths_file}; add the document "
                f"folder (e.g. <project>/06_Issued_Revisions/Portals/project-portal) and rerun `track.py daily` with the same go:\n  "
                + "\n  ".join(missing[:20]) + ("\n  ..." if len(missing) > 20 else ""))
    cmd_daily_commit(a)
    print("commit: dry run listed" if DRY else
          "commit: done. If the PR step is refused, fix it and run daily-pr alone with the same go "
          "(rerunning daily would find nothing new to commit)", flush=True)
    url = cmd_daily_pr(a)
    print(f"PR: {url or '(dry run)'}", flush=True)


def merge_refusal(prs: list[dict], branch: str) -> str | None:
    """None when the day's PR has merged and none is still open; else why after-merge must not run."""
    if not prs:
        return f"no PR from {branch}; run `track.py daily` first"
    still_open = [p for p in prs if p.get("state") == "OPEN"]
    if still_open:
        return f"{still_open[0]['url']} from {branch} is still open; after-merge runs once Bob has merged it"
    if not any(p.get("state") == "MERGED" for p in prs):
        return f"the PR from {branch} was closed without merging ({prs[0]['url']}); raise it with Bob"
    return None


SITE_DIFF = re.compile(r"vs site:\s*(\d+) added, (\d+) changed, \d+ unchanged, (\d+) removed")


def site_difference(out: str) -> tuple[int, int, int] | None:
    """(added, changed, removed) from publish_site.py --dry-run output, or None if it printed no plan."""
    m = SITE_DIFF.search(out)
    return (int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None


def publish_after_merge(go: str) -> None:
    """publish_site.py --dry-run with the newest filed revisions; publish for real only when the site differs.
    A project with no presentation site yet (site_revs.site_dormant, CPME practice) publishes nothing and passes."""
    why = site_revs.site_dormant()
    if why:
        print(f"site: {why}; nothing to publish", flush=True)
        return
    revs = site_revs.newest()
    if not revs["rev"]:
        print("site: no filed project-portal revision; nothing to publish", flush=True)
        return
    args = site_revs.publish_args(revs)
    base = [str(VENV_PY), str(rp.SCRIPTS / "publish_site.py"), *args]
    shown = (r".\harness\tools\venv\Scripts\python.exe harness\scripts\publish_site.py " + " ".join(args)
             + f" --bob-go {ps_quote(go)}")
    r = subprocess.run(base + ["--dry-run"], cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = mask((r.stdout or "") + (r.stderr or ""))
    for ln in out.strip().splitlines():
        print("   " + ln)
    diff = site_difference(out)
    if r.returncode != 0 or diff is None:
        print(f"site: publish dry run exit {r.returncode}{'' if diff else ' (no site plan printed)'}; not published. "
              f"After fixing the cause, the publish is:\n  {shown}", flush=True)
        sys.exit(2)
    added, changed, removed = diff
    if not any(diff):
        print(f"site: already holds {' '.join(args)} (0 added, 0 changed, 0 removed); publish skipped", flush=True)
        return
    if DRY:
        print(f"site: DRY-RUN would publish ({added} added, {changed} changed, {removed} removed):\n  {shown}", flush=True)
        return
    print(f"site: publishing {' '.join(args)} ({added} added, {changed} changed, {removed} removed)", flush=True)
    r = subprocess.run(base + ["--bob-go", go], cwd=REPO)
    if r.returncode != 0:
        # also the path when the desktop app's permission classifier stops the publish (2026-10-07)
        print(f"site: publish_site.py exit {r.returncode}; not published. Run exactly this from the repo root, in a "
              f"window allowed to publish:\n  {shown}", flush=True)
        sys.exit(2)
    print(f"site: published {' '.join(args)}", flush=True)


def cmd_after_merge(a) -> None:
    """After Bob merges the day's PR: sync the shared checkout's main, then publish the site, on the day's go."""
    date = check_date(a.date)
    branch = f"daily/{date}"
    go = read_go(date)
    print(f"go: \"{go}\" (from {show(go_file(date))})", flush=True)
    require_auth()
    slug = repo_slug()
    prs = json.loads(gh("pr", "list", "--repo", slug, "--head", branch, "--state", "all",
                        "--json", "number,state,url") or "[]")
    why = merge_refusal(prs, branch)
    if why:
        die(why)
    print(f"PR: merged {', '.join(p['url'] for p in prs if p['state'] == 'MERGED')}", flush=True)
    a.bob_go = go
    cmd_sync_main(a)
    print(f"sync-main: {'dry run, nothing changed' if DRY else 'done'}", flush=True)
    publish_after_merge(go)


def add_global_flags_to_subcommands(sub: argparse._SubParsersAction) -> None:
    """Accept --dry-run and --as-bob after the subcommand too. `sync-main --dry-run` was refused on 2026-10-07 because
    the flags were global only; a suppressed default keeps the global value when the flag is not repeated."""
    for sp in sub.choices.values():
        sp.add_argument("--dry-run", dest="dry_run", action="store_true", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
        sp.add_argument("--as-bob", dest="as_bob", action="store_true", default=argparse.SUPPRESS, help=argparse.SUPPRESS)


# --------------------------------------------------------------------------
def main() -> None:
    global DRY
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true", help="print writes instead of sending them")
    ap.add_argument("--as-bob", action="store_true",
                    help=f"ignored: {WRITER_ACCOUNT} is the writer since 2026-10-07 (was the interim flag)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    p = sub.add_parser("init-main", help="new job repo only: create main on GitHub as one empty commit, the base for the first daily PR")
    p.add_argument("--bob-go")
    p = sub.add_parser("daily-commit")
    p.add_argument("--date", required=True)
    p.add_argument("--paths-file", required=True)
    p.add_argument("--message-file", required=True)
    p.add_argument("--tag", action="append", default=[])
    p.add_argument("--local", action="store_true", help="commit and tag locally only; push later with daily-push")
    p.add_argument("--start", help="ref to create a new day's branch from (stacking), instead of origin/main")
    p.add_argument("--moves-file", help="CSV with old_path,new_path; tracked old paths are git mv'd (renames)")
    p.add_argument("--removes-file", help="one tracked path per line; each is removed from the index (git rm --cached)")
    p.add_argument("--bob-go")
    p = sub.add_parser("daily-push")
    p.add_argument("--date", required=True)
    p.add_argument("--bob-go")
    p = sub.add_parser("daily-pr")
    p.add_argument("--date", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--body-file", required=True)
    p.add_argument("--closes", action="append", type=int, default=[])
    p.add_argument("--reviewer", action="append", default=[], help="GitHub login to request review from")
    p.add_argument("--base", help="stacked PR: an earlier daily/<date> branch instead of main")
    p.add_argument("--bob-go")
    p = sub.add_parser("pr-retarget")
    p.add_argument("--date", required=True)
    p.add_argument("--bob-go")
    p = sub.add_parser("sync-main", help="after the PR merges: move the shared checkout's main to origin/main, writing no file")
    p.add_argument("--bob-go")
    p = sub.add_parser("daily", help="the day's one go: save it, run closeout.py, then daily-commit and daily-pr")
    p.add_argument("--date", required=True)
    p.add_argument("--paths-file", required=True)
    p.add_argument("--message-file", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--body-file", required=True)
    p.add_argument("--tag", action="append", default=[])
    p.add_argument("--bob-go")
    # what daily-commit / daily-pr take and daily does not offer: their single-command defaults
    p.set_defaults(local=False, start=None, moves_file=None, removes_file=None, closes=[], reviewer=[], base=None)
    p = sub.add_parser("after-merge", help="after Bob merges: sync-main, then publish the site, with the day's saved go")
    p.add_argument("--date", required=True)
    add_global_flags_to_subcommands(sub)
    a = ap.parse_args()
    DRY = a.dry_run
    if a.as_bob:
        print(f"--as-bob is ignored: {WRITER_ACCOUNT} is the writer (Bob, 2026-10-07)")
    {"status": cmd_status, "init-main": cmd_init_main, "daily-commit": cmd_daily_commit, "daily-push": cmd_daily_push,
     "daily-pr": cmd_daily_pr, "pr-retarget": cmd_pr_retarget, "sync-main": cmd_sync_main,
     "daily": cmd_daily, "after-merge": cmd_after_merge}[a.cmd](a)


if __name__ == "__main__":
    main()
