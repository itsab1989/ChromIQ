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

    # WHAT THE REAL SETTINGS OBJECT CAN DO, THIS ONE MUST DO TOO.
    # `TabChart._current_layout_recipe` calls `apply_indicator_style`, and
    # without it `_collect_manual` raised — so the refresh that SHOWS the
    # ChromIQ layout panel never finished, the panel stayed hidden, and Qt
    # charges a hidden widget nothing. This script measured Create Chart ▸
    # Manual at 402 px against a 540 px viewport and reported it clean, on the
    # very build whose panel needed 577. Both implementations read nothing but
    # `self.get`, so the real ones are borrowed rather than copied.
    def indicator_style(self):
        from core.settings import AppSettings
        return AppSettings.indicator_style(self)

    def apply_indicator_style(self, recipe):
        from core.settings import AppSettings
        return AppSettings.apply_indicator_style(self, recipe)


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


def settle(app, rounds: int = 25):
    """Pump until the layout stops moving.

    Qt propagates an invalidated size hint ONE level of the widget tree per
    event round, and the Create Chart ▸ Manual sections are six deep inside two
    collapsible frames. Measured on the build that shipped the fault: the
    layout panel's own minimum only moved on round 2, the scroll content's on
    round 5. A single `processEvents()` after opening a section reads the OLD
    floor and reports a panel that fits when it does not.
    """
    for _ in range(rounds):
        app.processEvents()


def open_every_section(root, app):
    """Expand every collapsible section that is on screen.

    EXPAND, do not "check". `CollapsibleGroupBox` opens via
    `set_collapsed(False)`; it is not checkable, so `setChecked(True)` is
    silently ignored — two earlier probes measured the owner's screenshot with
    the very section he had photographed still folded, and reported it clean.
    """
    from ui.widgets import CollapsibleGroupBox
    for _ in range(4):
        opened = False
        for grp in root.findChildren(CollapsibleGroupBox):
            if grp.isVisible() and grp.is_collapsed():
                grp.set_collapsed(False)
                opened = True
        settle(app)
        if not opened:
            break


#: The Create Chart states a user actually sits in. The fault the owner
#: reported four times lives in MANUAL mode with the ChromIQ layout engine on —
#: a state this script never entered, because it audited whatever mode the tab
#: happened to open in (Guided) and never opened a section. Both engines are
#: walked: the engine panel and the printtarg controls are different widgets in
#: the same pane.
_CHART_STATES = (("guided", "guided", None),
                 ("manual+engine", "manual", True),
                 ("manual+printtarg", "manual", False))


def tab_states(tab):
    """The state names to audit this tab in — one entry, "", for a plain tab."""
    import ui.tabs.tab_chart as tc
    return [n for n, _, _ in _CHART_STATES] if isinstance(tab, tc.TabChart) \
        else [""]


def enter_state(tab, state, app):
    """Put *tab* into one of `tab_states`' states and let the layout settle.

    Applied ONE AT A TIME, immediately before the audit that measures it. An
    earlier version built the whole list up front with `list(generator)`, which
    left the tab in the LAST state and then measured that same state three
    times under three different names.
    """
    if not state:
        open_every_section(tab, app)
        return
    for name, mode, engine in _CHART_STATES:
        if name != state:
            continue
        tab._switch_mode(mode)
        box = getattr(tab, "_manual_engine_check", None)
        if engine is not None and box is not None:
            # TOGGLE, don't just set. `setChecked(True)` on a box that is
            # already checked emits nothing, so `_on_manual_engine_toggled`
            # never ran and the ChromIQ layout panel stayed HIDDEN — and Qt
            # charges a hidden widget nothing, so this script measured a
            # Manual pane with its widest section missing and called it clean
            # (487 px against a 540 px viewport, on a build where the pane was
            # really 577).
            if box.isChecked() != engine:
                box.setChecked(engine)
            else:
                tab._on_manual_engine_toggled(engine)
        settle(app)
        open_every_section(tab, app)
        # PROVE THE STATE, then measure. A missing `apply_indicator_style` on
        # `FakeSettings` made `_refresh_manual_command_preview` raise before it
        # could show the engine panel, and this script then measured a Manual
        # pane with its widest section missing and printed "no clipped buttons
        # found". Refusing to measure beats measuring the wrong thing.
        panel = getattr(tab, "_manual_layout_panel", None)
        if engine is not None and panel is not None \
                and panel.isVisible() != engine:
            raise SystemExit(
                f"AUDIT ABORTED: asked for Manual with the ChromIQ layout "
                f"engine {'on' if engine else 'off'}, and the engine panel is "
                f"{'not ' if engine else ''}on screen. Everything measured "
                f"from here would describe a pane this app never shows.")
        return


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
        # ALWAYS-ON EVIDENCE, not evidence only when something is wrong. This
        # check has twice reported "clean" while the app was visibly cut off,
        # and both times there was no way to tell a pane that fitted from a
        # pane that was never measured. AUDIT_VERBOSE=1 prints every pane it
        # looked at, so a missing pane shows up as missing.
        if os.environ.get("AUDIT_VERBOSE"):
            print(f"    seen {type(content).__name__:<24} "
                  f"floor={floor:4d} viewport={vw:4d} scrolled={scrolled}")
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
        settle(app)
        page = tabwidget.widget(i)
        # Every state of this tab, not just the one it happens to open in.
        for state in tab_states(page):
            enter_state(page, state, app)
            if os.environ.get("AUDIT_VERBOSE"):
                pnl = getattr(page, "_manual_layout_panel", None)
                extra = ""
                if pnl is not None:
                    extra = (f" engine-panel on-screen={pnl.isVisible()} "
                             f"floor={pnl.minimumSizeHint().width()}")
                print(f"  tab {i} {type(page).__name__}"
                      + (f" [{state}]" if state else "") + extra)
            audit(win, seen, clipped)
            before = len(hscroll)
            audit_hscroll(win, hscroll)
            label = f"tab {i}" + (f" [{state}]" if state else "")
            for name, cw, vw in hscroll[before:]:
                print(f"  {label}: HSCROLL {name} content={cw} viewport={vw}")

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
