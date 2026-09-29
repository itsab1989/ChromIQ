"""The space bar must not activate a button just because a tab or dialog handed
it the initial focus (Knut): icon/help buttons are non-focusable, and a shared
helper clears the stray focus a dialog's default button grabs on show."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QEventLoop, QTimer
from PyQt6.QtWidgets import QApplication, QAbstractButton, QPushButton
from PyQt6.QtCore import Qt


@pytest.fixture(scope="module")
def app():
    a = QApplication.instance() or QApplication([])
    # Mirror main.py: the app-level filter that clears a dialog's stray button focus.
    from ui.widgets import DialogFocusFilter
    if not getattr(a, "_dff_installed", False):
        f = DialogFocusFilter(a); a.installEventFilter(f)
        a._dff = f; a._dff_installed = True
    return a


def _wait(ms):
    loop = QEventLoop(); QTimer.singleShot(ms, loop.quit); loop.exec()


def test_icon_and_help_buttons_are_not_focusable(app):
    from ui.widgets import (PatchGridButton, MeasuredChartButton,
                            RevealFolderButton, ImageFileButton,
                            StackedPagesButton, StripReadButton)
    from ui.tooltip_button import TooltipButton
    from ui.builtin_preset_popup import BuiltinPresetButton
    for make in (
        lambda: PatchGridButton("#0a0"),
        lambda: MeasuredChartButton("#0a0"),
        lambda: RevealFolderButton("#0a0"),
        lambda: ImageFileButton("#0a0"),
        lambda: StackedPagesButton("#0a0"),
        lambda: StripReadButton("#0a0"),
        lambda: BuiltinPresetButton(),
        lambda: TooltipButton("title", "body"),
    ):
        w = make()
        assert w.focusPolicy() == Qt.FocusPolicy.NoFocus, type(w).__name__


def test_defer_clear_button_focus_drops_a_focused_button(app):
    from ui.widgets import defer_clear_button_focus
    from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLineEdit
    w = QWidget()
    lay = QVBoxLayout(w)
    btn = QPushButton("Do it", w)
    edit = QLineEdit(w)
    lay.addWidget(btn); lay.addWidget(edit)
    w.show()
    app.setActiveWindow(w); w.activateWindow()
    # WAIT FOR THE ACTIVATION BEFORE STARTING THE CLOCK. Under a loaded
    # -n worker the window-activation event could land after the function's
    # last pass (150 ms) and hand the focus back to the button, so the test
    # failed on timing (18270 passed, this one red; 8 of 8 green alone). A real
    # dialog is active by the time anyone can press Space, which is the case
    # the function exists for.
    from PyQt6.QtTest import QTest
    # ALONE ON THE SCREEN. In the beta 41 gates this failed twice on a loaded
    # machine and never alone or beside any single file: a window an earlier
    # test on the same worker left shown can take the activation back after
    # the last pass. The function is about ONE window being shown, so the
    # test shows only that one.
    for other in app.topLevelWidgets():
        if other is not w and other.isVisible():
            other.hide()
    QTest.qWaitForWindowActive(w, 2000)
    btn.setFocus()
    if app.focusWidget() is not btn:
        pytest.skip("offscreen platform doesn't report app-level focus here")
    defer_clear_button_focus(w)
    # POLL FOR THE CLEAR, DO NOT SAMPLE ONCE. On a loaded -n worker a later
    # activation of this window (another test's window closing in the same
    # process) can make Qt give the focus back to the first widget in the
    # chain AFTER the last pass has run; a single look at 250 ms then saw the
    # button again (red twice in full tiers, green alone every time). What the
    # function promises is that its passes take the focus OFF the button, so
    # that is what is waited for. Still red when the function clears nothing:
    # the focus then never leaves the button.
    import time
    cleared = False
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        _wait(10)
        if not isinstance(app.focusWidget(), QAbstractButton):
            cleared = True
            break
    assert cleared, "the focus never left the button"
    # an input field's focus is preserved
    edit.setFocus()
    defer_clear_button_focus(w)
    _wait(250)
    assert app.focusWidget() is edit
    w.close()


def test_report_dialog_does_not_leave_a_button_focused(app):
    from core.settings import AppSettings
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    d = MeasurementReportDialog(AppSettings()); d.resize(800, 700); d.show()
    _wait(300)
    assert not isinstance(app.focusWidget(), QAbstractButton)
    d.close()


def test_defer_clear_reaches_a_window_that_is_not_active(app):
    """The pass must clear the button a window will restore on activation,
    even while that window is not the active one (`QApplication.focusWidget()`
    is then None or another window's widget). This was the suite's
    intermittent red under load, and a dialog shown behind another window in
    the app. MUTATION, proven red: ask only `QApplication.focusWidget()`."""
    from ui.widgets import defer_clear_button_focus
    from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLineEdit
    from PyQt6.QtTest import QTest
    w = QWidget(); lay = QVBoxLayout(w)
    btn = QPushButton("Do it", w); lay.addWidget(btn); lay.addWidget(QLineEdit(w))
    other = QWidget(); QVBoxLayout(other).addWidget(QLineEdit(other))
    try:
        w.show(); app.setActiveWindow(w); w.activateWindow()
        QTest.qWaitForWindowActive(w, 2000)
        btn.setFocus()
        if w.focusWidget() is not btn:
            pytest.skip("the platform did not record the window's focus widget")
        other.show(); app.setActiveWindow(other); other.activateWindow()
        QTest.qWaitForWindowActive(other, 2000)
        if app.activeWindow() is w:
            pytest.skip("the platform did not move activation away")
        defer_clear_button_focus(w)
        _wait(300)
        assert w.focusWidget() is not btn, (
            "the inactive window still holds the button as its focus widget, "
            "so activating it would hand the space bar to the button")
    finally:
        other.close(); w.close()
        other.deleteLater(); w.deleteLater()
