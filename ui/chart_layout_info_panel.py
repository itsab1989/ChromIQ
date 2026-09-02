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
        )
        for r, (key, label) in enumerate(rows, start=1):
            grid.addWidget(QLabel(label, self), r, 0)
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
               "of a change before re-generating the chart."),
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
                 page_patches=None, fillup=None) -> dict:
        # Patch size is held as a rounded (w, h) tuple so the diff-highlight can
        # compare it; formatted to "w×h mm" at render time. 2 decimals so a
        # derived size like 7.34 mm is visible instead of hidden by 1-dp rounding.
        patch = None
        if patch_w and patch_h and patch_w > 0 and patch_h > 0:
            patch = (round(float(patch_w), 2), round(float(patch_h), 2))
        return {"total": total, "fillup": fillup, "page_patches": page_patches,
                "rows": rows, "cols": cols, "pages": pages, "patch": patch}

    def set_actual(self, *, total: int, rows: int, cols: int, pages: int,
                   patch_w: float = 0.0, patch_h: float = 0.0,
                   page_patches: "int | None" = None,
                   fillup: "int | None" = None) -> None:
        """The measured values of the chart currently in the preview.

        *fillup* = how many of *total* are paper-white strip fill-up patches
        (None = unknown), so a total that grew past the designed count is
        explained right where the number is read (#124, Knut)."""
        self._actual = self._as_dict(total, rows, cols, pages, patch_w, patch_h,
                                     page_patches, fillup)
        self._render()

    def clear_actual(self) -> None:
        self._actual = None
        self._render()

    def set_estimate(self, *, total: int, rows: int, cols: int, pages: int,
                     patch_w: float = 0.0, patch_h: float = 0.0,
                     page_patches: "int | None" = None,
                     fillup: "int | None" = None) -> None:
        """The predicted values for the current (engine) settings."""
        self._estimate = self._as_dict(total, rows, cols, pages, patch_w, patch_h,
                                       page_patches, fillup)
        self._render()

    def clear_estimate(self) -> None:
        self._estimate = None
        self._render()

    def show_placeholder(self) -> None:
        self._actual = self._estimate = None
        self._render()

    # ------------------------------------------------------------------
    def _render(self) -> None:
        if self._actual is None and self._estimate is None:
            self._placeholder.setVisible(True)
            self._table.setVisible(False)
            return
        self._placeholder.setVisible(False)
        self._table.setVisible(True)
        def _fmt(key, v):
            if v is None:
                return _DASH
            if key == "patch":
                return f"{v[0]:g}×{v[1]:g}"
            return str(v)

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
                differs = (abs(a[0] - e[0]) > self._PATCH_TOL_MM
                           or abs(a[1] - e[1]) > self._PATCH_TOL_MM)
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
