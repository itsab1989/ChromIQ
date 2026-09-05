<h1 align="center">ChromIQ</h1>

<p align="center">
  <strong>Make your inkjet printer print accurate colour — without touching the command line.</strong>
</p>

<p align="center">
  <img alt="Version" src="https://img.shields.io/badge/version-4.1.4-7c5cff">
  <img alt="Downloads" src="https://img.shields.io/endpoint?url=https://itsab1989.github.io/github-traffic-downloads-dashboard/assets/badges/itsab1989_ChromIQ-downloads.json">
  <img alt="Platforms" src="https://img.shields.io/badge/platforms-macOS%20%C2%B7%20Windows%20%C2%B7%20Linux-2a9d8f">
  <img alt="License" src="https://img.shields.io/badge/license-GPLv3-blue">
</p>

<p align="center">
  <strong><a href="https://itsab1989.github.io/ChromIQ/">🌐 Website</a></strong>
  &nbsp;·&nbsp;
  <strong><a href="https://github.com/itsab1989/ChromIQ/releases/latest">⬇️ Download</a></strong>
</p>

<p align="center">
  <img src="docs/title.png" alt="ChromIQ — Create Chart tab with a full A4 test chart in the preview" width="900">
</p>

ChromIQ is a free, open-source desktop app that builds custom **ICC printer
profiles** — the colour "fingerprint" that tells your computer exactly how your
printer, ink, and paper reproduce colour. With an accurate profile, what you see
on screen is what comes out of the printer.

Under the hood it drives [**ArgyllCMS**](https://www.argyllcms.com/), the
gold-standard open-source colour engine, through a friendly five-step wizard.
ArgyllCMS does all the colour science; ChromIQ gives it a calm, guided interface
so you never have to memorise a single flag.

> [!NOTE]
> **New to printer profiling?** That's exactly who ChromIQ is for. Every screen
> has a clickable **ⓘ** icon that explains, in plain language, what the step
> does, what you need ready (device plugged in, paper loaded…), and what comes
> next. The in-app tooltips are the real manual — this README is the map.

<p align="center">
  <a href="https://ko-fi.com/itsab1989"><img src="https://ko-fi.com/img/githubbutton_sm.svg" alt="Support ChromIQ on Ko-fi" height="36"></a>
  <br>
  <sub>ChromIQ is free and always will be. If it's useful to you, a coffee is a kind way to say thanks — completely optional, and the app stays fully featured either way.</sub>
</p>

---

## Table of contents

- [What you'll need](#what-youll-need)
- [Download & install](#download--install)
  - [macOS](#macos)
  - [Windows](#windows)
  - [Linux (beta)](#linux-beta)
  - [Installing ArgyllCMS](#installing-argyllcms)
- [The five-step workflow](#the-five-step-workflow)
- [Screenshots](#screenshots)
- [Feature highlights](#feature-highlights)
- [Troubleshooting](#troubleshooting)
- [Configuration & logs](#configuration--logs)
- [For developers](#for-developers)
- [Reporting issues & feedback](#reporting-issues--feedback)
- [License](#license)
- [Acknowledgements](#acknowledgements)

---

## What you'll need

To build a profile you need three things:

1. **A printer** — any inkjet (RGB, CMYK, or extended-gamut with extra inks).
2. **A spectrophotometer** — the device that "reads" the printed colours.
   ChromIQ supports the X-Rite family:

   | Code | Instrument |
   |------|-----------|
   | `i1` | i1Pro / i1Pro 2 / i1Pro 3 |
   | `p3` | i1Pro 3 Plus |
   | `CM` | ColorMunki / i1Studio / ColorChecker Studio |
   | `SS` | SpectroScan (flatbed XY table) |

3. **ArgyllCMS** installed on your computer — ChromIQ looks for it automatically
   and walks you through installing it if it's missing. See
   [Installing ArgyllCMS](#installing-argyllcms).

ChromIQ itself runs on **macOS**, **Windows** (Intel/AMD and ARM64), and
**Linux** (x86_64 and aarch64, currently beta).

---

## Download & install

Grab the build for your system from the
**[latest release](https://github.com/itsab1989/ChromIQ/releases/latest)**.
The pre-built downloads are all most people need — you only need the
[from-source](#for-developers) route if you want to modify the code.

### macOS

**Requires macOS 13 Ventura or newer** (the Qt framework inside ChromIQ sets
this floor — on macOS 12 and older the app cannot start). On an older Mac,
ChromIQ can still run from source with an older Qt: install Python 3.12+,
then `pip install "PyQt6==6.8.*" "PyQt6-WebEngine==6.8.*"` with the other
requirements and start `python main.py`.

1. Download the universal DMG — **`ChromIQ-macOS-universal_<version>.dmg`**
   (works on both Apple Silicon and Intel).
2. Open the DMG, then drag **ChromIQ** into your **Applications** folder.
3. Eject the DMG (⌘E).
4. The first time only: open **Applications**, **right-click ChromIQ → Open**,
   then click **Open** in the dialog. This tells macOS you trust the app.

> [!TIP]
> **Right-click → Open shows only a "Done" button (macOS Sonoma 14+)?**
> Run this once in Terminal, then double-click ChromIQ normally:
> ```bash
> xattr -dr com.apple.quarantine /Applications/ChromIQ.app
> ```

### Windows

1. Download the build for your PC:
   - **`ChromIQ-Windows-x64_<version>.zip`** — Intel/AMD (most PCs)
   - **`ChromIQ-Windows-arm64_<version>.zip`** — ARM64 (e.g. Snapdragon X laptops)
2. Right-click the ZIP → **Extract All…**, open the extracted `ChromIQ` folder.
3. Double-click **`ChromIQ.exe`**.

> [!TIP]
> **"Windows protected your PC" / Defender flags the EXE?** This is the usual
> false positive for open-source apps that aren't code-signed yet — see
> [Troubleshooting](#troubleshooting) for how to allow it. The full source is in
> this repo and every release is built by GitHub Actions from its matching tag.

### Linux (beta)

1. Download the build for your machine:
   - **`ChromIQ-Linux-x86_64_<version>.tar.gz`** — Intel/AMD
   - **`ChromIQ-Linux-aarch64_<version>.tar.gz`** — ARM (Raspberry Pi 4/5, ARM workstations)
2. Extract and run:
   ```bash
   tar xzf ChromIQ-Linux-x86_64_*.tar.gz
   ./ChromIQ/ChromIQ
   ```

> [!TIP]
> **`qt.qpa.plugin: … xcb-cursor0 …` on launch?** Install the missing library —
> see [Troubleshooting](#troubleshooting).

Linux support is **beta**: ChromIQ runs, but the full workflow hasn't been
exercised against real hardware yet. Please report what works (and what doesn't)
via [Discussions](https://github.com/itsab1989/ChromIQ/discussions) or the
[issue tracker](https://github.com/itsab1989/ChromIQ/issues).

### Installing ArgyllCMS

ChromIQ needs ArgyllCMS 3.5.0 to do the colour work. **It is not bundled with
ChromIQ** — you install it once, separately, and ChromIQ finds it automatically.

| OS | How to install |
|----|----------------|
| **macOS** | Download from [argyllcms.com](https://www.argyllcms.com/downloadmac.html), unzip, and move the folder into `/Applications` (e.g. `/Applications/Argyll_V3.5.0/`). |
| **Windows** | Download the `win64` build from [argyllcms.com](https://www.argyllcms.com/downloadwin.html) and extract to `C:\Program Files\ArgyllCMS\`. |
| **Linux** | `sudo apt install argyll` · `sudo dnf install argyllcms` · `sudo pacman -S argyllcms`, or download from [argyllcms.com](https://www.argyllcms.com/downloadlinux.html). |

**On first launch ChromIQ searches automatically** — the system `PATH`, Homebrew,
MacPorts and any `Argyll*` folder in `/Applications` on macOS; the standard
install folders on Windows; `/usr/bin` and common paths on Linux. If it can't
find ArgyllCMS, a setup guide opens. You can also point it manually any time:

> **Preferences** (`⌘,` on macOS, `Ctrl+,` elsewhere) → **Auto-detect** to search
> again, or **Browse** to the ArgyllCMS `bin` folder, then **Test binaries** to
> confirm it works.

---

## The five-step workflow

ChromIQ is organised as five numbered tabs. Walk left to right and you have a
finished, installed profile.

| | Step | What happens | ArgyllCMS tool |
|---|------|--------------|----------------|
| **1** | **Create Chart** | Generate a test chart with the ideal number of colour patches for your instrument, paper, and page count. | `targen` + `printtarg` |
| **2** | **Print Chart** | Send the chart to your printer with colour management switched **off** (so you measure the printer's raw behaviour). | CUPS / native dialog |
| **3** | **Measure** | Scan the printed patches with your spectrophotometer. | `chartread` |
| **4** | **Build Profile** | Turn the measurements into a finished `.icc` profile and install it. | `colprof` |
| **5** | **Check & Refine** | Score the profile's accuracy, view its 3D gamut, and re-measure only the worst patches to improve it. | `profcheck` + `iccgamut` |

Every step offers two modes:

- **Guided** — pick instrument, paper, and page count; ChromIQ chooses sensible,
  empirically-tuned defaults for everything else.
- **Manual** — every ArgyllCMS flag is exposed, with a live preview of the exact
  command that will run. Save your favourite setups as named **presets**.

### Step 1 — Create Chart
Choose Guided or Manual, name your target, and click **Generate Chart**. The
patch grid appears in the preview on the right. Optionally tick **Refinement
profile** to base a second, improved pass on an existing `.icc`/`.icm`.

### Step 2 — Print Chart
Pick your printer and print the chart. **On macOS the native print dialog is now
the default** — ChromIQ opens the OS print sheet and *locks the driver's colour
controls off for you* (via PyObjC), so colour management can't sneak back in.
The per-brand steps for confirming colour is disabled are shown right in the tab.
On Windows and Linux the OS print sheet opens the same way, with per-brand
instructions for turning ICM off.

> [!TIP]
> Prefer the old behaviour on macOS? Turn **Use default macOS printer dialog**
> *off* in Preferences and ChromIQ falls back to its direct **PostScript
> pipeline**, which bypasses colour management automatically with no dialog at
> all — handy for batch printing.

### Step 3 — Measure
The chart from Step 1 loads automatically. Follow the on-screen prompts:
**Enter/Space** confirms a strip, and **F** / **B** step **forward** and **back**
between strips (the on-screen strip highlight follows along). Misread a strip?
The dialog offers **Retry**, **Skip Stripe**, or **Save Partial & Quit** (which
lets you resume later with one click).

### Step 4 — Build Profile
Review the `colprof` settings and click **Build Profile**. Then **Install
Profile** copies it to the right place for your OS so every app can use it. To
iterate, click **← Use as Pre-conditioning** to seed an improved second pass.
In Manual mode you can also control **black generation** (`-k`/`-K`) — how much
black ink the profile uses for dark colours — with every rule explained in
plain language. An optional, **experimental** ChromIQ-built profile engine
(off by default) can build here too — see
[the experimental engine](#experimental-the-chromiq-profile-engine-beta) below.

### Step 5 — Check & Refine
Click **Analyse Profile Quality** to get per-patch ΔE accuracy scores. The 3D
**Gamut Volume** viewer on the right shows the range of colours your profile can
reproduce — and you can load a second profile to **compare** them
(volume difference, overlap, and coverage in both directions). Patches that
scored poorly can be re-measured in one click, then rebuilt.

> [!NOTE]
> **Optional calibration mode.** Turn on **Enable calibration options** in
> Preferences to expand Step 4 into a three-part panel — **Create Calibration
> File** (`printcal`), **Build Profile** (`colprof`), and **Apply Calibration**
> (`applycal`) — for per-channel ink linearisation before profiling.

---

## Screenshots

Every screen is shown in both **Dark** and **Light** appearance (ChromIQ also has
a System/Auto mode that follows your OS live). Click any step to expand it.

<details open>
<summary><strong>Step 1 — Create Chart</strong></summary>

| | Dark | Light |
|---|---|---|
| **Guided** | ![Create Chart, guided, dark](docs/01-create-chart-guided-dark.png) | ![Create Chart, guided, light](docs/01-create-chart-guided-light.png) |
| **Manual** | ![Create Chart, manual, dark](docs/02-create-chart-manual-dark.png) | ![Create Chart, manual, light](docs/02-create-chart-manual-light.png) |
</details>

<details>
<summary><strong>Step 2 — Print Chart</strong></summary>

| | Dark | Light |
|---|---|---|
| **Native print dialog** (macOS default) | ![Print Chart, native dialog, dark](docs/03-print-chart-native-dialog-dark.png) | ![Print Chart, native dialog, light](docs/03-print-chart-native-dialog-light.png) |
| **PostScript pipeline** (no-dialog fallback) | ![Print Chart, PostScript, dark](docs/04-print-chart-postscript-dark.png) | ![Print Chart, PostScript, light](docs/04-print-chart-postscript-light.png) |
</details>

<details>
<summary><strong>Step 3 — Measure</strong></summary>

| | Dark | Light |
|---|---|---|
| **Guided** | ![Measure, guided, dark](docs/05-measure-guided-dark.png) | ![Measure, guided, light](docs/05-measure-guided-light.png) |
| **Manual** | ![Measure, manual, dark](docs/06-measure-manual-dark.png) | ![Measure, manual, light](docs/06-measure-manual-light.png) |
| **Expected vs. measured overlay** | ![Measure overlay, dark](docs/06b-measure-overlay-dark.png) | ![Measure overlay, light](docs/06b-measure-overlay-light.png) |
| **"All stripes read" prompt** | ![Measure dialog, dark](docs/17-dialog-measure-stripes-dark.png) | ![Measure dialog, light](docs/17-dialog-measure-stripes-light.png) |
</details>

<details>
<summary><strong>Step 4 — Build Profile</strong></summary>

| | Dark | Light |
|---|---|---|
| **Guided** | ![Build Profile, guided, dark](docs/07-build-profile-guided-dark.png) | ![Build Profile, guided, light](docs/07-build-profile-guided-light.png) |
| **Manual** | ![Build Profile, manual, dark](docs/08-build-profile-manual-dark.png) | ![Build Profile, manual, light](docs/08-build-profile-manual-light.png) |
| **"Profile built" — what next?** | ![Profile Built dialog, dark](docs/15-dialog-profile-built-dark.png) | ![Profile Built dialog, light](docs/15-dialog-profile-built-light.png) |
| **Calibration mode** — Create Calibration File (`printcal`) | ![Create Calibration File, dark](docs/09-calibration-create-file-dark.png) | ![Create Calibration File, light](docs/09-calibration-create-file-light.png) |
| **Calibration mode** — Apply Calibration (`applycal`) | ![Apply Calibration, dark](docs/10-calibration-apply-dark.png) | ![Apply Calibration, light](docs/10-calibration-apply-light.png) |
</details>

<details>
<summary><strong>Step 5 — Check &amp; Refine</strong></summary>

| | Dark | Light |
|---|---|---|
| **Analysis run** | ![Check & Refine, dark](docs/11-check-results-dark.png) | ![Check & Refine, light](docs/11-check-results-light.png) |
| **Quality assessment** (per-patch ΔE) | ![Quality Assessment dialog, dark](docs/16-dialog-quality-assessment-dark.png) | ![Quality Assessment dialog, light](docs/16-dialog-quality-assessment-light.png) |
| **Manual options** | ![Check & Refine, manual, dark](docs/12-check-manual-dark.png) | ![Check & Refine, manual, light](docs/12-check-manual-light.png) |
| **3D gamut comparison** (two profiles) | ![Gamut comparison, dark](docs/13-gamut-compare-dark.png) | ![Gamut comparison, light](docs/13-gamut-compare-light.png) |
</details>

<details>
<summary><strong>Preferences</strong></summary>

| Dark | Light |
|---|---|
| ![Preferences, dark](docs/14-preferences-dark.png) | ![Preferences, light](docs/14-preferences-light.png) |
</details>

---

## Feature highlights

### Guided & Manual, side by side
- **Guided** uses an empirical patch-capacity database to pick the right patch
  count for your instrument/paper/page combo — no guesswork.
- **Manual** exposes every `targen` / `printtarg` / `colprof` flag with a live
  command preview, plus per-tab **Save as Defaults** and named **presets**.

### Printing that just works
- **PostScript Level 2/3 pipeline** (macOS) that disables colour management
  automatically — no driver fiddling, no ColorSync in the way.
- **Automatic TIFF fallback** for AirPrint / driverless printers that reject
  PostScript, plus **16-bit TIFF** output for true 16-bit printers and RIPs.
- **Native OS print dialog** option — on macOS it even locks the driver's colour
  controls via PyObjC so they can't be re-enabled by accident; on Windows/Linux
  it shows per-brand instructions for turning ICM off.
- **Preflight confirmation** with paper-size and orientation checks, **offline
  printer detection**, and a **Clear Print Queue** button for stuck jobs.

### Serious colour science
- Full `colprof` option set — illuminants (D50/D65/A/C/F5/F8/F10), observers
  (1931 2°, 1964 10°, 2015 variants), FWA compensation, gamut-mapping intents.
- **RGB, CMYK, and multi-channel (DeviceN) targets** — from 4-channel CMYK to
  extended-gamut ink sets (CMYK plus Orange, Green, Light Cyan, …). The UI lets
  you stack up to **11 colorant overrides** (`-D`); ArgyllCMS supports up to 16
  device channels.
- **Pre-conditioning (second-pass) refinement** — drive a `targen -c` pass from
  an existing profile to iteratively improve it, with automatic archiving.
- **CIECAM02 viewing-condition presets** for correct perceptual/saturation tables.
- **ICC media attributes** (`colprof -Z`) embedded in the profile header.
- **Black generation control** (`colprof -k`/`-K`) in Build Profile → Manual —
  choose how much black ink your profiles use for dark colours, from pure CMY
  to maximum black, with plain-language explanations of every rule.

### Experimental: the ChromIQ profile engine (beta)

> [!WARNING]
> Everything in this section is **experimental** and **off by default**. The
> engine is validated against a synthetic test bench, ~2 000 automated tests,
> and ArgyllCMS's own tools — but **not yet on real multi-ink printing
> hardware**. Argyll `colprof` remains the default and the reference. If you
> try the engine, always print a test image before trusting a profile for
> real work.

ChromIQ now contains its **own profile builder** next to Argyll `colprof`.
Enable it under **Settings → Beta → ChromIQ profile engine** and the Build
Profile tab lets you build with either — same measurements, same options, so
you can build both and compare. Why it exists: `colprof` cannot build profiles
for printers with more than four inks; the engine can — CMYK plus orange,
green, violet, light inks — closing the whole multi-ink loop inside ChromIQ
(design the chart, print, measure, build, refine).

- **Three accuracy modes** (Settings → Beta): **Fast** (ChromIQ's own
  implementation of colprof's method, validated against Argyll), **Bit-exact**
  (real colprof for standard printers; a bundled helper runs Argyll's genuine
  gamut-mapping code for multi-ink ones), and **Maximum accuracy** (averages
  your repeated white/black patches, picks smoothing for your specific chart
  by cross-validation, survives a smudged patch and names it so you can
  remeasure, and honours the total-ink limit in the least-damaging way).
- **ICC v4 output** — build **v2** (classic, most compatible), **v4** (modern,
  with a built-in integrity checksum), or **Both**. Engine-only for now.
- **Spectral physics model** — a physical model of ink-on-paper for multi-ink
  printers with spectral measurements. It must beat the standard model on your
  own chart before it is used, so it can only win or change nothing.
- **Measurement noise handling** — diagnoses how noisy your measurement really
  was and only engages when the chart is measurably noisy; on a clean chart
  your profile is bit-for-bit unchanged.
- **Out-of-gamut rendering** — keep the Argyll-matched rendering (default) or
  try ChromIQ's mathematically-exact alternative and judge the look on your
  own prints.
- **Check & Refine for multi-ink profiles** — the accuracy check works on
  6-ink and larger profiles, which stock `profcheck` won't read.

### Quality check & 3D gamut viewer
- **`profcheck` integration** with per-patch ΔE statistics and quality grading.
- **Targeted re-measurement** — only the patches above your ΔE threshold.
- **Interactive 3D gamut viewer** (`iccgamut` + `viewgam` + X3DOM) with volume
  in ΔE³, Lab / CIECAM02 Jab, cusp markers, and edge plots.
- **Profile-vs-profile comparison** — volume delta, intersection volume, and
  bidirectional coverage.

### Design your own chart — layout editor & colour-set generator
Most people never need this — Guided mode already picks a great chart. But when
you want full control over *which colours* you measure and *how the sheet is laid
out*, the **chart layout editor** (Tools → **Edit / create chart layout**) is a
complete design surface:

- **Start from anything** — load an existing `.ti2`, pull in the chart you just
  made on the Create Chart tab, or build a fresh patch set from a targen seed,
  pasted colours or the colour-set generators.
- **Rearrange freely** — move patches and whole strips with Front / Up / Down /
  Back, and see the printed sheet redraw in a live, multi-page preview.
- **Recolour patches and spacers** — set or nudge patch colours, edit the spacer
  palette, or paint individual separator strips, all while ChromIQ keeps the
  measurement data and the printed pixels perfectly in sync.
- **Combine charts** — append or prepend the colours from another `.ti2`/`.ti1`/
  `.ti3`/i1Profiler file to merge two targets into one.
- **See it in 3D** — the **3D distribution** viewer plots your whole patch set as
  an interactive RGB cube so you can spot gaps and clumps at a glance.
- **Save & apply** pushes your custom layout straight back into the Create Chart
  tab, ready to print.

**Build a target around the colours you actually print.** The **colour-set
generator** (in *New chart* and *Add patches*) lets you stack any mix of these,
with live patch counts and automatic de-duplication so combined sets never
double up:

- **3D RGB cube** — even coverage across the whole colour range.
- **Skin tones** — light→dark ramps through all six Fitzpatrick phototypes.
- **Blues / turquoise** and **Greens (foliage)** — denser sampling of skies,
  water, forests, and foliage.
- **Near-neutral greys** — a neutral ramp plus subtle hue rings for clean,
  cast-free greys.
- **Saturated edges** and **gamut faces** — the most vivid colours your printer
  can reach, for accurate gamut boundaries.
- **Highlights & shadows** — extra detail at the bright and dark ends where
  printers struggle most.
- **Pastels** — soft, low-chroma colours across every hue.
- **From image** — load a photo and ChromIQ extracts its most representative
  colours, so you can profile around a specific image or palette.
- **White & black anchors** and **Fill remaining gaps** — guarantee pure
  paper-white/black, then scatter extra patches into the sparsest parts of the
  set up to a target count.

**Ink devices, not just RGB.** The *New chart* and *Add patches* windows can
design charts in **CMYK or CMYK + extra inks** (added as removable chips), with
a first-class ink limit and an optional preconditioning profile. Ink-native
colour sets — per-ink ramps, ink-pair and ink-triple overprints, a rich-black
ramp, grey-balance rings re-centred on your printer's measured neutral — join
the look-based sets above, which translate into real ink values through the
preconditioning profile. Charts save as **true separated TIFFs** (each ink a
named channel, opens correctly in Photoshop and RIPs) with an optional
press-ready **vector-PDF** export, and the preview gains a **per-ink
inspector**. The chart tools themselves are fully supported; note that
*building a profile* from charts with more than four inks requires the
[experimental profile engine](#experimental-the-chromiq-profile-engine-beta).

### Tools menu — standalone utilities
The masthead **Tools** button opens a menu of conversions and checks you can run
on their own, outside the five-step flow:
- **Edit / create chart layout** — the full layout editor and colour-set
  generator described above: reorder strips, recolour patches and spacers,
  combine charts, generate custom colour sets, and view them in 3D.
- **Average measurements** — combine repeat reads of the same chart for lower noise.
- **Merge measurements** — fold extra measurements into an existing set.
- **Convert TI1 → i1Profiler** and **Convert i1Profiler → TI1 / TI3** — move charts
  and measurements between ChromIQ/ArgyllCMS and X-Rite i1Profiler.
- **Verify a profile** (independent check) and **Verify against reference** —
  validate an existing profile's accuracy without rebuilding it.

### Your work, kept in order
- **Every run keeps its own chart, measurement, settings and description.**
  Going back to an older run shows the settings that run was actually made
  with — not the last ones you happened to type.
- **Nothing is deleted, only archived.** A measurement you replace, a chart you
  regenerate and a calibration you redo all move to an `old/` folder with the
  date, and the window says so before you commit.
- **Calibration is a run type** of its own: its chart, measurement and `.cal`
  file live in the project's `cal/` folder, shared by every run, and each
  profile records which calibration it was built with.
- **Verification runs, kept as history.** Measure a chart printed *through* a
  finished profile and the result is filed by date with its own report — earlier
  checks are never overwritten, so you can watch a profile drift over months.

### A calm, modern app
- **Light / Dark / System (Auto)** appearance that follows your OS theme live.
- **Sounds during measurement** — a strip accepted, a patch misread, a session
  finished. Choose a pack or your own files under **Preferences → Sounds**, so
  you can keep your eyes on the chart instead of the screen.
- **Twelve languages, complete** — German, Spanish, French, Italian, Dutch,
  Portuguese, Swedish, Norwegian, Polish, Russian, Japanese and Chinese. Every
  button, message, tooltip and help text, not just the menus.
- **Per-tab onboarding tooltips**, **live command preview**, and a **zoomable
  multi-channel TIFF preview** (RGB, CMYK, extended-gamut).
- **Session restore**, **rotating log file**, and a built-in **update checker**.
- **Self-documenting chart TIFFs** — the exact commands and ChromIQ version are
  stamped into each generated TIFF's margin.

---

## Troubleshooting

<details>
<summary><strong>Windows: "Windows protected your PC" or Defender removed the EXE</strong></summary>

ChromIQ is packaged with PyInstaller and isn't code-signed yet, so unsigned-app
heuristics sometimes flag it. This is common and not specific to ChromIQ.

- **SmartScreen warning:** click **More info → Run anyway**.
- **EXE disappeared after extracting:** open **Windows Security → Virus & threat
  protection → Protection history**, find ChromIQ, and choose **Restore** /
  **Allow on device**.
- **Keeps recurring:** add the ChromIQ folder under **Virus & threat protection →
  Manage settings → Exclusions → Add an exclusion → Folder**.
</details>

<details>
<summary><strong>Linux: <code>xcb-cursor0</code> error on launch</strong></summary>

Install the missing system library:
```bash
sudo apt install libxcb-cursor0     # Debian / Ubuntu
sudo dnf install xcb-util-cursor    # Fedora / RHEL
sudo pacman -S xcb-util-cursor      # Arch
```
</details>

<details>
<summary><strong>ChromIQ can't find ArgyllCMS</strong></summary>

Open **Preferences** → **Auto-detect**. If that fails, click **Browse**, select
the ArgyllCMS `bin` folder, and click **Test binaries**. See
[Installing ArgyllCMS](#installing-argyllcms) for the expected locations.
</details>

<details>
<summary><strong>Windows/Linux: colour looks wrong in the printed chart</strong></summary>

The CUPS/PostScript auto-bypass is macOS-only. On Windows and Linux you must
disable ICM/colour management **in the printer driver** before printing a
profiling target — ChromIQ shows per-brand instructions in the Print tab and
can't do this for you without CUPS.
</details>

---

## Configuration & logs

Settings are stored with `QSettings` (on macOS,
`~/Library/Preferences/ChromIQ.ChromIQ.plist`). The **Preferences** dialog (`⌘,`)
exposes:

| Setting | Default | What it does |
|---------|---------|--------------|
| ArgyllCMS bin path | auto-detected | Folder containing the ArgyllCMS executables |
| Output folder | `~/ChromIQ/` | Where chart/profile projects are saved |
| Restore last active tab on launch | On | Reopen on the last-used tab |
| Restore last session on launch | Off | Reload the last project's files at startup |
| Enable calibration options | Off | Unlock the `printcal → applycal` workflow |
| Use default macOS printer dialog | Off | Use the native print sheet instead of the PostScript pipeline (macOS) |
| Confirm print settings before sending | On | Show a preflight summary before each job |
| Use app theme colours for 3D gamut viewer | On | Tint the gamut mesh with ChromIQ's palette |

Each project lives in its own folder under `~/ChromIQ/<project-name>/`, holding
every generated file for that run (chart, measurements, profile, quality
reports). See [`docs/dev_folder_layout.md`](docs/dev_folder_layout.md) for the
exact layout.

**Logs** (rotating, max 5 MB × 5 backups) record every ArgyllCMS command run —
the fastest way to diagnose a problem:

- **macOS:** `~/Library/Logs/ChromIQ/chromiq.log`
- **Windows:** `%LOCALAPPDATA%\ChromIQ\Logs\chromiq.log`
- **Linux:** `~/.local/state/ChromIQ/logs/chromiq.log`

---

## For developers

> Most users don't need this section — the pre-built downloads above are all you
> need. Continue here only to run or modify the source.

### Run from source

```bash
git clone https://github.com/itsab1989/ChromIQ.git
cd ChromIQ
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Requires **Python 3.12+**. Key dependencies: PyQt6 / PyQt6-WebEngine (≥ 6.11),
Pillow, PyYAML, NumPy, tifffile, imagecodecs, certifi, and (macOS only) pycups
and pyobjc. See [`requirements.txt`](requirements.txt).

### Run the tests

```bash
source .venv/bin/activate
QT_QPA_PLATFORM=offscreen pytest    # ~1–2s, 284 tests
```

### Build a standalone app

```bash
pip install pyinstaller
pyinstaller ChromIQ.spec            # macOS → dist/ChromIQ.app
#           ChromIQWin.spec  (Windows)   ChromIQLinux.spec  (Linux)
```

ArgyllCMS binaries are **not** bundled — install them separately and set the path
in Preferences.

### Refresh the documentation screenshots

The screenshots in `docs/` are generated by a script that drives the real app:

```bash
scripts/make_sample_projects.sh     # build sample data (needs ArgyllCMS)
python scripts/capture_screens.py   # opens the app and captures docs/*.png

# The landing page (docs/index.html) has its own set, framed without the
# frames under the Create Chart preview, and inlined into the page:
CHROMIQ_SHOTS_OUT=/tmp/landing CHROMIQ_SHOTS_CLEAN_PREVIEW=1 \
    python scripts/capture_screens.py
python scripts/splice_landing_shots.py /tmp/landing
```

The chart is built from a fixed seed, so both sets always show the same sheet
and re-running either one reproduces it exactly.

### How the architecture fits together

ChromIQ is a thin GUI over ArgyllCMS; the heavy colour science is all Argyll.

| Directory | Purpose |
|-----------|---------|
| `core/` | Settings, ArgyllCMS detection, the `QProcess` runner, file/project management, logging |
| `data/` | `parameters.yaml` (every CLI flag + tooltip) and the patch-capacity database |
| `ui/` | All Qt widgets — main window, the five tabs, shared TIFF preview, gamut panel, dialogs |
| `workflow/` | Business logic — chart creation, PostScript generation, printing, measuring, profiling |

A few patterns worth knowing:

- **`data/parameters.yaml` drives the UI.** Add a parameter there — with `tool`,
  `flag`, `type`, `default`, `tooltip_title`, `tooltip_body` — and it appears in
  Manual mode automatically, no code changes needed. (`no_space: true` appends
  the value directly to the flag; `expert_only: true` hides it under "Expert".)
- **All file paths go through `Project` / `Run` / `Calibration`** in
  `core/file_manager.py` — never hard-code a filename pattern.
- **`ArgyllRunner` is a singleton** — only one ArgyllCMS process runs at a time.

More developer docs live in [`docs/`](docs/) (folder layout, built-in presets,
the i1Profiler export format, and more), and project-specific guidance is in
[`CLAUDE.md`](CLAUDE.md).

---

## Reporting issues & feedback

You can reach all of these from inside the app — **Preferences** (`⌘,`) →
**Report a Bug…** in the bottom row.

- **Found a bug?** [Open a bug report](https://github.com/itsab1989/ChromIQ/issues/new?template=bug_report.yml).
  Please attach the log file (see [Configuration & logs](#configuration--logs)) —
  it captures every ArgyllCMS command and is usually the fastest path to a fix.
- **Have an idea?** [Open a feature request](https://github.com/itsab1989/ChromIQ/issues/new?template=feature_request.yml).
- **Question or open-ended chat?** Use [Discussions](https://github.com/itsab1989/ChromIQ/discussions).

---

## License

ChromIQ is free software, licensed under the **GNU General Public License v3.0**
(see [`LICENSE`](LICENSE)). You're free to use, study, share, and modify it; if
you distribute a modified version, it must stay free under the same license.

GPLv3 is the right fit because ChromIQ builds on GPL-licensed components (PyQt6
and pycups), so the combined application is, and remains, free and open source.
ArgyllCMS (AGPLv3) is used at arm's length as a separate command-line program and
is not bundled or modified, so its copyleft does not extend to ChromIQ's own code.

Everything ChromIQ *ships* that somebody else wrote — colour profiles, fonts, the
plotly bundle, sounds, the test image — is listed with its terms in
[`THIRD-PARTY-NOTICES.md`](THIRD-PARTY-NOTICES.md).

---

## Acknowledgements

ChromIQ stands on the shoulders of [**ArgyllCMS**](https://www.argyllcms.com/) by
Graeme Gill — an outstanding open-source colour management system that does all
the real colour science here. ChromIQ is purely a friendly front-end to it.

A heartfelt thanks to **soul-traveller** for
[Argyll_Printer_Profiler](https://github.com/soul-traveller/Argyll_Printer_Profiler)
— a mature, in several areas more comprehensive printer-profiling tool. If you
prefer working from proven, pre-made test charts rather than randomly generated
targets, his project ships an excellent curated collection for exactly that.
