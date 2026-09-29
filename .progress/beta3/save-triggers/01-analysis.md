# The Create Chart tab's save triggers — Knut's three new cases (#182 beta 3)

Worktree `scratchpad/wt-182`, branch `feature/182-compliance-sets`, at
`72aa57f8`. Appended as each finding lands. Nothing here is a design decision.

Companion: `.progress/beta3/settings/01-analysis.md` (the five settings faults
fixed in `72aa57f8`), which this round builds on.

## 0. What Knut asked

> "When a ti1 file is loaded via the open ti1 icon button in Create Chart, or
> when applying a new patch set from the patch set editor. Both these cases also
> initiate the Generate Chart button action to update the preview, which also
> saves all the settings in the tab. Yet another case, which needs to be
> confirmed is the auto-update checkbox set to ON … Maybe that is now all the
> cases for Create Chart tab."

Three triggers, and one question: **is that now all of them?**

## 1. What the binding specification already says

`docs/design/per_target_settings.md` §3, the write table, verbatim:

| # | Event | Writes |
|---|---|---|
| W1 | **Generate Chart** | Create Chart's settings for that target |
| W2 | a preset is loaded | same — the preset has just decided them |
| W3 | a `.ti1` is loaded | same |
| W4 | a `.ti2` is loaded | same |
| W5 | auto-update preview redraws | same (the same code path as W1) |
| W6 | **leaving a tab** — including a target change (§2.1) and app quit | that tab's settings for the target being left |
| W7 | **Build Profile** pressed | tab 4's settings |
| W8 | **Start Measurement / Continue Measurement** pressed | the Measure tab's settings |

`docs/design/per_target_settings_test_plan.md` §6 repeats them as tests
(`W1 … W2–W4 preset / .ti1 / .ti2 loaded … W5 auto-update redraw …`).

**So two of Knut's three are already in the specification**, and have been since
2026-08-06:

| Knut's new case | Specification |
|---|---|
| a `.ti1` loaded from the icon button | **W3**, named |
| the auto-update checkbox ON | **W5**, named, *"the same code path as W1"* |
| applying a patch set from the patch-set editor | **NOT NAMED ANYWHERE** |

The third is the genuinely new one. Grepped across all of `docs/design/`: the
phrase *"applying a patch set from the editor"* appears once, in
`unified_measurement_management.md:344`, and it is about the **§4 warning
window**, not about settings:

> **Triggers:** Generate Chart · loading a `.ti1` · applying a patch set from
> the editor · auto-update · any preset change that regenerates.
>
> **Every one of them asks** (Knut, 2026-08-03, after beta.125 shipped with only
> two of them wired): *"the warning messages defined for section 4 … should then
> arrive for all these cases: Generate Chart, loading a .ti1, applying a patch
> set from the editor, any preset change that regenerates."*

That list is Knut's own, from a different document, and it is **one item longer
than §3's**: it also names *"any preset change that regenerates"*. So the same
five events were enumerated for warnings in August and only four of them reached
the settings table. That is the shape of the gap, and it was Knut's own list on
both sides.

Also relevant, and cited in full below where it bites:

- §2.0 — *"One target is live at a time, and it is the one the bar names."*
- §3a Q-4 — a write with nothing changed must cost nothing.
- §7 B — *"Loading settings must not trigger a rebuild."*
- §7 B's own note — *"the episode is the unit, not the flag"*, `_settle_live_preview`.

---

## 2. The one funnel: every one of the three ends at the same line

All three triggers reach the store through **one** call, and it is not the
Generate button's handler:

```
ui/tabs/tab_chart.py:17854      self.save_target_settings()
```

inside **`_on_generate_finished`** (`:17592`) — the *build-finished* handler, not
the *button-pressed* handler. Its own comment says why (`:17831`): *"THE CHART
THAT WAS JUST BUILT IS NOW THIS RUN'S OWN SETTINGS … §3 lists Generate Chart as
a write event … but the target-change handler was its only caller, so a build
never told the store what it had used."*

Every route that builds a chart is wired to that same handler, by name:

| Route | Line | `on_finish=` |
|---|---|---|
| Generate Chart button (`_on_generate`) | `:13769` | `_on_generate_finished` |
| **Load `.ti1` icon button** (`_on_load_ti1`) | `:14148` | `_on_generate_finished` |
| `_generate_from_ti1` — the shared re-layout | `:12419` | `_on_generate_finished` |
| Restore Used Chart | `:17270` | `_on_generate_finished` |
| Prebuilt preset (copy, no tool run) | `:12189` | called directly |
| Applied editor chart / preview refresh | via `_generate_from_ti1` | `_on_generate_finished` |

So **Knut's reading of the mechanism is exactly right**: *"Both these cases also
initiate the Generate Chart button action … which also saves all the settings in
the tab."* It is one write site, reached six ways.

`ui/tabs/tab_chart.py` has only **two** other `save_target_settings` calls, and
`ui/main_window.py` three:

| Where | Line | Event |
|---|---|---|
| `TabChart._on_target_changed` | `:17429` | W6 / §2.1 — writes the **outgoing** target explicitly |
| `MainWindow._save_settings_of_visible_tab` | `:1626` | Q-1 — a target pulldown opens |
| `MainWindow._save_settings_of_tab_left` | `:1658` | W6 — a tab change |
| `MainWindow.close_current_project` | `:1507` | every tab, on Close Project |

That is the complete set. §5 below enumerates the user actions that reach them.

---

## 3. TRIGGER 3 — "auto-update preview" ON  (spec W5)

Driven: `scratchpad/drv2/t1_auto_update.py`, `t1b_seed.py`, `t1c_who_deletes.py`,
on the real window against a copy of Knut's own `test` project (2 runs), run 1
selected, Profiling.

### 3.1 Does it save? Yes, and the trace names every line

```
  6.569  _generate_from_ti1
  6.769  _on_generate_finished
  6.776  json_write   run1/meta.json          <- _stamp_chart_meta
  6.840  save_target_settings  run1  wrote=True
  6.840  json_write   run1/cache/new_run.json
  6.841  json_write   run1/meta.json          <- the settings write
```

Stack, taken live at the write (`t1b_seed.py`):

```
tab_chart.py:15219 _seed_new_run_block
tab_chart.py:14892 save_target_settings
tab_chart.py:17854 _on_generate_finished
chart_creator.py:818 _finish
chart_creator.py:1497 _run_engine
chart_creator.py:1000 load_ti1_and_generate_preview
tab_chart.py:12416 _generate_from_ti1
tab_chart.py:19312 _auto_regenerate_preview     <- the debounce timer
```

**Store: `runs/run1`** — the selected run, every time. Over the whole drive the
set of stores written was `['run1']` and run 2's `meta.json` never moved.

### 3.2 Is the save correct? Yes, on this path

The panel holds what the user just dragged, and that is what is filed:
`_recipe_cols` in `runs/run1/meta.json` followed the spin box from 10 → 13 → 20.
This is W5 working as specified. The chart's own recipe cannot reach the store
here, because the chart being rewritten *is* the screen's recipe — the sidecar
is written **from** the panel, not read into it.

### 3.3 How often, and what it costs — MEASURED

| Drag | steps | pacing | builds | saves | `meta.json` writes |
|---|---|---|---|---|---|
| fast (a real drag) | 12 | 30 ms | **1** | **1** | 2 |
| slow (deliberate clicks) | 6 | 700 ms | **6** | **6** | **12** |

The 450 ms debounce (`_auto_preview_timer.start(450)`, `:19252`) restarts on
every change, so a continuous drag costs **one** render however long it is. The
fast drag fired `_maybe_schedule_auto_preview` **12 times** and rendered once.

**One render, end to end: 0.900 s** (change → chart on disk), of which 450 ms is
the debounce and ~190 ms the build. Three JSON writes per render:
`meta.json` (the chart stamp), `cache/new_run.json`, `meta.json` (the settings).

So **Knut's fear — "a user dragging a spin box could be writing to disk on every
step" — does not happen for a drag.** It happens for anything slower than
450 ms between changes: six deliberate clicks on a spin box's arrow, one every
0.7 s, rewrote the run's `meta.json` twelve times and re-ran printtarg and
rewrote the chart's `.ti2` and every page `.tif` six times. That is the real
cost, and it is the chart rewrite, not the settings write.

### 3.4 What the render also destroys — NOT in the specification

`_generate_from_ti1` → `chart_creator.load_ti1_and_generate_preview` →
`core/file_manager.py:2308 Run.reset_chart_artefacts`, which does:

```python
# exports/ AND cache/ ARE DERIVED, and go with the chart they describe.
for sub in (self.exports_dir, self.cache_dir):
    if sub.exists():
        shutil.rmtree(sub)
```

Traced live (`t1c_who_deletes.py`): **every live-preview render `rmtree`s the
selected run's `cache/` folder**, and `cache/new_run.json` is the New-run seed
block that §4a **N-4** deliberately put there (Knut, 2026-08-07: *"always … in
the cache/ folder"*). `save_target_settings` then re-creates it two lines later,
from the run now on screen:

```
>> new_run.json WRITE …/runs/run1/cache/new_run.json
   exists before = False
```

Consequences, both of which contradict a written rule:

- **§4a N-1 — *"The block is seeded only when it is empty"*** — is defeated. In
  practice the block is re-seeded on **every** preview render, so it tracks the
  run you are on. (That is closer to Knut's original sentence, *"the currently
  loaded run … is copied at the same time"*, than N-1 is — see DEF-7 in the
  companion analysis, where the opposite complaint was made.)
- **A New-run setup the user has typed is silently thrown away** by turning any
  layout knob on the run they came from, while auto-update is on.

`exports/` is deleted too, but is rebuilt by the same build (verified: run 1's
three sidecars are present and current after six renders), so nothing is lost
there. The comment at `:2300` says as much and is correct about `exports/`; it
is `cache/` that now holds something which is not derived.

---

## 4. TRIGGER 1 — a `.ti1` loaded from the icon button  (spec W3)

Driven: `scratchpad/drv2/t2_load_ti1.py`, `t6_ti1_traced.py`. Hostile pair built
through the UI (run 1: `targen -f 111`, 11 columns, 21 rows, 111 dpi, A4;
run 2: 222 / 22 / 12 / 222 / 130x180), a loose `.ti1` with its own sidecar, and
the real icon button (`tab._load_ti1_btn.click()`), the real destination window.

### 4.1 Does it save? Yes — one write, to the selected run

The button opens the real four-way window:

```
[Where should this patch set's chart go?]
  ['Cancel', 'Replace run 1', 'Build it as a new run instead',
   'Replace only the chart', 'Start a new project']
```

Answering **"Replace only the chart"**:

```
  RESTORE-CHART loaded.ti2   screen: cols=12 rows=18 dpi=200 f=600 p=130x180
  SAVE into <default:run1>   screen: (the same)                 wrote=True
```

One `save_target_settings`, resolved to `runs/run1` — the selected run.
Stack: `_on_generate_finished:17854` ← `chart_creator._finish` ←
`load_ti1_and_generate_preview` ← `_on_load_ti1:14148`. **W3 is wired.**

### 4.2 Is the save correct? Yes on this path, and deliberately so

The loaded file's own sidecar recipe **does** reach run 1's store — the seed went
from `1833157720` to the sidecar's `777777`, `targen -f` from 111 to 600, the
paper from A4 to 130x180. That is not an accident: `_on_load_ti1:14136` calls
`_apply_loaded_chart_settings`, which calls `_forget_what_the_chart_imposed()`
(`:11100`) — the shield is *deliberately* dropped, on the §10 ruling that
*"the chart sidecar will overrule the settings for the chart for that specific
run type"*. The user picked that file by name, so this is W3 + §10 working.

**It is worth flagging for the owner all the same**, because it means loading a
patch set silently replaces the run's paper size, margins, patch size, seed and
"use a fixed seed" tick with the file's — for a **"Replace only the chart"**,
whose own button text promises that everything else "stays put".

### 4.3 …but the round trip afterwards moved run 2's values into run 1

`t6`, immediately after the load, with nothing touched but the Profile-run
pulldown (run 1 → run 2 → run 1):

```
run 1 stored, before : targen-f=600  cols=12 rows=18 dpi=200
run 1 stored, after  : targen-f=222  cols=22 rows=12 dpi=222   <- run 2's values
```

The write that did it, with the screen recorded at the instant:

```
{'ev': 'SAVE', 'into': 'run1', 'screen': 'cols=12 rows=18 dpi=200 f=600',
 'wrote': True}          <- and the FILE received cols=22 rows=12 dpi=222 f=222
```

The screen and the file disagree, so the value written was not the screen's.
It came from the shield. **See §6 — this is a defect in the machinery, not in
the `.ti1` trigger, and it reproduces with no trigger at all.**

### 4.4 The controls

| Control | Result |
|---|---|
| `t3_control.py` — the same hostile pair, **four** round trips, no trigger | **clean**: 16 saves, every one `wrote=False`, both stores unchanged |
| `t7_shield_control.py` — as above **plus the two runs' charts made different on disk**, three round trips | **clean**: both stores unchanged |

So the ordinary case is sound at `72aa57f8`; the leak needs the extra condition
§6 names.

---

## 5. TRIGGER 2 — applying a patch set from the editor  (NOT in the specification)

Driven: `scratchpad/drv2/t9_editor_apply.py` (shield armed by prior run
switching) and `t10_editor_fresh.py` (stores staged on disk, one clean
selection). Both open the **real** Tools ▸ *Edit / create chart patch set*
window through `MainWindow._launch_tool("ti2_relayout")`, wait for it to load
run 1's 600-patch chart, and press its real **Apply / Save ▸ Overwrite**:

```
editor open, 600 patches, spec=True
DIALOG 'Apply or save this patch set' ['Overwrite', 'Save As…', 'Cancel'] -> Overwrite
```

### 5.1 Does it save? Yes — one call, and it is the same funnel

```
  BUILD from edited_patch_set.ti1
     <- main_window.py:2201 _apply_editor_chart
     <- ti2_relayout_dialog.py:7885 _save_and_apply
  SAVE into <default:run1>   screen: cols=10 rows=15 dpi=200 f=600 p=A4
     <- chart_creator.py:818 _finish  (i.e. _on_generate_finished)
     wrote=False
  LOAD sel=run1              screen: cols=11 rows=21 dpi=111 f=111 p=A4
     <- main_window.py:585 _on_tab_changed
     <- main_window.py:2203 _apply_editor_chart
```

Path: `Ti2RelayoutDialog._save_and_apply` → `MainWindow._apply_editor_chart`
→ `TabChart.apply_external_chart:11679` → `_generate_from_ti1:11751` →
`_on_generate_finished` → `save_target_settings`. **Knut is right that it goes
through the Generate action.** The store it resolves to is the selected run.

### 5.2 …but the save is a no-op, and the run ends up disagreeing with its chart

`wrote=False` in **both** drives — with the shield freshly armed and with it
armed by earlier switching. The chart was built from what was on screen
(10 columns, 15 rows, 200 dpi, A4), and the shield
(`_keep_the_targets_own_values`, `:14907`) put run 1's own stored values
(11 / 21 / 111) back into the snapshot before it was compared, so nothing
changed and nothing was written.

The shield is doing what it was built for: those on-screen values came from
run 1's *chart sidecar*, not from the user. But the **build used them**. So
after an editor apply:

| | value |
|---|---|
| the chart now on disk | laid out at 10 x 15, 200 dpi |
| `runs/run1/meta.json` | 11 x 21, 111 dpi |
| the panel, a moment later | 11 x 21, 111 dpi (the tab change re-loaded it) |

That is the exact fault the write at `:17854` was added to prevent, quoted in
its own comment (Basti, 2026-08-16): *"the run's stored settings load, four
times, putting 17 columns and 14 mm back on screen … the live preview rebuilds
the chart from THAT"*. It is reachable again through this door, because the
write is a no-op on it.

### 5.3 A second, undocumented save: the apply changes the TAB

`_apply_editor_chart:2203` does `self._tabs.setCurrentWidget(self._tab_chart)`.
When the editor was opened from any tab other than Create Chart, that is a
**tab change** — W6 — so it also fires
`MainWindow._save_settings_of_tab_left:1658` for the tab being left and
`_load_settings_of_tab_entered:585` for Create Chart. Observed above: the LOAD
came from `_on_tab_changed`, and it is what put 11 / 21 / 111 back on screen.

So one press of "Apply / Save ▸ Overwrite" reaches the settings machinery
**twice**, by two different events, and the specification names neither.

### 5.4 An ordering hazard this exposes

With the ChromIQ layout engine ON the build runs **in process**
(`chart_creator._run_engine`), so the save lands *before* the tab switch. With
the engine off the build is `printtarg` in a `QProcess`, so the tab switch and
its load happen **first** and the build's save happens after, against a panel
the load has already changed. The two orders file different things. This is the
same asynchrony the test plan already had to correct N3 for
(*"`QProcess.start` … is asynchronous. Nothing on disk has moved when the call
returns"*).

---

## 6. DEFECT — the shield remembers one run's value and spends it on another

**This is the one that writes the wrong run's store, and it needs no trigger.**

`scratchpad/drv2/t8_shield_leak.py`. Everything staged on disk **before the app
starts**; the only thing done on screen is picking a run in the bar, twice.

Setup:

```
run 2 stores targen -f = 222 ; its chart imposes 600  -> the shield will hold 222
run 1 stores targen -f = 600 , which is exactly what is on screen once run 2's
      chart has spoken, so loading run 1 moves no widget
```

The whole run:

```
start (run 1 selected): run1 stored targen-f = 600 | run2 stored targen-f = 222

===== pick run 2 =====
  SAVE into <default:run1>  screen f=600  shield {}            wrote=False
    LOAD sel=run2           screen f=222
  SAVE into run2            screen f=222  shield {}            wrote=False
    LOAD sel=run2           screen f=222
    RESTORE-CHART           screen f=600            <- the chart imposes 600

===== pick run 1 again — NOTHING ELSE TOUCHED =====
  SAVE into <default:run2>  screen f=600  shield {'targen-f': (222, 600)}  wrote=False
    LOAD sel=run1           screen f=600            <- run 1 stores 600: NO WIDGET MOVES
  SAVE into run1            screen f=600  shield {'targen-f': (222, 600)}  wrote=True
    LOAD sel=run1           screen f=222            <- reading back what was just written
    RESTORE-CHART           screen f=600

after: run1 stored targen-f = 222 | run2 stored targen-f = 222
```

**Run 1's stored value went from 600 to 222 — run 2's — with no user edit, no
build and no trigger. Two clicks in the Profile-run pulldown.** That is
`docs/design/per_target_settings.md` §2.0 broken in its own words: *"it must
never be written by the act of looking at a different target."*

### The mechanism, line by line

1. While run 2 is selected, `_note_what_the_chart_imposed` (`:14590`) records
   `_chart_imposed = {'params': {'targen-f': (run 2's own 222, the chart's 600)}}`
   and connects each affected widget's signal to `_release_ui_values_that_moved`
   (`:14713`).
2. The shield is released **only by a widget moving** (`:14692`). It is not
   scoped to the target it was taken for, and nothing clears it on a target
   change: `_note_what_the_chart_imposed` re-arms it for the incoming target,
   but it runs at the *end* of `_on_target_changed` (`:17521`), after the write.
3. Picking run 1 loads run 1's stored 600 over a widget that already shows 600.
   **No `valueChanged`, so no release.** The shield built for run 2 is still up.
4. `_on_target_changed:17429` writes run 1. `save_target_settings:14907` calls
   `_keep_the_targets_own_values(wanted, ui_state)`, which substitutes the
   shield's "own" value — **222, which is run 2's** — into run 1's snapshot.
5. That is written to `runs/run1/meta.json`.

### Why it hides

The shield is normally released by step 3, because loading a different run's
settings usually *does* move the widgets. It survives exactly when **the
incoming run's stored value already equals what is on screen** — which is
common in real use, because the value on screen at that moment is the
*outgoing run's chart's* value, and two runs of one project very often share a
chart recipe. It is also what the `.ti1` load produces on purpose (§4.3),
which is how this was found.

### Why the existing controls did not catch it

`t3` and `t7` both differ from `t8` in one respect only: the incoming run's
stored values are **not** equal to what is on screen, so the load moves the
widgets and releases the shield. `scripts/drive_per_target_settings.py` (the
sanctioned acceptance driver) builds every target with distinct values for the
same reason the test plan asks for it (*"Each sets an unusual value on a
different target first, so 'opens on defaults' cannot pass by accident"*) — and
that is precisely the arrangement in which this defect cannot fire.

---

## 7. Edge cases, driven one per process (`scratchpad/drv2/t12_edge.py`)

Each phase runs in its own process against its own copy of the project, because
the first attempt (`t11_edges.py`) let one phase change the state the next one
measured.

### E1 — no run selected ("New run"), auto-update ON, a knob turned

**Nothing happens at all.** No build, no save, no write of any kind.
`_current_ti1_path` is `None` on a New run, and `_maybe_schedule_auto_preview`
(`:19246`) declines on that. Both existing `new_run.json` blocks were left alone.
**Correct** — §4a: a New run has no store.

### E2 — a run with NOTHING stored, auto-update ON, ONE knob turned

`runs/run2/meta.json` had `create_chart_settings` and `create_chart_ui` removed
(§4 S4 / S9 — a deleted file, or a run made before the feature).

```
screen at the save : targen-f=600  printtarg-p=130x180  paper=130x180
                     cols=16  rows=18  dpi=200  seed=4242
written to the store: targen-f=0    printtarg-p=A4       paper=A4
                     cols=16  rows=0   dpi=300  seed=None
```

**Only `area_cols` — the one knob the user moved — matches the screen.
Everything else was filed as factory defaults**, for a chart that is 130x180
with 18 rows at 200 dpi. Same cause as §6: the shield's "own value" for a
nothing-stored run is the neutral reset, and it is substituted for every field
the user has not personally touched.

### E5 — the same run, but **Generate Chart** pressed (this is W1, not a new trigger)

```
screen  : targen-f=600 printtarg-p=130x180 paper=130x180 cols=12 rows=18 dpi=200 seed=4242
store   : targen-f=0   printtarg-p=A4      paper=A4      cols=0  rows=0  dpi=300 seed=None
```

**Not one field of the chart just built reached the store.** The run now records
"A4, 0 columns, 0 rows, 300 dpi" for a chart that is 130x180 with 12 x 18
patches. This is the tab's own main button, on the most ordinary case there is —
a run whose settings file has never been written, or was deleted (Knut's
*"some cases can occur if user deletes a file"*, §4 S4).

### E3 — Run type changed 120 ms into the 450 ms debounce

```
WRITE runs/run1/meta.json
SAVE  into <default:runs/run1>   screen cols=15 …   wrote=True
   <- measurement_target_bar.py:222 set_run_type        (Q-1, the outgoing target)
WRITE runs/run1/verifications/cache/new_run.json
WRITE runs/run1/verifications/meta.json
SAVE  into runs/run1/verifications   screen cols=0 dpi=300 …   wrote=True
   <- measurement_target_bar.py:224 set_run_type        (_on_target_changed)
```

- The queued render was **cancelled**, not run (`_cancel_pending_auto_preview`
  at the top of `_on_target_changed`). Good.
- The knob turn was filed against the **profiling** run — `rec.area_cols`
  12 → 15, and nothing else moved. **Correct.**
- The **verification** store was then created on arrival, holding factory
  defaults (`cols=0 rows=0 dpi=300 paper=A4`). §4 S5 says a verification with
  nothing stored opens on defaults and S9 that it records its own on first use,
  so this is defensible — but it is a write to the **incoming** target at the
  moment of arrival, which §2.1 does not describe.

### E4 — Close project 200 ms after a knob, while the preview is still pending

```
SAVE into <default:runs/run1>  screen cols=16 …  wrote=True     <- close_current_project
WRITE runs/run1/meta.json  x3
WRITE runs/run1/cache/new_run.json
SAVE into None  sel=(New run)  wrote=True
   <- measurement_target_bar.py:691 reset_to_empty
   <- main_window.py:1387 _reset_after_project_gone
   <- main_window.py:1514 close_current_project
```

- The queued render was cancelled. **No chart was rewritten.** Good.
- The knob turn reached the run's store before the project closed
  (`rec.area_cols` 12 → 16). **Correct and desirable.**
- **But the close then writes again, after the project is closed**: clearing the
  bar fires `about_to_change_target`, the Q-1 trigger, which lands on the
  New-run branch and writes `runs/run1/cache/new_run.json` into the project
  that has just been shut. §2.0 says there is *"no flush on quit, not a sweep"*.
  Harmless in itself (`cache/` is disposable) but it is one more writer nobody
  listed, and it fires on the way out of a project.
- The project was **not** deleted and remains on disk. Correct.

---

## 8. THE COMPLETE LIST OF SAVE PATHS FOR THE CREATE CHART TAB

Every route, from the code, with the specification row it belongs to. ✱ marks
the ones the specification does **not** name.

### A. Through `_on_generate_finished:17854` — "a chart was built"

| # | User action | Code path | Spec |
|---|---|---|---|
| A1 | **Generate Chart** button | `_on_generate:13769` (+ its four `.ti1` branches at `:13411/13437/13486/13522/13536`) | **W1** |
| A2 | **A preset that carries a patch set** is chosen | `_on_preset_selected:9119` → `_apply_tc918_preset:10758` / `_apply_knut_preset:11001` / `_generate_from_ti1` | **W2** |
| A3 | **A prebuilt-files preset** is chosen | `_create_prebuilt_target:12189` calls `_on_generate_finished` directly | **W2** |
| A4 | **The `.ti1` icon button** | `_on_load_ti1:14148` | **W3** |
| A5 | **Open Chart File (.ti2)** | `reflect_loaded_chart` / `_import_applied_chart:11889` | **W4** |
| A6 | ✱ **Apply / Save ▸ Overwrite in the patch-set editor** | `_apply_editor_chart:2201` → `apply_external_chart:11753` → `_generate_from_ti1` | **not named** |
| A7 | **Auto-update preview redraw** | `_auto_regenerate_preview:19312` → `_generate_from_ti1(preview=True)` | **W5** |
| A8 | ✱ **Restore Used Chart**, when it has to redraw the pages | `rebuild_verification_pages:17270` | not named (§2 L5 covers the *load*, not the write) |
| A9 | ✱ **Create a gamut chart** | `_on_generate_gamut:16751` → `_generate_from_ti1` | not named |

### B. Through `TabChart._on_target_changed:17429` — "the target changed"

| # | User action | Spec |
|---|---|---|
| B1 | Profile run picked | W6 / §2.1 |
| B2 | Run type picked (incl. Verification) | W6 / §2.1 |
| B3 | A verification date picked | W6 / §2.1 (§2 "not a separate event") |
| B4 | ✱ A run **deleted** (the selection moves) | not named; guarded since `set_profile_run(save_outgoing=False)` |
| B5 | ✱ A run **duplicated** (the selection moves) | not named |
| B6 | ✱ **Restore Used Chart** (refresh path, `main_window:1303`) | not named |

### C. Through `MainWindow._save_settings_of_visible_tab:1626` — Q-1

Fires on **`about_to_change_target`**, i.e. every `set_profile_run`,
`set_run_type` and `set_verification_id`, whether a person opened the pulldown
or the app moved the bar itself. That includes:

| # | Action | Spec |
|---|---|---|
| C1 | the pulldown opens | **Q-1** |
| C2 | ✱ the `.ti1` load choosing "Build it as a new run instead" (`_on_load_ti1` → `ctl.set_profile_run("")`) | not named |
| C3 | ✱ a preset creating a run and landing the bar on it | §4b, implied |
| C4 | ✱ **Close project** → `reset_to_empty:691` (measured, §7 E4) | not named, and §2.0 arguably forbids it |
| C5 | ✱ a build that creates or re-aligns a run and moves the bar | not named |

### D. Through `MainWindow._save_settings_of_tab_left:1658` — the tab changed

| # | Action | Spec |
|---|---|---|
| D1 | the user clicks another tab | **W6** |
| D2 | ✱ the patch-set editor's apply, which switches to Create Chart itself (`main_window:2203`) | not named |
| D3 | ✱ any other code that calls `setCurrentWidget` | not named |

### E. The rest

| # | Action | Code | Spec |
|---|---|---|---|
| E1 | **App quit** | `main_window:2977 closeEvent` → `_save_settings_of_tab_left` | **W6q** |
| E2 | **Close project** — every tab, deliberately | `main_window:1507` | §2.1, and it contradicts §2.0's "never a sweep" |

### So: is that all the cases for Create Chart?

**No — Knut's three are not the last three.** His list plus §3's leaves at least
these unnamed: the patch-set editor apply (A6 **and** D2, two events from one
press), Restore Used Chart's redraw (A8/B6), the gamut chart (A9), a run being
deleted or duplicated (B4/B5), Close project's second write (C4), and any
programmatic move of the bar or the tab (C2/C3/C5/D3).

**One thing his list names that the code does not do:** a preset that only fills
the panels — no bundled `.ti1`, no build — reaches **no** `save_target_settings`
at all. Every write in `_on_preset_selected` comes from the build. Measured for
a preset **with** a patch set (`t13_preset.py`: `wrote=True`, the paper went A4
→ 130x180); the no-patch-set case is a code reading only, because a user preset
without a `.ti1` did not appear in the combo, and it should be measured before
anything is changed for it.

---

## 9. Where the code contradicts a binding rule

| # | Rule, quoted | What the code does | Evidence |
|---|---|---|---|
| G-a | §2.0 *"A per-target setting has exactly one writer … it must never be written by the act of looking at a different target"* | picking run 2 and then run 1 writes **run 2's** value into run 1's store | §6, `t8_shield_leak.py` |
| G-b | §4c **D-4** *"The app's own starting point — factory settings, `default_recipe`, saved defaults — is **not** an answer"* | for a run with nothing stored, the app's own starting point is treated as the answer and written over what is on screen and over the chart just built | §7 E2/E5, `t12_edge.py E2/E5` |
| G-c | §3 W1 and its own comment at `:17831` *"THE CHART THAT WAS JUST BUILT IS NOW THIS RUN'S OWN SETTINGS"* | on the editor-apply path the write is a no-op, so the run keeps a layout that is not the chart's | §5.2, `t9`/`t10` |
| G-d | §4a **N-1** *"The block is seeded only when it is empty"* | every live-preview render `rmtree`s `cache/`, so the block is re-seeded on every render and a New-run setup the user typed is destroyed | §3.4, `t1c_who_deletes.py` |
| G-e | §2.0 *"not a flush on quit, not a fan-out"* | Close project writes every tab (deliberate, §2.1) **and then** writes a New-run block into the project it has just closed | §7 E4 |
| G-f | §3 W2 *"a preset is loaded → writes Create Chart's settings for that target"* | a preset that only fills the panels never calls `save_target_settings`; only a preset that builds does | §8 A2, code read + `t13` for the building case |
| G-g | §3's write table is the complete list of write events | at least nine further routes reach a write (§8) | §8 |
| G-h | §4a **N-3** *"Generate Chart copies it into the new run"* | it copies the parameters only; the whole layout recipe, the engine tick and the module are dropped | §13.1 |

Two of these — G-a and G-b — write values the user never chose into a run's
store, which is the failure the whole feature exists to prevent. The rest are
gaps between the document and the code rather than damage.

---

## 10. Implementation plan

Small pieces, reuse first. Nothing here needs a new store, a new file or a new
trigger. Pieces 1–4 need no design decision; 5–8 wait on §12.

**Phase 1 — stop the store being written with another target's values**

1. **Scope the shield to the target it was taken for.** In
   `_note_what_the_chart_imposed` (`:14590`), record the store's identity
   beside `_chart_imposed` — reuse `self._target_settings_key()` (`:15285`),
   which already exists for exactly this "name the target" job. In
   `_keep_the_targets_own_values` (`:14753`), return without doing anything
   when that identity is not the one being written. ~6 lines. **Kills §6 / G-a
   outright**, and does not disturb any case where the shield is used for its
   own target.

2. **End the episode explicitly.** In `_on_target_changed`, after the write at
   `:17429` and **before** `load_target_settings()`, drop the previous target's
   shield with the existing `_release_imposed_connections()` /
   `self._chart_imposed = {}`. The outgoing write has already had its use of
   it. Belt and braces with piece 1, and it makes the lifetime readable — the
   same *"the episode is the unit, not the flag"* discipline `_settle_live_preview`
   already applies to the live preview.

3. **A target with nothing stored has no "own values" to protect.** In
   `_note_what_the_chart_imposed`, do not arm the shield when the target's
   store held no `create_chart_settings` — §4c **D-4** in its own words. The
   snapshot in that case is the factory reset, and shielding it is what wrote
   "A4, 0 columns, 300 dpi" over a 130x180 chart (§7 E2/E5). The store has
   already been read one line later in `save_target_settings`; the cheapest
   correct place to decide it is where `_own_values_before_chart` is taken
   (`:17456`), which is inside `_on_target_changed` and can ask
   `store.load_meta()` once.

4. **Keep the New-run block out of the chart artefact sweep.** In
   `core/file_manager.py:2300 Run.reset_chart_artefacts`, delete the contents of
   `cache/` **except** `new_run.json` rather than the folder. One condition.
   Kills G-d without touching §4a N-4's ruling that the block lives in `cache/`.

4b. **The New-run block must carry the layout too.** `_adopt_new_run_settings`
   (`:15242`) writes `meta.create_chart_settings = held` and nothing else. The
   block is written by `save_target_settings`'s store-is-None branch (`:14848`)
   from `snapshot(self)` alone, so the `create_chart_ui` bucket never enters it
   either. Both ends need the same one extra key. Reuse `_collect_ui_state()`
   / `_apply_ui_state()`, which already exist and are already what the normal
   store uses. **Kills §13.1.**

**Phase 2 — the events nobody listed**

5. **The editor apply should change the tab first, then apply.** In
   `MainWindow._apply_editor_chart` (`:2201`), move
   `self._tabs.setCurrentWidget(self._tab_chart)` **above** the
   `apply_external_chart` call. The tab-change load then happens before the
   build instead of on top of its result, and the engine-on / engine-off
   ordering difference (§5.4) stops mattering. Two lines moved.

6. **Close project must not write on the way out.** `reset_to_empty`
   (`measurement_target_bar.py:691`) should move the selection with the
   existing `save_outgoing=False` argument that `set_profile_run` already
   carries for the delete case (`:226`). Reuse, no new mechanism. Kills G-e.

**Phase 3 — the specification**

7. **Add the missing rows to §3.** W3a *applying a patch set from the editor*,
   W6b *a tab change the app makes itself*, and the routes in §8 marked ✱.
   Knut's own list in `unified_measurement_management.md:344` already names the
   patch-set apply and *"any preset change that regenerates"* for the §4
   warning; the settings table should say the same five things.
   **This is a specification edit and needs approval, not a commit.**

8. **Say plainly whether a preset that only fills the panels writes.** §3 W2
   says it does; the code only writes when a preset builds. Either wire it or
   correct the row (§12 Q7).

**Phase 4 — proof**

9. Regression tests, one per measured fault, each of which fails at `72aa57f8`:
   the shield does not survive a target change (`t8`); a run with nothing stored
   records the chart it just built, not the factory defaults (`E5`); a live
   preview render does not delete `cache/new_run.json` (`t1c`); Close project
   writes nothing after the project is closed (`E4`).
10. Extend `scripts/drive_per_target_settings.py` with a pair of runs whose
    stored values **match what the other run's chart puts on screen** — the
    arrangement in which §6 fires and which the driver's "make every target
    different" rule currently excludes by construction.
11. Re-run the sanctioned driver (0 failures) and the full gate
    `QT_QPA_PLATFORM=offscreen pytest --runslow -n auto`.

---

## 11. Edge cases, each with the rule that must hold

| # | Case | The rule that must hold | State at `72aa57f8` |
|---|---|---|---|
| X1 | `.ti1` loaded into the selected run ("Replace only the chart") | the file's recipe may reach the store, because the user named the file (§10 sidecar precedence) | **holds** |
| X2 | `.ti1` loaded with "Build it as a new run" | the write that precedes the bar's move belongs to the run being left | **holds** (§13: the write into run 1 is a no-op, and the New-run block takes the screen) |
| X2b | `.ti1` loaded with "Build it as a new run" | the new run records the chart it was given | **broken** (§13.1) |
| X3 | `.ti1` loaded with "Start a new project" | nothing is written into the old project | not measured |
| X4 | patch set applied from the editor | the chart just built is what the run records | **broken** (§5.2, G-c) |
| X5 | patch set applied while standing on another tab | one press must not file two different snapshots | **at risk** (§5.3/5.4, D2) |
| X6 | auto-update ON, a drag | one render, one write, whatever the drag's length | **holds** (§3.3) |
| X7 | auto-update ON, slow repeated clicks | each render files the screen, into the selected run only | **holds**, at ~0.9 s and 3 JSON writes per click (§3.3) |
| X8 | auto-update ON, a New run selected | nothing is written anywhere | **holds** (E1) |
| X9 | auto-update ON, a run with nothing stored | the run records what is on screen | **broken** (E2) |
| X10 | Generate Chart on a run with nothing stored | the run records the chart it just built | **broken** (E5) |
| X11 | run type changed inside the debounce | the queued render is dropped; the knob is filed against the outgoing target | **holds** (E3) |
| X12 | project closed inside the debounce | the queued render is dropped; the last edit is filed; nothing is written after the close | **half** — the first two hold, the third does not (E4) |
| X13 | two runs, one selected then the other then back, nothing touched | neither store changes | **holds** when their stored values differ from the screen; **broken** when they do not (§6) |
| X14 | a run whose stored value equals what the other run's chart shows | the same rule as X13 | **broken** (§6) |
| X15 | a New-run block the user has set up, then a preview render on the run it came from | the block survives | **broken** (§3.4, G-d) |
| X16 | a preset with a bundled patch set | the preset's values are recorded for the target (W2) | **holds** (`t13`) |
| X17 | a preset that only fills the panels | W2 says recorded | **not wired** (code read) |
| X18 | the seed a chart was shuffled with | never recorded as the user's choice unless they ticked it | **holds** (`t13`: screen 1307302005, store `null`) |

---

## 12. Open questions for the owner

Plain language, each with a recommendation and its one-line reason.

1. **When you pick one run and then another and come back, may ChromIQ ever
   change what the first run has stored?**
   *Recommend: never.* It can today (§6): run 1's "648 patches" became run 2's
   "222" with nothing touched but the pulldown.

2. **A run whose settings file is missing or has never been written — when you
   press Generate Chart, should it record the chart it has just built, or the
   app's factory defaults?**
   *Recommend: the chart it has just built.* Today it records A4, 0 columns,
   300 dpi for a 130x180 chart with 12 x 18 patches, and the specification's own
   rule D-4 says the app's starting point is not an answer.

3. **When you apply a patch set from the patch-set editor, should the run's
   stored settings become the layout that chart was actually built with?**
   *Recommend: yes.* Today the run keeps its older layout, so the panel and the
   sheet disagree from the moment the editor closes.

4. **Loading a `.ti1` with "Replace only the chart" also replaces your paper
   size, margins, patch size and seed with the file's. Is that what "replace
   only the chart" should mean?**
   *Recommend: yes, keep it, but say so in the button's own text.* The layout
   is how the sheet was made, so restoring one without the other is the bug
   this feature exists to remove; but the button currently promises that
   everything else "stays put".

5. **With "Auto-update preview" on, six deliberate clicks on a spin box arrow
   rebuild the chart and rewrite its files six times, about 0.9 s apart. A
   continuous drag costs one. Is six acceptable, or should slow clicking be
   coalesced too?**
   *Recommend: leave it.* It is honest, it is what the option promises, and the
   drag — the case that worried you — already costs one.

6. **Your "New run" setup is kept in the run's `cache/` folder, and building a
   chart empties that folder. So turning any layout knob while auto-update is on
   throws away a New run you had set up. Should the block survive?**
   *Recommend: yes, keep it.* It is the only thing in `cache/` that is not
   derived from the chart.

7. **Choosing a preset that only fills the panels — no patch set of its own —
   records nothing for the run until something else happens. The specification
   says a preset is recorded the moment it is loaded. Which is right?**
   *Recommend: record it.* You chose it by name, which is the same reason §4b
   already says a preset that creates a run owns that run's settings.

8. **When you close a project, ChromIQ writes one more small file into it on
   the way out. Should closing write anything at all after the project is
   closed?** *Recommend: no.* Nothing is lost by stopping it; the real save
   already happened a moment earlier.

9. **The list of moments that save the Create Chart tab is longer than either of
   our lists. Should the specification name every one of them (§8), including
   the ones ChromIQ triggers itself — a run being deleted, a run being
   duplicated, the editor switching the tab for you?**
   *Recommend: yes.* Every one of them is a write, and a write nobody has
   written down is how three of the faults above survived.

11. **When you load a patch set into a brand new run, should that run remember
    the page layout the chart was built with, or only the patch recipe?**
    *Recommend: both.* Today it keeps the patch count and forgets the paper
    size, the columns, the rows, the resolution and the layout engine tick.

10. **After you pick a run, the log says "Restored the chart's own layout
    settings … now show the values this chart was made with" — every time, three
    times over in one switch. Should that line appear when you have only picked
    a run?** *Recommend: only for Restore Used Chart.* It reads like something
    you asked for.

---

## 13. The `.ti1` load's other destination: "Build it as a new run instead"

`t6_ti1_traced.py "Build it as a new run instead" newrun`. Same hostile pair,
same loose `.ti1`. The load creates **run 3** and lands the bar on it.

```
SAVE into <default:run1>  screen cols=10 rows=15 dpi=200 f=600   wrote=False
  LOAD sel=''             (New run)
SAVE into None            screen cols=10 rows=15 dpi=200 f=600   wrote=True
                                                 ^ the New-run block
  LOAD sel=run3           screen cols=0 rows=0 dpi=300 f=600   <- the new run's own
SAVE into run3            screen cols=0 rows=0 dpi=300 f=600   wrote=True
```

Result:

```
run 3 stored : targen-f=600  paper=A4  cols=0  rows=0  dpi=300  seed=None
the chart it just built: the loaded patch set, laid out at 100x150, 10 x 15, 200 dpi
```

### 13.1 The New-run block carries the parameters and drops the layout

`targen -f` (a **parameter**) survived the New-run block into run 3; every
layout value (paper, columns, rows, dpi, seed, the engine tick) did not.
`_adopt_new_run_settings:15242` writes

```python
meta.create_chart_settings = held
new_run.save_meta(meta)
```

and never touches `meta.create_chart_ui` — the bucket that holds `mode`,
`stamp`, `guided`, `engine_on`, **`engine_recipe`** and `gamut`. The whole
ChromIQ layout recipe is dropped on the way into a new run.

§4a **N-3**: *"Generate Chart copies it into the new run and clears it."* It
copies half of it. The companion analysis already noted that the
`create_chart_ui` bucket *"is not in the specification at all"*; this is what
that costs.

### 13.2 …and the round trip then leaks run 1's value into run 3

```
run3 -> run1 -> run3, nothing touched
  SAVE into run3   screen cols=0 rows=0 dpi=300   wrote=True
run 3 stored targen-f:  600  ->  111        <- run 1's value
```

**§6 again, on a different path and with a different value.** It is the same
mechanism: run 3's stored `targen-f` (600) was still what the screen showed when
run 3 was re-selected, so no widget moved, so the shield armed for run 1 was
spent on run 3.

This is the second independent reproduction of §6, and it is the strongest
argument that the fix belongs in the shield's scoping (plan piece 1) rather than
anywhere near the three triggers.
