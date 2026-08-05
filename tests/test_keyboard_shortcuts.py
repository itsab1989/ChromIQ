"""App-wide keyboard shortcuts (Knut/Sebastian keyboard-accessibility pass).

Every binding carries the ⌘ modifier (or is an F-key) so it never collides with
the single keys chartread claims during a measurement. These check the wiring:
⌘1–5 switch tabs and ⌘Return runs the current tab's primary action.

The MainWindow is built once (module-scoped) and never closed — its closeEvent
pulls in WebEngine/timer teardown that segfaults under offscreen Qt, and these
tests only need the constructed widget tree, not a clean shutdown."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QSettings
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import QApplication, QPushButton


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def win(qapp, tmp_path_factory):
    from core.settings import AppSettings
    from ui.main_window import MainWindow

    # Stub the offscreen-incompatible edges only: the ArgyllCMS-missing modal and
    # the native Cocoa title-bar tint (does Objective-C messaging on a window with
    # no native handle under offscreen Qt → segfault). Neither is under test.
    MainWindow._show_argyll_not_found_dialog = lambda self: None
    MainWindow._apply_title_bar = lambda self, mode: None
    tmp = tmp_path_factory.mktemp("kbd")
    s = AppSettings()
    s._qs = QSettings(str(tmp / "t.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp / "out"))
    s.set("restore_last_session", False)
    w = MainWindow(s)
    w.show()                                          # so button isVisible() is true
    qapp.processEvents()
    return w                                          # never closed — see module docstring


def test_every_tab_resolves_a_primary_button(win):
    """The ⌘Return dispatcher must find a real button on each tab — guards against
    a renamed attribute silently disabling the shortcut."""
    for i in range(win._tabs.count()):
        win._tabs.setCurrentIndex(i)
        btn = win._primary_action_button()
        assert isinstance(btn, QPushButton), f"tab {i} has no primary button"


def test_cmd_return_clicks_the_current_tab_primary(win):
    win._tabs.setCurrentIndex(0)                      # Create Chart
    btn = win._primary_action_button()
    btn.setEnabled(True)
    fired = []
    btn.clicked.connect(lambda: fired.append(True))
    win._trigger_primary_action()
    assert fired == [True]


def test_cmd_return_noop_when_primary_disabled(win):
    win._tabs.setCurrentIndex(0)
    btn = win._primary_action_button()
    btn.setEnabled(False)
    fired = []
    btn.clicked.connect(lambda: fired.append(True))
    win._trigger_primary_action()
    assert fired == []                               # disabled → nothing happens
    btn.setEnabled(True)


def test_all_shortcuts_carry_a_modifier_or_are_fkeys(win):
    """The core safety rule: no bare Space/Enter/Esc/arrow/letter shortcut, so
    none can steal a key chartread needs mid-measurement."""
    from PyQt6.QtCore import Qt

    unsafe = set()
    for sc in win.findChildren(QShortcut):
        seq = sc.key()
        for i in range(seq.count()):
            kc = seq[i]                              # QKeyCombination
            key = kc.key()
            is_fkey = Qt.Key.Key_F1 <= key <= Qt.Key.Key_F35
            if (kc.keyboardModifiers() == Qt.KeyboardModifier.NoModifier
                    and not is_fkey):
                unsafe.add(seq.toString())
    assert not unsafe, f"unsafe bare-key shortcuts: {unsafe}"


def test_cmd_tab_focuses_bar_so_arrows_move_between_tabs(win, qapp):
    """After ⌘N the tab strip takes focus, so ← / → then move between tabs (the
    arrows did nothing before — Basti)."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest

    # Arrow navigation only moves between ENABLED tabs, and the tab strip must
    # be in the ACTIVE window for the key to reach it. Both are established
    # here rather than inherited: another window built earlier in the same
    # process can hold the application's active-window slot, and a measurement
    # test can leave tabs disabled — either way the arrow silently does
    # nothing. The suite happened to run in an order where this held; running
    # in parallel it did not (2026-08-01).
    for i in range(win._tabs.count()):
        win._tabs.setTabEnabled(i, True)
    win.activateWindow()
    qapp.setActiveWindow(win)

    win._go_to_tab(2)                                  # ⌘3
    assert win._tabs.currentIndex() == 2
    assert win._tabs.tabBar().hasFocus()
    QTest.keyClick(win._tabs.tabBar(), Qt.Key.Key_Left)
    assert win._tabs.currentIndex() == 1               # ← → previous tab
    QTest.keyClick(win._tabs.tabBar(), Qt.Key.Key_Right)
    assert win._tabs.currentIndex() == 2               # → → next tab


def test_cmd_digits_are_bound_for_each_tab(win):
    bound = {sc.key().toString() for sc in win.findChildren(QShortcut)}
    for i in range(1, win._tabs.count() + 1):
        want = QKeySequence(f"Ctrl+{i}").toString()
        assert want in bound, f"missing tab shortcut {want}"


# --- the "Keyboard shortcuts" Help card -------------------------------------

def test_keyboard_help_card_is_registered(qapp):
    from ui.dialogs.welcome_dialog import WORKFLOWS

    card = next((w for w in WORKFLOWS if w["key"] == "keyboard_shortcuts"), None)
    assert card is not None and card["kind"] == "shortcuts"


def test_keyboard_help_html_is_alphabetical_and_complete(qapp):
    import re

    from ui.keyboard_help import keyboard_shortcuts_html

    h = keyboard_shortcuts_html()
    assert "<table" in h
    # The card has TWO tables: the app shortcuts, then the keys that drive a
    # measurement (Knut, beta.139). Only the first is alphabetical — the
    # measurement keys are in the order you meet them while reading a chart.
    first_table = h.split("</table>")[0]
    actions = re.findall(r"<td valign='top'>([^<]+)</td>", first_table)
    assert actions == sorted(actions, key=str.lower)
    # Every documented shortcut family is present.
    for token in ("⌘1", "⌘,", "⌘T", "F1", "⌘Z"):
        assert token in h, f"missing shortcut {token} in card"


def test_the_card_documents_the_measurement_keys(qapp):
    """Knut, beta.139: *"Make sure the help card with keyboard shortcuts are
    updated with new keys to use during measurement, also showing which
    chartread engine it applies to."*"""
    from ui.keyboard_help import keyboard_shortcuts_html

    h = keyboard_shortcuts_html()
    assert h.count("<table") == 2, "the measurement-key table is missing"
    measure_table = h.split("</table>")[1]
    # The keys a measurement actually listens for, including the two that
    # beta.139 gave a meaning to.
    for token in ("Space", "Esc", "⇧F", "Click a strip"):
        assert token in measure_table, f"missing measurement key {token}"


def test_the_card_says_which_engine_each_key_belongs_to(qapp):
    from ui.keyboard_help import keyboard_shortcuts_html

    h = keyboard_shortcuts_html()
    measure_table = h.split("</table>")[1]
    assert "Which engine" in measure_table
    assert "ChromIQ engine" in measure_table, "the engine-only key is unmarked"
    assert "Both engines" in measure_table
    # The one difference that can cost readings must be spelled out.
    assert "ArgyllCMS chartread" in h and "throws away" in h


def test_the_card_uses_the_words_the_rest_of_the_app_uses(qapp):
    """The app calls it an *engine* everywhere — "ChromIQ's own measuring
    engine", "the ChromIQ chart-reading engine" — and Settings labels the choice
    that way. An invented synonym leaves the reader hunting Preferences for a
    word that is not there."""
    from ui.keyboard_help import keyboard_shortcuts_html

    h = keyboard_shortcuts_html().replace("chart-reading", "")
    assert "reader" not in h.lower(), "the card invented a word for 'engine'"
    # …and it points at the tab by its real name.
    assert "Preferences → Beta." in h


def test_keyboard_help_icon_paints(qapp):
    from ui.dialogs.welcome_dialog import WorkflowIcon

    assert not WorkflowIcon("keyboard_shortcuts").grab().isNull()


# --- accessibility audit: no stray button focus on tab entry ----------------

def test_no_stray_button_focus_on_tab_entry(win, qapp):
    """The original bug: a button caught the initial focus when a tab opened, so
    the space bar activated it. _on_tab_changed clears that (deferred). Verify no
    tab lands focus on a button."""
    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import QAbstractButton

    for i in range(win._tabs.count()):
        win._tabs.setCurrentIndex(i)
        QTest.qWait(220)                     # let the 0/40/150 ms clear passes fire
        fw = qapp.focusWidget()
        assert not isinstance(fw, QAbstractButton), (
            f"tab {i}: a {type(fw).__name__} holds focus — space bar would fire it")
