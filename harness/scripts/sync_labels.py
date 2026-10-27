"""Create or update this repo's GitHub labels from .github/labels.yml.

Requires the GitHub CLI (`gh`) authenticated against the repo (harness/scripts/gh_signin.ps1). Idempotent:
re-running updates colour/description and leaves other labels alone. gh is found, and GH_CONFIG_DIR set,
the same way as track.py does it.
Run from the repository root:  python harness/scripts/sync_labels.py
"""
import subprocess
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import track as T  # noqa: E402  (gh_exe; importing it sets GH_CONFIG_DIR for every subprocess)


def main() -> int:
    path = next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists()) / ".github" / "labels.yml"
    labels = yaml.safe_load(path.read_text(encoding="utf-8"))
    failures = 0
    for label in labels:
        cmd = [
            T.gh_exe(), "label", "create", label["name"],
            "--color", label["color"],
            "--description", label.get("description") or "",
            "--force",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        status = "ok" if result.returncode == 0 else "FAIL"
        print(f"{status:4} {label['name']}")
        if result.returncode:
            failures += 1
            print("     " + result.stderr.strip())
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
