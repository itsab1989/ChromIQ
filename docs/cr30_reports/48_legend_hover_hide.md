# 48 — Legend chip hover-to-hide: design critique

**Status: COMPLETE.**
Request (Basti): the expected/measured legend chip sometimes sits over the
patches; make it disappear when the mouse hovers over it.

## Sections (filled in as established)
- [x] 1. Verification of the two prior claims (placement design; empty `_stripe_rects` fault)
- [x] 2. Q1 Coordinate space — who gets the events, whose coords is the chip in
- [x] 3. Q2 The disappearing-target problem / hysteresis
- [x] 4. Q3 Interaction with hover tile, click-to-jump, strip frame, arrow band
- [x] 5. Q4 No-pointer users, focus loss
- [x] 6. Q5 Alternatives to hover-to-hide
- [x] 7. Q6 "Don't show again" precedent
- [x] 8. Q7 Edge cases, numbered
- [x] 9. Q8 Tests + vacuity guard
- [x] 10. On-screen verification
- [x] 11. Verdict, module map, plan, open questions, rating


---
## 1. Verification of the two prior claims

### 1a. Chip placement design — CONFIRMED (code, ui/tiff_preview.py:2862-2918)
The chip is drawn inside `_draw_cq_overlay`, guarded by `items and self._pixmap
is not None` where `items = self._patch_overlay.get(self._current, [])` — so it
appears only on a page with at least one split-patch result. Placement:
bottom-margin-first (`patch_bottom` from `_stripe_rects` + `_edge_spacer_px`),
dodges the bidirectional arrow band (`- 25 if self._bidirectional`), clamps to
paper width and paper height. The comment at :2907-2914 concedes resting on the
last row is the accepted lesser evil (Sebastian, 2026-08-13). So "sometimes
over the patches" is a KNOWN accepted fallback, and hover-to-hide is a remedy
for an accepted state, not a placement bug. CONFIRMED as described in the brief.

### 1b. Empty `_stripe_rects` → chip at TOP — code CONFIRMED, but the F1
### screenshot is a DRIVER ARTEFACT, and there is a THIRD fault nobody asked about
- Code: with `_stripe_rects == []`, `patch_bottom` stays `oy` (:2883-2885),
  `cy = min(floor, oy+6)` then `max(oy, ...)` → chip lands at the top edge of
  the sheet, over row 1 and the column letters. CONFIRMED by reading :2883-2915.
- BUT `scripts/drive_47_aiming_overlay_verify.py:724,735` arms a bare
  `TiffPreview` with `load_tiff()` + `set_patch_overlay(...)` and NEVER calls
  `set_stripe_rects` — the real Measure tab always runs `_setup_stripe_rects()`
  right after `load_tiff` (tab_measure.py:4570). So F1_scene_parent_commit.png
  showing the chip at the top is (at least partly) the DRIVER's doing.
- Real-journey reachability: `_setup_stripe_rects` (tab_measure.py:4588-4676)
  can fall through all three strategies (engine channels.json → ti2
  PASSES_IN_STRIPS2 + uniform image detection → legacy label detection) and end
  WITHOUT calling `set_stripe_rects` at all. Whether patch-overlay items can
  coexist with that fall-through is checked below (they need patch boxes from
  the sidecar, which correlates with the engine path succeeding).

### 1c. NEW FAULT FOUND WHILE VERIFYING: `TiffPreview.clear()` does not clear
### `_patch_overlay`
`clear()` (:1779-1795) resets `_patch_info = {}` but never touches
`self._patch_overlay` — and `load_tiff()` (:730-767) resets `_stripe_rects`
but not `_patch_overlay` either (by DESIGN for reload-same-chart: the tab owns
clearing via `clear_patch_overlay()`, called at tab_measure.py:11465 (session
map) and :12625 (`_clear_overlay`, #134)). Whether any journey loads a NEW
chart without passing those call sites — leaving chart A's splits painted at
chart A's coordinates over chart B, plus the legend chip pinned to the top
because `_stripe_rects` was reset — needs the `_discard_stale_overlay` (#131)
path checked. See §1d.

### 1d. On-screen probe results (real `TiffPreview`, visible window, dpr 2.0)
Probe: `scripts/probe_48_legend_placement.py` (pattern of drive_47: no settings touched —
`TiffPreview` imports no `AppSettings` (grep: zero hits) — plist sha256
byte-compared before/after: UNCHANGED). Screenshots in
`~/Desktop/cr30-legend-hover/`.

| case | state | chip found at |
|---|---|---|
| P1 | stripe rects + overlay | rows 912–959 of 992 (centre 0.94) — bottom margin, as designed |
| P2 | `set_stripe_rects([])` | rows 12–59 (centre 0.04) — TOP of sheet. **Fault 2 CONFIRMED in the real widget.** |
| P3 | three `_overlay_mode` wordings | x-extents both=699 / expected=703 / **measured=1191** device px — widths differ, "measured" is ~70% wider |
| P4 | patches to 8 px of paper bottom | centre 0.97 — resting ON the last row (the accepted fallback, reproduced) |
| P6 | `clear()` then `load_tiff(new chart)` | `_patch_overlay` SURVIVES clear(); stale splits + chip at TOP drawn over the new chart |
| P7 | pane 280 px wide | chip WIDER than the paper: `cx` clamps only the LEFT edge, chip overflows the right paper edge onto the dark surround and its text is CLIPPED mid-word ("…colours ap") |

**Probe honesty note:** the first run scored a false PASS-shaped failure —
`set_stripe_rects` does NOT schedule a repaint (:1712-1734 sets state only),
so case 2 was scanning the stale case-1 canvas (identical fractions 0.9430 =
broken probe, not a finding). Fixed by forcing `_repaint_label()` after each
state change. In the app every caller follows with calls that repaint, so this
is a probe trap, not an app bug.

### 1e. Which REAL journeys reach fault 2 (empty rects + overlay items)
The chip needs overlay items; items need patch boxes
(`patch_boxes_from_sidecar`, tab_measure.py:406 — `<stem>.strips.json` OR
`channels.json layout.patches`). Strip rects need `channels.json
layout.strips` (`engine_strip_rects_from_sidecar`, :542) or image detection.
So the divergence is real but narrow:
1. **Page-count mismatch**: `engine_strip_rects_from_sidecar` is all-or-nothing
   (`if any(not p for p in per_page): return None`, :596-597) while
   `patch_boxes_from_sidecar` tolerates partial pages. A TIFF glob that picks
   up extra pages (the stem-widening hazard documented at tab_measure.py:4560:
   `"X-w10.0mm"` stem globbing any chart sharing the prefix) or a sidecar
   missing a page ⇒ rects None, boxes present. Then ti2-counts vs page-count
   also mismatches, and legacy label detection (`_detect_stripe_rects`) may
   fail on label-less charts ⇒ fall-through with NO `set_stripe_rects` call.
2. **`.strips.json` present without a usable `channels.json`** (import path:
   `workflow/chart_import.py` copies both as loose sidecars; only engine
   builds fold strips into channels — chart_creator.py:1365-1380).
3. **The `clear()` leak (1c/P6)**: any journey through `TiffPreview.clear()`
   that skips the tab's `clear_patch_overlay()` (tab_measure.py:11465 session
   map / :12625 `_clear_overlay`, guarded by `_discard_stale_overlay`'s
   chart-identity check AND its `if self._runner.is_running: return`).
4. Basti's F1 screenshot itself came from `drive_47_aiming_overlay_verify.py:724,735`
   — bare `load_tiff` + `set_patch_overlay`, never `set_stripe_rects`: a
   DRIVER artefact. The real Measure tab always runs `_setup_stripe_rects`
   (tab_measure.py:4570) — fault 2 on screen for a user needs journey 1–3.

**Verdict on fault 2: real code fault, narrow real-world reachability, and the
F1 evidence for it is tainted.** It should be fixed because it is one line and
the fix also serves the chip's PURPOSE (see §6), but it does not outrank the
hover request. It also interacts with hover-to-hide: the chip at the top sits
over the pointer's natural travel path, so hover-hide alone already mitigates
it for the user who meets it.

---
## 2. Q1 — Coordinate space (PROVEN, probe case 5)
- There is NO scroll area: `_build_ui` puts `_img_label` straight into the
  layout (:1880); interactive mode pans by repainting inside the label. The
  brief's viewport-offset worry is moot, but a DIFFERENT offset is real:
- Mouse moves land on **`TiffPreview.mouseMoveEvent`** (events over the child
  QLabel propagate up: probe recorded 2 hits via `QTest.mouseMove(label)` and
  1 via `sendEvent(label)`), with positions in **TiffPreview widget coords**.
- The chip is drawn in **canvas coords** (`_draw_cq_overlay` gets `s, ox=B,
  oy=B` in `_repaint_label`), while hit-testing needs **label coords**; the
  canvas is centred inside the label (AlignCenter). Measured offset
  widget→label: (0, **25**) in the probe window — a naive
  `rect.contains(event.pos())` is wrong by ≥25 px vertically plus the
  centring delta, exactly as the brief feared.
- The clean bridge already exists: `_paint_geom` (:2273-2276) is stored in
  LABEL coords in `_repaint_label` (`(s, (lw-cw)/2+B, (lh-ch)/2+B)`) and in
  canvas==label coords in `_repaint_interactive` (:3163, canvas fills the
  viewport, delta 0). So: record the chip rect with the ox/oy the overlay was
  CALLED with, then translate by `(_paint_geom.ox - call_ox, _paint_geom.oy -
  call_oy)` to get the label-space rect; hit-test with
  `self._img_label.mapFrom(self, event.position().toPoint())` — the exact
  pattern `_stripe_at` (:1677-1690) already uses.
- Interactive mode is used ONLY by the soft-proof dialog
  (ui/dialogs/softproof_dialog.py:472), which never calls
  `set_patch_overlay` — the chip is in practice a `_repaint_label`-only
  feature, but the translation above is correct in both modes anyway.

## 3. Q2 — Disappearing target / oscillation (analytical, from the paint model)
The chip is not a widget; it is baked into the label's pixmap
(`_img_label.setPixmap(canvas)`, :2337). Hiding it = repainting without it.
Consequences:
- **The design AS WRITTEN oscillates** if the rect is recorded only when the
  chip is DRAWN: hide → next paint records nothing → next move sees "not in
  (no) rect" → draws → records → hides → … a flicker at every second repaint.
- **Fix: compute and store the placement UNCONDITIONALLY** every paint
  (`cx, cy, tw, th` math :2873-2915 runs regardless), then decide drawing from
  the stored pointer position. The rect does not depend on the pointer (only
  on `_stripe_rects`, `_edge_spacer_px`, scale, wording), so
  hide/show cannot move it ⇒ no oscillation, no hysteresis needed. Boundary
  jitter is the same class as every hover UI in this file (strip hover
  repaints on boundary crossing already, :3212-3221, "a full repaint is
  ~3 ms").
- **State to store** (exact):
  - `self._legend_rect: QRect | None` — label-space chip rect, recomputed
    every `_draw_cq_overlay`, `None` when `items` empty / no pixmap.
  - `self._legend_pointer: QPoint | None` — last move position in WIDGET
    coords, set at the TOP of `mouseMoveEvent` (BEFORE the `self._panning`
    early return, :3189-3197), cleared in `leaveEvent`.
  - Hidden-ness is DERIVED at paint time (`rect contains mapFrom(pointer)`),
    never cached — so any repaint from any cause stays consistent.
  - In `mouseMoveEvent`/`leaveEvent`: repaint only when the containment VERDICT
    changes (compare against the last verdict, one bool
    `self._legend_hidden`), so parked-pointer moves inside the rect cost
    nothing.
- First-appearance case: pointer already parked where the chip WOULD appear
  when the first strip finishes ⇒ chip simply never draws there until the
  pointer moves off. Correct by construction (containment is evaluated at
  paint, not on enter).

## 4. Q3 — Interaction with the other occupants (all from code)
- **Patch hover tile** (`_PatchInfoTile`): sets
  `WA_TransparentForMouseEvents` (:322) — it can never block the moves that
  drive hide/show. When the chip hides over a measured patch and "Show patch
  values on hover" is on, the tile appears offset +18/+18 from the pointer
  (flipping near edges, :1455-1462) — NOT over the vacated spot — and shows
  exactly the numbers the user was peeking at. **Better experience, not
  worse.** Note the tile ALREADY appears when hovering the chip today (hit
  test is geometric, chip is only paint), on top of the chip.
- **Click-to-jump hover outline**: drawn BEFORE the chip in
  `_draw_cq_overlay` (:2818-2860 vs :2862+), i.e. today the chip paints OVER
  the outline of a patch beneath it. Hiding the chip reveals the outline —
  an improvement, and clicking through the chip already worked (paint-only).
- **Strip hover frame**: same paint order, same improvement. Its repaint
  triggers (:3212-3221) already do full immediate repaints on boundary
  crossings; the chip's containment verdict is recomputed in each — consistent.
- **Scan arrow band**: chip placement already dodges it (`- 25 if
  self._bidirectional`, :2904); hiding changes nothing.
- **`_CursorOverlay` (#29 readout)**: `WA_TransparentForMouseEvents` (:259) —
  no interference; it is drawn on its own overlay widget, not the canvas, so
  it stays visible over the vacated area (harmless).
- **`_show_only_measured` blanking**: independent paint layer, no coupling.
- **Nothing else reads `_legend_*`** — additive state, no existing test can be
  invalidated by adding it.

## 5. Q4 — No pointer / focus loss
- Keyboard-only: chip never hides — today's behaviour, unchanged. (They also
  cannot peek beneath; if that matters a "hide legend" control is the answer —
  §6. Not blocking.)
- Stuck-hidden risk: hidden-ness is derived per-paint from
  `self._legend_pointer`, which only survives while the pointer is genuinely
  inside the widget. `leaveEvent` (:3249, exists) clears it → chip restored.
  Focus loss WITHOUT pointer movement: the pointer is still physically over
  the chip's spot, so staying hidden is semantically right; when the window is
  covered/deactivated Qt's Leave delivery is platform-dependent (not proven
  here) — belt-and-braces: also clear in `hideEvent` (new, 3 lines) so a
  hidden tab never keeps stale pointer state.
- Touch (Windows VM): a tap synthesizes a move; after release no Leave comes
  until the next interaction, so a tap ON the chip could keep it hidden until
  the next tap elsewhere. macOS ChromIQ has no touchscreen; accepted, noted.

## 6. Q5 — Is hover-to-hide the best answer?
It is the RIGHT ship (asked for, minimal, additive). Honest alternatives:
1. **Reserve a band OUTSIDE the sheet** — precedent exists and is proven:
   `_pending_caption_band()` (:3044) reserves `cap_h` before scaling and makes
   the canvas taller (:2237-2262), drawing the helper-marker caption BELOW the
   paper. The legend could live there and would NEVER cover patches — killing
   the complaint AND fault 2 outright. Cost: the sheet renders slightly
   smaller whenever any patch is measured (a mid-measurement size jump the
   first time the chip appears — visible, and the kind of layout-shift Knut
   disliked). Worth OFFERING; hover-to-hide still helps when zoomed.
2. **The `_caption_lbl` under the preview** — occupied: Measure sets
   "CHART PREVIEW" (tab_measure.py:2048); merging legend text into it makes
   one label carry two jobs and drops the ◤/◢ glyph adjacency to the patches.
   Weaker.
3. **Fade to near-transparent** — he said "disappears"; a ghost still
   obscures a colour judgement (any overlay tints patches). Rejected.
Recommendation: ship hover-to-hide now; offer (1) as a one-line question to
Basti ("legend under the sheet instead of on it?") — if he takes it,
hover-to-hide remains useful only for zoom, but it is ~20 lines and additive.

## 7. Q6 — Does the chip need to exist at all once learned?
No "don't show again" precedent exists (grep over ui/core/workflow: the only
`suppress_*`/`_dismissed` hits are printtarg's left-clip flag and the reflect
notice — nothing settings-backed for one-time hints). And the chip is NOT a
one-time tip: its wording is STATE ("Showing measured colours, unread patches
show expected…" — :2866-2872), changing with `_overlay_mode`. A user reading
the "measured" view needs the reminder that unread patches lie. Do not invent
a don't-show-again here. (The existing "Show overlay" checkbox already
removes chip+overlay together for those who want neither.)

## 8. Q7 — Edge cases, numbered, with required behaviour
1. **Chip at top** (fault 2): hover-hide must work wherever the chip is —
   automatic, the rect is recorded where it was placed. Additionally FIX the
   placement: include the overlay ITEMS' own boxes in `patch_bottom`
   (`for r, *_ in items: patch_bottom = max(patch_bottom, oy+(r.y()+r.height())*s)`)
   — items ⊆ chart patches, so with rects present it is a no-op, and with
   rects absent the chip drops below the lowest split patch instead of
   pinning to `oy`. Kills P2/P6-top and the F1 look.
2. **Chart smaller than pane** (P1): chip centred in the sheet's bottom
   margin; rect valid; hover works. No special handling.
3. **Zoomed/scrolled** (interactive): only soft-proof uses it and never has a
   chip; the `_paint_geom`-delta translation is 0 there, correct anyway.
4. **Multi-page**: chip only on pages with items; page flips repaint and
   recompute rect + verdict from the stored pointer; when no chip is drawn
   set `_legend_rect = None` so no phantom hide-zone survives the flip.
5. **dpr 2.0**: chip is drawn in logical px (no `_dsnap` on the chip), rect
   recorded in logical px, mouse positions logical — probe ran at real
   dpr 2.0 and the maths held. No device-pixel conversion anywhere.
6. **Three wordings**: widths differ (P3: 699/703/1191 device px); rect is
   recomputed every paint from `fm.horizontalAdvance` and `set_overlay_mode`
   repaints immediately (:1650-1657) — verdict re-derives. No stale-width bug
   possible.
7. **Very narrow pane** (P7): chip wider than the paper — `cx = max(img_l,
   min(cx, img_r - tw))` clamps only LEFT; chip overflows the right paper
   edge and clips its text at the canvas edge. The recorded rect must be the
   DRAWN rect (cx, cy, tw, th), overflow included, so the whole visible chip
   is a hide trigger. (The clipped text itself is a pre-existing cosmetic
   defect — flagged for Basti, not this change.)
8. **`items` empty**: no chip drawn today (guard :2862); set
   `_legend_rect = None`, hit test no-ops, zero repaint churn from moves.
9. **Chip appears under a parked pointer** (first strip read completes):
   containment says hidden → it never pops under the cursor; moves off →
   appears. Correct and mildly elegant.
10. **Panning branch early-return** (:3190-3197): store the pointer BEFORE
    the branch or panning leaves a stale position; the pan's own
    `_repaint_label()` then re-derives the verdict for free.
11. **leaveEvent**: clear pointer; repaint ONLY if the chip was hidden
    (`self._legend_hidden`), mirroring the `_hover_patch_loc` pattern there.
12. **Measurement updating the overlay while hidden**: every
    `set_patch_overlay` repaint re-derives the verdict from the stored
    pointer — chip stays hidden while the pointer rests on it. Desired.

## 9. Q8 — Tests that prove it (real widget, no restatement)
File: `tests/test_legend_hover_hide.py` (everyday tier — no Argyll, no slow
mark). All arms drive a real `TiffPreview` offscreen with a synthetic TIFF and
locate the chip by PIXEL SCAN of the rendered canvas (grey run ≈ RGB 80±25,
≥30 logical px wide — the blend of `QColor(20,20,20,190)` over paper white),
never by reading `_legend_rect` back (that would restate the implementation).

1. **Visible → hidden → visible**: render with overlay+rects, assert chip
   pixels present at the bottom; send a real `QMouseEvent` move (through
   `QApplication.sendEvent` on the widget — propagation proven in probe case
   5) to a point inside the chip; assert chip pixels GONE **and the
   split-patch colours still present** at their boxes; move outside; assert
   chip back.
2. **leaveEvent restores**: hide as above, `sendEvent(Leave)`, assert back.
3. **No oscillation**: with the pointer parked inside the rect, force three
   repaints (`set_overlay_mode` round-trip, `_repaint_label()`); assert the
   chip absent in ALL three canvases (an oscillating implementation shows it
   in at least one).
4. **Placement fix** (edge case 1): overlay items, `_stripe_rects == []` —
   assert the chip's row-band sits BELOW the lowest item box, not in the top
   fifth of the sheet. (This test fails RED today — proven by probe P2 — so
   the mutation is proven to land.)
5. **Coordinate offset arm**: put the widget in a layout where the label has
   a vertical offset (the real `_build_ui` already gives one: probe measured
   +25 px); a hide triggered by a WIDGET-coord point that is inside the chip
   only after `mapFrom` proves the mapping; a point 25 px BELOW the chip in
   widget coords must NOT hide it (this arm fails against a naive
   `event.pos()` implementation).

**The vacuity guard, named**: arm 1's "hidden" state asserts BOTH chip-absent
AND split-patches-present in the same canvas — a probe that renders nothing
(or a hide that blanks the canvas) fails the second half; arm 1's first half
fails if the chip never rendered at all. Additionally arm 4 was demonstrated
red against HEAD before implementation (probe P2), so the suite cannot be
green by construction.

---
## 10. Verdict

**BUILD AS DESIGNED, with four named changes** (the core — record rect, track
pointer, skip drawing, repaint on boundary — survives attack):

1. **Compute the chip placement unconditionally and store it in label
   coords** (translate via the `_paint_geom`-minus-call-offset delta). The
   design as literally written ("record at paint time … skip drawing") records
   nothing while hidden and OSCILLATES (§3).
2. **Hit-test in mapped coords** (`_img_label.mapFrom(self, pos)`), never
   `event.pos()` raw — the offset is real and measured (+25 px here) (§2).
3. **Pointer state at the top of `mouseMoveEvent`** (before the panning
   early-return), cleared in `leaveEvent` (+ `hideEvent` belt-and-braces);
   hidden-ness DERIVED at paint, repaint only on verdict change (§3, §5).
4. **Take the two placement fixes along** (both need Basti's nod, both
   one-to-three lines): (a) `patch_bottom` includes the overlay items' own
   boxes — fixes fault 2 for every journey including the ones hover can't
   help; (b) `TiffPreview.clear()` also clears `_patch_overlay` (+
   `_page_patch_boxes` is already there; `_patch_info` already cleared) —
   fixes the P6 stale-splits-over-a-new-chart leak. Neither is covered by a
   docs/design spec (checked: the chip exists only in code comments), so
   these are code-fault fixes, not spec deviations — still Basti's call
   because (b) changes observable behaviour.

### Module map (exact)
| File | Change |
|---|---|
| `ui/tiff_preview.py` `__init__` (~:601) | `self._legend_rect: QRect \| None = None`, `self._legend_pointer: QPoint \| None = None`, `self._legend_hidden = False` |
| `ui/tiff_preview.py` `_draw_cq_overlay` (:2862-2918) | compute placement always; include item boxes in `patch_bottom`; store label-space `_legend_rect` (translate by `_paint_geom` delta — note `_repaint_interactive` assigns `_paint_geom` AFTER the overlay call (:3162), so store canvas rect + call-offsets and translate lazily in the hit test, or move that assignment up); skip `fillRect`/`drawText` when hidden |
| `ui/tiff_preview.py` `mouseMoveEvent` (:3189) | first lines: update `_legend_pointer`; derive verdict; `_repaint_label()` on change |
| `ui/tiff_preview.py` `leaveEvent` (:3249) | clear `_legend_pointer`; repaint if `_legend_hidden` |
| `ui/tiff_preview.py` `hideEvent` (new) | same clearing |
| `ui/tiff_preview.py` `clear()` (:1779) | add `self._patch_overlay = {}` (fix b) |
| `tests/test_legend_hover_hide.py` (new) | the five arms of §9 |
| i18n | NO new user-facing strings — nothing to extract/translate |

### Implementation plan
1. Add the three fields; write the placement block so `cx/cy/tw/th` are
   computed before the draw decision; store rect + the (ox, oy) it was
   computed in.
2. Add `_legend_hit(widget_pos) -> bool` doing mapFrom + delta translation +
   contains; call it from `mouseMoveEvent` (top) and from the paint (with the
   stored pointer).
3. Wire `mouseMoveEvent`/`leaveEvent`/`hideEvent` repaint-on-change.
4. Fix (a) `patch_bottom` from items; fix (b) `clear()` — each its own commit
   with its red test first.
5. Run `QT_QPA_PLATFORM=offscreen pytest -n auto` (everyday tier); on-screen
   sanity pass with the probe pattern; screenshots for Basti.

### Open questions for Basti (rulings needed before/with the build)
1. Placement fix (a): chip under the lowest SPLIT patch when strip geometry is
   missing — approve? (Fixes the F1 look everywhere, one line.)
2. `clear()` fix (b): any journey that WANTS the overlay to survive
   `clear()`? I found none (the tab pairs clear with `clear_patch_overlay`),
   but it is an observable change.
3. Offer alongside: move the legend permanently BELOW the sheet using the
   `_pending_caption_band` mechanism (never over patches, but the sheet
   shrinks a few px when the first result lands)? Hover-to-hide ships either
   way; this would make it a zoom-only nicety.
4. P7 cosmetic: on a very narrow pane the "measured" wording overflows the
   paper and clips mid-word — elide with "…" or leave as is?

### Rating of the proposed design: **7 / 10**
The shape is right (paint-time rect + pointer tracking + reuse of the
existing tracking/eventing — (b) is exactly correct, nothing new to plumb;
(c) hide-not-fade is the right reading of the request). What costs it three
points: (1) as written it oscillates — the rect must be computed on the
paint where the chip is NOT drawn, and the brief's own hysteresis question
shows the risk was sensed but the fix (unconditional placement) not named;
(2) the coordinate-space hazard was flagged as a question but the naive
implementation would have shipped a 25-px-plus-centring error, and the
translate-via-`_paint_geom` bridge (plus the `_repaint_interactive`
assignment-order trap) had to come from the code; (3) the design treats the
chip as the only moving part — the placement fault (2) and the `clear()`
leak found en route change what "the chip's rectangle" even is on real
journeys, and hover-to-hide without fix (a) leaves the top-pinned chip
parked over row 1 for anyone who reaches it without a mouse. All three are
now named, small, and testable.

**Report complete 2026-08-30. Probe: scripts/probe_48_legend_placement.py; screenshots
~/Desktop/cr30-legend-hover/ (P1-P7). Plist verified unchanged.**
