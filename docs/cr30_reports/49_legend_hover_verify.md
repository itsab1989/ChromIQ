# 49 — Legend hover-hide: adversarial verification

**Reviewer:** Claude (critic pass) · **Started:** 2026-08-30
**Under review:** commit `29c1a7c6` "The legend gets out of the way when you point at it"
**Parent:** `b46ab0cc`
**Design note it follows:** `docs/cr30_reports/48_legend_hover_hide.md`

Every claim is tagged **PROVEN** (I ran it) or **INFERENCE**.
Proof screenshots: `~/Desktop/cr30-legend-hover-verify/` (README there says what each shows).

## Status — COMPLETE

- [x] 0. Environment, sandbox, backups
- [x] 1. See it on screen; flicker sweep, four edges, both directions — **no flicker**
- [x] 2. Coordinate mapping — resize, pages, margins, dpr — **0 px error**
- [x] 3. The two fixes — (b) proven real; (a) correct, its stated routes are not
- [x] 4. Regressions — parent-commit pixel diff, every overlay on — **0 px**
- [x] 5. **THREE FAULTS FOUND** (§5), all cursor-free and headless-reproducible
- [x] 6. Test quality — **5 of 9 mutations survive** (§6)
- [x] 7. Edge cases, each with a verdict (§7)
- [x] 8. Anything missed (§8)
- [x] VERDICT: fix three named things, then ship

**Headline:** the flicker everybody expected is not there. What is there is a
fade state machine that can be left disagreeing with where the pointer actually
is, in three different ways, two of which leave the chip either stuck on top of
your patches or missing altogether.

---

## 0. Environment and scope  — PROVEN

* Driver: `scripts/drive_49_legend_hover_verify.py` (new; `scripts/` is in scope).
  Real `MainWindow`, real Create Chart tab, real Measure tab, real `TiffPreview`.
  Pointer moves are real `QTest.mouseMove` on the **top-level window**, so Qt's
  own hit test decides which widget gets them — nothing about the mapping under
  test is re-implemented in the harness.
* Sandbox: `…/scratchpad/sandbox49`. `CHROMIQ_PRESETS_DIR`, `custom_output_path`
  and `core.settings.QSettings` all redirected. `~/ChromIQ` never touched.
  `com.chromiq.ChromIQ.plist` backed up and hash-compared on every run; it was
  modified by the first run and **restored from the backup** (the guard worked),
  and untouched on every run after.
* Charts: real, built by the real Create Chart tab with the ChromIQ layout
  engine. `legend-i1-strip` (462 patches, i1, 12 mm bottom margin) was built
  fresh this session; `cr30-aim-*` and `i1-strip-chart` (1 mm bottom margin,
  hex and rectangular, one of them 1144 patches over **3 pages**) were built by
  the same real tab in the session for report 47 and reused.
* Measurements: the `.ti3` beside each chart is produced by the project's own
  `scripts/make_demo_projects.py::_ti3_from_ti2` from the chart's **real**
  `.ti2`. No instrument, no serial device, no CR30 was touched (constraint).
  The numbers are synthesised; **the chart, the patch geometry, the overlay
  path, the placement and every hover code path are the real ones.**
* User journey to get the chip on screen: load the chart into Measure with the
  ChromIQ engine selected, tick **"Show overlay from existing measurement"**
  (#134). That is `_on_overlay_toggled` → `_show_overlay_from_existing_ti3` →
  `TiffPreview.set_patch_overlay` — the real one.

### ⚠ SCOPE CORRECTION — the code moved under me

The brief names commit `29c1a7c6`. The **working tree** carries further
uncommitted work on the same feature: a **fade** (`_legend_opacity`,
`_legend_fade`, `_apply_legend_pointer`, `_start_legend_fade`,
`_on_legend_fade_step`, `LEGEND_FADE_MS = 110`), added after
*"can be a really fast one just not this completely instant on off"*, plus a
rewritten `tests/test_legend_hover_hide.py`. **Everything below is measured
against the WORKING TREE**, because that is what would ship. Where the fade
changes a verdict I say so.

Also noted and NOT pursued (owner's ruling, report 35 R2 / `08b4bf2f`): moving
the chip below the sheet into a reserved band is off the table. Nothing below
recommends it.


### ⚠ MEASUREMENT HYGIENE — one pass is contaminated and was re-run

Mid-review the owner reported: *"sometimes during its test i moved to another
desktop and took control over the mouse when it tried to use it."* Every result
that depended on a synthesised cursor (`QTest.mouseMove`) is therefore suspect.

What I did about it:

* Everything about the **state machine** was re-run **cursor-free**, by handing
  the position straight to `TiffPreview._apply_legend_pointer`. Those runs are
  the ones this report relies on. They are marked CURSOR-FREE.
* The three faults are additionally reproduced **headless** (`QT_QPA_PLATFORM=
  offscreen`, no window, no cursor at all) by three candidate pytest cases —
  see §6. No desktop activity can affect those.
* A real cursor is used only where the **mapping** is the thing under test, and
  those runs carry a delivery guard (the widget must report the pointer position
  it was sent, or the result is discarded).
* Results I report from the contaminated pass are named as such. One of them —
  a single opacity blip on the "left edge, moving in" sweep — did **not**
  reproduce on the clean re-run and I attribute it to the interference.

---

## 1. See it on screen, and the flicker sweep  — PROVEN

**It works.** Real Measure tab, real 462-patch engine chart, the overlay turned
on through the real "Show overlay from existing measurement" checkbox.

* `M7a_window_chip_visible.png` → `M7b_window_chip_hidden.png` — the whole
  window, chip present, then gone with the pointer on it.
* `B2/B4/B5_..._x3.png` — before / during / after at 3×, with a **real** cursor.
  It disappears cleanly (only the chip's own rectangle changes, see below) and
  it comes back.

### Flicker: NONE, on all four edges, in both directions  — PROVEN

Cursor-free, 1 px per step, 12 px outside to 12 px inside and back, 24 steps per
sweep, 260 ms of settling per step (the fade is 110 ms). Two independent runs.

| edge, direction | opacity trace | turn-rounds |
|---|---|---|
| top, in | `1.0 ×14 → 0.0 ×14` | **1** |
| top, out | `0.0 ×14 → 1.0 ×14` | **1** |
| bottom, in / out | same shape | **1** / **1** |
| left, in / out | same shape | **1** / **1** |
| right, in / out | same shape | **1** / **1** |

Eight sweeps, eight single clean turn-rounds. The animation was retargeted
exactly once per sweep.

Three further stress checks, same run:

* **Sitting still on the chip for 2 s: 0 repaints.** No repaint storm.
* **40 moves wholly inside the chip's footprint: 0 repaints, chip stays gone.**
* Approaching along an edge never produced a second transition.

The anti-flicker design works, and it works for the reason the commit gives: the
rectangle is recomputed on every paint, so the hit test still has something to
test against once the chip has gone. A mutation that records the rectangle only
on paints that *draw* the chip is caught by
`test_the_rectangle_is_refreshed_even_on_the_paint_that_hides_it` (I ran it;
§6 M8).

### The fade  — PROVEN

* It is a real dissolve, not a switch: caught at **opacity 0.48, 43 ms** after
  the pointer arrived (`N0_1_fade_opacity_0p48.png`).
* Measured trace (3 ms sampling): `1.00 … 0.59 0.33 0.15 0.06 0.02 0.00`.
  About **five drawn frames**; visually complete ≈ **60 ms** after the pointer
  lands, not 110. `LEGEND_FADE_MS = 110` with `OutCubic` front-loads the
  travel — 88 % of it is done by the halfway point.
* **Verdict on 110 ms: right, and if anything on the quick side.** It reads as a
  dissolve rather than a blink, which is what was asked for, and it never keeps
  you waiting for the patch underneath. I would not lengthen it. If it ever
  reads as *too* abrupt on a slower screen, the honest lever is the easing curve
  (`InOutCubic` would spend more of the 110 ms visible) rather than a longer
  duration.

### The segfault the fade note warns about: NOT reproduced  — PROVEN

The single-retargeted-animation design holds. Cursor-free, all survived with no
crash:

* 400 reversals with **no wait at all** between them, then 400 at 2 ms, 400 at
  5 ms, 200 at 12 ms, 200 at 30 ms.
* **68 reversals driven from inside the animation's own `valueChanged`
  callback** — the exact re-entrancy the commit message blames for the original
  crash. No crash.

---

## 2. Breaking the coordinate mapping — I could not  — PROVEN

The rectangle the hit test uses was compared against the chip's **actual**
on-screen rectangle, measured independently by rendering one frame at opacity
1.0 and one at 0.0 and taking the bounding box of the pixels that differ. That
measurement does not use `mapFrom`, `mapTo`, `_paint_geom` or `_legend_geom` —
it is pixels.

| condition | remembered rect (label coords) | measured from pixels | error L/T/R/B |
|---|---|---|---|
| 1500×1000, dpr 2 | `(395, 744, 350, 24)` | `(395, 744, 350, 24)` | **0, 0, 0, 0** |

**The difference bounding box is exactly the chip's rectangle.** That is a second
result worth having: hiding the chip changes *nothing else on the canvas* — no
patch, no ring, no arrow is disturbed by the hide.

Everything else I threw at the mapping:

* **Window resized** to 1100×760, 900×620, 1900×1100, 700×900, 1040×1000 —
  the remembered rect tracks the chip every time (it is recomputed each paint
  and stored with the `(ox, oy)` it was drawn in, then translated by the
  difference against the current `_paint_geom`).
* **Multi-page** (`cr30-aim-1144`, 3 real pages): page switches re-place the
  chip (page 1 `x=80`, page 2 `x=281`) and the remembered rect follows.
* **dpr 1 and 2**: the rect and the pointer are both in *logical* coordinates,
  so the ratio cancels. Verified at dpr 2 on the real screen (error 0) and at
  dpr 1 in the offscreen renders.
* **Different margins**: 1 mm and 12 mm bottom margins, 5 mm and 1 mm sides.
* **Panning / zooming**: the Measure preview is not interactive
  (`_interactive` is False there), so there is nothing to pan. I checked the
  interactive path by reading it — `_repaint_interactive` passes the label-frame
  `(x, y)` as `(ox, oy)`, and `_paint_geom` gets the same pair, so the
  translation is zero and the mapping is consistent. **INFERENCE, not run**: no
  UI I could find puts a patch overlay on an interactive preview.
* One thing I did find by reading, and it is harmless today —
  **`_repaint_interactive` calls `_draw_cq_overlay` BEFORE it assigns
  `_paint_geom`** (lines ~3213–3215), so a hit test performed inside that paint
  would use the *previous* frame's geometry. Since `3236cb9b` the paint no
  longer performs a hit test (it draws at `_legend_opacity`), so this is
  currently inert. **INFERENCE.** Worth noting only because reinstating a
  paint-time hit test — which is one of the ways to fix Fault 2 below — would
  wake it up.

**No case was found where the chip hides while the pointer is elsewhere, or
refuses to hide while the pointer is plainly on it, that is attributable to the
mapping.** The three faults in §5 are state-machine faults, not mapping faults.

---

## 3. The two fixes

### Fix (b) — `clear()` now resets `_patch_overlay`: REAL, and it closes a real gap — PROVEN

Counterfactual, run in a git worktree of the parent commit against the same
five-item overlay:

```
HEAD (working tree):  patch_overlay items before clear()=5  after clear()=0
PARENT b46ab0cc:      patch_overlay items before clear()=5  after clear()=5
```

Reachability through the UI. `TabMeasure.set_ti1_path` calls
`_update_resume_availability` → `_discard_stale_overlay`, which clears the
overlay whenever the **chart identity changes** — so on the ordinary
chart-to-chart path the fix is belt-and-braces (confirmed on screen:
`E2_second_chart_no_stale_patches.png`, chart 1 measured → chart 2 unmeasured,
`items=0`, no colours survive).

But `_discard_stale_overlay` deliberately bows out in two cases, and in those the
only thing standing between you and someone else's readings is `clear()`:

1. **the chart identity has NOT changed** (same `.ti2`, same mtime), and
2. **a measurement is running** (`self._runner.is_running`).

I reached case 1 through the tab: with a chart loaded and measured, delete its
TIFF and let `_try_load_tiffs` run again on the **same** chart. That takes the
"No matching TIFF preview found" branch, which calls `preview.clear()` —
`_discard_stale_overlay` returns early (identity unchanged, verified `True` at
run time) and does nothing.

```
overlay items before = 368; identity unchanged after = True
after _try_load_tiffs with the TIFF gone: items=0  patch_info=0  legend=None
```

**PROVEN: the fix is not purely defensive.** `L2_after_clear_same_chart.png`.

Nothing wants the overlay to survive `clear()`. `clear()` already dropped
`_patch_info` (the hover numbers) and `_page_patch_boxes`, so keeping the
painted colours was an inconsistency, not a feature. I looked at every
`preview.clear()` caller: 14 of the 16 are `tab_chart.py` / `ti2_relayout_dialog`
/ `layout_options_panel`, which own *different* `TiffPreview` instances that
never receive `set_patch_overlay` at all.

### Fix (a) — overlay items count towards `patch_bottom`: RIGHT, but I could NOT reach the state through the UI — PARTLY PROVEN

The fix itself is proven, as a picture. Same scene, same renderer, parent above
and HEAD below — `P_parent_vs_head_no_strips.png`: with no strip geometry the
parent puts the chip **at the top of the sheet, over the column letters and the
first row of patches**; HEAD puts it in the bottom margin. 15,776 pixels differ,
bounding box `y = 10 … 792`. This is exactly the worst form of the complaint the
placement exists to prevent, and the fix removes it.

**But the commit's three claimed routes to the state do not hold up:**

| claimed route | what actually happens |
|---|---|
| "a sidecar whose page count does not match" | **Wrong way round.** I made the sidecar claim page 2 on a one-page chart: `_stripe_rects=22`, `patch_boxes=[0]` — the *patch* reader came back empty and the *strip* reader was fine. The commit says the opposite ("the strip reader is all-or-nothing where the patch reader tolerates partial pages"). With no patch boxes there are no overlay items, so the state is not reached. |
| "a chart cleared and reloaded" | `load_tiff` resets `_stripe_rects` and `_setup_stripe_rects` refills it in the same call; I could not open a window between them from the UI. |
| "an imported chart" | See below — plausible, but not wired up today. |

What I did establish, by reading and then testing:

* `TabMeasure._setup_stripe_rects` fills `_patch_boxes` from the sidecar
  **independently**, then tries three routes for strip rects: the sidecar's
  `strips` block, `_detect_uniform_stripe_rects` (from `PASSES_IN_STRIPS2` in
  the `.ti2`), and the legacy label detector. `load_tiff` has already emptied
  `_stripe_rects`, so **if all three fail, the state is exactly patches-without-
  strips.**
* I removed the `strips` block from a real chart's sidecar entirely and loaded it
  through the real tab: route 2 rescued it (`stripe_rects=22`). For a *strip*
  chart it always will — the columns are there to be detected.
* **`workflow/grid_layout_from_render.derive_grid_layout` returns a layout with
  `patches` and NO `strips` key at all** (line 254), and
  `scanin_target.build_scanin_target_from_render` writes exactly that dict to a
  `<stem>.channels.json` "so the chart is re-usable without re-deriving". That
  is an **i1Profiler-laid-out chart**: a grid, with no strip columns for routes
  2 and 3 to find. It is the honest route to the state.
* **However**, `build_scanin_target_from_render` has **no caller in `ui/`**
  today. So the sidecar shape exists in the codebase but nothing in the UI
  writes one yet.

**Verdict: the fix is correct and I would keep it, but describe it honestly.**
It is not "defensive only" — the shape it guards against is produced by shipped
code (`grid_layout_from_render`) and would arrive the moment that path is wired
to the UI. It is also not reachable through today's UI, and **the commit
message's three named routes should be corrected**: the page-count-mismatch one
is factually the wrong way round.

---

## 4. Regressions: none  — PROVEN

`scripts/render_49_reference.py` renders one fixed `TiffPreview` scene from a
real chart. The same script was run inside a `git worktree` of the parent commit
`b46ab0cc` and against the working tree, and the PNGs compared pixel for pixel.

**The "rich" scene has every overlay that shares this canvas switched on at
once:** the expected/measured split patches, the red warn rings, the CR30 aiming
body circle, the aperture warning circle, the accent "read this next" ring, the
click-to-jump patch hover outline, the strip hover frame, both bidirectional
scan arrows, "show only measured" blanking plus its cell grid, and the edge
spacers.

| scene | differing pixels, parent vs HEAD |
|---|---|
| normal chart, strip geometry present | **0** |
| rich scene, `split` wording | **0** |
| rich scene, `expected` wording | **0** |
| rich scene, `measured` wording | **0** |
| no strip geometry | 15,776 — **the fix (a) chip move, and nothing else** |
| narrow panes, `measured` wording (520/420/340/260 px) | 257 / 361 / 391 / 491 — **the elision, and nothing else**; every bounding box is inside the chip's own last few characters |

Two further regression facts, measured on the real widget:

* **Hiding the chip changes only the chip's own rectangle.** The bounding box of
  the pixels that differ between an opacity-1.0 frame and an opacity-0.0 frame
  is exactly `_legend_rect`. Nothing else moves when it goes.
* **The patch value tile** (`_PatchInfoTile`) and the **coordinate cross-hair
  overlay** (`_CursorOverlay`) both carry `WA_TransparentForMouseEvents`
  (`ui/tiff_preview.py:322`, `:259`), so neither can swallow the mouse moves the
  chip depends on. Read from source — **INFERENCE** for the tile, since a real
  pointer was needed to exercise it and that pass is the contaminated one.

---

## 5. THE THREE FAULTS

All three are **cursor-free** and additionally reproduce **headless** as pytest
cases (`QT_QPA_PLATFORM=offscreen`, no window, no cursor) — see §6.

### FAULT 1 — flick off the chip and straight back on, and it stays visible under your pointer  — PROVEN

**Mechanism.** `_start_legend_fade` begins:

```python
if abs(self._legend_opacity - target) < 0.01:
    return
```

It asks "am I already there?" and never asks "is an animation currently running
somewhere else?". When the chip is fully hidden (`opacity == 0.0`) and the
pointer leaves, a fade towards **1.0** starts *from* 0.0. Come straight back
within the first few milliseconds and the request is `target = 0.0`, the opacity
is still ≈0.0, the guard fires, **the request is dropped — and the animation
heading for 1.0 carries on and finishes.** The chip is then drawn at full
opacity with `_legend_hidden == True`.

Measured, cursor-free, on the real widget:

```
opacity at leave = 0.0000 -> 0.0000
anim end value after the leave = 1.0
guard skipped the re-hide = True
anim end value after re-entering = 1.0     <- never retargeted
SETTLED: opacity=1.000  hidden=True  painted=True   *** the chip is drawn under the pointer ***
```

The same sequence starting **mid-fade** (opacity 0.585) behaves correctly, which
is exactly why `test_turning_back_mid_fade_does_not_snap` does not catch this.

**It does not heal.** Because `_legend_hidden` is already `True`, moving *within*
the chip changes nothing (`hidden != self._legend_hidden` is false, so no fade is
started). Measured: two nudges inside the chip, opacity stays 1.000. Only a full
move-clear-and-back-on recovers it.

**How a user hits it.** A small hand jitter at the chip's edge, or a sweep that
touches the chip and comes back. With a real synthesised cursor I reproduced it
at 0 ms, 18 ms and 25 ms of dwell off the chip (that pass is the contaminated
one, so treat the exact dwell figures as indicative; the mechanism above is not).

Pictures: `N1a_pointing_at_it_chip_gone.png` (correct) →
`N1b_FAULT_flicked_off_and_back_chip_returns.png` →
`N1c_FAULT_still_there_after_moving_within_the_chip.png`.

**Severity: HIGH.** It is the feature failing at the exact moment it is being
used, and the user's natural response — jiggle the mouse on it — makes it worse,
not better.

### FAULT 2 — the chip is re-placed out from under the pointer and stays invisible  — PROVEN

Since `3236cb9b` the paint no longer decides visibility; it draws at
`_legend_opacity`, and only a **mouse move** or a **leave** ever changes that.
So when the chip moves and the pointer does not, nothing reconciles them.

Reproduced cursor-free by resizing the window — which is what a tiling shortcut,
full-screen, or a window-manager hotkey does, and none of those move the pointer
or generate a `leaveEvent` on the preview:

```
pointer on the chip's right end  -> chip hidden (correct)
window 1500x1000 -> 1040x1000    (no mouse event at all)
chip re-centres: (281,671,350,24) -> (51,619,350,24)
pointer still at (622,682); on the chip = False
opacity = 0.000       <- the chip is invisible and nobody is pointing at it
2.5 s later           -> still 0.000
```

Pictures: `N2a_before_resize_chip_hidden.png` →
`N2b_FAULT_after_resize_chip_missing.png` /
`N2c_FAULT_after_resize_whole_width.png` (the crosshair marks the pointer).

The same shape is reachable any other way the chip is re-placed without a mouse
move — a page change driven from anywhere but a click on the preview, the
overlay-mode wording changing width by 70 % (350 px → 505 px, measured), a live
measurement that moves `patch_bottom` (which fix (a) now makes possible on a
strip-less chart).

**Severity: MEDIUM-HIGH.** The chip is simply gone, with no way for the user to
guess why or how to get it back.

### FAULT 3 — a new chart inherits the previous chart's hover state, and its legend never appears  — PROVEN

`clear()` resets `_legend_rect` and `_legend_geom` but **not** `_legend_pointer`,
`_legend_hidden` or `_legend_opacity`. Point at the chip, then load a different
chart:

```
hovering chart 1: opacity 0.00
clear():          opacity 0.00, hidden True, pointer (455,682) — all carried over
chart 2 loaded:   chip (280,693,350,24), pointer (455,682), on the chip = False
                  opacity 0.000     <- the new chart has no legend at all
```

Pictures: `N3_FAULT_new_chart_has_no_legend.png`,
`N3b_FAULT_new_chart_window.png` (whole window).

**Severity: MEDIUM.** This is the same root cause as Fault 2 (state that is only
ever reconciled by a mouse event) with an extra trigger.

### A candidate fix, tested

I did not edit `ui/`. I applied this in a throw-away `git worktree` to check it
is sufficient and does not break anything; **the implementation is yours.**

1. **`_start_legend_fade`** — do not take the early return while an animation is
   running towards a different target:
   ```python
   anim = self._legend_fade
   _running = anim is not None and anim.state() == QAbstractAnimation.State.Running
   if abs(self._legend_opacity - target) < 0.01 and not _running:
       return
   if _running and anim.endValue() == target:
       return
   ```
2. **After the chip is placed** in `_draw_cq_overlay`, reconcile once, deferred
   out of the paint (a direct call would recurse: `_start_legend_fade` →
   `_on_legend_fade_step` → `_repaint_label`):
   ```python
   if self._legend_is_hidden() != self._legend_hidden:
       QTimer.singleShot(0, self._reconcile_legend_hidden)
   ```
   with `_reconcile_legend_hidden` = `self._apply_legend_pointer(self._legend_pointer)`
   behind a `sip.isdeleted(self)` guard.
3. **`clear()`** — also reset `_legend_pointer = None`, `_legend_hidden = False`,
   `_legend_opacity = 1.0`, and stop the fade.

**Result: 13/13 pass** (the 10 existing + my 3 candidate tests), and **156/156**
across `test_measure_overlay_legend`, `test_engine_ui`,
`test_warn_ring_draw_order`, `test_cr30_aiming_overlay`,
`test_hex_overlay_geometry`, `test_legend_hover_hide`. Step 2 is what makes
Faults 2 and 3 go away together; step 3 alone fixes only Fault 3.

⚠ **If you take step 2, also swap the two lines in `_repaint_interactive` so
`_paint_geom` is assigned before `_draw_cq_overlay` is called** — see §2. Today
that ordering is inert; a paint-time hit test wakes it.

---

## 6. Judging the ten tests  — PROVEN by mutation

`tests/test_legend_hover_hide.py` now holds ten. Baseline: 10 pass in 1.35 s.
Every mutation below was applied in a throw-away worktree, **asserted to have
landed**, and the file re-run.

| # | mutation | caught? |
|---|---|---|
| M1 | `_note_legend_pointer` tests the **raw widget position** — no `label.mapFrom` | **survives** (10 passed) |
| M2 | `anim.setDuration(2000)` — the fade takes two seconds (constant untouched) | **survives** (10 passed) |
| M3 | a reversal **snaps to the far end** before animating back | **survives** (10 passed) |
| M4 | `hideEvent` no longer resets the chip | **survives** (10 passed) |
| M5 | the widest wording is no longer elided | **survives** (10 passed) |
| M6 | revert fix (a) — overlay items stop counting for `patch_bottom` | caught, by its own test |
| M7 | revert fix (b) — `clear()` leaves `_patch_overlay` alone | caught, by its own test |
| M8 | the rectangle is recorded **only on a paint that draws the chip** | caught, by `test_the_rectangle_is_refreshed_even_on_the_paint_that_hides_it` |
| M9 | the pointer is never consulted (feature off) | caught, 5 tests |

**Five of nine mutations survive.** The good news first: the test the author
already strengthened (M8) is genuinely strong, and the two fix tests (M6, M7) are
real. Now the weaknesses, in the order I would fix them.

**(a) `test_the_fade_is_quick` is vacuous.** It asserts
`60 <= preview.LEGEND_FADE_MS <= 200` — a constant against a constant. It cannot
fail unless somebody edits the constant, and it measures nothing. M2 changes the
actual duration to two seconds and it passes. Fix: time the real animation, e.g.
`_apply_legend_pointer(centre)`, then `waitUntil(opacity < 0.02)` and assert the
elapsed wall time is under ~300 ms.

**(b) `test_turning_back_mid_fade_does_not_snap` does not test what it is
named.** Its only assertion after the reversal is
`assert preview._legend_opacity <= 1.0`, which is unconditionally true; it then
waits for `> 0.99`, which the *snapping* implementation reaches immediately. M3
makes the reversal snap and it passes. Fix: capture `mid` before the reversal and
assert `preview._legend_opacity == pytest.approx(mid, abs=0.05)` right after
`_forget_legend_pointer()` plus one `processEvents()`.

**(c) The coordinate mapping — the headline subtlety of the whole commit — is
untested.** Every test drives `_apply_legend_pointer` (label coordinates) or sets
`_legend_pointer` directly, so `label.mapFrom(self, pos)` is never exercised. M1
removes it entirely and all ten pass. The commit message rightly calls this out
as the thing that would have "hidden the chip while the pointer was somewhere
else entirely" — and nothing guards it. Fix: one test that goes through
`mouseMoveEvent` with a widget-frame position and asserts the chip hides;
it needs the label offset to be non-zero, which it is (25 px + centring).

Note also that `_chip_pixels()` re-implements the same
`label.mapTo` translation the code does, so even a test that used it would be
half marking its own homework.

**(d) `hideEvent` is untested.** M4 removes its whole body and all ten pass. It
is easy to cover: `_apply_legend_pointer(centre)`, `preview.hide()`, assert
`_legend_opacity == 1.0` and `_legend_pointer is None`. (The behaviour itself is
correct — I proved it on screen twice, `M5_after_tab_switch_back.png` and
`M6_after_minimise_restore.png`.)

**(e) The elision (P7) is untested.** M5 disables it and all ten pass. Cover it
by resizing the preview narrow, setting the `measured` wording, and asserting the
drawn text ends in "…" and `_legend_rect` stays inside the paper.

**(f) `test_clear_drops_the_previous_charts_patches` asserts on the attribute,
not on the picture.** `assert preview._patch_overlay == {}`. Every other test in
the file counts pixels; this one does not, so it cannot see the thing the fault
was actually about (the previous chart's colours painted over the next one).

**(g) Nothing covers the three faults in §5.** I wrote three candidate tests that
fail on the code as it stands and pass with the candidate fix — they are in the
report's §5 and reproduce headless. I have not added them to `tests/`, because
they would make the suite red before the fix lands; they are yours to take with
the fix.

---

## 7. Edge cases, each with a verdict

| case | result | verdict |
|---|---|---|
| **No chart at all** | `_legend_rect=None`, `_pixmap=None`, opacity 1.0. Pointing at the empty pane does nothing. `M1_no_chart.png` | **PROVEN — correct** |
| **Chart with no measurement** | No overlay items, `_legend_rect=None`, no chip, and the "Show overlay" box is not even offered (`_engine_selected and has_ti3` gate). `M2_unmeasured_chart_no_chip.png` | **PROVEN — correct** |
| **The three wordings** | `split` 350 px, `expected` 352 px, `measured` 505 px. All three place correctly and all three hide on hover. `M4_wording_*.png` | **PROVEN — correct** |
| **Very narrow pane (the elision)** | 520 / 420 / 340 / 260 px panes, widest wording. Parent chopped mid-word and ran off the paper; HEAD elides with "…" and stays inside. `P_narrow_elision_parent_vs_head.png` | **PROVEN — fixed** |
| **`avail - 16` can go negative** | The guard is `if tw > avail > 0`, so a 1–15 px paper width passes `avail - 16 < 0` into `elidedText`. Not reachable on any real chart (the paper is always hundreds of px), and Qt does not crash on it. | **INFERENCE — cosmetic, ignore** |
| **Chip in the bottom margin vs its fallback on the last row** | On every real chart I built — including a 1 mm bottom margin — the chip landed **in the margin, clear of the patches** (chip top 673, lowest patch 665, paper bottom 731). I could not build a real chart that forces the fallback. The fallback path itself is exercised by `P_parent_vs_head_no_strips.png`. | **PARTLY PROVEN — the overlap case exists in the code but I could not reach it with a real chart; the hover remedy is what covers it either way** |
| **Window loses focus while hovering** | Minimise → restore: pointer forgotten, `hidden=False`, opacity back to 1.0. `M6_after_minimise_restore.png` | **PROVEN — correct** |
| **Pointer leaves without a `leaveEvent` (tab switch)** | Hide chip → Create Chart tab → back to Measure: pointer `None`, opacity 1.0. `hideEvent` does its job. `M5_after_tab_switch_back.png` | **PROVEN — correct** |
| **Keyboard-only user** | `TiffPreview.focusPolicy() == NoFocus`, `_img_label.focusPolicy() == NoFocus`. There is **no** keyboard route to move the chip out of the way. | **PROVEN — a gap, and a small one** |
| **Touch** | `WA_AcceptTouchEvents == False`; a touch device synthesises a mouse press/release but no hover, so a touch user cannot move the chip either. | **PROVEN — a gap, and macOS-irrelevant today** |

On (i) keyboard and (j) touch: I would **not** add a shortcut for this. It is a
cosmetic overlap on a preview, the wording is short, and the run of the app does
not depend on reading through it. Worth one line in the tooltip at most.

---

## 8. Anything else I found

1. **The overlay does not come back after a transient TIFF loss.** In §3's
   `clear()` experiment, after the TIFF was restored and `_try_load_tiffs` ran
   again, `items=0` and `legend=None` — while the **"Show overlay from existing
   measurement" checkbox is still ticked**. The box says one thing and the
   preview shows another. Pre-existing, not caused by this work, and a narrow
   path; noted because it is the same "what the box says is what you see" rule
   the code already fixed once (`tab_measure.py:4370`).

2. **`_legend_hidden` is a cache of something already derivable.** It exists only
   to decide "has the state changed?", and every one of the three faults is a
   consequence of it going stale. Consolidating on "recompute at paint, animate
   towards the answer" would remove the whole class. That is a bigger change than
   the §5 candidate fix and I am not proposing it now — just naming the shape.

3. **Consistency with the rest of the preview: good.** The chip is the only
   element on this canvas that responds to hover by *disappearing*; the strip
   frame, patch outline and value tile all respond by *appearing*. That reads
   fine because the chip is the only one that is in the way, but if a second
   element ever gains "get out of the way" behaviour they should share one
   mechanism rather than each grow their own opacity.

4. **The `docstring` on `_start_legend_fade` overstates the design.** It says the
   animation is *"never stopped and replaced"* — it is not replaced, but
   `anim.stop()` is called on it three lines below. Worth a wording tweak so the
   next reader does not go looking for a `stop()` that "should not be there".

5. **The commit message for `29c1a7c6` names three routes to the strips-empty
   state and at least one is the wrong way round** — see §3. Worth correcting in
   place, since the reasoning will be read again the next time the placement is
   touched.

6. **No, I am not proposing the caption band.** Recorded ruling R2
   (`08b4bf2f`, report 35): it costs preview height, which is what is being
   protected. Everything above judges hover on its own terms.

---

## VERDICT

**Fix these three things first, then ship.** Ranked.

### 1. FAULT 1 — flick off and back leaves the chip drawn under your pointer, and it does not recover. **BLOCKING.**
The one-line guard in `_start_legend_fade` drops a legitimate re-hide whenever
the opacity already equals the new target. Reproduced cursor-free and headless,
deterministic, and it is the feature failing in the middle of being used. §5,
`N1b`/`N1c`.

### 2. FAULT 2 — the chip is re-placed out from under the pointer and stays invisible. **BLOCKING.**
Resize the window with a tiling shortcut while pointing at the chip and the
legend is gone until you find it and point at it again. Since the fade landed,
nothing reconciles placement with hover state. §5, `N2b`/`N2c`.

### 3. FAULT 3 — a new chart inherits the previous chart's hover state and shows no legend. **SHOULD FIX.**
Same root cause; `clear()` does not reset the hover fields. Cheap to fix on its
own even if 2 is deferred. §5, `N3`.

### 4. The five surviving mutations. **SHOULD FIX, with the code.**
Two tests are vacuous as written (`test_the_fade_is_quick`,
`test_turning_back_mid_fade_does_not_snap`), and the mapping, `hideEvent` and the
elision have no cover at all. §6 (a)–(e). My three candidate tests in §5 go in
with the fix.

### 5. Corrections to the prose. **NICE TO HAVE.**
The commit message's three routes to the strips-empty state (§3) and the
`_start_legend_fade` docstring (§8.4).

### What is already good, and I would not touch

* **No flicker.** Eight one-pixel sweeps, four edges, both directions, one clean
  turn-round each. This is the thing the design was most likely to get wrong and
  it got it right, for the stated reason.
* **The mapping is exact** — 0 px error at dpr 2, and hiding the chip disturbs
  nothing but the chip's own rectangle.
* **No regression anywhere else**: 0 differing pixels against the parent commit
  with every other overlay on at once, in all three wordings.
* **No segfault**, including 68 reversals driven from inside the animation's own
  callback.
* **110 ms is right.** It reads as a dissolve, is visually complete in ~60 ms,
  and never keeps you waiting.
* **Fix (b) is real**, not defensive: proven counterfactually against the parent,
  and reachable through the tab on the same-chart route.
* **Fix (a) is right**, and the picture proves it; only its stated justification
  needs correcting.


---

## Final confirmation

Re-checked at `396d9b82` (the tip at the time of writing). `ui/tiff_preview.py`
and `tests/test_legend_hover_hide.py` are **unchanged since `3236cb9b`**, so
everything above describes the code as it stands.

```
tests/test_legend_hover_hide.py            10 passed
tests/test_legend_candidate.py (mine)       3 FAILED   <- the three faults, still there
```

The three candidate tests are saved at
`…/scratchpad/sandbox49/test_legend_candidate.py`; they are **not** committed,
because they would make the suite red before the fix lands.

Driver: `scripts/drive_49_legend_hover_verify.py` (phases A–N).
Renderer: `scripts/render_49_reference.py`.
Proof shots + README: `~/Desktop/cr30-legend-hover-verify/`.
