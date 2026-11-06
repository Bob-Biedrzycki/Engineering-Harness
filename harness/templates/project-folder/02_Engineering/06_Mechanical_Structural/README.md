# 06_Mechanical_Structural

Frame and structural calculations for this project: working aids for the engineer's Gate 3 check, never a
certification. Only Bob approves.

- **Frame_Calcs/** holds one record folder per saved run of the company-wide skid frame suite
  (`harness/structural-models/`, agent guide `README.md` there):
  `<date>_<model>_<name>/` with the record (use notes, then the report), `inputs.yaml` and `result.json`. They are
  written by `python -m skidframe run <model> <inputs.yaml>` only, and never edited by hand (TR-01). A change is a
  new run, and the old record stays.
- The log of every run is `../11_Scripts_Models/frame-calc-log.csv`.
- How this job applies the suite (its liquids, hot members, which models are critical) is in the job's knowledge
  folder (`job/knowledge/`).
