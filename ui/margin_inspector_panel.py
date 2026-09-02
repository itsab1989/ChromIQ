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
from ui.widgets import NoScrollDoubleSpinBox, WrappingCheckBox, set_ink
from workflow.margin_inspector import MarginReport, Violation

# Frame, text margin, the up/down buttons and the theme's padding around a spin
# box's editable text — measured on the real panel with the app's #compact_input
# rule applied (6 px left padding, 20 px for the buttons, plus the frame). Only a
# fallback: the width actually used is the larger of this and Qt's own
# minimumSizeHint.
_SPIN_CHROME_PX = 34

_MM_PER_INCH = 25.4
# SAY WHAT IS BEING MEASURED. These are the distances from the paper edge to
# the FIRST PATCH -- not to the first ink. Two things sit in between and are
# meant to: furniture bands (the row numbers down the left, the strip labels
# across the top) and, when the grid does not divide the width exactly, the
# leftover that keeps it centred.
#
# Unlabelled, the number reads as "the app ignored my margin". Basti set 1 mm
# and measured 8.6, and was right to ask -- part of it was a real fault (the
# row-label band was reserved OUTSIDE the margin in area-first; fixed) and part
# of it was this, which is correct and was simply never explained.
#: Built by a function, and the strings are LITERALS inside `tr()`, because
#: `scripts/i18n_extract.py` resolves `tr(NAME)` only for module-level string
#: constants -- a loop variable is invisible to it. Left as `tr(label)` over a
#: tuple, these four would have shipped untranslated in every language, silently,
#: which is this project's known extractor blind spot.
def _edges():
    return (("L", tr("Left (to first patch)")),
            ("R", tr("Right (to first patch)")),
            ("T", tr("Top (to first patch)")),
            ("B", tr("Bottom (to first patch)")))


class MarginInspectorPanel(QGroupBox):
    """Read-only margin readout + violation status + guide-line checkbox."""

    guides_toggled = pyqtSignal(bool)
    measured_guides_toggled = pyqtSignal(bool)
    coords_toggled = pyqtSignal(bool)
    #: (on, distance from edge mm, marker length mm) — #152

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(tr("Measured from Preview"), parent)
        self._mode = "dark"
        self._value_labels: dict[str, tuple[QLabel, QLabel]] = {}
        self._build_ui()
        self.show_placeholder()

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
        for key, label in _edges():
            name = QLabel(label, self)
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
        # THE PANEL'S OWN ⓘ, ON THE NUMBERS IT EXPLAINS. It used to sit against
        # the first tick box at the bottom, where it read as that box's help
        # while actually explaining the whole panel. Now that each tick box
        # answers for itself (#164), this one belongs with the table — top
        # right, on the header row.
        grid.addWidget(TooltipButton(
            tr("About the margin inspector"),
            tr("This little panel checks that the chart you just made will be "
               "easy to measure.\n\n"
               "Many spectrophotometers (like the i1Pro or ColorMunki) are slid "
               "along the printed chart by hand, often in a ruler or holder "
               "(sometimes called a jig or rig). For that to work, the coloured "
               "patches need a bit of blank white paper around them — if a "
               "patch sits too close to the edge of the page, the instrument "
               "can run off the paper or bump the ruler, and the reading fails. "
               "This panel helps you catch that before you print.\n\n"
               "What the numbers mean:\n"
               "• Left, Right, Top, Bottom — how much white space there is "
               "between each edge of the paper and the first PATCH, shown in "
               "both millimetres and inches.\n\n"
               "  These can read larger than the margins you set, and usually "
               "should. Two things sit in that space on purpose. Some charts "
               "print row indicators down the left and strip letters across the "
               "top, so you can find one patch among hundreds — that lettering "
               "needs room. And patches come in whole units, so the grid "
               "almost never divides the width exactly; the leftover is shared "
               "at both ends to keep the block centred on the page. Neither is "
               "the app ignoring your margins: they are the smallest white "
               "border you asked for, and this panel reports what the patches "
               "actually got.\n"
               "• Patch width — how wide one patch is across a strip.\n"
               "• Strip length — how long each strip of patches is (handy "
               "because some jigs have a maximum, e.g. 240 mm for the "
               "i1Pro).\n\n"
               "The 'min' column is the smallest each margin should be for your "
               "ruler or jig. If a margin is below its minimum, that row turns "
               "red and a short warning appears; when everything is fine you'll "
               "see a friendly green 'Margins: OK'.\n\n"
               "You decide those minimums yourself: open Preferences → "
               "Instrument Margins and set them for each instrument and paper "
               "size (the starting values are sensible defaults you can adjust "
               "to your own ruler). They're only a helpful warning — you can "
               "always go ahead and print anyway.\n\n"
               "The three tick boxes below draw these numbers onto the preview "
               "in different ways; each has its own ⓘ."), self),
            0, 4, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        v.addWidget(self._table)

        # Large pass/fail status, one or more lines.
        self._status = QLabel("", self)
        self._status.setWordWrap(True)
        self._status.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        v.addWidget(self._status)

        # Bottom row: the guide-lines checkbox, with the ⓘ help button tucked in
        # the corner so it doesn't take space at the top (#86).
        from PyQt6.QtWidgets import QHBoxLayout
        # A GRID, so every ⓘ in this panel shares one right-hand column.
        #
        # It used to be an HBox holding a column of checkboxes, a stretch and the
        # panel's own ⓘ — which put the helper-marker ⓘ at the end of its own row
        # and the panel ⓘ hard against the frame, 28 px further right and on a
        # different line. Knut, beta.3 of 4.0.2 (#152): *"The info icons on the
        # right side of the 'Measured from Preview' frame are not aligned to each
        # other and the frame is too wide."* Both are now cells in column 1, so
        # they line up by construction, and the frame is exactly as wide as its
        # widest row plus that column — no stretch pushing it out.
        bottom = QGridLayout()
        bottom.setContentsMargins(0, 0, 0, 0)
        bottom.setHorizontalSpacing(8)
        bottom.setVerticalSpacing(2)
        # WRAPPING BOXES. These three sit in a column of a panel whose width is
        # set by the tab, and a QCheckBox neither wraps nor elides — it clips.
        # In German the first of them wanted 482 px in the 437 it gets and lost
        # "(gepunktete Linien)" off the end (scripts/i18n_onscreen_audit.py,
        # 2026-08-27, once that audit was repaired to report anything at all).
        self._guide_check = WrappingCheckBox(
            tr("Show instrument-margin guide lines on preview (dotted lines)"), self)
        self._guide_check.toggled.connect(self.guides_toggled.emit)
        bottom.addWidget(self._guide_check, 0, 0)
        self._measured_check = WrappingCheckBox(
            tr("Show margin guide lines on preview (long dotted lines)"), self)
        self._measured_check.toggled.connect(self.measured_guides_toggled.emit)
        bottom.addWidget(self._measured_check, 1, 0)
        self._coord_check = WrappingCheckBox(
            tr("Show measurement coordinates on pointer"), self)
        self._coord_check.toggled.connect(self.coords_toggled.emit)
        bottom.addWidget(self._coord_check, 2, 0)

        # ONE ⓘ PER TICK BOX (#164, Basti). There used to be a single icon
        # against the first of the three, carrying one explanation of the panel
        # AND of all three boxes — so it looked like it belonged to that box, and
        # a reader after the third one had to work through the other two first.
        # Knut's own rule for this panel settles it: *"the help icon is not
        # vertically centered with the other objects on the line"* — an icon
        # belongs to the line it explains. Each box now answers for itself, in
        # its own words, and the overview of the NUMBERS above stays on the
        # panel's own icon.
        _align = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        bottom.addWidget(TooltipButton(
            tr("Instrument-margin guide lines"),
            tr("Draws the minimum margins your instrument needs straight onto "
               "the preview, as short dotted lines — one for each edge of the "
               "paper.\n\n"
               "Use it to see at a glance whether the patches keep far enough "
               "from the edges: a patch area that stays inside all four dotted "
               "lines is good to go. A line is black where that margin is fine "
               "and red where it is too tight, so a problem edge finds you "
               "rather than the other way round.\n\n"
               "You also get a thin solid rectangle marking the true edge of "
               "the sheet, because the page is drawn slightly inside the "
               "preview's white border — a 0 mm margin would sit right on that "
               "line.\n\n"
               "The minimums are yours to set: Preferences → Instrument "
               "Margins, per instrument and paper size.\n\n"
               "Default: off."), self), 0, 1, _align)
        bottom.addWidget(TooltipButton(
            tr("Margin guide lines"),
            tr("Draws a long dotted line at each of the four margins ChromIQ "
               "has just MEASURED — right where the patch area meets the white "
               "paper.\n\n"
               "This is the double-check for the numbers above: if the Left "
               "figure says 8.0 mm, this line shows you where those 8 mm end. "
               "It is a different thing from the instrument-margin lines above, "
               "which show what your ruler NEEDS rather than what the chart "
               "HAS — and you can have both sets on at once to compare them.\n\n"
               "Default: off."), self), 1, 1, _align)
        bottom.addWidget(TooltipButton(
            tr("Measurement coordinates on pointer"),
            tr("Turns your mouse into a ruler.\n\n"
               "Tick it and wherever you move the pointer over the chart, a "
               "thin cross-hair marks the exact spot and its position is shown "
               "next to it — measured from the top-left corner of the PAPER "
               "itself, not the preview's outer edge. The top line is "
               "millimetres to one decimal, the line below it inches to "
               "three.\n\n"
               "It is the easiest way to check a real distance on screen: "
               "hover over the edge of a patch, or over a margin, and read off "
               "exactly where it sits.\n\n"
               "Default: off."), self), 2, 1, _align)

        # (The ruler helper markers moved to Create Chart -> Manual -> Expert
        # Options -> "Ruler helper markers" in #158. They are printed on the
        # sheet and Generate Chart is what puts them there, so they belong with
        # the rest of the layout; keeping their row here also pinned this panel
        # to a 829 px floor, which is what Knut reported.)
        bottom.setColumnStretch(0, 1)
        # ONE GRID ROW PER LINE, so each ⓘ centres on the line it explains.
        # Knut, beta.8 (#152): *"the help icon is not vertically centered with
        # the other objects on the line for 'Show helper markers...'"*. The four
        # lines used to be a single nested column occupying one cell, which left
        # the icons nothing to align against — they could only be pinned to the
        # top and bottom of the whole block, and the bottom of that block is not
        # the middle of its last line. With real rows, AlignVCenter means what it
        # says, and column 1 still keeps both icons on the same right edge.
        v.addLayout(bottom)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_appearance(self, mode: str) -> None:
        from ui.theme import accept_mode
        self._mode = accept_mode(mode)

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
            # `source` is a structural marker, never translated. Sniffing the
            # translated `desc` for "laid out to" matched only in English, so
            # every other language was told the wrong minimum had been missed.
            self._thresholds_are_the_charts_own = (
                (thresholds or {}).get("source") == "chart")
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
        # THE STATUS LINE THROUGH `set_ink`. It was three raw literals - a red
        # for a violation, a green for "Margins: OK", a grey for "no
        # thresholds" - so it kept its hues in a theme that has none. The
        # owner saw the green one, and only after generating a preview: this
        # panel is empty until a chart exists, which is why every pixel census
        # walked past it.
        #
        # Nothing is lost by taking the hue out here, because the colour was
        # never the message: the warning names the edge, the measurement and
        # the threshold in words, and "Margins: OK" says so. `set_ink` returns
        # the Light and Dark values unchanged.
        if lines:                                       # something to warn about
            self._status.setText("\n".join(lines))
            set_ink(self._status, "#e0564b",
                    " font-size: 14px; font-weight: 700;", level="main")
            return
        if not thresholds_defined:
            self._status.setText(tr(
                "No instrument margins set for this instrument and paper size."))
            set_ink(self._status, "#909090", " font-size: 11px;", level="faint")
            return
        self._status.setText(tr("Margins: OK"))
        set_ink(self._status, "#4fc27a",
                " font-size: 15px; font-weight: 700;", level="main")
