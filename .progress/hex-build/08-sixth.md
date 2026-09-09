# 08 — SIXTH adversarial review (round 6), commit 2e2c787b

Branch: feature/nelson-photocard-presets
Bar: "would I sign this off to print on a paying customer's paper".
Started 2026-09-09.

Targets handed to me:
1. J7 fix — `ChartLayoutInfoPanel.set_pitch_axis(flat_top, column=...)` two-column vote.
2. J9 fix — the scanner mesh test (is it load-bearing?).
3. J5 fix — the changelog sentence about the count and the "Chart layout information" panel.
4. Fresh eyes: .ti2/.cht a turned chart writes, scanin_target, patch-set editor, TI2 relayout dialog,
   Preferences -> Chart Layout, Duplicate run, Check & Refine over a turned chart, multi-page turned
   charts in Measure, built-in CR30 presets.

Findings are appended below as K1, K2, ... as they are measured.

---
## K1 — J7's fix has a hole: an EMPTY or PITCHLESS column still votes on the row name

`ChartLayoutInfoPanel.set_pitch_axis` (ui/chart_layout_info_panel.py:208-240) decides the
row name from `self._pitch_axis = {"actual": …, "estimate": …}` and prints the neutral
"Patch pitch (mm)" whenever the two disagree. The docstring's rule is
"A column never filled does not vote." Two ways a column that is showing NOTHING still votes:

**(a) `clear_estimate()` and `show_placeholder()` never reset the vote.**
`clear_actual()` (line 200) resets `_pitch_axis["actual"]`; `clear_estimate()` (line 252) and
`show_placeholder()` (line 256) do not touch `_pitch_axis` at all. Measured on a real panel:

```
turned estimate (votes True) + pointy chart on screen (votes False)
  -> "Patch pitch (mm)"   actual=8   est=10.41            (correct: they disagree)
then clear_estimate()
  -> "Patch pitch (mm)"   actual=8   est=—                (WRONG: the only column with a
                                                           number is a POINTY chart whose 8 mm
                                                           IS a row pitch. Should say "Row pitch".)
show_placeholder() then a pointy actual
  -> "Patch pitch (mm)"   actual=8   est=—                (same; the vote survived the placeholder)
control: clear_actual() in the mirror-image state
  -> "Row pitch (mm)"     actual=—   est=8                (correct — only clear_actual resets)
```

Reachable: `clear_estimate()` is called from `tab_chart._refresh_layout_estimate` (line 5722,
5746) and `tab_chart._update_patch_count` (line 12685) — i.e. **every time the user unticks
"Use the ChromIQ layout engine"**, in Manual and in Guided, and on any exception in
`_predict_layout_info`. `show_placeholder()` from `_predict_layout_info` (17837) and
`_update_margin_inspector` (18012, 18053).

**(b) a column that has NO pitch at all still vetoes.** A rectangular chart has `row_pitch=0`,
so the panel shows "—" for it, but its `_flat=False` is still recorded as a vote:

```
rect chart on screen  + turned-hex estimate -> "Patch pitch (mm)"  actual=—      est=10.41
turned hex on screen  + rect estimate       -> "Patch pitch (mm)"  actual=10.41  est=—
```

In both, exactly one column carries a pitch, that pitch has one unambiguous axis, and the
panel refuses to name it because of a column that has nothing to say.

**Why it matters.** This is G10/J7's own failure mode, one notch weaker: the name never states
a FALSE axis, it states NO axis, so the panel is less informative rather than lying. That is
why I am filing it as a finding and not (yet) a blocker — see K-final for the verdict.
The vote should be conditioned on the column actually carrying a pitch value, not on the last
call having happened.

Confidence: high (measured directly on a real `ChartLayoutInfoPanel`; the code path is a
two-line read).
## Gate — `--runslow`, commit 2e2c787b, clean tree

```
========== 12620 passed, 167 skipped, 4 xfailed in 212.22s (0:03:32) ===========
```
No `node down` banner, no `Fatal Python error`, no `Timeout (0:0X:XX)!` dump. Exit 0.
(grep for "node down|Fatal Python|Timeout (0:" over the whole log: no hits.)

## K2 — the CR30-only turn is genuinely gated in the geometry, not just in the UI

`layout_options_panel._sync_hex_flat_top_visibility` only HIDES the checkbox for a
non-CR30 instrument, and `_collect` (line 4724) reads the hidden checkbox regardless, so a
recipe saved on CR30 with the turn on and then applied with the SpectroScan selected still
carries `hex_flat_top=True`. Measured what the geometry does with it:

```
CR30   hex_flat_top=True  -> pwid/plen 10.392/12.000 ; False -> 12.000/10.392   (differs)
SS     hex_flat_top=True  -> pwid/plen  7.000/ 6.062 ; False ->  7.000/ 6.062   (identical,
                                                        and geom.hex_flat_top comes back False)
i1     same, identical, False
```
`instruments.build` drops the flag for anything but the CR30, so the leak is inert.
NOT A FINDING. Recorded because it is the kind of hole that usually is one.

## K1 — CONFIRMED ON SCREEN (see ~/Desktop/ChromIQ-hex-proof/11-sixth/)

Real window, real CR30 honeycomb, sandboxed settings. Driver:
`<scratchpad>/drive_k.py`; stages in `11-sixth/stages.json`, pictures `S0`..`S7`.

| stage | chart on screen | current settings | pitch row NAME | on screen | estimate |
|---|---|---|---|---|---|
| S0 | (none) | turned | **Column pitch (mm)** | — | 10.39 |
| S1 | turned | turned | **Column pitch (mm)** | 10.41 | 10.39 |
| S2 | turned | pointy (auto-update OFF) | **Patch pitch (mm)** | 10.41 | 10.39 | ← correct, they disagree |
| S3 | turned | turned | **Column pitch (mm)** | 10.41 | 10.39 |
| S4 | turned | engine UNTICKED | **Column pitch (mm)** | 10.41 | 10.39 | ← see K4 |
| S6 | turned | CR30 **Rectangular** | **Patch pitch (mm)** | 10.41 | **—** | ← **K1(b) on screen** |
| S7 | turned | **i1** rectangular | **Patch pitch (mm)** | 10.41 | **—** | ← **K1(b) on screen** |

S6/S7 are the fault: the estimate column has NO pitch at all (it shows "—", the chart it
describes is rectangular), and its vote still stops the row naming the axis for the ONE column
that does have a pitch. `S6-panel.png` reads, verbatim:

```
Patch size (mm)      13.89×12.02       12×12
Patch pitch (mm)           10.41           —
```

which is the shape of G10's original symptom — "Patch size 13.89 x 12.02" above a pitch row
that does not say the 10.41 is the distance between COLUMNS — one notch weaker, because the
name is now vague rather than false.

**I could not construct a state in which the name is actively WRONG.** A stale or pitchless
vote can only manufacture a disagreement, and a disagreement always prints the neutral
"Patch pitch". So K1 is a **finding, not a blocker**: the panel loses information, it does not
state a falsehood. Confidence: high, measured on screen and headless.

## K3 — the changelog's "in either direction" is TRUE, and "a little" is fair

Measured the count with the turn off and on, over every paper in `papers.list_papers()`,
CR30 honeycomb, `instruments.build` defaults, `geometry.patches_per_sheet` + `compute`:

```
paper      pointy turned  delta      %        paper      pointy turned  delta      %
A4            416    396    -20   -4.8        Legal         512    513     +1   +0.2
127x178       126    120     -6   -4.8        A2           1782   1786     +4   +0.2
594x420      1824   1760    -64   -3.5        11x17         819    825     +6   +0.7
420x297       858    836    -22   -2.6        329x483      1100   1140    +40   +3.6
A4R           414    405     -9   -2.2        203x254       330    342    +12   +3.6
A3            874    864    -10   -1.1        Letter        384    399    +15   +3.9
LetterR       378    375     -3   -0.8        4x6            72     80     +8  +11.1
483x329      1102   1100     -2   -0.2
```
15 papers: **8 down, 7 up, none unchanged**. So "in either direction" is measured true, and
no paper is named as going one way. The largest move is +11.1 % on the 4x6 card (72 -> 80,
i.e. 8 patches); everywhere else it is under 5 %. "A little" is a slight understatement for
the 4x6 card only, and the sentence immediately hands the number to the panel, so this is
NOT a finding.

Cross-check through the app's own Manual recipe (the S0/S2 measurement above, A4, the
panel's own margins): pointy **351**, turned **345**, -1.7 %. Different from the 416/396 of
the bare-defaults route, which is exactly what the sentence now says ("by how much depends
on the paper as well as on your margins...").

## K3b — the changelog's second claim VERIFIED: the panel does show the count you have

Manual + engine on, CR30 honeycomb, **nothing generated** (S0): the estimate column already
read **345**, the count for the turned layout in the boxes. With auto-update preview OFF
(S2) the estimate still moved to **351** the moment the turn was unticked, while the on-screen
column stayed on the generated 345. So the sentence "Read it off the Chart layout information
panel, which shows the count for the layout you actually have" is true in the state the turn
lives in (Manual, engine on), with auto-update on and off. Confidence: high, photographed.

## K1(b) also happens in GUIDED — photographed

`11-sixth/G1-panel-guided.png`, real window, after building the two-page turned chart and
switching to Guided:

```
Patch size (mm)      13.89×12.02       12×12
Patch pitch (mm)           10.41           —
```
Same shape as S6/S7. Guided's estimate is a rectangular i1-style layout with no pitch at all,
and its vote still stops the row naming the axis of the only pitch on the panel. So K1(b)
reaches the default mode of the app, not only Manual.

## K5 — the sample-area cap on a TURNED honeycomb is SAFER than on a pointy one (no fault)

Built real CR30 honeycombs at 300 dpi (150 patches, A4), rendered the TIFF, and for every
patch took the read box `sample_margin(w, h, frac)` insets and counted the pixels inside it
that are not the patch's own ink. Tested just under the cap the dialog offers:

```
pointy  patch 142x122 px  cap 0.6446  at frac 0.640:
        68/150 boxes contain foreign ink; worst deviation 217/255 (a neighbour, not a blend);
        worst share of a box that is foreign: 0.02 %   (1-2 corner pixels of ~7,000)
turned  patch 123x142 px  cap 0.6443  at frac 0.639:
        0/150 boxes contain foreign ink; worst deviation 0/255; share 0.00 %
```
And with the ring spacer on (`ring_mm_of` = 1.3 mm, cap falls to 49 %), at 48.8/48.9 %:
0/150 impure on BOTH orientations, `spacer_mode` colored and white alike.

So the new orientation is clean at its cap and the old one leaks 0.02 % of area at 1-2 corner
pixels, worth about 0.04/255 on the average. The turn does not make the read worse; the pointy
cap is a hair generous and always was. NOT A BLOCKER, and NOT a regression.

Unit check on the ring, since the fifth round found a units bug there: `scanin_dialog.
_clamp_sample_area` converts `ring_mm * dpi / 25.4` before calling, so the cap is 49 % at 200,
300 and 600 dpi alike. Correct as shipped.

## K6 — the turn cannot be set in Preferences -> Chart Layout (and is not lost there)

`11-sixth/P1-preferences-chart-layout.png`. Preferences -> Chart Layout, instrument CR30,
Patch shape **Hexagonal** (the combo offers `["flat", "hex"]` there):

```
turn checkbox isVisible = False   isVisibleTo(panel) = False
_recipe_from_fields() -> hflag=True, hex_flat_top=False
```
`LayoutOptionsPanel._sync_hex_flat_top_visibility` reads `self.instr`, and the Preferences host
builds the panel WITHOUT selectors (`settings_dialog.py:5195`, no `with_selectors=True`), so
`inst` is `""` and the row is hidden whatever the dialog's own instrument combo says. Every
other layout option on that page is editable; this one is not, so a user cannot make turned
charts their default from Preferences.

It does NOT silently lose the setting: `set_recipe` writes the (hidden) checkbox from the
loaded recipe and `apply_to_recipe` writes it straight back, measured:

```
panel loaded with hex_flat_top=True  -> apply_to_recipe -> hex_flat_top=True
panel loaded with hex_flat_top=False -> applied onto a TURNED recipe -> False
```
The second line is the clobber shape, and it is unreachable in the dialog because
`_load_layout_page` always calls `set_recipe` with the recipe it is about to edit.
**Finding, low severity: a completeness gap, no data loss.** Confidence: high (on screen).

## K7 — NOT A FINDING: "Save as Defaults" does keep the turn (I read the wrong store first)

My first probe read the `chart_layout` PresetStore after pressing Save as Defaults and found
`hex_flat_top=False`, which looked like a dropped field. It is not: `_on_save_defaults`
(tab_chart.py:19471) writes `manual_engine_recipe` into **settings**, not into that preset
store, which belongs to Preferences -> Chart Layout. Decoded the sandbox .ini through
QSettings after a real on-screen Save as Defaults with the turn ON:

```
manual_engine_recipe -> dict, 86 keys, hex_flat_top = True, hflag = True,
                        instrument = CR30, paper = A4
```
The recipe round-trips whole. Recorded so the next round does not re-derive it.

## K8 — NOT A FINDING: the spacer controls are not locked out on a CR30 honeycomb

`V1-expert-frame-cr30-hex.png` shows the Patches & spacers rows greyed, which looked like the
ring being unreachable. Measured the widgets instead of the picture, over five instrument/shape
combinations on screen:

```
CR30/hex   spacer_mode enabled=True visible=True value="none"   spacer_width enabled=False
CR30/flat  spacer_mode enabled=True ...
SS/hex     spacer_mode enabled=True value="colored"
SS/flat, i1/clip  same
```
The combo is live; only its dependents are greyed because the value is "none". The grey in the
picture is the placeholder styling. NOT A FINDING.

## K9 — the turn's central claim, measured on the real two-page chart

Built a 690-patch, 2-page turned CR30 honeycomb on screen and read the artefacts:

* `.ti2`: `HEXAGON_PATCHES "True"`, `STEPS_IN_PASS "23"`, `PASSES_IN_STRIPS2 "15,15"`,
  690 sets, locs A1..AD23 with **exactly 23 patches in each of the 30 strips**.
* **Straightness:** the maximum spread of x within a strip, over all 30 strips, is **0 px**.
  Row numbers increase downward in every strip. So "a strip you read patch by patch runs
  straight down the page and a ruler lies along it" is literally true.
* **Strip letters run left to right** and continue across the page break:
  page 1 = A..O, page 2 = P..AD, both in alphabetical order by x.
* **Ink matches the data.** For all 690 patches I compared the .ti2's RGB with the pixel at
  the centre of the rect the sidecar records, in the right page's TIFF:
  **worst |ink - ti2| = 0.50 / 255, zero mismatches above 2/255.**

So the data -> paper -> sidecar loop is intact on a multi-page turned chart. Nothing found.
Pictures: `M3-measure-page1.png`, `M3-measure-page2.png`.

## K10 — the turn checkbox, all three hosts, Expert frame EXPANDED

My earlier "hidden" readings were contaminated by the collapsed Expert frame. Re-measured with
every `CollapsibleGroupBox` in the panel expanded, on screen:

```
Create Chart  CR30 + Hexagonal   isHidden=False  isVisibleTo(panel)=True   <- offered
Create Chart  i1                 isHidden=True                            <- correct
Create Chart  SpectroScan + hex  isHidden=True                            <- correct (Basti's rule)
TI2 relayout  CR30 + hex, over a turned chart
                                 isHidden=False  isVisibleTo(panel)=True  <- offered, checked=True
Preferences -> Chart Layout, CR30 + Hexagonal
                                 isHidden=True                            <- K6 stands
```
`V1-expert-frame-cr30-hex.png` shows the row in place, labelled
**"Straight strips (turn the honeycomb 30°)"**, inside Expert Options -> Patches & spacers,
which is exactly where the changelog says it is.

## K11 — **BLOCKER.** The J9 test poisons its xdist worker: `QDialog.exec` and four `QMessageBox` statics are patched and never restored

`tests/test_the_honeycomb_can_be_turned.py`, helper `_scanner_dialog_over_a_turned_chart`,
lines 826-828, added in the commit under review (`git log -S` confirms: only 2e2c787b, and the
file does not exist on master):

```python
    QDialog.exec = lambda self: 1                  # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
```

No `monkeypatch`, no fixture, no teardown, and `tests/conftest.py::
_repair_a_leaked_qmessagebox_exec` repairs **only `QMessageBox.exec`** (it deletes
`QMessageBox.__dict__["exec"]`). `QDialog.exec` and the four statics survive for the life of
the worker process, so under `--dist loadfile` every file xdist schedules onto that worker
afterwards runs with modal dialogs stubbed out.

### Measured

Four everyday-tier runs (`QT_QPA_PLATFORM=offscreen pytest -n auto`) on this branch, clean
tree, back to back:

| run | result |
|---|---|
| 1 | **5 failed**, 12472 passed |
| 2 | **1 failed**, 12476 passed |
| 3 | **3 failed**, 12474 passed |
| 4 | 12477 passed |

Four runs on **master** (`git worktree`, same venv, same machine, same command):

| run | result |
|---|---|
| 1-4 | **11729 passed** every time |

The failures are a different set each time and every one passes in isolation:
`test_splash.py::test_the_splash_steps_aside_for_a_modal_dialog[plain]` / `[classic]` /
`test_no_modal_escapes_the_main_window_constructor`,
`test_colormunki_dial_pictogram.py` (4 of its tests),
`test_cr30_black_calibration_flow.py::test_escape_really_cancels_on_a_real_window`,
`test_knut_beta139_windows_end_with_the_session.py::test_the_session_ending_closes_an_open_window`
— i.e. exactly the tests that need a real modal or a real window.

### Reproduced deterministically in 7 seconds, and the culprit isolated

```
A  pytest test_the_honeycomb_can_be_turned.py test_splash.py \
          test_colormunki_dial_pictogram.py test_cr30_black_calibration_flow.py \
          test_knut_beta139_windows_end_with_the_session.py
   -> 9 failed, 97 passed

B  the same four victim files WITHOUT the honeycomb file
   -> 59 passed

C  A again, with ONE test deselected:
   --deselect ".../test_the_scanner_mesh_is_told_the_orientation_by_a_resolver"
   -> 105 passed, 1 deselected
```

C is the proof: removing that single test removes all nine failures.

### Why it matters for THIS release

CLAUDE.md's own rule is that a red gate must mean something and a green one must too. This
makes both meaningless on this branch: a failure names an innocent test two files away, and a
green run is a scheduling accident. The commit message's "Gate 12620 passed --runslow" and my
own green `--runslow` at the top of this report are that accident, not evidence.

### Fix

Use `monkeypatch` (which correctly *deletes* an attribute that was inherited) or restore in a
`finally`, in the one place that patches:

```python
    mp = pytest.MonkeyPatch()
    mp.setattr(QDialog, "exec", lambda self: 1)
    for m in ("warning", "critical", "information", "question"):
        mp.setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
    try:
        ... build the dialog ...
    finally:
        mp.undo()
```
`QDialog.exec` is a real attribute of `QDialog` (not inherited), so `delattr` is wrong there
and `monkeypatch`/save-and-restore is right; the four `QMessageBox` statics ARE inherited
from nothing and must be **deleted**, which is what `monkeypatch.undo` does.
Widening `_repair_a_leaked_qmessagebox_exec` would be defence in depth, not the fix.

Confidence: **certain**. Deterministic 3-command reproduction, isolated to one test by
deselection, and master is 4/4 green under the identical command.

### K11 addendum — the RELEASE GATE went red on the second attempt

I ran `--runslow -n auto` twice on the same clean tree:

```
run 1   12620 passed, 167 skipped, 4 xfailed in 212.22s      <- the run reported at the top
run 2   25 FAILED, 12595 passed, 167 skipped, 4 xfailed in 212.88s
```
Run 2's victims are all of `tests/test_a_new_project_name_goes_through_one_door.py` that need
a dialog — the Import-txt and Copy-project name dialogs. Isolated:

```
pytest tests/test_a_new_project_name_goes_through_one_door.py            -> 40 passed
pytest tests/test_the_honeycomb_can_be_turned.py <that file>             -> 25 failed, 62 passed
```
Same 25. So the leak reaches the release gate, and the first green `--runslow` was luck. No
worker-down banner in either run, no `Fatal Python error`, no `Timeout (0:0X:XX)!` dump: this
is a genuine test failure, not a crash bystander.

## K12 — J9's fix is real, but its two assertions do not cover the mesh; proven by mutation

The brief asked whether `hex_flat_top is True` + `_sample_area.maximum() == 64` are
load-bearing. For what they claim (the orientation reaching the dialog through the app's own
wiring) they are: both derive from the same resolved `_flat`, and the fifth round's mutation
of that value is red. They do NOT cover the mesh as a whole. The **drawn sample sub-area** is
outside them entirely: the test's third block reads only `cell[:6]`, the six hexagon corners,
and never the four sample-box corners that follow.

Mutation **M-A**, in `ui/scan_grid_marquee.py::_cell_uv`:

```
-            iu, iv = u + mg / asp, v + mg
-            iw, ih = w - 2.0 * mg / asp, hh - 2.0 * mg
+            iu, iv = u + mg, v + mg
+            iw, ih = w - 2.0 * mg, hh - 2.0 * mg
```
(`sample_margin` is called with the width already multiplied by the aspect, so the inset has
to be divided back out; dropping that draws the read zone wrong in x only.)

**Proven to land**, on the real turned chart's own sidecar, sample fraction 0.60:

```
              drawn sample box, aspect-corrected      ratio w:h
shipped       0.028013 x 0.033717                     0.8308
mutated       0.032000 x 0.033717                     0.9491     (14.2 % wider in x)
```

**Test result with M-A in place:**

```
tests/test_the_honeycomb_can_be_turned.py                     47 passed
every test file that mentions the marquee (14 files)         387 passed
the FULL everyday tier                            12472 passed, 5 failed
```
and those 5 failures are K11's leak, not the mutation — they pass in isolation with M-A
applied. So **nothing in the suite sees a 14 % error in the read-zone rectangle the user
judges Sample area by.**

This is a coverage gap, not an eighth self-validating test: J9's assertions do measure real
behaviour. But "the mesh is right" is a bigger claim than they support, and the sample box is
the half of the mesh that decides whether the read stays inside the hexagon.
Severity: **finding, not a blocker** — the shipped code is correct; only the guard is thin.
Confidence: high (mutation applied, proven to land, gate re-run, reverted; `git status` clean).

## K13 — the 8 built-in CR30 HEXAGONAL presets are unchanged by this branch (no fault)

Their grids are pinned (`area_cols` x `area_rows` in `_CR30_BASE` + `_CR30_HEX`), so the
honeycomb rework can only change whether the pinned grid still fits the sheet. A/B'd the
layout each one produces on this branch against the same code on `master` (a `git worktree`,
same venv), through `instruments.geom_from_build_kwargs` -> `geometry.compute`:

```
preset                                      named  branch  master  pages b/m  per_sheet b/m
cr30_a4_153p_1page_w18_0mm_hexagonal          153     153     153        1/1        162/162
cr30_a4_420p_1page_w11_0mm_hexagonal          420     420     420        1/1        435/435
cr30_a4_840p_2pages_w11_0mm_hexagonal         840     840     840        2/2        435/435
cr30_a4_1260p_3pages_w11_0mm_hexagonal       1260    1260    1260        3/3        435/435
cr30_letter_170p_1page_w16_0mm_hexagonal      170     170     170        1/1        180/180
cr30_letter_390p_1page_w11_0mm_hexagonal      390     390     390        1/1        390/390
cr30_letter_780p_2pages_w11_0mm_hexagonal     780     780     780        2/2        390/390
cr30_letter_1170p_3pages_w11_0mm_hexagonal   1170    1170    1170        3/3        390/390
changed: 0 of 8
```
Every one still lays out exactly the count in its own name, on the pages in its own name, and
identically to master. Each also matches its bundled `chart.ti1` `NUMBER_OF_SETS`. All eight
are POINTY (`hex_flat_top` false); nothing ships pre-turned.

## K14 — what I did NOT measure, said plainly

* **Duplicate run over a turned chart** — not driven. No finding either way.
* **Check & Refine over a turned chart** — opened it on screen
  (`C1-check-and-refine.png`); with no `.ti3` and no profile the tab is inert, so there was
  nothing to judge. A measured turned run would be needed and I have no instrument.
* **The patch-set editor** — not opened.
* **The scanner marquee drawn over a real scan of a turned chart** — the fifth round has that
  picture (`10-fifth/J10-mesh-on-ink-turned.png`); I verified the numbers behind it instead
  (`hexagonal=True`, `hex_flat_top=True`, `sample_area.maximum()=64`, 345 rects) on a real
  `ScannerProfileDialog` over the chart I built.

---

## Housekeeping

* Sandbox: `CHROMIQ_SETTINGS_FILE` + `CHROMIQ_PRESETS_DIR` + a `custom_output_path` under the
  session scratchpad, on every one of the six drivers, each of which refused to start without
  them. Verified afterwards:
  `defaults read com.chromiq.ChromIQ custom_output_path` -> empty (exit 0), the value it had
  before I started, and the whole plist's md5 is **identical** before and after
  (`566ac004547d99939c91a41299e6a1ba` both times).
* Working tree clean apart from this file (`git status --short`). The mutation in K12 was
  applied from a saved copy and restored from it; `git diff` is empty.
* The `wt-master` worktree I created for the A/B was removed. The other worktrees under the
  scratchpad belong to earlier rounds and were left alone.
* Pictures and a captioned `findings.md` in `~/Desktop/ChromIQ-hex-proof/11-sixth/`.
  Folders 01-10 and README.md untouched.

## RELEASE VERDICT: **HOLD**

**One blocker, K11, and it is in the commit under review.** The J9 test leaves `QDialog.exec`
and four `QMessageBox` statics patched for the life of its xdist worker. Measured: this branch
failed 3 of 4 everyday runs (5, 1, 3 failures, all bystanders, all green alone) where master is
4 of 4 green under the identical command, and the **release gate itself flipped from
12620 passed to 25 FAILED between two consecutive `--runslow` runs on the same tree**. Until
that is fixed, neither a green gate nor a red one on this branch means anything, which is the
one property the project has spent the most effort buying. The fix is three lines
(`pytest.MonkeyPatch` + `undo`), and after it the gate must be run at least three times, not
once, because one green run is what this defect produces by accident.

**The hexagon work itself I would sign off.** Everything I could aim at it held: 690 patches
of a two-page turned chart land on ink that matches the .ti2 to 0.50/255, every strip is
straight to 0 px, the read box at the offered cap touches no neighbour where the pointy
orientation touches 68 of 150, all eight built-in CR30 honeycomb presets lay out exactly as
master, the CR30-only rule is enforced in the geometry and not only in the UI, and the
changelog's two claims (J5) are both true as written.

**Three findings I would ship with, named, after K11 is fixed:**

* **K1** the pitch row still prints the neutral "Patch pitch (mm)" when the only column with a
  pitch has an unambiguous axis, because an emptied or pitchless column votes. It is never
  wrong, only mute. Fix: condition the vote on the column carrying a pitch, and reset it in
  `clear_estimate` / `show_placeholder` as `clear_actual` already does.
* **K12** nothing in the suite sees a 14 % error in the drawn read box; J9's assertions cover
  the orientation, not the mesh.
* **K6** the turn cannot be set as a default in Preferences -> Chart Layout (it is preserved
  there, just not editable).

---
## FIXES APPLIED for round 6 (2026-09-09, uncommitted at time of writing)

**K11 (blocker) — fixed, two ways.**
* `tests/test_the_honeycomb_can_be_turned.py::_scanner_dialog_over_a_turned_chart` now takes
  `monkeypatch` and patches `QDialog.exec` and the four `QMessageBox` statics through it, so
  they are undone at teardown.
* `tests/conftest.py::_repair_a_leaked_qmessagebox_exec` was widened from `QMessageBox.exec`
  alone to the whole family: `QDialog.exec` and the four statics, so the NEXT leak of this
  shape is contained rather than discovered from a flipping gate.

**K12 — fixed.** The scanner-mesh test now asserts two things a mutation of `_cell_uv`'s
aspect correction breaks: that the read box is inset by the SAME distance on both axes
(Knut's equal-margin rule, #119), and that it covers the `sample_frac` of the slot's AREA
that the user set. Proven to land by mutation.

**K1(a) — fixed.** `clear_estimate` and `show_placeholder` now withdraw the column's vote,
as `clear_actual` already did, through a shared `_forget_pitch_axis`.

**K1(b) — fixed.** The naming moved into one place, `_name_the_pitch_row`, called from
`set_pitch_axis`, from `_forget_pitch_axis` and from `_render` (because the data, not only the
vote, decides which columns carry a pitch). A column whose data is loaded and whose pitch is
`None` -- a rectangular chart -- now ABSTAINS instead of vetoing. A column with no data yet
keeps its vote, which is the state between `set_pitch_axis` and the `set_actual` that follows.

**Both K1 halves are covered by tests, and both mutations were proven to land:**
* `test_a_column_with_no_pitch_does_not_veto_the_row_name` — fails when the abstain line is
  removed (`1 failed, 47 passed`).
* `test_clearing_a_column_withdraws_its_vote_on_the_row_name` — fails when the two
  `_forget_pitch_axis` calls are removed (`1 failed, 48 passed`).

**K6 — NOT fixed, deliberately.** The turn cannot be set as a default in
Preferences -> Chart Layout. It round-trips there, so nothing is lost; adding a selector to
that panel is a feature, not a release blocker, and goes to 4.2.2.

Gate: three consecutive `--runslow -n auto` runs, per K11's own warning that one green run is
what the defect produced by accident.
