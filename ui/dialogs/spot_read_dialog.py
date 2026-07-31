"""Single-patch (spot) reading tool — Tools ▸ "Read single patches".

Drives ArgyllCMS ``spotread`` via ``SpotReadManager`` to measure individual
colour patches off any material (or a display / light source), shows each
reading's L*a*b* with an on-screen sRGB swatch, and saves the set to a CSV plus
an Argyll ``.ti3``.

This is a standalone ``QDialog`` (its interactive Start/Take-reading/table shape
doesn't fit the Run/Close+log ``_ToolDialogBase``), but it reuses that module's
styling helpers and the calibration-popup pattern from the Measure tab so it
looks and behaves like the rest of the app.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.i18n import tr
from ui.dialogs.tools_dialogs import _indicator_color, neutral_controls_qss
from ui.styles import SPEC_GREEN
from ui.tab_header import dialog_masthead
from ui.widgets import NoScrollComboBox, tint_dialog_primary
from workflow.spot_read_io import SpotReading, average_readings, write_csv, write_ti3
from workflow.spot_read_manager import SpotReadManager, SpotReadParams

if TYPE_CHECKING:
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings

_ACCENT = "#56d6a5"   # share the Measure tab's accent — this is measurement work

_HELP = tr(
    "Read individual colour patches with your measuring instrument, off any "
    "material — printed sheets, fabric, paint chips, or even a display.\n\n"
    "Click Start session, calibrate the instrument if prompted, then place it "
    "on a colour and click Take reading. Each reading is added to the table with "
    "its L*a*b* value and an approximate on-screen colour. Save writes a CSV (for "
    "a spreadsheet) and an Argyll .ti3 (for other tools)."
)


class SpotReadDialog(QDialog):
    _MODE_KEYS = ("reflective", "emissive", "ambient")

    def __init__(
        self,
        runner: "ArgyllRunner",
        settings: "AppSettings",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._manager = SpotReadManager(runner, self)
        self._readings: list[SpotReading] = []

        self.setWindowTitle(tr("Read single patches"))
        self.setMinimumWidth(960)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        # Tab-style masthead (eyebrow + serif title + ⓘ) over a full-width
        # spectrum stripe, matching the chart-design windows. The outer layout
        # spans full width so the stripe bleeds to the edges; the content below
        # re-adds the side inset.
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        head, _header, stripe = dialog_masthead(
            self, tr("INSTRUMENT · SPOT READ"), tr("Read single patches"),
            tooltip_title=tr("Read single patches"), tooltip_body=_HELP,
            accent=SPEC_GREEN)
        root.addLayout(head)
        root.addWidget(stripe)

        outer = QVBoxLayout()
        outer.setContentsMargins(22, 14, 22, 16)
        outer.setSpacing(12)
        root.addLayout(outer)

        body = QLabel(
            tr("Measure single colours off any material and save their L*a*b* values."),
            self,
        )
        body.setWordWrap(True)
        outer.addWidget(body)

        sep = QFrame(self)
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        outer.addWidget(sep)

        # --- Session controls (disabled once a session runs) ---------------
        # The instrument number (spotread -c) is left at 1: almost everyone has a
        # single measuring device connected, so we don't ask. Multi-instrument
        # users can still use the strip-based Measure tab.
        controls = QHBoxLayout()
        controls.setSpacing(10)

        controls.addWidget(QLabel(tr("Mode"), self))
        self._mode = NoScrollComboBox(self)
        self._mode.addItem(tr("Reflective (material)"))
        self._mode.addItem(tr("Emissive (display)"))
        self._mode.addItem(tr("Ambient (light)"))
        controls.addWidget(self._mode)

        self._skip_cal = QCheckBox(tr("Skip initial calibration"), self)
        controls.addWidget(self._skip_cal)
        # Knut, #130 2026-07-31: *"add an help icon to the right of the checkbox
        # text and in that help text explain how argyllcms handles this request,
        # and that some instruments (like the ColorMunki / i1Studio) will still
        # often require a calibration the first time, but skip calibration if
        # you stop your measurement session and start another shortly after."*
        # He reported the box as broken; it is not, and the honest fix is to say
        # what it can and cannot promise.
        from ui.tooltip_button import TooltipButton
        controls.addWidget(TooltipButton(
            tr("About skipping the initial calibration"),
            tr("Ticking this asks ArgyllCMS to start measuring without "
               "calibrating first. ChromIQ passes it on as the -N option.\n\n"
               "It is a request, not a command. ArgyllCMS skips the calibration "
               "only where the instrument allows it, and several do not: a "
               "ColorMunki or i1Studio will usually still ask the first time you "
               "use it after plugging it in, however this box is set. That is "
               "the instrument protecting the accuracy of your readings, and "
               "nothing ChromIQ can overrule.\n\n"
               "Where it does help is a run of short sessions. Once the "
               "instrument has calibrated, it stays calibrated for a while — so "
               "if you stop a session and start another one shortly after, "
               "ticking this lets you go straight to reading instead of "
               "calibrating again.\n\n"
               "If you are unsure, leave it unticked. Calibrating takes a few "
               "seconds and is never the wrong thing to do."),
            self))
        controls.addStretch(1)
        outer.addLayout(controls)

        self._status = QLabel(tr("Idle — click Start session to begin."), self)
        self._status.setWordWrap(True)
        self._status.setStyleSheet("color: #909090;")
        outer.addWidget(self._status)

        # --- Results table -------------------------------------------------
        self._table = QTableWidget(0, 8, self)
        self._table.setHorizontalHeaderLabels([
            tr("Name"), tr("L*"), tr("a*"), tr("b*"),
            tr("X"), tr("Y"), tr("Z"), tr("Colour"),
        ])
        self._table.verticalHeader().setVisible(False)
        # Taller rows so each cell — especially the Colour swatch — has more
        # breathing room.
        self._table.verticalHeader().setDefaultSectionSize(34)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        hdr = self._table.horizontalHeader()
        # Name keeps the lion's share (stretches to fill), but the value /
        # Colour columns get comfortable fixed widths — wider than auto-sizing to
        # their short contents — so they're not cramped while Name stays the
        # biggest column by far.
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for c in range(1, 7):                       # L* a* b* X Y Z — kept small
            hdr.setSectionResizeMode(c, QHeaderView.ResizeMode.Interactive)
            self._table.setColumnWidth(c, 50)
        hdr.setSectionResizeMode(7, QHeaderView.ResizeMode.Interactive)
        self._table.setColumnWidth(7, 128)          # Colour swatch (bigger)
        self._table.itemChanged.connect(self._on_item_changed)
        self._table.itemSelectionChanged.connect(self._update_average_btn)
        outer.addWidget(self._table, 1)

        # --- Bottom buttons ------------------------------------------------
        # Session controls (Start / Take reading) live on the far left next to
        # Clear; Save / Close sit on the right — one unified action row.
        bottom = QHBoxLayout()
        bottom.setSpacing(10)

        self._start_btn = QPushButton(tr("Start session"), self)
        self._start_btn.setObjectName("primary")
        self._start_btn.clicked.connect(self._on_start_stop)
        bottom.addWidget(self._start_btn)

        self._read_btn = QPushButton(tr("Take reading"), self)
        self._read_btn.setEnabled(False)
        self._read_btn.clicked.connect(self._manager.take_reading)
        bottom.addWidget(self._read_btn)

        self._avg_btn = QPushButton(tr("Average selected"), self)
        self._avg_btn.setEnabled(False)
        self._avg_btn.setToolTip(
            tr("Select two or more readings, then average them into a new entry.")
        )
        self._avg_btn.clicked.connect(self._on_average_selected)
        bottom.addWidget(self._avg_btn)

        self._clear_btn = QPushButton(tr("Clear"), self)
        self._clear_btn.setEnabled(False)
        self._clear_btn.clicked.connect(self._on_clear)
        bottom.addWidget(self._clear_btn)

        bottom.addStretch(1)

        self._save_btn = QPushButton(tr("Save…"), self)
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._on_save)
        bottom.addWidget(self._save_btn)

        close_btn = QPushButton(tr("Close"), self)
        close_btn.clicked.connect(self.reject)
        bottom.addWidget(close_btn)

        outer.addLayout(bottom)

        self.setStyleSheet(neutral_controls_qss(_indicator_color(settings)))
        # Tint the Start button with the Measure tab's green accent — this tool
        # is measurement work and reads as part of that family.
        tint_dialog_primary(self, _ACCENT)

        # --- Manager signals ----------------------------------------------
        m = self._manager
        m.reading_ready.connect(self._on_reading)
        m.ready_to_read.connect(self._on_ready)
        m.calibration_prompt.connect(self._on_calibration_prompt)
        m.calibration_finished.connect(self._on_calibration_finished)
        m.misread.connect(lambda: self._set_status(tr("Misread — reposition and take the reading again.")))
        m.sensor_wrong_position.connect(self._on_sensor_wrong_position)
        m.no_instrument.connect(self._on_no_instrument)
        m.device_busy.connect(self._on_device_busy)
        m.instrument_disconnected.connect(self._on_disconnected)
        m.coms_init_failed.connect(lambda s: self._on_init_failed(s))
        m.inst_init_failed.connect(lambda s: self._on_init_failed(s))
        m.session_ended.connect(self._on_session_ended)

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------
    def _on_start_stop(self) -> None:
        if self._manager.is_running:
            self._manager.quit()
            self._manager.abort()
            return
        params = SpotReadParams(
            mode=self._MODE_KEYS[self._mode.currentIndex()],
            disable_initial_cal=self._skip_cal.isChecked(),
        )
        self._set_session_running(True)
        self._set_status(tr("Starting instrument…"))
        self._manager.start(params, lambda _line: None)

    def _set_session_running(self, running: bool) -> None:
        self._mode.setEnabled(not running)
        self._skip_cal.setEnabled(not running)
        self._start_btn.setText(tr("Stop session") if running else tr("Start session"))
        if not running:
            self._read_btn.setEnabled(False)

    def _on_session_ended(self, code: int) -> None:
        self._set_session_running(False)
        self._set_status(tr("Session ended."))

    def _on_ready(self) -> None:
        self._read_btn.setEnabled(True)
        self._set_status(tr("Ready — place the instrument on a colour and click Take reading."))

    # ------------------------------------------------------------------
    # Readings
    # ------------------------------------------------------------------
    def _on_reading(self, xyz: tuple, lab: tuple) -> None:
        name = tr("Patch {n}").format(n=len(self._readings) + 1)
        reading = SpotReading(name=name, xyz=tuple(xyz), lab=tuple(lab))
        self._readings.append(reading)
        self._append_row(reading)
        self._save_btn.setEnabled(True)
        self._clear_btn.setEnabled(True)
        self._set_status(
            tr("Read {name}: L* {l:.1f}  a* {a:.1f}  b* {b:.1f}").format(
                name=name, l=lab[0], a=lab[1], b=lab[2])
        )

    def _append_row(self, r: SpotReading) -> None:
        self._table.blockSignals(True)
        row = self._table.rowCount()
        self._table.insertRow(row)

        name_item = QTableWidgetItem(r.name)
        name_item.setFlags(name_item.flags() | Qt.ItemFlag.ItemIsEditable)
        self._table.setItem(row, 0, name_item)

        vals = (*r.lab, *r.xyz)
        for col, v in enumerate(vals, start=1):
            item = QTableWidgetItem(f"{v:.2f}")
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._table.setItem(row, col, item)

        swatch = QTableWidgetItem(r.hex)
        swatch.setFlags(swatch.flags() & ~Qt.ItemFlag.ItemIsEditable)
        swatch.setBackground(QColor(r.hex))
        swatch.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self._table.setItem(row, 7, swatch)

        self._table.blockSignals(False)
        self._table.scrollToBottom()

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if item.column() != 0:
            return
        row = item.row()
        if 0 <= row < len(self._readings):
            self._readings[row].name = item.text()

    def _selected_rows(self) -> list[int]:
        return sorted({idx.row() for idx in self._table.selectionModel().selectedRows()})

    def _update_average_btn(self) -> None:
        self._avg_btn.setEnabled(len(self._selected_rows()) >= 2)

    def _on_average_selected(self) -> None:
        rows = self._selected_rows()
        if len(rows) < 2:
            return
        averaged = average_readings([self._readings[r] for r in rows], tr("Average"))
        self._readings.append(averaged)
        self._append_row(averaged)
        self._save_btn.setEnabled(True)
        self._clear_btn.setEnabled(True)
        self._set_status(
            tr("Averaged {n} readings: L* {l:.1f}  a* {a:.1f}  b* {b:.1f}").format(
                n=len(rows), l=averaged.lab[0], a=averaged.lab[1], b=averaged.lab[2])
        )

    def _on_clear(self) -> None:
        self._readings.clear()
        self._table.setRowCount(0)
        self._save_btn.setEnabled(False)
        self._clear_btn.setEnabled(False)
        self._avg_btn.setEnabled(False)

    def _on_save(self) -> None:
        if not self._readings:
            return
        from ui.widgets import save_file_dialog
        chosen = save_file_dialog(
            self, tr("Save spot readings"), tr("Spot readings (*.csv)"),
            start_path=str(Path.home() / "spot-readings" / "spot-readings.csv"))
        if not chosen:
            return
        base = Path(chosen).with_suffix("")
        try:
            csv_path = write_csv(base.with_suffix(".csv"), self._readings)
            ti3_path = write_ti3(base.with_suffix(".ti3"), self._readings)
        except OSError as exc:
            QMessageBox.warning(self, tr("Save failed"), str(exc))
            return
        QMessageBox.information(
            self, tr("Saved"),
            tr("Readings saved to:\n{csv}\n{ti3}").format(
                csv=csv_path.name, ti3=ti3_path.name),
        )

    # ------------------------------------------------------------------
    # Calibration + error pop-ups
    # ------------------------------------------------------------------
    def _instrument_family(self) -> "str | None":
        """Which instrument's wording to use, or None for the generic text.

        Knut, #130 2026-07-31: *"one window for each instrument, wired to the
        detection of each instrument type during connection, so that the window
        shows correct text for each instrument."*

        spotread does not announce its model in anything ChromIQ parses, and
        inventing a pattern for output I have not seen is how four wrong theories
        about Save Partial happened. What IS known is the instrument the user has
        chosen in ChromIQ — the same value the Measure tab compares a chart
        against — and his own log confirms spotread is launched with the device
        ChromIQ picked. So the wording follows that, and falls back to the
        generic text whenever it is unset or unrecognised, which is exactly what
        the SpectroScan and any unknown instrument should get anyway.
        """
        try:
            from ui.ti2_loader import instrument_family
            return instrument_family(
                str(self._settings.get("chart_instrument", "") or ""))
        except Exception:      # noqa: BLE001 — wording must never break a read
            return None

    def _on_sensor_wrong_position(self) -> None:
        """Say — properly — that the instrument is not in its reading position.

        Knut, #130 2026-07-31 (item 5): with the dial still on calibration,
        *"the instrument button and Take Reading button registers ('Ready...'
        text blinks), but nothing happens"*, and he asked for what patch-by-patch
        does: *"a window saying 'The patch could not be read: Sensor should be
        in surface position', then Retry button."*

        This used to set a line of status text only, which is easy to miss while
        you are looking at the instrument rather than the screen.
        """
        self._set_status(tr("Instrument is in the wrong position."))
        if getattr(self, "_sensor_pos_open", False):
            return          # one window, however many times it is reported
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("Instrument in the Wrong Position"))
        dlg.setMinimumWidth(500)
        lay = QVBoxLayout(dlg)
        lay.setSpacing(16)
        lay.setContentsMargins(24, 20, 24, 20)
        msg = QLabel(
            tr("<b>That reading could not be taken — the instrument is not in "
               "its measuring position.</b><br><br>"
               "On most instruments this means the dial or head is still set to "
               "calibration. Turn it back to the measuring position, place the "
               "instrument on the colour you want to read, and try again."),
            dlg,
        )
        msg.setWordWrap(True)
        msg.setTextFormat(Qt.TextFormat.RichText)
        lay.addWidget(msg)
        box = QDialogButtonBox(dlg)
        again = box.addButton(tr("Try again"), QDialogButtonBox.ButtonRole.AcceptRole)
        again.setObjectName("primary")
        box.accepted.connect(dlg.accept)
        lay.addWidget(box)
        tint_dialog_primary(dlg, _ACCENT)
        self._sensor_pos_open = True
        try:
            dlg.exec()
        finally:
            self._sensor_pos_open = False

    def _on_calibration_finished(self) -> None:
        """Say that the calibration is done — and what to do with the device now.

        Knut, #130 2026-07-30: *"When I complete the calibration, there is no
        infomation window that calibration is done and to turn the unit back to
        measure mode."* Patch-by-patch mode has said this for a while; single
        patches went straight back to a ready button with the instrument still
        sitting on its calibration tile.

        Deliberately shorter than the Measure tab's version: he also said
        *"parts of the calibration complete window is not relevant for read
        single patches tool"*, and the parts about strips and charts are exactly
        those, so they are left out.
        """
        # Knut, #130 2026-07-31 (item 4): *"Before pressing Start Calibration in
        # the Calibration Complete window, I press the instrument button. That
        # results in another Calibration Complete window to appear on top of the
        # previous, every time I click the button."* Each press makes spotread
        # print its ready prompt again, and each one opened another window.
        if getattr(self, "_cal_done_open", False):
            return
        self._read_btn.setEnabled(True)
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("Calibration Complete"))
        from ui.ti2_loader import spot_measurement_instructions_html
        dlg.setMinimumWidth(500)
        lay = QVBoxLayout(dlg)
        lay.setSpacing(16)
        lay.setContentsMargins(24, 20, 24, 20)
        msg = QLabel(
            # Knut, #130 2026-07-31, on the first version of this text: *"The
            # text mentions 'Take it off the calibration tile', which does not
            # exist for this instrument … the button in the Read Single Patches
            # window is called Take Reading."* Both were mine and both were
            # wrong: a ColorMunki is turned by a dial, and no button here has
            # ever been called "Read patch". Named after what is actually on
            # screen, and worded for any instrument until the per-instrument
            # texts he asked for are wired to device detection.
            tr("<b>Your instrument is calibrated and ready.</b><br><br>")
            + spot_measurement_instructions_html(self._instrument_family())
            + tr("<br><br>Click <b>Take reading</b> for each measurement. The "
                 "instrument stays calibrated for the whole session, so you "
                 "will not be asked again unless it needs it."),
            dlg,
        )
        msg.setWordWrap(True)
        msg.setTextFormat(Qt.TextFormat.RichText)
        lay.addWidget(msg)
        box = QDialogButtonBox(dlg)
        ok = box.addButton(tr("Start Reading"), QDialogButtonBox.ButtonRole.AcceptRole)
        ok.setObjectName("primary")
        box.accepted.connect(dlg.accept)
        lay.addWidget(box)
        tint_dialog_primary(dlg, _ACCENT)
        self._cal_done_open = True
        try:
            dlg.exec()
        finally:
            self._cal_done_open = False

    def _on_calibration_prompt(self) -> None:
        # Same wording as the Measure tab's calibration pop-up — generic but
        # clear — with the strip-specific tail swapped for a spot-read one.
        self._read_btn.setEnabled(False)
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("Calibration Required"))
        dlg.setMinimumWidth(500)
        lay = QVBoxLayout(dlg)
        lay.setSpacing(16)
        lay.setContentsMargins(24, 20, 24, 20)

        # The same per-instrument instructions patch-by-patch has always shown
        # (Knut asked for exactly that); generic wording when the instrument is
        # unknown.
        from ui.ti2_loader import calibration_instructions_html
        msg = QLabel(calibration_instructions_html(self._instrument_family()), dlg)
        msg.setWordWrap(True)
        msg.setTextFormat(Qt.TextFormat.RichText)
        lay.addWidget(msg)

        box = QDialogButtonBox(dlg)
        ok = box.addButton(tr("Start Calibration"), QDialogButtonBox.ButtonRole.AcceptRole)
        ok.setObjectName("primary")
        # Knut, #130 2026-07-31 (item 2): *"the Calibration Required window is
        # lacking a Cancel Measurement button, like used in patch-by-patch mode
        # … There should be a chance to change my mind and exit the measurement
        # session."* Without it the only way out was the Stop session button
        # behind the window.
        cancel = box.addButton(tr("Cancel session"),
                               QDialogButtonBox.ButtonRole.RejectRole)
        box.accepted.connect(dlg.accept)
        box.rejected.connect(dlg.reject)
        lay.addWidget(box)

        tint_dialog_primary(dlg, _ACCENT)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._manager.send_key("\r")
            self._set_status(tr("Calibrating…"))
        else:
            # Dismissed — exit spotread cleanly.
            self._manager.send_key("\x1b")

    def _on_no_instrument(self) -> None:
        self._set_status(tr("No instrument detected."))
        QMessageBox.warning(
            self, tr("No instrument detected"),
            tr("No measuring instrument was found. Connect it and try again."),
        )

    def _on_device_busy(self) -> None:
        self._set_status(tr("Instrument is in use by another program."))
        QMessageBox.warning(
            self, tr("Instrument busy"),
            tr("The instrument is being used by another program. Close it and try again."),
        )

    def _on_disconnected(self) -> None:
        self._set_status(tr("Instrument disconnected."))

    def _on_init_failed(self, detail: str) -> None:
        self._set_status(tr("Could not start the instrument: {detail}").format(detail=detail))

    # ------------------------------------------------------------------
    def _set_status(self, text: str) -> None:
        self._status.setText(text)

    def reject(self) -> None:  # noqa: D102
        if self._manager.is_running:
            self._manager.quit()
            self._manager.abort()
        super().reject()

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._manager.is_running:
            self._manager.quit()
            self._manager.abort()
        super().closeEvent(event)
