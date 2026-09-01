# Row-label geometry — where the row indicators sit on the paper

**STATUS: DRAFT — the rules are Knut's; the behaviour awaits his confirmation.**

Covers the band of labels printed down the left-hand edge of a chart, one per
row of patches, and how it interacts with the margins, the clip border and the
label text size.

---

## Why this document exists

There was no specification for this. The band was a **fixed 7.5 mm**
(`instruments.ROW_LABEL_BAND_MM`) that did not follow the label size, was
subtracted from the patch area in one layout mode and pushed outside the margin
box in the other, and — with a clip border on the same edge — was printed
underneath that border and disappeared.

Knut set out the rules in his beta-5 report (#159, 2026-08-30). They are quoted
verbatim below. Basti ruled on 2026-09-01 that they are to be built as stated,
in beta 6.

---

## §R1 · Knut's rules, as written

> *"the row indicator labels should have maybe 1 millimetre space to the left of
> the letters… the left margin is no longer respected when 'Show row numbers' is
> set to ON, which is wrong. The whole patch area shall always follow the margins
> as law, especially when 'Prioritise chart area…'."*

1. **R1.1** Row labels are drawn **outside the patch area**, on the left,
   exactly as strip labels are drawn above it.
2. **R1.2** Their position follows **"Text distance to edge"** and the **Clip**
   setting. It is **not a fixed 7.5 mm**, because the label text size varies.
3. **R1.3** Row labels may never come closer to the page edge than the **Clip**
   limit, mirroring the rule that strip labels may not pass **T**.
4. **R1.4** The whole patch area shall **always follow the margins as law**,
   especially under "Prioritise chart area".
5. **R1.5** With clip border ON *and* row indicators ON, the **Clip** value may
   default to *clip-border width + 1 mm* so the labels land to the right of the
   border, and the left margin may be raised automatically to
   *clip width + label width + 1 mm* either side, so the labels do not collide
   with the patch area. **The user may still change the Clip setting
   afterwards.**

---

## §R2 · How the five rules resolve into one calculation

R1.3 and R1.4 pull against each other: the patches must start at the margin,
and the labels must not leave the page. They are reconciled by R1.5 — the
margin moves, not the patches. So there is one derivation, in this order:

```
  band      = width of the widest row label at the chosen text size  +  1 mm gap
  floor     = clip-border width          (when a clip border is on this edge)
              text-distance-to-edge      (otherwise)
  needed    = floor + band + 1 mm
  margin_l  = max(margin_l asked for, needed)        ← R1.5, raised, never lowered
  patches   start at margin_l                        ← R1.4, in BOTH layout modes
  labels    are right-aligned, ending 1 mm left of the patch block ← R1.1
```

Consequences, stated so they are not discovered later:

* **The band is inside the margin, not subtracted from the usable width.** That
  is what makes R1.4 true in both modes. Patch-first stops silently adding
  7.45 mm to the left margin; area-first stops pushing the labels out of the
  margin box.
* **The margin the user asked for can be raised, and never lowered.** It is
  raised only when the labels would otherwise break R1.3. The panel says so.
* **A bigger text size takes more paper, not more risk.** The band grows with
  the label; it no longer stays 7.5 mm while 16 pt labels walk toward the edge.
* **The number of digits counts.** A chart with 120 rows has a wider widest
  label than one with 9, and the band follows the widest label actually drawn.

---

## §R3 · What each rule replaces

| Rule | Before | After |
|---|---|---|
| R1.2 | `rlwi = ROW_LABEL_BAND_MM = 7.5`, a constant. `T` = 2 mm and `T` = 15 mm produced bit-identical positions. | The band is measured from the label at its actual size, and the floor comes from `text_edge_clip_mm` or the clip width. |
| R1.3 | Labels sat 0.51 mm from the paper edge with the Clip limit set to 15 mm. | The labels can never be closer to the edge than the floor; the margin is raised instead. |
| R1.4 | Patch-first: patches started at 13.46 mm when 6 mm was asked for. Area-first: patches started at the margin but the labels were clamped at the page edge. | Patches start at the (possibly raised) margin in both modes; the labels sit inside that margin. |
| R1.5 | Nothing adjusted anything; with a clip border on the same edge, the labels were printed under it and vanished. | The margin is raised so the labels land clear of the border. |

---

## ⏳ Awaiting confirmation

**Confirmed by:** *nobody yet.*

Everything in §R2 describes behaviour built to Knut's rules and verified by
rendered pages, but not yet confirmed by a human as *correct*. It is promoted to
confirmed behaviour only when Knut or Basti says so.

Open points that a reviewer should rule on:

1. **R1.5 says the margin "may" be raised.** It is built as *always raised when
   needed*, because the alternative is a chart that silently drops its labels —
   the fault being fixed. If it should instead warn and leave the margin alone,
   say so.
2. **The floor when there is no clip border.** Built as "text distance to
   edge", which is the only other distance-from-edge setting the panel has. If
   Knut meant the Clip value to apply even with the border off, that is a
   one-line change.
3. **Whether the raised margin should be written back into the recipe** (so it
   is visible in the panel and stored) or stay a render-time adjustment. Built
   as render-time, so the number the user typed is still the number they see.
