---
name: github-tracking
description: The daily commit, push and one-per-day pull request for this job's repo (one repo per job, TR-09; the job's repo is named in job/JOB.md), and GitHub status, through harness/scripts/track.py, which wraps the gh CLI with Bob's rules built in. Use for any commit, push or PR work in this repo. Work tracking moved to Linear on 2026-09-28; GitHub issues and milestones are retired. Only the project-manager (scrum master) runs it.
---

# GitHub tracking (scrum master)

All GitHub work in this repo goes through `harness/scripts/track.py`. Never call `gh`
or `git push` directly, and never do issue or PR work in the browser pane
unless Bob asks. The tool enforces Bob's rules so they cannot be skipped:

- **One PR per day, never one per file or change** (Bob, 2026-09-24).
- **Name before running.** Every commit, push and PR is named to Bob in chat first. It runs only with his go, passed verbatim
  as `--bob-go "<Bob's words>"`. Never write a go Bob did not give.
- **No closing keywords by accident.** "Closes #7", "fixes #3" or "please
  close #7" are refused unless that issue is passed with `--closes`, and
  `--closes` only when the whole issue is satisfied.
- **Shared checkout.** Several sessions share the working tree. The tool
  commits in a separate git worktree and never switches, resets or commits
  in the shared tree.
- **Credentials are Bob's, and the sign-in is a one-time event.** The tool
  uses the `gh` sign-in (`Bob-Biedrzycki`, the one writer since 2026-10-07)
  and never reads, prints or stores a token. The token stays in the Windows
  keyring; nothing in the daily cycle needs a new sign-in. If `status` says
  NOT signed in, or the `workflow` scope MISSING, paste the one command
  `status` prints (the sign-in script by its full path, runnable from any
  window) to Bob and stop. **Never hand Bob a raw `gh auth ...` or `git
  push` command to type** (Bob, 2026-10-07). Never sign in yourself.

  The script (`harness/scripts/gh_signin.ps1`) signs gh in with the
  `workflow` scope (needed to push any change to `.github/workflows/`) into
  `%USERPROFILE%\.config\gh`, persists `GH_CONFIG_DIR` as a user environment
  variable so every window opened afterwards reads that folder, and exits
  at once when the sign-in is already there. Every window uses that one
  folder (Bob, 2026-10-06): the desktop app's shells see a virtualized
  `%APPDATA%`, so gh's default config there was a different file from Bob's
  terminal's. `track.py`, `publish_site.py` and `sync_labels.py` set
  `GH_CONFIG_DIR` for every `gh` and `git` call unless it is already set;
  `.claude/settings.local.json` `env` sets it for agent shells. `daily-push`
  and `daily-commit` (not `--local`) refuse up front when the push changes
  `.github/workflows/` and the sign-in lacks `workflow`.

Run every command from the repo root with the repo venv:
`.\harness\tools\venv\Scripts\python.exe harness\scripts\track.py <command>`. Add `--dry-run`
(before or after the command) to see what would be sent without sending it.
`--as-bob` is accepted and ignored.

## Read-only commands (no go needed)

| Command | Use |
|---|---|
| `status` | Repo, gh config folder, sign-in state, `workflow` scope, writer account, current branch of the shared tree. Run it first, every time. |

## No GitHub issues or milestones (Bob, 2026-09-28)

Agent work is tracked in **Linear**, not GitHub issues (CLAUDE.md notice,
TR-12, C-06); `track.py` has no issue or milestone commands. The daily PR
names Linear issue IDs (`Relates to <ID>`, `Fixes <ID>` only when the whole
issue is done).

## A new job repo: the first commit (once, on Bob's go)

A new job repo on GitHub is empty: it has no `main`, so `daily-commit` has
nothing to build the day's branch on. Once, before the first day's commit:

```
track.py init-main --bob-go "<Bob's words>"
```

It pushes one **empty** commit (no files, documented message) as `main`, sets
the local `main` to it, and fetches. No working-tree file changes; everything
stays untracked until the first daily PR merges and `sync-main` runs. It
refuses when origin already has any branch or local `main` has a commit, so it
can never write over work. Run `--dry-run` first. Then the day goes as below.

## The daily commit and PR (end of day, on Bob's say-so)

The commit follows close-out (skill `closeout`,
`harness/scripts/closeout.py`): the Drive push,
checks and portal filing are done first, and close-out writes the starting
points for steps 1 and 2 below, `<project>/_work/daily/<date>-paths.txt` (candidate
paths; review them, other sessions share the checkout) and
`<project>/_work/daily/<date>-commit.md` (the commit body skeleton with the day's
filed revisions, checks and `--tag` list). Never commit before close-out has
pushed the day's large files.

**One go for the whole end of day** (Bob, 2026-10-07, verbatim: "THIS
SHOULD BE 1 "GO" THEN MY MERGE. THE SYNC SHOULD BE AUTOMATED." and, on the
site publish, "IT SHOULD BE INCLUDED AS PART OF THE PROCESS FOR THE DAY'S PR,
AND NOT REQUIRE A SECOND APPROVAL"). Before asking Bob anything, run
`closeout.py --dry-run`, write the paths file, the commit message and the PR
body, and run `publish_site.py --rev <newest portal> --dry-run`. Then name
the whole set to Bob in **one message**: close-out; the commit (branch,
number of paths, tags); the PR title; and what follows his merge
(`sync-main`, and, once the job has a site, the site publish when the dry run
shows a portal, quoting or landing revision newer than the site holds). Bob answers **once**. His
words go verbatim into `<project>/_work/daily/<date>-go.txt` and are passed as
`--bob-go` to every command of the day: close-out, `daily-commit`,
`daily-pr`, then after the merge `sync-main` and `publish_site.py`. No
second question for any of them; a refusal is fixed and rerun with the same
go. Bob's only action after the go is the merge on GitHub. In the steps
below, "with the day's go" means those words from the go file.

**The site is dormant until the job has one.** The site framework (project tracker,
quoting/estimating portal, landing page) is dormant
until Bob defines the job's presentation site (Bob, chat, 2026-10-26: a site/portal
is planned). While `site_repo` is `unknown` and no portal is filed, the site
publish has nothing to do and is left out of the message to Bob until the job
has a site. The steps below that name the site, the portals or
`publish_site.py` apply from then.

1. **List the day's paths** in a file, one repo-relative path per line, no
   wildcards. Include every file the day changed that belongs in the repo:
   registers, lists, rules, knowledge, agents, scripts, and each filed
   drawing folder under `<project>/06_Issued_Revisions/Drawings/`. Leave out `<project>/_work/`,
   `harness/tools/venv/` and anything another session owns and has not finished. Deleted
   files are not carried over; name them to Bob. A tracked file that must stop
   being tracked (for example a large file moved to the Google Drive store,
   CPME practice) goes in a second file, one path per line, passed as
   `--removes-file`; the commit records its removal from the index and the
   working tree keeps the file. Large files never go in the paths file: run
   `harness/scripts/drive_store.py pointers` and list the `<file>.drive`
   pointers instead.
   **The tool enforces it**, so a large file moved to the Drive store can
   never be committed because `.gitignore` was left out. Before any worktree
   exists, `daily-commit`
   (and so `daily`):
   - adds `.gitignore` to the paths, with one `paths: added .gitignore`
     line, when the checkout's copy differs from the branch's only inside
     the drive-store managed block. A change outside the block prints a
     `WARNING:` and is not added; list it yourself if it belongs;
   - expands every listed path (folders walked) and refuses, exit 2 with a
     `REFUSED:` list, any file the Drive-store rules select
     (`harness/lib/drive_rules.py`, the same rules as `drive_store.py` and
     CI's `drive_pointers.py`) unless its `.drive` pointer exists, the
     `.gitignore` the commit carries ignores it, and the branch does not
     still track it. Each line names the pointer to list instead. Files that
     pass stay out of the worktree and the add; a large file listed by name
     is replaced by its pointer.
2. **Write the commit message** to a file. The subject is at most 72
   characters. The body has these sections, each required: **Why**,
   **Changed IDs**, **Sources and rules cited**, **TR rows touched**,
   **Drawings filed**, **Checks run** (CLAUDE.md, TR-11).
3. **Write the PR body** from `.github/pull_request_template.md`: the date,
   `Relates to <ID>` for each Linear issue advanced, every change of the
   day with its IDs, drawings filed, checks, and the **Todd's requirements**
   compliance list. The tool refuses a body without the "Todd's requirements"
   and "Drawings filed" sections.
   **Linear issues named** (TR-12; Bob, 2026-10-07): the body names each
   Linear issue the day advanced (`Relates to CPM-nn`). The tool prints
   `Linear issues named: CPM-nn, ...` when it does; when the body names none
   it prints a `WARNING:` with the day's issue ids (from today's
   `<project>/_work/daily/<date>*` handoffs and `<date>-linear.json`) and carries on.
   Never a refusal; the dry run in step 4 shows it before anything is sent.
4. **The day: one command, on the one go** (the normal path, from
   2026-10-07). First the dry run, before asking Bob (it runs
   `closeout.py --dry-run` and the commit and PR dry runs, needs no
   `--bob-go`, and writes no go file):
   ```
   track.py daily --date <YYYY-MM-DD> --paths-file <paths> --message-file <msg> --title "Daily <date>: <summary>" --body-file <body> --tag <DOC-ID>-rev<X> --dry-run
   ```
   Then, on Bob's answer, the same command with his words and no `--dry-run`.
   It checks every input first (paths, message sections, PR body, closing
   keywords; the same rules as `daily-commit` and `daily-pr`), saves the go
   verbatim to `<project>/_work/daily/<date>-go.txt` (refused if that file already
   holds different words), runs `closeout.py --bob-go "<go>"`, then the commit
   and the PR with the same go, and prints `PR: <url>` on its own line. Bind
   that URL to the desktop app's PR monitor (`mcp__ccd_pr__bind_pr`) so the
   merge reaches this session without polling.
   - **Close-out exits non-zero: nothing is committed** and `daily` exits
     with close-out's code and says what next. Exit 3 is the list delta
     (process-engineer updates the lists, then rerun the same command); 1 is
     a broken check, a repo-integrity check or a failed step (fix, rerun); 2
     is a refusal. Design findings are warnings, as in CI, and do not stop
     it. A rerun with the same go is fine; close-out does not refile what it
     filed today.
   - **Once the job has a site, name the document folders close-out files into** in the paths file
     (`<project>/06_Issued_Revisions/Portals/project-portal`, `<project>/06_Issued_Revisions/Portals/quoting-portal`,
     `<project>/06_Issued_Revisions/Portals/portal-landing`), not a revision folder that does not exist
     yet. After close-out, `daily` refuses if a revision filed under
     `<project>/06_Issued_Revisions/Portals/` today is not covered, because after-merge could not
     publish it.
   - **Never pass `<date>-commit.md` or `<date>-paths.txt`**: close-out
     rewrites both (its skeleton) during the run, so `daily` refuses them.
     Copy the edited message to another name (e.g. `<date>-commit-final.md`).
     A message still holding a skeleton placeholder (`<fill: ...>`) is
     refused.
   - One `--tag` per drawing revision filed that day, for example
     `--tag <PID-DOC-ID>-revA` (the project's P&ID, `rp.PID_DOC_ID`, e.g.
     `0000-00-TST-001-PID-001-revA`).
   - **The writer is `Bob-Biedrzycki`** (Bob, 2026-10-07), the one writer. Bob approves and merges the daily PR himself (Bob,
     2026-09-29). No flag is needed.
   - Only one open PR per `daily/<date>` branch. The tool refuses a second
     one while the first is open (or was closed unmerged); push more commits
     to the open PR instead. Once the day's PR has merged, later work the
     same day goes on the same branch and a new PR on Bob's go (Bob,
     2026-09-29). Never merge. The engineer reviews and merges on GitHub.
5. **After the merge: one command, the same go, no new ask** (Bob,
   2026-10-07: "THE SYNC SHOULD BE AUTOMATED." and "IF THE ORIGINAL PR WAS
   APPROVED, THE CONTENT HAS ALREADY BEEN APPROVED AND IT SHOULD BE DONE.").
   The trigger is the app's merge event on the bound PR, or Bob saying it is
   merged:
   ```
   track.py after-merge --date <YYYY-MM-DD>
   ```
   It reads the go from `<project>/_work/daily/<date>-go.txt` (refused if missing),
   checks with gh that the day's PR merged and none is still open (refused
   if not), runs `sync-main` with that go, then (once the job has a site; the
   site framework is dormant until Bob defines the job's presentation site) runs `publish_site.py --dry-run` with the newest filed project-portal, quoting-portal and
   portal-landing revisions (`harness/lib/site_revs.py`, the same reader as
   close-out step 9) and publishes for real, with the same go, only when the
   dry run shows anything added, changed or removed on the site. Each step
   prints one result line (`go:`, `PR: merged`, `sync-main:`, `site:`).
   While the job has no site, the publish step skips cleanly and `site:`
   says so; that is not a failure.
   `--dry-run` runs the sync and publish dry runs only. **Known block
   (2026-10-07):** the desktop app's permission classifier refuses
   `publish_site.py` from an agent shell as a production deploy. When the
   publish is refused or fails, `after-merge` prints the exact
   `publish_site.py ... --bob-go '<go>'` command and exits 2; report that
   command in the handoff and stop there. Agents never add a permission rule
   to `.claude/settings.json` themselves.
6. **Fallback: the single commands**, with the day's go from the go file,
   when one step must be rerun alone (for example the PR after a refusal,
   since rerunning `daily` would find nothing new to commit):
   ```
   closeout.py --bob-go "<Bob's words>"
   track.py daily-commit --date <YYYY-MM-DD> --paths-file <paths> --message-file <msg> --tag <DOC-ID>-rev<X> --bob-go "<Bob's words>"
   track.py daily-pr --date <YYYY-MM-DD> --title "Daily <date>: <summary>" --body-file <body> --bob-go "<Bob's words>"
   track.py sync-main --bob-go "<Bob's words>"
   publish_site.py --rev <X> --quoting <Y> --landing <Z> --bob-go "<Bob's words>"
   ```
   **Push refused or no network?** `daily-commit --local` puts the commit
   and tags on the local `daily/<date>` branch only, with no sign-in and no
   push. Later, push with the day's go,
   `track.py daily-push --date <YYYY-MM-DD> --bob-go "<Bob's words>"`, which
   pushes the branch and its drawing tags. Later commits the same day build
   on the local branch, never reset it.

   **Sync** (Bob, 2026-10-02: "an ongoing problem"). The commit was made in a worktree, so the checkout's
   `main` did not move and the merged files sit there as identical untracked
   or modified copies; `git merge --ff-only` and `git pull` refuse to step
   over them, and the checkout then reads stale rule files and reports
   merged work as uncommitted. Run:
   ```
   track.py sync-main --dry-run
   track.py sync-main --bob-go "<Bob's words>"
   ```
   It fetches (in the dry run too), proves every local difference is already
   in `origin/main`, then does a **mixed** reset (branch and index move, no
   file is written), refreshes only files whose local copy still equals the
   old HEAD, and stops with a list if anything else differs. A refusal
   listing files that are the day's uncommitted work means that work goes
   in the next commit and PR first; then sync again. Never `git stash`,
   `git reset --hard` or `git checkout .` in the shared checkout to get past
   the refusal: other sessions' unfinished work lives there.

## When something is refused

The tool prints `REFUSED:` and the reason, and exits 2. Fix the input and
rerun. Do not work around a refusal with raw `gh` or `git`. If a rule itself
looks wrong, raise it with Bob in chat.
