# Changelog

## v3.2.9
### Fixed
- **Landscape charts printed as portrait on the CUPS PostScript path** (#14, #15).
  When the chart's pixel aspect contradicted the selected paper orientation,
  `PostScriptGenerator` was emitting `setpagedevice` with portrait dimensions
  and then drawing the landscape image on top. Apple's `pstops` filter
  double-rotated the result: HP and some other CUPS drivers clipped columns
  A–E (#14) or silently dropped the job entirely (#15). `PostScriptGenerator`
  now swaps `page_w`/`page_h` in `setpagedevice` to match the TIFF aspect
  before the PostScript is written. `CupsRawPrinter._build_lp_command_ps()` no
  longer forwards `orientation-requested` to `lp` on the PostScript path — the
  document now fully describes its own geometry, so `pstops` has nothing to
  rotate. The raw-TIFF fallback path is unaffected and still uses
  `orientation-requested`.

## v3.2.8
### Fixed
- **Intel-only DMG (`ChromIQ-macOS-x86_64.dmg`) failed to launch** with
  `[PYI-3463:ERROR] Could not load PyInstaller's embedded PKG archive from
  the executable`. The v3.2.7 derive-x86_64 step ran `lipo -thin x86_64`
  over every Mach-O in the universal bundle, including the PyInstaller
  bootloader at `Contents/MacOS/ChromIQ`. The bootloader has its onedir
  PKG archive appended *after* the Mach-O slices; `lipo` writes only the
  Mach-O bytes and silently discards the trailing archive, bricking the
  binary. The CI step now skips the bootloader (it stays universal2 — a
  ~1 MB cost; macOS Intel picks the x86_64 slice at exec time anyway).
- **Universal DMG (`ChromIQ-macOS-universal.dmg`) crashed on import numpy**
  with `Library not loaded: @rpath/libscipy_openblas64_.dylib`. numpy 2.4+
  vendors a SciPy-built OpenBLAS dylib that PyInstaller's bundled
  `hook-numpy.py` did not pick up on the universal2 build, leaving
  `Contents/Frameworks/libscipy_openblas64_.dylib` absent. The spec now
  collects numpy's dynamic libs explicitly (`collect_dynamic_libs('numpy')`),
  and a new CI step asserts the OpenBLAS dylib is in the bundle so a hook
  regression can never silently ship again.

## v3.2.7
### Fixed
- **Native macOS print dialog ignored chart paper size**: the new
  Sequoia/Tahoe print panel hides the standalone paper-size control, and
  ChromIQ's native print path never called `setPaperSize_`, so the job
  inherited whatever paper was last in `sharedPrintInfo` (typically
  Letter/A4). With clip pagination set on the print info, charts larger
  than that default were silently cropped at print time. The native
  print path now sets the paper size to the chart's own dimensions
  (computed from the TIFF's resolution tag) before opening the dialog,
  and explicitly enables `NSPrintPanelShowsPaperSize`,
  `NSPrintPanelShowsOrientation`, `NSPrintPanelShowsScaling` and
  `NSPrintPanelShowsPageSetupAccessory` on the panel so the user can
  still override paper / orientation / scale in the dialog or via the
  driver's Printer Options pane.

## v3.2.6
### Fixed
- **Universal DMG launches on Apple Silicon but crashed on Intel Macs** with
  `dlopen … QtGui.framework/Versions/A/QtGui … incompatible architecture`.
  The CI lipo step that fattens arch-specific wheels into universal2 only
  matched `*.so` and `*.dylib` files, so the Qt6 framework binaries (which
  live at `PyQt6/Qt6/lib/Qt*.framework/Versions/A/Qt*` with no extension)
  were silently left arm64-only. `PyQt6-Qt6` and `PyQt6-WebEngine-Qt6` were
  also missing from the merge list entirely. The lipo helper now walks the
  x86_64 wheel by relative path and merges every Mach-O it finds, and both
  Qt framework packages are included — restoring true universal2 builds.

## v3.2.5
### Added
- **Report a Bug button in Preferences**: the bottom row of the Preferences
  dialog now exposes a *Report a Bug…* button that opens the GitHub bug-report
  form (pre-filled with the right template) in the user's default browser.
  Sits next to *Restore Factory Defaults* and *Check for Updates* so all three
  "GitHub / external" actions cluster together on the left of the row, with
  Cancel / OK pinned to the right as before.

### Changed
- **Preferences dialog widened from 840 → 900 px** so the bottom-row buttons
  (Restore Factory Defaults, Report a Bug…, Check for Updates, Cancel, OK)
  all show their full labels without truncation.

### Project
- **Reporting issues & feedback section added to the README**, with deep-links
  that jump straight into the bug-report and feature-request forms (skipping
  the GitHub template chooser). The lone Windows-section feedback link now
  also points at the bug-report form rather than the issues list.
- **`.github/SUPPORT.md` added** so GitHub surfaces a *Help* entry in the
  new-issue chooser sidebar and on the repo's community profile, routing
  users to bugs / features / Discussions / the ArgyllCMS mailing list.

## v3.2.4
### Fixed
- **Stale files reappear after a restart**: with *Restore last session* enabled,
  clearing a `.ti3` / `.icc` / cal-`.ti3` mid-session previously didn't take
  effect on the next launch — the cleared paths still lived in settings and
  were resurrected. `clear_files()` in the Build Profile tab now also nulls
  `_cal_ti3_path` (which was being skipped) and the Measure and Build Profile
  tab clear methods eagerly write empty values to `session_ti1_path`,
  `session_ti3_path`, `session_icc_path`, and `session_cal_ti3_path` instead
  of relying on the quit-time save — so a crash before quit can no longer
  resurrect cleared files.

- **Working-folder name not sanitised against filesystem-illegal characters**:
  `FileManager.set_target_name` previously only replaced spaces with `-`. A
  printer name containing `/` (CUPS permits it) or a manually-typed chart name
  with `:` / `\` / control chars could create unintended subfolders or fail
  outright on Windows. Names are now run through a single `_sanitise` rule
  that keeps alnum / `_` / `-` / `.`, replaces everything else with `_`,
  strips leading and trailing dots (Windows forbids them), and falls back to
  `"session"` if the result is empty. Auto-generated session names are
  unchanged (they were already hyphenated).

- **Dead "high ΔE" warning in the Build Profile result dialog**:
  `ProfileBuilder.sanity_check` contained a regex `r"delta E .{0,10}> 5"`
  that looked for the literal substring `> 5` in colprof's log — which
  colprof never emits, so the warning was unreachable. Removed the dead
  tuple. Real ΔE evaluation already lives in Tab 5 (Check & Refine) via
  `profcheck`. The other two sanity checks (`out of gamut`,
  `Profile creation failed`) and the file-size checks are unchanged.

## v3.2.3
### Fixed
- **Gamut Analysis failed when comparison profile was loaded from
  `/System/Library/ColorSync/Profiles/`** (e.g. `sRGB Profile.icc`):
  ChromIQ copies the comparison ICC into a private temp directory before
  invoking `iccgamut`, and was using `shutil.copy2`, which copies file data
  *and* metadata. macOS system ColorSync profiles carry the SIP-protected
  BSD flag `SF_RESTRICTED` — the data copy succeeded but `copystat` failed
  with `[Errno 1] Operation not permitted` when re-applying the flag to the
  destination, surfacing as "Gamut Analysis Failed — Cannot copy ICC file".
  User-installed profiles under `~/Library/ColorSync/Profiles/` lacked the
  flag and were unaffected. ChromIQ now uses `shutil.copyfile`, which copies
  only the file bytes and skips metadata. Reported by @soul-traveller in #12.

### Changed
- Installation instructions now document the
  `xattr -dr com.apple.quarantine /Applications/ChromIQ.app` workaround for
  macOS Sonoma+ where Gatekeeper refuses to launch the ad-hoc-signed bundle.
  Bundled into the README and the auto-generated release notes for future
  builds.

### Project
- Added GitHub issue templates (`bug_report.yml`, `feature_request.yml`) and
  the supporting `platform:` / `Severity:` labels, so reports can be
  categorised consistently. Thanks to @soul-traveller for the suggestion.

## v3.2.2
### Fixed
- **Intermittent crash on app quit (`EXC_BAD_ACCESS` in `CrBrowserMain`)**:
  macOS occasionally reported "Python quit unexpectedly" after closing the
  app. The crash originated in `dealloc_QApplication` → `sip_api_visit_wrappers`
  — SIP was walking its wrapper graph during `QApplication` teardown and
  following a dangling pointer inside the `QWebEngineView` / Chromium subtree
  on the gamut viewer panel. The previous `aboutToQuit` handler loaded
  `about:blank` and slept 200 ms but never actually destroyed the view, so
  its Chromium child objects survived into `QApplication`'s destructor where
  the race fires. ChromIQ now also disconnects `loadFinished`, reparents the
  `QWebEnginePage` and the view to `None`, calls `deleteLater()` on both,
  and pumps the event loop so the deferred deletes run *before* the
  `QApplication` destructor.

## v3.2.1
### Fixed
- **Check/Refine — 3D gamut viewer flashed white on first open**: When the
  user opened the Check/Refine tab for the first time after launching the app,
  the embedded QWebEngineView briefly painted its default white surface before
  the dark `#111111` placeholder HTML rendered on top. The widget-level
  stylesheet only styled the QWidget chrome, not the Chromium-rendered page
  surface. `QWebEnginePage.setBackgroundColor` is now set to `#111111`
  immediately after constructing the view, so Chromium paints its very first
  compositor frame dark — no flash on first show.

## v3.2.0
### Added
- **macOS native print dialog — Adobe Color Printer Utility behaviour**: When "Use default
  macOS printer dialog" is enabled, ChromIQ now opens the real macOS print panel via PyObjC
  and sends the chart as untagged device RGB at its exact generated size. The print job is put
  into application-managed-colour mode (`AP_ColorMatchingMode` locked via PrintCore), and the
  selected driver's own "No Color Adjustment" / "Application Managed" option is auto-detected
  from its PPD and locked too — so the driver's colour controls appear greyed out and cannot be
  re-enabled, exactly like ACPU. No colour transform is applied; pixel values reach the printer
  unchanged.
- **Native macOS print — colour-management lock verification**: After every print, ChromIQ now
  reads the resolved colour-management keys back from the submitted job and confirms each one
  matches the values it locked (`AP_ColorMatchingMode = AP_ApplicationColorMatching`,
  `APCustomColorMatchingProfile = sRGB`, plus any vendor-PPD "no colour adjustment" key
  detected). On success, the result is recorded in `~/Library/Logs/ChromIQ/chromiq.log` as
  *"colour management verified OFF"*; on mismatch, a warning dialog tells the user the job was
  sent but the lock couldn't be verified, so they can check the swatch or switch print modes.
  The macOS print-mode warning text also explains that the system's "Color Matching" pane is
  cosmetic (macOS doesn't let third-party apps grey it out — Adobe Color Printer Utility has
  the same limitation), and that ChromIQ overrides it at the job level regardless of what the
  pane visibly shows.
- **Preflight confirmation dialog**: Before sending a job to CUPS, ChromIQ can show a summary of
  every option that will be sent (printer, paper size, media type, quality, tray, borderless,
  auto-detected orientation, forced-off duplex/colour management, and any detected mismatches).
  Toggleable in Settings → "Confirm print settings before sending to printer" (on by default).
- **Automatic page orientation**: ChromIQ now compares the chart's aspect ratio with the
  selected paper and requests portrait or landscape so the chart matches the media.
- **Page-size mismatch warning**: If the selected paper size doesn't match the size the chart
  was generated for, the preflight dialog flags it before you waste paper and ink.

### Changed
- **PostScript output**: The generated PostScript now uses the selected media's exact PageSize
  and centres the chart on it (instead of forcing the page to the TIFF's own dimensions), so the
  PS document and `lp -o PageSize=…` agree.
- **Print options order**: The "Borderless" option now appears directly after "Paper size" in
  the Print tab (was last), which reads more naturally.
- **Paper-mismatch check**: Now compares the chart against the printer's *printable area*
  (from the PPD's `*ImageableArea`) when available — instead of the full sheet — so the normal
  loss of the printer's hardware margins no longer trips the warning. Falls back to comparing
  against the full sheet with a wider tolerance when no printable-area data is available, and
  the warning is reworded to "possible paper mismatch".

### Fixed
- **Bogus "page-size mismatch" warning**: ArgyllCMS `printtarg` writes the chart TIFF's
  resolution in pixels-per-centimetre, which ChromIQ was reading as DPI directly — so an A4
  chart was reported as 533 × 754 mm and the preflight dialog showed a false mismatch warning
  (and the generated PostScript could be mis-sized). `_read_dpi` now honours the TIFF's
  ResolutionUnit tag.
- **Print tab — TIFF preview "shrunk" after chart generation**: When jumping straight from
  Create Chart to Print Chart, the preview sometimes rendered with a dark border around it
  (pixmap scaled too small). The preview's `showEvent` repainted synchronously, before Qt
  had activated the now-visible tab's layout, so the label still reported its hidden minimum
  size. Switching tabs and back happened to work because the second show landed after layout
  was already settled. The repaint is now deferred until layout activation completes, so the
  first show always uses the true label size.

## v3.1.4
### Fixed
- **Gamut viewer — empty profile error dialog**: When an ICC profile file is 0 bytes
  (e.g. from an interrupted colprof run), a clear popup now explains why the file is
  empty and how to rebuild it, instead of showing a cryptic "iccgamut exited with code 1"
  warning in the console.
- **Gamut viewer — iccgamut error dialog**: Any other iccgamut failure now shows a popup
  with the actual tool error message, common causes (corrupt or non-standard ICC file),
  and a pointer to the full log for further diagnosis.

## v3.1.3
### Added
- **Gamut viewer — 3D comparison overlay**: Profile A now keeps its natural per-vertex
  colours in combined view (instead of flat red). Profile B is rendered semi-transparent
  so both gamuts are visible simultaneously.
- **Gamut viewer — Opacity & Saturation sliders**: Live controls for Profile B's
  transparency and colour saturation in combined view. Values are saved as defaults.
- **Build Profile — FWA error dialog**: When colprof reports that the instrument does
  not support FWA compensation (ColorMunki, i1Studio, CC Studio), a clear popup
  explains why and what to do instead.
- **Build Profile — expanded tooltips**: All option tooltips across the manual, guided,
  printcal, and applycal modules now contain full explanations of what each option does
  and when to change it. Dialog widths increased where needed.

### Fixed
- **Gamut viewer — app close crash**: Closing the app while the 3D viewer was active
  caused a SIGBUS / bus error on macOS (Chromium GPU shared-memory race). Fixed by
  spinning a 200 ms nested event loop after navigating to about:blank on quit, giving
  the GPU subprocess time to release framebuffers cleanly.
- **Measure tab — instrument port spinbox**: Applied compact styling to match other
  inputs in the manual module.

## v3.1.2
### Fixed
- **Build Profile — Gamut Mapping path input**: The file-selection field in Build Profile → MANUAL → Gamut Mapping was collapsing to a ~2 px sliver. A new `compact_path` CSS rule (`min-height: 22px`) gives it a stable 22 px compact height matching the rest of the group.
- **Measure tab — Patch consistency tolerance spinbox**: Removed compact (22 px) styling from this control in the guided module; it now renders at standard input height.
- **Gamut viewer — Profiles section compact styling**: Profile and Compare path fields now use compact 22 px height; browse and clear buttons match. Vertical row spacing increased to 8 px and horizontal button spacing set to 4 px for a more consistent look.

## v3.1.1
### Added
- **Gamut viewer — app theme colours**: A new "Use app theme colours for 3D gamut viewer" toggle in Preferences → Behaviour (default: on) remaps the 3D model's vertex colours to ChromIQ's five spectrum accents (Magenta, Amber, Green, Cyan, Violet), preserving original lightness so the 3D shape reads clearly. The Lab axes (+a*, −a*, +b*, −b*) are mapped to the same palette; the grey L* axis and white/black-point spheres are left unchanged. Themed mode is pure client-side JavaScript — the original ArgyllCMS file is never modified.
- **Gamut viewer — improved tooltips**: All iccgamut option controls now have detailed ⓘ info dialogs with plain-English explanations and practical guidance. New tooltips added for the Show Axes, Mark Cusp Points, and Show Edge Plot checkboxes. Dialog widths enlarged for comfortable reading.

### Fixed
- **Windows ARM64 — 3D gamut viewer**: The embedded Chromium browser (QWebEngineView) now works on Qualcomm ARM64 hardware. The Chromium GPU blocklist prevented WebGL from initialising, showing a black screen or "Your browser does not support X3DOM" error. Applying `--ignore-gpu-blocklist --disable-gpu-compositing` at startup enables WebGL while routing all compositing through the software path, fixing the viewer on both ARM64 and x64 Windows.

## v3.1.0
### Added
- **Gamut Volume panel (Check & Refine tab)**: New right-side panel powered by ArgyllCMS `iccgamut` and `viewgam`. Displays the gamut volume of the active ICC profile as a number and as an interactive 3D mesh rendered in-app via QWebEngineView + X3DOM. Options: rendering intent, colour space (Lab / CIECAM02 Jab), surface resolution, mapping direction (forward / backward), axes, cusp markers, and edge plot.
- **Gamut comparison**: Load a second ICC/ICM profile to compare against the primary. ChromIQ computes both volumes, the delta %, the intersection volume, and bidirectional coverage percentages (A covered by B / B covered by A) using `viewgam`. A [PROFILE A] / [COMBINED] / [PROFILE B] toggle switches the 3D viewer between the three views.
- **Compare browse — smart starting location**: The comparison file dialog opens at ArgyllCMS's `ref/` folder (if installed) and shows sidebar shortcuts to the system ICC/ICM profile directories (`~/Library/ColorSync/Profiles`, `/Library/ColorSync/Profiles` on macOS; `System32\spool\drivers\color` on Windows).
- **Reset View button**: Resets the X3DOM camera to the default position via `x3d.runtime.resetView()`.

### Changed
- Default gamut surface resolution raised to **20** for noticeably smoother meshes out of the box.
- 3D viewer background colour now matches the TIFF preview dark-grey (`#111111`).

## v3.0.2
### Fixed
- **Load Chart dialog — button order on macOS**: Buttons now appear in the same left-to-right order as on Windows (Continue / Use as base for a new profile / Cancel) instead of being reordered by macOS HIG. Applies to all dialogs throughout the app.
- **Load Chart dialog — print-specific description text**: The "Continue" option no longer says "Continue printing…". Text is now neutral and accurate regardless of which tab triggered the dialog.
- **Load Chart dialog — Cancel now restores previous state**: Clicking Cancel fully undoes the load and restores whatever files were loaded before. Previously, files were partially loaded into several tabs before the dialog appeared, making Cancel ineffective.
- **"Use as base for a new profile" — copies all file types**: `.ti3` and `.icc`/`.icm` files are now copied to the new subfolder alongside `.ti2`, `.ti1`, and TIFF files. All tabs (Build Profile, Check & Refine, Measure, Print Chart) update to the new location after the copy.
- **"Use as base for a new profile" — file list in dialog**: The confirmation dialog now lists all file types that will be copied, including `.ti3` and `.icc`/`.icm` if present.
- **Load Chart dialog — text input focus**: The profile name field now reliably receives keyboard focus when the dialog opens, without requiring a click outside and back in to activate it.

## v3.0.1
### Fixed
- Mode buttons (GUIDED/MANUAL, calibration) now render at the correct font size on macOS; the Windows compatibility commit had introduced `setPixelSize(11)` + `font-size: 11px` CSS which made them noticeably smaller than action buttons

## v3.0.0
### Added
- **Windows support (x64 + ARM64)**: ChromIQ now ships a native Windows build alongside macOS. ArgyllCMS binary resolution appends `.exe` on Windows and auto-detects `Program Files\ArgyllCMS\bin` and `%LOCALAPPDATA%\ArgyllCMS\bin`. ICC profiles install to `%WINDIR%\System32\spool\drivers\color\`. Log files go to `%LOCALAPPDATA%\ChromIQ\Logs\`. Settings dialog shows Windows-specific download links and architecture guidance. CUPS is platform-guarded; the native Qt print dialog is the Windows print path. All platform-specific UI text adapts to the OS.
- **Windows — WinUSB driver installer**: New "Install USB Driver…" button in Settings → ArgyllCMS. ChromIQ detects connected colorimeters via the Windows registry and installs the WinUSB driver silently using `wdi-simple` (built from libwdi source in CI, elevated via UAC). If installation fails or is cancelled, a "Try Zadig" button opens the bundled Zadig GUI for guided installation. No test-signing mode, no command line, no restart required.
- **Build Profile — ICC media attributes and default intent**: Six new controls for `colprof -Z` flags in both Guided and Manual modes (and the calibration workflow's Build Profile module): Media Surface (Glossy / Matte), Color Type (Color / B&W), Media Type (Reflective / Transparent), Media Polarity (Positive / Negative), and Default Rendering Intent (Perceptual / Relative / Saturation / Absolute). All default to ArgyllCMS defaults so no `-Z` flag is emitted unless explicitly changed. Persisted via Save Defaults and user presets.

### Fixed
- **Windows — Calibration / all interactive prompts unresponsive**: Replaced pywinpty (unreliable in frozen PyInstaller apps) with a Windows-native approach: chartread starts with `CREATE_NEW_CONSOLE + SW_HIDE` so it gets a real but invisible console. Keystrokes are injected via `AttachConsole(pid)` + `WriteConsoleInputW`, writing directly into the same input buffer that `_getch()` reads — identical to a physical keypress. Works on both x64 and ARM64.
- **Windows — "Profile file was not created" false error**: `colprof` on Windows produces `.icm` files, not `.icc`. `expected_icc_path()` now probes for the actual file (`.icc` first, then `.icm`) so the post-build existence check no longer fails on Windows.
- **Windows — All UI text ~33 % larger than on macOS**: `1 pt = 1 px` at macOS's 72 DPI but `≈ 1.33 px` at Windows' 96 DPI. Every `font-size: Xpt` stylesheet string and every `setPointSize()` / `setPointSizeF()` call across the entire UI has been converted to `px` / `setPixelSize()`. Affected widgets: tab step labels, tab titles, guided-panel headlines, patch count, CHART/PRINT PREVIEW labels, spectrum progress bar, scan row badge, masthead wordmark, and tab bar labels.
- **Windows — Mode button text size and bold**: Mode buttons (GUIDED / MANUAL / calibration workflow buttons) now have an explicit `font-size: 11px` stylesheet rule, overriding the inherited 13 px from the global `QWidget` rule and matching the intended `setPixelSize(11)`. The active (checked) state also has `font-weight: 700` explicitly set, restoring bold which was inadvertently dropped in a beta patch.
- **Windows — Colorimeter detection**: `KNOWN_COLORIMETERS` dict keys are now consistently lowercase (fixing Datacolor Spyder and Colorvision devices); composite USB devices deduplicated by `(vid, pid)`; `libusb0` driver accepted alongside `winusb` so devices with the Argyll driver no longer appear as needing installation. Added X-Rite i1 Studio Argyll-driver entry (VID=0765 / PID=6008).
- **Windows — VM instrument conflict**: When a colorimeter is assigned to a Windows VM (Parallels, VMware, VirtualBox) and measurement is attempted on the macOS host, ChromIQ now shows a clear "Instrument Not Accessible" popup explaining the conflict and steps to resolve it.
- **Windows — Console flash**: `_test_argyll()` and the `taskkill` pre-measurement subprocess both pass `CREATE_NO_WINDOW`, eliminating brief console flashes on Windows.
- **Windows — Measure false success from stale .ti3**: `_on_measure_done()` compares the `.ti3` mtime to a snapshot taken at measurement start; a leftover file from a prior session no longer registers as a successful new measurement.
- **Windows — Device-not-found error undetected**: `_NO_INSTRUMENT_RE` now also matches `"No suitable instruments found"` and `"No instruments connected to use!"`, which are the strings Argyll prints on Windows when the USB driver is missing or the device is inaccessible.
- **Settings — macOS-only options hidden on Windows**: The "Use default macOS printer dialog" checkbox and tooltip are hidden when running on Windows.
- **Settings — Windows layout**: "Install USB Driver…" appears on the same row as Test Binaries, Auto-detect, and Download Latest Argyll, matching the macOS layout.
- **Create Chart — "Good Distribution" label**: Shortened from "(recommended)" to "(recomm.)" so the label fits within its column on Windows.

## v3.0.0-beta.10
### Added
- **Build Profile — colprof `-Z` media attributes and default intent**: Two new controls appear in the **Color Science** section of the guided Build Profile panel, and five controls appear in the manual mode panel. In both modes the same controls are also available in the Calibration tab's Build Profile module.
  - **Media Surface** (guided + manual): Glossy / Reflective (default) or Matte (`-Z m`). Embeds the surface type in the ICC profile header so colour management systems can automatically select the correct profile when both a matte and glossy profile are installed.
  - **Color Type** (guided + manual): Color media (default) or Black & White (`-Z b`). Marks the profile for monochrome inksets or pure-greyscale print modes.
  - **Media Type** (manual only): Reflective (default) or Transparent (`-Z t`). For transparency inksets and slide-film workflows.
  - **Media Polarity** (manual only): Positive (default) or Negative (`-Z n`). For photographic film negative workflows.
  - **Default Rendering Intent** (manual only): Not set / Perceptual / Relative Colorimetric / Saturation / Absolute Colorimetric (`-Z p/r/s/a`). Marks which rendering intent the ICC profile header advertises as its default, used by CMSes that respect this field.
  - All selections default to the ArgyllCMS defaults so no `-Z` flag is emitted unless the user explicitly changes a value.
  - Settings are persisted via "Save as defaults" (guided and manual) and user presets (manual).

## v3.0.0-beta.9
### Fixed
- **Windows — All UI text ~33% larger than on macOS**: Qt stylesheet `pt` units are DPI-dependent — 1 pt = 1 px at 72 DPI (macOS) but ≈ 1.33 px at 96 DPI (Windows). Every inline `font-size: Xpt` string and every `setPointSize()`/`setPointSizeF()` call across the entire UI has been converted to `px`/`setPixelSize()`. Affected widgets: tab step labels, tab titles, guided-panel headlines and flavour text (all tabs), patch count number, CHART/PRINT PREVIEW labels, spectrum progress bar, scan row badge, and the masthead wordmark.
- **Windows — Tab bar text too large**: `SpectrumTabBar` used `setPointSize(13)` for tab labels; converted to `setPixelSize(13)` for consistent size across platforms.
- **Settings — macOS "Use native printer dialog" checkbox misaligned when hidden on Windows**: The row containing this macOS-only option had extra margins that shifted surrounding controls when the checkbox was invisible. Fixed layout margins; dialog minimum width increased to 840 px on both platforms so button labels are never clipped.
- **Settings — "Install USB Driver…" button below other ArgyllCMS buttons on Windows**: The button now appears on the same row as Test Binaries, Auto-detect, and Download Latest Argyll, consistent with the macOS layout.
- **Measure — No explanation when measurement device is connected to a virtual machine**: When a colorimeter is assigned to a Windows VM (Parallels, VMware, VirtualBox, etc.) and measurement is started on the macOS host, ArgyllCMS prints `"Failed to get piif for USB device"` and exits immediately. ChromIQ now detects this string and shows a clear popup — "Instrument Not Accessible" — explaining the VM conflict and the steps to resolve it (disconnect device from VM, reconnect, retry).

## v3.0.0-beta.8
### Fixed
- **Windows ARM64 — Interactive prompts still unresponsive (beta.7 regression on ARM64)**: On ARM64 Windows, pywinpty's native DLL is x64-only and fails to load (`DLL load failed: module not found`), setting `_WINPTY_AVAILABLE = False`. The `_run_pty()` guard then bypassed `_run_winpty()` entirely and fell back to the old pipe path — defeating the beta.7 `CREATE_NEW_CONSOLE + WriteConsoleInputW` fix on the very platform it was needed most. Fixed by removing the `_WINPTY_AVAILABLE` conditional: `_run_winpty()` has no pywinpty dependency since beta.7 and is now called unconditionally on Windows. Confirmed on ARM64 VM: `_win_inject_key: ch='\r' ok=True written=2` → `Calibration complete`.
- **Windows — X-Rite i1 Studio (Argyll driver) not detected by USB driver dialog**: The i1 Studio registers as VID=0765 PID=6008 when using the Argyll `libusb0` driver, but the app only knew PID `d0c0` (native HID). Added `("0765", "6008"): "X-Rite i1 Studio (Argyll)"` to `KNOWN_COLORIMETERS`.
- **Windows — Devices with Argyll `libusb0` driver shown as needing installation**: `enumerate_connected()` checked only for `winusb` service, so devices with the Argyll `libusb0` driver appeared as uninstalled even though ArgyllCMS can use them. Extended the check to accept both `winusb` and `libusb0`.
### Removed
- `pywinpty` dependency removed from `requirements.txt` — unused since beta.7 and broken on ARM64 Windows.

## v3.0.0-beta.7
### Fixed
- **Windows — Calibration / all interactive prompts still unresponsive**: Pywinpty proved unreliable across four beta releases in a frozen PyInstaller app — WinPTY backend cannot locate `winpty-agent.exe` inside `_MEIPASS`, and ConPTY's `write()` never reliably reaches MSVCRT's `_getch()`. Replaced pywinpty entirely with the Windows-native approach: chartread now starts with `CREATE_NEW_CONSOLE + SW_HIDE` so it gets a real but invisible console (which `_getch()` opens via `\\.\CONIN$` directly). Keystrokes are injected via `AttachConsole(pid)` + `WriteConsoleInputW`, writing events directly into the same input buffer that `_getch()` reads from — identical to a physical keypress. Applies to calibration, strip selection, guided navigation, Esc-to-abort, and all other interactive chartread prompts.

## v3.0.0-beta.6
### Fixed
- **Windows — Calibration keypress (and all interactive prompts) still unresponsive**: Root cause identified: pywinpty's ConPTY backend emits a spurious `EOFError` on its output pipe whenever the child process blocks on `_getch()` waiting for input. The reader thread caught this as a true end-of-process, set `_winpty_proc = None`, and the subsequent `write_stdin("\r")` from the "Start Calibration" button silently fell through to no-op. Two fixes: (1) `_run_winpty()` now requests the **WinPTY backend** explicitly (`Backend.WinPTY`), which injects keystrokes via `WriteConsoleInput` and does not have the spurious-EOF problem; falls back to ConPTY if WinPTY is unavailable. (2) `_inner()` reader thread now checks `proc.isalive` before treating `EOFError` as terminal — if the process is still running it sleeps 50 ms and retries, preventing premature teardown. Both fixes apply equally to calibration, strip selection, guided navigation, and all other interactive chartread prompts.

## v3.0.0-beta.5
### Fixed
- **Windows — "No colorimeter detected" for Datacolor Spyder and Colorvision devices**: `KNOWN_COLORIMETERS` used mixed-case VID keys (`"085C"`, `"04DB"`) but the registry lookup normalises to lowercase, so `"085c" != "085C"` and all Datacolor Spyder and Colorvision Spyder 1 devices were silently skipped. All dict keys are now consistently lowercase. X-Rite devices (VID `0765`, all digits) were unaffected.
- **Windows — Composite USB devices listed multiple times**: Composite devices register a parent key plus one key per interface (`VID&PID&MI_00`, `VID&PID&MI_01`…). `enumerate_connected()` now deduplicates by `(vid, pid)` so each device appears once in the installer dialog.

## v3.0.0-beta.4
### Fixed
- **Windows — Calibration keypress still unresponsive (beta.3 regression)**: Two bugs prevented pywinpty from activating in the bundled app. (1) `ChromIQWin.spec` listed `'winpty'` only in `hiddenimports`, which omits the compiled `.pyd` extension's native binaries — PyInstaller now collects winpty via `collect_all('winpty')`. (2) `_winpty_reader` called `proc.read(4096, timeout=…)` but pywinpty ≥ 2.0 `read()` has no `timeout` parameter, raising `TypeError` on the first call and immediately killing the reader thread. The reader is rewritten with an inner thread + `queue.Queue` to replicate the 150 ms silence-window flush without using the unsupported parameter.

## v3.0.0-beta.3
### Fixed
- **Windows — Calibration prompt unresponsive**: chartread's interactive calibration keypress now works correctly on Windows. The previous subprocess-pipe approach couldn't deliver a real console to chartread's `_getch()` call; replaced with a pywinpty ConPTY pseudo-terminal so the device calibration sequence completes as expected.
- **Settings — Console flash when testing Argyll binaries**: The `_test_argyll()` check now passes `CREATE_NO_WINDOW` to the subprocess, eliminating the brief console window that flashed on Windows when opening the Preferences dialog.
- **Windows — In-app WinUSB driver installer**: New "Install USB Driver…" button in Settings → ArgyllCMS. ChromIQ detects connected colorimeters via the Windows registry, then installs the WinUSB driver silently using wdi-simple (built from libwdi source in CI, elevated via UAC). If automatic installation fails or is cancelled, a fallback "Try Zadig" button opens the bundled Zadig GUI for guided installation. No test-signing mode, no command line, no restart required.

## v3.0.0-beta.2
### Fixed
- **Settings — Hide macOS printer dialog option on Windows**: The "Use default macOS printer dialog" checkbox and its tooltip are now invisible when running on Windows, where the option has no effect.
- **Windows — Mode button text clipped when active**: Mode buttons (GUIDED / MANUAL / calibration buttons) were sized using Medium-weight font metrics but rendered bold when checked (via CSS `font-weight: 700`), causing text to overflow on Windows where font substitution metrics differ. Buttons now compute their size hint from the bold font, with CSS explicitly resetting to normal weight for the unchecked state.
- **Windows — Font rendering consistency**: `ButtonFontFilter` and the `SpectrumTabBar` now specify an explicit font-family fallback chain (`Menlo → Consolas → Courier New → monospace` for buttons; `Inter → Segoe UI → system-ui` for tab labels) so Windows substitution is deterministic rather than OS-default.
- **Measure — Console window flash on Windows**: The `taskkill` subprocess used to kill any pre-existing `chartread.exe` before measurement now passes `creationflags=CREATE_NO_WINDOW`, eliminating the brief console window that appeared on Windows when starting measurement.
- **Measure — False "Measurement complete" from stale .ti3**: `_on_measure_done()` now checks whether the `.ti3` file was created or modified *during the current run* (by comparing its mtime to a snapshot taken at measurement start). A leftover `.ti3` from a previous session no longer causes a failed measurement to be reported as successful.
- **Measure — Device-not-found error undetected on Windows**: `_NO_INSTRUMENT_RE` now also matches `"No suitable instruments found"` and `"No instruments connected to use!"`, which are the strings Argyll outputs on Windows when the USB driver is missing or the device is inaccessible.
- **Measure — "No Instrument Found" dialog text**: The dialog now says "Windows PC" instead of "Mac" on Windows, and adds a hint to install the Argyll WinUSB driver via the ArgyllInstallers tool or Zadig.

## v3.0.0-beta.1
### Added
- **Windows beta support**: Initial Windows compatibility layer. All macOS behaviour is completely unchanged — every adaptation is behind a `sys.platform` guard. Changes include:
  - ArgyllCMS binary resolution appends `.exe` on Windows; auto-detection scans `Program Files\ArgyllCMS\bin` and `%LOCALAPPDATA%\ArgyllCMS\bin`
  - Interactive ArgyllCMS tools (chartread) use subprocess pipes instead of a PTY on Windows, with the same 150 ms silence-window flush logic so prompts remain visible
  - CUPS subsystem (`cups` module, `lp`, `lpoptions`) is platform-guarded; on Windows the native Qt print dialog is the default and only print path
  - ICC profiles install to `%WINDIR%\System32\spool\drivers\color\` on Windows with a clear error if elevation is required
  - Log files written to `%LOCALAPPDATA%\ChromIQ\Logs\` on Windows
  - Settings dialog links to the Windows ArgyllCMS download page with Windows-specific architecture guidance
  - Print tab warning text adapts to the OS name
  - File dialog `/Applications` sidebar shortcut is macOS-only

## v2.11.0
### Added
- **Print Chart — Native macOS printer dialog**: New option in Preferences → Behaviour: "Use default macOS printer dialog". When enabled, the printer selection and CUPS print options are hidden; clicking Print Current Page or Print All Pages opens the standard macOS print sheet instead of ChromIQ's built-in PostScript / CUPS pipeline. The info box updates to remind the user to disable colour management manually in the driver panel, with per-brand instructions for Epson, Canon, HP, and other manufacturers. The same instructions appear in the Preferences tooltip. Defaults to off — existing behaviour is unchanged unless the option is explicitly enabled.

## v2.10.3
### Fixed
- **Print — Stuck PostScript job on TIFF fallback**: When a printer rejects PostScript and the app retries with a TIFF, the original PS job is now cancelled from the CUPS queue before the TIFF is submitted, preventing it from lingering as a stuck job.
- **Create Chart — Pre-conditioning profile staged to working folder**: The `-c` pre-conditioning ICC/ICM profile is now copied into the session working folder (`~/ChromIQ/<name>/`) with a `pre_` prefix at chart-generation time. The working-folder copy is what targen receives, keeping all session files together. The file is preserved across normal profiling runs but is deleted when generating a calibration target (full fresh-start wipe).

## v2.10.2
### Fixed
- **All tabs — Stale file state after new measurement cycle**: Loading a new `.ti2` file in Print Chart or Measure now clears any previously loaded `.ti3` in Build Profile and any loaded `.ti3`/`.icc` in Check & Refine. Creating a new chart already had this behaviour; Print Chart and Measure now match.
- **Build Profile — Profile description not updated on reload**: Loading a second `.ti3` file now always overwrites the profile description field in both Guided and Manual modules (previously only filled it when the field was empty).
- **Build Profile — Loaded `.ti3` clears Check & Refine**: Manually loading a `.ti3` in Build Profile now resets the Check & Refine tab, preventing stale results from a previous profile run being checked against a new measurement.
- **Measure — Completion clears Check & Refine**: When measurement finishes and the resulting `.ti3` is sent to Build Profile, any previously loaded files in Check & Refine are cleared.

## v2.10.1
### Changed
- **All tabs — Tooltip improvements**: Tooltip dialogs now auto-size correctly to fit their content. All Measure tab tooltips have been expanded with practical guidance on when and why to use each option. The Presets tooltip is consistent across all four tabs and uses a structured bullet layout.

## v2.10.0
### Added
- **Create Chart — Cascading colorant slots (-D)**: The "Add/Remove Colorant" expert option in Manual mode now supports up to 11 stacked `-D` modifications. Enabling one slot reveals the next; disabling a slot collapses all subsequent ones. Values and enabled states are saved and restored through presets and Save Defaults. Allows configuring extended-gamut printers (e.g. CMYK + Orange + Green + Light Cyan) without using the command line.

### Fixed
- **TIFF preview — High channel-count fallback**: The no-sidecar channel layout fallback table now covers 9, 10, and 11-channel TIFFs. Previously anything above 8 channels fell back to an all-black heuristic.
- **Create Chart — Working folder cleanup**: `.json` and `.cal` files are now included in both the calibration-target and normal-profiling cleanup passes. In normal mode `cal_*`-prefixed files are preserved; in calibration-target mode all matching files are wiped.

## v2.9.4
### Fixed
- **Create Chart — Calibration target cleanup**: Generating a calibration target now also removes stale `.channels.json` sidecar files from the working folder (previously only `ti1/ti2/tif/cht/ps` extensions were wiped, leaving the old JSON behind).

## v2.9.3
### Changed
- **Create Chart — Calibration target pre-fill**: Enabling "Create target for calibration" now immediately writes the calibration-appropriate parameter values (patches = 0, white/black patches = 0, single-channel steps = 20, good distribution off, randomisation off) directly into the visible parameter widgets, so the user can review and adjust them before clicking Generate. Unchecking the option restores the previous widget values.

## v2.9.2
### Changed
- **Create Chart — Compact parameter inputs**: Comboboxes, spinboxes, line-edit fields, and browse buttons in the targen and printtarg parameter sections (Basic and Expert Options) now use the same reduced height as the Measure tab's additional options, keeping the panel more compact.

## v2.9.1
### Fixed
- **Create Chart — Calibration file auto-fill**: Removed erroneous `set_user_enabled(False)` calls that were unchecking the `-K` and `-I` enable-checkboxes on every auto-fill. The path is now pre-filled into both fields without touching the checkbox state — the user chooses which option to enable.

## v2.9.0
### Added
- **Create Calibration File — Channel target overrides**: Per-channel initial target controls for C/M/Y/K and extended inkset channels (Ch4–Ch7). Each channel can override the maximum device %, development target %, white-point minimum ΔE, and 50 % tone target that `printcal` computes automatically. Extended channels are hidden behind a disclosure checkbox and persist across sessions.
- **Create Calibration File — Calibration Metadata**: New section for embedding a description, manufacturer, model, and copyright string in the `.cal` file header (flags `-D`, `-A`, `-M`, `-C`). Description is auto-suggested from the loaded `.ti3` filename.
- **Create Calibration File — Imitation target mode**: New "Imitation target" mode (`-I`) creates a null-calibration `.cal` from an existing `.ti3` — useful for deriving a calibration target when no previous `.cal` exists. Target override controls are shared with Initial calibration mode.
- **Create Calibration File — Dry run**: New "Dry run" checkbox (`-d`) simulates the full calibration calculation without writing any files, so settings can be verified before committing.
- **Create Calibration File — Scrollable UI**: The module now scrolls vertically, keeping the run button and log pinned outside the scroll area.
- **Create Calibration File — Progress bar**: Spectrum progress bar shown while `printcal` is running.
- **Create Calibration File — Result dialog**: After a successful run a rich dialog explains the `-K` / `-I` printtarg flags and offers a "Go to Create Chart →" button that navigates directly to the Create Chart tab with the `.cal` path already filled in.
- **Apply Calibration — Progress bar**: Spectrum progress bar shown while `applycal` is running.
- **Apply Calibration — Result dialog**: After a successful `apply` run a dialog offers "Install on this Mac" to immediately register the calibrated profile with macOS ColorSync.
- **Build Profile — Apply Calibration option**: When calibration mode is enabled, the "Profile Built" result dialog gains an "Apply Calibration →" button that navigates to the Apply Calibration module with the ICC path pre-filled.
- **Measure — Calibration-aware completion dialog**: When all stripes of a `cal_*` target are read (calibration mode enabled), the "All Stripes Read" dialog is replaced by a "Calibration Measurement Complete" variant whose primary button reads "Create Calibration File →" and explains the next step clearly.

### Changed
- **Create Calibration File — Mode tooltip**: Tooltip text updated to include flag names (`-i`, `-r`, `-e`, `-I`) and expanded description for all four modes.
- **Measure — Completion log message**: The "[OK] Measurement complete" log entry now references the correct next tab ("4. Calibration & Profiling" vs "4. Build Profile") depending on whether the measurement is a calibration or profiling run.
- **Create Chart — Calibration file auto-fill**: When a `.cal` file is found in the working folder, its path is pre-filled into both the `-K` and `-I` fields. Neither option is enabled automatically — the user selects which one applies to their workflow.

## v2.8.1
### Fixed
- **Create Chart — Manual module — Layout**: Left panel width reduced to 580 px to match the Print Chart tab. Parameter combo boxes no longer force horizontal scrolling when their option labels are long — the selected value still displays fully, but the minimum control width is decoupled from the longest item text.

## v2.8.0
### Changed
- **Main window — Responsive sizing**: The window now opens at a size that fits the available screen. On large displays (≥ 1440 × 1025) behaviour is unchanged. On smaller screens such as a 13″ MacBook (1280 × 800) the window scales down to fit. A minimum size of 900 × 650 is enforced so the UI remains usable. Geometry saved on a larger display is clamped to the current screen on the next launch.
- **Print Chart — Scrollable options panel**: The print-options group ("No configurable options detected" / printer driver options) and the verification warning are now inside a scroll area. When the window is small they scroll vertically instead of being squeezed together, while the printer selector remains pinned above the scroll area and the action buttons remain pinned below.
- **Print Chart — Button alignment**: The print-action buttons are now flush with the bottom of the panel, consistent with the action buttons in all other tabs.

## v2.7.0
### Added
- **Session Restore**: New "Restore last session on launch" toggle in Preferences → Behaviour (off by default). When enabled, ChromIQ reloads the previously active profiling project on startup: the .ti2 path in Measure, TIFFs in Print Chart and Measure, .ti3 and .icc paths in Build Profile, and both paths in Check & Refine. If any file is missing or was moved it is silently skipped — no errors.

### Changed
- **Print Chart — Printer tooltip and warning label**: Updated to accurately describe the PostScript-first pipeline with automatic TIFF fallback, replacing outdated text that referred only to direct TIFF/CUPS submission.

## v2.6.0
### Added
- **Optional Calibration Workflow**: A full printer calibration workflow (printcal → applycal) is now available behind a toggle in Preferences → Behaviour → "Enable calibration options". Off by default — most users profiling consumer inkjet printers do not need it.
  - When enabled: guided mode panels are hidden across all tabs; tab 4 is renamed "Calibration & Profiling" with matching header text; a three-module selector (Create Calibration File / Build Profile / Apply Calibration) appears.
  - **Create Chart — Calibration target**: A "Create target for calibration" checkbox prefixes all output files with `cal_`, applies calibration-specific parameter overrides (`-s 20`, `-r`, etc.), and performs a full folder clean. When a `cal_<name>.cal` file is found in the working folder, the `-I` and `-K` fields are pre-filled automatically.
  - **Measure — Smart routing**: Finished measurements whose filename starts with `cal_` are automatically routed to the Create Calibration File module instead of Build Profile.
  - **Create Calibration File (printcal)**: Runs Argyll's `printcal` to generate a `.cal` curve file from a calibration measurement. Options: mode (initial / recalibrate / verify), previous `.cal` for recalibration, smoothing, verbosity. On success, the `.cal` path is handed directly to the Apply Calibration module.
  - **Apply Calibration (applycal)**: Runs Argyll's `applycal` to bake, remove, or check calibration curves on an ICC profile. Auto-fills the `.cal` field from printcal output and the input ICC field from Build Profile output. Leaving the output field blank saves as `cal_<name>.icc`.
  - **Build Profile**: ICC path handed to Apply Calibration automatically on success.
  - All new options support Save as Defaults and restore correctly on relaunch.

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
