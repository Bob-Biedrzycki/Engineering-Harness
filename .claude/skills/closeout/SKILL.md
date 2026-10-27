---
name: closeout
description: Tier 3 of the skid-model pipeline for the project, the daily close-out, run by the project-manager only on Bob's word. Runs every check, reviews the list delta, renders portal media and files the portal (once the job has a site; dormant until then), pushes the day's large files to the Google Drive store and verifies them, and writes the commit body skeleton. Use when Bob says to close out the day. Does not commit.
---

# Close-out (tier 3, once a day, on Bob's word)

**When.** On the day's one go (Bob, 2026-10-07; `github-tracking`): the
project-manager runs `--dry-run` first, drafts the commit message and PR
body, names close-out, commit, PR and the post-merge sync (and the site
publish, once the job has a site) to Bob in one message, and on his one answer runs close-out and then the
commit and PR with the same words. No separate go for close-out. Any number
of model iterations and filings may come before it.

**The one command** (repo root, repo venv). Normally `track.py daily`
runs it for you with the day's go, then the commit and PR (`github-tracking`
step 4); run it alone only as the fallback:

```
.\harness\tools\venv\Scripts\python.exe harness\scripts\closeout.py --bob-go "<the day's go>"
```

**Exit codes.** 0 done; 1 done but a step failed, a check is broken, or a
repo-integrity check (`drive_pointers`) failed; 2 refused; 3 stopped at the
list delta. Checks are judged as CI judges them (`run_checks.sh`; Bob,
2026-10-07: "The PR should not be flagging design findings."): a design
finding (exit 1 with the `<name>: FAIL` summary) is a `WARN` row, not a
failure, so it never stops `track.py daily`.

Run `--dry-run` first: it lists every step and the pointers push would copy,
and changes nothing. `--frame-calc` also reruns the frame calc (about 20 min;
its input revision is named in `frame_calc.py`). The portal flags below
belong to the site framework (project tracker, quoting/estimating portal,
landing page), dormant until Bob defines the job's presentation site. One refile flag per document, and neither implies the other: `--refile-portal` files the project
tracker (project-portal) again when it was already filed today for the same
model revision; `--refile-quoting` files the quoting portal again when it was
already issued for the same model revision. The landing page is filed only
when it changed (`build_landing.py`).

**Steps.** (1) every `harness/checks/*.py`, as CI, except `portal_terms.py`,
which runs at the end of step 5 on the portal revision just filed; (2) frame-calc basis vs the
newest filed revision; (3) list delta of the newest filed revision vs the lists:
non-empty means it is appended to `<project>/01_Design_Basis/06_Assumptions_Open_Items/pid-revision-requests.md` and
close-out STOPS (exit 3) for the process-engineer step, then you rerun it;
**(4), (5) and (9) are the presentation site, dormant until the job has one**: the
site framework (project tracker, quoting/estimating portal, landing page) is
dormant until Bob defines the job's presentation site (Bob,
chat, 2026-10-26: a site/portal for the job is planned; while `site_repo` in `project.yaml` is `unknown` and the project's
`09_Presentation/` has no builders). Until then each prints one skip line and is not a failure.
Once the job has a site: (4) the looks line for the newest filed GLB
(`looks: n of m required instruments realistic; missing: ...`,
`materials.yaml` `required_looks`; read-only, also in `--dry-run`, a report
in Checks run, never a failure), then portal media (Blender) if missing; (5)
`web_glbs.py --rev <newest>`, the viewer's web GLB for the newest filed
revision only (Bob, 2026-10-12: older revisions are not rebuilt for a look
change; a current revision with no current-look GLB is a `WARNING web GLB`
row, reported, not a stop), then `build_portal.py --file` (the tracker), the
quoting portal once per model revision, and the landing page if it changed;
each portal files its content-hashed shared assets, listed in the revision's
`shared-assets.json`, into
`<project>/06_Issued_Revisions/Portals/<portal>/assets/`,
append-only; (6)
`drive_store.py pointers`, `push`, `verify` (nothing goes outside the repo
before this; push runs after the portal so its large files go too); (7)
Linear loops (TR-12; Bob, 2026-10-07; `harness/lib/linear_loops.py`): today's
`<project>/_work/daily/<date>*` `.md`/`.txt` handoffs and today's `Agent-to-Agent Questions.md` entries
with no `CPM-nn`, issues touched today with no comment today, `NEXT:` lines
naming an agent with no issue opened for it today, and handoffs saying
`LINEAR: unavailable`. Read-only, so it also runs in `--dry-run`. **Warnings
only**: never a failure, never a change to the exit code; (8)
`<project>/_work/daily/<date>-commit.md` (Why, Changed IDs, Sources and rules cited,
TR rows touched, Drawings filed, Checks run, Linear loops, `--tag` list) and
`<project>/_work/daily/<date>-paths.txt` (candidate paths); (9)
`harness/scripts/publish_site.py --rev <P> --quoting <Q> --landing <L> --dry-run`,
each the newest filed revision (`harness/lib/site_revs.py`): the
presentation site publish plan (C-08), dormant as above; it publishes the listed
shared assets as the site's `assets/` and only the data-store files the
published pages reach (the dry run names how much is left off). Publishing runs after
the day's PR merges, on the day's go, with no new ask (Bob, 2026-10-07):
`track.py after-merge`.

**Linear export, written first.** `closeout.py` has no Linear access, so before
running it the project-manager reads the day's issues with the
`mcp__linear-server` tools and writes `<project>/_work/daily/<date>-linear.json`
(`--linear-json <path>` names another file):
`{"exported": "<ISO>", "issues": [{"id": "CPM-nnn", "title": "...",
"labels": ["role:software-developer"], "createdAt": "<ISO>", "updatedAt":
"<ISO>", "comments": [{"createdAt": "<ISO>"}]}]}`. Without it, step 7 prints
`LINEAR: unavailable (no export at ...)` and checks only the CPM refs.

**Never.** Commit, push to GitHub, open a PR or a Linear issue, run on its own
initiative, or fix a list delta by editing the model's output.

**Hand-off line.** Each step's result line (the `looks:` line among them), the checks with exit codes, what
was pushed and verified, the commit-body path. Under `track.py daily` the
commit and PR follow at once with the day's go; run alone, go straight on to
`track.py daily-commit` / `daily-pr` with that go (`github-tracking`).
