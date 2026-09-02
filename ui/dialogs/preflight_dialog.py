"""Pre-flight confirmation dialog shown before submitting a print job.

Shows the user the exact lp options that will be sent to CUPS so they can
verify printer/size/media/quality/orientation/borderless and the forced
duplex-off + colour-management-off state before the chart wastes paper.
"""
from __future__ import annotations

from typing import Iterable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)
from core.i18n import tr
from ui.widgets import banner_qss


def _neutral() -> bool:
    """Is the colourless appearance the one on screen?"""
    from ui.theme import APPEARANCE_NEUTRAL, active_mode
    return active_mode() == APPEARANCE_NEUTRAL


class PreflightDialog(QDialog):
    """Read-only summary of every option that will be passed to lp."""

    def __init__(
        self,
        rows: Iterable[tuple[str, str]],
        warnings: Iterable[str] = (),
        pages: int = 1,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Confirm Print Settings"))
        self.setMinimumWidth(520)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )
        self._dont_ask_again = False
        self._build_ui(list(rows), list(warnings), pages)

    # ------------------------------------------------------------------

    def _build_ui(
        self,
        rows: list[tuple[str, str]],
        warnings: list[str],
        pages: int,
    ) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 16, 20, 16)
        outer.setSpacing(12)

        header = QLabel(
            tr("About to send <b>1</b> page to your printer. Please confirm:")
            if pages == 1 else
            tr("About to send <b>{pages}</b> pages to your printer. "
               "Please confirm:").format(pages=pages),
            self,
        )
        header.setWordWrap(True)
        outer.addWidget(header)

        form_frame = QFrame(self)
        form_frame.setFrameShape(QFrame.Shape.StyledPanel)
        form = QFormLayout(form_frame)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setContentsMargins(14, 10, 14, 10)
        form.setVerticalSpacing(4)
        for label, value in rows:
            lbl_w = QLabel(tr("{label}:").format(label=label), form_frame)
            lbl_w.setStyleSheet("color: #a0a0a0;")
            val_w = QLabel(value, form_frame)
            val_w.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            form.addRow(lbl_w, val_w)
        outer.addWidget(form_frame)

        for w in warnings:
            warn = QLabel(tr("⚠  {w}").format(w=w), self)
            warn.setWordWrap(True)
            # Light and Dark keep the amber-on-brown box they have always had
            # (it is the same in both — this one never grew a light branch).
            # Neutral gets dark ink on the raised surface with the handoff's
            # warning underline: no hue, and nothing faint.
            if _neutral():
                warn.setStyleSheet(banner_qss("#fdd835", "#2a2000", kind="warn"))
            else:
                warn.setStyleSheet(
                    "QLabel { color: #fdd835; background: #2a2000;"
                    " border: 1px solid #f9a825; border-radius: 4px;"
                    " padding: 8px; }"
                )
            outer.addWidget(warn)

        self._dont_ask_cb = QCheckBox(tr("Don't ask again"), self)
        outer.addWidget(self._dont_ask_cb)

        btn_row = QHBoxLayout()
        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        print_btn = bb.addButton(tr("Print"), QDialogButtonBox.ButtonRole.AcceptRole)
        print_btn.setObjectName("primary")
        print_btn.setDefault(True)
        bb.accepted.connect(self._on_accept)
        bb.rejected.connect(self.reject)
        btn_row.addStretch()
        btn_row.addWidget(bb)
        outer.addLayout(btn_row)

    # ------------------------------------------------------------------

    def _on_accept(self) -> None:
        self._dont_ask_again = self._dont_ask_cb.isChecked()
        self.accept()

    def dont_ask_again(self) -> bool:
        return self._dont_ask_again
