# Adversarial challenge — CR30 "100 Hz" (defect 1) and Double density (defect 2)

Reviewer: adversarial round, 2026-09-08. Nothing implemented.
Status legend: **CONFIRMED** = reproduced/ran it. **SUSPECTED** = read only.

## D1 — CONFIRMED: setting the default to 3.18 WITHOUT widening the range writes a THIRD false number, 10.0, and it is unmigratable

Ran the real `SettingsDialog` offscreen (Fusion, `CHROMIQ_SETTINGS_FILE` sandboxed),
with `MODEL_DEFAULTS["cr30"]` monkeypatched to `(3.18, None)` and the stored
`pace_sample_hz_cr30` removed (i.e. migration has already run):

```
BASELINE cr30 hz box: '100 Hz' 100.0 enabled= True
BASELINE decimals: 0 range: 10.0 500.0

AFTER default=3.18 but range/decimals UNCHANGED:
  text: '10 Hz' value: 10.0
  what Save would persist: 10.0
```

`ui/dialogs/settings_dialog.py:3557` `hz.setRange(*SAMPLE_HZ_RANGE)` clamps 3.18
up to 10.0 and `:3558` `setDecimals(0)` rounds it; `:5825` then persists
`pace_sample_hz_cr30 = 10.0` on the next Save.

**Why this is worse than the bug being fixed.** 10.0 is not a shipped default,
so it can never be added to `_SUPERSEDED_DEFAULTS`
(`core/settings.py:788-822`) — that table only drops a value EQUAL to an old
default. A user who lands on 10.0 is stuck with it for good, and no future
schema bump can help without also destroying a deliberately-typed 10.

**Consequence for the fix order.** `SAMPLE_HZ_RANGE` and `setDecimals` are not
optional cosmetics that can be deferred to a follow-up. If the value change
ships without them, the release is strictly worse than today. They must land in
the SAME commit, and the value change must not be merged first.

## D2 — CONFIRMED: the machine's locale is de_DE, so raising `setDecimals` puts a COMMA in the Hz column, on every row

```
QLocale system: de_DE   decimalPoint: ','
...
AFTER range lowered to 1.0 (decimals raised):
  cr30 text: '3,00 Hz'
```

`setDecimals(0)` at `ui/dialogs/settings_dialog.py:3558` is unconditional and
shared by all seven rows. Raising it to 1 or 2 to express 3.18 turns
`100 Hz` into `100,0 Hz` / `100,00 Hz` for the i1Pro, i1Pro 2, i1Pro 3,
i1Pro 3 Plus, ColorMunki and SpectroScan as well — six rows churned to fix one,
and the first locale-dependent decimal separator ever shown in that table.

**What the fix must do instead:** set decimals PER ROW
(`hz.setDecimals(2 if key == "cr30" else 0)`), or drop the spin box for the
CR30 entirely (see D6). Note also that `setValue` rounds to the CURRENT
`decimals`, so the per-row `setDecimals` must precede `:3561` `setValue` — it
does today, but any reordering silently reintroduces D1.

## D3 — CONFIRMED: the CR30 ⓘ carries TWO more false claims that the proposed fix does not touch

`explanation_for("cr30")` (`core/measure_pace.py:689-703`) appends
`_calculation_note(key)` (`core/measure_pace.py:512-547`), whose SHARED head is
rendered verbatim on the CR30 row. Rendered output:

> •  Readings per second is the instrument's own sampling rate, from its
>    specification. It rarely needs touching.

False twice for the CR30: 3.18/s is the device's per-reading *measurement time*
(EXP-018 calls the regularity proof that "it is the DEVICE's measurement time
and cannot be improved"), not a sampling rate, and it is not from any
specification — `chromiq-cr30-research/PROTOCOL.md:170-179` records that no
sensor-parameter command exists in ten vendor sessions.

And the closing paragraph, on the `min_samples`-falsy branch:

> Set a minimum above Off, and a number of patches per strip, and this
> instrument is judged like any other.

Also false, and it is an *invitation to act*. A user who follows it gets
`_pace_config` to build a real `PaceConfig` (`ui/tabs/tab_measure.py:4915`) and
still nothing is judged, because `strip_measured`
(`ui/tabs/tab_measure.py:1080`) is the only subscriber and `Cr30SpotManager`
does not emit it. The proposed fix edits only the `key == "cr30"` body branch at
`core/measure_pace.py:690-703` and leaves both of these standing.

**The fix must give `_calculation_note` a CR30 branch too**, or the release ships
a corrected number underneath an uncorrected explanation of what the number is.

## D4 — CONFIRMED: greying the box does NOT stop the value being persisted

`ui/dialogs/settings_dialog.py:5824-5825` reads `_hz.value()` from every entry
in `self._pace_hz` unconditionally. A disabled `QDoubleSpinBox` still answers
`.value()`. So "grey it" alone leaves `pace_sample_hz_cr30` being written on
every Preferences Save, exactly as today — only the number changes.

This is the same shape as the doctrine at `ui/tabs/tab_measure.py:1536-1540`
(`_apply_cr30_dead_options`): *"every save path reads the widget whether or not
it is enabled"*. There, that is deliberate. Here it is the thing being
complained about.

## D5 — CONFIRMED: lowering `SAMPLE_HZ_RANGE[0]` opens six other rows to nonsense, and no test guards them

With the floor at 1.0 every row's minimum became 1.0 (probe output:
`i1pro '100 Hz' min= 1.0`, `colormunki min= 1.0`, `spectroscan min= 1.0`). A
user can then set the i1Pro to 1 Hz, which makes
`PaceConfig.target_seconds = min_samples / sample_hz = 20 s per patch`
(`core/measure_pace.py:91`) and every strip "too fast" for ever. The 10 Hz floor
is the only thing preventing that today, and `tests/test_measure_pace.py:198-199`
is the only test that would notice the floor moving — it pins the tuple, nothing
pins the CONSEQUENCE.

Note also the falsy-`or` trap at `ui/dialogs/settings_dialog.py:3561` and
`ui/tabs/tab_measure.py:4890`: `settings.get(key, default) or default`. A stored
`0.0` silently becomes the default. So the floor can never usefully be 0.

**Cheaper alternative the fix should be measured against:** do not touch the
shared range at all. Give the CR30 row its own range
(`hz.setRange(1.0, 500.0) if key == "cr30"`), leaving the other six on
`SAMPLE_HZ_RANGE` and leaving `tests/test_measure_pace.py:198-199` green.

## D6 — SUSPECTED (design): the row's stated purpose does NOT require an editable Hz box, and greying it makes the "Readings per second" COLUMN HEADER the remaining lie

`core/measure_pace.py:332-342` gives exactly one reason for the row:

> The row exists so that `_pace_config`'s unknown-instrument fallback — the
> i1Pro's (100.0, 20) — can never be applied to a CR30 chart.

That reason is served by `MODEL_DEFAULTS["cr30"]` existing, not by the Preferences
table rendering a row for it. `defaults_for` (`core/measure_pace.py:713-721`)
reads `MODEL_DEFAULTS`; the table is a separate `for row, (key, …) in
enumerate(MODEL_DEFAULTS.items())` at `ui/dialogs/settings_dialog.py:3552-3553`.
So **removing the row would not break the fallback** — the finding note's
option B is cheaper than it claims. It would only mean the table stops being a
straight render of `MODEL_DEFAULTS`.

Greying keeps the row but leaves the column header `tr("Readings per second")`
(`:3527`) asserting a per-second rate for a device that takes exactly one reading
per button press. 3.18/s is a *reciprocal of a cycle time*, not a stream rate.
An honest greyed row would need its own tooltip AND the ⓘ to say so (D3), which
is three strings across 12 catalogues for a control nobody can use.

**This is a Basti/Knut design call, not a reviewer's.** But the two options are
not the "cheap vs expensive" pair the finding note implies: greying costs MORE
strings than removal.

## D7 — CONFIRMED: 3.18 is a HOST-TRIGGERED USB round-trip rate, measured on a code path ChromIQ deliberately never uses

`chromiq-cr30-research/tools/probe_measurement_rate.py:66-72` is the whole loop:

```python
while time.monotonic() - t0 < seconds:
    dev.trigger_unsafe()
    m = dev.read_measurement(enforce=False)
```

So one "cycle" is **four USB round trips**: `usb_measure.trigger()` (one
transact, `src/cr30/usb_measure.py:181`) plus `read_stored()`'s three chunk
transacts (`CHUNK_SUBS = (0x10, 0x11, 0x12)`, `src/cr30/usb_measure.py:38,
143-145`). 315 ms is the whole cycle, not an isolated integration time.

There is no fixed sleep inflating it (`src/cr30/transport.py:175` polls at
0.5 ms) and no UART in the path (`transport.py:34-36`), so the device dominates
— but "the regularity means it is the DEVICE's measurement time" is an
INFERENCE from low variance, not a measurement of the device's integration
time, and the repo's own `PROTOCOL.md:170-179` says no command exists that
could confirm or change it.

**The decisive point:** `trigger_unsafe` is explicitly not ChromIQ's path.
`src/cr30/device.py:95-113`:

> "Ask the device to measure NOW (USB only). **NOT for a ChromIQ backend.** …
> The spot workflow does not need this: the operator presses the instrument's
> own button and `read_measurement()` collects the result."

ChromIQ's CR30 backend is `Cr30SpotManager`, which waits for a button press
(`workflow/cr30_spot_manager.py:152-161`, `arm_trigger`). **A ChromIQ user
never experiences 3.18 readings a second.** They experience one reading per
hand placement and press — the "roughly two seconds" the CR30 ⓘ already quotes
(`core/measure_pace.py:700-702`), i.e. ≈0.5/s.

So writing 3.18 into a Preferences column headed "Readings per second" swaps a
false number for a **true number that answers a different question**. It is
defensible only as "the fastest the device can be made to cycle over USB",
which is not what the column, the tooltip or the tab note claim.

## D8 — CONFIRMED: 3.18 is USB-ONLY, ChromIQ ships Bluetooth too, and this repo's own code says Bluetooth is much slower

`captures/public/EXP-018-rate-usb.json` carries `"transport": "usb"`. I checked
every `EXP-BLE-*.json` in `captures/public/` for a rate field: **none records
`per_second`, `cycles` or `median_ms`.** There is no BLE rate measurement.

ChromIQ supports both: `workflow/cr30_spot_manager.py:307-322`
(`_transport_note`) prints "Connected to your CR30 over the USB cable." or
"…over Bluetooth." And `workflow/cr30_spot_manager.py:152-155` states, as the
reason for an ordering fix:

> "the reader thread does not reach its wait until it has taken the lock and
> opened the transport -- **seconds, over Bluetooth**."

So a single shipped number under "Readings per second" would be wrong for
roughly half the CR30 users, in the direction that flatters the device.

**Honest options, in order:** (a) do not show a rate for the CR30 at all (D6);
(b) show it only in the ⓘ, qualified as "over USB, host-driven, EXP-018", never
in a box headed "Readings per second"; (c) measure BLE first. Shipping 3.18 in
the box without (c) repeats the exact mistake being fixed — a number in a box
that the evidence does not cover.

## D9 — CONFIRMED: the i18n and em-dash cost is larger than the finding note states

Checked `tests/data/em_dash_baseline.json` (`{"english": [1187], "translations":
[470]}`) for each string the fix would touch:

| string | in frozen baseline | carries an em dash |
|---|---|---|
| `_calculation_note` head ("HOW THE THREE NUMBERS…") | **yes** | **yes** |
| CR30 ⓘ body ("The CR30 is not swiped at all…") | **yes** | **yes** |
| tab note ("Every instrument takes a fixed number…") | **yes** | **yes** |
| tab intro ("Reading a strip too quickly…") | **yes** | **yes** |
| `_calculation_note` worked-figures paragraph | **yes** | **yes** |
| Hz spin-box tooltip ("How many readings…") | no | no |
| `_calculation_note` tail ("On this row the minimum is Off…") | no | no |

CLAUDE.md's rule: *"a string you touch for any reason stops matching the
baseline, so clean its dash while you are in there."* So editing the CR30 ⓘ body
(D3) forces its em dashes out; editing `_calculation_note` to give the CR30 its
own branch (also D3) forces the head's out too, and the head is shared by **all
seven rows**, so six other instruments' help text changes as collateral.

Each touched string becomes a NEW key in **12 catalogues**
(`data/i18n/{de,es,fr,it,ja,nl,no,pl,pt,ru,sv,zh_CN}.json`), enforced by
`tests/test_i18n.py` (missing keys, stale keys, placeholder mismatches) and
`tests/test_no_new_em_dash_in_user_facing_text.py` (which separately refuses a
translation that adds an em dash its English source lacks — so a German
translation of a de-dashed string may not keep the dash either).

**Minimum realistic scope if D3 is honoured: 3-5 English strings x 12
catalogues = 36-60 translations,** for a control that does nothing. That is a
real argument for D6's "remove the row" rather than "grey it".

## D10 — CONFIRMED, AND THE MOST SERIOUS FINDING: bumping `SETTINGS_SCHEMA` for this cosmetic fix silently DESTROYS FIVE deliberate user settings

`AppSettings.migrate()` (`core/settings.py:875-926`) is gated by ONE counter:

```python
if int(self._qs.value("settings_schema", 0) or 0) >= SETTINGS_SCHEMA:
    return []
```

There is no per-migration bookkeeping. So a bump 22 → 23 re-runs **all thirteen
`_migrate_*` helpers and the whole `_SUPERSEDED_DEFAULTS` table** against a
store that has already been through them once. Every value a user has
*deliberately set back* since the last bump is dropped a second time.

Reproduced (sandboxed `.ini`, `core.settings.SETTINGS_SCHEMA` monkeypatched to
23 to stand in for the bump the CR30 fix needs):

```
before:  {'restore_last_tab': True, 'patch_read_warn_de': 80.0,
          'chartread_engine': 'argyll', 'save_measurement_report': False,
          'pace_min_samples_colormunki': 23}
migrate at schema 22 (no bump): []
migrate at schema 23 (bumped):  ['pace_min_samples_colormunki',
                                 'patch_read_warn_de (raised value now too high)',
                                 'save_measurement_report (now on by default)',
                                 'chartread_engine (ChromIQ engine now the default)',
                                 'restore_last_tab (now off by default)']
after:   {'restore_last_tab': None, 'patch_read_warn_de': None,
          'chartread_engine': None, 'save_measurement_report': None,
          'pace_min_samples_colormunki': None}
```

`main.py:178` calls `settings.migrate()` on every start, so this lands on the
first launch of v4.2.1, silently, for **every** user — not only CR30 owners.

The worst of the five: **`chartread_engine` "argyll" → dropped → ChromIQ
engine.** A user who deliberately went back to Argyll because the ChromIQ
reading engine misbehaved on their instrument is put back on it without being
told. `save_measurement_report` False → True is second.

**This is a pre-existing latent flaw, not one the fix introduces — but the fix
is what pulls the trigger, in a STABLE release.** Nothing in the proposed design
mentions it.

### The way out: this fix does not need a schema bump at all

The stored `pace_sample_hz_cr30` only matters because
`ui/dialogs/settings_dialog.py:3561-3562` reads it and `:5825` writes it. If the
CR30 row stops round-tripping through the store — read the default, never
persist the key — the stale 100.0 becomes inert wherever it sits, and
`_pace_config` (`ui/tabs/tab_measure.py:4890`) never reads it either because a
CR30's `min_samples <= 0` short-circuit at `:4911-4914` throws the Hz away
regardless.

So: **do not add `pace_sample_hz_cr30` to `_SUPERSEDED_DEFAULTS` and do not bump
the schema.** Skip the key on save and ignore it on load. If the stale key must
be tidied, do it unconditionally outside the schema gate (a `remove()` that is
idempotent by construction), not by bumping a counter that re-runs twelve other
migrations.

**If a bump is nevertheless chosen, it needs its own regression test** and a
CHANGELOG line saying which five settings reset — and `migrate()` needs
per-migration bookkeeping first. That is a much bigger change than the defect.

## D11 — SUSPECTED: a deliberately-typed CR30 rate is indistinguishable from the default, but that is not the real hazard

`_SUPERSEDED_DEFAULTS` matching is `abs(float(raw) - old) < 1e-9`
(`core/settings.py:881-886`), so a user who deliberately typed `100` into the
CR30 box would lose it. In practice that is not worth worrying about: with
`decimals(0)` and range `10..500` the only values reachable are integers, the
control changes nothing, and the ⓘ says so.

The hazard is the reverse one, and it is D1's: after a migration drops 100.0 the
box RE-SEEDS from the (clamped) default and the next Save persists **10.0**,
which no future migration can ever recognise.

---

# DEFECT 2 — "Double density stays ticked for an instrument that has none"

## D12 — CONFIRMED, AND IT INVALIDATES THE BRIEF: the CR30 *does* have a double-density mode. `_dd_check` is its **Hexagon patches** option (#159), and the proposed fix would destroy it

`_update_dd_visibility` (`ui/tabs/tab_chart.py:12715-12836`) is not a
show/hide: it is a **four-way relabel of one checkbox into three different
options**.

| instrument | `_dd_check` | label |
|---|---|---|
| `CM` | visible | "Double density" — printtarg `-h`, REQUIRES the ColorMunki rig |
| `CR30` | visible | "Hexagon patches (suits the round CR30, fits more per sheet)" (`:12741-12780`) |
| `SS` | visible | "Hexagon patches (packs ~15% more per sheet)" (`:12781-12798`) |
| `i1`, `p3` | hidden **and force-unchecked** (`:12799-12805`) | — |

Reproduced on screen (real `TabChart`, offscreen/Fusion, sandboxed settings):

```
CR30 fresh    instr='CR30' dd vis=True chk=False label='Hexagon patches (suits the round CR30,'
CR30 +hex     instr='CR30' dd vis=True chk=True  label='Hexagon patches (suits the round CR30,'
```

So `create_chart_ui.guided.double_density: true` on a CR30 chart is **not a
leaked ColorMunki flag — it is the recorded "make this chart hexagonal"
choice**, and #159 shipped it deliberately (`:12742-12744`: *"Same option, its
own numbers and its own reasons (#159, Basti 2026-08-28). Measured on this
branch: A4 patch-first, 532 patches rectangular against 576 hexagonal."*).

**The brief's premise — "Double density is a ColorMunki-only option
(`printtarg -h` for CM)" and "pick CR30 … an instrument without a
double-density mode" — is wrong.** Implementing "force `double_density` false
whenever the instrument has no double-density mode" would, if CR30 is on the
"has none" list, silently remove the hexagon chart from the CR30 and make it
unbuildable through Guided. That is a shipped feature, not a leak.

**STOP AND RE-SCOPE BEFORE WRITING CODE.** What was actually seen on screen is
D13, and it is a different bug with a different fix.

## D13 — CONFIRMED: the real defect is a SEMANTIC LEAK — one tick means three different things and carries silently between them, one of which requires HARDWARE the user may not own

Reproduced, same session:

```
CM fresh        dd chk=False label='Double density'
CM +dd          dd chk=True  label='Double density'
-> CR30         dd chk=True  label='Hexagon patches (suits the round CR30,'
   shared_get(guided).double_density = True
```

and the reverse, which is worse:

```
CR30 +hex       dd chk=True  label='Hexagon patches (suits the round CR30,'
-> SS           dd chk=True  label='Hexagon patches (packs ~15% more per s'
-> CM           dd chk=True  label='Double density'
   shared_get(guided) = {'instrument': 'CM', 'double_density': True, ...}
```

A user who asked for **hexagons on a CR30** and then switches to ColorMunki is
handed **rig-dependent double density**, ticked, with no prompt. The CM tooltip
itself says (`ui/tabs/tab_chart.py:12727-12730`):

> "REQUIRES the physical measuring rig accessory … Without the rig the device
> cannot align to the tighter patch spacing and **will misread**."

That is a chart the user cannot measure, produced by a control they never
touched for that instrument. It is strictly more serious than the reported
symptom.

**The correct fix is per-instrument state, not forcing false.** `_dd_check`
needs a remembered value PER instrument family (`{"CM": bool, "CR30": bool,
"SS": bool}`), restored on switch — the pattern `_apply_cr30_pbp_lock` already
uses for the patch-by-patch tick (`ui/tabs/tab_measure.py:1584+`,
`self._pbp_lock_snapshot`).

## D14 — CONFIRMED: the app already contains TWO CONTRADICTORY DOCTRINES for a control the current instrument cannot use, and the brief picks the one this file rejects

* `ui/tabs/tab_chart.py:12801-12805`, the `else` branch:
  > "Force-uncheck when hidden so the state can't leak into printtarg the next
  > time the user goes back to CM/SS without re-touching it."
* `ui/tabs/tab_measure.py:1536-1540`, `_apply_cr30_dead_options`:
  > "**DISABLE ONLY, NEVER UNTICK.** The saved value belongs to the target and
  > must survive for the day the same chart is measured with an instrument that
  > does honour it — every save path reads the widget whether or not it is
  > enabled. What actually falls silent is `build_args`."

Both are documented as deliberate, in capitals, by the same project. The brief's
proposed fix ("make the stored/collected value false") is the tab_chart
doctrine, and it is the one that **loses user intent**. Whichever is chosen,
this contradiction should be named in the commit, because a reviewer will
otherwise read the change as a violation of the other.

## D15 — CONFIRMED: the "does a deliberate tick survive an instrument round trip?" question is already answered NO, today, and forcing false makes it worse

```
CM +dd          dd chk=True
-> i1           dd vis=False chk=False   <-- force-unchecked
-> back to CM   dd vis=True  chk=False   <-- NOT restored
```

A ColorMunki user who ticks Double density, glances at i1Pro, and comes back has
silently lost it. That is the brief's own question 3, and the answer is that the
"new bug" already exists for the i1/p3 path. The proposed fix generalises it to
every instrument.

Per-instrument remembered state (D13) fixes both the leak and this loss in one
change; "force false" fixes neither.

## D16 — CONFIRMED: `no_strip_limit` and `triple_density` are force-unchecked on hide; **`left_border` is NOT**

`ui/tabs/tab_chart.py:12806-12836`:

* `_td_check` — `if not td_visible and self._td_check.isChecked(): setChecked(False)` (`:12813-12814`). Force-unchecked. Confirmed on screen: `CM +td` then `-> CR30` gives `td chk=False`.
* `_nsl_check` — force-unchecked (`:12834-12835`).
* **`_lb_check` — hidden at `:12823-12824` with NO uncheck.** A stored
  `left_border: true` therefore survives a switch to CM/SS/CR30 while invisible.

It cannot reach `printtarg -L` (gated by `l_applies = p.instrument in {"i1",
"p3"} or triple`, `:5430-5432`), but it IS collected into the shared snapshot
(`:7024`) and it is passed to the layout engine **ungated** at
`ui/tabs/tab_chart.py:178`: `suppress_left_clip=params.disable_left_border`.
That asymmetry needs deciding in the same change, or the fix leaves an
inconsistent set of four sibling controls.

## D17 — MEASURED, CONFIRMED: `double_density` on a CR30 reaches the ACTUAL BUILD. It is not cosmetic in the stored record

`workflow/chart_creator.py:1303-1316`:

```python
elif params.instrument == "CR30":
    kw["layout_mode"] = "patch_first"
    # Hexagons, from the same checkbox the SpectroScan uses (Basti,
    # 2026-08-28). Guided relabels it "Hexagon patches" for both.
    kw["hflag"] = bool(params.double_density)
```

and `workflow/layout_engine/instruments.py:220-223` /
`hex_capable()` measured live:

```
hex_capable: {'i1': False, 'p3': False, 'CM': False, 'SS': True, 'CR30': True}
```

Note **`CM` is NOT hex-capable and `CR30` is** — the exact inverse of the
brief's model.

Built two real CR30 A4 charts from
`assets/charts/redriver/rgb/standard_patch_set_v25/chart.ti1` through
`workflow.layout_engine.chart.build_chart`, identical but for `hflag`:

```
hflag=False: Layout(steps_in_pass=23, passes=15, patches_per_page=345, pages=6, pprow=23)
hflag=True:  Layout(steps_in_pass=26, passes=4,  patches_per_page=390, pages=6, pprow=26)
   .ti2 gains the keyword:  HEXAGON_PATCHES "True"
```

345 vs 390 patches per page, a different grid, and a keyword written into the
`.ti2` that downstream tools read. **Forcing `double_density` false for a CR30
would change the chart that is printed.** It is a functional regression, not a
metadata tidy-up.

## D18 — CONFIRMED: what is ALREADY on disk. Nothing needs healing, and a "heal" would be destructive

Existing CR30 projects with `create_chart_ui.guided.double_density: true` fall
into two groups and **nothing in the record distinguishes them**:

1. the user ticked "Hexagon patches" deliberately — the value is correct, and
   the chart on disk is hexagonal (`HEXAGON_PATCHES "True"` in its `.ti2`);
2. the tick leaked in from ColorMunki (D13) — the value is wrong, but the chart
   on disk is *still* hexagonal, because the build honoured it.

Either way **the chart that exists is what the stored flag says**, so a
migration that rewrites the flag to false would make the record disagree with
the artefact. The `.ti2` is the ground truth and it already carries
`HEXAGON_PATCHES`.

**Do not heal.** If anything is wanted here it is a read-side reconciliation:
prefer the `.ti2`'s `HEXAGON_PATCHES` keyword over the stored UI flag when
reopening a chart. Note `ui/tabs/tab_chart.py:11675-11691`
(`_carry_engine_recipe_from(channels_json)`) is the existing mechanism for
exactly that kind of read-back.

## D19 — CONFIRMED: only TWO tests touch `_dd_check`, and neither covers instrument switching

`grep -rn "_dd_check\|_update_dd_visibility" tests/` returns exactly:

* `tests/test_guided_manual_transfer.py:43` — `test_transfer_copies_instrument_paper_pages_and_density`, CM only, asserts `-h` becomes True
* `tests/test_guided_manual_transfer.py:87` — `test_switch_carries_instrument_paper_not_the_rest`, CM only, asserts density does NOT carry on a plain tab switch

`double_density` appears more widely (chart_creator, presets, engine), but
**nothing pins `_update_dd_visibility`'s relabelling, nothing pins the CR30
hexagon path through the checkbox, and nothing pins the force-uncheck on the
i1/p3 branch.** A change here is effectively untested today. That is why the
brief's premise survived to this point.

---

# THE THIRD DEFECT — `engine_recipe.instrument` — ANSWERED, NOT ASSUMED

## D20 — CONFIRMED: it is a DIFFERENT root cause. Fixing defect 2 would not touch it

Reproduced in a clean sandbox (real `TabChart`, Guided, CR30 + A4):

```
mode: guided
guided: {"double_density": false, "instrument": "CR30", "left_border": false,
         "no_strip_limit": false, "pages": 1, "paper": "A4", ...}
engine_recipe.instrument: i1   paper: A4   hflag: False
engine ON -> engine_recipe.instrument: i1  hflag: False
after hex tick: guided.double_density = True | engine_recipe.instrument = i1  hflag = False
after transfer: engine_recipe.instrument = CR30              hflag = True
```

(The stored instrument is whatever seeded the **Manual layout panel** — "i1" in
a fresh sandbox, "CM" in the owner's, per the brief. The value is not the
Guided selection either way.)

**Mechanism.** `_collect_ui_state` (`ui/tabs/tab_chart.py:14951-14954`) reads
the recipe from ONE place, unconditionally, whatever mode is active:

```python
rec = self._manual_layout_panel.get_recipe()
if rec is not None:
    out["engine_recipe"] = rec.to_dict()
```

The Manual panel is seeded by `_init_manual_layout_panel`
(`:5710-5730`) from `manual_engine_recipe` or the per-(instrument/paper/mode)
store, and the ONLY thing that pushes the Guided selection into it is
`_apply_guided_engine_recipe` (`:7233-7258`), called from exactly one site —
`_transfer_guided_to_manual` at `:6981`. **A Guided build does not call it**,
which the probe's last two lines prove: the value is wrong until a manual
transfer runs, then it is right.

**So the two defects are independent:**

| | defect 2 | defect 3 |
|---|---|---|
| widget | `_dd_check` in the **Guided** panel | `_manual_layout_panel`'s recipe |
| stored under | `create_chart_ui.guided.double_density` | `create_chart_ui.engine_recipe.*` |
| collected at | `_shared_get("guided")`, `:7022` | `_manual_layout_panel.get_recipe()`, `:14953` |
| broken because | one tick carries three meanings across instruments | Guided never writes into the Manual panel |

In the probe, ticking hexagons moved `guided.double_density` to `true` and left
`engine_recipe.hflag` at `false` **in the same snapshot**. A CR30 run's
`meta.json` therefore records two flags that contradict each other. Fixing
either one alone leaves the contradiction, so they should be fixed together —
but by two different edits, and neither fix implies the other.

## D21 — SUSPECTED: defect 3 has a live consequence, not just a wrong record

`ui/tabs/tab_chart.py:15088-15117` restores `engine_recipe` into the Manual
layout panel on target switch (`_apply_ui_state`, guarded only by `built_here`).
So reopening a CR30 project pushes an **i1Pro/ColorMunki** layout recipe into the
panel; a user who then opens Manual is shown, and can build from, a layout for
the wrong instrument. I have not driven that end to end — reproducing it needs a
real saved project and a target switch — so this is SUSPECTED, but the read path
is unambiguous.

## D22 — CONFIRMED, BLOCKING: the proposed defect-2 fix VIOLATES a CONFIRMED design specification

`docs/design/per_target_settings.md` §4c, *"An instrument default is not an
override"* — **✅ Confirmed behaviour, Confirmed by: Basti, 2026-09-02**
(`:374-411`). It was written about this exact scenario: Knut's 4.1.5-beta.5
report of loading a ColorMunki preset and **switching the instrument to CR30**.

| # | Rule |
|---|---|
| D-1 | An instrument default **may** set a value the person has not chosen |
| **D-2** | **It may not overwrite a value they have chosen — by hand, or by loading a preset** |
| D-3 | A default's **own** write is not an answer |
| D-4 | The app's own starting point (factory settings, `default_recipe`, saved defaults) is **not** an answer |

Basti's words in that section:

> *"Somebody who has just loaded a preset has already said what they want, by
> name, two clicks ago — overriding that is the app arguing with a decision the
> person made deliberately."*

Create Chart is explicitly **in scope** for this spec (§5 table, `:426`).

**"Make the stored/collected value false whenever the current instrument has no
double-density mode" is, precisely, an instrument-change default overwriting a
value the user chose by hand. It breaks D-2.**

And so does the code that already exists: the force-uncheck in the `else`
branch, `ui/tabs/tab_chart.py:12801-12805`, predates the 2026-09-02 ruling and
now contradicts it. That is a spec conflict to REPORT, not to fix on our own
judgement — CLAUDE.md: *"A fault that contradicts the specification is not
simply fixed. Report it, say which rule it breaks, and get the change reviewed
and approved before implementing it."*

**Consequence for the release:** defect 2 cannot ship as designed. The design
that DOES satisfy §4c is D13's — remember the tick per instrument and restore
it, so a switch neither leaks a choice nor destroys one. That is D-1 plus D-2
together, and it also removes the pre-existing D-2 violation at `:12801-12805`.

## D23 — CONFIRMED (context): the working tree is not where the brief says the fix lands

`git branch --show-current` → **`feature/nelson-photocard-presets`**, 5 commits
ahead of `master`, working tree otherwise clean. `core/version.py` already reads
`APP_VERSION = "4.2.1"`.

The brief says v4.2.1 is "a stable release off master". Whatever is built here
must be branched from master (project rule: *release from master — merge, then
tag*), not stacked on this branch, and the release gate
(`QT_QPA_PLATFORM=offscreen pytest --runslow -n auto`) has to be green on the
merge result, not on this tree.

## D24 — CONFIRMED: `left_border` DOES reach a CR30 build's recorded layout from an invisible checkbox

Measured, same live `TabChart`:

```
i1 + lb: {'instrument': 'i1',   ..., 'left_border': True}
CR30   : lb visible= False  checked= True
CR30 shared: {'instrument': 'CR30', ..., 'left_border': True}
ChartParams: instrument=CR30  disable_left_border=True  double_density=False
LayoutOptions.suppress_left_clip = True
```

So the sibling control the brief did NOT name is the one that genuinely leaks a
hidden value into a build record. It cannot reach `printtarg -L`
(`ui/tabs/tab_chart.py:5430-5432` gates on instrument) and it cannot reach the
engine's `nolpcbord` (`workflow/chart_creator.py:1274-1281`, i1/p3 branch only),
but it DOES reach `_layout_options_from_params`
(`ui/tabs/tab_chart.py:164-184`), which is described in its own docstring as
*"the chart's meta stamp and the Save-Preset layout sync"*.

Note the irony: by §4c D-2 (D22) that tick is the user's own choice and may not
be overwritten either. The brief's rule ("force false when the instrument has no
such mode") cannot be applied uniformly; whichever way it is settled has to be
settled for all four controls at once, by Basti, against §4c.

---

# THE DESIGNS I WOULD BUILD

## Defect 1 — the CR30's "100 Hz"

### What I would NOT do
* Not bump `SETTINGS_SCHEMA` (D10).
* Not widen the shared `SAMPLE_HZ_RANGE` (D5).
* Not raise the shared `setDecimals` (D2).
* Not put 3.18 in a box headed "Readings per second" (D7, D8).

### The build, file:line by file:line

1. `core/measure_pace.py:343` — leave the tuple's rate ALONE or set it to a
   named constant, and rewrite the comment at `:332-342` so it stops claiming
   100.0 is "purely so the spinbox shows the shipped default". Record the
   measured fact and its provenance there (EXP-018, USB, host-triggered).
   The value is never rendered once step 2 lands, so it is only documentation.
2. `ui/dialogs/settings_dialog.py:3552-3567` — inside the row loop, when
   `key == "cr30"`, do not build a spin box at all: place a read-only
   `QLabel(tr("Not applicable"))` in column 1, matching the "N/A" / "Off"
   language already used at `:3574` and `:3590`. Keep the ⓘ, keep the row (D6's
   fallback reason is `MODEL_DEFAULTS`, not the row, but the row is what tells
   the user nothing is being applied behind their back).
   *If Basti prefers a greyed number instead of "Not applicable", then and only
   then:* per-row `hz.setRange(1.0, 500.0)`, per-row `hz.setDecimals(2)` BEFORE
   `setValue`, `hz.setEnabled(False)`, and a CR30-specific tooltip — never the
   shared `setRange`/`setDecimals` lines.
3. `ui/dialogs/settings_dialog.py:5824-5825` — skip `cr30` in the save loop
   (`if _key == "cr30": continue`), with a comment naming D4. Do the same for
   `_pace_min` / `_pace_patches` only if step 2 also blanks those.
4. `core/measure_pace.py:512-547` — give `_calculation_note` an early
   `if key == "cr30"` return that omits the "Readings per second is the
   instrument's own sampling rate, from its specification" bullet and the
   "Set a minimum above Off … judged like any other" invitation (D3).
5. `core/measure_pace.py:689-703` — add ONE sentence to the CR30 ⓘ body giving
   the measured cycle and its exact scope, e.g. *"Measured over the USB cable
   with ChromIQ driving the instrument, one reading completes every 315 ms
   (about 3 a second). That is how long the device takes, not a rate you can
   spend on a swipe, and it has not been measured over Bluetooth."* Clean the
   paragraph's em dashes while there (D9).
6. `core/settings.py` — nothing. No `_SUPERSEDED_DEFAULTS` entry, no schema
   bump. A stale `pace_sample_hz_cr30` becomes inert.

### Edge cases it must handle
* A store already holding `pace_sample_hz_cr30 = 100.0` — must be ignored, not
  migrated (D10).
* A store holding `pace_sample_hz_cr30 = 10.0` from a half-shipped fix — same.
* `_pace_config`'s `or hz_default` falsy trap (`ui/tabs/tab_measure.py:4890`) —
  a stored 0.0 must still resolve to the default.
* A user who sets `pace_min_samples_cr30` above Off: `_pace_config` builds a
  real `PaceConfig` and still nothing is judged. The ⓘ must not invite it (D3).
* A CR30 chart read with a NON-CR30 instrument, and vice versa: `_pace_config`
  prefers the DETECTED model over the chart's (`:4874-4884`), so the row that
  applies is the connected instrument's. Blanking the CR30 row must not change
  that resolution.

### Tests that must exist
* `tests/test_cr30_registration.py` — the CR30 pace row shows no editable rate
  (extend `test_the_pace_row_exists_and_raises_no_warning`, `:388-400`).
* A new test that a Preferences Save does **not** write `pace_sample_hz_cr30`.
* A new test that `explanation_for("cr30")` contains neither "from its
  specification" nor "judged like any other".
* `tests/test_measure_pace.py:198-200` must stay GREEN unchanged — proof the
  shared range was not widened.
* `tests/test_cr30_registration.py:821-822` docstring says `defaults_for("cr30")`
  is `(100.0, None)`; update it if the tuple changes.
* `tests/test_i18n.py`, `tests/test_no_new_em_dash_in_user_facing_text.py` after
  the string edits, plus `python scripts/i18n_extract.py --missing <code>` for
  all 12.

## Defect 2 — the density tick across instruments

**Blocked pending Basti's ruling (D22).** The brief's fix breaks a confirmed
spec rule. What I would take to him:

> `_dd_check` is one checkbox carrying three different options — ColorMunki
> double density (needs the rig), CR30 hexagons, SpectroScan hexagons — and the
> tick carries between them unchanged. A CR30 hexagon choice becomes a
> rig-dependent ColorMunki chart; a ColorMunki choice becomes a hexagonal CR30
> chart. Separately, i1Pro/i1Pro 3 Plus force the tick OFF and never give it
> back, which §4c D-2 now forbids. Should the tick be remembered per instrument
> and restored on switch?

### The build, if he says yes

1. `ui/tabs/tab_chart.py:3907` — add `self._dd_per_instr: dict[str, bool] = {}`
   beside `_dd_check`, same for `_td_check` / `_nsl_check` / `_lb_check`.
2. `ui/tabs/tab_chart.py:12715` — at the TOP of `_update_dd_visibility`, stash
   the outgoing instrument's tick; at the bottom, restore the incoming one.
   Requires remembering the previous `currentData()` (the combo's signal is
   `currentIndexChanged`, `:3846`, which does not carry the old value).
   Block signals around the restore or `_on_guided_dd_toggled` / `_update_patch_count`
   (`:3908-3909`) fire spuriously.
3. `ui/tabs/tab_chart.py:12801-12805` — delete the force-uncheck; the restore in
   step 2 supersedes it. **This is the line that violates §4c D-2 today.**
4. `ui/tabs/tab_chart.py:12813-12814`, `:12834-12835` — same for `_td_check`
   and `_nsl_check`, or the four siblings stay inconsistent (D16, D24).
5. `ui/tabs/tab_chart.py:7022-7025` (`_shared_get("guided")`) — leave alone. It
   reports what is on screen, which is now correct by construction. Do NOT add
   an instrument-conditional zeroing there: that would re-break §4c D-2 and
   would also make the CR30's hexagon unstorable (D12/D17).
6. `workflow/chart_creator.py:1995` and `ui/tabs/tab_chart.py:5422` — unchanged;
   both already gate `-h` on `instrument in {"CM","SS"}`, which is the real
   "falls silent in build_args" defence tab_measure's doctrine calls for.

### Edge cases
* The interlock at `:12838-12842` (`_on_guided_dd_toggled` disables `_td_check`
  and vice versa) must not fight the restore — restore dd and td together, then
  re-run the interlock once.
* `_td_saved_lb_check` (`:12851-12858`) already stashes `_lb_check` around
  triple density. Two overlapping snapshot mechanisms for the same widget; the
  new one must not clobber it.
* A preset load (`_set_engine_recipe`, `:18090`) and a chart load
  (`_carry_engine_recipe_from`, `:11675`) both set the instrument. The
  per-instrument memory must be SEEDED from those, not overwrite them (§4c D-4:
  the app's own starting point is not an answer).
* The memory is session-only unless it is also written to the target store; the
  brief does not say which, and §3 of `per_target_settings.md` does.

### Tests that must exist
* CM tick → CR30 → the tick is off; CR30 tick → CM → off. (the leak)
* CM tick → i1 → CM → the tick is BACK. (the loss, D15)
* A CR30 with hexagons ticked still yields `hflag=True` through
  `ChartCreator._engine_build_kwargs` and `HEXAGON_PATCHES "True"` in the .ti2.
  (the regression guard for D12/D17 — nothing pins this today, D19)
* The same three for `_td_check`, `_nsl_check`, `_lb_check`.

## Defect 3 — `engine_recipe.instrument`

Independent of defect 2 (D20). One edit:
`ui/tabs/tab_chart.py:14951-14954` — when `self._mode_name() == "guided"`, build
the recipe from `LayoutRecipe.from_build_kwargs(self._creator._engine_build_kwargs(guided_params))`
(the exact call `_apply_guided_engine_recipe` already makes at `:7249-7250`)
instead of reading `self._manual_layout_panel.get_recipe()`. Guard it the same
way — best-effort, never blocking the write.

Test: a Guided CR30 build's `create_chart_ui.engine_recipe` reports
`instrument == "CR30"`, and its `hflag` agrees with
`create_chart_ui.guided.double_density`.

---

# PRIORITISED — WHAT WOULD BREAK

| # | If shipped as briefed | Severity |
|---|---|---|
| 1 | **Defect 2 removes the CR30's hexagon chart** (D12, D17). A shipped #159 feature; the .ti2 keyword and the 345→390 patch gain both disappear. Existing hexagon tests (`test_cr30_registration.py:118,331,666-670`, `test_hex_*`) go red. | **Blocker** |
| 2 | **A `SETTINGS_SCHEMA` bump silently resets five settings for EVERY user** in a stable release, including `chartread_engine` back to the ChromIQ engine (D10). | **Blocker** |
| 3 | **Defect 2 violates `per_target_settings.md` §4c D-2, confirmed by Basti 2026-09-02** (D22). Not ours to fix without his approval. | **Blocker (process)** |
| 4 | 3.18 without the range/decimals change persists an unmigratable **10.0** (D1). | High |
| 5 | 3.18 shown as "Readings per second" is a USB-only, host-driven cycle rate that no ChromIQ user experiences, presented to Bluetooth users too (D7, D8). | High |
| 6 | Raising the shared `setDecimals` puts `100,00 Hz` on six other rows on a de_DE machine (D2). | Medium |
| 7 | Lowering the shared `SAMPLE_HZ_RANGE` lets any row be set to 1 Hz; `tests/test_measure_pace.py:199` must move and nothing else guards it (D5). | Medium |
| 8 | The corrected number sits under an uncorrected ⓘ that still says "from its specification" and invites a setting that does nothing (D3). | Medium |
| 9 | Greying alone still persists the value on every Save (D4). | Medium |
| 10 | 3-5 English strings x 12 catalogues, with forced em-dash cleaning that reaches all seven instrument rows (D9). | Medium (cost) |
| 11 | `left_border` leaks invisibly into a CR30 build's `LayoutOptions` and is not in the brief (D24); `_lb_check` alone is not force-unchecked (D16). | Low-medium |
| 12 | `engine_recipe` restores an i1Pro/CM layout into the Manual panel on reopening a CR30 project (D21, SUSPECTED). | Low-medium |
| 13 | Only two tests touch `_dd_check` and neither covers instrument switching (D19), so the suite will not catch a regression here. | Low (but it is why this got through) |

# WHAT I COULD NOT VERIFY

* **The CR30's Bluetooth reading rate.** No `EXP-BLE-*` capture in
  `captures/public/` records a rate. `workflow/cr30_spot_manager.py:152-155`
  says the transport opens in "seconds" over Bluetooth, which is suggestive, not
  a measurement.
* **Whether 315 ms is integration time or round trip.** The probe measures four
  USB transactions per cycle (D7). No sensor-parameter command exists to ask the
  device (`PROTOCOL.md:170-179`), so this may not be answerable at all.
* **The owner's live settings.** I did not read the real preferences store; the
  100.0 in his log is the brief's evidence, not mine. All my runs were sandboxed
  via `CHROMIQ_SETTINGS_FILE`.
* **D21 end to end.** I read the restore path but did not drive a real saved
  CR30 project through a target switch.
* **Whether Basti wants the CR30 pace row greyed, blanked or removed**, and
  whether he wants the density tick remembered per instrument. Both are design
  calls, and §4c makes the second one binding on him, not on us.
* **`--runslow` on a tree containing either fix.** Nothing was implemented, so
  the gate was not run against a change. The baseline for the eight most
  relevant files is green (`tests/test_measure_pace.py`,
  `test_cr30_registration.py`, `test_guided_manual_transfer.py`,
  `test_pace_speed_estimate.py`, `test_colormunki_min_samples.py`,
  `test_i18n.py`, `test_no_new_em_dash_in_user_facing_text.py`,
  `test_message_catalogue.py` — 388 passed).

---

# D25 — CONFIRMED: DEFECT 1 IS ALREADY BEING IMPLEMENTED IN THIS SAME CHECKOUT, WHILE THIS REVIEW WAS RUNNING

The brief says "BEFORE any code is written". Code is being written. Mid-review
`git status` went from clean to:

```
 M core/measure_pace.py
 M ui/dialogs/settings_dialog.py
```

and changed again between two of my own commands (a probe that read
`d._pace_hz["cr30"]` raised `KeyError: 'cr30'` where the same probe had returned
a spin box twenty minutes earlier). This is the standing hazard recorded in
memory: *"an agent 'on a branch' edits YOUR checkout"*, and CLAUDE.md's *"Do not
edit source files while a gate is running."* **My earlier baseline (388 passed)
was taken on the pre-edit tree and is not a baseline for the tree as it now
stands.**

### What that in-flight change does, and how it lines up with this review

It independently reaches the design this review recommends, which is reassuring:

* `ui/dialogs/settings_dialog.py:3556-3599` — the CR30 gets a plain
  `QLabel(tr("N/A"))` instead of a spin box, and is **left out of `_pace_hz`**
  (matches D6 / D4 / D2).
* `:5856-5868` — the save loop iterates `_pace_hz`, so `pace_sample_hz_cr30` is
  no longer written (matches D4).
* `:3767-3775` — `_refresh_pace_estimates` switched to `_pace_hz.get(key)`
  (needed, or the missing key would crash the tab).
* No `SAMPLE_HZ_RANGE` change, no `setDecimals` change, **no schema bump**
  (matches D5, D2, D10 — and the comment at `:5860-5867` gives D10's reasoning
  almost verbatim).
* `core/measure_pace.py:343` → `(3.18, None)`, with the comment rewritten to
  state the USB / host-driven / no-Bluetooth caveats (matches D7, D8).
* `core/measure_pace.py:545-570` — a `key == "cr30"` early return in
  `_calculation_note`, explicitly to keep the other six rows' strings
  byte-identical (matches D3 and D9's "one new key, not seven").

I checked the remaining `_pace_hz` consumers: `:3695-3696` iterates the dict
(safe), `:3727` already used `.get` (safe). `tests/test_pace_speed_estimate.py`
indexes only i1pro/i1pro2/colormunki (safe). Dialog tests pass: **83 passed**.

### What is still WRONG or MISSING in the in-flight change

1. **The gate is RED right now.** `tests/test_i18n.py` fails on all 12
   catalogues. `python scripts/i18n_extract.py --missing de` names exactly two
   untranslated keys:
   * the new `_calculation_note` CR30 block ("WHY THIS ROW HAS NO READINGS PER
     SECOND…")
   * the new N/A cell tooltip ("A CR30 takes one reading each time you press its
     button…")

   `12 failed, 247 passed`. **2 strings x 12 catalogues = 24 translations owed.**
2. **The tab note is still false for that row.**
   `ui/dialogs/settings_dialog.py:3475-3481` still opens with *"Every instrument
   takes a fixed number of readings per second"* — now directly above a row
   whose rate cell reads N/A. This is the residue of D3 that the change did not
   pick up.
3. **The CR30 ⓘ body at `core/measure_pace.py:689-703` is untouched**, so the ⓘ
   now reads its old "the strip length shows N/A because a CR30 chart has no
   strips" paragraph and then the new "WHY THIS ROW HAS NO READINGS PER SECOND"
   block. Worth reading end to end on screen for repetition; and it still does
   not name EXP-018 as the source ("measured on real hardware" is the whole
   provenance the user gets).
4. **`_pace_min["cr30"]` and `_pace_patches["cr30"]` are still editable spin
   boxes and are still persisted** (`:5869-5872`). The row is now half blanked:
   an N/A label for the rate, live boxes for the two numbers that are equally
   inert. Either finish the row or say why the other two stay.
5. **No new test pins any of it.** Nothing asserts that `"cr30" not in
   dlg._pace_hz`, that a Save writes no `pace_sample_hz_cr30`, or that
   `explanation_for("cr30")` no longer says "from its specification".
6. **`defaults_for("cr30")` is now `(3.18, None)`** and
   `tests/test_cr30_registration.py:821-822`'s docstring still says
   `(100.0, None)`. Harmless (a docstring), but stale.

**Recommendation:** whoever owns that branch must be told about D22 before they
touch defect 2, and about D12/D17 before they touch `_dd_check` at all. Defect 1
is in good shape; defect 2 as briefed is a blocker.
