"""B8-1263 (beta 44 challenge F7): End did nothing in the open "Select preset"
list, while Up, Down, Right and Left on "▸ N more presets" worked.

Qt's End goes to the MODEL's last row, and that row is nearly always hidden
(the paper filter, or a preset under a closed arrow): measured, 204 rows, 35
shown, the last one hidden, and End left the highlight where it was. Home
happened to work only because the first row, "none", is always shown.

Now Home and End go to the first and last row Up and Down can reach: shown,
enabled and selectable, so a heading or separator is skipped and an open
list's arrow row counts, as it does for Down.

MUTATION (red here): drop the Home/End branch from
``_CappedComboBox.eventFilter``: End stays put.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QEvent, QSettings, Qt                  # noqa: E402
from PyQt6.QtGui import QKeyEvent                               # noqa: E402
from PyQt6.QtWidgets import QApplication                        # noqa: E402

import core.curated_presets as cp                               # noqa: E402
from ui.tabs import tab_chart as TC                             # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def tab(qapp, tmp_path):
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    s.set(cp.PAPER_FILTER_KEY, True)
    s.set("chart_instrument", "i1")
    t = TC.TabChart(ArgyllRunner(s), FileManager(s), s)
    t._switch_mode("manual")
    t.show()
    qapp.processEvents()
    yield t
    t._preset_combo.hidePopup()
    t.hide()
    t.deleteLater()
    qapp.processEvents()


def _key(qapp, view, key):
    qapp.sendEvent(view, QKeyEvent(QEvent.Type.KeyPress, key,
                                   Qt.KeyboardModifier.NoModifier))
    qapp.processEvents()
    return view.currentIndex().row()


def _reachable(cb):
    """The rows Up and Down step through: shown, enabled, selectable."""
    view = cb.view()
    model = cb.model()
    out = []
    for r in range(cb.count()):
        if view.isRowHidden(r):
            continue
        f = model.flags(model.index(r, 0))
        if f & Qt.ItemFlag.ItemIsEnabled and f & Qt.ItemFlag.ItemIsSelectable:
            out.append(r)
    return out


def test_end_and_home_in_the_open_list(tab, qapp):
    cb = tab._preset_combo
    view = cb.view()
    cb.showPopup()
    qapp.processEvents()
    assert view.isRowHidden(cb.count() - 1), (
        "the premise: the model's last row is hidden")
    rows = _reachable(cb)
    assert _key(qapp, view, Qt.Key.Key_End) == rows[-1]
    assert _key(qapp, view, Qt.Key.Key_Home) == rows[0]
    # End really is where Down stops: pressing Down from there stays there
    _key(qapp, view, Qt.Key.Key_End)
    assert _key(qapp, view, Qt.Key.Key_Down) == rows[-1]


def test_end_never_lands_on_a_heading_and_follows_an_open_arrow(tab, qapp):
    cb = tab._preset_combo
    view = cb.view()
    cb.showPopup()
    qapp.processEvents()
    heads = {h for h, _e in TC.BUILTIN_PRESET_GROUPS}
    end = _key(qapp, view, Qt.Key.Key_End)
    assert cb.itemText(end) not in heads and cb.itemData(end) is not None \
        or cb.itemData(end, cb.MORE_ROLE)
    # open the last group's arrow with Right: End reaches its new last row
    if cb.itemData(end, cb.MORE_ROLE):
        _key(qapp, view, Qt.Key.Key_Right)
        rows = _reachable(cb)
        assert _key(qapp, view, Qt.Key.Key_End) == rows[-1]
        assert _key(qapp, view, Qt.Key.Key_Home) == rows[0]
