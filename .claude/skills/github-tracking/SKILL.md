---
name: github-tracking
description: How this repo carries out Bob's global git rules - saving and backing up work as it is done (track.py save - commit, Drive push, branch push), and GitHub status for this repo (the pull request and merge are the global end-of-day skill's) - through harness/scripts/track.py, which wraps the gh CLI. Use for any save in this repo. Any session or agent saves. Work tracking is in Linear; GitHub issues and milestones are retired.
---

# GitHub tracking (scrum master)

The git rules are only those in the "Git and backup" section of Bob's global instructions
(`%USERPROFILE%\.claude\CLAUDE.md`). This skill adds no rule; it is how this repo carries them out. `track.py` is
this repo's save tool. Never call `gh` or `git push` directly, and never do issue or PR work in the browser pane
unless Bob asks. What the tool does:

- **Saving is routine; the pull request is end of day's.** `track.py save` (commit, Drive push, branch push) runs as each piece of
  work is done, with no question (global "Git and backup").
  Every other write (the single fallback commands) runs only when Bob asks for it by name, his words passed as
  `--bob-go "<Bob's words>"`. Never write a go Bob did not give.
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

Agent work is tracked in **Linear**, not GitHub issues (CLAUDE.md notice);
`track.py` has no issue or milestone commands. The PR
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
stays untracked until the first PR merges and `sync-main` runs. It
refuses when origin already has any branch or local `main` has a commit, so it
can never write over work. Run `--dry-run` first. Then the day goes as below.

## Saving as you go: `track.py save` (any session or agent, no question)

Global "Git and backup": save as each piece of work is done. When a piece of work is done (a revision filed, a
script changed, a rule edited), save it:

```
track.py save --paths-file <paths> --message-file <msg> [--tag <DOC-ID>-rev<X>]
```

- **Paths:** this piece of work's files only, one per line, no wildcards (other sessions share the checkout). A
  Locked revision folder is listed whole; its large files go as pointers automatically.
- **Message:** the documented message `track.py` requires (subject at most 72 characters; Why, Changed IDs, Sources and rules
  cited, TR rows touched, Drawings locked (or "Drawings filed"), Checks run), written to a file outside `_work/daily`
  skeleton names.
- **What it does:** `drive_store.py pointers` and `push` (large files to Google Drive, verified), then the commit on
  `daily/<today>` in a separate worktree, pushed to GitHub (the same guards as `daily-commit`). CI runs the checks on
  that push. A Drive failure stops it before the commit.
- **Report** what it prints, the CI line included, then run `day.py status` and show that this piece of work's files are saved and backed up
  (global "Git and backup"). Never ask Bob before a save, and never bring it up as a pending step.

## End of day: not this skill (Bob, 2026-11-09)

The pull request, the wait for CI, the merge into `main` and bringing this checkout up to date are done for every
repo by the global `end-of-day` skill when Bob says his day is over (`Claude-Git-Tools\day.py end-day`; global "Git
and backup"). No session or agent opens a pull request, merges, or runs `track.py daily`, `daily-pr`, `after-merge`
or `sync-main` as part of a day; the section that described that day was removed on 2026-11-23 (REVW-001 OP-5).
Those commands are still in `track.py` and are run only if Bob asks for one by name. A site publish is
`publish_site.py` on its own (skill `site-publish`).

**CI is read, not assumed** (Bob, 2026-11-23). Every save ends with the checks' result on the day's branch, and so
do the session-start note and `day.py status`. On a `CI FAILED` line: read it with the command it gives, fix what a
save of yours broke and save the fix before anything else; if another session's save broke it, tell Bob in one
line. Never report work as done or passing while the branch is red or its checks are still running.

## When something is refused

The tool prints `REFUSED:` and the reason, and exits 2. Fix the input and
rerun. Do not work around a refusal with raw `gh` or `git`. If a rule itself
looks wrong, raise it with Bob in chat.
