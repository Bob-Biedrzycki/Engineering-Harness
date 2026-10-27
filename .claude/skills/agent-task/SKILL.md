---
name: agent-task
description: Delegate a task to one of the repo's role agents (cad-design-engineer, process-engineer, mechanical-piping-engineer, controls-engineer, electrical-engineer, engineering-manager, project-manager, software-developer) the way Bob set up - check the agent's tools line against the task, open the Linear issue with the prompt verbatim, spawn, post the handoff, act on NEXT and CAPABILITY GAP. Use before every Agent call in this repo.
---

# Agent task (Bob, 2026-10-07: "do it")

Nothing blocks and nothing waits on Linear. One tool call to open, one to
comment, nothing else. No polishing of issue text.

## 1. Pick the role and check its tools

- Role = the owner of the deliverable (CLAUDE.md "The agent team").
- Read the agent's `tools:` line in `.claude/agents/<role>.md` against what
  the task needs (shell, browser, web search, Linear). A missing need is a
  one-line recommendation to Bob, never a workaround; edits to agent files
  take effect next session and need his approval.
- Browser work: run the agent in the foreground (background agents get a
  reduced tool set).

## 2. Write the prompt

Kept short:
- outcome, allowed files, acceptance checks;
- `Linear issue: CPM-nn` (filled in after step 3);
- which skill to follow (`component-add`, `pipe-route`, `model-iterate`...);
- if it edits a rule YAML: "add fields, never rename or remove keys; run
  pid_consistency.py";
- if it touches the model: "one revision for this batch, file, show, stop; no
  renders";
- the handoff ending: TR compliance list, `CAPABILITY GAP:` line, `NEXT:` line,
  then post the handoff verbatim as a comment on the issue.

## 3. Open the Linear issue before the Agent call

`save_issue`: team CPM, project = the project's Linear project
(the project's `linear_project` in `<project>/project.yaml`), title
`[<agent>] <task in a few words>`, label `role:<agent>`, milestone = the
gate if known, body = the prompt verbatim. Put the returned ID in the prompt.
(`list_projects` with milestones is too complex for the API; ask for
`fields=[id,name,status,url]`.)
Linear missing, not signed in or failing: go on and write
`LINEAR: unavailable (<reason>)` in your own handoff.

## 4. Spawn, then read the handoff

- The agent posts its handoff verbatim (`save_comment`). If it could not,
  post it yourself.
- `CAPABILITY GAP:` not `none`: map the need to an existing tool and give Bob
  a one-line recommendation.
- `NEXT:` names an agent: open that agent's issue now (same step 3) and start
  it, or say in your handoff why not. Per Bob, 2026-10-08, only a MUST-FIX
  starts a new model revision; reviewer SHOULD / NOTE items go in the one
  backlog issue.
- The project-manager audits and closes issues; the named agent never opens
  or closes one.

## 5. Report to Bob

Short: what was done (filed paths), checks, questions, assumptions, TR rows,
gap, next. Never a `<project>/_work/` path as the design.
