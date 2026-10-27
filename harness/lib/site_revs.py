"""site_revs - the newest filed revision of each document the presentation site publishes.

One reader for closeout.py step 9 (the publish plan), track.py after-merge (the publish after the day's PR merges)
and publish_site.py (its --quoting / --landing defaults), so the three never disagree about what "newest" means:
the last row of the document's revisions.csv (model_build.last_revision; revision letters are sequential, TR-08).

    import site_revs
    revs = site_revs.newest()            # {"rev": "J", "quoting": "E", "landing": "D"}; None where nothing is filed
    args = site_revs.publish_args(revs)  # ["--rev", "J", "--quoting", "E", "--landing", "D"]
    site_revs.hidden_models()            # ("<retired MODEL-ID>",): <project>/03_Working_Design/CAD/09_Presentation/site.yaml
    site_revs.hidden_pages()             # ("quote",): tracker pages not built (site.yaml, 2026-10-08)
    site_revs.site_dormant()             # "no presentation site yet (...)" while the project has none, else None
"""
from __future__ import annotations

from pathlib import Path

import repo_paths as rp
from model_build import last_revision

# The presentation builders (<project>/03_Working_Design/CAD/09_Presentation/). A project without them has no site yet.
BUILDERS = ("build_portal.py", "build_landing.py", "web_glbs.py", "portal_media.py", "presentation_materials.py")


def site_dormant(needs: tuple[str, ...] = ("build_portal.py",), site_repo: str | None = None,
                 presentations: Path | None = None) -> str | None:
    """Why the presentation site machinery is dormant on this project, or None when it can run.

    Dormant while project.yaml site_repo is `unknown` (or blank), or while a builder in `needs` is not in
    rp.PRESENTATIONS (CPME practice: the site framework stays, and skips cleanly until the project has a site)."""
    if site_repo is None and not rp.HAS_PROJECT:
        return "no presentation site yet (no project yet)"
    repo = (rp.SITE_REPO if site_repo is None else site_repo).strip()
    if not repo or repo.lower().startswith("unknown"):
        return "no presentation site yet (project.yaml site_repo is unknown)"
    folder = presentations or rp.PRESENTATIONS
    missing = [b for b in needs if not (folder / b).is_file()]
    if missing:
        try:
            where = rp.rel(folder)
        except ValueError:
            where = str(folder)
        return f"no presentation site yet ({where} has no {', '.join(missing)})"
    return None

# publish_site.py argument -> filed document folder (<project>/06_Issued_Revisions/Portals/<doc>/revisions.csv)
DOCS: dict[str, Path] = ({"rev": rp.PORTAL_FILED, "quoting": rp.QUOTING_FILED, "landing": rp.LANDING_FILED,
                          "mobile": rp.MOBILE_FILED}   # Mobile Optimized, mobile/ (Bob, 2026-10-17)
                         if rp.HAS_PROJECT else {})    # no project yet: nothing filed, nothing to publish


def newest(docs: dict[str, Path] | None = None) -> dict[str, str | None]:
    """{"rev", "quoting", "landing"} -> the newest filed revision letter of each, or None if none is filed."""
    return {k: last_revision(root) for k, root in (docs or DOCS).items()}


def _site_list(key: str, config: Path | None) -> tuple[str, ...]:
    if config is None and not rp.HAS_PROJECT:
        return ()
    p = config or rp.SITE_CONFIG
    if not p.is_file():
        return ()
    import yaml
    d = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    v = d.get(key) or []
    if isinstance(v, str):
        v = [v]
    return tuple(str(x).strip() for x in v if str(x).strip())


def hidden_models(config: Path | None = None) -> tuple[str, ...]:
    """Model IDs kept off the site (<project>/03_Working_Design/CAD/09_Presentation/site.yaml hidden_models, e.g. a
    retired model): the one reader for build_portal.py (revision picker) and publish_site.py (store files). No file,
    no key or an empty list: nothing hidden."""
    return _site_list("hidden_models", config)


def hidden_pages(config: Path | None = None) -> tuple[str, ...]:
    """Tracker pages left out of the build (<project>/03_Working_Design/CAD/09_Presentation/site.yaml hidden_pages, by file stem, e.g. "quote";
    Bob, chat, 2026-10-08: "REMOVE QUOTE PAGE ENTIRELY, WE MAY ADD IT BACK LATER"). build_portal.py writes no such
    page and no nav entry, tile or link to it; a filed revision built that way holds no such file, so publish_site.py
    never carries it. No file, no key or an empty list: every page is built."""
    return tuple(s.removesuffix(".html") for s in _site_list("hidden_pages", config))


def publish_args(revs: dict[str, str | None]) -> list[str]:
    """publish_site.py arguments naming each revision explicitly. No quoting portal filed: "--quoting none" (the
    pre-Phase 6 layout); no landing page: publish_site.py's own default (it then falls back the same way)."""
    if not revs.get("rev"):
        raise ValueError("no project-portal revision is filed")
    args = ["--rev", revs["rev"], "--quoting", revs.get("quoting") or "none"]
    if revs.get("quoting") and revs.get("landing"):
        args += ["--landing", revs["landing"]]
        args += ["--mobile", revs.get("mobile") or "none"]
    return args
