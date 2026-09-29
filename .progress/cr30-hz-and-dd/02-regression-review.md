# Regression review — `feature/nelson-photocard-presets` @ 2055fca7

Reviewer: regression round, 2026-09-08. Findings appended incrementally.
Status legend: **CONFIRMED** = reproduced. **SUSPECTED** = read only.

## G1 — CONFIRMED: the CR30 branch LEAKS THE LOOP VARIABLE `hz`, double-connecting the SpectroScan's box, and is an UnboundLocalError one dict-reorder away

`ui/dialogs/settings_dialog.py:3656`, at the END of the seven-row loop and
OUTSIDE the new `if key == "cr30": … else:` split:

```python
            self._pace_estimate[key] = est
            hz.valueChanged.connect(self._refresh_pace_estimates)   # <-- :3656
            pp.valueChanged.connect(self._refresh_pace_estimates)
            mn.valueChanged.connect(self._refresh_pace_estimates)
```

`hz` is now bound only in the `else` branch (`:3585`). On the `cr30` iteration
it is **not rebound**, so it still holds the previous row's spin box and
`:3656` connects that box a second time.

Measured on a real `SettingsDialog` (offscreen, Fusion, sandboxed .ini) —
receiver counts on `valueChanged`:

```
i1pro: 2   i1pro2: 2   i1pro3: 2   i1pro3plus: 2   colormunki: 2
spectroscan: 3      <-- the CR30 iteration reconnected it
```

`MODEL_DEFAULTS` order is `i1pro, i1pro2, i1pro3, i1pro3plus, colormunki,
spectroscan, cr30`, so today the victim is the SpectroScan.

**Effect today:** `_refresh_pace_estimates` runs twice for every SpectroScan Hz
change. It is idempotent, so nothing visible breaks. **SHOULD-FIX, not a
blocker.**

**Why it still matters:** the moment anybody moves `"cr30"` anywhere but last in
`MODEL_DEFAULTS`, `:3656` raises `UnboundLocalError` and the whole Preferences
dialog fails to build. That is not hypothetical in this file — the comment
eleven lines above (`:3641-3647`) records the identical failure happening once
already ("19 tests errored on a dialog that would not build"). A dict-ordering
change is exactly the kind of edit nobody would think to test the Preferences
dialog for.

**Fix:** move the three `connect` lines for `hz` inside the `else` branch, or
guard `if key != "cr30": hz.valueChanged.connect(...)`.

## G2 — CONFIRMED, harmless: `_pace_min["cr30"]` lost its `_refresh_pace_marginal_tip` connection

`ui/dialogs/settings_dialog.py:3697-3699` iterates `self._pace_hz` and connects
BOTH the hz box and the **min** box of each key. Dropping `cr30` from `_pace_hz`
therefore also dropped `_pace_min["cr30"].valueChanged` from that refresh.
Measured: `cr30: mn.valueChanged receivers = 1`, every other row `2`.

No user-visible consequence: `_refresh_pace_marginal_tip` (`:3729-3736`) only
ever quotes `colormunki, i1pro2, i1pro, i1pro3, i1pro3plus` and `break`s at the
first usable one, so a CR30 min change never changed that tooltip before either.
Recorded so a later reader does not mistake it for the cause of something else.

## G3 — CONFIRMED, no regression: the other six rows build, edit, save, reopen and recalculate correctly; Cancel is clean

Real `SettingsDialog`, sandboxed `.ini`, Fusion. Every editable cell on all
seven rows changed, `_save_and_close()`, reopened:

```
STORE after save:
  i1pro:      hz=123.0 min=7  pp=11
  i1pro2:     hz=124.0 min=8  pp=12
  i1pro3:     hz=125.0 min=9  pp=13
  i1pro3plus: hz=126.0 min=10 pp=14
  colormunki: hz=127.0 min=11 pp=15
  spectroscan:hz=128.0 min=12 pp=16
  cr30:       hz=100.0 (the stale pre-existing value, NOT rewritten) min=13 pp=17
round-trip MISMATCHES: none
```

* Every row's live "Min. strip reading speed" figure recalculated from the new
  numbers (`0.6 / 0.8 / 0.9 / 1.1 / 1.3 / 1.5 sec.`), so the `.get()` change at
  `:3775` did not break any row.
* `_refresh_pace_marginal_tip` still quotes an instrument with live numbers:
  *"Right now the ColorMunki limit is 87 ms per patch, so a strip is called
  close to the limit between 87 and 96 ms…"*
* **Cancel** (`reject()`) after changing every hz and min box: **nothing** in
  the store changed.
* **Restore Factory Defaults** does not raise, and the CR30 cell stays a label.
* All **9** Preferences tabs build and switch without error (General,
  Instrument Limits, Chart Layout, Scanner Limits, Paths, Reports, Measurement,
  Sounds, Beta).
* A stale stored `pace_sample_hz_cr30 = 100.0` survives untouched, exactly as
  the commit message says. Confirmed inert.

Pre-existing and NOT caused by this change: `_restore_defaults` calls
`_load_settings`, which does not re-seed the pace table (it is seeded once in
`_build_measurement_tab`), so Restore Factory Defaults leaves the pace boxes at
whatever is on screen and the next OK writes them back. Same on master.

## G4 — CONFIRMED, behaviour change (defensible, but undeclared): the CR30's last column now says "no limit" where it used to show a computed figure

The two boxes the CR30 row still offers (Patches per strip, Minimum readings per
patch) are still editable and still persisted (`pace_min_samples_cr30`,
`pace_estimate_patches_cr30`). With them set, the row's speed figure changed:

```
minimum = 13, patches per strip = 17
  master code path (hz box present, 100 Hz): '2.2 sec. @ 17 patches/strip'
  this branch     (no hz box, hz -> 0.0):    'no limit'
```

The new answer is the honest one — nothing on that row is used — so this is not
a fault. Two things about it are worth Basti's eye:

1. **"no limit" is the wrong word here.** On every other row it means *"the user
   switched the warning off"*. On the CR30 it now means *"this row is inert"*.
   The cell beside it already says `N/A` and the ⓘ says "Nothing on this row is
   used"; `tr("not applicable")` (the string `_refresh_pace_estimates` already
   has, `:3785`) would say the same thing in the row's own language.
2. **The row is half-blanked** (this is challenge item D25.4, still open). One
   cell reads N/A and is not persisted; two cells beside it are live spin boxes
   the user can type into, are written to the store on every Save, and now
   provably change nothing on screen either. Either finish the row or say why
   those two stay.

## G5 — CONFIRMED: the release gate is GREEN on this tree

```
QT_QPA_PLATFORM=offscreen pytest --runslow -n auto
========== 11980 passed, 167 skipped, 3 xfailed in 206.13s (0:03:26) ===========
[exited with code 0]
```

No `node down`, no `Fatal Python error`, no `Timeout (0:0X:XX)!` dump anywhere
in the log. Exit 0, so the `pytest_testnodedown` banner did not fire either.
Matches the count in the commit message exactly (11980 / 167 / 3).

## G6 — CONFIRMED, no regression: the per-instrument memory does what it claims, and neither the leak nor the loss survives

Real `TabChart` (offscreen, Fusion, sandboxed settings). `_dd_instr` is already
`'i1'` immediately after construction, so there is no "first call clobbers"
window.

```
CM fresh            dd chk=False               mem={}
CM +dd              dd chk=True                mem={'CM': True}
-> CR30             dd chk=False  "Hexagon…"   mem={'CM': True, 'CR30': False}   <-- the LEAK is gone
-> back to CM       dd chk=True   "Double…"                                      <-- restored
-> i1               dd chk=False  (hidden, force-unchecked)
-> back to CM again dd chk=True                                                  <-- the LOSS (D15) is gone
```

and the reverse:

```
CR30 +hex           dd chk=True   "Hexagon patches (suits the round CR30,"
-> SS               dd chk=False  "Hexagon patches (packs ~15% more per s"
-> CM               dd chk=True   "Double density"    ***
-> back to CR30     dd chk=True   "Hexagon…"
```

`*** ` note the third line: CM's OWN remembered `True` (set two steps earlier in
the same sequence) is correctly restored. It is not the CR30's value carrying
over. Verified separately: with `mem={'CM': False}`, `CR30 +hex -> CM` gives
`dd chk=False`.

`_shared_get("guided")` agrees with the widget at every step
(`CR30 -> double_density: True`, then `CM -> double_density: False`).

### Paper changes do NOT clobber the tick

`_paper_combo.currentIndexChanged` also calls `_update_dd_visibility`
(`:3969`). With `CR30 + hexagons` ticked:

```
after a paper change                    dd chk=True
after an explicit _update_dd_visibility dd chk=True
after refresh_chromiq_clip_visibility() dd chk=True
```

The `prev != instr` guard holds. Confirmed for the third caller too
(`refresh_chromiq_clip_visibility`, which MainWindow runs every time the
Settings dialog closes).

### The triple-density interlock still holds

Both boxes ticked at once is unreachable, from either direction:

```
CM +td, then dd programmatically ticked -> dd=True,  td=False   (dd wins, td cleared)
CM +dd, then td programmatically ticked -> dd=False, td=True    (td wins, dd cleared)
```

and while `td` is on, `_dd_check.isEnabled()` is `False`, so the user cannot
reach the state by hand either.

## G7 — CONFIRMED, no regression: a run's STORED tick still beats the session memory

`_apply_ui_state` with all four combinations of stored value x session memory,
both when the instrument index changes and when it does not:

```
             stored=True  memory=True  -> True   OK
             stored=True  memory=False -> True   OK
             stored=False memory=True  -> False  OK
             stored=False memory=False -> False  OK
```

The order in `_shared_get("guided")` is
`instrument, paper, pages, double_density, …`, so `_shared_set` applies the
instrument (which fires the memory restore) and *then* the stored
`double_density` on top. `meta.json` is written with `json.dump(..., indent=2)`
and no `sort_keys`, so a real record keeps that order.

## G8 — CONFIRMED, latent: the restore is ORDER-DEPENDENT on the stored dict's keys

The same call with the keys in a different order silently loses the stored
value:

```
_apply_ui_state({"guided": {"double_density": True, "instrument": "CR30", ...}})
   stored dd=True, session memory CR30=False  ->  on screen FALSE   *** wrong ***
```

No shipped record has that order today (see G7), so this is **not a live
regression**. It becomes one the moment anything rewrites a `meta.json` with
sorted keys — `sort_keys=True` puts `double_density` before `instrument`
alphabetically, and `jq`, a hand edit, or a future refactor of `_shared_get`
would all do it. `sort_keys=True` is already used in 20 places in this repo,
just not on `meta.json`.

**Cheap hardening:** in `_apply_ui_state`, apply `instrument` (and `paper`)
first explicitly rather than relying on `guided.items()` order. Or make the
memory restore in `_update_dd_visibility` skip while a UI-state load is in
flight.

## G9 — SUSPECTED, low: an OLD record with no `double_density` key now inherits another target's remembered tick

```
record = {"instrument": "CR30", "paper": "A4", "pages": 1}   (no double_density)
   session memory CR30=True  -> on screen True
   session memory CR30=False -> on screen False
```

On master the same record left whatever the widget happened to hold, so this is
a change of *which* stale value leaks, not a new leak. But `_apply_ui_state`'s
own doctrine is "ABSENT MEANS NEUTRAL, FOR EVERY BUCKET IN THIS METHOD" and this
bucket still is not, for a key that is absent inside an otherwise-present dict.
Pre-existing gap, now with a slightly different symptom.

## G10 — CONFIRMED, no regression: a ticked box still builds a hexagonal chart, an unticked one a rectangular one

Driven through the REAL UI path (`TabChart._collect_guided()` →
`ChartCreator._engine_build_kwargs()` → `workflow.layout_engine.chart.build_chart`),
same `.ti1`, everything else identical:

```
CR30 tick=True   params.double_density=True   hflag=True   layout_mode='patch_first'
CR30 tick=False  params.double_density=False  hflag=False  layout_mode='patch_first'
SS   tick=True   hflag=True     SS  tick=False  hflag=False
CM   tick=True/False -> hflag=None (printtarg path, -h gated on CM/SS as before)
i1   tick=False      -> hflag=None

BUILD tick=True :  Layout(steps_in_pass=26, passes=4,  patches_per_page=390, pages=6)
                   .ti2 contains  HEXAGON_PATCHES "True"
BUILD tick=False:  Layout(steps_in_pass=23, passes=15, patches_per_page=345, pages=6)
                   .ti2 contains  no HEXAGON line
```

390 vs 345 patches per page, and the keyword written/not written. Identical to
the challenge's D17 measurement, so the build wiring is untouched. #159's
hexagon chart is intact.

## G11 — CONFIRMED, PRE-EXISTING (not this change set): a Guided CR30 hexagon chart transfers `-h = False` into Manual

Run on BOTH trees, identical results:

```
                                 this branch          master
guided CR30 tick=True -> manual  -i='CR30' -h=False   -i='CR30' -h=False
guided CM   tick=True -> manual  -i='CM'   -h=True    -i='CM'   -h=True
guided SS   tick=True -> manual  -i='SS'   -h=True    -i='SS'   -h=True
```

`_transfer_guided_to_manual` calls
`self._set_manual_value("printtarg", "-h", bool(p.double_density))` with
`p.double_density = True`, and the Manual widget still reads back `False` for a
CR30. So a user who designs a hexagonal CR30 chart in Guided and then opens
Manual is shown, and would build, a **rectangular** chart — `_engine_build_kwargs`
takes `hflag` from `params.double_density`, which Manual now reports as False.

**Verified identical on master**, so it is NOT a regression from `2055fca7`. It
is the same family as the challenge's third defect (D20: Guided never writes its
own selection into the Manual side) and is worth its own issue.

## G12 — CONFIRMED, behaviour change, defensible: a plain Guided↔Manual tab switch can now move the density tick

`_carry_shared_settings` carries only `("instrument", "paper")` and its own
comment says that is so density does not "jump across". Setting the instrument
now fires the memory restore, so it can:

```
guided memory {CR30: True, CM: False}, guided showing CM/unticked,
then a plain switch from Manual (on CR30) back to Guided:
   this branch:  guided instr=CR30  dd=True     <-- CR30's own remembered answer
   master:       guided instr=CR30  dd=False
```

Nothing carried *from Manual*; what appeared is the user's own earlier Guided
answer for that instrument, which is the whole point of the change. But the
documented invariant at `:7208-7211` ("A plain tab switch carries ONLY
instrument + paper … without the surprise of … density … jumping across") is now
literally untrue, and the comment should say so. Not a fault; a stale comment
and a design point for Basti.

## G13 — CONFIRMED, no functional regression, but a real maintenance one: all 12 catalogues LOST their sorted key order, and 10 of 12 had their indentation rewritten

```
lang    master indent  HEAD indent  master sorted  HEAD sorted
de/es/fr/it/nl/no/pl/pt/ru/sv      1  ->  2        True  ->  False
ja / zh_CN                         2  ->  2        True  ->  False
```

* **Every existing key/value pair is byte-identical and in the same relative
  order** (verified programmatically for all 12): nothing was mistranslated by
  the rewrite, and `tests/test_i18n.py` + `test_no_new_em_dash…` +
  `test_message_catalogue` are green (158 passed), with
  `scripts/i18n_extract.py --missing <code>` reporting `0 missing of 5066` for
  all twelve.
* But the three new keys were **appended at the end** instead of sorted in, so
  the catalogues are no longer sorted. `workflow/i18n_roundtrip.py:433` writes
  them with `sort_keys=True`, so the next roundtrip through that tool will
  re-sort all 5,069 lines and produce another ~60,000-line diff.
* And the indent change turned a 3-string edit into **+51,467 / −50,680 lines**.
  A human cannot review that diff, and neither can the next reviewer of the next
  translation change.

**Nothing in the suite catches this** — there is no test on catalogue indent or
key order, which is why a green gate did not notice.

**SHOULD-FIX before merge:** rewrite the 12 catalogues with the master
convention (`json.dump(..., ensure_ascii=False, indent=1, sort_keys=True)`, plus
`indent=2` for `ja`/`zh_CN` if that was deliberate) so the commit's translation
diff is 36 lines, not 100,000.

## G14 — CONFIRMED, no regression: the three new strings are complete, valid, placeholder-clean and em-dash-clean in all 12 languages

* All 12 files parse; each has exactly **5067** keys; **+3 / −1 / ~0** per
  catalogue (the removed key is the reworded tab note, correctly evicted).
* **No new translation carries an em dash its English source lacks** — checked
  directly over all 36 new values, and `tests/test_no_new_em_dash_in_user_facing_text.py`
  is green. The reworded English note also drops the em dash it used to carry
  ("readings you want per patch — the reading speed" → "…per patch, and the
  reading speed"), per the rule.

### Meaning and register spot-check

**German — correct register (Du-form) and accurate.** "während du ziehst",
"weil du die Taste selbst drückst", "Setze diese Rate", "erhöhe das Minimum".
Two small language nits, neither wrong in meaning:

* `"leicht misszuverstehen"` — `missverstehen` is an **inseparable** verb, so
  the zu-infinitive is `zu missverstehen`, not `misszuverstehen`.
* `"nimmt … genau eine Messung"` — `eine Messung nehmen` is not idiomatic;
  `nimmt … eine Messung vor` or `macht … eine Messung` is.

**French — accurate and in the same tu-form register as the rest of the
catalogue** ("pendant que tu fais glisser", "Règle cette cadence", "augmente le
minimum"). "cadence" for rate, "plage" for patch, "bande" for strip, all
consistent with the existing catalogue's vocabulary. Nothing mistranslated.

**Japanese — accurate, in the same です/ます register the catalogue uses.**
「該当なし」matches the catalogue's own `N/A`. The nuance of "measured on real
hardware" is kept as 「（実機で測定）」and the "describes nothing you will see"
point survives intact.

### A genuinely interesting one: `tr("N/A")` is NOT "N/A" in three languages

```
de -> '—'        no -> '–'        sv -> '–'
es/fr/it/pt -> 'N/D'   nl -> 'n.v.t.'   pl -> 'Nie dot.'
ru -> 'Н/Д'      ja -> '該当なし'   zh_CN -> '不适用'
```

So the German CR30 rate cell renders a bare **em dash**, and the Norwegian and
Swedish ones a bare en dash. The commit message's claim that `tr("N/A")` "reads
right in every language" is true only in the weak sense that it matches the
Patches cell beside it (which uses the same string as its `specialValueText`) —
in German the row shows two adjacent bare dashes.

The translators handled this correctly: de / no / sv all avoid naming "N/A" in
the new help text and say "shows no value" instead
(`zeigt deshalb keinen Wert an` / `viser derfor ingen verdi` /
`visar därför inget värde`), while every language whose `N/A` is a readable
token quotes that token. That is careful work and no fix is needed. Flagged only
because a German CR30 owner sees `—` where the English sees `N/A`, and Basti may
want a word there instead.

## G15 — CONFIRMED ON SCREEN: `scripts/drive_cr30_hz_and_density_tick.py` passes, 0 problems

Real window, `CHROMIQ_SETTINGS_FILE` sandboxed, locale `de_DE`:

```
  i1pro '100 Hz' i1pro2 '200 Hz' i1pro3 '400 Hz' i1pro3plus '400 Hz'
  colormunki '50 Hz' spectroscan '250 Hz'    all decimals=0, min=10.0
  cr30 <no rate box>
  Save ran (canary overwritten): True
  CR30 rate left alone by Save : True
  CR30 hexagons ON -> ColorMunki: ticked=False, label 'Double density'
  CM double density ON -> i1Pro -> back on CM: ticked=True
  back on CR30: ticked=True
  problems: 0
```

Screenshot `02-per-instrument-table.png` read directly: the English table is
correct, the CR30's rate cell is a faint `N/A` where the other six have a spin
box, and no other row moved. No decimal comma anywhere.

## G16 — CONFIRMED ON SCREEN: with the UI in GERMAN the CR30 rate cell renders a bare em dash `—`, and the row's ⓘ contradicts itself about what it shows

Real window, `set_language("de")`, screenshot read directly
(`~/Desktop/cr30-review-de/de-01-per-instrument-table.png`):

| Messgerät | Messungen pro Sekunde | Messfelder pro Streifen | Mindestmessungen pro Feld | Min. Streifentempo |
|---|---|---|---|---|
| SpectroScan (Motortisch) | `250 Hz` | `—` | `Aus` | keine Grenze |
| **CR30 (Feld für Feld)** | **`—`** | `—` | `Aus` | keine Grenze |

`tr("N/A")` is `"—"` in German (and `"–"` in Norwegian and Swedish), so the row
shows two adjacent bare dashes. It is legible and it matches the cell beside it,
so it works — but the commit's "reads right in every language" is true only in
that weak sense, and Basti may want a word rather than a dash there.

**The self-contradiction is the real finding.** The German CR30 ⓘ now contains
both, in the same tooltip:

> …und die Streifenlänge zeigt **N/A**, weil ein CR30-Chart keine Streifen hat.
> *(paragraph 1, untouched, pre-existing)*
>
> …es gibt also keine Rate, die angewendet werden könnte, und die Zelle **zeigt
> keinen Wert an**. *(the new block)*

The first sends the reader to look for the letters "N/A" in a cell that shows
`—`; the second describes the same cell correctly. The new translation is the
right one; the old sentence is the stale one, and it is stale on master too.
**SHOULD-FIX** (one German string), and the same sentence should be checked in
`no` and `sv`.

The German ⓘ is otherwise complete and correct in Du-form, and the English one
no longer contains "from its specification", "judged like any other" or the
shared "HOW THE THREE NUMBERS…" head — all three verified absent.

## G17 — NICE-TO-HAVE: the English CR30 ⓘ now says the same thing three times

Read end to end (challenge item D25.3, not picked up by the build):

* ¶1 "…there is no reading speed to get wrong and nothing worth warning about."
* ¶2 "This whole row is inert for the CR30… a CR30 measurement never produces one."
* new ¶ "…there is no rate to apply and the cell shows N/A."
* new ¶ "Nothing on this row is used when you measure with a CR30."

Four statements of one fact in one tooltip. Nothing is wrong; it is just longer
than it needs to be, and ¶2 could now go.

## G18 — **CONFIRMED REGRESSION, THE HEADLINE ONE.** The session memory can overwrite a run's STORED tick, and re-arm the rig-dependent ColorMunki option the commit set out to disarm

`_update_dd_visibility` restores the remembered tick on **every** instrument
change, including the many the APP makes for itself. `_apply_ui_state` applies
the stored `double_density` *before* several of those, so the memory gets the
last word.

### Reproduced, offscreen, on BOTH trees, opposite results

```
  the user has ticked "Double density" on a ColorMunki this session
  a target is then loaded whose stored Guided row is CR30, double_density = False
  the run's own chart is then displayed, which seeds the MANUAL instrument from
  its .ti2 (tab_chart.py:11414) and the mirror pushes it into Guided

  this branch:  after the load  instr=CR30 dd=False
                after -i=CM     instr=CM   dd=TRUE      <-- the stored False is gone
                _shared_get("guided").double_density = True

  master     :  after the load  instr=CR30 dd=False
                after -i=CM     instr=CM   dd=False     <-- correct
```

`_shared_get("guided")` is what `_collect_ui_state` files, so **the wrong value
is written back into the run's `meta.json` on the next save.** It is persistent
corruption of the record, not a display glitch.

And what it re-arms is the worst of the three options: **"Double density" on a
ColorMunki, which needs the physical rig** — its own tooltip says the
instrument "will misread" without it. That is precisely the fault
`2055fca7` was written to fix, arriving through a different door.

### It also fires ON SCREEN every single time, through a second path

Same scenario driven in the real window (MainWindow, Fusion, sandboxed
settings), HEAD vs master, two runs each:

```
--- this branch (ON SCREEN) ---
  before: guided=CM manual -i=CM dd=True   mem={'CR30': True, 'CM': True}
  AFTER : guided=CM manual -i=CM dd=True    *** INSTRUMENT LOST ***  *** DD WRONG ***
  before: guided=CM manual -i=CM dd=False  mem={'CR30': True, 'CM': False}
  AFTER : guided=CM manual -i=CM dd=False   *** INSTRUMENT LOST ***  dd ok
  problems: 3
--- master (ON SCREEN) ---
  AFTER : guided=CM manual -i=CM dd=False   *** INSTRUMENT LOST ***  dd ok
  AFTER : guided=CM manual -i=CM dd=False   *** INSTRUMENT LOST ***  dd ok
  problems: 2
```

The traced write order (spy on `_dd_check.setChecked`, real window):

```
setChecked(True)  <- _apply_ui_state:15128 | _shared_set:7062 | _update_dd_visibility:12762   # memory for CR30
setChecked(False) <- _apply_ui_state:15128 | _shared_set:7077                                 # the STORED value
setChecked(False) <- _mirror:7138          | _shared_set:7062 | _update_dd_visibility:12762   # memory again, AFTER
```

Master has no third write at all.

### When it does NOT fire

Only when the instrument does not actually change after the load
(`prev == instr` in the guard). Measured:

```
session CR30=False | stored CR30 dd=True  | chart -i=CR30  ->  OK
session CR30=True  | stored CR30 dd=False | chart -i=CR30  ->  OK
session CM  =True  | stored CR30 dd=False | chart -i=CM    ->  *** STORED VALUE LOST ***
```

So the trigger is: **the app writes a different instrument after the stored
Guided row has been applied.** `_on_target_changed`'s own docstring says that
happens by design — *"`_display_run_chart` -> `_restore_chart_settings` runs a
few lines below and lays the chart sidecar's own recipe (instrument, paper …)
over what was just loaded here"* — and on screen the
`_link_instrument_controls` mirror does it as well, every time.

### Why it is a spec violation too

`docs/design/per_target_settings.md` §4c **D-4** (CONFIRMED, Basti 2026-09-02):
*"The app's own starting point (factory settings, `default_recipe`, saved
defaults) is not an answer."* A session memory filed under an instrument the
user last visited is exactly such a starting point, and here it overwrites a
value the target itself stored — which is **D-2** as well.

### The fix

The memory must only be read and written for a **user-driven** instrument
change. Three ways, in order of cheapness:

1. Restore from `self._instr_combo.activated` (user-driven only) instead of
   inside `_update_dd_visibility`, which is also called by
   `currentIndexChanged` (fires for every programmatic write),
   `_paper_combo.currentIndexChanged`, `refresh_chromiq_clip_visibility` and
   `_on_guided_td_toggled`.
2. Or suppress the restore while any load is in flight — the flags already
   exist: `self._loading_target_settings`, `self._syncing_instrument`,
   `self._mode_transfer_active`. **`_syncing_instrument` alone closes the
   on-screen mirror path**, but NOT the `_restore_chart_settings` /
   `.ti2`-seeding path, which is neither.
3. Or record the tick from `_dd_check.clicked` (user only) rather than
   `toggled` (fires for programmatic writes too) — this also stops the memory
   being poisoned in the first place, and is worth doing regardless: today a
   programmatic `setChecked` from a project load rewrites the memory.

**BLOCKER for this change set.** Everything else in it is sound; this one path
turns a fix into a persistent record corruption that is worse than the bug.

## G19 — CONFIRMED, PRE-EXISTING, ON SCREEN ONLY: `_apply_ui_state` does not restore the Guided instrument in the real window

Found while chasing G18, and worth its own issue because it is the reason G18 is
100% reproducible on screen.

```
  stored guided row: instrument = CR30
  ON SCREEN, both trees:   AFTER: guided=CM  manual -i=CM      *** INSTRUMENT LOST ***
  OFFSCREEN,  both trees:  AFTER: guided=CR30 manual -i=CR30   instrument ok
```

`_link_instrument_controls._mirror` (`:7128-7143`) is guarded by
`self._syncing_instrument`, which is a plain boolean set and cleared
synchronously. Offscreen the manual widget's write lands inside that window and
the echo is swallowed. In a real window it does not, so the manual→guided mirror
fires afterwards and pulls Guided back to the instrument Manual still holds.

**This is exactly the class of bug that only an on-screen run finds** — the
offscreen suite cannot see it, and the shipped driver does not exercise
`_apply_ui_state`. Not caused by `2055fca7`; reproduced identically on master.
Reported per CLAUDE.md's "report, do not fix" rule for spec-touching behaviour
(`per_target_settings.md` §2 L1 is the rule it breaks: "Put the selected
target's stored settings on screen").

# D — THE THINGS THE CHALLENGE ASKED FOR AND THE BUILD DID NOT DO

## G20 — CONFIRMED: the stale `pace_sample_hz_cr30` is inert, but NOT for the reason the commit gives

The commit says the stale key is safe because *"a CR30's minimum is Off, and
`_pace_config` throws the rate away on that branch"*. The minimum is **not
fixed at Off** — it is still a live, editable, persisted spin box in the same
row. Measured: setting it and saving stores `pace_min_samples_cr30 = 21`.

`ui/tabs/tab_measure.py:4887-4917` then does:

```python
hz_default, min_default = defaults_for(key)          # cr30 -> (3.18, None)
hz = float(self._settings.get(f"pace_sample_hz_{lookup}", hz_default) or hz_default)
...
if min_samples <= 0:
    return PaceConfig(min_samples=0, sample_hz=0.0, ...)   # the "thrown away" branch
return PaceConfig(min_samples=min_samples, sample_hz=hz, ...)
```

With `pace_min_samples_cr30 = 21` the short-circuit does **not** fire, and the
returned `PaceConfig` carries `sample_hz = 100.0` (the stale key) or `3.18` (the
new default) — a 31x difference in `target_seconds`.

**It is still harmless**, because `PaceTracker` is driven only by
`strip_measured` (`tab_measure.py:1080`) and `Cr30SpotManager` never emits one.
So the conclusion is right and the argument is wrong. The commit message should
say "nothing subscribes", not "min_samples is Off" — the second is a user
setting and the first is structural. **NICE-TO-HAVE** (a comment), but the kind
of reasoning that stops being true when somebody adds a strip signal to the CR30
backend.

## G21 — CONFIRMED, PRE-EXISTING, UNCHANGED: `left_border` still leaks into a CR30 build's recorded layout from an invisible checkbox (D16 / D24)

```
i1 + left_border ticked           lb ticked=True
-> CR30                           lb ticked=True, hidden=True   (hidden, NOT unchecked)
_shared_get("guided").left_border = True
ChartParams.disable_left_border   = True
LayoutOptions.suppress_left_clip  = True
```

Unchanged by this commit, and still the odd one out among the four sibling
controls (`_td_check` and `_nsl_check` ARE force-unchecked on hide, `_lb_check`
is not). Now more visible as an inconsistency, because `_dd_check` has just been
given a fourth behaviour (remember and restore) that the other three do not
share. Whatever Basti rules for the tick has to be ruled for all four.

## G22 — CONFIRMED, PRE-EXISTING, UNCHANGED: a Guided CR30 build's `engine_recipe` still contradicts its own `guided` bucket

```
guided.instrument        = CR30
guided.double_density    = True
engine_recipe.instrument = i1      hflag = False
```

Exactly the challenge's D20, deliberately out of scope. One `meta.json` records
a hexagonal CR30 chart in one bucket and a rectangular i1Pro chart in the other.
Worth carrying into its own issue rather than losing with this branch.

# F — MUTATIONS

Every mutation below was applied to the working tree, **proved to have landed by
grepping the file after the edit**, run with all `__pycache__` cleared, and then
reverted from a byte-for-byte backup (`git diff --stat` empty afterwards).

| # | mutation | result |
|---|---|---|
| M1 | `_update_dd_visibility`: drop `self._remember_dd_for(prev)` | **SURVIVED** — 27 passed |
| M2 | `_update_dd_visibility`: drop the `instr != prev` guard on the restore | **SURVIVED** — 124 passed |
| M3 | put the CR30 back into `_pace_hz` as a hidden spin box | **CAUGHT** — 2 failed |
| M4 | add `i1`/`p3` to `_DD_FAMILIES` so the memory applies to strip readers | **SURVIVED** — 124 passed |
| M5b | `_shared_set("guided","double_density")` ignores the stored value and reads `_dd_memory` instead | **SURVIVED THE FULL RELEASE GATE — 11980 passed, 167 skipped, 3 xfailed, exit 0** |

## G23 — CONFIRMED: M5b survives the whole gate, which is why G18 shipped

The single most important mutation. With
`_shared_set("guided", "double_density", value)` rewritten to

```python
self._dd_check.setChecked(bool(self._dd_memory.get(
    self._instr_combo.currentData() or "", False)))
```

a run's stored `double_density` is **never applied at all** — the session memory
decides, always. Proved to land:

```
session CM=True    | stored CR30 dd=False | -> STORED VALUE LOST
session CR30=False | stored CR30 dd=True  | -> STORED VALUE LOST
session CR30=True  | stored CR30 dd=False | -> STORED VALUE LOST
```

and then:

```
QT_QPA_PLATFORM=offscreen pytest --runslow -n auto
========== 11980 passed, 167 skipped, 3 xfailed in 208.57s (0:03:28) ===========
```

**Nothing in 11,980 tests asserts that a target's stored density tick is the one
that reaches the screen.** That is the hole G18 came through, and it must be
closed by the same change that fixes G18:

* a target whose stored `guided.double_density` is `False` still shows `False`
  after an instrument write that follows the load (the G18 case);
* a target whose stored value is `True` still shows `True` after the same;
* and the assertion should be on `_shared_get("guided")["double_density"]`, not
  only on the widget, because that is what gets written back.

## G24 — CONFIRMED: M1 proves `_remember_dd_for(prev)` in `_update_dd_visibility` is dead code

Deleting it changes nothing, and the reason is structural, not accidental:
`_dd_check.toggled` is connected to `_on_guided_dd_toggled`, which calls
`_remember_dd_for` on **every** state change, so `_dd_memory[instr]` is always
already in step with the widget. `setChecked` emits on every real change, so
there is no path where the exit-time filing adds anything.

M2 and M4 are **equivalent mutants** for the same reason (verified
behaviourally, not just by a green suite): the `!= prev` guard is not what
protects a paper change, and the i1/p3 force-uncheck still runs after the
restore. Reported so nobody wastes an hour on a mutant that cannot be killed.

**And that same structural fact is the root of G18.** "The memory" is not the
user's answer — it is *the last value the widget held for that instrument,
however it got there, including values the app itself wrote during a project
load.* Fixing G18 means making the memory record user intent (`clicked`, not
`toggled`) and restoring it only on a user-driven instrument change
(`activated`, not `currentIndexChanged`); the dead line should go at the same
time.

---

# PRIORITISED

## REGRESSIONS (caused by `2055fca7`)

| # | what | where |
|---|---|---|
| 1 | **A run's stored density tick can be overwritten by the session memory, and written back into `meta.json`.** Re-arms rig-dependent ColorMunki "Double density" on a chart the user never asked to be dense. Reproduced offscreen and on screen, HEAD vs master, opposite results. | **G18** |
| 2 | The CR30 branch **leaks the loop variable `hz`**, double-connecting the SpectroScan's box; an `UnboundLocalError` that kills the whole Preferences dialog is one `MODEL_DEFAULTS` reorder away. | **G1** |
| 3 | All 12 catalogues **lost their sorted key order**, 10 of 12 had indentation rewritten: a 3-string change became a **101,000-line diff**, and the next `i18n_roundtrip` run will churn them all again. | **G13** |

## BLOCKERS (must not ship as-is)

* **G18.** Everything else in this branch is sound; this one path turns the fix
  into persistent record corruption that is worse than the bug being fixed, and
  it breaks `per_target_settings.md` §4c **D-2** and **D-4** — the same CONFIRMED
  rules the commit message cites as its own justification.
* **G23.** The fix must land with a test. A mutation that makes the stored value
  *never* apply passes all 11,980 tests today.

## SHOULD-FIX (before merge, cheap)

* **G1** — move the three `connect` calls inside the `else` branch.
* **G13** — rewrite the catalogues with the master convention so the diff is
  36 lines.
* **G16** — the German CR30 ⓘ says the cell shows "N/A" (¶1, pre-existing) and
  "shows no value" (new ¶) about the same cell, which renders `—` in German.
  One string. Check `no` and `sv` too.
* **G8** — make `_apply_ui_state` apply `instrument` first explicitly instead of
  relying on `guided.items()` order; today a `sort_keys=True` rewrite of any
  `meta.json` silently loses the tick.
* **G4.1** — the CR30's speed cell says `"no limit"`, which on every other row
  means "the user turned the warning off". `tr("not applicable")` already exists.

## NICE-TO-HAVE

* **G4.2 / D25.4** — the CR30 row is half-blanked: one N/A cell that is not
  persisted, two live spin boxes that are, and that now provably change nothing
  on screen either.
* **G17** — the English CR30 ⓘ states the same fact four times; ¶2 could go.
* **G20** — the commit's reason for the stale key being inert ("the minimum is
  Off") is a user setting, not a structural fact. The structural reason
  ("nothing subscribes to `strip_measured` for a CR30") is the right one.
* **G12** — `_carry_shared_settings`'s comment now says something untrue.
* **G24** — `_remember_dd_for(prev)` in `_update_dd_visibility` is dead code.

## SEPARATE ISSUES (pre-existing, reproduced on master, NOT this branch's fault)

* **G19** — `_apply_ui_state` does not restore the Guided instrument in a real
  window (the `_link_instrument_controls` mirror races). Offscreen it works, so
  the suite cannot see it. This is what makes G18 fire every time on screen.
* **G11** — a Guided CR30 hexagon chart transfers `-h = False` into Manual, so
  building from Manual afterwards produces a rectangular chart.
* **G21** — `left_border` still leaks into a CR30 build's `LayoutOptions` from a
  hidden, never-unchecked box (challenge D16 / D24).
* **G22** — a Guided CR30 build's `engine_recipe` still records `instrument: i1`
  and `hflag: False` beside `guided: {CR30, double_density: true}` (D20).

## CONFIRMED WORKING — no regression found

* Every one of the six remaining pace rows builds, edits, saves, reopens and
  recalculates its live figure (**G3**). Cancel touches nothing. Restore Factory
  Defaults does not raise. All 9 Preferences tabs open. The marginal-percent
  tooltip still quotes a live instrument.
* The stale `pace_sample_hz_cr30` is left alone by Save and is inert (**G3**,
  **G20**).
* The density memory does what it claims: the leak and the loss are both gone,
  a paper change does not clobber the tick, the triple-density interlock still
  makes "both ticked" unreachable from either direction, `_shared_get` always
  agrees with the widget (**G6**).
* A ticked box still builds a hexagonal chart (`HEXAGON_PATCHES "True"`, 390
  patches/page) and an unticked one a rectangular chart (345), through the real
  UI path (**G10**). #159 is intact.
* All 12 catalogues are complete, valid, placeholder-clean and em-dash-clean;
  the German, French and Japanese say what the English says, in the right
  register (**G14**).
* **The release gate is green on this tree, twice**: `11980 passed, 167 skipped,
  3 xfailed`, exit 0, no worker crash, no timeout dump (**G5**, and again after
  every mutation was reverted).

# WHAT I COULD NOT VERIFY

* **A real two-project target switch on screen.** G18 was reproduced through
  `_apply_ui_state` (the exact method `_on_target_changed` calls) both offscreen
  and on screen, and through the `.ti2` instrument seeding at
  `tab_chart.py:11414`, but I did not build two real projects on disk and click
  between them in the target bar. The mechanism is unambiguous and reproduces
  100% of the time in both harnesses; the end-to-end click-through is the one
  step short.
* **Why the `_link_instrument_controls` mirror races on screen and not
  offscreen** (G19). Reproduced reliably on both trees; the cause is not
  isolated.
* **Whether Basti wants a dash or a word in the German CR30 rate cell** (G16),
  and whether he accepts the German ⓘ's two descriptions of the same cell.
* **Anything about the CR30 over Bluetooth.** Unchanged from the challenge's own
  "could not verify" list: no BLE rate has ever been measured.
* **The other nine languages' meaning.** Only `de`, `fr` and `ja` were read for
  sense; the other nine were checked mechanically (complete, valid,
  placeholders, em dashes, `N/A` token consistency) and by their handling of the
  `N/A` token, which was correct in all twelve.
* **The two earlier commits on the branch** (`c48706d1`, `08f96ef8`,
  `5a0cd98c`, `b2316b53`, `1dec7035` — the photo-card presets). The brief named
  `2055fca7` plus "the two before it"; the tab_chart diff for those is the
  preset/paper-code work, which I read but did not regression-test beyond the
  green gate.

---

# ADDENDUM — the earlier commits on the branch (photo-card presets)

## G25 — CONFIRMED, no regression: every prebuilt preset still resolves to the same printtarg `-p` code, and the two new ones are complete

`_prebuilt_paper_code` and `_prebuilt_paper` were rewritten (a `<W>x<H>` folder
is now read as millimetres, unless it is a named `PAPER_LABELS` code meaning
inches). Every shipped preset checked against master's mapping:

```
key                                folder    -p code   label                      assets
__chromiq_abw1110_builtin__        a4        A4        A4                         .ti1 .ti2 tif=2
__chromiq_tc918eg_a4_builtin__     a4        A4        A4                         .ti1 .ti2 tif=2
__chromiq_tc918eg_letter_builtin__ letter    Letter    US Letter                  .ti1 .ti2 tif=2
__chromiq_tc300_builtin__          a4        A4        A4                         .ti1 .ti2 tif=1
__chromiq_abw702_builtin__         a4        A4        A4                         .ti1 .ti2 tif=2
__chromiq_tc924_cm_a3_builtin__    a3        A3        A3                         .ti1 .ti2 tif=1
__chromiq_tc918eg_cm_a3_builtin__  a3plus    329x483   A3+                        .ti1 .ti2 tif=1
__chromiq_ext1944_a4_builtin__     a4        A4        A4                         .ti1 .ti2 tif=3
__chromiq_ext1944_letter_builtin__ letter    Letter    US Letter                  .ti1 .ti2 tif=3
__chromiq_photocard600_builtin__   100x150   100x150   10 × 15 cm (100 × 150 mm)  .ti1 .ti2 tif=4
__chromiq_photocard648_builtin__   130x180   130x180   13 × 18 cm (130 × 180 mm)  .ti1 .ti2 tif=3
```

All nine pre-existing rows are **identical to master**. The two new rows resolve
to a valid printtarg custom size, carry `.ti1` + `.ti2`, and their TIFF page
counts match the page counts in their own labels (4 pages / 3 pages). The
inches trap the commit message names (`4x6`, `11x17` are `PAPER_LABELS` codes
meaning inches, not 4 x 6 mm) is correctly handled: `_prebuilt_paper_is_mm`
returns False for both.

## G26 — NICE-TO-HAVE: the new `PREBUILT_PRESET_NOTES` tooltip is not wrapped in `tr()`

`ui/tabs/tab_chart.py`, `PREBUILT_PRESET_NOTES` and `_prebuilt_tooltip`: six
lines of new user-facing tooltip text, none of it in `tr()`. CLAUDE.md's rule is
"Wrap every new user-facing literal in `tr()`".

It is **consistent with its surroundings** — `_prebuilt_tooltip`'s whole shared
body is untranslated on master too (and its first line, "Built-in chart — cannot
be deleted.", carries an em dash that the em-dash test cannot see because it is
not a `tr()` literal). So this is a pre-existing untranslated block that has just
grown, not a new inconsistency. Worth one line in the issue rather than a fix
here; translating the block means translating all of it.
