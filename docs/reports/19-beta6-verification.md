# 19 — Beta 6 verification (adversarial)

**STATUS: complete** (2026-09-01)

Verifier: independent review of commit `1bbc2211` before tagging 4.1.5-beta.6.
Evidence: `~/Desktop/beta6-proof/4-verification/` (see its `INDEX.md`).

Sections are appended as work completes. Nothing here is rewritten wholesale.

### 0. Method / safety

Everything behavioural below was driven **in the real application on screen** —
real `MainWindow`, real theme (`apply_appearance(app, w, "light")`), real
`LayoutOptionsPanel` — against scratch copies of the `Demo-Full-RGB` demo
project taken from the session demo cache into `/tmp/beta6verify/w1…w5`.
Drivers live in `/tmp/beta6verify/drv/`, logs and artefacts in
`~/Desktop/beta6-proof/4-verification/`.

`CHROMIQ_SETTINGS_FILE=/tmp/beta6-verify.ini` is exported **before any import**
in `drv/base.py`, *and* `core.settings.QSettings` is replaced in the same file,
so the real preferences cannot be reached. `custom_output_path` points at
`/tmp/beta6verify/wN`. `~/ChromIQ`, `~/ChromIQ/CR30-Test` and
`~/Desktop/i1Profiler` were never opened or written. Verified by VALUE at the
end — see §11.

A/B comparisons use a detached `git worktree` of `1bbc2211^` at
`/tmp/beta6verify/pre`; the working tree is never mutated except for this
report.

---

## 1. K4 — the shield (per-field UI state)

### 1.1 not-a-bug — **the headline K4 case really is fixed**

The challenge's own scenario (`~/Desktop/beta6-challenge/d5.py`), re-driven at
HEAD on a fresh tree (`drv/v1_shield.py`, section A):

```
 1 unticked strip indicators. screen: strip=False
 2 went to run2.  run1 disk: strip=False
 3 back on run1.  screen: strip=True   disk: strip=False
                  shield: {'engine_recipe': ['show_strip_indicators']}
 4 nudged top margin.  shield: {'engine_recipe': ['show_strip_indicators']}
 5 left the tab.  disk: strip=False, mtop=7.0, printtarg-i='CM', rec.instr='CM'
 >>> strip==False? True   instrument agrees? True   margin kept? 7.0
```

Step 4 is where the previous round lost it; the shield now survives the panel
edit **and** the margin edit still lands. Several edits in a row (B), the other
recipe fields (C), a run with no chart and a brand-new run (H — shield empty),
and a build in flight all behave. The connections are released and re-armed on
every target change (K: 2 → 2, not 4).

### 1.2 **BLOCKER — a REGRESSION this commit introduced: the verification target now loads in the wrong module**

Non-dict UI keys (`mode`, `stamp`, `engine_on`) are still shielded **whole**,
but the release rule changed. Before, `panel.changed` cleared the entire `ui`
bucket, so an ordinary panel edit rescued them. Now
`_release_ui_values_that_moved` (`ui/tabs/tab_chart.py:13636-13664`) pops a
non-dict key **only when its current value differs from what the chart
imposed** — and for `mode` on a verification target it never does, because the
run-type rules are what set it.

Driven with identical steps on identical fresh trees, HEAD vs `1bbc2211^`
(`drv/vmode.py`, `drv/vmode2.py`):

```
                                              HEAD          1bbc2211^
 select verification run1, screen mode         gamut          gamut
 shield                                        {'mode':WHOLE} {'mode':WHOLE}
 nudge the top margin (an ordinary edit)
 shield after the nudge                        {'mode':WHOLE} {}          <-- released
 leave the tab, re-select the target
 SCREEN mode                                   manual         gamut
```

and on disk, `runs/run1/verifications/meta.json`:

```
  HEAD        "mode": "manual"
  1bbc2211^   "mode": "gamut"
```

`gamut` is the module **the app itself selected** for that target. The shield
writes `manual` over it, and because `manual` is a *legal* module for a
verification run nothing overrules it on the next load — so
`_apply_ui_state`'s own docstring (`:14211-14214`, *"the run-type module rules
… still run afterwards and win over an illegal stored mode"*) does not save it.
The user selects Verification, sees the From-profile-gamut module, comes back
later and finds Manual.

This is challenge §1.5, which the commit did not set out to fix — but the
per-field release made it **strictly worse**: the one gesture that used to
rescue it no longer does. Evidence: `4-verification/mode-regression-HEAD.log`,
`mode-regression-PRE.log`.

**Severity: BLOCKER for beta 6** — it is a regression, on the verification
run-type Knut is testing, reachable by selecting a target and nudging anything.

### 1.3 should-fix — **§1.2 of the challenge is NOT fixed: one file still holds two answers for the instrument**

Reproduced on a fresh tree (`drv/v3_shield.py`, section P). Visit run 1, then
run 2, then run 3, doing nothing else:

```
  run1: printtarg-i='CM'  rec.instr='CM'   engine_on=True   agree
  run2: printtarg-i='i1'  rec.instr='CM'   engine_on=True   TWO ANSWERS
  run3: printtarg-i='i1'  rec.instr='CM'   engine_on=True   TWO ANSWERS
```

`_restore_chart_settings` puts the sidecar's printtarg fields back on every
chart kind, but leaves the engine recipe holding the **previous target's**
instrument when the sidecar carries no `layout_recipe`. Nothing in this commit
touched that. The challenge listed it as blocker item 2, *"falls out with"* the
K4 fix. It did not fall out. Consequence: switch the layout engine off on run 2
and the instrument silently becomes an i1Pro.

### 1.4 should-fix — **the shield makes the screen lie, and a build follows the screen**

Still true at HEAD, now per-field (`drv/v3_shield.py`, section Q):

```
  1 stored strip: False                    (the user's own choice)
  2 back on run1: SCREEN strip = True      STORE strip = False
  3 the recipe a BUILD would use right now: show_strip_indicators = True
```

So the store is right and the sheet would be printed wrong. And a user who
looks at the ticked box and *decides* they want it ticked cannot say so —
leaving the tab stores `False` (measured, section M step 3). The escape is the
detour the challenge named: untick, retick (measured to work, M step 4).

Challenge §1.4, unchanged. Now spread over **seven** recipe fields and **four**
parameters at once on an ordinary run switch (measured shield, `v2.log` section
M), so the screen and the store can differ in eleven places simultaneously.

### 1.5 not-a-bug — the things that hold

* `_chart_imposed` does **not** leak between targets: the outgoing target is
  written before the note is re-taken.
* Restore Used Chart drops the shield **both** immediately after a target
  change (I) and after an intervening edit (J): shield `{}`, screen and store
  agree, `_forget_what_the_chart_imposed` is called at all four production
  sites (`:10373`, `:10769`, `:15866`, and the sidecar wrapper).
* `_release_imposed_connections` swallows `TypeError`/`RuntimeError`; no
  dead-widget hazard was found.
* An edit made in **Preferences** does not reach the tab's panel at all (the
  dialog holds its own `LayoutOptionsPanel` instance — measured,
  `is it the tab's own? False`), so it cannot release or corrupt the shield.
## 2. F2 — the margins (`_as_area_first`)

Measured on **rendered pages**, not on the function. 720 crossed combinations —
5 instruments × 3 papers × 2 layout modes × clip on/off × hexagons on/off ×
"use instrument margins" on/off × 3 patch counts — each rendered twice, with row
indicators on and off, at HEAD and at `1bbc2211^`
(`/tmp/beta6verify/f2probe2.py`, `4-verification/f2-analysis.txt`).

### 2.1 not-a-bug — **F2 is genuinely fixed, and the fix is precisely contained**

```
HEAD: AREA-FIRST combos where the rows-ON right edge differs from rows-OFF:   0 of 360
PRE : AREA-FIRST combos where the rows-ON right edge differs from rows-OFF: 312 of 360
```

Worst pre-fix shortfall in the sweep: **−7.451 mm** (ColorMunki), matching
report 16. At HEAD every area-first right edge is identical with row
indicators on and off, on every instrument, paper, clip setting, hexagon
setting and patch count.

**Nothing else moved.** Field-by-field diff of both renders across all 720
combos:

```
combos whose RENDER changed, by mode:  {('area_first', 'rows on'): 360}
                                        patch_first : 0
                                        rows off    : 0
```

Patch-first still reserves the band, and it takes it from the **left**
(measured left shift when rows go on: `+7.451 mm` ×252, `+7.62 mm` ×108 — the
i1Pro3+ band), while area-first now shifts nothing (`0.0 mm` ×360). That is
exactly the intended asymmetry.

No patch block crosses a margin at HEAD (0 of 720 at a 0.2 mm tolerance;
1 px at 150 dpi is 0.169 mm). No ink at the paper edge in this sweep.

### 2.2 not-a-bug — the capacity the UI shows equals what is rendered

60 combos, capacity read through `geometry.patches_per_sheet` (the call the
Create Chart tab, the Settings dialog and the relayout dialog all make),
then that exact number rendered:

```
HEAD: estimate != patches_per_page or != patches drawn on sheet 1:  0 of 60
PRE : same check:                                                   0 of 60
```

The estimate and the render stay in lock-step, before and after.

### 2.3 not-a-bug, but **the "121 built-in presets are byte-identical" check is vacuous**

I re-ran it properly: all **150** built-in default recipes (5 instruments ×
15 engine papers × 2 layout modes) rendered at HEAD and at `1bbc2211^` —
**0 differing**, page bytes and page counts identical
(`/tmp/beta6verify/presets_hash.py`).

But the reason is not that the fix is safe for them: **every one of the 150
default recipes has `show_row_indicators = False`**, and the change only
touches rows-on. The check cannot fail. It is true, and it proves nothing;
report it as "no built-in preset turns row indicators on" rather than as
evidence the geometry is unchanged.

### 2.4 nice-to-have — **existing area-first charts with row indicators change capacity, in both directions**

The same 15 default recipes with row indicators switched on
(`4-verification/capacity-analysis.txt`):

```
   CM|A4       48 ->   63        CR30|A3    759 ->  736
   CM|A3      108 ->  130        CR30|Letter 336 ->  320
   CR30|A4    330 ->  368        i1|Letter   638 ->  616
   i1|A4      651 ->  682        p3|A3       352 ->  336
   i1|A3     1408 -> 1485        p3|A4       140 ->  165
```

Up on six, **down on four**. A user who has an area-first recipe with row
indicators on and a patch count near the old ceiling (i1Pro/Letter 638) will
find the same recipe now needs a second sheet. That is the correct geometry
arriving, not a bug — but it is a visible change to existing recipes and
belongs in the changelog, which currently says only that the edges now agree.

## 3. F1 — the stamp (`_engine_moved_by_app`)

### 3.1 not-a-bug — **F1 is fixed, and the guard is what fixes it (proven by removing it)**

The challenge's traced path is `_restore_chart_settings → _on_manual_engine_toggled`.
Driven with that function called directly, on a run whose chart sidecar carries
no `layout` block (so the restore really flips the engine off — the branch at
`ui/tabs/tab_chart.py:10592-10594`), with the user's stamp deliberately OFF
(`drv/v7_stamp.py`, `4-verification/F1-stamp-guard-mutation.log`):

```
AA  HEAD                     engine True -> False, stamp stayed False   (kept)
AB  guard removed            engine True -> False, stamp False -> True
        stamp -> True  <- _restore_chart_settings:10594 / _on_manual_engine_toggled:4755
```

AB is the F1 fault reproduced verbatim, and the only difference between the two
runs is `_engine_moved_by_app`. The guard is doing the work, and the mutation
demonstrably lands.

### 3.2 not-a-bug — a real click still gets the default, both ways

`drv/v5_stamp.py` section W, with the checkbox's own `toggled` instrumented:

```
  click 1: engine True -> False, stamp -> True   (expected not-on: True)  OK
  click 2: engine False -> True, stamp -> False  (expected not-on: False) OK
```

### 3.3 not-a-bug — the counter cannot leak

`_set_engine_checked` (`:4682-4695`) wraps the move in `try/finally`. Driven
with `setChecked` made to raise (`drv/v6_stamp.py` section Z):

```
  raised: RuntimeError boom
  counter after the raise: 0
```

### 3.4 nice-to-have — **the commit message's claim is not literally true**

> *"Every programmatic move now goes through `_set_engine_checked`"*

It does not. `_refresh_manual_command_preview` moves the checkbox itself at
`ui/tabs/tab_chart.py:4926-4932`:

```python
chk.blockSignals(True)
chk.setChecked(want)
chk.blockSignals(False)
```

That is a sixth programmatic move, outside the new helper. It is **harmless for
F1** — with signals blocked, `_on_manual_engine_toggled` never runs, so no
default can be spent — but the claim should say "every move that fires the
toggle", and a future edit that drops the `blockSignals` pair would reopen F1
with nothing to catch it. The construction-time `setChecked` at `:4159` is safe
for a different reason: `toggled` is not connected until `:4161`.

Full audit of every production write to that widget: `:4159` (construction, no
connection yet), `:4926` (signals blocked), and `_set_engine_checked` at `:8290`,
`:8428`, `:10521`, `:10594`, `:14264`. Nothing outside `ui/tabs/tab_chart.py`
touches it.

### 3.5 not-a-bug — the acceptance driver is 83/83

`scripts/drive_per_target_settings.py`, sandboxed, on screen:
`83 checks, 0 failed` (`4-verification/acceptance-83-of-83.log`), including
Phase 3 *"run-A verification: verifications/meta.json == its imprint (own
store)"*. Note that this driver does **not** exercise §1.2 above: it writes an
imprint into every parameter, which releases the shield on every field, so the
`ui:mode` case cannot arise inside it.

## 4. F5 — the tile window

Driven with the real `TabMeasure._offer_cr30_tile_learning` and a reader stubbed
only at the radio (`drv/f5.py`, `4-verification/F5-four-endings.log`). The
instrument was not touched.

### 4.1 not-a-bug — **all four endings now produce exactly one correct note**

```
DECLINED                    1 note   "…running on ChromIQ's built-in value…"
FAILED (4.1 dE apart)       1 note   "…could not learn… Readings taken: 2. the two readings were 4.1 dE apart"
RAISED (link went away)     1 note   "…could not learn… Readings taken: 0. BLE link went away"
SUCCEEDED                   1 note   "…has learned this instrument's white-tile value…"
```

The FAILED and RAISED branches were unreachable before this commit; they now
run and carry the instrument's own reason. Never two notes, never the wrong one.
The thread is released in all four cases (`thread still referenced: False`), and
no unhandled exception reached any slot across five scenarios — including a
decline followed by a late `worker.done → dlg.accept()`, which I specifically
went looking for as a double-`finished` / dead-widget hazard and could not
provoke.

### 4.2 should-fix — **the RAISED note reports "Readings taken: 0" when a reading was taken**

`_Learn.run` (`ui/tabs/tab_measure.py:7916-7924`) only merges the learner's dict
on a clean return:

```python
result.update(reader.learn_tile(...))
except Exception as exc:
    result["error"] = str(exc) or type(exc).__name__
```

so on an exception `result["presses"]` never exists and the note falls back to
`0`. Measured: my stub emitted `on_press(1)` and then raised; the log said
**"Readings taken: 0. BLE link went away"** — one reading had in fact landed,
and the live line in the window had already counted it.

This is the one number in the diagnostic F5 was written to provide
(report 16: *"thirty-four seconds of a feature failing left no trace at all"*),
and it is wrong exactly on the failure mode that motivated it — the link going
away mid-learn. The worker already sees every press through `pressed`; counting
them there is a two-line fix.

### 4.3 nice-to-have — decline-then-succeed still tells the user the opposite

Challenge §6.2, unchanged and now unambiguous. Declining at +0.12 s while the
learner succeeds at +0.40 s prints the **declined** note, while
`measure_bridge.learn_tile`'s success path has already written
`cr30_tile_signatures`. The store and the log disagree.

## 5. The dialogs (name prompt, project picker)

Driven with the real stylesheet (`apply_appearance(app, None, "auto")` path,
`WinButtonLayoutStyle`, the app's fonts and event filters), against a real
parent window at 500×400, 700×500, 1400×900 and 2400×1400, with every optional
row of the name box exercised. Screenshots and logs in `4-verification/`.

### 5.1 not-a-bug — the clipping and the corner-placement are both fixed

```
                         PRE (1bbc2211^)             HEAD
 name box, natural       560x363, off-centre -382    665x363, off-centre (2,2)
 name box, illegal name  CLIPPED 1 label             clipped 0
 picker,  natural        560x341, overlap 1          605x408, overlap 0
```

The detector is proven to work: it caught the challenge's exact fault at PRE
(`CUT: 'Before ChromIQ can make your chart it needs a name for the p' w=520
h=96 needs 112`) and reports 0 at HEAD. Centring is exact — `(2,2)` is the
frame/geometry inset, not a placement error. With the parent hidden, and with
no parent at all, both dialogs fall back to the screen centre correctly.
The picker is right with 1, 4, 6, and 50 projects, with 70-character project
names (no horizontal scrollbar; the row is elided as intended), and with no
body text at all. With **0** projects it shows no window and returns `None`,
and `tab_profile.py:4291` then falls through to the name box — correct, not a
dead end.

### 5.2 should-fix — **the project picker's buttons overlap by 38 px at its own declared minimum width**

`ui/dialogs/project_picker.py:137` sets `dlg.setMinimumWidth(560)`, and
`pin_min_height(..., min_width=560)` pins only the *height*. The button row
needs 606 px:

```
  at 605 px (natural)        Choose this project   20..213
                             Make a new project…  221..468
                             Cancel               475..585      no overlap
  at 560 px (the minimum)    Cancel               430..540
                             >>> OVERLAP QPushButton x QPushButton = 38x42
```

Screenshot `4-verification/project-picker-560.png`: **"MAKE A NEW PROJECT
INSTE…" is cut off and Cancel is drawn on top of it.** A user can reach this by
dragging the window narrower; it is the state the dialog itself declares legal.
Pre-existing (PRE shows it at the *natural* size, so HEAD is an improvement),
but the fix moved the problem rather than removing it.

### 5.3 should-fix — **the name box now OVERLAPS at 560 px instead of clipping**

Same cause, same width, different symptom. `pin_min_height` measures each
wrapping label's `heightForWidth` at the **natural** width (625 px of content)
and never revisits it, so at the dialog's own 560 px minimum (520 px of
content) the body label needs more than the 112 px it was pinned to:

```
  QLabel     20, 51  520x112   'Before ChromIQ can make your chart it …'
  QLineEdit  20,159  492x 36   'bad/name'
  >>> OVERLAP QLabel x QLineEdit = 492x4 at 20,159
```

Screenshot `4-verification/name-prompt-560.png`: the last line of the body,
*"change it later, and ChromIQ will offer to rename the folder for you"*, is
**sliced by the top of the name field**. This is challenge §13.1, answered at
one width. The fix is a `resizeEvent` that re-pins, or giving `pin_min_height`
the scroll-area mode the challenge recommended.

## 6. The import button

### 6.1 **BLOCKER — the button Basti reported is now UNTRANSLATED in all twelve languages**

`"File it here"` was translated everywhere. Measured at `1bbc2211^`:

```
  de  'Hier ablegen'      fr  'Classer ici'
  ja  'ここに保存'          ru  'Сохранить здесь'
```

The three keys that replace it are present in all twelve catalogues and hold
**the English source string** in every one:

```
  "File it in a new run"        English x12
  "File it in {run}"            English x12
  "File it in the selected run" English x12
```

So a German user who could read that button in beta 5 cannot in beta 6.
Details and the full audit in §8.

### 6.2 not-a-bug — nothing clips, in any language

`fit_button_width` re-fits on every picker move (`ui/tabs/tab_profile.py:4398`)
and is called once at construction (`:4401`). Driven with the real style, real
fonts and the real fitting helpers, over 12 languages × 4 run numbers ×
3 label shapes = 144 buttons: **0 clipped** (`drv/button.py`). The longest
translated label is Italian *"File it in Esecuzione 12"* at 160 px; the widest
English is 187 px. (This measurement is of the English strings for two of the
three labels, because those strings are untranslated — see 6.1.)

### 6.3 not-a-bug — the picker's absence on a calibration target

`_build_run_picker` returns `(None, [peek.run_id])` for a calibration
(`ui/tabs/tab_chart.py:8974-8975`) and `_file_into_project` guards the whole
window with `if picker is not None`, so there is no button to name a run.
Pre-existing and deliberate. With **0** projects the picker shows nothing and
returns `None`, and `tab_profile.py:4291` falls through to the name box —
correct.

## 7. The em-dash removal

All 32 new source strings were read in full
(`4-verification/emdash-review.txt`). Placeholders and HTML tags are balanced
everywhere (mechanical check: 0 unbalanced `<b>`/`<i>`/`<code>`, 0 placeholder
changes). Meaning is preserved in most, but **not all**, and several are now
poor English.

### 7.1 should-fix — `name_prompt.py:94` has a **space before the full stop**

```python
tr("A folder name cannot contain / \\ : * ? \" < > | . Please "
   "use letters, numbers, spaces or hyphens instead.")
```

The old text was `… | — please use …`; the dash was replaced and the space in
front of it was not. On screen it reads **"| . Please"**. Visible in
`4-verification/name-prompt-560.png`, in red, in the one message a user only
ever sees when they have already made a mistake.

### 7.2 should-fix — **one bullet in a list of bullets now uses a different separator**

`ui/ti2_loader.py:641-642`, five lines apart, in the same `informativeText`:

```python
parts.append(f"&nbsp;&nbsp;•&nbsp; <b>{label}</b> — {desc}")          # every choice
parts.append(tr("&nbsp;&nbsp;•&nbsp; <b>Cancel</b>, nothing is opened, …"))  # Cancel
```

Every other bullet in that window still carries the em dash. The Cancel bullet
alone was rewritten, so the list is visibly inconsistent on screen. Either
change `:641` too or leave `:642` alone.

### 7.3 should-fix — **the button names in the two loaders now read as verbs in a list**

```
  <i>Continue</i>, convert and use the measurement in this folder as-is, nothing
  will be copied or moved.
  <i>Use as base for a new profile</i>, copy the files to a new subfolder …
```

`Continue` and `Use as base for a new profile` are **button names**. With the
dash they were labels followed by an explanation; with a comma they read as the
first item of a list of imperatives — *"Continue, convert and use …"* — which is
a different instruction from the one intended. `ui/txt_loader.py:167`, `:175`,
`ui/ti2_loader.py:1155`, `:1163`.

### 7.4 should-fix — **eight comma splices**, where the dash was doing real work

Each of these joins two independent clauses with a bare comma:

| where | text |
|---|---|
| `ti2_loader.py:265` | *"Take the magnetic cap off first**,** with the cap … near the instrument, the CR30 does not measure at all."* |
| `ti2_loader.py:268` | *"moves the highlight to the next patch**,** you do not need to touch the keyboard."* |
| `ti2_loader.py:321` | *"Hold it still until the reading is taken**,** there is no sliding in this mode."* |
| `ti2_loader.py:325` | *"Take the magnetic cap off the measuring end first**,** with the cap on, the CR30 reads its own white tile…"* |
| `ti2_loader.py:332` | *"moves on to the next patch**,** there is nothing to press on screen"* |
| `ti2_loader.py:335` | *"without touching the instrument at all**,** that keeps it perfectly still"* |
| `ti2_loader.py:343` | *"Keep it still until the reading is taken**,** there is no sliding in this mode."* |
| `ti2_loader.py:890` | *"Profile run / Run type are not used**,** the copy reproduces the project exactly."* |

`ti2_loader.py:265` and `:325` are the worst: *"Take the cap off first, with the
cap on, the CR30 reads its own white tile"* is not merely a splice, it now reads
as an instruction immediately contradicted. A semicolon, a full stop, or
"because" would each fix them.

### 7.5 not-a-bug — no meaning was lost elsewhere

The remaining rewrites (`:730`, `:746`, `:755`, `:765`, `measurement_import.py:83`,
`name_prompt.py:70`, the two log lines) read correctly as appositives, and the
sense is unchanged. One deliberate double space (the CR30 bullet's leading
indentation) is pre-existing.

### 7.6 nice-to-have — the dashes are gone from the English only

The carried-across German (and the other eleven) still contain the em dashes,
e.g. `<i>Weiter</i> — die Messung in diesem Ordner … — nichts wird kopiert`.
That follows from the deliberate decision to carry translations across, and is
fine — but "the em dashes in the import path are gone" is true in one language
of thirteen. Also, `ui/ti2_loader.py` still has 55 lines carrying an em dash and
`ui/txt_loader.py` 15, so the import path is not dash-free even in English.

## 8. i18n

Full audit: `4-verification/i18n-audit.txt`. 32 keys added, 30 removed
(4714 → 4716), and all twelve catalogues hold identical key sets — 0 extra,
0 missing, 0 placeholder mismatches. Those parts are clean.

### 8.1 **BLOCKER — 13 of the 32 new keys are English in all twelve languages**

The commit says *"19 of 32 new keys kept their German"*. The other **13** were
not translated at all, in any language:

```
  File it in a new run                              <- the button Basti reported
  File it in {run}                                  <- ditto
  File it in the selected run                       <- ditto
  A folder name cannot contain / \ : * ? " < > | . Please use letters…
  Choose the project this measurement belongs to. ChromIQ opens it and…   (picker body)
  Where should this measurement go?\n\nType the name of a project…        (name-box body)
  Prints a label down the left-hand side of the chart…                    (row-indicator help)
  ⚠ The left margin is tight for the row indicators, so…
  ⚠ There is no room for the row indicators down the left, so…
  •  CR30 (ChnSpec) — a small hand-held colorimeter…
  <b>Take the magnetic cap off first</b>, with the cap…
  <b>Your instrument needs to be calibrated before measuring.</b>…
  Rectangular or hexagonal patches…
```

plus one more English in eleven of twelve. **CLAUDE.md is explicit**: *"After
string changes run `python scripts/i18n_extract.py --missing de` and add the
German translations."* Eleven of these are new English echoes in **German**,
the language the project keeps current.

The user-visible consequence is 6.1: three windows in the import path — the
accept button, the picker body and the name-box body — that were readable in
German in beta 5 and are English in beta 6.

### 8.2 **should-fix — a translation WAS carried onto a key whose meaning changed, four times**

The K8 rename exists because the labels are *not always numbers*. The German
carried across says numbers:

| new English | kept German | means |
|---|---|---|
| `Row indicators` | `Zeilennummern` | "row numbers" |
| `Show row indicators` | `Zeilennummern anzeigen` | "show row numbers" |
| `⚠ The row indicators will not appear on this chart…` | `⚠ Die Zeilennummern erscheinen…` | "the row numbers" |
| the margin-inspector help (`…print row indicators down the left…`) | `…Zeilennummern…` | "row numbers" |

So in German the checkbox still promises numbers over a band that prints
A, B, C — **the exact fault Knut reported (K8), unfixed in twelve languages**,
and now the English and the German disagree about what the control does. The
carry-across rule is right for a pure em-dash rewording; it is wrong here,
because "indicators" *is* the change.

The same applies to the two `row numbers → row indicators` warnings that were
NOT carried (they went to English instead) — so of the six sibling messages the
commit renamed, German shows the old wrong word for four and English for two.

### 8.3 should-fix — **the deliberate budget rise understates what grew, and French is now at zero headroom**

`tests/test_help_cards_untranslated_are_tracked.py` was raised 117 → 122 with
the note *"Five substantial strings are new."* Measured:

```
  lang    PRE  HEAD  budget  headroom
  de       26    33      35     +2
  fr      117   122     122     +0        <- exactly on the ceiling
  es/it/ja/nl/no/pl/pt/sv  116  121  122   +1
  ru/zh_CN                 115  120  122   +2
```

Eleven new English echoes in German, not five. That file's own rule says:
*"If a rise ever cannot be explained in one sentence, something was added that
nobody meant to add."* French at +0 means the next string change of any kind
turns the gate red.

### 8.4 should-fix — **two of the untranslated keys are invisible to the only test that counts them**

`_english_echoes` skips any key shorter than 25 characters
(`tests/test_help_cards_untranslated_are_tracked.py:136`). Both

```
  "File it in a new run"   (20 chars)
  "File it in {run}"       (16 chars)
```

are under it. They are English in twelve languages and **no test in the repo
would go red for it** — `test_i18n.py` only checks that the key exists, and the
budget test cannot see them. That is the same blind spot the budget file's own
docstring was written about, one size class lower down.

## 9. The vacuous-test question (mutation proofs)
## 10. Free-form end-to-end findings

Driven through the real Build Profile import path on a demo project
(`drv/import_e2e.py`, screenshots `import-e2e-*.png`).

### 10.1 not-a-bug — the import chain works and the new button is right

```
  WINDOW  "Where should the measurement go?"
    picker: A new run… | Run 1 | Run 2 | Run 3
    button 'File it in a new run'   w=177  needs=135
    after picking 'Run 3': 'File it in Run 3'  w=142  needs=100
```

Filing a measurement that does not match the run's chart is refused
(*"This measurement does not belong to that chart"*), and filing into a run
that already holds one opens a second window — *"Run 1 already holds a
measurement, and ChromIQ does not write over one… it can make a new run beside
it"* — which answers the challenge's §11.7 worry about a beginner over-filing.
Nothing was overwritten in either run (`import-into-a-used-run.log`).

### 10.2 should-fix — **the STRIP-indicator help now carries the misnomer the ROW one was just cured of**

`ui/dialogs/layout_options_panel.py:443-449`:

> *"The small **letter** label printed above each strip (**A, B, C…**)"*

But the Strip pattern control four rows down explains that a pattern of
`1-999` or `0-9` *"labels … in plain numbers"*
(`layout_options_panel.py:1179-1198`). So the strip checkbox promises letters
over a band the user can set to numbers — **exactly the fault K8 reported about
the row checkbox**, now the only one of the pair left saying it. The row help
was extended to say *"they follow whatever the chart's own patch pattern says"*;
the strip help was not. This is also K11's other half.

Knut reported K8 by name; he will find its mirror image in the control
immediately above it.

### 10.3 nice-to-have — the working tree is not clean

`docs/design/row_label_geometry.md` (5,723 bytes, mtime 01:47, i.e. **after**
commit `1bbc2211`) is untracked. It is a `STATUS: DRAFT` design specification.
Per CLAUDE.md, `docs/design/` is binding once committed and
`tests/test_design_specs_are_binding.py` polices the confirmation lines — an
uncommitted draft sitting in that directory is invisible to that test. It is not
part of the commit under review and I did not touch it; whoever wrote it should
either commit it or move it out before the tag.

## 11. Verdict

### 11.1 Safety of this run

* **Settings.** `CHROMIQ_SETTINGS_FILE=/tmp/beta6-verify.ini` exported before
  any import in `drv/base.py`, *and* `core.settings.QSettings` replaced there
  too. All **12** of my sessions are identifiable in
  `~/Library/Logs/ChromIQ/chromiq.log` by their own
  `Settings SANDBOXED to /tmp/beta6-verify.ini` warning. Checked afterwards
  **by value**, against the values taken before the run:

  ```
  $ defaults read com.chromiq.ChromIQ custom_output_path   ->  (empty, as before)
  $ defaults read com.chromiq.ChromIQ strip_indicator_size_mm -> 0  (as before)
  ```

* **Working folders.** Every driver pointed `custom_output_path` at
  `/tmp/beta6verify/wN`, scratch copies taken from the session demo cache.
  Nothing under `~/ChromIQ` was opened; `~/ChromIQ/CR30-Test` still has its
  28 Aug mtime. `~/Desktop/i1Profiler` untouched (mtime still 29 May 01:10).

* **⚠ Somebody else is driving the real app in parallel.** The log records an
  **unsandboxed** session at `01:41:56` reading
  `/Users/Basti/Library/Preferences/com.chromiq.ChromIQ.plist`, and
  `docs/design/row_label_geometry.md` appeared in the working tree at `01:47`.
  Neither is mine. Do not read `~/ChromIQ` or the working tree as evidence of
  anything I did.

* **Mutations** were applied only to `/tmp/beta6verify/mutrepo`, an rsync copy,
  and every file was restored and byte-compared against the working tree
  afterwards (`same` for all six). The `1bbc2211^` worktree at
  `/tmp/beta6verify/pre` is read-only. **The only file this run adds to the
  repository is this report.** The instrument was not touched; the CR30 work
  used a reader stubbed at the radio.

### 11.2 Is it safe to tag beta 6?

**No — one new regression, and three of the four headline fixes are unguarded.**

The batch is a real improvement: K4's headline case, F2, F1 and F5 are all
genuinely fixed and I proved each one by measurement, and F2's and F5's new
tests are real guards that catch their own faults. But this commit introduced
a fault of its own on the run type Knut is testing, and the two fixes it calls
its blockers can be reverted line-for-line without a single test noticing.

### 11.3 The shortest list that would make it safe

1. **§1.2 — the verification target's module.** The per-field release never
   releases a non-dict key, so `ui:mode` is written back as `manual` over the
   `gamut` the app itself chose, and the target reopens in the wrong module.
   Proven A/B on disk against `1bbc2211^`. Either release UI keys the layout
   panel does not own from their own controls, or keep them out of the shield.
   **This is the blocker.**
2. **§9.2 — a guard for K4 and for F1.** With the exact original faults put
   back the whole everyday tier is green: 8348 passed, 0 failed. A test that
   unticks an indicator, switches run, returns, **nudges a panel control**,
   leaves the tab and asserts the store closes K4; a test that restores a
   printtarg chart with the engine on and the stamp off closes F1 (I drove
   exactly that in `drv/v7_stamp.py`, and the mutation is proven to land).
   Also make `test_an_explicit_restore_is_not_shielded` go through the
   production path instead of calling the helper by hand (§9.3).
3. **§8.2 — the K8 rename in German.** `Row indicators` kept
   `Zeilennummern`. In German the checkbox still promises numbers over a band
   that prints A, B, C — the fault Knut reported, in the language he reads.
   Four keys.
4. **§6.1 / §8.1 — the import button.** `File it here` was translated in all
   twelve; its three replacements are English in all twelve, and two of them
   are below the budget test's 25-character floor so nothing will ever notice.
   Translate them, at least in German.
5. **§7.1 — `name_prompt.py:94`.** `"| . Please"` — a space before the full
   stop, in red, in the message a user only sees after a mistake.

Everything else below is should-fix or lower and does not have to hold the tag.

### 11.4 Every finding, by severity

| # | severity | finding | where |
|---|---|---|---|
| §1.2 | **BLOCKER** | a verification target's Create Chart module is stored as `manual` and reopens in Manual; regression vs `1bbc2211^` | `ui/tabs/tab_chart.py:13636-13664` |
| §9.2 | **BLOCKER (belief)** | the everyday tier is green with K4, F1 and the Restore un-shielding all put back | `tests/test_the_chart_sidecar_never_files_into_the_target.py` |
| §8.1/§6.1 | should-fix | 13 of 32 new keys English in all twelve; the import button regressed from translated to English | `data/i18n/*.json` |
| §8.2 | should-fix | a translation carried onto four keys whose meaning changed — German still says "row numbers" | `data/i18n/*.json` |
| §1.3 | should-fix | one `meta.json` still holds two answers for the instrument (`printtarg-i='i1'`, `rec.instr='CM'`) | `ui/tabs/tab_chart.py:10592` |
| §1.4 | should-fix | the shield makes the screen disagree with the store in up to 11 places, and a build follows the screen | `ui/tabs/tab_chart.py:13694-13710` |
| §5.2 | should-fix | the picker's buttons overlap by 38×42 px at its own `setMinimumWidth(560)` | `ui/dialogs/project_picker.py:137` |
| §5.3 | should-fix | the name box now OVERLAPS by 4 px at 560 px instead of clipping | `ui/dialogs/name_prompt.py:314` |
| §4.2 | should-fix | a failed learn reports "Readings taken: 0" when a reading landed | `ui/tabs/tab_measure.py:7916-7924` |
| §7.1 | should-fix | `"| . Please"` — space before the full stop | `ui/dialogs/name_prompt.py:94` |
| §7.2 | should-fix | one bullet in a list of bullets uses a comma while its siblings use an em dash | `ui/ti2_loader.py:641-642` |
| §7.3 | should-fix | `<i>Continue</i>, convert and use…` reads the button name as a verb | `ui/txt_loader.py:167,175`, `ui/ti2_loader.py:1155,1163` |
| §7.4 | should-fix | eight comma splices, two of which now read as self-contradicting instructions | `ui/ti2_loader.py:265,268,321,325,332,335,343,890` |
| §8.3 | should-fix | the budget rise says "five substantial strings"; German gained eleven, and French is at +0 headroom | `tests/test_help_cards_untranslated_are_tracked.py:113` |
| §8.4 | should-fix | two untranslated keys are below the budget test's 25-char floor and invisible to it | same file, `:136` |
| §10.2 | should-fix | the strip-indicator help now carries the misnomer the row one was cured of ("letter label (A, B, C…)") | `ui/dialogs/layout_options_panel.py:445` |
| §2.4 | nice-to-have | area-first capacities move in both directions with row indicators on (i1/Letter 638 → 616) — belongs in the changelog | — |
| §3.4 | nice-to-have | "every programmatic move goes through `_set_engine_checked`" is not literally true | `ui/tabs/tab_chart.py:4926-4932` |
| §4.3 | nice-to-have | decline-then-succeed still prints the declined note | `ui/tabs/tab_measure.py:7991` |
| §10.3 | nice-to-have | an uncommitted `docs/design/` draft is sitting in the tree | `docs/design/row_label_geometry.md` |
| §2.3 | not-a-bug | the "presets are byte-identical" check is true but vacuous — no built-in preset enables row indicators | — |
| §1.5, §2.1, §2.2, §3.1-3.3, §3.5, §4.1, §5.1, §6.2, §6.3, §7.5, §10.1 | not-a-bug | measured and correct | — |

### 11.5 K1–K12 and F1/F2/F5, one line each

| # | verdict |
|---|---|
| K1 | open-by-design (untouched, as agreed) |
| K2 | open-by-design |
| K3 | **fixed-but-unguarded** — the headline gesture and the panel-edit gesture both hold; no test would catch either coming back |
| K4 | **fixed-but-unguarded**, and it brought a regression: §1.2 |
| K5 | fixed-and-guarded (re-measured: 0 overlapping pairs in both panel shapes) |
| K6 | open-by-design |
| K7 | open-by-design |
| K8 | **fixed-but-unguarded in English; still-broken in German** (§8.2), and its mirror image is now in the strip help (§10.2) |
| K9 | open-by-design |
| K10 | open-by-design — four of five clauses unchanged; a DRAFT specification appeared in the tree tonight (§10.3) |
| K11 | **half fixed, unguarded** — the row help now names the patch pattern, the strip help still does not |
| K12 | fixed-and-guarded |
| F1 | **fixed-but-unguarded** — proven fixed by removing the guard (§3.1), proven unguarded by the full tier (§9.2) |
| F2 | **fixed-and-guarded** — 0 of 360 area-first combos off, was 312 of 360; mutation caught |
| F5 | **fixed-and-guarded** — four endings, four correct notes; mutation caught. One residual: §4.2 |

### 11.6 The structural observation, one round later

The challenge report ended on *"assert the artefact, not the function"*, and
this commit did exactly that for F2 — a rendered page, an ink edge, a real
guard. It did not do it for K4, F1 or the Restore un-shielding, and those three
are the ones that can be reverted with the whole suite green. The pattern that
produced beta 5's broken fixes is still in the tree; it has just moved to
different items.

**STATUS: verified — do not tag as it stands.**
