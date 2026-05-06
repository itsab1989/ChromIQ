# ChromIQ

**ChromIQ** is a free, open-source macOS desktop application for creating custom ICC profiles for RGB inkjet printers using [ArgyllCMS](https://www.argyllcms.com/). It provides a guided, five-step printer color calibration workflow that takes you from generating and printing a test chart through spectrophotometer measurement, ICC profile building with `colprof`, and quality verification with `profcheck` — without needing to touch the command line.

Supported instruments: X-Rite i1Pro, i1Pro 2, i1Pro 3, i1Pro 3 Plus, ColorMunki, i1Studio, ColorChecker Studio, and SpectroScan.

---

## Download

Pre-built DMGs are attached to each [GitHub Release](https://github.com/itsab1989/ChromIQ/releases/latest):

| Build | Runs on |
|-------|---------|
| `ChromIQ-macOS-universal.dmg` | Apple Silicon **and** Intel (recommended) |
| `ChromIQ-macOS-arm64.dmg` | Apple Silicon only |

Open the DMG, drag ChromIQ to Applications, eject, then launch. **First launch:** right-click → Open to bypass Gatekeeper (the app is ad-hoc signed, not notarized). ArgyllCMS must be installed separately — see [Requirements](#requirements).

---

## Screenshots

| Step 1a — Create Chart (guided) | Step 1b — Create Chart (manual)  |
|---|---|
|![ChromIQ Guided Test Chart creation](docs/1a.png) | ![ChromIQ Manual Test Chart creation](docs/1b.png) |

| Step 2 — Print Chart | Step 3a — Measure Chart (guided) |
|---|---|
| ![ChromIQ Print Tab](docs/2.png) | ![ChromIQ Measurement Tab](docs/3a.png) |

| Step 3b — Measure Chart (manual) | Step 4a — Build Profile (guided) |
|---|---|
| ![ChromIQ Create ICC Profile](docs/3b.png) | ![ChromIQ Check & Refine](docs/4a.png) |

| Step 4b — Build Profile (manual) | Step 5a — Check & Refine (guided) |
|---|---|
| ![ChromIQ Print Tab](docs/4b.png) | ![ChromIQ Measurement Tab](docs/5a.png) |

| Step 5b — Check & Refine (manual)  | Settings |
|---|---|
| ![ChromIQ Create ICC Profile](docs/5b.png) | ![ChromIQ Check & Refine](docs/6.png) |

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
A4, A4 Landscape, A3, A3 Landscape, A2, US Letter, Letter Landscape, Legal, Tabloid (11×17)

### Key Capabilities
- **ArgyllCMS auto-detection** at launch — searches the system PATH, Homebrew, MacPorts, and any versioned Argyll folder in `/Applications`. An **Auto-detect** button in Preferences re-runs detection on demand.
- Empirical patch capacity database (measured with Argyll 3.5.0) for instant lookup without binary search
- Separate patch counts for charts with and without the left clip border (`-L` flag)
- Double-density mode for ColorMunki/i1Studio with measuring rig (`-h` flag)
- Live TIFF preview of the generated test chart
- Direct TIFF printing via CUPS — color management forced off automatically, no manual option selection required, no ColorSync interference
- **Multi-page TIFF support** — Print Current Page and Print All Pages correctly extract and send individual frames from multi-page charts
- **Printer reachability check** — detects offline printers before submitting a job and shows a clear error dialog
- **Clear Print Queue** button and stuck-job pre-print detection — cancels held or aborted jobs before submitting a new one
- **AirPrint driver detection** in the Print tab — identifies when no configurable options are available and explains how to reinstall the printer with a native PPD driver
- **Zoomable TIFF preview** panel on every tab (labelled CHART PREVIEW / PRINT PREVIEW) — live view of the generated chart updates as parameters change
- **Spectral filter type** option in Measure tab (`-F` flag) — override the measurement condition (M0 / M1 / M2 / M3) for instruments that support it
- Full `colprof` option set: illuminant (D50, D65, A, C, F5, F8, F10), observer (1931 2°, 1964 10°, 2015 variants), FWA compensation, gamut mapping source profiles, rendering intent overrides
- Per-tab **Save as Defaults** and named user presets (Manual mode) for repeatable workflows
- Automatic session naming based on printer, paper, media type, instrument, and timestamp
- **Update checker** — silent background check on launch; manual check available in Preferences
- Settings persist between sessions via `QSettings`

---

## Requirements

### System
- macOS 13 Ventura or later (Apple Silicon and Intel supported)
- [ArgyllCMS 3.5.0](https://www.argyllcms.com/downloaddev.html) — ChromIQ auto-detects ArgyllCMS at launch, scanning the system PATH, Homebrew, MacPorts, and any versioned Argyll folder in `/Applications`. The path can be overridden or re-detected from Preferences.

### To run from source
- Python 3.12 or later

### Python dependencies
```
PyQt6 >= 6.11.0
Pillow >= 10.0.0
PyYAML >= 6.0
```

---

## Installation

### Pre-built app (recommended)

Download the latest DMG from the [Releases page](https://github.com/itsab1989/ChromIQ/releases/latest), open it, drag ChromIQ to Applications, and launch. No Python or build tools required.

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
1. Install ArgyllCMS — download from [argyllcms.com](https://www.argyllcms.com/downloadmac.html), extract the archive, and move the folder to `/Applications`
2. Launch ChromIQ — it auto-detects ArgyllCMS and configures itself. If detection fails, a setup guide opens with instructions.
3. (Optional) Open **Preferences** (⌘,) → click **Auto-detect** to re-run detection, or browse to the `bin` folder manually, then **Test binaries** to confirm

### Step 1 — Create Chart
- Choose **Guided** or **Manual** mode
- In Guided mode: select your instrument and paper size, set the number of pages, and ChromIQ calculates the optimal patch count automatically
- Optionally toggle **Suppress left clip border (-L)** — suppressing it gains ~15 mm of printable width for extra patches; leave it on unless you use a physical paper-clip jig
- Click **Generate Chart** — the TIFF preview appears on the right when done

### Step 2 — Print Chart
- Select your printer from the dropdown (click ↺ to refresh the list)
- Configure paper slot, media type, and print quality if needed
- Use **No Color Adjustment** in your printer driver to bypass color management when printing
- Click **Print Page X** for each page of the chart

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
- Repeat until the profile accuracy meets your requirements

---

## Project Structure

```
ChromIQ/
├── main.py                    # Entry point
├── ChromIQ.spec               # PyInstaller build spec
├── requirements.txt
├── assets/                    # App icons and UI images
├── core/
│   ├── argyll_detect.py       # ArgyllCMS auto-detection (PATH, Homebrew, /Applications scan)
│   ├── argyll_runner.py       # QProcess wrapper for ArgyllCMS tools
│   ├── file_manager.py        # Working folder and target name management
│   ├── logger.py              # Rotating file logger (~Library/Logs/ChromIQ/chromiq.log)
│   ├── resource_path.py       # Asset path resolution for dev + frozen bundles
│   ├── settings.py            # QSettings wrapper with typed defaults
│   ├── strip_utils.py         # Strip label parsing and TIFF zone detection
│   ├── updater.py             # Background update checker (GitHub releases API)
│   └── version.py             # Application version constant
├── data/
│   ├── parameters.yaml        # All targen/printtarg/colprof flags + tooltips
│   └── patch_db.py            # Empirical per-sheet patch capacity database
├── ui/
│   ├── main_window.py         # Top-level window, tab container, status bar
│   ├── parameter_widget.py    # Auto-generated flag widgets from parameters.yaml
│   ├── styles.py              # Fusion dark-theme QSS stylesheet
│   ├── tiff_preview.py        # Zoomable TIFF viewer widget
│   ├── tooltip_button.py      # ? icon with popover tooltip
│   ├── tab_header.py          # Per-tab workflow header widget (step indicator + headline)
│   ├── widgets.py             # Shared widget helpers (browse buttons, etc.)
│   ├── dialogs/
│   │   └── settings_dialog.py # Preferences dialog
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
    ├── postscript_generator.py  # PostScript generation — internal infrastructure, not used in current workflow
    ├── print_manager.py       # Printer enumeration (lpstat)
    ├── profile_builder.py     # colprof orchestration
    └── profcheck_runner.py    # profcheck orchestration, ΔE parsing, quality grading, refinement guidance
```

---

## Configuration

All settings are stored via `QSettings` (macOS: `~/Library/Preferences/ChromIQ.ChromIQ.plist`).

**Preferences dialog** (⌘,) exposes:

| Setting | Default | Description |
|---------|---------|-------------|
| ArgyllCMS bin path | `/Applications/Argyll/bin` | Directory containing the ArgyllCMS executables |
| Output folder | `~/ChromIQ/` | Root folder for all chart/profile sessions |

**Per-tab defaults** — every tab has a **Save as Defaults** button that persists the current parameter values for that step. Defaults are restored on the next launch.

**User presets** (Create Chart — Manual mode) — multiple named parameter presets can be saved and recalled independently of the global defaults.

Each session creates a subfolder named after the target (e.g. `~/ChromIQ/Canon_A4_Matte_i1_2025-04-18_14-30/`) containing all generated files for that run.

---

## How Patch Count Is Calculated

In **Guided mode** ChromIQ determines how many color patches to generate:

1. **Direct lookup** — for standard `patch_scale` (1.0) and `margin_mm` (6 mm), the empirical database in `data/patch_db.py` is consulted. Separate values are stored for charts with (`-L`) and without the left clip border.
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

## Known Issues

> This section will be updated as issues are resolved.

- **Measurement (Step 3):** Some spectrophotometer models may require additional calibration steps not yet surfaced in the UI.
- **Advanced color science (Step 4):** FWA compensation and custom gamut mapping intents cover a wide range of instrument/paper combinations — edge cases may exist depending on your specific hardware and media.
- **macOS only:** ChromIQ is developed and tested exclusively on macOS. The profile installation path (`~/Library/ColorSync/Profiles/`) and certain system integrations (dark title bar, macOS keychain) are macOS-specific. There are no plans for Windows or Linux support at this time. If you need a simple Windows or Linux option for printer profiling, try [Argyll_Printer_Profiler scripts](https://soul-traveller.github.io/Argyll_Printer_Profiler/) by Knut Georg Larsson.

---

## Log File

ChromIQ writes a rotating log to `~/Library/Logs/ChromIQ/chromiq.log` (max 2 MB, 3 backups). All ArgyllCMS commands and their full argument lists are recorded here at `INFO` level, which is useful for debugging unexpected behaviour.

---

## License

To be determined.

---

## Acknowledgements

ChromIQ is built on top of [ArgyllCMS](https://www.argyllcms.com/) by Graeme Gill — an outstanding open-source color management system. All color science heavy lifting is done by ArgyllCMS; ChromIQ is purely a GUI front-end.

A heartfelt thanks to **soul-traveller** for [Argyll_Printer_Profiler](https://github.com/soul-traveller/Argyll_Printer_Profiler) — a printer profiling tool that is likely in a more mature and in several areas more comprehensive state than ChromIQ. If you prefer working with proven, pre-made test charts rather than randomly generated targets, his project includes an extensive collection of carefully selected charts that are an excellent fit for exactly that use case.
