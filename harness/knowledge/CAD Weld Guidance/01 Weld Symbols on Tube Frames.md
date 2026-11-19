# Weld symbols on tube frames (2D drawings)

Reference notes, paraphrased from public articles. Fetched 2026-11-19. These notes stand in for the pages; they are not
the standards. Where a note says "summary-derived", the page body came through only as a machine summary, so check it
against AWS A2.4 before relying on it.

---

## A. How to correctly use welding symbols for slotted HSS members

- **Publisher:** American Welding Society, *Inspection Trends*, May 2025. Author per summary: Chris Thurow, PE.
- **URL:** https://www.aws.org/magazines-and-media/inspection-trends/it-may-25-feature-02-symbols/
- **Read status:** partly verbatim; the rules below are summary-derived.
- **Summary:** how the A2.4:2020 arrow-side / other-side rule applies when a tube meets a plate, and why a double
  fillet symbol is often misread there.

Points:
- Arrow-side weld information goes **below** the reference line; other-side information goes **above** it (A2.4:2020,
  cited as clause 6.1).
- Reading a symbol starts with identifying the **joint** (AWS A3.0:2025 definition). A symbol applies only to the joint
  its arrow touches.
- A second T-joint on the opposite face of a member is a **separate joint**; an arrow at one does not cover the other.
- A double fillet symbol means fillets on both sides of **that one joint**, nothing more.
- Each leg of a formed channel, or each wall of a tube, is its own joint.
- **Exterior fillets on all four walls of a square tube need four separate single-fillet symbols.**
- Slotted tube over a gusset: a double fillet on the tube means the tube's outside and inside walls, **not** both faces
  of the gusset. Welds on each side of the plate each need their own symbol.
- Symbols are not the only option: tail notes or drawing notes may carry the requirement.

## B. Commonly misapplied welding symbols

- **Publisher:** STRUCTURE magazine (NCSEA), 2023-02-01. Author: Jason McCool, P.E.
- **URL:** https://www.structuremag.org/article/commonly-misapplied-welding-symbols/
- **Read status:** full article read.
- **Summary:** four common misreadings of weld symbols on structural drawings and the A2.4 rule for each.

1. **"A fillet doesn't need a size."** Wrong: a fillet has **no default size** (unlike an unsized V-groove, which reads
   as CJP). For lap joints 1/4 in. and thicker the maximum leg is 1/16 in. under the plate thickness; that is a maximum,
   not a default. Full-thickness fillets are discouraged (edge melts, undersize looks full). A typical size may sit in
   a detail note or general notes, but the farther the note is from the symbol, the easier it is to miss; check that
   the typical size is achievable at every blank symbol.
2. **Flare-bevel / flare-V welds.** These are always PJP. Show the **effective throat in parentheses**. A groove size
   without parentheses is groove depth (for a flare bevel, the radius). Specify throat rather than leg for skewed
   T-joints outside 80 to 100 degrees.
3. **"Weld all around is a fine shortcut at complex joints."** A2.4 restricts welds that run across the common plane
   (3-D corners): thin throat at the transitions and hidden poor fit-up. Continuous seal welds are recognised for
   liquid/air-tight, galvanising and **sanitary washdown**, but then the engineer should call for inspection (MT/PT)
   at those joints. Misuse examples: full-depth stiffeners; **square/rectangular HSS connections with flush members,
   where the flush sides become flare-bevel grooves, not fillets.**
4. **"Arrow side = near side."** Wrong: arrow/other side is relative to the **joint**, not the viewer. A hidden member
   behind a gusset is better referenced in the tail than with an other-side symbol.
- Closing: the code (D1.1) requires symbols to follow A2.4, so the standard is binding where the code is.

## C. Know your HSS welds

- **Publisher:** STRUCTURE magazine (NCSEA); date not shown (cites 2022 ASTM A500 updates). Authors: Mike Manor, P.E.,
  and Cathleen Jacinto, P.E., S.E. (Steel Tube Institute consultants).
- **URL:** https://www.structuremag.org/article/know-your-hss-welds/
- **Read status:** article text read; figures (flipbook) not read.
- **Summary:** choosing fillet, PJP or CJP for HSS joints, with what the symbol must state.

Points that affect the drawing:
- Weld strength rests on the **effective throat** (root to face).
- Fillets are the usual weld for plates to tube walls and for T/Y/K tube joints; non-90-degree joints need throat
  adjustment.
- Flare-bevel = flat face to tube corner; flare-V = corner to corner. Tube corner radius sets the flare throat
  (2.25t for stepped flat width, average 2t for matched flare bevels, per AISC).
- **Give the effective throat (S) in parentheses for flare-bevel PJP welds.** With no size, the shop fills flush,
  which costs many passes. Underfill is allowed only when the throat is stated.
- **A blank symbol on an HSS connection is read as CJP**: avoid it.
- Fillet leg may exceed tube wall thickness at matched or stepped joints.
- Size only what the load needs: one pass covers fillets to about 5/16 in.; fillets to about 3/4 in. are usually
  cheaper than grooves.
- **Stepped** joints (branch narrower than the chord) take plain fillets and are cheaper; **matched** joints (same
  width, flush) need fillets plus flare-bevel grooves. Matched root opening 0 nominal, 1/16 in. detailed tolerance,
  1/8 in. at fit-up.
- Tube-end welds are outside-only (single-sided): eccentricity and local bending in tension.
- CJP needs backing, which cannot be removed inside a closed tube: use rarely. Fillet-reinforced PJP is the suggested
  alternative.

---

## Takeaways for the skid frame (synthesis, not from any one source)

- State every fillet size; do not rely on a blank symbol. Put the default size in a general note **and** keep a TYP
  symbol at a representative joint so the size is near the work.
- One symbol per joint and per tube wall. Four walls welded = four single fillets (or a correctly placed all-around
  only where the weld truly runs around one joint without crossing a 3-D corner).
- Where a member is the same width as the one it lands on (flush, matched), the two flush faces are **flare-bevel
  grooves** with the effective throat in parentheses, not fillets.
- Mitred rail butt joints are grooves; give the throat (or say CJP explicitly) rather than leaving the symbol blank.
- If any frame weld is a continuous seal for sanitary washdown, say so on the symbol or note and name the inspection.
