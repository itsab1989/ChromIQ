# ADVERSARIAL REVIEW OF THE BUILT CHANGE SET — `feature/nelson-photocard-presets`
Reviewer: second adversarial pass, this time on the CODE as committed
(`2555c018`, `c24f15d9`, `1dec7035` off master `7e500e59`).
Everything below is CONFIRMED (reproduced here) or SUSPECTED (reasoned, not run).
Findings are appended in the order they were confirmed.

---

## R1 — CONFIRMED, NO REGRESSION: all nine shipped bundles resolve exactly as on master

`_prebuilt_paper` / `_prebuilt_paper_code` (`ui/tabs/tab_chart.py:360`, `:10938`)
were rewritten. I ran BOTH versions in separate interpreters (a `git worktree`
of master `7e500e59` against this checkout) and dumped every key:

| preset | master paper / code | HEAD paper / code |
|---|---|---|
| abw1110, abw702, tc300, tc918eg_a4, ext1944_a4 | `A4` / `A4` | identical |
| ext1944_letter, tc918eg_letter | `US Letter` / `Letter` | identical |
| tc918eg_cm_a3 (a3plus) | `A3+` / `329x483` | identical |
| tc924_cm_a3 (a3) | `A3` / `A3` | identical |

Nine of nine byte-identical. I also probed 20 synthetic folder names and 6
malformed asset stems (`""`, `"a"`, `"a/b"`, `"a/b/c"`, missing key): every
non-`WxH` name and every malformed stem returns exactly what master returned,
including the `""`→`A4` and `"a/b/c"`→`A` oddities. **The only behaviour that
changed is for folders matching `^\d+xd+$`, and no such folder existed on
master.**

`_prebuilt_tooltip` grew a second parameter with a default of `""`; it has
exactly ONE production call site (`tab_chart.py:8024`) plus the new tests, and
the two-arg / one-arg forms are pinned equal by
`test_photocard_builtin_presets.py:276`. No stale call site anywhere.

## R2 — CONFIRMED, THE `_binary_search` FIX IS CORRECT AND COSTS AT MOST ONE PROBE

Ran the real `ChartCreator._binary_search` against the real Argyll 3.5.0 on both
checkouts, instrumenting `_probe` to count and record every probe:

| case | master | HEAD | probes m→h | secs m→h |
|---|---|---|---|---|
| i1 / A4 / a0.95 | 528 | **528** | 10 → 10 | 8.8 → 7.7 |
| i1 / Letter / a0.95 | 550 | **550** | 10 → 10 | 8.8 → 7.8 |
| i1 / 4x6 / a0.95 | 100 | **100** | 8 → 8 | 1.9 → 1.8 |
| i1 / 127x178 / a0.95 | 169 | **169** | 9 → 9 | 3.0 → 2.8 |
| i1 / 203x254 / a0.95 | 460 | **460** | 10 → 10 | 7.5 → 6.8 |
| CM / A4 / a1.0 | 90 | **90** | 7 → 8 | 3.5 → 3.5 |
| i1 / A4 / a1.5 | 210 | **210** | 9 → 9 | 5.1 → 4.8 |
| i1 / A4 / a0.6 | 1368 | **1368** | 11 → 12 | 16.7 → 18.1 |
| i1 / 100x150 | 443 (bogus) | **90** | 9 → 10 | 4.9 → 3.2 |
| i1 / 130x180 | 443 (bogus) | **169** | 9 → 10 | 4.6 → 3.8 |

Every paper with a measured capacity row is unchanged to the patch. Worst probe
growth is **+1**; wall time is a wash. The two new sizes now return the numbers
`printtarg` itself gives (90 / 169). The `total_steps` progress denominator
(`chart_creator.py:2126`) still bounds the probe count in every case I ran
(12/12 at the worst), so the progress line does not overflow.

## R3 — CONFIRMED, SHOULD-FIX: the same lie is still there, just at a smaller sheet

The commit message says *"The patch count for an unmeasured sheet size was the
guess, not the answer"* and the CHANGELOG says the search *"started above the
real answer, found nothing, and reported the guess it had started from."*
It still does — the floor merely moved from `est*0.5` to the hard-coded `20`
(`workflow/chart_creator.py:2118`). Below 20 patches/sheet the function is
exactly as wrong as before, and the fallback is the SAME 443:

```
i1 / 60x90 mm / a0.95  ->  443     (probe at 20 patches = 2 pages)
i1 / 50x50 mm / a0.95  ->  443     (probe at 20 patches = 7 pages)
   WARNING _binary_search found no valid capacity in [20, 1107];
           falling back to scaled estimate 443
```

Both reached exactly the way the CHANGELOG says the old bug was reachable:
the `-p` "Custom (enter dimensions)" row. A 60 x 90 mm sheet is a real photo
size (2.4 x 3.5", the "wallet" print) and the app will tell its owner 443.

The honest ending for `best == 0` is not "return the estimate I just failed to
validate" — it is to report that nothing fits (the caller can then say so), or
at least to keep halving below 20. This is not a release blocker (the two
shipped presets are correct), but the change set claims to have fixed a class
of bug and fixed only the half of it that its own presets needed.

## R4 — CONFIRMED: `test_capacity_search_reaches_a_small_sheet.py` is REAL, and its parameter list stops one patch above the bug

Mutation, proved to land (`grep` on the source line after the edit):

```
workflow/chart_creator.py:2118   lo = 20   ->   lo = max(20, int(est * 0.5))
   FAILED test_the_search_finds_the_capacity_it_is_given[90]
   FAILED test_the_search_finds_the_capacity_it_is_given[169]
   FAILED test_the_search_finds_the_capacity_it_is_given[20]
   FAILED test_the_search_finds_the_capacity_it_is_given[45]
   FAILED test_a_small_sheet_no_longer_answers_with_the_guess_it_started_from
   5 failed, 4 passed
```

A second mutation (`hi = est * 2.5` -> `est * 25`) turns
`test_the_wider_window_costs_about_one_extra_probe` red on its own, so that one
is not decorative either.

**But the parametrize list is `[90, 169, 20, 45, 300, 504]` and 20 is exactly
the new floor.** Adding the next values down, with no other change:

```
   FAILED test_the_search_finds_the_capacity_it_is_given[19]   -> 443
   FAILED test_the_search_finds_the_capacity_it_is_given[12]   -> 443
   FAILED test_the_search_finds_the_capacity_it_is_given[5]    -> 443
```

So the suite's coverage of "the search reaches a small sheet" ends precisely
where the fix does (R3). That is not a false test, but the file's own title
promises more than the code delivers.

**One decorative assertion found.**
`test_a_known_paper_still_gets_its_measured_answer` says *"A4 for an i1Pro is a
measured 528 at -a0.95 -m10"* — but the probe is a `_FakeSheet(528)`, so 528 is
whatever the test itself put there. It cannot notice a change in
`data/patch_db.py`, in `est`, or in the real A4 capacity; it only re-tests that
a binary search converges, which the parametrized test already covers. Harmless,
but the docstring claims a guard it does not have.

## R5 — CONFIRMED: `test_photocard_builtin_presets.py` is real. Five mutations, five reds.

| mutation (verified landed in the file) | result |
|---|---|
| delete the `if _PREBUILT_CUSTOM_PAPER.match(paper): return paper` branch | 2 FAILED (`test_the_layout_panel_is_seeded_with_the_real_sheet`) |
| delete the two `100x150` / `130x180` rows from `_PREBUILT_PAPER_LABELS` | 4 FAILED (paper label + tooltip) |
| move the two rows to the END of the i1Pro group | 1 FAILED (`test_the_photo_cards_head_the_i1pro_group`) |
| restore `PAPER_SIZE "120.0x195.0"` in `photocard600.ti2` | 1 FAILED (`test_the_ti2_paper_size_agrees_with_the_sheet`) |
| remove `photocard600_04.tif` | 1 FAILED (`test_the_bundle_is_complete_on_disk`) |

All assets and sources restored; `git status` clean afterwards.

## R6 — CONFIRMED, the committed assets are good (I re-derived them, the facts doc measured the zips)

`00-facts-measured.md` ran `derive_layout_from_render` on the **unzipped working
copies**. The committed assets were then edited (`PAPER_SIZE` rewritten, files
renamed), so I re-ran the derivation on what is actually in git:

```
i1pro/100x150/photocard600  600 patches, paper_mm [100.0, 150.0], pages 0-3
i1pro/130x180/photocard648  648 patches, paper_mm [130.0, 180.0], pages 0-2
fresh derivation == committed channels.json   (byte-equal, both bundles)
```

## R7 — CONFIRMED GAP: nothing in the gate ever re-derives a bundle from its raster

`tests/test_layout_from_render.py:97 test_prebuilt_bundles_carry_verified_geometry`
gained the two new leaves — but read it: it only loads the **sidecar** and
compares its `loc` set against the `.ti2`. It never calls
`derive_layout_from_render`. Proof: removing `photocard600_04.tif` entirely
leaves that test **green** (only `test_the_bundle_is_complete_on_disk` caught
it, from the same new file).

So the check the project treats as the gate on a bundle ("the same gate that
once rejected the i1Pro/A4 tc924 bundle") runs only in
`scripts/derive_prebuilt_geometry.py`, by hand, at integration time. A
regenerated bundle whose raster no longer matches its `.ti2` ships green as long
as the stale sidecar is left in place. Pre-existing for all nine, now eleven —
not a regression, but the new file was the place to close it and did not.

## R8 — CONFIRMED ON SCREEN: "re-laid out (1 page)" for a run that emits SEVEN. C15 was deferred and it is worse than C15 said.

Driven in the real window (`MainWindow`, Manual, the preset picked through
`combo.activated` exactly as a click does, settings in a throwaway `.ini`):

```
after picking the preset, then ticking "Edit page layout" and nudging -a:

  Built-in preset — re-laid out (1 page · Auto patch count · Auto grey/white/black):
  Re-arranges the preset's exact patches on the page (targen skipped).
  printtarg -ii1 -p100x150 -t300 -a0.90 -m10 -M10 -c chart
```

That command, run against the bundled `.ti1` with the shipped Argyll 3.5.0:

```
Paper chosen is custom 100.0 x 150.0 mm
Test patches per row = 11 ; Rows per page = 8, patches per page = 88
Total pages needed = 7
```

**Seven, announced as one.** And C15 under-reported it: the `notes` string
carries THREE targen-only claims on a path where targen is skipped —
"1 page", "Auto patch count" and "Auto grey/white/black". All three are read off
targen widgets (`ui/tabs/tab_chart.py:5479-5495`) and none of them can affect
anything on this branch.

The `-p` itself is right (`-p100x150`), so the change set's own contribution
works. The lie is the page count next to it.

## R9 — the stale "Manual mode ... -pA4" info line right after a preset is picked is PRE-EXISTING, not a regression (checked against master)

Immediately after the preset applies and the chart is copied in, the info box
reads:

```
Manual mode — your current configuration (1 page · Auto patch count · Auto grey/white/black):
targen -d2 -f0 -e3 -B3 -G -g25 chart
printtarg -ii1 -pA4 -t300 -m10 -M10 -c chart
```

— i.e. it does not say a built-in is active, and it names `-pA4` while the
`-p` widget beside it already reads `100x150`. It refreshes to the correct
"Built-in preset — ready-made chart" text as soon as anything touches the panel.

**I ran the identical driver against a `git worktree` of master with the
`i1Pro · Letter-1944p` preset: byte-for-byte the same stale line, same `-pA4`.**
So this is old, and the change set neither caused nor worsened it. Recording it
because it is the closest thing on screen to "quietly saying A4", which is what
the CHANGELOG claims was fixed — a reader could reasonably test that claim, see
this, and conclude the fix did not land.

(For the record, an earlier probe of mine that called `_apply_prebuilt_preset`
directly instead of through the combo DID leave the `-p` widget at `A4`. That
was my harness, not the app: through the real `activated` path the widget holds
`100x150` / `130x180`, and `scripts/drive_photocard_presets.py` reports 0
mismatches. Stated so nobody re-derives the false alarm.)

---

# ⚠ THE BRANCH MOVED WHILE THIS REVIEW WAS RUNNING

Between R3 and R10 the branch was rebuilt: `2555c018`/`c24f15d9` became
`5a0cd98c`/`b2316b53` (same `1dec7035` base). R3 and R4's parameter-list point
were adopted. **Everything below is against the NEW head; R1-R9 above were
verified against the old one and I have re-checked which of them still stand.**

* R1, R5, R6, R7, R8, R9 — unaffected (no change to `ui/`, the assets or the
  other test files). Still stand as written.
* R2 — re-measured below (R10). Still holds, with the numbers updated.
* R3 — **ADOPTED AND FIXED.** See R10.
* R4 — **ADOPTED.** The parametrize list now runs down to 1, and the decorative
  A4 test was rewritten into a real one. Re-mutated below.

## R10 — CONFIRMED: the rewritten `lo = 1` fix is correct, and now the whole class is closed

Re-ran the real `_binary_search` against real Argyll 3.5.0 on the new head,
same instrumentation, and compared with the master run from R2:

| case | master | new HEAD | probes m→h |
|---|---|---|---|
| i1 / A4 / a0.95 | 528 | **528** | 10 → 11 |
| i1 / Letter | 550 | **550** | 10 → 11 |
| i1 / 4x6 | 100 | **100** | 8 → 8 |
| i1 / 127x178 | 169 | **169** | 9 → 9 |
| i1 / 203x254 | 460 | **460** | 10 → 11 |
| CM / A4 / a1.0 | 90 | **90** | 7 → 8 |
| i1 / A4 / a1.5 | 210 | **210** | 9 → 9 |
| i1 / A4 / a0.6 | 1368 | **1368** | 11 → 12 |
| i1 / 100x150 | 443 | **90** | 9 → 10 |
| i1 / 130x180 | 443 | **169** | 9 → 10 |
| i1 / 60x90 (R3's case) | 443 | **16** | – → 11 |
| i1 / 50x50 | 443 | 443, honest log | – → 10 |

Every measured paper is unchanged to the patch; the worst probe growth is +1,
which is exactly what the new source comment claims. The `best == 0` log now
names the real cause instead of blaming the search:

```
_binary_search: not even one patch fits on a single page of 50x50 for
instrument i1 (probed [1, 1107]) — the sheet is too small for this layout.
Returning the UNVERIFIED estimate 443
```

**What is still open, and the CHANGELOG now says so itself:** on a sheet where
not one patch fits, `estimate_patches` still hands the caller `est` (443), so
"Auto patch count" would build a 443-patch chart for a 50 x 50 mm card. That is
a message, not a number, and it is correctly deferred — but it IS still a wrong
number on screen, so it should not be forgotten.

## R11 — CONFIRMED: the rewritten capacity tests are real, both of them

| mutation (verified landed) | result |
|---|---|
| `lo = 1` → `lo = 20` (the version I reviewed as R3) | 5 FAILED: capacities 1, 5, 12, 16, 19 |
| `best = mid; lo = mid + 1` → `hi = mid - 1` (return the first fit, not the last) | 12 FAILED, including the rewritten `test_a_large_capacity_lands_exactly_and_not_one_short` |

The rewritten A4 test now guards a real property (the loop keeps the LARGEST
single-page probe) and its docstring says out loud that it does not guard
`patch_db`. R4's "decorative" finding is closed.

## R12 — CONFIRMED, SHOULD-FIX: `THIRD-PARTY-NOTICES.md` replaced one wrong file count with another

`THIRD-PARTY-NOTICES.md:224` now says **"`assets/charts/` (338 files)"**. The
tracked truth:

```
git ls-tree -r master --name-only assets/charts | wc -l   ->  317
git ls-tree -r HEAD   --name-only assets/charts | wc -l   ->  330
find assets/charts -type f | wc -l                        ->  331  (one stray .DS_Store, gitignored)
```

So it is **330**, not 338. The old value (277) was stale by 40; the new one is
wrong by 8 in the other direction. `02-challenge.md` C20 predicted *"331 today,
and would say 338"* — the implementer took the prediction instead of counting,
and that prediction was itself made with the new assets already in the working
tree, so it double-counted them.

The paragraph is otherwise a good, honest fix (Nelson named, the permission
basis quoted and dated, the "each carries its recipe" claim correctly excepted).
Nothing in the gate reads this number, which is why it rots.

## R13 — CONFIRMED, NICE-TO-HAVE: the landing page's `softwareVersion` still says 4.2.0

`docs/index.html:31` — `"softwareVersion": "4.2.0"` — the JSON-LD block Google
reads. It was bumped to 4.2.0 in the commit immediately before this branch
(`7e500e59`, whose subject is literally *"the site said 130 presets and a beta
CR30"*), and this change set bumps `core/version.py` to 4.2.1 without it.

The new `test_the_site_says_how_many_presets_there_really_are` pins the preset
count against the registry — good — but the version field beside it is pinned by
nothing, and it is the identical failure mode the new test's own docstring
describes ("the page advertises X by hand ... it has been wrong before").
`docs/index.html:363` also still offers `releases/tag/v4.2.0` as "get the beta".

## R14 — CONFIRMED: the printing contradiction (C8/C26) is still live, and the deferred modal makes TWO claims that are false about these two charts

`ui/tabs/tab_print.py` is not in `git diff master..HEAD --name-only`. The two
strings the user meets are unchanged:

`ui/tabs/tab_print.py:1609` (`_confirm_borderless`, a modal raised the moment a
borderless option is picked, with **Cancel as the default button**):

> "Borderless printing enlarges the page by a few percent so the ink reaches
> past the paper edges. The printer driver does this and **it cannot be turned
> off** — it is what borderless means. … Switch borderless off and print with
> borders instead — **the chart's white margins are made for that**."

`ui/tabs/tab_print.py:1741` (the preflight): *"… Print with borders instead."*

Both bolded claims are false for these two sheets specifically:

* **"it cannot be turned off"** — Canon and Epson drivers expose an
  extension/expansion amount that can be set to none, which is precisely what
  Nelson's printed instruction (*"print with borderless setting / NO expansion,
  retain size"*) tells the user to do.
* **"the chart's white margins are made for that"** — measured on the shipped
  rasters, ink reaches within 1.0-1.6 mm of the paper on the 13 x 18 and
  1.3-1.6 mm at the sides on the 10 x 15. These sheets have no such margins.
  The change set's OWN new tooltip says so in the opposite direction.

So the release ships **three** instructions on one screen path:

| where | says |
|---|---|
| the printed sheet (baked into the raster) | print borderless, no expansion |
| the new preset tooltip (`PREBUILT_PRESET_NOTES`) | borderless with expansion off if you can, otherwise borders |
| the print modal, default button = Cancel | borderless cannot be tuned; print with borders |

The tooltip is read once at selection; the modal fires at the moment of
printing, in red, and defaults to Cancel. **The modal is the one the user
obeys, and it is the one that contradicts the sheet.** One clause on
`tab_print.py:1609` would make all three agree.

## R15 — CONFIRMED: the print PATH itself is correct for these sheets (the geometry half of C10 holds on the built code)

`workflow/page_geometry.check_size_mismatch`, run directly:

```
100x150 chart on 4x6" media (101.6 x 152.4)   -> no warning   (1.6 % on both axes)
130x180 chart on 5x7" media (127 x 177.8)     -> no warning
100x150 chart on A4                           -> WARNS, correctly
130x180 chart on A4                           -> WARNS, correctly
```

One wrinkle for a beginner: the A4 warning ends *"Regenerate the chart for this
paper to be safe."* For a prebuilt bundle that advice is wrong twice over — the
chart cannot be regenerated (there is no recipe), and re-laying it out at the
app's own defaults gives 7 pages instead of 4. Generic, pre-existing text, but
these are the first presets where following it destroys the thing the user
picked.

## R16 — NICE-TO-HAVE, measured: the nine old bundles still claim a sheet that does not exist, and the two new ones now prove the field can be right

`ChartSpec.from_ti2` → `paper_to_flag(PAPER_SIZE)` is what the Create Chart
panel shows when a saved project is reopened. Run over all eleven:

| preset | tooltip says laid out for | `.ti2 PAPER_SIZE` | panel on reopen |
|---|---|---|---|
| abw1110 | A4 | 210.0x297.0 | A4 Portrait ✓ |
| tc918eg_a4 | A4 | 192.0x360.0 | **Custom 192x360** |
| tc918eg_letter | US Letter | **192.0x360.0** | **Custom 192x360** |
| tc300 | A4 | 297.0x210.0 | A4 Landscape ✓ |
| abw702 | A4 | 292.0x210.0 | **Custom 292x210** |
| tc924_cm_a3 | A3 | 475.0x305.0 | **Custom 475x305** |
| tc918eg_cm_a3 | A3+ | 495.0x329.0 | **Custom 495x329** |
| ext1944_a4 | A4 | 220.0x320.0 | **Custom 220x320** |
| ext1944_letter | US Letter | 220.0x320.0 | **Custom 220x320** |
| **photocard600** | 10 × 15 cm | **100.0x150.0** | **Custom 100x150 ✓** |
| **photocard648** | 13 × 18 cm | **130.0x180.0** | **Custom 130x180 ✓** |

Note the A4 and the US-Letter `tc918eg` carry the SAME `PAPER_SIZE`, which is
the clearest proof the field is currently noise. The resulting inconsistency is
only visible to someone who reopens one old and one new project, so it is not a
blocker — but it is now cheap and provably safe to correct the other seven the
same way, and the argument "leave it, the old ones are wrong too" no longer
holds now that two of them are right.

## R17 — CONFIRMED, LATENT TRAP: the new `<W>x<H>` rule collides with ChromIQ's own inch-named paper codes

`_PREBUILT_CUSTOM_PAPER = re.compile(r"^(\d+)x(\d+)$")` (`tab_chart.py:357`) and
`docs/dev_builtin_presets.md:92` both read a `<W>x<H>` folder as
**millimetres**. But four of `data/patch_db.PAPER_SIZES` are already spelled
that way and two of them are **inches**:

```
"4x6"      PAPER_LABELS -> '4×6" (102 × 152 mm)'
"11x17"    PAPER_LABELS -> 'Tabloid / 11 × 17"'
"127x178"  PAPER_LABELS -> '5×7" (127 × 178 mm)'   (mm, but named in inches)
"203x254"  PAPER_LABELS -> '8×10" (203 × 254 mm)'
```

Measured through the real functions with a synthetic asset stem:

```
folder "4x6"    ->  _prebuilt_paper "4 × 6 mm"       _prebuilt_paper_code "4x6"
folder "11x17"  ->  _prebuilt_paper "11 × 17 mm"     _prebuilt_paper_code "11x17"
```

The `-p` code is right (printtarg and `ParameterWidget` both take it, and the
combo even shows `4×6" (102 × 152 mm)` — verified), so nothing breaks. But the
TOOLTIP would tell the user the chart is laid out for a **4 by 6 millimetre**
sheet. Nothing ships in such a folder today, so this is a trap for the next
bundle, not a bug in this one — and the next bundle in this family is very
plausibly a 4x6" one, since that is the same photo paper.

Two-line fix while the memory is fresh: give `_prebuilt_paper` first refusal to
`data.patch_db.PAPER_LABELS` before falling through to "W × H mm".

## R18 — CONFIRMED: C27 was fixed in the source comment and RE-INTRODUCED in the test docstring

`ui/tabs/tab_chart.py:2485-2490` now says, correctly:

> "Smallest sheet first. That is all this block has ever done … **Not Knut's
> paper-then-width-then-count rule**, which belongs to the Knut families below"

`tests/test_photocard_builtin_presets.py:94`, in the same change set, says:

> """**Knut's rule for this group is smallest sheet first**, and these are the
> two smallest sheets ChromIQ has ever shipped a chart for."""

The two files now contradict each other about who set the rule, which is exactly
what C27 asked to avoid. One-line docstring fix.

## R19 — CONFIRMED: a stale count in a file this change set TOUCHED

`tests/test_knut_preview_geometry.py` gained the two new leaves in `BUNDLES`
(now eleven) but its docstrings were not swept:

* `:62` `"""All nine bundled presets are 360 dpi and none carries a recipe."""`
* `:69` `assert pitch == 0.0          # none of the nine is a honeycomb`

Everything else was swept correctly — I grepped the whole tree for
nine/ten/eleven next to prebuilt/pharmacist/bundle/chart and for
`N ready-made chart presets`, and found nothing else stale. In particular
`CHANGELOG.md:17`'s *"the way the other nine 'by Pharmacist' charts work"* is
RIGHT (eleven minus these two), and `docs/index.html`'s two `152` are right and
now pinned by a test.

One stale API reference: `docs/dev_builtin_presets.md:150` still documents
`_prebuilt_tooltip(paper)`, which grew a second parameter in this change set.

## R20 — CONFIRMED: what the beginner still cannot answer

Driven and read on screen. The preset answers:

| the question | where the app answers it |
|---|---|
| where do my files go | name prompt + tooltip ("copies … into a new folder under that name") ✓ |
| what paper do I load | the label `10x15cm` and the tooltip `10 × 15 cm (100 × 150 mm)` ✓ |
| how many sheets | the label `4pages` / `3pages` ✓ |
| will my printer clip the edges | the new `PREBUILT_PRESET_NOTES` paragraph ✓ (English only) |
| how many patches fit if I regenerate | now 90 / 169 instead of 443 ✓ |

and does NOT answer:

1. **"Why does the page size say *Custom*?"** Verified through the real widget:
   `set_value("100x150")` selects `Custom (enter dimensions)` and fills W 100 /
   H 150. Correct, and unexplained anywhere the user can see — the reasoning
   lives only in `docs/dev_builtin_presets.md`. A beginner reads "Custom" as
   "something went wrong". The tooltip has room for one clause.
2. **"What happens if I print it on A4?"** The preflight warns correctly
   (R15) and then advises *"Regenerate the chart for this paper to be safe."*
   For a prebuilt bundle that is impossible (no recipe) and re-laying it out
   gives 7 pages, not 4. The advice is generic, pre-existing and wrong here.
3. **"Borderless or not?"** Three answers, one of them a modal that defaults to
   Cancel. See R14.
4. **"Why did the page count change from 4 to 7?"** Nothing on screen says the
   preset's geometry is unreachable by any printtarg setting the UI offers. The
   info box says "1 page" (R8).

## R21 — NICE-TO-HAVE: the i1Profiler workflow export knows three papers, and none of them is a photo card

`ui/dialogs/tools_dialogs.py:197 _PWXF_PAPERS` is a literal
`{"A4", "A3", "US Letter"}`. A user who picks a photo-card preset and then uses
Tools → i1Profiler export gets an A4 workflow file for a 10 x 15 cm chart. It is
a separate tool keyed off a `.ti1`, not off the preset, and it was equally blind
to `4x6` / `127x178` before this change set, so it is not a regression — just
the one enumeration in section C that nobody could have updated without new
reverse-engineered `PaperFormat` values.

## METHODOLOGY NOTE — a stale `.pyc` faked a red gate, and the trap is worth recording

My first `--runslow`-tier run came back `12 failed`. The tree was clean, and
`inspect.getsource` showed the correct source. Cause: my own mutation
`lo = mid + 1` → `hi = mid - 1` is **byte-for-byte the same length**, and the
mutate → test → restore cycle finished inside one second, so
`workflow/__pycache__/chart_creator.cpython-314.pyc` still matched on
(source mtime in whole seconds, source size) and Python reused the MUTATED
bytecode. Proved by unpacking the pyc header:

```
pyc-src-mtime 1788868118  pyc-src-size 112383
actual mtime  1788868118  size         112383   => STALE-BUT-ACCEPTED
```

`rm -rf **/__pycache__` and the file is green again. Anyone mutation-testing
this repo should clear `__pycache__` after restoring, not just check
`git status`.

## R22 — THE GATE: green on the commit, RED on this machine, and the difference is not the change set

`QT_QPA_PLATFORM=offscreen pytest -n auto -q --runslow` at `5a0cd98c`, with a
**redirected `HOME`** so nothing could touch the owner's real folder:

```
11913 passed, 184 skipped, 3 xfailed in 202.99s (0:03:22)     EXIT=0
$HOME/ChromIQ was never created
```

The same command against the owner's **real** `HOME` came out:

```
11930 passed, 167 skipped, 3 xfailed, 12 errors in 211.91s    EXIT=1
```

All twelve are the same session-scoped guard,
`tests/conftest.py:858 _no_gate_run_may_rewrite_the_real_chromiq_folder`:

```
THIS RUN WROTE INTO THE REAL ~/ChromIQ FOLDER.
  rewritten: ['Youtube/runs/run1/meta.json']
```

and a slow-tier-only run reproduced a second variant, creating a whole
`~/ChromIQ/test/` project (the writer is
`tests/test_the_chart_path_survives_json.py`, which passes alone and writes
nothing alone — so it is cross-test contamination, not that file).

**This predates the branch, and I can date it:** `~/ChromIQ/test/old/` holds
archived copies from 2026-09-01, 09-02, 09-03 (x2 more), 09-04 and 09-05 —
every one before this branch was cut. It is the exact failure the guard's own
docstring describes ("`custom_output_path` then falls back to `""`, which IS
~/ChromIQ"), and the owner's real `custom_output_path` is indeed `""`.

Two things follow, and the second is the one that matters for the release:

1. **Nothing in this change set causes it.** Every test it adds or touches
   passes in both runs.
2. **The documented release gate cannot be run green on this machine.**
   `CLAUDE.md` says *"Any merge/release decision requires a green `--runslow`
   run"*. Anybody tagging 4.2.1 by that rule will get exit 1 and twelve red
   lines that have nothing to do with what they are tagging. Either the leak is
   found, or the tagger has to know to run with an isolated `HOME` — and that
   is not written down anywhere.

Also noticed while checking: `scripts/drive_guided_instrument_leaks_between_projects.py`
and `scripts/drive_youtube_cr30_shows_colormunki.py` are untracked in this
checkout — somebody else is working in the same tree, and `Youtube` is their
driver's project name. Some of the real-`HOME` noise is very likely theirs.
(`defaults read com.chromiq.ChromIQ custom_output_path` afterwards: `""`, the
owner's own value. Nothing of his was redirected by me.)

---

# PRIORITISED SUMMARY

Reviewed at `5a0cd98c` (the branch was rebuilt mid-review — see the banner above).

## BLOCKERS

1. **R14 — the app tells the user the opposite of what the chart tells them,
   in a modal that defaults to Cancel.** `ui/tabs/tab_print.py:1609` says
   borderless *"cannot be turned off"* and *"the chart's white margins are made
   for that"*. Both are false about these two sheets: the extension amount is
   settable on Canon and Epson drivers (which is what Nelson's printed
   instruction relies on), and these sheets have 1.0-1.6 mm of margin, not
   white margins made for a bordered print. The change set's own new tooltip
   says so. One clause on that string closes it; shipping without it means the
   first thing a photo-card user meets at print time contradicts the sheet in
   their hand. (This was C8/C26 and was deferred.)
2. **Nobody has printed and read one of these sheets.** The 0.564 mm spacer is
   34 % below the smallest ChromIQ has ever shipped — 8 pixels at 360 dpi, on
   glossy photo card, with dot gain. No test, no driver and no code review can
   answer it. (C23, still open. I am restating it, not re-deriving it.)
3. **The printed typo on all three pages of the 648 chart** ("wiith"), baked
   into the raster under the ChromIQ logo. Unfixable after release. (C9, still
   open — I confirmed the assets are the same ones.)

## SHOULD-FIX (in this change set)

4. **R12 — `THIRD-PARTY-NOTICES.md` says 338 files; it is 330.** The document
   replaced a stale number with a wrong one, taken from a prediction in the
   challenge doc instead of from `git ls-tree`. Everything else in that
   paragraph is right and is a genuine improvement.
5. **R8 — "Built-in preset — re-laid out (1 page)" for a run that emits seven**,
   plus "Auto patch count" and "Auto grey/white/black" on a branch where targen
   is skipped. Reproduced on screen and against real printtarg. Either drop the
   `notes` string on that branch or compute the page count.
6. **R18 — the source comment and the test docstring now contradict each other**
   about whose rule orders the i1Pro group. C27 was fixed in one and
   re-introduced in the other, in the same change set.
7. **R19 — stale counts in a file this change set edited:**
   `tests/test_knut_preview_geometry.py:62` ("All nine bundled presets") and
   `:69` ("none of the nine"). Plus `docs/dev_builtin_presets.md:150`, which
   still documents `_prebuilt_tooltip(paper)` after it grew a parameter.
8. **R13 — `docs/index.html:31` still says `"softwareVersion": "4.2.0"`**, and
   `:363` still offers `releases/tag/v4.2.0` as "get the beta". The preset count
   beside them is now pinned by a test; the version is pinned by nothing.
9. **R22 — the documented release gate is red on this machine** for reasons
   that predate the branch. Somebody has to decide whether 4.2.1 may be tagged
   against a gate nobody can currently run green, or fix the ~/ChromIQ leak
   first. This is a process blocker, not a code one, which is why it sits here.

## NICE-TO-HAVE

10. **R17 — `_prebuilt_paper` reads a `4x6` or `11x17` folder as millimetres.**
    Both are real ChromIQ paper codes and both are inches. Nothing ships in such
    a folder; the next photo-card bundle very plausibly would. Give
    `_prebuilt_paper` first refusal to `data.patch_db.PAPER_LABELS`.
11. **R10 residual — a sheet too small for one patch still returns 443.**
    Correctly disclosed in the CHANGELOG and correctly called "a message, not a
    number". Do not lose it.
12. **R16 — the seven old bundles whose `.ti2` still names a sheet that does not
    exist.** Now provably safe to correct, since two of them are correct.
13. **R7 — no test re-derives a bundle from its raster.** The check the project
    treats as the gate on a new bundle lives only in a script run by hand.
    Removing `photocard600_04.tif` leaves `test_prebuilt_bundles_carry_verified_geometry`
    green.
14. **R20 — the UI does not explain "Custom"**, and the A4 preflight tells the
    user to "regenerate the chart", which for a prebuilt bundle is impossible.
15. **`PREBUILT_PRESET_NOTES` is not `tr()`-wrapped.** Consistent with the
    existing tooltip body, but it is the first prebuilt tooltip that carries
    *print instructions* rather than a description of the mechanism, and a
    German user gets it in English. (C26's nice-to-have, still open.)
16. **R21 — the i1Profiler workflow export offers A4 / A3 / US Letter only.**
    Not a regression; nothing here could have fixed it without new
    reverse-engineered `PaperFormat` values.

## WHAT I VERIFIED AND FOUND CORRECT

* Nine of nine existing prebuilt presets resolve byte-identically to master
  (R1) — including every malformed-stem edge case.
* `_binary_search` returns the same number as master for every paper with a
  measured capacity row, at a cost of at most one extra probe, measured against
  real Argyll 3.5.0 on twelve instrument/paper/scale combinations (R2, R10).
* The committed rasters re-derive byte-identically to the committed
  `channels.json` (R6); the `.ti2` `PAPER_SIZE` correction did not disturb it.
* Both new test files are real: five source mutations, five reds, each mutation
  verified to have landed in the file (R5, R11).
* The print geometry path handles a 100x150 / 130x180 chart correctly, warning
  on A4 and staying silent on 4x6" / 5x7" (R15).
* The whole suite is green at `--runslow` on this commit under an isolated
  `HOME` (R22).
* Sanitised default names are 39 characters with no dot; the em-dash check is
  clean; `ChromIQ.spec` ships the new assets automatically (`('assets','assets')`);
  +1.5 MB against 23 MB of `assets/charts`.
* The CHANGELOG's numbers all check out: 600/4 pages, 648/3 pages, 90 for
  100x150, 169 for 130x180, 16 for 60x90, 443 for the old answer, "the seven
  printtarg would need" (measured: 7), "the other nine by Pharmacist charts"
  (eleven minus these two), "eleven bundles", `152` on the site. The release
  note renders with all four headings through `scripts/release_notes.py --tag v4.2.1`.

## WHAT I COULD NOT VERIFY

* **Whether these sheets can actually be READ.** The 0.564 mm spacer is the one
  question in this integration that no amount of code work answers. It needs one
  printed sheet of each and an i1Pro.
* **Whether a bordered print really clips only the crop marks**, and whether any
  common driver's "no expansion" borderless mode holds exact size. Both are
  printer-and-paper facts.
* **Whether the real-`HOME` gate errors (R22) also occur on master.** The
  evidence says yes (archived leftovers dated 09-01 to 09-05), but I did not run
  `--runslow` against a master worktree with the real `HOME`, because doing so
  writes into the owner's own project folder.
* **Anything about the i1Pro 3 Plus risk** (C22): unchanged, pre-existing, and
  these are simply the smallest patches yet.
* **Nelson's answers** to the two open questions the challenge raised: the
  "wiith" typo and the 2-white/2-black patch counts against ChromIQ's 4/4.
