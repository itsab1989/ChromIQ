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
from ui.widgets import NoScrollComboBox, PatchGridButton, load_refresh_icon, open_file_dialog
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
    "paper feed), enable \"Use the native print dialog\" in Preferences."
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
    "\"Use the native print dialog\" in Preferences to use the lp path instead "
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
        # Sequential-enabling state — populated in _rebuild_option_rows
        self._ordered_opts: list[tuple[str, list[str], QComboBox]] = []
        self._raw_value_pairs: dict[str, list[tuple[str, str]]] = {}
        self._restoring: bool = False
        self._mode: str = "dark"

        self._build_ui()

    # ------------------------------------------------------------------
    def set_appearance(self, mode: str) -> None:
        """Restyle the AirPrint info box when the theme changes."""
        new_mode = "light" if mode == "light" else "dark"
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

        # Print options — dynamically built from CUPS lpoptions output
        self._opts_grp = QGroupBox(tr("Print Options"), scroll_content)
        self._opts_layout = QVBoxLayout(self._opts_grp)
        self._option_combos: dict[str, QComboBox] = {}
        self._opts_layout.addWidget(
            QLabel(tr("Select a printer to see its options."), scroll_content)
        )
        scl.addWidget(self._opts_grp)

        self._printer_combo.currentIndexChanged.connect(self._on_printer_changed)

        scl.addStretch()
        scroll.setWidget(scroll_content)
        ll.addWidget(scroll, stretch=1)

        # Warning label — placed between scroll area and "Feed the beast" block
        self._warn_lbl = QLabel("", left)
        self._warn_lbl.setObjectName("warning")
        self._warn_lbl.setWordWrap(True)
        ll.addWidget(self._warn_lbl)

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
        beast_headline = QLabel(
            tr("Feed the beast<span style=\"color: {SPEC_AMBER}; font-style: italic;\">!</span>").format(SPEC_AMBER=SPEC_AMBER),
            beast_box,
        )
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
        for _color in TAB_COLORS:
            _seg = QFrame(beast_box)
            _seg.setFixedSize(22, 2)
            _seg.setStyleSheet(f"background-color: {_color}; border: none;")
            beast_bar.addWidget(_seg)
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
        self._refresh_printers()
        self._restore_defaults()
        self.apply_native_dialog_mode()

    # ------------------------------------------------------------------

    def load_tiffs(self, paths: list[Path]) -> None:
        """Called by main window after chart generation."""
        self._tiff_pages = paths
        if paths:
            self._preview.set_notice(None)     # a real chart — drop guidance
        self._preview.load_tiff(paths)
        self._set_print_buttons_enabled(bool(paths))

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
        box.setStyleSheet(
            f"#airprintInfoBox {{"
            f"  background-color: {bg};"
            f"  border: 1px solid {border};"
            "  border-radius: 6px;"
            "}"
            "#airprintInfoBox QLabel {"
            "  background: transparent;"
            "}"
            f"#airprintInfoBox QLabel#airprintInfoTitle {{"
            f"  font-weight: bold; color: {title_color};"
            "}"
            f"#airprintInfoBox QLabel#airprintInfoBody {{"
            f"  color: {body_color};"
            "}"
        )

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
        """Programmatically load a .ti2 file (cross-tab auto-population)."""
        from ui.ti2_loader import resolve_ti2
        if not path.exists():
            return
        result = resolve_ti2(self, path, self._settings)
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
        if self._settings.get("use_native_print_dialog", False):
            path, frame = self._preview._pages[self._preview._current]
            self._print_native([(path, frame)])
            return
        page = self._preview._pages[self._preview._current]
        self._print_pages([page])

    def _on_print_all(self) -> None:
        if not self._preview._pages:
            return
        if self._blocked_by_new_run():
            return
        if self._settings.get("use_native_print_dialog", False):
            self._print_native(list(self._preview._pages))
            return
        self._print_pages(list(self._preview._pages))

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

        for path, frame in pages:
            self._send_page(path, frame, orientation, page_size_pt)

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
    ) -> None:
        printer = self._printer_combo.currentData() or ""
        if not printer:
            QMessageBox.warning(self, tr("No Printer"), tr("Please select a printer before printing."))
            return

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
            return

        selected_opts = {k: (c.currentData() or "") for k, c in self._option_combos.items()}
        config = self._module.build_config(printer=printer, options=selected_opts)
        self._set_status(tr("Sending {name} (page {page}) to {printer}…").format(
            name=tiff_path.name, page=frame + 1, printer=printer))

        def _cleanup_and_finish(code: int) -> None:
            if tmp_path and tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
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
        self._native_warn_spacer.setVisible(enabled)
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
                    "Prefer no dialog at all? Untick \"Use the native print dialog\" in "
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
            try:
                from workflow.native_print_macos import print_frames, ColorManagementMismatch
                try:
                    print_frames(pages)
                except ColorManagementMismatch as exc:
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
            return
        self._print_native_qt(pages)

    def _print_native_qt(self, pages: list[tuple[Path, int]]) -> None:
        from PyQt6.QtPrintSupport import QPrinter, QPrintDialog
        from PyQt6.QtGui import QPainter, QImage
        from PyQt6.QtWidgets import QDialog

        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        dialog = QPrintDialog(printer, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        painter = QPainter(printer)
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
            except Exception as exc:
                log.warning("Native print: cannot render %s frame %d: %s", tiff_path.name, frame, exc)
        painter.end()
