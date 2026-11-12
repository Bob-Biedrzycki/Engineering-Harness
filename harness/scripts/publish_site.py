"""publish_site.py - copy filed portal revisions to the presentation site repo as the day's publish branch.

A separate folder and repo (Bob, chat, 2026-10-02). The site repo rp.SITE_REPO (<project>/project.yaml site_repo; checkout
rp.PRESENTATION_SITE, a sibling of this repo) is a publishing target only: generated copies of filed portal
revisions, never a source, record or decision. Nothing in this design repo is written or committed. While the
project has no site (site_repo `unknown`, or no builders in <project>/03_Working_Design/CAD/09_Presentation/;
site_revs.site_dormant) it prints "no presentation site yet" and exits 0, publishing nothing (CPME practice).
No project yet: it refuses with exit 2. Skill: .claude/skills/site-publish.

Every site is the project tracker, its landing page and Mobile Optimized. A project whose builders also make the
Fabrication Estimating Portal (record ID quoting-portal) or the customer site (customer-portal) publishes those too
(site_revs.portals(), the one test of which portals a project has). A project without them takes --quoting none
(site_revs.publish_args always passes it) and refuses any other value, and has no customer/ folder.

The publish is a daily branch (Bob, chat, 2026-11-09: "change publish_site.py to push to a daily branch in the site
repo. Then your merge is the publish, which settles the trigger question with no special exception. It also needs
to stop using git add -A."). A real run commits on daily/<YYYY-MM-DD> in the site repo and pushes that branch only;
its merge into the site's main, on Bob's end-of-day word, is the publish.

    1. Refuses unless <project>/06_Issued_Revisions/Portals/project-portal/project-portal-rev<X>/ is filed (rows in
       revisions.csv, every row's sha256 matching the file on disk), every file under the published filed folders
       (and each revisions.csv) is saved byte for byte on the design repo's origin/daily/<date> or origin/main
       (saved_on: saves go to the day's branch from a worktree, so the checkout's HEAD is not the test), and the site
       checkout is on main with a clean tree (it is never written or moved).
    1b. Upstream commits: fetches origin main in the site checkout and names every commit on origin/main since the last
       publish (a "Site: ..." commit or the merge of a daily/<date> branch), each marked KEEP-only or TOUCHES
       PUBLISHED CONTENT. KEEP-only commits (.github/**, .gitattributes, README.md) are carried: the branch is built on
       origin/main. One outside KEEP refuses (the publish would overwrite it). Dry run: listed, a fetch failure is a
       WARNING. Never a reset, rebase, force or merge. The branch builds on origin/daily/<date> when an earlier
       publish today is not merged yet (it must contain origin/main), else on origin/main.
    2. Large files (.drive pointers in the portal folders and the data stores) missing from this checkout are pulled
       first (drive_store.py pull), so real files are copied, never pointers.
    3. The site's content (everything but KEEP) becomes the filed trees. With a portal-landing revision filed: the
       landing page portal-landing-rev<L>/ at the root, project-portal-rev<X>/ as tracker/, quoting-portal-rev<Q>/ as
       estimating/ (projects with the Fabrication Estimating Portal), mobile-portal-rev<M>/ as mobile/ once one is
       filed, customer-portal-rev<C>/ as customer/ (projects with the customer site, once Bob files one), and the
       shared stores merged as data/ beside them, so every page's ../data/ resolves unchanged (a store path held by two
       with different bytes is refused). Without a landing page (or --landing none): project-portal-rev<X>/ and data/
       as filed, plus a root index.html that redirects to project-portal-rev<X>/.
       The shared assets each published portal revision lists in its shared-assets.json (content-hashed scripts,
       stylesheet, renders, turntable, drawings) go into the site root's assets/ beside the landing page's own, from
       <project>/06_Issued_Revisions/Portals/<portal>/assets/, so the portals load one copy; and data/ carries only
       what the published pages reach, never a model named in <project>/03_Working_Design/CAD/09_Presentation/site.yaml
       hidden_models (trim_store). Nothing filed is touched.
    4. README.md is rewritten from the template below, its Revisions table carried forward with a new row.
    4b. The site repo's packager as a check: the tree this publish leaves (plan + README.md) is staged as a scratch copy
       under <project>/_work/site-check/stage/ and the site's own .github/packaging/package_portals.py runs on it,
       unchanged, as the site's workflow runs it: python -I <script> --site <stage> --out <project>/_work/site-check/
       packages/ (the publish base's copy of the script). Its summary lines are printed. Dry run: a failure is
       "WARNING site packaging". Real run: a failure stops before anything is written, committed or pushed. No script
       in the site repo: a warning, and the publish goes on.
    4c. Publish notes: this publish is compared with the last one (the live site, origin/main; its publish-notes.json,
       else its README and tree): model and P&ID, the portals and their letters, top-level folders, files added /
       changed / removed, the upstream commits taken, the packager result. Anomalies (find_anomalies; CODES gives each
       code's severity) go in the commit message as a "Notes for packaging" section after the subject ("No
       anomalies." when none) and in publish-notes.json at the site root (schema NOTES_SCHEMA, documented above
       build_notes), rewritten every publish, never KEEP, never in the plan or the file counts. The dry run prints both
       exactly as they would be written, plus "packaging note:" summary lines that closeout.py carries into the go.
    5. Commits in a short-lived detached worktree of the site repo beside its checkout (publish_branch), staging by
       explicit path (git rm for removals, git add for the rest, never -A), subject
       "Site: project-portal Rev <X> (model Rev <M>, P&ID Rev <P>)", body naming the design-repo commit, then pushes
       HEAD:refs/heads/daily/<date> (never main, never forced) with gh as the git credential (as track.py does), and
       removes the worktree.

    .\\harness\\tools\\venv\\Scripts\\python.exe harness\\scripts\\publish_site.py --rev E --dry-run
    .\\harness\\tools\\venv\\Scripts\\python.exe harness\\scripts\\publish_site.py --rev E --quoting none --landing D --mobile B

--landing / --mobile pick the portal-landing and mobile-portal revisions (default: the newest filed; "none" for the
tracker-only layout, or no mobile/). --quoting picks the quoting-portal revision on a project with the estimating
portal (default the newest filed; "none" leaves estimating/ out); elsewhere only "none" is accepted. --customer picks
the customer-portal revision on a project with the customer site (default the newest filed; "none" leaves customer/
out); a dry run may name one not filed yet (shown in the layout, left out of the file plan); the real run refuses.

--bob-go: optional since the publish became a daily branch (its end-of-day merge is the publish); when given it is
recorded in the site commit body. --as-bob: accepted and ignored since 2026-10-07 (gh writes as Bob-Biedrzycki).
Exit 0 = pushed (or dry run listed, or no site yet); 2 = refused.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists()) / "harness" / "lib"))
import repo_paths as rp  # noqa: E402
if __name__ == "__main__":
    rp.require_project("publish_site.py")   # no project yet: exit 2, no portal to publish
import site_revs  # noqa: E402  (newest filed revision of each published document; the portals the project has)

sys.path.insert(0, str(rp.SCRIPTS))
import track as T  # noqa: E402  (gh credential helper, account checks, die; sets GH_CONFIG_DIR for every subprocess)

PY = rp.TOOLS / "venv" / "Scripts" / "python.exe"
PORTAL = rp.PORTAL_FILED
STORE = PORTAL / "data"
LANDING = rp.LANDING_FILED
# Mobile Optimized (Bob, chat, 2026-10-17: "a 3rd page selection from home called Mobile Optimized"): mobile-portal
# revisions as mobile/, beside tracker/, once one is filed (closeout.py files it with the tracker)
MOBILE = rp.MOBILE_FILED
MOB = "mobile/"
# the Fabrication Estimating Portal (record ID quoting-portal) as estimating/, on a project whose builders make it
QUOTING = rp.QUOTING_FILED
EST = "estimating/"
# the customer site (customer-portal) as customer/, on a project whose builders make it, once Bob files one; reached by
# its direct link (or an unlabeled landing tile); its pages carry robots noindex
CUSTOMER = rp.CUSTOMER_FILED
CUS = "customer/"
# never replaced on the site; .github holds the site repo's own packaging workflow
KEEP = {".git", ".gitattributes", "README.md", ".github"}
# the publish notes, rewritten by every publish at the site root, so it is not KEEP (an upstream commit touching it is
# published content and refuses); it is never part of the plan and never counted as added, changed or removed, and no
# page links it, so the site's packager does not take it
NOTES_FILE = "publish-notes.json"
GH_HARD_LIMIT = 100 * 2**20                      # GitHub rejects files over 100 MiB
GH_WARN = 50 * 2**20                             # and warns over 50 MiB
SITE_SLUG = rp.SITE_REPO   # <project>/project.yaml site_repo
# project identity for the README and index templates (<project>/project.yaml)
PROJECT_FMT = dict(project_code=rp.PROJECT_CODE, skid_name=rp.PROJECT_INFO["skid_name"], skid_description=rp.PROJECT_INFO["skid_description"],
               customer=rp.CUSTOMER, design_repo=rp.DESIGN_REPO, pid_doc_id=rp.PID_DOC_ID,
               portals=rp.rel(rp.PORTALS), presentations=rp.rel(rp.PRESENTATIONS))   # filed and builder paths, from rp

README6 = """# CPME Project {project_code} — {skid_name} Presentation Site

A static site that presents CPME USA project {project_code}, {skid_description}: a landing
page with {est_intro}the **Project Tracker** (`tracker/`: the full project portal) and, once filed, **Mobile
Optimized** (`mobile/`: the tracker for phones, current revision only, mobile-portal{mob_note}).{cus_intro}

**Content:** copies of documents filed in the job's repository (`{design_repo}`):
portal-landing **Rev {land}** (`{portals}/portal-landing/portal-landing-rev{land}/`) at the root,
project-portal **Rev {rev}** (`{portals}/project-portal/project-portal-rev{rev}/`) as `tracker/`,
{est_content}and the portals' shared data stores (`{portals}/*/data/`) merged as `data/`. They present model
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
# the estimating and customer sentences of README6, only on a project that publishes them (empty otherwise, so a
# project with the tracker, landing page and Mobile Optimized only gets the README it always had)
README6_EST_INTRO = ("the **Fabrication Estimating Portal** (`estimating/`: fabrication tables, plan set and 3D\n"
                     "model, issued for estimate), ")
README6_EST_CONTENT = ("the Fabrication Estimating Portal, filed as quoting-portal **Rev {quote}**\n"
                       "(`{portals}/quoting-portal/quoting-portal-rev{quote}/`), as `estimating/`,\n")
README6_CUS_INTRO = (" Once filed, the **customer\nsite** (`customer/`: drawings, 3D model and renders issued for review, "
                     "customer-portal{cus_note}) is\npublished too; it is reached by its direct link.")

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


def filed_revision(rev: str) -> tuple[list[dict], str, str, str, str]:
    """The revisions.csv rows of project-portal Rev <rev> (page files only), and model ID, model rev, P&ID rev, P&ID
    number. build_portal.py writes "<MODEL-ID> Rev <X>; P&ID <PID-DOC-ID> Rev <Y>"; a row without the P&ID number
    is read as the project's pid_doc_id."""
    rows = rcsv(PORTAL / "revisions.csv")
    mine = [r for r in rows if r["revision"] == rev and r["file"].startswith(f"project-portal-rev{rev}/")]
    folder = PORTAL / f"project-portal-rev{rev}"
    if not mine or not folder.is_dir():
        die(f"project-portal Rev {rev} is not filed: no project-portal-rev{rev}/ rows in {rp.rel(PORTAL / 'revisions.csv')}"
            f" or no folder {rp.rel(folder)}")
    m = re.match(r"(\S+) Rev (\w+); P&ID (?:(\S+) )?Rev (\w+)", mine[0].get("description", ""))
    if not m:
        die(f"cannot read the model and P&ID revisions from the Rev {rev} row description: {mine[0].get('description')!r}")
    return mine, m.group(1), m.group(2), m.group(4), m.group(3) or rp.PID_DOC_ID


def newest_filed(root: Path) -> str | None:
    """The last revisions.csv row's letter: the one reader shared with closeout.py and track.py (site_revs)."""
    return site_revs.newest({"doc": root})["doc"]


def docs_for(rev: str, land: str | None, mob: str | None = None, quote: str | None = None,
             cus: str | None = None) -> list[tuple[Path, str, str]]:
    """(document root, filed folder name, site prefix) of everything published, in site order; the stores are added
    by source_plan. Without a landing page: the tracker alone at its filed name (the others need the landing layout)."""
    if land:
        return ([(LANDING, f"portal-landing-rev{land}", ""), (PORTAL, f"project-portal-rev{rev}", "tracker/")]
                + ([(QUOTING, f"quoting-portal-rev{quote}", EST)] if quote else [])
                + ([(MOBILE, f"mobile-portal-rev{mob}", MOB)] if mob else [])
                + ([(CUSTOMER, f"customer-portal-rev{cus}", CUS)] if cus else []))
    return [(PORTAL, f"project-portal-rev{rev}", f"project-portal-rev{rev}/")]


def ensure_large_files(dry: bool) -> list[str]:
    """Every pointer under the portal folders / data stores must have its real file here; pull if not."""
    roots = [r for r in (PORTAL, LANDING, MOBILE, QUOTING, CUSTOMER) if r.is_dir()]
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
    """Published files in a site checkout (KEEP paths and the notes file left out)."""
    out = {}
    for p in site.rglob("*"):
        rel = p.relative_to(site)
        if rel.parts[0] in KEEP or rel.as_posix() == NOTES_FILE or not p.is_file():
            continue
        out[rel.as_posix()] = p
    return out


def base_blobs(site: Path, ref: str) -> dict[str, str]:
    """Published files in a site commit, path -> blob (KEEP paths and the notes file left out, as site_files does)."""
    out = {}
    for e in git("ls-tree", "-r", "-z", ref, cwd=site).split("\0"):
        if e:
            meta, path = e.split("\t", 1)
            if path.split("/", 1)[0] in KEEP or path == NOTES_FILE:
                continue
            out[path] = meta.split(" ")[2]
    return out


def plan_blobs(site: Path, plan: dict[str, Path]) -> dict[str, str]:
    """site path -> the blob each planned file would be, hashed in the site repo (`* -text`: byte for byte)."""
    keys = sorted(plan)
    if not keys:
        return {}
    r = subprocess.run(["git", "hash-object", "--stdin-paths", "--no-filters"], cwd=site,
                       input="\n".join(str(plan[k]) for k in keys) + "\n", capture_output=True, text=True,
                       encoding="utf-8")
    if r.returncode != 0:
        die(f"git hash-object failed in the site checkout: {r.stderr.strip()}")
    return dict(zip(keys, r.stdout.split()))


def carried_rows(site: Path, text: str | None = None) -> list[str]:
    """Revisions-table rows from a site README (the publish base's text when given, else the checkout's file), in the
    6-column layout."""
    if text is None:
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


# ------------------------------------------------------------------ the site checkout vs origin (upstream commits)
# The site repo's owners may push their own commits (for example the packaging workflow under .github/). The dry run
# names every upstream commit since the last publish; the publish branch, built on origin/main, carries commits that
# touch only KEEP paths; one that touches published content refuses; and the site's own packager runs on the staged
# tree before a push.

def keep_path(path: str) -> bool:
    """A site path publish_site.py never replaces (KEEP: .github/**, .gitattributes, README.md)."""
    top = path.replace("\\", "/").split("/", 1)[0]
    return top in KEEP and top != ".git"


def checkout_refusal(site: Path, slug: str | None = None) -> str | None:
    """Why the site checkout cannot be published from (no checkout, not on main, uncommitted changes, wrong origin), or
    None."""
    slug = SITE_SLUG if slug is None else slug
    if not (site / ".git").exists():
        return f"no site checkout at {site}"
    branch = git("rev-parse", "--abbrev-ref", "HEAD", cwd=site).strip()
    if branch != "main":
        return f"the site checkout is on {branch}, not main"
    if git("status", "--porcelain", cwd=site).strip():
        return f"the site checkout {site} has uncommitted changes; it is generated, so nothing there should be hand-edited"
    url = git("remote", "get-url", "origin", cwd=site).strip()
    if slug.lower() not in url.lower():
        return f"site origin is {url}, not {slug}"
    return None


def fetch_site(site: Path) -> str | None:
    """git fetch origin main in the site checkout, with gh as the credential (as track.git_remote). Returns the error
    text, or None. Fetch writes only the site's remote-tracking ref, never its branch or files."""
    exe = shutil.which("gh") or (str(T.GH_FALLBACK) if T.GH_FALLBACK.exists() else None)
    cred = ["-c", "credential.https://github.com.helper=",
            "-c", "credential.https://github.com.helper=!" + exe.replace("\\", "/") + " auth git-credential"] if exe else []
    r = subprocess.run(["git", *cred, "fetch", "origin", "main"], cwd=site, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return None if r.returncode == 0 else T.mask((r.stderr or r.stdout or f"exit {r.returncode}").strip())


def log_commits(site: Path, rng: str) -> list[dict]:
    """Each commit in a git log range, newest first, as {hash, author, date, subject, files, outside}; outside = its
    files that are not KEEP paths. A merge commit lists its diff against its first parent; renames are a delete plus
    an add."""
    log = git("log", "--no-renames", "--name-only", "--diff-merges=first-parent", "--date=short",
              "--format=%x1e%H%x1f%an%x1f%ad%x1f%s", rng, cwd=site)
    commits = []
    for rec in log.split("\x1e")[1:]:
        lines = rec.strip("\n").splitlines()
        h, author, date, subject = lines[0].split("\x1f", 3)
        files = [ln.strip() for ln in lines[1:] if ln.strip()]
        commits.append({"hash": h, "author": author, "date": date, "subject": subject, "files": files,
                        "outside": [f for f in files if not keep_path(f)]})
    return commits


def upstream(site: Path) -> dict:
    """Commits on origin/main (as last fetched) made after the last publish there (commits_since_last_publish: a
    "Site: ..." commit, or the merge of a daily/<date> publish branch), each as log_commits gives it. The site
    checkout's own main is not the reference: publishes reach main only through a merge, so the checkout may lag
    until it is synced."""
    if not git("rev-parse", "--verify", "--quiet", "refs/remotes/origin/main", cwd=site, check=False).strip():
        return {"commits": [], "error": "the site checkout has no origin/main ref"}
    return {"commits": [c | {"outside": [f for f in c["files"] if not keep_path(f)]}
                        for c in commits_since_last_publish(site, "origin/main")]}


def sync_decision(state: dict) -> tuple[str, str]:
    """("level" | "based" | "refuse", why). The publish branch is built on origin/main, so commits there since the last
    publish that touch only KEEP paths are simply carried ("based"); one that touches published content would be
    overwritten by this publish, so it refuses until Bob decides with the site repo's owners. Never a reset, rebase,
    force or merge."""
    cs = state["commits"]
    if not cs:
        return "level", "no upstream commits (origin/main is the last publish)"
    bad = [c for c in cs if c["outside"]]
    if bad:
        return "refuse", ("origin/main has commit(s) since the last publish that touch published content, which this "
                          "publish would overwrite; nothing written. Bob decides with the site repo's owners: "
                          + "; ".join(f"{c['hash'][:7]} {c['author']} ({', '.join(c['outside'][:4])}"
                                      + (" ..." if len(c["outside"]) > 4 else "") + ")" for c in bad))
    return "based", (f"origin/main has {len(cs)} commit(s) since the last publish, each touching only KEEP paths "
                     f"({', '.join(sorted(KEEP - {'.git'}))}); the publish branch is built on them")


def upstream_lines(state: dict) -> list[str]:
    """The lines naming each upstream commit (Bob sees them before he merges the publish branch)."""
    cs = state["commits"]
    if not cs:
        return []
    out = [f"upstream: origin/main has {len(cs)} commit(s) since the last publish:"]
    for c in cs:
        kind = ("KEEP-only (" + ", ".join(c["files"][:6]) + (" ..." if len(c["files"]) > 6 else "") + ")"
                if not c["outside"] else
                "TOUCHES PUBLISHED CONTENT (" + ", ".join(c["outside"][:6]) + (" ..." if len(c["outside"]) > 6 else "") + ")")
        out.append(f"          {c['hash'][:7]} {c['author']} {c['date']} \"{c['subject']}\": {kind}")
    return out


def sync_site(site: Path, dry: bool) -> tuple[list[str], str]:
    """Fetch origin main and report the upstream commits since the last publish. Returns the lines for the summary and
    the decision (level, based, refuse; unknown when not checked). Never moves the site checkout's branch or files.
    Dry run: a fetch failure is a WARNING line, a refusal is reported. Real run: a fetch failure or a refusal stops
    before anything is written."""
    err = fetch_site(site)
    if err:
        if not dry:
            die(f"git fetch origin main failed in the site checkout; nothing written:\n{err}")
        return [f"WARNING upstream: git fetch origin main failed ({err.splitlines()[-1] if err else 'no output'}); "
                "upstream commits not checked (dry run continues)"], "unknown"
    state = upstream(site)
    if state.get("error"):
        if not dry:
            die(state["error"] + "; nothing written")
        return [f"WARNING upstream: {state['error']} (dry run continues)"], "unknown"
    action, why = sync_decision(state)
    lines = upstream_lines(state) + [f"upstream: {why}" if action != "refuse" else f"WARNING upstream: a real publish REFUSES: {why}"]
    if not dry and action == "refuse":
        die(why + ("\n  " + "\n  ".join(lines[:-1]) if len(lines) > 1 else ""))
    return lines, action


# ------------------------------------------------------------------ the publish is a daily branch (Bob, 2026-11-09)
# The real run commits in a short-lived detached worktree of the site repo (the site checkout itself is never written,
# switched or moved), stages by explicit path, and pushes HEAD to daily/<date> only. The site's main changes only when
# that branch is merged, on Bob's end-of-day word.
DAILY_PREFIX = "daily/"


def daily_ref(date: str) -> str:
    """refs/heads/daily/<YYYY-MM-DD>, the only ref a real publish pushes; refuses anything else (never main)."""
    try:
        dt.date.fromisoformat(date)
    except (TypeError, ValueError):
        die(f"--date must be YYYY-MM-DD, got {date!r}")
    ref = f"refs/heads/{DAILY_PREFIX}{date}"
    if not ref.startswith("refs/heads/daily/") or ref.endswith("/main"):
        die(f"publish pushes only to daily/<date>, never {ref}")
    return ref


def push_refspec(date: str) -> str:
    """HEAD:refs/heads/daily/<date>, never forced (no leading +), never main."""
    spec = f"HEAD:{daily_ref(date)}"
    if spec.startswith("+") or spec.split(":", 1)[1] in ("refs/heads/main", "main"):
        die(f"refusing push refspec {spec}")
    return spec


def fetch_site_daily(site: Path, date: str) -> bool:
    """Fetch origin's daily/<date> into refs/remotes/origin/daily/<date> when it exists (an earlier publish today that
    is not merged). True when it exists. Writes only that remote-tracking ref."""
    branch = f"{DAILY_PREFIX}{date}"
    if not T.git_remote("ls-remote", "--heads", "origin", branch, cwd=site).strip():
        return False
    T.git_remote("fetch", "origin", f"refs/heads/{branch}:refs/remotes/origin/{branch}", cwd=site)
    return True


def is_ancestor(site: Path, a: str, b: str) -> bool:
    return subprocess.run(["git", "merge-base", "--is-ancestor", a, b], cwd=site).returncode == 0


def publish_base(site: Path, date: str, daily_exists: bool) -> str:
    """The commit the day's publish builds on, so the push to daily/<date> is always a plain fast-forward:
    - no daily/<date> on origin yet: origin/main;
    - daily/<date> waiting for its merge (it contains origin/main): origin/daily/<date>;
    - daily/<date> already merged into main with a merge commit (it is an ancestor of origin/main): origin/main;
    - neither (squash- or rebase-merged, or main moved past it some other way): refuse and say so, never guess."""
    if not daily_exists:
        return "origin/main"
    ref = f"origin/{DAILY_PREFIX}{date}"
    if is_ancestor(site, "origin/main", ref):
        return ref
    if is_ancestor(site, ref, "origin/main"):
        return "origin/main"
    die(f"{ref} and origin/main have diverged: the earlier publish branch today is neither waiting to be merged nor "
        "merged with a merge commit (a squash or rebase merge, or main moved some other way). Nothing written. Bob "
        f"deletes {DAILY_PREFIX}{date} in the site repo on GitHub (its content is on main if it was merged), then "
        "publish again")


def stage_explicit(wt: Path, written: list[str], removed: list[str], pathspec_dir: Path) -> None:
    """Stage by explicit path, never `git add -A` (Bob, 2026-11-09): `git rm` for each removed file, `git add` for each
    written one, each list from a pathspec file (a publish can exceed the Windows command-line limit)."""
    pathspec_dir.mkdir(parents=True, exist_ok=True)
    if removed:
        rf = pathspec_dir / "site-remove-paths.txt"
        rf.write_text("\n".join(removed) + "\n", encoding="utf-8", newline="\n")
        git("rm", "--quiet", "--cached", "--ignore-unmatch", f"--pathspec-from-file={rf}", cwd=wt)
    if written:
        af = pathspec_dir / "site-add-paths.txt"
        af.write_text("\n".join(written) + "\n", encoding="utf-8", newline="\n")
        git("add", f"--pathspec-from-file={af}", "--", cwd=wt)


# ------------------------------------------------------------------ filed folders saved on the design repo's origin
def disk_files(folders: list[str]) -> list[str]:
    """Files under the filed folders that git would keep (tracked or untracked, not ignored) and that exist on disk.
    Large files are ignored (Drive store); their .drive pointers are listed."""
    out = git("ls-files", "-z", "-co", "--exclude-standard", "--", *folders, cwd=rp.REPO)
    return sorted({p for p in out.split("\0") if p and (rp.REPO / p).is_file()})


def blobs_at(ref: str, folders: list[str]) -> dict[str, str]:
    """path -> blob hash under the folders in `ref` (empty when the ref is missing)."""
    out = git("ls-tree", "-r", "-z", "--full-tree", ref, "--", *folders, cwd=rp.REPO, check=False)
    res = {}
    for e in out.split("\0"):
        if e:
            meta, path = e.split("\t", 1)
            res[path] = meta.split(" ")[2]
    return res


def disk_blobs(paths: list[str]) -> dict[str, str]:
    if not paths:
        return {}
    r = subprocess.run(["git", "hash-object", "--stdin-paths"], cwd=rp.REPO, input="\n".join(paths) + "\n",
                       capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        die(f"git hash-object failed: {r.stderr.strip()}")
    return dict(zip(paths, r.stdout.split()))


def saved_on(folders: list[str], refs: list[str]) -> tuple[str | None, str]:
    """Every file under the published filed folders (each with its document's revisions.csv) is saved, byte for byte,
    on one of `refs` (origin/daily/<today>, then origin/main): the same set of paths and the same blob for each.
    Returns (the first ref that matches, why not when none does). The design repo's shared checkout stays on main
    while saves go to daily/<date> from a worktree (global "Git and backup"), so HEAD is not the test."""
    disk = disk_blobs(disk_files(folders))
    if not disk:
        return None, "no files found under the filed folders"
    whys = []
    for ref in refs:
        if not git("rev-parse", "--verify", "--quiet", ref, cwd=rp.REPO, check=False).strip():
            whys.append(f"{ref}: no such ref")
            continue
        at = blobs_at(ref, folders)
        missing = sorted(set(disk) - set(at))
        extra = sorted(set(at) - set(disk))
        differ = sorted(p for p in disk if p in at and at[p] != disk[p])
        if not (missing or extra or differ):
            return ref, ""
        whys.append(f"{ref}: {len(missing)} not saved, {len(differ)} different, {len(extra)} only there"
                    + (f" (e.g. {(missing or differ or extra)[0]})"))
    return None, "; ".join(whys)


# ------------------------------------------------------------------ the site repo's packager, run as a check
PACKAGER = Path(".github") / "packaging" / "package_portals.py"   # in the site repo; run unchanged, never imported


def reset_scratch(d: Path) -> Path:
    """An empty scratch folder under <project>/_work/ (refuses any other place, so the site checkout is never written)."""
    d = d.resolve()
    if not d.is_relative_to(rp.WORK.resolve()):
        die(f"scratch folder {d} is not under {rp.WORK}")
    if d.exists():
        shutil.rmtree(d, onexc=lambda f, p, e: (os.chmod(p, stat.S_IWRITE), f(p)))
    d.mkdir(parents=True)
    return d


def stage_tree(plan: dict[str, Path], extra: dict[str, bytes], dest: Path) -> Path:
    """A scratch copy of the site as this publish would leave it (the plan's files, bytes only, plus README.md and the
    root redirect when there is one), for the site's packager. Never written into the site checkout."""
    dest = reset_scratch(dest)
    for k, src in plan.items():
        dst = dest / k
        dst.parent.mkdir(parents=True, exist_ok=True)
        with open(src, "rb") as fi, open(dst, "wb") as fo:
            shutil.copyfileobj(fi, fo, 1 << 20)
    for k, b in extra.items():
        (dest / k).write_bytes(b)
    return dest


def site_packaging(script: Path, tree: Path, out: Path, timeout: int = 900) -> tuple[str, list[str]]:
    """Run the site repo's package_portals.py exactly as its workflow does (--site <tree> --out <out>, every portal),
    with python -I so nothing of ours or the site's is imported into the other. ("pass" | "fail" | "missing", lines)."""
    if not script.is_file():
        return "missing", [f"{script} is not in the site repo; the site's packaging not checked"]
    out = reset_scratch(out)
    env = dict(os.environ, GIT_CEILING_DIRECTORIES=str(tree.parent))   # the staged tree is not a repo; never find ours
    try:
        r = subprocess.run([sys.executable, "-I", str(script), "--site", str(tree), "--out", str(out)], cwd=out, env=env,
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        return "fail", [f"package_portals.py did not finish in {timeout} s"]
    lines = [ln.rstrip() for ln in ((r.stdout or "") + (r.stderr or "")).splitlines() if ln.strip()]
    return ("pass" if r.returncode == 0 else "fail"), [f"package_portals.py exit {r.returncode}"] + lines


# ------------------------------------------------------------------ publish notes on every publish
# Every publish compares itself with the last one (origin/main, the live site) and says, through the site repo itself,
# what is unusual: a "Notes for packaging" section in the site commit message and publish-notes.json at the site root.
#
# publish-notes.json, schema NOTES_SCHEMA (one JSON object, keys in this order, rewritten whole by every publish):
#   schema           "cpme-site-publish-notes/2"  (/1, written before 2026-11-10, named the packager fields by person)
#   written_by       "harness/scripts/publish_site.py"
#   published_at     local time, ISO 8601 with offset, seconds
#   design_repo      {repo, commit}                     the design-repo commit the filed revisions come from
#   site             {repo, parent_commit}              the site commit this publish is made on (its base)
#   model, pid       {id, revision}
#   portals          [{document, revision, folder}]     in site order; folder "" is the site root (landing page)
#   top_folders      [str]                              the site's top-level folders after this publish
#   files            {total, bytes, by_folder{folder: n}, added, changed, removed, unchanged,
#                     removed_paths[<= NOTES_PATHS_MAX], removed_paths_truncated}; "(root)" counts root files;
#                     README.md, .github/, .gitattributes and this file are not counted
#   upstream_commits [{hash, author, date, subject, files}]   site commits since the last publish that are not
#                     publishes, carried by the publish branch; [] when none
#   packager         {status pass|fail|missing|skipped, exit_code int|null, script, packager_portals[],
#                     packager_portals_source, warnings[], portals{<folder>: {revision, files, links_out[],
#                     unresolved_count, unresolved_shown[]}}, new_since_last {links_out[]|null, unresolved int|null}}
#                     (null = not known)
#   previous         {source, site_commit, model, pid, portals}   the last publish as read ("publish-notes.json" or
#                     "README.md and tree" for a publish that carried no notes)
#   anomalies        [{code, severity info|warn, message, details}]   [] = no anomalies
NOTES_SCHEMA = "cpme-site-publish-notes/2"
NOTES_KEYS = ("schema", "written_by", "published_at", "design_repo", "site", "model", "pid", "portals", "top_folders",
              "files", "upstream_commits", "packager", "previous", "anomalies")
NOTES_PATHS_MAX = 50
# document ID -> site folder, in site order ("" = the site root); the tracker-only layout is project-portal-rev<X>/
DOC_FOLDER = {"portal-landing": "", "project-portal": "tracker/", "quoting-portal": EST, "mobile-portal": MOB,
              "customer-portal": CUS}
SUPPORT_FOLDERS = {"assets", "data"}   # shared stores the site's packager follows references into
# Unusually large removals. Every publish removes many files from the shared stores assets/ and data/ (content-hashed
# scripts and renders replaced, the store trimmed), so a flat "more than 50 files" would fire every time. Two rules:
#   a page folder (the landing root, tracker/, estimating/, mobile/, customer/) loses more than 25% of the files it had
#   and at least 3 files;
#   the whole site loses more than 25% of its files and shrinks by more than 10% net (removed less added).
REMOVAL_FOLDER_SHARE, REMOVAL_FOLDER_MIN = 0.25, 3
REMOVAL_SITE_SHARE, REMOVAL_SITE_NET = 0.25, 0.10
CODES = {   # code: severity
    "MODEL_ID_CHANGED": "warn", "MODEL_REV_BACKWARDS": "warn", "PID_ID_CHANGED": "info",
    "PORTAL_ADDED": "info", "PORTAL_REMOVED": "warn", "REV_SKIPPED": "warn", "REV_BACKWARDS": "warn",
    "CUSTOMER_LEFT_OUT": "warn", "UPSTREAM_COMMITS": "info",
    "PACKAGER_FAILED": "warn", "PACKAGER_WARNED": "warn", "PACKAGER_NEW_FINDINGS": "warn",
    "PACKAGER_NOT_RUN": "warn",
    "PACKAGER_FINDINGS": "info", "LARGE_REMOVAL": "warn", "NEW_FOLDER_NOT_PACKAGED": "warn",
}


def packager_portals_default() -> tuple[str, ...]:
    """The site folders the site's packager is taken to package when its PORTALS cannot be read: the project's
    published portals except Mobile Optimized (tracker, plus estimating and customer where the project has them)."""
    have = site_revs.portals() or ("tracker",)
    return tuple(p for p in ("estimating", "customer", "tracker") if p in have)


def rev_index(letter: str) -> int:
    """A..Z = 1..26, AA = 27 ... (the sequential letters of CLAUDE.md "Drawing and design revisions")."""
    n = 0
    for ch in letter.strip().upper():
        if not "A" <= ch <= "Z":
            return 0
        n = n * 26 + ord(ch) - 64
    return n


def folder_of(path: str) -> str:
    """The top-level site folder a path counts under; "(root)" for a file at the site root."""
    return path.split("/", 1)[0] if "/" in path else "(root)"


def count_by_folder(paths) -> dict[str, int]:
    out: dict[str, int] = {}
    for p in paths:
        out[folder_of(p)] = out.get(folder_of(p), 0) + 1
    return dict(sorted(out.items()))


def tree_paths(site: Path, ref: str) -> list[str]:
    """Published files in a site commit (KEEP paths and the notes file left out, as site_files does)."""
    return [p for p in git("ls-tree", "-r", "--name-only", ref, cwd=site).splitlines()
            if p and not keep_path(p) and p != NOTES_FILE]


README_DOC = re.compile(r"(portal-landing|project-portal|quoting-portal|mobile-portal|customer-portal) \*\*Rev ([A-Z]+)\*\*")
README_MODEL = re.compile(r"model\s+`([^`]+)`\s+\*\*Rev (\w+)\*\*")
README_PID = re.compile(r"P&ID\s+`([^`]+)`\s+\*\*Rev (\w+)\*\*")
README_COMMIT = re.compile(r"design-repo commit\s+`([0-9a-f]+)`")


def portals_from_readme(text: str) -> list[dict]:
    seen: dict[str, str] = {}
    for doc, letter in README_DOC.findall(text):
        seen.setdefault(doc, letter)
    out = []
    for doc, letter in seen.items():
        folder = DOC_FOLDER[doc]
        if doc == "project-portal" and "portal-landing" not in seen:   # tracker-only layout: the portal at its filed name
            folder = f"project-portal-rev{letter}/"
        out.append({"document": doc, "revision": letter, "folder": folder})
    return sorted(out, key=lambda p: list(DOC_FOLDER).index(p["document"]))


def site_snapshot(site: Path, ref: str) -> dict:
    """The publish a site commit holds: {source, site_commit, design_commit, model, pid, portals, paths, packager}.
    From its publish-notes.json when it has one, else from its README (what publish_site.py wrote) and its tree."""
    commit = git("rev-parse", ref, cwd=site, check=False).strip()
    paths = tree_paths(site, ref) if commit else []
    raw = git("show", f"{ref}:{NOTES_FILE}", cwd=site, check=False) if commit else ""
    try:
        notes = json.loads(raw) if raw.strip() else None
    except ValueError:
        notes = None
    if isinstance(notes, dict) and str(notes.get("schema", "")).startswith("cpme-site-publish-notes/"):
        return {"source": NOTES_FILE, "site_commit": commit, "design_commit": (notes.get("design_repo") or {}).get("commit"),
                "model": notes.get("model") or {}, "pid": notes.get("pid") or {}, "portals": notes.get("portals") or [],
                "paths": paths, "packager": notes.get("packager")}
    text = git("show", f"{ref}:README.md", cwd=site, check=False) if commit else ""
    mm, pm, cm = README_MODEL.search(text), README_PID.search(text), README_COMMIT.search(text)
    return {"source": "README.md and tree" if text else ("tree" if commit else "none"), "site_commit": commit,
            "design_commit": cm.group(1) if cm else None,
            "model": {"id": mm.group(1), "revision": mm.group(2)} if mm else {},
            "pid": {"id": pm.group(1), "revision": pm.group(2)} if pm else {},
            "portals": portals_from_readme(text), "paths": paths, "packager": None}


PUBLISH_MERGE = re.compile(r"^Merge pull request #\d+ from \S+/daily/\d{4}-\d{2}-\d{2}\b")


def is_publish(subject: str) -> bool:
    """A publish on the site's main: a "Site: ..." commit (direct pushes before 2026-11-09, and the commit on each daily
    branch), or the merge of a daily/<date> publish branch (from 2026-11-09)."""
    return subject.startswith("Site: ") or bool(PUBLISH_MERGE.match(subject))


def commits_since_last_publish(site: Path, base: str, limit: int = 200) -> list[dict]:
    """The site commits on base's first-parent line made after the last publish commit: the site repo's own commits,
    carried by this publish's branch. [] when base is itself a publish."""
    subjects = git("log", "--first-parent", f"-{limit}", "--format=%H%x1f%s", base, cwd=site, check=False).splitlines()
    last = next((ln.split("\x1f", 1)[0] for ln in subjects if is_publish(ln.split("\x1f", 1)[-1])), None)
    if last is None:
        return []
    return [{k: c[k] for k in ("hash", "author", "date", "subject", "files")} for c in log_commits(site, f"{last}..{base}")]


def packager_portals(script: Path | None) -> tuple[list[str], str]:
    """The site folders the site's packager packages: the keys of PORTALS in its package_portals.py, read with ast
    (never imported or run); packager_portals_default() when the script is missing or the assignment cannot be read."""
    import ast
    if script and script.is_file():
        try:
            for node in ast.parse(script.read_text(encoding="utf-8")).body:
                if (isinstance(node, (ast.Assign, ast.AnnAssign))
                        and any(isinstance(t, ast.Name) and t.id == "PORTALS"
                                for t in (node.targets if isinstance(node, ast.Assign) else [node.target]))):
                    val = ast.literal_eval(node.value)
                    if isinstance(val, dict) and val:
                        return sorted(val), f"PORTALS in {PACKAGER.as_posix()}"
        except (SyntaxError, ValueError, UnicodeDecodeError):
            pass
    dflt = packager_portals_default()
    return sorted(dflt), f"default {', '.join(dflt)} (PORTALS not readable from {PACKAGER.as_posix()})"


PK_PACKAGED = re.compile(r"^packaged \S+ (\w+) Rev (\w+) \(model Rev \w+\): (\d+) files")
PK_LINKS = re.compile(r"^\s+links out of the portal, not packaged[^:]*:\s*(.*)$")
PK_UNRES = re.compile(r"^\s+(\d+) file-like mention\(s\) not in the site[^:]*:\s*(.*)$")


def parse_packager(status: str, lines: list[str], script: Path | None, prev: dict | None) -> dict:
    """The site packager's result as the notes record it: exit code, warning lines, and per portal its revision, files,
    links out and unresolved file mentions; new_since_last compares with the last publish's notes (null when the
    last publish carried none)."""
    code = None
    if lines and (m := re.match(r"package_portals\.py exit (-?\d+)", lines[0])):
        code = int(m.group(1))
    portals: dict[str, dict] = {}
    cur = None
    for ln in lines[1:]:
        if m := PK_PACKAGED.match(ln):
            cur = portals.setdefault(m.group(1), {"revision": m.group(2), "files": int(m.group(3)), "links_out": [],
                                                  "unresolved_count": 0, "unresolved_shown": []})
        elif cur is not None and (m := PK_LINKS.match(ln)):
            cur["links_out"] = [s.strip() for s in m.group(1).split(",") if s.strip()]
        elif cur is not None and (m := PK_UNRES.match(ln)):
            cur["unresolved_count"] = int(m.group(1))
            cur["unresolved_shown"] = [s.strip() for s in m.group(2).replace(" ...", "").split(",") if s.strip()]
    warnings = [ln.strip() for ln in lines[1:] if re.search(r"\bwarn", ln, re.I)]
    names, source = packager_portals(script)
    new = {"links_out": None, "unresolved": None}
    pp = (prev or {}).get("portals") if isinstance(prev, dict) else None
    if isinstance(pp, dict) and status == "pass" and (prev or {}).get("status") == "pass":
        new["links_out"] = sorted({f"{p}: {x}" for p, d in portals.items() for x in d["links_out"]}
                                  - {f"{p}: {x}" for p, d in pp.items() for x in d.get("links_out", [])})
        new["unresolved"] = max(0, sum(d["unresolved_count"] for d in portals.values())
                                - sum(int(d.get("unresolved_count", 0)) for d in pp.values()))
    return {"status": status, "exit_code": code, "script": PACKAGER.as_posix(), "packager_portals": names,
            "packager_portals_source": source, "warnings": warnings, "portals": portals, "new_since_last": new}


def find_anomalies(prev: dict, cur: dict, files: dict, upstream_commits: list[dict], packager: dict,
                   customer_site: bool | None = None) -> list[dict]:
    """Every anomaly of this publish against the last one, each {code, severity, message, details} (CODES gives the
    severity). prev and cur are snapshots ({model, pid, portals, ...}); files = {prev_by_folder, prev_total, added,
    changed, removed} (path lists); cur also carries top_folders. customer_site: the project has a customer site
    (default: "customer" in site_revs.portals()); only then, or when the last publish carried customer/, is leaving it
    out an anomaly. [] = no anomalies."""
    out: list[dict] = []
    if customer_site is None:
        customer_site = "customer" in site_revs.portals()

    def add(code: str, message: str, **details) -> None:
        out.append({"code": code, "severity": CODES[code], "message": message, "details": details})

    pm, cm = prev.get("model") or {}, cur.get("model") or {}
    if pm.get("id") and cm.get("id") and pm["id"] != cm["id"]:
        add("MODEL_ID_CHANGED", f"Model ID changed from {pm['id']} Rev {pm.get('revision')} to {cm['id']} Rev "
            f"{cm.get('revision')}; packages go under a new <MODEL-ID>/ folder.", previous=pm, current=cm)
    elif pm.get("id") and pm.get("id") == cm.get("id") and rev_index(cm.get("revision", "")) < rev_index(pm.get("revision", "")):
        add("MODEL_REV_BACKWARDS", f"Model {cm['id']} revision went backwards, Rev {pm['revision']} to Rev {cm['revision']}.",
            previous=pm, current=cm)
    pp, cp = prev.get("pid") or {}, cur.get("pid") or {}
    if pp.get("id") and cp.get("id") and pp["id"] != cp["id"]:
        add("PID_ID_CHANGED", f"P&ID number changed from {pp['id']} Rev {pp.get('revision')} to {cp['id']} Rev "
            f"{cp.get('revision')}.", previous=pp, current=cp)

    before = {p["document"]: p for p in prev.get("portals", [])}
    after = {p["document"]: p for p in cur.get("portals", [])}
    if "customer-portal" not in after and len(after) > 1 and (customer_site or "customer-portal" in before):
        was = "customer-portal" in before
        add("CUSTOMER_LEFT_OUT", "Customer site left out of this publish (--customer none or none filed)"
            + ("; customer/ was in the last publish and is removed, so the customer package cannot be rebuilt."
               if was else "; customer/ was not in the last publish either."),
            previous_revision=before.get("customer-portal", {}).get("revision"))
    for doc in after.keys() - before.keys():
        if before:   # the first publish with notes from nothing has no "last one" to compare
            add("PORTAL_ADDED", f"{doc} Rev {after[doc]['revision']} is new on the site, as {after[doc]['folder'] or 'the site root'}.",
                document=doc, revision=after[doc]["revision"], folder=after[doc]["folder"])
    for doc in before.keys() - after.keys():
        if doc == "customer-portal" and any(a["code"] == "CUSTOMER_LEFT_OUT" for a in out):
            continue
        add("PORTAL_REMOVED", f"{doc} (last published Rev {before[doc]['revision']}, {before[doc]['folder'] or 'site root'}) "
            "is not in this publish.", document=doc, revision=before[doc]["revision"], folder=before[doc]["folder"])
    for doc in sorted(before.keys() & after.keys(), key=list(DOC_FOLDER).index):
        a, b = rev_index(before[doc]["revision"]), rev_index(after[doc]["revision"])
        if b > a + 1:
            add("REV_SKIPPED", f"{doc} went from Rev {before[doc]['revision']} to Rev {after[doc]['revision']}, "
                f"skipping {b - a - 1} letter(s).", document=doc, previous=before[doc]["revision"],
                current=after[doc]["revision"])
        elif b < a:
            add("REV_BACKWARDS", f"{doc} went backwards, Rev {before[doc]['revision']} to Rev {after[doc]['revision']}.",
                document=doc, previous=before[doc]["revision"], current=after[doc]["revision"])

    if upstream_commits:
        add("UPSTREAM_COMMITS", f"Carried {len(upstream_commits)} upstream commit(s) made since the last "
            "publish (KEEP paths only): " + "; ".join(f"{c['hash'][:7]} {c['author']} \"{c['subject']}\""
                                                      for c in upstream_commits) + ".",
            commits=[{"hash": c["hash"], "author": c["author"], "subject": c["subject"]} for c in upstream_commits])

    st = packager.get("status")
    if st == "fail":
        add("PACKAGER_FAILED", f"The site's packager failed on the staged tree (exit {packager.get('exit_code')}); "
            "the publish stops before writing.", exit_code=packager.get("exit_code"))
    elif st in ("missing", "skipped"):
        add("PACKAGER_NOT_RUN", f"The site's packager was not run ({st}); the package of this publish is unchecked.",
            status=st)
    if packager.get("warnings"):
        add("PACKAGER_WARNED", f"The site's packager printed {len(packager['warnings'])} warning line(s): "
            + "; ".join(packager["warnings"][:3]) + ("..." if len(packager["warnings"]) > 3 else "") + ".",
            warnings=packager["warnings"])
    new = packager.get("new_since_last") or {}
    if new.get("links_out") or new.get("unresolved"):
        add("PACKAGER_NEW_FINDINGS", "The site's packager reports new findings since the last publish: "
            + ", ".join(filter(None, [f"{len(new['links_out'])} new link(s) out ({', '.join(new['links_out'][:4])})"
                                      if new.get("links_out") else "",
                                      f"{new['unresolved']} more unresolved file mention(s)" if new.get("unresolved") else ""]))
            + ".", **new)
    elif st == "pass" and new.get("unresolved") is None:
        lo = sum(len(d["links_out"]) for d in packager.get("portals", {}).values())
        un = sum(d["unresolved_count"] for d in packager.get("portals", {}).values())
        if lo or un:
            add("PACKAGER_FINDINGS", f"The site's packager passes with {lo} link(s) out and {un} unresolved file "
                "mention(s); the last publish carried no packager record, so what is new is not known.",
                links_out=lo, unresolved=un)

    prev_by, prev_total = files.get("prev_by_folder", {}), files.get("prev_total", 0)
    rem_by = count_by_folder(files.get("removed", []))
    for fold, n in rem_by.items():
        had = prev_by.get(fold, 0)
        if fold not in SUPPORT_FOLDERS and had and n >= REMOVAL_FOLDER_MIN and n > REMOVAL_FOLDER_SHARE * had:
            add("LARGE_REMOVAL", f"{n} of the {had} files in {fold}{'' if fold == '(root)' else '/'} are removed "
                f"(more than {REMOVAL_FOLDER_SHARE:.0%}).", folder=fold, removed=n, previous=had)
    nrem, nadd = len(files.get("removed", [])), len(files.get("added", []))
    if prev_total and nrem > REMOVAL_SITE_SHARE * prev_total and nrem - nadd > REMOVAL_SITE_NET * prev_total:
        add("LARGE_REMOVAL", f"{nrem} of the site's {prev_total} files are removed and only {nadd} added (the site "
            f"shrinks by {(nrem - nadd) / prev_total:.0%}).", folder="*", removed=nrem, added=nadd, previous=prev_total)

    packaged = set(packager.get("packager_portals") or packager_portals_default()) | SUPPORT_FOLDERS
    prev_top = {folder_of(p) for p in prev.get("paths", [])} - {"(root)"}
    # a site repo with no packager packages nothing: PACKAGER_NOT_RUN says so once, not once per folder
    for fold in [] if st == "missing" else sorted(set(cur.get("top_folders", [])) - prev_top - packaged):
        add("NEW_FOLDER_NOT_PACKAGED", f"New top-level folder {fold}/ is not one the site's packager packages "
            f"({', '.join(sorted(packaged - SUPPORT_FOLDERS))}).", folder=fold,
            packager_portals_source=packager.get("packager_portals_source"))
    return out


def notes_lines(anomalies: list[dict]) -> list[str]:
    """The "Notes for packaging" section of the site commit message."""
    return ["Notes for packaging:"] + ([f"- [{a['severity']}] {a['code']}: {a['message']}" for a in anomalies]
                                       or ["No anomalies."])


def commit_message(subject: str, anomalies: list[dict], body: list[str]) -> str:
    """The subject line unchanged, a blank line, the notes section, a blank line, then the body."""
    return "\n".join([subject, ""] + notes_lines(anomalies) + ([""] + body if body else [])) + "\n"


def validate_notes(n: dict) -> list[str]:
    """Problems with a publish-notes.json object against NOTES_SCHEMA; [] = valid."""
    bad = []
    if list(n) != list(NOTES_KEYS):
        bad.append(f"keys {list(n)} are not {list(NOTES_KEYS)}")
    if n.get("schema") != NOTES_SCHEMA:
        bad.append(f"schema {n.get('schema')!r} is not {NOTES_SCHEMA!r}")
    for k, t in (("design_repo", dict), ("site", dict), ("model", dict), ("pid", dict), ("portals", list),
                 ("top_folders", list), ("files", dict), ("upstream_commits", list), ("packager", dict),
                 ("previous", dict), ("anomalies", list)):
        if not isinstance(n.get(k), t):
            bad.append(f"{k} is not a {t.__name__}")
    for a in n.get("anomalies") or []:
        if set(a) != {"code", "severity", "message", "details"} or a.get("code") not in CODES \
                or a.get("severity") not in ("info", "warn") or not isinstance(a.get("details"), dict):
            bad.append(f"anomaly {a!r} is not {{code in CODES, severity info|warn, message, details{{}}}}")
        elif "\n" in a["message"]:
            bad.append(f"anomaly {a['code']} message is not one line")
    for p in n.get("portals") or []:
        if set(p) != {"document", "revision", "folder"}:
            bad.append(f"portal {p!r} is not {{document, revision, folder}}")
    for k in ("total", "bytes", "added", "changed", "removed", "unchanged"):
        if not isinstance((n.get("files") or {}).get(k), int):
            bad.append(f"files.{k} is not an integer")
    if (n.get("packager") or {}).get("status") not in ("pass", "fail", "missing", "skipped"):
        bad.append("packager.status is not pass|fail|missing|skipped")
    return bad


def build_notes(*, published_at: str, design_commit: str, parent: str, prev: dict, cur: dict, files: dict,
                upstream_commits: list[dict], packager: dict, customer_site: bool | None = None) -> dict:
    """The publish-notes.json object (NOTES_SCHEMA, keys in NOTES_KEYS order)."""
    removed = sorted(files.get("removed", []))
    plan_paths = files.get("plan_paths", [])
    notes = {
        "schema": NOTES_SCHEMA,
        "written_by": "harness/scripts/publish_site.py",
        "published_at": published_at,
        "design_repo": {"repo": rp.DESIGN_REPO, "commit": design_commit},
        "site": {"repo": SITE_SLUG, "parent_commit": parent},
        "model": cur.get("model") or {},
        "pid": cur.get("pid") or {},
        "portals": cur.get("portals", []),
        "top_folders": cur.get("top_folders", []),
        "files": {"total": len(plan_paths), "bytes": int(files.get("bytes", 0)), "by_folder": count_by_folder(plan_paths),
                  "added": len(files.get("added", [])), "changed": len(files.get("changed", [])), "removed": len(removed),
                  "unchanged": len(plan_paths) - len(files.get("added", [])) - len(files.get("changed", [])),
                  "removed_paths": removed[:NOTES_PATHS_MAX], "removed_paths_truncated": len(removed) > NOTES_PATHS_MAX},
        "upstream_commits": [{k: c[k] for k in ("hash", "author", "date", "subject", "files")} for c in upstream_commits],
        "packager": packager,
        "previous": {"source": prev.get("source"), "site_commit": prev.get("site_commit"),
                     "model": prev.get("model") or {}, "pid": prev.get("pid") or {}, "portals": prev.get("portals", [])},
        "anomalies": find_anomalies(prev, cur, files, upstream_commits, packager, customer_site),
    }
    return notes


def notes_json(notes: dict) -> str:
    return json.dumps(notes, indent=1, ensure_ascii=False) + "\n"


def anomaly_summary(anomalies: list[dict]) -> list[str]:
    """The dry run's one-line-per-anomaly summary, which closeout.py carries into the go."""
    if not anomalies:
        return ["packaging notes: no anomalies"]
    return [f"packaging notes: {len(anomalies)} anomal{'y' if len(anomalies) == 1 else 'ies'} "
            f"({sum(a['severity'] == 'warn' for a in anomalies)} warn)"] + [
        f"packaging note: [{a['severity']}] {a['code']}: {a['message']}" for a in anomalies]


def pick(arg: str | None, has: bool, root: Path, what: str, flag: str) -> str | None:
    """A portal revision from its flag: "none" -> None; a project without the portal accepts only "none" (or nothing);
    else the letter given, or the newest filed."""
    v = (arg or "").strip()
    if v.lower() == "none":
        return None
    if not has:
        if v:
            die(f"{flag} {v}: this project has no {what} (site_revs.portals(): {', '.join(site_revs.portals())}); "
                f"use {flag} none")
        return None
    return v or newest_filed(root)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--rev", required=True, help="filed project-portal revision letter")
    ap.add_argument("--dry-run", action="store_true", help="print the file plan and sizes; change nothing")
    ap.add_argument("--bob-go", help="optional: Bob's words, recorded in the site commit body (the end-of-day merge of "
                                     "the publish branch is the publish)")
    ap.add_argument("--as-bob", action="store_true", help="ignored since 2026-10-07 (Bob-Biedrzycki is the writer)")
    ap.add_argument("--site", default=str(rp.PRESENTATION_SITE), help="site checkout (default: sibling of this repo)")
    ap.add_argument("--quoting", help="filed quoting-portal revision, published as estimating/ (default the newest; "
                                      "'none': no estimating/ folder; only 'none' on a project without that portal)")
    ap.add_argument("--landing", help="filed portal-landing revision (default the newest; 'none': tracker-only layout)")
    ap.add_argument("--mobile", help="filed mobile-portal revision, published as mobile/ (default the newest; 'none': "
                                     "no mobile/ folder)")
    ap.add_argument("--customer", help="filed customer-portal revision, published as customer/ (default the newest; "
                                       "'none': no customer/ folder; only 'none' on a project without that site)")
    ap.add_argument("--date", help="the day's branch daily/<YYYY-MM-DD> in both repos (default today)")
    a = ap.parse_args()
    why = site_revs.site_dormant()
    if why:   # CPME practice: the framework stays; a project with no site publishes nothing and passes
        print(f"publish_site: {why}; nothing published")
        return 0
    rev, site, dry = a.rev.strip(), Path(a.site), a.dry_run
    date = a.date or dt.date.today().isoformat()
    daily_ref(date)   # refuses a malformed date before anything runs
    T.DRY = dry
    have = site_revs.portals()
    has_est, has_cus = "estimating" in have, "customer" in have
    quote = pick(a.quoting, has_est, QUOTING, "Fabrication Estimating Portal", "--quoting")
    cus = pick(a.customer, has_cus, CUSTOMER, "customer site", "--customer")
    land = None if (a.landing or "").lower() == "none" else (a.landing or newest_filed(LANDING))
    six = bool(land)   # the site layout: landing page at the root, the portals beside it
    if not six and ((a.quoting or "none").lower() != "none" or (a.customer or "none").lower() != "none"):
        die("estimating/ and customer/ need the landing layout; give --landing <L> (or --quoting none --customer none)")
    if not six:
        quote = cus = None
    mob = None if not six or (a.mobile or "").lower() == "none" else (a.mobile or newest_filed(MOBILE))
    go = (a.bob_go or "").strip()

    # 1. filed revisions, design-repo commit, site checkout state
    rows, model, mrev, prev, pid = filed_revision(rev)
    docs = docs_for(rev, land, mob, quote, cus)
    cus_unfiled = ""
    for root, f, pre in list(docs):
        if not (root / f).is_dir():
            if dry and root == CUSTOMER:   # a dry run may name the customer issue before Bob files it
                cus_unfiled = (f"{rp.rel(root / f)} is not filed: shown in the layout as {CUS}, left out of the file plan "
                               "(dry run only; the real run refuses)")
                docs.remove((root, f, pre))
                continue
            die(f"{rp.rel(root / f)} is not filed")
    folders = [rp.rel(root / f) for root, f, _ in docs]
    # Filed folders saved on the design repo's origin: every file under them, with each document's revisions.csv,
    # byte for byte on origin/daily/<date> (saved today by track.py save) or origin/main (merged).
    checked = folders + sorted({rp.rel(root / "revisions.csv") for root, _, _ in docs})
    commit_warn = ""
    T.git_remote("fetch", "origin", "main", cwd=rp.REPO)
    design_daily = f"origin/{DAILY_PREFIX}{date}"
    if T.git_remote("ls-remote", "--heads", "origin", f"{DAILY_PREFIX}{date}", cwd=rp.REPO).strip():
        T.git_remote("fetch", "origin", f"refs/heads/{DAILY_PREFIX}{date}:refs/remotes/{design_daily}", cwd=rp.REPO)
    on_ref, not_saved = saved_on(checked, [design_daily, "origin/main"])
    if on_ref is None:
        msg = (f"the filed folders are not saved on the design repo's origin ({not_saved}); save them with "
               "track.py save first, then publish")
        if not dry:
            die(msg)
        commit_warn = msg + " (dry run continues)"
    commit = (git("log", "-1", "--format=%H", on_ref, "--", *checked, cwd=rp.REPO).strip() if on_ref else "") or "-------"
    head = git("rev-parse", "HEAD", cwd=rp.REPO).strip()
    folder = folders[0] if not six else ", ".join(folders)
    refusal = checkout_refusal(site)
    if refusal:
        die(refusal)
    url = git("remote", "get-url", "origin", cwd=site).strip()
    # upstream commits since the last publish on origin/main: named; one touching published content refuses
    if not dry:
        T.require_writer()
    up_lines, up_action = sync_site(site, dry)
    last = git("log", "-1", "--format=%s", "origin/main", cwd=site, check=False).strip()
    # the publish branch builds on origin/daily/<date> (an earlier publish today, not merged yet) or origin/main;
    # the notes compare with the live site, origin/main
    base = publish_base(site, date, fetch_site_daily(site, date))
    prev_snap = site_snapshot(site, "origin/main")
    taken = commits_since_last_publish(site, "origin/main")

    # 2. large files present (pull if missing), filed bytes verified
    missing = ensure_large_files(dry)
    plan = source_plan(docs)
    hidden = site_revs.hidden_models()
    store_bytes = sum(p.stat().st_size for k, p in plan.items() if k.startswith("data/"))
    plan, dropped_store, still_shown = trim_store(plan, hidden)
    warns = (([cus_unfiled] if cus_unfiled else []) + ([commit_warn] if commit_warn else [])
             + (verify_sources(docs, plan) if not missing else []))
    kept_store = sum(p.stat().st_size for k, p in plan.items() if k.startswith("data/"))
    warns.append(f"data store: {len(dropped_store)} filed file(s), {mb(store_bytes - kept_store)}, left off the site (not reached by "
                 f"the published pages; hidden models: {', '.join(hidden) or 'none'}, {rp.rel(rp.SITE_CONFIG)})")
    if still_shown:
        warns.append(f"project-portal Rev {rev} was built before {', '.join(still_shown)} was hidden and still lists it in the "
                     "revision picker; its files stay published until a tracker built with the switch is filed and published")

    # 3. the site tree: filed trees (+ root redirect in the tracker-only layout) + README
    pub_date = dt.date.today().isoformat()
    target = f"project-portal-rev{rev}/"
    index_html = None if six else INDEX.format(target=target, rev=rev, **PROJECT_FMT)
    label = (f"Rev {rev}" + (f" + quoting Rev {quote}" if quote else "") + (f" + landing Rev {land}" if six else "")
             + (f", mobile Rev {mob}" if mob else "") + (f", customer Rev {cus}" if cus else ""))
    new_row = f"| {pub_date} | {label} | {model} Rev {mrev} | Rev {prev} | {commit[:7]} | {rows[0].get('notes', '').strip() or '-'} |"
    base_readme = git("show", f"{base}:README.md", cwd=site, check=False)
    old_rows = [r for r in carried_rows(site, base_readme) if f"| Rev {rev} |" not in r or "hand copy" in r]
    fmt = dict(PROJECT_FMT, rev=rev, model=model, mrev=mrev, prev=prev, date=pub_date, commit=commit[:7],
               rows="\n".join(old_rows + [new_row]))
    fmt["pid_doc_id"] = pid   # the P&ID number the published revision was built on
    if six:
        readme = README6.format(
            land=land, mob_note=f" **Rev {mob}**" if mob else " not filed yet",
            est_intro=README6_EST_INTRO if quote else "",
            est_content=README6_EST_CONTENT.format(quote=quote, **PROJECT_FMT) if quote else "",
            cus_intro=README6_CUS_INTRO.format(cus_note=f" **Rev {cus}**" if cus else " not filed yet") if has_cus else "",
            **fmt)
    else:
        readme = README.format(**fmt)
    # what the publish branch starts from, by blob (the site stores every file byte for byte, `* -text`)
    current = base_blobs(site, base)
    plan_blob = plan_blobs(site, plan)
    remove = sorted(k for k in current if k not in plan and (six or k != "index.html"))
    add = sorted(k for k in plan if k not in current)
    change = sorted(k for k in plan if k in current and current[k] != plan_blob[k])
    same = len(plan) - len(add) - len(change)
    total = sum(p.stat().st_size for p in plan.values())
    big = sorted(plan.items(), key=lambda kv: kv[1].stat().st_size, reverse=True)
    over = [k for k, p in big if p.stat().st_size > GH_HARD_LIMIT]
    subject = (f"Site: project-portal Rev {rev}" + (f", quoting-portal Rev {quote}" if quote else "")
               + f", landing Rev {land}" + (f", mobile Rev {mob}" if mob else "") + (f", customer Rev {cus}" if cus else "")
               + f" (model Rev {mrev}, P&ID Rev {prev})"
               if six else f"Site: project-portal Rev {rev} (model Rev {mrev}, P&ID Rev {prev})")

    print(f"publish_site{' (DRY RUN: nothing written, committed or pushed)' if dry else ''}")
    print(f"  source:  {folder} + the shared data store(s) ({model} Rev {mrev}, P&ID Rev {prev})")
    print(f"           design-repo commit {commit[:12]} (HEAD {head[:12]})")
    print(f"  site:    {site} on main, clean (not written); origin {url}; origin/main newest: {last}")
    print(f"  branch:  {DAILY_PREFIX}{date} in the site repo, built on {base}; its merge into main (end of day) is the publish")
    for ln in up_lines:
        print(f"  {ln}")
    if six:
        print(f"  layout:  index.html + assets/ (landing Rev {land}), tracker/ (project-portal Rev {rev}), "
              + (f"{EST} (Fabrication Estimating Portal, quoting-portal Rev {quote}), " if quote else "")
              + (f"{MOB} (Mobile Optimized, mobile-portal Rev {mob}), " if mob else "")
              + (f"{CUS} (customer site, customer-portal Rev {cus}{', NOT FILED' if cus_unfiled else ''}), " if cus else "")
              + "data/ (stores merged)")
    print(f"  files:   {len(plan)} filed files, {mb(total)} "
          + (f"(landing {sum(1 for k in plan if not k.startswith(('tracker/', EST, MOB, CUS, 'data/')))}, "
             f"tracker {sum(1 for k in plan if k.startswith('tracker/'))}, "
             + (f"estimating {sum(1 for k in plan if k.startswith(EST))}, " if quote else "")
             + f"mobile {sum(1 for k in plan if k.startswith(MOB))}, "
             + (f"customer {sum(1 for k in plan if k.startswith(CUS))}, " if cus else "")
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

    # The site's packager on a staged copy of the tree this publish leaves: a failure would break the site's own
    # packaging on the merge, so the real run stops here; the dry run warns. The site checkout is not written in either.
    # The packager as the publish base holds it (the branch is built on it, and the merge brings it to main).
    script, which = site / PACKAGER, "site checkout copy"
    shown = git("show", f"{base}:{PACKAGER.as_posix()}", cwd=site, check=False)
    if shown:
        script = reset_scratch(rp.SITE_CHECK / "upstream-packager") / PACKAGER.name
        script.write_text(shown, encoding="utf-8", newline="")
        which = f"{base} copy"
    # the publish notes: this publish against the last one
    cur_snap = {"model": {"id": model, "revision": mrev}, "pid": {"id": pid, "revision": prev},
                "portals": [{"document": f.rsplit("-rev", 1)[0], "revision": f.rsplit("-rev", 1)[1], "folder": pre}
                            for _, f, pre in docs],
                "top_folders": sorted({k.split("/", 1)[0] for k in plan if "/" in k})}
    nfiles = {"prev_by_folder": count_by_folder(current), "prev_total": len(current), "added": add, "changed": change,
              "removed": remove, "plan_paths": sorted(plan), "bytes": total}
    published_at = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    parent = git("rev-parse", base, cwd=site).strip()

    def make_notes(pk_status: str, pk_lines: list[str]) -> dict:
        return build_notes(published_at=published_at, design_commit=commit, parent=parent, prev=prev_snap,
                           cur=cur_snap, files=nfiles, upstream_commits=taken,
                           packager=parse_packager(pk_status, pk_lines, script, prev_snap.get("packager")),
                           customer_site=has_cus)

    tree = None
    if missing:
        status, pk = "skipped", [f"not run: {len(missing)} large file(s) not pulled here, so the tree cannot be staged"]
    else:
        # staged with publish-notes.json present, so the run shows the packager leaves it alone
        extra = ({"README.md": readme.encode("utf-8"), NOTES_FILE: notes_json(make_notes("skipped", [])).encode("utf-8")}
                 | ({"index.html": index_html.encode("utf-8")} if index_html else {}))
        tree = stage_tree(plan, extra, rp.SITE_CHECK / "stage")
        status, pk = site_packaging(script, tree, rp.SITE_CHECK / "packages")
        if status != "missing":
            pk[0] += f" (python -I {PACKAGER.as_posix()}, {which}, on the staged copy {rp.rel(tree)})"
    notes = make_notes(status, pk)
    if tree is not None:
        (tree / NOTES_FILE).write_text(notes_json(notes), encoding="utf-8", newline="\n")
    bad_notes = validate_notes(notes)
    if bad_notes:
        die(f"{NOTES_FILE} does not match {NOTES_SCHEMA}; nothing written:\n  " + "\n  ".join(bad_notes))
    if status in ("pass", "skipped"):
        print(f"  site packaging: {status}: {pk[0]}")
    else:
        print(f"  WARNING site packaging: {status}: {pk[0]}")
    for ln in pk[1:]:
        print(f"           {ln if len(ln) <= 220 or status == 'fail' else ln[:217] + '...'}")
    if status == "fail" and not dry:
        die(f"the site's packager ({PACKAGER.as_posix()}) fails on the staged tree, so this publish would break the "
            "site's packaging; nothing written to the site checkout:\n  " + "\n  ".join(pk))
    for ln in anomaly_summary(notes["anomalies"]):
        print(f"  {ln}")
    body_rest = ([
            f"Generated copies of the filed portal-landing Rev {land} (site root), project-portal Rev {rev} (tracker/)"
            + (f", quoting-portal Rev {quote} (the Fabrication Estimating Portal, {EST})" if quote else "")
            + (f", mobile-portal Rev {mob} ({MOB})" if mob else "") + (f", customer-portal Rev {cus} ({CUS})" if cus else ""),
            "with the portals' shared data stores merged as data/ so every",
            "page's ../data/ paths resolve. Do not hand-edit; republish instead.", ""] if six else [
            f"Generated copy of the filed project-portal Rev {rev} ({rp.rel(PORTAL)}/project-portal-rev{rev}/)",
            f"and the shared portal data store ({rp.rel(PORTAL)}/data/), laid out as filed so the pages'",
            "../data/ paths resolve; index.html forwards to the portal. Do not hand-edit; republish instead.", ""]) + [
            f"Design repo: {rp.DESIGN_REPO} commit {commit}",
            f"Model: {model} Rev {mrev}; P&ID {pid} Rev {prev}",
            f"Files: {len(plan)} filed files ({mb(total)}); {len(add)} added, {len(change)} changed, {len(remove)} removed",
            f"Notes: {NOTES_FILE} ({NOTES_SCHEMA}), compared with site commit {parent[:12]} ({prev_snap['source']})",
            "Basis: Bob, chat, 2026-10-02 and 2026-11-09; harness/scripts/publish_site.py",
            f"Published by: publish_site.py; live when the end-of-day merge of {DAILY_PREFIX}{date} lands on main"] + (
            [f"Bob's go: \"{go}\""] if go else [])
    message = commit_message(subject, notes["anomalies"], body_rest)
    if dry:
        print(f"\n----- site commit message, as it would be committed -----\n{message}"
              f"----- {NOTES_FILE}, as it would be written at the site root (published_at is the real run's time) -----\n"
              f"{notes_json(notes)}----- end of notes -----")
        print(f"\nTo push the publish branch {DAILY_PREFIX}{date} (its end-of-day merge is the publish): "
              f".\\harness\\tools\\venv\\Scripts\\python.exe harness\\scripts\\publish_site.py "
              f"--rev {rev} --quoting {quote or 'none'}"
              + ((f" --landing {land} --mobile {mob or 'none'}" + (f" --customer {cus or 'none'}" if has_cus else ""))
                 if six else " --landing none"))
        return 0

    # 4-5. write, commit and push the day's branch from a short-lived worktree (the site checkout is not written)
    extra_files = {"README.md": readme.encode("utf-8"), NOTES_FILE: notes_json(notes).encode("utf-8")}
    if index_html is not None:   # tracker-only layout: a redirect; with a landing page, that page is index.html
        extra_files["index.html"] = index_html.encode("utf-8")
    local, remote = publish_branch(site, base, date, plan, remove, add + change, extra_files, message,
                                   rp.TRACKING / f"site-rev{rev}")
    print(f"\npushed: {subject}\n  site commit {local[:12]} on {DAILY_PREFIX}{date}; origin {remote[:12]} "
          f"({'matches' if remote == local else 'DOES NOT MATCH'}). Not live yet: the end-of-day merge of "
          f"{DAILY_PREFIX}{date} into the site repo's main is the publish.")
    return 0 if remote == local else 1


def publish_branch(site: Path, base: str, date: str, plan: dict[str, Path], remove: list[str], copy: list[str],
                   extra_files: dict[str, bytes], message: str, scratch: Path) -> tuple[str, str]:
    """Build the publish commit on `base` in a detached worktree beside the site checkout, stage by explicit path
    (git rm for removals, git add for the rest; never -A), commit, push HEAD to daily/<date> only (never main, never
    forced), then remove the worktree. Returns (local commit, origin's daily/<date>). Bob, chat, 2026-11-09: "change
    publish_site.py to push to a daily branch in the site repo ... It also needs to stop using git add -A.\""""
    spec = push_refspec(date)
    wt = site.parent / f"{site.name}-daily-{date}"
    if wt.exists():
        die(f"worktree folder already exists: {wt} (a previous publish was cut short; recover with: "
            f"git -C \"{site}\" worktree remove --force \"{wt}\")")
    git("worktree", "add", "--detach", str(wt), base, cwd=site)
    try:
        for k in remove:
            rm(wt / k)
        for k in copy:
            dst = wt / k
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.exists():
                rm(dst)
            with open(plan[k], "rb") as fi, open(dst, "wb") as fo:   # bytes only; the filed read-only flag is not copied
                fo.write(fi.read())
        for d in sorted((p for p in wt.rglob("*") if p.is_dir() and ".git" not in p.relative_to(wt).parts),
                        key=lambda p: len(p.parts), reverse=True):
            if not any(d.iterdir()):
                d.rmdir()
        for k, data in extra_files.items():
            (wt / k).write_bytes(data)
        for k in plan:   # what was copied is what was filed
            if (wt / k).stat().st_size != plan[k].stat().st_size:
                die(f"copy check failed for {k}")
        if list(wt.rglob("*.drive")):
            die("a .drive pointer reached the site tree")
        written = sorted(set(copy) | set(extra_files))
        stage_explicit(wt, written, remove, scratch)
        # porcelain "XY path": Y is the worktree column; anything there (or "??") was not staged by name
        left = [ln for ln in git("status", "--porcelain", cwd=wt).splitlines() if ln[1:2] != " "]
        if left:
            die("changes outside the plan remain unstaged after staging by name: " + "; ".join(left[:5]))
        mf = scratch / "site-commit.md"
        mf.parent.mkdir(parents=True, exist_ok=True)
        mf.write_text(message, encoding="utf-8", newline="\n")
        git("commit", "-F", str(mf), cwd=wt)
        T.git_remote("push", "origin", spec, cwd=wt, write=True)
        local = git("rev-parse", "HEAD", cwd=wt).strip()
        out = T.git_remote("ls-remote", "origin", spec.split(":", 1)[1], cwd=wt).split()
        return local, (out[0] if out else "")
    finally:
        git("worktree", "remove", "--force", str(wt), cwd=site, check=False)


if __name__ == "__main__":
    sys.exit(main())
