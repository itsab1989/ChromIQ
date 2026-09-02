"""A themed 3D viewer for colverify's ``-w`` difference map.

colverify ``-w`` writes an X3DOM ``.x3d.html`` (plus sibling ``x3dom.css`` /
``x3dom.js``) that draws an arrow from each *target* colour to where the print
actually landed — green marks the reference, red the measurement. This dialog
embeds that file in a ``QWebEngineView``, reusing the gamut viewer's HTML patch
(page background + full-height canvas) and its careful WebEngine teardown so the
markers' meaning is preserved (``themed=False`` — we do **not** recolour them) and
the page background matches the app's light/dark theme.
"""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QUrl, Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from core.logger import get_logger
from core.webengine_shutdown import drain_web_view
from ui.theme import resolve_mode
from workflow.gamut_viewer import _patch_html
from core.i18n import tr

log = get_logger(__name__)

# Page backgrounds matching the gamut viewer's frame (see GamutPanel).
_BG_DARK  = "#111111"
_BG_LIGHT = "#efebe6"


def webengine_available() -> bool:
    try:
        import PyQt6.QtWebEngineWidgets  # noqa: F401
        return True
    except ImportError:
        return False


class DriftPlotDialog(QDialog):
    """Modal 3D viewer for a colverify ``-w`` difference map."""

    def __init__(self, html_path: Path, settings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("3D difference map"))
        self.setMinimumSize(640, 520)
        self.resize(760, 640)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        self._mode = resolve_mode(settings.get("appearance", "auto"))
        # THE PAGE THE PLOT SITS ON. Folded into two answers, so the light-grey
        # appearance was handed `#111111` and opened a near-black window from a
        # light-grey one. Reached only after a colverify run has produced a
        # difference map, which is why nothing had rendered it. The green and
        # red MARKERS below stay exactly as they are (``themed=False``): they
        # are the measurement, and the legend names them by colour in words.
        from ui.theme import by_mode
        from ui import neutral_styles as _n
        bg = by_mode(_BG_LIGHT, _BG_DARK, _n.NM_BG_VIEWER, self._mode)
        # Patch the file in place: page background + full-height canvas, but keep
        # colverify's own green/red markers (themed=False) since they carry meaning.
        try:
            _patch_html(html_path, themed=False, bg=bg)
        except OSError:
            pass

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 12)
        layout.setSpacing(10)

        legend = QLabel(
            tr("Each line runs from the colour you asked for to the colour you got. "
            "<b><span style='color:#3ec95a;'>Green</span></b> dots are the reference "
            "(target) values; <b><span style='color:#e34d4d;'>red</span></b> dots are "
            "your measurement. Drag to rotate, scroll to zoom."),
            self,
        )
        legend.setWordWrap(True)
        legend.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(legend)

        self._web_view = None
        try:
            from PyQt6.QtWebEngineWidgets import QWebEngineView
            view = QWebEngineView(self)
            view.page().setBackgroundColor(QColor(bg))
            try:
                from PyQt6.QtWebEngineCore import QWebEngineSettings
                view.settings().setAttribute(
                    QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True
                )
            except (ImportError, AttributeError):
                pass
            view.setUrl(QUrl.fromLocalFile(str(html_path)))
            self._web_view = view
            layout.addWidget(view, 1)
        except ImportError:
            fallback = QLabel(
                tr("Install PyQt6-WebEngine to view the interactive 3D difference map."),
                self,
            )
            fallback.setAlignment(Qt.AlignmentFlag.AlignCenter)
            fallback.setWordWrap(True)
            layout.addWidget(fallback, 1)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        bb.rejected.connect(self.reject)
        bb.accepted.connect(self.reject)
        layout.addWidget(bb)

    # ------------------------------------------------------------------
    def _teardown_webengine(self) -> None:
        """Synchronously destroy the web view when the dialog closes, so it
        can't leave a live Chromium subtree for SIP to walk into at quit. See
        :mod:`core.webengine_shutdown` and issue #38."""
        drain_web_view(self._web_view)
        self._web_view = None

    def reject(self) -> None:  # noqa: D102
        self._teardown_webengine()
        super().reject()

    def closeEvent(self, event) -> None:  # noqa: N802
        self._teardown_webengine()
        super().closeEvent(event)
