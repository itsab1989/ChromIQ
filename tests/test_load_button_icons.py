"""Load buttons on the Measure / Build Profile tabs are icon-only glyph
buttons (Sebastian), matching the Create Chart / Print load buttons — no text,
a friendly tooltip, painted in the tab's accent colour."""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtGui import QPixmap, QPainter  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="module")
def _app():
    return QApplication.instance() or QApplication([])


def _paints_without_error(btn) -> bool:
    pm = QPixmap(btn.size())
    pm.fill()
    p = QPainter(pm)
    try:
        btn.render(p)
    finally:
        p.end()
    return True


def test_measured_chart_button_paints(_app):
    from ui.widgets import MeasuredChartButton
    btn = MeasuredChartButton("#37bcd6")
    assert btn.text() == ""                       # icon-only
    assert _paints_without_error(btn)
    btn._hover = True                              # hover branch also paints
    assert _paints_without_error(btn)


class _Settings:
    def __init__(self, **kw):
        self._d = dict(kw)

    def get(self, k, d=None):
        return self._d.get(k, d)

    def set(self, k, v):
        self._d[k] = v


def test_the_load_buttons_now_live_in_the_masthead(_app):
    """Load .ti2 used to sit on BOTH the Print and Measure tabs, and Load
    Project on Create Chart. All three moved to the masthead (#130, spec agreed
    2026-07-31): they act on the whole app, and one Load .ti2 replaces two.
    """
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.tabs.tab_measure import TabMeasure
    from ui.tabs.tab_print import TabPrint
    from ui.tabs.tab_chart import TabChart

    assert not hasattr(TabMeasure(ArgyllRunner(_Settings()), _Settings()),
                       "_load_ti1_btn")
    s = AppSettings()
    assert not hasattr(TabChart(ArgyllRunner(s), FileManager(s), s),
                       "_load_profile_btn")
    assert not hasattr(TabPrint(_Settings()), "_load_btn")


def test_the_masthead_carries_both_load_buttons(_app):
    from ui.masthead_header import MastheadHeader
    m = MastheadHeader()
    m.resize(1400, 130)
    for btn in (m._load_project_btn, m._load_ti2_btn):
        assert btn.text() == ""                   # icon-only, like the rest
        assert btn.toolTip()
        assert not btn.icon().isNull()
        assert btn.size() == m._tools_btn.size()  # same size as Tools/Prefs/?


def test_the_masthead_load_buttons_follow_the_agreed_geometry(_app):
    """Knut's spec: same icon size, the gap between them equal to the
    Tools<->Preferences gap, and the left margin equal to the Help icon's
    right margin."""
    from PyQt6.QtWidgets import QApplication
    from ui.masthead_header import MastheadHeader
    m = MastheadHeader()
    m.resize(1400, 130)
    m.show()                      # resizeEvent is what places them
    QApplication.processEvents()
    lp, lt = m._load_project_btn, m._load_ti2_btn
    right_margin = m.width() - (m._help_btn.x() + m._help_btn.width())
    assert lp.x() == right_margin
    assert lt.x() - (lp.x() + lp.width()) == m._btn.x() - (
        m._tools_btn.x() + m._tools_btn.width())
    assert lp.y() == lt.y() == m._tools_btn.y()   # one row with the rest


def test_the_masthead_load_buttons_grey_while_measuring(_app):
    """Knut, 2026-07-31: "Remember that also the Load Project icon should be
    Disabled while a measurement runs." """
    from ui.masthead_header import MastheadHeader
    m = MastheadHeader()
    # `set_availability` replaced `set_load_buttons_enabled` in #164: the three
    # left-hand buttons are one group with one source of truth, because three
    # separate enable paths is how two of them ended up disagreeing.
    m.set_availability(MastheadHeader.BUSY_MEASURING, has_project=True)
    assert not m._load_project_btn.isEnabled()
    assert not m._load_ti2_btn.isEnabled()
    assert not m._close_project_btn.isEnabled()
    m.set_availability(None, has_project=True)
    assert m._load_project_btn.isEnabled()
    assert m._load_ti2_btn.isEnabled()
    assert m._close_project_btn.isEnabled()
    # …and the third one also greys when there is simply nothing to close.
    m.set_availability(None, has_project=False)
    assert m._load_project_btn.isEnabled(), "Open Project must stay offered"
    assert not m._close_project_btn.isEnabled()


def test_stacked_pages_button_paints(_app):
    from ui.widgets import StackedPagesButton
    btn = StackedPagesButton("#e0447b")
    assert btn.text() == ""                       # icon-only
    assert _paints_without_error(btn)
    btn._hover = True                              # hover branch (opaque knockout)
    assert _paints_without_error(btn)





def test_build_load_buttons_are_icon_only_measured_glyph(_app):
    from core.argyll_runner import ArgyllRunner
    from ui.tabs.tab_profile import TabProfile
    from ui.widgets import MeasuredChartButton
    tab = TabProfile(ArgyllRunner(_Settings()), _Settings())
    for btn in (tab._load_btn, tab._pc_load_btn):
        assert isinstance(btn, MeasuredChartButton)
        assert btn.text() == ""
        assert btn.toolTip()
