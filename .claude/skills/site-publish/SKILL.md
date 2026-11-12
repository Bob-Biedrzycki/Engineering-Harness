---
name: site-publish
description: How harness/scripts/publish_site.py publishes the filed project tracker, landing page and Mobile Optimized (and, on a project whose builders make them, the Fabrication Estimating Portal and the customer site) to the presentation site repo - a daily branch in the site repo whose end-of-day merge is the publish, the site repo's own upstream commits (carry or refuse), its packager run as a check, and the publish notes (codes, publish-notes.json schema). Use before any publish_site.py run, dry or real, and when reporting its upstream, site packaging or packaging note lines.
---

# Site publish (`publish_site.py`)

The site framework is CPME practice and **dormant until Bob defines the job's site**: while
`site_repo` in `<project>/project.yaml` is `unknown`, or the builders are not in
`<project>/03_Working_Design/CAD/09_Presentation/`, `publish_site.py` prints
`no presentation site yet (...); nothing published` and exits 0. That skip is not a defect.

## What a site holds

Every site is the **project tracker** (`tracker/`), its **landing page** (the site root) and
**Mobile Optimized** (`mobile/`). A project whose builders also make them publishes:

- the **Fabrication Estimating Portal** (record ID `quoting-portal`, site folder `estimating/`),
  when `portal_lib/quoting.py` is among the builders;
- the **customer site** (record ID `customer-portal`, site folder `customer/`), when
  `portal_lib/customer.py` is. It is filed only on Bob's word, never by close-out, and reached by
  its direct link (or an unlabeled landing tile); its pages carry robots noindex.

`harness/lib/site_revs.py` `portals()` is the one test of which a project has. A project without
the estimating portal takes `--quoting none` (always passed by `site_revs.publish_args`) and
refuses any other value; one without the customer site refuses any `--customer` but `none`.

## The publish is a daily branch; its end-of-day merge is the publish

Bob, chat, 2026-11-09: "change publish_site.py to push to a daily branch in the site repo.
Then your merge is the publish, which settles the trigger question with no special
exception. It also needs to stop using git add -A."

- A real run builds the publish commit on `daily/<YYYY-MM-DD>` in the site repo
  (`rp.SITE_REPO`). It works in a short-lived worktree beside the site checkout, stages every
  file by name (`git rm` for removals, `git add` for the rest), and pushes that branch only. It
  never commits or pushes to the site's `main` and never forces.
- The branch builds on `origin/main`, or on `origin/daily/<date>` when an earlier publish today
  is not merged yet.
- **When Bob says his day is over, the end-of-day merge of `daily/<date>` into the site's `main`
  is the publish** (global "Git and backup"). The site repo's own workflows run on that push to
  `main`.
- The site checkout (`rp.PRESENTATION_SITE`) is never written or moved by a publish.
- The filed folders must already be saved, byte for byte, on the design repo's
  `origin/daily/<date>` (saved today with `track.py save`) or `origin/main`. Otherwise the
  real run refuses and the dry run warns.

## The command

```
publish_site.py --rev <X> --quoting <Q or none> --landing <L> --mobile <M> [--customer <C>]
```

No go is needed to push the branch: it changes nothing live, and Bob's end-of-day word is the go
(`--bob-go` is optional and, when given, recorded in the site commit body). Run `--dry-run`
first and name its `upstream:`, `site packaging:` and `packaging note:` lines to Bob before the
push, so he sees them before he merges.

Each value is the newest filed revision (`harness/lib/site_revs.py`, the same reader as
close-out step 9). `--landing none` lays out the tracker alone at its filed name with a root
redirect. A dry run may name a customer revision not filed yet: it shows `customer/` in the
layout and leaves it out of the file plan; the real run refuses. Add `--dry-run` to see the
plan; it writes nothing but a fetch in the site checkout and scratch files under
`<project>/_work/site-check/`.

## The site repo's own commits (upstream)

The site repo's owners may push their own commits, for example a packaging workflow under
`.github/`. `publish_site.py` fetches `origin main` in the site checkout and names every commit
on `origin/main` since the last publish (a `Site: ...` commit or the merge of a `daily/<date>`
branch): hash, author, date, subject, files; `KEEP-only` or `TOUCHES PUBLISHED CONTENT`. The
real publish then:

- **carries** KEEP-only commits (`.github/**`, `.gitattributes`, `README.md`): the branch is
  built on `origin/main`, so they are already in it;
- **refuses**, nothing written, when the site checkout is not on `main` or its tree is dirty,
  or an upstream commit touches published content. Bob settles it with the site repo's owners;
  never reset, rebase, force or hand-merge the site checkout.
- **runs the site repo's packager as a check**: after staging the tree in
  `<project>/_work/site-check/stage/`, the site's own `.github/packaging/package_portals.py`
  runs unchanged (`python -I`, `--site <stage> --out <project>/_work/site-check/packages`, the
  publish base's copy of the script). A failure stops the publish before anything is written,
  committed or pushed, with the packager's error text. A missing script is a warning. The dry
  run reports a failure as `WARNING site packaging` and never stops.

## Publish notes

Every publish is compared with the last one (the live site, `origin/main`; its
`publish-notes.json`, else its README and tree) and every anomaly gets a stable code, a
severity (`info` / `warn`) and one plain line:

`MODEL_ID_CHANGED`, `MODEL_REV_BACKWARDS`, `PID_ID_CHANGED`, `PORTAL_ADDED`, `PORTAL_REMOVED`,
`REV_SKIPPED`, `REV_BACKWARDS`, `CUSTOMER_LEFT_OUT` (only on a project with a customer site, or
when the last publish carried `customer/`), `UPSTREAM_COMMITS`, `PACKAGER_FAILED`,
`PACKAGER_WARNED`, `PACKAGER_NEW_FINDINGS`, `PACKAGER_NOT_RUN`, `PACKAGER_FINDINGS`,
`LARGE_REMOVAL` (a page folder loses over 25% and at least 3 files, or the site loses over 25%
and shrinks over 10% net; the shared `assets/` and `data/` churn on every publish, so no flat
file count), `NEW_FOLDER_NOT_PACKAGED` (a new top-level folder outside the packager's
`PORTALS`, read from its script without importing it).

They go in the site commit as a `Notes for packaging:` section after the unchanged subject
(`No anomalies.` when none) and in `publish-notes.json` at the site root (schema
`cpme-site-publish-notes/2`, documented in `publish_site.py` above `build_notes`; `/1`, written
before 2026-11-10, named the packager fields differently and is still read), rewritten every
publish, never KEEP, never counted as a site change, and not taken by the packager (the staged
check runs with it present). The dry run prints the commit message and the JSON exactly as they
would be written, plus `packaging note:` lines. Notes never stop a publish.

## What to report

The dry run's `upstream:` and `site packaging:` lines (the site repo's own commits and whether
its packager passes on the tree) and its `packaging note:` lines (the anomalies the publish will
note, or `packaging notes: no anomalies`). Close-out step 9 carries them into its step result
(`closeout.site_packaging_lines`). A content commit upstream or a packager failure means the
publish will refuse; say so before it runs.

## Who runs it

The main session runs the publish itself, never a subagent: the desktop app's classifier may
refuse `publish_site.py` from a subagent shell as a production deploy. When the publish is
refused or fails, report the exact `publish_site.py ...` command and stop there. Agents never
add a permission rule to `.claude/settings.json` without Bob's approval in chat (CLAUDE.md
"Tooling").
