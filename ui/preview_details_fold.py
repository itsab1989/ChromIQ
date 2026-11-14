"""The fold above "Measured from Preview" and "Chart layout information".

Basti, 2026-11-14: *"in create chart tab can you make measured from preview
and chart layout information section collapsible? i think one button (or
triangle) should collapse both at once. i want a quick way to show and hide
it"*.

One header line under the chart preview, in the look of the tab's other
folding sections (`ui.widgets.CollapsibleGroupBox`: a bold title led by a
filled ▼ / ▶). A click on the line, or Space / Return while it has the
keyboard focus, hides or shows BOTH frames; hidden, the preview takes their
height. The line is never silent: while the frames are hidden it repeats their
verdict, the green "Margins: OK" or, in red, how many warnings there are, so
a warning that turns up after a preview update or a Generate is seen without
opening anything. A new warning does not open the frames: the person chose to
hide them.

The open / closed state is a view choice of the window, like the warning fold
inside "Measured from Preview" (`margin_warnings_expanded`): it is stored in
the app's settings (`preview_details_collapsed`), the same in Guided and
Manual, and is not part of a target or a preset (per_target_settings §1.1).
"""
from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QWidget

from core.i18n import tr


class PreviewDetailsFold(QWidget):
    """The header line; the owner hides and shows the frames on `toggled`."""

    #: True when the person has just folded the frames away.
    toggled = pyqtSignal(bool)

    def __init__(self, parent=None, *, collapsed: bool = False,
                 accent: str = "#d0459a") -> None:
        super().__init__(parent)
        self._collapsed = bool(collapsed)
        self._accent = accent
        self._verdict: "tuple[str, int]" = ("none", 0)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Preferred,
                           QSizePolicy.Policy.Fixed)
        row = QHBoxLayout(self)
        # 16 at the sides, like the two frames under it (`_info_row`).
        row.setContentsMargins(16, 6, 16, 2)
        row.setSpacing(10)
        self._title = QLabel(self)
        _f = self._title.font()
        _f.setBold(True)
        self._title.setFont(_f)
        row.addWidget(self._title)
        self._status = QLabel(self)
        self._status.setTextFormat(Qt.TextFormat.PlainText)
        row.addWidget(self._status)
        row.addStretch(1)
        for lbl in (self._title, self._status):
            # the line is one control: a click anywhere on it is the line's
            lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setToolTip(tr(
            "Show or hide the two boxes under the chart preview, “Measured "
            "from Preview” and “Chart layout information”, both at once.\n\n"
            "Hidden, the chart preview gets their room. This line then still "
            "tells you how the chart's margins look: “Margins: OK” in green "
            "when everything fits, or the number of warnings in red. Click "
            "the line (or press Space when it is selected) to see them again.\n\n"
            "ChromIQ remembers your choice, also after a restart."))
        self.setAccessibleName(tr("Preview details"))
        self._render()

    # -- state ---------------------------------------------------------------
    def is_collapsed(self) -> bool:
        return self._collapsed

    def set_collapsed(self, collapsed: bool, *, emit: bool = False) -> None:
        """Fold or unfold. Restoring the stored answer does not emit, so it
        is not mistaken for the person's click and written back."""
        collapsed = bool(collapsed)
        changed = collapsed != self._collapsed
        self._collapsed = collapsed
        self._render()
        if emit and changed:
            self.toggled.emit(collapsed)

    def toggle(self) -> None:
        self.set_collapsed(not self._collapsed, emit=True)

    def set_verdict(self, kind: str, count: int = 0) -> None:
        """What the frames say, as `MarginInspectorPanel.verdict` gives it."""
        self._verdict = (kind, int(count))
        self._render()

    def status_text(self) -> str:
        """The verdict line as shown, or "" while it is hidden."""
        return "" if self._status.isHidden() else self._status.text()

    # -- drawing -------------------------------------------------------------
    def _render(self) -> None:
        from ui.widgets import set_ink
        arrow = "▶" if self._collapsed else "▼"
        self._title.setText(f"{arrow}  " + tr("Preview details"))
        self._title.setStyleSheet(f"color: {self._title_ink()};")
        kind, n = self._verdict
        text = ""
        if self._collapsed:
            if kind == "warnings":
                body = (tr("1 warning") if n == 1
                        else tr("{n} warnings").format(n=n))
                text = f"{body} " + tr("(click to show)")
                set_ink(self._status, "#e0564b", " font-weight: 700;",
                        level="main")
            elif kind == "ok":
                text = tr("Margins: OK")
                set_ink(self._status, "#4fc27a", " font-weight: 700;",
                        level="main")
        self._status.setText(text)
        self._status.setVisible(bool(text))

    @staticmethod
    def _title_ink() -> str:
        """The ink of every group-box title in the app (the "Output" and
        "Presets" headers beside it), per appearance, so this line reads as
        one more of them."""
        from ui.theme import active_mode
        from ui.light_styles import LM_TEXT_FAINT
        from ui.neutral_styles import NM_TEXT_FAINT
        from ui.styles import TEXT_DIM
        return {"light": LM_TEXT_FAINT,
                "neutral": NM_TEXT_FAINT}.get(active_mode(), TEXT_DIM)

    def changeEvent(self, event) -> None:         # noqa: N802 (Qt override)
        from PyQt6.QtCore import QEvent
        super().changeEvent(event)
        if event.type() in (QEvent.Type.PaletteChange,
                            QEvent.Type.StyleChange):
            self._title.setStyleSheet(f"color: {self._title_ink()};")

    def paintEvent(self, event) -> None:          # noqa: N802 (Qt override)
        super().paintEvent(event)
        if not self.hasFocus():
            return
        # The keyboard focus, in the tab's own accent, round the title only.
        from ui.theme import accent_for
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(accent_for(self._accent)))
        pen.setWidthF(1.5)
        p.setPen(pen)
        r = self._title.geometry().adjusted(-4, -2, 4, 2)
        p.drawRoundedRect(QRectF(r), 4, 4)
        p.end()

    # -- input ---------------------------------------------------------------
    def mousePressEvent(self, event) -> None:     # noqa: N802 (Qt override)
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle()
            event.accept()
            return
        super().mousePressEvent(event)

    def keyPressEvent(self, event) -> None:       # noqa: N802 (Qt override)
        if event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return,
                           Qt.Key.Key_Enter):
            self.toggle()
            event.accept()
            return
        super().keyPressEvent(event)

    def focusInEvent(self, event) -> None:        # noqa: N802 (Qt override)
        super().focusInEvent(event)
        self.update()

    def focusOutEvent(self, event) -> None:       # noqa: N802 (Qt override)
        super().focusOutEvent(event)
        self.update()
