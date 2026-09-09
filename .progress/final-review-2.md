# FINAL RELEASE REVIEW, ROUND 2 — ChromIQ v4.2.1, commit `abff609b`

Reviewer: second final pass, 2026-09-08. Scope: the single unreviewed commit
`abff609b` (the density-tick fix, its new test file, and the rewritten v4.2.1
changelog), regressions against master, and an on-screen end-to-end run.

Prior round is `.progress/final-review.md` (S1..S19); its findings are not
re-derived here except where this commit claims to change them.

Findings are appended as they are confirmed. CONFIRMED = reproduced here.

---
## T1 — CONFIRMED, GREEN. The release gate passes on `abff609b`, and the count
### is exactly what the commit message claims.

```
QT_QPA_PLATFORM=offscreen pytest --runslow -n auto
12010 passed, 167 skipped, 4 xfailed in 203.76s (0:03:23)      exit 0
```

No worker-down banner, no `Fatal Python error`, no `Timeout (0:0X:XX)!` dump.
`12010 / 167 / 4` matches the commit message verbatim, and it is +9 over the
previous round's 12001, which is the 9 net new tests in the new file
(22 collected, 13 of them parametrised expansions of pre-existing ideas).

## T2 — CONFIRMED. The fix is real, and a 12,000-gesture random walk finds NO
### state reachable on HEAD that is not also reachable on master.

Probe `scratchpad/fr2/walk2.py`: a seeded random walk over the Guided panel
(instrument by `activated`, instrument by app `setCurrentIndex`, the four
checkboxes clicked only when visible AND enabled — what a mouse can do —,
paper, pages, a Guided/Manual round trip, `refresh_chromiq_clip_visibility`
and a random `_apply_ui_state` project load). Fifteen invariants are evaluated
after EVERY gesture, including `_collect_guided()`, i.e. what would be built.

30 seeds x 400 gestures = **12,000 gestures**, identical seeds in three trees:

| tree | distinct invariant breaches |
|---|---|
| **HEAD `abff609b`** | I6, I7, I8 |
| **master 7e500e59** | I6, I7, I8 — *the same three* |
| `ca0f639c` (the state the commit fixes) | I6, I7, I8 **+ I1, I3b, I4b** |

The three extra on `ca0f639c` are exactly the reported fault and its shadow:

```
I1  _td_check ticked + visible + DISABLED     <- the box nobody could untick
I3b _dd_check ticked but _td_check enabled
I4b _td_check DISABLED with _dd_check unticked  <- greyed for no reason
```

first hit at seed 0, gesture 15. **The probe is proven to land**: it reproduces
the fault on the broken tree within fifteen gestures and never once on HEAD.

I6/I7/I8 are pre-existing and are recorded separately (T3).

## T3 — CONFIRMED, PRE-EXISTING (identical on master), NOT this commit's:
### three Guided checkbox values reach the built command while their row is
### hidden.

Same walk, same seeds, breach for breach at the same gesture number on HEAD and
on master:

| | what happens | first hit |
|---|---|---|
| **I6** | `_apply_ui_state` applies a stored `double_density: true` on an i1Pro/3Plus **after** the instrument has hidden and cleared the row, so `_collect_guided().double_density` is True with the box hidden. `_SHARED_SETTINGS` applies `instrument` before `double_density` and nothing re-runs `_update_dd_visibility` afterwards. Such a record is writable from Manual, where `-h` is offered on a strip reader. | seed 0, g159 (HEAD **and** master) |
| **I7** | `-P` reaching the build with `_nsl_check` hidden — **false alarm**, triple density forces `-P` by design and the row is hidden on purpose. Excluded in the refined run. | — |
| **I8** | `_lb_check` keeps its value when hidden (that is the approved D-2 behaviour) and `_collect_guided().disable_left_border` then carries `-L` into a ColorMunki / SpectroScan chart. The code's own comment says both instruments ignore `-L`. | seed 0, g58 (HEAD **and** master) |

The only HEAD/master difference the walk found at any breach point is the
`_dd_memory` restore shipped in `2055fca7` and reviewed in an earlier round
(HEAD brings the SpectroScan hexagon tick back, master loses it). That is the
approved feature, not a defect.

**Verdict on T3: not a regression, not this commit's, and not worth holding
4.2.1 for.** I6 is the one worth a look after the release, because it is the
same shape as the fault this branch spent two commits on (a value that reaches
printtarg from a control the user cannot see).

## T4 — CONFIRMED. The walk widened to 20,000 gestures, with Restore Defaults
### and the Guided→Manual transfer added. HEAD is still identical to master,
### and the broken tree is now *worse* than the previous round knew.

`scratchpad/fr2/walk3.py`, 40 seeds x 500 gestures, same seeds in three trees:

| tree | breaches |
|---|---|
| **HEAD `abff609b`** | I6, I8 |
| **master 7e500e59** | I6, I8 — same keys, **same seed and same gesture number** for each |
| `ca0f639c` | I6, I8 **+ I1(dd), I1(td), I2, I3b, I4b** |

The broken tree can also reach **both density boxes ticked at once**
(`I2`, seed 36 gesture 332) and **`_dd_check` ticked and disabled**, neither of
which the previous round found. `abff609b` closes all five.

Gestures now covered: instrument by `activated`, instrument by app
`setCurrentIndex`, all four checkboxes (clicked only when visible AND enabled),
paper, pages, Guided↔Manual round trip, `refresh_chromiq_clip_visibility`,
`_restore_defaults`, `_transfer_guided_to_manual`, and `_apply_ui_state` with a
random stored record. **No caller of `_set_dd_without_remembering` or of
`_shared_set('guided', 'double_density', …)` produces a state on HEAD that
master cannot also reach.** Part A's specific worry — that the newly-unguarded
mutual-exclusion line silently unticks `_td_check` on an app-driven restore —
does happen (`_on_user_picked_instrument` restores `_dd_memory[instr]=True`,
which now clears and greys `_td_check`), but it is self-correcting: the very
next line restores `_td_memory` through `_set_td_without_remembering`, whose
`toggled` handler unticks `_dd_check` and re-enables `_td_check`. The walk
never caught the pair inconsistent.

## T5 — **CONFIRMED, AND IT IS THE ONE REAL DEFECT IN THIS COMMIT.** The
### changelog's *corrected* page-count sentence is still wrong: at the settings
### ChromIQ starts an i1Pro with, printtarg needs **nine** sheets, not seven.

`CHANGELOG.md:23-25`, as `abff609b` rewrote it:

> "…which is what fits 600 patches on four small cards where printtarg needs
> **nine sheets at its own defaults, or seven at the ones ChromIQ starts an
> i1Pro with**."

Measured on the shipped ArgyllCMS 3.5.0 against the bundled
`photocard600.ti1`, page count = number of `x_NN.tif` files produced:

```
-ii1 -p100x150 -t300                      ->  9    printtarg's own defaults (-m6 -M6 -a1.0)
-ii1 -p100x150 -t300 -m6  -M6  -a1.0      ->  9    the same, written out
-ii1 -p100x150 -t300 -m10 -M10 -a0.95     ->  9    <- CHROMIQ'S i1Pro DEFAULTS
-ii1 -p100x150 -t300 -m10      -a0.95     ->  9
-ii1 -p100x150 -t300      -M10 -a0.95     ->  9
-ii1 -p100x150 -t300 -m10 -M10 -a1.0      ->  9
-ii1 -p100x150 -t300           -a0.95     ->  7    printtarg's 6 mm margin + ChromIQ's 0.95 scale
-ii1 -p100x150 -t300 -m10 -M10 -a0.90     ->  7
```

ChromIQ's i1Pro defaults are **margin 10 mm, patch scale 0.95**
(`data/patch_db.py:169` `I1PRO_DEFAULT_PRESET_KEY = "m10_a0.95"`,
`INSTRUMENT_DEFAULT_MARGIN["i1"] = 10`), confirmed by reading them back off a
live `TabChart` on the Guided i1Pro panel: `margin_mm 10, patch_scale 0.95`.
The previous round measured the same table and wrote *"At every default a
reader would reproduce it is **nine**"*.

**The first half of the sentence is right and the second half is wrong.** Seven
only appears at printtarg's 6 mm margin with ChromIQ's 0.95 scale, or at
`-a0.90`, which is not a default of either program. So the sentence replaces
one checkably-wrong number with a different checkably-wrong number, in a stable
release note, about the headline feature.

**The fix is to delete the second clause**: *"…where printtarg needs nine
sheets"*. Nine is true at printtarg's defaults AND at ChromIQ's, which is the
strongest and simplest form of the claim.

(The 648 chart, for completeness, is 5 pages at both: `-ii1 -p130x180 -t300`
and `-ii1 -p130x180 -t300 -m10 -M10 -a0.95` both give 5, 4 at `-a0.90`. The
changelog quotes no number for it.)

## T6 — CONFIRMED, SHOULD-FIX WITH T5. The source comment that fed the wrong
### number was not corrected with the changelog.

`ui/tabs/tab_chart.py:272-275` still reads:

> "…which is what puts 600 patches on four small cards instead of **the seven
> sheets `printtarg -ii1 -p100x150` needs**."

That command, exactly as written, needs **nine** (measured above; it is
printtarg's own defaults). The commit corrected the changelog and left the
comment that will feed the next writer the same wrong figure. Developer-facing
only, so it is a should-fix, not a blocker — but it costs one line and it is in
the file the commit already touched.

### T5, addendum — where "seven" really comes from, and why it is still wrong.

Chased to the bottom, because "seven" is not arbitrary. Real Argyll, verbose,
reading `patches per page` straight out of printtarg:

```
-ii1 -p100x150 -t300 -m10 -M10 -a0.95        ->  70 per page  ->  9 sheets
-ii1 -p100x150 -t300 -m10 -M10 -a0.95 -L     ->  90 per page  ->  7 sheets
-ii1 -p130x180 -t300 -m10 -M10 -a0.95        -> 143 per page
-ii1 -p130x180 -t300 -m10 -M10 -a0.95 -L     -> 169 per page
-ii1 -p60x90   -t300 -m10 -M10 -a0.95 -L     ->  16 per page
```

So "seven" is the count **with the left clip border suppressed (`-L`)** — and
`-L` is **not** what ChromIQ starts an i1Pro with:

```
core/settings.py:29   "chart_disable_left_border": False
live TabChart, fresh settings file, Guided, i1Pro:
    lb ticked = False   disable_left_border = False   margin_mm 10   patch_scale 0.95
```

ChromIQ prints the branded left strip by default, which is exactly the column
that costs the two rows. **At the settings ChromIQ actually starts an i1Pro
with, printtarg needs nine.** Seven needs a box the user has to tick.

The same table **confirms the changelog's other three numbers exactly**: a
10 x 15 cm card holds **90**, a 13 x 18 cm one **169**, a 6 x 9 cm wallet print
**16**, all at `-ii1 -m10 -M10 -a0.95 -L`, which is the geometry the capacity
search works in. Those are right to the patch.

## T7 — VERIFIED. Everything else in the rewritten `## v4.2.1` section is
### accurate, and it renders.

| claim | checked how | verdict |
|---|---|---|
| 600 patches, four 10 x 15 cm cards | `NUMBER_OF_SETS 600` in `photocard600.ti1`; `photocard600_01..04.tif` | ✅ |
| 648 patches, three 13 x 18 cm cards | `NUMBER_OF_SETS 648`; `photocard648_01..03.tif` | ✅ |
| "the other **nine** by Pharmacist charts" | `PREBUILT_PRESETS` has 11 entries, 2 of them the new ones | ✅ |
| "the **eleven** bundled by Pharmacist charts" (Documentation) | same 11, and 11 leaf folders under `assets/charts/pharmacist` | ✅ |
| 443 → **90 / 169 / 16** | real printtarg, above | ✅ exact |
| "every paper ChromIQ already had a measurement for is unchanged to the patch" | `tests/test_capacity_search_reaches_a_small_sheet.py`, 14 passed | ✅ |
| "one case still open: a sheet too small to hold even one patch" | `workflow/chart_creator.py:2170` logs exactly that and still returns a number | ✅ honest |
| "Projects already carrying the wrong instrument are not repaired: correct the instrument once in Create Chart and it stays" | this is the sentence the previous round's **S18** asked for, and it is now there, in the user's words | ✅ **the round's most useful addition** |
| `scripts/release_notes.py --tag v4.2.1` | rendered, **exit 0**, all four sections present, "2 new or changed things and 4 fixed problems and 1 documentation update" | ✅ |

The lead paragraph still lands under `### 🔧 Fixed` rather than above the
sections. That is the pre-existing `split_sections` quirk the previous round
recorded (S13); **v4.2.0 shipped the same way**, so it is not a regression of
this commit.

**Nothing user-visible from the ten commits is missing.** Cross-checked the
five gaps the previous round listed (S11): the CR30 "readings per second" row,
the pace-panel prose, per-instrument density memory, the CR30 project reopening
as a ColorMunki, and the triple-density `-L` leak. Four are now covered
explicitly. The fifth (the `-L` leak) correctly is **not** mentioned, because
it was introduced and fixed inside this same branch and never shipped, and the
same is true of the stuck box this very commit fixes.

## T8 — **CONFIRMED. THE HEADLINE FINDING OF THIS ROUND. Two of the four lines
### the commit's fix consists of can be DELETED and all 12,010 tests stay
### green — including the new file, and including the state they produce is the
### same "ticked and unclickable" fault the commit exists to remove.**

Twelve mutations of `_update_dd_visibility`, `_on_guided_dd_toggled`,
`_on_guided_td_toggled`, `_remember_td` and the `activated` restore. Each was
applied to `ui/tabs/tab_chart.py`, **proved to land** (anchor unique, old text
gone, new text present, byte count printed, every `__pycache__` removed), then
the new test file and a 708-test `-k` selection were run, then the file was
restored from a byte-for-byte backup (`git status` clean after each).

| # | what was removed | new file (32) | wider (708) |
|---|---|---|---|
| M1 | **the fix reverted** — the early `return` on `_dd_writing` comes back | **5 failed** | 5 failed |
| M2 | `self._td_check.setEnabled(not checked)` | **1 failed** | 1 failed |
| **M3** | **the mutual exclusion in `_on_guided_dd_toggled`** (`if checked and _td_check.isChecked(): setChecked(False)`) | **32 passed** | **708 passed** |
| M4 | `self._dd_check.setEnabled(not checked)` in the TD handler | 1 failed | 1 failed |
| M5 | the `== "CM"` guard in `_remember_td` | 2 failed | 2 failed |
| M6 | the `activated` restore of triple density | 2 failed | 2 failed |
| M7 | the meaning-change clear in `_update_dd_visibility` | 1 failed | 1 failed |
| M8 | the `_dd_writing` guard inverted | 8 failed | 8 failed |
| M9 | the `_td_writing` guard in `_on_guided_td_toggled` | **32 passed** | **708 passed** |
| M10 | `_remember_td()` at hide time in `_update_dd_visibility` | **32 passed** | **708 passed** |
| **M12** | **the mutual exclusion in `_on_guided_td_toggled`** | **32 passed** | **708 passed** |

M1 is the mutation the commit message says turns "five cases red". Confirmed:
exactly 5 failed. That claim is honest.

**M9 and M10 are survivors because the code is dead**, and that is fine: both
paths reach `_remember_td`, whose own guard is `currentData() == "CM"`, at a
moment when the instrument is *not* CM, so they are no-ops. Redundant, not
untested.

**M3 and M12 are the real hole, and they are the two mutual-exclusion lines.**
Run the 20,000-gesture walk with each applied:

```
M3  applied -> I1 _dd_check ticked+visible+DISABLED
               I1 _td_check ticked+visible+DISABLED
               I2 both density boxes ticked
M12 applied -> the same three
```

That is the exact fault class of the commit, reachable in six gestures, with
the whole gate green.

**Why the new invariant test misses it.** `test_no_density_box_is_ever_ticked_
and_unclickable` ticks `_td_check` first and `_dd_check` second at each stop —
the fix the author applied after the first version failed to land. But the tick
is guarded by `isEnabled()`, so once triple density is on, the density box is
disabled and never ticked, and the *other* order — density box ticked while
triple density is already on — is never produced. And none of the seven routes
ever picks the same instrument twice in a row, which is the gesture that
reaches it (`_on_user_picked_instrument` restoring `_dd_memory[instr] = True`
onto a ticked `_td_check`). `test_the_two_density_options_stay_mutually_
exclusive` has the same shape: by the time it ticks `_dd_check`, `_td_check`
has already been unticked two lines above, so the line it means to pin is a
no-op when it runs.

**This is the same weakness the commit message says it already fixed once**,
in a different disguise: the order that cannot reach the fault.

**What would pin it** (fails under M3 and M12, passes on HEAD — verified with
`scratchpad/fr2/repick3.py`): tick the density box on a ColorMunki, let the app
seed the instrument away and back, tick Triple density, then have the person
pick "ColorMunki" again — and assert `_no_stuck_box` and mutual exclusion.

## T9 — **CONFIRMED, HEAD-ONLY, master is clean: re-picking the instrument you
### are already on silently replaces the person's Triple density with Double
### density, and the chart is built that way.**

Found while proving T8. Six gestures, every one of them ordinary, and the app
moves are real ones (a project load; `_apply_ui_state` is used here, not a
synthetic `setCurrentIndex`):

```
1  the person picks ColorMunki
2  ticks "Double density"                     dd on
3  opens a run stored as SpectroScan          dd cleared by the app
4  opens a run stored as ColorMunki           still clear
5  ticks "Triple density"                     td on, dd greyed  -> build triple_density=True
6  opens the instrument list and clicks
   "ColorMunki", the row already showing      <-- td OFF, dd ON, build double_density=True
```

| | step 6 result |
|---|---|
| **HEAD `abff609b`** | **Triple density unticked, Double density ticked, chart built with `-h`** |
| master 7e500e59 | Triple density stays ticked — correct |
| `ca0f639c` | **both ticked, both greyed, unrecoverable** |

The cause: `_dd_memory["CM"]` is set True at step 2 and never cleared, because
the app's clear at step 3 goes through `_set_dd_without_remembering`, and the
person's Triple density tick at step 5 unticks a box that is *already* unticked,
so `_remember_dd_for` never fires. Step 6's `activated` then restores the stale
True, and the mutual exclusion — correctly, by this commit's own rule — throws
away the tick made one gesture earlier.

**Three things make this less than a blocker.** It is not a stuck state:
everything stays clickable and consistent, and one click puts it back. Both
options need the same ColorMunki rig accessory, so the user is not handed a
chart their hardware cannot read. And the gesture ("choose the row already
showing") is one the code elsewhere calls "an easy gesture to make by accident"
rather than a normal one.

**Two things make it worth saying.** It is a regression against master, it is
`docs/design/per_target_settings.md` §4c **D-2** territory (an instrument change
may not overwrite a value they have chosen), and the run's next write files the
substituted value as the run's own answer. And **this commit made it, in the
sense that matters**: the mutual-exclusion line it un-guarded is the line that
performs the substitution. On `ca0f639c` the same gesture produced a stuck pair
instead, which is worse; `abff609b` is a genuine improvement and an incomplete
one.

The clean fix is one line and it belongs where the stale memory is made:
`_set_dd_without_remembering` should clear `_dd_memory[instr]` when the app
clears the box because the option changed meaning, or `_on_user_picked_
instrument` should not restore a density value when `_td_check` is ticked.
Neither is a change I would make the day of a stable tag without Basti's ruling
(it is the same "should the session memory cross a boundary" question the
previous round raised as **S5**).

## T10 — CONFIRMED. Part C: `_lb_check`, `_nsl_check`, the paper combo and the
### pages spin box are clean. No stuck or unreachable control found.

Invariants I9-I14 of the 20,000-gesture walk, evaluated after every gesture on
HEAD and on master, never fired once:

* `_lb_check` / `_nsl_check` ticked-and-disabled: **never** (they are never
  disabled at all — only hidden, which is the D-2 "keep the value" design).
* paper combo empty, or with rows but no selection, or disabled: **never**.
  It is refiltered per instrument (12 rows for an i1Pro, 14 for a SpectroScan,
  15 for a ColorMunki) and always lands on a valid row.
* pages spin disabled, or holding a value outside 1..20: **never**.

The one thing they DO do is keep a value while hidden and let it reach the
build (`I8`, `-L` on a ColorMunki/SpectroScan chart) — pre-existing, identical
on master, and recorded as T3.

## T11 — CONFIRMED ON SCREEN, real window, real popup, real mouse clicks:
### the five gestures now land on the correct, escapable state.

`scratchpad/fr2/drive_five.py`. Real `MainWindow`, shown, cocoa. Instruments
chosen through the **open popup** with the keyboard so Qt emits `activated`;
checkboxes moved with `QTest.mouseClick` on the indicator, so a disabled box
genuinely cannot be moved rather than being trusted not to be. Settings and the
ChromIQ root sandboxed.

```
1 pick ColorMunki        DD tick=False en=True  | TD tick=False en=True  | build td=False
2 CLICK Triple density   DD tick=False en=False | TD tick=True  en=True  | build td=True  -L=True
3 pick SpectroScan       DD tick=False en=True  | TD tick=False en=True  | build td=False
4 CLICK Hexagon patches  DD tick=True  en=True  | TD tick=False en=False | build dd=True
5 pick ColorMunki        DD tick=False en=False | TD tick=True  en=True  | build td=True  -L=True
   STUCK BOXES: none
6 CLICK Triple density   DD tick=False en=True  | TD tick=False en=True  | build td=False -L=False
```

Photographed: `scratchpad/fr2/shots/A5-after-five-gestures-row.png`. Read off
the pixels — **"Double density" greyed and empty, "Triple density" ticked
(solid accent fill) with its label in normal black text and its ⓘ button live.**
The previous round's S16 picture (both greyed, the ticked one drawn as a flat
off-white square with no mark) is gone. A real click at step 6 puts it back and
takes `-L` out of the build with it.

Both shipped drivers were re-run on this tree, on screen, both **0 problems**:
`scripts/drive_cr30_hz_and_density_tick.py` (the CR30 rate cell reads
`<no rate box>`, the other six rows untouched and whole-numbered under de_DE,
the density widget relabels across all four instruments and each keeps its own
answer, `activated` fired 10 times) and
`scripts/drive_a_run_reopens_on_its_own_instrument.py` (Guided instrument
`CR30` against a ColorMunki recipe and a ColorMunki saved default; `-P` and
Triple density both KEPT across a hide).

## T12 — CONFIRMED ON SCREEN: T9 reproduces in the real window with real
### mouse clicks, and it is photographed.

Part B of the same driver, on a second `MainWindow`:

```
5 CLICK Triple density   DD tick=False en=False | TD tick=True  en=True  | build td=True  -L=True
6 pick ColorMunki AGAIN  DD tick=True  en=True  | TD tick=False en=False | build dd=True  -L=False
```

`shots/B5-triple-density-on-row.png` and `shots/B6-after-repick-row.png`: the
accent fill moves from "Triple density" to "Double density" and the greying
swaps with it, from one popup selection of the row that was already showing.
Nothing is stuck; the value is simply not the one the person last chose.

## T13 — CONFIRMED: the owner's settings and projects are untouched.

Checked the VALUE, as CLAUDE.md requires, not just the file:

```
before  defaults read com.chromiq.ChromIQ custom_output_path  ->  (empty)
after   defaults read com.chromiq.ChromIQ custom_output_path  ->  (empty)
defaults export, whole plist, before vs after                 ->  IDENTICAL
git status --porcelain                                        ->  only this report
```

Every mutation in T8 was reverted from a byte-for-byte backup and `git status`
was clean after each one.

## T14 — CONFIRMED, UNCHANGED, AND STILL THE RELEASE BLOCKER: `v4.2.1` is
### already taken.

Not this commit's job, but it is the reason a "SHIP" here would still be wrong,
so it is re-verified rather than assumed:

```
git ls-remote --tags origin | grep 4.2.1
  720dd4d1…  refs/tags/v4.2.1-beta.1
  478c7396…  refs/tags/v4.2.1-beta.1^{}     <- feature/182-compliance-sets
git merge-base --is-ancestor v4.2.1-beta.1 HEAD   ->  NO
core/version.py                                    ->  "4.2.1"
```

The previous round's **S10** stands word for word. Two code bases still call
themselves 4.2.1 and the stable one is the smaller.

## T15 — CONFIRMED. A run's STORED density values are NOT clobbered by the
### newly-unguarded path. All 16 combinations, byte-identical to master.

Part A's sharpest question, answered exhaustively rather than by reading:
session memory (dd, td) x stored record (dd, td), loaded through
`_apply_ui_state` with the memory deliberately made stale first (the person
ticks on a ColorMunki, the APP moves the instrument away, then the run loads),
then the app re-seeds the instrument from the chart.

```
HEAD    16 rows
MASTER  16 rows   -> IDENTICAL, field for field, in both the "after load" and
                     the "after reseed" column
ca0f639c          -> 2 rows come out with Triple density TICKED AND DISABLED
```

The four rows marked CLOBBERED are the input the UI can never write
(`double_density` and `triple_density` both true in one record); the mutual
exclusion resolves them to triple density, and **master does exactly the same
thing**. No new clobbering, no new stuck state, no HEAD-only behaviour.

## T16 — CONFIRMED. Second gate run, identical, after every mutation was
### reverted.

```
QT_QPA_PLATFORM=offscreen pytest --runslow -n auto
12010 passed, 167 skipped, 4 xfailed in 212.42s (0:03:32)      exit 0
```

Two `--runslow` runs on this tree, both green, both exit 0, no worker-down
banner, no `Fatal Python error`, no `Timeout (0:0X:XX)!` dump. The tree is
byte-identical to `abff609b` (`git status --porcelain` shows only this report).

---

# RECOMMENDATION

## SHIP WITH CAVEATS — **the commit itself is good and should go in.** But it
## must not be tagged `v4.2.1`, and two things in it should be corrected first.

`abff609b` does what it says. The fix is right, it is the minimal right fix,
it holds on screen with real mouse clicks, it is identical to master on every
state 20,000 random gestures and 16 exhaustive load combinations can reach, and
the gate is green twice. Nothing in it is a regression.

### What must change before it is tagged

1. **T14 / the previous round's S10 — the version number is still taken.**
   `v4.2.1-beta.1` is a published GitHub pre-release built from
   `feature/182-compliance-sets`, and it is not an ancestor of this branch.
   Tagging `v4.2.1` from here makes the smaller build "Latest" and offers it
   through the updater to the people testing #182. **Basti's decision**: merge
   #182 first and fold both changelog sections, or number this work 4.2.2.
   Nothing in this commit changes that, and nothing in the gate can see it.

2. **T5 — the corrected page count is still wrong.** `CHANGELOG.md:24-25` says
   printtarg needs "nine sheets at its own defaults, **or seven at the ones
   ChromIQ starts an i1Pro with**". Measured on real Argyll 3.5.0: at ChromIQ's
   own i1Pro settings (`-m10 -M10 -a0.95`, left border NOT suppressed, which is
   `core/settings.py:29`) it is **nine**. Seven needs `-L`, which the user has
   to tick. **Delete the second clause.** Nine is true at both defaults, which
   is the stronger claim anyway.

3. **T6 — the source comment that produced the wrong number was not fixed with
   it.** `ui/tabs/tab_chart.py:273-275` still says "the seven sheets
   `printtarg -ii1 -p100x150` needs". That command needs nine.

### What should be added, and is cheap

4. **T8 — two of the four lines of the fix are unpinned.** Deleting either
   mutual-exclusion line (`_on_guided_dd_toggled` or `_on_guided_td_toggled`)
   leaves all 12,010 tests green while producing both density boxes ticked, and
   both ticked-and-disabled, in six gestures. The new invariant test has the
   same order-blindness its author already fixed once: it ticks triple density
   first, and `isEnabled()` then stops it ever ticking the density box on top.
   **One test closes it**: tick the density box on a ColorMunki, let the app
   seed the instrument away and back, tick Triple density, then pick
   "ColorMunki" again, and assert the pair. Verified to fail under both
   mutations and pass on HEAD.

### What is worth a ruling, not a fix today

5. **T9 — re-picking the instrument already showing swaps the person's Triple
   density for Double density**, on screen, with the chart built that way. It
   is HEAD-only (master keeps the tick) and it is `per_target_settings.md`
   §4c D-2 territory. It is *far* better than what `ca0f639c` did with the same
   gesture (both boxes ticked and greyed), it is one click to undo, and both
   options need the same rig accessory. It is the same "how far should the
   session memory reach" question the previous round raised as **S5** and it
   should be answered once, by Basti, rather than patched the day of a tag.

### Still open from the previous round, and not touched by this commit

* **S8** — `tab_print.py:1609`'s modal tells the user borderless "cannot be
  turned off" and that "the chart's white margins are made for that", in red,
  with Cancel as the default button, contradicting the instruction printed on
  these two sheets. One clause fixes it.
* **S14** — no `### Known issues` line for the `engine_recipe` defect the
  `xfail(strict=True)` documents. Shipping it is fine; shipping it silently is
  not.
* **S7** — "wiith", baked into all three pages of the 13 x 18 raster.
* **S9** — 0.564 mm spacers, on paper, read with an i1Pro. Still nobody has.
* **S15** — `THIRD-PARTY-NOTICES.md` says 331 files; it is 330.

### What I could not verify

* **A printed sheet, on paper, read with an i1Pro.** Unchanged from the
  previous round and still the honest limit of any review of this branch.
* **Windows and Linux.** Everything here is macOS, cocoa and offscreen.
* **Whether Basti wants the density memory to cross an app-driven instrument
  change at all** (T9 / S5). That is a ruling.
* **The preset-application path** was not driven end to end in this round; it
  reaches the density boxes only through the instrument mirror, which the
  20,000-gesture walk covers as `APPMOVE`, but a built-in preset that also
  generates a chart was not exercised here.

### What is genuinely good, and should be said

The fix is one `if` and it is in the right place: only `_remember_dd_for` cares
who moved the widget, and the commit says so in the code. The five-gesture
reproduction is kept as a test in the shape it was found. The commit message
volunteers that the first version of its own test stayed green under the
mutation it was written for — and that mutation, run here, does turn exactly
five cases red, so the claim is checkable and true. The changelog now covers
all four fixes including both faults the user reported himself, and it carries
the sentence the previous round asked for about projects that are not repaired.

---

## T9, ADDENDUM — re-verified on a CLEAN `abff609b` worktree after the
### coordinator could not reproduce it. **It stands.** The difference is one
### step, and it is the step that decides whether the memory is written.

Runnable probes, both offscreen and deterministic:

* `scratchpad/fr2/t9_probe.py` — shortest form, prints `_dd_memory` at every
  step, **exits 1 when the swap happens**.
* `scratchpad/fr2/t9_sidebyside.py` — the coordinator's sequence and mine, in
  the same process, so the divergence is visible in one output.
* `scratchpad/fr2/drive_five.py` part B — the same thing on screen, real popup,
  real mouse clicks, photographed as `shots/B5-…` and `shots/B6-…`.

Measured on `abff609b` in a clean worktree
(`scratchpad/clean-abff609b`, `git rev-parse HEAD = abff609b53…`), on master
`7e500e59`, and on the working tree carrying the coordinator's in-flight edits:

| tree | swap? |
|---|---|
| master 7e500e59 | **no** (`_dd_memory` does not exist there at all) |
| **`abff609b`, clean worktree** | **YES** (probe exit 1) |
| working tree with the T5/T6/T8 edits | YES (probe exit 1) |

### The coordinator's reasoning is right, and it does not cover my sequence

Their argument: ticking triple density calls `_dd_check.setChecked(False)`,
which fires `_on_guided_dd_toggled`, which files `_dd_memory["CM"] = False`.

True — **but only when `_dd_check` is actually True at that moment.** Setting an
already-unticked box to False emits no `toggled`, so the handler never runs and
`_remember_dd_for` is never reached. In their sequence the box is unticked *by
hand* first, which does emit. In mine the **app** clears it, through
`_set_dd_without_remembering`, which is designed not to write the memory. The
memory is then stale and nothing afterwards can correct it.

```
A. THEIR SEQUENCE                              _dd_memory
  1 pick CM                                    {}
  2 tick Double density                        {'CM': True}
  3 pick CM again                              {'CM': True}
  4 UNTICK Double density BY HAND              {'CM': False}   <- the handler runs
  5 tick Triple density                        {'CM': False}
  6 pick CM again                              {'CM': False}   -> swapped: False

B. MINE                                        _dd_memory
  1 pick CM                                    {}
  2 tick Double density                        {'CM': True}
  3 THE APP moves the instrument to SS         {'CM': True}    <- THE DIFFERENCE
  4 THE APP moves it back to CM                {'CM': True}
  5 tick Triple density (dd already False,
    so setChecked(False) emits NOTHING)        {'CM': True}    <- stale
  6 pick CM again                              {'CM': True}    -> swapped: True
```

At step 6 `_td_memory` also goes True -> False, so the person's triple-density
answer is destroyed in the memory as well as on screen.

### Answers to the four questions, in order

1. **Yes — this is case 1.** The state is `_dd_memory["CM"] == True` with
   `_td_check` ticked, and it is reached by an **app-driven instrument change
   between the two ticks**. `app_moves` in the probe is a bare `setCurrentIndex`
   (what `test_the_app_moving_the_instrument_never_restores_anything` calls
   `_app_moves_instrument_to`); variant C of the side-by-side does the same
   thing with two real `_apply_ui_state` project loads and swaps identically.
2. **No, it does not need a real popup.** It reproduces offscreen with exactly
   `setCurrentIndex` + `currentIndexChanged.emit` + `activated.emit`, which is
   what you emit. It ALSO reproduces on screen with a real popup pick and real
   `QTest.mouseClick`s, which is what the photographs show.
3. **Measured on `abff609b`**, in a clean worktree, offscreen and on screen.
   Not `ca0f639c` — on `ca0f639c` the same gestures give the *worse* outcome
   (both boxes ticked and greyed), which is the fault the commit fixes.
4. **Not withdrawn.**

### Unchanged from the original T9: this is a ruling, not a same-day fix

One click undoes it, nothing is stuck, and both options need the same ColorMunki
rig. It is a regression against master and §4c D-2 territory, and it belongs
with **S5** as one question for Basti about how far the session memory reaches.

## T17 — MINOR, in the coordinator's in-flight edit: the new comment names the
### wrong settings key.

`ui/tabs/tab_chart.py` (working tree) now says *"ChromIQ does not add it:
`chart_left_clip_info` ships False"*. The key that drives `-L` in Guided is
**`chart_disable_left_border`** (`core/settings.py:29`, read at
`tab_chart.py:19705` into `_lb_check`). `chart_left_clip_info`
(`core/settings.py:32`) is the Manual panel's clip-info checkbox and is a
different thing. Both happen to ship False, so the conclusion is right and the
citation is not.
