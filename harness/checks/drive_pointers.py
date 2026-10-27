"""drive_pointers - no large file is committed; every Drive-store pointer is well formed.

Checks (job/drive-store.yaml, harness/scripts/drive_store.py):
  * no tracked file is selected by the Drive-store rules (size threshold or large directory);
  * every tracked <file>.drive pointer parses, names its own path, has a 64-hex sha256 and a
    byte count, and its file is not tracked;
  * .gitignore carries the managed drive-store block.
Exit 0 PASS, 1 FAIL, 2 NOT IMPLEMENTED (config or dependency missing). First line is the summary.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists()) / "harness" / "lib"))
import repo_paths as rp  # noqa: E402
import drive_rules  # noqa: E402  (the same selection rule as drive_store.py and track.py's daily commit)

try:
    import yaml
except ImportError:
    print("drive_pointers: NOT IMPLEMENTED - pyyaml missing")
    sys.exit(2)

SUFFIX = drive_rules.POINTER_SUFFIX


def main() -> int:
    if not rp.DRIVE_STORE_CONFIG.is_file():
        print(f"drive_pointers: NOT IMPLEMENTED - {rp.rel(rp.DRIVE_STORE_CONFIG)} missing")
        return 2
    cfg = drive_rules.normalize(yaml.safe_load(rp.DRIVE_STORE_CONFIG.read_text(encoding="utf-8")))
    r = subprocess.run(["git", "ls-files", "-z"], cwd=rp.REPO, capture_output=True)
    tracked = [p.decode("utf-8") for p in r.stdout.split(b"\0") if p]
    tracked_set = set(tracked)
    problems: list[str] = []
    pointers = 0
    total = 0

    for rel in tracked:
        f = rp.REPO / rel
        size = os.path.getsize(f) if f.is_file() else 0
        if drive_rules.rule_for(rel, size, cfg):
            problems.append(f"tracked file belongs in the Drive store ({size:,} B): {rel}")
        if rel.endswith(SUFFIX):
            pointers += 1
            try:
                d = json.loads(f.read_text(encoding="utf-8-sig"))
            except (OSError, json.JSONDecodeError) as e:
                problems.append(f"pointer unreadable: {rel} ({e})")
                continue
            if d.get("path", "") + SUFFIX != rel:
                problems.append(f"pointer names another path: {rel} -> {d.get('path')}")
            if not re.fullmatch(r"[0-9a-f]{64}", str(d.get("sha256", ""))):
                problems.append(f"pointer sha256 malformed: {rel}")
            if not re.fullmatch(r"[0-9a-f]{32}", str(d.get("md5", ""))):
                problems.append(f"pointer md5 missing or malformed (Drive-side check needs it): {rel}")
            if not isinstance(d.get("bytes"), int) or d["bytes"] <= 0:
                problems.append(f"pointer byte count malformed: {rel}")
            else:
                total += d["bytes"]
            if d.get("path") in tracked_set:
                problems.append(f"pointer and its file are both tracked: {rel}")
    gi = rp.REPO / ".gitignore"
    if not gi.is_file() or drive_rules.split_block(gi.read_text(encoding="utf-8-sig"))[1] is None:
        problems.append(".gitignore has no drive-store block (run harness/scripts/drive_store.py pointers)")

    status = "FAIL" if problems else "PASS"
    print(f"drive_pointers: {status} - {pointers} pointer(s), {total / 1048576:,.1f} MB in the Drive store, "
          f"{len(problems)} problem(s)" + ("" if rp.HAS_PROJECT else " (whole repo checked; no project yet)"))
    for p in problems:
        print(f"  {p}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
