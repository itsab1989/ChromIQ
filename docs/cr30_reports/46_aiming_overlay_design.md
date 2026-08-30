# Report 46 — The CR30 aiming-help overlay: design critique before implementation

**Status: COMPLETE.**
Date: 2026-08-30. Author: the review agent, at the implementer's request.

Scope:
- Task 1: critique of the proposed Measure-tab aiming overlay (placement, visibility
  source, what it draws, when, what it must not do), the aperture-diameter sourcing
  problem, edge cases, tooltip draft, verdict.
- Task 2: real-app before/after proof of the flagged-ring two-pass fix (6428fd2c).
- Task 3a: margins-are-law rlwi band fix specification (owner: no printtarg parity
  needed in manual mode).
- Task 3b: re-verification of report 44's layout-control placement recommendation.

Legend: every claim is tagged **PROVEN** (ran it / read the exact code) or
**INFERENCE** (reasoned, not executed).

## 1. What the code does today — the reuse inventory

All **PROVEN** by reading the named lines on this working tree (post-6428fd2c).

**Already exists and does part of the job:**
- `TabMeasure._chart_is_cr30()` (`ui/tabs/tab_measure.py:5519`) — THE single
  CR30 question for the tab, resolving through `_chart_file_for` so it reads the
  `.ti2` (where `TARGET_INSTRUMENT` lives), not the `.ti1`. Its docstring
  forbids a second open-coded read. The visibility decision MUST route through
  it — the implementer's plan to call `read_target_instrument()` directly would
  re-create the exact bug this method exists to kill (a `.ti1` has no
  TARGET_INSTRUMENT → silently "not a CR30" after every project reopen).
- The chart-load path already flips CR30 behaviour per chart:
  `self._preview.set_no_swipe(self._chart_is_cr30())` at `:4514`, plus
  `_apply_cr30_pbp_lock()` / `_apply_cr30_dead_options()` called at
  `:1304-1316` and `:3378-3379`. The new checkbox's show/hide belongs on this
  same path — the hooks already fire on chart load AND settings load.
- `TiffPreview._active_patch_box` + `_active_patch_page` (`ui/tiff_preview.py:2655-2705`)
  — the #126 armed-patch accent ring (#1f8f6b over a white halo), hexagon-aware
  (`_patch_hexagon`), with small-patch stroke thinning (`RING_SMALL_PATCH_PX`)
  and whole-device-pixel halo discipline. The aiming overlay draws INSIDE this
  ring, on the same `_active_patch_box`, same paint block.
- `_make_live_preview_group` (`ui/tabs/tab_measure.py:2377`) — builds the
  view-controls group per module prefix ("g"/"m"); the QCheckBox+TooltipButton
  row pattern (`om_row`) is exactly what the new control copies.
- Physical scale IS available: `edge_spacer_px_from_sidecar` (`:458`) already
  reads `channels.json → layout.dpi` (default 300) and converts mm→image px via
  `dpi/25.4`. The 4 mm aperture is `4 * dpi / 25.4` image px, then the paint's
  own `s` scale maps to screen. No new geometry machinery needed.
- The calm-mode subtext already says the CR30 aiming instruction in words
  (`:1440`: "Rest the instrument on the highlighted patch and press its
  button."). The overlay is the graphical twin of a sentence the tab already
  speaks.

**Persistence pattern for view controls (all three existing controls follow it —
a fourth control must follow ALL FIVE hooks or it drifts):**
1. `_make_live_preview_group` attrs `_{prefix}_*` (`:2477-2479`).
2. `_apply_active_view_settings` / `_on_view_control_changed` (`:1164-1187`) —
   only the ACTIVE module's controls drive the shared preview.
3. App-settings save/load: `measure_*` keys for Guided (`:13127-13181`),
   `manual2_*` for Manual (`:13149-13221`) → survives a restart.
4. Preset save/load (`:2887-2917`).
5. Per-target store: `workflow/measure_settings.py` `MEASURE_CONTROLS`
   (`view_mode_guided`… `:64-69`) → survives a TARGET SWITCH per
   `docs/design/per_target_settings.md` §5 (binding spec — Knut: "measure tab
   must be included"). A new checkbox needs `aim_overlay_guided` /
   `aim_overlay_manual` entries here or it silently follows the user from
   target to target — the exact fault class Knut's beta.3 batch reported.
6. `_LINKED_PAIRS` (`:12564-12577`) — Knut's confirmed rule: a parameter shared
   and visible in both modules follows between them. The pair
   `("_g_aim_cr30", "_m_aim_cr30")` belongs in the tuple.

**§M question — ANSWERED (PROVEN):** `tests/test_message_catalogue.py`
enforces §M only on `WINDOW_SOURCES` (QMessageBox-style windows; `:309-325`)
plus the visible-debt list `UNCATALOGUED_MEASUREMENT_WINDOWS`. The three
existing Live-preview tooltips live as plain `tr()` strings in
`tab_measure.py`, not in `measurement_messages.CATALOGUE`. A preview tooltip
is therefore NOT §M material and needs no §M-PROPOSED cycle. What it DOES
need: `tr()` wrapping, `python scripts/i18n_extract.py --missing de` + German
strings (`tests/test_i18n.py` gates), and the checkbox label kept short.
## 2. The aperture figure — SOURCED, the overlay may draw it

**The CR30's measuring aperture is 4 mm in diameter, and the figure is PROVEN
from two independent sources:**

1. **The vendor's own specification.** CHNSpec's CR-series brochure
   (https://en.chnspec.com/uploadfiles/%E5%BD%A9%E9%A1%B5/%E8%8B%B1%E6%96%87%E5%BD%A9%E9%A1%B5/20220323094512206.pdf
   — the URL published in `~/Desktop/CR30-manufacturer-email.txt`; downloaded
   and text-extracted 2026-08-30) lists for CR10/CR20/CR30:
   `Measure Aperture: 4mm`, `Size: Diameter 33mm, Height 84mm`, weight ~75 g,
   45/0 geometry, 400–700 nm at 10 nm. **PROVEN** (I ran the extraction).
2. **An operator measurement on the real unit.** The research repo,
   `/Users/Basti/develop/chromiq-cr30-research/EXPERIMENTS.md:618` (EXP-018):
   *"Aperture 4 mm (operator, measured)."* **PROVEN** (read the file).

The code already carries the same figure: `workflow/layout_engine/instruments.py`
CR30 branch says "33 mm barrel, 4 mm circular aperture" and derives the 4.00 mm
clearance of a 12 mm patch from it. `02-design.md`'s 4.00/4.45 mm numbers are
**clearances around** the 4 mm aperture (square vs equal-area hexagon), not
aperture candidates — the implementer's worry that 4.45 might be "the other
aperture" is resolved: there is one aperture, 4 mm, and 4.45 was a hexagon
clearance figure.

**Honesty caveats the overlay text must respect (INFERENCE, flagged as such):**
- 4 mm is the *aperture* diameter per vendor spec. Whether the optically
  *sampled* spot is exactly the aperture is not established by anything we hold;
  no experiment in the research repo mapped the sensitive area. Draw and label
  it as **the instrument's 4 mm measuring aperture** (a sourced fact), never as
  "the area that is measured" (unsourced).
- The 33 mm opaque barrel is the ergonomic problem (occlusion — the user cannot
  see the patch once the instrument is on it). Drawing the 33 mm barrel to
  scale as a faint ring is *also* honest and arguably more useful, but on a
  12 mm patch it covers ~7 patches and adds noise; recommended as NOT drawn in
  v1 (owner may rule otherwise).
## 3. Task 1 — design critique

### (a) WHERE — agreed, with one correction
The Live-preview group (`_make_live_preview_group`, both prefixes) is the right
home. Correction: do not squeeze a third widget pair into `om_row`; add a
**third row** (`aim_row`), a QWidget container holding QCheckBox + spacing +
TooltipButton, and show/hide the CONTAINER. A hidden QWidget is excluded from
its layout entirely (no `retainSizeWhenHidden` set), so the group collapses
with no hole. (Qt layout semantics; verify visually during the driving run.)

### (b) VISIBILITY — right idea, wrong function
Deciding from the chart is correct — but calling
`ui.ti2_loader.read_target_instrument()` directly is exactly the bug
`_chart_is_cr30()`'s docstring forbids repeating: the tab is handed
`run.chart_ti1` on project open and `TARGET_INSTRUMENT` lives only in the
`.ti2`, so a direct read answers None → "not a CR30" after every reopen
(**PROVEN** — the docstring records the two open-coded reads that were both
wrong). Use `self._chart_is_cr30()`, refreshed from the three call sites that
already re-assert CR30 state: `set_ti1_path` (`:3378` — project open, Profile-run
/ Run-type change, every cross-tab load) and the two settings-load paths
(`:1304`, `:1315`). Add one method `_apply_cr30_aim_visibility()` called beside
`_apply_cr30_dead_options()` at those three sites.

- Chart with no instrument field → `is_cr30(None)` is False → hidden. Correct:
  the owner said "only visible when a chart is made for the cr30".
- Chart re-measured with a different physical instrument → still visible
  (the CHART was made for a CR30). Matches the owner's wording; also matches
  `_apply_cr30_pbp_lock`, which already follows the chart, not the port.
- Chart loaded before the .ti2 exists (project with .ti1 only) → hidden, and
  Start is disabled on the same condition (`:3368`), so no session can arm a
  patch anyway — consistent.
- Target switch → `set_ti1_path` fires → visibility re-evaluated; the checkbox
  VALUE comes back from that target's per-target store (§1 hook 5).

### (c) WHAT IT DRAWS — the proposal deviates from the design already agreed in #159
The implementer proposes crosshair + aperture circle. **The issue discussion the
owner is pointing at agreed something different and better** (PROVEN — issue
#159 comments, "The aiming circle (mockup above)" and "The aiming circle — how
it must be drawn", with `docs/design/mockups/cr30/aiming-circle.png`):

> Draw the instrument **body to scale** around the patch being read, so the
> user can place the device by making the ring of neighbours even. 1. To
> scale, from the chart's own dpi — an out-of-scale circle is worse than none.
> 2. Only where it means something — patch-by-patch mode, never a strip chart.
> 3. Visibly a guide — dashed and translucent, never mistakable for ink.

Ergonomics (the coordinator's steer #1, reasoned from the physical act): the
CR30 is a 33 mm opaque disc over a ~12 mm patch. **At the moment of contact the
user cannot see the patch, the aperture, or a crosshair — all three are under
the barrel.** The only cue that survives contact is the body's edge against the
ring of neighbouring patches. The 33 mm dashed circle teaches exactly that cue
in advance: "these are the patches that will vanish; centre yourself by making
what remains even." A crosshair at the patch centre helps only BEFORE contact,
duplicates what the existing #1f8f6b accent ring already gives (the target
patch is unambiguous), and paints over the one thing the preview must not
obscure — the patch colour. **Drop the crosshair.**

The **4 mm aperture circle** earns its place for a different reason, raised by
the owner's no-guard ruling: with no layout-time refusal, the overlay is the
only place a too-small patch ever becomes visible. Draw it as a second, small
dashed circle concentric with the body circle. When the patch is smaller than
4 mm the circle honestly overflows the patch — no invented warning text, the
geometry itself is the statement (truthful, not reassuring). Both figures are
sourced (§2); keep them as named constants next to the CR30 branch in
`workflow/layout_engine/instruments.py` ("a property of the instrument
definition, not a constant in the drawing code" — issue #159), e.g.
`CR30_BODY_DIAMETER_MM = 33.0`, `CR30_APERTURE_DIAMETER_MM = 4.0`, each with
its source in the comment.

Scale: the tab computes `px_per_mm = dpi / 25.4` from `channels.json →
layout.dpi` (the same read `edge_spacer_px_from_sidecar` already does) and
passes image-px radii to the preview. **If no dpi can be read, draw nothing**
(issue rule 1: out-of-scale is worse than none) — the checkbox stays visible
but the overlay stays silent; this is the honest fallback for a .ti2 whose
sidecars are gone.

Drawing rules carried over from the issue (they were written for this exact
feature): dashed with the white casing on BOTH sides of each dash (two
concentric centred strokes, halo first), even pen widths on whole-pixel
coordinates. One Qt trap to flag for implementation: **QPen dash patterns are
specified in units of the pen width**, so the wide halo stroke and the narrow
accent stroke need their patterns scaled (and dash offsets matched) or the
dashes will not nest — set `setDashPattern` per pen with widths compensated.

### (d) WHEN — armed patch only, v1
Draw only when `_active_patch_box` is set and `_active_patch_page ==
_current` — the same guard the accent ring uses. That means: only while a
patch-by-patch session is live and a patch is armed, which for a CR30 chart is
every session (pbp is locked on). Reviewing a chart with no session shows
nothing — correct, because the overlay's meaning is "place the device HERE
now". Following the hover patch as well is tempting (preview clearance before
clicking) but puts two large dashed circles on screen at once; defer, and note
it as an option for the owner. The issue also suggested the same circle in
Create Chart's preview ("will I be able to aim at this?" before printing) —
out of the owner's current ask, listed as follow-up.

### (e) WHAT IT MUST NOT DO — measured against the existing paint
- Obscure patch colour: the body circle lies entirely OUTSIDE the armed patch
  (Ø33 mm vs 12 mm patch), dashes translucent; the aperture circle covers a
  thin Ø4 mm dashed line, suppressed below a small-pixel threshold (§4 case 9).
- Fight the rings: paint order in `paintEvent` becomes fills → seams →
  warn-ring second pass → **aiming overlay** → accent ring → hover outline, so
  the accent ring stays on top of the body circle where they cross; the warn
  red (#ff2b2b) and accent (#1f8f6b) colours are untouched. Use the accent
  green family for the dashes (as the mockup does) so the overlay reads as
  "part of the same instruction" as the ring.
- Paint cost: one O(1) overlay per paint (two dashed ellipses), independent of
  patch count — versus the existing per-patch fill loop. Nothing per-patch is
  added. (INFERENCE from the paint code structure; no profiling run.)
## 4. Task 1 — edge-case table

1. **No chart loaded** — `_chart_is_cr30()` returns False (guarded `chart is
   None` path, PROVEN `:5537-5541`) → row hidden, nothing drawn.
2. **Chart with no TARGET_INSTRUMENT** — `read_target_instrument` → None →
   `is_cr30(None)` False → hidden. Correct per the owner's wording.
3. **Non-CR30 chart** — hidden. The checkbox value is still stored per target,
   so a CR30 target keeps its choice while a strip target never shows the row.
4. **Rectangular vs hexagonal CR30 chart** — identical: both circles centre on
   the armed box's centre; the recorded boxes already carry the hex stagger
   (PROVEN — `_apply_hex_stagger` docstring, `:492+`: boxes hold the drawn
   position since 2026-08-13). The accent ring stays shape-aware; the circles
   are shape-independent by design.
5. **1144-patch sheet** — overlay cost is O(1) (§3e). The body circle spans
   ~2.75 patch widths; dashes keep neighbours legible.
6. **Multi-page charts** — guard `_active_patch_page == self._current`, the
   accent ring's own guard (PROVEN `:2655`). Page without the armed patch
   draws nothing.
7. **"Show only measured patches" ON** — the armed patch is by definition
   unmeasured → blanked white with a thin outline; neighbours mostly white too.
   The circle still lands correctly (geometry is independent of fill mode) but
   the "even ring of neighbours" cue is weaker on white. Acceptable; no special
   case. Worth one line in the tooltip? No — tooltip stays outcome-focused.
8. **Patch smaller than the aperture** — the guard question is SETTLED by the
   owner (deferred; Argyll parity; recorded in 35_beta2_backlog.md, commit
   b286270d). The overlay draws the 4 mm circle overflowing the patch — the
   geometry states the problem truthfully without inventing new warning text
   (which would need owner approval). `preflight.MIN_PATCH_MM`'s 6 mm warning
   still applies at layout time as for every instrument (PROVEN —
   instruments.py CR30 comment block).
9. **Zoomed-out preview / tiny patches** — when Ø4 mm maps below ~8 device px,
   a dashed circle degenerates to noise: suppress the aperture circle below a
   threshold (mirror `RING_SMALL_PATCH_PX` practice, PROVEN the precedent
   exists `:2692`). The body circle (8.25× larger) survives all realistic zooms.
10. **High-DPI** — even pen widths, whole-pixel snapping, centred pens; the
    dash-pattern-in-pen-width-units trap (§3c). The existing ring's halo
    history (`:2676-2688` comment) is the cautionary precedent.
11. **No dpi available** (channels.json missing/unreadable; strips.json-only
    geometry) — draw nothing rather than guess a scale (issue rule 1). Silent,
    logged at debug.
12. **Chart re-measured with a different instrument** — row stays visible
    (chart-derived, §3b); if the user reads a CR30 chart with an i1Pro in
    strip mode there is no armed patch, so nothing draws — self-consistent.
13. **Target switch mid-view** — `set_ti1_path` re-evaluates visibility; the
    per-target store restores the checkbox value for the new target; the
    linked-pair mirror stands down during restore (`_suspend_linking`, PROVEN
    `:12596-12605`).
14. **Restart** — app-settings keys (hook 3, §1) restore the checkbox; chart
    reload re-evaluates visibility.
## 5. Task 1 — tooltip draft, label, §M

§M: **not required** for a tooltip (PROVEN, §1). It IS new user-facing text, so:
`tr()` + `scripts/i18n_extract.py --missing de` + German before the gate.

Checkbox label (short, count-free): `Show aiming help`
(visible only beside CR30 charts, so the label needs no "CR30" — but if the
owner prefers self-naming: `Show CR30 aiming help`.)

TooltipButton title: `Aiming help for your CR30`

Body draft (plain language, outcome + prerequisite, no jargon, no history):

    Turn this on and the preview draws a dashed circle around the patch you
    are asked to read next. The circle is your CR30's own footprint — the
    33 mm body of the instrument, drawn at the same scale as the chart.

    Why so big? The instrument is much wider than a patch: the moment you
    lower it, its body hides the patch you are aiming at. The circle shows
    you beforehand which neighbouring patches will disappear under it. Line
    the instrument up so the patches around it stay evenly visible on all
    sides, and the small reading window in the middle lands on the right
    patch.

    The small inner circle is that reading window — the 4 mm opening the
    CR30 actually measures through. There is comfortable room around it on a
    normal patch. If it ever pokes past the edges of the patch, the patches
    on this chart are too small for the CR30 to hit reliably — better to
    know that here than after a sheet of readings.

    The circles appear while a measurement is running, on the patch ChromIQ
    highlights for you. They are only a guide on the preview — they change
    nothing about your chart or your readings.

(4 paragraphs — extensive but each earns its place: what, why, the honest
too-small case, and the do-no-harm reassurance every neighbouring tooltip
ends with. The 33/4 mm figures are the sourced ones from §2.)
## 6. Task 2 — real-app flag-ring proof — DONE, fix confirmed at real scale

Produced with `scripts/drive_46_aiming_overlay_report.py` phases B+D on the
working tree (fix present) and on a git worktree at `6428fd2c^` (fix absent,
tag `before_`), each in its own sandbox. Output: `~/Desktop/cr30-flag-ring-proof-real/`
with a README saying exactly how each image was made. All **PROVEN** (I ran it
and LOOKED at the images):

- Real 432-patch hexagonal CR30 chart, built by the app itself (Manual, CR30,
  hex, area-first, A4); real Measure tab; flags produced by the tab's own
  `_on_strip_measured` ΔE-threshold + Tukey-fence logic on events whose
  expected colours are sampled from the chart's own TIFF. Only the instrument
  readings are synthetic (the CR30 was not touched, per the constraints).
- Flagged C8, I5+I6 (vertically adjacent — the fault geometry), N8.
- BEFORE (`before_D4_closeup_adjacent_pair.png`): I5's ring is visibly eaten
  along the edge it shares with I6 (fill painted after the ring); I6's
  upper-left edge shows casing with the red missing.
- AFTER (`D4_closeup_adjacent_pair.png`): both adjacent flagged hexagons carry
  complete rings, white casing on all six edges.
- Weight judgement at real scale: correct — legible without smothering patch
  colour; the white casing carries a red ring on a red patch (C8). Ring width
  `max(1.8, s*2.2)` thins with density; nothing too heavy/thin at 432. A
  1144-patch check is one driver run away if the owner wants his exact sheet.
- One driver defect worth noting honestly: the in-app `_apply_zoom` close-up
  did not take effect in the grabs (both D3 images are fit-to-window); the
  close-ups were made by cropping the full-resolution grabs instead. The
  evidence is unaffected.
- The real plist was backed up and verified byte-identical after all runs
  (shasum 8a64d9f6…, **PROVEN**). The worktree was removed.
## 7. Task 3a — margins-are-law: the fix, quantified on screen

**The fault, re-proven in the current tree** (phase B): set 1/6/2/1 mm, CR30
hex area-first A4 → measured left **8.47 mm**; 432 patches at 12.11 mm.
**The identical fault from the FROM PROFILE GAMUT module** (phase E, Demo-Full-RGB
with run2's real profile, Verification run type): measured left **8.55 mm** —
same path, same rlwi. **PROVEN**, screenshots in `~/Desktop/cr30-layout-controls/`.

**The coordinator's three gamut checks, all PROVEN on screen:**
1. `tab._manual_layout_panel` is the SAME `LayoutOptionsPanel` object in gamut
   mode (`is`-identity True; a 3.7 mm sentinel margin typed in Manual read back
   in the gamut module).
2. The margins-are-law path is reached identically (8.55 vs 8.47 mm — the
   0.08 mm difference is patch-size quantisation from a different patch count,
   not a different path; both go through `geometry.compute`/`placement`).
3. Gamut screenshots produced (E1, E2).
   Nothing in `_switch_mode`'s gamut branch pins instrument/margins/layout mode
   (instrument read back "CR30", mode "area_first" after the switch — PROVEN).

**The fix, specified** (matches Knut's own law-mode label rule at
`geometry.py:274-285`, and his beta-13 clip-inside-margin model, commit
`2d2656bb`):

1. `workflow/layout_engine/geometry.py::compute` — line 125: exclude `g.rlwi`
   from `avail_w` when `g.margins_are_law`.
2. `workflow/layout_engine/geometry.py::placement` — line 257 (avail_w) and
   line 294 (`x0=g.margin_l + g.rlwi + …`): same condition, drop `rlwi`.
3. `workflow/layout_engine/raster.py` needs NO position change: the row
   numbers are already right-aligned ending at `x0 − gap` and grow LEFT
   (`:1218-1236`), so with the new `x0` they land inside the left margin
   automatically. **But see the on-screen result below — a guard is needed.**
4. `ui/tabs/tab_chart.py::_engine_text_overflow_warnings` (`:16358`) — add the
   mirrored warning: for an instrument with `rlwi > 0` in area-first, when
   `margin_l + 0.05 < <needed>`, append "⚠ Left margin is too small for the
   row numbers — they overflow toward the page edge." `<needed>` should be the
   real text need: widest row number width + 1 mm gap + hex ¼-width
   protrusion, computable from the geometry (a conservative `rlwi` (7.5) is
   the cheap approximation and matches what the default mode reserves).
   **A second fault found here, PROVEN by reading the guard:** this method
   returns [] unless the MANUAL button is checked — so in FROM PROFILE GAMUT
   mode the existing top/bottom overflow warnings never show either. The
   owner's "gamut too" ruling makes this guard wrong; it must accept
   `mode in ("manual", "gamut")`.
5. `workflow/margin_inspector` / `realized_margins_mm` — no change; they follow
   `placement` (verified: the fixed build measures left 1.02 mm through the
   app's own `measure_from_engine`).
6. Tests that pin law-mode SS/CR30 layouts will move:
   `tests/test_layout_instrument_margins.py`, `tests/test_layout_geometry.py`,
   plus any golden capacity counts for SS/CR30 area-first (find by running the
   gate — the owner has waived printtarg parity for Manual AND gamut, so these
   are updates, not regressions). Instruments with `rlwi = 0` (i1/CM/i1Pro3)
   are untouched by construction.

**Quantified on screen (phase B vs C, PROVEN):**

| | today | with the fix |
|---|---|---|
| measured left (set 1 mm) | 8.47 mm | **1.02 mm** |
| patches (A4 hex) | 432 | **432 — unchanged** |
| patch size | 12.11 mm | 12.02 mm |
| measured right (set 2 mm) | 1.97 mm | **9.51 mm** |
| row numbers | in their own band | **GONE — off the page** |

Two consequences the naive geometry-only fix exposes, both needing a ruling:

- **The row numbers vanish at a 1 mm margin** (`3a_C3_left_edge_FIX.png`):
  right-aligned at `x0 − protrusion − gap`, a hex chart's ¼-width protrusion
  (~3 mm) plus the gap already exceeds 1 mm, so PIL clips the text entirely.
  Losing the 2-D coordinate system silently is unacceptable for the CR30 —
  "finding one patch among several hundred, by hand, is the CR30's entire
  ergonomic problem". Options: (i) clamp the number's left edge at the page
  edge — partially over the protruding hexagons on even rows, ugly but present,
  matching the top-label "slide toward the edge, clamped" precedent, plus the
  warning; (ii) let them clip (today's naive result) plus the warning;
  (iii) drop them below a threshold and say so. I recommend (i) for
  consistency with Knut's top-label rule, with the §7.4 warning in all cases.
- **The freed 7.5 mm lands as right-side whitespace** in the default
  "by patch width" method (a new hex column needs ~12 mm), because area-first
  left-anchors the block (`center-left`) and HIDES the alignment control.
  With the "columns × rows" method the patches widen instead (report 45:
  +4% on the owner's 26×44). Default = change nothing (left-anchored,
  predictable left margin); if the owner dislikes the big right gap, the
  patch-area-alignment row could be un-hidden in area-first law mode — his call.

**What "Measured from Preview" should SAY** (report 45 change 2, no ruling
needed, now sharpened by the fix): label the numbers "Left (to first patch)" /
"Top (to first patch)"; under each side that carries a furniture band in the
CURRENT mode add an indented line ("row-number band 7.5 mm — inside the page
margin in this mode" for law mode after the fix / "…between the margin and the
patches, printtarg-style" in the default mode); and one info-card sentence
saying which mode puts bands where. After the fix, law mode's left number will
simply agree with the box, which is the best display fix of all.
## 8. Task 3b — the sizing boxes: recommendation re-verified, and shown

Re-verified against the current tree and driven on screen (phases A and F,
screenshots + README in `~/Desktop/cr30-layout-controls/`, all **PROVEN**):

- Patch-first with Expert collapsed: NO sizing control visible anywhere
  (`3b_A1`); area-first shows its sizing fields in Basic → Layout (`3b_A3b`).
  The asymmetry is exactly as report 44 recorded.
- `3b_A2c_expert_patch_rows_BEFORE_crop.png`: Patch size (mm) / Patch scale
  inside Expert Options → Patches & spacers.
- `3b_F1b/F1c` — report 44's exact proposal MOCKED AT RUNTIME (widgets
  re-parented into the Layout grid in the live app; the source untouched): the
  two rows sit under "Create layout", reading naturally as the patch-first
  siblings of area-first's fields. The Expert group keeps the spacer rows.
- The gamut module shows the same panel instance (phase E), so the move
  reaches FROM PROFILE GAMUT with zero extra work — the owner's addendum is
  satisfied by construction, and now also by demonstration.
- I re-affirm report 44's items 1-5 including the `pscale`/`sscale` = 1.0
  initialisation and the two help-bullet rewordings, with one addition: the
  moved rows' visibility must key on `layout_mode` exactly as
  `_sync_layout_mode` already flags them in `_patch_first_rows` — the mock
  confirmed no layout jump or hole when the rows show/hide.
- Disagreements with report 44: none of substance. One nuance: it proposed the
  container "at the same grid position family as `_area_fields_w` (row 1)" —
  in the live mock, row 2 under "Create layout" (after the size rows'
  natural order Patch size → Patch scale → Patch shape) read better; final
  row order is cosmetic and the implementer's choice.
## 9. Verdict, implementation plan, open questions, rating

### Task 1 verdict: BUILD, WITH NAMED CHANGES
Build the option — but draw what issue #159 already agreed, not the proposed
crosshair: a dashed, translucent, to-scale **33 mm body circle** (the cue that
survives contact) plus the **4 mm aperture circle** (the honest too-small-patch
signal, now the only aiming aid there will be, per the owner's no-guard
ruling). Both figures are sourced (§2). Drop the crosshair. Decide CR30-ness
via `_chart_is_cr30()`, never a fresh `read_target_instrument()` call.

### The end-to-end journey (beginner, first time)
1. User builds/loads a chart made for the CR30; opens Measure. In the Live
   preview group a new row has appeared (it simply isn't there for other
   charts): `[x] Show aiming help  (?)`. Recommended default: ON for CR30
   charts (it is the point of the feature and a beginner will not discover an
   unchecked box) — owner's call, Q1 below.
2. Hovering the (?) gives the §5 tooltip.
3. User presses Start; the engine arms patch A1; the preview shows the accent
   ring (as today) with the dashed body circle around it and the small
   aperture circle at its centre. As each patch is armed the circles follow.
4. Unticking hides the circles instantly (only the preview changes). The value
   persists: app restart (AppSettings keys), target switch (per-target store),
   presets, and Guided/Manual mirroring via `_LINKED_PAIRS`.
5. Loading a non-CR30 chart hides the row entirely; the stored value is
   untouched (disable/hide, never untick — the tab's own rule).

### Module map (reuse vs new)
| Piece | Where | Status |
|---|---|---|
| `CR30_BODY_DIAMETER_MM = 33.0`, `CR30_APERTURE_DIAMETER_MM = 4.0` | `workflow/layout_engine/instruments.py` (CR30 block), source comments | NEW (2 constants) |
| checkbox + TooltipButton row, per prefix | `_make_live_preview_group`, `ui/tabs/tab_measure.py:2377` | NEW row, existing pattern |
| `_apply_cr30_aim_visibility()` | beside `_apply_cr30_dead_options()`; called from `:1304`, `:1315`, `:3378` | NEW (small) |
| push-to-preview | `_apply_active_view_settings` / `_on_view_control_changed` | EXTEND |
| mm→px scale | reuse `channels.json → layout.dpi` read (as `edge_spacer_px_from_sidecar`) | REUSE |
| `TiffPreview.set_aim_overlay(enabled, aperture_px, body_px)` + paint block after warn rings, before the accent ring | `ui/tiff_preview.py` (~2650) | NEW (~40 lines) |
| settings keys `measure_aim_help` / `manual2_aim_help` | `:13127/:13149` save, `:13177/:13221` load | EXTEND |
| preset dict `aim_help` | `:2887/:2913` | EXTEND |
| per-target store `aim_help_guided/_manual` | `workflow/measure_settings.py::MEASURE_CONTROLS` | EXTEND |
| linked pair `("_g_aim_cr30","_m_aim_cr30")` | `_LINKED_PAIRS:12564` | EXTEND |
| i18n | `tr()` + `scripts/i18n_extract.py --missing de` + German | REQUIRED |
| tests | visibility per chart type; persistence round-trip; draw-only-when-armed; no-dpi silence; per-target vocabulary test extension | NEW |

### Implementation plan (numbered, for the implementer)
1. Add the two sourced constants to `instruments.py` with the §2 citations.
2. `TiffPreview`: `set_aim_overlay(enabled: bool, aperture_px: float, body_px: float)`
   (image-px radii; ≤0 = unknown scale = draw nothing) + the paint block:
   two concentric dashed circles centred on `_active_patch_box`'s centre,
   guarded by `_active_patch_box is not None and _active_patch_page == _current`;
   halo-then-accent, even widths, whole-pixel snap, dash patterns compensated
   for pen width; suppress the aperture circle when its screen diameter < ~8 px.
3. Measure tab: build the row (both prefixes), wire visibility
   (`_apply_cr30_aim_visibility` at the three call sites), push state in
   `_apply_active_view_settings`, compute radii from the chart's dpi when the
   chart changes (`_try_load_tiffs` path, beside `set_no_swipe`).
4. Persistence: the five hooks (§1) + `_LINKED_PAIRS`.
5. Tooltip + label from §5 (owner may adjust wording); i18n extraction + de.
6. Tests as per the module map; extend the measure-settings drift test data.
7. Manual on-screen check with a CR30 chart (rect + hex), then the gate.

Separately (Task 3a, after the owner's rulings): the §7 fix list.
Separately (Task 3b): report 44 items 1-5 — pre-approved shape, shown in F1b.

### Open questions needing the owner's ruling
1. Aiming help default ON for CR30 charts, or OFF like the other view toggles?
2. Draw the aperture circle always, or only the body circle (aperture only
   when it does NOT fit, as an alarm)? (My recommendation: draw both always —
   a constant honest picture beats an appearing/disappearing alarm.)
3. Task 3a: row numbers at a too-small left margin — clamp at the page edge
   (my recommendation, mirrors the top-label rule), clip, or drop-with-warning?
4. Task 3a: accept the right-side whitespace in "by patch width" law mode
   (default: yes, change nothing), or expose patch-area alignment there?
5. Task 3b: confirm the move (report 44's ruling request stands; the F1b mock
   is the picture to judge).
6. Follow-ups filed, not asked: hover-follow for the circle; the same circle in
   Create Chart's preview (issue #159 suggested it — "will I be able to aim at
   this?" before printing).

### Rating of the proposed design (as submitted to me): 6/10
What earns points: the placement (right row, right pattern), chart-derived
visibility (right source), reusing the armed-patch machinery, worrying about
paint cost and honesty, and asking for the aperture figure instead of assuming
it. What costs points: (a) the crosshair + aperture-only drawing misses the
design already agreed and mocked in issue #159 — the body circle is the part
that actually solves the hand-aiming problem, and the deviation was
unexplained; (b) `read_target_instrument()` called directly would have
reintroduced the exact reopen bug `_chart_is_cr30()` documents — in an app
where that method's docstring says "never add a second open-coded read";
(c) the persistence surface (five hooks + linked pairs + per-target
vocabulary) was unmentioned, and missing any one of them is a Knut-grade
report; (d) "only while a session is live" was stated as an assumption rather
than derived from the armed-patch guard that already encodes it. With the
named changes the feature is small, honest, and almost entirely assembled
from parts the app already trusts.

**PROVEN/INFERENCE ledger for this report:** §1 all PROVEN (files read at the
cited lines); §2 PROVEN (brochure downloaded + extracted; research repo read);
§3-5 design reasoning INFERENCE from those facts (marked inline); §6 PROVEN
(driven, images inspected); §7 numbers PROVEN (driven), fix locations PROVEN
(code read), test-impact list INFERENCE until the gate is run; §8 PROVEN
(driven + mocked on screen).
