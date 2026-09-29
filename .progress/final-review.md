# FINAL RELEASE REVIEW — ChromIQ v4.2.1, branch `feature/nelson-photocard-presets`

Reviewer: last pass before a STABLE tag, 2026-09-08.
Scope: `ca0f639c` (unreviewed), the branch as one release unit, the three open
items, and one on-screen end-to-end run.
Baselines: master worktree at `scratchpad/master-run`, and `d1adbe31` (the
broken state `ca0f639c` fixes) in a throwaway worktree.

Findings are appended as they are confirmed. CONFIRMED = reproduced here.

---
## S1 — CONFIRMED, GREEN. The release gate passes on this tree, first run.

```
QT_QPA_PLATFORM=offscreen pytest --runslow -n auto -q
12001 passed, 167 skipped, 4 xfailed in 204.29s (0:03:24)     exit 0
```

No worker-down banner, no `Fatal Python error`, no `Timeout (0:0X:XX)!` dump.
The count matches `ca0f639c`'s commit message exactly (12001 / 167 / 4). The
"RED on this machine" note in `nelson-presets/03-review.md` §R22 does not
reproduce here. A second run is in flight and is reported in S2.

## S2 — CONFIRMED, GREEN. Second gate run, identical.

```
12001 passed, 167 skipped, 4 xfailed in 205.52s (0:03:25)     exit 0
```

Two `--runslow` runs, both green, both exit 0, no worker death, no timeout
dump. The gate is not the problem with this release.

## S3 — CONFIRMED. All four regressions `ca0f639c` set out to fix ARE fixed,
### and the i1Pro state is bit-identical to master.

Probe `scratchpad/fr/p_td.py`, run in three trees: this branch, the master
worktree (7e500e59), and `d1adbe31` (the broken state). Gesture: pick
ColorMunki, tick Triple density, pick i1Pro.

| field on the i1Pro afterwards | HEAD | master | d1adbe31 |
|---|---|---|---|
| `printtarg` | `-ii1 -pA4 -t300 -a0.95 -m10 -M10` | **same** | `… -t300 -L -a0.95 …` |
| `disable_left_border` | False | False | **True** |
| engine `nolpcbord` / `clip_content_mode` | False / `notes` | same | **True / `off`** |
| `grey_steps` | 28 | 28 | **30** |
| left-border row hidden | False | False | **True** |
| `-P` row hidden | False | False | **True** |
| density box enabled | True | True | **False** |
| stored `triple_density` / `left_border` | False / False | False / False | **True / True** |

Every one of the five named regressions (F1, F2, F3, F4, F6) is gone, and HEAD
matches master on every field of this state. The tick comes back on the
ColorMunki (`_td_memory`), which is the approved behaviour.

Separately verified, `_apply_ui_state` × 4 combinations of stored value against
session memory, checked both immediately after the load and after the app
re-seeds the instrument (the door G18 came through in the previous round):

```
stored=False mem=False -> False    stored=False mem=True -> False
stored=True  mem=False -> True     stored=True  mem=True -> True
```

**A run's stored `triple_density` beats the session memory in all four**, and an
app-driven instrument change never restores anything (`E_app_only_round_trip`:
memory True, widget stays False). The G18 fault is not repeated for `_td_memory`.

## S4 — **CONFIRMED REGRESSION, NEW, AND THE HEADLINE FINDING OF THIS ROUND.**
### Five gestures leave "Triple density" TICKED AND GREYED OUT on the ColorMunki.
### The user cannot untick it, the chart is built with it, and the run stores it.

This is the question the brief asked — *"both disabled? a disabled box whose
value reaches a build?"* — and the answer to both is **yes**.

**The reproduction, in full, offscreen and deterministic**
(`scratchpad/fr/p_stuck.py`, `p_escape.py`, `p_bisect.py`):

```
1. Instrument -> ColorMunki
2. tick "Triple density"
3. Instrument -> SpectroScan        (or CR30 — both work)
4. tick "Hexagon patches"
5. Instrument -> ColorMunki
```

State on screen at step 5, on this branch:

| | this branch | master | d1adbe31 |
|---|---|---|---|
| "Triple density" | **ticked, DISABLED** | unticked, enabled | ticked, **enabled** |
| "Double density" | unticked, DISABLED | unticked, enabled | unticked, disabled |
| `_collect_guided().triple_density` | **True** | False | True |
| the record the next write files | **`triple_density: true, left_border: true`** | false / false | true / true |

**Both boxes are disabled and one of them is ticked**, so a mouse can change
neither. Verified by only ever calling `setChecked` through a helper that
refuses when `isEnabled()` is False — which is what a click can do.

**And it is not recoverable by any obvious gesture.** Measured:

| attempted escape | works? |
|---|---|
| click "Triple density" off | **no** (disabled) |
| click "Double density" on | **no** (disabled) |
| ColorMunki -> i1Pro -> ColorMunki | **no**, comes straight back |
| ColorMunki -> CR30 -> ColorMunki | **no** |
| Guided -> Manual -> Guided | **no** |
| load a run whose stored `triple_density` is False | tick clears, but the box **stays greyed** |
| go to SpectroScan, tick hexagons, untick them, come back | yes — the box re-enables (still ticked) |

So the only way out is a sequence nobody would guess, or a restart.

**What it costs.** Triple density's own tooltip: *"REQUIRES the physical
measuring rig accessory. Without the rig the ColorMunki cannot track the
tighter i1-style strips."* A ColorMunki user without the rig is handed a chart
they cannot measure, from a control that is greyed out in front of them, and
the run's `meta.json` keeps the answer.

**Bisected, commit by commit, over all ten** (a worktree per commit, same probe):

| commit | "Triple density" after `SS hexagons -> ColorMunki` | after the 5-step gesture |
|---|---|---|
| master 7e500e59 | disabled, but **Double density is ticked** — consistent | consistent |
| 1dec7035 … c48706d1 | unchanged from master | unchanged |
| **2055fca7** | enabled — correct | enabled |
| **ff3d1b2b** | **disabled with NOTHING ticked** ← the greying starts here | disabled, unticked |
| 4d0670b4 | same | same |
| d1adbe31 | same | ticked, **enabled** (escapable) |
| **ca0f639c** | same | **ticked and DISABLED** ← the lock-in |

Two commits, one fault each, and neither was reviewed for this:

* `ff3d1b2b` gave `_on_guided_dd_toggled` an early `return` when `_dd_writing`
  is set. That early return skips `self._td_check.setEnabled(not checked)`, so
  every app-driven clear of `_dd_check` (`_set_dd_without_remembering`, which
  `_update_dd_visibility` calls on every change of meaning) leaves
  "Triple density" greyed with nothing to explain it.
* `ca0f639c` then restores the remembered tick through
  `_set_td_without_remembering`, which ticks a box that is already greyed and,
  through `_on_guided_td_toggled`, greys the other one as well.

**The gate cannot see it**: 12001 tests pass on this state. Nothing in the suite
asserts either density box is ever *enabled*, which is the same shape of hole
as the previous round's M7 (nothing asserted the `-P` row was ever *visible*).

**The fix is one line and it is in the commit that broke it.** Move the two
`setEnabled` calls in `_on_guided_dd_toggled` above the `_dd_writing` early
return (they describe the widget's relationship to the other box, not the
person's answer), or re-assert both boxes' enabled state at the end of
`_update_dd_visibility` from `td/dd.isChecked()`. Either makes step 5 land on
"Triple density ticked, enabled, Double density disabled", which is the correct
and escapable state.

## S5 — CONFIRMED, minor, and it is the design's own shape, not a slip:
### `_td_memory` crosses RUNS and PROJECTS, and can put triple density on a run
### that stored `triple_density: false`.

`_td_memory` is one bool on the `TabChart` instance, which lives for the whole
session. It is never cleared on a target, run or project switch.

```
run A: ColorMunki, the person ticks Triple density        _td_memory = True
run B: opens with instrument i1Pro, stored triple_density = false
       -> on screen: unticked, correct
the person picks "ColorMunki" in run B
       -> Triple density comes back ON, and run B's next write files
          triple_density: true, left_border: true
master, same gestures: false / false
```

It does **not** happen when run B's own instrument is the ColorMunki: the
stored `triple_density` is then applied while the combo is already on CM, the
`toggled` handler runs `_remember_td()`, and the memory is overwritten by the
record. Measured for all four stored × memory combinations, and after an
instrument round trip inside run B — all correct (S3). So the leak needs run B
to have nothing to say about the ColorMunki.

Two reasons this is a note and not a finding to block on:

* `_dd_memory` has exactly the same reach and was reviewed and shipped in the
  round before this one; the ColorMunki option it re-arms ("Double density")
  needs the same rig.
* the person did choose the instrument. It is "the last thing you said about a
  ColorMunki this session", not an app default.

Worth a ruling from Basti at some point (§4c D-2/D-3 read strictly would say a
record's own value wins), not worth holding 4.2.1 for.

## S6 — CONFIRMED, PRE-EXISTING (reproduces identically on master). Unticking
### Triple density restores a left-border value from the run you came FROM.

`_on_guided_td_toggled(True)` stashes `_lb_check` into `_td_saved_lb_check` and
forces `-L` on; the stash is restored on untoggle. `_apply_ui_state` applies
`triple_density` **before** `left_border`, so the stash captures the *previous
run's* left border, and the restore hands it to the run you are now in.

```
run A: i1Pro, "Suppress left clip border" ticked
run B: ColorMunki, stored triple_density true, left_border FALSE
   after the load                 left_border = false     (correct)
   the person unticks Triple density
   -> left_border = TRUE   <- run A's value, now run B's record
```

Identical on master, so it is not this branch's fault and not a release
blocker. Recorded so the next person does not spend an afternoon on it: the fix
is to stash inside `_update_dd_visibility`/the load rather than in the toggle
handler, or to apply `left_border` before `triple_density` in `_SHARED_SETTINGS`.

---

# PART C — the three things still open

## S7 — CONFIRMED with my own eyes. The "wiith" typo is on ALL THREE pages of
### the 13 x 18 chart, baked into the raster. The 10 x 15 chart is clean.

Cropped the left band out of each committed TIFF and read it
(`scratchpad/fr/648_band_*.png`, `600_band_*.png`):

```
648, pages 1, 2 and 3 (identical):
  i1Pro 1/2/3 648 patch target for 13x18 cm / 5x7" photo card -print wiith
  borderless setting / NO expansion, retain size, color management: OFF

600, page 1 (and the same on 2-4):
  i1Pro 1/2/3 600 patch target for 10x15 cm / 4x6" photo card - print with
  borderless setting / NO expansion, retain size, color management: OFF
```

Two defects in the 648 line, both absent from the 600 line: **"wiith"** for
"with", and the missing space after the hyphen (`card -print`). It is in the
pixels, not in any string ChromIQ owns, so no code change can fix it — only a
regenerated bundle from Nelson.

**My judgement: not a blocker, but it should not ship silently.** It is a
typo on a working sheet, it does not affect a single measurement, and ChromIQ
did not write it — but it is printed on paper by our app, three times per user,
and every one of the nine bundles already shipping is clean. Basti should be
shown this crop and asked, because the cost of asking Nelson for one corrected
render is small and the cost of a stable release carrying it is permanent.

## S8 — CONFIRMED, STILL LIVE, and it is the one I would hold the release for
### until somebody decides: three instructions, on one screen path, disagreeing.

`ui/tabs/tab_print.py` is **not in `git diff master..HEAD --name-only`**. Both
strings are exactly as the previous round found them:

| where the user meets it | what it says |
|---|---|
| the printed sheet, both charts, every page | *"print with borderless setting / NO expansion, retain size"* |
| the new preset tooltip, read once when picking the preset | borderless with expansion off if you can; otherwise borders |
| **`_confirm_borderless`, `tab_print.py:1609`**, a modal at the moment of printing, **default button Cancel** | *"the printer driver does this and **it cannot be turned off**"* … *"print with borders instead — **the chart's white margins are made for that**"* |
| the preflight warning, `tab_print.py:1741` | *"Print with borders instead."* |

Both bold claims are false **for these two sheets specifically**: Canon and
Epson expose an extension amount that can be set to none (which is exactly what
the sheet instructs), and these sheets have no white margins to speak of — ink
reaches within 1.0 to 1.6 mm of the paper edge, where every other bundled chart
keeps 12 mm or more. The change set's own tooltip says so, in the opposite
direction to the modal.

The modal is the one the user obeys: it is red, it fires at the moment of
printing, and Cancel is the default. So in a stable release we hand the user a
sheet that says "borderless", and then an app that says "don't, and here is why
you are wrong", where the app's reason is untrue about that sheet.

**One clause fixes it**, e.g. after "it cannot be turned off": *"unless your
driver offers an extension amount you can set to none, which some Canon and
Epson drivers do"*. Then all three agree.

While in there: the preflight string at `tab_print.py:1741` is **not wrapped in
`tr()`** and carries an em dash, so it is English-only in all twelve languages.
Pre-existing (the file is untouched by this branch), so not a regression, but it
is the string this release makes most likely to be read.

## S9 — CONFIRMED by independent measurement, and it is the one thing in this
### release that no amount of code review can settle: 0.564 mm of paper
### between patches, 27 % tighter than anything ChromIQ has ever shipped.

Re-derived from the committed rasters with the app's own
`workflow/layout_from_render.derive_layout_from_render`, not from the facts
document (`scratchpad/fr`, all eleven bundles, median along-strip gap):

| bundle | patch length (mm) | **spacer (mm)** | spacer (px @ 360 dpi) |
|---|---|---|---|
| **photocard600 (new)** | 7.27 | **0.564** | **8** |
| **photocard648 (new)** | 7.69 | **0.564** | **8** |
| extended1944 / Letter | 7.76 / 7.48 | 0.776 | 11 |
| tc918eg A4 / Letter | 7.69 | 0.847 | 12 |
| abw1110 | 9.03 | 1.058 | 15 |
| abw702 (ColorMunki) | 11.78 | 1.058 | 15 |
| tc924 / tc918eg A3(+) | 10.5 / 10.4 | 1.129 | 16 |
| tc300 (ColorMunki) | 12.63 | 1.129 | 16 |

Two corrections to the number as it has been quoted: the smallest spacer
already shipping is **0.776 mm** (`extended1944`), not 0.85, so the new sheets
are **27 % tighter than the tightest shipped**, not 34 %. And `tab_chart.py:271`
says "7.3 / 7.6 mm patch length"; measured, the 648 is **7.69**, which rounds to
7.7.

Eight pixels of unprinted paper, on glossy photo card, with dot gain, is exactly
the dimension a printer closes up — and if two patches merge, chartread reads
the wrong colour for both and the profile is silently wrong rather than loudly
broken. **Nobody has printed one of these sheets and read it with an i1Pro.**
Verified: no measurement file, `.ti3` or read log for either bundle exists
anywhere in the repo, and neither preset is exercised by anything that produces
a measurement.

The rasters themselves are correct — the spacers alternate black and white for
contrast, and both bundles round-trip through `derive_layout_from_render`. That
proves the *file* is right. It says nothing about the *paper*.

**This is a hardware question and it is the honest limit of this review.** It
does not have to block the release — a preset that turns out to be too dense is
one bundle to withdraw, not a corrupted install — but it MUST NOT be presented
as tested. If it ships, it ships as new and unproven on paper, and the release
notes should not imply otherwise.

---

# PART B — release readiness of the branch as one unit

## S10 — **CONFIRMED. THE RELEASE BLOCKER. `v4.2.1-beta.1` IS ALREADY PUBLISHED,
### FROM A DIFFERENT BRANCH, AND IT CONTAINS WORK THIS BRANCH DOES NOT HAVE.**

Verified against origin and against GitHub, not inferred:

```
$ git ls-remote --tags origin | grep 4.2.1
720dd4d1…  refs/tags/v4.2.1-beta.1
478c7396…  refs/tags/v4.2.1-beta.1^{}          <- feature/182-compliance-sets

$ git merge-base --is-ancestor v4.2.1-beta.1 HEAD    -> NO
$ git merge-base --is-ancestor v4.2.1-beta.1 master  -> NO

$ gh release list
ChromIQ v4.2.1-beta.1   Pre-release   2026-09-08T08:18:32Z    <- PUBLISHED TODAY
ChromIQ v4.2.0          Latest        2026-09-07
```

Ten commits are in that tag and in neither this branch nor master — the whole
of #182, the Measurement Report's limit sets:

```
478c7396 #182: the strip names the rows and points to the reasons …
f4fbfbeb #182: the adversarial review's findings, F1 to F17
a1434780 #182: read-only cells in the Report limits window …
d8465874 #182: the unlock confirmation never said yes; the site offers 4.2.1 beta 1
b3686153 #182: catalogues, design record, changelog and version for 4.2.1 beta 1
aa90c406 / 217ddab6 / bb26e1e9 / 2f0ca861 / 01970b03
```

`git show v4.2.1-beta.1:core/version.py` → `4.2.1-beta.1`. This branch's
`core/version.py` → `4.2.1`. **Two different code bases, both calling
themselves 4.2.1**, and the stable one is the smaller of the two.

What happens if `v4.2.1` is tagged from here:

1. `.github/workflows/build-release.yml:474` only marks `*-alpha|*-beta|*-rc|
   *-pre` as a prerelease, so **`v4.2.1` becomes GitHub's "Latest"**, above
   `v4.2.1-beta.1`.
2. `docs/index.html` points every Download button at `releases/latest`, so the
   site immediately serves the build **without** #182.
3. `core/updater.py`: `_is_prerelease("4.2.1")` is False and
   `_parse_version("4.2.1") > _parse_version("4.2.0")`, so every 4.2.0 user
   **and every 4.2.1-beta.1 tester** is offered it as an upgrade — and a
   4.2.1-beta.1 tester who takes it silently loses the entire limit-set
   feature they were testing.
4. The release note built by `scripts/release_notes.py --tag v4.2.1` from this
   CHANGELOG says nothing about #182, because that section does not exist here.

**This is a human decision and it is Basti's, not mine.** Two ways out:
merge `feature/182-compliance-sets` first and fold both CHANGELOG sections
(`scripts/release_notes.py --since v4.2.0` folds every newer version), or
number this work **4.2.2** and leave 4.2.1 to the #182 line. Either is fine.
Tagging `v4.2.1` from this branch as it stands is not.

Nothing in the gate can see this, and no earlier round looked for it.

## S11 — CONFIRMED, SHOULD-FIX. Five user-visible changes on this branch are
### not in the changelog, including both faults a user actually reported.

`git log --oneline master..HEAD -- CHANGELOG.md` returns commits **2 and 3 of
ten**. Commits 4 to 10 landed afterwards and the section was never revisited.

| missing from the changelog | commit | would a user notice? |
|---|---|---|
| the CR30's "Readings per second" cell in Preferences is now **N/A**, not a `100 Hz` spin box (4.2.0 shipped a wrong fact about the instrument) | `2055fca7` | **yes** — a widget disappears from a table they can open |
| the pace panel's intro note reworded, plus a new CR30 ⓘ paragraph, in 13 languages | `2055fca7` | yes, visible prose |
| **"Double density" is now remembered per instrument** — tick it on a ColorMunki, glance at an i1Pro, come back, and it is still there | `2055fca7`, `ff3d1b2b` | yes |
| **a CR30 project no longer reopens as a ColorMunki** — Basti's own report of 2026-09-08, and a §4c D-2/D-4 spec violation that corrupted the run's own record | `d1adbe31` | **yes, and it is the most user-visible fix on the branch** |
| **triple density no longer leaks `-L` into a build on an instrument that hides it** (`-L` in the command, the `-P` and left-border rows gone unrecoverably, the run storing `triple_density: true`) | `ca0f639c` | yes |

Two of these are stored-record corruption that the user reported. A stable
release that fixes them and does not say so is a release the user cannot tell
has fixed them.

The section also has no `### Changed` and no `### Known issues` heading, both
of which `scripts/release_notes.py` supports.

## S12 — CONFIRMED by running real ArgyllCMS. The changelog's "**the seven**
### printtarg would need" is **nine**.

`CHANGELOG.md:17-18`. Measured with the shipped Argyll 3.5.0 against the
bundled `.ti1`, at ChromIQ's own defaults:

```
600 patches, printtarg -ii1 -p100x150 -t300 -m10 -M10            -> 9 pages
                                                        -a1.0    -> 9   (parameters.yaml default)
                                                        -a0.95   -> 9   (what Guided builds)
                                                        -a0.90   -> 7   <- where "seven" came from
648 patches, -p130x180                                            -> 5
                                                        -a0.90   -> 4
```

"Seven" is only true if the patch scale has already been turned down to 0.90.
At every default a reader would reproduce it is **nine** — so the claim
understates the improvement AND is checkably wrong. One word.

## S13 — VERIFIED CORRECT (independent audit): version, gate paperwork, i18n,
### the site, and every other number in the changelog.

* `core/version.py` = `"4.2.1"`, no suffix; correctly consumed by both
  PyInstaller specs, the splash, the masthead, `core/updater.py` and the
  release workflow's prerelease test.
* `scripts/release_notes.py --tag v4.2.1` renders all four sections, exit 0.
  (Its lead paragraph lands under `### 🔧 Fixed` — a pre-existing quirk of
  `split_sections`; **v4.2.0 shipped the same way**, so not a regression.)
* Every other factual number in the section re-measured and correct: 600/4,
  648/3, "the other nine by Pharmacist charts", 443 → 90 / 169 / 16, "every
  paper ChromIQ already had a measurement for is unchanged to the patch",
  eleven bundled charts, the `.ti2` `PAPER_SIZE` fields, and the site's
  "152 ready-made chart presets" (`len(BUILTIN_PRESET_KEYS) == 152`, now
  test-pinned).
* **i18n is clean.** All twelve catalogues: `0 missing of 5066`, each. 158
  tests green across `test_i18n.py`, `test_no_new_em_dash_in_user_facing_text.py`
  and `test_message_catalogue.py`. The previous round's G13 (lost key order and
  indentation in all twelve) is **fixed** — the whole i18n diff against master
  is 36 insertions / 12 deletions. The branch's three new strings were read in
  German, French and Japanese: accurate, in each catalogue's own register,
  placeholder-clean, no new em dash, and each language handles its own `N/A`
  token correctly (fr "N/D", ja 「該当なし」, de avoids naming it because
  German's `tr("N/A")` renders as a bare dash).
* `docs/index.html` is corrected: `softwareVersion 4.2.1`, no hard-coded tag
  link anywhere, both preset counts right.

## S14 — CONFIRMED. The `xfail(strict=True)` is honest, its reason is still
### literally accurate, and the defect is IDENTICAL ON MASTER.

`tests/test_a_run_reopens_on_its_own_instrument.py:143-165`. It documents that
`create_chart_ui.engine_recipe` is collected from the **Manual layout panel**
whichever module the user is in, so a Guided build files a recipe describing a
different chart. Run on HEAD, the reason string reproduces field for field:

```
85 fields, 12 differ:  instrument 'i1' vs 'CR30',  hflag False vs True,
margins 38/9/19/26 (the i1Pro's) vs 6/6/6/6, layout_mode, area_ratio,
spacer_mode, patch_area_align, use_instrument_margins, clip_content_mode
13 passed, 1 xfailed          (strict, so it is a standing failure)
```

Run against the master worktree: **byte-identical, 12 of 85, same fields.** The
defect shipped in 4.2.0 and every release before it. This branch does not
introduce it, does not worsen it, and reduces its blast radius by fixing the
reading end.

**So shipping it in a stable 4.2.1 is acceptable** — it is no worse than 4.2.0,
and the only new thing is that it is now written down, which is an improvement.
But it should be *said*: one line under a `### Known issues` heading (the
renderer already supports one) saying that a run's stored layout recipe can
describe a different chart than Guided built, so "Duplicate run" and "Load setup
from preset" may carry the wrong layout.

## S15 — CONFIRMED, minor paperwork, all NICE-TO-HAVE

* `THIRD-PARTY-NOTICES.md:224` says the bundled charts are **331** files. The
  tracked truth is **330** (`git ls-tree -r HEAD --name-only assets/charts`);
  the 331st is a gitignored `.DS_Store`. Third wrong value in a row for that one
  number, in the document specifically about what is redistributed.
* `docs/dev_builtin_presets.md` is right about *what* these presets are (counts
  updated, both rows present, a good new section on the `<W>x<H>` paper folder)
  and wrong about *how to build the next one*: `:150` still documents
  `_prebuilt_tooltip(paper)` where the signature is now
  `_prebuilt_tooltip(self, paper, note="")`; the asset-layout block omits
  `<stem>.channels.json`, which all eleven bundles have; the five-step recipe
  omits `scripts/derive_prebuilt_geometry.py`, the two test files a new bundle
  must be added to, and the notices count; and `:94` states flatly that a
  `<W>x<H>` folder is millimetres without the inch-code exception `08f96ef8`
  added to the code.
* One stale entry left in the em-dash baseline (`--prune` tidies it); no test
  fails.
* `PREBUILT_PRESET_NOTES` is not wrapped in `tr()`, so the borderless printing
  instruction reaches a German user in English. Consistent with its container,
  which is also un-`tr()`'d and unchanged from master.
* Three stale `100 Hz` references in `docs/cr30_reports/` (historical
  implementation reports, not user docs, not design specs). No `docs/design/`
  document is touched by this branch and none needs to be.

---

# PART D — on screen, the real window, end to end

## S16 — CONFIRMED ON SCREEN. S4 reproduces in the real window, and it renders
### WORSE than the offscreen data says: the ticked box shows NO TICK.

Driver `scratchpad/fr/drive_end_to_end.py`, real `MainWindow`, shown, cocoa,
settings sandboxed. The five gestures of S4, performed on the Guided panel:

```
on the ColorMunki: 'Triple density' tick=True  enabled=False
                   'Double density' tick=False enabled=False
the build would use triple_density=True   -L suppressed=True
a click can untick Triple density: False
a click can tick   Double density: False
```

Screenshot `scratchpad/fr/shots/13-stuck-density-boxes.png`, and the row
enlarged in `…-td.png` / `…-boxes.png`. Read off the pixels:

* **"Double density"** — disabled and unticked — draws a proper rounded
  indicator with a border.
* **"Triple density"** — disabled and **ticked** — draws a flat, borderless,
  off-white square with **no check mark at all**.

So the user sees two greyed density options, **neither of which appears to be
on**, while the fixed-settings line below reads *"patch ×1.30 · extra-high
density · no strip-length cap"* and the chart is built with triple density.

**ChromIQ already knows this exact hazard and has already fixed it once.**
`ui/tabs/tab_measure.py:1607-1618`, in capitals:

> *"A DISABLED CHECKBOX NORMALLY RENDERS AS UNCHECKED HERE. Both themes
> deliberately override the checked fill when a box is disabled … correct for
> 'this whole group is off', wrong for 'this is on and not yours to change':
> the row then reads as switched OFF while the measurement is patch-by-patch
> (**Basti saw exactly that, 2026-08-28**)."*

The Measure tab solves it with an `#locked_on` object name and a muted accent
fill. The Create Chart density row has no such treatment, so S4 lands the user
in the very state Basti reported once already, in a different tab, and this
time it also changes the chart.

## S17 — VERIFIED ON SCREEN, no problems: the photo-card preset walks
### Create Chart -> Print Chart -> Measure correctly.

Same driver, same window, before the S4 section. Real preset row picked with
`activated`, the way a click picks it:

```
PRESET ROW   '★  i1Pro · 10x15cm-600p-4pages by Pharmacist  ·  built-in'
run folder   …/ChromIQ/FinalReview-10x15/runs/run1
run files    FinalReview-10x15.channels.json, .ti1, .ti2,
             _01.tif _02.tif _03.tif _04.tif, cache/, exports/, meta.json
printtarg -p '100x150'                       (a real custom size, not "A4")
preset tooltip  "Built-in chart — cannot be deleted. A complete, ready-made
                 target laid out for 10 x 15 cm (100 x 150 mm)…"
PRINT CHART   preview pages 4
              printers offered: Canon_G6000_series, Canon_PRO_300_series,
                                EPSON_ET_8550
MEASURE       Start Measurement — enabled
NO modal, warning, error or question was raised at any point in the walk.
```

Screenshots `10-create-chart-after-preset.png`, `11-print-chart.png`,
`12-measure.png`. Nothing looked wrong to a user in this path: the sheet is
named on the preview, the page navigation says "Page 1 / 4", the chart layout
box reports 600 total patches over 4 pages at 7.6 × 7.27 mm, and the run folder
holds exactly what the preset promises.

The three shipped drivers were also re-run on this tree, all green:
`drive_photocard_presets.py` (mismatches 0, both charts, both sheets measured
at 99.98 × 150.00 and 130.03 × 179.99 mm), `drive_cr30_hz_and_density_tick.py`
(0 problems) and `drive_a_run_reopens_on_its_own_instrument.py` (0 problems).
`drive_youtube_cr30_shows_colormunki.py` exits 1 **by design** — it is the
reproduction script for the fault, run against a stored record that still
contains it.

## S18 — **CONFIRMED, and nobody has said this out loud: the man who reported
### the bug will still see it, on his own project, after installing 4.2.1.**

`d1adbe31` stops a stale saved-default recipe from overwriting a run's Guided
instrument. It does **not** repair a record that the old fault has already
corrupted — and Basti's `youtube` project is one.

Driven on screen against a sandboxed COPY of `~/ChromIQ/youtube`
(`scratchpad/fr/p_youtube_heal.py`, his own files untouched):

```
the chart itself      Youtube.ti2  TARGET_INSTRUMENT 'CR30'  HEXAGON_PATCHES True
the run's own record  guided.instrument 'CM'   guided.double_density true
                      engine_recipe.instrument 'CM'
ChromIQ 4.2.1 opens it -> Guided shows "ColorMunki / i1Studio / ColorChecker Studio"
a Generate from that panel would build a ColorMunki chart for a CR30 project
```

`scripts/drive_youtube_cr30_shows_colormunki.py`, the reproduction script this
branch ships, **still prints ">>> REPRODUCED" on this tree**. That is not a
failure of the fix: the record's own stored answer really is `CM`, and the app
is now faithfully showing what the record says. It is a failure of the
*release*, because the symptom the user reported is what he will meet again.

The one piece of good news, measured: **the record is no longer rewritten.**
Opening the project, switching tabs and coming back leaves `meta.json`
byte-identical, so the self-sustaining loop is genuinely broken. The corruption
is frozen, not spreading.

**What this needs is one sentence to the user, not code.** A project that was
opened by an earlier version may still show the wrong instrument in Guided;
picking the right one once in the Guided panel writes it back and it stays.
Without that sentence, the fix looks like it did not work, to the one person
best placed to say so.

I would not attempt an automatic heal in this release. `cr30-hz-and-dd/01`
§D18 already argued that case ("nothing needs healing, and a heal would be
destructive"), and reconciling `guided.instrument` against a run's `.ti2` is a
new behaviour that would want its own review round.

## S19 — CONFIRMED: the owner's real settings and projects are untouched.

Every driver ran with `CHROMIQ_SETTINGS_FILE` set and a sandboxed ChromIQ root.
Checked the VALUE, not the file, as CLAUDE.md requires:

```
before:  defaults read com.chromiq.ChromIQ custom_output_path  ->  (empty)
after :  defaults read com.chromiq.ChromIQ custom_output_path  ->  (empty)
diff of the whole plist, 414 lines, before vs after            ->  IDENTICAL
~/ChromIQ/youtube/runs/run1/meta.json                          ->  mtime 13:56, untouched
```

---

# RECOMMENDATION

## DO NOT SHIP — not as `v4.2.1`, not from this branch, not today.

Two things must change first. Neither is a doubt about the work on this branch,
which is green, well-tested and genuinely fixes what it says it fixes.

### The two blockers

1. **S10 — the version number is already taken.** `v4.2.1-beta.1` is a pushed,
   published GitHub pre-release built from `feature/182-compliance-sets`,
   carrying ten commits of #182 Measurement Report limit-set work that exists
   in neither this branch nor master. Tagging `v4.2.1` from here makes a
   *smaller* build "Latest", replaces the beta on the site, and offers it
   through the in-app updater to the very testers who are running #182 — who
   would silently lose the feature. **Basti's decision:** merge #182 first and
   fold both changelog sections (`scripts/release_notes.py --since v4.2.0`), or
   number this work **4.2.2**.

2. **S4 / S16 — a five-gesture path leaves both density boxes greyed, "Triple
   density" ticked and unclickable, the chart built with it, the run storing it,
   and the ticked box rendering with NO TICK.** It is a regression against
   master (bisected to `ff3d1b2b` + `ca0f639c`), it is not recoverable by any
   obvious gesture, and it forces a chart that the option's own tooltip says
   needs hardware the user may not own. It reproduces in the real window. The
   fix is one line, in the commit that broke it: move the two `setEnabled`
   calls in `_on_guided_dd_toggled` above the `_dd_writing` early return, or
   re-assert both boxes' enabled state at the end of `_update_dd_visibility`.
   Add a test that asserts a density box is ever *enabled* — nothing in 12,001
   tests does, which is why this got through.

### Fix before tagging, whatever the version number ends up being

* **S11** — five user-visible changes are missing from the changelog, including
  both faults the user reported (the CR30 project reopening as a ColorMunki,
  and triple density leaking `-L` into a build). The section was written at
  commit 3 of 10 and never revisited.
* **S12** — "the seven printtarg would need" is **nine** at every default.
  Measured on real Argyll 3.5.0. One word.
* **S18** — say, in the release notes, that a project opened by an earlier
  version may still show the wrong instrument in Guided, and that picking it
  once writes it back. Otherwise Basti opens his own `youtube` project, sees
  the same symptom, and reasonably concludes the fix did not work.
* **S14** — one `### Known issues` line for the documented `engine_recipe`
  defect the `xfail` guards. Shipping it is fine (it is identical on master);
  shipping it silently is not.
* **S8** — one clause on `tab_print.py:1609` so the modal stops telling the user
  that borderless "cannot be turned off" and that "the chart's white margins are
  made for that", neither of which is true of these two sheets. Today the app
  contradicts, in red and with Cancel as the default button, an instruction
  printed on the paper it just told the user to print.

### Worth doing, not worth holding for

* **S7** — ask Nelson for a corrected 13 x 18 render. "wiith", on all three
  pages, in the pixels, for ever.
* **S15** — `THIRD-PARTY-NOTICES.md` says 331 files; it is 330.
  `docs/dev_builtin_presets.md`'s recipe would not reproduce what was built.
* **S5 / S6** — the session memory crosses runs, and unticking triple density
  restores a left border from the run you came from (the second is
  pre-existing, on master today).

### What I could not verify

* **A printed sheet, on paper, read with an i1Pro.** The 0.564 mm spacer (S9) is
  27 % tighter than anything ChromIQ has shipped and 8 pixels at 360 dpi. The
  raster is provably correct; the paper is not a thing a code review can reach.
  If these presets ship, they ship unproven on paper, and the release notes
  should not imply otherwise.
* **Windows and Linux.** Everything here is macOS, cocoa and offscreen.
* **Whether Nelson's borderless instruction is right for a printer that is not
  a Canon or an Epson** — the "extension: none" mode is not universal.
* **Whether Basti wants `_td_memory` and `_dd_memory` to cross runs at all**
  (S5). That is a ruling, not a defect.

### What is genuinely good, and should be said

The gate is green twice (12,001 passed, exit 0, no worker death). All four
regressions `ca0f639c` set out to fix are gone and the i1Pro state is
bit-identical to master. A run's stored `triple_density` beats the session
memory in all four combinations, and no app-driven instrument change restores
anything — the previous round's headline fault is not repeated. i18n is
complete in all twelve languages with zero missing keys, and the previous
round's catalogue damage is fully repaired. The photo-card presets walk Create
Chart → Print Chart → Measure in the real window without a single warning, and
put a real custom sheet size on screen where the app used to say "A4".
