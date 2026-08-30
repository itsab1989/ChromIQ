# 47 — Aiming overlay: adversarial verification of 6b879c6e

**Status:** COMPLETE.
**Started:** 2026-08-30
**Under test:** commit `6b879c6e` "The Measure tab shows where the CR30 will actually sit"
**Design:** `docs/cr30_reports/46_aiming_overlay_design.md`, mockup `docs/design/mockups/cr30/aiming-circle.png`
**Proof screenshots:** `~/Desktop/cr30-aiming-overlay-proof/`

Every claim below is tagged **PROVEN** (I ran it) or **INFERENCE** (read from code
only). Nothing is asserted from memory.

## Contents
1. Setup and safety
2. See it, and show it (mockup fidelity)
3. The visibility rule
4. The scale
5. The aperture rule
6. Persistence
7. Regressions
8. The tooltip text
9. Anything missed
10. Verdict

---

## 1. Setup and safety

Driver: **`scripts/drive_47_aiming_overlay_verify.py`** (new, this report).
It drives the real `MainWindow`, the real `TabChart`, the real `TabMeasure` and
the real `TiffPreview`. Nothing about the overlay is re-implemented in the
driver; the only thing faked is the instrument, which was not touched.

Safety, all **PROVEN** (printed by the driver on every run):

| Guard | How |
|---|---|
| `~/Library/Preferences/com.chromiq.ChromIQ.plist` | copied to the sandbox on entry, SHA-256 compared on exit, restored if it differs. Every run so far printed `plist untouched (sha 4d35a1b1b7a8066c)`. |
| Any `AppSettings()` anywhere in the app | `core.settings.QSettings` is replaced with a factory returning a sandbox `.ini`, so even a widget that builds its own `AppSettings` cannot reach the plist. |
| Presets | `CHROMIQ_PRESETS_DIR` set to the sandbox before any import. |
| Project folder | `custom_output_path` = the sandbox. `~/ChromIQ/CR30-Test` never referenced. |
| Modals | `QDialog.exec` stubbed to 1 and the four `QMessageBox` statics stubbed to 0 — no modal is ever left waiting. |
| Serial | nothing in the driver opens a port; no `chartread`, no engine helper, no `_cr30_bridge` is ever constructed. |

Sandbox: `…/scratchpad/sandbox47`.

### Charts built by the app itself — PROVEN

| Name | Instrument | Shape | Patches | Patch size | dpi |
|---|---|---|---|---|---|
| `cr30-aim-hex` | CR30 | hexagonal, area-first | 432 (1 page) | 12.11 × 10.50 mm (143 × 124 px) | 300 |
| `cr30-aim-rect` | CR30 | rectangular, area-first | 368 (1 page) | 12.53 × 12.62 mm (148 × 149 px) | 300 |
| `i1-strip-chart` | i1Pro | clip strip, patch-first | 462 (1 page) | 8.04 × 10.08 mm | 300 |

Margins 1/6/2/1 mm in every case (the same set report 46 used).

## 2. See it, and show it — the overlay against the mockup

**PROVEN. You built the agreed thing.**

`I1_mockup_left_real_app_right.png` puts `docs/design/mockups/cr30/aiming-circle.png`
next to the real `TiffPreview` at the same scale. Everything the mockup's own
caption promises is on screen:

| The mockup says | The app does | How I know |
|---|---|---|
| 33 mm body **to scale** | 32.99 mm (hex, 300 dpi) and 33.01 mm (tiny chart) | PROVEN — phase G, §4 |
| **dashed**, so patch borders stay visible | dash 9 px / gap 7 px, patch edges legible through it | PROVEN — `C3_hex_closeup_x3.png` |
| white casing on **BOTH sides** of each dash | radial profile across a dash: `W1.0dev · G4.0dev · W2.0dev` at 270°, `W1.0 · G3.0 · W1.0` at 0/30/60° — white on both flanks of every dash | PROVEN — radial scan of `C3_hex_closeup_x3.png`; matches the pens (casing 4.4 logical px under accent 2.0 → 1.2 px of white each side) |
| accent ring on top | the ring that says "this patch" is drawn after and stays whole | PROVEN — visible in every close-up; paint order in `ui/tiff_preview.py` puts the aim block above the ring block |

The dash-pattern-in-pen-width-units trap report 46 flagged **is handled
correctly**: measured on screen, the casing dashes and the accent dashes line
up, because `setDashPattern([9/w, 7/w])` cancels Qt's multiplication.

**Legibility.** In `C3_hex_closeup_x3.png` the circle crosses black, bright
green, red, magenta, light blue and white paper on one sheet. It is legible on
all of them: the white casing carries it over the dark patches, the dark green
carries it over the white. In `C3_rect_closeup_x3.png` the same holds on the
rectangular chart. I could not find a patch colour that swallows it.

**Hexagonal vs rectangular** — identical geometry, and the accent ring stays
shape-aware (hexagon on the hex chart, square on the flat chart). PROVEN,
`C3_hex_closeup_x3.png` / `C3_rect_closeup_x3.png`.

**Two cosmetic differences from the mockup, both harmless:**
1. The mockup's dashes are slightly longer relative to the circle. The app's
   are the same absolute size at every zoom (they are in screen pixels, not
   image pixels), which is the right choice and not what the mockup shows.
2. Nothing else. Side by side they read as the same drawing.

## 3. The visibility rule

**One real defect, everything else correct.**

| Case | Wanted | Got | Verdict |
|---|---|---|---|
| **No chart loaded (app just opened)** | hidden | **SHOWN, in both modules** | ✗ **FINDING 1** |
| Non-CR30 chart (i1Pro `.ti2`) | hidden | hidden, both modules | ✓ PROVEN |
| CR30 chart (`.ti2`) | shown | shown, both modules | ✓ PROVEN |
| **Reopen trap — the tab handed the `.ti1`** | shown | `read_target_instrument(.ti1)` = `None`, `_chart_is_cr30()` = `True`, row **shown** | ✓ PROVEN — the trap is avoided |
| CR30 → i1 → CR30 | follows | follows both ways | ✓ PROVEN |
| Guided ↔ Manual | both follow | both follow | ✓ PROVEN |
| Sidecar missing / corrupt / no `dpi` | row shown, nothing drawn | exactly that | ✓ PROVEN (see §4) |
| Multi-page, page without the armed patch | nothing | 0 overlay pixels | ✓ PROVEN |

### FINDING 1 — the row is on screen before any chart is loaded

**PROVEN.** `B1_no_chart_row_WRONGLY_SHOWN.png`, `B1b_no_chart_group_WRONGLY_SHOWN.png`:
a freshly opened window, `_ti1_path = None`, `_chart_is_cr30() = False`, and
"Show where the instrument will sit" is sitting in the Live-preview group of
**both** modules, ticked.

Cause, from the code: `_apply_cr30_aim_visibility()` is reached **only** from
`_apply_cr30_dead_options()`, which is called from `set_ti1_path` (`:3485`) and
the two target-settings paths (`:1310`, `:1321`). None of those runs while the
tab is being built, and `QCheckBox` is born visible. So the row ships visible
and is hidden by the first chart load.

This also makes the tooltip's last sentence false in that state — *"This option
appears for the CR30 only"* — see §8.

Report 46 §4 case 1 asked for hidden here, and it is the only edge case in that
table the build misses. Fix: call `_apply_cr30_aim_visibility()` once at the end
of the tab's construction (or default the two widgets to `setVisible(False)` at
creation, which needs no new call site at all).

### The hole test — PASSES

**PROVEN.** Live-preview group height, measured with the module actually on
screen and the layout activated:

| state | Guided | Manual |
|---|---|---|
| CR30 chart (row shown) | 126 px | 126 px |
| i1 chart (row hidden) | **98 px** | **98 px** |

28 px difference = the row's own height plus the group's 6 px `QVBoxLayout`
spacing. Nothing is left behind: `QLayout::isEmpty()` treats the whole
`aim_row` as empty once both widgets are hidden, so the spacing goes with it.
`B2b_i1_group_row_gone_no_hole.png` next to `B3b_cr30_group_row_present.png`
shows the group closing up cleanly, frame and all.

Report 46 §3a recommended a **container QWidget** to guarantee this; you hid the
two widgets instead. It happens to work — but only because `aim_row` holds
nothing but those two widgets, a spacer and a stretch. Add a third widget to
that row that is not hidden with them and the hole comes back. Worth a comment
at least; a container is still the safer shape.

## 4. The scale

**The 33 mm claim is honoured. PROVEN, measured off the screen.**

Method (phase G): render the identical scene with `set_aim_overlay(False)` and
`(True)` and diff. Every changed pixel **is** the overlay, whatever colour the
paper under it happens to be. My first attempt hunted for `#1f8f6b` pixels and
measured **292 mm** — it had found a chart patch of nearly that colour. The
diff method has no such failure mode.

| Chart | dpi | body stroke, inner → outer | centreline diameter | claimed |
|---|---|---|---|---|
| `cr30-aim-hex`, 432 hexagons | 300 | 36.02 → 42.45 logical px | **32.99 mm** | 33.00 mm |
| `cr30-aim-tiny`, 3.05 mm squares | 300 | 36.98 → 42.66 logical px | **33.01 mm** | 33.00 mm |
| `cr30-aim-600dpi`, 368 squares | **600** | — | body = 779.5 image px = **33.00 mm** | 33.00 mm |

Cross-check from the chart's own geometry: the hex chart's patch is 12.11 mm
wide, and the drawn circle is **2.745 patch widths** across; 33 / 12.11 = 2.726.
The 0.7 % excess is the box-vs-hexagon width difference, not a scaling error.

**Non-300 dpi works.** `cr30-aim-600dpi` was built through the real Create
Chart tab with the dpi spin set to 600; the sidecar records `dpi: 600`, the tab
computes 779.5 image px (double the 300 dpi figure) and the circle is still
33.00 mm on paper. PROVEN.

**Unknown dpi draws nothing, and it is nothing — not a wrong-sized circle.**
Three separate ways of losing the scale, all PROVEN:

| Sabotage | `_cr30_aim_diameters_px()` | preview |
|---|---|---|
| `channels.json` deleted | `(0.0, 0.0)` | `_aim_overlay = False` |
| `channels.json` = `{ this is not json ` | `(0.0, 0.0)` | `_aim_overlay = False` |
| `layout.dpi` key removed | `(0.0, 0.0)` | `_aim_overlay = False`, `body_px = 0.0` |

The `and body > 0` in `_apply_active_view_settings` and the `_aim_body_px > 0`
in the paint block are belt and braces; either alone would do it.
`B9_no_dpi_nothing_drawn.png` is the armed patch with the accent ring and no
circle at all.

## 5. The aperture rule — **THE FEATURE DOES NOT WORK**

The rule itself is implemented exactly as ruled. What is on the screen is not.

### The rule fires correctly — PROVEN

| Chart | patch | aperture | `aperture >= min(patch)` | overlay pixels inside the patch width |
|---|---|---|---|---|
| `cr30-aim-hex` | 12.11 mm (143 × 123 px) | 4.00 mm (47.2 px) | False | **0** — correctly hidden |
| `cr30-aim-tiny` | **3.05 mm** (36 × 36 px) | 4.00 mm (47.2 px) | True | 119 |

A patch smaller than the aperture **is** reachable through the UI: Manual →
CR30 → Rectangular → patch-first, patch size 3.0 × 3.0 mm, 120 patches, and the
app builds it without a murmur (`D3_tiny_patch_full_window.png`). So the "no
layout-time guard" ruling really does leave this overlay as the only warning.

### FINDING 2 — the warning vanishes in any window below ~1500 × 1000

**PROVEN.** The Measure preview is **not interactive** — `TiffPreview._interactive`
is `False` unless `set_interactive(True)` is called, and nothing in
`tab_measure.py` calls it. There is no zoom and no pan. So the on-screen scale
`s` is decided entirely by the size of the preview pane, and `_aim_circle`
refuses to draw below `rad < 4.0`:

| ChromIQ window | `s` | patch on screen | aperture radius | drawn? |
|---|---|---|---|---|
| 1500 × 1000 | 0.2042 | 7.4 px | 4.82 px | yes — 119 pixels |
| **1280 × 860** | 0.1587 | 5.7 px | 3.75 px | **NO — 0 pixels** |
| **1100 × 760** | 0.1296 | 4.7 px | 3.06 px | **NO — 0 pixels** |

`F6_tiny_1500x1000.png`, `F6_tiny_1280x860.png`, `F6_tiny_1100x760.png`.
The only place a too-small patch is ever visible disappears when the user makes
the window smaller — silently, with the checkbox still ticked and the tooltip
still promising it.

### FINDING 3 — even when it draws, the accent ring covers it

**PROVEN.** `H1_tiny_armed_patch_x10.png` is the armed 3.05 mm patch at ten
times magnification, straight out of the app. There is no visible circle: a
pale-green *glow* leaks out around the accent square and that is all.

The arithmetic agrees. On a 7.4 px patch the ring goes thin
(`RING_SMALL_PATCH_PX = 24`), so halo `5.0` + accent `1.0`, painted **after** the
aim block and therefore on top. The halo alone reaches 3.7 + 2.5 = 6.2 logical
px from the centre; the aperture circle's stroke spans 2.62 → 7.02 px. Almost
all of it is underneath. What survives — 119 device pixels, roughly one pixel
wide, poking past the flat sides of the square — is the entire warning.

It is also **the same colour as the accent ring and the body circle**
(`#1f8f6b`). A signal that says "there is a problem here" is drawn in the colour
that means "this is your patch".

**This is the finding I would hold the ship for.** The ruling was that the
overlay is the only place a too-small patch is visible. On this build it is not
visible. Three fixes, any of which would do it, all one-liners in the paint
block:

1. Draw the aperture circle **after** the accent ring instead of before it.
2. Draw it in the warn red `#ff2b2b` that the flagged-patch rings already use,
   so it cannot be mistaken for the accent family.
3. Drop or lower the `rad < 4.0` suppression **for the aperture circle only** —
   it exists to stop dash noise, and the aperture circle is not dashed. At
   `rad ≥ 2` it is still a legible ring against its white casing.

(1)+(2) together turn `H1_tiny_armed_patch_x10.png` from a glow into a red ring
overflowing a small square, which is what the ruling asked for.

## 6. Persistence — all five hooks work

Every row **PROVEN** in the real window (phase E).

| Check | Result |
|---|---|
| Fresh install (empty settings store) → new `MainWindow` → CR30 chart | **ticked** (`E4_fresh_install_on_by_default.png`) |
| Untick in Manual → Save as Defaults → untick in Guided → Save as Defaults | `measure_aim_help=False`, `manual2_aim_help=False` in the store |
| …then a brand-new `MainWindow` on the same store | **still unticked**, and `preview._aim_overlay = False` (`E3b_after_restart_still_off.png`) |
| Linked pair, Guided → Manual | set Guided off → Manual goes off |
| Linked pair, Manual → Guided | set Manual on → Guided goes on |
| Preset: collect → apply | `False` round-trips as `False`, `True` as `True` |
| **Preset written before the feature existed** (no `aim_help` key) | applies as **True** — the aid is not silently withheld |
| Per-target: `snapshot()` | `aim_help_manual` and `aim_help_guided` both present with the right value |
| Per-target: `apply()` | both restored, `unknown = []` |

### FINDING 4 (minor, pre-existing shape) — a target stored before today leaks

A `meta.json` written before this commit has a Measure record with no
`aim_help_*` keys. `measure_settings.apply()` only writes keys it finds, and
`_finish_half_covered_pairs` only helps when *one* half is present — so with
**neither** half present the checkbox keeps whatever the **previous target** left
on screen. PROVEN: `apply(legacy_snapshot)` left both widgets at `True` after I
had set them `True`, and would equally have left `False`.

This is the §4 leak `docs/design/per_target_settings.md` exists to prevent, and
it is the same shape Knut reported in beta.3. It is transient (the first save of
that target fixes it) and it is **identical to what happened when
`only_measured` / `patch_tile` were added**, so it is not a regression this
commit introduced. Worth knowing; worth a one-line default in `apply` some day.

### The drift test — answered precisely

`tests/test_measure_settings.py::test_the_drift_guard_every_setting_is_mapped_or_explained`
compares `MeasureParams` fields against `MEASURE_CONTROLS`. `aim_help_*` is not
a `MeasureParams` field (it is a view preference, like its three siblings), so
**that** test does not cover the new entries and cannot.

`test_every_mapped_control_exists_on_the_real_tab` **does**: it builds a real
`TabMeasure` and asserts every `MEASURE_CONTROLS` key resolves to a live widget
*and* appears in `snapshot()`. Both new keys pass it. Verified by running
`tests/test_measure_settings.py` (139 passed with `test_i18n` and
`test_message_catalogue`).

The unguarded direction is still unguarded: a Live-preview control added to the
tab and *not* added to `MEASURE_CONTROLS` fails no test. Pre-existing.

## 7. Regressions — none

### The paint is byte-identical to the parent commit — PROVEN

`render_reference()` builds one scene through the real `TiffPreview`: the real
432-hexagon CR30 chart, every 37th patch flagged (so the two-pass warn rings are
exercised, including adjacent pairs), an armed patch with the accent ring, and a
hovered patch with the hover outline. It runs unchanged on this tree and in a
`git worktree` at **`6b879c6e^`**, because it uses only APIs that predate the
commit.

```
identical bytes: True  (294840 vs 294840)
```

`F1_scene_this_tree.png` and `F1_scene_parent_commit.png` are those two files.
The warn rings, the accent ring, the hover outline and the strip geometry are
**pixel for pixel** what they were before the overlay existed.

That is not luck. Reading the paint code: the aim block runs only when
`_active_patch_box is not None`, which is exactly the condition under which the
accent-ring block already sets `Antialiasing = True` and `NoBrush`. So the two
state changes the aim block makes are ones the next block was making anyway —
no leak into the hover outline, the strip outline or the legend chip.

### Paint cost on the owner's 1144-patch sheet — negligible

I built `cr30-aim-1144` in the app: **1144 patches, 3 pages, 432 on page 1**.

```
_repaint_label: overlay OFF 2.2 / 2.2 ms, ON 2.4 ms   (delta +0.21 ms)
```

Timing `pv.repaint()` measures nothing here — the widget's `paintEvent` only
blits a finished pixmap, and the whole overlay is drawn in `_repaint_label`.
Timed there, the overlay costs **0.21 ms**, i.e. ~9 %, and it is O(1) in patch
count as report 46 predicted.

### The rest

| Case | Result |
|---|---|
| High-DPI | every measurement above was taken at **dpr = 2.0** on this Retina display, so high-DPI *is* the tested case. PROVEN |
| "Show only measured patches" ON | circle lands correctly on the blanked sheet; the neighbour cue is weaker on white, as report 46 predicted. `F3_only_measured_on.png` |
| Multi-page, other page | **0 overlay pixels** on page 2 of 3. PROVEN |
| Small window / zoomed-out preview | body circle survives everywhere down to 900 × 620 (radius 16.4 px); the aperture circle does not — FINDING 2 |

## 8. The tooltip, read as a beginner would

The label — "Show where the instrument will sit" — is good: short, plain, says
the outcome. It carries no "CR30", which is right while the row is CR30-only
(and wrong today because of FINDING 1).

Sentence by sentence:

| Claim | Verdict |
|---|---|
| "the patch you are being asked to read gets a dashed circle around it, drawn to scale" | **TRUE.** 32.99 mm measured. PROVEN |
| "exactly how much of your chart the body of your CR30 will cover" | **TRUE** as an outline of the 33 mm body |
| "The instrument is 33 mm across" | **Sourced**, not verified by me. CHNSpec's CR-series brochure per report 46 §2. ⚠ see FINDING 6 |
| "completely hides the patch the moment you lower it" | **TRUE** for any patch this app builds |
| "line the circle up on screen first … place the instrument so those same neighbours are evenly covered" | **UNPROVEN ASSUMPTION.** See FINDING 5 |
| "A second, much smaller circle appears only when there is a problem" | **FALSE as shipped.** It does not appear below a ~1500 × 1000 window, and where it does appear it is a one-pixel fringe under the accent ring. FINDINGS 2 and 3 |
| "part of what the instrument reads is the neighbouring patch" | **TRUE** on an abutting layout; on a chart with spacers the overflow is onto paper, not a neighbour. Pedantic, but the sentence states it as certain |
| "that reading will be wrong no matter how carefully you aim" | **TRUE** given the stated condition (patch smaller than the aperture) |
| "build the chart again with fewer or larger patches" | **HALF TRUE.** In area-first, fewer patches → larger patches. In **patch-first** — which is how I built the 3 mm chart — the patch size is typed in directly and reducing the count changes nothing. The advice can send a user in a circle |
| "It changes nothing about your measurements; it only draws on the preview" | **TRUE.** PROVEN by the byte-identical parent-commit render |
| "This option appears for the CR30 only" | **FALSE today** — it appears with no chart loaded (FINDING 1) |
| "because it is the only instrument ChromIQ asks you to aim by hand" | **FALSE.** Patch-by-patch is a normal user checkbox for every other instrument (`_apply_cr30_pbp_lock` only *forces and locks* it for the CR30; for an i1Pro or a ColorMunki the box is enabled and unlocked). Anyone reading a chart with `-p` places the instrument by hand and gets the accent ring but no circle. The true sentence is "the only instrument ChromIQ **always** reads one patch at a time" |

**What is missing:** the design draft (report 46 §5) ended with *"The circles
appear while a measurement is running, on the patch ChromIQ highlights for
you."* That sentence was dropped. It is the one a beginner most needs: today
they can tick the box, look at a loaded chart and see **nothing at all**,
because no patch is armed until a session starts. Nothing on screen explains
that.

**Tone/jargon:** clean. "measuring opening" instead of "aperture" is a good
call. No history, no version numbers, no Markdown. Length (4 paragraphs) is in
line with its neighbours in the same group.

**German:** `python scripts/i18n_extract.py --missing de` → `0 missing of 4642`.
`tests/test_i18n.py` and `tests/test_message_catalogue.py` pass. PROVEN.

## 9. Anything you missed

### FINDING 5 — nothing establishes that the aperture is at the centre of the body

The circle is drawn concentric with the armed patch, and the tooltip's whole
technique ("place it so those same neighbours are evenly covered") is only
sound if the 4 mm aperture sits at the **geometric centre** of the 33 mm
footprint. I searched `chromiq-cr30-research/EXPERIMENTS.md` and every
`docs/cr30_reports/*.md`: the 4 mm aperture and the 33 mm body are both
recorded, and **nothing records their relationship**. If the aperture is
offset — many hand colorimeters put it off-centre so the body can be gripped —
the advice is wrong and the circle should be drawn offset.

This is a two-minute measurement on the owner's unit and it is worth taking
before the tooltip tells people to aim by it. INFERENCE flagged as such;
not a code defect.

### FINDING 6 — the commit message over-states the sourcing of the body diameter

`6b879c6e` says the figures are *"confirmed independently by measuring the
owner's unit (EXP-018)"*. `EXPERIMENTS.md:618` says **"Aperture 4 mm (operator,
measured)"** and nothing else; the string `33 mm` does not occur anywhere in
that repo. So the **aperture** has two independent sources and the **body
diameter** has one — the brochure. The constants' own comment in
`instruments.py` makes the same conflation. Not a behaviour defect; it matters
because the comment tells the next reader the number is doubly attested when it
is not.

### FINDING 7 — the checkbox is a silent no-op when the sidecar is gone

With `channels.json` missing or corrupt the row stays visible and ticked and
draws nothing, for ever, with no explanation. That is report 46's stated design
("the checkbox stays visible but the overlay stays silent") and I am not asking
you to change it against a ruling — but it is the one state where the app
promises a drawing and never produces one. Greying the checkbox with the tab's
usual "why" tooltip would cost four lines and would match how
`_apply_cr30_dead_options` already speaks about options it cannot honour.

### FINDING 8 — no test covers any of it

`grep` across `tests/` finds no reference to `set_aim_overlay`,
`_cr30_aim_diameters_px`, `_apply_cr30_aim_visibility`, `CR30_BODY_DIAMETER_MM`
or the aperture rule. The only new test lines in the commit teach an existing
stand-in about two new method names. Everything in this report was proved by
driving the app; nothing in the suite would notice if it broke tomorrow. The
cheap ones — `_cr30_aim_diameters_px` returns `(0,0)` for a missing/dpi-less
sidecar, `47.2 px` at 300 dpi and `94.5 px` at 600; the visibility rule against
a `.ti1` path; `set_aim_overlay(True, …, 0)` draws nothing — are all pure and
need no window.

### Smaller notes

* `_apply_cr30_dead_options` now also calls `_apply_active_view_settings()`.
  That is safe — `_apply_active_view_settings` is the only caller of
  `set_overlay_mode` / `set_show_only_measured` / `set_show_patch_tile` anywhere
  in `ui/` and `workflow/`, so re-running it is idempotent (PROVEN by grep).
  It does add a `_schedule_refresh()` to every chart load and every target
  switch. Harmless, worth knowing.
* `set_ti1_path(None)` raises `TypeError` in `core/stem_paths.without_ext`.
  No caller passes `None` (four in `main_window.py`, two in `tab_measure.py`,
  all real paths), so it is not a user path — but it is why my first "no chart"
  probe crashed, and a `None` guard is one line. **Pre-existing, not yours.**
* The body circle is drawn over a neighbour's red warn ring where they cross.
  Correct by the agreed paint order; just noting it is a thing that happens.
* Report 46 §3d floated following the **hover** patch as well, and the same
  circle in Create Chart's preview before printing. Both still open, both still
  sensible; the Create Chart one would let a user see the 3 mm problem *before*
  spending a sheet, which is worth more than the aperture circle ever will be.

## 10. Verdict

**Fix these named things first — then ship.** The body circle, which is the
feature, is right: sourced, to scale to 0.02 mm, drawn like the mockup, legible
on every patch colour, free of regressions and free of measurable cost. The
aperture warning, which is the safety half, does not work.

Ranked:

1. **FINDING 3 — the aperture warning is invisible under the accent ring.**
   `H1_tiny_armed_patch_x10.png` is the proof. Draw it after the ring and in
   `#ff2b2b`. Without this, the ruling "this is the only place a too-small
   patch is visible" is not satisfied by the code that was written to satisfy
   it.
2. **FINDING 2 — and it vanishes entirely below a ~1500 × 1000 window**, because
   the Measure preview cannot zoom and `rad < 4.0` suppresses it. Exempt the
   aperture circle from that threshold, or lower it — it is not dashed, so the
   reason for the threshold does not apply to it.
3. **FINDING 1 — the row is on screen before any chart is loaded.** One call at
   the end of construction, or `setVisible(False)` at creation. It also makes
   the tooltip's closing sentence false.
4. **§8 — two tooltip sentences that are not true** ("the only instrument
   ChromIQ asks you to aim by hand"; "fewer or larger patches") and **one that
   is missing** ("the circles appear while a measurement is running"). The
   second is the one a beginner will trip over.
5. **FINDING 5 — measure whether the aperture is centred in the body** before
   the tooltip tells people to aim by an even ring of neighbours.
6. **FINDING 8 — add the four cheap unit tests.** None of them needs a window.
7. FINDING 6 — correct the sourcing comment in `instruments.py`.
8. FINDING 7 / the hidden-row container / the legacy per-target leak — take or
   leave.

Nothing here is a regression, and nothing here threatens anything that already
works. Items 1–3 are the difference between an aid that does what it claims and
one that claims more than it does.

---

### What I did not do
* The CR30 was never touched; no serial port was opened. Readings were never
  simulated either — I armed patches through the tab's own `_on_patch_ready`,
  which is the production path with the instrument bridge absent.
* No `pytest --runslow` (yours to run). I ran `test_measure_settings.py`,
  `test_i18n.py` and `test_message_catalogue.py`: 139 passed.
* No source outside `scripts/` was edited. `scripts/drive_47_aiming_overlay_verify.py`
  is new and is the whole apparatus.

---

## Addendum — live toggling (phase J, run after the sections above)

**PROVEN.** With a patch armed on the 432-hexagon CR30 chart:

| Action | `preview._aim_overlay` |
|---|---|
| tick the box in **Manual** | `True` → circle on screen (`J1_manual_checkbox_on.png`) |
| untick it | `False` → circle gone (`J2_manual_checkbox_off.png`) |
| tick again | `True` |
| the same three in **Guided** | identical (`J1_guided_checkbox_on.png`, `J2_guided_checkbox_off.png`) |

So the control works live, mid-session, in both modules, without reloading the
chart.

**One pre-existing wrinkle, not caused by this commit.** With Guided on screen,
writing to `_m_aim_help` mirrors into `_g_aim_help` — and `_mirror` does it
inside `dst.blockSignals(True)`, so `_on_view_control_changed("g")` never fires
and the preview is not refreshed. Measured: the Guided box read **unticked**
while the circle was still drawn.

`_g_overlay_mode`, `_g_only_measured` and `_g_patch_tile` all behave exactly the
same way — this is the established pattern, not a new fault, and the new control
follows it correctly. It is also close to unreachable in practice: a module's
box can only be changed while that module is on screen, and every settings-load
path ends in `_apply_active_view_settings()`, which resyncs. Recording it so it
is not rediscovered as a new bug.
