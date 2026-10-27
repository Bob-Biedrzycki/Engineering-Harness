"""drive_store.py - large files live in the job's Google Drive folder; git holds a pointer per file.

Bob, chat, 2026-09-28: "All large files or Large Directories should use Google Drive
as the database with pointers referencing this folder." Not Git LFS.

How it works
  * job/drive-store.yaml names the Drive folder and the rules: every file at or above
    `large_file_bytes`, and every file with a listed extension under a listed directory.
  * Each selected file gets a tracked pointer `<file>.drive` (JSON: path, bytes, sha256, md5,
    mtime, drive_folder). The file itself is gitignored by the managed block this tool writes
    into .gitignore, and lives in the Drive folder at the same repo-relative path.
  * The working tree keeps the real file beside its pointer, so builds and viewers work.
    `pull` fetches a missing file from Drive; `push` copies a new one there; `verify` hashes.
  * Transport: rclone (Bob, 2026-09-28) through the remote named `rclone_remote` in the YAML,
    rooted at the Drive folder; each machine creates it once with Bob's own Google sign-in
    (command in the YAML). Drive reports MD5, so the Drive side is checked by size and md5 and
    the local side by sha256. With --root <folder>, a plain folder (Google Drive for Desktop,
    or a staging mirror to drag into Drive) is used instead of rclone.
  * A filed revision never changes (TR-08): `pointers` refuses to rewrite a pointer whose file
    now hashes differently unless --allow-change is given, and `push` never overwrites a
    different file in Drive.

Run from the repo root with the repo venv:
  .\\harness\\tools\\venv\\Scripts\\python.exe harness\\scripts\\drive_store.py scan
  ... pointers [--allow-change]          write or refresh pointers and the .gitignore block (no upload)
  ... push [--root PATH] [--dry-run]     copy selected files into Drive (rclone) or a folder; --dry-run lists them
  ... pull [--root PATH]                 copy files missing from the working tree out of Drive
  ... verify [--root PATH] [--local-only]  check working tree (sha256) and Drive (size, md5) against the pointers
Exit codes: 0 ok, 1 a check found a problem, 2 refused (bad input, no transport).
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists()) / "harness" / "lib"))
import repo_paths as rp  # noqa: E402
import drive_rules  # noqa: E402  (the selection rules and block markers, shared with drive_pointers.py and track.py)
from drive_rules import BLOCK_BEGIN, BLOCK_END, POINTER_SUFFIX, excluded, rule_for  # noqa: E402,F401

REPO = rp.REPO
CHUNK = 4 * 1024 * 1024
SKIP_DIRS = (tuple(rp.rel(p) for p in (rp.WORK, rp.EXPORTS, rp.FAST_BUILDS, rp.PID_FAST_EDITS)) if rp.HAS_PROJECT
             else ()) + ("harness/tools", ".venv", "job/_work")
# rclone file lists: the project's working copies, or the job's while there is no project yet
LIST_WORK = (rp.WORK if rp.HAS_PROJECT else rp.JOBS / "_work") / "drive-store"
RCLONE_GLOB = str(Path.home() / "AppData/Local/Microsoft/WinGet/Packages/Rclone.Rclone_*/rclone-*/rclone.exe")


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def die(msg: str) -> None:
    print(f"REFUSED: {msg}", file=sys.stderr)
    sys.exit(2)


def mb(n: int) -> str:
    return f"{n / 1048576:,.1f} MB"


def load_config() -> dict:
    if not rp.DRIVE_STORE_CONFIG.is_file():
        die(f"missing {rp.rel(rp.DRIVE_STORE_CONFIG)}")
    try:
        return drive_rules.load(rp.DRIVE_STORE_CONFIG)
    except KeyError as e:
        die(f"{rp.rel(rp.DRIVE_STORE_CONFIG)} has no '{e.args[0]}'")


def hashes_of(path: Path) -> tuple[str, str]:
    """(sha256, md5) in one pass."""
    s, m = hashlib.sha256(), hashlib.md5()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(CHUNK), b""):
            s.update(block)
            m.update(block)
    return s.hexdigest(), m.hexdigest()


def iso_mtime(path: Path) -> str:
    return dt.datetime.fromtimestamp(path.stat().st_mtime).replace(microsecond=0).isoformat(sep=" ")


def selected_files(cfg: dict) -> list[tuple[str, int, str]]:
    """(rel_path, bytes, rule) for every working-tree file the rules select, sorted."""
    out = []
    for root, dirs, files in os.walk(REPO):
        rel_root = Path(root).relative_to(REPO).as_posix()
        rel_root = "" if rel_root == "." else rel_root
        dirs[:] = sorted(d for d in dirs if not excluded(f"{rel_root}/{d}".strip("/"), cfg))
        for f in sorted(files):
            rel = f"{rel_root}/{f}".strip("/")
            size = os.path.getsize(Path(root) / f)
            rule = rule_for(rel, size, cfg)
            if rule:
                out.append((rel, size, rule))
    return out


def pointer_path(rel: str) -> Path:
    return REPO / (rel + POINTER_SUFFIX)


def read_pointer(p: Path) -> dict:
    try:
        d = json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as e:
        die(f"unreadable pointer {rp.rel(p)}: {e}")
    for key in ("path", "bytes", "sha256"):
        if key not in d:
            die(f"pointer {rp.rel(p)} has no '{key}'")
    if d["path"] + POINTER_SUFFIX != p.relative_to(REPO).as_posix():
        die(f"pointer {rp.rel(p)} names a different path: {d['path']}")
    return d


def write_pointer(rel: str, size: int, sha: str, md5: str, mtime: str, cfg: dict) -> None:
    data = {"path": rel, "bytes": size, "sha256": sha, "md5": md5, "mtime": mtime,
            "drive_folder": cfg["drive_folder_url"],
            "note": "Pointer to a file in the job's Google Drive store (same path under that folder). "
                    "Written by harness/scripts/drive_store.py; never edited by hand."}
    pointer_path(rel).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n")


def all_pointers() -> list[Path]:
    out = []
    for root, dirs, files in os.walk(REPO):
        rel_root = Path(root).relative_to(REPO).as_posix()
        rel_root = "" if rel_root == "." else rel_root
        dirs[:] = sorted(d for d in dirs if d != ".git" and f"{rel_root}/{d}".strip("/") not in SKIP_DIRS
                         and not drive_rules.under(f"{rel_root}/{d}".strip("/"), "job/*/_work"))
        out += [Path(root) / f for f in sorted(files) if f.endswith(POINTER_SUFFIX)]
    return sorted(out)


def tracked_files() -> set[str]:
    r = subprocess.run(["git", "ls-files", "-z"], cwd=REPO, capture_output=True)
    return {p.decode("utf-8") for p in r.stdout.split(b"\0") if p}


def local_state(d: dict) -> str:
    """'ok', 'MISSING' or 'MISMATCH' for the working-tree copy of a pointer's file."""
    f = REPO / d["path"]
    if not f.is_file():
        return "MISSING"
    if f.stat().st_size != d["bytes"]:
        return "MISMATCH"
    return "ok" if hashes_of(f)[0] == d["sha256"] else "MISMATCH"


def gitignore_escape(rel: str) -> str:
    out = rel.replace("\\", "\\\\")
    for ch in "[]*?":
        out = out.replace(ch, "\\" + ch)
    if out.startswith(("#", "!")):
        out = "\\" + out
    if out.endswith(" "):
        out = out[:-1] + "\\ "
    return "/" + out


def gitignore_block(cfg: dict, size_rule_paths: list[str]) -> list[str]:
    lines = [BLOCK_BEGIN,
             f"# Files in the Google Drive store ({rp.rel(rp.DRIVE_STORE_CONFIG)}). Their *.drive pointers are tracked; "
             "the files are not."]
    for d, exts in cfg["directories"].items():
        for e in sorted(exts):
            lines.append(f"/{d}/**/*.{e}")
            if e.upper() != e:
                lines.append(f"/{d}/**/*.{e.upper()}")
    if size_rule_paths:
        lines.append(f"# Files at or above {int(cfg['large_file_bytes']):,} bytes outside those directories:")
        lines += [gitignore_escape(p) for p in size_rule_paths]
    lines.append(BLOCK_END)
    return lines


def write_gitignore_block(cfg: dict, size_rule_paths: list[str]) -> bool:
    gi = REPO / ".gitignore"
    text = gi.read_text(encoding="utf-8-sig") if gi.exists() else ""
    old = text.splitlines()
    block = gitignore_block(cfg, size_rule_paths)
    i = drive_rules.block_begin_index(old)
    if i >= 0 and BLOCK_END in old[i:]:
        j = old.index(BLOCK_END, i)
        new = old[:i] + block + old[j + 1:]
    else:
        new = old + ([""] if old and old[-1].strip() else []) + block
    if new == old:
        return False
    gi.write_text("\n".join(new) + "\n", encoding="utf-8", newline="\n")
    return True


# --------------------------------------------------------------------------
# transports: a plain folder (--root) or rclone to the Drive folder
# --------------------------------------------------------------------------
class FolderStore:
    """A local folder holding the same paths (Google Drive for Desktop, or a staging mirror)."""

    def __init__(self, root: Path):
        self.root = root

    def describe(self) -> str:
        return f"folder {self.root}"

    def stat(self, rel: str) -> dict | None:
        f = self.root / rel
        if not f.is_file():
            return None
        sha, md5 = hashes_of(f)
        return {"bytes": f.stat().st_size, "sha256": sha, "md5": md5}

    def push(self, rels: list[str]) -> None:
        for rel in rels:
            dst = self.root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(REPO / rel, dst)

    def pull(self, rels: list[str]) -> None:
        for rel in rels:
            dst = REPO / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.root / rel, dst)


class RcloneStore:
    """The Drive folder itself, through the rclone remote named in the YAML."""

    def __init__(self, remote: str):
        exe = shutil.which("rclone") or next(iter(sorted(glob.glob(RCLONE_GLOB), reverse=True)), None)
        if not exe:
            die("rclone is not installed. Bob installs it:  winget install --id Rclone.Rclone --scope user")
        self.exe, self.remote = exe, remote
        remotes = self._run(["listremotes"]).split()
        if f"{remote}:" not in remotes:
            die(f"rclone has no remote '{remote}'. Bob creates it once (opens the browser for his Google sign-in):\n"
                f"  rclone config create {remote} drive scope=drive root_folder_id=<folder id from job/drive-store.yaml>")
        self._listing: dict[str, dict] | None = None

    def _run(self, args: list[str]) -> str:
        r = subprocess.run([self.exe, *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            die(f"rclone {' '.join(args[:2])} failed ({r.returncode}):\n{r.stderr.strip()[-2000:]}")
        return r.stdout

    def describe(self) -> str:
        return f"rclone remote {self.remote}: (Drive folder)"

    def listing(self, refresh: bool = False) -> dict[str, dict]:
        if self._listing is None or refresh:
            out = self._run(["lsjson", "-R", "--files-only", "--hash", "--hash-type", "md5", f"{self.remote}:"])
            self._listing = {e["Path"]: {"bytes": e.get("Size", -1), "md5": (e.get("Hashes") or {}).get("md5", "")}
                             for e in json.loads(out or "[]")}
        return self._listing

    def stat(self, rel: str) -> dict | None:
        return self.listing().get(rel)

    def _files_from(self, rels: list[str], name: str) -> Path:
        LIST_WORK.mkdir(parents=True, exist_ok=True)
        p = LIST_WORK / name
        p.write_text("\n".join(rels) + "\n", encoding="utf-8", newline="\n")
        return p

    def push(self, rels: list[str]) -> None:
        lst = self._files_from(rels, "push-list.txt")
        self._run(["copy", str(REPO), f"{self.remote}:", "--files-from", str(lst), "--checksum",
                   "--transfers", "4", "--checkers", "8", "-q"])
        self.listing(refresh=True)

    def pull(self, rels: list[str]) -> None:
        lst = self._files_from(rels, "pull-list.txt")
        self._run(["copy", f"{self.remote}:", str(REPO), "--files-from", str(lst), "--checksum",
                   "--transfers", "4", "--checkers", "8", "-q"])


def matches(d: dict, st: dict | None) -> str:
    """Compare a pointer with a store stat: 'ok', 'MISSING', 'MISMATCH', or 'size-only' (no usable hash)."""
    if st is None:
        return "MISSING"
    if st["bytes"] != d["bytes"]:
        return "MISMATCH"
    if st.get("sha256"):
        return "ok" if st["sha256"] == d["sha256"] else "MISMATCH"
    if st.get("md5") and d.get("md5"):
        return "ok" if st["md5"] == d["md5"] else "MISMATCH"
    return "size-only"


def open_store(cfg: dict, root_arg: str | None):
    root = root_arg
    src = "--root"
    if not root and os.environ.get("CPME_DRIVE_ROOT"):
        root, src = os.environ["CPME_DRIVE_ROOT"], "CPME_DRIVE_ROOT"
    if not root and rp.DRIVE_ROOT_FILE.is_file():
        root, src = rp.DRIVE_ROOT_FILE.read_text(encoding="utf-8-sig").splitlines()[0].strip(), rp.rel(rp.DRIVE_ROOT_FILE)
    if root:
        p = Path(root).expanduser()
        if not p.is_dir():
            die(f"Drive folder path from {src} is not a directory: {p}")
        return FolderStore(p)
    if cfg.get("rclone_remote"):
        return RcloneStore(cfg["rclone_remote"])
    die("no transport: set rclone_remote in job/drive-store.yaml, or give --root <local folder> "
        "(or CPME_DRIVE_ROOT, or the first line of job/_work/drive-root.txt)")


# --------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------
def cmd_scan(a) -> None:
    cfg = load_config()
    sel = selected_files(cfg)
    tracked = tracked_files()
    total = 0
    print(f"{'rule':<4} {'size':>12}  {'pointer':<8} {'git':<8} path")
    for rel, size, rule in sel:
        total += size
        ptr = "yes" if pointer_path(rel).exists() else "none"
        git_state = "TRACKED" if rel in tracked else "-"
        print(f"{rule:<4} {mb(size):>12}  {ptr:<8} {git_state:<8} {rel}")
    orphans = [p for p in all_pointers() if not (REPO / read_pointer(p)["path"]).exists()]
    print(f"\n{len(sel)} file(s), {mb(total)} selected for the Drive store; "
          f"{sum(1 for r, _, _ in sel if pointer_path(r).exists())} with a pointer; "
          f"{sum(1 for r, _, _ in sel if r in tracked)} still tracked in git (remove from the index in the daily commit)")
    if orphans:
        print(f"{len(orphans)} pointer(s) whose file is not in the working tree (run pull):")
        for p in orphans:
            print(f"  {rp.rel(p)}")


def cmd_pointers(a) -> None:
    cfg = load_config()
    sel = selected_files(cfg)
    written = unchanged = 0
    changed: list[str] = []
    for rel, size, rule in sel:
        f = REPO / rel
        ptr = pointer_path(rel)
        mtime = iso_mtime(f)
        if ptr.exists():
            old = read_pointer(ptr)
            if old["bytes"] == size and old.get("mtime") == mtime and old.get("md5"):
                unchanged += 1
                continue
            sha, md5 = hashes_of(f)
            if sha != old["sha256"]:
                if not a.allow_change:
                    changed.append(f"{rel}: pointer {old['sha256'][:12]} ({old['bytes']} B) vs file {sha[:12]} ({size} B)")
                    continue
            elif old.get("md5") == md5 and old.get("mtime") == mtime:
                unchanged += 1
                continue
        else:
            sha, md5 = hashes_of(f)
        write_pointer(rel, size, sha, md5, mtime, cfg)
        written += 1
    size_rule_paths = sorted(rel for rel, _, rule in sel if rule == "size"
                             and not any(drive_rules.under(rel, d) and rel.rsplit(".", 1)[-1].lower() in exts
                                         for d, exts in cfg["directories"].items()))
    gi = write_gitignore_block(cfg, size_rule_paths)
    tracked = tracked_files()
    still = [rel for rel, _, _ in sel if rel in tracked]
    print(f"pointers: {written} written, {unchanged} unchanged, {len(sel)} selected, "
          f"{mb(sum(s for _, s, _ in sel))} total; .gitignore block {'updated' if gi else 'unchanged'}")
    if still:
        print(f"{len(still)} selected file(s) are still tracked in git; remove them from the index in the daily commit "
              "(track.py daily-commit --removes-file):")
        for rel in still:
            print(f"  {rel}")
    if changed:
        print(f"\n{len(changed)} file(s) differ from their pointer and were NOT rewritten (TR-08: a filed file never "
              "changes; pass --allow-change only for a file that was never filed or handed off):")
        for c in changed:
            print(f"  {c}")
        sys.exit(1)


def cmd_push(a) -> None:
    cfg = load_config()
    store = open_store(cfg, a.root)
    to_push: list[str] = []
    skipped = missing = 0
    problems: list[str] = []
    pointers = [read_pointer(p) for p in all_pointers()]
    for d in pointers:
        if not (REPO / d["path"]).is_file():
            missing += 1
            continue
        state = matches(d, store.stat(d["path"]))
        if state == "ok":
            skipped += 1
            continue
        if state in ("MISMATCH", "size-only"):
            problems.append(f"{d['path']}: a different file is already in {store.describe()} ({state}); not overwritten")
            continue
        if local_state(d) != "ok":
            problems.append(f"{d['path']}: working-tree file does not match its pointer; run pointers first")
            continue
        to_push.append(d["path"])
    if getattr(a, "dry_run", False):
        total = sum(d["bytes"] for d in pointers if d["path"] in set(to_push))
        print(f"push to {store.describe()} (DRY RUN, nothing copied): {len(to_push)} file(s), {mb(total)}, would be "
              f"copied; {skipped} already there, {missing} not in the working tree, {len(problems)} problem(s)")
        for rel in to_push:
            print(f"  would push  {rel}")
        for p in problems:
            print(f"  {p}")
        sys.exit(1 if problems else 0)
    if to_push:
        total = sum(d["bytes"] for d in pointers if d["path"] in set(to_push))
        print(f"copying {len(to_push)} file(s), {mb(total)}, to {store.describe()} ...")
        store.push(to_push)
        copied = 0
        for d in pointers:
            if d["path"] in to_push:
                state = matches(d, store.stat(d["path"]))
                if state == "ok":
                    copied += 1
                else:
                    problems.append(f"{d['path']}: after copy the store copy reads {state}")
    else:
        copied = 0
    print(f"push to {store.describe()}: {copied} copied and verified, {skipped} already there, "
          f"{missing} not in the working tree, {len(problems)} problem(s)")
    for p in problems:
        print(f"  {p}")
    sys.exit(1 if problems else 0)


def cmd_pull(a) -> None:
    cfg = load_config()
    store = open_store(cfg, a.root)
    to_pull: list[str] = []
    present = absent = 0
    problems: list[str] = []
    pointers = [read_pointer(p) for p in all_pointers()]
    for d in pointers:
        if (REPO / d["path"]).is_file():
            present += 1
            continue
        state = matches(d, store.stat(d["path"]))
        if state == "MISSING":
            absent += 1
            print(f"absent  {mb(d['bytes']):>12}  {d['path']}  (not in {store.describe()})")
        elif state == "ok":
            to_pull.append(d["path"])
        else:
            problems.append(f"{d['path']}: the store copy does not match the pointer ({state}); not copied")
    pulled = 0
    if to_pull:
        print(f"copying {len(to_pull)} file(s) from {store.describe()} ...")
        store.pull(to_pull)
        for d in pointers:
            if d["path"] in to_pull:
                if local_state(d) == "ok":
                    pulled += 1
                else:
                    problems.append(f"{d['path']}: pulled copy does not match the pointer")
    print(f"pull from {store.describe()}: {pulled} copied and verified, {present} already present, "
          f"{absent} absent from the store, {len(problems)} problem(s)")
    for p in problems:
        print(f"  {p}")
    sys.exit(1 if problems else 0)


def cmd_verify(a) -> None:
    cfg = load_config()
    store = None if a.local_only else open_store(cfg, a.root)
    problems = n = total = 0
    for ptr in all_pointers():
        d = read_pointer(ptr)
        n += 1
        total += d["bytes"]
        states = [f"local:{local_state(d)}"]
        if store is not None:
            states.append(f"drive:{matches(d, store.stat(d['path']))}")
        problems += sum(1 for s in states if not s.endswith(":ok"))
        print(f"{' '.join(states):<32} {d['path']}")
    where = "" if store is None else f" against {store.describe()}"
    print(f"\nverify{where}: {n} pointer(s), {mb(total)}, {problems} problem(s)")
    sys.exit(1 if problems else 0)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("scan", help="list the files the rules select and their pointer and git state")
    p = sub.add_parser("pointers", help="write or refresh <file>.drive pointers and the .gitignore block")
    p.add_argument("--allow-change", action="store_true",
                   help="rewrite a pointer whose file now hashes differently (never for a filed revision, TR-08)")
    for name, h in (("push", "copy selected files into the Drive store"),
                    ("pull", "copy files missing from the working tree out of the Drive store"),
                    ("verify", "check working tree and Drive store against the pointers")):
        p = sub.add_parser(name, help=h)
        p.add_argument("--root", help="use this local folder instead of rclone (else CPME_DRIVE_ROOT or job/_work/drive-root.txt)")
        if name == "verify":
            p.add_argument("--local-only", action="store_true", help="check the working tree only")
        if name == "push":
            p.add_argument("--dry-run", action="store_true", help="list the files push would copy; copy nothing")
    a = ap.parse_args()
    {"scan": cmd_scan, "pointers": cmd_pointers, "push": cmd_push, "pull": cmd_pull, "verify": cmd_verify}[a.cmd](a)


if __name__ == "__main__":
    main()
