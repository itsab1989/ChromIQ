"""Settings / Preferences dialog."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QFontMetrics
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.argyll_detect import find_argyll_bin_path
from core.logger import get_logger
from core.platform_paths import (
    argyll_download_page,
    default_argyll_bin_dir,
    is_macos,
    is_windows,
    native_print_supported,
)
from core.updater import UpdateChecker, WEBSITE_URL, _RELEASES_PAGE
from core.version import APP_VERSION
from ui.styles import SPEC_MAGENTA
from ui.tooltip_button import TooltipButton
from ui.widgets import (
    NoScrollComboBox,
    NoScrollDoubleSpinBox,
    NoScrollSpinBox,
    make_browse_button,
    open_dir_dialog,
)

if TYPE_CHECKING:
    from core.settings import AppSettings

log = get_logger(__name__)

import sys as _sys
from core.i18n import tr


class SettingsDialog(QDialog):
    def __init__(self, settings: "AppSettings", parent: QWidget | None = None,
                 *, margin_combo: "tuple[str, str, str] | None" = None,
                 layout_combo: "tuple[str, str, str] | None" = None) -> None:
        super().__init__(parent)
        self._settings = settings
        # (instrument label, paper name, orientation) to preselect on the
        # Margin Thresholds tab (#80); None → the pulldowns' first entries.
        self._initial_margin_combo = margin_combo
        # (engine instrument, paper code, mode) to preselect on the Chart
        # Layout tab so it opens on the combination the user is editing in
        # Create Chart — otherwise it always resets to i1/A4 and a preset saved
        # under any other combination looks lost (#93). None → first entries.
        self._initial_layout_combo = layout_combo
        self._update_checker: UpdateChecker | None = None
        self.setWindowTitle(tr("ChromIQ Preferences"))
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )
        self._build_ui()
        self._load_settings()
        # Size to the content's natural width with a comfortable floor. The
        # bottom-row buttons render wider on macOS than the headless fallback
        # font suggests, so a fixed width clipped the row once #56 added the
        # "Request a Feature…" button — fit the real sizeHint instead.
        _w = max(1040, self.sizeHint().width())
        self.setMinimumWidth(_w)
        # Open (and floor) ~50% taller than the bare sizeHint: now that each tab
        # scrolls, the natural hint is short, which left a lot of the content
        # hidden behind a scrollbar. A taller floor shows more at a glance.
        _h = int(self.sizeHint().height() * 1.5)
        self.setMinimumHeight(_h)
        self.resize(_w, _h)

    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setSpacing(12)
        outer.setContentsMargins(20, 16, 20, 16)

        # The preferences are split across tabs; the per-combo Margin Thresholds
        # editor lives on its own tab (Knut's request). The credits + button row
        # stay below the tabs so they're shared. All existing group boxes are
        # added to the General page via the local ``layout`` below, unchanged.
        self._tabs = QTabWidget(self)
        outer.addWidget(self._tabs)
        general_page = QWidget()
        layout = QVBoxLayout(general_page)
        layout.setSpacing(12)
        layout.setContentsMargins(12, 12, 12, 12)

        # ---- ArgyllCMS ----
        argyll_grp = QGroupBox(tr("ArgyllCMS Binaries"), self)
        ag = QVBoxLayout(argyll_grp)

        path_row = QHBoxLayout()
        path_row.addWidget(QLabel(tr("Binary path:"), self))
        self._argyll_edit = QLineEdit(self)
        path_row.addWidget(self._argyll_edit, stretch=1)
        browse_btn = make_browse_button(self, tr("Select ArgyllCMS bin folder"), icon="folder")
        browse_btn.clicked.connect(self._browse_argyll)
        path_row.addWidget(browse_btn)
        path_row.addWidget(TooltipButton(
            tr("ArgyllCMS Binary Path"),
            tr("Directory containing targen, printtarg, chartread, and colprof.\n"
               "Default: {path}\n"
               "You can download the latest version from argyllcms.com."
               ).format(path=default_argyll_bin_dir()),
            self,
        ))
        ag.addLayout(path_row)

        btn_row = QHBoxLayout()
        test_btn = QPushButton(tr("Test binaries"), self)
        test_btn.clicked.connect(self._test_argyll)
        detect_btn = QPushButton(tr("Auto-detect"), self)
        detect_btn.clicked.connect(self._auto_detect)
        dl_btn = QPushButton(tr("Download latest ArgyllCMS…"), self)
        dl_btn.clicked.connect(self._open_argyll_download)
        btn_row.addWidget(test_btn)
        btn_row.addWidget(detect_btn)
        btn_row.addWidget(dl_btn)

        if _sys.platform == "win32":
            driver_btn = QPushButton(tr("Install USB Driver…"), self)
            driver_btn.setToolTip(
                tr("Install the WinUSB driver for your colorimeter — "
                "no test-signing mode required, works on x64 and ARM64")
            )
            driver_btn.clicked.connect(self._show_usb_installer)
            btn_row.addWidget(driver_btn)

        btn_row.addStretch()
        ag.addLayout(btn_row)

        self._argyll_status = QLabel("", self)
        self._argyll_status.setWordWrap(True)
        ag.addWidget(self._argyll_status)

        layout.addWidget(argyll_grp)

        # ---- Output folder ----
        # ---- i1Pro chart defaults ----
        from data.patch_db import I1PRO_DEFAULT_PRESETS, I1PRO_PRESET_LABELS
        i1pro_grp = QGroupBox(tr("i1Pro Chart Defaults"), self)
        i1g = QVBoxLayout(i1pro_grp)

        # Row 1: default layout preset
        i1_preset_row = QHBoxLayout()
        i1_preset_row.addWidget(QLabel(tr("Default layout:"), self))
        self._i1pro_preset_combo = NoScrollComboBox(self)
        for key in ("m10_a0.95", "m10_a1.0", "m6_a1.0"):
            self._i1pro_preset_combo.addItem(I1PRO_PRESET_LABELS[key], key)
        self._i1pro_preset_combo.setMinimumWidth(320)
        i1_preset_row.addWidget(self._i1pro_preset_combo)
        i1_preset_row.addStretch()
        i1_preset_row.addWidget(TooltipButton(
            tr("i1Pro Chart Defaults"),
            tr("Sets the default printtarg layout flags (−m / −M margin and −a patch "
            "scale) used by the Create Chart tab whenever the active instrument is "
            "an i1Pro (i1Pro / i1Pro 2 / i1Pro 3).\n\n"
            "  • −m 10  −a 0.95  — recommended. Wider margin protects strip optics "
            "from drifting onto paper at the trailing edge; smaller patches let "
            "~9% more colours fit per sheet.\n"
            "  • −m 10  −a 1.0   — full-size patches with the wider margin.\n"
            "  • −m 6   −a 1.0   — tightest layout. Higher risk of 'not enough "
            "patches read' errors on some printers when the strip's last patch "
            "lands too close to the bare paper edge.\n\n"
            "Other instruments (i1Pro 3 Plus, ColorMunki, SpectroScan) are not "
            "affected by this setting — they keep their own defaults.\n\n"
            "Changes apply to both Guided and Manual mode. A custom margin or "
            "patch-scale you set manually is preserved — switching instruments "
            "only updates the value if it currently matches one of the three "
            "preset values above."),
            self,
            min_width=620,
        ))
        i1g.addLayout(i1_preset_row)

        # Row 2: ChromIQ-style clipping border checkbox
        i1_clip_row = QHBoxLayout()
        self._chromiq_clip_check = QCheckBox(
            tr("Use ChromIQ-style clipping border"), self
        )
        i1_clip_row.addWidget(self._chromiq_clip_check)
        i1_clip_row.addStretch()
        i1_clip_row.addWidget(TooltipButton(
            tr("ChromIQ-Style Clipping Border"),
            tr("Replaces printtarg's plain white i1Pro clip strip with a "
            "ChromIQ-branded version that includes a spectrum accent and "
            "three columns of useful info (chart summary + print reminders, "
            "a fill-in-the-blank form for archival notes, and scanning-table "
            "orientation instructions).\n\n"
            "How it works behind the scenes:\n"
            "  1. printtarg is always told to suppress the native clip strip "
            "(-L), so it can use the whole page width for patches.\n"
            "  2. ChromIQ then shifts the patch block to the right inside the "
            "TIFF, opening up roughly the same amount of space on the LEFT as "
            "printtarg would have reserved natively (~28 mm).\n"
            "  3. The ChromIQ left-strip content is stamped into that new "
            "white area.\n\n"
            "Trade-off: Argyll's small vertical ID line on the RIGHT edge of "
            "the chart gets pushed off the page by the shift, so the right-"
            "margin command/notes stamp is disabled while this is on (those "
            "options are hidden in the Create Chart tab).\n\n"
            "Only takes effect when the chart uses an i1Pro / i1Pro 2 / "
            "i1Pro 3 / i1Pro 3 Plus AND paper is A4 / Letter or larger. "
            "On smaller paper or other instruments the setting is silently "
            "ignored and the chart is generated normally."),
            self,
            min_width=620,
        ))
        i1g.addLayout(i1_clip_row)

        # These are printtarg (old-engine) i1Pro options; they live on the Chart
        # Layout tab now and are greyed when the ChromIQ engine is active, since
        # they have no effect then (Knut #93). Built here (widgets referenced by
        # load/save), re-homed in _build_chart_layout_tab.
        self._i1pro_grp = i1pro_grp

        # ---- Neutral patches ----
        neutral_grp = QGroupBox(tr("Neutral Patches"), self)
        ng = QVBoxLayout(neutral_grp)
        gr_row = QHBoxLayout()
        gr_row.addWidget(QLabel(tr("Grey ramp reference:"), self))
        self._grey_ref_spin = NoScrollSpinBox(self)
        self._grey_ref_spin.setRange(200, 2000)
        self._grey_ref_spin.setSingleStep(10)
        self._grey_ref_spin.setSuffix(" patches")
        self._grey_ref_spin.setMinimumWidth(140)
        gr_row.addWidget(self._grey_ref_spin)
        gr_row.addStretch()
        gr_row.addWidget(TooltipButton(
            tr("Grey Ramp Reference"),
            tr("Controls how many neutral patches (the grey ramp plus the white and "
            "black anchors) ChromIQ adds, relative to the size of the chart.\n\n"
            "It is the patch count at which a chart gets the standard set of "
            "32 grey + 4 white + 4 black. Bigger charts get proportionally more; "
            "smaller charts get fewer.\n\n"
            "  • Lower this number for DENSER neutrals on every chart — better "
            "grey balance and shadow detail, at the cost of fewer colour patches.\n"
            "  • Raise it for SPARSER neutrals — more of the chart spent on "
            "colour, fewer on greys.\n\n"
            "Small charts always keep a sensible minimum — they never receive the "
            "full neutral set, so a tiny target won't be swamped by greys.\n\n"
            "Applies to both Guided and Manual mode (Manual only when the "
            "Auto −g / −e / −B checkboxes are on). Default: 560."),
            self,
            min_width=600,
        ))
        ng.addLayout(gr_row)
        layout.addWidget(neutral_grp)

        # ---- Behaviour ----
        # Options are laid out in two equal-width columns to keep the dialog
        # short; each option (checkbox + optional tooltip) is one grid cell.
        behaviour_grp = QGroupBox(tr("Behaviour"), self)
        bh = QGridLayout(behaviour_grp)
        bh.setHorizontalSpacing(100)
        bh.setColumnStretch(0, 1)
        bh.setColumnStretch(1, 1)

        def _bh_cell(check: QCheckBox, tooltip: TooltipButton | None = None) -> QWidget:
            cell = QWidget(self)
            row = QHBoxLayout(cell)
            row.setContentsMargins(0, 0, 0, 0)
            row.addWidget(check)
            row.addStretch()
            if tooltip is not None:
                row.addWidget(tooltip)
            return cell

        self._restore_tab_check = QCheckBox(
            tr("Restore last active tab on launch"), self
        )
        restore_tab_tip = TooltipButton(
            tr("Restore Last Active Tab on Launch"),
            tr("ChromIQ is organised as five numbered steps along the top of the "
            "window:\n\n"
            "  1. Create Chart\n"
            "  2. Print Chart\n"
            "  3. Measure\n"
            "  4. Build Profile\n"
            "  5. Check & Refine\n\n"
            "When this option is ON, ChromIQ reopens on whichever step you were "
            "looking at when you last closed the app. This is handy if you tend to "
            "work in several sittings — for example, you print a chart, quit, and "
            "later come back to measure it: the app opens straight on the Measure "
            "step instead of sending you back to the beginning.\n\n"
            "When OFF, ChromIQ always starts on step 1 (Create Chart).\n\n"
            "This only remembers which step was open — it does not reload any of "
            "your files. To have your files come back too, also turn on "
            "\"Restore last session on launch\"."),
            self,
            min_width=600,
        )

        self._restore_session_check = QCheckBox(
            tr("Restore last session on launch"), self
        )
        restore_session_tip = TooltipButton(
            tr("Restore Last Session on Launch"),
            tr("When this option is ON, ChromIQ remembers the files you were working "
            "with and reloads them automatically the next time you start the app, "
            "so you can carry on exactly where you left off.\n\n"
            "What gets restored:\n\n"
            "  • The chart / target you created (its name and the .ti1 file)\n"
            "  • The printable chart images (TIFF files) in the working folder\n"
            "  • Your measurement data (the .ti3 file)\n"
            "  • The ICC profile you built (.icc)\n"
            "  • The calibration measurements, if calibration options are enabled\n\n"
            "These files are simply re-opened from where they are saved on disk — "
            "nothing is copied, changed, or re-measured. If you have since moved or "
            "deleted a file, ChromIQ just skips that one and loads the rest.\n\n"
            "When OFF, ChromIQ starts with an empty session every time and you load "
            "the files you need by hand. This is the default — turn the option on if "
            "you usually continue the same job across several sessions."),
            self,
            min_width=560,
        )

        self._themed_colors_check = QCheckBox(
            tr("Use app theme colors for 3D gamut viewer"), self
        )
        themed_colors_tip = TooltipButton(
            tr("Use App Theme Colours for 3D Gamut Viewer"),
            tr("On the Check & Refine step, ChromIQ can show a rotatable 3D model of "
            "your printer and paper's colour range (its \"gamut\") — the full set of "
            "colours that combination can actually reproduce.\n\n"
            "When this option is ON, the colours of that 3D model are recoloured to "
            "match ChromIQ's own accent palette, and the very brightest points are "
            "toned down slightly so they don't wash out to pure white. The result "
            "blends in neatly with the app's light or dark theme.\n\n"
            "When OFF, the model keeps the viewer's natural colours, where each point "
            "is drawn roughly in the colour it represents.\n\n"
            "This setting is purely cosmetic. It changes only how the 3D preview "
            "looks — it has no effect whatsoever on your measurements or on the ICC "
            "profile ChromIQ builds."),
            self,
            min_width=560,
        )

        self._native_files_check = QCheckBox(
            tr("Use the operating system's file browser"), self
        )
        native_files_tip = TooltipButton(
            tr("Use the Operating System's File Browser"),
            tr("Whenever ChromIQ needs you to pick a file or folder — a chart "
            "image, a measurement, a profile, a place to save something — it opens "
            "a file browser. This setting chooses WHICH browser you get.\n\n"
            "When OFF (the default), ChromIQ uses its own built-in file browser. "
            "It matches the app's light/dark theme, adds handy shortcuts down the "
            "left side that jump straight to the folders for the job at hand, and — "
            "when you're choosing an image — shows a live preview of the "
            "highlighted picture on the right.\n\n"
            "When ON, ChromIQ instead opens the SAME file browser you already know "
            "from the rest of your computer — Windows File Explorer's Open window "
            "on Windows, Finder's on a Mac.\n\n"
            "Why you might want to turn this on:\n\n"
            "  • Speed. On Windows the built-in browser can be slow to fill in a "
            "folder — you may see nothing, or just one item, for several seconds "
            "before the rest appear. The operating system's own browser shows "
            "everything instantly.\n"
            "  • Familiarity. It's the exact window you use everywhere else, with "
            "your usual Quick Access / favourites and sorting (for example "
            "\"most recent first\").\n\n"
            "The trade-off:\n\n"
            "  • ChromIQ's job-specific shortcuts on the left and its built-in "
            "image preview are part of ITS browser, so they aren't shown in the "
            "operating system's one — that window has its own Quick Access list "
            "and its own preview pane instead (in Explorer, turn on the Preview "
            "pane from the View menu).\n\n"
            "Nothing else changes: the same files are offered either way, and you "
            "can switch back at any time. This only affects how the browser "
            "windows look — not your charts, measurements, or profiles."),
            self,
            min_width=620,
        )

        self._update_notify_check = QCheckBox(
            tr("Check for updates on startup"), self
        )
        update_notify_tip = TooltipButton(
            tr("Check for Updates on Startup"),
            tr("When this is on, ChromIQ quietly checks for a newer version each "
            "time it starts and, if one is available, shows a small popup that "
            "links to the download page.\n\n"
            "It never downloads or installs anything on its own — it only lets "
            "you know. You can also turn this off straight from that popup (the "
            "\"Don't remind me of new available versions\" box), and turn it back "
            "on again here."),
            self,
            min_width=560,
        )

        self._hide_log_check = QCheckBox(
            tr("Hide the log panel on every tab"), self)
        hide_log_tip = TooltipButton(
            tr("Hide the Log Panel"),
            tr("Removes the box at the bottom of each tab that fills with "
               "text while ChromIQ works — the one headed “Output will appear "
               "here…” before anything has run.\n\n"
               "It is one switch for the whole app, not one per tab, so the "
               "layout stays consistent wherever you are. Turning it back on "
               "brings every panel back exactly as it was; nothing is lost "
               "while it is hidden, because ChromIQ keeps writing to its log "
               "file either way.\n\n"
               "WHY YOU MIGHT WANT IT ON\n"
               "On a small screen the log takes room that the chart preview, "
               "the patch list or the profile settings could use. If your "
               "measurements normally go smoothly, you may never read it — and "
               "the tab is calmer without a panel of technical output on it.\n\n"
               "WHY YOU MIGHT WANT IT OFF\n"
               "The log is where a failure explains itself. When a chart will "
               "not generate, an instrument will not answer or a profile build "
               "stops, the reason is almost always in that panel — and it is "
               "the first thing worth reading, and the first thing worth "
               "sending if you report a problem.\n\n"
               "Whichever you choose, the full log is always written to disk. "
               "Hiding the panel only changes what is on screen.\n\n"
               "One tab has no log panel to hide: Print Chart does its work "
               "through the system print dialog and has nothing of its own to "
               "report.\n\n"
               "Default: off (the log is shown)."),
            self,
            min_width=560,
        )

        self._show_location_check = QCheckBox(
            tr("Show the location being edited"), self)
        show_location_tip = TooltipButton(
            tr("Show the Location Being Edited"),
            tr("Keeps the line of text under the Profile-run bar that spells "
               "out which folder ChromIQ is working in right now — for "
               "example “ChromIQ/My-Printer/runs/run2/”.\n\n"
               "It follows the “Profile run” and “Run type” boxes above it, so "
               "before you create, print or measure anything you can see "
               "exactly where those files will be read from and written to.\n\n"
               "WHY YOU MIGHT WANT IT ON\n"
               "As soon as a project has more than one run — and most do, once "
               "you make a second profile for the same printer — this line is "
               "the quickest way to check you are working where you think you "
               "are. It is also the first thing worth looking at if a file "
               "ever turns up somewhere unexpected.\n\n"
               "WHY YOU MIGHT WANT IT OFF\n"
               "If you keep one project with one run, it answers a question "
               "you never ask, and the interface is a little simpler without "
               "it. Nothing changes except that the line is hidden: ChromIQ "
               "still works in exactly the same folders."),
            self,
            min_width=600,
        )

        self._cal_mode_check = QCheckBox(tr("Enable calibration options"), self)
        cal_tip = TooltipButton(
            tr("Enable Calibration Options"),
            tr("Unlocks the full printer calibration workflow (printcal / applycal).\n\n"
            "Most users do NOT need this — consumer and prosumer inkjet printers "
            "typically produce better results from a direct profiling run without "
            "any hardware calibration step.\n\n"
            "Enable this only if you know your printer requires linearisation curves "
            "before profiling, or if you are an advanced user following an explicit "
            "ArgyllCMS calibration guide.\n\n"
            "When active, the tabs switch to their expert layout: the GUIDED "
            "module is put away, and Create Chart and Measure open on MANUAL "
            "with every setting visible. (On a verification run, Create Chart "
            "still offers both MANUAL and FROM PROFILE GAMUT, and opens on "
            "FROM PROFILE GAMUT — the recommended check.) “Calibration” is "
            "added to the “Run type” list in the bar above the tabs, and tab "
            "4 becomes “Calibration & Profiling”: on a Calibration run it "
            "shows the Create Calibration File module, on a profiling run "
            "the Build Profile and Apply Calibration modules.\n\n"
            "Your projects are not changed by switching this on or off — a "
            "calibration you have already made stays in the project's “cal” "
            "folder either way, and switching this back on makes it available "
            "again exactly as you left it."),
            self,
            min_width=620,
        )

        self._chromiq_refine_check = QCheckBox(
            tr("ChromIQ-style refinement process"), self
        )
        refine_tip = TooltipButton(
            tr("ChromIQ-style refinement process"),
            tr("Builds a more accurate profile by REUSING the measurements you "
            "already made for an earlier profile, instead of throwing them away.\n\n"
            "Normally, every profiling run starts from scratch: you print a chart, "
            "measure it, and build a profile from only those patches. If you later "
            "make a second, refined chart for the same printer and paper, the "
            "measurements from the first run are not used again.\n\n"
            "With this option ON, ChromIQ can carry those earlier measurements "
            "forward. Here is the whole journey, step by step:\n\n"
            "  1. In Create Chart, you tick \"Refinement profile\" and pick the ICC "
            "profile from your earlier run. ChromIQ quietly keeps a copy of that "
            "profile's measurement data (a \"pre_…\" file) inside the working folder, "
            "so it is not deleted when the new chart is generated.\n\n"
            "  2. You print and measure the new chart as usual. In the Measure tab a "
            "new option appears: \"Also use measurement data from the pre-conditioning "
            "profile\". It only shows up when such saved data is actually present.\n\n"
            "  3. When you build the profile, ChromIQ combines the new measurements "
            "with the saved earlier ones and builds from the larger, combined set. "
            "More measured colours generally means a more accurate profile.\n\n"
            "Your freshly measured file is never altered — the combining happens on a "
            "separate copy only at build time, so you can re-measure or refine "
            "individual strips in Check & Refine exactly as before. The guided "
            "Check & Refine analysis still looks only at the strips you physically "
            "printed, so it will never ask you to re-measure a patch that came from "
            "the earlier run.\n\n"
            "When this option is OFF, ChromIQ behaves exactly as it always has — "
            "nothing in your normal workflow changes. Leave it off unless you "
            "specifically want to reuse measurements across refinement runs."),
            self,
            min_width=680,
        )

        self._averaging_check = QCheckBox(
            tr("Enable measurement averaging"), self
        )
        averaging_tip = TooltipButton(
            tr("Enable Measurement Averaging"),
            tr("Lets you read the SAME printed chart more than once and combine the "
            "readings, to even out the small random errors every measuring device "
            "makes. The more times you read a chart, the closer the averaged "
            "result gets to its \"true\" colour — which can make for a slightly "
            "more accurate profile, especially with budget instruments or tricky "
            "papers.\n\n"
            "You do NOT print a new chart. You measure the one already in front of "
            "you a second (or third, or fourth) time. Because the printed colours "
            "never change, only the tiny reading-to-reading wobble of the "
            "instrument does, averaging those reads cancels most of that wobble "
            "out.\n\n"
            "Here is the whole journey, step by step:\n\n"
            "  1. You measure your chart as usual in the Measure tab.\n\n"
            "  2. When the read finishes, a new completion window appears. As well "
            "as continuing to Build Profile, it offers \"Measure again\" — put the "
            "very same chart back on the table and read it once more.\n\n"
            "  3. You can repeat this as many times as you like. ChromIQ keeps each "
            "read safely side by side in the working folder (named …_read1, "
            "…_read2, and so on).\n\n"
            "  4. Once you have two or more reads, the window lets you either build "
            "from just the last read, or average all of the reads together and "
            "build from that combined result (saved as …_average).\n\n"
            "Mean vs. Median: averaging normally uses the plain mean (the ordinary "
            "average). The window also offers Median, which ignores the odd "
            "stray reading and only behaves differently once you have three or "
            "more reads — handy if one read was disturbed (a bump, a smudge) and "
            "you don't want it dragging the result.\n\n"
            "When this option is OFF (the default), ChromIQ behaves exactly as it "
            "always has: a finished measurement takes you straight on to Build "
            "Profile with no extra window and no extra files. Turn it on only if "
            "you want the option to read charts repeatedly for extra precision.\n\n"
            "Tip: two reads already remove most of the random noise; three or four "
            "give diminishing returns. There is no benefit to averaging reads of "
            "DIFFERENT charts — this is only for re-reading one and the same chart.\n\n"
            "With thanks to Alan Goldhammer, who suggested this feature."),
            self,
            min_width=660,
        )

        self._profile_engine_check = QCheckBox(
            tr("ChromIQ profile engine (beta)"), self
        )
        engine_tip = TooltipButton(
            tr("ChromIQ Profile Engine (beta)"),
            tr("A profile builder that lives inside ChromIQ itself.\n\n"
            "While this option is ON, clicking Build Profile runs the "
            "ChromIQ engine instead of Argyll colprof — same tab, same "
            "buttons, same options, nothing new to learn. Turn the option "
            "OFF and every profile is built by colprof again, exactly as "
            "before.\n\n"
            "Why would you want it? One reason above all: printers with "
            "EXTRA INKS. colprof can build profiles for RGB and CMYK "
            "printers, but not for a CMYK printer with orange, green or "
            "violet channels. The ChromIQ engine can. Together with the "
            "multi-ink charts from Create Chart this closes the loop "
            "entirely inside ChromIQ: print a multi-ink chart, measure "
            "it, build a working profile.\n\n"
            "What to expect:\n\n"
            "  • The engine understands every option on the Build Profile "
            "tab — quality levels, gamut sources, rendering intents, "
            "spectral illuminants and observers, paper-whitener "
            "compensation, ICC attributes and all the expert switches.\n\n"
            "  • Its colour rendering is computed by ChromIQ's own port "
            "of Argyll's gamut-mapping algorithm. In our own limited "
            "testing the results measure within colprof's normal "
            "build-to-build variation — but it has not been tested "
            "extensively yet, so treat that as promising rather than "
            "proven.\n\n"
            "  • If a build needs something only colprof has (for example "
            "a hand-typed extra flag the engine doesn't recognise), that "
            "build is quietly handed to colprof and the log tells you "
            "why.\n\n"
            "  • Your measurement files are never changed by either "
            "engine.\n\n"
            "Turning the option on shows this information once more and "
            "asks you to confirm. It is a new beta and has not been "
            "extensively tested, so use it at your own risk and verify "
            "every profile with a test print before you rely on it."),
            self,
            min_width=680,
        )
        self._profile_engine_check.clicked.connect(
            self._on_profile_engine_clicked)

        self._gammap_mode_combo = NoScrollComboBox(self)
        self._gammap_mode_combo.addItem(tr("Fast"), "fast")
        self._gammap_mode_combo.addItem(tr("Bit-exact"), "argyll")
        self._gammap_mode_combo.addItem(tr("Maximum accuracy"), "accurate")
        self._gammap_mode_combo.setSizeAdjustPolicy(
            NoScrollComboBox.SizeAdjustPolicy.AdjustToContents)
        gammap_mode_tip = TooltipButton(
            tr("Accuracy"),
            tr("This chooses how much work the profile engine puts into "
            "colour accuracy when it builds your profile. All three "
            "choices read the same measurement, understand the same "
            "options and give you a correct, ready-to-use profile for any "
            "printer ChromIQ supports, including 6-ink and beyond.\n\n"
            "  • Fast (built-in) — ChromIQ's own, careful re-creation of "
            "Argyll's gamut-mapping maths, running right inside the app. It "
            "finishes in a few seconds and, in our testing, is visually "
            "indistinguishable from the exact result. This is the best "
            "choice for everyday use.\n\n"
            "  • Bit-exact (Argyll's engine) — gives you ArgyllCMS's real "
            "colour rendering, not a re-creation of it:\n"
            "       – For a normal RGB or CMYK printer, ChromIQ builds the "
            "profile with ArgyllCMS colprof itself, so it is identical to "
            "what Argyll would produce on its own.\n"
            "       – For a 6-ink or larger printer — which Argyll's own "
            "profiler cannot build at all — ChromIQ builds it with its "
            "engine plus Argyll's actual gamut-mapping code (bundled with "
            "the app), so the colour mapping is Argyll's real algorithm "
            "there too.\n"
            "     It takes a little longer — expect up to a minute or two, "
            "and somewhat more for multi-ink printers.\n\n"
            "  • Maximum accuracy — the bit-exact rendering plus everything "
            "ChromIQ can do to squeeze the most out of your measurement:\n"
            "       – the paper's white and black are averaged over "
            "duplicate patches instead of trusting a single reading,\n"
            "       – the model's smoothing is tuned by testing it against "
            "held-back patches from your own chart,\n"
            "       – patches that look like misreads are detected, "
            "down-weighted and reported so you can remeasure them,\n"
            "       – extra inks (orange, green, violet …) are anchored on "
            "their measured colour instead of an assumed one,\n"
            "       – colours the printer cannot reach lose saturation "
            "instead of drifting to a different colour family, and dark "
            "shadows keep their depth when the total ink limit steps in.\n"
            "     Expect the build to take several minutes longer, "
            "especially at the higher quality settings.\n\n"
            "Which should you pick? Fast for everyday work. Bit-exact when "
            "you want Argyll's exact rendering. Maximum accuracy when the "
            "last bit of measured accuracy matters more than build time — "
            "for example fine-art printing on an expensive paper. Whatever "
            "you choose, verify the profile with a test print before you "
            "rely on it.\n\n"
            "Building a profile is a one-time step per paper and printer, "
            "so even the slowest choice only costs you those extra minutes "
            "once."),
            self,
            min_width=680,
        )
        self._gammap_mode_cell = gammap_mode_cell = QWidget(self)
        _gm_row = QHBoxLayout(gammap_mode_cell)
        _gm_row.setContentsMargins(0, 0, 0, 0)
        _gm_row.addWidget(QLabel(tr("Accuracy"), self))
        _gm_row.addWidget(self._gammap_mode_combo)
        _gm_row.addStretch()
        _gm_row.addWidget(gammap_mode_tip)
        # Gamut mapping only applies to the profile engine, so the picker is
        # shown only while the engine is enabled.
        self._profile_engine_check.toggled.connect(
            self._gammap_mode_cell.setVisible)

        # Both live on their own "Beta features" tab.
        self._beta_page = QWidget(self)
        _beta = QVBoxLayout(self._beta_page)
        _beta.setContentsMargins(16, 16, 16, 16)
        _beta.setSpacing(12)
        _beta_intro = QLabel(tr(
            "Experimental features — enabled at your own risk. Verify every "
            "result before you rely on it."), self)
        _beta_intro.setWordWrap(True)
        _beta.addWidget(_beta_intro)
        _eng_row = QHBoxLayout()
        _eng_row.addWidget(self._profile_engine_check)
        _eng_row.addStretch()
        _eng_row.addWidget(engine_tip)
        _beta.addLayout(_eng_row)
        _beta.addWidget(self._gammap_mode_cell)

        # Everything that used to follow here on the Beta tab moved to
        # Preferences -> Measurement (Knut + Sebastian, 2026-08-13: the
        # chart-reading engine and its companions have outgrown Beta; only
        # the profile engine is still experimental). The rows are built
        # here, in their original order, into a container the Measurement
        # tab places FIRST -- above its pace introduction.
        self._measure_engine_block = QWidget(self)
        _meas = QVBoxLayout(self._measure_engine_block)
        _meas.setContentsMargins(0, 0, 0, 0)
        # Tighter than the page's 12: seven rows moved in above the pace
        # section, and the tab should still fit a normal window height.
        _meas.setSpacing(6)

        # Chart-reading engine (#126) — Measure tab beta. A checkbox, mirroring
        # the profile-engine toggle above it (Knut): ON = ChromIQ engine.
        self._chartread_engine_check = QCheckBox(
            tr("ChromIQ chart-reading engine"), self)
        chartread_engine_tip = TooltipButton(
            tr("ChromIQ Chart-Reading Engine"),
            tr("This box changes how ChromIQ reads your printed chart in the "
            "Measure tab.\n\n"
            "When it is ON — the default — ChromIQ reads charts with its "
            "own engine. Switch it OFF and ChromIQ measures with Argyll's "
            "own chartread program instead, exactly the way plain ArgyllCMS "
            "works; the measured numbers are the same either way.\n\n"
            "When it is ON, ChromIQ uses its own chart-reading engine. The "
            "engine is built from the very same ArgyllCMS source code and "
            "talks to your instrument through Argyll's own, unmodified "
            "drivers — so the measurements themselves are identical, down to "
            "the numbers in your file. What the engine adds is everything "
            "around the measuring:\n\n"
            "  • Your readings are saved to disk after every single strip. "
            "If the instrument loses its connection, the app closes, or the "
            "power goes out, you lose at most the one strip you were reading "
            "— never the whole session.\n\n"
            "  • You can click any strip in the chart preview to jump "
            "straight to it — handy when you want to measure one strip again, "
            "or when Check & Refine has flagged a few strips as worth a "
            "second pass.\n\n"
            "  • After each swipe, the preview fills in what the instrument "
            "actually saw, patch by patch, split diagonally against what the "
            "chart expected — so a smudged or mixed-up row jumps out at you "
            "immediately, instead of quietly spoiling the profile.\n\n"
            "  • On charts whose patches are printed in a fixed order (not "
            "shuffled), the engine checks — wherever that is mathematically "
            "possible — that you really swiped the row it expected, and warns "
            "you on the spot. Regular chartread trusts you silently there.\n\n"
            "The measurement file has exactly the same format either way, "
            "and you can switch this box on or off between sessions freely "
            "— even resume a measurement started the other way.\n\n"
            "If the engine is missing on your computer, or a mode needs "
            "something it does not cover yet (patch-by-patch reading, XY "
            "tables), ChromIQ simply falls back to the normal chartread for "
            "that run and notes it in the log.\n\n"
            "─────────────────────────────────\n"
            "What each one gives you\n"
            "─────────────────────────────────\n\n"
            "Only with the ChromIQ engine:\n"
            "  • your readings are saved after every strip\n"
            "  • click a strip in the preview to jump to it\n"
            "  • the preview fills in each patch as you read\n"
            "  • a wrong-strip check on fixed-order charts\n"
            "  • the reading time for every strip\n"
            "  • a warning when a strip was read too fast, with advice\n"
            "  • the offer to read a hurried strip again\n"
            "  • per-strip figures in the end-of-measurement summary\n"
            "  • only the sounds you chose are heard\n\n"
            "The same either way:\n"
            "  • the measured values themselves, down to the numbers\n"
            "  • ArgyllCMS's own “Slow Down!” cue\n"
            "  • the right sound for the right kind of failure\n"
            "  • the strip-failure window and its advice\n"
            "  • the total measuring time in the summary\n\n"
            "Why reading pace needs the engine: ArgyllCMS tells our own code "
            "the exact moment the instrument fires, so a swipe can be timed. "
            "The separate chartread program only prints that it is ready and "
            "then that the strip was read, and the time between those two "
            "includes you picking the instrument up and lining it up — so it "
            "cannot be used to judge how fast you swiped.\n\n"
            "The last row has the same cause: the beeps built into ArgyllCMS "
            "are silenced in the engine, because it runs inside ChromIQ. The "
            "separate chartread program beeps on its own and offers no way to "
            "turn that off, so with it you may hear both its beeps and your "
            "chosen sounds.\n\nDefault: on"),
            self,
            min_width=680,
        )
        _cr_row = QHBoxLayout()
        _cr_row.addWidget(self._chartread_engine_check)
        _cr_row.addStretch()
        _cr_row.addWidget(chartread_engine_tip)
        _meas.addLayout(_cr_row)

        # XY / chart-reader engine support (opt-in). Sits right under the engine
        # toggle. Off by default → these niche instruments use stock chartread.
        self._engine_all_modes_check = QCheckBox(
            tr("Also drive XY tables and chart readers with the engine (beta)"),
            self)
        engine_all_modes_tip = TooltipButton(
            tr("Engine for XY tables & chart readers (beta)"),
            tr("Two rare kinds of instrument read a whole sheet at once instead "
            "of one strip at a time: motorised XY tables (the "
            "GretagMacbeth SpectroScan) and autonomous chart readers "
            "(the X-Rite i1iSis and DTP70).\n\n"
            "When this box is OFF (the default), ChromIQ measures these with "
            "Argyll's own chartread — the long-proven path. Everything works; "
            "you just don't get the engine's live preview for them.\n\n"
            "When it is ON, the ChromIQ engine drives them too, so you get the "
            "same extras as strip and patch reading: the expected-vs-measured "
            "preview fills in as sheets are read, and the result is saved after "
            "every sheet.\n\n"
            "This path is new and has NOT yet been tested on real "
            "SpectroScan or i1iSis hardware — so it is off by default. If "
            "you own one of these and want to help, turn it on and check the "
            "result; if anything looks wrong, switch it back off and the "
            "measurement runs the classic way. Needs the chart-reading engine "
            "above to be on.\n\nDefault: off"),
            self,
            min_width=680,
        )
        _xy_row = QHBoxLayout()
        _xy_row.addWidget(self._engine_all_modes_check)
        _xy_row.addStretch()
        _xy_row.addWidget(engine_all_modes_tip)
        _meas.addLayout(_xy_row)

        # Patch-reading error limit (#126, Knut): the ΔE at which a just-measured
        # patch gets the red warning outline in the live split-patch preview.
        self._patch_warn_spin = NoScrollDoubleSpinBox(self)
        self._patch_warn_spin.setRange(1.0, 100.0)
        self._patch_warn_spin.setSingleStep(1.0)
        self._patch_warn_spin.setDecimals(1)
        self._patch_warn_spin.setSuffix(" ΔE")
        self._patch_warn_spin.setFixedWidth(110)
        _pw_row = QHBoxLayout()
        _pw_row.addWidget(QLabel(tr("Flag a patch when its colour error reaches:"), self))
        _pw_row.addWidget(self._patch_warn_spin)
        _pw_row.addStretch()
        # Knut's option (c) of 2026-07-27: the strip comparison becomes a
        # switch, on by default, and it now governs BOTH reading modes — which
        # is what made them disagree so sharply before.
        self._patch_fence_check = QCheckBox(
            tr("When reading strips, only flag a patch that also stands out "
               "from its own strip"), self)
        self._patch_fence_check.setToolTip(tr(
            "On (the default): when you read strips, a patch is flagged only "
            "when it is past the limit above AND unusual compared with the "
            "other patches of its strip. This is what keeps a good print from "
            "being flagged almost everywhere, because the chart's design "
            "colours are sRGB and a printer does not reproduce them.\n\n"
            "Off: the limit means exactly what it says, and every patch past it "
            "is flagged — useful when you are checking a chart you already "
            "suspect is wrong, and expect most of it to be flagged.\n\n"
            "It applies to strip reading only, because it is the only mode "
            "where there is a strip to compare against. Patch by patch, the "
            "limit above is always the whole rule."))
        _pw_row.addWidget(TooltipButton(
            tr("Patch-reading error limit"),
            tr("While you measure with the ChromIQ chart-reading engine, each "
            "patch you read is shown split against the colour the chart was "
            "designed to have. ChromIQ draws a bright red outline around a patch "
            "that looks like a likely misread — a smudge, a skipped row, the "
            "strip swiped the wrong way — so it jumps out at you straight away.\n\n"
            "Important: the design colour is an sRGB value, and a printer does "
            "NOT reproduce sRGB — so vivid colours (a deep red, a saturated "
            "green) can legitimately measure 30–40 ΔE away on a perfectly good "
            "print. That is expected, not a mistake. If ChromIQ flagged every "
            "patch past a fixed number, it would light up half of a normal "
            "chart in red.\n\n"
            "So when you read STRIPS, a patch is flagged only when it is BOTH "
            "past this limit AND clearly stands out from the other patches in "
            "its own strip. A real misread spikes far above its neighbours; the "
            "normal, even difference between print and sRGB does not — so it "
            "stays quiet. In other words: a red outline means “this one patch "
            "looks wrong compared to the rest of the strip”, not simply “this "
            "patch differs from sRGB”.\n\n"
            "PATCH-BY-PATCH MODE IS DIFFERENT, ON PURPOSE\n"
            "Reading one patch at a time there is no strip to compare against — "
            "the patch you have just read is the only one that has arrived. So "
            "that mode uses this limit on its own, and flags every patch past "
            "it. Expect it to outline MORE patches than strip reading does on "
            "the very same chart, vivid colours among them: that is the honest "
            "consequence of having no neighbours to compare with, not a "
            "disagreement between the two modes about your print. The "
            "patch-by-patch help text explains it there as well.\n\n"
            "This limit is the floor beneath which a patch is never flagged. "
            "Lower it if you want to be warned about smaller odd-looking "
            "patches; raise it if you only want the most extreme ones. It "
            "changes only the red outline in the preview — never your "
            "measurements.\n\n"
            "Default: 50 ΔE"),
            self))
        _meas.addLayout(_pw_row)
        _fence_row = QHBoxLayout()
        _fence_row.addWidget(self._patch_fence_check)
        _fence_row.addStretch()
        _fence_row.addWidget(TooltipButton(
            tr("Only flag a patch that stands out from its own strip"),
            tr("While you read strips, every patch is compared with the "
            "colour the chart was designed to have — and vivid design "
            "colours legitimately measure far away on a perfectly good "
            "print, because a printer does not reproduce sRGB. Flagging "
            "every patch past the limit above would light up half of a "
            "healthy chart in red.\n\n"
            "On (the default): a patch gets the red outline only when it is "
            "past the limit above AND clearly stands out from the other "
            "patches of its own strip. A real misread — a smudge, a doubled "
            "patch, a swipe that drifted a row — spikes far above its "
            "neighbours, so it is caught; the normal, even difference "
            "between print and design stays quiet.\n\n"
            "Off: the limit above means exactly what it says, and every "
            "patch past it is flagged. Choose this when you already suspect "
            "the chart is wrong and want to see everything the limit "
            "catches.\n\n"
            "This applies to strip reading only — reading patch by patch "
            "there is no strip to compare against, so there the limit above "
            "is always the whole rule.\n\n"
            "Default: on"),
            self))
        _meas.addLayout(_fence_row)

        # Automatic calibration retries (#126, mavtop): how many times a failed
        # instrument calibration is retried before giving up.
        self._cal_retries_spin = NoScrollSpinBox(self)
        self._cal_retries_spin.setRange(0, 20)
        self._cal_retries_spin.setFixedWidth(110)
        _car_row = QHBoxLayout()
        _car_row.addWidget(QLabel(
            tr("Retry a failed calibration up to:"), self))
        _car_row.addWidget(self._cal_retries_spin)
        _car_row.addWidget(QLabel(tr("times"), self))
        _car_row.addStretch()
        _car_row.addWidget(TooltipButton(
            tr("Automatic calibration retries"),
            tr("Before you can measure a chart, your instrument calibrates "
            "itself — for most instruments that means a quick reading of the "
            "white tile on its base or dock. Usually it works first time and "
            "you never think about it.\n\n"
            "Sometimes, though, a calibration fails for a reason that clears "
            "itself moments later. This is especially common with older "
            "instruments like the original i1Pro: striking its lamp draws a "
            "burst of power, and on a lamp that has aged, or through a USB port "
            "that can't quite supply that burst, the very first attempt can "
            "read poorly — while the next attempt, with the lamp already warm, "
            "succeeds.\n\n"
            "Rather than stopping at the first failure, ChromIQ can simply try "
            "the calibration again a few times, pausing a couple of seconds "
            "between attempts so the instrument can settle. You don't need to "
            "do anything while it retries — just leave the instrument where it "
            "is. Each attempt is noted in the log.\n\n"
            "This setting is how many extra attempts it makes before giving "
            "up. For example, 3 means up to four tries in total. If your "
            "instrument's lamp needs several strikes to burn in, raise this — "
            "some old i1Pro units are happy at 10. If all the attempts fail, "
            "ChromIQ reports the problem and, where it can, falls back to "
            "ArgyllCMS's own reader so you can still measure.\n\n"
            "Set it to 0 to turn automatic retries off entirely. This only "
            "affects the ChromIQ chart-reading engine.\n\n"
            "Default: 3 (four attempts in total)"),
            self,
            min_width=620))
        _meas.addLayout(_car_row)

        # Faster instrument connection: skip Argyll's slow serial-port probe.
        self._fast_connect_check = QCheckBox(
            tr("Faster instrument connection"), self)
        _fc_row = QHBoxLayout()
        _fc_row.addWidget(self._fast_connect_check)
        _fc_row.addStretch()
        _fc_row.addWidget(TooltipButton(
            tr("Faster instrument connection"),
            tr("On some computers there's an annoying pause — often around ten "
            "seconds — between pressing Start and your instrument asking to be "
            "calibrated. This option removes that pause.\n\n"
            "Why does the pause happen? Before it finds your USB instrument "
            "(like an i1Pro or ColorMunki), the measuring engine looks at every "
            "serial port on the computer and, for each one, spends a couple of "
            "seconds trying to talk to it in case an old serial instrument is "
            "attached. On a Mac there's almost always an invisible “Bluetooth” "
            "serial port sitting there, and on Linux there can be Bluetooth "
            "ports too — so those few seconds are wasted on ports that are not "
            "instruments at all. (A Windows PC usually doesn't have these, which "
            "is why it already feels instant.)\n\n"
            "With this turned ON (the recommended default), ChromIQ tells the "
            "engine to skip those known-empty ports, so it goes straight to your "
            "USB instrument — the calibration prompt appears almost immediately.\n\n"
            "Is it safe? For almost every computer, yes. Only ports that are "
            "never real instruments are skipped (Bluetooth and debug ports). "
            "A genuine serial instrument connected through a USB-to-serial "
            "adapter is always kept, and USB instruments are never affected. "
            "Nothing about your measurements changes, only how quickly the "
            "connection is made.\n\n"
            "When to turn it OFF: if your instrument is not found at all. On "
            "some computers, older Macs in particular, this shortcut is what "
            "stops it being seen, and the same instrument that works on a "
            "newer machine reports “No instrument found” on the older one, "
            "in every mode: strip reading, patch by patch, and Read Single "
            "Patches. Switching this off is then the whole fix. It costs a "
            "pause of a few seconds before the calibration prompt appears, "
            "and nothing else. The no-instrument window offers the same "
            "switch, so you do not have to come here mid-measurement.\n\n"
            "Default: on"),
            self))
        _meas.addLayout(_fc_row)

        # Misalignment safety net (#50, opt-in): warn when a strip fits
        # dramatically better shifted by a patch (a likely one-off misread).
        self._safenet_check = QCheckBox(
            tr("Warn me if a strip looks misaligned"), self)
        _sn_row = QHBoxLayout()
        _sn_row.addWidget(self._safenet_check)
        _sn_row.addStretch()
        _sn_row.addWidget(TooltipButton(
            tr("Misalignment safety net"),
            tr("A safety net for a rare but annoying reading slip: sometimes a "
            "hand-held instrument locks onto a row one patch too early or too "
            "late — for example it starts on the blank paper before the first "
            "patch. Every patch in that strip is then filed one position out, "
            "and the last one reads the empty paper. The colours still get "
            "saved, so without a warning you might not notice until the profile "
            "looks off.\n\n"
            "With this turned on, after each strip ChromIQ quietly checks "
            "whether the reading would fit the chart dramatically better shifted "
            "by a patch or two. If it clearly would, it stops and tells you — "
            "and offers to jump straight back and re-measure just that one "
            "strip. Your other strips and everything read so far are untouched.\n\n"
            "It is deliberately cautious: it only speaks up when a shift makes a "
            "big, unmistakable improvement, so a normal good read — where vivid "
            "colours naturally differ from the design — never triggers it. And "
            "it only ever warns; it never changes your measurements on its own.\n\n"
            "Leave it off (the default) and nothing changes. Most misreads are "
            "already caught by the ‘wrong strip’ warning; this catches the "
            "subtler one-patch slips that slip past it.\n\n"
            "Default: off"),
            self))
        _meas.addLayout(_sn_row)

        # (The measurement-report options moved to their own Reports tab, Knut.)
        _beta.addStretch()

        self._native_print_check = QCheckBox(tr("Use default macOS printer dialog"), self)
        native_tip = TooltipButton(
            tr("Use default macOS printer dialog"),
            tr("When enabled, clicking Print in the Print Chart tab opens the standard\n"
            "macOS print dialog instead of ChromIQ's built-in PostScript / CUPS pipeline.\n\n"
            "⚠  IMPORTANT: You MUST disable colour management manually in the\n"
            "printer driver panel every time you print — otherwise the printer applies\n"
            "its own colour corrections, which will corrupt the measurement chart\n"
            "and make your ICC profile inaccurate.\n\n"
            "How to disable colour management in the macOS print dialog:\n"
            "After clicking Print, open the dropdown in the middle of the dialog\n"
            "(it usually shows your printer's name or 'Color Matching') and look\n"
            "for a colour-management section:\n\n"
            "  • Epson:  'Epson Color Controls' → Off (No Color Adjustment)\n"
            "  • Canon:  'Color Options' → Manual → set to None\n"
            "  • HP:     'Color Options' → Application Managed Colors\n"
            "  • Others: look for 'No Color Management', 'Off', or\n"
            "            'Application Controlled'\n\n"
            "If you are unsure, leave this option disabled and use ChromIQ's\n"
            "default printing method instead — it disables colour management\n"
            "automatically with no extra steps required."),
            self,
            min_width=620,
        )

        self._pdf_fallback_check = QCheckBox(
            tr("Exact-size PDF fallback (ChromIQ printing)"), self
        )
        pdf_fallback_tip = TooltipButton(
            tr("Exact-size PDF fallback"),
            tr("Applies only to ChromIQ's own printing pipeline (the default when "
            "the macOS printer dialog below is disabled).\n\n"
            "ChromIQ first sends every chart as PostScript. Most home and photo "
            "printers do not understand PostScript, so macOS rejects it and "
            "ChromIQ resends the chart in another format:\n\n"
            "  • OFF — resend as a plain TIFF. macOS then decides the size "
            "itself and SHRINKS a full-page chart by about 3% so it fits "
            "inside the printer's margins. The printed patches end up "
            "slightly smaller and shifted compared to the on-screen layout.\n\n"
            "  • ON — resend as a PDF built by ChromIQ with the chart placed "
            "at exactly 100% scale. Anything that would fall into the "
            "printer's unprintable margin is simply cut off (charts keep "
            "white margins there, so nothing of value is lost). This matches "
            "how Apple's ColorSync Utility prints.\n\n"
            "Colour is unaffected either way — both formats reach the printer "
            "without any colour conversion.\n\n"
            "Greyed out while the macOS printer dialog is enabled, because no "
            "fallback is involved on that path."),
            self,
            min_width=620,
        )

        self._confirm_print_check = QCheckBox(
            tr("Confirm print settings before printing"), self
        )
        confirm_tip = TooltipButton(
            tr("Confirm Print Settings"),
            tr("When enabled, ChromIQ shows a summary dialog of every option that "
            "will be sent to CUPS before each print job:\n\n"
            "  • Printer, paper size, media type, quality, tray, borderless\n"
            "  • Auto-detected orientation (portrait or landscape)\n"
            "  • The forced-off state of duplex and colour management\n"
            "  • Any detected mismatches (e.g. paper size ≠ chart size)\n\n"
            "Highly recommended — profiling targets waste expensive paper and "
            "ink when printed with the wrong settings."),
            self,
            min_width=560,
        )

        # The CUPS preflight summary and the PDF fallback only apply to
        # ChromIQ's own print pipeline. When the macOS print dialog is in use,
        # that dialog is the confirmation step and no lp fallback ever runs,
        # so grey both options out.
        self._native_print_check.toggled.connect(self._sync_print_path_options)

        self._declutter_check = QCheckBox(
            tr("Declutter files when loading from legacy folders"), self)
        declutter_tip = TooltipButton(
            tr("Declutter Files When Loading From Legacy Folders"),
            tr("Newer ChromIQ versions keep each project folder tidy by grouping "
               "the extra paperwork into a few sub-folders — reports (quality "
               "checks and measurement reports), exports (files for other "
               "programs) and cache (temporary tool files). Older projects, made "
               "before this tidy-up existed, keep everything loose in one folder.\n\n"
               "When this option is ON (the default), opening a file from such an "
               "old folder — a profile, a chart, a measurement, a scan target — "
               "quietly sorts those loose ChromIQ files into the right sub-folders "
               "first, creating them if needed, so the folder ends up as neat as a "
               "brand-new project. Then the file you asked for opens as usual.\n\n"
               "It is completely safe: only files ChromIQ itself made are moved, "
               "and only into sub-folders — nothing is renamed, nothing is "
               "deleted, your own files and the chart's core files are never "
               "touched, and a folder with nothing to tidy is left exactly as it "
               "was.\n\n"
               "Turn it OFF if you'd rather ChromIQ never rearrange anything when "
               "you open a file."),
            self,
            min_width=600,
        )
        self._declutter_tip = declutter_tip

        self._splash_check = QCheckBox(
            tr("Show the splash screen on startup"), self
        )
        splash_tip = TooltipButton(
            tr("Show the Splash Screen on Startup"),
            tr("When you launch ChromIQ, it briefly shows a small branded "
            "\"splash\" window — the ChromIQ name and version — while the main "
            "window is being built behind it. It's the app's way of saying "
            "\"I'm starting up\" so the screen isn't blank during the short "
            "moment before the window appears.\n\n"
            "When this option is ON (the default), that splash screen is shown "
            "each time you start the app.\n\n"
            "When OFF, ChromIQ skips the splash entirely and goes straight to "
            "building the main window. Nothing else changes — the app starts "
            "exactly the same way and takes the same amount of time; you simply "
            "don't see the branding screen first. Turn it off if you prefer a "
            "quieter, no-frills launch.\n\n"
            "This takes effect the next time you start ChromIQ."),
            self,
            min_width=560,
        )

        # Collect the options that apply on this platform, in order, then place
        # them two per row. Platform-specific options are simply omitted (rather
        # than hidden) so they leave no empty cell in the grid.
        bh_cells = [
            _bh_cell(self._restore_tab_check, restore_tab_tip),
            _bh_cell(self._restore_session_check, restore_session_tip),
            _bh_cell(self._update_notify_check, update_notify_tip),
            _bh_cell(self._themed_colors_check, themed_colors_tip),
            _bh_cell(self._show_location_check, show_location_tip),
            _bh_cell(self._hide_log_check, hide_log_tip),
            _bh_cell(self._native_files_check, native_files_tip),
            _bh_cell(self._cal_mode_check, cal_tip),
            _bh_cell(self._chromiq_refine_check, refine_tip),
            _bh_cell(self._averaging_check, averaging_tip),
            _bh_cell(self._declutter_check, declutter_tip),
            _bh_cell(self._splash_check, splash_tip),
        ]
        if native_print_supported():
            bh_cells.append(_bh_cell(self._native_print_check, native_tip))
        # The exact-size PDF fallback addresses a macOS-specific CUPS filter
        # behaviour (cgimagetopdf); skip it elsewhere.
        if is_macos():
            bh_cells.append(_bh_cell(self._pdf_fallback_check, pdf_fallback_tip))
        # The CUPS preflight summary is a macOS/Linux concept; skip it on Windows.
        if not is_windows():
            bh_cells.append(_bh_cell(self._confirm_print_check, confirm_tip))

        for i, cell in enumerate(bh_cells):
            bh.addWidget(cell, i // 2, i % 2)

        # The platform-gated print options above are constructed unconditionally
        # (their attributes are referenced by _load_settings / _save_and_close /
        # _sync_print_path_options), but only wrapped in a _bh_cell — which
        # reparents them into the grid — on the platforms that use them. On the
        # others they keep parent=self with no layout, so Qt floats them at the
        # dialog's top-left corner, where they pile up over the first group box.
        # Hide whatever wasn't placed.
        for widget in (
            self._native_print_check, native_tip,
            self._pdf_fallback_check, pdf_fallback_tip,
            self._confirm_print_check, confirm_tip,
        ):
            if widget.parent() is self:
                widget.hide()

        layout.addWidget(behaviour_grp)

        # ---- Appearance & Language ----
        # "&&" — QGroupBox treats a single "&" as a mnemonic marker.
        # Same two-column grid geometry as the Behaviour section above so the
        # cells line up visually.
        appearance_grp = QGroupBox(tr("Appearance && Language"), self)
        ap = QGridLayout(appearance_grp)
        ap.setHorizontalSpacing(100)
        ap.setColumnStretch(0, 1)
        ap.setColumnStretch(1, 1)

        def _ap_cell(label: str, combo: NoScrollComboBox,
                     tooltip: TooltipButton) -> QWidget:
            cell = QWidget(self)
            row = QHBoxLayout(cell)
            row.setContentsMargins(0, 0, 0, 0)
            row.addWidget(QLabel(label, self))
            row.addWidget(combo)
            row.addStretch()
            row.addWidget(tooltip)
            return cell

        self._appearance_combo = NoScrollComboBox(self)
        # data values map combo index -> setting string
        self._appearance_combo.addItem(tr("System (Auto)"), "auto")
        self._appearance_combo.addItem(tr("Light"),        "light")
        self._appearance_combo.addItem(tr("Dark"),         "dark")
        self._appearance_combo.setMinimumWidth(180)
        self._appearance_combo.currentIndexChanged.connect(self._on_appearance_preview)
        appearance_tip = TooltipButton(
            tr("Appearance"),
            tr("Switches the entire app between light and dark visuals.\n\n"
            "  • System (Auto) — follow your macOS Appearance setting and "
            "react if you change it while ChromIQ is running.\n"
            "  • Light — force the light theme even if your system is dark.\n"
            "  • Dark  — force the dark theme even if your system is light.\n\n"
            "Changes preview instantly. Click OK to keep them, or Cancel to revert."),
            self,
            min_width=520,
        )

        self._language_combo = NoScrollComboBox(self)
        from core.i18n import available_languages
        for code, native_name in available_languages():
            self._language_combo.addItem(native_name, code)
        self._language_combo.setMinimumWidth(180)
        self._language_combo.currentIndexChanged.connect(self._on_language_changed)
        language_tip = TooltipButton(
            tr("Language"),
            tr("Choose the language for everything ChromIQ shows you — menus, "
            "buttons, dialogs, help texts and tooltips.\n\n"
            "The change takes effect the next time you start ChromIQ, so "
            "nothing on screen jumps around mid-session.\n\n"
            "Output from the ArgyllCMS tools in the log view stays in "
            "English — it comes from the tools themselves, not from ChromIQ."),
            self,
            min_width=520,
        )

        ap.addWidget(_ap_cell(tr("Theme:"), self._appearance_combo,
                              appearance_tip), 0, 0)
        ap.addWidget(_ap_cell(tr("Language:"), self._language_combo,
                              language_tip), 0, 1)

        self._language_restart_hint = QLabel(
            tr("Takes effect after you restart ChromIQ."), self)
        self._language_restart_hint.setStyleSheet("color: #e6a23c; font-size: 11px;")
        self._language_restart_hint.setVisible(False)
        ap.addWidget(self._language_restart_hint, 1, 0, 1, 2)

        layout.addWidget(appearance_grp)
        layout.addStretch()

        self._tabs.addTab(self._scroll_wrap(general_page), tr("General"))
        self._tabs.addTab(self._scroll_wrap(self._build_margin_thresholds_tab()),
                          tr("Instrument Limits"))
        self._chart_layout_tab_widget = self._build_chart_layout_tab()
        self._tabs.addTab(self._chart_layout_tab_widget, tr("Chart Layout"))
        self._tabs.addTab(self._scroll_wrap(self._build_scanner_tab()),
                          tr("Scanner Limits"))
        self._tabs.addTab(self._scroll_wrap(self._build_paths_tab()),
                          tr("Paths"))
        self._tabs.addTab(self._scroll_wrap(self._build_reports_tab()),
                          tr("Reports"))
        self._tabs.addTab(self._scroll_wrap(self._build_measurement_tab()),
                          tr("Measurement"))
        self._sounds_tab_index = self._tabs.addTab(
            self._scroll_wrap(self._build_sounds_tab()), tr("Sounds"))
        self._tabs.addTab(self._scroll_wrap(self._beta_page), tr("Beta"))
        # Run the (deferred) Chart Layout estimate the first time that tab is
        # actually opened — it's suspended during build to keep the window quick.
        self._tabs.currentChanged.connect(self._on_settings_tab_changed)
        # Six tabs don't fit at the global 130px min-width / 20px padding, so
        # trim this tab bar's tabs enough that they all show without a scroller.
        self._tabs.tabBar().setStyleSheet(
            "QTabBar::tab { min-width: 78px; padding: 9px 12px; }")

        # ---- About / Updates (below the tabs) ----
        # The link word instead of the raw URL, in the app's magenta accent
        # (Sebastian: "something that looks nice", "use the magenta accent") —
        # SPEC_MAGENTA is theme-independent, so it reads in both modes.
        credit1 = QLabel(tr(
            "ChromIQ v{APP_VERSION} · Created by Sebastian Reiprich · "
            "<a href=\"{url}\" style=\"color:{accent}\">Website</a>").format(
                APP_VERSION=APP_VERSION, url=WEBSITE_URL,
                accent=SPEC_MAGENTA), self)
        credit1.setTextFormat(Qt.TextFormat.RichText)
        credit1.setOpenExternalLinks(True)
        credit1.setToolTip(tr("Open the ChromIQ website in your browser."))
        credit1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        credit1.setStyleSheet("color: #606060; font-size: 11px;")
        outer.addWidget(credit1)

        credit2 = QLabel(
            tr("Built on ArgyllCMS by Graeme Gill · Made possible by Knut Georg Larsson · "
            "Testing & feedback: Nelson (Pharmacist), Alan Goldhammer"), self
        )
        credit2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        credit2.setStyleSheet("color: #606060; font-size: 11px;")
        outer.addWidget(credit2)

        self._update_status = QLabel("", self)
        self._update_status.setStyleSheet("font-size: 11px;")
        self._update_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._update_status.setFixedHeight(QFontMetrics(self._update_status.font()).height())
        outer.addWidget(self._update_status)

        # ---- Bottom row: Restore Defaults | Report a Bug | Check for Updates  ...  Cancel / OK ----
        bottom_row = QHBoxLayout()
        reset_btn = QPushButton(tr("Restore Factory Defaults"), self)
        reset_btn.setObjectName("reset_defaults")
        reset_btn.clicked.connect(self._restore_defaults)
        bottom_row.addWidget(reset_btn)

        from core.issue_report import build_bug_report_url, build_feature_request_url
        bug_btn = QPushButton(tr("Report a Bug…"), self)
        bug_btn.setToolTip(tr("Open the bug-report form on GitHub in your browser."))
        bug_btn.clicked.connect(lambda: QDesktopServices.openUrl(
            QUrl(build_bug_report_url(
                self._settings.get("argyll_bin_path", "")))))
        bottom_row.addWidget(bug_btn)

        feature_btn = QPushButton(tr("Request a Feature…"), self)
        feature_btn.setToolTip(
            tr("Open the feature-request form on GitHub in your browser."))
        feature_btn.clicked.connect(lambda: QDesktopServices.openUrl(
            QUrl(build_feature_request_url())))
        bottom_row.addWidget(feature_btn)

        self._update_btn = QPushButton(tr("Check for Updates"), self)
        self._update_btn.clicked.connect(self._check_for_updates)
        bottom_row.addWidget(self._update_btn)
        bottom_row.addStretch()

        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        bb.accepted.connect(self._save_and_close)
        bb.rejected.connect(self.reject)
        bottom_row.addWidget(bb)

        # Match the gap between left-side buttons to QDialogButtonBox's own
        # internal spacing so Restore↔Bug↔Update reads the same as OK↔Cancel.
        bb_layout = bb.layout()
        bottom_row.setSpacing(bb_layout.spacing() if bb_layout else 6)

        outer.addLayout(bottom_row)

        from ui.theme import resolve_mode
        self._apply_indicator_theme(resolve_mode(self._settings.get("appearance", "auto")))

    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Margin Thresholds tab
    # ------------------------------------------------------------------
    # Instruments and paper+orientation choices the per-combo thresholds can be
    # defined for. The instrument labels match what the Create Chart inspector
    # derives from the chart (see core.settings.margin_combo_key).
    _MARGIN_INSTRUMENTS = ("i1Pro", "i1Pro 3+", "ColorMunki", "SpectroScan")
    _MARGIN_PAPERS = ("A4", "Letter", "Legal", "A3", "A3+", "A2", "Tabloid")
    _MARGIN_ORIENTS = ("Portrait", "Landscape")

    def _on_profile_engine_clicked(self, checked: bool) -> None:
        """Friendly beta consent dialog when the engine is switched on."""
        if not checked:
            return
        from PyQt6.QtWidgets import QMessageBox, QSpacerItem, QSizePolicy
        box = QMessageBox(self)
        box.setWindowTitle(tr("ChromIQ Profile Engine (beta)"))
        box.setIcon(QMessageBox.Icon.NoIcon)   # no exclamation mark
        box.setText(tr(
            "Great choice — you're switching on the ChromIQ profile "
            "engine. Here's exactly what that does, in plain terms, so "
            "there are no surprises.\n\n"
            "The short version: from now on, when you click Build Profile, "
            "ChromIQ builds the ICC profile itself instead of handing the "
            "job to Argyll colprof. Everything else stays where it is — "
            "the same tab, the same buttons, the same options. You don't "
            "have to change how you work.\n\n"
            "The big new thing this unlocks:\n\n"
            "•  Printers with extra inks. colprof can only build profiles "
            "for RGB and CMYK printers. If your printer adds orange, "
            "green, violet or other inks on top of CMYK, colprof simply "
            "can't make a profile for it — but the ChromIQ engine can. "
            "Print one of the multi-ink charts from Create Chart, measure "
            "it, and build a real, working profile for that printer, all "
            "without leaving ChromIQ.\n\n"
            "What stays exactly the same:\n\n"
            "•  Every option on the Build Profile tab still works — the "
            "quality levels, the gamut source, the rendering intents, "
            "spectral illuminants and observers, paper-whitener "
            "compensation, the ICC attributes and all the expert "
            "switches. Nothing is taken away.\n\n"
            "•  The colours match colprof. The engine's perceptual "
            "rendering is ChromIQ's own careful port of Argyll's "
            "gamut-mapping maths, and on our test charts the two build "
            "profiles that measure so close you shouldn't be able to tell "
            "them apart in a print.\n\n"
            "•  Your measurements are never touched. If a particular build "
            "needs something only colprof has, ChromIQ quietly lets "
            "colprof handle that one and writes the reason in the log — "
            "you don't have to do anything.\n\n"
            "•  You're always one click from going back. Switch this "
            "option off and ChromIQ returns to building every profile "
            "with colprof, exactly as before.\n\n"
            "Please read this part carefully: this engine is new and "
            "still in beta. It has NOT been extensively tested yet, so "
            "use it at your own risk. Treat every profile it makes as a "
            "trial run — always check it with a test print before you "
            "rely on it for anything that matters, and never use it "
            "unchecked for an important or paid job. If anything looks "
            "off, turn the option back off (colprof comes straight back) "
            "and tell us what you saw; every report genuinely helps make "
            "it better.\n\n"
            "Enable it at your own risk and give it a try?"))
        box.setStandardButtons(QMessageBox.StandardButton.Ok
                               | QMessageBox.StandardButton.Cancel)
        ok_btn = box.button(QMessageBox.StandardButton.Ok)
        cancel_btn = box.button(QMessageBox.StandardButton.Cancel)
        ok_btn.setText(tr("Enable the engine"))
        cancel_btn.setText(tr("Keep using colprof"))
        # Size each button to its own label so the text never clips
        # (QMessageBox default min-width is too narrow for wide labels).
        from PyQt6.QtGui import QFontMetrics
        from PyQt6.QtWidgets import QDialogButtonBox
        for b in (ok_btn, cancel_btn):
            w = QFontMetrics(b.font()).horizontalAdvance(b.text()) + 44
            b.setMinimumWidth(w)
        bbox = box.findChild(QDialogButtonBox)
        if bbox is not None:
            bbox.setCenterButtons(True)
        grid = box.layout()
        if grid is not None:
            # widen the box: a full-width spacer row under the text
            spacer = QSpacerItem(620, 1, QSizePolicy.Policy.Minimum,
                                 QSizePolicy.Policy.Minimum)
            grid.addItem(spacer, grid.rowCount(), 0, 1,
                         grid.columnCount())
        box.setDefaultButton(QMessageBox.StandardButton.Ok)
        if box.exec() != QMessageBox.StandardButton.Ok:
            self._profile_engine_check.setChecked(False)

    def _build_measurement_tab(self) -> QWidget:
        """Measurement pace (#131 Phase 2): how fast a strip may be swiped
        before ChromIQ says something.

        One row per instrument, because the instruments differ enormously — a
        ColorMunki samples at 50 readings per second and a i1Pro 3 at 400, so
        the same swipe gives one of them eight times more light than the other.
        """
        from core.measure_pace import (ESTIMATE_PATCHES_RANGE,
                                       MIN_SAMPLES_RANGE, MODEL_DEFAULTS,
                                       SAMPLE_HZ_RANGE, estimate_patches_for)
        from ui.widgets import NoScrollDoubleSpinBox, NoScrollSpinBox

        page = QWidget()
        v = QVBoxLayout(page)
        v.setSpacing(12)
        v.setContentsMargins(12, 12, 12, 12)

        # The reading-engine block, moved here from Beta (2026-08-13) --
        # first on the tab, in its original order, before the pace text.
        v.addWidget(self._measure_engine_block)

        intro = QLabel(tr(
            "Reading a strip too quickly is the most common reason a scan is "
            "rejected — the instrument simply does not gather enough light per "
            "patch. ChromIQ times each patch as you read it and, after a strip "
            "that was accepted but read close to the limit, tells you so. A "
            "strip read at a comfortable pace says nothing at all."), self)
        intro.setWordWrap(True)
        v.addWidget(intro)

        note = QLabel(tr(
            "Every instrument takes a fixed number of readings per second, so "
            "how long a patch takes decides how many readings it gets. Set that "
            "rate, how many patches one of your strips holds, and the minimum "
            "readings you want per patch — the reading speed at the end of each "
            "row follows from those three, and each instrument's ⓘ works it "
            "through. The defaults suit each instrument; raise the minimum for "
            "more careful measurements, or set it to “Off” to silence the hint "
            "for that instrument."), self)
        note.setWordWrap(True)
        note.setStyleSheet("color: #909090; font-size: 11px;")
        v.addWidget(note)

        self._pace_enable = QCheckBox(tr("Warn me when I read a strip too fast"), self)
        self._pace_enable.setChecked(bool(self._settings.get("pace_hint_enabled", True)))
        pace_tip = TooltipButton(
            tr("Warn Me When I Read a Strip Too Fast"),
            tr("Shows a window when you have swiped a strip more quickly than "
               "your instrument can measure it properly, and offers to read that "
               "strip again.\n\n"
               "WHY IT MATTERS\n"
               "A spectrophotometer takes a fixed number of readings per second "
               "— a ColorMunki manages about 50. Move the instrument quickly and "
               "each patch gets only a handful of them, so its colour is an "
               "average of fewer samples and carries more noise. The measurement "
               "still succeeds, which is exactly the problem: nothing looks "
               "wrong, and the noise ends up inside the profile you build from "
               "it.\n\n"
               "WHAT YOU SEE\n"
               "When a strip comes in too fast, ChromIQ tells you the speed it "
               "measured and what to aim for, and gives you two choices: read "
               "that strip again more slowly, or keep it and carry on. Nothing "
               "is discarded unless you ask for it.\n\n"
               "HOW FAST IS TOO FAST\n"
               "That depends on the instrument and on how many patches are in a "
               "strip, so the threshold is set per instrument in the table "
               "below. Raise a row's minimum for more careful work, or set it to "
               "“Off” to stop warning for that instrument alone.\n\n"
               "TURNING IT OFF changes nothing about how measuring works — the "
               "same readings are taken and saved. It only stops ChromIQ "
               "mentioning the speed, so a hurried strip passes without comment. "
               "Worth leaving on unless the window is interrupting you more "
               "often than it is helping.\n\n"
               "Default: on."),
            self)
        pace_row = QHBoxLayout()
        pace_row.setContentsMargins(0, 0, 0, 0)
        pace_row.addWidget(self._pace_enable)
        pace_row.addStretch()
        pace_row.addWidget(pace_tip)
        v.addLayout(pace_row)

        grp = QGroupBox(tr("Per instrument"), self)
        form = QGridLayout(grp)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)
        form.addWidget(QLabel(tr("Instrument"), self), 0, 0)
        form.addWidget(QLabel(tr("Readings per second"), self), 0, 1)
        # Knut, #130 2026-07-29: the strip length belongs to the instrument, not
        # to one box shared by all of them — an i1Pro 3 Plus needs 16 mm patches
        # and fits half as many on a strip as an i1Pro 2, so one common number
        # could only ever be right for one row.
        form.addWidget(QLabel(tr("Patches per strip"), self), 0, 2)
        form.addWidget(QLabel(tr("Minimum readings per patch"), self), 0, 3)
        # Knut, #131 2026-07-27: show what the numbers MEAN for a real strip,
        # live, so a threshold can be chosen without doing the arithmetic by
        # hand.
        form.addWidget(QLabel(tr("Min. strip reading speed"), self), 0, 5)

        labels = {
            "i1pro":      tr("i1Pro (first generation)"),
            "i1pro2":     tr("i1Pro 2"),
            "i1pro3":     tr("i1Pro 3"),
            "i1pro3plus": tr("i1Pro 3 Plus"),
            "colormunki": tr("ColorMunki / i1Studio"),
            "spectroscan": tr("SpectroScan (motorised table)"),
        }
        self._pace_hz: dict = {}
        self._pace_patches: dict = {}
        self._pace_min: dict = {}
        self._pace_estimate: dict = {}
        for row, (key, (hz_default, min_default)) in enumerate(
                MODEL_DEFAULTS.items(), start=1):
            form.addWidget(QLabel(labels.get(key, key), self), row, 0)

            hz = NoScrollDoubleSpinBox(self)
            hz.setRange(*SAMPLE_HZ_RANGE)
            hz.setDecimals(0)
            hz.setSuffix(tr(" Hz"))
            hz.setMaximumWidth(140)
            hz.setValue(float(self._settings.get(f"pace_sample_hz_{key}", hz_default)
                              or hz_default))
            hz.setToolTip(tr(
                "How many readings this instrument takes each second, from its "
                "specification. ChromIQ uses it to work out how many readings a "
                "patch received from how long it took."))
            form.addWidget(hz, row, 1)
            self._pace_hz[key] = hz

            # How long a strip is, for this instrument's figure. Changing it
            # shows straight away what the row's setting means for YOUR charts.
            pp = NoScrollSpinBox(self)
            pp.setRange(*ESTIMATE_PATCHES_RANGE)
            # 0 = "N/A": the SpectroScan places its head on each patch in turn,
            # so a strip length says nothing at all about it.
            pp.setSpecialValueText(tr("N/A"))
            pp.setMaximumWidth(140)
            pp_default = estimate_patches_for(key) or 0
            pp.setValue(int(self._settings.get(
                f"pace_estimate_patches_{key}", pp_default) or 0))
            pp.setToolTip(tr(
                "How many patches one strip of your charts holds for this "
                "instrument. It is used only for the reading speed shown at the "
                "end of this row — it changes nothing about how you measure."))
            form.addWidget(pp, row, 2)
            self._pace_patches[key] = pp

            mn = NoScrollSpinBox(self)
            # 0 means off, so the range starts one below the real minimum and
            # the special value shows as "Off" (the SpectroScan's default: a
            # motorised table has no swipe to be too quick).
            mn.setRange(0, MIN_SAMPLES_RANGE[1])
            mn.setSpecialValueText(tr("Off"))
            mn.setMaximumWidth(140)
            stored = self._settings.get(f"pace_min_samples_{key}", None)
            if stored is None:
                stored = 0 if min_default is None else min_default
            mn.setValue(int(stored or 0))
            mn.setToolTip(tr(
                "The fewest readings a patch should get. Below this, ChromIQ "
                "says the strip was read quickly. Set it to Off to give no "
                "warning for this instrument."))
            form.addWidget(mn, row, 3)
            self._pace_min[key] = mn

            # Why these two numbers, and how they were arrived at (Knut, #131
            # 2026-07-26). The text lives beside the defaults themselves, so a
            # changed default cannot leave a stale explanation behind.
            from core.measure_pace import explanation_for
            # NOT a local import of TooltipButton: it is imported at module
            # level, and re-importing it here made the name local to the whole
            # method — so the tooltip added earlier in this same method raised
            # UnboundLocalError, and 19 tests errored on a dialog that would
            # not build.
            title, body = explanation_for(key)
            form.addWidget(TooltipButton(title, body, self), row, 4)

            # The live figure: patches x minimum readings / readings per second.
            est = QLabel("", self)
            est.setStyleSheet("color: #909090;")
            form.addWidget(est, row, 5)
            self._pace_estimate[key] = est
            hz.valueChanged.connect(self._refresh_pace_estimates)
            pp.valueChanged.connect(self._refresh_pace_estimates)
            mn.valueChanged.connect(self._refresh_pace_estimates)

        # The slack goes into a column of its own on the right, so the boxes
        # keep a sensible width and the ⓘ next to each row is never squeezed
        # off the edge of the group.
        form.setColumnStretch(6, 1)

        v.addWidget(grp)

        # The single "No. of patches per strip for estimation of speed" box that
        # used to sit here is gone: each instrument now carries its own strip
        # length in the table above, and its explanation moved into each
        # instrument's ⓘ (Knut, #130 2026-07-29).
        self._refresh_pace_estimates()
        v.addStretch(1)
        return page

    def _refresh_pace_estimates(self) -> None:
        """Update every instrument's "fastest a strip may be read" figure.

        Live, because the point is to choose a threshold BY the reading speed it
        implies (Knut, #131 2026-07-27). An instrument whose warning is switched
        off has no such speed, and says so rather than showing a nonsense zero.
        Each row uses its OWN strip length (Knut, #130 2026-07-29), so the
        number after the @ is always the one in that row's box.
        """
        for key, lbl in getattr(self, "_pace_estimate", {}).items():
            hz = float(self._pace_hz[key].value())
            mn = int(self._pace_min[key].value())
            patches = int(self._pace_patches[key].value())
            if mn <= 0 or hz <= 0:
                lbl.setText(tr("no limit"))
                continue
            if patches <= 0:
                # The strip length is N/A — an honest "nothing to work out"
                # rather than a figure computed from a zero.
                lbl.setText(tr("not applicable"))
                continue
            seconds = patches * mn / hz
            if patches == 1:
                lbl.setText(tr("{secs} sec. @ 1 patch/strip").format(
                    secs=f"{seconds:.1f}"))
            else:
                lbl.setText(tr("{secs} sec. @ {n} patches/strip").format(
                    secs=f"{seconds:.1f}", n=patches))

    def _build_sounds_tab(self) -> QWidget:
        """Measurement sound feedback (#131): which sound plays for each event.
        The master on/off is the “Play sounds during measurement” box on the
        Measure tab; here you pick the sounds. Every dropdown is built from the
        .wav files in the sounds folder (Preferences → Paths), so it grows if you
        add your own."""
        import core.sound as snd

        page = QWidget()
        v = QVBoxLayout(page)
        v.setSpacing(12)
        v.setContentsMargins(12, 12, 12, 12)

        intro = QLabel(tr(
            "ChromIQ can play a short sound as you measure — a tick as each "
            "patch is read, a bell when a strip is done, a warning if a reading "
            "looks off, and a little fanfare when everything's finished. It's a "
            "hands-free way to know how the measurement is going without "
            "watching the screen."), self)
        intro.setWordWrap(True)
        v.addWidget(intro)

        note = QLabel(tr(
            "Turn sounds on with the “Play sounds during measurement” box on the "
            "Measure tab. Here you choose which sound plays for each event — pick "
            "“Off (no sound)” for any you'd rather keep silent, and press "
            "“Play” to hear one. To add your own sounds, set a sounds folder on "
            "the Paths tab."), self)
        note.setWordWrap(True)
        note.setStyleSheet("color: #909090; font-size: 11px;")
        v.addWidget(note)

        # The full windows-and-sounds table. It belongs on this tab and not on
        # the Measurement one (Knut, #131 2026-07-28): everything it explains is
        # a sound, so it sits with the sounds it names.
        _wnd_row = QHBoxLayout()
        _wnd_row.addWidget(QLabel(
            tr("Which sound belongs to which window during a measurement:"), page))
        from core.measure_windows import windows_and_sounds_html
        _wnd_row.addWidget(TooltipButton(
            tr("Measurement windows and their sounds"),
            windows_and_sounds_html(), page))
        _wnd_row.addStretch(1)
        v.addLayout(_wnd_row)

        self._sound_combos: dict = {}

        def _add_rows(grp_title: str, rows: list) -> None:
            grp = QGroupBox(grp_title, page)
            grid = QGridLayout(grp)
            grid.setHorizontalSpacing(8)
            grid.setVerticalSpacing(8)
            for r, (event, label, help_body) in enumerate(rows):
                lbl = QLabel(label, grp)
                grid.addWidget(lbl, r, 0)
                combo = NoScrollComboBox(grp)
                for stem in snd.list_choices(self._settings, event):
                    combo.addItem(
                        tr("Off (no sound)") if stem == snd.OFF else stem, stem)
                cur = snd.choice_for(self._settings, event)
                combo.setCurrentIndex(max(0, combo.findData(cur)))
                self._sound_combos[event] = combo
                grid.addWidget(combo, r, 1)
                play = QPushButton(tr("Play"), grp)
                play.setStyleSheet(
                    "QPushButton { padding: 2px 12px; min-height: 0; }")
                play.clicked.connect(
                    lambda _=False, e=event, c=combo: self._preview_sound(e, c))
                grid.addWidget(play, r, 2)
                grid.addWidget(TooltipButton(label, help_body, grp), r, 3)
            grid.setColumnStretch(1, 1)
            v.addWidget(grp)

        _add_rows(tr("Sounds at measurement actions"), [
            (snd.PATCH_OK, tr("Patch read OK"),
             tr("Plays each time a single patch is read successfully. A short, "
                "quiet sound (a tick or click) works best, because it repeats "
                "for every patch.\n\n"
                "Only in patch-by-patch reading — reading one patch at a time, "
                "or a chart set to patch-by-patch mode. When you swipe whole "
                "strips the instrument reports the strip in one go, once the "
                "swipe has finished, so there are no separate patches to sound "
                "as you go.")),
            (snd.PATCH_OUT_OF_TOL, tr("Patch reading looks off"),
             tr("Plays when a patch's reading is far from its expected colour — "
                "a likely misread or a smudge. A low “thump” makes it stand out "
                "from the normal patch tick.\n\n"
                "Needs the ChromIQ reading engine (on by default), and — like "
                "the patch tick above — only in patch-by-patch reading.")),
            (snd.STRIP_OK, tr("Strip read OK"),
             tr("Plays when a whole strip (a row of patches) has been read "
                "successfully — your cue to move to the next strip.")),
            (snd.STRIP_FAIL, tr("Strip read failed"),
             tr("Plays when a strip couldn't be read for a reason other than "
                "speed — the swipe wandered off the strip, started or ended in "
                "the wrong place, or the light level was wrong. Read that strip "
                "again.\n\nWhen the strip failed because it was read too "
                "quickly, the “Slow down” sound plays instead, so the cue "
                "always matches the fault.")),
            (snd.INSTRUMENT_ERROR, tr("Instrument error"),
             tr("Plays when the measuring instrument reports a problem — a "
                "disconnection, a wrong position, or a communication error.")),
            (snd.SLOW_DOWN, tr("Slow down"),
             tr("Plays when a strip was swiped too fast to read reliably and "
                "you should ease off. A calm, unmistakable cue.\n\n"
                "It is used both when the instrument rejects a strip for being "
                "hurried and when a strip was accepted but read faster than "
                "the minimum you set in Preferences → Measurement.")),
        ])

        _add_rows(tr("Sounds at action completion"), [
            (snd.MEASUREMENT_FINISHED, tr("Measurement finished"),
             tr("Plays once the whole chart has been measured — a celebratory "
                "sound like a drumroll or applause. This one may play even when "
                "you're not actively measuring.")),
            (snd.PROFILE_BUILT, tr("Profile build finished"),
             tr("Plays when a profile has finished building on the Build "
                "Profile tab. This one may play even when you're not "
                "measuring.")),
        ])

        v.addStretch()
        return page

    def _sync_sounds_audio_hold(self) -> None:
        """Hold the audio device open exactly while the Sounds tab is showing.

        The audition ignores the master on/off switch, so this does too — the
        point of the “Play” buttons is to hear a sound whether or not sounds are
        currently switched on.
        """
        want = (getattr(self, "_sounds_tab_index", -1) >= 0
                and self._tabs.currentIndex() == self._sounds_tab_index)
        if want == getattr(self, "_audio_held", False):
            return
        try:
            import core.sound as snd
            if want:
                self._audio_held = True
                snd.hold_audio_device(self._settings)
            else:
                self._audio_held = False
                snd.release_audio_device()
        except Exception:      # noqa: BLE001 — never break the dialog
            log.debug("could not change the audio hold", exc_info=True)

    def done(self, result: int) -> None:
        """Release the audio hold whichever way the dialog is dismissed —
        Save, Cancel, Escape or the window's close button all land here."""
        try:
            if getattr(self, "_audio_held", False):
                import core.sound as snd
                self._audio_held = False
                snd.release_audio_device()
        except Exception:      # noqa: BLE001
            log.debug("could not release the audio device", exc_info=True)
        super().done(result)

    def _preview_sound(self, event: str, combo) -> None:
        """Audition the dropdown's currently-selected sound (ignores the on/off
        switch and the during-measurement rule — it's a manual preview)."""
        import core.sound as snd
        stem = combo.currentData()
        path = snd.file_for_stem(self._settings, event, stem)
        if path is None:
            return
        cls = snd._sound_effect_cls()
        if cls is None:                     # no audio backend in this build/env
            return
        try:
            from PyQt6.QtCore import QUrl
            eff = getattr(self, "_preview_effect", None) or cls(self)
            self._preview_effect = eff       # keep a ref so it isn't GC'd mid-play
            eff.setSource(QUrl.fromLocalFile(str(path)))
            eff.setVolume(0.85)
            eff.play()
        except Exception:                    # noqa: BLE001 — preview must never crash
            pass

    def _build_reports_tab(self) -> QWidget:
        """Measurement-report settings (Knut): the auto-save toggle, moved here
        from Beta, and the default Pass thresholds the report opens with. A home
        for any further report settings later."""
        page = QWidget()
        v = QVBoxLayout(page)
        v.setSpacing(12)
        v.setContentsMargins(12, 12, 12, 12)

        intro = QLabel(tr(
            "Settings for the Measurement Report — the tool that checks a "
            "measured chart against its design colours and tracks how a printer "
            "drifts over time."), self)
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #909090; font-size: 11px;")
        v.addWidget(intro)

        # Auto-save (moved here from the Beta tab), in its own section so it lines
        # up with the defaults frame below (Knut).
        save_grp = QGroupBox(tr("Automatic Saving"), self)
        sg = QVBoxLayout(save_grp)
        sg.setSpacing(8)
        self._save_report_check = QCheckBox(
            tr("Save a measurement report after each measurement"), self)
        _rep_row = QHBoxLayout()
        _rep_row.addWidget(self._save_report_check)
        _rep_row.addStretch()
        _rep_row.addWidget(TooltipButton(
            tr("Save a measurement report after each measurement"),
            tr("When this is on, ChromIQ automatically writes a small dated "
            "report next to each chart every time you finish measuring it "
            "(in a “reports” folder beside the chart). Each report records how "
            "close the measurement came to the chart's design colours — a "
            "Pass/Fail check of the colour accuracy, the worst patches, the "
            "cube corners, and the paper white and black.\n\n"
            "Why keep it on? Because the reports then build up over time, and "
            "the Measurement Report tool can plot how a chart's measurements "
            "change from one to the next — a gradual rise, or a shift in white "
            "or black, is a sign of ageing inks, a drifting printer, or a "
            "drifting instrument. It's especially handy for regular "
            "verification measurements: the report shows you when the results "
            "have slipped far enough that re-profiling is worth it.\n\n"
            "It costs nothing noticeable and never changes your measurement "
            "files. Turn it off if you don't want this history.\n\n"
            "Default: on"),
            self))
        sg.addLayout(_rep_row)
        v.addWidget(save_grp)

        # Default Pass thresholds the Measurement Report opens with (Knut).
        defaults_grp = QGroupBox(tr("Measurement Report Defaults"), self)
        gl = QVBoxLayout(defaults_grp)
        gl.setSpacing(8)
        thr_row = QHBoxLayout()
        thr_row.addWidget(QLabel(tr("Pass threshold — Average:"), self))
        self._report_avg_thr_spin = NoScrollDoubleSpinBox(self)
        self._report_avg_thr_spin.setDecimals(1)
        self._report_avg_thr_spin.setRange(0.1, 100.0)
        self._report_avg_thr_spin.setSingleStep(0.5)
        self._report_avg_thr_spin.setSuffix(" ΔE")
        thr_row.addWidget(self._report_avg_thr_spin)
        thr_row.addSpacing(14)
        thr_row.addWidget(QLabel(tr("Maximum:"), self))
        self._report_max_thr_spin = NoScrollDoubleSpinBox(self)
        self._report_max_thr_spin.setDecimals(1)
        self._report_max_thr_spin.setRange(0.1, 100.0)
        self._report_max_thr_spin.setSingleStep(0.5)
        self._report_max_thr_spin.setSuffix(" ΔE")
        thr_row.addWidget(self._report_max_thr_spin)
        thr_row.addStretch()
        thr_row.addWidget(TooltipButton(
            tr("Pass thresholds"),
            tr("The colour-accuracy verdict. A metric passes when its measured "
               "ΔE00 is at or below its threshold. The Average threshold is "
               "compared against the three average metrics (all patches, the best "
               "95%, and the worst 5%); the Maximum threshold against the two "
               "maximum metrics (all patches, and the best 95%). Typical starting "
               "points are 2.0 for the average and 3.0 for the maximum — tighten "
               "them for critical work, loosen them for a quick health check."),
            self))
        gl.addLayout(thr_row)
        v.addWidget(defaults_grp)

        # Report title/filename prefixes (#130, Knut). The report picks the
        # profiling or verification line by whether its measurements are
        # colour-managed verifications; the date_time and optional profile name
        # are appended automatically.
        from PyQt6.QtWidgets import QLineEdit
        title_grp = QGroupBox(
            tr("Default measurement report title and file name"), self)
        tgl = QVBoxLayout(title_grp)
        tgl.setSpacing(8)
        _pr = QHBoxLayout()
        _pr.addWidget(QLabel(tr("Profiling measurement runs:"), self))
        self._report_title_prof_edit = QLineEdit(self)
        _pr.addWidget(self._report_title_prof_edit, 1)
        tgl.addLayout(_pr)
        _vr = QHBoxLayout()
        _vr.addWidget(QLabel(tr("Verification measurement runs:"), self))
        self._report_title_verify_edit = QLineEdit(self)
        _vr.addWidget(self._report_title_verify_edit, 1)
        tgl.addLayout(_vr)
        _apn_row = QHBoxLayout()
        self._report_add_profile_check = QCheckBox(
            tr("Add profile name in title and file name"), self)
        _apn_row.addWidget(self._report_add_profile_check)
        _apn_row.addStretch()
        _apn_row.addWidget(TooltipButton(
            tr("Report title and file name"),
            tr("The measurement report's first-page title and its saved PDF file "
            "name are built from these lines. ChromIQ uses the first line for a "
            "normal profiling report and the second for a verification report "
            "(it can tell which from the measurements).\n\n"
            "The first-page title is just your text — “<your text>” — because "
            "the report already shows its date inside. The saved PDF file name "
            "adds the date and time: “<your text> - <date_time>.pdf”.\n\n"
            "Tick “Add profile name in title and file name” to also insert the "
            "profile (chart) name, giving the title “<your text> - <profile "
            "name>” and the file name “<your text> - <profile name> - "
            "<date_time>.pdf”.\n\n"
            "Default: the two suggested lines, profile name on."),
            self))
        tgl.addLayout(_apn_row)
        v.addWidget(title_grp)

        v.addStretch()
        return page

    def _build_paths_tab(self) -> QWidget:
        """Every folder ChromIQ reads or writes, in one place (Knut, #108):
        the two the user may change, and the rest visible with a Reveal
        button instead of buried in documentation."""
        import sys
        from core.i18n import user_i18n_dir
        from core.platform_paths import icc_install_dir, log_dir, presets_dir
        from core.preset_store import reveal_in_file_manager

        page = QWidget()
        v = QVBoxLayout(page)
        v.setSpacing(10)
        v.setContentsMargins(12, 12, 12, 12)

        grp_w = QGroupBox(tr("Where ChromIQ writes"), page)
        gw = QVBoxLayout(grp_w)

        folder_lbl = QLabel(
            tr("Default output folder (leave blank to use ~/ChromIQ/):"), self)
        folder_lbl.setWordWrap(True)
        gw.addWidget(folder_lbl)
        folder_row = QHBoxLayout()
        self._folder_edit = QLineEdit(self)
        self._folder_edit.setPlaceholderText(tr("~/ChromIQ/  (default)"))
        folder_row.addWidget(self._folder_edit, stretch=1)
        folder_browse = make_browse_button(self, tr("Select output folder"), icon="folder")
        folder_browse.clicked.connect(self._browse_folder)
        folder_row.addWidget(folder_browse)
        gw.addLayout(folder_row)

        inst_lbl = QLabel(tr(
            "Profile install folder — where “Install profile” copies a "
            "finished .icc (leave blank for your system's colour-profile "
            "folder):"), self)
        inst_lbl.setWordWrap(True)
        gw.addWidget(inst_lbl)
        inst_row = QHBoxLayout()
        self._profile_dir_edit = QLineEdit(self)
        self._profile_dir_edit.setPlaceholderText(
            str(icc_install_dir(ignore_override=True)))
        self._profile_dir_edit.setText(
            str(self._settings.get("profile_install_dir", "")))
        inst_row.addWidget(self._profile_dir_edit, stretch=1)
        inst_browse = make_browse_button(
            self, tr("Select profile install folder"), icon="folder")

        def _pick_profile_dir() -> None:
            d = open_dir_dialog(self, tr("Select profile install folder"),
                                start_dir=self._profile_dir_edit.text()
                                or str(icc_install_dir()))
            if d:
                self._profile_dir_edit.setText(d)

        inst_browse.clicked.connect(_pick_profile_dir)
        inst_row.addWidget(inst_browse)
        gw.addLayout(inst_row)

        # Measurement sounds folder (#131). Blank = the bundled default pack;
        # point it at your own folder to add or replace sounds. The Sounds tab's
        # dropdowns list whatever .wav files are found in its three sub-folders.
        snd_lbl = QLabel(tr(
            "Measurement sounds folder — your own sounds for the Sounds tab "
            "(leave blank to use the sounds that come with ChromIQ). It should "
            "contain the sub-folders “measurement-events”, “slow-down” and "
            "“task-complete”; each .wav file inside becomes a choice in the "
            "matching dropdown."), self)
        snd_lbl.setWordWrap(True)
        gw.addWidget(snd_lbl)
        snd_row = QHBoxLayout()
        self._sound_dir_edit = QLineEdit(self)
        self._sound_dir_edit.setPlaceholderText(
            tr("(the sounds that come with ChromIQ)"))
        self._sound_dir_edit.setText(str(self._settings.get("sound_folder", "")))
        snd_row.addWidget(self._sound_dir_edit, stretch=1)
        snd_browse = make_browse_button(
            self, tr("Select measurement sounds folder"), icon="folder")

        def _pick_sound_dir() -> None:
            d = open_dir_dialog(self, tr("Select measurement sounds folder"),
                                start_dir=self._sound_dir_edit.text()
                                or str(Path.home()))
            if d:
                self._sound_dir_edit.setText(d)

        snd_browse.clicked.connect(_pick_sound_dir)
        snd_row.addWidget(snd_browse)
        gw.addLayout(snd_row)
        v.addWidget(grp_w)

        grp_r = QGroupBox(tr("For reference"), page)
        gr = QGridLayout(grp_r)
        gr.setHorizontalSpacing(8)
        gr.setVerticalSpacing(6)

        def _info_row(r: int, name: str, path: Path, about: str) -> None:
            lbl = QLabel(name, grp_r)
            lbl.setToolTip(about)
            gr.addWidget(lbl, r, 0)
            fld = QLineEdit(str(path), grp_r)
            fld.setReadOnly(True)
            fld.setToolTip(about)
            gr.addWidget(fld, r, 1)
            btn = QPushButton(tr("Reveal"), grp_r)
            btn.setStyleSheet("QPushButton { padding: 2px 12px; min-height: 0; }")
            btn.clicked.connect(
                lambda _=False, p=path: reveal_in_file_manager(
                    p if p.is_dir() or not p.suffix else p.parent))
            gr.addWidget(btn, r, 2)

        # The install location a USER thinks in: the .app bundle on macOS
        # (not its Contents/MacOS innards), the executable's folder elsewhere,
        # the repository when running from source (Knut).
        app_path = Path(sys.argv[0]).resolve()
        install = next((p for p in app_path.parents if p.suffix == ".app"),
                       app_path.parent)
        _info_row(0, tr("Log file:"), log_dir() / "chromiq.log",
                  tr("ChromIQ's session log — attach it to a bug report."))
        _info_row(1, tr("Presets:"), presets_dir(),
                  tr("Your saved presets as plain .json files — copy them to "
                     "another machine or share them."))
        _info_row(2, tr("Translation overrides:"), user_i18n_dir(),
                  tr("Drop an edited language file here (Tools → Translate / "
                     "edit language) and it overrides the built-in "
                     "translation."))
        _info_row(3, tr("ArgyllCMS binaries (change on General):"),
                  Path(str(self._settings.get("argyll_bin_path", ""))),
                  tr("The ArgyllCMS command-line tools ChromIQ runs. Change "
                     "the path on the General tab."))
        _info_row(4, tr("Installation:"), install,
                  tr("Where ChromIQ itself is installed."))
        gr.setColumnStretch(1, 1)
        v.addWidget(grp_r)
        v.addStretch()
        return page

    def _build_scanner_tab(self) -> QWidget:
        """Scanner/camera profiling: the misalignment-check thresholds (Knut,
        #108). Four plain numbers with friendly names — the checks themselves
        live in the Build profile with scanner or camera tool."""
        page = QWidget()
        v = QVBoxLayout(page)
        v.setSpacing(10)
        v.setContentsMargins(12, 12, 12, 12)

        intro = QLabel(tr(
            "When the scanner tool reads a scanned chart, it checks whether "
            "the reading grid actually sat on the patches. These are the "
            "limits those checks use. The defaults include a buffer for real "
            "scans (noisier than the built-in demo images) — loosen them if "
            "you get warnings on builds you've verified are fine, tighten "
            "them to be warned earlier."), page)
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #909090; font-size: 11px;")
        v.addWidget(intro)

        grp = QGroupBox(tr("Misalignment warnings"), page)
        g = QGridLayout(grp)
        g.setHorizontalSpacing(8)
        g.setVerticalSpacing(8)

        # Rows are grouped by which check they belong to, with a blank row
        # between groups so it's visible at a glance which limits work
        # together (Knut, #119):
        #   0,1  profile self-check      3  placement agreement
        #   5,6,7  patch-edge detection
        defaults = {0: "30", 1: "12", 3: "0.85", 5: "2", 6: "0.20", 7: "8"}

        def _row(r: int, label: str, spin, tip_title: str, tip_body: str) -> None:
            g.addWidget(QLabel(label, grp), r, 0)
            g.addWidget(spin, r, 1)
            body = tip_body + "\n\n" + tr("Default: {v}.").format(v=defaults[r])
            g.addWidget(TooltipButton(tip_title, body, grp), r, 2)

        def _gap(r: int) -> None:
            sp = QLabel("", grp)
            sp.setFixedHeight(10)
            g.addWidget(sp, r, 0)

        s = self._settings
        self._scan_peak_spin = NoScrollDoubleSpinBox(grp)
        self._scan_peak_spin.setRange(5.0, 200.0)
        self._scan_peak_spin.setDecimals(0)
        self._scan_peak_spin.setSingleStep(5.0)
        self._scan_peak_spin.setValue(float(s.get("scanner_selfcheck_peak", 30.0)))
        self._scan_peak_spin.setMinimumWidth(120)
        _row(0, tr("Warn when the finished profile fits worse than (peak):"), self._scan_peak_spin,
             tr("Profile self-check (after building)"),
             tr("After every build, colprof reports how well the finished "
                "profile fits its own measurements (\"peak err\"). An aligned "
                "read fits well; a grid that sat only half a patch off reads "
                "believable BLENDS of neighbouring colours — too subtle for "
                "the checks above, but the fit error jumps (60–90 instead of "
                "under 10).\n\n"
                "When the peak error is above this limit, ChromIQ warns you "
                "to check the diagnostic images before trusting the "
                "profile."))

        _gap(2)
        self._scan_check_spin = NoScrollDoubleSpinBox(grp)
        self._scan_check_spin.setRange(0.5, 0.99)
        self._scan_check_spin.setDecimals(2)
        self._scan_check_spin.setSingleStep(0.01)
        self._scan_check_spin.setValue(float(s.get("scanner_check_agreement", 0.85)))
        self._scan_check_spin.setMinimumWidth(120)
        _row(3, tr("Check alignment: flag placements below (0.5–0.99):"),
             self._scan_check_spin,
             tr("Placement agreement (Check alignment and building)"),
             tr("In short: this asks \"is my reading grid really on the "
                "patches, or would it fit better a little to one side?\" If a "
                "nearby position would fit better, ChromIQ tells you, and "
                "names the patches that look most wrong.\n\n"
                "You'll see two percentages, like \"worst 56.88 %, average "
                "96.70 %\". Every patch gets its own agreement number; "
                "\"worst\" is the single worst patch on the page and is the "
                "number that decides — when it falls below this setting, you "
                "get a warning. \"Average\" is simply the average of all the "
                "patches' numbers, so it tells you what kind of problem you "
                "have: a low worst with a high average means a few patches "
                "are off (a pulled corner, a local wrinkle), while both low "
                "means the whole grid has slipped.\n\n"
                "What to change: if you get warnings on scans you've checked "
                "by eye and know are fine, lower this. Raise it to be warned "
                "earlier. The default is calibrated on real scanned targets: "
                "a correctly placed grid reads about 90 % or better at any "
                "sample area, a single corner dragged inwards by a fiftieth "
                "of the grid already collapses the worst patch, and anything "
                "under about 5 % of a patch of drift passes.\n\n"
                "How it works, if you're curious: ChromIQ samples the scan at "
                "your grid position and again at every rung of a ladder "
                "around it — 24 steps of 5 % of a patch, in all 8 directions. "
                "Each patch is then ranked on its own ladder: its best "
                "reading anywhere is that patch's 100 %; each direction "
                "contributes its worst reading, directions where the reading "
                "never worsens are ignored, and the mildest of the remaining "
                "direction-worsts is that patch's 0 %. Your grid position "
                "lands somewhere between — separately for every patch, so "
                "one misplaced patch shows even when the rest of the page "
                "is perfect.\n\n"
                "The same check runs for every page when you build — a "
                "flagged page is listed in the warning popup before "
                "anything is built."))
        _gap(4)
        self._scan_flank_min_combo = NoScrollComboBox(grp)
        self._scan_flank_min_combo.addItem(tr("Off — don't detect patch edges"), 0)
        for _n in range(1, 10):
            self._scan_flank_min_combo.addItem(str(_n), _n)
        _cur = int(s.get("scanner_flank_min_boxes", 2))
        self._scan_flank_min_combo.setCurrentIndex(
            max(0, self._scan_flank_min_combo.findData(_cur)))
        self._scan_flank_min_combo.setMinimumWidth(120)
        _row(5, tr("Warn when this many patches sit on an edge (Off, 1–9):"),
             self._scan_flank_min_combo,
             tr("How many patches on an edge before you're warned"),
             tr("In short: ChromIQ checks each reading box separately to see "
                "whether it is sitting on the border between two patches "
                "instead of squarely inside one. This setting says how many "
                "patches have to be caught doing that, at the same time, "
                "before you get a misalignment warning.\n\n"
                "It counts whole patches of the reading grid — not the small "
                "sensing cells inside a single patch. Choose Off to switch "
                "edge detection off completely; the placement-agreement check "
                "above keeps running either way.\n\n"
                "What to change: lower it (1 or 2) to be warned as soon as a "
                "single patch lands on a border. Raise it if a target's own "
                "printed design keeps triggering warnings on grids you know "
                "are correct.\n\n"
                "Why the default is 2: an edge has to look like a straight "
                "border line before a patch is counted at all (see the "
                "settings below), so grain, specks and a target's own "
                "printed features can't inflate the count — on real "
                "600 dpi scans of a LaserSoft and a Wolf Faust IT8, a "
                "correct grid leaves at most 1 counted patch. Dragging one "
                "corner of the grid inwards, until a few patches in that "
                "corner straddle their borders, leaves 3 or more; sliding "
                "the whole grid a fifth of a patch sideways leaves over a "
                "hundred. So 2 warns at the earliest reliable moment "
                "without crying wolf on a correct grid."))
        self._scan_flank_spin = NoScrollDoubleSpinBox(grp)
        self._scan_flank_spin.setRange(0.02, 0.50)
        self._scan_flank_spin.setDecimals(2)
        self._scan_flank_spin.setSingleStep(0.01)
        self._scan_flank_spin.setValue(float(s.get("scanner_flank_limit", 0.20)))
        self._scan_flank_spin.setMinimumWidth(120)
        _row(6, tr("…counting a patch as on an edge above (0.02–0.5):"),
             self._scan_flank_spin,
             tr("How strong an edge has to be to count"),
             tr("In short: this is how obvious a patch border has to look "
                "before ChromIQ decides a reading box is sitting on it. "
                "Lower = stricter, so fainter borders count. It works "
                "together with the setting above: this one decides which "
                "patches are \"on an edge\", that one decides how many of "
                "them it takes to warn you.\n\n"
                "What the number means: it is NOT a percentage difference "
                "between two patches. It measures how STEEPLY the colour "
                "changes inside the box, compared with the gentle speckle of "
                "print grain and scanner noise on the same page. 0.20 means "
                "the box contains a colour change a fifth of the page's whole "
                "brightness range steeper than that grain. A patch border is "
                "a sharp step, so it towers over grain even when the two "
                "patches themselves are similar in colour.\n\n"
                "What to change: below about 0.06 you start counting the "
                "grain itself and will get false warnings. Above about 0.30, "
                "genuinely misplaced boxes go unnoticed. If you scan a very "
                "noisy or textured paper, raise it a little.\n\n"
                "How it works, if you're curious: every patch carries a fine "
                "grid of 30×30 small sensing cells (15×15 on low-resolution "
                "scans), spread over 85 % of the patch's width and height — "
                "shaped with the same equal-margin rule as the reading box, "
                "so the two always stay parallel. Only the cells around the "
                "reading box are awake: the box itself plus one thin ring of "
                "cells just outside it, so a border is spotted the moment it "
                "comes close to what is actually being READ — equally from "
                "every side, and following your Patch sample area setting in "
                "and out. Each awake cell records the steepest colour change "
                "it can see — in brightness and in two colour-opponent "
                "channels, so a border between two patches of the same "
                "brightness is still caught. A box counts as being on an "
                "edge only when enough cells light up in a straight row "
                "(see the setting below — a border is a line, while dust "
                "specks clump and grain scatters) AND the box reads clean a "
                "little to one side — that last rule is what stops a "
                "target's own printed bars and wedges from counting. The "
                "box's edge strength is then its third-strongest cell — the "
                "scale this limit is calibrated on.\n\n"
                "Where the default comes from: on real 600 dpi IT8 scans the "
                "page grain sits around 0.04 and reaches 0.05 on the noisiest "
                "patches. Half of all real patch borders are above 0.08, and "
                "the borders a misplaced box actually lands on read 0.20 and "
                "up. Together with a count of 2 above, 0.20 leaves a correctly "
                "placed grid completely silent."))
        self._scan_flank_cells_combo = NoScrollComboBox(grp)
        for _n in range(2, 21):
            self._scan_flank_cells_combo.addItem(str(_n), _n)
        _cur_c = int(s.get("scanner_flank_min_cells", 8))
        self._scan_flank_cells_combo.setCurrentIndex(
            max(0, self._scan_flank_cells_combo.findData(_cur_c)))
        self._scan_flank_cells_combo.setMinimumWidth(120)
        _row(7, tr("…needing this many sensing cells in a row (2–20):"),
             self._scan_flank_cells_combo,
             tr("How many sensing cells make an edge"),
             tr("In short: this protects you against grain and dust specks "
                "in the scan being mistaken for patch edges. Each patch is "
                "checked with a fine grid of small sensing cells; a patch "
                "border is only believed when at least this many cells "
                "light up TOGETHER, side by side in a straight row — "
                "because a border is a line, and a line crosses one cell "
                "after the next. Grain and dust can't do that: a speck "
                "lights a small clump, scattered noise lights lonely cells, "
                "and neither forms a straight row.\n\n"
                "This counts the small cells INSIDE one patch of the "
                "reading grid — not whole patches. (The setting above, "
                "\"Warn when this many patches sit on an edge\", counts "
                "whole patches.)\n\n"
                "The number counts real sensing cells, exactly as set: 6 "
                "means a straight run of 6 cells of the 30×30 sensing "
                "grid, 8 means 8 — the value is never converted or scaled. "
                "The maximum of 20 is 20 of the 30 cells along one side of "
                "that grid: two thirds of a patch have to lie on a straight "
                "colour change in a row before it can count as an edge.\n\n"
                "What to change: if a grainy or textured scan keeps "
                "flagging patches you know are clean, raise this — a real "
                "border crosses the whole box, so it easily lights more "
                "cells than any speck, and there is room up to 20. Lower it "
                "if you want the earliest possible warning and your scans "
                "are very clean.\n\n"
                "Why the default is 8: on real 600 dpi scans, grain and "
                "even a long narrow speck of grey inside a patch light "
                "straight runs of only a few cells, while a genuine border "
                "crosses the whole reading box — dozens of cells in a row. "
                "8 sits comfortably above anything grain produces and far "
                "below what every real border delivers.\n\n"
                "More than one group can be checked at once: if a speck "
                "lights a few cells in one corner while a real border "
                "crosses elsewhere in the same box, the border still "
                "counts — the speck can't mask it.\n\n"
                "How it works, if you're curious: every patch carries a "
                "30×30 grid of sensing cells (15×15 on low-resolution "
                "scans), spread over 85 % of the patch's width and height "
                "and shaped with the same equal-margin rule as the reading "
                "box, so the two always stay parallel. Only the cells "
                "around the reading box are awake — the box itself plus one "
                "thin ring just outside it, following your Patch sample "
                "area setting in and out — so a border is spotted the "
                "moment it comes close to what is actually being read. "
                "Each awake cell records the steepest colour change it "
                "sees. The hot cells must contain a straight run of at "
                "least this length, roughly parallel to a box side — the "
                "reading grid is aligned with the chart, so a genuine "
                "patch border always runs parallel to the box edges."))
        self._scan_avg_spin = NoScrollDoubleSpinBox(grp)
        self._scan_avg_spin.setRange(2.0, 60.0)
        self._scan_avg_spin.setDecimals(1)
        self._scan_avg_spin.setSingleStep(1.0)
        self._scan_avg_spin.setValue(float(s.get("scanner_selfcheck_avg", 12.0)))
        self._scan_avg_spin.setMinimumWidth(120)
        _row(1, tr("…and its average error is also above:"), self._scan_avg_spin,
             tr("Why BOTH numbers must be high"),
             tr("The self-check only warns when the peak AND the average fit "
                "error are both above their limits.\n\n"
                "A small Matrix profile legitimately fits a few extreme "
                "colours poorly — a perfectly aligned build can show a peak "
                "around 30 while its average stays low (about 8). A misplaced "
                "grid is different: it degrades EVERY patch, so the average "
                "climbs too (35–45 in real misalignment tests). Requiring "
                "both numbers keeps honest builds quiet without letting a "
                "shifted grid through."))
        g.setColumnStretch(3, 1)
        v.addWidget(grp)
        v.addStretch()
        return page

    def _build_margin_thresholds_tab(self) -> QWidget:
        """Per-(instrument, paper+orientation) minimum-margin editor.

        Instrument + paper pulldowns pick the active combo; below them a
        free-text description and a small L/R/T/B table hold that combo's
        editable minimums. The two behaviour checkboxes gate the Create Chart
        inspector; "Notify…" is greyed out while the frame is hidden.
        """
        page = QWidget()
        v = QVBoxLayout(page)
        v.setSpacing(10)
        v.setContentsMargins(12, 12, 12, 12)

        intro_row = QHBoxLayout()
        intro = QLabel(tr(
            "Limits for your measuring ruler / jig, per instrument, paper and "
            "orientation: the minimum page margins (mm, paper edge → patch area, "
            "in the printed orientation) and the maximum strip length. The Create "
            "Chart preview warns when a chart goes outside these. Editable starting "
            "points — adjust them to your own rig."), self)
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #909090; font-size: 11px;")
        intro_row.addWidget(intro, stretch=1)
        intro_row.addWidget(TooltipButton(
            tr("About instrument limits"),
            tr("These are your INSTRUMENT margins (not printer margins): how much "
               "blank white paper a chart should have around its patches so it's "
               "comfortable to measure.\n\n"
               "Why it matters: many spectrophotometers (i1Pro, ColorMunki…) are "
               "slid by hand along the chart, usually in a ruler or holder (a "
               "'jig' or 'rig'). If the patches sit too close to the edge of the "
               "page, the instrument can slip off the paper or bump the rail and "
               "the reading fails — so each edge needs a minimum margin.\n\n"
               "How to use this tab:\n"
               "• Pick an Instrument and a Paper size (with orientation) at the "
               "top — each combination has its own set of minimums.\n"
               "• Optionally type a Description, e.g. which ruler the values are "
               "for.\n"
               "• Set the smallest acceptable Left, Right, Top and Bottom margin "
               "(in mm) in the table. These ship with sensible starting values "
               "you can change to suit your own ruler.\n\n"
               "When you generate a chart, the Create Chart preview measures its "
               "actual margins and compares them to the values here: anything "
               "below the minimum is flagged. It's only a friendly heads-up — you "
               "can always print anyway.\n\n"
               "Tip about orientation: a sheet you place sideways in the jig is "
               "laid out the other way round on paper, so the margins are always "
               "in the orientation shown in the preview (which is what these "
               "values refer to). The two checkboxes above let you hide the whole "
               "feature, or keep it visible but turn the warning off."),
            self,
        ))
        v.addLayout(intro_row)

        # In-memory working copy; committed to settings on Save. Read via the
        # generic get + module parser so any settings object (incl. test doubles
        # with only get/set) works.
        from core.settings import parse_margin_thresholds
        self._margin_table = parse_margin_thresholds(
            self._settings.get("margin_thresholds", ""))

        # ---- behaviour checkboxes ----
        self._margin_show_check = QCheckBox(
            tr("Show the “Measured from Preview” frame in Create Chart"), self)
        # Sibling toggle for the other Create-Chart preview panel, kept next to
        # the "Measured from Preview" one since they sit side by side under the
        # preview (Knut, #93).
        self._layout_info_show_check = QCheckBox(
            tr("Show the “Chart layout information” panel in Create Chart"), self)
        self._margin_notify_check = QCheckBox(
            tr("Notify when a measured margin is below its threshold"), self)
        self._margin_show_check.toggled.connect(self._sync_margin_notify_enabled)
        v.addWidget(self._margin_show_check)
        v.addWidget(self._layout_info_show_check)
        v.addWidget(self._margin_notify_check)

        # ---- combo selectors ----
        sel = QGridLayout()
        sel.addWidget(QLabel(tr("Instrument:"), self), 0, 0)
        self._margin_instr = NoScrollComboBox(self)
        self._margin_instr.addItems(list(self._MARGIN_INSTRUMENTS))
        sel.addWidget(self._margin_instr, 0, 1)
        sel.addWidget(QLabel(tr("Paper size:"), self), 0, 2)
        self._margin_paper = NoScrollComboBox(self)
        self._margin_paper.addItems(
            [f"{p} {o}" for p in self._MARGIN_PAPERS for o in self._MARGIN_ORIENTS])
        sel.addWidget(self._margin_paper, 0, 3)
        sel.setColumnStretch(1, 1)
        sel.setColumnStretch(3, 1)
        v.addLayout(sel)

        # ---- description ----
        desc_row = QHBoxLayout()
        desc_row.addWidget(QLabel(tr("Description:"), self))
        self._margin_desc = QLineEdit(self)
        self._margin_desc.setPlaceholderText(
            tr("e.g. which ruler / jig these margins are for"))
        desc_row.addWidget(self._margin_desc, stretch=1)
        v.addLayout(desc_row)

        # ---- L/R/T/B value table (1-decimal mm, #85) ----
        grid = QGridLayout()
        self._margin_fields: dict[str, NoScrollDoubleSpinBox] = {}
        for col, (key, label) in enumerate(
                (("L", tr("Left")), ("R", tr("Right")),
                 ("T", tr("Top")), ("B", tr("Bottom")))):
            grid.addWidget(QLabel(label, self), 0, col, Qt.AlignmentFlag.AlignHCenter)
            sb = NoScrollDoubleSpinBox(self)
            sb.setRange(0, 100)
            sb.setDecimals(1)
            sb.setSingleStep(0.5)
            sb.setSuffix(" mm")
            sb.valueChanged.connect(self._on_margin_field_changed)
            self._margin_fields[key] = sb
            grid.addWidget(sb, 1, col)
        v.addLayout(grid)

        # ---- strip-length limit (the instrument's ruler / jig max, mm) ----
        # Configurable per combo (Knut #93). The Create Chart preview warns when a
        # strip is longer than this. 0 = use the instrument's built-in ruler.
        ruler_row = QHBoxLayout()
        ruler_row.addWidget(QLabel(tr("Strip length limit:"), self))
        self._margin_ruler = NoScrollDoubleSpinBox(self)
        self._margin_ruler.setRange(0, 2000)
        self._margin_ruler.setDecimals(0)
        self._margin_ruler.setSingleStep(10)
        self._margin_ruler.setSuffix(" mm")
        self._margin_ruler.setSpecialValueText(tr("instrument default"))
        self._margin_ruler.valueChanged.connect(self._on_margin_field_changed)
        ruler_row.addWidget(self._margin_ruler)
        ruler_row.addWidget(TooltipButton(
            tr("Strip length limit"),
            tr("The longest a single strip of patches may be (in mm) before "
               "the Create Chart preview warns that it won't fit your "
               "instrument's ruler or jig.\n\n"
               "The box starts out showing your instrument's own built-in "
               "limit, which is different for each device:\n"
               "  • i1Pro — 240 mm\n"
               "  • i1Pro 3+ — 220 mm\n"
               "  • ColorMunki — None (it reads strips without a ruler, so "
               "there is no fixed limit)\n"
               "  • SpectroScan — None (a flatbed table; it positions each "
               "patch itself, so strip length doesn't apply)\n\n"
               "You normally don't need to change this — it is here only if "
               "you use a non-standard ruler or jig and want ChromIQ to warn "
               "you against a different length. Type a value to set your own "
               "limit for the selected instrument, paper and orientation; set "
               "it back to the built-in number (or, where there is none, to "
               "“None”) to go back to the default."), self))
        ruler_row.addStretch(1)
        v.addLayout(ruler_row)

        # Restore-defaults button: re-seed the whole table to the shipped
        # defaults. Needed because changing the built-in defaults between
        # versions does NOT touch thresholds you've already saved (#82).
        reset_row = QHBoxLayout()
        reset_row.addStretch()
        reset_btn = QPushButton(tr("Restore default thresholds"), self)
        reset_btn.setToolTip(tr(
            "Reset every instrument/paper combination back to ChromIQ's "
            "built-in default margins. Use this to pick up new defaults from an "
            "update — your saved thresholds are otherwise kept as they were."))
        reset_btn.clicked.connect(self._restore_default_margin_thresholds)
        reset_row.addWidget(reset_btn)
        v.addLayout(reset_row)
        v.addStretch()

        # React to combo changes (load that combo's values).
        self._margin_instr.currentIndexChanged.connect(self._load_margin_combo)
        self._margin_paper.currentIndexChanged.connect(self._load_margin_combo)
        self._margin_desc.textChanged.connect(self._on_margin_desc_changed)
        # Preselect the combo active in Create Chart (#80), else the first
        # pulldown entries.
        combo = self._initial_margin_combo
        if combo:
            instr_label, paper_name, orient = combo
            i = self._margin_instr.findText(instr_label)
            if i >= 0:
                self._margin_instr.setCurrentIndex(i)
            j = self._margin_paper.findText(f"{paper_name} {orient}")
            if j >= 0:
                self._margin_paper.setCurrentIndex(j)
        self._loading_margin_combo = False
        self._load_margin_combo()
        return page

    def _current_margin_key(self) -> str:
        from core.settings import margin_combo_key

        instr = self._margin_instr.currentText()
        paper_orient = self._margin_paper.currentText()
        # paper_orient is "A4 Landscape" → split into paper + orientation
        parts = paper_orient.rsplit(" ", 1)
        paper, orient = (parts[0], parts[1]) if len(parts) == 2 else (paper_orient, "")
        return margin_combo_key(instr, paper, orient)

    def _load_margin_combo(self) -> None:
        """Populate the description + L/R/T/B fields from the selected combo."""
        self._loading_margin_combo = True
        entry = self._margin_table.get(self._current_margin_key(), {})
        self._margin_desc.setText(str(entry.get("desc", "")))
        for key, sb in self._margin_fields.items():
            try:
                sb.setValue(round(float(entry.get(key, 0)), 1))
            except (TypeError, ValueError):
                sb.setValue(0.0)
        # Strip-length limit: show the EFFECTIVE value — the user's override
        # if set, otherwise the instrument's own built-in ruler (240 mm i1Pro,
        # 220 mm i1Pro 3+, None for ColorMunki / SpectroScan). No hidden
        # hardcoded "instrument default" any more (Knut).
        from workflow.layout_engine.instruments import default_ruler_mm
        instr = self._margin_instr.currentText()
        default_ruler = default_ruler_mm(instr)
        try:
            override = round(float(entry.get("ruler", 0) or 0), 0)
        except (TypeError, ValueError):
            override = 0.0
        # "None" is shown at value 0 for instruments that have no ruler.
        self._margin_ruler.setSpecialValueText(tr("None"))
        self._margin_ruler.setValue(override if override > 0 else default_ruler)
        self._loading_margin_combo = False

    def _restore_default_margin_thresholds(self) -> None:
        """Re-seed the whole threshold table to the shipped defaults (#82)."""
        from core.settings import default_margin_thresholds
        self._margin_table = default_margin_thresholds()
        self._load_margin_combo()   # refresh the visible combo from the new table

    def _on_margin_field_changed(self) -> None:
        if getattr(self, "_loading_margin_combo", False):
            return
        self._commit_margin_combo()

    def _on_margin_desc_changed(self) -> None:
        if getattr(self, "_loading_margin_combo", False):
            return
        self._commit_margin_combo()

    def _commit_margin_combo(self) -> None:
        """Write the visible fields back into the in-memory table.

        A combo with all-zero margins and no description is dropped (treated as
        "no thresholds defined") so the inspector skips it cleanly.
        """
        key = self._current_margin_key()
        vals = {k: sb.value() for k, sb in self._margin_fields.items()}
        desc = self._margin_desc.text().strip()
        # The box shows the instrument's built-in ruler when unchanged; only a
        # value that DIFFERS from that default is stored as a real override, so
        # the box keeps tracking the built-in limit (and future default bumps)
        # unless the user deliberately changes it (Knut).
        from workflow.layout_engine.instruments import default_ruler_mm
        default_ruler = default_ruler_mm(self._margin_instr.currentText())
        box_ruler = self._margin_ruler.value() if getattr(self, "_margin_ruler", None) else 0
        ruler = 0 if round(box_ruler, 0) == round(default_ruler, 0) else box_ruler
        if not any(vals.values()) and not desc and not ruler:
            self._margin_table.pop(key, None)
            return
        entry = {k: v for k, v in vals.items()}
        entry["desc"] = desc
        if ruler:
            entry["ruler"] = ruler
        self._margin_table[key] = entry

    def _sync_margin_notify_enabled(self) -> None:
        """Notify-on-violation is meaningless when the frame is hidden."""
        self._margin_notify_check.setEnabled(self._margin_show_check.isChecked())

    def _sync_print_path_options(self) -> None:
        """Grey out the options that only apply to ChromIQ's own lp pipeline
        while the macOS print dialog is selected — that dialog is its own
        confirmation step, and no PS→PDF/TIFF fallback runs on its path."""
        if native_print_supported():
            lp_path_active = not self._native_print_check.isChecked()
            self._confirm_print_check.setEnabled(lp_path_active)
            self._pdf_fallback_check.setEnabled(lp_path_active)

    def _load_settings(self) -> None:
        s = self._settings
        self._argyll_edit.setText(s.get("argyll_bin_path", default_argyll_bin_dir()))
        self._folder_edit.setText(s.get("custom_output_path", ""))
        self._restore_tab_check.setChecked(s.get("restore_last_tab", True))
        self._restore_session_check.setChecked(bool(s.get("restore_last_session", False)))
        self._update_notify_check.setChecked(bool(s.get("update_notify", True)))
        self._themed_colors_check.setChecked(bool(s.get("gamut_themed_colors", True)))
        self._native_files_check.setChecked(bool(s.get("use_native_file_dialogs", False)))
        self._cal_mode_check.setChecked(bool(s.get("calibration_mode", False)))
        self._show_location_check.setChecked(
            bool(s.get("show_location_being_edited", True)))
        self._hide_log_check.setChecked(bool(s.get("hide_log_output", False)))
        # Scanner Limits — must follow Restore Factory Defaults too (Knut #108)
        self._scan_peak_spin.setValue(float(s.get("scanner_selfcheck_peak", 30.0)))
        self._scan_avg_spin.setValue(float(s.get("scanner_selfcheck_avg", 12.0)))
        self._scan_check_spin.setValue(float(s.get("scanner_check_agreement", 0.85)))
        self._scan_flank_spin.setValue(float(s.get("scanner_flank_limit", 0.20)))
        self._scan_flank_min_combo.setCurrentIndex(max(0, self._scan_flank_min_combo
            .findData(int(s.get("scanner_flank_min_boxes", 2)))))
        self._scan_flank_cells_combo.setCurrentIndex(max(0, self._scan_flank_cells_combo
            .findData(int(s.get("scanner_flank_min_cells", 8)))))
        self._chromiq_refine_check.setChecked(bool(s.get("chromiq_refinement", False)))
        self._averaging_check.setChecked(bool(s.get("averaging_enabled", False)))
        self._declutter_check.setChecked(bool(s.get("declutter_on_load", True)))
        self._splash_check.setChecked(bool(s.get("show_splash", True)))
        self._profile_engine_check.setChecked(bool(s.get("profile_engine_beta", False)))
        self._gammap_mode_combo.setCurrentIndex(
            max(0, self._gammap_mode_combo.findData(
                str(s.get("gammap_mode", "fast")))))
        # A no-change setChecked above may not emit toggled, so sync explicitly.
        self._gammap_mode_cell.setVisible(
            self._profile_engine_check.isChecked())
        self._chartread_engine_check.setChecked(
            str(s.get("chartread_engine", "argyll")) == "chromiq")
        self._engine_all_modes_check.setChecked(
            bool(s.get("engine_all_modes", False)))
        self._save_report_check.setChecked(
            bool(s.get("save_measurement_report", True)))
        self._report_avg_thr_spin.setValue(
            float(s.get("report_pass_threshold_avg", 2.0)))
        self._report_max_thr_spin.setValue(
            float(s.get("report_pass_threshold_max", 3.0)))
        self._report_title_prof_edit.setText(
            str(s.get("report_title_profiling",
                      "Measurement Report - Profiling of Printer")))
        self._report_title_verify_edit.setText(
            str(s.get("report_title_verification",
                      "Measurement Report - Verification of Profile")))
        self._report_add_profile_check.setChecked(
            bool(s.get("report_add_profile_name", True)))
        self._patch_warn_spin.setValue(
            float(s.get("patch_read_warn_de", 50.0)))
        self._patch_fence_check.setChecked(
            bool(s.get("patch_warn_outlier_fence", True)))
        self._cal_retries_spin.setValue(int(s.get("cal_auto_retries", 3)))
        self._fast_connect_check.setChecked(
            bool(s.get("fast_instrument_connect", True)))
        self._safenet_check.setChecked(bool(s.get("misalign_safenet", False)))
        self._native_print_check.setChecked(bool(s.get("use_native_print_dialog", False)))
        self._pdf_fallback_check.setChecked(bool(s.get("pdf_print_fallback", False)))
        self._confirm_print_check.setChecked(bool(s.get("confirm_before_printing", True)))
        self._sync_print_path_options()
        from data.patch_db import I1PRO_DEFAULT_PRESET_KEY
        i1pro_key = str(s.get("i1pro_default_preset", I1PRO_DEFAULT_PRESET_KEY))
        idx = self._i1pro_preset_combo.findData(i1pro_key)
        self._i1pro_preset_combo.setCurrentIndex(idx if idx >= 0 else 0)
        # Clip-border vs. layout engine are mutually exclusive — the engine
        # replaces the printtarg path, so the old ChromIQ clip-border can't be on
        # with it. The engine toggle now lives in Create Chart, so this dialog
        # enforces the rule from the *stored* setting on open: with the engine on,
        # force the clip-border off + disabled and remember its stored state.
        clip_on = bool(s.get("i1pro_chromiq_clip_style", False))
        if bool(s.get("use_chromiq_layout_engine", False)):
            self._clip_saved_state = clip_on
            self._chromiq_clip_check.setChecked(False)
            self._chromiq_clip_check.setEnabled(False)
        else:
            self.__dict__.pop("_clip_saved_state", None)
            self._chromiq_clip_check.setChecked(clip_on)
            self._chromiq_clip_check.setEnabled(True)
        self._grey_ref_spin.setValue(int(s.get("grey_ramp_reference", 560)))
        # Appearance: capture current value so Cancel can revert any live preview.
        current = str(s.get("appearance", "auto"))
        self._appearance_original = current
        idx = self._appearance_combo.findData(current)
        # Block signals so loading the saved value doesn't fire a preview.
        self._appearance_combo.blockSignals(True)
        self._appearance_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._appearance_combo.blockSignals(False)
        # Language: restart-to-apply, no preview — just select the saved code.
        lang = str(s.get("language", "en"))
        lang_idx = self._language_combo.findData(lang)
        self._language_combo.blockSignals(True)
        self._language_combo.setCurrentIndex(lang_idx if lang_idx >= 0 else 0)
        self._language_combo.blockSignals(False)
        self._language_restart_hint.setVisible(False)
        # Margin inspector behaviour checkboxes (the per-combo table is loaded
        # into the tab's own working copy in _build_margin_thresholds_tab).
        self._margin_show_check.setChecked(bool(s.get("margin_inspector_show", True)))
        self._layout_info_show_check.setChecked(bool(s.get("layout_info_show", True)))
        self._margin_notify_check.setChecked(bool(s.get("margin_violation_notify", True)))
        self._sync_margin_notify_enabled()

    def _apply_indicator_theme(self, mode: str) -> None:
        """Apply the neutral indicator colour to checkboxes, line-edit focus and
        tooltip ⓘ icons for the given resolved mode ('light'/'dark').

        Overrides the global APP_STYLESHEET ACCENT (SPEC_CYAN), which would read
        as the Build Profile cyan inside a dialog body where there's no tab
        accent to anchor it. Re-run on live theme preview so the colours switch
        without reopening the dialog.
          Light: masthead "Chrom" wordmark.  Dark: neutral grey (Restore border).
        """
        indicator = "#1c1b18" if mode == "light" else "#d0d0d0"
        # Shared with the Tools dialogs so every dialog highlights controls the
        # same neutral way (checkboxes, radios and the focus ring on text/number/
        # combo inputs).
        from ui.dialogs.tools_dialogs import neutral_controls_qss
        # neutral_controls_qss restyles :checked indicators in the neutral colour,
        # which would otherwise keep a *disabled* checked box looking active. Add a
        # higher-specificity :checked:disabled rule so it greys out like the rest
        # of the app (matching the global QCheckBox::indicator:disabled greys).
        dis_bg, dis_border = (
            ("#eeece8", "#d0ccc6") if mode == "light" else ("#1f1f1f", "#3a3a3a")
        )
        disabled_qss = (
            f"QCheckBox::indicator:checked:disabled {{"
            f" background: {dis_bg}; border-color: {dis_border}; }}"
        )
        self.setStyleSheet(neutral_controls_qss(indicator) + disabled_qss)
        for btn in self.findChildren(TooltipButton):
            btn._color_override = indicator
            btn._set_icon()

    def _on_appearance_preview(self, _index: int) -> None:
        """Apply the picked theme immediately without persisting it."""
        from ui.theme import apply_appearance
        app = QApplication.instance()
        if app is None:
            return
        # The dialog is parented to the main window — use that for masthead/title-bar updates.
        main_window = self.parent()
        setting = self._appearance_combo.currentData()
        mode = apply_appearance(app, main_window, str(setting))
        self._apply_indicator_theme(mode)

    def _on_language_changed(self, _index: int) -> None:
        # Language is restart-to-apply (strings are translated at widget
        # construction) — just surface the hint when the pick differs from
        # what's persisted.
        picked = str(self._language_combo.currentData())
        stored = str(self._settings.get("language", "en"))
        self._language_restart_hint.setVisible(picked != stored)

    def reject(self) -> None:  # type: ignore[override]
        # Revert any live theme preview to whatever was persisted on open.
        # Only when the theme was actually previewed to something different —
        # apply_appearance re-applies the app-wide stylesheet and re-polishes
        # every widget, which is slow, so skip it when nothing changed.
        original = getattr(self, "_appearance_original", None)
        if original is not None and str(self._appearance_combo.currentData()) != original:
            from ui.theme import apply_appearance
            app = QApplication.instance()
            if app is not None:
                apply_appearance(app, self.parent(), original)
        super().reject()

    # ------------------------------------------------------------------
    # Chart Layout tab (ChromIQ layout engine, issue #93)
    # ------------------------------------------------------------------
    # Labels mirror the printtarg -i combobox (data/parameters.yaml), so the
    # engine and printtarg show the same instrument names (Knut). Codes unchanged.
    # The four instruments ChromIQ actually supports end-to-end — matching the
    # Create Chart picker and the Instrument Limits tab. DTP41/DTP51 were listed
    # here only because the layout engine knows their geometry, but they were
    # never wired into chart creation or instrument limits (and aren't supported
    # — the extra testing isn't worth it), so they've been dropped (Basti/Knut).
    _LAYOUT_INSTRUMENTS = [
        ("i1", "i1Pro / i1Pro 2 / i1Pro 3"), ("p3", "i1Pro 3 Plus"),
        ("CM", "ColorMunki / i1Studio / ColorChecker Studio"),
        ("SS", "SpectroScan (flatbed)"),
    ]

    @staticmethod
    def _layout_modes(inst: str) -> list[tuple[str, str]]:
        # Share the engine panel's options so the two stay in sync (#93).
        from ui.dialogs.layout_options_panel import LayoutOptionsPanel
        return LayoutOptionsPanel.modes_for(inst)

    def _build_chart_layout_tab(self) -> QWidget:
        from core.preset_store import load_presets
        from workflow.layout_engine.presets import PresetStore

        page = QWidget()
        v = QVBoxLayout(page)
        v.setSpacing(10)
        v.setContentsMargins(12, 12, 12, 12)

        # The engine ON/OFF toggle moved to the Create Chart tab (above the
        # ChromIQ layout frame) so it's easy to switch engines per chart/preset
        # (Knut #93). It's kept here as a hidden widget purely so the existing
        # load/save plumbing keeps working; this tab now just edits the per-combo
        # DEFAULTS the engine uses.
        self._layout_engine_check = QCheckBox(self)
        self._layout_engine_check.setVisible(False)
        self._layout_engine_check.setChecked(
            bool(self._settings.get("use_chromiq_layout_engine", False)))
        moved_note = QLabel(tr(
            "The ChromIQ layout engine is switched on or off in the Create Chart "
            "tab, above the layout panel. Here you set the default layout each "
            "instrument and paper starts from."), self)
        moved_note.setWordWrap(True)
        moved_note.setStyleSheet("color: #909090; font-size: 11px;")
        v.addWidget(moved_note)

        # Everything below the master toggle lives in a body widget that is
        # greyed out (controls AND their labels) when the engine is off.
        self._layout_body = QWidget(self)
        v.addWidget(self._layout_body)
        v = QVBoxLayout(self._layout_body)
        v.setSpacing(10)
        v.setContentsMargins(0, 0, 0, 0)

        intro_row = QHBoxLayout()
        intro = QLabel(tr(
            "Default chart layout per instrument and paper. Pick a combination "
            "above; its values below are the starting point Create Chart uses, "
            "which you can still tweak per chart. Presets are saved as files you "
            "can back up or share."), self)
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #909090; font-size: 11px;")
        intro_row.addWidget(intro, stretch=1)
        intro_row.addWidget(TooltipButton(
            tr("About chart layout"),
            tr("This tab holds your DEFAULT chart layouts. Every combination of "
               "Instrument + Paper + Mode has its own saved set of values — so "
               "your i1Pro on A4 can differ from your ColorMunki on A3, and each "
               "remembers what you set.\n\n"
               "How to use it:\n"
               "• Pick an Instrument, a Paper size and a Mode at the top.\n"
               "• Adjust the patch and page settings below. The green line shows "
               "roughly how many patches fit on one sheet with those settings.\n"
               "• These are starting points: when you make a chart in Create "
               "Chart, it begins from these values and you can still tweak that "
               "one chart without changing the defaults here.\n\n"
               "What “Mode” means depends on the instrument — for the i1Pro it is "
               "whether a left clip border is printed; for the ColorMunki it is "
               "the reading density (hand-held vs the measuring rig); for the "
               "SpectroScan it is rectangular vs hexagonal patches. Each mode "
               "keeps its own preset.\n\n"
               "Your presets are saved as ordinary files (one per combination), "
               "so you can back them up, copy them between computers, or share "
               "them: use “Open presets folder”, or “Export…” / “Import…”. "
               "“Restore factory defaults” returns every combination to the "
               "values ChromIQ shipped with."),
            self))
        v.addLayout(intro_row)

        # working preset store (file-backed, like the manual-tab presets)
        self._layout_store = PresetStore.from_named_dict(
            load_presets("chart_layout", self._settings))
        self._loading_layout = False

        # ---- selectors ----
        sel = QGridLayout()
        sel.addWidget(QLabel(tr("Instrument:"), self), 0, 0)
        self._layout_instr = NoScrollComboBox(self)
        for key, label in self._LAYOUT_INSTRUMENTS:
            self._layout_instr.addItem(label, key)
        sel.addWidget(self._layout_instr, 0, 1)
        sel.addWidget(QLabel(tr("Paper:"), self), 0, 2)
        self._layout_paper = NoScrollComboBox(self)
        sel.addWidget(self._layout_paper, 0, 3)
        self._layout_mode_lbl = QLabel(tr("Mode:"), self)
        sel.addWidget(self._layout_mode_lbl, 1, 0)
        self._layout_mode = NoScrollComboBox(self)
        sel.addWidget(self._layout_mode, 1, 1)
        from ui.dialogs.layout_options_panel import LayoutOptionsPanel
        self._layout_mode_tip = TooltipButton(
            *LayoutOptionsPanel.mode_tooltip_for("i1"), self)
        sel.addWidget(self._layout_mode_tip, 1, 2)
        # Clip-border On/Off for CM/SS — same extra selector as Create Chart, so
        # the toggle is reachable here too (Knut, #93). i1/p3 use their Mode row.
        self._layout_clip_enable_lbl = QLabel(tr("Clip border:"), self)
        sel.addWidget(self._layout_clip_enable_lbl, 2, 0)
        self._layout_clip_enable = NoScrollComboBox(self)
        self._layout_clip_enable.addItem(tr("Off — more patches"), "off")
        self._layout_clip_enable.addItem(tr("On"), "on")
        sel.addWidget(self._layout_clip_enable, 2, 1)
        sel.setColumnStretch(1, 1)
        sel.setColumnStretch(3, 1)
        v.addLayout(sel)

        # ---- layout options (the SAME shared panel as Create Chart Manual,
        # so Settings defaults and per-chart edits can't drift) ----
        from ui.dialogs.layout_options_panel import LayoutOptionsPanel
        self._layout_panel = LayoutOptionsPanel(self)
        self._layout_panel.changed.connect(self._on_layout_field_changed)
        v.addWidget(self._layout_panel)

        self._layout_calc = QLabel("", self)
        self._layout_calc.setWordWrap(True)
        self._layout_calc.setStyleSheet("color: #1a8f3c; font-weight: 600;")
        v.addWidget(self._layout_calc)

        # ---- buttons ----
        btns = QHBoxLayout()
        reset_btn = QPushButton(tr("Restore factory defaults"), self)
        reset_btn.clicked.connect(self._restore_layout_defaults)
        folder_btn = QPushButton(tr("Open presets folder"), self)
        folder_btn.clicked.connect(self._open_layout_presets_folder)
        export_btn = QPushButton(tr("Export…"), self)
        export_btn.clicked.connect(self._export_layout_presets)
        import_btn = QPushButton(tr("Import…"), self)
        import_btn.clicked.connect(self._import_layout_presets)
        for b in (reset_btn, folder_btn, export_btn, import_btn):
            btns.addWidget(b)
        btns.addStretch()
        v.addLayout(btns)

        # ---- Strip indicator style (global; applies to all new charts) ----
        # The per-chart styling controls moved here from Create Chart (Knut #93):
        # font / size / style / rotation / alignment / offset / underline. These
        # are app-wide defaults for new charts; a saved preset still carries (and
        # restores) its own styling.
        v.addWidget(self._build_indicator_style_group())
        v.addStretch()

        # ---- wiring ----
        self._layout_instr.currentIndexChanged.connect(self._on_layout_instr_changed)
        self._layout_paper.currentIndexChanged.connect(self._load_layout_combo)
        self._layout_mode.currentIndexChanged.connect(self._load_layout_combo)
        self._layout_clip_enable.currentIndexChanged.connect(
            self._on_layout_clip_enable_changed)
        # panel.changed (wired above) drives _on_layout_field_changed

        # The defaults editor is always available now (the engine toggle moved to
        # Create Chart). The engine ⇄ old-clip-border mutual exclusion is applied
        # from the setting in _load_settings (and enforced live at the Create Chart
        # toggle), so nothing to gate here.
        # Populating the instrument/paper/mode combos fires their change signals,
        # each of which would run the (expensive) live layout estimate — several
        # thousand font text-measurements. Suspend it while the tab is being set
        # up and run it exactly once at the end, so opening Preferences is quick
        # (Basti: the window was slow to load).
        self._suspend_layout_calc = True
        # Populating the combos fires their change signals, each of which would
        # load a recipe into the panel and re-render the clip-strip preview image
        # — several times, all but the last discarded. Skip those redundant loads
        # during the build and do a single load for the final selection.
        self._building_layout_tab = True
        self._on_layout_instr_changed()      # populate paper+mode for the default
        self._preselect_layout_combo()       # then jump to the active combo (#93)
        self._building_layout_tab = False
        self._load_layout_combo()            # load the final selection once
        # Leave the estimate suspended: it's the expensive part (font-measured
        # layout math) and the Chart Layout tab isn't the tab Preferences opens
        # on, so there's nothing to show yet. It runs the first time the user
        # actually switches to this tab (see _on_settings_tab_changed), keeping
        # the window quick to open (Basti). The suspend flag stays False after,
        # so every later edit recomputes the estimate live as before.
        self._layout_estimate_pending = True

        # Re-home the printtarg (old-engine) i1Pro options here, greyed when the
        # ChromIQ engine is active (they have no effect then) (Knut #93).
        if getattr(self, "_i1pro_grp", None) is not None:
            engine_on = bool(self._settings.get("use_chromiq_layout_engine", False))
            self._i1pro_grp.setEnabled(not engine_on)
            self._i1pro_grp.setTitle(tr("i1Pro Chart Defaults (printtarg engine)"))
            page.layout().addWidget(self._i1pro_grp)
        return self._scroll_wrap(page)

    def _on_settings_tab_changed(self, _index: int) -> None:
        """Run the Chart Layout estimate the first time that tab is opened.

        The estimate (font-measured layout math) is suspended while the dialog
        is built, so opening Preferences stays quick. The moment the user
        switches to the Chart Layout tab, compute it once and re-enable live
        recomputation. Guarded so it runs at most once and only for that tab.

        It also keeps the audio device awake while the Sounds tab is open, so
        that pressing “Play” is heard whole rather than being clipped by the
        device starting up (#148) — which is how this fault was first noticed.
        """
        self._sync_sounds_audio_hold()
        if not getattr(self, "_layout_estimate_pending", False):
            return
        w = getattr(self, "_chart_layout_tab_widget", None)
        if w is not None and self._tabs.currentWidget() is w:
            self._layout_estimate_pending = False
            self._suspend_layout_calc = False
            self._update_layout_calc()

    # Underline-mode options shared with the Create Chart panel (key → label),
    # so the two stay in sync (Knut #93).
    _UNDERLINE_MODES = (
        ("off", "Off"), ("segments", "Coloured (5 segments)"),
        ("cycle", "Coloured (per strip)"), ("black", "Black"),
    )

    def _build_indicator_style_group(self) -> QWidget:
        """Global strip-indicator styling (font/size/style/rotation/alignment/
        offset/underline) — moved out of the per-chart panel (Knut #93). Wired to
        the ``strip_indicator_*`` / ``strip_underline_*`` settings keys; saved in
        ``_save``. The styling for every engine chart (presets don't override
        it — TabChart._current_layout_recipe overlays these values)."""
        s = self._settings
        grp = QGroupBox(tr("Strip indicator style (all new charts)"), self)
        g = QGridLayout(grp)
        g.setHorizontalSpacing(8)
        g.setVerticalSpacing(6)

        intro = QLabel(tr(
            "How the per-strip letter labels (A, B, C…) look on every new chart "
            "— including charts loaded from a saved preset."), self)
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #909090; font-size: 11px;")
        g.addWidget(intro, 0, 0, 1, 3)
        g.addWidget(TooltipButton(
            tr("Strip indicator style"),
            tr("These settings control the little letters printed above each "
            "strip of patches (A, B, C…) so you always know which strip you're "
            "measuring. They apply to every new chart, including charts loaded "
            "from a saved preset.\n\n"
            "  • Font & Size — the typeface and its size in points (12 pt is "
            "about the size of body text; “auto” lets ChromIQ pick a size that "
            "fits). Bold / Italic switch off automatically for fonts that don't "
            "offer them.\n"
            "  • Rotation — turn the label (0°, 90°, 180°, 270°); useful when a "
            "strip is very narrow.\n"
            "  • Alignment — left, centred or right over its strip.\n"
            "  • Label offset — nudge the label up or down (mm) relative to its "
            "strip.\n"
            "  • Underline — draws a line under each label, so misreads are "
            "easier to spot; the coloured options tint it, and Line thickness / "
            "Line distance set how thick it is and how far below the text it "
            "sits.\n\n"
            "Changing these here updates all future charts; charts you've "
            "already generated keep the style they were made with."),
            self), 0, 3, Qt.AlignmentFlag.AlignRight)

        # Font + size + bold/italic.
        g.addWidget(QLabel(tr("Font:"), self), 1, 0)
        self._isty_font = NoScrollComboBox(self)
        # Reuse the panel's font list so the choices match Create Chart exactly.
        self._layout_panel._populate_font_combo(self._isty_font)
        g.addWidget(self._isty_font, 1, 1)
        # Font size in points (Word/PowerPoint units), stored in mm — see
        # layout_options_panel.PT_PER_MM (Knut).
        self._isty_size = NoScrollDoubleSpinBox(self)
        self._isty_size.setRange(0.0, 72.0)
        self._isty_size.setDecimals(0)
        self._isty_size.setSingleStep(1)
        self._isty_size.setSuffix(" pt")
        self._isty_size.setSpecialValueText(tr("auto"))
        # Clean 4-column grid (label | control | label | control) with both
        # control columns the same width, filling the frame (Knut). Every
        # control expands so the boxes line up in two even columns.
        g.addWidget(QLabel(tr("Size:"), self), 1, 2, Qt.AlignmentFlag.AlignRight)
        g.addWidget(self._isty_size, 1, 3)

        # Bold / Italic on their own row so they don't unbalance the columns.
        self._isty_bold = QCheckBox(tr("Bold"), self)
        self._isty_italic = QCheckBox(tr("Italic"), self)
        sty_row = QHBoxLayout()
        sty_row.setContentsMargins(0, 0, 0, 0)
        sty_row.addWidget(self._isty_bold)
        sty_row.addWidget(self._isty_italic)
        sty_row.addStretch()
        _styw = QWidget(self)
        _styw.setLayout(sty_row)
        g.addWidget(QLabel(tr("Style:"), self), 2, 0, Qt.AlignmentFlag.AlignRight)
        g.addWidget(_styw, 2, 1, 1, 3)

        # Rotation + alignment.
        g.addWidget(QLabel(tr("Rotation:"), self), 3, 0, Qt.AlignmentFlag.AlignRight)
        self._isty_rotation = NoScrollComboBox(self)
        for _deg in (0, 90, 180, 270):
            self._isty_rotation.addItem(f"{_deg}°", _deg)
        g.addWidget(self._isty_rotation, 3, 1)
        g.addWidget(QLabel(tr("Alignment:"), self), 3, 2, Qt.AlignmentFlag.AlignRight)
        self._isty_align = NoScrollComboBox(self)
        for _k, _lbl in (("left", tr("Left")), ("center", tr("Centered")),
                         ("right", tr("Right"))):
            self._isty_align.addItem(_lbl, _k)
        g.addWidget(self._isty_align, 3, 3)

        # Label offset.
        g.addWidget(QLabel(tr("Label offset:"), self), 4, 0, Qt.AlignmentFlag.AlignRight)
        self._isty_offset = NoScrollDoubleSpinBox(self)
        self._isty_offset.setRange(-50.0, 50.0)
        self._isty_offset.setDecimals(1)
        self._isty_offset.setSingleStep(0.5)
        self._isty_offset.setSuffix(" mm")
        g.addWidget(self._isty_offset, 4, 1)

        # Underline mode + thickness + distance.
        g.addWidget(QLabel(tr("Underline:"), self), 5, 0, Qt.AlignmentFlag.AlignRight)
        self._isty_underline = NoScrollComboBox(self)
        for _k, _lbl in self._UNDERLINE_MODES:
            self._isty_underline.addItem(tr(_lbl), _k)
        g.addWidget(self._isty_underline, 5, 1)
        g.addWidget(QLabel(tr("Line thickness:"), self), 5, 2, Qt.AlignmentFlag.AlignRight)
        self._isty_ul_thick = NoScrollDoubleSpinBox(self)
        self._isty_ul_thick.setRange(0.1, 5.0)
        self._isty_ul_thick.setDecimals(1)
        self._isty_ul_thick.setSingleStep(0.1)
        self._isty_ul_thick.setSuffix(" mm")
        g.addWidget(self._isty_ul_thick, 5, 3)
        g.addWidget(QLabel(tr("Line distance:"), self), 6, 2, Qt.AlignmentFlag.AlignRight)
        self._isty_ul_gap = NoScrollDoubleSpinBox(self)
        self._isty_ul_gap.setRange(0.0, 20.0)
        self._isty_ul_gap.setDecimals(1)
        self._isty_ul_gap.setSingleStep(0.5)
        self._isty_ul_gap.setSuffix(" mm")
        g.addWidget(self._isty_ul_gap, 6, 3)
        # Both control columns equal width, filling the frame (Knut).
        g.setColumnStretch(1, 1)
        g.setColumnStretch(3, 1)
        for _w in (self._isty_font, self._isty_size, self._isty_rotation,
                   self._isty_align, self._isty_offset, self._isty_underline,
                   self._isty_ul_thick, self._isty_ul_gap):
            _w.setSizePolicy(QSizePolicy.Policy.Expanding,
                             _w.sizePolicy().verticalPolicy())

        # ---- load current values ----
        _fi = self._isty_font.findData(s.get("strip_indicator_font"))
        self._isty_font.setCurrentIndex(_fi if _fi >= 0 else 0)
        from ui.dialogs.layout_options_panel import mm_to_pt
        self._isty_size.setValue(mm_to_pt(float(s.get("strip_indicator_size_mm"))))
        self._isty_bold.setChecked(bool(s.get("strip_indicator_bold")))
        self._isty_italic.setChecked(bool(s.get("strip_indicator_italic")))
        _ri = self._isty_rotation.findData(int(s.get("strip_indicator_rotation")))
        self._isty_rotation.setCurrentIndex(_ri if _ri >= 0 else 0)
        _ai = self._isty_align.findData(s.get("strip_indicator_align"))
        self._isty_align.setCurrentIndex(_ai if _ai >= 0 else 0)
        self._isty_offset.setValue(float(s.get("strip_label_offset_mm")))
        _ui = self._isty_underline.findData(s.get("strip_underline_mode"))
        self._isty_underline.setCurrentIndex(_ui if _ui >= 0 else 0)
        self._isty_ul_thick.setValue(float(s.get("strip_underline_thickness_mm")))
        self._isty_ul_gap.setValue(float(s.get("strip_underline_gap_mm")))
        return grp

    def _save_indicator_style(self) -> None:
        """Persist the global strip-indicator styling controls."""
        if getattr(self, "_isty_font", None) is None:
            return
        s = self._settings
        s.set("strip_indicator_font", self._isty_font.currentData() or "JetBrains Mono")
        from ui.dialogs.layout_options_panel import pt_to_mm
        s.set("strip_indicator_size_mm", pt_to_mm(self._isty_size.value()))
        s.set("strip_indicator_bold", self._isty_bold.isChecked())
        s.set("strip_indicator_italic", self._isty_italic.isChecked())
        s.set("strip_indicator_rotation", int(self._isty_rotation.currentData() or 0))
        s.set("strip_indicator_align", self._isty_align.currentData() or "left")
        s.set("strip_label_offset_mm", float(self._isty_offset.value()))
        s.set("strip_underline_mode", self._isty_underline.currentData() or "off")
        s.set("strip_underline_thickness_mm", float(self._isty_ul_thick.value()))
        s.set("strip_underline_gap_mm", float(self._isty_ul_gap.value()))

    def _preselect_layout_combo(self) -> None:
        """Select the instrument/paper/mode the user is editing in Create Chart,
        so a preset saved under that combination is visible on open (#93)."""
        combo = self._initial_layout_combo
        if not combo:
            return
        inst, paper, mode = combo
        i = self._layout_instr.findData(inst)
        if i >= 0 and i != self._layout_instr.currentIndex():
            self._layout_instr.setCurrentIndex(i)   # repopulates paper+mode, loads
        elif i >= 0:
            self._on_layout_instr_changed()         # same instrument: refresh lists
        j = self._layout_paper.findData(paper)
        if j >= 0:
            self._layout_paper.setCurrentIndex(j)   # fires _load_layout_combo
        k = self._layout_mode.findData(mode)
        if k >= 0:
            self._layout_mode.setCurrentIndex(k)    # fires _load_layout_combo

    def _scroll_wrap(self, page: QWidget) -> QWidget:
        """Wrap a settings tab in a fading scroll area so every tab scrolls and
        shares the same backdrop (the tab pane is white, but a scroll area's
        viewport follows the window tint — so wrapping all tabs keeps them
        consistent) and gets the top/bottom fade the rest of the app uses."""
        from ui.fade_scroll import FadeScrollArea
        from ui.theme import resolve_mode
        scroll = FadeScrollArea(self, surface="dialog")
        scroll.set_appearance(resolve_mode(self._settings.get("appearance", "auto")))
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(FadeScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(page)
        return scroll

    def _on_layout_instr_changed(self) -> None:
        from workflow.layout_engine import papers
        self._loading_layout = True
        inst = self._layout_instr.currentData() or "i1"
        prev_paper = self._layout_paper.currentData()
        self._layout_paper.clear()
        for code, label, _ in papers.list_papers(inst, for_engine=True):
            self._layout_paper.addItem(label, code)
        i = self._layout_paper.findData(prev_paper)
        if i < 0:
            i = self._layout_paper.findData("A4")   # sane default, not A2 (index 0)
        self._layout_paper.setCurrentIndex(i if i >= 0 else 0)
        self._layout_mode.clear()
        for key, label in self._layout_modes(inst):
            self._layout_mode.addItem(label, key)
        from ui.dialogs.layout_options_panel import LayoutOptionsPanel
        self._layout_mode_lbl.setText(LayoutOptionsPanel.mode_label_for(inst))
        self._layout_mode_tip.set_content(*LayoutOptionsPanel.mode_tooltip_for(inst))
        # The extra clip-border On/Off selector is for CM/SS only.
        is_band = inst in ("CM", "SS")
        self._layout_clip_enable.setVisible(is_band)
        self._layout_clip_enable_lbl.setVisible(is_band)
        self._loading_layout = False
        self._load_layout_combo()

    def _layout_selection(self) -> tuple[str, str, str]:
        return (self._layout_instr.currentData() or "i1",
                self._layout_paper.currentData() or "A4",
                self._layout_mode.currentData() or "default")

    def _load_layout_combo(self) -> None:
        if getattr(self, "_building_layout_tab", False):
            return                           # one load at the end of the build
        inst, paper, mode = self._layout_selection()
        recipe = self._layout_store.get(inst, paper, mode)
        self._loading_layout = True
        self._layout_panel.set_recipe(recipe)
        # Mirror the loaded clip state into the CM/SS On/Off selector.
        i = self._layout_clip_enable.findData(
            "on" if self._layout_panel.clip_enabled() else "off")
        self._layout_clip_enable.setCurrentIndex(i if i >= 0 else 0)
        self._loading_layout = False
        self._update_layout_calc()

    def _on_layout_clip_enable_changed(self) -> None:
        if self._loading_layout:
            return
        self._layout_panel.set_clip_enabled(
            self._layout_clip_enable.currentData() == "on")
        # set_clip_enabled flips the panel's content mode → panel.changed →
        # _on_layout_field_changed persists it; nothing more to do here.

    def _recipe_from_fields(self):
        from workflow.layout_engine.presets import default_recipe
        inst, paper, mode = self._layout_selection()
        r = default_recipe(inst, paper, mode=mode)   # sets mode flags from selectors
        return self._layout_panel.apply_to_recipe(r)

    def _on_layout_field_changed(self, *_a) -> None:
        if self._loading_layout:
            return
        self._layout_store.set(self._recipe_from_fields())
        self._update_layout_calc()

    def _update_layout_calc(self) -> None:
        if getattr(self, "_suspend_layout_calc", False):
            return
        from workflow.layout_engine import geometry, instruments, papers, preflight
        try:
            r = self._recipe_from_fields()
            geom = instruments.geom_from_build_kwargs(r.build_kwargs())
            w_mm, h_mm = papers.dimensions_mm(r.paper)
            cap = geometry.patches_per_sheet(geom, w_mm, h_mm)
            layout = geometry.compute(geom, w_mm, h_mm, cap)
            rep = preflight.check(geom, layout)
            msgs = [(e, True) for e in rep.errors] + [(w, False) for w in rep.warnings]
            usable = h_mm - geom.margin_t - geom.margin_b
            if r.max_strip_mm and r.max_strip_mm > usable:
                msgs.append((tr("max strip length exceeds the usable page "
                                "length (~{u:.0f} mm)").format(u=usable), False))
            iw = preflight.indicator_width_warning(
                geom, r.dpi, font=r.indicator_font, size_mm=r.indicator_size_mm,
                show=r.show_strip_indicators)
            if iw:
                msgs.append((iw, False))
            html = ("<span style='color:#1a8f3c;font-weight:600'>"
                    + tr("≈ {n} patches per sheet").format(n=cap) + "</span>")
            for txt, is_err in msgs:
                colour = "#e05252" if is_err else "#c47f17"
                html += f"<br><span style='color:{colour}'>⚠ {txt}</span>"
            self._layout_calc.setText(html)
        except geometry.LayoutError as exc:
            self._layout_calc.setText(
                f"<span style='color:#e05252'>⚠ {exc}</span>")
        except Exception:
            self._layout_calc.setText("—")

    def _restore_layout_defaults(self) -> None:
        from workflow.layout_engine.presets import PresetStore
        self._layout_store = PresetStore()   # empty → get() returns shipped defaults
        self._load_layout_combo()
        self._reset_indicator_style_widgets()

    def _reset_indicator_style_widgets(self) -> None:
        """Reset the strip-indicator style group to the shipped defaults.

        Part of this page's "Restore factory defaults" — a user who picked an
        unfortunate label font/size had no way back, because the reset only
        covered the layout combos (#108 follow-up). Saved on OK like any edit."""
        if getattr(self, "_isty_font", None) is None:
            return
        from core.settings import DEFAULTS
        from ui.dialogs.layout_options_panel import mm_to_pt
        _fi = self._isty_font.findData(DEFAULTS["strip_indicator_font"])
        self._isty_font.setCurrentIndex(_fi if _fi >= 0 else 0)
        self._isty_size.setValue(mm_to_pt(float(DEFAULTS["strip_indicator_size_mm"])))
        self._isty_bold.setChecked(bool(DEFAULTS["strip_indicator_bold"]))
        self._isty_italic.setChecked(bool(DEFAULTS["strip_indicator_italic"]))
        _ri = self._isty_rotation.findData(int(DEFAULTS["strip_indicator_rotation"]))
        self._isty_rotation.setCurrentIndex(_ri if _ri >= 0 else 0)
        _ai = self._isty_align.findData(DEFAULTS["strip_indicator_align"])
        self._isty_align.setCurrentIndex(_ai if _ai >= 0 else 0)
        self._isty_offset.setValue(float(DEFAULTS["strip_label_offset_mm"]))
        _ui = self._isty_underline.findData(DEFAULTS["strip_underline_mode"])
        self._isty_underline.setCurrentIndex(_ui if _ui >= 0 else 0)
        self._isty_ul_thick.setValue(float(DEFAULTS["strip_underline_thickness_mm"]))
        self._isty_ul_gap.setValue(float(DEFAULTS["strip_underline_gap_mm"]))

    def _open_layout_presets_folder(self) -> None:
        from core.preset_store import reveal_in_file_manager, tab_dir
        reveal_in_file_manager(tab_dir("chart_layout"))

    def _export_layout_presets(self) -> None:
        import json
        from ui.widgets import save_file_dialog
        path = save_file_dialog(
            self, tr("Export layout presets"), tr("JSON files (*.json)"),
            start_path=str(Path.home() / "chromiq-layout-presets.json"))
        if not path:
            return
        Path(path).write_text(
            json.dumps(self._layout_store.as_named_dict(), indent=2),
            encoding="utf-8")

    def _import_layout_presets(self) -> None:
        import json
        from ui.widgets import open_file_dialog
        path = open_file_dialog(
            self, tr("Import layout presets"),
            name_filter=tr("JSON files (*.json)"),
            start_dir=str(Path.home()))
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except Exception as exc:
            log.warning("layout preset import failed: %s", exc)
            return
        if isinstance(data, dict):
            from workflow.layout_engine.presets import LayoutRecipe
            for k, vdict in data.items():
                if isinstance(vdict, dict):
                    self._layout_store.set(LayoutRecipe.from_dict(vdict))
            self._load_layout_combo()

    def _save_and_close(self) -> None:
        s = self._settings
        s.set("argyll_bin_path",       self._argyll_edit.text().strip())
        s.set("custom_output_path",    self._folder_edit.text().strip())
        s.set("restore_last_tab",          self._restore_tab_check.isChecked())
        s.set("restore_last_session",      self._restore_session_check.isChecked())
        s.set("update_notify",             self._update_notify_check.isChecked())
        s.set("gamut_themed_colors",       self._themed_colors_check.isChecked())
        s.set("use_native_file_dialogs",   self._native_files_check.isChecked())
        s.set("calibration_mode",          self._cal_mode_check.isChecked())
        s.set("show_location_being_edited",
              self._show_location_check.isChecked())
        s.set("hide_log_output",           self._hide_log_check.isChecked())
        s.set("chromiq_refinement",        self._chromiq_refine_check.isChecked())
        s.set("averaging_enabled",         self._averaging_check.isChecked())
        s.set("declutter_on_load",         self._declutter_check.isChecked())
        s.set("show_splash",               self._splash_check.isChecked())
        s.set("profile_engine_beta",       self._profile_engine_check.isChecked())
        s.set("gammap_mode",               self._gammap_mode_combo.currentData())
        s.set("chartread_engine",
              "chromiq" if self._chartread_engine_check.isChecked() else "argyll")
        s.set("engine_all_modes", self._engine_all_modes_check.isChecked())
        s.set("save_measurement_report", self._save_report_check.isChecked())
        s.set("report_pass_threshold_avg", float(self._report_avg_thr_spin.value()))
        s.set("report_pass_threshold_max", float(self._report_max_thr_spin.value()))
        s.set("report_title_profiling",
              self._report_title_prof_edit.text().strip()
              or "Measurement Report - Profiling of Printer")
        s.set("report_title_verification",
              self._report_title_verify_edit.text().strip()
              or "Measurement Report - Verification of Profile")
        s.set("report_add_profile_name", self._report_add_profile_check.isChecked())
        s.set("patch_read_warn_de", float(self._patch_warn_spin.value()))
        s.set("patch_warn_outlier_fence",
              bool(self._patch_fence_check.isChecked()))
        s.set("cal_auto_retries", int(self._cal_retries_spin.value()))
        s.set("fast_instrument_connect", self._fast_connect_check.isChecked())
        s.set("misalign_safenet", self._safenet_check.isChecked())
        s.set("use_native_print_dialog",   self._native_print_check.isChecked())
        s.set("pdf_print_fallback",        self._pdf_fallback_check.isChecked())
        s.set("confirm_before_printing",   self._confirm_print_check.isChecked())
        s.set("appearance",                str(self._appearance_combo.currentData()))
        s.set("language",                  str(self._language_combo.currentData()))
        s.set("i1pro_default_preset",      str(self._i1pro_preset_combo.currentData()))
        s.set("i1pro_chromiq_clip_style",  self._chromiq_clip_check.isChecked())
        s.set("grey_ramp_reference",       int(self._grey_ref_spin.value()))
        # Scanner-profiling misalignment thresholds (Settings → Scanner, #108).
        s.set("scanner_selfcheck_peak",    float(self._scan_peak_spin.value()))
        s.set("scanner_selfcheck_avg",     float(self._scan_avg_spin.value()))
        s.set("scanner_check_agreement",   float(self._scan_check_spin.value()))
        s.set("scanner_flank_limit",       float(self._scan_flank_spin.value()))
        s.set("scanner_flank_min_boxes",   int(self._scan_flank_min_combo.currentData()))
        s.set("scanner_flank_min_cells",   int(self._scan_flank_cells_combo.currentData()))
        s.set("profile_install_dir",       self._profile_dir_edit.text().strip())
        # Measurement sounds (#131): the user sounds folder + per-event choices.
        if hasattr(self, "_sound_dir_edit"):
            s.set("sound_folder", self._sound_dir_edit.text().strip())
        for _event, _combo in getattr(self, "_sound_combos", {}).items():
            s.set(f"sound_choice_{_event}", _combo.currentData())
        # Measurement pace (#131 Phase 2)
        if hasattr(self, "_pace_enable"):
            s.set("pace_hint_enabled", self._pace_enable.isChecked())
            for _key, _hz in self._pace_hz.items():
                s.set(f"pace_sample_hz_{_key}", float(_hz.value()))
            for _key, _mn in self._pace_min.items():
                s.set(f"pace_min_samples_{_key}", int(_mn.value()))
            for _key, _pp in self._pace_patches.items():
                s.set(f"pace_estimate_patches_{_key}", int(_pp.value()))
        from core.platform_paths import set_icc_install_override
        set_icc_install_override(self._profile_dir_edit.text())
        # Margin inspector: behaviour flags + the per-combo threshold table.
        self._commit_margin_combo()   # flush the currently-shown combo's edits
        s.set("margin_inspector_show",     self._margin_show_check.isChecked())
        s.set("layout_info_show",          self._layout_info_show_check.isChecked())
        s.set("margin_violation_notify",   self._margin_notify_check.isChecked())
        from core.settings import serialize_margin_thresholds
        s.set("margin_thresholds", serialize_margin_thresholds(self._margin_table))
        # Global strip-indicator styling (Knut #93): defaults for new charts.
        self._save_indicator_style()
        # ChromIQ layout engine (issue #93): toggle + file-backed presets.
        s.set("use_chromiq_layout_engine", self._layout_engine_check.isChecked())
        from core.preset_store import save_presets
        save_presets("chart_layout", self._layout_store.as_named_dict())
        log.info("Settings saved")
        self.accept()

    def _browse_argyll(self) -> None:
        d = open_dir_dialog(
            self, tr("Select ArgyllCMS bin directory"),
            start_dir=self._argyll_edit.text() or "/Applications",
        )
        if d:
            self._argyll_edit.setText(d)

    def _browse_folder(self) -> None:
        d = open_dir_dialog(
            self, tr("Select output folder"),
            start_dir=self._folder_edit.text() or str(Path.home()),
        )
        if d:
            self._folder_edit.setText(d)

    def _auto_detect(self) -> None:
        detected = find_argyll_bin_path()
        if detected:
            self._argyll_edit.setText(str(detected))
            self._argyll_status.setStyleSheet("color: #4caf50;")
            self._argyll_status.setText(tr("Auto-detected at {detected}").format(detected=detected))
        else:
            self._argyll_status.setStyleSheet("color: #ff5252;")
            self._argyll_status.setText(
                tr("ArgyllCMS not found in any known location. "
                "Install it or set the path manually.")
            )
        log.info("ArgyllCMS auto-detect: %s", detected)

    def _test_argyll(self) -> None:
        from core.resource_path import argyll_binary
        bin_dir = Path(self._argyll_edit.text().strip())
        results = []
        for tool in ("targen", "printtarg", "chartread", "colprof",
                     "profcheck", "printcal", "applycal", "iccgamut", "viewgam"):
            p = bin_dir / argyll_binary(tool)
            if tool == "chartread":
                # chartread probes USB hardware even with -?, causing a hang.
                # Existence + executable check is sufficient here.
                executable = p.exists() and (_sys.platform == "win32" or os.access(str(p), os.X_OK))
                if executable:
                    results.append(f"✓ {tool}")
                else:
                    results.append(f"✗ {tool} (not found)")
                continue
            if p.exists():
                try:
                    subprocess.run(
                        [str(p), "-?"], capture_output=True, timeout=5,
                        stdin=subprocess.DEVNULL,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    )
                    results.append(f"✓ {tool}")
                except Exception:
                    results.append(f"✗ {tool} (error)")
            else:
                results.append(f"✗ {tool} (not found)")
        msg = "  ".join(results)
        all_ok = all(r.startswith("✓") for r in results)
        self._argyll_status.setStyleSheet(
            "color: #4caf50;" if all_ok else "color: #ff9800;"
        )
        self._argyll_status.setText(msg)
        log.info("ArgyllCMS test: %s", msg)

    def _open_argyll_download(self) -> None:
        self._argyll_status.setStyleSheet("")
        if _sys.platform == "win32":
            hint = "win64 for x64 (Intel/AMD) or arm64 for ARM-based devices (Snapdragon)"
        elif _sys.platform == "darwin":
            hint = "arm64 for Apple Silicon, osx64 for Intel"
        else:
            hint = "the binary tar.bz2 matching your distro's architecture (x86_64 or aarch64) — " \
                   "or install via your package manager (e.g. sudo apt install argyll)"
        self._argyll_status.setText(
            tr("Opening argyllcms.com — download the latest version ({hint}), then unpack and set the bin path above.").format(hint=hint)
        )
        QDesktopServices.openUrl(QUrl(argyll_download_page()))

    def _show_usb_installer(self) -> None:
        if _sys.platform != "win32":
            return
        from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout
        from core.usb_driver_installer import (
            enumerate_connected, install_winusb, launch_zadig, unbound_targets,
        )
        from core.resource_path import resource_path as _rp
        from ui.widgets import tint_dialog_primary

        _wdi_available = _rp("assets/wdi_simple.exe").exists()

        _COLOR = "#56d6a5"
        _REFRESH = 2   # custom dlg.done() code, distinct from Accepted(1)/Rejected(0)

        while True:
            devices = enumerate_connected()
            needs_install = [d for d in devices if not d.has_winusb]

            dlg = QDialog(self)
            dlg.setWindowTitle(tr("Install USB Driver"))
            dlg.setMinimumWidth(500)
            layout = QVBoxLayout(dlg)
            layout.setSpacing(14)
            layout.setContentsMargins(24, 20, 24, 20)

            if not devices:
                msg_text = (
                    "<b>No colorimeter detected.</b><br><br>"
                    "Make sure your device is plugged in via USB, "
                    "then click <b>Refresh</b>."
                )
            else:
                lines = [
                    f"&nbsp;&nbsp;• {d.name} — "
                    f"<i>{'WinUSB ✓' if d.has_winusb else 'driver not installed'}</i>"
                    for d in devices
                ]
                if not needs_install:
                    # Every detected device already has a WinUSB/libusb0 driver.
                    # Don't promise an installer the old code wouldn't show a
                    # button for; explain that and still offer a manual repair
                    # path (forum #148275: dialog mentioned Zadig but had no
                    # button when the device reported the driver as installed).
                    action_text = (
                        "The driver is already installed for the device(s) above. "
                        "If ChromIQ or Argyll still can't open your instrument, click "
                        "<b>Reinstall Driver</b> to run the installer again."
                    )
                elif _wdi_available:
                    action_text = (
                        "Click <b>Install Driver</b> to install the Microsoft WinUSB driver "
                        "automatically. A Windows security prompt will appear — click Yes to "
                        "continue.<br><br>"
                        "<i>No test-signing mode required. Works on x64 and ARM64.</i>"
                    )
                else:
                    action_text = (
                        "Click <b>Open Zadig</b> and ChromIQ will launch <b>Zadig</b>, a free "
                        "USB driver tool. In Zadig:<br>"
                        "&nbsp;&nbsp;1. Click <b>Options → List All Devices</b><br>"
                        "&nbsp;&nbsp;2. Find your colorimeter in the dropdown<br>"
                        "&nbsp;&nbsp;3. Select <b>WinUSB</b> as the driver and click "
                        "<b>Install Driver</b>"
                    )
                msg_text = (
                    "<b>Connected colorimeter(s):</b><br>"
                    + "<br>".join(lines)
                    + "<br><br>"
                    + action_text
                )

            msg = QLabel(msg_text, dlg)
            msg.setWordWrap(True)
            layout.addWidget(msg)

            btn_box = QDialogButtonBox()
            if devices:
                if not needs_install:
                    btn_label = "Reinstall Driver" if _wdi_available else "Open Zadig"
                else:
                    btn_label = "Install Driver" if _wdi_available else "Open Zadig"
                install_btn = btn_box.addButton(btn_label, QDialogButtonBox.ButtonRole.AcceptRole)
                install_btn.setObjectName("primary")
            refresh_btn = btn_box.addButton(tr("Refresh"), QDialogButtonBox.ButtonRole.ResetRole)
            refresh_btn.clicked.connect(lambda checked=False, d=dlg: d.done(_REFRESH))
            btn_box.addButton(QDialogButtonBox.StandardButton.Close)
            # The install/reinstall/Open-Zadig button uses AcceptRole, which
            # fires QDialogButtonBox.accepted — wire it to the dialog's accept()
            # or clicking it does nothing (the dialog never returns Accepted).
            btn_box.accepted.connect(dlg.accept)
            btn_box.rejected.connect(dlg.reject)
            layout.addWidget(btn_box)
            tint_dialog_primary(dlg, _COLOR)

            result = dlg.exec()

            if result == _REFRESH:
                continue   # rebuild with fresh device list

            if result != QDialog.DialogCode.Accepted or not devices:
                break   # Close button or nothing connected

            # ---- run installation ----
            # "Reinstall Driver" (no device needs install) repairs every detected
            # device; otherwise only the ones missing a driver are targeted.
            targets = needs_install or devices
            if _wdi_available:
                ran_ok = all(install_winusb(d) for d in targets)
                # wdi-simple can report success (exit 0) without actually binding
                # the driver to the live device — a stale ghost instance from a
                # previous USB port can misdirect it. Verify by re-enumerating
                # before claiming success, and fall back to Zadig if it didn't bind.
                still_unbound = unbound_targets(targets)
                if ran_ok and not still_unbound:
                    outcome_text = "WinUSB driver installed successfully."
                    offer_zadig = False
                elif not ran_ok:
                    outcome_text = (
                        "Automatic installation failed or was cancelled.<br>"
                        "Click <b>Try Zadig</b> to install it manually using the guided tool."
                    )
                    offer_zadig = True
                else:
                    names = ", ".join(d.name for d in still_unbound) or "the instrument"
                    outcome_text = (
                        "Windows reported the install finished, but the driver still "
                        f"isn't bound to {names}. This often happens when the device "
                        "was previously plugged into a different USB port.<br><br>"
                        "Click <b>Try Zadig</b> to install it reliably: pick your "
                        "instrument in Zadig, choose <b>WinUSB</b> (or libusb-win32), "
                        "then click <b>Replace Driver</b>. Unplugging and replugging the "
                        "instrument first can also help."
                    )
                    offer_zadig = True
            else:
                status = launch_zadig()
                if status == "launched":
                    outcome_text = (
                        "Zadig is open. Select your colorimeter, choose WinUSB, "
                        "then click Install Driver."
                    )
                elif status == "download_page":
                    outcome_text = (
                        "Zadig isn't bundled with this build, so its download page "
                        "has been opened in your browser.<br>"
                        "Download and run <b>Zadig</b>, then: Options → List All Devices → "
                        "select your colorimeter → choose WinUSB → Install Driver."
                    )
                else:
                    outcome_text = (
                        "Could not open Zadig or its download page. Visit "
                        "<b>https://zadig.akeo.ie</b> manually, or try running ChromIQ "
                        "as Administrator."
                    )
                offer_zadig = False

            outcome_dlg = QDialog(self)
            outcome_dlg.setWindowTitle(tr("Driver Installation"))
            outcome_dlg.setMinimumWidth(420)
            ol = QVBoxLayout(outcome_dlg)
            ol.setContentsMargins(24, 20, 24, 20)
            ol.setSpacing(14)
            lbl = QLabel(outcome_text, outcome_dlg)
            lbl.setWordWrap(True)
            ol.addWidget(lbl)
            obox = QDialogButtonBox()
            if offer_zadig:
                zadig_btn = obox.addButton(tr("Try Zadig"), QDialogButtonBox.ButtonRole.AcceptRole)
                zadig_btn.setObjectName("primary")
                zadig_btn.clicked.connect(lambda: launch_zadig())
            obox.addButton(QDialogButtonBox.StandardButton.Ok)
            obox.accepted.connect(outcome_dlg.accept)
            obox.rejected.connect(outcome_dlg.reject)
            ol.addWidget(obox)
            outcome_dlg.exec()
            break

    def _restore_defaults(self) -> None:
        self._settings.reset_to_defaults()
        self._load_settings()
        # The log panels are sized from a setting that has just been reset, and
        # they are showing whatever the user dragged them to — so they have to
        # be told, or the reset would change the value and leave the screen as
        # it was (Basti: "resetting to factory defaults should restore it").
        from ui.widgets import refresh_log_panes_from_settings
        refresh_log_panes_from_settings()
        log.info("Factory defaults restored")

    def _check_for_updates(self) -> None:
        self._update_btn.setEnabled(False)
        self._update_btn.setText(tr("Checking…"))
        self._update_status.setText("")

        self._update_checker = UpdateChecker(self)
        self._update_checker.update_available.connect(self._on_update_available)
        self._update_checker.up_to_date.connect(self._on_up_to_date)
        self._update_checker.check_failed.connect(self._on_update_failed)
        self._update_checker.check_async()

    def _on_update_available(self, latest: str) -> None:
        self._update_btn.setEnabled(True)
        self._update_btn.setText(tr("Check for Updates"))
        self._update_status.setStyleSheet("font-size: 11px; color: #e67e00;")
        self._update_status.setText(
            tr("{latest} available — <a href=\"{_RELEASES_PAGE}\">open GitHub Releases</a>").format(latest=latest, _RELEASES_PAGE=_RELEASES_PAGE)
        )
        self._update_status.setOpenExternalLinks(True)

    def _on_up_to_date(self) -> None:
        self._update_btn.setEnabled(True)
        self._update_btn.setText(tr("Check for Updates"))
        self._update_status.setStyleSheet("font-size: 11px; color: #4caf50;")
        self._update_status.setText(tr("You're up to date."))

    def _on_update_failed(self, reason: str) -> None:
        self._update_btn.setEnabled(True)
        self._update_btn.setText(tr("Check for Updates"))
        self._update_status.setStyleSheet("font-size: 11px; color: #888;")
        self._update_status.setText(tr("Check failed: {reason}").format(reason=reason))
