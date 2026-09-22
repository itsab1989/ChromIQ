"""Startup "update available" popup.

Replaces the old tab status-bar notice. Uses the shared tab-style masthead
(uppercase eyebrow + serif title over the five-colour spectrum stripe), the same
look as the Tools windows, via :func:`ui.tab_header.dialog_masthead`.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QLabel, QVBoxLayout,
)

from core.i18n import tr
from core.updater import _RELEASES_PAGE
from core.version import APP_VERSION
from ui.tab_header import dialog_masthead


class UpdateAvailableDialog(QDialog):
    """Tells the user a newer ChromIQ release exists and offers to download it.

    Read :attr:`disable_notifications` after :meth:`exec` to learn whether the
    user asked not to be reminded about new versions at all.
    """

    def __init__(self, latest: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Update available"))
        self.setMinimumWidth(540)
        self._latest = latest

        # Full-width masthead (stripe bleeds to the edges); content re-inset.
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        head, _header, stripe = dialog_masthead(
            self, tr("SOFTWARE UPDATE"), tr("Update available"))
        root.addLayout(head)
        root.addWidget(stripe)

        inner = QVBoxLayout()
        inner.setContentsMargins(22, 14, 22, 16)
        inner.setSpacing(12)
        root.addLayout(inner)

        body = QLabel(
            tr("ChromIQ {latest} is available — you're running {current}.\n\n"
               "Download the new version and install it over your current one; "
               "your settings and projects are kept.").format(
                   latest=latest, current=f"v{APP_VERSION}"),
            self)
        body.setWordWrap(True)
        body.setTextFormat(Qt.TextFormat.PlainText)
        inner.addWidget(body)

        self._skip = QCheckBox(
            tr("Don't remind me of new available versions"), self)
        inner.addWidget(self._skip)

        bb = QDialogButtonBox(self)
        download_btn = bb.addButton(
            tr("Download"), QDialogButtonBox.ButtonRole.AcceptRole)
        later_btn = bb.addButton(
            tr("Later"), QDialogButtonBox.ButtonRole.RejectRole)
        download_btn.setDefault(True)
        download_btn.clicked.connect(self._open_download_page)
        later_btn.clicked.connect(self.reject)
        inner.addWidget(bb)

        # THE WINDOW MAY NOT OPEN SHORTER THAN ITS OWN TEXT. Knut, 2026-09-22:
        # *"Sometime the window opens too short in height, making the text
        # being cut ... The window should always show all text, and not keep
        # the window fixed and push the text into a frame that is partly not
        # shown on screen."*
        #
        # A WORD-WRAPPED `QLabel` DOES NOT REPORT THE HEIGHT IT NEEDS. Its
        # `minimumSizeHint` is computed from its own minimum content rather
        # than from the height the text takes at the width the dialog gives
        # it, so the dialog's minimum stays put while its sizeHint grows with
        # the body. Measured on screen, English, the only thing changed being
        # the length of the version string in the body:
        #
        #     latest                                  sizeHint   minimumSizeHint
        #     v9.9.9                                    346x294       329x262
        #     v4.3.0-beta.32                            346x294       329x262
        #     v4.3.0-beta.32-rc1+build.20260922.arm64   346x310       329x262
        #
        # So with a long version the content needs 310 px and nothing stopped
        # the window being 262. That is exactly the fault: the text is cut and
        # the user has to drag the window taller to read it.
        #
        # The width is pinned at 540 above, so the body can never have to wrap
        # into MORE lines than it does here, and the height this asks for is
        # the height it will need. Widening the window only frees space.
        self.layout().activate()
        self.setMinimumHeight(self.sizeHint().height())

    def _open_download_page(self) -> None:
        QDesktopServices.openUrl(QUrl(_RELEASES_PAGE))
        self.accept()

    @property
    def disable_notifications(self) -> bool:
        return self._skip.isChecked()
