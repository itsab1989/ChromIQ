"""Review D of beta 12: a window's default button is painted BOLD, so it is
measured bold, and the slow-chart window grows to its button row.

Measured on screen in Ukrainian: "Rebuild with faster layout" is 353 px in
regular Inter and 361 px bold, and the button was given room for the regular
weight: it lost a letter at each end. The window also has an explicit minimum
width, so Qt never widened it for the row once the button font was applied,
and the default button ran under Cancel (Russian and Ukrainian).
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PyQt6.QtGui import QFont, QFontMetrics  # noqa: E402
from PyQt6.QtWidgets import QApplication, QPushButton, QWidget  # noqa: E402

from ui.widgets import fit_button_width  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


LABEL = "Перебудуйте за допомогою швидшого макета"


def _button(default: bool, parent):
    b = QPushButton(LABEL, parent)
    f = QFont("Inter")
    f.setPixelSize(13)
    f.setCapitalization(QFont.Capitalization.AllUppercase)
    b.setFont(f)
    b.setDefault(default)
    return b


def test_the_default_button_gets_room_for_its_bold_label(qapp):
    host = QWidget()
    plain, default = _button(False, host), _button(True, host)
    fit_button_width(plain)
    fit_button_width(default)
    bold = QFont(default.font())
    bold.setBold(True)
    gap = (QFontMetrics(bold).horizontalAdvance(LABEL.upper())
           - QFontMetrics(plain.font()).horizontalAdvance(LABEL.upper()))
    assert gap > 0, "this font draws bold no wider; nothing to prove here"
    assert default.minimumWidth() >= plain.minimumWidth() + gap
    host.deleteLater()


def test_a_safe_default_is_drawn_regular_and_measured_regular(qapp):
    from ui.default_button import SAFE_DEFAULT
    host = QWidget()
    plain, safe = _button(False, host), _button(True, host)
    safe.setProperty(SAFE_DEFAULT, True)
    fit_button_width(plain)
    fit_button_width(safe)
    assert safe.minimumWidth() == plain.minimumWidth()
    host.deleteLater()


def test_the_slow_chart_window_grows_to_its_button_row(qapp):
    from ui.dialogs.slow_chart_dialog import SlowChartDialog
    dlg = SlowChartDialog(None, min_width=200, uses_profile=False)
    buttons = dlg.findChildren(QPushButton)
    for b in buttons:                     # what the button font filter does
        b.setMinimumWidth(b.sizeHint().width() + 150)
    dlg.show()
    qapp.processEvents()
    row = sum(b.minimumWidth() for b in buttons)
    assert dlg.width() >= row, (dlg.width(), row)
    dlg.close()
    dlg.deleteLater()
