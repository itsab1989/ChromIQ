"""Dialog shown when chart generation (targen) runs unusually long.

targen's default patch-spread algorithm (Optimised Farthest Point Sampling)
produces the best distribution, but for some preconditioning profiles it
degenerates into an effective hang at high patch counts (see the targen
OFPS-cliff investigation). When the slow-chart watchdog in tab_chart fires,
this dialog lets the user keep waiting, rebuild the identical chart with the
fast perceptual quasi-random sampler (-Q), or cancel.

The three results are returned via ``exec()`` as the WAIT / FAST / CANCEL
class constants. Closing the dialog any other way (Esc, window close) is
treated as WAIT, the safe non-destructive default.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication, QPalette
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from core.i18n import tr
from core.logger import get_logger

log = get_logger(__name__)


class SlowChartDialog(QDialog):
    """Modal three-way prompt for a chart build that's taking too long."""

    # exec() result codes (avoid Accepted/Rejected so a stray Esc maps to WAIT).
    WAIT = 1
    FAST = 2
    CANCEL = 3

    def __init__(self, parent: QWidget | None = None, min_width: int = 560,
                 *, uses_profile: bool = True) -> None:
        """*uses_profile*: whether this build passes targen a pre-conditioning
        profile (-c). The window's own text is about such a build (a
        refinement chart); a chart built without one is told only what
        applies to it (M-CHART-SLOW-NO-PROFILE, beta 12)."""
        super().__init__(parent)
        self.uses_profile = bool(uses_profile)
        title = tr("This chart is taking longer than usual")
        self.setWindowTitle(title)
        self.setMinimumWidth(min_width)
        self.setMaximumWidth(max(min_width + 160, 760))
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )

        text_color = self.palette().color(QPalette.ColorRole.WindowText).name()

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 16)

        heading = QLabel(title, self)
        heading.setStyleSheet(
            f"font-size: 15px; font-weight: bold; color: {text_color};"
        )
        heading.setWordWrap(True)
        layout.addWidget(heading)

        if not self.uses_profile:
            from workflow.measurement_messages import M_CHART_SLOW_NO_PROFILE
            _title, body_text = M_CHART_SLOW_NO_PROFILE.render()
        else:
            body_text = self._text_for_a_profile_build()
        body = QLabel(body_text, self)
        body.setWordWrap(True)
        body.setStyleSheet(f"color: {text_color};")
        body.setTextFormat(Qt.TextFormat.PlainText)
        body.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        scroll = _BodyScrollArea(self)
        scroll.setWidget(body)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")
        scroll.viewport().setStyleSheet("background: transparent;")
        layout.addWidget(scroll, 1)

        # Buttons. The recommended action is the default (highlighted) one.
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        wait_btn = QPushButton(tr("Keep waiting"), self)
        wait_btn.clicked.connect(lambda: self.done(self.WAIT))

        fast_btn = QPushButton(tr("Rebuild with faster layout"), self)
        fast_btn.setDefault(True)
        fast_btn.clicked.connect(lambda: self.done(self.FAST))

        cancel_btn = QPushButton(tr("Cancel"), self)
        cancel_btn.clicked.connect(lambda: self.done(self.CANCEL))

        # Keep-waiting and the recommended Rebuild action sit on the left;
        # Cancel is pushed to the far right.
        btn_row.addWidget(wait_btn)
        btn_row.addWidget(fast_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

        # Robust sizing (mirrors ui.tooltip_button._InfoDialog): measure the
        # wrapping labels at the final content width so the body is never
        # clipped, and cap at 90% of screen height with the scroll area taking
        # over past that.
        self.adjustSize()
        margins = layout.contentsMargins()
        avail = self.width() - margins.left() - margins.right()

        heading_h = max(0, heading.heightForWidth(avail))
        heading.setMinimumHeight(heading_h)

        sb = self.style().pixelMetric(QStyle.PixelMetric.PM_ScrollBarExtent)
        body_h = max(0, body.heightForWidth(max(1, avail - sb)))
        body.setMinimumHeight(body_h)

        chrome = (margins.top() + margins.bottom()
                  + heading_h
                  + max(cancel_btn.sizeHint().height(),
                        fast_btn.sizeHint().height())
                  + 3 * layout.spacing())
        desired = chrome + body_h
        screen = self.screen() or QGuiApplication.primaryScreen()
        cap = (int(screen.availableGeometry().height() * 0.9)
               if screen is not None else desired)
        self.setMaximumHeight(cap)
        self.resize(self.width(), min(desired, cap))
        log.debug("SlowChartDialog created")


    @staticmethod
    def _text_for_a_profile_build() -> str:
        """The window's text for a chart built with a pre-conditioning
        profile, which is where the slowdown was first met."""
        return tr(
            "ChromIQ hasn't frozen — your chart is still being built in the "
            "background. With certain pre-conditioning profiles, Argyll's "
            "standard way of arranging the colour patches can slow down "
            "dramatically on larger (multi-page) charts, and that's what's "
            "happening here.\n\n"
            "You have three choices:\n\n"
            "• Keep waiting — let it finish with the highest-quality patch "
            "layout. Be aware this may take a very long time, and there's no "
            "reliable way to predict how long.\n\n"
            "• Rebuild with the faster layout (recommended) — ChromIQ stops "
            "this attempt and immediately rebuilds the same chart, with the "
            "same profile and the same number of patches, using a different "
            "patch-arrangement method that doesn't suffer from this slowdown. "
            "The patches are still spread evenly through your profile's colour "
            "space, so for a refinement chart the quality is effectively the "
            "same — and it usually finishes in under a second.\n\n"
            "• Cancel — stop building the chart. Nothing is saved."
        )


class _BodyScrollArea(QScrollArea):
    """Scroll area that reports its content's full preferred height so the
    dialog grows to show the whole body when it fits (same trick as
    ui.tooltip_button._BodyScrollArea)."""

    def sizeHint(self):
        base = super().sizeHint()
        w = self.widget()
        if w is not None:
            from PyQt6.QtCore import QSize
            h = max(w.sizeHint().height(), w.minimumHeight()) + 2 * self.frameWidth()
            return QSize(base.width(), h)
        return base
