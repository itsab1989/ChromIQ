"""Tab 2: Print Chart."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSplitter,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from core.logger import get_logger
from core.platform_paths import file_manager_name
from core.platform_paths import is_linux, is_macos, is_windows
from ui.dialogs.preflight_dialog import PreflightDialog
from ui.fade_scroll import FadeScrollArea
from ui.tab_header import TabHeader
from ui.tiff_preview import TiffPreview, _find_sidecar_channels
from ui.tooltip_button import TooltipButton
from ui.widgets import NoScrollComboBox, PatchGridButton, info_box_qss, load_refresh_icon, open_file_dialog, set_accent_html, spectrum_cell
from workflow.cups_printer import CupsRawPrinter
from workflow.page_geometry import (
    ORIENTATION_LANDSCAPE,
    check_size_mismatch,
    compute_orientation,
    read_tiff_dimensions_points,
)
from workflow.print_manager import PrintModule

# CUPS option names that represent a paper-size selection — used to find which
# combo value to look up in the PPD when computing orientation / mismatch.
_PAGE_SIZE_KEYS = {"EPIJ_Size", "media", "PageSize"}
# Option names whose "on" value means borderless is enabled (native vendor
# toggles + the synthetic key surfaced by PrintModule for drivers that
# encode borderless in PageSize variants or EPIJ_PSrc).
_BORDERLESS_KEYS = {
    "EPIJ_Brlss", "CNBorderless", "BorderlessPrint", "Borderless",
    "__BORDERLESS__",
}


def _borderless_selected(selected_opts: dict[str, str]) -> bool:
    """True when the current option selection requests a borderless print.

    Covers all three ways drivers encode it: a dedicated on/off toggle
    (incl. ChromIQ's synthetic one), Epson's EPIJ_PSrc=3 page-setup value,
    and borderless PageSize variants picked directly (e.g. "A4.FullBleed").
    """
    from workflow.print_manager import (
        _BORDERLESS_SIZE_SUFFIXES,
        _EPSON_PSRC_BORDERLESS,
    )
    if any(
        selected_opts.get(k, "").lower() in ("true", "on", "yes", "1")
        for k in _BORDERLESS_KEYS
    ):
        return True
    if selected_opts.get("EPIJ_PSrc", "") == _EPSON_PSRC_BORDERLESS:
        return True
    return any(
        selected_opts.get(k, "").endswith(_BORDERLESS_SIZE_SUFFIXES)
        for k in _PAGE_SIZE_KEYS
    )

if TYPE_CHECKING:
    from core.settings import AppSettings

log = get_logger(__name__)
from ui.styles import SPEC_AMBER, TAB_COLORS
from core.i18n import tr


_TT_TITLE_PRINT = "Step 2 — Print the chart"

_TT_BODY_PRINT_MACOS_BYPASS = (
    "This step sends the TIFF from step 1 straight to your printer with "
    "all of macOS's colour management turned off. ChromIQ converts the "
    "chart to PostScript and sends it via the CUPS \"lp\" command, "
    "bypassing ColorSync and the driver's own colour matching. That's "
    "deliberate: to profile a printer we need to see how it behaves on "
    "its own, before any correction.\n\n"
    "Before you print:\n"
    "• Load the exact paper you chose in step 1. Different paper = "
    "different profile.\n"
    "• Make sure the printer is on, has ink, and is selected below.\n"
    "• Use the same ink, paper, and print settings every time you "
    "re-profile this printer — the profile only matches that recipe.\n\n"
    "How to use this screen:\n"
    "• Pick the printer and paper size. Quality should usually be the "
    "highest setting you'll print at in real use.\n"
    "• Click \"Print\". No print dialog will appear — the chart goes "
    "straight to the queue.\n\n"
    "After printing: let the print dry fully (at least 1 hour, 24 h for "
    "best accuracy with pigment inks) before measuring. Wet ink reads "
    "wrong.\n\n"
    "If you'd rather use the macOS print dialog (e.g. to pick a specific "
    "paper feed), enable \"Use default macOS printer dialog\" in Preferences."
)

_TT_BODY_PRINT_MACOS_NATIVE = (
    "This step opens macOS's standard print dialog so you can pick paper "
    "feed, media type, quality, and copies yourself.\n\n"
    "ChromIQ turns off the printer's colour management for you. It tells the "
    "system the chart is already in the printer's own colour space (so no "
    "colour transform is applied) and switches the driver to \"no colour "
    "correction\" — the same thing dedicated tools like Print-Tool do. The "
    "dialog's \"Color Matching\" pane opens greyed out as a result; that's "
    "expected and correct.\n\n"
    "Before you print:\n"
    "• Load the exact paper you chose in step 1.\n"
    "• Make sure the printer is on, has ink, and is selected.\n\n"
    "How to use this screen:\n"
    "• Click \"Print\". The macOS print dialog appears.\n"
    "• Pick the right paper / media type and print quality.\n"
    "• You don't need to touch any colour setting — just don't go out of "
    "your way to switch an ICC profile or rendering intent back on.\n"
    "• Never click Cancel/Abort in any pane or sub-window — always close them "
    "with OK. Cancel reverts the colour-off setting; OK keeps it.\n\n"
    "Prefer ChromIQ to print straight to the queue with no dialog? Untick "
    "\"Use default macOS printer dialog\" in Preferences to use the lp path instead "
    "— it also forces colour management off.\n\n"
    "Let the print dry fully (1 h minimum, 24 h for pigment inks) before "
    "measuring."
)

_TT_BODY_PRINT_LINUX = (
    "This step sends the TIFF from step 1 straight to your printer via "
    "CUPS, with all colour management turned off. ChromIQ converts the "
    "chart to PostScript and sends it through the \"lp\" command in raw "
    "mode, so the printer's own driver corrections don't touch the "
    "patches. That's deliberate: to profile a printer we need to see how "
    "it behaves on its own, before any correction.\n\n"
    "Before you print:\n"
    "• Load the exact paper you chose in step 1. Different paper = "
    "different profile.\n"
    "• Make sure the printer is on, has ink, and shows up in CUPS "
    "(the system print queue). If you don't see it below, check "
    "System Settings → Printers, or visit http://localhost:631.\n"
    "• Use the same ink, paper, and print settings every time you "
    "re-profile this printer — the profile only matches that recipe.\n\n"
    "How to use this screen:\n"
    "• Pick the printer and paper size. Quality should usually be the "
    "highest setting you'll print at in real use.\n"
    "• Click \"Print\". No print dialog will appear — the chart goes "
    "straight to the CUPS queue.\n\n"
    "After printing: let the print dry fully (at least 1 hour, 24 h for "
    "best accuracy with pigment inks) before measuring. Wet ink reads "
    "wrong.\n\n"
    "Note: on Linux there is no native dialog option — ChromIQ always "
    "prints via the CUPS bypass path, which is the right choice for "
    "profiling anyway."
)

_TT_BODY_PRINT_WINDOWS = (
    "This step opens Windows' standard print dialog so you can pick the "
    "printer and its options. IMPORTANT: ChromIQ cannot disable the "
    "printer driver's colour management for you on Windows — you must "
    "turn it off yourself before printing, or the printer will apply "
    "its own corrections and the chart will be unusable for profiling.\n\n"
    "Before you print:\n"
    "• Load the exact paper you chose in step 1.\n"
    "• Make sure the printer is on, has ink, and is selected.\n\n"
    "How to use this screen:\n"
    "• Click \"Print\" to open the dialog.\n"
    "• In the dialog, open the printer's Properties / Preferences and "
    "find its colour-management section. Set it to OFF / \"No Color "
    "Adjustment\" / \"Application Managed Colors\":\n"
    "    – Epson:  \"Epson Color Controls\" → Off (No Color Adjustment)\n"
    "    – Canon:  \"Color Options\" → Manual → None\n"
    "    – HP:     \"Color Options\" → Application Managed Colors\n"
    "    – Others: look for \"No Color Management\", \"Off\", or "
    "\"Application Controlled\"\n"
    "• Pick the right paper / media type and print quality. Confirm "
    "colour management is OFF before clicking Print.\n\n"
    "After printing: let the print dry fully (1 h minimum, 24 h for "
    "pigment inks) before measuring."
)


# ---------------------------------------------------------------------------
# Feature A (#130) — the §6 help and state texts of
# docs/design/verification_printing_and_target.md. The mockup generator
# (scripts/mockup_cm_verification_print.py) renders THESE constants, so the
# document's pictures and the app cannot drift apart.
# ---------------------------------------------------------------------------

_CM_COLOUR_HELP_TITLE = "Printing this chart through your profile"
_CM_COLOUR_HELP_BODY = (
    "This decides how the colours on this sheet are worked out before it is "
    "printed — and it is the setting that makes a verification mean "
    "something.\n\n"
    "What a verification is for. When you built your profile, you taught "
    "ChromIQ how your printer and this paper behave together. A verification "
    "asks the follow-up question: does the printer still do what the profile "
    "says it does? Ink settles, paper batches differ, printheads age — so it "
    "is worth checking, and worth checking the same way every time.\n\n"
    "Through the profile (recommended). ChromIQ looks up, for every "
    "single patch on the sheet, the exact amount of each ink your profile "
    "predicts will produce that colour. Those amounts are what gets printed. "
    "So the sheet coming out of your printer is your profile's own prediction, "
    "made real — and when you measure it, the difference between what was "
    "promised and what landed on the paper is exactly the number you are "
    "looking for. Pick this one unless you have a particular reason not to.\n\n"
    "Raw — no profile. The chart's own numbers go to the printer "
    "untouched, with no profile involved anywhere. This is the right way to "
    "print a chart you are going to build a profile from, because it shows "
    "the printer's raw behaviour. It is the wrong way to check a profile, "
    "because no profile took part — the measurement would describe your "
    "printer, not the profile you wanted to test.\n\n"
    "You do not have to change anything in the print dialog. Whichever you "
    "choose, ChromIQ does all of the colour work itself and hands the printer "
    "a finished sheet, with the printer's own colour adjustment switched off. "
    "That is deliberate: if the printer driver also tried to adjust the "
    "colours, they would be converted twice, the sheet would be wrong, and "
    "nothing afterwards could tell that it had happened.\n\n"
    "Your choice is written onto the report next to the results, because two "
    "sheets printed different ways cannot be compared with each other — and "
    "six months from now, nobody remembers which way a sheet was printed.\n\n"
    "There is also a third way that does not use this tab at all: print the "
    "chart from your own application — Photoshop, for example — with this "
    "run's profile applied there. That checks your everyday printing chain "
    "end to end. When you measure such a sheet, ChromIQ asks how it was "
    "printed and then judges it relative to the sheet's own paper white, "
    "because prints made that way map white to the paper.\n\n"
    "Default: through the profile."
)

_CM_INTENT_HELP_TITLE = "Which rendering intent to print with"
_CM_INTENT_HELP_BODY = (
    "Your printer cannot make every colour that exists — no printer can. "
    "Rendering intent is the rule for what happens to the colours it cannot "
    "reach.\n\n"
    "Relative colorimetric (recommended). Every colour your printer can "
    "actually make is reproduced exactly, and the few it cannot reach are "
    "moved to the closest colour it can manage. Paper white is treated as "
    "white. This is the usual choice for checking a profile, because it asks "
    "“did you hit the colours you could hit?” without punishing the "
    "printer for the ones nobody could print.\n\n"
    "Absolute colorimetric. The same, except that the paper’s own shade "
    "counts too. If your paper is slightly warm or slightly blue, that shows "
    "up as an error on every patch, so the numbers come out higher. Choose "
    "this when you have to match figures somebody else produced this way, or "
    "when the exact paper white matters to you.\n\n"
    "Perceptual and Saturation are meant for photographs and graphics rather "
    "than for measurement. They deliberately shift colours to look pleasing, "
    "which is the opposite of what a measurement wants, so they are here for "
    "completeness rather than for everyday use.\n\n"
    "Whichever you pick is written on the report, because a colour difference "
    "means nothing unless you know how it was produced.\n\n"
    "Default: relative colorimetric."
)

_CM_ROUTE_HELP_TITLE = "Printing this chart somewhere other than ChromIQ"
_CM_ROUTE_HELP_BODY = (
    "Pick this when you would rather drive the printer from an application "
    "you trust. ChromIQ then shows you where the sheets are and exactly what "
    "that application must be set to, and prints nothing itself.\n\n"
    "There is one rule, and everything depends on it: nothing between here "
    "and the paper may change the colours. The sheets ChromIQ hands over are "
    "already finished — if another application converts them again, it prints "
    "different colours, your measurement describes those different colours, "
    "and nothing afterwards can tell that it happened.\n\n"
    "So in the other application: no output profile, no “let the printer "
    "manage colours”, no proofing or simulation, no scaling or fitting "
    "to page, and no auto-tone or vivid mode.\n\n"
    "Your answer is written on the report, so a surprising result has "
    "somewhere obvious to start.\n\n"
    "Default: print here."
)

#: S6 — the on-panel notice while "Through the profile" is selected.
_CM_NOTICE_THROUGH = (
    "ChromIQ will work out the ink amounts your profile predicts for every "
    "patch and print exactly those, so the sheet is your profile’s own "
    "prediction made real. The printer’s own colour adjustment stays "
    "switched off, so nothing between here and the paper changes the "
    "colours.<br><br>"
    "You do not need to change any colour setting in the print dialog. The "
    "finished sheets are kept in the <b>cache</b> folder beside the chart, "
    "which is always safe to delete."
)

#: S7 — the on-panel notice when the run has no built profile (§3.1 A4).
_CM_NOTICE_NO_PROFILE = (
    "<b>There is no finished profile in this run yet</b>, so there is "
    "nothing for ChromIQ to print through. You can still print this sheet "
    "raw and measure it — but the result would describe your printer, not a "
    "profile, so it cannot tell you how accurate a profile is.<br><br>"
    "To get there: set <b>Run type</b> to <b>Profiling</b>, then create, "
    "print and measure the profiling chart as usual, and build the profile "
    "on the <b>Build Profile</b> tab. Come back here afterwards and this "
    "option will be waiting for you."
)

#: §3.1a — the notice for a chart that was converted when it was made.
_CM_NOTICE_ALREADY_CONVERTED = (
    "<b>This chart already has your profile applied, so it prints exactly "
    "as it is.</b><br><br>"
    "When you created it, ChromIQ asked your profile which ink amounts would "
    "produce each of the colours being tested, and stored the answer in the "
    "chart itself. The sheet is your profile’s prediction already — "
    "there is nothing left to convert.<br><br>"
    "That is why “Through the profile” is switched off "
    "here. Applying the profile a second time would print different colours "
    "from the ones being tested, your measurement would faithfully describe "
    "those different colours, and nothing afterwards could tell that it had "
    "happened.<br><br>"
    "You do not need to change anything. Print as usual — and if you print "
    "from another application, simply make sure it does not convert the "
    "colours either."
)

#: A3c — the chart claims stored colorimetric targets but the file is gone.
_CM_NOTICE_REFERENCE_MISSING = (
    "<b>This chart's records say its colours were already converted, but the "
    "stored reference file beside it is missing.</b> ChromIQ plays it safe "
    "and prints the chart exactly as it is — converting it again could not "
    "be undone and could not be detected afterwards. The measurement report "
    "may not be able to use the stored targets until the reference file is "
    "back."
)

#: §3.1b — raw chosen on a regular chart: a different question, not an error.
_CM_NOTICE_RAW_CHOSEN = (
    "<b>Printing raw measures your printer, not your profile.</b><br><br>"
    "The sheet goes to the printer exactly as it is, with no profile "
    "involved. That is useful for one particular question: <i>is my printer "
    "still behaving the way it did last time?</i> Print the same chart the "
    "same way each month and compare the results, and you will see it drift "
    "before it becomes visible in your work.<br><br>"
    "What it cannot tell you is how accurate your profile is, because no "
    "profile took part. For that, choose <b>Through the profile</b> above "
    "— then the sheet is your profile’s own prediction, and measuring it "
    "shows how close the prediction came.<br><br>"
    "Whichever you choose is written on the report, so you can always tell "
    "later which of the two questions a set of figures answered."
)


class TabPrint(QWidget):

    ti2_loaded         = pyqtSignal(Path)  # emitted when the user loads a .ti2 file
    ti2_replaced       = pyqtSignal()      # emitted when a different .ti2 file is loaded by the user
    ti2_load_cancelled = pyqtSignal()      # emitted when the cross-tab dialog is cancelled
    chart_relocated    = pyqtSignal(Path)  # emitted when files were copied to a new folder
    chart_load_requested = pyqtSignal(Path, list)  # user loaded a .ti2 here → reflect it in Create Chart
    """Step 2: print the test chart via CUPS."""

    def __init__(
        self,
        settings: "AppSettings",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._module   = PrintModule()
        self._printer  = CupsRawPrinter()
        self._tiff_pages: list[Path] = []
        self._current_ti2: Path | None = None
        self._target_ctl = None          # shared Profile-run / Run-type controller (#130)
        # (ti2, kwargs) for a print record that is written only if a page is
        # actually submitted — see `_apply_verification_colour` (R6 F5).
        self._pending_print_record: "tuple[Path, dict] | None" = None
        # Sequential-enabling state — populated in _rebuild_option_rows
        self._ordered_opts: list[tuple[str, list[str], QComboBox]] = []
        self._raw_value_pairs: dict[str, list[tuple[str, str]]] = {}
        self._restoring: bool = False
        self._mode: str = "dark"

        self._build_ui()

    # ------------------------------------------------------------------
    def set_appearance(self, mode: str) -> None:
        """Restyle the AirPrint info box when the theme changes."""
        from ui.theme import accept_mode
        new_mode = accept_mode(mode)
        if new_mode == self._mode:
            return
        self._mode = new_mode
        # If the AirPrint box is currently shown, restyle it in place.
        box = self.findChild(QFrame, "airprintInfoBox")
        if box is not None:
            self._apply_airprint_box_styles(box)

    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)

        # ---- Left controls ----
        left = QWidget(self)
        self._left_panel = left
        left.setFixedWidth(580)
        left.setStyleSheet("QPushButton { min-height: 44px; }")
        ll = QVBoxLayout(left)
        ll.setContentsMargins(16, 12, 16, 12)
        ll.setSpacing(10)

        _initial_tt_title, _initial_tt_body = self._compute_print_tooltip()
        # Amber grid button at the far right of the title row — loads an existing
        # target's .ti2 so it can be reprinted. Mirrors the Create Chart tab's
        # folder/grid/star trio, in this tab's amber accent (#70, Knut). Replaces
        # the old bottom-row "Load existing target" button.
        # MOVED TO THE MASTHEAD (#130, spec agreed 2026-07-31). These acted on
        # the whole app rather than on one tab, and Load .ti2 existed twice —
        # once here and once on the other tab. Both now live top-left in the
        # masthead; see MastheadHeader.load_project_clicked / load_ti2_clicked.
        # "Load image" (#117, Knut): print ANY TIFF through ChromIQ's raw,
        # colour-management-free pipeline — charts made by other tools, test
        # images. Print-only: measuring still needs the chart's .ti2.
        from ui.widgets import ImageFileButton
        self._load_image_btn = ImageFileButton(SPEC_AMBER, left)
        self._load_image_btn.setToolTip(
            tr("Load image (TIFF).\n"
               "Open any TIFF — for example a chart made by another tool — "
               "and print it exactly like a chart: without colour "
               "management.\n"
               "Printing only: to MEASURE a chart afterwards, load its .ti2 "
               "with the grid button instead, so ChromIQ knows its patches."))
        self._load_image_btn.clicked.connect(self._on_load_image)
        _trailing = QWidget(left)
        _tl = QHBoxLayout(_trailing)
        _tl.setContentsMargins(0, 0, 0, 0)
        _tl.setSpacing(6)
        # Order: load image, then reveal folder. "Load test chart" used to lead
        # this row; it moved to the masthead (#130) so one button serves the
        # whole app instead of one per tab.
        _tl.addWidget(self._load_image_btn)
        from ui.widgets import RevealFolderButton
        self._reveal_btn = RevealFolderButton(SPEC_AMBER, _trailing)
        self._reveal_btn.setToolTip(tr(
            "Open this chart's folder in {manager} — where "
            "the printable pages live. Handy if you'd rather print the pages "
            "from another application.").format(manager=file_manager_name()))
        self._reveal_btn.clicked.connect(self._reveal_folder)
        _tl.addWidget(self._reveal_btn)
        self._header = TabHeader(
            tr("STEP 02 · PRINT CHART"), tr("Print test chart"), "#ffb42d", left,
            tooltip_title=_initial_tt_title,
            tooltip_body=_initial_tt_body,
            trailing_widget=_trailing,
        )
        ll.addWidget(self._header)

        # Printer selection (pinned above scroll area)
        self._printer_grp = QGroupBox(tr("Printer"), left)
        printer_grp = self._printer_grp
        pg = QVBoxLayout(printer_grp)

        pr_row = QHBoxLayout()
        pr_row.addWidget(QLabel(tr("Printer:"), left))
        self._printer_combo = NoScrollComboBox(left)
        pr_row.addWidget(self._printer_combo, stretch=1)

        refresh_btn = QPushButton(left)
        refresh_btn.setIcon(load_refresh_icon("refresh_print"))
        refresh_btn.setFixedSize(34, 34)
        refresh_btn.setStyleSheet("QPushButton { padding: 0; min-height: 0; }")
        refresh_btn.setToolTip(tr("Refresh printer list"))
        refresh_btn.clicked.connect(self._refresh_printers)
        pr_row.addWidget(refresh_btn)

        pr_row.addWidget(TooltipButton(
            tr("Printer Selection"),
            tr("Select the printer to send the chart to.  Only printers installed in\n"
            "the system CUPS print queue are listed.\n\n"
            "ChromIQ converts the chart to PostScript and sends it via lp —\n"
            "bypassing ColorSync entirely.  If CUPS rejects PostScript (e.g.\n"
            "AirPrint or Driverless drivers), it automatically retries by sending\n"
            "the TIFF directly with colour-space-aware raster options.\n"
            "Colour management is always disabled automatically."),
            left,
        ))
        pg.addLayout(pr_row)
        ll.addWidget(printer_grp)

        # Scrollable content area (options + warning)
        scroll = FadeScrollArea(left)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_content = QWidget()
        scl = QVBoxLayout(scroll_content)
        scl.setContentsMargins(0, 0, 0, 0)
        scl.setSpacing(10)

        # "How this chart is printed" — feature A (#130): the reconciled
        # three-row section of verification_printing_and_target.md §4. Colour
        # and Rendering intent appear only for a verification; Route is shown
        # for every chart. Stays visible in native-dialog mode too — the
        # conversion happens before either print path. INSIDE the scroll area
        # (Basti, 2026-08-09): pinned above it, this section squeezed Print
        # Options down to a sliver — when space runs out, the info boxes and
        # every option scroll together instead of one section alone.
        self._build_cm_section(scroll_content, scl)

        # Print options — dynamically built from CUPS lpoptions output
        self._opts_grp = QGroupBox(tr("Print Options"), scroll_content)
        self._opts_layout = QVBoxLayout(self._opts_grp)
        self._option_combos: dict[str, QComboBox] = {}
        self._opts_layout.addWidget(
            QLabel(tr("Select a printer to see its options."), scroll_content)
        )
        scl.addWidget(self._opts_grp)

        self._printer_combo.currentIndexChanged.connect(self._on_printer_changed)

        # Warning label — inside the scroll area too (same request): it is an
        # info box, and it is tall.
        self._warn_lbl = QLabel("", scroll_content)
        self._warn_lbl.setObjectName("warning")
        self._warn_lbl.setWordWrap(True)
        scl.addWidget(self._warn_lbl)

        scl.addStretch()
        scroll.setWidget(scroll_content)
        ll.addWidget(scroll, stretch=1)

        # Spacer below warn label; shown only in native mode to vertically centre the label
        self._native_warn_spacer = QWidget(left)
        self._native_warn_spacer.setVisible(False)
        ll.addWidget(self._native_warn_spacer, stretch=1)

        # Feed the beast block
        beast_box = QGroupBox(left)
        # Only override layout (no title → zero top-margin + tight padding);
        # let border + radius come from the global QGroupBox theme.
        beast_box.setStyleSheet(
            "QGroupBox { margin-top: 0px; padding: 14px 8px 12px 8px; }"
        )
        beast_layout = QVBoxLayout(beast_box)
        beast_layout.setContentsMargins(0, 0, 0, 0)
        beast_layout.setSpacing(4)
        beast_headline = QLabel(beast_box)
        # The mark the headline ends in is an inline colour, which beats the
        # stylesheet -- so it kept its hue in a theme that has none. Resolved
        # through the appearance, and re-resolved on a live switch.
        set_accent_html(
            beast_headline,
            tr("Feed the beast<span style=\"color: {SPEC_AMBER}; font-style: italic;\">!</span>"),
            SPEC_AMBER=SPEC_AMBER)
        beast_headline.setTextFormat(Qt.TextFormat.RichText)
        beast_headline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        beast_headline.setStyleSheet(
            "background: transparent;"
            " font-family: Georgia; font-size: 28px;"
        )
        beast_layout.addWidget(beast_headline)
        beast_subtext = QLabel(tr("Your printer is hungry."), beast_box)
        beast_subtext.setAlignment(Qt.AlignmentFlag.AlignCenter)
        beast_subtext.setStyleSheet(
            "color: #808080; background: transparent;"
            " font-family: Menlo; font-size: 9px; font-weight: 300;"
        )
        beast_layout.addWidget(beast_subtext)
        beast_bar = QHBoxLayout()
        beast_bar.setContentsMargins(0, 6, 0, 0)
        beast_bar.setSpacing(0)
        beast_bar.addStretch()
        # Decoration, not a readout: the same five cells on every tab. One
        # ACTION value under Neutral, and the hue kept on each cell so a live
        # appearance switch repaints it -- see ui.widgets.spectrum_cell.
        for _color in TAB_COLORS:
            beast_bar.addWidget(spectrum_cell(beast_box, _color))
        beast_bar.addStretch()
        beast_layout.addLayout(beast_bar)
        ll.addWidget(beast_box)

        # Print buttons
        btn_row = QHBoxLayout()
        self._print_page_btn = QPushButton(tr("Print\nCurrent Page"), left)
        self._print_page_btn.setObjectName("primary")
        self._print_page_btn.clicked.connect(self._on_print_current)

        self._print_all_btn = QPushButton(tr("Print All\nPages"), left)
        self._print_all_btn.clicked.connect(self._on_print_all)

        self._save_defaults_btn = QPushButton(tr("Save as\nDefaults"), left)
        self._save_defaults_btn.clicked.connect(self._on_save_defaults)

        self._clear_queue_btn = QPushButton(tr("Clear\nPrint Queue"), left)
        self._clear_queue_btn.setToolTip(
            tr("Cancel all pending and stuck jobs for the selected printer.")
        )
        self._clear_queue_btn.clicked.connect(self._on_clear_queue)

        btn_row.addWidget(self._print_page_btn)
        btn_row.addWidget(self._print_all_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._clear_queue_btn)
        btn_row.addWidget(self._save_defaults_btn)
        ll.addLayout(btn_row)

        # Status — hidden when empty so it doesn't add gap below buttons
        self._status_lbl = QLabel("", left)
        self._status_lbl.setWordWrap(True)
        self._status_lbl.setVisible(False)
        ll.addWidget(self._status_lbl)

        # Status bar (replaces main-window status bar)
        self._status_bar_lbl = QLabel("", left)
        self._status_bar_lbl.setWordWrap(True)
        self._status_bar_lbl.setVisible(False)
        ll.addWidget(self._status_bar_lbl)

        splitter.addWidget(left)

        # ---- Right preview ----
        right = QWidget(self)
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 12)
        rl.setSpacing(0)
        self._preview = TiffPreview(right)
        self._preview.set_caption(tr("PRINT PREVIEW"))
        rl.addWidget(self._preview, stretch=1)
        splitter.addWidget(right)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter)

        # Initial state
        self._set_print_buttons_enabled(False)
        # ASKING CUPS IS DEFERRED TO THE FIRST TIME THIS TAB IS SHOWN.
        #
        # `_refresh_printers` shells out twice — `detect_printers`, then
        # `_on_printer_changed` → `query_options` — and both were run while the
        # main window was still being built, for a tab most sessions never
        # open. Measured 2026-08-07: 73 ms of the startup, spent waiting on an
        # external process.
        #
        # Nothing outside this tab reads the printer list (the only consumers
        # are `_on_printer_changed` and the print call itself), and the user
        # cannot press a button on a tab they have not looked at — so there is
        # no window in which the list can be needed but empty.
        self._printers_loaded = False
        self._restore_defaults()
        self.apply_native_dialog_mode()

    def showEvent(self, event) -> None:         # noqa: N802 — Qt's name
        """Load the printer list the first time the tab is actually looked at,
        and re-read the Colour row on every entry — its forced/free state
        depends on files on disk (the chart's colorimetric-reference marker,
        the run's profile) which can change while this tab is hidden."""
        super().showEvent(event)
        if not getattr(self, "_printers_loaded", False):
            self._printers_loaded = True
            try:
                self._refresh_printers()
            except Exception:      # noqa: BLE001 — never block showing the tab
                log.warning("Could not load the printer list", exc_info=True)
        try:
            self._update_colour_row_visible()
        except Exception:      # noqa: BLE001 — never break tab switching
            log.warning("colour row refresh on show failed", exc_info=True)

    def reload_printers(self) -> None:
        """Ask CUPS again — for callers that need the list refreshed on demand."""
        self._printers_loaded = True
        self._refresh_printers()

    # ------------------------------------------------------------------

    def load_tiffs(self, paths: list[Path]) -> None:
        """Called by main window after chart generation."""
        self._tiff_pages = paths
        if paths:
            self._preview.set_notice(None)     # a real chart — drop guidance
        self._preview.load_tiff(paths)
        self._set_print_buttons_enabled(bool(paths))
        self._update_colour_row_visible()

    def has_pages(self) -> bool:
        """Whether this tab currently holds printable page images.

        Asked by the masthead's Load .ti2 button, which took over from the two
        per-tab buttons: Print is the tab that notices a .ti2 arriving without
        its pages, and that message had to survive the move (#130).
        """
        return bool(self._tiff_pages)

    def set_chart_notice(self, text: "str | None") -> None:
        """Show guidance in the preview when there's no chart to print for the
        selected Profile-run / Run-type (#130, Knut)."""
        self._preview.set_notice(text)

    def set_target_controller(self, controller) -> None:
        """Receive the shared Profile-run / Run-type controller (#130) so loading
        a chart here honours the bar exactly like the Measure tab."""
        self._target_ctl = controller
        if controller is not None:
            # A run-type or run change moves the Colour/Intent rows in or out
            # (§3.1 table) — recompute rather than wait for the next tab visit.
            controller.changed.connect(self._update_colour_row_visible)

    # ------------------------------------------------------------------
    # Feature A (#130) — printing a verification chart through its profile.
    # Specification: docs/design/verification_printing_and_target.md §3–§5.
    # ------------------------------------------------------------------

    def _build_cm_section(self, left: QWidget, ll: QVBoxLayout) -> None:
        """The three-row §4 section: Colour · Rendering intent · Route, plus
        the state notice below them. Built hidden; `_update_colour_row_visible`
        decides what shows for the selected target."""
        from ui.tooltip_button import TooltipButton

        self._cm_grp = QGroupBox(tr("How this chart is printed"), left)
        gl = QVBoxLayout(self._cm_grp)
        gl.setSpacing(8)

        def row(label: str, control: QWidget, tip_title: str,
                tip_body: str) -> QWidget:
            r = QWidget(self._cm_grp)
            lay = QHBoxLayout(r)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(10)
            text = QLabel(label, r)
            text.setMinimumWidth(130)
            lay.addWidget(text)
            lay.addWidget(control, 1)
            lay.addWidget(TooltipButton(tip_title, tip_body, r))
            return r

        # -- Colour: through the profile, or raw (verification only) --------
        # Side by side (Basti, 2026-08-09), with labels short enough that the
        # pair fits the 580 px panel in every language — the first version's
        # longer labels clipped mid-letter.
        choice = QWidget(self._cm_grp)
        cl = QHBoxLayout(choice)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(14)
        self._cm_through_rb = QRadioButton(tr("Through the profile"), choice)
        self._cm_raw_rb = QRadioButton(tr("Raw — no profile"), choice)
        self._cm_through_rb.setChecked(True)
        cl.addWidget(self._cm_through_rb)
        cl.addWidget(self._cm_raw_rb)
        cl.addStretch(1)
        self._cm_colour_row = row(tr("Colour"), choice,
                                  tr(_CM_COLOUR_HELP_TITLE),
                                  tr(_CM_COLOUR_HELP_BODY))
        gl.addWidget(self._cm_colour_row)

        # -- Rendering intent (verification only, and only when converting) -
        self._cm_intent_combo = NoScrollComboBox(self._cm_grp)
        self._cm_intent_combo.setMinimumHeight(30)
        for label, name in (
                (tr("Relative colorimetric (recommended)"), "relative"),
                (tr("Absolute colorimetric"), "absolute"),
                (tr("Perceptual"), "perceptual"),
                (tr("Saturation"), "saturation")):
            self._cm_intent_combo.addItem(label, name)
        self._cm_intent_row = row(tr("Rendering intent"),
                                  self._cm_intent_combo,
                                  tr(_CM_INTENT_HELP_TITLE),
                                  tr(_CM_INTENT_HELP_BODY))
        gl.addWidget(self._cm_intent_row)

        # -- Route: printed here, or handed to another application ----------
        route = QWidget(self._cm_grp)
        rl = QHBoxLayout(route)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(14)
        self._cm_route_here_rb = QRadioButton(tr("Print here"), route)
        self._cm_route_ext_rb = QRadioButton(
            tr("In another application"), route)
        self._cm_route_here_rb.setChecked(True)
        rl.addWidget(self._cm_route_here_rb)
        rl.addWidget(self._cm_route_ext_rb)
        rl.addStretch(1)
        self._cm_route_row = row(tr("Route"), route,
                                 tr(_CM_ROUTE_HELP_TITLE),
                                 tr(_CM_ROUTE_HELP_BODY))
        gl.addWidget(self._cm_route_row)

        ll.addWidget(self._cm_grp)

        # -- the state notice (S6 / S7 / §3.1a / §3.1b) ---------------------
        # Below the group rather than inside it (as the mockups show): a
        # word-wrapped label nested in the group box clipped its own last
        # lines in the scroll area, while a sibling of the group renders in
        # full — the same placement the tab's other warning box uses.
        self._cm_notice = QLabel("", left)
        self._cm_notice.setObjectName("warning")
        self._cm_notice.setWordWrap(True)
        self._cm_notice.setTextFormat(Qt.TextFormat.RichText)
        ll.addWidget(self._cm_notice)
        self._cm_grp.setVisible(False)
        self._updating_cm = False
        #: The user's own Colour choice for the selected target — kept apart
        #: from the radios because a forced state (§3.1a, A4) must not
        #: overwrite what the user chose when the force lifts.
        self._cm_user_colour: "str | None" = None
        self._print_written: dict = {}       # per-store snapshot (§3a Q-4)

        self._cm_through_rb.toggled.connect(self._on_cm_selection_changed)
        self._cm_raw_rb.toggled.connect(self._on_cm_selection_changed)

    def _on_cm_selection_changed(self, *_a) -> None:
        """Follow a user click on the Colour radios: remember the choice and
        refresh the notice + intent row (§3.1b — the notice names the question
        the selected way of printing will answer)."""
        if getattr(self, "_updating_cm", False):
            return
        from workflow import verification_print as vp
        if self._cm_through_rb.isEnabled():
            self._cm_user_colour = (vp.COLOUR_THROUGH
                                    if self._cm_through_rb.isChecked()
                                    else vp.COLOUR_RAW)
        self._update_colour_row_visible()

    def _cm_run(self):
        """The Run the bar points at, or None (no project / no controller)."""
        ctl = getattr(self, "_target_ctl", None)
        if ctl is None:
            return None
        try:
            project = ctl.project_or_none()
            if project is None:
                return None
            from core.measurement_target import resolve_run
            return resolve_run(project, ctl.target)
        except Exception:      # noqa: BLE001 — a question must never raise
            return None

    def _update_colour_row_visible(self) -> None:
        """§3.1 + §3.1a + §3.1b: which rows show, what is forced, and what the
        notice says — recomputed from the target, the run's profile and the
        loaded chart every time any of them changes."""
        from workflow import verification_print as vp
        ctl = getattr(self, "_target_ctl", None)
        has_pages = bool(self._tiff_pages)
        is_verif = ctl is not None and ctl.target.is_verification()
        # A6: with no chart the tab shows its existing empty state — no rows.
        self._cm_grp.setVisible(has_pages)
        self._cm_colour_row.setVisible(is_verif)
        self._cm_intent_row.setVisible(is_verif)
        # The notice is a sibling of the group (not a child), so it needs the
        # no-pages condition itself.
        self._cm_notice.setVisible(has_pages and is_verif)
        if not (has_pages and is_verif):
            return

        state = vp.chart_conversion_state(self._current_ti2)
        run = self._cm_run()
        profile_exists = (run is not None
                          and run.built_profile_icc().exists())
        self._updating_cm = True
        try:
            if state != vp.STATE_REGULAR:
                # §3.1a — the chart was converted when it was made: force Raw,
                # DISABLE the other option (an error with no legitimate use).
                self._cm_raw_rb.setText(tr("Raw — already converted"))
                self._cm_raw_rb.setChecked(True)
                self._cm_through_rb.setEnabled(False)
                self._cm_intent_combo.setEnabled(False)
                notice = tr(_CM_NOTICE_ALREADY_CONVERTED)
                if state == vp.STATE_CONVERTED_REF_MISSING:
                    # A3c — say what could not be established, and stay safe.
                    notice = tr(_CM_NOTICE_REFERENCE_MISSING) + "<br><br>" + notice
                self._cm_notice.setText(notice)
            elif not profile_exists:
                # A4 — nothing to print through; raw stays available.
                self._cm_raw_rb.setText(tr("Raw — no profile"))
                self._cm_raw_rb.setChecked(True)
                self._cm_through_rb.setEnabled(False)
                self._cm_intent_combo.setEnabled(False)
                self._cm_notice.setText(tr(_CM_NOTICE_NO_PROFILE))
            else:
                # A3 / A5 — both options live; the user's choice rules.
                self._cm_raw_rb.setText(tr("Raw — no profile"))
                self._cm_through_rb.setEnabled(True)
                self._cm_raw_rb.setEnabled(True)
                wanted = self._cm_user_colour
                if wanted is None:
                    wanted = vp.default_colour_for_run(run)
                (self._cm_through_rb if wanted == vp.COLOUR_THROUGH
                 else self._cm_raw_rb).setChecked(True)
                through = self._cm_through_rb.isChecked()
                self._cm_intent_combo.setEnabled(through)
                self._cm_notice.setText(
                    tr(_CM_NOTICE_THROUGH) if through
                    else tr(_CM_NOTICE_RAW_CHOSEN))
        finally:
            self._updating_cm = False

    def _cm_selected_colour(self) -> str:
        """The colour route a print started now would actually take.

        Computed from the target and the widget STATE, never from
        ``isVisible()`` — a widget that has not been shown on screen yet
        answers ``isVisible() == False`` even when its row applies, which
        would silently downgrade "through" to raw."""
        from workflow import verification_print as vp
        ctl = getattr(self, "_target_ctl", None)
        if (ctl is None or not ctl.target.is_verification()
                or not self._tiff_pages):
            return vp.COLOUR_RAW
        if self._cm_through_rb.isChecked() and self._cm_through_rb.isEnabled():
            return vp.COLOUR_THROUGH
        return vp.COLOUR_RAW

    def _cm_selected_intent(self) -> str:
        return self._cm_intent_combo.currentData() or "relative"

    def _cm_selected_route(self) -> str:
        from workflow import verification_print as vp
        if self._tiff_pages and self._cm_route_ext_rb.isChecked():
            return vp.ROUTE_EXTERNAL
        return vp.ROUTE_CHROMIQ

    def _apply_verification_colour(self, pages):
        """The one funnel below both print buttons (§5 A2.2).

        Converts the pages through the run's profile when the Colour row says
        so, records how the sheet is produced (A15–A18), and handles the
        external route. Returns the pages the print path should send, or None
        when nothing is to be printed here — a failed conversion prints
        nothing (§3.2 A11), and the external route hands the files over
        instead of printing.
        """
        from workflow import verification_print as vp
        colour = self._cm_selected_colour()
        route = self._cm_selected_route()
        converted_dir = None

        if colour == vp.COLOUR_THROUGH:
            run = self._cm_run()
            profile = run.built_profile_icc() if run is not None else None
            chart_dir = (Path(self._current_ti2).parent
                         if self._current_ti2 is not None
                         else Path(pages[0][0]).parent)
            out_dir = chart_dir / "cache"
            bin_dir = self._settings.get("argyll_bin_path",
                                         "/Applications/Argyll/bin")
            unique = list(dict.fromkeys(p for p, _f in pages))
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            try:
                def _progress(n: int, total: int) -> None:
                    self._set_status(tr(
                        "Working out the ink amounts your profile predicts — "
                        "page {n} of {total}…").format(n=n, total=total))
                    QApplication.processEvents()

                mapping = vp.convert_pages_through_profile(
                    unique, profile if profile is not None else Path(""),
                    self._cm_selected_intent(), out_dir,
                    bin_dir=bin_dir, on_page=_progress)
            except vp.VerificationPrintError as err:
                self._set_status("")
                self._show_cm_error(err)
                return None
            finally:
                QApplication.restoreOverrideCursor()
            pages = [(mapping.get(p, p), f) for p, f in pages]
            converted_dir = out_dir
            self._set_status(tr(
                "The sheets have been prepared through this run's profile."))

        # A RECORD OF A PRINT IS WRITTEN WHEN THERE HAS BEEN ONE (R6 F5).
        #
        # This wrote `<stem>.print.json` here, above BOTH print paths and above
        # every one of their guards — no printer, printer offline, stuck jobs,
        # the borderless warning, the preflight, a TIFF that will not open, a
        # queue that rejects the job. Driven: with the printer asleep ChromIQ
        # correctly said so, sent zero pages, and left behind
        # `{"printed_at": …, "colour": "raw", "route": "chromiq"}`. Same on
        # Cancel at the preflight. That file then told the Measure tab that
        # ChromIQ had printed the sheet, so the "How was this sheet printed?"
        # question was never asked about a sheet ChromIQ had NOT printed, and
        # the report asserted `colour: raw` about a sheet that went through the
        # profile — with pairing 3's media-relative yardstick left off.
        #
        # So the two routes are timed by what each of them actually does:
        #
        #   route = external — the hand-off IS the act. By this line the pages
        #     are converted and the folder is about to open; nothing further
        #     can refuse. Written here, unchanged.
        #   route = chromiq  — the act is a print, and ChromIQ has not made one
        #     yet. The record is held and committed by whichever print path
        #     runs, once a page has been accepted by the printing system.
        #
        # "Accepted" is the strongest fact available: paper coming out of a
        # printer is not observable from here, and the record's question is
        # "did ChromIQ put this sheet through the profile", not "did it reach
        # the paper". A job the queue took carries the converted pages and the
        # answer is yes; a job that was never submitted, or that CUPS refused,
        # is not a print and leaves no record.
        self._pending_print_record = None
        if self._current_ti2 is not None:
            run = self._cm_run()
            pending = dict(
                colour=colour,
                intent=self._cm_selected_intent(),
                profile=(run.built_profile_icc() if run is not None else None),
                route=route,
                source_profile=(vp.source_profile_path(
                    self._settings.get("argyll_bin_path",
                                       "/Applications/Argyll/bin"))
                    if colour == vp.COLOUR_THROUGH else ""))
            if route == vp.ROUTE_EXTERNAL:
                vp.write_print_record(Path(self._current_ti2), **pending)
            else:
                self._pending_print_record = (Path(self._current_ti2), pending)

        if route == vp.ROUTE_EXTERNAL:
            folder = converted_dir if converted_dir is not None else (
                Path(self._current_ti2).parent if self._current_ti2 is not None
                else Path(pages[0][0]).parent)
            from core.preset_store import reveal_in_file_manager
            reveal_in_file_manager(folder)
            if converted_dir is not None:
                self._set_status(tr(
                    "The finished sheets are in the folder that just opened — "
                    "the colour work is already done. In your application: "
                    "print them with no colour conversion of any kind, and at "
                    "100% size."))
            else:
                self._set_status(tr(
                    "The chart pages are in the folder that just opened. In "
                    "your application: print them with no colour conversion "
                    "of any kind, and at 100% size."))
            return None
        return pages

    def _show_cm_error(self, err) -> None:
        """Render the §M message a failed conversion names (S9 / S10)."""
        from workflow import measurement_messages as M
        if err.message_id == "M-CM-NO-CCTIFF":
            title, body = M.M_CM_NO_CCTIFF.render()
        else:
            title, body = M.M_CM_CONVERT_FAILED.render(
                n=err.page or 1, total=err.total or 1,
                reason=err.reason or err.message_id)
        QMessageBox.critical(self, title, body)

    # ---- per-target settings (#130 feature A, §11 Q5) --------------------
    def save_target_settings(self, store=None, key=None) -> bool:
        """Record the Colour / Rendering intent / Route choices against the
        selected target — the same duck-typed contract Create Chart, Measure
        and Build Profile follow, called by MainWindow on the L1/W6 events."""
        if getattr(self, "_updating_cm", False) \
                or getattr(self, "_loading_print_settings", False):
            return False
        if store is None:
            from workflow.per_target_settings import store_for_target
            store = store_for_target(getattr(self, "_target_ctl", None))
        if store is None:
            return False
        try:
            if not Path(getattr(store, "dir", "")).is_dir():
                return False           # never resurrect a deleted project
        except (TypeError, ValueError):
            return False
        try:
            from workflow import verification_print as vp
            wanted = {
                "colour": self._cm_user_colour or "",
                "intent": self._cm_selected_intent(),
                "route": (vp.ROUTE_EXTERNAL
                          if self._cm_route_ext_rb.isChecked()
                          else vp.ROUTE_CHROMIQ),
            }
            fingerprint = str(getattr(store, "dir", store))
            if self._print_written.get(fingerprint) == wanted:
                return False
            meta = store.load_meta()
            if not hasattr(meta, "print_settings"):
                return False           # a Calibration store — no Colour row
            stored = dict(getattr(meta, "print_settings") or {})
            merged = dict(stored)
            # A forced state (§3.1a / A4) leaves the user's stored Colour
            # alone: only a choice the user could actually make is recorded.
            if wanted["colour"]:
                merged["colour"] = wanted["colour"]
            merged["intent"] = wanted["intent"]
            merged["route"] = wanted["route"]
            if merged == stored:
                self._print_written[fingerprint] = wanted
                return False
            meta.print_settings = merged
            store.save_meta(meta)
            self._print_written[fingerprint] = wanted
            log.debug("print settings written for %s", getattr(store, "id", store))
            return True
        except Exception:      # noqa: BLE001 — never lose the tab over a write
            log.warning("Could not save the target's Print settings",
                        exc_info=True)
            return False

    def load_target_settings(self) -> bool:
        """Put the selected target's Print choices on screen (§2 L1), falling
        back to the defaults — and to the Q3 history-aware Colour default —
        when the target has nothing stored (§4 S4/S5)."""
        from workflow.per_target_settings import store_for_target
        from workflow import verification_print as vp
        store = store_for_target(getattr(self, "_target_ctl", None))
        stored: dict = {}
        if store is not None:
            try:
                stored = dict(getattr(store.load_meta(), "print_settings",
                                      None) or {})
            except Exception:      # noqa: BLE001
                log.warning("Could not read the target's Print settings",
                            exc_info=True)
                stored = {}
        self._loading_print_settings = True
        self._updating_cm = True
        try:
            colour = stored.get("colour") or ""
            self._cm_user_colour = colour if colour in (
                vp.COLOUR_THROUGH, vp.COLOUR_RAW) else None
            idx = self._cm_intent_combo.findData(
                stored.get("intent") or vp.DEFAULT_INTENT)
            self._cm_intent_combo.setCurrentIndex(idx if idx >= 0 else 0)
            (self._cm_route_ext_rb
             if stored.get("route") == vp.ROUTE_EXTERNAL
             else self._cm_route_here_rb).setChecked(True)
        finally:
            self._updating_cm = False
            self._loading_print_settings = False
        self._update_colour_row_visible()
        return bool(stored)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _refresh_printers(self) -> None:
        self._printer_combo.blockSignals(True)
        self._printer_combo.clear()
        printers = self._module.detect_printers()
        for p in printers:
            self._printer_combo.addItem(p, p)
        if not printers:
            self._printer_combo.addItem(tr("No printers found"), "")
        self._printer_combo.blockSignals(False)

        last = self._settings.get("last_printer", "")
        if last:
            idx = self._printer_combo.findData(last)
            if idx >= 0:
                self._printer_combo.setCurrentIndex(idx)
        self._on_printer_changed()

    def _on_printer_changed(self) -> None:
        printer = self._printer_combo.currentData() or ""
        self._rebuild_option_rows(printer)

    @classmethod
    def _clear_layout(cls, layout) -> None:
        """Recursively delete every widget and sub-layout inside *layout*.

        Rows in the Print Options group are nested QHBoxLayouts whose inner
        QLabel/QComboBox are parented to the tab widget, not the layout — so
        deleting only the top-level layout items leaks them across rebuilds.
        Signals are disconnected before deleteLater so a queued slot can't
        fire into a wrapper that's about to disappear.
        """
        while layout.count():
            item = layout.takeAt(0)
            if item is None:
                break
            w = item.widget()
            if w is not None:
                if isinstance(w, QComboBox):
                    try:
                        w.currentIndexChanged.disconnect()
                    except (TypeError, RuntimeError):
                        pass
                w.deleteLater()
                continue
            sub = item.layout()
            if sub is not None:
                cls._clear_layout(sub)
                sub.deleteLater()

    def _apply_airprint_box_styles(self, box: "QFrame") -> None:
        """Paint the 'No configurable options detected' info box.

        Dark mode keeps the original dark-olive / amber treatment; light mode
        reuses the same chrome as QLabel#warning so the box and the
        'Verify that all print settings…' warning above match.

        NOTHING HAD EVER DRAWN THIS BOX IN NEUTRAL. It needs two conditions at
        once: ChromIQ's own ``lp`` pipeline (Preferences turns the OS print
        dialog off) AND a printer whose driver exposes no options at all. The
        fold above had room for two answers, so the third appearance took the
        dark branch and painted a dark-olive slab with amber text across the
        middle of the Print tab - 523,776 hued pixels in a theme that is meant
        to have none. It is a warning, so ``kind="warn"`` keeps it one: in
        Neutral the amber goes and the 2 px underline says it instead.
        """
        if self._mode == "light":
            from ui.light_styles import LM_WARN_BG, LM_WARN_TEXT
            # Border + title pick up the Print Chart tab's spectrum colour so
            # the box matches the rest of the tab's accents (amber).
            bg          = LM_WARN_BG
            border      = SPEC_AMBER
            body_color  = LM_WARN_TEXT
            title_color = SPEC_AMBER
        else:
            bg, border    = "#2a2000", "#f9a825"
            body_color    = "#e0d5b0"
            title_color   = "#fdd835"
        box.setStyleSheet(info_box_qss(
            "airprint", bg=bg, border=border, title=title_color,
            body=body_color, mode=self._mode, kind="warn"))

    def _rebuild_option_rows(self, printer: str) -> None:
        self._clear_layout(self._opts_layout)
        self._option_combos.clear()
        self._ordered_opts.clear()
        self._raw_value_pairs.clear()

        if not printer:
            self._opts_layout.addWidget(QLabel(tr("Select a printer to see its options."), self))
            return

        opts = self._module.query_options(printer)
        if not opts:
            box = QFrame(self)
            box.setFrameShape(QFrame.Shape.NoFrame)
            box.setObjectName("airprintInfoBox")
            box_layout = QVBoxLayout(box)
            box_layout.setContentsMargins(10, 8, 10, 8)
            box_layout.setSpacing(6)

            title = QLabel(tr("No configurable options detected"), box)
            title.setObjectName("airprintInfoTitle")
            box_layout.addWidget(title)

            body = QLabel(
                tr("macOS often installs an <b>AirPrint</b> or <b>Driverless</b> driver "
                "automatically when you add a printer. These work fine for everyday "
                "printing, but don't expose the detailed settings needed for ICC profiling."
                "<br><br>"
                "<b>How to check:</b><br>"
                "Open <i>System Settings → Printers &amp; Scanners</i>, select your "
                "printer, and look at the <i>Kind</i> field. If it says "
                "\"AirPrint\" or \"Driverless\", that's the cause."
                "<br><br>"
                "<b>How to fix:</b><br>"
                "1. Click the <b>−</b> button to remove the printer.<br>"
                "2. Download the native driver from your printer manufacturer's website.<br>"
                "3. Re-add the printer — macOS should now use the native PPD driver "
                "with all options available."),
                box,
            )
            body.setWordWrap(True)
            body.setTextFormat(Qt.TextFormat.RichText)
            body.setObjectName("airprintInfoBody")
            box_layout.addWidget(body)

            self._apply_airprint_box_styles(box)
            self._opts_layout.addWidget(box)
            return

        saved_printer_opts: dict[str, str] = {}
        raw_saved = self._settings.get(f"print_opts_{printer}", "")
        if raw_saved:
            for pair in str(raw_saved).split("|"):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    saved_printer_opts[k] = v

        for i, (opt_name, (label, value_pairs)) in enumerate(opts.items()):
            self._raw_value_pairs[opt_name] = value_pairs
            row = QHBoxLayout()
            lbl = QLabel(tr("{label}:").format(label=label), self)
            lbl.setMinimumWidth(160)
            row.addWidget(lbl)
            combo = NoScrollComboBox(self)
            combo.setMaxVisibleItems(12)
            combo.addItem(tr("Printer Default"), "")
            for display, raw_val in value_pairs:
                combo.addItem(display, raw_val)
            # All combos start enabled — "Printer Default" on a leading combo means
            # "let the driver decide", so downstream combos must be reachable without
            # forcing the user to pick a tray/size they don't care about.
            combo.setEnabled(True)
            row.addWidget(combo, stretch=1)
            self._opts_layout.addLayout(row)
            self._option_combos[opt_name] = combo
            self._ordered_opts.append((opt_name, [rv for _, rv in value_pairs], combo))
            combo.currentIndexChanged.connect(
                lambda _, idx=i: self._on_option_changed(idx)
            )

        # Restore saved values in insertion order so each restore re-filters the
        # next combo's value list before that combo is itself restored.
        self._restoring = True
        for opt_name, _, combo in self._ordered_opts:
            saved_val = saved_printer_opts.get(opt_name, "")
            if saved_val:
                found = combo.findData(saved_val)
                if found >= 0:
                    combo.setCurrentIndex(found)
        self._restoring = False

    def _on_option_changed(self, combo_index: int) -> None:
        if not self._ordered_opts:
            return

        # When the user changes a combo interactively, reset all later combos
        # so stale selections don't leak through into newly-invalid contexts.
        if not self._restoring:
            for j in range(combo_index + 1, len(self._ordered_opts)):
                _, _, c = self._ordered_opts[j]
                c.blockSignals(True)
                c.setCurrentIndex(0)
                c.blockSignals(False)

        # Re-filter every downstream combo so its value list matches the
        # current preceding selections — not just combo_index + 1.
        for j in range(combo_index, len(self._ordered_opts) - 1):
            self._repopulate_next(j)

    def _repopulate_next(self, combo_index: int) -> None:
        """Repopulate the combo at *combo_index + 1* based on selections 0..combo_index."""
        _, _, changed_combo = self._ordered_opts[combo_index]
        has_val = bool(changed_combo.currentData())
        next_opt, next_all_vals, next_combo = self._ordered_opts[combo_index + 1]
        next_all_pairs = self._raw_value_pairs.get(next_opt, [])

        if has_val:
            preceding = {
                self._ordered_opts[k][0]: self._ordered_opts[k][2].currentData() or ""
                for k in range(combo_index + 1)
            }
            preceding_labels = {
                self._ordered_opts[k][0]: self._ordered_opts[k][2].currentText() or ""
                for k in range(combo_index + 1)
            }
            valid_vals = set(self._module.get_valid_option_values(
                self._printer_combo.currentData() or "",
                preceding, preceding_labels, next_opt, next_all_vals, next_all_pairs,
            ))
        else:
            # 'Printer Default' = let the driver decide. Nothing to filter
            # against, so the next combo shows every value it offers —
            # otherwise drivers like HP Bonjour (no Auto in Paper Source)
            # would force the user to pick a tray to reach Paper Size.
            valid_vals = set(next_all_vals)

        next_combo.blockSignals(True)
        next_combo.clear()
        next_combo.addItem(tr("Printer Default"), "")
        for display, raw_val in next_all_pairs:
            if raw_val in valid_vals:
                next_combo.addItem(display, raw_val)
        next_combo.blockSignals(False)

    def set_ti2_path(self, path: Path) -> None:
        """Programmatically load a .ti2 file (cross-tab auto-population).

        THE CONTROLLER GOES IN, exactly as this tab's own Browse passes it.
        `resolve_ti2` routes on that argument: with a controller it takes the
        #130 model (A1a/A2a/A2b/A1b), without one it falls through to the
        pre-#130 "Load Test Session" window. This omission meant EVERY
        cross-tab propagation of a chart took the legacy road whatever the bar
        said — and the legacy road offers to "copy the files to a new subfolder
        so you can build a separate ICC profile" about a project ChromIQ has
        just filed a measurement into (R6 F2, driven `d03_who_clears_check.py`).
        """
        from ui.ti2_loader import resolve_ti2
        if not path.exists():
            return
        result = resolve_ti2(self, path, self._settings,
                             getattr(self, "_target_ctl", None))
        if result is None:
            self.ti2_load_cancelled.emit()
            return
        ti2_path, tiffs = result
        self._current_ti2 = ti2_path
        self.ti2_loaded.emit(ti2_path)
        if ti2_path != path:
            self.chart_relocated.emit(ti2_path)
        if tiffs:
            self.load_tiffs(tiffs)

    def note_generated_chart(self, ti2_path: "Path | None") -> None:
        """A chart was just generated (or cleared) in Create Chart — track its
        .ti2 and re-read the Colour row from it.

        Without this the row judged the PREVIOUS chart: generation handed this
        tab only the page images, so a chart from the FROM PROFILE GAMUT
        module — already converted, §3.1a says force Raw — still offered
        "Through the profile", and even defaulted to it (Basti, 2026-08-10).
        Deliberately emits nothing: the generation flow already tells the
        other tabs itself.
        """
        self._current_ti2 = Path(ti2_path) if ti2_path else None
        self._update_colour_row_visible()

    def apply_loaded_ti2(self, ti2_path: Path) -> None:
        """Cross-tab sync entry — path is already resolved and on disk.

        Skips resolve_ti2() so the user is not re-prompted with the
        "Continue / Use as base for a new profile" dialog when another
        tab has already loaded this chart into the working folder.
        Deliberately does not emit ti2_loaded — that would echo back
        through the cross-tab graph and re-trigger the sender.
        """
        from ui.ti2_loader import _related_files
        if not ti2_path.exists() or ti2_path == self._current_ti2:
            return
        _, tiffs = _related_files(ti2_path)
        self._current_ti2 = ti2_path
        if tiffs:
            self.load_tiffs(tiffs)

    def _reveal_folder(self) -> None:
        """Open the current chart's folder in the file manager (Knut — same
        button as the other tabs, for consistency)."""
        from core.preset_store import reveal_in_file_manager
        ti2 = getattr(self, "_current_ti2", None)
        if ti2 is not None:
            target = Path(ti2).parent
        else:
            custom = str(self._settings.get("custom_output_path", "")).strip()
            target = Path(custom).expanduser() if custom else Path.home() / "ChromIQ"
        reveal_in_file_manager(target)

    def _on_load_ti2(self) -> None:
        from ui.ti2_loader import resolve_ti2
        path = open_file_dialog(
            self, "Select .ti2 file to load its chart", "ArgyllCMS target files (*.ti2)",
            extra_path=self._settings.get("custom_output_path", ""),
            declutter_settings=self._settings,
        )
        if not path:
            return
        result = resolve_ti2(self, Path(path), self._settings,
                             getattr(self, "_target_ctl", None))
        if result is None:
            return
        ti2_path, tiffs = result
        if ti2_path != self._current_ti2:
            self._current_ti2 = ti2_path
            self.ti2_replaced.emit()
        self.ti2_loaded.emit(ti2_path)
        # Mirror this explicit load into the Create Chart tab (reflect-only).
        self.chart_load_requested.emit(ti2_path, list(tiffs or []))
        if tiffs:
            self.load_tiffs(tiffs)
        else:
            self._set_status("No TIFF files found matching the selected .ti2 file.")

    def _on_load_image(self) -> None:
        """#117 (Knut): print any TIFF raw. Deliberately print-only — the
        measuring workflow needs the chart's own .ti2 (grid button), and a
        bare image can't provide patch geometry."""
        from ui.widgets import open_files_dialog
        paths = open_files_dialog(
            self, tr("Select the TIFF images to print"),
            "TIFF images (*.tif *.tiff)",
            extra_path=self._settings.get("custom_output_path", ""),
            preview=True,
            declutter_settings=self._settings,
        )
        if not paths:
            return
        # A foreign image invalidates the loaded chart context downstream
        # (Profile / Check tabs) — same as loading a different chart.
        if self._current_ti2 is not None:
            self._current_ti2 = None
            self.ti2_replaced.emit()
        self.load_tiffs([Path(p) for p in paths])
        self._set_status(tr(
            "Image loaded for printing (no colour management). To measure a "
            "chart afterwards, load its .ti2 with the grid button — an image "
            "alone carries no patch geometry."))

    def _blocked_by_new_run(self) -> bool:
        """True — and the explaining pop-up has been shown — when the bar's
        **Profile run** is "New run" (#130, Knut). A run has to exist before its
        chart can be printed."""
        ctl = getattr(self, "_target_ctl", None)
        if ctl is None or ctl.target.profile_run:
            return False
        from PyQt6.QtWidgets import QMessageBox
        from core.measurement_target import new_run_guard_message
        QMessageBox.information(self, tr("Choose a profile run to print"),
                                new_run_guard_message("print"))
        return True

    def _on_print_current(self) -> None:
        if not self._preview._pages:
            return
        if self._blocked_by_new_run():
            return
        pages = [self._preview._pages[self._preview._current]]
        # Feature A: the verification conversion + route handling sit below
        # BOTH print buttons, before the two print paths split (§5 A2.2).
        pages = self._apply_verification_colour(pages)
        if pages is None:
            return
        if self._settings.get("use_native_print_dialog", False):
            self._print_native(pages)
            return
        self._print_pages(pages)

    def _on_print_all(self) -> None:
        if not self._preview._pages:
            return
        if self._blocked_by_new_run():
            return
        pages = self._apply_verification_colour(list(self._preview._pages))
        if pages is None:
            return
        if self._settings.get("use_native_print_dialog", False):
            self._print_native(pages)
            return
        self._print_pages(pages)

    def _print_pages(self, pages: list[tuple[Path, int]]) -> None:
        """Run pre-send checks + preflight once, then submit each page."""
        printer = self._printer_combo.currentData() or ""
        if not printer:
            QMessageBox.warning(self, tr("No Printer"), tr("Please select a printer before printing."))
            return

        if not self._printer.is_printer_reachable(printer):
            QMessageBox.critical(
                self, tr("Printer Offline"),
                tr("The printer \"{printer}\" appears to be offline or unreachable.\n"
                   "Please check that it is powered on and connected."
                   ).format(printer=printer),
            )
            return

        if not self._handle_stuck_jobs(printer):
            return

        selected_opts = {k: (c.currentData() or "") for k, c in self._option_combos.items()}
        first_tiff, _ = pages[0]
        orientation, page_size_pt, mismatch = self._compute_geometry(
            printer, selected_opts, first_tiff
        )

        # Independent of the preflight setting: borderless physically cannot
        # print at 100% (the driver enlarges the page a few percent so ink
        # reaches past the paper edges — Epson PPDs bake a 1.03–1.07
        # cupsBorderlessScalingFactor into their borderless sizes, Canon
        # scales via its extension setting). A scaled chart shifts every
        # patch, so always warn before wasting paper and ink.
        if _borderless_selected(selected_opts) and not self._confirm_borderless():
            return

        if self._settings.get("confirm_before_printing", True):
            if not self._show_preflight(
                printer, selected_opts, orientation, page_size_pt,
                mismatch, len(pages),
            ):
                return
        elif mismatch:
            log.warning("Preflight disabled; printing despite mismatch: %s", mismatch)

        submitted = False
        for path, frame in pages:
            if self._send_page(path, frame, orientation, page_size_pt):
                submitted = True
        self._commit_print_record(submitted)

    def _commit_print_record(self, submitted: bool) -> None:
        """Write the held print record, or drop it (R6 F5).

        Called by both print paths and by nothing else, so a route that ends in
        a refusal, a cancelled window or a rejected job leaves no record at
        all — and the next sheet is asked about rather than assumed.
        """
        pending, self._pending_print_record = self._pending_print_record, None
        if pending is None or not submitted:
            if pending is not None:
                log.info("nothing was submitted; no print record written")
            return
        ti2, kwargs = pending
        from workflow import verification_print as vp
        vp.write_print_record(ti2, **kwargs)

    def _confirm_borderless(self) -> bool:
        """Warn that borderless scales the chart. Returns False to cancel."""
        dlg = QMessageBox(self)
        dlg.setWindowTitle(tr("Borderless Will Scale the Chart"))
        dlg.setIcon(QMessageBox.Icon.Warning)
        dlg.setText(
            tr("Borderless printing enlarges the page by a few percent so the "
            "ink reaches past the paper edges. The printer driver does this "
            "and it cannot be turned off — it is what borderless means.\n\n"
            "A profiling chart must print at exactly 100%: enlarging it "
            "shifts every patch, so the measurement reads the wrong "
            "positions.\n\n"
            "Switch borderless off and print with borders instead — the "
            "chart's white margins are made for that.")
        )
        anyway_btn = dlg.addButton(
            tr("Print Borderless Anyway"), QMessageBox.ButtonRole.DestructiveRole
        )
        cancel_btn = dlg.addButton(QMessageBox.StandardButton.Cancel)
        dlg.setDefaultButton(cancel_btn)
        dlg.exec()
        if dlg.clickedButton() is anyway_btn:
            log.warning("Borderless print confirmed by user despite scaling warning")
            return True
        return False

    def _handle_stuck_jobs(self, printer: str) -> bool:
        """Prompt to clear stuck jobs. Returns False if user cancels."""
        stuck = self._module.get_stuck_jobs(printer)
        if not stuck:
            return True
        n = len(stuck)
        dlg = QMessageBox(self)
        dlg.setWindowTitle(tr("Stuck Print Jobs Detected"))
        dlg.setIcon(QMessageBox.Icon.Warning)
        if n == 1:
            head = tr("There is 1 stuck print job in the queue for \"{printer}\"."
                      ).format(printer=printer)
        else:
            head = tr("There are {n} stuck print jobs in the queue for \"{printer}\"."
                      ).format(n=n, printer=printer)
        dlg.setText(
            head + "\n\n"
            + tr("Stuck jobs can block new print jobs from being processed.\n"
                 "Clear them before printing?")
        )
        clear_btn  = dlg.addButton(tr("Clear && Print"),  QMessageBox.ButtonRole.AcceptRole)
        dlg.addButton(tr("Print Anyway"), QMessageBox.ButtonRole.DestructiveRole)
        cancel_btn = dlg.addButton(QMessageBox.StandardButton.Cancel)
        dlg.setDefaultButton(clear_btn)
        dlg.exec()
        clicked = dlg.clickedButton()
        if clicked is cancel_btn:
            return False
        if clicked is clear_btn:
            cleared = self._module.cancel_all_jobs(printer)
            log.info("Cleared %d stuck job(s) before printing", cleared)
        return True

    def _compute_geometry(
        self,
        printer: str,
        selected_opts: dict[str, str],
        tiff_path: Path,
    ) -> tuple[int | None, tuple[float, float] | None, str | None]:
        """Return (orientation, page_size_pt, mismatch_msg) for the given selection.

        Any/all may be None if PageSize is unset or the PPD doesn't declare
        physical dimensions (typical for AirPrint/Driverless queues).
        """
        size_key = next(
            (k for k in _PAGE_SIZE_KEYS if selected_opts.get(k)),
            None,
        )
        if size_key is None:
            return None, None, None
        size_raw = selected_opts[size_key]
        # Some vendor drivers (e.g. Epson EPIJ_Size) use opaque integer codes
        # for raw values but key *PaperDimension by display label. Pass both.
        size_display = ""
        combo = self._option_combos.get(size_key)
        if combo is not None:
            size_display = combo.currentText()
        page_dims = self._module.get_page_size_points(printer, size_raw, size_display)
        if not page_dims:
            return None, None, None
        imageable = self._module.get_imageable_area_points(printer, size_raw, size_display)
        try:
            tiff_w_pt, tiff_h_pt = read_tiff_dimensions_points(tiff_path)
        except Exception as exc:
            log.warning("Could not read TIFF dimensions for %s: %s", tiff_path.name, exc)
            return None, page_dims, None
        page_w_pt, page_h_pt = page_dims
        orientation = compute_orientation(tiff_w_pt, tiff_h_pt, page_w_pt, page_h_pt)
        mismatch = check_size_mismatch(
            tiff_w_pt, tiff_h_pt, page_w_pt, page_h_pt, imageable_pt=imageable,
        )
        return orientation, page_dims, mismatch

    def _show_preflight(
        self,
        printer: str,
        selected_opts: dict[str, str],
        orientation: int | None,
        page_size_pt: tuple[float, float] | None,
        mismatch: str | None,
        page_count: int,
    ) -> bool:
        """Show the preflight dialog. Returns True if user accepts."""
        rows: list[tuple[str, str]] = [("Printer", printer)]
        # Per-option rows, using the human-readable category label and the
        # selected combo's display text (not the raw CUPS value).
        for opt_name, combo in self._option_combos.items():
            raw = combo.currentData() or ""
            if not raw:
                continue
            # Get the category label from the layout row's QLabel.
            label = self._option_label_for(opt_name)
            rows.append((label, combo.currentText()))
        if orientation is not None:
            rows.append((
                "Orientation",
                "Landscape (auto)" if orientation == ORIENTATION_LANDSCAPE
                else "Portrait (auto)",
            ))
        if page_size_pt is not None:
            w_mm = page_size_pt[0] * 25.4 / 72.0
            h_mm = page_size_pt[1] * 25.4 / 72.0
            rows.append(("Media size", f"{w_mm:.0f} × {h_mm:.0f} mm"))
        rows.append(("Duplex", "Off (forced)"))
        rows.append(("Colour management", "Off (forced)"))

        warnings: list[str] = []
        if mismatch:
            warnings.append(mismatch)
        if _borderless_selected(selected_opts):
            warnings.append(
                "Borderless is enabled — the driver enlarges the page a few "
                "percent to reach past the paper edges, so the chart will NOT "
                "print at 100% and patches shift. Print with borders instead."
            )

        dlg = PreflightDialog(rows, warnings, page_count, self)
        accepted = dlg.exec() == QDialog.DialogCode.Accepted
        if accepted and dlg.dont_ask_again():
            self._settings.set("confirm_before_printing", False)
        return accepted

    def _option_label_for(self, opt_name: str) -> str:
        """Return the human-readable category label currently shown next to
        the combo for *opt_name* (e.g. 'Paper Size', 'Media Type')."""
        for i in range(self._opts_layout.count()):
            item = self._opts_layout.itemAt(i)
            layout = item.layout() if item else None
            if layout is None:
                continue
            # First widget in the row is the QLabel, second is the QComboBox.
            lbl_item = layout.itemAt(0)
            combo_item = layout.itemAt(1)
            if not lbl_item or not combo_item:
                continue
            if combo_item.widget() is self._option_combos.get(opt_name):
                lbl = lbl_item.widget()
                if isinstance(lbl, QLabel):
                    return lbl.text().rstrip(":")
        return opt_name

    def _send_page(
        self,
        tiff_path: Path,
        frame: int = 0,
        orientation: int | None = None,
        page_size_pt: tuple[float, float] | None = None,
    ) -> bool:
        """Submit one page. Returns True when the printing system ACCEPTED it.

        The return value is what decides whether a print record is written
        (R6 F5), so it says only what it can prove: the job was handed to CUPS
        and CUPS took it. Whether ink reached paper is not knowable from here,
        and is not what the record claims.
        """
        printer = self._printer_combo.currentData() or ""
        if not printer:
            QMessageBox.warning(self, tr("No Printer"), tr("Please select a printer before printing."))
            return False

        # Extract the target frame to a temporary single-page TIFF when needed.
        tmp_path: Path | None = None
        try:
            img = Image.open(tiff_path)
            n_frames = getattr(img, "n_frames", 1)
            if n_frames > 1 or frame > 0:
                img.seek(min(frame, n_frames - 1))
                fd, tmp_str = tempfile.mkstemp(suffix=".tif")
                os.close(fd)
                tmp_path = Path(tmp_str)
                img.save(tmp_path, format="TIFF")
                print_path = tmp_path
            else:
                print_path = tiff_path
        except Exception as exc:
            QMessageBox.critical(
                self, tr("TIFF Error"),
                tr("Cannot read TIFF file:\n{name}\n\n{exc}").format(name=tiff_path.name, exc=exc),
            )
            return False

        selected_opts = {k: (c.currentData() or "") for k, c in self._option_combos.items()}
        config = self._module.build_config(printer=printer, options=selected_opts)
        self._set_status(tr("Sending {name} (page {page}) to {printer}…").format(
            name=tiff_path.name, page=frame + 1, printer=printer))

        # `print_job_ps` reports the exit code through `on_finish`, and calls it
        # before returning on every one of its paths (PS, the PDF retry, the
        # TIFF retry, and a failure to generate PostScript at all). Recorded in
        # a cell rather than returned, so a path that ever became asynchronous
        # would leave this False — which asks the person how the sheet was
        # printed instead of assuming, the safe way round.
        accepted = [False]

        def _cleanup_and_finish(code: int) -> None:
            if tmp_path and tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
            accepted[0] = (code == 0)
            self._on_print_done(code)

        ink_channels = _find_sidecar_channels(tiff_path)
        self._printer.print_job_ps(
            print_path, config,
            ink_channels=ink_channels,
            on_finish=_cleanup_and_finish,
            orientation=orientation,
            page_size_pt=page_size_pt,
            pdf_fallback=is_macos() and bool(
                self._settings.get("pdf_print_fallback", False)
            ),
        )
        return accepted[0]

    def _on_print_done(self, code: int) -> None:
        if code == 0:
            self._set_status(tr("Print job submitted successfully."))
        else:
            self._set_status(tr("Print failed (lp exit code {code}).").format(code=code))
            QMessageBox.critical(
                self, tr("Print Error"),
                tr("CUPS rejected the print job (exit code {code}).\n"
                   "Check that the printer is online and the selected options are "
                   "valid.").format(code=code),
            )

    def _on_clear_queue(self) -> None:
        printer = self._printer_combo.currentData() or ""
        if not printer:
            QMessageBox.warning(self, tr("No Printer"), tr("Select a printer first."))
            return
        count = self._module.cancel_all_jobs(printer)
        if count:
            self._set_status(f"Cleared {count} job{'s' if count != 1 else ''} from the queue.")
        else:
            self._set_status("No jobs in the queue to clear.")

    def _set_status(self, text: str) -> None:
        self._status_lbl.setText(text)
        self._status_lbl.setVisible(bool(text))

    def _set_print_buttons_enabled(self, enabled: bool) -> None:
        self._print_page_btn.setEnabled(enabled)
        self._print_all_btn.setEnabled(enabled)

    def _on_save_defaults(self) -> None:
        s = self._settings
        printer = self._printer_combo.currentData() or ""
        s.set("last_printer", printer)
        if printer and self._option_combos:
            pairs = "|".join(
                f"{k}={combo.currentData() or ''}"
                for k, combo in self._option_combos.items()
            )
            s.set(f"print_opts_{printer}", pairs)
        self._set_status("Print settings saved as defaults.")

    def _restore_defaults(self) -> None:
        pass

    def shutdown(self) -> None:
        """Tear down option widgets and signals before QApplication destructs.

        Mirrors the QtWebEngine shutdown pattern in
        ui/gamut_panel.py::shutdown_webengine: disconnect signals, reparent
        children to None, deleteLater, then pump the event loop so the
        deferred deletes actually run while the main loop is still alive.
        Without this, SIP can follow a half-freed wrapper for one of the
        option combos during QApplication dealloc and EXC_BAD_ACCESS the
        process (issue #19 — macOS "ChromIQ quit unexpectedly").
        """
        try:
            self._printer_combo.currentIndexChanged.disconnect()
        except (TypeError, RuntimeError):
            pass

        for combo in list(self._option_combos.values()):
            try:
                combo.currentIndexChanged.disconnect()
            except (TypeError, RuntimeError):
                pass
            try:
                combo.setParent(None)
                combo.deleteLater()
            except RuntimeError:
                pass

        # Clear the options group's layout so any sibling labels / placeholder
        # widgets get the same reparent + deleteLater treatment as the combos.
        self._clear_layout(self._opts_layout)

        self._option_combos.clear()
        self._ordered_opts.clear()
        self._raw_value_pairs.clear()

        app = QApplication.instance()
        if app is not None:
            for _ in range(3):
                app.processEvents()

    # ------------------------------------------------------------------
    # Native macOS print dialog
    # ------------------------------------------------------------------

    def apply_native_dialog_mode(self) -> None:
        self._set_native_mode(bool(self._settings.get("use_native_print_dialog", False)))
        header = getattr(self, "_header", None)
        if header is not None:
            header.set_tooltip(*self._compute_print_tooltip())

    def _compute_print_tooltip(self) -> tuple[str, str]:
        if is_windows():
            return tr(_TT_TITLE_PRINT), tr(_TT_BODY_PRINT_WINDOWS)
        if is_linux():
            return tr(_TT_TITLE_PRINT), tr(_TT_BODY_PRINT_LINUX)
        if is_macos():
            if bool(self._settings.get("use_native_print_dialog", False)):
                return tr(_TT_TITLE_PRINT), tr(_TT_BODY_PRINT_MACOS_NATIVE)
            return tr(_TT_TITLE_PRINT), tr(_TT_BODY_PRINT_MACOS_BYPASS)
        return tr(_TT_TITLE_PRINT), tr(_TT_BODY_PRINT_MACOS_BYPASS)

    def _set_native_mode(self, enabled: bool) -> None:
        import sys as _sys
        self._printer_grp.setVisible(not enabled)
        self._opts_grp.setVisible(not enabled)
        # The spacer used to centre the warning label between the scroll area
        # and the buttons. With the warning inside the scroll area (Basti,
        # 2026-08-09) the spacer only fought the scroll for height — half the
        # panel went to pure emptiness while the warning was pushed out of
        # the viewport, invisible behind macOS's overlay scrollbar.
        self._native_warn_spacer.setVisible(False)
        if enabled:
            if _sys.platform == "win32":
                self._warn_lbl.setText(
                    tr("⚠  You are printing via the Windows printer dialog. You must disable "
                    "colour management in your printer driver before printing — otherwise "
                    "the printer applies its own corrections and the chart will be unusable "
                    "for accurate ICC profiling.\n\n"
                    "How to disable colour management: after clicking Print, open the "
                    "printer's Properties / Preferences and look for a colour-management "
                    "section:\n"
                    "  • Epson:  \"Epson Color Controls\" → Off (No Color Adjustment)\n"
                    "  • Canon:  \"Color Options\" → Manual → None\n"
                    "  • HP:     \"Color Options\" → Application Managed Colors\n"
                    "  • Others: look for \"No Color Management\", \"Off\", or "
                    "\"Application Controlled\"\n\n"
                    "Allow pigment inks to dry fully before measuring "
                    "(at least 1 h; 24 h for best accuracy).")
                )
            else:
                self._warn_lbl.setText(
                    tr("⚠  You are printing via the macOS printer dialog. Verify that the paper, "
                    "media type, and quality you pick match the media you are printing on — "
                    "wrong settings cause incorrect ink laydown and invalid colour "
                    "measurements.\n\n"
                    "Colour management is disabled automatically. ChromIQ declares the chart "
                    "as already being in the printer's own colour space (so no colour "
                    "transform is applied) and sets the driver's \"no colour correction\" "
                    "option — the same technique dedicated tools like Print-Tool use. The "
                    "dialog's \"Color Matching\" pane will be greyed out; that is expected.\n\n"
                    "You don't need to change any colour setting. Just don't switch an ICC "
                    "profile or rendering intent back on, and pick the correct paper / media "
                    "type and print quality.\n\n"
                    "IMPORTANT: never click Cancel (or Abort) in any of the dialog's panes "
                    "or sub-windows — always close them with OK. Cancel reverts the "
                    "colour-off setting ChromIQ applied; OK keeps it. When in doubt, OK is "
                    "always the safe button.\n\n"
                    "Prefer no dialog at all? Untick \"Use default macOS printer dialog\" in "
                    "Preferences to send the chart straight to the queue via lp (colour "
                    "management is forced off there too).\n\n"
                    "Allow pigment inks to dry fully before measuring "
                    "(at least 1 h; 24 h for best accuracy).")
                )
        else:
            if is_macos() and bool(self._settings.get("pdf_print_fallback", False)):
                fallback_sentence = (
                    "If CUPS rejects PostScript (most non-PostScript printers), it "
                    "automatically retries with an exact-size PDF that keeps the chart "
                    "at 100% scale (edges beyond the printable area are clipped, "
                    "never shrunk)."
                )
            else:
                fallback_sentence = (
                    "If CUPS rejects PostScript (e.g. AirPrint or Driverless drivers), "
                    "it automatically retries by sending the TIFF directly with "
                    "colour-space-aware raster options."
                )
            self._warn_lbl.setText(
                "⚠  Verify that all print settings above match the media you are printing on.\n\n"
                "Wrong media type or quality settings will cause incorrect ink laydown and "
                "invalid colour measurements. Allow pigment inks to dry fully before measuring "
                "(at least 1 h; 24 h for best accuracy).\n\n"
                "Colour management is disabled automatically. ChromIQ converts the chart to "
                "PostScript and sends it via lp, bypassing ColorSync entirely. "
                + fallback_sentence
            )

    def _print_native(self, pages: list[tuple[Path, int]]) -> None:
        import sys as _sys
        if _sys.platform == "darwin":
            submitted = False
            try:
                from workflow.native_print_macos import print_frames, ColorManagementMismatch
                try:
                    submitted = bool(print_frames(pages))
                except ColorManagementMismatch as exc:
                    # The job WAS submitted; only the colour-management lock
                    # could not be verified afterwards. That is a print, so the
                    # record describes it — and the window below says what
                    # could not be checked about it.
                    submitted = True
                    log.warning("Native macOS print: %s", exc)
                    QMessageBox.warning(
                        self, tr("Colour Management Lock Not Verified"),
                        tr("The print job was sent, but ChromIQ could not verify that "
                           "the printer driver's colour management was disabled.\n\n"
                           "Details: {exc}\n\n"
                           "The print may have been colour-managed by the driver. "
                           "Check the swatch with Digital Color Meter or reprint "
                           "after switching to the non-native (standard) print mode "
                           "in Preferences.").format(exc=exc),
                    )
            except Exception as exc:
                log.error("Native macOS print failed: %s", exc)
                QMessageBox.critical(
                    self, tr("Print Failed"),
                    tr("Could not open the macOS print dialog:\n{exc}").format(exc=exc),
                )
            self._commit_print_record(submitted)
            return
        self._print_native_qt(pages)

    def _print_native_qt(self, pages: list[tuple[Path, int]]) -> None:
        from PyQt6.QtPrintSupport import QPrinter, QPrintDialog
        from PyQt6.QtGui import QPainter, QImage
        from PyQt6.QtWidgets import QDialog

        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        dialog = QPrintDialog(printer, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            # Cancelled at the OS dialog: nothing was printed, so no record.
            self._commit_print_record(False)
            return

        painter = QPainter(printer)
        drawn = 0
        for i, (tiff_path, frame) in enumerate(pages):
            if i > 0:
                printer.newPage()
            try:
                img = Image.open(tiff_path)
                n_frames = getattr(img, "n_frames", 1)
                img.seek(min(frame, n_frames - 1))
                display_img = img.convert("RGB")
                import io as _io
                buf = _io.BytesIO()
                display_img.save(buf, format="PNG")
                buf.seek(0)
                qimg = QImage()
                qimg.loadFromData(buf.read())
                if qimg.isNull():
                    log.warning("Native print: QImage is null for %s frame %d", tiff_path.name, frame)
                    continue
                painter.save()
                rect = painter.viewport()
                size = qimg.size()
                size.scale(rect.size(), Qt.AspectRatioMode.KeepAspectRatio)
                painter.setViewport(rect.x(), rect.y(), size.width(), size.height())
                painter.setWindow(qimg.rect())
                painter.drawImage(0, 0, qimg)
                painter.restore()
                drawn += 1
            except Exception as exc:
                log.warning("Native print: cannot render %s frame %d: %s", tiff_path.name, frame, exc)
        painter.end()
        # A record only if a page really went onto the QPrinter: every page
        # failing to render leaves an empty job and nothing to describe.
        self._commit_print_record(drawn > 0)
