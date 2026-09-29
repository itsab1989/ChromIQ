# Regression review — d1adbe31 "A CR30 project reopened as a ColorMunki"

Reviewer: an adversarial pass over the finished change set, 2026-09-08.
A/B baseline is the commit's own parent, `d1adbe31~1` (4d0670b4), in a
throwaway worktree; the master worktree at 7e500e59 is used where the question
is "did this ever work differently before the CR30/density round".

Method: every bucket of `_apply_ui_state` exercised in 22 stored-record shapes,
each in its OWN process (offscreen), both trees, and diffed field by field.
Probe: `scratchpad/rr/bucket_ab.py`, differ `scratchpad/rr/diff.py`.

---

## F1 — REGRESSION, CONFIRMED. A ColorMunki "Triple density" tick that now
### survives HIDES two rows on the i1Pro, and one of them is `-P` itself.

`_update_dd_visibility` still computes, unchanged by this commit:

```python
lb_visible  = instr in {"i1", "p3"} and not self._td_check.isChecked()
nsl_visible = instr in {"i1", "p3"} and not self._td_check.isChecked()
```

Those two lines were correct only because the line directly above them used to
force `_td_check` off for every non-ColorMunki. Removing the force-uncheck
without touching them makes a stale ColorMunki tick suppress two i1Pro rows.

Measured, offscreen, both trees (`scratchpad/rr/td_hides_two_rows.py`):

| step | HEAD `_td` | HEAD `-L` row | HEAD `-P` row | parent `-P` row |
|---|---|---|---|---|
| on CM, nothing ticked | off | hidden (right) | hidden (right) | hidden |
| CM + Triple density ON | on | hidden | hidden | hidden |
| → i1Pro | **still on** | **HIDDEN** | **HIDDEN** | visible |
| → i1Pro 3 Plus | still on | HIDDEN | HIDDEN | visible |
| → back to i1Pro | still on | HIDDEN | HIDDEN | visible |

There is no way back from inside the i1Pro: `_td_check` is itself hidden for
every instrument but the ColorMunki, so the tick that is hiding the two rows
cannot be seen or cleared while they are hidden. The user must go back to a
ColorMunki, untick it there, and return.

The irony is exact: this change set exists to stop `-P` being thrown away, and
it has made `-P` unreachable on the only two instruments that use it.

## F2 — REGRESSION, CONFIRMED, AND IT CHANGES THE CHART. The same stale tick
### leaves `-L` forced ON for the i1Pro, so the sheet AND the patch set differ.

`_on_guided_td_toggled(True)` stashes the user's `_lb_check` and forces it on,
because triple density forces `-L` internally; the stash is restored **on
untoggle**. `_td_check` is now never untoggled by the instrument change, so the
forced value stands on the next instrument — and for an i1Pro `-L` is not a
no-op, it is the whole left clip border.

Measured, both trees, same script path
(`scratchpad/rr/td_changes_the_i1_chart.py`): tick Triple density on a
ColorMunki, switch to i1Pro, collect a Guided build.

| | never touched CM | after a CM triple-density tick (HEAD) | parent |
|---|---|---|---|
| `disable_left_border` | False | **True** | False |
| printtarg args | `-ii1 -pA4 -t300 -a0.95 -m10 -M10` | **`… -t300 -L -a0.95 …`** | unchanged |
| engine `nolpcbord` | False | **True** | False |
| engine `clip_content_mode` | `notes` | **`off`** | `notes` |
| targen grey steps (`-g`) | 28 | **30** | 28 |

So it is not only the layout: `guided_neutrals` sees the changed `-L` and the
**patch recipe changes too**. A different chart, from a tick made for a
different instrument, with no visible cause on screen (F1 hid the `-L` row).

This falsifies the claim the commit message and the new code comment both make:

> *"Neither can reach printtarg for an instrument that ignores it, so nothing
> builds differently; the tick simply comes back with the instrument it
> belongs to."*

`_td_check` does not reach printtarg directly. It reaches it through
`_lb_check`, which the toggle handler moved on its behalf and never moved back.

## F3 — REGRESSION, CONFIRMED. The same tick DISABLES "Hexagon patches" on the
### CR30 and "Double density" on the ColorMunki, permanently.

`_on_guided_td_toggled` also does `self._dd_check.setEnabled(not checked)`.
With the tick surviving, `_dd_check` stays **disabled** on every instrument the
user visits afterwards. Measured in the same run: on the CR30, `dd_enabled` is
`false` on HEAD and `true` on parent, with the box visible and greyed out. The
CR30's hexagon option — the subject of the sibling commit two back — cannot be
ticked at all until the user returns to a ColorMunki and clears triple density.

**F1, F2 and F3 are one omission**: the force-uncheck was removed, but the three
places that consumed "the widget is unticked whenever it is hidden" were not.
The `_dd_check` clear that was deliberately KEPT is the model for what was
needed here: keep a per-instrument memory, or gate the three consumers on
`td_visible and _td_check.isChecked()` rather than on the raw tick.

## F4 — REGRESSION, CONFIRMED. The poisoned state is WRITTEN INTO THE RUN and
### survives a reload, so the fault is permanent per target.

`_shared_get("guided")` reads the raw tick, so W6 files it. Measured
(`scratchpad/rr/td_persists.py`): tick Triple density on a ColorMunki, switch
to i1Pro, collect the run's record.

```
HEAD    guided = {instrument: i1, triple_density: TRUE,  left_border: TRUE,  …}
parent  guided = {instrument: i1, triple_density: false, left_border: false, …}
```

`left_border: true` is not cosmetic — it is the `-L` the chart is built with
(F2). Applying that record to a fresh tab reproduces the whole state: the tick
back on, both rows hidden, `_dd_check` disabled, `disable_left_border` True.

So a single stray tick on a ColorMunki converts the i1Pro run into one that
suppresses its left clip border for ever, and the app wrote that answer itself.
That is §4c D-3 ("a default's own write is not an answer") broken by the change
that was made to honour §4c D-2.

## V1 — VERIFIED, and on the path neither shipped driver takes. The reorder
### does fix the reported fault through the REAL target bar.

Both shipped drivers call `_apply_ui_state` directly. The owner's gesture is a
run switch in the bar, which goes `_on_target_changed` → `load_target_settings`
→ `apply()` → `_apply_ui_state`. Driver written for it:
`scratchpad/rr/drive_real_target_switch.py` — a real project made through
`win._file_mgr.set_target_name`, two runs, `run1` carrying the Youtube shape
(Guided CR30, `engine_recipe` ColorMunki) and a global "Save as Defaults"
ColorMunki recipe in preferences.

| tree | run1's stored recipe | run1 comes back as | run1's meta.json after looking at it |
|---|---|---|---|
| parent | ColorMunki | **CM, `-h` False** | **rewritten to CM / False** |
| HEAD | ColorMunki | CR30, `-h` True | untouched: CR30 / True |
| parent | i1Pro | CR30 (no clobber) | untouched |
| HEAD | i1Pro | CR30 | untouched |

So the corruption loop, including the write-back, reproduces on the parent
through the real path and is gone on HEAD. run2 keeps its own `-P` across both
switches on both trees.

**One caveat on how these tests must be built.** A synthetic run needs a
non-empty `create_chart_settings`, not just `create_chart_ui`:
`load_target_settings` treats an empty `create_chart_settings` as "nothing
stored", opens the target on its defaults and **never reads `create_chart_ui`
at all**. My first attempt had only the `ui` block, and both trees "failed"
identically for that reason. Worth knowing before writing a test for this area.

## F5 — SUSPECTED, low. After the reorder the layout PANEL is the one thing
### left holding the stale recipe, and the three modules briefly disagree.

`_set_engine_recipe` now runs before the Guided row, and the Guided row's
mirror reaches the printtarg `-i` widget but **not** the layout panel (nothing
connects `-i` to `_sync_engine_panel_selection`). So a run whose stored recipe
disagrees comes back as Guided CR30 / printtarg CR30 / panel ColorMunki.
Measured in 8 of the 22 bucket shapes, and in the real-path driver above
("panel='CM'").

It heals itself the moment the user enters Manual — `_refresh_manual_ui` calls
`_sync_engine_panel_selection()` on the engine's off→on transition, and the
probe shows the panel and the build both land on CR30 there. And nothing builds
differently: a Guided build reads `_collect_guided`, never the panel.

Recorded because it is the shape a later reviewer will trip over, and because
`test_the_two_modes_still_agree_afterwards` proves agreement against the
**hidden** printtarg `-i` row rather than the panel that Manual actually shows
when the engine is on. That test would stay green if the panel were left
arbitrarily wrong.

## D — MUTATIONS. Seven, each proven to land (`git diff --stat` after the edit,
### `ui/__pycache__` cleared before every run). Six caught, one very much not.

| # | mutation | caught by |
|---|---|---|
| M1 | revert the reorder: the present-recipe arms move back **after** the guided row | `test_the_guided_instrument_is_the_runs_own` ×3 + `test_the_two_modes_still_agree_afterwards` |
| M2 | drop the build-in-flight shield on the recipe (`and built_here` → `and False`) | not by the new file; caught by `test_live_preview_does_not_replace_a_preset` ×2 and `test_generate_keeps_the_settings_it_built_with` |
| M3 | put the `_td_check` force-uncheck back | `test_a_control_the_other_instrument_hides_keeps_its_value[_td_check-CM-i1]` |
| M4 | put the `_nsl_check` force-uncheck back | `…[_nsl_check-i1-CR30]` |
| M5 | move the ABSENT-recipe branch up as well (the red-gate mistake the commit message describes) | `test_an_absent_bucket_means_neutral_not_whatever_is_on_screen` — exactly the file the message names |
| M6 | the tempting wrong fix: `self._syncing_instrument = True` across the guided block | `test_the_two_modes_still_agree_afterwards` |
| **M7** | **`lb_visible = False` and `nsl_visible = False` — the `-P` and left-border rows never appear for anyone, on any instrument** | **NOTHING. 11856 passed, 310 skipped, 4 xfailed, everyday tier, 1:48.** |

M7 is the finding, not the method. **No test in the suite asserts that the `-P`
row or the left-border row is ever visible**, so deleting them entirely is a
green run — and that is precisely the hole F1/F2/F3 came through. The new test
`test_a_control_the_other_instrument_hides_keeps_its_value` checks that the tick
survives a visit to the other instrument; nothing checks what the visit did to
the instrument being visited.

Note on method, because it nearly cost this section: the first mutation run
reported every mutation as caught, and every one of those runs had actually
ERRORED with "file or directory not found" — zsh does not word-split an
unquoted `$TESTS` string. A mutation that is proven to land still proves nothing
if the tests never ran. Re-run with an array, the baseline is `53 passed,
1 xfailed`.

## V2 — VERIFIED. The `-P` half is safe. A surviving `-P` reaches no chart it
### should not.

`_collect_guided` gates it: `nsl_ui = self._nsl_check.isChecked() and instr in
{"i1","p3"} and not td`. Built both ways for all three instruments that hide it
(`scratchpad/rr/nsl_reaches_nothing.py`): identical `printtarg` args, identical
engine kwargs (`nolimit` False), identical grey steps.

| target | never touched the i1Pro | after `-P` ticked on the i1Pro |
|---|---|---|
| CR30 | engine only, `nolimit=False`, `-g32` | identical |
| ColorMunki | `-iCM -pA4 -t300 -M6`, `-g8` | identical |
| SpectroScan | `-iSS -pA4 -t300 -M6`, `-g58` | identical |

Worth recording that the gate is in the **guided collector**, not in
`_build_printtarg_args`: `chart_creator.py:2022` appends `-P` for any
instrument, ungated. The challenge document (E6) states `-P` is "filtered at
`workflow/chart_creator.py:1995`" — that filter covers `-h`, and the line it
cites next (`l_applies`, :2004) is the `-L` gate. `-P` has no instrument gate
there at all. The claim happens to hold for Guided; it does **not** hold as
stated, and Manual's own `-P` widget is ungated end to end (unchanged by this
commit, so not a regression, but the reasoning that licensed the change is
wrong).

## F6 — REGRESSION, CONFIRMED, minor. "Double density" and "Triple density" can
### now be ticked at the same time, and the pair is stored.

The two are mutually exclusive by design, enforced in both toggle handlers.
A random walk of 4000 real gestures over the instrument combo and the two boxes
(`scratchpad/rr/both_ticked.py`, seed 7, one tab so every state is reachable):

```
HEAD   : 2 distinct states with both boxes ticked (on CR30 and on SS)
parent : 0
```

Reached by, e.g., ticking Triple density on a ColorMunki, glancing at an i1Pro
(which no longer clears it) and picking a CR30, whose own remembered hexagon
answer is then restored through `_set_dd_without_remembering` — that path sets
`_dd_writing`, so `_on_guided_dd_toggled`'s "if checked, untick the other one"
never runs.

The BUILD is unharmed (`triple_density` is gated to the ColorMunki, so the CR30
sheet is a plain hexagon one). What is harmed is the record: `_shared_get`
returns `{"double_density": true, "triple_density": true}` and W6 files that
impossible pair as the run's own answer.

## E — THE GATE, on HEAD, unmodified

```
QT_QPA_PLATFORM=offscreen pytest --runslow -n auto
11999 passed, 167 skipped, 4 xfailed in 208.29s (0:03:28)     exit 0
```

Matches the commit message exactly. No worker-down banner, no `Timeout` dump.
The gate is green and F1–F4 and F6 are all real: it proves nothing about them,
which M7 explains.

## F — ON SCREEN, real window, cocoa, sandboxed settings

Settings sandboxed with `CHROMIQ_SETTINGS_FILE` for every run; afterwards
`defaults read com.chromiq.ChromIQ custom_output_path` prints the owner's empty
value, checked after each of the five on-screen runs.

**The two shipped drivers, on screen, on HEAD: 0 problems each.**

* `scripts/drive_a_run_reopens_on_its_own_instrument.py` — Guided `'CR30'`,
  density tick `True`, Manual `-i` `'CR30'`; both hidden controls kept.
* `scripts/drive_cr30_hz_and_density_tick.py` — all seven instruments' rate
  boxes, the three meanings of the density widget, the CR30 and ColorMunki
  memories. 0 problems.

**Beyond them — the gesture the owner actually performs.**
`scratchpad/rr/drive_real_target_switch.py`, shown window, a real project, the
run switched in the target bar:

```
HEAD    select run1 -> guided='CR30' -h=True  manual-i='CR30'   (meta untouched)
parent  select run1 -> guided='CM'   -h=False manual-i='CM'     (meta REWRITTEN to CM)
```

and then, in the same window, on the i1Pro after a ColorMunki triple-density
tick, side by side (screenshots on the Desktop in `real-target-switch/`,
`head-guided-options.png` and `parent-guided-options.png`):

| what the window shows on the i1Pro | parent | HEAD |
|---|---|---|
| "Suppress left clip border (-L)" row | visible | **gone** |
| "Don't limit strip length (-P)" row | visible | **gone** |
| Calculated Patches | **484** | **550** |
| the fixed-settings box | `targen -d2 -G -e4 -B4 -g28 … clip border on` | `… -g30 … clip border off` |

66 more patches on the sheet the user is about to print, and a clip border
turned off, from a tick made for a different instrument, with no control on
screen that says so. That is F1 and F2 as the owner would meet them.

**Score, on screen, same driver, same gesture: parent 3 problems, HEAD 3
problems.** They are not the same three. One reported fault is fixed; three
unreported ones are introduced.

---

# The prioritised list

## REGRESSIONS (all four are the same omission, all confirmed, all reachable
## by ordinary gestures, none caught by the gate)

1. **F2 — a ColorMunki "Triple density" tick changes the next i1Pro chart.**
   `-L` forced on and never restored: `printtarg … -L`, engine `nolpcbord=True`,
   `clip_content_mode` `notes`→`off`, and the patch recipe moves `-g28`→`-g30`
   (484 → 550 patches on screen). The commit message states this cannot happen.
2. **F1 — the `-P` and left-border rows disappear on the i1Pro** and cannot be
   brought back from there, because the tick hiding them is itself hidden.
   The change set exists to protect `-P`; it has made `-P` unreachable.
3. **F4 — the state is written into the run** (`triple_density: true,
   left_border: true` on an i1Pro run) and reproduces on reload. Per-target
   corruption, written by the app, which is §4c D-3.
4. **F3 — "Hexagon patches" / "Double density" is stuck disabled** on every
   instrument afterwards.
5. **F6 — both density boxes can be ticked at once** and the impossible pair is
   stored. Build unaffected.

**The fix is small and the commit already names it.** `_dd_check` was kept
clearing *with a per-instrument memory*, and that is the model these two needed
too. Either:
* give `_td_check` (and `_nsl_check`) the same memory treatment as `_dd_check` —
  clear the widget when it is hidden, restore it when the person picks that
  instrument back (`_on_user_picked_instrument`, never on an app-driven
  change); or
* keep the tick and fix all three consumers: `lb_visible` / `nsl_visible` must
  gate on `td_visible and self._td_check.isChecked()`, not the raw tick, and
  `_on_guided_td_toggled`'s two side effects (the `_lb_check` force + stash and
  the `_dd_check` disable) must be undone when the tick stops applying.

Worth knowing for whoever does it: on the Guided row `_td_check` is
ColorMunki-only, so `instr in {"i1","p3"}` is already False whenever triple
density is genuinely in effect. The `and not self._td_check.isChecked()` term in
both visibility lines can therefore **only** ever fire on a stale tick. Deleting
it fixes F1 outright.

## BLOCKERS

* Nothing blocks the *reorder* half. V1 shows it fixes the reported fault
  through the real target bar, V2 and the bucket sweep show no bucket changed
  behaviour, the build-in-flight shield is bit-identical to the parent, and six
  of seven mutations are caught.
* The **two-controls half should not ship as it stands**. It was approved on a
  statement of fact ("nothing builds differently") that F2 disproves. That makes
  it the CLAUDE.md category that goes back for a ruling on the *corrected*
  facts, not one to quietly patch and forget: Basti approved keeping a tick that
  changes no chart, and the tick as implemented changes the chart.

## SHOULD-FIX

* **The new tests test one direction only.** `test_a_control_the_other_
  instrument_hides_keeps_its_value` asks what the visitor did to the owner's
  tick; nothing asks what the visit did to the visitor. M7 shows the gap is
  total: `lb_visible = False; nsl_visible = False` is a green everyday tier
  (11856 passed). A test that pins the i1Pro's own rows visible, and its
  `-L`/`-g` unchanged, after a ColorMunki visit, would have caught F1 and F2.
* **The xfail's claim about `-P` gating is wrong in its cited location** (V2).
  `chart_creator.py:2022` appends `-P` ungated; the safety comes from
  `_collect_guided`. The comment in `_update_dd_visibility` repeats the wrong
  version and should be corrected wherever the change lands.

## NICE-TO-HAVE

* **F5** — after the reorder the layout panel alone keeps a disagreeing stored
  recipe until the user enters Manual. Harmless today, and
  `test_the_two_modes_still_agree_afterwards` would not notice if it stopped
  being harmless: it compares against the printtarg `-i` row, which is hidden
  whenever the engine is on. Compare the panel instead, or as well.
* The xfail is accurate and genuinely fails (12 of 85 fields, `i1` on a CR30
  run, margins 26/38/19/9 reproduced field for field), and its "harm is bounded"
  claim holds for the Guided instrument in all nine combinations of a stored
  recipe against a saved default.

## WHAT I COULD NOT VERIFY

* **A real ArgyllCMS render of the two i1Pro charts.** F2 is proven at the
  command and engine-kwargs level and in the on-screen patch count (484 vs 550);
  I did not print or byte-compare two rendered TIFFs.
* **Basti's own Youtube project.** Everything here uses synthetic runs of the
  same shape. E11's open question — where his ticked "double density" came from
  — is untouched by this review.
* **A preset load driven on screen.** Covered only by the existing tests, which
  M2 proves do bite (`test_live_preview_does_not_replace_a_preset` ×2 and
  `test_generate_keeps_the_settings_it_built_with`), plus the built-in-flight
  probe showing the panel, the Guided row, the module, the calibration and the
  gamut block all untouched while `_layout_owned_by_build` is set.
* **Windows and Linux.** Everything here is macOS, cocoa and offscreen.
* **Whether F1/F2/F3/F6 predate the commit in some other form.** They do not for
  the paths measured — the parent tree is clean on every one of them — but I did
  not search master's history for an earlier occurrence.
