# Approval Ladder: what needs Bob's word

Company-wide (harness), filed at Bob's direction. Where this file and `CLAUDE.md` differ,
`CLAUDE.md` governs and this file is corrected. `<project>` below is the active project
folder, `job/Project-*`.

Every change in the repo sits on exactly one rung. The bottom rung is what agents do all
day without asking. The top rung is what only Bob can do.

## The Git words, in drawing-revision terms

| Word | What it is | Approval |
|---|---|---|
| Edit | Changing a file on the PC. Like marking up a drawing on the desk. Nothing is recorded. | none |
| Commit | A saved snapshot of the whole repo with a note of what changed and why. Like filing a revision of every file at once. "Committed" means the snapshot exists in Git's history; a written note by itself is only a draft. Goes on the day's branch `daily/<YYYY-MM-DD>`. | Bob's go (the day's one go) |
| Push | Copying the day's branch and its commits from the PC up to GitHub. Rides along with the commit. | Bob's go (same go) |
| Pull request (PR) | The transmittal. Asks GitHub to fold the day's branch into `main`, the released set. One per day; it holds all of the day's commits. | Bob's go (same go) |
| Merge | The approval stamp on the PR. The day's work becomes part of `main`. | Bob alone, on GitHub |

**Two different things both get called "approve".**

1. **Bob's go in chat.** A repo rule. Close-out, commit, push, PR, sync and site publish run
   only when `track.py` is handed Bob's words (`--bob-go`). One go a day covers all of them
   (CLAUDE.md "Work cycle" step 6).
2. **The desktop app's permission pop-up or filter.** The app asking "may this tool run?"
   before a command or file write, or its classifier refusing a command shape it has not
   seen allowed. A safety mechanism of the app, not a Git step. It is why prompts feel
   random. Allow rules in `.claude/settings.json` stop it for named commands (rung 2).

## The ladder, bottom to top

### Rung 1: agents do it, no ask
Everything that stays on the PC, inside the repo rules. Edit any source file. Run checks.
Build the model (tier 1, `model_iterate.py`). File the next model or drawing revision
(tier 2, `model_file.py` / `revfile.py`; next letter, read-only, never overwrite, TR-08).
Write lists, registers, questions, handoffs and DEC drafts. Open and comment Linear issues.
Make previews.

### Rung 2: Bob's decision, no Git involved
Engineering and policy calls, answered in chat or `Agent-to-Bob Questions.md`, then recorded.

- Which level a new design rule belongs at, harness, job or project (CLAUDE.md hard rule 11).
- DEC decisions. Gate 1 to 4 sign-off. Resolving a HOLD or a question addressed to Bob.
- A new tool on an agent's `tools:` line (effective next session).
- **Permission rules in `.claude/settings.json`** (Bob, 2026-10-07, verbatim: "I CAN NOT
  EDIT A JSON. YOU'RE APPROVED, PLEASE MAKE THE CHANGE, AS WELL AS, OPEN IT UP FOR FUTURE
  CHANGES WITH MY PERMISSION." and, for the end-of-day commands, "YES, ADD THE RULE").
  When the app's filter blocks a command the repo allows, the agent names the exact
  command and the one allow rule it needs, in chat; Bob says yes in chat; the agent adds
  that rule itself, no wider than the named command, cites Bob's words in the handoff and
  the commit body, and runs the command. Bob never edits the JSON. Agents never add a rule
  Bob did not approve for that command, and never one that touches `main`, force-pushes or
  merges (the `deny` list stays). Make the edit under the `update-config` skill; the
  app's filter can refuse a direct Edit of settings.json as "Self-Modification".

### Rung 3: Bob's go, named once a day
Anything that leaves the PC. The project-manager prepares everything first (close-out dry
run, paths file, commit message, PR body, publish dry run), then names the whole set to
Bob in **one message**: close-out, the commit (branch, paths, tags), the PR title, and
what follows his merge (sync, and the site publish when the job has a site and a newer
portal revision is filed). Bob answers **once**. His words are saved verbatim to
`<project>/_work/daily/<date>-go.txt` and passed as `--bob-go` to every command of the day.

| Command | Does | Runs |
|---|---|---|
| `track.py daily` | close-out (`closeout.py`: checks, list delta, portal filing, Drive push and verify), then `daily-commit`, then `daily-pr`; prints `PR: <url>` | on the go |
| `track.py after-merge` | `sync-main` (moves the shared checkout's `main` to `origin/main`), then `publish_site.py` when the job has a site and it differs | after Bob's merge, same go, no new ask |
| single commands (`closeout.py`, `daily-commit`, `daily-push`, `daily-pr`, `sync-main`, `publish_site.py`) | fallback when one step must be rerun alone | same go from the go file |

Bob's only action after the go is the merge on GitHub (Bob, verbatim: "THIS SHOULD BE 1
"GO" THEN MY MERGE. THE SYNC SHOULD BE AUTOMATED.").

### Rung 4: Bob alone
Review and merge the daily PR on GitHub. The one-time gh sign-in (the script that
`track.py status` prints; it must carry the `workflow` scope). Sign-ins to Linear, Google
Drive (rclone) and vendor portals. No agent can do these.

### Off the ladder: never, even if asked in passing
Push to `main`. Force push. Merge locally. Raw `gh` or `git push`. `git add -A`. Overwrite
a filed revision. Delete a tag. Hand Bob a raw gh or git command to type. Blocked by
`.claude/settings.json` `deny` or refused by `track.py`.

## By category

### Harness changes (`harness/`, `.claude/`, `.github/`, `CLAUDE.md`; reused by every job)
| Change | Rung |
|---|---|
| Scripts, checks, libraries, cad-lib tooling | 1 (edit and test; software-developer) |
| Agent files, skills, CLAUDE.md | 1 (edit; a `tools:` change takes effect next session) |
| New or moved design rule in `harness/design-rules/` | 2 (Bob picks harness, job or project first) |
| New tool on an agent's `tools:` line | 2 |
| `settings.json` permission rule | 2 (agent names command and rule, Bob says yes, agent adds) |
| CI workflow (`.github/workflows/`) | 1 to edit; reaches GitHub in the day's push (3); the one-time gh sign-in needs the `workflow` scope (4) |
| Getting any of it onto GitHub | 3 (daily commit and PR) |

### Job and project changes (`job/`: the job's knowledge and rules, and each project folder)
| Change | Rung |
|---|---|
| Lists, registers, questions, knowledge, DEC drafts | 1 |
| Sizing records where a project DEC brings sizing in (named in `job/JOB.md`) | 1 to draft; 2 for Bob to approve the selections |
| Model build (tier 1) into `<project>/03_Working_Design/Exports/build/` | 1, after every change |
| File model revision (tier 2) or drawing revision | 1 (next letter, never overwrite, TR-08) |
| Job or project design rule or value | 2 (Bob picks harness, job or project first) |
| DEC decision content, HOLDs, Agent-to-Bob Questions | 2 |
| Gates 1 to 4 | 2 (Bob alone signs) |
| Drive push of large files | 3 (inside close-out) |
| Getting any of it onto GitHub | 3 (daily commit and PR) |

### Site changes (portal builders, their media, the presentation site repo)

Dormant: the site is planned but the job has none yet (`site_repo` in `project.yaml` is
`unknown`, C-08), so `publish_site.py` finds no site and stops. The rungs apply once it exists.

| Change | Rung |
|---|---|
| Builder code (portal and landing builders) | 1 (software-developer) |
| Portal media render | 1 (inside close-out) |
| File a portal revision under `<project>/06_Issued_Revisions/Portals/` | 1 (inside close-out, next letter) |
| Portal wording and what fabricators see | 2 (Bob's preferences on record) |
| Publish to the presentation site repo | 3 (covered by the day's one go; runs after Bob's merge, no second ask) |
| Getting builder code onto GitHub | 3 (daily commit and PR) |
| The configurator | Off the ladder: out of scope (TR-26) |

## A normal day
1. **All day, agents:** edits, checks, builds, filed revisions, Linear comments. No asks
   for Git.
2. **End of day, Bob's one go:** the agent names the whole set in one message; Bob answers
   once ("GO").
3. **Then, agents:** `track.py daily` runs close-out, commit, push and PR with Bob's words.
   The PR is bound to the desktop app's PR monitor. If CI fails, the app wakes the session
   and the fix is pushed to the same PR under the Autofix authorization.
4. **GitHub, Bob:** review, click Merge. His only click of the day.
5. **After merge, automatic:** `track.py after-merge` syncs the shared checkout and, once
   the job has a site, publishes it when a newer portal revision is waiting. Same go, no
   new ask.

## Rule of thumb on "is it committed?"
The working folder shows committed files as "changed" until the sync step after the merge,
because commits are made in a side copy (worktree). "Changed on disk" and "committed" look
the same from inside the folder. An agent states commit status from `git log`, as a table
per change: committed? on GitHub? in `main`? A written commit note is a draft and commits
nothing.
