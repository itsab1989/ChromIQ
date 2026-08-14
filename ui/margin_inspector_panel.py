"""The "Measured from Preview" margin inspector panel (Create Chart tab).

Shows the realised page margins (Left/Right/Top/Bottom) and estimated reading-
direction patch size of the generated chart preview, in mm and inches, plus a
large pass/fail status line and the dotted-guide-line toggle. Pure display +
one signal; all measurement/threshold logic lives in
:mod:`workflow.margin_inspector` and the owning tab.
"""
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from core.i18n import tr
from ui.tooltip_button import TooltipButton
from ui.widgets import NoScrollDoubleSpinBox
from workflow.margin_inspector import MarginReport, Violation

_MM_PER_INCH = 25.4
_EDGES = (("L", "Left"), ("R", "Right"), ("T", "Top"), ("B", "Bottom"))


class MarginInspectorPanel(QGroupBox):
    """Read-only margin readout + violation status + guide-line checkbox."""

    guides_toggled = pyqtSignal(bool)
    measured_guides_toggled = pyqtSignal(bool)
    coords_toggled = pyqtSignal(bool)
    #: (on, distance from edge mm, marker length mm) — #152
    helper_markers_changed = pyqtSignal(bool, float, float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(tr("Measured from Preview"), parent)
        self._mode = "dark"
        self._value_labels: dict[str, tuple[QLabel, QLabel]] = {}
        self._build_ui()
        self.show_placeholder()

    @staticmethod
    def _helper_marker_help() -> str:
        """Friendly, extensive help for the marker controls (#152)."""
        return tr(
            "Short dashes printed along all four edges of the sheet, to lay a "
            "ruler against while you measure.\n\n"
            "The dashes along the top and bottom line up with the strips going "
            "across the page — the start and the middle of every strip, and the "
            "end of the last one. The dashes down the left and right line up "
            "with the patches going down the page in the same way. The rest of "
            "each edge is filled with dashes at that same spacing, right out to "
            "the corners, so there is always one near wherever you put the "
            "ruler.\n\n"
            "“Distance from page edge” is how far in from the paper's edge the "
            "dashes sit, and “Marker length” is how long each dash is, pointing "
            "inwards. With 1 mm and 3 mm on an A4 sheet, the dashes on the left "
            "run from 1 mm to 4 mm across, and those on the right from 206 mm "
            "to 209 mm.\n\n"
            "These dashes are part of the printed chart, so they appear on "
            "paper as well as on screen. They are drawn last, which means they "
            "can cross the sheet text, the notes band or the clip border if "
            "those reach the same place. That is expected: if a dash lands "
            "somewhere awkward, move it with “Distance from page edge”, or give "
            "the text more room with its own distance setting.\n\n"
            "A ColorMunki chart offsets every second strip down the page. The "
            "dashes follow the first strip, and because the offset is half a "
            "patch they line up with the shifted strips as well.\n\n"
            "Not available for a SpectroScan chart with six-sided patches: a "
            "honeycomb has no straight rows for a ruler to follow.\n\n"
            "Default: off, 1.0 mm from the edge, 3.0 mm long")

    def _emit_helper_markers(self, *_a) -> None:
        self.helper_markers_changed.emit(
            self._helper_check.isChecked(),
            float(self._helper_edge.value()),
            float(self._helper_len.value()))

    def set_helper_markers(self, on: bool, edge_mm: float, len_mm: float) -> None:
        """Show what the chart on screen was actually made with, without
        bouncing a change straight back out again."""
        for w, v in ((self._helper_check, bool(on)),
                     (self._helper_edge, float(edge_mm)),
                     (self._helper_len, float(len_mm))):
            w.blockSignals(True)
            w.setChecked(v) if isinstance(w, QCheckBox) else w.setValue(v)
            w.blockSignals(False)

    def helper_markers(self) -> "tuple[bool, float, float]":
        return (self._helper_check.isChecked(),
                float(self._helper_edge.value()),
                float(self._helper_len.value()))

    def set_helper_markers_supported(self, supported: bool,
                                     reason: str = "") -> None:
        """Grey the markers out when the chart cannot carry them (#152).

        Knut asked for the reason to be visible in both places a user might
        look — the hover tooltip and the ⓘ — rather than the box simply going
        dead with no explanation.
        """
        for w in (self._helper_check, self._helper_edge, self._helper_len):
            w.setEnabled(bool(supported))
        why = reason or tr(
            "This chart's patches are six-sided, so it has no straight rows or "
            "columns for a ruler to line up with. Helper markers are available "
            "on charts with rectangular patches.")
        tip = "" if supported else why
        for w in (self._helper_check, self._helper_edge, self._helper_len):
            w.setToolTip(tip)
        self._helper_tip.set_content(
            tr("Helper markers"),
            self._helper_marker_help() if supported
            else why + "\n\n" + self._helper_marker_help())

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        v = QVBoxLayout(self)
        v.setSpacing(6)
        v.setContentsMargins(12, 8, 12, 10)

        self._placeholder = QLabel(
            tr("Generate a preview to measure its margins."), self)
        self._placeholder.setWordWrap(True)
        self._placeholder.setStyleSheet("color: #909090; font-size: 11px;")
        v.addWidget(self._placeholder)

        self._table = QWidget(self)
        grid = QGridLayout(self._table)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(3)
        hdr_mm = QLabel(tr("mm"), self)
        hdr_in = QLabel(tr("inch"), self)
        hdr_thr = QLabel(tr("min"), self)
        for w in (hdr_mm, hdr_in, hdr_thr):
            w.setAlignment(Qt.AlignmentFlag.AlignRight)
            w.setStyleSheet("color: #909090; font-size: 10px;")
        grid.addWidget(hdr_mm, 0, 1)
        grid.addWidget(hdr_in, 0, 2)
        grid.addWidget(hdr_thr, 0, 3)
        self._thr_labels: dict[str, QLabel] = {}
        row = 1
        for key, label in _EDGES:
            name = QLabel(tr(label), self)
            mm = QLabel("—", self)
            inch = QLabel("—", self)
            thr = QLabel("—", self)
            for lbl in (mm, inch, thr):
                lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            mm.setStyleSheet("font-family: Menlo; font-size: 11px;")
            inch.setStyleSheet("font-family: Menlo; font-size: 11px;")
            thr.setStyleSheet("font-family: Menlo; font-size: 11px; color: #909090;")
            grid.addWidget(name, row, 0)
            grid.addWidget(mm, row, 1)
            grid.addWidget(inch, row, 2)
            grid.addWidget(thr, row, 3)
            self._value_labels[key] = (mm, inch)
            self._thr_labels[key] = thr
            row += 1

        strip_name = QLabel(tr("Patch width (in strip reading direction)"), self)
        self._strip_mm = QLabel("—", self)
        self._strip_in = QLabel("—", self)
        self._strip_mm.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._strip_in.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._strip_mm.setStyleSheet("font-family: Menlo; font-size: 11px;")
        self._strip_in.setStyleSheet("font-family: Menlo; font-size: 11px;")
        grid.addWidget(strip_name, row, 0)
        grid.addWidget(self._strip_mm, row, 1)
        grid.addWidget(self._strip_in, row, 2)
        row += 1

        len_name = QLabel(tr("Strip length"), self)
        self._striplen_mm = QLabel("—", self)
        self._striplen_in = QLabel("—", self)
        self._striplen_mm.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._striplen_in.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._striplen_mm.setStyleSheet("font-family: Menlo; font-size: 11px;")
        self._striplen_in.setStyleSheet("font-family: Menlo; font-size: 11px;")
        grid.addWidget(len_name, row, 0)
        grid.addWidget(self._striplen_mm, row, 1)
        grid.addWidget(self._striplen_in, row, 2)
        grid.setColumnStretch(0, 1)
        v.addWidget(self._table)

        # Large pass/fail status, one or more lines.
        self._status = QLabel("", self)
        self._status.setWordWrap(True)
        self._status.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        v.addWidget(self._status)

        # Bottom row: the guide-lines checkbox, with the ⓘ help button tucked in
        # the corner so it doesn't take space at the top (#86).
        from PyQt6.QtWidgets import QHBoxLayout
        from ui.tooltip_button import TooltipButton
        bottom = QHBoxLayout()
        checks = QVBoxLayout()
        checks.setSpacing(2)
        self._guide_check = QCheckBox(
            tr("Show instrument-margin guide lines on preview (dotted lines)"), self)
        self._guide_check.toggled.connect(self.guides_toggled.emit)
        checks.addWidget(self._guide_check)
        self._measured_check = QCheckBox(
            tr("Show margin guide lines on preview (long dotted lines)"), self)
        self._measured_check.toggled.connect(self.measured_guides_toggled.emit)
        checks.addWidget(self._measured_check)
        self._coord_check = QCheckBox(
            tr("Show measurement coordinates on pointer"), self)
        self._coord_check.toggled.connect(self.coords_toggled.emit)
        checks.addWidget(self._coord_check)

        # Ruler helper markers (#152, Knut). Under and left-aligned with the
        # coordinates box, with the two distances on the same row to its right,
        # exactly as he laid it out.
        _hm = QHBoxLayout()
        _hm.setContentsMargins(0, 0, 0, 0)
        _hm.setSpacing(8)
        self._helper_check = QCheckBox(
            tr("Show helper markers (visible on print)"), self)
        _hm.addWidget(self._helper_check)
        _hm.addSpacing(10)
        _hm.addWidget(QLabel(tr("Distance from page edge:"), self))
        self._helper_edge = NoScrollDoubleSpinBox(self)
        self._helper_edge.setRange(0.0, 50.0)
        self._helper_edge.setDecimals(1)
        self._helper_edge.setSingleStep(0.5)
        self._helper_edge.setSuffix(tr(" mm"))
        self._helper_edge.setValue(1.0)
        _hm.addWidget(self._helper_edge)
        _hm.addWidget(QLabel(tr("Marker length:"), self))
        self._helper_len = NoScrollDoubleSpinBox(self)
        self._helper_len.setRange(0.5, 50.0)
        self._helper_len.setDecimals(1)
        self._helper_len.setSingleStep(0.5)
        self._helper_len.setSuffix(tr(" mm"))
        self._helper_len.setValue(3.0)
        _hm.addWidget(self._helper_len)
        self._helper_tip = TooltipButton(
            tr("Helper markers"), self._helper_marker_help(), self)
        _hm.addWidget(self._helper_tip)
        _hm.addStretch()
        checks.addLayout(_hm)
        for _w in (self._helper_check,):
            _w.toggled.connect(self._emit_helper_markers)
        for _w in (self._helper_edge, self._helper_len):
            _w.valueChanged.connect(self._emit_helper_markers)
        bottom.addLayout(checks)
        bottom.addStretch()
        bottom.addWidget(TooltipButton(
            tr("About the margin inspector"),
            tr("This little panel checks that the chart you just made will be "
               "easy to measure.\n\n"
               "Many spectrophotometers (like the i1Pro or ColorMunki) are slid "
               "along the printed chart by hand, often in a ruler or holder "
               "(sometimes called a jig or rig). For that to work, the coloured "
               "patches need a bit of blank white paper around them — if a patch "
               "sits too close to the edge of the page, the instrument can run "
               "off the paper or bump the ruler, and the reading fails. This "
               "panel helps you catch that before you print.\n\n"
               "What the numbers mean:\n"
               "• Left, Right, Top, Bottom — how much white space there is "
               "between each edge of the paper and the patches, shown in both "
               "millimetres and inches.\n"
               "• Patch width — how wide one patch is across a strip.\n"
               "• Strip length — how long each strip of patches is (handy because "
               "some jigs have a maximum, e.g. 240 mm for the i1Pro).\n\n"
               "The 'min' column is the smallest each margin should be for your "
               "ruler or jig. If a margin is below its minimum, that row turns "
               "red and a short warning appears; when everything is fine you'll "
               "see a friendly green 'Margins: OK'.\n\n"
               "You decide those minimums yourself: open Preferences → Instrument "
               "Margins and set them for each instrument and paper size (the "
               "starting values are sensible defaults you can adjust to your own "
               "ruler). They’re only a helpful warning — you can always go ahead "
               "and print anyway.\n\n"
               "Seeing it on the preview: tick 'Show instrument-margin guide "
               "lines on preview' to draw each minimum as a dotted line right on "
               "the chart — black where the margin is fine, red on any edge "
               "that's too tight. A patch area that stays inside all four dotted "
               "lines is good to go.\n\n"
               "You'll also see a thin solid rectangle marking the actual edge "
               "of the paper (the page is drawn slightly inside the preview's "
               "white border, so this line shows exactly where the sheet ends — "
               "a 0 mm margin would sit right on it).\n\n"
               "The second checkbox, 'Show margin guide lines on preview (long "
               "dotted lines)', is a different helper: instead of the thresholds, "
               "it draws a long purple/blue dotted line at each of the four "
               "measured margins — right where the patch area meets the white "
               "paper. It's an easy way to double-check that the numbers above "
               "really sit where the patches end. You can turn both sets of "
               "lines on together if you like.\n\n"
               "The third checkbox, 'Show measurement coordinates on pointer', "
               "turns your mouse into a ruler. Tick it and, wherever you move "
               "the pointer over the chart, a thin cross-hair marks the exact "
               "spot and its position is shown right next to it — measured from "
               "the top-left corner of the paper itself (not the preview's "
               "outer edge). The top line is in millimetres (one decimal), the "
               "line below it in inches (three decimals). It's the easiest way "
               "to check a real distance on screen: hover over the edge of a "
               "patch, or a margin, and read off exactly where it sits."),
            self))
        v.addLayout(bottom)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_appearance(self, mode: str) -> None:
        self._mode = "light" if mode == "light" else "dark"

    def guides_enabled(self) -> bool:
        return self._guide_check.isChecked()

    def set_guides_checked(self, on: bool) -> None:
        self._guide_check.setChecked(bool(on))

    def measured_guides_enabled(self) -> bool:
        return self._measured_check.isChecked()

    def set_measured_guides_checked(self, on: bool) -> None:
        self._measured_check.setChecked(bool(on))

    def coords_enabled(self) -> bool:
        return self._coord_check.isChecked()

    def set_coords_checked(self, on: bool) -> None:
        self._coord_check.setChecked(bool(on))

    def show_placeholder(self) -> None:
        """No preview yet (or measurement failed) — hide the numbers."""
        self._placeholder.setVisible(True)
        self._table.setVisible(False)
        self._status.setVisible(False)

    def update_report(
        self,
        report: Optional[MarginReport],
        violations: list[Violation],
        *,
        thresholds_defined: bool,
        notify: bool,
        thresholds: dict | None = None,
        text_warnings: "list[str] | None" = None,
    ) -> None:
        """Show ``report``'s margins and the pass/fail status.

        ``thresholds_defined`` is False when no thresholds exist for the chart's
        combo (status is then a neutral note, not green/red). ``notify`` mirrors
        the Settings flag — when False the status line is suppressed entirely
        (margins still shown). ``text_warnings`` are extra messages (e.g. a margin
        too small for its label/text band) shown with the margin status (#93).
        """
        if report is None:
            self.show_placeholder()
            return
        self._placeholder.setVisible(False)
        self._table.setVisible(True)

        vals = {"L": report.left_mm, "R": report.right_mm,
                "T": report.top_mm, "B": report.bottom_mm}
        violated_edges = {v.edge for v in violations}
        edge_name = {"L": "Left", "R": "Right", "T": "Top", "B": "Bottom"}
        for key, (mm_lbl, in_lbl) in self._value_labels.items():
            mm = vals[key]
            mm_lbl.setText(f"{mm:.1f}")
            in_lbl.setText(f"{mm / _MM_PER_INCH:.3f}")
            bad = edge_name[key] in violated_edges
            colour = "#e0564b" if bad else ("#1c1b18" if self._mode == "light" else "#d8d8d8")
            weight = "600" if bad else "400"
            for lbl in (mm_lbl, in_lbl):
                lbl.setStyleSheet(
                    f"font-family: Menlo; font-size: 11px; color: {colour}; font-weight: {weight};")
            # Threshold (minimum) for this edge — the "Margin Thresholds Set"
            # readout, shown beside the measured value for easy comparison (#86).
            self._thresholds_are_the_charts_own = bool(
                (thresholds or {}).get("desc", "").endswith("laid out to"))
            raw = (thresholds or {}).get(key)
            try:
                self._thr_labels[key].setText("—" if raw in (None, "") else f"{float(raw):.1f}")
            except (TypeError, ValueError):
                self._thr_labels[key].setText("—")

        if report.strip_width_mm is not None:
            self._strip_mm.setText(f"{report.strip_width_mm:.1f}")
            self._strip_in.setText(f"{report.strip_width_mm / _MM_PER_INCH:.3f}")
        else:
            self._strip_mm.setText("—")
            self._strip_in.setText("—")

        if report.strip_length_mm is not None:
            self._striplen_mm.setText(f"{report.strip_length_mm:.1f}")
            self._striplen_in.setText(f"{report.strip_length_mm / _MM_PER_INCH:.3f}")
        else:
            self._striplen_mm.setText("—")
            self._striplen_in.setText("—")

        self._update_status(violations, thresholds_defined=thresholds_defined,
                            notify=notify, text_warnings=text_warnings)

    # ------------------------------------------------------------------
    def _update_status(
        self, violations: list[Violation], *,
        thresholds_defined: bool, notify: bool,
        text_warnings: "list[str] | None" = None,
    ) -> None:
        if not notify:
            self._status.setVisible(False)
            return
        self._status.setVisible(True)
        text_warnings = list(text_warnings or [])
        # Name WHICH minimum was missed (Knut, #130 2026-07-27): the
        # instrument's, or the margins this chart was laid out to. Saying only
        # "the minimum" left him reading instrument figures into a chart that
        # had declined them.
        own = getattr(self, "_thresholds_are_the_charts_own", False)
        pattern = (tr("⚠ {edge} margin {measured:.1f} mm is below the "
                      "{threshold:.0f} mm minimum set for this chart")
                   if own else
                   tr("⚠ {edge} margin {measured:.1f} mm is below the "
                      "{threshold:.0f} mm instrument minimum"))
        margin_lines = [
            pattern.format(edge=tr(v.edge), measured=v.measured_mm,
                           threshold=v.threshold_mm)
            for v in violations
        ] if thresholds_defined else []
        lines = margin_lines + text_warnings
        if lines:                                       # something to warn about
            self._status.setText("\n".join(lines))
            self._status.setStyleSheet(
                "color: #e0564b; font-size: 14px; font-weight: 700;")
            return
        if not thresholds_defined:
            self._status.setText(tr(
                "No instrument margins set for this instrument and paper size."))
            self._status.setStyleSheet("color: #909090; font-size: 11px;")
            return
        self._status.setText(tr("Margins: OK"))
        self._status.setStyleSheet(
            "color: #4fc27a; font-size: 15px; font-weight: 700;")
