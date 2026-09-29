"""The button Return presses is FILLED in the window's accent (K44).

Knut, #182 5833776276: *"there is no indication that the Create New button is
the default choice"*; and 5833983335: some windows fill their main button, the
device-link window framed it, *"all windows and pop-up windows then should
follow the same standard"*.

The standard: the default button (Qt's ``isDefault()``, what Return presses)
is filled in the window's accent, the ``#primary`` look: the application's
accent in a window without one, the masthead's or the tab's otherwise
(`default_button_qss`). A non-default button is not filled; a DISABLED default
takes the disabled primary look; the SAFE default of a destructive question
(`mark_safe_default`) keeps the ordinary look. Painted pixels, all three
appearances.

The sheet is set on the test's own dialog, never on the application (see
CLAUDE.md: `qapp.setStyleSheet` re-polishes the whole suite's widgets). A
dialog's own sheet is exactly how a window's accent reaches it. The windows
are kept alive to the end of the module, so no later widget can reuse a
deleted one's address and meet a style cache that was not its own.
"""
from __future__ import annotations

import pytest
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QApplication, QDialog, QHBoxLayout, QMessageBox, QPushButton,
)

from ui import light_styles, neutral_styles, styles
from ui.default_button import freeze_default, mark_safe_default
from ui.light_styles import LIGHT_STYLESHEET
from ui.neutral_styles import NEUTRAL_STYLESHEET
from ui.styles import APP_STYLESHEET, SPEC_GREEN
from ui.theme import app_accent, default_button_qss

SHEETS = {
    "light": LIGHT_STYLESHEET,
    "dark": APP_STYLESHEET,
    "neutral": NEUTRAL_STYLESHEET,
}
#: The fill of an ordinary, enabled button, per appearance.
PLAIN_FILL = {
    "light": light_styles.LM_BG_WIDGET,
    "dark": styles.NEUTRAL_BTN,
    "neutral": neutral_styles.NM_BG_WIDGET,
}
MODES = ["light", "dark", "neutral"]
_KEEP: list = []


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app
    for w in _KEEP:
        w.close()
    _KEEP.clear()


def _fill(btn: QPushButton) -> QColor:
    """The button's fill, as painted: inside the edge and the rounded corner,
    left of the label (the sheet pads the label 18 px in)."""
    img = btn.grab().toImage()
    return QColor(img.pixel(6, img.height() // 2))


def _near(a: QColor, hex_: str, tol: int = 20) -> bool:
    b = QColor(hex_)
    return (abs(a.red() - b.red()) <= tol and abs(a.green() - b.green()) <= tol
            and abs(a.blue() - b.blue()) <= tol)


def _dialog(qapp, mode: str, accent: str | None = None):
    dlg = QDialog()
    _KEEP.append(dlg)
    sheet = SHEETS[mode]
    if accent is not None:
        sheet += default_button_qss(accent, mode)
    dlg.setStyleSheet(sheet)
    row = QHBoxLayout(dlg)
    other = QPushButton("Other", dlg)
    default = QPushButton("Default", dlg)
    default.setDefault(True)
    row.addWidget(other)
    row.addWidget(default)
    dlg.show()
    qapp.processEvents()
    return dlg, other, default


@pytest.mark.parametrize("mode", MODES)
def test_the_default_is_filled_in_the_app_accent(qapp, mode):
    _dlg, other, default = _dialog(qapp, mode)
    assert default.isDefault() and not other.isDefault()
    assert _near(_fill(default), app_accent(mode)), (mode, _fill(default).name())
    assert _near(_fill(other), PLAIN_FILL[mode]), (mode, _fill(other).name())


@pytest.mark.parametrize("mode", MODES)
def test_a_window_with_an_accent_fills_it_in_its_own(qapp, mode):
    _dlg, other, default = _dialog(qapp, mode, accent=SPEC_GREEN)
    want = neutral_styles.NM_ACTION if mode == "neutral" else SPEC_GREEN
    assert _near(_fill(default), want), (mode, _fill(default).name())
    assert _near(_fill(other), PLAIN_FILL[mode]), (mode, _fill(other).name())


@pytest.mark.parametrize("mode", MODES)
def test_a_disabled_default_is_not_filled_in_the_accent(qapp, mode):
    _dlg, _other, default = _dialog(qapp, mode, accent=SPEC_GREEN)
    default.setEnabled(False)
    qapp.processEvents()
    # (Qt itself hands the default away from a disabled button in a QDialog;
    # either way, a button that cannot be pressed is not drawn as the action.)
    fill = _fill(default)
    assert not _near(fill, app_accent(mode), 12), (mode, fill.name())
    if mode != "neutral":
        assert not _near(fill, SPEC_GREEN, 40), (mode, fill.name())


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("accent", [None, SPEC_GREEN])
def test_a_safe_default_keeps_the_ordinary_look(qapp, mode, accent):
    """Cancel as the default of a Delete question: Return presses it, and it
    is not drawn as the main action."""
    _dlg, _other, default = _dialog(qapp, mode, accent=accent)
    mark_safe_default(default)
    qapp.processEvents()
    assert default.isDefault()
    assert _near(_fill(default), PLAIN_FILL[mode]), (mode, _fill(default).name())


@pytest.mark.parametrize("mode", MODES)
def test_a_message_box_in_an_accent_window_fills_its_default(qapp, mode):
    """The Measurement Report's Update / Create New question is a QMessageBox
    parented to the report window: it inherits the window's sheet, and its
    default (Create New) is filled in the window's green."""
    dlg, _other, _default = _dialog(qapp, mode, accent=SPEC_GREEN)
    box = QMessageBox(dlg)
    _KEEP.append(box)
    new = box.addButton("Create New", QMessageBox.ButtonRole.AcceptRole)
    upd = box.addButton("Update", QMessageBox.ButtonRole.AcceptRole)
    box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(new)
    want = neutral_styles.NM_ACTION if mode == "neutral" else SPEC_GREEN
    box.show()
    qapp.processEvents()
    assert new.isDefault() and not upd.isDefault()
    assert _near(_fill(new), want), (mode, _fill(new).name())
    assert _near(_fill(upd), PLAIN_FILL[mode]), (mode, _fill(upd).name())


def test_the_fill_does_not_follow_the_focus(qapp):
    """QDialog autoDefault: a focused autoDefault button borrows the default,
    so a fill would jump to Cancel when the user tabs to it. After
    `freeze_default`, focus moves and the default (and fill) stays."""
    dlg, other, default = _dialog(qapp, "light")
    assert other.autoDefault()          # what a QPushButton in a QDialog is
    freeze_default(dlg)
    dlg.activateWindow()
    other.setFocus()
    qapp.processEvents()
    assert default.isDefault() and not other.isDefault()
    assert not other.autoDefault()
