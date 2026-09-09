"""The "Chart layout information" panel (Create Chart tab).

A small read-only readout of the chart's patch count, strip grid and page count,
shown next to the "Measured from Preview" margin inspector. Knut asked for this:
the only place these numbers appeared was the log text in the corner (#93).

Two columns differentiate the **chart currently on screen** (measured from the
generated chart) from a live **estimate** of the current settings — so after
loading a chart and changing options you can see both what's printed and what
regenerating would give (#93).
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QGridLayout, QGroupBox, QHBoxLayout, QLabel,
                            QVBoxLayout, QWidget)

from core.i18n import tr
from ui.widgets import set_ink
from ui.tooltip_button import TooltipButton
from workflow.hex_support import (HEX_HEIGHT_FACTOR,
                                  hex_two_heights_note)

_DASH = "—"
_AMBER = "#c47f17"      # estimate differs from the chart on screen
_MUTED = "#909090"

def _flag_by_weight() -> bool:
    """Does this appearance need weight to say what amber says elsewhere?"""
    from ui.index_rule import use_index_rule
    return use_index_rule()



class ChartLayoutInfoPanel(QGroupBox):
    """Patch-count / grid / page readout with on-screen vs estimate columns."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(tr("Chart layout information"), parent)
        self._actual: dict | None = None        # measured from the shown chart
        self._estimate: dict | None = None       # predicted from current settings
        self._actual_labels: dict[str, QLabel] = {}
        self._estimate_labels: dict[str, QLabel] = {}
        self._row_names: dict[str, QLabel] = {}
        #: Which axis the pitch row means, per column. None until a column has
        #: been filled, so an empty panel does not claim an orientation.
        self._pitch_axis: dict[str, "bool | None"] = {
            "actual": None, "estimate": None}
        self._build_ui()
        self._render()

    def _build_ui(self) -> None:
        v = QVBoxLayout(self)
        v.setSpacing(6)
        v.setContentsMargins(12, 8, 12, 10)

        self._placeholder = QLabel(
            tr("Generate a preview to see its layout."), self)
        self._placeholder.setWordWrap(True)
        self._placeholder.setStyleSheet("color: #909090; font-size: 11px;")
        v.addWidget(self._placeholder)

        # Fixed value-column width so the columns don't shift as values change
        # width (e.g. "8.9×8.9" vs "—"); the label column absorbs the slack.
        _COLW = 72

        self._table = QWidget(self)
        grid = QGridLayout(self._table)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(3)

        hdr_screen = QLabel(tr("on screen"), self)
        hdr_est = QLabel(tr("estimate"), self)
        for w in (hdr_screen, hdr_est):
            w.setAlignment(Qt.AlignmentFlag.AlignRight)
            w.setStyleSheet("color: #909090; font-size: 10px;")
            w.setFixedWidth(_COLW)
        grid.addWidget(hdr_screen, 0, 1)
        grid.addWidget(hdr_est, 0, 2)

        rows = (
            ("total", tr("Total patches")),
            ("fillup", tr("… of those, fill-up")),
            ("page_patches", tr("Patches (this page)")),
            ("rows", tr("Patches per strip")),
            ("cols", tr("Strips (this page)")),
            ("pages", tr("Pages")),
            ("patch", tr("Patch size (mm)")),
            # RENAMED AT RUNTIME ON A TURNED HONEYCOMB. See `set_pitch_axis`:
            # on a rotated sheet the second number is a COLUMN pitch across the
            # page, not a row pitch down a strip, and the panel printed 10.39 mm
            # under "Row pitch" where the sheet's rows are 12.00 mm apart.
            ("pitch", tr("Row pitch (mm)")),
        )
        for r, (key, label) in enumerate(rows, start=1):
            name = QLabel(label, self)
            self._row_names[key] = name
            grid.addWidget(name, r, 0)
            for col, store in ((1, self._actual_labels), (2, self._estimate_labels)):
                val = QLabel(_DASH, self)
                val.setAlignment(Qt.AlignmentFlag.AlignRight
                                 | Qt.AlignmentFlag.AlignVCenter)
                val.setStyleSheet("font-family: Menlo; font-size: 11px;")
                val.setFixedWidth(_COLW)
                grid.addWidget(val, r, col)
                store[key] = val
        grid.setColumnStretch(0, 1)
        v.addWidget(self._table)
        v.addStretch(1)

        bottom = QHBoxLayout()
        bottom.addStretch()
        bottom.addWidget(TooltipButton(
            tr("About chart layout information"),
            tr("This panel shows the SIZE and SHAPE of your chart — how many "
               "colour patches it has, how they're arranged, and how many pages "
               "it needs — so you can judge a chart before (and after) you make "
               "it.\n\n"
               "What the rows mean:\n"
               "• Total patches — how many colour squares the whole chart holds. "
               "More patches usually means a more accurate profile, but a bigger "
               "chart to print and measure.\n"
               "• … of those, fill-up — how many of the total are paper-white "
               "fill-up patches. Measuring instruments read whole strips, so "
               "when your designed patches don't fill the last strip exactly, "
               "it is topped up with plain paper-white patches (Argyll's "
               "printtarg does the same). That's why the total can be a little "
               "higher than the number of patches you designed — for example "
               "896 designed becoming 910 printed. The fill-up patches are "
               "measured like any others and are harmless; nothing of yours is "
               "lost or changed.\n"
               "• Patches per strip — how many patches sit in one strip (a strip "
               "is a single column the instrument reads from top to bottom).\n"
               "• Strips (this page) — how many of those strips fit across the "
               "page you're looking at.\n"
               "• Pages — how many sheets the chart spans.\n"
               "• Patch size — how big each patch is (width × height in mm). With "
               "“Prioritise chart area” this is worked out for you; very small "
               "patches can be hard for the instrument to read.\n\n"
               "The two columns:\n"
               "• on screen — the real numbers of the chart currently in the "
               "preview.\n"
               "• estimate — what the settings you have right now would produce "
               "if you generate. This is shown while the ChromIQ layout engine "
               "is switched on, because the engine can work the layout out "
               "exactly in advance.\n\n"
               "Change a setting (patch size, paper, margins, alignment…) and the "
               "estimate updates live. Any number that would come out different "
               "from the chart on screen turns amber — so you can see the effect "
               "of a change before re-generating the chart.")
            + "\n\n" + hex_two_heights_note(),
            self))
        v.addLayout(bottom)

    # ------------------------------------------------------------------
    # Patch sizes within this many mm count as equal (estimate vs on screen): the
    # estimate is the exact geometric size, the on-screen value is read back from
    # the pixel-snapped render, so they can legitimately differ by up to a pixel
    # plus a display-rounding step (~0.1 mm) without anything being wrong (#93).
    _PATCH_TOL_MM = 0.15

    @staticmethod
    def _as_dict(total, rows, cols, pages, patch_w, patch_h,
                 page_patches=None, fillup=None, row_pitch=None) -> dict:
        # Patch size is held as a rounded (w, h) tuple so the diff-highlight can
        # compare it; formatted to "w×h mm" at render time. 2 decimals so a
        # derived size like 7.34 mm is visible instead of hidden by 1-dp rounding.
        patch = None
        if patch_w and patch_h and patch_w > 0 and patch_h > 0:
            patch = (round(float(patch_w), 2), round(float(patch_h), 2))
        # `row_pitch` is set ONLY for a honeycomb, where the patch is taller than
        # the spacing between rows (they interlock). Square patches have nothing
        # to say here — their pitch is the height plus the spacer, a different
        # question — so the row stays hidden (#B8-80, Knut).
        pitch = (round(float(row_pitch), 2)
                 if row_pitch and float(row_pitch) > 0 else None)
        return {"total": total, "fillup": fillup, "page_patches": page_patches,
                "rows": rows, "cols": cols, "pages": pages, "patch": patch,
                "pitch": pitch}

    def set_actual(self, *, total: int, rows: int, cols: int, pages: int,
                   patch_w: float = 0.0, patch_h: float = 0.0,
                   page_patches: "int | None" = None,
                   fillup: "int | None" = None,
                   row_pitch: float = 0.0) -> None:
        """The measured values of the chart currently in the preview.

        *fillup* = how many of *total* are paper-white strip fill-up patches
        (None = unknown), so a total that grew past the designed count is
        explained right where the number is read (#124, Knut).

        *patch_h* is the patch's REAL height: for a hexagon that is tip to tip,
        not the slot it is drawn in. *row_pitch* carries the slot spacing for a
        honeycomb, where the two are different numbers and both matter."""
        self._actual = self._as_dict(total, rows, cols, pages, patch_w, patch_h,
                                     page_patches, fillup, row_pitch)
        self._render()

    def clear_actual(self) -> None:
        self._forget_pitch_axis("actual")
        self._actual = None
        self._render()

    def set_pitch_axis(self, flat_top: bool, *, column: str = "estimate") -> None:
        """Name the pitch row for the orientation, per COLUMN.

        The interlocking pitch is a ROW pitch down a strip on a pointy
        honeycomb and a COLUMN pitch across the page on a turned one, so the
        row has to say which. `_panel_patch_size_mm`'s docstring puts that duty
        on the caller.

        ONE NAME SERVES TWO COLUMNS THAT NEED NOT DESCRIBE THE SAME CHART, and
        that is what made the first two attempts at this wrong. The left column
        is the chart ON DISK and the right is what the current settings would
        build; with "Auto-update preview" off -- the state the two-column panel
        exists for -- they routinely differ, and whichever path ran last
        overwrote the other's label. The panel then printed "Patch size
        13.89 x 12.02" above "Row pitch 10.41" for a sheet whose rows are 12.02
        mm apart.

        So both are remembered and the name is a function of the pair: when
        they agree it names the axis, and when they disagree it says neither,
        because there is no single true answer to print.
        """
        if column not in ("actual", "estimate"):
            return
        self._pitch_axis[column] = bool(flat_top)
        self._name_the_pitch_row()

    def set_estimate(self, *, total: int, rows: int, cols: int, pages: int,
                     patch_w: float = 0.0, patch_h: float = 0.0,
                     page_patches: "int | None" = None,
                     fillup: "int | None" = None,
                     row_pitch: float = 0.0) -> None:
        """The predicted values for the current (engine) settings."""
        self._estimate = self._as_dict(total, rows, cols, pages, patch_w, patch_h,
                                       page_patches, fillup, row_pitch)
        self._render()

    def clear_estimate(self) -> None:
        self._forget_pitch_axis("estimate")
        self._estimate = None
        self._render()

    def show_placeholder(self) -> None:
        self._forget_pitch_axis("actual")
        self._forget_pitch_axis("estimate")
        self._actual = self._estimate = None
        self._render()

    def _forget_pitch_axis(self, column: str) -> None:
        """A CLEARED COLUMN STOPS VOTING ON THE ROW'S NAME.

        K1: every path that empties a column has to withdraw its claim, or the
        row goes on naming an axis for a column that is no longer shown -- or,
        worse, keeps saying "Patch pitch" because it still believes two columns
        disagree when only one is left. Measured on screen as
        `Patch size 13.89 x 12.02 / Patch pitch 10.41  --`, where the only
        pitch present is unambiguously a column pitch.
        """
        self._pitch_axis[column] = None
        self._name_the_pitch_row()

    def _name_the_pitch_row(self) -> None:
        """ONLY A COLUMN THAT IS SHOWING A PITCH GETS A VOTE.

        K1(b): the vote is recorded from the chart's orientation, but a
        rectangular chart has no interlocking pitch at all -- the panel prints
        "--" for it -- and its `flat_top=False` was still counted. So a turned
        honeycomb beside a rectangular estimate looked like a DISAGREEMENT and
        the row fell back to the neutral "Patch pitch (mm)", refusing to name
        the axis of the only pitch on the panel. Photographed in Manual and in
        Guided, where the estimate is an i1-style rectangular layout:

            Patch size (mm)      13.89x12.02       12x12
            Patch pitch (mm)           10.41         --

        A column whose data is loaded and whose pitch is `None` therefore
        abstains. A column with no data YET keeps its vote: that is the state
        between `set_pitch_axis` and the `set_actual`/`set_estimate` that
        follows it, and dropping it there would make the name flicker.
        """
        name = self._row_names.get("pitch")
        if name is None:
            return
        seen = set()
        for col, data in (("actual", self._actual),
                          ("estimate", self._estimate)):
            vote = self._pitch_axis.get(col)
            if vote is None:
                continue                       # never filled, or cleared
            if data is not None and data.get("pitch") is None:
                continue                       # on screen, but with no pitch
            seen.add(bool(vote))
        if len(seen) == 1:
            name.setText(tr("Column pitch (mm)") if seen.pop()
                         else tr("Row pitch (mm)"))
        elif len(seen) > 1:
            name.setText(tr("Patch pitch (mm)"))
        else:
            name.setText(tr("Row pitch (mm)"))  # nothing to name it from

    # ------------------------------------------------------------------
    def _render(self) -> None:
        if self._actual is None and self._estimate is None:
            self._placeholder.setVisible(True)
            self._table.setVisible(False)
            return
        self._placeholder.setVisible(False)
        self._table.setVisible(True)
        # The pitch row's NAME depends on which columns are showing a pitch,
        # and that changes with the data, not only with the vote. See
        # `_name_the_pitch_row`.
        self._name_the_pitch_row()
        def _fmt(key, v):
            if v is None:
                return _DASH
            if key == "patch":
                return f"{v[0]:g}×{v[1]:g}"
            if key == "pitch":
                return f"{v:g}"
            return str(v)

        # The row pitch row is a honeycomb's business only, and it is hidden
        # rather than dashed: a permanent "—" against a square chart would read
        # as a number the app failed to work out.
        _hex = bool((self._actual or {}).get("pitch")
                    or (self._estimate or {}).get("pitch"))
        for w in (self._row_names.get("pitch"),
                  self._actual_labels.get("pitch"),
                  self._estimate_labels.get("pitch")):
            if w is not None:
                w.setVisible(_hex)

        for key in self._actual_labels:
            a = self._actual.get(key) if self._actual else None
            e = self._estimate.get(key) if self._estimate else None
            self._actual_labels[key].setText(_fmt(key, a))
            est = self._estimate_labels[key]
            est.setText(_fmt(key, e))
            # Flag the estimate amber when it diverges from the shown chart. Patch
            # size gets a small tolerance so sub-pixel render rounding (estimate =
            # exact mm, on screen = pixel-snapped) isn't flagged as a mismatch.
            if a is None or e is None:
                differs = False
            elif key == "patch":
                # The tolerance absorbs ONE pixel of render snapping. A hexagon's
                # reported height is its slot scaled by 4/3, so that pixel is
                # scaled with it and the height tolerance has to be too, or a
                # honeycomb rendered at a low dpi flags amber against itself.
                _htol = self._PATCH_TOL_MM * (HEX_HEIGHT_FACTOR if _hex else 1.0)
                differs = (abs(a[0] - e[0]) > self._PATCH_TOL_MM
                           or abs(a[1] - e[1]) > _htol)
            elif key == "pitch":
                differs = abs(a - e) > self._PATCH_TOL_MM
            else:
                differs = a != e
            # THE FLAG SURVIVES WITHOUT THE HUE. Amber-versus-grey was the
            # only thing saying "this estimate does not match the chart on
            # screen", so taking the colour out in Neutral would delete the
            # information rather than de-hue it. The value carries it instead:
            # dark ink and bold where they differ, faint where they agree, so
            # the divergence is still the thing your eye lands on. Light and
            # Dark keep the amber, unchanged - `set_ink` returns their values
            # as they are.
            weight = " font-weight: 700;" if differs and _flag_by_weight() else ""
            set_ink(est, _AMBER if differs else _MUTED,
                    f" font-family: Menlo; font-size: 11px;{weight}",
                    level="main" if differs else "faint")
