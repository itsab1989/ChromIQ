# Adversarial challenge — the four "guided restore" defects

Round 3, 2026-09-08. HEAD = 478c7396 (`feature/182-compliance-sets`).
Every finding below was RUN, not reasoned. Probes live in the session
scratchpad and are named per finding.

---

## E1 — CONFIRMED. The premise is wrong: D-A is NOT a screen-only defect.
### It reproduces OFFSCREEN. The variable is `manual_engine_recipe` in settings.

The brief says D-A "DOES NOT REPRODUCE OFFSCREEN AT ALL", and 00-reproduced.md
says "every offscreen probe of the same sequence came back clean". Both are
misattributions. I crossed the two variables (probe `probe_da2.py`, four runs,
identical sequence, the owner's real settings copied into a sandbox each time):

| run | platform | `win.show()` | `manual_engine_recipe` in settings | guided after restore |
|---|---|---|---|---|
| A | cocoa | yes | present (instrument `CM`) | **`CM` — BROKEN** |
| B | cocoa | yes | **removed** | `CR30` — OK |
| C | **offscreen** | yes | present (instrument `CM`) | **`CM` — BROKEN** |
| D | cocoa | **no** | present (instrument `CM`) | **`CM` — BROKEN** |

The screen makes no difference at all. What decides it is whether the
`manual_engine_recipe` key exists — that is the blob written by **"Save as
Defaults"** in the layout panel. The owner's real preferences have one; a fresh
test sandbox does not, which is the *only* reason the suite and the earlier
offscreen probes were blind.

**Consequence for the plan.** The on-screen constraint is still right as a
general rule, but for these four it is not what unblocks the work: a plain
`QT_QPA_PLATFORM=offscreen` test that *first sets* `manual_engine_recipe` (or,
better, stores a disagreeing `engine_recipe` — see E3) reproduces D-A exactly.
That means **D-A is regression-testable in the normal suite**, and it must be.

---

## E2 — CONFIRMED. D-A's mechanism, proven by stack capture. It is the mirror,
### but it is not a "race": it is a deterministic LAST-WRITER-WINS ordering.

`_link_instrument_controls` is not racing anything. There is no timer, no
`showEvent`, no deferred layout. It is one synchronous call chain, captured by
wrapping `_instr_combo.setCurrentIndex` (probe `probe_da.py`):

```
1) ui/tabs/tab_chart.py:15186  _apply_ui_state -> _shared_set("guided","instrument")
   ui/tabs/tab_chart.py:7065   _instr_combo.setCurrentIndex(4)   # CR30 — correct
       -> currentIndexChanged -> _mirror("guided") -> manual -i = CR30

2) ui/tabs/tab_chart.py:15230  _apply_ui_state, the `elif not built_here:` arm
   ui/tabs/tab_chart.py:5730   _init_manual_layout_panel
                               _set_engine_recipe(LayoutRecipe.from_dict(saved))
   ui/tabs/tab_chart.py:18218  _set_engine_recipe -> panel.set_recipe
   ui/dialogs/layout_options_panel.py:4401  self.instr.setCurrentIndex(ii)   # CM
   ui/tabs/tab_chart.py:5785   _sync_manual_selection_from_panel -> pw.set_value("CM")
   ui/parameter_widget.py:156  combo.setCurrentIndex(idx)
   ui/tabs/tab_chart.py:7154   pw.value_changed -> _mirror("manual")
   ui/tabs/tab_chart.py:7065   _instr_combo.setCurrentIndex(2)   # CM — CLOBBER
```

So the order inside `_apply_ui_state` is: restore the Guided row, then rebuild
the Manual layout panel from a **different source**, and let the instrument link
carry that source's instrument back over the value just restored. The mirror is
doing exactly what it was written to do; it is being fed the wrong value.

Two details worth recording because a naive fix trips on both:

* **`_sync_manual_selection_from_panel`'s `_loading` guard does not hold here.**
  `layout_options_panel.py:4400` sets `_loading = True` before
  `instr.setCurrentIndex`, but `_on_instr_changed` is connected to the same
  signal *first* and clears `_loading` part way through (the panel's own
  `set_recipe` docstring, `layout_options_panel.py:4338`, says so). By the time
  the tab's slot runs, `_loading` is already False.
* **`_syncing_instrument` is not violated either.** The trace shows
  `syncing=True` on the clobbering write — that is the mirror's own flag,
  correctly set. The guard only suppresses the *echo*; it cannot tell a stale
  value from a fresh one.

### Which binding rule this breaks
**§4c D-4** (confirmed by Basti, 2026-09-02): *"The app's own starting point —
factory settings, `default_recipe`, saved defaults — is **not** an answer."*
`manual_engine_recipe` is literally "saved defaults", and here it overwrites the
target's own stored instrument. **§4c D-2** is broken too (a value the person
chose, by building a CR30 chart, is overwritten). And §2.0 — a per-target
setting must have exactly one writer — is broken by a global settings key
writing into a per-target control.

This is therefore **a fault that contradicts the spec in the target's favour**:
the spec is right and the code is wrong, so it is a straight fix, not a matter
for Basti's ruling. (D-C is the opposite case — see E5.)

---

## E3 — CONFIRMED. YES: the wrong instrument is written back into `meta.json`,
### and D-A + D-D together form a SELF-SUSTAINING corruption loop.

This is the question the brief said matters more than the fix, and the answer is
yes. Probe `probe_da3.py` / `probe_da4.py`, real window, `manual_engine_recipe`
**deleted** from settings so nothing but the run's own record is in play:

```
stored guided.instrument = CR30 , stored engine_recipe.instrument = CM
  guided combo after restore : CM
  _collect_ui_state would now WRITE BACK:
     guided.instrument        = CM
     guided.double_density    = False        <- was True
     engine_recipe.instrument = CM
```

So a run whose `meta.json` holds a CR30 Guided row and a ColorMunki engine
recipe is **converted to a ColorMunki run by the act of looking at it**, and the
next W6 write files that as the run's own answer. That is Basti's report —
*"the chart was made for the cr30, but in guided mode it shows colormunki"* —
end to end, with the write-back included.

The loop closes with D-D: a Guided build records an engine recipe it never
authored (`tab_chart.py:14953`), so the disagreement that D-A then acts on is
**created by D-D on every Guided build**. Fix either one alone and the pair
still bites:

* fix D-A only → the run stops flipping, but every Guided build keeps writing a
  recipe that describes a different chart, and anything that reads
  `engine_recipe` (E9) still gets the wrong sheet.
* fix D-D only → new runs stop disagreeing, but **every run already on disk that
  disagrees still flips**, and `manual_engine_recipe` (E1) still flips runs that
  never had a recipe at all.

**They must ship together.**

### Blast radius, measured field by field (probe `probe_da4.py`)

Stored `guided` = CR30 / A3 / 3 pages / hexagons ON, restored four ways:

| stored `engine_recipe` | engine | what comes back changed |
|---|---|---|
| `CM`/`A4` (disagrees) | on | **`instrument` CR30→CM**, **`double_density` True→False** |
| `CR30`/`A3` (agrees) | on | nothing |
| absent (and no saved defaults) | on | nothing |
| `CM`/`A4` (disagrees) | **off** | nothing |

So: `paper`, `pages`, `triple_density`, `left_border`, `no_strip_limit` and
`precond` are **not** carried by this path — the instrument link is the only
mirror, and paper is set independently before it. The second casualty,
`double_density`, is collateral and correct-in-itself: `_update_dd_visibility`
(`tab_chart.py:12801`) clears the tick when the instrument's meaning for `-h`
changes, and it is being handed a wrong instrument.

**The defect only exists with the layout engine ON.** With it off, nothing in
`_apply_ui_state` touches the layout panel's instrument combo, so the guided row
survives. That is the narrowest true statement of the trigger:
*engine on + a stored `engine_recipe` (or a saved `manual_engine_recipe`) whose
instrument differs from the run's Guided instrument.*

---

## E4 — the honest fix for D-A, and what the two obvious ones break

**Naive fix 1 — "re-apply the guided instrument at the end of `_apply_ui_state`."**
Breaks D-3/D-4 in the other direction and papers over the ordering instead of
removing it: any *later* legitimate write (a preset, a `.ti2` seed) would still
lose, and the Manual side would be left showing CM while Guided shows CR30, so
the two modes disagree — which is the exact report `_link_instrument_controls`
exists to prevent (Knut, #130 2026-07-28).

**Naive fix 2 — "suppress the mirror while `_apply_ui_state` runs."**
This is the one the earlier review's "race" wording invites, and it is wrong:
the mirror is not the wrong writer, the *layout panel* is. Suppressing the
mirror leaves Manual's `-i` and the layout panel on `CM` while Guided says
`CR30`, and `_collect_ui_state` then writes an `engine_recipe` that still says
CM — D-D's disagreement, made permanent and now invisible. It converts a loud
bug into a quiet one.

**The honest fix, file:line.** The run's own record must be the only source, and
it must be applied to the layout panel *before* anything derived from it:

1. `ui/tabs/tab_chart.py:15220-15240` — reorder `_apply_ui_state` so the
   `engine_recipe` arm runs **before** the `guided` arm, not after. Then the
   guided row is the last writer, which is what §2.0 requires (the target's own
   record is the single writer) and what §4c D-2/D-4 require (the target's
   value beats saved defaults).
2. `ui/tabs/tab_chart.py:15230` — the `elif not built_here:` arm must stop
   calling `_init_manual_layout_panel()`, which reads the **global**
   `manual_engine_recipe` (`tab_chart.py:5726`). A target with no stored recipe
   is an S4 ("saved defaults, else factory") *for the layout panel*, but §2.0
   still forbids that seeding from writing the **guided** instrument. Either
   seed the panel from the guided row that was just restored, or gate the
   panel→printtarg mirror for this one call.
3. The disagreement must be made impossible at the source — E9's D-D fix.

A reorder alone is not sufficient while `_init_manual_layout_panel` can move the
panel: step 2 is what makes E1's four-run table come out clean in all four rows.

### Tests that must exist
* `QT_QPA_PLATFORM=offscreen`, engine ON, `manual_engine_recipe` **set** in the
  sandboxed settings to a CM recipe → `_apply_ui_state` with guided `CR30` →
  combo is `CR30`. (E1 proves this reproduces offscreen; there is no excuse for
  leaving it to an on-screen driver.)
* Same, but the disagreement carried in the run's **own** `engine_recipe`.
* A round-trip: `_apply_ui_state(x)` then `_collect_ui_state()` returns the same
  `guided` block for every field — the E3/E4 table as an assertion.
* One test that the two modes still agree afterwards (the mirror still works),
  or fix 2 will be re-introduced by a future reviewer.

---

## E5 — D-B is NOT a defect. It is Knut's #2 ruling, and the probe measured the
### wrong path. The real (small) defect next to it is in `_apply_ui_state`.

`_SWITCH_CARRY_FIELDS = ("instrument", "paper")` (`tab_chart.py:7004`) is
deliberate and documented two lines above it: *"On a plain tab switch (no
Generate) only these carry — the rest waits for the post-Generate transfer
(Knut #2)."* `-h` is not missing from a carried set; it is **excluded on
purpose**, and the same exclusion covers pages, triple density, `-L`, `-P` and
`-c`.

Measured on screen (probe `probe_db.py`), Guided CR30 with hexagons ON:

| path | manual `-i` | manual `-h` | panel `hflag` |
|---|---|---|---|
| plain module switch (what 00-reproduced.md tested) | `CR30` | `False` | `False` |
| **post-Generate #79 transfer** (`_guided_transfer_pending`, armed at `tab_chart.py:17450`) | `CR30` | **`True`** | **`True`** |

`_transfer_guided_to_manual` carries `-h` at `tab_chart.py:6963` and the engine
recipe via `_apply_guided_engine_recipe` at `:6979`. It works. A user who
generates a hexagonal CR30 chart in Guided and then opens Manual gets a
hexagonal Manual setup. **The reverse direction is symmetric** — a plain switch
Manual→Guided carries only instrument and paper too — so there is no asymmetry
to fix either.

**Do not "fix" D-B by adding `double_density` to `_SWITCH_CARRY_FIELDS`.**
Two things break:

1. It contradicts Knut's #2 ruling directly. Per CLAUDE.md this is the category
   that must be **reported and approved, not corrected** — the spec is the thing
   that would have to change, and that is Knut's call.
2. `_carry_shared_settings` carries a field when the snapshot differs, and the
   `_dd_check` tick is moved **by the app** in two places — force-cleared for
   i1/p3 (`tab_chart.py:12884`) and cleared when the family meaning changes
   (`:12805`). Both look like "the user changed it" to the snapshot/diff, so a
   carried `-h` would let an app-driven clear wipe a Manual `-h` the person set
   by hand. That is §4c **D-3** ("a default's own write is not an answer").

**The one thing here that IS wrong** is narrower, and it is E3's blast radius,
not the carry: when `_apply_ui_state` flips the instrument (E2), the stored
`double_density` is silently converted to `False` and written back. Fixing D-A
fixes that; nothing needs to change in `_carry_shared_settings`.

### Also measured, and it is a trap for D-D
The guided tick does **not** map to `hflag` for every instrument. In
`_engine_build_kwargs` (`tab_chart.py:12398-12422`) a ColorMunki's tick becomes
`density = 2` (with `cm_stagger`) and only a hex-capable instrument's tick
becomes `hflag`. Measured: Guided CM + "Double density" ON through the #79
transfer gives manual `-h=True` **and** panel `hflag=False`, which is correct.
So `hflag = guided.double_density` is a WRONG fix for D-D — see E9.

---

## E6 — CONFIRMED. D-C's premise is backwards. `left_border` is the ONE of the
### four that behaves correctly; two of its "siblings" silently destroy a
### chosen value, and neither was reported.

Measured on screen (probe `probe_dc2.py`), Guided, one instrument change and
back:

| what the person chose | after glancing at a CR30 and returning |
|---|---|
| i1 + **`-L` ticked** | still ticked — **survives** |
| i1 + **`-P` ticked** | **cleared. Gone.** (`tab_chart.py:12921`) |
| ColorMunki + **Triple density** | **cleared. Gone.** (`tab_chart.py:12901`) |
| CR30 + **hexagons** | still on — round 2's `_dd_memory` works |

Both losses go straight into the target's record: `_shared_get("guided")`
returns the cleared value and W6 files it as the run's own answer.

### Which doctrine the binding spec requires: `tab_measure.py`'s, not `tab_chart.py`'s
§4c **D-2** (confirmed by Basti, 2026-09-02): an instrument default *"may not
overwrite a value they have chosen — by hand, or by loading a preset"*, and
**D-3**: *"a default's own write is not an answer."* `_apply_cr30_dead_options`
(`ui/tabs/tab_measure.py:1539`) already states the same doctrine in the app's own
words: **"DISABLE ONLY, NEVER UNTICK. The saved value belongs to the target and
must survive for the day the same chart is measured with an instrument that does
honour it."** That is the spec-compliant one. `tab_chart.py`'s force-uncheck is
the doctrine that loses.

`_dd_check` is not a counter-example — it is the exception that proves the rule.
Its clear is justified by a **change of subject**, not by inapplicability: the
one widget is three different options (`_DD_FAMILIES`, `tab_chart.py:12725`), so
a tick left standing would assert something about an option the person never
saw. Round 2 got that right by pairing the clear with per-instrument **memory**.
`-L`, `-P` and triple density each have exactly one meaning and one subject;
they merely become inapplicable, which is precisely the `tab_measure.py` case.

### Measured: nothing is at risk from letting a hidden value stand
Every one of these is already gated at **build** time, so the force-clear buys
no safety at all — it only destroys stored state:

* `-L`: `l_applies = p.instrument in {"i1","p3"} or triple`
  (`workflow/chart_creator.py:2004`).
* `-P` / `-h`: filtered at `workflow/chart_creator.py:1995` and in the guided
  collector (`tab_chart.py:19314`).
* the engine: `nolpcbord` is set **only** for i1/p3
  (`workflow/chart_creator.py:1276-1278`).

### And 00-reproduced.md's stated harm does not exist. Measured.
It says `left_border` *"IS passed to the layout engine ungated as
`suppress_left_clip` (ui/tabs/tab_chart.py:178)"*. Two separate errors:

1. `_layout_options_from_params` builds a `workflow.ti2_relayout.LayoutOptions`,
   which never reaches the engine — its only consumer is `printtarg_args()`
   (`ti2_relayout.py:508`). Both of its callers are explicitly gated OFF for
   engine charts (`tab_chart.py:10265` returns early when the engine is on;
   `tab_chart.py:19178` passes `sync_layout=not is_engine`).
2. Built and byte-compared. `ChartCreator._engine_build_kwargs` for a CR30 is
   **identical** for `disable_left_border` True and False, and so is the chart:

```
engine build kwargs  CR30: IDENTICAL   SS: IDENTICAL   CM: IDENTICAL
                     i1  : {'nolpcbord': (True, False),
                            'clip_content_mode': ('off', 'notes')}
real CR30 engine render (tests/fixtures/charts/cm_a4_480p_2pages.ti1, A4, 2 pages)
   disable_left_border=True   tiffs=['97101e78ab80f97c','892467785b07d2a9'] ti2=d4ebc804…
   disable_left_border=False  tiffs=['97101e78ab80f97c','892467785b07d2a9'] ti2=d4ebc804…
   -> IDENTICAL
```

### The honest fix, and it is the OPPOSITE of the reported one
**Leave `_lb_check` alone.** Stop the two clears that break D-2:
`tab_chart.py:12901` (`_td_check`) and `tab_chart.py:12921` (`_nsl_check`).
Keep the `_dd_check` clear + memory as round 2 left it.

### ⚠ THIS ONE NEEDS BASTI'S RULING BEFORE IMPLEMENTATION
Per CLAUDE.md's binding-spec rule this is exactly the "report it, say which rule
it breaks, get it approved" category, and for two reasons at once:
* the honest fix **inverts** the defect as reported — nothing is cleared, and
  one more control keeps its value;
* it changes the behaviour of **two controls nobody reported** (`-P` and triple
  density), and undoing a silent clear is visible: a `-P` a user once ticked
  will start reappearing on i1 charts where it used to vanish.

Do not implement D-C in the same change set as D-A/D-D. Ask, then do it.

---

## E7 — CONFIRMED. D-D is far worse than "`hflag` disagrees": **12 of 85 fields
### disagree**, including the instrument.

`_collect_ui_state` takes `engine_recipe` straight from
`self._manual_layout_panel.get_recipe()` (`ui/tabs/tab_chart.py:15059-15061`),
unconditionally, whatever module the user is in. Nothing in a Guided build ever
writes a Guided choice into that panel — only `_transfer_guided_to_manual` →
`_apply_guided_engine_recipe` (`:6989` / `:7241`) does, and that runs solely on
the post-Generate module switch (`_guided_transfer_pending`, armed at `:17450`).

Measured on screen (probe `probe_dd.py`) with Guided on CR30 + hexagons + A4,
comparing what the run stores against what a Guided build actually hands the
engine (`ChartCreator._engine_build_kwargs` → `LayoutRecipe.from_build_kwargs`,
`chart_creator.py:1246`):

```
   area_ratio              stored=1.0            guided-build=0.0
   clip_content_mode       stored='notes'        guided-build='off'
   hflag                   stored=False          guided-build=True
   instrument              stored='i1'           guided-build='CR30'
   layout_mode             stored='area_first'   guided-build='patch_first'
   margin_bottom           stored=19.0           guided-build=6.0
   margin_left             stored=26.0           guided-build=6.0
   margin_right            stored=9.0            guided-build=6.0
   margin_top              stored=38.0           guided-build=6.0
   patch_area_align        stored='top-left'     guided-build='center-left'
   spacer_mode             stored='colored'      guided-build='none'
   use_instrument_margins  stored=True           guided-build=False

   12 field(s) disagree out of 85
```

`instrument` appearing here and NOT in 00-reproduced.md is worth noting: it
agrees only if the session has switched to Manual at some point (that runs
`_sync_engine_panel_selection`). In a session that never leaves Guided —
the normal case for a Guided user — even the instrument is `i1`. That is the
supply side of E3's corruption loop, and it means the loop bites a user who
never touches Manual at all.

*(Caveat, so nobody re-derives it: the `guided-build` margins printed as 6/6/6/6
are `LayoutRecipe`'s dataclass defaults, not what the sheet used —
`chart_creator.py:1520-1535` documents that Guided has no margin boxes and
patches `INSTRUMENT_DEFAULT_MARGIN` in when it writes `channels.json`. The
comparison stands regardless: `26/38/19/9` are the **i1Pro** instrument margins
on a CR30 sheet.)*

---

## E8 — What reads `create_chart_ui.engine_recipe`, and what each gets

Complete list, grepped and read:

| reader | file:line | gets today | under fix (a) "make Guided author it" | under fix (b) "stop recording it" |
|---|---|---|---|---|
| the target load, `_apply_ui_state` → `_set_engine_recipe` | `tab_chart.py:15196-15223` | an i1 recipe, **and it clobbers the Guided instrument** (E2/E3) | the CR30 recipe — the clobber becomes a no-op because the two agree | falls to `elif not built_here` → `_init_manual_layout_panel` → **D-A again, via saved defaults (E1)** |
| **Duplicate run** | `core/file_manager.py:2470-2475`, `DUPLICATE_META_CARRY` | the duplicate carries the i1 recipe — its own comment says *"without it 'the same settings' would still build a different sheet"*, and that is exactly what happens | the duplicate builds the same sheet | the duplicate builds from whatever panel is on screen |
| the chart-sidecar shield's per-field diff | `tab_chart.py:14381-14400` | diffs fields that never described this chart | diffs real fields | the key is absent; the shield has nothing to compare |
| **Save Preset** / **"Load setup from preset"** | `tab_chart.py:10068-10075` (save), `:9126-9148` (load) | **neither reads `create_chart_ui`** — both go through the layout **panel** | unchanged directly, but a preset saved after reopening a Guided run is now right, because the panel was restored correctly | unchanged; the panel is whatever the saved defaults left |
| the TI2 layout editor / Restore Used Chart | `presets.LayoutRecipe.from_channels_json`, `tab_chart.py:11683` | **reads `<stem>.channels.json`, not `create_chart_ui`** — this record is already honest | unchanged | unchanged |

**The chart's own `channels.json` already holds the truth.** A Guided engine
build writes `LayoutRecipe.from_build_kwargs(self._engine_build_kwargs(params))`
into it at `workflow/chart_creator.py:1523-1527`, margins patched. So
`create_chart_ui.engine_recipe` is a **second, unauthored copy of a record that
already exists correctly elsewhere** — which is §2.0's "several actors" failure
in its purest form.

---

## E9 — The honest fix for D-D, and the one that looks obvious and is wrong

**Wrong fix: `engine_recipe["hflag"] = guided["double_density"]`.** Measured in
E5: the guided tick maps to `hflag` only for hex-capable instruments; on a
ColorMunki it maps to `density=2` + `cm_stagger`
(`tab_chart.py:12398-12422`, `chart_creator.py:1282-1300`). Writing `hflag=True`
for a CM double-density chart would record a hexagonal ColorMunki sheet, which
does not exist. And it fixes 1 of the 12 disagreeing fields.

**Wrong fix: stop recording `engine_recipe` in Guided.** It reads well —
"a Guided build never authored one" — and it re-opens D-A through the other
door: an absent key sends `_apply_ui_state` down `elif not built_here:` →
`_init_manual_layout_panel()` → the **global** `manual_engine_recipe`, which is
E1's exact reproduction. It also breaks Duplicate run.

**The honest fix: give the record one writer, and make it the chart's.**

1. `ui/tabs/tab_chart.py:15059-15061` — when the run's chart is an engine chart,
   `engine_recipe` must come from the recipe that built it, i.e.
   `LayoutRecipe.from_channels_json(<stem>.channels.json)`
   (`workflow/layout_engine/presets.py:348`), which the editor and Restore Used
   Chart already treat as authoritative.
2. Where there is no chart yet (a Guided panel being set up), derive it the way
   the build will: `LayoutRecipe.from_build_kwargs(
   self._creator._engine_build_kwargs(self._collect_guided()))`, with the same
   `INSTRUMENT_DEFAULT_MARGIN` patch `chart_creator.py:1527` applies — **share
   that code, do not re-implement it**, or the two records drift the way Set A
   and Set B did in #92.
3. Keep the panel as the source only when the module actually is Manual/gamut.

That produces a run whose stored state is honest by construction, and it is
also what makes E4's D-A fix stable: once the two records agree, the instrument
link has nothing wrong left to propagate.

### Tests that must exist
* Guided + CR30 + hexagons → `_collect_ui_state()["engine_recipe"]` has
  `instrument == "CR30"` and `hflag is True`, and **no field disagrees** with
  `LayoutRecipe.from_build_kwargs(_engine_build_kwargs(_collect_guided()))`.
  (Assert the whole dict, not `hflag` — E7 shows 12 fields were wrong and only
  one was noticed.)
* Guided + **ColorMunki** + Double density → `hflag is False`, `cm_density == 2`.
  This is the test that stops the obvious wrong fix being written later.
* A built Guided run: `create_chart_ui["engine_recipe"] ==` the recipe in that
  chart's `channels.json`.
* Duplicate a Guided CR30 run → the copy's `engine_recipe` still says CR30.

---

## E10 — the existing suite is green on all of this, and one test file is
### positioned to have caught it

`tests/test_a_preset_is_not_a_target_with_nothing_stored.py`,
`test_the_density_tick_belongs_to_one_instrument.py`,
`test_guided_manual_transfer.py`, `test_a_fresh_run_opens_on_its_own_defaults.py`
— **36 passed**, offscreen, on HEAD. The first of those already sets
`manual_engine_recipe` in the sandbox (line 80) to prove a *preset* survives it;
nobody asked the same question about a **run's own Guided instrument**, which is
E1. That is where D-A's regression test belongs.

No test asserts the force-clear of `_nsl_check` or `_td_check`, so E6's fix
breaks nothing that exists (grepped: the only `_manual_td_check.setChecked(False)`
lines in `tests/` are set-up, not assertions).

---

## E11 — SUSPECTED / OPEN. We reproduce the instrument half of Basti's report
### exactly. We do NOT reproduce the ticked box, and that matters.

His words: *"the chart was made for the cr30. but in guided mode it shows
colormunki **with double density selected**."*

E2/E3 account for "shows colormunki" completely. They do the **opposite** to the
tick: when the instrument flips from CR30 to CM, `_update_dd_visibility`
(`tab_chart.py:12801-12806`) sees the two families' meanings differ and clears
the box, so what we measure is ColorMunki with double density **off** — and that
False is then written back.

Neither of the two "absent means neutral" seeds explains it either. Read from
the owner's own preferences (read-only, `defaults read`):

```
chart_instrument      = CM          <- both routes point at a ColorMunki
chart_double_density  = 0           <- and neither ticks the box
manual_engine_recipe  : instrument = CM, cm_density = 1, hflag = 0
```

So there is either a **third path** that ticks it, or his run's `meta.json`
already held `guided = {instrument: CM, double_density: true}` from an earlier
pass of the loop, in which case the two halves happened on different days.

**Do not close the report on E2/E3 alone.** The evidence needed is his run's
actual `create_chart_ui` block, which
`scripts/drive_youtube_cr30_shows_colormunki.py` already prints (it copies the
project into a sandbox first). Run it before the fix and after it, and say which
of the two explanations it was.

---

## Recommendation — what ships together, and what needs a ruling first

### Ship as ONE change set: D-A + D-D
They are one defect with two ends (E3). Either alone leaves a live corruption
path, and D-D's fix is what makes D-A's fix stable rather than a suppression.
Neither contradicts the binding spec — both **restore** §2.0 (one writer per
per-target setting) and §4c D-2/D-4 (the target's own value beats the app's
saved defaults). No ruling needed; report the change, do not ask permission.

Order within the set: fix `_collect_ui_state`'s source of `engine_recipe` (E9)
first, then `_apply_ui_state`'s ordering and its `_init_manual_layout_panel`
call (E4). Doing E4 first makes E9 look unnecessary; doing E9 first makes E4
testable.

### Do NOT ship: D-B
It is not a defect (E5). `-h` is excluded from a plain module switch by Knut's
#2 ruling and carries correctly on the post-Generate path, which is what the
feature is for. Changing it would contradict a binding ruling AND reintroduce a
§4c D-3 hole. **Report it as "not a defect" and leave the code alone.** If Knut
wants density to carry on a plain switch, that is a spec change and his to make.

### Ask BASTI BEFORE implementing: D-C
E6 shows the reported fix is backwards: `left_border` is the only one of the
four that already obeys §4c D-2, and `-P` and triple density are losing chosen
values today. The honest fix therefore (a) does the opposite of what was
reported and (b) changes two controls nobody complained about, so a user will
start seeing a `-P` tick survive where it used to vanish. That is the
"report it, get the change approved" category in CLAUDE.md. One question is
enough:

> Create Chart clears three of the four instrument-specific tick boxes when you
> pick an instrument that cannot use them — so a "Don't limit strip length" or a
> "Triple density" you ticked yourself is gone when you come back, and the run
> records it as gone. The Measure tab already does the opposite ("disable only,
> never untick") and §4c D-2 says a default may not overwrite a value somebody
> chose. Should Create Chart keep those ticks the way Measure does?

### Also worth deciding at the same time (cheap, same area)
`_collect_ui_state`/`_apply_ui_state` currently seed a target's Guided row from
the **global** saved defaults when the key is absent. That is right for a target
with nothing stored (§4 S4/S9), and it is also the route by which the owner's
`chart_instrument = CM` reaches a CR30 run's panel. The fix set should make sure
that seed can never be **written back** as the target's own answer without the
user touching anything — §4c D-4.
