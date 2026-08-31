# 18 — Challenging the beta 6 batch

**STATUS: challenged** (2026-08-31 → 2026-09-01)

Adversarial review of the K1–K12 fixes in `18867d76` + `efe80bde`, before beta 6 is
tagged. No fixes are made here; this is analysis and evidence only.

Proof artefacts: `~/Desktop/beta6-challenge/` (see its `INDEX.md`).

---

## 0. Method / what was read

`CLAUDE.md`, `docs/reports/16-knut-beta5-findings.md` (1177 lines),
`16b-k12-cr30-tile-learning.md`, `17-knut-beta5-fixes.md`, and both fix commits
(`18867d76`, `efe80bde`) in full, before anything was measured.

**Everything behavioural below was driven in the real application on screen** —
real `MainWindow`, real theme (`apply_appearance`), real `LayoutOptionsPanel`,
against a scratch copy of the `Demo-Switching` demo project at
`/tmp/beta6work/w1/`. Drivers `d1.py`–`d5.py`, logs and screenshots in
`~/Desktop/beta6-challenge/`.

**Safety.** `CHROMIQ_SETTINGS_FILE=/tmp/beta6-challenge.ini` exported before any
import, *and* `core.settings.QSettings` replaced in every driver.
`custom_output_path` pointed at `/tmp/beta6work/w1`. Nothing under `~/ChromIQ`,
`~/ChromIQ/CR30-Test` or `~/Desktop/i1Profiler` was opened or written. The
instrument was not touched. Verified by value at the end — see §14.

---

## 1. The K3/K4 shield (`ui/tabs/tab_chart.py`)

### 1.1 BLOCKER — **K4 is not fixed. One ordinary panel edit brings it straight back.**

The shield has two halves with **different granularity**, and that is the whole
finding:

* **parameters** are shielded *per key* and released *per key*, by that row's own
  `value_changed` — `ui/tabs/tab_chart.py:13548-13558`;
* **UI state** is one all-or-nothing bucket, released in full by a single
  `LayoutOptionsPanel.changed` — `ui/tabs/tab_chart.py:13559-13564`:

```python
slot = lambda: self._chart_imposed.get("ui", {}).clear()
sig.connect(slot)          # panel.changed  ->  the ENTIRE ui shield is dropped
```

`ui:engine_recipe` is **where both indicator checkboxes live** (`show_strip_
indicators`, `show_row_indicators`, and also `instrument`, `layout_mode`, every
margin). So *any* edit anywhere in the layout panel un-shields all of them.

Driven on screen, `~/Desktop/beta6-challenge/d5-shield.log`, verbatim:

```
 1 unticked strip indicators, screen: {'instr':'CM','strip':False,'row':None,'margin_top':6.0}
 2 run2 -> run1 disk: {'printtarg-i':'CM','rec.instr':'CM','strip':False,...}
 3 back on run1 screen: {'instr':'CM','strip':True, ...}          <- the chart re-imposes
                disk : {... 'strip': False ...} shield: ([], ['engine_recipe'])
 4 nudged the top margin (an ordinary edit). shield: ([], [])     <- shield GONE
 5 left the tab. disk: {'printtarg-i':'CM','rec.instr':'CM','strip':True,'margin_top':7.0}
```

**Step 5 is Knut's K4, unchanged.** He unticked the box, it was filed, he came
back to the run, he moved one margin, he left the tab — and the box he unticked
is stored as ticked again. Nudging a margin is the single most ordinary thing a
person does in that panel, and Knut is testing *the layout panel* on *several
runs*: he will hit this.

**Severity: BLOCKER for beta 6.** The commit message claims K4 is fixed and
report 17 lists it as fixed with a mutation-proven guard. It is fixed only for
the exact gesture the new test drives (no panel edit in between).

### 1.2 BLOCKER — the store ends up holding **two disagreeing records of the same setting**

Same cause, worse symptom. `printtarg-i` (a parameter, shielded per key) and
`create_chart_ui.engine_recipe.instrument` (UI, released wholesale) are two
records of *the instrument*. Release one and not the other and the file
contradicts itself. Driven, `d3-shield.log`:

```
  state          : SCREEN = CM | printtarg-i='CR30' rec.instr='CR30'
  nudged margin_t: 7.0   shield: (['printtarg-i'], [])
  after leave    : printtarg-i='CR30'  rec.instr='CM'      <-- one file, two answers
```

`runs/run1/meta.json` now says the instrument is a CR30 *and* a ColorMunki.
Which one wins on the next load depends on the order of
`per_target_settings.apply` and `_apply_ui_state` inside `load_target_settings`
— i.e. on an implementation detail, not on anything the user did.

### 1.3 should-fix — **Restore Used Chart (§2 L5) IS shielded**, against the fix's own docstring

`ui/tabs/tab_chart.py:13509-13512` states:

> *"An explicit Restore Used Chart (§2 L5) is the case §10 blesses, and it does
> not come through here, so its values still reach the store as before."*

It does not come through `_on_target_changed` — but the shield armed by the
**preceding** run switch is still up, and is never cleared by a save. And
because Restore Used Chart restores *the very chart the run switch had already
displayed*, the value it writes is bit-identical to `from_chart`, so the
equality test always matches and the value is always reverted. Driven
(`d1-shield.log`, S2), calling the real `_restore_chart_settings` on the run's
own `.ti2`:

```
  S2c restored : True SCREEN = CM   shield still: ['printtarg-i']
  S2d after leave: printtarg-i='CR30'  rec.instr='CM'
```

L5's instrument reached the *recipe* record and was blocked from the
*parameter* record. §10's blessed case is now half-applied, and the store is
self-contradictory again.

### 1.4 should-fix — a user cannot choose the value the chart is already showing

Two conditions guard the shield, and the signal half is `value_changed`, which a
`QComboBox` does **not** emit when the entry re-selected is the current one.
Driven (`d2-shield.log`, S4): store `CR30`, chart imposes `CM`, the user picks
`CM` on screen, leaves the tab — the store still says `CR30`.

```
  S4b user selects CM (already shown); index 2 -> 2
      shield params: ['printtarg-i']
  S4c after leave : printtarg-i='CR30'      <-- the user's choice is discarded
```

The escape is a detour (pick something else, then CM). The new test file
acknowledges this in a docstring
(`tests/test_the_chart_sidecar_never_files_into_the_target.py:150`) — *"through
the UI a combo does not re-emit for the same entry"* — and then drives
`value_changed.emit()` by hand, so **no test covers the case a real user is in**.

### 1.5 should-fix — the shield records changes the chart never made

`_note_what_the_chart_imposed` (`:13507`) diffs the snapshot taken at `:16018`
against the state at the end of the handler, and attributes **everything in
between** to the chart sidecar. Several things in that window are not the
sidecar: `_refresh_gamut_visibility` (`:14930`, which calls `_switch_mode`, so
it can move `ui:mode`), `_update_name_fields`, and the `chart_finished`
emission. Measured on a verification target (`d3-shield.log`, S7):

```
  verif run2 : shield params ['targen-f']   ui ['guided', 'gamut']
```

`ui:gamut` is set by `_refresh_gamut_state` under §133's run-type module rules,
not by any sidecar — and the shield will now put the *previous* target's gamut
options back into this target's store. `_apply_ui_state`'s own docstring says
those rules *"still run afterwards and win over an illegal stored mode"*; at
write time they now lose.

### 1.6 not-a-bug — the cases that hold

Driven and correct:

* the headline K3 case (`d1-shield.log`, S1): pick CR30 on run 1, visit run 2,
  come back, leave the tab — `printtarg-i` stays `CR30`. **Fixed**, as long as
  nothing touches the panel.
* a run with **no chart** arms nothing (`_chart_imposed` empty) — the early
  `return` paths are covered because the note is in `finally` (`:16083`).
* the shield does **not** leak across targets: `_note_what_the_chart_imposed`
  runs on every target change, and `save_target_settings(outgoing)` at
  `:15990` runs *before* it, so the outgoing target is written with its own
  shield.
* `_release_imposed_connections` (`:13568`) swallows `TypeError`/`RuntimeError`,
  so a widget destroyed under a connection cannot raise. No dead-widget hazard
  was found.
* `_layout_owned_by_build`: cleared at `:16021`, *after* the snapshot at
  `:16018`, so a build in flight neither arms nor is shielded. No interaction
  found.
* a tab round-trip re-syncs the panel from the store before releasing the ui
  shield (`d4-shield.log`, step 5), so the tab-switch gesture alone is safe.
  It is the *panel edit without a re-sync* that is not.

### 1.7 The shortest fix

Shield `ui:engine_recipe` **field by field**, the way parameters are shielded,
and release each field from the control that owns it — or, far simpler, drop
the whole `ui` bucket from the shield and derive `engine_recipe` from the
already-shielded parameters. Either removes 1.1, 1.2 and 1.3 at once. 1.4 needs
a different signal (`activated`, which a combo *does* emit for a re-selected
entry) or an explicit "the user has touched this row" flag.


## 2. F1 — the stamp default moved to `_on_manual_engine_toggled`

### 2.1 BLOCKER (with §1.1) — **the default is still spent on a path the user did not drive**

The default was moved out of `_refresh_manual_command_preview` (which fired
from anything touching the panel) into `_on_manual_engine_toggled`
(`ui/tabs/tab_chart.py:4726-4730`), guarded by `_loading_target_settings`.

But the engine checkbox is *also* set programmatically by the chart-sidecar
restore, and **that path does not set the flag**: `_loading_target_settings` is
raised only around the registry apply at `ui/tabs/tab_chart.py:10571-10580`,
while `_manual_engine_check.setChecked(...)` is called outside it at `:10476`
and `:10550`.

Measured on screen with the checkbox's own `toggled` signal instrumented
(`~/Desktop/beta6-challenge/d6-stamp.log`), on a tree where run 2's chart
carries no layout recipe so restoring it switches the engine off:

```
  set stamp True. disk run1: False
  [after switching to run2] stamp on screen = True
      -> False  <-  load_target_settings:13879 / _apply_ui_state:14138
      -> True   <-  _on_target_changed:16076 / _display_run_chart:6087 /
                    _restore_chart_settings:10550 / _on_manual_engine_toggled:4730
```

Line 2 is the target's own stored `stamp=False` being put on screen. Line 3 is
the **new** line spending the default straight over it. §1.2 names the stamp
checkbox as a per-target setting, so this is the same confirmed-section
violation F1 was — narrowed, not removed.

**Why the store survived in this measurement:** the K3/K4 shield caught it
(`ui:stamp` moved after the snapshot, so it was restored to the target's own).
Two bugs cancelling. Release the ui shield with any panel edit (§1.1) and the
corruption returns. **F1 and K4 must be fixed together, or neither is fixed.**

### 2.2 should-fix — `_stamp_engine_state` is now **write-only dead state**

`grep -rn "_stamp_engine_state" --include="*.py" .` over the whole repository
returns exactly three lines:

```
ui/tabs/tab_chart.py:5170:            self._stamp_engine_state = use_engine
ui/tabs/tab_chart.py:7652:        "_engine_was_active", "_stamp_engine_state",   # a reset list
ui/tabs/tab_chart.py:14176:                    self._stamp_engine_state = on
```

It is **assigned twice and read nowhere.** So the 14-line comment added at
`:14162-14176` — *"AND THE STAMP DEFAULT IS ALREADY SPENT FOR THIS STATE …
Recording the state here means the default is only ever spent on a state the
USER changed"* — documents a mechanism that does not exist, and the
`if "stamp" in stored: self._stamp_engine_state = on` it guards is a **no-op**.

Answer to the brief's question: **no, `_stamp_engine_state` is not coherent.**
It is vestigial. Either delete it and its two comments, or make
`_on_manual_engine_toggled` read it (which would also fix 2.1, because the
sidecar restore would then not re-spend a default already spent for that state).

### 2.3 not-a-bug — a real user toggling the engine still gets the default

`was_on` is read from the settings before the write (`:4687`), and `on != was_on`
is true exactly once per real change, so a person ticking the engine box still
gets `stamp = not on`. Confirmed on screen (the toggle path in `d6-stamp.log`).


## 3. K8 — printed row labels from the chart's `patch_pattern`

### 3.1 not-a-bug — the default render IS byte-identical, and it is now proven

The shipped test only proves that *omitting* the argument equals *passing the
default*. That is not the same claim. I rendered the full page images at HEAD
and at `efe80bde^` over **40 combinations** — 5 instruments × row-indicators
on/off × 60 and 240 patches × A4 and Letter — and compared SHA-256 of the
concatenated greyscale bytes (`~/Desktop/beta6-challenge/render_hash.py`,
`hash_head.json`, `hash_pre.json`):

```
IDENTICAL across all combos
```

And **none of the 121 built-in presets names `patch_pattern` at all** (measured:
`presets that name patch_pattern at all: 0`), so every one of them takes
`permutation.DEFAULT_PATCH_PATTERN`. The byte-identity claim holds.

### 3.2 not-a-bug — the thread from the recipe to the page is complete

`LayoutRecipe.build_kwargs()` does pass both patterns
(`workflow/layout_engine/presets.py:417-418`) → `build_chart` →
`raster.render_pages(patch_pattern=…)` (`chart.py:312`) and
`ti2_writer.write_ti2(patch_pattern=…)` (`chart.py:265`), so the sheet and the
`.ti2` are now labelled from **one** value. `render_pages` has exactly one
production caller (`chart.py:309`); every other call is a test.

### 3.3 not-a-bug — an old `.strips.json` still loads

The only reader of that file in the app is
`ui/tabs/tab_measure.py:437` (`patch_boxes_from_sidecar`), and it reads only
`patches[]`. An older file without `patch_pattern` is unaffected.

### 3.4 nice-to-have — the new sidecar field is **written and never read**

`grep -rn '"patch_pattern"'` over the repo: the only consumers are
`presets.py:287` / `:418`, which read the **recipe** in `.channels.json`, not
`.strips.json`. So the commit's claim — *"The sidecar now records the pattern
too, so a restored chart can reproduce its own labels"* — describes something
that was **already true before the change**: `LayoutRecipe.to_dict()` has
carried `patch_pattern` since long before (`git show efe80bde^:…presets.py`
line 418). The `.strips.json` key is inert data. Harmless, but the report
should not credit it with fixing F4.

### 3.5 should-fix — **the rename Knut asked for was not done, and the fix made the label wrong**

K8 has two halves. Knut: *"Rename to **'Show row indicators'** — the labels are
not always numbers."*

```
$ grep -rn "Show row indicators" --include="*.py" --include="*.json" .
(nothing)
ui/dialogs/layout_options_panel.py:452:  WrappingCheckBox(tr("Show row numbers"), self)
ui/dialogs/layout_options_panel.py:470:  tr("Prints a number down the left-hand side of the chart for every row
                                          of patches (1, 2, 3…)…")
```

The box still says **"Show row numbers"** and its help still says it prints
**numbers**. Before this fix that was merely imprecise; **now the app will print
`A, B, C` down the side of a chart while the checkbox that turns it on is
called "Show row numbers" and its help says `1, 2, 3…`.** The fix made the
misnomer factually false rather than merely loose. Knut named this in his own
report; he will name it again.

K11 (both help texts must explain how Strip pattern and Patch pattern decide
the labels) is likewise untouched — see §9.

## 4. F2 — the `fill_beyond_ruler` guard in `area_fit.py`

### 4.1 BLOCKER-of-belief — **F2 is not fixed. The guard is in the right function and is fed a geometry that can never satisfy it.**

`area_fit._usable` now reads
`_rlwi = 0.0 if g.fill_beyond_ruler else g.rlwi` (`area_fit.py:45`). But the
only thing that calls `_usable` on the area-first sizing path is
`area_fit.derive_area_patch_size`, and it builds its geometry like this:

```python
base = {**kw, "layout_mode": "patch_first"}      # workflow/layout_engine/area_fit.py
geom = instruments.geom_from_build_kwargs(base)
avail_w, arowl = _usable(geom, w_mm, h_mm)
```

and `instruments.geom_from_build_kwargs:441` sets

```python
area_first = (kw.get("layout_mode") == "area_first")
geom = build(..., fill_beyond_ruler=area_first, ...)
```

so the geometry `_usable` is handed **always has `fill_beyond_ruler=False`**.
Measured, by spying on every `_usable` call made while building a real
area-first ColorMunki A4 geometry with row indicators on:

```
every _usable call made while building the area-first geometry:
fill_beyond_ruler  rlwi   usable_w
False                 7.5    170.5      <- the PRE-FIX value
```

One call, guard never fires, `170.5` — exactly what the code returned before
the fix.

**And the page is bit-identical.** `~/Desktop/beta6-challenge/f2-head.txt` vs
`f2-prefix.txt`, same probe run against HEAD and against `efe80bde^`, fixed
grid, margins 6 mm:

```
CM    area_first  True  |  usable_w 178.0   patch_r 196.43   margin_r 204.0     <- HEAD
CM    area_first  False |  usable_w 178.0   patch_r 203.88   margin_r 204.0
      -> rows-ON right edge minus rows-OFF: -7.45 mm   *** SHORTFALL ***

CM    area_first  True  |  usable_w 170.5   patch_r 196.43   margin_r 204.0     <- PRE-FIX
CM    area_first  False |  usable_w 178.0   patch_r 203.88   margin_r 204.0
      -> rows-ON right edge minus rows-OFF: -7.45 mm   *** SHORTFALL ***
```

`_usable` changed (170.5 → 178.0). **Every rendered right edge did not.**
`diff f2-head.txt f2-prefix.txt` differs only in the `usable_w` column. The
7.45 mm shortfall report 16 reported as F2 is still on the paper at HEAD, on
the ColorMunki, the i1Pro3+ (−7.62 mm) and the CR30 (−6.44 mm).

### 4.2 Why the test is green anyway

`tests/test_area_first_fills_the_margin_box.py` builds its geometry by hand:

```python
g = instruments.build("i1", row_indicators=rows_on, fill_beyond_ruler=True)
return area_fit._usable(g, _W, _H)[0], g
```

`fill_beyond_ruler=True` **is a state the production path never produces at
that call site.** The test proves the function; it does not ask where the patch
block lands. It is the same shape as the four vacuous tests this very commit
set out to repair — and it was written in the same commit.

### 4.3 Can a chart overflow the ruler or the margins?

No overflow was found. Across 64 rendered combinations
(`~/Desktop/beta6-challenge/f2probe.py`, instrument × paper × mode × rows ×
clip) the patch block never crossed the right margin. What it does is the
opposite — it stops short — and, separately, **the row labels themselves leave
the margin box**: measured ink at **0.34 mm** from the paper edge (i1Pro, A4,
area-first, rows on, clip off) and **0.68 mm** (i1Pro3+). That is K10 clause 3/4
and is open by design (§9), not a regression.

## 5. K5 — the stagger checkbox at grid row 7

**not-a-bug — the fix is correct in both panel shapes and on every instrument.**
Driven with the real theme applied, both constructions, every instrument the
combo offers (`~/Desktop/beta6-challenge/k5-panel-tab.png`,
`k5-panel-prefs.png`):

```
=== with selectors (Create Chart tab) ===
  cells holding more than one widget: NONE
  show_row_ind (4,1)   clip_enable (6,1)   cm_stagger_cb (7,1)
  CM  cm_stagger_cb (102,228,355,18)  clip_enable (102,198,355,22)   <- 220 < 228, clear
=== no selectors (Preferences) ===
  cells holding more than one widget: NONE
  show_row_ind (4,1)   cm_stagger_cb (6,1)
  CM  cm_stagger_cb (102,200,313,18)  show_row_indicators (102,172,313,18)
```

Row 5 is left empty in the Preferences shape; Qt collapses an empty grid row to
zero height, and the measured spacing (28 px, the same as every other row)
confirms **nothing is visually orphaned**. `_stagger_row` (`ui/dialogs/
layout_options_panel.py:749`) uses the identical `mode is not None` condition as
the block that claims rows 5 and 6, so the two cannot drift apart.

**nice-to-have, pre-existing, not from this commit:** the sweep found one other
overlapping pair, in the area-first fields — the **"Minimum patch width"** and
**"Minimum patch height"** ⓘ buttons, at `(453, 20, 22, 22)` and
`(453, 39, 22, 22)`: a 22 px button on a 19 px pitch, so they overlap by 3 px.
It only shows when the area fields are visible, which on a ColorMunki they are,
because choosing a ColorMunki flips the layout mode to area-first (K1). Worth
one row height; not a beta-6 blocker.

## 6. K12 — the CR30 learn-tile window (`ui/tabs/tab_measure.py:7730`)

### 6.1 should-fix — **F5 is dead code. Every failure still prints the "you declined" note.**

```python
7951:        stop["asked"] = True          # unconditional, right after dlg.exec()
...
7978:        if result.get("learned"): ...
7981:        elif stop["asked"]: ...       # <- therefore ALWAYS taken on failure
7985:        else:                          # <- F5's new diagnostic: UNREACHABLE
                _why = str(result.get("error") or "").strip()
                _presses_seen = int(result.get("presses") or 0)
```

`stop["asked"]` is set to `True` unconditionally at `:7951`, *before* the note
is chosen at `:7981`. So the `else` branch — the whole of F5, *"a failure says
how many readings it took and why they were not enough"* — can never run.

Driven with the real method and a reader stubbed only at the radio
(`~/Desktop/beta6-challenge/k12-f5-dead-branch.log`), the user never touching
"Not now":

```
--- presses disagree, user never declines ---
LOG: "[NOTE] The magnet check is running on ChromIQ's built-in value, which was
      measured on a different instrument…"
--- the learner raises ---
LOG: "[NOTE] The magnet check is running on ChromIQ's built-in value, which was
      measured on a different instrument…"
```

The exception text (`"BLE link went away"`) is captured into `result["error"]`
and then thrown away. **This is the same fault F5 was written to fix** —
report 16: *"Thirty-four seconds of a feature failing left no trace at all,
which is why the first hypothesis about this was wrong."* The trace is still
missing, and the user is now actively told they declined when they did not.

The fix is one line: capture the real answer before overwriting the flag
(`declined = stop["asked"]` immediately after `dlg.exec()`).

### 6.2 nice-to-have — decline, then the learn succeeds: the log says the opposite

`result` is read on the GUI thread the instant `dlg.exec()` returns, while the
worker may still be inside `learn_tile`. Driven
(`~/Desktop/beta6-challenge/k12-decline-race.log`): the user declines at
+0.15 s, the learner completes at +0.4 s with `learned: True` — and the log
says the magnet check is still on the built-in value. In the real
`measure_bridge.learn_tile` the success path has already written
`cr30_tile_signatures` by then (`measure_bridge.py:974`), so the store and the
log disagree.

### 6.3 not-a-bug — the lifetimes and the edge cases hold

Driven or read, each one:

* **No transport / `open_transport` raises** — `try/except` at `:7776` leaves
  `_kind = ""` and asks for **two** presses, which is the safe direction
  (`:7779`).
* **`guard_is_armed` raises** — `:7760` returns without a window.
* **Already armed** — early `return` at `:7759`; the window cannot be offered
  twice for a learned unit.
* **Declining and then pressing** — `dlg.finished` disconnects `pressed` from
  `_heard` (`:7940`), and `_heard` additionally guards with `sip.isdeleted`.
  Measured: **0 QDialogs alive** after the window closes, so the label really
  is destroyed and the guard is doing work, not decoration.
* **The thread outliving the window** — `self._learn_thread` is kept until
  `thread.finished` (`:7965-7975`); measured `thread still referenced: False`
  only after it ended.
* **A short screen** — `room = availableGeometry().height() - 80`, and the
  second `heightForWidth` pass at `:7883` grows the window only up to it. The
  floor is `max(320, room)`, so a screen under 400 px would still exceed it;
  no such screen is realistic.

### 6.4 The window no longer hangs

The K12 headline is genuinely fixed: the learner runs behind the window, the
live line counts the readings, the window closes itself on success, and there
is no confirm button left to answer falsely. Nothing in the shipped code can
reproduce Basti's 34-second silence.

## 7. Em dashes in user-facing text — complete inventory

Method: every `.py` outside `.venv/`, `tests/`, `scripts/`, `docs/` parsed with
`ast`. A string counts as **user-facing** when it is an argument of `tr()`/`trn()`
anywhere in the call, or when it is a non-docstring literal in one of the six
modules that build user text without `tr()` (`measurement_messages.py`, the two
loaders, the project picker, the name prompt, `measurement_import.py`).
**Docstrings and comments are excluded and were left alone.** Full listing:
`~/Desktop/beta6-challenge/emdash-inventory.txt` (181 lines), generator
`emdash_all.py`.

### The totals

| | count |
|---|---|
| **user-facing Python strings containing an em or en dash** | **1 208** |
| …of which contain an EN dash (–) | 37 |
| files affected | 57 |
| `data/parameters.yaml` strings with a dash | **71** |
| `data/i18n/*.json` **keys** (= English source strings) with a dash | **1 168 per language, × 12 languages** |
| `data/i18n/*.json` **values** with a dash | 998 (ja) – 1 276 (ru) |

**The cost is not 1 208 edits, it is ~1 208 + 71 + 14 016.** Every English source
string is a catalogue *key*; changing one invalidates the key in all twelve
`data/i18n/*.json` files, and `tests/test_i18n.py` fails CI on a stale key. A
sweep is a mechanical but very large change, and it must be one commit with the
catalogues regenerated.

### Where they are (top of the list)

```
 156  ui/tabs/tab_measure.py            34  ui/file_guide.py
 140  ui/dialogs/welcome_dialog.py      32  ui/measurement_target_bar.py
  83  ui/dialogs/settings_dialog.py     29  ui/dialogs/ti3_info_dialog.py
  79  ui/tabs/tab_chart.py              25  ui/dialogs/tools_dialogs.py
  78  ui/tabs/tab_profile.py            22  ui/getting_started.py
  72  ui/dialogs/scanin_dialog.py       21  ui/gamut_panel.py
  56  ui/dialogs/layout_options_panel.py 17 core/run_delete.py
  53  ui/dialogs/measurement_report_dialog.py
  52  ui/dialogs/ti2_relayout_dialog.py
  40  workflow/measurement_messages.py      (the §M catalogue)
```

…and 47 more files, each under 17. The full per-file table is in the artefact.

### The import dialogs specifically — **23 strings, and 3 of them are already gone**

These are the windows Basti was looking at in the screenshots:

| file:line | text (trimmed) | state |
|---|---|---|
| `ui/dialogs/name_prompt.py:65` | *"…it is printed on the chart itself — …"* | **fixed in the worktree** |
| `ui/dialogs/name_prompt.py:94` | *"A folder name cannot contain / \ : * ? " < > \| — please use letters…"* | **fixed in the worktree** |
| `ui/dialogs/project_picker.py:138` | the row separator `"   —   "` (`Name — 2 runs`) | **fixed in the worktree** (now `·`) |
| `ui/ti2_loader.py:641` | `"</b> — "` — the bullet separator in the choices list | **open** |
| `ui/ti2_loader.py:642` | *"• **Cancel** — nothing is opened, copied or changed…"* | **open** |
| `ui/ti2_loader.py:733` | *"Copies the chart — and its measurement (.ti3) and profile — into a brand-new run…"* | **open** |
| `ui/ti2_loader.py:746` | *"Moves the current verification chart into … — nothing is deleted — and then installs…"* | **open** |
| `ui/ti2_loader.py:755` | *"Moves this run's chart, measurement and printer profile — together with every folder…"* | **open** |
| `ui/ti2_loader.py:765` | *"Imports into a brand-new run — `runs/{new}/` — inside the profile project…"* | **open** |
| `ui/ti2_loader.py:889` | *"…Profile run / Run type are not used — the copy reproduces the project exactly."* | **open** |
| `ui/ti2_loader.py:1155` | *"*Continue* — use the files in this folder as-is — nothing will be copied or moved."* | **open** |
| `ui/ti2_loader.py:1163` | *"*Use as base for a new profile* — copy the files to a new subfolder…"* | **open** |
| `ui/ti2_loader.py:1492`, `:1583` | *"replaced %s — everything it held is kept at %s"* (log line) | **open** |
| `ui/ti2_loader.py:217, 265, 318, 325, 341` | the CR30 / i1Pro spot-read instruction cards | **open** |
| `ui/txt_loader.py:167` | *"*Continue* — convert and use the measurement in this folder as-is — nothing…"* | **open** |
| `ui/txt_loader.py:175` | *"*Use as base for a new profile* — copy the measurement to a new subfolder…"* | **open** |
| `ui/txt_loader.py:452` | *"replaced %s — everything it held is kept at %s"* (log line) | **open** |
| `workflow/measurement_import.py:83` | *"the chart has {chart} patches, but this file holds {got} measurements — so it is a measurement of a different chart"* | **open** |
| `ui/tabs/tab_profile.py:362, 921, 989, 1733, 1746, 1774, …` | the Build Profile page's own text; **the two import bodies were fixed in the worktree** | mostly **open** |

**So the three fixed in the worktree are not the ones in the screenshots Basti
was looking at.** `ui/ti2_loader.py` alone still has **16**, and the loaded-chart
routing window — the four-choice one — carries five of them
(`:733`, `:746`, `:755`, `:765`, `:889`).

### Judgement

Removing every dash in the app is a 1 200-string, 12-catalogue sweep and should
be one deliberate commit, not something bolted onto beta 6. Removing them from
**the import windows only** — `ui/ti2_loader.py` (16), `ui/txt_loader.py` (3),
`workflow/measurement_import.py` (1) — is 20 strings and would answer what
Basti actually saw. That is the recommendation.

## 8. The four rewritten tests — mutation proof

Method: `rsync` copy of the tree at `/tmp/beta6work/mutrepo` (never the working
tree). For each mutation: apply it, prove it is **present in the function under
test** via `inspect.getsource`, prove **the module still imports**, prove the
mutation **has an effect on behaviour**, then run the single test. All four were
green before any mutation.

| # | mutation | landed | effect proven | test | verdict |
|---|---|---|---|---|---|
| M1 | `picker.currentIndexChanged.connect(lambda _i: None)` — the exact original fault | yes, in `_file_into_project` | — | `test_the_run_picker_choice_is_connected` | **CAUGHT** |
| M2 | `spread_message_box_buttons` sets `order = None` after its docstring | yes, in the function | — | `test_cancel_sits_on_the_far_right_and_replace_is_not_first` | **STILL VACUOUS** |
| M2 | (same mutation) | yes | — | `test_the_given_order_is_what_the_row_ends_up_in` | **CAUGHT** |
| M3 | a hand-written nearest-neighbour re-pairing added to `assess`, using none of the four grepped library names | yes, in `assess` | yes — the shuffled measurement's verdict flips to `ok=True` | `test_a_measurement_out_of_the_chart_s_order_is_refused_not_re_paired` | **CAUGHT** |
| M4 | `ui/txt_loader.is_self_collision` grows its own `os.path.realpath` comparison, behaviour-identical on real paths, with no grep bait | yes | yes — same answers as the real helper | `test_both_loaders_ask_the_shared_helper_and_obey_it` | **CAUGHT** |

### M2 — the named test is still vacuous, and its docstring says otherwise

Under a `spread_message_box_buttons` that discards `order=` on its first line,
`test_cancel_sits_on_the_far_right_and_replace_is_not_first` **passes**. Only the
companion `test_the_given_order_is_what_the_row_ends_up_in` fails.

The companion's own docstring explains why, correctly:

> *"the style in a test run lays a QDialogButtonBox out accept-first anyway, so
> discarding `order=` entirely leaves that window looking correct."*

But the named test's docstring claims the opposite about itself:

> *"Proven: it did stay green under exactly that mutation. What matters is where
> the buttons end up, so that is what is measured."*

Both cannot be right. The pair is sound; **the test report 17 lists as repaired
is not the one doing the work.** Not a code defect — a claim defect, and worth
correcting so nobody later deletes the companion as a duplicate.

### Two lessons for the method, recorded because they nearly produced wrong answers here

1. **M3, first attempt, was inert.** It permuted `measured.patches`, and
   `Ti3Data` has no `patches` — it has `rows`. `inspect.getsource` showed the
   mutation, the module imported, the test passed, and the mutation had done
   *nothing*. A "green" verdict there would have libelled a good test.
2. **M3, second attempt, was also inert.** `_txt.split("BEGIN_DATA", 1)` splits
   at `BEGIN_DATA_FORMAT`, so the chart's device values were never read. Only
   the third attempt, verified by watching the verdict flip to `ok=True`,
   counted.

Presence in the source is not landing. **The effect must be measured**, and it
was, for M3 and M4.

## 9. The items deliberately left alone

I agree with every one of these calls. None of them is a plain bug hiding behind
a design question, and I looked for that specifically.

| # | what it is | why the call is right |
|---|---|---|
| **K1** | choosing the CR30 rewrites the layout mode *and* the spacer mode | Both changes are deliberate and each has an owner's decision behind it (#159; Basti 2026-08-30). No design document covers instrument-driven defaults at all, so "fixing" it would be inventing policy. **Do tell Knut about the spacer**, which he did not notice and which also changes his chart. |
| **K6** | "Show row numbers" greyed while strip indicators are off | The greying is honest about the raster as it stands: `raster.py:1216` draws the row block inside `if draw_indicators:`. Making them independent is a small change and a product decision about whether row indicators are a sub-option or a peer. Not a bug. |
| **K7** | Preferences overrides a preset's label size in both directions | Deliberate, and stated in `core/settings.py:398`: the styling fields a preset carries are *"inert history"*. Knut is asking for the rule to change, which is a decision, not a defect. |
| **F3** | the strip label never follows "Text distance from edge" | Same family as K9/K10 and measured to clamp to 0.00 mm under `margins_are_law`. It is a geometry design, not an oversight in isolation. |

### K9 / K10 — exactly which clauses the code breaks, and what a fix must decide

Knut's K10 is a five-clause specification. Re-measured at HEAD (§4.3 and
`~/Desktop/beta6-challenge/f2probe.py`), the code still breaks four of five —
**unchanged by this batch**:

| clause | state at HEAD | evidence |
|---|---|---|
| 1 · labels drawn outside the patch area, on the left | **held** | ink is left of the block in both modes |
| 2 · position follows "Text distance to edge" and Clip, not a fixed 7.5 mm | **broken** | `rlwi = ROW_LABEL_BAND_MM = 7.5` is a constant; `raster.py:1219` uses a hard-coded 1 mm gap; neither `text_edge_mm` nor `text_edge_clip_mm` is read on the row-label path |
| 3 · labels never closer to the edge than the Clip limit | **broken** | measured ink at **0.34 mm** from the paper edge (i1Pro, A4, area-first, rows on, clip off) and **0.68 mm** (i1Pro3+) |
| 4 · the whole patch area follows the margins as law | **broken, differently per mode** | patch-first *adds* 7.45 mm to the left margin; area-first keeps the margin and pushes the labels out of it |
| 5 · sensible defaults when clip border and row indicators are both on | **not implemented** | nothing adjusts Clip or the left margin; K9 is the consequence |

**Two decisions the clause list does not settle, and a fix cannot proceed
without them:**

1. In **patch-first**, does the reserved band come *out of* the margin (patch
   area starts at the margin, band inside it) or is it *added to* it (today,
   which enlarges a 6 mm margin to 13.46 mm)? Clause 4 says "margins are the
   law", which implies the former — but that shrinks every existing
   patch-first chart's patch count, so it is a compatibility decision, not a
   geometry one.
2. When the label will not fit inside the Clip limit, does the **label shrink**,
   the **margin grow**, or the **chart refuse**? Measured: at 16 pt the labels
   already start 0.10 mm inside a 6 mm margin, so a three-digit row number walks
   off the page. Nothing in the clause list says which of the three happens.

Report 17's judgement — *"this must be written down before it is built — it is
one design, not three bugs"* — is right, and I would add: **it should be written
down before beta 6 is tagged**, because Knut will re-test row indicators and
will re-report clauses 2, 3 and 4 as bugs unless he is told they are queued.

## 10. Could each fault come back? — every guard mutated

Method as §8: mutate the code the guard protects, prove the mutation is present
in the function under test and that the module still imports, then run the test.

| # | state | guard | mutation | result |
|---|---|---|---|---|
| **K1** | open-by-design | — | — | no guard, and none wanted |
| **K2** | open-by-design | — | — | no guard |
| **K3** | **fixed-and-guarded (narrowly)** | `test_the_chart_sidecar_never_files_into_the_target.py` | — | catches the headline case; **does not** cover the panel-edit case of §1.1 or the L5 case of §1.3 |
| **K4** | **STILL BROKEN** | the same file | — | **§1.1: driven on screen, the setting is destroyed again after one margin nudge.** No test covers it |
| **K5** | **fixed-and-guarded** | `test_the_layout_panel_has_no_two_widgets_in_one_cell.py` | `_stagger_row = 6` | **CAUGHT** (`test_every_cell_holds_at_most_one_widget[True]`) |
| **K6** | open-by-design | — | — | no guard |
| **K7** | open-by-design | — | — | no guard |
| **K8** | **half fixed, half unguarded** | `test_the_printed_row_labels_match_the_file.py` | `label_patch = make_labeller(DEFAULT_PATCH_PATTERN)` | **CAUGHT** for the labeller. **Nothing guards the rename Knut asked for** (§3.5) |
| **K9** | open-by-design | — | — | no guard |
| **K10** | open-by-design | — | — | no guard |
| **K11** | **not fixed, unguarded** | — | — | the help texts still say nothing about placement, Strip pattern or Patch pattern |
| **K12** | **fixed-and-guarded** | `test_cr30_the_learning_window_listens_while_it_is_open.py`, `test_cr30_the_guard_flags_are_really_properties.py` | — | the listening behaviour is covered; **F5's failure note is not** (§6.1 — proven dead) |
| **F1** | **STILL FIRES** | — | — | §2.1: no test covers the chart-restore path through `_on_manual_engine_toggled` |
| **F2** | **fixed in the function, inert on the page** | `test_area_first_fills_the_margin_box.py` | `_rlwi = g.rlwi` | **CAUGHT** — but the guard asserts the function, and §4.1 proves the page is unchanged either way |
| **F4** | written, never read | — | — | §3.4 |
| **F5** | **dead code** | — | — | §6.1, proven on screen |

### Where there is no test that would fail if the fault came back

Stated plainly, because this is the most useful part:

1. **K4 / the shield's UI half.** No test exercises `ui:engine_recipe` at all.
   A test that unticks an indicator, switches runs, nudges a panel control and
   asserts the store would fail today.
2. **F1 / the stamp default on the sidecar path.** No test drives a run whose
   chart flips the engine state.
3. **F2 on the page.** The guard is at the function; a rendered-page assertion
   (right edge with rows on == right edge with rows off, area-first) would have
   shown the fix inert on the day it was written.
4. **F5.** No test reads the log after a failed learn.
5. **K8's rename.** No test asserts the label matches what is printed.
6. **The tooltip accent (§12).** No test at all; the property is held by three
   unrelated loops.
7. **The two records of the instrument (§1.2).** No test asserts that
   `create_chart_settings["printtarg-i"]` and
   `create_chart_ui.engine_recipe.instrument` agree in a run's `meta.json`.
   That invariant is cheap to assert and would have caught §1.2 and §1.3 both.


## 11. The import window's accept button names the run

Reviewed in the worktree at `…/scratchpad/wt-button`; the main tree was not
touched.

### 11.1 BLOCKER for that change — **it fails `tests/test_i18n.py`, 24 tests**

Run in the worktree:

```
24 failed, 47 passed in 23.58s
FAILED tests/test_i18n.py::test_catalog_is_complete[de] … ×12
FAILED tests/test_i18n.py::test_catalog_has_no_stale_keys[de] … ×12
```

The same file passes 71/71 in the main tree. `scripts/i18n_extract.py --missing
de` names the seven new keys, three of them this change's:

```
"File it in a new run"
"File it in the selected run"
"File it in {run}"
```

plus the four created by the em-dash edits in `name_prompt.py`,
`project_picker.py` and `tab_profile.py`. `"File it here"` is now stale in all
twelve. **Per CLAUDE.md this must be fixed in the same commit** — twelve
catalogues plus the German translations — or the release gate goes red.

### 11.2 not-a-bug — nothing clips in any language

Measured with the real stylesheet, `fit_button_width` + `fit_message_box_buttons`
+ `spread_message_box_buttons` as the code calls them, against plausible
translations (`~/Desktop/beta6-challenge/button-widths-translated.txt`):

```
de        Im ausgewählten Durchlauf ablegen    btn 313  text 258  ok
de        In einem neuen Durchlauf ablegen     btn 294  text 250  ok
ru        Сохранить в выбранном прогоне        btn 292  text 227  ok
nl        Opslaan in de geselecteerde run      btn 283  text 242  ok
pl        Zapisz w wybranym przebiegu          btn 260  text 211  ok
```

The longest candidate is 313 px against 249 px for the longest English. Nothing
clips; the button grows and the box grows with it. `fit_button_width` on every
picker change is what makes that true, and it is called (`tab_profile.py:4399`).

### 11.3 not-a-bug — the two `currentIndexChanged` connections do not interfere

`chosen.__setitem__` is connected at `:4361`, the namer at `:4401`; Qt fires in
connection order, so `chosen[0]` is already updated when the label is rebuilt.
And `_name_the_run` reads `picker.currentData()` itself rather than `chosen`, so
even the order does not matter. No interference.

### 11.4 not-a-bug, but worth knowing — a CALIBRATION target shows **no window at all**

`_build_run_picker` returns `(None, [peek.run_id])` for a calibration
(`ui/tabs/tab_chart.py:8949`), and `_file_into_project` guards the whole window
with `if picker is not None:`. So there is no button to be honest or dishonest
about: the measurement is filed into the project's current run **without asking
and without saying so**. That is pre-existing, not from this change, and it is
deliberate (the comment explains why a picker there was harmful). It is worth a
line on screen all the same.

### 11.5 not-a-bug — empty / single-entry pickers

`peek.runs` is never empty for a real project, and the picker always carries
"A new run" as entry 0, so the button's fallback (`"File it in the selected
run"`) is only reachable if a run label ever came back blank. `_run_label`
returns `tr("Run {n}")`, which cannot be blank. The fallback is dead but
harmless, and it is the right kind of dead.

### 11.6 Judgement on the wording — **the implemented version is better than the suggestion**

Basti's own alternative was *"Choose the selected run"*. That is tautological —
it says the user is choosing what is already chosen — and it never says what
happens to the file. *"File it in Run 2"* names the verb and the destination, and
it cannot disagree with the combo because it is generated from it. Keep it.

One residual: a button whose **text changes while you look at it** is unusual,
and the row re-lays out on every combo move. Measured as safe here, but it is
worth Basti seeing it move before it ships.

### 11.7 What a beginner would still misread

*"File it in Run 2"* does not say **what is already in Run 2**. The picker rows
do (`Run 2 · holds a measurement`), but the button — the thing being clicked —
does not, and a beginner filing over a run that already holds a measurement gets
no warning from the words they are actually reading. That is worth a line in the
informative text, not a change to the button.

### 11.8 The neighbouring window — `project_picker.py`'s "Choose this project"

Judged on screen. It is **not** the same ambiguity: "this" refers to the row
highlighted in the list *inside the same window*, and the list is the only thing
there, so there is no second candidate for "this" to mean. The import window's
problem was that "here" competed with the run the user was looking at *behind*
the window. No change needed.

## 12. The tooltip ⓘ wearing the wrong tab's accent

### 12.1 The fault is real and I reproduced it in the MAIN tree

`TooltipButton._set_icon` (`ui/tooltip_button.py:129`) falls back to the class
attribute `ACCENT`, which `MainWindow._on_tab_changed` rewrites on every tab
change (`ui/main_window.py:840`). With `ACCENT` deliberately set to `#FF00FF`
and the name box opened with its own accent `#37bcd6`, the ⓘ's **icon pixels**
come back `(255, 0, 255)` (`~/Desktop/beta6-challenge/tip2.py`):

```
name_prompt (MAIN TREE)     tooltips=  1  drawn in the FOREIGN accent:   1
project_picker (MAIN TREE)  tooltips=  0  drawn in the FOREIGN accent:   0
```

The worktree fix (`color=accent or None`) is correct.

### 12.2 The sweep — **no other instance**, and here is why

AST audit of every `TooltipButton(` construction in the app
(`~/Desktop/beta6-challenge/tooltip-accent-audit.txt`): **293 constructions in
26 modules.** Three mechanisms keep them right, and between them they cover
everything except the one reported:

| mechanism | where | count |
|---|---|---|
| explicit `color=` at construction | 10 dialog modules (`tools_dialogs` 8, `measurement_report_dialog` 5, `ti3_info_dialog` 3, `softproof_dialog` 2, `devicelink*`, `scanin*`, `scanner_colprof`, `spot_read`, `ti2_relayout`) | 25 |
| a re-tint loop over `findChildren(TooltipButton)` | `main_window.py:841` (every tab), `settings_dialog.py:3081`, `measurement_target_bar.py:1614` | the rest |
| — nothing — | **`ui/dialogs/name_prompt.py`** | **1** |

Verified by pixels, not by reading: `SettingsDialog` **122** tooltips, 0 foreign;
`DeviceLinkDialog` 16, 0 foreign; `SoftproofDialog` 3, `Ti3InfoDialog` 4,
`SpotReadDialog` 2 — all 0. The 208 "plain" constructions in `tab_profile.py`,
`layout_options_panel.py`, `tab_chart.py`, `tab_measure.py`,
`tab_check_refine.py`, `gamut_panel.py`, `tab_print.py` and `tab_header.py` are
all inside a tab widget and are re-tinted on every tab change; the layout panel's
61 are additionally covered by the settings dialog's own loop when it appears in
Preferences (measured: 0 foreign there).

**So the answer to "how many others?" is: one, and it is the one that was
fixed.**

### 12.3 should-fix — nothing stops it happening again

The property "a ⓘ inside a window with its own accent must carry that accent" is
held by three unrelated pieces of code and asserted by **no test**. A new dialog
that takes an `accent` and forgets `color=` reproduces this silently, and the
only way anyone notices is a screenshot. The cheap guard is a property test that
sets `TooltipButton.ACCENT` to a foreign colour, builds each accent-carrying
dialog, and reads the icon pixels — which is exactly what `tip2.py` does.

The stronger fix is to make `TooltipButton._set_icon` read an accent from its
own window (a `windowAccent` property) rather than from a process-global, so the
question cannot be got wrong.

## 13. Dialogs sized for a width they may not get

### 13.1 should-fix — **`pin_min_height` does not solve the narrow case for the name box**

Driven in the worktree, real style, the dialog built by `ask_for_project_name`,
every optional row exercised (`~/Desktop/beta6-challenge/dialog-sizing.txt`):

```
  [as opened]                        dlg 679x347  CLIPPED LABELS: 0
  [an illegal name]                  dlg 679x347  CLIPPED LABELS: 0
  [a name that gets sanitised]       dlg 679x347  CLIPPED LABELS: 0
  [an existing project's name]       dlg 679x347  CLIPPED LABELS: 0
  [a very long name]                 dlg 679x347  CLIPPED LABELS: 0
  [forced to 560 px wide]            dlg 560x347  CLIPPED LABELS: 1
        CUT: 'Where should this measurement go?  Type the ' w=520 h=96 needs 112
```

**At 560 px — the dialog's own minimum width — the body label is 96 px tall and
needs 112.** Sixteen pixels, about one line, silently missing, with no scrollbar
and nothing to say so. That is the same failure the change was written to
remove; it has been moved from "a narrow display" to "a narrow display, or a
user who drags the window narrower".

Cause: `pin_min_height` pins each wrapping label to
`heightForWidth(target_w − margins)` where `target_w` is the **natural** width
(679 px here), and then never revisits it. A word-wrapped label's height is
valid only at the width it was measured for — which is the change's own stated
principle, applied at one width only.

**The dynamic rows are fine.** Revealing the error line, the folder line and the
"you already have a project with this name" line clipped nothing at any of the
five states driven, because `_revalidate()` runs *before* `pin_min_height` and
the floor it computes accommodates them. So the docstring's *"call it again
after revealing/hiding optional rows"* is not needed here. **Width is.**

The fix is a `resizeEvent` that re-pins, or the scroll area.

### 13.2 not-a-bug — the project picker is fine

0 clipped at 679, 560, 480 and 400 px, and at its own minimum height. Its body is
one short paragraph and the list takes the slack.

### 13.3 Judgement — **the tile window needs its scroll area; do not consolidate onto `pin_min_height`**

The coordinator asks whether `pin_min_height` alone would do for
`_offer_cr30_tile_learning`. **No, and 13.1 is the reason.** `pin_min_height`
guarantees a floor and caps the opening height at 90 % of the screen — it gives
the user no way to reach text that does not fit. The tile window is eight
paragraphs with the instruction that matters (how many presses) in the middle;
on a genuinely short display, capping the height without a scroll area hides
exactly that.

The two answers are not duplicates of one question. They answer different ones:

* `pin_min_height` — *"never let this window be dragged short enough for rows to
  overlap."*
* the tile window's `QScrollArea` + `heightForWidth` pass — *"never let this
  window hide text with no way to reach it."*

If anything is to be consolidated, it is the other way round: give
`pin_min_height` an optional scroll-area mode and let the name box use it, which
would fix 13.1 at the same time. **Leave `_offer_cr30_tile_learning` alone.**

### 13.4 The three em dashes removed in the worktree

Confirmed gone and correct: `name_prompt.py:70` (the tooltip body),
`name_prompt.py:94` (*"…| . Please use letters…"*),
`project_picker.py:139` (`Name · 2 runs`). They cost 4 new catalogue keys and 4
stale ones — see 11.1. **They are not the dashes in the screenshots**: 20 remain
in the import path itself (`ui/ti2_loader.py` 16, `ui/txt_loader.py` 3,
`workflow/measurement_import.py` 1). See §7.

## 14. Safety of this run

* **Settings.** `CHROMIQ_SETTINGS_FILE=/tmp/beta6-challenge.ini` exported before
  any import in every driver, **and** `core.settings.QSettings` replaced as well.
  All eight of my sessions are identifiable in `~/Library/Logs/ChromIQ/chromiq.log`
  by their own warning:

  ```
  2026-08-31 23:57:54 [WARNING] core.settings: Settings SANDBOXED to
      /tmp/beta6-challenge.ini (CHROMIQ_SETTINGS_FILE is set)
  ```

  Checked afterwards **by value**, not by checksum:

  ```
  $ defaults read com.chromiq.ChromIQ custom_output_path
  The domain/default pair of (com.chromiq.ChromIQ, custom_output_path) does not exist
  $ defaults read com.chromiq.ChromIQ strip_indicator_size_mm
  0
  ```

  Both unchanged from the values taken before the run.
  `cr30_tile_signatures` still holds the same two keys with identical arrays.

* **Working folder.** Every driver pointed `custom_output_path` at
  `/tmp/beta6work/w1` or `/tmp/beta6work/w2`, scratch copies of `Demo-Switching`.
  Nothing under `~/ChromIQ` was opened as a working folder by any of them, and
  `~/ChromIQ/CR30-Test` was never opened.

* **⚠ The `~/ChromIQ` inventory is NOT a usable check this run, and I will not
  claim it is.** It went from **1 061 files at 23:50 to 941 at 00:33**. The
  cause is not mine and I can show that: the log records a **separate, real
  ChromIQ session started at 23:51:08** — `argv=['main.py']`, reading
  `/Users/Basti/Library/Preferences/com.chromiq.ChromIQ.plist`, i.e. the real
  preferences, with **no sandbox warning** — which opened
  `/Users/Basti/ChromIQ/test` and wrote `session_project_root` at 23:53:07.
  `~/ChromIQ/test/runs/run1/meta.json` and `~/ChromIQ/test/old/` carry that
  timestamp, and they are the **only** paths under `~/ChromIQ` newer than my
  session start. Eleven further un-sandboxed sessions follow between 00:24 and
  00:33. **Somebody else — a person or another agent — is driving the real app
  against the real working folder at the same time as this run.** That should be
  known before anyone reads a `~/ChromIQ` inventory as evidence tonight.

* `~/Desktop/i1Profiler` — not read and not written (mtime still 29 May 01:10).

* **The instrument was not touched.** No BLE connection was opened and no frame
  was sent. The CR30 work in §6 used a reader stubbed at the radio only; the real
  `_offer_cr30_tile_learning` was driven.

* Mutations were applied only to `/tmp/beta6work/mutrepo`, an rsync copy, and
  each file was restored from the working tree afterwards. `git worktree` at
  `efe80bde^` (`/tmp/beta6work/pre`) is a read-only checkout.
  **The only file this run changes in the repository is this report.**

## 15. Verdict

### Is it safe to tag beta 6?

**No.** Three of the things report 17 lists as fixed are not fixed, and one of
them loses the user's data on a gesture Knut is certain to make.

### The shortest list that would make it safe

1. **§1.1 — K4.** Shield `ui:engine_recipe` field by field, or derive it from the
   already-shielded parameters. As it stands, one nudge of a margin after a run
   switch files the chart's indicator settings over the user's own, on screen,
   measured. **This is the blocker.**
2. **§1.2** falls out with it: while the two halves have different granularity,
   `meta.json` can hold two different answers for the instrument.
3. **§2.1 — F1.** Raise `_loading_target_settings` (or an equivalent) around
   `_restore_chart_settings`'s two `_manual_engine_check.setChecked(...)` calls at
   `tab_chart.py:10476` and `:10550`. Today the stamp default is still spent on a
   path the user did not drive, and only the (broken) shield hides it.
4. **§6.1 — F5.** One line: capture `declined = stop["asked"]` before
   `stop["asked"] = True` at `tab_measure.py:7951`. Until then every failed tile
   learn tells the user they declined, and the diagnostic F5 exists for cannot
   run.
5. **§3.5 — K8's rename.** "Show row numbers" is now *wrong on the sheet*, not
   merely loose. Rename to "Show row indicators" and fix the two help texts.
   Knut asked for this by name.

### Should be corrected before anyone acts on report 17

6. **§4.1 — F2 is not fixed.** The guard is fed a geometry with
   `fill_beyond_ruler=False` because `derive_area_patch_size` builds its
   provisional geom as `patch_first`. The rendered page is bit-identical to the
   pre-fix page. Report 17 should not list it as fixed.
7. **§11.1 — the worktree button change fails `tests/test_i18n.py`, 24 tests.**
   Seven new keys in twelve catalogues plus the stale `"File it here"`.
8. **§3.4 / §1.3 / §8 (M2)** — three claims in report 17 that the evidence does
   not support: the `.strips.json` `patch_pattern` is never read; Restore Used
   Chart **is** shielded; and the button-order test that was "repaired" is still
   the vacuous half of a working pair.

### Nice to have

9. §1.4 (a user cannot pick the value the chart is showing), §6.2 (decline-then-
   succeed race), §12.3 (no test guards the tooltip accent), §13.1
   (`pin_min_height` clips at 560 px), §5's 3-px ⓘ overlap in the area fields.

### K1–K12, one line each

| # | verdict |
|---|---|
| K1 | open-by-design (tell Knut about the spacer too) |
| K2 | open-by-design |
| K3 | fixed-and-guarded for the reported gesture; unguarded for L5 and for a panel edit |
| **K4** | **still broken — §1.1, measured on screen** |
| K5 | fixed-and-guarded (mutation caught) |
| K6 | open-by-design |
| K7 | open-by-design |
| K8 | labeller fixed-and-guarded; **the rename is still broken and unguarded** |
| K9 | open-by-design — needs the specification written first |
| K10 | open-by-design — four of five clauses still broken, unchanged |
| K11 | not fixed, unguarded |
| K12 | the hang is fixed-and-guarded; **F5's note is dead code — §6.1** |

### One structural observation, which is the point of all of it

Three of tonight's five "fixed and mutation-tested" items — F2, F5, and the
button-order test — are **green tests over code that does not do what the test's
name says.** F2's guard asserts a function the render path never calls with the
state it tests. F5's guard does not exist, and the branch it would guard is
unreachable. The button-order test passes under the exact mutation it was
rewritten to catch. Report 16's own most important finding was *"a green test
guarding the bug"*; the repair round has produced three more.

The cheap systemic answer is the one §10 ends on: **assert the artefact, not the
function.** The right edge of the patch block on a rendered page. The text in the
log pane. The store on disk after the gesture. Every fault in this report that
survived did so behind a test that asserted the intermediate value instead.

**STATUS: challenged.**
