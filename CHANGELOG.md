# Changelog

## v2.5.0
### Added
- **Create Chart — Manual module — printtarg Expert Options**: Eleven new printtarg parameters now available in the Expert Options panel, all correctly wired through to the `printtarg` binary:
  - **N-Channel TIFF (-N)**: For printers with more than 4 ink channels, encodes extra channels using TIFF's alpha-channel slots so all ink values are preserved in a single file.
  - **Apply Calibration (-K)**: Loads a `.cal` file (from Argyll's `printcal`) and remaps all patch values through its curves before chart generation, then embeds the calibration in the `.ti2` output. For printers without native calibration capability.
  - **Include Calibration (-I)**: Embeds a `.cal` file as metadata in the `.ti2` output without modifying patch values. For printers or RIPs that apply calibration natively during printing. Mutually exclusive with -K — enabling one automatically unchecks the other.
  - **Disable TIFF Compression (-C)**: Outputs uncompressed TIFF files for RIPs or drivers that cannot handle LZW-compressed TIFFs.
  - **Dither 8-bit Output (-D)**: Uses error-diffusion dithering when down-sampling from internal 16-bit precision to 8-bit TIFF output.
  - **Suppress CUPS CMM Header (-U)**: Removes the `cups-disable-cmm` job ticket comment from PostScript and EPS output files.
  - **Randomisation Seed (-R)**: Sets the starting seed for patch randomisation, producing identical layouts across sessions for reproducibility.
  - **Quantize Bits (-Q)**: Rounds all patch colour values to a specified bit depth before chart generation.
  - **Spacer-Only Scale (-A)**: Scales spacer bars independently from patch dimensions (complements the existing Patch Size Scale `-a`).
  - **No Spacers (-n)**: Removes all spacer bars between patches and strips.
  - **Force Colored Spacers (-c)**: Forces spacer areas to render in colour rather than black/white.

## v2.4.1
### Fixed
- **TIFF Preview — Multi-channel files with more than 4 inks**: PIL silently drops extra channels when opening Separated TIFFs with 5 or more inks (e.g. CMYK + LC LM). The preview now routes these files directly to tifffile, preserving all ink channels.
- **TIFF Preview — 16-bit and high-bit-depth TIFFs via tifffile**: Non-uint8 pixel data was passed raw to PIL, corrupting colours. The loader now normalises all data to uint8 before converting to RGB.

## v2.4.0
### Changed
- **Print Chart — Printing pipeline**: Replaced the TIFF/CUPS-RGB path with a PostScript Level 2/3 pipeline. The PS document embeds device-dependent colour spaces (`/DeviceGray`, `/DeviceRGB`, `/DeviceCMYK`, `/DeviceN`) and the `%cupsJobTicket: cups-disable-cmm` header, so CUPS and macOS ColorSync apply zero colour transforms to the profiling target — the pixel values that leave the application are exactly the values the spectrophotometer measures.
### Added
- **Print Chart — CMYK and multi-channel target support**: Profiling targets with 4 channels (CMYK) and 5–17 channels (DeviceN, e.g. CMYK + LC LM or extended-gamut inks) are now printed correctly. Previously all targets were force-cast to DeviceRGB by CUPS, corrupting CMYK and multi-ink patch data.
- **Print Chart — 16-bit TIFF support**: 16-bit profiling targets generated with `printtarg -T300` are printed as PostScript Level 3 with 16-bit colour components, preserving full bit depth for printers and RIPs with a true 16-bit pipeline.
- **Print Chart — Automatic TIFF fallback for non-PostScript printers**: Driverless / AirPrint printers (e.g. Epson EcoTank series) reject PostScript at the CUPS level. The pipeline now detects this and automatically retries by submitting the original TIFF with colour-space-aware CUPS raster options (`cupsColorSpace`, `ColorModel`), bypassing ColorSync without requiring PostScript support on the printer.

## v2.3.3
### Fixed
- **Create Chart — Manual module — Total Patch Count (-f) with 0**: Setting `-f` to 0 now passes `-f 0` directly to targen, letting targen determine the patch count automatically. Previously, 0 triggered a page-capacity database lookup (the guided-mode behaviour), causing the page to fill completely regardless of other parameters such as Single Channel Steps.

## v2.3.2
### Fixed
- **TIFF Preview — LZW-compressed multi-channel TIFFs**: Bundled app threw `could not import name 'lzw_decode' from 'imagecodecs'` when opening LZW-compressed CMYK or multi-ink TIFFs. PyInstaller's static analysis missed imagecodecs' compiled codec extensions; the spec now uses `collect_all('imagecodecs')` to include every binary.

## v2.3.1
### Fixed
- **Create Chart — Manual module — Total Patch Count (-f)**: The spinbox minimum was hardcoded to 50, preventing values below 50 from being entered. The minimum is now 0, matching targen's actual accepted range. Setting 0 passes `-f 0` to targen, which lets targen determine the patch count automatically based on other parameters.

## v2.3.0
### Added
- **TIFF Preview — Multi-channel support**: The preview widget now loads and displays CMYK and multi-channel TIFFs (up to 8 inks: LC, LM, Orange, Green, Violet, etc.) generated by ArgyllCMS. Previously, CMYK files showed wrong colours and 6–8 channel files failed silently.
- **TIFF Preview — ICC colour accuracy**: CMYK channels are now converted to sRGB using the bundled US Web Coated SWOP v2 ICC profile, with system Adobe/ColorSync profiles as fallbacks. Colours now match Photoshop rather than the naive subtractive formula.
- **TIFF Preview — Ink channel sidecar**: After chart generation a `.channels.json` sidecar is written alongside the TIFFs so that re-loading the file in a later session automatically identifies the correct ink order (C, M, Y, K, LC, LM, …) without any user input.
- **Stripe detection — Multi-channel TIFFs**: The Measure tab's strip auto-detection now works on multi-channel Separated TIFFs.
### Fixed
- **TIFF Preview — Sizing on tab switch**: When a chart was generated while on the Create Chart tab, the Print and Measure tab previews rendered too small with dark borders until something else triggered a repaint. The preview now repaints immediately when the tab is made active.

## v2.2.3
### Fixed
- **Create Chart — Manual module — Expert targen options**: Pre-conditioning Profile (`-c`), Calibration Override (`-C`), Add/Remove Colorant (`-D`), Neutral Axis Emphasis (`-N`), and Dark Region Emphasis (`-V`) were rendered in the UI but silently ignored — none of their values were passed to `targen`. All five are now correctly collected and included in the command.
- **App crash on close (macOS "quit unexpectedly")**: Closing the app while a measurement was running, or shortly after one completed, could trigger a segfault because a background PTY reader thread was still emitting Qt signals into objects being torn down. `closeEvent` now shuts down all running processes, closes the PTY file descriptor, and joins the reader thread before handing control back to Qt.

## v2.2.2
### Fixed
- **Create Chart — Manual module — Expert Options**: Preserve Patch Order (`-r`), Force B&W Spacers (`-b`), and Don't Limit Strip Length (`-P`) checkboxes now correctly pass their flags to printtarg. Previously toggling them had no effect because `ParameterWidget.get_raw_value()` was missing the same guard that `get_value()` already had for expert boolean widgets.

## v2.2.1
### Improved
- **Create Chart → Generate Chart**: Clicking Generate Chart now resets the Build Profile and Check & Refine tabs — clears any loaded .ti3 file, profile description, manufacturer, model, and copyright fields, and disables the Build button — so stale data from a previous session is never accidentally carried forward.
- **Create Chart — Guided module — Paper Size**: A3+ Portrait (329 × 483 mm) is now hidden when i1Pro 3 Plus is selected as the instrument, since its patch capacity is too low for a usable profile at that size.

## v2.2.0
### Added
- **Create Chart — Paper Size: Custom**: Both the Manual and Guided modules now include a "Custom (enter dimensions)" option in the Paper Size dropdown. Selecting it reveals width and height fields (in mm) whose values are passed directly to printtarg as `-pWxH`.
- **Create Chart — Paper Size: A3+**: A3+ Portrait (329 × 483 mm) and A3+ Landscape (483 × 329 mm) are now available as named paper sizes in both the Manual and Guided modules.
- **Create Chart — Paper Size: Photo formats**: 8×10" (203 × 254 mm), 5×7" (127 × 178 mm), and 4×6" (102 × 152 mm) added to both modules. In Guided mode, 5×7" and 4×6" are hidden for i1Pro 3 Plus where patch counts are too low for a usable profile.
- **Create Chart — Don't Limit Strip Length (-P)**: New expert option in the printtarg Expert Options section. Removes printtarg's default strip-length cap, useful for narrow roll paper or minimising strip count.
### Improved
- **Create Chart — Paper Size dropdown**: Sizes are now ordered from largest to smallest (A2 → A3+ → A3 → Tabloid → Legal → A4 → Letter → photo formats) in both the Manual and Guided modules.
- **Patch database**: All new paper sizes measured empirically with Argyll 3.5.0 for every instrument (i1Pro, i1Pro 3 Plus, ColorMunki standard and double-density, SpectroScan) × border-suppress setting combination. No estimated values.

## v2.1.2
### Improved
- **Settings — Behaviour**: New "Restore last active tab on launch" option. When enabled (default), the app re-opens on whichever tab was active when it was closed. When disabled, it always starts on the first tab.
- **Settings — Checkbox style**: Checked checkboxes in the Settings dialog now use the same grey/white colour as the "Restore Factory Defaults" button instead of the global cyan accent.
- **Print Chart tab**: The info panel now includes a note that colour management is disabled automatically via CUPS options, ensuring the printer always receives unaltered RGB values.
### Fixed
- **Create Chart — Guided module**: Tooltip buttons for "Double density", "Number of pages", and "Suppress left clip border" were positioned next to their controls instead of right-aligned. All three now align with the rest of the panel.
- **Build Profile — Manual module**: Tooltip buttons for "Smoothing / Noise" and "Dark Region Emphasis" in the Measurement & Smoothing section were positioned next to their controls instead of right-aligned.
- **Measure tab — Guided module**: Patch consistency tolerance (-T) option is now visible and enabled by default (0.7), pre-checked on every launch.

## v2.1.1
### Improved
- **All tabs — Guided module**: Each guided panel now shows a small motivational statement directly above the action buttons — a headline in Georgia with an accent-coloured italic punctuation mark and a one-line subtext in Menlo. Measure: "Keep calm!" / "Scan each strip with a slow, steady motion." Check & Refine: "Are you nervous?" / "Your colors are in good hands." Build Profile: "Ready to build?" / "Awaiting your command." — switches to "Working hard…" / "Good things take time." while colprof runs. Print Chart: "Feed the beast!" / "Your printer is hungry." — permanently visible, with load and print buttons moved to the bottom of the panel for a cleaner layout.
### Fixed
- **App bundle codesigning**: Replaced `codesign --deep` with an explicit bottom-up signing pass (leaf `.so`/`.dylib` → `.framework` bundles → outer `.app`). The previous `--deep` flag was re-signing already-signed internals and corrupting the code directory on Apple Silicon, causing Gatekeeper to reject the ARM build.

## v2.1.0
### Added
- **Measure tab — Manual mode refinement**: "Refine existing measurement (-r)" and "Use refinement strips file" options are now available in Manual mode, mirroring the Guided module. The refine option and strip file picker appear automatically when a `.ti3` file is present, and the guided strip-by-strip navigation activates when a strips file is loaded.

### Improved
- **Measure tab — Guided module**: Measurement Instrument section, Skip Initial Calibration, Patch-by-Patch Mode, and Additional Options section are now hidden in Guided mode, keeping the panel focused on the essential workflow steps.
- **Build Profile tab — Guided module**: Algorithm, Quality, and B2A table rows are hidden in Guided mode (Profile Description remains visible). Measurement & Smoothing, Color Science, and Advanced sections are hidden entirely. In Gamut Mapping, only the Gamut Source file picker is shown; Perceptual/Saturation Intent Overrides and nP/nS/nI flags rows are hidden.
- **Check & Refine tab — Guided module**: Delta E Formula, Rendering Intent, Sort by ΔE, and Verbosity rows are hidden in Guided mode (only the re-measurement threshold remains visible). Advanced Options section is hidden entirely.
- **Measure tab layout**: Fixed excess gap between the first section and the module action buttons; corrected spacing between the action buttons and the log output to match the 8 px standard used across all other tabs.

## v2.0.9
### Improved
- **Create Chart — Calibration Override (-C)**: New expert option in the targen Expert Options section. Accepts a `.cal` file whose calibration curves are applied when estimating the ink limit for patch generation, overriding any `.cal` embedded in a previous .ti3. Type `none` to explicitly suppress .cal use.

## v2.0.8
### Improved
- **Create Chart — Device Type (-d)**: Expanded from 6 to 16 options (0–15) matching targen 3.5.0 exactly. Adds Print grey (0) and all multi-channel CMYK combinations (CMYK + Light CM/CMK, CMYK + extended gamut inks). Labels updated to match targen's own output.
- **Create Chart — Add/Remove Colorant (-D)**: New expert option that lets you add or remove a single ink colorant from the base Device Type combination. Supports all 20 colorants known to targen (Cyan, Magenta, Yellow, Black, Orange, Red, Green, Blue, Violet, White, and their light/medium variants).
- **Settings dialog**: Focus border on path input fields is now a neutral grey (#f4f4f4) instead of the global cyan accent colour.

## v2.0.7
### Improved
- **Measure tab — Calibration Complete dialog**: Restructured with a visual key-binding table (Menlo, accent colour) for the navigation keys, separate prose and footnote sections. OK button is now tinted in the tab's green accent colour.
- **Measure tab**: All other tabs are disabled and visually dimmed while a measurement is running, preventing accidental tab switches mid-scan.
- **Build Profile tab**: Progress bar is now always visible — dimmed and static when idle, animated during a build.
- **Build Profile tab**: All other tabs are disabled and visually dimmed while colprof is running.
- **Build Profile tab — Profile Built dialog**: "Install on this Mac" and "Check Profile Quality" buttons are now tinted in the tab's cyan accent colour.
- **Spinboxes**: The focus border now runs continuously around the entire widget — the up/down buttons no longer interrupt it.
### Fixed
- ARM and universal2 app bundles are now reliably ad-hoc signed: all `.so` and `.dylib` files inside the bundle are signed individually before the top-level bundle sign, preventing Gatekeeper rejections on Apple Silicon.

## v2.0.6
### Improved
- Tab workflow headers: step label increased to 12 pt and headline increased to 30 pt for better legibility.

## v2.0.5
### Improved
- All button labels across every tab, dialog, and the Settings window now use Menlo font in all-caps, applied globally via a Qt event filter — future buttons inherit the style automatically.
- Empty TIFF preview placeholder text uses the same Menlo all-caps treatment.
- Status bar messages (ArgyllCMS warnings, update notifications) moved from the main-window status bar into the bottom of the left control panel on tabs 1–3, so the splitter divider now reaches the full window height.
- TIFF preview navigation buttons (‹ Prev / Next ›) now have 12 px of symmetric padding on all four sides.
- Left control panels are now fixed-width and non-resizable: Create Chart locks at 700 px, Print Chart and Measure both lock at 580 px.

## v2.0.4
### Improved
- Accent-coloured gradient wash at the top of each tab's control panel fades with a quadratic ease-out curve for a smoother, more natural look.
- A 2 px vertical accent line in the active tab's colour now runs along the full left edge of the window, below the tab bar.
- Active tab button background tint reduced to 6 % opacity for a subtler highlight.
- **Create Chart — Calculated Patches** section redesigned: patch count displayed in large Georgia 56 pt with letter-spacing 85 %, subtitle and paper info in small Menlo caps, and a five-segment spectrum bar underneath.
- Preview panel labels (CHART PREVIEW, PRINT PREVIEW) now use Menlo 9 pt grey all-caps.
- Calculated Patches group-box internal padding adjusted so top and bottom spacing are visually balanced.

## v2.0.3
### Improved
- Each tab now shows a workflow header at the top of its controls panel: a small coloured accent stroke followed by a step indicator (Menlo, all-caps, grey) and a large headline (Georgia 24 pt, white) — matching the tab's accent colour.
- Minimum window size increased slightly (1440 × 1025 px).

## v2.0.2
### Fixed
- arm64 DMG is now properly ad-hoc signed — the app opens on macOS 13+ via right-click → Open without Gatekeeper blocking it.
- Build is now automated via GitHub Actions (arm64 + universal2 in a single workflow).

## v2.0.1
### Fixed
- Settings lockdown during Build Profile — all settings widgets are disabled while colprof runs, preventing accidental changes mid-build.
- Guided panel section margins are now uniform across all five sections in the Create Chart tab.

## v2.0.0
### Added
- Complete UI redesign with the Spectrum design language: custom gradient masthead, per-tab accent colors, animated segment progress bar, and a new font stack (Inter, Instrument Serif, JetBrains Mono).
- Settings button embedded in the header.
- Colored folder and refresh icons on all file dialog buttons (HiDPI-aware).
- Start Measurement button is disabled until a .ti2 file is loaded.
- Analyse button in Check & Refine is disabled until both required files are loaded.
- Dialog primary buttons are tinted to match the active tab's color scheme.
- New monogram app icon.

## v1.7.1
### Fixed
- **Measure tab layout** — the empty space now appears between the Target File section and the action buttons, keeping the buttons and log output together at the bottom of the panel.

## v1.7.0
### Added
- **Spectral filter type option in Measure tab** — a new `-F` option in Additional Options lets you override the filter/illuminant condition used by the instrument: None (M0), D50 (M1), D65, UV Cut (M2), or Polarizing (M3). Disabled by default; D50 (M1) is pre-selected for when you need it.
### Improved
- **Measure tab layout** — the "Measurement Instrument" and "Target File (.ti2)" sections no longer stretch to fill the left panel height. They now sit at their natural content size, with the log output anchored to the bottom of the panel.
- **Additional Options input sizing** — combo boxes and spin boxes in Additional Options are now the same compact height as plain checkbox rows, giving the section a uniform appearance.

## v1.6.1
### Improved
- **AirPrint driver warning in Print tab** — when no configurable options are
  detected for the selected printer, the Print tab now shows an informative
  message explaining that macOS often installs AirPrint or Driverless drivers
  automatically, how to identify them in System Settings → Printers & Scanners,
  and how to reinstall the printer with the manufacturer's native PPD driver.

## v1.6.0
### Added
- **Manual mode presets** — the Create Chart tab's Manual mode now has a Presets section between the Output and parameter groups. Use the + button to save the current parameter values under a custom name, select a preset from the list to restore it instantly, and use the − button to delete it. Presets survive a factory settings reset.

## v1.5.2
### Fixed
- **Print tab button labels no longer clipped** — buttons in the Print tab are now taller and their labels are split across two lines so text fits correctly at all window sizes.
- **Save as Defaults button alignment** — on the Chart, Measure, Profile, and Check & Refine tabs, the "Save as Defaults" button was rendering at a different height than its neighbours. It now matches the row height exactly.

## v1.5.1
### Fixed
- **Update checker SSL error** — the "Check for Updates" feature failed with a certificate verification error inside the app bundle. Fixed by bundling certifi's CA certificates with the app.

## v1.5.0
### Added
- **Install Profile button in quality check dialog** — after running a quality check the result popup now offers a button to install the profile directly. The button label reflects the quality grade: "Install Profile" (Excellent), "Install Profile As Is" (Good / Acceptable), or "Install Profile Anyway" (Needs Work).
- **Update checker** — a "Check for Updates" button in Settings checks the GitHub releases page and shows the result inline. The app also performs a silent background check 3 seconds after launch and shows a status bar notice when a newer version is available.
### Improved
- **Quality report file numbering** — report files now always start at `_1_` (e.g. `Quality_Check_1_<stem>.txt`) so multiple reports sort correctly in any file browser.
- **Gamut source file browser** — the Browse button for the gamut source profile in Build Profile now opens directly in ArgyllCMS's `ref/` folder where the standard reference ICC profiles live.
- **Margin parameter simplified** — the duplicate "TIFF File Margin" (`-M`) expert option is removed from Create Chart. The page margin and TIFF margin are always kept in sync; a single "Margin (mm)" control handles both.
- **Sort disabled in summary mode** — in Check & Refine, "Sort by ΔE" is automatically unchecked and greyed out when verbosity is set to "Summary only", since sorting has no effect without per-patch output.
- **Settings credits** — the Settings dialog now credits ArgyllCMS author Graeme Gill and Knut Georg Larsson.

## v1.4.0
### Added
- **Clear Print Queue button** — cancels all pending and stuck jobs for the selected printer directly from the Print tab, without needing to open a system tool.
- **Stuck-job pre-print check** — before sending a job, ChromIQ detects held, stopped, or aborted jobs in the CUPS queue and offers to clear them first ("Clear & Print / Print Anyway / Cancel").
- **Printer reachability check** — a clear error dialog is shown if the selected printer is offline before a job is submitted.
### Improved
- **Print option combos unlock sequentially** — each option only becomes active once the preceding one is set, and incompatible quality values are filtered automatically based on the selected media type (Epson EPIJ exact rules, PPD UIConstraints, or general keyword heuristics for other drivers).
- **Color management is now always disabled automatically** — no manual option selection required; the correct CUPS flags are injected into every print job.
- **Multi-page TIFF handling** — "Print Current Page" and "Print All Pages" now correctly extract and send individual frames from multi-page TIFF files.
- **Printer detection** now uses the pycups API directly instead of parsing `lpstat` output, giving more reliable results across locales.
- **Drying time guidance** updated to reflect professional recommendations (at least 1 h; 24 h for best accuracy).
- **New app icon.**

## v1.3.1
### Improved
- **Check & Refine start-over logic** now uses OR logic: starting over is recommended when more than 50% of individual patches exceed the ΔE threshold, *or* when more than 75% of strips are flagged. This prevents false "start over" recommendations on small charts where a few outlier patches flag most strips, while still correctly catching large charts where nearly every strip needs re-measuring.
- **Settings dialog** now shows author credit at the bottom.

## v1.3.0
### Added
- **Build progress feedback** — the Build Profile button now shows "Building Profile…" while colprof runs, and a thin progress bar appears below it so it is clear the app is working. A result dialog appears on completion offering to install the profile, go to Check & Refine, or dismiss.
### Improved
- **Gamut Mapping defaults** — the gamut source is now enabled by default (Perceptual + Saturation, sRGB from the ArgyllCMS ref folder). Previously both options were disabled, leaving colprof to use an internal default that is not optimised for any real working colour space. The two separate `-s`/`-S` checkboxes are replaced by a single selector, preventing conflicting settings.
- **Gamut Mapping tooltips** rewritten to explain practical outcomes ("colours outside your printer's range are compressed to fit…") rather than raw CLI flag descriptions.
- **Measure tab** — the tooltip for "Refine existing measurement" is now hidden when the option itself is hidden, reducing clutter when no `.ti3` file is present.
### Fixed
- The `-s` (perceptual-only gamut source) path and enabled state were not saved to settings; the option had no effect after restarting the app.

## v1.2.0
### Added
- **Smart ti2 loading** in Print and Measure tabs: when a `.ti2` file is loaded from outside the working folder, a copy dialog guides the user to name and import the chart files. When the file is already in the working folder, the user can choose to continue printing as-is or use it as the base for a new profile.
### Improved
- **Profile quality grading** now accounts for peak ΔE as well as average ΔE. A profile with an excellent average but high-error outlier patches is now graded accordingly, and the explanation tells the user which metric is limiting the grade.
- **Guided refinement** recommendation logic is now patch-based: the "start over" recommendation is only triggered when more than 50 % of individual patches exceed the threshold, not when 50 % of strips are flagged. This avoids false "start over" recommendations on small charts with a handful of outlier patches.
- Log file moved to `~/Library/Logs/ChromIQ/chromiq.log` (standard macOS location). The app no longer creates a `ChromIQ` folder in the user's home directory on launch.
### Fixed
- Per-patch profcheck results were sometimes lost due to a QProcess output-buffer race condition. The fix ensures all output is drained before the process finish callback runs.
- The profile quality assessment popup was not shown when `profcheck` exited with a non-zero code (its normal exit behaviour when errors are found).
- An unhandled exception in the quality report file-write no longer silently prevents the assessment dialog from appearing.

## v1.1.6
### Fixed
- A3 Portrait is now hidden in guided mode when i1Pro / i1Pro 2 / i1Pro 3 is selected, matching the existing behaviour for i1Pro 3 Plus. A3 Landscape is shown and selected automatically instead.

## v1.1.5
### Fixed
- i1Pro 3 Plus patch capacity was incorrectly assumed identical to the regular i1Pro. All paper sizes have now been measured with `-i3p` and the database updated (e.g. A4: 504 → 108, A3: 735 → 153). Charts for this instrument will now correctly fill the page.
- A3 Portrait is hidden in guided mode when i1Pro 3 Plus is selected — it yields only 153 patches vs 225 on A3 Landscape, so the landscape variant is offered and selected automatically.
### Improved
- Guided mode now adds grey-axis patches (`-g`) scaled to total patch count: `max(8, total // 30)`, capped at 64. Previously grey patches were always disabled.
- White and black patches (`-e`, `-B`) in guided mode now scale with page count: base + (pages − 1) × 2 per type.

## v1.1.3
### Fixed
- Tooltip (ⓘ) and settings (⚙) icons now render crisp on Retina / HiDPI displays instead of appearing blurry.

## v1.1.2
### Improved
- The universal DMG now runs **natively on both Apple Silicon and Intel Macs** (universal2 fat binary). Previously it was arm64 only and required Rosetta on Intel machines.

## v1.1.1
### Improved
- macOS title bar now matches the dark app theme.
- Check & Refine: re-measurement threshold is now user-editable.
- Check & Refine: the resume option is hidden when no matching `.ti3` file exists.
- Tooltip buttons remain clickable even when their parent panel is collapsed.
### Fixed
- Button heights and vertical alignment corrected throughout the UI.

## v1.1.0
### Added
- **Check & Refine tab** — run `profcheck` on a finished profile, see per-patch ΔE results, and selectively re-measure only the worst patches with guided strip-by-strip instructions.
### Improved
- File open dialogs now show only relevant file types and include sidebar shortcuts for quick navigation.

## v1.0.3
### Fixed
- Pink / magenta screen artifact on Apple Silicon during measurement (disabled native file dialogs).
- App now auto-detects ArgyllCMS on launch and shows a clear setup guide if it is not found.
- Wrong-strip dialog now appears when chartread detects a mismatch during measurement.
- Unexpected colour-response warning dialog added (high ΔE on a known patch).
- "No instrument detected" dialog shown at measurement start instead of silent failure.
### Added
- Resume measurement flag (`-r`) exposed in measurement options.

## v1.0.2
### Added
- Calibration prompt dialog when chartread asks to position the instrument.
- Navigation instructions popup shown after instrument calibration completes.
- Completion dialog when all stripes have been successfully measured.
- Retry dialog on strip read failure.
### Improved
- Measurement settings are disabled while chartread is running to prevent accidental changes.

## v1.0.1
### Added
- Initial public release as a distributable DMG.
- Resolved macOS App Translocation crash (app must be run from /Applications).
- PyQt6 compatibility fix for macOS 15 Sequoia.
