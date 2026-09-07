# Agent B — on-screen findings (staged; appended after every journey)

Agent B, 2026-09-04/05. Tree `/Users/Basti/develop/ChromIQ` @ `feature/engine-accuracy-challenge`,
no file outside `scripts/engine_challenge/` edited. Every journey ran the REAL app
(`Harness.boot()`: real `MainWindow`, Fusion + `WinButtonLayoutStyle`, real fonts, real
event filters, visible window) on a sandbox: `CHROMIQ_SETTINGS_FILE`, `CHROMIQ_PRESETS_DIR`
and `custom_output_path` all under `~/Desktop/ChromIQ-engine-challenge/sandboxes/B-<journey>/`.
Nothing under `~/ChromIQ` was opened.

How to read "measured ON SCREEN": the window was visible on the display, the clicks were
`QTest.mouseClick` at the widget's centre, and the picture cited is `QWidget.grab()` of the
window or dialog as painted (real style). `screencapture` was ALSO taken but on this machine
the app's window lands on another Space, so every whole-screen capture shows the desktop
(`work-B/B1/05-accuracy-popup-screen.png` = wallpaper); I do not cite those. Popups are
grabbed as their own top-level widget (`combo.view().window().grab()`).

Drivers: `scripts/engine_challenge/drive_B_common.py` (generator-driven stepper so a journey
keeps clicking while a modal's `exec()` loop runs), `drive_B1_switch_on.py`, … Logs and
raw pictures: `~/Desktop/ChromIQ-engine-challenge/work-B/<journey>/`.

Harness changes (I own `harness.py`): ONE — `Harness(language="de")` (B9): `boot()` now writes the
`language` key and calls `core.i18n.set_language` + `install_qt_translator` before the MainWindow
is built, exactly as `main.py` does; default `"en"`, so every earlier journey is unaffected.
Everything else drives through `drive_B_common.py` on top of the harness. All `drive_B*.py`
files pass `tests/test_encoding_is_named.py` (49 passed) after the coordinator's note.

---

## B1 — the switch-on journey through the real Preferences window

Driver `drive_B1_switch_on.py` (sandbox `B-B1`, fresh: `profile_engine_beta` unset,
`gammap_mode=fast`). Log `work-B/B1.log`.

Click by click:
1. Build Profile tab → MANUAL. `_m_engine_rows_widget`: `isVisible()=False`, `isHidden()=True`
   (picture `work-B/B1/01-manual-before.png`: Profile Core, Measurement & Smoothing, no engine rows).
2. Clicked the masthead gear (`tooltip_btn`, tooltip "Preferences (⌘,)") → modal
   `SettingsDialog` "ChromIQ Preferences".
3. Clicked the **Beta** tab (index 8) on the tab bar. Engine box unticked, Accuracy row hidden
   (`02-prefs-beta-before.png`).
4. Clicked "ChromIQ profile engine (beta)". A `QMessageBox` appeared (668×702; window title is
   EMPTY on macOS — Qt drops message-box titles there, so the `setWindowTitle("ChromIQ Profile
   Engine (beta)")` never shows). `03-consent.png`: the full text is in the picture, from "Great
   choice —" to "Enable it at your own risk and give it a try?" (2231 chars, label 606×608,
   wordWrap on, visible region non-empty). Buttons "ENABLE THE ENGINE" 172×42 (text needs 132 px,
   has 156) and "KEEP USING COLPROF" 182×42 (142/166): both readable, nothing clipped.
   Clicked "Enable the engine" (recorded).
5. Box ticked, Accuracy row appeared inside the still-open Preferences (`04-prefs-after-consent.png`).
6. Clicked the Accuracy combo → popup opened (`view.isVisible()=True`); clicked the row
   "Maximum accuracy" in the popup list → combo shows "Maximum accuracy" / data `accurate`
   (`06-prefs-max-accuracy.png`). Popup picture: see B1b below (`12-accuracy-popup-widget.png`).
7. Clicked the Accuracy ⓘ → help dialog "Accuracy" 680×697 (`07-accuracy-help.png`, whole text
   readable, CLOSE button). Closed it (recorded).
8. Clicked OK. Modal gone; `settings.ini`: `profile_engine_beta=True`, `gammap_mode=accurate`.
9. WITHOUT touching the tab bar (Build Profile was the current tab the whole time, mode still
   MANUAL): `_m_engine_rows_widget.isVisible()=True`, `isHidden()=False`, geometry
   (10,148,1636×106) inside the Manual group — the refresh on Settings close works
   (`main_window._open_settings` calls `_refresh_engine_rows()` after `dlg.exec()`).
   BUT `visibleRegion().isEmpty()=True` for the widget and all four rows: their global y is
   973…1055 px on a 1050 px window — they are **below the fold of the Manual scroll area**.
   `08-manual-after.png` shows exactly what the user sees after OK: Profile Core, Measurement &
   Smoothing, then the cut-off; not one engine row in the picture.
10. Clicked the Spectral-physics ⓘ (its dialog opened, `09-spectral-help.png`), closed it.
11. GUIDED: no engine rows anywhere (`10-guided-after.png`); they live in the Manual group only.

Dialogs I clicked: consent → "Enable the engine"; Accuracy help → Close; Spectral help → Close.
Harness watchdog: not armed for this journey (`modals_answered=[]`).

### B-01 · OK · consent dialog (ON SCREEN)
Complete text, readable buttons, nothing clipped (`03-consent.png`). Two wording notes for the
orchestrator, not defects: (a) "on our test charts the two build profiles that measure so close
you shouldn't be able to tell them apart" is not a sentence (the verb is missing: "the two build
profiles that measure…"); (b) the box has no title on macOS, so "ChromIQ Profile Engine (beta)"
is never seen — harmless, but the first line of the body is the only heading the user gets.

### B-02 · IMPROVEMENT · the four rows appear on OK, but out of sight (ON SCREEN)
The Settings-close refresh is real (`isVisible()` flips to True with no tab change), and the
critic's worry about `showEvent` is answered. What the user actually sees, though, is
`08-manual-after.png`: nothing changed on the screen in front of them, because the rows are
appended after "Measurement & Smoothing" at y≈973–1055 in a 1050 px window and the Manual panel
has to be scrolled to reach them. Nothing announces that "Maximum accuracy" just added four
options. Suggestion: either scroll them into view / flash the group once when the refresh turns
them on, or put a one-line hint in the Build box ("Maximum accuracy adds four options under
Manual — see Colour tables"). Measured: `visibleRegion().isEmpty()` for `_m_spectral_cb`,
`_m_iccver_combo`, `_m_noise_cb`, `_m_render_combo`; picture B1b `11-manual-rows-scrolled.png`
shows them once scrolled.

### B-03 · INCONSISTENCY · the Accuracy tooltip's time claims (READ on screen, times from logs)
Text on screen (`07-accuracy-help.png`), verbatim:
* Fast: "It finishes in a few seconds".
* Bit-exact: "expect up to a minute or two, and somewhat more for multi-ink printers".
* Maximum accuracy: "Expect the build to take several minutes longer, especially at the
  higher quality settings."
Against what this machine does on the 924p chart, q=m: fast **101 s** (`builds/baseline-accurate-924p.log`,
critic S04), accurate **53–56 s** fresh process (`builds/baseline-accurate-924p-freshprocess.log`,
`builds/smoke-harness-run5.log`: 56 s on screen), bit-exact on ≤4 inks = colprof directly (critic
M1: 2.2 s at -ql). So the slow one is the one the tooltip calls seconds, and the "several minutes
longer" one is the fastest of the three engine paths on RGB. My own fresh-launch timings for all
three follow in B10. Sentences to rewrite: the three quoted above, plus the closing "even the
slowest choice only costs you those extra minutes once" (there are no extra minutes).

### B-04 · INCONSISTENCY · other tooltip promises to be held against B3/B5 (READ on screen)
Recorded here, verdict in the journey that tests each:
* Engine tooltip (Beta tab): "If a build needs something only colprof has … that build is quietly
  handed to colprof and the log tells you why." → B5 failure case (observer 2015_2, critic N03).
* Engine tooltip: "Its colour rendering is computed by ChromIQ's own port of Argyll's
  gamut-mapping algorithm." — in Maximum accuracy on ≤4 inks the rendering comes from a real
  colprof run (the log line "Saturation table: matching colprof's rendering (this runs Argyll
  colprof once in the background)" in every accurate build, B2). The sentence describes Fast only.
* Spectral physics row: "RGB printer drivers … there this option simply does nothing." → does the
  log say so? (B3)
* Noise row: "the log always tells you which way it went" → B3.
* ICC version row: "a twin ending in \"-v4.icc\" lands right next to it … Installing and the rest of
  the ChromIQ workflow keep using the v2 file." → B5 (archive / delete / File guide).
* Out-of-gamut row: "Only applies while the intent overrides (-t / -T) are unset" → B3 (N11).

### B1b — restart on the same sandbox (`drive_B1b_rows_after_restart.py`, ON SCREEN)
New process, same `settings.ini`: `profile_engine_beta=true`, `gammap_mode=accurate` came back;
MANUAL rows visible after scrolling the Manual panel (`FadeScrollArea` scrolled to 284/916):
`work-B/B1/11-manual-rows-scrolled.png` shows "Spectral physics model", "ICC profile version:
Version 2 (most compatible)", "Measurement noise handling", "Out-of-gamut rendering:
Argyll-matched (recommended)" — sitting INSIDE the "Color Science" group between "Black
generation (-k)" and "Source viewing (-c)", with no heading of their own and no flag hint in the
label (every neighbour carries one: "(-i)", "(-o)", "(-f)", "(-k)", "(-c)"). The Accuracy popup
grabbed as a widget: `12-accuracy-popup-widget.png` — three entries, "Maximum accuracy"
highlighted. Preferences closed with Cancel (recorded).

### B-05 · IMPROVEMENT · the four engine rows have no home of their own (ON SCREEN)
`11-manual-rows-scrolled.png`: "ICC profile version" is not colour science, and nothing in the
group says these four exist only because of Preferences → Beta → Maximum accuracy. A user who
later switches Accuracy back to Fast sees them vanish from the middle of Color Science with no
trace. A sub-heading ("Maximum accuracy (ChromIQ engine)") or their own group would say what they
are and why they come and go.

---

## B2 — Guided + accurate, then Manual with identical settings

Driver `drive_B2_guided_vs_manual.py` (sandbox `B-B2`, engine + accurate set at settings level).
Log `work-B/B2.log`; both build logs `work-B/B2/guided-log.txt`, `manual-log.txt`.

Click by click: open project (the measurement follows the bar: label shows
`…/Real-924/runs/run1/Real-924.ti3`, Build enabled) → GUIDED is the default → clicked BUILD
PROFILE → pictures at 3 s / 15 s / 40 s → "Profile Built" appeared after 57 s → clicked Done
(recorded) → clicked MANUAL → `ProfileParams` diff vs Guided: `{}` (identical) → BUILD PROFILE →
"Profile Built" after 9 s → Done (recorded).

What the pictures show (`work-B/B2/guided-building-15s.png`): headline "Working hard…", "Good
things take time.", the spectrum bar labelled "BUILDING" left and "CHROMIQ ENGINE" right, the
button "BUILDING PROFILE…", log tail
`26% · ~30s left · Gamut mapping (maximum accuracy): rendering intents matched to ArgyllCMS colprof.`
then `78% · ~20s left · Saturation table: matching colprof's rendering (this runs Argyll colprof
once in the background)…`. `guided-modal-Profile_Built.png`: "Your ICC profile has been built
successfully. Saved to: …/Real-924.icc", four buttons (Install on this Mac / ← Use as
Pre-conditioning / Check Profile Quality → / Done) — nothing about the engine or the mode.

### B-06 · GAP · Guided never says "Maximum accuracy" where a user looks (ON SCREEN)
The first log line is "Building with the ChromIQ profile engine (beta)…", the bar says "CHROMIQ
ENGINE", the finished window says nothing. The only place the mode is named is one mid-log line
("Gamut mapping (maximum accuracy): …") that scrolls by at 26 %. Guided has no engine rows, so
the four options are silently at their defaults (Spectral off, v2, Noise off, Argyll-matched) and
nothing tells the Guided user that Manual has more. Suggest: the first log line and the bar label
carry the mode ("ChromIQ engine · Maximum accuracy"), and the Profile Built window says which
builder made the file.

### B-07 · OK · Guided and Manual build the same profile (ON SCREEN + bytes)
Same `ProfileParams` (diff `{}`); `icc_tagdiff.py guided.icc manual.icc`: 17 tags all
byte-identical (A2B0/1/2, B2A0/1/2, gamt, wtpt, bkpt, targ, desc, …), only the header date differs.

### B-08 · INCONSISTENCY · the progress percentage and ETA (ON SCREEN, `guided-log.txt`)
26 % → 78 % in the same second (the saturation-table stage is entered at 78 % before colprof has
run), then **78 % with "~20s left" for 45 s** (+9 s … +54 s), then 92 % and "almost done" for the
last 3 s. The ETA went UP once (+4 s "~20s left", +9 s "~30s left") and is right by accident at
the end. In the second build (oracle cached: "Saturation table: reusing the colprof rendering
matched earlier in this session.") the bar ends at 78 % and jumps to the modal. The number never
goes backwards; it simply stops meaning anything between 78 % and the end. B10 measures fast /
bit-exact / q=h.

### B-09 · OK (recorded) · rebuild in the same run overwrote the profile in place
Second build into run1: `run1/` = `Real-924.icc, Real-924.ti3, cache, meta.json`, no `old/`.
`_archive_superseded_profile` only runs behind the "verifications exist" question
(`_confirm_rebuild_over_verifications`), so with no verification the previous `.icc` is
overwritten silently — same as the colprof path. B5 looks at the twin.

### B-10 · INCONSISTENCY (side finding, not engine) · stale text in "Profile Built"
`guided-modal-Profile_Built.png`: "Your existing chart files are preserved (renamed with a
`pre_` prefix) so nothing is lost." CLAUDE.md: the `pre_` prefixes are gone since #127
(`preconditioning.ti3/.icc` in the new run). Wrong sentence on every successful build.

---

## B3 — the four engine-only rows, one at a time

Driver `drive_B3_engine_rows.py build` then `… restart` (sandbox `B-B3`; logs `work-B/B3.log`,
`B3-restart.log`; per-build logs `work-B/B3/<row>-log.txt`, pictures `<row>-building-15s.png`,
`<row>-modal.png`, `<row>-after.png`). Manual, accurate, 924p chart, all other controls at
defaults. Each build ended in "Profile Built" → I clicked Done (6 modals recorded in the log;
watchdog never fired). Combo rows were changed by the popup helper; for the three combos inside
the tab the popup click did not register (`picked via popup=False`) and the helper fell back to
`setCurrentIndex` — an ASSISTED selection; the checkboxes were real clicks.

### B-11 · GAP · Spectral physics on an RGB chart: the log says nothing at all (ON SCREEN)
Ticked "Spectral physics model", built (56 s, first build of the session). `spectral-log.txt`
contains **no line** with "spectral" or "physic" — no "not applicable", no "RGB driver, skipped".
The tooltip says "there this option simply does nothing", and the log lets the user believe the
physics model ran. A ticked option that leaves no trace is indistinguishable from a broken one.
One line is owed: "Spectral physics model: not applicable to an RGB-driver chart — standard
model kept."

### B-12 · INCONSISTENCY · Noise handling engaged on a healthy ColorMunki chart, and said so in developer-speak (ON SCREEN)
Ticked "Measurement noise handling", built (11 s, oracle cached). Log (`noise-log.txt`):
`Repeated patches scatter 5.3× the healthy-instrument level — noise handling engaged.`
`Measurement-noise model from duplicate patches: σ = 0.265 + 0.000·exp(−Y/10).`
`Model-error floor folded into the noise budget (shadows ±0.00 ΔE, highlights ±0.00 ΔE).`
`Fitting the printer model: smoothing refine 1/4…` (printed twice)
`Smoothing chosen by cross-validation: ×0.176777 of the standard value (held-out median 0.65 × the instrument noise).`
`Confidence map (95% of patches, ΔE2000): shadows ±1.12, midtones ±0.33, highlights ±0.17, saturated colours ±0.24, neutrals ±0.69.`
Three things: (1) the tooltip promises "on a clean measurement it steps aside automatically … bit
for bit"; this is a real ColorMunki chart (4 whites, 4 blacks, critic M10) and the detector called it
5.3× worse than healthy and engaged — so either the chart is not clean (then the user should be
told what that means for the profile) or the "healthy level" is mis-set; Agent A's territory
for the number, but the user-facing consequence is that the two profiles differ (fit median
0.04/0.36 vs 0.05/0.41, and the "rows 757, 811" outlier line disappears with noise on).
(2) `σ = 0.265 + 0.000·exp(−Y/10)`, "Model-error floor folded into the noise budget (±0.00,
±0.00)" and `×0.176777` are not sentences a printmaker can act on; a zero term and six
decimals should not be printed. (3) The CV line changes its unit with the option: "held-out
median 0.65 ΔE2000" (noise off) vs "0.65 × the instrument noise" (noise on) — same number,
different meaning, no explanation. The confidence-map line is good and is the one thing the
tooltip promised that arrived.

### B-13 · BUG (cosmetic, critic N11 confirmed) · bijective prints both renderer lines (ON SCREEN)
Out-of-gamut rendering → "ChromIQ bijective (experimental)", built (10 s). `bijective-log.txt`:
`24% · Gamut mapping (maximum accuracy): bijective CAM16-UCS rendering intents (candidate).`
`26% · Gamut mapping (maximum accuracy): rendering intents matched to ArgyllCMS colprof.`
Two contradictory statements one line apart; and "(candidate)" is benchmark vocabulary
(`CHROMIQ_ENGINE_NEXT`) leaking into a shipped option's log.

### B-14 · OK · ICC version 4 and Both (ON SCREEN + bytes)
"Version 4" → `Real-924.icc` header 4.4.0, 539 636 bytes. "Both (v2 + v4)" → `Real-924.icc`
2.2.0 and `Real-924-v4.icc` 4.4.0 in `run1/`; log line `Also wrote the ICC v4 twin:
Real-924-v4.icc`. The "Profile Built" window (`both-modal.png`) names only `Real-924.icc`;
Install stays pointed at the v2 (`_icc_path`), as the tooltip says. What happens to the twin on
rebuild/delete: B5.

### B-15 · OK · Save as Defaults writes the four keys; a preset carries them (ON SCREEN)
All four set → "Save as Defaults" → `settings.ini`: `manual2_colprof_spectral=true`,
`manual2_colprof_iccver=both`, `manual2_colprof_noise=true`, `manual2_colprof_render=bijective`;
log "Profile settings saved as defaults." Preset "+" → "Save Preset" dialog (typed the name,
clicked OK — recorded) → `presets/Build Profile/engine-rows.json` → rows reset by hand → picked
"engine-rows" → all four came back (`after-preset.png`).

### B-16 · INCONSISTENCY · after a restart the saved defaults did NOT come back — the per-target store won (ON SCREEN, new process)
`drive_B3_engine_rows.py restart`: rows visible, state = spectral off / v2 / noise off /
Argyll-matched, although `settings.ini` still says both/true/bijective/true. Cause:
`run1/meta.json` → `profile_settings` carries `spectral_physics`, `icc_version`, `noise_model`,
`render_style` (the per-target write reuses `_m_collect_preset_data`, which includes them — so
the critic's addendum "not per-target" is refuted: **they ARE per-target**), and
`load_target_settings` applies the stored values before anything else. That is the
per-target rule working as specified for every Manual control, but from the user's chair "Save
as Defaults, quit, relaunch, same run" shows different values than were saved, with no hint that
the run's own memory overrode them. B4 measures the switch between runs.

### B-17 · GAP · there is no box to type an "extra colprof option" into (READ + ON SCREEN)
Both `_collect_guided_profile` and `_collect_manual_profile` hard-code `extra_args = ""`; no
widget on either page offers free flags (`11-manual-rows-scrolled.png`, every Manual group). So
the engine tooltip's "a hand-typed extra flag the engine doesn't recognise" and the critic's
S01 (`-L`) / N10 (`-g` as the whole failure text) describe a path a user cannot reach from the
app. Not a defect of the engine — a wrong sentence in the tooltip, and a scope note for the
orchestrator: `-L`, `-g`, `-p`, `.sp` are unreachable without a new control.

---

## B4 — per-target switching of the four rows (S16)

Driver `drive_B4_per_target.py` (sandbox `B-B4`; log `work-B/B4.log`; pictures
`work-B/B4/01-run1-set.png`, `03-on-run2-first.png`, `04-back-on-run1.png`, `05-on-run2.png`).
A second run could NOT be made through the bar: **Duplicate is greyed** ("This run does not have
a complete chart yet, so there is nothing to c…") because the sandbox project holds only a
measurement, and "New run" in the run dropdown creates nothing until a chart is generated. So
run2 was made with `Project.new_run()` (the same call the app uses) plus a copy of the
measurement — an ASSISTED step, everything after it on screen through the bar's run dropdown
(the popup click did not register on this combo either; the selection fell back to
`setCurrentIndex`, which fires the same `currentIndexChanged` the bar listens to).

Sequence and what the rows showed (also quality, as a control that is known to be per-target):
1. run1: set Spectral on, Both, Noise on, Bijective, quality High. `01-run1-set.png`.
2. switch to run2 (fresh `meta.json`, no `profile_settings`): rows = **Spectral on, Both, Noise on,
   Bijective**, quality **Medium**. `run2/meta.json` right after the switch: all four engine keys
   written with run1's values.
3. run1: on/Both/on/Bijective/High. 4. run2: on/Both/on/Bijective/Medium.
5. On run2 untick Noise → run1 shows Noise on → run2 shows Noise off; metas: run1 noise true,
   run2 noise false. Leaving the tab (Measure) and coming back changes nothing.

### B-18 · BUG · the four engine rows leak from run1 into a fresh run (ON SCREEN)
On the first switch to a run without stored settings every other Manual control fell back to the
saved defaults (quality High → Medium) while the four engine rows **kept run1's values** and were
then written into run2's `meta.json` as if the user had chosen them. Cause (read):
`_restore_defaults` (`tab_profile.py:5701…`) resets the Guided and Manual controls from
`manual2_colprof_*` but has no lines for `_m_spectral_cb`, `_m_iccver_combo`, `_m_noise_cb`,
`_m_render_combo` — only `_on_m_preset_selected`'s "none" branch (`:2341-2347`) and
`_m_apply_preset_data` know them. This is the exact §4 S4–S7 leak the comment above
`load_target_settings` warns about ("returning here leaves the PREVIOUS target's values on
screen, which is how a setting leaks from one run to another"), now for four new controls. Fix:
four lines in `_restore_defaults`; test: set the rows on run1, select a run with no
`profile_settings`, expect the saved defaults. Once both runs have stored settings the switching
is correct per the per-target rules (steps 3–5), and the critic's prediction "not per-target" is
refuted: the store carries `spectral_physics`, `icc_version`, `noise_model`, `render_style`.

### B-19 · GAP (product, not engine) · no way to make a second run from a measurement-only project (ON SCREEN)
Duplicate needs a complete chart; "New run" needs Create Chart. A user who imported a
measurement (i1Profiler `.txt`/`.mxf`, or a `.ti3` from elsewhere) cannot open a second run to
try another engine setting without leaving Build Profile. Recorded for the orchestrator; B-09
shows the consequence (rebuilds overwrite in place).

---

## B5 — rebuild over an existing profile with "Both", the twin, File guide, Install, Delete, failure

Driver `drive_B5_rebuild_twin.py` (sandbox `B-B5`; log `work-B/B5.log`; pictures
`work-B/B5/build1-modal.png`, `build2-after.png`, `fail-observer-modal.png`, `delete-modal.png`,
`after-delete.png`). Modals I answered: Profile Built → Done (×2), Profile Build Failed → Close,
Delete → "Delete run 1". Install was NOT clicked (it copies into the real ColorSync folder).

### B-20 · GAP · rebuild overwrites the profile AND the twin in place; nothing is archived, nothing is said (ON SCREEN)
Build #1 (Both): `run1/` = `Real-924.icc` 539 768 B 00:00:44, `Real-924-v4.icc` 539 636 B 00:00:44.
Build #2: both files' mtimes 00:00:56, same sizes, `old/` does not exist, no "moved to" line in the
log. The "never destroy" archive (`_archive_superseded_profile`) only runs behind the
verification question, so a plain rebuild in the same run silently replaces the previous profile
— the v2 exactly as the colprof path does, and the twin with it (critic S13's "not archived" is
moot because nothing is; N12's twin follows the v2's fate on rebuild). If the archive rule is
meant to cover every rebuild, the engine path needs it and must include the twin.

### B-21 · GAP · the File guide and the project's "Where are my files.txt" do not know the twin (READ from the live app)
`file_guide_body()` mentions no `-v4`; the `.icc` rows are `{name}.icc`, `preconditioning.icc`,
`merged.icc`, `calibrated.icc`. `Real-924/Where are my files.txt` (written by the app) has no `v4`.
The Delete dialog (`delete-modal.png`) lists "the printer profile Real-924.icc" and not the twin,
though the whole folder goes. Install: `_icc_path` = the v2 file; the twin cannot be installed
from the app (tooltip says so — consistent).

### B-22 · OK · Delete moves the run folder with the twin to the Trash (ON SCREEN)
With run2 present, Delete on run1 → dialog `delete-modal.png` ("The whole folder for this profile
run is moved to your Trash…") → "Delete run 1" → `~/.Trash/run1` contains `Real-924-v4.icc` and
`Real-924.icc`; run2 renumbered to run1, bar on "Run 1 (overwrite)". (The Trash item was removed
afterwards; it was sandbox data.)

### B-23 · BUG (critic N03 confirmed on screen) · observer 2015 2° is offered, the engine refuses, no colprof fallback (ON SCREEN)
Manual "CIE Observer (-o)" → "2015 2° (Stockman)" → Build: 1 s later the log shows
`4% · Computing colorimetry from the spectral data…` then
`[ERROR] Unknown observer '2015_2' (the engine knows 1931_2 and 1964_10).` and the modal
"Profile Build Failed" with exactly that sentence (`fail-observer-modal.png`). Nothing was handed
to colprof, contradicting the Beta tooltip ("quietly handed to colprof and the log tells you
why"). The run folder was untouched (same sizes/mtimes before and after) — no half file, and
the previous profile survives because the engine failed before writing. The message names the
engine's internal tokens (`1931_2`, `1964_10`) rather than the dropdown's words. Same for
"2015 10° (Stockman)" by code (`spectral.py:66`). Fix options: route `2015_*` to colprof in
`engine_support` (the tooltip's promise), or remove the two entries while the engine is on.

---

## B6 — locked controls during a build; closing the window mid-build

Driver `drive_B6_quit_mid_build.py` (`wait` mode: log `work-B/B6.log`; `exit` mode: log
`work-B/B6-exit.log`; picture `work-B/B6/01-locked-during-build.png`, `02-at-oracle-stage.png`).
Manual, accurate, -S ClayRGB1998.icm. No modal was answered by anyone in the `exit` run.

### B-24 · OK · the lock during a build (ON SCREEN)
At +4 s (`01-locked-during-build.png`): tabs 1, 2, 3, 5 greyed (`isTabEnabled` False), tab 4 on;
masthead Preferences / Tools / Open Project / Open Chart / Close Project disabled with the tooltip
"Not while a profile is being built. It will be available again as soon as the build finishes or is
stopped."; bar run-combo, Delete, Duplicate disabled; Build ("BUILDING PROFILE…"), Install, Save
as Defaults, the file group and the whole options stack disabled. Tried them for real: a click on
tab "3. Measure" DID switch the tab bar's current index (Qt still switches a disabled tab? —
`tabText(currentIndex)` came back "3. Measure"; a user watching sees the Build tab leave while
the build runs — worth a look, but it may be the direct `setCurrentIndex` I used rather than a
mouse click; I did not repeat it with the mouse), Tools opened nothing, Build did nothing.
GUIDED/MANUAL buttons stay enabled (mode switch during a build is possible; harmless since the
params were captured at start). The tooltip says "…or is stopped" — there is no Stop.

### B-25 · BUG (critic N16/N20 confirmed) · closing the window mid-build orphans colprof and its temp dir (ON SCREEN + shell)
`exit` run: at +12 s the log showed "Saturation table: matching colprof's rendering…"; the
oracle child was `colprof -qm -S ClayRGB1998.icm …/T/tmpfzroneti/oracle` (pid 59892).
`win.close()` returned True in 0.52 s, the window vanished, no question was asked; the engine
thread was still running. The driver then did what `main._hard_exit` does (`os._exit(0)`). From
the shell 1, 2 and 3 s later: pid 59892 still alive — an orphaned colprof burning a core for
~40 s more; the `TemporaryDirectory` cleanup never ran (see the follow-up line below for whether
`tmpfzroneti/` survived). No `.icc` was written (the engine writes it in one `write_bytes` at the
end, so a quit leaves no half file — good). In `wait` mode (event loop kept alive, i.e. what
would happen if something else kept the app open) the build finished 47 s after the close and
put a "Profile Built" window on screen for a main window that no longer exists.
The app never asks "a profile is being built — quit anyway?", unlike a running measurement
(`_ask_before_quitting_on_a_measurement`). Suggested: the same guard for `_engine_builder.is_running`,
a `timeout=` and a kill on the oracle `subprocess.run`, and a Stop button (the lock tooltip
already promises one: "…or is stopped").

Follow-up (shell, `until ! pgrep -f tmpfzroneti`): the orphaned colprof ran to completion at
00:12:42, ~53 s after the "quit", and left `$TMPDIR/tmpfzroneti/` behind with `oracle.ti3`
(359 799 B) and `oracle.icc` (539 560 B) — 900 KB per interrupted build, never cleaned (the
`TemporaryDirectory` context never exits). `run1/` afterwards: `Real-924.ti3, meta.json, cache`
— no profile, no half file. (I deleted that temp dir afterwards.)
---

## B7 — Tools → "Build profile with scanner or camera", printer mode, engine + accurate ON

Driver `drive_B7_scanner_tool.py` (tool half) and `… --engine-only` (engine half; the first run
ended in a "This measurement is not in the run you have selected" question because the tab kept
the previous project's `.ti3` — a harness artefact of `open_project`, recorded, and the second
run loaded the run's own measurement). Sandbox `B-B7` holds a COPY of `~/ChromIQ/Knut-Scanner`
(whole project). Logs `work-B/B7.log`, `B7-engine.log`; pictures `work-B/B7/01-tool-printer-mode.png`,
`02-tool-advanced-open.png`, `04-tool-after-build.png`, `engine-modal.png`; profiles
`tool-colprof.icc`, `engine-accurate.icc`; `a2b1-compare.json`.

Assisted steps, stated: the chart (`_set_chart(Knut-Scanner.ti2)`) and the scanner profile
(`Knut-Scanner-scanner.icc`) were set directly (both pickers are native file dialogs); the build
was started with the tool's own `_build_printer_profile(pbase, base)` on the already accumulated
`Knut-Scanner-printer.ti3` (the three page scans were not re-read through scanin; everything from
the colprof step on — sanitiser, archive, colprof through `ArgyllRunner`, self-check, install
offer — is the tool's real code path). The mode switch ("A chart I made in ChromIQ", "Profile my
printer from this scan") was clicked. No modal appeared in the tool half; the engine half's
"Profile Built" → Done (recorded).

### B-26 · INCONSISTENCY (A-Q3 answered: NO) · with the engine + Maximum accuracy on, the scanner tool still builds with colprof and shows no engine option (ON SCREEN)
`01-tool-printer-mode.png`: window title "Build printer profile"; the left column offers
Scanner profile, Chart you printed, Chart geometry, Page, Scan; the Advanced disclosure holds
colprof's type/quality/description and the `-S` default. Command preview, verbatim:
`colprof -v -D <chart name> scanner -al -qm -A ChromIQ -M <chart name> scanner -S /Applications/Argyll/ref/ClayRGB1998.icm <measurements>`
— with Preferences → Beta → engine ON and Accuracy = Maximum accuracy. Engine-ish controls in the
window: none (search over every button/combo for spectral/noise/bijective/ICC version/engine/
accuracy → `[]`). The build ran colprof (`tool-log.txt`: colprof's verbose "nnrev…", "Profile check
complete, peak err = 10.200573, avg err = 3.945191", "[OK] Printer profile saved: …/Knut-Scanner-
printer.icc"), 128 s. The same user, one tab over, gets the engine: Build Profile → Manual on the
same `.ti3` → "Building with the ChromIQ profile engine (beta)…", 96 s (74 s of it inside the
oracle colprof for the saturation table), a different profile file. The tool's own closing line
even sends the user there: "The measurement (.ti3) sits next to it — load that in the Build
Profile tab if you want to fine-tune the printer profile (intents, quality, …)". So the two
windows disagree about which builder makes "the printer profile", and only one of them honours
the Beta switch.

### B-27 · evidence for the routing decision (OFFSCREEN numbers on the on-screen profiles)
A2B1 through `xicclu -ff -ir -pl -s100` on 20 device values: median 0.40, max 0.89 ΔE76 between
the tool's colprof profile and the engine's accurate profile — but BOTH map every device value to
L*≈99.7, a*≈−5, b*≈1 (`a2b1-compare.json`): the 315p file is not a measurement (critic M10), so
this says only that the two builders agree on junk. What matters for routing: (a) on ≤4 inks the
accurate engine still runs colprof for its saturation table, so the tool would pay colprof's
time plus the engine's; (b) the tool's `_sanitize_scanner_ti3` (nan/inf) must stay in front of
the engine (critic A-Q3 addendum; B8 shows the engine's NaN behaviour); (c) the tool's self-check
thresholds (peak 30 / avg 12) let this flat profile through without a word, and the engine's
"Model fit median 4.51 ΔE, 95% 16.21 ΔE" + "Smoothing … ×4 of the standard value" (the top of the
ladder, critic S06) are the only hints — neither window says "every patch reads the same".

### B-28 · INCONSISTENCY (side) · the tool's description default (ON SCREEN)
Preview: `-D <chart name> scanner … -M <chart name> scanner` in PRINTER mode — the placeholder
still says "scanner" for a printer profile (the real build used "Knut-Scanner (scanner-measured)"
per `_build_printer_profile`), and the model tag `-M` repeats the description.

---

## B8 — bad inputs as the user sees them (critic N13, N17)

Driver `drive_B8_bad_inputs.py` (sandbox `B-B8`, three projects; log `work-B/B8.log`; pictures
`work-B/B8/<name>-modal.png`, `<name>-after.png`). Manual, accurate, defaults. NOTE for the
harness: switching projects with `open_project` left the previous project's `.ti3` in the tab
(the bar moved, the file did not), which the app correctly caught with its own "This measurement
is not in the run you have selected — Build anyway / Cancel" question in the first attempt; the
driver now loads the run's own measurement (harness `set_ti3_path`) before building. Modals I
answered: Profile Built → Done (×2), Profile Build Failed → Close.

### B-29 · BUG · a stuck-instrument chart (18 patches, every reading identical) builds a "successful" profile (ON SCREEN)
CR30-18p: log "Detected instrument: CR30 (no spectral data)"; Build → 3 s → "Profile Built",
`CR30-18p.icc` 181 472 B written. The log: no cross-validation (below 120 patches, silent), no
outlier line, then `78% · Using the engine's own rendering (colprof oracle failed:
/Applications/Argyll/bin/colprof: Error - 65539, set_icxLuLut: can't handle test points without a
white patch` — colprof REFUSED this chart and the engine went on without it — and the fit line
`Model fit (perceptual ΔE2000): median 0.02, 95% 0.05` — the best fit of the whole day, because
every patch reads XYZ ≈ 48.4/37.4/5.8 (critic M10). The user sees `B-29-cr30-18p-profile-built.png`:
"Your ICC profile has been built successfully." A perfect fit line on a flat chart is the bug: the
fit line cannot distinguish "the model is good" from "the chart has no colour in it". Argyll's
refusal was the right answer and was demoted to a 78 % progress note. Suggested: refuse (or
warn in the Profile Built window) when the chart has no white patch / a chroma range below a
threshold, and never bury a colprof refusal in a progress line.

### B-30 · GAP · the junk 315p scanner chart builds a flat profile with a hint only a specialist reads (ON SCREEN)
Scanner-315p: 95 s (74 s inside the oracle colprof), "Profile Built", `Scanner-315p.icc`
198 676 B. The only warnings: `Smoothing chosen by cross-validation: ×4 of the standard value
(held-out median 9.48 ΔE2000)` (×4 = the top of the ladder, critic S06, not flagged as a
boundary), `1 patch(es) disagree strongly … rows 266`, `Model fit … median 3.58, 95% 13.23` /
`median 4.51 ΔE, 95% 16.21 ΔE`. A 95 % fit error of 16 ΔE on the chart's own patches is a
measurement that describes nothing, and the finished window still says "built successfully".
Same conclusion as B7: the fit line needs a verdict ("this is far outside what a good
measurement gives — check the scan / the instrument"), not just numbers.

### B-31 · BUG (critic M7 confirmed on screen) · a NaN row ends in "cannot convert float NaN to integer" (ON SCREEN)
NaN-924p (row 100's XYZ = nan): the build ran 34 s — CV ladder, robust fit, inversion, and the
oracle colprof, which refused (`CGATS file read error … Field 'XYZ_X'`) and was again reduced to a
"Using the engine's own rendering" note — and then died in the writer: log `[ERROR] cannot convert
float NaN to integer`, modal "Profile Build Failed" with exactly that sentence
(`B-31-nan-failure-dialog.png`). No profile written. The user learns nothing about WHICH row is
broken; the scanner tool sanitises nan/inf before colprof (`_sanitize_scanner_ti3`) and Build
Profile does not. Suggested: validate on read (`read_ti3`) and name the SAMPLE_ID/LOC.

---

## B9 — wording and i18n on screen (S20, S24)

Driver `drive_B9_german_log.py` (sandbox `B-B9`; harness booted with `language="de"` — a
recorded harness change: `Harness(language=…)` calls `set_language` + `install_qt_translator`
exactly as `main.py` does). Manual, accurate, ALL FOUR rows on, -S ClayRGB1998.icm. Log
`work-B/B9.log`, classified lines `work-B/B9/de-lines.json`, pictures `B-32-german-log.png`,
`B-32-german-profile-built.png`. Modal: "Profil erstellt" → "Fertig" (recorded).

### B-32 · GAP (S20 confirmed) · in German, the engine's build log is English except three lines (ON SCREEN)
The tab is German ("4. Profil erstellen", "Profil erstellen", rows "Spektrales Physikmodell" /
"Umgang mit Messrauschen"), the finished window is German ("Profil erstellt", "Fertig"). Of the
30 distinct log lines of the build, exactly THREE are German:
`Erstelle mit der ChromIQ-Profil-Engine (Beta)…`, `Modellanpassung an den gemessenen Messfeldern:
Median 0.08 ΔE, 95 % 0.67 ΔE.`, `Perzeptive und Sättigungs-Tabellen aus der Gamut-Quelle
erstellt.` Every line from `builder.py` / `accuracy.py` / `gp.py` / `gamut_map.py` is an English
f-string: "Reading the measurement…", "Fitting the printer model (924 patches, grid 17)…",
"Repeated patches scatter 5.3× the healthy-instrument level — noise handling engaged.",
"Measurement-noise model from duplicate patches: σ = …", "Model-error floor folded into the
noise budget …", "Smoothing chosen by cross-validation: …", "N patch(es) disagree strongly …
rows … Consider remeasuring them.", "Inverting the model …", "Writing the profile…", "Building the
perceptual and saturation tables…", "Gamut mapping (maximum accuracy): …", "Saturation table: …",
"Also wrote the ICC v4 twin: …", "Model fit (perceptual ΔE2000): …", "Confidence map (95% of
patches, ΔE2000): …", and the tab's own `[OK] Profile saved: …` (an f-string in
`_on_engine_done`). The percentage/ETA prefix ("~30s left", "almost done") is English too. Full
list with classification in `de-lines.json`. (The critic's note stands: translating these needs
`_STAGE_PCT` to match translated prefixes.)

### B-33 · GAP (S07 confirmed on screen) · "rows 757, 811" cannot be found on the sheet
The line a beginner is asked to act on: `2 patch(es) disagree strongly with the model and were
down-weighted — rows 757, 811. Consider remeasuring them.` The chart file says: row 757 =
`SAMPLE_ID 757, SAMPLE_LOC "F20"`, RGB 12.5/6.3/6.3; row 811 = `SAMPLE_ID 811, SAMPLE_LOC "W1"`,
RGB 6.3/6.3/12.5 (`awk` over the DATA block). The printed sheet carries F20 and W1, not "757";
on an imported/merged `.ti3` the row number is not even the SAMPLE_ID. And "remeasuring them"
is not an action the app offers for two patches — the Measure tab re-reads a strip or the chart.
Wanted: "patches F20 and W1 (near-black, RGB 12/6/6 and 6/6/12) …", and a sentence that says
what the user can actually do (re-read strip F / W, or accept — they are the two darkest patches
and read within the dark-noise the noise option models).

---

## B10 — timing as felt (S04): fresh app launch per run, Manual, -S ClayRGB1998.icm, 924p

Driver `drive_B10_timing.py <mode> <q>` ×6 (sandboxes `B-B10-<mode>-<q>`; logs
`work-B/B10-<mode>-<q>.log`; every log line with its arrival time in
`work-B/B10/<mode>-<q>-stamped.json`). Each run: one process, one project, one build, "Profile
Built" → Done (recorded). Wall time = Build click → modal.

| mode (Preferences → Accuracy) | q=m | q=h | what the log shows |
|---|---|---|---|
| Fast | **108.9 s** | **206.2 s** | port does the perceptual mapping (40–74 %) AND then the oracle colprof runs for the saturation table (78 % for 44.5 s / 123 s) |
| Bit-exact (= colprof directly on ≤4 inks) | **44.9 s** | **120.2 s** | 3 log lines in total: the `[INFO] Bit-exact … building with ArgyllCMS colprof directly` line, then nothing for 45 s / 120 s, then `[OK] Profile saved` — no percentage, no ETA, no colprof output |
| Maximum accuracy | **56.7 s** | **152.6 s** | 78 % for 44.2 s / 125.3 s (the oracle colprof), 92 % for 4–6 s |

### B-34 · INCONSISTENCY (S04 confirmed with fresh launches) · the tooltip has the order of the three modes backwards (ON SCREEN timing)
"Fast … finishes in a few seconds" = the SLOWEST (109 s / 206 s). "Maximum accuracy … several
minutes longer" = faster than Fast at both qualities (57 s / 153 s) and only 12 s / 32 s slower
than Bit-exact. "Bit-exact … up to a minute or two" is the only sentence that is roughly true.
Also the Quality combo's own "(~2 min)" for Medium (colprof-era text, visible in every picture)
is right for Fast, double the truth for Maximum accuracy. Corrected sentences for the
orchestrator, measured on this 16-core machine: Fast ≈ 2 min (3.5 min at High); Bit-exact ≈ 45 s
(2 min at High); Maximum accuracy ≈ 1 min (2.5 min at High) — because on an RGB/CMYK chart the
accurate path lets colprof do the rendering once and skips the Python port.

### B-35 · INCONSISTENCY · the percentage never goes backwards, but it stops meaning anything at 78 % (ON SCREEN timing)
Dwell per percentage: accurate-m sits at **78 % for 44.2 of 56.7 s** (78 % of the build), accurate-h
at 78 % for 125.3 of 152.6 s, fast-h at 78 % for 123 of 206 s. The ETA: fast-m says "~20s left" from
t=4.5 s (real 104 s) through t=105 s (real 4 s) — the same text for 100 seconds; accurate-h says
"~40s left" at t=22 s with 131 s to go; "almost done" appeared exactly once in six runs (accurate-m,
0.8 s before the end). The bar's label never changes ("BUILDING / CHROMIQ ENGINE"). Cause (read):
`_STAGE_PCT` gives the oracle colprof stage 78→92 with no sub-steps, and the ETA is
elapsed·(100−p)/p smoothed, so it inherits the frozen p. Suggested: either drop the number during
the colprof stage ("running Argyll colprof — about a minute at Medium"), or time the oracle from
the previous run (the cache key already exists) and interpolate. And Bit-exact should not be a
45–120 s black hole: show colprof's own progress lines (the colprof path already streams them
in the colprof-only build).

