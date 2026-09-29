# ADVERSARIAL CHALLENGE — Nelson's 10x15 / 13x18 i1Pro presets
Reviewer: adversarial pass on `01-draft-plan.md`. Everything below is cited to
real code or measured with the shipped Argyll 3.5.0. Appended as confirmed.

---

## A. THE PAPER SIZE DECISION

### C1 — BLOCKER against plan option (a) as written: adding a paper to `PAPER_SIZES` without a capacity row makes ChromIQ tell the user 443 patches fit on a 100x150 card. It is ~90.

`data/patch_db.py:1028 query_patches` returns `None` for any paper not in its
tables, and every caller then goes to `workflow/chart_creator.py:2053
_binary_search`. That function seeds its search window from the *same* failed
lookup:

```
workflow/chart_creator.py:2080-2098
est_raw = query_patches(...) or query_patches(...) or 400
est  = max(20, int(est_raw / scale_sq))      # 400 / 0.95² = 443
lo   = max(20, int(est * 0.5))               # 221
hi   = max(lo + 50, int(est * 2.5))          # 1107
```

The loop only ever sets `best` when a probe returns **exactly one page**
(`chart_creator.py:2117-2122`). On a sheet whose true capacity is below `lo`,
every probe returns >1 page, `hi` walks down past `lo`, `best` stays 0, and
line 2128 returns the bogus `est`.

Measured, this checkout, real Argyll, the app's default i1 preset
(`-a0.95 -m10 -M10 -L`, `data/patch_db.py:I1PRO_DEFAULT_PRESET_KEY = "m10_a0.95"`):

| paper | printtarg truth (1 page fits) | `ChartCreator._binary_search` returns |
|---|---|---|
| 100x150 | **90-99** | **443**  (`found no valid capacity in [221, 1107]`) |
| 130x180 | **160-169** | **443**  (same warning) |
| 4x6 (existing) | 100 | 100 |
| 127x178 (existing) | 169 | 169 |

Reproduced with the shipped classes, not a re-implementation:

```
cc = ChartCreator(None, FM(), AppSettings())
cc._binary_search(ChartParams(instrument="i1", paper="100x150",
                              patch_scale=0.95, margin_mm=10))   -> 443
```

So option (a) is only honest if it ships **measured capacity rows** for
`100x150` and `130x180` in all eight `_PER_SHEET_CAPACITY*` tables that the
i1/p3/CM/SS matrix expects (`scripts/measure_*_capacity.py` exist for exactly
this). Adding the codes to `PAPER_SIZES`/`PAPER_LABELS` alone puts a 5x
over-estimate into the Guided patch-count field, the printtarg command preview
and the page-count line, for every user, on two new dropdown entries nobody
asked for.

Note this is a **pre-existing** bug that today is only reachable through the
`-p` "Custom (enter dimensions)" path (`data/parameters.yaml:734
custom_dimensions: true`). The plan would promote it from a corner to a
first-class dropdown item.

### C2 — the plan missed option (d), and it is the one I would take: `-p` already accepts a raw `WxH`, and `set_value` already routes it to the Custom row.

`_prebuilt_paper_code` feeds `_set_manual_value("printtarg", "-p", code)`
(`ui/tabs/tab_chart.py:11766`), which lands in
`ui/parameter_widget.py:141 set_value`:

```
ui/parameter_widget.py:152-170
elif t == "choice" ...:
    idx = combo.findData(str(v))
    if idx >= 0: combo.setCurrentIndex(idx)
    elif self._custom_combo is not None and "x" in str(v):
        w, h = int(parts[0]), int(parts[1])
        -> selects the "custom" item and fills the W / H spin boxes
```

`data/parameters.yaml:713` already lists `"custom"` as a `-p` choice with
`custom_dimensions: true`, and `ParameterWidget.value` reads it back as
`f"{w}x{h}"` (`ui/parameter_widget.py:95-98`). printtarg takes `-p100x150`
literally — verified: `printtarg -ii1 -p100x150 -t300 -a0.95 -m10 -M10 -L`
lays out a real sheet.

So `_prebuilt_paper_code` can simply return `"100x150"` / `"130x180"`, the
panel shows **Custom, W 100, H 150** — the exact truth — and **nothing global
changes**: no new dropdown item for every user, no layout-engine paper, no
relayout-dialog item, no i18n label, no capacity table. The
`workflow/layout_engine/papers.py` list, `ui/dialogs/ti2_relayout_dialog.py`
combos and `paper_name_token()` all already handle a bare `WxH` as a custom
size (`data/patch_db.py:252-262` returns it unchanged; comment: *"custom WxH or
unknown — already safe"*).

Cost of (d): the *capacity estimate* is still 443 if the user unlocks and
re-generates (C1 applies to a custom size today too). That is an argument for
fixing `_binary_search`'s window, not for widening the dropdown.

**Recommendation: (d) + fix `_binary_search`'s lower bound** (e.g. keep halving
`lo` while no single-page probe is found, or start `lo` at 20). (a) only if
Basti wants 10x15/13x18 offered to everybody, and then only with measured
capacity rows in the same commit.

### C3 — what the plan's option (c) "leave the fallback" actually does, measured.

`ui/tabs/tab_chart.py:10844-10851`: an unknown paper folder returns the literal
`"A4"`. It does **not** fail, warn, or log. The panel would then say A4 for a
100x150 card, and an "Edit layout" re-generate would lay 600 patches out on A4
(2 pages, i1 default) and print them on a 10x15 card. Silent, wrong, and
unrecoverable by the user. Ruled out, agreeing with the plan.

### C4 — `_prebuilt_paper` (the tooltip) has its own, separate map and its own
fallback, and the plan step 3 says "new folder entries" without saying both.

`ui/tabs/tab_chart.py:291-301` maps only `a4/a3/a3plus/letter` and otherwise
returns `paper.upper() or "A4"`. With the proposed folder name `10x15` the
tooltip would read *"laid out for 10X15"*. Both maps must be updated, and the
tooltip wants a human string ("10 x 15 cm (100 x 150 mm)"), not the folder name.

### C5 — "just add it to PAPER_SIZES" touches SIX independent, hand-maintained paper lists. The plan names one.

Grepped, this checkout:

| # | list | file:line | derived from PAPER_SIZES? |
|---|---|---|---|
| 1 | `PAPER_SIZES` / `PAPER_LABELS` / `PAPER_PRINTTARG_ARG` / `PAPER_FALLBACK` / `EXCLUDED_PAPERS` | `data/patch_db.py:201,218,225,234,270` | source |
| 2 | printtarg `-p` `choices` + `labels` | `data/parameters.yaml:713-731` | **no, literal** |
| 3 | the 13 translation overlays' `-p` `labels` | `data/i18n/parameters.de.yaml:549` (+ es fr it ja nl no pl pt ru sv zh_CN) | **no, positional** |
| 4 | layout-engine `_NAMED_MM` + `ENGINE_EXCLUDED_PAPERS` | `workflow/layout_engine/papers.py:19,31` | partly |
| 5 | `.ti2` PAPER_SIZE → `-p` reverse map `_NAMED_PAPERS` | `workflow/ti2_relayout.py:178-190` | **no, literal** |
| 6 | Patch Set Editor `_PAPER_ORDER` | `ui/dialogs/ti2_relayout_dialog.py:517-519` | **no, literal** |
| 7 | eight `_PER_SHEET_CAPACITY*` tables x 4 instruments | `data/patch_db.py:22-1020` | **no, measured** |

Two concrete breakages if only #1 (+#2) are done, which is what the plan's
step 4 describes:

* **#3 silently reverts the whole `-p` dropdown to English in 13 languages.**
  `core/i18n.py:302-312` applies a `labels` list *only* when its length matches
  the English one; a 16 -> 17 mismatch logs a warning and keeps English.
  `tests/test_i18n.py:140` turns that into a red gate, so it will be caught —
  but the fix is 13 files x a real translation of "10 x 15 cm (100 x 150 mm)",
  not a mechanical edit.
* **#6 + #5 put the wrong paper on screen in the Patch Set Editor.**
  `_paper_code_known()` (`ti2_relayout_dialog.py:522-529`) asks `PAPER_LABELS`,
  so adding the label makes it answer **True** for `100x150`; the combo is then
  built from the literal `_PAPER_ORDER`, `findData("100x150")` returns -1, the
  index is left where it was (**A4**, seeded at `:1053`) and the custom W/H row
  is explicitly hidden (`:6550`). A chart genuinely built at 100x150 reopens in
  the editor claiming A4. Today that path is safe precisely *because*
  `_paper_code_known` says False for a `WxH` code and the "custom" branch
  (`:6551-6560`) fires.

That last point is the strongest argument for C2's option (d): leaving these
sizes as `WxH` custom codes keeps every one of these seven lists correct with
no edit at all.

### C6 — the plan's `EXCLUDED_PAPERS["p3"]` note is half the exclusion story.

`EXCLUDED_PAPERS` (`data/patch_db.py:218`) is consumed by
`_rebuild_paper_combo` (`ui/tabs/tab_chart.py:12574-12586`) — the **Guided**
paper combo — and by `papers.list_papers(for_engine=False)`. The Manual
printtarg `-p` widget is built straight from `parameters.yaml` and honours **no
exclusion at all**, so a p3 user in Manual would still see and be able to pick
10x15. The engine has its own table, `ENGINE_EXCLUDED_PAPERS`
(`workflow/layout_engine/papers.py:19`), which the plan does not mention and
which already excludes `127x178` and `4x6` for p3 for exactly this reason.
Both tables, or the exclusion is cosmetic.

---

## F. THE ASSETS — independent re-verification

### C7 — `derive_layout_from_render` passing is NOT sufficient, but it is the strongest single check. Here is what it does not cover, re-checked independently.

`workflow/layout_from_render.py:260` only proves *the render agrees with the
`.ti2`*: right number of strips/steps per page, and every cell's interior is
that patch's device RGB within 8-bit rounding
(`_TOL = 3`, `layout_from_render.py:56`). It says **nothing** about the `.ti1`
vs the `.ti2`, the header counts, randomisation, spacers, sheet size vs
`PAPER_SIZE`, strip length vs the i1 ruler, or duplicate patches.

Re-measured all of those independently:

**(a) `.ti1` <-> `.ti2` identity — PASS.** 600/600 and 648/648 SAMPLE_IDs match
one-for-one. Device values differ on 586 / 638 rows, but only in the 5th-6th
decimal (`16.6667` -> `16.66743`, `50.0000` -> `50.00076`): printtarg's 8-bit
render quantisation written back, which is what every shipped bundle does.
Nothing structural.

**(b) header white/black counts — PASS.** Both `.ti1`s declare
`WHITE_COLOR_PATCHES "2"` / `BLACK_COLOR_PATCHES "2"` and both contain exactly
2 pure (100,100,100) and 2 pure (0,0,0). Those are also the ONLY duplicated
device values in either set — no accidental repeats.
*Worth flagging to Nelson, not blocking:* every shipped Pharmacist bundle and
ChromIQ's own default use **4** white / **4** black; `targen`'s `-e`/`-B`
defaults in this app are 4/4 (`ChartParams.white_patches = 4`,
`workflow/chart_creator.py`). Two white patches on a 600-patch chart is a
thinner white-point anchor than anything ChromIQ ships. His call, but ask.

**(c) randomisation — PASS, and I ran the real gate, not a re-implementation.**
`workflow.ti2_relayout.analyze_randomisation` (`ti2_relayout.py:1284`):

```
600p  safe=True  n_strips=40  min_symmetry=53.03  min_confusability=45.85
648p  safe=True  n_strips=36  min_symmetry=63.83  min_confusability=46.53
```

Both carry `RANDOM_START` (397 / 518), not `CHART_ID`, so chartread gets
bidirectional auto strip-ID. (Aside, unrelated to this task: the SHIPPED
`colormunki/a4/abw702` bundle reports **safe=False** on the same gate. Someone
should look at that separately.)

**(d) page fill / short last strip — PASS, no short strip anywhere.**
Derived from the renders: 600p = 4 pages x **exactly 150** patches (10 strips
x 15); 648p = 3 pages x **exactly 216** (12 strips x 18). `PASSES_IN_STRIPS2`
is `10,10,10,10` and `12,12,12`, matching. So the "does chartread cope with a
short final strip / padlrow" question **does not arise** — there is no partial
strip on any page of either chart. The plan's step 6 should pin this, because
it is the property that would break silently if a bundle were ever regenerated
at a different count.

**(e) i1 ruler — PASS with wide margin.** Measured patch-box extents per page:

| chart | strip length | Argyll's `mxrowl` for i1 |
|---|---|---|
| 600p | 116.77 - 117.19 mm | 240 mm |
| 648p | 147.32 mm | 240 mm |

**(f) NEW, and the plan does not mention it — the ink comes within 1.0 mm of
the sheet edge.** Measured non-white bounding box per page at 360 dpi:

| chart | top | bottom | left | right |
|---|---|---|---|---|
| 600p (all 4 pages) | 2.96-3.88 mm | 4.02-5.01 mm | 1.34-1.62 mm | 1.34-1.48 mm |
| 648p (all 3 pages) | **1.20-1.55 mm** | **0.99-1.34 mm** | 1.83-2.19 mm | 2.05-2.26 mm |

The *patches* are safe (600p: L 18.98 / R 4.89 / T 20.18 / B 12.63 mm; 648p:
L 26.95 / R 6.95 / T 20.46 / B 12.08 mm) — it is the crop marks and the strip /
chart identification text that sit in the outer 1-2 mm. A typical inkjet's
non-borderless imageable area starts ~3-3.4 mm in, so on a bordered print
**those marks and part of the identification text will be clipped**. Not fatal
for chartread (it reads patches), but it is a visible difference from the A4
bundles and it will generate support questions. It also interacts badly with
the print tab's own advice — see C10.

### C8 — THE BIGGEST FINDING, AND NEITHER THE FACTS NOR THE PLAN MENTIONS IT: the charts tell the user to do the exact opposite of what ChromIQ's print preflight tells them.

I read the sheets. The left band of **every page of both charts** carries this
printed instruction:

> `i1Pro 1/2/3 600 patch target for 10x15 cm / 4x6" photo card - print with
> borderless setting / NO expansion, retain size, color management: OFF`

ChromIQ's own preflight dialog says, verbatim
(`ui/tabs/tab_print.py:1741-1745`):

> "Borderless is enabled - the driver enlarges the page a few percent to reach
> past the paper edges, so the chart will NOT print at 100% and patches shift.
> **Print with borders instead.**"

So in one release we would ship a chart that says "print borderless" and an app
that pops a warning saying "don't". Whichever the user obeys, they were told the
other thing by us. This is the single most likely support ticket in the release.

Nelson is not wrong: he qualifies it with *"NO expansion, retain size"*, which
is the Canon/Epson "Amount of extension: none" / "Retain size" borderless mode
that does not scale. ChromIQ's warning knows nothing about that mode and fires
on `_borderless_selected(selected_opts)` unconditionally.

Measured, the geometry says the borderless advice is right for these sheets:
non-white ink reaches within **0.99-1.55 mm** of the sheet edge on the 648p and
**1.34-1.62 mm** on the 600p (C7f). A bordered 4x6" print centres the 100x150
image on a 101.6x152.4 page and then loses the printer's ~3 mm hardware margin,
so the crop marks, part of the header line and **the "Patch sampling and layout
design by Nelson Lau (c) for ChromIQ" credit down the right edge** are clipped.
The patches themselves survive (nearest patch edge is 4.89 mm in), so the chart
still reads.

**What I would do**, in order of preference:

1. Ask Nelson/Basti to settle the wording. If "borderless with extension set to
   none" is the intended instruction, the preflight warning needs a second
   sentence for it, not a flat "print with borders instead".
2. If nobody wants to touch the shared warning this release: make the preset's
   own tooltip (`_prebuilt_tooltip`) say what the sheet says, so the user meets
   the instruction before the contradiction.
3. Do **not** ship it silently and hope.

### C9 — a printed typo on all three pages of the 648p chart.

The 648p header reads `photo card -print wiith borderless setting`: "wiith" for
"with", and a missing space after the hyphen. Confirmed on pages 1, 2 **and** 3
by reading the rendered band; the 600p header is clean. Baked into the raster,
so it cannot be fixed after we ship it - only a regenerated bundle from Nelson
fixes it. Ask before integrating.

(For context I also read a shipped chart, `i1pro/a4/extended1944_01.tif`: it
carries the same ChromIQ logo and the same "Patch sampling & design by Nelson
Lau (c)" credit down the left band, so **the credit is precedent, not new** -
that part of question G is a non-issue. What is new is the borderless
instruction and the dropped "ChromIQ" prefix in the header's house style.)

---

## B. THE USER JOURNEY, STEP BY STEP

### C10 — printing: nothing in ChromIQ assumes A4, and the mismatch check will NOT false-alarm. This part of the plan is fine.

* Page size comes from the **printer's PPD**, not from the chart:
  `ui/tabs/tab_print.py:1674-1687` picks whichever `_PAGE_SIZE_KEYS` option the
  user selected and asks `PrintManager.get_page_size_points`
  (`workflow/print_manager.py:651-666`), which reads `*PaperDimension` from the
  PPD. `PostScriptGenerator.generate` defaults `page_size_pt` to the TIFF's own
  size (`workflow/postscript_generator.py:103-107`), so a 1417x2126 px @ 360 dpi
  page is 100.0 x 150.0 mm exactly.
* `check_size_mismatch` (`workflow/page_geometry.py:184`) allows an 8 % slack
  against the full sheet. 100x150 vs 4x6" (101.6 x 152.4) is 1.6 % on both
  axes; 130x180 vs 5x7" (127 x 177.8) is 2.4 % / 1.2 %. **No false warning**,
  and a user who leaves A4 selected DOES get the warning. Correct on both sides.
* Anything on an A4 assumption: none found in the print path.

The gap is not the geometry, it is the **advice** - see C8.

### C11 — the TIFF preview is safe: it reads the page's own dpi.

`ui/tiff_preview.py:1087-1120`: `_current_page_dpi` reads the resolution out of
each page TIFF (`workflow.margin_inspector._tiff_dpi`) and only falls back to
`self._coord_dpi`. The docstring at `:1108-1111` records the exact bug this
fixed (a 200 dpi chart read as 300 put an A4 corner at 140x198 mm). 360 dpi is
honoured, so the mm readout, the 33 mm instrument-body circle and the margin
guides are all to scale on a 100x150 page. No fixed page assumption found.

### C12 — measurement: nothing reads the paper, and the instrument handshake works.

`ui/tabs/tab_measure.py:4067-4137 _refresh_bidir_autodetect` reads
`TARGET_INSTRUMENT` from the run's `.ti2` and resolves `-b`/`-B` from it. Both
bundles carry `"GretagMacbeth i1 Pro"`, so an i1Pro chart gets forced
bidirectional reading, which is what a `RANDOM_START` chart wants. Nothing on
the Measure tab reads a paper size. Fine.

### C13 — the derived geometry, #66 and the scanner target all work on these bundles. Verified by running the shipped code.

```
600p  patch size (TabChart._chart_patch_size_mm) = 7.599 x 7.267 mm, pitch 0.0
648p                                            = 8.001 x 7.620 mm, pitch 0.0
has_scanner_geometry -> True for both
build_scanin_target_from_paths -> 600 patches / 4 pages, 648 patches / 3 pages
```

`comparable_presets` (`ui/tabs/tab_chart.py:2450-2475`) walks
`BUILTIN_PRESET_GROUPS` and takes any key whose `_builtin_ti1_asset` resolves,
so the two new rows appear in #66 "Compare with profile" with **no extra
wiring** - the plan is right to say nothing about it. Likewise
`builtin_recipe_choices`: prebuilts carry no `recipe.json`, so
`tests/test_prebuilt_presets_offer_no_setup.py` keeps passing and the
"Load setup from preset" tooltip stays true.

### C14 — reopening the project shows a paper size that does not exist. Precedent, but cheap to fix, and I would fix it.

`ui/tabs/tab_chart.py:11282-11286`: when a saved project's chart is reflected
back into Create Chart, the panel is seeded with
`ChartSpec.from_ti2(...).paper_flag`, which comes from
`workflow/ti2_relayout.py:192-201 paper_to_flag(PAPER_SIZE)`. The bundles carry
`PAPER_SIZE "120.0x195.0"` and `"135.0x225.0"`, so the panel will read
**Custom, W 120, H 195** for a 100x150 card.

The plan is right that this is precedent (`i1pro/a4/tc918eg` says 192x360 for an
A4 sheet, and shows Custom 192x360 today). But the plan draws the wrong
conclusion from it. `PAPER_SIZE` is a CGATS header keyword read by **exactly one
function in the app** (grepped: `workflow/ti2_relayout.py:251` is the only
reader) and by **nothing** in chartread - the physical layout lives in
`SAMPLE_LOC` / `STEPS_IN_PASS` / `PASSES_IN_STRIPS2`. Rewriting the two header
lines to `"100.0x150.0"` and `"130.0x180.0"` at integration time is a two-line,
zero-risk change that makes the reopened panel tell the truth, and it does not
invalidate `derive_layout_from_render` (which takes `paper_mm` from the TIFF -
verified: it returned `[100.0, 150.0]` and `[130.0, 180.0]`).

**Do it, and tell Nelson so his generator stops emitting the wrong value.**
Do not "leave it because the old ones are wrong too".

---

## C. THE OVERRIDE / RE-LAYOUT PATH

### C15 — measured: unlocking "Edit page layout" and pressing Generate gives 7 pages instead of 4, and the info box says "1 page" while it does it.

The routing is `ui/tabs/tab_chart.py:13019-13034`: printtarg signature changed
-> `_generate_from_ti1(bundled_ti1)`. Only `-i` and `-p` were seeded by
`_apply_prebuilt_preset` (`:11765-11766`); every other printtarg knob is the
user's own default, i.e. the app's i1 preset `m10_a0.95`
(`data/patch_db.py:I1PRO_DEFAULT_PRESET_KEY`).

Run against the real bundled `.ti1`s with the shipped Argyll 3.5.0:

| what the user gets | pages |
|---|---|
| the bundle, untouched | **600p: 4** / **648p: 3** |
| re-laid out on the right sheet (`-p100x150` / `-p130x180`, `-a0.95 -m10 -L`) | **7** / **4** |
| re-laid out with today's unknown-folder fallback (`-pA4`) | **2 A4 sheets** |

The 7-vs-4 gap is not a bug, it is physics: Argyll's i1 branch sets
`plen = pscale * 10.00 mm` (`target/printtarg.c:2137-2200`) and Nelson's patches
are 7.27 mm long, i.e. `-a0.727`. **printtarg cannot reproduce this bundle at
any setting ChromIQ's UI suggests.** A user who unlocks the layout gets a
completely different chart, and there is nothing on screen that says so in
numbers.

**Two honest gaps here, both fixable cheaply:**

1. **The page count in the info box is a lie on this path.**
   `ui/tabs/tab_chart.py:5393-5395` builds `notes` from
   `self._manual_pages_spin.value()` - a spin box, not a computed count - and
   `:5443-5448` pastes it into *"Built-in preset - re-laid out ({notes})"*. So
   the box reads "re-laid out (1 page)" for a run that will emit seven. On the
   normal targen path the pages spin is an input and this is fine; on the
   re-lay-out-a-fixed-.ti1 path it is meaningless. Either drop the page note in
   that branch or compute it.
2. **Nothing warns that the preset's geometry is unreachable.** The sentence
   *"Re-arranges the preset's exact patches on the page (targen skipped)"* is
   true and useless. One extra clause - "your printtarg settings will not
   reproduce this chart's patch size" - would cost nothing.

Neither is a blocker (the user opted in by ticking an override box that already
raises a warning `InfoDialog`), but item 1 is a wrong number on screen, which
this project treats seriously elsewhere.

### C16 — and with the plan's option (c)/(current fallback), the same click quietly produces an A4 chart for a 10x15 card. Measured above: 2 A4 pages. That is the strongest argument for C2/option (d) and against leaving `_prebuilt_paper_code` to fall through to `"A4"`.

---

## D. NAMING + UI CONSISTENCY

### C17 — the sanitiser is fine. Tested, not assumed.

```
FileManager._sanitise("i1Pro-10x15cm-600p-4pages-photo card by Pharmacist")
  -> "i1Pro-10x15cm-600p-4pages-photo-card-by-Pharmacist"   (50 chars, 50 bytes)
ui.dialogs.name_prompt.validate(...) -> None   (accepted; cap is 120 UTF-8 bytes)
```

The `x` survives (`core/file_manager.py:3372` keeps `isalnum()`), spaces become
hyphens, and - better than the existing rows - **there is no dot in the name**,
so the `core/stem_paths.py` trap (`Path("X-w10.0mm").suffix == ".0mm"`) does not
apply. Nothing to fix.

### C18 — but "10x15cm" is not the vocabulary the app itself uses for that sheet, and "photo card" duplicates the paper token.

Two separate problems with the proposed labels.

**(a) the paper token.** `TabChart._paper_name_and_orientation`
(`ui/tabs/tab_chart.py:9074-9092`) is what builds the #68 auto-name, and for a
custom size it returns the code verbatim: `"100x150"`, not `"10x15cm"`.
`paper_name_token("100x150")` likewise returns `"100x150"`
(`data/patch_db.py:258-260`, "custom WxH or unknown - already safe"). So a user
who re-generates a chart for this sheet gets a suggested name containing
`100x150` while the preset gave them `10x15cm`. Pick one. I would use
`10x15cm` in the **display label** (it is the name on the packet, and the label
is prose) and `100x150` in the **default target name** (it is a filename and
should match what the app generates).

**(b) "photo card" is the media, not the colour set.** Every existing prebuilt
label ends with a set name: `ABW-optimized`, `TC9.18 extended greys`, `TC3.00`,
`TC9.24`, `extended target`. `10x15cm-600p-4pages photo card` says the media
twice. And these really are two **different** colour sets, not one set at two
sizes - measured: only **256** device values are shared between the 600 and 648
patch sets, and the neutral ramps differ (600p: 21 steps at 5 % intervals;
648p: 24 steps at 4.348 % intervals). Neither overlaps `extended1944`
meaningfully (58 / 76 shared). So they deserve either two real set names from
Nelson, or none at all (the Knut families carry none:
`A4-204p-1page-Portrait-w10.0mm`). "photo card" on both is the worst of the
three options - it implies they are the same family and says nothing.

### C19 — where else the name surfaces, including one the plan misses.

* `_prebuilt_tooltip(_prebuilt_paper(key))` - `ui/tabs/tab_chart.py:7852,7931`.
  Needs the second map fixed (C4).
* The ★ overlay row - `BUILTIN_PRESET_GROUPS`'s second column,
  `ui/builtin_preset_popup.py` via `_marked_overlay_label`
  (`tab_chart.py:2441-2447`; its docstring says "the nine prebuilt ... rows" and
  would become stale).
* The name prompt's default - `_builtin_default_name`
  (`tab_chart.py:7915-7923`).
* **THE SHEET ITSELF.** `_active_layout_name` (`tab_chart.py:12018-12019`)
  returns `PREBUILT_PRESETS[key][1]` - the **default target name** - and it is
  stamped onto the TIFF as "Chart layout &lt;name&gt;" (#70). So the default name
  is not just a folder suggestion; on any re-layout it is printed on paper.
  A 50-character name is the same length as the existing `extended1944` one, so
  this is a constraint, not a defect - but it is a reason not to make the name
  longer than it already is.
* #66 "Compare with profile" (`comparable_presets`, `tab_chart.py:2450`) and
  the exports / i1Profiler sidecars, which key off the run stem, i.e. the
  sanitised name. Both follow automatically.
* `docs/dev_builtin_presets.md`'s table (which already says "the ten ... charts"
  at line 18 while shipping nine - fix that while you are in there).

---

## E. TESTS THAT WILL BREAK (grepped, exact)

| file:line | assertion | what it becomes |
|---|---|---|
| `tests/test_the_marker_follows_the_editable_design.py:27` | `len(tc.BUILTIN_PRESET_KEYS) == 150` | **152** |
| `tests/test_the_marker_follows_the_editable_design.py:28` | `len(tc.PREBUILT_PRESETS) == 9` | **11** |
| `tests/test_the_marker_follows_the_editable_design.py:30` | `135 + 6 + len(PREBUILT_PRESETS) == 150` | `== 152` |
| `tests/test_knut_preview_geometry.py:18-27` | `BUNDLES` = literal list of 9 asset stems; every one parametrises `test_bugC_every_prebuilt_bundle_reports_its_true_patch_size` and the margin-guide tests | add both leaves, or the new bundles are **untested by the geometry suite** |
| `tests/test_layout_from_render.py:93-95` | `@parametrize("leaf", ["rgb/colormunki/a4/tc300", "rgb/i1pro/a4/abw1110"])` | a sample, not a sweep - add at least one new leaf so a missing `channels.json` fails |
| `data/i18n/parameters.*.yaml` x13 via `tests/test_i18n.py:140` | label-count parity for `-p` | **only if** plan option (a) is taken (see C5). Option (d) touches none of these. |

Not affected, checked: `tests/test_editor_recipe_persistence.py:232`
(`len(starred) == 2+6+45+24+19+19+20`) counts only built-ins with a
`recipe.json` sidecar; prebuilts have none, so it stays at 135.
`tests/test_prebuilt_presets_offer_no_setup.py` has no count assertion (it
explicitly refuses to hard-code one - `:50`), and it stays green as long as the
new bundles ship **no** `recipe.json`.

Stale prose to fix in the same commit: `docs/dev_builtin_presets.md:18` ("the
ten ... charts", already wrong at nine), `:75` (the table),
`ui/tabs/tab_chart.py:2445` ("The nine prebuilt"),
`tests/test_prebuilt_presets_offer_no_setup.py:6,8` ("nine charts").

---

## G. RELEASE-EMBARRASSMENT SWEEP

### C20 — the licensing note in THIRD-PARTY-NOTICES.md is already untrue about the Pharmacist charts, and these two would widen the gap.

`THIRD-PARTY-NOTICES.md:224-230` says of `assets/charts/`:

> "patch sets generated by ArgyllCMS `targen` from recipes in this repo. **Each
> carries the recipe that made it** (`recipe.json`, or the
> `CHROMIQ_SET_RECIPE` keyword), so they are **reproducible outputs of the
> workflow rather than copied data**."

Checked: **zero** of the nine `assets/charts/pharmacist/**.ti1` files carry
`CHROMIQ_SET_RECIPE`, and none has a `recipe.json` - the project's own test file
says so out loud (`tests/test_prebuilt_presets_offer_no_setup.py:5`: *"They
arrived as finished patch-set files with no design behind them"*). Nelson's two
new `.ti1`s carry no `CHROMIQ_SET_RECIPE` either. So the sentence that carries
our copyright argument for the whole `assets/charts/` tree does **not** describe
the eleven files that are somebody else's work, and every one of them prints
**"Patch sampling and layout design by Nelson Lau (c) for ChromIQ"** on the
sheet.

That document also names Knut explicitly as a contributor of recipes and does
**not** name Nelson at all. And the file count in it (`277 files`) is already
stale - `find assets/charts -type f` says **331** today, and would say 338.

**This is a paperwork blocker, not a legal opinion.** The fix is small: add a
line naming Nelson Lau and the permission basis (his own message granting
ChromIQ the right to ship them), correct the "each carries its recipe" sentence
to except the prebuilt bundles, and update the count. The document already has a
"Still open" section for exactly this kind of item.

### C21 — PyInstaller: nothing to do. `ChromIQ.spec:169` is `('assets', 'assets')` - the whole tree. New leaves ship automatically. Size: +1.4 MB against 22 MB of `assets/charts` (12 MB of it already pharmacist). Not a concern.

### C22 — the i1Pro 3 Plus / ColorMunki user is protected by convention, not by code. That is unchanged, and acceptable.

The chart's own header says **"i1Pro 1/2/3"** (read off the raster), the group
heading is `INSTRUMENT_LABELS["i1"]` = "i1Pro / i1Pro 2 / i1Pro 3", and Knut's
3 Plus charts sit in their own `_P3_GROUP` for exactly this reason
(`docs/dev_builtin_presets.md`, "It is deliberately its own group ... offering
them to an i1Pro 1/2/3 owner under 'i1Pro' would hand them a chart their
instrument cannot read comfortably"). So a 3 Plus owner has to cross a group
heading to pick one.

There is **no runtime guard**: `TARGET_INSTRUMENT` is `"GretagMacbeth i1 Pro"`
for both devices (`workflow/ti2_relayout.py:165-172` says printtarg stamps the
3 Plus the same way), so `_refresh_bidir_autodetect` cannot tell them apart and
nothing warns. A 3 Plus reading a 7.27 mm patch will simply fail. **This risk is
identical to the nine charts already shipping** and the new ones are not worse -
they are the smallest patches yet (7.27 mm vs the previous floor of 7.48 mm), so
if anything the case for a guard gets stronger, but it is a separate piece of
work and not this release's.

### C23 — the spacer, 0.564 mm: the facts document is right to flag it and right not to block on it, but the plan then never actually raises it.

0.564 mm at 360 dpi is **8 pixels**, 34 % below the smallest that has ever
shipped (0.85 mm) and 47 % below `abw1110`'s 1.06 mm. Argyll's own i1 branch
nominates `pspa = pscale * sscale * 1.00` mm. Verification 3 in the facts doc
shows the spacers are correctly contrast-chosen black/white, so chartread has
the transitions it needs *in the raster* - but the raster is not what chartread
reads. **A printer is.** 8 pixels of ink at 360 dpi, on glossy photo card, with
dot gain, is the thing most likely to close up and merge two patches. That is a
question for somebody with the paper and the instrument, and it is the one
question in this whole integration that a code review cannot answer.

**The plan's step 9 ("Drive the real app on screen end to end") does not cover
it, because driving the app does not print anything.** Somebody has to print one
sheet of each and read it. Say so in the plan.

---

## H. THE IMPLEMENTATION IS ALREADY IN THE WORKING TREE — reviewed as built

Noticed while checking the branch state: `git status` on
`feature/nelson-photocard-presets` (off master `7e500e59`) already carries
+102 lines in `ui/tabs/tab_chart.py`, a `docs/index.html` 150 -> 152 edit, and
both asset leaves staged as `.../i1pro/100x150/photocard600/` and
`.../i1pro/130x180/photocard648/`, each with a `channels.json`. So this
"challenge the plan" round is running behind a build that has already started.
Flagging it because this project's own memory has a note about exactly that
(*"a decision list is NOT a build order"*), and because a reviewer who
challenges the plan while the code moves under them reviews the wrong thing.
The rest of this section reviews what is actually there.

### C24 — the build independently chose option (d) (C2) and corrected the `.ti2` PAPER_SIZE (C14). Both good, both verified by running the shipped code.

```
TabChart._prebuilt_paper_code(PHOTOCARD600) -> "100x150"
_prebuilt_paper(PHOTOCARD600)               -> "10 × 15 cm (100 × 150 mm)"
_set_manual_value("printtarg","-p","100x150")
   -> combo data "custom", W 100, H 150; ParameterWidget.get_value() == "100x150"
   -> _printtarg_signature() stable across a re-seed  (so Generate COPIES, correct)
```

Staged `.ti2` headers now read `PAPER_SIZE "100.0x150.0"` / `"130.0x180.0"` -
the true sheet, not Nelson's 120x195 / 135x225. That is the C14 fix, already
done. `re` is imported (`tab_chart.py:5`), so the new module-level
`re.compile` is safe at import time.

### C25 — but the residual risk of option (d) is NOT covered, and the new presets are the first thing in the app that puts a custom paper on screen by default.

C1's `_binary_search` bug is still live and is now one override-checkbox away.
`ChartCreator.estimate_patches` (`workflow/chart_creator.py:869-888`) asks
`query_patches` first; a custom `WxH` paper is not in any table, so it falls to
`_binary_search`, which returns **443** for both sheets. Concretely: tick
"Edit patch recipe", leave **Auto patch count** on (its default), press
Generate, and the log prints `Auto patch count: 443` and builds a 443-patch
chart for a card that holds ~90.

`_refresh_layout_estimate` (`tab_chart.py:5613`) bails unless the layout engine
is on, so the preview never triggers a live search - good, no UI freeze. It is
only the Generate path.

**One-line fix, and I would take it in this commit**: in
`chart_creator._binary_search`, when the loop ends with `best == 0`, retry once
with `lo = 20` (or just start `lo` at 20 and pay ~2 more probe steps). Today
that branch logs `_binary_search found no valid capacity in [221, 1107]` and
returns the estimate it just failed to validate - a wrong number, silently,
from a function whose whole job is to be right.

### C26 — the tooltip note (`PREBUILT_PRESET_NOTES`) is good and its numbers check out, but it does not close C8.

I re-measured the numbers it quotes and they are right (`1.0-1.6 mm` on the
13x18 top/bottom, `1.3-5.0 mm` on the 10x15; patches 12 mm from the bottom,
5-7 mm from the right). The advice is sound and the comment above it is honest
about the conflict.

It still leaves the user meeting **three different instructions**:

| where | what it says |
|---|---|
| the printed sheet | "print with borderless setting / NO expansion, retain size" |
| the preset tooltip (new) | "borderless with expansion off if you can; otherwise borders" |
| the print preflight, `ui/tabs/tab_print.py:1741` | "Borderless ... **Print with borders instead.**" |

The tooltip is read once, at preset selection. The preflight fires at the moment
of printing, in a modal, in red. **The preflight is the one the user will
obey**, and it is the one that contradicts the sheet. Adding one clause to that
warning ("...unless your driver can turn page expansion off, in which case
borderless at exact size is fine") makes all three agree and costs one string +
one German entry.

Also: `PREBUILT_PRESET_NOTES` is **not** wrapped in `tr()`, so a German user
gets it in English. That matches the existing `_prebuilt_tooltip` body (also
untranslated), so it is consistent rather than a regression - but this is the
first tooltip text that carries *print instructions* rather than a description
of the mechanism, and it is the one worth translating.

### C27 — the label ordering comment claims a rule that is not this group's rule.

The new comment says *"Smallest sheet first ... (Knut's rule for this group:
paper, then patch width, then count)"*. The line it replaced said
*"A4 first (ascending patch count), then US-Letter - keep paper grouped"*, and
the Pharmacist block is ordered A4-1110, A4-1160, A4-1944, Letter-1160,
Letter-1944, i.e. **paper, then count** - no patch width anywhere (these
bundles do not store one, which is why the labels omit it, per
`docs/dev_builtin_presets.md:70-72`). Putting the photo cards first is a fine
choice; attributing it to a rule Knut set for the *Knut* families, in a comment
on the *Pharmacist* block, will mislead the next person. Say "smallest sheet
first" and stop.

### C28 — measured red: exactly one test fails today, and it is the one predicted.

```
tests/test_the_marker_follows_the_editable_design.py::test_the_marker_counts_are_exactly_135_6_and_9
  assert len(tc.BUILTIN_PRESET_KEYS) == 150   ->  152
```
36 other tests in `test_prebuilt_presets_offer_no_setup.py`,
`test_knut_preview_geometry.py` and `test_layout_from_render.py` pass, and
`test_i18n.py` + `test_no_new_em_dash_in_user_facing_text.py` are green (93
passed) - so option (d) really did cost zero i18n work, which was its point.

Note the test's **name** encodes the counts too
(`test_the_marker_counts_are_exactly_135_6_and_9`); rename it, or it lies from
the day it is edited. And `test_knut_preview_geometry.py:18-27 BUNDLES` still
lists nine - the new bundles are currently **outside** the geometry suite.

### C29 — re-checked after the tree moved again (labels, docs and tests were updated while this review ran)

Now on disk: label `"★  i1Pro · 10x15cm-600p-4pages by Pharmacist  ·  built-in"`
(the redundant "photo card" dropped), default name
`"i1Pro-100x150-600p-4pages by Pharmacist"` (the #68 token, `100x150`) — i.e.
exactly the split C18 asks for. `docs/dev_builtin_presets.md` is at eleven with
both rows in the table, and a new `tests/test_photocard_builtin_presets.py`
pins sheet size, patch/page/strip counts, `.ti1` vs `.ti2` identity, full final
strips, and the custom `-p` seeding. **28 passed**, and the count pin in
`test_the_marker_follows_the_editable_design.py` is green again.

Still open at the time of writing:

* **The "wiith" typo is still in the staged asset** —
  `assets/charts/pharmacist/rgb/i1pro/130x180/photocard648/photocard648_01.tif`,
  read off the raster just now. C9 stands.
* **`ui/tabs/tab_print.py` is untouched**, so C8/C26's three-way contradiction
  is unresolved.
* **`THIRD-PARTY-NOTICES.md` is untouched**, so C20 stands.
* **`workflow/chart_creator.py` is untouched**, so C25 stands.
* The ordering comment still attributes "paper, then patch width, then count"
  to this group (C27).

---

# PRIORITISED SUMMARY

## BLOCKERS (do not tag 4.2.1 with these open)

1. **C8 / C26 — the sheet says "print with borderless", the app's print
   preflight says "Print with borders instead."** One of the two has to move, or
   we ship a self-contradiction on the most-clicked modal in the workflow.
   Cheapest honest fix: one clause on `ui/tabs/tab_print.py:1741`.
2. **C20 — `THIRD-PARTY-NOTICES.md` does not describe these files.** Its
   `assets/charts/` paragraph claims every chart "carries the recipe that made
   it" and is a "reproducible output of the workflow"; none of the eleven
   Pharmacist bundles does, all of them print a third-party copyright notice on
   the sheet, and Nelson Lau is named nowhere in that document. Add him and the
   permission basis, and correct the sentence and the file count (277 -> 338).
3. **C9 — a spelling mistake baked into the raster of all three pages of the
   648p chart** ("wiith"). Unfixable after release; ask Nelson for a corrected
   bundle before it ships, or ship the 600p alone.
4. **C23 — nobody has printed and read one of these sheets.** The 0.564 mm
   spacer is 34 % below anything ChromIQ has ever shipped and 8 pixels at
   360 dpi. Driving the app on screen (plan step 9) cannot test it. One printed
   sheet of each, read on an i1Pro, before the tag.

## SHOULD-FIX (in this change set)

5. **C25 / C1 — `_binary_search` returns 443 patches/sheet for a 100x150 card.**
   Reachable in one click from the new presets (unlock recipe + Auto patch
   count). Fix the lower bound in `workflow/chart_creator.py:2098`.
6. **C15 — the info box says "re-laid out (1 page)" for a run that emits 7.**
   `notes` is built from the pages spin box, which means nothing on the
   re-lay-out-a-fixed-`.ti1` path.
7. **C27 — the group-ordering comment attributes a rule to Knut that this group
   does not follow.**
8. **C6 — if anyone still wants the sizes in `PAPER_SIZES`, `ENGINE_EXCLUDED_
   PAPERS` needs the p3 entry too**, and the paper would need measured capacity
   rows (C1). My recommendation is: don't; option (d) as built is better.

## NICE-TO-HAVE

9. **C26 — translate `PREBUILT_PRESET_NOTES`.** It is the first prebuilt tooltip
   that carries *print instructions* rather than a description of the mechanism.
10. **C7b — 2 white / 2 black patches**, against 4/4 everywhere else in ChromIQ.
    Ask Nelson whether that is deliberate for a 600-patch chart.
11. **C22 — no runtime guard stops an i1Pro 3 Plus owner picking a 7.27 mm-patch
    i1Pro chart.** Pre-existing for all eleven bundles; these are just the
    smallest yet. Separate piece of work.
12. **C5/C14 for the SHIPPED bundles** — the nine existing `.ti2`s still carry a
    `PAPER_SIZE` that disagrees with their own sheet (`192.0x360.0` for A4), so
    reopening one of those projects shows "Custom 192 × 360". The new two were
    corrected; the old nine could be, the same way, at zero risk.
13. **Aside, unrelated to this task:** the shipped
    `colormunki/a4/abw702` bundle fails `analyze_randomisation` (`safe=False`)
    while the other eight and both new ones pass. Someone should look at it.

## WHERE THE PLAN WAS RIGHT

* ACCEPT both bundles as prebuilt-files built-ins — yes. Every structural check
  I could run independently passes (C7a-e, C13).
* Reject option (b) (map to 4x6 / 5x7) and option (c) (fall through to A4) —
  yes, and C16 measures exactly what (c) costs: 2 A4 sheets for a 10x15 card.
* Asset folder / stem convention, the `BUILTIN_PRESET_GROUPS` single-registry
  wiring, `derive_prebuilt_geometry.py`, and "nothing needed for #66 / the
  PyInstaller spec" — all correct, all verified.
* The plan's option (a) was the wrong first choice, but the plan was right that
  (b) and (c) were worse, and the build found (d) on its own.
