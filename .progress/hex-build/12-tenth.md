# 12 - TENTH adversarial review (round 10), commit `93488808`

Branch `feature/nelson-photocard-presets`. Bar: *would I sign this off to print on a
paying customer's paper, and to be tagged stable tonight.*

Proof folder: `~/Desktop/ChromIQ-hex-proof/17-tenth/`.
Worktree for every mutation: `<scratchpad>/wt10` at `93488808`, `git checkout -- .`
between each; the main tree was never edited.

---

## O1 - TARGET 1, the ruler-marker fix: CORRECT in the real window, in both
orientations, and correct in every order a user can produce. NOTHING FOUND

Driven on screen in the real app (`<scratchpad>/r10/drive_round10.py`,
`CHROMIQ_SETTINGS_FILE=/tmp/chromiq-round10.ini`), Create Chart > Manual, CR30 +
Hexagonal, ruler markers on:

```
=== turn=False ===
  TB checked=True enabled=False | SD checked=True enabled=True
  _area_is_turned_hex()=False  _hm_axis_is_top_bottom=False
  TB tip: "Not available on hexagonal patches. A honeycomb's rows sit at an even spacing down the page, ..."
  SD tip: ''
  after unticking the LIVE comb: warning='No dashes will be printed - tick at least one of the two edge boxes...'
  after unticking the DEAD comb: warning=''
=== turn=True ===
  TB checked=True enabled=True  | SD checked=True enabled=False
  _area_is_turned_hex()=True   _hm_axis_is_top_bottom=True
  TB tip: ''
  SD tip: 'Not available on a turned honeycomb. Its columns sit at an even spacing across the page, ...'
  after unticking the LIVE comb: warning='No dashes will be printed - tick at least one of the two edge boxes...'
  after unticking the DEAD comb: warning=''
```

That is the exact inverse of round 9's N7 measurement, which read identically for
both orientations. Pictures: `UI-marker-group-turnFalse.png`,
`UI-marker-group-turnTrue.png`, and the two `-live-off` states.

**Every order, off screen** (`<scratchpad>/r10/panel_orders.py`, `panel_orders2.py`,
tab_chart's own `changed -> set_helper_markers_supported(not hex, one_axis_only=hex)`
wired in verbatim):

| order | result |
|---|---|
| instrument -> shape -> turn -> master tick | correct at every step |
| master tick FIRST, then honeycomb, then turn | correct |
| turn toggled ON/OFF while the markers are on | follows, both ways |
| CR30 -> SS -> i1 -> CR30 -> p3 -> CR30 | correct; `mode` reverts to `flat` on the way, so BOTH combs live is right for a rectangular chart, and re-selecting `hex` restores the turned greying |
| master tick off then on, on a turned comb | the dead comb stays down (the `_hm_rows` re-enable path) |
| untick the live comb / the dead comb | notice appears for the live one only |
| `set_recipe` with `hex_flat_top=True`, then `False` | follows |

**The stored value survives, everywhere.** In all 30 states measured, the two
`isChecked()` values changed only when the probe itself clicked them. Disable,
never untick, holds.

**The fallback in `_area_is_turned_hex` is not reached from a selector-less panel
by any live path.** `set_helper_markers_supported` has exactly ONE caller in the
app (`ui/tabs/tab_chart.py:18422`), and `_manual_layout_panel` owns its selectors.
Preferences > Chart Layout and the relayout dialog never call it, so nothing is
greyed there at all - which is what they did before this commit too, and is
unchanged by it. `hex_flat_top_cb` is built in `_build_base` on EVERY panel and
`set_recipe` loads it, so when the fallback IS exercised it answers correctly:
a selector-less panel loaded with a turned CR30 recipe reports
`_inst=CR30 _recipe_hflag=True area_hex=True turned=True`.

**Ships-with-it: nothing on this target.**

## O2 - the greyed comb's REASON is reachable by a hover, and it is the right one

Measured with the REAL cursor (`QCursor.setPos`) over the running window,
`<scratchpad>/r10/tooltip_reach.py`. A tooltip on a DISABLED widget is a
well-known Qt doubt, and the whole "greyed, but never unexplained" rule rides on
it:

```
  SIDES (GREYED, tip set)     enabled=False tip_set=True  SHOWN=True
      shown_text='Not available on a turned honeycomb. Its columns sit at an e'
  TOP/BOTTOM (GREYED, tip set) enabled=False tip_set=True SHOWN=True
      shown_text="Not available on hexagonal patches. A honeycomb's rows sit a"
```

Both greyed boxes show their own reason on hover, and each shows the reason for
the orientation on screen. (The enabled controls did not raise a tooltip in the
same harness; that is the harness - the window was not frontmost - and it is not
reported as a finding, because the direction being tested came back POSITIVE.)

## O3 - the twelve translations of the new tooltip: present, and none has the
axes flipped. NOTHING FOUND

All twelve catalogues carry the new key, and each is a true mirror of that
language's existing pointy string - "left and right ... seam between rows" where
the old one says "top and bottom ... seam between columns", and "the top and
bottom dashes line up exactly" where the old one says the left and right ones do.
Checked word by word in de, es, fr, it, ja, nl, no, pl, pt, ru, sv, zh_CN
(`<scratchpad>/r10` transcript in `findings.md`). No em dash added by any of them.


## O4 - the geometry claim behind the whole fix, measured independently: on a
turned honeycomb the top and bottom comb lands to **0.0015-0.0104 mm** and the
side comb would be **3.00 mm** out. NOTHING FOUND

`<scratchpad>/r10/comb_lands2.py`. Patch centres taken from
`geometry.patch_rects_px` at 600 dpi, which is the record of where the ink is
(stagger included) - not from `place.x_of`, which is what the comb itself is
built from and would have made this circular. The REFUSED comb is measured too,
by suspending `instruments.is_hexagonal` for the measurement only, so every row
carries its own control.

```
paper     n  turned |  top/bottom worst mm   sides worst mm |  engine draws  patches
A4      150    True |               0.0025           2.9998 |    top/bottom   150
A4      150   False |               2.9996           0.0107 |        +sides   150
A4      345    True |               0.0067           2.9998 |    top/bottom   345
A4      345   False |               2.9998           0.0107 |        +sides   345
A4      690    True |               0.0078           2.9998 |    top/bottom   391
A3      690    True |               0.0099           2.9998 |    top/bottom   690
Letter  345    True |               0.0078           2.9997 |    top/bottom   345
A4R     690    True |               0.0104           2.9997 |    top/bottom   390
   ... 24 rows, 4 papers x 3 counts x both orientations, no exception
```

The comb the panel leaves live is the comb that lands, in every one. The
tooltip's "The top and bottom dashes line up exactly" and the changelog's "which
is which follows the turn" are both TRUE as measured.

## O5 - the preview OVERLAY agrees with the ink on the sheet, turned and pointy.
NOTHING FOUND

`<scratchpad>/r10/overlay_vs_sheet.py`. The chart is built twice, markers off and
on; the marker ink is the XOR. The overlay is rebuilt exactly as
`TabChart._helper_marker_lines_frac` does it (recorded recipe + `area_target_count`
from the .ti2 + `helper_marker_lines_mm`) and every segment is checked against
that ink, in both directions:

```
turned=True  segs=80   with ink under=79   WITHOUT=1  marker ink px=3673  ink no overlay covers=0
turned=False segs=114  with ink under=114  WITHOUT=0  marker ink px=5586  ink no overlay covers=0
```

Not one printed marker pixel is left uncovered by the overlay in either
orientation. The single turned segment with "no ink under it" is segment 38 at
x=103.59 mm, y=2.00-4.00 mm: measured, that spot is **already black in the
markers-OFF render** (min grey 0 both ways), i.e. the dash is printed on top of a
strip letter and the XOR cannot see it. That is O6, not an overlay fault.

`hex_flat_top` also survives the `channels.json` round trip
(`to_dict` -> `from_channels_json` -> `build_kwargs`), so the overlay cannot compute
a pointy geometry for a turned sheet.

## O6 - the ruler dashes DO print through the strip letters, and it is NOT the
turn's doing: a RECTANGULAR chart does the same, byte for byte, at master.
Ships-with-it; belongs on the 4.2.2 list

Round 9's N4 measured 14/15 letters struck on a turned honeycomb and called the
collision pre-existing, but its only control was a POINTY honeycomb - which is
refused top dashes, so 0/26 there proves nothing at all. The control this needed
is a RECTANGULAR chart, which takes both combs. Built here on both trees
(`<scratchpad>/r10/marker_vs_letters.py`):

| chart | struck | worst marker px inside a letter |
|---|---|---|
| CR30 honeycomb TURNED, this branch | 14/15 | 48 |
| **CR30 RECTANGULAR, this branch** | **13/15** | **48** |
| **CR30 RECTANGULAR, at master `7e500e59`** | **13/15** | **48** |
| i1 RECTANGULAR, branch / master | 1/1 | 74 / 74 |
| SS RECTANGULAR, branch / master | 9/9 | 36 / 36 |
| CR30 honeycomb pointy | 0/26 | 0 (no top dashes exist) |
| SS honeycomb pointy, at master | 0/16 | 0 (no markers at all at master) |

The rectangular numbers are **identical on both trees**. Top-edge ruler dashes
have overprinted the strip letters on every chart that carries them since #152
shipped; the turn only makes a honeycomb one more chart that carries them. By the
standing orders that is shipped behaviour, not this branch's, and not to be
changed under a stable tag.

## O7 - **THE ELEVENTH SELF-VALIDATING TEST**, and it is the one written in this
commit. `tests/test_the_three_specs_bundle_the_same_data.py` reads the specs with
a regex that does not know what a Python comment is: COMMENTING OUT the exact
entry it was written to protect leaves all 17 tests green. Ships-with-it (named)

Four mutations, each on a clean `wt10`, `git checkout --` between them:

| # | mutation on `ChromIQLinux.spec` | result |
|---|---|---|
| baseline | none | 17 passed |
| A | `('data/scanner_targets', ...)` **commented out** | **17 passed** |
| B | the same line **deleted** | 2 failed (the test bites) |
| C | the same line in **double quotes** | 2 failed - a FALSE alarm: the entry bundles |
| D | `*([(...)] if sys.platform == 'win32' else [])` | **17 passed** - bundles nothing on Linux |

`_datas()` is `re.findall(r"\(\s*'([^']+)'\s*,\s*'[^']*'\s*\)", block)` over the
raw text of the `datas=[...]` block. It therefore:

* counts a **commented-out** entry as bundled (mutation A) - and commenting out is
  how an entry is disabled in practice, which is precisely the fault the test
  exists to prevent;
* counts a **conditional** entry as bundled whatever the condition says (D);
* **cannot see** a legitimate double-quoted entry and fails on it (C);
* is blind to every `*_splat` (`_gammap_datas`, `_engine_datas`, `_ft_datas`,
  `_ic_datas`, `_bl_datas`, `_btp_datas`, `_we_datas`, `_oc_datas`, `_ak_datas`,
  `_ft_vendor_datas`) and to `certifi_where`, so `test_the_specs_do_not_drift_
  apart_again` compares four literal paths and nothing else. macOS bundles six
  splat groups that Linux does not; the drift test cannot see any of them.

Nothing in the tree today is commented out or conditional, so **no user is
affected**: the fix itself is right (see O8). It is a test that will not catch the
next occurrence of its own fault. Not a release blocker; it is a test-quality
item for 4.2.2, and it is the eleventh round running in which the round's own new
test has a hole in it.

The `ALLOWED` map also names `data/compliance_sets` as macOS-only, and that path
exists in no spec and in no `data/` directory on this branch - a forward-looking
entry that can never fire here.

## O8 - the spec fix itself is right, and macOS did not move. NOTHING FOUND

* `ChromIQ.spec` is **not touched** by `93488808` (`git show --stat`): the macOS
  bundle is byte-for-byte what it was.
* `data/i18n` and `data/scanner_targets` both exist and are both read through
  `core.resource_path` - `resource_path("data/i18n")`,
  `resource_path(f"data/i18n/{code}.json")`,
  `resource_path(f"data/i18n/parameters.{code}.yaml")`,
  `resource_path(f"data/i18n/qt/{code}.json")`,
  `resource_path("data/scanner_targets")`. `resource_path` resolves into the
  bundle when frozen, so a spec that does not carry them ships the features
  absent and silent.
* Neither path is collected by any other mechanism in either spec (no
  `collect_data_files` for them, no hook, no splat that reaches `data/`), so
  before this commit a Linux build really did carry neither and a Windows build
  really did carry no scanner targets.

## O9 - the six NEW helper-marker tests do not measure whether the comb LANDS -
but the suite is not blind, and the test that catches it is sound. NOTHING FOUND
(one withdrawn candidate, recorded because it nearly went out as a blocker)

`_engine_draws()` in `tests/test_helper_markers.py` returns `bool(lines)` and
never asks where the lines are. Mutation **G1**: on a turned honeycomb only,
shift the comb by half a dash pitch, so it stays evenly spaced, stays non-empty,
and points at the seam between two columns instead of at the patches. Proved to
land - worst centre-to-dash distance on A4 turned goes **0.0025 mm -> 2.5979 mm**:

```
all seven marker test files (145 tests)           145 passed   <- BLIND
the whole everyday tier under the same mutation   1 failed, 12507 passed, 323 skipped
  FAILED tests/test_the_honeycomb_can_be_turned.py::test_the_comb_that_survives_is_the_one_that_lands[True]
```

So the seven marker files are blind to it and `test_the_honeycomb_can_be_turned.py`
is not. That test measures against `patch_rects_px` centres, bypasses the refusal
the same way I did, and demands `kept < 0.2 mm`, `dropped > 1.0 mm` AND a 10x
ratio - it is not circular and it is not the fault's own arithmetic. **Withdrawn
as a finding.** Recorded because "the marker tests do not check alignment" reads
like a blocker until the mutation is run against the WHOLE suite, and four
reviewers in this series have reported a harness as a fault.

## O10 - six mutations of the panel fix, five caught. The sixth cannot land

Each on a clean `wt10`, against `tests/test_helper_markers.py`:

| # | mutation | caught by |
|---|---|---|
| P1 | `_hm_axis_is_top_bottom = False` (round 9's shipped fault restored) | `test_no_dashes_is_said_when_and_only_when_none_will_print[True]` (+3 more) |
| P2 | `_update_helper_marker_rows` back to hard-coded `top_bottom` | same, [True] |
| P3 | the two tooltips swapped | `test_the_greyed_comb_says_why_and_names_the_right_axis[False]` |
| P4 | `_area_is_turned_hex` always True | `..._none_will_print[False]` |
| P5 | the engine's `flat_top` branch reverted to the pointy one | `test_the_engine_honours_exactly_the_axis_the_panel_leaves_live[True]` |
| P6 | `_live.setEnabled(supported and not one_axis_only)` (grey BOTH combs) | **nothing - and it cannot be caught** |

P6 does not land: `set_helper_markers_supported` calls
`_update_helper_marker_rows()` two lines later, and that re-enables every widget
in `_hm_rows` (the live comb among them) whenever the master box is ticked; when
the master box is NOT ticked it disables everything anyway, and when `supported`
is False `_update_helper_marker_rows` is not called at all. So
`_live.setEnabled(supported)` is dead in the honeycomb case whichever way it is
written. Recorded as a mutation that could not be proved to land, per the rule -
not as a finding.

## O11 - a phantom I nearly reported, recorded so the next round does not chase it

From `UI-marker-group-turnTrue.png` alone the greyed "Sides (vertical)" box looks
UNTICKED, which would mean the panel shows the user that their stored answer was
lost - the opposite of "disable, never untick". Two harnesses said so and both
were mine and both were broken: an offscreen `grab()` of an unparented panel
returned two frames with **max channel diff 0 for the LIVE control as well**, so
it was painting nothing at all.

Measured properly, in the running window
(`<scratchpad>/r10/greyed_tick_onscreen.py`), the greyed box paints its tick:

```
GREYED-sides    checked vs unchecked: max diff 207  pixels differing 1276
LIVE-topbottom  checked vs unchecked: max diff 224  pixels differing 1276   <- control
```

Greyed + checked is a filled pale square; greyed + unchecked is a hollow outline
(`BOX-GREYED-sides-checked.png` / `-unchecked.png`). The two are distinguishable
and the control moves by the same 1276 pixels. **No finding.**

## O12 - the changelog sentence round 9 called untrue is now TRUE

`CHANGELOG.md:52` - *"The comb that lines up is drawn and the other is greyed
with the reason, and which is which follows the turn above."* Both halves
measured: the drawing follows the turn (O4) and the greying now follows it too
(O1), on screen and in every order. Round 9's N7 changelog complaint is closed.

## O13 - the gate, run once on a still tree

`wt10` at `93488808`, `git status` clean, nothing edited during the run:

```
QT_QPA_PLATFORM=offscreen pytest --runslow -n auto
12651 passed, 180 skipped, 4 xfailed in 210.38s (0:03:30)
```

Exit 0, no `node down` banner, no `Fatal Python error`, no `Timeout` dump.
(The commit message records 12664 passed; this host skipped 13 more. Nothing
failed either way.)

## O14 - the owner's preferences store is untouched

Every driver ran with `CHROMIQ_SETTINGS_FILE=/tmp/chromiq-round10.ini` and with
`AppSettings._qs` pointed at a copy in a fresh temp folder. After all five runs:

```
$ defaults read com.chromiq.ChromIQ custom_output_path
(no output - the key holds "" , the owner's value)
$ ls -la ~/Library/Preferences/com.chromiq.ChromIQ.plist
-rw-------  16900  9 Sep 05:22        <- hours BEFORE the first run at 17:00
```

The VALUE was checked, not the file against a backup.

---

# WHAT I DID NOT MEASURE, PLAINLY

* **A real Windows or Linux BUILD.** O8 proves the two specs now list the data
  and that nothing else collects it; it does not prove PyInstaller puts it where
  `resource_path` looks, on those platforms, because neither toolchain is on this
  machine. The macOS spec is untouched, so macOS cannot have regressed.
* **Printed paper.** Everything here is the TIFF the app writes and the pixels in
  it. Nothing was put on a printer, and no CR30 read anything.
* **The `data/compliance_sets` ALLOWED entry** - it names a path that exists
  nowhere on this branch, so its behaviour after #182 merges is unexercised.
* **The other six splat groups macOS bundles and Linux does not**
  (`_ft_datas`, `_bl_datas`, `_btp_datas`, `_oc_datas`, `_ak_datas`,
  `_ft_vendor_datas`). O7 shows the drift test cannot see them; I did not work out
  whether any of them is a real Linux gap. `ChromIQLinux.spec` has no
  `collect_all('freetype')` at all, which is worth somebody's ten minutes for
  4.2.2 (vector-PDF export), but Linux normally has a system libfreetype and I did
  not test it.
* **Preferences > Chart Layout and the relayout dialog.** `set_helper_markers_
  supported` has one caller in the whole app and it is not those; their edge boxes
  are live on every chart, honeycomb or not, and were before this commit too.
  Unchanged by `93488808`, so out of this round's scope, but nobody has ever
  measured what those two windows do with the marker group.
* **The tooltip on an ENABLED widget** never appeared in my hover harness (the
  window was not frontmost). The direction that mattered came back positive, so I
  did not chase it.
* **Anything outside the marker/spec change**: the strip-letter reserve, the
  capacity cost, the row-number offset and the margins were measured by rounds 7,
  8 and 9 and I did not re-derive them.

---

# RELEASE VERDICT: **SHIP**

No release blocker. Round 9's N7 - the panel greying the comb that prints - is
genuinely fixed: measured in the real window in both orientations, in seven
different orders including the instrument round trip and a preset load, with the
stored ticks surviving every one. The geometry claim under it holds to 0.01 mm
across 24 configurations with the refused comb as its own control, the overlay
matches the ink on the sheet in both orientations, the greyed box's reason is
reachable by hover and correct, and all twelve translations mirror the right axis.
The spec fix is right and macOS did not move. The gate is green on a still tree.

Two items for the 4.2.2 list, neither of which touches a sheet of paper today:

1. **O7** - `test_the_three_specs_bundle_the_same_data.py` passes with its own
   protected entry commented out, and with a conditional entry that bundles
   nothing. Rewrite it to parse the spec with `ast` instead of a regex, or to
   compare the three `datas` lists after executing them under a `Analysis` stub.
2. **O6** - top-edge ruler dashes overprint the strip letters on every chart that
   carries them, rectangular ones included, identically at master. It is a real
   thing on paper and it is not this branch's; it wants Basti's call on whether
   the comb should skip the label band.
