"""`keep_message_box_inside_the_work_area(box, widen_when_it_fits=False)`
leaves a box that fits exactly as Qt sizes it (4.3.16).

The boxes routed through the helper in 4.3.16 had bypassed it until then, and
Basti's rule for that release is that a short box looks as in 4.3.15. Step 1
("widen for the text") took a one-line question from 420 to 784 px wide on
screen and every other short box 5 to 13 px wider, so those calls widen only
a box that would otherwise be too tall. The default keeps what warn / inform
/ ask have done since 4.3.15.
"""
from __future__ import annotations

from PyQt6.QtCore import QRect
from PyQt6.QtGui import QScreen
from PyQt6.QtWidgets import QApplication, QMessageBox

import pytest

ONE_LINE = ("A preset named “Glossy 300” already exists. Overwrite "
            "it, or cancel and choose a different name.")


@pytest.fixture
def _app():
    return QApplication.instance() or QApplication([])


def _box(text: str) -> QMessageBox:
    box = QMessageBox()
    box.setIcon(QMessageBox.Icon.NoIcon)
    box.setWindowTitle("ChromIQ")
    box.setText(text)
    box.addButton("Overwrite", QMessageBox.ButtonRole.AcceptRole)
    box.addButton(QMessageBox.StandardButton.Cancel)
    return box


def test_a_box_that_fits_is_not_widened(_app):
    from ui import widgets
    box = _box(ONE_LINE)
    rows = box.layout().rowCount()
    widgets.keep_message_box_inside_the_work_area(box, widen_when_it_fits=False)
    assert box.layout().rowCount() == rows, "a spacer row was added"
    assert box.text() == ONE_LINE and not box.detailedText()
    box.deleteLater()


def test_the_default_still_widens_it_as_in_4_3_15(_app):
    """The mutation control: warn / inform / ask keep step 1."""
    from ui import widgets
    box = _box(ONE_LINE)
    rows = box.layout().rowCount()
    widgets.keep_message_box_inside_the_work_area(box)
    assert box.layout().rowCount() == rows + 1
    box.deleteLater()


def test_a_box_too_tall_for_the_work_area_is_still_widened(_app, monkeypatch):
    from ui import widgets
    text = "\n\n".join(["This paragraph is long enough to be wrapped by Qt "
                        "at the width a message box is given. " * 3] * 6)
    box = _box(text)
    real = QScreen.availableGeometry

    def short(screen):
        r = real(screen)
        return QRect(r.x(), r.y(), max(r.width(), 1400), 420)
    monkeypatch.setattr(QScreen, "availableGeometry", short)
    widgets.keep_message_box_inside_the_work_area(box, widen_when_it_fits=False)
    lay = box.layout()
    spacers = [lay.itemAt(i).spacerItem() for i in range(lay.count())
               if lay.itemAt(i).spacerItem() is not None]
    assert any(sp.sizeHint().width() > 420 for sp in spacers), (
        "a box too tall for the work area was not widened for its text")
    box.deleteLater()
