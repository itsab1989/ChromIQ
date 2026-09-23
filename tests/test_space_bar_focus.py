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
    QTest.qWaitForWindowActive(w, 2000)
    btn.setFocus()
    if app.focusWidget() is not btn:
        pytest.skip("offscreen platform doesn't report app-level focus here")
    defer_clear_button_focus(w)
    _wait(250)                       # let the 0/40/150ms passes run
    assert not isinstance(app.focusWidget(), QAbstractButton)
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
