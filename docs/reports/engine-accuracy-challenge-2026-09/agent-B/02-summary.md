# Agent B — summary (on-screen user-journey breaker, engine "Maximum accuracy")

Full record: `reports/agent-B/01-findings.md` (staged per journey, click by click).
Every journey ran the REAL app on screen through `scripts/engine_challenge/harness.py` +
`drive_B_common.py` on a sandbox (`CHROMIQ_SETTINGS_FILE`, `CHROMIQ_PRESETS_DIR`,
`custom_output_path` under `~/Desktop/ChromIQ-engine-challenge/sandboxes/B-*`); nothing under
`~/ChromIQ` was opened (B7 used a whole-project COPY of Knut-Scanner). Pictures cited are
`QWidget.grab()` of the real painted window/dialog; `screencapture` shows another Space on this
machine and is not cited. Real settings afterwards: `defaults read com.chromiq.ChromIQ
custom_output_path` → `""` (empty = the default `~/ChromIQ`; not a sandbox path).

**Modals answered:** the harness watchdog was never armed (`modals_answered=[]` in every log).
Every dialog was answered by the journey itself and is recorded in the driver log:
Profile Built → Done (B2 ×2, B3 ×6, B5 ×2, B7 ×1, B8 ×2, B9 ×1 "Fertig", B10 ×6); consent box →
"Enable the engine" (B1); Accuracy help / Spectral help → Close (B1); Preferences → OK (B1),
Cancel (B1b); Save Preset → OK (B3); Profile Build Failed → Close (B5 observer, B8 NaN); Delete
run 1 → "Delete run 1" (B5). Assisted (not clicked) steps are named in each journey: popup-list
clicks on three Manual combos fell back to `setCurrentIndex`; run2 created with
`Project.new_run()` (B4/B5, Duplicate greyed without a chart); B7's chart/scanner-profile pickers
(native file dialogs) and the tool build started from the accumulated `.ti3` (scanin skipped).

## Findings

| # | grade | finding | screenshot (`screenshots/`) | driver |
|---|---|---|---|---|
| B-01 | OK | consent dialog complete, buttons fit; 1 broken sentence, no title on macOS | B-01-consent-dialog.png, B-01-accuracy-popup.png | drive_B1_switch_on.py |
| B-02 | IMPROVEMENT | rows appear on Preferences OK without a tab change — but below the fold, unannounced | B-02-manual-after-ok-rows-below-fold.png | B1 |
| B-03 | INCONSISTENCY | Accuracy tooltip's time claims are inverted (see B-34) | B-03-accuracy-tooltip.png | B1 |
| B-04 | INCONSISTENCY | tooltip promises tested later: colprof hand-off (B-23), "own port" (B-06), spectral no-op (B-11), "log tells you" (B-12) | — | B1 |
| B-05 | IMPROVEMENT | the four rows sit unlabelled inside "Color Science", no flag hints, no heading | B-05-engine-rows-inside-color-science.png | drive_B1b_rows_after_restart.py |
| B-06 | GAP | Guided never names "Maximum accuracy" where a user looks; four options silently at defaults | B-06-guided-building.png, B-06-profile-built-window.png | drive_B2_guided_vs_manual.py |
| B-07 | OK | Guided and Manual profiles byte-identical apart from the date (17 tags) | — | B2 |
| B-08 | INCONSISTENCY | 26 %→78 % in one second, 78 % for 45 s with "~20s left" | B-06-guided-building.png | B2 |
| B-09 | OK (recorded) | rebuild in the same run overwrites in place, no `old/` | — | B2 |
| B-10 | INCONSISTENCY (side) | "Profile Built" still says charts are renamed with a `pre_` prefix | B-06-profile-built-window.png | B2 |
| B-11 | GAP | Spectral physics on an RGB chart: no log line at all | — | drive_B3_engine_rows.py |
| B-12 | INCONSISTENCY | Noise handling engaged on the real ColorMunki chart (5.3×) with σ=…+0.000·exp, ±0.00, ×0.176777, unit-switching CV line | B-12-noise-handling-log.png | B3 |
| B-13 | BUG (cosmetic, N11) | bijective prints both "bijective … (candidate)" and "matched to ArgyllCMS" | B-13-bijective-log.png | B3 |
| B-14 | OK | v4 header 4.4.0; Both writes the `-v4.icc` twin + log line | B-14-both-v2-v4.png | B3 |
| B-15 | OK | Save as Defaults writes the 4 keys; preset round-trips them | B-15-preset-restored-rows.png | B3 |
| B-16 | INCONSISTENCY | after restart the run's per-target store overrides the saved defaults (rows ARE per-target — critic refuted) | — | B3 restart |
| B-17 | GAP | no "extra colprof options" box exists → `-L`/`-g`/`-p` unreachable; tooltip sentence wrong | — | B3 |
| B-18 | BUG | the four rows LEAK from run1 into a fresh run (`_restore_defaults` lacks them) and get written into its meta | B-18-run2-inherits-run1-rows.png | drive_B4_per_target.py |
| B-19 | GAP (product) | no way to make a 2nd run from a measurement-only project (Duplicate greyed, New run needs a chart) | — | B4 |
| B-20 | GAP | rebuild with Both overwrites v2 AND twin in place; archive only behind the verification question | — | drive_B5_rebuild_twin.py |
| B-21 | GAP | File guide / "Where are my files.txt" / Delete list do not know the twin | B-22-delete-run-dialog.png | B5 |
| B-22 | OK | Delete moves the run folder incl. twin to the Trash | B-22-delete-run-dialog.png | B5 |
| B-23 | BUG (N03) | observer 2015 2° → "Profile Build Failed: Unknown observer '2015_2' (the engine knows 1931_2 and 1964_10)", no colprof hand-off | B-23-observer-2015-failure.png | B5 |
| B-24 | OK | lock during a build (tabs, masthead, bar, buttons) — tooltip promises a Stop that does not exist | B-24-locked-during-build.png | drive_B6_quit_mid_build.py |
| B-25 | BUG (N16/N20) | close mid-build: no question, orphaned colprof runs 53 s more, `$TMPDIR/tmp*/oracle.*` (900 KB) left behind | — | B6 `exit` |
| B-26 | INCONSISTENCY (A-Q3 = NO) | scanner tool builds with colprof (`colprof -v -D … -al -qm … -S ClayRGB`), no engine row, while Build Profile uses the engine on the same .ti3 | B-26-scanner-tool-printer-mode.png, B-26-scanner-tool-after-colprof-build.png | drive_B7_scanner_tool.py |
| B-27 | evidence | tool 128 s vs engine 96 s (74 s in oracle colprof); both flat on the junk chart; sanitiser + self-check notes for routing | — | B7 |
| B-28 | INCONSISTENCY (side) | tool preview says `-D <chart name> scanner -M <chart name> scanner` in printer mode | — | B7 |
| B-29 | BUG | 18p stuck-instrument chart → "built successfully", fit median 0.02; colprof's refusal buried in a 78 % line | B-29-cr30-18p-profile-built.png | drive_B8_bad_inputs.py |
| B-30 | GAP | 315p junk chart → success with fit 95 % 16 ΔE and CV at ladder top ×4, no verdict | B-30-scanner-315p-after.png | B8 |
| B-31 | BUG (M7) | NaN row → 34 s of work then "cannot convert float NaN to integer" | B-31-nan-failure-dialog.png | B8 |
| B-32 | GAP (S20) | German UI: 27 of 30 engine log lines English, incl. `[OK] Profile saved` | B-32-german-log.png, B-32-german-profile-built.png | drive_B9_german_log.py |
| B-33 | GAP (S07) | "rows 757, 811" = sheet patches F20 and W1; "remeasure them" is not an action the app offers | — | B9 |
| B-34 | INCONSISTENCY (S04) | fresh launches: Fast 109/206 s, Bit-exact 45/120 s, Accurate 57/153 s (q=m/q=h) — tooltip order backwards; Quality combo "(~2 min)" | — | drive_B10_timing.py |
| B-35 | INCONSISTENCY | never backwards, but 78 % for 44–125 s; "~20s left" for 100 s; Bit-exact = 3 log lines and no progress for 45–120 s | — | B10 |

## Fix order I would suggest
1. B-18 (four rows leak between runs — 4 lines in `_restore_defaults`, per-target rule).
2. B-29/B-30/B-31 (a flat or NaN chart must not end in "built successfully" / a Python error).
3. B-23 (observer 2015 → colprof hand-off or remove the entries), B-25 (quit guard + oracle
   timeout/kill + temp cleanup), B-13/B-11/B-12 wording (log lines a printmaker can act on).
4. B-06/B-34/B-35/B-03 (say which mode is building, honest times, honest bar).
5. B-26 (product call: route the scanner tool's printer profile through the engine when the
   Beta switch is on, keeping `_sanitize_scanner_ti3` in front and telling the user in the tool).
6. B-20/B-21 (the twin in archive/File guide), B-32/B-33 (i18n + patch naming), B-02/B-05.

Harness change recorded: `Harness(language=…)` (B9). Drivers: `scripts/engine_challenge/
drive_B_common.py`, `drive_B1_switch_on.py`, `drive_B1b_rows_after_restart.py`,
`drive_B2_guided_vs_manual.py`, `drive_B3_engine_rows.py`, `drive_B4_per_target.py`,
`drive_B5_rebuild_twin.py`, `drive_B6_quit_mid_build.py`, `drive_B7_scanner_tool.py`,
`drive_B8_bad_inputs.py`, `drive_B9_german_log.py`, `drive_B10_timing.py`. Logs + raw pictures:
`work-B/`. Sandboxes kept: `sandboxes/B-*` (15). Trash: the one run folder the app moved there
(B5) was removed by me; the orphaned oracle temp dir (B6) too.
