# Checkpoint 08: B3 gamut, B4 calibration, B5 header, B6 preview, B8 tooltips, B9 window, B10 German, B11 appearance, legacy migration, failed-build restore

Time: 09:26 to 09:41. Drivers: d08_gamut_calibration_legacy_ui.py (killed by me at 09:33 when the header Load patch set raised a five-way box my arming did not cover), d08b_rest.py (complete), d09_german_pass.py (complete). Data: d08_results.json, d08b_results.json, d09_results.json, d08b_tooltips_dump.json, the three .log files. Shots: Screenshots/B3-gamut, B4-calibration, B5-header, B6-preview, B9-window, B10-lang-de, B11-appearance, B12-names-files/l01, A10-extremes/x10.

## B3 From Profile Gamut (Demo-Full-RGB) - OBSERVED
- Run type Verification: bar shows "Verification: Overwrite 2026-05-20 09:05 / Overwrite 2026-06-24 16:40 / New verification"; Build Profile tab disabled; location runs/run2/verifications/.
- With a profile (run2): module visible; count 56 (range 50 to 5000), Auto off; Margin "Stay safely inside (recommended)" / "Use the full printable range"; Intent "Absolute colorimetric (recommended)" / "Media-relative"; count line "5123 of the 5960 reference colours (86 %) are printable with this profile. Your chart: 56 colours plus the 8 cube corners = 64 patches. That is about one sheet with your current layout." Full range: 96 %.
- Generate: S4 question "The verification measurements already made in this run used the chart you are about to replace" -> Generate the new chart -> 75 patches (64 + 11 fill-up, 15 x 5), estimate equal, Margins OK, "colorimetric reference was stored beside the chart (Demo-Full-RGB-verify-reference.ti3)", chart in verifications/.
- Without a profile (run3): group hidden, the "This run needs a finished profile first" card, Generate disabled, Stop visible (F-023), and from then on Generate stays disabled in Guided, Manual and under Profiling (F-024, proven in order in D08b).
- Guided and Manual under Verification without a profile show the agreed "There's no finished profile in this run yet ... You can go ahead and create the chart" box; Generate is enabled there until the gamut module has been visited (F-024).

## B4 Calibration run type - OBSERVED
- With calibration_mode on, Run type gains "Calibration"; selecting it fixes "Profile run" to "Project calibration", location cal/, hides the GUIDED / MANUAL / GAMUT buttons, shows the calibration chart (64, 16 x 4) with targen -f 64, -e 4, -B 4, -g 0 and the Auto boxes greyed; -l / -m / -M rows hidden. Tab 4 is renamed "Calibration & Profiling".
- Fresh session: Generate enabled; pressing it asks "This project already has a finished calibration, and generating a new chart starts that work over" with Replace the calibration / Cancel (cancelled). Matches calibration_run_type.md section 4.4 protection.
- The estimate column kept the previous target's prediction (F-002 instance).

## B5 header: Load patch set - OBSERVED
- The icon opens a file picker (replaced by a path in the driver, logged). With a project open it asks "Where should this patch set's chart go?" with Cancel / Replace run 3 / Build it as a new run instead / Replace only the chart / Start a new project. "Build it as a new run instead" created run4 and built 308 (22 x 14, 4 fill-up) from the 304-patch set; the estimate showed a 484 capacity fill (Auto count on; F-001 instance). The armed set then survived opening other projects (F-027, PARTIAL).

## B6 preview - OBSERVED
- 4-page chart: Page 1/4 to 4/4 with Prev/Next enabling correctly; the frames re-measure per page (112 per page). Overlays: instrument guides, measured guides and pointer coordinates toggle without error; zoom 2x and 0.5x render (shots v01, v02).

## B8 tooltips - OBSERVED
- 144 info buttons scanned in the tab; none empty; no "(s)" plural; four contain "no longer", all describing current behaviour. Content accuracy against Argyll: F-022.

## B9 window sizes - OBSERVED
- 1280 x 800: left pane 548 px, preview 696 x 282 px, both frames 311 px tall, everything present; the measured frame's row labels clip (F-026). 1700 x 1050 and maximised 1728 x 1051: clean.

## B10 German - OBSERVED
- No clipped control in Guided, Manual or the nine Preferences tabs at 1280 or 1700; the layout frame's header "auf dem Bildschirm" is cut at both sizes and the measured frame's labels clip at 1280 (F-028).

## B11 appearance - OBSERVED
- Light, dark and neutral applied live without error; shots a-light/dark/neutral-{guided,manual}.png for the owner's own reading (no defects found in a glance; not a colour audit).

## Legacy project (Demo-Legacy-v1, schema 1) - OBSERVED
- Opened without a dialog; project.json now schema 3; the .cht / diag files moved into cache/, the Quality_Check and Refine_Strips reports into reports/, "Where are my files.txt" written; run bar Run 2, 3 pages, Margins OK. Migration in place as documented.

## Failed build after a good chart - OBSERVED
- Files identical before and after the failure (set-aside works); preview 0 pages and a stale "Margins: OK" until a run round trip (F-025).

## Findings filed this checkpoint
F-023 (low), F-024 (high), F-025 (medium), F-026 (low), F-027 (medium, PARTIAL), F-028 (low). Earlier: F-002 gained two instances, F-001 one.

## Regression baseline additions
- Gamut module: count line, margin and intent choices, S4 question, reference file, chart in verifications/.
- Calibration target: fixed bar, cal/ location, mode buttons hidden, prefilled targen, replace question.
- Load patch set: five-way destination question; "new run" path works.
- Preview paging, overlays and zoom.
- Legacy schema-1 project migrates in place silently and correctly.
- Failed builds never lose the previous chart's files.
