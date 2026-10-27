# Engineering Harness (master)

The one master copy of the CPME skid design harness (Bob, chat, 2026-10-27). Every job repo (one per product line,
TR-09) carries an identical copy of the harness-owned files listed in `harness/harness-manifest.txt`: `harness/`,
`.claude/agents/`, `.claude/skills/`, `.claude/settings.json`, `CLAUDE.md`, `.github/`, `.gitattributes` and the core
`.gitignore` lines. Everything about a product or a project lives in that job's own `job/` folder, never here.

## Start a new job

```
<job repo>\harness\tools\venv\Scripts\python.exe "C:\Users\Bob\Documents\Engineering Harness\harness\scripts\job_new.py" <new folder> --name "<Job name>" --repo <owner/name>
```

It copies the harness from this master, writes the job's `job/JOB.md`, `job/drive-store.yaml`,
`job/carryover-terms.txt`, the component library, the `job/design-rules/` and `job/knowledge/` stubs and the question
files. Add `--project Project-<code>-<TYPE>-<nnn>` to make the first project. Skill: `job-bootstrap`.

## Change the harness

1. Make the change **here**, in this master, never only in a job.
2. In each job repo: `harness\scripts\harness_sync.py check .` lists what differs from the master;
   `harness\scripts\harness_sync.py pull .` copies the master's harness files in (job-owned files are never touched).
3. Commit the pulled files in the job on Bob's go, like any other change.

A change first made inside a job is brought here with `harness_sync.py seed --master "C:\Users\Bob\Documents\Engineering Harness" --force`
from that job, then pulled into the other jobs.

## What belongs here

Only what is true for every CPME skid job: filing and revisions, git, Linear and Drive, the project folder template,
the title block, the checks, the company-wide design rules, Todd Requirements, and the agents and skills written for
any product. A job's product (what it holds, how it is designed, its own rules and review items) goes in that job's
`job/JOB.md`, `job/knowledge/` and `job/design-rules/`.

## Repo

`origin` is `https://github.com/Bob-Biedrzycki/Engineering-Harness.git` (Bob, chat, 2026-10-27). Never push to any
other repo. A harness change is committed here on Bob's go, then pulled into each job with `harness_sync.py pull`.
