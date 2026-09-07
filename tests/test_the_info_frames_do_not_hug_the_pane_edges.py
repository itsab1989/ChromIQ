"""The two info frames under the Create Chart preview keep their outer gaps.

Basti, 4.2.0: *"In the Create Chart tab under the TIFF preview, the left side of
the frame around the Measured from Preview section touches the panel separator,
and the right side of the frame around the Chart layout information section
touches the right side of the main window. There should be a gap."*

He was right, and the reason was that ``_info_row`` in ``ui/tabs/tab_chart.py``
carried ``setContentsMargins(0, 0, 0, 0)``. Both panels are plain ``QGroupBox``es
and ``ui/styles.py`` gives them ``margin-top: 14px`` with **no** left/right
margin, so their 1 px border is drawn at the widget's own edge: 0 px of layout
margin is 0 px of visible gap. Measured on screen at 1700x1050 before the fix,
the "Measured from Preview" frame started at x=584 with the splitter handle
ending at x=584, and "Chart layout information" ended at x=1700 in a 1700 px
window. Both gaps: 0.

THE THREE THINGS THIS FILE PINS, and the third is the one a future reader will
otherwise undo:

1. The outer gaps exist, on BOTH sides, and are the tab's own 16 px, the same
   inset the left pane already uses against the window edge and the separator.
2. The 8 px channel between the two frames is untouched.
3. **The TIFF preview above them still bleeds to both edges.** That is not the
   same defect left unfixed, it is a design decision: ``ui/tiff_preview.py``
   sets ``border-left: none`` on the image label and the 4 px splitter handle is
   painted in the very same border colour, so the handle IS the preview's left
   border. Insetting the preview would stand it off a border it wears. Anyone
   "finishing the job" by moving the margin up to ``right_layout`` trips this.

Geometry, not source text: a test that greps for the literal ``16`` would pass
on a layout that never applies it.
"""
from __future__ import annotations

import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtCore import QPoint, QSettings          # noqa: E402
from PyQt6.QtWidgets import QApplication, QSplitter  # noqa: E402

from core.argyll_runner import ArgyllRunner         # noqa: E402
from core.file_manager import FileManager           # noqa: E402
from core.settings import AppSettings               # noqa: E402
from ui.tabs.tab_chart import TabChart              # noqa: E402

#: What the fix put on ``_info_row``. Equal to the left pane's own
#: ``left_layout.setContentsMargins(16, 12, 16, 12)``.
OUTER_GAP = 16
#: What #93 put between the two frames when it added the second one.
CHANNEL = 8


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _lay_out(qapp, tab, width: int) -> None:
    """Give *tab* a real geometry. `resize()` alone is not enough: a QSplitter
    distributes space in its own resizeEvent, so on a widget that was never
    shown both panes come back 0 wide and every gap below reads as noise."""
    tab.resize(width, 900)
    tab.show()
    tab.layout().activate()
    qapp.processEvents()


@pytest.fixture
def laid_out_tab(qapp, tmp_path):
    """A real ``TabChart``, sized wide enough that nothing is over-constrained,
    with its layout actually activated so the geometry below is the geometry
    Qt would paint."""
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "t.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    s.set("margin_inspector_show", True)
    s.set("layout_info_show", True)
    tab = TabChart(ArgyllRunner(s), FileManager(s), s)
    # 1440 is what MainWindow opens at (`min(1440, screen.width())`); the info
    # row needs 1142 in English, so nothing here is being squeezed.
    _lay_out(qapp, tab, 1440)
    yield tab
    tab.close()


def _edges(tab):
    """(handle right edge, frame lefts/rights, pane right edge) in tab coords."""
    splitter = tab.findChild(QSplitter)
    handle = splitter.handle(1)
    handle_right = handle.mapTo(tab, QPoint(handle.width(), 0)).x()

    def span(w):
        return (w.mapTo(tab, QPoint(0, 0)).x(),
                w.mapTo(tab, QPoint(w.width(), 0)).x())

    return handle_right, span(tab._margin_panel), span(tab._layout_info_panel)


def test_the_left_frame_stands_off_the_panel_separator(laid_out_tab):
    """Basti's first half: the "Measured from Preview" frame must not sit on the
    divider the left pane already keeps 16 px away from."""
    handle_right, (mp_left, _), _ = _edges(laid_out_tab)
    assert mp_left - handle_right == OUTER_GAP, (
        f"'Measured from Preview' starts at x={mp_left} with the splitter handle "
        f"ending at x={handle_right}: a gap of {mp_left - handle_right} px, not "
        f"{OUTER_GAP}. _info_row's left contents margin in ui/tabs/tab_chart.py "
        f"is what sets this.")


def test_the_right_frame_stands_off_the_window_edge(laid_out_tab):
    """Basti's second half: "Chart layout information" must not run into the
    right side of the window."""
    _, _, (_, li_right) = _edges(laid_out_tab)
    assert laid_out_tab.width() - li_right == OUTER_GAP, (
        f"'Chart layout information' ends at x={li_right} in a "
        f"{laid_out_tab.width()} px pane: a gap of "
        f"{laid_out_tab.width() - li_right} px, not {OUTER_GAP}. _info_row's "
        f"right contents margin in ui/tabs/tab_chart.py is what sets this.")


def test_the_channel_between_the_two_frames_is_untouched(laid_out_tab):
    """Fixing the outside must not spend the 8 px #93 put on the inside."""
    _, (_, mp_right), (li_left, _) = _edges(laid_out_tab)
    assert li_left - mp_right == CHANNEL, (
        f"the channel between the two frames is {li_left - mp_right} px, not "
        f"{CHANNEL}")


def test_the_preview_above_them_still_bleeds_to_both_edges(laid_out_tab):
    """NOT the same defect left unfixed. `ui/tiff_preview.py` removes the image
    label's LEFT border on purpose and the splitter handle is painted in the
    border colour, so the handle is the preview's left border. The gap belongs
    on `_info_row`, not on `right_layout`, and this fails if someone moves it."""
    tab = laid_out_tab
    handle_right, _, _ = _edges(tab)
    prev = tab._preview
    left = prev.mapTo(tab, QPoint(0, 0)).x()
    right = prev.mapTo(tab, QPoint(prev.width(), 0)).x()
    assert left == handle_right, (
        f"the chart preview now starts {left - handle_right} px after the "
        f"splitter handle. It is meant to bleed into it: tiff_preview.py sets "
        f"`border-left: none` on the image label precisely so the handle can be "
        f"its left border. Put the gap on _info_row, not on right_layout.")
    assert right == tab.width(), (
        f"the chart preview now ends {tab.width() - right} px short of the pane "
        f"edge; it is a full-bleed image area and Basti did not report it.")


def test_both_gaps_survive_the_narrow_window_and_a_splitter_drag(qapp, tmp_path):
    """The left edge sits against a splitter, so the gap has to hold wherever
    the handle can go. It cannot go anywhere — ``left.setFixedWidth(580)`` pins
    the left pane's minimum and maximum together — and this pins that too, at
    MainWindow's own 900 px floor as well as at its 1440 px default."""
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "t.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    tab = TabChart(ArgyllRunner(s), FileManager(s), s)
    splitter = tab.findChild(QSplitter)

    for width in (900, 1440):
        for sizes in (None, [1, 10_000], [10_000, 1]):
            _lay_out(qapp, tab, width)
            if sizes is not None:
                splitter.setSizes(sizes)
                _lay_out(qapp, tab, width)
            handle_right, (mp_left, _), (_, li_right) = _edges(tab)
            where = f"{width} px pane, splitter sizes {splitter.sizes()}"
            assert mp_left - handle_right == OUTER_GAP, f"left gap lost at {where}"
            assert tab.width() - li_right == OUTER_GAP, f"right gap lost at {where}"
