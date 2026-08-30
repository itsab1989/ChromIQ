# 50 — The `v4.1.5-beta.3` gate

**Reviewer:** Claude (adversarial gate pass) · **Started:** 2026-08-30
**Range:** `v4.1.5-beta.2..HEAD` (`396d9b82`), thirteen commits
**Question:** is this range safe to tag as `v4.1.5-beta.3`?

The legend hover/fade work is covered separately and in full in
`docs/cr30_reports/49_legend_hover_verify.md`; its verdict is carried into the
ranking here rather than re-argued.

Every claim is tagged **PROVEN** (I ran it) or **INFERENCE**.
Proof shots: `~/Desktop/cr30-beta3-gate/` with its own README.

## The thirteen

| commit | what it changes | priority |
|---|---|---|
| `396d9b82` | row numbers clamp at the paper edge; inspector relabels + warns | 1 |
| `af9cb63c` | ruling record (docs) | 6 |
| `ba09130a` | area-first stops reserving the row-label band outside the margin | 1 |
| `3236cb9b` | the legend fades | 3 → report 49 |
| `9024bdfc` | Patch size / Patch scale move Expert → Basic ▸ Layout; `pscale`/`sscale` floor 1.0 | 2 |
| `08b4bf2f` | ruling record (docs) | 6 |
| `29c1a7c6` | legend hover-hide + `patch_bottom` + `clear()` | 5 → report 49 |
| `b46ab0cc` | `docs/index.html` — public site copy about the CR30 | 6 |
| `974d528f` | aperture centred in the body | 4 |
| `761cdf4f` | aperture warning visible; tooltip corrected | 4 |
| `6b879c6e` | CR30 aiming overlay | 4 → report 47 |
| `b286270d` | ruling record (docs) | 6 |
| `6428fd2c` | flagged ring survives a neighbour's fill | 5 |

## Status — COMPLETE

- [x] T. Everyday tier: **8,205 passed**, 262 skipped, 3 xfailed, 89 s
- [x] 1. The margin work — **Guided is byte-identical on all four instruments**;
      the fix works and is quantified; one real cost found (§1c) and one
      imprecise warning (§1d)
- [x] 2. Patch size / scale move — correct in both modes, round-trip OK, the
      0.5 trap is really closed
- [x] 3. Legend fade — **three faults**, see report 49
- [x] 4. Aiming overlay — **0 differing pixels** since `b46ab0cc`
- [x] 5. Flagged rings + legend placement — **0 differing pixels** since
      `v4.1.5-beta.2`
- [x] 6. Every site claim checked against shipped code — all true, but **the
      "get the beta" link goes stale the moment you tag**
- [x] VERDICT: **NO** — three items, two of them one line each

Driver: `scripts/drive_50_beta3_gate.py` · renderers:
`scripts/render_50_layout_reference.py`, `scripts/probe_50_geometry.py`,
`scripts/probe_50_row_numbers.py`, `scripts/render_49_reference.py`.
Proof shots + README: `~/Desktop/cr30-beta3-gate/`.

---

## T. The everyday test tier  — PROVEN

```
QT_QPA_PLATFORM=offscreen pytest -n auto --dist loadfile -q
8205 passed, 262 skipped, 3 xfailed in 89.12s
```

Green, on the tip commit `396d9b82`. The release gate (`--runslow`) is yours to
run at the tag, per the brief.

---

## 1. The margin work — `ba09130a` + `396d9b82`

### 1a. GUIDED IS BYTE-IDENTICAL  — PROVEN, at the strongest level asked for

Not "the numbers agree" — the **rendered sheets are the same bytes**. The same
engine build (`workflow.layout_engine.chart.build_chart`, fixed seed, the same
real `.ti1`) was run inside a `git worktree` of `v4.1.5-beta.2` and against the
working tree, and the TIFFs hashed:

| case | pages | SHA-256 (first 16), beta.2 → HEAD |
|---|---|---|
| Guided i1Pro A4 | 2 | `9353661454e6750a` → **same**, `19cadb25e014af6a` → **same** |
| Guided CR30 A4 | 2 | `ff19b4c8eac49a25` → **same**, `f2133fc40576f052` → **same** |
| Guided ColorMunki A4 | 5 | all five pages → **same** |
| patch-first i1, 0 mm left margin | 1 | `a9a85d0aca51dab4` → **same** |

The Guided kwargs are `workflow/chart_creator._engine_build_kwargs`'s own —
and the reason it is safe is visible there: **Guided never sets `layout_mode`**,
so `instruments.geom_from_build_kwargs` computes `area_first = False`, and
`fill_beyond_ruler` is `False`. The new `_rlwi` is then `g.rlwi`, exactly as
before.

Geometry, both commits, `npat = 1144` (0.000 mm = identical):

| case | `rlwi` | `fill_beyond_ruler` | x0 beta.2 | x0 HEAD | Δ | patches/page |
|---|---|---|---|---|---|---|
| guided_i1 | 0.0 | False | 26.000 | 26.000 | **0.000** | 441 → 441 |
| guided_p3 | 0.0 | False | 26.000 | 26.000 | **0.000** | 90 → 90 |
| guided_cm | 0.0 | False | 6.000 | 6.000 | **0.000** | 105 → 105 |
| guided_cr30 | **7.5** | False | 13.500 | 13.500 | **0.000** | 345 → 345 |
| patch-first CR30, L = 0/1/3/5/7.5/10/20 mm | 7.5 | False | unchanged at every one | | **0.000** | unchanged |

**Not a single Guided pixel moved, on any of the four instruments.**
The keying decision (`fill_beyond_ruler`, not `margins_are_law`) is the right
one and is why: `rlwi` is 7.5 mm **only for the CR30** — it is 0.0 for the
i1Pro, the i1Pro3 and the ColorMunki, so even a wrong keying would have been
invisible on three of the four, and would have moved every patch-first CR30
chart. It did not.

### 1b. The fix on Basti's own case  — PROVEN, quantified

Area-first, CR30, hexagonal, 26 × 44, margins T6 R2 B1 **L1**:

| | beta.2 | HEAD |
|---|---|---|
| first patch x0 | **10.380 mm** | **2.880 mm** (−7.500) |
| patches per page | 1144 | 1188 |
| patch width | 7.520 mm | 7.520 mm (unchanged) |
| **inspector's "Left (to first patch)", real generated chart** | — | **1.0 mm**, against a set margin of 1.0 |

`A4_margin_inspector_L1.png` is the panel for a **real chart generated in the
real Create Chart tab**: `Left (to first patch) 1.0 mm`, `min 1.0`. The number
in the box is now the number on the sheet.

The 7.5 mm is freed at every left margin (0 → 20 mm, measured: Δx0 = −7.500 at
all of them), and the residual gap is the centring share the commit is honest
about not claiming: at L = 1 the first patch sits at 2.880 mm, of which 1.880 mm
is centring. The measured left margin reads 1.0 mm because on a HEX chart the
staggered rows reach half a patch further left than x0.

### 1c. ⚠ THE ROW NUMBERS: at Basti's own margin, half of them are unreadable  — PROVEN

This is the cost of 1b, and it lands squarely on the case he reported.
The numbers are drawn first and the patches **over** them, and on a hexagonal
chart the odd rows overhang half a patch to the left, so they eat the digit.
Rendered at 300 dpi, black ink counted inside each row's own band (a full digit
is 300–450 px):

| left margin | x0 | ink in the numbers "3" / "7" / "9" | verdict |
|---|---|---|---|
| **0.0 mm** | 1.890 | `0, 0, 0` | **GONE — every odd row has no number at all** |
| **1.0 mm** ← his | 2.880 | `78, 73, 117` | **UNREADABLE — ~20 % of the glyph survives** |
| 2.0 mm | 3.873 | `355, 293, 376` | legible |
| 3.0 / 4.0 / 5.0 / 7.5 / 12.0 mm | | `355, 293, 376` | legible |

Pictures: `A6_rownumbers_L0mm_GONE.png`, `A7_rownumbers_L1mm_UNREADABLE.png`,
`A8_rownumbers_L2mm_legible.png`, `A9_rownumbers_L3mm_legible.png` (left edge of
the real sheet, 3×). At 0 mm rows 1/3/5 have nothing beside them at all; at 1 mm
the "3" and the "5" are stubs behind a hexagon.

Basti's ruling — *the margin is law for the patches; the furniture slides* — is
implemented exactly as ruled, and the loss is the ruling's own consequence, not
a coding error. **But the app currently tells him about it in the same words at
5 mm (where nothing is lost) as at 0 mm (where half his coordinates are gone),
and A1/B2 coordinates are what make hand-aiming a CR30 possible.**

### 1d. The warning: correct, but it over-warns and under-states  — PROVEN on screen

`TabChart._engine_text_overflow_warnings`, driven through the real tab
(area-first, CR30 hex, 26×44, T6 R2 B1):

| left margin | row-number warning | numbers actually legible? |
|---|---|---|
| 0.0 / 1.0 | **shown** | **no** |
| 2.0 / 3.0 / 5.0 / 7.0 | **shown** | **yes** |
| 7.5 / 8.0 / 12.0 | not shown | yes |
| patch-first, L = 1.0 | **not shown** (correct — nothing overflows) | yes |

The rule is `margin_left < geom.rlwi` (7.5 mm). The damage begins below ~2 mm.
So it cries wolf across 2–7.5 mm and says the same mild thing ("**may** sit
under the patches") in the case where they are simply gone. Its second clause is
also literally false in the 2–7.5 mm band: they do move to the page edge, but
they do not sit under anything.

### 1e. Does anything else read `rlwi` and now disagree?  — PROVEN

* **The margin inspector** measures from the rendered TIFF (`measure_margins`
  / `measure_from_engine`) — it reports what is on the sheet, and it now reports
  1.0 for a 1.0 setting. Consistent.
* **`patch_boxes_from_sidecar`, `engine_strip_rects_from_sidecar`, the `.cht`
  writer and `scanin`** all read the `channels.json` `layout` block, which is
  written **from the same `placement()`** that the fix changed. They cannot
  disagree with the geometry — they *are* the geometry. Confirmed empirically:
  the Measure-tab overlay, the strip rects and the patch boxes all line up on a
  chart built at HEAD (report 49's phase E used exactly such a chart).
* **The one unconditional change**: `raster.py`'s `_tx = max(0, _rx - _tw)`
  applies in every mode, not just area-first. Tested at the worst patch-first
  case (i1, 0 mm left margin): the rendered sheet is **byte-identical** to
  beta.2, so the clamp is a no-op wherever the band is still reserved.

### 1f. Not verified

* Non-A4 paper sizes and the second/third page of a multi-page area-first CR30
  chart. **INFERENCE** that they behave the same: the change is one term in one
  expression, applied per page by the same `placement()`.

---

## 2. Patch size / Patch scale move — `9024bdfc`  — PROVEN on screen

| check | result |
|---|---|
| Where the rows now live | parent chain measured on screen: `QWidget ← QGroupBox("Layout") ← QWidget ← CollapsibleGroupBox("Basic")`. **In Basic ▸ Layout**, as claimed. |
| patch-first | patch-size container **shown** (h = 54), area container hidden. `B1_patch_first_layout_group.png` |
| area-first | patch-size container **hidden**, area container shown (h = 86). `B2_area_first_layout_group.png` |
| switching back and forth | correct both ways, no leftover |
| unseeded panel (the 0.5 trap) | fresh `LayoutOptionsPanel()`: **pscale = 1.0, sscale = 1.0** (range 0.5–3.0). Fixed. |
| spurious signal at construction | none — `sb.setValue(1.0)` runs **before** `sb.valueChanged.connect(self._emit)` |
| recipe round-trip | set pscale 1.4 / sscale 0.8 / patch 9.0 × 11.0 → `_current_layout_recipe()` reports all four → zeroed → `set_recipe()` → **all four restored. ROUND-TRIP OK**, and the rows stay visible |
| FROM PROFILE GAMUT | the module reuses the **same `LayoutOptionsPanel` object** (verified identity), and the patch-size rows are shown there too. `B5_from_profile_gamut_window.png` |
| anything positioned relative to the moved rows | the Layout grid rows were renumbered 1→3, 2→4, 3→5 in the same commit; on screen the group lays out correctly in both modes with no gap where the rows used to be |

Nothing here worries me. The `pscale`/`sscale` floor fix is a real latent bug
closed.

---

## 3. The legend fade — carried from report 49

Three faults, all cursor-free and headless-reproducible; full detail and a
tested candidate fix in `docs/cr30_reports/49_legend_hover_verify.md` §5.
Summary for the gate:

* **F1 — flick off the chip and straight back on and it stays drawn under your
  pointer, and does not recover** until you move fully clear and back.
* **F2 — resize the window (a tiling shortcut) while pointing at the chip and
  the legend disappears** and stays gone.
* **F3 — load a different chart while pointing at the chip and the new chart's
  legend never appears.**

No flicker (eight 1-px sweeps, four edges, both directions, one clean turn-round
each), no segfault (400 reversals at 0 ms, plus 68 driven from inside the
animation's own callback), mapping exact (0 px), and **0 differing pixels**
against the parent for every other overlay.

---

## 4. The CR30 aiming overlay — not disturbed  — PROVEN

`6b879c6e` / `761cdf4f` / `974d528f` were verified on screen in report 47. What
this pass adds is that **nothing after them moved a pixel of it**: the same
`TiffPreview` scene with every overlay on at once — split patches, warn rings,
the 33 mm body circle, the aperture warning, the accent ring, the patch hover
outline, the strip hover frame, both bidirectional arrows, "show only measured"
blanking and its grid — rendered at `b46ab0cc` (before the legend work) and at
HEAD gives **0 differing pixels**, in all three overlay wordings. The paint
order in `_draw_cq_overlay` is intact.

`974d528f` is a **comment-only** change to `instruments.py` (5 lines in, 4 out,
no number touched): the aperture-centred assumption is now recorded as confirmed
by Basti on his own unit.

---

## 5. Flagged rings + legend placement — `6428fd2c`, `29c1a7c6`

* The preview canvas at **`v4.1.5-beta.2` versus HEAD**, rich scene, both
  wordings, aiming overlay excluded (it did not exist at beta.2):
  **0 differing pixels.** So nothing in the thirteen commits changed how an
  existing chart is drawn.
* `6428fd2c`'s own effect needs a hex chart with **adjacent** flagged patches,
  which my scene does not have; it carries its own `tests/test_warn_ring_draw_order.py`
  (green) and was verified in report 45. **INFERENCE** that it is unchanged.
* `29c1a7c6`'s two fixes: `clear()` proven real by counterfactual against the
  parent (5 items survived `clear()` at the parent, 0 at HEAD) and reachable
  through the tab; the `patch_bottom` fix proven by a parent-vs-HEAD render, with
  a correction owed to its commit message (report 49 §3).

---

## 6. The docs and the public site copy — `b46ab0cc`

Three of the four docs commits (`af9cb63c`, `08b4bf2f`, `b286270d`) touch only
`docs/cr30_reports/35_beta2_backlog.md`. Nothing to gate.

`b46ab0cc` edits **`docs/index.html`, which is live and public.** I checked
every factual claim in the new copy against the shipped code:

| claim on the site | backed by | verdict |
|---|---|---|
| "no ArgyllCMS driver of any kind, so ChromIQ drives it itself" | `workflow/cr30/` exists and is the driver | **true** |
| "over **USB or Bluetooth**" | `requirements.txt` ships `pyserial>=3.5` **and** `bleak>=0.21`; `tests/test_cr30_ble_address_key_is_live_at_arm_time.py` and friends exercise the BLE path | **true** |
| "the preview draws the instrument's **33 mm body to scale**" | `CR30_BODY_DIAMETER_MM = 33.0`, drawn at scale in `_draw_cq_overlay`; verified on screen in report 47 | **true** — but the 33 mm is **single-sourced from the CHNSpec brochure**, which the code says in its own comment. The site states it flatly. Acceptable (it is the vendor spec) and worth knowing. |
| "stops measuring altogether if anything magnetic touches its opening … ChromIQ … refuses the reading" | `tests/test_cr30_magnet_stops_the_session.py`, `…_the_magnet_remedy_reaches_the_session.py`, `…_every_owner_gets_the_magnet_guard.py`, all green | **true** |
| "Calibrate it, read the chart patch by patch, build a profile" | the CR30 measure bridge + the existing profile path | **true** |

### ⚠ ONE THING THE TAG BREAKS

The copy's call to action is hard-wired to the **previous** beta:

```html
<a href="https://github.com/itsab1989/ChromIQ/releases/tag/v4.1.5-beta.2">get the beta</a>
```

The moment `v4.1.5-beta.3` is tagged, the public page sends every reader to
beta.2 — an older build without any of these thirteen commits. The commit
message explains why it is not `/releases/latest` (GitHub's "latest" excludes
pre-releases, so it would have served 4.1.4), and that reasoning is right.
**INFERENCE** (I did not fetch GitHub): `https://github.com/itsab1989/ChromIQ/releases`
— the release *list* — does show pre-releases, and would never go stale.

This is one line, it is public, and it is wrong the instant you tag.

---

## 7. Anything that should not ship in a beta

Nothing in the thirteen is unfinished-in-tree, gated behind a half-built flag,
or debug-only. Two notes rather than objections:

* **An area-first CR30 chart REBUILT after this upgrade will not match the one
  built before it** (1144 → 1188 patches per page on Basti's recipe, first patch
  7.5 mm further left). Charts already built keep their TIFFs and sidecars, so
  nothing already printed or measured is affected — but "regenerate this chart"
  now gives a different sheet. That is the intended fix, and it is worth a
  changelog line rather than a silent change.
* `scripts/drive_47_aiming_overlay_verify.py` (1,166 lines) and
  `scripts/drive_cr30_left_margin_and_flag_rings.py` ship in the range. They are
  developer drivers under `scripts/`, consistent with the rest of the tree, and
  they are not in `ChromIQ.spec`'s bundle. No objection.

---

## VERDICT — **NO**, but only just, and the list is short

The engineering in this range is sound. The everyday tier is green (8,205
passed), **Guided is byte-identical on all four instruments**, the preview
canvas is pixel-identical to `v4.1.5-beta.2`, and the fault Basti reported is
fixed and measurable on screen: he sets 1 mm and the panel now says 1.0 mm.

I am withholding the green light for three things, two of which are one line
each.

### The shortest list that makes it YES

**1. `docs/index.html` — the "get the beta" link.** It points at
`releases/tag/v4.1.5-beta.2`. Tagging beta.3 makes the live public page send
every reader to the previous build. Point it at
`https://github.com/itsab1989/ChromIQ/releases` (which does list pre-releases,
unlike `/latest`) so it never goes stale again, **or** bump it to
`v4.1.5-beta.3` in the same commit as the tag. *One line.*

**2. The legend hover fault F1** (report 49 §5): flick the pointer off the chip
and straight back on and the legend is drawn on top of your patches while you
are pointing at it, and stays there until you move fully clear and back. This is
the feature failing in the middle of the gesture it exists for, on the complaint
that prompted it, and the user's instinctive fix — wiggle the mouse — makes it
worse. The cause is one guard in `_start_legend_fade` that drops a legitimate
request when the opacity already equals the new target while an animation runs
the other way. *A three-line change; I have run it and it makes 13/13 tests and
156/156 preview tests pass.*

**3. The legend hover fault F2** (report 49 §5): resize the window with a tiling
shortcut or full-screen while pointing at the chip, and the legend vanishes and
does not come back. Same root cause family — nothing reconciles the chip's
placement with the hover state since the fade landed. *Fixed by the same patch's
second half.* (F3 — a new chart inheriting the hidden state — falls out of the
same fix; take it too.)

### Strongly recommended in the same push, not blocking

**4. Sharpen the row-number warning.** Measured: at a 0 mm left margin **every
odd row loses its number entirely**; at 1 mm — Basti's own setting — about 20 %
of the glyph survives, which is unreadable; from 2 mm up they are perfectly
legible. The warning currently fires identically anywhere under 7.5 mm, so it
cries wolf at 5 mm and understates ("**may** sit under the patches") at 0 mm
where they are simply gone. Two bands would be honest: below ~2 mm say the
coordinates are being lost, above it say they have moved to the page edge. This
matters because A1/B2 coordinates are what make hand-aiming a CR30 possible, and
the fix that produced this is the one he asked for.

**5. Fix the five surviving mutations in `tests/test_legend_hover_hide.py`**
(report 49 §6) with the code: two tests are vacuous as written, and the
coordinate mapping, `hideEvent` and the elision have no cover at all.

**6. Correct two pieces of prose** while they are fresh: `29c1a7c6`'s three
claimed routes to the strips-empty state (one is factually the wrong way round —
report 49 §3), and the `_start_legend_fade` docstring's "never stopped".

### With 1–3 done, this is a GREEN LIGHT

Nothing else in the thirteen commits gives me pause. Re-run the everyday tier
after the fix (it takes 90 s), run `--runslow` at the tag as you planned, and
ship it.

