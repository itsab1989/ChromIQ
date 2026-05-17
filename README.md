# ChromIQ

**ChromIQ** is a free, open-source desktop application for creating custom ICC profiles for RGB inkjet printers using [ArgyllCMS](https://www.argyllcms.com/). It provides a guided, five-step printer color calibration workflow that takes you from generating and printing a test chart through spectrophotometer measurement, ICC profile building with `colprof`, and quality verification with `profcheck` — without needing to touch the command line.

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
| ![ChromIQ Print Tab](docs/2a.png) | ![ChromIQ Measurement Tab](docs/2b.png) |

| Step 3a — Measure Chart (guided) | Step 3b — Measure Chart (manual) |
|---|---|
| ![ChromIQ Create ICC Profile](docs/3a.png) | ![ChromIQ Check & Refine](docs/3b.png) |

| Step 4a — Build Profile (guided) | Step 4b — Build Profile (manual) |
|---|---|
| ![ChromIQ Print Tab](docs/4a.png) | ![ChromIQ Measurement Tab](docs/4b.png) |

| Step 5a — Check & Refine (guided)  | Step 5b — Check & Refine (manual) |
|---|---|
| ![ChromIQ Create ICC Profile](docs/5a.png) | ![ChromIQ Check & Refine](docs/5b.png) |

| Settings  | Step 4c — Calibration & Profiling (disabled by default) |
|---|---|
| ![ChromIQ Create ICC Profile](docs/6.png) | ![ChromIQ Check & Refine](docs/4c.png) |

---

## Features

### Guided Workflow
ChromIQ walks you through five steps of RGB printer profiling:

1. **Create Chart** — generates a test chart using `targen` and `printtarg`, with automatic patch count calculation for your instrument/paper combination
2. **Print Chart** — sends the chart TIFF directly to your printer via CUPS with configurable print options
3. **Measure Chart** — drives your spectrophotometer with `chartread` to measure the printed patches
4. **Build Profile** — runs `colprof` to generate a finished ICC profile
5. **Check & Refine** — evaluates the finished profile with `profcheck`, shows per-patch ΔE statistics, and guides you through a targeted re-measurement to improve accuracy

### Guided and Manual Modes
- **Guided mode** (Step 1): Select instrument, paper size, and number of pages — ChromIQ looks up the optimal patch count from an empirical database and sets sensible defaults automatically.
- **Manual mode** (Step 1): Full access to all `targen` and `printtarg` flags for advanced users.

### Instrument Support
| Code | Instrument |
|------|-----------|
| `i1` | X-Rite i1Pro / i1Pro 2 / i1Pro 3 |
| `p3` | X-Rite i1Pro 3 Plus |
| `CM` | X-Rite ColorMunki / i1Studio / ColorChecker Studio |
| `SS` | X-Rite SpectroScan (flatbed XY) |

### Paper Size Support
A2, A3+, A3, A4, Tabloid (11×17), Legal, Letter, and landscape variants of each — plus photo formats (8×10", 5×7", 4×6") and fully custom dimensions (width × height in mm)

### Key Capabilities
- **ArgyllCMS auto-detection** at launch — on macOS searches the system PATH, Homebrew, MacPorts, and any versioned Argyll folder in `/Applications`; on Windows checks `C:\Program Files\ArgyllCMS\bin` and `%LOCALAPPDATA%\ArgyllCMS\bin`; on Linux probes `/usr/bin`, `/usr/local/bin`, `/opt/argyll/bin`, `/opt/argyllcms/bin`, and `~/.local/bin`. An **Auto-detect** button in Preferences re-runs detection on demand.
- Empirical patch capacity database (measured with Argyll 3.5.0) for instant lookup without binary search
- Separate patch counts for charts with and without the left clip border (`-L` flag)
- Double-density mode for ColorMunki/i1Studio with measuring rig (`-h` flag)
- Live TIFF preview of the generated test chart
- **PostScript Level 2/3 printing pipeline** — generates a device-dependent PS document (`/DeviceRGB`, `/DeviceCMYK`, `/DeviceN`) with `%cupsJobTicket: cups-disable-cmm`, ensuring zero colour transforms between the app and the printer
- **CMYK and multi-channel (DeviceN) target support** — 4-channel CMYK and 5–17 channel extended-gamut targets (e.g. CMYK + LC LM) print correctly without colour channel corruption
- **Cascading colorant slot overrides** (Create Chart — Manual mode) — up to 11 stacked `-D` modifications configure extended-gamut inksets (e.g. CMYK + Orange + Green + Light Cyan) directly in the UI; values and enabled states persist through presets and Save Defaults
- **16-bit TIFF printing** via PostScript Level 3 for printers and RIPs with a true 16-bit pipeline (`printtarg -T300`)
- **Automatic TIFF fallback** for AirPrint/driverless printers that reject PostScript — retries with colour-space-aware CUPS raster options, bypassing ColorSync without requiring PostScript support
- **Multi-page TIFF support** — Print Current Page and Print All Pages correctly extract and send individual frames from multi-page charts
- **Printer reachability check** — detects offline printers before submitting a job and shows a clear error dialog
- **Clear Print Queue** button and stuck-job pre-print detection — cancels held or aborted jobs before submitting a new one
- **AirPrint driver detection** in the Print tab — identifies when no configurable options are available and explains how to reinstall the printer with a native PPD driver
- **Optional native macOS printer dialog** — a toggle in Preferences → Behaviour opens the real macOS print panel via PyObjC and locks `AP_ApplicationColorMatching` mode automatically (no manual driver interaction needed); a post-print verification confirms the lock and shows a warning if it couldn't be applied. On Windows and Linux the native OS print dialog is always used — disable colour management manually in the driver panel (per-brand instructions are shown in the Print tab)
- **Print preflight confirmation** — before each job, ChromIQ shows a summary of all options being sent (printer, paper, tray, media, quality, orientation, duplex, colour-management status, and any detected mismatches); toggleable via "Confirm print settings before sending to printer" in Preferences (on by default). **Automatic page orientation** matches the chart aspect ratio to the selected paper, and a **paper-size mismatch warning** flags discrepancies before you waste ink
- **Zoomable TIFF preview** with full multi-channel support — displays RGB, CMYK, and extended-gamut TIFFs (up to 11 inks) with ICC-accurate colour conversion (US Web Coated SWOP v2); LZW-compressed files supported
- **Spectral filter type** option in Measure tab (`-F` flag) — override the measurement condition (M0 / M1 / M2 / M3) for instruments that support it
- Full `colprof` option set: illuminant (D50, D65, A, C, F5, F8, F10), observer (1931 2°, 1964 10°, 2015 variants), FWA compensation, gamut mapping source profiles, rendering intent overrides
- **ICC media attributes and default rendering intent** (`colprof -Z`) — embed Media Surface (Glossy/Matte), Colour Type (Color/B&W), Media Type, Polarity, and Default Rendering Intent in the profile header; available in both Guided and Manual modes
- **Interactive 3D ICC gamut viewer** (Check & Refine tab) — powered by ArgyllCMS `iccgamut` + `viewgam` + X3DOM; renders the profile gamut as a zoomable 3D mesh in-app with volume in ΔE³; options include rendering intent, colour space (Lab / CIECAM02 Jab), surface resolution, axes, cusp markers, and edge plot; themed to ChromIQ's spectrum accent colours; compare against a second ICC/ICM profile with delta %, intersection volume, and bidirectional coverage statistics
- **Windows WinUSB driver installer** — detects connected ArgyllCMS-compatible colorimeters via the Windows registry and installs the WinUSB driver silently with UAC elevation; falls back to bundled Zadig GUI if needed (Windows only)
- Per-tab **Save as Defaults** and named user presets (Manual mode) for repeatable workflows
- **Auto patch count** (Create Chart — Manual mode) — an "Auto" checkbox computes the exact patch count to fill a requested number of pages at Generate time, running a binary search when needed; the spinbox displays "Auto" while active
- **Self-documenting chart TIFFs** — the exact `targen` and `printtarg` commands plus the ChromIQ version are stamped as a rotated text line in the right margin of every generated TIFF; an optional "Chart notes" field (e.g. printer / paper details) rides along on the same stamp
- **Measurement error recovery** — the misread dialog offers Retry / Skip Stripe / Save Partial & Quit; "Save Partial & Quit" writes the `.ti3` with unread patches intact and automatically arms the resume checkbox so one click continues from where measurement left off
- **i1Pro margin auto-set to 10 mm** — for i1Pro / i1Pro 3 Plus the guided workflow silently applies a 10 mm page margin (vs. 6 mm for other instruments) to prevent strip-end clipping and "not enough patches read" errors; Manual mode pre-selects it when the instrument is picked but never overwrites a value typed by hand
- Automatic session naming based on printer, paper, media type, instrument, and timestamp
- **Optional calibration workflow** (`printcal → applycal`) — enabled via Preferences → Behaviour → "Enable calibration options" (off by default). When active: guided panels are hidden, Tab 4 becomes "Calibration & Profiling" with three modules (Create Calibration File, Build Profile, Apply Calibration), and measurements whose filename starts with `cal_` are automatically routed to the calibration module. **Create Calibration File** supports per-channel initial target overrides for C/M/Y/K and extended inkset channels (Ch4–Ch7), calibration metadata embedding (description, manufacturer, model, copyright flags `-D`/`-A`/`-M`/`-C`), imitation target mode (`-I`) to derive a null-calibration from an existing `.ti3`, a dry-run checkbox (`-d`) to simulate the calibration without writing any files, a spectrum progress bar, and a result dialog that offers "Go to Create Chart →" with the `.cal` path pre-filled. **Apply Calibration** shows a spectrum progress bar and a result dialog with "Install Profile". When calibration mode is active, the Build Profile result dialog also offers "Apply Calibration →" with the ICC path pre-filled; and the Measure completion dialog routes `cal_*` measurements to "Create Calibration File →" automatically
- **Responsive window sizing** — the window scales to fit the available screen on launch (13″ MacBook 1280×800 and larger); minimum size 900×650 enforced; geometry saved on a large display is clamped to the current screen on the next launch; the Print Chart options panel scrolls vertically on small screens
- **Session restore** — "Restore last session on launch" in Preferences reloads the previously active project files (`.ti2`, `.ti3`, `.icc`) on startup
- **Guided pre-conditioning (refinement) workflow** — the *Generate Chart* panel exposes an optional refinement section: tick the box and pick an existing `.icc` / `.icm` / `.mpp` to drive a `targen -c` second-pass profiling run. The *Build Profile* and *Check & Refine* result dialogs offer a one-click **Use as Pre-conditioning** action that pre-fills the chart picker with the just-built profile; the prior session's `.icc` / `.ti3` are auto-renamed `pre_*` so v1 isn't lost.
- **Per-tab onboarding tooltips** — every workflow tab has a clickable ⓘ icon next to its big title that opens a beginner-friendly explanation of what the screen does, what needs to be ready (devices connected, paper loaded…), how to use it, and what comes next. The *Build Profile* tooltip swaps to the 3-stage `printcal → applycal → colprof` flow when calibration mode is enabled; the *Print Chart* tooltip varies by OS and `use_native_print_dialog`.
- **Update checker** — silent background check on launch; manual check available in Preferences. SemVer-aware: pre-release users see newer betas as upgrade candidates, stable users only see stable releases.
- Settings persist between sessions via `QSettings`

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

### Step 2 — Print Chart
- Select your printer from the dropdown (click ↺ to refresh the list)
- Configure paper slot, media type, and print quality if needed
- Click **Print Page X** for each page of the chart — color management is disabled automatically via the PostScript pipeline; no driver settings need changing
- For AirPrint/driverless printers, ChromIQ falls back to TIFF automatically if the printer rejects PostScript
- On **Windows**, or when "Use default macOS printer dialog" is enabled in Preferences, the native OS print sheet opens — disable colour management manually in the driver panel (per-brand instructions are shown in the Print tab)

### Step 3 — Measure Chart
- The `.ti2` file from Step 1 is loaded automatically
- Follow the on-screen prompts from `chartread`
- Use **Enter/Space** to confirm each strip, **← →** to navigate, **ESC** to abort

### Step 4 — Build Profile
- Review the colprof settings (quality, algorithm, gamut mapping, etc.)
- Click **Build Profile** — the resulting `.icc` file is saved in the same folder as the chart
- Click **Install Profile** to copy it directly to `~/Library/ColorSync/Profiles/` so it is immediately available system-wide

### Step 5 — Check & Refine
- The `.ti3` measurement file from Step 3 is loaded automatically
- Click **Run profcheck** to evaluate the finished profile — per-patch ΔE statistics are shown in the log
- Patches above the ΔE threshold are highlighted; click **Re-measure patches** to start a guided re-measurement of only those patches
- After re-measurement, click **Build Profile** again to incorporate the improved data
- The **Gamut Volume** panel on the right displays the gamut as a zoomable 3D mesh and reports the gamut volume (ΔE³); load a second profile to compare volumes, delta %, and bidirectional coverage
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
