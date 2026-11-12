"""model_read - read a routed skidlib model the same way whichever generation of skidlib built it.

The checks written since 2026-10-30 (materials.py, solid_clash.py) read names a newer skidlib gives: Model.pieces(),
Piece.sid and Piece.material, Item.comp_id, Spool.start / Spool.end, an Item.step that is always a dict, and
layout.build(config). A model source that predates them gives the same facts under its own names (Spool.pieces,
Piece.spool, Spool.material, a CMP-nnnn in Item.source, Spool.upstream / Spool.downstream, Item.step None,
layout.build()). These functions return the fact from either, so a check reads the model it is given instead of
reporting "not checked" (Bob, 2026-11-11: "Let's follow through and check these on the model"). No geometry here;
nothing is written; no project name or value.
"""
from __future__ import annotations

import inspect
import re

_CMP = re.compile(r"\bCO?MP-(\d{4})\b")


def build(layout, config=None):
    """layout.build(config) where build takes a configuration, layout.build() where it takes none."""
    if inspect.signature(layout.build).parameters:
        return layout.build(config or None)
    return layout.build()


def pieces(m) -> list:
    """Every pipe piece of the model, spool by spool."""
    if hasattr(m, "pieces"):
        return list(m.pieces())
    return [pc for sp in m.spools for pc in sp.pieces]


def piece_spool_id(pc) -> str:
    return getattr(pc, "sid", None) or getattr(pc, "spool", "") or ""


def piece_material(pc, spools_by_id: dict) -> str:
    """A piece's own material, else its spool's."""
    return getattr(pc, "material", "") or getattr(spools_by_id.get(piece_spool_id(pc)), "material", "") or ""


def step_of(it) -> dict:
    """An item's STEP placement record; {} when it has none."""
    return getattr(it, "step", None) or {}


def comp_id(it) -> str:
    """The item's component register id (COMP-nnnn), from Item.comp_id or from a CMP-nnnn / COMP-nnnn in its source;
    "" when it names none."""
    c = getattr(it, "comp_id", "") or ""
    if c:
        return c
    mo = _CMP.search(getattr(it, "source", "") or "")
    return f"COMP-{mo.group(1)}" if mo else ""


def spool_end(sp, which: str) -> str:
    """What a spool's start or end meets ("start" | "end"), "" when the model records nothing there."""
    if hasattr(sp, which):
        return getattr(sp, which) or ""
    return getattr(sp, "upstream" if which == "start" else "downstream", "") or ""
