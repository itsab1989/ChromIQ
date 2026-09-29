# 09 — SEVENTH adversarial review (round 7), commit a70b0c6e

Branch: `feature/nelson-photocard-presets`.
Bar: "would I sign this off to print on a paying customer's paper, and tag it stable tonight".
Started 2026-09-09.

Targets handed to me:
1. `tests/conftest.py::_snapshot_the_modal_entry_points` / `_restore_the_modal_entry_points` (K11's fix).
2. `ui/chart_layout_info_panel.py::_name_the_pitch_row` (K1's fix).
3. The new/changed tests, by mutation.
4. The eighth self-validating test.
5. Fresh eyes on anything that prints wrong, misreports a measurement, or shows a wrong picture.

Findings appended as L1, L2, ... as measured.

---

## L1 — the K11 containment is REAL. Proven by a live leak, not by restating the code. NOTHING FOUND

Wrote a throwaway `tests/test_zzz_round7_leak_probe.py` that leaks all five entry points with
bare `setattr`, exactly as the offending helper did:

```python
QDialog.exec = lambda self: 1
for m in ("warning", "critical", "information", "question"):
    setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
QMessageBox.exec = QDialog.__dict__["exec"]
```

Scheduled it FIRST, in one process (`-n0`, so the ordering is guaranteed, not xdist luck),
ahead of the four victim files round 6 named.

| conftest | result |
|---|---|
| shipped (HEAD) | **86 passed** |
| repair disabled (`_restore_the_modal_entry_points()` replaced by `pass`) | **33 failed, 53 passed** |

The mutation was proven to land (grepped `ROUND7 MUTATION` in the file, `__pycache__` cleared)
and reverted; `git diff --stat tests/conftest.py` is empty.

33 failures is a bigger blast radius than round 6's own 5/25, because I leak all five at once
and schedule the probe first deliberately. The repair swallows every one of them. So K11's fix
is not merely present, it contains the exact fault that produced it. Confidence: certain.

---

## L2 — the repair SILENTLY REVERTS a module- or session-scoped patch of any of the five entry points, before the first test in the file even runs. Latent today; NOT a blocker

The repair is a function-scoped autouse fixture. pytest sets higher-scoped fixtures up FIRST,
so a `scope="module"` fixture that stubs `QMessageBox.warning` for a whole file is undone by
the repair in the setup of every test in that file, including the first.

Measured with a throwaway `tests/test_zzz_round7_modulescope_probe.py`:

```python
@pytest.fixture(scope="module", autouse=True)
def _stub_warning_for_the_whole_file():
    mp = pytest.MonkeyPatch()
    mp.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: CALLS.append(a) or 0))
    yield
    mp.undo()
```

```
FAILED test_first  - the module-scoped stub was not in effect for the FIRST test
FAILED test_second - the module-scoped stub was gone by the SECOND test
2 failed, 2 errors
```

i.e. a real `QMessageBox.warning` was called with an offscreen `QApplication`, in a suite whose
whole reason for this machinery is that a real modal hangs the gate. The `MODAL_GRACE_MS`
watchdog would eventually name it, so it fails loudly rather than hanging - but it fails on a
file that did nothing wrong, which is the exact shape of the fault this repair exists to stop.

**Why it is not a blocker.** I scanned every `tests/*.py` for a non-function-scoped fixture that
patches `QMessageBox`/`QDialog`, and for `setup_module` / `setup_class` / `scope="class"`:
**zero hits**. Nothing in the suite hits this today, and it cannot affect the shipped app.

**Why it should be written down.** The repair's docstring is 60 lines about what NOT to do and
says nothing about this; the next person who reaches for a module-scoped modal stub (a
perfectly ordinary thing to write) gets a file that fails for a reason nothing in the tree
explains. One sentence in the docstring, or a `scope="module"`-safe guard, closes it.
Confidence: high (measured, both tests, twice).

---

## L3 — **THE EIGHTH SELF-VALIDATING TEST.** `test_the_snapshot_was_taken_before_collection` cannot tell an early snapshot from a late one. Proven: the exact fault it names leaves all seven of its file's tests green

`tests/test_a_leaked_modal_never_reaches_the_next_test.py::test_the_snapshot_was_taken_before_collection`
(new in a70b0c6e) says, verbatim:

> *"a snapshot taken after a test module patched one at import time would record the stub and
> repair a worker into the fault."*

and then asserts

```python
assert recorded[("QMessageBox", name)] is QMessageBox.__dict__[name]
```

That is circular. The repair runs in the SETUP of this very test and has just written every
recorded object onto the class, so `recorded is current` is true **by construction**, whether
the recording happened in `pytest_configure` or a microsecond ago from a poisoned class.

### Measured

Mutation, in `tests/conftest.py`: `_snapshot_the_modal_entry_points()` removed from
`pytest_configure` and called lazily from the repair fixture instead (`if not
_PRISTINE_MODALS: _snapshot_the_modal_entry_points()`), which is precisely the "taken after
collection" world the test names. A throwaway `tests/test_aaa_round7_poison.py` patches
`QMessageBox.warning` with a `staticmethod` **at module import time** (i.e. during collection)
and never restores it. Files scheduled in that order, single process:

| conftest | the guard file | an honest probe of `QMessageBox.warning` in a LATER file |
|---|---|---|
| shipped | **7 passed** | pristine (`PyQt6.sip.methoddescriptor`) |
| late snapshot | **7 passed** | **`staticmethod` — the worker is poisoned for the rest of its life** |

Both mutations proven to land (`grep ROUND7 MUTATION tests/conftest.py`, `__pycache__` cleared
before each run). The guard is green in the world it exists to forbid, and an eight-line
throwaway probe in the same run is red. That is the definition this series has been using.

### It matters more than a usual guard gap

This is the guard on the fix for the round-6 BLOCKER, in a project whose stated first
principle is that a green gate must mean something. Under a late snapshot the repair does not
merely fail to repair: it *reinstalls the stub* on every subsequent test, so a single
import-time patch becomes permanent and the containment fixture becomes the delivery
mechanism. Nothing else in the suite would notice.

### A non-circular assertion, proven to discriminate

Assert what the recorded object IS, not that it equals what the repair just wrote:

```python
for owner, name, val in c._PRISTINE_MODALS:
    assert type(val).__name__ != "staticmethod", (
        f"the snapshot recorded a Python object for {owner.__name__}.{name}")
```

Measured with the same two conftests: shipped records `methoddescriptor` (green), the late
snapshot records `staticmethod` (red). Stronger still would be to assert the snapshot list is
non-empty at `pytest_collection` time, or to name `pytest_configure` as the only caller.
(NB: the pristine type is `PyQt6.sip.methoddescriptor`, not `builtin_function_or_method` --
my first draft of the assertion had the wrong type name and failed on the shipped tree, which
is itself a reminder to run the assertion both ways before writing it down.)

Severity: by the standing orders' own rule -- *"any test proved not to catch the fault it
exists for"* -- this is a **fix-before-tag** item. It does not touch the shipped app, nothing
prints wrong and no measurement moves; it is a hole in the guarantee that the gate means
something. Confidence: certain.

---

## L4 — K1's fix VERIFIED, four ways, and by an exhaustive state sweep. NOTHING FOUND

**(a) Model-based sweep, 819 sequences.** Built a real `ChartLayoutInfoPanel` and drove every
sequence of length 1, 2 and 3 over the nine app-realistic operations (actual/estimate x
turned / pointy / rectangular / cleared, plus `show_placeholder`), replaying the exact
`set_pitch_axis` -> `set_actual`/`set_estimate` pairing `tab_chart` uses. Invariant checked
against an INDEPENDENT model, not against the implementation: *the label must name the axis of
the pitch on screen when exactly one axis is shown, say the neutral "Patch pitch (mm)" when two
shown pitches run on different axes, and is unconstrained when nothing shows a pitch.*

```
sequences checked: 819
MISNAMED: 0
```

I could not construct a state, reachable or not, in which the row names a FALSE axis for a
pitch actually on screen. `/tmp/r7/panel_model.py`.

**(b) The two writers agree on the orientation.** The only vote for the actual column is
`chart_is_flat_top(ti2)` and the only source of its patch size is `_chart_patch_size_mm`, and
both resolve through the SAME `recipe_is_flat_top(recipe)` on the SAME `channels.json`. There
is no second opinion to drift. (`ui/tabs/tab_chart.py:17911-17913` and `:17944-17952`.)

**(c) Every path that empties a column now withdraws its vote**, and every path that fills one
votes first: `_update_layout_info` votes inside the `try` immediately before `set_actual`, and
its two failure exits both call `clear_actual`; `_predict_layout_info` the same with
`clear_estimate`. There is no reachable `set_actual`/`set_estimate` without a fresh vote.

**(d) Four mutations, each proven to land (grepped after editing, `__pycache__` cleared), each
caught:**

| mutation in `ui/chart_layout_info_panel.py` | result |
|---|---|
| baseline | 49 passed |
| the abstain line deleted (K1(b) restored) | 1 failed |
| the two `_forget_pitch_axis` calls deleted (K1(a) restored) | 1 failed |
| "Column pitch"/"Row pitch" swapped | **4** failed |
| the abstain condition inverted | 2 failed |

All four restored; `git diff --stat` clean.

Correction to round 6, recorded so it is not re-derived: K1 said `show_placeholder()` is
reached from `_update_margin_inspector` at tab_chart.py:18012 and :18053. Those two calls are
on `self._margin_panel`, a different widget. The layout panel's only `show_placeholder` caller
is `_predict_layout_info:17837`.

---

## L5 — the mesh test still cannot see a read box of the RIGHT SIZE in the WRONG PLACE. K12's fix closed one axis of a two-axis hole

K12 added two assertions to `test_the_scanner_mesh_is_told_the_orientation_by_a_resolver`: that
the read box is inset equally on both axes, and that it covers `sample_frac` of the slot AREA.
Both are computed from `max(bx) - min(bx)` and `max(by) - min(by)` -- the box's WIDTH and
HEIGHT. Neither reads where the box IS.

Mutation **M-B**, one line in `ui/scan_grid_marquee.py::_cell_uv`:

```
-            iu, iv = u + mg / asp, v + mg
+            iu, iv = u, v
```

The box keeps its exact size and is shoved flush into the slot's top-left corner. Measured on
the same turned honeycomb the test builds, sample fraction 0.60, unit-square coordinates:

```
            left     right    top      bottom      (inset from the slot edge)
shipped   +0.040444 +0.040444 +0.040444 +0.040444
M-B       +0.000000 +0.080889 +0.000000 +0.080889
```

i.e. the drawn read zone is displaced by a full inset, out of the hexagon and over the
neighbours, on every cell of every chart. Knut's #119 rule -- "the same distance to the patch
border on all four sides" -- is violated on all four sides at once, and the two new assertions
are both green because width and height never moved.

**What the suite sees, with M-B in place and proven to have landed:**

```
tests/test_the_honeycomb_can_be_turned.py                    49 passed
the 25 test files that mention the marquee               1,038 passed, 17 skipped
the whole everyday tier                     12,487 passed, 310 skipped, 4 xfailed
```

**Zero.** Reverted; `git diff --stat` clean.

**Why it matters and why it is not a blocker.** The shipped arithmetic is right (measured
above: four equal insets), and this array only DRAWS -- scanin's real sampling comes from the
`.cht` writer, not from here. So nothing prints or measures wrong today. But the alignment mesh
is the picture the user judges Sample area by, and a one-line slip in the two variables the
test does not read would show a read zone lying over the neighbouring patch while the app
reports the area as correct. K12's own reasoning ("the sample box is the half of the mesh that
decides whether the read stays inside the hexagon") applies verbatim to the half it left
uncovered. Fix: assert the four insets individually against the slot, not the box's size.
Confidence: certain (mutation measured, three test scopes run, reverted).

---

## L6 — K1's fix CONFIRMED IN THE REAL WINDOW, on the exact stages round 6 photographed the fault on. NOTHING FOUND

Real app, real screen, sandboxed settings (`CHROMIQ_SETTINGS_FILE`,
`CHROMIQ_PRESETS_DIR`, `custom_output_path` under the session scratchpad; the driver refuses
to start without all three). Driver `<scratchpad>/drive_r7.py`; window pictures and
`stages.json` in `~/Desktop/ChromIQ-hex-proof/13-seventh/`.

| stage | chart on screen | current settings | pitch row NAME | on screen | estimate | round 6 said |
|---|---|---|---|---|---|---|
| L6-S0 | (none) | turned | **Column pitch (mm)** | -- | 10.39 | Column pitch |
| L6-S1 | turned | turned | **Column pitch (mm)** | 10.41 | 10.39 | Column pitch |
| L6-S2 | turned | pointy (auto-update OFF) | **Patch pitch (mm)** | 10.41 | 10.39 | Patch pitch (correct: two axes) |
| L6-S3 | turned | turned | **Column pitch (mm)** | 10.41 | 10.39 | Column pitch |
| L6-S6 | turned | CR30 **Rectangular** | **Column pitch (mm)** | 10.41 | **--** | **Patch pitch -- K1(b)** |
| L6-S7 | turned | **i1** rectangular | **Column pitch (mm)** | 10.41 | **--** | **Patch pitch -- K1(b)** |
| L6-G1 | turned | **GUIDED** | **Column pitch (mm)** | 10.41 | **--** | **Patch pitch -- K1(b)** |

`L6-S6-window.png` reads, verbatim, where round 6's `S6-panel.png` read "Patch pitch (mm)":

```
Patch size (mm)      13.89×12.02       12×12
Column pitch (mm)          10.41           —
```

And J7's veto still holds where it must: L6-S2, two shown pitches on opposite axes, prints the
neutral "Patch pitch (mm)".

**The label agrees with the ink.** `L6-S6-preview-zoom.png` is the preview enlarged from the
same window capture: the patches are FLAT-TOP, columns run straight down the page, and
13.89 x 3/4 = 10.42 mm, which is the 10.41 the row now calls a COLUMN pitch. The row pitch on
that sheet is the 12.02 in the size cell above it, exactly as G10 originally complained.

**With a control render.** `L6-ink-turned.png` and `L6-ink-pointy-CONTROL.png` are the same
crop of two charts built from the same 345-patch `.ti1` at 300 dpi, identical in every setting
but the turn:

```
pointy (CONTROL)  slot 142x122 px   strip A: 26 patches, 2 distinct x  -> zigzag
turned            slot 123x142 px   strip A: 22 patches, 1 distinct x  -> straight
```

**A note on the pictures, because the first set was worthless.** `screencapture(1)` has no
Screen Recording permission in this session: it returns the desktop picture with every window
missing, and my first nine "window shots" were the owner's wallpaper at 7.3 MB each, saved
past a file-size assertion that proved nothing. (They were deleted; the wallpaper is a
personal photograph and is not in the proof folder.) `QScreen.grabWindow(0)` goes through a
different path and DOES composite the windows -- verified on a magenta probe window, 2,157,215
matching pixels at the right place in a 3456x2234 grab. Every shot filed is now that,
cropped to the window frame, and each is checked against the window's own render before it is
saved (mean absolute difference 13-20 of 255, i.e. the same picture plus a title bar).

---

## L7 — Duplicate run over a turned chart carries the turn. NOTHING FOUND (closes one of round 6's K14 gaps)

`Project.duplicate_run` copies the run and carries `create_chart_ui` (which holds the layout
recipe) through the exhaustive `DUPLICATE_META_CARRY` partition. Driven headless on a real
`Project`:

```
create_chart_ui carried: {"engine": true, "layout_recipe": {... "hex_flat_top": true ...}}
hex_flat_top in the copy: True
channels.json copied: True      chart_is_flat_top(copy .ti2): True
```
Both the stored recipe and the copied sidecar say turned, so the copy rebuilds the same sheet
and everything downstream that asks the chart its orientation gets the right answer.

---

## L8 — **THE STRIP LETTERS ARE CUT BY THE PATCHES ON EVERY TURNED SHEET.** The owner's report is confirmed, on the sheet he saw and on 31 of 49 configurations. RELEASE BLOCKER (paper)

Reproduced first on the app's OWN output -- `R7-Turned.tif`, built on screen in section L6,
A4, CR30, hexagonal, turned, 345 patches, 300 dpi:

```
label band bottom   74 px      topmost patch box   71 px
```

and the picture settles what that means. `L8-zoom-letterA-TURNED.png` is the letter A at 6x
from that file: **its legs stop dead on the hexagon's top edge.** The patches are painted
after the labels, so an overlapping letter is not sitting ON the ink, it is CUT OFF by it.

`L8-letters-side-by-side.png` puts four letters from two charts next to each other at 5x:
turned-A (raised strip, **cut**), turned-B (lowered strip, whole), pointy-A (whole),
pointy-B (whole).

### The metric, and the two false readings it took to get right

Per strip: the vertical extent of the label's own ink, with every patch polygon masked out
and dilated 3 px so an anti-aliased hexagon edge cannot be read as a letter. Every strip label
is a capital in one font at one size, so on a healthy sheet they all render to the same height;
a letter the patch has covered is SHORTER. Reference = the 75th percentile of the strip
heights (the median fails when half the strips are cut, and the maximum fails because a round
letter like "Q" overshoots by 5 px -- that one produced a confident "the fix made A4R worse"
which the picture then denied).

### Measured, shipped tree (worktree at a70b0c6e), 49 configurations

**Every pointy control is clean, and so is the SpectroScan honeycomb.** Every turned
configuration at the default patch scale and a top-anchored patch area cuts the letters of
exactly the RAISED strips -- half of them:

| configuration (turned) | strips cut | letter lost |
|---|---|---|
| A4, the owner's own recipe | 8 / 15 | 0.68 mm |
| A4R / LetterR | 11 / 22 | 0.68 mm |
| A3, 11x17, Legal, Letter, A2, A3+, 4x6, A2 landscape | half of them | 0.68 mm |
| 690 and 1035 patches (labels past Z) | 8 / 15 | 0.68 mm |
| 200 dpi / 600 dpi | 8 / 15 | 0.89 / 0.57 mm |
| bold labels, row indicators on or off, strip gap 5 mm, spacers colored/white/bw | 8 / 15 | 0.68 mm |
| **patch scale 1.5 / 2.0** | 5 / 10, 4 / 7 | **1.44 mm** |
| **label size 6 mm** | 8 / 15 | **1.86 mm** |
| **strip label offset +3 mm** | 8 / 15 | **3.64 mm** |
| **top margin 2 mm** | 3 / 15 | **4.57 mm** |

**Where it is worst:** a big label (6 mm) or a positive strip-label offset, where nearly half
the letter goes; and the small top margin, where 4.57 mm of a 4.7 mm letter is gone.

**What escapes it, measured:** patch scale <= 0.75; any patch-area alignment other than
top-\* (center and bottom clear it by 1.0-2.5 mm); a NEGATIVE strip-label offset; a top
margin of 10 mm or more; "Use instrument margins" off; **edge spacers on** (the leading
spacer pushes the ink 8 px down -- photographed, `L9-edgespacers-SHIPPED.png`); every pointy
chart; and the SpectroScan honeycomb.

The mechanism is the one the coordinator names: `geometry.placement` shifts the block down by
`g.hxeh`, which on a pointy sheet is the apex overshoot (plen/6 = 1.73 mm, and the slot top
really is that far below the patch-area top) but on a turned sheet is the STAGGER reserve
(plen/4 = 3.0 mm) that the raised strips come straight back up through. I could not break that
reading: the pointy control clears on every one of the 15 papers and both dpi values, the
turned one clears on none of them, and the strips that are cut are exactly the raised half.

Severity: **RELEASE BLOCKER.** It is on the paper, on the default recipe, on every paper size,
and it damages the labels the user reads the chart by.

---

## L9 — the coordinator's fix, measured against the same 49 configurations. It fixes 25 of them and leaves 4 real ones cut; it costs capacity on two papers only

The working tree carries an uncommitted +38-line change to
`workflow/layout_engine/geometry.py` (`if _turned_hex(g) and txhi > 0: mints = max(mints,
txhi + g.strip_indicator_gap)`). I copied it into a second worktree so the comparison is a
clean A/B against a70b0c6e and cannot be disturbed by further edits.

```
FIXED 25   STILL CUT 4 (+2 unmeasurable)   NEW 0   CLEAN IN BOTH 18
```

**Fixed, photographed:** the whole default family -- every paper, both dpi values, 30 to 1035
patches, bold labels, row indicators, strip gap, all spacer modes, top margin 2 mm, and the
top-right alignment. The A4 baseline goes from letters cut by 0.68 mm on 8 of 15 strips to
glyph heights {55, 56, 57} on all 15, i.e. no outlier at all.

**Still cut after the fix, each confirmed by looking:**

| configuration | before | after | picture |
|---|---|---|---|
| label size 6 mm | 8/15, 1.86 mm | **8/15, 1.86 mm (unchanged)** | `L9-indicator6mm-AFTER.png` -- A, C and E are cut in half |
| strip label offset +3 mm | 8/15, 3.64 mm | **8/15, 2.62 mm** | `L9-labeloffset3-AFTER.png` -- only the tops of A, C, E survive |
| patch scale 1.5 | 5/10, 1.44 mm | **3/10, 0.42 mm** | `L9-pscale1.5-AFTER.png` -- A and C still clipped |
| patch scale 2.0 | 4/7, 1.44 mm | 2/7, 0.42 mm | (same shape) |

All four are plain user settings in Expert Options. The fix moves the patch area below the
label BAND, and these are the cases where the band's own height is not what the letter needs
(a bigger label, a label pushed down into the gap, or a taller patch).

**Two rows I will not claim either way:** `edge spacers on` and `indicator rotation 90` came
back "still cut" from the metric and CLEAN from the picture
(`L9-edgespacers-AFTER.png`, all of A..E whole). The coloured ring of an edge spacer is drawn
partly ABOVE the first patch, outside the polygon mask, and the metric counts it as a 133 px
"letter". Recorded so the number is not quoted as a finding.

**Capacity cost, measured over all 15 papers x both orientations through
`geometry.patches_per_sheet`:**

```
A2  turned  1728 -> 1692   (-36, -2.1 %)
A4R turned   384 ->  360   (-24, -6.3 %)
everything else unchanged; every POINTY figure identical
total 20185 -> 20125  (-0.30 %)
```

**Margins after the fix:** the block moves down 12 px on A4, so the bottom clearance falls
from +2.97 mm to +2.04 mm inside the 6 mm bottom margin. Still inside. No configuration
measured put ink past a margin in either tree.

---

## L10 — what else is placed relative to `y0_first` rather than to the real ink. The bottom is NOT a mirror; the row numbers ARE half a pitch out

Answering the second question directly, by reading the placement code and measuring the sheet.

**1. The bottom reserve and the trailing edge: NOT a mirror, and no violation.**
`compute` reserves `2 * g.hxeh` for the block and `placement` spends only one `hxeh` at the
top, so the lowered strips' 3.0 mm run downward into a reserve that was already made for
them. Measured on A4, page 3508 px, 6 mm bottom margin:

```
                 topmost ink   lowest ink   top clearance   bottom clearance
shipped turned      71.0        3402.0        +0.1 px        +35.1 px (+2.97 mm)
shipped pointy      70.5        3425.3        -0.4 px        +11.8 px (+1.00 mm)
with the fix        83.0        3413.0       +12.1 px        +24.1 px (+2.04 mm)
```
Nothing is placed at the bottom that the ink can reach: the page text sits in the bottom
margin at `text_edge`, below the reserve, and the lowered strips stop 2 mm short of it.
(The pointy sheet's -0.4 px at the top is a rounding of the apex against `margin_t` and is
identical on master; it is not this branch's and it is not a millimetre.)

**2. The strip labels are the ONLY thing placed from `place.leader_top`.** One use in
`raster.py`, line 1290: `_lbl_top = px(place.leader_top + strip_label_offset_mm)`. Nothing
else in the renderer reads it, so no other furniture inherits the fault.

**3. The row numbers ARE misaligned on a turned sheet, and it is inherent, not a bug in this
fix.** `raster.py:1414` draws them `if _row_band_px > 0 and p == 0` -- once, against the
LEFTMOST strip. On a turned honeycomb the raised and lowered strips are offset by half a slot
pitch, measured on the owner's own sheet: A1 top y = 71 px, B1 top y = 142 px, a difference of
**71 px = 6.01 mm = exactly half the 142 px row pitch**. So "row 4" is level with A4, C4, E4
and sits on the seam between B3 and B4. `L10-rows-and-markers-TURNED.png` shows it. A POINTY
honeycomb does not have this: its strips all start at the same y and the numbers line up for
every one. This is a consequence of the turn itself, not of the placement shift, and it is
NOT made better or worse by the fix -- but it is a number beside a patch that does not name
that patch, and the changelog's "a ruler lies along it" claim is about the strip, not the row
band, so somebody should decide whether the row numbers should follow the strip they are drawn
against or be dropped on a turned sheet.

**4. The clip band** is a full-height band inside the clip-side margin (`geometry` puts the
patch origin at `margin_l` and the band inside it); it has no vertical anchor to `y0_first`
and no configuration measured showed patch ink inside it.

**5. Helper markers** are computed by `geometry.helper_marker_lines_mm` from the patch
geometry itself, not from `y0_first`, and they follow the ink: with markers on, the fixed tree
still measures no cut letters (heights {55, 56, 57}) and the ticks land on the patch centres.
One cosmetic thing worth a look, which is NOT new and not the turn:
`L10-helpermarkers-AFTER.png` shows the top ruler ticks drawn THROUGH the strip letters (the
tick band at `helper_marker_edge` 2 mm and the label band at `text_edge_top` 4 mm overlap).

**6. The Measure tab's overlay** reads the recorded patch rects out of `channels.json`, which
are the real slots, so it follows the ink and not the placement: round 6 measured 690 of 690
patches matching their `.ti2` values to 0.50/255 on a two-page turned chart, and round 5
photographed the overlay on real turned ink.

---

## Gate

`QT_QPA_PLATFORM=offscreen pytest --runslow -n auto`, clean tree at a70b0c6e:

```
12629 passed, 167 skipped, 4 xfailed in 217.77s (0:03:37)     exit 0
```
No worker-down banner, no `Fatal Python error`, no `Timeout (0:0X:XX)!` dump.

**One caveat, stated because the project's own rule covers it.** I applied a one-line mutation
to `ui/dialogs/scanin_dialog.py` (L-note below) during the last ~3 % of that run, which
CLAUDE.md forbids: an edit mid-run shifts `inspect.getsource` line offsets. The run came back
green anyway, so nothing was hidden by it, but the run should be repeated on a still tree
before it is quoted as the release gate. It is in any case superseded: the tree has changed
since.

## L-note — the OTHER source-text test is narrow, but the suite is not blind

`tests/test_the_honeycomb_spacer_is_a_ring.py::test_the_scanner_dialog_passes_the_orientation`
is the same shape as J9's self-validating test: `assert "flat_top=flat_top" in src`. I mutated
the CALL SITE instead (`scanin_dialog.py:4309`, `_flat` -> `False`), which leaves that
substring intact:

```
tests/test_the_honeycomb_spacer_is_a_ring.py            92 passed   (blind)
tests/test_the_honeycomb_can_be_turned.py                1 failed   (caught)
```
So the assertion is decorative but the behaviour is guarded, by the sibling file's real
dialog. A note, not a finding. Mutation reverted; `git diff --stat` on that file is empty.

---

# WHAT I DID NOT MEASURE, PLAINLY

* **The gate on the current tree.** The coordinator is editing `geometry.py` and
  `test_the_honeycomb_can_be_turned.py` as I write, and asked me to stop running pytest. The
  only gate figure I have is for a70b0c6e, with the caveat above. **The fix in L9 has not been
  through a gate at all as far as I know, and it changes capacity on two papers, so the
  built-in preset tests and every capacity test are the ones to watch.**
* **Whether the four still-cut cases in L9 matter enough to hold a tag.** That is a judgement
  about Expert Options, not a measurement.
* **The row-number misalignment (L10.3) as a decision.** I measured 6.01 mm; whether the row
  band should follow the strip it is drawn against, or be suppressed on a turned sheet, is
  Basti's or Knut's call and touches `per_target_settings` / the #164 marker geometry which is
  marked SETTLED.
* **Check & Refine over a measured turned run**, and **the patch-set editor** -- both still
  untouched since round 6 named them. No instrument, no measurement.
* **Multi-page turned charts' SECOND page label band.** Every measurement above is page 0.
  The band is computed once for the chart, so I expect page 2 to behave identically, but I did
  not build a two-page chart for this question.
* **The spacer-on and rotated-label rows of the L9 table**, which my metric cannot read (the
  edge spacer's ring is counted as a letter). The pictures say clean; the numbers say nothing.
* **Printing.** Nothing here went through `lp`, a PostScript path or a real printer.

---

# RELEASE VERDICT: **HOLD**

**Blocker: L8 — the strip letters are cut off by their own patches on every turned sheet.**
It is on the paper, on the default recipe, on all 15 paper sizes, at both resolutions, from 30
patches to 1035. Half the strips on every sheet lose 0.68 mm of their letter at the defaults,
and 1.9-4.6 mm on four ordinary Expert settings. Photographed on the app's own output and
against a pointy control that is clean everywhere. This is exactly the standing orders'
"anything that prints wrong on paper".

The fix now in the working tree removes it for 25 of 49 configurations, introduces nothing
new, and costs 0.30 % of capacity in total (A2 and A4-landscape turned only). It leaves four
reachable settings still cutting letters, three of which it improves and one -- **label size
6 mm** -- which it does not touch at all. Whether those four hold the tag is a judgement call;
they are Expert Options rather than the default sheet, and I would ship with them named,
provided the fix itself passes a gate on a still tree.

**Second item, by the standing orders' own rule rather than by paper: L3.**
`test_the_snapshot_was_taken_before_collection` is green in the exact world it exists to
forbid, and under that world the containment fixture becomes the delivery mechanism for a
permanently poisoned worker. "Any test proved not to catch the fault it exists for" is on the
fix-without-asking list. The replacement is one assertion, and I proved it discriminates.

**Ships-with-it, named:** L2 (the modal repair silently reverts a module- or session-scoped
patch; nothing in the suite does that today, but nothing warns the next person either), L5
(the mesh test cannot see a correctly-sized read box in the wrong place), L10.3 (the row
numbers are half a pitch out on a turned sheet), and the two K-items round 6 already deferred.

**What I could NOT break, said plainly:** the pitch row (819 sequences, four mutations, nine
on-screen stages, Manual and Guided), the modal containment (33 failures swallowed), duplicate
run, the bottom margin in either tree, and the turned honeycomb's own ink -- straight strips,
one x per strip, patch colours matching the data.

## Worktrees left in place

`<scratchpad>/wt-before` (a70b0c6e, clean) and `<scratchpad>/wt-after` (a70b0c6e + the
uncommitted geometry change) are still there, because they are what the L9 A/B was measured in
and the coordinator may want to re-run it. `git worktree remove` them when done.

---
## FIXES APPLIED for round 7 (2026-09-09)

**L8 / L9 — the strip letters, fixed properly this time.** The first attempt reserved the
label BAND (`label_band_mm`) and L9 measured four ordinary settings it did not cover. The
reserve now uses where the labels' INK ends, which only the renderer can say:

* `raster._furniture_reserves_mm` returns a third figure, `label_ink_bottom_mm` = the user's
  `strip_label_offset_mm` + the band's DRAWN height (`ind_px`, the font's full pixel size,
  where the reserve measures the ink bbox of "W8") + the underline.
* `chart.py` now passes `strip_label_offset_mm` into the geom kwargs. It never did, which is
  why an offset of +3 mm printed 2.46 mm of letter on the ink. Read by
  `_furniture_reserves_mm` alone, so no other layout moves.
* `geometry._top_reserve_for_a_turned_hex` raises the top reserve to
  `leader_top + label_ink_bottom_mm + 0.5 mm`, in BOTH branches of BOTH functions.

Measured on the six configurations, before -> after:

| | first fix | now |
|---|---|---|
| default | +0.76 | +0.51 |
| explicit 6 mm label | **-1.44** | +0.51 |
| strip-label offset +3 mm | **-2.20** | +0.51 |
| underline (found here, in NO round's list) | **-0.25** | +0.51 |
| patch scale 1.5 | 0.00 | +0.51 |
| patch scale 2.0 | 0.00 | +0.51 |

The underline case was not in L9's four. It was found by measuring the axes rather than the
four named rows, which is the reason to cross them.

Five parametrised tests added, one per setting. Mutating `ink_bottom` back to the band fails
two of them; the earlier pair still fail on their own mutations. The 76-page pointy manifest
is byte-identical after both fixes.

**L3 — the eighth self-validating test, replaced.** `test_the_snapshot_was_taken_before_
collection` asserted `recorded is current`, which the repair in its own setup had just made
true. It now compares every recorded object's type against a FRESH INTERPRETER's, which the
suite cannot have touched. Proven to discriminate: with the snapshot moved late and a
throwaway file patching `QMessageBox.warning` at import time, the old test passed and the new
one fails naming the `staticmethod` it found.

**L10.3 — the row numbers are half a pitch out on a turned sheet.** Not fixed: it is inherent
to the turn, it is unaffected by either fix, and where a row number should sit when the two
strips it names are 6 mm apart is Basti's call, not mine. Carried to him with the release.

**L2 and L5 — carried to 4.2.2.** L2 is latent (nothing patches a modal at module scope
today). L5 is a second axis of the mesh guard, not a fault in the app.

### The widened cross, after both fixes: 9,216 charts

Paper x patch scale x label size x label offset x underline x label rotation x alignment x
spacer mode x patch count x orientation.

```
letters on ink: 802   ->   turned 0,  pointy 802
```

**Not one turned sheet in 4,608 prints a letter on a patch.** Every remaining collision is a
POINTY chart, and pointy is where a rotated label meets a label offset:

```
A4R / Letter, offset +3 mm, underlined, label rotated 90, 690 patches
   with the fix    band 160 px, ink 91 px   -5.84 mm
   at a70b0c6e     band 160 px, ink 91 px   -5.84 mm      <- identical
   turned, same settings:  -6.52 mm  ->  +0.51 mm
```

Measured, not argued: the pointy figure is the same byte for byte with the change stashed, so
this is shipped behaviour and not this branch's. **DEFERRED to 4.2.2 and named**: a rotated,
offset strip label overlaps the first patch on a pointy chart. It wants the same treatment
(reserve what is drawn, not the band), but changing a pointy layout under a stable tag is
exactly what the standing orders forbid.

Margins over the same 9,216: tightest top +0.011 mm, tightest bottom -0.020 mm, both on A3 at
patch scale 0.75, and both identical before the change -- the box's own rounding.
