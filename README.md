# ChromIQ

**ChromIQ** is a free, open-source desktop application for creating custom ICC profiles for inkjet printers using [ArgyllCMS](https://www.argyllcms.com/). It guides you through a five-step workflow — generate a test chart, print it, measure it with a spectrophotometer, build the ICC profile with `colprof`, then verify and refine with `profcheck` — all without touching the command line. An optional `printcal → applycal → colprof` calibration mode is available from Preferences for users who want full per-channel ink calibration before profiling.

What sets ChromIQ apart:

- **Light / Dark / System (Auto) appearance** that follows your OS theme live.
- **Interactive 3D gamut viewer** with profile-vs-profile comparison (delta %, intersection volume, bidirectional coverage).
- **Print pipeline that bypasses colour management automatically** — PostScript Level 2/3 with TIFF fallback for AirPrint, plus an optional native OS print dialog.
- **RGB, CMYK, and DeviceN multi-channel targets** up to 11 inks (e.g. CMYK + Orange + Green + Light Cyan).

ChromIQ runs on **macOS**, **Windows** (x64 and ARM64), and **Linux** (x86_64 and aarch64, beta).

Supported instruments: X-Rite i1Pro, i1Pro 2, i1Pro 3, i1Pro 3 Plus, ColorMunki, i1Studio, ColorChecker Studio, and SpectroScan.

---

## Download & First Launch

### macOS

1. Go to the [Releases page](https://github.com/itsab1989/ChromIQ/releases/latest) and download **`ChromIQ-macOS-universal.dmg`** (works on both Apple Silicon and Intel).
2. Open the DMG — a Finder window appears.
3. Drag **ChromIQ** into your **Applications** folder.
4. Eject the DMG (⌘E or drag it to the Trash).
5. Open your **Applications** folder, **right-click ChromIQ** and choose **Open** from the menu, then click **Open** in the dialog that appears. This one-time step tells macOS you trust the app.

> **Dialog has no Open button (macOS Sonoma 14+ only)?**
> On Sonoma and later, right-click → Open sometimes shows only a "Done" button with no way to proceed. If that happens, run this one-time command in Terminal:
> ```
> xattr -dr com.apple.quarantine /Applications/ChromIQ.app
> ```
> Then double-click ChromIQ normally — no further steps needed.

6. On first launch, ChromIQ automatically searches for ArgyllCMS. If it isn't found, a setup guide opens — follow the on-screen steps or see [First-time setup](#first-time-setup) below.

---

### Windows

1. Go to the [Releases page](https://github.com/itsab1989/ChromIQ/releases/latest) and download the right build for your PC:
   - **`ChromIQ-Windows-x64.zip`** — 64-bit Intel or AMD (most PCs)
   - **`ChromIQ-Windows-arm64.zip`** — ARM64 (e.g. Snapdragon X laptops)
2. Right-click the ZIP → **Extract All…**, then open the extracted `ChromIQ` folder.
3. Double-click **`ChromIQ.exe`**.

> **Windows SmartScreen says "Windows protected your PC"?**
> This is expected for apps without a paid code-signing certificate. Click **More info**, then **Run anyway**.

4. On first launch, ChromIQ automatically searches for ArgyllCMS in `C:\Program Files\ArgyllCMS\bin` and `%LOCALAPPDATA%\ArgyllCMS\bin`. If it isn't found, a setup guide opens — see [First-time setup](#first-time-setup) below.

---

### Linux (beta)

1. Go to the [Releases page](https://github.com/itsab1989/ChromIQ/releases/latest) and download the right build:
   - **`ChromIQ-Linux-x86_64.tar.gz`** — 64-bit Intel / AMD
   - **`ChromIQ-Linux-aarch64.tar.gz`** — 64-bit ARM (Raspberry Pi 4/5, ARM workstations)
2. Extract the archive:
   ```
   tar xzf ChromIQ-Linux-x86_64.tar.gz
   ```
3. Run ChromIQ:
   ```
   ./ChromIQ/ChromIQ
   ```

> **`qt.qpa.plugin: ... xcb-cursor0 ...` on launch?**
> Install the missing system library:
> ```
> sudo apt install libxcb-cursor0        # Debian / Ubuntu
> sudo dnf install xcb-util-cursor       # Fedora / RHEL
> sudo pacman -S xcb-util-cursor         # Arch
> ```

4. Install ArgyllCMS from your package manager:
   - **Debian / Ubuntu:** `sudo apt install argyll`
   - **Fedora:** `sudo dnf install argyllcms`
   - **Arch:** `sudo pacman -S argyllcms`
   - Or download the latest version from [argyllcms.com](https://www.argyllcms.com/downloadlinux.html)
5. ChromIQ auto-detects ArgyllCMS at `/usr/bin` and common fallback paths. If needed, set the path manually in **Preferences → ArgyllCMS bin path**.

Linux support is currently **beta** — please report what works and what doesn't via [Discussions](https://github.com/itsab1989/ChromIQ/discussions) or the [issue tracker](https://github.com/itsab1989/ChromIQ/issues).

---

## Screenshots

| Step 1a — Create Chart (guided) | Step 1b — Create Chart (manual)  |
|---|---|
|![ChromIQ Guided Test Chart creation](docs/1a.png) | ![ChromIQ Manual Test Chart creation](docs/1b.png) |

| Step 2a — Print Chart (ChromIQ native) | Step 2a — Print Chart (OS native) |
|---|---|
| ![ChromIQ Print Tab ChromIQ native](docs/2a.png) | ![ChromIQ Print Tab OS native](docs/2b.png) |

| Step 3a — Measure Chart (guided) | Step 3b — Measure Chart (manual) |
|---|---|
| ![ChromIQ Measure Chart guided](docs/3a.png) | ![ChromIQ Measure Chart manual](docs/3b.png) |

| Step 4a — Build Profile (guided) | Step 4b — Build Profile (manual) |
|---|---|
| ![ChromIQ Create ICC Profile guided](docs/4a.png) | ![ChromIQ Create ICC Profile manual](docs/4b.png) |

| Step 4c — Calibration & Profiling (disabled by default) | Step 4d — Calibration & Profiling (disabled by default) |
|---|---|
| ![Calibration & Profiling](docs/4c.png) | ![Calibration & Profiling](docs/4d.png) |

| Step 5a — Check & Refine (guided)  | Step 5b — Check & Refine (manual) |
|---|---|
| ![ChromIQ Check & Refine guided](docs/5a.png) | ![ChromIQ Check & Refine manual](docs/5b.png) |

| Settings light mode  | Settings dark mode |
|---|---|
| ![Settings light mode](docs/6a.png) | ![ChromIQ Check & Refine](docs/6b.png) |

---

## Features

### Five-step guided workflow

1. **Create Chart** — `targen` + `printtarg` generate a test chart with the optimal patch count for your instrument/paper combo.
2. **Print Chart** — send the chart to the printer with colour management bypassed automatically.
3. **Measure Chart** — drive your spectrophotometer with `chartread`.
4. **Build Profile** — run `colprof` to write the finished ICC profile.
5. **Check & Refine** — evaluate the profile with `profcheck`, then re-measure only the worst patches and rebuild.

An optional `printcal → applycal → colprof` **calibration mode** (Preferences → Behaviour → *Enable calibration options*) turns Step 4 into a three-module panel — Create Calibration File, Build Profile, Apply Calibration — for users who want per-channel ink linearisation before profiling.

### Guided and Manual modes

- **Guided** picks sensible defaults from an empirical patch-capacity database — just choose instrument, paper, and page count.
- **Manual** exposes every `targen` / `printtarg` / `colprof` flag, with a live command preview.
- Per-tab **Save as Defaults** and named **user presets** (Manual mode) make repeatable workflows easy.

### Instrument and paper support

| Code | Instrument |
|------|-----------|
| `i1` | X-Rite i1Pro / i1Pro 2 / i1Pro 3 |
| `p3` | X-Rite i1Pro 3 Plus |
| `CM` | X-Rite ColorMunki / i1Studio / ColorChecker Studio |
| `SS` | X-Rite SpectroScan (flatbed XY) |

Paper sizes: A2, A3+, A3, A4, Tabloid (11×17), Legal, Letter (each with a landscape variant), photo formats (8×10", 5×7", 4×6"), and fully custom dimensions in mm.

### Printing pipeline

- **PostScript Level 2/3** output with `%cupsJobTicket: cups-disable-cmm` — zero colour transforms between app and printer.
- **Automatic TIFF fallback** for AirPrint / driverless printers that reject PostScript.
- **16-bit TIFF printing** via PostScript Level 3 for printers and RIPs with a true 16-bit pipeline.
- **Optional native OS print dialog** — on macOS it locks `AP_ApplicationColorMatching` via PyObjC; on Windows and Linux per-brand instructions are shown in-app.
- **Print preflight confirmation** with paper-size and orientation checks before each job.

<details>
<summary>More printing details</summary>

- **CMYK and multi-channel (DeviceN) target support** — 4-channel CMYK and 5–17 channel extended-gamut targets (e.g. CMYK + LC LM) print correctly without colour-channel corruption.
- **Cascading colorant slot overrides** (Create Chart — Manual mode) — up to 11 stacked `-D` modifications configure extended-gamut inksets (e.g. CMYK + Orange + Green + Light Cyan) directly in the UI; values and enabled states persist through presets and Save Defaults.
- **Multi-page TIFF support** — Print Current Page and Print All Pages correctly extract and send individual frames from multi-page charts.
- **Printer reachability check** detects offline printers before submitting a job and shows a clear error dialog.
- **Clear Print Queue** button and stuck-job pre-print detection cancel held or aborted jobs before submitting a new one.
- **AirPrint driver detection** in the Print tab — identifies when no configurable options are available and explains how to reinstall the printer with a native PPD driver.
- The native macOS dialog runs a **post-print verification** that confirms the colour-management lock and shows a warning if it couldn't be applied.
- **Automatic page orientation** matches the chart aspect ratio to the selected paper, and a **paper-size mismatch warning** flags discrepancies before you waste ink.

</details>

### Colour science and profiling

- Full `colprof` option set: illuminants (D50, D65, A, C, F5, F8, F10), observers (1931 2°, 1964 10°, 2015 variants), FWA compensation, gamut-mapping intents.
- **CIECAM02 viewing-condition presets** (`-c` / `-d`) for source and destination — required for correct perceptual / saturation tables when a Gamut Source profile is supplied.
- **Pre-conditioning (second-pass) refinement** — pick an existing `.icc` / `.icm` / `.mpp` to drive a `targen -c` second pass; the *Build Profile* and *Check & Refine* dialogs offer one-click **Use as Pre-conditioning** with auto-archiving of v1.
- **ICC media attributes** (`colprof -Z`) — embed Media Surface, Colour Type, Media Type, Polarity, and Default Rendering Intent in the profile header.
- **ClayRGB1998** (Argyll's AdobeRGB 1998 equivalent) ships as the default Gamut Source.

<details>
<summary>More colour-science details</summary>

- **Spectral filter type** in the Measure tab (`-F` flag) — override the measurement condition (M0 / M1 / M2 / M3) for instruments that support it.
- **Colorimetric-gamut combobox** in Manual mode collapses the `-nP` / `-nS` checkboxes into one selector; `-nI` (inverse gamut mapping) stays on its own row.
- **Auto patch count** (Manual mode) — an "Auto" checkbox computes the exact patch count to fill a requested page count at Generate time, running a binary search when needed.
- Separate patch counts for charts **with and without the left clip border** (`-L` flag).
- **Double-density mode** for ColorMunki / i1Studio with measuring rig (`-h` flag).
- **i1Pro margin auto-set to 10 mm** — silently applied for i1Pro / i1Pro 3 Plus to prevent strip-end clipping; never overwrites a value typed by hand in Manual mode.
- **Empirical patch-capacity database** (measured with Argyll 3.5.0) for instant lookup, with binary-search fallback for custom margins.
- **Optional calibration workflow** (`printcal → applycal`) — per-channel initial target overrides (C/M/Y/K, Ch4–Ch7), metadata embedding (`-D`/`-A`/`-M`/`-C`), imitation target mode (`-I`), dry-run (`-d`); `cal_*` measurements are auto-routed to the calibration module.

</details>

### Quality check and 3D gamut viewer

- **`profcheck` integration** in the Check & Refine tab with per-patch ΔE statistics and quality grading.
- **Targeted re-measurement** — patches above the ΔE threshold are highlighted; one click starts a guided re-measurement of just those patches.
- **Interactive 3D gamut viewer** powered by `iccgamut` + `viewgam` + X3DOM — zoomable mesh with volume in ΔE³, Lab / CIECAM02 Jab, cusp markers, edge plot.
- **Profile-vs-profile comparison** with delta %, intersection volume, and bidirectional coverage.
- **Measurement error recovery** — the misread dialog offers Retry / Skip Stripe / **Save Partial & Quit** that arms the resume checkbox for one-click continuation.

### App experience

- **Light / Dark / System (Auto) appearance** — Auto follows the OS theme live (re-skins on the fly on macOS).
- **Per-tab onboarding tooltips** — a ⓘ icon on every tab explains what the screen does, what needs to be ready, and what comes next.
- **Live command preview** in Manual mode mirrors the exact `targen` / `printtarg` lines that will run.
- **Zoomable multi-channel TIFF preview** — RGB, CMYK, and extended-gamut up to 11 inks, ICC-accurate.
- **Session restore** and **automatic session naming** based on printer, paper, media, instrument, and timestamp.
- **Responsive window sizing**, **rotating log file**, and a SemVer-aware **update checker**.

<details>
<summary>More UI details</summary>

- The window scales to fit the available screen on launch (13″ MacBook 1280×800 and larger); minimum size 900×650 enforced; geometry saved on a large display is clamped to the current screen on the next launch; the Print Chart options panel scrolls vertically on small screens.
- **Self-documenting chart TIFFs** — the exact `targen` and `printtarg` commands plus the ChromIQ version are stamped as a rotated text line in the right margin of every generated TIFF; an optional "Chart notes" field rides along on the same stamp.
- Settings persist between sessions via `QSettings`.

</details>

### Cross-platform and setup

- **ArgyllCMS auto-detection** at launch on every platform, with an **Auto-detect** button in Preferences to re-run on demand.
- **Windows WinUSB driver installer** — detects connected colorimeters via the Windows registry and installs the driver silently with UAC elevation; falls back to bundled Zadig GUI if needed.
- ICC profiles install to the standard system location for each OS — see [First-time setup](#first-time-setup).

---

## Requirements

### System
- **macOS:** macOS 13 Ventura or later (Apple Silicon and Intel supported)
- **Windows:** Windows 10 or later (x64 or ARM64)
- **Linux:** glibc-based distributions, x86_64 or aarch64 (beta) — see [Linux (beta)](#linux-beta) above
- [ArgyllCMS 3.5.0](https://www.argyllcms.com/downloaddev.html) — ChromIQ auto-detects ArgyllCMS at launch. On macOS: scans the system PATH, Homebrew, MacPorts, and any versioned Argyll folder in `/Applications`. On Windows: checks `C:\Program Files\ArgyllCMS\bin` and `%LOCALAPPDATA%\ArgyllCMS\bin`. The path can be overridden or re-detected from Preferences on both platforms.

### To run from source
- Python 3.12 or later

### Python dependencies
```
PyQt6 >= 6.11.0
PyQt6-WebEngine >= 6.11.0
Pillow >= 10.0.0
PyYAML >= 6.0
pycups >= 2.0.1       # macOS only
certifi >= 2024.0.0
tifffile >= 2024.0.0
numpy >= 1.24.0
imagecodecs >= 2024.0.0
```

---

## Building from source

> The pre-built downloads above cover most users. Only continue here if you want to run or modify the source code directly.

### From source

```bash
git clone https://github.com/itsab1989/ChromIQ.git
cd ChromIQ
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

### Build a standalone .app from source

```bash
source .venv/bin/activate
pip install pyinstaller
pyinstaller ChromIQ.spec
# Result: dist/ChromIQ.app
```

Copy `dist/ChromIQ.app` to `/Applications` and launch like any other macOS app. ArgyllCMS binaries are not bundled — install them separately and configure the path in Preferences.

---

## Usage

> Every workflow tab has a clickable **ⓘ** icon next to its title that opens a beginner-friendly explanation of what the screen does, what needs to be ready (devices connected, paper loaded…), how to use it, and what comes next — the README below is a quick reference; the in-app tooltips are the full guide.

### First-time setup

**Install ArgyllCMS** before or after installing ChromIQ:
- **macOS** — download from [argyllcms.com](https://www.argyllcms.com/downloadmac.html), extract the archive, and move the folder to `/Applications` (e.g. `/Applications/Argyll_V3.5.0/`)
- **Windows** — download `win64` from [argyllcms.com](https://www.argyllcms.com/downloadwin.html) and extract to `C:\Program Files\ArgyllCMS\`
- **Linux** — use your package manager (`sudo apt install argyll`) or download from [argyllcms.com](https://www.argyllcms.com/downloadlinux.html)

**On first launch**, ChromIQ searches for ArgyllCMS automatically. If it is found, you are ready to go. If not:
1. A setup guide opens — follow the on-screen instructions
2. Or open **Preferences** (`⌘,` on macOS / `Ctrl+,` on Windows & Linux), click **Auto-detect**, and ChromIQ will search again
3. If auto-detection still fails, click **Browse** and navigate manually to the ArgyllCMS `bin` folder, then click **Test binaries** to confirm everything is working

### Step 1 — Create Chart
- Choose **Guided** or **Manual** mode
- In Guided mode: select your instrument and paper size, set the number of pages, and ChromIQ calculates the optimal patch count automatically
- Optionally toggle **Suppress left clip border (-L)** — suppressing it gains ~15 mm of printable width for extra patches; leave it on unless you use a physical paper-clip jig
- Click **Generate Chart** — the TIFF preview appears on the right when done
- Optional **Refinement (Optional)** section: tick **Refinement profile** and pick an existing `.icc` / `.icm` to drive a `targen -c` second-pass profiling run — useful for iteratively improving an existing profile rather than building from scratch

### Step 2 — Print Chart
- Select your printer from the dropdown (click ↺ to refresh the list)
- Configure paper slot, media type, and print quality if needed
- Click **Print Page X** for each page of the chart — color management is disabled automatically via the PostScript pipeline; no driver settings need changing
- For AirPrint/driverless printers, ChromIQ falls back to TIFF automatically if the printer rejects PostScript
- The **native OS print sheet** is used on Windows and Linux, and on macOS when "Use default macOS printer dialog" is enabled in Preferences — when it opens, disable colour management manually in the driver panel (per-brand instructions are shown in the Print tab)
- Before each job a **Confirm Print Settings** dialog summarises printer, paper, media, quality, orientation, duplex, and colour-management status; toggle via *Confirm Print Settings* in Preferences (on by default)
- If the printer is offline or has held / stuck jobs, ChromIQ flags it before sending — use the **Clear Print Queue** button (top right of the Print tab) to cancel held jobs and retry

### Step 3 — Measure Chart
- The `.ti2` file from Step 1 is loaded automatically
- Follow the on-screen prompts from `chartread`
- Use **Enter/Space** to confirm each strip, **← →** to navigate, **ESC** to abort
- On a misread, the dialog offers **Retry**, **Skip Stripe**, or **Save Partial && Quit** — the last option writes the partial `.ti3` and arms the **Refine / resume existing measurement (-r)** checkbox so one click continues from where you stopped on the next launch
- For instruments that support it, set the **Spectral filter type (-F)** dropdown (None / M1 / M2 / M3) before measuring

### Step 4 — Build Profile
- Review the `colprof` settings (quality, algorithm, gamut mapping, etc.)
- When supplying a Gamut Source profile, set the CIECAM02 viewing-condition presets — **Source viewing (-c)** and **Destination viewing (-d)** — to drive correct perceptual and saturation tables
- Optionally embed ICC media attributes (Media Surface / Type / Polarity, Colour Type, Default Intent) from the **Color Science** group in Manual mode (`colprof -Z`)
- Click **Build Profile** — the resulting `.icc` file is saved in the same folder as the chart
- Click **Install Profile** to copy it to the standard system location so it is immediately available system-wide:
  - **macOS** — `~/Library/ColorSync/Profiles`
  - **Windows** — `C:\Windows\System32\spool\drivers\color`
  - **Linux** — `~/.local/share/color/icc` (or `$XDG_DATA_HOME/color/icc`)
- To iterate, click **← Use as Pre-conditioning** on the result dialog — the just-built profile pre-fills the Step 1 refinement chart picker and v1 is auto-archived as `pre_*`

> **Calibration mode** — turn on **Enable Calibration Options** in Preferences to rename this tab to **4. Calibration & Profiling** with three modules: **Create Calibration File** (`printcal`), **Build Profile** (`colprof`), and **Apply Calibration** (`applycal`). The Build Profile result dialog then offers an additional **Apply Calibration →** shortcut, and measurement files whose names start with `cal_` are routed to the calibration module automatically.

### Step 5 — Check & Refine
- The `.ti3` measurement file from Step 3 is loaded automatically
- Click **Run profcheck** to evaluate the finished profile — per-patch ΔE statistics are shown in the log
- Patches above the ΔE threshold are highlighted; click **Re-measure patches** to start a guided re-measurement of only those patches
- After re-measurement, click **Build Profile** again to incorporate the improved data
- The **Gamut Volume** panel on the right renders the profile as a zoomable 3D mesh and reports its volume (ΔE³); use **Compare with:** to load a second profile and ChromIQ reports the volume delta (Δ %), intersection volume, and bidirectional coverage (*A covered by B* / *B covered by A*)
- Click **← Use as Pre-conditioning** on the profcheck result dialog to start a Step 1 second-pass with the current profile pre-filled
- Repeat until the profile accuracy meets your requirements

---

## Project Structure

```
ChromIQ/
├── main.py                    # Entry point
├── ChromIQ.spec               # PyInstaller build spec (macOS)
├── ChromIQWin.spec            # PyInstaller build spec (Windows)
├── ChromIQLinux.spec          # PyInstaller build spec (Linux)
├── requirements.txt
├── assets/                    # App icons and UI images
├── core/
│   ├── argyll_detect.py       # ArgyllCMS auto-detection (PATH, Homebrew, /Applications scan, Windows paths)
│   ├── argyll_runner.py       # QProcess wrapper for ArgyllCMS tools
│   ├── file_manager.py        # Working folder and target name management
│   ├── logger.py              # Rotating file logger (~Library/Logs/ChromIQ/ on macOS; %LOCALAPPDATA%\ChromIQ\Logs\ on Windows)
│   ├── resource_path.py       # Asset path resolution for dev + frozen bundles
│   ├── settings.py            # QSettings wrapper with typed defaults
│   ├── strip_utils.py         # Strip label parsing and TIFF zone detection
│   ├── updater.py             # Background update checker (GitHub releases API)
│   ├── usb_driver_installer.py  # Windows: colorimeter detection and WinUSB driver installation via libwdi
│   ├── platform_paths.py      # Cross-platform path resolution (log dir, ICC install location, Argyll bin defaults)
│   └── version.py             # Application version constant
├── data/
│   ├── parameters.yaml        # All targen/printtarg/colprof flags + tooltips
│   └── patch_db.py            # Empirical per-sheet patch capacity database
├── ui/
│   ├── main_window.py         # Top-level window, tab container, status bar
│   ├── parameter_widget.py    # Auto-generated flag widgets from parameters.yaml
│   ├── styles.py              # Fusion dark-theme QSS stylesheet
│   ├── tiff_preview.py        # Zoomable multi-channel TIFF viewer widget
│   ├── tooltip_button.py      # ? icon with popover tooltip
│   ├── tab_header.py          # Per-tab workflow header widget (step indicator + headline)
│   ├── masthead_header.py     # Gradient masthead banner at the top of the window
│   ├── gradient_overlay.py    # Accent-coloured gradient wash on tab control panels
│   ├── spectrum_tab_bar.py    # Per-tab coloured tab bar
│   ├── spectrum_progress.py   # Animated five-segment spectrum progress bar
│   ├── scan_highlighter.py    # Strip highlight overlay during chartread measurement
│   ├── ti2_loader.py          # .ti2 file loading and cross-tab population logic
│   ├── gamut_panel.py         # 3D gamut viewer panel widget (iccgamut + X3DOM via QWebEngineView)
│   ├── widgets.py             # Shared widget helpers (browse buttons, etc.)
│   ├── dialogs/
│   │   ├── settings_dialog.py # Preferences dialog
│   │   └── preflight_dialog.py  # Print preflight confirmation dialog
│   └── tabs/
│       ├── tab_chart.py           # Step 1: chart creation
│       ├── tab_print.py           # Step 2: CUPS printing
│       ├── tab_measure.py         # Step 3: chartread measurement
│       ├── tab_profile.py         # Step 4: colprof profile building
│       └── tab_check_refine.py    # Step 5: profcheck quality check & refinement
└── workflow/
    ├── chart_creator.py       # targen + printtarg orchestration
    ├── cups_printer.py        # lp command wrapper
    ├── measure_manager.py     # chartread orchestration
    ├── postscript_generator.py  # PostScript Level 2/3 document generation for the print pipeline
    ├── print_manager.py       # Printer enumeration (lpstat)
    ├── printcal_runner.py     # printcal orchestration (calibration curve generation)
    ├── applycal_runner.py     # applycal orchestration (bake/remove/check calibration on ICC)
    ├── profile_builder.py     # colprof orchestration
    ├── profcheck_runner.py    # profcheck orchestration, ΔE parsing, quality grading, refinement guidance
    ├── gamut_viewer.py        # iccgamut orchestration, volume computation, X3DOM 3D mesh generation
    ├── viewgam_runner.py      # viewgam orchestration, gamut comparison and coverage statistics
    ├── native_print_macos.py  # macOS native print dialog implementation (PyObjC, colour-management lock)
    ├── page_geometry.py       # Chart page geometry computation (aspect ratio, orientation, DPI)
    └── tiff_metadata.py       # TIFF right-margin command stamp and chart notes
```

---

## Configuration

All settings are stored via `QSettings` (macOS: `~/Library/Preferences/ChromIQ.ChromIQ.plist`).

**Preferences dialog** (⌘,) exposes:

| Setting | Default | Description |
|---------|---------|-------------|
| ArgyllCMS bin path | `/Applications/Argyll/bin` | Directory containing the ArgyllCMS executables |
| Output folder | `~/ChromIQ/` | Root folder for all chart/profile sessions |

**Behaviour settings** (Preferences → Behaviour):

| Setting | Default | Description |
|---------|---------|-------------|
| Restore last active tab on launch | On | Re-opens on the tab that was active when the app was closed |
| Restore last session on launch | Off | Reloads previously loaded files (`.ti2`, `.ti3`, `.icc`) on startup |
| Enable calibration options | Off | Unlocks the full `printcal → applycal` calibration workflow |
| Use default macOS printer dialog | Off | Opens the native macOS print sheet instead of the built-in PostScript/CUPS pipeline (macOS only) |
| Confirm print settings before sending | On | Shows a preflight summary of all print options before every job |
| Use app theme colours for 3D gamut viewer | On | Remaps gamut mesh vertex colours to ChromIQ's spectrum accent palette |

**Per-tab defaults** — every tab has a **Save as Defaults** button that persists the current parameter values for that step. Defaults are restored on the next launch.

**User presets** (Create Chart — Manual mode) — multiple named parameter presets can be saved and recalled independently of the global defaults.

Each session creates a subfolder named after the target (e.g. `~/ChromIQ/Canon_A4_Matte_i1_2025-04-18_14-30/`) containing all generated files for that run.

---

## How Patch Count Is Calculated

In **Guided mode** ChromIQ determines how many color patches to generate:

1. **Direct lookup** — the empirical database in `data/patch_db.py` is consulted. Separate values are stored for charts with (`-L`) and without the left clip border, and for two margin settings: 6 mm (ColorMunki / SpectroScan) and 10 mm (i1Pro / i1Pro 3 Plus — raised to prevent strip-end clipping on the narrower scanning head).
2. **Binary search fallback** — for custom scale or margin settings, ChromIQ runs a series of quick `targen`/`printtarg` probes to find the maximum patch count that fits on a single page.

The database values were measured with Argyll 3.5.0 at 300 DPI. All common instrument/paper combinations are covered.

---

## Adding a New ArgyllCMS Parameter

Parameters are driven by `data/parameters.yaml` — no code changes needed:

```yaml
- tool: printtarg
  flag: "-x"
  type: bool
  default: false
  label: "Some new option"
  tooltip_title: "Some New Option (-x)"
  tooltip_body: "What this option does."
  expert_only: true   # optional: hide under Expert section
  no_space: false     # set true if value attaches directly to flag (e.g. -il not -i l)
```

Save the file and restart ChromIQ — the new parameter appears automatically in Manual mode.

---

## Windows

Full Windows support (x64 + ARM64) shipped in v3.0.0. All macOS behaviour is unchanged — every adaptation is behind a platform guard. The full ArgyllCMS workflow (chart creation, measurement, profiling, quality check) runs on Windows. The main differences from macOS:

- **Printing** uses the native Windows print dialog instead of the CUPS/PostScript pipeline. You must disable ICM (colour management) in your printer driver settings manually before printing a profiling target — ChromIQ cannot do this automatically without CUPS.
- **ICC profiles** are installed to `%WINDIR%\System32\spool\drivers\color\`. On some systems this may require administrator privileges; if it fails, copy the `.icc` file there manually.
- ArgyllCMS is auto-detected in `C:\Program Files\ArgyllCMS\bin` and `%LOCALAPPDATA%\ArgyllCMS\bin`. Download for Windows from [argyllcms.com](https://www.argyllcms.com/downloadwin.html) (`win64`).

### Feedback

If you run into any issues on Windows, please [open a bug report](https://github.com/itsab1989/ChromIQ/issues/new?template=bug_report.yml).

---

## Known Issues

> This section will be updated as issues are resolved.

- **Measurement (Step 3):** Some spectrophotometer models may require additional calibration steps not yet surfaced in the UI.
- **Advanced color science (Step 4):** FWA compensation and custom gamut mapping intents cover a wide range of instrument/paper combinations — edge cases may exist depending on your specific hardware and media.
- **Windows:** The CUPS-based PostScript print pipeline is not available on Windows — colour management must be disabled manually in the printer driver. See [Windows](#windows) above.
- **Linux (beta):** ChromIQ runs but has not been exercised against the full Argyll workflow on real hardware yet. Please report what works and what doesn't.

---

## Reporting issues & feedback

You can also reach these directly from inside the app — open **Preferences** (⌘,) and click **Report a Bug…** in the bottom row.

- **Bug?** [Open a bug report](https://github.com/itsab1989/ChromIQ/issues/new?template=bug_report.yml) — the form asks for the version, OS, ArgyllCMS install method, and repro steps. Filling it in completely is the single biggest factor in getting a fix.
- **Feature idea?** [Open a feature request](https://github.com/itsab1989/ChromIQ/issues/new?template=feature_request.yml).
- **Usage question or open-ended discussion?** Use [Discussions](https://github.com/itsab1989/ChromIQ/discussions) rather than the issue tracker.

Please include the contents of the in-app log panel (or the file under `~/Library/Logs/ChromIQ/chromiq.log` on macOS / `%LOCALAPPDATA%\ChromIQ\Logs\` on Windows / `~/.local/state/ChromIQ/logs/chromiq.log` on Linux) when reporting a bug — it captures every ArgyllCMS command ChromIQ ran and is usually the fastest way to identify the cause.

---

## Log File

ChromIQ writes a rotating log (max 5 MB × 5 backups) to:

- **macOS:** `~/Library/Logs/ChromIQ/chromiq.log`
- **Windows:** `%LOCALAPPDATA%\ChromIQ\Logs\chromiq.log`
- **Linux:** `~/.local/state/ChromIQ/logs/chromiq.log`

Every ArgyllCMS command and its full argument list is recorded at `INFO` level. Each session opens with a banner stamped with the local time, app version, platform, and Python version. Tab switches are logged with `---- Tab → <name> ----` markers so it's easy to locate output from a specific workflow step.

---

## License

To be determined.

---

## Support

ChromIQ is free and open-source. If it has saved you time and paper, [buying me a coffee on Ko-fi](https://ko-fi.com/itsab1989) is a kind way to say thanks and helps keep the project going.

---

## Acknowledgements

ChromIQ is built on top of [ArgyllCMS](https://www.argyllcms.com/) by Graeme Gill — an outstanding open-source color management system. All color science heavy lifting is done by ArgyllCMS; ChromIQ is purely a GUI front-end.

A heartfelt thanks to **soul-traveller** for [Argyll_Printer_Profiler](https://github.com/soul-traveller/Argyll_Printer_Profiler) — a printer profiling tool that is likely in a more mature and in several areas more comprehensive state than ChromIQ. If you prefer working with proven, pre-made test charts rather than randomly generated targets, his project includes an extensive collection of carefully selected charts that are an excellent fit for exactly that use case.
