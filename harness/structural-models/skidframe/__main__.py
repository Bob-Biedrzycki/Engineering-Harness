"""Command line: python -m skidframe list | check <model> <inputs> [--md out.md] [--json out.json] | run <model> <inputs>

  list   the models, their tier and when to run them
  check  a preview: prints the report (and writes --md / --json if asked); never a result to quote
  run    the result: saved into the active project as a calculation record with its use notes
         (<project>/02_Engineering/06_Mechanical_Structural/Frame_Calcs/, log in 11_Scripts_Models/frame-calc-log.csv;
         skidframe/save.py). The inputs file must carry name, purpose, inputs_source and run_by.

Exit codes: 0 all checks pass, 1 a check fails, 2 bad input (or missing use notes on run).
Run from harness/structural-models with the repo venv:
  ..\\tools\\venv\\Scripts\\python.exe -m skidframe list
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .catalog import MODELS
from .core import InputError
from .save import save_run, split_notes


def _load(path: str) -> dict:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if p.suffix.lower() in (".yaml", ".yml"):
        import yaml
        return yaml.safe_load(text)
    return json.loads(text)


def _default(o):
    try:
        import numpy as np
        if isinstance(o, np.generic):
            return o.item()
        if isinstance(o, np.ndarray):
            return o.tolist()
    except ImportError:
        pass
    return str(o)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="skidframe", description="Skid frame load-bearing models (company-wide)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="list the models, their tier and when to run them")
    for name, hlp in (("check", "preview one model on an inputs file (nothing saved)"),
                      ("run", "run one model and save the result into the active project with its use notes")):
        r = sub.add_parser(name, help=hlp)
        r.add_argument("model", choices=sorted(MODELS))
        r.add_argument("inputs")
        r.add_argument("--quiet", action="store_true")
        if name == "check":
            r.add_argument("--md", help="write the Markdown report here")
            r.add_argument("--json", help="write the JSON result here")
        else:
            r.add_argument("--project", help="project folder to save into (default: the active project)")
    a = ap.parse_args(argv)
    if a.cmd == "list":
        for tier in ("critical", "support"):
            print(f"\n{tier.upper()} MODELS")
            for name, (_, t, q, w) in MODELS.items():
                if t == tier:
                    print(f"  {name:20s} {q}\n  {'':20s} when: {w}")
        return 0
    try:
        notes, inputs = split_notes(_load(a.inputs))
        if a.cmd == "run":
            from .save import check_notes
            check_notes(notes)
        calc = MODELS[a.model][0](inputs)
    except (InputError, ValueError) as exc:
        print(f"INPUT ERROR: {exc}", file=sys.stderr)
        return 2
    d = json.loads(json.dumps(calc.to_dict(), default=_default))
    md = calc.to_markdown()
    if a.cmd == "check":
        if a.json:
            Path(a.json).write_text(json.dumps(d, indent=2), encoding="utf-8")
        if a.md:
            Path(a.md).write_text(md, encoding="utf-8")
    else:
        try:
            rec = save_run(notes, d, md, Path(a.inputs), Path(a.project) if a.project else None)
        except ValueError as exc:
            print(f"INPUT ERROR: {exc}", file=sys.stderr)
            return 2
        print(f"saved: {rec}")
    if not a.quiet:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        print(md)
    return 1 if calc.failed else 0


if __name__ == "__main__":
    sys.exit(main())
