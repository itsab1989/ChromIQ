# AGENT1 final assessment: ChromIQ 4.2.0 Create Chart tab, layout engine first

Repo /Users/Basti/develop/ChromIQ at master 80975e65 (v4.2.0), read-only throughout. Everything below was seen in the real app on the real screen, built the way main() builds it (fonts, WinButtonLayoutStyle("Fusion"), CompositeAppFilter, apply_appearance), with the owner's own look (neutral, English, log hidden) from a sandboxed settings file, a sandboxed presets copy and the projects folder /Users/Basti/ChromIQ-assessment. Every claim carries a grade: OBSERVED (on screen), PARTIAL, INFERRED (code or files), UNKNOWN. No em dash is used in anything I wrote. Paths are relative to /Users/Basti/Desktop/Create Chart Assessment/. One finding per file in Findings/ (29 files); staged checkpoints 01 to 08 in Reports/; the control-by-control table is Reports/AGENT1-functional-inventory.md.

## 1. What was tested

Time: 07:46 to 09:45 (two hours of on-screen driving, about 70 % of the effort on the layout engine). Fifteen driver files in Test Runs/drivers (cc_lib.py shared, d00 to d09 plus b-variants), 42 logs and JSON records in Test Runs/logs, 261 screenshots in 22 folders under Screenshots/. All runs unattended; every modal was answered by a watcher that asserts the dialog by title or text and clicks a named button (20 expected dialogs answered, 8 logged as unexpected and closed through their own Cancel/OK; none clicked by a human). 150 chart builds were made by the app in this session (55 in the instrument matrix, 14 layout modes, 8 margin cases, 20 furniture and export cases, 5 Guided, 12 preset and editor cases, 10 extremes, the rest in the smaller checks), 18 of them live-preview re-layouts, plus 4 printtarg runs by hand for parity. Zero CRITICAL log records; the only Python tracebacks were the engine's expected "paper too short" refusals (8) and one real caught AttributeError (F-029).

Modules and workflows covered (A = engine, B = the rest): A1 engine vs printtarg with file inventories; A2 every engine instrument and mode on five papers; A3 every layout mode; A4 margins, instrument margins, Instrument Limits through the real Preferences dialog, strip length; A5 every furniture option; A6 both info frames on engine, printtarg, external and empty charts; A7 auto-update; A8 named presets (save, reload, overwrite, delete, restart), built-ins, Chart Layout defaults; A9 the patch-set editor round trip; A10 extremes; A11 preflight; A12 PDF and sidecars; A13 scanner path (code only). B1 Guided incl. printtarg parity and the transfer to Manual; B2 Manual rows and the configuration line; B3 gamut with and without a profile; B4 Calibration; B5 header load; B6 preview; B7 run bar, deleted folder; B8 help texts against the Argyll docs; B9 window sizes; B10 German; B11 appearance; B12 names and a legacy project.

Not reached (UNKNOWN): individual expert targen/printtarg rows, "Save as Defaults", the Refinement profile row, the preset "reveal" button, a run folder with files removed by hand, keyboard focus order. Mockups: none produced (the owner allowed them; I spent the time on evidence).

Tooling errors of my own, recorded so nobody repeats them: my first "auto-update did not fire" conclusion (checkpoints 05 and 06) was wrong, the Python log proves it fired every time; D05, D07 and D08 each had to be resumed after my watcher mishandled a dialog (Apply-or-save box, id() reuse, a five-way box); one screen capture that showed only the desktop was deleted at once.

## 2. What works correctly (the regression baseline, all OBSERVED)

Layout engine
- Every engine instrument and mode builds on A4, A4 landscape, A3, A3 landscape and a 200 x 200 custom sheet without error (55 of 55), 8-bit LZW at 300 dpi, page sizes exact.
- With Auto patch count the "Chart layout information" estimate equals the built chart in 55 of 55 instrument builds and 11 of 11 layout-mode builds (rows, strips, pages, patch size within 0.06 mm).
- Every layout mode renders what it says: area-first by width, by grid (columns, rows, both pinned), height ratio, patch-first auto / fixed size / scale, all nine alignments.
- Own margins 0 to 60 mm are honoured; "Use instrument margins" copies the table and restores it on re-tick; the ruler note names strip length and ruler; Max strip is honoured in patch-first.
- Furniture: clip content modes, clip side and width, flip, strip and row indicators (with a full explanation when the left margin widens), label style, underline, sheet text, stamp, edge spacers, spacer modes, helper markers on four edges (greyed for hexagons with a reason), page offsets. Each option that changes capacity changes the estimate and the build together.
- Fixed seed reproduces the .ti2 exactly; 16-bit and zlib work; PDF export writes an A4 vector PDF beside the TIFF; i1Profiler sidecars (-colours.txt, -i1profiler.txt/.pxf) are written on every build.
- Auto-update preview: debounced (one build for two nudges 150 ms apart), fires about 1.5 s after a layout edit including paper, ignores note edits, rewrites the run's chart files.
- Named presets: save with attached .ti1, reload restores every key, overwrite asks, delete removes, values identical after a real restart. Chart Layout defaults in Preferences seed a fresh panel. The patch-set editor opens from the hint and from Tools with the run's set, and Apply / Overwrite rebuilds the same chart.
- Extremes: 1 patch, 10,000 patches (36 pages), 20 pages, 72 and 1200 dpi all build; impossible sheets fail without a crash and never lose the previous chart's files.
- Guided: the headline count equals the built count (5 of 5); the engine's Guided geometry equals printtarg's for i1 A4 (1 and 2 pages) and p3 A4 landscape when printtarg is run with the creator's own arguments; ColorMunki gains one strip per page by the accepted page-label reclaim. The transfer to Manual reproduces the Guided chart exactly.

The rest
- Session restore opens a project on its current run; run switching restores each run's engine state and margins; leaving a run writes its settings (W6); the chart sidecar wins on return (section 10 ruling).
- Gamut module: coverage line, margin and intent choices, the S4 question, the reference .ti3, the chart in verifications/. Calibration target: fixed bar, cal/ location, prefilled targen, the replace question. Load patch set: five-way destination question. Reflected external chart: locked panel, info cards.
- Name validation prompts for too long, illegal characters, reserved names, leading dots; umlauts accepted; a new name over an open project goes through the four-way Rename dialog. A schema-1 project migrates in place without a dialog. A project folder deleted while open does not crash the app.
- Known-and-ruled items, current state in one line each: chart overwrite of a chart-only run raises no window (55 silent overwrites in D02; also when another project's name is typed, D07b): as deferred. Helper markers: centred dashes on four edges, greyed for hexagons: as settled. i1Pro 19 mm bottom on A4 portrait: in force (min column 19.0). Guided always uses the engine: every Guided info line says "ChromIQ layout engine", parity holds. Build-in-flight clobber: the stored-mode variant did not reproduce (run switches restored the right mode in D07b); a related clobber did (F-003).

## 3. Problems

### Confirmed (OBSERVED)
High: F-001 estimate and hint disagree with a fixed-count area-first build (three capacities for one layout); F-003 printtarg panel and per-target store diverge from the built chart after Generate (two reproductions, the executed command differs from the preview); F-007 an Instrument Limits change reaches the inspector but not the panel, the estimate or the build; F-018 Guided i1Pro 3 Plus A4 landscape, nothing changed, is red against the shipped minimums; F-024 one visit to the gamut module without a profile disables Generate everywhere and shows Stop.
Medium: F-002 both frames describe a chart that is not on screen (empty preview, target change); F-005 "Clip border: Off, more patches" gains nothing with instrument margins on; F-006 the margin verdict disappears whenever a note is present; F-008 Max strip and Don't cap ignored in area-first; F-012 one unknown token leaves every token unexpanded; F-015 the Manual info line shows a printtarg command for engine-built and prebuilt presets, including "printtarg -iCR30"; F-017 a shipped i1Pro built-in is flagged red by the shipped minimums; F-019 impossible layouts are not refused before Generate and fail only in the hidden log; F-020 a 1 mm patch grid builds without a word after minutes of frozen window; F-021 the estimate reads the hidden printtarg Pages spin (20 pages assumed, 1 built); F-025 after a failed build the restored chart is not shown; F-029 the replace-calibration question can never list the runs built on the calibration (caught AttributeError).
Low: F-004 the engine toggle flips the Stamp box; F-009 "Use instrument margins" ticked and locked where no table exists; F-010 the configured ruler ignored with own margins; F-011 a question with only OK; F-016 built-ins move the engine toggle silently; F-022 help texts wrong against Argyll (-P, -n, -L, -f Auto, Guided flag names); F-023 Stop shown beside a disabled Generate; F-026 measured-frame labels clipped at 1280 x 800; F-028 German header and labels clipped.

### Likely (PARTIAL or INFERRED)
F-013 image clip mode keeps the caption (PARTIAL: greying of the Text box not captured); F-014 the engine preflight module is never run (INFERRED, no caller); F-027 a loaded patch set stays armed after another project is opened (PARTIAL: the lock is on screen on the other project, Generate there was not pressed).

### Areas needing further investigation
- The exact writer that flips -L at the Generate click (F-003): two reproductions, mechanism not found in the time available.
- Whether F-027's armed set really builds on the other project (one Generate press with the files inspected would settle it).
- Expert targen/printtarg rows, Save as Defaults, keyboard order, a run with hand-deleted files (UNKNOWN).
- The scanner path end to end (scanin target from an engine hex chart) lives outside Create Chart and was not run.

### Product decisions (see section 7) and feature suggestions
- Wire the engine's preflight (patch-size floor, contrast, fit) into the frames; it exists and is tested (F-014, F-020).
- Show the reason the estimate cannot lay out (dashes today) and grey Generate for that case (F-019).
- One Pages control when the engine is on (F-021); one source of "in flight" (F-023, F-024).
- The estimate and the hint should use the same sizing as the build (area_target_count) and the designed count, not the padded on-screen total (F-001).

## 4. Inconsistencies between Guided, Manual and Gamut (OBSERVED)
- Clip border off: Guided gains 66 patches (484 to 550), Manual with instrument margins on gains none; the two modules use different left margins (m10 versus the 26 mm table minimum) for the same idea (F-005).
- Thresholds: Guided clamps its margins to the table for i1 and CM but not for p3 A4 landscape (F-018); Manual never clamps after a Preferences edit until the boxes are re-synced (F-007).
- Labels: Guided calls its boxes "Suppress left clip border (-L)" and "Don't limit strip length (-P)" although it never runs printtarg; Manual's engine panel calls the same things "Clip border" and "Don't cap strip length".
- Estimate: Guided's headline is exact; Manual's estimate is exact with Auto count and wrong with a fixed count; the gamut module's estimate (on Manual's panel) is exact for its own set.
- Generate: the gamut module's "no profile" rule leaks into Guided and Manual (F-024); Guided's own text there promises the opposite.
- Recipe provenance: Guided writes 6/6/6/6 into the sidecar with no user-chosen stamp (known gap #171, decided); Manual writes the real margins.
- Info line: right for plain Manual builds, wrong for built-ins (F-015); Guided's fixed-settings line is right.

## 5. Fragile areas and regression risks
- Two records of the same thing in several places: two Pages spins (F-021), two clip-border margins (Guided m10 vs table 26), two token expanders (sheet and clip share one all-or-nothing formatter), sidecar `create_chart_settings` versus `printtarg_fields` (F-003), the estimate's geometry versus the build's (F-001). Each pair drifts under a path that touches only one side.
- The enabled state of Generate is set from thirteen places and "a build is in flight" is inferred from it (F-023, F-024); any new disable path will leak.
- Post-build restore paths (`_restore_chart_settings`, `_apply_ui_state`) run after Generate and can rewrite printtarg widgets (F-003) and hidden spins (F-021).
- Preset and load paths share flags (`_preset_ti1_path`, override rows) that are cleared on some routes and not others (F-016, F-027).
- The thresholds table is read at build time by one path and copied into boxes by another (F-007, F-010).
- Anything changed in `geom_from_build_kwargs` moves the estimate, the hint, the build and the inspector at once; F-001's fix belongs there, with the D02 matrix (55 exact matches) as the regression net.

## 6. Significant issues in detail

F-001 Estimate versus build (high). Tested: Manual engine i1 A4 clip with -f 400 and -f 300, by-grid 12 x 18 with -f 300, patch-first with -f 300, and a loaded 304-patch set. Observed: 418 built versus 425 estimated versus 525 in the hint; 304 versus 450; 306 versus 324; fill-up 15 versus 11; 308 versus 484. Why: the panels are the engine's only capacity feedback and the hint sends users to the editor to fill a page that is full. Options: A feed `area_target_count` and the designed count into the estimate and the hint (same maths as the build; low risk, the Auto-count matrix protects it); B suppress the hint for area-first; C print the assumption behind the estimate. Recommendation: A plus C. Owner decision: only on keeping the hint for area-first.

F-003 Panel and store versus the chart (high). Tested: printtarg builds in fresh runs, twice, with widget values read before, at and after the click and the runner's command compared with the preview. Observed: -L off in the preview, -L in the executed command, -L on in the panel and both stores afterwards; in A1 also -a 0.95 stored for a 1.0 build. Why: the run's record says it was made with a chart it was not made with; the next Generate builds something else; the engine conversion carries the wrong values. Options: A post-build seeding reads the sidecar's `create_chart_settings`; B W1 writes the ChartParams that ran and nothing may write later for that build; C one snapshot for both sidecar records. Recommendation: B with C. Owner decision: yes, which record is the truth for a run.

F-007 Instrument Limits (high). Tested: real Preferences dialog, Top 38 to 50 and ruler 240 to 200, then Generate, then restore. Observed: inspector red against 50 under a chart built at 39 with "Use instrument margins" ticked; panel one Preferences session behind in both directions. Options: A re-run the panel's margin sync after Preferences; B read the table lazily at estimate and build time. Recommendation: A now, B later. No owner decision.

F-018 Guided p3 A4 landscape (high). Tested: Guided defaults for i1 A4, CM A4, p3 A4R, i1 A4 2 pages. Observed: only p3 A4R red (Left 26 < 28, Top 33.4 < 40); the Manual matrix gets 28 mm for the same combo with instrument margins on. Options: A let the clamp win over the clip-band floor and test every Guided default against the table; B correct the p3 landscape seeds if they are wrong. Recommendation: A, after the owner confirms the seeds. Owner decision: yes.

F-024 Generate disabled after a gamut visit (high). Tested in order on a run without a profile: Guided enabled; gamut disables; Guided, Manual and Profiling stay disabled; in D08 the state survived into two more projects. Options: A recompute Generate's state on every module and target change; B keep the gamut rule inside the module; C track the build explicitly instead of reading the button. Recommendation: A plus C. No owner decision.

F-019 / F-020 / F-025 Refusals (medium). Tested: 60 mm patch on 20 x 20, 50 mm margins on 100 x 100, 200 x 500 grid, then a failure after a good chart. Observed: targen runs before the engine refuses; the reason lands only in the hidden log; the previous chart's files return but the preview stays blank; a 1 mm patch grid builds after 6.5 minutes with no warning. Options: grey Generate when the estimate has nothing and show the engine's reason in the frame; wire the preflight floor; reload the restored chart on the failure branch. Recommendation: all three; the floor values need the owner.

F-005 / F-008 / F-009 / F-010 Margins and ruler (medium and low). Tested: clip on versus off across five papers; Max strip and Don't cap in both modes; SS/CR30/custom with the box ticked; ruler 200 with own margins. Observed: as filed. These four share one question for the owner: what the 26 / 28 mm left minimum is (a jig requirement or the clip band itself) and whether area-first may ignore a typed cap.

F-015 / F-016 / F-017 Built-ins (medium and low). Tested: TC9.18, i1 162p, CR30 153p hex, Scanner 3430p through the real activation. Observed: charts correct; info line stale and wrong; toggle moved silently; TC9.18 red against the i1Pro table. Options: describe the preset's route in the info line; announce or grey the toggle; give prebuilt built-ins their own thresholds or re-lay them. Owner decision: whether the i1Pro "by Pharmacist" built-ins stay as they are under the current minimums.

## 7. Questions requiring the owner's decision
1. F-003: which record is the truth for a run's chart settings, what Generate ran with, or what the panel showed a second later? (The store today says the second.)
2. F-005 / F-018: is the i1Pro 26 mm (i1Pro 3+ 28 mm) left minimum a jig requirement independent of the clip border, or the clip band itself? The answer decides whether "Clip border: Off, more patches" can ever be true and whether Guided p3 landscape must be re-laid.
3. F-018: are the i1Pro 3+ A4 landscape minimums (28 left, 40 top) right? If so Guided must honour them.
4. F-008: should area-first respect a typed Max strip length, or is "fill the area" absolute?
5. F-009: for SpectroScan, CR30 and custom papers, should "Use instrument margins" be hidden, unticked, or backed by new seed rows?
6. F-014 / F-020: wire the engine preflight (patch-size floor per instrument, contrast, fit) into the frames, and with which floor values; or drop the module?
7. Margins of 0 mm are accepted and print to the paper edge with notes only (D03 g02): keep as is (printtarg allows it too) or add a floor?
8. Page X/Y offsets may push the block past the instrument margins with the box ticked (D04 f16, red afterwards): allowed by design?
9. Guided hides A2/A3 portrait for i1/p3 although it builds with the engine, which offers them in Manual: intended?
10. A project folder deleted while open is recreated silently on the next Generate (D07b): wanted, or should the app say so?
11. F-016: may a built-in preset move the engine toggle at all, and should "none" restore the user's state?
12. F-017: do the i1Pro "by Pharmacist" built-ins stay recommended as they are, given they fail the shipped i1Pro A4 minimums?
13. F-004: should the Stamp box follow the engine toggle, and in which direction?
14. F-013: is "image plus caption" the intended clip mode?
15. Sidecar precedence (section 10) means unbuilt edits are stored on leaving a run but never shown again while the run has a chart (D07b): is a hint wanted, or is the current silence fine?
16. F-001: should the "last page not full" hint appear for area-first charts at all?

## 8. Evidence index
Screenshots (261 files; each folder's files are named NN-what.png or step-what.png and are listed in the checkpoints):
- 00-launch (18): startup, empty tab, Demo-Full-RGB opened, Guided per instrument, Manual with engine, engine matrix per instrument, Verification and the gamut module.
- A1-engine-vs-printtarg (7): engine build before and after, engine preview, printtarg build and preview, engine on again.
- A2-instruments (55): one preview per instrument x mode x paper.
- A3-layout-modes (28): before and after for m01 to m14.
- A4-margins (28): g01 to g10 before and after, prefs-*, t01 to t03, s01, s02, u01, u02.
- A5-furniture (19): f01 to f18 previews, f15a overlay.
- A6-info-panels (5): run1, run2, reflected external, f003 after printtarg build.
- A7-auto-preview (5): after auto update, debounce tests, real click, clean order.
- A8-presets (19): save dialog, after save/reload/delete, built-ins, preset B after restart, Preferences Chart Layout, fresh session.
- A9-patch-editor (4): editor from the hint, via Tools, apply-or-save, after overwrite.
- A10-extremes (6): 1 patch, patch bigger than the page, margins no room, grid 200x500, 20 pages, after failed build.
- A12-exports (4): PDF, 16-bit, seed a and b.
- B1-guided (12): four Guided builds before and after, transfer, Manual generate after transfer.
- B3-gamut (7): with profile, generated, no profile, Guided and Manual under Verification, before and after the gamut visit.
- B4-calibration (3): selected (leaked state), generated, fresh session.
- B5-header (1), B6-preview (3), B7-runbar (3), B9-window (5), B10-lang-de (13), B11-appearance (6), B12-names-files (10: nine name cases and the legacy project).
Logs and records (Test Runs/logs, 42 files): d00 to d09 .log (every Python log record of the app plus my assess lines), *_results.json / *_matrix.json (every number quoted in the reports), d01_parity_printtarg_by_hand.json, d05b_presetB_recipe_saved.json, d08b_tooltips_dump.json, *_stdout.txt.
Drivers (Test Runs/drivers, 15 files): cc_lib.py, d00_launch_inventory.py, d01_engine_vs_printtarg.py, d02_instrument_matrix.py, d03_layout_modes_and_margins.py, d03b_thresholds_and_stripcap.py, d04_furniture_export_autopreview.py, d05_presets_editor_panels.py, d05b_presets_editor_recheck.py, d06_guided_parity_transfer.py, d07_extremes_names_runbar.py, d07b_extremes_rest.py, d08_gamut_calibration_legacy_ui.py, d08b_rest.py, d09_german_pass.py.
Other evidence: Evidence/sandbox_proof.txt, Evidence/clip_test_logo.png (test image for the clip image mode), Evidence/external_patchset.ti1 (the set loaded through the header icon), Evidence/baseline-before-assessment/*. Projects created in /Users/Basti/ChromIQ-assessment: A1-EngineVsPrinttarg, A2-Instruments, A3-LayoutModes, A5-Furniture, A10-Extremes, B1-Guided, B7-Delete (plus the four demo projects, mutated by the tests: Demo-Full-RGB gained run4 and a verification chart, Demo-Legacy-v1 was migrated).

## 9. Sandbox proof (Evidence/sandbox_proof.txt, 09:42, no driver running)
- `diff <(find ~/ChromIQ -maxdepth 1 | sort) Evidence/baseline-before-assessment/chromiq_home_dirs.txt` : empty, exit 0.
- `defaults read com.chromiq.ChromIQ custom_output_path` : prints an empty string (value=[]).
- The real plist ~/Library/Preferences/com.chromiq.ChromIQ.plist is byte-identical to the baseline copy.
- Files modified since 07:20 today in the real presets store ~/Library/Preferences/ChromIQ: 0; files named *Assess* there: 0; files modified since 07:20 anywhere under ~/ChromIQ: 0.
- All work went to the sandbox ini (custom_output_path=/Users/Basti/ChromIQ-assessment), the sandbox presets copy (which now holds AssessPresetA/B and their prefixed twins; the Chart Layout file D06 added was removed again), and /Users/Basti/ChromIQ-assessment.
