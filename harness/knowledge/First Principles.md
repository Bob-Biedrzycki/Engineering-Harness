# First principles: how the structure decides

Bob, "Migration Cleanup.csv", 2026-11-11: this analysis "needs to live in the appropriate guiding places to
eliminate any questions as to how the flow and decision making process works" (Approved). It was written while an
earlier job was moved onto this layout, and it holds for every CPME job.

When something does not fit, is missing, or could go in two places, work it out from these seven principles before
asking. Each one names the rule in CLAUDE.md it comes from, so this file adds no rule; it says why the rules are
what they are and how to apply them to a case they do not name.

## The seven principles

1. **One place per fact.** If two files state the same thing, one of them is wrong sooner or later. Find the
   authoritative file and point at it; never restate it. (Hard rule 8; "Where things are tracked".)
2. **A thing lives at the level where it is true.** Company-wide goes in the harness, every project of the product
   line in the job, one order in the project. The test for job against project: *would it hold for a different
   customer's order of the same product?* If yes, job. If it depends on this order's lines, tags, equipment,
   customer or decisions, project. Tools live at the level of what they compute for; an order's results live in
   the order's project folder. (Three levels: `harness/design-rules/README.md`; hard rule 11.)
3. **The master flows down.** A job never fixes or forks the harness. A harness change is made in the Engineering
   Harness master, tested there, and pulled (`harness_sync.py`). A job that is behind pulls; it does not patch.
4. **Filed things never change.** A fix to anything a filed revision depends on rides the next revision. If a
   correction would alter a filed file, or the bytes a filed file was built from, it is recorded as open and made
   with the next letter. (TR-08; hard rule 6.)
5. **A check either checks or says it did not.** "PASS" with nothing measured is worse than no check. A check
   that cannot run on a project reports "not checked" with the reason, and the reason is then removed at its
   source (the data or the format), not by quieting the check. Checks report; they do not block.
6. **Unknown stays unknown until it is given.** Nothing is invented to fill a folder, a field or a schedule. An
   empty folder is correct until there is work for it; a generator is written when its drawing is asked for; a
   record is finished when the part is used, not because the column exists. (Hard rules 1 and 5.)
7. **Bob decides; agents draft.** Rule levels, gates and Todd's rows are his. Everything else an agent decides
   from these principles, does, and reports in a line. (Hard rules 7, 11 and 12; Approval Ladder.md.)

## How to use them

- **Before asking Bob a question**, check whether a principle already answers it. If it does, act and say which
  principle you used. Ask only when the answer is his under principle 7, or when two principles pull apart and the
  choice would be hard to undo.
- **Hard rule 11 still stands**: a new rule, a new value field or a move between levels is asked of Bob first. The
  recommendation that goes with the question is the result of the test in principle 2, stated in one line.
- **When a job is moved onto this layout or falls behind it**, sort every difference into one of four bins:
  fixed now (principles 1, 3, 5); rides the next revision (4); correct as it is (6); Bob's word (7). Nothing is
  left outside a bin.

## Worked cases (a job moved onto this layout, 2026-11-11, each approved by Bob in "Migration Cleanup.csv")

| Case | Principle | How it was handled |
|---|---|---|
| A check printed "PASS - not checked" because the project's rule files gave the scope in words | 5, 3 | The scope was written in the form the master reads; no value changed; the result was compared with the earlier repo's |
| No job-level rules existed | 2 | Only entries that hold for any customer's order went to the job level; values keyed by one order's tags stayed in the project |
| A calculation read a retired model revision in the archive folder | 4 | The old calculation stays history; the gate gets a fresh run on the current revision |
| Stale paths inside a file whose bytes name filed web models | 4 | Left as filed; changed with the next model revision |
| Component records unfinished | 6 | Finished for the parts the filed model places; the other rows are library stock and are not reported until Bob asks |
| The job's harness copy was behind the master | 3 | Pulled; never patched in the job |
| The job's instructions told the story of the move and contradicted themselves | 1 | The instructions say only what is true now; the story went to a migration record |
| Customer name written three ways | 1, 6 | Identity lives in `project.yaml`, as on the filed revision; other files point at it |
| Schedule had no dates | 7, 6 | Only the date Bob gave was entered; the rest stays `unknown` |
| Empty engineering and drawing folders | 6 | Correct as they are |
