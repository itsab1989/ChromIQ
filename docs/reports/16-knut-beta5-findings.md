# Knut's beta 5 test — findings, numbered

STATUS: in-progress — for challenge and reproduction, no code written

**Knut's opening point, which is the one that matters most:**

> *"it is important that central features are recorded in the design
> specification… Claude tends to do whatever it wants instead of always looking
> at the design spec so that designed and reviewed and approved function is not
> destroyed."*

He is right, and this session proves it: §I.9 was written into
`unified_measurement_management.md` and then implemented as its opposite hours
later (a run holding a measurement WAS displaced, `duplicate_run(groups=…)` was
never called). Every finding below must be checked against the specification
FIRST, and any fix that contradicts a confirmed section is reported, not made.

---

## K1 · Changing instrument silently changes the layout mode
Load a ColorMunki preset (84 patches), change Instrument to **CR30**: "Create
layout" flips from *"Prioritise chart area…"* to *"Prioritise patch size…"* on
its own. Generate then produces much smaller patches.

## K2 · CR30 strip labels hug the top of each strip, not the top of the page
With CR30 the strip label sits directly above its column instead of at the top
of the page, below the "Text distance from edge" **T = 8.0**. Correct for
ColorMunki and i1Pro.

## K3 · Per-target settings are NOT saved when changing run or run type
`demo-projects/ChromIQ-Switching-Demo/Demo-Switching`: run 1 (ColorMunki) →
change instrument to CR30 → switch to run 2 (shows ColorMunki, correct) →
back to run 1 → **CR30 is gone**. Knut states the rule as previously
implemented and verified: every tab's parameters are saved when changing tabs,
when pressing that tab's main button, and when changing profile run or run
type; and the settings of the run being switched TO are loaded. **This includes
the new row-indicator checkbox.**

## K4 · Tab switching keeps the setting; run switching resets it
Turn off both "Show row numbers" and "Show strip indicators", switch to Measure
and back → kept. Then switch to run 2 and back to run 1 → **reset**.

## K5 · Two checkboxes overlap in the layout panel  *(mine, confirmed)*
"Offset every second strip" is drawn on top of the Clip border row.
`ui/dialogs/layout_options_panel.py`: `clip_enable` is at grid cell **(6, 1)**
and `cm_stagger_cb` is at **(6, 1)** — the same cell. The collision pre-dates
the row-indicator work (it was at row 5) but that work moved it and left it.

## K6 · "Show row numbers" is greyed when strip indicators are off
Undocumented in the help text. **Question for Basti/Knut:** is that intended,
or should row indicators be usable on their own? (It is currently forced
because `raster.py` draws the row block INSIDE `if draw_indicators:`.)

## K7 · Label text size is global, not per chart/preset
Loading "Scanner-A4-3430p-1page-Landscape-w4.0mm" showed strip and row labels
far too large. Preferences → Chart Layout → "Strip indicator style" size was
12 pt from some earlier, unrelated instrument/paper. Knut's rule: Preferences
is a **default only**; every saved chart and preset must carry its own label
settings so a chart renders as it was made.

## K8 · The checkbox is misnamed, and the labels ignore "Patch pattern"
Rename to **"Show row indicators"** — the labels are not always numbers.
And the row labels do not follow the **Patch pattern** field, on screen, in the
TIFF, or in the `.ti2`/`.ti3`. (Confirmed in code: `raster.py` hard-codes
`DEFAULT_PATCH_PATTERN` for the row labels; the user's pattern reaches only the
`.ti2`.) Both help texts must explain how Strip pattern and Patch pattern
decide what the labels look like.

## K9 · The clip border covers the row indicators
Preset "i1Pro-A4-162p-1page-Portrait-w7.5mm" (clip border ON): switching row
indicators on puts the clip border and its Notes box **on top of** them. Does
not happen with "i1Pro-A4-484p…", which uses *"Prioritise patch size"*.

## K10 · The 7.5 mm reservation is the wrong method — Knut specifies the right one
> *"the row indicator labels should have maybe 1 millimetre space to the left
> of the letters… the left margin is no longer respected when 'Show row
> numbers' is set to ON, which is wrong. The whole patch area shall always
> follow the margins as law, especially when 'Prioritise chart area…'."*

His design, to be implemented as stated:
* Row labels are drawn **outside** the patch area, on the left, exactly as
  strip labels are drawn above it.
* Their position follows **"Text distance to edge"** and the **Clip** setting —
  it is not a fixed 7.5 mm, because the label text size varies.
* Row labels may never come closer to the page edge than the **Clip** limit,
  mirroring the rule that strip labels may not pass **T**.
* With clip border ON *and* row indicators ON, the **Clip** value may default to
  clip-border width + 1 mm so the labels land to the right of the border, and
  the left margin may be raised automatically to clip width + label width + 1 mm
  either side, so the labels do not collide with the patch area.
* The user may still change the Clip setting afterwards.

## K11 · Help text must show the arithmetic
Both "Show strip indicators" and "Show row indicators" help must explain, with
worked examples, which parameters place the labels — margins, "Text distance to
edge" (T and Clip), and the clip border — and state plainly that labels can be
covered by the clip border content or the patch area if those values are not
aligned.

---

## Also in scope for the challenge
Everything changed in this session: the row-indicator tri-state, the name
dialog, the data-safety work, the loader wording, the measurement import, the
project and run pickers, and the shared `spread_message_box_buttons` fix.

Knut's log is at `~/Desktop/chromiq.log` (455 KB, 2026-08-31 18:22).

---

# Reproduction and challenge

STATUS: in-progress — plan written first, findings appended as each is measured.
2026-08-31 / 09-01. **No source file is changed by this report.**

Proof: `~/Desktop/knut-beta5/` (`INDEX.md`).
Settings sandboxed to `/tmp/knut16/settings.ini` via `CHROMIQ_SETTINGS_FILE`
**and** by replacing `core.settings.QSettings`, belt and braces, before any
`AppSettings` is constructed. Scratch trees under `/tmp/knut16/` only.
`~/ChromIQ` inventoried by SHA-256 before and after (1 058 files) and never
written to; `~/ChromIQ/CR30-Test` never opened; `~/Desktop/i1Profiler` never
touched. Probe and driver scripts live in `/tmp/knut16/`, never in `scripts/`.

## THE TEST PLAN (written before execution)

Knut's opening point decides the shape of this plan: **the specification is
read first for every finding, and the answer to "is this a bug?" is a quoted
rule or the plain statement that no rule covers it.** Three outcomes are
possible for each of K1–K11 and they are not the same thing:

* **BUG** — the code contradicts a *confirmed* section. Fix it.
* **DESIGN CONFLICT** — the code obeys a confirmed section and Knut's report
  asks for the opposite. **Report; do not fix.** (CLAUDE.md: *"'The code
  disagrees with the spec, so I corrected the code' is only right when the spec
  is right."*)
* **UNGOVERNED** — no specification covers it. Then it is Basti's or Knut's
  call, and the report frames it rather than deciding it.

### Phase 0 — read, before any drive
0.1 `per_target_settings.md` and `per_target_settings_test_plan.md` in full;
    then `unified_measurement_management.md` §I, and reports 13/14/15.
0.2 For each of K1–K11, name the governing section *before* reproducing it.
0.3 Static reads: `layout_options_panel.py` grid cells, `instruments.py` CR30
    branch, `raster.py` label drawing, `settings.py` `INDICATOR_STYLE_KEYS`.
0.4 A machine grid-collision scan of the whole layout panel (K5 asks for
    "every OTHER cell collision", and eyes miss those).

### Phase 1 — K3/K4, the most serious, and the one with a tag to compare against
1.1 Drive Knut's exact steps on a scratch copy of `Demo-Switching`:
    run 1 → instrument CR30 → run 2 → run 1.
1.2 Same for the two checkboxes of K4, with a tab switch in between to
    reproduce his "kept on a tab switch, lost on a run switch" asymmetry.
1.3 **Separate the two candidate mechanisms.** The store (`meta.json`) and the
    screen are different observations: read the JSON at every step, not only
    the widget. A value that IS stored and then overwritten on screen is a
    different fault from one that was never stored, and only one of them is a
    §2/§3 violation.
1.4 The full `per_target_settings_test_plan.md` sweep: every parameter the
    registry yields, on all four storing tabs, across four targets, in two
    visiting orders — I1/I2/I3/I4 of `scripts/drive_per_target_settings.py`,
    run from a copy in `/tmp/knut16/`.
1.5 **Regression or not:** `git worktree` at `v4.1.5-beta.4`, then at
    `v4.1.5-beta.5`, and run the identical driver against identical copies of
    the same project. Three verdicts, not one.

### Phase 2 — K1/K2, the CR30
2.1 K1: load a ColorMunki preset, change instrument to CR30 on screen, read
    `layout_mode` before and after. Find the line. Ask whether a *preset* load
    is distinguishable from a *user* switch in that line's guard.
2.2 K1 beyond his report: what ELSE does that switch change? (spacers, area
    method, paper, clip content) — he saw one of them.
2.3 K2: build a real CR30 chart and an i1Pro/CM chart at the same T, and
    MEASURE the label's top edge in the TIFF in mm. Geometry (`lspa`,
    `txhisl`) or raster (`place.leader_top`)? Answer with numbers.

### Phase 3 — K9/K10, the row-label geometry (his clause list is a spec)
Each clause of K10 becomes a check, measured in the rendered TIFF in mm:
3.1 labels drawn OUTSIDE the patch area;
3.2 position follows "Text distance to edge" / Clip, not a fixed 7.5 mm;
3.3 the left margin is respected — patch area inside the margins in BOTH
    layout modes, row indicators on and off;
3.4 labels never closer to the edge than the Clip limit;
3.5 clip border ON + row indicators ON — what happens today (K9);
3.6 label size varied (auto, 8 pt, 12 pt) — does the reservation follow?

### Phase 4 — K5, K6, K7, K8, K11
4.1 K5: confirm the collision on screen for a ColorMunki (both visible) and
    prove the scan found every other one.
4.2 K6: can the row block be drawn with strip indicators off? What exactly
    would have to change — and is any of it specified? Frame, do not decide.
4.3 K7: prove where the size is resolved; prove a preset carries it; render
    the same preset with Preferences at 12 pt and at auto and show both.
4.4 K8: build a chart with a non-default Patch pattern and read the row labels
    off the TIFF, the `.ti2` and the `.ti3`.
4.5 K11: read both help texts as they stand and judge them against his ask.

### Phase 5 — re-challenge this session's work (report 15's open items)
5.1 The import routing for `.mxf`/`.txt`; the run picker's
    `currentIndexChanged`; `proj.all_runs()`; "a new run" =
    `duplicate_run(source, ("chart",))`; the ancestor-walking gate; the project
    picker; the name dialog; `spread_message_box_buttons` ordering.
5.2 **Mutation-test every new test.** For each: apply a mutation to a COPY of
    the repo, prove the mutation LANDS (memory: *"a mutation test only counts
    if the mutation is proven to land"*), then run the test. Green after a
    landed mutation = vacuous.

### Phase 6 — safety close-out
6.1 `defaults read com.chromiq.ChromIQ` by VALUE, before and after.
6.2 `~/ChromIQ` SHA-256 inventory, before and after.
6.3 `~/Desktop/i1Profiler` untouched.

---


---

PLACEHOLDER## THE FINDINGS

Every drive below ran the **real** application on screen with the real theme
(`apply_appearance`), against a scratch copy of Knut's own `Demo-Switching`
under `/tmp/knut16/`. No mock harness was used for any behavioural claim.
Geometry numbers are measured in the rendered TIFF, in millimetres, from the
chart's own sidecar plus a pixel scan — not computed from the recipe.

---

### K3 · Per-target settings ARE saved. The LOAD throws them away. — **REPRODUCED. BUG. NOT a regression from this session.**

Knut's exact steps, driven on `Demo-Switching`
(`/tmp/knut16/drive_k34b.py`, output verbatim):

| step | on SCREEN | on DISK (`runs/run1/meta.json`) |
|---|---|---|
| A · run 1 selected | instrument `CM` | `printtarg-i = CM`, `engine_recipe.instrument = CM` |
| B · user picks CR30 | **`CR30`** | `CM` — correct, nothing written yet |
| C · switch to run 2 | `CM` (run 2's own) | **`CR30` — THE WRITE WORKED** |
| D · back to run 1 | **`CM`** ← Knut's report | **`CR30` — still there** |

**The store is not the problem.** Both §3 W6 writes fire, atomically, against
the right target: run 1's `meta.json` holds `CR30` at step C and still holds it
at step D. What fails is §2 L3's load — or rather, what runs *after* it.

**Cause, with two independent proofs.**

* **Control.** The same steps on **run 5, which has no chart**: the value is
  kept (`D5 = CR30`, screen and disk agree). Only a run whose chart exists
  loses it.
* **Ablation.** With `TabChart._restore_chart_settings` stubbed out for the
  duration of the drive, the same steps on run 1 keep `CR30` on screen
  (`D' = CR30`). One line, one cause.

`ui/tabs/tab_chart.py:15851` `_on_target_changed` does, in this order:
`save_target_settings(outgoing)` → `_apply_calibration_knobs` →
`load_target_settings()` → … → `_display_run_chart(ti2, …)`
(`:15907`) → `_restore_chart_settings(ti2)` (`ui/tabs/tab_chart.py:6069`) →
`_set_engine_recipe(recipe)` (`:10461`). The chart's `.channels.json` carries
`layout.recipe`, and that recipe carries **`instrument`, `paper`,
`layout_mode`, `show_strip_indicators`, `show_row_indicators`** — so the
sidecar re-imposes the chart's own values over the ones just loaded from the
target's store.

**AND IT THEN DESTROYS THE STORED VALUE.** `/tmp/knut16/drive_corrupt.py`, on
screen, verbatim:

```
1. on run1, disk: printtarg-i='CM'
2. picked CR30 on screen, disk: printtarg-i='CM'
3. moved to run2  -> run1 disk: printtarg-i='CR30'   <-- filed correctly
4. back on run1, SCREEN instrument = CM   disk: 'CR30'
5. left Create Chart (W6 fires) -> run1 disk: printtarg-i='CM'   <-- GONE
```

Merely visiting the run and leaving the tab deletes the user's stored setting.
That is exactly the failure §2.1 was written to prevent:

> *"If it does not, the on-screen values still belong to the old target when
> the user later leaves the tab — and §3's write-on-leave would then record the
> old target's edits **onto the new target**."*

Same shape, one step further along: the *chart's* values are recorded onto the
*target*.

**Which rule this breaks.** §2 L3/L4 say a Profile-run / Run-type change loads
**"that tab's settings for the currently selected target"**. §10's sidecar
ruling is narrower than the code treats it:

> *"The charts sidecar is the correct value to use. **When a chart is
> restored**, the chart sidecar will overrule the settings for the chart for
> that specific run type."*

"When a chart is restored" is §2 **L5** (a chart opened / Restore Used Chart).
The code applies it to **L3/L4** as well, because `_on_target_changed` calls
`_display_run_chart` unconditionally. §10 does bless one narrow case of this —
*"the chart sidecar rewrites the patch count on selection (L5) over the stored
value — correct per the sidecar-precedence ruling above"* — but that sentence
is about the **patch count**, and the code extends it to the whole recipe.

**This is where the specification and Knut's report genuinely disagree, so it
is REPORTED, not fixed.** See OPEN QUESTION 1. What is *not* in dispute is the
corruption in step 5: whatever the sidecar is allowed to show, the next write
must not file it into the target's own store.

**Regression?** **No.** Byte-for-byte the same behaviour at **v4.1.5-beta.4**
(`/tmp/knut16/beta4`) and at **v4.1.4 GA** (`/tmp/knut16/v414`) — same driver,
same project copy, same result: chartful run loses it, chartless run keeps it,
ablating `_restore_chart_settings` cures it. The load/save events landed in
`6996d3bc` (2026-08-06, v3.14.8-beta.169–171) and `_display_run_chart` was
already inside `_on_target_changed` before that (`cf515b1d`), so this has been
true since the feature shipped, i.e. since 4.0.0. The row-indicator work of
beta 5 did not cause it; it only added a new victim.

---

### K4 · Same cause. Tab switch survives; run switch does not. — **REPRODUCED. Same BUG as K3.**

Driven with **real clicks** (`QCheckBox.click()`, so `_row_indicators_touched`
arms exactly as for a person):

| step | SCREEN | DISK |
|---|---|---|
| E · untick both | strip `False`, row `False` | strip `True` (not written yet) |
| F · Measure → Create Chart | strip `False`, row `False` — **kept** | strip **`False`**, row **`False`** — filed |
| G · run 2 → run 1 | strip **`True`**, row **`None`** — **reset** | strip `False`, row `False` — still correct |

Knut's asymmetry is exact and its cause is the same single line: a tab switch
does not reload the chart, a run switch does. The recipes in this demo project
predate the row checkbox, so `show_row_indicators` comes back from
`LayoutRecipe.from_dict` as its default `None` — which is why the row box
"resets" rather than merely reverting.

One driver artefact worth recording so nobody repeats it: setting the tri-state
box with `setCheckState()` never arms `_row_indicators_touched`
(`ui/dialogs/layout_options_panel.py:467` connects `clicked`, deliberately and
correctly), so the recipe records `None` and the test looks like a different
bug. Drive it with `.click()`.

---

### K3/K4 ADDENDUM — the driver the test plan mandates is green ON THIS BUG

`scripts/drive_per_target_settings.py` is the on-screen harness
`per_target_settings_test_plan.md` §1 calls for. Run at HEAD it reports
**81 checks, 3 failed** — and none of the three is K3 or K4, because of this,
at `scripts/drive_per_target_settings.py:394`:

```python
VOLATILE.setdefault("Create Chart", set()).update({
    "targen-f", "printtarg-i", "printtarg-p",
    "ui:guided.instrument", "ui:guided.paper", "ui:guided.pages",
    "ui:engine_on", "ui:engine_recipe", "ui:mode",
})
```

`printtarg-i` is K3. `ui:engine_recipe` is K4. The exclusion cites Knut's own
sidecar-precedence ruling as its justification, and the specification's §10
"Sidecar note" blesses it. **So the feature's own acceptance driver was
built to ignore precisely the two values Knut reports as broken.** That is a
green test guarding the bug, and it is the single most important structural
finding in this report — more important than any one of K1–K12, because it is
why nobody caught this in fifty betas.

The three genuine failures it does report are all one key, `ui:stamp` (the
"stamp the command on the sheet" checkbox) on run-A profiling: driven ON, it
comes back OFF and the disk holds `False`. Not in Knut's list; reported here as
a further bug (see FURTHER BUGS, F1).

---

### K1 · Choosing CR30 silently rewrites the layout mode **and the spacers** — **REPRODUCED. DELIBERATE. UNGOVERNED — Basti's call.**

On screen, i1Pro → CR30 with no other action
(`/tmp/knut16/drive_k1_k5_k7.py`):

```
before: mode=area_first  spacer=colored
after : mode=patch_first spacer=none
CHANGED BY THE INSTRUMENT SWITCH: {'mode': ('area_first','patch_first'),
                                   'spacer': ('colored','none')}
```

Cause: `ui/dialogs/layout_options_panel.py:2046-2072`, inside
`_on_instr_changed`, guarded by `not was_loading` so a preset load is exempt
but a **user** switch is not. Both changes are documented and intentional
(#159, and Basti 2026-08-30 for the spacers).

**Knut saw one of the two.** He reports the layout mode; the spacer combo also
flips to *none*, and on a preset built with coloured spacers that is a second
silent change to his chart. Worth telling him.

**No design document covers instrument-driven defaults** — `docs/design/` has
no chart-layout specification at all. So this is neither a spec violation nor a
spec-blessed behaviour: it is an undocumented product decision, and whether a
user switch may rewrite two of the user's own choices without saying so is
Basti's and Knut's to settle. See OPEN QUESTION 2.

---

### K2 · The CR30 label is in the SAME place as everyone else's — the patch block is higher — **REPRODUCED, cause is not the label.**

Measured with identical recipes across four instruments (`/tmp/knut16/probe_k2.py`,
A4, margins 6 mm all round, T = 8.0, patch-first, instrument margins off):

| instrument | `txhisl` | `lspa` | strip-label top | patch-block top | gap label→patches |
|---|---|---|---|---|---|
| i1Pro | 7.0 | 23.0 | **6.00 mm** | 24.00 mm | 18.0 mm |
| ColorMunki | 7.0 | 33.0 | **6.00 mm** | 34.00 mm | 28.0 mm |
| SpectroScan | 5.0 | 13.0 | **6.00 mm** | 13.00 mm | 7.0 mm |
| **CR30** | 7.0 | **13.0** | **6.00 mm** | **13.00 mm** | **7.0 mm** |

The label sits at 6.00 mm from the page edge on **every** instrument. What
differs is `lspa` — `workflow/layout_engine/instruments.py:747`,
`lspa = border + txhisl` = 13 mm for the CR30, against 23 for the i1Pro and 33
for the ColorMunki, because the CR30 reserves no run-in/run-out for a swipe
that never happens. So the patch block starts 11–21 mm higher and the label,
unmoved, ends up 7 mm above it — which on paper reads exactly as Knut describes
it: hugging the strip.

**And his stated expectation is not implementable today.** He asks for the
label "below the *Text distance from edge* T = 8.0". `T` reaches the strip
label only under `margins_are_law` (`geometry.py:298-308`), and there it is
`max(0, min(T + gap, margin_t − label_band))` — with a 6 mm top margin and a
7 mm label band that clamps to **0.00 mm**, i.e. hard against the paper edge.
Without the law flag it is simply `margin_t`, and `T` is ignored entirely.
Measured in the same table: `leader_top` is 6.00 (no law) or 0.00 (law), never
8.0. **The strip label never follows T.** That is a real fault and it is the
same family as K10; no specification covers it.

---

### K5 · Confirmed, and it is the ONLY cell collision in the panel — **REPRODUCED. BUG.**

A machine scan of every constant-cell `addWidget`/`addLayout` in
`ui/dialogs/layout_options_panel.py` (`/tmp/knut16/gridscan.py`, AST-based)
finds exactly two collisions, both in the `lgg` grid and both the same pair:

```
cell (6, 1):  line 741 self.cm_stagger_cb   /  line 726 self.clip_enable
cell (6, 2):  line 742 self._cm_stagger_tip /  line 727 self._clip_enable_tip
```

Knut named the checkbox; **the tooltip buttons collide too**. Nothing else in
the file does.

On screen, in a real panel with the theme applied (`/tmp/knut16/drive_k57.py`):

| instrument | `clip_enable` | `cm_stagger_cb` | overlap |
|---|---|---|---|
| **CM** | visible, rect (102, **244**, 606, 22) | visible, rect (102, **246**, 606, 18) | **YES** |
| i1 | hidden | hidden | no |
| SS | visible (102, 198, …) | hidden | no |
| CR30 | visible (102, 198, …) | hidden | no |

Only the ColorMunki shows both, which is why it is a ColorMunki-only report.
Screenshot: `k5-layout-panel-CM-overlap.png`.

The fix is one row number, but it must move `cm_stagger_cb` **and** its tooltip
together, and it must not disturb the CM/SS/CR30 visibility logic in
`_sync_instrument_widgets` (`:1985`).

---

### K6 · The greying is deliberate and correct as the raster stands — **REPRODUCED. UNGOVERNED — framed for the owner.**

`ui/dialogs/layout_options_panel.py:3228-3240` (`_on_show_indicators`) disables
the row box when strip indicators are off, and says why:

> *"ROW NUMBERS RIDE ON THE STRIP LABELS. raster.py draws the row-number block
> INSIDE `if draw_indicators:`, so with strip indicators off the numbers are
> not drawn — while the 7.5 mm band is still reserved and paid for in patch
> area."*

Confirmed in the raster: the row block at `workflow/layout_engine/raster.py:1216`
sits inside `if draw_indicators:` at `:1181`, itself inside `if draw_indicators:`
at `:1139`. **Can they be independent?** Yes, and cheaply: the row block is
self-contained — it needs `label_patch`, `font`, `ind_px`, `_row_band_px`,
`place`, `x0` and `col_slots`, none of which depend on the strip label having
been drawn. Lifting it out of the `if` and giving it its own condition is a
small change. Two things ride along and must move with it: `ind_px` /
`label_band_h` are computed for the strip labels (`:1127-1132`) and the row
numbers reuse them, and `_indicator_tile`'s band-height logic must not then
reserve a top band for labels that are off.

**No specification covers this**, and it is a product question, not a code one:
is "row indicators" a sub-option of "strip indicators", or a peer? The help text
does not say either, which is the part of Knut's report that is unambiguously
right. See OPEN QUESTION 3.

---

### K7 · Preferences overrides the preset in BOTH directions — **REPRODUCED. Knut's diagnosis is exactly right. DELIBERATE (#93). UNGOVERNED.**

Measured on a real panel (`/tmp/knut16/drive_k57.py`):

```
panel recipe after set_recipe:                                   2.82  (8 pt)
  Preferences strip_indicator_size_mm=0.0  -> EFFECTIVE = 0.0    (auto)
  Preferences strip_indicator_size_mm=4.23 -> EFFECTIVE = 4.23   (12 pt)
```

The recipe's own 2.82 mm is never used. The mechanism is
`TabChart._current_layout_recipe` (`ui/tabs/tab_chart.py:5334`), which calls
`AppSettings.apply_indicator_style` and overlays the **ten**
`INDICATOR_STYLE_KEYS` (`core/settings.py:419`) — font, size, bold, italic,
rotation, align, label offset and all three underline fields — on top of
whatever the panel holds. `core/settings.py:398` states the intent plainly:

> *"These are the app-wide styling for EVERY engine chart — overlaid at read
> time in `TabChart._current_layout_recipe`, so the styling fields a
> preset/saved-defaults recipe carries are **inert history**."*

**Knut's specific chart.** `_KNUT_SCANNER_RECIPE` (`ui/tabs/tab_chart.py:310`)
carries **no `indicator_size_mm` key at all**, so it means "auto" — and
Preferences' 12 pt therefore decides the label size on a chart whose patches
are 4.0 mm. His account of what happened is correct in every particular.

The codebase already contains the counter-argument to its own design:
`_pin_restored_recipe` (`ui/tabs/tab_chart.py:5346`) exists solely to *undo*
this overlay when a chart is being reproduced, because Knut's run *"had been
drawn with a 4.23 mm indicator; Preferences said auto, so the rebuild drew it
at auto, the label band grew from 64 to 86 px, and every page came out
different."* So the exception has already been granted once, for the case where
being wrong was provable. Knut is now asking for the rule itself.

**Not covered by any design document.** It is a #93 decision recorded only in a
source comment. See OPEN QUESTION 4.

**Secondary finding for Basti:** whichever way that goes, the built-in scanner
presets ask for a 4.0 mm patch grid and specify no label size, so they render
at whatever the machine happens to say. They should carry an explicit one.

---

### K8 · The row labels ignore Patch pattern, and the sidecar does not record it — **REPRODUCED. BUG.**

`workflow/layout_engine/raster.py:1047`:

```python
label_patch = permutation.make_labeller(permutation.DEFAULT_PATCH_PATTERN)
```

The user's `patch_pattern` never reaches it. Built for real
(`Demo-Switching.ti1`, 240 patches, i1Pro, patch-first, row indicators on,
`patch_pattern = "A-Z;1-999"`, `strip_pattern = "1-999"`):

```
DEFAULT_PATCH_PATTERN = '0-9,@-9,@-9;1-999'
default labels 1..12: ['1','2','3','4','5','6','7','8','9','10','11','12']
user's  labels 1..12: ['A','B','C','D','E','F','G','H','I','J','K','L']

.ti2 SAMPLE_LOC, first 14: "9A" "6H" "5F" "11R" "9L" "8K" "5N" "4O" …
```

So the `.ti2` (and therefore the `.ti3`, and the report) call the patches
`9A`, `6H`, `5F`; the printed sheet numbers those same rows `1, 2, 3`. The
coordinate on paper does not match the coordinate in the file — which defeats
the only purpose the band has. **This is worse than cosmetic**, and it is
exactly Knut's point.

**A second half he did not mention:** the chart's own sidecar records
`strip_pattern` and **not** `patch_pattern`
(`k8.strips.json` keys: `dpi, paper_mm, steps_in_pass, strip_pattern,
label_band_bottom_px, strips, patches`). So even once the labeller is fixed, a
restored chart cannot reproduce its own row labels.

**The rename to "Show row indicators" is right** and costs nothing but an i18n
sweep (13 catalogues, per CLAUDE.md). The current label "Show row numbers" is
false on any chart whose patch pattern is not numeric — which is the same fact
the bug above is about.

---

### K9 · The clip border does not "cover" the labels — in area-first they are drawn INSIDE it — **REPRODUCED. BUG.**

Rendered A4 charts, i1Pro, clip border ON (26 mm, left), margins 6 mm, ink runs
measured across the left 45 mm of the page:

```
area-first, rows OFF : ink at 9.23–19.81, 20.24–22.86, patches from 25.99
area-first, rows ON  : ink at 9.23–19.81, 20.24–22.86, patches from 25.99   ← identical
patch-first, rows ON : ink at 9.23–19.81, 20.24–22.86, 27.09–29.29, 29.97–32.17, patches from 33.53
```

In **patch-first** the labels get their own space (27.09–32.17 mm), clear of the
clip band and left of the patches. In **area-first** they have nowhere to go:
`_rlwi = 0.0 if g.fill_beyond_ruler` (`geometry.py:279`) reserves nothing, so
`raster.py:1220` places them at `x0 − 1 mm` and clamps with
`_tx = max(0, _rx − _tw)` — landing them on top of the clip band. A pixel diff
of the two area-first pages confirms it: the only new ink is at **20.15–22.86 mm**,
inside the band. Black text on the band is invisible; that is what Knut saw.

Screenshots: `k9-areafirst-clip-rows-on.png`, `k9-areafirst-clip-rows-off.png`,
`k9-patchfirst-clip-rows-on.png`.

His observation that it *"does not happen with i1Pro-A4-484p, which uses
Prioritise patch size"* is exactly the mode difference above.

---

### K10 · Every clause of his design, measured — **REPRODUCED, and the code breaks four of five.**

Rendered charts, i1Pro, A4, 240 patches, measured in the TIFF:

| case | patch-area left | row-label ink | left margin asked |
|---|---|---|---|
| patch-first, rows OFF | **6.01 mm** | — | 6.0 |
| patch-first, rows ON | **13.46 mm** | 7.03 → 12.11 | 6.0 |
| area-first, rows OFF | **6.01 mm** | — | 6.0 |
| area-first, rows ON | **6.01 mm** | **0.51 → 5.93** | 6.0 |
| area-first, rows ON, margin 1 mm | 1.02 mm | **0.51 → 0.93** (clipped) | 1.0 |
| area-first, rows ON, T = 2 mm | 6.01 | 0.51 → 5.93 | 6.0 |
| area-first, rows ON, T = 15 mm | 6.01 | **0.51 → 5.93** — *identical* | 6.0 |
| patch-first, rows ON, 8 pt | 13.46 | 9.31 → 12.28 | 6.0 |
| patch-first, rows ON, 16 pt | 13.46 | **6.10** → 12.02 | 6.0 |

Clause by clause:

1. *"Row labels are drawn outside the patch area, on the left"* — **HELD.** In
   both modes the ink is left of the patch block.
2. *"Their position follows Text distance to edge and the Clip setting — not a
   fixed 7.5 mm"* — **BROKEN.** T = 2 mm and T = 15 mm produce **bit-identical**
   label positions. `rlwi = ROW_LABEL_BAND_MM = 7.5`
   (`instruments.py:747`) is a constant, and `raster.py:1219` uses a hard-coded
   `_gap = px(1.0)`. Neither `text_edge_mm` nor `text_edge_clip_mm` is read
   anywhere on the row-label path.
3. *"Labels may never come closer to the page edge than the Clip limit"* —
   **BROKEN.** With the Clip distance set to 15 mm the labels still sit at
   0.51 mm from the paper edge.
4. *"The whole patch area shall always follow the margins as law"* — **BROKEN,
   differently in each mode.** In patch-first the patch area starts at
   **13.46 mm** when the user asked for a 6 mm margin: `rlwi` is added to the
   origin (`geometry.py:318`), so switching row numbers on silently adds
   7.45 mm to the left margin. In area-first the patch area does start at the
   margin, but the labels are pushed **into** the margin and clamped at the page
   edge, so printed content leaves the margin box instead.
5. *"Sensible automatic defaults when clip border and row indicators are both
   on"* — **NOT IMPLEMENTED.** Nothing adjusts Clip or the left margin when
   both are on; K9 is the consequence.

**And the reservation does not follow the label size.** At 16 pt the labels
already start at 6.10 mm against a 6.0 mm margin — 0.10 mm of headroom — while
the reserved band is still 7.5 mm. A larger size or a three-digit row number
walks straight out of the page. That is the substance of Knut's *"it is not a
fixed 7.5 mm, because the label text size varies"*.

Screenshots: `k10-pf-rowon.png`, `k10-af-rowon.png`, `k10-af-m1-rowon.png`,
`k10-af-rowon-T15.png`, `k10-pf-rowon-16pt.png`.

**No confirmed specification covers row-label geometry**, so K10 is a design
Knut has now written and it can be implemented as stated — but it should be
written into a specification *first*, because this is precisely the kind of
agreed behaviour his opening criticism is about. See OPEN QUESTION 5.

---

### K11 · The help text does not do it, and one sentence in it is wrong — **REPRODUCED.**

As shipped (`ui/dialogs/layout_options_panel.py:443` and `:469`):

* **"Strip indicators"** — describes what the label is and sends the user to
  Preferences for the style. **Nothing** about placement: not margins, not
  "Text distance from edge", not the clip border, not what happens when they do
  not fit.
* **"Row numbers"** — describes the coordinate, says which instruments print it
  by default, and then: *"It costs 7.5 mm of paper down the left edge, so
  switching it on can leave room for fewer or slightly smaller patches."*

That sentence is **true in patch-first and false in area-first**, where nothing
is reserved and the labels intrude into the margin instead (measured above).
Neither text mentions the greying (K6), neither mentions Strip pattern or Patch
pattern (K8), and neither gives arithmetic or a worked example. Knut's ask is
not met, and the one number the text does give is mode-dependent and unqualified.


---

### K12 · The CR30 Bluetooth tile learn — **REPRODUCED, and the owner's own two sessions are the controlled experiment. BUG. Not a regression from this session; shipped in v4.1.5-beta.2.**

**No hardware was used, and none was needed.** Hardware access was granted
mid-task; it is declined here with a reason, because the live log already
contains the A/B pair that settles the question, and pressing the button — the
only thing that could add to it — is the one thing a driver cannot do. Sending
frames to the owner's only unit to re-observe something his own log already
proves would be risk for no information.

**The A/B pair, from `~/Library/Logs/ChromIQ/chromiq.log`:**

```
FAILED — 22:11, he pressed ONCE and confirmed
22:11:06,834  no tile signature learned for unit ble:FFB32AD2-…
22:11:07,641  calibration white answered in 0.81 s
              34 s, not one log line   ← window up, press, "I have pressed it"
22:11:41,954  ArgyllRunner: cleanup complete            ← force-quit

WORKED — 22:30, same machine, same unit, same build
22:29:58,405  no tile signature learned for unit ble:FFB32AD2-…
22:29:59,213  calibration white answered in 0.81 s
22:30:20,443  settings.set cr30_tile_signatures = {…, "ble:FFB32AD2-…": [31 bands]}
22:30:20,444  learned the tile signature of unit ble:FFB32AD2-… — the guard is now armed
22:30:26,972  calibration black answered in 0.81 s     ← the flow CONTINUES
```

**So the BLE learn path CAN complete — it completed in 21 seconds — and the
only difference between the two runs is how many times he pressed the button.**

**Answers to the five questions.**

**1 · What does "I have pressed it" do on BLE, and can that path complete?**
It closes the window and *then* starts collecting. `ui/tabs/tab_measure.py:7771`
`box.exec()` returns; only afterwards does `:7783` run
`reader.learn_tile(timeout=90.0)` on a worker thread. Over Bluetooth
`TileLearner.offer` (`workflow/cr30/tile_learning.py:180-186`) has no gate flag
to work with and accepts a value only when **two presses are bit-identical**, so
the first press returns `None` and `learn_tile`
(`workflow/cr30/measure_bridge.py:963-978`) loops to wait for a second one — for
up to 90 seconds, with **no window, no progress, no cancel, and nothing on
screen at all**. The window that would have told the user to press again is the
one that has just closed.

The message text says so itself, and the code contradicts it verbatim
(`workflow/measurement_messages.py`, M-CR30-LEARN-TILE, and
`docs/design/unified_measurement_management.md:1203`):

> *"Over Bluetooth it does not say, so ChromIQ asks for a SECOND press and
> accepts the value only if the two readings are identical … **Either way, just
> keep pressing until this window closes.**"*

There is no window to keep pressing at. And the headline —
**"One press teaches ChromIQ your instrument's white tile"** — is false on
Bluetooth, where two are required.

The hook for doing it properly already exists and is not used:
`learn_tile(…, on_press=…)` (`measure_bridge.py:942`) is never passed a
callback, and `TileLearner.needs_another_press`
(`tile_learning.py:192`) — written for exactly this — **is called nowhere in
the codebase**.

**2 · Why did the black calibration not follow?** Because it cannot.
`_offer_cr30_tile_learning(reader)` is called synchronously at
`ui/tabs/tab_measure.py:7394`, and `_run_cr30_black_calibration()` is the next
statement at `:7396`. The learn blocks that sequence for up to 90 s per missing
press. At 22:11 he force-quit 34 s in, before it gave up; at 22:30 it succeeded
in 21 s and black followed 6 s later.

**3 · Is the learn keyed to the id the guard reads back?** **Yes — the known
trap is NOT present here.** `MeasureBridge._signature_key`
(`measure_bridge.py:781`) is the single source of the key and is used both when
arming (`:833-834`) and when storing (`:974`); on BLE it returns
`ble:<address>`. Proved by value in the owner's own store:
`cr30_tile_signatures` now holds `"ble:FFB32AD2-D165-6D79-A509-5EA1566707A0"`,
which is the exact string the guard logged as "not learned" beforehand, and the
guard armed on it at 22:30.

**4 · Would it have waited for ever?** **No — but the distinction is academic.**
The wait is bounded: `timeout=90` per press, `MAX_LEARNING_PRESSES = 3`
(`measure_bridge.py:931`), and the first `MeasurementError` ends the loop, so
the worst case is ~90 s and the theoretical worst ~270 s. `cancelled` is not
passed, so there is no way to stop it; and because nothing on screen changes,
force-quitting after 34 seconds was the only rational thing to do.

**5 · The A6 stall (the deferred session) — kept separate.** No software cause
is evidenced. Patches 1–5 read normally over the same BLE link between 22:12:52
and 22:13:34; A6 then waited its full 180 s and was re-armed, and the session
was stopped at 22:19:28. There are **no** "discarded N readings taken before
this patch was armed" lines, no exception, and no reconnect — the transport
simply delivered nothing. Two things are worth saying and neither is a
conclusion:

* **ChromIQ cannot see a dropped BLE link.** `workflow/cr30/ble.py` never passes
  bleak a `disconnected_callback`; the only disconnect in the file is the one we
  ask for (`:278`). So "the link went away" and "nobody pressed the button" are
  indistinguishable in the log, and both look like a 180 s timeout.
* The owner was demonstrably doing other things from 22:13:50 (the sandbox
  warnings in that same log are this report's own drivers starting), so
  "nobody pressed" is at least as likely as any fault.

Establishing which needs one more press-dependent observation — see the SEQUENCE
FOR THE OWNER below.

**Which rule this breaks.** M-CR30-LEARN-TILE is §M-**PROPOSED**, not confirmed,
so this is not a violation of a confirmed section. It is, however, the code
contradicting the agreed wording of its own window, sentence for sentence, which
is the same failure mode as §I.9 — and it shipped in beta 2 and has never been
exercised over Bluetooth by anyone but the owner.

**What the fix must be** (three parts, smallest first):

1. **Log the outcome.** `_offer_cr30_tile_learning` writes to the tab's log pane
   only; `log.*` is called on no branch except `remember_signature`'s success.
   That is why 34 seconds of a failing feature left no trace. Declined, failed,
   timed out and succeeded must each write one line.
2. **Keep a window up while it collects,** and drive it from the `on_press`
   callback that already exists: "press 1 of 2 received — press it again",
   with a Cancel that reaches `learn_tile(cancelled=…)`. Then the shipped
   sentence *"keep pressing until this window closes"* becomes true.
3. **Fix the title on Bluetooth.** "One press…" is wrong there. The body already
   explains both cases; the title must not contradict it. Title text is §M, so
   it goes to §M-PROPOSED for approval, not straight into the tab.

**A SEQUENCE FOR THE OWNER** — the press-dependent half, which no agent can do.
Two minutes, and it settles the A6 question:

> 1. Forget the learned tile first, so the window appears:
>    Preferences is not enough — run
>    `defaults delete com.chromiq.ChromIQ cr30_tile_signatures` with ChromIQ
>    closed. (This removes the USB entry too; both are the same value, and
>    re-learning restores it.)
> 2. Start ChromIQ, open **CR30-Test**, Measure, Start Measurement, cap on.
> 3. At the tile window, press the instrument's button **once**, click
>    **"I have pressed it"**, and then **do nothing at all**. Time it.
>    * Report: does anything appear on screen? After how long does the black
>      calibration window arrive? (It should be ~90 s.)
> 4. Repeat, but this time press the button **again** about five seconds after
>    clicking "I have pressed it". Report how long until it says it has learned.
> 5. For A6: start a measurement and read four or five patches, then **wait two
>    minutes without touching anything**, then press the button again on the
>    same patch. Report whether that press is accepted, ignored, or produces
>    "discarded 1 reading taken before this patch was armed".
>    That last line is the one that separates a lost link from a lost press.


---

## FURTHER BUGS FOUND (not in Knut's list)

**F1 · "Stamp the command on the sheet" is not per target.** The test plan's own
driver, run at HEAD, fails on exactly one key across two rounds and on disk:
`ui:stamp` is driven ON, comes back OFF, and `meta.json` holds `False`. It is
recorded through `_collect_ui_state` (`ui/tabs/tab_chart.py:14001`) but
something resets it after the load — most likely
`_refresh_manual_command_preview`, which the engine toggle calls and which
resets the stamp checkbox to its mode default. It is a §1.2 per-target setting
("bit depth, compression, PDF export, **stamp checkbox**"), so this is a §2/§3
violation of a confirmed section, independent of K3.

**F2 · Area-first stops filling the margin box when row indicators are on.**
Measured on the same page, i1Pro, A4, 10 × 24 grid, margins 6 mm:

| | patch left | patch right edge | patch width |
|---|---|---|---|
| rows OFF | 6.01 mm | **203.88 mm** | 19.81 mm |
| rows ON | 6.01 mm | **196.43 mm** | 19.05 mm |

The block now stops **7.45 mm short of the right margin** while still starting
at the left one. Cause: `workflow/layout_engine/area_fit.py:38` subtracts
`g.rlwi` from the usable width with **no `fill_beyond_ruler` guard** — the guard
that `geometry.py:147` and `geometry.py:279` both have. It is the third site of
the same subtraction and it was missed when the other two were fixed. This is
Knut's *"the whole patch area shall always follow the margins as law, especially
when Prioritise chart area"* with a number on it, and the fix is one line.

**F3 · The strip label never follows "Text distance from edge".** See K2. Under
`margins_are_law` the label top is `max(0, min(T + gap, margin_t − label_band))`,
which for the common case (6 mm top margin, 7 mm label band) clamps to **0.00 mm** —
the label is printed hard against the paper edge, not at T. Without the law flag
`T` is not consulted at all. Measured for all four instruments.

**F4 · The chart sidecar does not record `patch_pattern`.** See K8. A chart
cannot reproduce its own row labels from its sidecar even once the labeller is
fixed.

**F5 · A failed or declined CR30 tile learn writes nothing to the log.** See
K12. Thirty-four seconds of a feature failing left no trace at all, which is why
the first hypothesis about this was wrong.

**F6 · ChromIQ cannot detect a dropped BLE link.** See K12(5).
`workflow/cr30/ble.py` passes bleak no `disconnected_callback`, so a link that
goes away is indistinguishable from an operator who has stopped pressing. Both
appear as a 180 s timeout with no explanation.

**F7 · One instrument, two transports, two learns — the tile must be taught
TWICE.** Basti's question, and his own store answers it: `cr30_tile_signatures`
holds **two keys for one CR30** —

```
"PT694D01E7"                                 (USB: the unit's serial, learned 2026-08-30 10:01)
"ble:FFB32AD2-D165-6D79-A509-5EA1566707A0"   (BLE: the CoreBluetooth UUID, learned 2026-08-31 22:30)
```

— and the two arrays are **byte-identical** (max absolute difference 0.0 across
all 31 bands). He learned it over USB on the 30th, and on the 31st every
Bluetooth session still logged *"no tile signature learned for unit
ble:FFB32AD2-…"* until he taught it a second time. So the K12 window he was
fighting only appeared at all because the USB learn did not count.

Cause: `MeasureBridge._signature_key` (`workflow/cr30/measure_bridge.py:781`)
returns the unit's **serial** over USB and `ble:<address>` over Bluetooth, and
`tile_learning.learned_signature` (`tile_learning.py:104-110`) does an exact
dictionary lookup on that key. Its "unknown unit" fallback — *arm it when
exactly one signature has ever been learned on this machine* — is guarded by
`if unit_id:` and the BLE key is a non-empty string, so the fallback can never
fire on the path that needs it.

**This is the trap the module's own docstring warns about, from the other side.**
Keying exists so a second instrument cannot inherit the first one's constant —
a good rule. But the same physical instrument gets two keys, and the guard has
no way to know they are the same device. Note the safety asymmetry: teaching one
device twice is harmless (the values agree to 0.0), whereas the two units ever
measured sit 4.69 %R apart, so a wrong match is not a realistic risk from
sharing within one machine.

**What the fix must be** — and it is a design question, not a mechanical one, so
it is OPEN QUESTION 8: either (a) let a BLE session fall back to a
single learned signature when the machine has exactly one, which is what the
existing `UNKNOWN_UNIT` branch already intends and would have armed his guard
on the 31st without a second press; or (b) read the unit's serial over BLE too,
if `identify()` can be made to return it, and key both transports on it; or (c)
leave it, and say so in the window, because a per-transport learn is one extra
press once in the instrument's life. (a) is the smallest and matches the
docstring's own reasoning; (b) is the correct one if the serial is reachable.

---

## RE-CHALLENGE OF THIS SESSION'S WORK

**The fixes report 15 demanded are genuinely in.** Verified in the source, not
in the report about it:

| Report-15 item | State at HEAD |
|---|---|
| B1 · `picker.currentIndexChanged` connected | **done** — `ui/tabs/tab_profile.py:4361`, writing `chosen[0]` |
| B2 · `proj.runs()` → `proj.all_runs()` | **done** — `:4390`; `Project` has no `runs()` and the test asserts that |
| §I.9 · "a new run" is a chart-only duplicate | **done** — `duplicate_run(source, ("chart",))` at `:4419` and `:4463` |
| B4 · the ancestor-walking gate | **done** — `ui/ti2_loader._project_root_for`; a run's own `.ti3` is recognised as inside its project, a stray one is not |
| `.mxf`/`.txt` convert before the question | **done** — `_convert_for_import` precedes `_offer_import_into_a_project` in `_on_load_ti3` |
| settings sandbox | **done** — `CHROMIQ_SETTINGS_FILE`, `core/settings.py:781-815`; this whole report depends on it and it held |

### Vacuous tests — MUTATED, and the mutation proven to land

Method: an rsync copy of the tree at `/tmp/knut16/mutrepo`; each mutation
applied, **proved present on disk**, **proved not to break the module's import**
(one mutation was discarded for exactly that reason — a "caught" verdict from a
syntax error is not a caught mutation), then the single test run.

| # | Mutation | Test | Landed | Verdict |
|---|---|---|---|---|
| M1b | add a real nearest-neighbour re-pairing function to `workflow/measurement_import.py`, written with none of the four grepped words | `test_no_repair_is_attempted_anywhere_in_the_module` | yes, imports | **VACUOUS** |
| M2 | connect `picker.currentIndexChanged` to a no-op lambda instead of the writer | `test_the_run_picker_choice_is_connected` | yes | **VACUOUS** |
| M3c | `ui/txt_loader.py` stops calling `dir_holds` entirely (the name survives in the docstring above it) | `test_both_loaders_use_that_one_helper` | yes | **VACUOUS** |
| M8 | `spread_message_box_buttons` throws its `order=` argument away on the first line | `test_cancel_sits_on_the_far_right_and_replace_is_not_first` | yes | **VACUOUS** |
| M3b | the same loader grows its own `.parent.resolve()` comparison back | `test_both_loaders_use_that_one_helper` | yes | caught |
| M4 | `duplicate_run` ignores its `groups` argument | `test_duplicating_for_an_import_copies_the_chart_only` | yes | caught |
| M5 | `Project.runs()` exists again | `test_project_has_all_runs_not_runs` | yes | caught |
| M6 | `CHROMIQ_SETTINGS_FILE` is ignored | `test_the_env_var_moves_the_whole_store` | yes | caught |
| M7 | `_project_root_for` stops walking ancestors | `test_a_runs_own_measurement_counts_as_already_in_a_project` | yes | caught |
| M10 | the conversion is moved after the routing question | `test_every_format_reaches_the_same_question` | yes | caught |

**What the four vacuous ones mean, in order of how much it matters:**

1. **`test_the_run_picker_choice_is_connected` cannot tell a wired picker from a
   decorative one.** It greps `inspect.getsource` for the string
   `"currentIndexChanged"`. B1 — the fault report 15 called *"worse than no
   picker"* — is guarded by a test that a no-op lambda satisfies. It must drive
   the picker and assert the run the file lands in.
2. **`test_cancel_sits_on_the_far_right_and_replace_is_not_first` observes the
   argument, not the result.** It captures the `order=` list the caller passes
   and never asks what `spread_message_box_buttons` did with it, so the function
   can discard it entirely and stay green. Report 15 listed the button-order work
   under "safe to keep as it is"; it is safe, but it is untested.
3. **`test_no_repair_is_attempted_anywhere_in_the_module` greps four library
   names.** Report 15 predicted this; it is now proven. A hand-written
   nearest-neighbour loop passes it. It must assert on the verdicts `assess`
   returns for a shuffled measurement, not on vocabulary.
4. **`test_both_loaders_use_that_one_helper` is satisfied by the word appearing
   in a docstring.** Its second assertion (no `.parent.resolve()`) does work;
   the first does not.

None of the four is *wrong* about the code as it stands today. All four would
stay green through the regression they exist to prevent.

---

## OPEN QUESTIONS

**1 · (Knut, and it decides K3 and K4.) When you select a different profile
run, should the chart's sidecar overwrite the settings you had stored for that
run?** Today it does, for the instrument, the paper, the layout mode and the
whole engine recipe including both indicator checkboxes. Your §10 ruling —
*"the charts sidecar is the correct value to use"* — was given about **restoring
a chart**; the code also applies it to merely **selecting a run**. There is a
real argument on each side: a sidecar describes the sheet that was printed and
measured, and Create Chart is also where you set up the *next* one. Which is it?
A middle answer is available and may be the right one: the sidecar keeps
geometry (so the preview matches the paper) while the target's store keeps the
choices that describe the next chart. **Nothing should be changed here until you
answer, because both behaviours are defensible and one of them is written into
the specification.**

**2 · (Basti/Knut.) May choosing an instrument silently rewrite settings the
user has already made?** Picking CR30 changes the layout mode *and* the spacers.
Both are deliberate and both are undocumented on screen. Options: leave as is;
say so in the log/status line; or ask.

**3 · (Basti/Knut.) Are row indicators a sub-option of strip indicators, or a
peer?** They can be made independent for modest cost (K6). If they stay coupled,
the help text must say so.

**4 · (Basti/Knut, and it decides K7.) Is Preferences → Chart Layout a DEFAULT
or the rule?** Today it is the rule and overrides every preset and every saved
recipe in both directions, by design (#93). Knut asks for the opposite. Note
that ChromIQ already grants the exception for Restore Used Chart
(`_pin_restored_recipe`), so the machinery for "the chart carries its own"
exists. If the rule changes, `INDICATOR_STYLE_KEYS` becomes a seed for new
charts rather than an overlay, and the built-in scanner presets need explicit
label sizes.

**5 · (Knut.) K10 is a specification, and it should be written as one before it
is built.** Row-label geometry has no design document. Given your opening point,
the right order is: K10's five clauses into a specification, reviewed, then
implemented — not implemented from a forum post and written up afterwards.
Two clauses need a decision your text leaves open: *(a)* in patch-first, should
the reserved band come out of the margin (patch area starts at the margin, band
inside it) or be added to it (today's behaviour, which enlarges the margin by
7.45 mm)? *(b)* when the label will not fit within the Clip limit, does the
label shrink, the margin grow, or the chart refuse?

**6 · (Basti.) The A6 stall needs one press-dependent observation** — the
sequence at the end of K12. Until then it is honestly unexplained, and F6 means
the log cannot settle it.

**8 · (Basti.) Should a tile learned over USB arm the guard over Bluetooth?**
See F7 — it does not today, and that is why the K12 window appeared at all after
you had already taught it once. Three options are set out there; (a) is one
`if` and matches what `UNKNOWN_UNIT` was written for.

**7 · (Basti.) Should the acceptance driver's exclusion list be allowed to hide
a reported fault?** `scripts/drive_per_target_settings.py:394` excludes
`printtarg-i` and `ui:engine_recipe` from every cross-target verdict, citing the
specification. Whatever the answer to question 1, that list should name the
ruling it depends on in a way that fails when the ruling changes.

---

## VERDICT

**K3 and K4 are one bug, it is not from this session, and it has been in every
release since 4.0.0.** The store, the write events and the load events are all
correct and can be shown to be correct on disk; a single unconditional call to
`_display_run_chart` on target change undoes the load, and the next write then
files the undone value over the user's own. The behaviour half of it is
arguably specified (§10) and must be ruled on before anything is changed; **the
corruption half is not defensible under any reading of §2.1 and should be fixed
whatever the ruling** — a load that loses a value is an annoyance, a write that
destroys it is data loss.

**The most serious finding is not on Knut's list.** The on-screen driver that
`per_target_settings_test_plan.md` §1 exists to mandate is green on this bug by
construction, because its exclusion list names the two values he reported. Fifty
betas of "74/74 green" were measuring something else.

**K12 is a real hang on the happy path of a feature shipped in beta 2**, and the
owner's own two sessions are a clean A/B: one press → silence and a force-quit;
two presses → learned in 21 seconds. The code contradicts the agreed wording of
its own window sentence for sentence, and the callback written to fix it
(`on_press`, `needs_another_press`) is dead code.

**K5 is a one-line fix** (with its tooltip). **K8's labeller is a one-line fix**
plus a sidecar field. **F2 is a one-line fix.** **K9/K10 are a design that must
be written down before it is built.** **K1, K6 and K7 are decisions, not bugs,
and belong to Basti and Knut.**

**Not safe to tag beta 6** on the strength of this session's work alone — not
because the import fixes are wrong (they are right, and mutation-tested where
they could be), but because four of the tests protecting them are vacuous, and
because K3/K4 need a ruling before anyone touches `_on_target_changed`.

---

## ⚠ URGENT — A BREAKING EDIT LANDED IN THE WORKING TREE WHILE THIS REPORT WAS BEING WRITTEN

**Do not tag anything until this is fixed.** `ui/tabs/tab_measure.py`,
`workflow/cr30/measure_bridge.py` and a new `ui/cr30_pictograms.py` changed
under this run at ~22:40 — a K12 fix in flight, adding a `DeviceReader
.open_transport` property so the window can ask for one press or two. The
intent is right. The edit is broken, in two ways, and one of them is a safety
regression.

```python
    MAX_LEARNING_PRESSES = 3

    @property
    @property                       # <- workflow/cr30/measure_bridge.py:934
    def open_transport(self) -> str:
        ...

    def guard_is_armed(self) -> bool:   # <- its @property was taken above
```

Measured, not read (`python -c` against the current tree):

```
open_transport  -> <class 'property'>
guard_is_armed  -> <class 'function'>          # NOT a property any more
r.guard_is_armed = <bound method DeviceReader.guard_is_armed …>
bool(r.guard_is_armed) -> True                 # always
r.open_transport -> TypeError: 'property' object is not callable
```

**1 · The tile-learning feature is switched off entirely.**
`ui/tabs/tab_measure.py:7755` reads `if reader.guard_is_armed: return`. That is
now a bound method, which is always truthy, so `_offer_cr30_tile_learning`
returns at its first line on every transport and **the window never appears at
all** — including for the very user this fix is for.

**2 · The magnet guard's refusal is disarmed — this is the safety one.**
`DeviceReader.trigger_allowed` (`measure_bridge.py:1038`) is
`return self.guard_is_armed`, and that is now truthy for **every** instrument,
learned or not. So `request_trigger` / `trigger_and_read` will fire the
instrument from the host on a unit whose tile signature is unknown — which is
precisely what M-CR30-TRIGGER-NOT-ARMED exists to prevent, because a
host-triggered reply cannot report the magnet gate and the learned signature is
the only thing that replaces the flag. A gated reading would go into the profile
unnoticed.

**3 · `open_transport` itself never works.** `property(property(f))` raises
`TypeError` on access. In the tab it is wrapped in `try/except Exception`, so
`_kind` falls back to `""` and `_times` becomes 2 — the right answer by
accident, and wrong on USB, where it will now ask for two presses.

**The fix is deleting one line** (the duplicated `@property`) **and restoring
the `@property` above `guard_is_armed`.** Then re-check: `bool(reader
.guard_is_armed)` must be `False` on an unlearned unit, and `reader
.open_transport` must return `"ble"` or `"usb"`.

**And it needs a test that would have caught it.** The three existing users of
`guard_is_armed` are two fakes that set it as a plain attribute
(`tests/test_the_measure_log_names_the_transport.py:57`,
`scripts/drive_55_transport_note.py:66`) and the tab, which only asks whether it
is truthy. A fake that assigns the attribute cannot tell a property from a
method, so nothing in the suite can see this — the exact "a fake that
re-implements the code validates itself" shape. The test that catches it asserts
on the real class: `isinstance(DeviceReader.__dict__["guard_is_armed"],
property)`, or better, that a `DeviceReader` with no learned tile answers
`trigger_allowed() is False`.

**A note on line numbers in this report.** Everything above K12 was measured
against the tree as it stood at 22:12–22:35. `ui/tabs/tab_measure.py`,
`workflow/cr30/measure_bridge.py` and `ui/cr30_pictograms.py` have since moved;
the K12 line references to those two files are approximate by ±40 lines, and the
findings themselves were re-verified against the current content before this
section was written. No other file this report cites has changed.

---

## SAFETY OF THIS RUN

* Settings sandboxed twice over: `CHROMIQ_SETTINGS_FILE` exported **before** any
  import, **and** `core.settings.QSettings` replaced, in every driver.
  Verified by value afterwards: `defaults read com.chromiq.ChromIQ
  custom_output_path` → *"does not exist"*, and
  `strip_indicator_size_mm` is still `0` — the value K7's drive set to 4.23 went
  to `/tmp/knut16/k57.ini`, not to the real store.
* All scratch trees, drivers and probes under `/tmp/knut16/`. Nothing was
  written to `scripts/`. The only file in the repository this run changes is
  this report.
* Mutations applied only to `/tmp/knut16/mutrepo`, an rsync copy, and reverted
  after each test. `git worktree` was used for the beta.4 and v4.1.4
  comparisons; both are read-only checkouts.
* **`~/ChromIQ` — 1 058 files before, 1 061 after, and every difference is the
  owner's OWN CR30 session, not this run.** The changed and added paths are all
  under `CR30-Test/runs/run1/` (`CR30-Test.ti3`, two `meta.json`, an
  `old/2026-08-31_221240/` archive and two `reports/report_2026-08-31_22-19-28`
  / `_22-30-38.json`), and their timestamps match his 22:12, 22:19 and 22:30
  sessions in the log. No driver in this report used `~/ChromIQ` as its working
  folder — every one pointed `custom_output_path` at `/tmp/knut16/w_*` — and
  `CR30-Test` was never opened by any of them.
* `~/Desktop/i1Profiler` was not read or written.
* **The instrument was not touched.** No BLE connection was opened, no frame was
  sent. Hardware access was granted and declined with the reason given in K12.
* Note for whoever reads the log next: this run's drivers appear in
  `~/Library/Logs/ChromIQ/chromiq.log` as
  `Settings SANDBOXED to /tmp/knut16/… ` warnings at 22:13:50, 22:14:01,
  22:15:14, 22:16:44, 22:17:51 and 22:23:24. They are interleaved with the
  owner's own CR30 sessions and are not app activity of his.

Proof and screenshots: `~/Desktop/knut-beta5/` (`INDEX.md`).

STATUS: challenged
