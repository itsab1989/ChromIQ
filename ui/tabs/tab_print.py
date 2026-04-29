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
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from core.logger import get_logger
from ui.tab_header import TabHeader
from ui.tiff_preview import TiffPreview
from ui.tooltip_button import TooltipButton
from ui.widgets import NoScrollComboBox, load_folder_icon, load_refresh_icon, open_file_dialog
from workflow.cups_printer import CupsRawPrinter
from workflow.print_manager import PrintModule

if TYPE_CHECKING:
    from core.settings import AppSettings

log = get_logger(__name__)


class TabPrint(QWidget):

    ti2_loaded = pyqtSignal(Path)  # emitted when the user loads a .ti2 file
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
        # Sequential-enabling state — populated in _rebuild_option_rows
        self._ordered_opts: list[tuple[str, list[str], QComboBox]] = []
        self._raw_value_pairs: dict[str, list[tuple[str, str]]] = {}
        self._restoring: bool = False

        self._build_ui()

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

        ll.addWidget(TabHeader(
            "STEP 02 · PRINT TARGET", "Print test chart", "#ffb42d", left
        ))

        # Printer selection
        printer_grp = QGroupBox("Printer", left)
        pg = QVBoxLayout(printer_grp)

        pr_row = QHBoxLayout()
        pr_row.addWidget(QLabel("Printer:", left))
        self._printer_combo = NoScrollComboBox(left)
        pr_row.addWidget(self._printer_combo, stretch=1)

        refresh_btn = QPushButton(left)
        refresh_btn.setIcon(load_refresh_icon("refresh_print"))
        refresh_btn.setFixedSize(34, 34)
        refresh_btn.setStyleSheet("QPushButton { padding: 0; min-height: 0; }")
        refresh_btn.setToolTip("Refresh printer list")
        refresh_btn.clicked.connect(self._refresh_printers)
        pr_row.addWidget(refresh_btn)

        pr_row.addWidget(TooltipButton(
            "Printer Selection",
            "Select the printer to send the chart to.  Only printers installed in\n"
            "the system CUPS print queue are listed.\n\n"
            "The TIFF is sent directly via lp with the options you configure below.\n"
            "Color management is always disabled automatically.",
            left,
        ))
        pg.addLayout(pr_row)
        ll.addWidget(printer_grp)

        # Print options — dynamically built from CUPS lpoptions output
        self._opts_grp = QGroupBox("Print Options", left)
        self._opts_layout = QVBoxLayout(self._opts_grp)
        self._option_combos: dict[str, QComboBox] = {}
        self._opts_layout.addWidget(
            QLabel("Select a printer to see its options.", left)
        )
        ll.addWidget(self._opts_grp)

        self._printer_combo.currentIndexChanged.connect(self._on_printer_changed)

        # Warning label
        warn = QLabel(
            "⚠  Verify that all print settings above match the media you are printing on.\n\n"
            "Wrong media type or quality settings will cause incorrect ink laydown and "
            "invalid colour measurements. Allow pigment inks to dry fully before measuring "
            "(at least 1 h; 24 h for best accuracy).",
            left,
        )
        warn.setObjectName("warning")
        warn.setWordWrap(True)
        ll.addWidget(warn)

        # Load existing target button
        load_btn = QPushButton("Load existing target — select .ti2 file", left)
        load_btn.setIcon(load_folder_icon("folder_print"))
        load_btn.clicked.connect(self._on_load_ti2)
        ll.addWidget(load_btn)

        # Print buttons
        btn_row = QHBoxLayout()
        self._print_page_btn = QPushButton("Print\nCurrent Page", left)
        self._print_page_btn.setObjectName("primary")
        self._print_page_btn.clicked.connect(self._on_print_current)

        self._print_all_btn = QPushButton("Print All\nPages", left)
        self._print_all_btn.clicked.connect(self._on_print_all)

        self._save_defaults_btn = QPushButton("Save as\nDefaults", left)
        self._save_defaults_btn.clicked.connect(self._on_save_defaults)

        self._clear_queue_btn = QPushButton("Clear\nPrint Queue", left)
        self._clear_queue_btn.setToolTip(
            "Cancel all pending and stuck jobs for the selected printer."
        )
        self._clear_queue_btn.clicked.connect(self._on_clear_queue)

        btn_row.addWidget(self._print_page_btn)
        btn_row.addWidget(self._print_all_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._clear_queue_btn)
        btn_row.addWidget(self._save_defaults_btn)
        ll.addLayout(btn_row)

        # Status
        self._status_lbl = QLabel("", left)
        self._status_lbl.setWordWrap(True)
        ll.addWidget(self._status_lbl)

        ll.addStretch()

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
        lbl = QLabel("PRINT PREVIEW", right)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(
            "color: #808080; background: transparent; padding: 4px;"
            " font-family: Menlo; font-size: 9pt; font-weight: 300;"
        )
        rl.addWidget(lbl)
        self._preview = TiffPreview(right)
        rl.addWidget(self._preview, stretch=1)
        splitter.addWidget(right)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter)

        # Initial state
        self._set_print_buttons_enabled(False)
        self._refresh_printers()
        self._restore_defaults()

    # ------------------------------------------------------------------

    def load_tiffs(self, paths: list[Path]) -> None:
        """Called by main window after chart generation."""
        self._tiff_pages = paths
        self._preview.load_tiff(paths)
        self._set_print_buttons_enabled(bool(paths))

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
            self._printer_combo.addItem("No printers found", "")
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

    def _rebuild_option_rows(self, printer: str) -> None:
        while self._opts_layout.count():
            item = self._opts_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._option_combos.clear()
        self._ordered_opts.clear()
        self._raw_value_pairs.clear()

        if not printer:
            self._opts_layout.addWidget(QLabel("Select a printer to see its options.", self))
            return

        opts = self._module.query_options(printer)
        if not opts:
            box = QFrame(self)
            box.setFrameShape(QFrame.Shape.NoFrame)
            box.setObjectName("airprintInfoBox")
            box.setStyleSheet(
                "#airprintInfoBox {"
                "  background-color: #2a2000;"
                "  border: 1px solid #f9a825;"
                "  border-radius: 6px;"
                "}"
                "#airprintInfoBox QLabel {"
                "  background: transparent;"
                "}"
            )
            box_layout = QVBoxLayout(box)
            box_layout.setContentsMargins(10, 8, 10, 8)
            box_layout.setSpacing(6)

            title = QLabel("No configurable options detected", box)
            title.setStyleSheet("font-weight: bold; color: #fdd835;")
            box_layout.addWidget(title)

            body = QLabel(
                "macOS often installs an <b>AirPrint</b> or <b>Driverless</b> driver "
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
                "with all options available.",
                box,
            )
            body.setWordWrap(True)
            body.setTextFormat(Qt.TextFormat.RichText)
            body.setStyleSheet("color: #e0d5b0;")
            box_layout.addWidget(body)

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
            lbl = QLabel(f"{label}:", self)
            lbl.setMinimumWidth(160)
            row.addWidget(lbl)
            combo = NoScrollComboBox(self)
            combo.setMaxVisibleItems(12)
            combo.addItem("(not set)", "")
            for display, raw_val in value_pairs:
                combo.addItem(display, raw_val)
            # Only the first combo starts enabled; the rest unlock sequentially.
            combo.setEnabled(i == 0)
            row.addWidget(combo, stretch=1)
            self._opts_layout.addLayout(row)
            self._option_combos[opt_name] = combo
            self._ordered_opts.append((opt_name, [rv for _, rv in value_pairs], combo))
            combo.currentIndexChanged.connect(
                lambda _, idx=i: self._on_option_changed(idx)
            )

        # Restore saved values in insertion order so the enable-chain fires naturally.
        self._restoring = True
        for opt_name, _, combo in self._ordered_opts:
            saved_val = saved_printer_opts.get(opt_name, "")
            if saved_val and combo.isEnabled():
                found = combo.findData(saved_val)
                if found >= 0:
                    combo.setCurrentIndex(found)
        self._restoring = False

    def _on_option_changed(self, combo_index: int) -> None:
        if not self._ordered_opts:
            return
        _, _, changed_combo = self._ordered_opts[combo_index]
        has_val = bool(changed_combo.currentData())

        # When the user changes a combo interactively, reset all later combos.
        if not self._restoring:
            for j in range(combo_index + 1, len(self._ordered_opts)):
                _, _, c = self._ordered_opts[j]
                c.setEnabled(False)
                c.blockSignals(True)
                c.setCurrentIndex(0)
                c.blockSignals(False)

        if not has_val or combo_index + 1 >= len(self._ordered_opts):
            return

        preceding = {
            self._ordered_opts[k][0]: self._ordered_opts[k][2].currentData() or ""
            for k in range(combo_index + 1)
        }
        preceding_labels = {
            self._ordered_opts[k][0]: self._ordered_opts[k][2].currentText() or ""
            for k in range(combo_index + 1)
        }
        next_opt, next_all_vals, next_combo = self._ordered_opts[combo_index + 1]
        next_all_pairs = self._raw_value_pairs.get(next_opt, [])

        valid_vals = set(self._module.get_valid_option_values(
            self._printer_combo.currentData() or "",
            preceding, preceding_labels, next_opt, next_all_vals, next_all_pairs,
        ))

        next_combo.blockSignals(True)
        next_combo.clear()
        next_combo.addItem("(not set)", "")
        for display, raw_val in self._raw_value_pairs.get(next_opt, []):
            if raw_val in valid_vals:
                next_combo.addItem(display, raw_val)
        next_combo.blockSignals(False)
        next_combo.setEnabled(True)

    def _on_load_ti2(self) -> None:
        from ui.ti2_loader import resolve_ti2
        path = open_file_dialog(
            self, "Select .ti2 file to load its chart", "ArgyllCMS target files (*.ti2)",
            extra_path=self._settings.get("custom_output_path", ""),
        )
        if not path:
            return
        result = resolve_ti2(self, Path(path), self._settings)
        if result is None:
            return
        ti2_path, tiffs = result
        self.ti2_loaded.emit(ti2_path)
        if tiffs:
            self.load_tiffs(tiffs)
        else:
            self._status_lbl.setText("No TIFF files found matching the selected .ti2 file.")

    def _on_print_current(self) -> None:
        if not self._preview._pages:
            return
        path, frame = self._preview._pages[self._preview._current]
        self._send_page(path, frame)

    def _on_print_all(self) -> None:
        if not self._preview._pages:
            return
        for path, frame in self._preview._pages:
            self._send_page(path, frame)

    def _send_page(self, tiff_path: Path, frame: int = 0) -> None:
        printer = self._printer_combo.currentData() or ""
        if not printer:
            QMessageBox.warning(self, "No Printer", "Please select a printer before printing.")
            return

        if not self._printer.is_printer_reachable(printer):
            QMessageBox.critical(
                self, "Printer Offline",
                f"The printer \"{printer}\" appears to be offline or unreachable.\n"
                "Please check that it is powered on and connected.",
            )
            return

        stuck = self._module.get_stuck_jobs(printer)
        if stuck:
            n = len(stuck)
            dlg = QMessageBox(self)
            dlg.setWindowTitle("Stuck Print Jobs Detected")
            dlg.setIcon(QMessageBox.Icon.Warning)
            dlg.setText(
                f"There {'is' if n == 1 else 'are'} {n} stuck print "
                f"job{'s' if n != 1 else ''} in the queue for \"{printer}\".\n\n"
                "Stuck jobs can block new print jobs from being processed.\n"
                "Clear them before printing?"
            )
            clear_btn  = dlg.addButton("Clear & Print",  QMessageBox.ButtonRole.AcceptRole)
            dlg.addButton("Print Anyway", QMessageBox.ButtonRole.DestructiveRole)
            cancel_btn = dlg.addButton(QMessageBox.StandardButton.Cancel)
            dlg.setDefaultButton(clear_btn)
            dlg.exec()
            clicked = dlg.clickedButton()
            if clicked is cancel_btn:
                return
            if clicked is clear_btn:
                cleared = self._module.cancel_all_jobs(printer)
                log.info("Cleared %d stuck job(s) before printing", cleared)

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
                self, "TIFF Error",
                f"Cannot read TIFF file:\n{tiff_path.name}\n\n{exc}",
            )
            return

        selected_opts = {k: (c.currentData() or "") for k, c in self._option_combos.items()}
        config = self._module.build_config(printer=printer, options=selected_opts)
        self._status_lbl.setText(f"Sending {tiff_path.name} (page {frame + 1}) to {printer}…")

        def _cleanup_and_finish(code: int) -> None:
            if tmp_path and tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
            self._on_print_done(code)

        self._printer.print_job(print_path, config, on_finish=_cleanup_and_finish)

    def _on_print_done(self, code: int) -> None:
        if code == 0:
            self._status_lbl.setText("Print job submitted successfully.")
        else:
            self._status_lbl.setText(f"Print failed (lp exit code {code}).")
            QMessageBox.critical(
                self, "Print Error",
                f"CUPS rejected the print job (exit code {code}).\n"
                "Check that the printer is online and the selected options are valid.",
            )

    def _on_clear_queue(self) -> None:
        printer = self._printer_combo.currentData() or ""
        if not printer:
            QMessageBox.warning(self, "No Printer", "Select a printer first.")
            return
        count = self._module.cancel_all_jobs(printer)
        if count:
            self._status_lbl.setText(
                f"Cleared {count} job{'s' if count != 1 else ''} from the queue."
            )
        else:
            self._status_lbl.setText("No jobs in the queue to clear.")

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
        self._status_lbl.setText("Print settings saved as defaults.")

    def _restore_defaults(self) -> None:
        pass
