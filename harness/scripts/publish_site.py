"""publish_site.py - copy a filed project-portal revision to the presentation site repo and push it, on Bob's go.

TR-09 conflict C-08 (Bob, chat, 2026-10-02). The site repo rp.SITE_REPO (<project>/project.yaml site_repo; checkout
rp.PRESENTATION_SITE, a sibling of this repo) is a publishing target only: generated copies of filed portal
revisions, never a source, record or decision. Nothing in this design repo is written or committed. While the
project has no site (site_repo `unknown`, or no builders in <project>/03_Working_Design/CAD/09_Presentation/;
site_revs.site_dormant) it prints "no presentation site yet" and exits 0, publishing nothing (CPME practice).
The site framework (project tracker, quoting/estimating portal, landing page) is CPME practice and dormant
until Bob defines the job's site. No project yet: it refuses with exit 2.

    1. Refuses unless <project>/06_Issued_Revisions/Portals/project-portal/project-portal-rev<X>/ is filed (rows in revisions.csv, every row's
       sha256 matching the file on disk), the filed folder is committed here, and the site checkout is on main with a
       clean tree.
    2. Large files (.drive pointers in the portal folder and the data store) missing from this checkout are pulled
       first (drive_store.py pull), so real files are copied, never pointers.
    3. The site's content (everything but .git, .gitattributes and README.md) becomes the filed trees. With a
       portal-landing and a quoting-portal revision filed: the landing page portal-landing-rev<L>/ at the root,
       project-portal-rev<X>/ as tracker/, quoting-portal-rev<Q>/ as estimating/ (the Fabrication Estimating
       Portal), and the two shared stores merged as
       data/ beside them, so every page's ../data/ resolves unchanged (a store path held by both with different
       bytes is refused). Without them (or --quoting none): project-portal-rev<X>/ and data/ as filed, plus a root
       index.html that redirects to project-portal-rev<X>/.
       The shared assets each published portal revision lists in its shared-assets.json
       (content-hashed scripts, stylesheet, renders, turntable, drawings) go into the site root's assets/ beside the
       landing page's own, from <project>/06_Issued_Revisions/Portals/<portal>/assets/, so both portals load one copy; and data/ carries
       only what the published pages reach, never a model named in <project>/03_Working_Design/CAD/09_Presentation/site.yaml hidden_models
       (trim_store). Nothing filed is touched.
    4. README.md is rewritten from the template below, its Revisions table carried forward with a new row.
    5. Commits in the site checkout, explicit paths, subject
       "Site: project-portal Rev <X> (model Rev <M>, P&ID Rev <P>)", body naming the design-repo commit, then pushes
       main with gh as the git credential (as track.py does). Needs --bob-go; --dry-run prints the plan and sizes.

    .\\harness\\tools\\venv\\Scripts\\python.exe harness\\scripts\\publish_site.py --rev E --dry-run
    .\\harness\\tools\\venv\\Scripts\\python.exe harness\\scripts\\publish_site.py --rev E --bob-go "<Bob's words>"

--quoting / --landing pick the quoting-portal and portal-landing revisions (default: the newest filed; "none" for
the tracker-only layout).

--as-bob: accepted and ignored since 2026-10-07; gh writes as Bob-Biedrzycki, the one writer (track.py).
Exit 0 = published (or dry run listed); 2 = refused.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists()) / "harness" / "lib"))
import repo_paths as rp  # noqa: E402
if __name__ == "__main__":
    rp.require_project("publish_site.py")   # no project yet: exit 2, no portal to publish
import site_revs  # noqa: E402  (newest filed revision of each published document)

sys.path.insert(0, str(rp.SCRIPTS))
import track as T  # noqa: E402  (gh credential helper, account checks, die; sets GH_CONFIG_DIR for every subprocess)

PY = rp.TOOLS / "venv" / "Scripts" / "python.exe"
PORTAL = rp.PORTAL_FILED
STORE = PORTAL / "data"
QUOTING = rp.QUOTING_FILED   # record ID of the Fabrication Estimating Portal (unchanged)
LANDING = rp.LANDING_FILED
# Mobile Optimized (Bob, chat, 2026-10-17: "a 3rd page selection from home called Mobile Optimized"): mobile-portal
# revisions as mobile/, beside tracker/ and estimating/, once one is filed (closeout.py files it with the tracker)
MOBILE = rp.MOBILE_FILED
MOB = "mobile/"
# site folder of the Fabrication Estimating Portal (Bob 2026-10-05: "Rename Quote portal to Fabrication
# Estimating Portal, would like to use quoting for different purpose in the future")
EST = "estimating/"
KEEP = {".git", ".gitattributes", "README.md"}   # never replaced on the site
GH_HARD_LIMIT = 100 * 2**20                      # GitHub rejects files over 100 MiB
GH_WARN = 50 * 2**20                             # and warns over 50 MiB
SITE_SLUG = rp.SITE_REPO   # <project>/project.yaml site_repo
# project identity for the README and index templates (<project>/project.yaml)
PROJECT_FMT = dict(project_code=rp.PROJECT_CODE, skid_name=rp.PROJECT_INFO["skid_name"], skid_description=rp.PROJECT_INFO["skid_description"],
               customer=rp.CUSTOMER, design_repo=rp.DESIGN_REPO, pid_doc_id=rp.PID_DOC_ID,
               portals=rp.rel(rp.PORTALS), presentations=rp.rel(rp.PRESENTATIONS))   # filed and builder paths, from rp

README6 = """# CPME Project {project_code} — {skid_name} Presentation Site

A static site that presents CPME USA project {project_code}, {skid_description}: a landing
page with the **Fabrication Estimating Portal** (`estimating/`: frame and piping
fabrication tables, plan set and 3D model, issued for estimate), the **Project
Tracker** (`tracker/`: the full project portal) and, once filed, **Mobile Optimized** (`mobile/`:
the tracker for phones, current revision only, mobile-portal{mob_note}).

**Content:** copies of documents filed in the job's repository (`{design_repo}`):
portal-landing **Rev {land}** (`{portals}/portal-landing/portal-landing-rev{land}/`) at the root,
project-portal **Rev {rev}** (`{portals}/project-portal/project-portal-rev{rev}/`) as `tracker/`,
the Fabrication Estimating Portal, filed as quoting-portal **Rev {quote}**
(`{portals}/quoting-portal/quoting-portal-rev{quote}/`), as `estimating/`,
and the portals' shared data stores (`{portals}/*/data/`) merged as `data/`. They present model
`{model}` **Rev {mrev}** and P&ID `{pid_doc_id}` **Rev {prev}**. Published {date} from
design-repo commit `{commit}`.

**The site is generated; do not hand-edit it.** Pages are built from the project records by
`{presentations}/build_portal.py` and `build_landing.py` in the job's repository and
copied here by `harness/scripts/publish_site.py`. To update: rebuild and file the next revisions
there, then republish with that script (one commit per publish).

## Viewing

Serve the folder over HTTP (the 3D viewer and the other revisions need it) and open `index.html`:

```bash
python -m http.server 8765
```

Then browse to http://localhost:8765/. The 3D viewer, fonts and table markdown load three.js,
Google Fonts and marked from public CDNs, so an internet connection is needed.

## Revisions

| Published | Portal revision | Model | P&ID | Design-repo commit | Note |
|---|---|---|---|---|---|
{rows}
"""

README = """# CPME Project {project_code} — {skid_name} Presentation Site

A static site that presents CPME USA project {project_code}, {skid_description} for
{customer}: overview, interactive 3D model, plan set, line register, fabrication tables,
equipment, structure, design reviews, bills of material and decision records.

**Content:** a copy of project-portal **Rev {rev}**, filed in the job's repository
(`{design_repo}`) at `{portals}/project-portal/project-portal-rev{rev}/`, with
the shared portal data store (`{portals}/project-portal/data/`) beside it as `data/`.
It presents model `{model}` **Rev {mrev}** (DRAFT, engineer review pending) and P&ID
`{pid_doc_id}` **Rev {prev}**. Published {date} from design-repo commit `{commit}`.

**The site is generated; do not hand-edit it.** Pages are built from the project records by
`{presentations}/build_portal.py` in the job's repository and copied here by
`harness/scripts/publish_site.py`. To update: rebuild and file the next portal revision there,
then republish it with that script (one commit per published revision).

## Viewing

Serve the folder over HTTP (the 3D viewer and embedded PDFs need it) and open `index.html`,
which forwards to `project-portal-rev{rev}/`:

```bash
python -m http.server 8765
```

Then browse to http://localhost:8765/. The 3D viewer, fonts and table markdown load
three.js, Google Fonts and marked from public CDNs, so an internet connection is needed.

## Revisions

| Published | Portal revision | Model | P&ID | Design-repo commit | Note |
|---|---|---|---|---|---|
{rows}
"""

INDEX = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CPME {project_code} {skid_name}</title>
<meta http-equiv="refresh" content="0; url={target}">
<link rel="canonical" href="{target}">
</head>
<body style="font-family:sans-serif;background:#fff;color:#222">
<p>Generated copy of project-portal Rev {rev}. Continue to <a href="{target}">{target}</a>.</p>
</body>
</html>
"""


def die(msg: str) -> None:
    T.die(msg)


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rcsv(p: Path) -> list[dict]:
    with open(p, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def git(*args: str, cwd: Path, check: bool = True) -> str:
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check and r.returncode != 0:
        die(f"git {' '.join(args)} failed in {cwd}:\n{r.stdout}\n{r.stderr}")
    return r.stdout


def mb(n: int) -> str:
    return f"{n / 2**20:,.1f} MB"


def pointers_under(*roots: Path) -> list[tuple[Path, dict]]:
    """(pointer path, fields) for every <file>.drive under the roots. Pointers are JSON objects written by
    drive_store.py (path, bytes, sha256, md5, mtime, drive_folder, note); a pointer that is not JSON is refused."""
    out = []
    for root in roots:
        for p in sorted(root.rglob("*.drive")):
            try:
                d = json.loads(p.read_text(encoding="utf-8-sig"))
            except ValueError as e:
                die(f"{rp.rel(p)} is not a JSON pointer ({e}); drive_store.py writes pointers, nothing else does")
            if not isinstance(d, dict) or not d.get("sha256") or not d.get("path"):
                die(f"{rp.rel(p)} lacks path or sha256; run drive_store.py pointers")
            out.append((p, d))
    return out


def filed_revision(rev: str) -> tuple[list[dict], str, str, str]:
    """The revisions.csv rows of project-portal Rev <rev> (page files only), and model ID, model rev, P&ID rev."""
    rows = rcsv(PORTAL / "revisions.csv")
    mine = [r for r in rows if r["revision"] == rev and r["file"].startswith(f"project-portal-rev{rev}/")]
    folder = PORTAL / f"project-portal-rev{rev}"
    if not mine or not folder.is_dir():
        die(f"project-portal Rev {rev} is not filed: no project-portal-rev{rev}/ rows in {rp.rel(PORTAL / 'revisions.csv')}"
            f" or no folder {rp.rel(folder)}")
    m = re.match(r"(\S+) Rev (\w+); P&ID Rev (\w+)", mine[0].get("description", ""))
    if not m:
        die(f"cannot read the model and P&ID revisions from the Rev {rev} row description: {mine[0].get('description')!r}")
    return mine, m.group(1), m.group(2), m.group(3)


def newest_filed(root: Path) -> str | None:
    """The last revisions.csv row's letter: the one reader shared with closeout.py and track.py (site_revs)."""
    return site_revs.newest({"doc": root})["doc"]


def docs_for(rev: str, quote: str | None, land: str | None, mob: str | None = None) -> list[tuple[Path, str, str]]:
    """(document root, filed folder name, site prefix) of everything published; the stores are added by source_plan."""
    if quote and land:
        return [(LANDING, f"portal-landing-rev{land}", ""), (PORTAL, f"project-portal-rev{rev}", "tracker/"),
                (QUOTING, f"quoting-portal-rev{quote}", EST)] + ([(MOBILE, f"mobile-portal-rev{mob}", MOB)] if mob else [])
    return [(PORTAL, f"project-portal-rev{rev}", f"project-portal-rev{rev}/")]


def ensure_large_files(dry: bool) -> list[str]:
    """Every pointer under the portal folders / data stores must have its real file here; pull if not."""
    roots = [r for r in (PORTAL, QUOTING, LANDING, MOBILE) if r.is_dir()]
    missing = [d.get("path", "") for p, d in pointers_under(*roots) if not p.with_suffix("").is_file()]
    if not missing:
        return []
    if dry:
        return missing
    print(f"pulling {len(missing)} large file(s) from the Drive store (drive_store.py pull) ...", flush=True)
    r = subprocess.run([str(PY), str(rp.SCRIPTS / "drive_store.py"), "pull"], cwd=rp.REPO, text=True,
                       encoding="utf-8", errors="replace", capture_output=True)
    print("   " + "\n   ".join((r.stdout + r.stderr).strip().splitlines()[-6:]))
    still = [d.get("path", "") for p, d in pointers_under(*roots) if not p.with_suffix("").is_file()]
    if r.returncode != 0 or still:
        die(f"drive_store.py pull exit {r.returncode}; still missing: {', '.join(still[:10]) or 'none'}")
    return []


SHARED_MANIFEST = "shared-assets.json"   # build_portal.py: the shared assets a portal revision uses


def source_plan(docs: list[tuple[Path, str, str]]) -> dict[str, Path]:
    """{site path: source file}: each filed folder under its site prefix, the shared assets each portal revision lists
    in its shared-assets.json (from the portal's asset store <project>/06_Issued_Revisions/Portals/<portal>/assets/, as assets/ at the site root
    beside the landing page's own), and the shared stores (merged as data/), pointers left out. A site
    path held by two sources with different bytes is refused."""
    plan: dict[str, Path] = {}
    for root, folder, prefix in docs:
        for p in sorted((root / folder).rglob("*")):
            if p.is_file() and p.suffix != ".drive":
                k = prefix + p.relative_to(root / folder).as_posix()
                if k in plan and sha256(plan[k]) != sha256(p):
                    die(f"{k} is in two published folders with different bytes ({rp.rel(plan[k])}, {rp.rel(p)}); nothing published")
                plan.setdefault(k, p)
    for root, folder, _ in docs:
        man = root / folder / SHARED_MANIFEST
        if not man.is_file():
            continue
        for name, h in json.loads(man.read_text(encoding="utf-8"))["assets"].items():
            p, k = root / "assets" / name, "assets/" + name
            if not p.is_file():
                if Path(str(p) + ".drive").is_file():
                    continue   # a large file not pulled yet (dry run): ensure_large_files lists it
                die(f"{rp.rel(man)} lists {name}, which is not in {rp.rel(root / 'assets')}; nothing published")
            if k in plan and plan[k] != p and sha256(plan[k]) != sha256(p):
                die(f"{k} is used by two published revisions with different bytes; nothing published")
            plan.setdefault(k, p)
    for root in dict.fromkeys(r for r, _, _ in docs):
        for p in sorted((root / "data").rglob("*")) if (root / "data").is_dir() else []:
            if not p.is_file() or p.suffix == ".drive":
                continue
            k = "data/" + p.relative_to(root / "data").as_posix()
            if k in plan and sha256(plan[k]) != sha256(p):
                die(f"{k} is in two portal data stores with different bytes ({rp.rel(plan[k])}, {rp.rel(p)}); nothing published")
            plan.setdefault(k, p)
    return plan


def trim_store(plan: dict[str, Path], hidden: tuple[str, ...]) -> tuple[dict[str, Path], list[str], list[str]]:
    """The data store as the published pages use it (Bob, 2026-10-08). The filed stores are append-only and keep everything ever filed; the site gets only what the published pages reach:
      - the page maps the tracker's revision picker names (data-pages) and the blocks those maps list
      - the web GLBs (and their base64 copies) named by a published page or a reached block
      - every data/<MODEL-ID>/ bundle except a hidden model's (<project>/03_Working_Design/CAD/09_Presentation/site.yaml hidden_models), and
        index.json, as filed
    build_portal.py leaves a hidden model out of the picker, so a tracker built with the switch on reaches none of its
    page maps, blocks or web GLBs. A published tracker built before the switch still lists them: they stay reachable
    (so its picker never breaks) and the third list names the hidden models it still shows, for a warning.
    Returns (plan, dropped site paths, hidden models the published picker still lists). Nothing filed is touched."""
    pages = [p for k, p in plan.items() if k.endswith(".html") and not k.startswith("data/")]
    text = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in pages)
    maps = set(re.findall(r'data-pages="([0-9a-f]{16})"', text))
    blocks: set[str] = set()
    still: set[str] = set()
    for h in maps:
        f = plan.get(f"data/blocks/{h}.js")
        m = re.match(r"PortalRev\.setPages\((.*)\);\s*$", f.read_text(encoding="utf-8"), re.S) if f else None
        if not m:
            continue
        payload = json.loads(m.group(1))
        if payload.get("model_id") in hidden:
            still.add(payload["model_id"])
        blocks.add(h)
        for pg in payload.get("pages", {}).values():
            blocks.update(b for b in pg.get("blocks", []) if b)
    reached = text + "\n".join(plan[f"data/blocks/{h}.js"].read_text(encoding="utf-8", errors="replace")
                               for h in blocks if f"data/blocks/{h}.js" in plan)
    glbs = set(re.findall(r"glb/([\w.-]+?\.glb(?:\.js)?)(?![\w.-])", reached))
    dropped = []
    for k in list(plan):
        parts = k.split("/")
        if parts[0] != "data" or len(parts) < 3:
            continue
        drop = ((parts[1] in hidden and parts[1] not in still)
                or (parts[1] == "blocks" and parts[2][:-3] not in blocks)
                or (parts[1] == "glb" and parts[2] not in glbs))
        if drop:
            dropped.append(k)
            del plan[k]
    return plan, dropped, sorted(still)


def verify_sources(docs: list[tuple[Path, str, str]], plan: dict[str, Path]) -> list[str]:
    """Filed bytes only: every row of each published revision and every store row (not the regenerated index) must
    hash as recorded, and each large file must match its pointer. Returns warnings; refuses on a mismatch."""
    bad, warn = [], []
    recorded: dict[Path, str] = {}
    for root, folder, _ in docs:
        for r in rcsv(root / "revisions.csv"):
            if r["file"].startswith((folder + "/", "assets/")) or (r["file"].startswith("data/") and r["file"] != "data/index.json"):
                recorded.setdefault(root / r["file"], r["sha256"])
    for p, h in recorded.items():
        if not p.is_file():
            bad.append(f"{rp.rel(p)}: filed but not on disk")
        elif sha256(p) != h:
            bad.append(f"{rp.rel(p)}: sha256 differs from revisions.csv")
    n_ptr = 0
    roots = [root / folder for root, folder, _ in docs] + [root / s for root in dict.fromkeys(r for r, _, _ in docs) for s in ("data", "assets")]
    for ptr, d in pointers_under(*[r for r in roots if r.is_dir()]):
        p = ptr.with_suffix("")
        if not p.is_file():
            bad.append(f"{rp.rel(p)}: pointer present but the file is not (pull did not deliver it)")
        elif sha256(p) != d["sha256"]:
            bad.append(f"{rp.rel(p)}: sha256 differs from its pointer")
        else:
            n_ptr += 1
    warn.append(f"{n_ptr} large file(s) match their Drive pointers")
    unrecorded = [k for k, p in plan.items() if p not in recorded and p.name != "index.json" and not Path(str(p) + ".drive").is_file()]
    if unrecorded:
        warn.append(f"{len(unrecorded)} file(s) in the tree have no revisions.csv row or pointer (copied as is): "
                    + ", ".join(unrecorded[:5]))
    rev = next((f.split("-rev")[-1] for root, f, _ in docs if root == PORTAL), "")
    idx =[r for r in rcsv(PORTAL / "revisions.csv") if r["revision"] == rev and r["file"] == "data/index.json"]
    if idx and (STORE / "index.json").is_file() and sha256(STORE / "index.json") != idx[-1]["sha256"]:
        warn.append("data/index.json differs from the one Rev " + rev + " was built against (the store has grown "
                    "since; it is append-only, so the revision's view is unchanged)")
    if bad:
        die("filed files do not match their records (TR-08); nothing published:\n  " + "\n  ".join(bad[:20]))
    return warn


def site_files(site: Path) -> dict[str, Path]:
    out = {}
    for p in site.rglob("*"):
        rel = p.relative_to(site)
        if rel.parts[0] in KEEP or not p.is_file():
            continue
        out[rel.as_posix()] = p
    return out


def carried_rows(site: Path) -> list[str]:
    """Revisions-table rows from the site's current README, in the 6-column layout."""
    readme = site / "README.md"
    if not readme.is_file():
        return []
    text = readme.read_text(encoding="utf-8")
    sect = text.split("## Revisions", 1)[1] if "## Revisions" in text else ""
    rows = []
    for ln in sect.splitlines():
        cells = [c.strip() for c in ln.strip().strip("|").split("|")] if ln.strip().startswith("|") else []
        if not cells or set("".join(cells)) <= set("-: ") or cells[0] in ("Site commit", "Published"):
            continue
        if len(cells) == 5:   # first layout (hand copy, 2026-10-01): site commit | portal | model | P&ID | note
            cells = ["2026-10-01 (hand copy)", cells[1], cells[2], cells[3], "-", cells[4]]
        rows.append("| " + " | ".join(cells) + " |")
    return rows


def rm(p: Path) -> None:
    try:
        p.unlink()
    except PermissionError:
        os.chmod(p, stat.S_IWRITE)
        p.unlink()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--rev", required=True, help="filed project-portal revision letter")
    ap.add_argument("--dry-run", action="store_true", help="print the file plan and sizes; change nothing")
    ap.add_argument("--bob-go", help="Bob's go, quoted verbatim (required for the real run)")
    ap.add_argument("--as-bob", action="store_true", help="ignored since 2026-10-07 (Bob-Biedrzycki is the writer)")
    ap.add_argument("--site", default=str(rp.PRESENTATION_SITE), help="site checkout (default: sibling of this repo)")
    ap.add_argument("--quoting", help="filed quoting-portal revision (default the newest; 'none': tracker-only layout)")
    ap.add_argument("--landing", help="filed portal-landing revision (default the newest)")
    ap.add_argument("--mobile", help="filed mobile-portal revision, published as mobile/ (default the newest; 'none': "
                                     "no mobile/ folder)")
    a = ap.parse_args()
    why = site_revs.site_dormant()
    if why:   # CPME practice: the framework stays; a project with no site publishes nothing and passes
        print(f"publish_site: {why}; nothing published")
        return 0
    rev, site, dry = a.rev.strip(), Path(a.site), a.dry_run
    T.DRY = dry
    quote = None if (a.quoting or "").lower() == "none" else (a.quoting or newest_filed(QUOTING))
    land = None if quote is None else (a.landing or newest_filed(LANDING))
    six = bool(quote and land)
    mob = None if not six or (a.mobile or "").lower() == "none" else (a.mobile or newest_filed(MOBILE))
    what = (f"project-portal Rev {rev}" + (f", quoting-portal Rev {quote}, portal-landing Rev {land}" if six else "")
            + (f", mobile-portal Rev {mob}" if mob else ""))
    go = None if dry else T.require_go(a.bob_go, f"publishing {what} to the presentation site")

    # 1. filed revisions, design-repo commit, site checkout state
    rows, model, mrev, prev = filed_revision(rev)
    docs = docs_for(rev, quote, land, mob)
    for root, f, _ in docs:
        if not (root / f).is_dir():
            die(f"{rp.rel(root / f)} is not filed")
    folders = [rp.rel(root / f) for root, f, _ in docs]
    commit_warn = ""
    dirty = git("status", "--porcelain", "--", *folders, *[rp.rel(root / "revisions.csv") for root, _, _ in docs], cwd=rp.REPO).strip()
    commits = [git("log", "-1", "--format=%H", "--", f, cwd=rp.REPO).strip() for f in folders]
    if dirty or not all(commits):
        msg = (f"{', '.join(f for f, c in zip(folders, commits) if not c) or 'a filed folder'} is not committed here "
               "(or its revisions.csv has uncommitted changes); publish only committed filed revisions")
        if not dry:
            die(msg)
        commit_warn = msg + " (dry run continues)"
    commit = max((c for c in commits if c), key=lambda c: git("log", "-1", "--format=%ct", c, cwd=rp.REPO).strip(), default="") or "-------"
    commit = commit if all(commits) else "-------"   # dry run only: some folder is not committed yet
    head = git("rev-parse", "HEAD", cwd=rp.REPO).strip()
    folder = folders[0] if not six else ", ".join(folders)
    if not (site / ".git").exists():
        die(f"no site checkout at {site}")
    branch = git("rev-parse", "--abbrev-ref", "HEAD", cwd=site).strip()
    if branch != "main":
        die(f"the site checkout is on {branch}, not main")
    if git("status", "--porcelain", cwd=site).strip():
        die(f"the site checkout {site} has uncommitted changes; it is generated, so nothing there should be hand-edited")
    url = git("remote", "get-url", "origin", cwd=site).strip()
    if SITE_SLUG.lower() not in url.lower():
        die(f"site origin is {url}, not {SITE_SLUG}")
    last = git("log", "-1", "--format=%s", cwd=site).strip()

    # 2. large files present (pull if missing), filed bytes verified
    missing = ensure_large_files(dry)
    plan = source_plan(docs)
    hidden = site_revs.hidden_models()
    store_bytes = sum(p.stat().st_size for k, p in plan.items() if k.startswith("data/"))
    plan, dropped_store, still_shown = trim_store(plan, hidden)
    warns = ([commit_warn] if commit_warn else []) + (verify_sources(docs, plan) if not missing else [])
    kept_store = sum(p.stat().st_size for k, p in plan.items() if k.startswith("data/"))
    warns.append(f"data store: {len(dropped_store)} filed file(s), {mb(store_bytes - kept_store)}, left off the site (not reached by "
                 f"the published pages; hidden models: {', '.join(hidden) or 'none'}, <project>/03_Working_Design/CAD/09_Presentation/site.yaml)")
    if still_shown:
        warns.append(f"project-portal Rev {rev} was built before {', '.join(still_shown)} was hidden and still lists it in the "
                     "revision picker; its files stay published until a tracker built with the switch is filed and published")

    # 3. the site tree: filed trees (+ root redirect in the tracker-only layout) + README
    date = dt.date.today().isoformat()
    target = f"project-portal-rev{rev}/"
    index_html = None if six else INDEX.format(target=target, rev=rev, **PROJECT_FMT)
    label = f"Rev {rev}" + (f" + quoting Rev {quote}, landing Rev {land}" if six else "") + (f", mobile Rev {mob}" if mob else "")
    new_row = f"| {date} | {label} | {model} Rev {mrev} | Rev {prev} | {commit[:7]} | {rows[0].get('notes', '').strip() or '-'} |"
    old_rows = [r for r in carried_rows(site) if f"| Rev {rev} |" not in r or "hand copy" in r]
    fmt = dict(rev=rev, model=model, mrev=mrev, prev=prev, date=date, commit=commit[:7], rows="\n".join(old_rows + [new_row]), **PROJECT_FMT)
    readme = (README6.format(quote=quote, land=land, mob_note=f" **Rev {mob}**" if mob else " not filed yet", **fmt)
              if six else README.format(**fmt))
    current = site_files(site)
    remove = sorted(k for k in current if k not in plan and (six or k != "index.html"))
    add = sorted(k for k in plan if k not in current)
    change = sorted(k for k in plan if k in current and (current[k].stat().st_size != plan[k].stat().st_size
                                                          or sha256(current[k]) != sha256(plan[k])))
    same = len(plan) - len(add) - len(change)
    total = sum(p.stat().st_size for p in plan.values())
    big = sorted(plan.items(), key=lambda kv: kv[1].stat().st_size, reverse=True)
    over = [k for k, p in big if p.stat().st_size > GH_HARD_LIMIT]
    subject = (f"Site: project-portal Rev {rev}, quoting-portal Rev {quote}, landing Rev {land}"
               + (f", mobile Rev {mob}" if mob else "") + f" (model Rev {mrev}, P&ID Rev {prev})"
               if six else f"Site: project-portal Rev {rev} (model Rev {mrev}, P&ID Rev {prev})")

    print(f"publish_site{' (DRY RUN: nothing written, committed or pushed)' if dry else ''}")
    print(f"  source:  {folder} + the shared data store(s) ({model} Rev {mrev}, P&ID Rev {prev})")
    print(f"           design-repo commit {commit[:12]} (HEAD {head[:12]})")
    print(f"  site:    {site} on main, clean; origin {url}; newest commit: {last}")
    if six:
        print(f"  layout:  index.html + assets/ (landing Rev {land}), tracker/ (project-portal Rev {rev}), "
              f"{EST} (Fabrication Estimating Portal, quoting-portal Rev {quote}), "
              + (f"{MOB} (Mobile Optimized, mobile-portal Rev {mob}), " if mob else "") + "data/ (stores merged)")
    print(f"  files:   {len(plan)} filed files, {mb(total)} "
          + (f"(landing {sum(1 for k in plan if not k.startswith(('tracker/', EST, MOB, 'data/')))}, "
             f"tracker {sum(1 for k in plan if k.startswith('tracker/'))}, estimating {sum(1 for k in plan if k.startswith(EST))}, "
             f"mobile {sum(1 for k in plan if k.startswith(MOB))}, "
             if six else f"({sum(1 for k in plan if k.startswith('project-portal-'))} pages/assets, ")
          + f"{sum(1 for k in plan if k.startswith('data/'))} data store), plus {'' if six else 'index.html (redirect) and '}README.md")
    print(f"  vs site: {len(add)} added, {len(change)} changed, {same} unchanged, {len(remove)} removed"
          f" (KEEP: {', '.join(sorted(KEEP))})")
    for k in remove[:12]:
        print(f"           remove {k}")
    if len(remove) > 12:
        print(f"           ... {len(remove) - 12} more removed")
    print("  largest: " + "; ".join(f"{k.split('/')[-1]} {mb(p.stat().st_size)}" for k, p in big[:5]))
    if missing:
        print(f"  large files missing here, would pull first: {len(missing)} ({', '.join(missing[:4])} ...)")
    for w in warns:
        print(f"  note:    {w}")
    if over:
        die(f"file(s) over GitHub's 100 MiB limit: {', '.join(over)}")
    for k, p in big:
        if p.stat().st_size > GH_WARN:
            print(f"  WARNING: {k} is {mb(p.stat().st_size)} (GitHub warns over 50 MiB)")
    print(f"  commit:  \"{subject}\"")
    if dry:
        print(f"\nTo publish (Bob's go): .\\harness\\tools\\venv\\Scripts\\python.exe harness\\scripts\\publish_site.py "
              f"--rev {rev}" + (f" --quoting {quote} --landing {land}" if six else " --quoting none")
              + " --bob-go \"<Bob's words>\"")
        return 0

    # 4. write the site tree (site checkout only)
    T.require_writer()
    T.git_remote("fetch", "origin", "main", cwd=site)
    if git("rev-parse", "HEAD", cwd=site).strip() != git("rev-parse", "origin/main", cwd=site).strip():
        die("the site checkout's main is not at origin/main; nothing written")
    for k in remove:
        rm(site / k)
    for k in add + change:
        dst = site / k
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            rm(dst)
        with open(plan[k], "rb") as fi, open(dst, "wb") as fo:   # bytes only; the filed read-only flag is not copied
            fo.write(fi.read())
    for d in sorted((p for p in site.rglob("*") if p.is_dir() and ".git" not in p.relative_to(site).parts),
                    key=lambda p: len(p.parts), reverse=True):
        if not any(d.iterdir()):
            d.rmdir()
    if index_html is not None:   # tracker-only layout: a redirect; with a landing page, that page is index.html
        (site / "index.html").write_bytes(index_html.encode("utf-8"))
    (site / "README.md").write_bytes(readme.encode("utf-8"))
    for k in plan:   # what was copied is what was filed
        if (site / k).stat().st_size != plan[k].stat().st_size:
            die(f"copy check failed for {k}")
    if list(site.rglob("*.drive")):
        die("a .drive pointer reached the site tree")

    # 5. commit (explicit paths) and push
    paths = sorted(set(remove + add + change + ([] if six else ["index.html"]) + ["README.md"]))
    work = rp.TRACKING
    work.mkdir(parents=True, exist_ok=True)
    pf, mf = work / f"site-rev{rev}-paths.txt", work / f"site-rev{rev}-commit.md"
    pf.write_text("\n".join(paths) + "\n", encoding="utf-8", newline="\n")
    body = [subject, ""] + ([
            f"Generated copies of the filed portal-landing Rev {land} (site root), project-portal Rev {rev} (tracker/)",
            f"and quoting-portal Rev {quote} (the Fabrication Estimating Portal, {EST}), with the portals' shared data",
            "stores merged as data/ so every",
            "page's ../data/ paths resolve. Do not hand-edit; republish instead.", ""] if six else [
            f"Generated copy of the filed project-portal Rev {rev} ({rp.rel(PORTAL)}/project-portal-rev{rev}/)",
            f"and the shared portal data store ({rp.rel(PORTAL)}/data/), laid out as filed so the pages'",
            "../data/ paths resolve; index.html forwards to the portal. Do not hand-edit; republish instead.", ""]) + [
            f"Design repo: {rp.DESIGN_REPO} commit {commit}",
            f"Model: {model} Rev {mrev}; P&ID {rp.PID_DOC_ID} Rev {prev}",
            f"Files: {len(plan)} filed files ({mb(total)}); {len(add)} added, {len(change)} changed, {len(remove)} removed",
            "Basis: TR-09 conflict C-08 (Bob, chat, 2026-10-02); harness/scripts/publish_site.py",
            f"Bob's go: \"{go}\""]
    mf.write_text("\n".join(body) + "\n", encoding="utf-8", newline="\n")
    git("add", "-A", f"--pathspec-from-file={pf}", cwd=site)
    extra = [ln for ln in git("status", "--porcelain", cwd=site).splitlines() if ln[:1] == " " or ln[:2] == "??"]
    if extra:
        die("unstaged changes remain after staging the plan: " + "; ".join(extra[:5]))
    git("commit", "-F", str(mf), cwd=site)
    T.git_remote("push", "origin", "main", cwd=site, write=True)
    local = git("rev-parse", "HEAD", cwd=site).strip()
    remote = T.git_remote("ls-remote", "origin", "refs/heads/main", cwd=site).split()[0]
    clean = not git("status", "--porcelain", cwd=site).strip()
    print(f"\npublished: {subject}\n  site commit {local[:12]}; origin/main {remote[:12]} "
          f"({'matches' if remote == local else 'DOES NOT MATCH'}); tree {'clean' if clean else 'NOT clean'}")
    return 0 if remote == local and clean else 1


if __name__ == "__main__":
    sys.exit(main())
