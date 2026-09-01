# Row-label geometry — where the row indicators sit on the paper

**STATUS: DRAFT — the rules are Knut's; the behaviour awaits his confirmation.**

Covers the band of labels printed down the left-hand edge of a chart, one per
row of patches, and how it interacts with the margins, the clip border and the
label text size.

**Corrected on 2026-09-01**, after Knut tested beta 6 and reported the feature
as *"not implemented"* and a verification pass proved him right. Four statements
in this document were wrong; they are listed in §R5 and fixed in place, because
a specification that misquotes the person whose rules it records is worse than
no specification at all.

---

## Why this document exists

There was no specification for this. The band was a **fixed 7.5 mm**
(`instruments.ROW_LABEL_BAND_MM`) that did not follow the label size, was
subtracted from the patch area in one layout mode and pushed outside the margin
box in the other, and — with a clip border on the same edge, printed underneath
that border and disappeared.

Knut set out the rules in his beta-5 report (#159, 2026-08-30). They are quoted
verbatim below. Basti ruled on 2026-09-01 that they are to be built as stated.

Beta 6 built the **limit** half of those rules and not the **position** half.
Knut, on beta 6:

> *"Row numbers are still glued to the left edge of the patch area, and are not
> placed according to the 'Clip' parameter under 'Text distance from edge', so
> not implemented."*

Measured on beta 6, in the real app, on his own four presets: sweeping Clip from
0 to 25 mm with the left margin pinned above its automatic minimum moved the
labels **0.00 mm**. The position half was built in beta 7 and is described in
§R2.

---

## §R1 · Knut's rules, as written

**On the position** (he wrote this three times, in three reports):

> *"I think it is important that the row label's position are **movable and
> definable using currently defined parameters, just like the strip labels**,
> and not fixed."*

> *"the row indicator labels should have maybe 1 millimetre space to the left of
> the letters… the left margin is no longer respected when 'Show row numbers' is
> set to ON, which is wrong. The whole patch area shall always follow the margins
> as law, especially when 'Prioritise chart area…'."*

**On the limit:**

> *"As for the strip labels, which are not allowed to go closer to the page edge
> than the T limit… the row labels should not be allowed to go closer to the
> page edge than the 'Clip' limit in 'Text distance to edge'."*

**On the default:**

> *"If clip border is set to ON and 'Show row indicators' is ON, then 'Text
> distance to edge' and 'Clip' setting can be set to clip border width + 1 mm as
> default, so that the labels land to the right of the clip border. The left
> margin must then also be set about 8 mm (or depending on the row label text
> width plus 1 mm before and after) more than the clip border width…  **User can
> then change the 'Clip' setting as desired.**"*

Restated as rules:

1. **R1.1** Row labels are drawn **outside the patch area**, down the left-hand
   side, with about 1 mm of air between the text and the patches.
2. **R1.2** Their **position** is set by the **Clip** value in **"Text distance
   from edge"**, measured **from the page edge** — the mirror of the way **T**
   sets the strip labels' position at the top. It is **not a fixed 7.5 mm**,
   because the label text size varies, and it is **not** the patch block's
   left edge, because that is not a setting anybody can move.
3. **R1.3** Row labels may never come closer to the page edge than the **Clip**
   limit, mirroring the rule that strip labels may not pass **T**. Where a clip
   border is drawn on the same edge they must clear the border as well, or the
   border is simply printed on top of them.
4. **R1.4** The whole patch area shall **always follow the margins as law**,
   especially under "Prioritise chart area".
5. **R1.5** With clip border ON *and* row indicators ON, the labels land to the
   right of the border, and the left margin may be raised automatically to
   *floor + label width + 1 mm* either side, so the labels do not collide with
   the patch area. **The user may still change the Clip setting afterwards, and
   that change must be visible on the paper.**

---

## §R2 · How the rules resolve into one calculation

R1.3 and R1.4 pull against each other: the patches must start at the margin,
and the labels must not leave the page. They are reconciled by R1.5 — the
margin moves, not the patches. R1.2 then decides where in that margin the band
sits. So there is one derivation, in this order:

```
  band       = width of the widest row label at the chosen text size  +  1 mm gap
  floor      = max( Clip, i.e. "Text distance from edge" → Clip
                  , the clip border's width, when a border is drawn on this edge
                  , the instrument's own left furniture )
  needed     = floor + band + 1 mm
  margin_l   = max(margin_l asked for, needed)        ← R1.5, raised, never lowered
  patches    start at margin_l                        ← R1.4, in BOTH layout modes

  band right = min(floor + band, patch x0 − 1 mm)     ← R1.2, THE POSITION
  label x    = max(floor, band right − label width)   ← R1.3, THE LIMIT
```

The last two lines are the mirror image of what `geometry.py` already does for
the strip labels, and that is the point of them:

| | strip labels (top) | row labels (left) |
|---|---|---|
| anchored at | `text_edge_top_mm` (**T**) from the page edge | `row_label_floor` (**Clip**, raised to clear a border) from the page edge |
| clamped by | the patch block: `margin_t − label height` | the patch block: `patch x0 − 1 mm` |
| in code | `geometry.placement`, `_leader_top` | `raster.render_pages`, `_band_right` |

Consequences, stated so they are not discovered later:

* **The band is inside the margin, not subtracted from the usable width.** That
  is what makes R1.4 true in both modes. Patch-first stops silently adding
  7.45 mm to the left margin; area-first stops pushing the labels out of the
  margin box.
* **The margin the user asked for can be raised, and never lowered.** It is
  raised only when the labels would otherwise break R1.3, **and when it happens
  the inspector under the preview says so**, naming the margin asked for, the
  margin used, where the labels start and how much their text needs. (Before
  beta 7 this happened in silence: a typed 26 mm resolved to 33.03 mm, a typed
  10 mm to 33.64 mm, and nothing on screen mentioned it.)
* **A wider left margin than the labels need is spent between the labels and
  the patches, not on the labels.** They stay where Clip put them. This is the
  behaviour change of beta 7, and it is what makes Clip a control rather than a
  floor nothing ever reaches.
* **Below the width of a clip border, Clip has no visible effect**, because the
  floor holds the labels clear of the border. This is R1.3 doing its job, and
  it is the reason Knut's own default rule sets Clip to *border width + 1 mm*
  on such a chart. Above the border's width, Clip moves the labels one for one.
* **A bigger text size takes more paper, not more risk.** The band grows with
  the label; it no longer stays 7.5 mm while 16 pt labels walk toward the edge.
* **The number of digits counts.** A chart with 120 rows has a wider widest
  label than one with 9, and the band follows the widest label actually drawn.
* **Nothing moves the patches or the clip-border content out of the labels'
  way.** If the three settings are not lined up, the labels can be printed
  underneath the clip border's content, or pushed up against the patch block.
  The help text for "Show row indicators" says so, with worked examples.

---

## §R3 · What each rule replaces

| Rule | Before | After |
|---|---|---|
| R1.2 (band) | `rlwi = ROW_LABEL_BAND_MM = 7.5`, a constant. `T` = 2 mm and `T` = 15 mm produced bit-identical positions. | The band is measured from the label at its actual size, and the floor comes from `text_edge_clip_mm` or the clip width. |
| R1.2 (position) | `_tx = max(floor, x0 − 1 mm − text width)`: the **patch block** placed the label and Clip was only a floor. Clip 0 → 25 mm with the margin pinned moved the labels 0.00 mm on all four of Knut's presets. | `_band_right = min(floor + band, x0 − 1 mm)`: the **page edge** places the label and the patch block clamps it. Clip moves the labels one for one above the floor. |
| R1.3 | Labels sat 0.51 mm from the paper edge with the Clip limit set to 15 mm. | The labels can never be closer to the edge than the floor; the margin is raised instead. |
| R1.4 | Patch-first: patches started at 13.46 mm when 6 mm was asked for. Area-first: patches started at the margin but the labels were clamped at the page edge. | Patches start at the (possibly raised) margin in both modes; the labels sit inside that margin. |
| R1.5 (raise) | Nothing adjusted anything; with a clip border on the same edge, the labels were printed under it and vanished. | The margin is raised so the labels land clear of the border. |
| R1.5 (said out loud) | The raise was silent, and the only message that did fire said *"the patches will cover part of each one"* on charts where the labels printed perfectly. | The raise is reported under the preview with both numbers; the stale warning no longer fires on a chart whose margin was raised. |

---

## §R4 · What an existing chart does after the beta-7 change

A chart re-prints **identically** whenever its left margin sits at or below the
automatic minimum (`floor + band + 1 mm`), because there `floor + band` *is*
`patch x0 − 1 mm` and the two formulas give the same number. Every one of
Knut's four presets is in that state, and three of the four are bit-identical
on a rendered page.

The exceptions, both deliberate:

* The **ColorMunki A4-84p** preset moves **0.13 mm** (one pixel at 200 dpi) to
  the left, because its patch block sits 0.05 mm right of the margin from the
  area-first horizontal slack, and the labels used to follow the block rather
  than the margin.
* A chart whose left margin is **wider** than the labels need re-prints with
  its labels at the Clip distance instead of hard against the patches. That is
  the fix, not a side effect: it is the case Knut reported.

---

## §R5 · The four corrections made on 2026-09-01

1. **§R1.1 claimed the labels are drawn *"exactly as strip labels are drawn
   above it"*.** They were not: the strip labels hang from the page edge and
   the row labels hung off the patch block. The sentence read as though the
   mirror rule had been implemented and hid the fault for a whole beta. R1.1
   now states only what it can state, and R1.2 carries the mirror rule
   explicitly.
2. **§R1.2 said the position "follows Text distance to edge and the Clip
   setting" while §R2 derived a position of `patch block − 1 mm`.** Those are
   two different rules and the document asserted both. §R2 now has one
   derivation in which Clip is the anchor and the patch block is the clamp.
3. **§R2 claimed "The panel says so" about the raised left margin.** No panel
   said anything. Measured: a typed 26 mm resolved to 33.03, 10 → 33.64,
   6 → 14.38, 4 → 8.95, in silence. The message now exists, so the sentence is
   true; it names where it appears and what it contains.
4. **Open point 1 framed the choice as "always raise" versus "warn and leave
   alone".** Knut's §R1.5 is neither: the raise is a *default* and *"User can
   then change the 'Clip' setting as desired."* On beta 6 there was nothing to
   change afterwards, because Clip was inert above the automatic minimum. The
   open point is rewritten below to ask the question that is actually open.

---

## ⏳ Awaiting confirmation

**Confirmed by:** *nobody yet.*

Everything in §R2 describes behaviour built to Knut's rules and verified by
rendered pages, measured in millimetres against an indicators-off control. It
has not been confirmed by a human as *correct*. It is promoted to confirmed
behaviour only when Knut or Basti says so.

Open points that a reviewer should rule on:

1. **The raise is still unconditional.** R1.5 says the margin "may" be raised;
   it is built as *always raised when needed*, because the alternative is a
   chart that silently drops its labels. What has changed is that it is no
   longer silent. If it should instead refuse to raise and leave the labels
   short of room, say so.
2. **The floor when there is no clip border.** Built as the Clip value, which
   is the distance-from-edge setting the panel offers for that side.
3. **Whether the raised margin should be written back into the recipe** (so it
   is visible in the panel's own spin box and stored) or stay a render-time
   adjustment. Built as render-time, so the number the user typed is still the
   number they see, with the resolved number reported under the preview.
4. **Whether Clip should also be *defaulted* to "clip border width + 1 mm"** on
   a chart that has both a border and row indicators, as R1.5 offers. Not
   built: Clip is one setting shared with the clip-border and notes text, so
   changing its default would move that text too, and the floor already
   delivers the outcome Knut asked the default for (the labels land clear of
   the border). If he wants the number in the box to change as well, that is a
   settings migration and his call.
