"""Offscreen render of the full main window in a given language; flags
clipped buttons/checkboxes (incl. multi-line) and horizontally overflowing
scroll panes.

Usage:  AUDIT_LANG=<code> QT_QPA_PLATFORM=offscreen python scripts/i18n_onscreen_audit.py
"""
import os

import sys
sys.path.insert(0, ".")

from core.logger import configure_logging
configure_logging()

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFontDatabase
from PyQt6.QtWidgets import (
    QApplication, QPushButton, QToolButton, QCheckBox, QRadioButton, QLabel,
)

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass
import faulthandler
faulthandler.enable()

from core.i18n import set_language
from core.resource_path import resource_path
from core.settings import DEFAULTS
from ui.styles import WinButtonLayoutStyle
from ui.theme import apply_appearance


class FakeSettings:
    def __init__(self, **overrides):
        self._store = {**DEFAULTS, **overrides}
    def get(self, key, default=None):
        return self._store.get(key, default)
    def set(self, key, value):
        self._store[key] = value
    def save_tab_defaults(self, prefix, values):
        for k, v in values.items():
            self.set(f"{prefix}_{k}", v)

    def sync(self):
        """`MainWindow.closeEvent` calls this. Without it the close raised
        AttributeError inside a Qt event handler, PyQt turned that into a
        FATAL abort, and `abort()` kills the process WITHOUT FLUSHING STDOUT —
        so this script printed its findings and then threw them away. It has
        been reporting nothing at all, which is why German shipped with a
        clipped checkbox and a horizontally scrolling section (Basti,
        2026-08-27). A stub that goes stale against the real settings object is
        the hazard; anything new `closeEvent` calls belongs here too."""

    def remove(self, key):
        self._store.pop(key, None)


def audit(root, seen, out):
    for w in root.findChildren((QPushButton, QToolButton, QCheckBox, QRadioButton)):
        if id(w) in seen:
            continue
        seen.add(id(w))
        text = w.text().replace("&", "")
        if not text:
            continue
        # A BUTTON THAT DOES NOT PAINT ITS TEXT CANNOT CLIP IT. `BarIconButton`
        # and friends keep the label on the widget for assistive technology and
        # draw `ToolButtonIconOnly`, so Qt still charges the text to
        # `minimumSizeHint` — three of them were reported as 3 px short in EVERY
        # language, English included, which made this script's exit code
        # useless: always 1, whether or not anything was really wrong.
        if isinstance(w, QToolButton) and \
                w.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly:
            continue
        hint = w.minimumSizeHint().width()
        actual = w.width()
        if w.isVisible() and actual > 0 and hint > actual + 1:
            out.append((type(w).__name__, text.replace("\n", "\\n"), hint, actual))


def audit_hscroll(root, out):
    """Flag scroll areas whose content is wider than the viewport."""
    from PyQt6.QtWidgets import QScrollArea
    for sa in root.findChildren(QScrollArea):
        if not sa.isVisible():
            continue
        content = sa.widget()
        if content is None:
            continue
        # COMPARE `minimumSizeHint` WITH THE VIEWPORT. Not `sizeHint`, and NOT
        # the scrollbar.
        #
        # The first version of this check compared `content.sizeHint().width()`
        # — what a widget would LIKE — and so cried wolf on English, where the
        # layout simply compresses. It was then changed to ask
        # `horizontalScrollBar().isVisible()`, on the theory that the bar is the
        # ground truth, and it reported German CLEAN. It is not the ground
        # truth: `TabChart._make_manual_panel` pins that bar OFF
        # (`ScrollBarAlwaysOff`), so it can never be visible however far the
        # content overflows — the content is CLIPPED instead, and a trackpad
        # swipe scrolls it sideways. German was 19 px over at the time and this
        # check said nothing, which is the second time it reported nothing at
        # all (Basti, 2026-08-27).
        #
        # `minimumSizeHint` is what the content CANNOT go below. Wider than the
        # viewport means something is cut off, bar or no bar. `maximum()` is
        # reported beside it because it is non-zero exactly when Qt has actually
        # scrolled the content, which is the same fault seen from the other end.
        vw = sa.viewport().width()
        if vw <= 0:
            continue
        floor = content.minimumSizeHint().width()
        bar = sa.horizontalScrollBar()
        scrolled = bar.maximum() if bar else 0
        if floor <= vw and scrolled <= 0:
            continue
        out.append((sa.objectName() or type(content).__name__, floor, vw))


def main():
    app = QApplication(sys.argv)
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))
    app.setStyle(WinButtonLayoutStyle("Fusion"))

    import os as _os2
    set_language(_os2.environ.get("AUDIT_LANG", "de"))
    settings = FakeSettings(show_welcome_dialog=False, restore_last_session=False,
                            restore_last_tab=False)
    apply_appearance(app, None, "dark")

    from ui.main_window import MainWindow
    # native objc title-bar call segfaults under the offscreen platform
    MainWindow._apply_title_bar = lambda self, mode: None
    win = MainWindow(settings)
    import os as _os
    w = int(_os.environ.get("AUDIT_W", "1440")); h = int(_os.environ.get("AUDIT_H", "900"))
    win.resize(w, h)
    win.show()
    app.processEvents()

    seen, clipped, hscroll = set(), [], []
    # visit every tab so its widgets get laid out
    tabs = win.findChild(type(win.centralWidget()), None)
    tabwidget = getattr(win, "_tabs", None) or getattr(win, "tabs", None)
    if tabwidget is None:
        from PyQt6.QtWidgets import QTabWidget
        tabwidget = win.findChild(QTabWidget)
    n = tabwidget.count() if tabwidget else 0
    print(f"tabs: {n}")
    for i in range(n):
        tabwidget.setCurrentIndex(i)
        app.processEvents()
        audit(win, seen, clipped)
        before = len(hscroll)
        audit_hscroll(win, hscroll)
        for name, cw, vw in hscroll[before:]:
            print(f"  tab {i}: HSCROLL {name} content={cw} viewport={vw}")

    # Settings dialog too
    from ui.dialogs.settings_dialog import SettingsDialog
    dlg = SettingsDialog(settings, win)
    dlg.show()
    app.processEvents()
    audit(dlg, seen, clipped)

    print(f"audited {len(seen)} buttons/checkboxes")
    if clipped:
        print(f"CLIPPED ({len(clipped)}):")
        for cls, text, hint, actual in clipped:
            print(f"  {cls:13s} need={hint:4d} have={actual:4d}  {text!r}")
    else:
        print("no clipped buttons found")

    # sample German visibility check
    labels = [w.text() for w in win.findChildren(QLabel) if w.text()][:8]
    print("sample labels:", labels)
    # FLUSH BEFORE CLOSING ANYTHING. A fatal error inside a Qt close handler
    # aborts the process, and an aborted process does not flush stdout — the
    # findings above would be lost exactly when something is wrong.
    sys.stdout.flush()
    dlg.close()
    win.close()
    app.processEvents()
    return 1 if (clipped or hscroll) else 0


if __name__ == "__main__":
    raise SystemExit(main())
