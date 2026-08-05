# Calibration as a Run type — feasibility analysis and design draft

> **Status:** DRAFT. No code has been written. **Questions 1, 2 and 6 are
> decided** (Sebastian, 2026-08-04); 3, 4, 5 and 7 carry a recommendation
> awaiting his word, and 8 is new. See §9. Requested by Sebastian
> on [issue #130](https://github.com/itsab1989/ChromIQ/issues/130), 2026-08-04:
> *"I wonder if it would be possible to offer a third 'calibration' run type in
> the bar — only when calibration options are turned on."*
>
> Every claim below about current behaviour was checked against the code and,
> where behaviour was in question, run. File and line references are to the tree
> at `v3.14.8-beta.129`; ArgyllCMS references are to the 3.5.0 sources.

## Verdict in one paragraph

**Doable, and worth doing — but "Calibration" is not a third *run* type; it is a
third *target* type.** A run is one profile build; a calibration is one per
**project**, shared by every run (`Calibration`, `core/file_manager.py:318-384`;
the file guide says so to the user too, `ui/file_guide.py:261`). So
"Profile run = Run 3 · Run type = Calibration" has no meaning, and the design
below makes the bar say what is actually true. The work is contained — the
folder model, both Argyll runners, the chart routing and the auto-prefill all
exist already — and the research turned up **six real defects in today's
calibration path**, one of which destroys the user's calibration without a word.
That last one is an argument *for* the feature: bringing calibration under the
same rules as runs is what fixes it.

---

## 1. What already exists (nothing here needs building)

| Piece | Where | What it does today |
|---|---|---|
| The preference | `calibration_mode`, `core/settings.py:141`; the checkbox in `ui/dialogs/settings_dialog.py:2541` | Off by default. |
| Mode switch-over | `MainWindow._apply_calibration_mode`, `ui/main_window.py:1138-1149` | Calls `set_calibration_mode(bool)` on tabs 1, 3, 4, 5 and renames tab 4 to "4. Calibration & Profiling". |
| The calibration folder | `Calibration`, `core/file_manager.py:318-384` | `cal/` with stem `<project>-cal`: `.ti1 .ti2 .ti3 .cal .icc .cht .ps .channels.json`, `exports/`, `meta.json`. **One per project.** |
| Making the chart | `_cal_target_grp` / `_cal_target_check`, `ui/tabs/tab_chart.py:2055-2087`; routing in `workflow/chart_creator.py:594-596` | The "Create chart for calibration" checkbox sets `ChartParams.cal_target`, which routes targen/printtarg output to `cal/`. |
| The calibration knobs | `_on_cal_target_toggled`, `ui/tabs/tab_chart.py:3612-3636` | Ticking the box sets `-f 0 -e 0 -B 0 -s 20`, `-G` off, printtarg `-r` on, and restores the previous values when unticked. |
| Measuring it | `ui/tabs/tab_measure.py:6383-6389` and `7288-7292` | Recognised by path: the `.ti3` lands in a folder named `cal`. |
| Hand-off to tab 4 | `MainWindow._on_measure_done`, `ui/main_window.py:569-575` | A cal measurement goes to `TabProfile.set_cal_ti3_path` and switches to tab 4. |
| The three modules | `ui/tabs/tab_profile.py:403-417`, `_switch_cal_mode`, `:642-652` | **CREATE CALIBRATION FILE** (printcal), **BUILD PROFILE** (colprof), **APPLY CALIBRATION** (applycal). |
| printcal | `workflow/printcal_runner.py` | Modes initial / recalibrate / verify / imitation, per-channel targets, its own error catalogue. |
| applycal | `workflow/applycal_runner.py` | apply / remove / check. |
| The auto-prefill | `_check_for_cal_file`, `ui/tabs/tab_chart.py:3545-3573` | If `cal/<project>-cal.cal` exists, its path is filled into printtarg **-K** and **-I**, and a green line says so. |
| -K / -I mutual exclusion | `_connect_cal_mutex`, `ui/tabs/tab_chart.py:4788-4794` | Enabling one switches the other off. **Note the prefill does not leave both off — see D4.** |
| Glossary + file guide | `ui/dialogs/welcome_dialog.py:599`, `ui/file_guide.py:49,102,261,377` | "Calibration" is defined; `cal/` is described. |

**So the request is almost entirely a navigation-model change.** The one thing
Sebastian asks for that already works is the prefill: *"the path to said file
would then automatically be prefilled in the 2 options in create chart tab"* —
that is `_check_for_cal_file`, shipped. Its trigger needs widening (§4.6).

### The Argyll flow, from the 3.5.0 sources

```
targen -s20 -f0 -e0 -B0        → cal/<project>-cal.ti1
printtarg -r …                 → cal/<project>-cal.ti2 + _NN.tif
[print with colour management OFF]
chartread                      → cal/<project>-cal.ti3
printcal -i | -r | -e          → cal/<project>-cal.cal
   printcal.c:90-93, and :110 — "prevcal  Base name of previous .cal file for
   recal or verify", loaded at :1014.
targen/printtarg -K cal | -I cal → the PROFILING chart, calibrated
   printtarg.c:2962-2963 — "-K … Apply printer calibration to patch values and
   include in .ti2"; "-I … Include calibration in .ti2 (but don't apply it)".
chartread → colprof             → runs/runN/<project>.icc
applycal -a                     → runs/runN/calibrated.icc
   applycal.c:65-67 — -a apply/re-apply, -u remove, -c check.
```

---

## 2. The one fact the design must follow

**A calibration belongs to the printer, paper and ink — not to a profile
attempt.** That is why `cal/` sits at project level and every run shares it, and
why `printcal -r` and `-e` need the *previous* `.cal` as an input. A per-run
calibration would mean re-linearising the printer for every profile attempt,
which is neither what the folder model says nor what the workflow is for.

Everything in §3 and §4 follows from this.

---

## 3. Seven defects found while researching (evidence, not opinion)

D1–D3 were reproduced with the real classes and real files; D4 and D5 turned up
while building the mockups in §12, in the real running app; D6 came out of
answering Sebastian's question in §13. None is speculative, and none is fixed —
this is a design draft.

### D1 · Regenerating a calibration chart deletes the calibration, silently

`ChartCreator.create()` calls `proj.calibration.reset()` for a cal target
(`workflow/chart_creator.py:595`), and `Calibration.reset()` is
`shutil.rmtree(cal/)` (`core/file_manager.py:380-384`). Measured:

```
cal/ before:  <project>-cal.cal, <project>-cal.ti2, <project>-cal.ti3
Calibration.reset()  →  GONE
old/ archive anywhere in the project:  none
Calibration has old_dir:         False
Calibration has archive_to_old:  False
```

The `.cal` **is** the user's calibration — the thing measured over a whole
printed chart — and nothing warns, and nothing is archived. Runs got exactly
this protection in #130 §2a/§4 ("archive, never delete", and
`Run.reset_chart_artefacts` deliberately keeps measurement and profile,
`core/file_manager.py:778-800`); `cal/` never did.

It also breaks the workflow one step later: with the previous `.cal` deleted,
printcal's **Re-calibrate** and **Verify** modes have no `prevcal` to read
(printcal.c:110, 1014) and can only fail — ChromIQ even has the error text
ready, `workflow/printcal_runner.py:44-49`.

### D2 · The §4 warning describes the wrong files for a calibration build

`_on_generate` calls `_confirm_displacing_results()` unconditionally
(`ui/tabs/tab_chart.py:7953`), and that guard assesses `project.current_run()`
(`:8804`, `:8817`). It never asks whether the build is going to `cal/`. Measured
on a project whose run holds a 9-patch measurement and a profile, with the build
targeted at `cal/`:

```
assess_profiling_chart(run) → warn=True, readings=9, has_profile=True
```

So the user is warned that **the run's** measurement and profile are about to
move to `old/` — while the build touches only `cal/` and leaves them alone
(confirmed: both files still there afterwards). A false warning in one
direction, silence about the real loss in the other.

### D3 · A calibration chart cannot be got back after the session

`project.calibration` is read in exactly four places
(`ui/main_window.py:1403`, `workflow/chart_creator.py:595-596`,
`core/file_manager.py:1701,1712`). Re-opening a project restores the *run's*
chart into Print and Measure (`ui/main_window.py:1387-1391`) and the cal `.ti3`
into tab 4 (`:1402-1404`) — but never the calibration **chart**. Its pages are
on disk in `cal/`, and no selection in the app can bring them back: the only
route is to generate it again, which (D1) deletes the calibration you already
made.

`_resolve_target_chart` (`ui/tabs/tab_chart.py:8983-9012`) is the function that
maps the bar's selection to a chart, and it knows only two branches — the run's
chart and the verification chart. **That is exactly where a Calibration target
belongs**, which is the shape of the fix.

---

### D4 · The auto-prefill silently switches **-I** on

Found by building the mockups, not by reading: `ParameterWidget.set_value`
**ticks the enable checkbox** for a `file_path` parameter when the value is
non-empty (`ui/parameter_widget.py:175-178`). `_check_for_cal_file` sets `-K`
first and `-I` second, and the mutex then switches `-K` back off — so the
calibration ends up **included but not applied**, chosen for the user, while the
status line says only *"auto-filled into -I and -K fields below"*.

The mockup `04-create-chart-prefill.png` is the real panel: `-I` is ticked, `-K`
is not. Either default is defensible — `-I` changes nothing about what is
printed — but the user is not told a choice was made for them, and the two
options mean different things on paper (printtarg.c:2962-2963). §4.6 and Q7
cover it.

### D5 · The `-I` row's label is clipped

Same mockup: *"Include Calibration File (no"* — the label is cut mid-word where
`-K`'s fits. A one-line width fix, but it is the row a user is being asked to
choose between.

### D7 · The page-based auto patch count is not disabled for a calibration chart

Measured 2026-08-05 in the running app, ticking "Create chart for calibration":

```
Auto patch count still ticked : True      ← nothing turns it off
Pages spin still enabled      : True
-f widget value               : 0         ← the toggle did set it…
-f widget enabled             : False     ← …but Auto owns the widget, so the 0 is cosmetic
```

`_on_cal_target_toggled` writes `-f 0` into a spinbox that Auto has disabled,
and at Generate `params.patches = estimate_patches(...)` (`:8210`) overwrites it
without ever consulting `cal_target` (computed 60 lines earlier at `:8151`).
The command preview reads the disabled widget and prints `-f0` while the build
uses the estimate, so the two disagree invisibly.

A calibration chart is a single-channel ramp; built this way it is a general
test chart with a ramp bolted on, which is not what printcal wants. Settled by
§4.2a.


## 4. The design

### 4.1 The bar

`Run type` gains a third value, **only** while `calibration_mode` is on:

```
Profile run: [ Project calibration ▾ ]   Run type: [ Calibration ▾ ]   ⓘ
```

- `RUN_TYPE_CALIBRATION = "calibration"` in `core/measurement_target.py`, with
  `MeasurementTarget.is_calibration()` beside `is_verification()`.
- When it is selected, **Profile run** shows one entry, *"Project calibration"*,
  and is disabled — because there is one calibration per project and no choice
  to make. Its tooltip says so in words. **The box has to be re-fitted for that
  label**: its floor is sized for `"Run 8 (overwrite)"`
  (`ui/measurement_target_bar.py:585-587`), and the first mockup clipped to
  *"Project calibratior"* until `_fit_box` was given the new text. The bar grows
  by 16 px, once, at construction. The **Verification** box hides, exactly
  as it does for Profiling.
- Turning the preference off while Calibration is selected drops the target back
  to Profiling, and the value disappears from the combo.
- The value is **not** persisted per run: `MeasurementTarget` is session state
  today (nothing in `RunMeta`, `core/file_manager.py:255-297`, records a run
  type), and this design keeps it that way. No schema change, no migration.

### 4.2 Create Chart

- The "Create chart for calibration" checkbox is **retired**; `Run type =
  Calibration` sets `ChartParams.cal_target`. `cal_target` is a transient field
  (`workflow/chart_creator.py:519`) — it is in no preset and no settings key —
  so nothing needs migrating.
- The calibration knob preset (`-f 0 -e 0 -B 0 -s 20`, `-G` off, `-r` on) moves
  from the checkbox's handler to the run-type switch, and **gains the half it
  was missing** — see 4.2a. It still restores the previous values when the
  target changes back, and now restores the tick states too.
- **The "targen parameters" section opens.** It starts collapsed
  (`ui/tabs/tab_chart.py:2426-2428`) because most charts never touch the patch
  recipe — but a calibration chart *is* the patch recipe: **Single Channel
  Steps** is the ramp being printed, and it decides how finely the calibration
  can describe each ink. Sebastian, 2026-08-04: *"the targen settings in create
  chart should not be collapsed so the user directly sees where to dial in the
  desired settings."* Opening it is not quite enough on its own — that row sits
  below the fold — so the panel also scrolls to it, which is what mockup 03
  shows.
- `_resolve_target_chart` gains a third branch returning `cal/`'s `.ti2`, `.ti1`
  and TIFFs — which **fixes D3 for free**: preview, Print and Measure all flow
  from that one function.
- `_confirm_displacing_results` learns the calibration case (**fixes D2**) and
  asks about the right files (§4.4).

### 4.2a The Auto counts, and putting them back (Sebastian, 2026-08-05)

> *"setting run type to calibration turns the auto settings off (choosing
> another runtype then should restore the auto options to how they were before
> → total patch count, white, black patches, grey axis steps). Single channel
> steps should be set to 20 on a calibration run by default like it is supposed
> to be now already and then also be reset to how it was before when the user
> sets another runtype again."*

**Switching to Calibration:**

| Control | targen | Becomes |
|---|---|---|
| Total Patch Count · Auto | `-f` | unticked **and disabled**, value `0` |
| White Patches · Auto | `-e` | unticked **and disabled**, value `0` |
| Black Patches · Auto | `-B` | unticked **and disabled**, value `0` |
| Grey Axis Steps · Auto | `-g` | unticked **and disabled**, value `0` |
| Single Channel Steps | `-s` | **`20`** |
| Pages | printtarg | disabled |

A calibration chart's size comes from the ramp, not from filling pages.
Disabled rather than merely unticked: a greyed box says *this is not yours to
set right now*, where an unticked one invites the user to tick it and get a
chart printcal cannot use.

**Switching away:** all six go back to exactly what they were — tick state and
value both, including a Single Channel Steps the user had set by hand.

`_pre_cal_snapshot` (`ui/tabs/tab_chart.py:3621-3636`) already does this for
the six targen *values*. It must also record the four **Auto tick states** and
the Pages enablement, because those are what actually decide the build — which
is D7.

**And the guard that is not a UI state.** `_on_generate`'s auto-patch estimate
(`:8210`) must skip when `cal_target` is set:

```python
if (self._current_mode() == "manual"
        and not cal_target_active                 # ← added
        and self._manual_auto_patches_check is not None
        and self._manual_auto_patches_check.isChecked()):
```

Belt and braces on purpose: the UI state is what the user sees, this guard is
what keeps the built command correct if any future path reaches Generate with
Auto still on. Without it the preview and the build can drift apart again in
silence — which is precisely how D7 stayed invisible.


### 4.3 Print and Measure

Nothing structural. Both already receive whatever chart Create Chart resolves
(`MainWindow._on_chart_generated`, `ui/main_window.py:512-535`). Two path
sniffs are replaced by the target — `ui/tabs/tab_measure.py:6386` and `:7288`,
`ui/main_window.py:569` currently ask *"is the .ti3's parent folder called
cal?"*, which is a guess that the run type states outright.

The existing "you can only measure an already created chart" guard
(`new_run_guard_message`, `core/measurement_target.py:198-223`) gets a
calibration wording: *"There is no calibration chart in this project yet."*

### 4.4 Data safety — `cal/` gets the same protection as a run (**fixes D1**)

- `Calibration` gains `old_dir` and `archive_to_old`, mirroring
  `Run` (`core/file_manager.py:716-748`).
- `Calibration.reset()` **archives** to `cal/old/<date>/` instead of deleting.
- Before regenerating a calibration chart, a §4-style window (draft text in
  §4.7) names what moves: the calibration chart, the calibration measurement,
  and — the part that matters — the `.cal` curves themselves, with what their
  loss costs (Re-calibrate and Verify need the previous `.cal`).
- The message belongs in the reviewed catalogue,
  `workflow/measurement_messages.py`, and in §M of the Unified Measurement
  Management model — not written into the tab. That rule is now enforced by
  `tests/test_message_catalogue.py`.

### 4.5 Tab 4 — which modules are offered

Exactly as Sebastian described:

| Run type | Calibration options | Modules shown |
|---|---|---|
| Calibration | on | **CREATE CALIBRATION FILE** only |
| Profiling | on | **BUILD PROFILE** + **APPLY CALIBRATION** |
| Profiling | off | Build Profile (the tab as it is without calibration mode) |
| Verification | either | unchanged — a verification never builds anything |

Implemented in `TabProfile.set_calibration_mode` / `_switch_cal_mode`
(`ui/tabs/tab_profile.py:628-652`) by hiding rather than disabling: a module
that cannot apply to the selected target is noise, and the header already
re-titles itself per mode.

**The Measurement Data frame loses its own load button.** Everywhere else the
loader moved to the header's upper-right — Build Profile's frame is already just
a label saying which file is selected (`ui/tabs/tab_profile.py:451-458`, *"The
load + reveal buttons now live in the header's upper-right"*). The Create
Calibration File module is the one place that kept an in-section loader
(`_pc_load_btn`, `:821-827`). Sebastian, 2026-08-04: *"Is this still needed here
as we moved the button out of this section for all other tabs and the build
profile module in this tab as well?"* It is not — the header's loader loads the
calibration measurement while this module is on screen, and the frame says which
file that is. Mockup 06 shows it gone.

**Not hidden, but explained:** if the user is in a Calibration target and tab 4
would be empty of anything actionable (no cal `.ti3` measured yet), the panel
says what to do rather than showing a dead button — the pattern agreed for #133.

**Tab 4 does not carry the bar** (it is shared by tabs 1–3 only), so nothing on
that tab would say which target its modules belong to. The mockup answers this
by re-titling the header — *"STEP 04 · CREATE CALIBRATION FILE / Calibration"*
against *"STEP 04 · CALIBRATE & PROFILE / Calibration & Profiling"* — which is
free, because the header already re-titles itself per mode
(`ui/tabs/tab_profile.py:634-640`). Q7 asks whether that is enough.

### 4.6 The prefill

`_check_for_cal_file` already fills `-K` and `-I`. Two gaps to close:

1. It is wired only to `_manual_target_name_edit.textChanged` and to
   `set_calibration_mode` (`ui/tabs/tab_chart.py:2711`, `:3531`). It must also
   run when a **project is opened**, when the **run type changes back to
   Profiling**, and when a **calibration has just been created** in tab 4 —
   which is precisely Sebastian's sentence *"If a user created a .cal file in
   such a calibration run and then switches to a profiling run…"*.
2. The green status line uses a hard-coded `color: #56d6a5`
   (`ui/tabs/tab_chart.py:2082`). It must be read from the palette so it is
   legible in light mode as well as dark.
3. **D4:** it must stop switching `-I` on silently. Two honest options, and Q7
   asks which: fill both values and leave **both off**, with the line saying
   *"Switch on the one you want — they cannot both be used at once"*; or switch
   **-K** on deliberately (the option that actually applies the calibration to
   what is printed) and say so in the same line. What it may not do is choose
   the weaker of the two without a word.

### 4.7 Draft user-facing text

Wording is a draft for review; it follows the house rules (outcome and
prerequisite first, no mechanism, real singular/plural, the exact UI element
named).

**Run type tooltip — the third bullet, added to the existing two:**

> • **Calibration** — measure a special chart that brings the printer itself to
> a known, repeatable state before any profile is built. It produces a
> calibration file (.cal) which every profile run of this project can then use.
> One calibration is shared by the whole project, so there is nothing to choose
> under "Profile run" while this is selected. This step is optional; use it when
> you want your printer to behave the same way today and in six months.

**"Profile run" while Calibration is selected (disabled box, its tooltip):**

> A calibration describes your printer, your paper and your inks — not one
> particular profile — so a project keeps exactly one, in its `cal` folder, and
> every profile run can use it. There is no run to pick here.

**Before a calibration chart is regenerated (the D1 window):**

> **This project already holds a calibration**
>
> Making a new calibration chart replaces the one this project has. What is here
> now moves to `cal/old/{date}/`, and nothing is deleted:
> {items}
>
> **What this costs you if you go ahead:** "Re-calibrate" and "Verify" in the
> Create Calibration File module both read the calibration you already have and
> compare the new readings against it. With it moved aside, the only mode left
> is "Initial" — a fresh start, with nothing to compare against.
>
> Your profile runs are not touched. Any profile already built with this
> calibration keeps working exactly as it does now.

*{items}, one line each, only for what is really there:* "• the calibration
chart and its printed pages" · "• the calibration measurement of {c} patches" ·
"• the calibration curves themselves ({name}.cal)".

**Measure, with a Calibration target and no chart yet:**

> There is no calibration chart in this project yet. Make one in the Create
> Chart tab with "Run type" set to "Calibration", print it with your printer's
> colour management switched OFF, then come back here to measure it.

**Dictionary — one new entry beside the existing "Calibration":**

> **Calibration run** — the round trip that produces your printer's calibration
> file: make the calibration chart, print it, measure it, then create the .cal
> from those readings. It is not a profile run — nothing is built from it — but
> every profile run in the project can use its result.

---

## 4a. The N-channel TIFF option — asked in the mockups

Sebastian, seeing it beside `-K` and `-I` in mockup 04: *"Is this (in general)
automatically enabled when the user creates charts for cmy+n devices?"* — and,
on my first answer: *"I don't even really understand why this is an option
because not setting it would give the user a tiff file that is useless for his
purpose."*

**First, a correction of my own.** I wrote that a >4-ink chart printed through
ChromIQ's own PostScript path "is RGB". That is wrong. `PostScriptGenerator`
picks its colour space from the channel count and has a **DeviceN branch** with
a tint transform for anything that is not 1, 3 or 4 channels
(`workflow/postscript_generator.py:208-233`), and the PDF path has the same
(`:417-431`). He was right to question it.

**Second, what the flag actually does — from the Argyll 3.5.0 sources, not from
assumption.** For a Device-N chart printtarg always renders **every** ink
channel: `nc = icx_noofinks(nmask)` (printtarg.c:1010-1016), and the renderer
writes `samplesperpixel = s->ncc` in both modes (render.c:403-421). The only
difference `-N` makes:

| | without `-N` (`ncol_2d`) | with `-N` (`ncol_a_2d`) |
|---|---|---|
| SamplesPerPixel | every ink | every ink |
| PhotometricInterpretation | `SEPARATED` | `SEPARATED` |
| ExtraSamples | not written | samples 5…N declared `EXTRASAMPLE_UNASSALPHA` |
| InkSet / InkNames | not written | not written |

(render.c:403-421 for the two branches, :455-456 for the ExtraSamples tag, and
:458-462 for the ink names — which neither mode writes, carrying Argyll's own
`~~99 should fix this` comment. `NumberOfInks` is never written either.)

**So the file is not truncated and not useless without it.** All the ink values
are in it both ways. What `-N` adds is a *declaration* that samples beyond the
fourth are unassociated alpha — which is how TIFF's SEPARATED photometric
accounts for components past the ink set, and therefore how a strict reader
knows what to do with them.

**And for ChromIQ's own printing it changes nothing**: the PostScript/PDF
generator reads the sample count from the image itself
(`postscript_generator.py:98`, `h, w, n_ch = arr.shape`), so both files print
identically.

**Where it can matter is in someone else's software** — a RIP or driver reading
the TIFF. Whether such a reader wants the extra samples declared as alpha, or
would rather have them undeclared, is a fact about that reader, and neither the
ChromIQ code nor the Argyll sources can tell us. That is why Argyll made it a
flag rather than a rule.

**Revised recommendation — surface it, do not decide it.** When targen's Device
Type has more than four inks (`-d6` and above), lift `-N` out of Expert Options
and put it beside Device Type, still defaulting to off, with a label and tooltip
that say plainly: every ink is written either way; tick this if the RIP or
driver you hand the TIFF to expects the extra inks declared as alpha channels;
ChromIQ's own printing does not need it. Auto-ticking it would be ChromIQ
guessing about a program it cannot see — and the guess is not free, because a
reader that honours ExtraSamples may treat those channels as transparency
rather than ink.

**The bigger gap, if N-channel charts are to be handed over at all:** neither
mode names the inks in the TIFF. A receiving RIP is told "SEPARATED, 7 samples"
and nothing about which ink is which; the order is the `.ti2`'s, which ChromIQ
also writes into `<stem>.channels.json`. Worth saying in the help text, and
worth a look before anyone relies on that hand-off.

**This is Q8.** Nothing in the calibration design depends on it.

---

## 5. The workflow, click by click, with file locations

Project `~/ChromIQ/My-Printer/`.

**A · Make the calibration** (Preferences → "Show calibration options" is on)

1. Tab 1 · **Create Chart**. Bar: `Run type` → **Calibration**. "Profile run"
   greys out and reads "Project calibration".
2. The calibration knobs are set for you (single-channel steps, no white/black
   filler, no randomisation). Press **Generate Chart**.
   → `cal/My-Printer-cal.ti1`, `.ti2`, `.channels.json`, `My-Printer-cal_01.tif`
   *If a calibration is already there, the §4.7 window asks first, and what is
   there moves to `cal/old/<date>/`.*
3. Tab 2 · **Print Chart** — colour management **off**. The pages are the ones
   from `cal/`.
4. Tab 3 · **Measure**. → `cal/My-Printer-cal.ti3`
5. Tab 4 · **Calibration & Profiling** opens on **CREATE CALIBRATION FILE**, the
   only module offered for this target, with the measurement already filled in.
   Mode "Initial" for a first calibration. Press it.
   → `cal/My-Printer-cal.cal`

**B · Build a profile that uses it**

6. Bar: `Run type` → **Profiling**, `Profile run` → **New run**. The `.cal` path
   appears in **-K** and **-I** with a line saying it was found. Enable **one**:
   -K applies the curves to the patch values, -I only records them (they are
   mutually exclusive, and ChromIQ enforces that).
7. **Generate Chart** → `runs/run1/My-Printer.ti1/.ti2/_01.tif`
8. Print (colour management off) → Measure → `runs/run1/My-Printer.ti3`
9. Tab 4 now offers **BUILD PROFILE** and **APPLY CALIBRATION**.
   Build Profile → `runs/run1/My-Printer.icc`
   Apply Calibration → `runs/run1/calibrated.icc`

**C · Six months later**

10. `Run type` → **Calibration** → the calibration chart is still there and
    shows in Print and Measure (D3 fixed). Print it, measure it, and in
    **CREATE CALIBRATION FILE** choose **Re-calibrate** — which reads the
    existing `.cal` and writes a new one, the old one archived to `cal/old/`.

---

## 6. Edge cases, and what must happen in each

| # | Case | Required behaviour |
|---|---|---|
| E1 | Calibration selected, no project loaded yet | Same as Profiling: Generate creates the project, and `cal/` inside it. |
| E2 | Calibration selected, then the preference is switched off | Target falls back to Profiling; the value leaves the combo; no files touched. |
| E3 | A project made before this feature, with a populated `cal/` | Nothing to migrate. Selecting Calibration finds and shows it. |
| E4 | A project made before this feature, with **no** `cal/` | Selecting Calibration shows the "no calibration chart yet" guidance. |
| E5 | Regenerating the calibration chart over a finished calibration | §4.7 window; everything to `cal/old/<date>/`; nothing deleted. |
| E6 | Measuring a calibration chart when `cal/` holds a complete `.ti3` | The §5 "starting over" rules apply unchanged — the same messages, against the calibration measurement. |
| E7 | A corrupt or empty calibration `.ti3` | Same as a run's: `M-CHART-CORRUPT` (already in the catalogue, pending approval). |
| E8 | Duplicate / Delete pressed with a Calibration target | Both are about runs. They grey out with a sentence saying which Run type they need — the pattern `duplicate_state` already uses (`ui/measurement_target_bar.py:427-440`). |
| E9 | Restore Used Chart with a Calibration target | Out of scope for the first version: no chart snapshot is kept for `cal/`. The button greys with a reason. Adding snapshots later is a small, separate step. |
| E10 | printcal Re-calibrate / Verify with no previous `.cal` | Already handled: `no_prev_cal`, `workflow/printcal_runner.py:44-49`. With E5 in place, the previous `.cal` is in `cal/old/` and can be pointed at. |
| E11 | The `.cal` is deleted outside ChromIQ while prefilled | The prefill only fills a value; the flag is off unless the user enables it. Enabling with a missing file must say so rather than let printtarg fail. |
| E12 | Two projects, one calibrated, one not | `_check_for_cal_file` resolves per project root — already correct. |
| E13 | Verification target while calibration options are on | Unchanged in every respect. |

---

## 7. Module map — reuse against new

| Module | Change | Size |
|---|---|---|
| `core/measurement_target.py` | `RUN_TYPE_CALIBRATION`, `is_calibration()`, `status_label`, a `calibration_blocked_reason` beside the verification one | small, pure, unit-testable |
| `core/file_manager.py` | `Calibration.old_dir`, `.archive_to_old`, `reset()` archives | small, and it is the D1 fix |
| `ui/measurement_target_bar.py` | third combo value, gated on the preference; "Profile run" fixed + disabled; button states | medium |
| `ui/tabs/tab_chart.py` | retire the checkbox; run-type drives `cal_target` and the knob preset; third branch in `_resolve_target_chart`; calibration case in `_confirm_displacing_results`; widen the prefill trigger; palette colour for the status line | medium — the bulk of the work |
| `ui/tabs/tab_profile.py` | module visibility by target | small |
| `ui/tabs/tab_measure.py`, `ui/main_window.py` | ask the target instead of sniffing the folder name (3 sites) | small |
| `workflow/measurement_messages.py` + §M of the model | one new message + its `{items}` lines | small, needs review before it ships |
| `workflow/chart_integrity.py` | `assess_calibration_chart()` | small, pure |
| `workflow/chart_creator.py` | unchanged — it already routes on `cal_target` | none |
| `workflow/printcal_runner.py`, `applycal_runner.py` | unchanged | none |
| `ui/file_guide.py`, `welcome_dialog.py` | `cal/old/` in the guide; one Dictionary entry | small |

**Nothing new is invented**: no new Argyll wrapper, no new folder concept, no
new persistence.

---

## 8. Test plan

*Pure logic (no Qt), the way #130's decision modules are tested:*

1. `is_calibration()` / `status_label()` for all three run types.
2. `calibration_blocked_reason`: no project · no `cal/` · chart but no
   measurement · complete.
3. `assess_calibration_chart`: empty `cal/` → no warning; chart only → none;
   chart + `.ti3` → warn; + `.cal` → warn naming the curves; corrupt `.ti3` →
   the corrupt message.
4. `Calibration.reset()` **archives**: files land in `cal/old/<date>/`, the
   folder is re-created empty, and a second reset does not overwrite the first
   archive.
5. The §4 guard does **not** report the run's measurement for a calibration
   build, and does report the calibration's.

*Wiring (source-level, as `tests/test_chart_integrity.py` does):*

6. Every path that generates a chart asks first, calibration included.
7. Tab 4 shows exactly the modules of §4.5's table, for all four rows.
8. No tab sniffs `parent.name == "cal"` any more.

*Rendered:*

9. The new window rendered in both variants — with and without a `.cal` — and
   checked for a placeholder and for stray Markdown (the beta.129 lesson).

*On screen, driving the real app:*

10. The whole of §5 A→C on a real project, watching both the interface and the
    folder: that `cal/old/<date>/` fills, that `runs/` is untouched, and that
    the calibration chart comes back after closing and re-opening the project.

*i18n:* English placeholders during beta; the twelve catalogues before GA.

---

## 9. Decisions — answered 2026-08-04, with the reasoning kept

Sebastian answered 1, 2 and 6 outright and asked for a recommendation on the
rest. Recommendations are marked **R**; they stand unless he says otherwise.

**1 · The label is "Calibration."** ✅ *Decided.* Short enough not to widen the
combo in any language, and it matches the Dictionary entry and the folder name.

**2 · The "Create chart for calibration" checkbox is retired.** ✅ *Decided.*
Two controls for one state is the confusion this feature removes; `cal_target`
is transient, so nothing needs migrating. Its tooltip — which still promises
`cal_` filename prefixes that #127 removed — goes with it (§14, item 6).

**3 · Restore Used Chart for a calibration — R: include it, in the first
version.** The chart snapshot is what makes the button work, and the helper
already exists (`workflow/verify_chart_snapshot.py`); a calibration chart would
be snapshotted at the same moment as any other — when its measurement starts.
Two reasons to do it now rather than later: the calibration chart is the one
chart whose loss is *unrecoverable today* (D3 — it cannot even be reloaded), and
leaving it out means the button needs an exception to explain, which costs a
sentence in a tooltip every user reads and buys nothing.

**4 · A project with a `cal/` while the preference is off — R: say it in the
file guide, and nowhere else.** The interface should not advertise a mode the
user has switched off; but "where are my files?" must always be answerable, and
the file guide is exactly where that is asked. With D6 fixed the hidden
calibration no longer *does* anything, so there is nothing to warn about — only
something to find.

**5 · Recording which `.cal` a run was built with — R: yes, one `RunMeta`
field.** It is the only way to answer "was this profile built on the calibration
that is in the project now?" once a calibration has been replaced — and with D1
fixed the older ones live on in `cal/old/<date>/`, so a stored stem stays
resolvable instead of dangling. Migration is nothing: absent means unknown,
which is the honest state of every run built before it. It also makes a future
warning possible ("this run was built on a calibration that has since been
replaced") without another schema change. Cost: a field, one write at build
time, one line in the file guide.

**6 · D1 ships with the feature, not before it.** ✅ *Decided* — "all together
when we build it."

**7 · The `.cal` prefill — R: gate it on the preference, fill both fields,
switch neither on, and say so.** Three parts, one principle: ChromIQ may offer,
not choose. `-K` reprints every patch value through the calibration and `-I`
only records it — that is a decision about what lands on paper, and the user is
the one who knows whether their printer or RIP applies curves itself. Switching
`-I` on silently (D4) makes that choice for them; doing it while calibration
options are switched off (D6) makes it invisibly. The status line becomes:
*"Calibration file found: {name} — filled into the -K and -I fields below.
Switch on the one you want; they cannot both be used at once."*

**8 · Should `-N` follow the device type? — R: surface it, don't decide it.**
Corrected after Sebastian pushed back, and the correction went both ways: my
"the PostScript path is RGB" was wrong, and "without it the TIFF is useless" is
not what Argyll does either — every ink is written in both modes, and `-N` only
declares samples 5…N as unassociated alpha. Full evidence in §4a. So: lift the
control out of Expert Options when the device type has more than four inks,
explain it, and leave the choice with the user, because the answer depends on
the RIP at the other end and nothing in either codebase knows it.

## 10. Rating of this design

| | Score | Why |
|---|---|---|
| Correctness | 9 | Every claim about current behaviour was run, not read. The model follows the one fact in §2, and the three defects are reproduced with real files. Held back from 10 until Q1–Q6 are answered. |
| Robustness | 8 | §6 enumerates thirteen cases including old projects and external deletion; the risk that remains is the one in §11 — the bar is shared by three tabs and has been a source of sequencing bugs before. |
| Maintainability | 9 | Reuses `MeasurementTarget`, `chart_integrity`, the message catalogue and the folder model; adds no new persistence and no new Argyll wrapper. One transient checkbox is retired, and the folder-name sniffing goes with it. |
| Efficiency | 9 | No new process runs, no new I/O on any hot path; the resolution branch is a stat of `cal/`. |

## 11. The main risk, stated plainly

**The bar is shared by Create Chart, Print and Measure, and adding a value to it
touches every guard that asks "which run am I on?".** #130's history is mostly
sequencing bugs of exactly that kind — a selection changing under a tab that had
already decided what it was working on. The mitigation is the one that worked
there: put every decision in a pure function with unit tests
(`chart_integrity`, `measurement_target`), leave the tabs to rendering, and drive
the finished thing on screen before calling it done.

The second risk is smaller and worth naming: **a user who has been ticking
"Create chart for calibration" will find it gone.** The release note has to say
where it went, in one sentence, without a history lesson in the interface itself.

---

## 12. Mockups — the real app, in the proposed state

`scripts/mockup_calibration_run_type.py` launches the **real** `MainWindow` with
the real fonts, the real theme and the real widgets, puts the live widgets into
the proposed state and grabs them. Nothing is drawn: only the state is invented,
never the styling, so what these show is what the app would look like at the
pixel. Re-run it after any change to the design.

| Image | What it shows |
|---|---|
| `01-bar-today-profiling.png` | The bar as it is today, for comparison. |
| `02-bar-proposed-calibration.png` | Run type = **Calibration**: the fixed, disabled "Project calibration", no Verification box, the three run buttons greyed with reasons. |
| `03-create-chart-calibration.png` | The whole window in a Calibration target — the bar, the retired checkbox, the empty-preview guidance written for this case, and the **targen section open at "Single Channel Steps"**, the setting that decides the calibration. |
| `04-create-chart-prefill.png` | **Today's** prefill, unmodified: the status line, and `-I` already switched on with `-K` off — the evidence for D4, and the clipped `-I` label of D5. |
| `05-replace-warning.png` | The §4.7 data-safety window, rendered as the real `QMessageBox` the §4 windows use. |
| `06-tab4-calibration-run.png` | Tab 4 in a Calibration target: **CREATE CALIBRATION FILE** alone, header re-titled, and the Measurement Data frame **without its own load button** — the header's loader is the one button, as everywhere else. |
| `07-tab4-profiling-run.png` | Tab 4 in a Profiling target with calibration options on: **BUILD PROFILE** + **APPLY CALIBRATION**. |

Two of this document's findings came out of building them rather than out of
reading the code (D4, D5), and one layout consequence did too — the Profile-run
box has to be re-fitted for its new label, or it clips (§4.1). That is the
argument for making mockups from the running app rather than from a drawing.

---

## 13. With calibration options switched OFF

**Short answer: yes for the feature, no for today.** The design changes nothing while the preference is off — but ChromIQ already does one thing there that it should not, and it is worth fixing whether or not the feature is greenlit.

**What the feature would do with the preference off:** nothing at all. The third Run type is only in the combo while the preference is on; `_resolve_target_chart`'s calibration branch is only reached by that target; the §4 calibration warning only fires for a build routed to `cal/`; and the archive-instead-of-delete fix (D1) only applies to a calibration build, which needs the preference. The retired checkbox was already hidden. A project that carries a `cal/` folder is untouched and still opens exactly as it does now.

**What ChromIQ does today with the preference off — D6.** I set a project up with a `cal/…-cal.cal` on disk, left "Enable calibration options" **off**, and typed the project name into "Printer profile project name":

```
calibration_mode: False | cal group visible: False | status line visible: False
-K enabled: False | -I enabled: True
printtarg would receive: ['-I', '…/My-Printer/cal/My-Printer-cal.cal']
```

`_check_for_cal_file` is wired to the name field unconditionally (`ui/tabs/tab_chart.py:2711`), and `set_value` on a `file_path` parameter **ticks its enable box** (`ui/parameter_widget.py:175-178`). So the chart is built with the calibration embedded in its `.ti2` — silently, because the green line that would say so lives inside the group the preference hides.

`-I` embeds the curves without applying them, so nothing about the printed sheet changes; but the `.ti2` carries a calibration the user never chose and cannot see, and `colprof` can reference it later. **The fix is one line either way: gate the prefill on the preference.** That, plus Q7's decision, is what makes "unchanged when off" actually true.

---

## 14. Help text this would touch, with the wording drafted

Ten places mention calibration. Four need new words, four need a correction they already deserve, and two are additions. All of it is drafted here so nothing is invented at implementation time.

### A · Needs new wording because of the feature

**1. Settings → "Enable calibration options" ⓘ** (`ui/dialogs/settings_dialog.py:440`). Its last paragraph promises the control this feature retires — *"a calibration target option appears in Create Chart"*. Replace that paragraph with:

> When active: the guided modes in all tabs are hidden, **"Calibration" is added to the "Run type" list** in the bar above the tabs, and the Calibration & Profiling tab gains the Create Calibration File and Apply Calibration modules. Your projects are not changed by switching this on or off — a calibration you have already made stays in the project's "cal" folder either way.

**2. "Run type" ⓘ** (`ui/measurement_target_bar.py:596`) — a third bullet after Profiling and Verification:

> • **Calibration** — measure a special chart that brings the printer itself to a known, repeatable state before any profile is built. It produces a calibration file (.cal) which every profile run of this project can then use. One calibration is shared by the whole project, so there is nothing to choose under "Profile run" while this is selected. This step is optional; use it when you want your printer to behave the same way today and in six months.

**3. "Profile run and Run type" ⓘ** (`ui/measurement_target_bar.py:629`) — it currently describes two values. Second paragraph becomes:

> "Profile run" picks which profile build you're working on (or a new one). "Run type" switches between building the profile (Profiling), checking a finished profile (Verification) and preparing the printer itself (Calibration). Verification adds a box for choosing a dated check; Calibration replaces the "Profile run" choice with the project's one calibration, because there is only ever one.

**4. "Profile run", while Calibration is selected** — the box is disabled, so its tooltip is all the user has:

> A calibration describes your printer, your paper and your inks — not one particular profile — so a project keeps exactly one, in its "cal" folder, and every profile run can use it. There is no run to pick here.

**5. Restore Used Chart / Duplicate / Delete ⓘ** — each already explains itself per Run type; each gains one line:

> RUN TYPE = CALIBRATION — *(Restore)* a calibration chart keeps no stored copy, so there is nothing to put back. *(Duplicate)* duplicating works on a profile run; switch "Run type" to "Profiling". *(Delete)* a project has one calibration and it is replaced rather than deleted — making a new calibration chart moves the old one to "cal/old".

### B · Corrections these already need, feature or no feature

**6. "Create Chart for Calibration" ⓘ** (`ui/tabs/tab_chart.py:2062`) — retired by the feature, and **wrong since #127**: it promises *"Output files are prefixed with 'cal_' (e.g. cal_MyChart.ti1)"* and *"The resulting cal_*.ti3 file"*. There are no `cal_` prefixes any more; the files are `cal/<project>-cal.*`. If the feature is not greenlit, this paragraph still has to be corrected to:

> The calibration chart and its measurement are saved in this project's "cal" folder, as `<project>-cal.ti1`, `-cal.ti2`, `-cal.ti3` and `-cal.cal`. They are shared by every profile run of the project.

**7. Calibration & Profiling header ⓘ** (`ui/tabs/tab_profile.py:171`, step 1 and step 2). Step 1 says *"with 'Calibration Target' ticked on tab 1"* → **"with 'Run type' set to 'Calibration' in the bar above the tabs"**. Step 2 ends *"ChromIQ auto-fills these fields when it finds a matching cal_ file"* → **"ChromIQ fills both fields in when the project already has a calibration, and tells you which one it switched on."** (Which is the honest sentence only after Q7 is answered — see D4.)

**8. printtarg -K and -I ⓘ** (`data/parameters.yaml:886` and `:915`) — both are accurate about what the flags do and say nothing about the auto-fill. One sentence each, at the end:

> When this project already has a calibration, ChromIQ fills this field in for you. **-K** and **-I** cannot both be active: switching one on switches the other off.

### C · Additions

**9. Dictionary** (`ui/dialogs/welcome_dialog.py:599`) — beside the existing "Calibration" entry:

> **Calibration run** — the round trip that produces your printer's calibration file: make the calibration chart, print it, measure it, then create the .cal from those readings. It is not a profile run — nothing is built from it — but every profile run in the project can use its result.

**10. File guide** (`ui/file_guide.py:261`) — the `cal/` row gains its archive:

> `cal/old/` — earlier calibrations. Making a new calibration chart moves what was there into a dated folder here rather than deleting it, so an earlier .cal can always be read back — which is also what "Re-calibrate" and "Verify" compare against.

**Not touched:** the guided Create Chart / Measure / Build Profile help cards, which never mention calibration; and the Measure tab's no-chart guidance, which is Run-type-aware already and gains its calibration case with the rest of the feature.
