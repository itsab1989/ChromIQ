# CR30 "100 Hz" in Preferences → Measurement — investigation

Report (owner): "in preferences under the measurement tab the cr30 is said to
have 100Hz. I think you measured more like 3Hz and it is patch by patch only
anyway"

## H1 — CONFIRMED: the 100.0 value, and the code's own comment on it

`core/measure_pace.py:343`

```
    "cr30":           (100.0, None),
```

in `MODEL_DEFAULTS = {model key: (sample_hz, min samples per patch)}`
(`core/measure_pace.py:319-344`). The tuple is (sample_hz, min_samples).

The comment immediately above it (`core/measure_pace.py:332-342`) already says
the number is **arbitrary**, in the source, in these words:

> The CR30 is placed on one patch by hand and triggered by its own button
> (#159). Like the SpectroScan there is no swipe, so the threshold is None
> (shown as "Off") and no pace warning is ever raised. The rate is inert in
> both directions: nothing subscribes to patch events for pace
> (tab_measure.py:1016-1022 — the pace model is wired to strip_measured
> only, and a CR30 never emits a strip), and the CR30 does not stream
> samples at all. **It is 100.0 rather than 0 or 1 purely so the Preferences
> spinbox shows the shipped default instead of silently clamping it to the
> bottom of SAMPLE_HZ_RANGE (10-500).** The row exists so that
> _pace_config's unknown-instrument fallback — the i1Pro's (100.0, 20) —
> can never be applied to a CR30 chart.

So 100.0 is (a) a placeholder and (b) numerically the i1Pro Rev A's rate
(`core/measure_pace.py:325`, `"i1pro": (100.0, 20)`).

`SAMPLE_HZ_RANGE = (10.0, 500.0)` — `core/measure_pace.py:384`. The spinbox
cannot express 0 or 3 Hz... 3 is also below the 10 Hz floor.

`ESTIMATE_PATCHES["cr30"] = None` — `core/measure_pace.py:364` — "no strips at
all — shown as N/A (#159)".

## H2 — CONFIRMED: what the UI actually says on screen

Preferences → Measurement, `ui/dialogs/settings_dialog.py::_build_measurement_tab`
(line 3439). The table has one row per instrument, columns:

- `ui/dialogs/settings_dialog.py:3525` — "Instrument"
- `ui/dialogs/settings_dialog.py:3527` — **"Readings per second"** (the Hz column)
- `ui/dialogs/settings_dialog.py:3532` — "Patches per strip"
- `ui/dialogs/settings_dialog.py:3534` — "Minimum readings per patch"
- `ui/dialogs/settings_dialog.py:3538` — "Min. strip reading speed"

CR30 row label: `ui/dialogs/settings_dialog.py:3546` — `tr("CR30 (patch by patch)")`.

The spin box: `settings_dialog.py:3556-3567`
```
hz = NoScrollDoubleSpinBox(self)
hz.setRange(*SAMPLE_HZ_RANGE)          # 3557 -> 10..500
hz.setDecimals(0)                      # 3558
hz.setSuffix(tr(" Hz"))                # 3559  <-- the "Hz" the report names
hz.setValue(float(self._settings.get(f"pace_sample_hz_{key}", hz_default)
                  or hz_default))      # 3561-3562  <-- CR30 default = 100
```
So the CR30 row reads literally **"100 Hz"**, "N/A" patches per strip, "Off"
minimum.

Spin box tooltip, `settings_dialog.py:3563-3567` — applied to EVERY row
including the CR30, and it is the false claim:

> "How many readings this instrument takes each second, from its
> specification. ChromIQ uses it to work out how many readings a patch received
> from how long it took."

Tab intro, `settings_dialog.py:3475-3481`, also unconditional:

> "Every instrument takes a fixed number of readings per second, so how long a
> patch takes decides how many readings it gets."

The CR30's own ⓘ help (`core/measure_pace.py:689-703`) DOES say the row is
inert: "This whole row is inert for the CR30: ChromIQ judges reading pace per
strip, and a CR30 measurement never produces one. The row is shown so you can
see that, rather than wonder which figures are being applied behind your back."
It never mentions 100 Hz, and it never says the 100 is meaningless.

`_calculation_note` (`core/measure_pace.py:512-547`) takes its `min_samples`/
`patches`-are-falsy branch for the CR30, so the ⓘ ends with "On this row the
minimum is Off and no strip length applies, so nothing is judged and no speed
is shown." It never prints the 100.

## H3 — CONFIRMED: what the Hz value DOES (and does not do)

Only consumer of a stored `pace_sample_hz_*`:
`ui/tabs/tab_measure.py:4866-4917` `_pace_config()`, feeding
`PaceTracker` (`tab_measure.py:4919-4930`), which is driven by exactly one
signal:

`ui/tabs/tab_measure.py:1080` — `self._manager.strip_measured.connect(self._report_strip_pace)`

and the comment at `tab_measure.py:1074-1078` states the rule (Knut, #131
2026-07-26): "reading pace is judged per STRIP, not per patch ... nothing
subscribes to patch events for pace any more."

`Cr30SpotManager` (`workflow/cr30_spot_manager.py:66-94`) declares its complete
signal surface and **has no `strip_measured` signal at all** (nor
`patch_measured`). So `_report_strip_pace` can never fire on a CR30 path.

Also, `_pace_config` short-circuits: `tab_measure.py:4911-4914` — when
`min_samples <= 0` it returns `PaceConfig(min_samples=0, sample_hz=0.0, ...)`,
DISCARDING the configured Hz entirely. The CR30's shipped min_samples is `None`
-> 0 -> "Off", so even if a CR30 did emit a strip the 100 would be thrown away.

**The 100 Hz is dead twice over on the CR30 path.** CONFIRMED by reading; the
only place it is ever rendered is the spin box itself.

## H4 — CONFIRMED: where the 100 Hz came from. One commit, and it is a placeholder.

`git log -S'cr30' -- core/measure_pace.py` returns exactly ONE commit:

```
368087e7  cr30: UI registrations — layout panel, preferences, margins, pace,
          and the FWA gate
          itsab1989 <itsab1989@users.noreply.github.com>
          Fri Aug 28 19:17:03 2026 +0200
```

That commit ADDS the `"cr30": (100.0, None)` line together with the comment
quoted in H1 — so the "purely so the spinbox shows the shipped default instead
of silently clamping it to the bottom of SAMPLE_HZ_RANGE (10-500)" reasoning is
the ORIGINAL justification, present from the first line of code. There is no
earlier value, no measurement behind it, and no other commit ever touched it.

The number 100.0 is the i1Pro Rev A's rate (`core/measure_pace.py:325`), i.e. a
copied default. It is NOT a CR30 measurement. CONFIRMED.

(The same commit's CR30 ⓘ text originally said "about 475 patches"; it now says
"about 345 patches" — a later edit. The 100.0 was never revisited.)

## H5 — CONFIRMED: the CR30's real rate was MEASURED, and it is 3.18 readings/s

Separate repo: **`/Users/Basti/develop/chromiq-cr30-research`** (the CR30
reverse-engineering repo).

Experiment **EXP-018** — "measurement rate, and does a reading follow a moving
head?", `chromiq-cr30-research/EXPERIMENTS.md:612-624`:

> USB: **3.18 readings/s**, cycle **315 ms**, range 313.8–317.4 ms over 78
> cycles, 0 failures. **The regularity means it is the DEVICE's measurement
> time and cannot be improved.** Held still: consecutive readings differ by
> ΔE 0.0037 (median). Drawn across patches: ΔE 0.27 median, 6.81 max — 74x the
> noise, so readings do follow the surface.

Machine-readable evidence, `chromiq-cr30-research/captures/public/EXP-018-rate-usb.json`
(dated `2026-08-29T18:31:31Z`, transport `usb`), both phases:

| phase | cycles | seconds | per_second | median_ms | fastest_ms | slowest_ms | errors |
|---|---|---|---|---|---|---|---|
| A (held still) | 39 | 12.27 | **3.18** | **314.6** | 313.6 | 317.4 | 0 |
| B (drawn across patches) | 39 | 12.27 | **3.18** | — | — | — | 0 |

The file's own `verdict` field:

> "At 3.2 readings a second, a 26-patch strip drawn over eight seconds gets
> about 1.0 readings per patch. Fewer than ~2 and a patch boundary cannot be
> placed; fewer than ~1 and patches are missed outright."

Raw copy: `chromiq-cr30-research/captures/raw/EXP-018-rate-usb.json`.

**So the owner's recollection is exactly right: ~3 Hz, not 100 Hz.** The
measurement is dated 2026-08-29 — the DAY AFTER commit `368087e7` (2026-08-28)
wrote 100.0 into `MODEL_DEFAULTS`. Nobody went back to the Preferences value.

Corroborating earlier note, `chromiq-cr30-research/INTEGRATION.md:275-279`:
"a fact nobody has measured: the CR30's real per-reading time ... If a reading
takes ~1 s ... a 400-patch chart is ~7 minutes". EXP-018 then measured it at
315 ms of *device* time per reading (the ~1 s figure was the pre-measurement
guess, and it is the per-reading DEVICE time; a human placement + press is the
"roughly two seconds" ChromIQ's own ⓘ quotes).

`chromiq-cr30-research/PROTOCOL.md:170-179` adds: **no sensor-parameter command
exists in ten vendor sessions**, so "there is no known knob for integration time
or averaging" — the 315 ms cannot be configured away.

## H6 — CONFIRMED: ChromIQ's OWN docs already carry the 3.18 figure, and name measure_pace

`docs/cr30_reports/18_strip_design.md:143` (a ChromIQ-repo design report):

> | Live pace feedback | YES | `core/measure_pace.py` — built for exactly
> "samples/patch ≈ time × rate" (#131 Phase 2); **CR30's rate is a measured
> constant, 3.18/s** |

Also `docs/cr30_reports/18_strip_design.md:22-31, 49-54, 91, 150, 167, 211,
270` all work in "0.315 s" / "3.18/s" / "315 ms cycle" / "3.18 Hz".
`docs/cr30_reports/19_design5.md:200` — "the 315 ms cycle is the budget".

So the correct number is written down in this repo, in a document that names the
very module holding the 100. Nobody joined them up. CONFIRMED.

## H7 — CONFIRMED: a CR30 chart is FORCED patch-by-patch, so a strip is impossible

`ui/tabs/tab_measure.py:1410-1419` (`_patch_by_patch`): "A CR30 chart is always
True... Basti's ruling is that the user cannot deselect it, in either module."
`_apply_cr30_pbp_lock` (`tab_measure.py:1584+`) ticks and disables the checkbox.

`ui/tabs/tab_measure.py:1476-1487` `_refresh_calm_subtext` replaces "Scan each
strip with a slow, steady motion." with "Rest the instrument on the highlighted
patch and press its button." for a CR30 chart.

So no strip is ever produced -> `strip_measured` never fires -> the pace tracker
never runs -> the CR30's Hz row is unreachable. This is the report's "it is
patch by patch only anyway", confirmed in code.

## H8 — CONFIRMED: there is already a SHIPPED pattern for exactly this problem

`ui/tabs/tab_measure.py:1470` —
`CR30_DEAD_OPTIONS = ("highres", "filter", "tolerance", "xrga")`
and `_apply_cr30_dead_options` (`tab_measure.py:1539-1581`), which disables (never
unticks) those chartread options on a CR30 chart with the tooltip
(`tab_measure.py:1550-1554`):

> "Your CR30 cannot use this. ChromIQ reads this instrument itself, so
> ArgyllCMS never opens it and there is nothing here for this setting to
> change. Your choice is remembered for other instruments."

The Preferences pace row is the same class of dead control and was NOT given the
same treatment. Note "tolerance" (chartread `-T`) is already in that list —
the pace Hz box is its Preferences-side twin.

## H9 — CONFIRMED: translation reach

`data/i18n/` holds **12** non-English catalogues (de, es, fr, it, ja, nl, no, pl,
pt, ru, sv, zh_CN). Each already contains **5** of the strings involved:
` Hz`, `CR30 (patch by patch)`, the CR30 ⓘ body, the Hz spin-box tooltip
("How many readings this instrument takes each second, from its
specification..."), and the tab note ("Every instrument takes a fixed number of
readings per second..."). So any wording change is 12 catalogues x however many
strings are touched, plus `scripts/i18n_extract.py --missing <code>` and
`tests/test_i18n.py`.

## H10 — CONFIRMED ON SCREEN: what the CR30 row renders, and that 3.18 cannot be typed

Rendered the real `SettingsDialog` offscreen (Fusion, settings sandboxed to a
scratch `.ini` via `CHROMIQ_SETTINGS_FILE`, so the real preferences were not
touched):

```
CR30 Hz box text : '100 Hz'
CR30 Hz value    : 100.0
CR30 patches text: 'N/A'
CR30 min text    : 'Off'
CR30 estimate lbl: 'no limit'
Hz tooltip       : 'How many readings this instrument takes each second, from
                    its specification. ChromIQ uses it to work out how many
                    readings a patch received from how long it took.'
Hz enabled       : True
--- try setting 3.18 ---
after setValue(3.18): '10 Hz'  ->  10.0
```

Two things this settles:

1. The on-screen claim is literally **"CR30 (patch by patch) | 100 Hz"**, with
   an enabled, editable, tooltipped spin box asserting it is the instrument's
   specification. The report is accurate.
2. **A one-line value change to 3.18 would NOT work.** `SAMPLE_HZ_RANGE =
   (10.0, 500.0)` (`core/measure_pace.py:384`) clamps it to 10, and
   `hz.setDecimals(0)` (`settings_dialog.py:3558`) would round it anyway. The
   row would then say "10 Hz", which is a second false number.

`_refresh_pace_estimates` (`settings_dialog.py:3729-3755`) shows "no limit" for
the CR30 because `mn <= 0`, so nothing is computed from the 100 anywhere.

## H11 — CONFIRMED: the wrong value is PERSISTED on any Preferences save

`ui/dialogs/settings_dialog.py:5824-5825`:
```
for _key, _hz in self._pace_hz.items():
    s.set(f"pace_sample_hz_{_key}", float(_hz.value()))
```
The loop covers every row including `cr30`, so the first time a user presses
Save on ANY Preferences tab, `pace_sample_hz_cr30 = 100.0` is written into their
settings store. `core/settings.py:274-275` seeds only `pace_sample_hz_i1pro`
and `pace_sample_hz_colormunki`, so there is no CR30 entry in DEFAULTS.
Consequence: a code-only default change will not reach anyone who has already
saved (the project's own "changing a default needs a migration" rule).

## H12 — CONFIRMED: no test pins the 100

`tests/test_cr30_registration.py:388-400`
(`test_the_pace_row_exists_and_raises_no_warning`) asserts only
`min_samples is None`, `defaults_for("cr30") != defaults_for(None)`,
`estimate_patches_for("cr30") is None`, and that the ⓘ exists. It never asserts
the Hz. `tests/test_measure_pace.py:198-199` pins `SAMPLE_HZ_RANGE == (10.0,
500.0)` — that test WOULD have to change if the range moved.

## H13 — CONFIRMED: no design specification covers this row

`docs/design/` (13 documents) contains no coverage of Preferences → Measurement
or of `core/measure_pace.py`. Grepping the folder for "pace" returns only
unrelated hits. So no spec-review obligation is triggered by changing this row.
(New user-facing message text still goes through §M of
`unified_measurement_management.md` if it is a measurement message; a
Preferences tooltip is not one, but `tests/test_message_catalogue.py` should be
run to confirm.)

---

# RECOMMENDATION (analysis only — nothing implemented)

## The honest fix: do not offer a rate for the CR30 at all

Changing 100 to 3 would replace a false number with a true-but-still-meaningless
one, on a control that does nothing, next to a tooltip that says the app uses it
(it does not) and a column header that says "Readings per second" (the CR30 does
not stream). It also cannot be entered (H10). The CR30 row should keep its ⓘ and
its label and lose the editable claim, exactly as `CR30_DEAD_OPTIONS` already
does on the Measure tab (H8).

### Preferred: option A — grey the row, state the measured fact in the ⓘ

1. `ui/dialogs/settings_dialog.py:3556-3567` — after building `hz`, disable it
   for `key == "cr30"` (`hz.setEnabled(False)`) and give it the CR30's own
   tooltip instead of the generic one at `:3563-3567`. Follow
   `_apply_cr30_dead_options`'s doctrine: **disable, never blank**.
   Same for `pp` (`:3569-3583`) and `mn` (`:3585-3600`), which already show
   "N/A" and "Off" but are equally editable and equally inert.
2. `core/measure_pace.py:343` — the value itself. Options:
   - leave `100.0` but stop showing it (weakest: the number is still in the
     store, and `pace_sample_hz_cr30 = 100.0` still gets written on save), or
   - set it to `3.18` and widen `SAMPLE_HZ_RANGE` / raise `setDecimals` so a
     disabled box can DISPLAY "3.2 Hz" honestly. `SAMPLE_HZ_RANGE = (10.0,
     500.0)` at `core/measure_pace.py:384` and `hz.setDecimals(0)` at
     `settings_dialog.py:3558` both block this today, and
     `tests/test_measure_pace.py:198-199` pins the range.
   My recommendation: **3.18 with the range lowered and one decimal**, so the
   row shows a fact the research repo can back, greyed, with the ⓘ explaining
   it changes nothing.
3. `core/measure_pace.py:689-703` — the CR30 ⓘ. Add the measured figure and its
   source: "The CR30 takes one reading every 315 ms (3.2 a second, measured on
   this instrument), and that is the device's own measurement time, not a
   sampling rate you can spend on a swipe." Replace nothing that is already
   correct; the "this whole row is inert" paragraph stays.
4. `ui/dialogs/settings_dialog.py:3475-3481` — the tab note ("Every instrument
   takes a fixed number of readings per second...") is now false for one of its
   seven rows. Either qualify it or leave it and rely on the greyed row plus ⓘ.
5. `ui/dialogs/settings_dialog.py:5824-5825` — the save loop. Consider skipping
   `cr30` so a dead value is never persisted, and/or adding a settings
   migration for anyone who already saved `pace_sample_hz_cr30 = 100.0`
   (H11; the project's own rule is that changing a default needs a migration).
6. `core/settings.py:274-275` — if a CR30 key is to have a DEFAULTS entry, this
   is where it goes.

### Option B — remove the CR30 row from the table entirely

Cheaper, and defensible: the row exists only to display inert values. But
`core/measure_pace.py:332-342` argues the row is there so `_pace_config`'s
i1Pro fallback can never be applied to a CR30 chart, and the ⓘ says it is shown
"rather than wonder which figures are being applied behind your back". Removing
it would need `MODEL_DEFAULTS["cr30"]` kept for the fallback while the table
skips the row — i.e. the table stops being a straight render of
`MODEL_DEFAULTS` (`settings_dialog.py:3552-3553`). Knut's/Basti's call.

### Files that would change (option A)

| File:line | What |
|---|---|
| `core/measure_pace.py:343` | the 100.0 -> 3.18 (or left, per the choice above) |
| `core/measure_pace.py:384` | `SAMPLE_HZ_RANGE` lower bound, only if 3.18 is to display |
| `core/measure_pace.py:689-703` | the CR30 ⓘ text: add the measured fact + source |
| `ui/dialogs/settings_dialog.py:3556-3567` | disable the Hz box for cr30; CR30-specific tooltip |
| `ui/dialogs/settings_dialog.py:3558` | `setDecimals(0)` -> 1, only if 3.18 is to display |
| `ui/dialogs/settings_dialog.py:3569-3600` | same treatment for the patches/min boxes |
| `ui/dialogs/settings_dialog.py:3475-3481` | the tab note, if it is to be qualified |
| `ui/dialogs/settings_dialog.py:5824-5825` | do not persist a dead cr30 rate |
| `core/settings.py:274-275` | DEFAULTS entry / migration, if added |
| `tests/test_measure_pace.py:198-199` | pins `SAMPLE_HZ_RANGE`; must move with it |
| `tests/test_cr30_registration.py:388-400` | the natural home for a new assertion that the row is inert/greyed |

### Translations

12 catalogues: `data/i18n/{de,es,fr,it,ja,nl,no,pl,pt,ru,sv,zh_CN}.json` (H9).
Each already holds the 5 strings in play. Any changed English string is a NEW
key, so all 12 need the new translation; `python scripts/i18n_extract.py
--missing de` (etc.) and `tests/test_i18n.py` enforce it. Watch the em-dash rule
(`tests/test_no_new_em_dash_in_user_facing_text.py`) — the current CR30 ⓘ body
contains em dashes and is in the frozen baseline, so touching it means cleaning
its dashes.

# SUMMARY

**What the UI says.** Preferences → Measurement → Per instrument, row "CR30
(patch by patch)": an enabled spin box reading **"100 Hz"** under the column
"Readings per second", with the tooltip "How many readings this instrument
takes each second, **from its specification**." Verified by rendering the real
dialog (H10).

**What is true.** The CR30's measured rate is **3.18 readings per second**
(315 ms per reading, range 313.6-317.4 ms, 78 cycles, 0 errors) — EXP-018 in
`/Users/Basti/develop/chromiq-cr30-research`, evidence file
`captures/public/EXP-018-rate-usb.json`. The research repo's own conclusion is
that "the regularity means it is the DEVICE's measurement time and cannot be
improved", and `PROTOCOL.md` §5 records that no integration-time or averaging
command exists in ten vendor sessions. So it is not a sampling rate in the sense
the column means at all: it is how long one press takes.

**Where 100 came from.** One commit, `368087e7` (2026-08-28), which introduced
the row and said in its own comment that 100.0 was chosen "purely so the
Preferences spinbox shows the shipped default instead of silently clamping it to
the bottom of SAMPLE_HZ_RANGE". It is the i1Pro Rev A's rate, copied. The
measurement that contradicts it (EXP-018) was taken the NEXT DAY, and
`docs/cr30_reports/18_strip_design.md:143` in this very repo records "CR30's
rate is a measured constant, 3.18/s" while naming `core/measure_pace.py`.

**Is the setting meaningful for a CR30?** No. It is dead twice: the pace tracker
is driven only by `strip_measured` (`ui/tabs/tab_measure.py:1080`), which
`Cr30SpotManager` does not emit and a CR30 chart cannot produce (patch-by-patch
is forced, `tab_measure.py:1410-1419`); and even if it did, `_pace_config`
throws the Hz away whenever `min_samples <= 0`, which is the CR30's shipped
state (`tab_measure.py:4911-4914`).

**Recommendation.** Do not simply retype the number. Grey the whole CR30 row the
way `CR30_DEAD_OPTIONS` already greys the chartread options it cannot honour,
set the value to the measured 3.18 (which needs `SAMPLE_HZ_RANGE` and
`setDecimals` widened, plus their test), and put the measured fact and its
source in the CR30's ⓘ. Stop persisting `pace_sample_hz_cr30`, and migrate
anyone who already has 100.0 stored.

**Not verified.** (a) Whether the 3.18 rate holds over Bluetooth — EXP-018 is
USB only, and no BLE rate experiment exists in `captures/public/`. (b) Whether
a real user's settings store already contains `pace_sample_hz_cr30 = 100.0` — I
did not read the owner's live preferences. (c) Whether Basti/Knut would prefer
option B (drop the row) over option A (grey it); that is a design call, not
mine.
