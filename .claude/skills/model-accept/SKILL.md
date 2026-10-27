---
name: model-accept
description: Accept the fast edits on the project's skid model (rp.SKID_MODEL_ID, named in job/JOB.md) as the next model revision, with the project's P&ID, line segment diagram and PFD, in one scripted pass (harness/scripts/model_accept.py). Use only when Bob says he accepts, or would like to file, the fast edit as Rev <X>. Not for a part of it asked on its own (a support check, placing a part): those are fast edits.
---

# Model accept (Bob's word, one pass)

Applies once the model source and the P&ID, line segment diagram and PFD generators exist.

Bob, chat, 2026-10-15: "Make them all, they should be run progamatically and deterministically. A P&ID
revision should be part of the package." On open items: "Stop, list them ... it should not turn into a never
ending process like it does from time to time."

**The model is the source of truth** (Bob, chat, 2026-10-16: "This
process was supposed to work in a way that we made model edits, then when accepted, all of the lists and other
drawings get updated based on the model. you were supposed to be keeping notes ... not a list of questions for me
to answer prior to acceptance."). Acceptance never hands Bob a list to answer.

**When.** Bob says he will or would like to accept or file this fast edit as Rev <X>. Nothing else starts it. A
request for one part before that ("run your support check", "place the hanger") is that part only, as a fast edit
(`model-iterate`); never file, and never ask whether to do the rest (Bob, 2026-10-15).

**The one command**, in the main session, run in the background (it takes about 10 min when nothing is open).
Put Bob's words in a UTF-8 file first: PowerShell 5.1 splits quoted arguments.

```
.\harness\tools\venv\Scripts\python.exe harness\scripts\model_accept.py --rev <X> --bob-file <file>
```

What it does, with no judgement in between:
1. Preflight: a fast build with the pipe support check (always at acceptance, Bob 2026-10-15); its list delta is
   written into the <project>/03_Working_Design/PID/02_Tag_Lists lists (`harness/lib/list_from_model.py`: rows added, resized or removed as the model
   has them, `unknown` where the model says nothing); a second fast build confirms it, with the three drawings in
   check mode, then `sanitary.py` (hygienic lines only) and `pid_consistency.py`. About 2.5 min.
2. Everything open (support findings, components not placed, open questions, check reports) is a **note** in the revision
   description; it never stops the run. Only a model that cannot be built or a drawing that cannot be drawn stops it
   (exit 3, nothing filed): that is a generator or model defect for the agent to fix, then rerun the same command.
   Never take it to Bob as a question.
3. Full build (about 6 min); a pipe supports failure alone is filed with `--failing-ok` and recorded.
4. `model_file.py --rev <X>`, then the P&ID, LSD and PFD (once their generators exist), each filed at its own next letter only when its content changed. Then PRRs raised since the last issued one are marked issued,
   `drive_store.py pointers`, a fast-log row, and `<project>/_work/accept/rev<X>/accepted.md`.

**Never.**
- Run `model_file.py` or a drawing generator by hand for an acceptance.
- File before the script does, or withdraw a filing.
- Start a side session during an acceptance (Bob approved, 2026-10-15: two sessions editing the model at once
  can build against a withdrawn filing); it stays in this session from the word to the report.
- Say "done" while `accepted.md` lists anything under NOT DONE.
- Commit or push: that is close-out.

**Report.** `accepted.md` as written, the filed GLB path (`<project>/06_Issued_Revisions/Models/<MODEL-ID>/<MODEL-ID>-rev<X>.glb`), and
"nothing committed or pushed". On exit 3: fix the defect it names and rerun; tell Bob only if it cannot be fixed.

**Testing the script** (software-developer only): `--sandbox <new folder>` files into a scratch folder and reuses
the current work build. `--preflight-only` prints the list and changes nothing.
