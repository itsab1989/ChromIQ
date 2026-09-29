"""B8-1311 (Knut, #182 5845588201): Create Chart > Manual's Output and Presets
frames fold away with an arrow, like Basic and ChromIQ layout, and are open by
default.

*"some users with a macbook pro 14" screen have trouble reading and scrolling
the layout parameters in the manual mode in Create Chart tab. [...] For the
Output frame and Presets frame, make those frames also have an arrow, like
Basic or "ChromIQ layout" frames have, so that Output frame and Presets frame
can be minimised/hidden, but default is that they are open and showing its
content."*

Both frames are the same `CollapsibleGroupBox` as Basic and ChromIQ layout.
Like those, the folded state is not stored: it lasts for the session and a new
start opens both again (the default Knut asked for).

MUTATIONS (mutations.txt of the k50 proof): Output back to a plain QGroupBox,
red; Presets likewise, red; either frame created folded, red.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QPoint, QPointF, QSettings, Qt, QEvent  # noqa: E402
from PyQt6.QtGui import QMouseEvent                              # noqa: E402
from PyQt6.QtWidgets import QApplication, QScrollArea            # noqa: E402

from ui.tabs import tab_chart as TC                              # noqa: E402
from ui.widgets import CollapsibleGroupBox                       # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def settings(tmp_path):
    from core.settings import AppSettings
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    return s


def _tab(qapp, settings):
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    t = TC.TabChart(ArgyllRunner(settings), FileManager(settings), settings)
    t._switch_mode("manual")
    # the panel's share of a 1512 x 982 point window (MacBook Pro 14")
    t.resize(760, 820)
    t.show()
    qapp.processEvents()
    return t


@pytest.fixture()
def tab(qapp, settings):
    t = _tab(qapp, settings)
    yield t
    t.hide()
    t.deleteLater()
    qapp.processEvents()


def _frames(tab):
    return {"Output": tab._manual_output_grp, "Presets": tab._manual_presets_grp}


def _click_title(qapp, grp):
    p = QPoint(30, 6)
    for kind in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease):
        qapp.sendEvent(grp, QMouseEvent(
            kind, QPointF(p), QPointF(grp.mapToGlobal(p)),
            Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton
            if kind == QEvent.Type.MouseButtonPress else Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier))
    qapp.processEvents()


def _params_scroll(tab):
    """The scroll area that holds Manual's parameters (the targen group)."""
    w = tab._manual_targen_grp
    while w is not None and not isinstance(w, QScrollArea):
        w = w.parentWidget()
    assert w is not None
    return w


@pytest.mark.parametrize("name", ["Output", "Presets"])
def test_the_frame_folds_like_basic_and_is_open_by_default(tab, qapp, name):
    grp = _frames(tab)[name]
    assert isinstance(grp, CollapsibleGroupBox)
    assert grp.title() == name
    assert not grp.is_collapsed() and grp.body.isVisible()
    _click_title(qapp, grp)
    assert grp.is_collapsed() and not grp.body.isVisible()
    _click_title(qapp, grp)
    assert not grp.is_collapsed() and grp.body.isVisible()


def test_folding_both_gives_the_parameters_the_height(tab, qapp):
    sa = _params_scroll(tab)
    before = sa.viewport().height()
    for grp in _frames(tab).values():
        _click_title(qapp, grp)
    qapp.processEvents()
    after = sa.viewport().height()
    folded = sum(g.body.sizeHint().height() for g in _frames(tab).values())
    assert after - before >= folded * 0.8, (before, after, folded)


def test_a_new_start_opens_both_again(qapp, settings):
    t = _tab(qapp, settings)
    for grp in _frames(t).values():
        grp.set_collapsed(True)
    t.hide()
    t.deleteLater()
    qapp.processEvents()
    t2 = _tab(qapp, settings)
    try:
        assert all(not g.is_collapsed() for g in _frames(t2).values())
    finally:
        t2.hide()
        t2.deleteLater()
        qapp.processEvents()
