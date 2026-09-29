# Settings leaking between runs — analysis (#182 beta 3 round)

Worktree: `scratchpad/wt-182`, branch `feature/182-compliance-sets` (v4.3.0-beta.1).
Knut's material: `scratchpad/knut-2026-09-09/` (test project, 4 preset archives,
2 session logs from 2026-09-09, app v4.2.1).

Appended as each thing is measured. Nothing here is a design decision; the
binding documents are `docs/design/per_target_settings.md` and its test plan.

## A. The agreed design, cited

`docs/design/per_target_settings.md`:

- §2.0 — *"One target is live at a time, and it is the one the bar names."*
  Every load/write touches that target and no other. **This is the rule Knut is
  quoting back at us.**
- §2 table L1 tab activated / L2 Open Project / L3 Profile run changes /
  L4 Run type changes / L5 chart opened or Restore Used Chart / L6 preset
  loaded / L7 .ti1-.ti2 loaded / L8 app start.
- §2.1 — a target change is **write the outgoing target, then load the incoming
  one**, in one guarded step.
- §3 table W1 Generate Chart / W2 preset loaded / W3 .ti1 / W4 .ti2 /
  W5 auto-update redraw / W6 leaving a tab (incl. target change and app quit) /
  W7 Build Profile pressed / W8 Start-Continue Measurement pressed.
- §3a Q-1 write fires when a target-changing pulldown **opens**; Q-2 read fires
  when an option is **selected**; Q-4 a write with nothing changed costs nothing.
- §4 S1-S10 what a target with nothing stored opens on; §4a N-1..N-6 the New-run
  seed; §4b P-1..P-3 a preset creating a target; §4c D-1..D-4 an instrument
  default is not an override.
- §5 scope: Create Chart, Measure, Build Profile, Calibration & Profiling.
  Print Chart and Check & Refine out of scope "for now".
- §7 B — loading settings must not trigger a rebuild.
- §10 F1 verification has its own store; F2 every tab saves/reloads the same
  way; **sidecar precedence**: *"The charts sidecar is the correct value to use.
  When a chart is restored, the chart sidecar will overrule the settings for the
  chart for that specific run type."*

### Knut's five rules of 2026-09-09 vs the specification

| Knut's rule (2026-09-09) | The specification says |
|---|---|
| 1. Save the tab when a profile-run / run-type box is **clicked** | **Same** — §3a Q-1, in his own words from 2026-08-06 |
| 2. Load the tab when an option in those boxes is **selected** | **Same** — §3a Q-2, §2 L3/L4 |
| 3. Save the active tab on a tab change, then load the tab moved to | **Same** — §2 L1 + §3 W6 |
| 4. Save the active tab when its main button is pressed | **Same** — §3 W1/W7/W8 |
| 5. **Load from a preset when a preset is selected, then save those settings, and save again whenever any of the above happens** | §2 L6 + §3 W2 say the first half (a preset loads into the panels and W2 records it). The **"save again whenever any of the above happens"** half is not stated anywhere; and §4b (Basti, 2026-09-02) adds P-1..P-3, which the 2026-09-09 list does not mention |

Nothing in his list contradicts the specification. What his list does **not**
cover, and what the reports below actually turn on, is §10's sidecar-precedence
ruling: what a **chart file on disk** is allowed to put on screen when a run is
merely *selected* (as opposed to explicitly restored). §2's L3/L4 rows say only
"the target's settings load"; the code additionally re-applies the chart
sidecar. `ui/tabs/tab_chart.py:17296-17305` says so in its own words:
*"`_display_run_chart` -> `_restore_chart_settings` runs a few lines below and
lays the chart sidecar's own recipe over what was just loaded here. Whether it
should is §10's question and is not settled."*

## B. The map of the code (citations)

| Concern | Where |
|---|---|
| What a per-target parameter IS (registry, snapshot, apply) | `workflow/per_target_settings.py` — `params_for`, `snapshot`, `apply` |
| Which store the bar points at | `workflow/per_target_settings.py:210 store_for_target` — Profiling → `runs/runN`, Verification → `runs/runN/verifications`, Calibration → `cal/`, New run → **None** |
| The New-run seed block | `per_target_settings.py:new_run_seed_path/seed_for_new_run` → `<target>/cache/new_run.json` |
| Write trigger Q-1 (pulldown OPENS) | `ui/measurement_target_bar.py:786,835` `about_to_open → about_to_change_target`; `ui/main_window.py:296 → _save_settings_of_visible_tab` (`:1614`) |
| Read trigger Q-2 (option selected) | `ui/main_window.py:305 changed → _load_settings_of_visible_tab` (`:1631`) |
| Tab change W6 / L1 | `ui/main_window.py:411 currentChanged → :584 _save_settings_of_tab_left`, `:585 _load_settings_of_tab_entered` |
| App quit | `ui/main_window.py:2977` |
| Close project | `ui/main_window.py:1485 close_current_project` (saves EVERY tab), then `:1361 _reset_after_project_gone` |
| Create Chart store | `ui/tabs/tab_chart.py:14657 save_target_settings`, `:14902 load_target_settings`, `:15170 _collect_ui_state`, `:15227 _apply_ui_state` |
| Create Chart target change | `ui/tabs/tab_chart.py:17230 _on_target_changed` (write outgoing → cal knobs → load → snapshot → **display the chart**) |
| The chart sidecar's own restore | `ui/tabs/tab_chart.py:11131 _restore_chart_settings` (recipe, engine on/off, printtarg fields, and the whole `create_chart_settings` registry) |
| The shield that keeps the chart's values out of the store | `:14494 _note_what_the_chart_imposed`, `:14595 _release_ui_values_that_moved`, `:14621 _keep_the_targets_own_values` |
| Measure store | `ui/tabs/tab_measure.py:1273/1319`, key `measure_settings` |
| Build Profile store | `ui/tabs/tab_profile.py:2156/2205`, key `profile_settings` |
| Print Chart store (out of scope in §5, but wired) | `ui/tabs/tab_print.py:1060/1113`, key `print_settings` |
| The two text fields | `tab_chart._refresh_target_text` / `_load_target_text` / `_set_target_text_fields`; cleared on close by `clear_loaded_project` (names only) |

**The split, and whether it is written down.** Per target: everything the four
in-scope tabs' registries yield, plus Create Chart's `create_chart_ui` bucket
(`mode`, `stamp`, `guided`, `engine_on`, `engine_recipe`, `engine_cal`,
`gamut`). Per project: the project name, `project.json`. Global: Preferences.
§1.1/§1.2 of the specification states the dividing line in prose; the
`create_chart_ui` bucket is **not** in the specification at all — it grew from
Knut's beta.3 bug test and lives only in the code. `GLOBAL_FLAGS` in
`per_target_settings.py` is deliberately empty, so nothing is declared global at
parameter level.

**One thing that is per target and also global.** `use_chromiq_layout_engine` is
an `AppSettings` key. `_apply_ui_state` writes it on every target load
(`tab_chart.py:15281`), so the last target visited leaves its value in the
installation-wide store. Knut's own log shows it moving 40+ times in one
session (`07-chromiq.log`, `settings.set use_chromiq_layout_engine = …`).

## C. What was driven, and how

Every run below is the REAL app on screen (`QApplication`, Fusion, the real
`MainWindow`), settings sandboxed (`CHROMIQ_SETTINGS_FILE`, plus a per-run
temporary `.ini` in place of `QSettings`), presets sandboxed
(`CHROMIQ_PRESETS_DIR`), projects in a scratch folder. Drivers:
`scratchpad/drv/d1..d15`. Shots are `QWidget.grab()` of the window itself, never
`screencapture` and never `grabWindow(0)`; each is checked for colour variety
before it is believed. `defaults read com.chromiq.ChromIQ custom_output_path`
after the runs: **unset**. `~/Library/Preferences/ChromIQ/presets` last modified
6 Sep, untouched.

Subject: Knut's own `test` project from `01-test.zip`, with a second run cloned
from run 1 and deliberately given different stored settings (a hostile pair
where every layout value differs), plus his two pharmacist presets installed
into the sandboxed preset folder.

## D. Defects reproduced

### DEF-1 — a run switch shows the CHART's layout, not the run's own (screen)

`d1_run_switch.py`. Run 1 edited on screen to 12 strips x 18 rows on 130x180.
Switch to run 2, switch back:

```
edited : cols=12 rows=18 custom=(130,180)
back   : cols=10 rows=15 custom=(100,150)        <- the chart's recipe
store  : cols=12 rows=18 paper=130x180           <- the edit WAS saved
```

So the edit is not lost on disk; it is **overwritten on screen**. Mechanism,
traced live (`d5_causal_chain.py`), inside one `_on_target_changed`:

```
>> load_target_settings   screen seed=None paper=999x999      (the run's own)
<< load_target_settings   screen seed=None paper=999x999
>> _restore_chart_settings
<< _restore_chart_settings screen seed=1833157720 paper=100x150  (the chart's)
```

`_display_run_chart → _restore_chart_settings` (`tab_chart.py:6733, 11131`) runs
after the load and applies the sidecar's recipe, its engine on/off decision, its
printtarg fields and its whole `create_chart_settings` registry. §2's L3/L4 do
not list the sidecar as a load source for a selection change; §10 covers it
"when a chart is **restored**". The code says so itself at `:17296`: *"Whether
it should is §10's question and is not settled."*

Proof: `d1-02-run1-edited-12x18.png` vs `d1-04-run1-again.png`.

### DEF-2 — and then the chart's values are FILED as the run's own (disk)

`d2_seed_probe.py`, with no edit of any kind:

```
run1 stored seed  : None          (the user never asked for a fixed seed)
run1 sidecar seed : 1833157720
select run1  -> screen shows "Use a fixed seed" TICKED, 1833157720
select run2  -> run1's stored seed is now 1833157720, and its stored
                paper has gone from 130x180 to 100x150
```

This is Knut's *"run 1 suddenly also gets this parameter set"* — not a leak from
run 2, but the run's own chart's drawn seed being presented, and then recorded,
as a decision the user made.

Mechanism, exactly (`d5_causal_chain.py`): the shield exists and works, and is
then thrown away.

```
>> _note_what_the_chart_imposed
<< _note_what_the_chart_imposed shield=['paper','seed','margin_top',...]
>> _note_what_the_chart_imposed          <- SECOND call, same target change
<< _note_what_the_chart_imposed shield=[]
```

`_note_what_the_chart_imposed` (`:14494`) sets `self._chart_imposed = {}` and
`self._own_values_before_chart = None` **before** deciding it has nothing to
report, so a second invocation in the same target change disarms the shield.
The next write then files the sidecar's values:

```
[meta.save] run2 seed=4242 paper=130x180
   <- save_target_settings:14780 <- _save_settings_of_visible_tab:1626
   <- set_profile_run:228
```

(`d4_who_writes.py`). The writer is the Q-1 trigger, which is correct; what is
wrong is what it finds on screen. When the handler runs only once the shield
survives and the store is left alone — which is why this is intermittent and
why it looks like "some runs, sometimes".

### DEF-3 — the engine on/off tick is never shielded, so it is always filed

`d6_engine_off.py`. Run 1 stores `engine_on: true`; its chart on disk was drawn
by printtarg (a sidecar with no recipe):

```
select run1        -> screen: engine tick OFF     (the chart turned it off)
                      store : engine_on = true
run2, then run1    -> store : engine_on = FALSE   (the choice is gone)
```

`_restore_chart_settings:11288` switches the tick off for a printtarg chart, and
`_note_what_the_chart_imposed` deliberately does not shield scalar ui values
(*"A SCALAR UI VALUE IS NOT THE SIDECAR'S TO KEEP"*, `:14520`) — so `engine_on`
has no protection at all. This is Knut's sentence verbatim: *"The layout went
back to printtarg engine, and I had to re-select the Use ChromIQ layout engine
again."*

**Independently corroborated by the project's own harness.**
`scripts/drive_per_target_settings.py`, run today on the demo project:
**83 checks, 1 failed** —
`run-A profiling: meta.json create_chart_settings == its imprint / 1 differ:
['ui:engine_on'] disk=True want=False`. The specification records that driver as
"fully green (74/74)".

### DEF-4 — a run with nothing stored inherits the previous run's engine tick

`d15_engine_neutral.py`. Run 1 stores `engine_on: true`; run 2 stores nothing:

```
on run1 -> tick ON,  global use_chromiq_layout_engine = True
on run2 -> tick ON,  and run2's store now says engine_on = True
```

§4 S4 is explicit: *"factory settings, or the saved defaults if the user has any
— never the last run's."* `_apply_ui_state` gives every other bucket an
"absent means neutral" branch and gives `engine_on` none (`:15281`, guarded only
by `if "engine_on" in stored`).

### DEF-5 — deleting a run writes the deleted run's values into the survivor

`d13_delete_trace.py`. run1 stores `targen -f = 111`, run2 stores 648:

```
DELETE run 2  (from the bar, real confirmation dialog, "Delete run 2")
[meta.save] run1 targen-f=648
   <- save_target_settings:14780 <- _save_settings_of_visible_tab:1626
   <- set_profile_run:228 <- _on_delete_clicked:1976
run1 stored targen -f: before=111  after=648
```

`ui/measurement_target_bar.py:1976` moves the selection to the surviving run
after the delete; that fires the Q-1 write while the screen still holds the
deleted run's values, and the store it resolves to is the survivor's.

### DEF-6 — Close Project keeps the run description and the chart notes

`d11_close_project.py`, through the real confirmation dialog:

```
before : name='test'  description='RUN1 description...'  notes='RUN1 chart notes...'
after  : name=''      description='RUN1 description...'  notes='RUN1 chart notes...'
```

`clear_loaded_project` (`tab_chart.py`) clears the two NAME fields only, and
`_load_target_text` returns early when there is no store, leaving the text.
The app contradicts its own dialog, which says: *"What you have typed but not
yet used is not kept: the name in "Printer profile project name" and the run
description beside it."* Chart notes are not mentioned there at all.

### DEF-8 — Close Project tells the user their project was DELETED

Found by looking at the proof shot `d11-02-after-close.png`, not by a probe.
After **Close project**, the Create Chart log says:

> *"The project was deleted, so ChromIQ is back where it starts: no project is
> open. …"*

`clear_loaded_project` (`ui/tabs/tab_chart.py:14355`) appends that one fixed
sentence, and `_reset_after_project_gone(deleted=False)` calls it. Nothing was
deleted. `main_window.py:1421` is careful about precisely this — *"Telling a
user who merely CLOSED their project that it was deleted is the worst thing this
feature could do (#164)"* — and the tab's own line defeats it. The heading and
the field labels also still read "Create test chart" and "Run 1 Description"
after the close.

### DEF-7 — "New run" shows a stale copy, not the run you were on

`d12_hostile.py`. run 1 edited to `targen -f = 111`, filed correctly. Then:

```
select New run -> screen targen -f = 600
                  (the value in runs/run1/cache/new_run.json, written days ago)
```

§4a N-1 says the block is seeded **only when it is empty**, so once a project has
one it never follows the run you are actually on again. Knut's own words in §4a
are *"the currently loaded run … is copied at the same time"*. **This is a
specification question, not plainly a code fault** — N-1 is a rule the
specification added, with our reasoning, not one Knut wrote.

## E. Reported but NOT reproduced

- **"Paper size is default set to A4 after loading the 10x15 / 13x18 presets and
  selecting New run."** Driven four ways (`d7`, `d8`, `d9`, `d10`, including a
  real Generate Chart from the 100x150 preset in a fresh project): the ChromIQ
  layout paper stayed Custom 100x150 / 130x180 throughout, the run the preset
  built stored `paper=100x150` (§4b P-1 holds), and switching the engine off
  mirrored 100x150 into the printtarg "Paper size" row correctly. The only route
  to A4 I could find is a target with **nothing stored**, which opens on the
  saved defaults, else A4 (`d9-02`) — and §4 S4 says that is correct. One
  related fact worth Knut's eye: **his own 100x150 preset file stores
  `printtarg_-p: "A4"`** beside `layout_recipe.paper: "100x150"` (his 130x180
  preset stores 130x180 in both), so the preset itself carries A4 in the
  printtarg paper row.
- **A fixed seed leaking from run 2 to run 1.** The symptom is real (DEF-2) but
  the direction is not: each run acquires its OWN chart's drawn seed. I could
  not produce a case where run 2's seed reached run 1.
- **Measure and Build Profile**: my own probe (`d14`) failed to mutate those
  panels and proved nothing either way. The project's own driver exercises them
  and reports them green; only `ui:engine_on` failed. Not investigated further.

## F. Where the code contradicts a binding rule

Naming the rule only; the choice is the owner's.

| # | Rule | What the code does |
|---|---|---|
| F-a | §2.0 *"A per-target setting has exactly one writer … it must never be written by the act of looking at a different target"* | DEF-2, DEF-3, DEF-5: looking at a run, and deleting a neighbour, both write |
| F-b | §4 S4 *"factory settings, or the saved defaults — never the last run's"* | DEF-4: the engine tick comes from the run before |
| F-c | §4c D-2 *"may not overwrite a value they have chosen"* (written for instrument defaults; the same principle) | DEF-1/DEF-3: the chart overwrites the run's chosen layout and engine |
| F-d | §2 L3/L4 list what loads on a target change: *"that tab's settings for the currently selected target"* | the chart sidecar also loads. §10's sidecar precedence is written for **restore**; the code applies it to **selection**, and says at `:17296` that this is unsettled |
| F-e | §7 C — `_loading_target_settings` is a re-entrancy guard over a single call | still true, but the *shield* (`_chart_imposed`) has no such discipline and is cleared by a repeat call (DEF-2) |
| F-f | The Close Project dialog's own promise | DEF-6 |
| F-g | #164, quoted in `main_window.py:1421`: a user who merely closed a project must not be told it was deleted | DEF-8 |

## G. What the correct behaviour is, case by case (quoting the specification)

| Case | Rule | Source |
|---|---|---|
| No run selected ("New run") | no store exists; nothing is written to any run. Values are held in `cache/new_run.json` of the run they were seeded from | §4a N-1..N-4, `store_for_target` returns None |
| A single run | its own settings load on selection and on tab entry; its own store is the only writer | §2.0, §2 L1/L3 |
| A run deleted | settings follow their run; the surviving run's store must not be written with the deleted run's screen | §6 row 4 + §2.0 |
| Run type changed | as a target change: write outgoing, load incoming | §2 L4, §2.1 |
| A preset loaded | the preset's values load (§2 L6) and are recorded for that target (§3 W2); a target a preset creates opens on the preset, not on defaults | §4b P-1..P-3 |
| Tab switched mid-edit | the tab being left writes; the tab entered loads | §3 W6, §2 L1 |
| Main button with unsaved edits | Generate Chart / Build Profile / Start Measurement each write first | §3 W1/W7/W8 |
| Project closed | every tab writes for the selected target, then the app returns to its starting state | §2.1 + `close_current_project`; what the TEXT fields do is unstated in the specification — the dialog says the name and description are not kept |
| Project reopened | nothing loads immediately; every tab is stale, the visible one loads at once | §2 L2 |
| An old project migrated in place | opens on saved defaults, else factory, and records its own on first use | §4 S9 |
| A chart file opened / Restore Used Chart | the chart's recorded settings win | §2 L5 + §10 sidecar precedence |
| A target whose `meta.json` is missing or truncated | S4/S5/S8 — defaults, never an error and never the previous target's values | §4, §7 A |

## H. Implementation plan

Reuse first; nothing here needs a new store, a new file format or a new trigger.
Pieces 1-3 and 7-8 are true whatever the owner decides; pieces 4-6 and 9-10 wait
on the answers in §I.

**Phase 1 — stop the store being corrupted (no design decision needed)**

1. **Make the shield idempotent.** `_note_what_the_chart_imposed` must not clear
   `_chart_imposed` when it has nothing new to compare: take
   `was = self._own_values_before_chart` and return **before** resetting when
   `was is None`. One guard, ~3 lines, in `tab_chart.py:14494`.
   Kills DEF-2 at its root.
2. **Stop the target change being handled twice.** `changed` reaches
   `TabChart._on_target_changed` from the controller (`tab_chart.py:14318`) and
   the tab is also driven from `main_window.py:1303`; the second pass re-enters
   the whole handler. Either de-duplicate the connection or make the handler
   return early when it is already inside itself for the same target. Piece 1
   makes the damage impossible; this makes the work not happen twice.
3. **Shield the scalar ui values too** (`engine_on`, and `mode`/`stamp` on the
   same footing). The comment at `:14520` is right that a scalar has no signal
   to release it — so give it one: connect `_manual_engine_check.toggled` and
   the stamp box the same way `params_for` widgets are connected at `:14580`.
   Reuse `_release_imposed_connections`. Kills DEF-3's store half.

**Phase 2 — the screen (needs Q1/Q2 answered)**

4. If the ruling is *"the run's own settings win on a selection change"*: in
   `_on_target_changed`, call `_display_run_chart` with the sidecar restore
   **suppressed** when the target has stored settings of its own — a flag
   parameter on `_display_run_chart`/`_restore_chart_settings`, defaulting to
   today's behaviour so Restore Used Chart (`:11424`, `:17060`) and chart
   opening are untouched. A target with nothing stored still takes the chart's
   values, which is what makes an old project readable (§4 S9).
5. If the ruling is *"the chart still wins on screen"*: leave the screen alone
   and say so in the log line the user already sees ("Restored the chart's own
   layout settings…") — it currently appears on every run switch and reads like
   an action the user asked for.
6. **`engine_on` gets an absent-means-neutral branch** in `_apply_ui_state`,
   the same shape as `stamp`/`guided`/`engine_cal` already have (§4 S4).
   Kills DEF-4.

**Phase 3 — the two events that write the wrong target**

7. **Delete.** In `measurement_target_bar._on_delete_clicked`, move the
   selection without the Q-1 write: the run being left has just been deleted, so
   there is nothing to file. Cheapest correct shape is to clear the tab's
   `_settings_store`/`_written_cache` entry for the deleted run and set the new
   selection inside a "no write" guard, reusing the flag the tab already has
   (`_loading_target_settings` is the wrong one — add an explicit
   `about_to_change_target` bypass argument or a one-shot suppression flag on
   MainWindow's handler). Kills DEF-5.
8. **Close Project.** In `clear_loaded_project`, clear the description and both
   notes fields by calling the existing `_set_target_text_fields("", "")` and
   dropping `_new_run_text`. Kills DEF-6. (Q6.) In the same method, take the
   closing sentence as an argument (`deleted: bool`) so the close path does not
   say "deleted" — `_reset_after_project_gone` already knows which it is, and
   §M governs the two wordings. Kills DEF-8.

**Phase 4 — the New-run block and the presets (need Q7/Q8)**

9. Re-seed `new_run.json` from the target being left whenever the block has not
   been edited by the user since it was written — reuse the same
   "has it changed since the last write" comparison `save_target_settings`
   already keeps per target (`_written_cache`).
10. When a preset is saved with the ChromIQ engine on, write the engine's paper
    into the printtarg paper row as well, so one preset does not carry two
    different paper sizes. Reuse `_sync_manual_selection_from_panel`.

**Phase 5 — proof**

11. Extend `scripts/drive_per_target_settings.py`: after each run switch assert
    the **screen** matches the target's store, not only that the store matches
    the imprint. Today it can be green while the panel shows the chart's values.
12. New regression tests, each one a fault above:
    `_note_what_the_chart_imposed` called twice keeps the shield; a printtarg
    chart does not clear a stored `engine_on`; a run with nothing stored does
    not inherit the engine tick; deleting a run does not write the survivor;
    Close Project clears the three text fields.
13. Re-run the sanctioned driver (must be 0 failures) and the full gate
    `QT_QPA_PLATFORM=offscreen pytest --runslow -n auto`.

## I. Edge cases, each with the rule that must hold

| # | Case | Rule |
|---|---|---|
| E1 | Run selected whose chart's sidecar disagrees with its store | one of the two wins by ruling (Q1); whichever it is, the store is unchanged unless the user moves a control |
| E2 | Run with a chart but no stored settings (pre-#130) | the chart's values are shown AND recorded — that is the migration path (§4 S9) |
| E3 | Run with stored settings and no chart | the store is shown, nothing else touches it (the project driver's Phase 6 already checks this) |
| E4 | New run, block absent | nothing is written anywhere; the screen keeps what it has |
| E5 | New run, block present | Q7 decides whether it is refreshed |
| E6 | Run type → Calibration and back | the six `_CAL_VALUES` rows belong to the selected target (§10 F3); leaving restores the pre-cal snapshot, then the incoming run's own store wins |
| E7 | Verification selected | its own store, `runs/runN/verifications/meta.json` (§10 F1) |
| E8 | A run deleted while it is selected | nothing is written for it; the survivor loads its own values before anything can be filed |
| E9 | A run deleted while a DIFFERENT run is selected | the selection does not move, so nothing is written at all |
| E10 | Tab switched mid-typing | W6 writes the tab's state at that moment; typing alone never writes (test plan N2) |
| E11 | Generate Chart with unsaved edits | W1 writes first, so the chart and the store agree |
| E12 | Quit with unsaved edits | W6q writes the visible tab silently for the selected target only (§3, Q2) |
| E13 | Project closed with unsaved edits | every tab writes first (already done), then the three text fields clear (Q6) |
| E14 | Project reopened | L2: nothing loads except the visible tab |
| E15 | `meta.json` deleted or truncated | S4/S5/S8 defaults, never the previous target's values |
| E16 | A stored key that no longer exists | ignored, the rest still load (§7 A) |
| E17 | Preset creating a run | P-1: the run opens on the preset, not on defaults |
| E18 | Instrument changed after a preset | D-2: the default may not overwrite what the person chose |
| E19 | Two paper controls (engine paper vs printtarg paper) | they must never disagree in anything that is saved (Q8) |
| E20 | Auto-update preview on | loading a target's settings must arm no rebuild (§7 B, N3) |

## J. Open questions for the owner

Each is phrased for someone who does not read code, with a recommendation and
the one-line reason.

1. **When you pick a different run, should Create Chart show the settings you
   last set for that run, or the settings its printed chart was made with?**
   *Recommend: the settings you last set.* The chart is a record of what was
   printed; the settings are your intention, and today the record silently wins
   even when you never asked to restore anything.
2. **If the chart's values are still to be shown when you merely pick a run,
   may they ever be saved into that run as if you had chosen them?**
   *Recommend: never.* A run's stored settings should change only when a person
   moves a control.
3. **Should the tick "Use the ChromIQ layout engine instead of printtarg" be
   remembered per run, exactly like the rest of the layout?**
   *Recommend: yes.* It is remembered today but has no protection, so a run
   whose chart was made the other way loses the choice permanently.
4. **A run that has never had settings saved: what should that tick show —
   off, your saved default, or whatever the previous run had?**
   *Recommend: your saved default, otherwise off.* "Never the last run's" is
   already the rule for everything else on that panel.
5. **When you delete a run, should ChromIQ save anything for the run you were
   looking at?** *Recommend: no.* Today it saves the deleted run's values onto
   the run that survives.
6. **When you close a project, should the Run Description and the Run Chart
   Notes be emptied along with the project name?** *Recommend: yes.* The
   confirmation window already promises the description is not kept.
7. **"New run" copies the run you were on. Should that copy be refreshed each
   time you pick New run, or taken once and then kept until a chart is made?**
   *Recommend: refresh it whenever you have not typed anything into the New run
   yourself.* Today it can be days old, which is exactly the "values I never set"
   complaint.
8. **A preset saved while the ChromIQ layout engine is on stores two paper
   sizes: the engine's (100x150) and printtarg's (A4). Should saving keep them
   the same?** *Recommend: yes.* Two paper sizes in one preset can only ever
   confuse, and one of your 10x15 presets carries A4 today.
9. **After picking a run, the log says "Restored the chart's own layout settings
   … now show the values this chart was made with" every time. Should that
   message appear when you only picked a run, or only when you press Restore
   Used Chart?** *Recommend: only for Restore Used Chart*, if question 1 is
   answered "the settings you last set".
10. **Should "Use a fixed seed" ever tick itself because the chart recorded which
    shuffle it used?** *Recommend: no.* ChromIQ can still reproduce the sheet
    from the chart's own record without changing your choice of "draw a fresh
    one each time".
11. **Print Chart and Check & Refine are out of scope in the specification
    (§5), but Print Chart already stores per-run settings in the code. Should
    the specification be updated to include it?** *Recommend: yes, describe what
    is built.* A specification that omits shipped behaviour is the thing this
    round is trying to avoid.

## K. Rating of this plan

| Dimension | Score | Why |
|---|---|---|
| Correctness | **8/10** | Every fault has a traced mechanism and a reproduction, and each piece of the plan names the line it changes. It loses points because pieces 4/5 depend on a ruling I cannot make, and because Measure and Build Profile were not driven by me — I am relying on the project's own driver for them |
| Robustness | **8/10** | Phase 1 removes a whole class ("the shield is state that anything can clear"), and Phase 5 turns each fault into a test. The residual risk is real: the sidecar restore is entangled with Restore Used Chart, chart opening and the build path, so piece 4 must be gated rather than removed |
| Maintainability | **7/10** | It reuses the existing shield, triggers and stores and adds no new concepts, but it leaves `_on_target_changed` doing three jobs (write, load, show the chart) — the deeper cleanup, separating "what the target says" from "what is on the sheet", is not attempted here |
| Efficiency | **9/10** | Small, local edits; no new file writes, no extra disk reads, and piece 2 removes a duplicated handler pass |
