"""harness_sync.py - keep a job repo's harness the same as the Engineering Harness master copy.

CPME practice (Bob, 2026-10-27): harness/, .claude/agents, .claude/skills, .claude/settings.json, CLAUDE.md, .github/,
.gitattributes and the core of .gitignore hold only what is true for every CPME skid job (the list is
harness/harness-manifest.txt). One master copy holds them; a harness fix is made in the master and pulled into each
job. Job-owned files (job/**, the question files, README.md, .claude/launch.json, .claude/settings.local.json, and the
drive-store block of .gitignore) are never written by this script. There is no push: harness changes are made in the
master.

    python harness/scripts/harness_sync.py check <job repo> [--master PATH]
        compare every harness-owned file by sha256; list added (in the master, not the job), changed, and missing
        (in the job, not the master)
    python harness/scripts/harness_sync.py pull <job repo> [--master PATH]
        copy the master's added and changed harness-owned files into the job and print each; a missing file (the
        job has it, the master does not) is listed and left alone
    python harness/scripts/harness_sync.py seed --master PATH [--job PATH] [--force]
        copy a job's harness-owned files (default: this repo) INTO the master; refuses when a master file differs,
        unless --force

The master defaults to CPME_HARNESS_MASTER, else C:\\Users\\Bob\\Documents\\Engineering Harness (Bob, 2026-10-27).
The manifest read is the master's for check and pull (the master is the authority), and the job's for seed; either
falls back to this script's own harness/harness-manifest.txt.

Exit codes: 0 identical (nothing to do), 1 differences found (listed; pulled or seeded where the command does that),
2 refused (a folder missing, the same folder twice, or a differing master file without --force).
"""
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sys
from dataclasses import dataclass, field
from fnmatch import fnmatchcase
from pathlib import Path

HERE_REPO = next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists())
sys.path.insert(0, str(HERE_REPO / "harness" / "lib"))
import drive_rules  # noqa: E402  (split_block: the .gitignore drive-store block markers)

MANIFEST_REL = "harness/harness-manifest.txt"
DEFAULT_MASTER = Path(r"C:\Users\Bob\Documents\Engineering Harness")
CORE_SUFFIX = "#core"
GLOB_CHARS = set("*?[")


def default_master() -> Path:
    env = os.environ.get("CPME_HARNESS_MASTER", "").strip()
    return Path(env) if env else DEFAULT_MASTER


@dataclass
class Manifest:
    include: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)
    core: list[str] = field(default_factory=list)   # files whose lines outside the drive-store block are owned


def parse_manifest(text: str) -> Manifest:
    m = Manifest()
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("!"):
            m.exclude.append(line[1:].strip())
        elif line.endswith(CORE_SUFFIX):
            m.core.append(line[:-len(CORE_SUFFIX)])
        else:
            m.include.append(line)
    return m


def read_manifest(*roots: Path) -> Manifest:
    """The manifest of the first root that has one, else this script's own."""
    for r in (*roots, HERE_REPO):
        p = Path(r) / MANIFEST_REL
        if p.is_file():
            return parse_manifest(p.read_text(encoding="utf-8"))
    raise FileNotFoundError(MANIFEST_REL)


def owned(rel: str, m: Manifest) -> bool:
    return any(fnmatchcase(rel, p) for p in m.include) and not any(fnmatchcase(rel, p) for p in m.exclude)


def _base(pattern: str) -> str:
    parts = []
    for seg in pattern.split("/"):
        if GLOB_CHARS & set(seg):
            break
        parts.append(seg)
    return "/".join(parts)


def owned_files(root: Path, m: Manifest) -> dict[str, Path]:
    """{repo-relative posix path: path} of every harness-owned file under root (the #core files not included)."""
    out: dict[str, Path] = {}
    for base in sorted({_base(p) for p in m.include}):
        start = root / base if base else root
        if start.is_file():
            cands = [start]
        elif start.is_dir():
            cands = []
            for dirpath, dirs, files in os.walk(start):
                d = Path(dirpath)
                reld = d.relative_to(root).as_posix()
                # prune an excluded folder (harness/tools/ holds the venvs) instead of walking it
                dirs[:] = [x for x in dirs if not any(fnmatchcase(f"{reld}/{x}/", p) for p in m.exclude)]
                cands += [d / f for f in files]
        else:
            continue
        for p in cands:
            rel = p.relative_to(root).as_posix()
            if owned(rel, m):
                out[rel] = p
    return out


def core_lines(path: Path) -> list[str] | None:
    """The lines of a #core file outside its drive-store managed block (right-stripped), or None if missing."""
    if not path.is_file():
        return None
    outside, _ = drive_rules.split_block(path.read_text(encoding="utf-8-sig"))
    return [ln.rstrip() for ln in outside]


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def snapshot(root: Path, m: Manifest) -> dict[str, str]:
    """{key: sha256} of every harness-owned file under root; a #core file is keyed '<file>#core' and hashed on its
    core lines only."""
    snap = {rel: _sha(p.read_bytes()) for rel, p in owned_files(root, m).items()}
    for rel in m.core:
        lines = core_lines(root / rel)
        if lines is not None:
            snap[rel + CORE_SUFFIX] = _sha(("\n".join(lines) + "\n").encode("utf-8"))
    return snap


@dataclass
class Diff:
    added: list[str]     # in the reference, not the target
    changed: list[str]   # in both, different
    missing: list[str]   # in the target, not the reference

    @property
    def identical(self) -> bool:
        return not (self.added or self.changed or self.missing)


def compare(target: Path, reference: Path, m: Manifest) -> Diff:
    t, r = snapshot(target, m), snapshot(reference, m)
    return Diff(added=sorted(set(r) - set(t)), changed=sorted(k for k in set(r) & set(t) if r[k] != t[k]),
                missing=sorted(set(t) - set(r)))


def copy_owned(key: str, src_root: Path, dst_root: Path, core_with_block: bool = True) -> None:
    """Copy one harness-owned file (or a #core file's core lines, keeping the destination's own drive-store block)."""
    if key.endswith(CORE_SUFFIX):
        rel = key[:-len(CORE_SUFFIX)]
        lines = core_lines(src_root / rel) or []
        dst = dst_root / rel
        block = None
        if core_with_block and dst.is_file():
            block = drive_rules.split_block(dst.read_text(encoding="utf-8-sig"))[1]
        dst.parent.mkdir(parents=True, exist_ok=True)
        text = "\n".join(lines + ([""] + block if block else [])) + "\n"
        dst.write_text(text, encoding="utf-8", newline="\n")
        return
    dst = dst_root / key
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src_root / key, dst)


def _print_diff(head: str, d: Diff, labels=("added", "changed", "missing")) -> None:
    print(head)
    for label, keys in zip(labels, (d.added, d.changed, d.missing)):
        for k in keys:
            print(f"  {label:<8} {k}")


def _refuse(msg: str) -> int:
    print(f"harness_sync: REFUSED - {msg}", file=sys.stderr)
    return 2


def _check_pair(job: Path, master: Path) -> str | None:
    if not job.is_dir():
        return f"job repo {job} is not a folder"
    if not master.is_dir():
        return f"master {master} is not a folder (seed it first: harness_sync.py seed --master <folder>)"
    if job.resolve() == master.resolve():
        return f"the job and the master are the same folder ({job})"
    return None


def cmd_check(job: Path, master: Path) -> int:
    why = _check_pair(job, master)
    if why:
        return _refuse(why)
    m = read_manifest(master, job)
    d = compare(job, master, m)
    n = len(snapshot(master, m))
    if d.identical:
        print(f"harness_sync check: IDENTICAL - {n} harness-owned file(s) of {job} match the master {master}")
        return 0
    _print_diff(f"harness_sync check: DIFFERENT - {job} vs the master {master}: {len(d.added)} added, "
                f"{len(d.changed)} changed, {len(d.missing)} missing (added = in the master only; missing = in the "
                f"job only)", d)
    return 1


def cmd_pull(job: Path, master: Path) -> int:
    why = _check_pair(job, master)
    if why:
        return _refuse(why)
    m = read_manifest(master, job)
    d = compare(job, master, m)
    if d.identical:
        print(f"harness_sync pull: IDENTICAL - nothing to pull from {master}")
        return 0
    for k in d.added + d.changed:
        copy_owned(k, master, job)
    _print_diff(f"harness_sync pull: PULLED {len(d.added)} added and {len(d.changed)} changed file(s) from {master} "
                f"into {job}; {len(d.missing)} job-only harness file(s) left alone (not in the master)", d,
                ("pulled", "pulled", "kept"))
    return 1


def cmd_seed(job: Path, master: Path, force: bool) -> int:
    if not job.is_dir():
        return _refuse(f"job repo {job} is not a folder")
    if master.exists() and not master.is_dir():
        return _refuse(f"master {master} is not a folder")
    if master.exists() and job.resolve() == master.resolve():
        return _refuse(f"the job and the master are the same folder ({job})")
    if not master.exists():
        if not master.parent.is_dir():
            return _refuse(f"the master's parent folder {master.parent} does not exist")
        master.mkdir()
    m = read_manifest(job)
    d = compare(master, job, m)
    if d.changed and not force:
        _print_diff(f"harness_sync seed: REFUSED - {len(d.changed)} master file(s) differ from {job}; the master is "
                    "never overwritten without --force", Diff([], d.changed, []), ("added", "differs", "missing"))
        return 2
    if d.identical:
        print(f"harness_sync seed: IDENTICAL - the master {master} already holds {job}'s harness")
        return 0
    for k in d.added + d.changed:
        copy_owned(k, job, master, core_with_block=False)
    _print_diff(f"harness_sync seed: SEEDED {len(d.added)} new and {len(d.changed)} overwritten file(s) into {master} "
                f"from {job}; {len(d.missing)} master-only harness file(s) left alone", d,
                ("seeded", "forced", "kept"))
    return 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("check", "pull"):
        p = sub.add_parser(name)
        p.add_argument("job", type=Path, help="the job repo folder")
        p.add_argument("--master", type=Path, default=None, help="master copy (default CPME_HARNESS_MASTER or "
                                                                    f"{DEFAULT_MASTER})")
    p = sub.add_parser("seed")
    p.add_argument("--master", type=Path, required=True, help="master folder to fill (empty, or same content)")
    p.add_argument("--job", type=Path, default=HERE_REPO, help="job repo to copy from (default this repo)")
    p.add_argument("--force", action="store_true", help="overwrite master files that differ")
    a = ap.parse_args(argv)
    if a.cmd == "seed":
        return cmd_seed(a.job, a.master, a.force)
    master = a.master or default_master()
    return cmd_check(a.job, master) if a.cmd == "check" else cmd_pull(a.job, master)


if __name__ == "__main__":
    sys.exit(main())
